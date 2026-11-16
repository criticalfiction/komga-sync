'''
The ComicRack adapter against ComicRack CE's REAL ComicBook class (loaded
from the installed ComicRack.Engine.dll), so read-only properties and the
95% read rule behave exactly as in ComicRack. Books are created in memory
only; nothing touches the library.
'''
from testlib import check, finish, temp_data_dir
import clr
clr.AddReference('System')
from System import DateTime

clr.AddReferenceToFileAndPath(
    r'C:\Program Files\ComicRack Community Edition\ComicRack.Engine.dll')
from cYo.Projects.ComicRack.Engine import ComicBook

from bookkey import path_key
from crbooks import read_state, apply_state, same_state

temp_data_dir()


def new_book(pages=20, path=u'X:\\Comics\\\xa1Garc\xeda!\\Test.cbz'):
    b = ComicBook()
    b.FilePath = path
    b.PageCount = pages
    return b


def show(b):
    return (b.CurrentPage, b.LastPageRead, b.HasBeenRead)


print('--- reading')
b = new_book()
s = read_state(b)
check('new book is unread', (s.index, s.completed), (0, False))
check('never opened -> no time', s.opened_utc, None)
check('path key', s.key, path_key(u'X:\\Comics\\\xa1Garc\xeda!\\Test.cbz'))
check('book without a file is skipped', read_state(new_book(path='')), None)

print('--- writing: unread -> page 5 -> completed -> unread')
apply_state(b, 5, False)
check('page 5: Current/LastPageRead/HasBeenRead', show(b), (5, 5, False))
check('part read now looks opened', b.OpenedTime != DateTime.MinValue, True)
s = read_state(b)
check('reads back as page 5', (s.index, s.completed), (5, False))
check('opened time is UTC', s.opened_utc is not None, True)

apply_state(b, 0, True)
check('completed via MarkAsRead', show(b), (19, 19, True))
check('reads back as completed', (read_state(b).index, read_state(b).completed), (19, True))

apply_state(b, 0, False)
check('unread via MarkAsNotRead', show(b), (0, 0, False))
check('MarkAsNotRead clears opened time', b.OpenedTime, DateTime.MinValue)

print('--- ComicRack\'s 95% rule')
apply_state(b, 18, False)            # page 19 of 20 = 95%
check('page 19/20 counts as read in ComicRack', read_state(b).completed, True)
apply_state(b, 17, False)            # page 18 of 20 = 90%
check('page 18/20 does not', read_state(b).completed, False)

print('--- a completed book read back further back is still completed')
apply_state(b, 0, True)
b.CurrentPage = 3                     # reader flipped back to page 4
s = read_state(b)
check('completed wins over the current page', (s.index, s.completed), (19, True))

print('--- 1-page book')
one = new_book(pages=1)
apply_state(one, 0, True)
s = read_state(one)
check('1-page book marked read', (s.index, s.completed), (0, True))

print('--- same_state')
check('two completed states with different pages', same_state(3, True, 19, True), True)
check('different pages', same_state(3, False, 4, False), False)
check('completed vs part read', same_state(19, True, 19, False), False)

finish()
