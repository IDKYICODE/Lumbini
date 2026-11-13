/* Navigation for the villa (adapted from office-vr): walk relative to where you look, collide with walls and
   furniture, climb the stairs (height follows the flight), teleport rings with a fade, a working lift between
   floors, comfort vignette, gaze reticle, HUD room chips, guided next/previous room on the remote.
   Inputs: Bluetooth gamepad axes + d-pad + buttons, WASD/arrows, Enter/Space, N/P, taps/clicks.
   The walkable plan comes from build/layout.json (Blender plan coords: x east, y north, z up). ?debug shows input. */
(function () {
  const T = AFRAME.THREE;
  const V = (window.V = window.V || {});
  const R = .22, SPEED = 1.35, DEAD = .18, STEP = .42;
  const cnv = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
  const ctex = (c) => { const t = new T.CanvasTexture(c); t.colorSpace = T.SRGBColorSpace; return t; };
  function radial(inner, outer, a) {
    const c = cnv(128, 128), x = c.getContext('2d'), g = x.createRadialGradient(64, 64, 64 * inner, 64, 64, 64 * outer);
    g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, `rgba(0,0,0,${a})`); x.fillStyle = g; x.fillRect(0, 0, 128, 128);
    return new T.CanvasTexture(c);
  }
  function drawLabel(c, text, sub) {
    const x = c.getContext('2d'); x.clearRect(0, 0, 512, 160);
    x.fillStyle = 'rgba(43,30,22,0.8)'; x.beginPath(); x.roundRect(8, 30, 496, sub ? 104 : 84, 42); x.fill();
    x.strokeStyle = 'rgba(185,144,92,.9)'; x.lineWidth = 3; x.stroke();
    x.fillStyle = '#FBF8F3'; x.font = '500 44px Jost, Helvetica, Arial, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.fillText(text, 256, sub ? 70 : 72);
    if (sub) { x.fillStyle = '#D9C4A4'; x.font = '500 22px Jost, Helvetica, Arial, sans-serif'; x.fillText(sub.toUpperCase(), 256, 110); }
  }
  function label(text, sub) { const c = cnv(512, 160); drawLabel(c, text, sub); return ctex(c); }
  function liftIcon(txt) {
    const c = cnv(128, 128), x = c.getContext('2d');
    x.fillStyle = 'rgba(43,30,22,0.85)'; x.beginPath(); x.arc(64, 64, 58, 0, 7); x.fill();
    x.lineWidth = 5; x.strokeStyle = '#B9905C'; x.stroke();
    x.fillStyle = '#FBF8F3'; x.font = '600 54px Jost, Helvetica, Arial, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(txt, 64, 68);
    return ctex(c);
  }
  function seatIcon() {           // round badge with a chair (side view)
    const c = cnv(128, 128), x = c.getContext('2d');
    x.fillStyle = 'rgba(43,30,22,0.85)'; x.beginPath(); x.arc(64, 64, 58, 0, 7); x.fill();
    x.lineWidth = 5; x.strokeStyle = '#B9905C'; x.stroke();
    x.strokeStyle = '#FBF8F3'; x.lineWidth = 8; x.lineCap = x.lineJoin = 'round';
    x.beginPath(); x.moveTo(46, 32); x.lineTo(46, 72); x.lineTo(84, 72); x.stroke();
    x.beginPath(); x.moveTo(52, 72); x.lineTo(52, 96); x.moveTo(80, 72); x.lineTo(80, 96); x.stroke();
    return ctex(c);
  }
  function beamTex() {
    const c = cnv(4, 64), x = c.getContext('2d'), g = x.createLinearGradient(0, 0, 0, 64);
    g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(1, 'rgba(255,255,255,0.9)'); x.fillStyle = g; x.fillRect(0, 0, 4, 64);
    return new T.CanvasTexture(c);
  }

  AFRAME.registerComponent('villa-nav', {
    init() {
      this.keys = {}; this.vel = new T.Vector2(); this.fade = 0; this.fadeDir = 0; this.pending = null; this.ready = false;
      this.prevBtn = []; this.target = null; this.targetPoint = new T.Vector3(); this.vig = 0; this.z = 0; this.zShow = 0; this.spotIdx = 0;
      this._q = new T.Quaternion(); this._f = new T.Vector3(); this._o = new T.Vector3(); this._e = new T.Euler(); this._ray = new T.Raycaster(); this._ndc = new T.Vector2();
      this.cam = document.getElementById('cam');
      const isConfirm = (c) => c === 'Enter' || c === 'Space' || c === 'NumpadEnter' || c === 'KeyE';
      window.addEventListener('keydown', (e) => {
        this.keys[e.code] = true; this.lastKey = e.code + (e.key ? ' / ' + e.key : '');
        if (!this.ready || e.repeat) return;
        if (isConfirm(e.code)) this.confirm();
        if (e.code === 'KeyN' || e.code === 'PageDown' || e.key === 'MediaTrackNext' || e.code === 'MediaTrackNext') this.step(1);
        if (e.code === 'KeyP' || e.code === 'PageUp' || e.key === 'MediaTrackPrevious' || e.code === 'MediaTrackPrevious') this.step(-1);
        if (e.code === 'KeyL') this.toggleMood();
        if (e.code === 'KeyV' && V.voice) V.voice.start();          // hold V and speak
        if (e.key === 'AudioVolumeUp') this.step(1);
        if (e.key === 'AudioVolumeDown') this.step(-1);
        if (/^Arrow|Space|PageUp|PageDown/.test(e.code)) e.preventDefault();
      });
      window.addEventListener('keyup', (e) => { this.keys[e.code] = false; if (e.code === 'KeyV' && V.voice) V.voice.stop(); });
      window.addEventListener('blur', () => (this.keys = {}));
      window.addEventListener('click', (e) => { if (this.ready && this.el.sceneEl.is('vr-mode') && !e.target.closest('#hud')) this.confirm(); });
      this.touchUI = 'ontouchstart' in window || navigator.maxTouchPoints > 0 || /[?&]touch/.test(location.search);
      if (this.touchUI) document.body.classList.add('touch');
      const sceneEl = this.el.sceneEl;
      sceneEl.addEventListener('enter-vr', () => document.body.classList.add('vr'));
      sceneEl.addEventListener('exit-vr', () => document.body.classList.remove('vr'));
      sceneEl.addEventListener('villa-ready', () => this.setup(), { once: true });
      V.nav = this;
    },

    /* ---------------- walkable plan ---------------- */
    prepPlan() {
      const L = V.layout, LZ = L.levelsZ || L.levels.map((l) => l.z);
      this.LZ = LZ; this.G = V.grid;
      if (this.G) return;                      // the computed heightfield replaces walk areas and collision boxes
      // surfaces: {r:[x0,y0,x1,y1], z(x,y)} ; walk rects carry a level (its floor height) or an explicit height
      this.surf = L.walk.map((w) => { const z = w.length > 5 ? w[5] : LZ[w[0]]; return { r: w.slice(1, 5), lv: w[0], z: () => z }; });
      L.ramps.forEach((rp) => {
        const [x0, y0, x1, y1] = rp.r, ax = rp.axis.replace('-', ''), neg = rp.axis[0] === '-';
        this.surf.push({ r: rp.r, ramp: true, z: (x, y) => {
          let t = ax === 'x' ? (x - x0) / (x1 - x0) : (y - y0) / (y1 - y0); t = Math.min(1, Math.max(0, neg ? 1 - t : t));
          return rp.z0 + (rp.z1 - rp.z0) * t;
        } });
      });
      this.blocks = L.block.map((b) => ({ lv: b[0], z: LZ[b[0]], r: b.slice(1) }));
    },
    surfaceAt(x, y, zNear) {       // best surface height near zNear at (x, y), or null
      const G = this.G;
      if (G) {
        const i = Math.floor((x - G.x0) / G.cell), j = Math.floor((y - G.y0) / G.cell);
        if (i < 0 || j < 0 || i >= G.nx || j >= G.ny) return null;
        let best = null, bd = 1e9; const c = j * G.nx + i;
        for (let k = 0; k < G.k; k++) {
          const v = G.H[k * G.n + c]; if (!v) continue;
          const h = v / 1000 - G.offset, d = Math.abs(h - zNear);
          if (d <= .32 && d < bd) { bd = d; best = h; }
        }
        return best;
      }
      let best = null;
      for (const s of this.surf) {
        const r = s.r; if (x < r[0] || x > r[2] || y < r[1] || y > r[3]) continue;
        const z = s.z(x, y);      // highest surface within a step: lets you climb onto steps that sit over the garden
        if (Math.abs(z - zNear) <= STEP && (best === null || z > best)) best = z;
      }
      return best;
    },
    blocked(x, y, z) {
      for (const b of this.blocks) {
        if (b.lv !== this.levelOf(z)) continue;      // obstacles belong to one floor only (the porch is just 0.45 m above the garden)
        const r = b.r; if (x > r[0] - R && x < r[2] + R && y > r[1] - R && y < r[3] + R) return true;
      }
      return false;
    },
    standable(x, y, zNear) {       // returns the height if a body can stand here
      if (this.G) return this.surfaceAt(x, y, zNear);      // body radius is already built into the grid
      const z = this.surfaceAt(x, y, zNear); if (z === null) return null;
      for (let k = 0; k < 8; k++) {
        const a = (k / 8) * Math.PI * 2, px = x + Math.cos(a) * R, py = y + Math.sin(a) * R;
        if (this.surfaceAt(px, py, z) === null) return null;
      }
      return this.blocked(x, y, z) ? null : z;
    },
    sight(x0, y0, x1, y1, z) {     // 2D line of sight across walkable floor (walls are the gaps between walk areas)
      const G = this.G;
      if (G) {                     // eye-height see-through bits per floor
        const bit = 1 << this.levelOf(z), n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) / (G.cell * .7));
        for (let s = 1; s < n; s++) {
          const t = s / n, i = Math.floor((x0 + (x1 - x0) * t - G.x0) / G.cell), j = Math.floor((y0 + (y1 - y0) * t - G.y0) / G.cell);
          if (i < 0 || j < 0 || i >= G.nx || j >= G.ny || !(G.SEE[j * G.nx + i] & bit)) return false;
        }
        return true;
      }
      const n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) / .18);
      for (let i = 1; i < n; i++) { const t = i / n; if (this.surfaceAt(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z) === null) return false; }
      return true;
    },
    levelOf(z) { let bi = 0, bd = 1e9; this.LZ.forEach((lz, i) => { const d = Math.abs(lz - z); if (d < bd) { bd = d; bi = i; } }); return bi; },

    setup() {
      this.prepPlan();
      const sceneEl = this.el.sceneEl, cam = this.cam.object3D;
      const ov = (geo, mat, z, order) => { const m = new T.Mesh(geo, mat); m.position.z = z; m.renderOrder = order; m.frustumCulled = false; cam.add(m); return m; };
      const base = { transparent: true, depthTest: false, depthWrite: false, fog: false, toneMapped: false };
      this.fadeMat = new T.MeshBasicMaterial({ ...base, color: 0x120c08, opacity: 1 }); this.fade = 1; this.fadeDir = -1;
      this.fadeMesh = ov(new T.PlaneGeometry(3, 3), this.fadeMat, -.2, 1000);
      this.vigMat = new T.MeshBasicMaterial({ ...base, map: radial(.5, 1, .92), opacity: 0 }); this.vigMesh = ov(new T.PlaneGeometry(.9, .9), this.vigMat, -.25, 999); this.vigMesh.visible = false;
      this.retMat = new T.MeshBasicMaterial({ ...base, color: 0xffffff, opacity: .85 }); this.ret = ov(new T.RingGeometry(.007, .011, 32), this.retMat, -1, 998);
      // teleport rings
      this.markers = new T.Group(); this.markers.userData.noProbe = true; this.hits = []; const beam = beamTex();
      const floorName = (lv) => (V.layout.levels[lv] || {}).name || '';
      this.spots = V.layout.spots.map((s, i) => {
        const z = this.LZ[s.lv], g = new T.Group(); g.position.copy(V.B(s.x, s.y, z));
        const ringMat = new T.MeshBasicMaterial({ color: 0xF1D7AE, transparent: true, opacity: .9, depthWrite: false, toneMapped: false });
        const ring = new T.Mesh(new T.RingGeometry(.3, .36, 48).rotateX(-Math.PI / 2), ringMat); ring.position.y = .03;
        const disc = new T.Mesh(new T.CircleGeometry(.3, 40).rotateX(-Math.PI / 2), new T.MeshBasicMaterial({ color: 0xF1D7AE, transparent: true, opacity: .14, depthWrite: false, toneMapped: false })); disc.position.y = .028;
        const bm = new T.MeshBasicMaterial({ map: beam, color: 0xF1D7AE, transparent: true, opacity: .08, depthWrite: false, side: T.DoubleSide, toneMapped: false });
        const bc = new T.Mesh(new T.CylinderGeometry(.16, .3, 1.3, 24, 1, true), bm); bc.position.y = .66;
        const sp = new T.Sprite(new T.SpriteMaterial({ map: label(s.name), transparent: true, depthWrite: false, toneMapped: false }));
        sp.scale.set(.8, .25, 1); sp.position.y = 1.5;
        const inv = new T.MeshBasicMaterial({ visible: false });
        const hitDisc = new T.Mesh(new T.CircleGeometry(.6, 20).rotateX(-Math.PI / 2), inv); hitDisc.position.y = .04;
        const hitPole = new T.Mesh(new T.CylinderGeometry(.22, .22, 1.6, 10), inv); hitPole.position.y = .8;
        [hitDisc, hitPole, sp].forEach((h) => { h.userData = { t: 'spot', i }; this.hits.push(h); });
        g.add(disc, ring, bc, sp, hitDisc, hitPole); this.markers.add(g);
        g.userData = { ring, ringMat, beamMat: bm, sp, s, floor: floorName(s.lv) };
        return g;
      });
      // the lift: on each floor, badges for the other floors beside the lift door
      this.acts = [];
      const lift = V.layout.lift;
      if (lift) {
        lift.levels.forEach((lv) => lift.levels.forEach((to, k) => {
          if (to === lv) return;
          const sp = new T.Sprite(new T.SpriteMaterial({ map: liftIcon(lift.labels[k]), transparent: true, depthWrite: false, toneMapped: false }));
          const n = lift.levels.indexOf(to) - (lift.levels.indexOf(to) > lift.levels.indexOf(lv) ? 1 : 0);
          sp.position.copy(V.B(lift.x + .12, lift.y + lift.badgeDy, this.LZ[lv] + 1.75 - n * .3)); sp.scale.setScalar(.24);
          sp.userData = { t: 'act', i: this.acts.length }; this.markers.add(sp); this.hits.push(sp);
          this.acts.push({ kind: 'lift', lv, to, sp, label: 'Lift to ' + (V.layout.levels[to] || {}).name, size: .24 });
        }));
      }
      const chair = seatIcon();
      (V.layout.seats || []).forEach((s) => {
        const sp = new T.Sprite(new T.SpriteMaterial({ map: chair, transparent: true, depthWrite: false, toneMapped: false }));
        sp.position.copy(V.B(s.x, s.y, s.z + s.h + .45)); sp.scale.setScalar(.22);
        sp.userData = { t: 'act', i: this.acts.length }; this.markers.add(sp); this.hits.push(sp);
        this.acts.push({ kind: 'seat', lv: this.levelOf(s.z), s, sp, label: 'Sit · ' + s.name, size: .22 });
      });
      const standBtn = document.getElementById('stand'); if (standBtn) standBtn.onclick = (e) => { e.stopPropagation(); this.stand(); };
      this.hoverC = cnv(512, 160); this.hoverT = ctex(this.hoverC); this.hoverText = '';
      this.hover = new T.Sprite(new T.SpriteMaterial({ map: this.hoverT, transparent: true, depthWrite: false, depthTest: false, toneMapped: false }));
      this.hover.scale.set(.8, .25, 1); this.hover.renderOrder = 997; this.hover.visible = false; this.markers.add(this.hover);
      sceneEl.object3D.add(this.markers);
      this._ray.camera = this.cam.getObject3D('camera');
      this.setupHUD(); this.setupTouch(sceneEl);
      if (V.Q.debug) { this.dbg = document.createElement('pre'); this.dbg.id = 'dbg'; document.body.appendChild(this.dbg); }
      const qs = new URLSearchParams(location.search), want = qs.get('spot');
      const startI = Math.max(0, want ? V.layout.spots.findIndex((s) => s.name.toLowerCase() === want.toLowerCase()) : V.layout.spots.findIndex((s) => s.start));
      this.place(startI);
      this.ready = true; document.body.classList.add('ready'); sceneEl.emit('nav-ready');
    },

    toggleMood() {
      if (this.moodBusy || this.pending) return;
      const next = V.mood === 'day' ? 'night' : 'day'; this.moodBusy = true;
      this.pending = { t: 'mood', mood: next }; this.fadeDir = 1;        // switch behind a short fade
    },
    setupHUD() {
      const mb = document.getElementById('mood');
      if (mb) mb.onclick = (e) => { e.stopPropagation(); this.toggleMood(); };
      this.el.sceneEl.addEventListener('mood', (e) => { const t = document.getElementById('moodTxt'); if (t) t.textContent = e.detail.mood === 'day' ? 'Day' : 'Evening'; });
      if (V.Q.debug) document.body.classList.add('debugging');
      const nav = document.getElementById('rooms'); if (!nav) return;
      let lastLv = -1; this.chips = [];
      V.layout.spots.forEach((s, i) => {
        if (s.lv !== lastLv && s.lv > 0) {
          const f = document.createElement('span'); f.className = 'fl'; f.textContent = { 1: 'Ground', 2: 'First', 3: 'Second' }[s.lv] || ''; nav.appendChild(f); lastLv = s.lv;
        }
        const b = document.createElement('button'); b.textContent = s.name; b.onclick = (e) => { e.stopPropagation(); this.go(i); };
        nav.appendChild(b); this.chips.push(b);
      });
      const hint = document.getElementById('hint');
      if (hint && this.touchUI) hint.textContent = 'Tap VR, put the phone in the headset · remote stick to walk · button to go where you look · hold button 3 and say “go to the pool”';
      else if (hint && V.voice && V.voice.supported) hint.textContent += ' · hold V and say “go to the kitchen”';
      const mic = document.getElementById('mic');
      if (mic && V.voice && V.voice.supported) {
        mic.onclick = (e) => { e.stopPropagation(); document.body.classList.contains('listening') ? V.voice.stop() : V.voice.start(); };
        document.body.classList.add('voice');
        if (this.touchUI) V.voice.primeMic();               // ask for the microphone now: the prompt cannot show inside the headset
      }
    },
    setupTouch(sceneEl) {
      const cv = sceneEl.canvas; let down = null; cv.style.touchAction = 'none';
      cv.addEventListener('pointerdown', (e) => { down = { x: e.clientX, y: e.clientY, t: performance.now(), id: e.pointerId }; });
      cv.addEventListener('pointerup', (e) => {
        if (!down || e.pointerId !== down.id) return;
        const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y), dt = performance.now() - down.t; down = null;
        if (moved < 12 && dt < 400) this.tap(e.clientX, e.clientY);
      });
    },

    /* ---------------- picking ---------------- */
    visibleHit(ud) { return ud.t === 'spot' ? this.spots[ud.i].visible : this.acts[ud.i].sp.visible; },
    tap(x, y) {
      if (this.fadeDir !== 0 || this.el.sceneEl.is('vr-mode')) return;
      const r = this.el.sceneEl.canvas.getBoundingClientRect();
      this._ndc.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
      this._ray.setFromCamera(this._ndc, this._ray.camera); this._ray.far = 30;
      for (const h of this._ray.intersectObjects(this.hits, false)) { if (this.visibleHit(h.object.userData)) { this.activate(h.object.userData); return; } }
    },
    confirm() { if (this.target) this.activate(this.target); else if (this.seated) this.stand(); },
    activate(ud) {
      if (ud.t === 'spot') return this.go(ud.i);
      const a = this.acts[ud.i];
      if (a.kind === 'lift' && !this.pending) { this.pending = { t: 'lift', to: a.to }; this.fadeDir = 1; }
      if (a.kind === 'seat' && !this.pending) { this.pending = { t: 'sit', s: a.s }; this.fadeDir = 1; }
    },
    go(i) { if (!this.pending && V.layout.spots[i]) { this.pending = { t: 'spot', i }; this.fadeDir = 1; } },
    stand() { if (!this.pending && this.seated) { this.pending = { t: 'stand' }; this.fadeDir = 1; } },
    setSeated(s) { this.seated = s; this.seatT = performance.now(); document.body.classList.toggle('seated', !!s); },
    sitDown(s) {         // eyes at seated height over the seat, facing the way the seat faces
      const yaw = Math.atan2(-s.fx, s.fy), eye = s.z + s.h + .72 - 1.6;
      this.setPos(s.x, s.y, eye, yaw); this.setSeated(s);
      const lc = this.cam.components['look-controls'];
      if (lc && !this.el.sceneEl.is('vr-mode')) { lc.pitchObject.rotation.x = -.08; lc.yawObject.rotation.y = 0; this.el.object3D.rotation.y = yaw; }
      this.announce(s.name, 'Seated');
    },
    standUp() {          // step out in front of the seat onto open floor
      const s = this.seated; if (!s) return;
      let tx = s.x + s.fx * .7, ty = s.y + s.fy * .7, z = this.standable(tx, ty, s.z);
      if (z === null) search: for (let r = .1; r < 1.6; r += .1) for (let a = 0; a < 360; a += 20) {
        const x = s.x + s.fx * .7 + r * Math.cos(a * Math.PI / 180), y = s.y + s.fy * .7 + r * Math.sin(a * Math.PI / 180);
        if ((z = this.standable(x, y, s.z)) !== null) { tx = x; ty = y; break search; }
      }
      this.setPos(tx, ty, z === null ? s.z : z, Math.atan2(-s.fx, s.fy));
      this.announce(this.nearestSpotName(), (V.layout.levels[this.levelOf(this.z)] || {}).name);
    },
    step(d) { const n = V.layout.spots.length; this.go(((this.spotIdx + d) % n + n) % n); },

    /* ---------------- moving the rig ---------------- */
    camYaw() { return this._e.setFromQuaternion(this.cam.object3D.quaternion, 'YXZ').y; },
    face(lx, ly, x, y) { return Math.atan2(-(lx - x), (ly - y)); },      // yaw (three) to look from (x,y) toward (lx,ly) in plan coords
    setPos(x, y, z, yaw) {
      const rig = this.el.object3D; this.px = x; this.py = y; this.z = z; this.zShow = z;
      rig.position.copy(V.B(x, y, z)); rig.rotation.y = yaw - this.camYaw(); this.vel.set(0, 0);
      if (this.seated) this.setSeated(null);
    },
    place(i) {
      const s = V.layout.spots[i]; this.spotIdx = i;
      this.setPos(s.x, s.y, this.LZ[s.lv], this.face(s.lx, s.ly, s.x, s.y));
      const lz = s.lz == null ? 1.4 : s.lz, look = Math.atan2(lz - 1.6, Math.hypot(s.lx - s.x, s.ly - s.y));
      const lc = this.cam.components['look-controls'];
      if (lc && !this.el.sceneEl.is('vr-mode')) { lc.pitchObject.rotation.x = look; lc.yawObject.rotation.y = 0; this.el.object3D.rotation.y = this.face(s.lx, s.ly, s.x, s.y); }
      this.chips && this.chips.forEach((c, k) => c.setAttribute('aria-current', k === i));
      this.announce(s.name, (V.layout.levels[s.lv] || {}).name);
    },
    announce(room, floor) {
      const wr = document.getElementById('wroom'), wf = document.getElementById('wfloor');
      if (wr) wr.textContent = room; if (wf) wf.textContent = floor || '';
    },
    applyPending(p) {
      if (p.t === 'mood') { this.holdFade = true; V.setMood(p.mood, this.el.sceneEl).finally(() => { this.moodBusy = false; this.holdFade = false; }); return; }
      if (p.t === 'spot') this.place(p.i);
      else if (p.t === 'sit') this.sitDown(p.s);
      else if (p.t === 'stand') this.standUp();
      else if (p.t === 'lift') {
        const L = V.layout.lift, z = this.LZ[p.to];
        let tx = L.x + L.out, ty = L.y;
        if (this.standable(tx, ty, z) === null) {                // search outward for open floor in front of the doors
          search: for (let r = .1; r < 2; r += .1) for (let a = 0; a < 360; a += 15) {
            const x = L.x + L.out + r * Math.cos(a * Math.PI / 180), y = L.y + r * Math.sin(a * Math.PI / 180);
            if (Math.sign(x - L.x) === Math.sign(L.out) && this.standable(x, y, z) !== null) { tx = x; ty = y; break search; }
          }
        }
        this.setPos(tx, ty, z, -Math.PI / 2 * Math.sign(L.out));     // step out of the lift facing away from it
        this.announce('Lift lobby', (V.layout.levels[p.to] || {}).name);
      }
    },

    readInput() {
      const k = this.keys; let ix = 0, iz = 0; const btn = [];
      if (k.KeyD || k.ArrowRight) ix += 1; if (k.KeyA || k.ArrowLeft) ix -= 1;
      if (k.KeyW || k.ArrowUp) iz += 1; if (k.KeyS || k.ArrowDown) iz -= 1;
      const pads = navigator.getGamepads ? navigator.getGamepads() : []; this.padInfo = '';
      for (const p of pads) {
        if (!p || !p.connected) continue;
        let ax = p.axes[0] || 0, ay = p.axes[1] || 0;
        if (p.mapping !== 'standard' && p.axes.length >= 4 && Math.hypot(p.axes[2], p.axes[3]) > Math.hypot(ax, ay)) { ax = p.axes[2]; ay = p.axes[3]; }
        if (Math.hypot(ax, ay) > DEAD) { ix += ax; iz -= ay; }
        const b = p.buttons;
        if (b[12] && b[12].pressed) iz += 1; if (b[13] && b[13].pressed) iz -= 1; if (b[14] && b[14].pressed) ix -= 1; if (b[15] && b[15].pressed) ix += 1;
        b.forEach((x, j) => { if (x && x.pressed) btn[j] = true; });
        this.padInfo += `pad ${p.index} "${p.id.slice(0, 40)}" map=${p.mapping || '-'} axes=[${Array.from(p.axes, (v) => v.toFixed(2))}] btn=[${Array.from(b, (x, j) => (x.pressed ? j : '')).join('')}]\n`;
      }
      const len = Math.hypot(ix, iz); if (len > 1) { ix /= len; iz /= len; }
      return { ix, iz, btn };
    },

    tick(time, dtMs) {
      if (!this.ready) return;
      const dt = Math.min(dtMs / 1000, .05), rig = this.el.object3D, cam = this.cam.object3D, vr = this.el.sceneEl.is('vr-mode');
      const inp = this.readInput(), pb = this.prevBtn;
      if (inp.btn[0] && !pb[0]) this.confirm();
      if ((inp.btn[1] && !pb[1]) || (inp.btn[5] && !pb[5])) this.step(1);
      if ((inp.btn[2] && !pb[2]) || (inp.btn[4] && !pb[4])) this.step(-1);
      // button 3 (Y): hold to speak a command (day / evening is by voice, not a button)
      const talk = V.voice && V.voice.supported;
      if (inp.btn[3] && !pb[3] && talk) V.voice.start();
      if (!inp.btn[3] && pb[3] && talk) V.voice.stop();
      if (V.voice) V.voice.tick();
      this.prevBtn = inp.btn;

      // walk relative to gaze on the floor plane; plan coords: x = three x, y = -three z
      cam.getWorldQuaternion(this._q); this._f.set(0, 0, -1).applyQuaternion(this._q); this._f.y = 0;
      if (this._f.lengthSq() < 1e-4) this._f.set(-Math.sin(rig.rotation.y), 0, -Math.cos(rig.rotation.y));
      this._f.normalize();
      const fx = this._f.x, fy = -this._f.z, rx = fy, ry = -fx;           // forward and right in plan coords
      const still = !!this.seated;
      if (still && !this.pending && performance.now() - this.seatT > 700 && Math.hypot(inp.ix, inp.iz) > .6) this.stand();
      const tx = still ? 0 : (fx * inp.iz + rx * inp.ix) * SPEED, ty = still ? 0 : (fy * inp.iz + ry * inp.ix) * SPEED;
      const kk = 1 - Math.exp(-dt / .2);
      this.vel.x += (tx - this.vel.x) * kk; this.vel.y += (ty - this.vel.y) * kk;
      if (Math.hypot(this.vel.x, this.vel.y) > .01 && this.fadeDir === 0) {
        const nx = this.px + this.vel.x * dt, ny = this.py + this.vel.y * dt;
        let z = this.standable(nx, ny, this.z);
        if (z !== null) { this.px = nx; this.py = ny; this.z = z; }
        else if ((z = this.standable(nx, this.py, this.z)) !== null) { this.px = nx; this.z = z; this.vel.y = 0; }
        else if ((z = this.standable(this.px, ny, this.z)) !== null) { this.py = ny; this.z = z; this.vel.x = 0; }
        else this.vel.set(0, 0);
        const lv = this.levelOf(this.z);
        if (lv !== this.lastLv) { this.lastLv = lv; this.announce(this.nearestSpotName(), (V.layout.levels[lv] || {}).name); }
      }
      this.zShow += (this.z - this.zShow) * (1 - Math.exp(-dt / .12));      // smooth the steps
      rig.position.set(this.px, this.zShow, -this.py);
      const sp = this.vel.length();
      this.vig += ((sp / SPEED) - this.vig) * (1 - Math.exp(-dt / .25));
      this.vigMat.opacity = vr ? Math.min(.45, this.vig * .45) : 0; this.vigMesh.visible = this.vigMat.opacity > .02;
      if (!vr) {     // a gentle head bob on a flat screen
        this.bobAmp = (this.bobAmp || 0) + (Math.min(sp / SPEED, 1) - (this.bobAmp || 0)) * (1 - Math.exp(-dt / .25));
        this.bob = (this.bob || 0) + sp * dt * (Math.PI * 2 / .72);
        cam.position.set(Math.sin(this.bob * .5) * .008 * this.bobAmp, 1.6 + Math.sin(this.bob) * .014 * this.bobAmp, 0);
      }
      // fade
      if (this.fadeDir === 1) { this.fade = Math.min(1, this.fade + dt / .16); if (this.fade >= 1) { this.applyPending(this.pending); this.pending = null; this.fadeDir = -1; } }
      else if (this.fadeDir === -1 && !this.holdFade) { this.fade = Math.max(0, this.fade - dt / .35); if (this.fade <= 0) this.fadeDir = 0; }
      this.fadeMat.opacity = this.fade; this.fadeMesh.visible = this.fade > .002;

      // which rings and badges show: same floor, in sight, not where you stand (re-checked a few times a second)
      this._vis = (this._vis || 0) + dt;
      if (this._vis > .2) {
        this._vis = 0; const lv = this.levelOf(this.z);
        this.spots.forEach((g) => {
          const s = g.userData.s, d = Math.hypot(this.px - s.x, this.py - s.y);
          g.visible = !this.seated && s.lv === lv && d > 1 && d < 16 && this.sight(this.px, this.py, s.x, s.y, this.z);
        });
        this.acts.forEach((a) => {
          if (a.kind === 'seat') {                       // nearby, same floor, in sight of the open floor in front of it
            const s = a.s, d = Math.hypot(this.px - s.x, this.py - s.y);
            a.sp.visible = !this.seated && a.lv === lv && d > .5 && d < 5 && this.sight(this.px, this.py, s.x + s.fx * .6, s.y + s.fy * .6, this.z);
            return;
          }
          const L = V.layout.lift; a.sp.visible = !this.seated && a.lv === lv && Math.hypot(this.px - L.x, this.py - L.y) < 5;
        });
      }
      // gaze picking
      cam.getWorldPosition(this._o); cam.getWorldQuaternion(this._q); this._f.set(0, 0, -1).applyQuaternion(this._q);
      this._ray.set(this._o, this._f); this._ray.far = 18; let tgt = null;
      if (this.fadeDir === 0) for (const h of this._ray.intersectObjects(this.hits, false)) { if (this.visibleHit(h.object.userData)) { tgt = h.object.userData; this.targetPoint.copy(h.point); break; } }
      this.target = tgt;
      const tt = time / 1000;
      this.spots.forEach((g, i) => {
        const u = g.userData, on = tgt && tgt.t === 'spot' && tgt.i === i;
        u.ring.scale.setScalar(on ? 1.22 : 1 + .05 * Math.sin(tt * 3 + i)); u.ringMat.opacity = on ? 1 : .7;
        u.beamMat.opacity = on ? .3 : .08; u.sp.scale.set(on ? 1 : .8, on ? .31 : .25, 1);
      });
      let hover = null;
      this.acts.forEach((a, i) => { const on = tgt && tgt.t === 'act' && tgt.i === i; a.sp.scale.setScalar(a.size * (on ? 1.35 : 1)); if (on) hover = a; });
      if (hover) {
        if (this.hoverText !== hover.label) { this.hoverText = hover.label; drawLabel(this.hoverC, hover.label); this.hoverT.needsUpdate = true; }
        this.hover.position.copy(hover.sp.position); this.hover.position.y += .3; this.hover.visible = true;
      } else this.hover.visible = false;
      this.ret.visible = vr; this.retMat.color.set(tgt ? 0xF1C98A : 0xffffff); this.ret.scale.setScalar(tgt ? 1.8 : 1);

      if (this.dbg && ((this._dt = (this._dt || 0) + dt) > .25)) {
        this._dt = 0; const inf = this.el.sceneEl.renderer.info;
        this.dbg.textContent = `fps ${(1 / dt).toFixed(0)}  calls ${inf.render.calls}  tris ${inf.render.triangles}  tex ${inf.memory.textures}\nplan ${this.px.toFixed(2)}, ${this.py.toFixed(2)}  z ${this.z.toFixed(2)}  lv ${this.levelOf(this.z)}  target ${tgt ? tgt.t + ':' + tgt.i : '-'}\n${V.Q.hq ? 'HIGH' : 'standard'} · ${(V.Q.gpu || '').replace('ANGLE (', '').slice(0, 46)}${new URLSearchParams(location.search).get('why') ? ' · fell back: ' + new URLSearchParams(location.search).get('why') : ''}\nkey ${this.lastKey || '-'}\n${this.padInfo || 'no gamepad'}`;
      }
    },
    nearestSpotName() {
      let best = '', bd = 1e9; const lv = this.levelOf(this.z);
      V.layout.spots.forEach((s) => { if (s.lv !== lv) return; const d = Math.hypot(s.x - this.px, s.y - this.py); if (d < bd) { bd = d; best = s.name; } });
      return best;
    },
  });
})();
