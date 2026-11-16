'''
The sync decision table, case by case, plus the snapshot file. Books are
20 pages on both sides unless a case says otherwise.
'''
from testlib import check, finish, temp_data_dir
import clr
clr.AddReference('System')
from System import DateTime, DateTimeKind
from System.IO import File
from System.Text import Encoding

import paths
import pagemap
from syncengine import decide, make_entry, komga_after_push, PUSH, PULL, NONE
from settings import FIRST_SYNC_COMICRACK as CR_SRC, FIRST_SYNC_KOMGA as K_SRC, \
    FIRST_SYNC_MOST_READ as MOST
from snapshot import Snapshot

temp_data_dir()


def utc(h, m=0):
    return DateTime(2026, 11, 16, h, m, 0, DateTimeKind.Utc)


NOW = utc(12)
SYNCED = utc(10)      # last sync of the book


class Cr(object):
    def __init__(self, index=0, completed=False, pages=20, opened=None):
        self.index, self.completed, self.pages, self.opened_utc = index, completed, pages, opened


class Kb(object):
    def __init__(self, page=None, completed=False, pages=20, modified=None):
        self.page, self.completed, self.pages, self.progress_modified = \
            page, completed, pages, modified


def entry(ci=0, cc=False, kp=None, kc=False):
    return make_entry(ci, cc, kp, kc, SYNCED)


def case(label, cr, kb, ent, source, want_action, want_target=None):
    d = decide(cr, kb, ent, NOW, source)
    got = (d.action, d.komga if d.action == PUSH else d.cr if d.action == PULL else None)
    want = (want_action, want_target)
    check('%-52s [%s]' % (label, d.reason), got, want)


print('--- already in sync')
case('both unread, never synced', Cr(), Kb(), None, MOST, NONE)
case('both completed (different pages counted)', Cr(19, True), Kb(20, True), None, MOST, NONE)
case('same page', Cr(5), Kb(6), entry(5, False, 6, False), MOST, NONE)

print('--- first sync: Keep the most read (the default)')
case('ComicRack read, Komga unread  -> push completed', Cr(19, True), Kb(), None, MOST,
     PUSH, pagemap.COMPLETED)
case('ComicRack page 10, Komga page 3 -> push page 11', Cr(10), Kb(3, modified=NOW), None,
     MOST, PUSH, 11)
case('ComicRack page 3, Komga page 10 -> pull index 9', Cr(3), Kb(10, modified=NOW), None,
     MOST, PULL, (9, False))
case('ComicRack unread, Komga completed -> pull completed', Cr(), Kb(20, True, modified=NOW),
     None, MOST, PULL, (19, True))
case('ComicRack completed, Komga page 5 -> push (never less read)', Cr(19, True),
     Kb(5, modified=NOW), None, MOST, PUSH, pagemap.COMPLETED)

print('--- first sync: ComicRack is the source')
case('Komga unread, ComicRack completed -> push completed', Cr(19, True), Kb(), None, CR_SRC,
     PUSH, pagemap.COMPLETED)
case('ComicRack unread, Komga completed -> push unread', Cr(), Kb(20, True, modified=NOW),
     None, CR_SRC, PUSH, pagemap.UNREAD)

print('--- first sync: Komga is the source')
case('Komga unread, ComicRack completed -> pull unread', Cr(19, True), Kb(), None, K_SRC,
     PULL, (0, False))
case('Komga page 7, ComicRack page 2 -> pull index 6', Cr(2), Kb(7, modified=NOW), None,
     K_SRC, PULL, (6, False))

print('--- synced before: one side changed')
case('read further in ComicRack -> push', Cr(8), Kb(3, modified=SYNCED), entry(2, False, 3, False),
     MOST, PUSH, 9)
case('read further in Komga -> pull', Cr(2), Kb(9, modified=utc(11)), entry(2, False, 3, False),
     MOST, PULL, (8, False))
case('finished in ComicRack -> push completed', Cr(19, True), Kb(3, modified=SYNCED),
     entry(2, False, 3, False), MOST, PUSH, pagemap.COMPLETED)

print('--- synced before: marking unread carries across')
case('marked unread in ComicRack -> push unread', Cr(), Kb(20, True, modified=SYNCED),
     entry(19, True, 20, True), MOST, PUSH, pagemap.UNREAD)
case('marked unread in Komga -> pull unread', Cr(19, True), Kb(), entry(19, True, 20, True),
     MOST, PULL, (0, False))

print('--- synced before: both changed, newest wins')
case('ComicRack opened 11:30, Komga changed 11:00 -> push', Cr(8, opened=utc(11, 30)),
     Kb(5, modified=utc(11)), entry(2, False, 3, False), MOST, PUSH, 9)
case('ComicRack opened 10:30, Komga changed 11:00 -> pull', Cr(8, opened=utc(10, 30)),
     Kb(5, modified=utc(11)), entry(2, False, 3, False), MOST, PULL, (4, False))
case('opened before last sync (was open across it) -> counts as now', Cr(8, opened=utc(9)),
     Kb(5, modified=utc(11)), entry(2, False, 3, False), MOST, PUSH, 9)
case('marked unread in Komga (no time) vs ComicRack 11:00 -> pull', Cr(8, opened=utc(11)),
     Kb(), entry(2, False, 3, False), MOST, PULL, (0, False))
case('same time -> ComicRack wins', Cr(8, opened=utc(11)), Kb(5, modified=utc(11)),
     entry(2, False, 3, False), MOST, PUSH, 9)

print('--- synced before: neither changed but they differ')
case('95% rule: ComicRack read, Komga page 19 -> left alone', Cr(19, True),
     Kb(19, modified=SYNCED), entry(19, True, 19, False), MOST, NONE)

print('--- different page counts (ComicRack 100, Komga 50)')
case('ComicRack halfway, Komga unread -> push halfway', Cr(50, pages=100), Kb(pages=50), None,
     MOST, PUSH, 26)
case('Komga halfway, ComicRack unread -> pull halfway', Cr(pages=100), Kb(25, pages=50,
     modified=NOW), None, MOST, PULL, (48, False))

print('--- what Komga holds after a push')
check('completed', komga_after_push(pagemap.COMPLETED, 20), (20, True))
check('unread', komga_after_push(pagemap.UNREAD, 20), (None, False))
check('page 7', komga_after_push(7, 20), (7, False))
check('last page means completed', komga_after_push(20, 20), (20, True))

print('--- snapshot file')
s = Snapshot.load()
check('no file: empty, first full sync', (len(s.entries), s.existed, s.damaged), (0, False, False))
s.entries[u'x:\\comics\\\xa1garc\xeda!\\01.cbz'] = make_entry(19, True, 182, True, utc(10, 30))
s.entries[u'x:\\b.cbz'] = make_entry(4, False, None, False, utc(10, 31))
s.save()
t = Snapshot.load()
check('reloaded: 2 books, not first sync', (len(t.entries), t.existed), (2, True))
e = t.entries[u'x:\\comics\\\xa1garc\xeda!\\01.cbz']
check('entry values', (e['ci'], e['cc'], e['kp'], e['kc']), (19, True, 182, True))
check('time kept to the second, as UTC', (e['t'] == utc(10, 30), e['t'].Kind == DateTimeKind.Utc),
      (True, True))
check('unread Komga page stays None', t.entries[u'x:\\b.cbz']['kp'], None)

File.WriteAllText(paths.state_path(), '{"version": 1, "books": {"x": {"ci": "bad"', Encoding.UTF8)
d = Snapshot.load()
check('damaged file: empty, flagged', (len(d.entries), d.damaged, d.existed), (0, True, False))
check('damaged file kept as state.dat.bad', File.Exists(paths.state_path() + '.bad'), True)

finish()
