// Sit in every seat (layout.seats) and photograph the view, then stand up and check you land on open floor.
// node tools/shoot_seats.mjs   (dev server running; PW=<dir with playwright-core>)
import { createRequire } from 'module';
import { mkdirSync } from 'fs';
const { chromium } = createRequire((process.env.PW || '.') + '/package.json')('playwright-core');
const out = new URL('../build/shots/', import.meta.url).pathname.replace(/^\/(\w:)/, '$1'); mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--use-angle=d3d11', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.goto('http://127.0.0.1:8090/');
await page.waitForFunction(() => document.body.classList.contains('ready'), null, { timeout: 120000 });
const n = await page.evaluate(() => V.layout.seats.length);
let bad = 0;
for (let i = 0; i < n; i++) {
  const name = await page.evaluate((i) => { const s = V.layout.seats[i]; V.nav.pending = { t: 'sit', s }; V.nav.fadeDir = 1; return s.name; }, i);
  await page.waitForTimeout(1600);
  await page.screenshot({ path: `${out}seat_${name.replace(/\W+/g, '_')}.png` });
  const r = await page.evaluate(() => { V.nav.stand(); return new Promise((ok) => setTimeout(() => ok({ seated: !!V.nav.seated, z: V.nav.z, ok: V.nav.standable(V.nav.px, V.nav.py, V.nav.z) !== null }), 1200)); });
  if (r.seated || !r.ok) bad++;
  console.log(r.seated || !r.ok ? 'FAIL' : 'PASS', name, JSON.stringify(r));
}
console.log('seats', n, 'bad', bad);
await browser.close();
