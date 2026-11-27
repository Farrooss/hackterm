"""Build the hackterm app icon: a green, melting code editor with a HACKTERM corner banner.

    uv run --no-project --with fonttools python packaging/linux/make_icon.py \
        hackterm.py /usr/share/fonts/TTF/JetBrainsMonoNerdFont-Bold.ttf \
        packaging/linux/io.github.Farrooss.hackterm.svg

The code lines are JetBrains Mono Bold (SIL OFL 1.1) glyphs converted to outlines, so the
icon needs no fonts to render. The banner uses hackterm's own 5x5 boot-screen font.
"""
import re, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

hk_src, font_path, out = sys.argv[1:4]
block = re.search(r'_F = """(.*?)"""', open(hk_src).read(), re.S).group(1)
PIX = {ln[0]: ln[2:].split("|") for ln in block.strip().splitlines()}

font = TTFont(font_path)
gs, cmap, upm = font.getGlyphSet(), font.getBestCmap(), font["head"].unitsPerEm

def text_path(s, x, baseline, size):
    k = size / upm
    pen = SVGPathPen(gs)
    for ch in s:
        g = cmap[ord(ch)]
        gs[g].draw(TransformPen(pen, (k, 0, 0, -k, x, baseline)))
        x += gs[g].width * k
    return pen.getCommands(), x

def pixel_word(text, cell):
    rects, x = [], 0
    for ch in text:
        for ry, row in enumerate(PIX[ch]):
            for rx, c in enumerate(row):
                if c == "#":
                    rects.append((x + rx, ry))
        x += len(PIX[ch][0]) + 1
    w = (x - 1) * cell
    return "".join(f'<rect x="{-w/2 + cx*cell:.2f}" y="{-2.5*cell + cy*cell:.2f}" width="{cell+0.05:.2f}" height="{cell+0.05:.2f}"/>'
                   for cx, cy in rects)

CODE = ["import os", "def run():", "  t = scan()", "  for p in t:", "    if p.open:",
        "      inject(p)", "  return root()", "run()"]
KW = {"import", "def", "for", "in", "if", "return"}
COL = {"kw": "#3dff97", "call": "#9dffc6", "name": "#e2fff0", "punct": "#25b864"}
SIZE, X0, Y0, DY = 5.6, 24, 32, 9

parts = {k: [] for k in COL}
cursor = None
for i, line in enumerate(CODE):
    x, base = X0, Y0 + i * DY
    for m in re.finditer(r"[A-Za-z_]+|\s+|.", line):
        tok = m.group()
        if tok.isspace():
            x += len(tok) * gs[cmap[32]].width * SIZE / upm
            continue
        kind = ("kw" if tok in KW else "call" if line[m.end():m.end() + 1] == "(" else
                "name" if tok[0].isalpha() or tok[0] == "_" else "punct")
        d, x = text_path(tok, x, base, SIZE)
        parts[kind].append(d)
    if i == len(CODE) - 1:
        cursor = (x + 1, base - SIZE * 0.72, SIZE * 0.55, SIZE * 0.85)

code_svg = "".join(f'<path fill="{COL[k]}" d="{" ".join(v)}"/>' for k, v in parts.items() if v)
cx, cy, cw, ch = cursor
screen = ("M27 20 H101 A9 9 0 0 1 110 29 V93 A9 9 0 0 1 101 102 H66 "
          "C63 102 61 103 61 106 V109 A4 4 0 0 1 53 109 V107 C53 105 51 104 49 105 V118 A5.5 5.5 0 0 1 38 118 V107 "
          "C38 105 36 105 34 106 V112 A4.5 4.5 0 0 1 25 112 V108 C21 107 18 105 18 101 V29 A9 9 0 0 1 27 20 Z")
svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- hackterm app icon: a melting code editor with a HACKTERM banner. Code glyphs are JetBrains Mono (SIL OFL 1.1) outlines;
     the banner uses hackterm's own 5x5 boot-screen font. -->
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <defs><clipPath id="scr"><rect x="18" y="20" width="92" height="82" rx="9"/></clipPath></defs>
  <rect x="10" y="18" width="108" height="98" rx="16" fill="#5f9e7a"/>
  <rect x="10" y="12" width="108" height="98" rx="16" fill="#dcf7e8"/>
  <path d="{screen}" fill="#04140a"/>
  <g clip-path="url(#scr)">
    {code_svg}
    <rect x="{cx:.2f}" y="{cy:.2f}" width="{cw:.2f}" height="{ch:.2f}" fill="#3dff97"/>
    <g transform="translate(83 47) rotate(45)">
      <rect x="-60" y="-9" width="120" height="18" fill="#3dff97"/>
      <g fill="#04140a">{pixel_word("HACKTERM", 1.35)}</g>
    </g>
  </g>
</svg>
'''
open(out, "w").write(svg)
print("wrote", out, len(svg), "bytes")
