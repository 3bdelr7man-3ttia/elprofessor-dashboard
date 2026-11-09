# -*- coding: utf-8 -*-
"""R17 — حارس الصلة بالقانون في مزامنة المقالات: مقال ختمته المنصة `legal_gate.ok=false` ما يتنشرش آليًّا أبدًا.

`BLOG_AUTOPUBLISH_ALL` افتراضيه true (كل اللي بيطلعه المولّد بيتنشر على الموقع) — الختم بيغلبه: المقال بيدخل المدوّنة
مسودة للمراجعة. غياب الختم (مقال قديم أو شرح المنصة) = السلوك القديم بالظبط.

Run:  cd backend && python3 -m pytest -q tests/test_sync_legal_gate.py
⛔ صفر شبكة: المنصة مستبدَلة بردّ ثابت، والدفع للاستضافة مستبدَل.
"""
import pytest

import app as appmod  # noqa: E402
from app import app as flask_app, db, Article, ArticleVersion  # noqa: E402

SECRET = 'sync-legal-gate-secret'
PARA = ('هذا نص تجريبي طويل يشرح المبدأ القانوني بالتفصيل ويعطي القارئ خطوات عملية واضحة. ' * 6).strip()


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


def _art(aid, title, gate='absent', category='news'):
    a = {'id': aid, 'title': title, 'body': '# ' + title + '\n\n' + PARA, 'category': category, 'author': 'x', 'keywords': [], 'faq': [],
         'source_url': 'https://news.example.com/' + aid}   # R19: مقال الخبر لازم له رابط مصدر
    if gate != 'absent':
        a['legal_gate'] = gate
    return a


def test_a_gated_article_lands_as_a_draft_even_with_autopublish_all(ctx, monkeypatch):
    _serve(monkeypatch, [
        _art('ART_off', 'خبر لا علاقة له بالقانون', {'ok': False, 'reason': 'off-theme', 'by': 'rule'}),
        _art('ART_ok', 'تعديل قانون الإجراءات الجنائية الجديد', {'ok': True, 'reason': 'ok:legislation', 'by': 'rule'}),
        _art('ART_old', 'مقال قديم بلا ختم'),
        _art('ART_null', 'مقال ختمه غير محسوم', {'ok': None}),
    ])
    out, st = appmod._sync_platform_articles()
    assert st == 200 and out['imported'] == 4 and out['published'] == 3 and out['drafts'] == 1 and out['held_not_legal'] == 1
    by = {a.title: a.status for a in Article.query.all()}
    assert by == {'خبر لا علاقة له بالقانون': 'draft', 'تعديل قانون الإجراءات الجنائية الجديد': 'published',
                  'مقال قديم بلا ختم': 'published', 'مقال ختمه غير محسوم': 'published'}
    assert sorted(ctx) == ['ART_null', 'ART_off', 'ART_ok', 'ART_old']      # الاستيراد نفسه زي ما هو (المسودة تتراجع في المدوّنة)


def test_even_a_feature_explainer_is_held_when_the_platform_stamped_it(ctx, monkeypatch):
    _serve(monkeypatch, [_art('ART_f', 'شرح ميزة', {'ok': False}, category='feature')])
    out, _ = appmod._sync_platform_articles()
    assert out['published'] == 0 and Article.query.first().status == 'draft'
