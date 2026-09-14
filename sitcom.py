"""Build the half-hour comedy channel from named public-domain series.

The other two builders work by *collection*: harvest.py takes everything in
`classic_tv`, curated.py takes a curator's whole shelf. Neither works here.
Searching for a genre — `subject:(sitcom)` — returns Leave It to Beaver, Are
You Being Served and NewsRadio on the first page, all three still in copyright
and uploaded by someone who didn't care. There is no collection whose boundary
is "sitcoms that are actually free", so the boundary has to be the series list
below, written out by hand.

Every title here lapsed into the public domain the same way: a 1950s producer
who owned the negative didn't file the renewal 28 years later. That is why the
list is so heavy on syndication-era filmed comedy and contains none of the
network shows people remember better — CBS renewed, Desilu renewed.

Caps are per series, not per channel. Jack Benny alone has 200 episodes free;
without a cap the channel is the Jack Benny channel with guests. The lineup is
then dealt round-robin so a viewer who leaves it on doesn't get fourteen
consecutive Bennys.
"""
import json, re, sys, time
from concurrent.futures import ThreadPoolExecutor

import harvest   # reuse search(), probe(), clean(), blocked(), claim()

NUM = 52
NAME = "LAUGH TRACK"
TAG = "Half-hour comedy, 1950-1964"

# 11.6 to 29 minutes. The ceiling is the load-bearing number and it is 1740,
# not 1800, because packChannel() adds a 60s break to every programme before
# choosing a slot: at 1741s an episode needs 1801s, overflows the half-hour,
# and is given a *whole hour* — 29 minutes of Jack Benny and 31 minutes of
# commercials. 27 episodes landed in that 1741-1800 window on the first build
# and dragged the channel to 28% ads, the worst on the dial.
#
# They are there because a recording made off-air already contains the ads, so
# it measures a full half-hour rather than the ~22 minutes of programme. The
# uncut ones cost a slot and a half each; cutting the band is the fix, and the
# per-series caps simply backfill from the next candidate down.
#
# The floor drops truncated fragments. Both ends together also throw out the
# "Complete TV Series" single-file dumps.
BAND = (700, 1740)

# (search phrase, cap). The phrase is matched against the *title* by
# archive.org, then re-checked here against `must` — the search tokenises, so
# `title:("Topper")` on its own would be happy with anything containing the
# word.
#
#   in `classic_tv` unless marked. That collection is curated toward free
#   material, which is a second filter on top of the series list: the same
#   title search run site-wide pulls in TV-rip uploads of the 1980s remakes.
SERIES = [
    ("The Jack Benny Program",   "benny",    14),
    ("The Adventures of Ozzie and Harriet", "ozzie", 14),
    ("I Married Joan",           "joan",     12),
    ("Meet Corliss Archer",      "corliss",  12),
    ("The Life of Riley",        "riley",    12),
    ("Date with the Angels",     "angels",   10),
    ("Life with Elizabeth",      "elizabeth", 10),
    ("Trouble with Father",      "father",   10),
    ("Burns and Allen",          "allen",    10),
    ("Topper",                   "topper",    8),
    ("Beverly Hillbillies",      "hillbill",  8),
    ("Petticoat Junction",       "petticoat", 6),
    ("Our Miss Brooks",          "brooks",    4),
    ("My Little Margie",         "margie",    4),
    # Not in classic_tv; the Turner-sourced uploads are episode-per-item, which
    # is what the band wants. Site-wide search, so `must` is doing real work.
    ("The Abbott and Costello Show", "abbott", 10, True),
]


# Omnibus uploads: one item holding a whole run. A few carry a single-episode
# derivative and so survive the duration band, but they list under a title that
# names no episode and they are not what an episode channel wants.
OMNIBUS = re.compile(r"(?i)complete (tv )?(series|season)|full series|all \d+ episodes")


# One prolific uploader of 1950s television brands every item with a shelf
# prefix — "Fifties Television:", "Early Television Comedy:", "1950's
# Television: -". It is their cataloguing, not the programme's name, and it
# reads badly in a listings grid where the channel already says what this is.
PREFIX = re.compile(r"(?i)^\s*(?:early |fifties |1950'?s |1960'?s )+"
                    r"television(?: comedy)?\s*:\s*-?\s*")
# Quote characters, except an apostrophe doing work inside a word: uploaders
# wrap episode names in ''these'' and "these", but "George's Old Flame" is the
# actual title and must survive.
QUOTES = re.compile(r"(?<![A-Za-z])['\"‘’“”]{1,2}|['\"‘’“”]{1,2}(?![A-Za-z])")


def tidy(title):
    """Strip an uploader's shelf prefix and their quoting habits.

    Deliberately narrow. harvest.clean() carries a note about bare-year rules
    destroying real titles, and the same trap is here: a rule broad enough to
    fix every mangled episode name in this channel would eat "Topper" and
    "My Little Margie" too. So: only the prefix above, only quote characters,
    and if the result looks damaged, keep what we were given.
    """
    t = PREFIX.sub("", title)
    t = QUOTES.sub("", t).strip(" -–—:,|")
    t = re.sub(r"\s{2,}", " ", t)
    return t if len(t) >= 3 else title.strip()


def epkey(phrase, title):
    """Identify the *episode*, so two uploads of it collide.

    The dedupe in harvest.py is exact-title, which is right for films and
    useless here: "Petticoat Junction - Herbie Gets Drafted" and
    'Petticoat Junction "Herbie Gets Drafted"' are the same half-hour from two
    uploaders, and a 30-item channel that plays it twice a loop is noticeably
    broken. Strip everything an uploader improvises — the series name they
    prefixed, the season code they chose a format for, the punctuation — and
    compare what is left.
    """
    t = title.lower()
    for w in re.findall(r"[a-z]+", phrase.lower()):
        if w not in ("the", "and", "with", "a", "of"):      # too common to cut
            t = t.replace(w, " ")
    t = re.sub(r"\bs\d{1,2}\s*[ex]\d{1,2}\b", " ", t)       # S01E02, s1 e14
    t = re.sub(r"\b[ex]p?\.?\s*\d{1,3}\b", " ", t)          # Ep01, E19, 02
    t = re.sub(r"\b(19|20)\d\d\b", " ", t)                  # stray years
    t = re.sub(r"[^a-z0-9]+", " ", t)
    # "The" is too common to cut wherever it appears — "The Clampetts Strike
    # Oil" needs it. But the series prefix leaves one stranded at the front,
    # which is the difference between "the getting settled" and the same
    # upload titled "getting settled".
    return re.sub(r"^(the|a) ", "", " ".join(t.split()))


def pull(spec, taken):
    """One series -> up to `cap` playable episodes."""
    phrase, must, cap = spec[0], spec[1], spec[2]
    wide = len(spec) > 3 and spec[3]
    q = 'mediatype:movies AND title:("%s")' % phrase
    if not wide:
        q = 'collection:"classic_tv" AND ' + q
    # archive.org's search endpoint returns a sporadic 502 under no particular
    # load. Unretried it is silent data loss, not an error: the series just
    # contributes nothing and the channel comes out short a show, which is only
    # visible if you are reading the counts.
    docs = None
    for attempt in range(4):
        try:
            docs = harvest.search(q, cap * 8)
            break
        except Exception as e:
            if attempt == 3:
                print(f"  {phrase:<38} SEARCH FAILED {e}", file=sys.stderr)
                return []
            time.sleep(2 * (attempt + 1))

    # Re-check the tokenised title match, and drop anything already on another
    # channel before spending a probe on it. THE VAULT is drawn from the same
    # collection and has first claim.
    cand = [d for d in docs
            if must in str(d.get("title") or "").lower()
            and d["identifier"] not in taken]

    with ThreadPoolExecutor(max_workers=16) as ex:
        probed = list(ex.map(harvest.probe, cand))

    out, seen, dropped = [], set(), 0
    for item in probed:
        if not item or harvest.blocked(item):
            continue
        if not (BAND[0] <= item["dur"] <= BAND[1]):
            continue
        if OMNIBUS.search(item["title"]):
            dropped += 1
            continue
        item["title"] = tidy(item["title"])
        key = item["title"].lower()
        if item["id"] in taken or key in taken:
            continue
        # An episode name that survives the strip identifies the episode; one
        # that strips down to nothing ("Petticoat Junction") identifies only
        # the series, so fall back to the identifier and keep it.
        ek = epkey(phrase, item["title"]) or item["id"]
        if ek in seen:
            dropped += 1
            continue
        seen.add(ek)
        taken.add(item["id"]); taken.add(key)
        # No series field is stored: `cand` above already required `must` in
        # the title, so every item here names its own series and a separate
        # label would only stutter in the listing.
        out.append(item)
        if len(out) >= cap:
            break
    note = f"  ({dropped} dupe/omnibus dropped)" if dropped else ""
    print(f"  {phrase:<38} {len(out):>3} of {len(cand):>4} candidates{note}",
          file=sys.stderr)
    return out


def deal(groups):
    """Round-robin the series together, longest run first."""
    groups = sorted(groups, key=len, reverse=True)
    out, i = [], 0
    while any(len(g) > i for g in groups):
        for g in groups:
            if len(g) > i:
                out.append(g[i])
        i += 1
    return out


def main():
    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)
    data["channels"] = [c for c in data["channels"] if c["num"] != NUM]

    taken = set()
    harvest.claim(data, taken)
    print(f"{len(data['channels'])} existing channels, "
          f"{len(taken)//2} items claimed\n", file=sys.stderr)

    groups = [g for g in (pull(s, taken) for s in SERIES) if g]
    items = deal(groups)
    if len(items) < 4:
        print("\ntoo thin, nothing written", file=sys.stderr)
        return 1

    data["channels"].append({"num": NUM, "name": NAME, "tag": TAG,
                             "items": items})
    data["channels"].sort(key=lambda c: c["num"])
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    print(f"\nCH {NUM} {NAME}: {len(items)} episodes from "
          f"{len(groups)} series", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
