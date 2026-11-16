'''
Full sync runs against the REAL Komga, limited to the test book (only_keys),
with an in-memory ComicRack copy of it (your real ComicRack library isn't
touched). The test book's Komga progress is restored at the end, even if a
step fails.

Starts like the real book: read in ComicRack, unread in Komga.
'''
from testlib import check, finish, temp_data_dir, test_config, pump
import jsonutil
import settings as S
from bookkey import path_key
from crbooks import read_state, apply_state
from komgaclient import KomgaClient
from syncrunner import SyncRunner
from fakes import make_book, FakeComicRack

temp_data_dir()
cfg = test_config()
path = cfg['test_books'][0]
key = path_key(path)

s = S.Settings()
s.url, s.api_key = cfg['url'], cfg['api_key']
s.save()
client = KomgaClient(s.url, s.api_key)
kb = [b for b in client.list_books() if b.key == key][0]
original = client.request('GET', '/api/v1/books/%s' % kb.id).get('readProgress')
print('     Komga original progress: %s' % jsonutil.dumps(original))

book = make_book(path, pages=kb.pages, completed=True)
cr = FakeComicRack([book])
asked = []
runner = SyncRunner(cr, cr.MainWindow, ask=lambda *a: asked.append(a[1:]) or True,
                    only_keys=[key])


def run():
    done = []
    runner.run_once(on_done=done.append)
    pump(60, lambda: bool(done))
    return done[0] if done else None


def komga_state():
    b = client.get_book(kb.id)
    return (b.page, b.completed)


try:
    if original is not None:
        client.clear_progress(kb.id)      # start from "unread in Komga"

    print('--- first sync, default "Keep the most read"')
    r = run()
    check('ran ok', (r.ok, r.error), (True, None))
    check('asked first: 1 push, 0 pull', asked[0][1:3], (1, 0))
    check('Komga: test book now read', komga_state(), (kb.pages, True))
    st = read_state(book)
    check('ComicRack: unchanged (still read)', (st.index, st.completed), (kb.pages - 1, True))

    print('--- read to page 4 in Komga -> ComicRack follows')
    client.set_progress(kb.id, page=4)
    r = run()
    st = read_state(book)
    check('ComicRack now on page 4 (index 3), not read', (st.index, st.completed), (3, False))
    check('counts', (r.pulled, r.pushed), (1, 0))

    print('--- marked read in ComicRack -> Komga follows')
    apply_state(book, 0, True)
    r = run()
    check('Komga: read again', komga_state(), (kb.pages, True))
    check('counts', (r.pulled, r.pushed), (0, 1))

    print('--- nothing changed -> nothing sent')
    r = run()
    check('counts', (r.pulled, r.pushed, r.failed), (0, 0, 0))
finally:
    print('--- restore Komga')
    if original is None:
        client.clear_progress(kb.id)
    else:
        client.set_progress(kb.id, page=original.get('page'),
                            completed=original.get('completed'))
    restored = client.request('GET', '/api/v1/books/%s' % kb.id).get('readProgress')
    check('test book back to its original Komga progress',
          (restored is None) == (original is None), True)

finish()
