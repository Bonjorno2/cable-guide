"""Build CH 12 COLLECTORS from ia-curation's programmed channel.

Every other channel here is a lineup: a set of films with an order imposed on
it afterwards by `packChannel()`, which shuffles blocks on a seed so the
channel is not front-loaded. That is the right thing to do to a list. It is the
wrong thing to do to a *programme*, and ia-curation ends in one.

`channel.py` over there does three things a list does not have to:

  one film per film   `Scars Of Dracula 1970` (3,636 downloads) and `Scars of
                      Dracula` (29,106) are one picture on two items. A list
                      can carry both and still be true; a channel that plays
                      the same film twice is broken.
  it has to play      every entry is checked against the item's `_files.xml`
                      for a real video file, and the runtime is read off that
                      same file rather than believed from a catalog.
  a running order     each film is a near neighbour of the one before it in
                      the co-favourite graph, so consecutive pictures share
                      actual collectors rather than a genre label. The greedy
                      walk plays nine Hammer pictures back to back, so a
                      franchise is held off for a few slots once it has played.

What it picks is a region of that graph rather than a shelf: mutual
nearest-neighbour components of the 155 endorsed films, gated on density and
then ranked by *obscurity*, because past a floor a denser region mostly means a
bigger crowd — the densest thing in there is the 1950s monster shelf that every
public-domain site already has. The winner is gothic → giallo → slasher, and
17 of the 36 films that survive the year gate below were found by the graph
alone: they sit beside 18 to 22 of the others in the collections of people with
nothing else in common.

So this file is deliberately thin. It does not re-decide anything *about the
programming*: the films, their order, their files and their runtimes are
`data/channel.json` as `channel.py` wrote it. The year gate is the one
exception and it is a licensing decision, not a curatorial one. Three things it
does do:

  * **Writes the blocks out, so the running order survives.** A walk that gets
    shuffled is a list again. CH 01 already needed prescribed blocks for its
    dayparts, so the template grew the mechanism — but there it is bundled with
    the local-clock shift, and this channel wants to stay globally identical.
    `blocks` now drives the packing and `daypart` only drives the clock.
  * **Titles through ia-curation's `titles.py`, not the guide's `clean()`.**
    This shelf's uploader ends every title with a bare year, and the guide's
    cleaner refuses to cut one on purpose — any rule blunt enough to strip it
    also destroys `Space 1999` and `Big News of 1941`. `titles.clean()` cuts it
    because it parses the year rather than pattern-matching it, has 38 cases
    behind it, and fixes `The Hound Of The Baskeгvilles`, which is genuinely
    spelled with a Cyrillic ghe. Without it 38 of the 40 listings would read
    `Horror Of Dracula 1958` next to a column that already prints 1958.
  * **Prefers the year in the title to the year in the catalog.** They disagree
    twice — Hands of the Ripper and Baron Blood — and the uploader who typed
    the title was naming the film, while `release_year()` is reading a date
    field that can be the edition rather than the picture.

No network. The file and duration of all 40 rows were checked against the
guide's own resolver — `curated.files_xml()`, which picks by derivative format
rather than by size — and agreed on all 40, so there is nothing to re-resolve.

Run after `curated.py` and before `describe.py`, which is what puts Erickson's
prose on the 22 endorsed films and fetches a description for the rest.
"""
import json
import os
import sys

CURATION = r"C:\Users\myerj\Desktop\ia-curation"
CHANNEL = os.path.join(CURATION, "data", "channel.json")
sys.path.insert(0, CURATION)
from titles import clean as ia_clean      # noqa: E402  (needs the path first)

SLOT = 1800
MINBREAK = 30            # keep in step with template.html and build.py
NUM = 12
NAME = "COLLECTORS"
TAG = "Gothic to giallo, programmed by the people who saved it"

# The one thing this file does re-decide, and it is not a programming decision.
# The region runs 1957-1989 and the last four -- Thirst, Strange Behavior, The
# New York Ripper, I, Madman -- are still in copyright. The walk is a claim
# about adjacency, so dropping films from it costs something real: what is left
# is a subsequence, and at four seams the neighbour of a neighbour now plays
# next. Four out of forty is a cheaper price than the channel carrying films it
# should not, and CH 17 is gated at the same year for the same reason.
UPTO = 1977


def slots_for(dur):
    """Half-hours a programme needs. Mirrors packChannel()."""
    return max(1, -(-(dur + MINBREAK) // SLOT))


def convert(rows, described):
    items, blocks = [], []
    for r in rows:
        title, year = ia_clean(r["title"])
        if not title or not r.get("file") or not r.get("runtime"):
            print(f"  skipped {r['identifier']}", file=sys.stderr)
            continue
        yr = year or r.get("year")
        if not isinstance(yr, int) or yr > UPTO:
            print(f"  dropped {title} ({yr}) -- after {UPTO}", file=sys.stderr)
            continue
        it = {"id": r["identifier"], "file": r["file"], "title": title,
              "year": yr, "dur": round(r["runtime"], 2),
              # How the film got here, which is the whole claim of the channel
              # and the one thing the screen cannot show without being told.
              "kind": r["kind"]}
        if r.get("grade"):
            it["grade"] = r["grade"]
        if r.get("director"):
            it["dir"] = r["director"]
        if r["kind"] == "graph" and r.get("reach"):
            it["reach"] = r["reach"]
        # This file drops the channel and rebuilds it, so without carrying the
        # blurb across a re-run the whole channel goes undescribed until the
        # next describe.py — and describe.py then refetches 18 items it has
        # already read once. Any copy on the dial will do: they are the same
        # archive.org item.
        it.update(described.get(r["identifier"], {}))
        items.append(it)
        blocks.append([1, int(slots_for(r["runtime"]))])
    return items, blocks


def main():
    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)
    with open(CHANNEL, encoding="utf-8") as f:
        rows = json.load(f)

    described = {i["id"]: {k: i[k] for k in ("desc", "desc_src") if k in i}
                 for c in data["channels"] for i in c["items"] if i.get("desc")}
    items, blocks = convert(rows, described)
    if len(items) < 4:
        sys.exit(f"only {len(items)} usable rows in {CHANNEL} -- "
                 f"has channel.py run?")

    data["channels"] = [c for c in data["channels"] if c["num"] != NUM]
    data["channels"].append({"num": NUM, "name": NAME, "tag": TAG,
                             "items": items, "blocks": blocks})
    data["channels"].sort(key=lambda c: c["num"])
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    kinds = {k: sum(1 for i in items if i["kind"] == k)
             for k in ("triple", "double", "graph")}
    cycle = sum(b[1] for b in blocks) * SLOT
    content = sum(i["dur"] for i in items)
    years = sorted(i["year"] for i in items if i.get("year"))
    print(f"CH {NUM:02d} {NAME}: {len(items)} films, {years[0]}-{years[-1]}, "
          f"{cycle/3600:.1f}h cycle, {(1-content/cycle)*100:.0f}% ads",
          file=sys.stderr)
    print(f"  endorsed three times {kinds['triple']:>3}\n"
          f"  endorsed twice       {kinds['double']:>3}\n"
          f"  found by the graph   {kinds['graph']:>3}", file=sys.stderr)

    # A film already on the dial is fine -- this channel is a view, like CH 01.
    # A film that is *only* here is the graph earning its keep, and it is the
    # number worth watching between runs.
    seen = {i["id"] for c in data["channels"] if c["num"] != NUM
            for i in c["items"]}
    fresh = [i for i in items if i["id"] not in seen]
    print(f"  new to the dial      {len(fresh):>3}"
          + (": " + ", ".join(i["title"] for i in fresh) if fresh else ""),
          file=sys.stderr)
    undescribed = sum(1 for i in items if not i.get("desc"))
    if undescribed:
        print(f"  {undescribed} without a description -- run describe.py",
              file=sys.stderr)


if __name__ == "__main__":
    main()
