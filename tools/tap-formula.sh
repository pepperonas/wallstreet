#!/bin/sh
# Print the formula for the Homebrew tap: packaging/wallstreet.rb with the checksum of
# the published release archive filled in.
#
#   tools/tap-formula.sh > ../homebrew-tap/Formula/wallstreet.rb
set -eu
cd "$(dirname "$0")/.."
version=$(cat VERSION)
url="https://github.com/pepperonas/wallstreet/releases/download/v$version/SHA256SUMS"
sum=$(curl -fsSL "$url" | awk '$2 == "wallstreet.tar.gz" {print $1}')
[ -n "$sum" ] || { echo "no checksum for wallstreet.tar.gz at $url" >&2; exit 1; }
sed -e "s/SHA256_OF_THE_RELEASE_ARCHIVE/$sum/" -e '1,3d' packaging/wallstreet.rb
