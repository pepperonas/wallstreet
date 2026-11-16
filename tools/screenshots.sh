#!/usr/bin/env bash
# Screenshots for the README and the project page: docs/screenshots/*.png
#
#   tools/screenshots.sh
#
# Starts wallstreet in a detached tmux session, waits for the data and takes
# the whole window plus the single panes, in demo mode: the companies and
# headlines in the pictures are invented.  Needs tmux and a
# Chromium-family browser (see tools/termshot.py).
set -eu
cd "$(dirname "$0")/.."
OUT=docs/screenshots
S=wallstreet
mkdir -p "$OUT"
export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

tmux kill-session -t $S 2>/dev/null || true
tmux new-session -d -s $S -x 172 -y 50 "bash"
tmux send-keys -t $S "WALLSTREET_OWN_SESSION=1 $PWD/bin/wallstreet --demo; exit" Enter
sleep 22
# select a stock further down and the three-month span, as a user would
tmux send-keys -t $S.0 Down Down Down Down
tmux send-keys -t $S.0 3
sleep 4
python3 tools/termshot.py $S "$OUT/wallstreet.png"
python3 tools/termshot.py $S "$OUT/quotes.png" --pane 0
python3 tools/termshot.py $S "$OUT/chart.png" --pane 1
python3 tools/termshot.py $S "$OUT/newsboat.png" --pane 2
python3 tools/termshot.py $S "$OUT/picture.png" --pane 3
tmux kill-session -t $S 2>/dev/null || true

# The table alone, large
tmux new-session -d -s wsshots -x 110 -y 34 "env WALLSTREET_DEMO=1 $PWD/lib/wallstreet/quotes"
sleep 5
python3 tools/termshot.py wsshots "$OUT/table.png"
tmux kill-session -t wsshots
tmux new-session -d -s wsshots -x 110 -y 34 "env WALLSTREET_DEMO=1 $PWD/lib/wallstreet/headlines"
sleep 40
python3 tools/termshot.py wsshots "$OUT/headlines.png"
tmux kill-session -t wsshots
