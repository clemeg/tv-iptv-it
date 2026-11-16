#!/usr/bin/env bash
# Rebuild both playlists and push them if they changed. Must run from an Italian IP.
# Safety: if a build looks broken (offline Mac, source down) nothing is published.
set -euo pipefail
cd "$(dirname "$0")"

MIN_CURATED=35   # of ~42 national channels
MIN_FULL=150

count() { grep -c '^#EXTINF' "$1"; }

python3 build_playlist.py --out .new-playlist.m3u --report .report.json
python3 build_playlist.py --extras --out .new-playlist-full.m3u --report .report-full.json

c=$(count .new-playlist.m3u); f=$(count .new-playlist-full.m3u)
echo "curated=$c full=$f"
if [ "$c" -lt "$MIN_CURATED" ] || [ "$f" -lt "$MIN_FULL" ]; then
  echo "refusing to publish: build looks broken (curated=$c<$MIN_CURATED or full=$f<$MIN_FULL)" >&2
  rm -f .new-playlist.m3u .new-playlist-full.m3u
  exit 1
fi
mv .new-playlist.m3u playlist.m3u
mv .new-playlist-full.m3u playlist-full.m3u

[ "${NOPUSH:-0}" = 1 ] && exit 0
git add playlist.m3u playlist-full.m3u
git diff --cached --quiet && { echo "no changes"; exit 0; }
git commit -q -m "Update playlists $(date +%F) (curated $c, full $f)"
git push -q origin main
echo "pushed"
