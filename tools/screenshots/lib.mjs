// Shared capture library for the tester-guide storyboards. A storyboard is data (see
// storyboards/*.mjs); this file knows how to sign in, open a sidebar group, draw the ring +
// pointer + numbered caption on a target, shoot, and click. What it knows about THIS app comes
// from app.config.mjs (project-owned). Runs against tools/screenshots/stack.sh.
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import APP from './app.config.mjs';

export const BASE = APP.base;
export const API = APP.api;
export const PASS = APP.password;
const RING = APP.ring || '#D92D20';
const VIEW = APP.viewport || { width: 1440, height: 900 };
const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 70);

/** A signed-in API client for storyboard SETUP calls (the state the guide assumes). */
export async function api(email) {
  const login = await fetch(`${API}${APP.login.apiPath}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(APP.login.apiBody(email, PASS)) }).then((r) => r.json());
  const h = { 'content-type': 'application/json', authorization: `Bearer ${login[APP.login.tokenField || 'token']}` };
  return {
    get: (p) => fetch(`${API}${p}`, { headers: h }).then((r) => r.json()),
    post: (p, body) => fetch(`${API}${p}`, { method: 'POST', headers: h, body: JSON.stringify(body || {}) }),
    put: (p, body) => fetch(`${API}${p}`, { method: 'PUT', headers: h, body: JSON.stringify(body || {}) }),
    patch: (p, body) => fetch(`${API}${p}`, { method: 'PATCH', headers: h, body: JSON.stringify(body || {}) }),
  };
}

export class Capture {
  constructor(outDir) { this.out = outDir; this.n = 0; this.index = []; mkdirSync(outDir, { recursive: true }); }
  async start() { this.browser = await chromium.launch(); }
  async stop() { await this.browser?.close(); writeFileSync(`${this.out}/index.json`, JSON.stringify(this.index, null, 2)); }

  /** A fresh browser context signed in as `email`; `shotSignIn` captures the sign-in as a step. */
  async login(email, { shotSignIn } = {}) {
    this.ctx = await this.browser.newContext({ viewport: VIEW, deviceScaleFactor: 1 });
    const page = this.page = await this.ctx.newPage();
    await page.goto(BASE);
    await page.waitForSelector(APP.login.email);
    await page.fill(APP.login.email, email);
    await page.fill(APP.login.password, PASS);
    if (shotSignIn) await this.shot(page.locator(APP.login.submit), shotSignIn, { click: false, file: 'sign-in' });
    await page.click(APP.login.submit);
    await page.waitForSelector(APP.login.ready, { timeout: 15000 });
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(800);
    return page;
  }
  async logout() { await this.ctx?.close(); this.ctx = null; this.page = null; }

  /** The items container of a sidebar group (opens it if closed). */
  async group(gid) {
    const g = this.page.locator(APP.nav.group(gid));
    if ((await g.getAttribute('aria-expanded')) !== 'true') { await g.click(); await this.page.waitForTimeout(300); }
    return this.page.locator(APP.nav.items(gid));
  }
  /** A second-level group (e.g. Administration → sub-group); shoots both when captions are given. */
  async adminGroup(gid, captions = {}) {
    if (!APP.nav.admin) throw new Error('app.config.mjs has no nav.admin; this app has no second-level nav group');
    const admin = this.page.locator(APP.nav.admin);
    const openAdmin = (await admin.getAttribute('aria-expanded')) !== 'true';
    if (captions.admin) await this.shot(admin, captions.admin, { click: openAdmin }); else if (openAdmin) await admin.click();
    await this.page.waitForTimeout(400);
    const grp = this.page.locator(APP.nav.adminGroup(gid));
    const openGrp = (await grp.getAttribute('aria-expanded')) !== 'true';
    if (captions.group) await this.shot(grp, captions.group, { click: openGrp }); else if (openGrp) await grp.click();
    await this.page.waitForTimeout(400);
    return this.page.locator(APP.nav.adminItems(gid));
  }

  async annotate(locator, caption) {
    const page = this.page;
    await locator.scrollIntoViewIfNeeded().catch(() => {});
    await page.waitForTimeout(250);
    const box = await locator.boundingBox();
    await page.evaluate(({ box, caption, n, ring }) => {
      document.querySelectorAll('.__shot').forEach((e) => e.remove());
      if (!box) return;
      const pad = 6, mk = (tag) => { const el = document.createElement(tag); el.className = '__shot'; document.body.appendChild(el); return el; };
      const r = mk('div');
      Object.assign(r.style, { position: 'fixed', left: `${box.x - pad}px`, top: `${box.y - pad}px`, width: `${box.width + pad * 2}px`, height: `${box.height + pad * 2}px`,
        border: `3px solid ${ring}`, borderRadius: '10px', boxShadow: `0 0 0 4px ${ring}38, 0 0 0 9999px rgba(0,0,0,.10)`, zIndex: 99998, pointerEvents: 'none' });
      const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
      const ptr = mk('div');
      ptr.innerHTML = '<svg width="46" height="52" viewBox="0 0 24 28" xmlns="http://www.w3.org/2000/svg"><path d="M6 2v18l4.5-4.2 3 7.2 3.4-1.5-3-7H21z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>';
      Object.assign(ptr.style, { position: 'fixed', left: `${Math.min(cx + 4, window.innerWidth - 50)}px`, top: `${Math.min(cy + 2, window.innerHeight - 56)}px`, zIndex: 99999, pointerEvents: 'none', filter: 'drop-shadow(0 2px 3px rgba(0,0,0,.35))' });
      const cap = mk('div'); cap.textContent = `${n}. ${caption}`;
      const below = box.y + box.height + 60 < window.innerHeight;
      Object.assign(cap.style, { position: 'fixed', left: `${Math.max(12, Math.min(box.x, window.innerWidth - 560))}px`, top: below ? `${box.y + box.height + 18}px` : `${Math.max(8, box.y - 58)}px`,
        maxWidth: '540px', padding: '9px 14px', background: ring, color: '#fff', font: '600 15px/1.35 system-ui, -apple-system, Segoe UI, sans-serif', borderRadius: '8px', boxShadow: '0 4px 14px rgba(0,0,0,.25)', zIndex: 99999, pointerEvents: 'none' });
    }, { box, caption, n: this.n, ring: RING });   // `shot` has already advanced the counter
  }
  /** Draw on `locator`, shoot, clear, then click it (unless click: false). No locator = a plain shot. */
  async shot(locator, caption, { click = true, file, wait = 600 } = {}) {
    this.n += 1;
    const name = `${String(this.n).padStart(2, '0')}-${file || slug(caption)}.png`;
    if (locator) await this.annotate(locator, caption);
    await this.page.waitForTimeout(150);
    await this.page.screenshot({ path: `${this.out}/${name}` });
    await this.page.evaluate(() => document.querySelectorAll('.__shot').forEach((e) => e.remove()));
    this.index.push({ n: this.n, file: name, caption });
    console.log(`  ${name}`);
    if (locator && click) { await locator.click(); await this.page.waitForTimeout(wait); }
  }
}

/** Run a storyboard: { title, guide, outDir, setup?(api), parts: [{ title, login, shotSignIn?, run(cap, page) }] }, then write README.md. */
export async function runStoryboard(sb) {
  if (sb.setup) await sb.setup(api);
  const cap = new Capture(sb.outDir);
  await cap.start();
  const partRanges = [];
  try {
    for (const part of sb.parts) {
      const from = cap.n + 1;
      const page = await cap.login(part.login, { shotSignIn: part.shotSignIn });
      await part.run(cap, page);
      await cap.logout();
      partRanges.push({ title: part.title, from, to: cap.n });
    }
  } finally {
    await cap.stop();
    const lines = [`# ${sb.title} — screenshots`, '', `*One shot per step of \`${sb.guide}\`, captured on a fresh test seed (${new Date().toISOString().slice(0, 10)}). Each shot marks the element to click with a red ring, a pointer and a numbered caption — the storyboard for the walkthrough video.*`, '',
      `Regenerate: \`tools/screenshots/stack.sh up\`, then \`node tools/screenshots/capture.mjs ${sb.name}\`.`, ''];
    for (const r of partRanges) {
      lines.push(`## ${r.title}`, '');
      for (const e of cap.index.filter((e) => e.n >= r.from && e.n <= r.to)) lines.push(`${e.n}. **${e.caption}**  `, `   ![${e.caption}](${e.file})`, '');
    }
    writeFileSync(`${sb.outDir}/README.md`, lines.join('\n'));
    console.log(`${cap.n} shots → ${sb.outDir}`);
  }
}
