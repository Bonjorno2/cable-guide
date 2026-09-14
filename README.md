# THE GUIDE

A cable television guide that is always already in progress. Eight channels
built from curated Internet Archive collections, running on a real schedule.
Tune in at 8:17 and you are seventeen minutes into the movie.

## The idea

There is no streaming backend and no playlist state. **The schedule is a pure
function of wall-clock time.** Every viewer who loads the page at the same
moment is watching the same frame of the same programme, because both are
derived from the same arithmetic:

```
elapsed = (now - EPOCH) mod channel_cycle_length
```

That single decision is what makes it feel like television instead of a video
player. You cannot pause it, you cannot pick a start point, and if you look
away you miss something.

## How a schedule is built

**1. Items are packed into blocks of whole 30-minute slots.** A six-minute
cartoon does not get its own half hour — it shares one with the cartoons
either side of it, the way a Saturday morning block actually worked. Anything
too long to share keeps a block to itself.

Packing in playlist order wastes a lot of slot (a 17-minute film followed by a
15-minute one strands each in its own half hour, pushing the channel past 40%
commercials), so blocks are filled longest-first, taking whatever still fits,
then dealt back out in a seeded order so the channel is not front-loaded.
`CONTENT = 0.86` is the target content share per slot; it lands the lineup at
~23% commercials on average, which is roughly period-accurate.

The point of slotting at all: **the guide grid aligns to :00 and :30**, like a
real listing. Without it the grid is a mess of ragged slivers and the
nostalgia evaporates.

**2. Breaks are distributed through the block, not dumped at the end.** Every
item is cut into acts of roughly a quarter hour, a break follows each act, and
the slot's spare time is shared across those breaks. Act and break lengths
carry a ±15% jitter from the same seeded PRNG, so the rhythm is irregular but
identical for every viewer.

A 90-minute slot holding a 79-minute feature becomes five acts of 15–18
minutes with ~90-second breaks between them:

```
SHOW  0:00–16:44   Bloody Pit of Horror
 ad  16:44–18:15
SHOW 18:15–32:57   Bloody Pit of Horror
 ad  32:57–34:39
...
SHOW 72:33–88:40   Bloody Pit of Horror
 ad  88:40–90:00
```

and a 30-minute cartoon block becomes three shorts with breaks between:

```
SHOW  0:00–7:14    More Popeye cartoons!
 ad   7:14–10:13
SHOW 10:13–17:27   The Brave Tin Soldier
 ad  17:27–20:04
SHOW 20:04–27:08   Betty Boop: Snow White
 ad  27:08–30:00
```

Break content is drawn from a PRNG seeded on
`(channel, cycle, block, break index)`, so which commercial you get is also
the same for everyone. Tune in mid-break and you get a 1956 Chevrolet ad and a
"WE'LL RETURN TO…" bug. That is the part that sells it.

## Where the programmes come from

Three harvesters, because popularity, curation and copyright status are
different things.

`harvest.py` asks archive.org for a collection sorted by downloads. That is
fine for newsreels and cartoons, where any given reel is interchangeable.

`curated.py` reads the **ia-curation** project instead, and it is where the
good channels come from. That project found the people who were already doing
the curating:

- **`curators.json`** — 129 uploader shelves scored for coherence. Someone who
  has uploaded only Turkish superhero pictures for a decade is not archiving,
  they're curating; their shelf is a channel already. This is where CH 27
  KILINK, CH 28 ANARQUISMO and CH 29 MOMMARTZ come from — lineups no
  collection query would ever assemble.
- **`savant_on_ia.json`** — 800 films Glenn Erickson graded for DVD Savant,
  matched to a free archive.org copy. Becomes CH 34, sorted best-grade-first.
- **`double_endorsed.json`** — 154 films that sit on a coherent shelf *and*
  were graded by Erickson. Two independent judgements, neither aware of the
  other. This is CH 15 DOUBLE, and it is the best channel on the dial.

Grades and directors ride along into the UI: the now-playing panel shows
`EXCELLENT · dir. Carol Reed`, and Excellent-graded programmes carry a ★ in
the guide.

`sitcom.py` builds one channel — CH 52 LAUGH TRACK — and exists because
neither of the other two can. There is no collection whose boundary is
"sitcoms that are actually free", and the obvious query is a trap: searching
`subject:(sitcom)` inside `classic_tv` returns Leave It to Beaver, Are You
Being Served and NewsRadio on the first page, all three still in copyright and
uploaded by someone who didn't care. So the boundary is a hand-written list of
15 series that lapsed into the public domain the same way — a 1950s producer
who owned his negative and didn't file the renewal 28 years later. That is
also why the list is heavy on syndicated filmed comedy and contains none of
the network shows people remember better: CBS renewed, Desilu renewed.

Two details that turned out to matter more than the series list:

- **Caps are per series.** Jack Benny alone has 200 free episodes; uncapped,
  the channel is the Jack Benny channel with guests. The lineup is then dealt
  round-robin, so leaving it on doesn't get you fourteen consecutive Bennys.
- **The duration ceiling is 1740s, not 1800s.** `packChannel()` adds a 60s
  break before choosing a slot, so a 1741s episode needs 1801s, overflows the
  half-hour and is given a *whole hour* — 29 minutes of programme, 31 minutes
  of commercials. 27 episodes landed in that window on the first build and
  took the channel to 28% ads, the worst on the dial; the ceiling brought it
  to 16%. They are there because a recording made off-air still contains its
  original ads, so it measures a full half-hour rather than ~22 minutes.

### Descriptions

**3,369 of 3,576 programmes (94%) carry a listing description**, from two
sources, best first:

1. **Glenn Erickson's own prose**, for the 324 films ia-curation matched to a
   DVD Savant review. A critic writing about the film beats anything an
   uploader typed into a metadata box, and it is credited in the panel as
   *— DVD SAVANT*.
2. **The archive.org `description` field** for the rest, read from
   `<id>_meta.xml` on the data nodes.

Raw metadata is not usable as-is, though. The cleaning in `describe.py` is
most of that file, and each rule came from reading what actually came back:

| problem | example |
|---|---|
| nested boilerplate | `National Archives description: "The original release sheet reads: …` — one pass leaves the inner prefix behind a quote |
| housekeeping sentences | *"PLEASE NOTE: A much higher-quality DV version (2.3 GB) now available at http://…"* |
| uploader narrating the transfer | *"This one was gotten from an old hard drive… I remember"* |
| catalogue records, not synopses | `KEYSTONE 1015 ft., rel. Feb. 9 1914 dir. … cast: …` |
| Wikipedia attribution prefix | *"The following concise, informative description was taken from…"* |

Filtering happens per *sentence*, not per description, so a good synopsis that
merely ends with a link keeps the synopsis. Anything left under 25 characters
is dropped rather than shown as a stub — hence 94% rather than 100%.

`--repolish` re-runs the cleaning rules over descriptions already stored, with
no network, which is how to iterate on those rules without a four-minute
refetch.

**Size**: descriptions roughly doubled `index.html`, 616 KB → **1.2 MB**
(371 KB gzipped, which is what a static host actually sends). Lower `MAXLEN`
in `describe.py` and re-run `--repolish` if that matters more than the prose.

### The speed trick, taken from ia-curation's README

Its own harvest hit the same wall mine did — the metadata API collapses to
about **one request per second regardless of concurrency**. The same data is
served from archive.org's **data nodes** via `/download/<id>/<id>_files.xml`,
which is not throttled that way. Measured here: **30 items/sec at 24 threads
versus 1/sec**. `curated.py` uses `_files.xml` and reads exact per-file
durations straight out of it, so 3,500 programmes resolve in minutes.

## Files

| File | Role |
|---|---|
| `curated.py` | Builds channels from the ia-curation lists; durations via `_files.xml` on the data nodes |
| `describe.py` | Adds a listing description to every programme (`--dry`, `--force`, `--repolish`) |
| `harvest.py` | Queries the Archive.org search + metadata APIs, picks a browser-playable MP4 derivative per item, reads exact per-file durations, writes `channels.json` |
| `sitcom.py` | Builds CH 52 from a hand-written list of public-domain series; per-series caps, episode-level dedupe |
| `channels.json` | The harvested lineups |
| `template.html` | The site — layout, schedule engine, player, guide grid |
| `build.py` | Inlines `channels.json` into the template → `index.html` |
| `index.html` | **The deliverable.** One self-contained static file |

```bash
python harvest.py        # collection-based channels (~45 min, API-throttled)
python curated.py        # curator/critic channels from ia-curation (~5 min)
python sitcom.py         # CH 52 only, merged in place (~1 min)
python build.py          # regenerate index.html
```

`curated.py` keeps the non-feature channels `harvest.py` produced (its `KEEP`
set) and replaces the rest, so the usual refresh is just `curated.py` then
`build.py`. `sitcom.py` only ever touches CH 52 — it drops that channel,
rebuilds it and merges — so it is safe to re-run alone, in any order. CH 52 is
in `curated.py`'s `KEEP` set so a refresh doesn't delete a channel it has no
way to rebuild.

### Why the harvest is slow, and how it is kept from being slower

Archive's metadata API rate-limits to roughly **one request per second no
matter how many threads you use** — 12, 24 and 40 workers all measured at
~1.0/s. So the only lever on runtime is the number of probes.

The search API is not rate-limited the same way: one request returns hundreds
of docs, and includes a `runtime` field. So the harvester pulls a large
candidate pool from search, drops anything whose advertised runtime is outside
the channel's duration band, and only then spends a probe confirming the exact
duration and locating a playable derivative.

Runtime coverage varies wildly by collection, so the filter adapts: it takes
everything it can vet for free, then tops up with blind probes where that is
all there is. Measured per channel:

| Collection | Items publishing `runtime` | Probe hit rate |
|---|---|---|
| `prelinger` | ~95% | 100% |
| `classic_cartoons` | ~70% | high |
| `classic_tv` | ~37% | mixed |
| `universal_newsreels` | ~3% | 45% (blind) |

`channels.json` is checkpointed after each channel, so a failure partway
through keeps what has already been gathered.

`index.html` has no build step, no dependencies and no backend. Drop it on any
static host, or open it directly.

## Channels

**47 channels, 3,687 programmes.** Most channels run for days before they
repeat; DOUBLE and SAVANT run for over a week.

Channels marked ● are curator shelves from ia-curation — a real point of view,
not a query. CH 52 is marked †: a hand-written list of public-domain series,
because no query can tell a free sitcom from a bootlegged one.

| CH | Name | What it is | Items | Loops |
|---|---|---|---|---|
| 02 | PRELINGER | Ephemeral & industrial film | 199 | 55h |
| 03 | SATURDAY AM | Classic theatrical cartoons | 240 | 36h |
| 06 | CHRONICLES | The Computer Chronicles | 200 | 125h |
| 07 | NEWSREEL | Universal Newsreels | 201 | 24h |
| 08 | A/V CLUB | Classroom & training films | 180 | 59h |
| 09 | THE VAULT | Television past | 150 | 111h |
| 13 | HOME MOVIES | Strangers' amateur film | 140 | 36h |
| 14 | MISSION CTRL | NASA film & mission footage | 129 | 46h |
| 15 | **DOUBLE** ● | **Endorsed twice, independently** | 153 | 274h |
| 16 | SHOCKER ● | Internet Drive-In double features | 50 | 172h |
| 17 | CHILLER ● | Hammer, giallo and the nasty years | 110 | 199h |
| 18 | SILENT ● | The complete silent shelf, 1901–1928 | 130 | 105h |
| 19 | NOIR ● | The fn01r noir shelf, 1940–1964 | 93 | 153h |
| 20 | NOIR ALLEY ● | Recordings with the intros intact | 110 | 193h |
| 21 | ARGENTINO ● | Cine Argentino, 1909–2012 | 110 | 185h |
| 22 | TRICK FILMS ● | Méliès, Chomón, cinema of attractions | 102 | 8.5h |
| 23 | CHAPLIN ● | The Keystone-to-Mutual shorts | 36 | 10h |
| 24 | KEYSTONE ● | Mabel Normand, Sennett, silent comedy | 110 | 36h |
| 25 | MOSFILM ● | Soviet popular cinema, 1956–1998 | 33 | 55h |
| 26 | GREEK ● | Greek cinema, 1948–1985 | 22 | 36h |
| 27 | KILINK ● | Turkish pop cinema: Kilink, Turkish Batman | 10 | 15h |
| 28 | ANARQUISMO ● | Spanish libertarian cinema | 8 | 10h |
| 29 | MOMMARTZ ● | Lutz Mommartz: German experimental | 42 | 11h |
| 30 | MONSTRUOS ● | Universal monsters, doblada al español | 10 | 16h |
| 31 | ARMY/NAVY ● | US Army & Navy training films | 46 | 20h |
| 32 | KATZMAN ● | Sam Katzman's bench | 33 | 52h |
| 33 | CINE NEGRO ● | Noir in Spanish, 1932–1970 | 19 | 35h |
| 34 | **SAVANT** ● | **Graded by DVD Savant, free to watch** | 170 | 306h |
| 35 | SERIALS ● | Colourized serials, monsters, B-pictures | 110 | 165h |
| 36 | SILENT HD ● | The silent canon in HD | 110 | 181h |
| 37 | EN COULEUR ● | DeOldify: European classics in colour | 90 | 146h |
| 38 | NIHON ● | Contemporary Japanese cinema | 60 | 129h |
| 39 | CALIGARI ● | Expressionism to noir, 1919–1960 | 41 | 69h |
| 40 | BOGART ● | The Bogart shelf, and friends | 35 | 57h |
| 41 | FEUILLADE ● | Les Vampires, and films named for directors | 13 | 16h |
| 42 | SIODMAK ● | Director-forward noir | 16 | 27h |
| 43 | GRAHAME ● | Gloria Grahame, second-tier noir bench | 13 | 25h |
| 44 | BAD MOVIE ● | Weirdness bad movie night | 21 | 45h |
| 45 | VERNE ● | Jules Verne, and D.O.A. in four languages | 8 | 14h |
| 46 | COLOURIZED ● | Colourized silents and early talkies | 25 | 36h |
| 47 | THE RANGE ● | B-westerns: Buck Jones, Tim McCoy | 13 | 15h |
| 48 | CHAN ● | Charlie Chan and early sound mysteries | 16 | 25h |
| 49 | THE SHADOW ● | Detectives, murder, Lamont Cranston | 12 | 17h |
| 50 | POLIZIESCO ● | Italian crime and thrillers | 9 | 16h |
| 51 | SHORT SUBJECTS ● | Stooges, Our Gang, Little Rascals | 38 | 32h |
| 52 | LAUGH TRACK † | Half-hour comedy, 1950–1964 | 111 | 55h |
| 53 | LLOYD & CO ● | Lloyd, Chaplin, Snub Pollard, 1900–1923 | 110 | 28h |

Gaps in the numbering are deliberate — a dial with holes in it is what a real
cable box looked like.

`curated.py` keeps a global set of claimed identifiers and titles, so no
programme appears on two channels. That matters here: half a dozen shelves are
noir, and without it CH 19, 20, 33, 42 and 43 would be the same twenty films.

Ad breaks pull from 150 spots in `classic_tv_commercials`. `build.py` prints
this table, including the ad share, on every build — worth glancing at after
changing a lineup, since a channel whose item durations tile badly into half
hours will show up here as an ad share well above 30%.

To add a channel, append a spec to `CHANNELS` in `harvest.py` — a search query
plus a duration band (`lo`/`hi` in seconds) that suits the format — then run
`python harvest.py 15` to harvest just that channel and merge it into the
existing `channels.json`, rather than re-harvesting everything. The duration
band matters more than the query: it is what keeps a cartoon channel from
swallowing a two-hour feature.

**Sample the top downloads of any collection before you add it.** That is what
caught the rejected ones below. Uploader titles also need watching: the film
collections are full of entries like `Laura (1944) Dir: Otto Preminger,
Starring Gene Tierney, ...`, which `clean()` trims back to `Laura`. Resist
generalising those rules too far — a filter aggressive enough to catch a bare
year will also destroy `Space 1999` and `Big News of 1941`.

## What sells the illusion

Beyond the schedule itself, these are the details doing the work:

- **You always join mid-programme.** There is no way to start anything from
  the beginning. This is the whole point.
- **Ad breaks land where they would on air** — every ~15 minutes, not stacked
  at the end, with a "WE'LL RETURN TO…" bug over the commercial.
- **Every block opens with a station ident** — SMPTE colour bars, the channel
  number, and a 1kHz line-up tone. It is a *real scheduled segment*, seven
  seconds paid for out of the break budget, not a decorative overlay: tune in
  during it and that is genuinely what is on.
- **Changing channel makes a noise.** A short filtered noise burst, and the
  ident tone, both synthesised with Web Audio — no audio files to load.
- **"UP NEXT" slides in** over the closing minute of a block.
- **The browser tab reads `CH 04 · Cosmos: War of the Planets`**, so the
  illusion survives being in a background tab.
- **`?ch=04` deep-links to a channel.** Because the schedule is global, that
  link lands someone on exactly what you are watching.
- **The guide crawls upward on its own**, the way Prevue did, pausing while
  your pointer is in it and returning to the present by itself.
- **A broken tape puts up a slate**, not a channel change. If a programme
  fails to load twice it shows PLEASE STAND BY / TECHNICAL DIFFICULTIES over
  the colour bars and holds the channel until the schedule moves on. An
  earlier version tuned you to the next channel instead, which is both
  unfaithful and disorienting.

### Two players, so a cut never goes black

There is no single `<video>` element. There are two — one on air, one warming
the next programme — and a cut swaps them.

This matters most in an ad break. A break is several short spots back to back,
and every one used to be a cold `src` + `load()`: fetch, parse the moov atom,
seek. Measured on real spots that ran **0.7–1.9 seconds of black each**, and a
two-minute break pays it three or four times over, plus again on the way back
into the feature.

Two details that are easy to get wrong, and that I did get wrong first:

- **Aim at the next *media* boundary, not the next segment.** Inside a break
  each spot is its own load, so warming toward the end of the whole break
  leaves every spot-to-spot cut cold. `tuneAt()` returns `endsAt` — when *this
  spot* finishes — and the prefetcher aims at that.
- **Don't pick the target by a flat time lookahead.** With a run of
  20-second commercials, `now + LEAD` can land two spots away and warm the
  wrong one.

Warming begins `LEAD` (25s) before the cut. The seven seconds of a station
ident is deliberately spent loading whatever follows it. If the standby is not
ready in time the code falls back to the old cold path, so the worst case is
what it used to be.

Measured after: **3 cuts in 190 seconds, 0 ms black, every incoming element at
`readyState: 4` at the instant of the cut.**

### One playback subtlety worth keeping

The drift resync — "if buffering put us behind real time, seek forward" — must
not fire while a seek is already in flight. Some programmes here are large
(CH 34 opens with a 1.94 GB file), a seek into one takes seconds, and
`currentTime` reads stale the whole time. Unguarded, it re-seeks every tick,
thrashes the connection and eventually errors the element out. It is now gated
on `!video.seeking` plus an 8-second floor.

## Controls

- **Click a row** or **↑ / ↓** — change channel
- **Type a number** (e.g. `04`) — direct dial
- **← / →** — pan the guide forward and back in time
- **Space** — pause the crawl · **M** — mute · **Click the picture** — mute
- **Volume slider** in the control cluster
- **⛶ FULL**, **F**, or **double-click the picture** — full screen ·
  **Esc** exits

### Full screen has three tiers

Fullscreen applies to the whole `.screen` box rather than the `<video>`, so the
channel bug, the station ident and the up-next strip come with it — a bare
video element would drop all of them.

The API is not always available, though, so there is a fallback chain:

1. `screen.requestFullscreen()` — the normal path
2. the video element's own fullscreen — iOS will not fullscreen a container
3. **cinema mode** — a CSS class that hides the guide and side panel and lets
   the picture fill the window. Always works, Esc or the on-screen ✕ exits.

**Verify the outcome; don't trust the call.** The embedded webview this was
developed against rejects `requestFullscreen()` with `TypeError: Permissions
check failed` when called without a gesture, and *resolves the promise without
entering fullscreen* when called with one — while `document.fullscreenEnabled`
reports `true` throughout and no `fullscreenchange` event ever fires. Hooking
the fallback to `.catch()` therefore did nothing. The code now checks
`fullscreenElement` 350 ms later and falls back on that, which covers
rejection, silent success and the old non-promise API in one path.

Note also that desktop Chrome exposes `video.webkitEnterFullscreen` even where
it is a silent no-op, so tier 2 is only attempted when no container fullscreen
method exists at all.

## Things worth knowing

- **Media is hotlinked from archive.org.** Fine for personal use; if this ever
  gets real traffic that is the Archive's bandwidth, not yours. Consider
  mirroring or asking them first before promoting it widely.
- **Public domain is a judgement call.** The collections used are overwhelmingly
  PD or Archive-cleared, but Archive.org's own metadata is the only provenance
  here and it is not a legal guarantee. Worth a pass before publishing.
- **Period content is period content.** The commercial pool is genuine 1950s–60s
  television, which means cigarette advertising. Authentic, and possibly not
  what you want depending on who this is for — `DENY` in `harvest.py` is where
  to filter.
- **Sample before you add. Several sources were rejected outright**, and a
  keyword denylist would have caught almost none of them:

  | source | why |
  |---|---|
  | Third Reich cinema shelf (1,187 items) | headed by *Europa: The Last Battle*, a neo-Nazi Holocaust-denial film |
  | Grindhouse International (204) | sexploitation — *Love Camp 7*, *Girl Camp*, *Nekromantik*. One title in 204 trips a keyword filter |
  | `vhsvault` (117k) | real suicide footage among its top downloads |
  | `videogamecommercials` (3.8k) | NSFW items on page one |
  | "Realm of the Senses" shelf (422) | unsimulated sex |
  | Maigret / French grab-bag (21) | top item is 1970s softcore |
  | `svtplay` (91), `legendado` (162) | ripped in-copyright broadcasts |

  All of these were found by reading the top titles, not by filtering. The
  denylist in `harvest.py` is a backstop for stragglers, not the defence. Note
  also that `nude` is not a substring of `nudist` — which is how *Diary of a
  Nudist* reached the MATINEE lineup before being caught by eye.
- **Some curator shelves hold films that are plainly still in copyright** —
  CH 17 has *The Silence of the Lambs*, CH 38 is Japanese cinema from
  2001–2022. They are on archive.org, which is not the same as being free to
  rebroadcast. Drop those channels from `SHELVES` in `curated.py` if that
  matters for how you use this.
- **Timezones**: slots align to :00/:30 in the viewer's local time. A viewer in
  a :45-offset zone (Nepal, Chatham Islands) sees the grid land on :15/:45.

## Possible next moves

- Station idents and a sign-off card between programmes
- Dayparting — cartoons in the morning, creature features after midnight
- A shareable `?ch=04` deep link, since the schedule is global anyway
