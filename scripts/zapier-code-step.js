/**
 * Zapier Code step for LUCI email publishing.
 *
 * Subject patterns:
 *   [news] Title
 *   [event] Title
 *   [seminar] Title
 *   [member] Full Name
 *
 * Body fields (all optional except body for normal posts):
 *   date: 2026-04-15
 *   summary: Short teaser
 *   time: 14:30 CET
 *   location: Online via Teams
 *   speaker: Sara Ugolini
 *   affiliation: IIIA – CSIC Barcelona
 *   abstract: ...
 *   role: Postdoctoral Researcher
 *   interests: ...
 *   website: https://...
 *   image_url: https://...
 *   body:
 *   Full markdown body here...
 */

const GITHUB_TOKEN = inputData.GITHUB_TOKEN;
const GITHUB_OWNER = inputData.GITHUB_OWNER;
const GITHUB_REPO = inputData.GITHUB_REPO;
const subject = (inputData.subject || '').trim();
const bodyText = inputData.body || '';
const senderEmail = (inputData.from_email || inputData.sender_email || '').trim();

const sectionMatch = subject.match(/^\[(news|event|seminar|member)\]\s*(.+)$/i);
if (!sectionMatch) {
  throw new Error(`Subject must start with [news], [event], [seminar], or [member]. Got: ${subject}`);
}

const rawSection = sectionMatch[1].toLowerCase();
const title = sectionMatch[2].trim();
const section = rawSection === 'event' ? 'events' : rawSection === 'seminar' ? 'seminars' : rawSection === 'member' ? 'members' : 'news';
const eventType = rawSection === 'event' ? 'event' : rawSection === 'seminar' ? 'seminar' : rawSection;

const fields = {};
let prose = '';
let inBody = false;
for (const line of bodyText.split('
')) {
  if (inBody) {
    prose += line + '
';
    continue;
  }
  if (line.trim().toLowerCase() === 'body:') {
    inBody = true;
    continue;
  }
  const kv = line.match(/^([a-zA-Z_]+):\s*(.+)$/);
  if (kv) fields[kv[1].toLowerCase()] = kv[2].trim();
}

const today = fields.date || new Date().toISOString().slice(0, 10);
const slugBase = rawSection === 'member'
  ? title.toLowerCase()
  : (fields.speaker ? `${fields.speaker.split(' ').slice(-1)[0]}-${today}` : title);
const slug = slugBase
  .normalize('NFD')
  .replace(/[̀-ͯ]/g, '')
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, '-')
  .replace(/(^-|-$)/g, '')
  .slice(0, 80);

const payload = {
  event_type: 'email-update',
  client_payload: {
    section,
    slug,
    title,
    date: today,
    body: prose.trim(),
    summary: fields.summary || '',
    event_type: eventType,
    speaker: fields.speaker || '',
    affiliation: fields.affiliation || '',
    time: fields.time || '',
    location: fields.location || fields.venue || '',
    abstract: fields.abstract || '',
    role: fields.role || '',
    interests: fields.interests || '',
    website: fields.website || '',
    image_url: fields.image_url || '',
    sender_email: senderEmail,
  },
};

const response = await fetch(`https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`, {
  method: 'POST',
  headers: {
    'Accept': 'application/vnd.github+json',
    'Authorization': `Bearer ${GITHUB_TOKEN}`,
    'X-GitHub-Api-Version': '2022-11-28',
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(payload),
});

if (!response.ok) {
  throw new Error(`GitHub API error ${response.status}: ${await response.text()}`);
}

return { status: 'ok', section, slug, title };
