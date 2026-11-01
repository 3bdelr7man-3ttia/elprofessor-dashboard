# -*- coding: utf-8 -*-
"""«السوق v4» في الداشبورد — خمس قطع على شاشة السوق (docs/v2/market4/SPEC.md). بروكسيات رفيعة فوق جسور المنصة:

    GET  /api/v2/market/suggestions                  ⇒ /api/bridge/market/suggestions               (طابور «أخرى»)
    POST /api/v2/market/suggestions/<id>/decide      ⇒ /api/bridge/market/suggestions/<id>/decide
    GET  /api/v2/market/catalog                      ⇒ /api/bridge/market/catalog                   (مدى الأسعار)
    PUT  /api/v2/market/catalog/<slug>/anchor        ⇒ /api/bridge/market/catalog/<slug>/anchor
    GET  /api/v2/market/orgs                         ⇒ /api/bridge/market/orgs                      (المكاتب)
    POST /api/v2/market/orgs/<id>/verify-reg         ⇒ /api/bridge/market/orgs/<id>/verify-reg      («وثّق السجل»)
    GET  /api/v2/market/licence-files/<file_id>      ⇒ /api/bridge/market/licence-files/<file_id>   (ملف الترخيص: بايتات)

الطلبات المفتوحة (القطعة ٤) بتقرا من المسار الموجود `GET /api/v2/market/requests` (v2_market_routes) — ما فيهاش مسار جديد.
المنح بالبلاد (القطعة ٥) بيمرّ على المسار الموجود `POST /api/platform-join-requests/<id>/approve` (app.py) بحقل `licensed_countries`.

نفس قواعد `v2_books_ours_routes.py` / `v2_market_routes.py`:
  * المفتاح (`DASH_V2_ENABLED`) مقفول ⇒ ٤٠٤ بلا أي نداء للمنصة · `Cache-Control: no-store` على كل رد.
  * القراءة والكتابة للأدمن بس (فيها إيميلات الناس)؛ ملف الترخيص للأدمن والموظف (زي طابور طلبات الانضمام اللي بيشوفه الموظف).
  * كل كتابة تطلب `confirmed: true` بالظبط من المتصفح، وإلا ٤٠٠ قبل أي نداء. `by` من التوكن وحده (اللي في الجسم بيتجاهل).
  * الجسم المبعوت للمنصة من قايمة بيضا بالحقول، والردود مفلترة بقايمة بيضا كمان (ولا حقل زيادة بيعدّي).
  * ⛔ نداء واحد ولا إعادة محاولة. رد ضاع (٥٠٠/٥٠٢/٥٠٣/٥٠٤) على كتابة ⇒ ٥٠٢ و`no_reply:true` «لم يصل رد…» مش «اترفض».
    نص `detail` العربي من المنصة (٤٠٤ · ٤٠٩ · ٤٢٢) بيعدّي كما هو بنفس الكود.
  * قراءة غابت من المنصة (٤٠٤ بلا ردّ عن عنصر) ⇒ `bridge_missing:true` والشاشة تكتب «غير متاح بعد» مش «لا شيء».
  * تدقيق عند النجاح بس، بالإجراء وبما حدث (مفاتيح وأعداد، لا نص حر).
  * مدى السعر: التحقق هنا قبل أي نداء (أعداد صحيحة · الأدنى < الأعلى · زوج كامل أو لا شيء · العملات السبع)، والمنصة تعيد التحقق.

`register(app, g)` بتتنادى من app.py بسطر واحد (محروس)، و`g` = globals() بتاعته.
"""
import re
from urllib.parse import quote

NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
MISSING_AR = 'سوق الخدمات الجديد غير متاح بعد على المنصة'
BAD_ID_AR = 'معرّف غير صالح'
BAD_DECISION_AR = 'اختر: اعتماد أو رفض'
BAD_CODE_AR = 'قيمة غير صالحة'
FILE_MISSING_AR = 'ملف الترخيص غير متاح'
FILE_BAD_AR = 'تعذّر عرض هذا الملف'

SUG_STATUSES = ('pending', 'approved', 'rejected', 'all')
ORG_STATUSES = ('pending', 'active', 'suspended', 'all')
CURRENCIES = ('EGP', 'SAR', 'AED', 'QAR', 'KWD', 'OMR', 'USD')
Q_MAX = 120
SCOPE_MAX = 600
CODE_RE = re.compile(r'^[a-z][a-z0-9_]{0,39}$')
SLUG_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')
FILE_ID_RE = re.compile(r'^[A-Za-z0-9_-]{8,64}$')
NUM_MAX = 10 ** 9
FILE_MAX = 11 * 1024 * 1024

SUG_FIELDS = ('id', 'user_email', 'org_id', 'name', 'note', 'status', 'created_slug', 'decided_by', 'decided_at', 'created_at')
CAT_FIELDS = ('slug', 'name', 'service_type', 'specialty', 'specialty_label', 'pricing_mode', 'licensed', 'status', 'has_range')
ORG_FIELDS = ('id', 'name', 'city', 'country', 'founded_year', 'status', 'created_at', 'badge')
MEMBER_FIELDS = ('email', 'role', 'verified_lawyer')
REG_FIELDS = ('url', 'verified_by', 'verified_at')

_SNIFF = (
    (b'%PDF-', 'application/pdf'),
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'\xff\xd8\xff', 'image/jpeg'),
)


def sniff_type(raw):
    """نوع الملف من البايتات وحدها (pdf · png · jpeg · webp): ما نثقش في رأس الرد. غير كده ⇒ None."""
    for magic, kind in _SNIFF:
        if raw.startswith(magic):
            return kind
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'image/webp'
    return None


def _pick(d, keys):
    return {k: d[k] for k in keys if k in d} if isinstance(d, dict) else {}


def _http_url(u):
    """رابط السجل التجاري: http(s) بس. أي شيء تاني ⇒ '' (ولا رابط javascript: يوصل الشاشة)."""
    u = u.strip() if isinstance(u, str) else ''
    return u[:600] if re.match(r'^https?://', u, re.I) else ''


def view_suggestions(d):
    if not isinstance(d, dict) or not isinstance(d.get('items'), list):
        return None
    items = [_pick(r, SUG_FIELDS) for r in d['items'] if isinstance(r, dict)]
    return {'items': items, 'total': d.get('total') if isinstance(d.get('total'), int) else len(items),
            'pending': d.get('pending') if isinstance(d.get('pending'), int) else None, 'status': d.get('status')}


def view_catalog(d):
    if not isinstance(d, dict) or not isinstance(d.get('items'), list):
        return None
    items = []
    for r in d['items']:
        if not isinstance(r, dict):
            continue
        row = _pick(r, CAT_FIELDS)
        ar = r.get('anchor_range')
        row['anchor_range'] = {k: v for k, v in ar.items() if k in CURRENCIES and isinstance(v, list) and len(v) == 2} if isinstance(ar, dict) else None
        items.append(row)
    cur = [c for c in (d.get('currencies') or []) if c in CURRENCIES] or list(CURRENCIES)
    return {'items': items, 'total': d.get('total') if isinstance(d.get('total'), int) else len(items), 'currencies': cur,
            'no_range_count': d.get('no_range_count') if isinstance(d.get('no_range_count'), int) else None}


def view_orgs(d):
    if not isinstance(d, dict) or not isinstance(d.get('items'), list):
        return None
    items = []
    for r in d['items']:
        if not isinstance(r, dict):
            continue
        row = _pick(r, ORG_FIELDS)
        reg = r.get('commercial_reg')
        if isinstance(reg, dict):
            row['commercial_reg'] = dict(_pick(reg, REG_FIELDS), url=_http_url(reg.get('url')))
        else:
            row['commercial_reg'] = None
        row['members'] = [_pick(m, MEMBER_FIELDS) for m in (r.get('members') or []) if isinstance(m, dict)][:50]
        items.append(row)
    return {'items': items, 'total': d.get('total') if isinstance(d.get('total'), int) else len(items), 'status': d.get('status')}


def clean_anchor(raw):
    """(None=مسح | {عملة: [أدنى, أعلى]}، رسالة عربية | None). التحقق قبل أي نداء؛ المنصة تعيده.
    ⛔ لا كسور ولا منطقي ولا نص (٢٥٠٠ مش «2500»)، والأدنى ≥ ٠ والأقل من الأعلى، والزوج كامل أو لا شيء."""
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, 'مدى السعر غير صالح'
    out = {}
    for key, val in raw.items():
        cur = str(key).upper()
        if cur not in CURRENCIES:
            return None, 'عملة غير معروفة'
        if val is None:
            continue
        if not isinstance(val, (list, tuple)) or len(val) != 2:
            return None, 'اكتب الأدنى والأعلى معًا (%s)' % cur
        nums = []
        for n in val:
            if n is None:
                return None, 'اكتب الأدنى والأعلى معًا (%s)' % cur
            if isinstance(n, bool) or not isinstance(n, (int, float)) or n != int(n) or n < 0 or n > NUM_MAX:
                return None, 'اكتب أرقامًا صحيحة بلا كسور (%s)' % cur
            nums.append(int(n))
        if nums[0] >= nums[1]:
            return None, 'يجب أن يكون الأدنى أقل من الأعلى (%s)' % cur
        out[cur] = nums
    return (out or None), None


def register(app, g):
    token_required = g['token_required']
    roles_required = g['roles_required']
    jsonify = g['jsonify']
    request = g['request']
    ID_RE = g['V2_ID_RE']

    def ns(resp):
        return g['_v2_ns'](resp)

    def err(msg, code=400):
        return ns((jsonify({'error': msg}), code))

    def guard(ids=(), write=True):
        closed = g['_v2_closed']()
        if closed:
            return closed, None
        for i in ids:
            if not ID_RE.match(i or ''):
                return err(BAD_ID_AR), None
        body = g['_v2_body']() if write else {}
        if write:
            bad = g['_v2_confirmed'](body)
            if bad:
                return bad, None
        return None, body

    def read(path, params=None):
        resp = g['_platform_proxy']('GET', path, params=params, timeout=15)
        if g['_resp_ok'](resp):
            return resp, None
        if isinstance(resp, tuple) and int(resp[1]) == 404:
            return None, ns((jsonify({'error': MISSING_AR, 'bridge_missing': True}), 404))
        return None, ns(g['_v2_mask_auth'](resp))

    def write(method, path, fields, action, target, meta):
        body = dict(fields)
        body['by'] = g['_actor_email']()[:80]
        resp = g['_platform_proxy'](method, path, json_body=body, timeout=25)
        if g['_resp_ok'](resp):
            g['_audit'](action, target=target, meta=meta)
            return ns(resp)
        if g['_ef_no_reply'](resp):
            g['_audit']('market4.no_reply', target=target, meta={'attempt': action})
            return ns((jsonify({'error': NO_REPLY_AR, 'no_reply': True}), 502))
        return ns(g['_v2_mask_auth'](resp))

    def q(x):
        return quote(x, safe='')

    # ------------------------------------------------------------------ ١ · اقتراحات «أخرى»
    @app.route('/api/v2/market/suggestions', methods=['GET'], endpoint='v2m4_suggestions')
    @token_required
    @roles_required('admin')
    def v2m4_suggestions():
        bad, _ = guard(write=False)
        if bad:
            return bad
        status = (request.args.get('status') or 'pending').strip()
        if status not in SUG_STATUSES:
            status = 'pending'
        resp, fail = read('/api/bridge/market/suggestions', {'status': status, 'limit': 100})
        if fail:
            return fail
        view = view_suggestions(resp.get_json(silent=True))
        if view is None:
            return err('تعذر قراءة رد المنصة', 502)
        return ns(jsonify(view))

    @app.route('/api/v2/market/suggestions/<sid>/decide', methods=['POST'], endpoint='v2m4_suggestion_decide')
    @token_required
    @roles_required('admin')
    def v2m4_suggestion_decide(sid):
        bad, b = guard([sid])
        if bad:
            return bad
        decision = b.get('decision')
        if decision not in ('approve', 'reject'):
            return err(BAD_DECISION_AR)
        fields = {'decision': decision}
        meta = {'decision': decision}
        if decision == 'approve':
            for k in ('service_type', 'specialty'):
                v = b.get(k, '')
                if v is None:
                    v = ''
                if not isinstance(v, str) or (v.strip() and not CODE_RE.match(v.strip())):
                    return err(BAD_CODE_AR)
                fields[k] = v.strip()
            scope = b.get('scope', '')
            if scope is None:
                scope = ''
            if not isinstance(scope, str) or len(scope.strip()) > SCOPE_MAX:
                return err('النطاق طويل (حتى ٦٠٠ حرف)')
            fields['scope'] = scope.strip()
            meta.update({'service_type': fields['service_type'] or 'default', 'specialty': fields['specialty'] or 'default'})
        return write('POST', '/api/bridge/market/suggestions/%s/decide' % q(sid), fields, 'market4.suggestion_' + decision, sid, meta)

    # ------------------------------------------------------------------ ٢ · مدى الأسعار
    @app.route('/api/v2/market/catalog', methods=['GET'], endpoint='v2m4_catalog')
    @token_required
    @roles_required('admin')
    def v2m4_catalog():
        bad, _ = guard(write=False)
        if bad:
            return bad
        params = {'limit': 300}
        if (request.args.get('no_range') or '').strip().lower() in ('1', 'true'):
            params['no_range'] = '1'
        text = (request.args.get('q') or '').strip()[:Q_MAX]
        if text:
            params['q'] = text
        resp, fail = read('/api/bridge/market/catalog', params)
        if fail:
            return fail
        view = view_catalog(resp.get_json(silent=True))
        if view is None:
            return err('تعذر قراءة رد المنصة', 502)
        return ns(jsonify(view))

    @app.route('/api/v2/market/catalog/<slug>/anchor', methods=['PUT'], endpoint='v2m4_catalog_anchor')
    @token_required
    @roles_required('admin')
    def v2m4_catalog_anchor(slug):
        bad, b = guard()
        if bad:
            return bad
        if not SLUG_RE.match(slug or ''):
            return err(BAD_ID_AR)
        if 'anchor_range' not in b:
            return err('مدى السعر مطلوب (أو فارغ للمسح)')
        rng, msg = clean_anchor(b.get('anchor_range'))
        if msg:
            return err(msg, 422)
        meta = {'currencies': sorted(rng.keys()) if rng else [], 'cleared': rng is None}
        return write('PUT', '/api/bridge/market/catalog/%s/anchor' % q(slug), {'anchor_range': rng}, 'market4.anchor', slug, meta)

    # ------------------------------------------------------------------ ٣ · المكاتب
    @app.route('/api/v2/market/orgs', methods=['GET'], endpoint='v2m4_orgs')
    @token_required
    @roles_required('admin')
    def v2m4_orgs():
        bad, _ = guard(write=False)
        if bad:
            return bad
        status = (request.args.get('status') or 'pending').strip()
        if status not in ORG_STATUSES:
            status = 'pending'
        resp, fail = read('/api/bridge/market/orgs', {'status': status})
        if fail:
            return fail
        view = view_orgs(resp.get_json(silent=True))
        if view is None:
            return err('تعذر قراءة رد المنصة', 502)
        return ns(jsonify(view))

    @app.route('/api/v2/market/orgs/<org_id>/verify-reg', methods=['POST'], endpoint='v2m4_org_verify')
    @token_required
    @roles_required('admin')
    def v2m4_org_verify(org_id):
        bad, _b = guard([org_id])
        if bad:
            return bad
        return write('POST', '/api/bridge/market/orgs/%s/verify-reg' % q(org_id), {}, 'market4.verify_reg', org_id, {})

    # ------------------------------------------------------------------ ٥ · ملف الترخيص (بايتات)
    @app.route('/api/v2/market/licence-files/<file_id>', methods=['GET'], endpoint='v2m4_licence_file')
    @token_required
    @roles_required('admin', 'employee')
    def v2m4_licence_file(file_id):
        bad, _ = guard(write=False)
        if bad:
            return bad
        if not FILE_ID_RE.match(file_id or ''):
            return err(BAD_ID_AR)
        if not g['PLATFORM_METRICS_SECRET']:
            return err('لم يتم ضبط الربط بعد', 503)
        try:
            r = g['requests'].request('GET', '%s/api/bridge/market/licence-files/%s' % (g['PLATFORM_API_URL'], q(file_id)),
                                      headers={'X-ELP-Metrics-Secret': g['PLATFORM_METRICS_SECRET']}, timeout=20)
        except Exception:   # noqa: BLE001
            return err('تعذر الاتصال بالمنصة', 502)
        if r.status_code == 404:
            return err(FILE_MISSING_AR, 404)
        if r.status_code != 200:
            return err('تعذر جلب الملف من المنصة', 502)
        raw = r.content or b''
        kind = sniff_type(raw)
        if not raw or len(raw) > FILE_MAX or kind is None:
            return err(FILE_BAD_AR, 422)
        g['_audit']('market4.licence_file_view', target=file_id, meta={'type': kind, 'size': len(raw)})
        resp = g['Response'](raw, mimetype=kind)
        resp.headers['Cache-Control'] = 'no-store'
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['Content-Security-Policy'] = "default-src 'none'; sandbox"
        resp.headers['Content-Disposition'] = 'inline; filename="licence-file"'
        return resp
