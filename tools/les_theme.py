"""Apply the Launchpad colour theme and cache-bust the mirrored assets.

Run after tools/les_content.py. It:
  1. recolours the site from Stan purple to Launchpad blue (#284be4) in the
     CSS, JS and HTML, including the colour the runtime pixel-dither uses;
  2. recolours the pre-dithered PNGs in img-dither/ and trail-dither/, whose
     four-colour palette is baked in;
  3. redraws the site icons in the new colour;
  4. moves /_next/static/mirror/ to /_next/static/les/ so browsers that cached
     the old files (they were served as immutable) fetch the new ones.
Steps 2 and 3 are idempotent, so re-running is safe.
"""
import base64
import glob
import io
import os
import re
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BLUE = '#284be4'
COLORS = {  # old (lowercase) -> new
    '#6355ff': BLUE,        # primary
    '#5200ff': '#1d3bc4',   # primary hover
    '#6d56ff': '#3556ea',   # image mono tint
    '#9d96ff': '#7f95f2',   # light accent
    '#4c3db0': '#1f37a3',   # dark accent / icon ink
    '#eef0ff': '#ebf0fe',   # light panel background
    '#dfe3ff': '#dce5fd',
    '#f4f5ff': '#f3f6ff',
    '#120f17': '#0c0f1a',   # dark overlays
    '#060010': '#01030f',
}
PNG_PALETTE = {  # baked dither palette (RGB)
    (76, 61, 176): (31, 55, 163),
    (158, 142, 255): (124, 147, 240),
}

OLD_DIR, NEW_DIR = '_next/static/mirror', '_next/static/les'


def text_files():
    root = NEW_DIR if os.path.isdir(NEW_DIR) else OLD_DIR
    return ([f for f in glob.glob('*.html')] +
            glob.glob(root + '/chunks/*.js') + glob.glob(root + '/chunks/*.css'))


# 1 + 4: colours and asset path in every text file
if os.path.isdir(OLD_DIR):
    if os.path.isdir(NEW_DIR):
        shutil.rmtree(NEW_DIR)
    shutil.move(OLD_DIR, NEW_DIR)
pat = re.compile('|'.join(re.escape(k) for k in COLORS), re.I)
for f in text_files():
    s = open(f, encoding='utf-8').read()
    o = s
    s = pat.sub(lambda m: COLORS[m.group(0).lower()] if m.group(0)[1:].islower() or m.group(0)[1:].isdigit()
                else COLORS[m.group(0).lower()].upper(), s)
    s = s.replace('/_next/static/mirror/', '/_next/static/les/').replace('static/mirror/', 'static/les/')
    # the FAQ band canvas mixes toward a hard-coded RGB purple (109, 86, 255)
    s = s.replace('O[n]=E+109*t*w,O[n+1]=E+86*t*w,O[n+2]=E+255*t*w', 'O[n]=E+40*t*w,O[n+1]=E+75*t*w,O[n+2]=E+228*t*w')
    if s != o:
        open(f, 'w', encoding='utf-8').write(s)

# 2: baked dither images
for f in glob.glob('img-dither/*.png') + glob.glob('trail-dither/*.png'):
    im = Image.open(f)
    mode = im.mode
    a = np.array(im.convert('RGBA'))
    changed = False
    for old, new in PNG_PALETTE.items():
        m = (a[..., 0] == old[0]) & (a[..., 1] == old[1]) & (a[..., 2] == old[2])
        if m.any():
            a[m, :3] = new
            changed = True
    if changed:
        out = Image.fromarray(a, 'RGBA')
        if mode == 'P':
            out = out.convert('RGB').quantize(colors=4, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        elif mode == 'RGB':
            out = out.convert('RGB')
        out.save(f, optimize=True)

# 3: icons
def font_file():
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    src = glob.glob(NEW_DIR + '/media/f99c309598d4ef8a*.woff2')[0]  # Big Shoulders, latin
    f = TTFont(src)
    f.flavor = None
    out = '/tmp/les_bigshoulders_800.ttf'
    instancer.instantiateVariableFont(f, {'wght': 800}).save(out)
    return out


FONT = font_file()


def mark(size):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, size - 1, size - 1], fill=BLUE)
    f = ImageFont.truetype(FONT, int(size * 0.66))
    bb = d.textbbox((0, 0), 'L', font=f)
    d.text(((size - (bb[2] - bb[0])) / 2 - bb[0], (size - (bb[3] - bb[1])) / 2 - bb[1]), 'L', font=f, fill='white')
    return im


mark(180).save('apple-icon.png')
mark(256).save('favicon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
buf = io.BytesIO()
mark(290).save(buf, 'PNG')
open('icon.svg', 'w').write('<svg width="290" height="290" viewBox="0 0 290 290" xmlns="http://www.w3.org/2000/svg">'
                            '<image width="290" height="290" href="data:image/png;base64,'
                            + base64.b64encode(buf.getvalue()).decode() + '"/></svg>\n')
# the initiatives page is not part of the site (vercel.json redirects /agenda home)
if os.path.exists('agenda.html'):
    os.remove('agenda.html')
print('theme applied')
