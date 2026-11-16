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


class Main(Base):
    def test_unknown_command_is_usage_error(self):
        with mock.patch.object(sys, "stderr", io.StringIO()):
            self.assertEqual(self.ws.main(["wsdata", "bogus"]), 2)

    def test_cachedir_prints_the_cache(self):
        self.assertEqual(out_of(self.ws.main, ["wsdata", "cachedir"]).strip(), self.ws.CACHE)


if __name__ == "__main__":
    unittest.main()
