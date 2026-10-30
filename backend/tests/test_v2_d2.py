# -*- coding: utf-8 -*-
"""D2 — تذاكر بعدّاد في «ملفات الخبراء» و«النزاعات والاستردادات» + صفحة الشخص الواحد، ورا نفس المفتاح المقفول.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2_d2.py

⛔ صفر شبكة حقيقية: المنصة جدول في الذاكرة (`uiharness/v2_fixtures.V2Platform(d2=True)`)، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.
المنطق النقي (v2Tickets · v2DisputeTickets · v2Person) بيتشغّل في node على صفوف الوارد الحقيقية (dashboard-api.js جوه node:vm).

اللي بيثبّته:
  ١. التذاكر: كل نوع صف في عموده الصح · نص العدّاد («متأخر ٢ س» / «باقٍ ٥ س» / «منذ ٣٥ د») · صف مجهول النوع ما بيسقطش (بيروح «ينتظر
     مراجعتك» بجملة عامة) · «عند الخبراء» أقرب ٣ بس + «و N في موعدها» · سطر التوزيع التلقائي · ولا زرّ قرار فلوس في أي تذكرة.
  ٢. النزاعات: العمدان الثلاثة بالمبلغ والعملة والطرفين والمدة والسبب بفصحى (مفيش نص خام من العميل) وزرّ «افتح وقرّر» بس، وبطاقة العدّ للاستردادات اليدوية.
  ٣. الشخص (node): فشل المصدر ⇒ «غير متاح بعد» مش صفر · لا «0» · الرابط والعنوان.
  ٤. `GET /api/v2/person` (pytest): أدمن بس · المفتاح مقفول ٤٠٤ · كل مصدر بيتنادى (قراءة بس، وبالسرّ) · المصدر الفاشل ⇒ null · ولا بريد
     مختلق ولا بريد غير المطلوب · ولا سطر سجل ولا تدقيق بأي بيانات من الشخص.
  ٥. الملفات: الغلاف · Dockerfile · الخطّافات في index.html · المفتاح مقفول ⇒ لا أثر.
"""
import copy
import datetime
import json
import os
import re
import sys
import time

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import fake_platform as fp   # noqa: E402
import v2_fixtures as v2fx   # noqa: E402
import v2_node               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
DC = os.path.join(ROOT, 'dashboard-cloud')
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
NOW = int(time.time() * 1000)
HALA = v2fx.HALA


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


# ---------------------------------------------------------------- أدوات (نفس نمط test_v2_d1)

class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else b''
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        return self._p


def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if u:
        u.role = role
        u.dashboard_role = role
        u.is_active = True
        db.session.commit()
        return u
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
             name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
             preferred_currency='AUTO', is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('v2d2-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser('v2d2-admin@x.test', 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    """`requests.request` البديل: يسجّل كل نداء ويرد من `V2Platform(d2=True)`. أي عنوان برّه المنصة المزيّفة ⇒ ممنوع."""

    def __init__(self):
        self.ef = v2fx.V2Platform(d2=True)
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'url': url, 'path': url[len(PLATFORM):], 'params': dict(params or {}),
                          'headers': dict(headers or {}), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        out = self.ef.handle(method, url[len(PLATFORM):], params, json)
        if out is None:
            return _Resp(200, [])
        return _Resp(*out)


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


def _person(ctx, email=HALA, role='admin', raw=None):
    c = ctx['client']
    path = '/api/v2/person?email=' + (raw if raw is not None else email)
    return c.get(path, headers=ctx['heads'][role] if role else {})


# ---------------------------------------------------------------- ١) صفوف الوارد الحقيقية

@pytest.fixture(scope='module')
def real(ctx):
    if not v2_node.NODE:
        pytest.skip('needs node')
    import app as appmod
    mp = pytest.MonkeyPatch()
    p = Plat()
    mp.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    mp.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    mp.setattr(appmod.requests, 'request', p)
    mp.setattr(appmod.requests, 'get', lambda url, **kw: p('GET', url, params=kw.get('params'), json=None,
                                                          headers=kw.get('headers'), timeout=kw.get('timeout')))
    try:
        out = v2_node.real_rows(ctx['client'], ctx['heads']['admin'])
    finally:
        mp.undo()
    assert p.blocked == []
    return out


def _tickets(real, **opts):
    o = {'now': NOW, 'queue': real['data']['opsQueue']}
    o.update(opts)
    return v2_node.logic('v2Tickets', list(real['inbox']), o)


def _dispute_tickets(real, **opts):
    o = {'now': NOW, 'queue': real['data']['opsQueue']}
    o.update(opts)
    return v2_node.logic('v2DisputeTickets', [r for r in real['inbox'] if not r.get('fyi')], o)


def _by_id(T, fid):
    for c in T['cols']:
        for t in T['cols'][c]:
            if (t['row'].get('ef') or {}).get('id') == fid:
                return c, t
    return None, None


@needs_node
def test_the_real_pipeline_still_loads_every_source(real):
    assert real['failed'] == [], real['failed']
    assert all(real['state'][k] == 'ready' for k in ('opsQueue', 'inbox', 'walletPayouts', 'invites', 'pendingUsers', 'market'))


# ---------------------------------------------------------------- ٢) تذاكر الملفات

@needs_node
def test_every_file_row_lands_in_its_own_column(real):
    T = _tickets(real, autoAssign=True, brainToday=2)
    col = lambda fid: _by_id(T, fid)[0]
    # متأخر: رأي عدّى ميعاده · ملف اتبعت لخبير وما اتستلمش
    assert col('ef-f5-4e5f6a7b') == 'late' and col('ef-x3-3c4d5e6f') == 'late' and col('ef-f3-2c3d4e5f') == 'late'
    # ينتظر مراجعتك: ملف مستني خبير (ميعاده لسه) · رأي للمراجعة · أموال متوقفة
    assert col('ef-f2-1b2c3d4e') == 'review' and col('ef-f1-0a1b2c3d') == 'review'
    assert col('ef-r1-9a0b1c2d') == 'review' and col('ef-kr-9d0e1f2a') == 'review'
    assert col('ef-f7-6b7c8d9e') == 'review' and col('ef-f6-5a6b7c8d') == 'review'
    # عند الخبراء: اتبعت من ساعات وفي موعده
    assert col('ef-w1-aa11bb22') == 'with' and col('ef-k2-7b8c9d0e') == 'with'
    # خلص النهارده: رأي اتعتمد النهارده
    assert col('ef-dn-1a1a2b2b') == 'done' and col('ef-dn-2b2b3c3c') == 'done'
    # كل صف في عمود واحد بالضبط وما سقطش ولا واحد (الصفوف التانية — نزاعات/قضايا/دفع بلا ملف — للوحة النزاعات)
    ids = [t['id'] for c in T['cols'] for t in T['cols'][c]]
    assert len(ids) == len(set(ids)) and T['total'] == len(ids)
    file_rows = [r for r in real['inbox'] if r.get('apiKind') == 'expert_file' and r.get('efLane') not in ('unactivated', 'case_disputed')]
    assert len(real['inbox']) > len(file_rows)
    only_files = v2_node.logic('v2Tickets', file_rows, {'now': NOW})
    assert only_files['total'] == len(file_rows), 'صف ملف سقط'


@needs_node
def test_tickets_carry_type_timer_parties_brain_line_and_one_button(real):
    T = _tickets(real)
    c, t = _by_id(T, 'ef-f5-4e5f6a7b')
    assert t['strip']['label'] == 'رأي متأخر' and re.fullmatch(r'متأخر [٠-٩]+ (س|د)|متأخر [٠-٩]+ أيام|متأخر يومان|متأخر يوم', t['text']), t['text']
    assert t['tone'] == 'late' and t['client'] == 'طارق' and t['expert']['name'] == 'م. سامي فؤاد'
    assert t['brain'].startswith('متأخر') and 'أقترح نقله إلى' in t['brain'] and t['reason']
    assert t['primary']['label'].startswith('انقله إلى ') and t['primary']['act']['do'] == 'send'
    c, t = _by_id(T, 'ef-f2-1b2c3d4e')
    assert t['strip']['label'] == 'ينتظر خبيرًا' and t['text'].startswith('باقٍ ') and t['primary']['act']['do'] == 'send'
    assert t['primary']['label'].startswith('أرسله إلى ')
    c, t = _by_id(T, 'ef-r1-9a0b1c2d')
    assert t['strip']['label'] == 'رأي ينتظر مراجعتك' and t['text'].startswith('منذ ') and t['primary']['act']['do'] == 'open'
    c, t = _by_id(T, 'ef-w1-aa11bb22')
    assert t['text'].startswith('باقٍ ') and t['primary']['act']['do'] == 'open' and t['brain'].startswith('ما زال بانتظار الاستلام لدى ')
    c, t = _by_id(T, 'ef-dn-1a1a2b2b')
    assert t['strip']['label'] == 'اعتُمد اليوم' and t['primary']['act']['do'] == 'open'


@needs_node
def test_the_timer_text_is_exact():
    h = 3600e3
    cases = [({'mode': 'left', 'at': NOW + 5 * h + 1000}, 'باقٍ ٥ س'), ({'mode': 'left', 'at': NOW + 35 * 60e3 + 1000}, 'باقٍ ٣٥ د'),
             ({'mode': 'over', 'at': NOW - 2 * h - 1000}, 'متأخر ٢ س'), ({'mode': 'since', 'at': NOW - 35 * 60e3 - 1000}, 'منذ ٣٥ د'),
             ({'mode': 'since', 'at': NOW - 10e3}, 'الآن'), ({'mode': 'since', 'at': NOW - 3 * 24 * h}, 'منذ ٣ أيام'),
             ({'mode': 'since', 'at': NOW - 49 * h}, 'منذ يومان'),
             # «باقٍ» لما الموعد يعدّى بيتحوّل «متأخر» لوحده (من غير إعادة تحميل)
             ({'mode': 'left', 'at': NOW - 2 * h - 1000}, 'متأخر ٢ س'),
             ({'mode': 'left', 'at': None}, ''), ({'mode': 'since', 'at': 'مش وقت'}, '')]
    got = [v2_node.logic('v2TimerText', t, NOW) for t, _ in cases]
    assert got == [w for _, w in cases]
    tones = v2_node.logic('v2TimerTone', {'mode': 'left', 'at': NOW + 3600e3}, NOW), v2_node.logic('v2TimerTone', {'mode': 'left', 'at': NOW + 5 * 3600e3}, NOW), \
        v2_node.logic('v2TimerTone', {'mode': 'left', 'at': NOW - 1000}, NOW)
    assert tones == ('warn', 'ok', 'late')


@needs_node
def test_the_timer_text_changes_with_the_clock():
    row = {'apiKind': 'expert_file', 'apiId': 'x1', 'efLane': 'waiting', 'who': 'منى',
           'ef': {'id': 'x1', 'status': 'assigned', 'title': 'ملف', 'assigned_to': 'a@b.test', 'assigned_name': 'أ. فلان',
                  'claim_deadline_at': datetime.datetime.utcfromtimestamp((NOW + 5 * 3600e3) / 1000).isoformat() + 'Z', 'hours_left': 5}}
    now0 = v2_node.logic('v2Tickets', [row], {'now': NOW})['cols']['with'][0]['text']
    now1 = v2_node.logic('v2Tickets', [row], {'now': NOW + 61 * 60e3})['cols']['with'][0]['text']
    assert now0 == 'باقٍ ٥ س' and now1 == 'باقٍ ٣ س'
    # بعد الموعد التذكرة تنتقل لـ«متأخر»
    late = v2_node.logic('v2Tickets', [row], {'now': NOW + 6 * 3600e3})
    assert late['counts']['late'] == 1 and late['counts']['with'] == 0 and late['cols']['late'][0]['text'].startswith('متأخر ')


@needs_node
def test_an_unknown_row_type_is_not_dropped_it_goes_to_review_with_a_generic_line():
    rows = [{'apiKind': 'نوع-جديد', 'apiId': 'z1', 'who': 'فلان', 'out': 'بند جديد من المنصة'},
            {'out': 'بلا نوع أصلًا', 'who': 'علان'},
            {'apiKind': 'expert_file', 'apiId': 'z2', 'efLane': 'lane-جديد', 'who': 'منى', 'ef': {'id': 'z2', 'status': 'حالة-جديدة', 'title': 'ملف غريب'}},
            None]
    T = v2_node.logic('v2Tickets', rows, {'now': NOW})
    assert T['total'] == 3, 'صف مجهول سقط'
    assert T['counts'] == {'late': 0, 'review': 3, 'with': 0, 'done': 0}
    unknown = [t for t in T['cols']['review'] if t['strip']['label'] == 'بند ينتظر قرارك']
    assert len(unknown) == 2
    for t in unknown:
        assert t['brain'] == 'يحتاج إلى قرارك' and t['primary'] == {'label': 'افتح البند', 'act': {'do': 'open'}} and t['text'] == ''
    # ملف بحالة جديدة ما نعرفهاش: برضه ما سقطش (في «ينتظر مراجعتك» بوسم الملف)
    weird = [t for t in T['cols']['review'] if t['strip']['label'] != 'بند ينتظر قرارك']
    assert len(weird) == 1 and weird[0]['title'] == 'ملف غريب'
    assert v2_node.logic('v2Tickets', None, {'now': NOW})['total'] == 0
    assert v2_node.logic('v2Tickets', [], {'now': NOW})['counts'] == {'late': 0, 'review': 0, 'with': 0, 'done': 0}


@needs_node
def test_with_experts_shows_the_three_closest_then_n_on_time(real):
    T = _tickets(real)
    n = T['counts']['with']
    assert n >= 5
    shown = T['shown']['with']
    assert len(shown) == 3 and T['withMore'] == n - 3
    deadlines = [t['sortAt'] for t in T['cols']['with']]
    assert deadlines == sorted(deadlines), 'العمود مش مرتّب بالأقرب موعدًا'
    assert [t['id'] for t in shown] == [t['id'] for t in T['cols']['with'][:3]]
    assert all(len(T['shown'][c]) == len(T['cols'][c]) for c in ('late', 'review', 'done'))


@needs_node
def test_the_header_line_reads_the_auto_assign_switch(real):
    on = _tickets(real, autoAssign=True, brainToday=3)
    assert on['header'] == 'التوزيع التلقائي يعمل · وزّع ٣ ملفات اليوم' and on['autoOn'] is True
    assert _tickets(real, autoAssign=True, brainToday=1)['header'] == 'التوزيع التلقائي يعمل · وزّع ملفًا واحدًا اليوم'
    assert _tickets(real, autoAssign=True, brainToday=0)['header'] == 'التوزيع التلقائي يعمل · لم يوزّع شيئًا اليوم'
    off = _tickets(real, autoAssign=False)
    assert off['header'].startswith('التوزيع التلقائي متوقف') and off['autoOn'] is False
    # بلا قيمة: من الطابور (`expert_files_auto_assign`) وإلا مفيش سطر (لا ادّعاء)
    q = dict(real['data']['opsQueue']); q.pop('expert_files_auto_assign', None)
    unknown = v2_node.logic('v2Tickets', list(real['inbox']), {'now': NOW, 'queue': q})
    assert unknown['header'] == '' and unknown['autoOn'] is None
    q['expert_files_auto_assign'] = True
    assert v2_node.logic('v2Tickets', list(real['inbox']), {'now': NOW, 'queue': q})['autoOn'] is True
    assert on['openTotal'] == real['data']['opsQueue']['expert_files_open_total']


@needs_node
def test_a_queue_count_larger_than_the_rows_is_announced_not_hidden(real):
    q = dict(real['data']['opsQueue'])
    ok = v2_node.logic('v2Tickets', list(real['inbox']), {'now': NOW, 'queue': q})
    assert ok['notes'] == {'late': '', 'review': '', 'with': 'المعروض هنا ما أُرسل ولم يُستلم بعد فقط', 'done': ''}, ok['notes']
    q['expert_files_in_review'] = q['expert_files_in_review'] + 4
    q['expert_files_late'] = q['expert_files_late'] + 2
    bad = v2_node.logic('v2Tickets', list(real['inbox']), {'now': NOW, 'queue': q})
    assert bad['notes']['review'].startswith('معروض ') and bad['notes']['late'].startswith('معروض ')


@needs_node
def test_no_ticket_has_a_money_button(real):
    T = _tickets(real)
    for c in T['cols']:
        for t in T['cols'][c]:
            assert t['primary']['act']['do'] in ('open', 'send'), t['primary']
            assert 'money' not in t['primary'] and 'money' not in json.dumps(t['primary'])
    D = _dispute_tickets(real)
    for c in D['cols']:
        for t in D['cols'][c]:
            assert t['primary'] == {'label': 'افتح وقرّر', 'act': {'do': 'open'}}


@needs_node
def test_cards_with_a_person_in_the_title_carry_their_email_so_the_name_opens_the_page(real):
    payouts = real['data']['walletPayouts']['rows']
    cards = v2_node.logic('v2Decisions', [r for r in real['inbox'] if not r.get('fyi')], payouts, real['data']['opsQueue'], {'now': NOW})
    by = {}
    for c in cards:
        by.setdefault(c['kind'], []).append(c)
    pay = by['payout'][0]
    assert pay['person']['email'] in ('hala@example.test', 'faisal@experts.test') and pay['person']['name'] == pay['title']
    assert by['trainer'][0]['person']['email'] == 'hala@example.test'
    assert by['manual_payment'][0]['person']['email'] in ('salma@example.test', 'yasser@example.test')
    assert by['pending_user'][0]['person']['email'] in ('nour.pending@example.test', 'karim.pending@example.test', 'silent.pending@example.test')
    # بطاقة عنوانها ملف (مش شخص) ما بيبقاش عليها رابط اسم
    assert all('person' not in c for k in ('file_waiting', 'dispute', 'review') for c in by.get(k, []))
    # بريد غير صالح ⇒ لا رابط (ولا بريد مخترع)
    bad = v2_node.logic('v2Card', {'apiKind': 'trainer', 'apiId': 't', 'who': 'فلان', 'personEmail': 'مش بريد'}, {'now': NOW})
    assert 'person' not in bad


# ---------------------------------------------------------------- ٣) تذاكر النزاعات

@needs_node
def test_dispute_tickets_columns_amount_parties_age_and_plain_reason(real):
    D = _dispute_tickets(real)
    c = D['counts']
    assert c['disputes'] >= 4 and c['legacy'] == 3 and len(D['cols']['refunds']) == 2
    kinds = {t['strip']['label'] for t in D['cols']['disputes']}
    assert {'نزاع على ملف', 'نزاع على استشارة', 'ملاحظة على مرحلة من قضية'} <= kinds
    for col in D['cols']:
        for t in D['cols'][col]:
            assert t['amount'] and re.search(r'جنيه|ريال|دولار|درهم|يورو', t['amount']), t
            assert t['text'].startswith('مفتوح منذ ') and t['title'] and t['client'] != '' and t['reason']
    f = [t for t in D['cols']['disputes'] if t['strip']['label'] == 'نزاع على ملف'][0]
    assert f['client'] == 'ريم' and f['expert'] == 'د. ندى حسن' and f['amount'] == '٥٠٠ جنيه'
    assert f['reason'] == 'اعتراض صاحب الطلب: الرأي لم يجب عن سؤال صاحب الطلب'
    # مرتّبة بالأقدم أولًا
    for col in D['cols']:
        ats = [t['sortAt'] for t in D['cols'][col] if t['sortAt'] is not None]
        assert ats == sorted(ats)


@needs_node
def test_dispute_reasons_are_never_raw_platform_or_client_text(real):
    D = _dispute_tickets(real)
    blob = ' | '.join(t['reason'] for c in D['cols'] for t in D['cols'][c])
    # نص حرّ كتبه العميل أو المنصة في صفوف الطقم ما يظهرش
    for raw in ('سألت إمتى الحضانة', 'الرأي اتكلم عن النفقة بس', 'ما اتكتبش سبب', 'فيه حاجة مش فاهمها', 'اتدفع وما وصلش', 'اتسلّمت قبل ما التحويل'):
        assert raw not in blob, raw
    assert re.search(r'ملاحظة من صاحب الطلب على المرحلة رقم [٠-٩]+', blob)
    assert 'دُفع المبلغ ولم يصل الملف إلى قائمة التوزيع' in blob and 'استشارة سُلّمت قبل التحويل التلقائي' in blob
    # كل سبب بكودات معروفة بيتترجم، والمجهول بيتقال بجملة ثابتة
    rows = [{'apiKind': 'dispute', 'dsrc': 'file', 'apiId': 'q1', 'who': 'منى', 'ef': {'id': 'q1', 'title': 'ملف', 'amount': 100, 'currency': 'SAR',
                                                                                          'dispute': {'reason': code, 'at': '2026-10-01T00:00:00Z', 'note': 'نص خام'}}}
            for code in ('unclear', 'not_answered', 'wrong_facts', 'كود-جديد')]
    out = v2_node.logic('v2DisputeTickets', rows, {'now': NOW})['cols']['disputes']
    assert [t['reason'] for t in out] == ['اعتراض صاحب الطلب: جزء من الرأي غير مفهوم لصاحب الطلب', 'اعتراض صاحب الطلب: الرأي لم يجب عن سؤال صاحب الطلب',
                                          'اعتراض صاحب الطلب: خطأ في الوقائع المذكورة في الرأي', 'اعتراض صاحب الطلب: لم يحدد صاحب الطلب سببًا']
    assert 'نص خام' not in json.dumps([t['reason'] for t in out], ensure_ascii=False)
    assert all('SAR' not in t['amount'] and 'ريال' in t['amount'] for t in out)


@needs_node
def test_manual_refunds_are_a_count_card_and_a_missing_queue_is_null_not_zero(real):
    D = _dispute_tickets(real)
    assert D['manualRefunds'] == real['data']['opsQueue']['manual_refunds_pending'] == 1
    assert D['counts']['refunds'] == 2 + 1
    none = v2_node.logic('v2DisputeTickets', [r for r in real['inbox'] if not r.get('fyi')], {'now': NOW, 'queue': None})
    assert none['manualRefunds'] is None and none['counts']['refunds'] == 2
    zero = dict(real['data']['opsQueue']); zero['manual_refunds_pending'] = 0
    assert v2_node.logic('v2DisputeTickets', [], {'now': NOW, 'queue': zero})['manualRefunds'] == 0


# ---------------------------------------------------------------- ٤) الشخص: العنوان والمنطق (node)

@needs_node
def test_person_address_round_trip_and_the_hidden_tab():
    res = v2_node.logic('routeFor', '#s/people/person/' + 'Hala%40Example.TEST')
    assert res['section'] == 'people' and res['tab'] == 'person' and res['mod'] == 'v2person' and res['person'] == HALA
    assert v2_node.logic('sectionHash', 'people', 'person', 'A@B.com') == '#s/people/person/a%40b.com'
    assert v2_node.logic('sectionHash', 'people', 'users', 'a@b.com') == '#s/people/users'
    # بلا بريد صالح ⇒ أول تبويب (لا صفحة فاضية)
    for bad in ('#s/people/person', '#s/people/person/', '#s/people/person/zzz', '#s/people/person/%E0%A4%A'):
        r = v2_node.logic('routeFor', bad)
        assert (r['section'], r['tab']) == ('people', 'invites') and 'person' not in r, bad     # أول تبويب في «الناس والدعوات» صار «الطلبات»
    assert v2_node.logic('personEmailOf', 'a%40b.com') == 'a@b.com' and v2_node.logic('personEmailOf', 'x') == ''
    hidden = v2_node.logic('SECTIONS')
    tabs = [t for s in hidden if s['key'] == 'people' for t in s['tabs']]
    assert [t['key'] for t in tabs if t.get('hidden')] == ['person'] and not any(t.get('hidden') for s in hidden if s['key'] not in ('people', 'money', 'courses', 'company') for t in s['tabs'])
    assert [t['key'] for s in hidden if s['key'] == 'money' for t in s['tabs'] if t.get('hidden')] == [], 'الإيصالات اليدوية لها تبويبها الجديد: لا تبويب قديم مخفي'


FULL = {'email': HALA, 'found': True, 'roles': ['expert', 'trainer'],
        'sources': {k: 'ok' for k in ('users', 'invites', 'experts', 'courses', 'files', 'payouts_pending', 'payouts_paid', 'pending', 'enrollments')},
        'identity': {'name': 'د. هالة سمير', 'trainer_status': 'approved', 'is_active': True, 'joined_at': '2026-04-23T10:00:00Z',
                     'last_login_at': '2026-10-30T09:00:00Z', 'photo': None, 'country': None,
                     'invited_by': {'name': 'أ. نادية فؤاد', 'kind': 'member'}},
        'expert': {'files_count': 4, 'partial': False, 'latest': [{'id': 'f1', 'title': 'عقد', 'status': 'writing', 'amount': 500, 'currency': 'EGP', 'at': '2026-10-30T01:00:00Z'}]},
        'trainer': {'status': 'approved', 'courses_count': 2, 'students_count': 31, 'rating_avg': 4.7, 'rating_count': 12,
                    'courses': [{'title': 'أساسيات العقود', 'state': 'published'}]},
        'money': {'pending': {'count': 1, 'amounts': [{'currency': 'EGP', 'amount': 1200}], 'partial': False},
                  'paid': {'count': 2, 'amounts': [{'currency': 'EGP', 'amount': 3350.5}], 'partial': False}, 'balance': None},
        'learner': {'enrollments_count': 0, 'reservations_count': 0}, 'books': None,
        'log': [{'at': '2026-10-30T09:00:00Z', 'kind': 'login', 'title': None}, {'at': '2026-10-29T09:00:00Z', 'kind': 'file_assigned', 'title': 'عقد إيجار'}],
        'log_partial': False}


@needs_node
def test_person_view_model_from_a_full_response():
    vm = v2_node.logic('v2Person', FULL, NOW, HALA)
    assert vm['state'] == 'ok' and vm['name'] == 'د. هالة سمير' and vm['initial'] == 'ه'
    assert [c['label'] for c in vm['chips']] == ['خبير', 'مدرّب']
    assert vm['joinLine'] == 'الانضمام في ٢٣ أبريل ٢٠٢٦ · بدعوة من أ. نادية فؤاد'
    assert [c['title'] for c in vm['cards']] == ['الملفات', 'الدورات', 'الفلوس', 'التعلّم']
    files, courses, money, learn = vm['cards']
    assert files['summary'] == '٤ ملفات' and files['items'][0]['title'] == 'عقد'
    assert 'دورتان' in courses['summary'] and '٣١' in courses['summary'] and courses['items'][0]['meta'] == 'منشورة'
    rows = {r['k']: r for r in money['rows']}
    assert rows['طلبات سحب معلقة']['v'] == 'طلب واحد — ١٬٢٠٠ جنيه' and rows['ما حُوّل من قبل']['v'] == 'طلبان — ٣٬٣٥٠٫٥ جنيه'
    assert rows['رصيد المحفظة']['na'] is True and rows['رصيد المحفظة']['v'] == 'غير متاح بعد'
    lrows = {r['k']: r for r in learn['rows']}
    assert lrows['دورات سجّل فيها أو دفع ثمنها']['v'] == 'لا تسجيلات' and lrows['الكتب المشتراة']['na'] is True
    assert [e['text'] for e in vm['log']] == ['آخر دخول', 'إسناد ملف «عقد إيجار»']
    assert vm['countryText'] == 'غير متاح بعد' and vm['photo'] is None


@needs_node
def test_a_failed_source_is_na_never_zero():
    resp = copy.deepcopy(FULL)
    resp.update({'expert': None, 'trainer': None, 'money': None, 'learner': None, 'log': None})
    resp['sources'].update({'files': 'failed', 'experts': 'failed', 'payouts_pending': 'failed', 'payouts_paid': 'failed', 'enrollments': 'failed'})
    vm = v2_node.logic('v2Person', resp, NOW, HALA)
    files, courses, money, learn = vm['cards']
    for c in (files, courses, money):
        assert c['na'] is True and c['text'] == 'غير متاح بعد'
    lrows = {r['k']: r for r in learn['rows']}
    assert lrows['دورات سجّل فيها أو دفع ثمنها'] == {'k': 'دورات سجّل فيها أو دفع ثمنها', 'v': 'غير متاح بعد', 'na': True}
    assert vm['log'] is None and 'files' in ' '.join(vm['failed']) and vm['failed']
    shown = json.dumps(vm['cards'], ensure_ascii=False)
    assert not re.search(r'(?<![\w])(0|٠)(?![\w٠-٩])', shown), shown
    # دفعة واحدة من اتنين فشلت: الفاشلة «غير متاح»، والتانية بقيمتها
    resp = copy.deepcopy(FULL); resp['money']['paid'] = None
    rows = {r['k']: r for r in v2_node.logic('v2Person', resp, NOW, HALA)['cards'][2]['rows']}
    assert rows['ما حُوّل من قبل'] == {'k': 'ما حُوّل من قبل', 'v': 'غير متاح بعد', 'na': True} and rows['طلبات سحب معلقة']['v'].startswith('طلب واحد')
    # مصدر المدرّب فاشل لكن الحساب مدرّب: «غير متاح» مش «ليس مدرّبًا»
    resp = copy.deepcopy(FULL); resp['trainer'] = None
    assert v2_node.logic('v2Person', resp, NOW, HALA)['cards'][1]['na'] is True
    resp['identity']['trainer_status'] = 'none'
    assert v2_node.logic('v2Person', resp, NOW, HALA)['cards'][1]['summary'] == 'لا صفة مدرّب لهذا الحساب'


@needs_node
def test_partial_lists_are_not_presented_as_complete_zero():
    resp = copy.deepcopy(FULL)
    resp['expert'] = {'files_count': 0, 'partial': True, 'latest': []}
    resp['money']['pending'] = {'count': 0, 'amounts': [], 'partial': True}
    vm = v2_node.logic('v2Person', resp, NOW, HALA)
    assert vm['cards'][0]['summary'] == 'لا ملفات ضمن الجزء المعروض من الملفات'
    assert {r['k']: r['v'] for r in vm['cards'][2]['rows']}['طلبات سحب معلقة'] == 'لا شيء ضمن الجزء المعروض'
    resp['expert'] = {'files_count': 0, 'partial': False, 'latest': []}
    assert v2_node.logic('v2Person', resp, NOW, HALA)['cards'][0]['summary'] == 'لا ملفات بعد'


@needs_node
def test_person_states_failed_and_not_found_and_the_inviter_is_never_invented():
    assert v2_node.logic('v2Person', None, NOW, HALA)['state'] == 'failed'
    assert v2_node.logic('v2Person', {'email': HALA, 'found': None, 'sources': {'users': 'failed'}}, NOW, HALA)['state'] == 'failed'
    assert v2_node.logic('v2Person', {'email': HALA, 'found': False, 'sources': {}}, NOW, HALA)['state'] == 'notfound'
    resp = copy.deepcopy(FULL); resp['identity']['invited_by'] = None
    assert v2_node.logic('v2Person', resp, NOW, HALA)['joinLine'] == 'الانضمام في ٢٣ أبريل ٢٠٢٦'
    resp['sources']['invites'] = 'failed'
    assert v2_node.logic('v2Person', resp, NOW, HALA)['joinLine'] == 'الانضمام في ٢٣ أبريل ٢٠٢٦ · الداعي: غير متاح بعد'
    resp['identity']['invited_by'] = {'name': None, 'kind': 'founder'}
    assert v2_node.logic('v2Person', resp, NOW, HALA)['joinLine'].endswith('بدعوة من الإدارة')


# ---------------------------------------------------------------- ٥) `GET /api/v2/person`

PERSON_PATHS = {'/api/bridge/users', '/api/bridge/invites', '/api/bridge/experts', '/api/bridge/courses', '/api/bridge/expert-files',
                '/api/bridge/wallet-payouts', '/api/bridge/pending-users'}


def test_person_is_admin_only(ctx, plat):
    for role in NON_ADMIN_ROLES:
        r = _person(ctx, role=role)
        assert r.status_code == 403, role
        assert 'identity' not in (r.get_json() or {})
    assert _person(ctx, role=None).status_code == 401
    assert plat.seen == [], 'ولا نداء للمنصة لغير الأدمن'


def test_person_is_closed_when_the_switch_is_off(ctx, plat, monkeypatch):
    monkeypatch.delenv('DASH_V2_ENABLED', raising=False)
    r = _person(ctx)
    assert r.status_code == 404 and plat.seen == []
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert _person(ctx).status_code == 404 and plat.seen == []


@pytest.mark.parametrize('raw', ['', 'x', 'a@b', '@b.com', 'a b@c.com', 'a@@b.com', 'a@b.com' + 'x' * 200, '../etc/passwd'])
def test_person_rejects_bad_emails_before_any_call(ctx, plat, raw):
    r = _person(ctx, raw=raw)
    assert r.status_code == 400 and plat.seen == []


def test_person_calls_every_source_read_only_with_the_secret(ctx, plat):
    r = _person(ctx)
    assert r.status_code == 200
    paths = {c['path'] for c in plat.seen}
    assert PERSON_PATHS <= paths and any(re.fullmatch(r'/api/bridge/users/[^/]+/purge-check', p) for p in paths)
    assert all(c['method'] == 'GET' for c in plat.seen), 'مفيش أي كتابة'
    assert all(c['headers'].get('X-ELP-Metrics-Secret') == SECRET for c in plat.seen)
    assert all(c['timeout'] and c['timeout'] <= 12 for c in plat.seen)
    statuses = sorted(c['params'].get('status') for c in plat.seen if c['path'] == '/api/bridge/wallet-payouts')
    assert statuses == ['paid', 'pending']
    assert [c['params'] for c in plat.seen if c['path'] == '/api/bridge/expert-files'] == [{'status': 'all'}]
    assert [c['params'].get('search') for c in plat.seen if c['path'] == '/api/bridge/users'] == [HALA]
    # نداء واحد لكل مصدر (لا إعادة محاولة)
    from collections import Counter
    assert max(Counter(c['path'] for c in plat.seen).values()) <= 2 and Counter(c['path'] for c in plat.seen)['/api/bridge/experts'] == 1
    assert r.headers['Cache-Control'] == 'no-store'


def test_person_full_page_every_field_from_its_source(ctx, plat):
    d = _person(ctx).get_json()
    assert d['found'] is True and d['email'] == HALA and all(v == 'ok' for k, v in d['sources'].items() if k in
                                                            ('users', 'invites', 'experts', 'courses', 'files', 'payouts_pending', 'payouts_paid', 'pending', 'enrollments'))
    assert d['sources']['photo'] == d['sources']['books'] == d['sources']['balance'] == d['sources']['client_files'] == 'none'
    i = d['identity']
    assert i['name'] == 'د. هالة سمير' and i['trainer_status'] == 'approved' and i['plan_id'] == 'pro' and i['joined_at'] and i['last_login_at']
    assert i['photo'] is None and i['country'] is None and i['invited_by'] == {'name': 'أ. نادية فؤاد', 'kind': 'member'}
    assert d['roles'] == ['expert', 'trainer']
    e = d['expert']
    assert e['files_count'] == 4 and e['partial'] is False and len(e['latest']) == 3
    assert [f['title'] for f in e['latest']][0] == 'إنذار بسداد متأخرات الإيجار'
    t = d['trainer']
    assert t['status'] == 'approved' and t['courses_count'] == 2 and t['students_count'] == 31 and t['rating_avg'] == 4.7 and t['rating_count'] == 12
    assert t['courses'] == [{'title': 'أساسيات صياغة العقود', 'state': 'published'}, {'title': 'مراجعة عقود الإيجار', 'state': 'pending'}]
    m = d['money']
    assert m['pending'] == {'count': 1, 'amounts': [{'currency': 'EGP', 'amount': 1200.0}], 'partial': False}
    assert m['paid'] == {'count': 2, 'amounts': [{'currency': 'EGP', 'amount': 3350.5}], 'partial': False} and m['balance'] is None
    assert d['learner'] == {'enrollments_count': 0, 'reservations_count': 0} and d['books'] is None
    kinds = [x['kind'] for x in d['log']]
    assert {'login', 'file_assigned', 'payout_requested', 'payout_paid', 'invite_registered'} <= set(kinds)
    ats = [x['at'] for x in d['log']]
    assert ats == sorted(ats, reverse=True) and len(d['log']) == 12 and d['log_partial'] is False   # ١٥ حدثًا ⇒ أحدث ١٢ (الأقدم: إرسال الدعوة وفتحها)
    assert all(set(x) == {'at', 'kind', 'title'} for x in d['log'])


def test_person_as_learner_and_visitor_take_roles_from_facts_only(ctx, plat):
    d = _person(ctx, 'mona.s@example.test').get_json()
    assert d['learner'] == {'enrollments_count': 3, 'reservations_count': 1} and d['roles'] == ['learner']
    assert d['trainer'] is None and d['expert'] == {'files_count': 0, 'partial': False, 'latest': []}
    assert d['money']['pending']['count'] == 0 and d['money']['paid']['count'] == 0
    v = _person(ctx, 'nour.pending@example.test').get_json()
    assert v['roles'] == ['visitor'] and v['identity']['country'] == 'مصر'
    plain = _person(ctx, 'salma@example.test').get_json()
    assert plain['roles'] == ['member']


def test_person_not_found(ctx, plat):
    d = _person(ctx, 'nobody@example.test').get_json()
    assert d['found'] is False and d['identity'] is None and d['expert'] is d['trainer'] is d['money'] is d['learner'] is d['log'] is None
    assert d['email'] == 'nobody@example.test'


def test_person_email_is_case_insensitive_and_trimmed(ctx, plat):
    d = _person(ctx, raw='%20Hala%40EXAMPLE.test%20').get_json()
    assert d['found'] is True and d['email'] == HALA


SECTION_OF_SOURCE = {   # المسار ⇒ (القسم اللي لازم يتحوّل null · مفتاح حالة المصدر)
    '/api/bridge/experts': (('trainer',), 'experts'), '/api/bridge/courses': (('trainer',), 'courses'),
    '/api/bridge/expert-files': (('expert',), 'files'), '/api/bridge/invites': (('invited_by',), 'invites'),
    '/api/bridge/pending-users': (('country',), 'pending')}


@pytest.mark.parametrize('path', sorted(SECTION_OF_SOURCE))
def test_a_failed_source_turns_its_part_into_null_not_zero(ctx, plat, path):
    plat.ef.forced[('GET', path)] = (502, {'detail': 'down'})
    d = _person(ctx).get_json()
    sections, key = SECTION_OF_SOURCE[path]
    assert d['sources'][key] == 'failed'
    for s in sections:
        got = d['identity'].get(s) if s in ('invited_by', 'country') else d[s]
        if path == '/api/bridge/courses':       # عدّاد الدليل وصل: الأعداد بتفضل، والعناوين بس null
            assert d['trainer']['courses'] is None and d['trainer']['courses_count'] == 2
        elif path == '/api/bridge/experts':     # العناوين من الدورات بس ما بتتعرضش بدون عدّاد يوافقها
            assert d['trainer']['courses_count'] is None and d['trainer']['students_count'] is None and d['trainer']['courses'] is None
        else:
            assert got is None, (path, s, got)
    # الباقي سليم
    assert d['identity']['name'] == 'د. هالة سمير' and d['found'] is True
    if path != '/api/bridge/expert-files':
        assert d['expert']['files_count'] == 4


def test_failed_payout_sources_null_only_their_half(ctx, plat):
    plat.ef.forced[('GET', '/api/bridge/wallet-payouts')] = (500, {'detail': 'x'})
    d = _person(ctx).get_json()
    assert d['money'] is None and d['sources']['payouts_pending'] == d['sources']['payouts_paid'] == 'failed'
    assert d['log_partial'] is True and not any(e['kind'].startswith('payout') for e in d['log'])


def test_failed_enrollment_check_is_null_learner(ctx, plat):
    uid = 'u-hala'
    plat.ef.forced[('GET', '/api/bridge/users/%s/purge-check' % uid)] = (500, {'detail': 'x'})
    d = _person(ctx).get_json()
    assert d['learner'] is None and d['sources']['enrollments'] == 'failed' and d['expert']['files_count'] == 4


def test_failed_identity_source_nulls_everything_and_says_unknown(ctx, plat):
    plat.ef.forced[('GET', '/api/bridge/users')] = (502, {'detail': 'x'})
    d = _person(ctx).get_json()
    assert d['found'] is None and d['sources']['users'] == 'failed'
    assert d['identity'] is d['expert'] is d['trainer'] is d['money'] is d['learner'] is d['books'] is d['log'] is None and d['roles'] == []


def test_every_source_down_is_all_null(ctx, plat):
    for path in PERSON_PATHS:
        plat.ef.forced[('GET', path)] = (502, {'detail': 'x'})
    d = _person(ctx).get_json()
    assert d['found'] is None and d['identity'] is None and d['log'] is None
    assert [c for c in plat.seen if 'purge-check' in c['path']] == [], 'فحص الحساب يحتاج معرّفه: مفيش هوية ⇒ مفيش نداء'


def test_a_non_json_or_wrong_shape_source_counts_as_failed(ctx, plat):
    plat.ef.forced[('GET', '/api/bridge/experts')] = (200, 'نص مش JSON')
    plat.ef.forced[('GET', '/api/bridge/courses')] = (200, {'unexpected': 1})
    d = _person(ctx).get_json()
    assert d['trainer']['courses_count'] is None and d['trainer']['courses'] is None


def test_truncated_lists_are_flagged_partial(ctx, plat):
    base = plat.ef.handle('GET', '/api/bridge/expert-files', {'status': 'all'})[1]
    plat.ef.forced[('GET', '/api/bridge/expert-files')] = (200, dict(base, total=base['count'] + 50))
    plat.ef.person_paid = [dict(p, id='x%d' % i, user_email='someone%d@example.test' % i) for i, p in enumerate(plat.ef.person_paid * 150)]
    d = _person(ctx).get_json()
    assert d['expert']['partial'] is True
    assert d['money']['paid']['partial'] is True and d['money']['paid']['count'] == 0 and d['money']['pending']['partial'] is False


def test_no_email_but_the_requested_one_ever_leaves(ctx, plat):
    # الطقم فيه بريد داعٍ وعميل وخبراء… وعنوان ملف كاتبه بريدًا: ولا واحد منهم يخرج
    plat.ef.person_files[0]['title'] = 'تواصل مع victim@leak.test بخصوص الإخلاء'
    plat.ef.person_invites[0]['invited_by']['name'] = 'داعٍ <inviter@leak.test>'
    d = _person(ctx).get_json()
    text = json.dumps(d, ensure_ascii=False)
    found = set(re.findall(r'[^\s"\\<>]+@[^\s"\\<>]+\.[A-Za-z]+', text))
    assert found == {HALA}, found
    assert 'leak.test' not in text and '…' in text
    # حتى لما الشخص مش موجود: البريد المطلوب بس (مفيش بريد مخترع)
    nf = json.dumps(_person(ctx, 'nobody@example.test').get_json(), ensure_ascii=False)
    assert set(re.findall(r'[^\s"\\<>]+@[^\s"\\<>]+\.[A-Za-z]+', nf)) == {'nobody@example.test'}


def test_nothing_about_the_person_is_logged_or_audited(ctx, plat, caplog):
    import logging
    with flask_app.app_context():
        before = AuditLog.query.count()
    with caplog.at_level(logging.DEBUG):
        r = _person(ctx)
    assert r.status_code == 200
    with flask_app.app_context():
        assert AuditLog.query.count() == before, 'قراءة صفحة شخص ما بتتسجلش'
    blob = caplog.text
    for needle in (HALA, 'hala', 'هالة', 'victim'):
        assert needle not in blob, needle


def test_person_without_the_bridge_secret_is_503(ctx, monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    assert _person(ctx).status_code == 503


def test_person_build_is_pure_and_the_fake_platform_serves_the_new_sources():
    import app as appmod
    out = appmod._v2_person_build(HALA, {k: None for k in ('users', 'invites', 'experts', 'courses', 'files', 'payouts_pending', 'payouts_paid', 'pending', 'enrollments')})
    assert out['found'] is None and out['identity'] is None
    # `fake_platform.py` (الطقم المستقل للاختبارات القديمة) اتوسّع بالمصادر الجديدة وما غيّرش ردودها القديمة
    assert fp.person_response('/api/bridge/users', 'search=hala')['count'] == 1
    assert fp.person_response('/api/bridge/users', 'limit=500') is None
    assert fp.person_response('/api/bridge/expert-files', 'status=all')['files'][0]['expert_email'] == fp.PERSON_EMAIL
    assert fp.person_response('/api/bridge/expert-files', 'status=waiting') is None
    assert fp.person_response('/api/bridge/wallet-payouts', 'status=paid')['payouts'][0]['status'] == 'paid'
    assert fp.person_response('/api/bridge/wallet-payouts', 'status=pending') is None
    built = appmod._v2_person_build(HALA, {
        'users': {'users': [fp.PERSON_USER]}, 'invites': [], 'experts': None, 'courses': None, 'files': fp.PERSON_FILES,
        'payouts_pending': {'payouts': []}, 'payouts_paid': fp.PERSON_PAID, 'pending': {'users': []},
        'enrollments': {'purgeable': False, 'linked': fp.PERSON_LINKED['u-hala']}})
    assert built['found'] is True and built['expert']['files_count'] == 1 and built['learner']['enrollments_count'] == 3
    assert built['money']['paid']['amounts'] == [{'currency': 'EGP', 'amount': 950.5}] and built['trainer']['courses_count'] is None


# ---------------------------------------------------------------- ٦) الملفات والخطّافات والنصوص

def test_the_files_are_wired_and_shipped():
    html = _read('dashboard-cloud', 'index.html')
    assert '<link rel="stylesheet" href="v2-d2.css">' in html and '<script src="v2-d2.js"></script>' in html
    assert html.index('v2-shell.js') < html.index('v2-d2.js')
    for df in ('Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')):
        txt = _read(df)
        assert 'dashboard-cloud/v2-d2.js' in txt and 'dashboard-cloud/v2-d2.css' in txt
    for f in ('v2-d2.js', 'v2-d2.css'):
        assert os.path.getsize(os.path.join(DC, f)) > 3000


def test_the_hooks_do_nothing_when_the_switch_is_off():
    html = _read('dashboard-cloud', 'index.html')
    i = html.index("if(current==='home'&&window.V2_ON&&window.V2)return V2.render(v);")
    nxt = html[i:i + 400]
    assert "if(window.V2_ON&&window.V2D2&&V2D2.owns(current))return V2D2.render(current,v);" in nxt
    assert "ap.classList.toggle('v2-bare',current==='home'||!!(window.V2D2&&V2D2.owns(current)))" in html
    # اسم المستخدم في القائمة القديمة: المفتاح مقفول ⇒ نفس `esc(u.name)` بالحرف
    assert "${window.V2_ON&&window.V2D2?V2D2.link(u.name,u.email):esc(u.name)}" in html
    js = _read('dashboard-cloud', 'v2-d2.js')
    assert "if (!email || !window.V2_ON) return esc(name);" in js
    assert "!window.V2_ON) return;" in js                     # معالج النقر العام على الأسماء
    # الموديولات الوهمية ما لها تعريف في القائمة القديمة
    mods = html[html.index('const MODULES={'):html.index('// موديولات الأدوار غير-الأدمن')]
    for m in ('v2files', 'v2disputes', 'v2person'):
        assert m not in mods
    api = _read('dashboard-cloud', 'dashboard-api.js')
    assert 'V2D2' not in api and 'personEmail' in api


def test_the_minute_timer_and_the_poll_exist():
    js = _read('dashboard-cloud', 'v2-d2.js')
    assert re.search(r'S\.minute = setInterval\(.*?tick\(\).*?\}, 60000\)', js, re.S), 'عدّاد الدقيقة'
    assert 'D2._tick = tick' in js and 'nowOverride' in js
    assert 'document.body.contains(S.view)' in js, 'ردّ متأخر ما يرسمش فوق شاشة تانية'


def test_touch_targets_and_mobile_rules_are_in_the_css():
    css = _read('dashboard-cloud', 'v2-d2.css')
    assert re.search(r'\.v2d-btn1,\.v2d-btn2\{[^}]*min-height:48px', css)
    mob = css[css.index('@media(max-width:760px)'):]
    assert 'min-height:52px' in mob and '.v2d-seg{display:flex' in mob and 'grid-template-columns:minmax(0,1fr)' in mob
    for col in ('late', 'review', 'with', 'done', 'disputes', 'refunds', 'legacy'):
        assert 'data-active="%s"]' % col in mob
    assert '.v2d-segb{flex:1;min-width:0;min-height:60px' in css


BANNED_IN_D2 = ['بعدين', 'اقبله', 'افتح له', "'لديه ", 'تواصلت معه', 'إلى محفظته', 'عليه نزاع', 'ينشر اسمه', 'ليس لديه', 'أوقف مؤقتًا',
                'طابور', 'Backend', 'endpoint', 'JSON']
BANNED_WORDS_D2 = ['ملفاته', 'دوراته', 'فلوسه', 'راسله']     # ضمير الغائب المذكّر في عناوين الصفحة (الجنس مجهول) — ككلمة كاملة بس


def _strip_comments(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def test_visible_text_is_plain_neutral_and_never_starts_with_ai():
    logic = _read('dashboard-cloud', 'v2-logic.js')
    block = logic[logic.index('// ---- التذاكر') if '// ---- التذاكر' in logic else logic.index('التذاكر (D2)'):logic.index('خريطة الأقسام (D1-B)')]
    for name, src in (('v2-d2.js', _read('dashboard-cloud', 'v2-d2.js')), ('v2-logic D2 block', block)):
        code = _strip_comments(src)
        for bad in BANNED_IN_D2:
            assert bad not in code, (name, bad)
        for w in BANNED_WORDS_D2:
            assert not re.search(r'(?<![\u0600-\u06FF])%s(?![\u0600-\u06FF])' % w, code), (name, w)


@needs_node
def test_rendered_texts_are_clean_and_no_headline_starts_with_ai(real):
    T = _tickets(real, autoAssign=True, brainToday=2)
    D = _dispute_tickets(real)
    texts = []
    for X in (T, D):
        for c in X['cols']:
            for t in X['cols'][c]:
                texts += [t['strip']['label'], t['brain'] if 'brain' in t else '', t.get('reason', ''), t['primary']['label'], t.get('text', '')]
    texts += [T['header']] + [v2_node.logic('v2Person', FULL, NOW, HALA)['joinLine']]
    labels = v2_node.logic('COL_LABEL')
    texts += list(labels.values())
    joined = ' | '.join(x for x in texts if x)
    for w in ('بعدين', 'مستني', 'مالوش', 'بإيدك', 'الفلوس واقفة', 'اتبعت', 'ما اتستلمش'):
        assert w not in joined, w
    for t in texts:
        assert not re.match(r'^\s*(AI|ai|ذكاء|الذكاء)', t or ''), t
    for t in [c['title'] for c in v2_node.logic('v2Person', FULL, NOW, HALA)['cards']]:
        assert not re.match(r'^\s*(AI|ذكاء|الذكاء)', t)
    # لا مصطلح تقني ولا أرقام لاتينية في نصوص التذاكر (إلا داخل بريد)
    assert not re.search(r'[A-Za-z]', joined)



# ---------------------------------------------------------------- مراجعة D2: إصلاحات

@needs_node
def test_review_fix_copy_is_gender_neutral_and_the_approval_is_the_founders(real):
    T = _tickets(real)
    texts = []
    for c in T['cols']:
        for t in T['cols'][c]:
            texts += [t['brain'], t.get('reason', ''), t['strip']['label']]
    j = ' | '.join(texts)
    for bad in ('يستلمه', 'اعتمدت', 'يعمل عليه'):
        assert bad not in j, bad
    assert 'لم يُستلم لدى ' in j and 'اعتُمد الرأي' in j
    src = _read('dashboard-cloud', 'v2-logic.js')
    assert 'ولم يستلمه' not in src and 'لم يستلمه' not in src and 'اعتمدت الرأي' not in src


@needs_node
def test_review_fix_the_done_column_is_named_for_what_it_can_see():
    assert v2_node.logic('COL_LABEL')['done'] == 'اعتُمد اليوم'
    js = _read('dashboard-cloud', 'v2-d2.js')
    assert 'لا شيء بعد اليوم' not in js and 'لا رأي معتمد اليوم' in js


@needs_node
def test_review_fix_the_with_column_says_it_counts_only_sent_and_not_received(real):
    T = _tickets(real)
    assert 'أُرسل ولم يُستلم' in T['notes']['with']
    js = _read('dashboard-cloud', 'v2-d2.js')
    assert "(c === 'with' ? '' : ' — العدد ناقص')" in js


@needs_node
def test_review_fix_a_missing_manual_refunds_key_is_unknown_not_zero(real):
    q = dict(real['data']['opsQueue']); q.pop('manual_refunds_pending', None)
    D = v2_node.logic('v2DisputeTickets', [r for r in real['inbox'] if not r.get('fyi')], {'now': NOW, 'queue': q})
    assert D['manualRefunds'] is None and D['counts']['refunds'] == 2


@needs_node
def test_review_fix_a_future_deadline_is_never_printed_as_lateness():
    # ساعة الجهاز متأخرة عن الخادم: الموعد في المستقبل لكن الوضع «متأخر» ⇒ نكتب «متأخر» بلا مدة.
    assert v2_node.logic('v2TimerText', {'mode': 'over', 'at': NOW + 5 * 3600e3}, NOW) == 'متأخر'
    assert v2_node.logic('v2TimerText', {'mode': 'over', 'at': NOW - 3 * 3600e3 - 1000}, NOW) == 'متأخر ٣ س'


def test_review_fix_a_ticket_without_a_deadline_has_no_empty_pill():
    js = _read('dashboard-cloud', 'v2-d2.js')
    assert "(t.text ? '<time class=\"v2d-time" in js


@needs_node
def test_review_fix_odd_file_statuses_land_where_they_belong():
    def row(i, st, **extra):
        ef = {'id': i, 'status': st, 'title': 'ملف ' + i, 'assigned_to': 'a@b.test', 'assigned_name': 'أ. فلان'}
        ef.update(extra)
        return {'apiKind': 'expert_file', 'apiId': i, 'efLane': 'waiting', 'who': 'منى', 'ef': ef}
    past = datetime.datetime.utcfromtimestamp((NOW - 30 * 3600e3) / 1000).isoformat() + 'Z'
    rows = [row('d1', 'delivered', delivered_at=past), row('c1', 'closed', closed_at=past), row('n1', 'needs_info', claim_deadline_at=past)]
    T = v2_node.logic('v2Tickets', rows, {'now': NOW})
    assert T['total'] == 3
    by = {t['row']['apiId']: (c, t) for c in T['cols'] for t in T['cols'][c]}
    for i in ('d1', 'c1'):
        c, t = by[i]
        assert c == 'review' and t['strip']['label'] in ('سُلّم', 'مغلق') and t['brain'] == 'لا قرار مطلوب' and t['primary']['act']['do'] == 'open'
    c, t = by['n1']
    assert c == 'with' and t['strip']['label'] == 'عند الخبير' and t['brain'] == 'بانتظار إجابة صاحب الطلب'


def test_review_fix_empty_columns_stay_selectable_and_disputes_tick():
    js = _read('dashboard-cloud', 'v2-d2.js')
    assert 'picked: { files: false, disputes: false }' in js
    assert '(!S.picked.files && !T.counts[active])' in js and '(!S.picked.disputes && !T.counts[active])' in js
    assert "S.picked[board] = true" in js
    assert 'function tickDisputes' in js and "isCurrent('v2disputes')" in js


def test_review_fix_slim_cards_and_one_brain_line():
    js = _read('dashboard-cloud', 'v2-d2.js')
    assert "t.col === 'with' || t.col === 'done'" in js
    assert 'v2d-why' not in js and "esc(t.reason)" in js    # الإيضاح الثاني اتشال من تذاكر الملفات؛ سبب النزاع بس لسه ظاهر في اللوحة التانية


def test_review_fix_css_contrast_touch_and_scope():
    css = _read('dashboard-cloud', 'v2-d2.css')
    assert '.v2d-t.tone-wait .v2d-strip{background:#8F5F00}' in css and '.v2d-t.tone-done .v2d-strip{background:#6F6A5F}' in css
    assert re.search(r'\.v2d-inline\{[^}]*min-height:44px', css)
    assert not re.search(r'(^|\n)\.center\{', css) and '.v2d .center{' in css


def test_review_fix_a_full_invite_or_pending_list_without_a_match_is_partial_not_empty():
    import app as appmod
    base = {k: None for k in ('users', 'invites', 'experts', 'courses', 'files', 'payouts_pending', 'payouts_paid', 'pending', 'enrollments')}
    user = {'email': HALA, 'full_name': 'هالة سمير', 'id': 'u1', 'created_at': '2026-01-01T00:00:00Z', 'is_active': True, 'role': 'user'}
    many = [{'email': 'x%d@example.test' % i, 'created_at': '2026-02-01T00:00:00Z'} for i in range(500)]
    out = appmod._v2_person_build(HALA, dict(base, users={'users': [user]}, invites={'invites': many}, pending={'users': many}))
    assert out['sources']['invites'] == 'partial' and out['sources']['pending'] == 'partial'
    assert out['identity']['invited_by'] is None and out['roles'] == []
    short = appmod._v2_person_build(HALA, dict(base, users={'users': [user]}, invites={'invites': many[:3]}, pending={'users': many[:3]}))
    assert short['sources']['invites'] == 'ok' and short['sources']['pending'] == 'ok' and short['roles'] == ['member']


@needs_node
def test_review_fix_a_partial_invite_source_prints_inviter_unavailable():
    resp = copy.deepcopy(FULL)
    resp['identity']['invited_by'] = None
    resp['sources'] = dict(resp.get('sources') or {}, invites='partial')
    assert 'الداعي: غير متاح بعد' in v2_node.logic('v2Person', resp, NOW, HALA)['joinLine']
