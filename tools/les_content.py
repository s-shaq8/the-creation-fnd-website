"""Rewrite the mirrored site's copy for Launchpad Entrepreneurial Society.

Run from the repo root on the pristine mirror:

    git checkout <mirror-commit> -- index.html who.html where.html agenda.html stan.html _next
    python3 tools/les_content.py

Every replacement is exact (the whole string, bounded by quotes or tags) and is
applied to the server-rendered markup, the React payload and the JS chunks, so
hydration renders the same text the HTML shows.
"""
import glob
import html
import json
import re
import sys

sys.path.insert(0, 'tools')
from rsc import Page  # noqa: E402

# the legal page is built from the mirror's legal/terms template and served at /legal
import os
import shutil
if os.path.exists('legal/terms.html'):
    shutil.move('legal/terms.html', 'legal.html')
    shutil.rmtree('legal', ignore_errors=True)
PAGES = {name: Page(name + '.html') for name in ['index', 'who', 'where', 'agenda', 'stan', 'legal']}
JS = {f: open(f, encoding='utf-8').read() for f in glob.glob('_next/static/mirror/chunks/*.js')}
LOG = []


# ---------------------------------------------------------------- primitives
def _payloads(page):
    return [page.parts[i] for i in page.payload_idx]


def rep(old, new, pages=None, min_hits=1):
    """Exact replacement everywhere old appears as a whole string."""
    pages = pages or list(PAGES)
    hits = 0
    esc_old, esc_new = html.escape(old, quote=True), html.escape(new, quote=True)
    j_old, j_new = json.dumps(old, ensure_ascii=False), json.dumps(new, ensure_ascii=False)
    for name in pages:
        pg = PAGES[name]
        def fm(s):
            nonlocal hits
            for a, b in [('>' + esc_old + '<', '>' + esc_new + '<'), ('"' + esc_old + '"', '"' + esc_new + '"')]:
                hits += s.count(a); s = s.replace(a, b)
            return s
        def fp(s):
            nonlocal hits
            hits += s.count(j_old)
            return s.replace(j_old, j_new)
        pg.sub_markup(fm)
        pg.sub_payload(fp)
    for f, s in JS.items():
        for a, b in [(j_old, j_new), (json.dumps(old), json.dumps(new))]:
            if a in s:
                hits += s.count(a); s = s.replace(a, b)
        JS[f] = s
    LOG.append((hits, old[:60]))
    if hits < min_hits:
        raise SystemExit(f'NOT FOUND: {old!r}')


def raw(page, old, new, where='both', count=None):
    """Literal replacement in one page's markup and/or decoded payload."""
    pg = PAGES[page]
    m, p = pg.count(old)
    if count is not None and (m if where == 'markup' else p if where == 'payload' else m + p) != count:
        raise SystemExit(f'{page}: expected {count} of {old!r}, got markup={m} payload={p}')
    if where in ('both', 'markup'):
        pg.sub_markup(lambda s: s.replace(old, new))
    if where in ('both', 'payload'):
        pg.sub_payload(lambda s: s.replace(old, new))
    LOG.append((m + p, f'[{page}] {old[:50]}'))


def elem_span(s, i):
    """Return end index of the JSON array starting at s[i] == '['."""
    depth, instr, esc = 0, False, False
    for j in range(i, len(s)):
        c = s[j]
        if instr:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': instr = False
        elif c == '"': instr = True
        elif c == '[': depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                return j + 1
    raise ValueError('unbalanced')


def edit_payload_elem(page, anchor, fn):
    """Find the element whose props contain anchor, decode it, let fn edit it."""
    pg = PAGES[page]
    done = 0
    for i in pg.payload_idx:
        s = pg.parts[i][1]
        k = s.find(anchor)
        if k < 0:
            continue
        start = k if anchor.startswith('["$",') else s.rfind('["$",', 0, k)
        end = elem_span(s, start)
        el = json.loads(s[start:end])
        fn(el)
        pg.parts[i][1] = s[:start] + json.dumps(el, ensure_ascii=False, separators=(',', ':')) + s[end:]
        done += 1
    if not done:
        raise SystemExit(f'{page}: payload anchor not found {anchor!r}')


def markup_region(page, start_pat, end_pat, fn):
    pg = PAGES[page]
    done = 0
    for i in pg.markup_idx:
        s = pg.parts[i]
        a = s.find(start_pat)
        if a < 0:
            continue
        b = s.find(end_pat, a) + len(end_pat)
        pg.parts[i] = s[:a] + fn(s[a:b]) + s[b:]
        done += 1
    if not done:
        raise SystemExit(f'{page}: markup anchor not found {start_pat!r}')


def swap_words(el, pairs):
    """Replace string leaves of a decoded element, in document order."""
    queue = list(pairs)
    def walk(x):
        if isinstance(x, list):
            if len(x) == 4 and x[0] == '$' and isinstance(x[3], dict):
                walk(x[3])  # a React element: ["$", type, key, props]
                return
            for idx, v in enumerate(x):
                if isinstance(v, str) and queue and v == queue[0][0]:
                    x[idx] = queue.pop(0)[1]
                else:
                    walk(v)
        elif isinstance(x, dict):
            if isinstance(x.get('word'), str) and queue and x['word'] == queue[0][0]:
                x['word'] = queue.pop(0)[1]  # client component taking the word as a prop
            elif 'children' in x:
                c = x['children']
                if isinstance(c, str) and queue and c == queue[0][0]:
                    x['children'] = queue.pop(0)[1]
                else:
                    walk(c)
    walk(el)
    if queue:
        raise SystemExit(f'words not all replaced: {queue}')


def heading(page, h1_class_anchor, pairs):
    """Rewrite a word-split headline (one span per word) in markup and payload."""
    def fm(block):
        pos = 0
        for old, new in pairs:
            k = block.find('>' + old + '<', pos)
            if k < 0:
                raise SystemExit(f'{page} heading markup missing {old!r}')
            block = block[:k] + '>' + new + '<' + block[k + len(old) + 2:]
            pos = k + len(new) + 2
        return block
    markup_region(page, h1_class_anchor, '</h1>', fm)
    edit_payload_elem(page, h1_class_anchor, lambda el: swap_words(el, pairs))


# ------------------------------------------------ letter-by-letter paragraphs
def typefill(page, n_old, lines):
    """Rebuild a .typefill block. lines = list of lists of (word, bold)."""
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
    n = idx
    new_markup = f'<span class="typefill" style="--n:{n}">{"".join(m_lines)}</span>'

    def fm(block):
        return new_markup
    start = f'<span class="typefill" style="--n:{n_old}">'
    pg = PAGES[page]
    for i in pg.markup_idx:
        s = pg.parts[i]
        a = s.find(start)
        if a < 0:
            continue
        depth = 0
        for mm in re.finditer(r'<(/?)span\b[^>]*>', s[a:]):
            depth += -1 if mm.group(1) else 1
            if depth == 0:
                b = a + mm.end(); break
        pg.parts[i] = s[:a] + new_markup + s[b:]
        break
    else:
        raise SystemExit(f'{page}: typefill {n_old} not in markup')

    def fp(el):
        el[3]['style']['--n'] = n
        el[3]['children'] = p_lines
    edit_payload_elem(page, '{"className":"typefill","style":{"--n":%d}' % n_old, fp)


def words(text, bold=()):
    return [(w, w.strip('.,:') in bold or w in bold) for w in text.split(' ')]


# =================================================================== CONTENT
# ---- shared: titles, meta, nav, footer
rep('Launchpad | Stan', 'Launchpad Entrepreneurial Society')
rep('Stan | Launchpad', 'Launchpad Entrepreneurial Society', min_hits=0)
rep('Who applies | Launchpad', 'Who it’s for | Launchpad', ['who'])
rep('Where it is | Launchpad', 'Where we are | Launchpad', ['where'])
rep('Agenda | Launchpad', 'Initiatives | Launchpad', ['agenda'])
rep('Who applies', 'Who it’s for')
rep('Where it is', 'Where we are')
rep('Agenda', 'Initiatives')
rep(' Find Community, Inc. (dba Stan)', ' Launchpad Entrepreneurial Society')
DESC = ('Launchpad Entrepreneurial Society is a youth-run nonprofit in Vancouver running free case '
        'competitions, hackathons and programs for high school students.')
for d in ['A select group of founders at a camp just outside of New York. Stanley for X in 14 days, filmed as a show. October 4–19, 2026.',
          'A select group of founders. 16 days just outside of New York. Pitch day in front of investors. Filmed as a show.']:
    rep(d, DESC, min_hits=0)

rep('Launchpad, by Stan', 'Launchpad Entrepreneurial Society')
for page, old, new in [
    ('who', 'The founders Launchpad is built for, and the ones it is not. Only the founders with the most potential make the cut.',
     'Who Launchpad is for: every high school student who wants to build, compete and lead. No experience needed, and always free.'),
    ('where', 'Cabins just outside of New York, a select group of founders, three meals a day in one hall. Two and a half hours north of Manhattan. Where the sixteen days happen.',
     'Launchpad Entrepreneurial Society is based in Vancouver, British Columbia, running events and school clubs across the Lower Mainland.'),
    ('agenda', 'Four acts across sixteen days and fifteen nights just outside of New York. Broad strokes only; format and schedule subject to change.',
     'Our initiatives: the Summit case competition, the Tyche Cup, school clubs and volunteering, all free for high school students.'),
    ('stan', 'Launchpad is run by Stan. We build in public, ship in days rather than months, and have taken our own products from zero.',
     'We are Launchpad Entrepreneurial Society, a youth-run nonprofit in Vancouver building free competitions and programs for high school students.'),
]:
    rep(old, new, [page])

# ---- home
heading('index', 'mx-auto max-w-[15ch] text-[2.75rem] leading-[0.8]', [
    ('Launch', 'Top'), ('in', 'competitions.'), ('two', 'Zero'), ('weeks.', 'cost.'),
    ('Leave', 'Built'), ('with', 'by'), ('revenue.', 'students.')])
# drop the revenue footnote asterisk
raw('index', 'students.<sup class="relative -top-[0.6em] text-[0.45em] tracking-normal align-baseline">*</sup>', 'students.', 'markup', 1)
edit_payload_elem('index', 'mx-auto max-w-[15ch] text-[2.75rem] leading-[0.8]',
                  lambda el: [c.__setitem__(3, {'children': 'students.'}) for c in el[3]['children']
                              if isinstance(c, list) and isinstance(c[3].get('children'), list) and c[3]['children'][0] == 'students.'])
rep('*Outcomes depend on each team. Stan does not guarantee revenue, investment, or prizes.', '')
# an empty string would hydrate as a text node the HTML does not have; render nothing instead
edit_payload_elem('index', 'sm:whitespace-nowrap md:mt-6 md:text-xs', lambda el: el[3].__setitem__('children', None))
# the hero is just the name: collapse the word-split headline to one word
HERO = 'mx-auto max-w-[15ch] text-[2.75rem] leading-[0.8]'
markup_region('index', HERO, '</h1>', lambda b: b[:b.index('>') + 1] + '<span class="font-medium">Launchpad</span></h1>')
edit_payload_elem('index', HERO, lambda el: el[3].__setitem__('children', [['$', 'span', None, {'className': 'font-medium', 'children': 'Launchpad'}]]))

typefill('index', 297, [
    words('Launchpad Entrepreneurial Society is a youth-run nonprofit redefining what high school competitions can be: '
          'world-class case competitions, hackathons and programs, completely free.',
          bold={'youth-run', 'nonprofit', 'completely', 'free'}),
    words('We’re building the next generation of founders and leaders, right here in Vancouver.',
          bold={'right', 'here', 'in', 'Vancouver'}),
    words('Join us.'),
])
rep('Learn about the experience', 'Explore our initiatives')
rep('Two weeks that move you further than most move in two years.',
    'Real competitions. Real mentors. Zero cost to students.')
rep('There is a curriculum drawn from launches Stanley has actually run. Office hours every day with the people who ran them, along with founders and creators brought in for the fortnight. Teams will take part in a variety of product, distribution, go-to-market, social media, customer acquisition, and other challenges, in public, with real results and an audience watching. Any physical activities are optional, and a non-physical alternative is always available.',
    'Launchpad Entrepreneurial Society is run entirely by high school students in Vancouver. We design and host the competitions we always wanted to compete in: case competitions judged by industry professionals, hackathons built around real problems, and workshops with founders and executives who have done it themselves. Every event is built to feel like the real thing, because the problems, the mentors and the feedback are real.')
rep('The teams still standing at the end will pitch their businesses to a panel of investors on Pitch Day. Investors may choose to invest in any number of teams, or none at all. A',
    'Most top youth competitions charge registration fees that keep talented students out. Every Launchpad competition, hackathon and workshop costs')
rep('$100,000', '$0', ['index'])
raw('index', '"$$100,000"', '"$$0"', 'payload', 1)  # RSC escapes a leading $ as $$
rep(' cash prize is awarded under the Official Rules.', ' to enter, for every student, every time.')
rep('At its heart, Launchpad is a teaching environment where the goal is to learn, grow, and become a better founder. It is a once-in-a-lifetime opportunity to build alongside other founders who are equally determined to succeed, and to learn directly from two entrepreneurs who have already proven that this playbook works. Teams may include different numbers of founders and arrive at different stages of development and success. What matters is how effectively each team uses the experience to build, adapt, and move its business forward.',
    'At its heart, Launchpad is a place to learn by doing. Students take on real business problems, build real products, and present to people who run real companies. It is a chance to meet other students who are just as driven, learn from mentors who have been there, and leave with skills, confidence and a network that last well beyond high school. What matters is not where you start, but how much you grow.')
rep('And all of it is filmed. Most founders build in private and write the story afterward, once the ending is known. Here, the record is made while you are still inside it: every pivot, every breakthrough, every first dollar.',
    'And we are just getting started. Launchpad is built by students, for students, and every event we run is shaped by the people who compete in it.')

rep('How the camp actually runs:', 'Our initiatives:')
PILLS = [
    ('One camp, a select group of founders', 'Summit Case Competition',
     'Everyone lives on site just outside of New York from arrival to departure. Cameras go up, and there is nowhere else to be.',
     'Canada’s largest free high school case competition. One day, three rounds and real cases, judged by professionals from Big 4 firms, banks and venture capital.'),
    ('What you’ve done before doesn’t decide this', 'The Tyche Cup',
     'No perfect deck or warm intro required. You’ll be judged on what you can build, grow, and sell in two weeks.',
     'One of our signature competitions. Students go head to head on fast-paced challenges that reward creativity, strategy and nerve.'),
    ('Talk, ship, charge', 'Hackathons',
     'The whole method. Ten conversations before lunch, something live by dark, and a price on it long before you feel ready.',
     'Build something real in a single weekend. Teams turn ideas into working products with help from mentors, then demo them to judges.'),
    ('Pivot without penalty', 'School clubs',
     'The best founders know when to change course. Test your ideas, learn fast, and adapt when something isn’t working. Change isn’t failure. It’s part of building.',
     'Launchpad clubs bring entrepreneurship into high schools across Vancouver, with workshops, guest speakers and practice cases all year round.'),
    ('Filmed end to end', 'Volunteering',
     'The cameras will be there to capture the wins, the setbacks, the pressure, and everything in between. Come ready to build in public.',
     'Every event is run by students. Volunteer as an organizer, logistics lead or ambassador and gain real leadership experience.'),
    ('Pitch day', 'Always free',
     'Take what you’ve built, learned, and accomplished and make your case to investors. The opportunity is real. What happens next is up to you.',
     'Every competition, workshop and resource is free for high school students. No registration fees, ever.'),
]
for t_old, t_new, b_old, b_new in PILLS:
    rep(t_old, t_new, ['index'])
    rep(b_old, b_new, ['index'])

rep('We have done this ourselves.', 'Built by students, for students.')
rep('Stan’s own results. Every team’s results will differ.', 'A few numbers that define how we work.')
STATS_HOME = [  # (old n, new n, old unit, new unit, old label, new label, old note, new note)
    ('$200K', '$0', 'Stanley LinkedIn', 'Cost to students',
     'Zero to two hundred thousand in 14 days, by the team running this camp.', 'Every competition, hackathon and workshop is free to enter.'),
    ('$1.3M', '100%', 'Stanley Short Form', 'Youth-run',
     'Four months on the same playbook. One wedge, no outside curriculum.', 'From the leadership team to the volunteers, Launchpad is run by high school students.'),
    ('1388', '∞', 'Stanley for X in 14 days', 'What we are creating',
     'Ten days. Cold outreach first, product second, price last.', 'Summit, the Tyche Cup, hackathons, clubs and more, with new initiatives every year.'),
]
for n_old, n_new, l_old, l_new, note_old, note_new in STATS_HOME:
    raw('index', f'aria-label="{n_old}"><span aria-hidden="true">{n_old}</span>', f'aria-label="{n_new}"><span aria-hidden="true">{n_new}</span>', 'markup', 1)
    raw('index', f'"n":"{n_old.replace("$", "$$")}"', f'"n":"{n_new.replace("$", "$$")}"', 'payload', 1)
    rep(l_old, l_new, ['index'])
    rep(note_old, note_new, ['index'], min_hits=0)
# units under the numbers
raw('index', '"unit":"ARR","label":"Cost to students"', '"unit":"","label":"Cost to students"', 'payload', 1)
raw('index', '"unit":"ARR","label":"Youth-run"', '"unit":"","label":"Youth-run"', 'payload', 1)
raw('index', '"unit":"customers","label":"What we are creating"', '"unit":"possibilities","label":"What we are creating"', 'payload', 1)
raw('index', '<span class="text-[1.35rem] font-semibold leading-none tracking-[-0.03em] text-black md:text-[1.85rem]">ARR</span>',
    '<span class="text-[1.35rem] font-semibold leading-none tracking-[-0.03em] text-black md:text-[1.85rem]"></span>', 'markup', 2)
raw('index', '<span class="text-[1.35rem] font-semibold leading-none tracking-[-0.03em] text-black md:text-[1.85rem]">customers</span>',
    '<span class="text-[1.35rem] font-semibold leading-none tracking-[-0.03em] text-black md:text-[1.85rem]">possibilities</span>', 'markup', 1)

# ---- speakers
rep('Featured speakers/investors', 'Featured speakers')
for f_old, f_new in [('/img/sophia-amoruso.jpg', '/img/gabriel-morgan.jpg'),
                     ('/img/zach-yadegari.jpg', '/img/shantanu-mehta.jpg'),
                     ('/img/gary-vee.jpg', '/img/speaker-tba-2.jpg')]:
    for pg in PAGES.values():
        pg.sub_markup(lambda s, a=f_old, b=f_new: s.replace(a, b))
        pg.sub_payload(lambda s, a=f_old, b=f_new: s.replace(a, b))
    for f in JS:
        JS[f] = JS[f].replace(f_old, f_new)
rep('Sophia Amoruso', 'Gabriel Morgan')
rep('Sophia Amoruso on LinkedIn', 'Gabriel Morgan on LinkedIn')
rep('Sophia Amoruso on X', 'Gabriel Morgan on X')
rep('https://www.linkedin.com/in/sophiaamoruso/', 'https://www.linkedin.com/in/gabrielmorgan/')
rep('Zach Yadegari', 'Shantanu Mehta')
rep('Zach Yadegari on LinkedIn', 'Shantanu Mehta on LinkedIn')
rep('Zach Yadegari on X', 'Shantanu Mehta on X')
rep('https://www.linkedin.com/in/zachyadegari', 'https://www.linkedin.com/in/shantanusmehta/')
rep('Gary Vee', 'Industry leaders')
rep('Gary Vee on LinkedIn', 'Industry leaders on LinkedIn')
rep('Gary Vee on X', 'Industry leaders on X')


def caption(name, text):
    """Replace a speaker card's role line ("Role, Company") with text."""
    markup_region('index', '>' + name + '</p><p class="mt-2', '</p><div', lambda b: re.sub(r'(<p class="mt-2[^"]*">).*?(</p><div)$', lambda m: m.group(1) + html.escape(text) + m.group(2), b))
    def fp(el):
        cap = el[3]['children'][1][3]['children']  # figcaption: [name, role line, socials]
        cap[1][3]['children'] = text
    edit_payload_elem('index', '["$","figure","' + name + '"', fp)


caption('Gabriel Morgan', 'Chief Technology Officer, Arc’teryx')
caption('Shantanu Mehta', 'Investment Associate, Spring')
caption('Industry leaders', 'To be announced')

# ---- FAQ (1-12 rewritten; only 1-7 are shown, see les.css)
FAQ = [
    ('How do I apply?', 'What is Launchpad Entrepreneurial Society?', None),
    ('When and where is it?', 'Who can take part?',
     ('Sunday, October 4 to Monday, October 19, 2026. One camp just outside of New York.',
      'Any high school student. No experience is needed, just curiosity and the drive to learn.')),
    ('Who gets in?', 'How much does it cost?',
     ('Teams of two to four founders, all 18 or older. What matters is having an idea you believe in and being ready to go all in.',
      'Nothing. Every Launchpad competition, hackathon, workshop and club is free for students.')),
    ('Do I need a product already?', 'What is Summit?',
     ('No. Come with an idea or something already in motion. Wherever you’re starting, be ready to build, test, grow, and move fast.',
      'Summit is Canada’s largest free high school case competition: one day, three rounds, teams of five, and judges from Big 4 firms, investment banks and venture capital. Learn more at summitcompetition.com.')),
    ('How long is it?', 'What is the Tyche Cup?',
     ('16 days and 15 nights, Sunday, October 4 to Monday, October 19. Demo Day is Sunday, October 18.',
      'The Tyche Cup is one of our signature competitions, named after the Greek goddess of fortune. It is a fast-paced challenge that rewards creativity, strategy and quick thinking.')),
    ('Am I on camera the whole time?', 'Do I need business experience?',
     ('Yes. From check-in to checkout, and so is everyone else. Pitch day is filmed in front of investors.',
      'No. Many of our competitors are doing their first case or hackathon. We run workshops beforehand so everyone starts ready.')),
    ('How does it end?', 'Can I compete as a team?',
     ('You make your pitch. You show what you’ve accomplished. Then you head home October 19. What happens next is just the beginning.',
      'Yes. Most of our competitions are team-based. Team sizes and rules are shared with each event.')),
    ('When do you decide?', 'Where are events held?',
     ('Applicants are accepted on a rolling basis. Interviews and places go out while applications are still open, so applying early is better than applying on the last day.',
      'In Vancouver, British Columbia. Venue details are announced with each event.')),
    ('How many people can be on my team?', 'Can I start a Launchpad club at my school?',
     ('Teams of two to four founders, all 18 or older.',
      'Yes. Reach out and we will help you set up a chapter, with resources, workshop materials and speakers.')),
    ('Do we all need to apply separately?', 'Can I volunteer?',
     ('No. One person applies for the team. If you are selected, everyone on the team appears in the videos and in the interviews, so put down the number who will actually be there.',
      'Yes. Students help organize every event we run, and it is one of the best ways to build real leadership experience.')),
    ('Is everyone there for the full two weeks?', 'Who runs Launchpad?',
     ('All selected participants must remain available for the full two-week program. A team’s status in the competition may change throughout the experience, and not every team will remain eligible for Pitch Day or the $100,000 cash prize. Additional details will be revealed during the program.',
      'High school students. Every part of the organization, from events to partnerships, is led by youth.')),
    ('What are the prizes?', 'How can my company get involved?',
     ('The final teams will have the opportunity to pitch their businesses to a panel of investors. One, multiple, all, or none of the teams may receive an investment. All investment decisions are made solely at each investor’s discretion, and an investment is not guaranteed. A $100,000 cash prize is awarded under the Official Rules. Prizes are awarded by Stan under the Official Rules, which every accepted team receives and signs.',
      'We partner with companies and leaders who want to support the next generation of founders, through judging, mentoring, speaking or sponsorship.')),
]
for q_old, q_new, ans in FAQ:
    rep(q_old, q_new, ['index'])
    if ans:
        rep(ans[0], ans[1], ['index'])
# FAQ 1 answer is composite (text + date + year); replace the whole paragraph
FAQ1 = ('We are a youth-run nonprofit based in Vancouver, British Columbia. We run free case competitions, '
        'hackathons, school clubs and volunteer programs for high school students.')
markup_region('index', 'Click “Apply”. It is one page', '.</p>', lambda b: FAQ1 + '</p>')
def faq1(el):
    el[3]['children'] = FAQ1
edit_payload_elem('index', 'Click “Apply”. It is one page', faq1)

# ---- who
heading('who', 'max-w-[22ch] text-[2.75rem] leading-[0.9]', [
    ('Who', 'Built'), ('we', 'for'), ('want', 'every'), ('in', 'high'), ('the', 'school'), ('room.', 'student.')])
rep('Only the founders with the most potential make the cut. We are not filtering for pedigree, revenue or a warm introduction. None of that survives the first week anyway. We are filtering for people who can be unreasonable for a fortnight in front of a camera.',
    'Launchpad is for high school students who want to build, compete and lead. We are not looking for perfect grades, a polished résumé or years of experience. We are looking for students who are curious, driven, and ready to try something new.')
WHO = [
    ('A team', 'Any high school student',
     'Teams of two to four founders, all 18 or older, who have already argued about something hard and stayed in the room.',
     'Every student in high school is welcome, from any school. Come on your own or bring your friends and form a team.'),
    ('Arrive October 4 and Leave October 19', 'No experience needed',
     'On site, the whole time. No commute home at the weekend, no client projects running quietly in the background, no calendar you are still honouring.',
     'You do not need to have done a case competition or hackathon before. We run workshops so every student starts ready.'),
    ('Early, not necessarily empty', 'Completely free',
     'Most teams arrive with nothing live yet. Some arrive with early users or early revenue. Both are fine. What matters is that you are early enough to move fast and are not protecting something.',
     'No registration fees and no hidden costs. Every event we run is free for students, because talent is everywhere but opportunity is not.'),
    ('A tolerance for being watched', 'Curious and driven',
     'The cameras are not a formality. Everything you make, break, charge for and get wrong is on the record, and the wrong parts are the ones people remember.',
     'The students who get the most out of Launchpad ask questions, take on hard problems and are not afraid to be wrong in front of a room.'),
    ('Shipping over planning', 'Ready to build',
     'The founders who do well here talk to a stranger before lunch and have something live by dark. Plans are welcome, they just do not count for much by Wednesday.',
     'Ideas are a start. We look for students who turn them into strategies, prototypes and pitches, and learn by doing.'),
    ('An appetite for the number', 'Here to grow',
     'For two weeks, every goal, challenge, activity, and dollar could count toward the scoreboard. The story, the deck, the following, it all matters, but results are what move you forward.',
     'Win or lose, every competition is a chance to get better. Our judges and mentors give real feedback, so you leave sharper than you arrived.'),
]
for t_old, t_new, b_old, b_new in WHO:
    rep(t_old, t_new, ['who'])
    rep(b_old, b_new, ['who'])
typefill('who', 43, [words('If that sounds like you, join us.')])
rep('The application takes about ten minutes and we read every one. We review on a rolling basis and reply either way, so the earlier you apply the sooner you hear.',
    'Follow our initiatives to hear about upcoming competitions, hackathons and workshops. Every event is open to high school students and free to join.')
rep('See the fortnight', 'See our initiatives')

# ---- where
heading('where', 'max-w-[18ch] text-[2.75rem] leading-[0.95]', [
    ('A', 'A'), ('whole', 'whole'), ('camp', 'community'), ('just', 'right'), ('outside', 'here'), ('of', 'in'), ('New York', 'Vancouver')])
rep('Cabins in the woods, a select group of founders, and three meals a day in one hall. Two and a half hours north of Manhattan, ours alone for the sixteen-day stay. The only real difference from the camp you remember is what you leave with.',
    'High schools across the city, students from every background, and events that bring them all together. Launchpad is based in Vancouver, British Columbia, one of the most exciting places in the world to start something.')
rep('The location is doing more than it looks like it is.', 'Why Vancouver matters.')
rep('Every accelerator that runs in a city loses to the city. People go home, take the meeting, keep the contract, sleep in their own bed and arrive with half a head. The programme becomes a calendar invite.',
    'Vancouver is home to world-class companies, universities and startups, yet most high school students never get a real way in. The best competitions and programs are often expensive, far away, or open to only a few.')
rep('Put a select group of founders somewhere with one road in and the arithmetic changes. The only people to talk to at eleven at night are the other founders, and every one of them is two days ahead of you on something and two days behind on something else.',
    'Launchpad changes that. We bring founders, executives and mentors from across the city into rooms full of high school students, and we make sure cost is never the reason someone misses out.')
rep('That is what being just outside of New York is for. Not the view, though the view helps at 6am on the morning the deploy finally goes green.',
    'That is what being based in Vancouver is for. Not just the view, though the mountains help on the morning of a big pitch.')
WHERE = [
    ('Getting there', 'Our events',
     'Two and a half hours north of Manhattan. You make your own way to New York. From there, Stan covers the coaches to camp on check-in morning and back to the city at the end.',
     'Competitions, hackathons and workshops are held at venues across Vancouver, announced with each event.'),
    ('Sleeping and eating', 'Our schools',
     'Cabins on site, with sleeping arrangements determined before arrival. Depending on travel logistics, you may be asked to book a nearby hotel for the night before camp begins. All meals and snacks are provided, and nobody eats at a desk alone. We’re in it together.',
     'Launchpad clubs bring workshops, practice cases and guest speakers directly into high schools across the region.'),
    ('Building', 'Our partners',
     'One large build hall, a scatter of smaller rooms for calls, and proper fibre at every desk. A camp in setting only.',
     'Local companies, founders and leaders volunteer their time as judges, mentors and speakers.'),
    ('Phones', 'Our community',
     'Every camera in the place is one more angle on your story, and the founders who film the most of it are the ones people follow out.',
     'Students from across the Lower Mainland who compete together, learn together, and keep building together long after the event ends.'),
]
for t_old, t_new, b_old, b_new in WHERE:
    rep(t_old, t_new, ['where'])
    rep(b_old, b_new, ['where'])
WHERE_DATE = 'Built in Vancouver, for students everywhere.'
markup_region('where', '>Sunday, October 4<!-- --> to <!-- -->Monday, October 19', '</p>', lambda b: '>' + WHERE_DATE + '</p>')
edit_payload_elem('where', '"children":["Sunday, October 4"," to ","Monday, October 19","."]', lambda el: el[3].__setitem__('children', WHERE_DATE))
rep('Get yourself to New York. Stan covers the coaches from Manhattan on the morning of check-in and back at the end. Bring a laptop, two weeks of clothes, and whatever you were already going to build.',
    'Follow Launchpad to hear about our next competition, hackathon or workshop. Bring your ideas, your friends and whatever you want to build.')

# ---- agenda -> initiatives
heading('agenda', 'whitespace-nowrap text-[min(5.5rem,10cqw)] leading-[0.8]', [
    ('The', 'Our'), ('agenda,', 'initiatives,'), ('roughly.', 'explained.')])
AG_INTRO = ('Case competitions, hackathons, school clubs and volunteering, all run by high school students in Vancouver '
            'and all free to take part in.')
AG_INTRO2 = 'Every initiative is shaped by the students who take part. Flick through them to see what we run.'
markup_region('agenda', 'Sixteen days and fifteen nights', '</p>', lambda b: AG_INTRO + '<br/>' + AG_INTRO2 + '</p>')
edit_payload_elem('agenda', 'Sixteen days and fifteen nights', lambda el: el[3].__setitem__('children', [AG_INTRO, ['$', 'br', None, {}], AG_INTRO2]))
ACTS = [
    ('Explore', 'Summit',
     'Everyone arrives, settles in, and starts pushing outward inside the same week. The first days are about volume rather than polish: conversations with real people, ideas tested in public, offers written and thrown away by dark. By the end of it every team has something live and a much shorter list of things they still believe. Nothing is precious yet, and that is the entire point of putting it first.',
     'Summit is Canada’s largest free high school case competition, and British Columbia’s most rigorous. Teams of five take on a real business case across three rounds in a single day, adapt to a mid-competition disruption, and present to judges from Big 4 firms, investment banks and venture capital. Learn more at summitcompetition.com.'),
    ('Create', 'Tyche Cup',
     'Whatever got a reaction becomes the only thing anyone touches. Teams cut the rest and spend the longest uninterrupted build blocks of the fortnight turning a signal into something a stranger would pay for. The story gets rewritten to match, because most of what sounded good in week one does not survive contact with an actual customer.',
     'The Tyche Cup is one of our signature competitions, named after the Greek goddess of fortune. Students go head to head on fast-paced challenges where creativity, strategy and quick thinking decide who comes out on top. Fortune favours the bold, and so does the scoreboard.'),
    ('Sell', 'Clubs',
     'A number goes on it, well before anybody feels ready to ask for one. Outbound starts in earnest and first revenue tends to land somewhere in this stretch, rarely from the customer the team had in mind. Whatever the market breaks gets repaired in the open that same week, on camera, with everyone else watching.',
     'Launchpad clubs bring entrepreneurship into high schools across Vancouver. Chapters run workshops, practice cases, hackathon prep and guest speaker sessions, so students build skills all year and not just on competition day.'),
    ('Ship', 'Volunteer',
     'Everything narrows. Distribution past the first easy customers, then rehearsal, where the pitch gets said out loud twice and cut in half. The last full day is one room, investors in it, one shot each and the cameras still running. In the morning the vans leave and you go home with whatever you built.',
     'Every Launchpad event is run by students. Volunteers help with organizing, logistics, outreach and partnerships, gaining real leadership experience while creating opportunities for thousands of students to come.'),
]
for t_old, t_new, b_old, b_new in ACTS:
    rep(t_old, t_new, ['agenda'])
    rep(b_old, b_new, ['agenda'])
for a, b in [('Act I', 'Part I'), ('Act II', 'Part II'), ('Act III', 'Part III'), ('Act IV', 'Part IV')]:
    rep(a, b, ['agenda'])
rep('Next act', 'Next', ['agenda'])

# ---- stan -> who we are
heading('stan', 'max-w-[12ch] text-[2.75rem] leading-[0.8]', [('We', 'We'), ('are', 'are'), ('Stan.', 'Launchpad.')])
rep('We make tools for people who build in public, and we use them on ourselves. Launchpad is the version of our own week that we would have wanted at the start, run for a select group of founders at once.',
    'We are a youth-run nonprofit based in Vancouver. We run the competitions and programs we always wished existed, and we make every one of them free for high school students.')
rep('These are Stan’s own results, from building and selling our own products. They are not a forecast for any Launchpad team.',
    'A few things that define us.')
STATS = [  # (old count, new count, old prefix, new prefix, old suffix, new suffix, old label, new label)
    (200, 100, '$$', '', 'K', '%', 'ARR from Stanley LinkedIn, built and sold from nothing', 'youth-run, from the leadership team to every volunteer'),
    (1388, None, '', '∞', '', '', 'customers on Stanley for X, cold outreach first', 'possibilities, with new initiatives every year'),
    (14, 4, '', '', ' days', '', 'from idea to first paying customer, more than once', 'ways to get involved: compete, hack, start a club or volunteer'),
    (100, 0, '', '', 'M', ' fees', 'impressions the season is built to reach', 'for students, at every event we run'),
]
for c_old, c_new, pre_o, pre_n, suf_o, suf_n, l_old, l_new in STATS:
    old_p = json.dumps([pre_o, ['$', 'span', None, {'data-count': c_old, 'children': '0'}], suf_o], ensure_ascii=False, separators=(',', ':'))
    # c_new None: a fixed symbol instead of a counting number
    new_p = json.dumps(pre_n if c_new is None else [pre_n, ['$', 'span', None, {'data-count': c_new, 'children': '0'}], suf_n], ensure_ascii=False, separators=(',', ':'))
    raw('stan', old_p, new_p, 'payload', 1)
    mo = f'>{pre_o.replace("$$", "$")}<span data-count="{c_old}">0</span>{suf_o}</p>'
    mn = f'>{pre_n}</p>' if c_new is None else f'>{pre_n}<span data-count="{c_new}">0</span>{suf_n}</p>'
    raw('stan', mo, mn, 'markup', 1)
    rep(l_old, l_new, ['stan'])
rep('We did not set out to run an accelerator.', 'We did not set out to build an organization.')
rep('Stan started as a tool for creators who wanted to sell something to the people already listening to them. Building it taught us the thing the whole camp is built around: the gap between having an idea and having a customer is mostly courage and a very short deadline.',
    'Launchpad started with a few high school students in Vancouver who wanted more than what was on offer: competitions that felt real, mentors who had actually built things, and events that did not cost a fortune to enter. So we decided to build them ourselves.')
rep('So we started running that pattern on ourselves. Pick a wedge on Monday, talk to people by Wednesday, charge for it by Friday, and say all of it out loud while it happens. It landed often enough, and embarrassed us often enough, that we stopped treating it as a stunt.',
    'We started small, with one competition and a handful of volunteers. Every event taught us something, and every student who took part made the next one better. Today we run case competitions, hackathons, school clubs and volunteer programs, all led by students.')
rep('Launchpad is that method handed over. We are not the gatekeepers of it and we do not think it belongs to us. A select group of founders, a camp, and the same fortnight we would have run anyway, except this time the whole thing is filmed, so the parts that usually get edited out of founder stories are the parts you get to watch.',
    'Launchpad is built on a simple idea: talent is everywhere, but opportunity is not. We are here to change that, one competition at a time, and to prove that high school students can build something that matters for the students who come after them.')
rep('Come and do it with us.', 'Come build it with us.')
rep('A select group of founders, one camp, sixteen days. If you have read this far you probably already know whether it is for you.',
    'Compete, volunteer, or start a club at your school. If you have read this far, you probably already know you belong here.')
rep('Who we are looking for', 'Who it’s for')

# ---- drifting tile wall (who page): the hovered column used to stop; keep it moving
_wall = [f for f, js in JS.items() if 'let i=D.current&&x||I.current===e?0:1' in js]
assert len(_wall) == 1, _wall
JS[_wall[0]] = JS[_wall[0]].replace('let i=D.current&&x||I.current===e?0:1', 'let i=D.current&&x?0:1')

# ---- navigation: Summit takes the place of the old initiatives page
rep('Initiatives', 'Summit')
rep('/agenda', 'https://summitcompetition.com')

# ---- footer: our socials, Summit and the legal page
SOCIAL_HEAD = '"className":"text-[13px] font-semibold text-[#142658]/50","children":"Stan"'
for name in PAGES:
    raw(name, 'text-[#142658]/50">Stan</p>', 'text-[#142658]/50">Follow us</p>', 'markup', 1)
    raw(name, SOCIAL_HEAD, SOCIAL_HEAD.replace('"Stan"', '"Follow us"'), 'payload', 1)
rep('https://www.instagram.com/stanforcreators', 'https://www.instagram.com/launchpadsociety/')
rep('https://www.linkedin.com/company/stanwithme', 'https://www.linkedin.com/company/launchpad-entrepeunrial-society/')
rep('/legal/terms', '/legal')
rep('Program details', 'Legal')
rep('https://assets.stanwith.me/legal/terms-of-service.pdf', 'https://summitcompetition.com')
rep('Stan Terms of Service', 'Summit')

# ---- legal page (content from summitcompetition.com/legal)
sys.path.insert(0, 'tools')
from legal_content import SECTIONS  # noqa: E402
rep('Program Details | Launchpad', 'Legal | Launchpad', ['legal'])


def slug(t):
    return re.sub(r'[^a-z0-9]+', '-', t.lower().replace('’', '')).strip('-')


def node(tag, props, children):
    """Build the same element as a React payload node and as SSR markup."""
    attrs = ''.join(f' {"class" if k == "className" else k}="{html.escape(v, quote=True)}"' for k, v in props.items())
    kids = children if isinstance(children, list) else [children]
    inner = ''.join(k[1] if isinstance(k, tuple) else html.escape(k) for k in kids)
    pl = [k[0] if isinstance(k, tuple) else k for k in kids]
    return (['$', tag, None, dict(props, children=pl if isinstance(children, list) else pl[0])],
            f'<{tag}{attrs}>{inner}</{tag}>')


H2 = 'text-[1.15rem] font-bold leading-tight tracking-[-0.03em] md:text-[1.4rem]'
H3 = 'text-base font-semibold leading-snug tracking-[-0.02em] pt-2'
P = 'text-base leading-relaxed text-black'
toc = node('ol', {'className': 'mt-4 space-y-1.5 list-decimal pl-5 text-base text-black'},
           [node('li', {}, [node('a', {'href': '#' + slug(sec['title']), 'className': 'underline-offset-2 hover:underline hover:text-[#284be4]'}, sec['title'])]) for sec in SECTIONS])
sections = []
for sec in SECTIONS:
    blocks = [node('h3' if kind == 'h3' else 'p', {'className': H3 if kind == 'h3' else P}, text) for kind, text in sec['blocks']]
    sections.append(node('section', {'id': slug(sec['title']), 'className': 'scroll-mt-24'},
                         [node('h2', {'className': H2}, sec['title']), node('div', {'className': 'mt-3 space-y-3'}, blocks)]))
LEGAL_CLASS = 'mx-auto max-w-7xl px-6 md:px-10 pt-14 pb-20 md:pt-20 md:pb-28'
legal = node('section', {'className': LEGAL_CLASS}, [
    node('h1', {'className': 'font-display max-w-[18ch] text-[2.25rem] leading-[0.9] tracking-[-0.05em] md:text-[3.25rem]'}, 'Legal'),
    node('p', {'className': 'font-label mt-4 text-[11px] uppercase tracking-wider text-[#808eb6]'}, 'LaunchPad Entrepreneurial Society'),
    node('div', {'className': 'mt-8 max-w-[68ch]'}, [node('h2', {'className': H2}, 'Contents'), toc]),
    node('div', {'className': 'mt-14 max-w-[68ch] space-y-12'}, sections),
])
FOOTER_START = '<section class="relative overflow-hidden text-[#142658]"'
_pg = PAGES['legal']
for _i in _pg.markup_idx:
    _s = _pg.parts[_i]
    _a = _s.find('<section class="' + LEGAL_CLASS + '">')
    if _a >= 0:
        _b = _s.index(FOOTER_START, _a)
        _pg.parts[_i] = _s[:_a] + legal[1] + _s[_b:]
        break
else:
    raise SystemExit('legal: content section not found')
edit_payload_elem('legal', '"className":"' + LEGAL_CLASS + '"', lambda el: el.__setitem__(slice(None), legal[0]))

# ---- footer column heading (after the agenda edits, which rename an act called Explore)
for name in PAGES:
    raw(name, '></span>Camp</p>', '></span>Explore</p>', 'markup', 1)
    raw(name, ',"Camp"]', ',"Explore"]', 'payload', 1)

# ---- assets: renamed logo, and share images that pointed at Stan's server
for pg in PAGES.values():
    pg.sub_markup(lambda s: s.replace('/brand/stan-x-launchpad-lockup.png', '/brand/launchpad-lockup.png'))
    pg.sub_payload(lambda s: s.replace('/brand/stan-x-launchpad-lockup.png', '/brand/launchpad-lockup.png'))
    pg.sub_markup(lambda s: re.sub(r'<meta (?:property|name)="(?:og|twitter):image[^"]*" content="[^"]*"/>', '', s))
for f in JS:
    JS[f] = JS[f].replace('/brand/stan-x-launchpad-lockup.png', '/brand/launchpad-lockup.png')

# ------------------------------------------------------------------ write
for pg in PAGES.values():
    pg.save()
for f, s in JS.items():
    open(f, 'w', encoding='utf-8').write(s)
CSS = '_next/static/mirror/chunks/35wfv2cy29n3b.css'
css = open(CSS, encoding='utf-8').read().split('\n/* ---- Launchpad Entrepreneurial Society overrides')[0]
open(CSS, 'w', encoding='utf-8').write(css + open('tools/les.css', encoding='utf-8').read())
for hits, what in LOG:
    if hits == 0:
        print('   0 hits:', what)
print(f'{len(LOG)} edits applied')
