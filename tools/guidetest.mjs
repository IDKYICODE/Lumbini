// Guided tour: a "phone" page (?client=4821) and a "laptop" page (?guide=4821) through the local relay.
// Checks: they pair; the guide's teleport, walk, seat and evening reach the client; the client's head direction
// reaches the guide's camera. node tools/guidetest.mjs  (dev server + node relay/server.js running; PW=...)
import { createRequire } from 'module';
import { mkdirSync } from 'fs';
const { chromium } = createRequire((process.env.PW || '.') + '/package.json')('playwright-core');
const out = new URL('../build/shots/', import.meta.url).pathname.replace(/^\/(\w:)/, '$1'); mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--use-angle=d3d11'] });
const open = async (q) => {
  const p = await browser.newPage({ viewport: { width: 960, height: 540 } });
  p.on('pageerror', (e) => console.log('[pageerror]', q, e.message));
  await p.goto('http://127.0.0.1:8090/?q=low&' + q);
  await p.waitForFunction(() => document.body.classList.contains('ready'), null, { timeout: 180000 });
  return p;
};
let bad = 0; const check = (ok, what, info) => { if (!ok) bad++; console.log(ok ? 'PASS' : 'FAIL', what, info === undefined ? '' : JSON.stringify(info)); };
const client = await open('client=4821'), guide = await open('guide=4821');
await guide.waitForTimeout(2500);
check(await guide.evaluate(() => document.getElementById('guideBar').textContent.includes('their view')), 'paired');
// teleport
await guide.evaluate(() => V.nav.go(V.layout.spots.findIndex((s) => s.name === 'Kitchen')));
await guide.waitForTimeout(2000);
const st = () => client.evaluate(() => ({ room: document.getElementById('wroom').textContent, x: +V.nav.px.toFixed(2), y: +V.nav.py.toFixed(2), z: +V.nav.z.toFixed(2) }));
const g = () => guide.evaluate(() => ({ x: +V.nav.px.toFixed(2), y: +V.nav.py.toFixed(2), z: +V.nav.z.toFixed(2) }));
let c = await st(), gg = await g();
check(c.room === 'Kitchen' && Math.hypot(c.x - gg.x, c.y - gg.y) < .05, 'teleport reaches the client', { c, gg });
// walk (hold W on the guide)
await guide.keyboard.down('KeyW'); await guide.waitForTimeout(1200); await guide.keyboard.up('KeyW'); await guide.waitForTimeout(1200);
c = await st(); gg = await g();
check(Math.hypot(c.x - gg.x, c.y - gg.y) < .1, 'walking follows', { c, gg });
// the client's head turns -> the guide's camera turns the same way (world space)
await client.evaluate(() => { const lc = document.getElementById('cam').components['look-controls']; lc.yawObject.rotation.y += 1.1; lc.pitchObject.rotation.x = -.3; });
await guide.waitForTimeout(800);
const dirs = await Promise.all([client, guide].map((p) => p.evaluate(() => { const v = new AFRAME.THREE.Vector3(0, 0, -1); document.getElementById('cam').object3D.getWorldDirection(v); return v.toArray().map((k) => +k.toFixed(3)); })));
check(Math.hypot(dirs[0][0] - dirs[1][0], dirs[0][1] - dirs[1][1], dirs[0][2] - dirs[1][2]) < .03, 'guide sees through the client\'s eyes', dirs);
// sit + evening
await guide.evaluate(() => { const s = V.layout.seats.find((k) => k.name === 'Living'); V.nav.pending = { t: 'sit', s }; V.nav.fadeDir = 1; });
await guide.waitForTimeout(2200);
c = await st(); check(c.room === 'Living' && Math.abs(c.z - (0.45 + .48 + .72 - 1.6)) < .02, 'sitting reaches the client', c);
await guide.evaluate(() => V.nav.toggleMood()); await guide.waitForTimeout(4000);
check(await client.evaluate(() => V.mood) === 'night', 'evening reaches the client');
// the client cannot move themselves
const before = await st(); await client.keyboard.down('KeyW'); await client.waitForTimeout(800); await client.keyboard.up('KeyW');
const after = await st(); check(Math.hypot(after.x - before.x, after.y - before.y) < .01, 'client keys do nothing', { before, after });
await client.screenshot({ path: out + 'guided_client.png' }); await guide.screenshot({ path: out + 'guided_guide.png' });
console.log('guided checks bad', bad);
await browser.close();
