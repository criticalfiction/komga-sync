''' ===========================================================================

The sync decision for one book: push ComicRack's state to Komga, pull
Komga's into ComicRack, or nothing. Pure logic - no network, no ComicRack
calls - so every rule can be tested directly.

Inputs (all plain values):
  cr      ComicRack state: .index (0-based), .completed, .pages, .opened_utc
  kb      Komga book:      .page (1-based or None), .completed, .pages,
                           .progress_modified (UTC or None)
  entry   the book's snapshot entry (state at its last successful sync),
          or None if it has never been synced
  now     current UTC time
  first_source  the "First sync source" setting

Rules:
  - Sides already agree -> nothing.
  - Never synced -> the First sync source decides:
      comicrack: push    komga: pull
      most_read: whichever side is further through the book; never makes
                 a book less read
  - Synced before: compare each side with the snapshot.
      only ComicRack changed -> push; only Komga changed -> pull
      both changed -> the newer change wins (see _cr_change_time /
      _komga_change_time); a tie goes to ComicRack
      neither changed but they differ -> nothing (e.g. ComicRack's 95% rule
      calls a book read that Komga shows as in progress)

=========================================================================== '''
import pagemap
from crbooks import same_state
from settings import FIRST_SYNC_COMICRACK, FIRST_SYNC_KOMGA, FIRST_SYNC_MOST_READ

PUSH = 'push'     # ComicRack -> Komga
PULL = 'pull'     # Komga -> ComicRack
NONE = 'none'


class Decision(object):
    '''
    action  PUSH / PULL / NONE
    komga   for PUSH: pagemap.COMPLETED, pagemap.UNREAD or a 1-based page
    cr      for PULL: (index, completed) to apply in ComicRack
    reason  short text for the log
    '''
    __slots__ = ('action', 'komga', 'cr', 'reason')

    def __init__(self, action, reason, komga=None, cr=None):
        self.action, self.reason, self.komga, self.cr = action, reason, komga, cr

    def __repr__(self):
        return 'Decision(%s, %s)' % (self.action, self.reason)


def komga_as_cr(cr, kb):
    '''Komga's progress in ComicRack's page numbering: (index, completed).'''
    return pagemap.cr_from_komga(kb.page, kb.completed, kb.pages, cr.pages)


def in_sync(cr, kb):
    ki, kc = komga_as_cr(cr, kb)
    return same_state(cr.index, cr.completed, ki, kc)


def _push(cr, kb, reason):
    return Decision(PUSH, reason,
                    komga=pagemap.komga_from_cr(cr.index, cr.completed, cr.pages, kb.pages))


def _pull(cr, kb, reason):
    return Decision(PULL, reason, cr=komga_as_cr(cr, kb))


def _cr_change_time(cr, entry, now):
    '''
    When ComicRack's change happened. ComicRack doesn't record that, but a
    change can only happen while the book is open, so its last-opened time
    is the best clue - if it's after the last sync. Otherwise (the book was
    already open at the last sync) all we know is that it changed since
    then, so use now.
    '''
    synced = entry.get('t')
    if cr.opened_utc is not None and synced is not None and cr.opened_utc > synced:
        return cr.opened_utc
    return now


def _komga_change_time(kb, now):
    '''Komga records when progress changed; marking unread deletes it, so use now.'''
    return kb.progress_modified if kb.progress_modified is not None else now


def decide(cr, kb, entry, now, first_source=FIRST_SYNC_MOST_READ):
    if in_sync(cr, kb):
        return Decision(NONE, 'in sync')

    if entry is None:
        if first_source == FIRST_SYNC_COMICRACK:
            return _push(cr, kb, 'first sync: ComicRack is the source')
        if first_source == FIRST_SYNC_KOMGA:
            return _pull(cr, kb, 'first sync: Komga is the source')
        ki, kc = komga_as_cr(cr, kb)
        cr_progress = pagemap.progress(cr.index, cr.completed, cr.pages)
        k_progress = pagemap.progress(ki, kc, cr.pages)
        if cr_progress > k_progress:
            return _push(cr, kb, 'first sync: ComicRack is further')
        if k_progress > cr_progress:
            return _pull(cr, kb, 'first sync: Komga is further')
        return Decision(NONE, 'first sync: equally far')

    cr_changed = not same_state(cr.index, cr.completed, entry['ci'], entry['cc'])
    k_changed = (kb.page, bool(kb.completed)) != (entry['kp'], entry['kc'])
    if cr_changed and not k_changed:
        return _push(cr, kb, 'changed in ComicRack')
    if k_changed and not cr_changed:
        return _pull(cr, kb, 'changed in Komga')
    if not cr_changed and not k_changed:
        return Decision(NONE, 'unchanged (sides differ, left alone)')

    cr_time = _cr_change_time(cr, entry, now)
    k_time = _komga_change_time(kb, now)
    if k_time > cr_time:
        return _pull(cr, kb, 'changed on both, Komga newer')
    return _push(cr, kb, 'changed on both, ComicRack newer')


# ===========================================================================
def komga_after_push(target, komga_pages):
    '''Komga's (page, completed) once a push of `target` has succeeded.'''
    if target == pagemap.COMPLETED:
        return (komga_pages or None, True)
    if target == pagemap.UNREAD:
        return (None, False)
    if komga_pages and target >= komga_pages:
        return (target, True)            # Komga completes on the last page
    return (target, False)


def make_entry(cr_index, cr_completed, komga_page, komga_completed, now):
    '''A snapshot entry: both sides' state as of a successful sync at `now`.'''
    return {'ci': int(cr_index), 'cc': bool(cr_completed),
            'kp': komga_page, 'kc': bool(komga_completed), 't': now}
