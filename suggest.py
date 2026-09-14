"""Build the suggested lineup from the double-endorsed films.

CH 15 DOUBLE already holds the films that are on a coherent curator shelf
*and* carry a DVD Savant grade -- two independent judgements, neither aware
of the other. This splits that one channel back out into themed channels so
it can stand on its own as a small, entirely vouched-for service.

Everything comes from channels.json plus the cluster names in
double_endorsed.json, so there are no network calls: the durations, files and
descriptions were resolved when curated.py ran.

Run order:  curated.py  ->  suggest.py  ->  build.py
(curated.py rewrites channels.json wholesale, which drops the key this adds.)
"""
import json
import os
import sys

CURATION = r"C:\Users\myerj\Desktop\ia-curation"
DOUBLE = os.path.join(CURATION, "data", "double_endorsed.json")
SOURCE_CH = 15

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

    data["suggested"] = out
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    total = sum(len(c["items"]) for c in out)
    print(f"suggested lineup: {len(out)} channels, {total} of "
          f"{len(src['items'])} double-endorsed films")
    for c in out:
        hrs = sum(i["dur"] for i in c["items"]) / 3600
        exc = sum(1 for i in c["items"] if i.get("grade") == "Excellent")
        print(f"  CH {c['num']:02d} {c['name']:<10}{len(c['items']):>4} films"
              f"{hrs:>8.1f}h  {exc:>3} excellent")
    if missed:
        print(f"\n  not placed on any theme ({len(missed)}):")
        for i in missed:
            print(f"    {i['title'][:48]:<48} {cluster.get(i['id'],'?')[:40]}")


if __name__ == "__main__":
    main()
