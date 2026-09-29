# Project: The Creation Foundation Website

## Branches

- `main` — production. Deployed to Vercel. This is what the public sees. Only push code that is ready.
- `test` — staging. Work-in-progress pages and experiments live here. Not deployed. Merge into `main` when ready.

## Stack

Static pre-rendered output of a Next.js site (mirrored from launchpad.stan.store, recoloured and recopied for The Creation Foundation). No build step at deploy time — Vercel serves the committed HTML/JS/CSS as-is. There is no `package.json`; do not `npm install` or expect a dev server. Editing text/markup means editing the HTML files directly (see `tools/` for the scripts originally used to batch-rewrite copy and theme colors across the mirrored pages).

## File structure

- `index.html`, `who.html`, `where.html`, `stan.html`, `legal.html` — pages
- `_next/static/les/` — hashed JS/CSS bundles (Next.js runtime + chunks)
- `brand/`, `img/`, `img-dither/`, `trail/`, `trail-dither/`, `video/` — mirrored image/video/animation-frame assets
- `tools/` — Python scripts used to rewrite content/theme across the mirrored pages
- `vercel.json` — clean URLs + redirects (`/agenda`, `/apply` → `/`; `/legal/*` → `/legal`)

## Agent behavior

Multi-step tasks should be delegated to subagents whenever possible.

## Workflow

- New features/pages: work on `test` branch first
- When ready to go live: merge `test` → `main`, Vercel auto-deploys
- Do not push unfinished work to `main`
