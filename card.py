"""Generate how-to-watch.png — a single image with a QR code and three steps.

One picture, sendable over any chat app, readable by someone who will not
read instructions. Palette is lifted from template.html so the card looks
like it belongs to the guide.
"""
import io
import segno
from PIL import Image, ImageDraw, ImageFont

URL = "https://bonjorno2.github.io/cable-guide/"
OUT = "how-to-watch.png"

PANEL = "#0e0b45"
GOLD = "#ffd24a"
INK = "#ffffff"
DIM = "#b9b6ff"
CELL = "#2320a8"

W, H = 1080, 2000  # H is generous; the canvas is cropped to content at the end
FONTS = "C:/Windows/Fonts/"


def font(name, size):
    for cand in (name, "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(FONTS + cand, size)
        except OSError:
            continue
    return ImageFont.load_default()


F_TITLE = font("ariblk.ttf", 96)
F_SUB = font("arialbd.ttf", 25)
F_URL = font("consolab.ttf", 31)
F_STEP = font("arialbd.ttf", 37)
F_NUM = font("ariblk.ttf", 40)
F_FOOT = font("ariali.ttf", 27)
F_NOTE = font("arial.ttf", 24)


def track(d, cx, y, s, f, fill, ls=0):
    """Draw letterspaced text centred on cx. PIL has no tracking of its own."""
    widths = [f.getlength(c) for c in s]
    total = sum(widths) + ls * (len(s) - 1)
    x = cx - total / 2
    for c, w in zip(s, widths):
        d.text((x, y), c, font=f, fill=fill)
        x += w + ls
    return total


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if d.textlength(trial, font=f) <= maxw:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


img = Image.new("RGB", (W, H), PANEL)
d = ImageDraw.Draw(img)

# faint scanline texture, so the flat navy does not read as dead space
for y in range(0, H, 4):
    d.line([(0, y), (W, y)], fill="#13104e", width=1)

cx = W // 2

track(d, cx, 96, "THE GUIDE", F_TITLE, GOLD, ls=16)
track(d, cx, 224, "CONTINUOUS PROGRAMMING FROM THE INTERNET ARCHIVE",
      F_SUB, DIM, ls=3)

d.line([(cx - 190, 286), (cx + 190, 286)], fill=CELL, width=3)

# ---- QR panel -------------------------------------------------------------
# error='m' keeps this at 29 modules; 'h' would push it to 37 and make the
# code needlessly dense. border=4 bakes in the quiet zone the spec requires --
# scaling the symbol *with* its border keeps that margin proportional.
qr = segno.make(URL, error="m")
buf = io.BytesIO()
qr.save(buf, kind="png", scale=20, border=4, dark="#0e0b45", light="#ffffff")
buf.seek(0)
qimg = Image.open(buf).convert("RGB")

QR_BOX, RIM = 560, 12
qimg = qimg.resize((QR_BOX - RIM * 2, QR_BOX - RIM * 2), Image.NEAREST)

qx, qy = cx - QR_BOX // 2, 340
d.rounded_rectangle([qx, qy, qx + QR_BOX, qy + QR_BOX], radius=26, fill=INK)
img.paste(qimg, (qx + RIM, qy + RIM))

# ---- URL ------------------------------------------------------------------
uy = qy + QR_BOX + 42
d.rounded_rectangle([cx - 372, uy, cx + 372, uy + 62], radius=31, fill=CELL)
d.text((cx, uy + 31), "bonjorno2.github.io/cable-guide",
       font=F_URL, fill=INK, anchor="mm")

# ---- steps ----------------------------------------------------------------
STEPS = [
    "Point your phone camera at the square above, as if taking a photo.",
    "A link pops up on the screen. Tap it.",
    "Tap the yellow POWER ON button and watch.",
]

LH = 46  # line height
y = uy + 120
for i, step in enumerate(STEPS, 1):
    lines = wrap(d, step, F_STEP, W - 250)
    block = len(lines) * LH
    d.ellipse([84, y, 84 + 62, y + 62], fill=GOLD)
    d.text((84 + 31, y + 32), str(i), font=F_NUM, fill=PANEL, anchor="mm")
    ty = y + 31 - block / 2
    for ln in lines:
        d.text((176, ty), ln, font=F_STEP, fill=INK)
        ty += LH
    y += max(62, block) + 46

# ---- footer ---------------------------------------------------------------
y += 26
d.line([(cx - 190, y), (cx + 190, y)], fill=CELL, width=3)
y += 42
d.text((cx, y), "There is nothing to install and nothing to sign up for.",
       font=F_NOTE, fill=DIM, anchor="mm")
y += 54
d.text((cx, y), "It is always already playing. You cannot pause it.",
       font=F_FOOT, fill=GOLD, anchor="mm")
y += 38
d.text((cx, y), "That is the point.", font=F_FOOT, fill=GOLD, anchor="mm")

img = img.crop((0, 0, W, y + 62))
img.save(OUT, optimize=True)
print(f"{OUT}  {img.width}x{img.height}")
