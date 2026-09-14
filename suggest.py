"""Build the suggested lineup: a small service where every programme is vouched for.

CH 15 DOUBLE holds the films that are on a coherent curator shelf *and* carry a
DVD Savant grade -- two independent judgements, neither aware of the other. Six
of the channels here are that one channel split back out into themes so it can
stand on its own as a service.

The seventh is not, and the dial should say so rather than let the claim quietly
go soft: CH 07 COMEDY is drawn from CH 52, whose boundary is one hand-written
list of series, cut once more here. One judgement, not two, and its tag says
"vouched for once" where the others say "endorsed twice".

It is here because six noir-adjacent channels and nothing to follow them with
is a mood rather than a service. The films are the argument for this lineup;
the comedy is what makes it somewhere you can stay.

Channels 08-10 come from ia-curation's *third* signal, `fav_curators.json`:
the `fav-<user>` collections every archive.org item already carries, scored for
coherence exactly the way uploaders were, so what counts is not how many people
favourited a film but how many people with a demonstrable shelf of their own
did. That signal was already joined against the other two next door, and the
arithmetic there is what these three channels are:

  all three agree           59 films  ->  CH 08 TRIPLE
  shelf + collectors, no critic  478  ->  CH 09 ONE REEL and CH 10 CRIME

CH 08 is the strongest claim the curation can make and it was not on either
dial. Every one of its films also plays on 01-06, which is the same bargain
CH 01 and CH 12 make on the main dial, and the tag says so.

09 and 10 are the other half, and they are the half with new material in it:
Erickson reviewed DVDs, so the shelves he never touched -- the silent
one-reelers, the noir bench nobody pressed a disc of -- reach the service
only through the people who collected them. Where that pool splits is not a
judgement call; it splits itself, 191 silent-era items with a median under
fifteen minutes against 91 crime features from 1941 to 1959, and nothing in
between worth a channel.

Both are cut before they are counted:

  * the Grindhouse International shelf is dropped whole, for the reason
    curated.py drops it -- sexploitation, and one title in 204 trips a keyword
    filter, so it has to go by the shelf and not by the title;
  * Black-and-White Benchmarks is left out of CH 10 although it is noir, because
    it is an upscaler's shelf of major studio pictures -- Gilda, Double
    Indemnity, Gaslight -- which are on archive.org without being free to
    rebroadcast;
  * and five titles are cut by name, every one of them found by reading the
    list rather than by a rule. See EXCLUDE_TITLE.

Titles on 09 and 10 are re-cleaned through ia-curation's `titles.py` rather than
reused from the dial, for the reason walk.py gives: these uploaders catalogue
inside the title, and `harvest.clean()` leaves `"1776, or The Hessian
Renegades"` in its quote marks and truncates `Big Town After Dark (1947, USA)
Phillip Reed, Hillary Brooke - Film No` at seventy characters. A serial chapter
then gets its number put back, since ten listings reading LES VAMPIRES is not a
listing.

Run order:  curated.py  ->  sitcom.py  ->  walk.py  ->  suggest.py  ->  build.py
(curated.py rewrites channels.json wholesale, which drops the key this adds;
sitcom.py must have run, since CH 07 is built out of what it left in CH 52.)

01-08 need no network: their durations, files and descriptions were resolved
when curated.py ran. 09 and 10 reuse whatever the dial already resolved and
fetch `_files.xml` for the rest -- about a hundred items, off the data nodes.
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import curated  # files_xml() -- duration and derivative off the data nodes
import describe  # meta_description() for the items no channel has described
import harvest  # blocked()
import sitcom   # SERIES and CANON -- the series list, and which of it travels

CURATION = r"C:\Users\myerj\Desktop\ia-curation"
DATA = os.path.join(CURATION, "data")
DOUBLE = os.path.join(DATA, "double_endorsed.json")
SOURCE_CH = 15
SITCOM_CH = 52

sys.path.insert(0, CURATION)
from titles import clean as ia_clean  # noqa: E402  (needs the path first)

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

TRIPLE = (8, "TRIPLE", "Endorsed three times · shelf, critic and collectors")

# The two channels cut out of the 478 films a shelf and its collectors both
# picked and Erickson never graded. The gate is the material's own: silent-era
# and under the half hour, or a crime feature off one of the noir shelves.
ONE_REEL = (9, "ONE REEL", "Endorsed twice · the silent shorts collectors kept")
CRIME = (10, "CRIME", "Endorsed twice · the noir bench nobody graded")

SHORT_BAND = (45, 1800)     # a reel to the half hour, the slot they tile into
FEATURE_BAND = (1500, 11000)  # 25 min - 3 hours, curated.py's FEATURE
SILENT_ERA = 1929

# Shelves that are silent by their own definition, for the handful of trick
# films that carry no year at all: a Chomón with a blank date field is still a
# Chomón, and dropping it would cost the channel its oldest material.
SILENT_SHELVES = ["Complete Silent Shelf", "Trick Films", "Keystone and After",
                  "Chaplin: The Keystone", "Les Vampires"]

# Noir shelves for CH 10, named rather than pattern-matched. Black-and-White
# Benchmarks is noir too and is deliberately absent: it is an upscaler's shelf
# whose collector picks are Gilda, Double Indemnity and Gaslight, studio
# pictures that are on archive.org without being free to rebroadcast. The
# service can carry the bench without carrying that.
NOIR_SHELVES = ["fn01r Noir", "Director-Forward Noir", "Noir: Preminger",
                "Gloria Grahame", "Intros Intact"]

# Dropped whole, the way curated.py drops it: sexploitation, and exactly one
# title in 204 trips a keyword filter, so the unit of exclusion has to be the
# shelf.
EXCLUDE_SHELF = ["Grindhouse International"]

# Cut by name, all five found by reading the list rather than by a rule --
# which is the standing lesson of this project and not a formality:
#   Levi and Cohen        1903 Bitzer actuality, and the title is the act: an
#                         ethnic caricature. Two minutes of it, uncontextualised
#                         between two Keaton shorts, is not what this is for.
#   A Natural Born Gambler  Bert Williams, and genuinely important -- one of the
#                         earliest surviving films led by a Black performer --
#                         but he is in burnt cork, and a channel that cannot
#                         frame that should not be the place it turns up.
#   The Road to Ruin      1928, a road-show exploitation picture, sold as a
#                         warning and shot as the other thing.
#   Silent Hall Of Fame   a 2015 documentary about silent film, on a channel of
#                         silent film. Not the same object.
#   a trailer / movie trailer
#                         two items that are trailers. A trailer is not a
#                         programme, and both say so in their own titles --
#                         which is why this is matched against the raw title as
#                         well as the cleaned one. `"The Big City" (1928)
#                         starring Lon Chaney and Marceline Day - a trailer`
#                         cleans up to `The Big City`, and the words that
#                         condemn it are the ones the cleaner exists to remove.
EXCLUDE_TITLE = ["levi and cohen", "a natural born gambler", "the road to ruin",
                 "silent hall of fame", "a trailer", "movie trailer"]

# A serial chapter whose number ia_clean() dropped. "Episode 5-Dead Man's
# Escape" gives back the name too; "Ch. 6 Pearl White" does not, because what
# follows an unhyphenated number on this shelf is the cast.
CHAPTER = re.compile(
    r"(?i)\b(ch(?:apter)?|ep(?:isode)?)\.?\s*(\d{1,2})\b"
    r"(?:\s*[-–—]\s*([^,(]{2,36}))?")

# A parenthesised year with anything else inside the brackets, closed or not.
# Both cleaners want the year alone in there and neither matches "(1950 USA /
# France)", so `Gunman in the Streets (1950 USA / France) Dane Clark, Simone
# Signoret` came through as "Gunman in the Streets Dane Clark,". The closing
# bracket is optional because `Highway Dragnet (1954 Richard Conte, Joan
# Bennett - Film Noir Full Movie` never closes its own. Cutting the raw title
# here first costs nothing where the brackets are well formed: that is where
# ia_clean() cuts anyway.
LOOSE_YEAR = re.compile(r"\s*[\(\[]\s*(?:1[89]\d\d|20[0-2]\d)\b[^)\]]*[\)\]]?.*$")

# An item that is an advertisement for the film rather than the film. The
# silent shelf's uploader is a non-profit that posts a one-minute taste and
# sells the full print, and says so in the description of every one; two more
# are marked only in the file name (`The-Cameraman-clip.mp4`), which is why
# both are tested. Unchecked, the channel lists The Cameraman and plays 132
# seconds of it, which is worse than not carrying it.
PREVIEW_DESC = re.compile(
    r"(?i)\bthis is a (?:short |brief )?(?:preview|excerpt|clip|sample|taste)\b"
    r"|\b(?:watch|see) the (?:whole|full|complete|entire) (?:film|movie)\b")
PREVIEW_FILE = re.compile(r"(?i)\bpreview|[-_ ]clip\b|trailer|teaser|excerpt")


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


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def shelf_index():
    """identifier -> (shelf name, catalogue record), vouched-for shelves only.

    The same index triple_endorsed.py builds, and for the same reason: a shelf
    the curation rated anything less than 'strong' wandering onto a good film
    is coincidence, not a judgement about it.
    """
    curators = load("curators.json")
    with open(os.path.join(CURATION, "names.json"), encoding="utf-8") as f:
        names = json.load(f)
    idx = {}
    for c in curators:
        ed = names.get(c["items"][0]["identifier"])
        if not ed or ed.get("quality") != "strong":
            continue
        if any(x.lower() in ed["name"].lower() for x in EXCLUDE_SHELF):
            continue
        for it in c["items"]:
            idx.setdefault(it["identifier"], (ed["name"], it))
    return idx


def trimmed_prefix(raw, title):
    """What ia_clean() cut off the *front* of a title, verbatim."""
    head = raw.lstrip(" \"“”‘’'")
    i = head.lower().find(title.lower()[:12])
    return head[:i] if i > 0 else ""


def prefix_key(p):
    """A prefix as a class, so twelve different file indexes count as one."""
    return re.sub(r"\d+", "#", p)


def prefix_census(shelf):
    """shelf name -> how often ia_clean() cuts each prefix off that shelf.

    A front-trim is the one edit either cleaner makes that can take a word of
    the actual title, and it does: `2 A.M. in the Subway` comes back as `A.M.
    in the Subway` because a leading number reads as a file index, and `Man's
    Genesis` comes back as `Genesis` because a capitalised possessive reads as
    `Buster Keaton's`. ia-curation's own comment on the second one says a
    connective inside the match is the tell, and "Man's" has none.

    So ask the shelf instead. A prefix that is cataloguing recurs across it --
    "Buster Keaton's" fifteen times, a leading index on all twelve East Side
    Kids -- and a prefix that is part of a title appears once. Below the floor
    the cut is refused and the prefix put back, which is why this returns
    counts rather than a verdict.
    """
    census = {}
    for name, rec in shelf.values():
        raw = str(rec.get("title") or rec["identifier"])
        title, _ = ia_clean(LOOSE_YEAR.sub("", raw))
        if not title:
            continue
        p = prefix_key(trimmed_prefix(raw, title))
        if p:
            census.setdefault(name, {})
            census[name][p] = census[name].get(p, 0) + 1
    return census


PREFIX_FLOOR = 3


def title_of(rec, shelf_name="", census=None):
    """ia-curation's cleaner, guarded, with a serial's chapter number put back."""
    raw = str(rec.get("title") or rec["identifier"])
    title, year = ia_clean(LOOSE_YEAR.sub("", raw))
    if not title:
        return None, None
    if census is not None:
        p = trimmed_prefix(raw, title)
        if p and census.get(shelf_name, {}).get(prefix_key(p), 0) < PREFIX_FLOOR:
            title = p + title          # the cut was part of the title: put it back
    m = CHAPTER.search(raw)
    if m and not re.search(rf"\b{m.group(2)}\b", title):
        word = "Ch." if m.group(1).lower().startswith("ch") else "Ep."
        part = f"{word} {m.group(2)}"
        if m.group(3):
            part += f": {m.group(3).strip()}"
        title = f"{title} - {part}"
    return title[:70].strip(" -–—:,|·•"), year or rec.get("year")


def kept_pool():
    """The 478: on a vouched shelf, kept by >=2 coherent collectors, ungraded.

    Erickson is subtracted rather than ignored -- the films he did grade are
    already the six channels above, and a film arriving here is one that
    reached the service on the collectors' vote alone.
    """
    shelf = shelf_index()
    census = prefix_census(shelf)
    graded = {s["ia"]["identifier"] for s in load("savant_on_ia.json")}
    votes = load("fav_curators.json")["votes"]
    out = []
    for ident, (name, rec) in shelf.items():
        if ident in graded or ident not in votes:
            continue
        title, year = title_of(rec, name, census)
        hay = (title or "").lower() + " " + str(rec.get("title") or "").lower()
        if not title or any(x in hay for x in EXCLUDE_TITLE):
            continue
        out.append({"id": ident, "title": title, "year": year,
                    "shelf": name, "favs": votes[ident],
                    "downloads": rec.get("downloads") or 0})
    # most-collected first, so a cap and a tie both fall the right way
    out.sort(key=lambda r: (-r["favs"], -r["downloads"]))
    return out


def resolve(rows, band, dial):
    """rows -> playable items, reusing whatever the dial already resolved.

    A file and a duration off `_files.xml` is the one check in this project
    that verifies the thing rather than a claim about it, and two thirds of
    these have already had it done to them on a harvested channel. Titles and
    descriptions are not reused: see the module docstring, and PREVIEW_DESC.

    Returns (items, previews) so the count of what was thrown out is printed
    rather than silently absorbed.
    """
    todo = [r for r in rows if r["id"] not in dial]
    got = {}
    if todo:
        with ThreadPoolExecutor(max_workers=24) as ex:
            for r, res in zip(todo, ex.map(curated.files_xml,
                                           [r["id"] for r in todo])):
                if res:
                    got[r["id"]] = res

    cand, seen = [], set()
    for r in rows:
        on = dial.get(r["id"])
        if on:
            file, dur = on["file"], on["dur"]
        elif r["id"] in got:
            file, dur = got[r["id"]]
        else:
            continue
        if not band[0] <= dur <= band[1]:
            continue
        key = r["title"].lower()
        if key in seen:                 # one film per film: the shelves carry
            continue                    # the same picture on two uploads
        it = {"id": r["id"], "file": file, "title": r["title"],
              "year": r["year"], "dur": round(dur, 2),
              # How it got here, and the only one of the three signals that is
              # invisible on screen unless the listing says it.
              "kind": "kept", "favs": r["favs"]}
        if harvest.blocked(it):
            continue
        seen.add(key)
        cand.append(it)

    # One read of the description field does both jobs: it is what rejects a
    # preview, and what is left of it after describe.py's rules is the listing.
    items, previews = [], []
    with ThreadPoolExecutor(max_workers=24) as ex:
        raws = list(ex.map(describe.meta_raw, [i["id"] for i in cand]))
    for it, raw in zip(cand, raws):
        if PREVIEW_DESC.search(raw) or PREVIEW_FILE.search(it["file"]):
            previews.append(it)
            continue
        d = describe.clean(raw)
        if d and not describe.echoes_title(it["title"], d):
            it["desc"] = describe.shorten(d)
            it["desc_src"] = "ia"
        items.append(it)
    return items, previews


def triple_channel(dial):
    """The 59 films all three signals agree on, rarest first.

    Every one of them also plays on 01-06, because the 59 are a subset of the
    155 those six channels split up. That is the same bargain CH 01 and CH 12
    make on the main dial: a view over the service rather than more of it, and
    worth a channel because this is the one claim the service is *for* and
    nothing on either dial was making it.

    Not a running order, so no blocks -- rarest first is a ranking, and
    packChannel() is the right thing to do to a ranking.
    """
    rows = load("triple_endorsed.json")
    num, name, tag = TRIPLE
    items, missing = [], []
    for r in sorted(rows, key=lambda r: r["ia"]["downloads"]):
        on = dial.get(r["ia"]["identifier"])
        if not on:
            missing.append(r)
            continue
        it = dict(on)
        it["kind"] = "triple"
        it["favs"] = r["fav_votes"]
        items.append(it)
    return {"num": num, "name": name, "tag": tag, "items": items}, missing


def kept_channels(dial):
    """CH 09 and CH 10, off the one pool, split where the pool splits."""
    pool = kept_pool()
    short = [r for r in pool
             if (r["year"] <= SILENT_ERA if r["year"]
                 else any(s in r["shelf"] for s in SILENT_SHELVES))]
    noir = [r for r in pool
            if any(s in r["shelf"] for s in NOIR_SHELVES)]

    out, thrown = [], []
    for (num, name, tag), rows, band in (
            (ONE_REEL, short, SHORT_BAND), (CRIME, noir, FEATURE_BAND)):
        items, previews = resolve(rows, band, dial)
        thrown += previews
        print(f"  CH {num:02d} {name:<9}{len(items):>4} of {len(rows):<4} "
              f"resolved, in band and whole "
              f"({len(previews)} previews dropped)", file=sys.stderr)
        if len(items) >= 4:
            out.append({"num": num, "name": name, "tag": tag, "items": items})
    return out, thrown


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

    # Anything already resolved anywhere on the dial, so 08 needs no network
    # and 09/10 only fetch what is new.
    dial = {i["id"]: i for c in data["channels"] for i in c["items"]}

    triple, missing = triple_channel(dial)
    if len(triple["items"]) >= 4:
        out.append(triple)

    kept, previews = kept_channels(dial)
    out += kept

    out.sort(key=lambda c: c["num"])
    data["suggested"] = out
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    films = sum(len(c["items"]) for c in out if c is not comedy)
    print(f"\nsuggested lineup: {len(out)} channels, {films} films "
          f"and {len(comedy['items']) if comedy else 0} episodes")
    for c in out:
        hrs = sum(i["dur"] for i in c["items"]) / 3600
        if c is comedy:
            print(f"  CH {c['num']:02d} {c['name']:<10}"
                  f"{len(c['items']):>4} eps  {hrs:>8.1f}h  "
                  f"{sum(1 for g in groups if g):>3} series")
            continue
        exc = sum(1 for i in c["items"] if i.get("grade") == "Excellent")
        kp = sum(1 for i in c["items"] if i.get("kind") == "kept")
        print(f"  CH {c['num']:02d} {c['name']:<10}{len(c['items']):>4} films"
              f"{hrs:>8.1f}h  " +
              (f"{kp:>3} kept" if kp else f"{exc:>3} excellent"))

    if missing:
        print(f"\n  CH {TRIPLE[0]:02d} {TRIPLE[1]}: "
              f"{len(missing)} of the 59 are not on the dial to draw from:")
        for r in missing:
            print(f"    {r['title'][:42]:<44} {r['year']}")

    # The number that says whether the third signal is still earning its keep:
    # a film on 09 or 10 that no harvested channel carries reached the service
    # on the collectors' vote and on nothing else.
    for c in kept:
        new = [i for i in c["items"] if i["id"] not in dial]
        desc = sum(1 for i in c["items"] if i.get("desc"))
        print(f"\n  CH {c['num']:02d} {c['name']}: {len(new)} new to the dial, "
              f"{desc} of {len(c['items'])} described"
              + (("\n    " + ", ".join(i["title"] for i in new[:6]))
                 if new else ""))
    if previews:
        print(f"\n  dropped as a preview or a clip, not the film ({len(previews)}):")
        for i in previews:
            print(f"    {i['title'][:36]:<38}{round(i['dur']):>5}s  {i['file'][:34]}")

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
