'''
Full sync runs (background thread, UI-thread apply, snapshot, status) with
real in-memory ComicBooks and a fake Komga.
'''
from testlib import check, finish, temp_data_dir, pump
import clr
clr.AddReference('System')
from System.IO import File

import paths
import settings as S
from crbooks import read_state, apply_state
from komgaclient import KomgaError
from syncrunner import SyncRunner
from fakes import make_book, FakeComicRack, FakeKomga

temp_data_dir()
s = S.Settings()
s.api_key = 'x'
s.save()

A, B, C, D, E = [u'X:\\Comics\\%s.cbz' % n for n in
                 (u'A read here', u'B further in Komga', u'C unread', u'D only in ComicRack',
                  u'E only in Komga')]
books = [make_book(A, completed=True), make_book(B, index=4), make_book(C),
         make_book(D, index=2)]
by_path = dict((b.FilePath, b) for b in books)
cr = FakeComicRack(books)
komga = FakeKomga({A: (20, None, False), B: (20, 10, False), C: (20, None, False),
                   E: (20, 3, False)})

questions = []
answer = [False]


def ask(owner, source, pushes, pulls, missing):
    questions.append((source, pushes, pulls, missing))
    return answer[0]


runner = SyncRunner(cr, cr.MainWindow, make_client=lambda st: komga, ask=ask)


def run():
    done = []
    started = runner.run_once(on_done=done.append)
    pump(20, lambda: bool(done))
    return started, (done[0] if done else None)


def cr_state(path):
    st = read_state(by_path[path])
    return (st.index, st.completed)


print('--- first sync, answered No')
started, r = run()
check('started', started, True)
check('asked once: most read, 1 push, 1 pull, 1 not in Komga', questions,
      [(S.FIRST_SYNC_MOST_READ, 1, 1, 1)])
check('cancelled, nothing changed', (r.cancelled, komga.state(A), cr_state(B)),
      (True, (None, False), (4, False)))
check('no snapshot saved', File.Exists(paths.state_path()), False)
check('automatic sync switched off', S.Settings.load().enabled, False)
check('status explains it', S.Settings.load().last_sync_status.startswith('first sync cancelled'),
      True)

print('--- first sync, answered Yes')
answer[0] = True
st = S.Settings.load()
st.enabled = True
st.save()
started, r = run()
check('ok', (r.ok, r.error), (True, None))
check('A: read in ComicRack -> completed in Komga', komga.state(A), (20, True))
check('A: ComicRack unchanged', cr_state(A), (19, True))
check('B: Komga page 10 pulled into ComicRack', cr_state(B), (9, False))
check('C: both unread, nothing sent', [c for c in komga.calls if c[0] != 'list' and
                                       c[1] == komga.id_of(C)], [])
check('counts', (r.pushed, r.pulled, r.failed, r.not_in_komga), (1, 1, 0, 1))
check('snapshot saved', File.Exists(paths.state_path()), True)
status = S.Settings.load()
check('status saved', (status.last_sync_status, bool(status.last_sync_time)),
      ('1 pulled, 1 pushed, 1 book not in Komga', True))

print('--- second run: nothing to do, no question')
del questions[:]
calls_before = len(komga.calls)
started, r = run()
check('no question', questions, [])
check('nothing pushed or pulled', (r.pushed, r.pulled), (0, 0))
check('only the book list was requested', komga.calls[calls_before:], [('list',)])

print('--- changes on each side')
apply_state(by_path[B], 0, True)           # finished B in ComicRack
komga.set_state(A, None, False)            # marked A unread in Komga
apply_state(by_path[C], 7, False)          # read some of C in ComicRack
started, r = run()
check('B finished in ComicRack -> completed in Komga', komga.state(B), (20, True))
check('A marked unread in Komga -> unread in ComicRack', cr_state(A), (0, False))
check('C page 8 in ComicRack -> Komga page 8', komga.state(C), (8, False))
check('counts', (r.pushed, r.pulled), (2, 1))

print('--- Komga down: nothing changes, status says why')
komga.fail_list = KomgaError('unreachable', 'Can\'t connect to Komga at http://x. Is Komga running?')
snap_before = File.ReadAllText(paths.state_path())
started, r = run()
check('failed with the reason', (r.ok, r.error.startswith('Can\'t connect')), (False, True))
check('snapshot untouched', File.ReadAllText(paths.state_path()) == snap_before, True)
check('status shows the failure', S.Settings.load().last_sync_status.startswith('failed:'), True)
komga.fail_list = None

print('--- one book fails to push, the rest still sync')
apply_state(by_path[C], 12, False)
apply_state(by_path[A], 0, True)
komga.fail_ids.add(komga.id_of(C))
started, r = run()
check('A pushed, C failed', (komga.state(A), r.pushed, r.failed), ((20, True), 1, 1))
komga.fail_ids.clear()
started, r = run()
check('C retried next time', komga.state(C), (13, False))

print('--- only one run at a time')
first = runner.run_once()
second = runner.run_once()
check('second start refused while running', (first, second), (True, False))
pump(20, lambda: not runner.running)

print('--- Redo first sync with "Komga" as the source')
import snapshot
snapshot.reset()
st = S.Settings.load()
st.first_sync_source = S.FIRST_SYNC_KOMGA
st.save()
komga.set_state(A, None, False)            # Komga unread, ComicRack read
del questions[:]
started, r = run()
check('asked again (first sync), Komga as source', questions[0][0], S.FIRST_SYNC_KOMGA)
check('A: ComicRack made unread to match Komga', cr_state(A), (0, False))

finish()
