/* Voice commands: "go to the pool", "ground floor", "sit down", "evening"...
   Push to talk: hold remote button 3 (a quick tap still switches day / evening), hold V on a keyboard, or tap the mic
   pill on a phone outside the headset. Uses the browser's speech recognition (Chrome sends the audio to Google, so it
   needs a connection). V.voice.match(text) is pure and testable: it returns the action, or null. */
(function () {
  const T = AFRAME.THREE;
  const V = (window.V = window.V || {});
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  // what people call each room (the spot name itself always counts)
  const ALIAS = {
    'Arrival': ['gate', 'main gate', 'street', 'outside', 'start', 'beginning', 'arrival'],
    'Entrance': ['entrance', 'front door', 'foyer', 'entry', 'door'],
    'Drawing room': ['drawing', 'drawing room', 'formal living', 'sitting room', 'visitors room'],
    'Dining': ['dining', 'dining room', 'dining table', 'dinner table'],
    'Living': ['living', 'living room', 'hall', 'tv room', 'television'],
    'Kitchen': ['kitchen', 'cooking area', 'pantry'],
    'Guest bedroom': ['guest', 'guest room', 'guest bedroom'],
    'Deck': ['deck', 'garden', 'back garden', 'backyard', 'lawn', 'wooden deck'],
    'Staircase': ['stairs', 'staircase', 'steps'],
    'Family lounge': ['lounge', 'family lounge', 'family room', 'family area'],
    'Master bedroom': ['master', 'master bedroom', 'master room', 'main bedroom', 'parents room'],
    'Master balcony': ['balcony', 'master balcony', 'bedroom balcony'],
    'Bedroom 2': ['bedroom 2', 'bedroom two', 'second bedroom', 'kids room', 'children room'],
    'Pooja room': ['pooja', 'puja', 'pooja room', 'prayer room', 'mandir', 'temple'],
    'Upper lobby': ['lobby', 'upper lobby'],
    'Bedroom 3': ['bedroom 3', 'bedroom three', 'third bedroom'],
    'Home theatre': ['theatre', 'theater', 'home theatre', 'home theater', 'cinema', 'movie room', 'movies'],
    'Terrace': ['terrace', 'roof', 'rooftop', 'roof top'],
    'Plunge pool': ['pool', 'swimming pool', 'plunge pool', 'swimming', 'pool side', 'poolside'],
  };
  const FLOORS = [[/\b(ground|bottom|lower)\s*(floor|level)?\b|\bdownstairs\b/, 1], [/\b(first|1st|one|middle)\s*(floor|level)\b/, 2],
    [/\b(second|2nd|two|top)\s*(floor|level)\b/, 3]];
  const ACTIONS = [[/\b(sit|seat|have a seat|sit down)\b/, 'sit'], [/\b(stand|get up|stand up)\b/, 'stand'],
    [/\b(evening|night|dusk|sunset|dark|lights on)\b/, 'night'], [/\b(day|daytime|morning|daylight|sunlight|bright)\b/, 'day'],
    [/\b(next|forward)\b/, 'next'], [/\b(previous|back|go back|last room)\b/, 'prev']];

  const norm = (s) => s.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').replace(/\b(please|go|to|take|me|the|a|an|into|in|show|lets|let's|can|you|i|want|visit|open|on|at|towards)\b/g, ' ').replace(/\s+/g, ' ').trim();
  function lev(a, b) {                       // edit distance, for near misses ("plunge pole", "kitchin")
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++)
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    return d[a.length][b.length];
  }
  function matchOne(raw) {
    const t = ' ' + norm(raw) + ' ', spots = (V.layout && V.layout.spots) || [];
    if (!t.trim()) return null;
    // rooms first ("master balcony" must not read as a floor or an action), longest alias wins
    let best = null, bl = 0;
    spots.forEach((s, i) => (ALIAS[s.name] || []).concat([s.name.toLowerCase()]).forEach((a) => {
      if (t.includes(' ' + a + ' ') && a.length > bl) { bl = a.length; best = { kind: 'room', i, name: s.name }; }
    }));
    if (best) return best;
    for (const [re, lv] of FLOORS) if (re.test(t)) return { kind: 'floor', lv, name: ((V.layout.levels || [])[lv] || {}).name || 'Floor' };
    for (const [re, a] of ACTIONS) if (re.test(t)) return { kind: a, name: { sit: 'Sit down', stand: 'Stand up', night: 'Evening', day: 'Day', next: 'Next room', prev: 'Previous room' }[a] };
    // near misses: compare every alias with every word run of the same length
    const words = t.trim().split(' '); let bd = 1e9;
    spots.forEach((s, i) => (ALIAS[s.name] || []).concat([s.name.toLowerCase()]).forEach((a) => {
      const n = a.split(' ').length;
      for (let k = 0; k + n <= words.length; k++) {
        const w = words.slice(k, k + n).join(' '), d = lev(w, a) / Math.max(a.length, 4);
        if (d < bd) { bd = d; best = { kind: 'room', i, name: s.name }; }
      }
    }));
    return bd <= .34 ? best : null;
  }
  function match(alts) { for (const a of [].concat(alts)) { const m = matchOne(a); if (m) return m; } return null; }

  /* ---------------- acting on a command ---------------- */
  function run(m) {
    const n = V.nav; if (!n || !m) return;
    if (m.kind === 'room') return n.go(m.i);
    if (m.kind === 'floor') {
      const lift = V.layout.lift;
      if (lift && lift.levels.includes(m.lv) && !n.pending) { n.pending = { t: 'lift', to: m.lv }; n.fadeDir = 1; }
      else { const i = V.layout.spots.findIndex((s) => s.lv === m.lv); if (i >= 0) n.go(i); }
      return;
    }
    if (m.kind === 'sit') {
      const lv = n.levelOf(n.z); let bs = null, bd = 1e9;
      (V.layout.seats || []).forEach((s) => { const d = Math.hypot(s.x - n.px, s.y - n.py); if (n.levelOf(s.z) === lv && d < bd) { bd = d; bs = s; } });
      if (bs && !n.pending) { n.pending = { t: 'sit', s: bs }; n.fadeDir = 1; return; }
      return say('No seat on this floor');
    }
    if (m.kind === 'stand') return n.stand();
    if (m.kind === 'night' || m.kind === 'day') { if ((V.mood === 'day') !== (m.kind === 'day')) n.toggleMood(); return; }
    if (m.kind === 'next') return n.step(1);
    if (m.kind === 'prev') return n.step(-1);
  }

  /* ---------------- feedback: a pill on the camera (visible in the headset) and in the page ---------------- */
  let pill, pillCtx, pillTex, hideAt = 0;
  function ensurePill() {
    if (pill || !V.nav) return;
    const c = document.createElement('canvas'); c.width = 768; c.height = 128; pillCtx = c.getContext('2d');
    pillTex = new T.CanvasTexture(c); pillTex.colorSpace = T.SRGBColorSpace;
    pill = new T.Mesh(new T.PlaneGeometry(.48, .08), new T.MeshBasicMaterial({ map: pillTex, transparent: true, depthTest: false, depthWrite: false, toneMapped: false }));
    pill.position.set(0, -.2, -.8); pill.renderOrder = 1001; pill.frustumCulled = false; pill.visible = false;
    document.getElementById('cam').object3D.add(pill);
  }
  function say(text, mic, ms = 2200) {
    ensurePill();
    const el = document.getElementById('voiceTxt'); if (el) { el.textContent = text; el.parentNode.classList.toggle('on', !!text); }
    if (!pill) return;
    const x = pillCtx; x.clearRect(0, 0, 768, 128);
    x.fillStyle = 'rgba(43,30,22,0.86)'; x.beginPath(); x.roundRect(6, 14, 756, 100, 50); x.fill();
    x.strokeStyle = 'rgba(185,144,92,.95)'; x.lineWidth = 4; x.stroke();
    if (mic) { x.fillStyle = '#E2604A'; x.beginPath(); x.arc(64, 64, 14, 0, 7); x.fill(); }
    x.fillStyle = '#FBF8F3'; x.font = '500 42px Jost, Helvetica, Arial, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.fillText(text.length > 30 ? text.slice(0, 29) + '…' : text, 404, 66);
    pillTex.needsUpdate = true; pill.visible = document.body.classList.contains('vr');      // the page shows its own pill outside the headset hideAt = mic ? Infinity : performance.now() + ms;
  }
  function hideLater() { if (pill && performance.now() > hideAt) pill.visible = false; const el = document.getElementById('voiceTxt'); if (el && performance.now() > hideAt) el.parentNode.classList.remove('on'); }

  /* ---------------- listening ---------------- */
  let rec = null, listening = false, heard = [];
  function start() {
    if (!SR || listening) return;
    try {
      rec = new SR(); rec.lang = 'en-IN'; rec.interimResults = true; rec.maxAlternatives = 5; rec.continuous = false;
      heard = [];
      rec.onresult = (e) => {
        heard = []; for (const r of e.results) for (const a of r) heard.push(a.transcript);
        if (heard[0]) say('“' + heard[0].trim() + '”', true);
      };
      rec.onerror = (e) => { if (e.error === 'not-allowed') say('Microphone blocked: allow it in the browser'); else if (e.error !== 'aborted' && e.error !== 'no-speech') say('Voice error: ' + e.error); };
      rec.onend = () => { listening = false; document.body.classList.remove('listening'); finish(); };
      rec.start(); listening = true; document.body.classList.add('listening'); say('Listening…', true);
    } catch (e) { listening = false; say('Voice not available'); }
  }
  function stop() { if (rec && listening) { try { rec.stop(); } catch (_) {} } }
  function cancel() { if (rec && listening) { heard = []; try { rec.abort(); } catch (_) {} } }
  function finish() {
    if (!heard.length) { if (pill && pill.visible && hideAt === Infinity) say('', false, 0); return; }
    const m = match(heard);
    if (m) { say('→ ' + m.name); run(m); } else say('Try “go to the kitchen”');
  }
  // ask for the microphone before the headset view (a permission prompt cannot show inside it)
  function primeMic() {
    if (!SR || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
    navigator.mediaDevices.getUserMedia({ audio: true }).then((s) => s.getTracks().forEach((t) => t.stop())).catch(() => {});
  }

  V.voice = { supported: !!SR, match, matchOne, start, stop, cancel, run, say, primeMic, tick: hideLater };
})();
