r''' ===========================================================================

Debug log for Komga Sync: %APPDATA%\Komga Sync\sync.log (see paths.py).

Written from both ComicRack's thread and the background sync thread, so
writes are serialised with a lock. Rotated to sync.log.1 past MAX_BYTES so
it can't grow without limit.

Never pass secrets (the API key) to these functions.

=========================================================================== '''
import sys
import clr
import paths

clr.AddReference('System')
from System import DateTime
from System.IO import File, FileInfo
from System.Threading import Monitor

MAX_BYTES = 1024 * 1024

_lock = object()


def _to_text(arg):
    if isinstance(arg, unicode):
        return arg
    try:
        return unicode(arg)
    except Exception:
        return repr(arg)


def debug(*args):
    '''Appends one timestamped line. Never raises.'''
    line = u'[%s] %s\r\n' % (DateTime.Now.ToString('yyyy-MM-dd HH:mm:ss'),
                             u' '.join(_to_text(a) for a in args))
    Monitor.Enter(_lock)
    try:
        try:
            path = paths.log_path()
            if File.Exists(path) and FileInfo(path).Length > MAX_BYTES:
                old = path + '.1'
                if File.Exists(old):
                    File.Delete(old)
                File.Move(path, old)
            File.AppendAllText(path, line)
        except Exception:
            pass
    finally:
        Monitor.Exit(_lock)


def debug_exc(message):
    '''Logs message plus the exception currently being handled.'''
    exc = sys.exc_info()[1]
    debug(message, '-', exc.__class__.__name__ + ':', exc)
