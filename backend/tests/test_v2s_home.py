# -*- coding: utf-8 -*-
"""«اللوحة + كل الوارد + الدرج + الجرس + الدخول» (الجولة النهائية) — SPEC-home §١٢.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_home.py

⛔ صفر شبكة: المنطق النقي (الشرائح · التذاكر · البحث · سطر العقل · الجرس · طبقة النصوص) بيتشغّل في node على v2-logic.js،
و`v2s/home.js` بيتحمّل في node:vm بنافذة ومستند مزيّفين (يثبّت إن المفتاح المقفول = ولا كتابة في الصفحة). اللقطات (المتصفح الحقيقي) في
`uiharness/v2_shots_home.py`.
"""
import json
import os
import re
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
DC = os.path.join(ROOT, 'dashboard-cloud')
NODE = __import__('shutil').which('node')
needs_node = pytest.mark.skipif(not NODE, reason='needs node')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


HTML = _read('dashboard-cloud', 'index.html')
HOME_JS = _read('dashboard-cloud', 'v2s', 'home.js')
HOME_CSS = _read('dashboard-cloud', 'v2s', 'home.css')
LOGIC = _read('dashboard-cloud', 'v2-logic.js')
COPY_JS = _read('dashboard-cloud', 'v2s', 'home_copy.js')


def _node(js):
    script = "const L=require(%s);require(%s);\n%s" % (json.dumps(os.path.join(DC, 'v2-logic.js')), json.dumps(os.path.join(DC, 'v2s', 'home_copy.js')), js)
    p = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


def _j(v):
    return json.dumps(v, ensure_ascii=False)


# ---------------------------------------------------------------- ١) الربط والأمان

def test_sections_block_once_after_d2_with_the_home_files():
    assert HTML.count('<!-- v2 sections begin -->') == 1 and HTML.count('<!-- v2 sections end -->') == 1
    b = HTML.index('<!-- v2 sections begin -->')
    assert HTML.index('<script src="v2-d2.js"></script>') < b
    blk = HTML[b:HTML.index('<!-- v2 sections end -->')]
    assert '<link rel="stylesheet" href="v2s/home.css">' in blk and '<script src="v2s/home.js"></script>' in blk
    assert '<script src="v2s/home_copy.js"></script>' in blk
    keys = re.findall(r'href="v2s/([a-z0-9_]+)\.css"', blk)
    assert keys == sorted(keys)
    # بعد المنطق واللوحة والغلاف، وقبل السكربت الداخلي
    assert HTML.index('<script src="v2-shell.js"></script>') < b < HTML.index('<script>\n', b)


def test_the_two_hooks_are_the_first_statement_and_appear_once():
    vi = "function viewInbox(v){\n  if(window.V2SEC&&V2SEC.home&&V2SEC.home.inbox&&V2SEC.home.inbox(v))return;\n"
    ri = "function renderInbox(){\n  if(window.V2SEC&&V2SEC.home&&V2SEC.home.list&&V2SEC.home.list())return;\n"
    assert HTML.count(vi) == 1 and HTML.count(ri) == 1
    assert HTML.count('V2SEC.home.inbox(v)') == 1 and HTML.count('V2SEC.home.list()') == 1


def test_login_flag_wiring_s5_s6():
    flag = HTML[HTML.index('function v2LoadFlag'):HTML.index('window.EP_BOOT=function(){')]
    then, _, catch = flag.partition('.catch(')
    assert then.count("localStorage.setItem('ep_v2_shell','1')") == 1 and then.count("localStorage.setItem('ep_v2_shell','0')") == 1
    assert "removeItem('ep_v2_shell')" not in flag
    assert 'localStorage' not in catch                      # الفشل والمهلة لا يكتبان شيئًا
    boot = HTML[HTML.index('window.EP_BOOT=function(){'):HTML.index('function epBootCore(){')]
    assert "localStorage.getItem('ep_v2_shell')==='1'" in boot
    assert "ep_v2_shell" in _read('backend', 'tests', 'test_v2_d1b.py') and "localStorage.setItem('ep_v2_shell','0')" in _read('backend', 'tests', 'test_v2_d1b.py')


def test_both_dockerfiles_copy_the_sections_directory():
    for f in ('Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')):
        assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in _read(f)


def test_xss_allowlist_accepts_only_v2s_named_scripts():
    src = _read('backend', 'tests', 'test_xss_hardening.py')
    m = re.search(r"re\.search\(r'(<script\\s\+src=\[\"\\'\]\(\?!.*?)', src\)", src)
    assert m, 'regex not found'
    rx = re.compile(m.group(1).replace('\\\\', '\\'))
    assert not rx.search('<script src="v2s/home.js">')
    assert rx.search('<script src="https://evil.test/x.js">')
    assert rx.search('<script src="v2s/../x.js">')
    assert rx.search('<script src="evil.js">')


def test_every_css_selector_is_scoped_so_the_switch_off_is_untouched():
    css = re.sub(r'/\*.*?\*/', '', HOME_CSS, flags=re.S)
    css = re.sub(r'@media[^{]*\{', '', css)
    ok = ('.app.v2-shell', 'body:has(> .app.v2-shell)', 'body:has(> .app.v2-shell:not(.v2-roles))', 'html.v2h-login', '.app.v2-pre', 'from', 'to', '0%', '100%')
    bad = []
    for sel in re.findall(r'([^{}]+)\{', css):
        for part in sel.split(','):
            part = part.strip()
            if not part or part.startswith('@keyframes'):
                continue
            if not part.startswith(ok):
                bad.append(part)
    assert not bad, bad[:5]


def test_home_has_no_server_routes_of_its_own():
    """بعد الدمج: app.py فيه مسارات الأقسام الأخرى؛ الرئيسية ما لها ملف مسارات ولا سطر تسجيل."""
    assert not os.path.exists(os.path.join(ROOT, 'backend', 'v2_home_routes.py'))
    assert 'v2_home_routes' not in _read('backend', 'app.py')


def test_css_pieces_that_replace_js():
    assert '.app.v2-shell:has(.v2h) #view{' in HOME_CSS
    assert '.app.v2-shell:has(.v2h) .topbar .search{display:none!important}' in HOME_CSS
    # .note-ai ورقة عادية: لا `content` ولا عنوان للعقل
    for m in re.finditer(r'[^{}]*\.note-ai[^{}]*\{([^}]*)\}', HOME_CSS):
        assert 'content' not in m.group(1)
    assert re.search(r'#v2HBell|\.v2h-bell\{[^}]*z-index:78', HOME_CSS)
    assert 'z-index:78' in HOME_CSS and 'z-index:77' in HOME_CSS
    assert 'v2-bare' not in HOME_JS            # الإطار يُزال بالـCSS لا بصنف يمحوه سطر الغلاف


def test_no_network_in_home_js_other_than_the_read_only_notifications():
    assert re.findall(r'fetch\(|XMLHttpRequest|sendBeacon', HOME_JS) == []
    assert HOME_JS.count("E.api('/notifications')") == 1
    assert 'method' not in HOME_JS.replace('PUT', '')    # لا POST/PUT من هنا


# ---------------------------------------------------------------- ٢) المفتاح مقفول: النسخة القديمة بالحرف (node:vm)

VM_JS = r"""
const vm = require('vm'), fs = require('fs');
function make(opts) {
  opts = opts || {};
  const writes = [];
  const cls = new Set();
  const store = opts.storage === 'throw' ? null : Object.assign({}, opts.storage || {});
  const el = () => ({ classList: { add() { writes.push('add'); }, remove() {}, toggle() {}, contains() { return false; } }, appendChild() { writes.push('append'); }, addEventListener() {},
    setAttribute() { writes.push('attr'); }, querySelector() { return null; }, style: {} });
  const doc = { documentElement: { classList: { add: c => cls.add(c), remove: c => cls.delete(c), contains: c => cls.has(c) } },
    getElementById() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; }, addEventListener() {},
    createElement() { writes.push('create'); return el(); }, body: { appendChild() { writes.push('body.append'); }, closest() { return null; } } };
  const bb = { onclick: 'ORIGINAL' };
  doc.getElementById = id => (id === 'bellBtn' ? bb : null);
  const win = { localStorage: store === null ? { getItem() { throw new Error('blocked'); } } : { getItem: k => (k in store ? store[k] : null), setItem() {} },
    document: doc, matchMedia: () => ({ matches: false, addEventListener() {} }), setInterval() {}, setTimeout() {}, MutationObserver: function () { this.observe = function () {}; },
    EP: opts.EP || { role: 'admin', state: {}, data: {}, ensure() {}, authed: true }, V2_ON: opts.V2_ON !== false };
  if (opts.shell !== null) win.V2SHELL = { on: opts.shellOn !== false, boot() {}, nav() {} };
  win.window = win; win.localStorage = win.localStorage;
  const ctx = vm.createContext(Object.assign(win, { role: opts.role || 'admin', current: 'inbox', selected: null, activeFilter: 'all', INBOX: [], console: console }));
  vm.runInContext('globalThis.localStorage = window.localStorage; globalThis.document = window.document;', ctx);
  vm.runInContext(fs.readFileSync(%(logic)s, 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(%(copy)s, 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(%(home)s, 'utf8'), ctx);
  return { ctx, win, writes, cls, bb };
}
""" % {'logic': _j(os.path.join(DC, 'v2-logic.js')), 'copy': _j(os.path.join(DC, 'v2s', 'home_copy.js')), 'home': _j(os.path.join(DC, 'v2s', 'home.js'))}


def _vm(js):
    p = subprocess.run([NODE, '-e', VM_JS + "\n" + js], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1800:]
    return json.loads(p.stdout)


@needs_node
@pytest.mark.parametrize('case', ['noshell', 'shelloff', 'employee', 'v2off'])
def test_switch_off_means_both_hooks_return_false_and_write_nothing(case):
    opt = {'noshell': "{shell:null}", 'shelloff': "{shellOn:false}", 'employee': "{role:'employee'}", 'v2off': "{V2_ON:false}"}[case]
    r = _vm("const h = make(%s); const v = {innerHTML: 'OLD'}; const a = h.win.V2SEC.home.inbox(v), b = h.win.V2SEC.home.list();"
            "console.log(JSON.stringify({a, b, html: v.innerHTML, writes: h.writes}))" % opt)
    assert r == {'a': False, 'b': False, 'html': 'OLD', 'writes': []}


@needs_node
def test_bell_is_not_mounted_and_the_old_handler_is_untouched_when_off():
    r = _vm("const h = make({shellOn:false}); h.win.V2SEC.home.bell.mount(); h.win.V2SEC.home.start();"
            "console.log(JSON.stringify({onclick: h.bb.onclick, writes: h.writes}))")
    assert r == {'onclick': 'ORIGINAL', 'writes': []}


@needs_node
@pytest.mark.parametrize('storage,expect', [("{ep_v2_shell: '1'}", True), ("{}", True), ("{ep_v2_shell: '0'}", False), ("'throw'", True)])
def test_login_look_default_is_new_and_only_stored_zero_keeps_the_old(storage, expect):
    r = _vm("const h = make({storage: %s}); console.log(JSON.stringify(h.cls.has('v2h-login')))" % storage)
    assert r is expect


# ---------------------------------------------------------------- ٣) الدوال النقية

@needs_node
def test_chips_order_labels_zero_hiding_and_contexts():
    r = _node("""const c = L.v2hChips('home', {all: 34, late: 12, 't:files': 18, 't:disputes': 0, 't:legacy': 3, 't:money': 2, 't:decisions': 8, auto: 0}, 'all');
      const f = L.v2hChips('files', {'t:files': 5, late: 0, attn: 2, review: 0}, 't:files');
      const fa = L.v2hChips('files', {'t:files': 5, late: 0, attn: 2, review: 0}, 'late');
      const m = L.v2hChips('messages', {'t:messages': 4}, 't:messages'), d = L.v2hChips('disputes', {'t:disputes': 1, 't:legacy': 0}, 't:disputes');
      console.log(JSON.stringify({home: c.row1.map(x => [x.key, x.label, x.n, x.text, x.on, x.tone]), files: [f.row1.map(x => x.key), f.row2.map(x => x.key)], fa: fa.row1.map(x => x.key),
        m: m, d: d.row1.map(x => x.key), labels: L.v2hChips('home', {'t:decisions': 1}, 'all').row1.map(x => x.label)}))""")
    assert r['home'] == [['all', 'الكل', 34, '٣٤', True, ''], ['late', 'متأخر', 12, '١٢', False, 'late'], ['t:files', 'ملفات الخبراء', 18, '١٨', False, ''],
                         ['t:legacy', 'استشارات قديمة', 3, '٣', False, ''], ['t:money', 'إيصالات التحويل', 2, '٢', False, ''],
                         ['t:decisions', 'طلبات انضمام واعتماد', 8, '٨', False, '']]
    assert r['files'] == [['t:files'], ['attn']] and r['fa'] == ['t:files', 'late']        # النشطة تظهر ولو صفرًا
    assert r['m'] == {'row1': [], 'row2': []} and r['d'] == ['t:disputes']
    assert 'طلبات انضمام واعتماد' in r['labels']


@needs_node
def test_no_chip_label_collides_with_the_waiting_group():
    r = _node("""const all = []; ['home','files','disputes','messages'].forEach(c => { const k = L.v2hChipKeys(c); const cnt = {}; k.forEach(x => cnt[x] = 1);
      const ch = L.v2hChips(c, cnt, ''); all.push.apply(all, ch.row1.concat(ch.row2).map(x => x.label)); });
      console.log(JSON.stringify(all))""")
    assert 'ينتظر قرارك' not in r and 'طلبات تنتظر قرارك' not in r
    assert len(set(r)) >= 15


@needs_node
def test_groups_late_first_then_rank_then_oldest_unknown_last_and_stable():
    items = [{'card': {'group': 70, 'ts': 5}, 'row': {}, 'late': False}, {'card': {'group': 10, 'ts': 9}, 'row': {}, 'late': True},
             {'card': {'group': 10, 'ts': 3}, 'row': {}, 'late': True}, {'card': {'group': 20, 'ts': None}, 'row': {}, 'late': False},
             {'card': {'group': 20, 'ts': None}, 'row': {'triage': 'auto'}, 'late': False}, {'card': {'group': 20, 'ts': 1}, 'row': {}, 'late': False},
             {'card': None, 'row': {'who': 'س'}, 'late': False}]
    for i, it in enumerate(items):
        it['i'] = i
    g = _node("const g = L.v2hGroups(%s); console.log(JSON.stringify(g.map(x => [x.key, x.label, x.items.map(i => i.i)])))" % _j(items))
    assert g == [['late', 'متأخر', [2, 1]], ['wait', 'ينتظر قرارك', [5, 3, 0, 6]], ['auto', 'عولجت تلقائيًا', [4]]]
    assert _node("console.log(JSON.stringify(L.v2hGroups([{card:null,row:{},late:false}]).map(x=>x.key)))") == ['wait']      # الفارغة تسقط
    assert _node("console.log(JSON.stringify(L.v2hGroups([])))") == []


@needs_node
def test_tone_and_flags_every_branch():
    r = _node("""console.log(JSON.stringify({t: [L.v2hTone({}, null, true), L.v2hTone({apiKind:'payout'}, null, false), L.v2hTone({apiKind:'manual_payment'}, {kind:'manual_payment'}, false),
        L.v2hTone({triage:'auto'}, null, false), L.v2hTone({apiKind:'trainer'}, {kind:'trainer'}, false), L.v2hTone({apiKind:'legacy'}, null, false), L.v2hTone({triage:'auto'}, null, true)],
      f: [L.v2hFlags({}), L.v2hFlags({urgent:1, contract:1, noCandidate:1, needsAttention:1}), L.v2hFlags({licensed:1}), L.v2hFlags({licensed:1, licenceMissing:1}), L.v2hFlags({flagLabels:['أ','ب']}),
          L.v2hFlags({msgSource:'site'}), L.v2hFlags({msgSource:'platform'}), L.v2hFlags({licenceMissing:1})]}))""")
    assert r['t'] == ['late', 'money', 'money', 'done', 'wait', 'money', 'late']
    ft = [[x['t'] for x in f] for f in r['f']]
    assert ft == [[], ['مستعجل', 'مراجعة عقد', 'لا خبير متاح', 'يحتاج تدخّلك'], ['خدمة مرخّصة'], ['خدمة مرخّصة بلا رقم قيد'], ['حساب عليه علامات'], ['من الموقع'], ['من المنصة'], ['خدمة مرخّصة بلا رقم قيد']]
    assert r['f'][4][0]['tip'] == 'أ · ب'
    assert not any('خدمة مرخّصة' in a and 'بلا' in b for a, b in zip(ft[2], ft[2]))


@needs_node
def test_search_normalisation_and_text():
    r = _node("""const n = L.v2hNorm;
      console.log(JSON.stringify([n('أحمد'), n('احمد') === n('إحمد'), n('مدرسة') === n('مدرسه'), n('على') === n('علي'), n('مُحَمَّد') === n('محمد'), n('ـــمحمد') === n('محمد'), n('١٢٣') === n('123'), n('  A   B '),
        L.v2hSearchText({out:'و', from:'ف', who:'ه', serviceLabel:'خ', email:'e@x.test', searchText:'س'}, 'وجهة', {tag:'تاغ', title:'عنوان'}),
        n(L.v2hSearchText({email:'Sara@Example.test'}, '', null)).indexOf(n('sara@exa')) > -1]))""")
    assert r[0] == 'احمد' and all(r[1:7]) and r[7] == 'a b'
    assert r[8] == 'و ف ه خ e@x.test س وجهة تاغ عنوان' and r[9] is True


@needs_node
def test_brain_line_wording_and_rules():
    def it(late, title='ملف', age='منذ ٣ ساعات', ts=1, auto=False):
        return {'card': {'title': title, 'ageText': age, 'ts': ts, 'group': 10}, 'row': {'triage': 'auto'} if auto else {}, 'late': late}
    f = lambda items, n, st: _node("console.log(JSON.stringify(L.v2hBrainLine(%s, %d, %s)))" % (_j(items), n, _j(st)))
    assert f([it(True)], 0, 'ready') == 'بند متأخر واحد — أقدمها «ملف» منذ ٣ ساعات'
    assert f([it(True), it(True, ts=2)], 0, 'ready').startswith('بندان متأخران')
    assert f([it(True)] * 3, 0, 'ready').startswith('٣ بنود متأخرة')
    assert f([it(True)] * 11, 0, 'ready').startswith('١١ بندًا متأخرًا')
    assert f([it(True, 'القديم', 'منذ يوم', ts=1), it(True, 'الأحدث', 'منذ ساعة', ts=9)], 0, 'ready') == 'بندان متأخران — أقدمها «القديم» منذ يوم'
    assert f([it(False)], 0, 'ready') == 'أقدم ما ينتظرك: «ملف» منذ ٣ ساعات'
    assert f([it(False)], 3, 'ready').endswith('وزّع العقل ٣ ملفات اليوم')
    assert 'وزّع العقل' not in f([it(False)], 0, 'ready')
    assert f([], 0, 'ready') == 'لا شيء ينتظرك في الوارد الآن'
    assert f([], 0, 'partial') is None and f([], 0, 'error') is None and f([it(True)], 5, 'loading') is None
    assert f([], 1, 'ready') == 'لا شيء ينتظرك في الوارد الآن · وزّع العقل ملفًا واحدًا اليوم'


@needs_node
def test_every_queue_counter_key_has_a_standard_label():
    keys = re.findall(r"'(\w+)'\]", HTML[HTML.index('function opsQueueCounters'):HTML.index('function goOps')])
    keys = [k for k in keys if k not in ('inbox', 'finance', 'courses', 'topics', 'team', 'escrow', 'invites')]
    assert len(set(keys)) == 23, keys
    r = _node("console.log(JSON.stringify([%s].map(k => L.v2hQueueLabel(k)).concat([L.v2hQueueLabel('unknown_key')])))" % ','.join(_j(k) for k in sorted(set(keys))))
    assert r[-1] == 'بند من المنصة' and 'بند من المنصة' not in r[:-1]
    for t in r:
        assert not re.search(r'[A-Za-z]', t), t


@needs_node
def test_notif_list_accepts_the_server_shape_the_old_bell_missed():
    r = _node("""const item = {id: 'message:1', title: 'x', detail: 'منى: عقد', kind: 'message', when: '2026-10-30T10:00:00', unread: true};
      console.log(JSON.stringify([L.v2hNotifList({count: 1, total: 1, items: [item]}), L.v2hNotifList([item]), L.v2hNotifList({notifications: [item]}), L.v2hNotifList({}), L.v2hNotifList(null), L.v2hNotifList('x'), L.v2hNotifList({items: 'no'})]))""")
    assert len(r[0]) == 1 and r[0][0]['id'] == 'message:1' and len(r[1]) == 1 and len(r[2]) == 1
    assert r[3] is None and r[4] is None and r[5] is None and r[6] is None            # غير ذلك = فشل (لا قائمة فارغة كاذبة)


@needs_node
def test_notif_titles_details_and_destinations_by_kind():
    r = _node("""const f = (kind, detail, title) => L.v2hNotif({id: kind, kind, detail, title, unread: true});
      console.log(JSON.stringify({m: f('message', 'منى: عقد'), w: f('withdrawal', 'مستثمر — 250.5 USD'), t: f('trainer_application', 'أ. هالة بانتظار الموافقة'), p: f('program_request', 'دورة — أحمد'),
        s: f('signup', 'سلمى أنشأ حسابًا'), u: f('other', 'x', 'Hello'), u2: f('other', 'x', 'تنبيه'), unread: L.v2hNotif({id: 'a', kind: 'signup', unread: false}).unread}))""")
    assert r['m']['title'] == 'رسالة جديدة من نموذج التواصل' and r['m']['detail'] == 'منى: عقد' and r['m']['dest'] == {'section': 'people', 'tab': 'messages'}
    assert r['w']['title'] == 'طلب سحب من مستثمر ينتظر المراجعة' and r['w']['detail'] == 'مستثمر — ٢٥٠٫٥ دولار' and r['w']['dest'] == {'section': 'company', 'tab': 'invest'}
    assert r['t']['detail'] == 'أ. هالة' and r['t']['dest'] == {'section': 'courses', 'tab': 'trainers'}
    assert r['p']['dest'] == {'section': 'courses', 'tab': 'courses'}
    assert r['s']['title'] == 'حساب جديد على المنصة' and r['s']['detail'] == 'سلمى' and r['s']['dest'] == {'section': 'people', 'tab': 'users'}
    assert r['u']['title'] == 'إشعار' and r['u']['dest'] is None and r['u2']['title'] == 'تنبيه' and r['unread'] is False


@needs_node
def test_bell_badge_counts_only_unseen_notifications_never_health():
    r = _node("""const N = (n, un) => Array.from({length: n}, (_, i) => ({id: 'n' + i, unread: i < un}));
      const okH = {ok: true, failed: false, alerts: []}, badH = {ok: false, failed: false, alerts: ['a', 'b', 'c']}, failH = {ok: false, failed: true, alerts: []};
      const b = (h, n, s) => L.v2hBellBadge(h, n, s);
      console.log(JSON.stringify([b(okH, [], []), b(badH, N(2, 2), []), b(okH, N(3, 3), ['n0']), b(okH, N(3, 1), []), b(failH, N(2, 2), []), b(okH, null, []), b(failH, null, []), b(null, undefined, []),
        b(okH, N(3, 3), {n0: true, n1: true})]))""")
    assert r[0] == {'text': '', 'tone': 'none', 'dot': False}
    assert r[1] == {'text': '٢', 'tone': 'count', 'dot': True}                        # ٣ تنبيهات صحة + ٢ إشعار ⇒ «٢» ونقطة
    assert r[2]['text'] == '٢' and r[3]['text'] == '١'                                # المقروء والمشاهَد خارج العدّ
    assert r[4] == {'text': '٢', 'tone': 'count', 'dot': True}
    assert r[5] == {'text': '', 'tone': 'warn', 'dot': True}
    assert r[6] == {'text': '!', 'tone': 'warn', 'dot': False}
    assert r[7] == {'text': '', 'tone': 'none', 'dot': False}
    assert r[8]['text'] == '١'


@needs_node
def test_ticket_button_label_and_drawer_target():
    r = _node("""const c = (d, label) => ({primary: {label, act: {do: d}}});
      const out = {}; ['send', 'pay_confirm', 'pay_reject', 'decide', 'resolve', 'payout_settle', 'offer_approve', 'open', 'person', 'section', 'goto', 'row'].forEach(d => out[d] = L.v2hTicketBtn(c(d, 'اسم الزر')));
      out.none = L.v2hTicketBtn({primary: null}); out.nullcard = L.v2hTicketBtn(null); out.colloq = L.v2hTicketBtn(c('decide', 'اعتمد وحوّل للموديول')); out.map = L.V2H_ACT_TO_DRAWER;
      console.log(JSON.stringify(out))""")
    assert r['send'] == {'label': 'اسم الزر', 'drawerA': 'ef_pick'}
    assert r['pay_confirm']['drawerA'] == 'approve' and r['pay_reject']['drawerA'] == 'reject'
    assert r['decide']['drawerA'] == 'approve' and r['resolve']['drawerA'] == 'resolve'
    assert r['payout_settle'] == {'label': 'اسم الزر', 'drawerA': None} and r['offer_approve']['drawerA'] is None
    assert r['open'] == {'label': 'اسم الزر', 'drawerA': None}
    for k in ('person', 'section', 'goto', 'row', 'none', 'nullcard'):
        assert r[k] == {'label': 'افتح وقرّر', 'drawerA': None}, k
    assert r['colloq']['label'] == 'اعتمد الطلب'                                  # كل تسمية تمرّ من طبقة النصوص
    for v in r['map'].values():
        assert 'data-a="%s"' % v in HTML, v                                          # الهدف زر حقيقي في الدرج


@needs_node
def test_segments_default_counts_and_explicit_choice():
    items = lambda late, wait, auto: ([{'card': None, 'row': {}, 'late': True}] * late + [{'card': None, 'row': {}, 'late': False}] * wait +
                                      [{'card': None, 'row': {'triage': 'auto'}, 'late': False}] * auto)
    f = lambda it, seg: _node("const s = L.v2hSegs(%s, %s); console.log(JSON.stringify([s.active, s.segs.map(x => [x.key, x.label, x.n, x.on])]))" % (_j(it), _j(seg)))
    a, segs = f(items(0, 3, 1), None)
    assert a == 'wait' and segs == [['late', 'متأخر', 0, False], ['wait', 'ينتظر قرارك', 3, True], ['auto', 'عولجت تلقائيًا', 1, False]]
    assert f(items(2, 3, 1), None)[0] == 'late' and f(items(0, 0, 2), None)[0] == 'auto'
    a, segs = f(items(0, 0, 0), None)
    assert a == 'late' and [s[2] for s in segs] == [0, 0, 0]
    assert f(items(2, 0, 0), 'auto')[0] == 'auto'                                      # الاختيار الصريح يغلب ولو فارغًا
    assert sum(s[2] for s in f(items(2, 3, 4), None)[1]) == 9


@needs_node
def test_alert_sections_and_health_line():
    r = _node("""console.log(JSON.stringify({a: ['ملف واحد ينتظر التوزيع', 'رأي متأخر واحد', 'نزاع واحد على استشارة ينتظر قرارك', 'استشارة قديمة واحدة سُلّمت وتنتظر قرارك: للخبير أم للعميل',
        'حجز واحد أُلغي وأمواله لدينا — أعدها يدويًا', 'تعذّر الوصول إلى سجل الالتحاق بالدورات', 'الفحص الدوري: لم تعمل حتى الآن — شغّلها اليوم', ''].map(L.v2hAlertSection),
      h: [L.v2hHealthLine('loading', null).text, L.v2hHealthLine('error', null).text, L.v2hHealthLine('ready', {ok: true, alerts: []}).text, L.v2hHealthLine('ready', {ok: false, alerts: ['a', 'b']}).text,
          L.v2hHealthLine('ready', {ok: false, alerts: ['a']}).text, L.v2hHealthLine('ready', {failed: true}).text]}))""")
    assert r['a'] == ['files', 'files', 'disputes', 'disputes', 'disputes', 'courses', None, None]
    assert r['h'] == ['حالة المنصة: جارٍ الفحص…', 'حالة المنصة: تعذّر الفحص — افتح التنبيهات', 'حالة المنصة: كل شيء يعمل',
                      'حالة المنصة: تنبيهان — افتح التنبيهات', 'حالة المنصة: تنبيه واحد — افتح التنبيهات', 'حالة المنصة: تعذّر الفحص — افتح التنبيهات']


@needs_node
def test_service_auto_and_fyi_lines():
    r = _node("""console.log(JSON.stringify({s: [L.v2hServiceLine('closed', null), L.v2hServiceLine('allowlist', 2), L.v2hServiceLine('allowlist', null), L.v2hServiceLine('open', 1)],
      a: [L.v2hAutoLine(true), L.v2hAutoLine(false), L.v2hAutoLine(null)], y: [L.v2hFyiLine(1, true, false), L.v2hFyiLine(3, false, false), L.v2hFyiLine(3, true, true)]}))""")
    assert r['s'][0].startswith('خدمة «ملف للخبير» متوقفة') and 'حسابان' in r['s'][1] and '(' not in r['s'][2] and r['s'][3] == ''
    assert r['a'][0]['btn'] == 'أوقفه' and 'هل توقفه؟' in r['a'][0]['confirm'] and r['a'][1]['btn'] == 'شغّله' and r['a'][2] is None
    assert 'ملف واحد أُرسل' in r['y'][0] and r['y'][0].endswith('إن لم يُستلم يُرسل إلى خبير آخر تلقائيًا.')
    assert r['y'][1].startswith('للعلم: ٣ ملفات أُرسلت') and r['y'][1].endswith('إن لم يُستلم يعود إلى هنا.')
    assert r['y'][2].startswith('هذه ملفات أُرسلت إلى خبير')


# ---------------------------------------------------------------- ٤) طبقة النصوص

COLLOQ = ['مش ', 'دلوقتي', 'اتبعت', 'اتدفع', 'اتستلم', 'بتاع', 'عايز', 'هيت', 'ابعته', 'رجّع', 'مستني', 'لوحده', 'لوحدها', 'إيه', ' ليه', 'كده', 'اللي', 'تاني', 'مالهاش', 'بقى', 'إزاي', 'خالص', 'يقوّم']


def has_marker(t):
    # «بقى» كلمة كاملة (لا تُطابَق داخل «يبقى/تبقى»)
    return any((re.search(r'(^|[^\u0621-\u064A])بقى', t) if m == 'بقى' else m in t) for m in COLLOQ)


def _capture():
    p = os.path.join(ROOT, 'docs', 'v2', 'final', 'shots-home', 'copy-capture.json')
    if not os.path.exists(p):
        pytest.skip('run uiharness/v2_shots_home.py first (writes copy-capture.json)')
    with open(p, encoding='utf-8') as fh:
        return json.load(fh)


def test_colloquial_markers_constant_matches_the_spec():
    assert _node("console.log(JSON.stringify(L.V2H_COLLOQUIAL))") == COLLOQ


@needs_node
def test_copy_seed_entries_from_the_spec():
    cases = {'رجّع الفلوس': 'أعد الأموال إلى صاحب الطلب', 'ابعته لحد تاني': 'أرسله إلى خبير آخر', 'رجّعه للخبير': 'أعده إلى الخبير', 'قارن الرأيين': 'قارن بين الرأيين',
             'اعتمد وحوّل للموديول': 'اعتمد الطلب', 'عُولجت — عرض': 'عولجت تلقائيًا — اعرض', 'حوّل للخبير المحدَّد': 'أرسل إلى الخبير المختار',
             'اطلب عيّنة/مستندًا — الصفّ يفضل مفتوح': 'اطلب مستندًا أو عيّنة — يبقى الطلب مفتوحًا', 'يُدار في موديول': 'القسم', 'حالة الفرز': 'الحالة',
             'اتبعت تلقائي لـهالة': 'أُرسل تلقائيًا إلى هالة', 'اتبعت بإيدك لـهالة': 'أرسلته بنفسك إلى هالة', 'فتح الوارد': 'افتح الوارد',
             'اختر بندًا من الوارد لرؤية مساره الكامل والإجراء.': 'اختر بندًا من القائمة لترى تفاصيله وما يمكنك فعله.',
             'لا يوجد خبير معتمد في هذا التخصص بعد — اعتمد خبيرًا أولًا من «الخبراء والمدربون».': 'لا يوجد خبير معتمد في هذا التخصص بعد — اعتمد خبيرًا أولًا من «ملفات الخبراء ← الخبراء».',
             'ابعتلنا رقم قيدك بالنقابة — أو رابط صورة الكارنيه — واكتبه في خانة «رقم القيد» في الاستمارة.': 'يُرجى إرسال رقم القيد في النقابة أو رابط صورة البطاقة، وكتابته في خانة «رقم القيد» في الاستمارة.'}
    r = _node("console.log(JSON.stringify(%s.map(k => L.v2hCopy(k))))" % _j(list(cases)))
    assert r == list(cases.values())
    assert _node("console.log(JSON.stringify([L.v2hCopy('اعتبرها منتهية'), L.v2hCopy('  '), L.v2hCopy(null), L.v2hCopy(5), L.v2hCopy('نص فصيح تمامًا')]))") == [None] * 5


@needs_node
def test_copy_keeps_surrounding_whitespace_and_interpolated_parts():
    r = _node("console.log(JSON.stringify([L.v2hCopy('  رجّع الفلوس\\n'), L.v2hCopy('هترجّع '), L.v2hCopy(' كاملين لمحفظة '), L.v2hCopy('📩 رجعت ٥٠٠ ج لمحفظة طارق ✓')]))")
    assert r == ['  أعد الأموال إلى صاحب الطلب\n', 'ستُعيد ', ' كاملةً إلى محفظة ', '📩 أُعيد ٥٠٠ ج إلى محفظة طارق ✓']


@needs_node
def test_copy_is_idempotent_and_never_outputs_a_colloquial_marker_or_the_banned_verb():
    d = _node("console.log(JSON.stringify({e: Object.keys(L.__copyDict.EXACT), p: L.__copyDict.PHRASES.map(x => x[0])}))")
    keys = d['e'] + d['p']
    assert len(keys) > 150
    outs = _node("console.log(JSON.stringify(%s.map(k => [k, L.v2hCopy(k)])))" % _j(keys))
    for k, o in outs:
        if o is None:
            continue                                                        # مفتاح قصير يمرّ كجزء (يُغطّى بالتالي)
        assert _node("console.log(JSON.stringify(L.v2hCopy(%s)))" % _j(o)) is None, (k, o)      # idempotent
        assert 'يقوّم' not in o and not has_marker(o), (k, o)
        assert not re.search(r'[A-Za-z]', o), (k, o)
        assert not re.match(r'^(ذكاء|الذكاء|AI)', o)


def test_copy_keys_exist_verbatim_in_the_source_or_in_the_captured_run():
    d = _node("console.log(JSON.stringify({e: Object.keys(L.__copyDict.EXACT), p: L.__copyDict.PHRASES.map(x => x[0])}))") if NODE else {'e': [], 'p': []}
    cap = _capture()
    # جمل وقوف الأموال تأتي من المنصة حرفيًا (فيكستشر المنصة يعكسها)، فهي مصدر مفاتيحها
    blob = HTML + _read('dashboard-cloud', 'dashboard-api.js') + _read('backend', 'tests', 'uiharness', 'ef_fixtures.py') + '\n'.join(cap)
    dead = [k for k in d['e'] + d['p'] if k.strip() not in blob]
    assert not dead, dead[:8]


def test_every_colloquial_captured_string_is_handled_by_the_dictionary():
    if not NODE:
        pytest.skip('needs node')
    cap = [t for t in _capture() if has_marker(t)]
    outs = _node("console.log(JSON.stringify(%s.map(t => [t, L.v2hCopy(t)])))" % _j(cap))
    unhandled = [t for t, o in outs if o is None]
    # كلام الناس وبيانات المنصة (أسئلة العملاء وإجاباتهم وما يكتبه الخبراء) تبقى كما وصلت: ما يرد حرفًا في فيكستشرات المنصة يُستثنى عمدًا
    fx = ''.join(_read('backend', 'tests', 'uiharness', f) for f in ('ef_fixtures.py', 'v2_fixtures.py', 'fake_platform.py'))
    left = [t for t in unhandled if t[:18] not in fx]
    assert not left, left[:6]


def _fake_node_vm(extra=''):
    return ("const h = make({EP: {role:'admin', state:{}, data:{}, ensure(){}, authed:true}});"
            "h.win.INBOX = []; const C = h.win.V2SEC.home.copy;"
            "const mk = (txt, classes, tag) => ({nodeType: 3, nodeValue: txt, parentNode: {nodeType: 1, tagName: tag || 'DIV', value: '', defaultValue: '',"
            " closest(sel) { return classes.some(c => sel.indexOf(c) > -1) ? this : null; }}});" + extra)


@needs_node
def test_copy_misses_are_recorded_not_hidden_and_people_words_are_skipped():
    r = _vm(_fake_node_vm("""
      const scope = ['.drawer'];
      const a = mk('جملة عامية جديدة مش معروفة', scope), b = mk('اللي كتبه العميل بنفسه', scope.concat(['.ef-quote .row2'])), c = mk('نص فصيح تمامًا', scope), d = mk('رجّع الفلوس', scope);
      C.processText(a); C.processText(b); C.processText(c); C.processText(d);
      for (let i = 0; i < 700; i++) C.processText(mk('كلمة مش رقم ' + i, scope));
      console.log(JSON.stringify({missed: C.missed.size, hasA: C.missed.has('جملة عامية جديدة مش معروفة'), hasB: C.missed.has('اللي كتبه العميل بنفسه'), d: d.nodeValue, a: a.nodeValue}))"""))
    assert r['hasA'] is True and r['hasB'] is False
    assert r['missed'] == 500                                   # الحدّ الأقصى
    assert r['d'] == 'أعد الأموال إلى صاحب الطلب' and r['a'] == 'جملة عامية جديدة مش معروفة'


@needs_node
def test_copy_translates_field_labels_but_leaves_typed_textarea_text_and_the_row_own_data_alone():
    r = _vm(_fake_node_vm("""
      h.win.INBOX = [{details: [{k: 'ليه عايز ينضم', v: 'عايزة أنضم'}], who: 'هالة'}]; h.ctx.selected = 0;
      const scope = ['.drawer'];
      const own = mk('ليه عايز ينضم', scope), own2 = mk('عايزة أنضم', scope);
      const ta1 = mk('ابعتلنا رقم قيدك بالنقابة — أو رابط صورة الكارنيه — واكتبه في خانة «رقم القيد» في الاستمارة.', scope, 'TEXTAREA'); ta1.parentNode.value = ta1.parentNode.defaultValue = 'x';
      const ta2 = mk('ابعتلنا رقم قيدك بالنقابة — أو رابط صورة الكارنيه — واكتبه في خانة «رقم القيد» في الاستمارة.', scope, 'TEXTAREA'); ta2.parentNode.value = 'كتبه المؤسس'; ta2.parentNode.defaultValue = 'x';
      C.processText(own); C.processText(own2); C.processText(ta1); C.processText(ta2);
      console.log(JSON.stringify({own: own.nodeValue, own2: own2.nodeValue, ta1: ta1.nodeValue.slice(0, 12), ta2: ta2.nodeValue.slice(0, 8), missed: [...C.missed]}))"""))
    assert r['own'] == 'سبب طلب الانضمام'                       # عنوان الحقل كتبه الداشبورد فيُترجَم
    assert r['own2'] == 'عايزة أنضم' and r['missed'] == []      # وكلام الناس (القيمة) يبقى كما كُتب
    assert r['ta1'].startswith('يُرجى') and r['ta2'].strip() == 'ابعتلنا'          # المكتوب باليد لا يُلمس


@needs_node
def test_strict_mode_keeps_short_words_for_people_and_platform_text():
    r = _node("""console.log(JSON.stringify([L.v2hCopy('أقدر أطلق دلوقتي؟'), L.v2hCopy('أقدر أطلق دلوقتي؟', true), L.v2hCopy('ما قدرناش نجيب القضية دلوقتي — اقفل الدرج وافتحه تاني', true),
      L.v2hCopy('الفلوس دي رجعت للعميل يدوي قبل كده', true)]))""")
    assert r[0] == 'أقدر أطلق الآن؟' and r[1] is None            # العبارة القصيرة لا تمسّ كلام الناس
    assert r[2] == 'تعذّر جلب القضية الآن — أغلق التفاصيل وافتحها من جديد'
    assert r[3] == 'أُعيدت هذه الأموال إلى صاحب الطلب يدويًا من قبل'


@needs_node
def test_old_screen_names_in_the_drawer_become_the_new_place_names():
    r = _vm(_fake_node_vm("""
      h.win.INBOX = [{dest: 'escrow', apiKind: 'manual_payment', who: 'سلمى'}, {dest: 'team', apiKind: 'trainer'}]; h.ctx.selected = 0;
      h.ctx.MODULES_LOOKUP = {escrow: {label: 'الضمان والنزاعات'}, team: {label: 'الخبراء والمدربون'}};
      const scope = ['.drawer'];
      const a = mk('الضمان والنزاعات', scope), b = mk('فتح الضمان والنزاعات', scope), c = mk('الخبراء والمدربون', scope);
      C.processText(a); C.processText(b); C.processText(c);
      h.ctx.selected = 1; const d = mk('الخبراء والمدربون', scope); C.processText(d);
      console.log(JSON.stringify([a.nodeValue, b.nodeValue, c.nodeValue, d.nodeValue]))"""))
    assert r == ['الفلوس', 'افتح الفلوس', 'الخبراء والمدربون', 'الدورات والمدرّبون']      # لكل صف مكانه (الصف الأول لا يغيّر اسم «الخبراء»)


# محاكاة أصدق لـ`closest`: `own` = أصناف العنصر نفسه، `anc` = أصناف الأسلاف. يدعم القائمة بفاصلة وعلاقة «سليل» بمسافة.
_FAKE_DOM = """
const mk2 = (txt, own, anc, tag) => {
  const el = { nodeType: 1, tagName: tag || 'DIV', value: '', defaultValue: '',
    closest(sel) {
      return sel.split(',').some(one => {
        const toks = one.trim().split(/\\s+/), last = toks.pop();
        if (!own.includes(last)) return false;
        return toks.every(t => anc.includes(t));
      }) ? this : null;
    } };
  return { nodeType: 3, nodeValue: txt, parentNode: el };
};
"""


@needs_node
def test_drawer_outside_the_inbox_view_is_never_rewritten():
    """درج جهات الاتصال والمستثمرين والأسواق والمستخدمين والدورات يشارك صنف `.drawer`: أسماء الناس فيه لا تُمسّ أبدًا."""
    r = _vm(_fake_node_vm(_FAKE_DOM + """
      const names = ['شركة الشغل للمقاولات', 'أريد استرجاع فلوس الدورة', 'العميل المميز', 'رجّع الفلوس'];
      const outside = names.map(t => mk2(t, ['.drawer'], []));              // درج قسم آخر: لا `.v2h` فوقه
      const inside = names.map(t => mk2(t, ['.drawer'], ['.v2h']));        // درج الوارد
      outside.forEach(n => C.processText(n)); inside.forEach(n => C.processText(n));
      console.log(JSON.stringify({out: outside.map(n => n.nodeValue), inn: inside.map(n => n.nodeValue), missed: [...C.missed]}))"""))
    assert r['out'] == ['شركة الشغل للمقاولات', 'أريد استرجاع فلوس الدورة', 'العميل المميز', 'رجّع الفلوس']
    assert r['inn'][3] == 'أعد الأموال إلى صاحب الطلب'                      # وفي الوارد تعمل الطبقة كما كانت
    assert r['missed'] == []


@needs_node
def test_modal_and_toasts_outside_the_inbox_use_long_phrases_only():
    r = _vm(_fake_node_vm(_FAKE_DOM + """
      const a = mk2('شركة الشغل', ['#epModal'], []), b = mk2('ما قدرناش نجيب القضية دلوقتي — اقفل الدرج وافتحه تاني', ['#toasts'], []);
      C.processText(a); C.processText(b);
      console.log(JSON.stringify([a.nodeValue, b.nodeValue]))"""))
    assert r[0] == 'شركة الشغل' and r[1].startswith('تعذّر جلب القضية')


def test_scope_selector_pins_the_drawer_to_the_inbox_mount():
    assert "var SCOPE = '.v2h .drawer,#epModal,#toasts';" in HOME_JS
    assert "'.drawer,#epModal" not in HOME_JS                                # الصيغة القديمة (كل الأقسام) ممنوعة


@needs_node
def test_row_badges_and_warn_line_reach_the_ticket_without_duplicates():
    r = _node("""const row = {urgent: 1, contract: 1, noCandidate: 1, needsAttention: 1, warnLine: 'فلوس الملف لم تتحرك',
      badges: [{w: true, attn: true, t: 'محتاج تدخّلك'}, {w: true, t: '⚡ مستعجل'}, {w: true, t: 'مالوش خبير متاح'}, {t: 'مراجعة عقد', tip: 'مراجعة عقد قبل التوقيع'},
               {w: true, t: '⏳ فاضل أقل من ١٢ ساعة', tip: 'لو ما اتستلمش قبل الميعاد، فلوس العميل بترجع لوحدها'}, {t: 'خبير اعتذر'}, {t: 'قانون العمل'}, {w: true, t: '⚠️ البلد مختلف'}]};
      console.log(JSON.stringify({f: L.v2hFlags(row), w: L.v2hWarn(row), none: L.v2hFlags({badges: [{t: ''}, null]}), nowarn: L.v2hWarn({})}))""")
    t = [x['t'] for x in r['f']]
    assert t[:4] == ['مستعجل', 'مراجعة عقد', 'لا خبير متاح', 'يحتاج تدخّلك']
    assert len(t) == len(set(t))                                           # لا تكرار
    assert not any('محتاج تدخّلك' in x or 'مالوش' in x for x in t)
    assert any('أقل من' in x and 'ساعة' in x for x in t)
    warn = [x for x in r['f'] if 'ساعة' in x['t']][0]
    assert warn.get('w') is True and 'العميل' not in warn.get('tip', '')    # التلميح بالنص المبسّط
    assert 'خبير اعتذر' in t and 'قانون العمل' in t and 'البلد مختلف' in t and not any(x.startswith('⚠') or x.startswith('⏳') for x in t)
    assert r['w'] == 'فلوس الملف لم تتحرك' and r['none'] == [] and r['nowarn'] == ''


def test_ticket_renders_flags_with_warning_tone_and_the_stuck_money_line():
    assert "L.v2hWarn(it.row)" in HOME_JS and "(f.w ? ' w' : '')" in HOME_JS and 'class="v2h-warn"' in HOME_JS
    assert '.v2h-flag.w' in HOME_CSS and '.v2h-warn' in HOME_CSS


def test_card_texts_say_the_requester_not_the_customer_at_the_source():
    """التسمية المحايدة في مصدر البطاقات المشتركة، لا بنص استبدال وقت العرض."""
    src = LOGIC[LOGIC.index('function v2Card'):LOGIC.index('// ===== v2s:home =====')] if 'function v2Card' in LOGIC else LOGIC
    assert "'العميل: '" not in src and "'العميل ينتظر" not in src
    assert 'صاحب الطلب: ' in src
    assert 'function neutral' not in HOME_JS and 'neutral(' not in HOME_JS


def test_ticket_button_for_a_file_preselects_the_suggested_expert_in_the_existing_picker():
    assert 'function openPicker(card)' in HOME_JS
    assert "if (tb.drawerA === 'ef_pick') openPicker(tc);" in HOME_JS
    body = HOME_JS[HOME_JS.index('function openPicker(card)'):HOME_JS.index('function focusTarget(')]
    assert 'expertFileSend' not in body and 'confirmed' not in body       # لا إرسال من هنا: يبقى بزر القائمة نفسها
    assert "'.ef-cand .nm'" in HOME_JS or '.ef-cand .nm' in HOME_JS      # اسم الخبير لا تلمسه طبقة النصوص


def test_bell_dot_sits_on_the_button_corner_not_on_the_count():
    assert '.v2h-bn.dot:not(:empty)::after' not in HOME_CSS
    assert '#bellBtn.v2h-hd::after' in HOME_CSS and "classList.toggle('v2h-hd'" in HOME_JS


def test_mobile_header_is_compacted_so_the_first_ticket_is_near_the_top():
    m = HOME_CSS[HOME_CSS.index('@media(max-width:760px){\n  .app.v2-shell .v2h-top'):]
    m = m[:m.index('@media(min-width:761px)')]
    assert '.v2h-top{flex-wrap:nowrap' in m and '.v2h-autot span{display:none}' in m and '.v2h-bl span{display:block;white-space:nowrap' in m


# ---------------------------------------------------------------- ٥) الكتابة المرئية في home.js

def _visible_strings():
    out = []
    for m in re.finditer(r"'((?:\\.|[^'\\\n])*)'|\"((?:\\.|[^\"\\\n])*)\"|`((?:\\.|[^`\\])*)`", HOME_JS):
        t = m.group(1) or m.group(2) or m.group(3) or ''
        if re.search(r'[\u0600-\u06FF]', t):
            out.append(t)
    return out


def test_home_js_visible_copy_is_plain_arabic_without_markers_or_banned_words():
    for t in _visible_strings():
        if t in COLLOQ or t == 'يقوّم':
            continue                          # مقارنة الكود بقائمة العلامات، لا نصًّا ظاهرًا
        assert 'يقوّم' not in t, t
        assert not re.match(r'^(ذكاء|الذكاء|AI)', t.strip()), t
        assert not has_marker(t), t


def test_logic_helper_outputs_have_no_latin_letters_in_titles():
    for t in ('رسالة جديدة من نموذج التواصل', 'طلب سحب من مستثمر ينتظر المراجعة', 'طلب انضمام مدرّب جديد', 'حساب جديد على المنصة', 'افتح وقرّر'):
        assert t in LOGIC


def test_dialect_keys_live_only_in_the_dictionary_file():
    """اختبار D1 بيمنع العامية في مصدر v2-logic.js — فالقاموس (مفاتيحه عامية) في `v2s/home_copy.js` لوحده."""
    for w in ('الفلوس واقفة', 'فلوسها واقفة', 'بعدين', 'اقبله'):
        assert w not in re.sub(r'/\*.*?\*/', '', LOGIC, flags=re.S).replace('//', '\n//')
    assert 'رجّع الفلوس' in COPY_JS and 'رجّع الفلوس' not in LOGIC
