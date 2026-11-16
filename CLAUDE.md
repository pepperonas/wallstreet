# CLAUDE.md

Wall Street screen for the terminal: quotes, tickers, headlines in tmux panes. Split out of
Dustin Kirkland's `hollywood` (Apache-2.0) and given data sources that answer. Repo
`pepperonas/wallstreet` (public), page <https://wallstreet.celox.io>, brew
`pepperonas/tap/wallstreet`. The sister project is `~/claude/hollywood`.

## Layout

- `bin/wallstreet` — launcher (bash): session, window, layout by terminal width, `--demo`.
- `lib/wallstreet/*` — one script per pane: `quotes`, `ticker`, `newsboat`, `img2txt`,
  plus `headlines` and `jp2a` (not in the default layout).
- `share/wallstreet/wsdata` — **the only place that touches the network.** Python 3.9+,
  standard library only. Commands: `table`, `movers up|down`, `headlines`, `image`,
  `marquee`, `cachedir`, `demofeed`.
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

## Sources (checked 2026-11-16)

Nasdaq `api.nasdaq.com/api/marketmovers?assetclass=stocks` needs a browser User-Agent.
Dead or blocking: Yahoo Finance (429), wsj.com pages (403), Reuters feeds (gone), CNN RSS
(frozen since 2023), stooq CSV (404).
