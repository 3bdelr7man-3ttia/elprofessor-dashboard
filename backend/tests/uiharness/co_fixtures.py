# -*- coding: utf-8 -*-
"""بذرة قسم «الشركة ورأس المال» للقطات (SPEC-company §11): تكتب في قاعدة الداشبورد المؤقتة فقط — ⛔ صفر شبكة.

    import co_fixtures as cof
    cof.seed_dash(h.app)       # بيانات اللوحة المعتمدة (أرقام لوحة المفاهيم: ٤٠٠٬٠٠٠ متفق عليها · ٣٧٥٬٠٠٠ مدفوعة · شريك باقٍ عليه ٢٥٬٠٠٠ …)
    cof.clear_dash(h.app)      # قاعدة فاضية (أول مرة)
الأسماء والأرقام مخترعة (لا بيانات حقيقية).
"""
import datetime


def _month(d, back):
    y, m = d.year, d.month - back
    while m <= 0:
        y, m = y - 1, m + 12
    return y, m


def clear_dash(appmod):
    import v2_company_routes as co
    m = appmod
    with m.app.app_context():
        m.db.session.remove()
        for model in list(co.M.values()):
            m.db.session.query(model).delete()
        for model in (m.Partner, m.Asset, m.CashTransaction, m.Revenue, m.Expense, m.ForecastMonth, m.AuditLog, m.Course):
            m.db.session.query(model).delete()
        m.db.session.query(m.Setting).delete()
        m.db.session.commit()


def seed_dash(appmod, today=None):
    """يمسح ثم يزرع. يعيد dict بالمعرّفات المفيدة للّقطات."""
    clear_dash(appmod)
    import v2_company_routes as co
    m = appmod
    today = today or datetime.date.today()
    d = lambda n: today + datetime.timedelta(days=n)       # noqa: E731
    ids = {}
    with m.app.app_context():
        db = m.db
        # —— الشركاء: المؤسس ٥٥٪ (٢٢٠ ألف) · شريك مؤسس ٢٥٪ (١٠٠ ألف) · مستثمر ١٢٪ (٨٠ ألف، دفع ٥٥ ألف) · احتياطي ٨٪
        founder = m.Partner(name='عبدالرحمن عطية', role='founder', equity_percent=55, profit_share_percent=55, capital_egp=220000, capital_usd=0, notes='')
        cof = m.Partner(name='منى الشريف', role='cofounder', equity_percent=25, profit_share_percent=25, capital_egp=100000, capital_usd=0, notes='')
        inv = m.Partner(name='سامي حسين', role='investor', equity_percent=12, profit_share_percent=12, capital_egp=80000, capital_usd=0, notes='')
        pool = m.Partner(name='غير موزّع', role='pool', equity_percent=8, profit_share_percent=8, capital_egp=0, capital_usd=0, notes='محجوز للخبراء المؤسسين')
        db.session.add_all([founder, cof, inv, pool])
        db.session.commit()
        ids.update(founder=founder.id, cofounder=cof.id, investor=inv.id, pool=pool.id)
        # —— دفعات الشركاء (نقدًا ومعدات)
        cash_in = m.CashTransaction(date=d(-15), kind='capital_in', source='شريك: سامي حسين', description='دفعة من المستثمر', amount_egp=20000, amount_usd=0, notes='co:contribution:seed')
        cash_out = m.CashTransaction(date=d(-27), kind='cash_out', source='الشركة', description='شراء معدات التصوير', amount_egp=38000, amount_usd=0, notes='')
        db.session.add_all([cash_in, cash_out])
        db.session.commit()
        C = co.M['Contribution']
        db.session.add_all([
            C(partner_id=founder.id, kind='cash', date=d(-90), amount=220000, currency='EGP', note='تأسيس', created_by='seed', op_id='seed-0001-c1'),
            C(partner_id=cof.id, kind='cash', date=d(-80), amount=100000, currency='EGP', note='', created_by='seed', op_id='seed-0001-c2'),
            C(partner_id=inv.id, kind='cash', date=d(-40), amount=35000, currency='EGP', note='', created_by='seed', op_id='seed-0001-c3'),
            C(partner_id=inv.id, kind='cash', date=d(-15), amount=20000, currency='EGP', note='دفعة ثانية', cash_tx_id=cash_in.id, created_by='seed', op_id='seed-0001-c4'),
        ])
        # —— المعدات: ستة بنود + اشتراك قديم بين المعدات
        db.session.add_all([
            m.Asset(name='كاميرا وعدستان', category='camera', owner='الشركة', value_egp=26000, monthly_rent_egp=0, status='in_studio', notes=''),
            m.Asset(name='ميكروفونان وإضاءة', category='microphone', owner='الشركة', value_egp=12000, monthly_rent_egp=0, status='in_studio', notes=''),
            m.Asset(name='لابتوب المونتاج', category='computers', owner='عبدالرحمن عطية', value_egp=34000, monthly_rent_egp=1500, status='leased_to_company', notes=''),
            m.Asset(name='جهاز قراءة النص', category='teleprompter', owner='الشركة', value_egp=6500, monthly_rent_egp=0, status='owned_by_company', notes=''),
            m.Asset(name='حوامل وملحقات', category='tripod', owner='الشركة', value_egp=4800, monthly_rent_egp=0, status='with_person', notes=''),
            m.Asset(name='هاتف التصوير', category='phones', owner='منى الشريف', value_egp=15000, monthly_rent_egp=0, status='out_of_service', notes=''),
            m.Asset(name='اجتماعات الفيديو وبرامج التصميم', category='software', owner='الشركة', value_egp=0, monthly_rent_egp=1800, status='leased_to_company', notes='اشتراك قديم'),
        ])
        S = co.M['Subscription']
        subs = [
            S(name='الخوادم والخدمات السحابية', amount=3400, currency='EGP', cycle='monthly', renews_on=d(5), status='active', paid_by='المؤسس', note='', created_by='seed'),
            S(name='النطاق والاستضافة', amount=120, currency='USD', cycle='yearly', renews_on=d(64), status='active', paid_by='الشركة', note='', created_by='seed'),
            S(name='البريد المؤسسي', amount=25, currency='USD', cycle='monthly', renews_on=d(21), status='active', paid_by='الشركة', note='', created_by='seed'),
            S(name='أداة جدولة قديمة', amount=600, currency='EGP', cycle='monthly', renews_on=None, status='stopped', paid_by=None, note='', created_by='seed'),
        ]
        db.session.add_all(subs)
        # —— الاتفاقات
        A = co.M['Agreement']
        smart = A(kind='sponsor', party='المكتب الذكي', summary='شعار في الدورات · ٣ أشهر', terms='', amount=30000, currency='EGP', starts_on=d(-78), ends_on=d(12), status='active',
                  ref_code='smart-office', note='', created_by='seed')
        syn = A(kind='content', party='نقابة فرعية', summary='٤ ندوات مسجّلة', terms='نصف الدخل لكل طرف', starts_on=d(-40), status='active', note='', created_by='seed')
        pub = A(kind='book', party='دار نشر', summary='', terms='١٥٪ من كل نسخة مطبوعة', starts_on=d(-120), ends_on=d(240), status='active', note='', created_by='seed')
        old = A(kind='sponsor', party='راعٍ سابق', summary='إعلان في النشرة', terms='', amount=12000, currency='EGP', starts_on=d(-300), ends_on=d(-30), status='ended', note='', created_by='seed')
        draft = A(kind='company_paper', party='السجل التجاري', summary='تجديد الترخيص', terms='', status='draft', ends_on=d(80), note='', created_by='seed')
        db.session.add_all([smart, syn, pub, old, draft])
        db.session.commit()
        ids.update(smart=smart.id, old_deal=old.id)
        db.session.add(m.Revenue(date=d(-60), source='sponsor', description='راعٍ: راعٍ سابق', client_name='راعٍ سابق', payment_method='bank_transfer', amount_egp=12000, amount_usd=0,
                                 payment_id='co:agreement:%d:seed-0001' % old.id, notes='company'))
        # —— عملاء الإعلانات: نتائج ثلاثة أشهر (الأحدث لم يُرسل كشفه)
        CL, R = co.M['AdClient'], co.M['AdResult']
        c1 = CL(name='مكتب الأمل للمحاماة', email='amal@example.test', offer='حملة على صفحاتنا', deal='percent', percent=10, currency='EGP', count_label='عملاء جاؤوا من الحملة',
                ref_code='amal-law', status='active', note='', created_by='seed')
        c2 = CL(name='مركز تدريب قانوني', email='', offer='إعلان دوراتهم في نشرتنا', deal='fixed_plus_percent', percent=5, fixed_amount=6000, currency='EGP', count_label='تسجيلات من عندنا',
                status='active', note='', ledger_kind='book', ledger_owner_id='bk-tenant-guide', created_by='seed')
        db.session.add_all([c1, c2])
        db.session.commit()
        y1, m1 = _month(today, 1)
        y2, m2 = _month(today, 2)
        y3, m3 = _month(today, 3)
        p1, p2, p3 = '%04d-%02d' % (y1, m1), '%04d-%02d' % (y2, m2), '%04d-%02d' % (y3, m3)
        now = datetime.datetime.utcnow()
        rows = [R(client_id=c1.id, period=p3, count=9, income=30000, source='manual', note='', sent_at=now - datetime.timedelta(days=60), sent_by='seed', created_by='seed'),
                R(client_id=c1.id, period=p2, count=11, income=36000, source='manual', note='', sent_at=now - datetime.timedelta(days=30), sent_by='seed', created_by='seed'),
                R(client_id=c1.id, period=p1, count=14, income=48000, source='manual', note='', created_by='seed'),
                R(client_id=c2.id, period=p3, count=20, income=22000, source='manual', note='', sent_at=now - datetime.timedelta(days=60), sent_by='seed', created_by='seed'),
                R(client_id=c2.id, period=p2, count=25, income=28000, source='manual', note='', sent_at=now - datetime.timedelta(days=30), sent_by='seed', created_by='seed'),
                R(client_id=c2.id, period=p1, count=31, income=31000, source='manual', note='', created_by='seed')]
        db.session.add_all(rows)
        db.session.commit()
        # الأقدم محصَّل
        rev = m.Revenue(date=d(-55), source='ad_client', description='عميل إعلانات: مكتب الأمل للمحاماة · %s' % p3, client_name='مكتب الأمل للمحاماة', payment_method='bank_transfer',
                        amount_egp=3000, amount_usd=0, payment_id='co:adresult:%d' % rows[0].id, notes='company')
        db.session.add(rev)
        db.session.commit()
        rows[0].revenue_id = rev.id
        db.session.commit()
        ids.update(client1=c1.id, client2=c2.id, result_open=rows[2].id, result_collected=rows[0].id)
        # —— الأهداف الشهرية: ستة شهور حول الشهر الحالي
        for k in range(-2, 4):
            y, mo = today.year, today.month + k
            while mo <= 0:
                y, mo = y - 1, mo + 12
            while mo > 12:
                y, mo = y + 1, mo - 12
            db.session.add(m.ForecastMonth(month='%04d-%02d' % (y, mo), revenue_egp=40000 + 5000 * (k + 2), cogs_egp=8000, marketing_egp=6000, payroll_egp=12000, rent_egp=3000, other_sga_egp=2000,
                                           target_courses=3 + max(k, 0), target_students=90 + 30 * (k + 2), notes=''))
        # —— الدخل والمصروف: يغطي الدخلُ المصروفَ منذ شهرين
        def rv(year_month, egp, label):
            y, mo = year_month
            db.session.add(m.Revenue(date=datetime.date(y, mo, 12), source='course', description=label, amount_egp=egp, amount_usd=0, client_name='طلاب'))

        def ex(year_month, egp, label):
            y, mo = year_month
            db.session.add(m.Expense(date=datetime.date(y, mo, 18), category='tools', description=label, amount_egp=egp, amount_usd=0, is_business=True, paid_by='الشركة'))
        rv((y3, m3), 30000, 'مبيعات دورات'); ex((y3, m3), 40000, 'مصروف تشغيل')
        rv((y2, m2), 44000, 'مبيعات دورات'); ex((y2, m2), 41000, 'مصروف تشغيل')
        rv((y1, m1), 46000, 'مبيعات دورات'); ex((y1, m1), 42000, 'مصروف تشغيل')
        db.session.add(m.Revenue(date=today, source='course', description='مبيعات هذا الشهر', amount_egp=31000, amount_usd=0, client_name='طلاب'))
        # —— الدورات (للسطر «الآن»)
        for i, (t, n) in enumerate((('أساسيات التسويق القانوني', 120), ('صياغة العقود', 90), ('الملكية الفكرية', 60), ('التحكيم', 40), ('قانون العمل', 70), ('الشركات الناشئة', 30))):
            db.session.add(m.Course(title=t, status='active', students_count=n))
        # —— الإعدادات
        for k, v in (('company_name', 'البروفيسور — ElProfessor'), ('fiscal_year_start', 'تبدأ ١ يناير'), ('monthly_report_day', '١'), ('exchange_rate', '51.5'),
                     ('company_domain', '')):
            db.session.add(m.Setting(key=k, value=v))
        # —— فريق الإدارة (الحسابان الموجودان من الأداة + ثالث)
        from werkzeug.security import generate_password_hash
        if not m.User.query.filter_by(email='nour@local.test').first():
            db.session.add(m.User(email='nour@local.test', password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name='نور المتابعة', role='employee', dashboard_role='employee',
                                  linked_to_name='', preferred_currency='AUTO', is_active=True))
        # —— سجل العمليات: ٣٠ صفًا
        actions = ['company.contribution.add', 'company.subscription.paid', 'company.agreement.add', 'company.adresult.add', 'company.income.add', 'settings.update', 'admin.update_user',
                   'company.forecast.add', 'company.subscription.add', 'company.agreement.renew']
        for i in range(30):
            db.session.add(m.AuditLog(actor_email='admin@local.test', action=actions[i % len(actions)], target=str(100 + i), meta_json='{}',
                                      created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=i * 7)))
        db.session.commit()
    return ids
