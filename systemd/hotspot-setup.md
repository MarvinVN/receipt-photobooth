# Wifi hotspot fallback — one-time setup (run on the Pi)

The Pi joins known wifi when available; if it can't, `autohotspot.service`
brings up the `Photobooth-Setup` access point so the editor stays reachable
at http://192.168.4.1:8080.

## 1. Make sure the wifi country is set (AP mode needs it)
```bash
sudo raspi-config nonint do_wifi_country US      # change US to your country code
```

## 2. Create the hotspot connection profile (once)
Change the password (must be 8+ chars).
```bash
sudo nmcli connection add type wifi ifname wlan0 con-name Photobooth-Setup \
     autoconnect no ssid "Photobooth-Setup"
sudo nmcli connection modify Photobooth-Setup \
     802-11-wireless.mode ap 802-11-wireless.band bg \
     ipv4.method shared ipv4.addresses 192.168.4.1/24 ipv6.method ignore \
     wifi-sec.key-mgmt wpa-psk wifi-sec.psk "photobooth"
```

Quick manual test: `sudo nmcli connection up Photobooth-Setup`
→ phone should see "Photobooth-Setup"; connect, browse http://192.168.4.1:8080
→ then `sudo nmcli connection down Photobooth-Setup` to return to wifi.

## 3. Install the fallback service
```bash
chmod +x ~/photobooth/systemd/autohotspot.sh
sudo sed -i 's/\r$//' ~/photobooth/systemd/autohotspot.sh
sudo install -m 644 ~/photobooth/systemd/autohotspot.service /etc/systemd/system/
sudo sed -i 's/\r$//' /etc/systemd/system/autohotspot.service
sudo systemctl daemon-reload
sudo systemctl enable autohotspot.service
```

## 4. Test the fallback
Down your home wifi so the Pi can't connect, then run the script:
```bash
sudo nmcli connection down "YOUR_HOME_SSID"
~/photobooth/systemd/autohotspot.sh      # waits ~30s, then starts hotspot
```
Reconnect with `sudo nmcli connection up "YOUR_HOME_SSID"` or just reboot.

Logs: `journalctl -t autohotspot`
