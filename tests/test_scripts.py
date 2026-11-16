"""Tests for the shell side: bin/wallstreet and the widgets in lib/wallstreet."""
import os
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WIDGETS = sorted((ROOT / "lib/wallstreet").iterdir())
CODE = re.compile(r"^\s*#.*$", re.M)


def code(path):
    return CODE.sub("", path.read_text())


class Scripts(unittest.TestCase):
    def test_launcher_is_valid_bash(self):
        subprocess.run(["bash", "-n", str(ROOT / "bin/wallstreet")], check=True)

    def test_every_widget_is_valid_sh(self):
        for w in WIDGETS:
            subprocess.run(["sh", "-n", str(w)], check=True)

    def test_every_widget_is_executable(self):
        for w in WIDGETS:
            self.assertTrue(os.access(w, os.X_OK), w.name)

    def test_the_expected_widgets_exist(self):
        self.assertEqual([w.name for w in WIDGETS],
                         ["headlines", "img2txt", "jp2a", "newsboat", "quotes", "ticker"])

    def test_launcher_starts_only_widgets_that_exist(self):
        used = set(re.findall(r"\$widget_dir/([a-z0-9]+)", code(ROOT / "bin/wallstreet")))
        self.assertTrue(used)
        self.assertLessEqual(used, {w.name for w in WIDGETS})

    def test_nothing_kills_processes_by_pattern(self):
        # "pkill -f lib/wallstreet/" also hit an editor that had a widget open
        for path in [ROOT / "bin/wallstreet", *WIDGETS]:
            self.assertNotIn("pkill", code(path), path.name)

    def test_every_widget_quits_by_closing_its_window(self):
        for w in WIDGETS:
            self.assertIn("trap quit INT", w.read_text(), w.name)
            self.assertIn('tmux kill-window -t "$TMUX_PANE"', w.read_text(), w.name)

    def test_nothing_uses_dev_shm(self):
        for path in [ROOT / "bin/wallstreet", *WIDGETS]:
            self.assertNotIn("/dev/shm", code(path), path.name)

    def test_gnu_only_tools_are_gone(self):
        for path in WIDGETS:
            for tool in ("shuf", "wget", "w3m", "rsstail"):
                self.assertNotRegex(code(path), r"\b%s\b" % tool, (path.name, tool))

    def test_unknown_option_is_a_usage_error(self):
        r = subprocess.run([str(ROOT / "bin/wallstreet"), "--bogus"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage", r.stderr)

    def test_demo_flag_reaches_the_panes(self):
        src = code(ROOT / "bin/wallstreet")
        starts = re.findall(r'"(\$run )?\$widget_dir/', src)
        self.assertTrue(starts)
        self.assertTrue(all(starts), "a pane is started without the demo environment")

    def test_session_is_only_killed_when_owned(self):
        src = code(ROOT / "bin/wallstreet")
        self.assertRegex(src, r'\[ -n "\$WALLSTREET_OWN_SESSION" \] && tmux kill-session')

    def test_data_helper_is_executable(self):
        self.assertTrue(os.access(ROOT / "share/wallstreet/wsdata", os.X_OK))

    def test_feed_list_has_only_https_urls(self):
        lines = (ROOT / "share/wallstreet/newsboat.urls").read_text().split()
        self.assertTrue(lines)
        self.assertTrue(all(l.startswith("https://") for l in lines), lines)

    def test_version_file_matches_the_changelog(self):
        version = (ROOT / "VERSION").read_text().strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        first = re.search(r"^## \[(\d+\.\d+\.\d+)\]", (ROOT / "CHANGELOG.md").read_text(), re.M)
        self.assertEqual(first.group(1), version)

    def test_formula_carries_the_version(self):
        version = (ROOT / "VERSION").read_text().strip()
        formula = (ROOT / "packaging/wallstreet.rb").read_text()
        self.assertIn("/v%s/wallstreet.tar.gz" % version, formula)
        self.assertIn('version "%s"' % version, formula)

    def test_launcher_carries_the_version(self):
        version = (ROOT / "VERSION").read_text().strip()
        self.assertIn('VERSION="%s"' % version, (ROOT / "bin/wallstreet").read_text())
        r = subprocess.run([str(ROOT / "bin/wallstreet"), "--version"], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "wallstreet " + version)

    def test_licence_and_notice_are_there(self):
        self.assertIn("Apache License", (ROOT / "LICENSE").read_text())
        self.assertIn("Dustin Kirkland", (ROOT / "NOTICE").read_text())

    def test_installer_names_the_release_asset(self):
        self.assertIn("assets/wallstreet.tar.gz", (ROOT / ".github/workflows/release.yml").read_text())
        self.assertIn('"$BASE/$NAME.tar.gz"', (ROOT / "install.sh").read_text())

    def test_man_page_names_the_demo_option(self):
        self.assertIn("--demo", (ROOT / "share/man/man1/wallstreet.1").read_text())


if __name__ == "__main__":
    unittest.main()
