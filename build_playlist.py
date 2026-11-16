#!/usr/bin/env python3
"""Build a curated Italian IPTV playlist: for each wanted channel pick the first stream that passes a
live check, rewrite Rai relinker links to https, and align tvg-id with the EPG.
Run it from an Italian IP (geo-blocked streams look dead otherwise).
Usage: build_playlist.py [--extras] [--out playlist.m3u] [--report report.json]
"""
import argparse, concurrent.futures as cf, gzip, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(__file__))
from iptv_check import parse, load, check

TUNDRAK = "https://github.com/Tundrak/IPTV-Italia/raw/main/iptvitaplus.m3u"
FREETV = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_italy.m3u8"
EPG = "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz"
UA = "ExoPlayerLib/2.18.7"

# (LCN, canonical name, group, extra normalized aliases)
WANTED = [
    (1, "Rai 1", "Rai", []), (2, "Rai 2", "Rai", []), (3, "Rai 3", "Rai", []),
    (21, "Rai 4", "Rai", []), (23, "Rai 5", "Rai", []), (24, "Rai Movie", "Rai", []),
    (25, "Rai Premium", "Rai", []), (42, "Rai Gulp", "Rai", []), (43, "Rai YoYo", "Rai", []),
    (48, "Rai News 24", "Rai", []), (54, "Rai Storia", "Rai", []), (57, "Rai Scuola", "Rai", []),
    (58, "Rai Sport", "Rai", ["raisporthd"]),
    (4, "Rete 4", "Mediaset", []), (5, "Canale 5", "Mediaset", []), (6, "Italia 1", "Mediaset", []),
    (20, "20 Mediaset", "Mediaset", ["20"]), (22, "Iris", "Mediaset", []), (30, "La 5", "Mediaset", ["la5"]),
    (27, "Twenty Seven", "Mediaset", ["27twentyseven"]), (34, "Cine34", "Mediaset", []),
    (35, "Focus", "Mediaset", []), (39, "Top Crime", "Mediaset", []), (40, "Boing", "Mediaset", []),
    (46, "Cartoonito", "Mediaset", []), (49, "Italia 2", "Mediaset", []), (51, "TGCom 24", "Mediaset", ["tgcom"]),
    (55, "Mediaset Extra", "Mediaset", []),
    (7, "La7", "La7", []), (29, "La7d", "La7", []),
    (8, "TV8", "Altri", []), (9, "Nove", "Discovery", []), (26, "Cielo", "Altri", []),
    (31, "Real Time", "Discovery", []), (52, "DMAX", "Discovery", []), (41, "K2", "Discovery", []),
    (38, "Giallo", "Discovery", []), (44, "Frisbee", "Discovery", []), (37, "Warner TV", "Discovery", []),
    (33, "Food Network", "Discovery", []), (56, "HGTV", "Discovery", ["hgtvhomegarden"]),
    (59, "Motor Trend", "Discovery", []),
    (50, "Sky TG24", "Altri", []), (28, "TV2000", "Altri", []), (32, "QVC", "Altri", []),
    (47, "Super!", "Altri", ["super"]),
]

def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("Ⓖ", "").replace("Ⓢ", ""))

def rai_https(url):
    m = re.match(r"https?://mediapolis\.rai\.it/relinker/relinkerServlet\.htm\?cont=(\d+)", url)
    return f"https://mediapolis.rai.it/relinker/relinkerServlet.htm?cont={m.group(1)}&output=7" if m else url

def read_attr(text, name):
    m = re.search(rf'{name}="([^"]*)"', text)
    return m.group(1) if m else ""

def candidates(src_text, source):
    """parse() drops logos; re-read them from the raw EXTINF lines."""
    chans = parse(src_text)
    extinf = [l for l in src_text.splitlines() if l.startswith("#EXTINF")]
    for c, l in zip(chans, extinf):
        c["logo"], c["src"] = read_attr(l, "tvg-logo"), source
    return chans

def epg_map():
    raw = urllib.request.urlopen(urllib.request.Request(EPG, headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read()
    root = ET.fromstring(gzip.decompress(raw))
    by_name, ids = {}, set()
    for ch in root.iter("channel"):
        cid = ch.get("id"); ids.add(cid)
        for dn in ch.findall("display-name"):
            by_name.setdefault(norm(dn.text or ""), cid)
        by_name.setdefault(norm(cid.removesuffix(".it")), cid)
    return by_name, ids

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="playlist.m3u"); ap.add_argument("--report", default="report.json")
    ap.add_argument("--extras", action="store_true", help="append all other working channels (regional, thematic, radio)")
    a = ap.parse_args()

    tund = candidates(load(TUNDRAK), "tundrak")
    free = [c for c in candidates(load(FREETV), "free-tv") if not re.match(r"rai", norm(c["name"]))]  # Rai: official links only
    for c in tund:
        c["url"] = rai_https(c["url"])
        if "mediapolis.rai.it" in c["url"]: c["ua"] = None  # https relinker accepts Android/ExoPlayer UAs

    plan = []  # (entry, [candidates in priority order])
    for lcn, name, group, aliases in WANTED:
        keys = {norm(name), *aliases}
        cs = [c for c in tund + free if norm(c["name"]) in keys]
        plan.append(((lcn, name, group), cs))

    flat = [(i, c) for i, (_, cs) in enumerate(plan) for c in cs]
    with cf.ThreadPoolExecutor(16) as ex:
        results = list(ex.map(lambda t: (t[0], check(t[1], UA)), flat))
    ok_by = {}
    for i, r in results:
        if r["ok"]:
            ok_by.setdefault(i, []).append(r)

    by_name, ids = epg_map()
    lines = [f'#EXTM3U x-tvg-url="{EPG}"']
    report = {"included": [], "missing": [], "no_epg": []}
    for i, ((lcn, name, group), cs) in enumerate(plan):
        picked = ok_by.get(i)
        if not picked:
            report["missing"].append({"name": name, "tried": [(c["src"], c["why"] if "why" in c else "") for c in cs]})
            continue
        c = picked[0]
        epg_id = c["id"] if c["id"] in ids else next((by_name[k] for k in [norm(name), *WANTED[i][3]] if k in by_name), "")
        if not epg_id:
            report["no_epg"].append(name)
        lines.append(f'#EXTINF:-1 tvg-id="{epg_id}" tvg-name="{name}" tvg-chno="{lcn}" tvg-logo="{c.get("logo","")}" group-title="{group}",{name}')
        if c["ua"]:
            lines.append(f'#EXTVLCOPT:http-user-agent={c["ua"]}')
        lines.append(c["url"])
        report["included"].append({"lcn": lcn, "name": name, "src": c["src"], "epg_id": epg_id, "alternatives": len(picked) - 1})

    if a.extras:  # every other working channel from both sources, after the curated ones
        used_names = {norm(n) for _, n, _, _ in WANTED} | {norm(x) for _, _, _, al in WANTED for x in al}
        seen = set(); extra = []
        for c in tund + free:
            k = norm(c["name"])
            if not k or k in used_names or k in seen or re.match(r"rai", k):
                continue
            seen.add(k); extra.append(c)
        with cf.ThreadPoolExecutor(16) as ex:
            extra = [r for r in ex.map(lambda c: check(c, UA), extra) if r["ok"]]
        extra.sort(key=lambda c: norm(c["name"]))
        for n, c in enumerate(extra, start=100):
            name = re.sub(r"\s*[ⒼⓈ]\s*", " ", c["name"]).strip()
            epg_id = c["id"] if c["id"] in ids else by_name.get(norm(name), "")
            grp = "Radio" if re.search(r"radio|rds|virgin|m2o|deejay|r101|rtl|kiss|zeta|capital|freccia|105|montecarlo", norm(name)) else "Regionali e altri"
            lines.append(f'#EXTINF:-1 tvg-id="{epg_id}" tvg-name="{name}" tvg-chno="{n}" tvg-logo="{c.get("logo","")}" group-title="{grp}",{name}')
            if c["ua"]:
                lines.append(f'#EXTVLCOPT:http-user-agent={c["ua"]}')
            lines.append(c["url"])
            report["included"].append({"lcn": n, "name": name, "src": c["src"], "epg_id": epg_id, "group": grp})

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    json.dump(report, open(a.report, "w"), indent=1, ensure_ascii=False)
    print(f"included {len(report['included'])}/{len(WANTED)}  missing {len(report['missing'])}  without EPG id {len(report['no_epg'])}")
    print("missing:", [m["name"] for m in report["missing"]])
    print("no epg :", report["no_epg"])
