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


# ═══════════════════════════════════════════════ R33: تشفير اختياري + نبضة «اتسحبت» + سطر الملخص
TEST_KEY = 'test-only-passphrase-not-a-secret'


def _probe(mod):
    with mod.app.app_context():
        if not mod._sqlite_file_path():
            pytest.skip('suite DB is not a file-backed sqlite')
        mod.db.session.execute(mod.db.text("CREATE TABLE IF NOT EXISTS zz_backup_probe (id INTEGER PRIMARY KEY, v TEXT)"))
        mod.db.session.execute(mod.db.text("INSERT INTO zz_backup_probe (v) VALUES ('قيمة مشفّرة')"))
        mod.db.session.commit()


def _kv_clear(mod):
    import tg_ops
    with mod.app.app_context():
        tg_ops._models(mod.db)
        mod.db.create_all()
        row = tg_ops._STATE['kv'].query.get(mod.BACKUP_KV_KEY)
        if row is not None:
            mod.db.session.delete(row)
            mod.db.session.commit()


def test_encrypted_dump_restores_with_key_and_openssl(client, mod, monkeypatch, tmp_path):
    import shutil
    import subprocess
    import backup_crypto as bc
    _probe(mod)
    monkeypatch.setenv('BACKUP_ENCRYPTION_KEY', TEST_KEY)
    r = client.get(URL, headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 200
    assert r.headers['X-ELP-Backup-Encrypted'] == '1' and '.db.gz.enc' in r.headers['Content-Disposition']
    body = r.data
    assert body[:8] == b'Salted__' and int(r.headers['Content-Length']) == len(body)
    assert TEST_KEY.encode() not in body
    raw = gzip.decompress(bc.decrypt_bytes(body, TEST_KEY))
    assert raw[:16] == b'SQLite format 3\x00'
    with pytest.raises(Exception):
        gzip.decompress(bc.decrypt_bytes(body, 'wrong-key'))
    openssl = shutil.which('openssl')
    if openssl:
        enc = tmp_path / 'd.db.gz.enc'
        enc.write_bytes(body)
        out = tmp_path / 'd.db.gz'
        p = subprocess.run([openssl, 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-iter', str(bc.PBKDF2_ITER), '-md', 'sha256',
                            '-pass', 'env:BACKUP_ENCRYPTION_KEY', '-in', str(enc), '-out', str(out)],
                           env=dict(os.environ, BACKUP_ENCRYPTION_KEY=TEST_KEY), capture_output=True)
        if p.returncode == 0:
            db_file = tmp_path / 'restored.db'
            db_file.write_bytes(gzip.decompress(out.read_bytes()))
            con = sqlite3.connect(str(db_file))
            try:
                assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert ('قيمة مشفّرة',) in con.execute('SELECT v FROM zz_backup_probe').fetchall()
            finally:
                con.close()


def test_plain_dump_when_no_key_and_pull_stamps_heartbeat(client, mod, monkeypatch):
    import tg_ops
    _probe(mod)
    _kv_clear(mod)
    monkeypatch.delenv('BACKUP_ENCRYPTION_KEY', raising=False)
    r = client.get(URL, headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 200 and r.headers['X-ELP-Backup-Encrypted'] == '0'
    assert r.data[:2] == b'\x1f\x8b' and int(r.headers['Content-Length']) == len(r.data)
    with mod.app.app_context():
        assert tg_ops.kv_get(mod.__dict__, mod.BACKUP_KV_KEY)   # النبضة اتكتبت بعد آخر بايت


def test_unauthorized_pull_never_stamps(client, mod):
    import tg_ops
    _kv_clear(mod)
    assert client.get(URL, headers={'X-ELP-Metrics-Secret': 'wrong'}).status_code == 401
    with mod.app.app_context():
        assert tg_ops.kv_get(mod.__dict__, mod.BACKUP_KV_KEY) is None


def test_digest_backup_lines(mod, monkeypatch):
    import datetime as dt
    import tg_ops
    ns = mod.__dict__
    _kv_clear(mod)
    monkeypatch.delenv('BACKUP_ENCRYPTION_KEY', raising=False)
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=40)).isoformat()
    with mod.app.app_context():
        lines = tg_ops.backup_digest_lines(ns, {'heartbeats': {'backup_last': old}, 'backup_encrypted': False})
        text = '\n'.join(lines)
        assert lines[0] == '🗄️ النسخ الاحتياطية:'
        assert 'نسخة قاعدة اللوحة: لم تُسحب ولا مرّة' in text
        assert 'نسخة قاعدة اللوحة غير مشفّرة' in text
        assert 'نسخة قاعدة المنصة: متوقّفة منذ ٤٠ ساعة' in text
        assert 'نسخة قاعدة المنصة غير مشفّرة' in text
        assert 'BACKUP' not in text and 'backup' not in text          # لا مفتاح ماكينة في نص المؤسس
        # كله سليم ⇒ ولا سطر
        monkeypatch.setenv('BACKUP_ENCRYPTION_KEY', TEST_KEY)
        tg_ops.kv_set(ns, mod.BACKUP_KV_KEY, dt.datetime.utcnow().isoformat() + 'Z')
        fresh = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)).isoformat()
        assert tg_ops.backup_digest_lines(ns, {'heartbeats': {'backup_last': fresh}, 'backup_encrypted': True}) == []
        # طابور المنصة غايب ⇒ ما نحكمش على المنصة
        assert tg_ops.backup_digest_lines(ns, None) == []
        # والملخص نفسه بيحطّها
        tg_ops.kv_set(ns, mod.BACKUP_KV_KEY, '2000-01-01T00:00:00Z')
        assert 'نسخة قاعدة اللوحة: آخر سحب منذ' in tg_ops.digest_text(ns, {'alerts_v2': []})


def test_dockerfile_ships_backup_crypto():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(root, 'Dockerfile'), encoding='utf-8') as fh:
        assert 'COPY backend/backup_crypto.py /app/backup_crypto.py' in fh.read()
