#!/usr/bin/env python3
"""Print the CHANGELOG section of one version - the body of its GitHub release.

    python3 tools/release_notes.py 1.0.0

Exits 1 when the changelog has no entry for that version: the release workflow
should stop rather than publish a release nobody can read.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def notes_for(version, changelog=None):
    """The text between `## [version]` and the next `## [` heading, or None."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8") if changelog is None else changelog
    match = re.search(r"^## \[%s\][^\n]*\n(.*?)(?=^## \[|\Z)" % re.escape(version), text, re.M | re.S)
    return match.group(1).strip() + "\n" if match and match.group(1).strip() else None


def main(argv):
    if len(argv) != 2:
        print("usage: release_notes.py VERSION", file=sys.stderr)
        return 2
    notes = notes_for(argv[1].lstrip("v"))
    if not notes:
        print("CHANGELOG.md has no entry for %s" % argv[1], file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
