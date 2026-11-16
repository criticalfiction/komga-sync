''' ===========================================================================

Page numbers between ComicRack and Komga.

ComicRack: pages are 0-based (CurrentPage). "Completed" is its read flag
(HasBeenRead, true from 95% of the pages).
Komga: pages are 1-based. No progress = unread. Reaching the last page
always means completed (Komga sets that itself).

Both sides are reduced to (index, completed):
  index      0-based page on THAT side's page count
  completed  True if read
and "unread" is (0, False) on both sides: Komga's page 1 and ComicRack's
page 0 mean the same thing.

If the two sides count a different number of pages, the page is scaled by
its position in the book.

=========================================================================== '''

UNREAD = 'unread'
COMPLETED = 'completed'


def _scale(index, from_pages, to_pages):
    '''index on a from_pages book -> same position on a to_pages book.'''
    if to_pages <= 0 or from_pages <= 0 or from_pages == to_pages:
        return max(0, index)
    if from_pages == 1 or to_pages == 1:
        return 0
    pos = float(index) / (from_pages - 1)
    return int(round(pos * (to_pages - 1)))


def _clamp(index, pages):
    if pages > 0:
        return max(0, min(index, pages - 1))
    return max(0, index)


def cr_from_komga(page, completed, komga_pages, cr_pages):
    '''
    Komga progress (1-based page or None, completed) -> ComicRack
    (index, completed).
    '''
    if completed:
        return (max(0, cr_pages - 1), True)
    if not page:
        return (0, False)
    index = _scale(page - 1, komga_pages, cr_pages)
    return (_clamp(index, cr_pages), False)


def komga_from_cr(index, completed, cr_pages, komga_pages):
    '''
    ComicRack (index, completed) -> what Komga should record: COMPLETED,
    UNREAD, or a 1-based page number. A book that isn't completed is never
    put on Komga's last page, since Komga would then mark it completed.
    '''
    if completed:
        return COMPLETED
    if index <= 0:
        return UNREAD
    if komga_pages <= 0:            # Komga hasn't counted the pages yet
        return index + 1
    if komga_pages <= 2:
        # a 1-2 page book has no "part read" page that isn't the first
        # (= unread) or the last (= completed): record page 1
        return 1
    page_index = _scale(index, cr_pages, komga_pages)
    # not page 1 (would read back as unread), not the last (completed)
    return max(1, min(page_index, komga_pages - 2)) + 1


def progress(index, completed, pages):
    '''How far through the book, 0.0 (unread) to 1.0 (completed).'''
    if completed:
        return 1.0
    if pages <= 1 or index <= 0:
        return 0.0
    return min(0.999, float(index) / (pages - 1))
