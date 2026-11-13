// R24 م١ — يشغّل dashboard-cloud/dashboard-api.js + v2-logic.js الحقيقيين جوه node:vm بردود جاهزة، ويشغّل سكربت الاختبار.
//   stdin : {"responses": {"/api/path": {"status": 200, "body": {...}}}, "code": "<JS بيرجّع Promise أو قيمة>"}
//   stdout: {"result": <القيمة>, "calls": [{"url","method","body"}]}
// ⛔ لا شبكة: fetch جدول في الذاكرة (أي مسار مش في الجدول ⇒ ٤٠٤). النداءات كلها بتتسجّل.
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = [];
const sb = { console, setTimeout, clearTimeout, setInterval, clearInterval, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error, RegExp };
sb.window = sb;
sb.document = { readyState: 'loading', addEventListener() {}, getElementById() { return null; }, createElement() { return { style: {}, appendChild() {}, classList: { add() {}, remove() {} } }; }, body: { appendChild() {} } };
sb.localStorage = { getItem() { return 'tok'; }, setItem() {}, removeItem() {} };
sb.location = { reload() {}, hash: '' };
sb.toast = function () {};
sb.fetch = function (url, opts) {
  const p = String(url);
  calls.push({ url: p, method: (opts && opts.method) || 'GET', body: opts && opts.body ? JSON.parse(opts.body) : null });
  const hit = input.responses[p] || input.responses[p.split('?')[0]];
  const status = hit ? hit.status : 404;
  const body = hit ? hit.body : { error: 'not found' };
  return Promise.resolve({ ok: status >= 200 && status < 300, status: status, json: () => Promise.resolve(body) });
};
vm.createContext(sb);
const dc = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
vm.runInContext(fs.readFileSync(path.join(dc, 'v2-logic.js'), 'utf8'), sb);
vm.runInContext(fs.readFileSync(path.join(dc, 'dashboard-api.js'), 'utf8'), sb);
const EP = sb.EP;
EP.authed = true; EP.role = input.role || 'admin';
function settled(k) { return new Promise((res) => { const t = () => { const s = EP.state[k]; if (s === 'ready' || s === 'error') res(); else setTimeout(t, 5); }; t(); }); }
sb.settled = settled;
Promise.resolve(vm.runInContext('(function(){' + input.code + '})()', sb)).then((r) => {
  setTimeout(() => process.stdout.write(JSON.stringify({ result: r, calls }, (k, v) => (v === Infinity ? null : v))), 30);
}).catch((e) => { process.stdout.write(JSON.stringify({ error: String(e && e.stack || e) })); process.exit(1); });
