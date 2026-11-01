# -*- coding: utf-8 -*-
"""«ناقشها في الساحة» من محرّر المقال (docs/v2/saha-link/SPEC.md) — مساران فقط، وملف مستقل كي لا يلمس غيره.

    import v2_saha_link_routes as _v2s_saha_link; _v2s_saha_link.register(app, globals())

`ns` = `globals()` الخاصة بـ app.py: كل اسم يُبحث عنه وقت الطلب فلا يستورد هذا الملف `app` أبدًا.

  1. POST /api/v2/content/articles/<id>/saha-topic          يفتح نقاشًا للمقال المنشور على المنصة (جسر `/bridge/topics`) ويحفظ معرّفه على المقال.
  2. POST /api/v2/content/articles/<id>/saha-topic/detach   يفصل المقال عن نقاشه (يمسح المعرّف هنا فقط؛ النقاش نفسه يبقى في المنصة).

القواعد (نفس `v2_market4_routes.py`):
  * أدمن بس · المفتاح `DASH_V2_ENABLED` مقفول ⇒ ٤٠٤ بلا أي نداء · `no-store`.
  * كل كتابة تطلب `confirmed: true` بالضبط قبل أي نداء.
  * مقال منشور فقط: رابط المقال لا يتجمّد إلا عند أول نشر، والنقاش يحمل هذا الرابط.
  * نداء الكتابة اللي ضاع رده ⇒ ٥٠٢ و`no_reply`. إعادة المحاولة آمنة: قبل أي إنشاء نقرأ نقاشات المنصة ونبحث عن واحد
    `source_article_slug` بتاعه هو رابط هذا المقال، فلو كان اتعمل ورده ضاع نربطه بدل أن نكرّره. نقاش مسودة (أُنشئ ولم يُفتح) نفتحه.
  * المعرّف لا يُحفظ على المقال إلا بعد أن يصير النقاش علنيًّا (الموقع لا يرسم زرًّا لصفحة لا تُفتح).
  * الحفظ أو الفصل على مقال منشور يُطلق توليد صفحات الزواحف في الخلفية (الزرّ جزء من الصفحة المُسبقة العرض).
  * تدقيق عند النجاح بس: `article.saha_open` · `article.saha_detach` (وعند الرد الضايع `saha_link.no_reply`).
⛔ لا يعدّل `prerender.py` ولا أي مسار من `/api/content/*`؛ و`PUT /api/content/articles/<id>` لا يقبل هذا الحقل أبدًا.
"""
import re

SAHA_APP_URL = 'https://app.elprofessor.net/?page=saha&topic='
TOPIC_ID_RE = re.compile(r'^[A-Za-z0-9_-]{8,64}$')
_SLUG_BAD = re.compile(r'[\s/\\?#]')
_LIVE = ('open', 'published')            # النقاش علنيّ فعلًا
_PUBLISHABLE = ('draft', 'pending_review', 'merged')
_DEAD = ('rejected', 'archived')

CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
NOT_FOUND_AR = 'المقال غير موجود'
NOT_PUBLISHED_AR = 'انشر المقال على الموقع أولًا ثم افتح نقاشه'
HAS_TOPIC_AR = 'لهذا المقال نقاش مفتوح بالفعل'
NO_TOPIC_AR = 'لا نقاش مرتبط بهذا المقال'
BAD_SLUG_AR = 'رابط المقال غير صالح لفتح نقاش'
BAD_TITLE_AR = 'عنوان النقاش من ٣ إلى ٢٠٠ حرف'
BAD_QUESTION_AR = 'اكتب سؤال النقاش (حتى ٥٠٠٠ حرف)'
NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة ثم أعد المحاولة؛ إن كان النقاش قد فُتح فسيُربط بالمقال ولن يتكرر.'
HALF_AR = 'أُنشئ النقاش لكنه لم يُفتح للناس بعد. أعد المحاولة وسنكمل من حيث توقف.'
BAD_REPLY_AR = 'تعذّر قراءة رد المنصة'
PLATFORM_DOWN_AR = 'تعذّر الاتصال بالمنصة'


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

    def call(method, path, body=None, timeout=25):
        return N('_platform_proxy')(method, path, json_body=body, timeout=timeout)

    def fail(resp, target, attempt):
        """ردّ المنصة غير الناجح ⇒ رد الداشبورد: الضايع ⇒ no_reply، والباقي نصّ المنصة العربي كما هو."""
        if N('_ef_no_reply')(resp):
            N('_audit')('saha_link.no_reply', target=str(target), meta={'attempt': attempt})
            return err(NO_REPLY_AR, 502, no_reply=True)
        return out(N('_v2_mask_auth')(resp))

    def rows_of(resp):
        # `_proxy_json` يُسقط القوائم (يرجع {} لغير القاموس) والجسر يرد قائمة صفوف مباشرة ⇒ نقرأ الرد بأنفسنا.
        try:
            data = (resp[0] if isinstance(resp, tuple) else resp).get_json(silent=True)
        except Exception:                                  # noqa: BLE001
            return None
        if isinstance(data, dict):
            data = data.get('topics')
        return data if isinstance(data, list) else None

    def push(aid):
        try:
            N('_prerender_push_async')('article-saha:%s' % aid)
        except Exception:                                  # noqa: BLE001 — توليد الصفحات لا يُسقط الحفظ
            pass

    def head(aid):
        """المقال + الحارسان المشتركان (المفتاح، التأكيد). يرجع (رد جاهز | None، المقال، الجسم)."""
        closed = N('_v2_closed')()
        if closed:
            return closed, None, None
        body = N('_v2_body')()
        bad = N('_v2_confirmed')(body)
        if bad:
            return bad, None, None
        art = N('Article').query.get(aid)
        if not art:
            return err(NOT_FOUND_AR, 404), None, None
        return None, art, body

    @app.route('/api/v2/content/articles/<int:aid>/saha-topic', methods=['POST'], endpoint='v2_saha_link_open')
    @guard
    def v2_saha_link_open(aid):
        bad, art, body = head(aid)
        if bad:
            return bad
        if art.status != 'published':
            return err(NOT_PUBLISHED_AR, 409)
        if art.saha_topic_id:
            return err(HAS_TOPIC_AR, 409)
        slug = N('_article_slug')(art)
        if not slug or len(slug) > 200 or _SLUG_BAD.search(slug):
            return err(BAD_SLUG_AR, 409)
        title = body.get('title', None)
        title = (art.title if title is None else title)
        title = title.strip() if isinstance(title, str) else ''
        if not 3 <= len(title) <= 200:
            return err(BAD_TITLE_AR)
        question = body.get('question', None)
        if question is None:
            question = art.excerpt or art.meta_description or ''
        question = question.strip() if isinstance(question, str) else ''
        if not 1 <= len(question) <= 5000:
            return err(BAD_QUESTION_AR)
        cover = (art.image_url or '').strip()
        if not (cover.lower().startswith('https://') and len(cover) <= 2000):
            cover = ''

        # ١) هل لهذا المقال نقاش عند المنصة أصلًا؟ (رد ضايع سابق · أو فصلٌ ثم إعادة فتح) — نقرأ قبل أي إنشاء.
        resp = call('GET', '/api/bridge/topics')
        if not N('_resp_ok')(resp):
            return out(N('_v2_mask_auth')(resp))
        rows = rows_of(resp)
        if rows is None:
            return err(BAD_REPLY_AR, 502)
        found = None
        for r in rows:
            if (isinstance(r, dict) and r.get('source_article_slug') == slug and r.get('status') not in _DEAD
                    and isinstance(r.get('id'), str) and TOPIC_ID_RE.match(r['id'])):
                found = r
                break
        adopted = found is not None
        status = found.get('status') if found else None
        tid = found['id'] if found else None

        # ٢) إنشاء (إن لم يوجد)
        if not adopted:
            payload = {'title': title, 'question': question, 'source': 'human', 'source_article_slug': slug}
            if cover:
                payload['cover_url'] = cover
            resp = call('POST', '/api/bridge/topics', payload)
            if not N('_resp_ok')(resp):
                return fail(resp, aid, 'create')
            made = N('_proxy_json')(resp)
            tid = made.get('id') if isinstance(made, dict) else None
            if not (isinstance(tid, str) and TOPIC_ID_RE.match(tid)):
                return err(BAD_REPLY_AR, 502)
            status = made.get('status') or 'draft'

        # ٣) فتحه للناس (إن لم يكن علنيًّا)
        if status not in _LIVE:
            resp = call('POST', '/api/bridge/topics/%s/publish' % tid)
            if not N('_resp_ok')(resp):
                if N('_ef_no_reply')(resp):
                    N('_audit')('saha_link.no_reply', target=str(aid), meta={'attempt': 'publish', 'topic_id': tid})
                    return err(NO_REPLY_AR, 502, no_reply=True)
                return err(HALF_AR, 502, partial=True)

        # ٤) الحفظ على المقال (بعد أن صار النقاش علنيًّا فقط)
        art.saha_topic_id = tid
        N('db').session.commit()
        N('_audit')('article.saha_open', target=str(aid), meta={'topic_id': tid, 'adopted': adopted})
        push(aid)
        return out(jsonify({'ok': True, 'saha_topic_id': tid, 'url': SAHA_APP_URL + tid, 'adopted': adopted}))

    @app.route('/api/v2/content/articles/<int:aid>/saha-topic/detach', methods=['POST'], endpoint='v2_saha_link_detach')
    @guard
    def v2_saha_link_detach(aid):
        bad, art, _body = head(aid)
        if bad:
            return bad
        if not art.saha_topic_id:
            return err(NO_TOPIC_AR, 409)
        tid = art.saha_topic_id
        art.saha_topic_id = None
        N('db').session.commit()
        N('_audit')('article.saha_detach', target=str(aid), meta={'topic_id': tid})
        push(aid)
        return out(jsonify({'ok': True, 'saha_topic_id': None}))
