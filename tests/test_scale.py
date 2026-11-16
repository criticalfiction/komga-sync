'''
A library the user's size: 4,300 ComicRack books (half read), 4,229 of them
in Komga (all unread, as just after installing Komga). Checks the first
sync's numbers and how long each step takes, including how long ComicRack's
thread is busy.
'''
from testlib import check, finish, temp_data_dir, pump
import clr
clr.AddReference('System')
from System.Diagnostics import Stopwatch

import settings as S
from syncrunner import SyncRunner
from fakes import make_book, FakeComicRack, FakeKomga

temp_data_dir()
st = S.Settings()
st.api_key = 'x'
st.save()

N_CR, N_KOMGA = 4300, 4229
paths = [u'X:\\Comics\\Series %03d\\Issue %04d.cbz' % (i // 20, i) for i in range(N_CR)]
books = [make_book(p, pages=24, completed=(i % 2 == 0)) for i, p in enumerate(paths)]
cr = FakeComicRack(books)
komga = FakeKomga(dict((p, (24, None, False)) for p in paths[:N_KOMGA]))
asked = []
runner = SyncRunner(cr, cr.MainWindow, make_client=lambda s: komga,
                    ask=lambda *a: asked.append(a[2:]) or True)


def timed_run():
    done = []
    watch = Stopwatch.StartNew()
    runner.run_once(on_done=done.append)
    started_ms = watch.ElapsedMilliseconds          # ComicRack's thread was busy this long
    pump(120, lambda: bool(done))
    return done[0], started_ms, watch.ElapsedMilliseconds


r, busy_ms, total_ms = timed_run()
print('     first sync: %d ms total, ComicRack busy %d ms reading books' % (total_ms, busy_ms))
read = len([i for i in range(N_KOMGA) if i % 2 == 0])
check('asked: %d to Komga, 0 to ComicRack, 71 not in Komga' % read, asked[0], (read, 0, N_CR - N_KOMGA))
check('pushed every read book, pulled none', (r.pushed, r.pulled, r.failed), (read, 0, 0))
check('ComicRack untouched', all(b.HasBeenRead == (i % 2 == 0) for i, b in enumerate(books)), True)
check('reading ComicRack\'s books took under 2 s', busy_ms < 2000, True)

r, busy_ms, total_ms = timed_run()
print('     second sync: %d ms total' % total_ms)
check('second sync: nothing to do', (r.pushed, r.pulled), (0, 0))
check('second sync under 10 s (plus Komga\'s ~2 s list)', total_ms < 10000, True)

finish()
