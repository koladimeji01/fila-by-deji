# Download the original FÌLÀ by Deji photograph exports provided by the Figma MCP asset service.
# From project root on Windows: .\download-assets.ps1
$ErrorActionPreference = 'Stop'
$base = 'https://www.figma.com/api/mcp/asset/ded820d0-e0b5-477b-b042-9a8b3cc29ca8'
$images = [ordered]@{
  'hero.png' = "$base/43739.png"
  'ceremonial.png' = "$base/9659d.png"
  'classic.png' = "$base/f5c54.png"
  'premium.png' = "$base/1111a.png"
}
$dir = Join-Path $PSScriptRoot 'assets'
New-Item -Force -ItemType Directory -Path $dir | Out-Null
foreach ($item in $images.GetEnumerator()) {
  Write-Host "Downloading $($item.Key) from the supplied Figma file..."
  $path = Join-Path $dir $item.Key
  Invoke-WebRequest -Uri $item.Value -OutFile $path
  $bytes = [IO.File]::ReadAllBytes($path)
  if ($bytes.Length -lt 1000 -or $bytes[0] -ne 137 -or $bytes[1] -ne 80 -or $bytes[2] -ne 78 -or $bytes[3] -ne 71) {
    Remove-Item $path -ErrorAction SilentlyContinue
    throw "The original $($item.Key) did not download as a valid PNG. The temporary Figma link may have expired; export the image layer manually from Figma."
  }
}
Write-Host 'The four original Figma images are ready.' -ForegroundColor Green