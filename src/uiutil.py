''' ===========================================================================

Running code on a control's UI thread from a background thread.

Control.Invoke/BeginInvoke take the abstract System.Delegate type, which
IronPython can't build from a Python function by itself; the function is
wrapped in MethodInvoker first.

=========================================================================== '''
import clr
import log

clr.AddReference('System.Windows.Forms')
from System.Windows.Forms import MethodInvoker


def invoke(control, fn, wait=False):
    '''
    Runs fn() on control's UI thread (directly if already on it). With
    wait=False it returns at once. Returns False if the control is gone or
    has no window yet, True otherwise.
    '''
    if control is None or control.IsDisposed:
        return False
    try:
        if not control.InvokeRequired:
            fn()
        elif wait:
            control.Invoke(MethodInvoker(fn))
        else:
            control.BeginInvoke(MethodInvoker(fn))
        return True
    except SystemError:
        # "Invoke or BeginInvoke cannot be called on a control until the
        # window handle has been created" (or it was just disposed)
        return False
    except Exception:
        log.debug_exc('UI update failed')
        return False
