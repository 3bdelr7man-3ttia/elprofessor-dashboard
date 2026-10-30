# -*- coding: utf-8 -*-
"""«الناس والدعوات» (نهائي) — الطلبات · الدعوات · المستخدمون · الرسائل بالشكل الجديد، ورا نفس المفتاح المقفول.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_people.py

⛔ صفر شبكة حقيقية: المنطق النقي (`V2L.v2p`) بيتشغّل في node، والمنصة جدول في الذاكرة (`uiharness/people_fixtures.PeoplePlatform`)، وأي عنوان برّه
`https://platform.test` بيوقّع الاختبار. اللقطات في `uiharness/v2_shots_people.py`.

اللي بيثبّته:
  ١. الخريطة والعناوين (التبويبات بالنص، والروابط القديمة تهبط في مكانها).
  ٢. `requests` (أعمدة · العمود المختلط · نصوص التذاكر = `v2Card` بالحرف · قاعدة رابط الاسم · سطر العقل B1 وB1-g).
  ٣. `pipeline` (أعمدة المحطات · أرقام بلا اختلاق · نسب · مدخل «الداعي» · «انضمّ» آخر ٧ أيام).
  ٤. `users` (شرائح بأرقام صادقة · بحث · فلتر · حارس آخر إدارة) و`messages` (أسماء حقول المنصة · أقدم أولًا · أكثر من يوم).
  ٥. النصوص (فصحى بلا «يقوّم» ولا عامية ولا لاتيني) والإجراءات (كل مسار موجود في الداشبورد، بلا prompt/confirm/alert، وكل كتابة عبر PX.call).
  ٦. Flask: كل كتابة بتوصل المنصة بنفس المسار والجسم، والرد بالبريد ما بيبعتش بريد.
  ٧. الربط: كتلة index.html · سطر التوجيه · المفتاح مقفول ⇒ الشاشات القديمة بالحرف · لا مسار خادم جديد · زرّ «إدارة الحساب» من صفحة الشخص بس.
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, Message  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import people_fixtures as pf   # noqa: E402
import v2_node                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
DC = os.path.join(ROOT, 'dashboard-cloud')
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NODE = v2_node.NODE
needs_node = pytest.mark.skipif(not NODE, reason='needs node')
NOW = int(time.time() * 1000)
H = 3600e3


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


PEOPLE_JS = _read('dashboard-cloud', 'v2s', 'people.js')
PEOPLE_CSS = _read('dashboard-cloud', 'v2s', 'people.css')
LOGIC = _read('dashboard-cloud', 'v2-logic.js')
INDEX = _read('dashboard-cloud', 'index.html')
API_JS = _read('dashboard-cloud', 'dashboard-api.js')
BLOCK = LOGIC[LOGIC.index('// ===== v2s:people ====='):LOGIC.index('// ===== /v2s:people =====')]


def _node(js):
    script = "const L=require(%s);\n%s" % (json.dumps(os.path.join(DC, 'v2-logic.js')), js)
    p = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


def v2p(fn, *args):
    return v2_node.logic('v2p.' + fn, *args)


def ago(hours):
    return NOW - hours * H


# ---------------------------------------------------------------- صفوف جاهزة (بأشكال الداشبورد بعد المحمّلات)
def visitor(i='pu-1', who='نور', email='nour@x.test', hours=3, flags=None, country='مصر', role='محامٍ'):
    return {'apiKind': 'pending_user', 'apiId': i, 'ref': 'PU-' + i, 'who': who, 'personEmail': email, 'email': email, 'ts': ago(hours), 'puCountry': country, 'puRole': role,
            'flagLabels': flags or [], 'details': [{'k': 'الإيميل', 'v': email}]}


def join(i='jr-1', who='مها', email='maha@x.test', hours=20, licence_missing=False, info=''):
    return {'apiKind': 'join', 'apiId': i, 'ref': 'JR-' + i, 'who': who, 'personEmail': email, 'email': email, 'ts': ago(hours), 'serviceLabel': 'مراجعة العقود', 'licensed': True,
            'licenceMissing': licence_missing, 'licenceNote': '', 'infoRequest': info, 'attachments': [], 'details': []}


def founding(i='fl-1', who='ثابت', email='thabit@x.test', hours=30, nxt='contacted', wa='+970599000000'):
    return {'apiKind': 'founding', 'apiId': i, 'ref': 'FND-' + i, 'who': who, 'personEmail': email, 'email': email, 'ts': ago(hours), 'fSpec': 'تحكيم', 'fCountry': 'فلسطين',
            'note': 'التخصّص: تحكيم · الخبرة: ١٥ — كلّمه على واتساب، وعلّم الخطوة من هنا.', 'nextStatus': nxt,
            'details': ([{'k': 'واتساب', 'v': wa}] if wa else []) + [{'k': 'الخبرة', 'v': '١٥'}]}


def inv(i, stage='pending', hours=5, **kw):
    row = {'id': i, 'name': kw.pop('name', 'مدعو ' + i), 'email': kw.pop('email', ''), 'status': kw.pop('status', stage), 'stage': stage, 'at': ago(hours), 'link': kw.pop('link', 'https://l.test/' + i),
           'opened': stage in ('opened', 'roles_chosen', 'pain_seen', 'exercised', 'declared', 'registered'), 'registered': stage == 'registered', 'revoked': stage == 'revoked', 'invitedByLabel': kw.pop('by', 'المؤسس'),
           'invitedByUserId': kw.pop('uid', ''), 'generation': kw.pop('generation', 1), 'rolesLabel': '—', 'specialtyLabel': '—', 'note': '', 'approvalNote': '', 'docRequested': False,
           'expiresAt': kw.pop('exp', None)}
    row.update(kw)
    return row


def wl(i, name='طالبة', hours=10, status='new', phone='+201001234567'):
    return {'id': i, 'name': name, 'email': i + '@x.test', 'phone': phone, 'note': 'سبب', 'roleLabel': 'محامٍ', 'specialtyLabel': '—', 'countryLabel': 'مصر', 'status': status, 'at': ago(hours)}


def pu(i, requested=False, **kw):
    r = {'id': i, 'name': 'زائر ' + i, 'email': i + '@x.test', 'requested': requested, 'rejected': False, 'at': ago(5), 'lastLogin': '', 'aiUsed': None}
    r.update(kw)
    return r


def inp(**kw):
    base = {'inbox': [], 'inboxState': 'ready', 'failed': [], 'trunc': [], 'invites': {'rows': [], 'count': 0, 'missing': False, 'counts': None}, 'invitesState': 'ready',
            'waitlist': {'rows': [], 'count': 0, 'missing': False}, 'waitlistState': 'ready', 'pending': {'rows': [], 'count': 0, 'missing': False}, 'pendingState': 'ready',
            'settings': None, 'userEmails': []}
    base.update(kw)
    return base


# ================================================================ ١) الخريطة والعناوين
@needs_node
def test_the_people_tabs_match_the_spec_exactly():
    tabs = _node("console.log(JSON.stringify(L.sectionByKey('people').tabs.map(t=>[t.key,t.label,t.mod,t.st,!!t.hidden])))")
    assert tabs == [['invites', 'الطلبات', 'invites', {}, False], ['pipeline', 'الدعوات', 'v2p_invites', {}, False], ['users', 'المستخدمون', 'users', {}, False],
                    ['messages', 'الرسائل', 'inbox', {'activeFilter': 't:messages'}, False], ['person', 'صفحة الشخص', 'v2person', {}, True]]
    sec = _node("console.log(JSON.stringify(L.sectionByKey('people')))")
    assert sec['label'] == 'الناس والدعوات' and sec['img'] == 'people'


@needs_node
def test_old_links_and_addresses_still_land_where_they_did():
    r = _node("""console.log(JSON.stringify([L.routeFor('#invites'),L.routeFor('#users'),L.routeFor('#messages'),L.sectionFor('inbox',{activeFilter:'t:messages'}),
      L.sectionFor('v2p_invites'),L.routeFor('#s/people/pipeline'),L.parseSectionHash('#s/people/pipeline'),L.ALIASES]))""")
    assert (r[0]['section'], r[0]['tab']) == ('people', 'invites')
    assert (r[1]['section'], r[1]['tab']) == ('people', 'users')
    assert (r[2]['section'], r[2]['tab']) == ('people', 'messages') and r[2]['st'] == {'activeFilter': 't:messages'}
    assert (r[3]['section'], r[3]['tab']) == ('people', 'messages')
    assert (r[4]['section'], r[4]['tab']) == ('people', 'pipeline')
    assert (r[5]['section'], r[5]['tab']) == ('people', 'pipeline') and r[6] == {'section': 'people', 'tab': 'pipeline', 'exact': True}
    assert set(r[7]) == {'overview', 'messages', 'packages', 'tutorials', 'partners', 'foundation'}


# ================================================================ ٢) الطلبات
@needs_node
def test_each_kind_lands_in_its_column_and_the_not_requested_visitor_never_becomes_a_ticket():
    R = v2p('requests', inp(inbox=[visitor('pu-1'), join(), founding()], invites={'rows': [inv('i1', 'awaiting_approval', status='awaiting_approval', by='منى', uid='u1', generation=2)], 'count': 1},
                           waitlist={'rows': [wl('w1'), wl('w2', status='invited')], 'count': 2}, pending={'rows': [pu('p1', True), pu('p2'), pu('p3', rejected=True, requestStatus='rejected')], 'count': 3}), NOW)
    c = R['cols']
    assert [t['kind'] for t in c['visitors']['items']] == ['waitlist', 'visitor'] or sorted(t['kind'] for t in c['visitors']['items']) == ['visitor', 'waitlist']
    assert len(c['approval']['items']) == 1 and len(c['join']['items']) == 1 and len(c['founding']['items']) == 1
    assert [x['count'] for x in (c['visitors'], c['approval'], c['join'], c['founding'])] == [2, 1, 1, 1]
    assert [r['id'] for r in R['later']['rows']] == ['p2', 'p3'] and R['later']['total'] == 3
    assert all(t['kind'] != 'visitor' or t['ref']['apiId'] == 'pu-1' for t in c['visitors']['items'])


@needs_node
def test_ticket_buttons_follow_the_spec():
    R = v2p('requests', inp(inbox=[visitor('pu-1'), visitor('pu-2', flags=['إيميل بنقط']), join('jr-1'), join('jr-2', licence_missing=True, info='أرسل رقم القيد'), founding(), founding('fl-2', wa='')],
                           invites={'rows': [inv('i1', 'awaiting_approval', status='awaiting_approval')], 'count': 1}, waitlist={'rows': [wl('w1')], 'count': 1}), NOW)
    vis = {t['id']: t for t in R['cols']['visitors']['items']}
    assert vis['visitor:pu-1']['primary'] == {'label': 'افتح المنصة للزائر', 'act': {'do': 'decide', 'action': 'approve'}}
    assert vis['visitor:pu-2']['primary'] == {'label': 'افتح وراجع', 'act': {'do': 'sheet', 'sheet': 'visitor'}} and vis['visitor:pu-2']['warn'] == 'يحتاج مراجعة: إيميل بنقط'
    assert vis['waitlist:w1']['primary']['label'] == 'أرسل دعوة' and vis['waitlist:w1']['secondary'][0]['label'] == 'التفاصيل'
    assert vis['waitlist:w1']['brain'] == 'طلب دعوة من الموقع ولا يملك حسابًا بعد' and vis['waitlist:w1']['extra'] == ['سبب الطلب: سبب']
    ap = R['cols']['approval']['items'][0]
    assert ap['primary']['label'] == 'وافق على الدعوة' and ap['secondary'][0]['label'] == 'ارفض' and ap['brain'] == 'تحتاج موافقتك قبل أن يعمل رابطها'
    j = {t['id']: t for t in R['cols']['join']['items']}
    assert j['join:jr-1']['primary']['label'] == 'اقبل' and [s['label'] for s in j['join:jr-1']['secondary']] == ['ارفض', 'اطلب استكمالًا']
    assert j['join:jr-2']['primary'] == {'label': 'افتح وراجع', 'act': {'do': 'sheet', 'sheet': 'join'}} and j['join:jr-2']['extra'] == ['طُلب من صاحب الطلب: أرسل رقم القيد — بانتظار رده']
    f = {t['id']: t for t in R['cols']['founding']['items']}
    assert f['founding:fl-1']['primary']['label'] == 'تم التواصل' and f['founding:fl-1']['secondary'][0] == {'label': 'واتساب', 'act': {'do': 'link', 'url': 'https://wa.me/970599000000'}}
    assert [s['label'] for s in f['founding:fl-2']['secondary']] == ['ليس مناسبًا']          # بلا رقم صالح ⇒ لا زرّ واتساب


@needs_node
def test_the_founding_primary_label_follows_next_status():
    for nxt, label in (('contacted', 'تم التواصل'), ('invited', 'أُرسلت الدعوة'), ('converted', 'تم التحويل إلى مدرّب')):
        R = v2p('requests', inp(inbox=[founding(nxt=nxt)]), NOW)
        assert R['cols']['founding']['items'][0]['primary']['label'] == label


@needs_node
def test_inbox_ticket_text_is_v2Card_field_by_field_and_never_says_mashbooh():
    rows = [visitor('pu-1'), visitor('pu-2', flags=['إيميل بنقط', 'اسم عشوائي']), join('jr-1'), join('jr-2', licence_missing=True), founding()]
    R = v2p('requests', inp(inbox=rows), NOW)
    tickets = {t['ref']['apiId']: t for k in ('visitors', 'join', 'founding') for t in R['cols'][k]['items']}
    for row in rows:
        card = v2_node.logic('v2Card', row, {'now': NOW})
        t = tickets[row['apiId']]
        assert (t['tag'], t['title'], t['brain'], t['reason'], t['warn'], t['primary']['label']) == (card['tag'], card['title'], card['brain'], card['reason'], card['warn'], card['primary']['label']), row['apiId']
        if row['apiKind'] != 'founding':
            assert t['sub'] == card['sub'], row['apiId']
    # «ليدات المؤسسين»: نص الملاحظة القديم عامي («كلّمه على…») فلا يُعرض، وتبقى الخبرة وحدها
    assert tickets['fl-1']['sub'] == 'الخبرة: ١٥'
    assert all('كلّمه' not in json.dumps({k: v for k, v in t.items() if k != 'ref'}, ensure_ascii=False) for t in R['cols']['founding']['items'])
    for col in R['cols'].values():
        for t in col['items']:
            assert 'مشبوه' not in json.dumps(t, ensure_ascii=False)
    assert tickets['pu-2']['warn'] == 'يحتاج مراجعة: إيميل بنقط · اسم عشوائي'


@needs_node
def test_a_failed_source_is_failed_not_zero_and_the_head_names_it():
    R = v2p('requests', inp(inbox=None, inboxState='error', waitlist=None, waitlistState='error'), NOW)
    for k in ('visitors', 'join', 'founding'):
        c = R['cols'][k]
        assert c['state'] == 'failed' and c['count'] is None and c['countText'] == '—' and c['items'] == [], k
    assert set(R['head']['failedLabels']) == {'الزوّار', 'قائمة الانتظار', 'طلبات تقديم الخدمة', 'الخبراء المؤسسون'}
    R = v2p('requests', inp(inbox=[visitor()], failed=['طلبات تقديم الخدمة']), NOW)
    assert R['cols']['join']['state'] == 'failed' and R['cols']['join']['count'] is None and R['cols']['visitors']['state'] == 'ready'
    assert 'تعذّر جلب: طلبات تقديم الخدمة' in R['head']['text'] and 'لا أحد ينتظر' not in R['head']['text']
    R = v2p('requests', inp(invites=None, invitesState='error'), NOW)
    assert R['cols']['approval']['state'] == 'failed' and R['cols']['approval']['count'] is None and R['cols']['approval']['retry'] == [{'key': 'invites', 'label': 'الدعوات'}]
    R = v2p('requests', inp(invites={'rows': [], 'count': 0, 'missing': True}), NOW)
    assert R['cols']['approval']['state'] == 'missing' and R['cols']['approval']['count'] is None


@needs_node
def test_column_one_is_mixed_when_only_one_of_its_two_sources_arrived():
    rows = [visitor('pu-1'), visitor('pu-2'), visitor('pu-3')]
    R = v2p('requests', inp(inbox=rows, waitlist=None, waitlistState='error'), NOW)
    c = R['cols']['visitors']
    assert c['state'] == 'mixed' and c['count'] == 3 and c['countText'] == '٣+؟' and c['retry'] == [{'key': 'waitlist', 'label': 'قائمة الانتظار'}] and len(c['items']) == 3
    assert 'قائمة الانتظار' in R['head']['failedLabels']
    R = v2p('requests', inp(inbox=[], failed=['زوّار ينتظرون الفتح'], waitlist={'rows': [wl('w1'), wl('w2')], 'count': 2}), NOW)
    c = R['cols']['visitors']
    assert c['state'] == 'mixed' and c['countText'] == '٢+؟' and c['retry'] == [{'key': 'inbox', 'label': 'الزوّار'}] and 'الزوّار' in R['head']['failedLabels']
    R = v2p('requests', inp(inbox=rows, waitlist={'rows': [], 'count': 0, 'missing': True}), NOW)
    c = R['cols']['visitors']
    assert c['state'] == 'mixed' and c['retry'][0].get('missing') is True and 'قائمة الانتظار' in R['head']['failedLabels']
    R = v2p('requests', inp(inbox=None, inboxState='error', waitlist=None, waitlistState='error'), NOW)
    assert R['cols']['visitors']['state'] == 'failed' and R['cols']['visitors']['countText'] == '—'


@needs_node
def test_truncated_inbox_sources_are_partial():
    R = v2p('requests', inp(inbox=[join()], trunc=['طلبات تقديم الخدمة: معروض ٢٥ من ٣٠']), NOW)
    assert R['cols']['join']['partial'] is True and R['cols']['founding']['partial'] is False


@needs_node
def test_title_link_rule_only_for_people_with_an_account():
    R = v2p('requests', inp(inbox=[visitor('pu-1', email='Nour@X.test'), join(), founding('fl-1', email='has@x.test'), founding('fl-2', email='none@x.test')],
                           waitlist={'rows': [wl('w1')], 'count': 1}, invites={'rows': [inv('i1', 'awaiting_approval', status='awaiting_approval')], 'count': 1}, userEmails=['has@x.test']), NOW)
    by = {t['id']: t for k in R['cols'] for t in R['cols'][k]['items']}
    assert by['waitlist:w1']['link'] is None and by['invite:i1']['link'] is None
    assert by['visitor:pu-1']['link'] == 'nour@x.test' and by['join:jr-1']['link'] == 'maha@x.test'
    assert by['founding:fl-1']['link'] == 'has@x.test' and by['founding:fl-2']['link'] is None


@needs_node
def test_the_head_line_B1_and_the_pipeline_pointer_B1g():
    R = v2p('requests', inp(inbox=[visitor('pu-1', hours=26), join()], waitlist={'rows': [wl('w1')], 'count': 1}), NOW)
    assert R['head']['text'] == 'ينتظر قرارك ٣: زائر واحد ينتظر الفتح، واحد من قائمة الانتظار، طلب تقديم خدمة واحد. أقدمها منذ يوم.' or R['head']['text'].startswith('ينتظر قرارك ٣: ')
    R = v2p('requests', inp(), NOW)
    assert R['head']['text'] == 'لا أحد ينتظر قرارك الآن.' and R['head']['invitesLine'] is None
    rows = [inv('a', 'opened', hours=80, exp=NOW + 100 * H), inv('b', 'declared', hours=90, exp=NOW + 100 * H), inv('c', 'pending', hours=5, exp=NOW + 30 * H)]
    R = v2p('requests', inp(invites={'rows': rows, 'count': 3}), NOW)
    ln = R['head']['invitesLine']
    assert ln['href'] == '#s/people/pipeline' and 'دعوتان متوقفتان' in ln['text'] and 'دعوة واحدة تنتهي مهلتها قريبًا' in ln['text'] and '«الدعوات»' in ln['text']
    R = v2p('requests', inp(invites={'rows': rows[:2], 'count': 2}), NOW)
    assert 'تنتهي' not in R['head']['invitesLine']['text']
    R = v2p('requests', inp(invites=None, invitesState='error'), NOW)
    assert R['head']['invitesLine'] is None


# ================================================================ ٣) الدعوات
@needs_node
def test_every_stage_lands_in_its_column_and_awaiting_is_not_on_the_board():
    rows = [inv('w', 'pending'), inv('o', 'opened'), inv('r', 'roles_chosen'), inv('p', 'pain_seen'), inv('e', 'exercised'), inv('d', 'declared'), inv('j', 'registered', email='j@x.test', registeredAt=ago(48)),
            inv('x', 'expired'), inv('v', 'revoked'), inv('n', 'rejected', status='rejected', approvalNote='الاسم ناقص'), inv('a', 'awaiting_approval', status='awaiting_approval')]
    P = v2p('pipeline', {'rows': rows, 'count': len(rows), 'counts': {'opened': 7, 'roles_chosen': 4, 'exercised': 3, 'declared': 2, 'registered': 1}}, 'ready', NOW, '')
    ids = lambda c: sorted(t['id'] for t in P['cols'][c]['items'])
    assert ids('waiting') == ['w'] and ids('journey') == ['d', 'e', 'o', 'p', 'r'] and ids('joined') == ['j'] and ids('stopped') == ['n', 'v', 'x']
    assert P['cards'] == {'sent': 9, 'opened': 6, 'joined': 1, 'awaiting': 1}            # أُرسلت = الكل − تنتظر − مرفوضة
    assert P['pct'] == {'opened': '٦٧٪ مما أُرسل', 'joined': '١١٪ مما أُرسل'}
    assert [(s['key'], s['n']) for s in P['steps']] == [('roles_chosen', 4), ('exercised', 3), ('declared', 2)]
    rej = [t for t in P['cols']['stopped']['items'] if t['id'] == 'n'][0]
    assert rej['strip'] == 'رُفضت' and rej['teamNote'] == 'ملاحظة الفريق: الاسم ناقص' and rej['primary']['label'] == 'أعِد إصدارها'
    w = P['cols']['waiting']['items'][0]
    assert w['primary']['label'] == 'انسخ الرابط' and [s['label'] for s in w['secondary']] == ['أرسل عبر واتساب', 'اسحب الدعوة']
    j = P['cols']['journey']['items'][0]
    assert j['primary']['label'] == 'ذكّر عبر واتساب'
    P2 = v2p('pipeline', {'rows': [inv('w', 'pending', link='')], 'count': 1, 'counts': None}, 'ready', NOW, '')
    assert P2['cols']['waiting']['items'][0]['primary'] == {'label': 'الرابط غير متاح من المنصة', 'act': {'do': 'none'}, 'disabled': True}


@needs_node
def test_unknown_numbers_are_null_never_zero():
    for state, data in (('error', None), ('ready', {'rows': [], 'count': 0, 'missing': True, 'counts': None})):
        P = v2p('pipeline', data, state, NOW, '')
        assert P['state'] in ('failed', 'missing') and all(v is None for v in P['cards'].values()) and all(s['n'] is None for s in P['steps'])
    P = v2p('pipeline', {'rows': [inv('a', 'opened')], 'count': 1, 'counts': None}, 'ready', NOW, '')
    assert all(s['n'] is None for s in P['steps']) and P['cards']['sent'] == 1
    P = v2p('pipeline', {'rows': [], 'count': 0, 'counts': None}, 'ready', NOW, '')
    assert P['cards']['sent'] == 0 and P['pct'] == {'opened': None, 'joined': None}


@needs_node
def test_partial_stalled_and_expiring_thresholds_are_exact():
    rows = [inv('a%d' % i, 'opened', hours=5) for i in range(2)]
    P = v2p('pipeline', {'rows': rows, 'count': 40, 'counts': None}, 'ready', NOW, '')
    assert P['partial'] == {'shown': 2, 'total': 40}
    edge = [inv('s1', 'opened', hours=72, exp=NOW + 100 * H), inv('s2', 'opened', hours=72.01, exp=NOW + 100 * H), inv('e1', 'pending', hours=1, exp=NOW + 48 * H), inv('e2', 'pending', hours=1, exp=NOW + 48.01 * H),
            inv('e3', 'pending', hours=1, exp=NOW - 1 * H)]
    P = v2p('pipeline', {'rows': edge, 'count': 5, 'counts': None}, 'ready', NOW, '')
    assert P['stalled'] == 1 and P['expiring'] == 1
    assert any('دعوة واحدة فُتحت ولم تكتمل' in b for b in P['brain']) and any('دعوة واحدة تنتهي مهلتها خلال يومين' in b for b in P['brain'])
    assert P['brain'][0] == 'أُرسلت ٥، فُتح منها ٢ وانضمّ ٠.'


@needs_node
def test_inviter_key_and_the_inviter_filter_changes_columns_not_cards():
    keys = v2p_many([inv('a', uid='u7'), inv('b', uid='', generation=0, by='—'), inv('c', uid='', generation=None, by='—'), inv('d', uid='', generation=2, by='—'), inv('e', uid='', generation=1)])
    assert keys == ['u:u7', 'founder', 'founder', 'none', 'founder']          # الجيل ١ بلا معرّف ومسمّى «المؤسس» ⇒ المؤسس
    rows = [inv('a', 'pending', uid='u7', by='منى'), inv('b', 'pending', uid='u7', by='منى'), inv('c', 'opened', uid=''), inv('d', 'pending', uid='', generation=2, by='—')]
    P = v2p('pipeline', {'rows': rows, 'count': 4, 'counts': None}, 'ready', NOW, '')
    assert [i['label'] for i in P['inviters']] == ['كل الداعين (٤)', 'المؤسس (١)', 'منى (٢)', 'بلا داعٍ محدد (١)']
    P2 = v2p('pipeline', {'rows': rows, 'count': 4, 'counts': None}, 'ready', NOW, 'u:u7')
    assert P2['cards'] == P['cards'] and len(P2['cols']['waiting']['items']) == 2 and len(P2['cols']['journey']['items']) == 0
    P3 = v2p('pipeline', {'rows': rows, 'count': 4, 'counts': None}, 'ready', NOW, 'none')
    assert [t['id'] for t in P3['cols']['waiting']['items']] == ['d']


def v2p_many(rows):
    return _node("console.log(JSON.stringify(%s.map(r=>L.v2p.inviterKey(r))))" % json.dumps(rows))


@needs_node
def test_joined_column_holds_only_the_last_seven_days_while_the_card_counts_everyone():
    rows = [inv('new', 'registered', email='a@x.test', registeredAt=ago(48)), inv('old', 'registered', email='b@x.test', registeredAt=ago(8 * 24)), inv('fallback', 'registered', hours=24)]
    P = v2p('pipeline', {'rows': rows, 'count': 3, 'counts': None}, 'ready', NOW, '')
    assert P['cards']['joined'] == 3 and P['cols']['joined']['total'] == 3
    assert sorted(t['id'] for t in P['cols']['joined']['items']) == ['fallback', 'new'] and len(P['cols']['joined']['all']) == 3
    new = [t for t in P['cols']['joined']['items'] if t['id'] == 'new'][0]
    assert new['person'] == 'a@x.test' and new['primary']['label'] == 'افتح صفحة الشخص'
    fb = [t for t in P['cols']['joined']['items'] if t['id'] == 'fallback'][0]
    assert fb['person'] is None and fb['primary']['label'] == 'التفاصيل'


# ================================================================ ٤) المستخدمون
def U(uid, name, email, **kw):
    r = {'id': uid, 'full_name': name, 'email': email, 'phone': kw.pop('phone', ''), 'role': kw.pop('role', 'member'), 'trainer_status': kw.pop('trainer', 'none'), 'plan_id': kw.pop('plan', 'free'),
         'is_active': kw.pop('active', True), 'created_at': pf.iso(kw.pop('joined', -100)), 'last_login_at': kw.pop('login', pf.iso(-5)), 'segment': kw.pop('seg', ''), 'tags': kw.pop('tags', []),
         'is_test': kw.pop('test', False)}
    r.update(kw)
    return r


def users(raw, **kw):
    o = {'usersState': 'ready', 'metrics': None, 'pending': None, 'packages': None, 'q': '', 'chip': 'all', 'filter': {'role': None, 'seg': None}, 'sort': 'new', 'limit': 50, 'now': NOW,
         'searchExtra': [], 'searching': False, 'searchFailed': False}
    o.update(kw)
    return v2p('users', raw, o)


RAW = [U('1', 'سلمى', 's@x.test', plan='pro', phone='0100', seg='lawyer'), U('2', 'كريم', 'k@x.test', role='admin'), U('3', 'منى', 'm@x.test', trainer='approved', tags=['أ', 'ب', 'ج', 'د']),
       U('4', 'ياسر', 'y@x.test', role='staff', login=None, active=False), U('5', 'ليلى', 'l@x.test', role='investor', test=True), U('6', 'نادر', 'n@x.test', trainer='pending')]


@needs_node
def test_user_chip_counts_come_from_metrics_else_rows_and_never_guess_when_truncated():
    m = {'total': 120, 'members': 90, 'admins': 1, 'staff': 2, 'investors': 1, 'trainers_approved': 14, 'paid_plan': 20, 'signups_today': 3, 'signups_7d': 19}
    V = users(RAW, metrics=m, pending={'rows': [pu('p1', True)], 'count': 7})
    assert [(c['key'], c['n']) for c in V['chips']] == [('all', 120), ('member', 90), ('trainer', 14), ('staff', 2), ('visitor', 7)]
    assert [c['label'] for c in V['chips']] == ['الكل', 'أعضاء', 'مدرّبون', 'فريق العمل', 'زوّار']
    assert [(r['key'], r['n']) for r in V['filterOptions']['roles']] == [('admin', 1), ('investor', 1), ('trainer_pending', None), ('test', None)]
    assert V['truncated'] is True and V['total'] == 120
    V = users(RAW)                                                               # بلا أرقام وبلا اقتطاع ⇒ من الصفوف
    assert [c['n'] for c in V['chips']][:4] == [6, 3, 1, 1] and V['truncated'] is False
    V = users(RAW, metrics={'total': 600})
    assert [c['n'] for c in V['chips']][1:4] == [None, None, None]               # مقتطع بلا أرقام ⇒ بلا رقم
    assert 'غير متاح بعد' in V['head'] and V['head'].startswith('الحسابات ٦٠٠')


@needs_node
def test_the_visitor_chip_comes_from_the_pending_list_and_rows_carry_at_most_four_chips():
    V = users(RAW, pending={'rows': [pu('p1', True, email='s@x.test')], 'count': 1}, chip='visitor')
    assert [r['id'] for r in V['rows']] == ['1'] and any(c['key'] == 'visitor' for c in V['rows'][0]['chips'])
    V = users(RAW)
    r3 = [r for r in V['rows'] if r['id'] == '3'][0]
    assert len(r3['chips']) == 5 and r3['chips'][-1] == {'key': 'more', 'label': '+٢'} and sum(1 for c in r3['chips'] if c['key'] != 'more') == 4
    labels = lambda uid: [c['label'] for c in [r for r in V['rows'] if r['id'] == uid][0]['chips']]
    assert labels('4') == ['فريق العمل', 'موقوف'] and labels('5') == ['مستثمر', 'تجريبي'] and labels('6') == ['عضو', 'طلب مدرّب']
    assert [r for r in V['rows'] if r['id'] == '1'][0]['planText'] == 'احترافية'
    assert [r for r in V['rows'] if r['id'] == '4'][0]['lastText'] == 'غير متاح'        # لا «لم يدخل» لأننا لا نعرف


@needs_node
def test_search_filters_sort_and_empty_states():
    assert [r['id'] for r in users(RAW, q='سلم')['rows']] == ['1']
    assert [r['id'] for r in users(RAW, q='K@X')['rows']] == ['2'] and [r['id'] for r in users(RAW, q='0100')['rows']] == ['1']
    V = users(RAW, filter={'role': 'admin', 'seg': None})
    assert [r['id'] for r in V['rows']] == ['2'] and V['activeFilters'] == [{'key': 'role', 'label': 'الإدارة'}]
    V = users(RAW, filter={'role': None, 'seg': 's:lawyer'})
    assert [r['id'] for r in V['rows']] == ['1'] and V['activeFilters'][0]['label'] == 'محامون'
    V = users(RAW, filter={'role': None, 'seg': 't:أ'})
    assert [r['id'] for r in V['rows']] == ['3']
    V = users(RAW, filter={'role': 'trainer_pending', 'seg': None})
    assert [r['id'] for r in V['rows']] == ['6']
    V = users(RAW, sort='login')
    assert V['rows'][-1]['id'] == '4' and {'key': 'sort', 'label': 'آخر دخول'} in V['activeFilters']
    V = users(RAW, q='لا يوجد أبدًا')
    assert V['empty'] == {'text': 'لا حساب يطابق «لا يوجد أبدًا»', 'hint': 'اكتب البريد كاملًا واضغط إدخال لفتح صفحة الشخص'}
    V = users(RAW, q='لا يوجد أبدًا', searching=True)
    assert V['empty'] is None and V['searchLine'] == '…نبحث في كل الحسابات'
    V = users(RAW, q='x', searchFailed=True)
    assert V['searchLine'] == 'تعذّر البحث في كل الحسابات الآن — النتائج من المعروض فقط'
    V = users(RAW, q='ليلى', searchExtra=[U('9', 'ليلى الجديدة', 'new@x.test'), U('5', 'ليلى', 'l@x.test')])
    assert sorted(r['id'] for r in V['rows']) == ['5', '9'] and [r for r in V['rows'] if r['id'] == '9'][0]['fromSearch'] is True
    V = users(RAW, limit=3)
    assert len(V['rows']) == 3 and V['more'] == 3 and V['shown'] == 3
    assert users(None, usersState='error')['state'] == 'failed' and users(None, usersState='loading')['state'] == 'loading'
    assert users([], usersState='ready')['state'] == 'empty'


@needs_node
def test_admin_guard_locks_the_last_admin_and_an_unknown_count():
    g = lambda *a: v2p('adminGuard', *a)
    admin = {'role': 'admin'}
    assert g(admin, {'admins': 1}, [], True) == {'locked': True, 'note': 'هذا آخر حساب إدارة، فلا يمكن تغيير دوره'}
    assert g(admin, {'admins': 2}, [], True)['locked'] is False
    assert g(admin, None, [{'role': 'admin'}], False)['locked'] is True and g(admin, None, [{'role': 'admin'}, {'role': 'admin'}], False)['locked'] is False
    unk = g(admin, None, [{'role': 'admin'}, {'role': 'admin'}], True)
    assert unk['locked'] is True and unk['note'].endswith('(تعذّر التأكد من عدد حسابات الإدارة)')
    assert g({'role': 'member'}, {'admins': 1}, [], True)['locked'] is False


# ================================================================ ٥) الرسائل
@needs_node
def test_messages_read_the_platform_field_names_oldest_first_and_flag_the_old_ones():
    site = [{'id': 1, 'name': 'أ', 'email': 'a@x.test', 'phone': '', 'topic': 'موضوع', 'body': 'نص', 'status': 'new', 'at': ago(30)},
            {'id': 2, 'name': 'ب', 'email': 'b@x.test', 'phone': '', 'topic': '', 'body': 'نص', 'status': 'new', 'at': ago(2)},
            {'id': 3, 'name': 'ج', 'email': 'c@x.test', 'phone': '', 'topic': 'قديم', 'body': 'رد', 'status': 'replied', 'at': ago(90)}]
    chat = [{'id': 'pm-2', 'from_name': 'هـ', 'from_email': 'e@x.test', 'subject': 'سؤال', 'body': 'متأخر', 'contact_phone': '+20100', 'created_at': pf.iso(-3)},
            {'id': 'pm-1', 'name': 'و', 'email': '', 'topic': 'قديم الشكل', 'text': 'بلا بريد', 'phone': '+201001234567', 'created_at': pf.iso(-40)},
            {'id': 'pm-3', 'user_name': 'ز', 'summary': 'ملخص', 'created_at': pf.iso(-1)}]
    lead = [{'id': 'ld-1', 'full_name': 'سلمى', 'phone': '+201555000111', 'experience': 'خمس سنوات', 'want': 'استشارة', 'from_email': 'm@x.test', 'created_at': pf.iso(-8)},
            {'id': 'ld-2', 'name': 'بلا', 'need': 'عرض', 'email': 'n@x.test', 'created_at': pf.iso(-1)}, {'id': 'ld-3', 'created_at': pf.iso(-1)}]
    M = v2p('messages', site, 'ready', chat, 'ready', lead, 'ready', NOW)
    s = M['cols']['site']['items']
    assert [t['rid'] for t in s] == [1, 2] and s[0]['old'] is True and s[1]['old'] is False and 'مرّ عليها أكثر من يوم' in s[0]['brain'] and 'مرّ عليها' not in s[1]['brain']
    assert s[0]['primary'] == {'label': 'ردّ', 'act': {'do': 'sheet', 'sheet': 'reply'}} and s[0]['secondary'][0]['label'] == 'احذف'
    assert [r['rid'] for r in M['replied']] == [3]
    c = M['cols']['chat']['items']
    assert [t['rid'] for t in c] == ['pm-1', 'pm-2', 'pm-3']
    pm2 = [t for t in c if t['rid'] == 'pm-2'][0]
    assert pm2['title'] == 'هـ' and pm2['sub'] == 'سؤال' and pm2['email'] == 'e@x.test' and pm2['phone'] == '+20100'
    assert pm2['primary']['label'] == 'ردّ بالبريد' and pm2['primary']['act']['url'].startswith('mailto:e@x.test?subject=') and pm2['secondary'][0]['label'] == 'علّمها منتهية'
    pm1 = [t for t in c if t['rid'] == 'pm-1'][0]
    assert pm1['primary']['label'] == 'واتساب' and pm1['primary']['act']['url'] == 'https://wa.me/201001234567' and pm1['body'] == 'بلا بريد'
    pm3 = [t for t in c if t['rid'] == 'pm-3'][0]
    assert pm3['title'] == 'ز' and pm3['primary'] == {'label': 'علّمها منتهية', 'act': {'do': 'resolve'}} and pm3['secondary'] == [] and pm3['body'] == 'ملخص'
    f = {t['rid']: t for t in M['cols']['follow']['items']}
    assert f['ld-1']['sub'] == 'يريد: استشارة' and f['ld-1']['body'] == 'الخبرة: خمس سنوات' and f['ld-1']['primary']['label'] == 'واتساب' and f['ld-1']['secondary'][0]['label'] == 'تمت المتابعة'
    assert f['ld-2']['title'] == 'بلا' and f['ld-2']['sub'] == 'يريد: عرض' and f['ld-2']['primary']['label'] == 'ردّ بالبريد'
    assert f['ld-3']['primary'] == {'label': 'تمت المتابعة', 'act': {'do': 'resolve'}} and f['ld-3']['title'] == 'بلا اسم'
    assert f['ld-1']['brain'] == 'طلب التواصل دون إنشاء حساب'
    assert M['head']['text'].startswith('تنتظر الرد ٨: ٢ من الموقع · ٣ من المحادثة · ٣ طلبات تواصل.')


@needs_node
def test_a_failed_message_source_is_null_not_zero():
    M = v2p('messages', [], 'ready', None, 'error', [], 'ready', NOW)
    assert M['cols']['chat']['state'] == 'failed' and M['cols']['chat']['count'] is None and M['cols']['site']['count'] == 0
    assert 'تعذّر جلب: رسائل المحادثة' in M['head']['text'] and 'لا رسائل' not in M['head']['text']
    M = v2p('messages', [], 'ready', [], 'ready', [], 'ready', NOW)
    assert M['head']['text'] == 'لا رسائل تنتظر الرد.'


# ================================================================ ٦) النصوص
def _strings(src):
    """كل النصوص المقتبسة (بنفس علامة الاقتباس) في ملف جافاسكربت — تقريب كافٍ لفحص النص الظاهر."""
    out = []
    for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'", src):
        out.append(m.group(1))
    return out


def _visible(src):
    out = []
    for s in _strings(src):
        t = re.sub(r'<[^>]*>?', ' ', s)                      # وسوم HTML وسماتها (أصناف · معرّفات · aria) ليست نصًّا ظاهرًا — ويشمل الوسم المقطوع عند علامة اقتباس
        t = re.sub(r'(^|\s)[a-z-]+="[^"]*"?', ' ', t)
        t = re.sub(r"&[a-z]+;", ' ', t).replace('\\n', ' ')
        if re.search(r'[؀-ۿ]', t):
            out.append(t)
    return out


def test_copy_is_plain_standard_arabic_without_banned_words():
    for name, src in (('people.js', PEOPLE_JS), ('v2s:people', BLOCK)):
        assert 'يقوّم' not in src and 'يقوم' not in src.replace('يقوم بـ', ''), name
        assert 'مشبوه' not in src, name
        for s in _visible(src):
            assert not re.search(r'(?<![؀-ۿ])(اتبعت|اتبعتت|مستني|مستنّي|لسه|عايز|عايزة|ليه|مش|دلوقتي|اتنسخ|هيتعمل|بتاع|بتاعة|اتسحبت|فين|منين)(?![؀-ۿ])', s), (name, s)
            latin = re.sub(r'(mailto:|https?://wa\.me/?|https?://|tel:)', '', s)
            assert not re.search(r'[A-Za-z]', latin), (name, s)
        # لا عنوان يبدأ بالذكاء الاصطناعي
        for s in _visible(src):
            assert not re.match(r'\s*(الذكاء|ذكاء|AI)', s), (name, s)
    assert 'مشبوه' not in LOGIC


@needs_node
def test_stage_labels_wa_texts_and_urls_are_exact():
    L_ = _node("console.log(JSON.stringify(Object.keys(L.v2p.STAGE).map(k=>[k,L.v2p.stageLabel(k)])))")
    assert dict(L_) == {'pending': 'لم تُفتح بعد', 'opened': 'فتح الرابط', 'roles_chosen': 'اختيار الصفة', 'pain_seen': 'مشاهدة التعريف', 'exercised': 'تجربة مثال', 'declared': 'الموافقة على الشروط',
                        'registered': 'الانضمام', 'expired': 'انتهت مهلتها', 'revoked': 'سُحبت', 'awaiting_approval': 'تنتظر موافقتك', 'rejected': 'رُفضت'}
    assert v2p('waText', 'invite', 'منى', 'https://l.test/1') == 'أهلًا منى،\nهذه دعوتك إلى منصة البروفيسور، وهي باسمك وحدك:\nhttps://l.test/1'
    assert v2p('waText', 'remind', 'منى', 'https://l.test/1') == 'أهلًا منى،\nدعوتك إلى منصة البروفيسور ما زالت بانتظارك، ويمكنك إكمالها من الرابط نفسه:\nhttps://l.test/1'
    assert v2p('waText', 'invite', '', 'https://l.test/1').startswith('أهلًا،\n')
    from urllib.parse import quote
    t = 'نص'
    assert v2p('waUrl', '+20 100 123 4567', t) == 'https://wa.me/201001234567?text=' + quote(t, safe='')
    assert v2p('waUrl', '12', t) == 'https://wa.me/?text=' + quote(t, safe='') and v2p('waUrl', '', t) == 'https://wa.me/?text=' + quote(t, safe='')


def test_toasts_and_errors_reachable_from_people_js_are_standard_arabic():
    """الرسائل التي تخرجها دوال الداشبورد التي يناديها القسم (قرار الزائر · طلب الاستكمال · إنهاء الرسالة · فشل الرد) بفصحى بلا عامية."""
    def body(start, end):
        i = API_JS.index(start)
        return API_JS[i:API_JS.index(end, i)]
    chunks = [body('EP.decideInboxItem = function', 'EP.setPendingUserAccess'), body('EP.setPendingUserAccess = function', 'EP.purgeCheck = function'),
              body('EP.resolveInboxItem = function', 'EP.reassignVerify'), body('var EF_NO_REPLY_AR', 'EP.expertFileDetail')]
    strings = []
    for c in chunks:
        # الثابتان `EF_NO_REPLY_AR` و`EF_SESSION_AR` يبقيان كما هما في `error` (اختبارات نوافذ الفلوس تثبّتهما)؛ ما يخرج للمؤسس هو التوست الفصيح بجانبهما
        c = '\n'.join(l for l in c.split('\n') if 'EF_NO_REPLY_AR =' not in l and 'EF_SESSION_AR =' not in l and 'status === 401' not in l)
        strings += [t for t in re.findall(r'"([^"\n]*[؀-ۿ][^"\n]*)"', re.sub(r'//[^\n]*', '', c))]
    assert any('فُتحت المنصة للزائر' in t for t in strings) and any('لم يصلنا رد' in t for t in strings)
    bad = r'(?<![؀-ۿ])(اتفتحت|اترفض|اترفضت|اتبعت|اتقفل|اتحوّل|فضل|ما وصلناش|وشوف|حصل إيه|دوس|تاني|لسه|مش|عشان|دلوقتي|اتعمدت)(?![؀-ۿ])'
    for t in strings:
        assert not re.search(bad, t), t


@needs_node
def test_whatsapp_links_need_an_international_number_else_copy_the_number_or_use_email():
    wn = lambda p: v2p('waNumber', p)
    assert wn('+20 100 123 4567') == '201001234567' and wn('00966501234567') == '966501234567' and wn('+966-50-123-4567') == '966501234567'
    assert wn('01098765432') == '' and wn('0098') == '' and wn('+12') == '' and wn('') == '' and wn('+1234567890123456') == ''
    from urllib.parse import quote
    assert v2p('waUrl', '01098765432', 'x') == 'https://wa.me/?text=' + quote('x', safe='') and v2p('waUrl', '00201098765432', 'x') == 'https://wa.me/201098765432?text=' + quote('x', safe='')
    chat = [{'id': 'a', 'name': 'محلي', 'phone': '01098765432', 'created_at': pf.iso(-1)}, {'id': 'b', 'name': 'محلي وبريد', 'phone': '01098765432', 'email': 'q@x.test', 'created_at': pf.iso(-1)},
            {'id': 'c', 'name': 'دولي', 'phone': '0020 109 876 5432', 'created_at': pf.iso(-1)}]
    lead = [{'id': 'l', 'name': 'محلي', 'phone': '01098765432', 'created_at': pf.iso(-1)}, {'id': 'm', 'name': 'محلي وبريد', 'phone': '01098765432', 'email': 'q@x.test', 'created_at': pf.iso(-1)}]
    M = v2p('messages', [], 'ready', chat, 'ready', lead, 'ready', NOW)
    c = {t['rid']: t for t in M['cols']['chat']['items']}
    assert c['a']['primary'] == {'label': 'انسخ الرقم', 'act': {'do': 'copy', 'text': '01098765432'}} and c['b']['primary']['label'] == 'ردّ بالبريد'
    assert c['c']['primary']['act']['url'] == 'https://wa.me/00201098765432'.replace('0020', '20', 1)
    f = {t['rid']: t for t in M['cols']['follow']['items']}
    assert f['l']['primary']['act'] == {'do': 'copy', 'text': '01098765432'} and f['m']['primary']['label'] == 'ردّ بالبريد'
    assert not any('wa.me' in json.dumps(t, ensure_ascii=False) for t in (c['a'], c['b'], f['l'], f['m']))


@needs_node
def test_messages_head_line_uses_correct_counts_grammar():
    def head(n):
        lead = [{'id': 'l%d' % i, 'name': 'ن', 'created_at': pf.iso(-1)} for i in range(n)]
        return v2p('messages', [], 'ready', [], 'ready', lead, 'ready', NOW)['head']['text']
    assert 'طلب تواصل واحد.' in head(1) and 'طلبا تواصل.' in head(2) and '٣ طلبات تواصل.' in head(3) and '١١ طلب تواصل.' in head(11)
    assert '٢ طلبات' not in head(2)
    assert 'متوقفة' in LOGIC and 'واقفة' not in BLOCK and 'واقفتان' not in BLOCK


def test_the_visitor_reject_label_and_the_reason_wording():
    assert 'سبب الرفض (اختياري) — يُحفظ على الطلب، فاكتب ما لا تمانع أن يقرأه صاحبه' in PEOPLE_JS
    assert 'ولا يراه صاحبه' not in PEOPLE_JS and 'ولا يراه صاحبه' not in BLOCK


# ================================================================ ٧) الإجراءات (ثابتة)
def test_every_write_path_exists_in_the_dashboard_api():
    paths = ['"/pending-users/" + encodeURIComponent(row.id) + "/access"', '"/invites/" + encodeURIComponent(id) + "/approve"', '"/invites/" + encodeURIComponent(id) + "/reject"',
             '"/invites/" + encodeURIComponent(inv.id) + "/revoke"', '"/invites/" + encodeURIComponent(inv.id) + "/reissue"', 'post("/invites", {', '"/waitlist/" + encodeURIComponent(row.id) + "/invite"',
             '"/platform-users/" + u.id + "/role"', '"/platform-users/" + u.id + "/plan"', '"/platform-users/" + u.id + "/tags"', '"/platform-users/" + encodeURIComponent(u.id) + "/flag-test"',
             '"/platform-trainers/" + encodeURIComponent(u.id) + "/deactivate"', '"/users/" + encodeURIComponent(u.id) + "/purge"', '"/users/" + encodeURIComponent(userId) + "/purge-check"',
             '"/messages/" + m.id + "/reply"', 'api("/messages/" + m.id, { method: "DELETE" })', 'post("/settings/founding"', 'post("/settings/invites"', 'post("/settings/invite-videos"',
             '"/platform-messages/" + encodeURIComponent(i.apiId) + "/resolve"', '"/platform-leads/" + encodeURIComponent(i.apiId) + "/resolve"']
    for p in paths:
        assert p in API_JS, p
    # والمسارات نفسها بصيغة people.js
    for frag in ("'/pending-users/' + encodeURIComponent(id) + '/access'", "'/invites/' + encodeURIComponent(r.id) + '/reject'", "'/invites/' + encodeURIComponent(r.id) + '/revoke'",
                 "'/invites/' + encodeURIComponent(r.id) + '/reissue'", "'/waitlist/' + encodeURIComponent(w.id) + '/invite'", "'/platform-users/' + encodeURIComponent(u.id) + '/role'",
                 "'/platform-users/' + encodeURIComponent(u.id) + '/plan'", "'/platform-users/' + encodeURIComponent(u.id) + '/tags'", "'/platform-users/' + encodeURIComponent(u.id) + '/flag-test'",
                 "'/platform-trainers/' + encodeURIComponent(u.id) + '/deactivate'", "'/users/' + encodeURIComponent(u.id) + '/purge'", "'/messages/' + encodeURIComponent(t.rid) + '/reply'",
                 "'/settings/founding'", "'/settings/invites'", "'/settings/invite-videos'", "path: '/invites',"):
        assert frag in PEOPLE_JS, frag


def test_no_native_dialogs_no_user_post_and_every_write_goes_through_the_one_door():
    for bad in ('window.prompt', 'prompt(', 'confirm(', 'alert('):
        assert bad not in PEOPLE_JS, bad
    assert "'/platform-users'," not in PEOPLE_JS and 'POST /api/platform-users"' not in PEOPLE_JS
    api_calls = re.findall(r'\.api\(([^)]*)\)', PEOPLE_JS)
    assert len(api_calls) == 2, api_calls                       # PX.call (الكتابة) وPX.read (القراءة) فقط
    assert 'E.api(spec.path, opts)' in PEOPLE_JS and 'E.api(path)' in PEOPLE_JS
    assert 'fetch(' not in PEOPLE_JS and 'XMLHttpRequest' not in PEOPLE_JS
    assert 'createUser' not in PEOPLE_JS and 'EP.setUserRole' not in PEOPLE_JS
    for fn in ('decideInboxItem', 'resolveInboxItem'):
        assert 'E.' + fn in PEOPLE_JS
    # لا تأكيد = لا كتابة: كل ورقة كتابة فيها زرّ تنفيذ، والتحويلات المالية غير موجودة في القسم
    assert '/wallet-payouts' not in PEOPLE_JS and 'confirmed' not in PEOPLE_JS.replace('confirmScreen', '')


def test_the_users_list_has_no_management_controls_only_the_person_page_opens_the_sheet():
    start = PEOPLE_JS.index('function userRowHtml(')
    end = PEOPLE_JS.index('function usersBodyHtml(')
    row = PEOPLE_JS[start:end]
    assert 'data-v2p-manage' not in row and 'إدارة' not in row and 'افتح صفحة الشخص' in row
    assert PEOPLE_JS.count('data-v2p-manage') == 3        # manageBtn (زر + رسالة) + المستمع
    assert 'EP.createUser' not in PEOPLE_JS


# ================================================================ ٨) Flask: كل كتابة بتوصل المنصة بنفس المسار والجسم
class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.text = self.content.decode('utf-8')
        self.headers = {'Content-Type': 'application/json'}
        self.ok = 200 <= status < 300

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
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
             preferred_currency='AUTO', is_active=True)
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
        admin = _bearer(_mkuser('v2sp-admin@x.test', 'admin'))
        staff = _bearer(_mkuser('v2sp-staff@x.test', 'employee'))
        yield {'admin': admin, 'staff': staff, 'client': flask_app.test_client()}


class Plat(object):
    """يلتقط كل نداء للمنصة (requests.request وSession.request) ويرد من `PeoplePlatform`. أي عنوان برّه المنصة المزيّفة ⇒ ممنوع."""

    def __init__(self):
        self.ef = pf.PeoplePlatform()
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None, **_kw):
        method = method.upper()
        if not str(url).startswith(PLATFORM + '/'):
            self.blocked.append(str(url))
            raise RuntimeError('طلب حقيقي ممنوع: ' + str(url))
        path = str(url)[len(PLATFORM):]
        self.seen.append((method, path, dict(params or {}), json))
        out = self.ef.handle(method, path, params or {}, json or {})
        if out is None:
            return _Resp(200, [])
        return _Resp(*out)

    def writes(self):
        return [(m, p, b) for m, p, _, b in self.seen if m in ('POST', 'PUT', 'DELETE', 'PATCH')]


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    import requests
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(requests, 'request', p)
    monkeypatch.setattr(requests.Session, 'request', lambda self, method, url, **kw: p(method, url, params=kw.get('params'), json=kw.get('json'), headers=kw.get('headers'), timeout=kw.get('timeout')))
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


def _call(ctx, method, path, body=None, role='admin'):
    c = ctx['client']
    kw = {'headers': ctx[role]}
    if body is not None:
        kw['json'] = body
    return getattr(c, method.lower())(path, **kw)


WRITES = [
    ('POST', '/api/pending-users/pu-1/access', {'access': 'member'}, '/api/bridge/users/pu-1/access', {'access': 'member'}),
    ('POST', '/api/pending-users/pu-2/access', {'access': 'pending', 'note': 'نحتاج بيانات'}, '/api/bridge/users/pu-2/access', {'access': 'pending', 'note': 'نحتاج بيانات'}),
    ('POST', '/api/invites/inv-aw1/approve', {}, '/api/bridge/invites/inv-aw1/approve', None),
    ('POST', '/api/invites/inv-aw2/reject', {'note': 'غير مكتمل'}, '/api/bridge/invites/inv-aw2/reject', {'note': 'غير مكتمل'}),
    ('POST', '/api/invites/inv-p1/revoke', {}, '/api/bridge/invites/inv-p1/revoke', None),
    ('POST', '/api/invites/inv-x1/reissue', {}, '/api/bridge/invites/inv-x1/reissue', None),
    ('POST', '/api/invites', {'name': 'سيف', 'email': '', 'phone': '+201001112222', 'note': ''}, '/api/bridge/invites', {'name': 'سيف', 'phone': '+201001112222'}),
    ('POST', '/api/waitlist/wl-1/invite', {'phone': '+201112223344'}, '/api/bridge/waitlist/wl-1/invite', {'phone': '+201112223344'}),
    ('POST', '/api/platform-users/u-mona/role', {'role': 'staff', 'email': 'mona.s@example.test'}, '/api/bridge/users/u-mona/role', {'role': 'staff'}),
    ('POST', '/api/platform-users/u-mona/plan', {'plan_id': 'pro'}, '/api/bridge/users/u-mona/plan', {'plan_id': 'pro'}),
    ('POST', '/api/platform-users/u-mona/tags', {'tags': ['أ', 'ب']}, '/api/bridge/users/u-mona/tags', {'tags': ['أ', 'ب']}),
    ('POST', '/api/platform-users/u-mona/flag-test', {'is_test': True, 'email': 'mona.s@example.test'}, '/api/bridge/users/u-mona/flag-test', {'is_test': True}),
    ('POST', '/api/platform-trainers/u-hala/deactivate', {'reason': 'سبب', 'is_test': True, 'email': 'hala@example.test'}, '/api/bridge/trainers/u-hala/deactivate', {'reason': 'سبب', 'is_test': True}),
    ('POST', '/api/users/pu-3/purge', {'note': ''}, '/api/bridge/users/pu-3/purge', {'note': ''}),
    ('POST', '/api/settings/founding', {'open': False}, '/api/bridge/settings/founding', {'open': False}),
    ('POST', '/api/settings/invites', {'member_invite_quota': 7}, '/api/bridge/settings/invites', {'member_invite_quota': 7}),
    ('POST', '/api/settings/invite-videos', {'lawyer': 'https://example.test/v/l'}, '/api/bridge/settings/invite-videos', {'lawyer': 'https://example.test/v/l'}),
    ('POST', '/api/platform-messages/pm-1/resolve', {}, '/api/bridge/messages/pm-1/resolve', None),
    ('POST', '/api/platform-leads/ld-1/resolve', {}, '/api/bridge/leads/ld-1/resolve', None),
]


@pytest.mark.parametrize('method,path,body,platform_path,platform_body', WRITES, ids=[w[1] for w in WRITES])
def test_each_write_reaches_the_platform_with_the_same_path_and_body(ctx, plat, method, path, body, platform_path, platform_body):
    r = _call(ctx, method, path, body)
    assert r.status_code == 200, (path, r.status_code, r.get_data(as_text=True)[:200])
    hits = [w for w in plat.writes() if w[1] == platform_path]
    assert len(hits) == 1, (platform_path, plat.writes())
    if platform_body:
        for k, v in platform_body.items():
            assert (hits[0][2] or {}).get(k) == v, (platform_path, hits[0])


def test_purge_refuses_when_the_check_says_no_and_the_dashboard_passes_the_reason_through(ctx, plat):
    chk = _call(ctx, 'GET', '/api/users/u-hala/purge-check')
    assert chk.status_code == 200 and chk.get_json()['purgeable'] is False and chk.get_json()['reason']
    r = _call(ctx, 'POST', '/api/users/u-hala/purge', {'note': ''})
    assert r.status_code == 409 and r.get_json().get('purgeable') is False
    ok = _call(ctx, 'GET', '/api/users/pu-3/purge-check')
    assert ok.get_json()['purgeable'] is True


def test_reply_records_replied_and_sends_no_email_and_calls_no_platform(ctx, plat):
    with flask_app.app_context():
        m = Message(name='زائر', email='v@x.test', topic='سؤال', body='نص', status='new')
        db.session.add(m)
        db.session.commit()
        mid = m.id
    r = _call(ctx, 'POST', '/api/messages/%d/reply' % mid, {'body': 'شكرًا لتواصلك'})
    assert r.status_code == 200
    with flask_app.app_context():
        m = Message.query.get(mid)
        assert m.status == 'replied' and m.reply_body == 'شكرًا لتواصلك'
    assert plat.seen == [], plat.seen                        # لا نداء للمنصة ولا بريد: الرد يُحفظ هنا ويُفتح بريد المؤسس من المتصفح
    r = _call(ctx, 'DELETE', '/api/messages/%d' % mid)
    assert r.status_code == 200 and plat.seen == []
    with flask_app.app_context():
        assert Message.query.get(mid) is None


def test_reads_the_sheets_use_are_admin_or_employee_reads_only(ctx, plat):
    for path in ('/api/waitlist?limit=200', '/api/pending-users?limit=200', '/api/invites?limit=200', '/api/invites/inv-o2', '/api/platform-users?search=سلوى', '/api/platform-messages?status=new',
                 '/api/platform-leads?status=new', '/api/settings/invites', '/api/settings/invite-videos', '/api/settings/founding', '/api/platform-metrics', '/api/packages'):
        r = _call(ctx, 'GET', path)
        assert r.status_code == 200, (path, r.status_code)
    assert all(m == 'GET' for m, _, _, _ in plat.seen)
    r = _call(ctx, 'GET', '/api/platform-users?search=سلوى')
    names = [u['full_name'] for u in r.get_json()['users']]
    assert 'سلوى محمود' in names                              # الباحث في الخادم يصل لحسابات خارج المعروض


# ================================================================ ٩) الربط
def test_index_has_exactly_our_two_lines_in_the_sections_block_and_the_hook_once_after_d3():
    blk = INDEX[INDEX.index('<!-- v2 sections begin -->'):INDEX.index('<!-- v2 sections end -->')]
    lines = [l.strip() for l in blk.splitlines()[1:] if l.strip()]
    assert '<link rel="stylesheet" href="v2s/people.css">' in lines and '<script src="v2s/people.js"></script>' in lines   # بعد الدمج: كتلة واحدة لكل الأقسام
    assert lines.index('<link rel="stylesheet" href="v2s/people.css">') + 1 == lines.index('<script src="v2s/people.js"></script>')
    assert INDEX.index('<script src="v2-d2.js"></script>') < INDEX.index('<script src="v2-d3.js"></script>') < INDEX.index('<!-- v2 sections begin -->')
    # الخطّاف موحّد بعد الدمج: سجلّ V2SEC (v2s/_registry.js) والأشخاص مسجَّلون فيه بمفتاحهم، وبلا V2SECT
    hook = "const _s=V2SEC.owner(current);if(_s){const _ap=document.querySelector('.app');if(_ap){_ap.classList.add('v2-bare');_ap.classList.remove('v2-inbox');}return _s.render(current,v);}"
    assert INDEX.count(hook) == 1 and 'V2SECT' not in INDEX
    d3 = "if(window.V2_ON&&window.V2D3&&V2D3.owns(current))return V2D3.render(current,v);"
    assert INDEX.index(d3) < INDEX.index(hook) and INDEX[INDEX.index(d3):INDEX.index(hook)].count('\n') <= 2


def test_the_old_screens_are_byte_identical_to_the_base_commit():
    def body(name):
        i = INDEX.index('function %s(' % name)
        return INDEX[i:INDEX.index('\nfunction ', i + 10)]
    got = {n: hashlib.sha1(body(n).encode('utf-8')).hexdigest() for n in ('viewUsers', 'viewInvites', 'viewMessages')}
    assert got == {'viewUsers': 'd04e63d6470f3a74c061f0a206fe1bd391aad700', 'viewInvites': '50ca6afa99c8b8312547e35bdb2481159f96711f', 'viewMessages': '254715337ca776d5785722528b1881531816c9d8'}


def test_no_server_route_for_people_and_dockerfiles_ship_the_folder():
    app_py = _read('backend', 'app.py')
    assert 'v2/people' not in app_py and not os.path.exists(os.path.join(ROOT, 'backend', 'v2_people_routes.py'))
    for df in ('Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')):
        assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in _read(df), df
    assert os.path.isfile(os.path.join(DC, 'v2s', 'people.js')) and os.path.isfile(os.path.join(DC, 'v2s', 'people.css'))


def test_the_person_page_opens_the_account_sheet_and_is_byte_identical_without_us():
    d2 = _read('dashboard-cloud', 'v2-d2.js')
    expr = "(window.V2SEC&&V2SEC.people&&V2SEC.people.manageBtn?V2SEC.people.manageBtn(email):'')"
    assert d2.count(expr) == 1
    assert d2.index('data-a="mail">مراسلة</a>') < d2.index(expr) < d2.index("'</div></header>'")


STUB = r"""
global.window = global; global.localStorage = {getItem(){return null}}; const listeners = [];
global.document = {addEventListener(t, f){ listeners.push(t) }, getElementById(){ return null }, querySelector(){ return null }, querySelectorAll(){ return [] }, body: {contains(){ return false }}};
window.V2L = require(%s);
let SH = %s; if (SH) window.V2SHELL = {on: SH.on}; window.V2_HOST = {state: () => ({section: SH ? SH.section : 'home', tab: SH ? SH.tab : 'board'}), current: () => 'x'};
require(%s);
const S = window.V2SEC.people;
%s
"""


def _stub(shell, js):
    script = STUB % (json.dumps(os.path.join(DC, 'v2-logic.js')), json.dumps(shell), json.dumps(os.path.join(DC, 'v2s', 'people.js')), js)
    p = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


@needs_node
def test_owns_is_false_when_the_shell_is_off_so_the_old_screens_render():
    mods = ['invites', 'users', 'v2p_invites', 'inbox', 'home']
    off = _stub(None, "console.log(JSON.stringify(%s.map(m=>S.owns(m))))" % json.dumps(mods))
    assert off == [False] * 5
    on = _stub({'on': True, 'section': 'people', 'tab': 'messages'}, "console.log(JSON.stringify(%s.map(m=>S.owns(m))))" % json.dumps(mods))
    assert on == [True, True, True, True, False]
    inbox_home = _stub({'on': True, 'section': 'home', 'tab': 'inbox'}, "console.log(JSON.stringify(S.owns('inbox')))")
    assert inbox_home is False
    btn = _stub({'on': True, 'section': 'people', 'tab': 'users'}, "console.log(JSON.stringify(S.manageBtn('a@b.test')))")
    assert 'data-v2p-manage="a@b.test"' in btn and 'إدارة الحساب' in btn


def test_the_css_is_scoped_and_the_old_look_classes_are_not_reused():
    css = re.sub(r'/\*.*?\*/', '', PEOPLE_CSS, flags=re.S)
    for sel in re.findall(r'(?m)^\s*([^\s@}{][^{}]*)\{', css):
        for part in sel.split(','):
            part = part.strip()
            if not part or part in ('from', 'to'):
                continue
            assert re.search(r'\.v2p|\.v2pm|v2d-pact|#v2sbar', part), part
    for old in ('.kpi', '.panel', '.policy', '.inboxwrap', '.trow', '.filterbar'):
        assert old not in PEOPLE_CSS and old not in PEOPLE_JS
    assert '#9E2B4E' in PEOPLE_CSS and '#FBFAF7' in PEOPLE_CSS and '#21262E' in PEOPLE_CSS
