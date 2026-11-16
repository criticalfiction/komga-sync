''' ===========================================================================

When syncs run, while ComicRack is open:
  - at start-up (once ComicRack's window is ready)
  - every "Sync every N minutes" (checked every 30 s, so a changed interval
    applies within 30 s, no restart needed)
  - when ComicRack's window is activated (you switch back to it), at most
    once a minute. ComicRack's reader keeps its own copy of the page a book
    was opened at, so progress has to be pulled BEFORE you open the book;
    switching back from your phone triggers that.
  - when ComicRack closes: push-only, waiting at most a few seconds

Nothing runs unless the plugin is configured and switched on (re-checked
each time, so changes in the settings dialog apply straight away).

=========================================================================== '''
import clr
import log
from settings import Settings

clr.AddReference('System')
clr.AddReference('System.Windows.Forms')
from System import DateTime, EventHandler
from System.Windows.Forms import Timer

CHECK_EVERY_MS = 30 * 1000
ACTIVATE_GAP_SECONDS = 60
SHUTDOWN_WAIT_MS = 5000
SHUTDOWN_REQUEST_TIMEOUT_MS = 4000


class Scheduler(object):
    '''
    runner      a SyncRunner
    window      ComicRack's main window (for the Activated event), or None
    now         returns the current UTC time (tests pass their own clock)
    load        returns the current Settings
    '''

    def __init__(self, runner, window=None, now=None, load=None):
        self.runner = runner
        self.window = window
        self.now = now or (lambda: DateTime.UtcNow)
        self.load = load or Settings.load
        self.last_start = None          # UTC time the last sync started
        self.timer = None
        self.__activated_handler = None

    def _allowed(self):
        try:
            s = self.load()
        except Exception:
            log.debug_exc('settings unreadable')
            return None
        return s if s.is_configured() and s.enabled else None

    def _start(self, why):
        if self.runner.run_once():
            self.last_start = self.now()
            log.debug('sync started (%s)' % why)
            return True
        return False                    # one is already running

    # -------------------------------------------------------------------
    def start(self):
        '''Start-up: one sync now, then the timer. Call on ComicRack's thread.'''
        if self._allowed():
            self._start('start-up')
        self.timer = Timer()
        self.timer.Interval = CHECK_EVERY_MS
        self.timer.Tick += self.__on_tick
        self.timer.Start()
        if self.window is not None:
            self.__activated_handler = EventHandler(self.__on_activated)
            self.window.Activated += self.__activated_handler

    def stop(self):
        if self.timer is not None:
            self.timer.Stop()
            self.timer.Dispose()
            self.timer = None
        if self.window is not None and self.__activated_handler is not None:
            self.window.Activated -= self.__activated_handler
            self.__activated_handler = None

    def __on_tick(self, sender, event):
        try:
            self.tick()
        except Exception:
            log.debug_exc('timer tick failed')

    def __on_activated(self, sender, event):
        try:
            self.activated()
        except Exception:
            log.debug_exc('activated sync failed')

    # -------------------------------------------------------------------
    def tick(self):
        '''Runs a sync if the interval has passed since the last one started.'''
        s = self._allowed()
        if s is None or self.runner.running:
            return False
        if self.last_start is not None and \
                (self.now() - self.last_start).TotalMinutes < s.interval_minutes:
            return False
        return self._start('every %d min' % s.interval_minutes)

    def activated(self):
        '''ComicRack's window came to the front: sync unless one ran recently.'''
        if self._allowed() is None or self.runner.running:
            return False
        if self.last_start is not None and \
                (self.now() - self.last_start).TotalSeconds < ACTIVATE_GAP_SECONDS:
            return False
        return self._start('ComicRack activated')

    def shutdown(self):
        '''
        ComicRack is closing: send ComicRack's latest changes to Komga,
        waiting at most SHUTDOWN_WAIT_MS. Never raises.
        '''
        try:
            self.stop()
            if self._allowed() is None:
                return
            # let a sync that's already running finish (briefly)
            if self.runner.running and not self.runner.wait(SHUTDOWN_WAIT_MS):
                log.debug('shutdown: a sync was still running; not waiting longer')
                return
            if self.runner.run_once(push_only=True,
                                    timeout_ms=SHUTDOWN_REQUEST_TIMEOUT_MS):
                if not self.runner.wait(SHUTDOWN_WAIT_MS):
                    log.debug('shutdown: Komga sync didn\'t finish in time; '
                              'the rest is sent at the next start')
        except Exception:
            log.debug_exc('shutdown sync failed')
