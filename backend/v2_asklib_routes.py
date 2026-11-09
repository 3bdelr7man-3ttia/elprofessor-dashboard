# -*- coding: utf-8 -*-
"""«أدخل قوانين المكتبة» في الداشبورد (المحتوى ‹ أدخل قوانين المكتبة): مستندات مكتبة المنصة ⇒ تقسيمها مواد في قاعدة نصوص «اسأل».

    GET  /api/v2/ask/library                 ⇒ /api/bridge/ask/library-scan + /api/bridge/ask/corpus/stats   (قراءة: قائمة المستندات + ملخص القاعدة)
    POST /api/v2/ask/library/preview         ⇒ POST /api/bridge/ask/ingest-library {apply:false}              (جرّب التقسيم: لا كتابة ولا تدقيق)
    POST /api/v2/ask/library/ingest          ⇒ POST /api/bridge/ask/ingest-library {apply:true}               (أدخل المواد: تأكيد + `_v2_write` + تدقيق ask.ingest_library)

قواعد الملف (نفس `v2_tools_routes.py`):
  * أدمن بس · المفتاح `DASH_V2_ENABLED` مقفول ⇒ ٤٠٤ بلا أي نداء للمنصة · `no-store`.
  * الكتابة تطلب `confirmed: true` بالظبط قبل أي نداء، و`by` من التوكن وحده (`_v2_write`)، وتدقيق عند النجاح بس.
  * الجسم المبعوت للمنصة من قايمة بيضا، والردود مفلترة بقايمة بيضا.
  * الجسر لسه ما وصلش المنصة (٤٠٤ عام) ⇒ ٤٠٤ و`bridge_missing:true` والشاشة تكتب «الميزة لسه ما وصلتش المنصة». ٤٠٤ بنص عربي من المنصة (مستند مش موجود) بيعدّي كما هو.
  * ⛔ نداء واحد بلا إعادة محاولة. رد ضايع على الكتابة ⇒ ٥٠٢ و`no_reply:true` (من `_v2_write`).
  * ⛔ صفر ذكاء: التقسيم بالقواعد عند المنصة.
"""
import re

MISSING_AR = 'الميزة لسه ما وصلتش المنصة'
BAD_TRACK_AR = 'اختر التخصص'
BAD_REF_AR = 'معرّف المستند غير صالح'
BAD_LAW_AR = 'رقم القانون غير صالح (مثال 117/1958)'
SCAN_LIMIT = 500
_TRACK_RE = re.compile(r'^[a-z][a-z0-9-]{1,59}$')
_REF_RE = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
_LAW_RE = re.compile(r'^[^\x00-\x1f<>]{1,20}$')   # نفس سقف عقد المنصة (law ≤ ٢٠)
_GENERIC_404 = ('', 'not found', 'تعذر تنفيذ العملية')

ITEM_STR = ('id', 'title', 'law_number', 'law_key', 'country', 'category', 'specialization', 'suggested_track')
ITEM_NUM = ('chars', 'articles_found')
STATUSES = ('library', 'proposed', 'verified', 'rejected')


def _s(v, n=300):
    return v.strip()[:n] if isinstance(v, str) else ''


def _n(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else (int(v) if isinstance(v, float) and v >= 0 else None)


def view_item(it):
    if not isinstance(it, dict) or not _REF_RE.match(str(it.get('id') or '')):
        return None
    out = {k: (_s(it.get(k)) or None) for k in ITEM_STR}
    out['id'] = str(it['id'])
    for k in ITEM_NUM:
        out[k] = _n(it.get(k))
    ing = it.get('ingested') if isinstance(it.get('ingested'), dict) else {}
    by = ing.get('by_status') if isinstance(ing.get('by_status'), dict) else {}
    out['ingested'] = {'total': _n(ing.get('total')) or 0,
                       'by_status': {k: _n(by.get(k)) or 0 for k in STATUSES if _n(by.get(k))}}
    return out


def view_scan(d):
    if not isinstance(d, dict) or not isinstance(d.get('items'), list):
        return None
    items = [v for v in (view_item(i) for i in d['items']) if v]
    tracks = []
    for t in d.get('tracks') if isinstance(d.get('tracks'), list) else []:
        if isinstance(t, dict) and _TRACK_RE.match(str(t.get('id') or '')):
            tracks.append({'id': str(t['id']), 'label': _s(t.get('label'), 80) or str(t['id'])})
    return {'items': items, 'tracks': tracks, 'count': _n(d.get('count')) if _n(d.get('count')) is not None else len(items),
            'pending': _n(d.get('pending')) or 0}


def view_stats(d):
    """ملخص القاعدة: {articles:{تخصص:{حالة:عدد}}, corrections_approved:n}. شكل غير مفهوم ⇒ None (الشاشة تكتب «غير متاح بعد»)."""
    if not isinstance(d, dict) or not isinstance(d.get('articles'), dict):
        return None
    arts = {}
    for t, row in d['articles'].items():
        if isinstance(row, dict) and _TRACK_RE.match(str(t)):
            arts[str(t)] = {s: _n(row.get(s)) or 0 for s in STATUSES if _n(row.get(s))}
    return {'articles': arts, 'corrections_approved': _n(d.get('corrections_approved')) or 0}


def view_ingest(d):
    if not isinstance(d, dict):
        return None
    prev = []
    for p in (d.get('preview') if isinstance(d.get('preview'), list) else [])[:15]:
        if isinstance(p, dict):
            prev.append({'article_no': _s(str(p.get('article_no') if p.get('article_no') is not None else ''), 20),
                         'text': _s(p.get('text'), 700)})
    dups = []
    for x in (d.get('duplicates') if isinstance(d.get('duplicates'), list) else [])[:100]:
        dups.append(_s(str(x.get('article_no')) if isinstance(x, dict) and x.get('article_no') is not None else str(x), 40))
    out = {'articles': _n(d.get('articles')) or 0, 'preview': prev, 'duplicates': dups,
           'applied': d.get('applied') is True, 'law_key': _s(d.get('law_key'), 80)}
    c = d.get('counts')
    if isinstance(c, dict):
        out['counts'] = {k: _n(c.get(k)) or 0 for k in ('inserted', 'updated', 'kept')}
    return out


def register(app, ns):
    from flask import jsonify, request

    def N(name):
        return ns[name]

    def guard(f):
        return N('token_required')(N('roles_required')('admin')(f))

    def out(resp):
        return N('_v2_ns')(resp)

    def err(msg, code=400, **extra):
        body = {'error': msg}
        body.update(extra)
        return out((jsonify(body), code))

    def status_of(resp):
        return resp[1] if isinstance(resp, tuple) and len(resp) > 1 else getattr(resp, 'status_code', 200)

    def json_of(resp):
        try:
            return (resp[0] if isinstance(resp, tuple) else resp).get_json(silent=True)
        except Exception:                                  # noqa: BLE001
            return None

    def missing(resp):
        """٤٠٤ عام (الجسر ناقص) لا ٤٠٤ بنص عربي من المنصة."""
        if status_of(resp) != 404:
            return False
        e = (json_of(resp) or {}).get('error') if isinstance(json_of(resp), dict) else ''
        return (e or '').strip().lower() in _GENERIC_404

    def miss():
        return err(MISSING_AR, 404, bridge_missing=True)

    def bad(resp):
        """رد غير ناجح ⇒ رد الداشبورد (٤٠١/٤٠٣ من المنصة ⇒ ٥٠٢، والنص العربي يعدّي)."""
        if missing(resp):
            return miss()
        return out(N('_v2_mask_auth')(resp))

    def clean_body(body):
        """(الجسم المبعوت للمنصة | None، رد الخطأ). التحقق قبل أي نداء."""
        track = _s(body.get('track'), 60)
        if not _TRACK_RE.match(track):
            return None, err(BAD_TRACK_AR)
        ref = _s(body.get('ref_id'), 80)
        if not _REF_RE.match(ref):
            return None, err(BAD_REF_AR)
        law = _s(body.get('law'), 200)
        if law and not _LAW_RE.match(law):
            return None, err(BAD_LAW_AR)
        payload = {'track': track, 'ref_id': ref, 'as_proposed': body.get('as_proposed') is True}
        if law:
            payload['law'] = law
        return payload, None

    @app.route('/api/v2/ask/library', methods=['GET'], endpoint='v2_asklib_scan')
    @guard
    def v2_asklib_scan():
        closed = N('_v2_closed')()
        if closed:
            return closed
        resp = N('_platform_proxy')('GET', '/api/bridge/ask/library-scan', params={'limit': SCAN_LIMIT}, timeout=30)
        if not N('_resp_ok')(resp):
            return bad(resp)
        scan = view_scan(json_of(resp))
        if scan is None:
            return err('تعذّر قراءة رد المنصة', 502)
        # ملخص القاعدة اختياري: لو غاب أو اتعطّل الشاشة تكتبه «غير متاح بعد» وتكمل بالقائمة.
        sresp = N('_platform_proxy')('GET', '/api/bridge/ask/corpus/stats')
        scan['stats'] = view_stats(json_of(sresp)) if N('_resp_ok')(sresp) else None
        return out(jsonify(scan))

    @app.route('/api/v2/ask/library/preview', methods=['POST'], endpoint='v2_asklib_preview')
    @guard
    def v2_asklib_preview():
        closed = N('_v2_closed')()
        if closed:
            return closed
        payload, bad_resp = clean_body(N('_v2_body')())
        if bad_resp:
            return bad_resp
        payload['apply'] = False
        resp = N('_platform_proxy')('POST', '/api/bridge/ask/ingest-library', json_body=payload, timeout=25)
        if not N('_resp_ok')(resp):
            return bad(resp)
        v = view_ingest(json_of(resp))
        if v is None:
            return err('تعذّر قراءة رد المنصة', 502)
        return out(jsonify(v))

    @app.route('/api/v2/ask/library/ingest', methods=['POST'], endpoint='v2_asklib_ingest')
    @guard
    def v2_asklib_ingest():
        closed = N('_v2_closed')()
        if closed:
            return closed
        body = N('_v2_body')()
        conf = N('_v2_confirmed')(body)
        if conf:
            return conf
        payload, bad_resp = clean_body(body)
        if bad_resp:
            return bad_resp
        # معاينة قبل الكتابة: مفيش مواد ⇒ مفيش إدخال ولا تدقيق كاذب.
        pre = N('_platform_proxy')('POST', '/api/bridge/ask/ingest-library', json_body=dict(payload, apply=False), timeout=25)
        if not N('_resp_ok')(pre):
            return bad(pre)
        pv = view_ingest(json_of(pre))
        if pv is None:
            return err('تعذّر قراءة رد المنصة', 502)
        if not pv['articles']:
            return err('لا توجد مواد للإدخال في هذا المستند', 400)
        payload['apply'] = True
        resp = N('_v2_write')('POST', '/api/bridge/ask/ingest-library', payload, 'ask.ingest_library', payload['ref_id'],
                              {'track': payload['track'], 'as_proposed': payload['as_proposed']})
        if not N('_resp_ok')(resp):
            return bad(resp)
        v = view_ingest(json_of(resp))
        if v is None:
            return err('تعذّر قراءة رد المنصة', 502)
        if not v['applied']:
            return err('لم يُدخل شيء، أعد المحاولة', 502)
        return out(jsonify(v))
