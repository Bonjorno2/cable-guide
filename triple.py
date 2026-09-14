"""Build CH 12 TRIPLE — the films three independent judgements agree on.

CH 15 DOUBLE is the best channel on the dial because two strangers agreed
about every film on it: someone kept it on a coherent shelf, and Glenn
Erickson graded it. ia-curation has a third signal that the guide has never
read, and it is the one that costs the most to fake.

`fav_analyze.py` scores the *favouriter* the same way `analyze.py` scores an
uploader — 894,629 favourite edges across 132,668 people, of whom 1,108 hold a
shelf coherent enough to count as a point of view rather than a bookmark pile.
`triple_endorsed.py` intersects all three:

  1. an anonymous uploader preserved it inside a coherent, focused shelf;
  2. Erickson reviewed and graded it, in a column no longer on the live web;
  3. at least two of those independent collectors saved it.

59 films. The independence is structural rather than assumed: the uploader
acted years before there was anything to favourite, Erickson was writing about
DVDs and never saw archive.org, and a favouriter cannot see anyone else's list
in aggregate. Nothing here is one crowd agreeing with itself — which is the
whole reason to put it on a channel.

This is a *view* over the dial, not a harvest. Every film is already in CH 15
with its duration, derivative, grade, director and DVD Savant blurb resolved,
so there are no network calls and nothing is claimed away from DOUBLE. That is
the licence daypart.py takes for CH 01 and suggest.py takes for the ★ lineup;
CH 12 is the third and last channel that repeats material.

Three things worth knowing:

  * 58 of the 59 make it. World on a Wire is the miss, and it fails twice
    over: 3h24m of Fassbinder is past curated.py's 11,000-second ceiling so it
    never reached CH 15, and a 1973 West German television film is plainly
    still in copyright. `carried()` reports any future miss by name rather
    than quietly shipping a shorter channel.
  * The collector count rides along into the UI, the way the grade and the
    director already do. It is the one signal of the three a viewer cannot
    otherwise see — the shelf is the channel and the grade is the badge, so
    without it "endorsed three times" is a claim the screen never backs up.
  * Rarest first, within grade. Thirty collectors saved Kiss Me Deadly, which
    has 80,000 downloads; two saved Murnau's Phantom, which has 2,555. The two
    is the more interesting number: a film almost nobody downloads that two
    separate coherent shelves went out of their way to keep is the thing
    popularity sorting can never surface. The template reshuffles blocks on a
    seed anyway, so this decides nothing about airtime — it is the order the
    channel is stored and read in.

Run after describe.py, so the blurbs are there to copy. Safe to re-run alone:
it drops CH 12, rebuilds it and merges, and writes channels.json in the same
compact form suggest.py does.
"""
import json
import os
import sys

CURATION = r"C:\Users\myerj\Desktop\ia-curation"
TRIPLE = os.path.join(CURATION, "data", "triple_endorsed.json")

SOURCE_CH = 15
NUM = 12
NAME = "TRIPLE"
TAG = "Endorsed three times, independently"

GRADE_ORDER = {"Excellent": 0, "Very Good": 1, "Good": 2, "Fair": 3}


def carried(src, rows):
    """The triple-endorsed films that are actually on the dial, best first."""
    by_id = {r["ia"]["identifier"]: r for r in rows}
    items = []
    for it in src["items"]:
        r = by_id.get(it["id"])
        if not r:
            continue
        # A copy, so DOUBLE is left exactly as curated.py wrote it.
        items.append(dict(it, collectors=r["fav_votes"]))
    items.sort(key=lambda i: (GRADE_ORDER.get(i.get("grade"), 9),
                              i["collectors"], i["title"]))
    return items, [r for i, r in by_id.items()
                   if i not in {x["id"] for x in items}]


def main():
    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)
    with open(TRIPLE, encoding="utf-8") as f:
        rows = json.load(f)

    src = next((c for c in data["channels"] if c["num"] == SOURCE_CH), None)
    if src is None:
        sys.exit(f"no CH {SOURCE_CH} in channels.json -- run curated.py first")

    items, missing = carried(src, rows)
    if len(items) < 4:
        sys.exit(f"only {len(items)} of {len(rows)} triple-endorsed films are "
                 f"on CH {SOURCE_CH} -- has curated.py run?")

    data["channels"] = [c for c in data["channels"] if c["num"] != NUM]
    data["channels"].append({"num": NUM, "name": NAME, "tag": TAG,
                             "items": items})
    data["channels"].sort(key=lambda c: c["num"])
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    hrs = sum(i["dur"] for i in items) / 3600
    described = sum(1 for i in items if i.get("desc"))
    print(f"CH {NUM:02d} {NAME}: {len(items)} of {len(rows)} triple-endorsed "
          f"films, {hrs:.1f}h of programme", file=sys.stderr)
    for g in GRADE_ORDER:
        n = sum(1 for i in items if i.get("grade") == g)
        if n:
            print(f"  {g:<12}{n:>4}", file=sys.stderr)
    print(f"  described   {described:>4} of {len(items)}", file=sys.stderr)
    print(f"  collectors  {min(i['collectors'] for i in items)}-"
          f"{max(i['collectors'] for i in items)} per film", file=sys.stderr)
    for r in missing:
        # Not an error — the curation grades films the guide cannot schedule —
        # but a channel quietly losing a film is worth one line of output.
        print(f"  not on CH {SOURCE_CH}: {r['title']} ({r['year']}) "
              f"{r['movie']}", file=sys.stderr)


if __name__ == "__main__":
    main()
