# -*- coding: utf-8 -*-
"""«أدخل قوانين المكتبة» في الداشبورد (المحتوى ‹ أدخل قوانين المكتبة): مستندات مكتبة المنصة ⇒ تقسيمها مواد في قاعدة نصوص «اسأل».

    GET  /api/v2/ask/library                 ⇒ /api/bridge/ask/library-scan + /api/bridge/ask/corpus/stats   (قراءة: قائمة المستندات + ملخص القاعدة)
    POST /api/v2/ask/library/preview         ⇒ POST /api/bridge/ask/ingest-library {apply:false}              (جرّب التقسيم: لا كتابة ولا تدقيق)
    POST /api/v2/ask/library/ingest          ⇒ POST /api/bridge/ask/ingest-library {apply:true}               (أدخل المواد: تأكيد + `_v2_write` + تدقيق ask.ingest_library)
    GET  /api/v2/ask/library/cleanup         ⇒ /api/bridge/ask/library-cleanup                                (تنظيف المكتبة: النسخ المكررة + شبه الفاضية + المحذوفات)
    POST /api/v2/ask/library/delete          ⇒ POST /api/bridge/ask/library-delete                            (حذف يترجّع: تأكيد + `_v2_write` + تدقيق ask.library_delete)
    POST /api/v2/ask/library/restore         ⇒ POST /api/bridge/ask/library-restore                           (رجّع مستند: تأكيد + `_v2_write` + تدقيق ask.library_restore)

قواعد الملف (نفس `v2_tools_routes.py`):
  * أدمن بس · المفتاح `DASH_V2_ENABLED` مقفول ⇒ ٤٠٤ بلا أي نداء للمنصة · `no-store`.
  * الكتابة تطلب `confirmed: true` بالظبط قبل أي نداء، و`by` من التوكن وحده (`_v2_write`)، وتدقيق عند النجاح بس.
  * الجسم المبعوت للمنصة من قايمة بيضا، والردود مفلترة بقايمة بيضا.
  * الجسر لسه ما وصلش المنصة (٤٠٤ عام) ⇒ ٤٠٤ و`bridge_missing:true` والشاشة تكتب «الميزة لسه ما وصلتش المنصة». ٤٠٤ بنص عربي من المنصة (مستند مش موجود) بيعدّي كما هو.
  * ⛔ نداء واحد بلا إعادة محاولة. رد ضايع على الكتابة ⇒ ٥٠٢ و`no_reply:true` (من `_v2_write`).
  * ⛔ صفر ذكاء: التقسيم بالقواعد عند المنصة.
  * ⛔ التنظيف حذف يترجّع بس (المنصة بتعلّم المستند، ما بتمسحوش)، وشروطه عند المنصة: المكرر لازم يطابق الباقي حرفيًا، واللي اتدخلت منه مواد ما بيتحذفش.
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
DEL_REASONS = ('duplicate', 'empty', 'manual')
SKIP_WHY = ('missing', 'has_articles', 'keep_missing', 'not_identical', 'not_empty')
DELETE_BATCH = 60          # = LIB_DELETE_BATCH عند المنصة
BAD_BATCH_AR = 'اختر من مستند واحد إلى 60 في المرة'
BAD_REASON_AR = 'سبب الحذف غير معروف'


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


def view_clean_card(c):
    if not isinstance(c, dict) or not _REF_RE.match(str(c.get('id') or '')):
        return None
    return {'id': str(c['id']), 'title': _s(c.get('title')), 'chars': _n(c.get('chars')) or 0,
            'created_at': _s(c.get('created_at'), 40), 'ingested': _n(c.get('ingested')) or 0}


def view_cleanup(d):
    """تنظيف المكتبة: {total, groups:[{keep, extras}], tiny:[…], deleted:[…], pending}. شكل غير مفهوم ⇒ None."""
    if not isinstance(d, dict) or not isinstance(d.get('groups'), list) or not isinstance(d.get('tiny'), list):
        return None
    groups = []
    for g in d['groups']:
        keep = view_clean_card(g.get('keep')) if isinstance(g, dict) else None
        extras = [v for v in (view_clean_card(x) for x in (g.get('extras') if isinstance(g, dict) and isinstance(g.get('extras'), list) else [])) if v]
        if keep and extras:
            groups.append({'keep': keep, 'extras': extras})
    tiny = []
    for t in d['tiny']:
        card = view_clean_card(t)
        if card:
            card['head'] = _s(t.get('head'), 200)
            tiny.append(card)
    deleted = []
    for x in d.get('deleted') if isinstance(d.get('deleted'), list) else []:
        if isinstance(x, dict) and _REF_RE.match(str(x.get('id') or '')):
            deleted.append({'id': str(x['id']), 'title': _s(x.get('title')), 'deleted_at': _s(x.get('deleted_at'), 40),
                            'reason': x.get('reason') if x.get('reason') in DEL_REASONS else ''})
    return {'total': _n(d.get('total')) or 0, 'groups': groups, 'tiny': tiny, 'deleted': deleted,
            'pending': _n(d.get('pending')) or 0, 'tiny_chars': _n(d.get('tiny_chars')) or 500}


def _id_list(v):
    return [str(x) for x in (v if isinstance(v, list) else []) if isinstance(x, str) and _REF_RE.match(x)][:DELETE_BATCH]


def _skips(v):
    return [{'id': str(x['id']), 'why': x['why']} for x in (v if isinstance(v, list) else [])
            if isinstance(x, dict) and isinstance(x.get('id'), str) and _REF_RE.match(x['id']) and x.get('why') in SKIP_WHY][:DELETE_BATCH]


def view_deleted(d):
    if not isinstance(d, dict) or not isinstance(d.get('deleted'), list):
        return None
    return {'deleted': _id_list(d['deleted']), 'skipped': _skips(d.get('skipped'))}


def view_restored(d):
    if not isinstance(d, dict) or not isinstance(d.get('restored'), list):
        return None
    return {'restored': _id_list(d['restored']), 'skipped': _skips(d.get('skipped'))}


# ── «القوانين الناقصة»: القايمة الأساسية لكل بلد + نص قانون يتحط في مكانه ──
COUNTRY_IDS = ('egypt', 'qatar', 'saudi')
LAW_KINDS = ('law', 'regulation', 'decision')
LAW_TEXT_MAX = 3000000
BAD_COUNTRY_AR = 'اختر البلد'
BAD_KIND_AR = 'اختر نوع النص'
BAD_TITLE_AR = 'اكتب اسم القانون'
BAD_URL_AR = 'حط رابط المصدر الرسمي للنص'
BAD_TEXT_AR = 'الصق نص القانون كامل'
_URL_RE = re.compile(r'^https?://[^\s/<>"]+\.[^\s<>"]+$')


def view_coverage(d):
    """{countries:[{id,label,official,laws:[{key,title,articles}],missing,base_laws,base_articles}], later:[…]}."""
    if not isinstance(d, dict) or not isinstance(d.get('countries'), list):
        return None
    out = []
    for c in d['countries']:
        if not isinstance(c, dict) or c.get('id') not in COUNTRY_IDS or not isinstance(c.get('laws'), list):
            continue
        laws = [{'key': _s(l.get('key'), 30), 'title': _s(l.get('title')), 'articles': _n(l.get('articles')) or 0}
                for l in c['laws'] if isinstance(l, dict) and _s(l.get('key'), 30)]
        out.append({'id': c['id'], 'label': _s(c.get('label'), 40), 'official': _s(c.get('official'), 120),
                    'laws': laws, 'missing': sum(1 for l in laws if not l['articles']),
                    'base_laws': _n(c.get('base_laws')) or 0, 'base_articles': _n(c.get('base_articles')) or 0})
    later = [_s(x, 40) for x in d.get('later') if isinstance(x, str)] if isinstance(d.get('later'), list) else []
    return {'countries': out, 'later': later}


def view_law_text(d):
    if not isinstance(d, dict) or _n(d.get('articles')) is None:
        return None

    def rows(v):
        return [{'article_no': _s(x.get('article_no'), 30), 'text': _s(x.get('text'), 200)}
                for x in (v if isinstance(v, list) else []) if isinstance(x, dict)]
    out = {'law_key': _s(d.get('law_key'), 40), 'articles': _n(d.get('articles')) or 0,
           'existing': _n(d.get('existing')) or 0, 'applied': d.get('applied') is True,
           'duplicates': [_s(x, 30) for x in (d.get('duplicates') if isinstance(d.get('duplicates'), list) else [])][:40],
           'preview': rows(d.get('preview')), 'last': rows(d.get('last'))}
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

    # ------------------------------------------------------------ تنظيف المكتبة (حذف يترجّع)

    def clean_ids(raw):
        """قايمة معرّفات صالحة من ١ إلى ٦٠ بلا تكرار، وإلا None."""
        if not isinstance(raw, list) or not 1 <= len(raw) <= DELETE_BATCH:
            return None
        ids = []
        for x in raw:
            if not isinstance(x, str) or not _REF_RE.match(x) or x in ids:
                return None
            ids.append(x)
        return ids

    def clean_law_text(body):
        country = body.get('country')
        if country not in COUNTRY_IDS:
            return None, err(BAD_COUNTRY_AR)
        kind = body.get('kind')
        if kind not in LAW_KINDS:
            return None, err(BAD_KIND_AR)
        law = _s(body.get('law'), 200)
        if not law or not _LAW_RE.match(law) or len(law) < 3:
            return None, err(BAD_LAW_AR)
        title = _s(body.get('title'), 300)
        if len(title) < 4:
            return None, err(BAD_TITLE_AR)
        url = body.get('source_url')
        url = url.strip() if isinstance(url, str) else ''
        if not _URL_RE.match(url) or len(url) > 600:
            return None, err(BAD_URL_AR)
        text = body.get('text')
        if not isinstance(text, str) or not 50 <= len(text.strip()) <= LAW_TEXT_MAX:
            return None, err(BAD_TEXT_AR)
        return {'country': country, 'kind': kind, 'law': law, 'title': title, 'source_url': url,
                'text': text.strip()}, None

    @app.route('/api/v2/ask/library/coverage', methods=['GET'], endpoint='v2_asklib_coverage')
    @guard
    def v2_asklib_coverage():
        closed = N('_v2_closed')()
        if closed:
            return closed
        resp = N('_platform_proxy')('GET', '/api/bridge/ask/coverage', timeout=30)
        if not N('_resp_ok')(resp):
            return bad(resp)
        v = view_coverage(json_of(resp))
        if v is None:
            return err('تعذّر قراءة رد المنصة', 502)
        return out(jsonify(v))

    @app.route('/api/v2/ask/library/law-text/preview', methods=['POST'], endpoint='v2_asklib_lawtext_preview')
    @guard
    def v2_asklib_lawtext_preview():
        closed = N('_v2_closed')()
        if closed:
            return closed
        payload, bad_resp = clean_law_text(N('_v2_body')())
        if bad_resp:
            return bad_resp
        payload.update(apply=False, by=N('_actor_email')())
        resp = N('_platform_proxy')('POST', '/api/bridge/ask/law-text', json_body=payload, timeout=30)
        if not N('_resp_ok')(resp):
            return bad(resp)
        v = view_law_text(json_of(resp))
        if v is None:
            return err('تعذّر قراءة رد المنصة', 502)
        return out(jsonify(v))

    @app.route('/api/v2/ask/library/law-text', methods=['POST'], endpoint='v2_asklib_lawtext')
    @guard
    def v2_asklib_lawtext():
        closed = N('_v2_closed')()
        if closed:
            return closed
        body = N('_v2_body')()
        conf = N('_v2_confirmed')(body)
        if conf:
            return conf
        payload, bad_resp = clean_law_text(body)
        if bad_resp:
            return bad_resp
        payload['apply'] = True
        resp = N('_v2_write')('POST', '/api/bridge/ask/law-text', payload, 'ask.law_text',
                              '%s:%s' % (payload['country'], payload['law']),
                              {'country': payload['country'], 'law': payload['law'], 'kind': payload['kind'],
                               'title': payload['title'], 'source_url': payload['source_url'],
                               'chars': len(payload['text'])})
        if not N('_resp_ok')(resp):
            return bad(resp)
        v = view_law_text(json_of(resp))
        if v is None:
            return err('تعذّر قراءة رد المنصة', 502)
        return out(jsonify(v))

    @app.route('/api/v2/ask/library/cleanup', methods=['GET'], endpoint='v2_asklib_cleanup')
    @guard
    def v2_asklib_cleanup():
        closed = N('_v2_closed')()
        if closed:
            return closed
        resp = N('_platform_proxy')('GET', '/api/bridge/ask/library-cleanup', timeout=30)
        if not N('_resp_ok')(resp):
            return bad(resp)
        v = view_cleanup(json_of(resp))
        if v is None:
            return err('تعذّر قراءة رد المنصة', 502)
        return out(jsonify(v))

    @app.route('/api/v2/ask/library/delete', methods=['POST'], endpoint='v2_asklib_delete')
    @guard
    def v2_asklib_delete():
        closed = N('_v2_closed')()
        if closed:
            return closed
        body = N('_v2_body')()
        conf = N('_v2_confirmed')(body)
        if conf:
            return conf
        reason = body.get('reason')
        if reason not in DEL_REASONS:
            return err(BAD_REASON_AR)
        raw = body.get('items')
        if not isinstance(raw, list) or not 1 <= len(raw) <= DELETE_BATCH:
            return err(BAD_BATCH_AR)
        items, seen = [], set()
        for it in raw:
            rid = it.get('id') if isinstance(it, dict) else None
            dup = (it.get('dup_of') or '') if isinstance(it, dict) else ''
            if not isinstance(rid, str) or not _REF_RE.match(rid) or rid in seen or not isinstance(dup, str):
                return err(BAD_REF_AR)
            if reason == 'duplicate':
                if not _REF_RE.match(dup) or dup == rid:        # المكرر لازم له أصل تاني باقي
                    return err(BAD_REF_AR)
                items.append({'id': rid, 'dup_of': dup})
            else:
                items.append({'id': rid})
            seen.add(rid)
        resp = N('_v2_write')('POST', '/api/bridge/ask/library-delete', {'items': items, 'reason': reason},
                              'ask.library_delete', items[0]['id'] if len(items) == 1 else 'n=%d' % len(items),
                              {'reason': reason, 'ids': [i['id'] for i in items]})
        if not N('_resp_ok')(resp):
            return bad(resp)
        v = view_deleted(json_of(resp))
        if v is None:
            return err('تعذّر قراءة رد المنصة', 502)
        return out(jsonify(v))

    @app.route('/api/v2/ask/library/restore', methods=['POST'], endpoint='v2_asklib_restore')
    @guard
    def v2_asklib_restore():
        closed = N('_v2_closed')()
        if closed:
            return closed
        body = N('_v2_body')()
        conf = N('_v2_confirmed')(body)
        if conf:
            return conf
        ids = clean_ids(body.get('ids'))
        if ids is None:
            return err(BAD_REF_AR)
        resp = N('_v2_write')('POST', '/api/bridge/ask/library-restore', {'ids': ids},
                              'ask.library_restore', ids[0] if len(ids) == 1 else 'n=%d' % len(ids), {'ids': ids})
        if not N('_resp_ok')(resp):
            return bad(resp)
        v = view_restored(json_of(resp))
        if v is None:
            return err('تعذّر قراءة رد المنصة', 502)
        return out(jsonify(v))
