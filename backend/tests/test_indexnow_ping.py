import json


def test_indexnow_ping_builds_urls_from_changed_pre_pages(tmp_path, monkeypatch):
    import app as A
    feed = tmp_path / "f.json"
    feed.write_text(json.dumps({"articles": [{"id": 5, "slug": "عقد-5"}, {"id": 6, "slug": "x-6"}]}), encoding="utf-8")
    sent = {}

    class R:
        status_code = 200

    def fake_post(url, json=None, timeout=0):
        sent["url"], sent["body"] = url, json
        return R()
    monkeypatch.setattr(A.requests, "post", fake_post)
    out = A._indexnow_ping(["blog/_pre/5.html", "blog.html", "feed.xml"], str(feed))
    assert out == {"urls": 2, "status": 200}
    assert sent["url"] == "https://api.indexnow.org/indexnow"
    assert sent["body"]["urlList"][0].startswith("https://elprofessor.net/blog/%D8%B9")
    assert sent["body"]["keyLocation"].endswith(A.INDEXNOW_KEY + ".txt")
    assert A._indexnow_ping([], str(feed)) is None
