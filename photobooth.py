from datetime import datetime
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps
from escpos.printer import File
from picamera2 import Picamera2

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PRINTER_DEVICE = "/dev/usb/lp0"
PRINTER_WIDTH  = 576                        # 80mm @ 203 DPI (try 512 if it doesn't fill the paper)
FONT_PATH      = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
ASSETS         = Path.home() / "photobooth" / "assets"
LOGO_FILE      = "good-company-logo.png"    # set to None to skip the logo
LOGO_SCALE     = 0.75                        # fraction of paper width the logo occupies

# Image tuning -- adjust these if the photo looks wrong on paper:
AUTOCONTRAST_CUTOFF = 2      # % of pixels clipped at each end to normalize levels
GAMMA               = 0.7    # <1 lifts shadows (more detail in darks); raise toward 1.0 for darker
CONTRAST            = 1.1    # final contrast multiplier (1.0 = none)

# Layout (pixels)
MARGIN_TOP      = 24
MARGIN_BOTTOM   = 24
GAP             = 18
FEED_BEFORE_CUT = 5          # blank lines fed so the footer clears the cutter/tear bar

# Text
HEADER_TEXT = None           # None -> current date/time
FOOTER_TEXT = "Thanks for visiting!"
HEADER_SIZE = 28
FOOTER_SIZE = 36


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------
def capture_photo() -> Image.Image:
    cam = Picamera2()
    cam.configure(cam.create_still_configuration(main={"size": (1920, 1440)}))
    cam.start()
    time.sleep(2)                          # let auto-exposure settle
    arr = cam.capture_array()
    cam.stop()
    return Image.fromarray(arr).convert("RGB")


def prep_photo(photo: Image.Image, width: int) -> Image.Image:
    """Center-crop to square, resize, normalize tones, dither to 1-bit."""
    w, h = photo.size
    side = min(w, h)
    photo = photo.crop(((w - side) // 2, (h - side) // 2,
                        (w + side) // 2, (h + side) // 2))
    photo = photo.resize((width, width), Image.LANCZOS)
    g = photo.convert("L")
    g = ImageOps.autocontrast(g, cutoff=AUTOCONTRAST_CUTOFF)
    g = g.point(lambda x: int(255 * (x / 255) ** GAMMA))     # lift shadows
    g = ImageEnhance.Contrast(g).enhance(CONTRAST)
    return g.convert("1", dither=Image.Dither.FLOYDSTEINBERG)


# ---------------------------------------------------------------------------
# Layout: render each block to its own 1-bit image, then stack vertically
# ---------------------------------------------------------------------------
def render_text(text: str, size: int, width: int) -> Image.Image:
    font = ImageFont.truetype(FONT_PATH, size)
    measure = ImageDraw.Draw(Image.new("1", (1, 1)))
    bbox = measure.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    img = Image.new("1", (width, th), 1)
    ImageDraw.Draw(img).text(((width - tw) // 2 - bbox[0], -bbox[1]),
                             text, font=font, fill=0)
    return img


def load_logo(width: int):
    if not LOGO_FILE:
        return None
    path = ASSETS / LOGO_FILE
    if not path.exists():
        print(f"  (logo not found at {path}, skipping)")
        return None
    logo = Image.open(path)
    # Flatten transparency onto white, else transparent areas become black splotches
    if logo.mode in ("RGBA", "LA") or (logo.mode == "P" and "transparency" in logo.info):
        logo = logo.convert("RGBA")
        bg = Image.new("RGBA", logo.size, (255, 255, 255, 255))
        bg.alpha_composite(logo)
        logo = bg
    logo = logo.convert("L")
    target_w = int(min(logo.width, width) * LOGO_SCALE)
    ratio = target_w / logo.width
    logo = logo.resize((target_w, int(logo.height * ratio)), Image.LANCZOS)
    return logo.convert("1", dither=Image.Dither.NONE)   # crisp threshold, no grain


def spacer(height: int, width: int) -> Image.Image:
    return Image.new("1", (width, height), 1)


def stack(blocks, width: int) -> Image.Image:
    blocks = [b for b in blocks if b is not None]
    total = sum(b.height for b in blocks)
    canvas = Image.new("1", (width, total), 1)
    y = 0
    for b in blocks:
        canvas.paste(b, ((width - b.width) // 2, y))
        y += b.height
    return canvas


def build_receipt(photo: Image.Image) -> Image.Image:
    header = HEADER_TEXT or datetime.now().strftime("%Y-%m-%d  %H:%M")
    logo = load_logo(PRINTER_WIDTH)

    blocks = [spacer(MARGIN_TOP, PRINTER_WIDTH)]
    if logo is not None:
        blocks += [logo, spacer(GAP, PRINTER_WIDTH)]
    blocks += [
        render_text(header, HEADER_SIZE, PRINTER_WIDTH),
        spacer(GAP, PRINTER_WIDTH),
        photo,
        spacer(GAP, PRINTER_WIDTH),
        render_text(FOOTER_TEXT, FOOTER_SIZE, PRINTER_WIDTH),
        spacer(MARGIN_BOTTOM, PRINTER_WIDTH),
    ]
    return stack(blocks, PRINTER_WIDTH)


# ---------------------------------------------------------------------------
# Print
# ---------------------------------------------------------------------------
def print_receipt(img: Image.Image):
    p = File(PRINTER_DEVICE)
    p.image(img)
    p.ln(FEED_BEFORE_CUT)        # feed so the footer clears the cutter/tear bar
    p.cut()


def main():
    print("Capturing...")
    photo = capture_photo()
    photo.save("/tmp/last_capture.jpg")    # raw shot, for debugging
    print("Composing...")
    final = build_receipt(prep_photo(photo, PRINTER_WIDTH))
    final.save("/tmp/last_receipt.png")    # exact bitmap sent to printer
    print("Printing...")
    print_receipt(final)
    print("Done.")


if __name__ == "__main__":
    main()
