# -*- coding: utf-8 -*-
"""R24 م١ — «بعدين» و«تجاهل» على الخادم · الشريط قرارات بس · تصليح الأزرار الميتة · لا بيانات تجريبية · العدّاد واحد.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r24_dash_p1.py

⛔ صفر شبكة حقيقية وصفر نداء للمنصة: أي نداء `requests` بيوقّع الاختبار، والمنطق (v2-logic.js) والمحمّلات (dashboard-api.js) بيتشغّلوا
في node:vm بردود جاهزة (`uiharness/r24_ep.js`).
  ١. مسارات الخادم الأربعة: أدمن بس · المفتاح مقفول ⇒ ٤٠٤ · `until` إجباري ومستقبلي · السبب إجباري للتجاهل · «تجاهل» مرفوض لأنواع الفلوس
     وأنواع صاحبها مستني رد · رجّعها · تدقيق لكل فعل · مفيش نداء للمنصة · مسح المؤجَّل القديم.
  ٢. المنطق: الشريط قرارات بس · «للعلم» · الدالة المشتركة للإخفاء (ميعاد · بصمة الحالة · تجاهل) · العدّاد واحد (المربّع = الشريط).
  ٣. المحمّلات: `INBOX` مرئي بس والمخفي في `INBOX_SNOOZED` · فعل بعدين/تجاهل/رجّعها يمشي على المسار الصح · «افتح المنصة» يعمل ack للتسجيل.
  ٤. ثابت: الأزرار الميتة والعناوين والبيانات التجريبية والنجاح الوهمي.
"""
import datetime
import json
import os
import re
import subprocess
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
DC = os.path.join(ROOT, 'dashboard-cloud')
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


API_JS = _read('dashboard-cloud', 'dashboard-api.js')
HOME_JS = _read('dashboard-cloud', 'v2-home.js')
LOGIC_JS = _read('dashboard-cloud', 'v2-logic.js')
PEOPLE_JS = _read('dashboard-cloud', 'v2s', 'people.js')
MARKETING_JS = _read('dashboard-cloud', 'v2s', 'marketing.js')
D3_JS = _read('dashboard-cloud', 'v2-d3.js')
HTML = _read('dashboard-cloud', 'index.html')
TG_OPS = _read('backend', 'tg_ops.py')


def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role,
                 dashboard_role=role, linked_to_name='', preferred_currency='AUTO', is_active=True)
        db.session.add(u)
        db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('r24-%s@x.test' % r, r)) for r in ('admin', 'employee', 'viewer', 'investor', 'trainer')}
        yield {'heads': heads, 'client': flask_app.test_client()}


@pytest.fixture(autouse=True)
def v2_on_no_platform(monkeypatch):
    """المفتاح مفتوح، وأي نداء للمنصة (requests) بيوقّع الاختبار — الجدول محلي ومفيش حاجة تروح بره."""
    import app as appmod
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')

    def boom(*a, **k):
        raise AssertionError('نداء للمنصة ممنوع هنا: %r' % (a[:2],))
    monkeypatch.setattr(appmod.requests, 'request', boom)
    monkeypatch.setattr(appmod.requests, 'get', boom)
    yield


def _call(ctx, method, path, body=None, who='admin'):
    return ctx['client'].open(path, method=method, headers={} if who is None else ctx['heads'][who], json=body)


def _future(days=2):
    return (datetime.datetime.utcnow() + datetime.timedelta(days=days)).replace(microsecond=0).isoformat() + 'Z'


def _past():
    return (datetime.datetime.utcnow() - datetime.timedelta(hours=1)).replace(microsecond=0).isoformat() + 'Z'


def _audits(action, target=None):
    q = AuditLog.query.filter_by(action=action)
    if target:
        q = q.filter_by(target=target)
    return q.count()


def _ensure_table():
    from sqlalchemy import text
    db.session.execute(text('CREATE TABLE IF NOT EXISTS decision_snooze (item_key TEXT PRIMARY KEY, until TEXT NULL, kind TEXT NOT NULL DEFAULT \'snooze\', '
                            'reason TEXT NOT NULL DEFAULT \'\', by TEXT NOT NULL DEFAULT \'\', created_at TEXT NOT NULL, fingerprint TEXT NOT NULL DEFAULT \'\')'))
    db.session.commit()


def _clear():
    from sqlalchemy import text
    _ensure_table()
    db.session.execute(text('DELETE FROM decision_snooze'))
    db.session.commit()


# ——————————————————————————————————————————————————————— ١. مسارات الخادم

def test_table_is_created_idempotently_with_the_spec_columns(ctx):
    from sqlalchemy import text
    r = _call(ctx, 'GET', '/api/v2/decisions/snoozed')
    assert r.status_code == 200
    cols = [row[1] for row in db.session.execute(text('PRAGMA table_info(decision_snooze)')).fetchall()]
    for c in ('item_key', 'until', 'kind', 'reason', 'by', 'created_at'):
        assert c in cols
    assert 'fingerprint' in cols            # بصمة حالة البند (للرجوع لو الحالة اتغيّرت)
    assert _call(ctx, 'GET', '/api/v2/decisions/snoozed').status_code == 200   # تاني مرة: مفيش كسر


@pytest.mark.parametrize('method,path', [
    ('GET', '/api/v2/decisions/snoozed'),
    ('POST', '/api/v2/decisions/signup:u1/snooze'),
    ('POST', '/api/v2/decisions/signup:u1/dismiss'),
    ('POST', '/api/v2/decisions/signup:u1/restore'),
])
def test_admin_only_and_closed_switch(ctx, monkeypatch, method, path):
    assert _call(ctx, method, path, {}, who=None).status_code == 401
    for who in ('employee', 'viewer', 'investor', 'trainer'):
        assert _call(ctx, method, path, {}, who=who).status_code == 403, who
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = _call(ctx, method, path, {'until': _future(), 'reason': 'تمام'})
    assert r.status_code == 404                                            # المفتاح مقفول = كأن المسار مش موجود
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    assert _call(ctx, 'GET', '/api/v2/decisions/snoozed').headers.get('Cache-Control') == 'no-store'


def test_snooze_validation_until_is_required_and_in_the_future(ctx):
    _clear()
    base = '/api/v2/decisions/payout:p-1/snooze'
    assert _call(ctx, 'POST', base, {}).status_code == 400                       # until إجباري
    assert _call(ctx, 'POST', base, {'until': ''}).status_code == 400
    assert _call(ctx, 'POST', base, {'until': 'بكرة'}).status_code == 400        # مش تاريخ
    r = _call(ctx, 'POST', base, {'until': _past()})
    assert r.status_code == 400 and 'المستقبل' in r.get_json()['error']
    far = (datetime.datetime.utcnow() + datetime.timedelta(days=400)).isoformat() + 'Z'
    assert _call(ctx, 'POST', base, {'until': far}).status_code == 400            # أقصى تأجيل سنة
    assert _call(ctx, 'GET', '/api/v2/decisions/snoozed').get_json()['rows'] == []   # الرفض ما كتبش حاجة


def test_the_browser_sends_the_key_percent_encoded_and_it_still_matches(ctx):
    _clear()
    r = _call(ctx, 'POST', '/api/v2/decisions/signup%3Au-enc/snooze', {'until': _future()})
    assert r.status_code == 200 and r.get_json()['key'] == 'signup:u-enc'
    assert _call(ctx, 'POST', '/api/v2/decisions/signup%3Au-enc/restore').get_json()['removed'] is True


def test_bad_keys_and_unknown_types_are_refused(ctx):
    for key in ('nocolon', 'payout:', ':1', 'Payout:1', 'weird_type:1', 'x' * 40 + ':1'):
        r = _call(ctx, 'POST', '/api/v2/decisions/%s/snooze' % key, {'until': _future()})
        assert r.status_code in (400, 404), key
    assert _call(ctx, 'POST', '/api/v2/decisions/madeup:1/snooze', {'until': _future()}).status_code == 400


def test_snooze_roundtrip_listing_audit_and_restore(ctx):
    _clear()
    until = _future(3)
    r = _call(ctx, 'POST', '/api/v2/decisions/trainer:t-77/snooze', {'until': until, 'fingerprint': 'a|b'})
    assert r.status_code == 200 and r.get_json()['ok'] is True and r.get_json()['kind'] == 'snooze'
    rows = _call(ctx, 'GET', '/api/v2/decisions/snoozed').get_json()['rows']
    assert len(rows) == 1
    row = rows[0]
    assert row['key'] == 'trainer:t-77' and row['type'] == 'trainer' and row['id'] == 't-77'
    assert row['until'] == until and row['kind'] == 'snooze' and row['fingerprint'] == 'a|b'
    assert row['by'] == 'r24-admin@x.test' and row['created_at'].endswith('Z')
    assert _audits('decision.snooze', 'trainer:t-77') >= 1
    # تأجيل تاني لنفس البند يستبدل (مفتاح أساسي واحد)
    _call(ctx, 'POST', '/api/v2/decisions/trainer:t-77/snooze', {'until': _future(5)})
    assert len(_call(ctx, 'GET', '/api/v2/decisions/snoozed').get_json()['rows']) == 1
    # رجّعها
    r = _call(ctx, 'POST', '/api/v2/decisions/trainer:t-77/restore')
    assert r.status_code == 200 and r.get_json()['removed'] is True
    assert _call(ctx, 'GET', '/api/v2/decisions/snoozed').get_json()['rows'] == []
    assert _audits('decision.restore', 'trainer:t-77') >= 1
    again = _call(ctx, 'POST', '/api/v2/decisions/trainer:t-77/restore')
    assert again.status_code == 200 and again.get_json()['removed'] is False       # مرتين = مفيش كسر ولا تدقيق زيادة


@pytest.mark.parametrize('key', ['payout:p1', 'manual_payment:m1', 'dispute:d1', 'legacy:l1', 'unactivated:u1', 'file:f1', 'book_offer:o1',
                                 'trainer:t1', 'join:j1', 'pending_user:pu1', 'identity_doc:i1', 'founding:f1'])
def test_dismiss_is_refused_for_money_and_waiting_types(ctx, key):
    _clear()
    r = _call(ctx, 'POST', '/api/v2/decisions/%s/dismiss' % key, {'reason': 'مش مهم'})
    assert r.status_code == 409 and r.get_json().get('refused') is True and 'ارفضه' in r.get_json()['error']
    assert _call(ctx, 'GET', '/api/v2/decisions/snoozed').get_json()['rows'] == []
    assert _audits('decision.dismiss', key) == 0
    # «بعدين» مسموح لنفس النوع
    assert _call(ctx, 'POST', '/api/v2/decisions/%s/snooze' % key, {'until': _future()}).status_code == 200


@pytest.mark.parametrize('key', ['signup:u9', 'payfail:pf-1', 'site_message:44', 'message:m1', 'lead:l1', 'stuck_payment:sp1'])
def test_dismiss_needs_a_reason_and_works_for_types_without_a_platform_decision(ctx, key):
    _clear()
    url = '/api/v2/decisions/%s/dismiss' % key
    assert _call(ctx, 'POST', url, {}).status_code == 400
    assert _call(ctx, 'POST', url, {'reason': '  '}).status_code == 400
    assert _call(ctx, 'POST', url, {'reason': 'ab'}).status_code == 400
    assert _call(ctx, 'POST', url, {'reason': 'ه' * 201}).status_code == 400
    r = _call(ctx, 'POST', url, {'reason': 'معروف عندي', 'fingerprint': 'order'})
    assert r.status_code == 200 and r.get_json()['kind'] == 'dismiss' and r.get_json()['until'] is None
    row = _call(ctx, 'GET', '/api/v2/decisions/snoozed').get_json()['rows'][0]
    assert row['kind'] == 'dismiss' and row['until'] is None and row['reason'] == 'معروف عندي' and row['fingerprint'] == 'order'
    assert _audits('decision.dismiss', key) == 1


def test_old_expired_snoozes_are_purged_on_read_but_recent_ones_stay(ctx):
    from sqlalchemy import text
    _clear()
    old = (datetime.datetime.utcnow() - datetime.timedelta(days=90)).replace(microsecond=0).isoformat() + 'Z'
    recent = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).replace(microsecond=0).isoformat() + 'Z'
    for k, u in (('book:old', old), ('book:recent', recent)):
        db.session.execute(text("INSERT INTO decision_snooze (item_key, until, kind, reason, by, created_at, fingerprint) VALUES (:k, :u, 'snooze', '', 'x', :c, '')"),
                           {'k': k, 'u': u, 'c': old})
    db.session.commit()
    keys = [r['key'] for r in _call(ctx, 'GET', '/api/v2/decisions/snoozed').get_json()['rows']]
    assert keys == ['book:recent']                       # القديم اتمسح، واللي لسه قريب فضل (الواجهة بتعامله زي المنتهي)


def test_ack_audit_is_written_only_after_the_platform_accepts(ctx, monkeypatch):
    """R24: `_audit` في `tg_ops.py` بعد `_resp_ok` بس — كان بيتكتب حتى لو المنصة رفضت."""
    import app as appmod
    for path, action, target in (('/api/platform-signups/u-ack-1/ack', 'signup.ack', 'u-ack-1'),
                                 ('/api/platform-payment-failures/pf-ack-1/ack', 'payment_failure.ack', 'pf-ack-1')):
        before = _audits(action, target)
        monkeypatch.setattr(appmod, '_platform_proxy', lambda *a, **k: (appmod.jsonify({'error': 'no'}), 409))
        assert _call(ctx, 'POST', path, {}).status_code == 409
        assert _audits(action, target) == before                      # رفض ⇒ ولا سطر
        monkeypatch.setattr(appmod, '_platform_proxy', lambda *a, **k: appmod.jsonify({'ok': True}))
        assert _call(ctx, 'POST', path, {}).status_code == 200
        assert _audits(action, target) == before + 1                  # قبول ⇒ سطر واحد


# ——————————————————————————————————————————————————————— ٢. المنطق (v2-logic.js)

NOW = 1763020800000      # 2025-11-13 08:00 UTC — ثابت (مفيش ساعة خفية)
HOUR = 3600e3


def _payout(pid='p1'):
    return {'kind': 'payout', 'pid': pid, 'who': 'سارة', 'email': 's@x.test', 'amount': 500, 'currency': 'EGP', 'dest': 'فودافون', 'status': 'pending',
            'raw': {'amount': 500, 'created_at': '2026-11-12T08:00:00Z'}}


ROWS = {
    'manual_payment': {'apiKind': 'manual_payment', 'apiId': 'm1', 'who': 'منى', 'amount': 300, 'currency': 'EGP', 'payMethod': 'InstaPay', 'ref': 'PAY-1'},
    'trainer': {'apiKind': 'trainer', 'apiId': 't1', 'who': 'تامر', 'personEmail': 't@x.test', 'ref': 'TRN-1', 'trHeadline': 'محامي'},
    'join': {'apiKind': 'join', 'apiId': 'j1', 'who': 'جلال', 'serviceLabel': 'استشارة', 'ref': 'JR-1', 'licensed': False},
    'join_waiting': {'apiKind': 'join', 'apiId': 'j2', 'who': 'جمال', 'serviceLabel': 'استشارة', 'ref': 'JR-2', 'waiting': True},
    'join_licensed': {'apiKind': 'join', 'apiId': 'j3', 'who': 'جيهان', 'serviceLabel': 'مرافعة', 'ref': 'JR-3', 'licensed': True},
    'pending_user': {'apiKind': 'pending_user', 'apiId': 'pu1', 'who': 'بسمة', 'ref': 'PU-1', 'flagLabels': []},
    'pending_user_flagged': {'apiKind': 'pending_user', 'apiId': 'pu2', 'who': 'بدر', 'ref': 'PU-2', 'flagLabels': ['حساب مكرر']},
    'founding_new': {'apiKind': 'founding', 'apiId': 'f1', 'who': 'فادي', 'ref': 'FND-1', 'nextStatus': 'contacted', 'statusLabel': 'جديد'},
    'founding_contacted': {'apiKind': 'founding', 'apiId': 'f2', 'who': 'فاتن', 'ref': 'FND-2', 'nextStatus': 'invited', 'statusLabel': 'تم التواصل'},
    'founding_invited': {'apiKind': 'founding', 'apiId': 'f3', 'who': 'فريد', 'ref': 'FND-3', 'nextStatus': 'converted', 'statusLabel': 'تمت دعوته'},
    'signup': {'apiKind': 'signup', 'apiId': 's1', 'who': 'سلمى', 'email': 'sal@x.test', 'ref': 'SGN-s1'},
    'payfail': {'apiKind': 'payfail', 'apiId': 'pf1', 'who': 'بشير', 'ref': 'PF-1', 'pfScope': 'order', 'pfWhy': 'رُفضت', 'pfGateway': 'stripe'},
    'gateway': {'apiKind': 'payfail', 'apiId': 'gw_stripe_down', 'who': 'بوابة stripe', 'ref': 'PF-gw', 'pfScope': 'gateway', 'pfAttempts': 4, 'pfGateway': 'stripe'},
    'dispute': {'apiKind': 'dispute', 'dsrc': 'file', 'apiId': 'd1', 'who': 'دينا', 'ref': 'EF-d1', 'ef': {'title': 'ملف'}},
    'review': {'apiKind': 'expert_file', 'efLane': 'review', 'apiId': 'r1', 'who': 'رنا', 'ref': 'EF-r1', 'ef': {'title': 'رأي', 'expert_name': 'خبير'}},
    'identity_doc': {'apiKind': 'identity_doc', 'apiId': 'i1', 'who': 'إيمان', 'ref': 'IDD-1', 'idTitle': 'محام'},
    'book': {'apiKind': 'book', 'apiId': 'b1', 'who': 'ناشر', 'ref': 'KNW-1', 'note': 'كتاب'},
    'site_message': {'apiKind': 'site_message', 'apiId': 44, 'msgSource': 'site', 'msgId': 44, 'who': 'زائر', 'ref': 'MSG-44', 'note': 'رسالة'},
    'site_message2': {'apiKind': 'site_message', 'apiId': 45, 'msgSource': 'site', 'msgId': 45, 'who': 'زائر آخر', 'ref': 'MSG-45', 'note': 'رسالة تانية'},
    'lead': {'apiKind': 'lead', 'apiId': 'l1', 'who': 'ليلى', 'ref': 'LEAD-l1', 'resolve': True, 'note': 'محتملة'},
    'file_cand': {'apiKind': 'expert_file', 'apiId': 'ef9', 'efLane': 'waiting', 'who': 'عميل', 'ref': 'EF-ef9',
                  'ef': {'id': 'ef9', 'title': 'ملف عقد', 'status': 'awaiting_assignment', 'hours_left': 20,
                         'candidates': [{'email': 'e@x.test', 'name': 'خبير أول', 'auto_pick': True}]}},
    'file_nocand': {'apiKind': 'expert_file', 'apiId': 'ef8', 'efLane': 'waiting', 'who': 'عميل', 'ref': 'EF-ef8',
                    'ef': {'id': 'ef8', 'title': 'ملف بلا خبير', 'status': 'awaiting_assignment', 'hours_left': 20, 'candidates': []}},
    'file_sent': {'apiKind': 'expert_file', 'apiId': 'ef7', 'efLane': 'assigned', 'fyi': True, 'who': 'عميل', 'ref': 'EF-ef7',
                  'ef': {'id': 'ef7', 'title': 'ملف اتبعت', 'status': 'assigned', 'hours_left': 40}},
}

DECISION_KINDS = ['manual_payment', 'trainer', 'join', 'pending_user', 'founding_new', 'lead', 'file_cand']
FYI_ONLY = ['join_waiting', 'founding_contacted', 'founding_invited', 'signup', 'payfail', 'gateway']
OPEN_ONLY = ['join_licensed', 'pending_user_flagged', 'dispute', 'review', 'identity_doc', 'book', 'site_message', 'file_nocand']


def _split(rows, payouts=None, queue=None, **opts):
    o = {'now': NOW}
    fyi_rows = [r for r in rows if r.get('fyi')]
    o['fyiRows'] = fyi_rows
    o.update(opts)
    return v2_node.logic('v2Split', [r for r in rows if not r.get('fyi')], payouts or [], queue, o)


def _kinds(cards):
    return sorted(c['kind'] for c in cards)


@needs_node
def test_deck_holds_only_decisions_with_a_closing_primary_action():
    rows = [ROWS[k] for k in DECISION_KINDS + FYI_ONLY + OPEN_ONLY] + [ROWS['file_sent']]
    out = _split(rows, [_payout()], {'courses_pending': {'count': 2, 'titles': ['دورة أ', 'دورة ب']}, 'live_needs_decision': [{'title': 'حيّة', 'reserved_count': 2, 'quorum': 5}]})
    deck = out['decisions']
    # R24 م٢ (اتغيّر): اللي كان «افتح» بس (نزاع · رأي · هوية · كتاب · رسالة موقع · انضمام مرخَّص · زائر عليه علامة · ملف بلا مرشّح) رجع قرارًا في بيته
    # بفعله الحقيقي (`read` = اقرأ وقرّر جوه القسم)، و«للعلم» فيها الحقيقي بس.
    assert _kinds(deck) == sorted(['payout', 'manual_payment', 'trainer', 'join', 'join', 'pending_user', 'pending_user', 'founding', 'lead', 'file_waiting', 'file_waiting',
                                   'dispute', 'review', 'identity_doc', 'book', 'open_message'])
    for c in deck:                                    # كل بطاقة في الشريط فعلها الأساسي بيقفلها أو بيفتح قراية فيها القفل (مش «افتح» عادي)
        assert c['bucket'] == 'decision'
        assert c['primary']['act']['do'] in ('send', 'decide', 'resolve', 'payout_settle', 'pay_confirm', 'offer_approve', 'brain_approve', 'read'), c['kind']
    # الباقي كله «للعلم» (مفيش بطاقة بتضيع)
    fyi_cards = [c for g in out['fyi']['groups'] for c in g['cards']]
    kinds = {c['kind'] for c in fyi_cards}
    assert {'signup', 'payfail', 'course', 'live'} <= kinds and not ({'dispute', 'review', 'identity_doc', 'book', 'open_message'} & kinds)
    assert out['fyi']['total'] == len(fyi_cards) == out['fyi']['info'] + out['fyi']['open']
    # لا قرارات مكررة بين الشريطين
    assert not ({c['id'] for c in deck} & {c['id'] for c in fyi_cards})


@needs_node
def test_course_and_live_counters_and_stuck_payments_are_fyi_never_decisions():
    stuck = [{'id': 'sp1', 'name': 'دافع', 'email': 'd@x.test', 'kindText': 'دورة', 'amountText': '٥٠٠ جنيه', 'provider': 'stripe', 'ageHours': 30, 'refundable': True}]
    out = _split([], None, {'courses_pending': {'count': 1, 'titles': ['دورة أ']}, 'live_needs_decision': [{'title': 'حيّة'}]}, stuck=stuck)
    assert out['decisions'] == []
    groups = {g['key']: g for g in out['fyi']['groups']}
    assert groups['stuck_payment']['kind'] == 'info' and groups['stuck_payment']['n'] == 1
    assert groups['course']['n'] == 1 and groups['live']['n'] == 1
    assert 'دفعة بالبطاقة لسه ما كملتش' in groups['stuck_payment']['label']


@needs_node
def test_gateway_failure_is_one_health_line_with_attempts_not_a_card():
    gw2 = dict(ROWS['gateway'], apiId='gw_paypal_down', pfAttempts=2, who='بوابة paypal')
    out = _split([ROWS['gateway'], gw2, ROWS['payfail']])
    assert out['decisions'] == []
    g = {x['key']: x for x in out['fyi']['groups']}
    assert 'gateway' in g and g['gateway']['n'] == 2 and 'محاولات' in g['gateway']['label']
    assert g['payfail']['n'] == 1
    assert out['fyi']['groups'][0]['key'] == 'gateway'                # الصحة أول سطر


@needs_node
def test_founding_only_new_is_a_decision_followups_are_info():
    out = _split([ROWS['founding_new'], ROWS['founding_contacted'], ROWS['founding_invited']])
    assert [c['row']['apiId'] for c in out['decisions']] == ['f1']
    fg = [g for g in out['fyi']['groups'] if g['key'] == 'founding_follow'][0]
    assert fg['kind'] == 'info' and fg['n'] == 2


@needs_node
def test_join_needs_info_waits_for_the_applicant_so_it_is_not_a_decision():
    out = _split([ROWS['join'], ROWS['join_waiting']])
    assert [c['row']['apiId'] for c in out['decisions']] == ['j1']
    assert [g['key'] for g in out['fyi']['groups']] == ['join_waiting']


# —— مفاتيح البنود والبصمة

@needs_node
def test_keys_are_type_colon_platform_id_and_stable_for_site_messages_and_files():
    k = lambda r: v2_node.logic('snoozeKeyOfRow', r)
    assert k(ROWS['site_message']) == 'site_message:44' and k(ROWS['site_message2']) == 'site_message:45'   # كان '||' لكل الرسائل
    assert k(ROWS['signup']) == 'signup:s1' and k(ROWS['trainer']) == 'trainer:t1' and k(ROWS['dispute']) == 'dispute:d1'
    assert k(_payout('p9')) == 'payout:p9'
    assert k(ROWS['file_cand']) == 'file:ef9'
    late = json.loads(json.dumps(ROWS['file_cand'])); late['efLane'] = 'late'
    assert k(late) == 'file:ef9'                                      # تغيّر الحارة ما يغيّرش المفتاح
    assert k({'apiKind': 'lead'}) is None and k({'apiKind': 'course_q', 'apiId': 'c0'}) is None   # بلا معرّف ثابت ⇒ مفيش مفتاح


# —— الدالة المشتركة للإخفاء

def _entry(key, until=None, kind='snooze', fp='', reason=''):
    return {'key': key, 'until': until, 'kind': kind, 'reason': reason, 'fingerprint': fp, 'by': 'a', 'created_at': '2026-11-13T00:00:00Z'}


def _iso(ms):
    return datetime.datetime.utcfromtimestamp(ms / 1000.0).replace(microsecond=0).isoformat() + 'Z'


@needs_node
def test_snoozed_item_leaves_the_deck_and_returns_after_until():
    until = _iso(NOW + 3 * 24 * HOUR)
    snz = {'map': {'trainer:t1': _entry('trainer:t1', until)}, 'now': NOW}
    out = _split([ROWS['trainer'], ROWS['join']], snooze=snz)
    assert [c['row']['apiId'] for c in out['decisions']] == ['j1']
    assert [x['key'] for x in out['snoozed']] == ['trainer:t1']
    # بعد الميعاد يرجع لوحده ومعاه «رجع لأن…»
    later = _split([ROWS['trainer']], snooze={'map': snz['map'], 'now': NOW + 4 * 24 * HOUR}, now=NOW + 4 * 24 * HOUR)
    assert [c['row']['apiId'] for c in later['decisions']] == ['t1']
    assert later['decisions'][0]['returned'] == 'رجع لأن مدة التأجيل خلصت' and later['snoozed'] == []


@needs_node
def test_status_change_on_the_platform_brings_the_item_back_with_a_reason():
    fp_now = v2_node.logic('snoozeFingerprint', ROWS['founding_new'])
    until = _iso(NOW + 5 * 24 * HOUR)
    snz = {'map': {'founding:f1': _entry('founding:f1', until, fp=fp_now)}, 'now': NOW}
    assert _split([ROWS['founding_new']], snooze=snz)['decisions'] == []                       # نفس الحالة ⇒ مخفي
    moved = dict(ROWS['founding_new'], nextStatus='invited', statusLabel='تم التواصل')          # حالة جديدة على المنصة
    out = _split([moved], snooze=snz)
    assert out['decisions'] == [] and [g['key'] for g in out['fyi']['groups']] == ['founding_follow']
    assert out['fyi']['groups'][0]['cards'][0]['returned'] == 'رجع لأن حالته اتغيّرت'
    # والملف اللي اتأخّر (الحارة اتغيّرت) يرجع للشريط ومعاه السبب
    fp_file = v2_node.logic('snoozeFingerprint', ROWS['file_cand'])
    late = json.loads(json.dumps(ROWS['file_cand'])); late['efLane'] = 'late'
    out2 = _split([late], snooze={'map': {'file:ef9': _entry('file:ef9', until, fp=fp_file)}, 'now': NOW})
    assert [c['kind'] for c in out2['decisions']] == ['file_late'] and out2['decisions'][0]['returned'] == 'رجع لأن حالته اتغيّرت'


@needs_node
def test_dismissed_stays_hidden_until_the_state_changes_and_gateway_attempts_do_not_bring_it_back():
    fp = v2_node.logic('snoozeFingerprint', ROWS['gateway'])
    snz = {'map': {'payfail:gw_stripe_down': _entry('payfail:gw_stripe_down', None, 'dismiss', fp, 'البوابة اتصلّحت')}, 'now': NOW}
    assert _split([ROWS['gateway']], snooze=snz)['fyi']['total'] == 0
    more = dict(ROWS['gateway'], pfAttempts=9)                         # محاولات أكتر ⇒ لسه مخفي (الشكوى: بتتفتح مع كل فشل)
    assert _split([more], snooze=snz)['fyi']['total'] == 0
    out = _split([ROWS['gateway']], snooze=snz)
    assert out['snoozed'][0]['entry']['kind'] == 'dismiss'
    lists = v2_node.logic('v2SnoozeLists', out['snoozed'])
    assert len(lists['gone']) == 1 and lists['gone'][0]['reason'] == 'البوابة اتصلّحت' and lists['later'] == []


@needs_node
def test_every_source_goes_through_the_same_function_payouts_stuck_offers_brain():
    until = _iso(NOW + 24 * HOUR)
    mp = {k: _entry(k, until) for k in ('payout:p1', 'stuck_payment:sp1', 'book_offer:o1', 'brain_item:bi1')}
    stuck = [{'id': 'sp1', 'name': 'دافع', 'ageHours': 30}, {'id': 'sp2', 'name': 'دافع٢', 'ageHours': 30}]
    offers = [{'id': 'o1', 'title': 'عرض ١', 'ownerName': 'ناشر'}, {'id': 'o2', 'title': 'عرض ٢', 'ownerName': 'ناشر'}]
    brain = [{'id': 'bi1', 'status': 'proposed', 'title': 'اقتراح'}, {'id': 'bi2', 'status': 'proposed', 'title': 'اقتراح٢'}]
    out = _split([], [_payout('p1'), _payout('p2')], None, stuck=stuck, offers=offers, snooze={'map': mp, 'now': NOW})
    assert [c['row']['pid'] for c in out['decisions'] if c['kind'] == 'payout'] == ['p2']
    assert [c['row']['offerRow']['id'] for c in out['decisions'] if c['kind'] == 'book_offer'] == ['o2']
    assert [c['row']['stuck']['id'] for g in out['fyi']['groups'] for c in g['cards'] if c['kind'] == 'stuck_payment'] == ['sp2']
    assert sorted(x['key'] for x in out['snoozed']) == ['book_offer:o1', 'payout:p1', 'stuck_payment:sp1']
    assert sorted(v2_node.logic('util.kindOf', r) for r in out['hiddenRows']) == ['book_offer', 'payout', 'stuck_payment']


@needs_node
def test_picks_dates_and_texts():
    picks = v2_node.logic('snoozePicks', NOW)
    assert [p['label'] for p in picks] == ['بكرة', 'بعد ٣ أيام', 'الأسبوع الجاي']
    prev = NOW
    for p in picks:                                                   # كلها في المستقبل وبترتيب
        t = datetime.datetime.strptime(p['until'], '%Y-%m-%dT%H:%M:%S.%fZ')
        ms = (t - datetime.datetime(1970, 1, 1)).total_seconds() * 1000
        assert ms > prev
        prev = ms
    future = (datetime.datetime.utcfromtimestamp(NOW / 1000.0) + datetime.timedelta(days=9)).strftime('%Y-%m-%d')
    assert v2_node.logic('snoozeUntilFromDate', future, NOW)
    assert v2_node.logic('snoozeUntilFromDate', '2020-01-01', NOW) is None           # فات
    assert v2_node.logic('snoozeUntilFromDate', '2026-02-30', NOW) is None           # مش تاريخ
    assert v2_node.logic('snoozeUntilFromDate', 'بكرة', NOW) is None
    txt = v2_node.logic('snoozeUntilText', _iso(NOW + 24 * HOUR))
    assert re.search(r'[٠-٩]', txt) and '·' not in txt


# —— العدّاد واحد: المربّع = الشريط

@needs_node
def test_one_counter_tiles_and_deck_agree_after_snooze():
    until = _iso(NOW + 2 * 24 * HOUR)
    rows = [ROWS['pending_user'], dict(ROWS['pending_user'], apiId='pu3', ref='PU-3', who='بدور'), ROWS['join'], ROWS['signup']]
    snz = {'map': {'pending_user:pu1': _entry('pending_user:pu1', until)}, 'now': NOW}
    queue = {'founding_leads_new': 0}
    out = _split(rows, None, queue, snooze=snz)
    visible = [r for r in rows if r['apiId'] != 'pu1']                     # اللي المحمّل بيسيبه في INBOX
    tiles = v2_node.logic('v2Tiles', queue, {'inbox': visible, 'pendingVisitors': 2, 'invitesAwaiting': 0, 'hidden': out['hiddenRows'], 'now': NOW})
    people = [t for t in tiles if t['key'] == 'people'][0]
    deck_people = [c for c in out['decisions'] if c['kind'] in ('pending_user', 'join')]
    # المربّع: زائر (٢ - ١ مخفي) + طلب انضمام + تسجيل = ٣ · الشريط: الزائر والطلب بس (التسجيل «للعلم»)
    assert people['count'] == 3 and len(deck_people) == 2
    unhidden = v2_node.logic('v2Tiles', queue, {'inbox': rows, 'pendingVisitors': 2, 'invitesAwaiting': 0, 'hidden': [], 'now': NOW})
    assert [t for t in unhidden if t['key'] == 'people'][0]['count'] == people['count'] + 1


@needs_node
def test_hidden_rows_come_off_every_queue_derived_count():
    q = {'wallet_payouts_pending': {'count': 3}, 'manual_payments_pending': {'count': 2}, 'stuck_card_payments': {'count': 2, 'orders': []},
         'expert_files_awaiting_assignment': {'count': 4}, 'expert_files_disputed': {'count': 2}, 'trainer_applications_pending': {'count': 2},
         'topics_pending_review': {'count': 2}, 'creative_pending': {'count': 1}}
    hidden = [_payout('p1'), {'apiKind': 'manual_payment', 'apiId': 'm1'}, {'apiKind': 'stuck_payment', 'apiId': 'sp1'}, ROWS['file_cand'], ROWS['dispute'],
              ROWS['trainer'], {'apiKind': 'topic', 'apiId': 'tp1'}, {'apiKind': 'creative', 'apiId': 'cr1'}]
    base = {t['key']: t for t in v2_node.logic('v2Tiles', q, {'inbox': [], 'hidden': [], 'now': NOW})}
    cut = {t['key']: t for t in v2_node.logic('v2Tiles', q, {'inbox': [], 'hidden': hidden, 'now': NOW})}
    for key, d in (('money', 3), ('files', 1), ('disputes', 1), ('courses', 1), ('content', 2)):
        assert base[key]['count'] - cut[key]['count'] == d, key
    # مفيش عدّاد سالب لو الطابور أقل من المخفي
    tiny = {t['key']: t for t in v2_node.logic('v2Tiles', {'wallet_payouts_pending': {'count': 0}}, {'inbox': [], 'hidden': [_payout('p1')], 'now': NOW})}
    assert tiny['money']['count'] == 0


@needs_node
def test_visible_copy_has_no_middot_next_to_arabic_digits_and_no_technical_words():
    defs = v2_node.logic('FYI_DEFS')
    texts = [f for d in defs.values() for f in d[1]]
    assert len(defs) >= 25 and all(isinstance(t, str) and t for t in texts)
    for t in texts:
        assert '·' not in t, t
        assert not re.search(r'[A-Za-z]{3,}', t), t
    assert {d[0] for d in defs.values()} == {'info', 'open'}


# ——————————————————————————————————————————————————————— ٣. المحمّلات (dashboard-api.js جوه node:vm)

def _ep(responses, code, role='admin'):
    script = os.path.join(_HERE, 'uiharness', 'r24_ep.js')
    p = subprocess.run([v2_node.NODE, script], input=json.dumps({'responses': responses, 'code': code, 'role': role}, ensure_ascii=False),
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:] + p.stdout[-800:]
    return json.loads(p.stdout)


def _ok(body, status=200):
    return {'status': status, 'body': body}


SIGNUPS = {'signups': [{'user_id': 'u1', 'email': 'a@x.test', 'full_name': 'أحمد', 'provider': 'google'},
                       {'user_id': 'u2', 'email': 'b@x.test', 'full_name': 'بهاء', 'provider': 'google'}]}
LOAD_INBOX = "EP.reload('inbox', null); return settled('inbox').then(function(){ return %s; });"


@needs_node
def test_inbox_loader_keeps_only_visible_rows_and_puts_the_rest_in_inbox_snoozed():
    rows = [{'key': 'signup:u1', 'until': None, 'kind': 'dismiss', 'reason': 'معروف', 'by': 'a', 'created_at': '2026-11-13T00:00:00Z', 'fingerprint': ''}]
    out = _ep({'/api/v2/decisions/snoozed': _ok({'rows': rows}), '/api/platform-signups': _ok(SIGNUPS)},
              LOAD_INBOX % "{inbox: window.INBOX.map(function(r){return r.ref}), hidden: window.INBOX_SNOOZED.map(function(h){return h.key}), ok: window.INBOX_SNOOZE_OK}")
    assert out['result'] == {'inbox': ['SGN-u2'], 'hidden': ['signup:u1'], 'ok': True}
    asked = [c['url'] for c in out['calls']]
    assert asked.count('/api/v2/decisions/snoozed') == 1               # مرة واحدة مع تحميل الوارد


@needs_node
def test_snooze_load_failure_shows_everything_and_says_so_but_forbidden_or_closed_is_quiet():
    base = {'/api/platform-signups': _ok(SIGNUPS)}
    code = LOAD_INBOX % "{n: window.INBOX.length, hidden: window.INBOX_SNOOZED.length, ok: window.INBOX_SNOOZE_OK}"
    boom = _ep(dict(base, **{'/api/v2/decisions/snoozed': _ok({'error': 'x'}, 500)}), code)
    assert boom['result'] == {'n': 2, 'hidden': 0, 'ok': False}                   # عطل حقيقي ⇒ بنعرض كله ونقول
    quiet = _ep(dict(base, **{'/api/v2/decisions/snoozed': _ok({'error': 'x'}, 404)}), code)
    assert quiet['result'] == {'n': 2, 'hidden': 0, 'ok': True}                   # مفتاح مقفول ⇒ مفيش تحذير
    emp = _ep(dict(base, **{'/api/v2/decisions/snoozed': _ok({'error': 'x'}, 403)}), code, role='employee')
    assert emp['result']['ok'] is True


@needs_node
def test_snoozed_site_messages_are_distinct_and_the_row_key_is_stable():
    msgs = {'messages': [{'id': 44, 'name': 'أ', 'body': 'مرحبا', 'created_at': '2026-11-12T08:00:00Z'},
                         {'id': 45, 'name': 'ب', 'body': 'تاني', 'created_at': '2026-11-12T09:00:00Z'}]}
    until = _iso(NOW + 5 * 24 * HOUR)
    out = _ep({'/api/messages?status=new': _ok(msgs),
               '/api/v2/decisions/snoozed': _ok({'rows': [dict(_entry('site_message:44', until), by='a')]})},
              LOAD_INBOX % "{keys: window.INBOX.map(function(r){return V2L.snoozeKeyOfRow(r)}), kinds: window.INBOX.map(function(r){return r.apiKind}), id: window.INBOX.map(function(r){return r.apiId})}")
    # الوقت الحقيقي: التأجيل في ٢٠٢٥ فات ⇒ الاتنين ظاهرين، بمفتاحين مختلفين (مش '||')
    assert out['result']['keys'] == ['site_message:44', 'site_message:45']
    assert out['result']['kinds'] == ['site_message', 'site_message'] and out['result']['id'] == [44, 45]


@needs_node
def test_wallet_payouts_loader_hides_snoozed_payouts():
    future = (datetime.datetime.utcnow() + datetime.timedelta(days=3)).replace(microsecond=0).isoformat() + 'Z'
    payouts = {'payouts': [{'id': 'p1', 'amount': 500, 'user_name': 'أ', 'user_email': 'a@x.test', 'status': 'pending'},
                           {'id': 'p2', 'amount': 700, 'user_name': 'ب', 'user_email': 'b@x.test', 'status': 'pending'}]}
    out = _ep({'/api/platform-wallet-payouts': _ok(payouts), '/api/v2/decisions/snoozed': _ok({'rows': [_entry('payout:p1', future)]})},
              "EP.reload('walletPayouts', null); return settled('walletPayouts').then(function(){ var w = EP.data.walletPayouts; return {rows: w.rows.map(function(r){return r.pid}), hidden: w.hidden.map(function(h){return h.key}), count: w.count}; });")
    assert out['result'] == {'rows': ['p2'], 'hidden': ['payout:p1'], 'count': 1}


@needs_node
def test_snooze_dismiss_restore_actions_hit_the_right_routes_and_refresh():
    future = (datetime.datetime.utcnow() + datetime.timedelta(days=3)).replace(microsecond=0).isoformat() + 'Z'
    resp = {'/api/v2/decisions/signup%3As1/snooze': _ok({'ok': True}), '/api/v2/decisions/signup%3As1/dismiss': _ok({'ok': True}),
            '/api/v2/decisions/signup%3As1/restore': _ok({'ok': True}),
            '/api/v2/decisions/payout%3Ap1/dismiss': _ok({'error': 'ده مالوش «تجاهل» — ارفضه بسبب أو أجّله بميعاد', 'refused': True}, 409)}
    code = ("return Promise.all([EP.snoozeItem('signup:s1', %s, 'fp'), EP.dismissItem('signup:s1', 'معروف', 'fp'), EP.restoreItem('signup:s1'), EP.dismissItem('payout:p1', 'x', '')])"
            ".then(function(r){ return r; });" % json.dumps(future))
    out = _ep(resp, code)
    assert [r['ok'] for r in out['result']] == [True, True, True, False]
    assert out['result'][3]['refused'] is True and 'ارفضه' in out['result'][3]['error']
    posts = [(c['url'], c['body']) for c in out['calls'] if c['method'] == 'POST']
    assert posts[0] == ('/api/v2/decisions/signup%3As1/snooze', {'until': future, 'fingerprint': 'fp'})
    assert posts[1] == ('/api/v2/decisions/signup%3As1/dismiss', {'reason': 'معروف', 'fingerprint': 'fp'})
    assert posts[2] == ('/api/v2/decisions/signup%3As1/restore', {})
    # بعد النجاح الوارد والتحويلات بيتحمّلوا من جديد
    assert any(c['url'].startswith('/api/platform-signups') for c in out['calls'])


@needs_node
def test_opening_the_platform_for_a_visitor_also_acks_the_signup_of_the_same_email():
    pu = {'users': [{'id': 'u1', 'email': 'a@x.test', 'full_name': 'أحمد', 'invite_request': {'status': 'requested', 'requested_at': '2026-11-12T08:00:00Z'}}]}
    resp = {'/api/pending-users?limit=200': _ok(pu), '/api/platform-signups': _ok(SIGNUPS),
            '/api/pending-users/u1/access': _ok({'ok': True}), '/api/platform-signups/u1/ack': _ok({'ok': True})}
    code = ("EP.reload('inbox', null); return settled('inbox').then(function(){"
            " var row = window.INBOX.filter(function(r){return r.apiKind==='pending_user'})[0];"
            " return EP.decideInboxItem(row, 'approve', null, '').then(function(r){ return r; }); });")
    out = _ep(resp, code)
    assert out['result']['ok'] is True
    posts = [c['url'] for c in out['calls'] if c['method'] == 'POST']
    assert posts[:2] == ['/api/pending-users/u1/access', '/api/platform-signups/u1/ack']
    # رفض الزائر ما يعملش ack للتسجيل
    out2 = _ep(resp, code.replace("'approve'", "'reject'").replace("''", "'سبب'"))
    assert [c['url'] for c in out2['calls'] if c['method'] == 'POST'] == ['/api/pending-users/u1/access']
    # ولو ما فيش صف تسجيل بنفس البريد: فتح المنصة بس، ولا نداء ack
    resp3 = dict(resp, **{'/api/platform-signups': _ok({'signups': [SIGNUPS['signups'][1]]})})
    out3 = _ep(resp3, code)
    assert [c['url'] for c in out3['calls'] if c['method'] == 'POST'] == ['/api/pending-users/u1/access']


@needs_node
def test_ack_failure_does_not_undo_the_open():
    pu = {'users': [{'id': 'u1', 'email': 'a@x.test', 'full_name': 'أحمد', 'invite_request': {'status': 'requested', 'requested_at': '2026-11-12T08:00:00Z'}}]}
    resp = {'/api/pending-users?limit=200': _ok(pu), '/api/platform-signups': _ok(SIGNUPS), '/api/pending-users/u1/access': _ok({'ok': True}),
            '/api/platform-signups/u1/ack': _ok({'error': 'x'}, 500)}
    out = _ep(resp, "EP.reload('inbox', null); return settled('inbox').then(function(){ var row = window.INBOX.filter(function(r){return r.apiKind==='pending_user'})[0];"
                    " return EP.decideInboxItem(row, 'approve', null, ''); });")
    assert out['result']['ok'] is True


@needs_node
def test_row_shapes_for_the_dead_button_fixes():
    trainers = {'applications': [{'id': 7, 'user_name': 'تامر', 'user_email': 't@x.test', 'headline': 'محامي', 'join_as': 'expert'}]}
    pf = {'failures': [{'id': 'pf1', 'scope': 'order', 'why': 'رُفضت', 'user_email': 'b@x.test', 'amount': 5, 'currency': 'USD'}]}
    jr = {'requests': [{'id': 'j1', 'status': 'needs_info', 'user_name': 'جمال', 'user_email': 'j@x.test', 'service_label': 'استشارة', 'info_request': 'ابعت رقم قيدك'},
                       {'id': 'j2', 'status': 'pending', 'user_name': 'جلال', 'user_email': 'k@x.test', 'service_label': 'استشارة'}]}
    out = _ep({'/api/platform-trainer-applications?status=pending': _ok(trainers), '/api/platform-signups': _ok(SIGNUPS), '/api/platform-payment-failures': _ok(pf),
               '/api/platform-join-requests?status=open': _ok(jr), '/api/v2/decisions/snoozed': _ok({'rows': []})},
              LOAD_INBOX % "window.INBOX.map(function(r){return {k:r.apiKind, id:r.apiId, lbl:r.approveLabel, rej:r.canReject, need:r.rejectNeedsReason, w:r.waiting}})")
    by = {}
    for r in out['result']:
        by.setdefault(r['k'], []).append(r)
    assert by['trainer'][0]['rej'] is True and by['trainer'][0]['need'] is True            # ارفض بسبب في الدرج
    assert {r['lbl'] for r in by['signup']} == {'تمام، اطّلعت'} and by['payfail'][0]['lbl'] == 'تمام، اطّلعت'
    assert {r['id']: r['w'] for r in by['join']} == {'j1': True, 'j2': False}


@needs_node
def test_vanished_row_message_and_host_open_row_contract():
    # openRow بيدوّر **قبل** ما يروح للوارد، وبيرجّع false (الكارت بيكتب «البند ده اتحل بالفعل»)
    i = HTML.index('openRow:function(row){')
    body = HTML[i:HTML.index('logout:function', i)]
    # R24 م٢ (اتغيّر): «افتح» بقت درج القراية فوق القسم؛ والبحث عن الصف (v2FindRow) قبل أي فتح، والفشل ⇒ false + «البند ده اتحل بالفعل»
    assert 'v2OpenReading(row,null)' in body
    reading = HTML[HTML.index('function v2OpenReading('):HTML.index('function v2CloseReading(')]
    assert reading.index('v2FindRow(row)') < reading.index('drawInbox()') and 'return false' in reading and 'return true' in reading and "go('inbox')" not in reading
    assert "function v2FindRow(row)" in HTML and 'row.apiKind==null||row.apiId==null)return -1' in HTML
    assert 'البند ده اتحل بالفعل' in HOME_JS and 'opened === false' in HOME_JS
    assert "toast('البند ده اتحل بالفعل')" in HTML                                      # openRowAt كمان


# ——————————————————————————————————————————————————————— ٣ب. اللوحة (v2-home.js جوه node:vm بمستند مزيّف)

def _home(inbox, steps=None, **kw):
    script = os.path.join(_HERE, 'uiharness', 'r24_home.js')
    payload = dict({'inbox': inbox, 'queue': {}, 'steps': steps or []}, **kw)
    p = subprocess.run([v2_node.NODE, script], input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


HROWS = [dict(ROWS['trainer'], ts=1), dict(ROWS['lead'], ts=2), dict(ROWS['signup'], ts=3), dict(ROWS['dispute'], ts=4)]


def _far():
    return (datetime.datetime.utcnow() + datetime.timedelta(days=5)).replace(microsecond=0).isoformat() + 'Z'


@needs_node
def test_home_board_shows_the_for_info_box_and_the_two_restore_lines_not_cards_with_buttons():
    snoozed = [{'row': dict(ROWS['join'], ts=5), 'key': 'join:j1', 'entry': dict(_entry('join:j1', _far()), kind='snooze')},
               {'row': dict(ROWS['signup'], apiId='s2', ref='SGN-s2', ts=6), 'key': 'signup:s2', 'entry': _entry('signup:s2', None, 'dismiss', '', 'معروف')}]
    out = _home(HROWS, snoozed=snoozed)
    html = out['html']
    assert 'ابدأ القرارات (٣)' in html                                     # R24 م٢: trainer + lead + نزاع (النزاع بقى قرارًا في بيته)
    assert 'للعلم (١)' in html and 'تسجيل جديد' in html
    assert 'مؤجّلة (١)' in html and 'اتشالت (١)' in html
    assert 'data-a="primary"' not in html and 'data-a="later"' not in html          # اللوحة مفيهاش أزرار قرار


@needs_node
def test_home_restore_line_opens_the_list_and_restore_calls_the_server():
    snoozed = [{'row': dict(ROWS['join'], ts=5), 'key': 'join:j1', 'entry': dict(_entry('join:j1', _far()), kind='snooze')}]
    out = _home(HROWS, steps=[{'click': '[data-a="lines"]', 'idx': 0}], snoozed=snoozed)
    assert 'رجّعها' in out['html'] and 'جلال' in out['html'] and 'لحد ' in out['html']
    out2 = _home(HROWS, steps=[{'click': '[data-a="lines"]', 'idx': 0}, {'click': '[data-a="restore"]', 'idx': 0}], snoozed=snoozed)
    assert {'fn': 'restoreItem', 'key': 'join:j1'} in out2['calls']


@needs_node
def test_home_dismissed_list_shows_the_reason_and_restore():
    snoozed = [{'row': dict(ROWS['signup'], apiId='s2', ref='SGN-s2', ts=6), 'key': 'signup:s2', 'entry': _entry('signup:s2', None, 'dismiss', '', 'معروف عندي')}]
    out = _home(HROWS, steps=[{'click': '[data-a="lines"]', 'idx': 0}], snoozed=snoozed)
    assert 'السبب: معروف عندي' in out['html'] and 'رجّعها' in out['html']


@needs_node
def test_focus_later_opens_the_picker_and_saves_on_the_server_the_card_leaves_the_deck():
    out = _home(HROWS, steps=[{'mode': 'focus'}])
    assert out['mode'] == 'focus' and len(out['deck']) == 3      # R24 م٢: trainer + lead + نزاع
    assert 'data-a="later"' in out['html'] and '>بعدين</button>' in out['html']
    first_deck = out['deck']
    out = _home(HROWS, steps=[{'mode': 'focus'}, {'click': '[data-a="later"]'}])
    assert out['modal']['title'] == 'بعدين لحد إمتى؟'
    for label in ('بكرة', 'بعد ٣ أيام', 'الأسبوع الجاي', 'اختار يوم'):
        assert label in out['modal']['html']
    out = _home(HROWS, steps=[{'mode': 'focus'}, {'click': '[data-a="later"]'}, {'modalClick': '.v2z-pick', 'idx': 1}])
    snooze = [c for c in out['calls'] if c['fn'] == 'snoozeItem']
    assert len(snooze) == 1 and snooze[0]['key'] == 'trainer:t1' and snooze[0]['until'].endswith('Z')
    assert out['deck'] == first_deck[1:]                              # ما لفّتش لآخر الكوتشينة: خرجت
    # الميعاد اللي اتحفظ هو «بعد ٣ أيام» (الاختيار رقم ١) في المستقبل
    t = datetime.datetime.strptime(snooze[0]['until'], '%Y-%m-%dT%H:%M:%S.%fZ')
    delta = (t - datetime.datetime.utcnow()).total_seconds() / 86400
    assert 1.9 < delta < 3.2


@needs_node
def test_focus_snooze_of_the_last_card_ends_with_the_postponed_line_and_show_postponed_button():
    one = [dict(ROWS['trainer'], ts=1)]
    out = _home(one, steps=[{'mode': 'focus'}, {'click': '[data-a="later"]'}, {'modalClick': '.v2z-pick', 'idx': 0}])
    assert out['deck'] == []
    assert 'أجّلت قرارًا واحدًا' in out['html'] and 'اعرض المؤجّلة' in out['html']


@needs_node
def test_dismiss_button_only_on_cards_whose_type_has_no_platform_decision_and_needs_a_reason():
    out = _home(HROWS, steps=[{'mode': 'focus'}])
    assert 'data-a="dismiss"' not in out['html']                      # أول بطاقة مدرّب: ليها «ارفض بسبب» مش «تجاهل»
    lead_first = [dict(ROWS['lead'], ts=1)]
    out = _home(lead_first, steps=[{'mode': 'focus'}])
    assert 'data-a="dismiss"' in out['html']
    out = _home(lead_first, steps=[{'mode': 'focus'}, {'click': '[data-a="dismiss"]'}, {'modalType': {'sel': '#v2z_r', 'value': 'ab'}}, {'modalClick': '#v2z_go'}])
    assert [c for c in out['calls'] if c['fn'] == 'dismissItem'] == []        # السبب أقصر من ٣ حروف ⇒ مفيش نداء
    out = _home(lead_first, steps=[{'mode': 'focus'}, {'click': '[data-a="dismiss"]'}, {'modalType': {'sel': '#v2z_r', 'value': 'معروف عندي'}}, {'modalClick': '#v2z_go'}])
    d = [c for c in out['calls'] if c['fn'] == 'dismissItem']
    assert len(d) == 1 and d[0]['key'] == 'lead:l1' and d[0]['reason'] == 'معروف عندي'


@needs_node
def test_open_on_a_vanished_row_says_so_instead_of_landing_silently():
    # R24 م٢ (اتغيّر): النزاع قراره «افتح النزاع وقرّر» (قراية جوه القسم) — لو الصف اتحل بنقول كده وبنشيل البطاقة، مش بنرمي المؤسس على شاشة فاضية
    out = _home([dict(ROWS['dispute'], ts=4)], steps=[{'mode': 'focus'}, {'click': '[data-a="primary"]'}], openRowResult=False)
    assert {'fn': 'toast', 't': 'البند ده اتحل بالفعل'} in out['calls']
    assert len(out['deck']) == 0                                      # البطاقة اتشالت من الكوتشينة


@needs_node
def test_returned_line_is_shown_on_the_card():
    row = dict(ROWS['trainer'], ts=1, returnedWhy='رجع لأن حالته اتغيّرت')
    out = _home([row], steps=[{'mode': 'focus'}])
    assert 'رجع لأن حالته اتغيّرت' in out['html'] and 'v2-returned' in out['html']


@needs_node
def test_for_info_group_expands_with_open_snooze_dismiss_and_ack_buttons():
    out = _home(HROWS, steps=[{'click': '[data-a="fg"]', 'idx': 0}])
    html = out['html']
    assert 'data-a="fopen"' in html and 'data-a="fsnooze"' in html and 'data-a="fdismiss"' in html and 'data-a="fack"' in html and 'تمام، اطّلعت' in html
    out = _home(HROWS, steps=[{'click': '[data-a="fg"]', 'idx': 0}, {'click': '[data-a="fack"]'}])
    assert any(c['fn'] == 'decideInboxItem' and c['ref'] == 'SGN-s1' and c['action'] == 'approve' for c in out['calls'])


# ——————————————————————————————————————————————————————— ٤. ثابت

def test_home_later_is_the_server_picker_not_the_in_memory_rotation():
    assert 'S.deck.push(S.deck.shift())' not in HOME_JS
    assert 'snoozePicks' in HOME_JS and 'snoozeUntilFromDate' in HOME_JS and 'E.snoozeItem(c.key, until, c.fp)' in HOME_JS
    assert 'data-a="later"' in HOME_JS and '>بعدين</button>' in HOME_JS and '>لاحقًا</button>' not in HOME_JS
    assert 'اختار يوم' in HOME_JS and 'بكرة' in LOGIC_JS and 'بعد ٣ أيام' in LOGIC_JS and 'الأسبوع الجاي' in LOGIC_JS
    assert 'مؤجّلة' in HOME_JS and 'اتشالت' in HOME_JS and 'رجّعها' in HOME_JS and 'للعلم' in HOME_JS
    # الكوتشينة بتتبني من `compute().decisions` (اللي فيها الفلتر)، فالمؤجَّل مش بيرجع على «ابدأ القرارات»
    assert 'S.deck = d.decisions.slice()' in HOME_JS


def test_still_pending_always_true_hack_is_gone():
    assert "c.kind === 'course' || c.kind === 'live' || c.kind === 'stuck_payment'" not in HOME_JS
    assert re.search(r"function stillPending\(c\)", HOME_JS)


def test_the_two_counters_read_the_same_split():
    # compute() و V2.tiles() (اللي بتغذّي القايمة الجانبية) بيعدّوا من `gather()` اللي فيه `v2Split` + `extras.hidden`
    g = HOME_JS[HOME_JS.index('function gather()'):HOME_JS.index('function compute()')]
    assert 'L.v2Split(' in g and 'extras.hidden = split.hiddenRows' in g
    # R24 م٢ (اتغيّر): العدد = عدد القرارات (`v2SectionTiles` على نفس `split.byHome`) — حسابات الأساس v2Tiles بقت للفشل والعدّ الناقص بس
    assert 'var tiles = L.v2SectionTiles(L.v2Tiles(Q, g.extras), g.split, g.avail)' in HOME_JS and 'var decisions = g.split.decisions' in HOME_JS
    assert re.search(r'V2\.tiles = function \(\) \{ var g = gather\(\); return L\.v2SectionTiles\(L\.v2Tiles\(g\.Q, g\.extras\), g\.split, g\.avail\); \}', HOME_JS)
    # قوايم القسم (الفلوس والكتب) من نفس الدالة المشتركة
    assert 'L.v2SnoozeSplit(list, keyFn, sz.map, now())' in D3_JS and 'stuckVisible(' in D3_JS


def test_people_messages_resolve_action_is_wired():
    i = PEOPLE_JS.index('function doAct(t, act)')
    body = PEOPLE_JS[i:PEOPLE_JS.index('function openSheetFor', i)]
    assert "case 'resolve': return resolveMsg(t.id);" in body


def test_marketing_later_moved_off_session_storage_to_the_snooze_table():
    assert 'sessionStorage' not in MARKETING_JS and 'mk_later_' not in MARKETING_JS and 'mk_legacy_later' not in MARKETING_JS
    assert "laterOnServer('mk_tip:' + key" in MARKETING_JS and "laterOnServer('mk_tip:legacy'" in MARKETING_JS


def test_no_fake_success_or_demo_fallbacks_left_in_the_old_screens():
    for bad in ('تم تحرير المبلغ للخبير', "toast('القرار: استرداد", "toast('تم نشر الدورة')", "toast('تم حفظ سعر الصرف')",
                "toast('تم حفظ بيانات الشركة')", "toast('تم تغيير دور '", "toast('تم تسجيل اهتمامك", "user@mail.com", 'عرض مؤقت بالبيانات التصميمية'):
        assert bad not in HTML + API_JS, bad
    assert "const ESC_NO_DATA_AR='ما وصلتش البيانات — حاول تاني'" in HTML
    assert HTML.count('toast(ESC_NO_DATA_AR)') >= 5
    assert 'const ESCROW=[];' in HTML and 'const DISPUTES=[];' in HTML and 'const RELEASED=[];' in HTML
    assert 'if (onLocal) onLocal();' not in API_JS                                      # مفيش مستخدم وهمي بيتضاف محليًا


def test_audit_in_tg_ops_comes_after_resp_ok():
    for action in ('signup.ack', 'payment_failure.ack'):
        i = TG_OPS.index("ns['_audit']('%s'" % action)
        assert "ns['_resp_ok'](resp)" in TG_OPS[i - 220:i], action


def test_new_blocks_have_no_middot_beside_arabic_digits():
    home = HOME_JS[HOME_JS.index('R24 م١ · «للعلم»'):HOME_JS.index('// ------------------------------------------------------------------ التنفيذ')]
    logic = LOGIC_JS[LOGIC_JS.index('R24 م١ · «بعدين» و«تجاهل» + «للعلم»'):LOGIC_JS.index('  var api = {')]
    for name, src in (('home', home), ('logic', logic)):
        src = '\n'.join(l for l in src.split('\n')[1:] if not l.strip().startswith('//'))      # تعليقات الكود مش نصوص ظاهرة
        assert re.search(r"[٠-٩]\s*·|·\s*[٠-٩]", src) is None, name
