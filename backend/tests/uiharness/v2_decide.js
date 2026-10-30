// يشغّل EP.decideInboxItem الحقيقي (dashboard-api.js) جوه node:vm على ردّ جاهز، ويرجّع النتيجة + المسار والجسم اللي اتبعتوا.
//   stdin : {"row": {...}, "action": "approve", "reason": "", "extra": null, "reply": {"status": 200, "body": {}} | {"throw": true}}
//   stdout: {"result": {...}, "calls": [{"url", "method", "body"}]}
// ⛔ لا شبكة: fetch جدول في الذاكرة.
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = [];
const sb = { console, setTimeout, clearTimeout, setInterval, clearInterval, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error };
sb.window = sb;
sb.document = { readyState: 'loading', addEventListener() {}, getElementById() { return null; }, createElement() { return { style: {}, appendChild() {}, classList: { add() {}, remove() {} } }; }, body: { appendChild() {} } };
sb.localStorage = { getItem() { return 'tok'; }, setItem() {}, removeItem() {} };
sb.location = { reload() {}, hash: '' };
sb.toast = function () {};
sb.fetch = function (url, opts) {
  calls.push({ url: String(url), method: (opts && opts.method) || 'GET', body: opts && opts.body ? JSON.parse(opts.body) : null });
  if (calls.length > 1 && (opts && opts.method) !== 'POST') return Promise.reject(new Error('stop'));   // إعادة تحميل الوارد بعد القرار — مش موضوع الاختبار
  if (input.reply.throw) return Promise.reject(new TypeError('Failed to fetch'));
  const st = input.reply.status;
  return Promise.resolve({ ok: st >= 200 && st < 300, status: st, json: () => Promise.resolve(input.reply.body || {}) });
};
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', '..', '..', 'dashboard-cloud', 'dashboard-api.js'), 'utf8'), sb);
const EP = sb.EP;
EP.authed = true; EP.role = 'admin';
Promise.resolve(EP.decideInboxItem(input.row, input.action, null, input.reason || '', input.extra || undefined)).then((r) => {
  setTimeout(() => process.stdout.write(JSON.stringify({ result: r, calls: calls.filter((c) => c.method === 'POST') })), 20);
});
