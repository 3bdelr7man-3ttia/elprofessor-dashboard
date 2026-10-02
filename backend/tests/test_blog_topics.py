# -*- coding: utf-8 -*-
"""سجلّ موضوعات المدوّنة + صفحات /blog/topic/<slug> + بحث المدوّنة — قرار المؤسس ٢٠٢٦-١٠-٠٢.

⛔ فخّ «مكتوبٌ ولا يُرسم»: الاختبار الطرفي يمرّر فيد الداشبورد الحقيقي (_prerender_feed_json) عبر
`prerender.py` الحقيقي وقالبَي article.html / blog.html الحقيقيين من ريبو الموقع، ويفحص الصفحات
المكتوبة على القرص: H1 والروابط والـJSON-LD، ورابط «ضمن موضوع» في صفحة المحور، وفهرس الموضوعات
في blog.html، ومسح صفحة الموضوع الذي اختفى.

Run:  cd backend && python3 -m pytest -q tests/test_blog_topics.py
"""
import csv
import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile

import jwt
import pytest
from werkzeug.security import generate_password_hash

import app as appmod  # noqa: E402
from app import app as flask_app, db, Article, BlogTopic, User  # noqa: E402

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIR = os.path.expanduser(os.environ.get('EP_SITE_REPO', '~/elprofessor-site'))
PRERENDER = os.path.join(BACKEND, 'prerender.py')
CURATED = os.path.expanduser(os.environ.get(
    'EP_CLUSTERS_CSV', '~/Documents/Playground/elprofessor/backend/data/clusters_curated_2026-10-02.csv'))
LONG = ('هذا نص تجريبي طويل يشرح المبدأ القانوني بالتفصيل ويعطي القارئ خطوات عملية واضحة. ' * 12).strip()


@pytest.fixture
def ctx():
    with flask_app.app_context():
        db.create_all()
        Article.query.delete()
        BlogTopic.query.delete()
        db.session.commit()
        appmod._seed_blog_topics()
        yield
        Article.query.delete()
        BlogTopic.query.delete()
        db.session.commit()


def _pub(title, cluster=None, role=None, parent=None, audience='المحامون', keywords=(), days=0, excerpt='مقتطف'):
    a = Article(title=title, excerpt=excerpt, cat='دليل', kicker='دليل', by='فريق منصة البروفيسور',
                date='١ أكتوبر ٢٠٢٦', body=json.dumps(['## ' + title, LONG, LONG], ensure_ascii=False),
                keywords=json.dumps(list(keywords), ensure_ascii=False), faq='[]', target_audience=audience,
                status='published', published_at=datetime.datetime(2026, 9, 1) + datetime.timedelta(days=days),
                cluster_id=cluster, role=role, parent_id=parent)
    db.session.add(a)
    db.session.commit()
    return a


# ——— ١) السجلّ ———

def test_seed_has_20_stable_ascii_slugs_and_is_idempotent(ctx):
    rows = BlogTopic.query.order_by(BlogTopic.sort_order).all()
    assert len(rows) == 20
    slugs = [t.slug for t in rows]
    assert len(set(slugs)) == 20 and len({t.cluster_id for t in rows}) == 20
    for s in slugs:
        assert appmod.TOPIC_SLUG_RE.match(s), s
        assert s.isascii() and not s[-1].isdigit() and len(s) <= 30, s   # لا يشبه ذيل «-<id>»
    assert 'tahkeem' in slugs and 'siyaghat-al-uqood' in slugs
    for t in rows:
        assert t.label and t.description and 20 <= len(t.description) <= 400
    # تحرير المؤسس لا يُمحى بإعادة البذر
    t = BlogTopic.query.filter_by(cluster_id='c-arbitration').first()
    t.label = 'التحكيم — معدَّل'
    db.session.commit()
    assert appmod._seed_blog_topics() == 0
    assert BlogTopic.query.filter_by(cluster_id='c-arbitration').first().label == 'التحكيم — معدَّل'
    assert BlogTopic.query.count() == 20


@pytest.mark.skipif(not os.path.isfile(CURATED), reason='curated clusters CSV (platform repo) not present')
def test_seed_matches_the_curated_csv():
    with open(CURATED, encoding='utf-8-sig') as fh:
        rows = list(csv.DictReader(fh))
    want = {}
    for r in rows:
        want.setdefault(r['cluster_id'], {'label': r['label'], 'hub': None})
        if r['role'] == 'hub':
            want[r['cluster_id']]['hub'] = int(r['id'])
    seed = {cid: (label, hub) for cid, _slug, label, hub, _d in appmod.BLOG_TOPICS_SEED}
    assert set(seed) == set(want)
    for cid, w in want.items():
        assert seed[cid] == (w['label'], w['hub']), cid


# ——— ٢) الفيد والنقطة العامّة ———

def test_feed_and_public_topics_endpoint(ctx):
    hub = _pub('إجراءات التحكيم خطوة بخطوة', 'c-arbitration', 'hub')
    _pub('دعوى بطلان حكم التحكيم', 'c-arbitration', 'support', hub.id)
    _pub('مقال مستقل بلا محور')
    c = flask_app.test_client()
    rows = c.get('/api/content/articles').get_json()['articles']
    by = {r['title']: r for r in rows}
    assert by['إجراءات التحكيم خطوة بخطوة']['topic_slug'] == 'tahkeem'
    assert by['إجراءات التحكيم خطوة بخطوة']['topic_label'] == 'إجراءات التحكيم'
    assert by['مقال مستقل بلا محور']['topic_slug'] is None
    summ = c.get('/api/content/articles?fields=summary').get_json()['articles']
    assert 'topic_slug' in summ[0] and 'target_audience' in summ[0]
    tops = c.get('/api/content/topics').get_json()['topics']
    assert [t['slug'] for t in tops] == ['tahkeem']            # only topics with a published article
    assert tops[0]['count'] == 2 and tops[0]['hub_id'] == hub.id
    assert tops[0]['url'] == 'https://elprofessor.net/blog/topic/tahkeem'
    assert len(c.get('/api/content/topics?all=1').get_json()['topics']) == 20
    feed = json.loads(appmod._prerender_feed_json())
    assert [t['slug'] for t in feed['topics']] == ['tahkeem']


def test_sitemap_lists_topic_pages_with_lastmod_of_newest_article(ctx):
    hub = _pub('صياغة العقود التجارية', 'c-contracts', 'hub', days=0)
    s = _pub('صياغة عقد العمل', 'c-contracts', 'support', hub.id, days=3)
    s.updated_at = datetime.datetime(2026, 9, 20, 10, 0)
    db.session.commit()
    xml = appmod._articles_sitemap_xml()
    assert ('<url><loc>https://elprofessor.net/blog/topic/siyaghat-al-uqood</loc>'
            '<lastmod>2026-09-20</lastmod>') in xml
    assert '/blog/topic/tahkeem' not in xml                    # no published article ⇒ no URL


def test_admin_edit_label_is_gated_and_slug_is_frozen(ctx, monkeypatch):
    pushes = []
    monkeypatch.setattr(appmod, '_prerender_push_async', lambda reason='': pushes.append(reason) or {})
    c = flask_app.test_client()
    assert c.put('/api/content/topics/c-arbitration', json={'label': 'x'}).status_code == 401
    u = User.query.filter_by(email='topics-admin@test.local').first()
    if not u:
        u = User(email='topics-admin@test.local', password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
                 name='admin', role='admin', dashboard_role='admin', linked_to_name='',
                 preferred_currency='AUTO', is_active=True)
        db.session.add(u)
        db.session.commit()
    tok = jwt.encode({'user_id': u.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    h = {'Authorization': 'Bearer ' + tok}
    r = c.put('/api/content/topics/c-arbitration', headers=h,
              json={'label': 'التحكيم التجاري', 'description': 'وصف جديد للموضوع في جملة واحدة.'})
    assert r.status_code == 200 and r.get_json()['label'] == 'التحكيم التجاري'
    assert r.get_json()['slug'] == 'tahkeem' and pushes == ['topic:c-arbitration']
    assert c.put('/api/content/topics/c-arbitration', headers=h, json={'slug': 'other'}).status_code == 400
    assert c.put('/api/content/topics/c-arbitration', headers=h, json={'label': ''}).status_code == 400
    assert c.put('/api/content/topics/nope', headers=h, json={'label': 'x'}).status_code == 404
    assert BlogTopic.query.filter_by(cluster_id='c-arbitration').first().slug == 'tahkeem'


def test_dockerfile_ships_every_backend_module_the_app_imports():
    docker = open(os.path.join(os.path.dirname(BACKEND), 'Dockerfile'), encoding='utf-8').read()
    for mod in ('app.py', 'prerender.py', 'refresh_rules.py'):
        assert 'COPY backend/%s ' % mod in docker, mod
    src = open(os.path.join(BACKEND, 'app.py'), encoding='utf-8').read()
    local = {f[:-3] for f in os.listdir(BACKEND) if f.endswith('.py') and not f.startswith('test_')}
    for m in re.findall(r'^\s*import (\w+)|^\s*from (\w+) import', src, re.M):
        name = m[0] or m[1]
        if name in local and name not in ('app', 'conftest'):
            assert 'COPY backend/%s.py ' % name in docker, name


# ——— ٣) طرفي: prerender.py + القوالب الحقيقية ⇒ صفحات على القرص ———

@pytest.mark.skipif(not (shutil.which('node') and os.path.isfile(os.path.join(SITE_DIR, 'blog.html'))),
                    reason='needs node + the marketing-site repo (EP_SITE_REPO)')
def test_topic_pages_are_prerendered_linked_and_pruned(ctx):
    hub = _pub('إجراءات التحكيم خطوة بخطوة', 'c-arbitration', 'hub', keywords=['التحكيم'])
    sups = [_pub('دعوى بطلان حكم التحكيم', 'c-arbitration', 'support', hub.id, days=1, keywords=['حكم التحكيم']),
            _pub('تنفيذ حكم التحكيم', 'c-arbitration', 'support', hub.id, days=2, keywords=['تنفيذ حكم التحكيم'])]
    # مستقلّ يتقاطع مع كلمات الموضوع النادرة في ٣+ (اجراءات · تحكيم · تنفيذ · حكم) ⇒ «مقالات قريبة»
    rel = _pub('شرط التحكيم في عقود التوريد الدولية', keywords=['تنفيذ حكم التحكيم', 'إجراءات التحكيم'], days=4)
    # صفحة منتج «عن المنصة» لا تُعرض قريبةً أبدًا ولو تطابقت الكلمات
    prod = _pub('إجراءات التحكيم على المنصة', keywords=['تنفيذ حكم التحكيم', 'إجراءات التحكيم'], days=4)
    prod.cat = 'عن المنصة'
    db.session.commit()
    chub = _pub('صياغة العقود التجارية', 'c-contracts', 'hub', days=5)
    csup = _pub('صياغة عقد العمل', 'c-contracts', 'support', chub.id, days=6)
    for i in range(30):   # blog.html's verifier wants a realistically full index (≥5000 chars)
        _pub('مقال تحليلي عن موضوع قانوني مختلف رقم %d' % i, keywords=['موضوع'], excerpt=LONG[:160], days=10 + i)
    feed = appmod._prerender_feed_json()
    tmp = tempfile.mkdtemp(prefix='prerender-topics-')
    try:
        for name in ('article.html', 'blog.html'):
            shutil.copy(os.path.join(SITE_DIR, name), os.path.join(tmp, name))
        os.makedirs(os.path.join(tmp, 'blog', '_pre'))
        os.makedirs(os.path.join(tmp, 'blog', '_topic'))
        stale = os.path.join(tmp, 'blog', '_topic', 'old-topic.html')
        with open(stale, 'w') as fh:
            fh.write('old')
        ff = os.path.join(tmp, '_feed.json')
        with open(ff, 'w', encoding='utf-8') as fh:
            fh.write(feed)
        proc = subprocess.run(['python3', PRERENDER, '--site', tmp, '--feed-file', ff, '--min-articles', '1'],
                              capture_output=True, text=True, timeout=300)
        assert proc.returncode == 0, proc.stderr[-2000:]
        summary = json.loads(proc.stdout.strip().splitlines()[-1])
        assert summary['topics'] == ['siyaghat-al-uqood', 'tahkeem'] and summary['topics_error'] is None
        assert not os.path.exists(stale)                                   # vanished topic pruned
        assert sorted(os.listdir(os.path.join(tmp, 'blog', '_topic'))) == ['siyaghat-al-uqood.html', 'tahkeem.html']

        page = open(os.path.join(tmp, 'blog', '_topic', 'tahkeem.html'), encoding='utf-8').read()
        assert re.findall(r'<h1>(.*?)</h1>', page) == ['إجراءات التحكيم']
        assert '<link rel="canonical" href="https://elprofessor.net/blog/topic/tahkeem">' in page
        assert '<meta property="og:url" content="https://elprofessor.net/blog/topic/tahkeem">' in page
        desc = BlogTopic.query.filter_by(cluster_id='c-arbitration').first().description
        assert desc in page
        # المحور أولًا (بطاقة feat) ثم التفصيلية بترتيب النشر، ثم المستقلّ القريب
        pos = [page.find('href="%s"' % appmod._blog_url(a).replace('https://elprofessor.net', ''))
               for a in [hub] + sups + [rel]]
        assert all(p > 0 for p in pos) and pos == sorted(pos), pos
        assert page.find('class="feat"') < pos[1]
        assert ('href="%s"' % appmod._blog_url(prod).replace('https://elprofessor.net', '')) not in page
        assert 'صياغة عقد العمل' not in page.split('موضوعات أخرى')[0]    # other topic's article not listed
        assert 'href="/blog/topic/siyaghat-al-uqood"' in page              # «موضوعات أخرى»
        lds = {}
        for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
            o = json.loads(m.group(1))
            lds[o.get('@type')] = o
        assert lds['CollectionPage']['url'] == 'https://elprofessor.net/blog/topic/tahkeem'
        assert lds['CollectionPage']['mainEntity']['numberOfItems'] == 3
        assert [x['name'] for x in lds['BreadcrumbList']['itemListElement']] == ['الرئيسية', 'المقالات',
                                                                                  'إجراءات التحكيم']
        # لا مسار نسبي (الصفحة على /blog/topic/ ⇒ ٤٠٤) ولا بقايا مُصيِّر المدوّنة
        # (الوسم الافتتاحي لكل <script> يُفحص أيضًا: <script src="pixel.js"> نسبي في القالب — ضرب مرّة)
        tags = re.sub(r'(?is)(<script\b[^>]*>).*?</script>', r'\1', page)
        assert not re.findall(r'\b(?:href|src)="(?!/|#|https?:|mailto:|tel:|data:)[^"]+"', tags)
        assert 'content-loader.js' not in page and 'id="grid"' not in page
        assert 'href="/mobile-fixes.css' in page and 'src="/pixel.js?v=' in page

        # رابط «ضمن موضوع» في صفحة المحور والتفصيلية — لا في المستقلّ
        for a, want in ((hub, True), (sups[0], True), (rel, False)):
            pre = open(os.path.join(tmp, 'blog', '_pre', '%d.html' % a.id), encoding='utf-8').read()
            assert ('href="/blog/topic/tahkeem"' in pre) is want, a.title

        # blog.html: كل روابط المقالات + فهرس الموضوعات الثابت
        blog = open(os.path.join(tmp, 'blog.html'), encoding='utf-8').read()
        n_pub = Article.query.filter_by(status='published').count()
        assert blog.count('<a class="post" href="/blog/') + blog.count('<a class="feat" href="/blog/') == n_pub
        assert 'href="/blog/topic/tahkeem"' in blog and 'href="/blog/topic/siyaghat-al-uqood"' in blog
        assert 'class="fchip' not in blog.split('id="filters">')[1].split('</div>')[0]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.skipif(not (shutil.which('node') and os.path.isfile(os.path.join(SITE_DIR, 'blog.html'))),
                    reason='needs node + the marketing-site repo')
def test_blog_search_js_suite_passes():
    """مُطبِّع البحث العربي وفلاتر blog.html — نفس السكربت المنشور، في node:vm."""
    proc = subprocess.run(['node', os.path.join(SITE_DIR, 'tools', 'test-blog-search.js'),
                           os.path.join(SITE_DIR, 'blog.html')], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
