# The Creation Foundation Website

Static rebuild of The Creation Foundation landing page (hero section), matched pixel-for-pixel against the reference design at a 1870×976 viewport.

## Run locally

No build step. Serve the folder with any static server:

```sh
npx serve .
# or
python3 -m http.server 8080
```

Then open http://localhost:8080 (or 3000 for `serve`).

## Structure

```
index.html            Page markup (nav + hero)
styles.css            All styles, design tokens and responsive rules
assets/fonts/         Self-hosted variable fonts (SIL Open Font License)
  inter-*.woff2               Inter v4 (opsz + wght axes) — title & subtitle
  plus-jakarta-sans-*.woff2   Plus Jakarta Sans — nav, Apply button, "Stan"
assets/img/
  stan-mark.svg               Stan "$" mark
  launchpad-wordmark.svg      LAUNCHPAD wordmark
  logo-arcteryx.svg           Partner logos
  logo-fidelity.svg
  logo-spring.svg
  hero-lodge.png              Dithered purple lodge image (8-colour palette)
```

## Design tokens

| Token | Value |
| --- | --- |
| Brand purple | `#6355FF` |
| Text | `#000` on `#fff` |
| Title | Inter 400, 49px, −0.005em |
| Subtitle | Inter 420, 20px, −0.01em |
| Nav links / Apply | Plus Jakarta Sans 500, 18px |
| Page gutter | `clamp(20px, 9.2vw, 172px)` |

The hero image uses `image-rendering: pixelated` so the dither pattern stays crisp at every size.
