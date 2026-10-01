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
