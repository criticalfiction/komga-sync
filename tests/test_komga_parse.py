''' Parsing Komga book records and dates (offline). '''
from testlib import check, finish, temp_data_dir, ROOT
import clr
clr.AddReference('System')
from System import DateTimeKind
from System.IO import File, Path
from System.Text import Encoding

import jsonutil
from bookkey import path_key
from komgaclient import KomgaBook, parse_utc

temp_data_dir()

print('--- path keys')
check('case and slashes', path_key('X:/Comics/Foo/BAR.cbz'), u'x:\\comics\\foo\\bar.cbz')
check('composed == decomposed accent',
      path_key(u'X:\\Garc\u00eda.cbz') == path_key(u'X:\\Garci\u0301a.cbz'), True)
check('empty', path_key(None), '')

print('--- dates')
d = parse_utc('2026-11-16T01:49:46Z')
check('Z -> UTC', (d.Year, d.Hour, d.Kind == DateTimeKind.Utc), (2026, 1, True))
d = parse_utc('2026-11-16T01:49:46.123456Z')
check('fractional seconds', (d.Second, d.Millisecond), (46, 123))
d = parse_utc('2026-11-16T03:49:46+02:00')
check('offset converted to UTC', d.Hour, 1)
check('missing -> None', parse_utc(None), None)
check('garbage -> None', parse_utc('yesterday-ish'), None)

print('--- saved list page (docs/samples)')
sample = Path.Combine(ROOT, 'docs', 'samples', 'books_page_get.json')
if File.Exists(sample):
    page = jsonutil.loads(File.ReadAllText(sample, Encoding.UTF8))
    books = [KomgaBook.from_json(b) for b in page['content']]
    check('every record parsed', all(b is not None for b in books), True)
    check('pages read', all(b.pages > 0 for b in books), True)
    check('paths start with a drive', all(b.path[1:3] == ':\\' for b in books), True)
else:
    print('     (skipped: no sample; run tools/inspect_komga.py)')

print('--- records with and without progress')
unread = KomgaBook.from_json({'id': 'a', 'url': 'X:\\a.cbz', 'media': {'pagesCount': 20},
                              'readProgress': None, 'deleted': False})
check('unread', (unread.page, unread.completed, unread.progress_modified), (None, False, None))
reading = KomgaBook.from_json({'id': 'b', 'url': 'X:\\b.cbz', 'media': {'pagesCount': 20},
                               'readProgress': {'page': 7, 'completed': False,
                                                'readDate': '2026-11-15T10:00:00Z',
                                                'lastModified': '2026-11-15T10:00:05Z'}})
check('page 7 of 20', (reading.page, reading.completed), (7, False))
check('progress time from lastModified', reading.progress_modified.Second, 5)
done = KomgaBook.from_json({'id': 'c', 'url': 'X:\\c.cbz', 'media': {'pagesCount': 20},
                            'readProgress': {'page': 20, 'completed': True,
                                             'lastModified': '2026-11-15T10:00:05Z'}})
check('completed', (done.page, done.completed), (20, True))
gone = KomgaBook.from_json({'id': 'd', 'url': 'X:\\d.cbz', 'media': {}, 'deleted': True})
check('deleted flagged', gone.deleted, True)
check('record without id ignored', KomgaBook.from_json({'url': 'x'}), None)

finish()
