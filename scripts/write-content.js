#!/usr/bin/env node
/**
 * write-content.js
 * Called by the email-update GitHub Actions workflow.
 * Reads env vars injected by the workflow and writes a Hugo content file.
 *
 * Supported sections: news | seminars | members
 */

const fs   = require('fs');
const path = require('path');

const {
  SECTION     = 'news',
  SLUG,
  TITLE       = 'Untitled',
  DATE        = new Date().toISOString().split('T')[0],
  BODY        = '',
  // Seminar extras
  SPEAKER     = '',
  AFFILIATION = '',
  TALK_TIME   = '14:30 CET',
  VENUE       = 'Online via Teams',
  ABSTRACT    = '',
} = process.env;

if (!SLUG) {
  console.error('ERROR: SLUG env var is required');
  process.exit(1);
}

/* ── Build frontmatter ── */
let frontmatter = `---\ntitle: "${TITLE.replace(/"/g, '\\"')}"\ndate: ${DATE}\n`;

if (SECTION === 'seminars') {
  if (SPEAKER)     frontmatter += `speaker: "${SPEAKER.replace(/"/g, '\\"')}"\n`;
  if (AFFILIATION) frontmatter += `affiliation: "${AFFILIATION.replace(/"/g, '\\"')}"\n`;
  if (TALK_TIME)   frontmatter += `time: "${TALK_TIME}"\n`;
  if (VENUE)       frontmatter += `venue: "${VENUE.replace(/"/g, '\\"')}"\n`;
  if (ABSTRACT)    frontmatter += `abstract: "${ABSTRACT.replace(/"/g, '\\"').replace(/\n/g, ' ')}"\n`;
}

frontmatter += `---\n`;

const content = frontmatter + '\n' + BODY + '\n';
const dir     = path.join('content', SECTION);
const file    = path.join(dir, `${SLUG}.md`);

fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(file, content, 'utf8');

console.log(`✓ Written: ${file}`);
