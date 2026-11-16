''' Shared helpers for tests run with run_ironpython.ps1 (IronPython 2.7). '''
import clr
import sys

clr.AddReference('System')
clr.AddReference('System.Windows.Forms')
from System import DateTime, Guid
from System.IO import Directory, File, Path
from System.Text import Encoding
from System.Threading import Thread
from System.Windows.Forms import Application

import paths
import jsonutil

ROOT = Path.GetDirectoryName(Path.GetDirectoryName(Path.GetFullPath(sys.argv[0])))
_results = []


def check(label, got, want=True):
    ok = got == want
    _results.append(ok)
    print('%s %-58s %r' % ('ok  ' if ok else 'FAIL', label, got))
    if not ok:
        print('     expected %r' % (want,))
    return ok


def finish():
    '''Prints the failure count (run_ironpython.ps1 turns it into the exit code).'''
    print('%d failure(s)' % _results.count(False))


def temp_data_dir():
    '''Points paths at a new empty temp folder; returns it.'''
    folder = Path.Combine(Path.GetTempPath(), 'KomgaSyncTest-' + Guid.NewGuid().ToString('N'))
    Directory.CreateDirectory(folder)
    paths.set_data_dir(folder)
    return folder


def test_config():
    '''test_config.json from the project root (url, api_key, test_books).'''
    path = Path.Combine(ROOT, 'test_config.json')
    return jsonutil.loads(File.ReadAllText(path, Encoding.UTF8))


def pump(seconds, until=None):
    '''Processes window messages until until() is true or time runs out.'''
    end = DateTime.Now.AddSeconds(seconds)
    while DateTime.Now < end:
        Application.DoEvents()
        if until is not None and until():
            return True
        Thread.CurrentThread.Join(30)
    return until() if until is not None else True
