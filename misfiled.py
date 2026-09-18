"""Build CH 11 MISFILED: the films that were skipped for having no date on them.

Every year gate in this project drops an item whose year cannot be read --
curated.py's shelf ceilings, CH 17's 1977 cap, suggest.py's silent-era line.
That is correct behaviour and it has a cost nobody was counting: on the
feature_films pool, 26,631 items reach those gates with no year at all, so they
are not rejected by any of them, they are simply never considered. A film with
an empty date field has been invisible to this guide since the first harvest.

`ia-curation/backfill_years.py` goes and gets those years out of the witnesses
the catalog scrape ignored -- the uploader's slug, the subject tag list, and
the description off the metadata API. This reads its output and programmes the
oldest, safest end of what it found.

Two rules, and both of them are the copyright rule wearing different clothes:

  the ceiling   1929. Not because the silent era is a theme -- though it makes
                one -- but because a backfilled year is a year this project
                did not have a moment ago, and a gate is only as good as the
                number fed into it. Everything here would still be out of
                copyright if its year turned out to be a decade wrong.
  read the list The standing lesson of this repo, and the reason CH 38 was cut
                and EXCLUDE_TITLE exists. A rule that admits 150 films is a
                rule you can check by hand, so it gets checked by hand.

`confidence` is carried onto every item so the dial can say where the date came
from. `agreed` means two independent witnesses named the same year; `single`
means one did, and one is one uploader's typing.

Run order:  ia-curation/backfill_years.py  ->  suggest.py  ->  misfiled.py
->  build.py   (suggest.py rewrites data["suggested"] wholesale, which drops
the channel this adds -- the same bargain suggest.py makes with curated.py.)
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import curated   # files_xml() -- duration and derivative off the data nodes
import describe  # meta_raw()/clean() -- the listing under each title
import harvest   # blocked()

CURATION = r"C:\Users\myerj\Desktop\ia-curation"
DATA = os.path.join(CURATION, "data")
BACKFILL = os.path.join(DATA, "years_backfilled.json")

sys.path.insert(0, CURATION)
from titles import clean as ia_clean  # noqa: E402  (needs the path first)

NUM, NAME = 11, "MISFILED"
TAG = "Found with no date on it · everything the year gates never saw"

CEILING = 1929
BAND = (45, 11000)          # a single reel to three hours

# Cut by name, every one found by reading the list rather than by a rule.
#   trailer / reel / outtake  not programmes. Matched on the raw title too,
#                     because ia_clean() removes the very words that condemn
#                     them -- suggest.py's EXCLUDE_TITLE makes the same point.
#   road to ruin      cut here for the reason suggest.py cuts it: a road-show
#                     exploitation picture sold as a warning and shot as the
#                     other thing. The copy here is dated 1929 rather than
#                     1928 and is the same film.
#   marken / heres to america
#                     two minutes each, no favourites, and neither is a
#                     programme -- a travelogue postcard and a filler reel.
#   the jazz singer   cut for the reason suggest.py cuts A Natural Born
#                     Gambler, and it is the same reason: Jolson is in burnt
#                     cork for the last reel. Genuinely a landmark, and a
#                     channel that runs it unannounced between two Keaton
#                     features is not the place that gets framed.
EXCLUDE_TITLE = ["trailer", "film prints", "sample reel", "test film",
                 "home movie", "screen test", "outtake", "road to ruin",
                 "peninsula of marken", "heres to america", "jazz singer"]


def excluded(raw, title):
    hay = (str(raw) + " " + str(title)).lower()
    return any(w in hay for w in EXCLUDE_TITLE)


# `ia_clean()` strips a leading number and a leading possessive, because on the
# shelves it was written for those are catalogue numbers and "Buster Keaton's".
# On this pool they are as often the film's actual name, and the cleaner hands
# back `Bad Men` for `3 Bad Men` and `Fan` for `Lady Windermere's Fan`.
#
# The tell is that nothing was *cleaned*: a raw title with no brackets, no
# dash, no cast list -- nothing for the cleaner to be removing -- that comes
# back shortened has had its name eaten, not its cataloguing. Those are handed
# back whole rather than patched by name, because the same two rules will do
# the same thing to the next shelf.
CATALOGUING = re.compile(r"[\(\[\],;|/]|\s[-–—]\s|\bdir\b|\bstarring\b", re.I)

# An identifier used as a title: `NanookOfTheNorth1922english`,
# `William_McKinley_Inauguration_1897`, `AChristmas Carol`. The two lookbehinds
# are the reason this is not a one-liner: splitting every lowercase-uppercase
# seam turns McKinley into Mc Kinley.
# Underscores have to be spaces *before* this runs, in a pass of their own:
# `_` is a word character, so in `William_McKinley` there is no word boundary
# in front of `Mc` for the lookbehind to find, and McKinley splits anyway.
RUNON = re.compile(r"(?<!\bMc)(?<!\bMac)(?<=[a-z])(?=[A-Z])")
# `AChristmas Carol` has no lowercase-uppercase seam to split on -- the article
# is welded to the front of a word that was already capitalised.
LONE_ARTICLE = re.compile(r"^([AI])(?=[A-Z][a-z])")
TRAILING_JUNK = re.compile(r"\s*(1[89]\d\d|20[0-2]\d)\s*(english|silent|hd)?$",
                           re.I)


def unclip(raw, title):
    """Give back what the cleaner ate, when it had nothing to clean."""
    raw = str(raw or "").strip().rstrip("_").strip()
    if not raw or CATALOGUING.search(raw) or len(raw) > 44:
        return title
    if title and title.lower() != raw.lower() and raw.lower().endswith(
            title.lower()):
        return raw
    return title


def respace(title):
    """`AChristmas Carol` -> `A Christmas Carol`. Only for titles that are
    plainly an identifier wearing a title's hat: an underscore, or a camelCase
    run inside a word."""
    if ("_" not in title and not re.search(r"[a-z][A-Z]", title)
            and not LONE_ARTICLE.search(title)):
        return title
    out = LONE_ARTICLE.sub(r"\1 ", title.replace("_", " "))
    out = re.sub(r"\s+", " ", RUNON.sub(" ", out)).strip()
    return TRAILING_JUNK.sub("", out).strip() or title


# Two uploads of one film do not collapse on an exact title: the shelf carries
# `Nosferatu`, `Nosferatu Rescored` and `FW Murnaus Nosferatu`. Whichever title
# is wholly contained in another, word for word, is the same picture.
NOISE = {"the", "a", "an", "of", "and", "rescored", "restored", "hd", "silent",
         "english", "version", "film", "movie", "fw", "dir", "by"}


def keywords(title):
    return frozenset(w for w in re.findall(r"[a-z0-9']+", title.lower())
                     if w not in NOISE) or frozenset([title.lower()])


def load_backfill():
    """The backfilled years, oldest first, film-shaped and under the ceiling."""
    if not os.path.exists(BACKFILL):
        sys.exit(f"no {BACKFILL} -- run ia-curation/backfill_years.py first")
    with open(BACKFILL, encoding="utf-8") as f:
        found = json.load(f)

    rows = {}
    for fn in ("catalog.jsonl", "catalog_moviesandfilms.jsonl"):
        path = os.path.join(DATA, fn)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                rows.setdefault(r["identifier"], r)

    out = []
    for ident, v in found.items():
        if v["shape"] != "film" or v["confidence"] == "conflict":
            continue
        if not v["year"] or v["year"] > CEILING:
            continue
        row = rows.get(ident)
        if not row:
            continue
        raw = row.get("title") or ""
        title, _ = ia_clean(raw)
        title = respace(unclip(raw, title))
        if not title or excluded(raw, title):
            continue
        out.append({"id": ident, "raw": row.get("title"), "title": title,
                    "year": v["year"], "confidence": v["confidence"],
                    "why": v["why"],
                    "favs": sum(1 for c in (row.get("collection") or [])
                                if c.startswith("fav-"))})
    out.sort(key=lambda r: (r["year"], -r["favs"]))
    return out


def resolve(rows, dial):
    """Duration and a playable derivative for each, off the data nodes."""
    need = [r for r in rows if r["id"] not in dial]
    got = {}
    if need:
        with ThreadPoolExecutor(max_workers=24) as ex:
            for r, res in zip(need, ex.map(curated.files_xml,
                                           [r["id"] for r in need])):
                if res:
                    got[r["id"]] = res

    items, seen = [], []
    for r in rows:
        on = dial.get(r["id"])
        if on:
            file, dur = on["file"], on["dur"]
        elif r["id"] in got:
            file, dur = got[r["id"]]
        else:
            continue
        if not BAND[0] <= dur <= BAND[1]:
            continue
        # The same picture on two uploads: whichever title's words are wholly
        # inside the other's. Keep the one more people favourited.
        key = keywords(r["title"])
        dup = next((k for k in seen if k <= key or key <= k), None)
        if dup is not None:
            continue
        it = {"id": r["id"], "file": file, "title": r["title"],
              "year": r["year"], "dur": round(dur, 2),
              "kind": r["confidence"], "favs": r["favs"]}
        if harvest.blocked(it):
            continue
        seen.append(key)
        items.append(it)
    return items


def describe_all(items):
    with ThreadPoolExecutor(max_workers=24) as ex:
        raws = list(ex.map(describe.meta_raw, [i["id"] for i in items]))
    for it, raw in zip(items, raws):
        d = describe.clean(raw)
        if d and not describe.echoes_title(it["title"], d):
            it["desc"] = describe.shorten(d)
            it["desc_src"] = "ia"
    return items


def main():
    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)
    dial = {i["id"]: i for c in data["channels"] for i in c["items"]}

    rows = load_backfill()
    print(f"{len(rows)} backfilled films at or under {CEILING}")

    items = resolve(rows, dial)
    print(f"{len(items)} of them are playable and in band")

    items = describe_all(items)

    ch = {"num": NUM, "name": NAME, "tag": TAG, "items": items}
    data["suggested"] = [c for c in data["suggested"] if c["num"] != NUM] + [ch]
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    hrs = sum(i["dur"] for i in items) / 3600
    agreed = sum(1 for i in items if i["kind"] == "agreed")
    new = sum(1 for i in items if i["id"] not in dial)
    desc = sum(1 for i in items if i.get("desc"))
    years = sorted(i["year"] for i in items)
    print(f"\nCH {NUM:02d} {NAME}: {len(items)} films, {years[0]}-{years[-1]}, "
          f"{hrs:.1f}h")
    print(f"  {agreed} dated by two witnesses, {len(items)-agreed} by one")
    print(f"  {new} new to the dial, {desc} described\n")
    for i in items:
        print(f"  {i['year']}  {i['title'][:44]:<46} {i['kind']:<7}"
              f"{i['favs']:>5} fav  {round(i['dur']/60):>4} min")


if __name__ == "__main__":
    main()
