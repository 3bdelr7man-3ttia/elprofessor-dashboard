# -*- coding: utf-8 -*-
"""الجولة الأخيرة · قسم «الشركة ورأس المال» (SPEC-company.md §8).

جداول محلية جديدة (SQLite الداشبورد فقط): دفعات الشركاء · الاشتراكات · الاتفاقات والرعاة · عملاء الإعلانات ونتائجهم.
المعدات تعيد استعمال جدول `assets` الموجود، والشركاء جدول `partners` الموجود.

⛔ كل مسار: أدمن بس (`token_required` + `roles_required('admin')`) ثم `_v2_closed()` (المفتاح مقفول ⇒ ٤٠٤)،
   و`Cache-Control: no-store` على كل رد (النجاح والخطأ والرفض)، وأخطاء JSON بعربي بسيط، وسقف ٥٠٠ صف للقوائم.
⛔ كل حركة فلوس تطلب `confirmed: true` (القيمة المنطقية بالظبط)، وتتسجّل مرة واحدة في الدفتر الموجود:
   دفعة نقدية ⇒ `CashTransaction(capital_in)` · مبلغ مستلم ⇒ `Revenue` · دفع اشتراك ⇒ `Expense`.
⛔ منع التكرار من العمود المخزَّن (`op_id` · `payment_id` · مفتاح `notes`) مش من ذاكرة العملية، فيصمد لإعادة التشغيل وتعدد العمّال.
⛔ لا بيحوّل عملات ولا بيجمع عملتين: لكل عملة سطرها. و«المستحق» بيتحسب هنا (الخادم) في مكان واحد.
⛔ لا شبكة إلا بروكسي الزيارات إلى جسر المنصة (قراءة فقط) عبر `_v2_get`.
"""
import calendar
import datetime
import functools
import re
from decimal import Decimal, ROUND_HALF_UP

from flask import g, jsonify, request
from sqlalchemy.exc import IntegrityError

M = {}                                    # الموديلات تتبني مرة واحدة (الجداول بتتعمل من `db.create_all()` في آخر app.py)
_DONE = set()                             # التطبيقات اللي اتسجّلت عليها المسارات (لا تسجيل مرتين)

MAX_AMOUNT = 100000000
MAX_ROWS = 500
OP_RE = re.compile(r'^[A-Za-z0-9_-]{8,64}$')
REF_RE = re.compile(r'^[a-z0-9-]{3,40}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
MONTH_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')
CUR_PARTNER = ('EGP', 'USD')
CUR_ALL = ('EGP', 'USD', 'SAR', 'AED', 'KWD', 'QAR', 'EUR', 'GBP')
RESERVE_NAMES = ('غير موزّع', 'Unallocated / Option Pool')
LEGACY_SUB_CATS = ('subscription', 'software', 'tool')
AGREEMENT_KINDS = ('sponsor', 'content', 'book', 'company_paper', 'other')
DEALS = ('percent', 'fixed_plus_percent', 'fixed', 'other')
DEFAULT_COUNT_LABEL = 'عملاء جاؤوا من الحملة'
UNKNOWN_AR = 'النوع غير معروف'


class Bad(Exception):
    def __init__(self, msg, status=422):
        Exception.__init__(self, msg)
        self.msg = msg
        self.status = status


def bad(msg, status=422):
    raise Bad(msg, status)


# ---------------------------------------------------------------- أدوات التحقق
def _num(v, label, lo_excl=True, hi=MAX_AMOUNT, optional=False):
    """رقم من الجسم (عدد أو نص رقمي، لا منطقي). `lo_excl`: أكبر من صفر (وإلا ≥ صفر)."""
    if v is None or v == '':
        if optional:
            return None
        bad('%s مطلوب' % label)
    if isinstance(v, bool):
        bad('%s غير صالح' % label)
    try:
        x = float(v)
    except (TypeError, ValueError):
        bad('%s غير صالح' % label)
    if x != x or x in (float('inf'), float('-inf')):
        bad('%s غير صالح' % label)
    if (lo_excl and x <= 0) or (not lo_excl and x < 0) or x > hi:
        bad('%s خارج الحدود' % label)
    return x


def _text(v, label, maxlen, required=False, default=''):
    if v is None:
        v = ''
    if not isinstance(v, str):
        bad('%s غير صالح' % label)
    v = v.strip()
    if required and not v:
        bad('%s مطلوب' % label)
    if len(v) > maxlen:
        bad('%s أطول من المسموح (%d حرفًا)' % (label, maxlen))
    return v if v else default


def _date(v, label, optional=False):
    if v is None or v == '':
        if optional:
            return None
        bad('%s مطلوب' % label)
    if not isinstance(v, str) or not DATE_RE.match(v):
        bad('%s غير صالح' % label)
    try:
        return datetime.date.fromisoformat(v)
    except ValueError:
        bad('%s غير صالح' % label)


def _enum(v, allowed, label='النوع'):
    if v not in allowed:
        bad(UNKNOWN_AR if label == 'النوع' else '%s غير معروف' % label)
    return v


def _cur(v, allowed=CUR_ALL, partner=False):
    v = (v or '').strip().upper() if isinstance(v, str) else v
    if v not in allowed:
        bad('العملة لازم جنيه أو دولار' if partner else 'العملة غير مدعومة')
    return v


def _ref(v):
    if v is None or v == '':
        return None
    if not isinstance(v, str) or not REF_RE.match(v.strip()):
        bad('كود التتبّع: حروف إنجليزية صغيرة وأرقام وشرطة فقط (٣ إلى ٤٠)')
    return v.strip()


def _iso(d):
    return d.isoformat() if d else None


def _dt(d):
    return d.isoformat() if d else None


def _round2(x):
    return float(Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _add_months(d, n):
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return datetime.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _sum_by_cur(pairs):
    """[(currency, amount)] ⇒ [{currency, amount}] (الجنيه أولًا ثم الباقي أبجديًا). بالسنت لتفادي أخطاء الكسور."""
    acc = {}
    for c, a in pairs:
        if not a:
            continue
        acc[c] = acc.get(c, 0) + int(round(float(a) * 100))
    keys = sorted(acc.keys(), key=lambda k: (k != 'EGP', k))
    return [{'currency': k, 'amount': acc[k] / 100.0} for k in keys if acc[k]]


def _month_key(d):
    return d.strftime('%Y-%m')


def register(app, ns):
    if id(app) in _DONE:
        return
    _DONE.add(id(app))

    db = ns['db']
    token_required = ns['token_required']
    roles_required = ns['roles_required']
    _audit = ns['_audit']
    _v2_closed = ns['_v2_closed']
    _v2_ns = ns['_v2_ns']
    _v2_body = ns['_v2_body']
    _v2_confirmed = ns['_v2_confirmed']
    _v2_get = ns['_v2_get']
    Partner = ns['Partner']
    CashTransaction = ns['CashTransaction']
    Revenue = ns['Revenue']
    Expense = ns['Expense']
    Asset = ns['Asset']
    ForecastMonth = ns['ForecastMonth']
    Payout = ns['Payout']
    monthly_financial_rows = ns['monthly_financial_rows']
    get_rate = ns['get_rate']

    # ------------------------------------------------------------ الموديلات (مرة واحدة)
    if not M:
        class CoContribution(db.Model):
            __tablename__ = 'co_contributions'
            id = db.Column(db.Integer, primary_key=True)
            partner_id = db.Column(db.Integer, nullable=False, index=True)
            kind = db.Column(db.String(20), nullable=False)
            kind_other = db.Column(db.String(60), nullable=True)
            date = db.Column(db.Date, nullable=False)
            amount = db.Column(db.Float, nullable=False)
            currency = db.Column(db.String(3), nullable=False)
            note = db.Column(db.String(300), default='')
            cash_tx_id = db.Column(db.Integer, nullable=True)
            asset_id = db.Column(db.Integer, nullable=True)
            asset_name = db.Column(db.String(255), nullable=True)
            op_id = db.Column(db.String(64), unique=True, nullable=True)
            created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
            created_by = db.Column(db.String(255))

        class CoSubscription(db.Model):
            __tablename__ = 'co_subscriptions'
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(120), nullable=False)
            amount = db.Column(db.Float, nullable=False)
            currency = db.Column(db.String(3), nullable=False)
            cycle = db.Column(db.String(10), nullable=False)
            cycle_other = db.Column(db.String(60), nullable=True)
            renews_on = db.Column(db.Date, nullable=True)
            status = db.Column(db.String(10), default='active')
            paid_by = db.Column(db.String(120), nullable=True)
            note = db.Column(db.String(300), default='')
            created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
            updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
            created_by = db.Column(db.String(255))

        class CoAgreement(db.Model):
            __tablename__ = 'co_agreements'
            id = db.Column(db.Integer, primary_key=True)
            kind = db.Column(db.String(20), nullable=False)
            kind_other = db.Column(db.String(60), nullable=True)
            party = db.Column(db.String(160), nullable=False)
            summary = db.Column(db.String(300), default='')
            terms = db.Column(db.String(300), default='')
            amount = db.Column(db.Float, nullable=True)
            currency = db.Column(db.String(3), nullable=True)
            starts_on = db.Column(db.Date, nullable=True)
            ends_on = db.Column(db.Date, nullable=True)
            status = db.Column(db.String(10), default='active')
            ref_code = db.Column(db.String(40), nullable=True)
            renewed_from = db.Column(db.Integer, nullable=True)
            op_id = db.Column(db.String(64), unique=True, nullable=True)
            note = db.Column(db.String(500), default='')
            created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
            updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
            created_by = db.Column(db.String(255))

        class CoAdClient(db.Model):
            __tablename__ = 'co_ad_clients'
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(160), nullable=False)
            email = db.Column(db.String(200), nullable=True)
            offer = db.Column(db.String(300), default='')
            deal = db.Column(db.String(20), nullable=False)
            deal_other = db.Column(db.String(120), nullable=True)
            percent = db.Column(db.Float, nullable=True)
            fixed_amount = db.Column(db.Float, nullable=True)
            currency = db.Column(db.String(3), nullable=False)
            count_label = db.Column(db.String(60), default=DEFAULT_COUNT_LABEL)
            ref_code = db.Column(db.String(40), nullable=True)
            ledger_kind = db.Column(db.String(10), nullable=True)
            ledger_owner_id = db.Column(db.String(200), nullable=True)
            status = db.Column(db.String(10), default='active')
            note = db.Column(db.String(500), default='')
            created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
            updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
            created_by = db.Column(db.String(255))

        class CoAdResult(db.Model):
            __tablename__ = 'co_ad_results'
            __table_args__ = (db.UniqueConstraint('client_id', 'period', name='uq_co_ad_result_period'),)
            id = db.Column(db.Integer, primary_key=True)
            client_id = db.Column(db.Integer, nullable=False, index=True)
            period = db.Column(db.String(7), nullable=False)
            count = db.Column(db.Integer, nullable=True)
            income = db.Column(db.Float, nullable=True)
            due_manual = db.Column(db.Float, nullable=True)
            source = db.Column(db.String(10), default='manual')
            note = db.Column(db.String(300), default='')
            sent_at = db.Column(db.DateTime, nullable=True)
            sent_by = db.Column(db.String(255), nullable=True)
            revenue_id = db.Column(db.Integer, nullable=True)
            created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
            updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
            created_by = db.Column(db.String(255))

        M.update(Contribution=CoContribution, Subscription=CoSubscription, Agreement=CoAgreement, AdClient=CoAdClient, AdResult=CoAdResult)

    Contribution, Subscription, Agreement = M['Contribution'], M['Subscription'], M['Agreement']
    AdClient, AdResult = M['AdClient'], M['AdResult']

    # ------------------------------------------------------------ مساعدات المسارات
    @app.after_request
    def _co_no_store(resp):                                    # no-store على كل رد تحت /api/v2/company (حتى ٤٠١ و٤٠٣)
        try:
            if request.path.startswith('/api/v2/company/'):
                resp.headers['Cache-Control'] = 'no-store'
        except Exception:
            pass
        return resp

    def actor():
        try:
            return str(getattr(g.user, 'email', '') or 'dashboard')[:255]
        except Exception:
            return 'dashboard'

    def route(rule, methods):
        def deco(fn):
            name = 'v2c_' + fn.__name__

            @functools.wraps(fn)
            def inner(*a, **k):
                closed = _v2_closed()
                if closed:
                    return closed
                try:
                    return _v2_ns(fn(*a, **k))
                except Bad as e:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    return _v2_ns((jsonify({'error': e.msg}), e.status))
            inner.__name__ = name
            return app.route(rule, methods=methods, endpoint=name)(token_required(roles_required('admin')(inner)))
        return deco

    def need_confirm(body):
        r = _v2_confirmed(body)
        if r is not None:
            raise Bad('لازم تأكيد صريح قبل التنفيذ', 400)

    def need_op(body):
        op = body.get('op_id')
        if not isinstance(op, str) or not OP_RE.match(op):
            bad('رمز العملية ناقص — أعد فتح الورقة', 400)
        return op

    def jbody():
        b = _v2_body()
        return b if isinstance(b, dict) else {}

    def not_found(msg='غير موجود'):
        bad(msg, 404)

    def get_or_404(model, rid, msg='غير موجود'):
        row = db.session.get(model, rid) if hasattr(db.session, 'get') else model.query.get(rid)
        if row is None:
            not_found(msg)
        return row

    # ------------------------------------------------------------ تسلسل
    def s_contribution(c, partner_names=None):
        pn = ''
        if partner_names is not None:
            pn = partner_names.get(c.partner_id, '')
        return {'id': c.id, 'partner_id': c.partner_id, 'partner_name': pn, 'kind': c.kind, 'kind_other': c.kind_other,
                'date': _iso(c.date), 'amount': c.amount, 'currency': c.currency, 'note': c.note or '',
                'cash_tx_id': c.cash_tx_id, 'asset_id': c.asset_id, 'asset_name': c.asset_name}

    def s_sub(s):
        return {'id': s.id, 'name': s.name, 'amount': s.amount, 'currency': s.currency, 'cycle': s.cycle, 'cycle_other': s.cycle_other,
                'renews_on': _iso(s.renews_on), 'status': s.status, 'paid_by': s.paid_by, 'note': s.note or '',
                'created_at': _dt(s.created_at), 'updated_at': _dt(s.updated_at), 'created_by': s.created_by}

    def received_for(agr_id):
        pairs = []
        like = 'co:agreement:%d:%%' % agr_id
        for r in Revenue.query.filter(Revenue.payment_id.like(like)).all():
            if r.currency and r.amount_original:
                pairs.append((r.currency, r.amount_original))
            else:
                pairs.append(('EGP', r.amount_egp or 0))
                pairs.append(('USD', r.amount_usd or 0))
        return _sum_by_cur(pairs)

    def s_agreement(a, with_received=True):
        d = {'id': a.id, 'kind': a.kind, 'kind_other': a.kind_other, 'party': a.party, 'summary': a.summary or '', 'terms': a.terms or '',
             'amount': a.amount, 'currency': a.currency, 'starts_on': _iso(a.starts_on), 'ends_on': _iso(a.ends_on), 'status': a.status,
             'ref_code': a.ref_code, 'renewed_from': a.renewed_from, 'note': a.note or '',
             'created_at': _dt(a.created_at), 'updated_at': _dt(a.updated_at), 'created_by': a.created_by}
        if with_received:
            d['received'] = received_for(a.id)
        return d

    def due_of(client, res):
        """المستحق للبروفيسور: رقم أو None (لا صفر مختلق). النصف يُقرَّب لأعلى لأقرب سنت."""
        pct = client.percent
        if client.deal == 'fixed':
            return _round2(client.fixed_amount) if client.fixed_amount is not None else None
        if client.deal == 'other':
            return res.due_manual if res.due_manual is not None else None
        if res.income is None or pct is None:
            return None
        part = _round2(Decimal(str(res.income)) * Decimal(str(pct)) / Decimal(100))
        if client.deal == 'percent':
            return part
        if client.fixed_amount is None:
            return None
        return _round2(Decimal(str(client.fixed_amount)) + Decimal(str(part)))

    def due_list(client, res):
        d = due_of(client, res)
        return None if d is None else [{'currency': client.currency, 'amount': d}]

    def collected_on(r):
        if r.revenue_id is None:
            return None
        rev = db.session.get(Revenue, r.revenue_id) if hasattr(db.session, 'get') else Revenue.query.get(r.revenue_id)
        return _iso(rev.date) if rev is not None else None

    def s_result(client, r):
        return {'id': r.id, 'client_id': r.client_id, 'period': r.period, 'count': r.count, 'income': r.income, 'due_manual': r.due_manual,
                'due': due_list(client, r), 'source': r.source, 'note': r.note or '', 'sent_at': _dt(r.sent_at), 'sent_by': r.sent_by,
                'revenue_id': r.revenue_id, 'collected': r.revenue_id is not None, 'collected_on': collected_on(r), 'created_at': _dt(r.created_at)}

    def s_client(c, results=None):
        d = {'id': c.id, 'name': c.name, 'email': c.email, 'offer': c.offer or '', 'deal': c.deal, 'deal_other': c.deal_other,
             'percent': c.percent, 'fixed_amount': c.fixed_amount, 'currency': c.currency, 'count_label': c.count_label or DEFAULT_COUNT_LABEL,
             'ref_code': c.ref_code, 'ledger_kind': c.ledger_kind, 'ledger_owner_id': c.ledger_owner_id, 'status': c.status, 'note': c.note or '',
             'created_at': _dt(c.created_at), 'updated_at': _dt(c.updated_at), 'created_by': c.created_by}
        if results is not None:
            d['results'] = [s_result(c, r) for r in results]
        return d

    def client_results(cid):
        return AdResult.query.filter_by(client_id=cid).order_by(AdResult.period.desc(), AdResult.id.desc()).all()

    def ref_taken(code, exclude_agr=None, exclude_client=None):
        if not code:
            return False
        for a in Agreement.query.filter_by(ref_code=code).all():
            if a.status == 'active' and a.id != exclude_agr:
                return True
        for c in AdClient.query.filter_by(ref_code=code).all():
            if c.status == 'active' and c.id != exclude_client:
                return True
        return False

    def aud(action, target, meta=None):
        _audit(action, target=str(target), meta=meta)

    # ============================================================ الملخّص
    def block_partners():
        rows, agreed_all, paid_all = [], [], []
        eq_total = 0.0
        contribs = Contribution.query.all()
        by_p = {}
        for c in contribs:
            by_p.setdefault(c.partner_id, []).append(c)
        for p in Partner.query.order_by(Partner.equity_percent.desc(), Partner.id.asc()).all():
            reserve = (p.role == 'pool') or (p.name in RESERVE_NAMES)
            agreed = []
            if (p.capital_egp or 0) > 0:
                agreed.append({'currency': 'EGP', 'amount': p.capital_egp})
            if (p.capital_usd or 0) > 0:
                agreed.append({'currency': 'USD', 'amount': p.capital_usd})
            mine = by_p.get(p.id, [])
            paid = _sum_by_cur([(c.currency, c.amount) for c in mine])
            last = max([c.date for c in mine if c.date], default=None)
            eq_total += p.equity_percent or 0
            rows.append({'id': p.id, 'name': p.name, 'role': p.role, 'equity': p.equity_percent or 0, 'reserve': reserve, 'agreed': agreed,
                         'paid': paid, 'contributions': len(mine), 'last_paid_at': _iso(last), 'notes': p.notes or ''})
            agreed_all += [(a['currency'], a['amount']) for a in agreed]
        paid_all = [(c.currency, c.amount) for c in contribs]
        return {'rows': rows, 'equity_total': round(eq_total, 2), 'agreed_total': _sum_by_cur(agreed_all),
                'paid_total': _sum_by_cur(paid_all), 'any_contribution': len(contribs) > 0}

    def block_moves():
        out = []
        for t in CashTransaction.query.order_by(CashTransaction.date.desc(), CashTransaction.id.desc()).limit(5).all():
            eg = t.amount_egp or 0
            out.append({'date': _iso(t.date), 'kind': t.kind, 'description': t.description or t.source or '',
                        'amount': abs(eg) if eg else abs(t.amount_usd or 0), 'currency': 'EGP' if eg else 'USD'})
        return out

    def block_assets():
        items = Asset.query.all()
        return {'count': len(items), 'value_egp': sum(a.value_egp or 0 for a in items), 'rent_egp_monthly': sum(a.monthly_rent_egp or 0 for a in items)}

    def block_subs():
        act = Subscription.query.filter_by(status='active').all()
        nxt = sorted([s for s in act if s.renews_on], key=lambda s: (s.renews_on, s.id))[:3]
        return {'active': len(act),
                'monthly': _sum_by_cur([(s.currency, s.amount) for s in act if s.cycle == 'monthly']),
                'yearly': _sum_by_cur([(s.currency, s.amount) for s in act if s.cycle == 'yearly']),
                'next': [{'id': s.id, 'name': s.name, 'renews_on': _iso(s.renews_on), 'amount': s.amount, 'currency': s.currency, 'cycle': s.cycle} for s in nxt]}

    def block_agreements():
        today = datetime.date.today()
        act = Agreement.query.filter_by(status='active').all()
        lim = today + datetime.timedelta(days=45)
        end = sorted([a for a in act if a.ends_on and today <= a.ends_on <= lim], key=lambda a: (a.ends_on, a.id))
        return {'active': len(act),
                'ending': [{'id': a.id, 'kind': a.kind, 'party': a.party, 'ends_on': _iso(a.ends_on), 'amount': a.amount, 'currency': a.currency,
                            'ref_code': a.ref_code} for a in end]}

    def block_ads():
        clients = AdClient.query.order_by(AdClient.id.asc()).all()
        unsent, open_pairs, unsent_pairs, latest = 0, [], [], []
        for c in clients:
            res = client_results(c.id)
            for r in res:
                d = due_of(c, r)
                if r.revenue_id is None and d is not None:
                    open_pairs.append((c.currency, d))
                    if r.sent_at is None and c.status == 'active':
                        unsent += 1
                        unsent_pairs.append((c.currency, d))
            if c.status == 'active' and res:
                r = res[0]
                latest.append({'client_id': c.id, 'name': c.name, 'period': r.period, 'count': r.count, 'income': r.income, 'due': due_list(c, r)})
        return {'active': len([c for c in clients if c.status == 'active']), 'unsent': unsent, 'due_open': _sum_by_cur(open_pairs), 'due_unsent': _sum_by_cur(unsent_pairs), 'latest': latest}

    def block_money():
        rate = get_rate()
        revenues = Revenue.query.all()
        expenses = Expense.query.filter_by(is_business=True).all()
        payouts = Payout.query.filter(Payout.status != 'waived').all()
        rows = monthly_financial_rows(revenues, expenses, payouts, rate)
        cur = _month_key(datetime.date.today())
        done = [r for r in rows if r['month'] < cur]
        if not done:
            return None
        last = done[-1]
        covered_since = None
        if last['revenue'] >= last['expenses']:
            covered_since = last['month']
            by = {r['month']: r for r in done}
            y, m = int(last['month'][:4]), int(last['month'][5:])
            while True:
                m -= 1
                if m == 0:
                    y, m = y - 1, 12
                k = '%04d-%02d' % (y, m)
                r = by.get(k)
                if not r or r['revenue'] < r['expenses']:
                    break
                covered_since = k
        return {'month': last['month'], 'revenue': last['revenue'], 'expenses': last['expenses'], 'covered_since': covered_since}

    @route('/api/v2/company/summary', ['GET'])
    def summary():
        out = {'generated_at': datetime.datetime.utcnow().isoformat()}
        for key, fn in (('partners', block_partners), ('capital_moves', block_moves), ('assets', block_assets), ('subscriptions', block_subs),
                        ('agreements', block_agreements), ('ad_clients', block_ads), ('money', block_money)):
            try:
                out[key] = fn()
            except Exception as e:                                # كتلة واحدة فاشلة ⇒ null والباقي سليم
                try:
                    db.session.rollback()
                except Exception:
                    pass
                try:
                    app.logger.warning('company summary block %s failed: %s', key, e)
                except Exception:
                    pass
                out[key] = None
        return jsonify(out)

    # ============================================================ دفعات الشركاء
    @route('/api/v2/company/contributions', ['GET'])
    def contributions_list():
        q = Contribution.query
        pid = request.args.get('partner_id')
        if pid:
            try:
                q = q.filter_by(partner_id=int(pid))
            except ValueError:
                bad('الشريك غير صالح', 400)
        names = {p.id: p.name for p in Partner.query.all()}
        rows = q.order_by(Contribution.date.desc(), Contribution.id.desc()).limit(MAX_ROWS).all()
        return jsonify({'items': [s_contribution(c, names) for c in rows]})

    @route('/api/v2/company/contributions', ['POST'])
    def contributions_add():
        b = jbody()
        need_confirm(b)
        op = need_op(b)
        dup = Contribution.query.filter_by(op_id=op).first()
        if dup:
            return jsonify({'item': s_contribution(dup, {p.id: p.name for p in Partner.query.all()}), 'duplicate': True}), 200
        pid = b.get('partner_id')
        if isinstance(pid, bool) or not isinstance(pid, int):
            bad('اختر الشريك')
        partner = db.session.get(Partner, pid) if hasattr(db.session, 'get') else Partner.query.get(pid)
        if partner is None:
            not_found('الشريك غير موجود')
        kind = _enum(b.get('kind'), ('cash', 'asset', 'other'))
        kind_other = _text(b.get('kind_other'), 'نوع الدفعة', 60, required=(kind == 'other'), default=None) if kind == 'other' else None
        amount = _num(b.get('amount'), 'المبلغ')
        currency = _cur(b.get('currency'), CUR_PARTNER, partner=True)
        date = _date(b.get('date') or datetime.date.today().isoformat(), 'التاريخ')
        note = _text(b.get('note'), 'الملاحظة', 300)
        record_cash = (b.get('record_cash') is True) and kind == 'cash'
        record_asset = (b.get('record_asset') is True) and kind == 'asset'
        asset_name = None
        if kind == 'asset':
            asset_name = _text(b.get('asset_name'), 'اسم المعدة', 255, required=True)
            if record_asset and currency != 'EGP':
                bad('المعدات تُسجَّل بالجنيه فقط')
        row = Contribution(partner_id=partner.id, kind=kind, kind_other=kind_other, date=date, amount=amount, currency=currency, note=note,
                           asset_name=asset_name if kind == 'asset' else None, op_id=op, created_by=actor())
        try:
            db.session.add(row)
            db.session.flush()
            if record_cash:
                tx = CashTransaction(date=date, kind='capital_in', source='شريك: %s' % partner.name, description='دفعة رأس مال من %s' % partner.name,
                                     amount_egp=amount if currency == 'EGP' else 0, amount_usd=amount if currency == 'USD' else 0,
                                     notes='co:contribution:%d' % row.id)
                db.session.add(tx)
                db.session.flush()
                row.cash_tx_id = tx.id
            if record_asset:
                a = Asset(name=asset_name, category='equipment', owner=partner.name, value_egp=amount, monthly_rent_egp=0,
                          status='owned_by_company', notes='co:contribution:%d' % row.id)
                db.session.add(a)
                db.session.flush()
                row.asset_id = a.id
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            again = Contribution.query.filter_by(op_id=op).first()
            if again is None:
                bad('تعذّر الحفظ — حاول مرة أخرى', 409)
            return jsonify({'item': s_contribution(again, {p.id: p.name for p in Partner.query.all()}), 'duplicate': True}), 200
        aud('company.contribution.add', row.id, {'partner_id': partner.id, 'amount': amount, 'currency': currency, 'kind': kind,
                                                 'cash_tx_id': row.cash_tx_id, 'asset_id': row.asset_id})
        return jsonify({'item': s_contribution(row, {partner.id: partner.name})}), 201

    @route('/api/v2/company/contributions/<int:rid>', ['DELETE'])
    def contributions_delete(rid):
        b = jbody()
        need_confirm(b)
        row = get_or_404(Contribution, rid, 'الدفعة غير موجودة')
        meta = {'partner_id': row.partner_id, 'amount': row.amount, 'currency': row.currency}
        if row.cash_tx_id:
            tx = db.session.get(CashTransaction, row.cash_tx_id) if hasattr(db.session, 'get') else CashTransaction.query.get(row.cash_tx_id)
            if tx is not None:
                db.session.delete(tx)
        if row.asset_id:
            a = db.session.get(Asset, row.asset_id) if hasattr(db.session, 'get') else Asset.query.get(row.asset_id)
            if a is not None:
                db.session.delete(a)
        db.session.delete(row)
        db.session.commit()
        aud('company.contribution.delete', rid, meta)
        return jsonify({'ok': True})

    # ============================================================ الاشتراكات
    def sub_fields(b, partial_from=None):
        name = _text(b.get('name'), 'الاسم', 120, required=True)
        amount = _num(b.get('amount'), 'المبلغ')
        currency = _cur(b.get('currency'), CUR_PARTNER, partner=True)
        cycle = _enum(b.get('cycle'), ('monthly', 'yearly', 'other'))
        cycle_other = _text(b.get('cycle_other'), 'الدورة', 60, required=True) if cycle == 'other' else None
        renews = _date(b.get('renews_on'), 'موعد التجديد', optional=True)
        status = _enum(b.get('status') or 'active', ('active', 'stopped'), 'الحالة')
        paid_by = _text(b.get('paid_by'), 'يدفعه', 120, default=None)
        note = _text(b.get('note'), 'الملاحظة', 300)
        return dict(name=name, amount=amount, currency=currency, cycle=cycle, cycle_other=cycle_other, renews_on=renews, status=status, paid_by=paid_by, note=note)

    @route('/api/v2/company/subscriptions', ['GET'])
    def subs_list():
        rows = Subscription.query.order_by(Subscription.id.asc()).limit(MAX_ROWS).all()
        return jsonify({'items': [s_sub(s) for s in rows]})

    @route('/api/v2/company/subscriptions', ['POST'])
    def subs_add():
        f = sub_fields(jbody())
        row = Subscription(created_by=actor(), **f)
        db.session.add(row)
        db.session.commit()
        aud('company.subscription.add', row.id, {'name': row.name, 'amount': row.amount, 'currency': row.currency})
        return jsonify({'item': s_sub(row)}), 201

    @route('/api/v2/company/subscriptions/import', ['POST'])
    def subs_import():
        b = jbody()
        need_confirm(b)
        ids = b.get('asset_ids')
        if not isinstance(ids, list) or not ids or len(ids) > 100 or any(isinstance(i, bool) or not isinstance(i, int) for i in ids):
            bad('اختر بنودًا من القائمة')
        ids = list(dict.fromkeys(ids))
        assets = []
        for i in ids:
            a = db.session.get(Asset, i) if hasattr(db.session, 'get') else Asset.query.get(i)
            if a is None or a.category not in LEGACY_SUB_CATS or not (a.monthly_rent_egp or 0) > 0:
                bad('بند ليس اشتراكًا قديمًا')
            assets.append(a)
        made = []
        for a in assets:
            s = Subscription(name=(a.name or '')[:120], amount=a.monthly_rent_egp, currency='EGP', cycle='monthly', renews_on=None,
                             status='active', note=(a.notes or '')[:300], created_by=actor())
            db.session.add(s)
            made.append(s)
            db.session.delete(a)
        db.session.commit()
        aud('company.subscription.import', len(made), {'count': len(made), 'asset_ids': ids})
        return jsonify({'items': [s_sub(s) for s in made], 'moved': len(made)})

    @route('/api/v2/company/subscriptions/<int:rid>', ['PUT'])
    def subs_update(rid):
        row = get_or_404(Subscription, rid, 'الاشتراك غير موجود')
        b = jbody()
        merged = s_sub(row)
        merged.update({k: v for k, v in b.items() if k in ('name', 'amount', 'currency', 'cycle', 'cycle_other', 'renews_on', 'status', 'paid_by', 'note')})
        f = sub_fields(merged)
        for k, v in f.items():
            setattr(row, k, v)
        row.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        aud('company.subscription.update', rid, {'status': row.status})
        return jsonify({'item': s_sub(row)})

    @route('/api/v2/company/subscriptions/<int:rid>', ['DELETE'])
    def subs_delete(rid):
        b = jbody()
        need_confirm(b)
        row = get_or_404(Subscription, rid, 'الاشتراك غير موجود')
        name = row.name
        db.session.delete(row)
        db.session.commit()
        aud('company.subscription.delete', rid, {'name': name})
        return jsonify({'ok': True})

    @route('/api/v2/company/subscriptions/<int:rid>/paid', ['POST'])
    def subs_paid(rid):
        b = jbody()
        need_confirm(b)
        if b.get('op_id') is not None and not (isinstance(b.get('op_id'), str) and OP_RE.match(b['op_id'])):
            bad('رمز العملية غير صالح', 400)
        row = get_or_404(Subscription, rid, 'الاشتراك غير موجود')
        if row.status != 'active':
            bad('الاشتراك متوقف', 409)
        date = _date(b.get('date') or datetime.date.today().isoformat(), 'التاريخ')
        base = row.renews_on or date
        key = 'co:subscription:%d:%s' % (rid, base.isoformat())
        if Expense.query.filter_by(notes=key).first():
            bad('سُجّل دفع هذه الفترة من قبل', 409)
        exp = Expense(date=date, category='tools', description='اشتراك: %s' % row.name, amount_egp=row.amount if row.currency == 'EGP' else 0,
                      amount_usd=row.amount if row.currency == 'USD' else 0, is_business=True, paid_by=row.paid_by, notes=key)
        db.session.add(exp)
        if row.cycle == 'monthly':
            row.renews_on = _add_months(base, 1)
        elif row.cycle == 'yearly':
            row.renews_on = _add_months(base, 12)
        row.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        aud('company.subscription.paid', rid, {'amount': row.amount, 'currency': row.currency, 'expense_id': exp.id, 'date': date.isoformat()})
        return jsonify({'item': s_sub(row), 'expense_id': exp.id})

    # ============================================================ الاتفاقات والرعاة
    def agr_fields(b, exclude_id=None):
        kind = _enum(b.get('kind'), AGREEMENT_KINDS)
        kind_other = _text(b.get('kind_other'), 'نوع الاتفاق', 60, required=True) if kind == 'other' else None
        party = _text(b.get('party'), 'الطرف الآخر', 160, required=True)
        summary = _text(b.get('summary'), 'ماذا نقدّم', 300)
        terms = _text(b.get('terms'), 'المقابل', 300)
        amount = _num(b.get('amount'), 'المبلغ', optional=True)
        currency = _cur(b.get('currency') or 'EGP') if amount is not None else (_cur(b.get('currency')) if b.get('currency') else None)
        starts = _date(b.get('starts_on'), 'تاريخ البداية', optional=True)
        ends = _date(b.get('ends_on'), 'تاريخ الانتهاء', optional=True)
        if starts and ends and ends < starts:
            bad('تاريخ الانتهاء قبل البداية')
        status = _enum(b.get('status') or 'active', ('active', 'draft', 'ended'), 'الحالة')
        ref = _ref(b.get('ref_code'))
        if ref and status == 'active' and ref_taken(ref, exclude_agr=exclude_id):
            bad('هذا الكود مستخدم لاتفاق أو عميل آخر', 409)
        note = _text(b.get('note'), 'الملاحظة', 500)
        return dict(kind=kind, kind_other=kind_other, party=party, summary=summary, terms=terms, amount=amount, currency=currency,
                    starts_on=starts, ends_on=ends, status=status, ref_code=ref, note=note)

    @route('/api/v2/company/agreements', ['GET'])
    def agr_list():
        rows = Agreement.query.order_by(Agreement.id.desc()).limit(MAX_ROWS).all()
        return jsonify({'items': [s_agreement(a) for a in rows]})

    @route('/api/v2/company/agreements', ['POST'])
    def agr_add():
        f = agr_fields(jbody())
        row = Agreement(created_by=actor(), **f)
        db.session.add(row)
        db.session.commit()
        aud('company.agreement.add', row.id, {'party': row.party, 'kind': row.kind})
        return jsonify({'item': s_agreement(row)}), 201

    @route('/api/v2/company/agreements/<int:rid>', ['PUT'])
    def agr_update(rid):
        row = get_or_404(Agreement, rid, 'الاتفاق غير موجود')
        b = jbody()
        merged = s_agreement(row, with_received=False)
        merged.update({k: v for k, v in b.items() if k in ('kind', 'kind_other', 'party', 'summary', 'terms', 'amount', 'currency', 'starts_on', 'ends_on', 'status', 'ref_code', 'note')})
        if merged.get('amount') is None:
            merged['currency'] = merged.get('currency')
        f = agr_fields(merged, exclude_id=rid)
        for k, v in f.items():
            setattr(row, k, v)
        row.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        aud('company.agreement.end' if b.get('status') == 'ended' and len(b) <= 2 else 'company.agreement.update', rid, {'status': row.status})
        return jsonify({'item': s_agreement(row)})

    @route('/api/v2/company/agreements/<int:rid>', ['DELETE'])
    def agr_delete(rid):
        b = jbody()
        need_confirm(b)
        row = get_or_404(Agreement, rid, 'الاتفاق غير موجود')
        if received_for(rid):
            bad('للاتفاق مبالغ مستلمة مسجّلة', 409)
        party = row.party
        db.session.delete(row)
        db.session.commit()
        aud('company.agreement.delete', rid, {'party': party})
        return jsonify({'ok': True})

    @route('/api/v2/company/agreements/<int:rid>/renew', ['POST'])
    def agr_renew(rid):
        b = jbody()
        need_confirm(b)
        op = need_op(b)
        dup = Agreement.query.filter_by(op_id=op).first()
        if dup:
            prev = db.session.get(Agreement, dup.renewed_from) if (dup.renewed_from and hasattr(db.session, 'get')) else None
            return jsonify({'item': s_agreement(dup), 'previous': s_agreement(prev) if prev else None, 'duplicate': True}), 200
        old = get_or_404(Agreement, rid, 'الاتفاق غير موجود')
        starts = _date(b.get('starts_on'), 'تاريخ البداية')
        ends = _date(b.get('ends_on'), 'تاريخ الانتهاء', optional=True)
        if ends and ends < starts:
            bad('تاريخ الانتهاء قبل البداية')
        amount = _num(b.get('amount'), 'المبلغ', optional=True) if b.get('amount') not in (None, '') else old.amount
        currency = (_cur(b.get('currency')) if b.get('currency') else old.currency)
        if amount is not None and not currency:
            currency = 'EGP'
        try:
            new = Agreement(kind=old.kind, kind_other=old.kind_other, party=old.party, summary=old.summary, terms=old.terms, amount=amount,
                            currency=currency, starts_on=starts, ends_on=ends, status='active', ref_code=None, renewed_from=old.id, op_id=op,
                            note=old.note, created_by=actor())
            old_ref = old.ref_code
            old.status = 'ended'
            old.updated_at = datetime.datetime.utcnow()
            db.session.add(new)
            db.session.flush()
            if old_ref:
                new.ref_code = old_ref                       # الكود ينتقل للاتفاق الجديد (القديم انتهى، فلا تعارض)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            again = Agreement.query.filter_by(op_id=op).first()
            if again is None:
                bad('تعذّر الحفظ — حاول مرة أخرى', 409)
            return jsonify({'item': s_agreement(again), 'previous': None, 'duplicate': True}), 200
        aud('company.agreement.renew', rid, {'new_id': new.id, 'starts_on': starts.isoformat(), 'ends_on': _iso(ends)})
        return jsonify({'item': s_agreement(new), 'previous': s_agreement(old)})

    # ============================================================ عملاء الإعلانات
    def client_fields(b, exclude_id=None):
        name = _text(b.get('name'), 'الاسم', 160, required=True)
        email = _text(b.get('email'), 'البريد', 200, default=None)
        if email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            bad('البريد غير صالح')
        offer = _text(b.get('offer'), 'ماذا نقدّم لهم', 300)
        deal = _enum(b.get('deal'), DEALS, 'طريقة الحساب')
        deal_other = _text(b.get('deal_other'), 'طريقة الحساب', 120, required=True) if deal == 'other' else None
        percent = fixed = None
        if deal in ('percent', 'fixed_plus_percent'):
            percent = _num(b.get('percent'), 'النسبة', hi=100)
        if deal in ('fixed', 'fixed_plus_percent'):
            fixed = _num(b.get('fixed_amount'), 'المبلغ الثابت')
        currency = _cur(b.get('currency') or 'EGP')
        count_label = _text(b.get('count_label'), 'اسم العدد', 60, default=DEFAULT_COUNT_LABEL)
        ref = _ref(b.get('ref_code'))
        status = _enum(b.get('status') or 'active', ('active', 'ended'), 'الحالة')
        if ref and status == 'active' and ref_taken(ref, exclude_client=exclude_id):
            bad('هذا الكود مستخدم لاتفاق أو عميل آخر', 409)
        lk = b.get('ledger_kind') or None
        lo = b.get('ledger_owner_id') or None
        if lk:
            _enum(lk, ('course', 'book'), 'نوع العمل')
            lo = _text(lo, 'العمل المرتبط', 200, required=True)
        else:
            lk = lo = None
        note = _text(b.get('note'), 'الملاحظة', 500)
        return dict(name=name, email=email, offer=offer, deal=deal, deal_other=deal_other, percent=percent, fixed_amount=fixed, currency=currency,
                    count_label=count_label, ref_code=ref, ledger_kind=lk, ledger_owner_id=lo, status=status, note=note)

    @route('/api/v2/company/ad-clients', ['GET'])
    def clients_list():
        rows = AdClient.query.order_by(AdClient.id.asc()).limit(MAX_ROWS).all()
        return jsonify({'items': [s_client(c, client_results(c.id)) for c in rows]})

    @route('/api/v2/company/ad-clients', ['POST'])
    def clients_add():
        f = client_fields(jbody())
        row = AdClient(created_by=actor(), **f)
        db.session.add(row)
        db.session.commit()
        aud('company.adclient.add', row.id, {'name': row.name, 'deal': row.deal})
        return jsonify({'item': s_client(row, [])}), 201

    @route('/api/v2/company/ad-clients/<int:rid>', ['PUT'])
    def clients_update(rid):
        row = get_or_404(AdClient, rid, 'العميل غير موجود')
        b = jbody()
        merged = s_client(row)
        merged.update({k: v for k, v in b.items() if k in ('name', 'email', 'offer', 'deal', 'deal_other', 'percent', 'fixed_amount', 'currency', 'count_label',
                                                           'ref_code', 'ledger_kind', 'ledger_owner_id', 'status', 'note')})
        f = client_fields(merged, exclude_id=rid)
        # المستحق يُحسب من شروط العميل: لا تتغير الشروط بعد إرسال كشف أو تحصيل مبلغ حتى لا يختلف المعروض عن المحصَّل
        if any(f[k] != getattr(row, k) for k in ('deal', 'percent', 'fixed_amount', 'currency')):
            if any(r.revenue_id is not None or r.sent_at is not None for r in client_results(rid)):
                bad('لهذا العميل كشوف أُرسلت أو مبالغ حُصّلت — أنهِ هذا الاتفاق وأضف اتفاقًا جديدًا بالشروط الجديدة', 409)
        for k, v in f.items():
            setattr(row, k, v)
        row.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        aud('company.adclient.update', rid, {'status': row.status})
        return jsonify({'item': s_client(row, client_results(rid))})

    @route('/api/v2/company/ad-clients/<int:rid>', ['DELETE'])
    def clients_delete(rid):
        b = jbody()
        need_confirm(b)
        row = get_or_404(AdClient, rid, 'العميل غير موجود')
        res = client_results(rid)
        if any(r.revenue_id is not None for r in res):
            bad('حُصّل مبلغ لهذا العميل — لا يُحذف', 409)
        name = row.name
        for r in res:
            db.session.delete(r)
        db.session.delete(row)
        db.session.commit()
        aud('company.adclient.delete', rid, {'name': name})
        return jsonify({'ok': True})

    def result_fields(b):
        count = b.get('count')
        if count in (None, ''):
            count = None
        else:
            if isinstance(count, bool) or not isinstance(count, (int, float, str)):
                bad('العدد غير صالح')
            try:
                fc = float(count)
            except ValueError:
                bad('العدد غير صالح')
            if fc != int(fc) or fc < 0 or fc > 1000000000:
                bad('العدد غير صالح')
            count = int(fc)
        income = _num(b.get('income'), 'دخلهم من الحملة', lo_excl=False, optional=True)
        due_manual = _num(b.get('due_manual'), 'المستحق', lo_excl=False, optional=True)
        note = _text(b.get('note'), 'الملاحظة', 300)
        return count, income, due_manual, note

    @route('/api/v2/company/ad-clients/<int:rid>/results', ['POST'])
    def results_add(rid):
        client = get_or_404(AdClient, rid, 'العميل غير موجود')
        b = jbody()
        period = b.get('period')
        if not isinstance(period, str) or not MONTH_RE.match(period):
            bad('الشهر غير صالح')
        if AdResult.query.filter_by(client_id=rid, period=period).first():
            bad('لهذا الشهر نتيجة مسجّلة — عدّلها', 409)
        count, income, due_manual, note = result_fields(b)
        if client.deal != 'other':
            due_manual = None
        row = AdResult(client_id=rid, period=period, count=count, income=income, due_manual=due_manual, source='manual', note=note, created_by=actor())
        db.session.add(row)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            bad('لهذا الشهر نتيجة مسجّلة — عدّلها', 409)
        aud('company.adresult.add', row.id, {'client_id': rid, 'period': period})
        return jsonify({'item': s_result(client, row)}), 201

    @route('/api/v2/company/ad-results/sent', ['POST'])
    def results_sent():
        b = jbody()
        ids = b.get('ids')
        if not isinstance(ids, list) or not ids or len(ids) > 100 or any(isinstance(i, bool) or not isinstance(i, int) for i in ids):
            bad('اختر كشوفًا من القائمة')
        ids = list(dict.fromkeys(ids))
        rows = []
        for i in ids:
            r = db.session.get(AdResult, i) if hasattr(db.session, 'get') else AdResult.query.get(i)
            if r is None:
                not_found('نتيجة غير موجودة')
            rows.append(r)
        now = datetime.datetime.utcnow()
        marked = []
        for r in rows:
            if r.sent_at is None:
                r.sent_at = now
                r.sent_by = actor()
                marked.append(r)
        db.session.commit()
        for r in marked:
            aud('company.adresult.sent', r.id, {'client_id': r.client_id, 'period': r.period})
        clients = {c.id: c for c in AdClient.query.filter(AdClient.id.in_([r.client_id for r in rows])).all()}
        return jsonify({'items': [s_result(clients[r.client_id], r) for r in rows if r.client_id in clients]})

    @route('/api/v2/company/ad-results/<int:rid>', ['PUT'])
    def results_update(rid):
        row = get_or_404(AdResult, rid, 'النتيجة غير موجودة')
        if row.revenue_id is not None:
            bad('حُصّل مبلغ هذا الشهر — لا يُعدَّل', 409)
        client = get_or_404(AdClient, row.client_id, 'العميل غير موجود')
        b = jbody()
        merged = {'count': row.count, 'income': row.income, 'due_manual': row.due_manual, 'note': row.note}
        merged.update({k: v for k, v in b.items() if k in merged})
        count, income, due_manual, note = result_fields(merged)
        row.count, row.income, row.note = count, income, note
        row.due_manual = due_manual if client.deal == 'other' else None
        row.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        aud('company.adresult.update', rid, {'client_id': row.client_id, 'period': row.period})
        return jsonify({'item': s_result(client, row)})

    @route('/api/v2/company/ad-results/<int:rid>', ['DELETE'])
    def results_delete(rid):
        b = jbody()
        need_confirm(b)
        row = get_or_404(AdResult, rid, 'النتيجة غير موجودة')
        if row.revenue_id is not None:
            bad('حُصّل مبلغ هذا الشهر — لا يُحذف', 409)
        meta = {'client_id': row.client_id, 'period': row.period}
        db.session.delete(row)
        db.session.commit()
        aud('company.adresult.delete', rid, meta)
        return jsonify({'ok': True})

    @route('/api/v2/company/ad-clients/<int:rid>/statement', ['GET'])
    def client_statement(rid):
        client = get_or_404(AdClient, rid, 'العميل غير موجود')
        frm, to = request.args.get('from'), request.args.get('to')
        for v in (frm, to):
            if v and not MONTH_RE.match(v):
                bad('الفترة غير صالحة', 400)
        rows, due_p, col_p, open_p = [], [], [], []
        for r in sorted(client_results(rid), key=lambda x: x.period):
            if (frm and r.period < frm) or (to and r.period > to):
                continue
            d = due_of(client, r)
            rows.append({'period': r.period, 'count': r.count, 'income': r.income, 'due': d, 'sent_at': _dt(r.sent_at), 'collected': r.revenue_id is not None})
            if d is not None:
                due_p.append((client.currency, d))
                (col_p if r.revenue_id is not None else open_p).append((client.currency, d))
        return jsonify({'client': s_client(client), 'rows': rows, 'totals': {'due': _sum_by_cur(due_p), 'collected': _sum_by_cur(col_p), 'open': _sum_by_cur(open_p)}})

    # ============================================================ المبلغ المستلم
    @route('/api/v2/company/income', ['POST'])
    def income_add():
        b = jbody()
        need_confirm(b)
        op = need_op(b)
        kind = _enum(b.get('from_kind'), ('agreement', 'ad_result'), 'المصدر')
        fid = b.get('from_id')
        if isinstance(fid, bool) or not isinstance(fid, int):
            bad('المصدر غير صالح')
        amount = _num(b.get('amount'), 'المبلغ')
        currency = _cur(b.get('currency'))
        date = _date(b.get('date') or datetime.date.today().isoformat(), 'التاريخ')
        method = _enum(b.get('method'), ('bank_transfer', 'cash', 'other'), 'طريقة الاستلام')
        if kind == 'agreement':
            src = get_or_404(Agreement, fid, 'الاتفاق غير موجود')
            if src.currency and currency != src.currency:
                bad('عملة المبلغ لازم تكون عملة الاتفاق')
            pid = 'co:agreement:%d:%s' % (fid, op)
            who, source, desc = src.party, 'sponsor', 'راعٍ: %s' % src.party
        else:
            res = get_or_404(AdResult, fid, 'النتيجة غير موجودة')
            if res.revenue_id is not None:
                bad('حُصّل مبلغ هذا الشهر من قبل', 409)
            client = get_or_404(AdClient, res.client_id, 'العميل غير موجود')
            due = due_of(client, res)
            if due is None:
                bad('لا مستحق محسوب لهذا الشهر')
            if currency != client.currency or abs(due - amount) > 0.004:
                bad('المبلغ لا يطابق المستحق')
            pid = 'co:adresult:%d' % fid
            who, source, desc = client.name, 'ad_client', 'عميل إعلانات: %s · %s' % (client.name, res.period)
        dup = Revenue.query.filter_by(payment_id=pid).first()
        if dup and kind == 'agreement':
            return jsonify({'item': {'id': dup.id, 'payment_id': dup.payment_id}, 'duplicate': True}), 200
        rev = Revenue(date=date, source=source, description=desc, client_name=who, payment_method=method, payment_id=pid,
                      amount_egp=amount if currency == 'EGP' else 0, amount_usd=amount if currency == 'USD' else 0,
                      amount_original=None if currency in ('EGP', 'USD') else amount, currency=None if currency in ('EGP', 'USD') else currency,
                      needs_fx=currency not in ('EGP', 'USD'), notes='company')
        try:
            db.session.add(rev)
            db.session.flush()
            if kind == 'ad_result':
                res.revenue_id = rev.id
                res.updated_at = datetime.datetime.utcnow()
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            again = Revenue.query.filter_by(payment_id=pid).first()
            if again is None:
                bad('تعذّر الحفظ — حاول مرة أخرى', 409)
            if kind == 'ad_result':
                bad('حُصّل مبلغ هذا الشهر من قبل', 409)
            return jsonify({'item': {'id': again.id, 'payment_id': again.payment_id}, 'duplicate': True}), 200
        aud('company.income.add', rev.id, {'from_kind': kind, 'from_id': fid, 'amount': amount, 'currency': currency})
        return jsonify({'item': {'id': rev.id, 'payment_id': rev.payment_id}}), 201

    # ============================================================ الزيارات (بروكسي قراءة)
    @route('/api/v2/company/visits', ['GET'])
    def visits():
        codes = [c for c in (request.args.get('codes') or '').split(',') if c.strip()]
        if not codes:
            return jsonify({'enabled': None, 'items': []})
        if len(codes) > 50 or any(not REF_RE.match(c.strip()) for c in codes):
            bad('الأكواد غير صالحة', 400)
        params = {'codes': ','.join(c.strip() for c in codes)}
        for k in ('from', 'to'):
            v = request.args.get(k)
            if v:
                if not DATE_RE.match(v):
                    bad('التاريخ غير صالح', 400)
                params[k] = v
        resp = _v2_get('/api/bridge/visits/by-ref', params=params)
        status = resp[1] if isinstance(resp, tuple) else getattr(resp, 'status_code', 200)
        try:
            status = int(status)
        except Exception:
            status = 502
        if status == 404:
            return jsonify({'enabled': False, 'items': []})
        if not (200 <= status < 300):
            bad('تعذّر جلب الزيارات', 502)
        try:
            r = resp[0] if isinstance(resp, tuple) else resp
            body = r.get_json(silent=True) or {}
        except Exception:
            body = {}
        items = body.get('items') if isinstance(body, dict) else None
        return jsonify({'enabled': True, 'items': items if isinstance(items, list) else []})

    # ============================================================ أهداف الشهور
    @route('/api/v2/company/forecast', ['POST'])
    def forecast_add():
        b = jbody()
        month = b.get('month')
        if not isinstance(month, str) or not MONTH_RE.match(month):
            bad('الشهر غير صالح')
        if ForecastMonth.query.filter_by(month=month).first():
            bad('هذا الشهر مسجّل — عدّله', 409)
        vals = {}
        for k, label in (('revenue_egp', 'هدف الدخل'), ('cogs_egp', 'تكلفة التنفيذ'), ('marketing_egp', 'التسويق'), ('payroll_egp', 'الرواتب'),
                         ('rent_egp', 'الإيجار'), ('other_sga_egp', 'مصروفات أخرى')):
            vals[k] = _num(b.get(k) if b.get(k) not in (None, '') else 0, label, lo_excl=False)
        for k, label in (('target_courses', 'عدد الدورات'), ('target_students', 'عدد الطلاب')):
            v = b.get(k) if b.get(k) not in (None, '') else 0
            x = _num(v, label, lo_excl=False)
            if x != int(x):
                bad('%s لازم عدد صحيح' % label)
            vals[k] = int(x)
        notes = _text(b.get('notes'), 'الملاحظة', 500)
        row = ForecastMonth(month=month, notes=notes, **vals)
        db.session.add(row)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            bad('هذا الشهر مسجّل — عدّله', 409)
        aud('company.forecast.add', row.id, {'month': month})
        return jsonify({'id': row.id}), 201
