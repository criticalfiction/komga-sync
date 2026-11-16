''' Settings: defaults, round trip, encrypted key, bad values, bad file. '''
from testlib import check, finish, temp_data_dir
import clr
clr.AddReference('System')
from System.IO import File
from System.Text import Encoding

import paths
import settings as S
import snapshot

temp_data_dir()

print('--- defaults (no file)')
s = S.Settings.load()
check('url', s.url, 'http://localhost:25600')
check('interval', s.interval_minutes, 5)
check('enabled', s.enabled, True)
check('first sync source', s.first_sync_source, S.FIRST_SYNC_MOST_READ)
check('not configured without a key', s.is_configured(), False)

print('--- round trip')
s.url = 'localhost:25600/'
s.api_key = 'secret-test-key-123'
s.interval_minutes = 12
s.enabled = False
s.first_sync_source = S.FIRST_SYNC_KOMGA
s.last_sync_time = '2026-11-16 12:04'
s.last_sync_status = '3 pulled, 1 pushed'
s.save()
t = S.Settings.load()
check('url normalised', t.url, 'http://localhost:25600')
check('api key', t.api_key, 'secret-test-key-123')
check('interval', t.interval_minutes, 12)
check('enabled', t.enabled, False)
check('first sync source', t.first_sync_source, S.FIRST_SYNC_KOMGA)
check('last sync', (t.last_sync_time, t.last_sync_status),
      ('2026-11-16 12:04', '3 pulled, 1 pushed'))
check('configured', t.is_configured(), True)

text = File.ReadAllText(paths.settings_path(), Encoding.UTF8)
check('key not readable in the file', 'secret-test-key' in text, False)
check('no temp file left behind', File.Exists(paths.settings_path() + '.tmp'), False)

print('--- every first sync source survives a round trip')
for key, _ in S.FIRST_SYNC_SOURCES:
    t.first_sync_source = key
    t.save()
    check('  ' + key, S.Settings.load().first_sync_source, key)

print('--- bad values')
File.WriteAllText(paths.settings_path(),
                  '{"interval_minutes": 0, "first_sync_source": "nonsense", '
                  '"api_key_protected": "not-base64!", "url": ""}', Encoding.UTF8)
b = S.Settings.load()
check('interval clamped to 1', b.interval_minutes, 1)
check('unknown source -> default', b.first_sync_source, S.FIRST_SYNC_MOST_READ)
check('undecryptable key -> empty', b.api_key, '')
check('empty url -> default', b.url, 'http://localhost:25600')
check('interval 99999 clamped', S.clamp_interval(99999), 24 * 60)
check('interval "abc" -> default', S.clamp_interval('abc'), 5)

print('--- damaged file')
File.WriteAllText(paths.settings_path(), '{not json', Encoding.UTF8)
check('damaged file -> defaults', S.Settings.load().url, 'http://localhost:25600')

print('--- redo first sync clears the snapshot')
File.WriteAllText(paths.state_path(), '{}', Encoding.UTF8)
check('reset returns True', snapshot.reset(), True)
check('state.dat gone', File.Exists(paths.state_path()), False)
check('reset with nothing to clear', snapshot.reset(), False)

finish()
