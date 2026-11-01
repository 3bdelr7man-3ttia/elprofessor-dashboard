# -*- coding: utf-8 -*-
"""«القاموس»: القالبان + المولّد (prerender.py) + الدفع والمسح في app.py (docs/v2/glossary/SPEC.md §٦).

Run:  cd backend && EP_SITE_REPO=~/elprofessor-site/.worktrees/glossary python3 -B -m pytest tests/test_glossary_prerender.py -q -p no:cacheprovider

⛔ صفر شبكة حقيقية: الفيدات ملفات محلية، وجلب القوالب `requests.get` مبدَّل، وSFTP بديل في الذاكرة. القالبان الحقيقيان يُقرآن من
ريبو الموقع (EP_SITE_REPO، الفرع site-glossary)؛ بدونهما تُتخطّى الاختبارات بسبب واضح.

اللي بيثبّته:
  ١. verify_glossary_term / verify_glossary_index: الصفحة السليمة (بمراجِع ونقاش وبدونهما) تمرّ، وكل عيب على حدة يفشل.
  ٢. prerender طرفي بسطر الأوامر على فيد محلي: مصطلح بمراجِع ونقاش وملاحظة بلاد · مصطلح بلا شيء · قريب غير منشور · أرقام لاتينية في
     example_ar ⇒ هندية · قالب غائب ⇒ تخطٍّ · عيب ⇒ لا تُكتب أي صفحة قاموس والمقالات تُكتب · المقالات حرفيًّا نفسها بالقاموس وبدونه.
  ٣. الدفع والمسح (app.py) مع SFTP بديل: يرفع صفحات القاموس، يمسح اليتيمة بنمط الـslug فقط، لا يمسح بعد جلب/تحقق فاشل أو قالب غائب.
  ٤. الجولة ٣ (قرار المؤسس 2026-11-01: «احنا نحط المصطلح ونفتحه للنقاش»): لا شارة «تحت التأكيد» ولا «راجعه» ولا نموذج مراجعة ولا نقطة إرسال ولا علامة
     حالة في الفهرس ولا أزرار تصفية بالحالة؛ مفاتيح المراجعة في الفيد اختيارية وتُتجاهل، وملاحظة البلاد تظهر متى وُجدت؛ كل غياب ومعه عيب يُسقطه،
     وطرفي بسطر الأوامر: مصطلح بنقاش · بلا نقاش · فيد بشكل «الجولة ٢» (مفاتيح المراجعة موجودة) لا يغيّر الصفحة.
"""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types

import pytest

import app as appmod  # noqa: E402
from app import app as flask_app, db, Article  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(_HERE)
# بلا EP_SITE_REPO: يُفضَّل ريبو الموقع المجاور لهذا الفرع (القالبان فيه فقط)، وإلا ~/elprofessor-site.
_SIBLING_SITE = os.path.expanduser('~/elprofessor-site/.worktrees/glossary')
_DEFAULT_SITE = _SIBLING_SITE if os.path.isfile(os.path.join(_SIBLING_SITE, 'glossary-term.html')) else '~/elprofessor-site'
SITE_DIR = os.path.expanduser(os.environ.get('EP_SITE_REPO', _DEFAULT_SITE))
PRERENDER = os.path.join(BACKEND, 'prerender.py')
sys.path.insert(0, BACKEND)
import prerender as pr  # noqa: E402

HAS_NODE = bool(shutil.which('node'))
HAS_TPL = all(os.path.isfile(os.path.join(SITE_DIR, n)) for n in ('glossary-term.html', 'glossary.html', 'article.html', 'blog.html'))
def test_the_glossary_templates_were_found_so_the_site_tests_do_not_skip_silently():
    """⛔ بدون القالبين تُتخطّى ٩٩ اختبارًا بصمت. على جهاز فيه node يجب أن يُعثر عليهما، وإلا فالتشغيل:
    EP_SITE_REPO=~/elprofessor-site/.worktrees/glossary. (CI_ALLOW_SKIP=1 يسمح بالتخطّي صراحةً.)"""
    if os.environ.get('CI_ALLOW_SKIP') == '1' or not HAS_NODE:
        pytest.skip('node missing or skipping explicitly allowed')
    assert HAS_TPL, 'glossary-term.html / glossary.html not found under %s: set EP_SITE_REPO to the site-glossary checkout' % SITE_DIR


needs_site = pytest.mark.skipif(not (HAS_NODE and HAS_TPL), reason='needs node + the site checkout on site-glossary (EP_SITE_REPO)')

TID = 'c0ffee00-1111-4222-8333-444455556666'
AREAS = [{'code': c, 'label': l} for c, l in (
    ('contracts', 'عقود'), ('litigation', 'تقاضٍ'), ('corporate', 'شركات'), ('general', 'عام'), ('arbitration', 'تحكيم'),
    ('criminal', 'جنائي'), ('ip', 'ملكية فكرية'), ('labor', 'عمل'), ('family', 'أسرة'), ('other', 'أخرى'))]
LONG = ('هذا نص تجريبي طويل يشرح المبدأ القانوني بالتفصيل ويعطي القارئ خطوات عملية واضحة. ' * 12).strip()


def term(slug, **kw):
    """مصطلح بشكل الفيد في الوضع المغلق (glossary.expert_reviews_enabled = off): بلا أي مفتاح مراجعة."""
    t = {'id': 1, 'slug': slug, 'ar': 'المقابل (العوض)', 'en': 'consideration', 'fr': 'contrepartie', 'area': 'contracts',
         'area_label': 'عقود', 'definition_ar': 'شيء ذو قيمة يقدّمه كل طرف للآخر ليصبح الوعد ملزمًا.',
         'example_en': 'The fee is USD 50,000.', 'example_ar': 'الرسم 50,000 دولار بنسبة 0.5% سنويًا.',
         'false_friend_note_ar': 'لا تترجمها «الاعتبار».', 'countries_note_ar': None, 'related': [], 'saha_topic_id': None,
         'published_at': '2026-11-01T10:05:00', 'updated_at': '2026-11-01T10:05:00'}
    t.update(kw)
    return t


def feed_of(*terms, areas=AREAS):
    return {'source': 'dashboard', 'areas': areas, 'terms': list(terms)}


# مصطلح بنقاش وملاحظة بلاد وقريب منشور وآخر غير منشور
FULL = term('consideration', saha_topic_id=TID, countries_note_ar='يُقال «العوض» في مصر و«المقابل» في الأردن.',
            related=[{'slug': 'offer', 'ar': 'الإيجاب', 'en': 'offer'}, {'slug': 'ghost', 'ar': 'شبح', 'en': 'ghost'}])
# مصطلح بلا نقاش ولا فرنسي ولا مثال
PLAIN = term('offer', ar='الإيجاب', en='offer', fr=None, example_en=None, example_ar=None, false_friend_note_ar=None,
             area='litigation', area_label='تقاضٍ', related=[{'slug': 'consideration', 'ar': 'المقابل', 'en': 'consideration'}],
             countries_note_ar=None)
# ملاحظة بلاد بلا نقاش (معرّف نقاش غير صالح لا يُرسم رابطًا)
NOTE_ONLY = term('estoppel', ar='الدفع بالتناقض', en='estoppel', countries_note_ar='ملاحظة بلاد تظهر لأن المصطلح مفتوح للنقاش.',
                 saha_topic_id='bad id!')
WAIVER = term('waiver', ar='التنازل', en='waiver', fr=None, countries_note_ar='يُسمّى «الإسقاط» في بعض البلاد.',
              example_ar=None, example_en=None, false_friend_note_ar=None)
# فيد بشكل الجولة ٢ (الإعداد مفتوح): مفاتيح المراجعة موجودة بقيم مؤكَّدة ومعها اسم وصفة. يجب أن تُتجاهل كليًّا فلا تظهر على الصفحة.
ON_SHAPE = term('laches', ar='التقادم المانع', en='laches', review_state='confirmed', reviewed_by_name='أ. اسم مسرّب', reviewed_by_role='صفة مسرّبة',
                reviewed_at='2026-11-01T10:00:00', countries_note_ar='ملاحظة بلاد تظهر.')


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _gfile(tmp, feed, name='gfeed.json'):
    p = os.path.join(tmp, name)
    _write(p, json.dumps(feed, ensure_ascii=False))
    return p


def _block(html):
    return html.split(pr.GL_OPEN, 1)[1].split(pr.GL_CLOSE, 1)[0]


# ——————————————————————————————————————————————— الأرقام (النسختان)

def test_arabic_indic_digits_python_mirror():
    assert pr.glossary_ar('50,000') == '٥٠٬٠٠٠'
    assert pr.glossary_ar('0.5%') == '٠٫٥٪'
    assert pr.glossary_ar('1,234.56 دولار') == '١٬٢٣٤٫٥٦ دولار'
    assert pr.glossary_ar('المادة 12') == 'المادة ١٢'
    assert pr.glossary_ar('a, b. c') == 'a, b. c'
    assert pr.glossary_ar(None) == ''


# ——————————————————————————————————————————————— فحص الفيد

def _feed_err(tmp_path, feed):
    p = tmp_path / 'f.json'
    p.write_text(json.dumps(feed, ensure_ascii=False), encoding='utf-8')
    with pytest.raises(pr.Fail) as e:
        pr.fetch_glossary_feed(str(p))
    return str(e.value)


def test_feed_accepts_a_good_feed_and_an_empty_one(tmp_path):
    p = tmp_path / 'f.json'
    p.write_text(json.dumps(feed_of(FULL, PLAIN), ensure_ascii=False), encoding='utf-8')
    terms, areas = pr.fetch_glossary_feed(str(p))
    assert [t['slug'] for t in terms] == ['consideration', 'offer'] and len(areas) == 10
    p.write_text(json.dumps(feed_of()), encoding='utf-8')
    assert pr.fetch_glossary_feed(str(p))[0] == []


def test_feed_rejects_bad_shapes_slugs_and_the_reserved_index_name(tmp_path):
    assert 'no terms[]' in _feed_err(tmp_path, {'articles': []})
    assert 'reserved' in _feed_err(tmp_path, feed_of(term('index')))
    assert 'invalid slug' in _feed_err(tmp_path, feed_of(term('Bad_Slug')))
    assert 'invalid slug' in _feed_err(tmp_path, feed_of(term('عقد')))
    assert 'invalid slug' in _feed_err(tmp_path, feed_of(term('ends-with-dash-')))
    assert 'duplicate' in _feed_err(tmp_path, feed_of(PLAIN, copy.deepcopy(PLAIN)))
    assert 'no definition_ar' in _feed_err(tmp_path, feed_of(term('x1', definition_ar='  ')))
    assert 'not text' in _feed_err(tmp_path, feed_of(term('x2', fr=5)))
    assert 'malformed related' in _feed_err(tmp_path, feed_of(term('x3', related=['nope'])))


def test_feed_ignores_the_review_keys_whatever_they_hold(tmp_path):
    """review_state وreviewed_by_* وreviewed_at اختيارية وتُتجاهل: غيابها أو قيمتها الغريبة ليست عيبًا (الإعداد قد يُفتح ويُغلق)."""
    p = tmp_path / 'ok.json'
    odd = [term('a1'), term('a2', review_state='confirmed', reviewed_by_name='س', reviewed_by_role='ص', reviewed_at='2026-11-01T10:00:00'),
           term('a3', review_state='draft'), term('a4', review_state=None), term('a5', review_state=5, reviewed_at=7, reviewed_by_name=3)]
    p.write_text(json.dumps(feed_of(*odd)), encoding='utf-8')
    assert [t['slug'] for t in pr.fetch_glossary_feed(str(p))[0]] == ['a1', 'a2', 'a3', 'a4', 'a5']


def test_feed_url_mode_is_not_used_by_a_file_run(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError('network touched')
    monkeypatch.setattr(pr.urllib.request, 'urlopen', boom)
    p = tmp_path / 'f.json'
    p.write_text(json.dumps(feed_of(PLAIN)), encoding='utf-8')
    assert pr.fetch_glossary_feed(str(p))[0][0]['slug'] == 'offer'


# ——————————————————————————————————————————————— ١) التحقق

@pytest.fixture(scope='module')
def built(tmp_path_factory):
    if not (HAS_NODE and HAS_TPL):
        pytest.skip('needs node + site checkout')
    tmp = str(tmp_path_factory.mktemp('gl'))
    terms = [FULL, PLAIN, NOTE_ONLY, WAIVER, ON_SHAPE]
    gf = _gfile(tmp, feed_of(*terms))
    summary, pages = pr.glossary_step(SITE_DIR, gf)
    assert summary['state'] == 'ok' and summary['terms'] == 5
    by = {os.path.basename(p)[:-5]: h for p, h in pages.items()}
    return {'terms': {t['slug']: t for t in terms}, 'pages': by, 'slugs': {t['slug'] for t in terms},
            'term_tpl': _read(os.path.join(SITE_DIR, 'glossary-term.html')), 'index_tpl': _read(os.path.join(SITE_DIR, 'glossary.html')),
            'list': terms}


def _verify(b, slug, html=None):
    return pr.verify_glossary_term(html if html is not None else b['pages'][slug], b['terms'][slug], None, b['term_tpl'], b['slugs'])


@needs_site
def test_good_pages_verify_with_and_without_a_topic_and_with_an_on_shape_feed(built):
    for slug in ('consideration', 'offer', 'estoppel', 'waiver', 'laches'):
        assert _verify(built, slug) == [], slug
    assert pr.verify_glossary_index(built['pages']['index'], built['list'], None, built['index_tpl']) == []


@needs_site
def test_topic_link_and_country_note_appear_only_when_they_should(built):
    full, plain, note, waiver, on = (_block(built['pages'][s_]) for s_ in ('consideration', 'offer', 'estoppel', 'waiver', 'laches'))
    assert full.count(pr.SAHA_LINK_PREFIX + TID + '"') == 1 and full.count('ناقشه في الساحة') == 1
    for b in (plain, note, waiver, on):                                                  # بلا معرّف نقاش صالح ⇒ لا رابط ولا نص
        assert pr.SAHA_LINK_PREFIX not in b and 'ناقشه في الساحة' not in b
    # ملاحظة البلاد تظهر متى وُجدت بلا شرط حالة
    assert full.count('class="gl-country"') == 1 and 'في البلاد العربية' in full
    assert 'ملاحظة بلاد تظهر لأن المصطلح مفتوح للنقاش.' in note and 'يُسمّى «الإسقاط» في بعض البلاد.' in waiver and 'ملاحظة بلاد تظهر.' in on
    assert 'class="gl-country"' not in plain
    assert 'lang="fr"' in full and 'lang="fr"' not in plain          # الفرنسي يُحذف حين يغيب
    assert full.count('https://app.elprofessor.net/?page=chat"') == 1 and full.count('اسأل خبيرًا') == 1


@needs_site
def test_related_links_only_to_generated_pages_and_unpublished_is_omitted(built):
    full = _block(built['pages']['consideration'])
    assert re.findall(r'href="/glossary/([^"/]+)\.html"', full) == ['offer']         # «ghost» غير منشور ⇒ لا رابط ولا نص
    assert '/glossary/ghost' not in full and 'شبح' not in full
    assert re.findall(r'href="/glossary/([^"/]+)\.html"', _block(built['pages']['offer'])) == ['consideration']


@needs_site
def test_latin_digits_in_arabic_text_become_arabic_indic_but_english_keeps_latin(built):
    b = _block(built['pages']['consideration'])
    assert '«الرسم ٥٠٬٠٠٠ دولار بنسبة ٠٫٥٪ سنويًا.»' in b
    assert '“The fee is USD 50,000.”' in b                                           # الإنجليزي لاتيني
    assert TID in built['pages']['consideration'] and 'c0ffee00-1111' in built['pages']['consideration']   # المعرّف لا يمرّ بالتحويل


@needs_site
def test_seo_basics_title_description_canonical_og_and_jsonld(built):
    h = built['pages']['consideration']
    assert re.search(r'<title>المقابل \(العوض\) — consideration \| القاموس القانوني \| البروفيسور</title>', h)
    assert h.count('<link rel="canonical" href="https://elprofessor.net/glossary/consideration.html">') == 1
    assert '<meta property="og:url" content="https://elprofessor.net/glossary/consideration.html">' in h
    m = re.search(r'<meta name="description" content="([^"]*)">', h)
    assert m and len(m.group(1)) <= 160 and 'شيء ذو قيمة' in m.group(1)
    lds = [json.loads(x) for x in re.findall(r'(?s)<script type="application/ld\+json"[^>]*>(.*?)</script>', h)]
    terms = [n for n in pr._ld_nodes(lds) if n.get('@type') == 'DefinedTerm']
    assert len(terms) == 1 and terms[0]['name'] == 'المقابل (العوض)' and terms[0]['alternateName'] == ['consideration', 'contrepartie']
    assert terms[0]['inDefinedTermSet']['url'] == 'https://elprofessor.net/glossary/'
    idx = built['pages']['index']
    assert idx.count('<link rel="canonical" href="https://elprofessor.net/glossary/">') == 1
    sets = [n for n in pr._ld_nodes([json.loads(x) for x in re.findall(r'(?s)<script type="application/ld\+json"[^>]*>(.*?)</script>', idx)])
            if n.get('@type') == 'DefinedTermSet']
    assert len(sets) == 1 and len(sets[0]['hasDefinedTerm']) == 5
    assert 'EP_PRERENDERED=true' in h and 'EP_GLOSSARY_SLUG="consideration"' in h


@needs_site
def test_index_groups_by_area_links_every_term_once_and_has_no_search_box(built):
    idx = _block(built['pages']['index'])
    assert sorted(re.findall(r'href="/glossary/([^"/]+)\.html"', idx)) == ['consideration', 'estoppel', 'laches', 'offer', 'waiver']
    assert 'id="area-contracts"' in idx and 'id="area-litigation"' in idx and 'id="area-labor"' not in idx
    assert '<input' not in idx and '<form' not in idx and idx.count('اسأل خبيرًا') == 1


@needs_site
@pytest.mark.parametrize('word', ['تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح', 'راجعه: فلان', 'راجعه متخصص', 'مؤكّد', 'مؤكد', 'مؤكـــد', 'بانتظار تأكيد المحكّمين', 'نبحث عن صياغة أفضل', 'أنت متخصص؟ راجِع هذا المصطلح'])
def test_state_words_inside_the_free_text_do_not_fail_the_glossary(tmp_path, word):
    """تعريف أو مثال أو ملاحظة يحوي عبارة من عبارات المراجعة المحذوفة لا يُسقط الصفحة: الفحص على ما يضيفه القالب لا على نصّ الفيد."""
    tricky = term('tricky', definition_ar='تعريف يذكر عبارة «%s» في سياق الشرح.' % word, example_ar='مثال: %s.' % word,
                  false_friend_note_ar='خطأ في نقل «%s».' % word, countries_note_ar='ملاحظة بلاد فيها %s.' % word)
    summary, pages = pr.glossary_step(SITE_DIR, _gfile(str(tmp_path), feed_of(tricky)))
    assert summary['state'] == 'ok', summary
    html = next(h for pth, h in pages.items() if pth.endswith('tricky.html'))
    assert word in _block(html)
    assert pr.verify_glossary_term(html, tricky, None, _read(os.path.join(SITE_DIR, 'glossary-term.html')), {'tricky'}) == []


@needs_site
def test_markup_typed_inside_the_free_text_is_escaped_and_does_not_fail_the_glossary(tmp_path):
    """نصٌّ حرٌّ فيه وسوم إدخال أو زر يُكتب نصًّا مُهرَّبًا لا عنصرًا، فلا يُسقط الصفحة ولا يُنتج عنصر تحكّم."""
    tricky = term('tricky', definition_ar='تعريف فيه <input name="x"> و<button>زر</button> و<textarea></textarea> مكتوبة نصًّا.')
    summary, pages = pr.glossary_step(SITE_DIR, _gfile(str(tmp_path), feed_of(tricky)))
    assert summary['state'] == 'ok', summary
    html = next(h for pth, h in pages.items() if pth.endswith('tricky.html'))
    assert not pr.GLOSSARY_ABSENT_CONTROLS_RE.search(_block(html)) and '&lt;input' in _block(html)


@needs_site
def test_no_badge_state_line_reviewer_form_or_endpoint_on_any_page(built):
    """⛔ قرار المؤسس 2026-11-01: لا شارة ولا «راجعه» ولا نموذج ولا نقطة إرسال ولا علامة حالة، ولو حمل الفيد مفاتيح المراجعة (ON_SHAPE)."""
    for slug, html in built['pages'].items():
        b = _block(html)
        for w in ('تحت التأكيد', 'راجعه', 'راجِع', 'أنت متخصص', 'مؤكّد', 'مؤكَّد', 'مؤكد'):
            assert w not in b, (slug, w)
        fb = pr._gl_fold(b)
        for w in ('تحت التأكيد', 'مؤكد', 'تأكيد', 'نبحث عن', 'راجعه'):
            assert pr._gl_fold(w) not in fb, (slug, w)
        assert not pr.GLOSSARY_ABSENT_CONTROLS_RE.search(b), slug
        for m in ('<form', 'gl-rev', 'gl-review', 'gl-form', 'gl-sum', 'gl-hp', 'gl-l-st', 'gl-filter', 'data-st=', 'data-gl-f', 'data-gl-review',
                  'name="verdict"', 'name="website"', 'epGlossaryReviewJs', 'epGlossaryFilterJs'):
            assert m not in html, (slug, m)
        assert 'expert-reviews' not in html and 'api/public' not in html, slug
    on = built['pages']['laches']
    assert 'أ. اسم مسرّب' not in on and 'صفة مسرّبة' not in on                            # الاسم والصفة من الفيد لا يظهران في أي مكان


@needs_site
def test_a_term_page_runs_only_the_renderer_script_besides_the_site_trackers(built):
    for slug in ('offer', 'consideration', 'laches'):
        h = built['pages'][slug]
        ids = re.findall(r'<script id="([^"]+)"', h)
        assert ids.count('epGlossaryJs') == 1 and 'epGlossaryReviewJs' not in ids and 'epGlossaryFilterJs' not in ids
        assert h.count('googletagmanager.com/gtm.js') == built['term_tpl'].count('googletagmanager.com/gtm.js')
        assert 'expert-reviews' not in '\n'.join(pr._script_bodies(h))


@needs_site
def test_index_has_area_chips_only_no_state_marks_no_filter(built):
    idx = _block(built['pages']['index'])
    chips = re.findall(r'<a class="chip" href="#(area-[a-z]+)">([^<]*?) <span class="n">([^<]*)</span></a>', idx)
    assert chips == [('area-contracts', 'عقود', '٤'), ('area-litigation', 'تقاضٍ', '١')]
    assert idx.count('class="chip"') == len(chips) and '<button' not in idx and 'data-st' not in idx and 'gl-l-st' not in idx
    for w in ('مؤكّد', 'تحت التأكيد', 'تصفية'):
        assert w not in idx
    html = built['pages']['index']
    assert 'epGlossaryFilterJs' not in html and 'data-gl-filter' not in html


NMUT = 52


def _in_content(h, old, new):
    """يبدّل أول ظهور داخل كتلة المحتوى فقط (النص نفسه يتكرر في تعليقات القالب وسكربتاته)."""
    i, j = h.index(pr.GL_OPEN), h.index(pr.GL_CLOSE)
    assert old in h[i:j], old
    return h[:i] + h[i:j].replace(old, new, 1) + h[j:]


def _mutations(b):
    """(اسم, slug, دالة تعدّل الصفحة, جزء من رسالة الخطأ)."""
    full = 'consideration'
    actions = '<div class="gl-actions">'
    badge = 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح'
    form = ('<section class="gl-review"><details class="gl-rf"><summary class="btn btn-ghost gl-sum">أنت متخصص؟ راجِع هذا المصطلح</summary>'
            '<form class="gl-form" data-gl-review data-endpoint="https://dashboard.elprofessor.net/api/public/expert-reviews" novalidate>'
            '<input type="hidden" name="kind" value="glossary_term"><div class="gl-hp" aria-hidden="true"><input type="text" name="website" tabindex="-1"></div>'
            '<button type="submit" class="btn btn-primary">أرسل المراجعة</button></form></details></section>')
    return [
        ('second h1', full, lambda h: h.replace('<h1>', '<h1>x</h1><h1>', 1), 'H1'),
        ('wrong canonical', full, lambda h: h.replace('glossary/consideration.html">', 'glossary/other.html">', 1), 'canonical'),
        ('saha link removed', full, lambda h: re.sub(r'<a class="btn btn-ghost"[^>]*>ناقشه في الساحة</a>', '', h), 'saha link'),
        ('saha link doubled', full, lambda h: h.replace(actions, actions + '<a href="' + pr.SAHA_LINK_PREFIX + TID + '">ناقشه في الساحة</a>', 1), 'saha link'),
        ('saha link on a term without topic', 'offer', lambda h: h.replace(actions, actions + '<a href="' + pr.SAHA_LINK_PREFIX + TID + '">ناقشه في الساحة</a>', 1), 'saha'),
        ('saha link on a term with an invalid topic id', 'estoppel', lambda h: h.replace(actions, actions + '<a href="' + pr.SAHA_LINK_PREFIX + TID + '">ناقشه في الساحة</a>', 1), 'saha'),
        ('country note dropped', full, lambda h: h.replace('class="gl-country"', 'class="x"'), 'country'),
        ('country note dropped on a term the old rules hid', 'laches', lambda h: h.replace('class="gl-country"', 'class="x"'), 'country'),
        ('country note doubled', 'waiver', lambda h: h.replace(actions, '<section class="gl-country"><p>يُسمّى «الإسقاط» في بعض البلاد.</p></section>' + actions, 1), 'country'),
        ('country note invented on a term without one', 'offer', lambda h: h.replace(actions, '<section class="gl-country"><p>ملاحظة</p></section>' + actions, 1), 'country'),
        ('script inside the content', full, lambda h: h.replace(actions, '<script>1</script>' + actions, 1), 'script'),
        ('prerender flag missing', full, lambda h: h.replace('window.EP_PRERENDERED=true;', '', 1), 'EP_PRERENDERED'),
        ('slug flag wrong', full, lambda h: h.replace('EP_GLOSSARY_SLUG="consideration"', 'EP_GLOSSARY_SLUG="zzz"', 1), 'SLUG'),
        ('extra tracking tag', full, lambda h: h.replace('</head>', '<script>/* GTM-N5G8ZRBV */</script></head>', 1), 'tracking'),
        ('pixel tag removed', full, lambda h: h.replace('/pixel.js?v=', '/pixel.js-x?v=', 1), 'tracking'),
        ('two DefinedTerm blocks', full, lambda h: h.replace('</head>', '<script type="application/ld+json">{"@type":"DefinedTerm","name":"x"}</script></head>', 1), 'DefinedTerm'),
        ('broken JSON-LD', full, lambda h: h.replace('"termCode"', '"termCode",,', 1), 'JSON-LD'),
        ('relative url', full, lambda h: h.replace('href="/site.css', 'href="site.css', 1), 'relative'),
        ('link to a page that is not generated', full, lambda h: h.replace(actions, '<a href="/glossary/ghost.html">x</a>' + actions, 1), 'related'),
        ('related link dropped', full, lambda h: h.replace('href="/glossary/offer.html"', 'href="/glossary/"', 1), 'related'),
        ('Latin digits left in Arabic example', full, lambda h: h.replace('٥٠٬٠٠٠', '50,000', 1), 'example'),
        ('definition missing', full, lambda h: h.replace('<p class="gl-def">شيء ذو قيمة', '<p class="gl-def">شيء', 1), 'definition'),
        ('ask link doubled', full, lambda h: h.replace(actions, actions + '<a href="https://app.elprofessor.net/?page=chat">اسأل خبيرًا</a>', 1), 'ask'),
        ('placeholder left', full, lambda h: h.replace('<div class="gl-body" id="term">', '<div class="gl-body" id="term"><p>جارٍ تحميل المصطلح…</p>', 1), 'placeholder'),
        # —— الجولة ٣: غياب الشارة وسطر المراجعة والنموذج ونقطة الإرسال وعلامات الحالة (كلٌّ منها يُسقط الصفحة)
        ('stray «تحت التأكيد» badge', 'offer', lambda h: h.replace(actions, '<p>' + badge + '</p>' + actions, 1), 'تحت التأكيد'),
        ('stray badge on a term with a topic', full, lambda h: h.replace(actions, '<p>' + badge + '</p>' + actions, 1), 'تحت التأكيد'),
        ('stray state line markup', 'offer', lambda h: h.replace(actions, '<p class="gl-rev wait" data-state="under_review">x</p>' + actions, 1), 'markup'),
        ('stray confirmed state line', full, lambda h: h.replace(actions, '<p class="gl-rev" data-state="confirmed">x</p>' + actions, 1), 'markup'),
        ('stray «راجعه:» reviewer line', full, lambda h: h.replace(actions, '<p>راجعه: أحد</p>' + actions, 1), 'راجعه'),
        ('stray «راجعه متخصص» line', 'waiver', lambda h: h.replace(actions, '<p>راجعه متخصص</p>' + actions, 1), 'راجعه'),
        ('stray «مؤكّد» word', 'offer', lambda h: h.replace(actions, '<p>مؤكّد</p>' + actions, 1), 'مؤكد'),
        ('stray review button text', full, lambda h: h.replace(actions, '<a class="btn" href="#">أنت متخصص؟ راجِع هذا المصطلح</a>' + actions, 1), 'أنت متخصص'),
        ('stray review form', full, lambda h: h.replace('</article>', form + '</article>', 1), 'markup'),
        ('stray bare form', 'offer', lambda h: h.replace(actions, '<form></form>' + actions, 1), '<form'),
        ('stray review attribute', 'offer', lambda h: h.replace(actions, '<div data-gl-review></div>' + actions, 1), 'data-gl-review'),
        ('stray honeypot input', 'offer', lambda h: h.replace(actions, '<input name="website" tabindex="-1">' + actions, 1), 'markup'),
        ('stray endpoint text', full, lambda h: h.replace(actions, '<p>https://dashboard.elprofessor.net/api/public/expert-reviews</p>' + actions, 1), 'endpoint'),
        ('review script back before the body end', full, lambda h: h.replace('</body>', '<script id="epGlossaryReviewJs">\nvar u="https://dashboard.elprofessor.net/api/public/expert-reviews";\n</script></body>', 1), 'markup'),
        ('endpoint inside another script', 'offer', lambda h: h.replace('</body>', '<script>fetch("https://dashboard.elprofessor.net/api/public/expert-reviews")</script></body>', 1), 'endpoint'),
        ('filter script on a term page', 'offer', lambda h: h.replace('</body>', '<script id="epGlossaryFilterJs">\n1\n</script></body>', 1), 'markup'),
        ('state mark span on a term page', 'offer', lambda h: h.replace(actions, '<span class="gl-l-st is-w">x</span>' + actions, 1), 'markup'),
        # —— ثغرات فحص «لا يبقى شيء»: كلمة بلا تشكيل، أو بتطويل، وأي عنصر إدخال أو زر داخل محتوى المصطلح
        ('plain «مؤكد» without diacritics', 'offer', lambda h: h.replace(actions, '<p>مؤكد</p>' + actions, 1), 'مؤكد'),
        ('«مؤكد» stretched with tatweel', 'offer', lambda h: h.replace(actions, '<p>مؤكـــد</p>' + actions, 1), 'مؤكد'),
        ('hidden badge with plain «مؤكد، نبحث عن مراجع»', full, lambda h: h.replace(actions, '<span class="x" hidden>مؤكد، نبحث عن مراجع</span>' + actions, 1), 'مؤكد'),
        ('«نبحث عن» line', 'offer', lambda h: h.replace(actions, '<p>نبحث عن متخصص</p>' + actions, 1), 'نبحث عن'),
        ('«تأكيد» word', 'offer', lambda h: h.replace(actions, '<p>بانتظار تأكيد</p>' + actions, 1), 'تأكيد'),
        ('stray email input', full, lambda h: h.replace(actions, '<input type="email" name="mail">' + actions, 1), 'form control'),
        ('stray select', 'offer', lambda h: h.replace(actions, '<select><option>x</option></select>' + actions, 1), 'form control'),
        ('stray textarea', 'offer', lambda h: h.replace(actions, '<textarea name="note"></textarea>' + actions, 1), 'form control'),
        ('stray button', 'offer', lambda h: h.replace(actions, '<button type="button">x</button>' + actions, 1), 'form control'),
        ('stray upper-case INPUT', 'offer', lambda h: h.replace(actions, '<INPUT name="x">' + actions, 1), 'form control'),
        ('reviewer name from the feed shown (on-shape)', 'laches', lambda h: h.replace(actions, '<p>راجعه: أ. اسم مسرّب</p>' + actions, 1), 'راجعه'),
    ]


@needs_site
@pytest.mark.parametrize('idx', range(NMUT))
def test_each_defect_fails_verification(built, idx):
    name, slug, fn, needle = _mutations(built)[idx]
    html = fn(built['pages'][slug])
    assert html != built['pages'][slug], name + ': the mutation did not change the page'
    errs = _verify(built, slug, html)
    assert errs and any(needle.lower() in e.lower() for e in errs), (name, errs[:3])


@needs_site
def test_mutations_list_is_exhaustively_parametrized(built):
    assert len(_mutations(built)) == NMUT


@needs_site
def test_index_defects_fail(built):
    idx = built['pages']['index']
    for name, html in (('missing link', idx.replace('href="/glossary/offer.html"', 'href="/glossary/"', 1)),
                       ('search box', idx.replace('<div class="gl-end">', '<input type="search"><div class="gl-end">', 1)),
                       ('wrong canonical', idx.replace('<link rel="canonical" href="https://elprofessor.net/glossary/">', '<link rel="canonical" href="https://elprofessor.net/glossary/index.html">')),
                       ('dead area jump', idx.replace('id="area-litigation"', 'id="area-zzz"', 1))):
        assert pr.verify_glossary_index(html, built['list'], None, built['index_tpl']), name


def _index_errs(built, html):
    return pr.verify_glossary_index(html, built['list'], None, built['index_tpl'])


@needs_site
def test_index_state_and_filter_defects_fail(built):
    """⛔ الفهرس شرائح المجالات وحدها: أي علامة حالة أو زر تصفية أو كلمة تأكيد أو نقطة إرسال تُسقط الصفحة."""
    idx = built['pages']['index']
    cases = (
        ('state mark on an item', idx.replace('<span class="gl-l-ar">الإيجاب</span>', '<span class="gl-l-ar">الإيجاب</span><span class="gl-l-st is-w">تحت التأكيد</span>', 1), 'markup'),
        ('item carries data-st', idx.replace('<li><a href="/glossary/offer.html">', '<li data-st="under_review"><a href="/glossary/offer.html">', 1), 'markup'),
        ('«مؤكّد» word in the content', idx.replace('<div class="gl-end">', '<p>مؤكّد</p><div class="gl-end">', 1), 'مؤكد'),
        ('plain «مؤكد» in the content', idx.replace('<div class="gl-end">', '<p>مؤكد</p><div class="gl-end">', 1), 'مؤكد'),
        ('«مؤكد» stretched with tatweel', idx.replace('<div class="gl-end">', '<p>مؤكـــد</p><div class="gl-end">', 1), 'مؤكد'),
        ('«نبحث عن» line in the content', idx.replace('<div class="gl-end">', '<p>نبحث عن مراجع لهذه المصطلحات</p><div class="gl-end">', 1), 'نبحث عن'),
        ('a textarea in the content', idx.replace('<nav class="gl-areas"', '<textarea></textarea><nav class="gl-areas"', 1), 'form control'),
        ('«تحت التأكيد» note in the content', idx.replace('<div class="gl-end">', '<p>المصطلح المعلَّم بـ«تحت التأكيد» منشور.</p><div class="gl-end">', 1), 'تحت التأكيد'),
        ('filter chips back', idx.replace('<nav class="gl-areas"', '<div class="gl-filter" role="group" data-gl-filter><button type="button" class="chip" data-gl-f="all" aria-pressed="true">الكل <span class="n">٥</span></button></div><nav class="gl-areas"', 1), 'markup'),
        ('a button in the content', idx.replace('<nav class="gl-areas"', '<button type="button">x</button><nav class="gl-areas"', 1), 'button'),
        ('filter script back', idx.replace('</body>', '<script id="epGlossaryFilterJs">\n1\n</script></body>', 1), 'markup'),
        ('review endpoint in a script', idx.replace('</body>', '<script>var u="https://dashboard.elprofessor.net/api/public/expert-reviews";</script></body>', 1), 'endpoint'),
        ('review form back', idx.replace('<div class="gl-end">', '<form></form><div class="gl-end">', 1), 'form'),
        ('search box beside the chips', idx.replace('<nav class="gl-areas"', '<select></select><nav class="gl-areas"', 1), 'search box'),
    )
    for name, html, needle in cases:
        assert html != idx, name + ': the mutation did not change the page'
        errs = _index_errs(built, html)
        assert errs and any(needle.lower() in e.lower() for e in errs), (name, errs[:3])


@needs_site
def test_state_words_in_a_term_name_or_area_do_not_fail_the_index(tmp_path):
    """اسم مصطلح أو مجال فيه «مؤكّد» أو «تحت التأكيد» نصٌّ حرٌّ من الفيد فلا يُسقط الفهرس."""
    t = term('odd', ar='العقد مؤكّد', en='confirmed contract', area='other', area_label='تحت التأكيد')
    summary, pages = pr.glossary_step(SITE_DIR, _gfile(str(tmp_path), feed_of(t)))
    assert summary['state'] == 'ok', summary


# ——————————————————————————————————————————————— ٢) طرفي: سطر الأوامر

@pytest.fixture(scope='module')
def article_feed():
    """فيد مقالات حقيقي الشكل (٦٢ مقالًا) من الدفتر، يُحفظ نصًّا ثم يُنظَّف الدفتر."""
    if not (HAS_NODE and HAS_TPL):
        pytest.skip('needs node + site checkout')
    import datetime
    with flask_app.app_context():
        db.create_all()
        Article.query.delete()
        db.session.commit()
        for i in range(62):
            title = 'مقال تحليلي عن موضوع قانوني رقم %d' % i
            db.session.add(Article(title=title, excerpt=LONG[:160], cat='دليل', kicker='دليل', by='فريق منصة البروفيسور', date='١ أكتوبر ٢٠٢٦',
                                   body=json.dumps(['## ' + title, LONG, LONG], ensure_ascii=False), keywords='[]', faq='[]',
                                   target_audience='المحامون', status='published', published_at=datetime.datetime(2026, 9, 1) + datetime.timedelta(days=i)))
        db.session.commit()
        feed = appmod._prerender_feed_json()
        Article.query.delete()
        db.session.commit()
    return feed


def _site(tmp, glossary_tpls=True, tweak=None):
    for n in ('article.html', 'blog.html'):
        shutil.copy(os.path.join(SITE_DIR, n), os.path.join(tmp, n))
    if glossary_tpls:
        for n in ('glossary-term.html', 'glossary.html'):
            shutil.copy(os.path.join(SITE_DIR, n), os.path.join(tmp, n))
        if tweak:
            tweak(tmp)
    return tmp


def _cli(tmp, article_feed, *extra):
    ff = os.path.join(tmp, '_feed.json')
    _write(ff, article_feed)
    proc = subprocess.run(['python3', PRERENDER, '--site', tmp, '--feed-file', ff, '--min-articles', '1'] + list(extra),
                          capture_output=True, text=True, timeout=300)
    out = None
    if proc.returncode == 0:
        lines = proc.stdout.strip().splitlines()
        out = json.loads(lines[0])                       # ملخّص المقالات (كما كان)
        if len(lines) > 1:
            out.update(json.loads(lines[-1]))            # + سطر القاموس الأخير عند طلبه
    return proc, out


def _tree(tmp, *dirs):
    got = {}
    for d in dirs:
        for root, _dirs, files in os.walk(os.path.join(tmp, d)):
            for f in files:
                p = os.path.join(root, f)
                got[os.path.relpath(p, tmp)] = open(p, 'rb').read()
    return got


def _glossary_files(tmp):
    d = os.path.join(tmp, 'glossary')
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


@needs_site
def test_cli_end_to_end_writes_term_pages_and_index(article_feed, tmp_path):
    tmp = _site(str(tmp_path))
    gf = _gfile(tmp, feed_of(FULL, PLAIN, NOTE_ONLY))
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', gf)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert out['glossary']['state'] == 'ok' and out['glossary']['terms'] == 3
    assert _glossary_files(tmp) == ['consideration.html', 'estoppel.html', 'index.html', 'offer.html']
    assert all(re.match(r'^[a-z0-9.-]+$', n) for n in _glossary_files(tmp))              # أسماء ASCII
    full = _read(os.path.join(tmp, 'glossary', 'consideration.html'))
    offer = _read(os.path.join(tmp, 'glossary', 'offer.html'))
    assert 'راجعه' not in _block(full) and pr.SAHA_LINK_PREFIX + TID + '"' in full
    assert 'راجعه' not in _block(offer) and pr.SAHA_LINK_PREFIX not in _block(offer)
    assert os.path.isfile(os.path.join(tmp, 'blog', '_pre', '%s.html' % json.loads(article_feed)['articles'][0]['id']))   # والمقالات كالمعتاد


def _cli_feed_shapes():
    """مصطلح بنقاش وملاحظة بلاد · مصطلح بلا نقاش · مصطلح بشكل الجولة ٢ (مفاتيح المراجعة موجودة، والاسم فيه رموز تُهرَّب)."""
    topic = term('delay', ar='التأخير', en='delay', fr=None, example_en=None, example_ar=None, saha_topic_id=TID, countries_note_ar='في الأردن 3 أنظمة و0.5% رسم.')
    none = term('waiver', ar='التنازل', en='waiver', fr=None, countries_note_ar='يُسمّى «الإسقاط» في بعض البلاد.')
    on = term('breach', ar='الإخلال', en='breach', example_en=None, example_ar=None, review_state='confirmed', reviewed_at='2026-11-01T09:00:00',
              reviewed_by_name='أ. سلمى & <b>الشريك</b> 2', reviewed_by_role='محكّمة منذ 15 سنة', countries_note_ar='في مصر نظام آخر.')
    return topic, none, on


@needs_site
def test_cli_end_to_end_a_term_with_a_topic_without_one_and_an_on_shape_feed(article_feed, tmp_path):
    tmp = _site(str(tmp_path))
    topic, none, on = _cli_feed_shapes()
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(topic, none, on)))
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert out['glossary']['state'] == 'ok' and out['glossary']['terms'] == 3
    d, w, b, idx = (_read(os.path.join(tmp, 'glossary', f + '.html')) for f in ('delay', 'waiver', 'breach', 'index'))
    # بنقاش: رابط الساحة مرة واحدة؛ بلا نقاش: لا رابط ولا نص؛ ملاحظة البلاد بأرقام هندية تظهر في الثلاثة
    assert _block(d).count(pr.SAHA_LINK_PREFIX + TID + '"') == 1 and _block(d).count('ناقشه في الساحة') == 1
    for h in (w, b):
        assert pr.SAHA_LINK_PREFIX not in _block(h) and 'ناقشه في الساحة' not in _block(h)
    assert 'في الأردن ٣ أنظمة و٠٫٥٪ رسم.' in _block(d) and 'يُسمّى «الإسقاط» في بعض البلاد.' in _block(w) and 'في مصر نظام آخر.' in _block(b)
    assert not re.search(r'[0-9]', pr.strip_to_text(_block(d)))                                       # لا رقم لاتيني في النص الظاهر
    # الفيد بمفاتيح المراجعة لا يغيّر شيئًا: لا اسم ولا صفة ولا سطر ولا نموذج في أي صفحة
    for h in (d, w, b, idx):
        for m in ('سلمى', 'الشريك', 'محكّمة', 'تحت التأكيد', 'راجعه', 'مؤكّد', '<form', 'expert-reviews', 'gl-rev', 'gl-l-st', 'data-st', 'data-gl-f'):
            assert m not in h, m
    assert 'class="chip"' in idx and '<button' not in _block(idx)


@needs_site
def test_cli_the_on_shape_feed_gives_the_same_pages_as_the_off_shape_feed(article_feed, tmp_path):
    """نفس المصطلحات بمفاتيح المراجعة وبدونها ⇒ صفحات قاموس متطابقة بايتًا."""
    off = [term('delay'), term('breach', ar='الإخلال', en='breach', countries_note_ar='ملاحظة.')]
    on = [dict(t, review_state='confirmed', reviewed_by_name='أ. اسم', reviewed_by_role='محامية', reviewed_at='2026-11-01T10:00:00') for t in off]
    trees = []
    for name, terms in (('off', off), ('on', on)):
        d = tmp_path / name
        d.mkdir()
        tmp = _site(str(d))
        proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(*terms)))
        assert proc.returncode == 0 and out['glossary']['state'] == 'ok', proc.stderr[-1500:]
        trees.append(_tree(tmp, 'glossary'))
    assert trees[0] and trees[0] == trees[1]


@needs_site
def test_cli_a_missing_or_odd_review_state_is_not_an_error(article_feed, tmp_path):
    tmp = _site(str(tmp_path))
    for st in ('published', 'draft', 'Confirmed', None, 5):
        proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(PLAIN, term('zz1', review_state=st))))
        assert proc.returncode == 0 and out['glossary']['state'] == 'ok', st
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(PLAIN)))
    assert out['glossary']['state'] == 'ok' and 'review_state' not in _read(os.path.join(tmp, 'glossary', 'offer.html'))


def _inject(tpl, old, new):
    """يعدّل القالب في موقع الأعمال (--site) لاختبار أن المولّد يرفض قالبًا يُعيد ما أُزيل."""
    def tweak(tmp):
        p = os.path.join(tmp, tpl)
        s = _read(p)
        assert old in s, old
        _write(p, s.replace(old, new, 1))
    tweak.__name__ = 'inject_' + re.sub(r'\W+', '_', new)[:30]
    return tweak


@needs_site
@pytest.mark.parametrize('tpl,old,new', [
    ('glossary-term.html', "h.push('</article>');", "h.push('<p class=\"gl-rev wait\" data-state=\"under_review\">تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح</p>');h.push('</article>');"),
    ('glossary-term.html', "h.push('</article>');", "h.push('<form data-gl-review data-endpoint=\"https://dashboard.elprofessor.net/api/public/expert-reviews\"></form>');h.push('</article>');"),
    ('glossary-term.html', "h.push('</article>');", "h.push('<p>راجعه: أحد</p>');h.push('</article>');"),
    ('glossary-term.html', "h.push('</article>');", "h.push('<a class=\"btn\" href=\"#\">أنت متخصص؟ راجِع هذا المصطلح</a>');h.push('</article>');"),
    ('glossary-term.html', "h.push('</article>');", "h.push('<span class=\"gl-badge\" hidden>مؤكد، نبحث عن مراجع</span><input type=\"email\" name=\"mail\">');h.push('</article>');"),
    ('glossary-term.html', "h.push('</article>');", "h.push('<input type=\"email\" name=\"mail\">');h.push('</article>');"),
    ('glossary-term.html', "h.push('</article>');", "h.push('<p>مؤكد</p>');h.push('</article>');"),
    ('glossary.html', "return '<li><a href=\"/glossary/'", "return '<li data-st=\"under_review\"><a href=\"/glossary/'"),
    ('glossary.html', "h.push('<nav class=\"gl-areas\"", "h.push('<p>مؤكّد</p>');h.push('<nav class=\"gl-areas\""),
])
def test_cli_a_template_that_brings_back_the_badge_form_or_state_marks_writes_no_glossary_page(article_feed, tmp_path, tpl, old, new):
    tmp = _site(str(tmp_path), tweak=_inject(tpl, old, new))
    _write(os.path.join(tmp, 'glossary', 'old.html'), 'OLD')                                  # ولا مسح بعد فشل
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(PLAIN)))
    assert proc.returncode == 0 and out['glossary']['state'] == 'error' and 'verification failure' in out['glossary']['error'], new
    assert _glossary_files(tmp) == ['old.html'] and out['files_written'] > 30


@needs_site
def test_cli_dry_run_writes_no_glossary_file(article_feed, tmp_path):
    tmp = _site(str(tmp_path))
    gf = _gfile(tmp, feed_of(FULL))
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', gf, '--dry-run')
    assert proc.returncode == 0 and out['glossary']['state'] == 'ok' and out['dry_run'] is True
    assert _glossary_files(tmp) == []


@needs_site
def test_cli_without_glossary_options_is_the_article_path_only(article_feed, tmp_path):
    tmp = _site(str(tmp_path))                                  # القالبان موجودان لكن لم يُطلب القاموس
    proc, out = _cli(tmp, article_feed)
    assert proc.returncode == 0 and 'glossary' not in out and _glossary_files(tmp) == []


@needs_site
def test_cli_missing_template_skips_the_glossary_with_a_log_line_and_writes_articles(article_feed, tmp_path):
    tmp = _site(str(tmp_path), glossary_tpls=False)
    gf = _gfile(tmp, feed_of(FULL))
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', gf)
    assert proc.returncode == 0, proc.stderr[-1500:]
    assert out['glossary']['state'] == 'skipped' and out['glossary']['reason'] == 'template-missing'
    assert 'glossary: SKIPPED' in proc.stderr and _glossary_files(tmp) == []
    assert os.path.isdir(os.path.join(tmp, 'blog', '_pre')) and out['files_written'] > 30


@needs_site
def test_cli_one_template_missing_also_skips(article_feed, tmp_path):
    tmp = _site(str(tmp_path))
    os.unlink(os.path.join(tmp, 'glossary.html'))
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(FULL)))
    assert proc.returncode == 0 and out['glossary']['state'] == 'skipped' and out['glossary']['missing'] == ['glossary.html']


def _two_h1(tmp):
    p = os.path.join(tmp, 'glossary-term.html')
    s = _read(p)
    old = "<h1>'+esc(ad(t.ar))+'</h1>"
    assert old in s
    _write(p, s.replace(old, "<h1>'+esc(ad(t.ar))+'</h1><h1>x</h1>"))


@needs_site
def test_cli_a_defect_in_any_glossary_page_writes_no_glossary_page_but_articles_are_written(article_feed, tmp_path):
    tmp = _site(str(tmp_path), tweak=_two_h1)
    _write(os.path.join(tmp, 'glossary', 'old.html'), 'OLD')                      # ولا يُمسح شيء بعد فشل
    gf = _gfile(tmp, feed_of(FULL, PLAIN))
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', gf)
    assert proc.returncode == 0, proc.stderr[-1500:]
    assert out['glossary']['state'] == 'error' and 'verification failure' in out['glossary']['error']
    assert _glossary_files(tmp) == ['old.html']                                  # لا صفحة جديدة ولا مسح
    assert out['files_written'] > 30


@needs_site
def test_cli_prerender_guard_broken_in_the_template_is_caught(article_feed, tmp_path):
    def unguard(tmp):
        p = os.path.join(tmp, 'glossary-term.html')
        s = _read(p)
        old = "if(window.EP_PRERENDERED) return;\n  var box=document.getElementById('term');\n  var m="
        assert old in s
        _write(p, s.replace(old, "var box=document.getElementById('term');\n  var m="))
    tmp = _site(str(tmp_path), tweak=unguard)
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(FULL)))
    assert proc.returncode == 0 and out['glossary']['state'] == 'error' and 'EP_PRERENDERED guard broken' in out['glossary']['error']
    assert _glossary_files(tmp) == []


@needs_site
def test_cli_reserved_or_bad_slug_in_the_feed_is_an_error_not_a_page(article_feed, tmp_path):
    tmp = _site(str(tmp_path))
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(PLAIN, term('index'))))
    assert out['glossary']['state'] == 'error' and 'reserved' in out['glossary']['error'] and _glossary_files(tmp) == []


@needs_site
def test_cli_prunes_only_slug_pattern_pages_missing_from_the_feed_after_a_good_run(article_feed, tmp_path):
    tmp = _site(str(tmp_path))
    for n in ('old-term.html', 'notes.txt', 'Upper.html', 'x.html.tmp'):
        _write(os.path.join(tmp, 'glossary', n), 'x')
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(PLAIN)))
    assert proc.returncode == 0 and out['glossary']['state'] == 'ok' and out['pruned'] == 1
    assert _glossary_files(tmp) == ['Upper.html', 'index.html', 'notes.txt', 'offer.html', 'x.html.tmp']
    # --no-prune يترك اليتيمة
    _write(os.path.join(tmp, 'glossary', 'orphan.html'), 'x')
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(PLAIN)), '--no-prune')
    assert 'orphan.html' in _glossary_files(tmp)


@needs_site
def test_cli_empty_feed_is_ok_and_prunes_pages_but_never_the_other_files(article_feed, tmp_path):
    tmp = _site(str(tmp_path))
    _write(os.path.join(tmp, 'glossary', 'gone.html'), 'x')
    _write(os.path.join(tmp, 'glossary', 'keep.json'), 'x')
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of()))
    assert out['glossary'] == {'state': 'ok', 'terms': 0, 'files': []} and _glossary_files(tmp) == ['keep.json']


@needs_site
def test_cli_unreachable_feed_url_is_an_error_without_pruning(article_feed, tmp_path, monkeypatch):
    tmp = _site(str(tmp_path))
    _write(os.path.join(tmp, 'glossary', 'old.html'), 'x')
    # بلا شبكة حقيقية: عنوان محلي مرفوض فورًا (منفذ مغلق) وبلا إعادة محاولة طويلة
    proc, out = _cli(tmp, article_feed, '--glossary-feed-url', 'http://127.0.0.1:9/never')
    assert proc.returncode == 0 and out['glossary']['state'] == 'error' and 'unreachable' in out['glossary']['error']
    assert _glossary_files(tmp) == ['old.html']


@needs_site
def test_articles_output_is_byte_identical_with_and_without_the_glossary(article_feed, tmp_path):
    os.makedirs(str(tmp_path / 'a'))
    os.makedirs(str(tmp_path / 'b'))
    a = _site(str(tmp_path / 'a'))
    b = _site(str(tmp_path / 'b'))
    pa, oa = _cli(a, article_feed)
    gf = _gfile(b, feed_of(FULL, PLAIN))
    pb, ob = _cli(b, article_feed, '--glossary-feed-file', gf)
    assert pa.returncode == 0 and pb.returncode == 0
    ta, tb = _tree(a, 'blog'), _tree(b, 'blog')
    assert ta and ta == tb
    for f in ('blog.html', 'feed.xml'):
        assert open(os.path.join(a, f), 'rb').read() == open(os.path.join(b, f), 'rb').read(), f
    for k in ('articles', 'text_chars_min', 'text_chars_median', 'text_chars_max', 'blog_text_chars', 'rss_bytes', 'pruned', 'topics', 'topics_error'):
        assert oa[k] == ob[k], k
    assert oa['files_written'] + 3 == ob['files_written']                          # صفحتا مصطلحين + الفهرس، لا غير
    assert 'glossary' not in oa and ob['glossary']['state'] == 'ok'


@needs_site
def test_old_site_template_set_is_safe_default_url_is_never_fetched_without_a_flag(article_feed, tmp_path, monkeypatch):
    assert pr.GLOSSARY_FEED_URL == 'https://dashboard.elprofessor.net/api/content/glossary'
    tmp = _site(str(tmp_path))
    proc, out = _cli(tmp, article_feed)           # لا --glossary: لا شبكة ولا مفتاح
    assert proc.returncode == 0 and 'glossary' not in out


# ——————————————————————————————————————————————— ٣) الدفع والمسح (app.py) بـSFTP بديل

class FakeSftp(object):
    """نظام ملفات في الذاكرة بواجهة paramiko المستعملة في _prerender_push."""
    def __init__(self, files=None, dirs=()):
        self.files = dict(files or {})
        self.dirs = set(dirs)
        self.removed = []

    def normalize(self, p):
        return '/home/u'

    def stat(self, p):
        if p in self.dirs or p in self.files:
            return object()
        raise IOError(p)

    def mkdir(self, p):
        self.dirs.add(p)

    def put(self, local, remote):
        with open(local, 'rb') as fh:
            self.files[remote] = fh.read()

    def posix_rename(self, src, dst):
        self.files[dst] = self.files.pop(src)

    def rename(self, src, dst):
        self.posix_rename(src, dst)

    def listdir(self, d):
        if d not in self.dirs:
            raise IOError(d)
        pre = d.rstrip('/') + '/'
        return sorted({p[len(pre):].split('/')[0] for p in list(self.files) + list(self.dirs) if p.startswith(pre) and p != d})

    def remove(self, p):
        if p not in self.files:
            raise IOError(p)
        self.removed.append(p)
        del self.files[p]

    def putfo(self, fo, p):
        self.files[p] = fo.read()

    def close(self):
        pass


ROOT = '/home/u/domains/elprofessor.net/public_html'


@pytest.fixture
def push(monkeypatch, article_feed, tmp_path):
    """يشغّل _prerender_push الحقيقي (المولّد الحقيقي والقوالب الحقيقية) مع بدائل للشبكة والـSFTP."""
    if not (HAS_NODE and HAS_TPL):
        pytest.skip('needs node + site checkout')
    state = {'hashes': str(tmp_path / 'hashes.json'), 'sftp': None, 'tpl_status': {}, 'feed': feed_of(FULL, PLAIN), 'tpl_get': []}

    def fake_get(url, **kw):
        name = url.rsplit('/', 1)[-1]
        state['tpl_get'].append(name)
        code = state['tpl_status'].get(name, 200)
        path = os.path.join(SITE_DIR, name)
        return types.SimpleNamespace(status_code=code if os.path.isfile(path) else 404, text=_read(path) if os.path.isfile(path) else '')

    sftp_holder = {}

    class Client(object):
        def set_missing_host_key_policy(self, p):
            pass

        def connect(self, *a, **k):
            pass

        def open_sftp(self):
            return sftp_holder['s']

        def close(self):
            pass
    monkeypatch.setitem(sys.modules, 'paramiko', types.SimpleNamespace(SSHClient=Client, AutoAddPolicy=lambda: None))
    monkeypatch.setattr(appmod.requests, 'get', fake_get)
    monkeypatch.setattr(appmod, '_prerender_ready', lambda: (True, ''))
    monkeypatch.setattr(appmod, '_PRERENDER_SCRIPT', PRERENDER)
    monkeypatch.setattr(appmod, '_PRERENDER_HASHES', str(tmp_path / 'hashes.json'))
    monkeypatch.setattr(appmod, '_prerender_feed_json', lambda: article_feed)
    monkeypatch.setattr(appmod, '_retracted_article_ids', lambda: set())
    monkeypatch.setitem(appmod.__dict__, '_glossary_feed_payload', lambda: copy.deepcopy(state['feed']))

    def run(remote_files=None, dirs=()):
        s = FakeSftp(remote_files, set(dirs) | {ROOT})
        sftp_holder['s'] = s
        with flask_app.app_context():
            Article.query.delete()
            db.session.commit()
            res = appmod._prerender_push('test')
        return res, s
    state['run'] = run
    return state


def _glob(s, sub):
    pre = '%s/%s/' % (ROOT, sub)
    return sorted(p[len(pre):] for p in s.files if p.startswith(pre))


@needs_site
def test_push_uploads_glossary_pages_prunes_orphans_and_writes_sitemap(push):
    remote = {ROOT + '/glossary/old-term.html': b'old', ROOT + '/glossary/notes.txt': b'keep', ROOT + '/glossary/x.html.tmp': b'keep',
              ROOT + '/glossary/Upper.html': b'keep'}
    res, s = push['run'](remote, dirs=[ROOT + '/glossary'])
    assert res['state'] == 'ok', res
    assert res['glossary'] == {'state': 'ok', 'pages': 3, 'pruned': 1}
    assert _glob(s, 'glossary') == ['Upper.html', 'consideration.html', 'index.html', 'notes.txt', 'offer.html', 'x.html.tmp']
    assert ROOT + '/glossary/old-term.html' in s.removed and len(s.removed) == 1
    assert not [p for p in s.files if p.endswith('.tmp') and p != ROOT + '/glossary/x.html.tmp']            # لا بقايا رفع
    sm = s.files[ROOT + '/sitemap-articles.xml'].decode('utf-8')
    assert '<loc>https://elprofessor.net/glossary/</loc>' in sm and '<loc>https://elprofessor.net/glossary/consideration.html</loc>' in sm
    assert '<lastmod>2026-11-01</lastmod>' in sm and sm.count('/glossary/') == 3
    assert res['articles'] == 62 and push['tpl_get'][:4] == ['article.html', 'blog.html', 'glossary-term.html', 'glossary.html']


@needs_site
def test_push_second_run_uploads_nothing_new_for_unchanged_pages(push):
    r1, s = push['run']()
    assert r1['glossary']['pages'] == 3
    # نفس الهاشات ⇒ لا رفع (الهاش في ملف)، والمسح ما زال لا يمسّ شيئًا
    r2, s2 = push['run'](dict(s.files), dirs=list(s.dirs))
    assert r2['state'] == 'ok' and r2['uploaded'] == 0 and r2['glossary']['pruned'] == 0


@needs_site
def test_push_glossary_template_404_uploads_and_prunes_nothing_of_the_glossary(push):
    push['tpl_status']['glossary.html'] = 404
    remote = {ROOT + '/glossary/old-term.html': b'old'}
    res, s = push['run'](remote, dirs=[ROOT + '/glossary'])
    assert res['state'] == 'ok' and 'glossary' not in res
    assert _glob(s, 'glossary') == ['old-term.html'] and s.removed == []
    assert '/glossary/' not in s.files[ROOT + '/sitemap-articles.xml'].decode('utf-8')
    assert len(_glob(s, 'blog/_pre')) >= 62                                      # المقالات كالمعتاد


@needs_site
def test_push_failed_glossary_verification_or_feed_never_prunes(push):
    push['feed'] = feed_of(PLAIN, term('index'))                                 # slug محجوز ⇒ الخطوة error
    remote = {ROOT + '/glossary/old-term.html': b'old'}
    res, s = push['run'](remote, dirs=[ROOT + '/glossary'])
    assert res['state'] == 'ok' and res['glossary']['state'] == 'error' and res['glossary']['pages'] == 0
    assert _glob(s, 'glossary') == ['old-term.html'] and s.removed == []
    assert len(_glob(s, 'blog/_pre')) >= 62


@needs_site
def test_push_feed_payload_raising_skips_the_glossary_and_keeps_articles(push, monkeypatch):
    def boom():
        raise RuntimeError('db down')
    monkeypatch.setitem(appmod.__dict__, '_glossary_feed_payload', boom)
    remote = {ROOT + '/glossary/old-term.html': b'old'}
    res, s = push['run'](remote, dirs=[ROOT + '/glossary'])
    assert res['state'] == 'ok' and 'glossary' not in res and s.removed == []
    assert _glob(s, 'glossary') == ['old-term.html']


@needs_site
def test_push_unpublishing_every_term_removes_the_pages_but_not_other_files(push):
    push['feed'] = feed_of()
    remote = {ROOT + '/glossary/consideration.html': b'x', ROOT + '/glossary/index.html': b'x', ROOT + '/glossary/readme.txt': b'keep'}
    res, s = push['run'](remote, dirs=[ROOT + '/glossary'])
    assert res['glossary'] == {'state': 'ok', 'pages': 0, 'pruned': 2}
    assert _glob(s, 'glossary') == ['readme.txt']


@needs_site
def test_push_articles_are_identical_with_and_without_the_glossary(push):
    r_with, s_with = push['run']()
    os.unlink(push['hashes'])                                    # كاش الهاشات يجعل الدفعة الثانية «بلا تغيير» فلا تملأ الـSFTP الجديد
    push['tpl_status']['glossary-term.html'] = 404
    r_wo, s_wo = push['run']()
    art = lambda s: {p: v for p, v in s.files.items() if '/blog/' in p or p.endswith('/blog.html') or p.endswith('/feed.xml')}   # noqa: E731
    assert art(s_with) == art(s_wo) and art(s_with)
    assert 'glossary' in r_with and 'glossary' not in r_wo
    assert r_with['articles'] == r_wo['articles'] == 62


def test_public_sitemap_fallback_is_unchanged_by_the_glossary():
    with flask_app.app_context():
        a = appmod._articles_sitemap_xml()
        assert '/glossary/' not in a and a.startswith('<?xml') and a.endswith('</urlset>')
    rows = appmod._glossary_sitemap_rows({'terms': [{'slug': 'offer', 'updated_at': '2026-11-01T10:05:00'}]}, ['offer.html', 'index.html'])
    assert rows.startswith('<url><loc>https://elprofessor.net/glossary/</loc><lastmod>2026-11-01</lastmod>')
    assert '<loc>https://elprofessor.net/glossary/offer.html</loc>' in rows and appmod._glossary_sitemap_rows({}, []) == ''


def test_remote_prune_rules_for_the_glossary_dir():
    class S(FakeSftp):
        pass
    s = S({'/r/glossary/a.html': b'', '/r/glossary/b.html': b'', '/r/glossary/index.html': b'', '/r/glossary/n.txt': b'', '/r/glossary/c.html.tmp': b''},
          dirs={'/r/glossary'})
    n = appmod._prerender_prune_glossary(s, '/r/glossary', {'glossary/a.html': 'h', 'glossary/index.html': 'h', 'blog.html': 'h'})
    assert n == 1 and s.removed == ['/r/glossary/b.html']
    assert appmod._prerender_prune_glossary(FakeSftp(), '/r/missing', {}) == 0                  # دليل غائب ⇒ لا خطأ
