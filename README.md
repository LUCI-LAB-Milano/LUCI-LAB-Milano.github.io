# LUCI Lab Website

Hugo site for the **Logic, Uncertainty, Computation and Information Lab**  
Department of Philosophy "Piero Martinetti" — Università degli Studi di Milano

---

## Stack

| Layer | Tool |
|---|---|
| Static site generator | [Hugo](https://gohugo.io) 0.128+ |
| Hosting | GitHub Pages (free) |
| CI/CD | GitHub Actions |
| Email → publish pipeline | Zapier Email Parser + Code step |
| Theme | Custom (`themes/luci/`) — no dependencies |

---

## Local development

```bash
# 1. Install Hugo (extended)
brew install hugo          # macOS
# or https://gohugo.io/installation/

# 2. Clone the repo
git clone https://github.com/YOUR_ORG/luci-site.git
cd luci-site

# 3. Serve locally with live reload
hugo server -D
# → http://localhost:1313
```

---

## Deploying

Every push to `main` triggers the GitHub Actions workflow (`.github/workflows/deploy.yml`) which builds the site and publishes it to GitHub Pages.

**One-time setup:**

1. Go to your repo → **Settings → Pages**
2. Set Source to **GitHub Actions**
3. The workflow handles everything else — no `gh-pages` branch needed

---

## Adding content manually

Hugo's `hugo new` command scaffolds files from archetypes:

```bash
# News post
hugo new content/news/my-post-slug.md

# Seminar
hugo new content/seminars/speaker-lastname-YYYY-MM-DD.md

# New member
hugo new content/members/firstname-lastname.md
```

Then edit the generated Markdown file. Push to `main` to publish.

---

## Email-to-publish workflow

Any lab member can publish by sending a **structured email** to the lab's update address (configured in Zapier).

### Step 1 — Set up Zapier

1. Create a free [Zapier](https://zapier.com) account
2. Create a new Zap: **Email Parser by Zapier** → **Code by Zapier** → *(optional: Slack/email confirmation)*
3. In **Email Parser**, note the `@robot.zapier.com` inbox address — this is what members send to
4. In the **Code** step, paste the contents of `scripts/zapier-code-step.js`
5. Add these **Input Data** fields to the Code step:

| Key | Value |
|---|---|
| `GITHUB_TOKEN` | A GitHub Personal Access Token with `repo` scope |
| `GITHUB_OWNER` | Your GitHub username or org (e.g. `luci-unimi`) |
| `GITHUB_REPO` | Repository name (e.g. `luci-site`) |

### Step 2 — Email format

Send to the Zapier inbox address. Subject must start with `[news]`, `[seminar]`, or `[member]`.

**News post:**
```
Subject: [news] New postdoc position open

date: 2026-05-01
body:
We are happy to announce an open postdoctoral position...
```

**Seminar:**
```
Subject: [seminar] Proof Theory and Bounded Rationality

date: 2026-06-04
time: 14:30 CET
venue: Online via Teams
speaker: Maria Rossi
affiliation: University of Bologna
abstract: This talk explores the connection between...
body:
Full description of the talk goes here.
```

### What happens next

```
Email sent
  → Zapier parses fields
    → POSTs to GitHub API (repository_dispatch)
      → GitHub Actions runs email-update.yml
        → writes .md file to content/
          → commits + pushes to main
            → deploy.yml triggers
              → Hugo builds
                → site live in ~60 seconds
```

### Step 3 — Create a GitHub secret

In your repo → **Settings → Secrets → Actions**, add:

| Name | Value |
|---|---|
| `CONTENT_PAT` | Same Personal Access Token used in Zapier |

---

## Content structure

```
content/
  _index.md          ← homepage (no editing needed)
  news/              ← lab announcements, dated posts
  seminars/          ← one file per talk
  members/           ← one file per person
  research/          ← logic.md, uncertainty.md, computation.md
```

### Member frontmatter fields

```yaml
---
title: "Full Name"
role: "Permanent Member"   # or: Postdoctoral Researcher | PhD Student
website: "https://..."     # optional
interests: "Many-valued logics, ..."
weight: 1                  # controls display order
---
```

### Seminar frontmatter fields

```yaml
---
title: "Talk Title"
date: 2026-06-04T14:30:00+01:00
speaker: "Speaker Name"
affiliation: "Institution"
time: "14:30 CET"
venue: "Online via Teams"
abstract: "Short abstract shown in listings."
---

Full description of the talk goes here (body of the .md file).
```

---

## Customisation

| What | Where |
|---|---|
| Colours, fonts, spacing | `themes/luci/static/css/main.css` |
| Site title, tagline, email | `hugo.toml` → `[params]` |
| Navigation links | `hugo.toml` → `[menu]` |
| Homepage hero text | `themes/luci/layouts/index.html` |
| Header / footer | `themes/luci/layouts/partials/` |

The accent colour is `--accent: #8b3a2a` (terracotta). Change it in one place at the top of `main.css` and it cascades everywhere.

---

## User roles & access

| Role | How they publish |
|---|---|
| PI / admin | Push directly to `main`; manage GitHub repo |
| Lab member | Send structured email to Zapier inbox |
| Guest / collaborator | Submit to PI, who sends the email |

To restrict email publishing to known senders, add a **Filter** step in Zapier between the Email Parser and Code steps: only continue if the sender's address is in an allowlist.

---

## Maintenance

- **Hugo updates**: change `hugo-version` in `.github/workflows/deploy.yml`
- **Add a new section** (e.g. Publications): create `content/publications/_index.md`, add a list template in `themes/luci/layouts/`, add to `hugo.toml` menu
- **Custom domain**: add a `CNAME` file to `static/` with your domain, and configure DNS

---

*Built for LUCI Lab, University of Milan.*
