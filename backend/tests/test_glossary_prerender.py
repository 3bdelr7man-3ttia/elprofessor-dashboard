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
  ٤. الجولة ٢ (قرار المؤسس 2026-11-01): المصطلح المنشور بلا ختم ظاهر «تحت التأكيد»، و«مؤكّد» بعد الختم (باسم المراجع إن وافق وإلا «راجعه متخصص»)؛
     نموذج «أنت متخصص؟ راجِع هذا المصطلح» (وجهة حرفية، kind/ref، فخّ الروبوتات، التخصصات الست)، وعلامات الفهرس وأزرار التصفية؛
     كل قاعدة ومعها عيب يُسقطها، وطرفي بسطر الأوامر للحالات الثلاث.
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
    t = {'id': 1, 'slug': slug, 'ar': 'المقابل (العوض)', 'en': 'consideration', 'fr': 'contrepartie', 'area': 'contracts',
         'area_label': 'عقود', 'definition_ar': 'شيء ذو قيمة يقدّمه كل طرف للآخر ليصبح الوعد ملزمًا.',
         'example_en': 'The fee is USD 50,000.', 'example_ar': 'الرسم 50,000 دولار بنسبة 0.5% سنويًا.',
         'false_friend_note_ar': 'لا تترجمها «الاعتبار».', 'countries_note_ar': None, 'related': [], 'review_state': 'under_review',
         'reviewed_by_name': None, 'reviewed_by_role': None, 'reviewed_at': None, 'saha_topic_id': None,
         'published_at': '2026-11-01T10:05:00', 'updated_at': '2026-11-01T10:05:00'}
    t.update(kw)
    return t


def feed_of(*terms, areas=AREAS):
    return {'source': 'dashboard', 'areas': areas, 'terms': list(terms)}


FULL = term('consideration', review_state='confirmed', reviewed_by_name='أ. هبة الجندي', reviewed_by_role='محامية', reviewed_at='2026-11-01T10:00:00',
            saha_topic_id=TID, countries_note_ar='يُقال «العوض» في مصر و«المقابل» في الأردن.',
            related=[{'slug': 'offer', 'ar': 'الإيجاب', 'en': 'offer'}, {'slug': 'ghost', 'ar': 'شبح', 'en': 'ghost'}])
PLAIN = term('offer', ar='الإيجاب', en='offer', fr=None, example_en=None, example_ar=None, false_friend_note_ar=None,
             area='litigation', area_label='تقاضٍ', related=[{'slug': 'consideration', 'ar': 'المقابل', 'en': 'consideration'}],
             countries_note_ar=None)
UNREV_WITH_NOTE = term('estoppel', ar='الدفع بالتناقض', en='estoppel', countries_note_ar='ملاحظة بلاد لا يجوز ظهورها.',
                       saha_topic_id='bad id!')
# مؤكّد والمراجع لم يوافق على ظهور اسمه: الخادم يرجّع الاسم والصفة null، والملاحظة تظهر
CONF_ANON = term('waiver', ar='التنازل', en='waiver', fr=None, review_state='confirmed', reviewed_at='2026-11-01T09:00:00',
                 countries_note_ar='يُسمّى «الإسقاط» في بعض البلاد.', example_ar=None, example_en=None, false_friend_note_ar=None)
# فيد مخالف للعقد: تحت التأكيد ومعه اسم مراجع وملاحظة بلاد ⇒ القالب والمولّد يمنعان ظهورهما
LEAK = term('laches', ar='التقادم المانع', en='laches', reviewed_by_name='أ. اسم مسرّب', reviewed_by_role='صفة مسرّبة',
            countries_note_ar='ملاحظة بلاد مسرّبة.')


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


def test_feed_requires_a_known_review_state(tmp_path):
    for state in ('draft', 'published', 'CONFIRMED', '', None, 5, True):
        msg = _feed_err(tmp_path, feed_of(term('st1', review_state=state)))
        assert 'review_state' in msg and 'st1' in msg, state
    t = term('st2')
    del t['review_state']
    assert 'review_state' in _feed_err(tmp_path, feed_of(t))                          # غيابه عيب لا افتراض
    assert 'reviewed_at is not text' in _feed_err(tmp_path, feed_of(term('st3', reviewed_at=7))).replace('glossary term st3: ', '')
    p = tmp_path / 'ok.json'
    p.write_text(json.dumps(feed_of(term('a1'), term('a2', review_state='confirmed'))), encoding='utf-8')
    assert [t['review_state'] for t in pr.fetch_glossary_feed(str(p))[0]] == ['under_review', 'confirmed']


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
    terms = [FULL, PLAIN, UNREV_WITH_NOTE, CONF_ANON, LEAK]
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
def test_good_pages_verify_with_and_without_reviewer_and_topic(built):
    for slug in ('consideration', 'offer', 'estoppel', 'waiver', 'laches'):
        assert _verify(built, slug) == [], slug
    assert pr.verify_glossary_index(built['pages']['index'], built['list'], None, built['index_tpl']) == []


@needs_site
def test_reviewer_topic_and_country_note_appear_only_when_they_should(built):
    full, plain, unrev = (_block(built['pages'][s]) for s in ('consideration', 'offer', 'estoppel'))
    assert full.count('راجعه:') == 1 and '<bdi>أ. هبة الجندي</bdi>، <bdi>محامية</bdi>' in full
    assert full.count(pr.SAHA_LINK_PREFIX + TID + '"') == 1 and full.count('ناقشه في الساحة') == 1
    assert 'class="gl-country"' in full and 'في البلاد العربية' in full
    for b in (plain, unrev):
        assert 'راجعه' not in b and pr.SAHA_LINK_PREFIX not in b and 'ناقشه في الساحة' not in b       # «راجِع» في الزر بكسرة: كلمة أخرى
    assert 'class="gl-country"' not in unrev and 'ملاحظة بلاد' not in built['pages']['estoppel'].split('<script id="epGlossaryJs">')[0]
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
@pytest.mark.parametrize('state,name', [('under_review', None), ('confirmed', 'أ. هبة الجندي'), ('confirmed', None)])
def test_state_words_inside_the_content_do_not_fail_the_glossary(tmp_path, state, name):
    """تعريف أو مثال أو ملاحظة تحوي «راجعه:» أو «راجعه متخصص» أو نص الشارة لا يُسقط الصفحة؛ العدّ داخل سطر الحالة وحده."""
    badge = 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح'
    tricky = term('tricky', review_state=state, reviewed_by_name=name, reviewed_by_role='محامية' if name else None,
                  reviewed_at='2026-11-01T10:00:00' if state == 'confirmed' else None,
                  definition_ar='تعريف يذكر عبارة راجعه: فلان وعبارة راجعه متخصص وعبارة «%s» في سياق الشرح.' % badge,
                  example_ar='مثال: راجعه: محامٍ آخر.', false_friend_note_ar='خطأ في نقل «راجعه متخصص».')
    gf = _gfile(str(tmp_path), feed_of(tricky))
    summary, pages = pr.glossary_step(SITE_DIR, gf)
    assert summary['state'] == 'ok', summary
    html = next(h for pth, h in pages.items() if pth.endswith('tricky.html'))
    b = _block(html)
    assert b.count(badge) == (2 if state == 'under_review' else 1) and 'راجعه متخصص' in b
    assert pr.verify_glossary_term(html, tricky, None, _read(os.path.join(SITE_DIR, 'glossary-term.html')), {'tricky'}) == []


@needs_site
def test_state_line_badge_reviewer_and_anonymous_reviewer(built):
    under, conf, anon, leak = (_block(built['pages'][s_]) for s_ in ('offer', 'consideration', 'waiver', 'laches'))
    badge = 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح'
    for b in (under, leak):                                             # تحت التأكيد ⇒ الشارة الهادئة وحدها
        assert b.count(badge) == 1 and 'data-state="under_review"' in b and 'class="gl-rev wait"' in b
        assert 'راجعه' not in b
    for b in (conf, anon):                                              # مؤكّد ⇒ لا شارة
        assert badge not in b and 'data-state="confirmed"' in b and 'class="gl-rev wait"' not in b
    assert conf.count('راجعه: <b><bdi>أ. هبة الجندي</bdi>، <bdi>محامية</bdi></b>') == 1 and 'راجعه متخصص' not in conf
    assert anon.count('راجعه متخصص') == 1 and 'راجعه:' not in anon                              # بلا اسم ولا صفة
    # ملاحظة البلاد: مؤكّد فقط (حتى بلا اسم ظاهر)، وتسريب الفيد يُحجب في القالب
    assert 'class="gl-country"' in anon and 'يُسمّى «الإسقاط» في بعض البلاد.' in anon
    assert 'class="gl-country"' not in leak and 'ملاحظة بلاد مسرّبة' not in built['pages']['laches'].split('<script id="epGlossaryJs">')[0]
    assert 'أ. اسم مسرّب' not in built['pages']['laches'].split('<script id="epGlossaryJs">')[0] and 'صفة مسرّبة' not in leak
    # الحالة سطر واحد بالضبط في كل صفحة، وهو الأول بعد الأسماء (داخل رأس البطاقة)
    for slug in ('offer', 'consideration', 'waiver', 'laches', 'estoppel'):
        assert len(re.findall(r'<p class="gl-rev', _block(built['pages'][slug]))) == 1, slug


@needs_site
def test_every_term_page_has_exactly_one_review_form_with_the_exact_endpoint(built):
    for slug, html in built['pages'].items():
        if slug == 'index':
            continue
        b = _block(html)
        assert b.count('<form') == 1 and b.count('أنت متخصص؟ راجِع هذا المصطلح') == 1, slug
        assert b.count('data-endpoint="https://dashboard.elprofessor.net/api/public/expert-reviews"') == 1, slug
        assert b.count('<input type="hidden" name="kind" value="glossary_term">') == 1
        assert b.count('<input type="hidden" name="ref" value="%s">' % slug) == 1
        assert b.count('name="website"') == 1 and '<div class="gl-hp" aria-hidden="true">' in b and 'tabindex="-1"' in b
        assert not re.search(r'<form[^>]*\baction=', b) and '<script' not in b.lower()
        assert re.findall(r'<option value="([^"]*)">', b) == ['', 'law_practice', 'judiciary', 'legal_translation', 'law_teaching', 'corporate_counsel', 'other']
        for label in ('محاماة', 'قضاء', 'ترجمة قانونية', 'تدريس القانون', 'مستشار شركات', '>أخرى</option>'):
            assert label in b
        assert re.findall(r'name="verdict" value="([^"]*)"', b) == ['confirm', 'suggest']
        for text in ('أؤكد الترجمة والتعريف', 'أقترح تعديلًا', 'أوافق على ظهور اسمي مع المصطلح بعد اعتماد مراجعتي',
                     'لا نعرض بريدك، ونستعمله للتواصل بشأن مراجعتك فقط.'):
            assert b.count(text) == 1
        assert html.count('<script id="epGlossaryReviewJs">') == 1 and html.index('<script id="epGlossaryReviewJs">') > html.index(pr.GL_CLOSE)


@needs_site
def test_review_script_is_not_a_tracker_and_the_page_adds_no_tracking(built):
    for slug in ('offer', 'consideration'):
        h = built['pages'][slug]
        js = re.search(r'<script id="epGlossaryReviewJs">\n(.*?)</script>', h, re.S).group(1)
        for bad in pr.GL_TRACKING_JS:
            assert bad not in js, bad
        assert "credentials:'omit'" in js and h.count('googletagmanager.com/gtm.js') == built['term_tpl'].count('googletagmanager.com/gtm.js')
        sec = re.search(r'(?s)<section class="gl-review".*?</section>', _block(h)).group(0)
        assert 'data-cta' not in sec and 'pixel' not in sec.lower()              # نموذج المراجعة بلا وسوم قياس


@needs_site
def test_index_marks_each_term_with_its_state_and_has_filter_chips(built):
    idx = _block(built['pages']['index'])
    items = dict((m[1], (m[0], m[2], m[3])) for m in re.findall(
        r'<li data-st="([a-z_]+)"><a href="/glossary/([^"/]+)\.html">.*?<span class="gl-l-st (is-[cw])">([^<]*)</span>', idx, re.S))
    assert items == {'consideration': ('confirmed', 'is-c', 'مؤكّد'), 'waiver': ('confirmed', 'is-c', 'مؤكّد'),
                     'offer': ('under_review', 'is-w', 'تحت التأكيد'), 'estoppel': ('under_review', 'is-w', 'تحت التأكيد'),
                     'laches': ('under_review', 'is-w', 'تحت التأكيد')}
    chips = re.findall(r'data-gl-f="([a-z_]+)" aria-pressed="([a-z]+)">([^<]*?) <span class="n">([^<]*)</span>', idx)
    assert chips == [('all', 'true', 'الكل', '٥'), ('confirmed', 'false', 'مؤكّد', '٢'), ('under_review', 'false', 'تحت التأكيد', '٣')]
    assert idx.count('data-gl-filter') == 1 and 'role="group"' in idx and '<input' not in idx and '<form' not in idx
    html = built['pages']['index']
    assert html.count('<script id="epGlossaryFilterJs">') == 1 and html.index('<script id="epGlossaryFilterJs">') > html.index(pr.GL_CLOSE)


@needs_site
def test_index_without_both_states_has_no_filter_chips_but_still_marks(built, tmp_path):
    for feed_terms, mark in (([PLAIN, UNREV_WITH_NOTE], 'تحت التأكيد'), ([FULL, CONF_ANON], 'مؤكّد')):
        summary, pages = pr.glossary_step(SITE_DIR, _gfile(str(tmp_path), feed_of(*feed_terms)))
        idx = next(h for p_, h in pages.items() if p_.endswith('index.html'))
        b = _block(idx)
        assert 'data-gl-filter' not in b and 'data-gl-f=' not in b and b.count('class="gl-l-st') == 2
        assert re.findall(r'<span class="gl-l-st is-[cw]">([^<]*)</span>', b) == [mark, mark]
        assert pr.verify_glossary_index(idx, feed_terms, None, built['index_tpl']) == []


NMUT = 60


def _in_content(h, old, new):
    """يبدّل أول ظهور داخل كتلة المحتوى فقط (النص نفسه يتكرر في تعليقات القالب وسكربتاته)."""
    i, j = h.index(pr.GL_OPEN), h.index(pr.GL_CLOSE)
    assert old in h[i:j], old
    return h[:i] + h[i:j].replace(old, new, 1) + h[j:]


def _in_review_js(h, old, new):
    k = h.index('<script id="epGlossaryReviewJs">')
    assert old in h[k:], old
    return h[:k] + h[k:].replace(old, new, 1)


def _mutations(b):
    """(اسم, slug, دالة تعدّل الصفحة, جزء من رسالة الخطأ)."""
    full = 'consideration'
    return [
        ('second h1', full, lambda h: h.replace('<h1>', '<h1>x</h1><h1>', 1), 'H1'),
        ('wrong canonical', full, lambda h: h.replace('glossary/consideration.html">', 'glossary/other.html">', 1), 'canonical'),
        ('saha link removed', full, lambda h: re.sub(r'<a class="btn btn-ghost"[^>]*>ناقشه في الساحة</a>', '', h), 'saha link'),
        ('saha link doubled', full, lambda h: h.replace('<div class="gl-actions">', '<div class="gl-actions"><a href="' + pr.SAHA_LINK_PREFIX + TID + '">ناقشه في الساحة</a>', 1), 'saha link'),
        ('saha link on a term without topic', 'offer', lambda h: h.replace('<div class="gl-actions">', '<div class="gl-actions"><a href="' + pr.SAHA_LINK_PREFIX + TID + '">ناقشه في الساحة</a>', 1), 'saha'),
        ('review stamp dropped', full, lambda h: h.replace('راجعه:', 'راجع:'), 'راجعه'),
        ('review stamp on an unreviewed term', 'offer', lambda h: h.replace('<div class="gl-actions">', '<p>راجعه: أحد</p><div class="gl-actions">', 1), 'راجعه'),
        ('country note leaked on an unreviewed term', 'estoppel', lambda h: h.replace('<div class="gl-actions">', '<section class="gl-country"><p>ملاحظة بلاد لا يجوز ظهورها.</p></section><div class="gl-actions">', 1), 'country'),
        ('country note dropped on a reviewed term', full, lambda h: h.replace('class="gl-country"', 'class="x"'), 'country'),
        ('script inside the content', full, lambda h: h.replace('<div class="gl-actions">', '<script>1</script><div class="gl-actions">', 1), 'script'),
        ('prerender flag missing', full, lambda h: h.replace('window.EP_PRERENDERED=true;', '', 1), 'EP_PRERENDERED'),
        ('slug flag wrong', full, lambda h: h.replace('EP_GLOSSARY_SLUG="consideration"', 'EP_GLOSSARY_SLUG="zzz"', 1), 'SLUG'),
        ('extra tracking tag', full, lambda h: h.replace('</head>', '<script>/* GTM-N5G8ZRBV */</script></head>', 1), 'tracking'),
        ('pixel tag removed', full, lambda h: h.replace('/pixel.js?v=', '/pixel.js-x?v=', 1), 'tracking'),
        ('two DefinedTerm blocks', full, lambda h: h.replace('</head>', '<script type="application/ld+json">{"@type":"DefinedTerm","name":"x"}</script></head>', 1), 'DefinedTerm'),
        ('broken JSON-LD', full, lambda h: h.replace('"termCode"', '"termCode",,', 1), 'JSON-LD'),
        ('relative url', full, lambda h: h.replace('href="/site.css', 'href="site.css', 1), 'relative'),
        ('link to a page that is not generated', full, lambda h: h.replace('<div class="gl-actions">', '<a href="/glossary/ghost.html">x</a><div class="gl-actions">', 1), 'related'),
        ('related link dropped', full, lambda h: h.replace('href="/glossary/offer.html"', 'href="/glossary/"', 1), 'related'),
        ('Latin digits left in Arabic example', full, lambda h: h.replace('٥٠٬٠٠٠', '50,000', 1), 'example'),
        ('definition missing', full, lambda h: h.replace('<p class="gl-def">شيء ذو قيمة', '<p class="gl-def">شيء', 1), 'definition'),
        ('ask link doubled', full, lambda h: h.replace('<div class="gl-actions">', '<div class="gl-actions"><a href="https://app.elprofessor.net/?page=chat">اسأل خبيرًا</a>', 1), 'ask'),
        ('placeholder left', full, lambda h: h.replace('<div class="gl-body" id="term">', '<div class="gl-body" id="term"><p>جارٍ تحميل المصطلح…</p>', 1), 'placeholder'),
        # —— الجولة ٢: الحالة
        ('badge missing on an under-review term', 'offer', lambda h: h.replace('تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح', 'قيد النظر'), 'badge'),
        ('badge doubled', 'offer', lambda h: h.replace('<div class="gl-actions">', '<p>تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح</p><div class="gl-actions">', 1), 'badge'),
        ('badge on a confirmed term', full, lambda h: h.replace('<div class="gl-actions">', '<p>تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح</p><div class="gl-actions">', 1), 'badge'),
        ('badge on a confirmed term without a name', 'waiver', lambda h: h.replace('<div class="gl-actions">', '<p>تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح</p><div class="gl-actions">', 1), 'badge'),
        ('reviewer name missing on a confirmed term', full, lambda h: h.replace('أ. هبة الجندي', 'أحدهم', 1), 'name'),
        ('anonymous line missing', 'waiver', lambda h: h.replace('راجعه متخصص', 'راجعه أحد', 1), 'راجعه متخصص'),
        ('anonymous line on an under-review term', 'offer', lambda h: h.replace('<div class="gl-actions">', '<p>راجعه متخصص</p><div class="gl-actions">', 1), 'راجعه متخصص'),
        ('anonymous line next to a public name', full, lambda h: h.replace('<div class="gl-actions">', '<p>راجعه متخصص</p><div class="gl-actions">', 1), 'راجعه متخصص'),
        ('name shown on a confirmed term that hides it', 'waiver', lambda h: h.replace('<div class="gl-actions">', '<p>راجعه: أحد</p><div class="gl-actions">', 1), 'راجعه'),
        ('leaked reviewer name on an under-review term', 'laches', lambda h: h.replace('<div class="gl-actions">', '<p>أ. اسم مسرّب</p><div class="gl-actions">', 1), 'leaked'),
        ('leaked country note on an under-review term', 'laches', lambda h: h.replace('<div class="gl-actions">', '<section class="gl-country"><p>ملاحظة بلاد مسرّبة.</p></section><div class="gl-actions">', 1), 'country'),
        ('country note dropped on a confirmed anonymous term', 'waiver', lambda h: h.replace('class="gl-country"', 'class="x"'), 'country'),
        ('two state lines', 'offer', lambda h: h.replace('<div class="gl-actions">', '<p class="gl-rev wait" data-state="under_review">x</p><div class="gl-actions">', 1), 'state line'),
        ('state line says the wrong state', 'offer', lambda h: h.replace('data-state="under_review"', 'data-state="confirmed"', 1), 'data-state'),
        # —— الجولة ٢: نموذج المراجعة
        ('form removed', full, lambda h: re.sub(r'(?s)<form.*?</form>', '', h), 'form'),
        ('form doubled', full, lambda h: h.replace('</form>', '</form><form data-gl-review></form>', 1), 'form'),
        ('endpoint wrong host', full, lambda h: h.replace('dashboard.elprofessor.net/api/public/expert-reviews', 'dashboard.elprofessor.net/api/messages', 1), 'post to exactly'),
        ('endpoint lookalike', full, lambda h: h.replace('https://dashboard.elprofessor.net/api/public', 'https://dashboard.elprofessor.net.evil.example/api/public', 1), 'post to exactly'),
        ('form got an action', full, lambda h: h.replace('<form class="gl-form"', '<form action="/x" class="gl-form"', 1), 'action'),
        ('kind wrong', full, lambda h: h.replace('name="kind" value="glossary_term"', 'name="kind" value="course"', 1), 'kind'),
        ('ref wrong', full, lambda h: h.replace('name="ref" value="consideration"', 'name="ref" value="offer"', 1), 'ref'),
        ('ref missing', full, lambda h: h.replace('<input type="hidden" name="ref" value="consideration">', '', 1), 'ref'),
        ('honeypot renamed', full, lambda h: h.replace('name="website"', 'name="site"', 1), 'honeypot'),
        ('honeypot visible (not hidden from assistive tech)', full, lambda h: h.replace('<div class="gl-hp" aria-hidden="true">', '<div class="gl-hp">', 1), 'honeypot'),
        ('honeypot reachable by tab', full, lambda h: h.replace('name="website" tabindex="-1"', 'name="website"', 1), 'honeypot'),
        ('honeypot prefilled', full, lambda h: h.replace('name="website" tabindex="-1"', 'name="website" value="x" tabindex="-1"', 1), 'honeypot'),
        ('review button text changed', full, lambda h: _in_content(h, 'أنت متخصص؟ راجِع هذا المصطلح', 'راجع المصطلح'), 'button'),
        ('specialty «أخرى» removed', full, lambda h: h.replace('<option value="other">أخرى</option>', '', 1), 'specialty'),
        ('specialty value renamed', full, lambda h: h.replace('value="judiciary"', 'value="judge"', 1), 'specialty'),
        ('verdict radio removed', full, lambda h: re.sub(r'<label class="gl-opt"><input type="radio" name="verdict" value="suggest">.*?</label>', '', h, count=1, flags=re.S), 'verdict'),
        ('consent text changed', full, lambda h: _in_content(h, 'أوافق على ظهور اسمي مع المصطلح بعد اعتماد مراجعتي', 'أوافق'), 'the text'),
        ('privacy line dropped', full, lambda h: _in_content(h, 'لا نعرض بريدك، ونستعمله للتواصل بشأن مراجعتك فقط.', ''), 'the text'),
        ('review script missing', full, lambda h: h.replace('<script id="epGlossaryReviewJs">', '<script id="x">', 1), 'review script'),
        ('review script tracks', full, lambda h: h.replace('<script id="epGlossaryReviewJs">\n', '<script id="epGlossaryReviewJs">\nfbq("track","Lead");\n', 1), 'tracking'),
        ('review script uses local storage', full, lambda h: h.replace('<script id="epGlossaryReviewJs">\n', '<script id="epGlossaryReviewJs">\nlocalStorage.x=1;\n', 1), 'tracking'),
        ('review script sends credentials', full, lambda h: _in_review_js(h, "credentials:'omit'", "credentials:'include'"), 'without credentials'),
        ('review script twice', full, lambda h: h.replace('</body>', '<script id="epGlossaryReviewJs">\n1</script></body>', 1), 'review script'),
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
    idx = built['pages']['index']
    cases = (
        ('item data-st flipped', idx.replace('<li data-st="under_review"><a href="/glossary/offer.html">', '<li data-st="confirmed"><a href="/glossary/offer.html">', 1), 'marked data-st'),
        ('item data-st invalid', idx.replace('<li data-st="confirmed">', '<li data-st="published">', 1), 'marked data-st'),
        ('mark text wrong', idx.replace('<span class="gl-l-st is-w">تحت التأكيد</span>', '<span class="gl-l-st is-w">مؤكّد</span>', 1), 'visible mark'),
        ('mark class wrong', idx.replace('<span class="gl-l-st is-c">مؤكّد</span>', '<span class="gl-l-st is-w">مؤكّد</span>', 1), 'visible mark'),
        ('mark missing', idx.replace('<span class="gl-l-st is-c">مؤكّد</span>', '', 1), 'mark'),
        ('mark doubled', idx.replace('<span class="gl-l-st is-c">مؤكّد</span>', '<span class="gl-l-st is-c">مؤكّد</span><span class="gl-l-st is-c">مؤكّد</span>', 1), 'mark'),
        ('item data-st dropped', idx.replace('<li data-st="under_review">', '<li>', 1), 'state mark'),
        ('filter removed', re.sub(r'(?s)<div class="gl-filter".*?</div>', '', idx, count=1), 'filter chips'),
        ('filter count wrong', idx.replace('data-gl-f="confirmed" aria-pressed="false">مؤكّد <span class="n">٢</span>', 'data-gl-f="confirmed" aria-pressed="false">مؤكّد <span class="n">٣</span>', 1), 'filter chips'),
        ('filter chip pressed wrongly', idx.replace('data-gl-f="all" aria-pressed="true"', 'data-gl-f="all" aria-pressed="false"', 1), 'filter chips'),
        ('filter chip renamed', idx.replace('data-gl-f="under_review"', 'data-gl-f="pending"', 1), 'filter chips'),
        ('filter script missing', idx.replace('<script id="epGlossaryFilterJs">', '<script id="x">', 1), 'filter script'),
        ('filter script tracks', idx.replace('<script id="epGlossaryFilterJs">\n', '<script id="epGlossaryFilterJs">\ngtag("event","x");\n', 1), 'tracking'),
        ('search box beside the chips', idx.replace('<nav class="gl-areas"', '<select></select><nav class="gl-areas"', 1), 'search box'),
    )
    for name, html, needle in cases:
        assert html != idx, name + ': the mutation did not change the page'
        errs = _index_errs(built, html)
        assert errs and any(needle.lower() in e.lower() for e in errs), (name, errs[:3])


@needs_site
def test_index_with_chips_when_every_term_has_one_state_fails(built, tmp_path):
    terms = [PLAIN, UNREV_WITH_NOTE]
    summary, pages = pr.glossary_step(SITE_DIR, _gfile(str(tmp_path), feed_of(*terms)))
    idx = next(h for p_, h in pages.items() if p_.endswith('index.html'))
    chip = '<div class="gl-filter" role="group" data-gl-filter><button type="button" class="chip" data-gl-f="all" aria-pressed="true">الكل <span class="n">٢</span></button></div>'
    bad = idx.replace('<nav class="gl-areas"', chip + '<nav class="gl-areas"', 1)
    errs = pr.verify_glossary_index(bad, terms, None, built['index_tpl'])
    assert errs and any('filter chips appear' in e for e in errs)


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
    gf = _gfile(tmp, feed_of(FULL, PLAIN, UNREV_WITH_NOTE))
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', gf)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert out['glossary']['state'] == 'ok' and out['glossary']['terms'] == 3
    assert _glossary_files(tmp) == ['consideration.html', 'estoppel.html', 'index.html', 'offer.html']
    assert all(re.match(r'^[a-z0-9.-]+$', n) for n in _glossary_files(tmp))              # أسماء ASCII
    full = _read(os.path.join(tmp, 'glossary', 'consideration.html'))
    offer = _read(os.path.join(tmp, 'glossary', 'offer.html'))
    assert 'راجعه: <b><bdi>أ. هبة الجندي</bdi>، <bdi>محامية</bdi></b>' in full and pr.SAHA_LINK_PREFIX + TID + '"' in full
    assert 'راجعه' not in _block(offer) and pr.SAHA_LINK_PREFIX not in _block(offer)
    assert os.path.isfile(os.path.join(tmp, 'blog', '_pre', '%s.html' % json.loads(article_feed)['articles'][0]['id']))   # والمقالات كالمعتاد


def _cli_state_feed():
    under = term('delay', ar='التأخير', en='delay', fr=None, countries_note_ar='ملاحظة بلاد لا تظهر.')
    named = term('breach', ar='الإخلال', en='breach', example_en=None, example_ar=None, review_state='confirmed', reviewed_at='2026-11-01T09:00:00',
                 reviewed_by_name='أ. سلمى & <b>الشريك</b> 2', reviewed_by_role='محكّمة منذ 15 سنة',
                 countries_note_ar='في الأردن 3 أنظمة و0.5% رسم.')
    anon = term('waiver', ar='التنازل', en='waiver', fr=None, review_state='confirmed', reviewed_at='2026-11-01T09:00:00',
                countries_note_ar='يُسمّى «الإسقاط» في بعض البلاد.')
    return under, named, anon


@needs_site
def test_cli_end_to_end_the_three_states_under_review_named_and_anonymous(article_feed, tmp_path):
    tmp = _site(str(tmp_path))
    under, named, anon = _cli_state_feed()
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(under, named, anon)))
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert out['glossary']['state'] == 'ok' and out['glossary']['terms'] == 3
    u, n, a, idx = (_read(os.path.join(tmp, 'glossary', f + '.html')) for f in ('delay', 'breach', 'waiver', 'index'))
    badge = 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح'
    # تحت التأكيد: شارة، بلا مراجع ولا ملاحظة بلاد، ونموذج واحد
    assert _block(u).count(badge) == 1 and 'راجعه' not in _block(u) and 'class="gl-country"' not in _block(u) and 'ملاحظة بلاد لا تظهر' not in u
    # مؤكّد باسم: الاسم يمرّ بالتهريب والأرقام هندية، وملاحظة البلاد تظهر بأرقام هندية
    assert badge not in _block(n)
    assert 'راجعه: <b><bdi>أ. سلمى &amp; &lt;b&gt;الشريك&lt;/b&gt; ٢</bdi>، <bdi>محكّمة منذ ١٥ سنة</bdi></b>' in _block(n)
    assert 'في الأردن ٣ أنظمة و٠٫٥٪ رسم.' in _block(n) and '<b>الشريك</b>' not in n
    assert not re.search(r'[0-9]', pr.strip_to_text(_block(n)))                                        # لا رقم لاتيني في النص الظاهر
    # مؤكّد بلا اسم: «راجعه متخصص» وملاحظة البلاد
    assert _block(a).count('راجعه متخصص') == 1 and 'راجعه:' not in _block(a) and badge not in _block(a)
    assert 'يُسمّى «الإسقاط» في بعض البلاد.' in _block(a)
    for html in (u, n, a):
        b = _block(html)
        assert b.count('<form') == 1 and b.count('name="website"') == 1 and 'api/public/expert-reviews' in b
    # الفهرس: علامات وأزرار تصفية
    assert idx.count('class="gl-l-st is-c">مؤكّد<') == 2 and idx.count('class="gl-l-st is-w">تحت التأكيد<') == 1 and 'data-gl-filter' in idx


@needs_site
def test_cli_unknown_or_missing_review_state_is_an_error_and_writes_nothing(article_feed, tmp_path):
    tmp = _site(str(tmp_path))
    for bad in ('published', 'draft', 'Confirmed'):
        proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(PLAIN, term('zz1', review_state=bad))))
        assert proc.returncode == 0 and out['glossary']['state'] == 'error' and 'review_state' in out['glossary']['error'], bad
        assert _glossary_files(tmp) == []
    t = term('zz2')
    del t['review_state']
    proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(t)))
    assert out['glossary']['state'] == 'error' and 'review_state' in out['glossary']['error'] and _glossary_files(tmp) == []


@needs_site
def test_cli_a_template_that_drops_the_review_form_or_the_badge_writes_no_glossary_page(article_feed, tmp_path):
    def drop_form(tmp):
        p = os.path.join(tmp, 'glossary-term.html')
        s = _read(p)
        assert "<form class=\"gl-form\" data-gl-review" in s and "'</form></details>" in s
        _write(p, s.replace('<form class="gl-form" data-gl-review', '<div class="gl-form" data-gl-review').replace("'</form></details>", "'</div></details>"))

    def drop_badge(tmp):
        p = os.path.join(tmp, 'glossary-term.html')
        s = _read(p)
        assert 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح' in s
        _write(p, s.replace('تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح', 'قيد النظر'))
    for tweak in (drop_form, drop_badge):
        d = tmp_path / tweak.__name__
        d.mkdir()
        tmp = _site(str(d), tweak=tweak)
        proc, out = _cli(tmp, article_feed, '--glossary-feed-file', _gfile(tmp, feed_of(PLAIN)))
        assert proc.returncode == 0 and out['glossary']['state'] == 'error' and 'verification failure' in out['glossary']['error'], tweak.__name__
        assert _glossary_files(tmp) == [] and out['files_written'] > 30


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


# ——————————————————————————————————————————————— ٢ب) المتصفح: النموذج والتصفية (playwright محلي، كل طلب خارجي مجهَض)

@needs_site
def test_browser_review_form_and_index_filter_with_a_fake_fetch():
    """tests/uiharness/glossary_review_form.py: يتحقق في كروميوم حقيقي من النموذج (تحقق، جسم JSON حرفي، ٢٠١/٤٠٠/٤٢٩/٤٠٤/انقطاع،
    فخّ الروبوتات، الأهداف)، ومن علامات الفهرس وأزرار التصفية، وبلا JS. fetch مبدَّلة وأي مضيف خارجي يُجهَض. خروج ٧٧ = لا متصفح هنا."""
    proc = subprocess.run([sys.executable, '-B', os.path.join(_HERE, 'uiharness', 'glossary_review_form.py'), SITE_DIR],
                          capture_output=True, text=True, timeout=300)
    if proc.returncode == 77:
        pytest.skip('no browser in this environment')
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-1500:]


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
