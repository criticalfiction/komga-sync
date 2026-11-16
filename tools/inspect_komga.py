'''
Read-only look at a live Komga server (CPython 3, no plugin code involved):
prints the server version, the current user, how the book list is paged,
one book record, and the record for each test book in test_config.json.
Saves raw responses to docs/samples/ for the parsing tests.

    python tools/inspect_komga.py

test_config.json (project root, not committed):
    {"url": "http://localhost:25600", "api_key": "...",
     "test_books": ["D:\\\\Comics\\\\...\\\\Some Book.cbz"]}

Only GET requests are made, except one POST to /api/v1/books/list, which
is Komga's search endpoint and doesn't change anything.
'''
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = json.load(open(os.path.join(ROOT, 'test_config.json'), encoding='utf-8'))
BASE = cfg['url'].rstrip('/')
SAMPLES = os.path.join(ROOT, 'docs', 'samples')
os.makedirs(SAMPLES, exist_ok=True)


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={
        'X-API-Key': cfg['api_key'], 'Accept': 'application/json',
        'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode('utf-8')
            return r.status, (json.loads(text) if text.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:300]


def save(name, obj):
    with open(os.path.join(SAMPLES, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def norm(p):
    return p.replace('/', '\\').lower()


status, info = call('GET', '/api/v1/actuator/info')
print('actuator/info:', status, json.dumps(info)[:200] if status == 200 else info)
status, me = call('GET', '/api/v2/users/me')
print('users/me:', status, me if status != 200 else {k: me.get(k) for k in ('id', 'email', 'roles')})
save('users_me.json', me)

for label, method, path, body in [
        ('GET  /api/v1/books', 'GET', '/api/v1/books?page=0&size=2', None),
        ('POST /api/v1/books/list', 'POST', '/api/v1/books/list?page=0&size=2', {})]:
    status, page = call(method, path, body)
    print('\n%s -> %s' % (label, status))
    if status != 200:
        print('  ', page)
        continue
    print('   paging keys:', sorted(k for k in page if k != 'content'))
    print('   totalElements=%s totalPages=%s size=%s' % (
        page.get('totalElements'), page.get('totalPages'), page.get('size')))
    save('books_page_%s.json' % method.lower(), page)
    if page.get('content'):
        b = page['content'][0]
        print('   book keys:', sorted(b))
        print('   media keys:', sorted(b.get('media', {})))
        print('   readProgress:', b.get('readProgress'))

# find each test book by path (scan all pages, read-only)
wanted = dict((norm(p), p) for p in cfg.get('test_books', []))
found = {}
page_no, total = 0, None
while wanted and (total is None or page_no < total):
    status, page = call('GET', '/api/v1/books?page=%d&size=500' % page_no)
    if status != 200:
        print('book list failed:', status, page)
        break
    total = page['totalPages']
    for b in page['content']:
        if norm(b['url']) in wanted:
            found[norm(b['url'])] = b
    page_no += 1
print('\nscanned %d page(s) of 500' % page_no)
for key, path in wanted.items():
    b = found.get(key)
    print('\nTEST BOOK %s' % path)
    if not b:
        print('   NOT FOUND in Komga (check the path and that the library is scanned)')
        continue
    print('   id=%s url=%s' % (b['id'], b['url']))
    print('   pagesCount=%s mediaStatus=%s' % (b['media'].get('pagesCount'), b['media'].get('status')))
    print('   lastModified=%s' % b.get('lastModified'))
    print('   readProgress=%s' % json.dumps(b.get('readProgress')))
    status, single = call('GET', '/api/v1/books/%s' % b['id'])
    save('book_%s.json' % b['id'], single)
