"""Inline channels.json into template.html -> index.html (one static file)."""
import sys
import json

# The suggested lineup is headed by a star on the site, and this table names it
# the same way. A Windows console is cp1252 and will not take one.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = sys.argv[1] if len(sys.argv) > 1 else "channels.json"
with open(src, encoding="utf-8") as f:
    data = json.load(f)
with open("template.html", encoding="utf-8") as f:
    tpl = f.read()

blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
out = tpl.replace("__CHANNEL_DATA__", blob)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(out)

SLOT = 1800
CONTENT = 0.86
MINBREAK = 30          # keep in step with the template; see packChannel there


def pack(items):
    """Mirror of packChannel() in the template, for reporting."""
    cap = SLOT * CONTENT

    def mk(lst, d):
        return (lst, d, max(SLOT, -(-(d + MINBREAK) // SLOT) * SLOT))

    long = [mk([it], it["dur"]) for it in items if it["dur"] + MINBREAK > SLOT]
    pool = sorted((it for it in items if it["dur"] + MINBREAK <= SLOT),
                  key=lambda it: -it["dur"])

    short = []
    while pool:
        cur, total, i = [], 0, 0
        while i < len(pool):
            if total + pool[i]["dur"] <= cap:
                total += pool[i]["dur"]
                cur.append(pool.pop(i))
            else:
                i += 1
        if not cur:
            cur.append(pool.pop(0))
            total = cur[0]["dur"]
        short.append(mk(cur, total))
    return short + long


def report(channels, heading):
    print(f"\n{heading}")
    print(f"  {'':22}{'items':>6}{'blocks':>8}{'loop':>8}{'ads':>7}")
    for c in channels:
        if c.get("blocks"):
            # Blocks were decided by daypart.py or walk.py; repacking them here
            # would report a schedule the site does not run.
            k, blocks = 0, []
            for n, slots, *_ in c["blocks"]:
                grp = c["items"][k:k + n]; k += n
                blocks.append((grp, sum(i["dur"] for i in grp), slots * SLOT))
        else:
            blocks = pack(c["items"])
        cycle = sum(b[2] for b in blocks)
        ad = 1 - sum(b[1] for b in blocks) / cycle
        print(f"  CH {c['num']:02d} {c['name']:<16}{len(c['items']):>6}"
              f"{len(blocks):>8}{cycle/3600:>7.1f}h{ad*100:>6.0f}%")


print(f"index.html  ({len(out)/1024:.0f} KB)")
print(f"{len(data['channels'])} channels, {len(data['interstitials'])} fill spots")
report(data["channels"], "the dial")
# The star button is a second lineup with its own packing, so it needs its own
# table: a channel of half-hour shorts and a channel of 90-minute features tile
# into the grid completely differently, and the ad share is where that shows.
if data.get("suggested"):
    report(data["suggested"], "★ SUGGESTED")
