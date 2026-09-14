"""Harvest channel lineups from Internet Archive collections.

Writes channels.json: for each channel, a playlist of items with exact
durations and a direct MP4 derivative URL. Run this to refresh lineups;
the site itself makes no API calls at runtime.

The metadata API is rate-limited to roughly one request a second no matter how
many threads you throw at it, so probe count — not parallelism — is what sets
the runtime. The search API, by contrast, returns hundreds of docs per request
and includes a `runtime` field for ~95% of items. So: pull a large candidate
pool from search, drop anything whose advertised runtime is outside the
channel's band, and only then spend a probe confirming the exact duration and
finding a playable derivative. That takes the probe hit rate from ~20% to ~85%.
"""
import json, re, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "cable-guide-harvester/1.0"}
SEARCH = "https://archive.org/advancedsearch.php"
META = "https://archive.org/metadata/"

# Preferred derivative formats, best first. All are browser-playable MP4.
MP4_FORMATS = ["h.264 IA", "h.264", "MPEG4", "512Kb MPEG4", "HiRes MPEG4"]

PAGE = 500          # search results per request
PROBE_SLACK = 1.35  # probe this many times `want`, to absorb misses

CHANNELS = [
    dict(num=2,  name="PRELINGER",  tag="Ephemeral & industrial film",
         query='collection:"prelinger" AND mediatype:movies',
         lo=240,  hi=1800, want=200),
    dict(num=3,  name="SATURDAY AM", tag="Classic theatrical cartoons",
         query='(collection:"classic_cartoons" OR collection:"more_animation") AND mediatype:movies',
         lo=200,  hi=1200, want=240),
    dict(num=4,  name="NIGHT OWL",  tag="Late-night creature feature",
         query='collection:"feature_films" AND mediatype:movies AND '
               '(subject:"horror" OR subject:"science fiction" OR subject:"sci-fi")',
         lo=3300, hi=7800, want=80),
    # ...and MATINEE takes everything that is *not* a creature feature, so the
    # two film channels do not end up showing each other's lineup.
    dict(num=5,  name="MATINEE",    tag="Public domain features",
         query='collection:"feature_films" AND mediatype:movies AND NOT '
               '(subject:"horror" OR subject:"science fiction" OR subject:"sci-fi")',
         lo=3300, hi=7800, want=80),
    dict(num=6,  name="CHRONICLES", tag="The Computer Chronicles",
         query='collection:"computerchronicles" AND mediatype:movies',
         lo=1200, hi=1800, want=200),
    dict(num=7,  name="NEWSREEL",   tag="Universal Newsreels",
         query='collection:"universal_newsreels" AND mediatype:movies',
         lo=200,  hi=900,  want=250),
    dict(num=8,  name="A/V CLUB",   tag="Classroom & training films",
         query='collection:"avgeeks" AND mediatype:movies',
         lo=300,  hi=2400, want=180),
    dict(num=9,  name="THE VAULT",  tag="Television past",
         query='collection:"classic_tv" AND mediatype:movies',
         lo=600,  hi=3600, want=150),
    dict(num=10, name="SILENT",     tag="Silent cinema",
         query='collection:"silent_films" AND mediatype:movies',
         lo=600,  hi=7800, want=120),
    dict(num=11, name="NOIR ALLEY", tag="Shadows and venetian blinds",
         query='collection:"feature_films" AND mediatype:movies AND '
               '(subject:"film noir" OR subject:"noir")',
         lo=3300, hi=7800, want=80),
    dict(num=12, name="THE RANGE",  tag="Public domain westerns",
         query='collection:"feature_films" AND mediatype:movies AND subject:"western"',
         lo=3300, hi=7800, want=80),
    dict(num=13, name="HOME MOVIES", tag="Other people's memories",
         query='collection:"home_movies" AND mediatype:movies',
         lo=180,  hi=1800, want=140),
    dict(num=14, name="MISSION CTRL", tag="NASA film & mission footage",
         query='collection:"nasa" AND mediatype:movies',
         lo=300,  hi=3600, want=140),
]

# Short spots used to fill the breaks.
INTERSTITIAL = dict(
    query='collection:"classic_tv_commercials" AND mediatype:movies',
    lo=15, hi=120, want=150)

# Open collections carry mis-filed and genuinely unpleasant uploads. Matched
# against identifier + title, case-insensitively.
#
# Two collections were scouted and rejected outright rather than filtered:
# `vhsvault` (real suicide footage among its top downloads) and
# `videogamecommercials` (NSFW items on the first page of results). Neither is
# worth the risk of a keyword list catching only what I thought to name.
DENY = [
    "quran", "playboy", "banned commercial", "godaddy",
    "sex", "xxx", "nude", "nudist", "nudie", "porn", "erotic", "nsfw",
    "strip tease", "striptease", "burlesque",
    "test upload", "test pattern", "please delete",
    # violent or graphic material that surfaces in open film collections
    "suicide", "budd dwyer", "graphic warning", "execution", "beheading",
    "autopsy", "lynching", "atrocity",
    # films whose content makes them a poor fit for unattended scheduling
    "birth of a nation", "pink flamingos",
]


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
        return json.load(r)


def search(query, rows):
    """Page through search results, newest-most-popular first."""
    out, page = [], 1
    while len(out) < rows:
        qs = urllib.parse.urlencode({
            "q": query, "sort[]": "downloads desc",
            "rows": min(PAGE, rows - len(out)), "page": page, "output": "json",
        }, doseq=True) + "&fl[]=identifier&fl[]=title&fl[]=year&fl[]=runtime"
        docs = get(f"{SEARCH}?{qs}")["response"]["docs"]
        if not docs:
            break
        out.extend(docs)
        page += 1
    return out


def parse_len(v):
    """Archive durations: seconds ('394.83'), 'H:MM:SS', or '6 min 34 sec'."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if ":" in s:
        try:
            out = 0.0
            for p in s.split(":"):
                out = out * 60 + float(p)
            return out
        except ValueError:
            return None
    m = re.findall(r"(\d+(?:\.\d+)?)\s*(h|hour|min|sec|m|s)", s, re.I)
    if m:
        mult = {"h": 3600, "hour": 3600, "m": 60, "min": 60, "s": 1, "sec": 1}
        return sum(float(n) * mult[u.lower()] for n, u in m)
    try:
        return float(s)
    except ValueError:
        return None


def blocked(item):
    hay = (item["id"] + " " + item["title"]).lower()
    return any(w in hay for w in DENY)


def probe(doc):
    """Fetch metadata; return a playable item dict or None."""
    try:
        d = get(META + doc["identifier"])
    except Exception:
        return None
    files = d.get("files") or []
    if not d.get("metadata"):
        return None

    best = None
    for fmt in MP4_FORMATS:
        for f in files:
            if f.get("format") != fmt or not f.get("name", "").lower().endswith(".mp4"):
                continue
            dur = parse_len(f.get("length"))
            if dur:
                best = (f["name"], dur)
                break
        if best:
            break
    if not best:
        return None

    name, dur = best
    title = doc.get("title") or d["metadata"].get("title") or doc["identifier"]
    if isinstance(title, list):
        title = title[0]
    year = doc.get("year") or d["metadata"].get("year")
    if isinstance(year, list):
        year = year[0]
    try:
        year = int(str(year)[:4])
    except Exception:
        year = None

    return {"id": doc["identifier"], "file": name,
            "title": clean(str(title)), "year": year, "dur": round(dur, 2)}


def clean(t):
    t = re.sub(r"\s+", " ", t).strip()
    # Uploaders in the feature-film collections often title an item
    # "Laura (1944) Dir: Otto Preminger, Starring Gene Tierney, ...". Where a
    # parenthesised year is followed by more text, that text is cataloguing,
    # not the title — so cut at the first such year.
    m = re.match(r"^(.{3,}?)\s*[\(\[]\s*(?:19|20)\d\d\s*[,;]?\s*[\)\]]\s*\S.*$", t)
    if m:
        t = m.group(1)
    t = re.sub(r"\s*[\(\[]\s*(?:19|20)\d\d\s*[,;]?\s*[\)\]]\s*$", "", t)  # trailing year
    # "... [1:24:59] Charles Laughton" — a bracketed runtime and whatever follows
    t = re.sub(r"\s*\[\s*\d{1,2}:\d{2}(?::\d{2})?\s*\].*$", "", t)
    # NOTE: do not try to cut at a *bare* year. Plenty of real titles contain
    # one ("Space 1999", "Big News of 1941", "Tokyo 1964 - Part 1 of 3") and
    # any rule general enough to catch the junk destroys those instead.
    t = re.sub(r"(?i)\s*\(\s*cc\s*\).*$", "", t)   # "(CC)" caption marker + trailing slugs
    t = re.sub(r"(?i)\s*[-–—|]\s*(?:full (?:movie|film|length)|complete film|"
               r"public domain|hd remaster\w*)\b.*$", "", t)
    # trailing decoration, including uploader star ratings like "★★★½"
    return t[:70].strip(" -–—:,|·•★☆⭐*_½¼¾⯨")


def build(spec, taken):
    """taken: identifiers/titles already claimed by an earlier channel."""
    docs = search(spec["query"], spec["want"] * 6)

    # Cheap pre-filter on the runtime the search API already gave us. Coverage
    # varies enormously between collections — Prelinger publishes runtime for
    # ~95% of items, the newsreel collection for ~3% — so prefer items we can
    # vet for free, then top up with blind ones where that is all there is.
    lo, hi = spec["lo"], spec["hi"]
    known, unknown = [], []
    for d in docs:
        if d["identifier"] in taken:
            continue
        rt = parse_len(d.get("runtime"))
        if rt is None:
            unknown.append(d)
        elif lo * 0.9 <= rt <= hi * 1.1:      # loose: exact duration comes from probe
            known.append(d)

    need = int(spec["want"] * PROBE_SLACK)
    cand = known[:need]
    if len(cand) < need:                      # blind probes miss far more often
        cand += unknown[: int((need - len(cand)) * 2.2)]

    out = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for item in ex.map(probe, cand):
            if not item or blocked(item):
                continue
            if not (lo <= item["dur"] <= hi):
                continue
            key = item["title"].lower()
            if item["id"] in taken or key in taken:
                continue
            taken.add(item["id"])
            taken.add(key)
            out.append(item)
    return out, len(cand)


def save(result):
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)


def claim(result, taken):
    """Seed the dedupe set from lineups we already have."""
    for group in [result["interstitials"]] + [c["items"] for c in result["channels"]]:
        for it in group:
            taken.add(it["id"])
            taken.add(it["title"].lower())


def main():
    # `python harvest.py 10,11,12` harvests only those channel numbers and
    # merges them into an existing channels.json, rather than starting over.
    only = set()
    if len(sys.argv) > 1:
        only = {int(x) for x in sys.argv[1].split(",")}

    result = {"channels": [], "interstitials": []}
    taken = set()

    if only:
        with open("channels.json", encoding="utf-8") as f:
            result = json.load(f)
        result["channels"] = [c for c in result["channels"] if c["num"] not in only]
        claim(result, taken)
        print(f"merging into {len(result['channels'])} existing channels",
              file=sys.stderr)
    else:
        print("fill spots...", file=sys.stderr)
        spots, n = build(INTERSTITIAL, taken)
        result["interstitials"] = spots[: INTERSTITIAL["want"]]
        print(f"  {len(result['interstitials'])} spots from {n} probes", file=sys.stderr)
        save(result)

    for spec in CHANNELS:
        if only and spec["num"] not in only:
            continue
        print(f"ch {spec['num']} {spec['name']}...", file=sys.stderr)
        items, n = build(spec, taken)
        items = items[: spec["want"]]
        hit = len(items) / max(n, 1) * 100
        print(f"  {len(items)} items from {n} probes ({hit:.0f}% hit)", file=sys.stderr)
        if len(items) < 4:
            print("  SKIPPED (too thin)", file=sys.stderr)
            continue
        result["channels"].append({
            "num": spec["num"], "name": spec["name"],
            "tag": spec["tag"], "items": items,
        })
        result["channels"].sort(key=lambda c: c["num"])
        save(result)   # checkpoint, so a mid-run failure keeps what we have

    print(f"\nwrote channels.json: {len(result['channels'])} channels", file=sys.stderr)


if __name__ == "__main__":
    main()
