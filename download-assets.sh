#!/usr/bin/env bash
# From the project root on macOS/Linux: bash download-assets.sh
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p assets
base='https://www.figma.com/api/mcp/asset/ded820d0-e0b5-477b-b042-9a8b3cc29ca8'
for pair in 'hero.png 43739.png' 'ceremonial.jpg 9659d.png' 'classic.jpg f5c54.png' 'premium.jpg 1111a.png'; do
  read -r name slug <<<"$pair"
  echo "Downloading original $name from Figma..."
  curl -fL --retry 2 --connect-timeout 12 --max-time 50 "$base/$slug" -o "assets/$name"
done
python3 - <<'PY'
from pathlib import Path
for name in ('hero.png','ceremonial.jpg','classic.jpg','premium.jpg'):
    data=(Path('assets')/name).read_bytes()
    if len(data)<1000 or (name=='hero.png' and not data.startswith(b'\x89PNG\r\n\x1a\n')) or (name!='hero.png' and not data.startswith(b'\xff\xd8\xff')):
        raise SystemExit(f'{name} is not a valid PNG/JPEG. Export that layer directly from the original Figma file.')
print('All four original Figma images downloaded successfully.')
PY