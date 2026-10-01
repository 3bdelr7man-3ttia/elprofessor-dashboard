# -*- coding: utf-8 -*-
"""الروابط الداخلية «اقرأ أيضًا» + المسودّات المكرّرة — إصلاح مصنع المقالات ٢٠٢٦-١٠-٠١.

القياس الذي استدعاه: صفر روابط داخلية في ١٨٩٣ كتلة متن على المدوّنة، و٦٥ مسودّةً عالقة على المنصّة
لأن المزامنة كانت تتخطّى العنوان المكرّر ولا تُخرجه من الطابور.

⛔ فخّ «مكتوبٌ ولا يُرسم» (ذاكرة written_but_never_rendered): الاختبار الأخير يمرّر الكتل التي تنتجها
هذه المزامنة نفسها عبر `prerender.py` الحقيقي ومُصيِّر `article.html` الحقيقي من ريبو الموقع، ويفحص
أن `<a href="https://elprofessor.net/blog/…">` موجودٌ فعلًا في الصفحة الثابتة — وأن `javascript:`
لا يصير رابطًا أبدًا.

Run:  cd backend && python3 -m pytest -q tests/test_related_links.py
"""
import datetime
import json
import os
import shutil
import subprocess
import tempfile

import pytest

import app as appmod  # noqa: E402
from app import app as flask_app, db, Article  # noqa: E402

SITE_DIR = os.path.expanduser(os.environ.get('EP_SITE_REPO', '~/elprofessor-site'))
PRERENDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'prerender.py')

LONG = ('هذا نص تجريبي طويل يشرح المبدأ القانوني بالتفصيل ويعطي القارئ خطوات عملية واضحة. ' * 12).strip()


@pytest.fixture
def ctx():
    with flask_app.app_context():
        db.create_all()
        Article.query.delete()
        db.session.commit()
        yield
        Article.query.delete()
        db.session.commit()


def _pub(title, keywords=(), audience='المحامون', body=None, excerpt='مقتطف'):
    a = Article(title=title, excerpt=excerpt, cat='دليل', kicker='تحليل قانوني', by='فريق البروفيسور',
                date='١ أكتوبر ٢٠٢٦', body=json.dumps(body or ['## ' + title, LONG, LONG], ensure_ascii=False),
                keywords=json.dumps(list(keywords), ensure_ascii=False), faq='[]',
                target_audience=audience, status='published',
                published_at=datetime.datetime(2026, 9, 1))
    db.session.add(a)
    db.session.commit()
    return a


# ——— ١) المتن: رابط الموقع يعبر، وكل ما عداه يُنزع ———

def test_md_to_blocks_keeps_only_same_site_blog_links():
    md = ('# عنوان\n\nانظر [صياغة عقد الصلح](https://elprofessor.net/blog/%D8%B5%D9%8A-12) و'
          '[موقع آخر](https://evil.example/x) و[خبيث](javascript:alert(1)) و[نسبي](/blog/abc-3).\n'
          '- [بند](https://elprofessor.net/blog/x-9)')
    blocks = appmod._md_to_blocks(md)
    joined = '\n'.join(blocks)
    assert '[صياغة عقد الصلح](https://elprofessor.net/blog/%D8%B5%D9%8A-12)' in joined
    assert '[نسبي](/blog/abc-3)' in joined
    assert '• [بند](https://elprofessor.net/blog/x-9)' in joined
    assert 'evil.example' not in joined and 'javascript' not in joined
    assert 'موقع آخر' in joined and 'خبيث' in joined          # the text survives, the link does not


# ——— ٢) اختيار ذي الصلة ———

def test_related_prefers_overlap_and_requires_two(ctx):
    a1 = _pub('صياغة عقد التوريد: البنود التي تحمي المورّد', ['عقد توريد', 'صياغة العقود'])
    a2 = _pub('أخطاء صياغة العقود: عشرة عيوب تظهر لحظة الخلاف', ['صياغة العقود'])
    _pub('التقديم لوظيفة معاون نيابة: الشروط والأوراق', ['النيابة العامة'], audience='وكلاء النيابة')
    pool = Article.query.filter_by(status='published').all()
    rel = appmod._related_articles('صياغة العقود التجارية: دليل للمحامي', ['صياغة العقود'], 'المحامون', pool)
    assert [a.id for a in rel][:2] == [a1.id, a2.id] or {a.id for a in rel} >= {a1.id, a2.id}
    assert all('نيابة' not in a.title for a in rel)          # no link without real overlap
    blocks, n = appmod._with_related(['فقرة'], 'صياغة العقود التجارية', ['صياغة العقود'], 'المحامون', pool)
    assert n == 2 and blocks[1] == appmod.RELATED_HEADING
    assert blocks[2].startswith('• [') and '](https://elprofessor.net/blog/' in blocks[2]
    # only one related candidate → no «اقرأ أيضًا» with a lonely link
    blocks, n = appmod._with_related(['فقرة'], 'معاون نيابة إدارية', ['النيابة'], 'وكلاء النيابة', pool)
    assert n == 0 and blocks == ['فقرة']


# ——— ٣) المزامنة: مكرّرٌ يُعلَّم ولا يُحذف، والجديد يحمل روابطه ———

class _Resp:
    def __init__(self, data, code=200):
        self._d, self.status_code = data, code

    def json(self):
        return self._d


def test_sync_marks_title_duplicates_and_links_new_articles(ctx, monkeypatch):
    _pub('صياغة عقد التوريد: البنود التي تحمي المورّد', ['صياغة العقود'])
    _pub('أخطاء صياغة العقود: عشرة عيوب تظهر لحظة الخلاف', ['صياغة العقود'])
    drafts = [
        {'id': 'ART_dup', 'title': 'صياغة عقد التوريد: البنود التي تحمي المورّد', 'body': '# x\nنص',
         'category': 'guide', 'status': 'draft'},
        {'id': 'ART_new', 'title': 'صياغة العقود التجارية: المراحل والأخطاء', 'body': '# t\n\nنص المقال',
         'category': 'guide', 'status': 'draft', 'keywords': ['صياغة العقود'], 'target_audience': 'المحامون'},
    ]
    calls = []
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', 'sec')
    monkeypatch.setattr(appmod.requests, 'get', lambda *a, **k: _Resp({'articles': drafts}))
    monkeypatch.setattr(appmod.requests, 'post', lambda url, **k: calls.append(('POST', url)) or _Resp({}))
    monkeypatch.setattr(appmod.requests, 'delete', lambda url, **k: calls.append(('DELETE', url)) or _Resp({}))
    monkeypatch.setattr(appmod, '_prerender_push_async', lambda reason='': {'state': 'stub'})
    out, status = appmod._sync_platform_articles()
    assert status == 200 and out['imported'] == 1 and out['duplicates'] == 1 and out['with_related_links'] == 1
    assert ('POST', appmod.PLATFORM_API_URL + '/api/bridge/articles/ART_dup/mark-duplicate') in calls
    assert not any(m == 'DELETE' and 'ART_dup' in u for m, u in calls)   # never destroyed
    new = Article.query.filter_by(title='صياغة العقود التجارية: المراحل والأخطاء').first()
    body = json.loads(new.body)
    assert appmod.RELATED_HEADING in body and sum(1 for b in body if b.startswith('• [')) == 2


# ——— ٤) الردم: تجربة جافّة لا تكتب، والتطبيق يكتب مرّة واحدة ———

def test_backfill_dry_run_then_apply_is_idempotent(ctx, monkeypatch):
    for t in ('صياغة عقد التوريد', 'أخطاء صياغة العقود', 'صياغة العقود التجارية', 'مراجعة العقد قبل التوقيع'):
        _pub(t + ': دليل', ['صياغة العقود', 'العقود'])
    dry = appmod._backfill_related(apply=False)
    assert dry['would_link'] == 4 and dry['applied'] is False
    assert all(appmod.RELATED_HEADING not in (a.body or '') for a in Article.query.all())
    done = appmod._backfill_related(apply=True)
    assert done['would_link'] == 4
    assert all(appmod.RELATED_HEADING in (a.body or '') for a in Article.query.all())
    again = appmod._backfill_related(apply=True)
    assert again['would_link'] == 0 and again['already_linked'] == 4


def test_backfill_endpoint_is_secret_gated_and_dry_by_default(ctx, monkeypatch):
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', 'sec')
    c = flask_app.test_client()
    assert c.post('/api/content/backfill-related').status_code == 401
    _pub('صياغة عقد التوريد: دليل', ['صياغة العقود'])
    r = c.post('/api/content/backfill-related', headers={'X-ELP-Metrics-Secret': 'sec'})
    assert r.status_code == 200 and r.get_json()['applied'] is False


# ——— ٥) من الكتلة إلى الصفحة: prerender.py + article.html الحقيقيان ———

@pytest.mark.skipif(not (shutil.which('node') and os.path.isfile(os.path.join(SITE_DIR, 'article.html'))),
                    reason='needs node + the marketing-site repo (EP_SITE_REPO)')
def test_related_links_reach_the_prerendered_page_and_js_links_never_do(ctx):
    arts = [_pub('صياغة عقد التوريد: البنود التي تحمي المورّد %d' % i, ['صياغة العقود']) for i in range(3)]
    for i in range(30):   # blog.html's own verifier wants a realistically full index page (≥5000 chars)
        _pub('مقال تحليلي عن موضوع قانوني مختلف رقم %d' % i, ['موضوع'], excerpt=LONG[:160])
    pool = Article.query.filter_by(status='published').all()
    blocks = appmod._md_to_blocks('# عنوان\n\n' + LONG + '\n\nخبيث [اضغط](javascript:alert(1)) هنا.')
    # the dashboard already strips it; inject a raw one too, as if an admin typed it in the editor
    blocks.append('رابط مدسوس [اضغط هنا](javascript:alert(document.cookie)) نهاية')
    blocks, n = appmod._with_related(blocks, 'صياغة العقود التجارية', ['صياغة العقود'], 'المحامون', pool)
    assert n >= 2
    target = _pub('صياغة العقود التجارية: المراحل', ['صياغة العقود'], body=blocks)
    feed = {'source': 'dashboard',
            'articles': [appmod.serialize_article(a) for a in Article.query.filter_by(status='published').all()]}
    tmp = tempfile.mkdtemp(prefix='prerender-test-')
    try:
        for name in ('article.html', 'blog.html'):
            shutil.copy(os.path.join(SITE_DIR, name), os.path.join(tmp, name))
        os.makedirs(os.path.join(tmp, 'blog', '_pre'))
        ff = os.path.join(tmp, '_feed.json')
        with open(ff, 'w', encoding='utf-8') as fh:
            json.dump(feed, fh, ensure_ascii=False)
        proc = subprocess.run(['python3', PRERENDER, '--site', tmp, '--feed-file', ff, '--min-articles', '1'],
                              capture_output=True, text=True, timeout=300)
        assert proc.returncode == 0, proc.stderr[-1500:]
        page = open(os.path.join(tmp, 'blog', '_pre', '%d.html' % target.id), encoding='utf-8').read()
        for a in arts[:2]:
            assert ('<a class="inlink" href="%s">' % appmod._blog_url(a)) in page
        assert 'اقرأ أيضًا' in page
        assert 'href="javascript' not in page.lower() and 'اضغط هنا' in page
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
