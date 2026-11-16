''' Settings dialog: layout, Test connection, Redo first sync, OK saves. '''
import sys
from testlib import check, finish, temp_data_dir, test_config, pump, ROOT
import clr
clr.AddReference('System.Windows.Forms')
clr.AddReference('System.Drawing')
from System.Drawing import Bitmap, Rectangle
from System.Drawing.Imaging import ImageFormat
from System.IO import Directory, File, Path
from System.Text import Encoding
from System.Windows.Forms import Button

import paths
import settings as S
from configform import ConfigForm

out = Path.Combine(ROOT, 'build', 'ui-test')
Directory.CreateDirectory(out)
temp_data_dir()
cfg = test_config()


def snapshot_png(form, name):
    bmp = Bitmap(form.Width, form.Height)
    form.DrawToBitmap(bmp, Rectangle(0, 0, form.Width, form.Height))
    bmp.Save(Path.Combine(out, name), ImageFormat.Png)
    bmp.Dispose()


def all_controls(parent):
    for c in parent.Controls:
        yield c
        for g in all_controls(c):
            yield g


s = S.Settings.load()
form = ConfigForm(s)
form.Show()
pump(1)

print('--- layout')
inside = all(c.Right <= c.Parent.ClientSize.Width and c.Bottom <= c.Parent.ClientSize.Height
             for c in all_controls(form))
check('every control inside its parent', inside)
check('defaults shown', (form.url_box.Text, int(form.interval_box.Value),
                         form.source_box.SelectedIndex, form.enabled_box.Checked),
      ('http://localhost:25600', 5, 0, True))
check('status says never synced', form.status_label.Text, 'Last sync: never')
check('API key is masked', form.key_box.UseSystemPasswordChar, True)

print('--- Test connection')
form.key_box.Text = 'wrong-key'
form.test_button.PerformClick()
pump(15, lambda: form.test_button.Enabled)
check('bad key message', 'rejected the API key' in form.test_result.Text, True)
form.key_box.Text = cfg['api_key']
form.test_button.PerformClick()
pump(15, lambda: form.test_button.Enabled)
check('good key -> Connected as ...', form.test_result.Text.startswith('Connected as '), True)
print('     %s' % form.test_result.Text.split('@')[0] + '@...')
snapshot_png(form, 'settings.png')

print('--- Redo first sync (answered automatically)')
import configform
real_show = configform.MessageBox.Show


class FakeBox(object):
    answer = None

    @staticmethod
    def Show(*args):
        return FakeBox.answer
configform.MessageBox = FakeBox
from System.Windows.Forms import DialogResult
File.WriteAllText(paths.state_path(), '{}', Encoding.UTF8)
FakeBox.answer = DialogResult.No
form.redo_button.PerformClick()
check('No keeps the snapshot', File.Exists(paths.state_path()), True)
FakeBox.answer = DialogResult.Yes
form.redo_button.PerformClick()
check('Yes clears the snapshot', File.Exists(paths.state_path()), False)
check('note confirms it', form.redo_note.Text.startswith('Done'), True)

print('--- OK saves')
form.interval_box.Value = 7
form.source_box.SelectedIndex = 1
form.ok_button.PerformClick()
pump(1)
t = S.Settings.load()
check('saved interval', t.interval_minutes, 7)
check('saved source', t.first_sync_source, S.FIRST_SYNC_COMICRACK)
check('saved key works', t.api_key == cfg['api_key'], True)
check('dialog closed', form.IsDisposed or not form.Visible, True)

finish()
