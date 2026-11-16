# Komga Sync for ComicRack

A ComicRack Community Edition plugin that keeps **read state and page
position** in step, in both directions, between ComicRack and a
[Komga](https://komga.org) server serving the same comic files. Read on your
phone (Mihon, Panels, or any Komga app) and ComicRack follows; read in
ComicRack and Komga follows.

## Requirements

- ComicRack Community Edition on Windows.
- Komga on the **same PC**, with its library pointing at the **same folders**
  ComicRack uses. Books are matched by file path. Path matching ignores case
  and slash direction, and handles accented characters stored in different
  forms.
- One Komga user. ComicRack only keeps one reader's progress per book.

## Setup

1. **Back up your ComicRack library first.** Close ComicRack (check the system
   tray too), and copy
   `%APPDATA%\cYo\ComicRack Community Edition\ComicDb.xml` somewhere safe. To
   restore, close ComicRack and copy it back. For regular automatic backups,
   see Edit > Preferences > Advanced > Backup Manager.
2. Install Komga (the Windows desktop app is easiest), add a library for your
   comics folder, and let it finish scanning.
3. In Komga's web page, create an **API key** under your account settings.
4. In ComicRack, install `KomgaSync-<version>.crplugin` (Edit > Preferences >
   Scripts > Install) and restart ComicRack.
5. Open the plugin's settings: Edit > Preferences > Scripts, under
   Available Scripts > "Actions when ComicRack starts" select **Komga Sync**,
   then click **Configure...** below the list. Enter the Komga address (`http://localhost:25600`) and the API
   key, then click **Test connection**.
6. Choose the **First sync** option (below) and click OK. The next sync
   starts within 30 seconds.

## The first sync

A book that has never been synced is handled by the **First sync** setting.
This covers every book on the very first run, and books added later:

| Option | Effect |
|---|---|
| **Keep the most read** (default) | Takes whichever side is further through the book. It never makes a book less read: completed beats any page, and a later page beats an earlier one. Unread never wipes progress. |
| **ComicRack** | Copies ComicRack's state to Komga, including unread. |
| **Komga** | Copies Komga's state to ComicRack, including unread. |

If Komga is freshly installed (everything unread there) and ComicRack has
your reading history, **Keep the most read** and **ComicRack** give the same
result. Your read books are marked read in Komga, and nothing in ComicRack
changes.

Before the very first sync changes anything, the plugin shows a summary
("N books will be updated in Komga, M in ComicRack") and asks. If you answer
**No**, nothing changes and automatic sync is switched off; switch it back on
in the settings when you're ready.

**Redo first sync** (in the settings) forgets which books have been synced,
so the next sync treats every book as never synced, using the First sync
option. The summary and question are shown again. Use it after changing the
First sync option, after reinstalling Komga, or if the two have drifted apart
badly.

## When it syncs

While ComicRack is open, and only when the plugin is configured and **Sync
automatically** is ticked:

- When ComicRack starts.
- Every **N minutes** (the "Sync every" setting, default 5). A change applies
  within 30 seconds, without a restart.
- When you **switch back to ComicRack's window**, at most once a minute. That's
  how a book you read on the phone opens at the right page: ComicRack's
  reader takes the page when a book opens, so the progress has to arrive
  first. It takes a couple of seconds.
- When ComicRack **closes**. This sends only ComicRack's latest changes to
  Komga, and waits at most 5 seconds. Anything newer in Komga is picked up at
  the next start.

The time and result of the last sync are shown at the bottom of the settings,
for example "Last sync: 2026-11-16 12:04, 3 pulled, 1 pushed, 71 books not in
Komga". Books in only one of the two programs are counted and left alone.

## Who wins when both changed

After a book's first sync, the plugin compares each side with how the book
was at the last sync:

- If only one side changed, that change is copied to the other. This includes
  marking a book unread.
- If both changed, the newer change wins. Komga records when its progress
  changed. ComicRack doesn't, so its change time is when you last opened the
  book, or the time of the sync if the book was already open at the previous
  one. A tie goes to ComicRack.

## Known limits

- **ComicRack's 95% rule.** ComicRack counts a book as read once you've read
  95% of its pages. Komga only does at the last page. A book left on, say,
  page 19 of 20 in Komga shows as read in ComicRack and in progress in Komga.
  The plugin leaves that difference alone instead of flipping it back and
  forth.
- **Page counts.** If the two programs count a different number of pages, the
  position is scaled. A 1-2 page book can't show "part read" in Komga.
- **A book open in ComicRack** keeps its own page while it's open. A change
  made on the phone at the same time arrives once the book is closed and
  reopened, or ComicRack's page wins if you keep reading there.
- **ComicRack must be running** for changes to cross over. Komga keeps the
  phone's progress in the meantime.
- **Marking unread from Komga** uses ComicRack's own "mark as unread". That
  also clears the book's opened count and last-opened date, just as it does
  in ComicRack.
- **Moving or renaming files** makes the plugin see them as new books, which
  are handled by the First sync option.
- **The same file twice** in ComicRack's library: that file is skipped and
  logged.

## Files

All in `%APPDATA%\Komga Sync\`:

| File | Contents |
|---|---|
| `settings.dat` | Settings. The API key is encrypted for your Windows account (DPAPI). |
| `state.dat` | Each book's state at its last sync. Deleting it is the same as Redo first sync. A damaged copy is kept as `state.dat.bad`. |
| `sync.log` | What each sync did, book by book. Rotated at 1 MB to `sync.log.1`. |

## Development

The plugin is IronPython 2.7, the version built into ComicRack. Tests run in
ComicRack CE's own IronPython, using its real `ComicBook` class, and several
run against a live Komga. Live tests use only the test book(s), and always
put them back as they were.

```
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_tests.ps1          # checks, all tests, build
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_tests.ps1 scheduler  # tests matching a name
python build.py                                                               # build only
```

Live tests need `test_config.json` in the project root. It isn't committed:

```json
{"url": "http://localhost:25600", "api_key": "...",
 "test_books": ["X:\\Comics\\Some Series\\01.cbz"]}
```

- `check_imports.ps1` checks every .NET name imported in `src\` against the
  real assemblies.
- `check_source.py` flags non-ASCII characters and byte-order marks (which
  IronPython 2 rejects), class attributes later redefined as methods, and
  syntax errors.
- `docs/facts.md` records what was confirmed about ComicRack and Komga, and
  where it came from.
