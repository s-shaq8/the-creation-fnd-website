"""Home hero for The Creation Foundation.

Run from the repo root after tools/tcf_rebrand.py. It:
  1. recolours the hero landscape (camp-valley) from the green fern-blush tone
     to the palette's sky-bloom tone (soft sky shadow, blossom-pink light);
  2. replaces the hidden countdown/Apply stack under the title with a subtitle
     and the "Explore our initiatives" button;
  3. drops the old button row under the intro paragraph (the button now lives
     in the hero);
  4. appends the hero CSS to the shared stylesheet.
Markup and React payload are edited together through rsc.Page.
"""
import json
import sys

sys.path.insert(0, 'tools')
from rsc import Page  # noqa: E402

pg = Page('index.html')
CSS = '_next/static/les/chunks/35wfv2cy29n3b.css'
SUB = 'Where high school students start building.'
BTN_CLASS = ('inline-flex min-h-11 w-fit shrink-0 items-center justify-center rounded-[90px] border '
             'border-[#e4ebe7] px-7 py-[11px] text-sm font-medium text-black transition-colors hover:bg-[#eef4f0]')


def markup(old, new):
    n = pg.count(old)[0]
    assert n == 1, ('markup', old[:70], n)
    pg.sub_markup(lambda s: s.replace(old, new))


def payload(old, new):
    n = pg.count(old)[1]
    assert n == 1, ('payload', old[:70], n)
    pg.sub_payload(lambda s: s.replace(old, new))


# ---- 1: hero landscape tone -------------------------------------------------
shadow, deep, light = '#2a4f6a', '#5f9fc6', '#f6bccb'  # TONES['sky-bloom'] in theme_natural.py
payload('"tune":{"color":"#3f8a6a","shadow":"#15352c","light":"#f4b6b0"',
        '"tune":{"color":"%s","shadow":"%s","light":"%s"' % (deep, shadow, light))

# ---- 2: subtitle + button under the title ----------------------------------
m_start = '<div class="mt-12 flex justify-center md:mt-16" data-rv="soft" style="--d:500ms">'
m_end = 'data-rv="soft" style="--d:860ms"></p>'
for i in pg.markup_idx:
    s = pg.parts[i]
    a = s.find(m_start)
    if a < 0:
        continue
    b = s.index(m_end, a) + len(m_end)
    pg.parts[i] = (s[:a] +
                   f'<p class="tcf-hero__sub" data-rv="soft" style="--d:500ms">{SUB}</p>'
                   f'<div class="tcf-hero__cta" data-rv="soft" style="--d:740ms">'
                   f'<a href="#days" class="{BTN_CLASS}">Explore our initiatives</a></div>' +
                   s[b:])
    break
else:
    raise SystemExit('hero markup not found')

p_start = '["$","div",null,{"className":"mt-12 flex justify-center md:mt-16"'
p_end = '"style":{"--d":"860ms"},"children":null}]'
new_children = [
    ['$', 'p', None, {'className': 'tcf-hero__sub', 'data-rv': 'soft', 'style': {'--d': '500ms'}, 'children': SUB}],
    ['$', 'div', None, {'className': 'tcf-hero__cta', 'data-rv': 'soft', 'style': {'--d': '740ms'},
                        'children': ['$', 'a', None, {'href': '#days', 'className': BTN_CLASS,
                                                      'children': 'Explore our initiatives'}]}],
]
enc = ','.join(json.dumps(c, ensure_ascii=False, separators=(',', ':')) for c in new_children)
for i in pg.payload_idx:
    s = pg.parts[i][1]
    a = s.find(p_start)
    if a < 0:
        continue
    b = s.index(p_end, a) + len(p_end)
    pg.parts[i][1] = s[:a] + enc + s[b:]
    break
else:
    raise SystemExit('hero payload not found')

# ---- 3: drop the old button row under the intro ------------------------------
old_row = ('<div class="mt-4 flex flex-wrap items-center justify-center gap-2 md:mt-5" data-rv="soft" style="--d:160ms">'
           '<a href="/apply" class="inline-flex min-h-11 w-fit shrink-0 items-center justify-center rounded-[90px] '
           'bg-[#2d6a4f] px-7 py-3 text-sm font-medium text-[#ffffff] transition-colors hover:bg-[#22533d]">Apply</a>'
           f'<a href="#days" class="{BTN_CLASS}">Explore our initiatives</a></div>')
markup(old_row, '')
payload(',"$L3a"]', ']')

pg.save()

# ---- 4: CSS -------------------------------------------------------------------
open(CSS, 'a', encoding='utf-8').write(
    '/* home hero */'
    '.tcf-hero__sub{margin:1.25rem auto 0;max-width:30ch;font-size:1.125rem;line-height:1.35;'
    'letter-spacing:-0.02em;color:rgb(18 33 27/.72)}'
    '.tcf-hero__cta{margin-top:1.75rem;display:flex;justify-content:center}'
    '@media (min-width:768px){.tcf-hero__sub{margin-top:1.75rem;font-size:1.375rem}.tcf-hero__cta{margin-top:2.25rem}}'
    '/* end home hero */\n')
print('hero updated')
