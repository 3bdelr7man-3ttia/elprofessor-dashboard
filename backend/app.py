"""
ElProfessor Management Dashboard - Backend API
Flask + SQLAlchemy + SQLite (upgradeable to MySQL/PostgreSQL)
"""
import os, json, datetime, hashlib, secrets, functools
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import jwt
import requests

load_dotenv()

# ============================================================
# CONFIG
# ============================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
database_url = os.environ.get('DATABASE_URL', 'sqlite:///elprofessor.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app, origins=os.environ.get('CORS_ORIGINS', '*').split(','))
db = SQLAlchemy(app)
CUT_OFF_DATE = datetime.date(2026, 6, 1)
SEED_PREFIX = 'seed:v3'

# ============================================================
# MODELS
# ============================================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255))
    role = db.Column(db.String(50), default='admin')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Revenue(db.Model):
    __tablename__ = 'revenues'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    source = db.Column(db.String(100))  # course, consulting, subscription, other
    description = db.Column(db.Text)
    amount_egp = db.Column(db.Float, default=0)
    amount_usd = db.Column(db.Float, default=0)
    client_name = db.Column(db.String(255))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    payment_method = db.Column(db.String(50))  # bank_transfer, cash, stripe, wise
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(100))  # tools, hosting, marketing, travel, legal, office, bank_fees, other
    description = db.Column(db.Text)
    amount_egp = db.Column(db.Float, default=0)
    amount_usd = db.Column(db.Float, default=0)
    is_business = db.Column(db.Boolean, default=True)
    paid_by = db.Column(db.String(100))
    has_receipt = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Campaign(db.Model):
    __tablename__ = 'campaigns'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    platform = db.Column(db.String(50))  # google_ads, facebook, instagram, linkedin, tiktok
    status = db.Column(db.String(20), default='active')  # draft, active, paused, completed
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    budget = db.Column(db.Float, default=0)
    spent = db.Column(db.Float, default=0)
    currency = db.Column(db.String(5), default='USD')
    impressions = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    leads = db.Column(db.Integer, default=0)
    conversions = db.Column(db.Integer, default=0)
    revenue_attributed = db.Column(db.Float, default=0)
    target_audience = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    revenues = db.relationship('Revenue', backref='campaign', lazy=True)

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100))
    trainer_name = db.Column(db.String(255))
    status = db.Column(db.String(20), default='active')  # draft, active, completed, archived
    price_egp = db.Column(db.Float, default=0)
    price_usd = db.Column(db.Float, default=0)
    cost_egp = db.Column(db.Float, default=0)
    cost_usd = db.Column(db.Float, default=0)
    students_count = db.Column(db.Integer, default=0)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    lms_id = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    revenues = db.relationship('Revenue', backref='course', lazy=True)

class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class AILog(db.Model):
    __tablename__ = 'ai_logs'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100))
    prompt = db.Column(db.Text)
    response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), default='equipment')
    owner = db.Column(db.String(255), default='عبدالرحمن')
    value_egp = db.Column(db.Float, default=0)
    monthly_rent_egp = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='leased_to_company')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class ForecastMonth(db.Model):
    __tablename__ = 'forecast_months'
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(7), unique=True, nullable=False)
    revenue_egp = db.Column(db.Float, default=0)
    cogs_egp = db.Column(db.Float, default=0)
    marketing_egp = db.Column(db.Float, default=0)
    payroll_egp = db.Column(db.Float, default=0)
    rent_egp = db.Column(db.Float, default=0)
    other_sga_egp = db.Column(db.Float, default=0)
    target_courses = db.Column(db.Integer, default=0)
    target_students = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class CashTransaction(db.Model):
    __tablename__ = 'cash_transactions'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    kind = db.Column(db.String(50), default='capital_in')  # capital_in, cash_out, adjustment
    source = db.Column(db.String(255))
    description = db.Column(db.Text)
    amount_egp = db.Column(db.Float, default=0)
    amount_usd = db.Column(db.Float, default=0)
    related_expense_id = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Partner(db.Model):
    __tablename__ = 'partners'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(100), default='founder')
    equity_percent = db.Column(db.Float, default=0)
    profit_share_percent = db.Column(db.Float, default=0)
    capital_egp = db.Column(db.Float, default=0)
    capital_usd = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Payout(db.Model):
    __tablename__ = 'payouts'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='trainer')  # trainer, affiliate, influencer
    related_to = db.Column(db.String(255))
    basis_amount_egp = db.Column(db.Float, default=0)
    percent = db.Column(db.Float, default=0)
    amount_egp = db.Column(db.Float, default=0)
    amount_usd = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='accrued')  # accrued, paid, waived
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# ============================================================
# AUTH MIDDLEWARE
# ============================================================

def token_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token required'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            g.user = User.query.get(data['user_id'])
            if not g.user or not g.user.is_active:
                return jsonify({'error': 'Invalid user'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except Exception:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated

# ============================================================
# HELPER
# ============================================================

def get_rate():
    s = Setting.query.get('exchange_rate')
    return float(s.value) if s else 50.0

def get_setting_float(key, default=0):
    s = Setting.query.get(key)
    try:
        return float(s.value) if s else default
    except (TypeError, ValueError):
        return default

def to_egp(usd, egp, rate=None):
    if rate is None:
        rate = get_rate()
    return (egp or 0) + (usd or 0) * rate

def month_add(start, offset):
    month = start.month + offset
    year = start.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return datetime.date(year, month, 1)

def expense_total(expenses, rate):
    return sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses)

def revenue_total(revenues, rate):
    return sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in revenues)

def payout_total(payouts, rate):
    total = 0
    for p in payouts:
        total += to_egp(p.amount_usd, p.amount_egp, rate) or ((p.basis_amount_egp or 0) * (p.percent or 0) / 100)
    return total

def cash_total(cash_transactions, rate):
    total = 0
    for t in cash_transactions:
        amount = to_egp(t.amount_usd, t.amount_egp, rate)
        total += amount if t.kind in ('capital_in', 'adjustment_in') else -amount
    return total

def month_key(date_value):
    return f'{date_value.year}-{date_value.month:02d}' if date_value else None

def payout_amount(payout, rate):
    return to_egp(payout.amount_usd, payout.amount_egp, rate) or ((payout.basis_amount_egp or 0) * (payout.percent or 0) / 100)

def period_label(date_value):
    if not date_value:
        return 'unknown'
    return 'pre_launch' if date_value < CUT_OFF_DATE else 'operating'

def monthly_financial_rows(revenues, expenses, payouts, rate):
    monthly = {}
    for revenue in revenues:
        if not revenue.date:
            continue
        key = month_key(revenue.date)
        monthly.setdefault(key, {'month': key, 'revenue': 0, 'expenses': 0, 'direct_expenses': 0, 'payouts': 0, 'asset_rent': 0})
        monthly[key]['revenue'] += to_egp(revenue.amount_usd, revenue.amount_egp, rate)
    for expense in expenses:
        if not expense.date:
            continue
        key = month_key(expense.date)
        monthly.setdefault(key, {'month': key, 'revenue': 0, 'expenses': 0, 'direct_expenses': 0, 'payouts': 0, 'asset_rent': 0})
        amount = to_egp(expense.amount_usd, expense.amount_egp, rate)
        monthly[key]['expenses'] += amount
        monthly[key]['direct_expenses'] += amount
        if expense.category == 'asset_rent':
            monthly[key]['asset_rent'] += amount
    for payout in payouts:
        if not payout.date:
            continue
        key = month_key(payout.date)
        monthly.setdefault(key, {'month': key, 'revenue': 0, 'expenses': 0, 'direct_expenses': 0, 'payouts': 0, 'asset_rent': 0})
        amount = payout_amount(payout, rate)
        monthly[key]['expenses'] += amount
        monthly[key]['payouts'] += amount
    rows = []
    for key, row in sorted(monthly.items()):
        row['profit'] = row['revenue'] - row['expenses']
        row['period'] = 'pre_launch' if key < CUT_OFF_DATE.strftime('%Y-%m') else 'operating'
        rows.append({
            'month': row['month'],
            'period': row['period'],
            'revenue': round(row['revenue']),
            'expenses': round(row['expenses']),
            'direct_expenses': round(row['direct_expenses']),
            'payouts': round(row['payouts']),
            'asset_rent': round(row['asset_rent']),
            'profit': round(row['profit']),
        })
    return rows

def period_totals(revenues, expenses, payouts, rate, period_name):
    revenue_total_value = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in revenues if period_label(r.date) == period_name)
    direct_expenses = sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses if period_label(e.date) == period_name)
    payout_expenses = sum(payout_amount(p, rate) for p in payouts if period_label(p.date) == period_name)
    asset_rent = sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses if period_label(e.date) == period_name and e.category == 'asset_rent')
    return {
        'revenue': round(revenue_total_value),
        'expenses': round(direct_expenses + payout_expenses),
        'direct_expenses': round(direct_expenses),
        'payouts': round(payout_expenses),
        'asset_rent': round(asset_rent),
        'profit': round(revenue_total_value - direct_expenses - payout_expenses),
    }

def revenues_for_course(course):
    linked = list(course.revenues)
    if linked:
        return linked
    title = (course.title or '').strip()
    if not title:
        return []
    return [r for r in Revenue.query.filter_by(source='course').all() if title in (r.description or '')]

def expenses_for_course(course):
    title = (course.title or '').strip()
    if not title:
        return []
    return [
        expense for expense in Expense.query.filter_by(is_business=True).all()
        if title in (expense.description or '') or title in (expense.notes or '')
    ]

def serialize_date(d):
    return d.isoformat() if d else None

# ============================================================
# AUTH ROUTES
# ============================================================

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    user = User.query.filter_by(email=data.get('email', '').lower().strip()).first()
    if not user or not check_password_hash(user.password_hash, data.get('password', '')):
        return jsonify({'error': 'Invalid credentials'}), 401
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    return jsonify({'token': token, 'user': {'id': user.id, 'email': user.email, 'name': user.name, 'role': user.role}})

@app.route('/api/auth/me', methods=['GET'])
@token_required
def me():
    return jsonify({'id': g.user.id, 'email': g.user.email, 'name': g.user.name, 'role': g.user.role})

@app.route('/api/users', methods=['GET'])
@token_required
def list_users():
    return jsonify([{
        'id': u.id, 'email': u.email, 'name': u.name, 'role': u.role,
        'is_active': u.is_active, 'created_at': u.created_at.isoformat() if u.created_at else None
    } for u in User.query.order_by(User.created_at.desc()).all()])

@app.route('/api/users', methods=['POST'])
@token_required
def create_user():
    d = request.json or {}
    email = (d.get('email') or '').lower().strip()
    password = d.get('password') or ''
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 409
    user = User(
        email=email,
        password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
        name=d.get('name') or email.split('@')[0],
        role=d.get('role') or 'viewer',
        is_active=True
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({'id': user.id, 'message': 'تم إضافة المستخدم'}), 201

# ============================================================
# DASHBOARD / KPIs
# ============================================================

@app.route('/api/dashboard', methods=['GET'])
@token_required
def dashboard():
    rate = get_rate()
    
    # Financial KPIs
    revenues = Revenue.query.all()
    expenses = Expense.query.filter_by(is_business=True).all()
    assets = Asset.query.all()
    forecasts = ForecastMonth.query.order_by(ForecastMonth.month.asc()).limit(6).all()
    payouts = Payout.query.filter(Payout.status != 'waived').all()
    cash_transactions = CashTransaction.query.order_by(CashTransaction.date.desc()).all()
    partners = Partner.query.order_by(Partner.equity_percent.desc()).all()
    
    total_revenue = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in revenues)
    payout_cost = payout_total(payouts, rate)
    total_expenses = sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses) + payout_cost
    net_profit = total_revenue - total_expenses
    raw_revenue = get_setting_float('raw_bank_revenue_usd', 0) * rate + get_setting_float('raw_bank_revenue_egp', 0)
    raw_expenses = get_setting_float('raw_bank_expenses_usd', 0) * rate + get_setting_float('raw_bank_expenses_egp', 0)
    assets = Asset.query.all()
    total_assets = sum(a.value_egp or 0 for a in assets)
    asset_reference_rent = sum(a.monthly_rent_egp or 0 for a in assets)
    monthly_rows = monthly_financial_rows(revenues, expenses, payouts, rate)
    pre_launch = period_totals(revenues, expenses, payouts, rate, 'pre_launch')
    operating = period_totals(revenues, expenses, payouts, rate, 'operating')
    current_month_key = datetime.date.today().strftime('%Y-%m')
    current_month_row = next((row for row in monthly_rows if row['month'] == current_month_key), None)
    forecasts = ForecastMonth.query.order_by(ForecastMonth.month.asc()).all()
    next_forecast = forecasts[0] if forecasts else None
    break_even_month = None
    for fcast in forecasts:
        total_burn = (fcast.cogs_egp or 0) + (fcast.marketing_egp or 0) + (fcast.payroll_egp or 0) + (fcast.rent_egp or 0) + (fcast.other_sga_egp or 0)
        if (fcast.revenue_egp or 0) >= total_burn:
            break_even_month = fcast.month
            break
    
    opening_balance_s = Setting.query.get('opening_balance_egp')
    opening_balance = float(opening_balance_s.value) if opening_balance_s else 0
    cash_balance = cash_total(cash_transactions, rate)
    current_balance = cash_balance + net_profit
    monthly_burn = (total_expenses / max(1, len({e.date.strftime('%Y-%m') for e in expenses if e.date}))) if expenses else 0
    runway_months = round(cash_balance / monthly_burn, 1) if monthly_burn > 0 else None
    
    # Marketing KPIs
    campaigns = Campaign.query.all()
    total_ad_spend = sum(c.spent or 0 for c in campaigns)
    total_leads = sum(c.leads or 0 for c in campaigns)
    total_conversions = sum(c.conversions or 0 for c in campaigns)
    
    best_campaign = None
    if campaigns:
        best = max(campaigns, key=lambda c: c.revenue_attributed or 0)
        if best.revenue_attributed:
            best_campaign = {'id': best.id, 'name': best.name, 'revenue': best.revenue_attributed}
    
    # Courses KPIs
    courses = Course.query.all()
    total_students = sum(c.students_count or 0 for c in courses)
    
    best_course = None
    if courses:
        def course_profit(c):
            rev = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in revenues_for_course(c))
            course_payout_cost = sum(
                payout_amount(p, rate)
                for p in payouts
                if (p.related_to or '').strip() == (c.title or '').strip()
            )
            course_expense_cost = sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses_for_course(c))
            cost = to_egp(c.cost_usd, c.cost_egp, rate) + course_payout_cost + course_expense_cost
            return rev - cost
        best = max(courses, key=course_profit)
        best_course = {'id': best.id, 'title': best.title, 'profit': course_profit(best)}
    
    monthly = monthly_rows[-12:]
    
    # Alerts
    alerts = []
    if net_profit < 0:
        alerts.append({'type': 'warning', 'message': f'صافي خسارة: {abs(net_profit):,.0f} ج.م'})
    if total_revenue == 0:
        alerts.append({'type': 'info', 'message': 'لم يتم تسجيل أي إيرادات بعد'})
    if cash_balance <= 0:
        alerts.append({'type': 'danger', 'message': 'رصيد Cash Flow يحتاج ضخ رأس مال'})
    elif runway_months is not None and runway_months < 2:
        alerts.append({'type': 'warning', 'message': f'Runway قصير: حوالي {runway_months} شهر فقط'})
    unpaid_campaigns = [c for c in campaigns if c.status == 'active' and (c.spent or 0) > (c.revenue_attributed or 0) * 0.5]
    for c in unpaid_campaigns[:2]:
        alerts.append({'type': 'warning', 'message': f'حملة "{c.name}" تكلفتها أعلى من إيراداتها'})
    
    # Recent transactions
    recent_revs = Revenue.query.order_by(Revenue.date.desc()).limit(5).all()
    recent_exps = Expense.query.filter_by(is_business=True).order_by(Expense.date.desc()).limit(5).all()
    recent = sorted(
        [{'type': 'revenue', 'date': serialize_date(r.date), 'desc': r.description, 'amount': to_egp(r.amount_usd, r.amount_egp, rate)} for r in recent_revs] +
        [{'type': 'expense', 'date': serialize_date(e.date), 'desc': e.description, 'amount': -to_egp(e.amount_usd, e.amount_egp, rate)} for e in recent_exps],
        key=lambda x: x['date'] or '', reverse=True
    )[:7]
    
    return jsonify({
        'financial': {
            'total_revenue': round(total_revenue),
            'raw_bank_revenue': round(raw_revenue),
            'total_expenses': round(total_expenses),
            'raw_bank_expenses': round(raw_expenses),
            'net_profit': round(net_profit),
            'raw_bank_profit': round(raw_revenue - raw_expenses),
            'opening_balance': round(opening_balance),
            'current_balance': round(current_balance),
            'cash_balance': round(cash_balance),
            'cash_balance_usd': round(cash_balance / rate, 2) if rate else 0,
            'capital_in': round(sum(to_egp(t.amount_usd, t.amount_egp, rate) for t in cash_transactions if t.kind in ('capital_in', 'adjustment_in'))),
            'cash_out': round(sum(to_egp(t.amount_usd, t.amount_egp, rate) for t in cash_transactions if t.kind not in ('capital_in', 'adjustment_in'))),
            'payout_cost': round(payout_cost),
            'runway_months': runway_months,
            'total_assets': round(total_assets),
            'monthly_asset_rent': round(current_month_row['asset_rent']) if current_month_row else 0,
            'asset_reference_rent': round(asset_reference_rent),
            'break_even_month': break_even_month,
            'next_month_target': round(next_forecast.revenue_egp) if next_forecast else 0,
            'pre_launch_expenses': pre_launch['expenses'],
            'operating_expenses': operating['expenses'],
            'operating_revenue': operating['revenue'],
            'operating_net': operating['profit'],
            'pre_launch_net': pre_launch['profit'],
        },
        'marketing': {
            'total_ad_spend': round(total_ad_spend),
            'total_leads': total_leads,
            'total_conversions': total_conversions,
            'best_campaign': best_campaign,
            'cpl': round(total_ad_spend / total_leads, 2) if total_leads else 0,
            'cac': round(total_ad_spend / total_conversions, 2) if total_conversions else 0,
        },
        'courses': {
            'total_courses': len(courses),
            'total_students': total_students,
            'best_course': best_course,
        },
        'monthly': monthly,
        'periods': {
            'cutoff_month': CUT_OFF_DATE.strftime('%Y-%m'),
            'pre_launch': pre_launch,
            'operating': operating,
        },
        'forecast': [{
            'month': f.month,
            'revenue': round(f.revenue_egp or 0),
            'expenses': round((f.cogs_egp or 0) + (f.marketing_egp or 0) + (f.payroll_egp or 0) + (f.rent_egp or 0) + (f.other_sga_egp or 0)),
            'marketing': round(f.marketing_egp or 0),
            'target_courses': f.target_courses,
            'target_students': f.target_students
        } for f in forecasts[:12]],
        'alerts': alerts,
        'recent': recent,
        'partners': [{
            'name': p.name, 'role': p.role, 'equity_percent': p.equity_percent,
            'profit_share_percent': p.profit_share_percent,
            'capital_egp': round(to_egp(p.capital_usd, p.capital_egp, rate))
        } for p in partners],
        'exchange_rate': rate,
    })

# ============================================================
# REVENUE CRUD
# ============================================================

@app.route('/api/revenues', methods=['GET'])
@token_required
def list_revenues():
    items = Revenue.query.order_by(Revenue.date.desc()).all()
    rate = get_rate()
    return jsonify([{
        'id': r.id, 'date': serialize_date(r.date), 'source': r.source,
        'description': r.description, 'amount_egp': r.amount_egp, 'amount_usd': r.amount_usd,
        'total_egp': round(to_egp(r.amount_usd, r.amount_egp, rate)),
        'client_name': r.client_name, 'course_id': r.course_id, 'campaign_id': r.campaign_id,
        'payment_method': r.payment_method, 'notes': r.notes
    } for r in items])

@app.route('/api/revenues', methods=['POST'])
@token_required
def create_revenue():
    d = request.json or {}
    r = Revenue(
        date=datetime.date.fromisoformat(d['date']),
        source=d.get('source', 'other'),
        description=d.get('description', ''),
        amount_egp=d.get('amount_egp', 0),
        amount_usd=d.get('amount_usd', 0),
        client_name=d.get('client_name', ''),
        course_id=d.get('course_id'),
        campaign_id=d.get('campaign_id'),
        payment_method=d.get('payment_method', ''),
        notes=d.get('notes', '')
    )
    db.session.add(r)
    db.session.commit()
    return jsonify({'id': r.id, 'message': 'تم إضافة الإيراد'}), 201

@app.route('/api/revenues/<int:id>', methods=['PUT'])
@token_required
def update_revenue(id):
    r = Revenue.query.get_or_404(id)
    d = request.json or {}
    for k in ['source', 'description', 'amount_egp', 'amount_usd', 'client_name', 'course_id', 'campaign_id', 'payment_method', 'notes']:
        if k in d:
            setattr(r, k, d[k])
    if 'date' in d:
        r.date = datetime.date.fromisoformat(d['date'])
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/revenues/<int:id>', methods=['DELETE'])
@token_required
def delete_revenue(id):
    r = Revenue.query.get_or_404(id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

# ============================================================
# EXPENSE CRUD
# ============================================================

@app.route('/api/expenses', methods=['GET'])
@token_required
def list_expenses():
    items = Expense.query.order_by(Expense.date.desc()).all()
    rate = get_rate()
    return jsonify([{
        'id': e.id, 'date': serialize_date(e.date), 'category': e.category,
        'description': e.description, 'amount_egp': e.amount_egp, 'amount_usd': e.amount_usd,
        'total_egp': round(to_egp(e.amount_usd, e.amount_egp, rate)),
        'is_business': e.is_business, 'paid_by': e.paid_by, 'has_receipt': e.has_receipt, 'notes': e.notes
    } for e in items])

@app.route('/api/assets', methods=['GET'])
@token_required
def list_assets():
    items = Asset.query.order_by(Asset.category.asc(), Asset.value_egp.desc()).all()
    return jsonify([{
        'id': a.id, 'name': a.name, 'category': a.category, 'owner': a.owner,
        'value_egp': a.value_egp, 'monthly_rent_egp': a.monthly_rent_egp,
        'status': a.status, 'notes': a.notes
    } for a in items])

@app.route('/api/assets', methods=['POST'])
@token_required
def create_asset():
    d = request.json or {}
    a = Asset(
        name=d.get('name', ''), category=d.get('category', 'equipment'),
        owner=d.get('owner', 'عبدالرحمن'), value_egp=d.get('value_egp', 0),
        monthly_rent_egp=d.get('monthly_rent_egp', 0),
        status=d.get('status', 'leased_to_company'), notes=d.get('notes', '')
    )
    db.session.add(a)
    db.session.commit()
    return jsonify({'id': a.id, 'message': 'تم إضافة الأصل'}), 201

@app.route('/api/assets/<int:id>', methods=['PUT'])
@token_required
def update_asset(id):
    a = Asset.query.get_or_404(id)
    d = request.json or {}
    for k in ['name', 'category', 'owner', 'value_egp', 'monthly_rent_egp', 'status', 'notes']:
        if k in d:
            setattr(a, k, d[k])
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/assets/<int:id>', methods=['DELETE'])
@token_required
def delete_asset(id):
    a = Asset.query.get_or_404(id)
    db.session.delete(a)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

@app.route('/api/forecast', methods=['GET'])
@token_required
def list_forecast():
    items = ForecastMonth.query.order_by(ForecastMonth.month.asc()).all()
    return jsonify([{
        'id': f.id, 'month': f.month, 'revenue_egp': f.revenue_egp, 'cogs_egp': f.cogs_egp,
        'marketing_egp': f.marketing_egp, 'payroll_egp': f.payroll_egp, 'rent_egp': f.rent_egp,
        'other_sga_egp': f.other_sga_egp,
        'total_expenses': (f.cogs_egp or 0) + (f.marketing_egp or 0) + (f.payroll_egp or 0) + (f.rent_egp or 0) + (f.other_sga_egp or 0),
        'ebitda': (f.revenue_egp or 0) - ((f.cogs_egp or 0) + (f.marketing_egp or 0) + (f.payroll_egp or 0) + (f.rent_egp or 0) + (f.other_sga_egp or 0)),
        'target_courses': f.target_courses, 'target_students': f.target_students, 'notes': f.notes
    } for f in items])

@app.route('/api/forecast/<int:id>', methods=['PUT'])
@token_required
def update_forecast(id):
    f = ForecastMonth.query.get_or_404(id)
    d = request.json or {}
    for k in ['revenue_egp', 'cogs_egp', 'marketing_egp', 'payroll_egp', 'rent_egp', 'other_sga_egp', 'target_courses', 'target_students', 'notes']:
        if k in d:
            setattr(f, k, d[k])
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/expenses', methods=['POST'])
@token_required
def create_expense():
    d = request.json or {}
    e = Expense(
        date=datetime.date.fromisoformat(d['date']),
        category=d.get('category', 'other'),
        description=d.get('description', ''),
        amount_egp=d.get('amount_egp', 0),
        amount_usd=d.get('amount_usd', 0),
        is_business=d.get('is_business', True),
        paid_by=d.get('paid_by', ''),
        has_receipt=d.get('has_receipt', False),
        notes=d.get('notes', '')
    )
    db.session.add(e)
    db.session.flush()
    if d.get('cash_impact'):
        db.session.add(CashTransaction(
            date=e.date,
            kind='cash_out',
            source=d.get('paid_by', 'company_cash'),
            description=f'مصروف من Cash Flow: {e.description}',
            amount_egp=e.amount_egp,
            amount_usd=e.amount_usd,
            related_expense_id=e.id,
            notes='Generated from expense entry'
        ))
    db.session.commit()
    return jsonify({'id': e.id, 'message': 'تم إضافة المصروف'}), 201

@app.route('/api/expenses/<int:id>', methods=['PUT'])
@token_required
def update_expense(id):
    e = Expense.query.get_or_404(id)
    d = request.json or {}
    for k in ['category', 'description', 'amount_egp', 'amount_usd', 'is_business', 'paid_by', 'has_receipt', 'notes']:
        if k in d:
            setattr(e, k, d[k])
    if 'date' in d:
        e.date = datetime.date.fromisoformat(d['date'])
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/expenses/<int:id>', methods=['DELETE'])
@token_required
def delete_expense(id):
    e = Expense.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

# ============================================================
# CAMPAIGN CRUD
# ============================================================

@app.route('/api/campaigns', methods=['GET'])
@token_required
def list_campaigns():
    items = Campaign.query.order_by(Campaign.created_at.desc()).all()
    result = []
    for c in items:
        cpl = round(c.spent / c.leads, 2) if c.leads else 0
        cac = round(c.spent / c.conversions, 2) if c.conversions else 0
        roas = round(c.revenue_attributed / c.spent, 2) if c.spent else 0
        conv_rate = round(c.conversions / c.leads * 100, 1) if c.leads else 0
        # Recommendation logic
        if roas >= 3:
            recommendation = 'continue'
        elif roas >= 1:
            recommendation = 'optimize'
        else:
            recommendation = 'stop' if c.spent > 0 else 'monitor'
        result.append({
            'id': c.id, 'name': c.name, 'platform': c.platform, 'status': c.status,
            'start_date': serialize_date(c.start_date), 'end_date': serialize_date(c.end_date),
            'budget': c.budget, 'spent': c.spent, 'currency': c.currency,
            'impressions': c.impressions, 'clicks': c.clicks, 'leads': c.leads,
            'conversions': c.conversions, 'revenue_attributed': c.revenue_attributed,
            'cpl': cpl, 'cac': cac, 'roas': roas, 'conversion_rate': conv_rate,
            'recommendation': recommendation,
            'target_audience': c.target_audience, 'notes': c.notes
        })
    return jsonify(result)

@app.route('/api/campaigns', methods=['POST'])
@token_required
def create_campaign():
    d = request.json or {}
    c = Campaign(
        name=d['name'], platform=d.get('platform', ''),
        status=d.get('status', 'active'),
        start_date=datetime.date.fromisoformat(d['start_date']) if d.get('start_date') else None,
        end_date=datetime.date.fromisoformat(d['end_date']) if d.get('end_date') else None,
        budget=d.get('budget', 0), spent=d.get('spent', 0), currency=d.get('currency', 'USD'),
        impressions=d.get('impressions', 0), clicks=d.get('clicks', 0),
        leads=d.get('leads', 0), conversions=d.get('conversions', 0),
        revenue_attributed=d.get('revenue_attributed', 0),
        target_audience=d.get('target_audience', ''), notes=d.get('notes', '')
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({'id': c.id, 'message': 'تم إضافة الحملة'}), 201

@app.route('/api/campaigns/<int:id>', methods=['PUT'])
@token_required
def update_campaign(id):
    c = Campaign.query.get_or_404(id)
    d = request.json or {}
    for k in ['name', 'platform', 'status', 'budget', 'spent', 'currency', 'impressions', 'clicks', 'leads', 'conversions', 'revenue_attributed', 'target_audience', 'notes']:
        if k in d:
            setattr(c, k, d[k])
    for dk in ['start_date', 'end_date']:
        if dk in d and d[dk]:
            setattr(c, dk, datetime.date.fromisoformat(d[dk]))
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/campaigns/<int:id>', methods=['DELETE'])
@token_required
def delete_campaign(id):
    c = Campaign.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

# ============================================================
# COURSE CRUD
# ============================================================

@app.route('/api/courses', methods=['GET'])
@token_required
def list_courses():
    items = Course.query.order_by(Course.created_at.desc()).all()
    rate = get_rate()
    payouts = Payout.query.filter(Payout.status != 'waived').all()
    result = []
    for c in items:
        course_revenues = revenues_for_course(c)
        course_expenses = expenses_for_course(c)
        total_revenue = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in course_revenues)
        linked_payout_cost = sum(
            payout_amount(p, rate)
            for p in payouts
            if (p.related_to or '').strip() == (c.title or '').strip()
        )
        linked_expense_cost = sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in course_expenses)
        total_cost = to_egp(c.cost_usd, c.cost_egp, rate) + linked_payout_cost + linked_expense_cost
        profit = total_revenue - total_cost
        result.append({
            'id': c.id, 'title': c.title, 'category': c.category,
            'trainer_name': c.trainer_name, 'status': c.status,
            'price_egp': c.price_egp, 'price_usd': c.price_usd,
            'cost_egp': c.cost_egp, 'cost_usd': c.cost_usd,
            'students_count': c.students_count,
            'start_date': serialize_date(c.start_date), 'end_date': serialize_date(c.end_date),
            'total_revenue': round(total_revenue), 'total_cost': round(total_cost),
            'linked_expense_cost': round(linked_expense_cost),
            'linked_payout_cost': round(linked_payout_cost),
            'profit': round(profit), 'lms_id': c.lms_id, 'notes': c.notes
        })
    return jsonify(result)

@app.route('/api/courses', methods=['POST'])
@token_required
def create_course():
    d = request.json or {}
    c = Course(
        title=d['title'], category=d.get('category', ''),
        trainer_name=d.get('trainer_name', ''), status=d.get('status', 'active'),
        price_egp=d.get('price_egp', 0), price_usd=d.get('price_usd', 0),
        cost_egp=d.get('cost_egp', 0), cost_usd=d.get('cost_usd', 0),
        students_count=d.get('students_count', 0),
        start_date=datetime.date.fromisoformat(d['start_date']) if d.get('start_date') else None,
        end_date=datetime.date.fromisoformat(d['end_date']) if d.get('end_date') else None,
        lms_id=d.get('lms_id', ''), notes=d.get('notes', '')
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({'id': c.id, 'message': 'تم إضافة الدورة'}), 201

@app.route('/api/courses/<int:id>', methods=['PUT'])
@token_required
def update_course(id):
    c = Course.query.get_or_404(id)
    d = request.json or {}
    for k in ['title', 'category', 'trainer_name', 'status', 'price_egp', 'price_usd', 'cost_egp', 'cost_usd', 'students_count', 'lms_id', 'notes']:
        if k in d:
            setattr(c, k, d[k])
    for dk in ['start_date', 'end_date']:
        if dk in d and d[dk]:
            setattr(c, dk, datetime.date.fromisoformat(d[dk]))
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/courses/<int:id>', methods=['DELETE'])
@token_required
def delete_course(id):
    c = Course.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

# ============================================================
# SETTINGS
# ============================================================

@app.route('/api/settings', methods=['GET'])
@token_required
def get_settings():
    items = Setting.query.all()
    return jsonify({s.key: s.value for s in items})

@app.route('/api/settings', methods=['PUT'])
@token_required
def update_settings():
    d = request.json or {}
    for k, v in d.items():
        s = Setting.query.get(k)
        if s:
            s.value = str(v)
            s.updated_at = datetime.datetime.utcnow()
        else:
            s = Setting(key=k, value=str(v))
            db.session.add(s)
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

# ============================================================
# CASH FLOW / PARTNERS / PAYOUTS
# ============================================================

@app.route('/api/cashflow', methods=['GET'])
@token_required
def list_cashflow():
    rate = get_rate()
    items = CashTransaction.query.order_by(CashTransaction.date.desc(), CashTransaction.id.desc()).all()
    return jsonify({
        'balance_egp': round(cash_total(items, rate)),
        'balance_usd': round(cash_total(items, rate) / rate, 2) if rate else 0,
        'capital_in': round(sum(to_egp(t.amount_usd, t.amount_egp, rate) for t in items if t.kind in ('capital_in', 'adjustment_in'))),
        'cash_out': round(sum(to_egp(t.amount_usd, t.amount_egp, rate) for t in items if t.kind not in ('capital_in', 'adjustment_in'))),
        'transactions': [{
            'id': t.id, 'date': serialize_date(t.date), 'kind': t.kind, 'source': t.source,
            'description': t.description, 'amount_egp': t.amount_egp, 'amount_usd': t.amount_usd,
            'total_egp': round(to_egp(t.amount_usd, t.amount_egp, rate)),
            'related_expense_id': t.related_expense_id, 'notes': t.notes
        } for t in items]
    })

@app.route('/api/cashflow', methods=['POST'])
@token_required
def create_cashflow():
    d = request.json or {}
    t = CashTransaction(
        date=datetime.date.fromisoformat(d.get('date') or datetime.date.today().isoformat()),
        kind=d.get('kind', 'capital_in'),
        source=d.get('source', ''),
        description=d.get('description', ''),
        amount_egp=d.get('amount_egp', 0),
        amount_usd=d.get('amount_usd', 0),
        related_expense_id=d.get('related_expense_id'),
        notes=d.get('notes', '')
    )
    db.session.add(t)
    db.session.commit()
    return jsonify({'id': t.id, 'message': 'تم تسجيل حركة الكاش فلو'}), 201

@app.route('/api/cashflow/<int:id>', methods=['PUT'])
@token_required
def update_cashflow(id):
    t = CashTransaction.query.get_or_404(id)
    d = request.json or {}
    for k in ['kind', 'source', 'description', 'amount_egp', 'amount_usd', 'related_expense_id', 'notes']:
        if k in d:
            setattr(t, k, d[k])
    if 'date' in d:
        t.date = datetime.date.fromisoformat(d['date'])
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/cashflow/<int:id>', methods=['DELETE'])
@token_required
def delete_cashflow(id):
    t = CashTransaction.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

@app.route('/api/partners', methods=['GET'])
@token_required
def list_partners():
    rate = get_rate()
    items = Partner.query.order_by(Partner.equity_percent.desc()).all()
    return jsonify([{
        'id': p.id, 'name': p.name, 'role': p.role,
        'equity_percent': p.equity_percent, 'profit_share_percent': p.profit_share_percent,
        'capital_egp': p.capital_egp, 'capital_usd': p.capital_usd,
        'total_capital_egp': round(to_egp(p.capital_usd, p.capital_egp, rate)),
        'notes': p.notes
    } for p in items])

@app.route('/api/partners', methods=['POST'])
@token_required
def create_partner():
    d = request.json or {}
    p = Partner(
        name=d.get('name', ''), role=d.get('role', 'founder'),
        equity_percent=d.get('equity_percent', 0),
        profit_share_percent=d.get('profit_share_percent', d.get('equity_percent', 0)),
        capital_egp=d.get('capital_egp', 0), capital_usd=d.get('capital_usd', 0),
        notes=d.get('notes', '')
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'id': p.id, 'message': 'تم إضافة الشريك'}), 201

@app.route('/api/partners/<int:id>', methods=['PUT'])
@token_required
def update_partner(id):
    p = Partner.query.get_or_404(id)
    d = request.json or {}
    for k in ['name', 'role', 'equity_percent', 'profit_share_percent', 'capital_egp', 'capital_usd', 'notes']:
        if k in d:
            setattr(p, k, d[k])
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/partners/<int:id>', methods=['DELETE'])
@token_required
def delete_partner(id):
    p = Partner.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

@app.route('/api/payouts', methods=['GET'])
@token_required
def list_payouts():
    rate = get_rate()
    items = Payout.query.order_by(Payout.date.desc()).all()
    return jsonify([{
        'id': p.id, 'date': serialize_date(p.date), 'name': p.name, 'role': p.role,
        'related_to': p.related_to, 'basis_amount_egp': p.basis_amount_egp,
        'percent': p.percent, 'amount_egp': p.amount_egp, 'amount_usd': p.amount_usd,
        'total_egp': round(to_egp(p.amount_usd, p.amount_egp, rate) or ((p.basis_amount_egp or 0) * (p.percent or 0) / 100)),
        'status': p.status, 'notes': p.notes
    } for p in items])

@app.route('/api/payouts', methods=['POST'])
@token_required
def create_payout():
    d = request.json or {}
    p = Payout(
        date=datetime.date.fromisoformat(d.get('date') or datetime.date.today().isoformat()),
        name=d.get('name', ''), role=d.get('role', 'trainer'), related_to=d.get('related_to', ''),
        basis_amount_egp=d.get('basis_amount_egp', 0), percent=d.get('percent', 0),
        amount_egp=d.get('amount_egp', 0), amount_usd=d.get('amount_usd', 0),
        status=d.get('status', 'accrued'), notes=d.get('notes', '')
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'id': p.id, 'message': 'تم تسجيل الاستحقاق'}), 201

@app.route('/api/payouts/<int:id>', methods=['PUT'])
@token_required
def update_payout(id):
    p = Payout.query.get_or_404(id)
    d = request.json or {}
    for k in ['name', 'role', 'related_to', 'basis_amount_egp', 'percent', 'amount_egp', 'amount_usd', 'status', 'notes']:
        if k in d:
            setattr(p, k, d[k])
    if 'date' in d:
        p.date = datetime.date.fromisoformat(d['date'])
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/payouts/<int:id>', methods=['DELETE'])
@token_required
def delete_payout(id):
    p = Payout.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

# ============================================================
# AI ASSISTANT
# ============================================================

AI_PROVIDERS = {
    'anthropic': {
        'label': 'Claude',
        'env_key': 'ANTHROPIC_API_KEY',
        'model_env': 'ANTHROPIC_MODEL',
        'default_model': 'claude-sonnet-4-20250514',
        'models': ['claude-sonnet-4-20250514', 'claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest'],
    },
    'openai': {
        'label': 'ChatGPT',
        'env_key': 'OPENAI_API_KEY',
        'model_env': 'OPENAI_MODEL',
        'default_model': 'gpt-4.1-mini',
        'models': ['gpt-4.1-mini', 'gpt-4.1', 'gpt-4o-mini'],
    },
    'deepseek': {
        'label': 'DeepSeek',
        'env_key': 'DEEPSEEK_API_KEY',
        'model_env': 'DEEPSEEK_MODEL',
        'default_model': 'deepseek-chat',
        'models': ['deepseek-chat', 'deepseek-reasoner'],
    },
}

def ai_models_payload():
    payload = []
    for key, cfg in AI_PROVIDERS.items():
        default_model = os.environ.get(cfg['model_env'], cfg['default_model'])
        models = list(dict.fromkeys([default_model] + cfg['models']))
        payload.append({
            'id': key,
            'label': cfg['label'],
            'configured': bool(os.environ.get(cfg['env_key'])),
            'default_model': default_model,
            'models': models,
        })
    return payload

def build_ai_messages(question, snapshot):
    system_prompt = """أنت مساعد إداري ومالي لشركة "البروفيسور" (ElProfessor) - منصة تعليم قانوني مصرية.
أجب بالعربية. كن مختصراً ودقيقاً. استخدم الأرقام الفعلية من البيانات المرفقة.
نسّق الأرقام بالفاصلة. إذا طُلب منك تقرير، اجعله منظماً بعناوين فرعية."""
    user_content = f"{question}\n\nبيانات الشركة الحالية:\n{json.dumps(snapshot, ensure_ascii=False, indent=2)}"
    return system_prompt, user_content

def call_anthropic(api_key, model, system_prompt, user_content):
    r = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'content-type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
        },
        json={
            'model': model,
            'max_tokens': 1200,
            'system': system_prompt,
            'messages': [{'role': 'user', 'content': user_content}],
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    return '\n'.join(part.get('text', '') for part in data.get('content', []) if part.get('type') == 'text')

def call_openai_compatible(base_url, api_key, model, system_prompt, user_content):
    r = requests.post(
        f'{base_url}/chat/completions',
        headers={'authorization': f'Bearer {api_key}', 'content-type': 'application/json'},
        json={
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_content},
            ],
            'temperature': 0.2,
            'max_tokens': 1200,
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    return data.get('choices', [{}])[0].get('message', {}).get('content', '')

def answer_with_ai(provider, model, question, snapshot):
    cfg = AI_PROVIDERS.get(provider)
    if not cfg:
        raise ValueError('Unsupported AI provider')
    api_key = os.environ.get(cfg['env_key'])
    if not api_key:
        raise RuntimeError(f'{cfg["label"]} API key is not configured')
    model = model or os.environ.get(cfg['model_env'], cfg['default_model'])
    system_prompt, user_content = build_ai_messages(question, snapshot)
    if provider == 'anthropic':
        return call_anthropic(api_key, model, system_prompt, user_content)
    if provider == 'openai':
        return call_openai_compatible('https://api.openai.com/v1', api_key, model, system_prompt, user_content)
    if provider == 'deepseek':
        return call_openai_compatible('https://api.deepseek.com/v1', api_key, model, system_prompt, user_content)
    raise ValueError('Unsupported AI provider')

@app.route('/api/ai/models', methods=['GET'])
@token_required
def ai_models():
    return jsonify(ai_models_payload())

def generate_ai_snapshot():
    """Generate a structured data snapshot for AI consumption."""
    rate = get_rate()
    revenues = Revenue.query.all()
    expenses = Expense.query.filter_by(is_business=True).all()
    payouts = Payout.query.filter(Payout.status != 'waived').all()
    cash_transactions = CashTransaction.query.order_by(CashTransaction.date.desc()).all()
    campaigns = Campaign.query.all()
    courses = Course.query.all()
    assets = Asset.query.all()
    forecasts = ForecastMonth.query.order_by(ForecastMonth.month.asc()).limit(6).all()
    
    total_rev = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in revenues)
    payout_cost = payout_total(payouts, rate)
    cash_balance = cash_total(cash_transactions, rate)
    total_exp = sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses) + payout_cost
    
    # Revenue by source
    rev_by_source = {}
    for r in revenues:
        s = r.source or 'other'
        rev_by_source[s] = rev_by_source.get(s, 0) + to_egp(r.amount_usd, r.amount_egp, rate)
    
    # Expense by category
    exp_by_cat = {}
    for e in expenses:
        c = e.category or 'other'
        exp_by_cat[c] = exp_by_cat.get(c, 0) + to_egp(e.amount_usd, e.amount_egp, rate)
    
    # Top clients
    client_totals = {}
    for r in revenues:
        if r.client_name:
            client_totals[r.client_name] = client_totals.get(r.client_name, 0) + to_egp(r.amount_usd, r.amount_egp, rate)
    top_clients = sorted(client_totals.items(), key=lambda x: -x[1])[:5]
    
    snapshot = {
        'company': 'البروفيسور - ElProfessor',
        'type': 'منصة تعليم قانوني وأدوات قانونية بالذكاء الاصطناعي',
        'date': datetime.date.today().isoformat(),
        'financials': {
            'total_revenue_egp': round(total_rev),
            'total_expenses_egp': round(total_exp),
            'net_profit_egp': round(total_rev - total_exp),
            'revenue_count': len(revenues),
            'expense_count': len(expenses),
            'revenue_by_source': {k: round(v) for k, v in rev_by_source.items()},
            'expenses_by_category': {k: round(v) for k, v in exp_by_cat.items()},
            'payout_cost_egp': round(payout_cost),
            'cash_balance_egp': round(cash_balance),
            'cash_balance_usd': round(cash_balance / rate, 2) if rate else 0,
            'top_clients': [{'name': n, 'total_egp': round(t)} for n, t in top_clients],
            'raw_bank_revenue_egp': round(get_setting_float('raw_bank_revenue_usd', 0) * rate + get_setting_float('raw_bank_revenue_egp', 0)),
            'raw_bank_expenses_egp': round(get_setting_float('raw_bank_expenses_usd', 0) * rate + get_setting_float('raw_bank_expenses_egp', 0)),
        },
        'cashflow': {
            'balance_egp': round(cash_balance),
            'balance_usd': round(cash_balance / rate, 2) if rate else 0,
            'transactions': [{'date': serialize_date(t.date), 'kind': t.kind, 'source': t.source, 'description': t.description, 'total_egp': round(to_egp(t.amount_usd, t.amount_egp, rate))} for t in cash_transactions[:10]],
        },
        'payouts': [{'name': p.name, 'role': p.role, 'related_to': p.related_to, 'percent': p.percent, 'total_egp': round(to_egp(p.amount_usd, p.amount_egp, rate) or ((p.basis_amount_egp or 0) * (p.percent or 0) / 100)), 'status': p.status} for p in payouts],
        'marketing': {
            'campaigns_count': len(campaigns),
            'total_ad_spend': sum(c.spent or 0 for c in campaigns),
            'total_leads': sum(c.leads or 0 for c in campaigns),
            'total_conversions': sum(c.conversions or 0 for c in campaigns),
            'campaigns': [{'name': c.name, 'platform': c.platform, 'spent': c.spent, 'leads': c.leads, 'conversions': c.conversions, 'roas': round(c.revenue_attributed / c.spent, 2) if c.spent else 0} for c in campaigns]
        },
        'courses': {
            'count': len(courses),
            'total_students': sum(c.students_count or 0 for c in courses),
            'courses': [{'title': c.title, 'students': c.students_count, 'status': c.status} for c in courses]
        },
        'assets': {
            'total_value_egp': round(sum(a.value_egp or 0 for a in assets)),
            'monthly_rent_egp': round(sum(a.monthly_rent_egp or 0 for a in assets)),
            'items': [{'name': a.name, 'owner': a.owner, 'value_egp': a.value_egp, 'monthly_rent_egp': a.monthly_rent_egp} for a in assets],
        },
        'forecast': [{'month': f.month, 'revenue_egp': f.revenue_egp, 'total_expenses_egp': (f.cogs_egp or 0) + (f.marketing_egp or 0) + (f.payroll_egp or 0) + (f.rent_egp or 0) + (f.other_sga_egp or 0), 'target_courses': f.target_courses, 'target_students': f.target_students} for f in forecasts],
        'exchange_rate': rate
    }
    return snapshot

@app.route('/api/ai/snapshot', methods=['GET'])
@token_required
def ai_snapshot():
    return jsonify(generate_ai_snapshot())

@app.route('/api/ai/ask', methods=['POST'])
@token_required
def ai_ask():
    """Proxy to the selected AI model. Expects {question, provider, model}."""
    d = request.json or {}
    question = (d.get('question') or '').strip()
    provider = d.get('provider') or 'anthropic'
    model = d.get('model')
    if not question:
        return jsonify({'error': 'Question is required'}), 400
    
    log = AILog(action=f'ask:{provider}:{model or "default"}', prompt=question)
    db.session.add(log)
    db.session.commit()

    try:
        snapshot = generate_ai_snapshot()
        response = answer_with_ai(provider, model, question, snapshot)
        log.response = response
        db.session.commit()
        return jsonify({'question': question, 'provider': provider, 'model': model, 'log_id': log.id, 'response': response})
    except Exception as exc:
        log.response = f'ERROR: {exc}'
        db.session.commit()
        return jsonify({'error': str(exc), 'models': ai_models_payload(), 'log_id': log.id}), 502

@app.route('/api/ai/log', methods=['POST'])
@token_required
def ai_log_response():
    """Log AI response for audit"""
    d = request.json or {}
    log_id = d.get('log_id')
    if log_id:
        log = AILog.query.get(log_id)
        if log:
            log.response = d.get('response', '')
            db.session.commit()
    return jsonify({'message': 'logged'})

# ============================================================
# FINANCIAL SUMMARY
# ============================================================

@app.route('/api/finance/summary', methods=['GET'])
@token_required
def finance_summary():
    rate = get_rate()
    revenues = Revenue.query.all()
    expenses = Expense.query.filter_by(is_business=True).all()
    payouts = Payout.query.filter(Payout.status != 'waived').all()
    cash_transactions = CashTransaction.query.order_by(CashTransaction.date.desc()).all()

    monthly_list = monthly_financial_rows(revenues, expenses, payouts, rate)

    # By category
    cat_totals = {}
    for e in expenses:
        c = e.category or 'other'
        cat_totals[c] = cat_totals.get(c, 0) + to_egp(e.amount_usd, e.amount_egp, rate)
    for p in payouts:
        c = p.role or 'payout'
        cat_totals[c] = cat_totals.get(c, 0) + payout_amount(p, rate)

    pre_launch = period_totals(revenues, expenses, payouts, rate, 'pre_launch')
    operating = period_totals(revenues, expenses, payouts, rate, 'operating')

    return jsonify({
        'monthly': monthly_list,
        'expense_categories': [{'category': k, 'total': round(v)} for k, v in sorted(cat_totals.items(), key=lambda x: -x[1])],
        'total_revenue': round(sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in revenues)),
        'total_expenses': round(sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses) + payout_total(payouts, rate)),
        'payout_cost': round(payout_total(payouts, rate)),
        'cutoff_month': CUT_OFF_DATE.strftime('%Y-%m'),
        'pre_launch': pre_launch,
        'operating': operating,
        'cashflow': {
            'balance_egp': round(cash_total(cash_transactions, rate)),
            'balance_usd': round(cash_total(cash_transactions, rate) / rate, 2) if rate else 0,
        },
        'exchange_rate': rate,
    })

# ============================================================
# SEED DATA
# ============================================================

def seed():
    """Seed initial data"""
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@elprofessor.com').lower().strip()
    if not User.query.filter_by(email=admin_email).first():
        admin = User(
            email=admin_email,
            password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin123'), method='pbkdf2:sha256'),
            name=os.environ.get('ADMIN_NAME', 'عبدالرحمن'),
            role='admin'
        )
        db.session.add(admin)
    
    def upsert_setting(key, value):
        item = Setting.query.get(key)
        if item:
            item.value = str(value)
        else:
            db.session.add(Setting(key=key, value=str(value)))

    def upsert_seed_revenue(description, payload):
        item = Revenue.query.filter_by(description=description).first()
        if not item:
            item = Revenue(description=description)
            db.session.add(item)
        item.date = payload['date']
        item.source = payload.get('source', 'other')
        item.amount_egp = payload.get('amount_egp', 0)
        item.amount_usd = payload.get('amount_usd', 0)
        item.client_name = payload.get('client_name', '')
        item.payment_method = payload.get('payment_method', '')
        item.notes = payload.get('notes', SEED_PREFIX)

    def sync_seed_expenses(definitions):
        managed_items = Expense.query.filter(Expense.notes.like(f'{SEED_PREFIX}%')).all()
        for item in managed_items:
            db.session.delete(item)
        legacy_descriptions = {
            'تأسيس واستضافة وبنية تحتية',
            'اشتراكات AI وأدوات إنتاج',
            'مساحة عمل وتجهيزات تشغيل',
            'تجارب تسويق ومحتوى وإطلاق',
            'تأسيس قانوني وإجراءات واستشارات',
            'إيجار أصول مؤسس للشركة - شهر مايو',
        }
        for item in Expense.query.filter(Expense.description.in_(legacy_descriptions)).all():
            db.session.delete(item)
        for payload in definitions:
            db.session.add(Expense(
                date=payload['date'],
                category=payload['category'],
                description=payload['description'],
                amount_egp=payload.get('amount_egp', 0),
                amount_usd=payload.get('amount_usd', 0),
                is_business=payload.get('is_business', True),
                paid_by=payload.get('paid_by', 'عبدالرحمن'),
                notes=f"{SEED_PREFIX}:{payload.get('seed_key', payload['description'])}"
            ))

    def upsert_asset(name, category, usd, monthly_rent_egp, notes):
        item = Asset.query.filter_by(name=name).first()
        if not item:
            item = Asset(name=name)
            db.session.add(item)
        item.category = category
        item.owner = 'عبدالرحمن'
        item.value_egp = usd * 50
        item.monthly_rent_egp = monthly_rent_egp
        item.status = 'leased_to_company'
        item.notes = notes

    def upsert_partner(name, role, equity, profit, capital_usd, notes):
        item = Partner.query.filter_by(name=name).first()
        if not item:
            item = Partner(name=name)
            db.session.add(item)
        item.role = role
        item.equity_percent = equity
        item.profit_share_percent = profit
        item.capital_usd = capital_usd
        item.notes = notes

    def upsert_payout(name, related_to, payload):
        item = Payout.query.filter_by(name=name, related_to=related_to).first()
        if not item:
            item = Payout(name=name, related_to=related_to)
            db.session.add(item)
        item.date = payload['date']
        item.role = payload.get('role', 'trainer')
        item.basis_amount_egp = payload.get('basis_amount_egp', 0)
        item.percent = payload.get('percent', 0)
        item.amount_egp = payload.get('amount_egp', 0)
        item.amount_usd = payload.get('amount_usd', 0)
        item.status = payload.get('status', 'accrued')
        item.notes = payload.get('notes', SEED_PREFIX)

    def upsert_course(title, payload):
        item = Course.query.filter_by(title=title).first()
        if not item:
            item = Course(title=title)
            db.session.add(item)
        item.category = payload.get('category', '')
        item.trainer_name = payload.get('trainer_name', '')
        item.status = payload.get('status', 'active')
        item.price_egp = payload.get('price_egp', 0)
        item.price_usd = payload.get('price_usd', 0)
        item.cost_egp = payload.get('cost_egp', 0)
        item.cost_usd = payload.get('cost_usd', 0)
        item.students_count = payload.get('students_count', 0)
        item.start_date = payload.get('start_date')
        item.end_date = payload.get('end_date')
        item.lms_id = payload.get('lms_id', '')
        item.notes = payload.get('notes', SEED_PREFIX)

    def upsert_forecast(month_value, payload):
        item = ForecastMonth.query.filter_by(month=month_value).first()
        if not item:
            item = ForecastMonth(month=month_value)
            db.session.add(item)
        item.revenue_egp = payload['revenue_egp']
        item.cogs_egp = payload['cogs_egp']
        item.marketing_egp = payload['marketing_egp']
        item.payroll_egp = payload['payroll_egp']
        item.rent_egp = payload['rent_egp']
        item.other_sga_egp = payload['other_sga_egp']
        item.target_courses = payload['target_courses']
        item.target_students = payload['target_students']
        item.notes = payload.get('notes', '')

    for key, value in [
        ('exchange_rate', '50'),
        ('opening_balance_egp', '15000'),
        ('company_name', 'البروفيسور - ElProfessor'),
        ('currency', 'EGP'),
        ('raw_bank_revenue_usd', '4920.18'),
        ('raw_bank_revenue_egp', '1529.39'),
        ('raw_bank_expenses_usd', '4121.94'),
        ('raw_bank_expenses_egp', '0'),
    ]:
        upsert_setting(key, value)

    for legacy in Revenue.query.filter_by(description='دورة الذكاء الاصطناعي للمستقبل القانوني - 6 طلاب').all():
        db.session.delete(legacy)

    upsert_seed_revenue('دورة الذكاء الاصطناعي للقانونيين - الدفعة الأولى (6 طلاب)', {
        'date': datetime.date(2026, 5, 1),
        'source': 'course',
        'amount_egp': 14500,
        'client_name': 'مجموعة طلاب',
        'payment_method': 'bank_transfer',
        'notes': f'{SEED_PREFIX}:course-launch',
    })
    upsert_seed_revenue('تدريب واستشارات قانونية تقنية', {
        'date': datetime.date(2026, 5, 4),
        'source': 'consulting',
        'amount_usd': 500,
        'client_name': 'استشارات مؤسس',
        'payment_method': 'wise',
        'notes': f'{SEED_PREFIX}:consulting',
    })

    sync_seed_expenses([
        {'seed_key': 'legal_setup', 'date': datetime.date(2024, 4, 22), 'category': 'legal', 'description': 'رسوم فتح بيانات بنكية وتأسيس أولي', 'amount_gbp': 45, 'amount_usd': 45 * 1.25, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'domain_hosting', 'date': datetime.date(2026, 1, 10), 'category': 'hosting', 'description': 'استضافة ودومين وبنية تشغيل سنوية', 'amount_usd': 400, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'company_setup', 'date': datetime.date(2026, 1, 12), 'category': 'legal', 'description': 'إجراءات تأسيس الشركة والخدمات القانونية', 'amount_usd': 250, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'travel_flight', 'date': datetime.date(2025, 1, 9), 'category': 'travel', 'description': 'رحلة عمل ومؤتمر - Flydubai', 'amount_egp': 623.15 * 13.6, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'travel_car_rental', 'date': datetime.date(2025, 1, 15), 'category': 'travel', 'description': 'إيجار سيارة أثناء رحلة العمل - دبي', 'amount_egp': 50 * 13.6, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'ai_chatgpt', 'date': datetime.date(2025, 2, 10), 'category': 'tools', 'description': 'ChatGPT / OpenAI اشتراك عمل', 'amount_usd': 20, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'design_freepik', 'date': datetime.date(2025, 2, 13), 'category': 'tools', 'description': 'Freepik Essential مواد تصميم', 'amount_egp': 6.84 * 55, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'ai_consensus', 'date': datetime.date(2025, 3, 6), 'category': 'tools', 'description': 'Consensus AI للبحث والمحتوى', 'amount_usd': 7.19, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'office_setup', 'date': datetime.date(2026, 2, 1), 'category': 'office', 'description': 'إيجار وتجهيزات مساحة عمل', 'amount_usd': 370, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'software_stack', 'date': datetime.date(2026, 2, 18), 'category': 'tools', 'description': 'FluentCRM + THRIVE وأدوات تشغيل', 'amount_usd': 474, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'asset_rent_prelaunch', 'date': datetime.date(2026, 4, 15), 'category': 'asset_rent', 'description': 'استخدام أصول المؤسس خلال مرحلة التأسيس حتى نهاية أبريل', 'amount_egp': 18000, 'paid_by': 'الشركة'},
        {'seed_key': 'ai_openai_api', 'date': datetime.date(2026, 4, 30), 'category': 'tools', 'description': 'OpenAI API usage', 'amount_usd': 6, 'paid_by': 'عبدالرحمن'},
        {'seed_key': 'course_room_may', 'date': datetime.date(2026, 5, 1), 'category': 'course_delivery', 'description': 'إيجار القاعة - دورة الذكاء الاصطناعي للقانونيين', 'amount_egp': 1800, 'paid_by': 'الشركة'},
        {'seed_key': 'asset_rent_may', 'date': datetime.date(2026, 5, 5), 'category': 'asset_rent', 'description': 'إيجار أصول مؤسس - مايو 2026', 'amount_egp': 3500, 'paid_by': 'الشركة'},
        {'seed_key': 'internet_may', 'date': datetime.date(2026, 5, 3), 'category': 'office', 'description': 'WE Internet - تشغيل مايو', 'amount_egp': 120, 'paid_by': 'عبدالرحمن'},
    ])

    for row in [
        ('MACBook Pro M3', 'computers', 2400, 2200, 'أصل ثابت - إيجار مرجعي عند الاستخدام الشهري الكامل'),
        ('Mac mini M4', 'computers', 600, 700, 'أصل ثابت - تشغيل دائم'),
        ('Workstation desktop', 'computers', 250, 250, 'استخدام عند الإنتاج المكتبي'),
        ('Screen', 'computers', 55, 150, 'شاشة مساعدة للإنتاج'),
        ('iPhone 16 Pro Max', 'phones', 1199, 900, 'أصل تصوير واتصالات'),
        ('Canon camera D600', 'camera', 400, 400, 'كاميرا تصوير ثابتة'),
        ('Ricoh Theta X', 'camera', 900, 650, 'كاميرا 360 عند الحاجة'),
        ('DJI Osmo Pocket 3', 'camera', 519, 350, 'كاميرا محتوى متحرك'),
        ('DJI Mic Mini', 'microphone', 59, 100, 'مايك متنقل'),
        ('Canon lenses bundle', 'lenses', 100, 120, 'عدسات حسب الاستخدام'),
        ('Microphones and podcast audio bundle', 'microphone', 610, 450, 'عدة صوت وبودكاست'),
        ('Tripods and stands bundle', 'tripod', 392, 250, 'حوامل واستوديو'),
        ('Teleprompter and studio support', 'teleprompter', 70, 100, 'معدات تقديم'),
        ('Lighting kit', 'lighting', 374, 250, 'إضاءة تصوير'),
        ('Cables, chargers, tablet and office bundle', 'hardware', 353, 180, 'ملحقات تشغيل'),
    ]:
        upsert_asset(*row)

    if CashTransaction.query.count() == 0:
        db.session.add(CashTransaction(
            date=datetime.date(2026, 5, 5),
            kind='capital_in',
            source='Founders cash reserve',
            description='رصيد Cash Flow حالي - رأس مال تشغيل وليس إيراد',
            amount_usd=1500,
            notes=f'{SEED_PREFIX}:cash-balance'
        ))

    for row in [
        ('عبدالرحمن', 'founder', 70.8, 70.8, 4500, 'من Cap Table: مساهمة نقدية/أصول، وليست كلها Cash Flow'),
        ('منى مصطفى', 'cofounder', 10.8, 10.8, 7500, 'من Cap Table'),
        ('الشيخ سمير', 'cofounder', 5.5, 5.5, 2000, 'من Cap Table'),
        ('أبو ضيف', 'cofounder', 6.1, 6.1, 1000, 'من Cap Table'),
        ('Unallocated / Option Pool', 'pool', 6.8, 6.8, 0, 'النسبة المتبقية غير موزعة'),
    ]:
        upsert_partner(*row)

    upsert_course('دورة الذكاء الاصطناعي للقانونيين', {
        'category': 'Legal AI',
        'trainer_name': 'د. عبد الرحمن',
        'status': 'completed',
        'price_egp': 2500,
        'students_count': 6,
        'start_date': datetime.date(2026, 5, 1),
        'end_date': datetime.date(2026, 5, 7),
        'lms_id': 'demo-ai-lawyers-01',
        'notes': f'{SEED_PREFIX}:demo-course',
    })

    for legacy in Payout.query.filter_by(name='Trainer / Affiliate Pool').all():
        db.session.delete(legacy)

    upsert_payout('محمد عبد المقصود', 'دورة الذكاء الاصطناعي للقانونيين', {
        'date': datetime.date(2026, 5, 5),
        'role': 'supervisor',
        'basis_amount_egp': 14500,
        'amount_egp': 2000,
        'status': 'accrued',
        'notes': f'{SEED_PREFIX}:training-supervisor',
    })

    upsert_payout('د. جمال معاطي', 'دورة الذكاء الاصطناعي للقانونيين', {
        'date': datetime.date(2026, 5, 1),
        'role': 'affiliate',
        'basis_amount_egp': 14500,
        'amount_egp': 200,
        'status': 'accrued',
        'notes': f'{SEED_PREFIX}:affiliate-course',
    })

    upsert_payout('د. عبد الرحمن', 'دورة الذكاء الاصطناعي للقانونيين', {
        'date': datetime.date(2026, 5, 5),
        'role': 'trainer',
        'basis_amount_egp': 10500,
        'percent': 60,
        'amount_egp': 6300,
        'status': 'accrued',
        'notes': f'{SEED_PREFIX}:trainer-share',
    })

    start = datetime.date(2026, 6, 1)
    forecast = [
        (40000, 9000, 25000, 9000, 3500, 12000, 2, 18),
        (65000, 14000, 35000, 12000, 3500, 14000, 3, 28),
        (95000, 19000, 45000, 14000, 3500, 16000, 4, 42),
        (135000, 27000, 55000, 16000, 3500, 18000, 5, 60),
        (180000, 36000, 65000, 18000, 3500, 20000, 6, 78),
        (240000, 48000, 80000, 22000, 3500, 24000, 8, 105),
    ]
    for idx, row in enumerate(forecast):
        month_value = month_add(start, idx).strftime('%Y-%m')
        rev, cogs, marketing, payroll, rent, other, courses, students = row
        upsert_forecast(month_value, {
            'revenue_egp': rev,
            'cogs_egp': cogs,
            'marketing_egp': marketing,
            'payroll_egp': payroll,
            'rent_egp': rent,
            'other_sga_egp': other,
            'target_courses': courses,
            'target_students': students,
            'notes': SEED_PREFIX,
        })
    
    db.session.commit()
    print("✅ Database seeded successfully")

# ============================================================
# INIT
# ============================================================

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.0.0'})

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    root_dir = os.path.dirname(__file__)
    for static_dir in (
        os.path.join(root_dir, '..', 'frontend', 'dist'),
        os.path.join(root_dir, 'static'),
        os.path.join(root_dir, 'dist'),
    ):
        requested = os.path.join(static_dir, path)
        if path and os.path.exists(requested) and not os.path.isdir(requested):
            return send_from_directory(static_dir, path)
        index_path = os.path.join(static_dir, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_dir, 'index.html')
    return jsonify({'status': 'ok', 'message': 'ElProfessor Dashboard API is running'})

with app.app_context():
    db.create_all()
    seed()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
