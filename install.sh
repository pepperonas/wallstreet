#!/bin/sh
# wallstreet installer: downloads the newest release, verifies it, installs it.
#
#   curl -fsSL https://github.com/pepperonas/wallstreet/releases/latest/download/install.sh | sh
#
# Installs into $PREFIX (default: ~/.local) - bin/, lib/wallstreet/, share/wallstreet/ and the
# man page.  Nothing needs root.  PREFIX=/usr/local sh install.sh for a system-wide copy.
set -eu

NAME=wallstreet
BASE="${WALLSTREET_BASE:-https://github.com/pepperonas/wallstreet/releases/latest/download}"
PREFIX="${PREFIX:-$HOME/.local}"
NEED="tmux python3"
OPTIONAL="newsboat img2txt jp2a"

say() { printf '%s\n' "$*"; }
die() { say "install.sh: $*" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || die "curl is needed"
command -v tar >/dev/null 2>&1 || die "tar is needed"
if command -v sha256sum >/dev/null 2>&1; then
	sum() { sha256sum "$1" | cut -d' ' -f1; }
elif command -v shasum >/dev/null 2>&1; then
	sum() { shasum -a 256 "$1" | cut -d' ' -f1; }
else
	die "sha256sum or shasum is needed to verify the download"
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM

say "Downloading $NAME ..."
curl -fsSL -o "$tmp/$NAME.tar.gz" "$BASE/$NAME.tar.gz" || die "download failed"
curl -fsSL -o "$tmp/SHA256SUMS" "$BASE/SHA256SUMS" || die "could not fetch SHA256SUMS"

want=$(awk -v f="$NAME.tar.gz" '$2 == f {print $1}' "$tmp/SHA256SUMS")
[ -n "$want" ] || die "SHA256SUMS has no entry for $NAME.tar.gz"
have=$(sum "$tmp/$NAME.tar.gz")
[ "$want" = "$have" ] || die "checksum mismatch: expected $want, got $have"
say "Checksum ok."

tar -xzf "$tmp/$NAME.tar.gz" -C "$tmp"
src=$(find "$tmp" -maxdepth 1 -type d -name "$NAME-*" | head -n 1)
[ -d "$src/bin" ] || die "unexpected archive layout"

mkdir -p "$PREFIX/bin" "$PREFIX/lib" "$PREFIX/share/man/man1"
rm -rf "$PREFIX/lib/$NAME" "$PREFIX/share/$NAME"
cp -R "$src/lib/$NAME" "$PREFIX/lib/"
cp -R "$src/share/$NAME" "$PREFIX/share/"
cp "$src/share/man/man1/$NAME.1" "$PREFIX/share/man/man1/"
cp "$src/bin/$NAME" "$PREFIX/bin/$NAME"
chmod +x "$PREFIX/bin/$NAME"
say "Installed $NAME $(cat "$src/VERSION") into $PREFIX"

missing=
for tool in $NEED; do
	command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
done
extra=
for tool in $OPTIONAL; do
	command -v "$tool" >/dev/null 2>&1 || extra="$extra $tool"
done
[ -z "$missing" ] || say "Needed and not found:$missing"
[ -z "$extra" ] || say "Optional and not found (their panes stay away):$extra"
case ":$PATH:" in
	*":$PREFIX/bin:"*) ;;
	*) say "Add $PREFIX/bin to your PATH to run '$NAME'." ;;
esac
