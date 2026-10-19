# FÌLÀ by Deji: download the exact artwork from the linked Figma file.
# Run from Windows PowerShell in this project folder: .\download-assets.ps1
# Figma asset links are short-lived. These were retrieved on 19 October 2026.
$ErrorActionPreference = 'Stop'
$assets = Join-Path $PSScriptRoot 'assets'
New-Item -Path $assets -ItemType Directory -Force | Out-Null

$images = 'https://www.figma.com/api/mcp/asset/ded820d0-e0b5-477b-b042-9a8b3cc29ca8'
$icons = 'https://www.figma.com/api/mcp/asset/afc60cbb-3b7f-4d15-b136-3d82e5d26bdc'
$files = [ordered]@{
  'hero.png'        = "$images/43739.png"
  'ceremonial.png'  = "$images/9659d.png"
  'classic.png'     = "$images/f5c54.png"
  'premium.png'     = "$images/1111a.png"
  'facebook.svg'    = "$icons/97566.svg"
  'instagram.svg'   = "$icons/65215.svg"
  'twitter.svg'     = "$icons/e6cb4.svg"
}
foreach ($entry in $files.GetEnumerator()) {
  $dest = Join-Path $assets $entry.Key
  Write-Host "Downloading $($entry.Key)..."
  Invoke-WebRequest -Uri $entry.Value -OutFile $dest
  if ((Get-Item $dest).Length -lt 80) { throw "Downloaded asset appears empty: $($entry.Key)" }
}
Write-Host 'All original Figma page assets are ready.' -ForegroundColor Green