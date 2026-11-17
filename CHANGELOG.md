# Changelog

All notable changes to wallstreet are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.5.0] - 2026-11-17

### Added
- **The logo in real pixels.** Where the terminal draws pictures (sixel: iTerm2, WezTerm,
  foot, Windows Terminal ...) the logo is a picture of up to 576 pixels a side instead of
  30 character halves. Inside tmux this needs tmux 3.4 or newer built with sixel, and every
  terminal attached to the session must be able to; otherwise the logo stays in characters.
- Terminals without pictures but with true colour get the half blocks in 24-bit colour
  instead of the 256-colour palette.
- `WALLSTREET_LOGO=blocks` keeps the characters, `WALLSTREET_LOGO=sixel` asks for pixels.

### Changed
- Logos are fetched at 512 pixels (parqet.com first, financialmodelingprep.com as the
  second source); small ones are enlarged smoothly. PNGs with 1, 2 or 4 bits a pixel are
  read too.

## [1.4.0] - 2026-11-17

### Added
- **The logo of the selected company** beside the feed reader, drawn with half-block
  characters on a light tile; it follows the selection like the chart. A company without a
  logo, and every company in demo mode, gets a monogram in a colour of its own.
  Logos come from financialmodelingprep.com or parqet.com and are kept for 30 days.

### Changed
- The logo takes the place of the news picture in the default layout. The picture widget
  (`lib/wallstreet/img2txt`) is still there; `img2txt` (libcaca) is no longer needed for
  the default screen.

## [1.3.0] - 2026-11-17

### Added
- **Search.** `/` in the quote table - or a click on its hint line - opens a search for
  any stock or fund traded on a US exchange, by name or symbol. The results appear while
  you type; Enter or a click takes one.
- **Watchlist.** What you found is kept in a section of its own above the day's movers,
  with its quote, and stays there between runs. `d` on a watchlist row removes it.
- A status line at the bottom of the session names the keys.

### Changed
- Esc is recognised as a key of its own (it was held back as the possible start of an
  escape sequence), Backspace and Delete are understood.

## [1.2.0] - 2026-11-17

### Added
- **`YTD`** as a fifth span of the chart: from the first trading day of the year. The keys
  are now `1`-`5`.
- The day's chart draws **yesterday's close as a dotted line** and names it on the axis.
- After the close the header also shows the **after-hours** price and its change.
- Month, quarter, year-to-date and year end with **today's price**; the daily closes Nasdaq
  delivers stop at yesterday.

### Fixed
- **The day's chart began at 4:00 with the pre-market.** Thin early trading filled the
  first third of the picture and pushed the session, the part every other chart shows,
  to the right. The day now starts with the opening bell at 9:30; trading after 16:00 is
  drawn in grey behind it. Before the bell, the pre-market is all there is and is shown.
- **The day's result was wrong after the close.** The header compared the after-hours
  price with a `previousClose` from the chart answer that is not yesterday's close
  (NVDA on 16 November: -6.34 % instead of -4.12 %). It now takes the session's close and
  its change from the quote, as the table beside it does.

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
