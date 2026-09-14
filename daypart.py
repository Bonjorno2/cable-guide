"""Build CH 01 THE NETWORK — one station programmed across the day.

Every other channel on the dial is a genre that runs the same way at four in
the afternoon as at four in the morning. A real station was not like that. It
signed on with the news, gave the morning to cartoons, put its best picture at
nine and its worst at two, and that shape is most of what makes a schedule
feel like television rather than a playlist.

This is the one channel with a clock. It is a *view* over the dial rather than
new material: the items are the ones already harvested for the genre channels,
re-dealt into a week that runs to a station's day. That means programmes
appear twice on the dial, which no other channel does — the same licence
suggest.py takes when it re-splits CH 15 into the ★ SUGGESTED lineup.

Two things make this different from packChannel():

  Blocks are prescribed, not derived. A daypart boundary has to land on a slot
  boundary or the whole idea falls apart, so each window is filled to an exact
  number of half-hours and the block list is written into channels.json for
  the template to use as-is.

  The cycle is exactly seven days. Anything else and a programme drifts
  through the clock, which is precisely what dayparting exists to stop.

The local-time anchor lives in the template — see `tzShift` in programAt.
"""
import json, random, sys

SLOT = 1800
MINBREAK = 30            # keep in step with template.html and build.py
CONTENT = 0.86
DAY = 48                 # half-hour slots in a day
DAYS = 7
NUM = 1

# (from_hour, to_hour, name, [source channel numbers]). Hours are local. The
# windows have to tile 24h exactly; main() asserts it rather than trusting me.
#
# A window showing features must be at least 4 slots wide. A feature needs 3
# or 4 half-hours, so a 2-slot window can never hold one: it falls through to
# the short-subject filler every time, and the first build had Popeye at
# eleven at night on the strength of it. Prime time is 8-10 and the late movie
# runs 10-12 for that reason, not for period accuracy — though that is also
# how it ran.
DAYPARTS = [
    (0,  6,  "AFTER MIDNIGHT", [17, 44, 35, 20]),
    (6,  8,  "SIGN-ON",        [7, 2, 14]),
    (8,  12, "MORNING",        [3, 53, 22]),
    (12, 16, "DAYTIME",        [8, 2, 13]),
    (16, 18, "AFTER SCHOOL",   [3, 51, 23]),
    (18, 19, "EVENING NEWS",   [7, 2]),
    (19, 20, "EARLY EVENING",  [52, 9]),
    (20, 22, "PRIME TIME",     [15, 34]),
    (22, 24, "LATE NIGHT",     [19, 42, 43]),
]

# When a window has an odd half-hour left that no feature fits, it is filled
# with short subjects from here. Without a guaranteed filler the exact-fill
# loop cannot terminate.
FILLER = [2, 7, 3, 14]


def slots_for(dur):
    """Half-hours a single programme needs. Mirrors packChannel()."""
    return max(1, -(-(dur + MINBREAK) // SLOT))


def main():
    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)
    data["channels"] = [c for c in data["channels"] if c["num"] != NUM]
    by = {c["num"]: c for c in data["channels"]}

    total = sum(b - a for a, b, _, _ in DAYPARTS)
    if total != 24:
        sys.exit(f"dayparts cover {total}h, not 24")

    rnd = random.Random(20250101)

    def pool(nums):
        out = []
        for n in nums:
            if n in by:
                out += by[n]["items"]
        rnd.shuffle(out)
        return out

    pools = {name: pool(nums) for _, _, name, nums in DAYPARTS}
    filler = pool(FILLER)
    used = set()

    def take(seq, want_slots, exact):
        """Next unused item needing `want_slots`, or fitting within it."""
        for i, it in enumerate(seq):
            if it["id"] in used:
                continue
            s = slots_for(it["dur"])
            if (s == want_slots) if exact else (s <= want_slots):
                used.add(it["id"])
                return seq.pop(i)
        return None

    borrowed = {}

    def one_slot_block(seq, name):
        """Bin-pack short subjects into a single half-hour, as packChannel does."""
        cap, items, tot = SLOT * CONTENT, [], 0
        for src, seq_ in (("own", seq), ("filler", filler)):
            if src == "filler" and not items:
                borrowed[name] = borrowed.get(name, 0) + 1
            i = 0
            while i < len(seq_):
                it = seq_[i]
                if it["id"] in used or slots_for(it["dur"]) != 1:
                    i += 1
                    continue
                if tot + it["dur"] > cap:
                    i += 1
                    continue
                used.add(it["id"]); tot += it["dur"]
                items.append(seq_.pop(i))
                if tot > cap * 0.75:
                    break
            if items:
                break
        return items

    out_items, out_blocks, parts = [], [], []
    part_idx = {}
    for _, _, name, _ in DAYPARTS:
        part_idx[name] = len(parts); parts.append(name)

    for day in range(DAYS):
        for a, b, name, _ in DAYPARTS:
            remaining = (b - a) * 2
            seq = pools[name]
            while remaining > 0:
                it = None
                # Prefer a programme that fills the window exactly, then any
                # that fits. A feature is only worth placing if 2+ slots are
                # left; below that it would be cut off by the daypart.
                if remaining >= 2:
                    it = take(seq, remaining, True) or take(seq, remaining, False)
                if it and slots_for(it["dur"]) > 1:
                    s = slots_for(it["dur"])
                    out_items.append(it)
                    out_blocks.append([1, s, part_idx[name]])
                    remaining -= s
                    continue
                if it:                      # a 1-slot item came back; put it back
                    seq.insert(0, it); used.discard(it["id"])
                grp = one_slot_block(seq, name)
                if not grp:
                    sys.exit(f"day {day} {name}: ran out of material "
                             f"with {remaining} slots to fill")
                out_items += grp
                out_blocks.append([len(grp), 1, part_idx[name]])
                remaining -= 1

    cycle = sum(b[1] for b in out_blocks) * SLOT
    if cycle != DAYS * 86400:
        sys.exit(f"cycle is {cycle}s, not {DAYS} whole days")

    data["channels"].append({
        "num": NUM, "name": "THE NETWORK",
        "tag": "One station, all day — cartoons at dawn, monsters at midnight",
        "daypart": True, "parts": parts,
        "items": out_items, "blocks": out_blocks,
    })
    data["channels"].sort(key=lambda c: c["num"])
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)

    print(f"CH {NUM} THE NETWORK: {len(out_items)} programmes, "
          f"{len(out_blocks)} blocks, {DAYS}-day cycle", file=sys.stderr)
    seen = {}
    for blk, in zip(out_blocks):
        seen[parts[blk[2]]] = seen.get(parts[blk[2]], 0) + blk[1]
    for name in parts:
        # Slots a daypart could not fill from its own channels. A few in a
        # short-subject window is normal; any at all in a window meant to show
        # features means the window is too narrow to hold one.
        b = borrowed.get(name, 0)
        note = f"   {b} slots borrowed from filler" if b else ""
        print(f"  {name:<16}{seen[name]//DAYS/2:>5.1f}h/day{note}", file=sys.stderr)


if __name__ == "__main__":
    main()
