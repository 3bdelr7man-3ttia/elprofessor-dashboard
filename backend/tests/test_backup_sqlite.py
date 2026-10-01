# -*- coding: utf-8 -*-
"""نسخة احتياطية حيّة لقاعدة الداشبورد (F-162) — تسبق أي هجرة على جدول المقالات.
المخرَج قاعدةٌ تُفتح ويُقرأ منها صفٌّ كُتب قبل النسخ، لا بايتات فقط.
Run:  cd backend && python3 -m pytest -q tests/test_backup_sqlite.py
"""
import gzip
import io
import os
import sqlite3
import tempfile

import pytest

SECRET = 'backup-bridge-service-secret'
URL = '/api/bridge/backup/sqlite'


@pytest.fixture()
def mod():
    import app as m
    return m


@pytest.fixture()
def client(monkeypatch, mod):
    monkeypatch.setattr(mod, 'PLATFORM_METRICS_SECRET', SECRET, raising=False)
    with mod.app.app_context():
        mod.db.create_all()
    with mod.app.test_client() as c:
        yield c


def test_closed_without_secret(client):
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={'X-ELP-Metrics-Secret': 'wrong'}).status_code == 401


def test_dump_is_a_real_database(client, mod):
    with mod.app.app_context():
        if not mod._sqlite_file_path():
            pytest.skip('suite DB is not a file-backed sqlite')
    with mod.app.app_context():
        mod.db.session.execute(mod.db.text("CREATE TABLE IF NOT EXISTS zz_backup_probe (id INTEGER PRIMARY KEY, v TEXT)"))
        mod.db.session.execute(mod.db.text("INSERT INTO zz_backup_probe (v) VALUES ('قيمة قبل النسخ')"))
        mod.db.session.commit()
    r = client.get(URL, headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 200, r.data[:200]
    raw = gzip.GzipFile(fileobj=io.BytesIO(r.data)).read()
    assert raw[:16] == b'SQLite format 3\x00'
    out = os.path.join(tempfile.mkdtemp(), 'restored.db')
    open(out, 'wb').write(raw)
    con = sqlite3.connect(out)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == 'ok'
        assert ('قيمة قبل النسخ',) in con.execute("SELECT v FROM zz_backup_probe").fetchall()
    finally:
        con.close()
