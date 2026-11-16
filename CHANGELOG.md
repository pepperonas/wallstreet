# Changelog

All notable changes to wallstreet are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.1] - 2026-11-17

### Changed
- **A click on `1D`, `1M`, `3M` or `1Y` opens that span.** Until now every click in the
  chart pane went on to the next span, wherever it landed. A click elsewhere in the pane
  still does that.

## [1.1.0] - 2026-11-17

### Added
- **The quote table is interactive.** Click a row - or move with the arrow keys, `j`/`k`
  or the mouse wheel - and the stock is selected.
- **A chart pane** beside the table shows the course of the selected stock, drawn with
  braille characters: today's trading by the minute, or one month, three months or a year
  of daily closes. `1`-`4`, the arrow keys or a click on the chart change the span. The
  course comes from the same Nasdaq interface as the quotes; in demo mode it is invented
  and ends at the quote in the table.
- The selection is remembered between runs.

### Changed
- **Layout:** the chart sits beside the quote table, above the feed reader and the
  picture. From 110 columns there is a chart and a feed reader, from 150 the picture too.
- wallstreet switches on tmux's mouse support in the session it creates, so clicks reach
  the table. A session you started yourself keeps its own setting; the keys work either way.
- The tickers show every symbol once and only the direction they stand for. The demo list
  of advancers could hold falling stocks, and symbols that are also Nasdaq-100 movers ran
  through a ticker twice.

## [1.0.0] - 2026-11-16

First release as a project of its own. It is based on `wallstreet` from
[hollywood 1.27](https://github.com/dustinkirkland/hollywood) by Dustin Kirkland;
the version numbers of this project are its own.

### Added
- **Data sources that answer.** Quotes, gainers and losers come from the Nasdaq
  market-movers API; headlines, the feed reader and the pictures from RSS feeds of
  BBC, CNBC, MarketWatch and the WSJ (`share/wallstreet/newsboat.urls` - one list for
  all three). The pages upstream scraped are gone or refuse scripts: Yahoo Finance
  answers 429, wsj.com 403, the Reuters feeds are switched off and the CNN feeds
  have carried no new entry since 2023.
- **`share/wallstreet/wsdata`**, the one place that fetches, caches and renders
  (Python 3, standard library only). Several panes share one request; when the
  network is down the last good state stays on screen.
- **`wallstreet --demo`**: invented companies and headlines, nothing is fetched -
  for screenshots, presentations and machines without a network.
- **Runs on macOS.** No `/dev/shm`, no `shuf`; the tools `w3m`, `rsstail`, `ticker`
  and `wget` are no longer needed, the tickers are drawn by `wsdata marquee`.
- `wallstreet --version`, Homebrew formula (`brew install pepperonas/tap/wallstreet`),
  `install.sh`, a release archive with checksums, and a test suite.

### Changed
- **Layout:** the quote table, the feed reader and a news picture on top, three
  tickers of three rows each below. Terminals narrower than 150 columns drop the
  picture, narrower than 110 the feed reader as well. The quote table redraws when
  its pane changes size and never prints more rows than fit.
- **Ctrl-C in any pane ends the show** by closing the tmux window; upstream killed
  processes by a path pattern, which also hit unrelated processes.
- The tmux session is closed on exit only if wallstreet created it.

### Security
- Text from the network is treated as untrusted: control characters are removed
  before anything reaches the terminal, so a feed or a company name cannot send
  escape sequences.
- Pictures are fetched over http(s) from public hosts only - no local files, no
  addresses inside the own network, redirects included - and answers above 8 MB are
  dropped.
- The cache lives in a directory only the user can write to
  (`~/Library/Caches/wallstreet`, `~/.cache/wallstreet`), not in a shared temporary
  directory.
