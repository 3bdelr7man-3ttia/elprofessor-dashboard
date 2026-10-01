"""طلب prerender يصل والتوليد شغّال لازم يعمل دورة إضافية بعده — مش يتبلع (عطل 2026-10-01)."""
import threading
import app as appmod


def test_request_during_a_run_triggers_exactly_one_more_pass(monkeypatch):
    started, release, calls = threading.Event(), threading.Event(), []

    def fake_push(reason=''):
        calls.append(reason)
        if len(calls) == 1:
            started.set()
            release.wait(5)

    monkeypatch.setattr(appmod, '_prerender_push', fake_push)
    monkeypatch.setattr(appmod, '_prerender_running', False)
    monkeypatch.setattr(appmod, '_prerender_pending', None)
    assert appmod._prerender_push_async('first')['state'] == 'started'
    assert started.wait(5)
    assert appmod._prerender_push_async('second')['state'] == 'queued-after-current'
    assert appmod._prerender_push_async('third')['state'] == 'queued-after-current'   # coalesced
    release.set()
    for _ in range(100):
        if not appmod._prerender_running:
            break
        threading.Event().wait(0.05)
    assert calls == ['first', 'third']     # one extra pass, carrying the latest reason
    assert appmod._prerender_running is False and appmod._prerender_pending is None


class _FakeSftp:
    def __init__(self, names):
        self.names, self.removed = list(names), []

    def listdir(self, d):
        return list(self.names)

    def remove(self, p):
        self.removed.append(p.rsplit('/', 1)[-1])


def test_remote_prune_removes_only_orphan_article_pages():
    fresh = {'blog.html': 'h', 'feed.xml': 'h', 'blog/_pre/manifest.txt': 'h',
             'blog/_pre/7.html': 'h', 'blog/_pre/79.html': 'h'}
    sftp = _FakeSftp(['7.html', '79.html', '240.html', '28.html', 'manifest.txt',
                      '7.html.tmp', 'index.html', 'notes.html'])
    assert appmod._prerender_prune_remote(sftp, '/r/blog/_pre', fresh) == 2
    assert sorted(sftp.removed) == ['240.html', '28.html']   # numeric orphans only


def test_remote_prune_refuses_to_wipe_on_an_empty_generation():
    sftp = _FakeSftp(['7.html', '79.html'])
    assert appmod._prerender_prune_remote(sftp, '/r/blog/_pre', {'blog.html': 'h'}) == 0
    assert sftp.removed == []


class _FakeGoneSftp:
    def __init__(self, names=(), exists=True):
        self.names, self.exists, self.put, self.removed, self.made = set(names), exists, [], [], []

    def stat(self, d):
        if not self.exists:
            raise IOError

    def mkdir(self, d):
        self.made.append(d)
        self.exists = True

    def listdir(self, d):
        return list(self.names)

    def putfo(self, fo, p):
        self.put.append(p.rsplit('/', 1)[-1])

    def remove(self, p):
        self.removed.append(p.rsplit('/', 1)[-1])


def test_gone_markers_track_retracted_articles_exactly():
    sftp = _FakeGoneSftp(names={'240', '79', 'README'}, exists=False)
    out = appmod._prerender_sync_gone(sftp, '/r/blog/_gone', {'240', '28'})
    assert sftp.made == ['/r/blog/_gone']
    assert sftp.put == ['28']            # 240 already marked
    assert sftp.removed == ['79']        # 79 republished → its marker goes; non-numeric files untouched
    assert out == {'added': 1, 'removed': 1, 'total': 2}


def test_retracted_ids_are_drafts_that_were_once_published():
    import datetime, json
    from app import app as flask_app, db, Article
    with flask_app.app_context():
        db.create_all()
        Article.query.delete()
        mk = lambda t, st, pub: Article(title=t, excerpt='', cat='دليل', kicker='', by='', date='', body='[]',
                                        keywords='[]', faq='[]', target_audience='عام', status=st, published_at=pub)
        when = datetime.datetime(2026, 9, 1)
        a, b, c = mk('مسحوب', 'draft', when), mk('منشور', 'published', when), mk('مسودة جديدة', 'draft', None)
        db.session.add_all([a, b, c])
        db.session.commit()
        assert appmod._retracted_article_ids() == {str(a.id)}
        Article.query.delete()
        db.session.commit()
