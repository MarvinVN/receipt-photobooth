"""Standalone button check. Run on the Pi:  python3 button_test.py
Press the arcade button; you should see PRESSED / released printed.
Ctrl+C to quit. This proves the wiring before we build the booth loop."""
from gpiozero import Button
from signal import pause

BUTTON_PIN = 21      # physical pin 40 (paired with GND on pin 39)

button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
button.when_pressed  = lambda: print("PRESSED")
button.when_released = lambda: print("released")

print(f"Listening on GPIO{BUTTON_PIN}. Press the button (Ctrl+C to quit).")
pause()
