// Voice command matcher: typical phrases (and near misses the recogniser produces) must land on the right target,
// and a matched command must actually move you. node tools/voicetest.mjs   (dev server running; PW=<dir with playwright-core>)
import { createRequire } from 'module';
const { chromium } = createRequire((process.env.PW || '.') + '/package.json')('playwright-core');
const CASES = [
  ['go to the pool', 'Plunge pool'], ['take me to the swimming pool', 'Plunge pool'], ['plunge pole', 'Plunge pool'],
  ['kitchen', 'Kitchen'], ['go to the kitchin', 'Kitchen'], ['show me the master bedroom', 'Master bedroom'],
  ['master bedroom balcony', 'Master balcony'], ['home theatre', 'Home theatre'], ['go to the theater', 'Home theatre'],
  ['cinema room', 'Home theatre'], ['living room', 'Living'], ['drawing room', 'Drawing room'], ['pooja room', 'Pooja room'],
  ['puja', 'Pooja room'], ['guest room', 'Guest bedroom'], ['bedroom two', 'Bedroom 2'], ['bedroom 3', 'Bedroom 3'],
  ['terrace', 'Terrace'], ['go to the deck', 'Deck'], ['main gate', 'Arrival'], ['dining table', 'Dining'],
  ['family lounge', 'Family lounge'], ['upper lobby', 'Upper lobby'], ['staircase', 'Staircase'],
  ['go to the ground floor', 'floor:1'], ['first floor', 'floor:2'], ['take me to the second floor', 'floor:3'], ['downstairs', 'floor:1'],
  ['sit down', 'sit'], ['stand up', 'stand'], ['make it evening', 'night'], ['switch to day', 'day'], ['next room', 'next'], ['go back', 'prev'],
  ['what is the weather', null], ['', null],
];
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--use-angle=d3d11'] });
const page = await browser.newPage();
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.goto('http://127.0.0.1:8090/');
await page.waitForFunction(() => document.body.classList.contains('ready'), null, { timeout: 180000 });
let bad = 0;
for (const [said, want] of CASES) {
  const got = await page.evaluate((t) => { const m = V.voice.matchOne(t); return m ? (m.kind === 'room' ? m.name : m.kind === 'floor' ? 'floor:' + m.lv : m.kind) : null; }, said);
  const ok = got === want; if (!ok) bad++;
  console.log(ok ? 'PASS' : 'FAIL', JSON.stringify(said), '->', got, ok ? '' : '(want ' + want + ')');
}
// a matched command moves you: "go to the pool" from the arrival spot
const moved = await page.evaluate(() => new Promise((res) => { V.voice.run(V.voice.match(['go to the pool'])); setTimeout(() => res(document.getElementById('wroom').textContent), 1200); }));
if (moved !== 'Plunge pool') bad++;
console.log(moved === 'Plunge pool' ? 'PASS' : 'FAIL', 'run: arrived at', moved);
console.log('voice cases', CASES.length + 1, 'bad', bad);
await browser.close();
