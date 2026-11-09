# -*- coding: utf-8 -*-
"""R19 — قاعدة المؤسس (2026-11-09): «أي حاجة ملهاش رابط أو مش هتعرف توصل للرابط بتاعها ما تنشرهاش».

المنصّة ما بتولّد مقال خبر بلا رابط يفتح، والمزامنة هنا الحزام الثاني: مقال `category=news` (أو له
`source_news_id`) بلا `source_url` http(s) يدخل المدوّنة مسودة حتى مع BLOG_AUTOPUBLISH_ALL، ويرجع في
ردّ المزامنة تحت `held_no_source`.

Run:  cd backend && python3 -m pytest -q tests/test_sync_source_link_guard.py
⛔ صفر شبكة: المنصّة مستبدَلة بردّ ثابت، والدفع للاستضافة مستبدَل.
"""
import pytest

import app as appmod  # noqa: E402
import article_integrity as ai  # noqa: E402
from app import app as flask_app, db, Article, ArticleVersion  # noqa: E402

SECRET = 'sync-source-guard-secret'
PARA = ('هذا نص تجريبي طويل يشرح المبدأ القانوني بالتفصيل ويعطي القارئ خطوات عملية واضحة. ' * 6).strip()
SRC = 'https://news.example.com/labour-law'


# ——— الدالة النقيّة ———

def test_has_source_url_accepts_only_http_urls():
    assert ai.has_source_url(SRC) and ai.has_source_url('http://example.org/a?b=1')
    for bad in ('', None, '   ', 'javascript:alert(1)', 'ftp://x.example.com/a', '/relative', 'https://', 'https://a b.com',
                'example.com/page'):
        assert not ai.has_source_url(bad), bad


def test_news_without_source_detection():
    assert ai.news_without_source({'category': 'news'})
    assert ai.news_without_source({'category': 'news', 'source_url': ''})
    assert ai.news_without_source({'category': 'law', 'source_news_id': 'N1', 'source_url': None})   # له خبر أصلي
    assert not ai.news_without_source({'category': 'news', 'source_url': SRC})
    assert not ai.news_without_source({'category': 'law', 'source_news_id': 'N1', 'source_url': SRC})
    # غير الأخبار لا تتأثر
    assert not ai.news_without_source({'category': 'law'})
    assert not ai.news_without_source({'category': 'feature'})
    assert not ai.news_without_source({'category': 'guide', 'source_url': None})


# ——— الدمج في المزامنة ———

@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET, raising=False)
    monkeypatch.setattr(appmod, '_prerender_push_async', lambda reason='': {'state': 'stubbed', 'reason': reason})
    deleted = []
    monkeypatch.setattr(appmod, '_delete_platform_article', lambda aid: deleted.append(aid))
    monkeypatch.setenv('BLOG_AUTOPUBLISH_ALL', 'true')
    with flask_app.app_context():
        db.create_all()
        ArticleVersion.query.delete()
        Article.query.delete()
        db.session.commit()
        yield deleted


def _serve(monkeypatch, payload):
    class R:
        status_code = 200

        def json(self):
            return {'articles': payload}
    monkeypatch.setattr(appmod.requests, 'get', lambda *a, **k: R())


def _art(aid, title, category='guide', **extra):
    a = {'id': aid, 'title': title, 'body': '# %s\n\n%s' % (title, PARA), 'category': category, 'author': 'x',
         'keywords': [], 'faq': []}
    a.update(extra)
    return a


def test_news_without_a_source_link_lands_as_a_draft_even_with_autopublish_all(ctx, monkeypatch):
    _serve(monkeypatch, [
        _art('A_guide', 'دليل عادي'),
        _art('A_news_ok', 'خبر له مصدر', 'news', source_url=SRC),
        _art('A_news_none', 'خبر بلا مصدر', 'news'),
        _art('A_news_empty', 'خبر مصدره فارغ', 'news', source_url='  '),
        _art('A_news_bad', 'خبر برابط غير http', 'news', source_url='javascript:alert(1)'),
        _art('A_law_from_news', 'تحليل من خبر بلا رابط', 'law', source_news_id='N7'),
    ])
    out, st = appmod._sync_platform_articles()
    assert st == 200 and out['imported'] == 6 and out['published'] == 2 and out['drafts'] == 4
    assert {h['title'] for h in out['held_no_source']} == {
        'خبر بلا مصدر', 'خبر مصدره فارغ', 'خبر برابط غير http', 'تحليل من خبر بلا رابط'}
    assert {h['platform_id'] for h in out['held_no_source']} == {'A_news_none', 'A_news_empty', 'A_news_bad', 'A_law_from_news'}
    by = {a.title: a.status for a in Article.query.all()}
    assert by == {'دليل عادي': 'published', 'خبر له مصدر': 'published', 'خبر بلا مصدر': 'draft',
                  'خبر مصدره فارغ': 'draft', 'خبر برابط غير http': 'draft', 'تحليل من خبر بلا رابط': 'draft'}
    assert len(ctx) == 6                                              # الاستيراد نفسه كما هو (المسودة تظهر في اللوحة)
    assert out['prerender']['reason'] == 'sync:+2'                    # الدفع للزواحف عن المنشور فقط


def test_a_clean_sync_reports_an_empty_held_no_source(ctx, monkeypatch):
    _serve(monkeypatch, [_art('A1', 'دليل أول'), _art('A2', 'خبر سليم', 'news', source_url=SRC)])
    out, _ = appmod._sync_platform_articles()
    assert out['held_no_source'] == [] and out['published'] == 2


def test_the_source_rule_also_holds_when_autopublish_is_off(ctx, monkeypatch):
    monkeypatch.setenv('BLOG_AUTOPUBLISH_ALL', 'false')
    _serve(monkeypatch, [_art('A1', 'خبر بلا مصدر', 'news', status='published')])
    out, _ = appmod._sync_platform_articles()
    assert out['published'] == 0 and len(out['held_no_source']) == 1
