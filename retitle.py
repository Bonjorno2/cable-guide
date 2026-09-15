"""Re-clean the dial's listing titles through ia-curation's `titles.py`.

`harvest.clean()` is deliberately timid. It refuses to cut a bare year because
any rule blunt enough would also destroy `Space 1999` and `Big News of 1941`,
and it caps a title at seventy characters, which on a verbose shelf means a
listing that stops mid-word. That was the right trade while the guide's titles
all came from the same place. It stopped being right when suggest.py's CH 09
and CH 10 started re-cleaning through `titles.py` instead, because the same
film now read two different ways depending on which dial you were on: CH 18
SILENT said `Buster Keaton's "Cops"` and the suggested lineup said `Cops`.

So: 497 of 4,179 listings carried junk — 204 truncated at the cap, 195 still in
quote marks, 264 still carrying a year, a cast list or a `Dir:` credit. This
fixes them where it is safe to, which is not everywhere.

**Scope is the curated film channels only.** `titles.py` parses an uploader's
catalogue-in-the-title, and that is what curated.py's shelves are. It is not
what the collection channels are, and run over those it does real damage: it
turned `Space 1999 (Complete Series 2)` into `Space`, and it ate the part
number off `Postwar Germany: 28 Months After V-E Day (Part II)`, `On the Run
(Part I)` and six more Prelinger and newsreel items, where a trailing
parenthetical is the one thing telling two halves apart. CH 16 is out too --
drivein.py owns those titles and they are night names, not films.

Three things it does beyond calling the cleaner:

  * **The raw title, but only where the stored one was truncated.** Everywhere
    else the stored title is the better input: CH 15 and CH 34 are titled from
    Erickson's review headings, which are properly cased, where the uploader's
    raw is `The Woman In The Window`. Feeding raw to the cleaner also returns
    None on a few and eats the article off `The Day the Earth Stood Still`.
    But a title cut at the cap loses the close of its own bracket, so cleaning
    it leaves `Walk a Crooked Mile (` -- and there the raw is the only source
    that still has the information.
  * **A front-trim has to be earned**, by the census rule suggest.py uses, one
    channel at a time rather than one shelf at a time. That is the same
    argument: a prefix that is cataloguing recurs, a prefix that is part of the
    title appears once.
  * **A collision is examined, not resolved by fiat.** See below.

Run after curated.py and before describe.py and suggest.py: it changes titles,
which is an input to both `echoes_title()` and the suggested lineup.
No network -- every raw title it needs is already in ia-curation's data.
"""
import collections
import json
import os
import re
import sys

import curated  # SHELVES and CURATION, so the scope cannot drift from the dial
import suggest  # LOOSE_YEAR, trimmed_prefix, prefix_key, PREFIX_FLOOR

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, curated.CURATION)
from titles import clean as ia_clean  # noqa: E402  (needs the path first)

DATA = os.path.join(curated.CURATION, "data")
CAP = 69                  # harvest.clean() truncates at 70; at or over is suspect

# drivein.py writes CH 16's titles and they name evenings, not films.
SCOPE = ({num for num, *_ in curated.SHELVES} | {15, 34}) - {16}

# What the cleaner leaves behind when its input was cut mid-bracket.
ORPHAN = re.compile(r"\s*[\(\[]\s*(?:1[89]\d\d|20[0-2]\d)?\s*$")

# A cut is only taken when what it removes is *cataloguing*. Without this the
# cleaner is just as happy to remove meaning, and on these shelves it does: a
# trailing parenthetical is a cast list on CH 17 and an English gloss on CH 27,
# and only one of those is junk. Rejected by this gate, correctly:
#   Orumcek (Turkish Spiderman)            CH 27 -- the gloss is why it is legible
#   Karavan smerti (The caravan of death)  CH 25
#   El Turista (aka Millonario Por Un Dia) CH 21 -- an a.k.a. is a real title
#   Umberto D.                                   -- the cut was one full stop
# Accepted, correctly: anything carrying a year, a credit, a cast list, a
# quality note or a quote mark.
CATALOGUING = re.compile(
    r"(?i)(?:1[89]\d\d|20[0-2]\d)|\bdir\b|\bdirected by\b|starring|featuring|"
    r"restored|colou?ri[sz]ed|remastered|deoldify|full (?:movie|film)|film noir|"
    r"\b(?:hd|sd|\d{3,4}p)\b|imdb|intro and outro|[\"“”\[\]]|\.\.\.|…")

# When two items on a channel clean down to the same title, this is what
# decides whether that is one film twice or two versions of it.
#
# A language or a colour treatment changes what is on the screen, so it is
# programming and has to survive into the listing. CH 30's tag is "Universal
# monsters, doblada al español" and CH 45's is "Jules Verne, and D.O.A. in four
# languages" -- on those two channels the marker is the entire point, and the
# cleaner strips it as trailing decoration: `DRÁCULA. 1931. HD. Español.` and
# `DRÁCULA. 1931. HD.` are the Spanish and English 1931 Draculas, shot at night
# on the same sets, and collapsing them loses the one the channel exists for.
#
# A transfer does not change what is on the screen. `I Love Trouble` at 576p
# and at 720p is one Noir Alley recording twice, and `(restored)` versus
# `(restored, with intro and outro)` is a description of the file. Those
# collide, and the longer copy wins -- which on CH 20 is also the one with the
# intro still on it, this being the channel that is about intros.
VARIANT = re.compile(
    r"(?i)\b(espa[nñ]ol|english|fran[cç]ais|deutsch|italiano|silent|"
    r"colou?rized|colou?rised|tinted|deoldify|dubbed|sub(?:titled|s)?)\b")


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def raw_titles():
    """identifier -> the uploader's own title, as ia-curation recorded it."""
    out = {}
    for c in load("curators.json"):
        for it in c["items"]:
            out.setdefault(it["identifier"], it.get("title"))
    for fn in ("savant_on_ia.json", "double_endorsed.json"):
        for r in load(fn):
            out.setdefault(r["ia"]["identifier"], r["ia"].get("title"))
    return out


def source(it, raw):
    """Which text to clean: the stored title, unless it lost something.

    The stored one is usually the better input -- see the module docstring --
    but it is the wrong one twice. When it was cut at the cap it no longer
    closes its own bracket, and when it is a serial chapter the number is only
    in the raw: `THE PERILS OF PAULINE ( 1914) Ch. 1 Pearl White` was stored as
    `THE PERILS OF PAULINE`, so searching the stored text for a chapter finds
    nothing to put back and the dial disagrees with the suggested lineup, which
    titles the same item from the raw.
    """
    r = raw.get(it["id"])
    if not r:
        return it["title"]
    if len(it["title"]) >= CAP:
        return str(r)
    m = suggest.CHAPTER.search(str(r))
    if m and not re.search(rf"\b{m.group(2)}\b", it["title"]):
        return str(r)
    return it["title"]


def census_for(ch, raw):
    """How often the cleaner trims each prefix off this channel.

    suggest.py takes this census one shelf at a time because that is the
    grouping it has; here it is one channel at a time, which for the curated
    channels is the same set of items. Shaped as {name: counts} because that is
    what suggest.title_of() expects to look a channel up in.
    """
    c = collections.Counter()
    for it in ch["items"]:
        s = source(it, raw)
        t, _ = ia_clean(suggest.LOOSE_YEAR.sub("", s))
        if t:
            c[suggest.prefix_key(suggest.trimmed_prefix(s, t))] += 1
    c.pop("", None)
    return {ch["name"]: c}


def worth_it(old, new, truncated):
    """Is this change a cut of cataloguing, or a cut of meaning?"""
    if new == old:
        return False
    if truncated:
        # The stored title stopped mid-word. Anything the raw one gives back is
        # an improvement by definition, including a title that gets *longer*.
        return True
    if new.startswith(old):
        # Purely additive, which here means a serial chapter being put back:
        # `THE PERILS OF PAULINE` -> `THE PERILS OF PAULINE - Ch. 1`. Nothing
        # was removed, so there is nothing for the gate below to judge.
        return True
    removed = old.replace(new, "", 1) if new in old else old
    return bool(CATALOGUING.search(removed))


def clean_title(it, raw, census, name):
    """suggest.py's cleaner, so the two dials cannot disagree by construction.

    Calling it rather than repeating it is the point: title_of() is what puts a
    serial's chapter number back, and a copy of this logic that forgot to would
    quietly undo `THE PERILS OF PAULINE - Ch. 1` on the suggested lineup -- the
    exact class of drift this file exists to remove.
    """
    s = t = source(it, raw)
    # To a fixed point, because one pass is not stable and a pipeline gets
    # re-run. `Sherlock Holmes movies 1939-1944 colorized` loses `-1944
    # colorized` on the first pass, which leaves `1939` looking like a trailing
    # year to the second one, so the title erodes a little on every rebuild.
    # Settling it here means the stored value is already what a re-run would
    # produce, and retitle.py is a no-op the second time. It costs this one
    # listing its year range; a year column is printed beside it anyway.
    for _ in range(4):
        n, _year = suggest.title_of({"title": t, "identifier": it["id"]},
                                    name, census)
        if not n:
            break
        n = ORPHAN.sub("", n).strip(" -–—:,|·•\"“”")[:70].strip()
        if not n or n == t:
            break
        t = n
    if not worth_it(it["title"], t, len(it["title"]) >= CAP):
        return None
    return t


def variant_of(it, raw):
    """The language or treatment marker the cleaner threw away, if any."""
    m = VARIANT.search(source(it, raw))
    return m.group(1) if m else None


def settle(group, raw):
    """One cleaned title, several items. Returns (titles, dropped).

    A marker that changes what is on the screen is put back and both stay. A
    marker that only describes the file does not count, so those are one
    programme twice and the longest copy is kept -- longest rather than first
    because on a shelf of two transfers the short one is the incomplete print.
    """
    marks = {id(i): variant_of(i, raw) for i in group}
    if len({(marks[id(i)] or "").lower() for i in group}) == len(group):
        return ({id(i): marks[id(i)] for i in group}, [])
    keep = max(group, key=lambda i: i["dur"])
    return ({}, [i for i in group if i is not keep])


def main():
    dry = "--dry" in sys.argv
    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)
    raw = raw_titles()

    retitled, dropped, kept_apart = {}, [], []
    for ch in data["channels"]:
        if ch["num"] not in SCOPE:
            continue
        census = census_for(ch, raw)
        proposed = {}
        for it in ch["items"]:
            t = clean_title(it, raw, census, ch["name"])
            if t:
                proposed[id(it)] = t

        groups = collections.defaultdict(list)
        for it in ch["items"]:
            groups[proposed.get(id(it), it["title"]).lower()].append(it)

        gone = set()
        for members in groups.values():
            if len(members) == 1:
                continue
            marks, losers = settle(members, raw)
            for it in members:
                mark = marks.get(id(it))
                if mark:
                    # Put the marker back rather than letting the shelf's own
                    # distinction vanish into a duplicate.
                    proposed[id(it)] = f"{proposed[id(it)]} ({mark})"
                    kept_apart.append((ch["num"], proposed[id(it)]))
            for it in losers:
                dropped.append((ch["num"], proposed.get(id(it), it["title"]),
                                it["id"], it["dur"]))
                gone.add(id(it))

        ch["items"] = [i for i in ch["items"] if id(i) not in gone]
        for it in ch["items"]:
            t = proposed.get(id(it))
            if t and t != it["title"]:
                retitled[it["id"]] = t
                it["title"] = t

    # CH 01, CH 11 and CH 12 carry copies of these items, and the suggested
    # lineup carries copies of CH 15's. A title fixed on one dial and not the
    # other is the defect this file exists to close, so the map is applied
    # everywhere rather than only where it was computed.
    copies = 0
    for ch in data["channels"] + data.get("suggested", []):
        for it in ch["items"]:
            t = retitled.get(it["id"])
            if t and t != it["title"]:
                it["title"] = t
                copies += 1

    print(f"{len(retitled)} listings retitled across "
          f"{len(SCOPE)} curated channels, {copies} copies brought into line")
    if kept_apart:
        print(f"\nkept apart, a version rather than a repeat ({len(kept_apart)}):")
        for num, t in kept_apart:
            print(f"  CH {num:02d}  {t}")
    if dropped:
        print(f"\nthe same programme twice, shorter copy dropped ({len(dropped)}):")
        for num, t, ident, dur in dropped:
            print(f"  CH {num:02d}  {t[:38]:<40}{ident[:34]:<36}{round(dur):>6}s")
    if dry:
        print("\n--dry: nothing written")
        return
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("\nchannels.json written -- run describe.py --repolish, "
          "then suggest.py, then build.py")


if __name__ == "__main__":
    main()
