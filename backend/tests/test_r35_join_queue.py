# -*- coding: utf-8 -*-
"""R35 (قرار المؤسس 2026-11-18) — طابور «طلبات الانضمام» الواحد في «الناس ⇐ محتاج قرارك» بأنواعه + «اطلب معلومات» + قبول «أخرى».

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r35_join_queue.py
⛔ صفر شبكة: المنصة دالة في الذاكرة (`Plat` من اختبار R10)، وأي عنوان برّه `https://platform.test` يوقّع الاختبار.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
from test_r10_trainer_join import ctx, plat, _post, _audits, _read, SECRET, needs_node   # noqa: E402,F401
import v2_node   # noqa: E402


# ——————————————————————————————————————————————————————— البروكسي
def test_request_info_goes_to_the_bridge_with_the_text_and_is_audited(ctx, plat):
    n0 = _audits('trainer_application.request_info')
    assert _post(ctx, '/api/platform-trainer-applications/ta-1/request_info', {'admin_note': 'قصير'}).status_code == 400
    r = _post(ctx, '/api/platform-trainer-applications/ta-1/request_info', {'admin_note': 'أرسل رقم القيد أو صورة الكارنيه'})
    assert r.status_code == 200
    call = plat.seen[-1]
    assert call['path'] == '/api/bridge/trainer-applications/ta-1/request_info'
    assert call['json'] == {'admin_note': 'أرسل رقم القيد أو صورة الكارنيه'} and call['headers'] == {'X-ELP-Metrics-Secret': SECRET}
    assert _audits('trainer_application.request_info') == n0 + 1
    assert _post(ctx, '/api/platform-trainer-applications/ta-1/request_info', {'admin_note': 'أرسل رقم القيد'}, who='viewer').status_code in (401, 403)


def test_approve_carries_the_chosen_role_for_other_and_refuses_an_unknown_one(ctx, plat):
    r = _post(ctx, '/api/platform-trainer-applications/ta-9/approve', {'approve_as': 'provider'})
    assert r.status_code == 200 and plat.seen[-1]['json'] == {'admin_note': '', 'approve_as': 'provider'}
    n = len(plat.seen)
    assert _post(ctx, '/api/platform-trainer-applications/ta-9/approve', {'approve_as': 'king'}).status_code == 400
    assert len(plat.seen) == n
    assert _post(ctx, '/api/platform-trainer-applications/ta-9/approve', {}).status_code == 200
    assert plat.seen[-1]['json'] == {'admin_note': ''}                # الطلب العادي زي ما كان بالحرف


# ——————————————————————————————————————————————————————— البطاقة (node: v2Card الحقيقي)
def _card(**row):
    base = {'apiKind': 'trainer', 'apiId': 't1', 'ref': 'TRN-t1', 'who': 'خالد السني', 'personEmail': 'k@x.test', 'ts': 1793000000000,
            'canReject': True, 'rejectNeedsReason': True}
    base.update(row)
    return v2_node.logic('v2Card', base, {'now': 1793000000000})


@needs_node
def test_cards_name_their_type_and_carry_the_expert_fields():
    c = _card(trJoin='expert', trType='new', trSpecs=['جنائي'], trBio='محامٍ بالاستئناف، ١١ سنة في الجنايات.', trYears='من ١١ إلى ١٥ سنة',
              trBar='١٤٣٢٥٦', trFrom='د. هالة رشدي')
    assert c['tag'] == 'طلب انضمام — خبير' and c['specChips'] == ['جنائي'] and '«محامٍ بالاستئناف' in c['brain']
    assert 'رقم القيد: ١٤٣٢٥٦' in c['reason'] and 'جاء من دعوة: د. هالة رشدي' in c['reason']
    assert [c['primary']['label'], c['secondary']['label'], c['edit']['label']] == ['اقبل الطلب', 'ارفض بسبب', 'اطلب معلومات']
    assert c['edit']['act']['do'] == 'request_info'
    add = _card(trJoin='trainer', trType='add_role', trAddRole='expert', trSpecs=['تجاري وشركات'], trBio='')
    assert add['tag'] == 'إضافة صفة — خبير' and add['sub'].startswith('معتمد الآن مدرّب') and add['primary']['label'] == 'اقبل الصفة'
    assert 'بلا نبذة بعد' in add['brain']
    oth = _card(trJoin='other', trOther='مترجم قانوني', trType='new')
    assert oth['tag'] == 'طلب انضمام — أخرى: مترجم قانوني' and oth['primary']['act']['do'] == 'approve_other'
    wait = _card(trJoin='expert', trType='new', trStatus='needs_info', trInfo='اختر تخصصاتك')
    assert wait['warn'].startswith('طلبنا منه: اختر تخصصاتك')


@needs_node
def test_request_info_for_a_join_application_hits_its_own_route():
    out = v2_node.decide({'apiKind': 'trainer', 'apiId': 'ta-1', 'ref': 'TRN-ta-1'}, 'request_info', {'status': 200, 'body': {'ok': True}}, 'أرسل رقم القيد')
    assert out['calls'][0]['url'].endswith('/platform-trainer-applications/ta-1/request_info')
    assert out['calls'][0]['body']['admin_note'] == 'أرسل رقم القيد'


def test_dialog_copy_says_in_app_now_and_email_held():
    home = _read('dashboard-cloud', 'v2-home.js')
    assert "['يصله', 'إشعار داخل المنصة الآن'], ['البريد', 'محفوظ لحد جولة البريد']" in home
    assert "function otherModal(c)" in home and "['provider', 'مقدّم خدمة'" in home
    for s in ('اطلب معلومات', 'المطلوب بالضبط', 'اقبل واختر صفته'):
        assert s in home or s in _read('dashboard-cloud', 'v2-logic.js')
