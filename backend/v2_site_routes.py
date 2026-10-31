# -*- coding: utf-8 -*-
"""مسارات «الموقع» داخل قسم المحتوى (SPEC docs/v2/brain2/SPEC-B.md §B6).

    import v2_site_routes; v2_site_routes.register(app, globals())

قواعد ثابتة في كل المسارات (نفس قواعد v2_brain2_routes):
  * أدمن بس + المفتاح (`DASH_V2_ENABLED`) مفتوح، وإلا ٤٠٤ بلا أي نداء. `Cache-Control: no-store` على كل رد.
  * الفاعل من التوكن (`_actor_email`) لا من الجسم. كل كتابة تطلب `confirmed: true` بالضبط، وتُدقَّق.
  * ⛔ لا مسار هنا يكتب في الموقع: تعديل المؤسس ينشئ اقتراحًا بانتظار اعتماده من مسار «العقل» العادي
    (`POST /api/v2/brain/items/<id>/approve`)، والتنفيذ والإرجاع الفعليان بـSFTP يحدثان هناك أو في «أرجِع الصفحة» بتأكيد.

  GET    /api/v2/site/pages                 قائمة الصفحات المسموحة.
  GET    /api/v2/site/blocks?page=          كتل الصفحة من الموقع الحي (نداء HTTPS واحد) + بصمة النصوص.
  POST   /api/v2/site/edit                  {page, path, old, new, sha, confirmed} ⇒ اقتراح (مصدره المؤسس) بانتظار الاعتماد.
  GET    /api/v2/site/decisions             القواعد الفعّالة.   POST {text, confirmed} يضيف.   DELETE /<id> {confirmed} يحذف.
  GET    /api/v2/site/backups?page=         آخر ٢٠ نسخة للصفحة (بلا المحتوى).
  POST   /api/v2/site/restore               {page, backup_id, confirmed} ⇒ يرجع الصفحة لتلك النسخة.
"""
import re

import site_edit
from flask import jsonify, request

from brain2 import producers_site

ID_RE = re.compile(r'^[0-9a-f]{32}$')
ERR_BAD_PAGE = 'اختر صفحة من القائمة'
ERR_BAD_BODY = 'بيانات غير صالحة'
ERR_STALE_CLIENT = 'تغيّرت الصفحة منذ فتحتها؛ حدّث الكتل ثم أعد المحاولة'
ERR_NO_DECISION = 'هذه القاعدة غير موجودة'


def _iso(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=None).isoformat() + 'Z'


def register(app, ns):
    db = ns['db']
    token_required = ns['token_required']
    roles_required = ns['roles_required']
    site_edit.models(db)                      # الجداول تُعرَّف قبل db.create_all() (app.py ~11536)
    producers_site.decision_model(db)

    def L(name):
        return ns[name]

    def out(payload, status=200):
        return L('_v2_ns')((jsonify(payload), status) if status != 200 else jsonify(payload))

    def fail(e):
        return out({'error': e.message, 'code': e.code}, e.status)

    def gate():
        return L('_v2_closed')()

    def page_arg(source):
        page = source.get('page') if hasattr(source, 'get') else None
        return page if site_edit.page_allowed(page) else None

    # ------------------------------------------------------------------ الصفحات والكتل
    @app.route('/api/v2/site/pages', methods=['GET'], endpoint='v2_site_pages')
    @token_required
    @roles_required('admin')
    def v2_site_pages():
        closed = gate()
        if closed:
            return closed
        return out({'pages': [{'page': p, 'label': lab} for p, lab in site_edit.PAGES]})

    @app.route('/api/v2/site/blocks', methods=['GET'], endpoint='v2_site_blocks')
    @token_required
    @roles_required('admin')
    def v2_site_blocks():
        closed = gate()
        if closed:
            return closed
        page = page_arg(request.args)
        if page is None:
            return out({'error': ERR_BAD_PAGE}, 400)
        try:
            live = site_edit.fetch_live(page)
        except site_edit.SiteError as e:
            return fail(e)
        return out({'page': page, 'label': site_edit.LABELS[page], 'sha': live['sha'], 'blocks': live['blocks']})

    # ------------------------------------------------------------------ تعديل المؤسس ⇒ اقتراح
    @app.route('/api/v2/site/edit', methods=['POST'], endpoint='v2_site_edit')
    @token_required
    @roles_required('admin')
    def v2_site_edit():
        closed = gate()
        if closed:
            return closed
        body = L('_v2_body')()
        bad = L('_v2_confirmed')(body)
        if bad:
            return bad
        page = page_arg(body)
        if page is None:
            return out({'error': ERR_BAD_PAGE}, 400)
        path, old, new, sha = body.get('path'), body.get('old'), body.get('new'), body.get('sha')
        if not (isinstance(path, str) and isinstance(old, str) and isinstance(new, str) and isinstance(sha, str)):
            return out({'error': ERR_BAD_BODY}, 400)
        actor = L('_actor_email')()
        try:
            live = site_edit.fetch_live(page)
            if live['sha'] != sha:
                return out({'error': ERR_STALE_CLIENT, 'code': 'stale'}, 409)
            row = producers_site.propose_manual(ns, live, path, old, new, actor)
        except site_edit.SiteError as e:
            return fail(e)
        L('_audit')('v2_site.propose', target=row.id, meta={'page': page, 'path': path[:200]})
        return out({'ok': True, 'item_id': row.id, 'status': row.status, 'page': page})

    # ------------------------------------------------------------------ القرارات
    @app.route('/api/v2/site/decisions', methods=['GET'], endpoint='v2_site_decisions_get')
    @token_required
    @roles_required('admin')
    def v2_site_decisions_get():
        closed = gate()
        if closed:
            return closed
        return out({'decisions': [producers_site.decision_out(r) for r in producers_site.list_decisions(db)]})

    @app.route('/api/v2/site/decisions', methods=['POST'], endpoint='v2_site_decisions_post')
    @token_required
    @roles_required('admin')
    def v2_site_decisions_post():
        closed = gate()
        if closed:
            return closed
        body = L('_v2_body')()
        bad = L('_v2_confirmed')(body)
        if bad:
            return bad
        actor = L('_actor_email')()
        row, err = producers_site.add_decision(db, body.get('text'), actor)
        if row is None:
            return out({'error': err}, 400)
        L('_audit')('v2_site.decision_add', target=row.id, meta={'text': row.text[:200]})
        return out({'ok': True, 'decision': producers_site.decision_out(row)})

    @app.route('/api/v2/site/decisions/<decision_id>', methods=['DELETE'], endpoint='v2_site_decisions_delete')
    @token_required
    @roles_required('admin')
    def v2_site_decisions_delete(decision_id):
        closed = gate()
        if closed:
            return closed
        body = L('_v2_body')()
        bad = L('_v2_confirmed')(body)
        if bad:
            return bad
        if not ID_RE.match(decision_id or ''):
            return out({'error': ERR_BAD_BODY}, 400)
        if not producers_site.remove_decision(db, decision_id):
            return out({'error': ERR_NO_DECISION}, 404)
        L('_audit')('v2_site.decision_remove', target=decision_id)
        return out({'ok': True, 'id': decision_id})

    # ------------------------------------------------------------------ النسخ السابقة
    @app.route('/api/v2/site/backups', methods=['GET'], endpoint='v2_site_backups')
    @token_required
    @roles_required('admin')
    def v2_site_backups():
        closed = gate()
        if closed:
            return closed
        page = page_arg(request.args)
        if page is None:
            return out({'error': ERR_BAD_PAGE}, 400)
        rows = site_edit.list_backups(db, page)
        return out({'page': page, 'backups': [
            {'id': r['id'], 'sha256': r['sha256'][:12], 'created_at': _iso(r['created_at']), 'created_by': r['created_by'],
             'note': r['note'], 'size': r['size']} for r in rows]})

    @app.route('/api/v2/site/restore', methods=['POST'], endpoint='v2_site_restore')
    @token_required
    @roles_required('admin')
    def v2_site_restore():
        closed = gate()
        if closed:
            return closed
        body = L('_v2_body')()
        bad = L('_v2_confirmed')(body)
        if bad:
            return bad
        page = page_arg(body)
        if page is None:
            return out({'error': ERR_BAD_PAGE}, 400)
        bid = body.get('backup_id')
        if isinstance(bid, bool) or not isinstance(bid, int):
            return out({'error': ERR_BAD_BODY}, 400)
        actor = L('_actor_email')()
        res = site_edit.restore_backup(db, page, bid, actor)
        L('_audit')('v2_site.restore', target=page, meta={'backup_id': bid, 'ok': bool(res.get('ok')), 'code': res.get('code', '')})
        if not res.get('ok'):
            return out({'error': res.get('error') or ERR_BAD_BODY, 'code': res.get('code', '')}, res.get('status') or 400)
        return out({'ok': True, 'page': page, 'backup_id': bid})
