#!/usr/bin/env python3
"""Check every stream in an M3U playlist. A stream is OK if, after redirects, the body starts
like an HLS playlist (#EXTM3U) or the response is a media/octet stream with data.
Usage: iptv_check.py <url-or-file> [--ua UA] [--out result.json]
"""
import argparse, concurrent.futures as cf, json, re, subprocess, sys, urllib.request

def load(src):
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    return open(src, encoding="utf-8").read()

def parse(text):
    out, cur, opts = [], None, {}
    for l in text.splitlines():
        l = l.strip()
        if l.startswith("#EXTINF"):
            cur = {"name": l.rsplit(",", 1)[-1].strip(),
                   "id": (re.search(r'tvg-id="([^"]*)"', l) or [None, ""])[1],
                   "group": (re.search(r'group-title="([^"]*)"', l) or [None, ""])[1]}
            opts = {}
        elif l.startswith("#EXTVLCOPT:http-user-agent="):
            opts["ua"] = l.split("=", 1)[1]
        elif l and not l.startswith("#") and cur:
            cur["url"], cur["ua"] = l, opts.get("ua"); out.append(cur); cur = None
    return out

def check(c, default_ua):
    ua = c["ua"] or default_ua
    cmd = ["curl", "-sL", "--max-time", "12", "-A", ua, "-w", "\n__%{http_code}|%{content_type}",
           "-r", "0-3000", c["url"]]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=20)
    except Exception as e:
        return {**c, "ok": False, "why": f"error {e}"}
    body, _, tail = r.stdout.rpartition(b"\n__")
    code, _, ctype = tail.decode("latin1").partition("|")
    head = body[:200].decode("latin1", "replace")
    ok = code in ("200", "206") and ("#EXTM3U" in head or "<MPD" in head or "mpegurl" in ctype.lower()
                                      or "dash+xml" in ctype.lower()
                                      or ctype.startswith(("video/", "audio/", "application/octet")) and len(body) > 500)
    why = "ok" if ok else (f"http {code}" if code not in ("000", "") else f"curl exit {r.returncode}")
    return {**c, "ok": ok, "why": why}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--ua", default="Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36")
    ap.add_argument("--out"); a = ap.parse_args()
    ch = parse(load(a.src))
    with cf.ThreadPoolExecutor(16) as ex:
        res = list(ex.map(lambda c: check(c, a.ua), ch))
    ok = [r for r in res if r["ok"]]
    print(f"{a.src}\n  total {len(res)}  ok {len(ok)}  bad {len(res) - len(ok)}")
    for r in res:
        if not r["ok"]:
            print(f"  BAD  {r['name'][:32]:32} {r['why']}")
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
