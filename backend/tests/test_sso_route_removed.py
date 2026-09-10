# -*- coding: utf-8 -*-
"""إزالة `/api/auth/sso` (2026-09-10) — المنصّة شالت `POST /api/lms/sso/verify` النهارده
(commit 6733465)، فالمسار هنا كان بالفعل عاطلًا (بوّابة المنصّة كانت ترجّع 403 لشهور)
ومقطوعًا (لا استدعاء لـ`?sso=` في أي مكان بـ`dashboard-cloud/` — كل المِنتات كانت في
`frontend/` الـCRA المهجورة على المنصّة، هي كمان اتشالت). هذا الملف يثبّت أن الحذف
كامل ونظيف: لا مسار حيّ، لا استدعاء منسي، ولا رجعة صامتة لسطر `lms/sso/verify`.

Run:  cd backend && python3 -m pytest -q tests/test_sso_route_removed.py
"""
import os

from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User  # noqa: E402

APP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.py')

PW = 'CorrectHorse#42'
EMAIL = 'sso-removed-login@x.test'


def _mkuser(email, active=True, role='admin'):
    u = User.query.filter_by(email=email).first()
    if u:
        u.is_active = active
        u.password_hash = generate_password_hash(PW, method='pbkdf2:sha256')
        db.session.commit()
        return u
    u = User(email=email, password_hash=generate_password_hash(PW, method='pbkdf2:sha256'),
             name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
             preferred_currency='AUTO', is_active=active)
    db.session.add(u)
    db.session.commit()
    return u


def test_sso_route_absent_from_url_map():
    """No rule left whose path IS `/api/auth/sso`, and no `sso_login` view function.
    (A naive substring scan for 'sso' over every rule string is NOT used here — it
    false-positives on `/api/platform-courses/.../le**sso**ns/<lesson_id>/questions`.)"""
    rules = list(flask_app.url_map.iter_rules())
    assert not any(r.rule == '/api/auth/sso' for r in rules), \
        [r.rule for r in rules if 'auth' in r.rule]
    assert 'sso_login' not in flask_app.view_functions


def test_sso_post_gets_the_same_405_as_any_other_unrouted_path():
    """The route+function are gone, so `/api/auth/sso` is just another unmapped path.
    This app's SPA catch-all (`@app.route('/<path:path>')`, app.py, GET-only) still
    matches the URL for METHOD purposes, so Werkzeug answers 405 (method not allowed)
    rather than a bare 404 — identical to any other path nobody ever registered.
    Asserted against a live control path, not a hardcoded status code, so this test
    can't be fooled by that global catch-all changing shape later."""
    client = flask_app.test_client()
    r_sso = client.post('/api/auth/sso', json={'sso': 'anything'})
    r_control = client.post('/api/definitely-never-registered-9f3a', json={})
    assert r_sso.status_code == r_control.status_code == 405, \
        (r_sso.status_code, r_control.status_code)


def test_login_still_works_after_sso_removal():
    """اللوجن العادي (إيميل/باسورد) ما اتلمسش — نفس نمط test_login_lockout.py."""
    with flask_app.app_context():
        db.create_all()
        _mkuser(EMAIL)
    client = flask_app.test_client()
    r = client.post('/api/auth/login', json={'email': EMAIL, 'password': PW})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body.get('token')
    assert body.get('user', {}).get('email') == EMAIL


def test_lms_sso_string_gone_from_app_py():
    """حارس ريجرشِن: لا رجعة صامتة لنداء `/api/lms/sso/verify` — المنصّة نفسها شالته."""
    with open(APP_PY, encoding='utf-8') as f:
        src = f.read()
    assert 'lms/sso' not in src
