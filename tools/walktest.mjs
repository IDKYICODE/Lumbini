// Walk test: drive the keyboard in headless Chrome and check the visitor gets where they should.
// node tools/walktest.mjs   (dev server running; PW=<dir with playwright-core>)
import { createRequire } from 'module';
const { chromium } = createRequire((process.env.PW || '.') + '/package.json')('playwright-core');
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--use-angle=d3d11', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
const state = () => page.evaluate(() => ({ x: +V.nav.px.toFixed(2), y: +V.nav.py.toFixed(2), z: +V.nav.z.toFixed(2), lv: V.nav.levelOf(V.nav.z) }));
// face a plan direction (yaw: 0 = north/+y, -90 = east/+x) by setting the rig and resetting look-controls
const face = (deg) => page.evaluate((d) => { const lc = document.getElementById('cam').components['look-controls']; lc.yawObject.rotation.y = 0; lc.pitchObject.rotation.x = 0; V.nav.el.object3D.rotation.y = d * Math.PI / 180; }, deg);
const walk = async (key, ms) => { await page.keyboard.down(key); await page.waitForTimeout(ms); await page.keyboard.up(key); await page.waitForTimeout(300); };
let ok = true;
const check = (name, cond, s) => { console.log(cond ? 'PASS' : 'FAIL', name, JSON.stringify(s)); ok = ok && cond; };

await page.goto('http://127.0.0.1:8090/?spot=Arrival');
await page.waitForFunction(() => document.body.classList.contains('ready'), null, { timeout: 120000 });
await page.waitForTimeout(800);
// 1. street -> gateway -> steps -> porch -> into the drawing room (walking north)
await face(0); await walk('KeyW', 6500);
let s = await state(); check('enter the house from the street', s.lv === 1 && s.y > 2.6, s);
// 2. from the dining side, into the stair: flight 1 climbs west, landing, flight 2 climbs east to the first floor
await page.evaluate(() => V.nav.setPos(6.6, 8.8, .45, 0)); await face(90); await walk('KeyW', 4200);
s = await state(); check('flight 1 to the landing', s.z > 1.8 && s.z < 2.3, s);
await face(0); await walk('KeyW', 700); await face(-90); await walk('KeyW', 4200);
s = await state(); check('flight 2 to the first floor', s.lv === 2, s);
// 3. walls stop you: walk west into the lounge wall for a while
await page.evaluate(() => V.nav.setPos(9.5, 8.0, 3.75, 0)); await face(-90); await walk('KeyW', 4000);
s = await state(); check('lounge east wall stops you', s.x < 12.05 && s.lv === 2, s);
// 3b. second floor: lobby -> theatre (south through its door), lobby -> terrace (east through the open slider half)
await page.evaluate(() => V.nav.setPos(7.9, 7.4, 7.05, 0)); await face(180); await walk('KeyW', 3000);
s = await state(); check('into the home theatre', s.y < 6.0 && s.lv === 3, s);
await face(90); await walk('KeyW', 3000);
s = await state(); check('down the theatre aisle', s.x < 6.5 && s.lv === 3, s);
await page.evaluate(() => V.nav.setPos(7.0, 9.3, 7.05, 0)); await face(-90); await walk('KeyW', 3000);
s = await state(); check('out to the terrace', s.x > 8.8 && s.lv === 3, s);
// 3c. ground floor: dining -> deck through the slider, drawing room -> dining
await page.evaluate(() => V.nav.setPos(11.75, 9.0, .45, 0)); await face(-90); await walk('KeyW', 2500);
s = await state(); check('dining out to the deck', s.x > 12.3, s);
await page.evaluate(() => V.nav.setPos(8.0, 4.0, .45, 0)); await face(0); await walk('KeyW', 3000);
s = await state(); check('drawing room to dining', s.y > 6.6 && s.lv === 1, s);
// 4. the lift
await page.evaluate(() => { V.nav.pending = { t: 'lift', to: 3 }; V.nav.fadeDir = 1; }); await page.waitForTimeout(1200);
s = await state(); check('lift to the second floor', s.lv === 3, s);
await browser.close();
process.exit(ok ? 0 : 1);
