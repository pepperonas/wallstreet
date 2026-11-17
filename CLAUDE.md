# CLAUDE.md

Wall Street screen for the terminal: quotes, tickers, headlines in tmux panes. Split out of
Dustin Kirkland's `hollywood` (Apache-2.0) and given data sources that answer. Repo
`pepperonas/wallstreet` (public), page <https://wallstreet.celox.io>, brew
`pepperonas/tap/wallstreet`. The sister project is `~/claude/hollywood`.

## Layout

- `bin/wallstreet` — launcher (bash): session, window, layout by terminal width, `--demo`.
- `lib/wallstreet/*` — one script per pane: `quotes` (interactive, `wsdata browse`),
  `chart` (`wsdata chart`), `logo` (`wsdata logo`), `ticker`, `newsboat`,
  plus `headlines`, `img2txt` and `jp2a` (not in the default layout).
- `share/wallstreet/wsdata` — **the only place that touches the network.** Python 3.9+,
  standard library only. Commands: `browse`, `chart`, `table`, `movers up|down`,
  `headlines`, `image`, `marquee`, `cachedir`, `demofeed`.
- `share/wallstreet/newsboat.urls` — one feed list for reader, ticker and pictures.
- `tools/`, `website/` — as in hollywood.

## Rules

- Everything from the network is untrusted: `clean()` before printing, `check_url()` before
  fetching (http(s), public hosts, redirects too), `MAX_BYTES`. Tests pin each.
- The cache is `~/Library/Caches/wallstreet` / `~/.cache/wallstreet`, never a shared temp dir.
- Panes get their environment from the tmux **server**, not from the launcher — that is why
  every pane command is prefixed with `$run` (`env WALLSTREET_DEMO=…`); a test pins it.
- `wsdata` asks the terminal for its size on fd 2/0/1: stdout is a pipe inside `$(...)`.
- Public pictures are taken with `--demo` (invented companies and headlines).
- Version lives in `VERSION`, `bin/wallstreet`, `CHANGELOG.md`, `packaging/wallstreet.rb`.
- Never kill by pattern (`pkill -f lib/wallstreet/`); panes quit by closing their window.
- Release and page: as in hollywood (`tools/tap-formula.sh`, product-page kit, wildcard TLS).

## Interaction (1.1.0)

- `wsdata browse` and `wsdata chart` are two processes in two panes; the selection travels
  through `selection.json` (`selection-demo.json` in demo mode) in the cache directory.
  `read_selection()` validates symbol and span — the file is input like any other.
- `Terminal` uses cbreak, not raw: Ctrl-C stays a signal, so the widget's `trap quit INT`
  still closes the window. Mouse = SGR 1006 (`ESC [ < b ; x ; y M`); a release (`m`) is not
  a click; a sequence cut in half stays in the buffer.
- Clicks only arrive with tmux `mouse on`. It is a **session** option: set it only in a
  session the launcher created (`WALLSTREET_OWN_SESSION`), never in the user's own.
- Testing without a hand on the mouse: `tmux send-keys -t wallstreet.0 -l $'\e[<0;10;16M'`
  delivers a click report to the pane's program. The path through a real terminal and
  tmux's forwarding was not exercised by hand.
- A row of the table must not contain `ESC[0m` — it would end the highlight of the selected
  row after the first column (pinned). Use `ESC[39;22m`.

## Search and watchlist (1.3.0)

- `search()` asks `api.nasdaq.com/api/autocomplete/slookup/25?search=` and keeps `asset`
  STOCKS and ETF only (mutual funds and notes have no chart). Demo: `DEMO_STOCKS`.
- The watchlist is `watchlist.json` (`watchlist-demo.json`) in the cache directory, newest
  first, at most `WATCH_MAX`; `read_watchlist()` validates like `read_selection()`.
  Its quotes come from `quote()` - one cached request per symbol and minute.
- `table_rows()` returns `(text, symbol, section)`; section `watch` is what `d` may remove.
- Search results sit on line `3 + i` of the pane: `cmd_browse` maps a click on line `y` to
  result `y - 3`, and a test reads the position off the rendered view.
- A lone ESC is the Escape key only once nothing follows (`parse_input(final=True)`);
  before 1.3.0 it stayed in the buffer forever.

## Logo (1.4.0)

- `wsdata logo` follows `selection.json` like the chart. PNG decoding is the script's own
  (`png_pixels`, 8-bit, not interlaced, at most 1024 px a side, bounded decompression) -
  the standard library has none, and the picture is untrusted input.
- Sources `LOGO_URLS`, tried in order, cached 30 days per source; what is not a PNG is
  deleted and the symbol remembered in `NO_LOGO` for the process. Only a `SYMBOL` match
  reaches the address. Demo mode never fetches: monogram.
- Tile ground: dark for a logo that is mostly white **and** has transparent corners
  (Alnylam); a picture with a ground of its own keeps the light tile (Apple from FMP).
- Three ways to draw (`graphics()`): **sixel** when every tmux client has the `sixel`
  feature and reports a cell size (`#{client_termfeatures}`, `#{client_cell_width/height}`;
  re-checked every 3 s because the terminal attaches after the pane starts), else half
  blocks in 24-bit colour (`RGB` feature), else in 256 colours. A client without sixel
  would be shown tmux's placeholder text - hence "every".
- The picture is a square of whole cells, at most 576 px; tmux re-emits it at the pane's
  position. Checked 2026-11-17 with a stand-in terminal (pty with a pixel size that answers
  the device-attributes question with `4`) and `sixel2png` from libsixel: 544 x 544 px
  arrived at the right cell. **Not seen in iTerm2 by me.**
- Never test with `tmux kill-server` on the default socket: it ends the user's own
  wallstreet/hollywood. Use `tmux -L <name>`.

## The chart's numbers (1.2.0)

- The day is the **regular session** (9:30-16:00 New York; the API writes local time as if
  it were UTC, `minute_of_day`). Pre-market is dropped, after-hours follows in grey
  (`dim_from`). Before the bell there is only pre-market and it is shown.
- The day's result comes from `/info`, never from the chart answer: after the close
  `primaryData` is the after-hours trade and `secondaryData` the session; `previousClose`
  of the chart answer is **not** yesterday's close (NVDA 2026-11-16: 166.19 vs 162.85).
  Yesterday's close = session last - session change.
- Longer spans compare with their first point. YTD starts on 1 January, so its base is the
  first close of the year - that is what Google shows; the textbook base (last close of the
  old year) gives another figure (TSLA: -15.56 % vs -13.32 %).
- Compared by hand with Google Finance on 2026-11-16: NVDA day 156.14 / -6.71 / -4.12 %.

## Sources (checked 2026-11-16)

Nasdaq `api.nasdaq.com/api/marketmovers?assetclass=stocks` needs a browser User-Agent.
Charts: `api.nasdaq.com/api/quote/<symbol>/chart?assetclass=stocks|etf` (intraday), with
`&fromdate=&todate=` daily closes; an ETF answers only under `etf`.
Dead or blocking: Yahoo Finance (429), wsj.com pages (403), Reuters feeds (gone), CNN RSS
(frozen since 2023), stooq CSV (404).
