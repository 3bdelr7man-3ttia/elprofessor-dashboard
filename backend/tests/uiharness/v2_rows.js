// يشغّل dashboard-api.js الحقيقي جوه node:vm بدل المتصفح عشان نطلّع صفوف الوارد (window.INBOX) بالأشكال الحقيقية،
// من ردود جاهزة للمسارات (من الداشبورد نفسه بـ Flask test client). ⛔ لا شبكة: fetch هنا جدول في الذاكرة.
//   stdin : {"responses": {"/api/path?query": {"status": 200, "body": {...}}}, "keys": ["inbox", ...]}
//   stdout: {"asked": [...], "inbox": [...], "failed": [...], "data": {...}, "state": {...}}
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const asked = [];
const sb = { console, setTimeout, clearTimeout, setInterval, clearInterval, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error };
sb.window = sb;
sb.document = { readyState: 'loading', addEventListener() {}, getElementById() { return null; }, createElement() { return { style: {}, appendChild() {}, classList: { add() {}, remove() {} } }; }, body: { appendChild() {} } };
sb.localStorage = { getItem() { return 'tok'; }, setItem() {}, removeItem() {} };
sb.location = { reload() {}, hash: '' };
sb.fetch = function (url, opts) {
  const p = String(url);
  asked.push(p);
  const hit = input.responses[p];
  const status = hit ? hit.status : 404;
  const body = hit ? hit.body : { error: 'not found' };
  return Promise.resolve({ ok: status >= 200 && status < 300, status: status, json: () => Promise.resolve(body) });
};
vm.createContext(sb);
const api = fs.readFileSync(path.join(__dirname, '..', '..', '..', 'dashboard-cloud', 'dashboard-api.js'), 'utf8');
vm.runInContext(api, sb);
const EP = sb.EP;
EP.authed = true; EP.role = 'admin';
const keys = input.keys || ['opsQueue', 'inbox', 'walletPayouts', 'invites', 'pendingUsers', 'market'];
function settled(k) { return new Promise((res) => { const t = () => { const s = EP.state[k]; if (s === 'ready' || s === 'error') res(); else setTimeout(t, 5); }; t(); }); }
keys.forEach((k) => EP.reload(k, null));
Promise.all(keys.map(settled)).then(() => {
  const out = { asked: asked, inbox: sb.window.INBOX || [], failed: sb.window.INBOX_FAILED || [], state: EP.state,
                data: { opsQueue: EP.data.opsQueue, walletPayouts: EP.data.walletPayouts, invites: EP.data.invites,
                        pendingUsers: EP.data.pendingUsers, market: EP.data.market } };
  process.stdout.write(JSON.stringify(out));
});
