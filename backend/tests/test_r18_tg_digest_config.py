# -*- coding: utf-8 -*-
"""R18 — أسطر «محرّك الفرص» في ملخص تليجرام اليومي (بلا ما يقع الملخص لو الملخص فشل) + «فحص الإعدادات» (`/api/ops/config-check`).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r18_tg_digest_config.py

⛔ صفر شبكة: `requests.post/request/get` مزيّفة، ولا توكن ولا سرّ حقيقي، ولا رسالة تليجرام حقيقية.
"""
import datetime
import os
import re

import jwt
import pytest
from werkzeug.security import generate_password_hash

import app as appmod
from app import app as flask_app, db, User
import tg_ops

NS = appmod.__dict__
SECRET = 'test-metrics-secret'
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class R:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body
        self.text = ''
        self.content = b'x'

    def json(self):
        if self._body is None:
            raise ValueError('no json')
        return self._body


class Net:
    """يردّ حسب المسار (لا طابور) ويلتقط كل نداء."""
    def __init__(self):
        self.calls = []
        self.by_path = {}

    def request(self, method, url, json=None, headers=None, timeout=None, **k):
        self.calls.append((method, url, json, headers))
        for suffix, r in self.by_path.items():
            if url.endswith(suffix):
                if isinstance(r, Exception):
                    raise r
                return r
        return R(404, {'detail': 'Not Found'})

    def sent_text(self):
        return [c[2]['text'] for c in self.calls if c[1].endswith('/api/bridge/telegram/send')]


@pytest.fixture()
def net(monkeypatch):
    n = Net()
    monkeypatch.setattr(tg_ops.requests, 'request', n.request)
    monkeypatch.setattr(tg_ops.requests, 'post', lambda *a, **k: (_ for _ in ()).throw(AssertionError('إرسال مباشر ممنوع هنا')))
    monkeypatch.setattr(tg_ops.requests, 'get', lambda *a, **k: (_ for _ in ()).throw(AssertionError('get ممنوع')))
    monkeypatch.setattr(tg_ops, 'RETRY_DELAYS', (0, 0))
    for v in ('TELEGRAM_OPS_BOT_TOKEN', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_ADMIN_CHAT_ID', 'DASH_SCHEDULER'):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    with flask_app.app_context():
        tg_ops._STATE['model'].query.delete()
        tg_ops._STATE['kv'].query.delete()
        db.session.commit()
        yield n
        tg_ops._STATE['model'].query.delete()
        tg_ops._STATE['kv'].query.delete()
        db.session.commit()


SUMMARY = {'drafts_waiting': 4, 'possible_duplicates': 1, 'published_24h': 2, 'held_news_24h': 3, 'autorun': {'enabled': True, 'source': 'settings'},
           'last_run': {'at': 'x', 'fetched': 20, 'published': 2, 'drafts': 4, 'skipped': 9, 'errors': 2}}


# ───────────────────────────────────────────────────────── الملخص اليومي

def test_digest_carries_the_opportunity_lines(net):
    net.by_path = {'/api/bridge/ops/queue': R(200, {'alerts_v2': [{'key': 'signups_new', 'count': 1}]}),
                   '/api/bridge/opportunities/summary': R(200, SUMMARY), '/api/bridge/telegram/send': R(200, {'ok': True, 'reason': 'ok'})}
    assert tg_ops.send_digest(NS)['ok'] is True
    text = net.sent_text()[0]
    for line in ('🔎 الفرص:', 'فرص تنتظر المراجعة: ٤', 'منها غالبًا مكررة: ١', 'فرص نُشرت آخر ٢٤ ساعة: ٢', 'أخبار محجوزة للمراجعة آخر ٢٤ ساعة: ٣',
                 'أعطال في آخر تشغيل لجلب الفرص: ٢'):
        assert line in text, (line, text)
    assert 'متوقّف' not in text and 'تسجيلات جديدة لم تُراجع: ١' in text
    assert not re.search(r'·\s*[٠-٩]|[٠-٩]\s*·', text) and 'استشار' not in text
    assert not re.search(r'[0-9]', text), 'كل رقم ظاهر بأرقام هندية'


def test_digest_still_goes_out_when_the_summary_fails(net):
    for bad in (R(500, None), R(404, {'detail': 'Not Found'}), ConnectionError('dns'), R(200, ['not', 'a', 'dict'])):
        net.calls.clear()
        with flask_app.app_context():
            tg_ops._STATE['kv'].query.delete()
            db.session.commit()
        net.by_path = {'/api/bridge/ops/queue': R(200, {'alerts_v2': []}), '/api/bridge/opportunities/summary': bad,
                       '/api/bridge/telegram/send': R(200, {'ok': True, 'reason': 'ok'})}
        assert tg_ops.send_digest(NS)['ok'] is True, bad
        text = net.sent_text()[0]
        assert 'ملخص اليوم' in text and 'الفرص' not in text, text


def test_opportunity_lines_skip_zeros_and_flag_a_stopped_autorun():
    lines = tg_ops.opp_digest_lines({'drafts_waiting': 0, 'possible_duplicates': 0, 'published_24h': 0, 'held_news_24h': None,
                                     'autorun': {'enabled': False}, 'last_run': {'errors': 0}})
    assert lines[0] == '🔎 الفرص:' and any('متوقّف' in x for x in lines) and not any(': ٠' in x for x in lines)
    assert tg_ops.opp_digest_lines({'drafts_waiting': True}) == ['🔎 الفرص:', '• لا جديد ينتظر قرارك']
    assert tg_ops.opp_digest_lines(None) == [] and tg_ops.opp_digest_lines([]) == []


def test_digest_text_without_opp_keeps_the_old_shape(net):
    t = tg_ops.digest_text(NS, {'alerts_v2': []})
    assert 'الفرص' not in t and 'لا شيء ينتظر قرارك' in t


# ───────────────────────────────────────────────────────── فحص الإعدادات

def _admin_headers():
    with flask_app.app_context():
        db.create_all()
        u = User.query.filter_by(email='r18cfg-admin@x.test').first()
        if not u:
            u = User(email='r18cfg-admin@x.test', password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name='a', role='admin',
                     dashboard_role='admin', linked_to_name='', preferred_currency='AUTO', is_active=True)
            db.session.add(u)
            db.session.commit()
        tok = jwt.encode({'user_id': u.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


# مفتاح وهمي بيتبني وقت التشغيل (حماية GitHub بترفض أي نص شكله مفتاح Stripe حيّ في الكود).
FAKE_LIVE_KEY = 'sk_' + 'live_' + 'FAKEFAKEFAKEFAKE0000'

ITEMS = [{'key': 'ai_daily_cap', 'label_ar': 'سقف نداءات الذكاء اليومي', 'value': 300, 'ok': False, 'fix_ar': 'في Coolify ← الباك إند ← المتغيرات: AI_DAILY_CALLS_CAP = 1500 أو امسحه',
          'secret': 'sk-live-xxx'},
         {'key': 'stripe', 'label_ar': 'مفتاح الدفع', 'value': 'live', 'ok': True, 'fix_ar': ''},
         {'key': 'leaky', 'label_ar': 'قيمة طويلة', 'value': FAKE_LIVE_KEY, 'ok': True},
         {'key': 'bad key!', 'label_ar': 'x', 'value': 1, 'ok': True},
         'not a dict']


def test_config_check_whitelists_items_and_never_passes_a_secret(net):
    net.by_path = {'/api/bridge/ops/config-check': R(200, {'items': ITEMS})}
    out = tg_ops.config_check(NS)
    keys = [x['key'] for x in out['items']]
    assert keys[:3] == ['ai_daily_cap', 'stripe', 'leaky'] and 'bad key!' not in keys
    assert keys[3:] == ['dash.bridge_secret', 'dash.scheduler']
    a = out['items'][0]
    assert a == {'key': 'ai_daily_cap', 'label_ar': 'سقف نداءات الذكاء اليومي', 'value': 300, 'ok': False,
                 'fix_ar': 'في Coolify ← الباك إند ← المتغيرات: AI_DAILY_CALLS_CAP = 1500 أو امسحه', 'where': 'platform'}
    assert out['items'][2]['value'] == 'مضبوط', 'نص طويل بشكل مفتاح لا يعدّي'
    assert out['platform_ok'] is True and out['bad'] == 1
    blob = repr(out)
    assert 'sk-live' not in blob and 'sk_live' not in blob and SECRET not in blob
    assert [c for c in net.calls if c[1].endswith('/api/bridge/ops/config-check')][0][3] == {'X-ELP-Metrics-Secret': SECRET}


def test_config_check_platform_missing_or_down_keeps_dashboard_items_only(net, monkeypatch):
    net.by_path = {'/api/bridge/ops/config-check': R(404, {'detail': 'Not Found'})}
    out = tg_ops.config_check(NS)
    assert out['platform_ok'] is False and out['platform_missing'] is True and [x['where'] for x in out['items']] == ['dashboard', 'dashboard']
    net.by_path = {'/api/bridge/ops/config-check': ConnectionError('dns')}
    out = tg_ops.config_check(NS)
    assert out['platform_ok'] is False and out['platform_missing'] is False and out['platform_error'] == 'network'
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    monkeypatch.setenv('DASH_SCHEDULER', '0')
    out = tg_ops.config_check(NS)
    assert out['platform_error'] == 'no_bridge_secret' and out['bad'] == 2 and all(x['ok'] is False for x in out['items'])


def test_config_check_route_is_admin_only_and_no_store(net):
    net.by_path = {'/api/bridge/ops/config-check': R(200, {'items': ITEMS[:2]})}
    c = flask_app.test_client()
    assert c.get('/api/ops/config-check').status_code == 401
    r = c.get('/api/ops/config-check', headers=_admin_headers())
    assert r.status_code == 200 and r.headers.get('Cache-Control') == 'no-store'
    assert [x['key'] for x in r.get_json()['items']] == ['ai_daily_cap', 'stripe', 'dash.bridge_secret', 'dash.scheduler']
    with flask_app.app_context():
        u = User.query.filter_by(email='r18cfg-emp@x.test').first()
        if not u:
            u = User(email='r18cfg-emp@x.test', password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name='e', role='employee',
                     dashboard_role='employee', linked_to_name='', preferred_currency='AUTO', is_active=True)
            db.session.add(u)
            db.session.commit()
        tok = jwt.encode({'user_id': u.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    assert c.get('/api/ops/config-check', headers={'Authorization': 'Bearer ' + tok}).status_code == 403


def test_config_check_ui_is_wired_in_both_settings_screens():
    html = open(os.path.join(ROOT, 'dashboard-cloud', 'index.html'), encoding='utf-8').read()
    assert 'id="cfgPanel"' in html and "EP.get('/ops/config-check')" in html and 'cfgPanelWire();' in html
    co = open(os.path.join(ROOT, 'dashboard-cloud', 'v2s', 'company.js'), encoding='utf-8').read()
    assert "cfg: '/ops/config-check'" in co and "card('فحص الإعدادات'" in co and "card('تنبيهات تليجرام'" in co
    assert "settings: { src: ['cfg']" in co and "wireTg();" in co and 'data-tg="test"' in co


# ───────────────────────────────────────────────────────── جولة التصليح: أشكال `ops_config.py` الحقيقية (قيمة = قاموس)
COOL = 'في Coolify ← الباك إند ← المتغيرات: '
REAL_ITEMS = [
    {'key': 'ai_daily_calls_cap', 'label_ar': 'سقف نداءات الذكاء في اليوم', 'value': {'limit': 300, 'source': 'env'}, 'ok': False,
     'fix_ar': COOL + 'AI_DAILY_CALLS_CAP = 1500 أو امسحه'},
    {'key': 'free_ai_requests', 'label_ar': 'أسئلة بروف المجانية', 'value': {'value': 10, 'source': 'default'}, 'ok': True, 'fix_ar': ''},
    {'key': 'free_ai_period', 'label_ar': 'نظام الأسئلة المجانية', 'value': {'value': 'monthly', 'source': 'env'}, 'ok': False,
     'fix_ar': COOL + 'FREE_AI_PERIOD = once ثم إعادة تشغيل الباك إند'},
    {'key': 'telegram_bot_token', 'label_ar': 'توكن بوت التليجرام', 'value': {'set': True}, 'ok': True, 'fix_ar': ''},
    {'key': 'brevo_api_key', 'label_ar': 'مفتاح إرسال الإيميلات (Brevo)', 'value': {'set': False}, 'ok': False, 'fix_ar': COOL + 'BREVO_API_KEY = المفتاح'},
    {'key': 'stripe_key', 'label_ar': 'مفتاح الدفع بالبطاقة (Stripe)', 'value': {'set': True, 'mode': 'test'}, 'ok': False, 'fix_ar': COOL + 'STRIPE_SECRET_KEY مفتاح تجريبي'},
    {'key': 'saha_enabled', 'label_ar': 'الساحة مفتوحة', 'value': {'enabled': True}, 'ok': True, 'fix_ar': ''},
    {'key': 'opp_autorun', 'label_ar': 'جلب الفرص اليومي', 'value': {'enabled': True, 'source': 'settings', 'hours': '7,19'}, 'ok': True, 'fix_ar': ''},
    {'key': 'opp_digest', 'label_ar': 'إيميل «فرص الأسبوع في مسارك»', 'value': {'enabled': False}, 'ok': False,
     'fix_ar': 'من الداشبورد ← الفرص ← «إيميل الأسبوع»: شغّل المفتاح بعد رسالة تجربة'},
    {'key': 'opp_state', 'label_ar': 'حالة الفرص', 'value': {'error': True}, 'ok': False, 'fix_ar': 'القاعدة مش متاحة دلوقتي — جرّب تاني'},
    {'key': 'weird', 'label_ar': 'شكل غريب', 'value': {'token': FAKE_LIVE_KEY, 'raw': 'x'}, 'ok': True},
]


def test_config_check_flattens_the_real_platform_value_shapes(net):
    net.by_path = {'/api/bridge/ops/config-check': R(200, {'items': REAL_ITEMS, 'ok': False})}
    out = tg_ops.config_check(NS)
    v = {x['key']: x['value'] for x in out['items']}
    assert v['ai_daily_calls_cap'] == '300 (من إعدادات الخادم)', 'الرقم الفعلي ومصدره يظهروا'
    assert v['free_ai_requests'] == '10 (القيمة الافتراضية)' and v['free_ai_period'] == 'كل شهر (من إعدادات الخادم)'
    assert v['telegram_bot_token'] == 'مضبوط' and v['brevo_api_key'] == 'غير مضبوط' and v['stripe_key'] == 'مضبوط، تجريبي'
    assert v['saha_enabled'] == 'يعمل' and v['opp_autorun'] == 'يعمل، الساعة 7 و19 (محفوظ في المنصة)' and v['opp_digest'] == 'متوقّف'
    assert v['opp_state'] == 'تعذّرت القراءة' and v['weird'] is None, 'حقل مش معروف يتشال'
    assert 'sk_live' not in repr(out)
    assert out['bad'] == 6


def test_config_check_points_the_opportunity_items_to_the_real_screen(net):
    net.by_path = {'/api/bridge/ops/config-check': R(200, {'items': REAL_ITEMS})}
    fx = {x['key']: x['fix_ar'] for x in tg_ops.config_check(NS)['items']}
    assert 'الساحة ← محرّك الفرص ← إيميل الأسبوع' in fx['opp_digest'] and '← الفرص ←' not in fx['opp_digest']
    assert fx['opp_autorun'] == '', 'بند سليم بلا نص تصليح'
    bad_auto = dict(REAL_ITEMS[7], value={'enabled': False, 'source': 'default', 'hours': '7'}, ok=False, fix_ar='من الداشبورد ← الفرص ← «التشغيل اليومي»: شغّل المفتاح')
    net.by_path = {'/api/bridge/ops/config-check': R(200, {'items': [bad_auto]})}
    it = tg_ops.config_check(NS)['items'][0]
    assert it['value'] == 'متوقّف (القيمة الافتراضية)' and 'الساحة ← محرّك الفرص ← التشغيل' in it['fix_ar']

