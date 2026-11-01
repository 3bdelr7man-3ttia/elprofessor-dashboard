# -*- coding: utf-8 -*-
"""«ناقشها في الساحة» من محرّر المقال (docs/v2/saha-link/SPEC.md).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_saha_link.py

⛔ صفر شبكة حقيقية وصفر نداء حقيقي: جسر المنصة بديل في الذاكرة (`FakeBridge`)، وأي عنوان برّه `https://platform.test` يوقّع الاختبار.
`_prerender_push_async` متبدّلة بدالة تسجّل السبب (ولا SFTP). القالب الحقيقي من ريبو الموقع (EP_SITE_REPO) وهو الفرع `site-saha-link`؛
والقالب القديم (قبل الزرّ) يُشتقّ منه بقصّ كتلة الزرّ — فنفس الملف يُختبر بالحالتين.

اللي بيثبّته:
  ١. verify_article: المقال بالزرّ وبدونه مقبول مع القالب الجديد والقديم · العيب وحده يفشل (زرّ ناقص · رابط بلا معرّف) · عدّ وسوم التتبّع ثابت.
  ٢. prerender طرفي (سطر الأوامر) بقالب قديم وجديد: الصفحة تحمل الزرّ لمقال له معرّف فقط، وغيره بلا أي أثر.
  ٣. الفيد (`/api/content/articles` و`_prerender_feed_json`) يحمل `saha_topic_id`، و`PUT` المقال العام لا يكتبه.
  ٤. المسار: أدمن بس · المفتاح · التأكيد قبل أي نداء · مقال منشور · لا تكرار · تبنّي نقاش موجود · الرد الضايع · نصف الفتح · الفصل.
"""
import copy
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import jwt
import pytest
from werkzeug.security import generate_password_hash

import app as appmod  # noqa: E402
from app import app as flask_app, db, User, AuditLog, Article  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(_HERE)
ROOT = os.path.dirname(BACKEND)
SITE_DIR = os.path.expanduser(os.environ.get('EP_SITE_REPO', '~/elprofessor-site'))
PRERENDER = os.path.join(BACKEND, 'prerender.py')
sys.path.insert(0, BACKEND)
import prerender as pr  # noqa: E402

PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
LONG = ('هذا نص تجريبي طويل يشرح المبدأ القانوني بالتفصيل ويعطي القارئ خطوات عملية واضحة. ' * 12).strip()
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
TID = 'c0ffee00-1111-4222-8333-444455556666'
TID2 = 'deadbeef-1111-4222-8333-444455556666'

HAS_NODE = bool(shutil.which('node'))
TPL_PATH = os.path.join(SITE_DIR, 'article.html')
HAS_SITE = os.path.isfile(TPL_PATH) and os.path.isfile(os.path.join(SITE_DIR, 'blog.html'))
needs_site = pytest.mark.skipif(not (HAS_NODE and HAS_SITE), reason='needs node + the marketing-site repo (EP_SITE_REPO)')


def _tpl():
    with open(TPL_PATH, encoding='utf-8') as fh:
        return fh.read()


NEW_TPL = bool(HAS_NODE and HAS_SITE and 'saha_topic_id' in _tpl())
needs_new_tpl = pytest.mark.skipif(not NEW_TPL, reason='the site checkout is not on the branch with the «ناقشها في الساحة» button (site-saha-link)')


def old_template(new):
    """القالب قبل الزرّ: نقصّ كتلة الزرّ (تعليقاها + شرطها) من الجديد."""
    out = re.sub(r"\n    // «ناقشها في الساحة».*?':''\)\+\n", "\n", new, count=1, flags=re.S)
    assert 'saha_topic_id' not in out
    return out


# ——————————————————————————————————————————————— مقالات وأدوات

def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if u:
        u.role = role
        u.dashboard_role = role
        u.is_active = True
        db.session.commit()
        return u
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role, dashboard_role=role,
             linked_to_name='', preferred_currency='AUTO', is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


def _pub(title, status='published', saha=None, image=None, excerpt='مقتطف عن المسألة', days=0):
    a = Article(title=title, excerpt=excerpt, cat='دليل', kicker='دليل', by='فريق منصة البروفيسور', date='١ أكتوبر ٢٠٢٦',
                body=json.dumps(['## ' + title, LONG, LONG], ensure_ascii=False), keywords='[]', faq='[]', target_audience='المحامون',
                status=status, image_url=image, saha_topic_id=saha,
                published_at=(datetime.datetime(2026, 9, 1) + datetime.timedelta(days=days)) if status == 'published' else None)
    db.session.add(a)
    db.session.commit()
    return a


@pytest.fixture
def ctx():
    with flask_app.app_context():
        db.create_all()
        Article.query.delete()
        AuditLog.query.filter(db.or_(AuditLog.action.like('article.saha%'), AuditLog.action.like('saha_link%'))).delete(synchronize_session=False)
        db.session.commit()
        heads = {r: _bearer(_mkuser('saha-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser('saha-admin@x.test', 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}
        Article.query.delete()
        db.session.commit()


# ——————————————————————————————————————————————— ١) verify_article

def _pipeline(tpl, articles):
    """نفس خطوات main() في prerender.py: تشغيل مُصيِّر القالب في node ثم البناء ثم التحقق. يرجع {id: (html, errs, art)}."""
    art_tpl = tpl
    with open(os.path.join(SITE_DIR, 'blog.html'), encoding='utf-8') as fh:
        blog_doc = fh.read()
    article_code = pr.extract_inline(art_tpl, '</script>\n<script src="/content-loader.js', 'article.html')
    blog_code = pr.extract_inline(blog_doc, '</script>\n<script src="content-loader.js', 'blog.html')
    soft = re.search(r"var nfTitle=DATA\.length\?'([^']*)':'([^']*)'", article_code)
    c = {
        'renderer_has_faq': 'faqHtml' in article_code,
        'renderer_has_topic': 'topic_slug' in article_code,
        'renderer_has_saha': 'saha_topic_id' in article_code,
        'soft404': list(soft.groups()) if soft else [],
        'placeholder': pr.unique_line(art_tpl, r'^<title>.*</title>$', 'title')[len('<title>'):-len('</title>')],
    }
    res = pr.run_node(article_code, blog_code, articles, 'dashboard')
    out = {}
    for a in articles:
        r = res['articles'][str(a['id'])]
        html, meta = pr.build_article(art_tpl, a, r)
        errs, _n = pr.verify_article(html, a, r, meta, c)
        out[str(a['id'])] = (html, errs, r, meta, c)
    return out


def _feed_articles(*specs):
    """مقالات من الدفتر بشكل الفيد: specs = [(title, saha_topic_id|None)]."""
    for i, (title, saha) in enumerate(specs):
        _pub(title, saha=saha, days=i)
    return json.loads(appmod._prerender_feed_json())['articles']


def _art_part(html):
    """ما رُسم فعلًا داخل #art (نص القالب نفسه يحمل بادئة الرابط داخل سكربت المُصيِّر، فلا يُعدّ على الصفحة كلها)."""
    return html.split('<article class="art" id="art">', 1)[1].split('</article>', 1)[0]


TRACK_PATTERNS = (pr.GTM_ID, 'googletagmanager.com/ns.html', '/pixel.js?v=', 'facebook.com/tr?id=', 'EP_PRERENDERED', '<script')


@needs_site
def test_old_template_accepts_articles_with_and_without_topic_and_renders_no_button(ctx):
    arts = _feed_articles(('مقال بنقاش', TID), ('مقال بلا نقاش', None))
    out = _pipeline(old_template(_tpl()), arts)
    for aid, (html, errs, r, _m, c) in out.items():
        assert errs == [], errs
        assert c['renderer_has_saha'] is False
        assert pr.SAHA_LINK_PREFIX not in html and 'page=saha' not in r['art'], 'قالب قديم: لا زرّ'


@needs_new_tpl
def test_new_template_renders_the_button_only_for_an_article_with_a_topic_and_verifies_both(ctx):
    arts = _feed_articles(('مقال بنقاش', TID), ('مقال بلا نقاش', None))
    out = _pipeline(_tpl(), arts)
    with_id = [v for a, v in zip(arts, [out[str(a['id'])] for a in arts]) if a['saha_topic_id']][0]
    no_id = [out[str(a['id'])] for a in arts if not a['saha_topic_id']][0]
    html, errs, r, _m, c = with_id
    assert errs == [] and c['renderer_has_saha'] is True
    assert r['art'].count(pr.SAHA_LINK_PREFIX + TID + '"') == 1 and r['art'].count('ناقشها في الساحة') == 1
    assert 'class="saha-btn"' in r['art'] and _art_part(html).count(pr.SAHA_LINK_PREFIX) == 1
    html2, errs2, r2, _m2, _c2 = no_id
    assert errs2 == [] and 'saha' not in r2['art'] and pr.SAHA_LINK_PREFIX not in _art_part(html2)


@needs_new_tpl
@pytest.mark.parametrize('bad', ['', 'short', 'has space in it', 'x' * 65, 'a/b/c/d/e/f', '<script>alert(1)</script>', 'ok-id-but-"quote"'])
def test_new_template_ignores_a_malformed_topic_id_and_verify_still_passes(ctx, bad):
    arts = json.loads(json.dumps(_feed_articles(('مقال بمعرّف فاسد', None))))
    arts[0]['saha_topic_id'] = bad
    html, errs, r, _m, _c = list(_pipeline(_tpl(), arts).values())[0]
    assert errs == [] and 'page=saha' not in r['art'] and 'saha-btn' not in r['art']


@needs_new_tpl
def test_verify_fails_on_the_real_defects_only(ctx):
    arts = _feed_articles(('مقال بنقاش', TID), ('مقال بلا نقاش', None))
    by_id = {str(a['id']): a for a in arts}
    out = _pipeline(_tpl(), arts)
    wid = [i for i, a in by_id.items() if a['saha_topic_id']][0]
    nid = [i for i, a in by_id.items() if not a['saha_topic_id']][0]

    # ١) الزرّ مفقود من مقال له معرّف
    html, _e, r, meta, c = out[wid]
    r2 = dict(r, art=re.sub(r'<div class="saha">.*?</div></div>', '', r['art'], flags=re.S))
    errs, _n = pr.verify_article(html.replace(r['art'], r2['art']), by_id[wid], r2, meta, c)
    assert any('saha button' in e for e in errs), errs
    # ٢) رابط نقاش خاطئ (معرّف آخر)
    r3 = dict(r, art=r['art'].replace(TID, TID2))
    errs, _n = pr.verify_article(html.replace(r['art'], r3['art']), by_id[wid], r3, meta, c)
    assert any('saha button' in e for e in errs), errs
    # ٣) زرّ مكرّر
    r4 = dict(r, art=r['art'] + r['art'][r['art'].index('<div class="saha">'):r['art'].index('<div class="saha">') + 300])
    errs, _n = pr.verify_article(html + 'x', by_id[wid], r4, meta, c)
    assert any('saha' in e for e in errs), errs
    # ٤) رابط نقاش في مقال بلا معرّف
    html0, _e0, r0, meta0, c0 = out[nid]
    leak = dict(r0, art=r0['art'] + '<a href="%s%s">x</a>' % (pr.SAHA_LINK_PREFIX, TID))
    errs, _n = pr.verify_article(html0, by_id[nid], leak, meta0, c0)
    assert any('no valid saha_topic_id' in e for e in errs), errs
    # ٥) سكربت تسرّب داخل #art
    sc = dict(r0, art=r0['art'] + '<script>1</script>')
    errs, _n = pr.verify_article(html0, by_id[nid], sc, meta0, c0)
    assert any('<script> leaked' in e for e in errs), errs


@needs_new_tpl
def test_old_verify_contract_template_without_the_field_is_not_asked_for_a_button(ctx):
    """القالب القديم + مقال له معرّف: لا يُطلب زرّ (هذا ما يجعل ترتيب النشر آمنًا: verify_article أولًا ثم القالب)."""
    arts = _feed_articles(('مقال بنقاش', TID))
    out = _pipeline(old_template(_tpl()), arts)
    html, errs, r, _m, c = list(out.values())[0]
    assert errs == [] and c['renderer_has_saha'] is False and 'saha' not in r['art']


@needs_new_tpl
def test_button_adds_no_tracking_tags_counts_identical(ctx):
    a = _feed_articles(('مقال بمعرّف فاسد', None))
    with_id = json.loads(json.dumps(a))
    with_id[0]['saha_topic_id'] = TID
    h_no = list(_pipeline(_tpl(), a).values())[0][0]
    h_yes = list(_pipeline(_tpl(), with_id).values())[0][0]
    assert h_yes != h_no and pr.SAHA_LINK_PREFIX in _art_part(h_yes)
    for pat in TRACK_PATTERNS:
        assert h_yes.count(pat) == h_no.count(pat), pat
    # القالب القديم يطابق الجديد بلا معرّف حرفًا بحرف في كل ما عدا CSS الزرّ نفسه
    h_old = list(_pipeline(old_template(_tpl()), a).values())[0][0]
    for pat in TRACK_PATTERNS:
        assert h_old.count(pat) == h_no.count(pat), pat


# ——————————————————————————————————————————————— ٢) طرفي: prerender.py بسطر الأوامر

def _run_prerender(tmp, tpl_text, feed):
    for name in ('blog.html',):
        shutil.copy(os.path.join(SITE_DIR, name), os.path.join(tmp, name))
    with open(os.path.join(tmp, 'article.html'), 'w', encoding='utf-8') as fh:
        fh.write(tpl_text)
    os.makedirs(os.path.join(tmp, 'blog', '_pre'), exist_ok=True)
    os.makedirs(os.path.join(tmp, 'blog', '_topic'), exist_ok=True)
    ff = os.path.join(tmp, '_feed.json')
    with open(ff, 'w', encoding='utf-8') as fh:
        fh.write(feed)
    return subprocess.run(['python3', PRERENDER, '--site', tmp, '--feed-file', ff, '--min-articles', '1'], capture_output=True, text=True, timeout=300)


def _seed_many(with_topic_id):
    ids = {}
    for i in range(30):   # blog.html's verifier wants a realistically full index (≥5000 chars)
        _pub('مقال تحليلي عن موضوع قانوني رقم %d' % i, excerpt=LONG[:160], days=i)
    ids['with'] = _pub('مقال له نقاش في الساحة', saha=with_topic_id, days=40).id
    ids['without'] = _pub('مقال بلا نقاش في الساحة', days=41).id
    return ids


@needs_site
@pytest.mark.parametrize('which', ['old', 'new'])
def test_prerender_end_to_end_writes_pages_with_and_without_the_button(ctx, which):
    tpl = _tpl()
    if which == 'old':
        tpl = old_template(tpl)
    elif 'saha_topic_id' not in tpl:
        pytest.skip('the site checkout is not on site-saha-link')
    ids = _seed_many(TID)
    tmp = tempfile.mkdtemp(prefix='prerender-saha-')
    try:
        proc = _run_prerender(tmp, tpl, appmod._prerender_feed_json())
        assert proc.returncode == 0, proc.stderr[-2000:]
        pre = os.path.join(tmp, 'blog', '_pre')
        with_page = open(os.path.join(pre, '%d.html' % ids['with']), encoding='utf-8').read()
        without_page = open(os.path.join(pre, '%d.html' % ids['without']), encoding='utf-8').read()
        assert pr.SAHA_LINK_PREFIX not in _art_part(without_page) and 'saha-btn' not in _art_part(without_page)
        if which == 'new':
            assert _art_part(with_page).count(pr.SAHA_LINK_PREFIX + TID + '"') == 1 and _art_part(with_page).count('ناقشها في الساحة') == 1
            assert re.search(r'<a class="saha-btn" href="https://app\.elprofessor\.net/\?page=saha&amp;topic=%s">ناقشها في الساحة</a>' % TID, with_page)
        else:
            assert pr.SAHA_LINK_PREFIX not in _art_part(with_page) and pr.SAHA_LINK_PREFIX not in with_page
        # عدّ وسوم التتبّع ثابت بين الصفحتين (الزرّ لا يضيف وسمًا)
        for pat in ('googletagmanager.com/ns.html', '/pixel.js?v=', 'facebook.com/tr?id=', 'window.EP_PRERENDERED=true'):
            assert with_page.count(pat) == without_page.count(pat), pat
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@needs_new_tpl
def test_prerender_dry_run_with_the_new_template_and_a_field_less_feed_is_unchanged(ctx):
    """فيد قديم بلا الحقل أصلًا (الداشبورد القديم) + القالب الجديد: لا زرّ ولا فشل."""
    ids = _seed_many(None)
    feed = json.loads(appmod._prerender_feed_json())
    for a in feed['articles']:
        a.pop('saha_topic_id', None)
    tmp = tempfile.mkdtemp(prefix='prerender-saha-')
    try:
        proc = _run_prerender(tmp, _tpl(), json.dumps(feed, ensure_ascii=False))
        assert proc.returncode == 0, proc.stderr[-2000:]
        page = open(os.path.join(tmp, 'blog', '_pre', '%d.html' % ids['with']), encoding='utf-8').read()
        assert 'page=saha' not in _art_part(page)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ——————————————————————————————————————————————— ٣) الفيد

def test_feed_carries_saha_topic_id_and_null_otherwise(ctx):
    a = _pub('مقال بنقاش', saha=TID, days=0)
    b = _pub('مقال بلا نقاش', days=1)
    _pub('مسودة بنقاش', status='draft', saha=TID2)
    rows = {x['id']: x for x in ctx['client'].get('/api/content/articles').get_json()['articles']}
    assert rows[a.id]['saha_topic_id'] == TID and rows[b.id]['saha_topic_id'] is None
    assert len(rows) == 2, 'المسودة لا تظهر في الفيد'
    feed = {x['id']: x for x in json.loads(appmod._prerender_feed_json())['articles']}
    assert feed[a.id]['saha_topic_id'] == TID and feed[b.id]['saha_topic_id'] is None
    allr = {x['id']: x for x in ctx['client'].get('/api/content/articles/all', headers=ctx['heads']['admin']).get_json()['articles']}
    assert allr[a.id]['saha_topic_id'] == TID
    summ = ctx['client'].get('/api/content/articles?fields=summary').get_json()['articles'][0]
    assert 'saha_topic_id' not in summ, 'الملخّص للقوائم لا يحمل الحقل'


def test_the_general_article_put_cannot_write_the_field(ctx, monkeypatch):
    monkeypatch.setattr(appmod, '_prerender_push_async', lambda reason='': {'state': 'x'})
    a = _pub('مقال', days=0)
    r = ctx['client'].put('/api/content/articles/%d' % a.id, json={'title': 'مقال معدّل', 'saha_topic_id': TID}, headers=ctx['heads']['admin'])
    assert r.status_code == 200 and r.get_json()['saha_topic_id'] is None
    assert db.session.get(Article, a.id).saha_topic_id is None


# ——————————————————————————————————————————————— ٤) المسار

class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else b''
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        return self._p


class FakeBridge(object):
    """جسر المنصة بديل في الذاكرة: `/api/bridge/topics` (قراءة · إنشاء) و`/publish`. أعطال تُضبط من الاختبار."""

    def __init__(self):
        self.topics = []
        self.seen = []
        self.blocked = []
        self.list_status = 200
        self.create_mode = 'ok'          # ok | lost_after_create | lost_before_create | reject
        self.publish_mode = 'ok'         # ok | lost | reject

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None, data=None, files=None):
        path = url[len(PLATFORM):] if url.startswith(PLATFORM) else url
        self.seen.append({'method': method.upper(), 'url': url, 'path': path, 'headers': dict(headers or {}), 'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        m = method.upper()
        if path == '/api/bridge/topics' and m == 'GET':
            if self.list_status != 200:
                return _Resp(self.list_status, {'detail': 'تعذر'})
            return _Resp(200, copy.deepcopy(self.topics))
        if path == '/api/bridge/topics' and m == 'POST':
            if self.create_mode == 'lost_before_create':
                return _Resp(504, {'detail': 'timeout'})
            if self.create_mode == 'reject':
                return _Resp(422, {'detail': 'رابط الغلاف لازم يبدأ بـ https'})
            row = {'id': 'new-%08d-0000-4000-8000-000000000000' % (len(self.topics) + 1), 'title': json['title'], 'question': json['question'], 'status': 'draft',
                   'source_article_slug': json.get('source_article_slug'), 'cover_url': json.get('cover_url', '')}
            self.topics.append(row)
            if self.create_mode == 'lost_after_create':
                return _Resp(504, {'detail': 'timeout'})
            return _Resp(200, copy.deepcopy(row))
        mm = re.match(r'^/api/bridge/topics/([^/]+)/publish$', path)
        if mm and m == 'POST':
            if self.publish_mode == 'lost':
                return _Resp(503, {'detail': 'down'})
            if self.publish_mode == 'reject':
                return _Resp(404, {'detail': 'Topic not found'})
            for t in self.topics:
                if t['id'] == mm.group(1):
                    t['status'] = 'published'
                    return _Resp(200, copy.deepcopy(t))
            return _Resp(404, {'detail': 'Topic not found'})
        return _Resp(404, {'detail': 'no route'})

    def writes(self):
        return [c for c in self.seen if c['method'] != 'GET']


@pytest.fixture
def plat(monkeypatch):
    p = FakeBridge()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    p.pushes = []
    monkeypatch.setattr(appmod, '_prerender_push_async', lambda reason='': p.pushes.append(reason) or {'state': 'started'})
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


def _open(ctx, aid, body=None, role='admin'):
    kw = {'headers': ctx['heads'][role] if role else {}}
    kw['json'] = {'confirmed': True} if body is None else body
    return ctx['client'].post('/api/v2/content/articles/%s/saha-topic' % aid, **kw)


def _detach(ctx, aid, body=None, role='admin'):
    kw = {'headers': ctx['heads'][role] if role else {}}
    kw['json'] = {'confirmed': True} if body is None else body
    return ctx['client'].post('/api/v2/content/articles/%s/saha-topic/detach' % aid, **kw)


def _stored(aid):
    db.session.expire_all()
    return db.session.get(Article, aid).saha_topic_id


def _audits(prefix, aid):
    """سطور التدقيق لمقالٍ بعينه (الجدول يتراكم عبر الاختبارات)."""
    return [(a.action, a.target, json.loads(a.meta_json or 'null'), a.actor_email)
            for a in AuditLog.query.filter(AuditLog.action.like(prefix + '%'), AuditLog.target == str(aid)).order_by(AuditLog.id).all()]


@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
def test_only_admin_may_open_or_detach(ctx, plat, role):
    a = _pub('مقال')
    for fn in (_open, _detach):
        r = fn(ctx, a.id, role=role)
        assert r.status_code == 403, (role, fn.__name__, r.status_code)
    assert plat.seen == [] and _stored(a.id) is None


def test_no_token_is_401(ctx, plat):
    a = _pub('مقال')
    assert _open(ctx, a.id, role=None).status_code == 401 and _detach(ctx, a.id, role=None).status_code == 401
    assert plat.seen == []


def test_closed_flag_is_404_and_no_call(ctx, plat, monkeypatch):
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    a = _pub('مقال')
    assert _open(ctx, a.id).status_code == 404 and _detach(ctx, a.id).status_code == 404
    assert plat.seen == [] and _stored(a.id) is None


@pytest.mark.parametrize('body', [{}, {'confirmed': False}, {'confirmed': 'true'}, {'confirmed': 1}, {'title': 'عنوان صالح'}])
def test_confirmation_is_required_before_any_call(ctx, plat, body):
    a = _pub('مقال')
    r = _open(ctx, a.id, body)
    assert r.status_code == 400 and r.get_json()['error'] == CONFIRM_AR
    assert plat.seen == [] and _stored(a.id) is None and _audits('article.saha', a.id) == []
    b = _pub('مقال آخر', saha=TID)
    r = _detach(ctx, b.id, body)
    assert r.status_code == 400 and r.get_json()['error'] == CONFIRM_AR and _stored(b.id) == TID


def test_missing_and_draft_articles_are_refused_without_a_call(ctx, plat):
    assert _open(ctx, 987654).status_code == 404
    d = _pub('مسودة', status='draft')
    r = _open(ctx, d.id)
    assert r.status_code == 409 and 'انشر المقال' in r.get_json()['error']
    assert plat.seen == [] and _stored(d.id) is None


def test_open_creates_publishes_stores_audits_and_regenerates_pages(ctx, plat):
    a = _pub('هل يكفي التوكيل العام لرفع الدعوى؟', image='https://img.example.test/cover.jpg', excerpt='سؤال يتكرر أمام المحاكم')
    r = _open(ctx, a.id)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    tid = body['saha_topic_id']
    assert body['ok'] is True and body['adopted'] is False and body['url'] == 'https://app.elprofessor.net/?page=saha&topic=' + tid
    assert r.headers.get('Cache-Control') == 'no-store'
    assert [(c['method'], c['path']) for c in plat.seen] == [('GET', '/api/bridge/topics'), ('POST', '/api/bridge/topics'), ('POST', '/api/bridge/topics/%s/publish' % tid)]
    assert all(c['headers'].get('X-ELP-Metrics-Secret') == SECRET for c in plat.seen)
    create = plat.seen[1]['json']
    slug = appmod._article_slug(db.session.get(Article, a.id))
    assert create == {'title': 'هل يكفي التوكيل العام لرفع الدعوى؟', 'question': 'سؤال يتكرر أمام المحاكم', 'source': 'human', 'source_article_slug': slug,
                      'cover_url': 'https://img.example.test/cover.jpg'}
    assert _stored(a.id) == tid
    assert _audits('article.saha_open', a.id) == [('article.saha_open', str(a.id), {'topic_id': tid, 'adopted': False}, 'saha-admin@x.test')]
    assert plat.pushes == ['article-saha:%d' % a.id]
    # الفيد صار يحمل المعرّف
    feed = {x['id']: x for x in ctx['client'].get('/api/content/articles').get_json()['articles']}
    assert feed[a.id]['saha_topic_id'] == tid


def test_open_uses_the_editors_title_and_question_and_skips_a_non_https_cover(ctx, plat):
    a = _pub('عنوان المقال', image='http://img.example.test/cover.jpg', excerpt='مقتطف')
    r = _open(ctx, a.id, {'confirmed': True, 'title': '  عنوان النقاش  ', 'question': ' سؤال النقاش '})
    assert r.status_code == 200
    create = plat.seen[1]['json']
    assert create['title'] == 'عنوان النقاش' and create['question'] == 'سؤال النقاش' and 'cover_url' not in create
    assert set(create) == {'title', 'question', 'source', 'source_article_slug'}


@pytest.mark.parametrize('body,msg', [({'confirmed': True, 'title': 'ab'}, 'عنوان النقاش'), ({'confirmed': True, 'title': 'x' * 201}, 'عنوان النقاش'),
                                      ({'confirmed': True, 'title': 5}, 'عنوان النقاش'), ({'confirmed': True, 'question': '   '}, 'سؤال النقاش'),
                                      ({'confirmed': True, 'question': 'س' * 5001}, 'سؤال النقاش')])
def test_bad_title_or_question_is_400_before_any_call(ctx, plat, body, msg):
    a = _pub('مقال صالح')
    r = _open(ctx, a.id, body)
    assert r.status_code == 400 and msg in r.get_json()['error']
    assert plat.seen == [] and _stored(a.id) is None


def test_no_excerpt_and_no_question_is_400(ctx, plat):
    a = _pub('مقال بلا مقتطف', excerpt='')
    a.meta_description = None
    db.session.commit()
    r = _open(ctx, a.id)
    assert r.status_code == 400 and 'سؤال النقاش' in r.get_json()['error'] and plat.seen == []


def test_an_article_that_already_has_a_topic_is_409_no_call(ctx, plat):
    a = _pub('مقال', saha=TID)
    r = _open(ctx, a.id)
    assert r.status_code == 409 and 'نقاش مفتوح بالفعل' in r.get_json()['error']
    assert plat.seen == [] and _stored(a.id) == TID


def test_an_existing_public_topic_for_the_slug_is_adopted_without_any_write(ctx, plat):
    a = _pub('مقال')
    slug = appmod._article_slug(db.session.get(Article, a.id))
    plat.topics.append({'id': TID, 'title': 'نقاش سابق', 'status': 'open', 'source_article_slug': slug})
    plat.topics.append({'id': TID2, 'title': 'نقاش لمقال آخر', 'status': 'open', 'source_article_slug': 'other-slug-9'})
    r = _open(ctx, a.id)
    assert r.status_code == 200 and r.get_json()['adopted'] is True and r.get_json()['saha_topic_id'] == TID
    assert plat.writes() == [] and _stored(a.id) == TID
    assert _audits('article.saha_open', a.id)[0][2] == {'topic_id': TID, 'adopted': True}


def test_a_rejected_topic_for_the_slug_is_not_adopted(ctx, plat):
    a = _pub('مقال')
    slug = appmod._article_slug(db.session.get(Article, a.id))
    plat.topics.append({'id': TID, 'title': 'نقاش مرفوض', 'status': 'rejected', 'source_article_slug': slug})
    r = _open(ctx, a.id)
    assert r.status_code == 200 and r.get_json()['adopted'] is False and r.get_json()['saha_topic_id'] != TID
    assert [c['method'] for c in plat.writes()] == ['POST', 'POST']


def test_an_existing_draft_topic_is_published_not_recreated(ctx, plat):
    a = _pub('مقال')
    slug = appmod._article_slug(db.session.get(Article, a.id))
    plat.topics.append({'id': TID, 'title': 'مسودة سابقة', 'status': 'draft', 'source_article_slug': slug})
    r = _open(ctx, a.id)
    assert r.status_code == 200 and r.get_json()['adopted'] is True
    assert [(c['method'], c['path']) for c in plat.writes()] == [('POST', '/api/bridge/topics/%s/publish' % TID)]
    assert plat.topics[0]['status'] == 'published' and _stored(a.id) == TID


def test_lost_reply_on_create_is_502_no_reply_nothing_stored_and_the_retry_adopts_the_topic(ctx, plat):
    a = _pub('مقال')
    plat.create_mode = 'lost_after_create'
    r = _open(ctx, a.id)
    assert r.status_code == 502 and r.get_json()['no_reply'] is True and 'لم يصل رد' in r.get_json()['error']
    assert _stored(a.id) is None and plat.pushes == []
    assert [x[0] for x in _audits('saha_link', a.id)] == ['saha_link.no_reply'] and _audits('saha_link', a.id)[0][2] == {'attempt': 'create'}
    assert _audits('article.saha_open', a.id) == []
    assert len(plat.topics) == 1                       # المنصة أنشأته فعلًا والرد ضاع
    plat.create_mode = 'ok'
    n_before = len(plat.writes())
    r = _open(ctx, a.id)
    assert r.status_code == 200 and r.get_json()['adopted'] is True
    assert len(plat.topics) == 1, 'لا تكرار للنقاش'
    assert [(c['method'], c['path'].rsplit('/', 1)[-1]) for c in plat.writes()[n_before:]] == [('POST', 'publish')]
    assert _stored(a.id) == plat.topics[0]['id'] and plat.topics[0]['status'] == 'published'


def test_a_platform_refusal_on_create_passes_its_arabic_text_and_stores_nothing(ctx, plat):
    a = _pub('مقال', image='https://img.example.test/c.jpg')
    plat.create_mode = 'reject'
    r = _open(ctx, a.id)
    assert r.status_code == 422 and r.get_json()['error'] == 'رابط الغلاف لازم يبدأ بـ https' and 'no_reply' not in r.get_json()
    assert _stored(a.id) is None and _audits('article.saha', a.id) == [] and _audits('saha_link', a.id) == []


def test_half_open_publish_refused_stores_nothing_and_the_retry_finishes_the_draft(ctx, plat):
    a = _pub('مقال')
    plat.publish_mode = 'reject'
    r = _open(ctx, a.id)
    assert r.status_code == 502 and r.get_json()['partial'] is True and 'لم يُفتح للناس' in r.get_json()['error']
    assert _stored(a.id) is None and plat.pushes == [] and len(plat.topics) == 1 and plat.topics[0]['status'] == 'draft'
    plat.publish_mode = 'ok'
    r = _open(ctx, a.id)
    assert r.status_code == 200 and r.get_json()['adopted'] is True and len(plat.topics) == 1
    assert plat.topics[0]['status'] == 'published' and _stored(a.id) == plat.topics[0]['id']


def test_lost_reply_on_publish_is_no_reply_and_stores_nothing(ctx, plat):
    a = _pub('مقال')
    plat.publish_mode = 'lost'
    r = _open(ctx, a.id)
    assert r.status_code == 502 and r.get_json()['no_reply'] is True and _stored(a.id) is None
    assert _audits('saha_link', a.id)[0][2]['attempt'] == 'publish'


@pytest.mark.parametrize('status', [401, 403])
def test_a_platform_auth_refusal_on_the_read_is_masked_as_502_and_writes_nothing(ctx, plat, status):
    a = _pub('مقال')
    plat.list_status = status
    r = _open(ctx, a.id)
    assert r.status_code == 502 and r.get_json()['error'] == 'تعذّر الاتصال بالمنصة'
    assert plat.writes() == [] and _stored(a.id) is None


def test_a_failed_read_never_falls_through_to_a_create(ctx, plat):
    a = _pub('مقال')
    plat.list_status = 500
    r = _open(ctx, a.id)
    assert r.status_code >= 500 and plat.writes() == [] and _stored(a.id) is None


def test_detach_clears_the_id_audits_pushes_and_never_calls_the_platform(ctx, plat):
    a = _pub('مقال', saha=TID)
    r = _detach(ctx, a.id)
    assert r.status_code == 200 and r.get_json() == {'ok': True, 'saha_topic_id': None}
    assert plat.seen == [] and _stored(a.id) is None
    assert _audits('article.saha_detach', a.id) == [('article.saha_detach', str(a.id), {'topic_id': TID}, 'saha-admin@x.test')]
    assert plat.pushes == ['article-saha:%d' % a.id]
    feed = {x['id']: x for x in ctx['client'].get('/api/content/articles').get_json()['articles']}
    assert feed[a.id]['saha_topic_id'] is None
    r = _detach(ctx, a.id)
    assert r.status_code == 409 and 'لا نقاش' in r.get_json()['error']


def test_detach_then_open_again_adopts_the_old_discussion(ctx, plat):
    a = _pub('مقال')
    assert _open(ctx, a.id).status_code == 200
    tid = _stored(a.id)
    assert _detach(ctx, a.id).status_code == 200 and _stored(a.id) is None
    n = len(plat.writes())
    r = _open(ctx, a.id)
    assert r.status_code == 200 and r.get_json()['adopted'] is True and r.get_json()['saha_topic_id'] == tid
    assert len(plat.writes()) == n and len(plat.topics) == 1


def test_a_failing_page_regeneration_does_not_fail_the_save(ctx, plat, monkeypatch):
    a = _pub('مقال')

    def boom(reason=''):
        raise RuntimeError('sftp down')
    monkeypatch.setattr(appmod, '_prerender_push_async', boom)
    r = _open(ctx, a.id)
    assert r.status_code == 200 and _stored(a.id) == r.get_json()['saha_topic_id']


# ——————————————————————————————————————————————— ٥) الواجهة (نصوص ومواضع) + الحارس الأمني

def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


JS = _read('dashboard-cloud', 'v2s', 'content.js')


def test_editor_block_wording_endpoints_and_confirmation():
    for needle in ('افتح نقاشًا لهذا المقال', 'النقاش مفتوح', 'افصل', 'ناقشها في الساحة', 'راجع وافتح', 'افتح النقاش في الساحة',
                   "'/v2/content/articles/' + encodeURIComponent(raw.id) + '/saha-topic'", "/saha-topic/detach"):
        assert needle in JS, needle
    # كل نداء كتابة هنا يحمل confirmed:true ويمرّ على inlineConfirm/confirmSheet
    assert JS.count('confirmed: true') >= 3
    form = JS[JS.index('function sahaForm'):JS.index('function sahaDetach')]
    assert 'inlineConfirm(sheet' in form and form.index('inlineConfirm') < form.index('apiPost(')
    detach = JS[JS.index('function sahaDetach'):JS.index('function publishSite')]
    assert 'confirmSheet(' in detach and detach.index('confirmSheet') < detach.index('apiPost(')
    # الرابط يُرسم بمعرّف صالح فقط ومن safeLink (http/https)
    assert 'SAHA_ID.test(tid)' in JS and 'safeLink(SAHA_APP' in JS


def test_editor_copy_has_no_banned_words_and_no_dot_beside_a_digit():
    block = JS[JS.index('// —— «النقاش في الساحة»'):JS.index('function publishSite')]
    texts = re.findall(r"'([^']*[؀-ۿ][^']*)'", block)
    assert texts
    for t in texts:
        assert 'يقوّم' not in t and 'يقوم' not in t, t
        assert not re.search(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]', t), t
    for t in ('API', 'JSON', 'Claude', 'DeepSeek', 'bridge', 'token'):
        assert t not in ' '.join(texts), t


def test_dockerfile_ships_the_route_module():
    docker = _read('Dockerfile')
    assert 'COPY backend/v2_saha_link_routes.py /app/v2_saha_link_routes.py' in docker
    app_src = _read('backend', 'app.py')
    assert 'import v2_saha_link_routes as _v2s_saha_link; _v2s_saha_link.register(app, globals())' in app_src
    assert app_src.index('_v2s_saha_link.register') < app_src.index('# ---- v2 section routes end')


def test_the_new_column_is_migrated_on_an_existing_articles_table():
    src = _read('backend', 'app.py')
    assert "('saha_topic_id', 'VARCHAR(80)')" in src
    assert 'saha_topic_id = db.Column(db.String(80))' in src
