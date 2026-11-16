r''' ===========================================================================

Where Komga Sync keeps its files: %APPDATA%\Komga Sync\
  settings.dat  settings (API key encrypted)
  state.dat     sync snapshot (what each book looked like at the last sync)
  sync.log      debug log

Tests call set_data_dir() to use a temporary folder instead.

=========================================================================== '''
import clr

clr.AddReference('System')
from System import Environment
from System.IO import Directory, Path

_data_dir = None


def data_dir():
    '''The data folder (created if missing).'''
    global _data_dir
    if _data_dir is None:
        _data_dir = Path.Combine(Environment.GetFolderPath(
            Environment.SpecialFolder.ApplicationData), 'Komga Sync')
    if not Directory.Exists(_data_dir):
        Directory.CreateDirectory(_data_dir)
    return _data_dir


def set_data_dir(folder):
    '''Use another folder (tests).'''
    global _data_dir
    _data_dir = folder


def settings_path():
    return Path.Combine(data_dir(), 'settings.dat')


def state_path():
    return Path.Combine(data_dir(), 'state.dat')


def log_path():
    return Path.Combine(data_dir(), 'sync.log')
