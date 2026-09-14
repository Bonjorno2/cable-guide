"""Inline channels.json into template.html -> index.html (one static file)."""
import sys
import json

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


def pack(items):
    """Mirror of packChannel() in the template, for reporting."""
    cap = SLOT * CONTENT

    def mk(lst, d):
        return (lst, d, max(SLOT, -(-(d + 60) // SLOT) * SLOT))

    long = [mk([it], it["dur"]) for it in items if it["dur"] + 60 > SLOT]
    pool = sorted((it for it in items if it["dur"] + 60 <= SLOT),
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


print(f"index.html  ({len(out)/1024:.0f} KB)")
print(f"{len(data['channels'])} channels, {len(data['interstitials'])} fill spots\n")
print(f"  {'':22}{'items':>6}{'blocks':>8}{'loop':>8}{'ads':>7}")
for c in data["channels"]:
    blocks = pack(c["items"])
    cycle = sum(b[2] for b in blocks)
    ad = 1 - sum(b[1] for b in blocks) / cycle
    print(f"  CH {c['num']:02d} {c['name']:<16}{len(c['items']):>6}{len(blocks):>8}"
          f"{cycle/3600:>7.1f}h{ad*100:>6.0f}%")
