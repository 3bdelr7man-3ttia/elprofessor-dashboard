"""F-021 — الداشبورد يرفض الإقلاع بلا SECRET_KEY قويّ (بعد تأكيد المؤسس وجوده في Coolify)."""
import os, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _boot(env_overrides):
    env = {k: v for k, v in os.environ.items() if k not in ('SECRET_KEY', 'ALLOW_WEAK_SECRET_KEY')}
    env.update(env_overrides)
    return subprocess.run([sys.executable, '-c', 'import app'], cwd=HERE, env=env,
                          capture_output=True, text=True, timeout=120)


def test_missing_secret_key_refuses_to_boot():
    r = _boot({})
    assert r.returncode != 0
    assert 'FATAL: SECRET_KEY' in (r.stdout + r.stderr)


def test_repo_placeholder_refuses_to_boot():
    r = _boot({'SECRET_KEY': 'change-this-in-coolify-to-a-long-random-secret'})
    assert r.returncode != 0
    assert 'FATAL: SECRET_KEY' in (r.stdout + r.stderr)


def test_strong_secret_key_boots():
    r = _boot({'SECRET_KEY': '8f' * 32})
    assert r.returncode == 0, r.stderr[-800:]


def test_local_escape_hatch_still_boots_without_a_key():
    r = _boot({'ALLOW_WEAK_SECRET_KEY': '1'})
    assert r.returncode == 0, r.stderr[-800:]
