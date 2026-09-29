"""Swap the single-blue Launchpad theme for a natural, film-like two-tone palette.

Run from the repo root after tools/les_theme.py (it expects the blue theme as
input; to re-run, `git checkout` the touched files first). It:
  1. remaps the UI colours: forest-black ink instead of navy, forest-green
     accent instead of blue, mint panels, green-grey muted text. Any leftover
     blue tint is hue-shifted to the same green;
  2. teaches the runtime pixel-dither "tones": each photo is drawn with a
     four-stop ramp (shadow -> deep -> light -> white) picked from its file
     name. Every tone pairs a coloured shadow with a coloured light, like
     sunlight through leaves, and one group of images shares one tone;
  3. gives the landscape canvases (hero, where-hero, footer forest) a shadow
     and light colour so they can ramp across two hues (with a light colour
     given, the visible levels are exactly shadow, colour, light);
  4. tints the who-page rows (icon ink + card) per row;
  5. recolours the pre-dithered PNGs in img-dither/ and trail-dither/ with
     the same tones, and the site icons with the accent.

Palette rules: no browns, and orange/yellow never share a tone with dark blue.
"""
import base64
import colorsys
import glob
import io
import re

import numpy as np
from PIL import Image

LES = '_next/static/les'

# --- palette ---------------------------------------------------------------
INK = '#12211b'        # forest black, replaces navy text
ACCENT = '#2d6a4f'     # forest green, replaces the blue accent (6.4:1 on white)
ACCENT_HOVER = '#22533d'

# (shadow, deep, light); the ramp always ends in white
TONES = {
    'meadow':     ('#163628', '#4a8a5c', '#f0c47c'),   # green leaves, gold light
    'fern-blush': ('#15352c', '#3f8a6a', '#f4b6b0'),   # green stems, pink petals
    'lagoon':     ('#0e3a3f', '#2f8a86', '#f3d9a4'),   # teal water, pale sand
    'teal-coral': ('#113c44', '#2c8a8e', '#f59a86'),   # teal shade, coral light
    'sky-bloom':  ('#2a4f6a', '#5f9fc6', '#f6bccb'),   # soft sky, blossom pink
}

# file-name fragment -> tone. One tone per group of images.
TONE_RULES = [
    # home: initiative pills, speakers
    ('/img/banner', 'teal-coral'), ('/img/crew', 'teal-coral'), ('/img/room', 'teal-coral'),
    ('/img/portrait', 'teal-coral'), ('/img/film', 'teal-coral'), ('/img/stanfam', 'teal-coral'),
    ('gabriel-morgan', 'sky-bloom'), ('shantanu-mehta', 'sky-bloom'), ('speaker-tba', 'sky-bloom'),
    # who it's for: photo strip + rows
    ('/trail/', 'sky-bloom'),
    ('icp-team', 'teal-coral'), ('icp-days', 'meadow'), ('icp-early', 'sky-bloom'),
    ('icp-watched', 'teal-coral'), ('icp-shipping', 'meadow'), ('icp-number', 'sky-bloom'),
    # where we are
    ('where-lounge', 'sky-bloom'), ('where-seats', 'sky-bloom'), ('talk.', 'teal-coral'), ('counter.', 'teal-coral'),
    # who we are
    ('trail-dither', 'fern-blush'), ('huddle.', 'sky-bloom'), ('doorway.', 'lagoon'),
    ('agenda-', 'teal-coral'),
]
DEFAULT_TONE = 'teal-coral'
ROW_TONES = ['teal-coral', 'meadow', 'sky-bloom']  # who-page rows, in order
ROW_PANELS = ['#fdf0ec', '#f1f6ea', '#eef4f9']     # matching card backgrounds

# landscape canvases: (src fragment, tone)
LANDSCAPES = [('camp-valley', 'sky-bloom'), ('camp-pavilion', 'lagoon'), ('woods', 'meadow')]
BAND_RGB = (77, 133, 96)  # home FAQ band, was (40, 75, 228)

COLORS = {  # blue theme -> natural theme
    '#284be4': ACCENT,
    '#1d3bc4': ACCENT_HOVER,
    '#3556ea': TONES[DEFAULT_TONE][1],
    '#7f95f2': '#f59a86',
    '#1f37a3': ACCENT_HOVER,
    '#142658': INK,
    '#808eb6': '#7f8c86',
    '#737fa8': '#6f7d77',
    '#dae0ea': '#e4ebe7',
    '#ebf0fe': '#eef4f0',
    '#dce5fd': '#dcebe3',
    '#f3f6ff': '#f6faf8',
    '#e7ebfb': '#e9f1ec',
    '#0c0f1a': '#0b1411',
    '#01030f': '#050a08',
    '#05060f': '#060b09',
    '#090e22': '#0e1a16',
    '#0d1330': '#12201b',
    '#99a4ff': '#f59a86',
    '#22edc8': '#2c8a8e',
}
KEEP = {'#3b82f6', '#0a66c2', '#004182'}  # dev slider UI, LinkedIn


def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def warm(h):
    """Hue-shift a leftover blue tint to the accent green, keeping lightness."""
    r, g, b = (x / 255 for x in hex_rgb(h))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.08 or not (0.53 <= hh <= 0.75):
        return h
    r, g, b = colorsys.hls_to_rgb(150 / 360, l, s * 0.45)
    return '#%02x%02x%02x' % tuple(round(x * 255) for x in (r, g, b))


def lab(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in hex_rgb(h))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


# --- 1: UI colours in every text file ----------------------------------------
HEX = re.compile(r'#[0-9a-fA-F]{6}(?![0-9a-zA-Z_-])|#[0-9a-fA-F]{8}(?![0-9a-zA-Z_-])')


def remap(m):
    s = m.group(0)
    base, alpha = s[:7].lower(), s[7:]
    new = COLORS.get(base) or (base if base in KEEP else warm(base))
    if new == base:
        return s
    return (new.upper() if s[1:7].isupper() and not s[1:7].isdigit() else new) + alpha


navy_lab = 'lab(16.189% 8.20136 -33.0742'
L, A, B = lab(INK)
ink_lab = 'lab(%.3f%% %.4f %.4f' % (L, A, B)

text_files = glob.glob('*.html') + glob.glob(LES + '/chunks/*.js') + glob.glob(LES + '/chunks/*.css')
for f in text_files:
    s = open(f, encoding='utf-8').read()
    o = s
    s = HEX.sub(remap, s)
    s = s.replace(navy_lab, ink_lab)
    s = s.replace('rgba(0,6,20,0.9)', 'rgba(10,20,17,0.9)')
    s = s.replace('O[n]=E+40*t*w,O[n+1]=E+75*t*w,O[n+2]=E+228*t*w',
                  'O[n]=E+%d*t*w,O[n+1]=E+%d*t*w,O[n+2]=E+%d*t*w' % BAND_RGB)
    if s != o:
        open(f, 'w', encoding='utf-8').write(s)


def patch(path, old, new, count=1):
    s = open(path, encoding='utf-8').read()
    n = s.count(old)
    assert n == count, (path, old[:60], n)
    open(path, 'w', encoding='utf-8').write(s.replace(old, new))


# --- 2: tones in the runtime dither ------------------------------------------
DITHER = LES + '/chunks/1i6vnvxz198wi.js'
tones_js = '{' + ','.join('"%s":[%s,[255,255,255]]' % (k, ','.join('[%d,%d,%d]' % hex_rgb(c) for c in v))
                          for k, v in TONES.items()) + '}'
rules_js = '[' + ','.join('[%r,%r]' % r for r in TONE_RULES).replace("'", '"') + ']'
# palette: a tone gives four explicit stops, spread over the levels
patch(DITHER, 'function n(e){let t=255,r=255,n=255,i=0,a=0,o=0;',
      'const TONES=' + tones_js + ',TONE_RULES=' + rules_js + ';'
      'function toneOf(e){let t=e.closest("[data-tone]");if(t)return t.dataset.tone;'
      'let r=e.dataset.ditherSrc||e.currentSrc||e.src||"";for(let[n,i]of TONE_RULES)if(r.includes(n))return i;'
      'return "%s"}' % DEFAULT_TONE +
      'function withTone(e,t){let r=toneOf(e);return{...t,monoColor:r,tone:TONES[r]}}'
      'function n(e){if(e.mono&&e.tone){let t=e.tone,r=Math.max(1,e.levels-1),n=new Uint8ClampedArray((r+1)*3);'
      'for(let i=0;i<=r;i++){let a=i/r*3,o=Math.min(2,Math.floor(a)),l=a-o;'
      'for(let s=0;s<3;s++)n[3*i+s]=t[o][s]+(t[o+1][s]-t[o][s])*l}return n}'
      'let t=255,r=255,n=255,i=0,a=0,o=0;')
# every place an image fetches its params goes through withTone
patch(DITHER, 'params:()=>o.current[r],phase', 'params:()=>withTone(e,o.current[r]),phase')
patch(DITHER, 'params:()=>o.current[s.scope],phase', 'params:()=>withTone(e,o.current[s.scope]),phase')
patch(DITHER, 'function x(t){let i=o.current[t.scope],', 'function x(t){let i=withTone(t.img,o.current[t.scope]),')

# --- 3: two-hue landscape canvases -------------------------------------------
LAND = LES + '/chunks/2k6axtzk1phra.js'
patch(LAND, 'J=((e,t,r)=>{let n=l(e),a=s(l(t)),o=[255,255,255],u=[10,8,34],c=[];'
            'for(let e=0;e<r;e++){let t=e/(r-1);a?c.push(e===r-1?null:t<.5?i(i(n,u,.75),n,2*t):i(n,i(n,o,.7),(t-.5)*2))',
      'J=((e,t,r,d,h)=>{let n=l(e),a=s(l(t)),o=[255,255,255],u=[10,8,34],c=[],D=d?l(d):i(n,u,.75),H=h?l(h):i(n,o,.7);'
      'for(let e=0;e<r;e++){let t=e/(r-1);a?c.push(e===r-1?null:h?t<.5?i(D,n,Math.min(1,3*t)):i(n,H,Math.min(1,3*t-1))'
      ':t<.5?i(D,n,2*t):i(n,H,(t-.5)*2))')
patch(LAND, '})(u.color,ec,u.levels)', '})(u.color,ec,u.levels,u.shadow,u.light)')
for f in glob.glob('*.html'):
    s = open(f, encoding='utf-8').read()
    o = s
    for frag, tone in LANDSCAPES:
        sh, deep, light = TONES[tone]
        add = '\\"color\\":\\"%s\\",\\"shadow\\":\\"%s\\",\\"light\\":\\"%s\\",' % (deep, sh, light)
        s = re.sub(r'(\\"src\\":\\"[^\\"]*%s[^\\"]*\\"[^{]*?\\"tune\\":\{)(?!\\"color)' % re.escape(frag),
                   lambda m: m.group(1) + add, s)
    if s != o:
        open(f, 'w', encoding='utf-8').write(s)

# --- 4: who-page rows ---------------------------------------------------------
ROWS = LES + '/chunks/3-9ce_-rrsrer.js'
inks = '[' + ','.join('"%s"' % TONES[t][1] for t in ROW_TONES) + ']'
patch(ROWS, 'ink:"%s",className:"icpt__icon"' % ACCENT_HOVER,
      'ink:%s[a%%%d],className:"icpt__icon"' % (inks, len(ROW_TONES)))
css = glob.glob(LES + '/chunks/35wfv2cy29n3b.css')[0]
open(css, 'a', encoding='utf-8').write(''.join(
    '.icpt__row:nth-child(%dn+%d) .icpt__card{background:%s}' % (len(ROW_PANELS), i + 1, c)
    for i, c in enumerate(ROW_PANELS)) + '\n')

# --- 5: baked PNGs and icons ---------------------------------------------------
OLD_STOPS = [(10, 10, 18), (31, 55, 163), (124, 147, 240)]  # white stays white


def tone_for(path):
    p = '/' + path
    return next((t for frag, t in TONE_RULES if frag in p), DEFAULT_TONE)


for f in glob.glob('img-dither/*.png') + glob.glob('trail-dither/*.png'):
    im = Image.open(f)
    mode = im.mode
    a = np.array(im.convert('RGBA'))
    stops = [hex_rgb(c) for c in TONES[tone_for(f)]]
    for old, new in zip(OLD_STOPS, stops):
        m = (a[..., 0] == old[0]) & (a[..., 1] == old[1]) & (a[..., 2] == old[2])
        a[m, :3] = new
    out = Image.fromarray(a, 'RGBA')
    if mode == 'P':
        out = out.convert('RGB').quantize(colors=4, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    elif mode == 'RGB':
        out = out.convert('RGB')
    out.save(f, optimize=True)


def recolour_icon(im):
    """Swap the blue disc for the accent, keeping anti-aliased edges."""
    a = np.array(im.convert('RGBA')).astype(np.float32)
    blue, acc = np.array(hex_rgb('#284be4'), np.float32), np.array(hex_rgb(ACCENT), np.float32)
    # each pixel is white*k + blue*(1-k); solve k from the red channel
    k = np.clip((a[..., 0] - blue[0]) / (255 - blue[0]), 0, 1)[..., None]
    a[..., :3] = 255 * k + acc * (1 - k)
    return Image.fromarray(a.round().astype(np.uint8), 'RGBA')


recolour_icon(Image.open('apple-icon.png')).save('apple-icon.png')
ico = Image.open('favicon.ico')
ico.size = max(ico.info.get('sizes', [ico.size]))
recolour_icon(ico).save('favicon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
svg = open('icon.svg').read()
b64 = re.search(r'base64,([^"]+)"', svg).group(1)
buf = io.BytesIO()
recolour_icon(Image.open(io.BytesIO(base64.b64decode(b64)))).save(buf, 'PNG')
open('icon.svg', 'w').write(svg.replace(b64, base64.b64encode(buf.getvalue()).decode()))
print('natural theme applied')
