from datetime import datetime
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from escpos.printer import File
from picamera2 import Picamera2

PRINTER_DEVICE = "/dev/usb/lp0"
PRINTER_WIDTH  = 576                       # 80mm @ 203 DPI
FONT_PATH      = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
ASSETS         = Path.home() / "photobooth" / "assets"

def capture_photo() -> Image.Image:
    cam = Picamera2()
    cam.configure(cam.create_still_configuration(main={"size": (1920, 1440)}))
    cam.start()
    time.sleep(2)                          # auto-exposure settle
    arr = cam.capture_array()
    cam.stop()
    return Image.fromarray(arr).convert("RGB")

def prep_photo_for_thermal(photo: Image.Image, width: int) -> Image.Image:
    # crop to square, resize to printer width, boost contrast, dither to 1-bit
    w, h = photo.size
    side = min(w, h)
    photo = photo.crop(((w - side) // 2, (h - side) // 2,
                       (w + side) // 2, (h + side) // 2))
    photo = photo.resize((width, width), Image.LANCZOS)
    photo = ImageEnhance.Contrast(photo).enhance(1.4)
    photo = ImageEnhance.Brightness(photo).enhance(1.1)
    return photo.convert("L").convert("1", dither=Image.Dither.FLOYDSTEINBERG)

def draw_centered_text(canvas: Image.Image, y: int, text: str, size: int) -> int:
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT_PATH, size)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((canvas.width - tw) // 2, y), text, font=font, fill=0)
    return y + (bbox[3] - bbox[1]) + 10

def build_receipt(photo: Image.Image) -> Image.Image:
    logo_path = ASSETS / "logo.png"
    logo = Image.open(logo_path).convert("1") if logo_path.exists() else None

    # measure heights first so we know canvas height
    logo_h = logo.height if logo else 0
    photo_h = photo.height
    canvas_h = logo_h + 30 + 60 + photo_h + 60 + 50 + 80   # rough; padding at bottom

    canvas = Image.new("1", (PRINTER_WIDTH, canvas_h), 1)
    y = 0
    if logo:
        canvas.paste(logo, ((PRINTER_WIDTH - logo.width) // 2, y))
        y += logo_h + 20

    y = draw_centered_text(canvas, y, datetime.now().strftime("%Y-%m-%d  %H:%M"), 28)
    y += 10
    canvas.paste(photo, (0, y))
    y += photo_h + 20
    y = draw_centered_text(canvas, y, "Thanks for visiting!", 36)

    # trim trailing white space
    return canvas.crop((0, 0, PRINTER_WIDTH, y + 20))

def print_receipt(img: Image.Image):
    p = File(PRINTER_DEVICE)
    p.image(img)
    p.cut()

def main():
    print("Capturing...")
    photo = capture_photo()
    photo.save("/tmp/last_capture.jpg")    # for debugging
    print("Composing...")
    receipt = prep_photo_for_thermal(photo, PRINTER_WIDTH)
    final = build_receipt(receipt)
    final.save("/tmp/last_receipt.png")    # for debugging
    print("Printing...")
    print_receipt(final)
    print("Done.")

if __name__ == "__main__":
    main()