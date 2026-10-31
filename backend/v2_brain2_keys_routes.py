# -*- coding: utf-8 -*-
"""«المفاتيح والكاتب» — مسارات الخادم (SPEC-B B1). المنطق في `brain2/keys.py`.

قواعد ثابتة في كل المسارات (نفس `v2_brain2_routes`):
  * أدمن بس + المفتاح (`DASH_V2_ENABLED`) مفتوح وإلا ٤٠٤. `Cache-Control: no-store` على كل رد.
  * الفاعل من التوكن (`_actor_email`). الكتابة تطلب `confirmed: true`.
  * ⛔ لا رد يحمل `key_enc` ولا النص الصريح للمفتاح: `row_out` قايمة بيضا، والمفتاح يظهر `key_tail` فقط.
  * ⛔ الاختبار نداء واحد صغير عبر الناقل نفسه الذي تستعمله `ai_call`، ويُحسب من السقف اليومي؛ وأخطاؤه جمل عربية بيضاء (لا نص من المزوّد).
  * التدقيق: `brain.key_add|key_update|key_delete|key_test` وميتاها {preset, tail} فقط.
"""
import datetime
import logging
import re
import uuid

from flask import jsonify

from brain2 import keys as K

logger = logging.getLogger(__name__)

ID_RE = re.compile(r'^[0-9a-f]{32}$')
TEST_SYSTEM = 'أنت تختبر الاتصال فقط. أجب بكلمة واحدة.'
TEST_USER = 'أجب بكلمة: تم'
CAP_AR = 'بلغنا سقف نداءات اليوم. جرّب غدًا'


def _iso(dt):
    from v2_brain_routes import _utc_iso
    return _utc_iso(dt)


def register(app, ns):
    db = ns['db']
    Key = K._models(db)
    token_required = ns['token_required']
    roles_required = ns['roles_required']

    def L(name):
        return ns[name]

    def out(payload, status=200):
        return L('_v2_ns')((jsonify(payload), status) if status != 200 else jsonify(payload))

    def gate():
        return L('_v2_closed')()

    def row_out(r):
        """قايمة بيضا. ⛔ لا key_enc ولا نص المفتاح. العنوان يظهر لمن أدخله بنفسه فقط (أخرى / OpenRouter)."""
        p = K.preset_of(r.preset)
        readable = K.decrypt(r.key_enc) is not None
        d = {'id': r.id, 'label': r.label, 'preset': r.preset or '', 'kind': r.kind,
             'base_url': (r.base_url or '') if (p and p['needs_url']) else '', 'model': r.model or '',
             'key_tail': r.key_tail or '', 'role': r.role, 'readable': bool(readable),
             'created_at': _iso(r.created_at), 'created_by': r.created_by or '',
             'last_test_at': _iso(r.last_test_at), 'last_test_ok': r.last_test_ok,
             'last_test_error': r.last_test_error or ''}
        if not readable:
            d['notice'] = K.UNREADABLE_AR
        return d

    def bad_id(key_id):
        return None if ID_RE.match(key_id or '') else out({'error': K.ERR_BAD_ID}, 400)

    def confirmed_body():
        body = L('_v2_body')()
        return body, L('_v2_confirmed')(body)

    def audit(action, r):
        L('_audit')(action, target=r.id, meta={'preset': r.preset or '', 'tail': r.key_tail or ''})

    def make_room(role, except_id=None):
        """دور واحد لكل من الأساسي والاحتياطي: الأساسي القديم يصير احتياطيًّا (SPEC)، وأي احتياطي سابق يصير موقوفًا."""
        other = (except_id or '')
        if role in ('main', 'backup'):
            for old in Key.query.filter(Key.role == 'backup', Key.id != other).all():
                old.role = 'off'
        if role == 'main':
            for old in Key.query.filter(Key.role == 'main', Key.id != other).all():
                old.role = 'backup'

    # ------------------------------------------------------------------ قراءة
    @app.route('/api/v2/brain/keys', methods=['GET'], endpoint='v2_brain2_keys_get')
    @token_required
    @roles_required('admin')
    def v2_brain2_keys_get():
        closed = gate()
        if closed:
            return closed
        rows = Key.query.order_by(Key.created_at.desc(), Key.id).all()
        return out({'keys': [row_out(r) for r in rows], 'presets': K.presets_public()})

    # ------------------------------------------------------------------ إضافة
    @app.route('/api/v2/brain/keys', methods=['POST'], endpoint='v2_brain2_keys_add')
    @token_required
    @roles_required('admin')
    def v2_brain2_keys_add():
        closed = gate()
        if closed:
            return closed
        body, bad = confirmed_body()
        if bad:
            return bad
        preset = K.preset_of(body.get('preset'))
        if preset is None:
            return out({'error': K.ERR_PRESET}, 400)
        label = K.clean_line(body.get('label'), K.LABEL_MAX) if body.get('label') not in (None, '') else preset['label']
        if not label or len(label) > K.LABEL_MAX:
            return out({'error': K.ERR_LABEL}, 400)
        model = body.get('model')
        model = model.strip() if isinstance(model, str) else ''
        if not model:
            model = preset['model']
        if not K.valid_model(model):
            return out({'error': K.ERR_MODEL}, 400)
        kind, url = K.resolve_target(preset, body.get('base_url'))
        if kind is None:
            return out({'error': K.ERR_URL}, 400)
        key = body.get('key')
        key = key.strip() if isinstance(key, str) else ''
        if not K.valid_key_text(key):
            return out({'error': K.ERR_KEY}, 400)
        role = body.get('role') if body.get('role') is not None else 'backup'
        if role not in K.ROLES:
            return out({'error': K.ERR_ROLE}, 400)
        if Key.query.count() >= K.KEYS_CAP:
            return out({'error': K.ERR_FULL}, 409)
        try:
            enc = K.encrypt(key)
        except ValueError:
            logger.error('brain keys: no secret configured — cannot store a key')
            return out({'error': 'تعذّر حفظ المفتاح الآن'}, 503)
        actor = L('_actor_email')()
        make_room(role)
        row = Key(id=uuid.uuid4().hex, label=label, preset=preset['id'], kind=kind, base_url=url or '', model=model,
                  key_enc=enc, key_tail=K.tail_of(key), role=role, created_at=datetime.datetime.utcnow(), created_by=actor)
        db.session.add(row)
        db.session.commit()
        audit('brain.key_add', row)
        return out({'key': row_out(row)})

    # ------------------------------------------------------------------ تعديل
    @app.route('/api/v2/brain/keys/<key_id>', methods=['PUT'], endpoint='v2_brain2_keys_put')
    @token_required
    @roles_required('admin')
    def v2_brain2_keys_put(key_id):
        closed = gate()
        if closed:
            return closed
        body, bad = confirmed_body()
        if bad:
            return bad
        bad = bad_id(key_id)
        if bad:
            return bad
        row = Key.query.get(key_id)
        if row is None:
            return out({'error': K.ERR_NOT_FOUND}, 404)
        changes = {}
        if body.get('role') is not None:
            if body['role'] not in K.ROLES:
                return out({'error': K.ERR_ROLE}, 400)
            changes['role'] = body['role']
        if body.get('model') is not None:
            m = body['model'].strip() if isinstance(body['model'], str) else ''
            if not K.valid_model(m):
                return out({'error': K.ERR_MODEL}, 400)
            changes['model'] = m
        if body.get('label') is not None:
            lab = K.clean_line(body['label'], K.LABEL_MAX)
            if not lab or len(lab) > K.LABEL_MAX:
                return out({'error': K.ERR_LABEL}, 400)
            changes['label'] = lab
        if not changes:
            return out({'error': K.ERR_NOTHING}, 400)
        if 'role' in changes:
            make_room(changes['role'], except_id=row.id)
            row.role = changes['role']
        if 'model' in changes:
            row.model = changes['model']
            row.last_test_ok, row.last_test_at, row.last_test_error = None, None, None   # الاختبار القديم لموديل آخر
        if 'label' in changes:
            row.label = changes['label']
        db.session.commit()
        audit('brain.key_update', row)
        return out({'key': row_out(row)})

    # ------------------------------------------------------------------ حذف
    @app.route('/api/v2/brain/keys/<key_id>', methods=['DELETE'], endpoint='v2_brain2_keys_delete')
    @token_required
    @roles_required('admin')
    def v2_brain2_keys_delete(key_id):
        closed = gate()
        if closed:
            return closed
        _, bad = confirmed_body()
        if bad:
            return bad
        bad = bad_id(key_id)
        if bad:
            return bad
        row = Key.query.get(key_id)
        if row is None:
            return out({'error': K.ERR_NOT_FOUND}, 404)
        preset, tail = row.preset or '', row.key_tail or ''
        db.session.delete(row)
        db.session.commit()
        L('_audit')('brain.key_delete', target=key_id, meta={'preset': preset, 'tail': tail})
        return out({'ok': True, 'id': key_id})

    # ------------------------------------------------------------------ اختبار
    @app.route('/api/v2/brain/keys/<key_id>/test', methods=['POST'], endpoint='v2_brain2_keys_test')
    @token_required
    @roles_required('admin')
    def v2_brain2_keys_test(key_id):
        closed = gate()
        if closed:
            return closed
        bad = bad_id(key_id)
        if bad:
            return bad
        row = Key.query.get(key_id)
        if row is None:
            return out({'error': K.ERR_NOT_FOUND}, 404)
        key = K.decrypt(row.key_enc)
        ok, err = False, ''
        if not key:
            err = K.UNREADABLE_AR                       # لا نداء ولا حجز من السقف
        else:
            allowed, _usage = L('_ai_reserve_call')()   # الاختبار يُحسب من السقف اليومي (يُحجز قبل لمس الشبكة)
            if not allowed:
                return out({'error': CAP_AR, 'reason': 'cap'}, 429)
            spec = K.row_spec(row, key)
            try:
                text = L('_ai_send_spec')(spec, TEST_SYSTEM, TEST_USER)
                if (text or '').strip():
                    ok = True
                else:
                    err = K.NO_REPLY_AR
            except Exception as exc:   # noqa: BLE001
                err = K.classify_error(exc)
                logger.error('brain key test failed (key=%s, %s): %s', row.id, row.preset, type(exc).__name__)
        row.last_test_at, row.last_test_ok, row.last_test_error = datetime.datetime.utcnow(), ok, (None if ok else err)
        db.session.commit()
        audit('brain.key_test', row)
        return out({'ok': ok, 'error': err, 'key': row_out(row)})
