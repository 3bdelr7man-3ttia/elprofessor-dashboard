// يشغّل دالة من v2-logic.js على مدخلات JSON: stdin {"fn": "v2Tiles", "args": [...]} ⇒ stdout JSON. ⛔ نقي: لا شبكة ولا DOM.
const fs = require('fs');
const path = require('path');
const L = require(path.join(__dirname, '..', '..', '..', 'dashboard-cloud', 'v2-logic.js'));
const inp = JSON.parse(fs.readFileSync(0, 'utf8'));
const fn = inp.fn.split('.').reduce((o, k) => o[k], L);
const out = typeof fn === 'function' ? fn.apply(null, inp.args || []) : fn;   // قيمة ثابتة (SECTIONS · COL_LABEL) تُرجَع كما هي
// Infinity لا يمرّ في JSON ⇒ null (الوقت المجهول).
process.stdout.write(JSON.stringify(out, (k, v) => (v === Infinity ? null : v)));
