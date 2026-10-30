# -*- coding: utf-8 -*-
"""شاشات غير الأدمن (المدرّب · المستثمر · فريق المتابعة · الحساب بانتظار التفعيل) — مسارا الخادم.

  GET  /api/v2/roles/config    أي حساب مسجَّل: {enabled, role, linked} — مفتاح الشاشات الجديدة لغير الأدمن.
  POST /api/v2/roles/withdraw  مستثمر/مدرّب بمحفظة: حارس `confirmed:true` ثم **تفويض** لـ `request_withdrawal` الموجودة.

⛔ لا قاعدة فلوس هنا: الحد الأدنى والرصيد وصفّ الطلب كلها في `request_withdrawal` (مكان واحد). هذا الملف يتحقق من التأكيد والعملة
   والمبلغ فقط، ثم يسجّل سطر تدقيق عند النجاح. ⛔ لا نداء شبكة: المحفظة جدول في SQLite الداشبورد نفسه.
⛔ مفتاح رجوع خاص: `DASH_V2_ROLES_ENABLED=false` يعيد الشاشات القديمة لهذه الأدوار فقط، ولوحة الأدمن الجديدة تبقى شغّالة.
"""
import os
import sys

from flask import g, jsonify, request


def register(app):
    M = sys.modules[app.import_name]
    token_required = M.token_required
    roles_required = M.roles_required

    def roles_enabled():
        """مفتاح الأدمن مفتوح **و** مفتاح الأدوار غير مقفول صراحة (غير المضبوط يتبع المفتاح الرئيسي)."""
        return bool(M._v2_enabled()) and (os.environ.get('DASH_V2_ROLES_ENABLED') or 'true').strip().lower() != 'false'

    def ns(resp):
        return M._v2_ns(resp)

    @app.route('/api/v2/roles/config', methods=['GET'])
    @token_required
    def v2_roles_config():
        return ns(jsonify({'enabled': roles_enabled(), 'role': M.reported_role(g.user), 'linked': bool(M.entitlement_key(g.user))}))

    @app.route('/api/v2/roles/withdraw', methods=['POST'])
    @token_required
    @roles_required('investor', 'trainer')
    def v2_roles_withdraw():
        if not roles_enabled():
            return ns((jsonify({'error': 'غير متاح'}), 404))
        body = request.get_json(silent=True)
        body = body if isinstance(body, dict) else {}
        if body.get('confirmed') is not True:
            return ns((jsonify({'error': M.V2_CONFIRM_AR}), 400))
        amount = body.get('amount')
        ok = (isinstance(amount, (int, float)) and not isinstance(amount, bool) and amount == amount
              and amount not in (float('inf'), float('-inf')) and amount > 0)
        if not ok or body.get('currency') != 'EGP':
            return ns((jsonify({'error': 'اكتب مبلغًا صحيحًا'}), 400))
        rv = app.view_functions['request_withdrawal']()
        resp, code = rv if isinstance(rv, tuple) else (rv, 200)
        if 200 <= code < 300:
            item_id = (resp.get_json(silent=True) or {}).get('id')
            M._audit('roles.withdraw', target=item_id, meta={'amount': amount, 'currency': 'EGP'})
        resp.headers['Cache-Control'] = 'no-store'
        return resp, code
