#!/usr/bin/env bash
# Photobooth wifi fallback.
#
# At boot, wait briefly for NetworkManager to join a known wifi network.
# If it doesn't, bring up our own access point ("Photobooth-Setup") so the
# web editor stays reachable at http://192.168.4.1:8080 at events with no wifi.
#
# Once the hotspot is up it stays up until reboot (so an event session is not
# interrupted by re-scans). To rejoin home wifi, reboot in range of it.
set -u

HOTSPOT="Photobooth-Setup"
IFACE="wlan0"
WAIT=30                       # seconds to wait for a normal wifi connection

# True if wlan0 has an active wifi connection that is NOT our hotspot.
is_on_real_wifi() {
  nmcli -t -f TYPE,DEVICE,NAME connection show --active 2>/dev/null \
    | awk -F: -v i="$IFACE" -v h="$HOTSPOT" \
        '$1=="802-11-wireless" && $2==i && $3!=h {found=1} END{exit !found}'
}

# Bail out gracefully if the hotspot profile was never created.
if ! nmcli -t -f NAME connection show 2>/dev/null | grep -qx "$HOTSPOT"; then
  logger -t autohotspot "Hotspot profile '$HOTSPOT' not found; skipping."
  exit 0
fi

for ((t = 0; t < WAIT; t++)); do
  if is_on_real_wifi; then
    logger -t autohotspot "Joined known wifi; hotspot not needed."
    exit 0
  fi
  sleep 1
done

logger -t autohotspot "No known wifi after ${WAIT}s; starting hotspot '$HOTSPOT'."
nmcli connection up "$HOTSPOT"
