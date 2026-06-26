"""Photobooth button listener: press -> capture -> compose active event -> print.

Run manually to test:  python3 booth.py
Or install booth.service to autostart it on boot (see systemd/booth.service).

The camera is started once and kept warm, so a press captures instantly. A
non-blocking lock means button mashing during a print is ignored rather than
queuing a pile of receipts.
"""
import threading
import time
from signal import pause

from PIL import Image
from gpiozero import Button
from picamera2 import Picamera2
from libcamera import controls

import photobooth      # active_event_dir(), print_image()
import renderer

BUTTON_PIN = 21        # physical pin 40, paired with GND on pin 39
WARMUP_S   = 2
COOLDOWN_S = 2.0       # after a print, ignore presses this long (drops button-mashing)
COUNTDOWN_S = 3        # delay between press and capture, so the subject can pose

_busy = threading.Lock()
_last_done = 0.0

# Keep the camera running so captures are instant and exposure stays settled.
cam = Picamera2()
cam.configure(cam.create_still_configuration(main={"size": (1920, 1440)}))
cam.start()
time.sleep(WARMUP_S)
cam.set_controls({"AfMode": controls.AfModeEnum.Auto})   # autofocus on; we trigger a lock per shot


def capture() -> Image.Image:
    return Image.fromarray(cam.capture_array()).convert("RGB")


def on_press():
    # gpiozero serializes callbacks, so a mash queues several. The lock is a
    # safety net; the cooldown is what actually drops the queued burst.
    global _last_done
    if not _busy.acquire(blocking=False):
        return
    did_work = False
    try:
        if time.monotonic() - _last_done < COOLDOWN_S:
            print("cooldown - press ignored")
            return
        did_work = True
        event_dir = photobooth.active_event_dir()
        print(f"[{event_dir.name}] get ready...")
        for i in range(COUNTDOWN_S, 0, -1):
            print(i)                       # hook an LED flash / buzzer beep here later
            if i == 1:
                cam.autofocus_cycle()      # ~1s focus lock, consumes the final beat
            else:
                time.sleep(1)
        print("capturing...")
        photo = capture()
        photo.save("/tmp/last_capture.jpg")          # editor preview uses this
        receipt = renderer.compose(event_dir, photo)
        receipt.save("/tmp/last_receipt.png")
        print("printing...")
        photobooth.print_image(receipt)
        print("done.")
    except Exception as e:
        print("ERROR:", e)
    finally:
        if did_work:
            _last_done = time.monotonic()   # cooldown from completion, even on error
        _busy.release()


button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.08)
button.when_pressed = on_press

print(f"Booth ready on GPIO{BUTTON_PIN}. Press the button. (Ctrl+C to quit)")
pause()
