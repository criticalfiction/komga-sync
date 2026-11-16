''' ===========================================================================

Runs one full sync, keeping ComicRack responsive:

  1. ComicRack's thread: read every library book's state (fast, no I/O).
  2. Background thread:  fetch Komga's books, load the snapshot, decide.
  3. First full sync only (no snapshot yet): show a summary on ComicRack's
     thread and ask before changing anything.
  4. Background thread:  push ComicRack changes to Komga.
  5. ComicRack's thread: apply Komga changes to ComicRack's books.
  6. Background thread:  save the snapshot and the "last sync" status.

Only one sync runs at a time. Failures are logged and shown as the last
sync status in the settings dialog; no popups.

=========================================================================== '''
import clr
import log
import uiutil
import syncengine
from syncengine import PUSH, PULL, NONE
from crbooks import read_state, apply_state
from komgaclient import KomgaClient, KomgaError
from settings import Settings, FIRST_SYNC_SOURCES
from snapshot import Snapshot
import pagemap

clr.AddReference('System')
clr.AddReference('System.Windows.Forms')
from System import DateTime
from System.Threading import Thread, ThreadStart, Monitor, ManualResetEvent
from System.Windows.Forms import MessageBox, MessageBoxButtons, MessageBoxIcon, \
    MessageBoxDefaultButton, DialogResult


class SyncResult(object):
    '''What one run did. ok is False if the run failed or was cancelled.'''

    def __init__(self):
        self.ok = False
        self.pushed = self.pulled = self.failed = 0
        self.not_in_komga = self.not_in_comicrack = 0
        self.first_sync = False
        self.cancelled = False
        self.skipped = False          # push-only run with a first sync pending
        self.error = None

    def summary(self):
        if self.error:
            return 'failed: %s' % self.error
        if self.cancelled:
            return 'first sync cancelled; automatic sync turned off'
        if self.skipped:
            return 'skipped: the first sync hasn\'t been confirmed yet'
        parts = ['%d pulled' % self.pulled, '%d pushed' % self.pushed]
        if self.failed:
            parts.append('%d failed' % self.failed)
        if self.not_in_komga:
            parts.append('%d %s not in Komga' % (
                self.not_in_komga, 'book' if self.not_in_komga == 1 else 'books'))
        return ', '.join(parts)


# ===========================================================================
def ask_first_sync(owner, source, push_count, pull_count, not_in_komga):
    '''The first-full-sync summary; True to go ahead. Runs on the UI thread.'''
    name = dict(FIRST_SYNC_SOURCES)[source].split(' (')[0]
    text = ('Komga Sync is about to sync for the first time, using "%s".\n\n'
            '    %d books will be updated in Komga\n'
            '    %d books will be updated in ComicRack\n'
            '    %d books in ComicRack aren\'t in Komga (left alone)\n\n'
            'Not backed up your ComicRack library yet? Answer No, close '
            'ComicRack and copy ComicDb.xml from\n'
            '%%APPDATA%%\\cYo\\ComicRack Community Edition\n'
            'somewhere safe. (No turns automatic sync off: tick it again in '
            'the Komga Sync settings when you\'re ready.)\n\nGo ahead?'
            % (name, push_count, pull_count, not_in_komga))
    answer = MessageBox.Show(owner, text, 'Komga Sync: first sync',
                             MessageBoxButtons.YesNo, MessageBoxIcon.Question,
                             MessageBoxDefaultButton.Button2)
    return answer == DialogResult.Yes


# ===========================================================================
class SyncRunner(object):
    '''
    comicrack      object with .App.GetLibraryBooks() (ComicRack itself)
    ui             a Control on ComicRack's main thread (ComicRack.MainWindow)
    make_client    settings -> KomgaClient (tests pass a fake)
    ask            the first-sync question (owner, source, push, pull, missing)
                   -> bool
    only_keys      if given, only books with these path keys are synced
                   (tests, so a live run touches only the test book)
    '''

    def __init__(self, comicrack, ui, make_client=None, ask=ask_first_sync,
                 only_keys=None):
        self.comicrack = comicrack
        self.ui = ui
        self.make_client = make_client or (
            lambda s: KomgaClient(s.url, s.api_key))
        self.ask = ask
        self.only_keys = set(only_keys) if only_keys else None
        self.__lock = object()
        self.__running = False
        self.__idle = ManualResetEvent(True)     # set while no sync is running
        self.last_result = None

    @property
    def running(self):
        return self.__running

    def wait(self, timeout_ms):
        '''Waits up to timeout_ms for a running sync to finish; True if idle.'''
        return self.__idle.WaitOne(timeout_ms)

    # -------------------------------------------------------------------
    def run_once(self, on_done=None, push_only=False, timeout_ms=None):
        '''
        Starts a sync; call on ComicRack's thread. Returns False (and does
        nothing) if one is already running. on_done(result) is called on
        the background thread when it's finished.

        push_only: only send ComicRack's changes to Komga; don't change
        ComicRack's books or ask anything (used while ComicRack closes,
        when its window can't be used). A pending first sync is skipped.
        timeout_ms: per-request time limit for Komga.
        '''
        Monitor.Enter(self.__lock)
        try:
            if self.__running:
                return False
            self.__running = True
            self.__idle.Reset()
        finally:
            Monitor.Exit(self.__lock)

        result = SyncResult()
        try:
            settings = Settings.load()
            cr_books = self.__read_comicrack()
        except Exception, ex:
            log.debug_exc('reading ComicRack books failed')
            result.error = 'reading ComicRack books: %s' % ex
            self.__finish(result, None, on_done)
            return True

        def work():
            try:
                self.__sync(settings, cr_books, result, push_only, timeout_ms)
            except KomgaError, ex:
                result.error = ex.message
            except Exception, ex:
                log.debug_exc('sync failed')
                result.error = unicode(ex)
            self.__finish(result, settings, on_done)

        thread = Thread(ThreadStart(work))
        thread.IsBackground = True
        thread.Name = 'Komga Sync'
        thread.Start()
        return True

    # -------------------------------------------------------------------
    def __read_comicrack(self):
        '''key -> CrState for every library book with a file (main thread).'''
        books, duplicates = {}, set()
        for book in self.comicrack.App.GetLibraryBooks():
            state = read_state(book)
            if state is None:
                continue
            if self.only_keys is not None and state.key not in self.only_keys:
                continue
            if state.key in books:
                duplicates.add(state.key)
            books[state.key] = state
        for key in duplicates:
            # two library entries for one file: can't tell which one to use
            log.debug('skipped: the same file is in the library twice: %s' % key)
            del books[key]
        return books

    def __sync(self, settings, cr_books, result, push_only=False, timeout_ms=None):
        now = DateTime.UtcNow
        client = self.make_client(settings)
        if timeout_ms is not None and hasattr(client, 'timeout_ms'):
            client.timeout_ms = timeout_ms
        komga = {}
        for kb in client.list_books():
            if self.only_keys is None or kb.key in self.only_keys:
                komga[kb.key] = kb
        snap = Snapshot.load()
        if snap.damaged:
            log.debug('snapshot was damaged: every book is treated as never synced')
        result.first_sync = not snap.existed
        result.not_in_komga = len([k for k in cr_books if k not in komga])
        result.not_in_comicrack = len([k for k in komga if k not in cr_books])

        # decide for every book found on both sides
        plan = []
        for key, cr in cr_books.items():
            kb = komga.get(key)
            if kb is None:
                continue
            d = syncengine.decide(cr, kb, snap.entries.get(key), now,
                                  settings.first_sync_source)
            plan.append((key, cr, kb, d))
        pushes = [p for p in plan if p[3].action == PUSH]
        pulls = [p for p in plan if p[3].action == PULL]
        log.debug('sync plan: %d books matched, %d to push, %d to pull%s' % (
            len(plan), len(pushes), len(pulls), ' (first sync)' if result.first_sync else ''))

        if push_only:
            if result.first_sync:
                log.debug('push-only sync skipped: the first sync hasn\'t been confirmed')
                result.skipped = True
                result.ok = True
                return
            deferred = pulls                  # pulled at the next full sync
            pulls = []
        else:
            deferred = []

        if result.first_sync and (pushes or pulls):
            answer = [False]

            def ask():
                answer[0] = self.ask(self.ui, settings.first_sync_source,
                                     len(pushes), len(pulls), result.not_in_komga)
            if not uiutil.invoke(self.ui, ask, wait=True) or not answer[0]:
                result.cancelled = True
                return

        new_entries = {}
        # books whose pull was put off keep their old record, so the next
        # full sync still sees "changed in Komga"
        for key, cr, kb, d in deferred:
            if key in snap.entries:
                new_entries[key] = snap.entries[key]
        # books that need nothing: record them as synced now
        for key, cr, kb, d in plan:
            if d.action == NONE:
                new_entries[key] = syncengine.make_entry(
                    cr.index, cr.completed, kb.page, kb.completed, now)

        # ComicRack -> Komga
        for key, cr, kb, d in pushes:
            try:
                if d.komga == pagemap.UNREAD:
                    client.clear_progress(kb.id)
                elif d.komga == pagemap.COMPLETED:
                    client.set_progress(kb.id, completed=True)
                else:
                    client.set_progress(kb.id, page=d.komga)
                page, done = syncengine.komga_after_push(d.komga, kb.pages)
                new_entries[key] = syncengine.make_entry(cr.index, cr.completed,
                                                         page, done, now)
                result.pushed += 1
                log.debug('pushed %s -> %s (%s)' % (cr.path, d.komga, d.reason))
            except KomgaError, ex:
                if ex.kind in ('unreachable', 'timeout', 'auth'):
                    raise                     # no point trying the rest
                result.failed += 1
                log.debug('push failed for %s: %s' % (cr.path, ex.message))
                if key in snap.entries:
                    new_entries[key] = snap.entries[key]   # try again next time

        # Komga -> ComicRack, on ComicRack's thread
        if pulls:
            done = []

            def apply_all():
                for key, cr, kb, d in pulls:
                    try:
                        index, completed = d.cr
                        apply_state(cr.book, index, completed)
                        after = read_state(cr.book)
                        done.append((key, after, kb, d))
                    except Exception:
                        log.debug_exc('pull failed for %s' % cr.path)
            if not uiutil.invoke(self.ui, apply_all, wait=True):
                raise Exception('ComicRack\'s window isn\'t available')
            for key, after, kb, d in done:
                new_entries[key] = syncengine.make_entry(after.index, after.completed,
                                                         kb.page, kb.completed, now)
                log.debug('pulled %s <- %s (%s)' % (after.path, d.cr, d.reason))
            result.pulled = len(done)
            failed = len(pulls) - len(done)
            result.failed += failed
            for key, cr, kb, d in pulls:
                if key not in new_entries and key in snap.entries:
                    new_entries[key] = snap.entries[key]

        # books no longer on both sides are dropped from the snapshot
        snap.entries = new_entries
        snap.save()
        result.ok = True

    def __finish(self, result, settings, on_done):
        self.last_result = result
        log.debug('sync finished: %s' % result.summary())
        try:
            s = Settings.load()           # fresh: the dialog may have saved
            s.last_sync_time = DateTime.Now.ToString('yyyy-MM-dd HH:mm')
            s.last_sync_status = result.summary()
            if result.cancelled:
                s.enabled = False
            s.save()
        except Exception:
            log.debug_exc('saving the sync status failed')
        Monitor.Enter(self.__lock)
        try:
            self.__running = False
            self.__idle.Set()
        finally:
            Monitor.Exit(self.__lock)
        if on_done is not None:
            try:
                on_done(result)
            except Exception:
                log.debug_exc('on_done failed')
