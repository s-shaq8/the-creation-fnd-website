"""Rebrand the public site from Launchpad to The Creation Foundation.

Run from the repo root on the Launchpad copy (after tools/theme_natural.py):

    python3 tools/tcf_lockup.py
    python3 tools/tcf_rebrand.py

The Creation Foundation is only the public name. The legal entity is still
LaunchPad Entrepreneurial Society (BC society S0083354), so:
  * the footer copyright names the society and says it operates as
    The Creation Foundation;
  * the legal page keeps LaunchPad Entrepreneurial Society as the party to
    every term, and the About section states the operating name.
Everywhere else "Launchpad" becomes "The Creation Foundation". Every edit goes
through rsc.Page so the server markup and the React payload stay in step.
"""
import html
import re
import sys

sys.path.insert(0, 'tools')
from rsc import Page  # noqa: E402

NAME = 'The Creation Foundation'
LEGAL = 'LaunchPad Entrepreneurial Society'
PAGES = {n: Page(n + '.html') for n in ['index', 'who', 'where', 'stan', 'legal']}


def raw(old, new, pages=None, where='both', min_hits=1):
    """Literal replacement in markup and/or payload of the given pages."""
    hits = 0
    for n in pages or PAGES:
        pg = PAGES[n]
        m, p = pg.count(old)
        if where in ('both', 'markup'):
            hits += m
            pg.sub_markup(lambda s: s.replace(old, new))
        if where in ('both', 'payload'):
            hits += p
            pg.sub_payload(lambda s: s.replace(old, new))
    if hits < min_hits:
        raise SystemExit(f'NOT FOUND: {old!r}')


# ---- shared chrome: logo, footer, contact subject ----------------------------
raw('/brand/launchpad-lockup.png', '/brand/creation-lockup.png')
raw('mailto:launchpad@stanwith.me?subject=Launchpad', 'mailto:launchpad@stanwith.me?subject=The%20Creation%20Foundation')
# copyright line keeps the legal name
raw('<!-- --> Launchpad Entrepreneurial Society</span>',
    f'<!-- --> {LEGAL}, operating as {NAME}</span>', where='markup')
raw('" Launchpad Entrepreneurial Society"', f'" {LEGAL}, operating as {NAME}"', where='payload')
# footer wordmark
raw('tracking-[-0.05em]">Launchpad</p>', f'tracking-[-0.05em]">{NAME}</p>', where='markup')
raw('"className":"text-[15px] font-medium tracking-[-0.05em]","children":"Launchpad"',
    '"className":"text-[15px] font-medium tracking-[-0.05em]","children":"%s"' % NAME, where='payload')
# page titles
raw(' | Launchpad', ' | ' + NAME)

# ---- home hero: heading and the scroll-filled intro ---------------------------
raw('<span class="font-medium">Launchpad</span></h1>', f'<span class="font-medium">{NAME}</span></h1>',
    ['index'], 'markup')
raw('"className":"font-medium","children":"Launchpad"', '"className":"font-medium","children":"%s"' % NAME,
    ['index'], 'payload')


def typefill(page, n_old, lines):
    """Rebuild a .typefill block (one span per letter). lines = [[(word, bold)]]."""
    pg = PAGES[page]
    idx, m_lines, p_lines = 0, [], []
    for li, words in enumerate(lines):
        m_words, p_words = [], []
        for wi, (w, bold) in enumerate(words):
            cls = 'inline-block font-semibold' if bold else 'inline-block'
            chars_m, chars_p = [], []
            for ci, ch in enumerate(w):
                chars_m.append(f'<span style="--i:{idx}">{html.escape(ch)}</span>')
                chars_p.append(['$', 'span', str(ci), {'style': {'--i': idx}, 'children': ch}])
                idx += 1
            idx += 1  # the space / line break after each word
            m_words.append(f'<span class="{cls}">{"".join(chars_m)}</span>')
            last = wi == len(words) - 1
            p_words.append(['$', '$1', str(wi), {'children': [['$', 'span', None, {'className': cls, 'children': chars_p}], None if last else ' ']}])
        style_m = 'display:block' if li == 0 else 'display:block;margin-top:1.2em'
        m_lines.append(f'<span class="typefill__line" style="{style_m}">{" ".join(m_words)}</span>')
        p_lines.append(['$', 'span', str(li), {'className': 'typefill__line',
                                                'style': {'display': 'block', 'marginTop': '$undefined' if li == 0 else '1.2em'},
                                                'children': p_words}])
    new_markup = f'<span class="typefill" style="--n:{idx}">{"".join(m_lines)}</span>'
    start = f'<span class="typefill" style="--n:{n_old}">'
    for i in pg.markup_idx:
        s = pg.parts[i]
        a = s.find(start)
        if a < 0:
            continue
        depth = 0
        for mm in re.finditer(r'<(/?)span\b[^>]*>', s[a:]):
            depth += -1 if mm.group(1) else 1
            if depth == 0:
                pg.parts[i] = s[:a] + new_markup + s[a + mm.end():]
                break
        break
    else:
        raise SystemExit(f'{page}: typefill {n_old} not in markup')
    # payload: swap the element's props in place
    import json
    anchor = '{"className":"typefill","style":{"--n":%d}' % n_old
    for i in pg.payload_idx:
        s = pg.parts[i][1]
        k = s.find(anchor)
        if k < 0:
            continue
        end = _obj_end(s, k)
        props = json.loads(s[k:end])
        props['style']['--n'] = idx
        props['children'] = p_lines
        pg.parts[i][1] = s[:k] + json.dumps(props, ensure_ascii=False, separators=(',', ':')) + s[end:]
        return
    raise SystemExit(f'{page}: typefill {n_old} not in payload')


def _obj_end(s, i):
    depth, instr, esc = 0, False, False
    for j in range(i, len(s)):
        c = s[j]
        if instr:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': instr = False
        elif c == '"': instr = True
        elif c in '[{': depth += 1
        elif c in ']}':
            depth -= 1
            if depth == 0:
                return j + 1
    raise ValueError('unbalanced')


def words(text, bold=()):
    return [(w, w.strip('.,:') in bold or w in bold) for w in text.split(' ')]


typefill('index', 275, [
    words(f'{NAME} is a youth-run nonprofit redefining what high school competitions can be: '
          'world-class case competitions, hackathons and programs, completely free.',
          bold={'youth-run', 'nonprofit', 'completely', 'free'}),
    words('We’re building the next generation of founders and leaders, right here in Vancouver.',
          bold={'right', 'here', 'in', 'Vancouver'}),
    words('Join us.'),
])

# ---- who we are: "We are Launchpad." -> one span per word keeps the stagger --
ACC = 'text-[#2d6a4f]'
raw(f'<span class="{ACC}">Launchpad.</span>',
    ' '.join(f'<span class="{ACC}">{w}</span>' for w in ['The', 'Creation', 'Foundation.']), ['stan'], 'markup')
raw('["$","span",null,{"className":"%s","children":"Launchpad."}]' % ACC,
    '," ",'.join('["$","span",null,{"className":"%s","children":"%s"}]' % (ACC, w)
                 for w in ['The', 'Creation', 'Foundation.']), ['stan'], 'payload')

# ---- legal page: keep the society as the party, state the operating name -------
raw('uppercase tracking-wider text-[#7f8c86]">LaunchPad Entrepreneurial Society</p>',
    f'uppercase tracking-wider text-[#7f8c86]">{LEGAL}, operating as {NAME}</p>', ['legal'], 'markup')
raw('>LaunchPad Entrepreneurial Society</p>', f'>{LEGAL}, operating as {NAME}</p>', ['legal'], 'markup')  # contact
raw('"children":"LaunchPad Entrepreneurial Society"}', '"children":"%s, operating as %s"}' % (LEGAL, NAME),
    ['legal'], 'payload')
raw('incorporation number S0083354.',
    f'incorporation number S0083354. The society operates publicly under the name {NAME}; '
    f'references in this document to {LEGAL} include {NAME}.', ['legal'])
raw('Use of the Summit ’26 and LaunchPad Entrepreneurial Society website',
    f'Use of the Summit ’26 and {NAME} websites', ['legal'])

# ---- everything else: the full name, then "Launchpad" in running text ----------
raw('Launchpad Entrepreneurial Society', NAME)
for old, new in [
    ('Every Launchpad competition', 'Every Creation Foundation competition'),
    ('Launchpad clubs', 'Creation Foundation clubs'),
    ('a Launchpad club', 'a Creation Foundation club'),
    ('Launchpad', NAME),
]:
    raw(old, new, [n for n in PAGES if n != 'legal'], min_hits=0)
# the legal payload still carries unrendered rows from the mirror's filming terms
raw('Launchpad', NAME, ['legal'], 'payload', min_hits=0)

# ---- check: only URLs, emails, handles and the legal name may mention Launchpad
ALLOWED = re.compile(r'LaunchPad Entrepreneurial Society|launchpad@stanwith\.me|launchpadsociety|'
                     r'launchpad-entrepeunrial-society|launchpad\.stan\.store|about-launchpad-')
for n, pg in PAGES.items():
    for i in pg.markup_idx + pg.payload_idx:
        s = pg.parts[i] if isinstance(pg.parts[i], str) else pg.parts[i][1]
        left = [m.group(0) for m in re.finditer(r'.{0,40}launch ?pad.{0,40}', ALLOWED.sub('', s), re.I)]
        if left:
            raise SystemExit(f'{n}: leftover {left[:3]}')
for pg in PAGES.values():
    pg.save()
print('rebranded to', NAME)

# ---- client components carry some of the same copy; keep them in step ----------
JS_EDITS = [
    ('3-9ce_-rrsrer.js', 'get the most out of Launchpad ask', f'get the most out of {NAME} ask'),
    ('2k6axtzk1phra.js', '"aria-label":"Launchpad, by Stan, home"', f'"aria-label":"{NAME}, home"'),
    ('2k6axtzk1phra.js', 'src:"/brand/launchpad-lockup.png",alt:"Launchpad Entrepreneurial Society",width:4707,height:448',
     f'src:"/brand/creation-lockup.png",alt:"{NAME}",width:1367,height:150'),
]
for f in ['0ws4pbzy5k7b2.js', '278i-8izzp032.js', '004l7_k0_qf31.js']:
    JS_EDITS.append((f, '"SITE",0,{name:"Launchpad",', '"SITE",0,{name:"%s",' % NAME))
for f, old, new in JS_EDITS:
    path = '_next/static/les/chunks/' + f
    s = open(path, encoding='utf-8').read()
    assert s.count(old) == 1, (f, old)
    open(path, 'w', encoding='utf-8').write(s.replace(old, new))
print('client chunks updated')
