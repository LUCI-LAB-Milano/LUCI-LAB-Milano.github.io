# LUCI Lab website redesign and migration scaffold

This package is a drop-in Hugo replacement for the current LUCI GitHub Pages repository.

## What is included

- a cleaner information architecture,
- page-bundle based member pages with portraits,
- page-bundle based events and seminar pages with graphics,
- a modern custom layout and stylesheet,
- legacy URL aliases for key public WordPress pages,
- a hardened email-to-publish workflow for GitHub Actions.

## Key structural changes

### Members

Each member now lives in:

```text
content/members/<slug>/index.md
content/members/<slug>/portrait.(svg|jpg|png)
```

### Events and seminars

Each event or seminar now lives in:

```text
content/events/<slug>/index.md
content/events/<slug>/cover.(svg|jpg|png)
content/seminars/<slug>/index.md
content/seminars/<slug>/cover.(svg|jpg|png)
```

This makes image management straightforward and keeps content, metadata, and visuals together.

## Email posting

The workflow accepts structured emails, validates the sender against an allowlist, creates or updates a Hugo page bundle, optionally downloads a graphic from a URL, commits the change, and lets the Pages deploy run on `push`.

See `.github/workflows/email-update.yml` and `scripts/write-content.js`.

## What still needs manual completion

- FTP-only binaries or media not publicly reachable from the current live site
- final member portraits
- final event graphics where public copies were not available
- exact membership roster validation if the public site has changed since crawl time
