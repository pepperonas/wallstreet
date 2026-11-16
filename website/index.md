<!--# block name="none" --><!--# endblock -->
# wallstreet — Live Stock Tickers for Your Terminal

> wallstreet is a free, open-source (Apache-2.0) program that turns a terminal into a trading-desk screen with tmux: a table of the most active stocks, three tickers for gainers, losers and headlines, a feed reader and press photos as ASCII art. The quotes come from the Nasdaq market-movers API without an API key, the news from RSS feeds of BBC, CNBC, MarketWatch and the WSJ. A demo mode shows invented companies and headlines without any network request. It began as the sister program of Dustin Kirkland's hollywood and was rebuilt with data sources that answer; it runs on macOS and Linux and needs Python 3 and tmux.

This is the Markdown version of https://wallstreet.celox.io/ for agents and text tools. A short summary with every link lives at https://wallstreet.celox.io/llms.txt.

## Download

- **Newest release:** https://wallstreet.celox.io/download (picks the file for your platform; always the current release)
- **Current version:** <!--# include virtual="/ssi/version.txt" stub="none" --> · released <!--# include virtual="/ssi/date.txt" stub="none" -->
- **Release data as JSON:** https://wallstreet.celox.io/latest.json
- **Requirements:** macOS · Linux: macOS or Linux · tmux

Files in the current release:

<!--# include virtual="/ssi/files.md" stub="none" -->

## Features

- **The quote table** — The most active stocks, the Nasdaq-100 movers, advancers and decliners — symbol, name, last price, change and percent, green for up and red for down. It redraws every minute and never prints more rows than fit.
- **Three tickers** — Across the bottom of the window: the day's biggest gainers in green, the biggest losers in red and the headlines of all feeds in yellow, each scrolling at its own pace.
- **News beside the numbers** — A feed reader shows the latest articles and reloads by itself; next to it a press photo from the feeds appears as coloured ASCII art. One list of feeds drives the reader, the ticker and the pictures — edit it to follow other news.
- **No key, no account** — The quotes come from the Nasdaq market-movers interface, the news from public RSS feeds of BBC, CNBC, MarketWatch and the WSJ. Nothing to register, nothing to configure, and wallstreet itself collects nothing.
- **A demo mode for the camera** — `wallstreet --demo` shows twenty companies that do not exist, prices that drift every minute and invented headlines. Nothing is fetched — for presentations, screenshots, a film set or a machine without a network.
- **Careful with what the network sends** — Headlines and company names are stripped of control characters before they reach your terminal. Pictures are loaded over http(s) from public hosts only, and the cache is a folder that only you can write to.

### What it looks like

- **The whole screen** — Quotes, feed reader, picture and three tickers — here in demo mode. ([image](https://wallstreet.celox.io/assets/gallery/wallstreet.jpg))
- **Quote table** — Four sections, fitted to the height of the pane. ([image](https://wallstreet.celox.io/assets/gallery/table.jpg))
- **Feed reader** — The newest articles, reloading by themselves. ([image](https://wallstreet.celox.io/assets/gallery/newsboat.jpg))
- **Headlines** — One headline after the other, with the time. ([image](https://wallstreet.celox.io/assets/gallery/headlines.jpg))

## Install

1. **Install** — With Homebrew: `brew install pepperonas/tap/wallstreet` brings wallstreet and the programs its panes use. Without Homebrew, `curl -fsSL https://github.com/pepperonas/wallstreet/releases/latest/download/install.sh | sh` puts it into `~/.local` and names what is missing.
2. **Run** — Type `wallstreet` in a terminal — the wider the window, the more panes. `wallstreet --demo` shows invented data instead of the day's news.
3. **Quit** — Press Ctrl-C in any pane. The window closes, the tmux session that wallstreet started ends, and you are back at your prompt.

## Verify

<!--# include virtual="/ssi/checksums.md" stub="none" -->

- The installer script compares the archive with this checksum before it installs anything.

## FAQ

**Is wallstreet free?** Yes. It is open source under the Apache-2.0 licence, without ads, accounts or telemetry, and it needs no paid data subscription. The original was written by Dustin Kirkland as part of hollywood.

**Where do the numbers come from?** From the market-movers interface of nasdaq.com: the most active, rising and falling stocks of the trading day. Outside trading hours the last close stays on screen. They are for looking at, not for trading.

**What does it need?** macOS or Linux, `tmux` and Python 3.9 or newer. The feed reader needs `newsboat`, the picture `img2txt` from libcaca; without them those two panes stay away. Homebrew installs all of it.

**How do I update?** With Homebrew: `brew upgrade wallstreet`. Otherwise run the installer script again; it replaces the installed copy with the newest release.

**Can I follow my own stocks or other news?** Other news: yes — the file `newsboat.urls` lists the feeds, one per line. Your own stocks: no. The table shows the day's market movers; a watch list is not part of wallstreet.

**Is the download genuine?** Every release is built by GitHub Actions from the tagged source. This page shows the SHA-256 of each file; compare it with `shasum -a 256`, or let the installer script do it.

## Limits

- wallstreet is a display, not a trading or analysis tool; it places no orders and gives no advice.
- The quotes are the day's market movers of the US exchanges as published by Nasdaq; there is no free choice of symbols and no history.
- The data comes from third-party services that may change or stop answering; wallstreet is not affiliated with Nasdaq, BBC, CNBC, MarketWatch or the WSJ.
- It needs tmux and Python 3.9 or newer; there is no Windows version.
- Developed and run on macOS with Apple silicon; on Linux the test suite runs, a full run in a terminal has not been done.

## Links

- Source code: https://github.com/pepperonas/wallstreet
- Changelog: https://wallstreet.celox.io/changelog.md
- Licence (Apache-2.0): https://github.com/pepperonas/wallstreet/blob/main/LICENSE
- Support the project: https://www.paypal.com/donate/?business=martin.pfeffer@celox.io&currency_code=EUR&item_name=wallstreet
- Author: Martin Pfeffer, https://celox.io — Imprint https://celox.io/impressum/ · Privacy https://celox.io/datenschutz/
