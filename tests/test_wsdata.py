"""Tests for share/wallstreet/wsdata.  No network: demo mode or a patched fetch.

    python3 -m unittest discover -s tests -v
"""
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import re
import stat
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def load(demo, cache_home):
    """A private copy of the script as a module, with its own cache directory."""
    env = {"XDG_CACHE_HOME": cache_home, "WALLSTREET_DEMO": "1" if demo else "0"}
    with mock.patch.dict(os.environ, env):
        loader = importlib.machinery.SourceFileLoader("wsdata_%d" % demo, str(ROOT / "share/wallstreet/wsdata"))
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        sys.dont_write_bytecode = True
        loader.exec_module(module)
    return module


def out_of(fn, *args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class Base(unittest.TestCase):
    demo = True

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = load(self.demo, self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()


class Clean(Base):
    def test_escape_sequences_lose_their_escape(self):
        self.assertNotIn("\x1b", self.ws.clean("A\x1b[31mB"))

    def test_bell_and_backspace_are_removed(self):
        self.assertEqual(self.ws.clean("a\x07b\x08c"), "a b c")

    def test_bidi_override_is_removed(self):
        self.assertNotIn("‮", self.ws.clean("abc‮def"))

    def test_ordinary_text_is_untouched(self):
        self.assertEqual(self.ws.clean("Zürich & Co. — 12,5 %"), "Zürich & Co. — 12,5 %")

    def test_non_strings_are_converted(self):
        self.assertEqual(self.ws.clean(42), "42")


class Urls(Base):
    def refused(self, url):
        with self.assertRaises(ValueError):
            self.ws.check_url(url)

    def test_file_scheme_is_refused(self):
        self.refused("file:///etc/passwd")

    def test_ftp_scheme_is_refused(self):
        self.refused("ftp://8.8.8.8/a.jpg")

    def test_loopback_is_refused(self):
        self.refused("http://127.0.0.1:8080/a.jpg")

    def test_private_network_is_refused(self):
        self.refused("http://192.168.1.10/a.jpg")

    def test_link_local_metadata_address_is_refused(self):
        self.refused("http://169.254.169.254/latest/meta-data")

    def test_ipv6_loopback_is_refused(self):
        self.refused("http://[::1]/a.jpg")

    def test_url_without_host_is_refused(self):
        self.refused("https:///a.jpg")

    def test_public_address_passes(self):
        self.assertEqual(self.ws.check_url("https://8.8.8.8/a.jpg"), "https://8.8.8.8/a.jpg")

    def test_fetch_checks_before_it_connects(self):
        with mock.patch.object(self.ws.OPENER, "open") as opened:
            with self.assertRaises(ValueError):
                self.ws.fetch("http://127.0.0.1/x")
            opened.assert_not_called()

    def test_opener_has_no_file_or_ftp_handler(self):
        names = {type(h).__name__ for h in self.ws.OPENER.handlers}
        self.assertFalse(names & {"FileHandler", "FTPHandler"}, names)


class CacheDir(Base):
    def test_cache_lives_under_xdg_cache_home(self):
        self.assertEqual(self.ws.CACHE, os.path.join(self.tmp.name, "wallstreet"))

    def test_cache_is_private(self):
        self.assertEqual(stat.S_IMODE(os.stat(self.ws.CACHE).st_mode), 0o700)

    def test_open_permissions_are_closed_again(self):
        os.chmod(self.ws.CACHE, 0o755)
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": self.tmp.name}):
            self.ws.cache_dir()
        self.assertEqual(stat.S_IMODE(os.stat(self.ws.CACHE).st_mode), 0o700)

    def test_a_symlink_in_its_place_is_refused(self):
        with tempfile.TemporaryDirectory() as other, tempfile.TemporaryDirectory() as home:
            os.symlink(other, os.path.join(home, "wallstreet"))
            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": home}):
                with self.assertRaises(SystemExit):
                    self.ws.cache_dir()


class Cached(Base):
    def test_producer_result_is_returned_and_stored(self):
        self.assertEqual(self.ws.cached("a", 60, lambda: b"one"), b"one")
        self.assertTrue(os.path.exists(os.path.join(self.ws.CACHE, "a")))

    def test_fresh_copy_is_reused(self):
        self.ws.cached("a", 60, lambda: b"one")
        self.assertEqual(self.ws.cached("a", 60, lambda: b"two"), b"one")

    def test_old_copy_is_replaced(self):
        self.ws.cached("a", 60, lambda: b"one")
        self.assertEqual(self.ws.cached("a", 0, lambda: b"two"), b"two")

    def test_stale_copy_survives_a_failure(self):
        self.ws.cached("a", 60, lambda: b"one")

        def fail():
            raise OSError("network down")
        self.assertEqual(self.ws.cached("a", 0, fail), b"one")

    def test_failure_without_a_copy_gives_nothing(self):
        def fail():
            raise OSError("network down")
        self.assertEqual(self.ws.cached("b", 60, fail), b"")

    def test_no_temporary_file_is_left_behind(self):
        self.ws.cached("a", 60, lambda: b"one")
        self.assertEqual(os.listdir(self.ws.CACHE), ["a"])


class Demo(Base):
    def test_every_section_has_rows(self):
        data = self.ws.movers()
        for key, least in (("MostActiveByDollarVolume", 8), ("Nasdaq100Movers", 8),
                           ("MostAdvanced", 1), ("MostDeclined", 1)):
            self.assertGreaterEqual(len(data[key]["table"]["rows"]), least, key)

    def test_two_reads_in_one_minute_agree(self):
        with mock.patch.object(self.ws.time, "time", return_value=1_800_000_000.0):
            self.assertEqual(self.ws.movers(), self.ws.movers())

    def test_quotes_move_from_minute_to_minute(self):
        with mock.patch.object(self.ws.time, "time", return_value=1_800_000_000.0):
            a = self.ws.movers()
        with mock.patch.object(self.ws.time, "time", return_value=1_800_000_060.0):
            b = self.ws.movers()
        self.assertNotEqual(a, b)

    def test_demo_never_fetches(self):
        with mock.patch.object(self.ws, "fetch", side_effect=AssertionError("fetched")):
            out_of(self.ws.cmd_table)
            out_of(self.ws.cmd_headlines)
            out_of(self.ws.cmd_movers, "up")
            out_of(self.ws.cmd_image)

    def movers_at(self, minute, direction):
        with mock.patch.object(self.ws.time, "time", return_value=1_800_000_000.0 + 60 * minute):
            return out_of(self.ws.cmd_movers, direction).strip()

    def test_gainers_are_all_up(self):
        # the demo quotes change every minute: one minute proves nothing
        for minute in range(200):
            line = self.movers_at(minute, "up")
            self.assertNotIn(" -", line, minute)

    def test_losers_are_all_down(self):
        for minute in range(200):
            line = self.movers_at(minute, "down")
            self.assertNotIn(" +", line, minute)

    def test_no_symbol_runs_twice_in_a_ticker(self):
        for minute in range(200):
            for direction in ("up", "down"):
                symbols = [part.split()[0] for part in self.movers_at(minute, direction).split(" ... ") if part]
                self.assertEqual(len(symbols), len(set(symbols)), (minute, symbols))

    def test_a_flat_or_unreadable_change_is_left_out(self):
        fake = {"MostAdvanced": {"table": {"rows": [
            {"symbol": "AAA", "lastSalePrice": "$1", "change": "+2%"},
            {"symbol": "BBB", "lastSalePrice": "$1", "change": "unch"},
            {"symbol": "CCC", "lastSalePrice": "$1", "change": "0.00%"}]}}}
        with mock.patch.object(self.ws, "movers", return_value=fake):
            self.assertEqual(out_of(self.ws.cmd_movers, "up").strip(), "AAA 1 +2.00%")

    def test_headlines_are_unique(self):
        lines = out_of(self.ws.cmd_headlines).splitlines()
        self.assertEqual(len(lines), len(set(lines)))
        self.assertGreaterEqual(len(lines), 20)

    def test_demo_picture_ships_with_the_package(self):
        path = out_of(self.ws.cmd_image).strip()
        with open(path, "rb") as f:
            self.assertEqual(f.read(3), b"\xff\xd8\xff")

    def test_demo_feed_is_valid_rss(self):
        urls = out_of(self.ws.cmd_demofeed).strip()
        with open(urls) as f:
            url = f.read().strip()
        self.assertTrue(url.startswith("file://"))
        root = ET.parse(url[len("file://"):]).getroot()
        self.assertEqual(len(root.findall(".//item")), len(self.ws.DEMO_HEADLINES))


class Table(Base):
    def render(self, cols, lines):
        size = os.terminal_size((cols, lines))
        with mock.patch.object(self.ws, "term_size", return_value=size):
            return out_of(self.ws.cmd_table).rstrip("\n").split("\n")

    def test_no_line_is_wider_than_the_terminal(self):
        for cols in (60, 80, 120):
            for line in self.render(cols, 40):
                self.assertLess(len(ANSI.sub("", line)), cols, (cols, line))

    def test_table_never_exceeds_the_height(self):
        for lines in (10, 24, 40):
            self.assertLess(len(self.render(80, lines)), lines)

    def test_cut_never_ends_on_a_bare_heading(self):
        for lines in range(8, 60):
            last = ANSI.sub("", self.render(80, lines)[-1])
            self.assertRegex(last, r"\d", (lines, last))

    def test_losses_are_red_and_gains_green(self):
        text = "\n".join(self.render(80, 60))
        for m in re.finditer(r"\x1b\[1;(3[12])m\s*([+-])", text):
            self.assertEqual(m.group(1), "32" if m.group(2) == "+" else "31")

    def test_empty_data_is_said_plainly(self):
        with mock.patch.object(self.ws, "movers", return_value={}):
            self.assertIn("No market data", out_of(self.ws.cmd_table))


class Marquee(Base):
    def run_once(self, text):
        with mock.patch.object(self.ws.time, "sleep"), \
                mock.patch.object(self.ws, "term_size", return_value=os.terminal_size((20, 5))):
            return out_of(self.ws.cmd_marquee, "green", "0", text)

    def test_text_scrolls_through(self):
        frames = self.run_once("HELLO").split("\r")
        self.assertTrue(any("HELLO" in f for f in frames))

    def test_cursor_is_shown_again(self):
        out = self.run_once("HELLO")
        self.assertLess(out.index("\x1b[?25l"), out.rindex("\x1b[?25h"))

    def test_frames_fit_the_terminal(self):
        for frame in self.run_once("A LONGER LINE OF TEXT THAN THE TERMINAL").split("\r"):
            self.assertLessEqual(len(ANSI.sub("", frame)), 20)

    def test_control_characters_do_not_reach_the_terminal(self):
        out = self.run_once("A\x1b]0;owned\x07B")
        self.assertNotIn("\x07", out)
        self.assertNotIn("\x1b]", out)

    def test_empty_text_is_an_error(self):
        self.assertEqual(self.ws.cmd_marquee("green", "0", "   "), 1)


class Live(Base):
    """The live code paths, with the network replaced."""
    demo = False

    RSS = ("<rss xmlns:media='http://search.yahoo.com/mrss/'><channel>"
           "<item><title>Good \x1b[31mnews</title><media:thumbnail url='https://8.8.8.8/a.jpg'/></item>"
           "<item><title>Local</title><media:thumbnail url='file:///etc/passwd.jpg'/></item>"
           "<item><title>Script</title><media:content url='javascript:alert(1).jpg'/></item>"
           "<item><title></title></item>"
           "</channel></rss>").replace("\x1b", "&#27;") .encode()

    def test_feed_titles_are_cleaned_and_only_web_pictures_kept(self):
        rss = self.RSS.replace(b"&#27;", b"")
        with mock.patch.object(self.ws, "feed_urls", return_value=["https://8.8.8.8/f"]), \
                mock.patch.object(self.ws, "fetch", return_value=rss):
            items = self.ws.feeds()
        self.assertEqual([t for t, _ in items], ["Good [31mnews", "Local", "Script"])
        self.assertEqual([p for _, p in items], ["https://8.8.8.8/a.jpg", None, None])

    def test_quotes_from_the_api_are_cleaned(self):
        api = {"data": {"STOCKS": {"MostAdvanced": {"table": {"rows": [
            {"symbol": "AB\x1b[2JC", "name": "Evil\x07 Corp", "lastSalePrice": "$1.00",
             "lastSaleChange": "+0.1", "change": "+10%", "deltaIndicator": "up"}]}}}}}
        with mock.patch.object(self.ws, "fetch", return_value=json.dumps(api).encode()):
            row = self.ws.rows("MostAdvanced")[0]
        self.assertNotIn("\x1b", row["symbol"])
        self.assertNotIn("\x07", row["name"])

    def test_broken_api_answer_gives_no_rows(self):
        with mock.patch.object(self.ws, "fetch", return_value=b"<html>busy</html>"):
            self.assertEqual(self.ws.rows("MostAdvanced"), [])

    def test_unreachable_feeds_give_no_headlines(self):
        with mock.patch.object(self.ws, "feed_urls", return_value=["https://8.8.8.8/f"]), \
                mock.patch.object(self.ws, "fetch", side_effect=OSError("down")):
            self.assertEqual(self.ws.feeds(), [])

    def test_feed_list_is_the_newsboat_file(self):
        urls = self.ws.feed_urls()
        self.assertGreaterEqual(len(urls), 5)
        self.assertTrue(all(u.startswith("https://") for u in urls), urls)

    def test_oversized_answer_is_refused(self):
        class Big:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, n): return b"x" * n
        with mock.patch.object(self.ws.OPENER, "open", return_value=Big()):
            with self.assertRaises(ValueError):
                self.ws.fetch("https://8.8.8.8/big")


class Input(Base):
    def events(self, raw):
        return self.ws.parse_input(raw)

    def test_a_click_carries_its_cell(self):
        self.assertEqual(self.events("\x1b[<0;12;5M"), ([("click", 12, 5)], ""))

    def test_the_release_of_the_button_is_not_a_second_click(self):
        self.assertEqual(self.events("\x1b[<0;12;5M\x1b[<0;12;5m")[0], [("click", 12, 5)])

    def test_other_buttons_and_drags_are_ignored(self):
        self.assertEqual(self.events("\x1b[<2;1;1M\x1b[<32;4;4M")[0], [])

    def test_the_wheel_moves_up_and_down(self):
        self.assertEqual(self.events("\x1b[<64;1;1M\x1b[<65;1;1M")[0], [("wheel", -1), ("wheel", 1)])

    def test_arrow_keys_in_both_encodings(self):
        self.assertEqual(self.events("\x1b[A\x1bOB")[0], [("key", "up"), ("key", "down")])

    def test_plain_characters_and_enter(self):
        self.assertEqual(self.events("j3\r")[0], [("key", "j"), ("key", "3"), ("key", "enter")])

    def test_a_sequence_cut_in_half_waits_for_the_rest(self):
        events, rest = self.events("k\x1b[<0;3")
        self.assertEqual(events, [("key", "k")])
        self.assertEqual(self.events(rest + ";7M")[0], [("click", 3, 7)])

    def test_unknown_sequences_are_dropped_not_typed(self):
        self.assertEqual(self.events("\x1b[15~\x1b[?1;2cx")[0], [("key", "x")])


class Selection(Base):
    def test_round_trip(self):
        self.ws.write_selection(symbol="NRDL", span="3m")
        self.assertEqual(self.ws.read_selection(), ("NRDL", "3m"))

    def test_changing_one_part_keeps_the_other(self):
        self.ws.write_selection(symbol="NRDL", span="3m")
        self.ws.write_selection(symbol="HLXQ")
        self.assertEqual(self.ws.read_selection(), ("HLXQ", "3m"))
        self.ws.write_selection(span="1y")
        self.assertEqual(self.ws.read_selection(), ("HLXQ", "1y"))

    def test_nothing_selected_at_first(self):
        self.assertEqual(self.ws.read_selection(), ("", "1d"))

    def test_a_tampered_file_cannot_smuggle_a_path_or_a_span(self):
        with open(self.ws.selection_path(), "w") as f:
            json.dump({"symbol": "../../etc/passwd", "span": "forever"}, f)
        self.assertEqual(self.ws.read_selection(), ("", "1d"))

    def test_garbage_in_the_file_is_no_selection(self):
        with open(self.ws.selection_path(), "w") as f:
            f.write("[1, 2")
        self.assertEqual(self.ws.read_selection(), ("", "1d"))


class Chart(Base):
    def test_plot_has_the_asked_size(self):
        rows = self.ws.plot([1, 5, 2, 8, 3], 30, 6)
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(len(r) == 30 for r in rows))

    def dots(self, rows):
        """Per dot column the set of dot rows that are lit."""
        bits = self.ws.BRAILLE
        cols = [set() for _ in range(len(rows[0]) * 2)]
        for cy, row in enumerate(rows):
            for cx, ch in enumerate(row):
                cell = 0 if ch == " " else ord(ch) - 0x2800
                for dy in range(4):
                    for dx in range(2):
                        if cell & bits[dy][dx]:
                            cols[cx * 2 + dx].add(cy * 4 + dy)
        return cols

    def test_the_line_has_no_gaps(self):
        # neighbouring columns must touch, also across a steep jump: without the
        # vertical fill a sharp move is two dots with nothing between them
        cols = self.dots(self.ws.plot([1, 100, 1, 100, 50, 51], 12, 6))
        self.assertTrue(all(cols), "a column without any dot")
        for left, right in zip(cols, cols[1:]):
            self.assertLessEqual(min(right), max(left) + 1)
            self.assertGreaterEqual(max(right), min(left) - 1)

    def test_few_points_are_joined_by_straight_lines(self):
        rows = self.ws.plot([0, 10], 10, 5)
        heights = []
        for col in range(10):
            heights.append(min(i for i, r in enumerate(rows) if r[col] != " "))
        self.assertEqual(heights, sorted(heights, reverse=True))
        self.assertGreater(len(set(heights)), 2, "two points drawn as a step")

    def test_a_flat_course_does_not_divide_by_zero(self):
        self.assertEqual(len(self.ws.plot([5, 5, 5], 10, 3)), 3)

    def test_chart_fits_the_pane(self):
        data = self.ws.history("NRDL", "1d")
        for cols, lines in ((91, 20), (40, 12), (30, 8), (120, 40)):
            out = self.ws.chart_lines(data, "1d", cols, lines)
            self.assertLessEqual(len(out), lines)
            for line in out:
                self.assertLess(len(ANSI.sub("", line)), cols, (cols, lines, line))

    def test_gain_is_green_and_loss_red(self):
        data = dict(self.ws.history("NRDL", "1d"))
        data["last"], data["reference"] = 110.0, 100.0
        self.assertIn("\x1b[1;32m+10.00  +10.00%", self.ws.chart_lines(data, "1d", 80, 20)[1])
        data["last"] = 90.0
        self.assertIn("\x1b[1;31m-10.00  -10.00%", self.ws.chart_lines(data, "1d", 80, 20)[1])

    def test_the_current_span_is_marked(self):
        data = self.ws.history("NRDL", "3m")
        tabs = self.ws.chart_lines(data, "3m", 80, 20)[2]
        self.assertIn("\x1b[7m 3M \x1b[27m", tabs)
        self.assertEqual(tabs.count("\x1b[7m"), 1)

    def tab_cells(self, line):
        """Per span the 1-based columns its label occupies in a rendered tab line."""
        plain = ANSI.sub("", line)
        return {key: range(plain.index(label) + 1, plain.index(label) + 1 + len(label))
                for key, label, _ in self.ws.SPANS}

    def test_a_click_on_a_tab_names_that_span(self):
        # measured on what is drawn, so the click map cannot drift from the picture
        line = self.ws.chart_lines(self.ws.history("NRDL", "1d"), "1d", 80, 20)[self.ws.TAB_ROW - 1]
        for key, cells in self.tab_cells(line).items():
            for x in cells:
                self.assertEqual(self.ws.tab_at(x, self.ws.TAB_ROW), key, (key, x))

    def test_the_click_area_is_exactly_the_marked_tab(self):
        # the highlighted block is what the eye takes for the button: every cell of
        # it must open the span, the cells left and right of it must not
        data = self.ws.history("NRDL", "1d")
        for key, _, _ in self.ws.SPANS:
            line = self.ws.chart_lines(data, key, 80, 20)[self.ws.TAB_ROW - 1]
            start = len(ANSI.sub("", line[:line.index("\x1b[7m")])) + 1
            block = line[line.index("\x1b[7m") + 4:line.index("\x1b[27m")]
            cells = range(start, start + len(block))
            self.assertEqual([self.ws.tab_at(x, self.ws.TAB_ROW) for x in cells], [key] * len(block), key)
            self.assertNotEqual(self.ws.tab_at(cells[-1] + 1, self.ws.TAB_ROW), key)
            if start > 1:
                self.assertNotEqual(self.ws.tab_at(start - 1, self.ws.TAB_ROW), key)

    def test_a_click_beside_the_tabs_names_none(self):
        line = self.ws.chart_lines(self.ws.history("NRDL", "1d"), "1d", 80, 20)[self.ws.TAB_ROW - 1]
        on_a_tab = {x for cells in self.tab_cells(line).values() for x in cells}
        gaps = [x for x in range(1, 80) if self.ws.tab_at(x, self.ws.TAB_ROW) is None]
        self.assertFalse(on_a_tab & set(gaps))
        self.assertIn(5, gaps)             # between 1D and 1M
        self.assertIn(40, gaps)            # right of the last tab
        for y in (1, 2, 4, 10):
            self.assertIsNone(self.ws.tab_at(2, y))

    def test_the_tabs_sit_on_the_same_line_with_and_without_data(self):
        with_data = self.ws.chart_lines(self.ws.history("NRDL", "1d"), "1d", 80, 20)
        without = self.ws.chart_lines(None, "1d", 80, 20)
        for out in (with_data, without):
            self.assertIn("1D", ANSI.sub("", out[self.ws.TAB_ROW - 1]))

    def test_without_data_it_says_what_to_do(self):
        text = "\n".join(self.ws.chart_lines(None, "1d", 80, 20))
        self.assertIn("Select a stock", text)
        self.ws.write_selection(symbol="NRDL")
        self.assertIn("No chart data", "\n".join(self.ws.chart_lines(None, "1d", 80, 20)))


class DemoHistory(Base):
    def test_it_ends_at_the_quote_in_the_table(self):
        for minute in range(0, 600, 37):
            with mock.patch.object(self.ws.time, "time", return_value=1_800_000_000.0 + 60 * minute):
                row = self.ws.rows("MostActiveByDollarVolume")[0]
                data = self.ws.history(row["symbol"], "1d")
                self.assertAlmostEqual(data["points"][-1], float(row["lastSalePrice"].lstrip("$")), places=6)

    def test_the_day_starts_at_the_previous_close(self):
        data = self.ws.history("NRDL", "1d")
        self.assertAlmostEqual(data["points"][0], data["reference"], places=6)

    def test_every_span_has_its_number_of_points(self):
        self.assertEqual([len(self.ws.history("NRDL", k)["points"]) for k, _, _ in self.ws.SPANS],
                         [390, 22, 64, 252])

    def test_two_reads_in_a_minute_agree(self):
        with mock.patch.object(self.ws.time, "time", return_value=1_800_000_000.0):
            self.assertEqual(self.ws.history("HLXQ", "1m"), self.ws.history("HLXQ", "1m"))

    def test_demo_history_never_fetches(self):
        with mock.patch.object(self.ws, "fetch", side_effect=AssertionError("fetched")):
            self.ws.history("NRDL", "1y")


class LiveHistory(Base):
    demo = False

    def answer(self, chart, **extra):
        data = {"company": "Evil\x1b[2J Corp", "lastSalePrice": "$1,010.50", "previousClose": "$1,000.00",
                "chart": chart}
        data.update(extra)
        return json.dumps({"data": data}).encode()

    def points(self, n=5):
        return [{"y": 1000 + i, "z": {"dateTime": "t%d" % i}} for i in range(n)]

    def test_course_reference_and_labels_are_read(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.answer(self.points())):
            data = self.ws.history("NVDA", "1d")
        self.assertEqual(data["points"], [1000.0, 1001.0, 1002.0, 1003.0, 1004.0])
        self.assertEqual((data["last"], data["reference"]), (1010.5, 1000.0))
        self.assertEqual(data["labels"], ("t0", "t4"))

    def test_names_from_the_api_are_cleaned(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.answer(self.points())):
            self.assertNotIn("\x1b", self.ws.history("NVDA", "1d")["name"])

    def test_longer_spans_compare_with_their_first_day(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.answer(self.points())):
            self.assertEqual(self.ws.history("NVDA", "3m")["reference"], 1000.0)

    def test_longer_spans_ask_for_a_date_range(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.answer(self.points())) as fetch:
            self.ws.history("NVDA", "1m")
        self.assertRegex(fetch.call_args[0][0], r"fromdate=\d{4}-\d\d-\d\d&todate=\d{4}-\d\d-\d\d")

    def test_an_etf_is_found_on_the_second_try(self):
        def fetch(url):
            return self.answer(self.points() if "assetclass=etf" in url else None)
        with mock.patch.object(self.ws, "fetch", side_effect=fetch):
            self.assertEqual(len(self.ws.history("SPY", "1d")["points"]), 5)

    def test_no_chart_at_all_is_none(self):
        with mock.patch.object(self.ws, "fetch", return_value=b"<html>busy</html>"):
            self.assertIsNone(self.ws.history("NVDA", "1d"))

    def test_a_single_point_is_no_chart(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.answer(self.points(1))):
            self.assertIsNone(self.ws.history("NVDA", "1d"))

    def test_the_symbol_cannot_leave_its_place_in_the_url(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.answer(self.points())) as fetch:
            self.ws.history("A/../B?x=1", "1d")
        self.assertIn("/quote/A%2F..%2FB%3Fx%3D1/chart", fetch.call_args[0][0])


class Browse(Base):
    def test_every_quote_row_can_be_selected_and_headings_cannot(self):
        table = self.ws.table_rows(80, 60)
        for text, symbol in table:
            plain = ANSI.sub("", text)
            if symbol:
                self.assertTrue(plain.startswith(symbol[:6]), plain)
            else:
                self.assertNotRegex(plain, r"\d+\.\d\d")

    def test_the_cut_never_ends_on_a_bare_heading(self):
        for lines in range(4, 60):
            self.assertTrue(self.ws.table_rows(80, lines)[-1][1], lines)

    def test_no_row_is_wider_than_the_pane(self):
        for cols in (60, 80, 120):
            for text, _ in self.ws.table_rows(cols, 40):
                self.assertLess(len(ANSI.sub("", text)), cols)

    def test_the_marked_row_keeps_its_background_to_the_end(self):
        # a full reset inside the row would end the highlight after the first column
        for text, symbol in self.ws.table_rows(80, 40):
            if symbol:
                self.assertNotIn("\x1b[0m", text)


class Main(Base):
    def test_unknown_command_is_usage_error(self):
        with mock.patch.object(sys, "stderr", io.StringIO()):
            self.assertEqual(self.ws.main(["wsdata", "bogus"]), 2)

    def test_cachedir_prints_the_cache(self):
        self.assertEqual(out_of(self.ws.main, ["wsdata", "cachedir"]).strip(), self.ws.CACHE)


if __name__ == "__main__":
    unittest.main()
