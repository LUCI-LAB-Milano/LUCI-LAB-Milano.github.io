# LUCI AIR publications automation

This bundle turns `/publications/` into a page generated from AIR researcher pages.

## What is included

- `scripts/sync_air_publications.py`
  - fetches each configured AIR researcher page
  - looks for AIR export links on the page
  - prefers a CSV export when AIR exposes one
  - falls back to scraping the rendered HTML when a CSV export is not available
  - merges and deduplicates publications across LUCI co-authors
  - writes `data/publications.json`
- `data/air_members.json`
  - seed list of current LUCI members with confirmed AIR researcher URLs where available
- `layouts/publications/list.html`
  - Hugo section template for `/publications/`
- `content/publications/_index.md`
  - replacement section intro
- `.github/workflows/sync-publications.yml`
  - weekly and manual GitHub Actions sync

## One-time installation

Copy these files into the root of the website repository, preserving the paths.

Then commit and push.

## First run

In GitHub:

1. open **Actions**
2. open **Sync AIR publications**
3. click **Run workflow**

The workflow will update `data/publications.json` and commit the refreshed data back to `main`.
Your existing deploy workflow should then rebuild the site automatically.

## AIR researcher pages already configured

The seed config already includes confirmed AIR researcher pages for:

- Giuseppe Primiero
- Hykel Hosni
- Marcello D'Agostino
- Costanza Larese
- Ekaterina Kubyshkina
- Stipe Pandžić
- Alejandro J. Solares-Rojas
- Francesco A. Genco
- Jürgen Landes
- Paolo Baldi

## Members still to map manually

These current members are present in `data/air_members.json` but left disabled until you add the right AIR researcher URL:

- Luca Ausili
- Francesco Ponti
- Giovanni Duca
- Giovanni Sanavio
- Alberto Termine
- Esther Anna Corsi
- Soroush Rafiee Rad

To enable one, edit the corresponding object in `data/air_members.json`, add the AIR page URL, and set `"enabled": true`.

## Notes

- AIR can be inconsistent about direct fetches, so the script is designed as a best-effort sync.
- The preferred path is CSV export because it is much easier to parse reliably than the rendered HTML.
- When AIR does not expose a usable CSV export link, the script falls back to scraping the researcher page itself.
- Deduplication uses AIR item URL first, DOI second, then normalized title plus year.
