// يشغّل دالة من v2s/market4.js على مدخلات JSON: stdin {"fn": "anchorCheck", "args": [...]} ⇒ stdout JSON. ⛔ نقي: لا شبكة ولا DOM.
const fs = require('fs');
const path = require('path');
const DC = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
require(path.join(DC, 'v2-logic.js'));                 // يضع V2L على globalThis
const M = require(path.join(DC, 'v2s', 'market4.js')).v2sMarket4;
const L = globalThis.V2L;
const inp = JSON.parse(fs.readFileSync(0, 'utf8'));
const root = inp.of === 'L' ? L : M;
const fn = inp.fn.split('.').reduce((o, k) => o[k], root);
const out = typeof fn === 'function' ? fn.apply(null, inp.args || []) : fn;
process.stdout.write(JSON.stringify(out, (k, v) => (v === Infinity ? null : v)));
