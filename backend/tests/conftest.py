"""Make `import app` work for tests that live in this sub-directory.

The historical suite is flat (`backend/test_*.py`), so pytest's rootdir insertion put
`backend/` on sys.path for free. Files under `backend/tests/` get `backend/tests/` inserted
instead — so add the parent explicitly. Env defaults use setdefault: when the flat modules
run first they have already imported `app` with their own temp SQLite, and re-pointing
DATABASE_URL here would be a silent no-op that looks like it worked.
"""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

os.environ.setdefault(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(tempfile.mkdtemp(), 'xss_hardening_test.db'),
)
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-xss-hardening')
os.environ.setdefault('METRICS_SECRET', 'test-metrics-secret')
