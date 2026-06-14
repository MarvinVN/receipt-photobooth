# Pushes the photobooth code + assets to the Pi.
# Usage:  .\deploy.ps1
$Pi   = "photobooth@photobooth.local"
$Dest = "/home/photobooth/photobooth"

Write-Host "Deploying to $Pi ..." -ForegroundColor Cyan
scp "$PSScriptRoot\photobooth.py" "${Pi}:${Dest}/photobooth.py"
scp -r "$PSScriptRoot\assets"     "${Pi}:${Dest}/"
Write-Host "Done. Now run on the Pi:" -ForegroundColor Green
Write-Host "  python3 ~/photobooth/photobooth.py"
