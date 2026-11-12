// Ride the lift to each floor and photograph the lift doors from where you land (checks the doors exist and you
// arrive on open floor). node tools/shoot_lift.mjs   (dev server running; PW=<dir with playwright-core>)
import { createRequire } from 'module';
import { mkdirSync } from 'fs';
const { chromium } = createRequire((process.env.PW || '.') + '/package.json')('playwright-core');
const out = new URL('../build/shots/', import.meta.url).pathname.replace(/^\/(\w:)/, '$1'); mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--use-angle=d3d11', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.goto('http://127.0.0.1:8090/?spot=Staircase');
await page.waitForFunction(() => document.body.classList.contains('ready'), null, { timeout: 120000 });
for (const lv of [1, 2, 3]) {
  await page.evaluate((to) => { V.nav.pending = { t: 'lift', to }; V.nav.fadeDir = 1; }, lv);
  await page.waitForTimeout(1500);
  // turn round to face the lift (west) and step back a little so the doors fill the frame
  const st = await page.evaluate(() => {
    const lc = document.getElementById('cam').components['look-controls']; lc.yawObject.rotation.y = 0; lc.pitchObject.rotation.x = -.05;
    V.nav.el.object3D.rotation.y = Math.PI / 2; V.nav.px += .6; V.nav.el.object3D.position.x = V.nav.px;
    return { x: V.nav.px.toFixed(2), y: V.nav.py.toFixed(2), z: V.nav.z.toFixed(2), standable: V.nav.standable(V.nav.px - .6, V.nav.py, V.nav.z) !== null };
  });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${out}lift_${lv}.png` });
  console.log('lift', lv, JSON.stringify(st));
}
await browser.close();
