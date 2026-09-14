"""Build CH 11 THE EVENING -- two half-hours and the feature, from one audience.

Every other channel on this dial is one medium. The film channels are films and
CH 52 is television, and nothing joins them, because the two catalogues are
separate scrapes with separate curation stories and no shared key. This one is
both, and the thing that joins them is the only signal archive.org has that
crosses the boundary: **the same person favourited both**.

That signal is in ia-curation already, as a *defect*. Its README says so, under
what `neighbours.py` does badly:

    The TV catalog leaks in. `catalog_tv.jsonl` is loaded so TV items can be
    seeded, but a collector who saves both films and sitcoms drags one medium
    into the other's neighbourhood: One Foot in the Grave surfaces under a 1928
    Garbo silent on a single shared collector.

For a film recommender that is noise and it is right to call it noise. For an
evening's viewing it is the entire question -- *which half-hour goes in front of
this picture?* -- and there is no other evidence anywhere that answers it. So
this file reads the leak as the signal, and it is the only place in either
project that does.

## The night

    8:00  half-hour        the film's strongest pairing
    8:30  half-hour        its second
    9:00  the feature      graded Excellent or Very Good by Glenn Erickson

which is what an independent station ran: two syndicated comedies into the late
movie. The blocks are prescribed, so the pairing survives -- `packChannel()`
would shuffle the three apart and the channel would be a lineup again, which is
the same argument `walk.py` makes for CH 12.

## Scoring, and the one correction that is not neighbours.py's

Three of the four corrections are inherited, because the failure modes are the
same graph's:

    hoarder damping      someone with 400 favourites links everything to
                         everything; each voter weighs 1/log(2+picks) and past
                         MAX_PICKS is dropped outright.
    support floor        two people must have saved both. One is coincidence,
                         and across media it is *usually* coincidence -- the
                         Garbo/One Foot in the Grave edge above is exactly one
                         person. MIN_SHARED is 3 here rather than neighbours.py's
                         2 for that reason: this is the thin end of a graph that
                         was already thin, and the floor has to pay for it.
    a size floor         a series nobody saved cannot vouch for anything.

The fourth is new, and without it the channel does not exist. `neighbours.py`
penalises the *candidate's* popularity and that is enough when both ends are
films. Here one end is a series and the other is a picture, and the series end
is drawn from a list of fifteen: score on shared collectors alone and **The
Abbott and Costello Show takes 92 of the 159 pairings**, not because it belongs
in front of 92 films but because it is one item with 536 collectors and every
other series has 54 to 397. The bigger shelf wins every comparison it is in, and
nine series end up dividing the whole channel between them.

So the overlap is normalised by both ends -- a weighted cosine rather than a
weighted count. That takes Abbott and Costello to 59 of 159 and the rest across
eleven series, with *My Man Godfrey* (1936) landing on *Topper* (1953) at 0.054
against 0.037 for the next pairing down, the largest gap on the page. Screwball
to screwball, a ghost comedy under a ghost comedy, and not one subject tag
involved.

## Caps, for the reason sitcom.py has them

Cosine fixes the ranking and does not fix the *distribution*: Abbott and
Costello still wins more pairings than any other series, and uncapped this is
the Abbott and Costello channel with features attached. That is CH 52's lesson
almost word for word -- "Jack Benny alone has 200 free episodes; uncapped, the
channel is the Jack Benny channel with guests" -- so a series carries at most
CAP nights and the night goes to whoever is next.

Nights are then dealt in a seeded order with no series adjacent to itself, so
leaving it on does not give you three Topper evenings in a row, and the strongest
pairings are not all in the first hour.

## No network

Both ends are already resolved. The features are films the dial has played since
`curated.py` ran -- 258 graded features sit on it, 256 of them on CH 34 SAVANT
or CH 15 DOUBLE, with their files, durations and Erickson's prose already
attached -- and the half-hours are CH 52's, which is a hand-written list of
series that lapsed into the public domain and the only part of this that could
not be derived. Nothing here is fetched and nothing here is re-decided; this
file only says which of them go together.

That makes CH 11 a *view* over the dial, like CH 01 and CH 12, and it is exempt
from `curated.py`'s claimed-identifier rule for the same reason both of those
are: a view is supposed to replay the dial. Run it after `sitcom.py` and
`curated.py`, any time before `build.py`.
"""
import collections
import json
import math
import os
import random
import re
import sys

import sitcom   # SERIES -- the hand-written public-domain list, and its tokens

CURATION = r"C:\Users\myerj\Desktop\ia-curation"
SAVANT = os.path.join(CURATION, "data", "savant_on_ia.json")
FILM_CATALOGS = ("catalog_moviesandfilms.jsonl", "catalog.jsonl")
TV_CATALOG = "catalog_tv.jsonl"

NUM = 11
NAME = "THE EVENING"
TAG = "Two half-hours and the feature, paired by the people who saved both"

SLOT = 1800
MINBREAK = 30            # keep in step with template.html and build.py
SOURCE_TV = 52           # where the half-hours come from

GRADES = ("Excellent", "Very Good")
FEATURE = (3300, 9000)   # a feature: not a short subject, not a serial in one lump
LEAD_INS = 2             # half-hours in front of it
CAP = 5                  # nights one series may carry

MAX_PICKS = 400          # neighbours.py: past this a favouriter is hoarding
MIN_FILM_VOTERS = 8      # a film nobody saved cannot be paired with anything
MIN_SERIES_VOTERS = 20   # nor can a series
MIN_SHARED = 3           # people who must have saved both ends
SEED = 11


def lst(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def as_text(v):
    return v if isinstance(v, str) else " ".join(str(x) for x in lst(v))


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def load_favourites():
    """identifier -> the people who saved it, films and television apart.

    Read straight off the `fav-<user>` collections in ia-curation's catalogs,
    which is where that project reads them too: a favourite is stored as a
    pseudo-collection, and it is the only per-person signal archive.org exposes.
    """
    films, tv, missing = {}, {}, []
    for name, bucket in [(f, films) for f in FILM_CATALOGS] + [(TV_CATALOG, tv)]:
        path = os.path.join(CURATION, "data", name)
        if not os.path.exists(path):
            missing.append(path)
            continue
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            ident = r["identifier"]
            if ident in bucket:
                continue
            users = {c[4:] for c in lst(r.get("collection"))
                     if c.startswith("fav-")}
            if users:
                bucket[ident] = (as_text(r.get("title")), users)
    if missing:
        sys.exit("missing ia-curation catalogs:\n  " + "\n  ".join(missing))
    picks = collections.Counter()
    for bucket in (films, tv):
        for _, users in bucket.values():
            picks.update(users)
    return films, tv, picks


def series_voters(tv, phrases):
    """Series phrase -> everyone who saved any item of it.

    Matched on the phrase rather than sitcom.py's short token, which is the one
    place the two must differ. `must` there identifies an item inside CH 52,
    where the series list is already the boundary; out here the token is loose
    on 14,798 rows -- "father" alone pulls in Father Knows Best, Make Room for
    Daddy and My Three Sons, none of which is Trouble with Father, and their
    collectors would be counted as its own.
    """
    out = {}
    for phrase in phrases:
        key = norm(phrase)
        short = norm(re.sub(r"(?i)^(the|a)\s+", "", phrase))
        users, n = set(), 0
        for title, who in tv.values():
            t = norm(title)
            if short in t or key in t:
                users |= who
                n += 1
        out[phrase] = (users, n)
    return out


def pair(film_voters, series, weight):
    """The series this film's collectors also saved, best first.

    A weighted cosine, not a weighted count. The count answers "how many people
    saved both", which the largest shelf wins by being largest; the cosine asks
    what share of *each* audience the overlap is, which is the question.
    """
    fw = sum(weight(u) for u in film_voters)
    if fw <= 0:
        return []
    out = []
    for phrase, (users, sw) in series.items():
        shared = film_voters & users
        if len(shared) < MIN_SHARED:
            continue
        out.append((sum(weight(u) for u in shared) / math.sqrt(fw * sw),
                    phrase, len(shared)))
    out.sort(reverse=True)
    return out


def select(candidates):
    """Best pairing first, until a series has carried CAP nights.

    Greedy rather than optimal on purpose. The strongest pairing on the channel
    is the one with the most to say, so it gets what it asked for and the cap
    falls on whoever turns up later with a weaker claim to the same series -- an
    assignment tuned for the best *total* would take Topper off My Man Godfrey
    to give it to something that needed it less.
    """
    nights, used = [], collections.Counter()
    for sc, item, pairs in sorted(candidates, key=lambda c: -c[0]):
        open_pairs = [p for p in pairs if used[p[1]] < CAP]
        if len(open_pairs) < LEAD_INS:
            continue
        chosen = open_pairs[:LEAD_INS]
        for _, phrase, _n in chosen:
            used[phrase] += 1
        nights.append({"score": sc, "film": item, "pairs": chosen})
    return nights


def order(nights, rng):
    """A seeded order with no series adjacent to itself.

    Score order front-loads the channel, which is the thing packChannel()'s
    shuffle exists to prevent and would be silly to reintroduce by hand. A plain
    shuffle instead runs Topper into Topper often enough to read as a fault, so
    the shuffle is repaired: walk it, and where a night shares a series with the
    one before, swap in the first later night that does not.
    """
    out = nights[:]
    rng.shuffle(out)
    for i in range(1, len(out)):
        prev = {p[1] for p in out[i - 1]["pairs"]}
        if not (prev & {p[1] for p in out[i]["pairs"]}):
            continue
        for j in range(i + 1, len(out)):
            if not (prev & {p[1] for p in out[j]["pairs"]}):
                out[i], out[j] = out[j], out[i]
                break
    return out


def episodes_for(tv_items, phrase, token, want, taken):
    """Half-hours of one series, never the same one twice on this channel."""
    pool = [i for i in tv_items
            if token in i["title"].lower() and i["id"] not in taken]
    return pool[:want]


def slots_for(dur):
    """Half-hours a programme needs. Mirrors packChannel()."""
    return max(1, -(-(dur + MINBREAK) // SLOT))


def build(nights, tv_items, tokens):
    """Nights -> the flat item list and the blocks that hold it together."""
    items, blocks, taken, quota = [], [], set(), collections.Counter()
    for night in nights:
        # Built into a scratch set, because a night that cannot be finished has
        # to give its half-hours back. CAP bounds the nights a series is picked
        # for, not the episodes CH 52 actually holds of it -- Abbott and
        # Costello is one item there and Riley is two -- so the supply runs out
        # first and the last night to want one is the one that goes short.
        # Consuming an episode for a night that is then dropped spends it twice.
        lead, want = [], set()
        for _sc, phrase, shared in night["pairs"]:
            got = episodes_for(tv_items, phrase, tokens[phrase], 1,
                               taken | want)
            if not got:
                break
            ep = dict(got[0])
            want.add(ep["id"])
            # The claim this half-hour is here to make. Without it the listing
            # is an unexplained sitcom in front of an unexplained film.
            ep["kind"] = "leadin"
            ep["shared"] = shared
            lead.append((phrase, ep))
        if len(lead) < LEAD_INS:
            continue
        for phrase, ep in lead:
            taken.add(ep["id"])
            quota[phrase] += 1
        lead = [ep for _p, ep in lead]
        film = dict(night["film"])
        film["kind"] = "feature"
        film["with"] = " and ".join(p[1] for p in night["pairs"])
        items += lead
        items.append(film)
        blocks += [[1, 1]] * len(lead)
        blocks.append([1, int(slots_for(film["dur"]))])
    return items, blocks, quota


def main():
    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)
    channels = {c["num"]: c for c in data["channels"]}
    if SOURCE_TV not in channels:
        sys.exit(f"no CH {SOURCE_TV} in channels.json -- run sitcom.py first")
    tv_items = channels[SOURCE_TV]["items"]
    tokens = {s[0]: s[1] for s in sitcom.SERIES}

    with open(SAVANT, encoding="utf-8") as f:
        graded = {r["ia"]["identifier"]: r for r in json.load(f)
                  if r["movie"] in GRADES}

    # Every copy of a graded film the dial already holds, with its file, its
    # runtime and Erickson's prose attached. One film can sit on two channels;
    # either copy will do, since they are the same archive.org item.
    on_air = {}
    for c in data["channels"]:
        if c["num"] == NUM:
            continue
        for it in c["items"]:
            if it["id"] in graded and FEATURE[0] <= it["dur"] <= FEATURE[1]:
                on_air.setdefault(it["id"], it)

    films, tv, picks = load_favourites()

    def weight(u):
        return 0.0 if picks[u] > MAX_PICKS else 1.0 / math.log(2 + picks[u])

    series = {phrase: (users, sum(weight(u) for u in users))
              for phrase, (users, _n) in series_voters(tv, list(tokens)).items()
              if len(users) >= MIN_SERIES_VOTERS}

    candidates, thin = [], 0
    for ident, item in on_air.items():
        voters = films.get(ident, (None, set()))[1]
        if len(voters) < MIN_FILM_VOTERS:
            thin += 1
            continue
        pairs = pair(voters, series, weight)
        if len(pairs) >= LEAD_INS:
            candidates.append((pairs[0][0], item, pairs))

    nights = order(select(candidates), random.Random(SEED))
    items, blocks, quota = build(nights, tv_items, tokens)
    if len(items) < LEAD_INS + 1:
        sys.exit(f"only {len(items)} items -- has curated.py run?")

    data["channels"] = [c for c in data["channels"] if c["num"] != NUM]
    data["channels"].append({"num": NUM, "name": NAME, "tag": TAG,
                             "items": items, "blocks": blocks})
    data["channels"].sort(key=lambda c: c["num"])
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    feats = [i for i in items if i.get("kind") == "feature"]
    cycle = sum(b[1] for b in blocks) * SLOT
    content = sum(i["dur"] for i in items)
    years = sorted(i["year"] for i in feats if i.get("year"))
    print(f"CH {NUM:02d} {NAME}: {len(feats)} nights, {years[0]}-{years[-1]}, "
          f"{cycle / 3600:.1f}h cycle, {(1 - content / cycle) * 100:.0f}% ads",
          file=sys.stderr)
    print(f"  candidates paired    {len(candidates):>3} of {len(on_air)} graded "
          f"features on the dial ({thin} too thinly saved to pair)",
          file=sys.stderr)
    print(f"  excellent            "
          f"{sum(1 for i in feats if i.get('grade') == 'Excellent'):>3}",
          file=sys.stderr)
    for phrase, n in quota.most_common():
        print(f"    {phrase:<38}{n:>2} night" + ("s" if n != 1 else ""),
              file=sys.stderr)
    undescribed = sum(1 for i in items if not i.get("desc"))
    if undescribed:
        print(f"  {undescribed} without a description -- run describe.py",
              file=sys.stderr)


if __name__ == "__main__":
    main()
