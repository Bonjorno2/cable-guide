"""Re-sculpt CH 16 SHOCKER into the programme it already was.

`curated.py` harvests this shelf the way it harvests the other forty: take the
uploader's items, resolve a playable file, hand the set to `packChannel()`,
which fills half-hours longest-first and then shuffles on a seed. That is the
right thing to do to a *set*. This shelf is not a set.

ia-curation found it by coherence scoring and its README says what it is —
"113+ numbered weeks of themed double features. Not a collection, a
*programme*." One person ran an internet drive-in weekly from August 2010 to
January 2021: every item is a whole night, one video file carrying two or three
features plus trailers, snack-bar ads, an intermission and a cartoon.

Three things that programme knows and the shuffled channel throws away:

  the order      The weeks are numbered, and the numbering is real: sorted by
                 week, the 51 uploads are in date order with exactly one
                 exception, `Week 7 REDO`, which is a re-upload of week 7's
                 slot and belongs there rather than at its own upload date.
                 So week number is the broadcast slot, and it is what this
                 file sorts on.

  the calendar   The programmer wrote to the year. Sixteen weeks name a season
                 or a holiday and all sixteen were uploaded in the month they
                 name -- Christmas in December, Halloween in October, Mother's
                 Day in May, "Springtime For Starman" Parts 1 and 2 three weeks
                 apart in April. A shuffle puts the Christmas triple between
                 two summer slasher nights and can play Part 2 before Part 1.
                 In broadcast order the seasons come round in order, and the
                 two-parter is adjacent by construction.

  the bill      Every listing currently reads `Shocker Internet Drive In -
                 Week NN: ...`, so in a guide grid fifty rows open with the
                 same thirty characters and none of them says what is on.
                 The uploader does say, in the item description, and `bill()`
                 below takes the two or three features out of it.

None of this re-harvests anything: the identifiers, files and durations are
`curated.py`'s, already resolved and verified, and are used as written.

Run after `curated.py` and before `describe.py`. The blurb `describe.py` writes
is carried across untouched; the bill is re-read from archive.org each run,
which is fifty items off the data nodes.
"""
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

CURATION = r"C:\Users\myerj\Desktop\ia-curation"
CATALOGS = ("catalog_moviesandfilms.jsonl", "catalog.jsonl")
UPLOADER = "hurstst2@verizon.net"

UA = {"User-Agent": "cable-guide-harvester/1.0"}
SLOT = 1800
MINBREAK = 30            # keep in step with template.html and build.py
NUM = 16
NAME = "SHOCKER"
TAG = "The Internet Drive-In, in broadcast order"

WEEK = re.compile(r"week\s*[-~]?\s*(\d{1,3})", re.I)
# "Shocker Internet Drive In - Week 18: " and the variants eleven years of
# typing produced: "~ Week 36:", "Week 3 -", "REVISED-... Week 7 REDO -".
BOILER = re.compile(r"(?i)^\s*(?:revised\s*-\s*)?shocker\s+internet\s+drive\s*-?\s*in"
                    r"\s*[-~:]?\s*")


def slots_for(dur):
    """Half-hours a programme needs. Mirrors packChannel()."""
    return max(1, -(-(dur + MINBREAK) // SLOT))


def week_of(title):
    m = WEEK.search(title)
    return int(m.group(1)) if m else None


def retitle(title):
    """`Week 18: A Naschy Double Feature` -- the part that differs."""
    t = BOILER.sub("", title).strip(" -~:")
    t = re.sub(r"(?i)^week\s*[-~]?\s*(\d{1,3})", r"Week \1", t)
    t = t.strip(" -~:")
    # The uploader quotes his own theme names; the guide already renders them
    # as a title, so the quotes are noise. Strip unpaired ones too.
    t = re.sub(r"[\"“](.+?)[”\"]", r"\1", t)
    t = t.replace('"', "").replace("“", "").replace("”", "")
    return re.sub(r"\s+", " ", t).strip()


def tidy(t):
    """A shift key held a beat too long: `Night of the LIving Dead`."""
    return re.sub(r"\b([A-Z])([A-Z])([a-z]{2,})", lambda m:
                  m.group(1) + m.group(2).lower() + m.group(3), t)


# ---------------------------------------------------------------- the bill

def totext(d):
    d = re.sub(r"(?is)<(script|style).*?</\1>", " ", d)
    d = re.sub(r"(?i)<br\s*/?>|</p>", "\n", d)
    d = re.sub(r"<[^>]+>", " ", d)
    d = html.unescape(d).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", d).strip()


# Everything from here on is the drive-in's own promotion, not the programme.
TAIL = re.compile(r"(?im)^\s*(?:new\s+)?facebook\b|^\s*website\s*:|https?://|www\.")
QUOTED = re.compile(r"[\"“]([^\"“”]{2,60})[”\"]")

# A feature is announced. Eleven years of prose, one house style: the films are
# the objects of these verbs and the extras never are.
PRESENTS = re.compile(
    r"(?i)\b(?:"
    r"bring(?:s|ing)?\s+(?:you|us|out)|"
    r"present(?:ing|s)?|"
    r"followed by|"
    r"(?:first|second|third|fourth|fifth|final|last|next)\s+"
    r"(?:feature|movie|film|flick|picture)\s+is|"
    r"finish(?:es|ing)?\s+(?:things\s+)?up\s+with|"
    r"finish(?:ing)?\s+out|clos(?:e|es|ing)\s+out|conclude[sd]?|"
    r"begin(?:s|ning)?\s+(?:the\s+fun\s+)?with|get right to it with|"
    r"continue[sd]?\s+with|start(?:s|ing)?\s+(?:off\s+|things\s+off\s+)?with|"
    r"first up|next up|double bill|"
    r"we\s+(?:also|then|proudly|happily|gladly|encourage|invite|offer)"
    r")\b")

# Marked as not-the-feature in the words around the quote.
SUPPORT_AFTER = re.compile(r"(?i)^\W{0,4}(cartoon|short|reel|trailer|promo)")
SUPPORT_BEFORE = re.compile(
    r"(?i)(short\s+subject|\bshort\b|cartoon|coming attraction|preview|trailer|"
    r"advertisement|newsreel|intermission|snack\s*bar|remake of|sequel to|"
    r"days of|or even|prequel to|double feature in|feature in|starring|"
    r"also known as|a\.?k\.?a\.?|\bor\b\s*$)\W{0,4}$")


# "Double Feature", "Triple Treat", "Bela Lugosi Triple Threats", "Multi-Feature".
COUNTED = re.compile(r"(?i)\b(double|triple|quadruple|multi)[-\s]*"
                     r"(?:feature|treat|bill|threat)s?\b")


def count_in(text):
    m = COUNTED.search(text or "")
    return {"double": 2, "triple": 3, "quadruple": 4}.get(
        m.group(1).lower()) if m else None


def norm(s):
    s = html.unescape(s).lower()
    s = re.sub(r"[’']", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"^(?:the|a|an) ", "", s)


def sentences(t):
    """Split on real sentence ends only.

    The lookbehind is load-bearing: splitting on every `. ` cuts "the George A.
    Romero classic" in half and strands Night of the Living Dead in a fragment
    with no verb in it, so the week bills nothing. A full stop after a single
    capital is an initial, not an end.
    """
    return [s for s in re.split(r"(?<![A-Z].)(?<=[.!?])\s+|\n+", t) if s.strip()]


def bill(desc, title, known):
    """The features on a night, out of the barker prose that announces them.

    Quoted strings in this shelf are films, theme names, nicknames and plain
    emphasis all at once -- one week quotes "witch" five times. Three gates,
    and a candidate has to pass all three:

      it is a film      the quoted text matches a title archive.org actually
                        holds. This alone removes every quoted adjective
                        ("racist", "massive", "staticky") without a word list.
      it is announced   it sits in a clause that presents something. "Star
                        Wars" survives the first gate and is a comparison --
                        "guaranteed to make you yearn for the good old days of".
      it is the feature the words touching it do not mark it as support. The
                        cartoon, the short subject and the alternate title in
                        brackets are all films too: "The City of The Dead" (or
                        "Horror Hotel") is one picture with two names.

    Returns [] rather than a guess. A listing that bills a Popeye cartoon as
    half the double feature is worse than one that bills nothing, and the
    uploader's own blurb is still there to describe the night.
    """
    t = totext(desc or "")
    cut = TAIL.search(t)
    body = t[: cut.start()] if cut else t
    # No rule here rejects a candidate for matching the night's own name.
    # `Week 4 - Night of the Living Dead Double Feature` is titled after the
    # film it opens with, so a theme test strict enough to drop `Week 13`'s
    # quoted "Demented" also drops Romero. The week's own name being quoted at
    # it is left to the count check, which fails closed.

    out, seen = [], set()
    for s in sentences(body):
        if not PRESENTS.search(s):
            continue
        for m in QUOTED.finditer(s):
            q = m.group(1).strip().strip(".,;:!?-–— ")
            n = norm(q)
            if not n or n in seen or q == q.lower():
                continue
            if n not in known:
                continue
            if SUPPORT_BEFORE.search(s[: m.start()]) or \
               SUPPORT_AFTER.match(s[m.end():]):
                continue
            seen.add(n)
            out.append(tidy(q))

    # The week says how many it is showing, and where it does and we disagree
    # we have mis-read the prose -- saying so is the whole point of the check.
    # The blurb outranks the title when they differ: week 41 is headed "Boo's
    # For Bela Double Feature" and then shows three Lugosi pictures.
    want = count_in(body) or count_in(title)
    if want and len(out) != want:
        return []
    return out if len(out) >= 2 else []


# ---------------------------------------------------------------- inputs

def catalog_titles():
    """Every film title archive.org holds, normalised. ia-curation's scrape."""
    known = set()
    for name in CATALOGS:
        path = os.path.join(CURATION, "data", name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                t = json.loads(line).get("title")
                if isinstance(t, str):
                    n = norm(re.sub(r"\s*\(?(?:19|20)\d\d\)?\s*$", "", t))
                    if n:
                        known.add(n)
    if not known:
        sys.exit(f"no catalog under {CURATION}\\data -- has scrape_catalog.py run?")
    return known


def shelf_titles():
    """The uploader's items, as ia-curation's coherence scoring found them.

    Keyed to the *untruncated* title, which is the reason to come here rather
    than read what is already in channels.json. `harvest.clean()` caps a title
    at 70 characters, and on this shelf thirty of those are the boilerplate
    prefix every week shares, so eight nights arrive cut mid-word -- "Woof Woof
    A Father's Day Specia". Stripping the prefix after the cut cannot put them
    back; taking the title from here and stripping it first can.
    """
    path = os.path.join(CURATION, "data", "curators.json")
    with open(path, encoding="utf-8") as f:
        for c in json.load(f):
            if c["uploader"] == UPLOADER or UPLOADER in c.get("accounts", []):
                return {i["identifier"]: i["title"] for i in c["items"]}
    sys.exit(f"{UPLOADER} is not a cluster in curators.json")


def meta_description(ident):
    """Off the data nodes: ~0.8s against ~33s for the metadata API."""
    url = f"https://archive.org/download/{ident}/{ident}_meta.xml"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=45) as r:
            raw = r.read()
    except Exception:
        return ident, None
    try:
        # Explicit, because the guide's own copy of these blurbs carries a
        # U+FFFD where the uploader typed a curly apostrophe.
        root = ET.fromstring(raw.decode("utf-8", "replace"))
    except ET.ParseError:
        return ident, None
    return ident, "\n".join(e.text or "" for e in root.findall("description"))


# ---------------------------------------------------------------- build

def main():
    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)

    ch = next((c for c in data["channels"] if c["num"] == NUM), None)
    if not ch or not ch.get("items"):
        sys.exit(f"CH {NUM} is not in channels.json -- run curated.py first")

    items = [dict(i) for i in ch["items"]]
    on_shelf = shelf_titles()
    stray = [i["id"] for i in items if i["id"] not in on_shelf]
    if stray:
        print(f"  {len(stray)} item(s) not on the shelf: {stray}", file=sys.stderr)
    for it in items:
        it["title"] = on_shelf.get(it["id"], it["title"])

    unnumbered = [i for i in items if week_of(i["title"]) is None]
    if unnumbered:
        sys.exit("no week number on: " + ", ".join(i["title"] for i in unnumbered))

    # Re-read every week rather than trusting the `feat` already on the item:
    # the bill is parsed, the parser is the part of this that will change, and
    # a cached miss would survive the fix that was written to catch it.
    with ThreadPoolExecutor(max_workers=4) as ex:
        descs = dict(ex.map(meta_description, [i["id"] for i in items]))
    failed = [k for k, v in descs.items() if not v]
    if failed:
        print(f"  {len(failed)} description(s) unread, bill kept: {failed}",
              file=sys.stderr)

    known = catalog_titles()
    billed = 0
    for it in items:
        if descs.get(it["id"]):
            got = bill(descs[it["id"]], it["title"], known)
            # An unread description leaves last run's bill alone; a read one
            # that yields nothing retracts it.
            it.pop("feat", None)
            if got:
                it["feat"] = got
        it["title"] = retitle(it["title"])
        if it.get("feat"):
            billed += 1

    items.sort(key=lambda i: week_of(i["title"]))
    blocks = [[1, int(slots_for(i["dur"]))] for i in items]

    data["channels"] = [c for c in data["channels"] if c["num"] != NUM]
    data["channels"].append({"num": NUM, "name": NAME, "tag": TAG,
                             "items": items, "blocks": blocks})
    data["channels"].sort(key=lambda c: c["num"])
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    cycle = sum(b[1] for b in blocks) * SLOT
    content = sum(i["dur"] for i in items)
    weeks = [week_of(i["title"]) for i in items]
    print(f"CH {NUM:02d} {NAME}: {len(items)} nights, weeks {weeks[0]}-{weeks[-1]}, "
          f"{cycle/3600:.1f}h cycle, {(1-content/cycle)*100:.0f}% ads",
          file=sys.stderr)
    print(f"  billed with their features {billed:>3} of {len(items)}",
          file=sys.stderr)
    print(f"  longest night {max(i['dur'] for i in items)/3600:.1f}h",
          file=sys.stderr)


if __name__ == "__main__":
    main()
