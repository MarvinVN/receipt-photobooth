"""Photobooth main: capture a photo, compose the active event's receipt, print.

Usage:
  python3 photobooth.py            capture + compose + print
  python3 photobooth.py --preview  compose to /tmp/last_receipt.png, no camera/printer
  python3 photobooth.py --no-print  capture + compose to PNG, but don't print
"""
import argparse
import time
from pathlib import Path

from PIL import Image
from escpos.printer import File

import renderer

PRINTER_DEVICE  = "/dev/usb/lp0"
FEED_BEFORE_CUT = 5                       # blank lines so the footer clears the cutter
EVENTS_DIR      = Path.home() / "photobooth" / "events"


def active_event_dir() -> Path:
    pointer = EVENTS_DIR / "active.txt"
    name = pointer.read_text(encoding="utf-8").strip() if pointer.exists() else "default"
    d = EVENTS_DIR / name
    return d if d.exists() else EVENTS_DIR / "default"


def capture_photo() -> Image.Image:
    from picamera2 import Picamera2
    cam = Picamera2()
    cam.configure(cam.create_still_configuration(main={"size": (1920, 1440)}))
    cam.start()
    time.sleep(2)                          # let auto-exposure settle
    arr = cam.capture_array()
    cam.stop()
    return Image.fromarray(arr).convert("RGB")


def print_image(img: Image.Image):
    p = File(PRINTER_DEVICE)
    p.image(img)
    p.ln(FEED_BEFORE_CUT)
    p.cut()


def run(preview=False, no_print=False):
    event_dir = active_event_dir()
    print(f"Event: {event_dir.name}")

    photo = None
    if not preview:
        print("Capturing...")
        photo = capture_photo()
        photo.save("/tmp/last_capture.jpg")

    print("Composing...")
    receipt = renderer.compose(event_dir, photo)
    receipt.save("/tmp/last_receipt.png")

    if preview or no_print:
        print("Saved -> /tmp/last_receipt.png (not printed)")
    else:
        print("Printing...")
        print_image(receipt)
        print("Done.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true",
                    help="render to PNG using a placeholder photo; no camera or printer")
    ap.add_argument("--no-print", action="store_true",
                    help="capture and compose to PNG, but don't print")
    args = ap.parse_args()
    run(preview=args.preview, no_print=args.no_print)


if __name__ == "__main__":
    main()
