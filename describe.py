"""Add a one-line programme description to every item in channels.json.

Two sources, best first:

  1. For films the ia-curation project matched to a DVD Savant review, use
     Glenn Erickson's own prose. It is a critic writing about the film, which
     beats anything an uploader typed into a metadata box.
  2. Otherwise the archive.org `description` field, read from `<id>_meta.xml`
     on the data nodes — same trick curated.py uses, ~30/sec instead of ~1.

Descriptions are cut to roughly a TV listing's length, which is also what the
guide has room for. Run with --dry to print a sample without writing.
"""
import html, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

CURATION = os.path.join("C:" + os.sep, "Users", "myerj", "Desktop", "ia-curation")
DATA = os.path.join(CURATION, "data")
UA = {"User-Agent": "cable-guide-harvester/1.0"}
MAXLEN = 190

# Boilerplate that wraps a lot of archive.org descriptions.
STRIP_PREFIX = [
    r"^National Archives description:\s*",
    r'^The original release sheet reads:\s*["“]?',
    r"^The following concise,?\s*informative description was taken from[^:]{0,60}:\s*",
    r"^Description:\s*",
    r"^Synopsis:\s*",
    r"^Plot:\s*",
    r"^From the [A-Z][\w ]+ collection[.:]\s*",
]
# Lines that are provenance, not programme description.
JUNK = re.compile(
    r"(?i)^(uploaded by|scanned by|digitized by|courtesy of|source:|credits?:"
    r"|https?://|www\.|this (video|film|item) (was|is) )")

# Whole sentences that are housekeeping rather than programme description —
# links, "a better transfer is over here", donor acknowledgements.
DROP_SENT = re.compile(
    r"(?i)(https?://|www\.|please note|higher[- ]quality|better (copy|version|transfer)"
    r"|now available at|donated to the|digitized (by|from)|for more information"
    # uploaders narrating their own transfer rather than the programme
    r"|\bi (remember|found|have|got|ripped|recorded|uploaded)\b|\bmy (copy|collection|vhs)\b"
    r"|this one was|gotten from|ripped from|taken from (a|an|my)|recorded (off|from)"
    r"|\bold hard drive\b|\bpart of a dvd\b|\bvhs (tape|rip)\b|\benjoy!?\b)")

# Catalogue records: "KEYSTONE 1015 ft., rel. Feb. 9 1914 dir. ... cast: ..."
# Informative, but not a listing description.
CREDITS = re.compile(r"(?i)(\bcast:|\bcam\.\s|\d+\s*ft\.,|\breel,\s*rel\.|\brel\.\s*\w+\.?\s*\d+,\s*\d{4})")


def sentences(t):
    return [p for p in re.split(r"(?<=[.!?])\s+", t) if p.strip()]


def clean(t):
    if not t:
        return ""
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = t.replace(" ", " ")
    t = re.sub(r"\s+", " ", t).strip()
    # Boilerplate nests: the newsreels arrive as
    #   National Archives description: "The original release sheet reads: ...
    # so a single pass leaves the inner prefix behind a quote mark.
    for _ in range(3):
        before = t
        t = t.strip(' "“”\'')
        for p in STRIP_PREFIX:
            t = re.sub(p, "", t).strip()
        if t == before:
            break
    t = t.strip(' "“”\'')

    if CREDITS.search(t[:160]):      # a catalogue record, not a description
        return ""
    keep = [s for s in sentences(t) if not DROP_SENT.search(s)]
    t = " ".join(keep).strip()

    if JUNK.match(t) or len(t) < 25:
        return ""
    return t


def shorten(t, n=MAXLEN):
    """Cut to about a listing's length, preferring a sentence boundary."""
    if len(t) <= n:
        return t
    window = t[: n + 40]
    ends = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", window) if m.end() <= n + 40]
    if ends and ends[-1] >= n * 0.55:
        return window[: ends[-1]].strip()
    cut = t[:n].rsplit(" ", 1)[0].rstrip(" ,;:-–—")
    return cut + "…"


def meta_description(ident):
    url = f"https://archive.org/download/{ident}/{ident}_meta.xml"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=40) as r:
            root = ET.fromstring(r.read())
    except Exception:
        return ""
    parts = [e.text or "" for e in root.findall("description")]
    return clean(" ".join(parts))


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def excerpt_map():
    """identifier -> Erickson's review prose."""
    out = {}
    for fn in ("savant_on_ia.json", "double_endorsed.json"):
        try:
            rows = load(fn)
        except Exception:
            continue
        for r in rows:
            ident = (r.get("ia") or {}).get("identifier")
            ex = clean(r.get("excerpt") or "")
            if ident and ex:
                out[ident] = ex
    return out


def repolish(data):
    """Re-run the cleaning rules over descriptions already stored, no network.
    The stored text is already plain, so clean() is safe to reapply."""
    kept = dropped = changed = 0
    for c in data["channels"]:
        for it in c["items"]:
            d = it.get("desc")
            if not d:
                continue
            new = shorten(clean(d))
            if not new:
                it.pop("desc", None); it.pop("desc_src", None); dropped += 1
            else:
                if new != d:
                    changed += 1
                it["desc"] = new
                kept += 1
    print(f"repolish: {kept} kept ({changed} rewritten), {dropped} dropped",
          file=sys.stderr)


def main():
    dry = "--dry" in sys.argv
    force = "--force" in sys.argv

    with open("channels.json", encoding="utf-8") as f:
        data = json.load(f)

    if "--repolish" in sys.argv:
        repolish(data)
        with open("channels.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        return

    crit = excerpt_map()
    items = [it for c in data["channels"] for it in c["items"]]
    if not force:
        items = [it for it in items if not it.get("desc")]

    # 1) critic prose where we have it — free, no network
    from_crit = 0
    todo = []
    for it in items:
        ex = crit.get(it["id"])
        if ex:
            it["desc"] = shorten(ex)
            it["desc_src"] = "savant"
            from_crit += 1
        else:
            todo.append(it)
    print(f"{from_crit} from DVD Savant reviews", file=sys.stderr)

    # 2) archive.org descriptions for the rest
    print(f"fetching {len(todo)} descriptions from the data nodes...",
          file=sys.stderr)
    got = 0
    with ThreadPoolExecutor(max_workers=24) as ex:
        for it, d in zip(todo, ex.map(meta_description, [t["id"] for t in todo])):
            if d:
                it["desc"] = shorten(d)
                it["desc_src"] = "ia"
                got += 1
    print(f"{got} from archive.org metadata, "
          f"{len(todo)-got} had none usable", file=sys.stderr)

    if dry:
        shown = 0
        for c in data["channels"]:
            for it in c["items"]:
                if it.get("desc") and shown < 14:
                    src = it.get("desc_src", "?")
                    print(f"\n  [{src}] {it['title'][:50]}\n      {it['desc']}"
                          .encode("ascii", "replace").decode(), file=sys.stderr)
                    shown += 1
        return

    total = sum(1 for c in data["channels"] for it in c["items"] if it.get("desc"))
    allit = sum(len(c["items"]) for c in data["channels"])
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    print(f"\n{total}/{allit} programmes described "
          f"({total*100//max(allit,1)}%)", file=sys.stderr)


if __name__ == "__main__":
    main()
