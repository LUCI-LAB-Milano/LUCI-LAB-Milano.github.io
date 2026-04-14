#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const https = require('https');

const env = process.env;
const allowedSections = new Set(['news', 'events', 'seminars', 'members']);
const section = (env.SECTION || 'news').toLowerCase();
const slug = env.SLUG;
const title = env.TITLE || 'Untitled';
const date = env.DATE || new Date().toISOString().slice(0, 10);
const body = (env.BODY || '').trim();
const summary = (env.SUMMARY || env.ABSTRACT || body || '').trim().replace(/\s+/g, ' ').slice(0, 220);
const imageUrl = (env.IMAGE_URL || '').trim();
const senderEmail = (env.SENDER_EMAIL || '').trim().toLowerCase();
const allowedSenders = (env.ALLOWED_SENDERS || '')
  .split(',')
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);

if (!allowedSections.has(section)) {
  console.error(`Unsupported section: ${section}`);
  process.exit(1);
}
if (!slug) {
  console.error('SLUG is required');
  process.exit(1);
}
if (allowedSenders.length && !allowedSenders.includes(senderEmail)) {
  console.error(`Sender not allowed: ${senderEmail || '(empty)'}`);
  process.exit(1);
}

const bundleDir = path.join('content', section, slug);
fs.mkdirSync(bundleDir, { recursive: true });

const imageRelative = imageUrl
  ? `./${fileNameFromUrl(imageUrl)}`
  : section === 'members'
    ? './portrait.svg'
    : './cover.svg';

const frontmatter = buildFrontmatter({ title, date, summary, imageRelative, section });
const contentPath = path.join(bundleDir, 'index.md');
fs.writeFileSync(contentPath, `${frontmatter}\n${body || defaultBody(section, title)}\n`, 'utf8');

(async () => {
  if (imageUrl) {
    await download(imageUrl, path.join(bundleDir, fileNameFromUrl(imageUrl)));
  } else {
    writeFallbackSvg(path.join(bundleDir, section === 'members' ? 'portrait.svg' : 'cover.svg'), title, section);
  }
  console.log(`Wrote ${contentPath}`);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});

function esc(value) {
  return String(value || '')
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\n/g, ' ');
}

function buildFrontmatter({ title, date, summary, imageRelative, section }) {
  let out = `---\ntitle: "${esc(title)}"\ndate: ${date}\nsummary: "${esc(summary)}"\nimage: "${imageRelative}"\n`;
  if (section === 'seminars' || section === 'events') {
    if (env.EVENT_TYPE) out += `event_type: "${esc(env.EVENT_TYPE)}"\n`;
    if (env.TALK_TIME) out += `time: "${esc(env.TALK_TIME)}"\n`;
    if (env.LOCATION) out += `location: "${esc(env.LOCATION)}"\n`;
    if (env.SPEAKER) out += `speaker: "${esc(env.SPEAKER)}"\n`;
    if (env.AFFILIATION) out += `affiliation: "${esc(env.AFFILIATION)}"\n`;
    if (env.ABSTRACT) out += `abstract: "${esc(env.ABSTRACT)}"\n`;
  }
  if (section === 'members') {
    if (env.ROLE) out += `role: "${esc(env.ROLE)}"\n`;
    if (env.INTERESTS) out += `interests: "${esc(env.INTERESTS)}"\n`;
    if (env.WEBSITE) out += `website: "${esc(env.WEBSITE)}"\n`;
  }
  out += '---\n';
  return out;
}

function defaultBody(section, title) {
  switch (section) {
    case 'members':
      return `${title} profile created from the email publishing workflow.`;
    case 'seminars':
      return env.ABSTRACT || `${title} seminar page created from the email publishing workflow.`;
    default:
      return `${title} page created from the email publishing workflow.`;
  }
}

function fileNameFromUrl(url) {
  try {
    const name = path.basename(new URL(url).pathname) || 'image';
    return name.replace(/[^A-Za-z0-9._-]/g, '-');
  } catch {
    return 'image';
  }
}

function download(url, dest) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(download(res.headers.location, dest));
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`Failed to download image: ${res.statusCode}`));
      }
      const file = fs.createWriteStream(dest);
      res.pipe(file);
      file.on('finish', () => file.close(resolve));
      file.on('error', reject);
    }).on('error', reject);
  });
}

function writeFallbackSvg(dest, title, section) {
  const label = section === 'members' ? initials(title) : title;
  const fontSize = section === 'members' ? 260 : 74;
  const footer = section === 'members' ? 'Member portrait placeholder' : 'Event graphic placeholder';
  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900" role="img" aria-label="${escapeXml(title)}">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#f4dfd7"/>
      <stop offset="100%" stop-color="#8b3a2a"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="900" fill="url(#g)"/>
  <rect x="48" y="48" width="1104" height="804" rx="36" fill="rgba(255,255,255,0.15)" stroke="rgba(255,255,255,0.4)"/>
  <text x="80" y="130" font-family="Arial, Helvetica, sans-serif" font-size="36" fill="#fff" opacity="0.9">LUCI Lab</text>
  <text x="80" y="480" font-family="Arial, Helvetica, sans-serif" font-size="${fontSize}" font-weight="700" fill="#fff">${escapeXml(label)}</text>
  <text x="80" y="820" font-family="Arial, Helvetica, sans-serif" font-size="32" fill="#fff" opacity="0.95">${footer}</text>
</svg>`;
  fs.writeFileSync(dest, svg, 'utf8');
}

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
}

function escapeXml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}
