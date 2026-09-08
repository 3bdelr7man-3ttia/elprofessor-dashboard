"""جذر طقم الداشبورد (الاختبارات المسطّحة test_*.py هنا لا ترى tests/conftest.py).
F-021: التطبيق يرفض الإقلاع بلا SECRET_KEY قويّ ⇒ الاختبارات تقلع بمفتاحٍ ثابتٍ قويّ (لا صمّام التشغيل المحلّي،
حتى يبقى الرفض نفسه مُختبَرًا في tests/test_secret_key_fail_fast.py)."""
import os
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-the-dashboard-suite-0123456789')
