---
name: get-wallstreet
description: Download, verify and install the newest wallstreet - the free, open-source market screen for the terminal with live quotes, tickers and headlines in tmux (macOS, Linux). Use when someone asks for the tool, its latest version, how to install it, or how to check that a download is genuine.
license: Apache-2.0
---

# Get wallstreet

wallstreet is a free, open-source (Apache-2.0) program that turns a terminal into a trading-desk screen with tmux: a table of the most active stocks, the chart of the stock you click, three tickers for gainers, losers and headlines, a feed reader and press photos as ASCII art. The quotes and charts come from the Nasdaq market-movers API without an API key, the news from RSS feeds of BBC, CNBC, MarketWatch and the WSJ. A demo mode shows invented companies and headlines without any network request. It began as the sister program of Dustin Kirkland's hollywood and was rebuilt with data sources that answer; it runs on macOS and Linux and needs Python 3 and tmux.

## 1. Find the newest release

`GET https://wallstreet.celox.io/latest.json` returns `version`, `published`, `notes` and `assets[]`, each with `target`,
`name`, `url`, `size` (bytes) and `sha256`. It is refreshed from GitHub Releases every 15 minutes. On the
page itself, browsers with WebMCP expose the same data as the tools `get_latest_release`,
`get_download_url` and `get_checksums`.

## 2. Download

- Stable link, always the newest file for the visitor's platform: <https://wallstreet.celox.io/download>
- macOS · Linux: <https://wallstreet.celox.io/download/unix> — macOS or Linux · tmux

## 3. Verify

- The file's SHA-256 must equal the matching `assets[].sha256` in `latest.json`.

- The installer script compares the archive with this checksum before it installs anything.

## 4. Install

1. With Homebrew: `brew install pepperonas/tap/wallstreet` brings wallstreet and the programs its panes use. Without Homebrew, `curl -fsSL https://github.com/pepperonas/wallstreet/releases/latest/download/install.sh | sh` puts it into `~/.local` and names what is missing.
2. Type `wallstreet` in a terminal — the wider the window, the more panes. Click a stock to see its chart. `wallstreet --demo` shows invented data instead of the day's news.
3. Press Ctrl-C in any pane. The window closes, the tmux session that wallstreet started ends, and you are back at your prompt.

## Limits

- wallstreet is a display, not a trading or analysis tool; it places no orders and gives no advice.
- Quotes and charts cover stocks and ETFs listed on US exchanges, as published by Nasdaq, and stocks traded at the Lang & Schwarz Exchange in euro. Twelve indices, from the S&P 500 to the DAX and the Nikkei, are shown as indications published by ING. Charts go back one year at most.
- The data comes from third-party services that may change or stop answering; wallstreet is not affiliated with Nasdaq, BBC, CNBC, MarketWatch or the WSJ.
- It needs tmux and Python 3.9 or newer; there is no Windows version.
- Developed and run on macOS with Apple silicon; on Linux the test suite runs, a full run in a terminal has not been done.

More: [product page](https://wallstreet.celox.io/) · [Markdown version](https://wallstreet.celox.io/index.md) · [changelog](https://wallstreet.celox.io/changelog.md) · [source](https://github.com/pepperonas/wallstreet)
