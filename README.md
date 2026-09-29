# The Creation Foundation website

Website for The Creation Foundation, a youth-run nonprofit in Vancouver running free case competitions, hackathons, school clubs and volunteer programs for high school students.

The Creation Foundation is the public name of LaunchPad Entrepreneurial Society, the BC nonprofit society (S0083354) that is the legal entity. The site uses the public name everywhere except where the legal entity matters: the footer copyright ("LaunchPad Entrepreneurial Society, operating as The Creation Foundation") and the terms on `/legal`, which keep the society as the party.

The design, animations and pixel-dither image effect (recoloured to Launchpad blue, `#284be4`) come from a static mirror of a Next.js site; all copy has been rewritten for Launchpad. There is no build step: the repo is served as plain files.

## Pages

| URL | File | Content |
| --- | --- | --- |
| `/` | `index.html` | Home: mission, initiatives, stats, featured speakers, FAQ |
| `/who` | `who.html` | Who it’s for |
| `/where` | `where.html` | Where we are (Vancouver) |
| `/stan` | `stan.html` | Who we are |
| `/legal` | `legal.html` | Legal: event terms, privacy policy and website terms (from summitcompetition.com/legal, text in `tools/legal_content.py`) |

`vercel.json` turns on `cleanUrls` (so `/who` serves `who.html`) and redirects `/agenda` and `/apply` to the home page and `/legal/*` to `/legal`. (`agenda.html` is still rewritten by the content script, then removed by the theme script.)

## Editing the text

Each page stores its text twice: in the HTML and in the React data embedded in the page (`self.__next_f.push(...)`), which React uses when the page loads. Both copies have to change together, or React puts the old text back.

All copy changes live in `tools/les_content.py`. To change wording, edit that file and rebuild from the original mirror:

```sh
rm -rf _next/static/les
git checkout 3e4e675 -- index.html who.html where.html agenda.html stan.html legal/terms.html _next
python3 tools/les_content.py   # copy
python3 tools/les_theme.py     # blue theme (#284be4), recoloured images, assets moved to /_next/static/les/
python3 tools/theme_natural.py # two-tone natural palette
python3 tools/tcf_lockup.py    # header lockup, brand/creation-lockup.png
python3 tools/tcf_rebrand.py   # Launchpad -> The Creation Foundation (legal name kept where it matters)
python3 tools/tcf_hero.py      # home hero: title, subtitle, initiatives button, sky-bloom landscape
```

The script stops without saving anything if a phrase it expects isn't found. Page-wide CSS overrides (hidden Apply buttons, footer links, extra FAQs) are in `tools/les.css` and get appended by the script.

## Images

- `img/` — photos (dithered at runtime by the site's own script), including `gabriel-morgan.jpg` and the two “To be announced” speaker placeholders
- `brand/creation-lockup.png` — header logo (drawn by `tools/tcf_lockup.py`); `icon.svg`, `favicon.ico`, `apple-icon.png` — site icons

## Run locally

```sh
npx serve .
```
