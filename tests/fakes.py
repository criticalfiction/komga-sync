''' Test doubles: ComicRack with in-memory books, and an in-memory Komga. '''
import clr
clr.AddReference('System')
clr.AddReference('System.Windows.Forms')
clr.AddReferenceToFileAndPath(
    r'C:\Program Files\ComicRack Community Edition\ComicRack.Engine.dll')
from System import DateTime
from System.Windows.Forms import Form
from cYo.Projects.ComicRack.Engine import ComicBook

from bookkey import path_key
from crbooks import apply_state
from komgaclient import KomgaBook, KomgaError


def make_book(path, pages=20, index=0, completed=False):
    '''A real ComicRack ComicBook (in memory only) in the given state.'''
    b = ComicBook()
    b.FilePath = path
    b.PageCount = pages
    if completed or index:
        apply_state(b, index, completed)
    return b


class FakeApp(object):
    def __init__(self, books):
        self.books = books

    def GetLibraryBooks(self):
        return list(self.books)


class FakeComicRack(object):
    def __init__(self, books):
        self.App = FakeApp(books)
        self.MainWindow = Form()
        self.MainWindow.ShowInTaskbar = False
        self.MainWindow.Opacity = 0
        self.MainWindow.Show()            # window handle needed for Invoke


class FakeKomga(object):
    '''
    Books by path: {path: [pages, page or None, completed]}. Records calls
    in .calls. fail_list / fail_ids make requests fail.
    '''

    def __init__(self, books):
        self.books = {}
        self.ids = {}
        for i, (path, (pages, page, completed)) in enumerate(sorted(books.items())):
            book_id = 'K%03d' % i
            self.books[book_id] = {'path': path, 'pages': pages, 'page': page,
                                   'completed': completed,
                                   'modified': DateTime.UtcNow if page or completed else None}
            self.ids[path_key(path)] = book_id
        self.calls = []
        self.fail_list = None          # a KomgaError to raise from list_books
        self.fail_ids = set()          # ids whose progress calls fail (HTTP 500)

    def id_of(self, path):
        return self.ids[path_key(path)]

    def state(self, path):
        b = self.books[self.id_of(path)]
        return (b['page'], b['completed'])

    def set_state(self, path, page, completed, modified=None):
        b = self.books[self.id_of(path)]
        b['page'], b['completed'] = page, completed
        b['modified'] = modified or (DateTime.UtcNow if (page or completed) else None)

    def list_books(self, page_size=500, on_page=None):
        self.calls.append(('list',))
        if self.fail_list is not None:
            raise self.fail_list
        out = []
        for book_id, b in sorted(self.books.items()):
            out.append(KomgaBook.from_json({
                'id': book_id, 'url': b['path'], 'media': {'pagesCount': b['pages']},
                'readProgress': None if b['page'] is None and not b['completed'] else {
                    'page': b['page'], 'completed': b['completed'],
                    'lastModified': b['modified'].ToString('o') if b['modified'] else None},
                'deleted': False}))
        return out

    def _check(self, book_id):
        if book_id in self.fail_ids:
            raise KomgaError('http', 'Komga returned HTTP 500', 500)

    def set_progress(self, book_id, page=None, completed=None, timeout_ms=None):
        self.calls.append(('set', book_id, page, completed))
        self._check(book_id)
        b = self.books[book_id]
        if completed:
            b['page'], b['completed'] = b['pages'], True
        elif page is not None:
            b['page'], b['completed'] = page, page >= b['pages']
        b['modified'] = DateTime.UtcNow

    def clear_progress(self, book_id, timeout_ms=None):
        self.calls.append(('clear', book_id))
        self._check(book_id)
        b = self.books[book_id]
        b['page'], b['completed'], b['modified'] = None, False, None
