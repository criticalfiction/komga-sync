''' Page conversion between ComicRack (0-based) and Komga (1-based). '''
from testlib import check, finish, temp_data_dir
from pagemap import cr_from_komga, komga_from_cr, progress, UNREAD, COMPLETED

temp_data_dir()

print('--- Komga -> ComicRack (same page count, 20)')
for (page, done), want in [((None, False), (0, False)),   # unread
                           ((1, False), (0, False)),      # page 1 = unread
                           ((2, False), (1, False)),
                           ((10, False), (9, False)),
                           ((20, True), (19, True)),      # last page = completed
                           ((5, True), (19, True))]:      # completed wins over page
    check('komga page %r done=%r' % (page, done), cr_from_komga(page, done, 20, 20), want)

print('--- ComicRack -> Komga (same page count, 20)')
for (index, done), want in [((0, False), UNREAD),
                            ((1, False), 2),
                            ((9, False), 10),
                            ((18, False), 19),
                            ((19, False), 19),           # never Komga's last page
                            ((19, True), COMPLETED),
                            ((3, True), COMPLETED)]:
    check('cr index %d done=%r' % (index, done), komga_from_cr(index, done, 20, 20), want)

print('--- round trips keep the page (20 pages)')
check('every part-read page survives CR->Komga->CR',
      all(cr_from_komga(komga_from_cr(i, False, 20, 20), False, 20, 20) == (i, False)
          for i in range(1, 19)))

print('--- different page counts (CR 100, Komga 50)')
check('halfway CR -> halfway Komga', komga_from_cr(50, False, 100, 50), 26)
check('halfway Komga -> halfway CR', cr_from_komga(25, False, 50, 100), (48, False))
check('first part-read CR page not shown as unread', komga_from_cr(1, False, 100, 50), 2)
check('near the end stays below the last page', komga_from_cr(98, False, 100, 50), 49)

print('--- tiny books')
check('1-page book read', komga_from_cr(0, True, 1, 1), COMPLETED)
check('1-page book unread', komga_from_cr(0, False, 1, 1), UNREAD)
check('2-page book part read -> page 1', komga_from_cr(1, False, 3, 2), 1)
check('Komga page 1 of 1, completed', cr_from_komga(1, True, 1, 1), (0, True))
check('page count unknown in Komga', komga_from_cr(5, False, 20, 0), 6)
check('page count unknown in ComicRack', cr_from_komga(5, False, 20, 0), (4, False))

print('--- progress (for "keep the most read")')
check('unread', progress(0, False, 20), 0.0)
check('completed', progress(3, True, 20), 1.0)
check('later page is more', progress(10, False, 20) > progress(3, False, 20), True)
check('part read never equals completed', progress(19, False, 20) < 1.0, True)

finish()
