# -*- coding: utf-8 -*-
"""تشغيل اللوحة محليًّا فوق `dashboard-cloud/` نفسه لاختبار الواجهة (وأخذ اللقطات).

    python3 run_dash.py <port> <db_path> <platform_base> [msg_count]

⛔ يخدم `dashboard-cloud/` مباشرةً لا `backend/dist`: الملفّ المعدَّل هو ما يُفحَص، وإلا
اختبرنا نسخةً مبنيّةً قديمة وقلنا «شغّال».
⛔ قاعدةٌ مؤقّتة ومنصّةٌ وهميّة: صفر لمسٍ للإنتاج، وصفر نداء ذكاء (المفاتيح تُنزع أدناه).

يبذر: أدمن + **٤٠ رسالة تواصل جديدة** — العدد مقصود: أكبر من السقف الصامت (٢٥) الذي كان
يقصّ الوارد بلا إعلان، فوجود ٤٠ صفًّا في الشاشة هو إثبات اختفاء السقف.

`msg_count` الاختياريّ يرفع العدد فوق `INBOX_SOURCE_CAP` (٥٠٠) لإثبات الوجه الآخر: أن
الإعلان «معروض ٥٠٠ من N» يُرسَم فعلًا يوم يُقَصّ الطابور — ضمانةُ الصدق التي بلا اختبارٍ
يمرّ عليها تبقى كودًا لم يُشغَّل مرّة.
"""
import datetime
import os
import sys

PORT = int(sys.argv[1])
DB_PATH = sys.argv[2]
PLATFORM = sys.argv[3]

_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(_HERE))
ROOT = os.path.dirname(BACKEND)
DC = os.path.join(ROOT, 'dashboard-cloud')

os.environ['DATABASE_URL'] = 'sqlite:///' + DB_PATH
os.environ['SECRET_KEY'] = 'ui-harness-secret-key-0123456789abcdefghij'
os.environ['ADMIN_EMAIL'] = 'admin@local.test'
os.environ['ADMIN_PASSWORD'] = 'LocalVerify!2026'
os.environ['METRICS_SECRET'] = 'ui-harness-bridge-secret'
os.environ['PLATFORM_API_URL'] = PLATFORM
for k in list(os.environ):
    if k.endswith('_API_KEY'):
        os.environ.pop(k, None)      # ⛔ صفر نداء ذكاء من الطقم

sys.path.insert(0, BACKEND)
import app as m                                   # noqa: E402
from flask import send_from_directory             # noqa: E402

MSG_COUNT = int(sys.argv[4]) if len(sys.argv) > 4 else 40

with m.app.app_context():
    if m.Message.query.count() < MSG_COUNT:
        for i in range(MSG_COUNT):
            m.db.session.add(m.Message(
                name='مراسل رقم %d' % (i + 1),
                email='sender%d@example.test' % (i + 1),
                phone='0100000%04d' % i,
                topic='استفسار',
                body='رسالة اختبار رقم %d — نصّها هنا.' % (i + 1),
                status='new',
                created_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=i),
            ))
        m.db.session.commit()


# شركاء: جدول الحصص الذي ابتُلع في «الاستثمار والشركاء». مصدرهم دفتر الداشبورد نفسه
# (`/api/partners` ⇐ SQLite) لا جسر المنصّة — لذلك البذر هنا. «غير موزّع» صفٌّ محجوز
# للاحتياطي: يُعدّ في الحصص ولا يُعدّ في الملّاك، وهو ما يميّزه اختبارُ العدّادات.
with m.app.app_context():
    if m.Partner.query.count() == 0:
        for name, role, eq, cap in (('عبدالرحمن عطية', 'المؤسس', 60.0, 50000.0),
                                    ('شريك تشغيل', 'شريك', 25.0, 20000.0),
                                    ('غير موزّع', 'احتياطي', 15.0, 0.0)):
            m.db.session.add(m.Partner(name=name, role=role, equity_percent=eq, capital_egp=cap))
        m.db.session.commit()


# سحب مستثمرٍ **واحد** معلَّق في دفتر اللوحة (SQLite) — دفترٌ آخر تمامًا غير محافظ المنصّة.
# ⛔ بدونه كان عطل «الشارة تعدّ دفترًا والتبويب يسرد دفترين» غير قابلٍ للسقوط في الطقم:
# صفر مستثمرين = اتفاقٌ بالصدفة. وجودُه هو ما يثبت أن لكل دفترٍ تبويبَه وعدّادَه.
with m.app.app_context():
    if m.WithdrawalRequest.query.count() == 0:
        wal = m.InvestorWallet.query.filter_by(investor_name='مستثمر تجريبي').first()
        if wal is None:
            wal = m.InvestorWallet(investor_name='مستثمر تجريبي', balance=300.0,
                                   total_invested=1000.0, total_returns=300.0)
            m.db.session.add(wal)
            m.db.session.commit()
        # المبلغ بالدولار في هذا الدفتر (`amount_egp` = المبلغ × السعر) ⇒ ١٥٬٠٠٠ ج على الشاشة:
        # هو بعينه الصفّ الذي كان يُجمَع مع سحب المحفظة (١٬٢٠٠) في مربّعٍ واحد فيقول ١٦٬٢٠٠.
        m.db.session.add(m.WithdrawalRequest(wallet_id=wal.id, amount=300.0, status='pending'))
        m.db.session.commit()


@m.app.before_request
def _serve_cloud():
    p = m.request.path
    if p.startswith('/api') or p.startswith('/escrow'):
        return None
    fn = p.lstrip('/')
    if fn and os.path.isfile(os.path.join(DC, fn)):
        return send_from_directory(DC, fn)
    return send_from_directory(DC, 'index.html')


m.app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False, threaded=True)
