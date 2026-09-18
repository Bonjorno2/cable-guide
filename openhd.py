"""Build CH 12 CLEARED: modern, sharp, and free because the maker said so.

Everything else on this dial is old enough that its copyright has run out. This
channel is the other way round -- films from 2006 to last year, in 720p and
better, that are free to rebroadcast because whoever made them said so.

The obvious way to build it does not work, and it is worth writing down why.
archive.org items carry a `licenseurl` field, so the one-line version of this
channel is "filter on licenseurl, sort by resolution". Run it and the top of
the list is Lady Vengeance, The Peanuts Movie, Astro Boy and Letters from Iwo
Jima, every one of them stamped `publicdomain/mark/1.0`. The field is written
by whoever uploaded the item, which makes it a claim and not evidence -- the
same lesson `release_year()` learned about `year` and `id_year()` learned about
a number in a slug, arriving for a third time.

Worse, the correlation runs backwards. Of 1,001 items in the catalog whose
title advertises an HD source and whose release year is 1970 or later, three
carry any licence claim at all, and the rest have names like
`Jennifer.1978.1080p.BluRay.DTS-HD.x264-BARC0DE`. The genuinely open films of
the same era were encoded at 2000s web resolutions -- Star Wreck is 564x240,
Warriors of The Net is 641x480 -- because that is what the web was then. So
"newest and best-looking" is very nearly a search *for* infringement, and the
resolution gate has to sit downstream of a rights test that does not depend on
an uploader's typing.

That test is the source, not the item:

  blender     the Blender Foundation's open movies. CC-BY, and uploaded by the
              people who hold the copyright. Sintel, Big Buck Bunny, Cosmos
              Laundromat, Tears of Steel -- made to be redistributed, and made
              at resolutions that still hold up.
  nasa        works of the US federal government, public domain by statute
              rather than by anybody's assertion. CH 14 already trades on this.
  named       four films whose free licence is a matter of public record and
              was checked by hand. A list, because at this size a list is
              honest and a filter is not.

Run order:  suggest.py  ->  misfiled.py  ->  openhd.py  ->  build.py
(suggest.py rewrites data["suggested"] wholesale.)
"""
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import describe
import harvest

# Titles here carry emoji and box-drawing; a Windows console is cp1252.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = {"User-Agent": "cable-guide-harvester/1.0"}
SEARCH = "https://archive.org/advancedsearch.php"

NUM, NAME = 12, "CLEARED"
TAG = "Modern, sharp, and free because the maker said so"

# 1280 wide is the 720p class. Gating on *width* rather than height is the
# whole point: a 2.39:1 feature at 1280x534 is a 720p encode, and a rule that
# asked for 720 rows would throw away every widescreen film in the channel.
MIN_WIDTH = 1280
FLOOR_YEAR = 2005           # "newest": this side of the web-video line
BAND = (60, 11000)          # a minute to three hours

# Anything in an MP4 container the browser will play. Unlike harvest.MP4_FORMATS
# this is not a preference order -- the derivative is chosen by pixel width,
# because picking "h.264 IA" first would hand back the 640x360 proxy of a file
# that also exists at 1920x1080.
MP4_FORMATS = {"h.264 IA", "h.264", "MPEG4", "512Kb MPEG4", "HiRes MPEG4",
               "HD MPEG4", "MPEG4 1080p", "h.264 HD"}

SOURCES = [
    ("blender", 'collection:"blender_foundation" OR creator:"Blender Foundation"'),
    ("nasa", 'collection:"nasa" AND mediatype:movies AND year:[2010 TO 2026]'),
]

# The Blender Foundation's shelf is not a shelf of films. Most of it is the
# software -- `blender 4.0.0`, `blender-2.82` -- and most of the rest is the
# Blender Conference archive, which is how a first run of this channel ended up
# programming `Speed Sculpting Live Session` and `Blender 2.90 Features Reel`
# between two Apollo magazines. The open movies are a finite set with names, so
# they are named. Same argument this file already makes about NAMED, one level
# down: at this size a list is honest and a filter is not.
# The year is the release year of the film, and it is here because half these
# uploads carry no date at all -- Spring, Elephants Dream and Glass were each
# dropped by the date gate before the resolution gate ever saw them. Which is
# the same failure CH 11 MISFILED is built out of, met from the other side: a
# blank date field costs you the film. Here the set is known, so it is stated.
BLENDER_FILMS = {
    "elephants dream": 2006, "big buck bunny": 2008, "sintel": 2010,
    "tears of steel": 2012, "cosmos laundromat": 2015, "glass half": 2015,
    "caminandes": 2016, "agent 327": 2017, "hero": 2018, "spring": 2019,
    "coffee run": 2020, "sprite fright": 2021, "charge": 2022, "wing it": 2023,
}

# NASA's 5,673 items are mostly raw archive: film-magazine transfers, downlink
# feeds, press webcasts and B-roll, filed under the catalogue number they were
# transferred as -- `jsc2023m000111_Earth_in_4K_Space_Station_E`,
# `ak13_Mag_Trks___Apollo_11_Earth_Ops2_SOUND`, `CMP-0723A_Apollo11_EVA1`.
#
# A first pass tried to name the patterns and missed every one of those: the
# titles are not all-caps, the underscores are single, and `\bEVA\b` does not
# match `EVA1`. Testing for the *absence* of prose is the wrong way round. A
# programme has a title somebody wrote for a reader to read, so that is what
# gets required -- words, and no catalogue numbers among them.
CODE_TOKEN = re.compile(r"[a-z]{2,}\d{3,}|\d{5,}|^\d{6}$", re.I)
NASA_DROP = re.compile(
    r"\b(webcast|downlink|b[-_ ]?roll|magazine|mag[_ ]trks|onboard[_ ]film|"
    r"briefing|press conference|news conference|coverage|feed|interview|"
    r"spacewalk|on-?orbit|extended cut|EVA\d*)\b", re.I)


def is_prose(title):
    """A title written for a reader, not a transfer log."""
    if "_" in title:
        return False
    words = title.split()
    return (len(words) >= 3
            and not any(CODE_TOKEN.search(w) for w in words))

# Checked by hand, one at a time, because four is a number you can check. Each
# is a documented decision by the rights holder, which is exactly what the
# `licenseurl` field fails to be.
#   sita sings the blues   Nina Paley put it out under a free licence herself
#                          and later released it outright.
#   the internet's own boy Brian Knappenberger released it CC-BY-NC-SA 4.0 on
#                          the day it premiered.
#   pioneer one            released CC-BY-NC-SA through VODO, an episode at a
#                          time, and the only modern *series* on the dial that
#                          is free by its makers' choice.
# Searched by title rather than listed by identifier, because each of these is
# on archive.org several times over and the copy worth playing is decided by
# resolve(), not by whichever identifier got transcribed here.
NAMED = [
    'title:"Sita Sings the Blues"',
    'title:"The Internet\'s Own Boy"',
    'title:"Pioneer One"',
    'title:"Elephants Dream"',
]

# Each NAMED search also returns that film's trailers, its press clips and, in
# one case, a seven-minute scene posted on its own. A programme-length floor is
# a blunter instrument than matching them by name and it does not go stale.
NAMED_MIN_DUR = 1200

# ...and the Blender shelf carries a podcast whose episode titles name the
# films it discusses, which is how `Blender Radio: Text Effects + Elephants
# Dream` was programmed as if it were Elephants Dream.
BLENDER_DROP = re.compile(
    r"\b(radio|podcast|conference|session|tutorial|workshop|webinar|talk|"
    r"ask me anything|AMA|showcase|features reel|released|LTS|demo ?reel)\b",
    re.I)

# NASA's collection is 5,673 items of which most are press clips and B-roll.
# Left alone it is not a channel, it is CH 14 with more pixels, so it is capped
# and required to be programme-shaped rather than a thirty-second cutaway. Six,
# because the first build came back 22 NASA items out of 30 and that is the
# space channel this dial already has, in a slot that was asked for films.
NASA_CAP = 6
NASA_MIN_DUR = 240

# A clip, a trailer or a loop is not a programme -- suggest.py's point, and it
# needs making again here because open-movie shelves carry a lot of tests.
EXCLUDE = re.compile(
    r"\b(trailer|teaser|preview|test ?render|b-?roll|raw footage|loop|"
    r"wallpaper|sample|behind the scenes|making of|vfx breakdown|"
    r"time ?lapse|promo)\b", re.I)


def search(query, rows=200):
    params = [("q", query), ("rows", str(rows)), ("output", "json"),
              ("sort[]", "downloads desc")]
    params += [("fl[]", f) for f in
               ("identifier", "title", "year", "date", "downloads",
                "licenseurl", "creator")]
    url = SEARCH + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=60) as r:
            return json.load(r)["response"]["docs"]
    except Exception as e:
        print(f"  search failed ({query[:40]}): {e}")
        return []


def best_mp4(ident):
    """-> (name, duration, width, height) for the widest playable MP4."""
    url = f"https://archive.org/download/{ident}/{ident}_files.xml"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=60) as r:
            root = ET.fromstring(r.read())
    except Exception:
        return None
    best = None
    for f in root.findall("file"):
        name = f.get("name") or ""
        if (f.findtext("format") not in MP4_FORMATS
                or not name.lower().endswith(".mp4")):
            continue
        dur = harvest.parse_len(f.findtext("length"))
        try:
            w, h = int(f.findtext("width")), int(f.findtext("height"))
        except (TypeError, ValueError):
            continue
        if dur and (best is None or w > best[2]):
            best = (name, dur, w, h)
    return best


def year_of(doc):
    for key in ("year", "date"):
        head = str(doc.get(key) or "")[:4]
        if head.isdigit():
            return int(head)
    return None


# Quality and format notes an uploader hangs off a title. `Pioneer One S01E01`
# and `Pioneer One S01E01 [720p HD]` are one episode, and must key alike.
QUALITY = re.compile(
    r"[\(\[]?\b(720p?|1080p?|2160p|4k|hd|sd|60 ?fps|stereo|x264|h ?264|"
    r"widescreen|remaster(?:ed)?|full|english|subbed|dub(?:bed)?)\b[\)\]]?",
    re.I)


def norm_key(title):
    """A title reduced to the programme it names."""
    t = QUALITY.sub(" ", str(title).lower())
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def film_of(title):
    """Which Blender open movie this upload is a copy of, or None.

    Seven of the eleven Big Buck Bunny uploads differ only in encode -- `Big
    Buck Bunny 4k 60fps`, `Big Buck Bunny 1280x720 Stereo`, `Big Bug Bunny`.
    Matching them to one name is what lets `resolve()` keep the sharpest copy
    of each film rather than the first one it happened to read.
    """
    t = re.sub(r"[^a-z0-9 ]+", " ", str(title).lower())
    t = re.sub(r"\s+", " ", t)
    hits = [f for f in BLENDER_FILMS if f in t or f.replace(" ", "") in t]
    # `big buck bunny` also contains `bunny`; longest name wins, and a typo'd
    # `Big Bug Bunny` is caught by the fuzz below rather than missed entirely.
    if not hits and re.search(r"big bu[gc]k? bunny", t):
        return "big buck bunny"
    return max(hits, key=len) if hits else None


def gather():
    """Candidates from each verified-open source, deduped by identifier."""
    seen, out = set(), []
    for label, query in SOURCES + [("named", q) for q in NAMED]:
        docs = search(query)
        kept = 0
        for d in docs:
            ident = d["identifier"]
            title = str(d.get("title") or "")
            if ident in seen or EXCLUDE.search(title):
                continue
            film = None
            if label == "blender":
                if BLENDER_DROP.search(title):
                    continue
                film = film_of(title)
                if not film:            # the software, or a conference talk
                    continue

            year = year_of(d) or (BLENDER_FILMS.get(film) if film else None)
            if year is None or year < FLOOR_YEAR:
                continue
            elif label == "nasa":
                if not is_prose(title) or NASA_DROP.search(title):
                    continue

            seen.add(ident)
            out.append({"id": ident, "title": title, "year": year,
                        "src": label, "film": film or norm_key(title),
                        "downloads": d.get("downloads") or 0})
            kept += 1
        print(f"  {label:<8}{len(docs):>5} found  {kept:>4} in date and shape")
    return out


def resolve(cands):
    """Duration and the widest MP4 for each; drop anything under the floor."""
    with ThreadPoolExecutor(max_workers=16) as ex:
        got = list(ex.map(best_mp4, [c["id"] for c in cands]))

    best = {}
    for c, res in zip(cands, got):
        if not res:
            continue
        file, dur, w, h = res
        if w < MIN_WIDTH or not BAND[0] <= dur <= BAND[1]:
            continue
        if c["src"] == "nasa" and dur < NASA_MIN_DUR:
            continue
        if c["src"] == "named" and dur < NAMED_MIN_DUR:
            continue                    # a trailer, a scene, a press clip
        it = {"id": c["id"], "file": file, "title": harvest.clean(c["title"]),
              "year": c["year"], "dur": round(dur, 2),
              "kind": c["src"], "res": f"{w}x{h}", "w": w}
        if harvest.blocked(it):
            continue
        best.setdefault(c["film"], []).append(it)

    # One entry per film. Eleven uploads of Big Buck Bunny is not eleven
    # programmes -- but "keep the widest" alone put a two-minute 1080p clip of
    # The Internet's Own Boy on the channel in place of the 105-minute film.
    # Copies of a film run about as long as each other, so length settles what
    # the programme *is* and width only settles which copy of it to play.
    picked = []
    for copies in best.values():
        longest = max(c["dur"] for c in copies)
        full = [c for c in copies if c["dur"] >= longest * 0.9]
        picked.append(max(full, key=lambda c: c["w"]))
    best = picked

    items = best
    # NASA is capped after the dedupe, not during: capping first would spend
    # the allowance on whichever raw transfers happened to sort early.
    nasa = sorted((i for i in items if i["kind"] == "nasa"),
                  key=lambda i: -i["dur"])[:NASA_CAP]
    items = [i for i in items if i["kind"] != "nasa"] + nasa
    for i in items:
        i.pop("w", None)
    items.sort(key=lambda i: (i["year"], i["title"]))
    return items


def main():
    print("gathering from verified-open sources:")
    cands = gather()
    print(f"\n{len(cands)} candidates; reading files.xml for pixel sizes")
    items = resolve(cands)
    print(f"{len(items)} clear {MIN_WIDTH}px wide and are in band\n")

    with ThreadPoolExecutor(max_workers=16) as ex:
        raws = list(ex.map(describe.meta_raw, [i["id"] for i in items]))
    for it, raw in zip(items, raws):
        d = describe.clean(raw)
        if d and not describe.echoes_title(it["title"], d):
            it["desc"] = describe.shorten(d)
            it["desc_src"] = "ia"

    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)
    ch = {"num": NUM, "name": NAME, "tag": TAG, "items": items}
    data["suggested"] = [c for c in data["suggested"] if c["num"] != NUM] + [ch]
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    hrs = sum(i["dur"] for i in items) / 3600
    years = sorted(i["year"] for i in items)
    print(f"CH {NUM:02d} {NAME}: {len(items)} programmes, "
          f"{years[0]}-{years[-1]}, {hrs:.1f}h")
    for i in items:
        print(f"  {i['year']}  {i['title'][:42]:<44}{i['kind']:<9}"
              f"{i['res']:>10}{round(i['dur']/60):>5} min")


if __name__ == "__main__":
    main()
