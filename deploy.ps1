# Deploys photobooth CODE to the Pi over SSH in a single transfer.
# Uses the 'photobooth' host alias in ~/.ssh/config (key auth -> no password prompts).
# Usage:  .\deploy.ps1
$Pi   = "photobooth"
$Dest = "/home/photobooth/photobooth"

# Code + static assets only.
# We intentionally do NOT push events/ — those are edited live on the Pi via the
# web editor (and hold uploaded logos). Copying the desktop copy over them would
# wipe your event content. To seed events on a fresh Pi, run the one-off at the bottom.
$items = @("photobooth.py", "booth.py", "renderer.py", "webadmin.py", "templates", "assets", "systemd")
$src   = $items | ForEach-Object { Join-Path $PSScriptRoot $_ }

Write-Host "Deploying code to $Pi ..." -ForegroundColor Cyan
scp -r $src "${Pi}:${Dest}/"
Write-Host "Done." -ForegroundColor Green
Write-Host "Apply changes if running as a service:  ssh $Pi 'sudo systemctl restart webadmin'" -ForegroundColor Yellow

# One-off: seed the default event(s) onto a fresh Pi (overwrites Pi-side event content!):
#   scp -r "$PSScriptRoot\events" "photobooth:/home/photobooth/photobooth/"
