# -*- coding: utf-8 -*-
"""«ملف للخبير» في الواجهة — حقائق ثابتة في المصدر (الجولة ٦ · SPEC §١٠-ب، ومتحدّثة للجولة ٧ · §١٥).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_ui_static.py

قراية ملفات بس (زي `test_dash_ia_structure.py`): القايمة ما كبرتش، الشرايح والعدّادات بأسماء مفاتيح
المنصة الحقيقية، ولا نافذة متصفح للتأكيد، وفعل الفلوس بيبعت `confirmed: true`، والسجل له أسماء عربي،
ولا كلمة بتختار «الرأي الرسمي»، ولا كلام تقني في النصوص الجديدة. السلوك نفسه في المتصفح:
`test_expert_files_ui.py`.
"""
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
INDEX = os.path.join(_ROOT, 'dashboard-cloud', 'index.html')
API_JS = os.path.join(_ROOT, 'dashboard-cloud', 'dashboard-api.js')

NEW_UI_FUNCS = ('drawExpertFile', 'drawDispute', 'drawUnactivated', 'expertPickModal', 'moneyConfirmModal',
                'opinionsCompareModal', 'efRefundModal', 'efResolveModal', 'efOpinionPreview', 'efServiceLine',
                'efBlockedStrips', 'efPayee',
                # الجولة ٨
                'drawReview', 'efReviewApproveModal', 'efReviewReturnModal', 'drawLegacy', 'efLegacyModal',
                'efLockedBtn', 'efReleaseLock', 'efTrialLine', 'efSlot')
NEW_API_FUNCS = ('EP.expertFileDetail', 'EP.expertFileSend', 'EP.expertFileRefund', 'EP.expertFileUnactivatedRefund',
                 'EP.disputeDecide', 'EP.expertFileReview', 'EP.legacyDecide')
NEW_ROW_FUNCS = ('efFileRow', 'efDisputeRow', 'consDisputeRow', 'efFlagBadges', 'efUnactivatedRow', 'efUnactWhy',
                 'efAttentionBadge', 'efReviewRow', 'legacyRow', 'efReleaseWhy', 'efRefundWhy', 'efMoneyBackBadge')


@pytest.fixture(scope='module')
def html():
    with open(INDEX, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def apijs():
    with open(API_JS, encoding='utf-8') as fh:
        return fh.read()


def _body(src, head):
    """من `function X(` (أو `EP.X = function`) لحد أول تعريف تاني على أول السطر/بعد مسافتين."""
    start = src.index(head)
    nxt = re.search(r'\n(?:function |/\* |  EP\.[A-Za-z]+ = function|  function |  var LOADERS)', src[start + len(head):])
    return src[start:start + len(head) + (nxt.start() if nxt else len(src))]


def _modules(html):
    body = html[html.index('const MODULES={'):html.index('const CO_PINNED=')]
    out = {}
    for mid, rest in re.findall(r"^\s{2}([a-z_]+):\{(.*)\},?$", body, re.M):
        g = re.search(r"grp:'([a-z]+)'", rest)
        out[mid] = g.group(1) if g else None
    return out


def test_menu_did_not_grow(html):
    mods = _modules(html)
    assert len([m for m, g in mods.items() if g and g != 'co']) == 12
    assert len([m for m, g in mods.items() if g == 'co']) == 4
    assert not any('ملف' in k or 'expert_file' in k for k in mods)


def test_inbox_types_files_and_disputes_exist(html):
    t = _body(html, 'function inboxType(')
    assert "i.apiKind==='expert_file')return 'files'" in t
    assert "i.apiKind==='dispute')return 'disputes'" in t
    # قبل «قرارات» — وإلا كل صفّ فيه apiKind كان هيقع في «قرارات».
    assert t.index("'files'") < t.index("return 'decisions'")
    r = _body(html, 'function renderInbox(')
    assert "['files','ملفات للخبير'" in r and "['disputes','نزاعات'" in r
    assert 'i.searchText' in r


ROUND7_KEYS = ('expert_files_awaiting_assignment', 'expert_files_assign_overdue', 'expert_files_late',
               'expert_files_disputed', 'consultation_disputes', 'expert_files_blocked', 'expert_files_unactivated')


def test_queue_counters_read_the_real_keys(html):
    """الجولة ٧ (ب٣): «مستني توزيع» منفصل عن «ما اتستلمش من ١٢ ساعة» · نزاعات الاستشارات ليها عدّاد ·
    «فلوسها واقفة» و«اتدفعت وما وصلتش» بقى ليهم صفوف (الوجهة «الوارد» مش null)."""
    c = _body(html, 'function opsQueueCounters(')
    for key in ROUND7_KEYS:
        assert "n(Q.%s),'inbox','%s'" % (key, key) in c, key
        assert key + ':function(){efLand(' in html, key
    # «ملفات لسه ما اتستلمتش» (مستني توزيع + اتبعت مع بعض) مش شريحة: اللي اتبعت ولسه في مهلته = «للعلم».
    assert "Q.expert_files_waiting" not in c
    assert "'expert_files_unactivated'" in c and ",null,'expert_files_unactivated'" not in c
    assert 'OPSQ_NOSCREEN_NOTE' not in html
    p = _body(html, 'function opsQueuePanel(')
    for key in ('expert_files_assigned_unclaimed', 'expert_files_awaiting_payment', 'expert_files_open_total'):
        assert key in p, key


def test_queue_alerts_with_a_visible_counter_are_not_repeated(html):
    a = html[html.index('const EF_QUEUE_ALERTS='):html.index('function opsQueuePanel(')]
    for key in ROUND7_KEYS:
        assert "'%s'" % key in a, key
    # نصوص المنصة الجديدة بالحرف (ops_queue_snapshot + bridge_ops_queue)
    for text in ('ملف مستني توزيع$', 'ملف اتبعت لخبير وما اتستلمش من ١٢ ساعة$', 'ملف فلوسه ما اتحرّكتش لوحدها',
                 'نزاع على استشارة مستني قرارك$'):
        assert text in a, text
    assert 'ملف مستني خبير$' not in a                       # النص القديم اتغيّر على المنصة
    # الخدمة مقفولة: ما نقولش «وهي مقفولة ما ينفعش من هنا» (الجسر بقى شغّال بالسرّ)
    assert 'ما ينفعش من هنا' not in html and 'شغّل الخدمة على المنصة تاني' not in html


def test_inbox_nav_item_keeps_opening_the_whole_inbox(html):
    a = _body(html, 'function applyNavCounts(')
    assert "c[2]!=='inbox'" in a


@pytest.mark.parametrize('fn', NEW_UI_FUNCS)
def test_no_browser_dialogs_in_the_new_ui(html, fn):
    body = _body(html, 'function %s(' % fn)
    for bad in ('confirm(', 'prompt(', 'alert('):
        assert bad not in body, (fn, bad)


@pytest.mark.parametrize('fn', NEW_API_FUNCS)
def test_no_browser_dialogs_in_the_new_actions(apijs, fn):
    body = _body(apijs, '%s = function' % fn)
    for bad in ('confirm(', 'prompt(', 'alert('):
        assert bad not in body, (fn, bad)


def test_money_calls_send_confirmed_true(apijs):
    assert 'confirmed: true' in _body(apijs, 'EP.expertFileRefund = function')
    assert 'confirmed: true' in _body(apijs, 'EP.disputeDecide = function')
    # التوزيع مش فعل فلوس — ما بيبعتش confirmed.
    assert 'confirmed' not in _body(apijs, 'EP.expertFileSend = function')


def test_money_confirm_locks_the_button_and_the_close(html):
    m = _body(html, 'function moneyConfirmModal(')
    assert 'if(go.dataset.busy)return;' in m
    assert 'go.disabled=true' in m
    assert "s.dataset.busy='1'" in m and 'tryClose' in m
    p = _body(html, 'function expertPickModal(')
    assert "if(!pick||go.dataset.busy)return;" in p


def test_the_inbox_loader_is_admin_only_and_403_is_not_a_failure(apijs):
    inbox = apijs[apijs.index('    inbox: function () {'):apijs.index('    // الضمان والنزاعات: /api/escrow')]
    assert 'String(EP.role || "").trim().toLowerCase() === "admin"' in inbox
    assert 'e.status === 403' in inbox
    for path in ('/platform-expert-files?status=', '/platform-consultation-disputes'):
        assert path in inbox
        # كل النداءات الجديدة جوه حارس الأدمن
        assert inbox.index(path) > inbox.index('=== "admin"')


def test_a_file_dispute_is_listed_once(apijs):
    inbox = apijs[apijs.index('    inbox: function () {'):apijs.index('    // الضمان والنزاعات: /api/escrow')]
    assert 'c.expert_file_id && efDisputeIds[c.expert_file_id]' in inbox


def test_audit_labels_cover_the_new_actions(html):
    a = html[html.index('const AUDIT_LABEL={'):html.index('function auditModal(')]
    for key in ('expert_file.assign', 'expert_file.reassign', 'expert_file.refund', 'expert_file.resolve',
                'expert_file.no_reply', 'consultation.resolve', 'consultation.no_reply'):
        assert "'%s':" % key in a, key


def test_no_official_opinion_choice(html, apijs):
    for src in (html, apijs):
        for bad in ('الرأي الرسمي هو', 'اعتمد التعديل', 'اعتمد الأصلي', 'خلّي التعديل', 'الرأي المعتمد'):
            assert bad not in src, bad
    d = _body(html, 'function drawDispute(')
    assert 'القرار هنا على الفلوس بس — أنهي رأي يفضل هو الرسمي لسه هنتفق عليه.' in d
    c = _body(html, 'function opinionsCompareModal(')
    assert 'data-a=' not in c and 'disputeDecide' not in c      # المقارنة قراية بس


def _visible_strings(src):
    """النصوص العربي في الكود (بين علامات تنصيص) — اللي ممكن تتعرض."""
    return [m for m in re.findall(r"['\"`]([^'\"`]*[؀-ۿ][^'\"`]*)['\"`]", src)]


def test_no_tech_words_in_new_visible_strings(html, apijs):
    chunks = [_body(html, 'function %s(' % f) for f in NEW_UI_FUNCS]
    chunks += [_body(apijs, 'function %s(' % f) for f in NEW_ROW_FUNCS]
    chunks += [_body(apijs, '%s = function' % f) for f in NEW_API_FUNCS]
    for ch in chunks:
        for s in _visible_strings(ch):
            for bad in ('API', 'bridge', 'escrow', 'status', 'جسر', 'Bridge', 'endpoint', 'JSON'):
                assert bad not in s, (bad, s)


def test_browser_never_computes_the_hours(apijs):
    row = _body(apijs, 'function efFileRow(')
    assert 'Date.now' not in row and 'Date.parse' not in row
    assert 'hours_left' in row and 'assign_overdue' in row


def test_failures_never_show_raw_browser_or_http_text(apijs):
    """«Failed to fetch» / «HTTP 502» / «unauthorized» ما يوصلوش للمؤسس، والرد اللي مش رفض أكيد = «ما وصلناش رد»."""
    body = _body(apijs, 'function efFailed(')
    assert 'e.message' not in body
    assert '!status' in body and 'status >= 500' in body and 'noReply' in body


def test_money_windows_name_the_currency_in_words_and_the_audit_title_is_arabic(html):
    for fn in ('efRefundModal', 'efResolveModal'):
        b = _body(html, 'function %s(' % fn)
        assert "efCurName(" in b and "' ('+" not in b, fn
    assert 'Audit Log' not in html


def test_a_release_after_the_client_got_the_money_back_is_never_offered(html):
    """الجولة ٨ (البند ٥ — قرار المؤسس): العميل خد فلوسه (يدوي/البوابة) ⇒ مفيش «للخبير» خالص والفلوس فاضلة محجوزة.
    (كانت هنا نافذة «المنصة هتدفع من فلوسها» — اتشالت.)"""
    b = _body(html, 'function efResolveModal(')
    assert 'المنصة هتدفع' not in html and 'manualPaid' not in html
    assert 'if(!p||efReleaseLock(r,p))return;' in b
    # المبلغ اللي هيتحوّل له رقم دايمًا — من المنصة (`release_amount`) — ولا «نصيب الخبير» من غير رقم
    assert 'نصيب الخبير' not in b and 'const pay=p.amount' in b


# ---------------------------------------------------------------- الجولة ٧: الشاشة بتقرا، مش بتستنتج

def test_release_reads_the_amount_and_the_payee_from_the_platform(html):
    p = _body(html, 'function efPayee(')
    assert 'r.release_amount' in p and 'r.payee_name' in p
    b = _body(html, 'function efResolveModal(')
    assert 'efPayee(i)' in b
    # التخمين القديم اتشال: ولا «أجر الخبير أو المبلغ كله» محسوب هنا، ولا «الاحتمالين» في التوثيق
    for gone in ('has?r.expert_amount:r.amount', 'efIsApprovedExpert', 'efNameByEmail', 'اللي وثّق) — إلا لو'):
        assert gone not in html, gone
    d = _body(html, 'function drawDispute(')
    # «للخبير» مقفول لو مفيش حد يقبض — أو بسبب المنصة (الجولة ٨)، والسبب مكتوب تحت الزرار
    assert "const relWhy=efReleaseLock(r,payee)" in d and "efLockedBtn('btn-primary','dsp_rel'" in d
    assert "(payee?'':EF_NO_PAYEE_AR)" in _body(html, 'function efReleaseLock(')


def test_reason_names_and_fee_come_from_the_platform(html, apijs):
    for gone in ('REASON_AR', 'efNameOf'):
        assert gone not in html and gone not in apijs, gone
    assert 'f.reason_label || d.reason_label' in _body(apijs, 'function efDisputeRow(')
    assert 'd.name || d.email' in _body(apijs, 'function efFileRow(')
    assert 'd.name||d.email' in _body(html, 'function drawExpertFile(')


def test_needs_attention_badge_reads_the_platform_reason(apijs, html):
    a = _body(apijs, 'function efAttentionBadge(')
    assert 'x.label' in a and '"محتاج تدخّلك"' in a
    assert 'f.needs_attention' in a
    assert "if(f==='attn')return !!i.needsAttention;" in html
    assert "mk('attn','محتاج تدخّلك ('" in _body(html, 'function renderInbox(')


def test_unactivated_refund_is_confirmed_and_goes_by_the_money_id(apijs, html):
    b = _body(apijs, 'EP.expertFileUnactivatedRefund = function')
    assert 'confirmed: true' in b and '/platform-expert-files/unactivated/' in b and 'u.consultation_id' in b
    assert 'EP.expertFileUnactivatedRefund' in _body(html, 'function efRefundModal(')
    assert 'moneyConfirmModal' in _body(html, 'function efRefundModal(')


def test_the_browser_never_sends_by(apijs):
    """`by` بيتحط في الخادم من التوكن — المتصفح ما بيبعتهوش (ولا يقدر يزوّره)."""
    for fn in NEW_API_FUNCS:
        assert 'by:' not in _body(apijs, '%s = function' % fn), fn


def test_service_closed_hides_sending_and_says_so(html):
    d = _body(html, 'function drawExpertFile(')
    assert 'efServiceClosed()' in d and 'const others=off?[]:efOthers(i,mode);' in d
    assert 'EF_SERVICE_OFF_AR' in _body(html, 'function efServiceLine(')
    assert 'efServiceLine()+efFyiLine()' in _body(html, 'function renderInbox(')


def test_the_consultation_note_label_no_longer_warns_it_reaches_both_sides(html):
    b = _body(html, 'function efResolveModal(')
    assert 'كأن الطرفين ممكن يقروها' not in b and 'ما بتوصلش للعميل ولا للخبير' in b


# --------------------------------------------------------------------------- مراجعة الجولة ٧ (SPEC §١٦)
def test_service_closed_never_promises_money_back_on_its_own(apijs, html):
    """م١: وهي مقفولة كنسة الملفات واقفة على المنصة — ولا «فلوسه ترجع لوحدها» ولا «للعلم … مش محتاج منك حاجة»."""
    row = _body(apijs, 'function efFileRow(')
    assert 'var fyi = !closed && ' in row
    assert 'else if (pre && closed) sla = EF_OFF_MONEY_AR;' in row
    assert row.index('else if (pre && closed) sla') < row.index('وفلوسه ترجع لوحدها')
    assert 'if (pre && !closed && hl > 0 && hl <= 12) badges.unshift' in row
    assert 'مش هترجع لوحدها' in apijs[apijs.index('var EF_OFF_MONEY_AR'):][:120]
    fyi = _body(html, 'function efFyiLine(')
    assert fyi.index("if(efServiceClosed())return '';") < fyi.index('const n=inboxFyi().length;')
    d = _body(html, 'function drawExpertFile(')
    assert "off?'واقف — الخدمة مقفولة'" in d and "!off&&hl>0&&!back?'لو ما اتستلمش قبل الميعاد" in d
    assert 'الفلوس مش بتتحرّك لوحدها' in html[html.index("const EF_SERVICE_OFF_AR="):][:200]
    assert "const efSent=efQMode==='closed'?0:" in _body(html, 'function opsQueuePanel(')


def test_money_that_already_went_back_is_never_offered_a_second_refund(apijs, html):
    """م٢: الختم بسبب «الفلوس رجعت قبل كده» (البوابة/يدوي) ⇒ ولا زرار «رجّع الفلوس» ولا «رجّعها من هنا»."""
    assert 'var EF_ALREADY_BACK = { gateway_refund: true, gateway_partial: true, manual_refund: true };' in apijs
    assert 'EF_ALREADY_BACK[f.refund_blocked]' in _body(apijs, 'function efMoneyAlreadyBack(')
    assert 'efMoneyAlreadyBack(f)) out = "فلوس ملف رجعت للعميل قبل كده"' in _body(apijs, 'function efFileRow(')
    d = _body(html, 'function drawExpertFile(')
    assert 'const canRefund=(pre||work)&&!back;' in d
    assert "else if(expired){if(!back)strips+=" in d


# --------------------------------------------------------------------------- الجولة ٨ (SPEC §١٧)
def _inbox_loader(apijs):
    return apijs[apijs.index('    inbox: function () {'):apijs.index('    // الضمان والنزاعات: /api/escrow')]


def test_review_lane_is_loaded_admin_only_and_has_its_own_chip(apijs, html):
    """١: «مستنية مراجعتك» = `status=review` من المنصة، جوه حارس الأدمن، وليها شريحة فرز جوه «ملفات للخبير»."""
    inbox = _inbox_loader(apijs)
    assert '["review", "آراء مستنية مراجعتك"]' in inbox
    assert inbox.index('["review"') > inbox.index('=== "admin"')
    assert 'if (L[0] === "review") realRows.push(efReviewRow(f));' in inbox
    assert "if(f==='review')return i.efLane==='review';" in _body(html, 'function inboxMatches(')
    r = _body(html, 'function renderInbox(')
    assert "mk('review','مستنية مراجعتك ('" in r
    assert "i.apiKind==='expert_file')return 'files'" in _body(html, 'function inboxType(')     # جوه «ملفات للخبير»


def test_review_row_names_file_expert_law_amount_and_since_and_is_an_item(apijs):
    row = _body(apijs, 'function efReviewRow(')
    for key in ('f.title', 'f.law_label', 'f.expert_name', 'efMoney(f.amount, f.currency)', 'rv.submitted_at'):
        assert key in row, key
    assert 'fyi: false' in row and 'efLane: "review"' in row                # بند لازم فعل منك — مش «للعلم»
    assert 'Date.now' not in row and 'Date.parse' not in row                # «من إمتى» من المنصة (relTime بس)


def test_review_counter_and_its_landing_read_the_real_key(html):
    c = _body(html, 'function opsQueueCounters(')
    assert "n(Q.expert_files_in_review),'inbox','expert_files_in_review'" in c
    assert "expert_files_in_review:function(){efLand('review');}" in html
    a = html[html.index('const EF_QUEUE_ALERTS='):html.index('function opsQueuePanel(')]
    assert "'expert_files_in_review'" in a and 'رأي مستني مراجعتك قبل ما يوصل للعميل$' in a


def test_review_drawer_shows_the_opinion_like_the_client_and_has_the_two_decisions(html):
    d = _body(html, 'function drawReview(')
    for t in ('po.answers.map(', 'الخطوة الجاية: ', 'مبني على', 'det.based_on', 'رأي خبير معتمد لدى البروفيسور',
              'اعتمده وابعته للعميل', 'رجّعه للخبير', 'data-a="rv_ok"', 'data-a="rv_back"'):
        assert t in d, t
    assert 'EP.expertFileDetail(id)' in d                                    # «مبني على» من قراية الملف كله
    assert "el.classList.add('ef-scroll')" in d
    assert "el.classList.remove('ef-scroll')" in _body(html, 'function drawInbox(')


def test_review_approve_is_a_confirmed_money_window_and_return_needs_a_note(apijs, html):
    ok = _body(html, 'function efReviewApproveModal(')
    assert 'moneyConfirmModal(' in ok and "efCurName(f.currency)" in ok and "'المبلغ',money(f.amount)" in ok
    assert "EP.expertFileReview(i,'approve'" in ok
    back = _body(html, 'function efReviewReturnModal(')
    assert 'noteRequired:true' in back and "EP.expertFileReview(i,'return'" in back
    assert 'بتوصل للخبير زي ما هي' in back
    m = _body(html, 'function moneyConfirmModal(')
    assert 'o.noteRequired' in m and 'if(needNote()){note.focus();return;}' in m
    a = _body(apijs, 'EP.expertFileReview = function')
    assert 'if (approve) body.confirmed = true;' in a and '/review' in a
    lit = a[a.index('var body = {'):a.index('};', a.index('var body = {'))]
    assert 'confirmed' not in lit                                            # الرجوع للخبير مش فعل فلوس


def test_legacy_is_its_own_chip_drawer_and_confirmed_decision(apijs, html):
    """٣: «استشارات قديمة محتاجة قرارك» — شريحة · عدّاد · درج بفعلين بنفس نافذة التأكيد."""
    inbox = _inbox_loader(apijs)
    assert 'get("/platform-legacy-consultations")' in inbox
    assert inbox.index('/platform-legacy-consultations') > inbox.index('=== "admin"')
    assert "if(i.apiKind==='legacy')return 'legacy';" in _body(html, 'function inboxType(')
    assert "['legacy','استشارات قديمة','var(--gold)']" in _body(html, 'function renderInbox(')
    assert "if(i.apiKind==='legacy'){drawLegacy(el,i);return;}" in _body(html, 'function drawInbox(')
    c = _body(html, 'function opsQueueCounters(')
    assert "n(Q.consultations_legacy),'inbox','consultations_legacy'" in c
    assert "consultations_legacy:function(){efLand('t:legacy');}" in html
    d = _body(html, 'function drawLegacy(')
    assert "'حوّل للخبير'" in d and "'رجّع للعميل'" in d
    m = _body(html, 'function efLegacyModal(')
    assert m.count('moneyConfirmModal(') == 2 and 'EP.legacyDecide(i,action' in m
    a = _body(apijs, 'EP.legacyDecide = function')
    assert 'confirmed: true' in a and '/platform-legacy-consultations/' in a and '/decide' in a


def test_legacy_row_names_client_expert_amount_and_delivery(apijs):
    row = _body(apijs, 'function legacyRow(')
    for key in ('c.client_first_name', 'c.expert_name', 'efMoney(c.amount, c.currency)', 'c.delivered_at', 'c.title'):
        assert key in row, key
    assert 'apiKind: "legacy"' in row


def test_release_is_locked_by_the_platform_reason_everywhere(apijs, html):
    """٢: «للخبير» مقفول والسبب مكتوب تحته بكلام المنصة — نزاع ملف · نزاع استشارة · القديمة."""
    why = _body(apijs, 'function efReleaseWhy(')
    assert 'r.release_blocked_reason' in why and 'EF_RELEASE_MANUAL_AR' in why
    assert 'العميل خد فلوسه يدوي قبل كده، فمفيش تحويل للخبير من هنا. الفلوس فاضلة محجوزة لحد ما المشكلة تتحل' in apijs
    assert 'r.refund_blocked_reason' in _body(apijs, 'function efRefundWhy(')
    btn = _body(html, 'function efLockedBtn(')
    assert 'disabled' in btn and '<div class="ef-why">${esc(why)}</div>' in btn
    assert "efLockedBtn('btn-primary','dsp_rel'" in _body(html, 'function drawDispute(')
    assert "efLockedBtn('btn-human','dsp_ref'" in _body(html, 'function drawDispute(')
    d = _body(html, 'function drawLegacy(')
    assert "efLockedBtn('btn-primary','lg_rel'" in d and "efLockedBtn('btn-human','lg_ref'" in d
    assert 'efReleaseWhy' in d and 'efRefundWhy' in d
    for fn in ('efResolveModal', 'efLegacyModal'):                         # النافذة نفسها ما بتتفتحش لو مقفول
        assert 'efReleaseWhy' in _body(html, 'function %s(' % fn) or 'efReleaseLock' in _body(html, 'function %s(' % fn)


def test_service_mode_decides_closed_and_the_trial_line(apijs, html):
    """٤: الوضع (`service_mode`) هو الحَكَم — التجربة (`allowlist`) مش مقفولة، وليها سطر «مفتوحة للتجربة بس (n حساب)»."""
    inbox = _inbox_loader(apijs)
    assert 'r.service_mode' in inbox and 'var closed = mode === "closed";' in inbox
    assert 'EP.data.efServiceMode' in inbox and 'EP.data.efAllowlistSize' in inbox
    assert "return efServiceMode()==='closed';" in _body(html, 'function efServiceClosed(')
    assert "return efServiceMode()==='allowlist';" in _body(html, 'function efServiceTrial(')
    t = _body(html, 'function efTrialLine(')
    assert "'الخدمة مفتوحة للتجربة بس'" in t and "' حساب)'" in t
    assert 'efTrialLine(EP.data.efAllowlistSize)' in _body(html, 'function efServiceLine(')
    assert 'efServiceTrial()' in _body(html, 'function expertPickModal(')
    p = _body(html, 'function opsQueuePanel(')
    assert "efQMode==='allowlist'?efTrialLine(Q.expert_files_allowlist_size)" in p


def test_r8_audit_labels(html):
    a = html[html.index('const AUDIT_LABEL={'):html.index('function auditModal(')]
    for key in ('expert_file.review_approve', 'expert_file.review_return', 'consultation.legacy'):
        assert "'%s':" % key in a, key


def test_the_menu_still_has_thirteen_items(html):
    """⛔ ولا عنصر قايمة جديد (`CLAUDE.md`): الشغل كله صفوف وشرايح في «الوارد»."""
    mods = _modules(html)
    assert len([m for m, g in mods.items() if g and g != 'co']) == 12
    assert not any('legacy' in k or 'review' in k for k in mods)
