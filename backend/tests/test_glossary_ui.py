# -*- coding: utf-8 -*-
"""واجهة تبويب «القاموس» (docs/v2/glossary/SPEC.md) — فحوص الملفات + المسار الكامل في متصفح حقيقي.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_glossary_ui.py

المسار الكامل بيشغّل `uiharness/v2_shots_glossary.py` (كمبيوتر ١٤٤٠ وموبايل ٤٣٠): المربّعات · القائمة والبحث والمجال · شاشة المصطلح · النشر المعطّل وسببه ·
«راجعه» ثم النشر · تعديل منشور مُراجَع (تحذير الختم والرجوع مسودة) · مصطلح جديد · نقاش الساحة · الحذف · الاستيراد (الأساسي · المرشّحة · ملف) · شرط المراجعة ·
المصدر الواقع والحالات الفاضية والجسر الغايب · المفتاح مقفول · الجولة الثانية: الوضع الافتراضي (نشر بلا ختم ⇒ «تحت التأكيد» ⇒ ختم بموافقة ظهور الاسم ⇒ تعديل يعيده
«تحت التأكيد») · صندوق «مراجعات القاموس» (اعتمد تأكيدًا · اقتراحًا يفتح المحرّر · تمّ لدورة · ارفض بملاحظة وبلا · تنبيه تغيّر المصطلح · حالات فاضية وواقعة).
الجولة الثالثة (قرار المؤسس ٢٠٢٦-١١-٠١): المراجعات مطفأة افتراضيًا (مسودة / منشور فقط والختم داخلي) · «افتح نقاشًا لهذا المصطلح» (معاينة بلا كتابة ⇒ تأكيد) ·
«نقاشات المصطلحات» دفعةً (تجربة ⇒ تأكيد ⇒ نتيجة لكل مصطلح)؛ والخطوات ٠١ إلى ١٥ بالإعداد مفعّلًا (شكل الجولة ٢ كما كان).
⛔ صفر شبكة: الداشبورد وقاعدته جوه العملية والمنصة بديل في الذاكرة. لو playwright أو المتصفح غير متاحين ⇒ يُتخطّى (فحوص الملفات بتشتغل دايمًا).
"""
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
SCRIPT = os.path.join(_HERE, 'uiharness', 'v2_shots_glossary.py')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def _js():
    return _strip(_read('dashboard-cloud', 'v2s', 'saha_glossary.js'))


def test_the_tab_the_module_and_the_registry_lines_are_wired_inside_the_content_section():
    logic = _read('dashboard-cloud', 'v2-logic.js')
    assert "T('glossary',  'القاموس',         'v2s_glossary')" in logic
    sec = logic[logic.index("{ key: 'content', label: 'المحتوى', img: 'content', desc:"):]
    sec = sec[:sec.index("{ key: 'marketing'")]
    assert "'v2s_glossary'" in sec and sec.index("'v2s_diwan'") < sec.index("'v2s_glossary'") < sec.index("topicsTab: 'tutorials'"), 'القاموس بعد الديوان داخل المحتوى'
    assert 'والقاموس' in sec.split('tabs: [')[0], 'وصف القسم يذكر القاموس'
    assert len(re.findall(r"\{ key: '[a-z]+', label: '", logic[logic.index('var SECTIONS = ['):logic.index('var ALIASES')])) == 13, 'القائمة الرئيسية ١٣ بند'
    g = _read('dashboard-cloud', 'v2s', 'saha_glossary.js')
    assert "key: 'glossary', mod: 'v2s_glossary'" in g and "window.V2S_GLOSSARY = B;" in g
    assert "if (typeof window === 'undefined' || typeof document === 'undefined') return;" in g, 'الواجهة تتخطّى node'
    html = _read('dashboard-cloud', 'index.html')
    block = re.search(r'<!-- v2 sections.*?<!-- v2 sections end -->', html, re.S).group(0)
    assert '<link rel="stylesheet" href="v2s/glossary.css">' in block and block.count('<script src="v2s/glossary.js"></script>') == 1 and block.count('<script src="v2s/saha_glossary.js"></script>') == 1
    assert block.index('v2s/saha.js') < block.index('v2s/saha_diwan.js') < block.index('v2s/saha_glossary.js') < block.index('v2s/trainer_share.js'), 'واجهة القاموس تُحمَّل بعد محرّك الساحة'
    assert block.index('v2s/glossary.css') < block.index('v2s/glossary.js') < block.index('v2s/home.css'), 'المنطق والأنماط في مكانهما الأبجدي'
    assert html.index('v2-logic.js') < html.index('v2s/glossary.js') < html.index('v2s/saha_glossary.js'), 'المنطق يتحمّل قبل الواجهة'
    assert 'module.exports' in _read('dashboard-cloud', 'v2s', 'glossary.js') and 'V2S_SAHA_KIT' not in _read('dashboard-cloud', 'v2s', 'glossary.js'), 'المنطق نقي'
    assert 'v2s_glossary' not in _read('dashboard-cloud', 'dashboard-api.js')
    assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in _read('Dockerfile'), 'الملفان يُشحنان مع المجلد كله'


def test_every_mutation_goes_through_the_review_sheet_with_the_exact_flag_and_the_preview_is_the_only_unconfirmed_call():
    code = _js()
    api_calls = [ln.strip() for ln in code.split('\n') if 'B.api(' in ln and 'B.api = ' not in ln]
    assert len(api_calls) >= 14, len(api_calls)
    previews = [ln for ln in api_calls if "/preview'" in ln]
    assert len(previews) == 3 and all('confirmed' not in ln for ln in previews), previews          # التجارب الثلاث (استيراد · نقاش مصطلح · دفعة) لا تكتب
    for ln in api_calls:
        assert 'confirmed: true' in ln or "/preview'" in ln, ln                # كل نداء كتابة فيه confirmed، والتجارب وحدها بلا (لا تكتب)
    assert code.count('B.flow(') >= 10 and code.count('send: function') >= 10, 'كل ورقة كتابة لها `send` واحد يمرّ على التأكيد'
    vals = re.findall(r"confirmed\s*[:=]\s*(\S+)", code)
    assert vals and all(v.startswith('true') for v in vals), vals
    assert not re.search(r"\bby\s*:", code) and "'by'" not in code, 'الهوية من التوكن عند الخادم وحده'
    assert 'ep-b1' in code and 'ep-b2' in code and 'ep-bs' in code and not re.search(r'class="(btn|v3-btn1|v3-btn2|v2d-btn1|m4-)', code)
    assert not re.search(r'\b(confirm|alert|prompt)\(', code) and 'localStorage' not in code and 'sessionStorage' not in code and 'indexedDB' not in code
    assert not re.search(r'\bfetch\(|XMLHttpRequest|sendBeacon|WebSocket', code), 'كل النداءات عبر B.api'
    assert not re.search(r"https?://(api|dashboard)\.elprofessor\.net", code), 'لا عنوان حقيقي للخادم في الواجهة'
    assert not re.search(r"https?://", code), 'الروابط العامة في المنطق وحده'
    logic = _strip(_read('dashboard-cloud', 'v2s', 'glossary.js'))
    assert set(re.findall(r"https?://[^\s'\"<>)]+", logic)) == {'https://elprofessor.net/glossary/', 'https://app.elprofessor.net/?page=saha&topic='}, 'روابط عامة فقط (معاينة ونقاش)'
    assert not re.search(r'\bfetch\(|XMLHttpRequest|sendBeacon|WebSocket|document\.|window\.', logic), 'المنطق نقي'


def test_the_screens_only_call_the_glossary_admin_routes():
    js = _js()
    assert set(re.findall(r"'(/v2/[^']*)'", js)) == {'/v2/content/glossary'}, 'مسار الجذر وحده حرفيًّا، والباقي لواحق منه'
    assert "'/saha-topic/preview'" in js and "'/saha-topic/open'" in js and "'/saha-topics/bulk/preview'" in js and "'/saha-topics/bulk/open'" in js
    assert "'/seed/preview'" in js and "'/seed/import'" in js and "'/attach-topic'" in js and "'/detach-topic'" in js and "'/review'" in js and "'/unreview'" in js
    assert "'/publish'" in js and "'/unpublish'" in js and "'DELETE'" in js and "'PUT'" in js


def test_visitor_names_are_isolated_with_bdi_wherever_the_screens_print_them():
    js = _js()
    assert "var bdi = function (v) { return '<bdi>' + Kit.esc(v) + '</bdi>'; }" in js
    for printed in ("bdi(r.reviewerName)", "bdi(r.reviewerRole)", "bdi(sg.name)", "bdi(sg.specialtyText)", "bdi(r.name)", "bdi(r.specialtyText)", "bdi(rv.name)", "bdi(rv.specialtyText)"):
        assert printed in js, printed
    assert "esc(r.reviewerName" not in js and "esc(sg.name)" not in js and "esc(rv.name)" not in js and "esc(r.name +" not in js, 'اسم زائر مطبوع بلا عزل اتجاهه'


def test_round_two_the_reviews_box_the_three_states_and_the_name_consent_are_wired():
    js, logic = _js(), _read('dashboard-cloud', 'v2s', 'glossary.js')
    assert "'/approve'" in js and "'/reject'" in js and "reviews: BASE + '/reviews?status=all&limit=500'" in js
    assert "sub: 'reviews', name: 'مراجعات القاموس'" in js and "screens: { terms: screenList('all'), wait: screenList('wait'), term: screenTerm, topics: screenTopics, reviews: screenReviews, review: screenReview" in js
    assert "Kit.chk('reviewer_name_public'" in js and 'وافق المراجع على ظهور اسمه' in js, 'خانة موافقة المراجع على ظهور اسمه'
    assert 'اعتمد وافتح المحرّر' in logic and "'تمّ'" in logic and 'ارفض المراجعة' in logic and 'تغيّر نص المصطلح بعد وصول هذه المراجعة' in logic
    assert "['under_review', 'تحت التأكيد']" in logic and "['confirmed', 'مؤكّد']" in logic and 'سيرجع المصطلح إلى «تحت التأكيد» ويبقى ظاهرًا' in logic
    assert 'requireReview: on && resp.require_review === true' in logic and 'resp.reviews_enabled === true' in logic, 'الشرط ومراجعات المتخصصين مغلقان افتراضيًا'
    assert 'localStorage' not in js and 'require_review: false' not in js, 'لا إعداد بالجسم من الواجهة خارج ورقة التأكيد'
    nv = _read('dashboard-cloud', 'v2-logic.js')
    assert "glossary_review: { section: 'content', tab: 'glossary' }" in nv and "glossary_review: 'مراجعات القاموس تنتظر قرارك'" in nv, 'صفّ الجرس يفتح تبويب القاموس'
    css = _read('dashboard-cloud', 'v2s', 'glossary.css')
    assert '.g-sugbox' in css and '.g-sug' in css and '.g-rules' in css


def test_round_three_reviews_are_switched_off_by_default_and_the_boxes_are_gated():
    js, logic = _js(), _strip(_read('dashboard-cloud', 'v2s', 'glossary.js'))
    assert "var on = reviewsOn();" in js and "if (on) {" in js and "list.push(Object.assign({ sub: 'import'" in js, 'مربّعات المراجعات والانتظار والشرط تُضاف حين تُفعَّل المراجعات فقط'
    assert js.count('offScreen(') >= 4 and "B.empty('غير مفعّلة الآن'" in js, 'الشاشات الثلاث مغلقة بحالة صريحة لو وصلها أحد'
    assert 'مراجعة داخلية، لا تظهر على الموقع' in js, 'ختم «راجعه» الداخلي موسوم'
    assert "'منشور'" in logic and "'مسودة'" in logic and 'STATUS_CHIPS_OFF' in logic and 'reviewsOn: on' in logic
    assert "(on ? '<div class=\"fld\">' + Kit.chk('reviewer_name_public'" in js, 'خانة موافقة الاسم لا تظهر والمراجعات مطفأة'
    srv = _read('backend', 'v2_glossary_routes.py')
    assert "EXPERT_KEY = 'glossary.expert_reviews_enabled'" in srv and 'def reviews_enabled(Setting)' in srv
    app = _read('backend', 'app.py')
    assert "'glossary.expert_reviews_enabled' in d" in app and '_v2s_glossary.reviews_enabled(Setting)' in app, 'الإعداد محجوب من الإعدادات العامة وصفّ الجرس مشروط'


def test_round_three_the_topic_screens_are_wired_with_a_dry_run_before_every_write():
    js, logic = _js(), _strip(_read('dashboard-cloud', 'v2s', 'glossary.js'))
    assert "افتح نقاشًا لهذا المصطلح" in js and 'data-a="gtopen"' in js and 'أو اربط نقاشًا موجودًا في الساحة' in js, 'افتح جديدًا أولًا والربط بموجود ثانويًّا'
    assert "sub: 'topics', name: 'نقاشات المصطلحات'" in js and 'جرّب فتح النقاشات (بلا فتح)' in js and "data-a=\"gbgo\"" in js
    assert 'check: function (vals) {' in js and "B.api(path(r, '/saha-topic/preview'), f.body).then(" in js, 'ورقة المراجعة تأتي من معاينة الخادم لا من افتراض'
    assert "res.body" in js and "no_reply: true" in js, 'الورقة تعرض ما تمّ قبل التوقف'
    saha = _strip(_read('dashboard-cloud', 'v2s', 'saha.js'))
    assert "typeof r.then === 'function'" in saha and "s.dataset.checking" in saha, 'محرّك الأوراق يقبل معاينة غير متزامنة'
    for need in ('topicDefaults', 'topicFormCheck', 'topicOpenCheck', 'bulkView', 'bulkCheck', 'bulkStopText', 'canOpenTopic'):
        assert need + ': ' + need in logic, need
    css = _read('dashboard-cloud', 'v2s', 'glossary.css')
    assert '.g-tl' in css


def test_the_markup_text_has_no_forbidden_visible_copy_and_every_picker_has_other():
    js = _js()
    strings = ' '.join(re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", js))
    for need in ('أخرى', 'راجعه', 'ألغِ النشر', 'انشر المصطلح', 'أعد المحاولة'.replace('أعد المحاولة', 'غير متاح بعد'), 'جرّب الاستيراد (بلا حفظ)', 'اختر ملفًا', 'افصل النقاش', 'اربط النقاش', 'أضف مصطلحًا',
                 'ابحث في المصطلحات', 'اختر المجال', 'المصطلحات القريبة', 'الخطأ الشائع', 'يُنشر بعد أن يراجعه خبير'.replace('يُنشر بعد أن يراجعه خبير', 'ملاحظة الدول')):
        assert need in strings or need in _read('dashboard-cloud', 'v2s', 'glossary.js'), need
    assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', strings)
    assert not re.search(r'[\d٠-٩]\s*·|·\s*[\d٠-٩]', strings)
    assert '→ ' in js and "'← " not in js, 'زرّ الرجوع بسهم الرجوع في الاتجاه العربي'
    assert "sel('area', vals.area, G.AREAS, create ? 'اختر المجال' : null)" in js and "[OTHER, 'أخرى']" in _read('dashboard-cloud', 'v2s', 'glossary.js'), 'المجال فيه «أخرى»'
    assert 'type="file"' in js and 'class="ep-bs sh-filebtn"' in js and 'sh-fileinp' in js, 'زرّ ملفات محلي لا الأصلي'
    heads = re.findall(r'<h[1-4][^>]*>([^<]+)<', js) + re.findall(r"title: '([^']+)'", js)
    assert heads and not any(h.strip().startswith('الذكاء') for h in heads), heads


def test_the_css_is_scoped_has_no_yellow_and_keeps_the_touch_sizes():
    css = _strip(_read('dashboard-cloud', 'v2s', 'glossary.css'))
    css_nm = re.sub(r'@media[^{]*\{', '', css)
    bad = []
    for sel in re.findall(r'([^{}]+)\{', css_nm):
        for part in sel.split(','):
            part = part.strip()
            if part and not re.match(r'^(\.v2s-sh|#epModal\.v2s-sh-sh)', part):
                bad.append(part)
    assert not bad, bad[:5]
    for hexc in re.findall(r'#([0-9A-Fa-f]{6})\b', css):
        r, g, b = int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16)
        assert not (r > 190 and g > 150 and b < 140 and abs(r - g) < 90), 'لون أصفر: #' + hexc
    assert 'min-height:44px' in css and 'width:44px;height:44px' in css and '@media (max-width:760px)' in css


def test_full_flow_in_a_real_browser(tmp_path):
    try:
        import playwright  # noqa: F401
    except Exception:   # noqa: BLE001
        pytest.skip('playwright غير متاح')
    out = tmp_path / 'shots'
    p = subprocess.run([sys.executable, '-B', SCRIPT, str(out)], capture_output=True, text=True, timeout=2400, cwd=os.path.dirname(_HERE))
    blob = p.stdout + p.stderr
    if 'Executable doesn\'t exist' in blob or 'BrowserType.launch' in blob:
        pytest.skip('المتصفح غير متاح لـplaywright')
    assert '"problems"' in p.stdout, blob[-2000:]
    rep = json.loads(p.stdout[p.stdout.index('{\n'):])
    assert rep['problems'] == [], rep['problems']
    assert rep['unexpected'] == [] and rep['blocked_inproc'] == []
    assert p.returncode == 0, blob[-1500:]
    assert len(rep['shots']) >= 60
