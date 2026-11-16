#!/usr/bin/env bash
# Rebuild both playlists and push them if they changed. Must run from an Italian IP.
# Safety: if a build looks broken (offline Mac, source down) nothing is published.
set -euo pipefail
cd "$(dirname "$0")"

MIN_CURATED=35   # of ~42 national channels
MIN_FULL=150

count() { grep -c '^#EXTINF' "$1"; }

# Optional Uptime Kuma "push" heartbeat. The push URL is a secret: it lives outside the repo,
# in ~/.config/tv-iptv-it/kuma-push-url (one line). Missing file = no heartbeat, no error.
KUMA_URL_FILE="${KUMA_URL_FILE:-$HOME/.config/tv-iptv-it/kuma-push-url}"
heartbeat() {  # heartbeat up|down "message"
  [ -r "$KUMA_URL_FILE" ] || return 0
  curl -fsS -m 15 -G --data-urlencode "status=$1" --data-urlencode "msg=$2" "$(head -n1 "$KUMA_URL_FILE")" >/dev/null 2>&1 || true
}
trap 'heartbeat down "update.sh failed (line $LINENO)"' ERR

python3 build_playlist.py --out .new-playlist.m3u --report .report.json
python3 build_playlist.py --extras --out .new-playlist-full.m3u --report .report-full.json

c=$(count .new-playlist.m3u); f=$(count .new-playlist-full.m3u)
echo "curated=$c full=$f"
if [ "$c" -lt "$MIN_CURATED" ] || [ "$f" -lt "$MIN_FULL" ]; then
  echo "refusing to publish: build looks broken (curated=$c<$MIN_CURATED or full=$f<$MIN_FULL)" >&2
  rm -f .new-playlist.m3u .new-playlist-full.m3u
  heartbeat down "refused to publish: curated=$c full=$f"
  exit 1
fi
mv .new-playlist.m3u playlist.m3u
mv .new-playlist-full.m3u playlist-full.m3u

[ "${NOPUSH:-0}" = 1 ] && exit 0
git add playlist.m3u playlist-full.m3u
if git diff --cached --quiet; then
  echo "no changes"
  heartbeat up "ok, no changes (curated=$c full=$f)"
  exit 0
fi
git commit -q -m "Update playlists $(date +%F) (curated $c, full $f)"
git push -q origin main
echo "pushed"
heartbeat up "ok, published (curated=$c full=$f)"
