# -*- coding: utf-8 -*-
"""R19 — إصلاح المقالات المنشورة المبتورة مرة واحدة (قرار المؤسس 2026-11-09 «المقالات المتقطعة ظبطها»).

القصّ بس (بلا كلام جديد) للي ناقصهم ذيل، والمسودة للي العنوان بيعد بحاجة مش موجودة أو بقايا قصيرة.
Run:  cd backend && python3 -m pytest -q tests/test_r19_fix_published_truncated.py
⛔ صفر شبكة: الدفع للاستضافة مستبدَل.
"""
import json

import pytest

import app as appmod  # noqa: E402
import article_integrity as ai  # noqa: E402
from app import app as flask_app, db, Article, ArticleVersion, Setting  # noqa: E402

PARA = ('هذا نص تجريبي طويل يشرح المبدأ القانوني بالتفصيل ويعطي القارئ خطوات عملية واضحة. ' * 3).strip()
LINKS = ['## اقرأ أيضًا', '• [مقال](https://elprofessor.net/blog/x)']


# ——— القصّ (دالة نقيّة) ———

def test_mid_word_tail_is_cut_back_to_the_last_full_sentence():
    new, acts = ai.repair_tail([PARA, PARA + ' ويبقى الأمل على تكث'])
    assert acts == ['trim_sentence'] and new[-1].endswith('واضحة.') and ai.incomplete_reasons(new) == []


def test_a_cut_list_line_is_dropped_whole_not_left_as_a_bare_number():
    blk = '4. المصادر: النص الساري وقت إصدار الرأي.\n5. التحليل: ربط النص بالوقائع، لا سرد'
    new, acts = ai.repair_tail([PARA, blk])
    assert acts == ['drop_line'] and new[-1].endswith('الرأي.') and '5.' not in new[-1]


def test_sentence_cut_never_stops_on_a_list_number():
    blk = PARA + ' 4. المصادر القانونية النافذة مع التحقق. 5. التحليل: ربط النص بالوقائع لا سرد'
    new, _ = ai.repair_tail([blk])
    assert new[-1].endswith('التحقق.')


def test_a_fragment_and_the_bare_heading_above_it_are_removed_and_links_kept():
    new, acts = ai.repair_tail([PARA, '## سادسًا: الإعسار', 'هذه أخطر النقاط التي تُترك عادةً لل'] + LINKS)
    assert acts == ['drop_fragment', 'drop_heading'] and new == [PARA] + LINKS


def test_a_trailing_bare_heading_after_a_table_is_removed():
    new, acts = ai.repair_tail([PARA, '| أ | ب |', '## أخطاء تراكم'])
    assert acts == ['drop_heading'] and new[-1] == '| أ | ب |'


def test_a_complete_article_is_never_touched_and_repair_is_idempotent():
    assert ai.repair_tail([PARA, PARA] + LINKS) == ([PARA, PARA] + LINKS, [])
    once, _ = ai.repair_tail([PARA, PARA + ' ويبقى الأمل على تكث'])
    assert ai.repair_tail(once)[1] == []


# ——— التطبيق مرة واحدة على المنشور ———

@pytest.fixture
def ctx(monkeypatch):
    pushed = []
    monkeypatch.setattr(appmod, '_prerender_push_async', lambda reason='': pushed.append(reason))
    with flask_app.app_context():
        db.create_all()
        ArticleVersion.query.delete()
        Article.query.delete()
        for k in (appmod.R19_FIX_KEY, appmod.R19_COMPLETE_KEY):
            s = db.session.get(Setting, k)
            if s is not None:
                db.session.delete(s)
        db.session.commit()
        yield pushed


def _mk(aid, body, status='published'):
    db.session.add(Article(id=aid, title='مقال %d' % aid, body=json.dumps(body, ensure_ascii=False), status=status))


def test_fix_trims_the_listed_tails_drafts_the_broken_ones_and_runs_once(ctx):
    _mk(134, [PARA, PARA + ' جهز جدولًا للاحتفاظ بالبي'])
    _mk(354, [PARA, '• تعارض المصالح: إفصاح دوري، لا مرة'])
    _mk(112, [PARA], status='draft')          # مش منشور ⇒ ما يتلمسش
    _mk(999, [PARA, PARA + ' مقطوع لكن مش في القايمة'])  # برّه القايمة ⇒ ما يتلمسش
    db.session.commit()

    rep = appmod._r19_fix_truncated_articles()
    assert rep['trimmed'] == {134: ['trim_sentence']} and rep['drafted'] == [354] and 112 in rep['skipped']
    assert json.loads(db.session.get(Article, 134).body)[-1].endswith('واضحة.')
    assert db.session.get(Article, 354).status == 'draft'
    assert json.loads(db.session.get(Article, 999).body)[-1].endswith('في القايمة')
    assert ctx == ['r19-truncated-fix']

    # مرة واحدة: علامة settings بتمنع التكرار حتى لو اتنشر المقال تاني
    db.session.get(Article, 354).status = 'published'
    db.session.commit()
    assert appmod._r19_fix_truncated_articles() is None
    assert db.session.get(Article, 354).status == 'published'


# ——— تكميل المسحوبين (مرة واحدة) ———

def test_completion_publishes_only_still_drafted_articles_once(ctx):
    import r19_article_completions as c
    body354 = c.COMPLETED_BODIES['354']
    assert ai.incomplete_reasons(body354, 'مكتب محاماة دولي: ٦ خطوات') == []
    _mk(354, [PARA, '• تعارض المصالح: إفصاح دوري، لا مرة'], status='draft')
    _mk(286, [PARA], status='published')          # المؤسس نشره بإيده ⇒ ما نكتبش فوقه
    db.session.commit()
    rep = appmod._r19_complete_drafted_articles()
    assert rep['published'] == [354] and 286 in rep['skipped']
    a = db.session.get(Article, 354)
    assert a.status == 'published' and json.loads(a.body) == body354
    assert json.loads(db.session.get(Article, 286).body) == [PARA]
    assert appmod._r19_complete_drafted_articles() is None
