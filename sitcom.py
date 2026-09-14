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
TAG = "Half-hour comedy, 1950-1966"

# 11.6 to 29.5 minutes. The ceiling is SLOT - MINBREAK: an episode longer than
# this needs the next half-hour up and is handed a whole one, which is how the
# channel first came out at 28% ads. It was 1740 while packChannel() insisted
# on a 60s break; that floor is now 30s, so 30 seconds of ceiling come back and
# with them the uncut half-hours — most of the Burns and Allen shelf, which is
# recorded off-air with its own commercials still in it.
#
# Keep in step with MINBREAK in template.html. Too high and the channel pays a
# full extra slot per episode; too low and the uncut recordings all drop out.
#
# The floor drops truncated fragments. Both ends together also throw out the
# "Complete TV Series" single-file dumps.
BAND = (700, 1770)

# The years this channel claims. A year outside them is not the programme's:
# the `youtube-` re-uploads carry their *upload* date, which is how "The
# Abbott and Costello Show (2019)" came to sit in a grid whose channel tag
# says 1950-1966. Wide enough to allow a syndication print dated a year or two
# either side of the run; narrow enough that an upload date cannot pass.
ERA = (1945, 1970)

# (search phrase, cap). The phrase is matched against the *title* by
# archive.org, then re-checked here against `must` — the search tokenises, so
# `title:("Topper")` on its own would be happy with anything containing the
# word.
#
#   in `classic_tv` unless marked. That collection is curated toward free
#   material, which is a second filter on top of the series list: the same
#   title search run site-wide pulls in TV-rip uploads of the 1980s remakes.
#
# The six series named in CANON below are also the whole of suggest.py's CH 07
# COMEDY. Their caps are set a little higher than the rest of the tail
# deserves, because they now carry a second channel as well as their share of
# this one -- Our Miss Brooks at four episodes was a fine fifteenth of a
# round-robin and far too thin to be a sixth of a service.
SERIES = [
    ("The Jack Benny Program",   "benny",    14),
    ("The Adventures of Ozzie and Harriet", "ozzie", 14),
    ("I Married Joan",           "joan",     12),
    ("Meet Corliss Archer",      "corliss",  12),
    ("The Life of Riley",        "riley",    12),
    ("Date with the Angels",     "angels",   10),
    ("Trouble with Father",      "father",   10),
    ("Topper",                   "topper",   10),
    ("Beverly Hillbillies",      "hillbill",  8),
    ("Petticoat Junction",       "petticoat", 6),
    ("My Little Margie",         "margie",    4),
    # Site-wide, the fourth field. `classic_tv` is a second filter on top of
    # the series list and usually worth having; for these three it is costing
    # more than it saves now that they carry a sixth of CH 07 COMEDY each.
    # Dropping it is worth 4 -> 6 episodes for Our Miss Brooks, 7 -> 8 for
    # Burns and Allen and 10 -> 12 for Life with Elizabeth. A thin return for
    # a much wider net, and the net is what costs: site-wide, Our Miss Brooks
    # comes back mostly as the *radio* show (see SHOUTING above) and the
    # candidate pool goes from 4 items to 46 to gain two. Worth it only where
    # the series was too thin to stand, which is why the rest of the list
    # stays inside the collection.
    #
    # Abbott and Costello is not in the collection at all -- the Turner-sourced
    # uploads are episode-per-item, which is what the band wants.
    ("Burns and Allen",          "allen",    12, True),
    ("Life with Elizabeth",      "elizabeth", 12, True),
    ("Our Miss Brooks",          "brooks",   12, True),
    ("The Abbott and Costello Show", "abbott", 10, True),
]

# Read by suggest.py. Kept here rather than there because this is the file that
# knows what the phrases mean.
CANON = ["The Jack Benny Program", "The Adventures of Ozzie and Harriet",
         "Burns and Allen", "Life with Elizabeth", "Our Miss Brooks", "Topper"]


# Omnibus uploads: one item holding a whole run. A few carry a single-episode
# derivative and so survive the duration band, but they list under a title that
# names no episode and they are not what an episode channel wants.
#
# The second half catches the season pack, which is the same thing under a
# different name: "The Adventures Of Ozzie And Harriet Season One", "Season 8
# to 14". Four of Ozzie's fourteen were these. Anchored at the end and
# requiring the season token last, so an episode that happens to be *called*
# something ending in a number is untouched.
OMNIBUS = re.compile(r"(?i)complete(?:\s+\w+){0,5}?\s+(?:tv\s+)?(?:series|season)"
                     r"|full series|\bepisodes\b|\bdis[ck]\s*\d"
                     r"|seasons?\s+(?:\d{1,2}|one|two|three|four|five|six|seven|"
                     r"eight|nine|ten)\s*(?:(?:to|thru|through|[-–—])\s*\d{1,2})?"
                     r"\s*$")

# Also not an episode, and harder to see coming: the retrospective and the fan
# compilation, which pass the title match and sit squarely inside the duration
# band. "Betty White LIFE WITH ELIZABETH Revisited (1998, KCOP TV 50th
# Anniversary)" is twenty-six minutes of exactly the wrong thing.
NOTEPISODE = re.compile(r"(?i)\b(?:revisited|retrospective|anniversary|"
                        r"documentary|interview|tribute|compilation|best of|"
                        r"bloopers?|outtakes?|opening credits|theme song|"
                        r"promo|trailer)\b")

# An uploader's run-on index line rather than a title: "OUR MISS BROOKS
# MARINATED HEARING THE FESTIVAL SUZI PRENTISS CONKLIN PLA". These are the old
# time *radio* compilations, four half-hours to an item with every episode name
# jammed into one field, and going site-wide for Our Miss Brooks brought back
# eight of them against four of the television show. They are caught on the
# shouting: past a certain length a title with no lower case in it is a
# catalogue entry, and none of these series has an episode named that way.
SHOUTING = re.compile(r"^[^a-z]{34,}$")


# One prolific uploader of 1950s television brands every item with a shelf
# prefix — "Fifties Television:", "Early Television Comedy:", "1950's
# Television - ". It is their cataloguing, not the programme's name, and it
# reads badly in a listings grid where the channel already says what this is.
# Others prefix the station they taped it off ("WGN Channel 9 - ") or their
# own reaction to it ("LMAO: ").
#
# The noun after the adjectives is not always "television": the same shelves
# run as "Classic TV Comedy:" and "Fifties Popular Culture -", which the first
# version of this let through and which put the uploader's filing system in
# front of six of ten Burns and Allen listings.
ADJ = (r"(?:early |classic |comedic |vintage |fifties |sixties |"
       r"1950'?s |1960'?s )+")
PREFIX = re.compile(r"(?i)^\s*(?:" + ADJ + r"(?:television|tv)(?: comedy)?"
                    r"|" + ADJ + r"popular culture"
                    r"|lmao|w[a-z]{2,3} channel \d+|k[a-z]{2,3} tv)"
                    r"\s*[:\-–—]\s*-?\s*")
# "RetroVision Theater Presents Life With Elizabeth" — the same thing without
# the punctuation. Kept separate so the rule above can go on requiring a
# separator, which is most of what stops it eating a real title.
PRESENTS = re.compile(r"(?i)^\s*[a-z][a-z ]{2,28}\s+presents\s*[:\-–—]?\s*")

# "61 02 12 The Jack Benny Program S 11e 17 Death Row Sketch" — one uploader
# files every episode under YY MM DD plus a season code. The air date is real
# information, so it is lifted into `year` before being cut rather than simply
# thrown away; the season code is not, and goes.
DATECODE = re.compile(r"^\s*([0-9]{2})\s+[0-9]{2}\s+[0-9]{2}\s+")
# Season codes arrive spaced ("S 11e 17"), punctuated ("Topper: S1E14,") and
# truncated at the end of a cut title, so the separators either side are part
# of the match rather than assumed to be spaces.
SEASONCODE = re.compile(r"(?i)[\s:,\-–—]*\bs\s*[0-9]{1,2}\s*e?\s*[0-9]{1,2}\b"
                        r"[\s:,\-–—]*")
# The same code written out: "The Jack Benny Program, Season 2, Episode 1".
# Not folded into SEASONCODE because the abbreviated form must stay tight —
# `\bs\s*\d` spelled loosely enough to also mean the word would start eating
# ordinary titles. A bare "Season N" at the end of a title never reaches here;
# OMNIBUS rejects the item outright.
SEASONWORD = re.compile(r"(?i)[\s:,\-–—]*\bseasons?\s*[0-9]{1,2}"
                        r"(?:[\s:,\-–—]*\bep(?:isode)?s?\.?\s*[0-9]{1,3}\b)?"
                        r"[\s:,\-–—]*")
# A trailing "— Aired: 11/04/1951", which the date already says.
AIRED = re.compile(r"(?i)\s*[-–—]?\s*aired\s*:?\s*[0-9/.\-]+\s*$")
# An air date appended without the word: "The Jack Benny program - 01/17/1954",
# "The Jack Benny Program (3/April/1955)". The date is real information, so the
# year is lifted out before the rest is cut — the same bargain DATECODE makes
# at the front of a title. Three components required, so a score or a fraction
# in a real title ("9 1/2 Weeks") cannot match.
TAILDATE = re.compile(r"(?i)\s*[-–—(]?\s*[0-9]{1,2}\s*[/.\-]\s*"
                      r"(?:[0-9]{1,2}|[a-z]{3,9})\s*[/.\-]\s*"
                      r"((?:19|20)[0-9]{2}|[0-9]{2})\s*\)?\s*$")
# Some uploaders park the episode name in a parenthetical instead of the title:
# "Burns and Allen (Episode title: Too Much of the Mortons?)". It is the only
# episode name the item carries, so it is promoted into the title rather than
# cut as cataloguing — without this the item reads as a bare "Burns and Allen"
# and names_episode() below throws it out.
PARENTITLE = re.compile(r"(?i)\s*\(\s*(?:episode(?:\s+title)?|title)\s*:\s*"
                        r"([^)]+?)\s*\)\s*$")
# The other trailing parenthetical from the same shelf, which is cataloguing
# and goes: "(Episode aired 11 Oct 1953)", "(Possibly a rerun)". Cut after
# PARENTITLE has had its turn, so an item carrying both keeps the episode name.
PARENNOTE = re.compile(r"(?i)\s*\((?:episo?de?\s+)?(?:aired|air date|possibly|"
                       r"probably|maybe|unconfirmed|source)\b[^)]*\)\s*$")
# UTF-8 bytes that were read as latin-1: "–" arrives as "â\x80\x93". Repaired
# by reversing the mistake rather than deleting the characters, which gets the
# real dash back instead of a gap.
MOJIBAKE = re.compile(r"[ÂÃâ][-¿]")
# Truncation debris. harvest.clean() cuts titles at 70 characters, which can
# land mid-parenthetical and leave "... The Drugstore (Comple".
ORPHAN_PAREN = re.compile(r"\s*\([^)]{0,40}$")
# A trailing bare date, "( 1953 10 09)", and an uploader's shelf tag,
# "(1954 TV Com Fan)" — both cataloguing rather than title.
PAREN_JUNK = re.compile(r"\s*\(\s*(?:19|20)\d\d(?:[\s./-]+\d{1,2}){0,2}"
                        r"(?:\s+[A-Za-z][A-Za-z ]{1,24})?\s*\)")


def demojibake(t):
    if not MOJIBAKE.search(t):
        return t
    try:
        return t.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return t
# Quote characters, except an apostrophe doing work inside a word: uploaders
# wrap episode names in ''these'' and "these", but "George's Old Flame" is the
# actual title and must survive.
QUOTES = re.compile(r"(?<![A-Za-z])['\"‘’“”]{1,2}|['\"‘’“”]{1,2}(?![A-Za-z])")


def tidy(title):
    """Strip an uploader's cataloguing. Returns (title, year_or_None).

    Deliberately narrow. harvest.clean() carries a note about bare-year rules
    destroying real titles, and the same trap is here: a rule broad enough to
    fix every mangled episode name in this channel would eat "Topper" and
    "My Little Margie" too. So: only the prefixes above, only quote
    characters, only the two date/season codes — and if the result looks
    damaged, keep what we were given.
    """
    t = demojibake(title)
    # A U+FFFD that arrived already lost: "Season 4, Episode 3 <?> Humphrey
    # Bogart guest". demojibake() cannot recover it because the bytes are gone,
    # but it stood where a dash stood, and putting one back gets a readable
    # title instead of a black diamond in the grid.
    t = t.replace("�", "-")
    # ORPHAN_PAREN first, and it has to be: the titles carrying an episode name
    # in a parenthetical are the longest on the channel and so the ones clean()
    # cuts, which leaves "(Episode title: Too Much of the Mortons?) (Possib" --
    # a closed parenthetical followed by an open one. PARENTITLE anchors at the
    # end, so it cannot see the name it wants until the debris is gone.
    t = ORPHAN_PAREN.sub("", t)
    t = PARENNOTE.sub("", t)
    t = PARENTITLE.sub(r" - \1", t)
    t = PARENNOTE.sub("", t)              # "...(Title: X) (Episode aired ...)"
    t = PAREN_JUNK.sub("", t)
    t = AIRED.sub("", t)

    # The date code, if present, is the only year these items carry. Two-digit
    # and unambiguous: this channel stops at 1964, so 50-99 is 19xx and there
    # is no 20xx case to get wrong.
    year = None
    m = DATECODE.match(t)
    if m:
        yy = int(m.group(1))
        if 45 <= yy <= 99:
            year = 1900 + yy
        t = DATECODE.sub("", t)

    m = TAILDATE.search(t)
    if m:
        yy = int(m.group(1))
        if yy > 99:
            year = year or yy
        elif 45 <= yy <= 99:
            year = year or (1900 + yy)
        t = TAILDATE.sub("", t)

    t = SEASONCODE.sub(" - ", t)
    t = SEASONWORD.sub(" - ", t)
    for _ in range(2):                      # "LMAO: Fifties Television - ..."
        t = PREFIX.sub("", t)
    t = PRESENTS.sub("", t)
    t = QUOTES.sub("", t).strip(" -–—:,|")
    t = re.sub(r"\s*-\s*-\s*", " - ", t)
    t = re.sub(r"\s{2,}", " ", t)
    # Cutting a season code out of "Topper S01E01 Topper Meets The Ghosts"
    # leaves the series name twice. Only collapse an exact repeat.
    t = re.sub(r"(?i)^(.{3,}?) - \1\b", r"\1", t)
    t = ORPHAN_PAREN.sub("", t).strip(" -–—:,|")

    # "Jack Takes The Stewarts To A". clean() cuts at 70 characters *before*
    # this function strips the uploader's date and season code, so a title that
    # arrived at the limit is short here and still truncated — which is why the
    # length is tested on what came in, not on what is going out. Dropping the
    # dangling preposition does not restore the name, but "Jack Takes The
    # Stewarts" reads as a title where the other reads as a bug.
    # Twice, because a cut lands as often on "...To The" as on "...To".
    if len(title) >= 68:
        for _ in range(2):
            t = re.sub(r"(?i)\s+(?:to|the|a|an|and|of|in|for|with|on|at|his|"
                       r"her|their|is|was)\s*$", "", t)

    # One separator between series and episode. The shelf uses " - ", ": " and
    # " ~ " interchangeably and the three of them side by side in a column read
    # as three different kinds of programme. A colon between digits is left
    # alone, being a time rather than a separator.
    t = re.sub(r"(?<!\d)\s*[:~]\s*(?!\d)", " - ", t).strip(" -–—:,|")
    return (t if len(t) >= 3 else title.strip()), year


# Words that carry no episode in them: the articles, and the cataloguing an
# uploader adds around a series name. "Misc" and "No." are deliberately absent
# — the whole Life with Elizabeth shelf is filed as "Misc episode No. 4", which
# is a poor title and still a real distinction between one half-hour and the
# next.
NOTATITLE = re.compile(r"(?i)\b(?:the|a|an|and|with|of|tv|show|program+e?|"
                       r"episode|ep|season|part|full)\b")


def names_episode(phrase, title):
    """Does the title identify the half-hour, or only the series?

    "Burns and Allen", "Burns and Allen # 68" and "The Beverly Hillbillies TV
    Show" all name a programme the guide cannot tell apart from the next one,
    and two of them in a row read as the channel repeating itself rather than
    as two different episodes. epkey() below keeps these by falling back to the
    identifier, which is right for *dedupe* — they are genuinely different
    uploads — and wrong for the listing, so the judgement is made separately
    here and they are dropped.
    """
    t = title.lower()
    for w in re.findall(r"[a-z]+", phrase.lower()):
        t = re.sub(r"\b%s\b" % re.escape(w), " ", t)
    t = NOTATITLE.sub(" ", t)
    return bool(re.sub(r"[^a-z]+", " ", t).split())


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
        if (OMNIBUS.search(item["title"]) or NOTEPISODE.search(item["title"])
                or SHOUTING.match(item["title"])):
            dropped += 1
            continue
        item["title"], yr = tidy(item["title"])
        if yr and not item.get("year"):
            item["year"] = yr
        # A year outside the channel's era belongs to the upload, not the
        # programme. Dropped rather than corrected: there is nothing to correct
        # it to, and no year at all reads better than a wrong one.
        if item.get("year") and not (ERA[0] <= item["year"] <= ERA[1]):
            item["year"] = None
        if not names_episode(phrase, item["title"]):
            dropped += 1
            continue
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
    note = f"  ({dropped} dupe/omnibus/unnamed dropped)" if dropped else ""
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
