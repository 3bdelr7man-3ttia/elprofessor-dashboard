# -*- coding: utf-8 -*-
"""منطق «الأدوات / الاستوديو» في الداشبورد (v2s/tools.js، الجزء النقي) + تبويب «الأدوات» في خريطة الأقسام — بيتشغّل في node بلا شبكة وبلا DOM.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_tools_logic.py

اللي بيثبّته:
  ١. نظرة اليوم: ثلاث حالات (شغّال · متوقف يدويًا · استراحة السقف) · نسبة الصرف · أعمال اليوم والفاشل (المصدر الفاشل «—» لا صفر) · المفاتيح للقراءة فقط وتحذيرات الخادم.
  ٢. الأدوات: ترتيب المجموعات · السعر والقاعدة المجانية · الحدّ الأدنى للسعر (التكلفة × المضاعِف × الصرف، تقريب لأعلى) · تحقق الخانات وحارس السعر والصفر · الفروق.
  ٣. الأماكن: التجميع بالأداة · ظاهر/غير ظاهر · المحمي من الحذف · التحقق (الاسم والترتيب والوصف والصورة بنوعها وحجمها) · معرّف ثابت للنافذة.
  ٤. الإعدادات: السقف ≤ الحدّ الأقصى ≤ ٥٠ · المضاعِفات · الأعداد الصحيحة · الشحن لكل عملة وسقفه · الصرف · لا يُرسل إلا ما تغيّر · «لا تغيير» ليس خطأ.
  ٥. العيّنات: الصفوف ونصوص «سليم / أخفِ / امنع» (الاسترداد مذكور) · ٦. التقرير: الإجماليات بلا جمع عملات · الشحن منفصل «رصيد للعميل لا إيراد» · «غير متاح بعد» لا صفر · الفترة.
  ٧. النصوص: أرقام هندية و«·» ما تلاصق رقمًا · لا «يقوّم» ولا مصطلحات تقنية · «أخرى» في أي قائمة اختيار حر.
  ٨. الخريطة: تبويب «الأدوات» في قسم «الشركة ورأس المال» بدون مربّع جديد في اللوحة.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import tools_fixtures as tfx   # noqa: E402

NODE = shutil.which('node')
needs_node = pytest.mark.skipif(not NODE, reason='needs node')
NOW = 1793361600000          # 2026-10-30T12:00:00Z
H = 3600e3


def _run(fn, args, of):
    p = subprocess.run([NODE, os.path.join(_HERE, 'uiharness', 't_apply.js')], input=json.dumps({'fn': fn, 'args': list(args), 'of': of}, ensure_ascii=False),
                       capture_output=True, text=True, timeout=60, env=dict(os.environ, TZ='UTC'))
    if p.returncode != 0:
        raise RuntimeError('node failed: ' + p.stderr[-1500:])
    return json.loads(p.stdout)


def M(fn, *args):
    return _run(fn, args, 'M')


def L(fn, *args):
    return _run(fn, args, 'L')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _texts(o, out=None):
    out = [] if out is None else out
    if isinstance(o, str):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', o):          # تاريخ ISO قيمة داخلية لا نصًّا ظاهرًا
            out.append(o)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k not in ('preview', 'ts', 'id', 'recipeId', 'updatedAt', 'kind', 'range', 'provider', 'state', 'free', 'group', 'rule'):
                _texts(v, out)
    elif isinstance(o, list):
        for v in o:
            _texts(v, out)
    return out


def _clean_copy(o, label=''):
    for t in _texts(o):
        assert not re.search(r'[\d٠-٩]\s*·|·\s*[\d٠-٩]', t), (label, t)
        assert not re.search(r'[0-9]', re.sub(r'@\S+', '', t)), (label, 'رقم لاتيني', t)
        assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', t), (label, t)
        assert not re.search(r'(?<![A-Za-z])(API|JSON|endpoint|token|bridge|Claude|DeepSeek|OpenAI|Higgsfield|mock|live|kill)(?![A-Za-z])', t), (label, t)


def _ov(**over):
    d = {'flags': {'tools_enabled': False, 'provider': 'mock', 'topup_enabled': False}, 'today': {'cap_usd': 10, 'spent_usd': 2.4, 'remaining_usd': 7.6, 'kill': False, 'paused': False, 'reason': None},
         'ffmpeg': True, 'raqm': True, 'jobs': {'count': 43, 'succeeded': 41, 'failures': 2}}
    d.update(over)
    return d


def _rec():
    return {'recipes': [r for r in _json_recipes()], 'styles': _json_styles()}


def _json_recipes():
    rs = tfx.seed_recipes()
    for r in rs:
        r.pop('prompt_template', None)
    return rs


def _json_styles():
    return [dict(s, preview_data='data:image/jpeg;base64,AAAA' if s.get('preview_data') else '') for s in tfx.seed_styles()]


# ---------------------------------------------------------------- ١) نظرة اليوم

@needs_node
def test_overview_three_states_and_the_progress():
    o = M('overview', _ov())
    assert o['state'] == 'on' and o['stateText'] == 'الاستوديو شغّال' and o['pct'] == 24 and o['killed'] is False
    assert o['spendLine'] == 'صُرف اليوم ٢٫٤ دولار من ١٠ دولارات' and o['remainingLine'] == 'المتبقي ٧٫٦ دولار'
    assert (o['jobsText'], o['okText'], o['failText'], o['failHot']) == ('٤٣', '٤١', '٢', True)
    k = M('overview', _ov(today={'cap_usd': 10, 'spent_usd': 2.4, 'remaining_usd': 7.6, 'kill': True, 'paused': True, 'reason': 'kill'}))
    assert k['state'] == 'kill' and k['killed'] is True and 'متوقف يدويًا' in k['stateText'] and 'أعد تشغيله' in k['stateNote']
    c = M('overview', _ov(today={'cap_usd': 10, 'spent_usd': 9.95, 'remaining_usd': 0.05, 'kill': False, 'paused': True, 'reason': 'cap'}))
    assert c['state'] == 'cap' and 'استراحة' in c['stateText'] and c['pct'] == 99 and 'ارفع السقف' in c['stateNote']
    assert M('overview', _ov(today={'cap_usd': 10, 'spent_usd': 0, 'remaining_usd': 10, 'kill': False, 'paused': False}))['spendLine'] == 'لم يُصرف شيء اليوم، والسقف ١٠ دولارات'
    _clean_copy([o, k, c], 'overview')


@needs_node
def test_overview_failed_report_is_a_dash_not_a_zero_and_a_bad_source_is_null():
    o = M('overview', _ov(jobs=None))
    assert o['jobs'] is None and o['jobsText'] == '—' and o['failText'] == '—' and o['failHot'] is False
    assert M('overview', None) is None and M('overview', {}) is None and M('overview', {'today': 5}) is None
    assert M('overview', _ov(today={'kill': False, 'paused': False}))['spendLine'] == 'الصرف غير متاح بعد'


@needs_node
def test_overview_flags_are_read_only_facts_and_server_warnings_show():
    o = M('overview', _ov())
    f = {x['k']: x for x in o['facts']}
    assert f['وضع الرسم']['v'] == 'تجريبي' and f['الأدوات للأعضاء']['v'] == 'مغلقة' and f['شحن الرصيد']['v'] == 'مغلق'
    live = M('overview', _ov(flags={'tools_enabled': True, 'provider': 'live', 'topup_enabled': True}))
    f = {x['k']: x for x in live['facts']}
    assert f['وضع الرسم']['v'] == 'حيّ' and f['الأدوات للأعضاء']['v'] == 'مفتوحة' and f['شحن الرصيد']['v'] == 'مفتوح' and live['toolsEnabled'] is True
    w = M('overview', _ov(ffmpeg=False, raqm=False))
    assert len(w['warns']) == 2 and 'الفيديو' in w['warns'][0] and 'الحروف العربية' in w['warns'][1]
    _clean_copy([live, w], 'overview-flags')


@needs_node
def test_kill_copy_is_a_stop_and_a_resume_with_their_own_buttons():
    s, r = M('killCopy', True), M('killCopy', False)
    assert s['go'] == 'أوقف الاستوديو الآن' and 'فورًا' in s['lead'] and r['go'] == 'أعد تشغيل الاستوديو' and s['title'] != r['title']
    _clean_copy([s, r], 'kill')


# ---------------------------------------------------------------- ٢) الأدوات

@needs_node
def test_recipes_group_order_prices_free_rules_and_counts():
    d = M('recipes', _rec())
    assert [g['key'] for g in d['groups']] == ['photo', 'social', 'video_cards'] and [g['label'] for g in d['groups']] == ['صورتك', 'لينكدإن والسوشيال', 'الفيديو والكروت']
    by = {r['id']: r for r in d['rows']}
    assert [r['id'] for r in d['rows']] == ['headshot', 'linkedin', 'post', 'card', 'trend_video']
    assert by['headshot']['priceText'] == '٢٠ جنيه، و٦ عملات أخرى' and by['headshot']['freeText'] == 'مجانًا أول مرة لكل حساب موثّق' and by['headshot']['enabled'] is True
    assert by['card']['priceText'] == 'بلا سعر' and by['card']['freeText'] == 'مجانية دائمًا' and by['card']['providerText'] == 'تصميم بالكود بلا تكلفة' and by['card']['costText'] == ''
    assert by['post']['freeText'] == 'مجانًا مرة واحدة كل يوم' and by['headshot']['costText'] == 'تكلفتها علينا نحو ٠٫١٢ دولار للعمل'
    assert by['headshot']['stylesText'] == '٤ أماكن ظاهرة' and d['enabledCount'] == 2 and d['countText'] == '٢ من ٥ أدوات شغّالة'
    assert by['trend_video']['video'] is True and by['headshot']['canEnable'] is True
    _clean_copy(d, 'recipes')


@needs_node
def test_recipes_bad_source_is_null_and_an_unknown_group_goes_to_other():
    assert M('recipes', None) is None and M('recipes', {}) is None and M('recipes', {'recipes': 'x'}) is None
    rs = _json_recipes()
    rs[0]['group'] = 'brand_new'
    d = M('recipes', {'recipes': rs, 'styles': []})
    assert d['groups'][-1]['key'] == 'other' and d['groups'][-1]['label'] == 'أخرى'


@needs_node
def test_free_rule_texts_cover_every_rule():
    assert M('freeText', 'none') == 'بلا قاعدة مجانية' and M('freeText', 'always') == 'مجانية دائمًا'
    assert M('freeText', 'daily:2') == 'مجانًا مرتين كل يوم' and M('freeText', 'daily:12') == 'مجانًا ١٢ مرة كل يوم' and M('freeText', 'weekly:1') == 'قاعدة غير معروفة'
    assert [o[0] for o in M('ruleOptions')] == ['none', 'once_per_verified_account', 'always', 'daily']
    assert M('ruleForm', 'daily:3') == {'rule': 'daily', 'daily': '٣'} and M('ruleForm', 'always')['rule'] == 'always' and M('ruleForm', 'zzz')['rule'] == 'none'


@needs_node
def test_enable_copy_says_what_happens_and_warns_when_tools_are_closed_to_members():
    row = {'title': 'لينكدإن قوي', 'provider': True, 'priceText': '٤٠ جنيه، و٦ عملات أخرى'}
    on = M('enableCopy', row, True, False)
    assert on['go'] == 'شغّل الأداة' and 'السقف اليومي' in on['lead'] and 'مغلقة للأعضاء' in on['lead']
    assert 'مغلقة' not in M('enableCopy', row, True, True)['lead']
    code = M('enableCopy', dict(row, provider=False), True, True)
    assert 'بالكود' in code['lead']
    off = M('enableCopy', row, False, True)
    assert off['go'] == 'أوقف الأداة' and 'فورًا' in off['lead'] and 'جديدة' in off['lead']
    _clean_copy([on, code, off], 'enable')


@needs_node
def test_price_minimum_is_cost_times_multiple_times_rate_rounded_up():
    rec = {'provider': True, 'cost': 0.12, 'video': False}
    m = M('priceMins', rec, {'image_min_multiple': 3, 'video_min_multiple': 2.5, 'rates': {'EGP': 50, 'SAR': 3.75, 'KWD': 0.31, 'USD': 1}})
    assert m['EGP'] == 18 and m['USD'] == 0.36 and m['SAR'] == 1.35 and m['KWD'] == 0.12      # ٠٫١١١٦ ⇒ ٠٫١٢ لأعلى
    v = M('priceMins', {'provider': True, 'cost': 0.6, 'video': True}, {'video_min_multiple': 2.5, 'rates': {'EGP': 50}})
    assert v['EGP'] == 75 and v['USD'] == 1.5
    assert all(x == 0 for x in M('priceMins', {'provider': False, 'cost': 0.5}, {}).values()) and all(x == 0 for x in M('priceMins', {'provider': True, 'cost': 0}, {}).values())


SET = {'image_min_multiple': 3, 'video_min_multiple': 2.5, 'rates': {'EGP': 50, 'SAR': 3.75, 'AED': 3.67, 'QAR': 3.64, 'KWD': 0.31, 'OMR': 0.385, 'USD': 1}}


def _headshot_row():
    d = M('recipes', _rec())
    return [r for r in d['rows'] if r['id'] == 'headshot'][0]


def _form(row, **over):
    f = M('recipeInputs', row)
    f.update(over)
    return f


@needs_node
def test_recipe_inputs_are_arabic_digits_and_the_check_accepts_both_digit_sets():
    row = _headshot_row()
    f = M('recipeInputs', row)
    assert f['price']['EGP'] == '٢٠' and f['price']['KWD'] == '٠٫٤' and f['est'] == '٠٫١٢' and f['rule'] == 'once_per_verified_account'
    ok = M('recipeCheck', row, f, SET)
    assert ok['ok'] is True and ok['payload']['price']['EGP'] == 20 and ok['payload']['price']['KWD'] == 0.4 and ok['payload']['est_cost_usd'] == 0.12
    assert ok['payload']['free_rule'] == 'once_per_verified_account'
    latin = M('recipeCheck', row, _form(row, price=dict(f['price'], EGP='25', SAR='6.5', AED='١٬٠٠٠'), est='0.1'), SET)
    assert latin['ok'] is True and latin['payload']['price']['EGP'] == 25 and latin['payload']['price']['SAR'] == 6.5 and latin['payload']['price']['AED'] == 1000 and latin['payload']['est_cost_usd'] == 0.1


@needs_node
@pytest.mark.parametrize('price,frag', [
    ({'EGP': ''}, 'اكتب السعر'), ({'EGP': 'abc'}, 'اكتب السعر'), ({'EGP': '-5'}, 'اكتب السعر'), ({'EGP': '١٠٠٠٠١'}, 'اكتب السعر'), ({'EGP': '1.23456'}, 'اكتب السعر'),
    ({'EGP': '5'}, 'أقل سعر مسموح ١٨ جنيه'), ({'USD': '0.2'}, 'أقل سعر مسموح ٠٫٣٦ دولار'), ({'KWD': '0.1'}, 'أقل سعر مسموح ٠٫١٢ دينار كويتي'),
])
def test_recipe_check_flags_the_bad_price_per_currency(price, frag):
    row = _headshot_row()
    f = M('recipeInputs', row)
    f['price'].update(price)
    r = M('recipeCheck', row, f, SET)
    key = 'price_' + list(price)[0]
    assert r['ok'] is False and key in r['errors'] and frag in r['errors'][key], r['errors']
    assert r['error'] == 'صحّح الخانات المعلَّمة'


@needs_node
def test_a_zero_price_needs_a_free_rule_when_the_recipe_costs_something():
    row = _headshot_row()
    f = M('recipeInputs', row)
    f['price']['EGP'] = '٠'
    f['rule'] = 'none'
    bad = M('recipeCheck', row, f, SET)
    assert bad['ok'] is False and 'السعر صفر' in bad['errors']['price_EGP']
    f['rule'] = 'always'
    assert M('recipeCheck', row, f, SET)['ok'] is True
    card = M('recipes', _rec())['rows']
    card = [r for r in card if r['id'] == 'card'][0]
    fc = M('recipeInputs', card)
    assert fc['price']['EGP'] == '٠' and M('recipeCheck', card, fc, SET)['ok'] is True and 'est_cost_usd' not in M('recipeCheck', card, fc, SET)['payload']


@needs_node
def test_est_cost_and_the_daily_rule_are_validated_and_move_the_minimum():
    row = _headshot_row()
    f = M('recipeInputs', row)
    for bad in ('', 'x', '21', '-1', '0.123456'):
        assert M('recipeCheck', row, dict(f, est=bad), SET)['errors'].get('est'), bad
    r = M('recipeCheck', row, dict(f, est='0.5'), SET)                  # ٠٫٥ × ٣ × ٥٠ = ٧٥ جنيه ⇒ السعر الحالي ٢٠ يقع تحت الحد الجديد
    assert r['ok'] is False and 'أقل سعر مسموح ٧٥ جنيه' in r['errors']['price_EGP']
    assert M('recipeCheck', row, dict(f, rule='daily', daily=''), SET)['errors']['rule'] == 'اكتب عددًا صحيحًا من ١ إلى ٩٩٩'
    assert M('recipeCheck', row, dict(f, rule='daily', daily='0'), SET)['errors'].get('rule')
    assert M('recipeCheck', row, dict(f, rule='daily', daily='1000'), SET)['errors'].get('rule')
    ok = M('recipeCheck', row, dict(f, rule='daily', daily='٣'), SET)
    assert ok['ok'] is True and ok['payload']['free_rule'] == 'daily:3'
    assert M('recipeCheck', row, dict(f, rule='nope'), SET)['errors'].get('rule')


@needs_node
def test_recipe_diff_lists_only_what_changed_with_before_and_after():
    row = _headshot_row()
    p = {'price': {'EGP': 25, 'SAR': 5, 'AED': 5, 'QAR': 5, 'KWD': 0.4, 'OMR': 0.5, 'USD': 1}, 'est_cost_usd': 0.1, 'free_rule': 'daily:2'}
    lines = M('recipeDiff', row, p)
    assert [l['label'] for l in lines] == ['السعر بـجنيه مصري', 'التكلفة التقديرية للعمل', 'القاعدة المجانية']
    assert lines[0] == {'label': 'السعر بـجنيه مصري', 'from': '٢٠ جنيه', 'to': '٢٥ جنيه'} and lines[2]['to'] == 'مجانًا مرتين كل يوم'
    assert M('recipeDiff', row, {'price': row['price'], 'est_cost_usd': 0.12, 'free_rule': row['free']}) == []
    _clean_copy(lines, 'diff')


@needs_node
def test_a_confirmed_not_saved_or_not_attached_reply_shows_the_platforms_message_not_a_lost_reply():
    assert M('writeError', 502, {'error': 'تعذّر ربط المكان بالأداة، لم يُحفظ شيء. حاول مرة أخرى', 'not_saved': True}) == 'تعذّر ربط المكان بالأداة، لم يُحفظ شيء. حاول مرة أخرى'
    assert 'لم يُربط' in M('writeError', 502, {'error': 'أُضيف المكان لكنه لم يُربط بالأداة. حدّث الصفحة', 'attach_failed': True})
    assert M('writeError', 502, {}) == 'تعذّر الحفظ، حاول مرة أخرى', 'بلا علامة أكيدة ⇒ النص العام'
    assert M('writeError', 409, {'error': 'هذا آخر مكان شغّال في أداة شغّالة. أوقف الأداة أولًا'}).startswith('هذا آخر مكان شغّال')


@needs_node
def test_write_errors_pass_the_platform_text_in_arabic_digits_and_lost_replies_stay_lost():
    assert M('writeError', 409, {'error': 'تغيّرت هذه الأداة منذ فتحت الصفحة.'}).startswith('تغيّرت هذه الأداة')
    assert M('writeError', 422, {'error': 'سعر EGP أقل من الحد الأدنى (التكلفة × 3)'}) == 'سعر EGP أقل من الحد الأدنى (التكلفة × ٣)'
    assert M('writeError', 502, {'error': 'لم يصل رد. حدّث الصفحة.', 'no_reply': True}) == 'لم يصل رد. حدّث الصفحة.'
    assert M('writeError', 404, {}) == 'لم تعد هذه الأداة موجودة على المنصة' and M('writeError', 500, {}) == 'تعذّر الحفظ، حاول مرة أخرى'
    assert M('writeError', 413, {'error': 'صورة المكان أكبر من 3 ميجا'}) == 'صورة المكان أكبر من ٣ ميجا'


# ---------------------------------------------------------------- ٣) الأماكن والأنماط

@needs_node
def test_styles_group_by_recipe_with_visible_flag_and_protection():
    d = M('styles', _rec())
    secs = {s['recipe']['id']: s for s in d['sections']}
    hs = secs['headshot']
    assert [s['id'] for s in hs['styles']] == ['hs_office', 'hs_library', 'hs_entrance', 'hs_plain'] and all(s['visible'] for s in hs['styles']) and hs['canAdd'] is True
    assert hs['styles'][0]['hasPreview'] is True and hs['styles'][0]['judgeOk'] is False and hs['styles'][1]['judgeOk'] is True and hs['styles'][0]['orderText'] == 'الترتيب ١'
    assert secs['card']['canAdd'] is False and all(s['codeOnly'] for s in secs['card']['styles'])
    prot = {s['id']: s['protectedKind'] for s in secs['card']['styles']}
    assert prot == {'card_expert': True, 'card_cert': True, 'card_winner': True} and not any(s['canDelete'] for s in secs['card']['styles'])
    assert all(s['canDelete'] for s in hs['styles'])
    li = secs['linkedin']['styles']
    assert [s['hasPreview'] for s in li] == [False, False, False] and secs['linkedin']['enabled'] is False
    post = {s['id']: s for s in secs['post']['styles']}
    assert post['post_answer']['visible'] is True and secs['post']['canAdd'] is True and post['post_quote']['codeOnly'] is True
    assert d['total'] == 15 and d['totalText'] == '١٥ تصميمًا'
    _clean_copy(d, 'styles')


@needs_node
def test_a_style_that_is_not_in_the_recipe_list_is_marked_not_visible():
    rs = _json_recipes()
    rs[0]['styles'] = ['hs_office']
    d = M('styles', {'recipes': rs, 'styles': _json_styles()})
    hs = [s for s in d['sections'] if s['recipe']['id'] == 'headshot'][0]
    assert [(s['id'], s['visible']) for s in hs['styles']] == [('hs_office', True), ('hs_library', False), ('hs_entrance', False), ('hs_plain', False)]
    assert M('styles', None) is None and M('styles', {'recipes': []}) is None


@needs_node
def test_style_check_validates_the_name_order_description_and_the_picture():
    ok = M('styleCheck', {'title': ' مكتب الاجتماعات ', 'sort': '٣', 'place': 'a quiet meeting room', 'judge': True, 'file': {'name': 'x'}}, True)
    assert ok['ok'] is True and ok['payload'] == {'title_ar': 'مكتب الاجتماعات', 'sort': 3, 'place_prompt': 'a quiet meeting room', 'judge_ok': True}
    for form, key in (({'title': '', 'sort': '1', 'place': 'x', 'file': 1}, 'title'), ({'title': 'ا' * 61, 'sort': '1', 'place': 'x', 'file': 1}, 'title'),
                      ({'title': 'م', 'sort': '', 'place': 'x', 'file': 1}, 'sort'), ({'title': 'م', 'sort': '1000', 'place': 'x', 'file': 1}, 'sort'), ({'title': 'م', 'sort': '1.5', 'place': 'x', 'file': 1}, 'sort'),
                      ({'title': 'م', 'sort': '1', 'place': '', 'file': 1}, 'place'), ({'title': 'م', 'sort': '1', 'place': 'x' * 401, 'file': 1}, 'place'),
                      ({'title': 'م', 'sort': '1', 'place': 'x'}, 'file')):
        r = M('styleCheck', form, True)
        assert r['ok'] is False and key in r['errors'], (form, r['errors'])
    edit = M('styleCheck', {'title': 'م', 'sort': '2', 'place': '', 'judge': False}, False)
    assert edit['ok'] is True and edit['payload']['place_prompt'] == '' and edit['payload']['judge_ok'] is False
    code_only = M('styleCheck', {'title': 'م', 'sort': '2', 'hasPlace': False}, False)
    assert code_only['ok'] is True and 'place_prompt' not in code_only['payload']


@needs_node
def test_file_check_uses_type_and_size_and_the_style_id_is_stable_per_window():
    ok = {'type': 'image/png', 'size': 1000}
    assert M('fileCheck', ok)['ok'] is True and M('fileCheck', {'type': 'image/webp', 'size': 3 * 1024 * 1024})['ok'] is True
    assert 'JPG أو PNG أو WebP' in M('fileCheck', {'type': 'text/html', 'size': 10})['error'] and M('fileCheck', {'type': 'application/pdf', 'size': 10})['ok'] is False
    assert M('fileCheck', {'type': 'image/png', 'size': 3 * 1024 * 1024 + 1})['error'] == 'صورة المكان أكبر من ٣ ميجا'
    assert M('fileCheck', {'type': 'image/png', 'size': 0})['ok'] is False and M('fileCheck', None)['error'] == 'اختر صورة المكان'
    assert M('newStyleId', 'A1B2C3D4E5') == 'st_a1b2c3d4' and M('newStyleId', 'xyz') == 'st_00000000' and re.fullmatch(r'st_[0-9a-f]{8}', M('newStyleId', '12345678'))


@needs_node
def test_style_diff_visible_delete_and_create_copy():
    st = {'title': 'مكتبة', 'sort': 2, 'place': 'old', 'judgeOk': True}
    lines = M('styleDiff', st, {'title_ar': 'المكتبة', 'sort': 5, 'place_prompt': 'new', 'judge_ok': False, 'preview_data': 'data:image/png;base64,AA'})
    assert [l['label'] for l in lines] == ['الاسم', 'الترتيب', 'وصف المكان', 'يناسب القضاة وأعضاء النيابة', 'الصورة'] and lines[1] == {'label': 'الترتيب', 'from': '٢', 'to': '٥'}
    assert M('styleDiff', st, {'title_ar': 'مكتبة', 'sort': 2, 'place_prompt': 'old', 'judge_ok': True}) == []
    show, hide = M('visibleCopy', st, True, 'صورتك المهنية'), M('visibleCopy', st, False, 'صورتك المهنية')
    assert show['go'] == 'أظهره للناس' and hide['go'] == 'أخفِه عن الناس' and 'محفوظًا' in hide['lead']
    dele = M('deleteCopy', st, 'صورتك المهنية')
    assert dele['go'] == 'احذف المكان' and 'نهائيًا' in dele['lead'] and 'أخفِه' in dele['lead']
    assert 'وظهر للناس' in M('createDone', {'attached': True}) and 'غير ظاهر' in M('createDone', {'attached': False}) and 'لم يُربط' in M('createDone', {'attach_failed': True})
    _clean_copy([lines, show, hide, dele], 'style-copy')


# ---------------------------------------------------------------- ٤) الإعدادات

def _settings():
    return {'daily_cap_usd': 10, 'daily_cap_max_usd': 20, 'absolute_max_usd': 50, 'kill': False, 'image_min_multiple': 3, 'video_min_multiple': 2.5, 'per_user_daily': 10, 'per_ip_daily': 30,
            'free_posts_daily': 1, 'sample_pct': 5, 'retry_limit': 3, 'topup_max_egp': 10000, 'next_line': '', 'blocked_terms_count': 4,
            'topup_min_by_currency': {'EGP': 100, 'SAR': 15, 'AED': 15, 'QAR': 15, 'KWD': 1, 'OMR': 1, 'USD': 3}, 'rates': dict(tfx.DEFAULT_RATES)}


@needs_node
def test_settings_inputs_are_arabic_and_an_untouched_form_has_nothing_to_save():
    cur = _settings()
    f = M('settingsInputs', cur)
    assert f['cap'] == '١٠' and f['capMax'] == '٢٠' and f['imgM'] == '٣' and f['vidM'] == '٢٫٥' and f['tmax'] == '١٠٠٠٠' and f['tmin']['KWD'] == '١' and f['rate']['OMR'] == '٠٫٣٨٥' and f['next'] == ''
    r = M('settingsCheck', f, cur)
    assert r['ok'] is False and r['nothing'] is True and r['changes'] == {} and r['error'] == 'لا يوجد تغيير للحفظ' and r['errors'] == {}
    assert M('settings', None) is None and M('settings', {}) is None


@needs_node
def test_settings_changes_carry_only_what_changed():
    cur = _settings()
    f = M('settingsInputs', cur)
    f.update(cap='١٥', perUser='8', next='الجاي: لينكدإن قوي')
    f['tmin']['EGP'] = '150'
    f['rate']['EGP'] = '51.5'
    r = M('settingsCheck', f, cur)
    assert r['ok'] is True and r['changes'] == {'daily_cap_usd': 15, 'per_user_daily': 8, 'next_line': 'الجاي: لينكدإن قوي', 'topup_min_by_currency': {'EGP': 150}, 'rates': {'EGP': 51.5}}
    lines = M('settingsDiff', r['changes'], cur)
    labels = [l['label'] for l in lines]
    assert 'السقف اليومي' in labels and 'حد المستخدم اليومي' in labels and 'أقل شحنة بـجنيه مصري' in labels and any(l['label'].startswith('سعر الصرف') for l in lines)
    cap = [l for l in lines if l['label'] == 'السقف اليومي'][0]
    assert cap['from'] == '١٠ دولارات' and cap['to'] == '١٥ دولارًا'
    hot = M('settingsHot', r['changes'])
    assert any('سقف الصرف' in h for h in hot) and any('حارس السعر' in h for h in hot)
    _clean_copy([lines, hot], 'settings-diff')


@needs_node
@pytest.mark.parametrize('over,key', [
    ({'cap': '25'}, 'cap'), ({'cap': '0'}, 'cap'), ({'cap': ''}, 'cap'), ({'cap': 'x'}, 'cap'), ({'cap': '١٠.٥٥٥'}, 'cap'),
    ({'capMax': '51'}, 'capMax'), ({'capMax': '0'}, 'capMax'), ({'capMax': ''}, 'capMax'),
    ({'imgM': '0.5'}, 'imgM'), ({'imgM': '21'}, 'imgM'), ({'vidM': ''}, 'vidM'),
    ({'perUser': '0'}, 'perUser'), ({'perUser': '201'}, 'perUser'), ({'perUser': '5.5'}, 'perUser'), ({'perIp': '1001'}, 'perIp'), ({'freePosts': '-1'}, 'freePosts'),
    ({'sample': '101'}, 'sample'), ({'retry': '11'}, 'retry'), ({'tmax': '99'}, 'tmax'), ({'tmax': '1000.5'}, 'tmax'), ({'next': 'ا' * 81}, 'next'),
])
def test_settings_validation_names_the_bad_field(over, key):
    cur = _settings()
    f = M('settingsInputs', cur)
    f.update(over)
    r = M('settingsCheck', f, cur)
    assert r['ok'] is False and key in r['errors'] and r['error'] == 'صحّح الخانات المعلَّمة', r['errors']


@needs_node
def test_settings_per_currency_fields_and_the_cap_against_the_new_maximum():
    cur = _settings()
    f = M('settingsInputs', cur)
    f['tmin']['SAR'] = '0'
    f['tmin']['KWD'] = '1.5'
    f['rate']['AED'] = '0'
    r = M('settingsCheck', f, cur)
    assert set(r['errors']) == {'tmin_SAR', 'tmin_KWD', 'rate_AED'}
    f = M('settingsInputs', cur)
    f.update(capMax='٣٠', cap='٢٥')
    ok = M('settingsCheck', f, cur)
    assert ok['ok'] is True and ok['changes'] == {'daily_cap_max_usd': 30, 'daily_cap_usd': 25}
    f.update(capMax='٣٠', cap='٣٥')
    assert 'cap' in M('settingsCheck', f, cur)['errors']
    f.update(capMax='٥٠', cap='٤٥')
    assert M('settingsCheck', f, cur)['ok'] is True
    assert 'cap' in M('settingsCheck', dict(f, capMax='٢٠', cap='٤٥'), cur)['errors']
    low = M('settingsCheck', dict(M('settingsInputs', cur), capMax='٨'), cur)                 # الحدّ الأقصى أقل من السقف الحالي ⇒ لازم يتخفّض السقف معه
    assert 'cap' in low['errors']


@needs_node
def test_settings_error_texts_use_arabic_digits():
    assert M('settingsError', 422, {'error': 'السقف اليومي لا يتجاوز 20 دولارًا'}) == 'السقف اليومي لا يتجاوز ٢٠ دولارًا'
    assert M('settingsError', 502, {'error': 'لم يصل رد.', 'no_reply': True}) == 'لم يصل رد.'


# ---------------------------------------------------------------- ٥) العيّنات

def _samples():
    import datetime
    two_h_ago = (datetime.datetime.fromtimestamp((NOW - 2 * H) / 1000.0, datetime.timezone.utc)).isoformat()
    return {'samples': [{'id': 'ou-a1b2c3d4', 'email': 'hala@example.test', 'recipe_id': 'headshot', 'style_id': 'hs_library', 'created_at': two_h_ago, 'preview': 'data:image/jpeg;base64,AAAA', 'sizes': ['4x5']},
                        {'id': 'ou-zz', 'email': 'x@example.test', 'recipe_id': 'gone', 'style_id': 'nope', 'created_at': 'bad', 'preview': '', 'sizes': []}], 'limit': 50}


@needs_node
def test_samples_rows_resolve_titles_and_a_missing_preview_is_honest():
    rec = M('recipes', _rec())
    d = M('samples', _samples(), rec['rows'], _json_styles(), NOW)
    assert d['count'] == 2 and d['capped'] is False and d['countText'] == 'عيّنتان تنتظران مراجعتك'
    r0, r1 = d['rows']
    assert (r0['recipe'], r0['style'], r0['hasPreview'], r0['who']) == ('صورتك المهنية', 'مكتبة', True, 'hala@example.test') and r0['when'].startswith('منذ')
    assert (r1['recipe'], r1['style'], r1['hasPreview'], r1['when']) == ('أداة محذوفة', '', False, '')
    assert M('samples', {'samples': []}, [], [], NOW)['countText'] == 'لا عيّنات تنتظر' and M('samples', None, [], [], NOW) is None
    big = {'samples': [{'id': 'ou-%06d' % i} for i in range(50)], 'limit': 50}
    cap = M('samples', big, [], [], NOW)
    assert cap['capped'] is True and cap['countText'] == '٥٠ عيّنة أو أكثر تنتظر مراجعتك'
    _clean_copy(d, 'samples')


@needs_node
def test_moderation_copy_each_action_says_what_it_does_including_the_refund():
    row = {'id': 'ou-a1b2c3d4', 'who': 'hala@example.test'}
    ok, hide, ban = M('moderateCopy', 'ok', row), M('moderateCopy', 'hide', row), M('moderateCopy', 'ban_user', row)
    assert ok['go'] == 'العمل سليم' and ok['danger'] is False and 'لا يتغيّر شيء' in ok['lead']
    assert hide['go'] == 'أخفِ العمل' and hide['danger'] is True and 'يُرَدّ المبلغ' in hide['lead'] and 'فلوسي' in hide['lead']
    assert ban['go'] == 'امنع صاحب العمل' and ban['danger'] is True and 'hala@example.test' in ban['lead'] and 'كل أعماله' in ban['lead']
    assert M('moderateDone', 'ok', {}) == 'عُلِّم العمل سليمًا'
    assert M('moderateDone', 'hide', {'refunded': 1}) == 'أُخفي العمل، ورُدّ مبلغ مهمة واحدة إلى «فلوسي»' and M('moderateDone', 'hide', {'refunded': 0}) == 'أُخفي العمل'
    assert 'مُنع' in M('moderateDone', 'ban_user', {'refunded': 3}) and '٣ مهام' in M('moderateDone', 'ban_user', {'refunded': 3})
    assert M('moderateError', 404, {}) == 'هذا العمل لم يعد في الطابور. حدّث الصفحة' and M('moderateError', 502, {'error': 'لم يصل رد.', 'no_reply': True}) == 'لم يصل رد.'
    _clean_copy([ok, hide, ban], 'moderation')


# ---------------------------------------------------------------- ٦) التقرير

def _report(**over):
    rows = tfx.seed_report_rows()
    d = {'recipes': rows, 'from': '2026-11-01', 'to': '2026-11-01', 'range': 'today', 'topups': None}
    d.update(over)
    return d


@needs_node
def test_report_totals_never_add_across_currencies_and_flag_the_guard():
    rows = tfx.seed_report_rows()
    rows[4].update(count=3, succeeded=3, cost_usd=1.8, avg_cost_usd=0.6, revenue_usd=3.0, revenue_by_currency={'SAR': 114}, margin_usd=1.2, guard_flag=True)
    d = M('report', _report(recipes=rows))
    t = d['totals']
    assert (t['count'], t['failures'], t['failHot']) == ('٤٦', '٢', True) and t['revenue'] == '٤٦٠ جنيه، ١٣٤ ريال سعودي' and t['cost'] == '٥٫٥٢ دولار'
    assert [r['id'] for r in d['guardRows']] == ['trend_video'] and d['rows'][4]['guard'] is True and d['rows'][0]['guard'] is False
    h = d['rows'][0]
    assert h['revenueText'] == '٤٦٠ جنيه، ٢٠ ريال سعودي ويعادل ١٤٫٩٢ دولار' and h['marginText'] == 'هامش ١١٫٢ دولار' and h['costText'] == '٣٫٧٢ دولار' and h['failText'] == '٢'
    assert d['rows'][2]['revenueText'] == 'لا إيراد' and d['rows'][2]['costText'] == 'بلا تكلفة' and d['rows'][2]['marginText'] == 'بلا هامش' and d['rows'][2]['active'] is False
    assert [r['id'] for r in d['activeRows']] == ['headshot', 'card', 'trend_video']
    _clean_copy(d, 'report')


@needs_node
def test_a_negative_margin_reads_as_a_shortfall():
    rows = tfx.seed_report_rows()
    rows[0].update(margin_usd=-2.5)
    d = M('report', _report(recipes=rows))
    assert d['rows'][0]['marginText'] == 'عجز ٢٫٥ دولار' and d['rows'][0]['marginNeg'] is True


@needs_node
def test_topups_are_separate_and_labelled_customer_balance_not_revenue():
    na = M('report', _report())
    assert na['topups'] == {'available': False, 'line': 'أرقام الشحن غير متاحة بعد من المنصة'}
    ok = M('report', _report(topups={'by_currency': {'EGP': 1500, 'SAR': 45}, 'count': 7}))
    assert ok['topups']['available'] is True and ok['topups']['line'] == 'شُحن ٧ مرات: ١٬٥٠٠ جنيه، ٤٥ ريال سعودي'
    none = M('report', _report(topups={'by_currency': {}, 'count': 0}))
    assert none['topups']['line'] == 'لا شحنات في هذه الفترة'
    note = M('TOPUP_NOTE')
    assert 'رصيد للعميل وليس إيرادًا' in note and 'فلا يدخل في الإيراد' in note
    assert ok['totals']['revenue'] == '٤٦٠ جنيه، ٢٠ ريال سعودي'          # الشحن لا يدخل الإيراد
    assert M('report', None) is None and M('report', {}) is None
    _clean_copy([ok, na, none, note], 'topups')


@needs_node
def test_report_period_text_and_query_and_the_custom_range_check():
    assert M('periodText', 'today', '2026-11-01', '2026-11-01') == 'تقرير يوم ١ نوفمبر ٢٠٢٦'
    assert M('periodText', 'week', '2026-10-26', '2026-11-01') == 'من ٢٦ أكتوبر ٢٠٢٦ إلى ١ نوفمبر ٢٠٢٦' and M('periodText', 'week', '', '') == ''
    assert M('reportQuery', 'today', '', '') == '/v2/tools/report?range=today' and M('reportQuery', 'week', '', '') == '/v2/tools/report?range=week'
    assert M('reportQuery', 'custom', '2026-10-01', '2026-10-15') == '/v2/tools/report?range=custom&from=2026-10-01&to=2026-10-15' and M('reportQuery', 'zzz', '', '') == '/v2/tools/report?range=today'
    assert M('rangeCheck', '2026-10-01', '2026-10-15')['ok'] is True
    for a, b, frag in (('', '', 'اختر تاريخ'), ('2026-10-15', '2026-10-01', 'بعد'), ('2025-01-01', '2026-11-01', 'سنة'), ('2026-1-1', '2026-1-2', 'اختر تاريخ')):
        r = M('rangeCheck', a, b)
        assert r['ok'] is False and frag in r['error'], (a, b)
    assert [M('RANGE_LABEL')[k] for k in ('today', 'week', 'custom')] == ['اليوم', 'آخر ٧ أيام', 'أخرى']


# ---------------------------------------------------------------- ٧) النصوص والملف

@needs_node
def test_the_visible_strings_in_the_file_have_no_forbidden_copy():
    js = _read('dashboard-cloud', 'v2s', 'tools.js')
    js = re.sub(r'/\*.*?\*/', '', js, flags=re.S)
    js = '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in js.split('\n'))
    strings = ' '.join(s for s in re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", js) if not re.search(r'[();=]|function', s))
    for need in ('أوقف الاستوديو الآن', 'أعد تشغيل الاستوديو', 'سليم', 'أخفِ العمل', 'امنع صاحبه', 'رصيد للعميل وليس إيرادًا', 'أخرى', 'احذف المكان'):
        assert need in strings, need
    assert js.count('راجع ثم احفظ') >= 2 and js.count('راجع ثم أضِف') == 1, 'مراجعة ثم تأكيد قبل كل كتابة'
    assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', strings)
    assert not re.search(r'[\d٠-٩]\s*·|·\s*[\d٠-٩]', strings)
    assert not re.search(r'(?<![A-Za-z])(API|JSON|endpoint|token|bridge|Claude|DeepSeek|OpenAI|Higgsfield|mock|live)(?![A-Za-z])', strings)


@needs_node
def test_pickers_with_free_choice_have_other_and_the_closed_ones_are_justified():
    js = _read('dashboard-cloud', 'v2s', 'tools.js')
    assert "['daily', 'مجانًا عددًا محددًا كل يوم']" in js, 'القاعدة المجانية: «عددًا محددًا» هي المدخل الحر الوحيد'
    assert M('RANGE_LABEL')['custom'] == 'أخرى', 'التقرير: فترة «أخرى» بتاريخين'
    assert [g[1] for g in M('GROUPS')][-1] == 'الفيديو والكروت'
    spec = _read('docs', 'v2', 'tools', 'SPEC.md')
    assert 'استثناءات «أخرى»' in spec


# ---------------------------------------------------------------- ٨) الخريطة

@needs_node
def test_the_tools_tab_lives_in_the_company_section_with_no_new_home_tile():
    secs = L('SECTIONS')
    co = [s for s in secs if s['key'] == 'company'][0]
    tab = [t for t in co['tabs'] if t['key'] == 'tools']
    assert len(tab) == 1 and tab[0]['label'] == 'الأدوات' and tab[0]['mod'] == 'v2s_tools' and not tab[0].get('hidden')
    assert [t['key'] for t in co['tabs'] if not t.get('hidden')] == ['invest', 'partners', 'assets', 'deals', 'ads', 'tools', 'settings']
    assert len(secs) == 13 and 'tools' not in [s['key'] for s in secs]
    where = L('sectionFor', 'v2s_tools', {}, None)
    assert where['section'] == 'company' and where['tab'] == 'tools'
    index = _read('dashboard-cloud', 'index.html')
    assert 'href="v2s/tools.css"' in index and 'src="v2s/tools.js"' in index
    assert "tools = { owns: T.owns, render: T.render }" in _read('dashboard-cloud', 'v2s', 'tools.js') or ').tools = { owns: T.owns, render: T.render }' in _read('dashboard-cloud', 'v2s', 'tools.js')
