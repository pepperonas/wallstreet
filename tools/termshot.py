#!/usr/bin/env python3
"""termshot: picture of a tmux window, pane by pane, as PNG.

    tools/termshot.py SESSION OUT.png [--pane N] [--scale 2]

tmux cannot hand out a composed window, only the text of each pane with its
colours.  This reads every pane of SESSION's active window (or just pane N),
turns the ANSI colours into HTML, places the panes where tmux has them and
lets a Chromium-family browser take the picture.  Standard library only.
"""
import argparse
import html
import os
import pathlib
import re
import subprocess
import sys
import tempfile

BG, FG, BORDER = "#11121a", "#c8cde4", "#2c2e3f"
BASE = ["#1a1b26", "#f7768e", "#9ece6a", "#e0af68", "#7aa2f7", "#bb9af7", "#7dcfff", "#c0caf5",
        "#565f89", "#ff899d", "#b9f27c", "#ffc777", "#8db0ff", "#c7a9ff", "#a4daff", "#ffffff"]
CELL_W, CELL_H, FONT = 8.4, 17, 14
SGR = re.compile(r"\x1b\[([0-9;]*)m")
OTHER = re.compile(r"\x1b\[[0-9;?]*[A-Za-ln-z]|\x1b[()][0-9A-B]|\x0f|\x0e")


def colour256(n):
    if n < 16:
        return BASE[n]
    if n < 232:
        n -= 16
        r, g, b = n // 36, (n // 6) % 6, n % 6
        return "#%02x%02x%02x" % tuple(0 if v == 0 else 55 + 40 * v for v in (r, g, b))
    v = 8 + 10 * (n - 232)
    return "#%02x%02x%02x" % (v, v, v)


def apply(codes, st):
    i = 0
    while i < len(codes):
        c = codes[i]
        if c == 0:
            st.update(fg=None, bg=None, bold=False, dim=False, rev=False)
        elif c == 1:
            st["bold"] = True
        elif c == 2:
            st["dim"] = True
        elif c == 22:
            st["bold"] = st["dim"] = False
        elif c == 7:
            st["rev"] = True
        elif c == 27:
            st["rev"] = False
        elif 30 <= c <= 37:
            st["fg"] = BASE[c - 30]
        elif 90 <= c <= 97:
            st["fg"] = BASE[c - 82]
        elif c == 39:
            st["fg"] = None
        elif 40 <= c <= 47:
            st["bg"] = BASE[c - 40]
        elif 100 <= c <= 107:
            st["bg"] = BASE[c - 92]
        elif c == 49:
            st["bg"] = None
        elif c in (38, 48) and i + 1 < len(codes):
            key = "fg" if c == 38 else "bg"
            if codes[i + 1] == 5 and i + 2 < len(codes):
                st[key] = colour256(codes[i + 2])
                i += 2
            elif codes[i + 1] == 2 and i + 4 < len(codes):
                st[key] = "#%02x%02x%02x" % tuple(codes[i + 2:i + 5])
                i += 4
        i += 1


def line_html(line, st):
    out, pos = [], 0
    line = OTHER.sub("", line)

    def emit(text):
        if not text:
            return
        fg, bg = st["fg"] or FG, st["bg"]
        if st["bold"] and st["fg"] in BASE[:8]:
            fg = BASE[BASE.index(st["fg"]) + 8]
        if st["rev"]:
            fg, bg = bg or BG, fg
        style = "color:%s;" % fg
        if bg:
            style += "background:%s;" % bg
        if st["bold"]:
            style += "font-weight:700;"
        if st["dim"]:
            style += "opacity:.6;"
        cells = "".join(html.escape(ch) if ord(ch) < 127 else "<i>%s</i>" % html.escape(ch)
                        for ch in text)
        out.append('<span style="%s">%s</span>' % (style, cells))

    for m in SGR.finditer(line):
        emit(line[pos:m.start()])
        codes = [int(c) if c else 0 for c in m.group(1).split(";")]
        apply(codes, st)
        pos = m.end()
    emit(line[pos:])
    return "".join(out)


def tmux(*args):
    return subprocess.run(("tmux",) + args, capture_output=True, text=True, check=True).stdout


def browser():
    names = [os.environ.get("TERMSHOT_BROWSER"),
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Chromium.app/Contents/MacOS/Chromium",
             "google-chrome", "chromium", "chromium-browser"]
    for name in filter(None, names):
        if os.path.isfile(name):
            return name
        from shutil import which
        if which(name):
            return which(name)
    sys.exit("termshot: no Chromium-family browser found (set TERMSHOT_BROWSER)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("out")
    ap.add_argument("--pane", type=int)
    ap.add_argument("--scale", type=float, default=2)
    a = ap.parse_args()

    fmt = "#{pane_index} #{pane_left} #{pane_top} #{pane_width} #{pane_height} #{pane_id}"
    panes = [p.split() for p in tmux("list-panes", "-t", a.session, "-F", fmt).splitlines()]
    if a.pane is not None:
        panes = [p for p in panes if int(p[0]) == a.pane]
        panes[0][1] = panes[0][2] = "0"
    cols = max(int(p[1]) + int(p[3]) for p in panes)
    rows = max(int(p[2]) + int(p[4]) for p in panes)

    blocks = []
    for _, left, top, width, height, pid in panes:
        text = tmux("capture-pane", "-e", "-p", "-t", pid)
        st = dict(fg=None, bg=None, bold=False, dim=False, rev=False)
        lines = [line_html(l, st) for l in text.split("\n")[:int(height)]]
        blocks.append('<pre style="left:%.1fpx;top:%dpx;width:%.1fpx;height:%dpx">%s</pre>' % (
            int(left) * CELL_W, int(top) * CELL_H, int(width) * CELL_W, int(height) * CELL_H,
            "\n".join(lines)))

    pad = 14
    w, h = int(cols * CELL_W + 2 * pad + 1), rows * CELL_H + 2 * pad
    page = """<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;width:%dpx;height:%dpx;background:%s;overflow:hidden}
.grid{position:absolute;left:%dpx;top:%dpx;width:%.1fpx;height:%dpx;background:%s}
pre{position:absolute;margin:0;overflow:hidden;background:%s;color:%s;
  font:%dpx/%dpx Menlo,"DejaVu Sans Mono",monospace;white-space:pre}
pre i{display:inline-block;width:%.1fpx;height:%dpx;overflow:hidden;font-style:normal;
  vertical-align:top;text-align:center}
pre span{display:inline-block;height:%dpx;vertical-align:top;letter-spacing:%.3fpx}
</style><div class="grid">%s</div>""" % (
        w, h, BG, pad, pad, cols * CELL_W, rows * CELL_H, BORDER, BG, FG, FONT, CELL_H,
        CELL_W, CELL_H, CELL_H, 0, "".join(blocks))

    out = pathlib.Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / "shot.html"
        src.write_text(page, encoding="utf-8")
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=%g" % a.scale,
                        "--window-size=%d,%d" % (w, h), "--screenshot=%s" % out,
                        src.as_uri()], check=True, capture_output=True)
    print("%s  %dx%d cells" % (out, cols, rows))


if __name__ == "__main__":
    main()
