# -*- coding: utf-8 -*-
"""محرّر الدورات من الداشبورد — مسارات `/api/v2/courses2/*` (SPEC-C-courses §C1).

بروكسيات رفيعة فوق جسر المنصة `/api/bridge/courses2/*` (`routes/courses_bridge.py`). نفس قواعد باقي أقسام اللوحة الجديدة:
  * أدمن بس + المفتاح (`DASH_V2_ENABLED`) مفتوح، وإلا ٤٠٤ قبل أي رحلة للمنصة. `Cache-Control: no-store` على كل رد.
  * كل كتابة (إلا المعاينة ومسودة المخ) تطلب `confirmed: true` بالظبط من المتصفح، وإلا ٤٠٠ قبل أي نداء. الجسم المبعوت للمنصة من قايمة
    بيضا بالحقول لكل مسار، و`by` من التوكن وحده (اللي في جسم المتصفح بيتجاهل)، و`confirmed:true` بيتحط هنا للجسر.
  * ⛔ ولا سعر ولا نسبة من هنا أبدًا: أي حقل `price*` أو `pricing` أو `is_free` أو نسبة مدرّب بيتشال من الجسم قبل أي حاجة.
  * ⛔ نداء واحد ولا إعادة محاولة. رد ضاع (٥٠٠/٥٠٢/٥٠٣/٥٠٤) على كتابة أو معاينة أو مسودة ⇒ ٥٠٢ و`no_reply:true` بنص «لم يصل رد…»،
    مش «اترفض». نص `detail` العربي من المنصة بيوصل كما هو في `error` بنفس الكود (٤٠٠ · ٤٠٤ · ٤٠٩ · ٤٢٢).
  * تدقيق عند النجاح بس باسم `course2.<إجراء>` وبما **حدث** (مفاتيح الحقول لا محتواها).

`register(app, g)` بتتنادى من app.py بسطر واحد، و`g` = globals() بتاعته (الديكوريترز والمساعدات والموديلات).
"""
import re
from urllib.parse import quote

NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
BAD_ID_AR = 'معرّف غير صالح'
TITLE_MAX = 160
IDEM_RE = re.compile(r'^[A-Za-z0-9_.:-]{8,80}$')
CASE_RE = re.compile(r'^[A-Za-z0-9_-]{1,40}$')

# ⛔ مفاتيح السعر والنسبة: تُشال من أول مستوى في أي جسم (الجسر يتجاهلها أصلًا، وإحنا ما نبعتهاش).
_MONEY_EXACT = {'pricing', 'is_free', 'trainer_share_pct', 'share_pct', 'trainer_share', 'commission', 'max_seats', 'quorum'}

DATA_KEYS = ('title', 'subtitle', 'description', 'cover', 'level', 'outcomes')
LESSON_KEYS = ('title', 'blocks', 'time', 'for', 'hero', 'motion',                                           # تفاعلي
               'video', 'duration_seconds', 'is_preview', 'chapters', 'checkpoints', 'summary', 'transcript',  # مسجّل
               'starts_at', 'duration_min', 'zoom_link', 'recording_url', 'status', 'quiz')                  # مباشر
BRAIN_KEYS = ('instruction', 'kind', 'lesson_id', 'material')


def strip_money(body):
    """نسخة من الجسم بلا أي مفتاح سعر/نسبة في المستوى الأول (حساس لحالة الحروف)."""
    out = {}
    for k, v in (body or {}).items():
        lk = str(k).lower()
        if lk.startswith('price') or lk in _MONEY_EXACT:
            continue
        out[k] = v
    return out


def pick(body, keys):
    clean = strip_money(body)
    return {k: clean[k] for k in keys if k in clean}


def register(app, g):
    token_required = g['token_required']
    roles_required = g['roles_required']
    jsonify = g['jsonify']
    request = g['request']
    ID_RE = g['V2_ID_RE']
    BASE = '/api/bridge/courses2'

    def ns(resp):
        return g['_v2_ns'](resp)

    def err(msg, code=400):
        return ns((jsonify({'error': msg}), code))

    def guard(ids=(), write=True):
        """(رد جاهز أو None، الجسم). المفتاح ⇒ المعرّفات ⇒ التأكيد (بالترتيب ده)."""
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

    def no_reply(action, target):
        g['_audit']('course2.no_reply', target=target, meta={'attempt': action})
        return ns((jsonify({'error': NO_REPLY_AR, 'no_reply': True}), 502))

    def send(method, path, platform_body, action, target, meta, audit=True, params=None):
        """نداء واحد للجسر. `audit=False` للمعاينة ومسودة المخ (لا كتابة)، لكن ضياع الرد يبقى «لم يصل رد»."""
        resp = g['_platform_proxy'](method, path, params=params, json_body=platform_body, timeout=40)
        if g['_resp_ok'](resp):
            if audit:
                g['_audit']('course2.' + action, target=target, meta=meta)
            return ns(resp)
        if g['_ef_no_reply'](resp):
            return no_reply(action, target)
        return ns(g['_v2_mask_auth'](resp))

    def write(method, path, fields, action, target, meta):
        body = dict(fields)
        body['confirmed'] = True
        body['by'] = g['_actor_email']()
        return send(method, path, body, action, target, meta)

    def read(path, params=None):
        return ns(g['_v2_mask_auth'](g['_platform_proxy']('GET', path, params=params, timeout=15)))

    def q(x):
        return quote(x, safe='')

    # ------------------------------------------------------------------ ١ · قائمة الدورات
    @app.route('/api/v2/courses2', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2c2_list():
        bad, _ = guard(write=False)
        return bad or read(BASE)

    # ------------------------------------------------------------------ ٢ · إنشاء بمفتاح منع تكرار
    @app.route('/api/v2/courses2', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2c2_create():
        bad, b = guard()
        if bad:
            return bad
        b = strip_money(b)
        title = b.get('title')
        title = title.strip() if isinstance(title, str) else ''
        if not title or len(title) > TITLE_MAX:
            return err('اكتب عنوان الدورة (حتى ١٦٠ حرفًا)')
        idem = b.get('idem_key')
        if not isinstance(idem, str) or not IDEM_RE.match(idem):
            return err('مفتاح منع التكرار غير صالح')
        out = {'title': title, 'idem_key': idem}
        if b.get('platform_owned') is True:
            out['platform_owned'] = True
        else:
            email = b.get('owner_email')
            email = email.strip().lower() if isinstance(email, str) else ''
            if email:
                out['owner_email'] = email[:200]
        return write('POST', BASE, out, 'create', idem, {'title': title[:80], 'platform_owned': bool(out.get('platform_owned')), 'owner': out.get('owner_email', '')})

    # ------------------------------------------------------------------ ٣ · الدورة كاملة
    @app.route('/api/v2/courses2/<cid>', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2c2_get(cid):
        bad, _ = guard([cid], write=False)
        return bad or read('%s/%s' % (BASE, q(cid)))

    # ------------------------------------------------------------------ ٤ · البيانات
    @app.route('/api/v2/courses2/<cid>/data', methods=['PUT'])
    @token_required
    @roles_required('admin')
    def v2c2_data(cid):
        bad, b = guard([cid])
        if bad:
            return bad
        out = pick(b, DATA_KEYS)
        if not out:
            return err('لا يوجد تغيير')
        return write('PUT', '%s/%s/data' % (BASE, q(cid)), out, 'data', cid, {'keys': sorted(out.keys())})

    # ------------------------------------------------------------------ ٥ · الهيكل
    @app.route('/api/v2/courses2/<cid>/structure', methods=['PUT'])
    @token_required
    @roles_required('admin')
    def v2c2_structure(cid):
        bad, b = guard([cid])
        if bad:
            return bad
        if not isinstance(b.get('units'), list):
            return err('الهيكل ناقص: لا وحدات')
        out = pick(b, ('cases', 'units'))
        n = sum(len(u.get('lessons') or []) for u in out['units'] if isinstance(u, dict) and isinstance(u.get('lessons'), list))
        return write('PUT', '%s/%s/structure' % (BASE, q(cid)), out, 'structure', cid, {'units': len(out['units']), 'lessons': n})

    # ------------------------------------------------------------------ ٦ · محتوى درس
    @app.route('/api/v2/courses2/<cid>/lessons/<lid>', methods=['PUT'])
    @token_required
    @roles_required('admin')
    def v2c2_lesson(cid, lid):
        bad, b = guard([cid, lid])
        if bad:
            return bad
        out = pick(b, LESSON_KEYS)
        if not out:
            return err('لا يوجد تغيير')
        return write('PUT', '%s/%s/lessons/%s' % (BASE, q(cid), q(lid)), out, 'lesson', cid, {'lesson': lid, 'keys': sorted(out.keys())})

    # ------------------------------------------------------------------ ٧ · معاينة (GET من المحفوظ · POST لما لم يُحفظ — بلا تأكيد ولا كتابة)
    @app.route('/api/v2/courses2/<cid>/lessons/<lid>/preview', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2c2_preview_get(cid, lid):
        bad, _ = guard([cid, lid], write=False)
        if bad:
            return bad
        case = request.args.get('case', '')
        params = {'case': case} if CASE_RE.match(case or '') else None
        return read('%s/%s/lessons/%s/preview' % (BASE, q(cid), q(lid)), params)

    @app.route('/api/v2/courses2/<cid>/lessons/<lid>/preview', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2c2_preview_post(cid, lid):
        bad, b = guard([cid, lid], write=False)
        if bad:
            return bad
        b = g['_v2_body']()
        case = request.args.get('case', '')
        params = {'case': case} if CASE_RE.match(case or '') else None
        return send('POST', '%s/%s/lessons/%s/preview' % (BASE, q(cid), q(lid)), pick(b, LESSON_KEYS), 'preview', cid, None, audit=False, params=params)

    # ------------------------------------------------------------------ ٨ · نشر · ٩ · إيقاف · ١٠ · إرجاع بملاحظات
    @app.route('/api/v2/courses2/<cid>/publish', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2c2_publish(cid):
        bad, _ = guard([cid])
        return bad or write('POST', '%s/%s/publish' % (BASE, q(cid)), {}, 'publish', cid, None)

    @app.route('/api/v2/courses2/<cid>/pause', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2c2_pause(cid):
        bad, _ = guard([cid])
        return bad or write('POST', '%s/%s/pause' % (BASE, q(cid)), {}, 'pause', cid, None)

    @app.route('/api/v2/courses2/<cid>/return', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2c2_return(cid):
        bad, b = guard([cid])
        if bad:
            return bad
        notes = b.get('notes')
        if not isinstance(notes, list) or not 1 <= len(notes) <= 40:
            return err('اكتب ملاحظة واحدة على الأقل (حتى ٤٠)')
        out = []
        for n in notes:
            if not isinstance(n, dict):
                return err('ملاحظة غير صالحة')
            kind = n.get('target_kind')
            text = n.get('text')
            text = text.strip() if isinstance(text, str) else ''
            tid = n.get('target_id')
            tid = tid.strip() if isinstance(tid, str) else ''
            if kind not in ('lesson', 'unit', 'course') or not text or len(text) > 600:
                return err('كل ملاحظة تحتاج هدفًا ونصًا حتى ٦٠٠ حرف')
            out.append({'target_kind': kind, 'target_id': '' if kind == 'course' else tid, 'text': text})
        return write('POST', '%s/%s/return' % (BASE, q(cid)), {'notes': out}, 'return', cid, {'notes': len(out)})

    # ------------------------------------------------------------------ ١١ · أداة المخ — مسودة فقط (بلا تأكيد ولا كتابة)
    @app.route('/api/v2/courses2/<cid>/brain/draft', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2c2_brain(cid):
        bad, _ = guard([cid], write=False)
        if bad:
            return bad
        b = pick(g['_v2_body'](), BRAIN_KEYS)
        ins = b.get('instruction')
        if not isinstance(ins, str) or not ins.strip():
            return err('اكتب ما تريده من المساعد')
        if b.get('lesson_id') is not None and not (isinstance(b['lesson_id'], str) and ID_RE.match(b['lesson_id'])):
            return err(BAD_ID_AR)
        b['by'] = g['_actor_email']()
        return send('POST', '%s/%s/brain/draft' % (BASE, q(cid)), b, 'brain_draft', cid, None, audit=False)

    # ------------------------------------------------------------------ ١٢ · رفع الفيديو (يرجّع ترويسات TUS للمتصفح)
    @app.route('/api/v2/courses2/<cid>/upload', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2c2_upload(cid):
        bad, b = guard([cid])
        if bad:
            return bad
        title = b.get('title')
        title = title.strip()[:200] if isinstance(title, str) else ''
        return write('POST', '%s/%s/upload' % (BASE, q(cid)), {'title': title}, 'upload', cid, {'title': title[:80]})

    return app
