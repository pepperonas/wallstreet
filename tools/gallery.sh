#!/bin/sh
# Gallery pictures of the project page: the screenshots framed to 1120x800,
# as website/assets/gallery/<id>.jpg and .webp.  Needs ImageMagick 7 and cwebp.
#
#   tools/gallery.sh        (after tools/screenshots.sh)
set -eu
cd "$(dirname "$0")/.."
out=website/assets/gallery
mkdir -p "$out"
for id in wallstreet chart table headlines; do
	magick "docs/screenshots/$id.png" -resize 1056x736 -background '#11121a' \
		-gravity center -extent 1120x800 -strip -quality 88 "$out/$id.jpg"
	cwebp -quiet -q 84 "$out/$id.jpg" -o "$out/$id.webp"
	echo "$out/$id.jpg"
done
