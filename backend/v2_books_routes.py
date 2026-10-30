# -*- coding: utf-8 -*-
"""مسارا قراءة لتبويب «الكتب والأعمال» الجديد (قسم «الكتب»).

مسارات قراءة فقط، أدمن فقط، ورا نفس مفتاح `DASH_V2_ENABLED` المقفول:
  • GET /api/v2/books/review?status=pending_review|rejected  ← /api/bridge/knowledge/review (حالة المراجعة + هل في ملف)
  • GET /api/v2/books/store                                  ← /api/bridge/books/works (كتب المتجر: صاحب العمل · المبيعات · الاتفاقية)

⛔ `register(app, g)`: `g` هو `globals()` بتاع app.py. كل اسم بيتدوّر عليه وقت الطلب لا وقت التسجيل (`_platform_proxy` معرَّفة
تحت سطر التسجيل في app.py).
⛔ ما يمرّ للمتصفح إلا قايمة حقول بيضا: نص العمل نفسه ورابط الملف ومساره والتسعير ما بيخرجوش من هنا أبدًا.
⛔ نداء واحد بلا إعادة محاولة، ولا جسم مخترع لو المنصة ما ردّتش: الحالة والخطأ كما وصلا (و٤٠١/٤٠٣ بيتحوّلوا ٥٠٢ حتى لا يخرج الأدمن من جلسته).
"""
from flask import jsonify, request

REVIEW_STATUSES = ('pending_review', 'rejected')
REVIEW_FIELDS = ('id', 'slug', 'title', 'type', 'owner_email', 'owner_name', 'rights', 'is_active', 'status', 'created_at', 'updated_at',
                 'review_note', 'total_acquired')
STORE_FIELDS = ('slug', 'title', 'source', 'type', 'owner_email', 'owner_name', 'catalog_id', 'offer_id', 'plan', 'plan_label', 'owner_pct',
                'platform_pct', 'paid_owners', 'owners_total', 'last_sold_at')
BAD_STATUS_AR = 'حالة غير معروفة'


def _pick(src, fields):
    return {k: src[k] for k in fields if k in src}


def _review_item(d):
    out = _pick(d, REVIEW_FIELDS)
    out['has_file'] = bool(str(d.get('file_url') or '').strip())
    return out


def _store_item(d):
    out = _pick(d, STORE_FIELDS)
    bv = d.get('by_version')
    if isinstance(bv, dict):
        out['by_version'] = _pick(bv, ('read', 'pdf'))
    return out


def _rebuild(resp, make):
    """ردّ المنصة الناجح ⇒ {"items": [...], "count": n} من القايمة البيضا، أو None لو الشكل غير مفهوم."""
    data = resp.get_json(silent=True)
    rows = data.get('items') if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return None
    items = [make(r) for r in rows if isinstance(r, dict)]
    return {'items': items, 'count': len(items)}


def register(app, g):
    def closed():
        return g['_v2_closed']()

    def ns(resp):
        return g['_v2_ns'](resp)

    def get(path, params=None):
        return ns(g['_v2_mask_auth'](g['_platform_proxy']('GET', path, params=params)))

    @app.route('/api/v2/books/review', methods=['GET'])
    @g['token_required']
    @g['roles_required']('admin')
    def v2_books_review():
        c = closed()
        if c:
            return c
        status = (request.args.get('status') or '').strip()
        if status not in REVIEW_STATUSES:
            return ns((jsonify({'error': BAD_STATUS_AR}), 400))
        resp = get('/api/bridge/knowledge/review', {'status': status})
        if isinstance(resp, tuple):
            return resp
        body = _rebuild(resp, _review_item)
        if body is None:
            return ns((jsonify({'error': 'تعذر قراءة رد المنصة'}), 502))
        return ns(jsonify(body))

    @app.route('/api/v2/books/store', methods=['GET'])
    @g['token_required']
    @g['roles_required']('admin')
    def v2_books_store():
        c = closed()
        if c:
            return c
        resp = get('/api/bridge/books/works')
        if isinstance(resp, tuple):
            return resp
        body = _rebuild(resp, _store_item)
        if body is None:
            return ns((jsonify({'error': 'تعذر قراءة رد المنصة'}), 502))
        return ns(jsonify(body))
