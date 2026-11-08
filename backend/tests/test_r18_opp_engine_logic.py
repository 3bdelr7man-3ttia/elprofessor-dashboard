# -*- coding: utf-8 -*-
"""R18 — منطق شاشة «محرّك الفرص» (v2s/saha.js الجزء النقي) و«فحص الإعدادات» (V2L.co.cfgCheck) — في node بلا شبكة وبلا DOM.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r18_opp_engine_logic.py

اللي بيثبّته:
  ١. المواعيد بالعربي («٧ صباحًا و٧ مساءً») · «٧، ١٩» بالهندي يتطبَّع · خارج ٠..٢٣ يترفض · نفس المواعيد ⇒ «لا تغيير».
  ٢. المفتاح: ورقة المراجعة تقول الحالة قبل ⇐ بعد، وإعداد الخادم يتنبّه له · آخر تشغيل (أعطال · مشغول · فشل) · المربّع.
  ٣. المراجعة: «غالبًا مكررة» · اسم المصدر · سبب الفحص (رمز معروف ⇒ عربي، المجهول اللاتيني لا يظهر) · المصادر وتوثيقها.
  ٤. إيميل الأسبوع (الموعد · آخر إرسال) · البريد · المعاينة · نتيجة التجربة بسبب مقروء.
  ٥. فحص الإعدادات: الأحمر أولًا · القيمة المنطقية «مضبوط/غير مضبوط» · رقم هندي · المنصة غايبة تتقال.
  ٦. كل النصوص: أرقام هندية و«·» لا تلاصق رقمًا ولا «استشارة» ولا «يقوّم».
"""
import json
import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
NODE = shutil.which('node')
pytestmark = pytest.mark.skipif(not NODE, reason='needs node')
APPLY = os.path.join(_HERE, 'uiharness', 'saha_apply.js')
NOW = 1794139200000          # 2026-11-08T12:00:00Z


def S(fn, *args, of='S'):
    p = subprocess.run([NODE, APPLY], input=json.dumps({'fn': fn, 'args': list(args), 'of': of}, ensure_ascii=False), capture_output=True, text=True,
                       timeout=60, env=dict(os.environ, TZ='UTC'))
    if p.returncode != 0:
        raise RuntimeError('node failed: ' + p.stderr[-1500:])
    return json.loads(p.stdout)


def _texts(o, out=None):
    out = [] if out is None else out
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            _texts(v, out)
    elif isinstance(o, list):
        for v in o:
            _texts(v, out)
    return out


def _clean(o):
    for t in _texts(o):
        assert not re.search(r'[\d٠-٩]\s*·|·\s*[\d٠-٩]', t), t
        assert 'استشار' not in t and 'يقوّم' not in t, t


AUTO = {'enabled': True, 'source': 'settings', 'hours': '7,19', 'running': False,
        'last_result': {'fetched': 12, 'published': 2, 'drafts': 5, 'errors': 1, 'skipped': 3, 'at': '2026-11-08T05:00:00Z', 'ok': True, 'busy': False, 'failed': False}}


def test_hours_are_spoken_in_arabic():
    assert S('hourText', 7) == '٧ صباحًا' and S('hourText', 0) == '١٢ منتصف الليل' and S('hourText', 12) == '١٢ ظهرًا' and S('hourText', 19) == '٧ مساءً'
    assert S('hoursText', '7,19') == '٧ صباحًا و٧ مساءً' and S('hoursText', '6,12,18') == '٦ صباحًا، ١٢ ظهرًا و٦ مساءً' and S('hoursText', '') == ''


def test_autorun_view_and_last_run():
    v = S('engAuto', AUTO, NOW)
    assert v['on'] is True and v['statusText'] == 'يعمل كل يوم الساعة ٧ صباحًا و٧ مساءً بتوقيت القاهرة' and v['sourceText'] == 'مضبوط من هنا'
    assert v['last']['headline'] == 'اكتمل آخر تشغيل وفيه أعطال' and v['last']['when'] == 'منذ ٧ ساعات'
    assert [r['n'] for r in v['last']['rows']] == [12, 2, 5, 1]
    off = S('engAuto', dict(AUTO, enabled=False, source='env', hours='', last_result=None), NOW)
    assert off['statusText'] == 'التشغيل اليومي متوقّف' and off['hoursText'] == '٧ صباحًا' and off['last'] is None and off['sourceText'] == 'مضبوط من إعدادات الخادم'
    assert S('engAuto', {'enabled': 'yes'}, NOW) is None and S('engAuto', None, NOW) is None
    assert S('engRun', {'busy': True, 'failed': False}, NOW)['headline'] == 'كان هناك تشغيل آخر يعمل'
    assert S('engRun', {'failed': True}, NOW)['headline'] == 'تعذّر آخر تشغيل'
    _clean(v)


def test_autorun_toggle_sheet_says_before_and_after_and_warns_about_the_server_setting():
    on = S('engAuto', dict(AUTO, enabled=False, source='env'), NOW)
    t = S('engAutoToggle', on)
    assert t['body'] == {'enabled': True} and t['lines'][0]['from'] == 'متوقّف' and t['lines'][0]['to'] == 'يعمل'
    assert 'يغلب إعداد الخادم' in t['warns'][0] and 'موثوق' in t['lead'] and t['goLabel'] == 'تشغيل الجلب اليومي'
    t = S('engAutoToggle', S('engAuto', AUTO, NOW))
    assert t['body'] == {'enabled': False} and t['warns'] == [] and 'تشغيل الآن' in t['lead'] and t['goLabel'] == 'إيقاف الجلب اليومي'
    _clean(t)


@pytest.mark.parametrize('text,hours', [('٧، ١٩', '7,19'), ('19,7,7', '7,19'), (' 0 ', '0'), ('23', '23')])
def test_hours_check_normalises(text, hours):
    r = S('engHoursCheck', text, S('engAuto', dict(AUTO, hours='8'), NOW))
    # المواعيد وحدها في الجسم: حالة المفتاح تُقرأ طازة على الخادم (لا تُرسل قيمة الشاشة القديمة)
    assert r['ok'] is True and r['body'] == {'hours': hours} and 'على حاله' in r['lead'] and r['goLabel'] == 'حفظ المواعيد'


@pytest.mark.parametrize('text', ['24', '٧.٥', 'x', '', '1,2,3,4,5,6,7', '-3'])
def test_hours_check_refuses(text):
    r = S('engHoursCheck', text, S('engAuto', AUTO, NOW))
    assert r['ok'] is False and 'ساعة' in r['error']


def test_hours_check_same_hours_is_no_change_and_off_switch_is_told():
    assert S('engHoursCheck', '٧،١٩', S('engAuto', AUTO, NOW))['ok'] is False
    r = S('engHoursCheck', '9', S('engAuto', dict(AUTO, enabled=False), NOW))
    assert r['ok'] is True and r['body'] == {'hours': '9'} and r['warns']


def test_run_done_texts():
    assert S('engRunDone', {'fetched': 3, 'published': 1, 'drafts': 4, 'errors': 0}) == 'اكتمل التشغيل: نُشرت فرصة واحدة، ٤ مسودات للمراجعة'
    assert S('engRunDone', {'fetched': 3, 'published': 0, 'drafts': 0, 'errors': 2}) == 'اكتمل التشغيل: لم يُنشر شيء، ومعه عطلان'
    assert 'تشغيل آخر' in S('engRunDone', {'busy': True}) and 'تعذّر' in S('engRunDone', {'failed': True})


SRC = {'items': [{'id': 'eu', 'name': 'منح أوروبية', 'host': 'eu.test', 'url': 'https://eu.test/g', 'enabled': True, 'trusted': False,
                  'last_run': {'at': '2026-11-08T05:00:00Z', 'ok': True, 'fetched': 9}},
                 {'id': 'un', 'name': '', 'host': 'un.test', 'url': '', 'enabled': False, 'trusted': True, 'last_run': {'at': '2026-11-08T05:00:00Z', 'ok': False}},
                 {'id': 'nw', 'name': 'جديد', 'host': '', 'enabled': True, 'trusted': False, 'last_run': None}]}


def test_sources_view_and_toggles():
    v = S('engSources', SRC, NOW)
    assert v['countText'] == '٣ مصادر' and v['on'] == 2 and v['trusted'] == 1
    a, b, c = v['rows']
    assert a['lastText'] == 'منذ ٧ ساعات، جُلب ٩ عناصر' and b['name'] == 'un.test' and b['lastBad'] is True and c['lastText'] == 'لم يُجلب بعد'
    t = S('engSourceToggle', a, 'trusted')
    assert t['body'] == {'trusted': True} and 'مباشرة' in t['lead'] and t['lines'][0] == {'label': 'موثوق', 'from': 'لا', 'to': 'نعم'}
    t = S('engSourceToggle', a, 'enabled')
    assert t['body'] == {'enabled': False} and t['goLabel'] == 'إيقاف المصدر'
    assert S('engSources', {'nope': 1}, NOW) is None
    _clean(v)


def test_review_view_badge_source_and_reason():
    src = S('engSources', SRC, NOW)['rows']
    rv = {'items': [{'id': 'j1', 'title': 'منحة', 'kind': 'grant', 'provider': 'جهة', 'deadline': '2026-12-01', 'source_id': 'eu', 'possible_duplicate_of': 'j0',
                     'legal_reason': 'weak-legal-signal', 'created_at': '2026-11-08T10:00:00Z'},
                    {'id': 'j2', 'title': '', 'kind': 'weird', 'deadline': '', 'source_id': 'ghost', 'possible_duplicate_of': '', 'legal_reason': 'xyz-code'},
                    {'id': 'j3', 'title': 'ت', 'kind': 'job', 'legal_reason': 'خارج مجالات المنصة 2'}]}
    v = S('engReview', rv, src, NOW)
    a, b, c = v['rows']
    assert v['countText'] == '٣ مسودات تنتظر' and v['dupCount'] == 1
    assert a['dup'] is True and a['source'] == 'منح أوروبية' and a['reason'] == 'صلته بالقانون ضعيفة' and a['deadlineText'] == 'آخر موعد ١ ديسمبر ٢٠٢٦'
    assert b['title'] == 'فرصة بلا عنوان' and b['kindText'] == 'أخرى' and b['source'] == '' and b['reason'] == '' and b['deadlineText'] == 'بلا موعد معلن'
    assert c['reason'] == 'خارج مجالات المنصة ٢'
    assert S('engReview', {'items': []}, [], NOW)['countText'] == 'لا مسودات تنتظر'
    _clean(v)


def test_tile_from_summary():
    t = S('engTile', S('engSummary', {'drafts_waiting': 3, 'autorun': {'enabled': False}}))
    assert t == {'n': '٣', 'note': 'مسودة تنتظر مراجعتك، والتشغيل اليومي متوقّف', 'hot': True}
    t = S('engTile', S('engSummary', {'drafts_waiting': 0, 'autorun': {'enabled': True}}))
    assert t['n'] == '٠' and t['hot'] is False and t['note'] == 'لا مسودات تنتظر'
    t = S('engTile', S('engSummary', {'autorun': {'enabled': True}}))
    assert t['n'] == 'يعمل' and t['word'] is True, 'الرقم الغايب لا يصير صفرًا'
    assert S('engTile', None) is None


def test_digest_view_toggle_email_preview_and_test_result():
    d = S('engDigest', {'enabled': True, 'day': 'sun', 'hour': 10, 'last_sent_at': '2026-11-02T08:00:00Z', 'last_count': 14}, NOW)
    assert d['statusText'] == 'يعمل، كل أحد الساعة ١٠ صباحًا' and d['lastText'] == 'منذ ٦ أيام، أُرسل إلى ١٤ عضوًا'
    d0 = S('engDigest', {'enabled': False, 'day': '', 'hour': None, 'last_sent_at': None, 'last_count': 0}, NOW)
    assert d0['statusText'] == 'متوقّف' and d0['lastText'] == 'لم يُرسل بعد'
    t = S('engDigestToggle', d0)
    assert t['body'] == {'enabled': True} and 'فرص الأسبوع في مسارك' in t['lead']
    assert S('engEmailCheck', ' Me@X.test ') == {'ok': True, 'email': 'me@x.test'}
    for bad in ('', 'a@b', 'a b@c.test', '<a@b.test>'):
        assert S('engEmailCheck', bad)['ok'] is False
    p = S('engPreview', {'subject': 'فرص الأسبوع في مسارك', 'html': '<p>x</p>', 'count': 3, 'track': 'eg-intl', 'track_title': 'القانون الدولي',
                         'reason': '', 'will_send': True, 'too_big': False})
    assert p['countText'] == '٣ فرص' and p['html'] == '<p>x</p>' and p['trackText'] == 'القانون الدولي' and p['warn'] == '' and p['willSend'] is True
    assert 'eg-intl' not in str(p), 'رمز المسار اللاتيني لا يظهر'
    assert S('engPreview', {'count': 0})['countText'] == 'لا فرص في هذا الأسبوع'
    assert S('engTestDone', {'sent': True}).startswith('أُرسلت')
    assert S('engTestDone', {'sent': False, 'reason': 'unsubscribed'}) == 'لم تُرسل رسالة التجربة: صاحب هذا البريد أوقف رسائل المنصة'
    assert S('engTestDone', {'sent': False, 'reason': 'zzz'}) == 'لم تُرسل رسالة التجربة: المنصة لم ترسلها'
    _clean([d, d0, t, p])


def test_config_check_view():
    v = S('co.cfgCheck', {'platform_ok': True, 'items': [
        {'key': 'tg', 'label_ar': 'توكن البوت', 'value': True, 'ok': True},
        {'key': 'cap', 'label_ar': 'سقف نداءات الذكاء اليومي', 'value': 300, 'ok': False, 'fix_ar': 'في Coolify ← الباك إند ← المتغيرات: AI_DAILY_CALLS_CAP = 1500 أو امسحه'},
        {'key': 'free', 'label_ar': 'التجربة المجانية', 'value': 'once', 'ok': None},
        {'key': '', 'label_ar': 'x'}, 'bad']}, of='L')
    assert [r['key'] for r in v['rows']] == ['cap', 'tg', 'free'], 'الأحمر أولًا'
    assert v['rows'][0]['value'] == '٣٠٠' and v['rows'][1]['value'] == 'مضبوط' and v['rows'][2]['ok'] is None
    assert v['head'] == 'إعداد واحد يحتاج تعديلًا' and v['platformNote'] == ''
    m = S('co.cfgCheck', {'platform_ok': False, 'platform_missing': True, 'items': [{'key': 'dash.x', 'label_ar': 'ربط', 'value': True, 'ok': True, 'where': 'dashboard'}]}, of='L')
    assert m['head'] == 'لا مشكلة فيما أمكن فحصه' and 'غير متاح بعد' in m['platformNote'] and m['rows'][0]['where'] == 'dashboard'
    assert S('co.cfgCheck', {'platform_ok': True, 'items': [{'key': 'a', 'label_ar': 'أ', 'value': False, 'ok': True}]}, of='L')['head'] == 'كل الإعدادات سليمة'
    assert S('co.cfgCheck', {'items': 'x'}, of='L') is None and S('co.cfgCheck', None, of='L') is None


# ---------------------------------------------------------------- جولة التصليح: رموز المنصة الحقيقية (opp_digest.preview / send_test)
@pytest.mark.parametrize('reason,frag', [
    ('no-brevo-key', 'مفتاح خدمة البريد غير مضبوط'), ('no-items', 'لا فرص جديدة'), ('brevo-rejected', 'خدمة البريد رفضت الإرسال'),
    ('bad-email', 'البريد الإلكتروني غير صحيح'), ('unsubscribed', 'أوقف رسائل المنصة')])
def test_send_test_maps_the_platform_reason_codes(reason, frag):
    t = S('engTestDone', {'sent': False, 'reason': reason})
    assert t.startswith('لم تُرسل رسالة التجربة: ') and frag in t and 'المنصة لم ترسلها' not in t


def test_send_test_sample_track_explains_the_other_track():
    t = S('engTestDone', {'sent': True, 'reason': 'sample-track'})
    assert t.startswith('أُرسلت') and 'مسار آخر' in t and 'بلا مسار' in t


@pytest.mark.parametrize('reason,frag', [
    ('unsubscribed', 'أوقف رسائل المنصة، فلن تصله الرسالة'), ('pending', 'ينتظر فتح الدخول'), ('inactive', 'موقوف'), ('test-account', 'حساب تجريبي')])
def test_preview_warns_when_the_member_will_not_get_it(reason, frag):
    p = S('engPreview', {'subject': 'فرص الأسبوع في مسارك', 'html': '<p>x</p>', 'count': 2, 'track': 'eg-x', 'track_title': 'النيابة العامة',
                         'reason': reason, 'will_send': False})
    assert frag in p['warn'] and p['html'] == '<p>x</p>' and p['countText'] == 'فرصتان' and p['willSend'] is False


def test_preview_no_user_replaces_the_count_with_the_reason():
    p = S('engPreview', {'subject': 'فرص الأسبوع في مسارك', 'html': '', 'count': 0, 'track': '', 'reason': 'no-user', 'will_send': False})
    assert p['warn'] == 'هذا البريد ليس لعضو على المنصة' and p['countText'] == '' and p['trackText'] == ''
    p = S('engPreview', {'html': '', 'count': 0, 'reason': 'zzz', 'will_send': False})
    assert p['warn'] == 'لن تصل هذه الرسالة لصاحب هذا البريد'


def test_engine_copy_is_gender_neutral():
    js = open(os.path.join(ROOT, 'dashboard-cloud', 'v2s', 'saha.js'), encoding='utf-8').read()
    eng = js[js.index('// —— ٦ب · محرّك الفرص (R18)'):js.index('// ------------------------------------------------------------------ التسجيل')]
    logic = js[js.index('٦ب · محرّك الفرص (R18)'):js.index('٧ · الديوان · الأعمال')]
    for bad in ('شغّل الآن', 'غيّر المواعيد', 'أضف المصادر', '>انشر<', '>ارفض<', 'افتح للتعديل', 'اجعله موثوق', 'ألغِ التوثيق', 'أعد الفحص',
                'اكتب بريد', 'اكتب ساعة', 'اكتب الساعة', 'احفظ', 'أرسل التجربة', 'ابدأ التشغيل', "'أوقف", "'شغّل", 'حاول '):
        assert bad not in eng and bad not in logic, bad
    for good in ('تشغيل الآن', 'تغيير المواعيد', 'إضافة المصادر الأولى', '>نشر<', '>رفض<', 'فتح للتعديل', 'توثيق المصدر', 'إلغاء التوثيق'):
        assert good in eng or good in logic, good


def test_config_check_card_shows_the_flattened_platform_text_in_arabic_digits():
    """الخادم بيسطّح قاموس المنصة لنص (`tg_ops._check_value`)؛ البطاقة تعرضه بأرقام عربية."""
    v = S('co.cfgCheck', {'platform_ok': True, 'items': [
        {'key': 'ai_daily_calls_cap', 'label_ar': 'سقف نداءات الذكاء في اليوم', 'value': '300 (من إعدادات الخادم)', 'ok': False, 'fix_ar': 'x'},
        {'key': 'opp_autorun', 'label_ar': 'جلب الفرص اليومي', 'value': 'يعمل، الساعة 7 و19 (محفوظ في المنصة)', 'ok': True}]}, of='L')
    vals = {r['key']: r['value'] for r in v['rows']}
    assert vals['ai_daily_calls_cap'] == '٣٠٠ (من إعدادات الخادم)' and vals['opp_autorun'] == 'يعمل، الساعة ٧ و١٩ (محفوظ في المنصة)'
