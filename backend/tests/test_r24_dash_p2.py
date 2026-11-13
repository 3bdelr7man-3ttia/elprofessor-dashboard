# -*- coding: utf-8 -*-
"""R24 م٢ — الهيكل الجديد: كل نوع بند له بيت · شريط «محتاج قرارك» في كل قسم · الناس ببطاقة لكل شخص · الشكل الجديد · عدّاد واحد.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r24_dash_p2.py

⛔ صفر شبكة حقيقية وصفر نداء للمنصة: المنطق (v2-logic.js) والرسم (v2-home.js · v2-strip.js) بيتشغّلوا في node:vm بردود جاهزة
(`uiharness/r24p2_ui.js`)، و`/api/v2/person` بيتجرّب بمصادر مزيّفة (`_v2_pull` متبدّلة).
  ١. الهيكل: ترتيب الأقسام والتبويبات · «كل الوارد» و«كل السجلات» اتشالوا · السجلات القديمة للقراية بس · الأسماء القديمة بتتحوّل · ١٠ مربّعات.
  ٢. بيت كل نوع وأفعاله (جدول التسليم): كل نوع كان «افتح» بس بقى قرار له بيت وفعل حقيقي · «للعلم» الحقيقي بس.
  ٣. الناس: بطاقة لكل شخص · التسجيل بيتبلع مع طلب الفتح بس · القبول بتأكيد بخطواته وتنفيذ بالترتيب وتوقف عند أول فشل · الرفض بسبب.
  ٤. العدّاد الواحد: المربّع = الشريط = القايمة الجانبية = «ابدأ القرارات» بعد البعدين والتجاهل.
  ٥. الرسم: اللوحة (ترحيب · «ن قرار مستنيك» · ١٠ مربّعات · صندوقان) · الشريط المشترك · «ابدأ القرارات» بـ«من: القسم» · قراية جوه القسم.
  ٦. صفحة الشخص (الخادم): كل الطلبات المفتوحة بالإيميل · مصدر فاشل ⇒ معلَن · خبير مؤسس بلا حساب.
  ٧. ثابت: التكرارات اتشالت · الـDockerfile بيشحن الملفات الجديدة · الشكل (ورق · عنّابي · قايمة فاتحة) · CLAUDE.md.
"""
import json
import os
import re
import subprocess
import sys

import pytest

from app import app as flask_app, db  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
DC = os.path.join(ROOT, 'dashboard-cloud')
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
NOW = 1763020800000      # ثابت (مفيش ساعة خفية)


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


LOGIC_JS = _read('dashboard-cloud', 'v2-logic.js')
HOME_JS = _read('dashboard-cloud', 'v2-home.js')
HOME_CSS = _read('dashboard-cloud', 'v2-home.css')
STRIP_JS = _read('dashboard-cloud', 'v2-strip.js')
STRIP_CSS = _read('dashboard-cloud', 'v2-strip.css')
SHELL_JS = _read('dashboard-cloud', 'v2-shell.js')
SHELL_CSS = _read('dashboard-cloud', 'v2-shell.css')
D2_JS = _read('dashboard-cloud', 'v2-d2.js')
D3_JS = _read('dashboard-cloud', 'v2-d3.js')
BRAIN2_JS = _read('dashboard-cloud', 'v2-brain2.js')
EXPERTS_JS = _read('dashboard-cloud', 'v2s', 'experts.js')
COURSES_JS = _read('dashboard-cloud', 'v2s', 'courses.js')
PEOPLE_JS = _read('dashboard-cloud', 'v2s', 'people.js')
API_JS = _read('dashboard-cloud', 'dashboard-api.js')
HTML = _read('dashboard-cloud', 'index.html')
DOCKERFILE = _read('Dockerfile')
CLAUDE_MD = _read('CLAUDE.md')


def ui(payload):
    """يشغّل `r24p2_ui.js` (الرسم الحقيقي في node:vm) ⇒ dict."""
    proc = subprocess.run([v2_node.NODE, os.path.join(_HERE, 'uiharness', 'r24p2_ui.js')], input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-1500:]
    return json.loads(proc.stdout)


def text_of(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html or '')).strip()


# ——————————————————————————————————————————————————————— صفوف جاهزة

def row(kind, rid, **kw):
    r = {'apiKind': kind, 'apiId': rid, 'ref': '%s-%s' % (kind[:3].upper(), rid), 'who': kw.pop('who', 'شخص ' + str(rid)), 'ts': NOW - 3 * 3600e3}
    r.update(kw)
    return r


MONA = 'mona@x.test'
ROWS = {
    'visitor': row('pending_user', 'u1', who='منى عبد الحميد', personEmail=MONA, email=MONA, canReject=True, flagLabels=[], puCountry='مصر'),
    'visitor_flagged': row('pending_user', 'u2', who='بدر', personEmail='bader@x.test', email='bader@x.test', canReject=True, flagLabels=['حساب مكرر']),
    'trainer': row('trainer', 't1', who='منى عبد الحميد', personEmail=MONA, canReject=True, rejectNeedsReason=True, trJoin='both', trHeadline='محامية بالنقض'),
    'trainer_solo': row('trainer', 't2', who='تامر', personEmail='tamer@x.test', canReject=True, rejectNeedsReason=True, trJoin='trainer', trHeadline='محامي'),
    'join': row('join', 'j1', who='جلال', personEmail='galal@x.test', email='galal@x.test', serviceLabel='استشارة', licensed=False, canReject=True),
    'join_waiting': row('join', 'j2', who='جمال', personEmail='gamal@x.test', serviceLabel='استشارة', waiting=True),
    'join_licensed': row('join', 'j3', who='جيهان', personEmail='gehan@x.test', serviceLabel='مرافعة', licensed=True, canReject=True),
    'founding_new': row('founding', 'f1', who='فادي', personEmail='fady@x.test', nextStatus='contacted', statusLabel='جديد', canReject=True),
    'founding_contacted': row('founding', 'f2', who='فاتن', personEmail='faten@x.test', nextStatus='invited', statusLabel='تم التواصل', canReject=True),
    'identity': row('identity_doc', 'i1', who='منى عبد الحميد', personEmail=MONA, email=MONA, idTitle='محامية', canReject=True),
    'identity_solo': row('identity_doc', 'i2', who='إيمان', personEmail='eman@x.test', idTitle='محام'),
    'signup_visitor': row('signup', 'u1', who='منى', personEmail=MONA, email=MONA),
    'signup_free': row('signup', 'u9', who='علي', personEmail='ali@x.test', email='ali@x.test'),
    'payfail': row('payfail', 'pf1', who='بشير', pfScope='order', pfWhy='رُفضت', pfGateway='stripe'),
    'gateway': row('payfail', 'gw_stripe_down', who='بوابة stripe', pfScope='gateway', pfAttempts=4, pfGateway='stripe'),
    'dispute': row('dispute', 'd1', dsrc='file', who='دينا', ef={'title': 'ملف نزاع', 'id': 'd1'}),
    'review': row('expert_file', 'r1', efLane='review', who='رنا', ef={'title': 'رأي', 'expert_name': 'خبير', 'id': 'r1'}),
    'legacy': row('legacy', 'l1', who='ليلى', cons={'title': 'استشارة قديمة', 'id': 'l1'}),
    'unactivated': row('expert_file', 'un1', efLane='unactivated', unact=True, who='أمل', ef={'title': 'دفع بلا ملف', 'id': 'un1'}),
    'attention': row('expert_file', 'at1', efLane='waiting', needsAttention=True, who='عادل', ef={'title': 'ملف أمواله متوقفة', 'id': 'at1', 'status': 'blocked'}),
    'file_cand': row('expert_file', 'ef9', efLane='waiting', who='عميل', ef={'id': 'ef9', 'title': 'ملف عقد', 'status': 'awaiting_assignment', 'hours_left': 20,
                                                                          'candidates': [{'email': 'e@x.test', 'name': 'خبير أول', 'auto_pick': True}]}),
    'file_nocand': row('expert_file', 'ef8', efLane='waiting', who='عميل', ef={'id': 'ef8', 'title': 'ملف بلا خبير', 'status': 'awaiting_assignment', 'hours_left': 20, 'candidates': []}),
    'file_sent': row('expert_file', 'ef7', efLane='assigned', fyi=True, who='عميل', ef={'id': 'ef7', 'title': 'ملف اتبعت', 'status': 'assigned', 'hours_left': 40}),
    'verify': row('verify', 'v1', who='طالب توثيق', candidates=[{'email': 'x@x.test', 'name': 'خبير'}], note='توثيق'),
    'manual_payment': row('manual_payment', 'm1', who='منى', amount=300, currency='EGP', payMethod='InstaPay', canReject=True),
    'book': row('book', 'b1', who='ناشر', note='كتاب عن الإيجار', canReject=True),
    'program': row('program', 'pg1', who='طالب برنامج', note='برنامج الصياغة'),
    'topic': row('topic', 'tp1', who='عضو', note='موضوع عن النفقة'),
    'creative': row('creative', 'cr1', who='مبدع', note='عمل فني', canReject=True),
    'site_message': row('site_message', 44, msgSource='site', msgId=44, who='زائر', note='رسالة'),
    'lead': row('lead', 'l9', who='ليلى', resolve=True, note='محتملة'),
}
PAYOUT = {'kind': 'payout', 'pid': 'p1', 'who': 'سارة', 'email': 's@x.test', 'amount': 500, 'currency': 'EGP', 'dest': 'فودافون', 'status': 'pending',
          'raw': {'amount': 500, 'created_at': '2026-11-12T08:00:00Z'}}
OFFER = {'id': 'o1', 'title': 'دليل المستأجر', 'ownerName': 'ناشر', 'typeText': 'دليل', 'suggestedText': '١٤٩ جنيه', 'at': NOW - 3600e3}
INVITE = {'id': 'iv1', 'email': 'hala@x.test', 'name': 'د. هالة رشدي', 'invitedByLabel': 'سارة', 'status': 'awaiting_approval', 'generation': 2, 'at': NOW - 3600e3, 'note': 'زميلتي'}
BRAIN = lambda iid, sec: {'id': iid, 'producer': 'p', 'section': sec, 'kind': 'note', 'target_label': 'موقع', 'tag': 'اقتراح', 'status': 'proposed', 'body': {'text': 'نص', 'why': ''}, 'created_at': '2026-11-13T05:00:00Z'}


def split(rows, payouts=None, queue=None, **opts):
    fyi = [r for r in rows if r.get('fyi')]
    o = {'now': NOW, 'fyiRows': fyi}
    o.update(opts)
    return v2_node.logic('v2Split', [r for r in rows if not r.get('fyi')], payouts or [], queue, o)


def only(kind_key, **opts):
    out = split([ROWS[kind_key]], **opts)
    cards = out['decisions'] + [c for g in out['fyi']['groups'] for c in g['cards']]
    assert len(cards) == 1, (kind_key, cards)
    return cards[0], out


# ——————————————————————————————————————————————————————— ١. الهيكل والقايمة

@needs_node
def test_sections_in_the_approved_order_with_the_merged_ones():
    out = subprocess.run([v2_node.NODE, '-e', """
const vm=require('vm'),fs=require('fs');const sb={console};sb.window=sb;vm.createContext(sb);
vm.runInContext(fs.readFileSync(%r,'utf8'),sb);const L=sb.V2L;
console.log(JSON.stringify({secs:L.SECTIONS.map(s=>[s.key,s.label,s.tabs.map(t=>[t.key,t.label,!!t.hidden])]),tiles:L.TILE_DEFS.map(t=>[t.key,t.label]),keys:L.SECTION_KEYS}));
""" % os.path.join(DC, 'v2-logic.js')], capture_output=True, text=True, timeout=30)
    d = json.loads(out.stdout)
    assert [s[0] for s in d['secs']] == ['home', 'people', 'files', 'disputes', 'money', 'courses', 'books', 'market', 'content', 'marketing', 'company']
    assert [s[1] for s in d['secs']] == ['اللوحة', 'الناس', 'ملفات الخبراء', 'النزاعات والاستردادات', 'الفلوس', 'الدورات', 'الكتب', 'سوق الخدمات', 'المحتوى', 'التسويق والتقارير', 'الشركة والعقل']
    assert d['keys'] == [s[0] for s in d['secs']][1:]
    assert [t[0] for t in d['tiles']] == d['keys'] and len(d['tiles']) == 10        # ١٠ مربّعات بنفس الترتيب
    tabs = {s[0]: [t[0] for t in s[2]] for s in d['secs']}
    assert tabs['home'] == ['board']                                                 # «كل الوارد» اتشال
    assert tabs['people'] == ['users', 'pipeline', 'invites', 'messages', 'person']  # الرسائل تبويب جوه الناس
    assert 'escrow' not in tabs['disputes'] and 'all' in tabs['disputes']            # «كل السجلات» القديمة بأزرارها اتشالت من النزاعات
    assert tabs['money'] == ['overview', 'payouts', 'receipts', 'prices', 'shares', 'ads']
    assert 'all' not in tabs['courses'] and 'trainers' in tabs['courses']
    assert tabs['marketing'] == ['campaigns', 'social', 'plan', 'report', 'demand', 'sunday']       # التقارير اندمجت
    assert {'brain', 'helpers', 'legacy', 'legacyfin'} <= set(tabs['company']) and 'reports' not in tabs and 'brain' not in tabs
    assert d['secs'][-1][2][-1][2] is True            # «الأهداف» مخفي زي ما كان


@needs_node
def test_old_section_names_and_links_resolve_to_the_new_homes():
    out = subprocess.run([v2_node.NODE, '-e', """
const vm=require('vm'),fs=require('fs');const sb={console};sb.window=sb;vm.createContext(sb);
vm.runInContext(fs.readFileSync(%r,'utf8'),sb);const L=sb.V2L;
const r=h=>{const x=L.routeFor(h,{});return x?[x.section,x.tab]:null};
console.log(JSON.stringify({a:r('#s/reports/report'),b:r('#s/reports'),c:r('#s/brain/log'),d:r('#s/brain/helpers'),e:r('#s/brain'),f:r('#inbox'),g:r('#overview'),
 h:r('#s/home/inbox'),i:r('#s/disputes/escrow'),j:r('#ai'),k:r('#analysis'),l:r('#s/people/invites'),m:[L.sectionByKey('brain').key,L.sectionByKey('reports').key,L.tabByKey('brain','log').key]}));
""" % os.path.join(DC, 'v2-logic.js')], capture_output=True, text=True, timeout=30)
    d = json.loads(out.stdout)
    assert d['a'] == ['marketing', 'report'] and d['b'] == ['marketing', 'report']
    assert d['c'] == ['company', 'brain'] and d['d'] == ['company', 'helpers'] and d['e'] == ['company', 'brain']
    assert d['f'] == ['home', 'board'] and d['g'] == ['home', 'board']          # «كل الوارد» ⇒ اللوحة
    assert d['h'][0] == 'home' and d['i'][0] == 'disputes'                      # تبويب مش موجود ⇒ أول تبويب في القسم
    assert d['j'] == ['company', 'helpers'] and d['k'] == ['marketing', 'report']
    assert d['l'] == ['people', 'invites'] and d['m'] == ['company', 'marketing', 'brain']


def test_legacy_tabs_are_read_only_with_no_action_buttons():
    assert "SH.readOnly" in SHELL_JS and 'v2-ro' in SHELL_JS
    assert "V2SHELL.readOnly(current==='finance'||current==='escrow')" in HTML
    css = SHELL_CSS.split('R24 م٢: «السجلات القديمة» للقراية بس')[1]
    assert '#view.v2-ro .btn' in css and 'display:none!important' in css          # مفيش زرار فعل في السجلات القديمة
    assert 'v2-ro::before' in css and 'مفيش فيها أزرار قرار' in css


def test_the_old_inbox_is_gone_from_navigation_and_the_reading_view_lives_inside_the_section():
    assert "T('inbox', 'كل الوارد'" not in LOGIC_JS
    assert 'v2OpenReading' in HTML and "openReading:function(row,opts){return v2OpenReading(row,opts);}" in HTML
    assert 'function v2ReadingActive' in HTML and 'v2rd-box' in HTML
    # أي فعل جوه الدرج بيرجع لـviewInbox/renderInbox فنحدّث الدرج مش نفتح «الوارد»
    assert re.search(r'function viewInbox\(v\)\{\s*if\(v2ReadingActive\(\)\)\{v2ReadingTick\(\);return;\}', HTML)
    assert re.search(r'function renderInbox\(\)\{\s*if\(v2ReadingActive\(\)\)\{v2ReadingTick\(\);return;\}', HTML)
    assert 'openRow:function(row){return v2OpenReading(row,null);}' in HTML           # «افتح» القديمة بقت درج القراية


# ——————————————————————————————————————————————————————— ٢. بيت كل نوع وأفعاله (جدول التسليم)

# النوع ⇒ (البيت، الفعل الأساسي، فعل ثاني)  — act.do هو دالة التنفيذ في v2-home.js (`run`)
TABLE = {
    'visitor': ('people', 'decide', 'reject_reason'),
    'visitor_flagged': ('people', 'read', None),
    'trainer_solo': ('people', 'decide', 'reject_reason'),
    'join': ('people', 'decide', 'reject_reason'),
    'join_licensed': ('people', 'read', None),
    'founding_new': ('people', 'decide', 'reject_reason'),
    'identity_solo': ('people', 'read', None),
    'site_message': ('people', 'read', None),
    'lead': ('people', 'resolve', 'read'),
    'dispute': ('disputes', 'read', None),
    'legacy': ('disputes', 'read', None),
    'unactivated': ('disputes', 'read', None),
    'review': ('files', 'read', None),
    'attention': ('files', 'read', None),
    'file_nocand': ('files', 'read', None),
    'verify': ('files', 'read', None),
    'file_cand': ('files', 'send', 'read'),
    'manual_payment': ('money', 'pay_confirm', 'pay_reject'),
    'book': ('books', 'decide', 'reject_reason'),
    'program': ('courses', 'decide', 'reject_reason'),
    'topic': ('content', 'decide', 'reject_reason'),
    'creative': ('content', 'decide', 'reject_reason'),
}


@needs_node
@pytest.mark.parametrize('key', sorted(TABLE))
def test_every_type_comes_back_as_a_decision_in_its_home_with_a_real_action(key):
    home, primary, second = TABLE[key]
    c, out = only(key)
    assert out['decisions'] and c['bucket'] == 'decision', key
    assert c['home'] == home and out['counts'][home] == 1 and out['counts']['total'] == 1
    assert c['primary']['act']['do'] == primary, (key, c['primary'])
    assert ((c.get('secondary') or {}).get('act') or {}).get('do') == second if second else True
    assert out['byHome'][home][0]['id'] == c['id']
    assert not out['fyi']['groups'], 'القرار ما يتكررش في «للعلم»'


@needs_node
def test_payout_and_book_offer_and_brain_items_have_their_homes():
    out = split([], [PAYOUT], None, offers=[OFFER], brainItems=[BRAIN('b1', 'content'), BRAIN('b2', 'reports'), BRAIN('b3', 'brain'), BRAIN('b4', 'home'), BRAIN('b5', 'files')])
    homes = {c['kind'] + ':' + c['id'].split('|')[1]: c['home'] for c in out['decisions']}
    assert homes['payout:p1'] == 'money' and homes['book_offer:o1'] == 'books'
    assert homes['brain_item:b1'] == 'content' and homes['brain_item:b5'] == 'files'
    assert homes['brain_item:b2'] == 'marketing' and homes['brain_item:b3'] == homes['brain_item:b4'] == 'company'    # التقارير ⇒ التسويق · العقل/اللوحة ⇒ الشركة
    pay = next(c for c in out['decisions'] if c['kind'] == 'payout')
    assert pay['primary']['act']['do'] == 'payout_settle' and pay['secondary']['act']['do'] == 'payout_reject'


@needs_node
@pytest.mark.parametrize('key,fyi', [('join_waiting', 'join_waiting'), ('founding_contacted', 'founding_follow'), ('signup_free', 'signup'), ('payfail', 'payfail'),
                                      ('gateway', 'gateway'), ('file_sent', 'file_sent')])
def test_real_for_your_information_items_stay_out_of_the_strip(key, fyi):
    out = split([ROWS[key]])
    assert out['decisions'] == [] and out['counts']['total'] == 0
    assert [g['key'] for g in out['fyi']['groups']] == [fyi]
    assert out['fyi']['groups'][0]['home'] in ('people', 'money', 'files')


@needs_node
def test_stuck_payment_and_course_counters_are_for_your_information_with_their_home():
    stuck = [{'id': 'sp1', 'name': 'دافع', 'kindText': 'دورة', 'amountText': '٣٠٠ جنيه', 'provider': 'بطاقة', 'ageHours': 5, 'refundable': True, 'email': 'd@x.test'}]
    out = split([], [], {'courses_pending': {'count': 1, 'titles': ['دورة أ']}, 'live_needs_decision': [{'title': 'حيّة', 'reserved_count': 2, 'quorum': 5}]}, stuck=stuck)
    assert out['decisions'] == []
    homes = {g['key']: g['home'] for g in out['fyi']['groups']}
    assert homes == {'stuck_payment': 'money', 'course': 'courses', 'live': 'courses'}


@needs_node
def test_publishing_and_acceptance_need_a_confirmation_and_rejection_needs_a_reason():
    for key, conf in (('book', 'book'), ('creative', 'creative'), ('topic', 'topic'), ('program', 'program')):
        c, _ = only(key)
        assert c['primary']['act'] == {'do': 'decide', 'action': 'approve', 'confirm': conf}
        assert c['secondary']['act'] == {'do': 'reject_reason'} and c['read']['act'] == {'do': 'read'}   # «اقرأه كامل» جوه القسم
    assert only('creative')[0]['warn'] == 'القبول بينشره للناس' and only('program')[0]['warn'] == ''


# ——————————————————————————————————————————————————————— ٣. الناس: بطاقة لكل شخص

@needs_node
def test_one_card_per_person_groups_every_open_request_by_email():
    out = split([ROWS['visitor'], ROWS['trainer'], ROWS['signup_visitor'], ROWS['trainer_solo'], ROWS['identity']], invites=[dict(INVITE, email=MONA, name='منى')])
    people = out['byHome']['people']
    assert len(people) == 2 and sorted(c['kind'] for c in people) == ['person', 'trainer']
    mona = next(c for c in people if c['kind'] == 'person')
    assert mona['person'] == {'email': MONA, 'name': 'منى عبد الحميد'} and mona['key'] == 'person:' + MONA and mona['dismiss'] is False
    assert mona['merged'] == 4
    assert set(mona['chips']) == {'طلب انضمام — خبير ومدرّب', 'مستند هوية', 'طلب فتح المنصة', 'دعوة من عضو', 'تسجيل جديد'}
    assert len(mona['parts']) == 4 and out['fyi']['groups'] == []                       # التسجيل اتبلع (عند منى طلب فتح)
    # فيه مستند هوية ⇒ القراية الأول: الفعل الأساسي «افتح ملفه» (كل طلب بزراره في صفحته)
    assert mona['primary'] == {'label': 'افتح الملف', 'act': {'do': 'person', 'email': MONA}}
    assert mona['secondary']['act'] == {'do': 'person_reject', 'email': MONA}


@needs_node
def test_a_person_with_only_one_click_requests_gets_accept_all_with_the_exact_steps():
    out = split([ROWS['visitor'], ROWS['trainer'], ROWS['signup_visitor']])
    card = out['byHome']['people'][0]
    assert card['kind'] == 'person' and card['merged'] == 2
    assert card['primary']['label'] == 'اقبل كل الطلبات' and card['primary']['act'] == {'do': 'person_accept', 'email': MONA}
    assert card['primary']['steps'] == ['هتقبل طلب الانضمام كخبير ومدرّب', 'هتفتح المنصة للطلب']
    assert card['secondary']['steps'] == ['هيترفض طلب الانضمام', 'الطلب هيترفض والمنصة مش هتتفتح']
    assert out['fyi']['groups'] == []                       # تسجيله اتبلع جوه البطاقة


@needs_node
def test_signup_is_absorbed_only_when_the_person_has_a_visitor_request():
    out = split([ROWS['trainer'], ROWS['signup_visitor']])                   # منى بلا طلب فتح ⇒ التسجيل «للعلم» مش جوه بطاقتها
    assert [c['kind'] for c in out['byHome']['people']] == ['trainer']
    assert [g['key'] for g in out['fyi']['groups']] == ['signup']
    out = split([ROWS['visitor'], ROWS['signup_visitor']])
    only_card = out['byHome']['people'][0]
    assert only_card['kind'] == 'pending_user' and only_card['chips'] == ['طلب فتح المنصة', 'تسجيل جديد'] and out['fyi']['groups'] == []


@needs_node
def test_invites_awaiting_approval_join_the_person_card_and_stand_alone_otherwise():
    solo = split([], invites=[INVITE])
    c = solo['byHome']['people'][0]
    assert c['kind'] == 'invite' and c['primary']['act'] == {'do': 'invite_approve'} and c['secondary']['act'] == {'do': 'reject_reason'}
    assert c['key'] == 'invite:iv1' and c['sub'] == 'الداعي: سارة، الجيل ٢'
    both = split([row('trainer', 'tt', who='هالة', personEmail='hala@x.test', canReject=True)], invites=[INVITE])
    comp = both['byHome']['people'][0]
    assert comp['kind'] == 'person' and comp['merged'] == 2 and 'دعوة من عضو' in comp['chips']
    assert comp['primary']['steps'][-1] == 'هتوافق على الدعوة (ورابطها يشتغل)'


@needs_node
def test_person_card_snooze_hides_all_its_requests_and_comes_back_when_a_request_is_added():
    key = 'person:' + MONA
    rows = [ROWS['visitor'], ROWS['trainer']]
    base = split(rows)
    fp = base['byHome']['people'][0]['fp']
    entry = {'key': key, 'kind': 'snooze', 'until': '2099-01-01T08:00:00Z', 'fingerprint': fp}
    hid = split(rows, snooze={'map': {key: entry}, 'now': NOW})
    assert hid['counts']['people'] == 0 and hid['decisions'] == []
    assert [s['key'] for s in hid['snoozedBy']['people']] == [key]                   # «مؤجّلة (١)» ببطاقة الشخص نفسها
    back = split(rows + [ROWS['identity']], snooze={'map': {key: entry}, 'now': NOW})  # طلب جديد = حالة اتغيّرت ⇒ يرجع
    assert back['counts']['people'] == 1 and back['byHome']['people'][0]['returned'] == 'رجع لأن حالته اتغيّرت'


# ——————————————————————————————————————————————————————— ٤. العدّاد الواحد

@needs_node
def test_one_counter_tile_strip_and_deck_agree_after_snooze():
    rows = [ROWS[k] for k in ('visitor', 'trainer', 'dispute', 'review', 'topic', 'creative', 'book', 'file_cand', 'manual_payment', 'site_message')]
    snz = {'ok': True, 'at': 1, 'map': {'topic:tp1': {'key': 'topic:tp1', 'kind': 'snooze', 'until': '2099-01-01T08:00:00Z', 'fingerprint': ''}}}
    o = ui({'inbox': rows, 'snooze': snz, 'payouts': [PAYOUT], 'mount': 'content'})
    tiles = {t['key']: t['count'] for t in o['tiles']}
    for k, v in o['counts'].items():
        if k != 'total':
            assert tiles[k] == v == o['strips'][k]['n'], k               # المربّع = الشريط = العدّاد
    assert o['counts']['total'] == sum(tiles.values()) == sum(s['n'] for s in o['strips'].values()) == 9
    assert tiles['content'] == 1 and o['strips']['content']['later'] == 1       # الموضوع اتأجّل: بيرجع في «مؤجّلة (١)»
    assert 'ابدأ القرارات (٩)' in text_of(o['html'])                            # وزر «ابدأ القرارات» بنفس الرقم


@needs_node
def test_a_failed_source_shows_unreachable_not_nothing_waiting():
    o = ui({'inbox': [], 'stateOverride': {'inbox': 'error'}})
    t = {x['key']: x for x in o['tiles']}
    for k in ('people', 'files', 'disputes', 'money', 'courses', 'books', 'content'):
        assert t[k]['failed'] is True and t[k]['next'] == 'تعذّر الوصول', k
    assert t['marketing']['failed'] is False and t['company']['failed'] is False
    txt = text_of(o['html'])
    assert 'تعذّر جلب القرارات' in txt and 'مفيش قرار مستنيك' not in txt     # ⛔ مفيش «مفيش قرار» فوق جلب فاشل
    strip = ui({'inbox': [], 'stateOverride': {'inbox': 'error'}, 'mount': 'files'})['strip']
    assert 'تعذّر جلب قرارات هذا القسم' in strip and 'مفيش حاجة مستنياك هنا' not in strip


# ——————————————————————————————————————————————————————— ٥. الرسم

@needs_node
def test_home_has_the_greeting_hero_ten_photo_tiles_and_the_two_boxes():
    o = ui({'inbox': [ROWS['dispute'], ROWS['topic'], ROWS['signup_free']]})
    html, txt = o['html'], text_of(o['html'])
    assert re.search(r'(صباح|مساء) الخير يا عبد الرحمن (الجمعة|السبت|الأحد|الاثنين|الثلاثاء|الأربعاء|الخميس)', txt)
    assert 'قرارين مستنيينك' in txt and 'ابدأ القرارات (٢)' in txt and 'اللي عمله العقل' in txt
    assert html.count('data-tile=') == 10 and html.count('class="v2-tile') == 10
    assert '١ محتاج قرارك' in txt and txt.count('مفيش حاجة مستنياك') == 8             # المربّعات بعدد القرارات بس
    assert 'v2-cnt' not in html and 'v2-next' not in html                              # الدايرة الرقمية والشريط الكحلي القديم اتشالوا
    assert 'للعلم' in txt and 'العقل عمل لوحده النهارده' in txt and 'لسه مفيش حاجة اتعملت لوحدها' in txt     # صندوقا اللوحة
    assert 'v2-boxes' in html and 'v2-brainbox' in html and 'v2-hero' in html
    assert 'تسجيل جديد' in txt                                                          # التسجيل «للعلم» (مفيش طلب فتح)
    # مفيش قرارات ⇒ سطر هادئ مش نجاح كاذب
    empty = text_of(ui({'inbox': []})['html'])
    assert 'مفيش قرار مستنيك' in empty and 'ابدأ القرارات' not in empty


@needs_node
def test_start_decisions_walks_the_sections_in_order_with_from_and_open_in():
    rows = [ROWS[k] for k in ('topic', 'dispute', 'trainer_solo', 'file_cand', 'manual_payment')]
    o = ui({'inbox': rows, 'payouts': [PAYOUT], 'steps': [{'mode': 'focus'}]})
    kinds = [d.split('|')[0] for d in o['deck']]
    assert kinds == ['trainer', 'file_waiting', 'dispute', 'payout', 'manual_payment', 'topic']      # الناس · الملفات · النزاعات · الفلوس · المحتوى
    txt = text_of(o['html'])
    assert 'من: الناس' in txt and 'افتح في الناس' in txt and 'اقبل الطلب' in txt and 'ارفض بسبب' in txt and 'بعدين' in txt
    # نفس الأزرار والفعل: الزر الأساسي هنا هو نفسه زر الشريط (V2.runCard ⇒ run)
    s = ui({'inbox': rows, 'payouts': [PAYOUT], 'mount': 'people', 'steps': []})['strip']
    assert 'اقبل الطلب' in s and 'ارفض بسبب' in s


@needs_node
def test_every_section_gets_the_strip_and_an_empty_one_is_a_single_line():
    o = ui({'inbox': [ROWS['dispute']], 'mount': 'files'})
    assert 'مفيش حاجة مستنياك هنا' in o['strip'] and 'class="v2z empty"' in o['strip'] and 'data-id=' not in o['strip']
    d = ui({'inbox': [ROWS['dispute'], ROWS['legacy']], 'mount': 'disputes'})
    assert 'محتاج قرارك' in d['strip'] and d['strip'].count('<article') == 2 and 'مفيش حاجة مستنياك هنا' not in d['strip']
    for k in ('people', 'files', 'disputes', 'money', 'courses', 'books', 'market', 'content', 'marketing', 'company'):
        assert 'محتاج قرارك' in ui({'inbox': [], 'mount': k})['strip']


@needs_node
def test_strip_button_runs_the_same_function_the_old_drawer_calls():
    o = ui({'inbox': [ROWS['trainer_solo']], 'mount': 'people', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
    assert {'fn': 'decideInboxItem', 'kind': 'trainer', 'id': 't2', 'ref': 'TRA-t2', 'action': 'approve', 'note': ''} in o['calls']
    assert any(c['fn'] == 'toast' and 'قُبل المدرّب' in c['t'] for c in o['calls'])
    # الإرسال: نفس EP.expertFileSend
    f = ui({'inbox': [ROWS['file_cand']], 'mount': 'files', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
    assert {'fn': 'expertFileSend', 'ref': 'EXP-ef9', 'email': 'e@x.test'} in f['calls']
    # الفلوس: نافذة التأكيد القديمة بالمبلغ (مش تنفيذ مباشر)
    m = ui({'inbox': [ROWS['manual_payment']], 'mount': 'money', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
    assert not [c for c in m['calls'] if c['fn'] == 'decideInboxItem'] and m['modals'] == ['تأكيد الدفع']
    assert '٣٠٠' in m['modal']['html'] and 'أكّد' in m['modal']['html']
    m2 = ui({'inbox': [ROWS['manual_payment']], 'mount': 'money', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}, {'modalClick': '#v2m_go'}]})
    assert {'fn': 'decideInboxItem', 'kind': 'manual_payment', 'id': 'm1', 'ref': 'MAN-m1', 'action': 'approve', 'note': ''} in m2['calls']


@needs_node
def test_read_and_decide_opens_the_reading_view_inside_the_section_never_the_old_inbox():
    o = ui({'inbox': [ROWS['dispute']], 'mount': 'disputes', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
    assert o['calls'][0] == {'fn': 'openReading', 'ref': 'DIS-d1', 'home': 'disputes'}
    assert not [c for c in o['calls'] if c['fn'] == 'openRow']
    gone = ui({'inbox': [ROWS['review']], 'mount': 'files', 'openRowResult': False, 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
    assert any(c['fn'] == 'toast' and c['t'] == 'البند ده اتحل بالفعل' for c in gone['calls'])        # مفيش زرار ميت
    # الأنواع اللي كانت «افتح» بس: كلها بزرارها الحقيقي
    for k in ('legacy', 'unactivated', 'attention', 'identity_solo', 'site_message', 'file_nocand', 'visitor_flagged', 'join_licensed'):
        r = ui({'inbox': [ROWS[k]], 'mount': TABLE[k][0], 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
        assert [c['fn'] for c in r['calls']].count('openReading') == 1, k


@needs_node
def test_publish_asks_first_reject_needs_a_written_reason_and_founding_is_one_tap_confirm():
    # نشر عمل إبداعي: نافذة تأكيد ⇒ بعد «اعتمد» يتنفّذ approve
    o = ui({'inbox': [ROWS['creative']], 'mount': 'content', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
    assert o['modals'] == ['تأكيد النشر'] and not [c for c in o['calls'] if c['fn'] == 'decideInboxItem']
    o = ui({'inbox': [ROWS['creative']], 'mount': 'content', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}, {'modalClick': '#v2m_go'}]})
    assert {'fn': 'decideInboxItem', 'kind': 'creative', 'id': 'cr1', 'ref': 'CRE-cr1', 'action': 'approve', 'note': ''} in o['calls']
    # الرفض: لا يتنفّذ بلا سبب (٥ أحرف على الأقل)، وبعده يوصل السبب كما هو
    steps = [{'strip': '[data-a]', 'attr': {'data-a': 's'}}, {'modalClick': '#v2m_go'}]
    o = ui({'inbox': [ROWS['trainer_solo']], 'mount': 'people', 'steps': steps})
    assert o['modals'] == ['ارفض بسبب'] and not [c for c in o['calls'] if c['fn'] == 'decideInboxItem']
    steps = [{'strip': '[data-a]', 'attr': {'data-a': 's'}}, {'modalType': {'sel': '#v2m_f', 'value': 'الأوراق ناقصة'}}, {'modalClick': '#v2m_go'}]
    o = ui({'inbox': [ROWS['trainer_solo']], 'mount': 'people', 'steps': steps})
    assert {'fn': 'decideInboxItem', 'kind': 'trainer', 'id': 't2', 'ref': 'TRA-t2', 'action': 'reject', 'note': 'الأوراق ناقصة'} in o['calls']
    # «ليس مناسبًا» للمؤسس: تأكيد بلا سبب
    o = ui({'inbox': [ROWS['founding_new']], 'mount': 'people', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 's'}}, {'modalClick': '#v2m_go'}]})
    assert o['modals'] == ['ليس مناسبًا'] and {'fn': 'decideInboxItem', 'kind': 'founding', 'id': 'f1', 'ref': 'FOU-f1', 'action': 'reject', 'note': ''} in o['calls']


@needs_node
def test_accept_all_lists_the_exact_steps_runs_them_in_order_and_stops_at_the_first_failure():
    rows = [ROWS['visitor'], ROWS['trainer']]
    o = ui({'inbox': rows, 'mount': 'people', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
    t = text_of(o['modal']['html'])
    assert o['modals'] == ['قبول كل طلبات منى عبد الحميد'] and '١ هتقبل طلب الانضمام كخبير ومدرّب' in t and '٢ هتفتح المنصة للطلب' in t
    assert not [c for c in o['calls'] if c['fn'] == 'decideInboxItem']                              # التأكيد الأول
    o = ui({'inbox': rows, 'mount': 'people', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}, {'modalClick': '#v2m_go'}]})
    dec = [(c['kind'], c['action']) for c in o['calls'] if c['fn'] == 'decideInboxItem']
    assert dec == [('trainer', 'approve'), ('pending_user', 'approve')]                              # كل طلب بفعل بيته
    # أول خطوة فشلت ⇒ الثانية ما اتنفّذتش، والرسالة بتقول اللي حصل
    o = ui({'inbox': rows, 'mount': 'people', 'failOn': 'trainer', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}, {'modalClick': '#v2m_go'}]})
    assert [(c['kind']) for c in o['calls'] if c['fn'] == 'decideInboxItem'] == ['trainer']
    # رفض كل الطلبات بسبب واحد يوصل لكل طلب
    steps = [{'strip': '[data-a]', 'attr': {'data-a': 's'}}, {'modalType': {'sel': '#v2m_f', 'value': 'بيانات غير مكتملة'}}, {'modalClick': '#v2m_go'}]
    o = ui({'inbox': rows, 'mount': 'people', 'steps': steps})
    assert [(c['kind'], c['action'], c['note']) for c in o['calls'] if c['fn'] == 'decideInboxItem'] == [('trainer', 'reject', 'بيانات غير مكتملة'), ('pending_user', 'reject', 'بيانات غير مكتملة')]


@needs_node
def test_invite_approval_and_rejection_use_the_invite_functions_with_ok_or_error():
    o = ui({'invites': [INVITE], 'mount': 'people', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
    assert {'fn': 'decideInvite', 'id': 'iv1', 'action': 'approve', 'note': ''} in o['calls']
    steps = [{'strip': '[data-a]', 'attr': {'data-a': 's'}}, {'modalType': {'sel': '#v2m_f', 'value': 'مش مناسب'}}, {'modalClick': '#v2m_go'}]
    o = ui({'invites': [INVITE], 'mount': 'people', 'steps': steps})
    assert {'fn': 'decideInvite', 'id': 'iv1', 'action': 'reject', 'note': 'مش مناسب'} in o['calls']
    assert 'EP.decideInvite = function (id, action, noteText)' in API_JS and 'ok: true' in API_JS.split('EP.decideInvite')[1][:600]


@needs_node
def test_snooze_from_the_strip_saves_on_the_server_with_the_person_key_and_dismiss_is_not_offered_for_waiting_people():
    o = ui({'inbox': [ROWS['visitor'], ROWS['trainer']], 'mount': 'people'})
    assert 'data-a="l"' in o['strip'] and 'data-a="d"' not in o['strip']                    # «بعدين» آه · «تجاهل» لا (صاحبه مستني رد)
    s = ui({'inbox': [ROWS['visitor'], ROWS['trainer']], 'mount': 'people', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'l'}}, {'modalClick': '.v2z-pick', 'idx': 0}]})
    sn = [c for c in s['calls'] if c['fn'] == 'snoozeItem']
    assert len(sn) == 1 and sn[0]['key'] == 'person:' + MONA and sn[0]['until'] and sn[0]['fp']
    # «تجاهل» متاح لتسجيل/دفع فاشل بس — وبسبب
    d = ui({'inbox': [], 'mount': 'money', 'steps': []})
    assert 'data-a="d"' not in d['strip']


@needs_node
def test_the_strip_lists_what_is_snoozed_or_dismissed_with_a_restore_button():
    snz = {'ok': True, 'at': 1, 'map': {'topic:tp1': {'key': 'topic:tp1', 'kind': 'snooze', 'until': '2099-01-01T08:00:00Z', 'fingerprint': ''}}}
    o = ui({'inbox': [ROWS['topic'], ROWS['creative']], 'snooze': snz, 'mount': 'content',
            'snoozed': [], 'steps': [{'strip': '[data-l]', 'attr': {'data-l': 'later'}}]})
    assert 'مؤجّلة (١)' in text_of(o['strip']) and o['strips']['content']['n'] == 1
    o2 = ui({'inbox': [ROWS['creative']], 'snoozed': [{'row': ROWS['topic'], 'entry': snz['map']['topic:tp1'], 'key': 'topic:tp1'}], 'snooze': snz, 'mount': 'content'})
    assert 'مؤجّلة (١)' in text_of(o2['strip'])


@needs_node
def test_brain_suggestions_are_cards_in_their_section_strip_exactly_once():
    items = [BRAIN('b1', 'content'), BRAIN('b2', 'content'), BRAIN('b3', 'reports')]
    o = ui({'inbox': [], 'brain': items, 'mount': 'content'})
    assert o['strips']['content']['n'] == 2 and o['strips']['marketing']['n'] == 1
    assert o['strip'].count('<article') == 2 and 'اقتراح' in o['strip']
    # الاقتراح بيتنفّذ بنفس منفّذ العقل
    r = ui({'inbox': [], 'brain': items, 'mount': 'content', 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
    assert any(c['fn'] == 'brainAct' for c in r['calls'])
    # والشريط القديم (تحت الترويسة) اتدمج: ما بيرسمش حاجة تاني
    code = BRAIN2_JS.split('function mountBar(section, el) {')[1][:700]
    assert 'hide(el); return;' in code and 'R24 م٢' in code


# ——————————————————————————————————————————————————————— ٦. صفحة الشخص (الخادم)

import app as appmod  # noqa: E402

P_EMAIL = 'mona@x.test'
USERS = {'users': [{'id': 'u-mona', 'full_name': 'منى عبد الحميد', 'email': P_EMAIL, 'role': 'member', 'trainer_status': 'pending', 'is_active': True, 'created_at': '2026-11-01T08:00:00Z'}]}
SOURCES = {
    '/api/bridge/users': USERS,
    '/api/bridge/invites': {'invites': [{'id': 'iv1', 'email': P_EMAIL, 'name': 'منى', 'status': 'awaiting_approval', 'invited_by': {'kind': 'member', 'name': 'سارة'}, 'created_at': '2026-11-12T08:00:00Z', 'generation': 2, 'note': 'زميلتي'},
                            {'id': 'iv2', 'email': 'other@x.test', 'name': 'غيرها', 'status': 'awaiting_approval', 'invited_by': {'kind': 'founder'}, 'created_at': '2026-11-12T08:00:00Z'}]},
    '/api/bridge/experts': {'experts': []}, '/api/bridge/courses': {'courses': []}, '/api/bridge/expert-files': {'files': [], 'total': 0},
    '/api/bridge/wallet-payouts': {'payouts': []},
    '/api/bridge/pending-users': {'users': [{'id': 'u-mona', 'email': P_EMAIL, 'full_name': 'منى عبد الحميد', 'country': 'مصر', 'role_requested': 'lawyer', 'created_at': '2026-11-01T08:00:00Z',
                                             'invite_request': {'status': 'requested', 'requested_at': '2026-11-12T10:00:00Z'}, 'flag_labels': ['حساب مكرر']}]},
    '/api/bridge/trainer-applications': {'applications': [{'id': 't1', 'user_email': P_EMAIL, 'user_name': 'منى', 'join_as': 'both', 'headline': 'محامية بالنقض', 'created_at': '2026-11-10T08:00:00Z'},
                                                         {'id': 't2', 'user_email': 'x@x.test', 'join_as': 'trainer', 'created_at': '2026-11-10T08:00:00Z'}]},
    '/api/bridge/join-requests': {'requests': [{'id': 'j1', 'user_email': P_EMAIL, 'status': 'pending', 'service_label': 'استشارة', 'licensed': True, 'submitted_at': '2026-11-11T08:00:00Z'},
                                               {'id': 'j2', 'user_email': P_EMAIL, 'status': 'needs_info', 'service_label': 'ترجمة', 'submitted_at': '2026-11-11T09:00:00Z'},
                                               {'id': 'j3', 'user_email': P_EMAIL, 'status': 'granted', 'service_label': 'قديم'}]},
    '/api/bridge/founding-expert-leads': {'leads': [{'id': 'f1', 'email': P_EMAIL, 'name': 'منى', 'status': 'invited', 'specialization': 'عقود', 'created_at': '2026-11-09T08:00:00Z'},
                                                   {'id': 'f2', 'email': P_EMAIL, 'status': 'converted'}]},
    '/api/bridge/identity-docs': {'items': [{'user_id': 'u-mona', 'email': P_EMAIL, 'name': 'منى', 'title': 'محامية', 'submitted_at': '2026-11-12T11:00:00Z', 'status': 'pending'}]},
    '/api/bridge/signups/recent': {'signups': [{'user_id': 'u-mona', 'email': P_EMAIL, 'full_name': 'منى', 'provider': 'google', 'where': 'مصر', 'created_at': '2026-11-01T08:00:00Z'}]},
}


def _admin_headers():
    import datetime
    import jwt
    from werkzeug.security import generate_password_hash
    with flask_app.app_context():
        db.create_all()
        u = appmod.User.query.filter_by(email='r24p2-admin@x.test').first()
        if not u:
            u = appmod.User(email='r24p2-admin@x.test', password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name='a', role='admin', dashboard_role='admin',
                            linked_to_name='', preferred_currency='AUTO', is_active=True)
            db.session.add(u)
            db.session.commit()
        tok = jwt.encode({'user_id': u.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture
def person_api(monkeypatch):
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', 'secret')
    seen = []

    def pull(path, params=None):
        seen.append((path, dict(params or {})))
        for k, v in SOURCES.items():
            if path == k:
                return v
        return None

    def boom(*a, **k):
        raise AssertionError('نداء للمنصة ممنوع')
    monkeypatch.setattr(appmod, '_v2_pull', pull)
    monkeypatch.setattr(appmod.requests, 'request', boom)
    monkeypatch.setattr(appmod.requests, 'get', boom)
    return seen


def test_person_page_returns_every_open_request_on_the_email(person_api):
    c = flask_app.test_client()
    d = c.get('/api/v2/person?email=' + P_EMAIL, headers=_admin_headers()).get_json()
    reqs = d['requests']
    kinds = sorted((r['kind'], r['id']) for r in reqs)
    assert kinds == [('founding', 'f1'), ('identity_doc', 'u-mona'), ('invite', 'iv1'), ('join', 'j1'), ('join', 'j2'), ('pending_user', 'u-mona'), ('signup', 'u-mona'), ('trainer', 't1')]
    by = {(r['kind'], r['id']): r for r in reqs}
    assert by[('join', 'j2')]['waiting'] is True and by[('join', 'j1')]['licensed'] is True       # مستني رد صاحبه · مرخَّصة
    assert by[('founding', 'f1')]['status'] == 'invited'                                          # الخطوة الجاية بتتحسب في الواجهة
    assert by[('pending_user', 'u-mona')]['flags'] == ['حساب مكرر'] and by[('trainer', 't1')]['join_as'] == 'both'
    assert by[('invite', 'iv1')]['invited_by'] == 'سارة' and by[('invite', 'iv1')]['generation'] == 2
    assert all(r.get('at') for r in reqs) and [r['at'] for r in reqs] == sorted(r['at'] for r in reqs)      # الأقدم أولًا
    assert d['request_sources'] == {'trainer': 'ok', 'join': 'ok', 'founding': 'ok', 'identity_doc': 'ok', 'signup': 'ok', 'pending_user': 'ok', 'invite': 'ok'}
    assert 'x@x.test' not in json.dumps(d) and 'other@x.test' not in json.dumps(d)                 # ولا طلب لحد غيره
    paths = {p for p, _ in person_api}
    assert {'/api/bridge/trainer-applications', '/api/bridge/join-requests', '/api/bridge/founding-expert-leads', '/api/bridge/identity-docs', '/api/bridge/signups/recent'} <= paths
    assert dict(person_api)['/api/bridge/join-requests'] == {'status': 'open'} and dict(person_api)['/api/bridge/trainer-applications'] == {'status': 'pending'}


def test_a_source_that_failed_is_announced_not_read_as_no_requests(person_api, monkeypatch):
    SOURCES_BAK = dict(SOURCES)
    try:
        SOURCES.pop('/api/bridge/join-requests'); SOURCES.pop('/api/bridge/founding-expert-leads')
        d = flask_app.test_client().get('/api/v2/person?email=' + P_EMAIL, headers=_admin_headers()).get_json()
    finally:
        SOURCES.clear(); SOURCES.update(SOURCES_BAK)
    assert d['request_sources']['join'] == 'failed' and d['request_sources']['founding'] == 'failed' and d['request_sources']['trainer'] == 'ok'
    assert not [r for r in d['requests'] if r['kind'] in ('join', 'founding')] and [r for r in d['requests'] if r['kind'] == 'trainer']


def test_a_founding_lead_without_an_account_still_gets_a_page_with_the_request(person_api):
    SOURCES_BAK = dict(SOURCES)
    try:
        SOURCES['/api/bridge/users'] = {'users': []}
        SOURCES['/api/bridge/founding-expert-leads'] = {'leads': [{'id': 'f9', 'email': 'new.lead@x.test', 'name': 'فادي مؤسس', 'status': 'new', 'specialization': 'تجاري'}]}
        d = flask_app.test_client().get('/api/v2/person?email=new.lead@x.test', headers=_admin_headers()).get_json()
    finally:
        SOURCES.clear(); SOURCES.update(SOURCES_BAK)
    assert d['found'] is False and [(r['kind'], r['id'], r['name']) for r in d['requests']] == [('founding', 'f9', 'فادي مؤسس')]


@needs_node
def test_person_page_logic_builds_buttons_with_their_home_actions_and_the_founding_follow_line():
    resp = {'email': P_EMAIL, 'found': True, 'sources': {}, 'roles': ['visitor'], 'identity': {'name': 'منى', 'is_active': True}, 'expert': None, 'trainer': None, 'money': None, 'learner': None, 'books': None, 'log': [],
            'requests': [{'kind': 'trainer', 'id': 't1', 'at': '2026-11-10T08:00:00Z', 'name': 'منى', 'join_as': 'trainer', 'headline': 'محامية'},
                         {'kind': 'founding', 'id': 'f1', 'at': '2026-11-09T08:00:00Z', 'name': 'منى', 'status': 'invited', 'spec': 'عقود'},
                         {'kind': 'founding', 'id': 'f3', 'at': '2026-11-09T08:00:00Z', 'name': 'منى', 'status': 'new', 'spec': 'عقود'},
                         {'kind': 'identity_doc', 'id': 'u1', 'at': '2026-11-12T08:00:00Z', 'name': 'منى', 'title': 'محامية'},
                         {'kind': 'invite', 'id': 'iv1', 'at': '2026-11-12T08:00:00Z', 'name': 'منى', 'invited_by': 'سارة'},
                         {'kind': 'signup', 'id': 'u1', 'at': '2026-11-01T08:00:00Z', 'name': 'منى', 'provider': 'google'}],
            'request_sources': {'trainer': 'failed'}}
    vm = v2_node.logic('v2Person', resp, NOW, P_EMAIL)
    assert vm['requestsFailed'] == ['طلبات الانضمام'] and [r['kind'] for r in vm['requests']] == ['trainer', 'founding', 'founding', 'identity_doc', 'invite', 'signup']
    cards = v2_node.logic('v2PersonCards', vm['requests'], [], P_EMAIL, NOW)
    by = {x['req']['kind'] + x['req']['id']: x['card'] for x in cards}
    assert by['trainert1']['primary']['act']['do'] == 'decide' and by['trainert1']['secondary']['act']['do'] == 'reject_reason'
    assert by['foundingf1']['follow'] is True and by['foundingf1']['primary']['label'] == 'تم التحويل إلى مدرّب'        # مسار متابعة مش قرار بيرجع
    assert by['foundingf3']['follow'] is False and by['foundingf3']['primary']['label'] == 'تم التواصل'
    assert by['identity_docu1']['primary']['act']['do'] == 'read' and by['inviteiv1']['primary']['act']['do'] == 'invite_approve'
    assert by['signupu1']['primary']['label'] == 'تمام، اطّلعت'
    unreg = dict(resp, found=False, identity=None)
    assert v2_node.logic('v2Person', unreg, NOW, P_EMAIL)['unregistered'] is True            # بلا حساب: الصفحة بتتفتح بطلباته
    assert v2_node.logic('v2Person', dict(unreg, requests=[]), NOW, P_EMAIL)['state'] == 'notfound'


def test_person_page_draws_the_requests_with_their_buttons_and_the_follow_line():
    assert 'function personRequests(vm)' in D2_JS and 'الطلبات المفتوحة' in D2_JS and 'V2STRIP.wire(rqRoot, S.reqCards' in D2_JS
    assert "x.card.reqKind === 'founding' && x.card.follow" in D2_JS and 'خبير مؤسس في المتابعة' in D2_JS
    assert "ep().api('/v2/person" in D2_JS.replace('E.api', 'ep().api') or "E.api('/v2/person?email='" in D2_JS


# ——————————————————————————————————————————————————————— ٧. ثابت: التكرارات · الشحن · الشكل · الدليل

def test_duplicate_decision_places_are_gone():
    # ملفات الخبراء ⇐ الخبراء: ردود دعوة المؤسس اتشالت (القرار في الناس)
    assert 'setFoundingLeadStatus' not in EXPERTS_JS and 'foundingLeads' not in EXPERTS_JS and 'data-a="lead"' not in EXPERTS_JS
    # الدورات ⇐ المدرّبون: قايمة للقراية بس (مفيش قبول/رفض/أزرار مدرّب)
    tr = COURSES_JS.split('function drawTrainers(v) {')[1].split('// ------------------------------------------------------------------ الدورات الحيّة')[0]
    assert 'appaccept' not in tr and 'appreject' not in tr and 'appTicketHtml' not in tr and 'data-a="tstop"' not in COURSES_JS.split('function trainerRowHtml')[1].split('function overdueCount')[0]
    assert 'طلبات الانضمام (مدرّب أو خبير) في «الناس»' in tr
    # الناس ⇐ الطلبات: قائمة الانتظار وسجّلوا بس (مفيش أعمدة قرار)
    dr = PEOPLE_JS.split('function drawRequests(v) {')[1].split('function laterHtml')[0]
    assert 'قائمة الانتظار' in dr and "colHtml(k, R.cols[k]" not in dr and 'REQ_ORDER.map' not in dr
    # الفلوس والكتب: التذكرة بتوصّل للشريط بدل زرار القرار
    pay = D3_JS.split('function payRow')[1].split('function barsHtml')[0]
    assert 'data-a="settle"' not in pay and 'data-a="tostrip"' in pay
    assert 'data-a="settle"' not in D3_JS.split('function payoutTicket')[1].split('function minPayoutBar')[0]
    rec = D3_JS.split('function receiptTicket')[1].split('function stuckTicket')[0]
    assert 'data-a="rconfirm"' not in rec and 'data-a="rreject"' not in rec and 'data-a="tostrip"' in rec
    assert 'data-a="oapprove" data-id' not in D3_JS and 'data-a="oreject" data-id' not in D3_JS      # شاشة العروض ما فيهاش زرّي القرار
    assert 'اعتمد هذه الأسعار</button>' not in D3_JS
    # تذكرة الملف: «افتح الملف» (أرسله إلى … في الشريط)
    assert "var isSend = t.primary && t.primary.act && t.primary.act.do === 'send';" in D2_JS and 'sendTicket(board, t); else' not in D2_JS


def test_user_chips_visitor_and_trainer_pending_link_to_the_cards_instead_of_acting():
    assert "data-a=\"tostrip\" data-email=" in PEOPLE_JS and 'فيه طلب في «محتاج قرارك»' in PEOPLE_JS
    assert 'دي فلتر للقراية بس' in PEOPLE_JS and "S.users.filter.role === 'trainer_pending'" in PEOPLE_JS


def test_new_files_are_shipped_by_the_dockerfile_and_loaded_by_index():
    assert 'dashboard-cloud/v2-strip.js' in DOCKERFILE and 'dashboard-cloud/v2-strip.css' in DOCKERFILE
    assert '<link rel="stylesheet" href="v2-strip.css"><script src="v2-strip.js"></script>' in HTML
    # كل ملف جذر الواجهة اللي index.html بيحمّله لازم يتشحن (نمط R22: ملف بيتحمّل وما بيتشحنش = شاشة ميتة)
    root_files = set(re.findall(r'(?:src|href)="((?!https?:|v2s/)[\w.-]+\.(?:js|css))"', HTML))
    for f in root_files:
        assert 'dashboard-cloud/' + f in DOCKERFILE, f
    # ولا ملف خادم جديد في م٢ (التعديلات في app.py وv2_decisions_routes.py الموجودين، وكلاهما في الـDockerfile)
    assert 'COPY backend/app.py' in DOCKERFILE and 'COPY backend/v2_decisions_routes.py' in DOCKERFILE


def test_decisions_routes_know_the_person_and_invite_keys():
    src = _read('backend', 'v2_decisions_routes.py')
    assert "'person'," in src.split('KNOWN_TYPES')[1].split('])')[0] and "'invite'," in src.split('KNOWN_TYPES')[1].split('])')[0]
    refused = src.split('DISMISS_REFUSED_MONEY_OR_WAITING')[1].split('])')[0]
    assert "'person'" in refused and "'invite'" in refused                    # بطاقة الشخص ودعوته: «بعدين» أو «ارفض بسبب» — مفيش «تجاهل»


def test_the_new_look_light_sidebar_paper_wine_and_no_leftover_old_look():
    # قايمة فاتحة بنص بس + عدّاد في دايرة + «—» لو مفيش
    assert "'<span class=\"v2s-dash\" aria-label=\"مفيش حاجة مستنياك\">—</span>'" in SHELL_JS and 'v2s-ph' not in SHELL_JS.split('function sideItem')[1].split('function userBlock')[0]
    assert 'background:#FBF8F4' in SHELL_CSS and '.v2s-item.on{background:#9E2B4E' in SHELL_CSS and '.v2s-ph{display:none}' in SHELL_CSS
    assert '#F7F3ED' in SHELL_CSS and '#FBFAF7' not in SHELL_CSS                         # الورق المعتمد
    # الشريط الكحلي القديم («القرار التالي») اتشال، والاستبدال هيرو بيضاء
    assert '.v2-next' not in HOME_CSS and 'القرار التالي' not in HOME_JS and 'v2-hero' in HOME_JS
    assert re.search(r'IBM Plex Sans Arabic', HOME_CSS) and '--v2-wine:#9E2B4E' in HOME_CSS and '--v2-paper:#F7F3ED' in HOME_CSS
    # لا «·» ملاصقة لرقم عربي في النصوص الجديدة
    for src in (HOME_JS, STRIP_JS, D2_JS):
        for lit in re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", src):
            assert not re.search(r'[٠-٩0-9]\s*·|·\s*[٠-٩0-9]', lit), lit


def test_claude_md_records_the_new_structure_with_date_and_approval():
    line = [l for l in CLAUDE_MD.splitlines() if 'القائمة' in l and 'عنصر' in l][0]
    assert '١١ عنصر' in line and '2026-11-13' in line and 'موافقة المؤسس' in line
    assert 'التسويق والتقارير' in line and 'الشركة والعقل' in line and 'مترجعش' in line
    assert 'القائمة ١٣ عنصر' not in CLAUDE_MD


# ——————————————————————————————————————————————————————— ٨. الغلاف الحقيقي (v2-shell.js في node:vm)

def shell(payload):
    proc = subprocess.run([v2_node.NODE, os.path.join(_HERE, 'uiharness', 'r24p2_shell.js')], input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-1500:]
    return json.loads(proc.stdout)


@needs_node
def test_light_sidebar_lists_the_eleven_items_in_order_with_the_decision_count_and_a_dash_when_none():
    o = shell({'inbox': [ROWS['dispute'], ROWS['legacy'], ROWS['topic']], 'section': 'disputes', 'tab': 'disputes'})
    names = re.findall(r'<span class="v2s-name">([^<]+)</span>', o['side'])
    assert names == ['اللوحة', 'الناس', 'ملفات الخبراء', 'النزاعات والاستردادات', 'الفلوس', 'الدورات', 'الكتب', 'سوق الخدمات', 'المحتوى', 'التسويق والتقارير', 'الشركة والعقل']
    assert o['side'].count('class="v2s-item') == 11 and o['side'].count('v2s-ph') == 0                    # بلا صور ولا دايرة فوتو (قايمة فاتحة بنص)
    items = re.findall(r'<a class="v2s-item[^"]*"[^>]*>(.*?)</a>', o['side'])
    tail = {re.search(r'v2s-name">([^<]+)', i).group(1): re.sub(r'<[^>]+>', '', i.split('</span>', 1)[1]) for i in items}
    assert tail['النزاعات والاستردادات'] == '٢' and tail['المحتوى'] == '١' and tail['الناس'] == '—' and tail['الفلوس'] == '—' and tail['اللوحة'] == ''
    assert re.search(r'<a class="v2s-item on"[^>]*aria-current="page"[^>]*><span class="v2s-name">النزاعات والاستردادات', o['side'])      # القسم الحالي
    assert 'v2s-tile' in o['sheet'] and o['sheet'].count('class="v2s-tile') == 11                       # ورقة الموبايل بنفس الأقسام


@needs_node
def test_every_section_header_has_the_strip_mounted_and_the_detail_pages_and_home_do_not():
    for sec, tab, hidden in (('files', 'files', False), ('people', 'users', False), ('company', 'brain', False), ('marketing', 'report', False),
                              ('people', 'person', True), ('courses', 'course', True), ('home', 'board', True)):
        o = shell({'inbox': [ROWS['dispute']], 'section': sec, 'tab': tab})
        assert o['strip']['hidden'] is hidden, (sec, tab)
        if not hidden:
            assert 'محتاج قرارك' in o['strip']['html'], (sec, tab)
    o = shell({'inbox': [], 'section': 'books', 'tab': 'books'})
    assert 'مفيش حاجة مستنياك هنا' in o['strip']['html']
    # ترويسة القسم: الوصف الثابت (مش «ن محتاج قرارك» المكرّر مع الشريط)
    h = shell({'inbox': [ROWS['dispute']], 'section': 'money', 'tab': 'overview'})['head']
    assert 'كل جنيه دخل' in h and 'محتاج قرارك' not in h


def test_header_line_is_not_the_tile_count_anymore():
    body = SHELL_JS.split('function descOf(sec, T) {')[1].split('function drawHead')[0]
    assert 'return own || sec.desc;' in body and 't.next' not in body
