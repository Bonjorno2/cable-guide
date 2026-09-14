"""Build the suggested lineup: the double-endorsed films, plus the comedy.

CH 15 DOUBLE already holds the films that are on a coherent curator shelf
*and* carry a DVD Savant grade -- two independent judgements, neither aware
of the other. This splits that one channel back out into themed channels so
it can stand on its own as a small, vouched-for service.

Six of the seven channels are that split. The seventh is not, and the dial
should say so rather than let the claim quietly go soft: CH 07 COMEDY is drawn
from CH 52, whose boundary is one hand-written list of series, cut once more
here. One judgement, not two, and its tag says "vouched for once" where the
others say "endorsed twice".

It is here because six noir-adjacent channels and nothing to follow them with
is a mood rather than a service. The films are the argument for this lineup;
the comedy is what makes it somewhere you can stay.

Everything comes from channels.json plus the cluster names in
double_endorsed.json, so there are no network calls: the durations, files and
descriptions were resolved when curated.py and sitcom.py ran.

Run order:  curated.py  ->  sitcom.py  ->  suggest.py  ->  build.py
(curated.py rewrites channels.json wholesale, which drops the key this adds;
sitcom.py must have run, since CH 07 is built out of what it left in CH 52.)
"""
import json
import os
import sys

import sitcom   # SERIES and CANON -- the series list, and which of it travels

CURATION = r"C:\Users\myerj\Desktop\ia-curation"
DOUBLE = os.path.join(CURATION, "data", "double_endorsed.json")
SOURCE_CH = 15
SITCOM_CH = 52

# The 15 shelves collapse to 6 channels. Six of them are noir variants and two
# are colourization projects; kept apart they make channels of 3-9 films, whose
# loops come round fast enough to notice. Matched on a substring because the
# shelf names carry en-dashes that do not survive every encoding intact.
#
# The noir shelves split in two rather than pooling, because pooled they were
# 63 films against 10 for the smallest channel — a sixth of the dial holding
# half the service. The line is the one the shelves themselves draw: two are
# organised around a director, the rest around the films. That also gives the
# split a reason a viewer can feel, which an even cut by count would not.
THEMES = [
    (1, "NOIR", "Endorsed twice · the noir shelves", [
        "fn01r Noir", "Intros Intact", "Gloria Grahame",
        "Best Available Source: Noir"]),
    (2, "DIRECTORS", "Endorsed twice · Preminger, Siodmak, Mann, Wilder", [
        "Noir: Preminger", "Director-Forward Noir"]),
    (3, "COLOUR", "Endorsed twice · colourized and upscaled", [
        "Colourized and Upscaled", "DeOldify"]),
    (4, "CHILLER", "Endorsed twice · Hammer, giallo, the nasty years", [
        "Retro Chiller"]),
    (5, "SILENT", "Endorsed twice · the silent canon", [
        "Complete Silent Shelf", "Silent Canon in HD", "Keystone and After"]),
    (6, "ODDMENTS", "Endorsed twice · grindhouse, expressionism, oddments", [
        "Grindhouse International", "Black-and-White Benchmarks",
        "Les Vampires"]),
]

GRADE_ORDER = {"Excellent": 0, "Very Good": 1, "Good": 2, "Fair": 3}

# CH 52 runs fifteen series deep. That is right for a channel you leave on --
# the tail is what keeps it from being the Jack Benny channel with guests --
# and wrong for a seven-channel service, where the tail is Meet Corliss Archer
# and Trouble with Father, half-hours that were filler when they were new.
#
# The line is the one the shows themselves drew: an act that already existed
# before television and was carried onto it more or less intact. Benny and
# Burns and Allen came off the radio with their timing formed, Eve Arden
# brought Our Miss Brooks over from CBS radio whole, Ozzie and Harriet had been
# playing themselves for eight years before the cameras arrived, and Betty
# White built Life with Elizabeth out of a live local show she was already
# doing five days a week. Topper is the odd one -- a film adaptation, no act
# behind it -- and earns its place the other way, by being the one premise here
# anybody still recognises.
#
# The names are in sitcom.py because that is the file that knows what a search
# phrase means; the `must` token that identifies an item is taken from the same
# row, so the two cannot drift apart.
COMEDY = (7, "COMEDY", "Vouched for once · the comedy that kept its name")


def comedy_channel(src):
    """CH 52 -> the canonical series only, re-dealt round-robin."""
    must = {s[0]: s[1] for s in sitcom.SERIES}
    groups = []
    for phrase in sitcom.CANON:
        tok = must[phrase]
        groups.append([i for i in src["items"] if tok in i["title"].lower()])
    # Deal them together, longest run first -- the same reason sitcom.py does
    # it: six series in shelf order means six consecutive Bennys at the top of
    # every loop.
    items = sitcom.deal([g for g in groups if g])
    num, name, tag = COMEDY
    return {"num": num, "name": name, "tag": tag, "items": items}, groups


def main():
    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)
    with open(DOUBLE, encoding="utf-8") as f:
        double = json.load(f)

    cluster = {r["ia"]["identifier"]: r["cluster"] for r in double}

    src = next((c for c in data["channels"] if c["num"] == SOURCE_CH), None)
    if src is None:
        sys.exit(f"no CH {SOURCE_CH} in channels.json -- run curated.py first")

    unplaced = []
    out = []
    for num, name, tag, matchers in THEMES:
        items = []
        for it in src["items"]:
            cl = cluster.get(it["id"])
            if cl and any(m in cl for m in matchers):
                items.append(it)
        # best first, then a stable tiebreak so the packer sees a fixed order
        items.sort(key=lambda i: (GRADE_ORDER.get(i.get("grade"), 9), i["title"]))
        if len(items) >= 4:
            out.append({"num": num, "name": name, "tag": tag, "items": items})
        else:
            unplaced += items

    placed = {id(i) for c in out for i in c["items"]}
    missed = [i for i in src["items"] if id(i) not in placed]

    sit = next((c for c in data["channels"] if c["num"] == SITCOM_CH), None)
    comedy = None
    if sit is None:
        print(f"no CH {SITCOM_CH} in channels.json -- CH {COMEDY[0]} "
              f"{COMEDY[1]} skipped", file=sys.stderr)
    else:
        comedy, groups = comedy_channel(sit)
        # Under four items a channel's loop comes round inside two hours, which
        # is the same floor the film themes are held to above.
        if len(comedy["items"]) < 4:
            print(f"CH {COMEDY[0]} {COMEDY[1]} too thin -- skipped",
                  file=sys.stderr)
            comedy = None
        else:
            out.append(comedy)

    data["suggested"] = out
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    films = sum(len(c["items"]) for c in out if c is not comedy)
    print(f"suggested lineup: {len(out)} channels, {films} of "
          f"{len(src['items'])} double-endorsed films")
    for c in out:
        hrs = sum(i["dur"] for i in c["items"]) / 3600
        if c is comedy:
            print(f"  CH {c['num']:02d} {c['name']:<10}"
                  f"{len(c['items']):>4} eps  {hrs:>8.1f}h  "
                  f"{sum(1 for g in groups if g):>3} series")
            continue
        exc = sum(1 for i in c["items"] if i.get("grade") == "Excellent")
        print(f"  CH {c['num']:02d} {c['name']:<10}{len(c['items']):>4} films"
              f"{hrs:>8.1f}h  {exc:>3} excellent")
    if comedy:
        print(f"\n  CH {COMEDY[0]:02d} {COMEDY[1]} draws "
              f"{len(comedy['items'])} of CH {SITCOM_CH}'s "
              f"{len(sit['items'])} episodes:")
        for phrase, g in zip(sitcom.CANON, groups):
            print(f"    {phrase:<40}{len(g):>3} ep")
    if missed:
        print(f"\n  not placed on any theme ({len(missed)}):")
        for i in missed:
            print(f"    {i['title'][:48]:<48} {cluster.get(i['id'],'?')[:40]}")


if __name__ == "__main__":
    main()
