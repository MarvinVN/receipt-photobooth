"""Receipt renderer: turns an event's template.yaml into a 1-bit PIL image.

Each block type maps to a function returning a full-printer-width image;
the blocks are stacked top-to-bottom. The template is read fresh by the
caller on every print, so edits take effect on the next receipt.
"""
import random
from datetime import datetime
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

try:
    import qrcode
except ImportError:
    qrcode = None

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
FONT_FILES = {
    (False, False): "DejaVuSans.ttf",
    (True,  False): "DejaVuSans-Bold.ttf",
    (False, True):  "DejaVuSans-Oblique.ttf",
    (True,  True):  "DejaVuSans-BoldOblique.ttf",
}
ASSETS = Path.home() / "photobooth" / "assets"

DEFAULT_QUIPS = [
    "You look unreasonably good today.",
    "Certified main character.",
    "Warning: dangerously photogenic.",
    "This one's going in the hall of fame.",
]


# --------------------------------------------------------------------------
# Context / variables
# --------------------------------------------------------------------------
class _SafeDict(dict):
    def __missing__(self, key):
        return ""


def pick_quip(event_dir: Path) -> str:
    f = event_dir / "quips.txt"
    quips = DEFAULT_QUIPS
    if f.exists():
        lines = [l.strip() for l in f.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
        if lines:
            quips = lines
    return random.choice(quips)


def build_context(event_dir: Path, meta: dict) -> dict:
    now = datetime.now()
    ctx = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "datetime": now.strftime("%Y-%m-%d %H:%M"),
        "event": meta.get("event", ""),
        "quip": pick_quip(event_dir),
    }
    for k, v in meta.items():                 # expose custom event.yaml fields
        ctx.setdefault(k, "" if v is None else str(v))
    return ctx


def subst(text, ctx) -> str:
    return str(text).format_map(_SafeDict(ctx))


# --------------------------------------------------------------------------
# Block renderers (each returns a width-wide 1-bit image)
# --------------------------------------------------------------------------
def _font(size, bold=False, italic=False):
    return ImageFont.truetype(str(FONT_DIR / FONT_FILES[(bool(bold), bool(italic))]), int(size))


def _wrap(text, font, max_w):
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        if font.getlength(f"{cur} {w}") <= max_w:
            cur = f"{cur} {w}"
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def render_text(content, width, size=28, bold=False, italic=False,
                align="center", pad=8, line_spacing=6):
    font = _font(size, bold, italic)
    max_w = width - 2 * pad
    lines = []
    for para in str(content).split("\n"):
        lines.extend(_wrap(para, font, max_w))
    ascent, descent = font.getmetrics()
    line_h = ascent + descent + line_spacing
    img = Image.new("1", (width, line_h * len(lines) + pad), 1)
    d = ImageDraw.Draw(img)
    y = 0
    for ln in lines:
        w = font.getlength(ln)
        x = pad if align == "left" else (width - pad - w) if align == "right" else (width - w) / 2
        d.text((x, y), ln, font=font, fill=0)
        y += line_h
    return img


def render_spacer(width, height=16):
    return Image.new("1", (width, int(height)), 1)


def render_rule(width, style="solid", thickness=3, pad=8):
    img = Image.new("1", (width, int(thickness) + 2 * pad), 1)
    d = ImageDraw.Draw(img)
    y = pad
    if style == "dashed":
        x, dash, gap = 0, 12, 8
        while x < width:
            d.rectangle([x, y, min(x + dash, width), y + thickness - 1], fill=0)
            x += dash + gap
    else:
        d.rectangle([0, y, width, y + thickness - 1], fill=0)
    return img


def _align_paste(im, width, align):
    canvas = Image.new("1", (width, im.height), 1)
    x = 0 if align == "left" else (width - im.width) if align == "right" else (width - im.width) // 2
    canvas.paste(im, (x, 0))
    return canvas


def render_image(src, event_dir, width, scale=1.0, align="center", dither=False):
    path = event_dir / src
    if not path.exists() and (ASSETS / src).exists():   # fall back to shared assets
        path = ASSETS / src
    if not path.exists():
        print(f"  (image not found: {src})")
        return None
    im = Image.open(path)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    im = im.convert("L")
    target = max(1, int(min(im.width, width) * float(scale)))
    ratio = target / im.width
    im = im.resize((target, max(1, int(im.height * ratio))), Image.LANCZOS)
    mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    return _align_paste(im.convert("1", dither=mode), width, align)


def render_qr(data, width, scale=6, align="center", border=2):
    if qrcode is None:
        return render_text("[pip install qrcode]", width, size=20)
    qr = qrcode.QRCode(border=int(border), box_size=int(scale))
    qr.add_data(data)
    qr.make(fit=True)
    im = qr.make_image(fill_color="black", back_color="white").convert("1")
    return _align_paste(im, width, align)


def _placeholder(width):
    img = Image.new("1", (width, width), 1)
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, width - 3, width - 3], outline=0, width=2)
    f = _font(40, bold=True)
    t = "PHOTO PREVIEW"
    d.text(((width - f.getlength(t)) / 2, width / 2 - 24), t, font=f, fill=0)
    return img


def render_photo(photo_rgb, width, settings):
    if photo_rgb is None:
        return _placeholder(width)
    crop = settings.get("crop", "square")
    gamma = float(settings.get("gamma", 0.7))
    contrast = float(settings.get("contrast", 1.1))
    cutoff = int(settings.get("autocontrast", 2))
    img = photo_rgb
    w, h = img.size
    if crop == "square":
        s = min(w, h)
        img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
    elif crop == "portrait":                       # 4:5
        tw, th = w, int(w * 1.25)
        if th > h:
            th, tw = h, int(h * 0.8)
        img = img.crop(((w - tw) // 2, (h - th) // 2, (w + tw) // 2, (h + th) // 2))
    ratio = width / img.width
    img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
    g = ImageOps.autocontrast(img.convert("L"), cutoff=cutoff)
    g = g.point(lambda x: int(255 * (x / 255) ** gamma))    # lift shadows
    g = ImageEnhance.Contrast(g).enhance(contrast)
    return g.convert("1", dither=Image.Dither.FLOYDSTEINBERG)


# --------------------------------------------------------------------------
# Compose
# --------------------------------------------------------------------------
def stack(blocks, width):
    blocks = [b for b in blocks if b is not None]
    total = sum(b.height for b in blocks) or 1
    canvas = Image.new("1", (width, total), 1)
    y = 0
    for b in blocks:
        canvas.paste(b, (0, y))
        y += b.height
    return canvas


def compose(event_dir, photo_rgb=None):
    """Render the active event's template to a 1-bit image.

    photo_rgb: the captured RGB photo, or None to render a preview placeholder.
    """
    event_dir = Path(event_dir)
    template = yaml.safe_load((event_dir / "template.yaml").read_text(encoding="utf-8")) or {}
    width = int(template.get("width", 576))
    meta = {}
    ev = event_dir / "event.yaml"
    if ev.exists():
        meta = yaml.safe_load(ev.read_text(encoding="utf-8")) or {}
    ctx = build_context(event_dir, meta)
    photo_settings = template.get("photo", {})

    out = []
    for blk in template.get("blocks", []):
        t = blk.get("type")
        if t == "spacer":
            out.append(render_spacer(width, blk.get("height", 16)))
        elif t == "text":
            out.append(render_text(subst(blk.get("content", ""), ctx), width,
                                    size=blk.get("size", 28), bold=blk.get("bold", False),
                                    italic=blk.get("italic", False), align=blk.get("align", "center")))
        elif t == "image":
            out.append(render_image(blk.get("src", ""), event_dir, width,
                                    scale=blk.get("scale", 1.0), align=blk.get("align", "center"),
                                    dither=blk.get("dither", False)))
        elif t == "photo":
            out.append(render_photo(photo_rgb, width, photo_settings))
        elif t == "qr":
            out.append(render_qr(subst(blk.get("data", ""), ctx), width,
                                 scale=blk.get("scale", 6), align=blk.get("align", "center")))
        elif t == "rule":
            out.append(render_rule(width, style=blk.get("style", "solid"),
                                   thickness=blk.get("thickness", 3)))
        else:
            print(f"  (unknown block type: {t})")
    return stack(out, width)
