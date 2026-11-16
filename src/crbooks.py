''' ===========================================================================

Reading and writing a ComicRack book's read state.

Read as (index, completed):
  index      CurrentPage, the 0-based page the reader is on
  completed  HasBeenRead (ComicRack's own rule: 95% of the pages read)
Written with ComicRack's own MarkAsRead() / MarkAsNotRead() for read and
unread, the same as the menu commands; a part-read position sets
CurrentPage and LastPageRead.

Must run on ComicRack's main thread: ComicBook isn't thread-safe.

=========================================================================== '''
import clr
from bookkey import path_key

clr.AddReference('System')
from System import DateTime


# ===========================================================================
class CrState(object):
    '''A ComicRack book's state at one moment.'''
    __slots__ = ('book', 'key', 'path', 'pages', 'index', 'completed', 'opened_utc')

    def __repr__(self):
        return 'CrState(pages=%d, index=%d, completed=%r)' % (
            self.pages, self.index, self.completed)


def read_state(book):
    '''The book's state, or None for a book with no file (nothing to match).'''
    path = book.FilePath
    if not path:
        return None
    s = CrState()
    s.book = book
    s.path = path
    s.key = path_key(path)
    s.pages = max(0, int(book.PageCount))
    s.completed = bool(book.HasBeenRead)
    if s.completed:
        s.index = max(0, s.pages - 1)
    else:
        # clamp: a book marked read with 1 page sits on "page 1" (index 1)
        s.index = max(0, int(book.CurrentPage))
        if s.pages > 0:
            s.index = min(s.index, s.pages - 1)
    opened = book.OpenedTime
    s.opened_utc = None if opened == DateTime.MinValue else opened.ToUniversalTime()
    return s


def apply_state(book, index, completed):
    '''Sets the book to (index, completed); (0, False) means unread.'''
    if completed:
        book.MarkAsRead()
    elif index <= 0:
        book.MarkAsNotRead()
    else:
        pages = int(book.PageCount)
        if pages > 0:
            index = min(index, pages - 1)
        book.CurrentPage = index
        book.LastPageRead = index
        if book.OpenedTime == DateTime.MinValue:
            # part read but "never opened" would look odd in ComicRack
            book.OpenedTime = DateTime.Now
            if book.OpenedCount == 0:
                book.OpenedCount = 1


def same_state(a_index, a_completed, b_index, b_completed):
    '''True if two (index, completed) states mean the same thing.'''
    if a_completed or b_completed:
        return bool(a_completed) == bool(b_completed)
    return a_index == b_index
