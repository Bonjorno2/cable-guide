"""Build channels from the ia-curation project's curated lists.

`harvest.py` finds programmes by asking archive.org for a collection sorted by
downloads. That gets you popularity, not curation. This reads the output of
../ia-curation instead, where three better signals already exist:

  curators.json       129 uploader shelves scored for coherence. A person who
                      has uploaded only Turkish superhero pictures for a decade
                      is not archiving, they're curating — their shelf is a
                      channel already.
  savant_on_ia.json   800 films Glenn Erickson graded for DVD Savant, matched
                      to a free archive.org copy. A working critic's verdict.
  double_endorsed     154 films that are on a coherent shelf *and* graded. Two
                      independent judgements, neither aware of the other.

Durations come from `<id>_files.xml` on the data nodes rather than the
metadata API. That is the trick ia-curation's README documents: the API
collapses to ~1 req/sec under any concurrency, the data nodes serve ~30/sec.
"""
import json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import harvest   # reuse clean(), blocked(), parse_len()

CURATION = r"C:\Users\myerj\Desktop\ia-curation"
DATA = os.path.join(CURATION, "data")
UA = {"User-Agent": "cable-guide-harvester/1.0"}
MP4 = ["h.264 IA", "h.264", "MPEG4", "512Kb MPEG4", "HiRes MPEG4"]

FEATURE = (1500, 11000)     # 25 min – 3 hours
SHORTS  = (45, 2400)        # a reel to 40 minutes
MIXED   = (240, 11000)
LONG    = (240, 22000)      # drive-in *double* features run past three hours

# Curator shelves. Resolved by matching text, not by a hand-copied identifier:
# the keys in names.json are 40+ character archive.org identifiers and
# transcribing them is how five channels silently came back empty first time.
#   ("name", s) matches a substring of the editorial name in names.json
#   ("top",  s) matches the title of the cluster's top-downloaded item, for the
#               89 coherent clusters that were never given an editorial name
# An optional seventh field is a year ceiling: the shelf is kept, but nothing
# released after that year is taken from it. A coherent shelf is one person's
# taste, and taste does not stop at the copyright line -- see CH 17.
SHELVES = [
    (16, "SHOCKER",    "Internet Drive-In double features",
     ("name", "Shocker Internet"), LONG, 60),
    # Capped at 1977. The shelf runs to 1996 and the late end is where the
    # exposure is: The Silence of the Lambs, Bad Moon, Tenebre, the Fulci
    # zombie pictures. Pruned rather than cut, because the Hammer and giallo
    # half is the reason the shelf scored, and it is old enough to be safe.
    (17, "CHILLER",    "Hammer, giallo and the nasty years",
     ("name", "Retro Chiller"), FEATURE, 110, 1977),
    (18, "SILENT",     "The complete silent shelf, 1901-1928",
     ("name", "Complete Silent Shelf"), MIXED, 130),
    (19, "NOIR",       "The fn01r noir shelf, 1940-1964",
     ("name", "fn01r Noir"), FEATURE, 110),
    (20, "NOIR ALLEY", "Recordings with the intros intact, 1919-1966",
     ("name", "Intros Intact"), FEATURE, 110),
    (21, "ARGENTINO",  "Cine Argentino, 1909-2012",
     ("name", "Cine Argentino: 1,218"), FEATURE, 110),
    (22, "TRICK FILMS", "Melies, Chomon and the cinema of attractions",
     ("name", "Trick Films"), SHORTS, 110),
    (23, "CHAPLIN",    "The Keystone-to-Mutual shorts, 1914-1949",
     ("name", "Chaplin: The Keystone"), SHORTS, 60),
    (24, "KEYSTONE",   "Mabel Normand, Sennett and silent comedy",
     ("name", "Keystone and After"), SHORTS, 110),
    (25, "MOSFILM",    "Soviet popular cinema, 1956-1998",
     ("name", "Mosfilm and Lenfilm"), FEATURE, 60),
    (26, "GREEK",      "Greek cinema, 1948-1985",
     ("name", "Greek Cinema"), FEATURE, 60),
    (27, "KILINK",     "Turkish pop cinema: Kilink, Batman and the Supermen",
     ("name", "Turkish Pop Cinema"), MIXED, 40),
    (28, "ANARQUISMO", "Spanish libertarian cinema",
     ("name", "Anarquismo"), MIXED, 40),
    (29, "MOMMARTZ",   "Lutz Mommartz: German experimental, 1964-2013",
     ("name", "Lutz Mommartz"), SHORTS, 60),
    (30, "MONSTRUOS",  "Universal monsters, doblada al espanol",
     ("name", "Universal Monsters"), FEATURE, 40),
    (31, "ARMY/NAVY",  "US Army and Navy training films, 1942-1961",
     ("name", "Army and Navy"), MIXED, 60),
    (32, "KATZMAN",    "Sam Katzman's bench: East Side Kids to monster imports",
     ("name", "Sam Katzman"), FEATURE, 50),
    (33, "CINE NEGRO", "Noir in Spanish, 1932-1970",
     ("name", "Cine Negro"), FEATURE, 40),
    (35, "SERIALS",    "Colourized serials, monsters and B-pictures",
     ("name", "Colourized and Upscaled"), MIXED, 110),
    (36, "SILENT HD",  "The silent canon in HD, 1915-1932",
     ("name", "Silent Canon in HD"), MIXED, 110),
    (37, "EN COULEUR", "DeOldify: European classics in colour",
     ("name", "DeOldify"), MIXED, 90),
    # 38 NIHON, "Contemporary Japanese", is deliberately absent. The shelf is
    # coherent and scored well -- it is 2001-2022 Japanese cinema, which is
    # exactly the problem: those are licensed releases somebody uploaded, not
    # films that fell out of copyright. Being on archive.org is not the same as
    # being free to rebroadcast, and the guide is a public page that lists them
    # by title and plays them unattended. Do not re-add it from the score alone.
    (39, "CALIGARI",   "Expressionism to noir, 1919-1960",
     ("name", "Black-and-White Benchmarks"), FEATURE, 46),
    (40, "BOGART",     "The Bogart shelf, and friends",
     ("name", "Bogart Shelf"), FEATURE, 35),
    (41, "FEUILLADE",  "Les Vampires, and films named for their directors",
     ("name", "Les Vampires"), MIXED, 26),
    (42, "SIODMAK",    "Director-forward noir: Siodmak, Mann, Wilder",
     ("name", "Director-Forward Noir"), FEATURE, 25),
    (43, "GRAHAME",    "Gloria Grahame and the second-tier noir bench",
     ("name", "Gloria Grahame"), FEATURE, 20),
    (44, "BAD MOVIE",  "Weirdness bad movie night",
     ("name", "Bad Movie Night"), MIXED, 21),
    (45, "VERNE",      "Jules Verne on film, and D.O.A. in four languages",
     ("name", "Jules Verne"), MIXED, 12),
    (46, "COLOURIZED", "Colourized silents and early talkies, 1924-1940",
     ("name", "Colourized Silents"), MIXED, 25),
    # --- coherent shelves the curation found but never named ---
    (47, "THE RANGE",  "B-westerns: Buck Jones, Tim McCoy, John Wayne",
     ("top", "War of the Wildcats"), FEATURE, 20),
    (48, "CHAN",       "Charlie Chan and early sound mysteries",
     ("top", "The Chinese Ring"), FEATURE, 26),
    (49, "THE SHADOW", "Detectives, murder and Lamont Cranston",
     ("top", "The Sphinx"), FEATURE, 14),
    (50, "POLIZIESCO", "Italian crime and thrillers",
     ("top", "Diabolik"), FEATURE, 12),
    # Three small shelves pooled into one channel. Separately they ran 8–9
    # items each — a four-hour loop, and shorts of ~16 minutes tile so badly
    # into half-hour slots that one shelf came out 43% commercials. Together
    # they are a proper short-subjects block, which is how they aired anyway.
    (51, "SHORT SUBJECTS", "Stooges, Our Gang and the Little Rascals",
     [("top", "Dopey Dicks"), ("top", "Sunday Calm"), ("top", "Little Rascals")],
     MIXED, 50),
    (53, "LLOYD & CO", "Lloyd, Chaplin, Snub Pollard: silent comedy, 1900-1923",
     ("top", "The Pilgrim"), SHORTS, 110),
]

# Shelves excluded on purpose. Every one of these was found by *sampling the
# titles*, not by a keyword filter — which is the whole lesson here, since a
# denylist would have caught almost none of them:
#   Grindhouse International (204) — sexploitation: Love Camp 7, Girl Camp,
#     Nekromantik. One title of 204 trips a keyword filter.
#   Third Reich cinema (1187) — headed by "Europa: The Last Battle", a
#     neo-Nazi Holocaust-denial film. Not a film shelf; propaganda.
#   "In the Realm of the Senses" shelf (422) — unsimulated sex.
#   Maigret/French grab-bag (21) — top item is 1970s softcore.
#   svtplay (91) and legendado (162) — ripped in-copyright broadcasts.
#   Race films / nudie-cuties (13) — the shelf conflates the two.
EXCLUDE_NAME = ["Grindhouse International", "Maigret"]
EXCLUDE_TOP = ["EUROPA THE LAST BATTLE", "In The Realm Of The Senses",
               "Eraserhead", "Alien (1979)", "Teaserama", "House On Bare Mountain",
               "Last Kungfu Monk", "Carne"]


def files_xml(ident):
    """Duration + playable derivative, straight off the data nodes."""
    url = f"https://archive.org/download/{ident}/{ident}_files.xml"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=40) as r:
            root = ET.fromstring(r.read())
    except Exception:
        return None
    best = {}
    for f in root.findall("file"):
        name = f.get("name") or ""
        fmt = f.findtext("format")
        dur = harvest.parse_len(f.findtext("length"))
        if fmt in MP4 and dur and name.lower().endswith(".mp4"):
            best.setdefault(fmt, (name, dur))
    for fmt in MP4:
        if fmt in best:
            return best[fmt]
    return None


def make(rec, band, taken, grade=None, director=None):
    """rec: {identifier,title,year} -> playable item dict, or None."""
    ident = rec["identifier"]
    if ident in taken:
        return None
    got = files_xml(ident)
    if not got:
        return None
    name, dur = got
    if not (band[0] <= dur <= band[1]):
        return None
    title = harvest.clean(str(rec.get("title") or ident))
    if not title:
        return None
    item = {"id": ident, "file": name, "title": title,
            "year": rec.get("year"), "dur": round(dur, 2)}
    if grade:
        item["grade"] = grade
    if director:
        item["dir"] = director
    if harvest.blocked(item):
        return None
    return item


def gather(recs, band, taken, cap, grades=None, dirs=None):
    recs = [r for r in recs if r["identifier"] not in taken]
    out = []
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs = [ex.submit(make, r, band, taken,
                          (grades or {}).get(r["identifier"]),
                          (dirs or {}).get(r["identifier"])) for r in recs]
        for f in futs:
            it = f.result()
            if not it:
                continue
            key = it["title"].lower()
            if it["id"] in taken or key in taken:
                continue
            taken.add(it["id"]); taken.add(key)
            out.append(it)
            if len(out) >= cap:
                break
    return out


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def load_names():
    with open(os.path.join(CURATION, "names.json"), encoding="utf-8") as f:
        n = json.load(f)
    n.pop("_readme", None)
    return n


def main():
    curators = load("curators.json")
    savant   = load("savant_on_ia.json")
    double   = load("double_endorsed.json")

    def top_item(c):
        return max(c["items"], key=lambda i: i.get("downloads") or 0)
    names = load_names()

    def excluded(c):
        nm = names.get(top_item(c)["identifier"], {}).get("name", "")
        tt = top_item(c)["title"]
        return (any(x.lower() in nm.lower() for x in EXCLUDE_NAME)
                or any(x.lower() in tt.lower() for x in EXCLUDE_TOP))

    pool = [c for c in curators if not excluded(c)]

    def resolve(matcher):
        how, needle = matcher
        needle = needle.lower()
        for c in pool:
            hay = (names.get(top_item(c)["identifier"], {}).get("name", "")
                   if how == "name" else top_item(c)["title"])
            if needle in hay.lower():
                return c
        return None

    # keep the existing non-feature channels; the curation is all features
    with open("channels.json", encoding="utf-8") as f:
        existing = json.load(f)
    # 52 is sitcom.py's, and it is kept for the same reason as the rest: the
    # curation is all features, so nothing here would rebuild it. Leaving it
    # out means a routine `curated.py` refresh silently deletes the channel.
    KEEP = {2, 3, 6, 7, 8, 9, 13, 14, 52}
    out = {"interstitials": existing["interstitials"],
           "channels": [c for c in existing["channels"] if c["num"] in KEEP]}

    taken = set()
    harvest.claim(out, taken)
    print(f"keeping {len(out['channels'])} existing channels, "
          f"{len(taken)//2} items claimed\n", file=sys.stderr)

    def add(num, name, tag, items, band, cap, grades=None, dirs=None, note=""):
        got = gather(items, band, taken, cap, grades, dirs)
        print(f"  CH {num:02d} {name:<12} {len(got):>4} of {len(items):<5} {note}",
              file=sys.stderr)
        if len(got) >= 4:
            out["channels"].append({"num": num, "name": name, "tag": tag,
                                    "items": got})

    # --- the two critic-backed channels, best signal first ---
    dg = {d["ia"]["identifier"]: d["movie"] for d in double}
    dd = {d["ia"]["identifier"]: d.get("director") for d in double}
    add(15, "DOUBLE", "Endorsed twice, independently",
        [dict(identifier=d["ia"]["identifier"], title=d["title"], year=d["year"])
         for d in double], MIXED, 160, dg, dd, "(curator shelf x critic grade)")

    sg = {s["ia"]["identifier"]: s["movie"] for s in savant}
    sd = {s["ia"]["identifier"]: s.get("director") for s in savant}
    order = {"Excellent": 0, "Very Good": 1, "Good": 2, "Fair": 3, "Poor": 4}
    savant.sort(key=lambda s: order.get(s["movie"], 9))
    add(34, "SAVANT", "Graded by DVD Savant, free to watch",
        [dict(identifier=s["ia"]["identifier"], title=s["title"], year=s["year"])
         for s in savant], MIXED, 170, sg, sd, "(Erickson's grades)")

    # --- the curator shelves ---
    for num, name, tag, matcher, band, cap, *rest in SHELVES:
        upto = rest[0] if rest else None
        ms = matcher if isinstance(matcher, list) else [matcher]
        items, missed = [], []
        for m in ms:
            c = resolve(m)
            if c:
                items += c["items"]
            else:
                missed.append(m)
        if missed:
            print(f"  CH {num:02d} {name:<14} NO MATCH for {missed}", file=sys.stderr)
        if not items:
            continue
        if upto:
            # No year is not old enough. Every item on the one shelf this
            # applies to carries one, so nothing is lost to caution here, and
            # a shelf that stops dating its uploads is exactly the case where
            # guessing would be worst.
            n = len(items)
            items = [i for i in items
                     if isinstance(i.get("year"), int) and i["year"] <= upto]
            print(f"  CH {num:02d} {name:<14} {n - len(items)} dropped "
                  f"as post-{upto}", file=sys.stderr)
        items.sort(key=lambda i: -(i.get("downloads") or 0))
        add(num, name, tag, items, band, cap)

    out["channels"].sort(key=lambda c: c["num"])
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    total = sum(len(c["items"]) for c in out["channels"])
    print(f"\n{len(out['channels'])} channels, {total} programmes", file=sys.stderr)


if __name__ == "__main__":
    main()
