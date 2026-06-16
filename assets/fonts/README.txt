Drop custom .ttf / .otf font files here.

Reference them from a template.yaml text block by filename (extension optional):
  - {type: text, content: "{event}", size: 44, font: "MyFont"}

The renderer resolves fonts in this order:
  1. a matching file in this folder (assets/fonts/)
  2. any font family installed on the Pi (see: fc-list : family | sort -u)
  3. bundled DejaVu Sans
