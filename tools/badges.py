#!/usr/bin/env python3
"""Write the README's headline badges: .github/badges/{version,loc,tests}.json

    python3 tools/badges.py [--check]

The numbers are counted, never typed: the version comes from VERSION, the tests
from unittest's own discovery, the lines from the files that make up the program
and its tests.  --check changes nothing and exits 1 if a file is out of date
(lines of code are left out of the check: they move with every edit, and the
badges workflow refreshes them after each push).
"""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / ".github" / "badges"
CODE = ("bin", "lib", "share", "tests", "tools", "install.sh")
TEXT = {".sh", ".py", ".rb", ".config", ".urls", ".1", ""}


def count_tests():
    def walk(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                yield from walk(item)
            else:
                yield item
    return sum(1 for _ in walk(unittest.defaultTestLoader.discover(str(ROOT / "tests"))))


def count_lines():
    total = 0
    for entry in CODE:
        path = ROOT / entry
        files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        for f in files:
            if f.suffix not in TEXT or "__pycache__" in f.parts:
                continue
            try:
                total += sum(1 for _ in f.open(encoding="utf-8"))
            except UnicodeDecodeError:
                pass
    return total


def payloads():
    tests = count_tests()
    if tests == 0:
        sys.exit("badges: found no tests - refusing to publish a zero")
    version = (ROOT / "VERSION").read_text().strip()
    return {
        "version": {"schemaVersion": 1, "label": "version", "message": "v" + version, "color": "2D6CDF"},
        "loc": {"schemaVersion": 1, "label": "lines of code", "message": str(count_lines()), "color": "5C4EE5"},
        "tests": {"schemaVersion": 1, "label": "unit tests", "message": "%d passing" % tests, "color": "2EA44F"},
    }


def main(argv):
    check = "--check" in argv
    stale = []
    for key, data in payloads().items():
        path = OUT / (key + ".json")
        text = json.dumps(data, indent=2) + "\n"
        if check:
            if key != "loc" and (not path.exists() or path.read_text() != text):
                stale.append(key)
            continue
        OUT.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print("%-8s %s" % (key, data["message"]))
    if stale:
        print("stale badges: %s - run tools/badges.py" % ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
