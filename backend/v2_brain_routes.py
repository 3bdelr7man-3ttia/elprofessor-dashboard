# -*- coding: utf-8 -*-
"""الجولة الأخيرة · قسم «العقل» (المفتاح `brain`): قواعده وسجل اليوم ومساعدوه — مسارات الخادم.

SPEC: docs/v2/final/SPEC-brain.md §3. تسجيل واحد من app.py:
    from v2_brain_routes import register as _v2_brain_register; _v2_brain_register(app, globals())

قواعد ثابتة في كل المسارات:
  * أدمن بس + المفتاح (`DASH_V2_ENABLED`) مفتوح، وإلا ٤٠٤ بلا أي نداء للمنصة.
  * `Cache-Control: no-store` على كل رد.
  * ⛔ لا يستدعي أي مسار هنا `ai_call` أو أي خدمة خارجية غير بروكسي المنصة، ولا يعيد محاولة.
  * ⛔ مصدر فاشل ⇒ `null` (والرد ٢٠٠)، لا قائمة فاضية ولا صفر مختلق.
  * ⛔ لا بيانات عميل ولا مبالغ في ردّ السجل (قايمة بيضا بالحقول).
المساعدات تُقرأ من `ns` (= globals() في app.py) وقت الطلب لا وقت التسجيل، لأن بعضها يُعرَّف بعد سطر التسجيل.
"""
import datetime
import json
import re
import uuid

from flask import jsonify, request

RULE_ID_RE = re.compile(r'^[0-9a-f]{32}$')
RULE_MIN, RULE_MAX, RULES_CAP = 6, 300, 50
SINCE_MAX_DAYS = 8
TITLE_MAX = 80
WHY_MAX = 300
HISTORY_ACTIONS = ('expert_file.auto_assign', 'v2_brain.rule_add', 'v2_brain.rule_delete')
_CTRL_RE = re.compile(r'[\x00-\x1f\x7f-\x9f‎‏‪-‮]')
_MODEL = {}


def _utc_iso(dt):
    """وقت بلا منطقة (SQLite) = UTC دائمًا، ويخرج بمنطقته."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).isoformat()


_ISO_RE = re.compile(r'^(\d{4})-(\d\d)-(\d\d)(?:[T ](\d\d):(\d\d)(?::(\d\d)(?:[.,](\d+))?)?)?\s*(Z|z|[+-]\d\d:?\d\d)?$')


def parse_iso(value):
    """ISO ⇒ datetime بمنطقة UTC، وإلا None. بلا منطقة ⇒ UTC. يقرأ الكسور بأي طول (بايثون ٣٫٩ لا يقرأ إلا ٣ أو ٦ منازل)،
    و«+» التي حوّلها الاستعلام إلى فراغ (`...00:00` بدل `+00:00`)."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    s = re.sub(r'(?<=\d) (\d\d:?\d\d)$', r'+\1', s) if re.search(r'T\d\d:\d\d(:\d\d)?([.,]\d+)? \d\d:?\d\d$', s) else s
    m = _ISO_RE.match(s)
    if not m:
        return None
    y, mo, d, h, mi, sec, frac, tz = m.groups()
    try:
        dt = datetime.datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(sec or 0), int(((frac or '0') + '000000')[:6]))
    except ValueError:
        return None
    if tz and tz not in ('Z', 'z'):
        sign = 1 if tz[0] == '+' else -1
        digits = tz[1:].replace(':', '')
        dt = dt - sign * datetime.timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
    return dt.replace(tzinfo=datetime.timezone.utc)


def clean_rule_text(value):
    if not isinstance(value, str):
        return ''
    return re.sub(r'\s+', ' ', _CTRL_RE.sub(' ', value)).strip()


def _short(value, n):
    if not isinstance(value, str):
        return ''
    s = re.sub(r'\s+', ' ', value).strip()
    return s[:n]


def _email(v):
    return v.strip().lower() if isinstance(v, str) and '@' in v else ''


def build_entries(files, since):
    """صفوف الجسر ⇒ مدخلات السجل (قايمة بيضا). ⛔ لا عميل ولا مبلغ ولا عملة."""
    out = []
    for f in files:
        if not isinstance(f, dict):
            continue
        log = f.get('assign_log')
        if not isinstance(log, list) or not log:
            continue
        names = {}
        for c in (f.get('candidates') if isinstance(f.get('candidates'), list) else []):
            if isinstance(c, dict) and _email(c.get('email')) and isinstance(c.get('name'), str) and c['name'].strip():
                names[_email(c['email'])] = c['name'].strip()
        for d in (f.get('declined') if isinstance(f.get('declined'), list) else []):
            if isinstance(d, dict) and _email(d.get('email')) and isinstance(d.get('name'), str) and d['name'].strip():
                names.setdefault(_email(d['email']), d['name'].strip())
        for ek, nk in (('assigned_to', 'assigned_name'), ('expert_email', 'expert_name')):
            if _email(f.get(ek)) and isinstance(f.get(nk), str) and f[nk].strip():
                names[_email(f[ek])] = f[nk].strip()
        last = log[-1] if isinstance(log[-1], dict) else {}
        status = f.get('status') if isinstance(f.get('status'), str) else ''
        assigned_to = _email(f.get('assigned_to'))
        for e in log:
            if not isinstance(e, dict):
                continue
            at = parse_iso(e.get('at'))
            to = _email(e.get('to'))
            if at is None or at < since or not to:
                continue
            by = 'auto' if e.get('by') == 'auto' else 'founder'
            name = e.get('to_name') if isinstance(e.get('to_name'), str) and e['to_name'].strip() else names.get(to)
            reason = e.get('reason') if isinstance(e.get('reason'), str) else ''
            out.append({
                'file_id': str(f.get('id') or '')[:80],
                'title': _short(f.get('title'), TITLE_MAX),
                'status': status,
                'at': at.isoformat(),
                'by': by,
                'reason': reason[:30],
                'why': _short(e.get('why'), WHY_MAX),
                'to_email': to,
                'to_name': name.strip()[:120] if isinstance(name, str) and name.strip() else None,
                'pre_claim': status == 'assigned',
                'current': bool(e is last and to == assigned_to),
            })
    out.sort(key=lambda x: x['at'], reverse=True)
    return out


def _model(db):
    if 'cls' in _MODEL:
        return _MODEL['cls']

    class V2BrainRule(db.Model):
        """قاعدة طلبها المؤسس بنص حر: تُحفظ للمراجعة فقط ولا يقرؤها شيء ليعمل بها (الحالة دائمًا requested)."""
        __tablename__ = 'v2_brain_rules'
        __table_args__ = {'extend_existing': True}
        id = db.Column(db.String(32), primary_key=True)
        text = db.Column(db.Text, nullable=False)
        status = db.Column(db.String(16), nullable=False, default='requested')
        created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
        created_by = db.Column(db.String(255))

    _MODEL['cls'] = V2BrainRule
    return V2BrainRule


def register(app, ns):
    db = ns['db']
    Rule = _model(db)
    token_required = ns['token_required']
    roles_required = ns['roles_required']

    def L(name):
        return ns[name]

    def out(payload, status=200):
        return L('_v2_ns')((jsonify(payload), status) if status != 200 else jsonify(payload))

    def row_out(r):
        return {'id': r.id, 'text': r.text, 'status': r.status or 'requested',
                'created_at': _utc_iso(r.created_at), 'created_by': r.created_by or ''}

    # ------------------------------------------------------------------ B1 · سجل اليوم
    @app.route('/api/v2/brain/today', methods=['GET'], endpoint='v2_brain_today')
    @token_required
    @roles_required('admin')
    def v2_brain_today():
        closed = L('_v2_closed')()
        if closed:
            return closed
        since = parse_iso(request.args.get('since'))
        if since is None:
            return out({'error': 'تاريخ غير صالح'}, 400)
        now = datetime.datetime.now(datetime.timezone.utc)
        since = max(min(since, now), now - datetime.timedelta(days=SINCE_MAX_DAYS))
        resp = L('_ef_bridge')('GET', '/api/bridge/expert-files', params={'status': 'all'})
        if not L('_resp_ok')(resp):
            missing = isinstance(resp, tuple) and int(resp[1]) == 404
            body = {'files_ok': False, 'entries': None}
            if missing:
                body['missing'] = True
            return out(body)
        data = L('_proxy_json')(resp)
        files = data.get('files')
        if not isinstance(files, list):
            return out({'files_ok': False, 'entries': None})
        entries = build_entries(files, since)
        total = data.get('total') if isinstance(data.get('total'), int) and not isinstance(data.get('total'), bool) else None
        oldest = None
        for f in files:
            t = parse_iso(f.get('updated_at')) if isinstance(f, dict) else None
            if t is not None and (oldest is None or t < oldest):
                oldest = t
        partial = bool(total is not None and total > len(files) and (oldest is None or oldest >= since))
        mode = data.get('service_mode')
        return out({'files_ok': True, 'partial': partial,
                    'service': mode if mode in ('open', 'allowlist', 'closed') else None,
                    'entries': entries})

    # ------------------------------------------------------------------ B2 · المفتاح والقيم والتاريخ
    @app.route('/api/v2/brain/rules', methods=['GET'], endpoint='v2_brain_rules_get')
    @token_required
    @roles_required('admin')
    def v2_brain_rules_get():
        closed = L('_v2_closed')()
        if closed:
            return closed
        auto, auto_missing = None, False
        resp = L('_ef_bridge')('GET', '/api/bridge/expert-files/settings')
        if L('_resp_ok')(resp):
            d = L('_proxy_json')(resp)
            if isinstance(d.get('auto_assign'), bool):
                at = d.get('updated_at')
                by = d.get('updated_by')
                auto = {'value': d['auto_assign'],
                        'explicit': d['explicit'] if isinstance(d.get('explicit'), bool) else None,
                        'updated_at': _utc_iso(parse_iso(at)) if isinstance(at, str) and parse_iso(at) else None,
                        'updated_by': by.strip()[:120] if isinstance(by, str) and by.strip() else None}
        elif isinstance(resp, tuple) and int(resp[1]) == 404:
            auto_missing = True
        release = None
        resp2 = L('_platform_proxy')('GET', '/api/policies')
        if L('_resp_ok')(resp2):
            esc_ = L('_proxy_json')(resp2).get('escrow')
            v = esc_.get('auto_release_hours') if isinstance(esc_, dict) else None
            if type(v) is int and v > 0:
                release = v
        requested = [row_out(r) for r in Rule.query.order_by(Rule.created_at.desc(), Rule.id.desc()).limit(RULES_CAP).all()]
        AuditLog = L('AuditLog')
        history = []
        for r in AuditLog.query.filter(AuditLog.action.in_(HISTORY_ACTIONS)).order_by(AuditLog.id.desc()).limit(20).all():
            try:
                meta = json.loads(r.meta_json) if r.meta_json else None
            except (TypeError, ValueError):
                meta = None
            history.append({'at': _utc_iso(r.created_at), 'actor_email': r.actor_email or '', 'action': r.action, 'meta': meta})
        body = {'auto_assign': auto, 'release_hours': release, 'requested': requested, 'history': history}
        if auto_missing:
            body['auto_assign_missing'] = True
        return out(body)

    # ------------------------------------------------------------------ B3 · حالة تحديثات اليوم
    @app.route('/api/v2/brain/helpers-status', methods=['GET'], endpoint='v2_brain_helpers_status')
    @token_required
    @roles_required('admin')
    def v2_brain_helpers_status():
        closed = L('_v2_closed')()
        if closed:
            return closed
        import os
        configured = any(os.environ.get(c['env_key']) for c in L('AI_PROVIDERS').values())
        st = L('ai_daily_usage_state')()
        cap = st.get('cap') if isinstance(st.get('cap'), int) and st.get('cap') > 0 else None
        broken = bool(st.get('counter_error'))
        used = None if broken else int(st.get('used') or 0)
        remaining = None if (cap is None or broken) else max(0, cap - used)
        # الكاتب الحالي: 'main' (الأساسي) · 'backup' (الاحتياطي) · None (لا أحد). ⛔ لا اسم مزوّد من البيئة يخرج؛ ومفتاح القاعدة يعلو ويخرج اسمه (writer_label).
        from brain2 import engine as _engine
        ws = _engine.writer_state(ns)
        writer = ws['writer']
        payload = {'configured': bool(configured or writer is not None), 'cap': cap, 'used': used, 'remaining': remaining,
                   'blocked': bool(st.get('blocked')) and cap is not None, 'writer': writer}
        if ws['label']:
            payload['writer_label'] = ws['label']
        return out(payload)

    # ------------------------------------------------------------------ B4 · قاعدة تريدها
    @app.route('/api/v2/brain/rules', methods=['POST'], endpoint='v2_brain_rules_add')
    @token_required
    @roles_required('admin')
    def v2_brain_rules_add():
        closed = L('_v2_closed')()
        if closed:
            return closed
        body = L('_v2_body')()
        bad = L('_v2_confirmed')(body)
        if bad:
            return bad
        text = clean_rule_text(body.get('text'))
        if len(text) < RULE_MIN or len(text) > RULE_MAX:
            return out({'error': 'اكتب القاعدة في جملة واحدة واضحة (٦ أحرف على الأقل)'}, 400)
        if Rule.query.count() >= RULES_CAP:
            return out({'error': 'وصلت إلى ٥٠ قاعدة محفوظة. احذف واحدة قبل إضافة غيرها'}, 409)
        row = Rule(id=uuid.uuid4().hex, text=text, status='requested', created_at=datetime.datetime.utcnow(),
                   created_by=L('_actor_email')())
        db.session.add(row)
        db.session.commit()
        L('_audit')('v2_brain.rule_add', target=row.id, meta={'text': text[:120]})
        return out(row_out(row))

    # ------------------------------------------------------------------ B5 · حذف قاعدة
    @app.route('/api/v2/brain/rules/<rule_id>', methods=['DELETE'], endpoint='v2_brain_rules_delete')
    @token_required
    @roles_required('admin')
    def v2_brain_rules_delete(rule_id):
        closed = L('_v2_closed')()
        if closed:
            return closed
        body = L('_v2_body')()
        bad = L('_v2_confirmed')(body)
        if bad:
            return bad
        if not RULE_ID_RE.match(rule_id or ''):
            return out({'error': 'معرّف غير صالح'}, 400)
        row = Rule.query.get(rule_id)
        if row is None:
            return out({'error': 'هذه القاعدة غير موجودة'}, 404)
        text = row.text or ''
        db.session.delete(row)
        db.session.commit()
        L('_audit')('v2_brain.rule_delete', target=rule_id, meta={'text': text[:120]})
        return out({'ok': True})
