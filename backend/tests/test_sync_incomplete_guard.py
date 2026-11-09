# -*- coding: utf-8 -*-
"""R19 — حارس الاكتمال في مزامنة المقالات: متنٌ مبتور ما يتنشرش آليًّا أبدًا.

القياس (٢٠٢٦-١١-٠٩): ١٥ من ٢٢٤ مقالًا منشورًا مبتورة (مقال ٣٥٤ «٦ خطوات» يقف عند ٤، ٣٤٤ ينتهي بعنوان
«## أخطاء تراكم»، ٢٨٦ بعنوان «## س»، وأخبار تنتهي وسط الكلمة). الحارس يقرأ المتن نفسه — ولا يعتمد على المنصّة.

Run:  cd backend && python3 -m pytest -q tests/test_sync_incomplete_guard.py
⛔ صفر شبكة: المنصّة مستبدَلة بردّ ثابت، والدفع للاستضافة مستبدَل.
"""
from pathlib import Path

import pytest

import app as appmod  # noqa: E402
import article_integrity as ai  # noqa: E402
from app import app as flask_app, db, Article, ArticleVersion  # noqa: E402

SECRET = 'sync-incomplete-guard-secret'
PARA = ('هذا نص تجريبي طويل يشرح المبدأ القانوني بالتفصيل ويعطي القارئ خطوات عملية واضحة. ' * 6).strip()
ROOT = Path(__file__).resolve().parents[2]


# ——— الدالة النقيّة ———

def test_complete_bodies_are_not_flagged():
    assert ai.incomplete_reasons(['مقدمة تنتهي بنقطة.', '## ١. أولًا', PARA, '## الخطوة التالية', PARA], 'دليل: ٢ خطوات') == []
    assert ai.incomplete_reasons([PARA, 'جملة تنتهي بعلامة استفهام؟'], '') == []
    assert ai.incomplete_reasons([PARA, 'وختامها «اقتباس»'], '') == []
    # أقسام الروابط المرسومة آليًّا لا تُحسب «آخر المتن»
    assert ai.incomplete_reasons([PARA, '## اقرأ أيضًا', '• [مقال](https://elprofessor.net/blog/x)'], '') == []


def test_each_truncation_shape_is_caught():
    # (أ) وسط الكلمة/الجملة — مقالات ٢٣٠ و٢١٩ و٢٠٥ و١٧٧
    assert ai.incomplete_reasons([PARA, 'ويبقى الأمل على تكث'], '') == ['no_terminal_punctuation']
    # (ب) بند قائمة مقطوع — مقال ٣٥٤
    assert 'no_terminal_punctuation' in ai.incomplete_reasons([PARA, '• تعارض المصالح: إفصاح دوري، لا مرة'], '')
    # (ج) ينتهي بعنوان — مقالا ٣٤٤ و٢٨٦
    assert ai.incomplete_reasons([PARA, '## أخطاء تراكم'], '') == ['ends_on_heading']
    # (د) ينتهي بتمهيد قائمة لم تأتِ
    assert ai.incomplete_reasons([PARA, 'راجع هذه النقاط:'], '') == ['no_terminal_punctuation']
    # (هـ) جدول مفتوح
    assert ai.incomplete_reasons([PARA, '| العمود | القيمة |'], '') == ['ends_in_table']
    # (و) فارغ
    assert ai.incomplete_reasons([], 'x') == ['empty_body']
    assert ai.incomplete_reasons(['## اقرأ أيضًا', '• [م](https://elprofessor.net/blog/a)'], '') == ['empty_body']


def test_promised_step_count_vs_numbered_sections():
    body = [PARA, '## ١. أ', PARA, '## ٢. ب', PARA, '## ٣. ج', PARA, '## ٤. د', PARA]
    assert ai.incomplete_reasons(body, 'مكتب محاماة دولي: ٦ خطوات لتأهيل ملف') == ['promised_6_got_4']
    assert ai.incomplete_reasons(body, 'كذا: 4 خطوات') == []
    # «٦ محاور» لا تُقارَن: مقالا ٣٣٩ و٢٩٢ سليمان وعناوينهما غير مرقّمة بالعدد الموعود
    assert ai.incomplete_reasons(body, 'شهادة: ٦ محاور أساسية') == []


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


def _art(aid, title, body, category='guide'):
    return {'id': aid, 'title': title, 'body': body, 'category': category, 'author': 'x', 'keywords': [], 'faq': []}


def test_a_truncated_article_lands_as_a_draft_even_with_autopublish_all(ctx, monkeypatch):
    _serve(monkeypatch, [
        _art('A_ok', 'مقال كامل', '# مقال كامل\n\n' + PARA),
        _art('A_cut', 'خبر مقطوع', '# خبر مقطوع\n\n' + PARA + '\n\nويبقى الأمل على تكث'),
        _art('A_head', 'مقال ينتهي بعنوان', '# مقال ينتهي بعنوان\n\n' + PARA + '\n\n## أخطاء تراكم'),
        _art('A_steps', 'دليل: ٦ خطوات للتأهيل',
             '# دليل\n\n' + PARA + '\n\n## ١. أ\n\n' + PARA + '\n\n## ٢. ب\n\n' + PARA + '.'),
    ])
    out, st = appmod._sync_platform_articles()
    assert st == 200 and out['imported'] == 4 and out['published'] == 1 and out['drafts'] == 3
    assert {h['title'] for h in out['held_incomplete']} == {'خبر مقطوع', 'مقال ينتهي بعنوان', 'دليل: ٦ خطوات للتأهيل'}
    by = {a.title: a.status for a in Article.query.all()}
    assert by == {'مقال كامل': 'published', 'خبر مقطوع': 'draft', 'مقال ينتهي بعنوان': 'draft',
                  'دليل: ٦ خطوات للتأهيل': 'draft'}
    assert sorted(ctx) == ['A_cut', 'A_head', 'A_ok', 'A_steps']      # الاستيراد نفسه كما هو (المسودة تظهر في اللوحة)
    assert out['prerender']['reason'] == 'sync:+1'                      # الدفع للزواحف عن المنشور الوحيد فقط


def test_the_module_ships_in_both_dockerfiles():
    """app.py يستورد article_integrity عند الإقلاع؛ غيابه من الـDockerfile = الحاوية لا تقوم (فخّ refresh_rules)."""
    assert 'article_integrity.py' in (ROOT / 'Dockerfile').read_text('utf-8')
    assert 'article_integrity.py' in (ROOT / 'backend' / 'Dockerfile').read_text('utf-8')
