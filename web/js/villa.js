/* Villa loader: zones (GLB + baked lightmap), materials rebuilt from the glTF extras written by blender/lib.py,
   box-projected reflection probes for glossy surfaces (marble, glass, water, lacquer), sky, and small living
   details (leaves in the wind, water shimmer, drifting clouds).
   Blender plan coordinates (x east, y north, z up) map to three as (x, z, -y). */
(function () {
  const T = AFRAME.THREE;
  const V = (window.V = window.V || {});
  const qs = new URLSearchParams(location.search);
  const mobile = /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent) || qs.get('q') === 'low';        // ?q=low|high also forces the tier
  V.Q = { full: qs.has('full'), mobile, debug: qs.has('debug'), probeSize: mobile ? 128 : 256, aniso: mobile ? 4 : 8, noProbes: qs.has('noprobes'), hq: false, gpu: '' };
  V.B = (x, y, z = 0) => new T.Vector3(x, z, -y);
  V.U = { time: { value: 0 } };
  const progress = (m, f) => V.onProgress && V.onProgress(m, f);

  /* ---------------- textures ---------------- */
  const texLoader = new T.TextureLoader(), texCache = {};
  function tex(path, srgb = true, repeat = true) {
    const hqName = V.hqTex && path.split('/').pop().replace(/\.\w+$/, '');
    if (hqName && V.hqTex[hqName]) return V.hqTex[hqName];
    if (texCache[path]) return texCache[path];
    const t = texLoader.load(path);
    t.flipY = false; t.colorSpace = srgb ? T.SRGBColorSpace : T.NoColorSpace;
    if (repeat) t.wrapS = t.wrapT = T.RepeatWrapping;
    t.anisotropy = V.Q.aniso;
    return (texCache[path] = t);
  }
  /* quality tier: strong phone GPUs (and desktops) get full-resolution lightmaps, 2K textures and relief maps, all as
     GPU-compressed KTX2 (Basis UASTC -> ASTC / BC7). ?q=high or ?q=low overrides. */
  const TRANSCODER = 'https://cdn.jsdelivr.net/npm/three@0.173.0/examples/jsm/libs/basis/';
  function strongGPU(gpu) {
    if (!mobile) return true;
    if (/Apple|Immortalis|Xclipse/i.test(gpu)) return true;
    const a = /Adreno\D*(\d{3})/i.exec(gpu); if (a) { const n = +a[1]; return (n >= 640 && n < 700) || n >= 720; }
    const m = /Mali-G(\d+)/i.exec(gpu); if (m) { const n = +m[1]; return (n >= 76 && n < 100) || n >= 710; }
    return false;
  }
  function fallBack(why) {
    if (qs.get('q') === 'low') return;                           // already at the standard tier
    console.warn('[villa] falling back to standard quality:', why);
    const u = new URL(location.href); u.searchParams.set('q', 'low'); u.searchParams.set('why', why); location.replace(u.toString());
  }
  V.checkGPU = (r) => {
    const gl = r.getContext(); let e, oom = false;
    while ((e = gl.getError()) !== gl.NO_ERROR) { if (e === gl.OUT_OF_MEMORY) oom = true; }
    if (oom && V.Q.hq) fallBack('gpu-memory');
  };
  async function pickTier(sceneEl) {
    const r = sceneEl.renderer || await new Promise((res) => sceneEl.addEventListener('renderstart', () => res(sceneEl.renderer), { once: true }));
    r.domElement.addEventListener('webglcontextlost', (e) => { e.preventDefault(); if (V.Q.hq) fallBack('context-lost'); });
    const gl = r.getContext(), ext = gl.getExtension('WEBGL_debug_renderer_info');
    V.Q.gpu = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
    const want = qs.get('q');
    V.Q.hq = !!T.KTX2Loader && want !== 'low' && (want === 'high' || strongGPU(V.Q.gpu));
    if (V.Q.hq) {
      V.Q.aniso = Math.min(16, r.capabilities.getMaxAnisotropy()); V.Q.probeSize = mobile ? 128 : 256;     // cube probes are half-float: keep phones lean
      V.k2 = new T.KTX2Loader().setTranscoderPath(TRANSCODER).setWorkerLimit(4).detectSupport(r);
    } else if (mobile) {                                    // weaker phones: keep the canvas modest
      sceneEl.maxCanvasSize = { width: 1800, height: 1800 }; sceneEl.resize && sceneEl.resize();
    }
    // headset: render at (or above) the panel's native resolution on strong GPUs
    const xrs = parseFloat(qs.get('xrs') || (V.Q.hq && !mobile ? '1.3' : '1'));
    if (r.xr && r.xr.setFramebufferScaleFactor) r.xr.setFramebufferScaleFactor(xrs);
    console.log('[villa] gpu', V.Q.gpu, '| tier', V.Q.hq ? 'high' : 'standard', '| aniso', V.Q.aniso, '| xr scale', xrs);
    return r;
  }
  async function preloadHQ() {
    const meta = await fetch('assets/hq/hq.json').then((x) => x.json());
    V.hqMeta = meta; const tx = {}, nor = {};
    await Promise.all([
      ...meta.tex.map(async (n) => { const t = await V.k2.loadAsync('assets/hq/tex/' + n + '.ktx2'); t.wrapS = t.wrapT = T.RepeatWrapping; t.anisotropy = V.Q.aniso; tx[n] = t; }),
      ...meta.relief.map(async (n) => { const t = await V.k2.loadAsync('assets/hq/tex/' + n + '_n.ktx2'); t.wrapS = t.wrapT = T.RepeatWrapping; t.anisotropy = V.Q.aniso; t.colorSpace = T.NoColorSpace; nor[n] = t; }),
    ]);
    V.hqTex = tx; V.hqNor = nor;
  }
  const loadTex = (path, srgb) => new Promise((res, rej) => texLoader.load(path, (t) => { t.flipY = false; t.colorSpace = srgb ? T.SRGBColorSpace : T.NoColorSpace; res(t); }, undefined, rej));

  /* ---------------- shader patches ---------------- */
  // gloss: box-projected cube reflection with a Schlick fresnel, added on top of the unlit + lightmapped colour
  function patchGloss(mat, probe, gloss) {
    mat.envMap = probe.tex; mat.combine = T.AddOperation; mat.reflectivity = 0;
    const box = probe.box3, at = probe.pos;
    mat.userData.gl = { uGloss: { value: gloss }, uBoxMin: { value: box.min.clone() }, uBoxMax: { value: box.max.clone() }, uProbePos: { value: at.clone() } };
    patchSurface(mat);
  }
  /* relief: the tangent frame comes from screen-space derivatives (no tangents in the mesh); the normal map tilts a
     fixed soft key light and darkens cavities, multiplying the baked light, and also bends the gloss reflections. */
  function patchSurface(mat) {
    const d = mat.userData, det = d.det, gl = d.gl;
    if (!det && !gl) return;
    mat.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, gl || { uGloss: { value: 0 }, uBoxMin: { value: new T.Vector3() }, uBoxMax: { value: new T.Vector3() }, uProbePos: { value: new T.Vector3() } }, { uTime: V.U.time });
      if (det) Object.assign(sh.uniforms, { uDet: { value: det.tex }, uRelief: { value: det.s } });
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\nvarying vec3 vWP; varying vec3 vWN;')
        .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWP = (modelMatrix * vec4(transformed, 1.0)).xyz; vWN = normalize(mat3(modelMatrix) * normal);');
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', '#include <common>\nvarying vec3 vWP; varying vec3 vWN; uniform float uGloss; uniform vec3 uBoxMin; uniform vec3 uBoxMax; uniform vec3 uProbePos; uniform float uTime;' +
          (det ? '\nuniform sampler2D uDet; uniform float uRelief;' : ''))
        .replace('#include <aomap_fragment>', `#include <aomap_fragment>
  vec3 Nd = normalize(vWN);
#ifdef USE_DET
  {
    vec3 Ng = gl_FrontFacing ? Nd : -Nd;
    vec3 dp1 = dFdx(vWP), dp2 = dFdy(vWP); vec2 du1 = dFdx(vMapUv), du2 = dFdy(vMapUv);
    vec3 dp2p = cross(dp2, Ng), dp1p = cross(Ng, dp1);
    vec3 Tt = dp2p * du1.x + dp1p * du2.x, Bt = dp2p * du1.y + dp1p * du2.y;
    float im = inversesqrt(max(max(dot(Tt, Tt), dot(Bt, Bt)), 1e-20));
    vec3 nt = texture2D(uDet, vMapUv).xyz * 2.0 - 1.0;
    vec3 Np = normalize(Tt * im * nt.x + Bt * im * nt.y + Ng * max(nt.z, 0.2));
    float sh = 1.0 + dot(Np - Ng, normalize(vec3(0.35, 0.85, 0.4))) * uRelief * 1.6;
    sh *= mix(1.0, clamp(nt.z, 0.0, 1.0), 0.8 * uRelief);
    reflectedLight.indirectDiffuse *= clamp(sh, 0.55, 1.35);
    Nd = gl_FrontFacing ? Np : -Np;
  }
#endif`)
        .replace('#include <envmap_fragment>', `
#ifdef USE_ENVMAP
  vec3 Vd = normalize(vWP - cameraPosition);
  vec3 Nn = Nd;
  #ifdef IS_WATER
    Nn = normalize(Nn + vec3(sin(vWP.x * 3.1 + uTime * 1.3) + sin(vWP.z * 2.3 - uTime * 1.1), 0.0, cos(vWP.z * 2.9 + uTime * 1.2) + sin(vWP.x * 1.7 + uTime * .9)) * 0.035);
  #endif
  vec3 Rr = reflect(Vd, Nn);
  vec3 tA = (uBoxMax - vWP) / Rr, tB = (uBoxMin - vWP) / Rr;
  vec3 tF = max(tA, tB);
  float tHit = min(min(tF.x, tF.y), tF.z);
  vec3 dirP = (vWP + Rr * tHit) - uProbePos;
  vec3 envC = textureCube(envMap, vec3(flipEnvMap * dirP.x, dirP.yz)).rgb;
  float fr = uGloss * (0.04 + 0.96 * pow(1.0 - clamp(dot(-Vd, Nn), 0.0, 1.0), 5.0));
  outgoingLight += envC * fr;
#endif`);
    };
    mat.customProgramCacheKey = () => 'surf' + (gl ? 'g' : '') + (d.water ? 'w' : '') + (det ? 'd' : '');
    mat.defines = Object.assign({}, d.water ? { IS_WATER: '' } : {}, det ? { USE_DET: '' } : {});
    mat.needsUpdate = true;
  }
  // wind in the leaves (garden trees are world-space cards; sway grows with height)
  function patchSway(mat) {
    mat.onBeforeCompile = (sh) => {
      sh.uniforms.uTime = V.U.time;
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nuniform float uTime;')
        .replace('#include <begin_vertex>', `#include <begin_vertex>
  { float h = clamp((position.y - 1.5) * 0.25, 0.0, 1.0);
    transformed.x += sin(uTime * 1.2 + position.x * 0.7 + position.z * 0.5) * 0.06 * h;
    transformed.z += cos(uTime * 0.9 + position.z * 0.6 + position.x * 0.3) * 0.05 * h; }`);
    };
    mat.customProgramCacheKey = () => 'sway';
  }

  /* ---------------- materials from glTF extras ---------------- */
  function srcColor(hex, fallback) { return new T.Color(hex || fallback || '#ffffff'); }
  function buildMaterial(src, zone) {
    const u = src.userData || {}, k = u.k || 'std';
    const map = u.tex ? tex('assets/tex/' + u.tex) : null;
    const side = src.side === T.DoubleSide ? T.DoubleSide : T.FrontSide;
    let m;
    if (k === 'emit') {
      const es = u.es || 1, c = srcColor(u.emit);
      const gain = map ? Math.min(1.6, .5 + es * .6) : Math.min(5, 1 + es * .35);
      m = new T.MeshBasicMaterial({ map, color: c.multiplyScalar(gain), side, toneMapped: true });
    } else if (k === 'glass') {
      m = new T.MeshBasicMaterial({ color: srcColor(u.tint, '#DDE8EE').multiplyScalar(.35), transparent: true, opacity: .14, depthWrite: false, side: T.DoubleSide });
      m.userData.glossWant = .9;
    } else if (k === 'water') {
      m = new T.MeshBasicMaterial({ color: srcColor('#2E7F94'), transparent: true, opacity: .82, depthWrite: false, side: T.DoubleSide });
      m.userData.glossWant = 1; m.userData.water = true;
    } else if (k === 'alpha') {          // garden tree cards: flat sun tone, swaying
      m = new T.MeshBasicMaterial({ map, color: new T.Color('#D1DBC6'), alphaTest: .5, side: T.DoubleSide });
      patchSway(m);
    } else {     // std + cut: lightmapped
      m = new T.MeshBasicMaterial({ map, color: srcColor(u.tint), side: k === 'cut' ? T.DoubleSide : side, alphaTest: k === 'cut' ? .5 : 0 });
      if (zone.light) { m.lightMap = zone.light; m.lightMapIntensity = zone.lmax * Math.PI * (V.exposure || 1); m.userData.zone = zone.name; V.lightMats.push(m); }
      if (u.gloss > 0) m.userData.glossWant = u.gloss;
      const nm = u.tex && V.hqNor && V.hqNor[u.tex.replace(/\.\w+$/, '')];
      if (nm) { m.userData.det = { tex: nm, s: parseFloat(qs.get('relief') || '.7') }; patchSurface(m); }
    }
    m.name = src.name; m.userData.k = k;
    return m;
  }

  /* plants: light baked per vertex in Cycles (custom attributes _lday / _lnight) */
  V.plantMeshes = [];
  function plantMaterial(src, outdoor) {
    const u = src.userData || {};
    const m = new T.MeshBasicMaterial({ map: u.tex ? tex('assets/tex/' + u.tex) : null, color: new T.Color(u.tex ? '#ffffff' : (u.tint || '#ffffff')),
      vertexColors: true, alphaTest: u.k === 'cut' ? .5 : 0, side: T.DoubleSide });
    m.color.multiplyScalar(V.exposure || 1);
    if (outdoor) patchSway(m);
    m.name = src.name; m.userData.k = 'plant';
    return m;
  }
  function takePlants(scene, zn, root) {
    const outdoor = zn === 'ext' || zn === 'site', cache = new Map();
    scene.traverse((o) => {
      if (!o.isMesh) return;
      const g = o.geometry, day = g.getAttribute('_lday'), night = g.getAttribute('_lnight');
      if (!day) return;
      g.setAttribute('color', new T.BufferAttribute(day.array.slice(), day.itemSize));
      if (!cache.has(o.material.name)) cache.set(o.material.name, plantMaterial(o.material, outdoor));
      o.material = cache.get(o.material.name);
      o.matrixAutoUpdate = false; o.updateMatrix();
      V.plantMeshes.push({ mesh: o, zone: zn, light: { day: day.array, night: night ? night.array : day.array } });
    });
    root.add(scene);
  }

  /* walkable heightfield computed from the geometry (blender/navgrid.py) */
  async function loadGrid() {
    const meta = await fetch('assets/nav.json').then((r) => r.json());
    const res = await fetch('assets/nav.bin');
    const buf = await new Response(res.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
    const n = meta.nx * meta.ny;
    return { ...meta, n, H: new Uint16Array(buf, 0, n * meta.k), SEE: new Uint8Array(buf, n * meta.k * 2, n) };
  }

  /* ---------------- loading ---------------- */
  V.lightMats = []; V.mood = 'day';
  const lmaxOf = (z, mood) => (typeof z.lmax === 'object' ? z.lmax[mood] || z.lmax.day : z.lmax) || 1;
  async function loadLight(z, mood) {
    const sfx = mood === 'day' ? '' : '_' + mood, name = z.light.split('/').pop().replace('.jpg', '') + sfx;
    const t = V.Q.hq && V.hqMeta && V.hqMeta.lights.includes(name) ? await V.k2.loadAsync('assets/hq/light/' + name + '.ktx2') : await loadTex(lightPath(z, mood), true);
    t.channel = 1; t.wrapS = t.wrapT = T.ClampToEdgeWrapping; if (!t.isCompressedTexture) t.generateMipmaps = true;
    return t;
  }
  const lightPath = (z, mood) => 'assets/' + z.light.replace('.jpg', (mood === 'day' ? '' : '_' + mood) + (V.Q.mobile && !V.Q.full ? '_m' : '') + '.jpg');
  async function loadVilla(el) {
    progress('Reading the plan', .03);
    await pickTier(el.sceneEl);
    const hqReady = V.Q.hq ? preloadHQ().catch((e) => { console.warn('[villa] hq textures failed, using standard', e); V.Q.hq = false; V.hqTex = V.hqNor = null; }) : null;
    const [scene, layout, grid] = await Promise.all([fetch('assets/scene.json').then((r) => r.json()), fetch('assets/layout.json').then((r) => r.json()), loadGrid()]);
    await hqReady;
    V.layout = layout; V.scene = scene; V.grid = grid;
    const root = new T.Group(); root.name = 'villa';
    const loader = new T.GLTFLoader();
    if (T.DRACOLoader) { const d = new T.DRACOLoader(); d.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.7/'); loader.setDRACOLoader(d); }
    const names = Object.keys(scene.zones); let done = 0;
    V.zones = {};
    await Promise.all(names.map(async (zn) => {
      const z = scene.zones[zn];
      const [g, light, fx, pl] = await Promise.all([loader.loadAsync('assets/' + z.glb), loadLight(z, 'day'),
        z.fx ? loader.loadAsync('assets/' + z.fx) : null, z.plants ? loader.loadAsync('assets/' + z.plants) : null]);
      const zone = { name: zn, light, lmax: lmaxOf(z, 'day'), meshes: [], lights: { day: light }, src: z };
      const mats = new Map();
      const take = (obj) => obj.traverse((o) => {
        if (!o.isMesh) return;
        const key = o.material.name + '|' + (o.material.userData && o.material.userData.k);
        if (!mats.has(key)) mats.set(key, buildMaterial(o.material, zone));
        o.material.dispose && o.material.dispose();
        o.material = mats.get(key);
        o.matrixAutoUpdate = false; o.updateMatrix();
        if (o.material.transparent) o.renderOrder = 5;
        zone.meshes.push(o);
      });
      take(g.scene); root.add(g.scene);
      if (fx) { take(fx.scene); root.add(fx.scene); }
      if (pl) { takePlants(pl.scene, zn, root); pl.scene.traverse((o) => o.isMesh && zone.meshes.push(o)); }
      V.zones[zn] = zone;
      progress('Furnishing ' + ({ ext: 'the garden', gf: 'the ground floor', ff: 'the first floor', sf: 'the second floor' }[zn] || zn), .1 + .7 * (++done / names.length));
    }));
    if (layout.lamps && layout.lamps.length) root.add(V.glows = makeGlows(layout.lamps));
    // sky: tone-mapped HDRI on a big sphere; clouds drift slowly
    const sky = new T.Mesh(new T.SphereGeometry(800, 48, 24), new T.MeshBasicMaterial({ map: await loadTex('assets/sky.jpg', true), side: T.BackSide, depthWrite: false, fog: false, toneMapped: false }));
    sky.material.map.flipY = true; sky.material.map.needsUpdate = true; sky.renderOrder = -10; sky.name = 'sky';
    root.add(sky); V.sky = sky;
    el.setObject3D('villa', root); V.root = root;
    return root;
  }

  function makeGlows(lamps) {
    const c = document.createElement('canvas'); c.width = c.height = 128; const x = c.getContext('2d');
    const g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(.12, 'rgba(255,255,255,.55)'); g.addColorStop(.4, 'rgba(255,255,255,.12)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = g; x.fillRect(0, 0, 128, 128);
    const map = new T.CanvasTexture(c), grp = new T.Group(); grp.userData.noProbe = true; grp.name = 'glows';
    [[0, .45], [1, .9]].forEach(([big, size]) => {              // downlights small, pendants and lamps larger
      const pts = lamps.filter((l) => (l[3] === 'POINT') === !!big);
      if (!pts.length) return;
      const pos = new Float32Array(pts.length * 3), col = new Float32Array(pts.length * 3);
      pts.forEach((l, i) => { const v = V.B(l[0], l[1], l[2]); pos.set([v.x, v.y, v.z], i * 3); col.set([l[4], l[5], l[6]].map((k) => k * .8), i * 3); });
      const geo = new T.BufferGeometry(); geo.setAttribute('position', new T.BufferAttribute(pos, 3)); geo.setAttribute('color', new T.BufferAttribute(col, 3));
      const m = new T.PointsMaterial({ map, size, sizeAttenuation: true, vertexColors: true, transparent: true, depthWrite: false, blending: T.AdditiveBlending, toneMapped: false, opacity: .22 });
      const p = new T.Points(geo, m); p.frustumCulled = false; p.renderOrder = 6; grp.add(p);
    });
    return grp;
  }

  /* ---------------- reflection probes ---------------- */
  function captureProbes(renderer, scene3) {
    const P = (V.layout.probes || []).map((p) => {
      const [x0, y0, z0, x1, y1, z1] = p.box;
      const box3 = new T.Box3(new T.Vector3(Math.min(x0, x1), z0, -Math.max(y0, y1)), new T.Vector3(Math.max(x0, x1), z1, -Math.min(y0, y1)));
      const pos = V.B(p.at[0], p.at[1], p.at[2]);
      return { ...p, box3, pos };
    });
    const gloss = [];
    Object.values(V.zones).forEach((z) => z.meshes.forEach((m) => { if (m.material.userData.glossWant) gloss.push(m); }));
    gloss.forEach((m) => (m.visible = false));                 // glossy surfaces stay out of their own captures
    const hide = []; scene3.traverse((o) => { if (o.userData.noProbe && o.visible) { o.visible = false; hide.push(o); } });
    P.forEach((p) => {
      const rt = new T.WebGLCubeRenderTarget(V.Q.probeSize, { type: T.HalfFloatType, generateMipmaps: true, minFilter: T.LinearMipmapLinearFilter });
      const cam = new T.CubeCamera(.05, 400, rt); cam.position.copy(p.pos); scene3.add(cam); cam.update(renderer, scene3); scene3.remove(cam);
      p.tex = rt.texture; p.cam = cam;
    });
    gloss.forEach((m) => (m.visible = true)); hide.forEach((o) => (o.visible = true));
    // assign: split each glossy mesh's triangles by the probe box they fall in (smallest containing box, else nearest)
    const c = new T.Vector3(), a = new T.Vector3(), b = new T.Vector3(), d = new T.Vector3();
    const vol = (p) => { const s = p.box3.getSize(new T.Vector3()); return s.x * s.y * s.z; };
    const pick = (pt) => {
      let best = null, bv = Infinity;
      for (const p of P) if (p.box3.containsPoint(pt)) { const v = vol(p); if (v < bv) { bv = v; best = p; } }
      if (best) return best;
      let bd = Infinity; for (const p of P) { const dd = p.box3.distanceToPoint(pt); if (dd < bd) { bd = dd; best = p; } }
      return best;
    };
    for (const m of gloss) {
      const g = m.geometry, pos = g.attributes.position, idx = g.index;
      const tris = idx ? idx.count / 3 : pos.count / 3, get = (i) => (idx ? idx.getX(i) : i);
      const byProbe = new Map();
      for (let t = 0; t < tris; t++) {
        a.fromBufferAttribute(pos, get(t * 3)); b.fromBufferAttribute(pos, get(t * 3 + 1)); d.fromBufferAttribute(pos, get(t * 3 + 2));
        c.copy(a).add(b).add(d).multiplyScalar(1 / 3).applyMatrix4(m.matrixWorld);
        const p = pick(c); if (!byProbe.has(p)) byProbe.set(p, []);
        byProbe.get(p).push(get(t * 3), get(t * 3 + 1), get(t * 3 + 2));
      }
      const order = [...byProbe.keys()], newIdx = [], mats = [];
      g.clearGroups();
      order.forEach((p, i) => {
        const list = byProbe.get(p); g.addGroup(newIdx.length, list.length, i); newIdx.push(...list);
        const ud = m.material.userData; m.material.userData = {}; const mm = m.material.clone(); m.material.userData = ud; mm.userData = { ...ud };       // userData holds textures: keep it out of the JSON copy
        if (mm.lightMap) V.lightMats.push(mm);
        patchGloss(mm, p, m.material.userData.glossWant); mats.push(mm);
      });
      g.setIndex(newIdx); m.material = mats;
    }
    V.probes = P; V.glossMeshes = gloss;
    console.log('[villa] probes', P.length, 'glossy meshes', gloss.length);
  }

  function recapture(renderer, scene3) {
    if (!V.probes || !V.probes.length) return;
    V.glossMeshes.forEach((m) => (m.visible = false));
    const hide = []; scene3.traverse((o) => { if (o.userData.noProbe && o.visible) { o.visible = false; hide.push(o); } });
    V.probes.forEach((p) => { scene3.add(p.cam); p.cam.update(renderer, scene3); scene3.remove(p.cam); });
    V.glossMeshes.forEach((m) => (m.visible = true)); hide.forEach((o) => (o.visible = true));
  }

  /* day / dusk: swap every zone's lightmap, the sky and the exposure, then refresh the reflections */
  V.setMood = async function (mood, sceneEl) {
    if (mood === V.mood) return;
    const zs = Object.values(V.zones).filter((z) => (z.src.moods || ['day']).includes(mood));
    if (!zs.length) return;
    await Promise.all(zs.map(async (z) => {
      if (!z.lights[mood]) z.lights[mood] = await loadLight(z.src, mood);
    }));
    if (!V.skies) V.skies = { day: V.sky.material.map };
    if (!V.skies[mood]) { const t = await loadTex(mood === 'day' ? 'assets/sky.jpg' : 'assets/sky_' + mood + '.jpg', true); t.flipY = true; t.needsUpdate = true; V.skies[mood] = t; }
    V.mood = mood;
    V.lightMats.forEach((m) => {
      const z = V.zones[m.userData.zone]; if (!z || !z.lights[mood]) return;
      m.lightMap = z.lights[mood]; m.lightMapIntensity = lmaxOf(z.src, mood) * Math.PI * (V.exposure || 1);
    });
    // unlit water, leaves and glass have no lightmap: dim them by hand at dusk
    Object.values(V.zones).forEach((z) => z.meshes.forEach((o) => [].concat(o.material).forEach((m) => {
      if (!['water', 'alpha', 'glass'].includes(m.userData.k)) return;
      if (!m.userData.c0) m.userData.c0 = m.color.clone();
      m.color.copy(m.userData.c0).multiplyScalar(mood === 'day' ? 1 : m.userData.k === 'water' ? .35 : .18);
    })));
    V.plantMeshes.forEach((p) => { const a = p.mesh.geometry.getAttribute('color'); a.array.set(p.light[mood] || p.light.day); a.needsUpdate = true; });
    V.sky.material.map = V.skies[mood]; V.sky.material.color.setScalar(mood === 'day' ? 1 : .9);
    if (V.glows) V.glows.children.forEach((p) => (p.material.opacity = mood === 'day' ? .22 : .85));
    const r = sceneEl.renderer; r.toneMappingExposure = (V.tmBase || 1.15) * (mood === 'day' ? 1 : (V.nightGain || 1.6));
    recapture(r, sceneEl.object3D);
    document.body.classList.toggle('dusk', mood !== 'day');
    sceneEl.emit('mood', { mood });
  };

  AFRAME.registerComponent('villa', {
    init() {
      const el = this.el, sceneEl = el.sceneEl, t0 = performance.now();
      V.exposure = parseFloat(qs.get('exp') || '1');
      loadVilla(el).then(() => {
        const ready = () => {
          const r = sceneEl.renderer;
          document.querySelectorAll('[data-aframe-default-light]').forEach((n) => n.remove());
          r.toneMapping = T.AgXToneMapping !== undefined && !qs.has('aces') ? T.AgXToneMapping : T.ACESFilmicToneMapping;
          V.tmBase = parseFloat(qs.get('tm') || '1.15'); V.nightGain = parseFloat(qs.get('ng') || '.9');
          r.toneMappingExposure = V.tmBase;
          progress('Polishing the marble', .9);
          setTimeout(() => {
            if (!V.Q.noProbes) captureProbes(r, sceneEl.object3D);
            console.log('[villa] ready in', Math.round(performance.now() - t0), 'ms');
            V.checkGPU(r); setTimeout(() => V.checkGPU(r), 4000);     // uploads finish over the first frames
            if (qs.get('why')) console.warn('[villa] standard quality after', qs.get('why'));
            progress('Welcome', 1);
            sceneEl.emit('villa-ready');
            if (qs.get('mood') === 'night') V.setMood('night', sceneEl);
          }, 30);
        };
        sceneEl.renderer ? ready() : sceneEl.addEventListener('renderstart', ready, { once: true });
      }).catch((e) => { console.error(e); progress('Could not load the villa: ' + e.message, 0); });
    },
    tick(t, dt) {
      V.U.time.value = t / 1000;
      // draw calls: floors two levels away cannot be seen from inside, so skip them (garden and terrace see everything)
      if (V.nav && V.nav.ready && V.zones) {
        const lv = V.nav.levelOf(V.nav.z), show = { gf: lv !== 3, ff: true, sf: lv !== 1 };
        if (lv !== this._lv) {
          this._lv = lv;
          Object.entries(V.zones).forEach(([zn, z]) => { if (zn in show) z.meshes.forEach((m) => (m.visible = show[zn])); });
        }
      }
      if (V.sky) V.sky.rotation.y += (dt / 1000) * .0015;
    },
  });
})();
