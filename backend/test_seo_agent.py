"""Self-tests for the SEO/AEO agent scorecard (deterministic article checks).

Run:  cd backend && python -m pytest test_seo_agent.py -v
"""
import os
import tempfile

# Point the app at a throwaway SQLite file BEFORE importing the app module.
_tmpdir = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_tmpdir, 'seo_test.db')}"
os.environ['SECRET_KEY'] = 'test-secret-key-for-seo'
os.environ['METRICS_SECRET'] = 'test-metrics-secret'

import app as appmod  # noqa: E402


def _good_article():
    body = ("# عنوان قوي عن تحصيل الأتعاب\n\nإجابة مباشرة في أول فقرة تلخّص الموضوع بوضوح. " +
            "نص طويل ومفيد وعملي للمحامي. " * 200 +
            "\n\n## القسم الأول\nمحتوى.\n\n## القسم الثاني\nمحتوى.\n\n## الأسئلة الشائعة\n### سؤال؟\nإجابة.")
    return {
        'id': 'A1', 'title': 'دليل المحامي لتحصيل الأتعاب دون إحراج بخطوات عملية',
        'status': 'published', 'category': 'guide', 'body': body,
        'meta_description': ('دليل عملي للمحامي لتحصيل الأتعاب دون إحراج مع صيغة اتفاق مكتوبة تحميك '
                             'قانونًا وخطوات واضحة تقدر تطبّقها من اليوم مع موكليك.'),
        'keywords': ['تحصيل الأتعاب', 'اتفاق أتعاب', 'المحامي', 'مصر'],
        'faq': [{'q': 'كيف؟', 'a': 'كذا.'}],
    }


def test_good_article_scores_high():
    c = appmod._seo_scorecard(_good_article())
    assert c['score'] >= 85 and c['has_faq'] and c['keywords_count'] >= 3
    assert c['issues'] == [] or all('منافسة' not in i for i in c['issues'])


def test_thin_article_flagged():
    c = appmod._seo_scorecard({'id': 'A2', 'title': 'قصير', 'status': 'draft',
                               'body': 'كلمتين وخلاص.', 'meta_description': '', 'keywords': [], 'faq': []})
    assert c['score'] < 60
    joined = ' '.join(c['issues'])
    assert 'وصف ميتا' in joined and 'كلمة' in joined and 'أسئلة شائعة' in joined


def test_competitor_mention_is_heavily_penalised():
    a = _good_article()
    a['body'] += '\n\nتقدر تتعلم على Udemy و LinkedIn Learning كمان.'
    c = appmod._seo_scorecard(a)
    assert any('منافسة' in i for i in c['issues']) and c['score'] <= 70


def test_json_faq_parser():
    import json as _json
    assert appmod._json_faq(None) == []
    assert appmod._json_faq('not json') == []
    assert appmod._json_faq(_json.dumps([{'q': 'س', 'a': 'ج'}, {'q': '', 'a': 'x'}, {'bad': 1}])) == [{'q': 'س', 'a': 'ج'}]
    assert appmod._json_list(_json.dumps(['ك1', 'ك2'])) == ['ك1', 'ك2']


def test_seo_bundle_degrades_without_bridge(monkeypatch):
    # no platform secret / bridge → _bridge_get returns None → empty but well-formed bundle, never raises
    monkeypatch.setattr(appmod, '_bridge_get', lambda *a, **k: None)
    b = appmod._seo_bundle()
    assert b['total_articles'] == 0 and b['avg_seo_score'] is None and b['weakest_articles'] == []
