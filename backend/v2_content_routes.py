# -*- coding: utf-8 -*-
"""مسارات قسم «المحتوى» (الجولة الأخيرة) — ثلاثة مسارات فقط، وملف مستقل كي لا يلمس غيره.

    import v2_content_routes as _v2s_content; _v2s_content.register(app, globals())

`ns` = `globals()` الخاصة بـ app.py: كل اسم يُبحث عنه وقت الطلب (`ns['Article']`…) فلا يستورد هذا الملف `app` أبدًا ويعمل تحت أي اسم وحدة.

  1. GET  /api/v2/content/overview          حالة مقالات الموقع من SQLite الداشبورد نفسها (كلمات · صورة · وصف · مراجع) + حالة صفحات محركات البحث.
                                            ⛔ قراءة فقط: لا نداء للمنصة ولا تشغيل لتوليد الصفحات، ولا نص مقال ولا وصف ولا كلمات مفتاحية في الرد.
  2. GET  /api/v2/testimonials?status=      آراء متعلّمي الدورات من جسر المنصة (`/api/bridge/testimonials`).
  3. POST /api/v2/testimonials/<id>/<action> approve|reject — الاعتماد يطلب `confirmed: true` بالضبط، والتدقيق عند النجاح فقط.
⛔ لا يعدّل `prerender.py` ولا أي مسار من `/api/content/*`.
"""
import re

_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
_STATUSES = ('pending', 'approved', 'rejected')
_ACTIONS = ('approve', 'reject')
_PLATFORM_DOWN = 'تعذّر الوصول إلى المنصة'


def _iso_z(value):
    """ISO بتوقيت UTC صريح: الخادم يخزّن التواريخ naive، والمتصفح يقرأ الـnaive كتوقيت جهازه فيغلط في العمر."""
    if value is None or value == '':
        return None
    try:
        s = value.isoformat() if hasattr(value, 'isoformat') else str(value)
    except Exception:
        return None
    if not s:
        return None
    if s.endswith('Z') or re.search(r'[+-]\d\d:\d\d$', s):
        return s
    return s + 'Z'


def _words(paragraphs):
    n = 0
    for p in paragraphs or []:
        t = str(p).strip()
        if t.startswith('## '):
            t = t[3:]
        n += len(t.split())
    return n


def register(app, ns):
    from flask import jsonify, request

    def N(name):
        return ns[name]

    def guard(f):
        return N('token_required')(N('roles_required')('admin')(f))

    def nostore(resp):
        return N('_no_store')(resp)

    def closed():
        """المفتاح مقفول ⇒ ٤٠٤ (كأن المسار غير موجود) — نفس قاعدة بروكسيات D3."""
        if not N('_v2_enabled')():
            return nostore(jsonify({'error': 'غير متاح'})), 404
        return None

    def mask(resp):
        """رفض المنصة للمفتاح المشترك (٤٠١/٤٠٣) عطلٌ في الربط لا انتهاء جلسة الأدمن: يصير ٥٠٢ فلا يُخرج الشاشة إلى تسجيل الدخول."""
        try:
            if isinstance(resp, tuple) and int(resp[1]) in (401, 403):
                return nostore(jsonify({'error': _PLATFORM_DOWN})), 502
        except Exception:
            pass
        return resp

    @app.route('/api/v2/content/overview', methods=['GET'], endpoint='v2s_content_overview')
    @guard
    def v2s_content_overview():
        c = closed()
        if c:
            return c
        Article = N('Article')
        rows = Article.query.order_by(Article.created_at.desc(), Article.id.desc()).all()
        body_list = N('_article_body_list')
        out = []
        for a in rows:
            out.append({
                'id': a.id, 'title': a.title or '', 'status': a.status or 'draft', 'by': a.by or '', 'cat': a.cat or '',
                'date': a.date or '', 'slug': a.slug or '',
                'created_at': _iso_z(a.created_at), 'published_at': _iso_z(a.published_at), 'updated_at': _iso_z(a.updated_at),
                'words': _words(body_list(a)),
                'has_image': bool((a.image_url or '').strip()),
                'has_meta': bool((a.meta_description or '').strip()),     # الوصف الخام فقط: بديل المقتطف في serialize_article لا يُحسب
                'reviewed_by': (a.reviewed_by or '').strip() or None,
            })
        last = ns.get('_prerender_last') or {}
        state = 'running' if ns.get('_prerender_running') else (last.get('state') or 'never-run')
        if state not in ('ok', 'error', 'skipped', 'never-run', 'running'):
            state = 'never-run'                                           # حالات داخلية (queued…) لا تُعرض كما هي
        pre = {'state': state, 'at': _iso_z(last.get('at')), 'uploaded': last.get('uploaded') if state == 'ok' else None}
        import datetime
        return nostore(jsonify({'articles': out, 'prerender': pre, 'now': _iso_z(datetime.datetime.utcnow())}))

    @app.route('/api/v2/testimonials', methods=['GET'], endpoint='v2s_testimonials_list')
    @guard
    def v2s_testimonials_list():
        c = closed()
        if c:
            return c
        status = (request.args.get('status') or 'pending').strip().lower()
        if status not in _STATUSES:
            status = 'pending'
        resp = N('_platform_proxy')('GET', '/api/bridge/testimonials', params={'status': status})
        return nostore_any(mask(resp))

    @app.route('/api/v2/testimonials/<tid>/<action>', methods=['POST'], endpoint='v2s_testimonials_decide')
    @guard
    def v2s_testimonials_decide(tid, action):
        c = closed()
        if c:
            return c
        if action not in _ACTIONS:
            return nostore(jsonify({'error': 'إجراء غير معروف'})), 400
        if not _ID_RE.match(tid or ''):
            return nostore(jsonify({'error': 'رقم الرأي غير صالح'})), 400
        body = request.get_json(silent=True)
        body = body if isinstance(body, dict) else {}
        if action == 'approve' and body.get('confirmed') is not True:
            return nostore(jsonify({'error': 'أكّد النشر أولًا'})), 400
        resp = N('_platform_proxy')('POST', '/api/bridge/testimonials/%s/%s' % (tid, action), timeout=25)
        if N('_resp_ok')(resp):
            N('_audit')('testimonial.' + action, target=tid)
        return nostore_any(mask(resp))

    def nostore_any(resp):
        try:
            r = resp[0] if isinstance(resp, tuple) else resp
            r.headers['Cache-Control'] = 'no-store'
        except Exception:
            pass
        return resp
