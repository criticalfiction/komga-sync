''' The first-sync question's text (MessageBox replaced, so nothing pops up). '''
from testlib import check, finish, temp_data_dir
import syncrunner
import settings as S

temp_data_dir()
shown = []


class FakeBox(object):
    @staticmethod
    def Show(owner, text, title, *rest):
        shown.append(text)
        return syncrunner.DialogResult.No
syncrunner.MessageBox = FakeBox

answer = syncrunner.ask_first_sync(None, S.FIRST_SYNC_MOST_READ, 2115, 0, 71)
text = shown[0]
print(text)
check('No means no', answer, False)
check('names the option', '"Keep the most read"' in text, True)
check('counts', ('2115 books will be updated in Komga' in text,
                 '0 books will be updated in ComicRack' in text), (True, True))
check('backup path shown correctly',
      '%APPDATA%\\cYo\\ComicRack Community Edition' in text, True)
check('no wrong menu location', 'File >' in text, False)
finish()
