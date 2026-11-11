// يشغّل v2s/identity_docs.js (درج «توثيق هوية») في node بلا DOM حقيقي ولا شبكة: عناصر وهمية تحفظ `onclick`.
//   stdin : {"mode": "logic", "row": {...}, "texts": ["", "abc", ...]}
//           → {"html": "...", "checks": [{ok, error|text}, ...]}
//   stdin : {"mode": "wire", "row": {...}, "steps": [{"click": "ok"|"no"|"view"|"close", "reason": "...", "reply": {"ok": true} | {"ok": false, "error": "..."}, "blob": {"type": "image/png"}}]}
//           → {"decides": [[action, reason]], "msgs": [text...], "api": [path...], "closed": n, "disabled": {ok, no}}
const fs = require('fs');
const path = require('path');
const M = require(path.join(__dirname, '..', '..', '..', 'dashboard-cloud', 'v2s', 'identity_docs.js'));
const inp = JSON.parse(fs.readFileSync(0, 'utf8'));

if (inp.mode === 'logic') {
  process.stdout.write(JSON.stringify({ html: M.drawerHtml(inp.row), checks: (inp.texts || []).map((t) => M.reasonCheck(t)), fileErr: [404, 422, 500, 0].map((s) => M.fileError(s)) }));
} else {
  const mk = () => ({ dataset: {}, style: {}, onclick: null, disabled: false, textContent: '', innerHTML: '', value: '', focus() {} });
  const els = { '[data-idd-msg]': mk(), '#iddView': mk(), '#iddOut': mk(), '#iddOk': mk(), '#iddNo': mk(), '#iddClose': mk(), '[data-idd-reason]': mk() };
  const el = { querySelector: (s) => els[s] || null };
  const decides = [], api = [], msgs = [];
  let closed = 0, step = null;
  const h = {
    api: (p) => { api.push(p); return Promise.resolve(step.blob || { type: 'image/png' }); },
    decide: (a, r) => { decides.push([a, r]); return Promise.resolve(step.reply || { ok: true }); },
    close: () => { closed++; },
  };
  M.wire(el, inp.row, h);
  (async () => {
    for (const s of inp.steps) {
      step = s;
      els['[data-idd-reason]'].value = s.reason || '';
      const b = { ok: els['#iddOk'], no: els['#iddNo'], view: els['#iddView'], close: els['#iddClose'] }[s.click];
      if (b.onclick) b.onclick();
      await new Promise((r) => setTimeout(r, 15));
      msgs.push(els['[data-idd-msg]'].textContent);
    }
    process.stdout.write(JSON.stringify({ decides, msgs, api, closed, disabled: { ok: els['#iddOk'].disabled, no: els['#iddNo'].disabled } }));
  })();
}
