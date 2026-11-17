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

    def offline(request, timeout=15):
        raise OSError("a test must not reach the network: " + request.full_url)
    module.OPENER.open = offline        # tests that need an answer patch fetch or OPENER themselves
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


def png(width, height, pixels, colour=6):
    """A PNG from rows of RGBA tuples, written with filter 0 - the test's own encoder."""
    import struct, zlib
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    raw = b"".join(b"\0" + b"".join(bytes(p[:4] if colour == 6 else p[:3]) for p in row) for row in pixels)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class Logo(Base):
    demo = False
    RED, CLEAR = (200, 0, 0, 255), (0, 0, 0, 0)

    def picture(self):
        # left half red, right half transparent
        return png(8, 8, [[self.RED] * 4 + [self.CLEAR] * 4 for _ in range(8)])

    def test_a_png_is_decoded(self):
        w, h, rows = self.ws.png_pixels(self.picture())
        self.assertEqual((w, h), (8, 8))
        self.assertEqual(rows[3][0], self.RED)
        self.assertEqual(rows[3][7][3], 0)

    def test_rgb_without_alpha_is_decoded(self):
        _, _, rows = self.ws.png_pixels(png(2, 1, [[(1, 2, 3), (4, 5, 6)]], colour=2))
        self.assertEqual(rows[0], [(1, 2, 3, 255), (4, 5, 6, 255)])

    def test_what_is_not_a_png_is_refused(self):
        for data in (b"", b"<html>404</html>", self.picture()[:40]):
            with self.assertRaises(Exception):
                self.ws.png_pixels(data)

    def test_a_picture_larger_than_a_logo_is_refused(self):
        # complete and valid, only wide: decoding it would cost time and memory
        wide = png(2000, 1, [[self.RED] * 2000])
        with self.assertRaises(ValueError):
            self.ws.png_pixels(wide)
        self.assertEqual(self.ws.png_pixels(wide, limit=2000)[0], 2000)

    def test_transparent_pixels_show_the_tile(self):
        grid = self.ws.tile(self.ws.png_pixels(self.picture()), 12)
        self.assertEqual(len(grid), 12)
        self.assertEqual(grid[0][0], self.ws.TILE)            # the margin
        self.assertEqual(grid[6][3], (200, 0, 0))             # the red half
        self.assertEqual(grid[6][8], self.ws.TILE)            # the transparent half

    def test_a_white_logo_gets_a_dark_tile(self):
        white = (255, 255, 255, 255)
        grid = self.ws.tile(self.ws.png_pixels(png(8, 8, [[white] * 4 + [self.CLEAR] * 4 for _ in range(8)])), 12)
        self.assertEqual(grid[0][0], self.ws.TILE_DARK)
        self.assertEqual(grid[6][8], self.ws.TILE_DARK)
        self.assertEqual(grid[6][3], (255, 255, 255))

    def test_a_logo_with_a_white_ground_of_its_own_keeps_the_light_tile(self):
        white, black = (255, 255, 255, 255), (0, 0, 0, 255)
        rows = [[white] * 8 for _ in range(8)]
        rows[4][4] = black
        self.assertEqual(self.ws.tile(self.ws.png_pixels(png(8, 8, rows)), 12)[0][0], self.ws.TILE)

    def test_the_pane_is_drawn_with_half_blocks_and_fits(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.picture()):
            lines = self.ws.logo_lines("NVDA", 44, 17)
        self.assertLessEqual(len(lines), 17)
        blocks = [ANSI.sub("", l) for l in lines if "\u2580" in l]
        self.assertEqual(len(blocks), 15)
        for b in blocks:
            self.assertLess(len(b), 44)
            self.assertEqual(len(b.strip()), 30)
        self.assertIn("NVDA", ANSI.sub("", lines[-1]))
        self.assertTrue(all(l.endswith("\033[0m") for l in lines if "\u2580" in l))

    def test_a_small_pane_gets_a_small_logo(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.picture()):
            lines = self.ws.logo_lines("NVDA", 20, 8)
        self.assertLessEqual(len(lines), 8)
        self.assertTrue(all(len(ANSI.sub("", l)) < 20 for l in lines))

    def test_no_logo_means_a_monogram_and_one_question_per_source(self):
        with mock.patch.object(self.ws, "fetch", return_value=b"<html>not found</html>") as fetch:
            first = self.ws.logo_grid("ZZQQ", 20)
            self.ws.logo_grid("ZZQQ", 20)
        self.assertEqual(fetch.call_count, len(self.ws.LOGO_URLS))
        self.assertEqual(first, self.ws.monogram("ZZQQ", 20))
        self.assertIn((255, 255, 255), [px for row in first for px in row])
        self.assertFalse([f for f in os.listdir(self.ws.CACHE) if f.startswith("logo")])

    def test_the_second_source_is_asked_when_the_first_has_nothing(self):
        answers = [b"nope", self.picture()]
        with mock.patch.object(self.ws, "fetch", side_effect=lambda *a, **k: answers.pop(0)):
            grid = self.ws.logo_grid("NVDA", 12)
        self.assertEqual(grid[6][3], (200, 0, 0))

    def test_a_logo_is_fetched_once(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.picture()) as fetch:
            self.ws.logo_grid("NVDA", 12)
            self.ws.logo_grid("NVDA", 12)
        self.assertEqual(fetch.call_count, 1)

    def test_only_a_symbol_reaches_the_address(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.picture()) as fetch:
            for bad in ("../../etc", "A B", "x?y=1", "", "A/B"):
                self.ws.logo_grid(bad, 12)
        fetch.assert_not_called()

    def test_monograms_differ_by_symbol(self):
        self.assertNotEqual(self.ws.monogram("AB", 20), self.ws.monogram("CD", 20))

    def test_colours_stay_inside_the_256_palette(self):
        for rgb in ((0, 0, 0), (255, 255, 255), (118, 185, 0), (128, 128, 128), (255, 0, 255), (3, 3, 3)):
            self.assertTrue(16 <= self.ws.colour256(rgb) <= 255)
        self.assertEqual(self.ws.colour256((255, 255, 255)), 231)
        self.assertEqual(self.ws.colour256((0, 0, 0)), 16)


def unsixel(data):
    """The test's own sixel decoder: {(x, y): (r, g, b) in percent} and the declared size."""
    body = re.fullmatch(r'\x1bP[0-9;]*q"1;1;(\d+);(\d+)(.*)\x1b\\', data, re.S)
    width, height, rest = int(body.group(1)), int(body.group(2)), body.group(3)
    palette, pixels, x, y, colour = {}, {}, 0, 0, None
    for m in re.finditer(r"#(\d+);2;(\d+);(\d+);(\d+)|#(\d+)|!(\d+)(.)|([$-])|([?-~])", rest):
        if m.group(1):
            palette[int(m.group(1))] = tuple(int(m.group(i)) for i in (2, 3, 4))
        elif m.group(5):
            colour = int(m.group(5))
        elif m.group(8) == "$":
            x = 0
        elif m.group(8) == "-":
            x, y = 0, y + 6
        else:
            count, ch = (int(m.group(6)), m.group(7)) if m.group(6) else (1, m.group(9))
            for _ in range(count):
                for bit in range(6):
                    if (ord(ch) - 63) >> bit & 1:
                        pixels[(x, y + bit)] = palette[colour]
                x += 1
    return width, height, pixels


class Pixels(Base):
    demo = False

    def grid(self):
        # 20 x 15: red left, blue right, one green pixel
        g = [[(248, 0, 0)] * 10 + [(0, 0, 248)] * 10 for _ in range(15)]
        g[7][3] = (0, 248, 0)
        return g

    def test_a_sixel_picture_decodes_to_the_grid(self):
        width, height, pixels = unsixel(self.ws.sixel(self.grid()))
        self.assertEqual((width, height), (20, 15))
        self.assertEqual(len(pixels), 300, "every pixel is set exactly where it belongs")
        near = lambda a, b: all(abs(x - y) <= 2 for x, y in zip(a, b))
        self.assertTrue(near(pixels[(0, 0)], (98, 0, 0)))
        self.assertTrue(near(pixels[(19, 14)], (0, 0, 98)))
        self.assertTrue(near(pixels[(3, 7)], (0, 98, 0)))
        self.assertTrue(near(pixels[(4, 7)], (98, 0, 0)))

    def test_a_sixel_picture_is_all_printable(self):
        data = self.ws.sixel(self.grid())
        self.assertTrue(data.startswith("\033P") and data.endswith("\033\\"))
        self.assertNotRegex(data[2:-2], r"[^ -~]")

    def test_more_colours_than_registers_still_fit(self):
        grid = [[(x * 8 % 256, y * 8 % 256, (x + y) * 4 % 256) for x in range(64)] for y in range(36)]
        data = self.ws.sixel(grid)
        registers = {int(n) for n in re.findall(r"#(\d+);2;", data)}
        self.assertLessEqual(len(registers), 255)
        self.assertEqual({int(n) for n in re.findall(r"[$-]#(\d+)", "-" + data.split("q", 1)[1])} - registers, set())
        self.assertEqual(len(unsixel(data)[2]), 64 * 36)

    def test_palette_pngs_with_four_bits_are_decoded(self):
        import struct, zlib
        def chunk(kind, body):
            return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        # 3 x 2, palette of three colours, four bits a pixel: 0 1 2 / 2 1 0
        raw = b"\0" + bytes([0x01, 0x20]) + b"\0" + bytes([0x21, 0x00])
        data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 3, 2, 4, 3, 0, 0, 0))
                + chunk(b"PLTE", bytes([255, 0, 0, 0, 255, 0, 0, 0, 255])) + chunk(b"IDAT", zlib.compress(raw))
                + chunk(b"IEND", b""))
        _, _, rows = self.ws.png_pixels(data)
        self.assertEqual([px[:3] for px in rows[0]], [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        self.assertEqual([px[:3] for px in rows[1]], [(0, 0, 255), (0, 255, 0), (255, 0, 0)])

    def test_a_small_logo_is_enlarged_smoothly(self):
        black, white = (0, 0, 0, 255), (255, 255, 255, 255)
        grid = self.ws.tile((2, 2, [[black, white], [black, white]]), 40, margin=0)
        self.assertEqual(grid[20][0], (0, 0, 0))
        self.assertEqual(grid[20][39], (255, 255, 255))
        middle = grid[20][20][0]
        self.assertTrue(60 < middle < 200, "a blend between the two, not a hard edge: %d" % middle)
        self.assertEqual(sorted(px[0] for px in grid[20]), [px[0] for px in grid[20]])

    def clients(self, *lines):
        def fake(cmd, **kw):
            return mock.Mock(stdout="$1\n" if cmd[1] == "display-message" else "".join(l + "\n" for l in lines))
        return mock.patch.object(self.ws.subprocess, "run", side_effect=fake)

    def mode(self, *lines, **env):
        base = {"TMUX": "/tmp/x,1,0", "TMUX_PANE": "%1", "COLORTERM": "", "WALLSTREET_LOGO": "", "TERM_PROGRAM": ""}
        with mock.patch.dict(os.environ, dict(base, **env)), self.clients(*lines):
            return self.ws.graphics()

    def test_pixels_when_every_terminal_can(self):
        self.assertEqual(self.mode("RGB,sixel,title|14|34"), ("sixel", 14, 34))
        self.assertEqual(self.mode("RGB,sixel|14|34", "sixel|8|16"), ("sixel", 8, 16))

    def test_characters_when_one_terminal_cannot(self):
        # tmux shows such a terminal a placeholder text instead of the picture
        self.assertEqual(self.mode("RGB,sixel|14|34", "RGB,title|8|16"), ("rgb",))
        self.assertEqual(self.mode("256,title|8|16"), ("256",))

    def test_characters_without_a_cell_size_or_a_terminal(self):
        self.assertEqual(self.mode("RGB,sixel|0|0"), ("rgb",))
        self.assertEqual(self.mode(), ("256",))

    def test_the_wish_for_characters_wins(self):
        self.assertEqual(self.mode("RGB,sixel|14|34", WALLSTREET_LOGO="blocks"), ("rgb",))

    def test_outside_tmux_only_known_terminals_get_pixels(self):
        with mock.patch.object(self.ws, "cell_pixels", return_value=(9, 18)):
            self.assertEqual(self.mode(TMUX="", TERM_PROGRAM="iTerm.app"), ("sixel", 9, 18))
            self.assertEqual(self.mode(TMUX="", TERM_PROGRAM="Apple_Terminal", COLORTERM="truecolor"), ("rgb",))
        with mock.patch.object(self.ws, "cell_pixels", return_value=(0, 0)):
            self.assertEqual(self.mode(TMUX="", TERM_PROGRAM="iTerm.app"), ("256",))

    def test_the_picture_fills_whole_cells_inside_the_pane(self):
        with mock.patch.object(self.ws, "fetch", return_value=png(4, 4, [[(200, 0, 0, 255)] * 4] * 4)):
            screen = self.ws.logo_screen("NVDA", 44, 17, ("sixel", 14, 34))
        row, col = map(int, re.search(r"\x1b\[J\x1b\[(\d+);(\d+)H\x1bP", screen).groups())
        width, height, _ = unsixel(re.search(r"\x1bP.*?\x1b\\", screen, re.S).group())
        self.assertEqual(width, height)
        self.assertEqual(height % 34, 0)
        self.assertLessEqual(row - 1 + height // 34 + 2, 17)
        self.assertLessEqual(col - 1 + -(-width // 14), 44)
        self.assertGreaterEqual(height, 400, "real pixels, not thirty of them")
        self.assertIn("NVDA", ANSI.sub("", screen.split("\x1b\\")[-1]))

    def test_a_narrow_pane_gets_a_picture_of_whole_cells_too(self):
        # 28 usable columns of 14 px are 392 px: not a multiple of the 34 px a line is high
        with mock.patch.object(self.ws, "fetch", return_value=png(4, 4, [[(200, 0, 0, 255)] * 4] * 4)):
            screen = self.ws.logo_screen("NVDA", 30, 17, ("sixel", 14, 34))
        width, height, _ = unsixel(re.search(r"\x1bP.*?\x1b\\", screen, re.S).group())
        self.assertEqual((width, height), (374, 374))

    def test_true_colour_blocks_where_pixels_are_not_possible(self):
        with mock.patch.object(self.ws, "fetch", return_value=png(4, 4, [[(118, 185, 0, 255)] * 4] * 4)):
            rgb = self.ws.logo_screen("NVDA", 44, 17, ("rgb",))
            low = self.ws.logo_screen("NVDA", 44, 17, ("256",))
        self.assertIn("38;2;118;185;0", rgb)
        self.assertNotIn("38;2;", low)
        self.assertNotIn("\x1bP", rgb + low)


class LogoDemo(Base):
    def test_demo_mode_never_asks_the_network(self):
        with mock.patch.object(self.ws, "fetch") as fetch:
            lines = self.ws.logo_lines("MRNOW", 44, 17)
        fetch.assert_not_called()
        self.assertTrue(any("\u2580" in l for l in lines))


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
        self.assertIn("\x1b[1;32m +10.00  +10.00%", self.ws.chart_lines(data, "1d", 80, 20)[1])
        data["last"] = 90.0
        self.assertIn("\x1b[1;31m -10.00  -10.00%", self.ws.chart_lines(data, "1d", 80, 20)[1])

    def test_the_current_span_is_marked(self):
        data = self.ws.history("NRDL", "3m")
        tabs = self.ws.chart_lines(data, "3m", 80, 20)[2]
        self.assertIn("\x1b[7m 3M \x1b[27m", tabs)
        self.assertEqual(tabs.count("\x1b[7m"), 1)

    def tab_cells(self, line):
        """Per span the 1-based columns its label occupies in a rendered tab line."""
        plain = ANSI.sub("", line)
        return {key: range(plain.index(label) + 1, plain.index(label) + 1 + len(label))
                for key, label in self.ws.SPANS}

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
        for key, _ in self.ws.SPANS:
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
        self.assertIn(60, gaps)            # right of the last tab
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
        with mock.patch.object(self.ws.time, "time", return_value=1_800_000_000.0):   # 2027-01-15
            counts = {k: len(self.ws.history("NRDL", k)["points"]) for k, _ in self.ws.SPANS}
        self.assertEqual(counts, {"1d": 390, "1m": 21, "3m": 63, "ytd": 9, "1y": 252})

    def test_two_reads_in_a_minute_agree(self):
        with mock.patch.object(self.ws.time, "time", return_value=1_800_000_000.0):
            self.assertEqual(self.ws.history("HLXQ", "1m"), self.ws.history("HLXQ", "1m"))

    def test_demo_history_never_fetches(self):
        with mock.patch.object(self.ws, "fetch", side_effect=AssertionError("fetched")):
            self.ws.history("NRDL", "1y")


class LiveHistory(Base):
    """The live course, with the two Nasdaq answers (chart and info) replaced."""
    demo = False

    def minute(self, hour, minute, value):
        x = (hour * 3600 + minute * 60) * 1000 + 1_794_787_200_000        # a day, New York time as UTC
        return {"x": x, "y": value, "z": {"dateTime": "%d:%02d" % (hour, minute)}}

    def day(self):
        return ([self.minute(4, m, 162.0 + m / 100) for m in (0, 1, 2)]          # pre-market
                + [self.minute(9, 30, 159.3), self.minute(12, 0, 158.0), self.minute(16, 0, 156.15)]
                + [self.minute(17, 0, 155.9), self.minute(18, 30, 155.8)])        # after hours

    def info(self, after_hours=True):
        official = {"lastSalePrice": "$156.14", "netChange": "-6.71", "percentageChange": "-4.12%"}
        late = {"lastSalePrice": "$155.80", "netChange": "-0.34", "percentageChange": "-0.22%"}
        return {"primaryData": late if after_hours else official,
                "secondaryData": official if after_hours else None,
                "marketStatus": "After-Hours" if after_hours else "Open"}

    def serve(self, chart=None, info=None, etf_only=False):
        chart = self.day() if chart is None else chart
        info = self.info() if info is None else info

        def fetch(url):
            if etf_only and "assetclass=stocks" in url:
                return json.dumps({"data": None}).encode()
            if "/info?" in url:
                return json.dumps({"data": info}).encode()
            # previousClose is what the API really sends there: a figure that is not yesterday's close
            return json.dumps({"data": {"company": "Evil\x1b[2J Corp", "lastSalePrice": "$155.80",
                                         "previousClose": "$166.19", "chart": chart}}).encode()
        return mock.patch.object(self.ws, "fetch", side_effect=fetch)

    def test_the_day_is_the_regular_session_not_the_pre_market(self):
        with self.serve():
            data = self.ws.history("NVDA", "1d")
        self.assertEqual(data["points"], [159.3, 158.0, 156.15, 155.9, 155.8])
        self.assertEqual(data["labels"], ("9:30", "18:30"))

    def test_after_hours_trading_is_marked_as_outside_the_session(self):
        with self.serve():
            self.assertEqual(self.ws.history("NVDA", "1d")["dim_from"], 3)

    def test_the_result_of_the_day_is_the_close_against_yesterdays_close(self):
        # not the after-hours price, and not the previousClose of the chart answer
        with self.serve():
            data = self.ws.history("NVDA", "1d")
        self.assertEqual(data["last"], 156.14)
        self.assertAlmostEqual(data["reference"], 162.85, places=6)
        self.assertEqual(data["extended"], {"last": 155.8, "change": -0.34, "pct": -0.22, "label": "after-hours"})

    def test_during_the_session_there_is_no_extended_quote(self):
        chart = self.day()[:5]
        with self.serve(chart=chart, info=self.info(after_hours=False)):
            data = self.ws.history("NVDA", "1d")
        self.assertIsNone(data["extended"])
        self.assertIsNone(data["dim_from"])
        self.assertAlmostEqual(data["reference"], 162.85, places=6)

    def test_before_the_bell_the_pre_market_is_all_there_is(self):
        with self.serve(chart=self.day()[:3]):
            data = self.ws.history("NVDA", "1d")
        self.assertEqual(len(data["points"]), 3)
        self.assertEqual(data["dim_from"], 0)

    def test_without_a_quote_the_course_comes_without_a_verdict(self):
        with self.serve(info={"primaryData": None}):
            data = self.ws.history("NVDA", "1d")
        self.assertIsNone(data["reference"])
        self.assertEqual(data["last"], 156.15)                 # the last price of the session
        header = ANSI.sub("", self.ws.chart_lines(data, "1d", 80, 20)[1])
        self.assertEqual(header.strip(), "156.15")

    def test_names_from_the_api_are_cleaned(self):
        with self.serve():
            self.assertNotIn("\x1b", self.ws.history("NVDA", "1d")["name"])

    def daily(self, last_label):
        return [{"y": 100.0 + i, "z": {"dateTime": label}}
                for i, label in enumerate(("10/01/2026", "10/02/2026", last_label))]

    def test_longer_spans_compare_with_their_first_day(self):
        with self.serve(chart=self.daily("11/13/2026")):
            self.assertEqual(self.ws.history("NVDA", "3m")["reference"], 100.0)

    def test_today_is_added_to_the_daily_closes(self):
        with mock.patch.object(self.ws.time, "time", return_value=1_794_870_000.0), \
                self.serve(chart=self.daily("11/13/2026")):                # the 16th in New York
            data = self.ws.history("NVDA", "1m")
        self.assertEqual(data["points"], [100.0, 101.0, 102.0, 156.14])
        self.assertEqual(data["labels"], ("10/01/2026", "11/16/2026"))
        self.assertEqual(data["last"], 156.14)

    def test_today_is_not_added_twice(self):
        with mock.patch.object(self.ws.time, "time", return_value=1_794_870_000.0), \
                self.serve(chart=self.daily("11/16/2026")):
            data = self.ws.history("NVDA", "1m")
        self.assertEqual(len(data["points"]), 3)

    def test_longer_spans_ask_for_a_date_range(self):
        with self.serve(chart=self.daily("11/13/2026")) as fetch:
            self.ws.history("NVDA", "1m")
        self.assertTrue(any(re.search(r"fromdate=\d{4}-\d\d-\d\d&todate=\d{4}-\d\d-\d\d", c[0][0])
                            for c in fetch.call_args_list))

    def test_the_year_to_date_starts_on_new_years_day(self):
        with mock.patch.object(self.ws.time, "time", return_value=1_794_870_000.0), \
                self.serve(chart=self.daily("11/13/2026")) as fetch:
            self.ws.history("NVDA", "ytd")
        self.assertTrue(any("fromdate=2026-01-01&" in c[0][0] for c in fetch.call_args_list))

    def test_an_etf_is_found_on_the_second_try(self):
        with self.serve(etf_only=True):
            self.assertEqual(len(self.ws.history("SPY", "1d")["points"]), 5)

    def test_no_chart_at_all_is_none(self):
        with mock.patch.object(self.ws, "fetch", return_value=b"<html>busy</html>"):
            self.assertIsNone(self.ws.history("NVDA", "1d"))
            self.assertIsNone(self.ws.history("NVDA", "1y"))

    def test_a_single_point_is_no_chart(self):
        with self.serve(chart=self.day()[3:4]):
            self.assertIsNone(self.ws.history("NVDA", "1d"))

    def test_the_symbol_cannot_leave_its_place_in_the_url(self):
        with self.serve() as fetch:
            self.ws.history("A/../B?x=1", "1d")
        for call in fetch.call_args_list:
            self.assertIn("/quote/A%2F..%2FB%3Fx%3D1/", call[0][0])


class DayChart(Base):
    """How the trading day is drawn."""
    def data(self, **extra):
        data = dict(self.ws.history("NRDL", "1d"))
        data.update(points=[100.0, 98.0, 97.0, 96.0, 95.5, 95.0], last=97.0, reference=104.0,
                    reference_line=True, dim_from=3,
                    extended={"label": "after-hours", "last": 95.0, "change": -2.0, "pct": -2.06})
        data.update(extra)
        return data

    def test_the_header_names_the_session_and_the_late_trade(self):
        header = ANSI.sub("", self.ws.chart_lines(self.data(), "1d", 100, 20)[1])
        self.assertEqual(header, "97.00 -7.00  -6.73%  after-hours 95.00 -2.00 (-2.06%)")

    def test_the_late_trade_is_dropped_before_the_line_gets_too_long(self):
        header = ANSI.sub("", self.ws.chart_lines(self.data(), "1d", 34, 20)[1])
        self.assertEqual(header, "97.00 -7.00  -6.73%")

    def test_the_previous_close_is_on_the_axis_and_drawn_as_a_line(self):
        out = self.ws.chart_lines(self.data(), "1d", 80, 20)
        marked = [l for l in out if "┈" in l]
        self.assertEqual(len(marked), 1)
        self.assertTrue(ANSI.sub("", marked[0]).rstrip().endswith("104.00"))
        self.assertEqual(out.index(marked[0]), 3, "the reference is the highest value: top row")

    def test_trading_after_the_close_is_grey(self):
        rows = self.ws.chart_lines(self.data(reference_line=False), "1d", 80, 20)[3:-1]
        coloured = "".join(re.findall(r"\x1b\[31m([^\x1b]*)", r)[0] for r in rows)
        grey = "".join(re.findall(r"\x1b\[90m([^\x1b]*)", r)[0] for r in rows)
        self.assertTrue(coloured.strip() and grey.strip())
        self.assertEqual({len(re.findall(r"\x1b\[31m([^\x1b]*)", r)[0]) for r in rows}, {36})

    def test_longer_spans_have_no_reference_line(self):
        out = self.ws.chart_lines(self.ws.history("NRDL", "1y"), "1y", 80, 20)
        self.assertFalse([l for l in out if "┈" in l])


class Browse(Base):
    def test_every_quote_row_can_be_selected_and_headings_cannot(self):
        table = self.ws.table_rows(80, 60)
        for text, symbol, _ in table:
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
            for text, _, _ in self.ws.table_rows(cols, 40):
                self.assertLess(len(ANSI.sub("", text)), cols)

    def test_the_marked_row_keeps_its_background_to_the_end(self):
        # a full reset inside the row would end the highlight after the first column
        for text, symbol, _ in self.ws.table_rows(80, 40):
            if symbol:
                self.assertNotIn("\x1b[0m", text)


class Keys(Base):
    def test_backspace_in_both_encodings(self):
        self.assertEqual(self.ws.parse_input("\x7f\x08")[0], [("key", "backspace"), ("key", "backspace")])

    def test_the_delete_key(self):
        self.assertEqual(self.ws.parse_input("\x1b[3~x")[0], [("key", "delete"), ("key", "x")])

    def test_a_lone_escape_waits_while_more_may_come(self):
        self.assertEqual(self.ws.parse_input("\x1b"), ([], "\x1b"))

    def test_a_lone_escape_is_the_key_once_nothing_follows(self):
        self.assertEqual(self.ws.parse_input("\x1b", final=True), ([("key", "escape")], ""))

    def test_final_does_not_break_a_sequence_that_is_under_way(self):
        self.assertEqual(self.ws.parse_input("\x1b[<0;3", final=True), ([], "\x1b[<0;3"))


class Watchlist(Base):
    def test_a_watched_stock_comes_first(self):
        self.ws.watch("NRDL", "Nordlicht Robotics AG")
        self.ws.watch("HLXQ", "Helix Quantum Corp.")
        self.assertEqual([s for s, _ in self.ws.read_watchlist()], ["HLXQ", "NRDL"])

    def test_watching_twice_moves_it_up_instead_of_doubling_it(self):
        for symbol in ("NRDL", "HLXQ", "NRDL"):
            self.ws.watch(symbol, symbol)
        self.assertEqual([s for s, _ in self.ws.read_watchlist()], ["NRDL", "HLXQ"])

    def test_unwatch_removes_only_that_one(self):
        self.ws.watch("NRDL", "a")
        self.ws.watch("HLXQ", "b")
        self.ws.unwatch("NRDL")
        self.assertEqual(self.ws.read_watchlist(), [("HLXQ", "b")])

    def test_the_list_is_capped(self):
        for i in range(30):
            self.ws.watch("S%d" % i, "n")
        self.assertEqual(len(self.ws.read_watchlist()), self.ws.WATCH_MAX)
        self.assertEqual(self.ws.read_watchlist()[0][0], "S29")

    def test_a_symbol_that_is_none_is_not_stored(self):
        self.ws.watch("../../etc", "x")
        self.ws.watch("", "x")
        self.assertEqual(self.ws.read_watchlist(), [])

    def test_a_tampered_file_is_cleaned_on_reading(self):
        with open(self.ws.watchlist_path(), "w") as f:
            json.dump([{"symbol": "OK", "name": "fine\x1b[2J"}, {"symbol": "a b/c", "name": "x"},
                       {"symbol": "OK", "name": "twice"}, "garbage"], f)
        self.assertEqual(self.ws.read_watchlist(), [])            # one bad entry spoils the file
        with open(self.ws.watchlist_path(), "w") as f:
            json.dump([{"symbol": "OK", "name": "fine\x1b[2J"}, {"symbol": "a b/c", "name": "x"},
                       {"symbol": "OK", "name": "twice"}], f)
        got = self.ws.read_watchlist()
        self.assertEqual([s for s, _ in got], ["OK"])
        self.assertNotIn("\x1b", got[0][1])

    def test_the_watchlist_is_the_first_section_of_the_table(self):
        self.ws.watch("KRYO", "Kryon Semiconductor")
        table = self.ws.table_rows(80, 60)
        self.assertEqual(ANSI.sub("", table[0][0]), "WATCHLIST")
        self.assertEqual((table[2][1], table[2][2]), ("KRYO", "watch"))
        self.assertRegex(ANSI.sub("", table[2][0]), r"KRYO +Kryon Semiconductor +\d+\.\d\d +[+-]\d")

    def test_without_watched_stocks_there_is_no_empty_section(self):
        self.assertNotIn("WATCHLIST", [ANSI.sub("", t) for t, _, _ in self.ws.table_rows(80, 60)])

    def test_the_hint_offers_removal_only_on_a_watchlist_row(self):
        self.ws.watch("KRYO", "Kryon Semiconductor")
        table = self.ws.table_rows(80, 60)
        on = ANSI.sub("", self.ws.table_view(table, 2, 80, 30)[-1])
        off = ANSI.sub("", self.ws.table_view(table, 6, 80, 30)[-1])
        self.assertIn("d remove", on)
        self.assertNotIn("d remove", off)
        self.assertIn("/ search", off)

    def test_the_table_view_fills_the_pane_and_no_more(self):
        table = self.ws.table_rows(80, 28)
        for lines in (10, 30):
            view = self.ws.table_view(self.ws.table_rows(80, lines - 2), 2, 80, lines)
            self.assertEqual(len(view), lines)


class DemoSearch(Base):
    def test_symbol_and_name_are_searched(self):
        self.assertEqual([r["symbol"] for r in self.ws.search("kry")], ["KRYO"])
        self.assertEqual([r["symbol"] for r in self.ws.search("airlines")], ["ZPHR"])

    def test_a_symbol_that_starts_with_the_query_comes_first(self):
        hits = [r["symbol"] for r in self.ws.search("m")]
        starts = [h.startswith("M") for h in hits]
        self.assertEqual(starts, sorted(starts, reverse=True))

    def test_an_empty_query_finds_nothing_and_asks_nobody(self):
        with mock.patch.object(self.ws, "fetch", side_effect=AssertionError("fetched")):
            self.assertEqual(self.ws.search("   "), [])
            self.assertEqual(self.ws.search("zzzz"), [])

    def test_the_view_fits_the_pane(self):
        results = self.ws.search("a")
        for cols, lines in ((80, 38), (50, 12), (120, 8)):
            view = self.ws.search_lines("a", results, 0, cols, lines)
            self.assertLessEqual(len(view), lines)
            for line in view:
                self.assertLess(len(ANSI.sub("", line)), cols, (cols, line))

    def test_a_result_sits_where_a_click_looks_for_it(self):
        # cmd_browse maps a click on line y to result y - 3
        results = self.ws.search("a")
        view = [ANSI.sub("", l) for l in self.ws.search_lines("a", results, 0, 80, 30)]
        for i, r in enumerate(results):
            self.assertTrue(view[i + 2].startswith(r["symbol"][:6]), (i, view[i + 2]))

    def test_the_view_says_what_is_going_on(self):
        text = lambda *a, **k: "\n".join(ANSI.sub("", l) for l in self.ws.search_lines(*a, **k))
        self.assertIn("Type a name or a symbol.", text("", [], 0, 80, 20))
        self.assertIn("searching ...", text("ab", [], 0, 80, 20, waiting=True))
        self.assertIn('Nothing found for "ab".', text("ab", [], 0, 80, 20))


class LiveSearch(Base):
    demo = False

    def answer(self, *items):
        return json.dumps({"data": [dict({"exchange": "NYSE"}, **i) for i in items]}).encode()

    def test_only_what_has_a_course_is_offered(self):
        answer = self.answer({"symbol": "TSLA", "name": "Tesla", "asset": "STOCKS"},
                             {"symbol": "BMBVGXX", "name": "A note linked to Tesla", "asset": "MUTUALFUNDS"},
                             {"symbol": "TSLP", "name": "A fund", "asset": "ETF"},
                             {"symbol": "X Y", "name": "broken", "asset": "STOCKS"})
        with mock.patch.object(self.ws, "fetch", return_value=answer):
            self.assertEqual([r["symbol"] for r in self.ws.search("tesla")], ["TSLA", "TSLP"])

    def test_names_from_the_api_are_cleaned(self):
        answer = self.answer({"symbol": "EVIL", "name": "Evil\x1b[2J Corp\x07", "asset": "STOCKS"})
        with mock.patch.object(self.ws, "fetch", return_value=answer):
            name = self.ws.search("evil")[0]["name"]
        self.assertNotIn("\x1b", name)
        self.assertNotIn("\x07", name)

    def test_the_query_cannot_leave_its_place_in_the_url(self):
        with mock.patch.object(self.ws, "fetch", return_value=self.answer()) as fetch:
            self.ws.search("a&b=c /../x")
        urls = [c[0][0] for c in fetch.call_args_list]
        self.assertTrue(urls[0].endswith("?search=a%26b%3Dc%20%2F..%2Fx"))
        self.assertTrue(urls[1].endswith("&q=a%26b%3Dc%20%2F..%2Fx"))
        for url in urls[1:]:                    # the spellings tried at the second source
            self.assertRegex(url, r"&q=[A-Za-z0-9%.-]+$")

    def test_a_broken_answer_finds_nothing(self):
        for raw in (b"<html>busy</html>", b'{"data": null}', b'{"data": ["x", 3]}'):
            with tempfile.TemporaryDirectory() as tmp:
                ws = load(False, tmp)
                with mock.patch.object(ws, "fetch", return_value=raw):
                    self.assertEqual(ws.search("abc"), [])

    def test_at_most_ten_results(self):
        answer = self.answer(*[{"symbol": "S%d" % i, "name": "n", "asset": "STOCKS"} for i in range(25)])
        with mock.patch.object(self.ws, "fetch", return_value=answer):
            self.assertEqual(len(self.ws.search("s")), 10)

    def test_the_watchlist_shows_the_days_quote(self):
        info = {"data": {"primaryData": {"lastSalePrice": "$35.84", "netChange": "-0.78", "percentageChange": "-2.13%"},
                         "secondaryData": None}}
        self.ws.watch("DB", "Deutsche Bank AG")
        with mock.patch.object(self.ws, "fetch", return_value=json.dumps(info).encode()):
            row = self.ws.watch_rows()[0]
        self.assertEqual((row["lastSalePrice"], row["lastSaleChange"], row["change"], row["deltaIndicator"]),
                         ("35.84", "-0.78", "-2.13%", "down"))

    def test_a_watched_stock_without_a_quote_still_has_its_row(self):
        self.ws.watch("DB", "Deutsche Bank AG")
        with mock.patch.object(self.ws, "fetch", side_effect=OSError("down")):
            self.assertEqual(self.ws.watch_rows()[0]["symbol"], "DB")


class Main(Base):
    def test_unknown_command_is_usage_error(self):
        with mock.patch.object(sys, "stderr", io.StringIO()):
            self.assertEqual(self.ws.main(["wsdata", "bogus"]), 2)

    def test_cachedir_prints_the_cache(self):
        self.assertEqual(out_of(self.ws.main, ["wsdata", "cachedir"]).strip(), self.ws.CACHE)


if __name__ == "__main__":
    unittest.main()


class Elsewhere(Base):
    """Stocks that are not listed in the US come from Lang & Schwarz and are known by ISIN."""
    demo = False
    VW, MB = "DE0007664039", "DE0007100000"
    FOUND = [{"instrumentId": 34304, "displayname": "VOLKSWAGEN AG VORZUGSAKTIEN", "isin": VW, "wkn": 766403,
              "categorySymbol": "STK"},
             {"instrumentId": 685824, "displayname": "VOLKSWAGEN INTL18/UND.FLR", "isin": "XS1799939027",
              "wkn": "A192QF", "categorySymbol": "BND"},
             {"instrumentId": 7, "displayname": "Evil\x1b[2J AG", "isin": "DE000EVIL007", "wkn": "EVIL07",
              "categorySymbol": "STK"},
             {"instrumentId": 8, "displayname": "no isin", "isin": "../../etc", "wkn": 1, "categorySymbol": "STK"},
             "rubbish"]
    DAY = 1794812400000        # 2026-11-16 08:00 in Berlin

    def net(self, intraday=None, history=None, previous=67.31, nasdaq=()):
        def answer(url, timeout=15):
            if "api.nasdaq.com/api/autocomplete" in url:
                return json.dumps({"data": list(nasdaq)}).encode()
            if "instrument/search" in url:
                return json.dumps(self.FOUND).encode()
            if "series=intraday" in url:
                points = intraday if intraday is not None else [[self.DAY + i * 60000, 67.0 + i / 100] for i in range(60)]
                return json.dumps({"info": {"plotlines": [{"id": "previousDay", "value": previous}]},
                                   "series": {"intraday": {"data": points}}}).encode()
            if "series=history" in url:
                points = history if history is not None else [[self.DAY - (400 - i) * 86400000, 50.0 + i / 10] for i in range(400)]
                return json.dumps({"info": {}, "series": {"history": {"data": points}}}).encode()
            raise OSError("unexpected " + url)
        return mock.patch.object(self.ws, "fetch", side_effect=answer)

    def test_an_isin_is_not_a_ticker(self):
        for symbol in ("AAPL", "BRK.B", "MRNOW", "766403", "", "DE00076640390", "de0007664039"):
            self.assertFalse(self.ws.is_isin(symbol), symbol)
        self.assertTrue(self.ws.is_isin(self.VW))
        self.assertTrue(self.ws.SYMBOL.fullmatch(self.VW), "it must pass as a symbol everywhere")

    def test_volkswagen_is_found_although_nasdaq_knows_nothing(self):
        with self.net():
            found = self.ws.search("volkswagen")
        self.assertEqual(found[0], {"symbol": self.VW, "label": "766403", "name": "VOLKSWAGEN AG VORZUGSAKTIEN",
                                    "exchange": "L&S EUR", "id": 34304})

    def test_a_name_typed_with_spaces_is_still_found(self):
        asked = []

        def answer(url, timeout=15):
            if "autocomplete" in url:
                return b'{"data": []}'
            asked.append(url.rsplit("&q=", 1)[1])
            return json.dumps(self.FOUND if asked[-1] == "mercedes-benz" else []).encode()
        with mock.patch.object(self.ws, "fetch", side_effect=answer):
            found = self.ws.search("mercedes benz")
        self.assertEqual(asked, ["mercedes%20benz", "mercedes-benz"])
        self.assertEqual(found[0]["symbol"], self.VW)

    def test_one_word_is_asked_once(self):
        with self.net() as fetch:
            self.ws.search("volkswagen")
        self.assertEqual(len([c for c in fetch.call_args_list if "instrument/search" in c[0][0]]), 1)

    def test_bonds_broken_isins_and_rubbish_are_left_out(self):
        with self.net():
            found = self.ws.search("volkswagen")
        self.assertEqual([r["symbol"] for r in found], [self.VW, "DE000EVIL007"])
        self.assertNotIn("\x1b", found[1]["name"])

    def test_both_sources_share_the_ten_lines(self):
        us = [{"symbol": "A%d" % i, "name": "US %d" % i, "asset": "STOCKS"} for i in range(25)]
        with self.net(nasdaq=us):
            found = self.ws.search("a")
        self.assertEqual(len(found), 10)
        self.assertEqual([r["symbol"] for r in found[-2:]], [self.VW, "DE000EVIL007"])
        self.assertEqual(found[0]["symbol"], "A0")

    def test_the_search_shows_the_wkn_in_the_narrow_column(self):
        with self.net():
            lines = self.ws.search_lines("volkswagen", self.ws.search("volkswagen"), 0, 80, 20)
        self.assertIn("766403 VOLKSWAGEN AG VORZUGSAKTIEN", ANSI.sub("", lines[2]))
        self.assertIn("L&S EUR", ANSI.sub("", lines[2]))

    def test_the_quote_is_measured_against_yesterday(self):
        with self.net():
            q = self.ws.quote(self.VW)
        self.assertAlmostEqual(q["last"], 67.59)
        self.assertAlmostEqual(q["change"], 0.28)
        self.assertAlmostEqual(q["pct"], 0.28 / 67.31 * 100)
        self.assertEqual(q["currency"], "EUR")
        self.assertIsNone(q["extended"])

    def test_the_day_runs_on_the_clock_in_berlin(self):
        with self.net():
            data = self.ws.history(self.VW, "1d")
        self.assertEqual(data["labels"], ("08:00", "08:59"))
        self.assertEqual(len(data["points"]), 60)
        self.assertEqual((data["reference"], data["reference_line"]), (67.31, True))
        self.assertEqual(data["name"], "VOLKSWAGEN AG VORZUGSAKTIEN")
        self.assertIsNone(data["dim_from"])

    def test_longer_spans_are_cut_from_the_daily_closes(self):
        now = self.DAY / 1000 + 3600
        with self.net(), mock.patch.object(self.ws.time, "time", return_value=now):
            month = self.ws.history(self.VW, "1m")
            year = self.ws.history(self.VW, "1y")
        self.assertTrue(20 <= len(month["points"]) <= 33, len(month["points"]))
        self.assertTrue(360 <= len(year["points"]) <= 368, len(year["points"]))
        self.assertEqual(month["reference"], month["points"][0])
        self.assertFalse(month["reference_line"])
        # the right edge is the price of this minute, not last night's close
        self.assertAlmostEqual(month["last"], 67.59)
        self.assertAlmostEqual(month["points"][-1], 67.59)
        self.assertEqual(month["labels"][1], "11/16/2026")

    def test_todays_close_in_the_history_gives_way_to_the_price_of_this_minute(self):
        now = self.DAY / 1000 + 3600
        days = [[self.DAY - (40 - i) * 86400000, 50.0 + i] for i in range(41)]      # the last one is today
        with self.net(history=days), mock.patch.object(self.ws.time, "time", return_value=now):
            month = self.ws.history(self.VW, "1m")
        self.assertAlmostEqual(month["points"][-1], 67.59)
        self.assertAlmostEqual(month["points"][-2], 89.0)
        self.assertEqual(len([p for p in month["points"] if p > 89.5]), 0, "today is there once, not twice")

    def test_the_chart_names_the_currency(self):
        with self.net():
            lines = self.ws.chart_lines(self.ws.history(self.VW, "1d"), "1d", 90, 20)
        self.assertIn(self.VW, ANSI.sub("", lines[0]))
        self.assertIn("67.59 EUR", ANSI.sub("", lines[1]))

    def test_dollar_charts_stay_as_they_were(self):
        data = {"symbol": "NVDA", "name": "NVIDIA", "points": [1.0, 2.0], "labels": ("a", "b"), "last": 2.0,
                "reference": 1.0, "reference_line": False, "dim_from": None, "extended": None}
        self.assertNotIn("EUR", ANSI.sub("", self.ws.chart_lines(data, "1d", 90, 20)[1]))

    def test_the_watchlist_shows_wkn_price_and_euro(self):
        with self.net():
            self.ws.watch(self.VW, "VOLKSWAGEN AG VORZUGSAKTIEN")
            rows = self.ws.table_rows(100, 40)
        text, symbol, section = rows[2]
        self.assertEqual((symbol, section), (self.VW, "watch"), "the ISIN is what gets selected")
        plain = ANSI.sub("", text)
        self.assertTrue(plain.startswith("766403 VOLKSWAGEN AG VORZUGSAKTIEN"))
        self.assertIn("67.59 \u20ac", plain)
        self.assertIn("+0.28", plain)
        self.assertLessEqual(len(plain), 99)

    def test_an_unknown_isin_has_no_course_and_no_crash(self):
        with self.net():
            self.assertIsNone(self.ws.history("FR0000000001", "1d"))
            self.assertIsNone(self.ws.quote("FR0000000001"))
            self.assertEqual(self.ws.label("FR0000000001"), "FR0000000001")

    def test_a_broken_answer_is_no_course(self):
        for bad in ([], [["x", "y"]], "nope"):
            with tempfile.TemporaryDirectory() as tmp:
                self.ws = load(False, tmp)
                with self.net(intraday=bad):
                    self.assertIsNone(self.ws.history(self.VW, "1d"))

    def test_the_logo_is_asked_for_by_isin(self):
        with mock.patch.object(self.ws, "fetch", return_value=b"nothing") as fetch:
            self.ws.logo_grid(self.VW, 12)
        self.assertEqual([c[0][0] for c in fetch.call_args_list if "logos" in c[0][0]],
                         ["https://assets.parqet.com/logos/isin/%s?format=png&size=512" % self.VW])
