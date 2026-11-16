// Guided-tour relay: pairs one guide (laptop) with one client (phone in the headset) by a short code and passes
// their messages through unchanged. Nothing is stored. node server.js  (PORT env, default 8091)
const http = require('http');
const { WebSocketServer } = require('ws');

const rooms = new Map();                       // code -> { guide, client }
const other = (role) => (role === 'guide' ? 'client' : 'guide');
const send = (ws, m) => { if (ws && ws.readyState === 1) ws.send(JSON.stringify(m)); };

const server = http.createServer((req, res) => {            // health check for Render
  res.writeHead(200, { 'content-type': 'text/plain', 'access-control-allow-origin': '*' });
  res.end('vana relay ok, rooms ' + rooms.size);
});
const wss = new WebSocketServer({ server, maxPayload: 16 * 1024 });

wss.on('connection', (ws) => {
  ws.alive = true; ws.on('pong', () => (ws.alive = true));
  ws.on('message', (data) => {
    let m; try { m = JSON.parse(data); } catch { return; }
    if (m.t === 'hello') {                                  // { t:'hello', role:'guide'|'client', code:'4821' }
      const code = String(m.code || '').replace(/\D/g, '').slice(0, 6), role = m.role === 'guide' ? 'guide' : 'client';
      if (!code) return;
      let r = rooms.get(code); if (!r) rooms.set(code, (r = {}));
      if (r[role] && r[role] !== ws) { send(r[role], { t: 'status', peer: false, replaced: true }); try { r[role].close(4000, 'replaced'); } catch {} }
      r[role] = ws; ws.code = code; ws.role = role;
      const o = r[other(role)];
      send(ws, { t: 'status', peer: !!o }); send(o, { t: 'status', peer: true });
      return;
    }
    const r = rooms.get(ws.code); if (!r) return;
    const o = r[other(ws.role)];
    if (o && o.readyState === 1) o.send(data.toString());
  });
  ws.on('close', () => {
    const r = rooms.get(ws.code); if (!r || r[ws.role] !== ws) return;
    delete r[ws.role];
    const o = r[other(ws.role)];
    if (o) send(o, { t: 'status', peer: false }); else rooms.delete(ws.code);
  });
});
setInterval(() => wss.clients.forEach((ws) => { if (!ws.alive) return ws.terminate(); ws.alive = false; ws.ping(); }), 25000);
server.listen(process.env.PORT || 8091, () => console.log('vana relay on', process.env.PORT || 8091));
