''' ===========================================================================

Komga Sync settings, stored as JSON in settings.dat (see paths.py).

The API key is encrypted with Windows DPAPI for the current Windows user
(System.Security.Cryptography.ProtectedData), so it isn't readable in the
file and only this Windows account can decrypt it. It is never logged.

=========================================================================== '''
import clr
import log
import paths
import jsonutil

clr.AddReference('System')
clr.AddReference('System.Security')
from System import Convert
from System.IO import File
from System.Text import Encoding
from System.Security.Cryptography import ProtectedData, DataProtectionScope

# First sync source: what to do with a book that has never been synced
FIRST_SYNC_MOST_READ = 'most_read'    # take the side with more progress
FIRST_SYNC_COMICRACK = 'comicrack'    # copy ComicRack's state to Komga
FIRST_SYNC_KOMGA = 'komga'            # copy Komga's state to ComicRack
FIRST_SYNC_SOURCES = [
    (FIRST_SYNC_MOST_READ, 'Keep the most read (never makes a book less read)'),
    (FIRST_SYNC_COMICRACK, 'ComicRack (copy ComicRack to Komga, including unread)'),
    (FIRST_SYNC_KOMGA, 'Komga (copy Komga to ComicRack, including unread)'),
]

DEFAULT_URL = 'http://localhost:25600'
DEFAULT_INTERVAL = 5            # minutes
MIN_INTERVAL, MAX_INTERVAL = 1, 24 * 60

# extra entropy for DPAPI, so other programs using plain DPAPI calls can't
# read the value by accident
_ENTROPY = Encoding.UTF8.GetBytes('KomgaSync.ApiKey.v1')


def protect(text):
    '''Encrypts text for the current Windows user; returns base64.'''
    if not text:
        return ''
    data = ProtectedData.Protect(Encoding.UTF8.GetBytes(text), _ENTROPY,
                                 DataProtectionScope.CurrentUser)
    return Convert.ToBase64String(data)


def unprotect(blob):
    '''Reverses protect(); '' if blob is empty or can't be decrypted.'''
    if not blob:
        return ''
    try:
        data = ProtectedData.Unprotect(Convert.FromBase64String(blob), _ENTROPY,
                                       DataProtectionScope.CurrentUser)
        return Encoding.UTF8.GetString(data)
    except Exception:
        log.debug('saved API key could not be decrypted (other Windows user?)')
        return ''


# ===========================================================================
class Settings(object):
    '''All Komga Sync settings. load() / save() use settings.dat.'''

    def __init__(self):
        self.url = DEFAULT_URL
        self.api_key = ''
        self.interval_minutes = DEFAULT_INTERVAL
        self.enabled = True
        self.first_sync_source = FIRST_SYNC_MOST_READ
        # written by the sync runner, shown in the settings dialog
        self.last_sync_time = ''      # local time text, '' if never
        self.last_sync_status = ''    # e.g. "3 pulled, 1 pushed" / "failed: ..."

    def is_configured(self):
        '''True once a URL and API key have been entered.'''
        return bool(self.url and self.api_key)

    # -------------------------------------------------------------------
    @classmethod
    def load(cls):
        '''Settings from settings.dat; defaults for anything missing/bad.'''
        s = cls()
        path = paths.settings_path()
        if not File.Exists(path):
            return s
        try:
            data = jsonutil.loads(File.ReadAllText(path, Encoding.UTF8)) or {}
        except Exception:
            log.debug_exc('settings.dat unreadable, using defaults')
            return s
        s.url = normalize_url(data.get('url') or DEFAULT_URL)
        s.api_key = unprotect(data.get('api_key_protected'))
        s.interval_minutes = clamp_interval(data.get('interval_minutes'))
        s.enabled = bool(data.get('enabled', True))
        source = data.get('first_sync_source')
        if source in [k for k, _ in FIRST_SYNC_SOURCES]:
            s.first_sync_source = source
        s.last_sync_time = data.get('last_sync_time') or ''
        s.last_sync_status = data.get('last_sync_status') or ''
        return s

    def save(self):
        data = {
            'url': normalize_url(self.url),
            'api_key_protected': protect(self.api_key),
            'interval_minutes': clamp_interval(self.interval_minutes),
            'enabled': bool(self.enabled),
            'first_sync_source': self.first_sync_source,
            'last_sync_time': self.last_sync_time,
            'last_sync_status': self.last_sync_status,
        }
        path = paths.settings_path()
        tmp = path + '.tmp'
        write_atomic(path, jsonutil.dumps(data))


def write_atomic(path, text):
    '''Writes text to path via a temp file, so a crash can't leave half a file.'''
    tmp = path + '.tmp'
    File.WriteAllText(tmp, text, Encoding.UTF8)
    if File.Exists(path):
        File.Replace(tmp, path, None)
    else:
        File.Move(tmp, path)


def normalize_url(url):
    '''"localhost:25600/" -> "http://localhost:25600".'''
    url = (url or '').strip().rstrip('/')
    if url and '://' not in url:
        url = 'http://' + url
    return url


def clamp_interval(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL
    return max(MIN_INTERVAL, min(MAX_INTERVAL, value))
