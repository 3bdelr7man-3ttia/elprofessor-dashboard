# -*- coding: utf-8 -*-
"""«العقل» الجولة ٢ — بطاقات الرأي والاقتراحات وشريط «ما كتبه العقل هنا» (الواجهة فقط، P4). SPEC docs/v2/brain2/SPEC.md §4 و§5.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_ui.py

⛔ صفر شبكة: الدوال النقية في `v2-logic.js` (`v2bFacts` · `v2bDecorate` · `v2bItemCard` وخطّافا `v2Card`/`v2Decisions`) بتتشغّل في node بمدخلات JSON،
و`v2-brain2.js` بيتحمّل في node:vm بنافذة ومؤقّتات وساعة مزيّفة وخادم مزيّف (ما فيه `fetch` حقيقي). اللقطات (المتصفح الحقيقي) في
`uiharness/v2_shots_brain2.py`. ⛔ لا نداء ذكاء اصطناعي: المتصفح لا يكلّم غير مسارات `/api/v2/brain/*` وهي هنا جدول في الذاكرة.
"""
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node  # noqa: E402

DC = os.path.join(ROOT, 'dashboard-cloud')
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
NOW = 1793361600000          # 2026-10-30T12:00:00Z
H = 3600e3
ALLOWED = set('tag age sub warn reason static_line facts money_text objection expert_reply hours_held headline specialty years attachments '
              'method dispute_check fx_alert type suggested_price price_note service licensed licence_missing body topic'.split())
MONEY = ['payout', 'manual_payment', 'stuck_payment', 'unactivated', 'legacy', 'file_attention', 'dispute']


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


HTML = _read('dashboard-cloud', 'index.html')
LOGIC = _read('dashboard-cloud', 'v2-logic.js')
BRAIN_JS = _read('dashboard-cloud', 'v2-brain2.js')
BRAIN_CSS = _read('dashboard-cloud', 'v2-brain2.css')
HOME_JS = _read('dashboard-cloud', 'v2-home.js')
SHELL_JS = _read('dashboard-cloud', 'v2-shell.js')
SEC_HOME_JS = _read('dashboard-cloud', 'v2s', 'home.js')
SEC_PEOPLE_JS = _read('dashboard-cloud', 'v2s', 'people.js')


def _iso(hours_ago):
    import datetime
    return datetime.datetime.fromtimestamp((NOW - hours_ago * H) / 1000.0, datetime.timezone.utc).isoformat()


def _block():
    m = re.search(r'// ===== brain2 =====\n(.*?)// ===== /brain2 =====', LOGIC, re.S)
    assert m, 'brain2 block missing'
    return m.group(1)


# ---------------------------------------------------------------- صفوف للتجربة
TRAINER = {'apiKind': 'trainer', 'apiId': 't1', 'ref': 'T1', 'who': 'د. هالة سمير', 'personEmail': 'hala.s@example.test',
           'trHeadline': 'محكّمة معتمدة اتصل على 01012345678 أو hala.s@example.test', 'trSpec': 'عقود', 'trYears': '١٢', 'trAttach': 2,
           'note': 'محكّمة — اعتمد', 'ts': NOW - 50 * H}
JOIN = {'apiKind': 'join', 'apiId': 'j1', 'ref': 'J1', 'who': 'أ. مها الجبالي', 'serviceLabel': 'مراجعة العقود', 'licensed': True,
        'licenceMissing': True, 'licenceNote': 'الترخيص بلا رقم قيد', 'ts': NOW - 10 * H}
VISITOR = {'apiKind': 'pending_user', 'apiId': 'p1', 'ref': 'P1', 'who': 'نور الهدى', 'puCountry': 'مصر', 'ts': NOW - 5 * H}
LEAD = {'apiKind': 'lead', 'apiId': 'l1', 'ref': 'LEAD-l1', 'who': 'كريم عادل', 'resolve': True, 'ts': NOW - 3 * H,
        'note': 'أريد استشارة، رقمي +20 100 123 4567 وبريدي karim@example.test', 'body': 'أريد استشارة، رقمي +20 100 123 4567 وبريدي karim@example.test', 'topic': 'عقد إيجار'}
MESSAGE = {'apiKind': 'message', 'apiId': 'm1', 'ref': 'PMSG-m1', 'who': 'دينا فؤاد', 'resolve': True, 'ts': NOW - 4 * H, 'msgSource': 'platform',
           'email': 'dina@example.test', 'note': 'سؤال عن الباقات', 'body': 'سؤال عن الباقات', 'topic': 'الاشتراك'}
DISPUTE = {'apiKind': 'dispute', 'dsrc': 'file', 'apiId': 'f9', 'who': 'منى الشريف', 'amountLabel': '٥٠٠ ريال',
           'ef': {'title': 'عقد توريد', 'client_first_name': 'منى الشريف', 'expert_name': 'م. سامي فؤاد', 'dispute': {'at': _iso(60), 'note': 'لم يصلني الرأي', 'expert_reply': 'سُلّم في الموعد'}},
           'note': 'اعتراض على التأخير — لم يصلني الرأي', 'sub2': 'اعتراض على التأخير'}
PAYOUT = {'apiKind': 'payout', 'pid': 'p9', 'status': 'pending', 'who': 'سارة محمد', 'email': 'sara@example.test', 'amount': 600.5, 'currency': 'EGP', 'dest': 'إنستاباي',
          'raw': {'amount': 600.5, 'method': 'إنستاباي', 'created_at': _iso(20)}, 'fx_alert': False}
RECEIPT = {'apiKind': 'manual_payment', 'apiId': 'r1', 'ref': 'PAY-r1', 'who': 'خالد منصور', 'amount': 1200, 'currency': 'EGP', 'payMethod': 'تحويل بنكي',
           'payWhat': 'اشتراك', 'payRef': 'IP-77', 'personEmail': 'khaled@example.test'}
FILE_WAIT = {'apiKind': 'expert_file', 'apiId': 'ef1', 'efLane': 'waiting', 'ef': {'id': 'ef1', 'status': 'awaiting_assignment', 'title': 'ملف', 'paid_at': _iso(5)}, 'who': 'عميل'}
OFFER = {'id': 'o1', 'title': 'كتاب الصياغة', 'typeText': 'كتاب', 'ownerName': 'أ. دعاء', 'suggestedText': '٢٠٠ جنيه', 'brain': 'عرض جديد', 'at': NOW - 8 * H}


def card(row, **opts):
    return v2_node.logic('v2Card', row, dict(now=NOW, **opts))


def facts(c, now=NOW):
    return v2_node.logic('v2bFacts', c, now)


def ready(text='رأي', recommend='', why='', ago_h=3):
    return {'state': 'ready', 'item': {'created_at': _iso(ago_h), 'body': {'text': text, 'recommend': recommend, 'why': why}}}


# ================================================================ ١) الربط الثابت
def test_index_html_loads_the_files_right_after_d3():
    line = '<link rel="stylesheet" href="v2-brain2.css"><script src="v2-brain2.js"></script>'
    assert HTML.count(line) == 1
    assert HTML.index('<script src="v2-d3.js"></script>') < HTML.index(line)
    after = HTML[HTML.index('<script src="v2-d3.js"></script>'):HTML.index(line)]
    assert after.count('<script') == 1 and '<link' not in after       # «بعد v2-d3.js» مباشرة، لا شيء بينهما


def test_shell_creates_the_bar_next_to_the_search_bar_and_mounts_it_from_drawhead():
    assert "bbar.id = 'v2bbar'" in SHELL_JS and "bbar.className = 'v2-bbar'" in SHELL_JS and 'bbar.hidden = true' in SHELL_JS
    assert SHELL_JS.index("sbar.id = 'v2sbar'") < SHELL_JS.index("bbar.id = 'v2bbar'")
    assert 'view.parentNode.insertBefore(bbar, view)' in SHELL_JS
    head = SHELL_JS[SHELL_JS.index('function drawHead'):SHELL_JS.index('SH.head = function')]
    assert 'mountBrainBar(sec.key)' in head
    helper = SHELL_JS[SHELL_JS.index('function mountBrainBar'):]
    assert 'document.getElementById("v2bbar")' in helper and 'B.mountBar(key, bb)' in helper and 'else bb.hidden = true' in helper   # غياب العقل ⇒ مخفي بصمت لا استثناء
    assert 'try {' in helper


def test_home_deck_wiring():
    assert 'brainItems: g.brainItems' in HOME_JS and 'V2BRAIN.pending()' in HOME_JS
    assert 'V2BRAIN.decorate(c, { fetch: true })' in HOME_JS and 'V2BRAIN.prefetch(S.deck.slice(1, 9))' in HOME_JS
    for case in ("case 'brain_approve': case 'brain_reject': case 'brain_edit': return brainAct(c, a);",):
        assert case in HOME_JS
    brain_act = HOME_JS[HOME_JS.index('function brainAct'):HOME_JS.index('function doneVerb')]
    assert 'track(c, Promise.resolve({ ok: true })' in brain_act and 'V2BRAIN.act(c, a,' in brain_act
    sp = HOME_JS[HOME_JS.index('function stillPending'):HOME_JS.index('// انتظار تحميل المصادر')]
    assert "c.kind === 'brain_item'" in sp and 'V2BRAIN.pending()' in sp
    sig = HOME_JS[HOME_JS.index('function signature'):HOME_JS.index('// ---', HOME_JS.index('function signature'))]
    assert 'V2BRAIN.sig()' in sig
    assert 'V2BRAIN.listen' in HOME_JS            # وصول رأي والبطاقة معروضة ⇒ إعادة رسم (مؤقّت اللوحة لا يعمل في التركيز)


def test_section_tickets_decorate_from_the_cache_and_prefetch_once():
    assert "window.V2BRAIN.decorate(it.card, { remap: false })" in SEC_HOME_JS            # التذكرة: بلا تبديل لزرّها ولا طلب رأي جديد
    assert SEC_HOME_JS.count("V2BRAIN['prefetch'](") == 1 and 'fetch: true' not in SEC_HOME_JS
    assert "window.V2BRAIN.decorate(c, { remap: false })" in SEC_PEOPLE_JS
    assert SEC_PEOPLE_JS.count("V2BRAIN['prefetch'](") == 1 and 'fetch: true' not in SEC_PEOPLE_JS
    assert "['trainer', 'join', 'pending_user', 'founding']" in SEC_PEOPLE_JS


def test_the_logic_file_has_one_brain2_block_at_the_end_and_the_hooks():
    assert LOGIC.count('// ===== brain2 =====') == 1 and LOGIC.count('// ===== /brain2 =====') == 1
    assert LOGIC.index('// ===== brain2 =====') < LOGIC.index('// ===== /brain2 =====')
    assert LOGIC.rstrip().endswith('// ===== /brain2 =====')
    blk = _block()
    for fn in ('v2bFacts', 'v2bDecorate', 'v2bItemCard'):
        assert 'L.%s = %s' % (fn, fn) in blk
    assert "case 'brain_item':" in LOGIC and 'opts.brainItems' in LOGIC
    # الخطّافان خارج الكتلة لا يزيدان عن المسموح: سطر kindOf وcase وجملة الطابور
    outside = LOGIC.replace(blk, '')
    assert outside.count('brain_item') == 4          # kindOf (مرتان في سطر واحد) + case + سطر الطابور
    # ملف العقل (P5) ما لُمس: لا `v2s.brain` ولا v2sBrain في كتلتنا
    assert 'v2sBrain' not in blk and 'v2s:brain' not in blk


def test_dockerfile_ships_the_files():
    txt = _read('Dockerfile')
    assert 'dashboard-cloud/v2-brain2.js' in txt and 'dashboard-cloud/v2-brain2.css' in txt


def test_css_is_scoped_to_its_own_classes():
    css = re.sub(r'/\*.*?\*/', '', BRAIN_CSS, flags=re.S)
    css = re.sub(r'@media[^{]*\{', '', css)
    css = re.sub(r'@keyframes [^{]+\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}', '', css)
    bad = []
    for sel in re.findall(r'([^{}]+)\{', css):
        for part in sel.split(','):
            part = part.strip()
            if part and not re.search(r'v2b-|v2-bbar', part):
                bad.append(part)
    assert not bad, bad[:5]


# ================================================================ ٢) v2bFacts
@needs_node
@pytest.mark.parametrize('row', [TRAINER, JOIN, VISITOR, LEAD, MESSAGE, DISPUTE, PAYOUT, RECEIPT])
def test_facts_have_no_email_no_phone_and_only_allowed_keys(row):
    c = card(row)
    out = facts(c)
    assert out and out['kind'] == c['kind'] and out['card_id'] == c['id']
    blob = json.dumps(out['facts'], ensure_ascii=False)
    assert '@' not in blob
    assert not re.search(r'\d{7,}', blob.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')).replace(' ', ''))
    assert not re.search(r'(?:\d[\s\-().]*){7,}', blob.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    assert set(out['facts']) <= ALLOWED
    assert len(blob.encode('utf-8')) < 3000


@needs_node
def test_the_clients_name_becomes_the_requester_and_emails_and_phones_are_stripped():
    out = facts(card(DISPUTE))
    blob = json.dumps(out['facts'], ensure_ascii=False)
    assert 'منى' not in blob and 'الشريف' not in blob and 'صاحب الطلب' in blob
    assert out['facts']['objection'] and out['facts']['expert_reply'] == 'سُلّم في الموعد'
    assert out['facts']['hours_held'] == 'أكثر من يومين'      # بحبيبة اليوم: لا يتغيّر المفتاح كل ساعة
    tr = facts(card(TRAINER))
    assert 'هالة' not in json.dumps(tr['facts'], ensure_ascii=False)
    assert tr['facts']['headline'] == 'محكّمة معتمدة اتصل على أو' or '0101' not in tr['facts']['headline']
    assert tr['facts']['specialty'] == 'عقود' and tr['facts']['attachments'] == 2
    ld = facts(card(LEAD))['facts']
    assert 'karim' not in json.dumps(ld, ensure_ascii=False) and '100 123' not in json.dumps(ld, ensure_ascii=False) and ld['topic'] == 'عقد إيجار'


@needs_node
def test_kind_specific_keys():
    assert {'objection', 'expert_reply', 'hours_held'} <= set(facts(card(DISPUTE))['facts'])
    assert {'headline', 'specialty', 'years', 'attachments'} <= set(facts(card(TRAINER))['facts'])
    p = facts(card(PAYOUT))['facts']
    assert {'method', 'dispute_check'} <= set(p) and p['money_text'] and 'fx_alert' not in p
    j = facts(card(JOIN))['facts']
    assert j['service'] == 'مراجعة العقود' and j['licensed'] is True and j['licence_missing'] is True
    bo = card({'apiKind': 'book_offer', 'apiId': 'o1', 'ref': 'o1', 'offerRow': OFFER, 'who': 'أ. دعاء'})
    f = facts(bo)['facts']
    assert f['type'] == 'كتاب' and f['suggested_price'] == '٢٠٠ جنيه'
    m = facts(card(MESSAGE))['facts']
    assert m['body'] == 'سؤال عن الباقات' and m['topic'] == 'الاشتراك'


@needs_node
def test_excluded_and_unknown_kinds_have_no_facts():
    assert facts(card(FILE_WAIT)) is None
    assert facts({'id': 'x', 'kind': 'file_late'}) is None and facts({'id': 'x', 'kind': 'file_waiting'}) is None
    assert facts({'id': 'x', 'kind': 'brain_item'}) is None and facts({'id': 'x', 'kind': 'whatever'}) is None
    assert facts(None) is None and facts({}) is None


@needs_node
def test_facts_stay_small_even_for_a_huge_card():
    c = card(LEAD)
    c['brain'] = 'ن' * 5000
    c['sub'] = 'س' * 5000
    out = facts(c)
    assert len(json.dumps(out['facts'], ensure_ascii=False).encode('utf-8')) <= 3000


@needs_node
def test_facts_do_not_change_within_the_day_but_do_when_the_data_changes():
    a = facts(card(DISPUTE), NOW)
    b = facts(card(DISPUTE), NOW + 5 * H)
    assert a['facts'] == b['facts']
    c2 = dict(DISPUTE, amountLabel='٦٠٠ ريال')
    assert facts(card(c2))['facts'] != a['facts']


# ================================================================ ٣) v2bDecorate
MARKS = {
    'failed': 'جملة ثابتة: تعذّرت كتابة رأي العقل الآن',
    'cap': 'جملة ثابتة: بلغ العقل حدّ كتابته اليوم',
    'off': 'جملة ثابتة: رأي العقل متوقّف من القواعد',
    'loading': 'يكتب العقل رأيه…',
}


@needs_node
@pytest.mark.parametrize('state,text', sorted(MARKS.items()))
def test_every_mark_keeps_the_static_line(state, text):
    base = card(TRAINER)
    d = v2_node.logic('v2bDecorate', base, {'state': state}, NOW)
    assert d['src']['text'] == text
    assert d['brain'] == base['brain'] and d['brainHead'] == base['brainHead'] and d['primary'] == base['primary'] and d['secondary'] == base['secondary']


@needs_node
def test_busy_none_and_unknown_states_do_not_invent_text():
    base = card(TRAINER)
    assert v2_node.logic('v2bDecorate', base, {'state': 'none'}, NOW)['src']['text'] == ''
    assert v2_node.logic('v2bDecorate', base, None, NOW)['src']['text'] == ''
    assert 'مشغول' in v2_node.logic('v2bDecorate', base, {'state': 'busy'}, NOW)['src']['text']
    assert v2_node.logic('v2bDecorate', base, {'state': 'ready', 'item': None}, NOW)['src']['text'] == ''       # رأي بلا جسم لا يمحو الجملة الثابتة


@needs_node
def test_an_ai_opinion_replaces_the_line_with_why_and_source_and_does_not_mutate_the_card():
    base = card(DISPUTE)
    before = json.dumps(base, sort_keys=True)
    d = v2_node.logic('v2bDecorate', base, ready('الاعتراض واضح.', '', 'القرار يخص الأموال.', 3), NOW)
    assert d['brain'] == 'الاعتراض واضح.' and d['reason'] == 'القرار يخص الأموال.' and d['brainHead'] == 'رأي العقل'
    assert d['src'] == {'text': 'كتبه العقل منذ ٣ ساعات', 'tone': 'ai'}
    assert json.dumps(base, sort_keys=True) == before          # الأصل لا يُلمس


MONEY_ROWS = {
    'payout': PAYOUT, 'manual_payment': RECEIPT, 'dispute': DISPUTE,
    'unactivated': {'apiKind': 'expert_file', 'apiId': 'u1', 'ref': 'U1', 'unact': True, 'who': 'ليلى', 'ef': {'title': 'ملف', 'paid_at': _iso(30)}},
    'legacy': {'apiKind': 'legacy', 'apiId': 'c1', 'ref': 'C1', 'who': 'ليلى', 'cons': {'title': 'استشارة', 'delivered_at': _iso(300)}},
    'file_attention': {'apiKind': 'expert_file', 'apiId': 'ef2', 'ref': 'EF2', 'needsAttention': True, 'who': 'ليلى', 'ef': {'title': 'ملف', 'blocked': [{'at': _iso(30)}]}},
    'stuck_payment': {'apiKind': 'stuck_payment', 'apiId': 's1', 'ref': 's1', 'who': 'ليلى', 'stuck': {'name': 'ليلى', 'amountText': '١٠٠ جنيه', 'kindText': 'دورة', 'refundable': True}},
}


@needs_node
@pytest.mark.parametrize('kind', MONEY)
@pytest.mark.parametrize('rec', ['reject', 'open', 'approve', 'wait'])
def test_money_kinds_are_never_remapped(kind, rec):
    base = card(MONEY_ROWS[kind])
    assert base['kind'] == kind
    d = v2_node.logic('v2bDecorate', base, ready('نص', rec, 'سبب'), NOW)
    assert d['primary'] == base['primary'] and d['secondary'] == base['secondary'] and 'remapped' not in d
    assert d['brain'] == 'نص'          # النص يتغير والأزرار لا


@needs_node
def test_open_makes_the_existing_open_act_primary_and_never_invents_one():
    base = card(TRAINER)                       # الأساسي «اقبل الطلب» والثانوي «افتح الطلب»
    d = v2_node.logic('v2bDecorate', base, ready('x', 'open'), NOW)
    assert d['primary'] == base['secondary'] and d['secondary'] == base['primary'] and d['remapped'] == 'open'
    acts_before = {json.dumps(base['primary']['act'], sort_keys=True), json.dumps(base['secondary']['act'], sort_keys=True)}
    assert {json.dumps(d['primary']['act'], sort_keys=True), json.dumps(d['secondary']['act'], sort_keys=True)} == acts_before
    # الانضمام برقم قيد ناقص: الأساسي مفتوح أصلًا ⇒ لا تغيير
    j = card(JOIN)
    assert v2_node.logic('v2bDecorate', j, ready('x', 'open'), NOW)['primary'] == j['primary']


@needs_node
def test_reject_remaps_only_when_a_reject_act_already_exists():
    # لا فعل رفض على بطاقة المدرّب ⇒ لا تبديل ولا فعل جديد
    t = card(TRAINER)
    d = v2_node.logic('v2bDecorate', t, ready('x', 'reject'), NOW)
    assert d['primary'] == t['primary'] and d['secondary'] == t['secondary'] and 'remapped' not in d
    # عرض كتاب فيه «ارفض» ثانوي ⇒ يصير أساسيًا
    bo = card({'apiKind': 'book_offer', 'apiId': 'o1', 'ref': 'o1', 'offerRow': OFFER, 'who': 'أ. دعاء'})
    d = v2_node.logic('v2bDecorate', bo, ready('x', 'reject'), NOW)
    assert d['primary']['act']['do'] == 'offer_reject' and d['secondary']['act']['do'] == 'offer_approve'


@needs_node
def test_approve_wait_and_unknown_recommendations_change_nothing():
    for row in (TRAINER, VISITOR, LEAD):
        base = card(row)
        for rec in ('approve', 'wait', '', 'publish', 'whatever'):
            d = v2_node.logic('v2bDecorate', base, ready('x', rec), NOW)
            assert d['primary'] == base['primary'] and d['secondary'] == base['secondary']


@needs_node
def test_info_group_accepts_open_and_wait_and_the_remap_option_can_be_off():
    base = card(LEAD)                          # تم (resolve) ثم افتح
    d = v2_node.logic('v2bDecorate', base, ready('x', 'open'), NOW)
    assert d['primary']['act']['do'] == 'open'
    off = v2_node.logic('v2bDecorate', base, dict(ready('x', 'open'), remap=False), NOW)
    assert off['primary'] == base['primary'] and off['brain'] == 'x'


@needs_node
def test_excluded_kinds_get_no_marks_and_no_text():
    base = card(FILE_WAIT)
    d = v2_node.logic('v2bDecorate', base, {'state': 'failed'}, NOW)
    assert d['src']['text'] == '' and d['brain'] == base['brain']
    d2 = v2_node.logic('v2bDecorate', base, ready('x', 'open'), NOW)
    assert d2['brain'] == base['brain']


# ================================================================ ٤) v2bItemCard وv2Decisions
def _item(**kw):
    it = {'id': 'it1', 'producer': 'reply_draft', 'section': 'people', 'kind': 'draft', 'target_label': 'رد على رسالة', 'status': 'proposed', 'tag': 'مسودة رد',
          'approve_label': 'أرسل الرد', 'created_at': _iso(2), 'body': {'text': 'مرحبًا بكم'}}
    it.update(kw)
    return it


@needs_node
def test_item_card_shape_for_a_draft():
    c = v2_node.logic('v2bItemCard', _item(), NOW)
    assert c['kind'] == 'brain_item' and c['group'] >= 900 and c['tag'] == 'مسودة رد' and c['title'] == 'رد على رسالة'
    assert c['brain'] == 'مرحبًا بكم' and c['brainHead'] == 'ما كتبه العقل'
    assert c['primary'] == {'label': 'أرسل الرد', 'act': {'do': 'brain_approve', 'id': 'it1'}}
    assert c['secondary'] == {'label': 'ارفض', 'act': {'do': 'brain_reject', 'id': 'it1'}}
    assert c['edit'] == {'label': 'عدّل', 'act': {'do': 'brain_edit', 'id': 'it1'}}
    assert c['img'] == 'people' and c['id'] == 'brain_item|it1' and c['ageText'] == 'منذ ساعتين'


@needs_node
def test_item_card_prefers_the_producers_label_and_has_a_default():
    assert v2_node.logic('v2bItemCard', _item(approve_label='انشر الدورة', section='courses'), NOW)['primary']['label'] == 'انشر الدورة'
    assert v2_node.logic('v2bItemCard', _item(approve_label=''), NOW)['primary']['label'] == 'اعتمد'
    assert v2_node.logic('v2bItemCard', _item(approve_label=None, tag=None), NOW)['tag'] == 'اقتراح العقل'


@needs_node
def test_note_cards_use_keep_and_delete():
    c = v2_node.logic('v2bItemCard', _item(kind='note', producer='seo_notes', section='content', approve_label='', tag='ملاحظة على مسودة'), NOW)
    assert c['primary']['label'] == 'احتفظ بها' and c['secondary']['label'] == 'احذفها' and c['edit'] is None
    assert c['primary']['act']['do'] == 'brain_approve' and c['secondary']['act']['do'] == 'brain_reject' and c['img'] == 'content'
    c2 = v2_node.logic('v2bItemCard', _item(kind='note', approve_label='أي شيء'), NOW)
    assert c2['primary']['label'] == 'احتفظ بها'          # الملاحظة لا تتبع زر المنتج


@needs_node
def test_item_card_renders_generic_fields_and_rejects_empty_items():
    c = v2_node.logic('v2bItemCard', _item(body={'text': 'ن', 'fields': {'title': 'عنوان الدرس', 'body': 'نص الدرس', 'secret': 'x'}}), NOW)
    assert c['fields'] == [{'k': 'العنوان', 'v': 'عنوان الدرس'}, {'k': 'النص', 'v': 'نص الدرس'}]
    assert v2_node.logic('v2bItemCard', None, NOW) is None and v2_node.logic('v2bItemCard', {}, NOW) is None


@needs_node
def test_v2card_case_returns_the_prepared_card_and_ignores_an_empty_row():
    c = card({'apiKind': 'brain_item', 'apiId': 'it1', 'ref': 'it1', 'item': _item()})
    assert c['kind'] == 'brain_item' and c['primary']['act']['id'] == 'it1'
    assert card({'apiKind': 'brain_item', 'apiId': 'x', 'ref': 'x'}) is None


@needs_node
def test_decisions_put_brain_items_last_oldest_first_and_only_proposed():
    items = [_item(id='a', created_at=_iso(1)), _item(id='b', created_at=_iso(9)), _item(id='c', status='approved'), _item(id='d', status='rejected'), {'id': ''}, None,
             _item(id='e', created_at=_iso(5), status=None)]
    out = v2_node.logic('v2Decisions', [TRAINER, VISITOR, LEAD], [dict(PAYOUT)], None, {'now': NOW, 'brainItems': items})
    kinds = [c['kind'] for c in out]
    assert kinds == ['payout', 'trainer', 'pending_user', 'lead', 'brain_item', 'brain_item', 'brain_item']
    assert [c['id'] for c in out if c['kind'] == 'brain_item'] == ['brain_item|b', 'brain_item|e', 'brain_item|a']
    # بلا الخطّاف: القائمة كما كانت بالحرف
    base = v2_node.logic('v2Decisions', [TRAINER, VISITOR, LEAD], [dict(PAYOUT)], None, {'now': NOW})
    assert [c['id'] for c in base] == [c['id'] for c in out if c['kind'] != 'brain_item']
    for bad in (None, 'x', {}, 5):
        assert [c['id'] for c in v2_node.logic('v2Decisions', [TRAINER], [], None, {'now': NOW, 'brainItems': bad})] == [c['id'] for c in v2_node.logic('v2Decisions', [TRAINER], [], None, {'now': NOW})]


# ================================================================ ٥) v2-brain2.js في node:vm (ساعة ومؤقّتات وخادم مزيّفة)
VM_JS = r"""
const vm = require('vm'), fs = require('fs'), path = require('path');
const DC = process.argv[1];
const inp = JSON.parse(fs.readFileSync(0, 'utf8'));
const clock = { t: 1793361600000 };
class FakeDate extends Date { static now() { return clock.t; } }
let timers = [], tid = 0;
const calls = [];
const state = { route: null, onscreen: [], shellOn: true, authed: true };
function setTimeout_(fn, ms) { const id = ++tid; timers.push({ id, fn, at: clock.t + ms }); return id; }
function clearTimeout_(id) { timers = timers.filter(t => t.id !== id); }
const flush = async () => { for (let i = 0; i < 6; i++) await new Promise(r => setImmediate(r)); };
async function advance(ms) {
  const end = clock.t + ms;
  for (;;) {
    const due = timers.filter(t => t.at <= end).sort((a, b) => a.at - b.at)[0];
    if (!due) break;
    timers = timers.filter(t => t !== due); clock.t = Math.max(clock.t, due.at); due.fn(); await flush();
  }
  clock.t = end; await flush();
}
const win = { toast: undefined };
win.window = win;
win.EP = { get authed() { return state.authed; }, api(p, o) {
  const method = (o && o.method) || 'GET', body = o && o.body;
  calls.push({ method, path: p, body });
  return Promise.resolve().then(() => { const r = state.route(method, p, body); if (r && r.__err) { const e = new Error('x'); e.status = r.__err; e.data = r.data || {}; throw e; } return r; });
} };
win.V2SHELL = { get on() { return state.shellOn; } };
const doc = { querySelectorAll() { return state.onscreen.map(id => ({ getAttribute: () => id })); }, getElementById() { return null; } };
const ctx = vm.createContext({ window: win, document: doc, setTimeout: setTimeout_, clearTimeout: clearTimeout_, Date: FakeDate, Promise, JSON, console, encodeURIComponent, unescape, Math, Object, Array, String, Number, isNaN, isFinite, parseInt, Error, navigator: {} });
vm.runInContext(fs.readFileSync(path.join(DC, 'v2-logic.js'), 'utf8'), ctx);
vm.runInContext(fs.readFileSync(path.join(DC, 'v2-brain2.js'), 'utf8'), ctx);
const B = win.V2BRAIN, L = win.V2L;
const out = {};
(async () => { try { %s } catch (e) { out.error = String(e && e.stack || e); } process.stdout.write(JSON.stringify({ out, calls })); })();
"""


def _vm(body):
    p = subprocess.run([v2_node.NODE, '-e', VM_JS % body, DC], capture_output=True, text=True, timeout=60, input=json.dumps({}))
    assert p.returncode == 0, p.stderr[-1500:]
    res = json.loads(p.stdout)
    assert 'error' not in res['out'], res['out']['error']
    return res


TRAINER_CARD = {'id': 'trainer|t1|T1', 'kind': 'trainer', 'tag': 'مدرّب جديد', 'title': 'مدرّب', 'sub': 'عقود', 'brain': 'سطر', 'reason': '', 'warn': '', 'facts': [], 'ageText': '',
                'primary': {'label': 'اقبل الطلب', 'act': {'do': 'decide', 'action': 'approve'}}, 'secondary': {'label': 'افتح الطلب', 'act': {'do': 'open'}}, 'row': {'who': 'اسم', 'apiKind': 'trainer'}}


@needs_node
def test_pending_is_undefined_then_array_then_cached_for_sixty_seconds_then_refetched():
    r = _vm("""
state.route = (m, p) => ({ items: [{ id: 'a', status: 'proposed', section: 'people' }, { id: 'b', status: 'approved', section: 'people' }, { id: '', status: 'proposed' }] });
out.first = B.pending() === undefined;
await flush();
out.second = B.pending().map(i => i.id);
await advance(30000); B.pending(); await flush();
out.getsAfter30 = calls.filter(c => c.method === 'GET').length;
await advance(40000); out.stale = B.pending().map(i => i.id); await flush();
out.getsAfter70 = calls.filter(c => c.method === 'GET').length;
""")
    o = r['out']
    assert o['first'] is True and o['second'] == ['a'] and o['getsAfter30'] == 1 and o['stale'] == ['a'] and o['getsAfter70'] == 2
    assert r['calls'][0]['method'] == 'GET' and r['calls'][0]['path'] == '/v2/brain/items?status=proposed' and not r['calls'][0].get('body')


@needs_node
def test_pending_is_null_on_failure_and_quiet_when_the_switch_is_off():
    r = _vm("""
state.route = () => ({ __err: 500 });
B.pending(); await flush();
out.failed = B.pending();
state.shellOn = false;
out.off = B.pending() === undefined;
out.sigOff = B.sig();
const n = calls.length; B.pending(); out.noCallsWhenOff = calls.length === n;
""")
    o = r['out']
    assert o['failed'] is None and o['off'] is True and o['sigOff'] == '' and o['noCallsWhenOff'] is True


@needs_node
def test_decorate_without_fetch_never_asks_and_with_fetch_asks_once_with_clean_facts():
    card_js = json.dumps(TRAINER_CARD, ensure_ascii=False)
    r = _vm("""
state.route = (m, p, b) => p === '/v2/brain/opinion' ? { queued: true } : { items: {} };
const c = %s;
const d0 = B.decorate(c, {});
out.noFetch = calls.length === 0 && d0.src.text === '';
const d1 = B.decorate(c, { fetch: true });
out.loading = d1.src.text;
B.decorate(c, { fetch: true }); B.decorate(c, { fetch: true });
await flush();
out.asks = calls.filter(x => x.path === '/v2/brain/opinion').length;
out.body = calls.filter(x => x.path === '/v2/brain/opinion')[0].body;
""" % card_js)
    o = r['out']
    assert o['noFetch'] is True and o['loading'] == 'يكتب العقل رأيه…' and o['asks'] == 1
    assert set(o['body']) == {'kind', 'card_id', 'facts'} and o['body']['kind'] == 'trainer' and o['body']['card_id'] == TRAINER_CARD['id']
    assert 'اسم' not in json.dumps(o['body'], ensure_ascii=False)


@needs_node
def test_a_cached_opinion_comes_back_at_once_and_flips_the_buttons():
    card_js = json.dumps(TRAINER_CARD, ensure_ascii=False)
    r = _vm("""
state.route = () => ({ item: { id: 'o', created_at: new Date(clock.t - 7 * 60000).toISOString(), body: { text: 'افتحه أولًا', recommend: 'open', why: 'لم تُقرأ المرفقات' } } });
const c = %s;
B.decorate(c, { fetch: true }); await flush();
const d = B.decorate(c, { fetch: true });
out.d = { brain: d.brain, why: d.reason, src: d.src, primary: d.primary.label, secondary: d.secondary.label };
const t = B.decorate(c, { remap: false });
out.t = { primary: t.primary.label, brain: t.brain };
""" % card_js)
    o = r['out']
    assert o['d'] == {'brain': 'افتحه أولًا', 'why': 'لم تُقرأ المرفقات', 'src': {'text': 'كتبه العقل منذ ٧ دقائق', 'tone': 'ai'}, 'primary': 'افتح الطلب', 'secondary': 'اقبل الطلب'}
    assert o['t'] == {'primary': 'اقبل الطلب', 'brain': 'افتحه أولًا'}          # التذكرة: النص من الذاكرة بلا تبديل لزرّها


@needs_node
def test_polling_every_three_seconds_stops_after_twenty_and_only_while_the_card_is_on_screen():
    card_js = json.dumps(TRAINER_CARD, ensure_ascii=False)
    r = _vm("""
state.route = (m, p) => p === '/v2/brain/opinion' ? { queued: true } : { items: { [%s]: null } };
state.onscreen = [%s];
const c = %s;
B.decorate(c, { fetch: true }); await flush();
await advance(2999); out.before3 = calls.filter(x => x.path.indexOf('lookup') > -1).length;
await advance(2); out.at3 = calls.filter(x => x.path.indexOf('lookup') > -1).length;
await advance(3000 * 40);
out.total = calls.filter(x => x.path.indexOf('lookup') > -1).length;
out.mark = B.decorate(c, { fetch: true }).src.text;
out.oneCardEach = calls.filter(x => x.path.indexOf('lookup') > -1).every(x => x.body.cards.length === 1);
""" % (json.dumps(TRAINER_CARD['id']), json.dumps(TRAINER_CARD['id']), card_js))
    o = r['out']
    assert o['before3'] == 0 and o['at3'] == 1 and o['total'] == 20 and o['oneCardEach'] is True
    assert o['mark'] == MARKS['failed']


@needs_node
def test_polling_pauses_off_screen_and_resumes_and_lands_the_opinion():
    card_js = json.dumps(TRAINER_CARD, ensure_ascii=False)
    r = _vm("""
let polls = 0;
state.route = (m, p) => { if (p === '/v2/brain/opinion') return { queued: true };
  polls++; return { items: { [%s]: polls >= 2 ? { id: 'o', created_at: new Date(clock.t).toISOString(), body: { text: 'جاهز', recommend: 'wait' } } : null } }; };
const c = %s;
state.onscreen = [];
B.decorate(c, { fetch: true }); await flush();
await advance(20000);
out.offscreen = calls.filter(x => x.path.indexOf('lookup') > -1).length;
state.onscreen = [%s];
B.decorate(c, { fetch: true });          // رجعت للشاشة
await advance(3100); await advance(3100);
out.after = calls.filter(x => x.path.indexOf('lookup') > -1).length;
out.brain = B.decorate(c, { fetch: true }).brain;
""" % (json.dumps(TRAINER_CARD['id']), card_js, json.dumps(TRAINER_CARD['id'])))
    o = r['out']
    assert o['offscreen'] == 0 and o['after'] == 2 and o['brain'] == 'جاهز'


@needs_node
def test_every_reason_maps_to_its_mark_and_not_supported_stays_silent():
    card_js = json.dumps(TRAINER_CARD, ensure_ascii=False)
    res = {}
    for reason in ('off', 'cap', 'busy', 'no_writer', 'not_supported'):
        r = _vm("""
state.route = () => ({ item: null, reason: '%s' });
const c = %s;
B.decorate(c, { fetch: true }); await flush();
out.t = B.decorate(c, { fetch: true }).src.text;
""" % (reason, card_js))
        res[reason] = r['out']['t']
    assert res['off'] == MARKS['off'] and res['cap'] == MARKS['cap'] and res['no_writer'] == MARKS['failed'] and 'مشغول' in res['busy'] and res['not_supported'] == ''


@needs_node
def test_a_closed_server_404_leaves_the_static_line_and_stops_asking():
    t2 = dict(TRAINER_CARD, id='trainer|t2|T2')
    r = _vm("""
state.route = () => ({ __err: 404 });
const a = %s, b = %s;
B.decorate(a, { fetch: true }); await flush();
out.a = B.decorate(a, { fetch: true }).src.text;
B.decorate(b, { fetch: true }); await flush();
out.asks = calls.filter(x => x.path === '/v2/brain/opinion').length;
B.prefetch([a, b]);
out.noLookup = calls.filter(x => x.path.indexOf('lookup') > -1).length;
""" % (json.dumps(TRAINER_CARD, ensure_ascii=False), json.dumps(t2, ensure_ascii=False)))
    o = r['out']
    assert o['a'] == '' and o['asks'] == 1 and o['noLookup'] == 0


@needs_node
def test_a_network_failure_shows_the_failed_mark_without_retrying():
    card_js = json.dumps(TRAINER_CARD, ensure_ascii=False)
    r = _vm("""
state.route = () => ({ __err: 500 });
const c = %s;
B.decorate(c, { fetch: true }); await flush();
out.t = B.decorate(c, { fetch: true }).src.text;
await advance(30000);
out.asks = calls.filter(x => x.path === '/v2/brain/opinion').length;
""" % card_js)
    assert r['out']['t'] == MARKS['failed'] and r['out']['asks'] == 1


@needs_node
def test_prefetch_makes_one_lookup_for_up_to_forty_cards_and_never_asks_again_for_the_same():
    cards = [dict(TRAINER_CARD, id='trainer|t%d|T%d' % (i, i)) for i in range(45)]
    cards.append({'id': 'ef|1', 'kind': 'file_waiting'})
    cards.append(None)
    r = _vm("""
state.route = () => ({ items: {} });
const cs = %s;
B.prefetch(cs); await flush();
B.prefetch(cs); await flush();
out.n = calls.filter(x => x.path.indexOf('lookup') > -1).length;
out.size = calls[0].body.cards.length;
out.writes = calls.filter(x => x.method !== 'GET' && x.path.indexOf('lookup') < 0).length;
out.keys = Object.keys(calls[0].body.cards[0]).sort();
""" % json.dumps(cards, ensure_ascii=False))
    o = r['out']
    assert o['size'] == 40 and o['keys'] == ['card_id', 'facts', 'kind'] and o['writes'] == 0
    assert o['n'] == 2          # الأربعون ثم الخمسة الباقية؛ لا تكرار لما سُئل عنه


@needs_node
def test_prefetch_lands_found_opinions_so_decorate_shows_them_without_asking():
    card_js = json.dumps(TRAINER_CARD, ensure_ascii=False)
    r = _vm("""
state.route = (m, p, b) => ({ items: { [%s]: { id: 'o', created_at: new Date(clock.t - 3600000).toISOString(), body: { text: 'من الذاكرة' } } } });
const c = %s;
B.prefetch([c]); await flush();
const d = B.decorate(c, {});
out.brain = d.brain; out.src = d.src.text; out.asks = calls.filter(x => x.path === '/v2/brain/opinion').length;
""" % (json.dumps(TRAINER_CARD['id']), card_js))
    o = r['out']
    assert o['brain'] == 'من الذاكرة' and o['src'] == 'كتبه العقل منذ ساعة' and o['asks'] == 0


MOUNT = r"""
function mkEl() { return { hidden: true, innerHTML: '', querySelectorAll() { return []; }, querySelector() { return null; } }; }
const items = %s;
state.route = () => ({ items });
B.pending(); await flush();
const el = mkEl();
B.mountBar('people', el); out.people = { hidden: el.hidden, html: el.innerHTML };
const e2 = mkEl(); B.mountBar('home', e2); out.home = { hidden: e2.hidden, html: e2.innerHTML };
const e3 = mkEl(); B.mountBar('brain', e3); out.brain = { hidden: e3.hidden, html: e3.innerHTML };
const e4 = mkEl(); B.mountBar('money', e4); out.empty = { hidden: e4.hidden, html: e4.innerHTML };
state.shellOn = false; const e5 = mkEl(); e5.hidden = false; e5.innerHTML = 'x'; B.mountBar('people', e5); out.off = { hidden: e5.hidden, html: e5.innerHTML };
"""


def _bar_items(n, section='people'):
    return [{'id': 'i%d' % k, 'section': section, 'kind': 'draft', 'status': 'proposed', 'tag': 'مسودة رد', 'target_label': 'رد %d' % k, 'approve_label': 'أرسل الرد',
             'created_at': _iso(k + 1), 'body': {'text': 'نص %d' % k}} for k in range(n)]


@needs_node
def test_bar_shows_three_cards_and_the_show_all_count():
    r = _vm(MOUNT % json.dumps(_bar_items(5), ensure_ascii=False))
    p = r['out']['people']
    assert p['hidden'] is False and p['html'].count('class="v2b-c"') == 3 and 'اعرض الكل (٥)' in p['html'] and 'ما كتبه العقل هنا' in p['html']
    assert p['html'].count('data-a="brain_approve"') == 3 and p['html'].count('data-a="brain_edit"') == 3 and p['html'].count('data-a="brain_reject"') == 3
    assert '>أرسل الرد<' in p['html'] and '>ارفض<' in p['html'] and '>عدّل<' in p['html']
    assert '<span class="v2b-n">٥</span>' in p['html']


@needs_node
def test_bar_has_no_show_all_button_for_three_or_less():
    r = _vm(MOUNT % json.dumps(_bar_items(3), ensure_ascii=False))
    assert 'اعرض الكل' not in r['out']['people']['html'] and r['out']['people']['html'].count('class="v2b-c"') == 3


@needs_node
def test_bar_is_hidden_on_home_and_brain_when_empty_and_when_the_switch_is_off():
    r = _vm(MOUNT % json.dumps(_bar_items(2), ensure_ascii=False))
    o = r['out']
    for k in ('home', 'brain', 'empty', 'off'):
        assert o[k]['hidden'] is True and o[k]['html'] == '', k


@needs_node
def test_bar_note_cards_have_keep_delete_and_no_edit():
    items = [{'id': 'n1', 'section': 'content', 'kind': 'note', 'status': 'proposed', 'tag': 'ملاحظة على مسودة', 'target_label': 'مسودة', 'approve_label': '',
              'created_at': _iso(1), 'body': {'text': 'ملاحظة'}}]
    body = MOUNT.replace("B.mountBar('people', el)", "B.mountBar('content', el)") % json.dumps(items, ensure_ascii=False)
    html = _vm(body)['out']['people']['html']
    assert '>احتفظ بها<' in html and '>احذفها<' in html and 'brain_edit' not in html


@needs_node
def test_bar_text_is_escaped():
    items = _bar_items(1)
    items[0]['body'] = {'text': '<img src=x onerror=alert(1)>'}
    items[0]['target_label'] = '"><script>x</script>'
    html = _vm(MOUNT % json.dumps(items, ensure_ascii=False))['out']['people']['html']
    assert '<img src=x' not in html and '<script' not in html and '&lt;img' in html


@needs_node
def test_act_degrades_silently_when_there_is_no_modal_function():
    r = _vm("""
const item = { id: 'a', kind: 'draft', approve_label: 'أرسل الرد', body: { text: 'ن' } };
let cbCalled = false;
B.act({ brainItem: item }, { do: 'brain_approve' }, () => { cbCalled = true; });
B.act({ brainItem: item }, { do: 'brain_edit' }, () => { cbCalled = true; });
B.act({}, { do: 'brain_approve' }, () => { cbCalled = true; });
B.act(null, null, null);
out.cb = cbCalled; out.writes = calls.length;
""")
    assert r['out'] == {'cb': False, 'writes': 0}


@needs_node
def test_sig_changes_when_data_arrives():
    r = _vm("""
state.route = () => ({ items: [{ id: 'a', status: 'proposed', section: 'people' }] });
const s0 = B.sig(); B.pending(); await flush(); const s1 = B.sig();
out.changed = s0 !== s1; out.stable = B.sig() === s1;
""")
    assert r['out'] == {'changed': True, 'stable': True}


# ================================================================ ٦) فحص النصوص
def _strings(src):
    """كل النصوص المقتبسة التي فيها حرف عربي (مفرد/مزدوج)."""
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    out = []
    for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"", src):
        s = m.group(1) if m.group(1) is not None else m.group(2)
        if re.search(r'[؀-ۿ]', s):
            out.append(s)
    return out


def _new_strings():
    s = _strings(BRAIN_JS) + _strings(_block())
    # نصوص الربط الجديدة في الملفات المشتركة (ما أضفناه فقط)
    for src in (HOME_JS, SEC_HOME_JS, SEC_PEOPLE_JS, SHELL_JS):
        for line in src.split('\n'):
            if 'brain2' in line or 'V2BRAIN' in line or 'brainAct' in line or 'v2b-' in line:
                s += _strings(line)
    return s


FORBIDDEN = ['يقوّم', 'اعكس', '⇒', '✓', 'لما ']


def test_copy_rules_on_the_new_strings():
    strings = _new_strings()
    assert len(strings) > 40
    for s in strings:
        for bad in FORBIDDEN:
            assert bad not in s, (bad, s)
        # لا لاتيني داخل نص عربي مرئي (أصناف CSS وأسماء الحقول لا تحمل عربيًا)
        assert not re.search(r'[A-Za-z]', re.sub(r'<[^>]*>', '', s)), s
        assert not re.search(r'(?:^|\s)(?:0|null|undefined|NaN)(?:\s|$)', s), s
        assert not s.strip().startswith(('الذكاء', 'AI')), s


def test_no_text_claims_an_email_was_sent():
    blob = '\n'.join(_new_strings())
    assert 'يُرسل بريد من اللوحة بعد' in blob          # الجملة الصادقة الوحيدة عن البريد
    for bad in ('أُرسل البريد', 'تم إرسال البريد', 'أرسلنا بريدًا', 'وصل البريد', 'سيصل البريد', 'تم إرسال الرد بالبريد'):
        assert bad not in blob, bad
    assert 'يصل هذا الرد إلى صاحب الرسالة إشعارًا داخل المنصة.' in blob


def test_exact_spec_copy_is_present():
    blob = BRAIN_JS + _block()
    for exact in ('إرسال الرد', 'يصل هذا الرد إلى صاحب الرسالة إشعارًا داخل المنصة.', 'نعم، أرسله', 'رجوع',
                  'يُحفظ الرد هنا ويُنسخ لترسله بنفسك. لا يُرسل بريد من اللوحة بعد.', 'نُسخ النص',
                  'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.', 'ما كتبه العقل هنا', 'اعرض الكل (', 'احفظ وأرسل',
                  'احتفظ بها', 'احذفها', 'ما كتبه العقل', 'عدّل', 'ارفض', 'جملة ثابتة: تعذّرت كتابة رأي العقل الآن', 'جملة ثابتة: بلغ العقل حدّ كتابته اليوم',
                  'جملة ثابتة: رأي العقل متوقّف من القواعد', 'يكتب العقل رأيه…', 'كتبه العقل '):
        assert exact in blob, exact


def test_a_422_with_copy_text_shows_the_error_and_the_text():
    assert "typeof data.copy_text === 'string'" in BRAIN_JS and 'يمكنك نسخ النص من هنا:' in BRAIN_JS


def test_new_js_never_touches_the_network_directly_or_the_other_packages_files():
    assert re.findall(r'\bfetch\(|XMLHttpRequest|sendBeacon|\bprompt\(|\bconfirm\(|\balert\(', BRAIN_JS) == []
    assert BRAIN_JS.count('call(') >= 5
    # لا يكلّم غير مسارات العقل (قراءة الاقتراحات · رأي · lookup · اعتماد/رفض/حذف)
    paths = set(re.findall(r"'(/v2/brain/[^']*)'", BRAIN_JS))
    assert paths == {'/v2/brain/items?status=proposed', '/v2/brain/opinions/lookup', '/v2/brain/opinion', '/v2/brain/items/'}
    assert "'by'" not in BRAIN_JS and 'by:' not in BRAIN_JS          # الفاعل من التوكن لا من الجسم
    assert 'confirmed: true' in BRAIN_JS
    assert not re.search(r'/bridge/agents|vet-trainer|review-course|api/ai', BRAIN_JS)


def test_no_new_role_and_no_other_package_files_are_referenced():
    for src in (BRAIN_JS, BRAIN_CSS):
        assert 'v2s/brain' not in src and 'V2SEC.brain' not in src


# ================================================================ جولة الإصلاح: «عدّل» ومراجعة الموقع
_SITE_EDITS = [{'path': 'b1', 'old': ('عنوان قديم طويل جدًا ' * 6).strip(), 'new': 'عنوان جديد أوضح', 'why': 'يخالف قرارًا معتمدًا'},
               {'path': 'b2', 'old': 'فقرة قديمة', 'new': 'فقرة جديدة', 'why': ''},
               {'path': 'b3', 'old': 'ثالث قديم', 'new': 'ثالث جديد', 'why': 'سبب'},
               {'path': 'b4', 'old': 'رابع قديم', 'new': 'رابع جديد', 'why': 'سبب آخر'}]


@needs_node
@pytest.mark.parametrize('producer', ['site_review', 'site_edit_manual'])
def test_site_items_hide_edit_and_carry_every_edit_in_full(producer):
    c = v2_node.logic('v2bItemCard', _item(producer=producer, section='content', approve_label='انشر التعديل على الموقع',
                                           body={'text': 'ملخص مقتطع…', 'edits': _SITE_EDITS, 'page': 'pricing.html'}), NOW)
    assert c['edit'] is None, 'لا «عدّل» لاقتراح تعديلات الموقع'
    assert c['primary']['label'] == 'انشر التعديل على الموقع'
    assert [e['new'] for e in c['edits']] == [e['new'] for e in _SITE_EDITS], 'كل التعديلات، بلا قصّ'
    assert c['edits'][0]['old'] == _SITE_EDITS[0]['old'] and c['edits'][0]['why'] == 'يخالف قرارًا معتمدًا'


@needs_node
def test_items_without_edits_keep_the_edit_button_and_an_empty_list():
    c = v2_node.logic('v2bItemCard', _item(), NOW)
    assert c['edit'] == {'label': 'عدّل', 'act': {'do': 'brain_edit', 'id': 'it1'}} and c['edits'] == []
    c2 = v2_node.logic('v2bItemCard', _item(body={'text': 'ن', 'edits': []}), NOW)
    assert c2['edit'] is not None and c2['edits'] == []


def test_approve_sheet_renders_the_full_edits_list_instead_of_the_truncated_summary():
    blob = BRAIN_JS
    assert 'function editsList(' in blob and 'v2b-e-old' in blob and 'v2b-e-new' in blob and 'v2b-e-why' in blob
    # صفحة التأكيد تستعمل القائمة الكاملة حين توجد تعديلات، والمقتطف المقتصّ حين لا توجد
    assert re.search(r"edits\.length \? editsList\(edits\) : quote\(item\.body && item\.body\.text\)", blob)
    css = _read('dashboard-cloud', 'v2-brain2.css')
    assert '.v2b-edits' in css
