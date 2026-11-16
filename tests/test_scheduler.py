''' When syncs run: start-up, interval, window activated, shutdown. '''
from testlib import check, finish, temp_data_dir, pump
import clr
clr.AddReference('System')
from System import DateTime, DateTimeKind, TimeSpan
from System.Diagnostics import Stopwatch
from System.Threading import Thread

import settings as S
import scheduler as sched_mod
from scheduler import Scheduler
from syncrunner import SyncRunner
from crbooks import read_state, apply_state
from komgaclient import KomgaError
from fakes import make_book, FakeComicRack, FakeKomga

temp_data_dir()


class Clock(object):
    def __init__(self):
        self.t = DateTime(2026, 11, 16, 12, 0, 0, DateTimeKind.Utc)

    def __call__(self):
        return self.t

    def advance(self, minutes=0, seconds=0):
        self.t = self.t.AddMinutes(minutes).AddSeconds(seconds)


class StubRunner(object):
    def __init__(self):
        self.calls = []
        self.running = False

    def run_once(self, **kw):
        if self.running:
            return False
        self.calls.append(kw)
        return True

    def wait(self, ms):
        return True


def settings(configured=True, enabled=True, interval=5):
    s = S.Settings()
    s.api_key = 'x' if configured else ''
    s.enabled = enabled
    s.interval_minutes = interval
    return lambda: s


print('--- start-up')
r = StubRunner()
Scheduler(r, load=settings(configured=False)).start()
check('not configured: no sync at start-up', len(r.calls), 0)
r = StubRunner()
Scheduler(r, load=settings(enabled=False)).start()
check('switched off: no sync at start-up', len(r.calls), 0)
r = StubRunner()
clock = Clock()
cfg = settings(interval=5)
sc = Scheduler(r, now=clock, load=cfg)
sc.start()
check('configured: one sync at start-up', len(r.calls), 1)
check('timer running', sc.timer is not None and sc.timer.Enabled, True)

print('--- interval')
clock.advance(minutes=4)
check('4 min later: not yet', sc.tick(), False)
clock.advance(minutes=1)
check('5 min later: sync', sc.tick(), True)
cfg().interval_minutes = 1                 # changed in the settings dialog
clock.advance(minutes=1)
check('interval cut to 1 min: applies without restart', sc.tick(), True)
r.running = True
clock.advance(minutes=10)
check('a sync still running: tick skipped', sc.tick(), False)
r.running = False
cfg().enabled = False
check('switched off: tick does nothing', sc.tick(), False)
cfg().enabled = True

print('--- window activated')
sc.tick()                                  # a sync starts now
clock.advance(seconds=30)
check('30 s after a sync: no', sc.activated(), False)
clock.advance(seconds=31)
check('61 s after: sync', sc.activated(), True)
sc.stop()

print('--- the real WinForms timer fires')
r = StubRunner()
sc = Scheduler(r, now=Clock(), load=settings(configured=False))
sc.start()
sc.timer.Interval = 200
cfg2 = S.Settings()
cfg2.api_key = 'x'
sc.load = lambda: cfg2                     # becomes configured after start-up
pump(2, lambda: len(r.calls) > 0)
check('timer tick started a sync once configured', len(r.calls), 1)
sc.stop()

print('--- shutdown with a real runner')
st = S.Settings()
st.api_key = 'x'
st.save()
P, Q = u'X:\\Comics\\P.cbz', u'X:\\Comics\\Q.cbz'
bp, bq = make_book(P), make_book(Q)
cr = FakeComicRack([bp, bq])
komga = FakeKomga({P: (20, None, False), Q: (20, None, False)})
runner = SyncRunner(cr, cr.MainWindow, make_client=lambda s: komga, ask=lambda *a: True)
sc = Scheduler(runner, cr.MainWindow)


def full_sync():
    done = []
    runner.run_once(on_done=done.append)
    pump(20, lambda: bool(done))


print('     (first sync pending)')
apply_state(bp, 5, False)
sc.shutdown()
check('first sync pending: shutdown sends nothing', [c for c in komga.calls if c[0] != 'list'], [])
full_sync()                                # first sync confirmed (ask -> True)
check('first full sync pushed P', komga.state(P), (6, False))

apply_state(bp, 9, False)                  # read further in ComicRack
komga.set_state(Q, 7, False)               # read Q on the phone
sc.shutdown()
check('shutdown pushed ComicRack\'s change', komga.state(P), (10, False))
q = read_state(bq)
check('shutdown left ComicRack alone', (q.index, q.completed), (0, False))
full_sync()
q = read_state(bq)
check('next start pulls the phone\'s page', (q.index, q.completed), (6, False))

print('--- shutdown can\'t hang on a stuck Komga')


class SlowKomga(FakeKomga):
    def list_books(self, page_size=500, on_page=None):
        Thread.Sleep(20000)                # background thread: fine
        return FakeKomga.list_books(self)
slow = SlowKomga({P: (20, None, False)})
runner2 = SyncRunner(cr, cr.MainWindow, make_client=lambda s: slow)
sc2 = Scheduler(runner2, cr.MainWindow)
watch = Stopwatch.StartNew()
sc2.shutdown()
watch.Stop()
seconds = watch.ElapsedMilliseconds / 1000.0
check('shutdown returned within its limit (%.1f s)' % seconds,
      seconds < sched_mod.SHUTDOWN_WAIT_MS / 1000.0 + 2, True)

print('--- the Shutdown hook always lets ComicRack close')
import KomgaSync
KomgaSync.ComicRack = cr


class Broken(object):
    def shutdown(self):
        raise Exception('boom')
KomgaSync._scheduler = None
check('no scheduler -> True', KomgaSync.komga_sync_shutdown(True), True)
KomgaSync._scheduler = Broken()
check('scheduler raises -> still True', KomgaSync.komga_sync_shutdown(True), True)

finish()
