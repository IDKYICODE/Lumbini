// Screenshot the walkthrough at named spots with headless Chrome (GPU), printing console errors.
// node tools/shoot.mjs [spot ...]   (needs the dev server: python tools/serve.py; PW=<folder with node_modules/playwright-core>)
import { createRequire } from 'module';
const { chromium } = createRequire((process.env.PW || '.') + '/package.json')('playwright-core');
import { mkdirSync } from 'fs';
const spots = process.argv.slice(2).length ? process.argv.slice(2) : ['Arrival'];
const out = new URL('../build/shots/', import.meta.url).pathname.replace(/^\/(\w:)/, '$1');
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true,
  args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on('console', (m) => { const t = m.text(); if (m.type() === 'error' || m.type() === 'warning' || /\[villa\]/.test(t)) console.log('[page]', m.type(), t.slice(0, 300)); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
for (const s of spots) {
  const t0 = Date.now();
  const [mood, sp] = s.includes(":") ? s.split(":") : ["day", s];
  const custom = sp.startsWith('@');            // @x,y,level,lookx,looky[,pitch] : any viewpoint in plan metres
  await page.goto(`http://127.0.0.1:8090/?debug${process.env.QS || ""}&mood=${mood}&spot=${custom ? 'Arrival' : encodeURIComponent(sp)}`);
  await page.waitForFunction(() => document.body.classList.contains('ready'), null, { timeout: 120000 });
  if (custom) await page.evaluate((v) => {
    const [x, y, lv, lx, ly, pitch] = v.slice(1).split(',').map(Number), n = V.nav, lc = document.getElementById('cam').components['look-controls'];
    n.setPos(x, y, n.LZ[lv], 0); lc.yawObject.rotation.y = 0; lc.pitchObject.rotation.x = pitch || 0;
    n.el.object3D.rotation.y = Math.atan2(-(lx - x), ly - y);
  }, sp);
  await page.waitForTimeout(mood === "night" ? 3500 : 1500);
  await page.screenshot({ path: `${out}${process.env.TAG || ""}${s.replace(/[ :@,.]/g, "_")}.png` });
  console.log('shot', s, Date.now() - t0, 'ms');
}
await browser.close();
