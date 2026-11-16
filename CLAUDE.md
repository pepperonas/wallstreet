# CLAUDE.md

Wall Street screen for the terminal: quotes, tickers, headlines in tmux panes. Split out of
Dustin Kirkland's `hollywood` (Apache-2.0) and given data sources that answer. Repo
`pepperonas/wallstreet` (public), page <https://wallstreet.celox.io>, brew
`pepperonas/tap/wallstreet`. The sister project is `~/claude/hollywood`.

## Layout

- `bin/wallstreet` — launcher (bash): session, window, layout by terminal width, `--demo`.
- `lib/wallstreet/*` — one script per pane: `quotes` (interactive, `wsdata browse`),
  `chart` (`wsdata chart`), `ticker`, `newsboat`, `img2txt`,
  plus `headlines` and `jp2a` (not in the default layout).
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

## Sources (checked 2026-11-16)

Nasdaq `api.nasdaq.com/api/marketmovers?assetclass=stocks` needs a browser User-Agent.
Charts: `api.nasdaq.com/api/quote/<symbol>/chart?assetclass=stocks|etf` (intraday), with
`&fromdate=&todate=` daily closes; an ETF answers only under `etf`.
Dead or blocking: Yahoo Finance (429), wsj.com pages (403), Reuters feeds (gone), CNN RSS
(frozen since 2023), stooq CSV (404).
