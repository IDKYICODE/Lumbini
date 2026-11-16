/* Guided tour: a guide on a laptop drives, the client in the headset follows and looks around freely.
   Phone:  ...?client       shows a 4-digit code (or ?client=4821 to fix it)
   Laptop: ...?guide        asks for the code (or ?guide=4821)
   The guide's position, teleports, seat and day / evening go to the phone; the phone's head direction comes back,
   so the laptop shows exactly what the client sees (C switches to the guide's own free look). Only the client's
   position is moved - their head is never turned (comfort). Messages pass through relay/server.js. */
(function () {
  const qs = new URLSearchParams(location.search);
  const role = qs.has('guide') ? 'guide' : qs.has('client') ? 'client' : null;
  if (!role) return;
  const T = AFRAME.THREE, V = (window.V = window.V || {});
  const local = /^(localhost|127\.|192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)/.test(location.hostname);
  const RELAY = qs.get('relay') || (local ? `ws://${location.hostname}:8091` : 'wss://vana-villa-relay.onrender.com');
  let code = (qs.get(role) || '').replace(/\D/g, '').slice(0, 6);
  if (role === 'client' && !code) code = String(1000 + Math.floor(Math.random() * 9000));
  let ws = null, peer = false, theirEyes = true, headQ = null, lastSend = 0, lastJump = null;
  V.guided = role;
  document.body.classList.add('guided-' + role);       // (deferred script: the body exists)

  /* ---------------- banner (page) ---------------- */
  const bar = document.createElement('div'); bar.id = 'guideBar'; document.body.appendChild(bar);
  const css = document.createElement('style');
  css.textContent = `#guideBar{position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:14;font:500 14px Jost,sans-serif;color:#FBF8F3;
    background:rgba(43,30,22,.82);border:1px solid rgba(185,144,92,.6);border-radius:999px;padding:9px 18px;backdrop-filter:blur(6px);display:flex;gap:10px;align-items:center}
    #guideBar b{font:600 22px/1 'Cormorant Garamond',serif;letter-spacing:.12em;color:#F1D7AE}#guideBar input{width:86px;font:600 18px Jost,sans-serif;letter-spacing:.2em;text-align:center;
    border-radius:999px;border:1px solid rgba(185,144,92,.7);background:#FBF8F3;color:#2B1E16;padding:4px 8px}#guideBar button{font:500 13px Jost,sans-serif;border-radius:999px;border:0;
    background:#B9905C;color:#2B1E16;padding:6px 14px;cursor:pointer}#guideBar i{font-style:normal;opacity:.75;font-size:12.5px}
    body.vr #guideBar{display:none}body.guided-client #rooms,body.guided-client #hint,body.guided-client #mic,body.guided-client #mood,body.guided-client #stand,body.guided-client #where{display:none!important}.dot{width:9px;height:9px;border-radius:50%;background:#C9542B;display:inline-block}.dot.on{background:#7BC47F}`;
  document.head.appendChild(css);
  function render() {
    const dot = `<span class="dot ${peer ? 'on' : ''}"></span>`;
    if (role === 'client') bar.innerHTML = peer ? `${dot} Guide connected - put on the headset` : `${dot} Guide code <b>${code}</b> <i>enter it on the laptop</i>`;
    else if (!code) {
      bar.innerHTML = `Client's code <input id="gcode" inputmode="numeric" maxlength="6" placeholder="4821"> <button id="ggo">Connect</button>`;
      const go = () => { code = document.getElementById('gcode').value.replace(/\D/g, ''); if (code) { connect(); render(); } };
      document.getElementById('ggo').onclick = go; document.getElementById('gcode').onkeydown = (e) => { e.stopPropagation(); if (e.key === 'Enter') go(); };
    } else bar.innerHTML = `${dot} Guiding <b>${code}</b> <i>${peer ? (theirEyes ? 'their view · C free look' : 'free look · C their view') : 'waiting for the headset…'}</i>`;
  }

  /* ---------------- connection ---------------- */
  function connect() {
    if (!code) return;
    try { ws = new WebSocket(RELAY); } catch (e) { return setTimeout(connect, 3000); }
    ws.onopen = () => ws.send(JSON.stringify({ t: 'hello', role, code }));
    ws.onmessage = (e) => { let m; try { m = JSON.parse(e.data); } catch { return; } on(m); };
    ws.onclose = () => { peer = false; render(); setTimeout(connect, 3000); };
    ws.onerror = () => {};
  }
  const send = (m) => { if (ws && ws.readyState === 1) ws.send(JSON.stringify(m)); };

  function on(m) {
    const n = V.nav;
    if (m.t === 'status') {
      peer = m.peer; render();
      if (peer && role === 'guide' && n && n.ready) { sendJump(); send({ t: 'mood', mood: V.mood }); }
      if (role === 'client' && V.voice) V.voice.say(peer ? 'Guide connected' : 'Guide disconnected');
      return;
    }
    if (!n || !n.ready) return;
    if (role === 'client') {
      if (m.t === 'jump') lastJump = m;                        // applied behind a fade in tick
      else if (m.t === 'mv') { n.tx = m.x; n.ty = m.y; n.tz = m.z; }
      else if (m.t === 'mood' && m.mood !== V.mood && !n.pending) { n.pending = { t: 'mood', mood: m.mood }; n.fadeDir = 1; }
    } else if (m.t === 'h') headQ = m.q;
  }
  function sendJump() {
    const n = V.nav;
    send({ t: 'jump', x: n.px, y: n.py, z: n.z, yaw: n.jumpYaw || 0, seated: !!n.seated, room: (document.getElementById('wroom') || {}).textContent || '',
      floor: (document.getElementById('wfloor') || {}).textContent || '' });
  }

  /* ---------------- wiring into the walkthrough ---------------- */
  function wire() {
    const n = V.nav, cam = n.cam;
    if (role === 'guide') {
      const setPos = n.setPos.bind(n);
      n.setPos = (x, y, z, yaw) => { setPos(x, y, z, yaw); n.jumpYaw = yaw; setTimeout(sendJump, 0); };   // after seat / room labels are set
      n.el.sceneEl.addEventListener('mood', (e) => send({ t: 'mood', mood: e.detail.mood }));
      window.addEventListener('keydown', (e) => { if (e.code === 'KeyC' && !e.repeat && document.activeElement.tagName !== 'INPUT') { theirEyes = !theirEyes; render(); } });
    } else {
      // the client only looks: no walking, buttons, taps or voice of their own
      const readInput = n.readInput.bind(n);
      n.readInput = () => { readInput(); return { ix: 0, iz: 0, btn: [] }; };
      n.confirm = n.step = n.go = n.tap = n.stand = n.toggleMood = () => {};
      if (V.voice) V.voice.start = () => {};
      n.tx = n.px; n.ty = n.py; n.tz = n.z;
    }
    render();
  }

  const _q = new T.Quaternion(), _r = new T.Quaternion();
  AFRAME.registerComponent('guided', {
    tick(time, dt) {
      const n = V.nav; if (!n || !n.ready) return;
      if (!this.wired) { this.wired = true; wire(); connect(); }
      const cam = n.cam.object3D, lc = n.cam.components['look-controls'];
      if (role === 'guide') {
        if (peer && time - lastSend > 50) { lastSend = time; send({ t: 'mv', x: +n.px.toFixed(3), y: +n.py.toFixed(3), z: +n.z.toFixed(3) }); }
        const follow = peer && theirEyes && headQ;
        if (lc && lc.data.enabled === !!follow) n.cam.setAttribute('look-controls', 'enabled', !follow);
        if (follow) {                                          // the laptop camera takes the client's head direction (world space)
          n.el.object3D.getWorldQuaternion(_r).invert();
          cam.quaternion.copy(_r.multiply(_q.fromArray(headQ)));
        }
        V.showReticle = !!follow;                              // their gaze dot in the middle of the laptop screen
      } else {
        // head direction to the guide (in the headset the pose lives on the inner camera)
        if (peer && time - lastSend > 50) { lastSend = time; (n.cam.getObject3D('camera') || cam).getWorldQuaternion(_q); send({ t: 'h', q: _q.toArray().map((v) => +v.toFixed(4)) }); }
        if (lastJump && !n.pending) {                          // teleport, sit, stand, lift: behind the usual fade
          const j = lastJump; lastJump = null;
          n.pending = { t: 'fn', fn: () => { n.setPos(j.x, j.y, j.z, j.yaw); n.tx = j.x; n.ty = j.y; n.tz = j.z; n.announce(j.room, j.floor); } }; n.fadeDir = 1;
        } else if (n.fadeDir === 0 && n.tx !== undefined) {   // walking: glide to the guide's position
          const k = 1 - Math.exp(-dt / 90), dx = n.tx - n.px, dy = n.ty - n.py;
          if (Math.hypot(dx, dy) > 1.5) { lastJump = { x: n.tx, y: n.ty, z: n.tz, yaw: n.el.object3D.rotation.y + n.camYaw(), room: '', floor: '' }; }
          else { n.px += dx * k; n.py += dy * k; n.z = n.tz; n.vig = Math.max(n.vig, Math.min(1, Math.hypot(dx, dy) * 2)); }
        }
      }
    },
  });
  const add = () => document.querySelector('a-scene').setAttribute('guided', '');
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', add) : add();
})();
