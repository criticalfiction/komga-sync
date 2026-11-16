''' ===========================================================================

The sync snapshot (state.dat): what each book looked like on both sides at
its last successful sync, keyed by bookkey.path_key(path).

Entry (see syncengine.make_entry):
  ci, cc   ComicRack index (0-based) and completed
  kp, kc   Komga page (1-based or None) and completed
  t        UTC time of that sync (a DateTime in memory, ISO text on disk)

Books not in it are "never synced" and use the First sync source setting.

=========================================================================== '''
import clr
import log
import paths
import jsonutil
from settings import write_atomic

clr.AddReference('System')
from System import DateTime
from System.Globalization import CultureInfo, DateTimeStyles
from System.IO import File
from System.Text import Encoding

VERSION = 1
_ISO = 'yyyy-MM-ddTHH:mm:ss.fffZ'


def _to_text(dt):
    return dt.ToUniversalTime().ToString(_ISO, CultureInfo.InvariantCulture)


def _from_text(text):
    return DateTime.ParseExact(text, _ISO, CultureInfo.InvariantCulture,
                               DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal)


# ===========================================================================
class Snapshot(object):
    '''
    entries  dict: path key -> entry
    existed  True if state.dat was there when loaded. When False, the next
             sync is a "first full sync" (shows a preview and asks first).
    damaged  True if state.dat couldn't be read (it's kept as state.dat.bad)
    '''

    def __init__(self, entries=None, existed=False, damaged=False):
        self.entries = entries if entries is not None else {}
        self.existed = existed
        self.damaged = damaged

    @classmethod
    def load(cls):
        path = paths.state_path()
        if not File.Exists(path):
            return cls()
        try:
            data = jsonutil.loads(File.ReadAllText(path, Encoding.UTF8))
            if not isinstance(data, dict) or not isinstance(data.get('books'), dict):
                raise ValueError('not a snapshot file')
            entries = {}
            for key, e in data['books'].items():
                entries[key] = {'ci': int(e['ci']), 'cc': bool(e['cc']),
                                'kp': int(e['kp']) if e.get('kp') is not None else None,
                                'kc': bool(e['kc']), 't': _from_text(e['t'])}
            return cls(entries, existed=True)
        except Exception:
            log.debug_exc('state.dat is damaged; starting again as if never synced')
            try:
                bad = path + '.bad'
                if File.Exists(bad):
                    File.Delete(bad)
                File.Move(path, bad)
            except Exception:
                log.debug_exc('could not set the damaged state.dat aside')
            return cls(damaged=True)

    def save(self):
        books = {}
        for key, e in self.entries.items():
            books[key] = {'ci': e['ci'], 'cc': e['cc'], 'kp': e['kp'],
                          'kc': e['kc'], 't': _to_text(e['t'])}
        write_atomic(paths.state_path(), jsonutil.dumps({'version': VERSION, 'books': books}))
        self.existed = True


def reset():
    '''
    Forgets every book's sync record ("Redo first sync"): the next sync
    treats every book as never synced. Returns True if there was one.
    '''
    path = paths.state_path()
    if File.Exists(path):
        File.Delete(path)
        log.debug('snapshot cleared (redo first sync)')
        return True
    return False
