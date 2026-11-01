// يشغّل دالة من v2s/saha.js (الجزء النقي) على مدخلات JSON: stdin {"fn": "oppCheck", "args": [...], "of": "S"|"L"} ⇒ stdout JSON. ⛔ نقي: لا شبكة ولا DOM.
const fs = require('fs');
const path = require('path');
const DC = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
require(path.join(DC, 'v2-logic.js'));                 // يضع V2L على globalThis
const S = require(path.join(DC, 'v2s', 'saha.js')).v2sSaha;
const L = globalThis.V2L;
const inp = JSON.parse(fs.readFileSync(0, 'utf8'));
const root = inp.of === 'L' ? L : S;
const fn = inp.fn.split('.').reduce((o, k) => o[k], root);
const out = typeof fn === 'function' ? fn.apply(null, inp.args || []) : fn;
process.stdout.write(JSON.stringify(out === undefined ? null : out, (k, v) => (v === Infinity ? null : v)));
