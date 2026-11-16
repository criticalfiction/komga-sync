''' ===========================================================================

Komga Sync - ComicRack Community Edition plugin.

Keeps read state and page position in sync, in both directions, between
ComicRack and a Komga server that serves the same comic files.

=========================================================================== '''
# How ComicRack reads the #@ headers below (PluginEngine.Initialize):
# - it keeps only ONE command per #@Key (ConfigScript excepted), so the
#   Startup and Shutdown hooks need different keys;
# - the ConfigScript is attached to the command with the same key, and that
#   command's "Configure..." button in Edit > Preferences > Scripts opens it;
# - each listed command needs its own #@Name, or its row is blank.

import clr
import log
from settings import Settings

clr.AddReference('System.Windows.Forms')
from System.Windows.Forms import MessageBox, MessageBoxButtons, MessageBoxIcon

# ComicRack is injected by the host at runtime
if False:
    ComicRack = None


# ============================================================================
#@Key   komga-sync
#@Hook  ConfigScript
# ============================================================================
def komga_sync_config():
    '''Opens the Komga Sync settings.'''
    try:
        from configform import ConfigForm
        form = ConfigForm(Settings.load())
        try:
            form.ShowDialog(ComicRack.MainWindow)
        finally:
            form.Dispose()
    except Exception, ex:
        log.debug_exc('config failed')
        MessageBox.Show('Komga Sync settings failed to open:\n\n%s' % ex,
                        'Komga Sync', MessageBoxButtons.OK, MessageBoxIcon.Error)


# the scheduler for this ComicRack session (created at Startup)
_scheduler = None


# ============================================================================
#@Name  Komga Sync
#@Key   komga-sync
#@Hook  Startup
#@Image komgasync.png
#@Description Keeps read progress in sync between ComicRack and Komga.
# ============================================================================
def komga_sync_startup():
    '''
    When ComicRack starts: sync once (if configured and switched on), then
    keep syncing while ComicRack is open. The schedule re-reads the
    settings each time, so it also starts working as soon as the plugin is
    configured, without a restart.
    '''
    global _scheduler
    try:
        from syncrunner import SyncRunner
        from scheduler import Scheduler
        s = Settings.load()
        if not s.is_configured():
            log.debug('startup: not configured yet; waiting for settings')
        elif not s.enabled:
            log.debug('startup: automatic sync is off')
        runner = SyncRunner(ComicRack, ComicRack.MainWindow)
        _scheduler = Scheduler(runner, ComicRack.MainWindow)
        _scheduler.start()
    except Exception:
        log.debug_exc('startup failed')


# ============================================================================
#@Name  Komga Sync (on close)
#@Key   komga-sync-shutdown
#@Hook  Shutdown
#@Image komgasync.png
#@Description Sends ComicRack's latest read progress to Komga when ComicRack closes.
# ============================================================================
def komga_sync_shutdown(is_user_closing):
    '''
    When ComicRack closes: send ComicRack's latest changes to Komga (a few
    seconds at most). Must return True, or ComicRack cancels the close.
    '''
    try:
        if _scheduler is not None:
            _scheduler.shutdown()
    except Exception:
        log.debug_exc('shutdown failed')
    return True
