# -*- coding: utf-8 -*-
"""المراجعة الخبيرة ٢٠٢٦-١٠-٠٢ (§3.2 + E1–E10) — حرّاس الداشبورد.

E2  الرابط مجمَّد: الردم يكتب الرابط المحسوب الحيّ بايتًا بايتًا، وتغيير العنوان بعد النشر لا يغيّره.
E3  updated_at + البصمة: يتحرّكان لتعديل جوهري فقط — لا لأقسام الروابط ولا للعنوان وحده.
E1  الخريطة: lastmod = updated_at أو النشر، وتُكتب في public_html من نفس دفعة الـprerender.
E9  robots حقيقي + X-Robots-Tag: noindex على كل شيء عدا الخريطة وrobots.
E5  روابط المحاور: support ⇒ المحور + شقيقتان · hub ⇒ كل التفصيليات · standalone ⇒ كلمة غير عامّة.
§3.2-5  جسر التحديث: 401/409/422/200/duplicate + لقطة ArticleVersion + الرابط ثابت.
E8  أول عنوان يساوي العنوان يُحذف عند الاستيراد.
E4  التوقيع «فريق منصة البروفيسور» + author=Organization؛ reviewedBy فقط بمراجع مسجّل.

Run:  cd backend && python3 -m pytest -q tests/test_expert_review_2026_10_02.py
"""
import datetime
import json
import os

import pytest

import app as appmod  # noqa: E402
from app import app as flask_app, db, Article, ArticleVersion  # noqa: E402
import refresh_rules as rr  # noqa: E402

SECRET = 'expert-review-secret'
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
PARA = ('هذا نص تجريبي طويل يشرح المبدأ القانوني بالتفصيل ويعطي القارئ خطوات عملية واضحة. ' * 10).strip()


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET, raising=False)
    monkeypatch.setattr(appmod, '_prerender_push_async', lambda reason='': {'state': 'stubbed', 'reason': reason})
    with flask_app.app_context():
        db.create_all()
        ArticleVersion.query.delete()
        Article.query.delete()
        db.session.commit()
        yield
        ArticleVersion.query.delete()
        Article.query.delete()
        db.session.commit()


@pytest.fixture
def client(ctx):
    with flask_app.test_client() as c:
        yield c


def _mk(title, status='published', body=None, keywords=(), role=None, cluster_id=None, parent_id=None,
        faq=None, primary_kw=None, by='فريق البروفيسور', published_at=datetime.datetime(2026, 9, 1)):
    a = Article(title=title, excerpt='مقتطف', cat='دليل', kicker='دليل', by=by, date='١ سبتمبر ٢٠٢٦',
                body=json.dumps(body or ['فقرة افتتاحية تشرح ' + title + '. ' + PARA, '## القسم الأول', PARA,
                                         '## القسم الثاني', PARA], ensure_ascii=False),
                keywords=json.dumps(list(keywords), ensure_ascii=False),
                faq=json.dumps(faq or [{'q': 'سؤال؟', 'a': 'جواب.'}], ensure_ascii=False),
                target_audience='المحامون', status=status, role=role, cluster_id=cluster_id,
                parent_id=parent_id, primary_kw=primary_kw,
                published_at=published_at if status == 'published' else None)
    db.session.add(a)
    db.session.commit()
    return a


def _old_slug(title, aid):
    """الصيغة القديمة حرفيًّا (قبل التجميد) — مرجع «الرابط الحيّ»."""
    return '%s-%s' % (appmod._slugify_ar(title), aid)


# ——— E2: تجميد الرابط ———

TRICKY = ['نموذج عقد أتعاب محاماة', 'الذكاء الاصطناعي يكتب ويبدع.. فمن يملك الحقوق؟',
          'صياغة «مذكرة دفاع»: من تسجيل الوقائع إلى الطلبات', 'Contract 101 — دليل (2026)', '؟؟؟',
          'من محامي عمومي لمتخصص: إزاي تختار تخصصك (شركات/تحكيم/جنائي) في أول 3 سنين']


def test_backfill_writes_the_current_live_slug_byte_identical(ctx):
    arts = [_mk(t, status=('published' if i % 2 else 'draft')) for i, t in enumerate(TRICKY)]
    before = {a.id: _old_slug(a.title, a.id) for a in arts}
    # محاكاة صفوف ما قبل الهجرة: لا slug مخزَّن
    db.session.execute(db.text('UPDATE articles SET slug = NULL, content_hash = NULL'))
    db.session.commit()
    db.session.expire_all()
    assert all(a.slug is None for a in Article.query.all())
    out = appmod._backfill_article_slugs()
    assert out['slugs'] == len(TRICKY) and out['hashes'] == len(TRICKY)
    db.session.expire_all()
    for a in Article.query.all():
        assert a.slug == before[a.id]
        assert appmod._article_slug(a).encode('utf-8') == before[a.id].encode('utf-8')
        assert appmod.serialize_article(a)['slug'] == before[a.id]
    # idempotent: تشغيلة ثانية لا تلمس شيئًا
    assert appmod._backfill_article_slugs() == {'slugs': 0, 'hashes': 0}


def test_sitemap_and_feed_urls_identical_before_and_after_backfill(ctx, client):
    for t in TRICKY:
        _mk(t)
    db.session.execute(db.text('UPDATE articles SET slug = NULL'))
    db.session.commit()
    db.session.expire_all()
    xml_before = client.get('/sitemap-articles.xml').data
    feed_before = [a['slug'] for a in client.get('/api/content/articles').get_json()['articles']]
    appmod._backfill_article_slugs()
    db.session.expire_all()
    assert client.get('/sitemap-articles.xml').data == xml_before
    assert [a['slug'] for a in client.get('/api/content/articles').get_json()['articles']] == feed_before


def test_title_change_after_publish_keeps_the_url(ctx):
    a = _mk('نموذج عقد أتعاب محاماة')
    url = appmod._blog_url(a)
    a.title = 'نموذج عقد أتعاب محاماة: ٨ بنود تحمي المحامي والموكل'
    db.session.commit()
    assert appmod._blog_url(a) == url and a.slug == _old_slug('نموذج عقد أتعاب محاماة', a.id)


def test_never_published_draft_slug_follows_title_then_freezes_at_publish(ctx):
    a = _mk('عنوان أول', status='draft')
    assert a.slug == _old_slug('عنوان أول', a.id)
    a.title = 'عنوان ثانٍ'
    db.session.commit()
    assert a.slug == _old_slug('عنوان ثانٍ', a.id)
    a.status, a.published_at = 'published', datetime.datetime.utcnow()
    db.session.commit()
    a.title = 'عنوان ثالث بعد النشر'
    db.session.commit()
    assert a.slug == _old_slug('عنوان ثانٍ', a.id)
    # اتسحب ثم اتعدّل: ما زال مجمَّدًا (الرابط معروف ويردّ 410)
    a.status = 'draft'
    db.session.commit()
    a.title = 'عنوان رابع'
    db.session.commit()
    assert a.slug == _old_slug('عنوان ثانٍ', a.id)


# ——— E3: updated_at + البصمة ———

def test_material_edit_bumps_updated_at_links_and_title_do_not(ctx):
    a = _mk('صياغة عقد التوريد')
    h0 = a.content_hash
    assert h0 and a.updated_at is None
    # روابط فقط
    a.body = json.dumps(appmod._article_body_list(a) + [rr.RELATED_HEADING, '• [س](https://elprofessor.net/blog/x-1)'],
                        ensure_ascii=False)
    db.session.commit()
    assert a.updated_at is None and a.content_hash == h0
    # عنوان فقط (تحديث CTR): البصمة تتغيّر، التاريخ لا
    a.title = 'صياغة عقد التوريد: البنود التي تحمي المورّد'
    db.session.commit()
    assert a.updated_at is None and a.content_hash != h0
    # تعديل جوهري: قسم جديد
    a.body = json.dumps(appmod._article_body_list(a)[:5] + ['## قسم جديد', PARA], ensure_ascii=False)
    db.session.commit()
    assert a.updated_at is not None
    assert appmod.serialize_article(a)['updated_at'] == a.updated_at.isoformat()


def test_backfill_related_refresh_never_moves_dates(ctx):
    a = _mk('صياغة عقد التوريد', keywords=['صياغة العقود'])
    _mk('أخطاء صياغة العقود التجارية', keywords=['صياغة العقود'])
    _mk('صياغة العقود الإدارية للمحامي', keywords=['صياغة العقود'])
    h0 = a.content_hash
    out = appmod._backfill_related(apply=True, refresh=True)
    assert out['would_link'] >= 1
    db.session.expire_all()
    a = Article.query.get(a.id)
    assert rr.RELATED_HEADING in a.body and a.updated_at is None and a.content_hash == h0


# ——— E1: الخريطة ———

def test_sitemap_lastmod_uses_updated_at(ctx, client):
    a = _mk('مقال قديم', published_at=datetime.datetime(2026, 7, 1))
    b = _mk('مقال محدّث', published_at=datetime.datetime(2026, 7, 1))
    b.updated_at = datetime.datetime(2026, 9, 30)
    db.session.commit()
    xml = appmod._articles_sitemap_xml()
    assert xml.count('<url>') == 2
    assert '<lastmod>2026-09-30</lastmod>' in xml and '<lastmod>2026-07-01</lastmod>' in xml
    assert client.get('/sitemap-articles.xml').data.decode('utf-8') == xml
    assert a.slug in __import__('urllib.parse').parse.unquote(xml)


def test_prerender_push_writes_and_uploads_the_sitemap():
    src = open(os.path.join(BACKEND, 'app.py'), encoding='utf-8').read()
    body = src[src.index('def _prerender_push(reason'):src.index('def _prerender_push_async')]
    assert "os.path.join(tmp, SITEMAP_FILE)" in body and '_articles_sitemap_xml()' in body
    assert "'blog/_pre/manifest.txt', SITEMAP_FILE]" in body          # في قائمة الرفع (hash-diffed)
    assert '_sftp_replace(sftp' in body                                # .tmp ثم استبدال ذرّي


def test_sftp_replace_prefers_posix_rename():
    calls = []

    class F:
        def posix_rename(self, a, b):
            calls.append(('posix', a, b))

        def remove(self, p):
            calls.append(('rm', p))

        def rename(self, a, b):
            calls.append(('mv', a, b))
    appmod._sftp_replace(F(), 'x.tmp', 'x')
    assert calls == [('posix', 'x.tmp', 'x')]

    class G(F):
        def posix_rename(self, a, b):
            raise IOError('unsupported')
    calls.clear()
    appmod._sftp_replace(G(), 'x.tmp', 'x')
    assert calls == [('rm', 'x'), ('mv', 'x.tmp', 'x')]


# ——— E9: robots + noindex ———

def test_dashboard_robots_and_noindex(client):
    r = client.get('/robots.txt')
    assert r.status_code == 200 and r.mimetype == 'text/plain'
    txt = r.data.decode()
    assert 'Disallow: /' in txt and 'Allow: /sitemap-articles.xml' in txt
    assert 'X-Robots-Tag' not in r.headers
    assert 'noindex' in client.get('/').headers.get('X-Robots-Tag', '')
    assert 'noindex' in client.get('/api/content/articles').headers.get('X-Robots-Tag', '')
    assert 'X-Robots-Tag' not in client.get('/sitemap-articles.xml').headers


# ——— E5: روابط المحاور ———

def test_support_links_hub_first_then_two_siblings(ctx):
    hub = _mk('نموذج عقد أتعاب محاماة', role='hub', cluster_id='c-fees')
    s1 = _mk('عقد اتعاب محاماة بنسبة', role='support', cluster_id='c-fees', parent_id=hub.id)
    s2 = _mk('عقد اتعاب محاماة سنوي', role='support', cluster_id='c-fees', parent_id=hub.id)
    s3 = _mk('عقد اتعاب محاماة الكتروني', role='support', cluster_id='c-fees', parent_id=hub.id)
    _mk('عقد الامتياز التجاري', keywords=['عقد'])
    pool = Article.query.filter_by(status='published').all()
    secs = appmod._cluster_links(s1, pool)
    assert secs[0][0] == appmod.SAME_GUIDE_HEADING
    assert secs[0][1][0].id == hub.id and len(secs[0][1]) == 3
    assert {x.id for x in secs[0][1][1:]} == {s2.id, s3.id}
    hub_secs = appmod._cluster_links(hub, pool)
    assert hub_secs[0][0] == appmod.HUB_NAV_HEADING
    assert [x.id for x in hub_secs[0][1]] == [s1.id, s2.id, s3.id]
    blocks, n = appmod._with_links(appmod._article_body_list(hub), hub, pool)
    assert '## تفاصيل أكثر في هذا الدليل' in blocks and n == 3
    assert any(appmod._blog_url(s1) in b for b in blocks)


def test_retired_support_leaves_hub_nav_without_moving_dates(ctx):
    hub = _mk('نموذج عقد أتعاب محاماة', role='hub', cluster_id='c-fees')
    s1 = _mk('عقد اتعاب محاماة بنسبة', role='support', cluster_id='c-fees', parent_id=hub.id)
    s2 = _mk('عقد اتعاب محاماة سنوي', role='support', cluster_id='c-fees', parent_id=hub.id)
    appmod._backfill_related(apply=True, refresh=True)
    db.session.expire_all()
    assert appmod._blog_url(s2) in Article.query.get(hub.id).body
    s2 = Article.query.get(s2.id)
    s2.status = 'draft'
    db.session.commit()
    appmod._backfill_related(apply=True, refresh=True)
    db.session.expire_all()
    h = Article.query.get(hub.id)
    assert appmod._blog_url(s2) not in h.body and appmod._blog_url(s1) in h.body
    assert h.updated_at is None


def test_standalone_generic_token_alone_is_not_relevance(ctx):
    """مقال 79: «عقد الامتياز» و«عقد الصلح» تقاطعا في «عقد» وحدها فترابطا."""
    _mk('عقد الامتياز التجاري', keywords=['عقد', 'قانون'])
    _mk('عقد الصلح في القانون', keywords=['عقد', 'قانون'])
    me = _mk('نموذج عقد أتعاب محاماة', keywords=['عقد', 'محامي'])
    pool = Article.query.filter_by(status='published').all()
    assert appmod._related_articles(me.title, ['عقد', 'محامي'], 'المحامون', pool, exclude_id=me.id) == []
    assert appmod._cluster_links(me, pool) == []


def test_new_support_from_sync_links_hub_and_refreshes_hub_nav(ctx, monkeypatch):
    hub = _mk('نموذج عقد أتعاب محاماة', role='hub', cluster_id='c-fees')
    payload = [{'id': 'ART_1', 'title': 'عقد اتعاب محاماة بنسبة', 'body': '# عقد اتعاب محاماة بنسبة\n\n' + PARA,
                'category': 'guide', 'author': 'الوكيل الذكي — البروفيسور', 'keywords': ['عقد اتعاب'],
                'faq': [], 'primary_kw': 'عقد اتعاب محاماة بنسبة', 'cluster_id': 'c-fees', 'role': 'support'}]

    class R:
        status_code = 200

        def json(self):
            return {'articles': payload}
    monkeypatch.setattr(appmod.requests, 'get', lambda *a, **k: R())
    monkeypatch.setattr(appmod, '_delete_platform_article', lambda aid: None)
    monkeypatch.setenv('BLOG_AUTOPUBLISH_ALL', 'true')
    out, st = appmod._sync_platform_articles()
    assert st == 200 and out['published'] == 1
    new = Article.query.filter_by(title='عقد اتعاب محاماة بنسبة').first()
    assert new.role == 'support' and new.parent_id == hub.id and new.primary_kw == 'عقد اتعاب محاماة بنسبة'
    blocks = appmod._article_body_list(new)
    assert blocks[0] != '## عقد اتعاب محاماة بنسبة'                     # E8: H1 المكرّر سقط
    assert appmod.SAME_GUIDE_HEADING in blocks and appmod._blog_url(hub) in json.dumps(blocks, ensure_ascii=False)
    db.session.expire_all()
    assert appmod._blog_url(new) in Article.query.get(hub.id).body        # قائمة المحور اتحدّثت
    assert new.by == 'فريق منصة البروفيسور'                                # E4


# ——— E8 ———

def test_md_to_blocks_drops_leading_title_heading_only():
    blocks = appmod._md_to_blocks('# نموذج عقد أتعاب محاماة\n\nفقرة.\n\n## البنود\n\nنص.', 'نموذج عقد أتعاب محاماة')
    assert blocks == ['فقرة.', '## البنود', 'نص.']
    assert appmod._md_to_blocks('## عنوان آخر\n\nفقرة.', 'نموذج')[0] == '## عنوان آخر'


# ——— E4: التوقيع ———

def test_byline_is_organization_and_reviewedby_only_when_set(ctx, client):
    a = _mk('مقال آلي', by='هيئة تحرير البروفيسور')
    s = appmod.serialize_article(a)
    assert s['author_type'] == 'Organization' and s['author_name'] == 'منصة البروفيسور'
    assert s['reviewed_by'] is None
    b = _mk('مقال خبير', by='د. أحمد سالم')
    assert appmod.serialize_article(b)['author_type'] == 'Person'
    assert appmod._sync_byline('الوكيل الذكي — البروفيسور') == 'فريق منصة البروفيسور'
    assert appmod._sync_byline('د. أحمد سالم') == 'د. أحمد سالم'


def test_bylines_normalize_dry_run_then_apply_touches_team_bylines_only(ctx, client):
    a = _mk('أ', by='هيئة تحرير البروفيسور')
    b = _mk('ب', by='الوكيل الذكي — البروفيسور')
    c = _mk('ج', by='د. أحمد سالم')
    d = _mk('د', by='فريق البروفيسور', status='draft')
    assert client.post('/api/content/bylines/normalize').status_code == 401
    h = {'X-ELP-Metrics-Secret': SECRET}
    r = client.post('/api/content/bylines/normalize', headers=h).get_json()
    assert r['applied'] is False and r['would_change'] == 2
    db.session.expire_all()
    assert Article.query.get(a.id).by == 'هيئة تحرير البروفيسور'
    r = client.post('/api/content/bylines/normalize?apply=1', headers=h).get_json()
    assert r['applied'] is True
    db.session.expire_all()
    assert Article.query.get(a.id).by == Article.query.get(b.id).by == 'فريق منصة البروفيسور'
    assert Article.query.get(c.id).by == 'د. أحمد سالم'
    assert Article.query.get(d.id).by == 'فريق البروفيسور'                # المسودّات خارج النطاق الافتراضي
    assert Article.query.get(a.id).updated_at is None and Article.query.get(a.id).reviewed_by is None


def test_editor_sets_reviewed_by_and_clears_it(ctx):
    a = _mk('مقال')
    appmod._apply_article_fields(a, {'reviewed_by': 'أ. منى'})
    db.session.commit()
    assert a.reviewed_by == 'أ. منى' and a.reviewed_at is not None
    appmod._apply_article_fields(a, {'reviewed_by': ''})
    db.session.commit()
    assert a.reviewed_by is None and a.reviewed_at is None


# ——— §3.2-5: جسر التحديث ———

def _refresh(client, aid, **body):
    return client.post('/api/bridge/articles/%s/refresh' % aid, json=body,
                       headers={'X-ELP-Metrics-Secret': SECRET})


def test_refresh_bridge_contract(ctx, client):
    a = _mk('نموذج عقد أتعاب محاماة', primary_kw='نموذج عقد أتعاب محاماة',
            body=['نموذج عقد أتعاب محاماة يحدد العلاقة. ' + PARA, '## البنود', PARA, '## الأخطاء', PARA])
    slug = a.slug
    assert client.post('/api/bridge/articles/%s/refresh' % a.id, json={}).status_code == 401
    assert _refresh(client, a.id, request_id='r0', if_hash='nope').status_code == 409
    h = a.content_hash
    # قسم ناقص ⇒ 422
    r = _refresh(client, a.id, request_id='r1', if_hash=h, body=['نموذج عقد أتعاب محاماة. ' + PARA, '## البنود', PARA * 2])
    assert r.status_code == 422 and any(e.startswith('h2_missing') for e in r.get_json()['errors'])
    # رقم جديد ⇒ 422
    r = _refresh(client, a.id, request_id='r2', if_hash=h,
                 body=appmod._article_body_list(a)[:4] + [PARA + ' الرسوم 1500 جنيه.'])
    assert r.status_code == 422 and any(e.startswith('new_numbers') for e in r.get_json()['errors'])
    # عنوان بلا سبب CTR ⇒ 422
    r = _refresh(client, a.id, request_id='r3', if_hash=h, title='عنوان جديد تمامًا', reasons=['heuristic:age'])
    assert r.status_code == 422
    # تجربة جافّة لا تكتب
    md = ('# نموذج عقد أتعاب محاماة\n\nنموذج عقد أتعاب محاماة يحدد العلاقة. ' + PARA +
          '\n\n## البنود\n\n' + PARA + '\n\n## الأخطاء\n\n' + PARA + '\n\n## متى تحتاج محاميًا\n\n' + PARA)
    r = _refresh(client, a.id, request_id='r4', if_hash=h, body=md, reasons=['heuristic:thin'], dry_run=True)
    assert r.status_code == 200 and r.get_json()['dry_run'] and ArticleVersion.query.count() == 0
    # تحديث جوهري حقيقي
    r = _refresh(client, a.id, request_id='r5', if_hash=h, body=md, reasons=['heuristic:thin'],
                 faq=[{'q': 'سؤال؟', 'a': 'جواب.'}, {'q': 'سؤال ثان؟', 'a': 'جواب ثان.'}],
                 change_log=['expanded: متى تحتاج محاميًا'])
    j = r.get_json()
    assert r.status_code == 200 and j['material'] is True and j['version'] == 1 and j['slug'] == slug
    db.session.expire_all()
    a = Article.query.get(a.id)
    assert a.updated_at is not None and a.refresh_count == 1 and a.slug == slug
    assert appmod._article_body_list(a)[0] != '## نموذج عقد أتعاب محاماة'
    v = ArticleVersion.query.filter_by(article_id=a.id).one()
    assert v.request_id == 'r5' and v.hash == h and '## الأخطاء' in v.body
    # نفس request_id ⇒ duplicate بلا كتابة
    r = _refresh(client, a.id, request_id='r5', if_hash='anything')
    assert r.status_code == 200 and r.get_json()['duplicate'] is True
    # تحديث CTR (عنوان فقط) ⇒ لا يحرّك updated_at
    u0 = a.updated_at
    r = _refresh(client, a.id, request_id='r6', if_hash=a.content_hash,
                 title='نموذج عقد أتعاب محاماة: ٣ أقسام تحمي الطرفين', reasons=['ctr:0.6%'])
    assert r.status_code == 200 and r.get_json()['material'] is False
    db.session.expire_all()
    a = Article.query.get(a.id)
    assert a.updated_at == u0 and a.slug == slug and a.title.endswith('تحمي الطرفين')


def test_refresh_bridge_rejects_slug_change(ctx, client):
    a = _mk('مقال')
    r = _refresh(client, a.id, request_id='s1', if_hash=a.content_hash, slug='other-1')
    assert r.status_code == 422 and r.get_json()['errors'] == ['slug_changed']


# ——— §3.2-9: تعيين المحاور ———

def test_cluster_assignment_validates_and_dry_runs(ctx, client):
    hub = _mk('نموذج عقد أتعاب محاماة')
    s1 = _mk('عقد اتعاب محاماة بنسبة')
    other = _mk('عقد الامتياز')
    h = {'X-ELP-Metrics-Secret': SECRET}
    bad = client.post('/api/bridge/articles/clusters', headers=h, json={'rows': [
        {'id': s1.id, 'cluster_id': 'c-fees', 'role': 'support'}]})
    assert bad.status_code == 422 and 'support without parent_id' in bad.get_json()['errors'][0]
    two_hubs = client.post('/api/bridge/articles/clusters', headers=h, json={'rows': [
        {'id': hub.id, 'cluster_id': 'c-fees', 'role': 'hub'}, {'id': other.id, 'cluster_id': 'c-fees', 'role': 'hub'}]})
    assert two_hubs.status_code == 422 and 'second hub' in json.dumps(two_hubs.get_json(), ensure_ascii=False)
    rows = [{'id': hub.id, 'cluster_id': 'c-fees', 'role': 'hub', 'primary_kw': 'نموذج عقد أتعاب محاماة'},
            {'id': s1.id, 'cluster_id': 'c-fees', 'role': 'support', 'parent_id': hub.id}]
    dry = client.post('/api/bridge/articles/clusters', headers=h, json={'rows': rows}).get_json()
    assert dry['applied'] is False and dry['valid'] == 2
    db.session.expire_all()
    assert Article.query.get(hub.id).role is None
    ok = client.post('/api/bridge/articles/clusters?apply=1', headers=h, json={'rows': rows}).get_json()
    assert ok['applied'] is True
    db.session.expire_all()
    assert Article.query.get(s1.id).parent_id == hub.id
    assert appmod._blog_url(Article.query.get(s1.id)) in Article.query.get(hub.id).body


# ——— المُتحقِّق المشترك ———

def test_shared_fixtures_pass():
    fx = json.load(open(os.path.join(BACKEND, 'refresh_fixtures.json'), encoding='utf-8'))
    for c in fx['cases']:
        v = rr.validate(c['cur'], c['new'], c.get('reasons', []), ymyl=c.get('ymyl', True),
                        primary_kw=c.get('primary_kw'), today=datetime.date.fromisoformat(c.get('today', '2026-10-02')))
        e = c['expect']
        assert v['ok'] == e['ok'], (c['name'], v)
        if 'material' in e:
            assert v['material'] == e['material'], c['name']
        if 'errors' in e:
            assert v['errors'] == e['errors'], c['name']
        for x in e.get('errors_contain', []):
            assert any(err.startswith(x) for err in v['errors']), (c['name'], x, v['errors'])
        for x in e.get('warnings_contain', []):
            assert any(w.startswith(x) for w in v['warnings']), (c['name'], x)


def test_validator_is_byte_identical_to_the_platform_copy():
    other = os.path.expanduser(os.environ.get(
        'EP_PLATFORM_REPO', '~/Documents/Playground/elprofessor')) + '/backend/services/refresh_rules.py'
    if not os.path.exists(other):
        pytest.skip('platform repo not checked out next to the dashboard')
    assert open(other, 'rb').read() == open(os.path.join(BACKEND, 'refresh_rules.py'), 'rb').read()
    fx_other = os.path.dirname(other) + '/refresh_fixtures.json'
    assert open(fx_other, 'rb').read() == open(os.path.join(BACKEND, 'refresh_fixtures.json'), 'rb').read()


# ——— من البيانات إلى الصفحة الثابتة فعلًا (فخّ «مكتوبٌ ولا يُرسم») ———

def test_prerendered_page_carries_org_author_reviewedby_hub_nav_and_datemodified(ctx):
    import re
    import shutil
    import subprocess
    import tempfile
    site = os.path.expanduser(os.environ.get('EP_SITE_REPO', '~/elprofessor-site'))
    if not os.path.exists(os.path.join(site, 'article.html')):
        pytest.skip('site repo not available')
    for i in range(30):   # blog.html's verifier wants a realistically full index (≥5000 chars)
        f = _mk('مقال تحليلي عن موضوع قانوني مختلف رقم %d' % i, keywords=['موضوع%d' % i])
        f.excerpt = PARA[:160]
    db.session.commit()
    hub = _mk('نموذج عقد أتعاب محاماة', role='hub', cluster_id='c-fees', by='فريق منصة البروفيسور')
    sup = _mk('عقد اتعاب محاماة بنسبة', role='support', cluster_id='c-fees', parent_id=hub.id)
    sup.reviewed_by, sup.reviewed_at = 'أ. منى مصطفى', datetime.datetime(2026, 10, 2)
    db.session.commit()
    appmod._backfill_related(apply=True, refresh=True)
    hub = Article.query.get(hub.id)
    hub.body = json.dumps(appmod._article_body_list(hub)[:5] + ['## قسم جديد بعد التحديث', PARA] +
                          appmod._article_body_list(hub)[5:], ensure_ascii=False)
    db.session.commit()
    assert hub.updated_at is not None
    feed = {'source': 'dashboard', 'articles': [appmod.serialize_article(a)
                                                for a in Article.query.filter_by(status='published').all()]}
    tmp = tempfile.mkdtemp(prefix='prerender-er-')
    try:
        for name in ('article.html', 'blog.html'):
            shutil.copy(os.path.join(site, name), os.path.join(tmp, name))
        os.makedirs(os.path.join(tmp, 'blog', '_pre'))
        ff = os.path.join(tmp, '_feed.json')
        with open(ff, 'w', encoding='utf-8') as fh:
            json.dump(feed, fh, ensure_ascii=False)
        proc = subprocess.run(['python3', os.path.join(BACKEND, 'prerender.py'), '--site', tmp, '--feed-file', ff,
                               '--min-articles', '1'], capture_output=True, text=True, timeout=300)
        assert proc.returncode == 0, proc.stderr[-1500:]

        def ld(page):
            m = re.search(r'<script type="application/ld\+json" id="ld-article">(.*?)</script>', page, re.S)
            return json.loads(m.group(1))
        hub_page = open(os.path.join(tmp, 'blog', '_pre', '%d.html' % hub.id), encoding='utf-8').read()
        sup_page = open(os.path.join(tmp, 'blog', '_pre', '%d.html' % sup.id), encoding='utf-8').read()
        h, s = ld(hub_page), ld(sup_page)
        assert h['author'] == {'@type': 'Organization', 'name': 'منصة البروفيسور'}
        assert 'reviewedBy' not in h
        assert s['reviewedBy'] == {'@type': 'Person', 'name': 'أ. منى مصطفى'}
        assert h['dateModified'].startswith(hub.updated_at.strftime('%Y-%m-%d')) and h['dateModified'] != h['datePublished']
        assert s['dateModified'] == s['datePublished']
        assert 'تفاصيل أكثر في هذا الدليل' in hub_page
        assert ('<a class="inlink" href="%s">' % appmod._blog_url(sup)) in hub_page
        assert ('<a class="inlink" href="%s">' % appmod._blog_url(hub)) in sup_page and 'في نفس الدليل' in sup_page
        assert 'article:modified_time' in hub_page
        assert ('<link rel="canonical" href="%s">' % appmod._blog_url(hub)) in hub_page
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_dockerfile_ships_every_local_module_app_imports():
    """الصورة تنسخ ملفات بعينها لا المجلّد كله — وحدةٌ محلية يستوردها app.py ولا ينسخها الـDockerfile
    = حاوية لا تقوم بعد النشر (اتلقطت قبل النشر الأول لـrefresh_rules.py)."""
    import re
    src = open(os.path.join(BACKEND, 'app.py'), encoding='utf-8').read()
    docker = open(os.path.join(os.path.dirname(BACKEND), 'Dockerfile'), encoding='utf-8').read()
    local = {m for m in re.findall(r'^\s*import (\w+)', src, re.M) + re.findall(r'^\s*from (\w+) import', src, re.M)
             if os.path.exists(os.path.join(BACKEND, m + '.py'))}
    assert 'refresh_rules' in local
    for m in local:
        assert ('COPY backend/%s.py /app/%s.py' % (m, m)) in docker, m
