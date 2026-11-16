# Confirmed facts

Checked on 2026-11-16 against ComicRack CE (installed build, plus source on
GitHub `maforget/ComicRackCE`) and the user's Komga at http://localhost:25600.

## ComicRack CE

Source: `tools/inspect_comicbook.ps1` (reflection on `ComicRack.Engine.dll`,
`ComicRack.Plugins.dll`) and `ComicRack.Engine/ComicBook.cs`,
`ComicRack/MainForm.cs`, `ComicRack/Program.cs`.

### `cYo.Projects.ComicRack.Engine.ComicBook`

| Member | Type | Writable | Notes |
|---|---|---|---|
| `FilePath` | String | yes | full Windows path, e.g. `X:\Comics\...\x.cbz` |
| `PageCount` | Int32 | yes | |
| `CurrentPage` | Int32 | yes | 0-based page the reader is on |
| `LastPageRead` | Int32 | yes | 0-based furthest page read |
| `OpenedTime` | DateTime | yes | local time; `DateTime.MinValue` = never opened |
| `OpenedCount` | Int32 | yes | |
| `HasBeenRead` | Boolean | yes | getter: `ReadPercentage >= 95`; setter calls `MarkAsRead()` / `MarkAsNotRead()` |
| `ReadPercentage` | Int32 | no | `(LastPageRead + 1) * 100 / PageCount`, clamped 1-100; 0 if `LastPageRead <= 0` |
| `Id` | Guid | yes | |
| `MarkAsRead()` | method | | `OpenedCount` to at least 1, `OpenedTime = Now`, `CurrentPage = LastPageRead = PageCount - 1` (1 for a 1-page book) |
| `MarkAsNotRead()` | method | | `OpenedTime = MinValue`, `CurrentPage = OpenedCount = LastPageRead = 0` |
| `BookChanged` | event | | exists; not needed for now |

`ReadPercentageAsRead = 95` is a constant in the code, not a setting.

### Plugin API: `ComicRack.App` (`IApplication`)

`GetLibraryBooks()` returns all library books (`IEnumerable<ComicBook>`);
`GetBook(file)` finds one by path. No mark-read helpers on the API itself.

### Hooks (`PluginEngine.ValidHooks`) and how they're called

- `Startup`: run via `BeginInvoke` on the main form once it's initialised,
  with no arguments.
- `BookOpened`: called with the `ComicBook`, **after** ComicRack has set
  `OpenedTime = DateTime.Now` (when "track current page" is on). So at
  that point `OpenedTime` no longer shows when the book was last read.
- `Shutdown`: called from the main form's `FormClosing` with one argument,
  `isUserClosing` (bool). **It must return True**: if it returns False
  while the user is closing, ComicRack cancels the close. Exceptions are
  swallowed by ComicRack.
- `ConfigScript`: the plugin's settings entry.
- There is **no** book-closed hook. (`MainForm.OnBookClosed` queues the book
  for file update but doesn't call plugins.)

## Komga

Source: `tools/inspect_komga.py` (read-only), samples in `docs/samples/`
(not committed: they contain personal paths).

- Auth: `X-API-Key` header works. `GET /api/v2/users/me` returns the user
  (id, email, roles). The user has roles ADMIN, FILE_DOWNLOAD,
  PAGE_STREAMING, KOREADER_SYNC, KOBO_SYNC, USER.
- `/api/v1/actuator/info` doesn't exist (404); there's no version call to rely on.
- Book list: `GET /api/v1/books?page=N&size=500` (also `POST /api/v1/books/list`).
  Spring page: `content`, `totalElements`, `totalPages`, `number`, `size`,
  `first`, `last`, `numberOfElements`, `empty`, `pageable`, `sort`.
  The library has **4,229 books = 9 pages of 500**.
- Book record keys: `id`, `url`, `name`, `number`, `seriesId`, `seriesTitle`,
  `libraryId`, `media`, `metadata`, `readProgress`, `created`,
  `lastModified`, `fileLastModified`, `fileHash`, `size`, `sizeBytes`,
  `deleted`, `oneshot`.
  - `url` is the plain Windows file path, the same as ComicRack's
    `FilePath` (including non-ASCII characters), so books match by path
    after lower-casing.
  - `media.pagesCount` is the page count; `media.status` is `READY` when
    analysed.
  - `readProgress` is `null` for unread books. When set it has `page`
    (1-based), `completed`, `lastModified`, `readDate`, `created`,
    `deviceId`, `deviceName` (confirmed in Task 3).
- Progress calls (confirmed live on the test book, then restored):
  - `PATCH /api/v1/books/{id}/read-progress {"page": 3}` sets page 3, not completed.
  - `{"completed": true}` marks it read **and moves the page to the last page**.
  - `{"page": <last page>}` **also marks it completed**: there's no
    "on the last page but not finished" state in Komga.
  - `DELETE /api/v1/books/{id}/read-progress` makes it unread (`readProgress = null`).
  - `readProgress.lastModified` moves forward with each change.
- Listing all 4,229 books (9 requests of 500) takes about 2 seconds.
  - `deleted` marks books Komga has seen disappear from disk; skip those.
  - Top-level `lastModified` is when the book record changed, **not** the
    reading progress.

## Test book

`X:\Comics\¡García!\01 - Tomo 1.cbz`, 182 pages.

| | ComicRack | Komga |
|---|---|---|
| State | read: `CurrentPage = LastPageRead = 181` (last page) | unread: `readProgress = null` |
| Last opened | 2023-02-06 | - |
| Id | `783772d1-6863-48d7-9f04-0af155ee0ecb` | `0S86GE5H7SE1Y` |

Under the default first-sync option ("Keep the most read") the expected
first sync result is: Komga marked read, ComicRack unchanged.

## Design changes from these facts

1. "Completed" on the ComicRack side means `HasBeenRead` (95% rule), so it
   matches what ComicRack shows. Writing uses `MarkAsRead()` /
   `MarkAsNotRead()`; a partial page sets `CurrentPage` and `LastPageRead`.
2. `BookOpened` can't use `OpenedTime` as "last read in ComicRack". For a
   conflict at that moment, the plugin uses the time it first saw the
   ComicRack change (recorded in the snapshot), as the plan allows.
3. The `Shutdown` hook always returns True, even on errors or timeouts.
4. Books with `deleted = true` in Komga are ignored.
