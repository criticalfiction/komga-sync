''' ===========================================================================

The Komga Sync settings dialog.

Layout is written in pixels at 96 DPI; AutoScaleMode.Dpi scales it to the
display (ComicRack runs DPI-aware). Sizes use ClientSize, the area inside
the borders.

=========================================================================== '''
import clr
import log
import settings as settings_mod
import snapshot
import uiutil
from komgaclient import KomgaClient, KomgaError

clr.AddReference('System.Windows.Forms')
clr.AddReference('System.Drawing')
from System.Windows.Forms import Form, Label, TextBox, Button, CheckBox, \
    NumericUpDown, ComboBox, ComboBoxStyle, GroupBox, DialogResult, \
    FormBorderStyle, FormStartPosition, AutoScaleMode, MessageBox, \
    MessageBoxButtons, MessageBoxIcon, MessageBoxDefaultButton
from System.Drawing import Point, Size, SizeF, Color
from System.Threading import Thread, ThreadStart

TEST_TIMEOUT_MS = 10000


# ===========================================================================
class ConfigForm(Form):

    def __init__(self, current):
        '''current: the Settings object to show (and update on OK).'''
        self.__settings = current
        self.AutoScaleDimensions = SizeF(96.0, 96.0)
        self.AutoScaleMode = AutoScaleMode.Dpi
        self.Text = 'Komga Sync Settings'
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MaximizeBox = False
        self.MinimizeBox = False
        self.ShowInTaskbar = False
        self.StartPosition = FormStartPosition.CenterParent
        self.ClientSize = Size(480, 400)
        self.__testing = False
        self.__build()
        self.__load_values()

    # -------------------------------------------------------------------
    def __label(self, text, x, y, w, h=20, parent=None):
        lbl = Label()
        lbl.Text = text
        lbl.Location = Point(x, y)
        lbl.Size = Size(w, h)
        (parent or self).Controls.Add(lbl)
        return lbl

    def __build(self):
        self.__label('Komga address:', 12, 15, 110)
        self.url_box = TextBox()
        self.url_box.Location = Point(130, 12)
        self.url_box.Size = Size(338, 23)
        self.Controls.Add(self.url_box)

        self.__label('API key:', 12, 47, 110)
        self.key_box = TextBox()
        self.key_box.Location = Point(130, 44)
        self.key_box.Size = Size(338, 23)
        self.key_box.UseSystemPasswordChar = True
        self.Controls.Add(self.key_box)

        self.test_button = Button()
        self.test_button.Text = 'Test connection'
        self.test_button.Location = Point(130, 76)
        self.test_button.Size = Size(130, 26)
        self.test_button.Click += self.__on_test
        self.Controls.Add(self.test_button)
        self.test_result = self.__label('', 130, 106, 338, 36)

        self.enabled_box = CheckBox()
        self.enabled_box.Text = 'Sync automatically while ComicRack is open'
        self.enabled_box.Location = Point(12, 148)
        self.enabled_box.Size = Size(456, 24)
        self.Controls.Add(self.enabled_box)

        self.__label('Sync every', 30, 181, 76)
        self.interval_box = NumericUpDown()
        self.interval_box.Location = Point(110, 178)
        self.interval_box.Size = Size(60, 23)
        self.interval_box.Minimum = settings_mod.MIN_INTERVAL
        self.interval_box.Maximum = settings_mod.MAX_INTERVAL
        self.Controls.Add(self.interval_box)
        self.__label('minutes', 176, 181, 100)

        group = GroupBox()
        group.Text = 'First sync'
        group.Location = Point(12, 210)
        group.Size = Size(456, 122)
        self.Controls.Add(group)
        self.__label('For books that have never been synced, use:', 10, 20, 436,
                     parent=group)
        self.source_box = ComboBox()
        self.source_box.DropDownStyle = ComboBoxStyle.DropDownList
        self.source_box.Location = Point(10, 42)
        self.source_box.Size = Size(436, 23)
        for _, text in settings_mod.FIRST_SYNC_SOURCES:
            self.source_box.Items.Add(text)
        group.Controls.Add(self.source_box)
        self.redo_button = Button()
        self.redo_button.Text = 'Redo first sync...'
        self.redo_button.Location = Point(10, 78)
        self.redo_button.Size = Size(140, 26)
        self.redo_button.Click += self.__on_redo
        group.Controls.Add(self.redo_button)
        self.redo_note = self.__label('Treats every book as never synced at the '
                                      'next sync, using the option above.',
                                      160, 76, 286, 36, parent=group)
        self.redo_note.ForeColor = Color.DimGray

        self.status_label = self.__label('', 12, 338, 456, 20)
        self.status_label.ForeColor = Color.DimGray

        self.ok_button = Button()
        self.ok_button.Text = 'OK'
        self.ok_button.Location = Point(300, 364)
        self.ok_button.Size = Size(80, 26)
        self.ok_button.Click += self.__on_ok
        self.Controls.Add(self.ok_button)
        self.cancel_button = Button()
        self.cancel_button.Text = 'Cancel'
        self.cancel_button.Location = Point(388, 364)
        self.cancel_button.Size = Size(80, 26)
        self.cancel_button.DialogResult = DialogResult.Cancel
        self.Controls.Add(self.cancel_button)
        self.AcceptButton = self.ok_button
        self.CancelButton = self.cancel_button

    def __load_values(self):
        s = self.__settings
        self.url_box.Text = s.url
        self.key_box.Text = s.api_key
        self.enabled_box.Checked = s.enabled
        self.interval_box.Value = settings_mod.clamp_interval(s.interval_minutes)
        keys = [k for k, _ in settings_mod.FIRST_SYNC_SOURCES]
        self.source_box.SelectedIndex = keys.index(s.first_sync_source) \
            if s.first_sync_source in keys else 0
        if s.last_sync_time:
            self.status_label.Text = 'Last sync: %s, %s' % (s.last_sync_time,
                                                            s.last_sync_status)
        else:
            self.status_label.Text = 'Last sync: never'

    # -------------------------------------------------------------------
    def __on_test(self, sender, event):
        '''Checks the address and key in the boxes (not yet saved).'''
        if self.__testing:
            return
        self.__testing = True
        self.test_button.Enabled = False
        self.test_result.ForeColor = Color.DimGray
        self.test_result.Text = 'Testing...'
        client = KomgaClient(self.url_box.Text, self.key_box.Text.strip(),
                             TEST_TIMEOUT_MS)

        def work():
            try:
                me = client.whoami()
                ok, text = True, 'Connected as %s' % (me.get('email') or me.get('id'))
            except KomgaError, ex:
                ok, text = False, ex.message
            except Exception, ex:
                log.debug_exc('test connection failed')
                ok, text = False, 'Test failed: %s' % ex

            def show():
                self.__testing = False
                self.test_button.Enabled = True
                self.test_result.ForeColor = Color.DarkGreen if ok else Color.Firebrick
                self.test_result.Text = text
            uiutil.invoke(self, show)

        thread = Thread(ThreadStart(work))
        thread.IsBackground = True
        thread.Start()

    def __on_redo(self, sender, event):
        answer = MessageBox.Show(
            self,
            'Forget which books have already been synced?\n\n'
            'At the next sync every book is treated as never synced, using '
            'the "First sync" option. You\'ll see a summary and can cancel '
            'before anything changes.',
            'Redo first sync', MessageBoxButtons.YesNo, MessageBoxIcon.Question,
            MessageBoxDefaultButton.Button2)
        if answer != DialogResult.Yes:
            return
        try:
            snapshot.reset()
            self.redo_note.ForeColor = Color.DarkGreen
            self.redo_note.Text = 'Done: the next sync treats every book as never synced.'
        except Exception, ex:
            log.debug_exc('redo first sync failed')
            self.redo_note.ForeColor = Color.Firebrick
            self.redo_note.Text = 'Couldn\'t clear the sync records: %s' % ex

    def __on_ok(self, sender, event):
        # reload first: a sync may have saved its status while the dialog
        # was open, and this dialog doesn't edit that
        s = settings_mod.Settings.load()
        self.__settings = s
        s.url = settings_mod.normalize_url(self.url_box.Text)
        s.api_key = self.key_box.Text.strip()
        s.enabled = self.enabled_box.Checked
        s.interval_minutes = int(self.interval_box.Value)
        s.first_sync_source = settings_mod.FIRST_SYNC_SOURCES[
            max(0, self.source_box.SelectedIndex)][0]
        try:
            s.save()
        except Exception, ex:
            log.debug_exc('saving settings failed')
            MessageBox.Show(self, 'Couldn\'t save the settings: %s' % ex,
                            'Komga Sync', MessageBoxButtons.OK, MessageBoxIcon.Error)
            return
        self.DialogResult = DialogResult.OK
        self.Close()
