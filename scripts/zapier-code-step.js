/**
 * ZAPIER CODE STEP (JavaScript)
 * ─────────────────────────────
 * Place this as a "Code by Zapier" step after the "Email Parser by Zapier" trigger.
 *
 * Expected email format sent to updates@luci.unimi.it:
 * ─────────────────────────────────────────────────────
 * Subject: [news] Workshop on Bounded Rationality
 *
 * date: 2026-04-15
 * body:
 * We are pleased to announce the workshop…
 *
 * ─── For seminars, use subject [seminar] and add: ───
 * Subject: [seminar] Counterfactuals: an Algebraic View
 *
 * date: 2026-05-07
 * time: 14:30 CET
 * venue: Online via Teams
 * speaker: Sara Ugolini
 * affiliation: IIIA – CSIC, Barcelona
 * abstract: A counterfactual conditional is a statement…
 * body:
 * Full seminar description here…
 *
 * INPUT FIELDS FROM EMAIL PARSER STEP:
 *   inputData.subject  — email subject line
 *   inputData.body     — full email body text
 *
 * ZAPIER INPUT DATA (set in Code step):
 *   GITHUB_TOKEN  — your Personal Access Token (repo scope)
 *   GITHUB_OWNER  — your GitHub username or org
 *   GITHUB_REPO   — repository name, e.g. "luci-site"
 */

const GITHUB_TOKEN = inputData.GITHUB_TOKEN;
const GITHUB_OWNER = inputData.GITHUB_OWNER;
const GITHUB_REPO  = inputData.GITHUB_REPO;

// ── Parse section from subject ──────────────────────────────
const subject = inputData.subject || '';
const sectionMatch = subject.match(/^\[(news|seminar|member)\]\s*/i);
if (!sectionMatch) {
  throw new Error(`Subject must start with [news], [seminar], or [member]. Got: "${subject}"`);
}
const section = sectionMatch[1].toLowerCase() === 'seminar' ? 'seminars'
              : sectionMatch[1].toLowerCase() === 'member'  ? 'members'
              : 'news';
const title = subject.replace(/^\[.*?\]\s*/, '').trim();

// ── Parse key:value fields from body ──────────────────────────
const rawBody = inputData.body || '';
const fields  = {};
let   prose   = '';
let   inBody  = false;

for (const line of rawBody.split('\n')) {
  if (inBody) {
    prose += line + '\n';
    continue;
  }
  if (line.trim().toLowerCase() === 'body:') {
    inBody = true;
    continue;
  }
  const kv = line.match(/^(\w+):\s*(.+)$/);
  if (kv) {
    fields[kv[1].toLowerCase()] = kv[2].trim();
  }
}

// ── Build slug ─────────────────────────────────────────────────
const today = fields.date || new Date().toISOString().split('T')[0];
const slug  = (section === 'seminars' && fields.speaker)
  ? `${fields.speaker.split(' ').pop().toLowerCase()}-${today}`
  : title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 50);

// ── Build payload ──────────────────────────────────────────────
const payload = {
  event_type: 'email-update',
  client_payload: {
    section,
    slug,
    title,
    date:        today,
    body:        prose.trim(),
    speaker:     fields.speaker     || '',
    affiliation: fields.affiliation || '',
    time:        fields.time        || '14:30 CET',
    venue:       fields.venue       || 'Online via Teams',
    abstract:    fields.abstract    || '',
  }
};

// ── POST to GitHub ─────────────────────────────────────────────
const response = await fetch(
  `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`,
  {
    method:  'POST',
    headers: {
      'Accept':        'application/vnd.github+json',
      'Authorization': `Bearer ${GITHUB_TOKEN}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type':  'application/json',
    },
    body: JSON.stringify(payload),
  }
);

if (!response.ok) {
  const text = await response.text();
  throw new Error(`GitHub API error ${response.status}: ${text}`);
}

return { status: 'ok', section, slug, title };
