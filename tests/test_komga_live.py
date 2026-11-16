'''
Against the real Komga: list every book, then change the TEST BOOK's progress
step by step and put it back exactly as it was (in a finally block, so it's
restored even if a check or request fails).
'''
from testlib import check, finish, temp_data_dir, test_config
import clr
clr.AddReference('System')
from System.Diagnostics import Stopwatch

import jsonutil
from bookkey import path_key
from komgaclient import KomgaClient

temp_data_dir()
cfg = test_config()
client = KomgaClient(cfg['url'], cfg['api_key'])

print('--- list every book')
watch = Stopwatch.StartNew()
pages_seen = []
books = client.list_books(on_page=lambda done, total: pages_seen.append((done, total)))
watch.Stop()
print('     %d books in %d requests, %.1f s' % (len(books), len(pages_seen),
                                                 watch.ElapsedMilliseconds / 1000.0))
check('more than 4,000 books', len(books) > 4000, True)
check('ids unique', len(set(b.id for b in books)), len(books))
check('paths unique', len(set(b.key for b in books)), len(books))

key = path_key(cfg['test_books'][0])
matches = [b for b in books if b.key == key]
check('test book found by path', len(matches), 1)
if not matches:
    finish()
    raise SystemExit
book = matches[0]
print('     %r' % book)


def raw_progress():
    return client.request('GET', '/api/v1/books/%s' % book.id).get('readProgress')


original = raw_progress()
print('     original readProgress: %s' % jsonutil.dumps(original))

try:
    print('--- page 3')
    client.set_progress(book.id, page=3)
    b = client.get_book(book.id)
    check('page 3, not completed', (b.page, b.completed), (3, False))
    check('progress time set', b.progress_modified is not None, True)
    print('     readProgress shape: %s' % ', '.join(sorted(raw_progress().keys())))
    first_time = b.progress_modified

    print('--- completed')
    client.set_progress(book.id, completed=True)
    b = client.get_book(book.id)
    check('completed', b.completed, True)
    check('page after completed', b.page, book.pages)
    check('progress time moved on', b.progress_modified >= first_time, True)

    print('--- last page by number (does Komga mark it completed?)')
    client.clear_progress(book.id)
    client.set_progress(book.id, page=book.pages)
    b = client.get_book(book.id)
    print('     page=%r completed=%r' % (b.page, b.completed))
    check('last page reached is recorded', b.page, book.pages)

    print('--- unread')
    client.clear_progress(book.id)
    b = client.get_book(book.id)
    check('unread again', (b.page, b.completed, b.progress_modified), (None, False, None))
finally:
    print('--- restore original')
    if original is None:
        client.clear_progress(book.id)
    else:
        client.set_progress(book.id, page=original.get('page'),
                            completed=original.get('completed'))
    restored = raw_progress()
    same = (restored is None) == (original is None) and (
        original is None or (restored.get('page'), restored.get('completed')) ==
        (original.get('page'), original.get('completed')))
    check('test book back to its original progress', same, True)

finish()
