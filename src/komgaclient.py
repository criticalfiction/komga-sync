''' ===========================================================================

Komga REST client (HttpWebRequest + JSON). Authenticates with an API key in
the X-API-Key header, so no session/cookies are involved.

Errors are raised as KomgaError with a `kind` the caller can act on:
  'auth'         key rejected (HTTP 401/403)
  'unreachable'  can't connect: wrong address, Komga not running, DNS
  'timeout'      no answer in time
  'http'         any other HTTP error status
  'bad_response' the reply wasn't the JSON we expected

Network calls block: never call these on ComicRack's UI thread.

=========================================================================== '''
import clr
import log
import jsonutil
from bookkey import path_key
from settings import normalize_url

clr.AddReference('System')
from System import Uri, DateTime
from System.Globalization import CultureInfo, DateTimeStyles
from System.IO import StreamReader
from System.Net import HttpWebRequest, WebException, WebExceptionStatus, \
    ServicePointManager
from System.Text import Encoding

# a POST/PATCH would otherwise wait up to a second for "100 Continue"
ServicePointManager.Expect100Continue = False

DEFAULT_TIMEOUT_MS = 30000


def parse_utc(text):
    '''Komga's ISO 8601 time ("2026-11-16T01:49:46Z") as a UTC DateTime, or None.'''
    if not text:
        return None
    try:
        return DateTime.Parse(text, CultureInfo.InvariantCulture,
                              DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal)
    except Exception:
        log.debug('unreadable Komga date: %r' % (text,))
        return None


# ===========================================================================
class KomgaBook(object):
    '''
    The parts of a Komga book record the sync needs.
      id, path (the file path), key (bookkey.path_key(path)), pages,
      page        1-based page of the reading progress, None if unread
      completed   True if marked read
      progress_modified  UTC DateTime the progress last changed, None if unread
      deleted     True if Komga no longer finds the file
    '''
    __slots__ = ('id', 'path', 'key', 'pages', 'page', 'completed',
                 'progress_modified', 'deleted')

    @classmethod
    def from_json(cls, raw):
        if not isinstance(raw, dict) or not raw.get('id'):
            return None
        b = cls()
        b.id = raw['id']
        b.path = raw.get('url') or ''
        b.key = path_key(b.path)
        media = raw.get('media') or {}
        b.pages = int(media.get('pagesCount') or 0)
        progress = raw.get('readProgress')
        if isinstance(progress, dict):
            b.page = int(progress.get('page') or 0) or None
            b.completed = bool(progress.get('completed'))
            b.progress_modified = parse_utc(progress.get('lastModified')
                                            or progress.get('readDate'))
        else:
            b.page, b.completed, b.progress_modified = None, False, None
        b.deleted = bool(raw.get('deleted'))
        return b

    def __repr__(self):
        return 'KomgaBook(%s, pages=%d, page=%r, completed=%r)' % (
            self.id, self.pages, self.page, self.completed)


# ===========================================================================
class KomgaError(Exception):
    def __init__(self, kind, message, status=None):
        Exception.__init__(self, message)
        self.kind = kind
        self.status = status
        self.message = message

    def __str__(self):
        return self.message


# ===========================================================================
class KomgaClient(object):

    def __init__(self, url, api_key, timeout_ms=DEFAULT_TIMEOUT_MS):
        self.url = normalize_url(url)
        self.__api_key = api_key or ''
        self.timeout_ms = timeout_ms

    # -------------------------------------------------------------------
    def request(self, method, path, body=None, timeout_ms=None):
        '''
        Sends one request; returns the parsed JSON reply (None for an empty
        reply, e.g. 204). Raises KomgaError.
        '''
        timeout = timeout_ms or self.timeout_ms
        target = self.url + path
        try:
            req = HttpWebRequest.Create(Uri(target))
        except Exception:
            raise KomgaError('unreachable', 'Not a valid Komga address: %s' % self.url)
        req.Method = method
        req.Accept = 'application/json'
        req.Headers.Add('X-API-Key', self.__api_key)
        req.Timeout = timeout
        req.ReadWriteTimeout = timeout
        req.AllowAutoRedirect = False
        try:
            if body is not None:
                data = Encoding.UTF8.GetBytes(jsonutil.dumps(body))
                req.ContentType = 'application/json'
                req.ContentLength = data.Length
                stream = req.GetRequestStream()
                try:
                    stream.Write(data, 0, data.Length)
                finally:
                    stream.Close()
            response = req.GetResponse()
            try:
                text = StreamReader(response.GetResponseStream(), Encoding.UTF8).ReadToEnd()
            finally:
                response.Close()
        except WebException, ex:
            raise self.__error(ex, method, path, timeout)
        try:
            return jsonutil.loads(text)
        except Exception:
            raise KomgaError('bad_response',
                             'Komga sent a reply that isn\'t JSON for %s %s' % (method, path))

    def __error(self, ex, method, path, timeout):
        '''A KomgaError describing a WebException.'''
        status = ex.Status
        if status == WebExceptionStatus.ProtocolError and ex.Response is not None:
            code = int(ex.Response.StatusCode)
            detail = ''
            try:
                text = StreamReader(ex.Response.GetResponseStream(), Encoding.UTF8).ReadToEnd()
                data = jsonutil.loads(text)
                if isinstance(data, dict):
                    detail = data.get('message') or data.get('error') or ''
            except Exception:
                pass
            finally:
                ex.Response.Close()
            log.debug('Komga HTTP %d for %s %s %s' % (code, method, path, detail))
            if code in (401, 403):
                return KomgaError('auth', 'Komga rejected the API key (HTTP %d). '
                                  'Check the key in Komga under your account\'s API keys.'
                                  % code, code)
            if code in (301, 302, 303, 307, 308):
                return KomgaError('http', 'Komga redirected the request (HTTP %d); '
                                  'check the address, e.g. http vs https.' % code, code)
            return KomgaError('http', 'Komga returned HTTP %d%s' %
                              (code, (': ' + detail) if detail else ''), code)
        if status == WebExceptionStatus.Timeout:
            return KomgaError('timeout', 'Komga didn\'t answer within %d seconds.'
                              % (timeout // 1000))
        log.debug('Komga unreachable for %s %s: %s' % (method, path, status))
        if status == WebExceptionStatus.NameResolutionFailure:
            return KomgaError('unreachable', 'Can\'t find the server %s (name not found).'
                              % self.url)
        return KomgaError('unreachable', 'Can\'t connect to Komga at %s (%s). '
                          'Is Komga running?' % (self.url, status))

    # -------------------------------------------------------------------
    def list_books(self, page_size=500, on_page=None):
        '''
        Every book in Komga, as KomgaBook objects. Fetched page_size at a
        time (about 9 requests for 4,200 books). on_page(done, total) is
        called after each page if given. Deleted books are left out.
        '''
        books, page, total = [], 0, None
        while total is None or page < total:
            data = self.request('GET', '/api/v1/books?page=%d&size=%d&sort=id'
                                % (page, page_size))
            if not isinstance(data, dict) or not isinstance(data.get('content'), list):
                raise KomgaError('bad_response', 'Komga\'s book list had an unexpected format.')
            total = int(data.get('totalPages') or 0)
            for raw in data['content']:
                book = KomgaBook.from_json(raw)
                if book is not None and not book.deleted:
                    books.append(book)
            page += 1
            if on_page is not None:
                on_page(page, total)
        return books

    def get_book(self, book_id, timeout_ms=None):
        '''One book by Komga id, as a KomgaBook.'''
        raw = self.request('GET', '/api/v1/books/%s' % book_id, timeout_ms=timeout_ms)
        book = KomgaBook.from_json(raw)
        if book is None:
            raise KomgaError('bad_response', 'Komga returned an unexpected book record.')
        return book

    def set_progress(self, book_id, page=None, completed=None, timeout_ms=None):
        '''
        Records progress: page is Komga's 1-based page number; completed=True
        marks the book read. Pass one or both.
        '''
        body = {}
        if page is not None:
            body['page'] = int(page)
        if completed is not None:
            body['completed'] = bool(completed)
        self.request('PATCH', '/api/v1/books/%s/read-progress' % book_id, body,
                     timeout_ms=timeout_ms)

    def clear_progress(self, book_id, timeout_ms=None):
        '''Marks the book unread (removes its progress).'''
        self.request('DELETE', '/api/v1/books/%s/read-progress' % book_id,
                     timeout_ms=timeout_ms)

    # -------------------------------------------------------------------
    def whoami(self, timeout_ms=None):
        '''The user the API key belongs to: dict with at least 'id', 'email'.'''
        me = self.request('GET', '/api/v2/users/me', timeout_ms=timeout_ms)
        if not isinstance(me, dict) or 'id' not in me:
            raise KomgaError('bad_response', 'Komga didn\'t return a user for the API key.')
        return me
