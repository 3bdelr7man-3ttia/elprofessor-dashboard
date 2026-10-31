# -*- coding: utf-8 -*-
"""«الأنظمة المتصلة» — مسارات الإدارة (SPEC-B B5). المنطق في `brain2/links.py` و`mcp_server.py`.

قواعد ثابتة (نفس `v2_brain2_keys_routes`):
  * أدمن بس + المفتاح (`DASH_V2_ENABLED`) مفتوح وإلا ٤٠٤. `Cache-Control: no-store` على كل رد.
  * الفاعل من التوكن (`_actor_email`). الكتابة تطلب `confirmed: true`.
  * ⛔ لا رد يحمل `token_enc` ولا `hash` ولا نص رمز مخزَّن. النص الصريح لرمز الدخول إلى اللوحة يظهر مرة واحدة في ردّ إنشائه فقط.
  * ⛔ «جرّب الاتصال» نداءان فقط (`initialize` ثم `tools/list`) ولا يستدعي أي أداة؛ وأخطاؤه جمل عربية بيضاء.
  * هذه الوحدة تسجّل أيضًا نقطة `/api/mcp` (`mcp_server.register`) بسطر واحد في app.py.
  * التدقيق: `brain.link_add|link_update|link_delete|link_test` و`brain.mcp_token_create|mcp_token_revoke`، وميتاها بلا أي رمز.
"""
import datetime
import logging
import os
import re
import uuid

from flask import jsonify

from brain2 import keys as K
from brain2 import links as LK

logger = logging.getLogger(__name__)

ID_RE = re.compile(r'^[0-9a-f]{32}$')
SERVER_URL_DEFAULT = 'https://dashboard.elprofessor.net/api/mcp'
ERR_BAD_ID = 'معرّف غير صالح'
ERR_NAME = 'اكتب اسمًا من حرف إلى ٦٠ حرفًا'
ERR_URL = 'اكتب عنوانًا يبدأ بـ https://'
ERR_TOKEN = 'الرمز غير مكتمل أو فيه مسافات'
ERR_BRAND = 'معرّف العلامة غير صالح'
ERR_NOTHING = 'لا تعديل مطلوب'
ERR_FULL = 'وصلت إلى حدّ الأنظمة المتصلة. احذف نظامًا قبل إضافة غيره'
ERR_NOT_FOUND = 'هذا النظام غير موجود'
ERR_T_NAME = 'اكتب اسمًا من حرف إلى ٣٦ حرفًا'
ERR_T_SCOPE = 'اختر صلاحية الرمز'
ERR_T_DUP = 'يوجد رمز عامل بهذا الاسم'
ERR_T_FULL = 'وصلت إلى حدّ الرموز العاملة. ألغِ رمزًا قبل إنشاء غيره'
ERR_T_NOT_FOUND = 'هذا الرمز غير موجود'
ERR_T_REVOKED = 'أُلغي هذا الرمز من قبل'
ERR_SECRET = 'تعذّر الحفظ الآن'
ERR_URL_NEEDS_TOKEN = 'غيّرت العنوان؛ أدخل الرمز من جديد'
TOKEN_MIN, TOKEN_MAX = 8, 600


def _iso(dt):
    from v2_brain_routes import _utc_iso
    return _utc_iso(dt)


def server_url():
    return (os.environ.get('DASH_MCP_URL') or '').strip() or SERVER_URL_DEFAULT


def register(app, ns):
    import mcp_server
    db = ns['db']
    Link = LK._models(db)
    Token = mcp_server._models(db)
    token_required = ns['token_required']
    roles_required = ns['roles_required']
    try:
        mcp_server.register(app, ns)
    except Exception:   # noqa: BLE001 — لا تسقط لوحة الإدارة بسبب نقطة الخادم
        logger.exception('mcp server endpoint not registered')

    def L(name):
        return ns[name]

    def out(payload, status=200):
        return L('_v2_ns')((jsonify(payload), status) if status != 200 else jsonify(payload))

    def gate():
        return L('_v2_closed')()

    def confirmed_body():
        body = L('_v2_body')()
        return body, L('_v2_confirmed')(body)

    def bad_id(i, err=ERR_BAD_ID):
        return None if ID_RE.match(i or '') else out({'error': err}, 400)

    # ------------------------------------------------------------------ عرض
    def link_out(r):
        """قايمة بيضا. ⛔ لا token_enc ولا نص الرمز."""
        from brain2 import producers_links
        readable = LK.token_of(r) is not None
        d = {'id': r.id, 'name': r.name, 'url': r.url, 'enabled': bool(r.enabled), 'brand_id': r.brand_id or '',
             'readable': bool(readable), 'known': producers_links.system_of(r.name) is not None,
             'last_ok_at': _iso(r.last_ok_at), 'last_error': r.last_error or '',
             'created_at': _iso(r.created_at), 'created_by': r.created_by or ''}
        if not readable:
            d['notice'] = LK.ERR_UNREADABLE
        return d

    def token_out(r):
        """قايمة بيضا. ⛔ لا hash ولا نص الرمز."""
        return {'id': r.id, 'name': r.name, 'scopes': r.scopes, 'can_propose': mcp_server.can_propose(r),
                'created_at': _iso(r.created_at), 'created_by': r.created_by or '',
                'last_used_at': _iso(r.last_used_at), 'revoked_at': _iso(r.revoked_at)}

    def clean_token(raw):
        t = raw.strip() if isinstance(raw, str) else ''
        return t if TOKEN_MIN <= len(t) <= TOKEN_MAX and re.match(r'^[\x21-\x7e]+$', t) else None

    # ================================================================== رموز الدخول إلى هذه اللوحة
    @app.route('/api/v2/brain/mcp-tokens', methods=['GET'], endpoint='v2_brain2_mcp_tokens_get')
    @token_required
    @roles_required('admin')
    def v2_brain2_mcp_tokens_get():
        closed = gate()
        if closed:
            return closed
        rows = Token.query.order_by(Token.created_at.desc(), Token.id).all()
        return out({'tokens': [token_out(r) for r in rows], 'server_url': server_url(), 'protocol': mcp_server.PROTOCOL,
                    'tools': list(mcp_server.TOOLS)})

    @app.route('/api/v2/brain/mcp-tokens', methods=['POST'], endpoint='v2_brain2_mcp_tokens_add')
    @token_required
    @roles_required('admin')
    def v2_brain2_mcp_tokens_add():
        closed = gate()
        if closed:
            return closed
        body, bad = confirmed_body()
        if bad:
            return bad
        name = LK.clean_name(body.get('name'))
        if not name or len(name) > mcp_server.TOKEN_NAME_MAX:
            return out({'error': ERR_T_NAME}, 400)
        scopes = body.get('scopes')
        if scopes == 'propose':
            scopes = 'read,propose'
        if scopes not in mcp_server.SCOPES:
            return out({'error': ERR_T_SCOPE}, 400)
        active = Token.query.filter(Token.revoked_at == None).all()   # noqa: E711
        if any(a.name == name for a in active):
            return out({'error': ERR_T_DUP}, 409)
        if len(active) >= mcp_server.TOKENS_CAP:
            return out({'error': ERR_T_FULL}, 409)
        raw, hashed = mcp_server.new_token()
        row = Token(id=uuid.uuid4().hex, name=name, hash=hashed, scopes=scopes, created_by=L('_actor_email')(),
                    created_at=datetime.datetime.utcnow())
        db.session.add(row)
        db.session.commit()
        L('_audit')('brain.mcp_token_create', target=row.id, meta={'name': name, 'scopes': scopes})
        # ⛔ النص الصريح يخرج هنا مرة واحدة فقط ولا يُخزَّن.
        return out({'token': raw, 'item': token_out(row), 'server_url': server_url(), 'warning': 'يظهر الرمز مرة واحدة فقط'})

    @app.route('/api/v2/brain/mcp-tokens/<token_id>', methods=['DELETE'], endpoint='v2_brain2_mcp_tokens_revoke')
    @token_required
    @roles_required('admin')
    def v2_brain2_mcp_tokens_revoke(token_id):
        closed = gate()
        if closed:
            return closed
        _, bad = confirmed_body()
        if bad:
            return bad
        bad = bad_id(token_id)
        if bad:
            return bad
        row = Token.query.get(token_id)
        if row is None:
            return out({'error': ERR_T_NOT_FOUND}, 404)
        changed = Token.query.filter(Token.id == token_id, Token.revoked_at == None).update(   # noqa: E711
            {'revoked_at': datetime.datetime.utcnow()}, synchronize_session=False)
        db.session.commit()
        if changed != 1:
            return out({'error': ERR_T_REVOKED}, 409)
        L('_audit')('brain.mcp_token_revoke', target=token_id, meta={'name': row.name})
        db.session.expire_all()
        return out({'ok': True, 'item': token_out(Token.query.get(token_id))})

    # ================================================================== الأنظمة المتصلة
    @app.route('/api/v2/brain/links', methods=['GET'], endpoint='v2_brain2_links_get')
    @token_required
    @roles_required('admin')
    def v2_brain2_links_get():
        closed = gate()
        if closed:
            return closed
        rows = Link.query.order_by(Link.created_at.desc(), Link.id).all()
        return out({'links': [link_out(r) for r in rows]})

    @app.route('/api/v2/brain/links', methods=['POST'], endpoint='v2_brain2_links_add')
    @token_required
    @roles_required('admin')
    def v2_brain2_links_add():
        closed = gate()
        if closed:
            return closed
        body, bad = confirmed_body()
        if bad:
            return bad
        name = LK.clean_name(body.get('name'))
        if not name or len(name) > LK.NAME_MAX:
            return out({'error': ERR_NAME}, 400)
        url = K.normalize_url(body.get('url'))
        if url is None:
            return out({'error': ERR_URL}, 400)
        token = clean_token(body.get('token'))
        if token is None:
            return out({'error': ERR_TOKEN}, 400)
        brand = None
        if body.get('brand_id') not in (None, ''):
            brand = LK.clean_brand(body.get('brand_id'))
            if brand is None:
                return out({'error': ERR_BRAND}, 400)
        if Link.query.count() >= LK.LINKS_CAP:
            return out({'error': ERR_FULL}, 409)
        try:
            enc = K.encrypt(token)
        except ValueError:
            logger.error('brain links: no secret configured — cannot store a token')
            return out({'error': ERR_SECRET}, 503)
        row = Link(id=uuid.uuid4().hex, name=name, url=url, token_enc=enc, enabled=True, brand_id=brand,
                   created_at=datetime.datetime.utcnow(), created_by=L('_actor_email')())
        db.session.add(row)
        db.session.commit()
        L('_audit')('brain.link_add', target=row.id, meta={'name': name})
        return out({'link': link_out(row)})

    @app.route('/api/v2/brain/links/<link_id>', methods=['PUT'], endpoint='v2_brain2_links_put')
    @token_required
    @roles_required('admin')
    def v2_brain2_links_put(link_id):
        closed = gate()
        if closed:
            return closed
        body, bad = confirmed_body()
        if bad:
            return bad
        bad = bad_id(link_id)
        if bad:
            return bad
        row = Link.query.get(link_id)
        if row is None:
            return out({'error': ERR_NOT_FOUND}, 404)
        ch = {}
        if body.get('name') is not None:
            name = LK.clean_name(body['name'])
            if not name or len(name) > LK.NAME_MAX:
                return out({'error': ERR_NAME}, 400)
            ch['name'] = name
        if body.get('url') is not None:
            url = K.normalize_url(body['url'])
            if url is None:
                return out({'error': ERR_URL}, 400)
            if url != row.url and body.get('token') in (None, ''):
                return out({'error': ERR_URL_NEEDS_TOKEN}, 400)    # ⛔ لا يُرسَل رمز محفوظ إلى عنوان تغيّر
            ch['url'] = url
        if body.get('token') not in (None, ''):
            token = clean_token(body['token'])
            if token is None:
                return out({'error': ERR_TOKEN}, 400)
            try:
                ch['token_enc'] = K.encrypt(token)
            except ValueError:
                return out({'error': ERR_SECRET}, 503)
        if body.get('enabled') is not None:
            if not isinstance(body['enabled'], bool):
                return out({'error': ERR_NOTHING}, 400)
            ch['enabled'] = body['enabled']
        if 'brand_id' in body:
            if body['brand_id'] in (None, ''):
                ch['brand_id'] = None
            else:
                brand = LK.clean_brand(body['brand_id'])
                if brand is None:
                    return out({'error': ERR_BRAND}, 400)
                ch['brand_id'] = brand
        if not ch:
            return out({'error': ERR_NOTHING}, 400)
        for k, v in ch.items():
            setattr(row, k, v)
        if 'url' in ch or 'token_enc' in ch:
            row.last_ok_at, row.last_error = None, None          # التجربة القديمة لعنوان/رمز آخر
        db.session.commit()
        L('_audit')('brain.link_update', target=row.id, meta={'name': row.name, 'fields': sorted(k for k in ch if k != 'token_enc') + (['token'] if 'token_enc' in ch else [])})
        return out({'link': link_out(row)})

    @app.route('/api/v2/brain/links/<link_id>', methods=['DELETE'], endpoint='v2_brain2_links_delete')
    @token_required
    @roles_required('admin')
    def v2_brain2_links_delete(link_id):
        closed = gate()
        if closed:
            return closed
        _, bad = confirmed_body()
        if bad:
            return bad
        bad = bad_id(link_id)
        if bad:
            return bad
        row = Link.query.get(link_id)
        if row is None:
            return out({'error': ERR_NOT_FOUND}, 404)
        name = row.name
        db.session.delete(row)
        db.session.commit()
        L('_audit')('brain.link_delete', target=link_id, meta={'name': name})
        return out({'ok': True, 'id': link_id})

    @app.route('/api/v2/brain/links/<link_id>/test', methods=['POST'], endpoint='v2_brain2_links_test')
    @token_required
    @roles_required('admin')
    def v2_brain2_links_test(link_id):
        closed = gate()
        if closed:
            return closed
        bad = bad_id(link_id)
        if bad:
            return bad
        row = Link.query.get(link_id)
        if row is None:
            return out({'error': ERR_NOT_FOUND}, 404)
        res, err = None, ''
        try:
            res = LK.probe(row)                      # initialize + tools/list فقط؛ ⛔ لا نداء أداة
        except LK.LinkError as exc:
            err = exc.message
        except Exception as exc:   # noqa: BLE001
            logger.error('brain link test failed (%s): %s', row.id, type(exc).__name__)
            err = LK.ERR_CONNECT
        LK.mark(db, row, res is not None, err)
        L('_audit')('brain.link_test', target=row.id, meta={'name': row.name, 'ok': res is not None})
        payload = {'ok': res is not None, 'error': err, 'link': link_out(row)}
        if res is not None:
            payload.update({'count': res['count'], 'tools': res['tools'], 'server': res['server']})
        return out(payload)
