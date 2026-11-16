''' Test connection against the real Komga (read-only). '''
from testlib import check, finish, temp_data_dir, test_config
from komgaclient import KomgaClient, KomgaError

temp_data_dir()
cfg = test_config()


def attempt(url, key):
    try:
        me = KomgaClient(url, key, 8000).whoami()
        return 'ok', me
    except KomgaError, ex:
        return ex.kind, ex.message


kind, me = attempt(cfg['url'], cfg['api_key'])
check('good key connects', kind, 'ok')
if kind == 'ok':
    check('user has an id', bool(me.get('id')), True)
    check('user has an email', '@' in (me.get('email') or ''), True)

kind, msg = attempt(cfg['url'], 'wrong-key')
check('bad key -> auth error', kind, 'auth')
print('     message: %s' % msg)

kind, msg = attempt('http://localhost:1', cfg['api_key'])
check('nothing listening -> unreachable', kind, 'unreachable')
print('     message: %s' % msg)

kind, msg = attempt('http://no-such-host.invalid:25600', cfg['api_key'])
check('unknown host -> unreachable', kind, 'unreachable')
print('     message: %s' % msg)

kind, msg = attempt(cfg['url'] + '/not-komga', cfg['api_key'])
check('wrong path -> http error, not a crash', kind in ('http', 'auth', 'bad_response'), True)
print('     %s: %s' % (kind, msg))

finish()
