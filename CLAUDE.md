# Project: The Creation Foundation Website

## Branches

- `main` — production. Deployed to Vercel. This is what the public sees. Only push code that is ready.
- `test` — staging. Work-in-progress pages and experiments live here. Not deployed. Merge into `main` when ready.

## Stack

Plain HTML + CSS. No JavaScript framework, no build tools, no bundler.

## File structure

- `index.html` — single page
- `styles.css` — all styles
- `assets/img/` — SVG logos and hero photo
- `assets/fonts/` — self-hosted Inter and Plus Jakarta Sans (woff2)

## Agent behavior

Multi-step tasks should be delegated to subagents whenever possible.

## Workflow

- New features/pages: work on `test` branch first
- When ready to go live: merge `test` → `main`, Vercel auto-deploys
- Do not push unfinished work to `main`
