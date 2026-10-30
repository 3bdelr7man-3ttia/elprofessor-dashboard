// يرسم تبويبات «التسويق» كنص (بلا DOM): stdin {tab, model} ⇒ stdout {html}. ⛔ نقي: لا شبكة ولا متصفح. المصدر الناقص في model = idle.
const fs = require('fs');
const path = require('path');
global.window = global;
global.document = { getElementById: () => null, querySelector: () => null, querySelectorAll: () => [], createElement: () => ({}), body: {} };
const DC = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
require(path.join(DC, 'v2-logic.js'));
(0, eval)(fs.readFileSync(path.join(DC, 'v2s', 'marketing.js'), 'utf8'));
const inp = JSON.parse(fs.readFileSync(0, 'utf8'));
const M = Object.assign({ now: Date.parse('2026-10-30T10:00:00Z'), filter: 'active', skipped: [], legacyLater: false, note: null, src: {} }, inp.model || {});
['campaigns', 'owners', 'income', 'ads', 'attribution', 'published'].forEach(k => { M.src[k] = Object.assign({ state: 'idle', data: null }, M.src[k] || {}); });
const out = { html: window.V2SEC.marketing._html(inp.tab, M) };
if (inp.cards) out.cards = window.V2SEC.marketing._cards(M).map(c => Object.assign({}, c, { open: typeof c.open }));
process.stdout.write(JSON.stringify(out));
