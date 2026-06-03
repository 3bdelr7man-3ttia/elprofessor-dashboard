"""
ElProfessor Management Dashboard - Backend API
Flask + SQLAlchemy + SQLite (upgradeable to MySQL/PostgreSQL)
"""
import os, json, datetime, hashlib, secrets, functools
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
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
    dashboard_role = db.Column(db.String(50), default='admin')
    linked_to_name = db.Column(db.String(255))
    preferred_currency = db.Column(db.String(10), default='AUTO')
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
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
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
    lms_id = db.Column(db.String(50))   # = Tutor course id (tutor_id) for synced courses
    lms_instructor_email = db.Column(db.String(255))  # academy course instructor — trainer link by email
    lms_synced = db.Column(db.Boolean, default=False)  # True = mirrored from the academy (WordPress/Tutor)
    open_for_investment = db.Column(db.Boolean, default=False)  # admin opened it → shows in investor marketplace
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    revenues = db.relationship('Revenue', backref='course', lazy=True)

class RevenueSplit(db.Model):
    __tablename__ = 'revenue_splits'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), unique=True, nullable=False)
    trainer_percent = db.Column(db.Float, default=35)
    platform_percent = db.Column(db.Float, default=30)
    investor_percent = db.Column(db.Float, default=25)
    affiliate_percent = db.Column(db.Float, default=10)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Investment(db.Model):
    __tablename__ = 'investments'
    id = db.Column(db.Integer, primary_key=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey('investment_opportunities.id'), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    investor_name = db.Column(db.String(255), nullable=False)
    investor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    amount_egp = db.Column(db.Float, default=0)
    amount_usd = db.Column(db.Float, default=0)
    profit_percent = db.Column(db.Float, default=20)
    share_pct = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='accrued')
    actual_return = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class InvestmentOpportunity(db.Model):
    __tablename__ = 'investment_opportunities'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    target_amount = db.Column(db.Float, nullable=False, default=0)
    min_investment = db.Column(db.Float, default=200)
    current_funded = db.Column(db.Float, default=0)
    expected_roi = db.Column(db.Float, default=0)
    expected_start = db.Column(db.Date)
    expected_end = db.Column(db.Date)
    trainer_pct = db.Column(db.Float, default=35)
    platform_pct = db.Column(db.Float, default=35)
    investors_pct = db.Column(db.Float, default=30)
    affiliate_pct = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='open')  # open, hot, invite_only, funded, closed
    video_url = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class InvestorWallet(db.Model):
    __tablename__ = 'investor_wallets'
    id = db.Column(db.Integer, primary_key=True)
    investor_name = db.Column(db.String(255), unique=True, nullable=False)
    investor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    balance = db.Column(db.Float, default=0)
    total_invested = db.Column(db.Float, default=0)
    total_returns = db.Column(db.Float, default=0)
    level = db.Column(db.String(50), default='bronze')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class WithdrawalRequest(db.Model):
    __tablename__ = 'withdrawal_requests'
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('investor_wallets.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(50), default='pending')  # pending, approved, rejected, completed
    requested_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

class InvestorBadge(db.Model):
    __tablename__ = 'investor_badges'
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('investor_wallets.id'), nullable=False)
    badge_type = db.Column(db.String(100), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

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

def roles_required(*allowed_roles):
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if not getattr(g, 'user', None):
                return jsonify({'error': 'Unauthorized'}), 401
            if g.user.role not in allowed_roles:
                return jsonify({'error': 'Forbidden'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

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

def user_dashboard_role(user):
    return (getattr(user, 'dashboard_role', None) or getattr(user, 'role', None) or 'viewer').strip()

def user_linked_name(user):
    return (getattr(user, 'linked_to_name', None) or getattr(user, 'name', None) or '').strip()

def badge_catalog():
    return {
        'first_investment': {'label': 'أول استثمار', 'icon': 'star'},
        'three_courses': {'label': '٣ دورات', 'icon': 'check'},
        'roi_50': {'label': 'عائد +50%', 'icon': 'trend'},
        'platinum': {'label': 'مستثمر بلاتيني', 'icon': 'crown'},
        'ten_courses': {'label': '١٠ دورات', 'icon': 'spark'},
    }

def normalize_name(value):
    raw = (value or '').strip().lower()
    for token in ('د.', 'د ', 'dr.', 'dr ', 'mr.', 'mr ', 'أ.', 'استاذ', 'الأستاذ'):
        raw = raw.replace(token, '')
    return ' '.join(raw.split())

def names_match(left, right):
    a = normalize_name(left)
    b = normalize_name(right)
    if not a or not b:
        return False
    return a == b or a in b or b in a

def investor_display_name(user=None, explicit_name=''):
    if explicit_name:
        return explicit_name.strip()
    return user_linked_name(user) if user else ''

def sync_opportunity_funding(opportunity):
    if not opportunity:
        return 0
    related = Investment.query.filter_by(opportunity_id=opportunity.id).all()
    funded = sum((item.amount_usd or 0) for item in related)
    opportunity.current_funded = funded
    if opportunity.status not in ('closed', 'invite_only'):
        opportunity.status = 'funded' if opportunity.target_amount and funded >= (opportunity.target_amount or 0) else opportunity.status
    return funded

def determine_wallet_level(total_invested_usd, avg_roi):
    if total_invested_usd >= 10000 or avg_roi >= 70:
        return 'platinum'
    if total_invested_usd >= 5000 or avg_roi >= 40:
        return 'gold'
    if total_invested_usd >= 2000 or avg_roi >= 20:
        return 'silver'
    return 'bronze'

def get_or_create_wallet(investor_name, investor_user_id=None):
    wallet = InvestorWallet.query.filter_by(investor_name=investor_name).first()
    if not wallet:
        wallet = InvestorWallet(investor_name=investor_name, investor_user_id=investor_user_id)
        db.session.add(wallet)
        db.session.flush()
    if investor_user_id and not wallet.investor_user_id:
        wallet.investor_user_id = investor_user_id
    return wallet

def award_wallet_badges(wallet, investments, avg_roi):
    earned = {item.badge_type for item in InvestorBadge.query.filter_by(wallet_id=wallet.id).all()}
    unique_courses = len({(item.opportunity_id or item.course_id) for item in investments if item.opportunity_id or item.course_id})
    badge_rules = []
    if len(investments) >= 1:
        badge_rules.append('first_investment')
    if unique_courses >= 3:
        badge_rules.append('three_courses')
    if avg_roi >= 50:
        badge_rules.append('roi_50')
    if wallet.level == 'platinum':
        badge_rules.append('platinum')
    if unique_courses >= 10:
        badge_rules.append('ten_courses')
    for badge_type in badge_rules:
        if badge_type not in earned:
            db.session.add(InvestorBadge(wallet_id=wallet.id, badge_type=badge_type))

def sync_wallet(wallet):
    items = Investment.query.filter_by(investor_name=wallet.investor_name).all()
    total_invested = sum((item.amount_usd or 0) for item in items)
    completed_returns = sum((item.actual_return or 0) for item in items if item.status in ('completed', 'loss', 'paid'))
    pending_withdrawals = sum((item.amount or 0) for item in WithdrawalRequest.query.filter_by(wallet_id=wallet.id, status='pending').all())
    completed_withdrawals = sum((item.amount or 0) for item in WithdrawalRequest.query.filter(WithdrawalRequest.wallet_id == wallet.id, WithdrawalRequest.status.in_(['approved', 'completed'])).all())
    avg_roi = 0
    completed_items = [item for item in items if item.status in ('completed', 'loss', 'paid') and (item.amount_usd or 0)]
    if completed_items:
        avg_roi = sum((((item.actual_return or 0) - (item.amount_usd or 0)) / (item.amount_usd or 1)) * 100 for item in completed_items) / len(completed_items)
    wallet.total_invested = round(total_invested, 2)
    wallet.total_returns = round(completed_returns, 2)
    wallet.balance = round(max(0, completed_returns - completed_withdrawals - pending_withdrawals), 2)
    wallet.level = determine_wallet_level(wallet.total_invested, avg_roi)
    award_wallet_badges(wallet, items, avg_roi)
    return {
        'wallet': wallet,
        'items': items,
        'avg_roi': round(avg_roi, 1),
        'pending_withdrawals': round(pending_withdrawals, 2),
        'completed_withdrawals': round(completed_withdrawals, 2),
    }

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

def get_course_split(course_id):
    split = RevenueSplit.query.filter_by(course_id=course_id).first()
    if split:
        return split
    split = RevenueSplit(course_id=course_id, trainer_percent=35, platform_percent=30, investor_percent=25, affiliate_percent=10)
    db.session.add(split)
    db.session.flush()
    return split

def serialize_split(split):
    total_percent = round((split.trainer_percent or 0) + (split.platform_percent or 0) + (split.investor_percent or 0) + (split.affiliate_percent or 0), 2)
    return {
        'id': split.id,
        'course_id': split.course_id,
        'trainer_percent': split.trainer_percent or 0,
        'platform_percent': split.platform_percent or 0,
        'investor_percent': split.investor_percent or 0,
        'affiliate_percent': split.affiliate_percent or 0,
        'total_percent': total_percent,
        'valid': abs(total_percent - 100) < 0.001,
        'notes': split.notes or '',
    }

def serialize_opportunity(item, rate, course_lookup=None):
    course = course_lookup.get(item.course_id) if course_lookup else Course.query.get(item.course_id)
    funded = sync_opportunity_funding(item)
    target = item.target_amount or 0
    remaining = max(0, target - funded)
    funding_percent = round((funded / target) * 100, 1) if target else 0
    expected_return_value = 0
    if course:
        financial = course_financials(course, rate)
        expected_return_value = round(financial['distribution'].get('investor_pool_egp', 0) / rate) if rate else 0
    if not expected_return_value and item.target_amount and item.expected_roi:
        expected_return_value = round((item.target_amount or 0) * (1 + ((item.expected_roi or 0) / 100)), 2)
    return {
        'id': item.id,
        'course_id': item.course_id,
        'course_title': course.title if course else 'دورة غير مرتبطة',
        'trainer_name': course.trainer_name if course else '',
        'programs_count': 1,
        'students_count': course.students_count if course else 0,
        'target_amount': round(target, 2),
        'min_investment': round(item.min_investment or 0, 2),
        'current_funded': round(funded, 2),
        'remaining_amount': round(remaining, 2),
        'funding_percent': funding_percent,
        'expected_roi': round(item.expected_roi or 0, 1),
        'expected_return_value': round(expected_return_value, 2),
        'expected_start': serialize_date(item.expected_start),
        'expected_end': serialize_date(item.expected_end),
        'trainer_pct': item.trainer_pct or 0,
        'platform_pct': item.platform_pct or 0,
        'investors_pct': item.investors_pct or 0,
        'affiliate_pct': item.affiliate_pct or 0,
        'status': item.status,
        'video_url': item.video_url or '',
        'notes': item.notes or '',
        'created_at': item.created_at.isoformat() if item.created_at else None,
    }

def serialize_investment(item, rate, course_lookup=None, opportunity_lookup=None):
    invested_egp = to_egp(item.amount_usd, item.amount_egp, rate)
    course = course_lookup.get(item.course_id) if course_lookup else Course.query.get(item.course_id)
    opportunity = opportunity_lookup.get(item.opportunity_id) if opportunity_lookup and item.opportunity_id else (InvestmentOpportunity.query.get(item.opportunity_id) if item.opportunity_id else None)
    payout = 0
    roi = 0
    course_profit = 0
    if course:
        financial = course_financials(course, rate)
        course_profit = financial['distribution']['net_distributable_profit']
        if item.actual_return:
            payout = round(item.actual_return * rate)
        elif opportunity and opportunity.current_funded:
            funded_egp = (opportunity.current_funded or 0) * rate
            investor_pool = financial['distribution'].get('investor_pool_egp', 0)
            payout = round(investor_pool * (invested_egp / funded_egp)) if funded_egp else 0
        else:
            payout = round(course_profit * ((item.profit_percent or 0) / 100))
        roi = round(((payout - invested_egp) / invested_egp) * 100, 1) if invested_egp else 0
    return {
        'id': item.id,
        'opportunity_id': item.opportunity_id,
        'course_id': item.course_id,
        'course_title': course.title if course else '',
        'investor_name': item.investor_name,
        'investor_user_id': item.investor_user_id,
        'amount_egp': item.amount_egp,
        'amount_usd': item.amount_usd,
        'invested_total_egp': round(invested_egp),
        'profit_percent': item.profit_percent or 0,
        'share_pct': round(item.share_pct or 0, 2),
        'status': item.status,
        'notes': item.notes or '',
        'created_at': item.created_at.isoformat() if item.created_at else None,
        'course_profit_egp': round(course_profit),
        'due_egp': round(payout),
        'roi_percent': roi,
        'actual_return': round(item.actual_return or 0, 2),
        'opportunity': serialize_opportunity(opportunity, rate, course_lookup) if opportunity else None,
    }

def serialize_wallet(wallet, rate, avg_roi=0, pending_withdrawals=0):
    return {
        'id': wallet.id,
        'investor_name': wallet.investor_name,
        'investor_user_id': wallet.investor_user_id,
        'balance': round(wallet.balance or 0, 2),
        'balance_egp': round((wallet.balance or 0) * rate, 2),
        'total_invested': round(wallet.total_invested or 0, 2),
        'total_invested_egp': round((wallet.total_invested or 0) * rate, 2),
        'total_returns': round(wallet.total_returns or 0, 2),
        'total_returns_egp': round((wallet.total_returns or 0) * rate, 2),
        'avg_roi': round(avg_roi or 0, 1),
        'level': wallet.level or 'bronze',
        'pending_withdrawals': round(pending_withdrawals or 0, 2),
        'created_at': wallet.created_at.isoformat() if wallet.created_at else None,
    }

def serialize_badges(wallet):
    catalog = badge_catalog()
    earned = {item.badge_type: item for item in InvestorBadge.query.filter_by(wallet_id=wallet.id).all()}
    payload = []
    for badge_type, info in catalog.items():
        item = earned.get(badge_type)
        payload.append({
            'badge_type': badge_type,
            'label': info['label'],
            'icon': info['icon'],
            'earned': bool(item),
            'earned_at': item.earned_at.isoformat() if item and item.earned_at else None,
        })
    return payload

def simulate_distribution(payload, rate):
    students = float(payload.get('students_count') or 0)
    price_per_student = float(payload.get('price_per_student') or 0)
    projected_revenue = float(payload.get('revenue_egp') or 0) or students * price_per_student
    execution_cost = float(payload.get('execution_cost_egp') or payload.get('room_cost_egp') or 0)
    supervision_cost = float(payload.get('supervision_cost_egp') or 0)
    ads_cost = float(payload.get('total_ads_budget_egp') or payload.get('ads_cost_egp') or 0)
    investor_contribution = float(payload.get('investor_contribution_egp') or ads_cost or 0)
    affiliate_mode = (payload.get('affiliate_mode') or 'percent').strip()
    affiliate_fixed = float(payload.get('affiliate_fixed_egp') or 0)
    direct_costs = execution_cost + supervision_cost + ads_cost
    net_profit = max(0, projected_revenue - direct_costs)
    trainer_percent = float(payload.get('trainer_percent') or 0)
    platform_percent = float(payload.get('platform_percent') or 0)
    investor_percent = float(payload.get('investor_percent') or 0)
    affiliate_percent = float(payload.get('affiliate_percent') or 0)
    warnings = []
    if ads_cost < 0 or investor_contribution < 0:
        warnings.append('قيم الإعلان والمساهمة يجب أن تكون موجبة')
    if ads_cost and investor_contribution > ads_cost:
        warnings.append('مساهمة المستثمر أكبر من ميزانية الإعلان الكلية')
    if affiliate_mode == 'fixed':
        total_percent = trainer_percent + platform_percent + investor_percent
        affiliate_allocation = min(net_profit, max(0, affiliate_fixed))
        distributable_base = max(0, net_profit - affiliate_allocation)
        allocations = {
            'trainer': round(distributable_base * trainer_percent / 100),
            'platform': round(distributable_base * platform_percent / 100),
            'investor': round(distributable_base * investor_percent / 100),
            'affiliate': round(affiliate_allocation),
        }
        if affiliate_fixed > net_profit:
            warnings.append('مبلغ الأفلييت أكبر من صافي الربح المتوقع، فتم تقييده بصافي الربح')
    else:
        total_percent = trainer_percent + platform_percent + investor_percent + affiliate_percent
        distributable_base = net_profit
        allocations = {
            'trainer': round(distributable_base * trainer_percent / 100),
            'platform': round(distributable_base * platform_percent / 100),
            'investor': round(distributable_base * investor_percent / 100),
            'affiliate': round(distributable_base * affiliate_percent / 100),
        }
    contribution_share = (investor_contribution / ads_cost) if ads_cost else (1 if investor_contribution > 0 else 0)
    effective_contribution_share = max(0, min(1, contribution_share))
    investor_due = round((allocations['investor'] or 0) * effective_contribution_share)
    roi_percent = round(((investor_due - investor_contribution) / investor_contribution) * 100, 1) if investor_contribution else 0
    valid_total = abs(total_percent - 100) < 0.001
    if not valid_total:
        warnings.append('مجموع نسب التوزيع يجب أن يساوي 100%')
    return {
        'inputs': {
            'projected_revenue_egp': round(projected_revenue),
            'students_count': round(students),
            'price_per_student': round(price_per_student),
            'execution_cost_egp': round(execution_cost),
            'supervision_cost_egp': round(supervision_cost),
            'total_ads_budget_egp': round(ads_cost),
            'investor_contribution_egp': round(investor_contribution),
            'direct_costs_egp': round(direct_costs),
        },
        'distribution': {
            'affiliate_mode': affiliate_mode,
            'trainer_percent': trainer_percent,
            'platform_percent': platform_percent,
            'investor_percent': investor_percent,
            'affiliate_percent': affiliate_percent,
            'affiliate_fixed_egp': round(affiliate_fixed),
            'total_percent': round(total_percent, 2),
            'valid': valid_total,
            'net_distributable_profit': round(net_profit),
            'post_affiliate_pool_egp': round(distributable_base),
            'allocations_egp': allocations,
            'investor_pool_egp': round(allocations['investor']),
            'investor_due_egp': investor_due,
            'investor_share_of_budget_percent': round(effective_contribution_share * 100, 1),
            'investor_roi_percent': roi_percent,
            'warning': ' | '.join(warnings),
        },
    }

def course_financials(course, rate):
    course_revenues = revenues_for_course(course)
    course_expenses = expenses_for_course(course)
    payouts = Payout.query.filter(Payout.status != 'waived').all()
    investments = Investment.query.filter_by(course_id=course.id).all()
    total_revenue = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in course_revenues)
    linked_payouts = [
        p for p in payouts
        if (p.related_to or '').strip() == (course.title or '').strip()
    ]
    linked_expense_cost = sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in course_expenses)
    linked_payout_cost = sum(payout_amount(p, rate) for p in linked_payouts)
    direct_payout_cost = sum(payout_amount(p, rate) for p in linked_payouts if p.role in ('supervisor',))
    linked_investment_cost = sum(to_egp(i.amount_usd, i.amount_egp, rate) for i in investments)
    direct_costs = linked_expense_cost + direct_payout_cost + linked_investment_cost
    split = get_course_split(course.id)
    distribution = simulate_distribution({
        'revenue_egp': total_revenue,
        'room_cost_egp': linked_expense_cost,
        'supervision_cost_egp': direct_payout_cost,
        'ads_cost_egp': linked_investment_cost,
        'trainer_percent': split.trainer_percent,
        'platform_percent': split.platform_percent,
        'investor_percent': split.investor_percent,
        'affiliate_percent': split.affiliate_percent,
    }, rate)['distribution']
    return {
        'total_revenue': round(total_revenue),
        'linked_expense_cost': round(linked_expense_cost),
        'linked_payout_cost': round(linked_payout_cost),
        'linked_investment_cost': round(linked_investment_cost),
        'total_cost': round(to_egp(course.cost_usd, course.cost_egp, rate) + linked_expense_cost + linked_payout_cost),
        'profit': round(total_revenue - (to_egp(course.cost_usd, course.cost_egp, rate) + linked_expense_cost + linked_payout_cost)),
        'direct_costs': round(direct_costs),
        'distribution': distribution,
        'split': serialize_split(split),
        'investments': investments,
        'linked_payouts_models': linked_payouts,
        'course_expenses_models': course_expenses,
    }

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
    dashboard_role = user_dashboard_role(user)
    return jsonify({'token': token, 'user': {'id': user.id, 'email': user.email, 'name': user.name, 'role': dashboard_role, 'dashboard_role': dashboard_role, 'linked_to_name': user_linked_name(user), 'preferred_currency': (user.preferred_currency or 'AUTO')}})

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json or {}
    email = (data.get('email') or '').lower().strip()
    password = data.get('password') or ''
    name = (data.get('name') or '').strip()
    if not email or not password or not name:
        return jsonify({'error': 'الاسم والبريد وكلمة المرور مطلوبة'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'هذا البريد مسجل بالفعل'}), 409
    user = User(
        email=email,
        password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
        name=name,
        role='viewer',
        dashboard_role='viewer',
        linked_to_name='',
        preferred_currency='AUTO',
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'تم إنشاء الحساب. يمكن للإدارة الآن ضبط دورك داخل الداشبورد.'}), 201

@app.route('/api/auth/me', methods=['GET'])
@token_required
def me():
    dashboard_role = user_dashboard_role(g.user)
    return jsonify({'id': g.user.id, 'email': g.user.email, 'name': g.user.name, 'role': dashboard_role, 'dashboard_role': dashboard_role, 'linked_to_name': user_linked_name(g.user), 'preferred_currency': (g.user.preferred_currency or 'AUTO')})

# --- Single sign-on FROM the main platform (one identity reaches the BI brain) ---
PLATFORM_API_URL = os.environ.get('PLATFORM_API_URL', 'https://api.elprofessor.net').rstrip('/')
PLATFORM_SSO_AUD = 'elprofessor-dashboard'
# Platform system role -> this dashboard's role.
_PLATFORM_ROLE_MAP = {'admin': 'admin', 'staff': 'admin', 'investor': 'investor'}

@app.route('/api/auth/sso', methods=['POST'])
def sso_login():
    data = request.json or {}
    token = (data.get('sso') or data.get('token') or '').strip()
    if not token:
        return jsonify({'error': 'رمز الدخول مفقود'}), 400

    # Verify the signed token server-to-server against the platform (same pattern
    # as the WordPress academy bridge) — no shared secret needed on this side.
    try:
        resp = requests.post(f"{PLATFORM_API_URL}/api/lms/sso/verify", json={'token': token}, timeout=12)
    except Exception:
        return jsonify({'error': 'تعذر التحقق من تسجيل الدخول'}), 502
    if resp.status_code != 200:
        return jsonify({'error': 'رمز الدخول غير صالح أو منتهي'}), 401
    body = resp.json() if resp.content else {}
    if body.get('aud') != PLATFORM_SSO_AUD:
        return jsonify({'error': 'هذا الرمز ليس مخصصًا لهذه اللوحة'}), 401

    platform_user = body.get('user') or {}
    email = (platform_user.get('email') or '').lower().strip()
    if not email:
        return jsonify({'error': 'هوية الدخول غير صالحة'}), 401
    platform_role = (platform_user.get('role') or '').strip().lower()
    mapped_role = _PLATFORM_ROLE_MAP.get(platform_role, 'viewer')

    user = User.query.filter_by(email=email).first()
    if not user:
        # First arrival via SSO: create a passwordless account (login is via the platform).
        user = User(
            email=email,
            password_hash=generate_password_hash(secrets.token_hex(32), method='pbkdf2:sha256'),
            name=(platform_user.get('full_name') or email),
            role=mapped_role,
            dashboard_role=mapped_role,
            linked_to_name='',
            preferred_currency='AUTO',
            is_active=True,
        )
        db.session.add(user)
    else:
        # Don't override an explicit dashboard role the admin set here; only fill gaps.
        if not (getattr(user, 'dashboard_role', None) or '').strip():
            user.dashboard_role = mapped_role
        if not user.is_active:
            user.is_active = True
    db.session.commit()

    token_out = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    role_out = user_dashboard_role(user)
    return jsonify({'token': token_out, 'user': {'id': user.id, 'email': user.email, 'name': user.name, 'role': role_out, 'dashboard_role': role_out, 'linked_to_name': user_linked_name(user), 'preferred_currency': (user.preferred_currency or 'AUTO')}})

# --- Pull live platform numbers (the "ربط = مزامنة" data sync) ---
# (PLATFORM_API_URL is defined above with the SSO consumer.)
PLATFORM_METRICS_SECRET = os.environ.get('METRICS_SECRET', '').strip()

@app.route('/api/platform-metrics', methods=['GET'])
@token_required
@roles_required('admin')
def platform_metrics():
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط مزامنة المنصة بعد'}), 503
    try:
        r = requests.get(
            f"{PLATFORM_API_URL}/api/admin/metrics",
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=12,
        )
    except Exception:
        return jsonify({'error': 'تعذر الاتصال بالمنصة'}), 502
    if r.status_code != 200:
        return jsonify({'error': 'تعذر جلب أرقام المنصة'}), 502
    return jsonify(r.json() if r.content else {})

# --- The real website users (from the platform) + role control, surfaced here ---
@app.route('/api/platform-users', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee = read-only follow-up, no mutations below
def platform_users_list():
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط الربط بعد'}), 503
    try:
        r = requests.get(
            f"{PLATFORM_API_URL}/api/bridge/users",
            params={'search': (request.args.get('search') or '')[:80], 'limit': 500},
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=12,
        )
    except Exception:
        return jsonify({'error': 'تعذر الاتصال بالمنصة'}), 502
    if r.status_code != 200:
        return jsonify({'error': 'تعذر جلب المستخدمين'}), 502
    return jsonify(r.json() if r.content else {})

@app.route('/api/platform-users/<user_id>/role', methods=['POST'])
@token_required
@roles_required('admin')
def platform_users_set_role(user_id):
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط الربط بعد'}), 503
    role = ((request.json or {}).get('role') or '').strip()
    try:
        r = requests.post(
            f"{PLATFORM_API_URL}/api/bridge/users/{user_id}/role",
            json={'role': role},
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=12,
        )
    except Exception:
        return jsonify({'error': 'تعذر الاتصال بالمنصة'}), 502
    if r.status_code != 200:
        body = r.json() if r.content else {}
        return jsonify({'error': body.get('detail') or 'تعذر تغيير الدور'}), r.status_code
    return jsonify(r.json() if r.content else {})

@app.route('/api/platform-trainer-applications', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW pending applications (follow-up)
def platform_trainer_apps():
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط الربط بعد'}), 503
    try:
        r = requests.get(
            f"{PLATFORM_API_URL}/api/bridge/trainer-applications",
            params={'status': request.args.get('status') or 'all'},
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=12,
        )
    except Exception:
        return jsonify({'error': 'تعذر الاتصال بالمنصة'}), 502
    if r.status_code != 200:
        return jsonify({'error': 'تعذر جلب الطلبات'}), 502
    return jsonify(r.json() if r.content else {})


def _platform_proxy(method, path, params=None, json_body=None):
    """Proxy an admin action to the main platform via the shared service secret.
    Same pattern as platform_metrics/platform_users above, factored out because the
    approval endpoints below all need it. Returns a Flask (json, status) response."""
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط الربط بعد'}), 503
    try:
        r = requests.request(
            method,
            f"{PLATFORM_API_URL}{path}",
            params=params,
            json=json_body,
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=12,
        )
    except Exception:
        return jsonify({'error': 'تعذر الاتصال بالمنصة'}), 502
    if r.status_code != 200:
        body = r.json() if r.content else {}
        return jsonify({'error': body.get('detail') or 'تعذر تنفيذ العملية'}), r.status_code
    return jsonify(r.json() if r.content else {})


@app.route('/api/platform-trainer-applications/<application_id>/<action>', methods=['POST'])
@token_required
@roles_required('admin')
def platform_trainer_decide(application_id, action):
    if action not in ('approve', 'reject'):
        return jsonify({'error': 'إجراء غير معروف'}), 400
    body = request.json or {}
    return _platform_proxy(
        'POST',
        f"/api/bridge/trainer-applications/{application_id}/{action}",
        json_body={'admin_note': body.get('admin_note') or ''},
    )


@app.route('/api/platform-program-requests', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW pending program requests (follow-up)
def platform_program_requests():
    return _platform_proxy(
        'GET',
        '/api/bridge/program-requests',
        params={'status': request.args.get('status') or 'all'},
    )


@app.route('/api/platform-program-requests/<request_id>/<action>', methods=['POST'])
@token_required
@roles_required('admin')
def platform_program_decide(request_id, action):
    if action not in ('approve', 'reject'):
        return jsonify({'error': 'إجراء غير معروف'}), 400
    body = request.json or {}
    return _platform_proxy(
        'POST',
        f"/api/bridge/program-requests/{request_id}/{action}",
        json_body={
            'admin_note': body.get('admin_note') or '',
            'lms_entry_url': body.get('lms_entry_url') or '',
            'lms_course_ref': body.get('lms_course_ref') or '',
        },
    )


@app.route('/api/investor/wallet', methods=['GET'])
def investor_wallet_bridge():
    """Read-only investor wallet by email, for the platform to mirror in its
    investor portal. Secured by the same platform<->dashboard service secret."""
    secret = request.headers.get('X-ELP-Metrics-Secret', '')
    if not PLATFORM_METRICS_SECRET or not secret or not secrets.compare_digest(secret, PLATFORM_METRICS_SECRET):
        return jsonify({'error': 'unauthorized'}), 401
    email = (request.args.get('email') or '').lower().strip()
    if not email:
        return jsonify({'error': 'email required'}), 400

    user = User.query.filter_by(email=email).first()
    wallet = None
    if user:
        wallet = InvestorWallet.query.filter_by(investor_user_id=user.id).first()
        if not wallet:
            name = user_linked_name(user)
            if name:
                wallet = InvestorWallet.query.filter_by(investor_name=name).first()
    if not wallet:
        return jsonify({'exists': False, 'balance': 0, 'total_invested': 0, 'total_returns': 0, 'level': 'bronze', 'currency': 'USD'})

    sync_wallet(wallet)
    db.session.commit()
    return jsonify({
        'exists': True,
        'balance': wallet.balance or 0,
        'total_invested': wallet.total_invested or 0,
        'total_returns': wallet.total_returns or 0,
        'level': wallet.level or 'bronze',
        'currency': 'USD',
    })

@app.route('/api/users', methods=['GET'])
@token_required
@roles_required('admin')
def list_users():
    return jsonify([{
        'id': u.id, 'email': u.email, 'name': u.name, 'role': user_dashboard_role(u), 'dashboard_role': user_dashboard_role(u), 'linked_to_name': user_linked_name(u), 'preferred_currency': (u.preferred_currency or 'AUTO'),
        'is_active': u.is_active, 'created_at': u.created_at.isoformat() if u.created_at else None
    } for u in User.query.order_by(User.created_at.desc()).all()])

@app.route('/api/users', methods=['POST'])
@token_required
@roles_required('admin')
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
        role=d.get('dashboard_role') or d.get('role') or 'viewer',
        dashboard_role=d.get('dashboard_role') or d.get('role') or 'viewer',
        linked_to_name=d.get('linked_to_name') or '',
        preferred_currency=(d.get('preferred_currency') or 'AUTO').upper(),
        is_active=True
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({'id': user.id, 'message': 'تم إضافة المستخدم'}), 201

@app.route('/api/users/<int:id>', methods=['PUT'])
@token_required
@roles_required('admin')
def update_user(id):
    user = User.query.get_or_404(id)
    d = request.json or {}
    for key in ['name', 'email', 'role', 'dashboard_role', 'linked_to_name', 'preferred_currency', 'is_active']:
        if key in d:
            value = d[key]
            if key == 'email' and value:
                value = value.lower().strip()
            if key in ('role', 'dashboard_role') and not value:
                value = 'viewer'
            if key == 'preferred_currency':
                value = (value or 'AUTO').upper()
            setattr(user, key, value)
    if d.get('password'):
        user.password_hash = generate_password_hash(d['password'], method='pbkdf2:sha256')
    db.session.commit()
    return jsonify({'message': 'تم تحديث المستخدم'})

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
    course_lookup = {c.id: c for c in Course.query.all()}
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
            'course_id': c.course_id,
            'course_title': course_lookup.get(c.course_id).title if c.course_id in course_lookup else '',
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
        course_id=d.get('course_id'),
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
    for k in ['name', 'platform', 'status', 'budget', 'spent', 'currency', 'impressions', 'clicks', 'leads', 'conversions', 'revenue_attributed', 'course_id', 'target_audience', 'notes']:
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
    viewer_role = user_dashboard_role(g.user)
    linked_name = user_linked_name(g.user)
    items = Course.query.order_by(Course.created_at.desc()).all()
    if viewer_role == 'trainer':
        items = [item for item in items if names_match(item.trainer_name, linked_name) or names_match(item.trainer_name, g.user.name)]
    elif viewer_role == 'investor':
        if request.args.get('scope') == 'marketplace':
            # المستثمر يشوف بس الدورات اللي الأدمن فتحها للاستثمار.
            items = [item for item in items if item.open_for_investment]
        else:
            course_ids = {item.course_id for item in Investment.query.filter_by(investor_name=linked_name).all()}
            items = [item for item in items if item.id in course_ids]
    rate = get_rate()
    result = []
    for c in items:
        financial = course_financials(c, rate)
        linked_payouts = [
            {
                'id': p.id,
                'date': serialize_date(p.date),
                'name': p.name,
                'role': p.role,
                'related_to': p.related_to,
                'percent': p.percent,
                'total_egp': round(payout_amount(p, rate)),
            }
            for p in financial['linked_payouts_models']
        ]
        linked_expenses = [
            {
                'id': e.id,
                'date': serialize_date(e.date),
                'category': e.category,
                'description': e.description,
                'total_egp': round(to_egp(e.amount_usd, e.amount_egp, rate)),
            }
            for e in financial['course_expenses_models']
        ]
        result.append({
            'id': c.id, 'title': c.title, 'category': c.category,
            'trainer_name': c.trainer_name, 'status': c.status,
            'price_egp': c.price_egp, 'price_usd': c.price_usd,
            'cost_egp': c.cost_egp, 'cost_usd': c.cost_usd,
            'students_count': c.students_count,
            'start_date': serialize_date(c.start_date), 'end_date': serialize_date(c.end_date),
            'total_revenue': financial['total_revenue'], 'total_cost': financial['total_cost'],
            'linked_expense_cost': financial['linked_expense_cost'],
            'linked_payout_cost': financial['linked_payout_cost'],
            'linked_investment_cost': financial['linked_investment_cost'],
            'linked_expenses': linked_expenses,
            'linked_payouts': linked_payouts,
            'profit': financial['profit'],
            'revenue_split': financial['split'],
            'distribution': financial['distribution'],
            'linked_investments': [serialize_investment(item, rate, {c.id: c}) for item in financial['investments']],
            'lms_id': c.lms_id, 'notes': c.notes,
            'lms_synced': bool(c.lms_synced), 'lms_instructor_email': c.lms_instructor_email,
            'open_for_investment': bool(c.open_for_investment),
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
    for k in ['title', 'category', 'trainer_name', 'status', 'price_egp', 'price_usd', 'cost_egp', 'cost_usd', 'students_count', 'lms_id', 'notes', 'open_for_investment']:
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


# Pull the REAL courses from the academy (WordPress/Tutor, via the platform bridge) and
# upsert them into our Course table keyed by lms_id = tutor_id, tied to each course's
# instructor (by email). Manual financials (price/cost) are preserved on update.
_LMS_STATUS_MAP = {'publish': 'active', 'draft': 'draft', 'pending': 'draft', 'trash': 'archived', 'private': 'draft'}


@app.route('/api/courses/sync-lms', methods=['POST'])
@token_required
@roles_required('admin')
def sync_courses_from_lms():
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط الربط بعد'}), 503
    try:
        r = requests.get(
            f"{PLATFORM_API_URL}/api/bridge/lms-courses",
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=30,
        )
    except Exception:
        return jsonify({'error': 'تعذر الاتصال بالمنصة'}), 502
    if r.status_code != 200:
        body = r.json() if r.content else {}
        return jsonify({'error': body.get('detail') or 'تعذر جلب الدورات من الأكاديمية'}), r.status_code

    rows = (r.json() or {}).get('courses', [])
    created = 0
    updated = 0
    for row in rows:
        tutor_id = str(row.get('tutor_id') or '').strip()
        if not tutor_id:
            continue
        status = _LMS_STATUS_MAP.get(str(row.get('post_status') or '').strip().lower(), 'draft')
        instructor = (row.get('instructor_name') or '').strip()
        email = (row.get('instructor_email') or '').strip().lower()
        c = Course.query.filter_by(lms_id=tutor_id).first()
        if c is None:
            c = Course(lms_id=tutor_id, price_egp=0, price_usd=0, cost_egp=0, cost_usd=0)
            db.session.add(c)
            created += 1
        else:
            updated += 1
        # Academy owns: title, trainer (instructor), student count, status, link.
        # We keep our manual financials (price/cost) untouched.
        c.title = (row.get('title') or c.title or '').strip() or 'دورة بدون عنوان'
        c.trainer_name = instructor or c.trainer_name
        c.lms_instructor_email = email
        c.students_count = int(row.get('enrolled_count') or 0)
        c.status = status
        c.lms_synced = True
    db.session.commit()
    return jsonify({
        'message': 'تمت المزامنة من الأكاديمية',
        'total': len(rows), 'created': created, 'updated': updated,
    })

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
@roles_required('admin')
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
    viewer_role = user_dashboard_role(g.user)
    linked_name = user_linked_name(g.user)
    if viewer_role == 'trainer':
        items = [item for item in items if names_match(item.name, linked_name) or names_match(item.name, g.user.name)]
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

@app.route('/api/investments', methods=['GET'])
@token_required
def list_investments():
    rate = get_rate()
    items = Investment.query.order_by(Investment.created_at.desc()).all()
    course_lookup = {course.id: course for course in Course.query.all()}
    opportunity_lookup = {item.id: item for item in InvestmentOpportunity.query.all()}
    viewer_role = user_dashboard_role(g.user)
    linked_name = user_linked_name(g.user)
    if viewer_role == 'investor':
        items = [item for item in items if names_match(item.investor_name, linked_name) or names_match(item.investor_name, g.user.name) or item.investor_user_id == g.user.id]
    return jsonify([serialize_investment(item, rate, course_lookup, opportunity_lookup) for item in items])

@app.route('/api/investments', methods=['POST'])
@token_required
def create_investment():
    d = request.json or {}
    item = Investment(
        opportunity_id=d.get('opportunity_id'),
        course_id=d.get('course_id'),
        investor_name=d.get('investor_name', ''),
        investor_user_id=d.get('investor_user_id') or (g.user.id if user_dashboard_role(g.user) in ('investor', 'trainer') else None),
        amount_egp=d.get('amount_egp', 0),
        amount_usd=d.get('amount_usd', 0),
        profit_percent=d.get('profit_percent', 20),
        share_pct=d.get('share_pct', 0),
        status=d.get('status', 'accrued'),
        actual_return=d.get('actual_return', 0),
        notes=d.get('notes', ''),
    )
    db.session.add(item)
    if item.opportunity_id:
        opportunity = InvestmentOpportunity.query.get(item.opportunity_id)
        if opportunity:
            sync_opportunity_funding(opportunity)
    if item.investor_name:
        wallet = get_or_create_wallet(item.investor_name, item.investor_user_id)
        sync_wallet(wallet)
    db.session.commit()
    return jsonify({'id': item.id, 'message': 'تم إضافة الاستثمار'}), 201

@app.route('/api/investments/<int:id>', methods=['PUT'])
@token_required
def update_investment(id):
    item = Investment.query.get_or_404(id)
    d = request.json or {}
    previous_name = item.investor_name
    previous_opportunity_id = item.opportunity_id
    for key in ['opportunity_id', 'course_id', 'investor_name', 'investor_user_id', 'amount_egp', 'amount_usd', 'profit_percent', 'share_pct', 'status', 'actual_return', 'notes']:
        if key in d:
            setattr(item, key, d[key])
    if previous_opportunity_id:
        opportunity = InvestmentOpportunity.query.get(previous_opportunity_id)
        if opportunity:
            sync_opportunity_funding(opportunity)
    if item.opportunity_id:
        opportunity = InvestmentOpportunity.query.get(item.opportunity_id)
        if opportunity:
            sync_opportunity_funding(opportunity)
    if previous_name:
        wallet = get_or_create_wallet(previous_name)
        sync_wallet(wallet)
    if item.investor_name:
        wallet = get_or_create_wallet(item.investor_name, item.investor_user_id)
        sync_wallet(wallet)
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/investments/<int:id>', methods=['DELETE'])
@token_required
def delete_investment(id):
    item = Investment.query.get_or_404(id)
    deleted_name = item.investor_name
    deleted_opportunity_id = item.opportunity_id
    db.session.delete(item)
    if deleted_opportunity_id:
        opportunity = InvestmentOpportunity.query.get(deleted_opportunity_id)
        if opportunity:
            sync_opportunity_funding(opportunity)
    if deleted_name:
        wallet = get_or_create_wallet(deleted_name)
        sync_wallet(wallet)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

@app.route('/api/investments/active', methods=['GET'])
@token_required
def investment_active():
    rate = get_rate()
    viewer_role = user_dashboard_role(g.user)
    linked_name = user_linked_name(g.user)
    items = Investment.query.filter(Investment.status.in_(['active', 'pending', 'accrued'])).order_by(Investment.created_at.desc()).all()
    if viewer_role == 'investor':
        items = [item for item in items if names_match(item.investor_name, linked_name) or names_match(item.investor_name, g.user.name) or item.investor_user_id == g.user.id]
    course_lookup = {course.id: course for course in Course.query.all()}
    opportunity_lookup = {item.id: item for item in InvestmentOpportunity.query.all()}
    return jsonify([serialize_investment(item, rate, course_lookup, opportunity_lookup) for item in items])

@app.route('/api/investments/history', methods=['GET'])
@token_required
def investment_history():
    rate = get_rate()
    viewer_role = user_dashboard_role(g.user)
    linked_name = user_linked_name(g.user)
    items = Investment.query.filter(Investment.status.in_(['completed', 'loss', 'paid'])).order_by(Investment.created_at.desc()).all()
    if viewer_role == 'investor':
        items = [item for item in items if names_match(item.investor_name, linked_name) or names_match(item.investor_name, g.user.name) or item.investor_user_id == g.user.id]
    course_lookup = {course.id: course for course in Course.query.all()}
    opportunity_lookup = {item.id: item for item in InvestmentOpportunity.query.all()}
    return jsonify([serialize_investment(item, rate, course_lookup, opportunity_lookup) for item in items])

@app.route('/api/investment-opportunities', methods=['GET'])
@token_required
def list_investment_opportunities():
    rate = get_rate()
    items = InvestmentOpportunity.query.order_by(InvestmentOpportunity.created_at.desc()).all()
    viewer_role = user_dashboard_role(g.user)
    if viewer_role == 'investor':
        items = [item for item in items if item.status in ('open', 'hot', 'invite_only', 'funded')]
    course_lookup = {course.id: course for course in Course.query.all()}
    return jsonify([serialize_opportunity(item, rate, course_lookup) for item in items])

@app.route('/api/investment-opportunities', methods=['POST'])
@token_required
@roles_required('admin')
def create_investment_opportunity():
    d = request.json or {}
    item = InvestmentOpportunity(
        course_id=d.get('course_id'),
        target_amount=d.get('target_amount', 0),
        min_investment=d.get('min_investment', 200),
        current_funded=d.get('current_funded', 0),
        expected_roi=d.get('expected_roi', 0),
        expected_start=datetime.date.fromisoformat(d['expected_start']) if d.get('expected_start') else None,
        expected_end=datetime.date.fromisoformat(d['expected_end']) if d.get('expected_end') else None,
        trainer_pct=d.get('trainer_pct', 35),
        platform_pct=d.get('platform_pct', 35),
        investors_pct=d.get('investors_pct', 30),
        affiliate_pct=d.get('affiliate_pct', 0),
        status=d.get('status', 'open'),
        video_url=d.get('video_url', ''),
        notes=d.get('notes', ''),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'id': item.id, 'message': 'تمت إضافة فرصة الاستثمار'}), 201

@app.route('/api/investment-opportunities/<int:id>', methods=['PUT'])
@token_required
@roles_required('admin')
def update_investment_opportunity(id):
    item = InvestmentOpportunity.query.get_or_404(id)
    d = request.json or {}
    for key in ['course_id', 'target_amount', 'min_investment', 'current_funded', 'expected_roi', 'trainer_pct', 'platform_pct', 'investors_pct', 'affiliate_pct', 'status', 'video_url', 'notes']:
        if key in d:
            setattr(item, key, d[key])
    if 'expected_start' in d:
        item.expected_start = datetime.date.fromisoformat(d['expected_start']) if d.get('expected_start') else None
    if 'expected_end' in d:
        item.expected_end = datetime.date.fromisoformat(d['expected_end']) if d.get('expected_end') else None
    db.session.commit()
    return jsonify({'message': 'تم تحديث فرصة الاستثمار'})

@app.route('/api/investment-opportunities/<int:id>', methods=['DELETE'])
@token_required
@roles_required('admin')
def delete_investment_opportunity(id):
    item = InvestmentOpportunity.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'تم حذف فرصة الاستثمار'})

@app.route('/api/investor/wallet', methods=['GET'])
@token_required
def get_investor_wallet():
    rate = get_rate()
    viewer_role = user_dashboard_role(g.user)
    investor_name = request.args.get('investor_name', '').strip() if viewer_role == 'admin' else user_linked_name(g.user)
    if not investor_name:
        return jsonify({'error': 'لا يوجد مستثمر مرتبط بهذا الحساب'}), 400
    wallet = get_or_create_wallet(investor_name, g.user.id if viewer_role in ('investor', 'trainer') else None)
    payload = sync_wallet(wallet)
    db.session.commit()
    return jsonify(serialize_wallet(payload['wallet'], rate, payload['avg_roi'], payload['pending_withdrawals']))

@app.route('/api/investor/withdraw', methods=['POST'])
@token_required
def request_withdrawal():
    rate = get_rate()
    investor_name = user_linked_name(g.user)
    if not investor_name:
        return jsonify({'error': 'هذا الحساب غير مرتبط بمحفظة مستثمر'}), 400
    wallet = get_or_create_wallet(investor_name, g.user.id if user_dashboard_role(g.user) in ('investor', 'trainer') else None)
    payload = sync_wallet(wallet)
    d = request.json or {}
    amount = float(d.get('amount') or 0)
    currency = (d.get('currency') or 'USD').upper()
    amount_usd = amount if currency == 'USD' else amount / (rate or 50)
    if amount_usd < 50:
        return jsonify({'error': 'الحد الأدنى للسحب هو 50 دولار'}), 400
    if amount_usd > wallet.balance:
        return jsonify({'error': 'الرصيد المتاح لا يكفي'}), 400
    item = WithdrawalRequest(wallet_id=wallet.id, amount=round(amount_usd, 2), status='pending')
    db.session.add(item)
    db.session.flush()
    sync_wallet(wallet)
    db.session.commit()
    return jsonify({'id': item.id, 'message': 'تم إرسال طلب السحب وسيتم التعامل معه خلال 7 أيام عمل'})

@app.route('/api/investor/badges', methods=['GET'])
@token_required
def get_investor_badges():
    investor_name = user_linked_name(g.user)
    if not investor_name:
        return jsonify([])
    wallet = get_or_create_wallet(investor_name, g.user.id if user_dashboard_role(g.user) in ('investor', 'trainer') else None)
    payload = sync_wallet(wallet)
    db.session.commit()
    return jsonify(serialize_badges(payload['wallet']))

@app.route('/api/admin/wallets', methods=['GET'])
@token_required
@roles_required('admin')
def admin_wallets():
    rate = get_rate()
    wallets = InvestorWallet.query.order_by(InvestorWallet.created_at.desc()).all()
    rows = []
    for wallet in wallets:
        payload = sync_wallet(wallet)
        pending = WithdrawalRequest.query.filter_by(wallet_id=wallet.id, status='pending').count()
        rows.append({**serialize_wallet(payload['wallet'], rate, payload['avg_roi'], payload['pending_withdrawals']), 'pending_requests': pending})
    db.session.commit()
    return jsonify(rows)

@app.route('/api/admin/withdrawals', methods=['GET'])
@token_required
@roles_required('admin')
def admin_withdrawals():
    rate = get_rate()
    rows = []
    for item in WithdrawalRequest.query.order_by(WithdrawalRequest.requested_at.desc()).all():
        wallet = InvestorWallet.query.get(item.wallet_id)
        rows.append({
            'id': item.id,
            'investor_name': wallet.investor_name if wallet else '',
            'amount': round(item.amount or 0, 2),
            'amount_egp': round((item.amount or 0) * rate, 2),
            'status': item.status,
            'requested_at': item.requested_at.isoformat() if item.requested_at else None,
            'processed_at': item.processed_at.isoformat() if item.processed_at else None,
        })
    return jsonify(rows)

@app.route('/api/admin/withdrawals/<int:id>', methods=['PUT'])
@token_required
@roles_required('admin')
def update_withdrawal(id):
    item = WithdrawalRequest.query.get_or_404(id)
    d = request.json or {}
    if d.get('status') in ('approved', 'rejected', 'completed'):
        item.status = d['status']
        item.processed_at = datetime.datetime.utcnow()
    wallet = InvestorWallet.query.get(item.wallet_id)
    if wallet:
        sync_wallet(wallet)
    db.session.commit()
    return jsonify({'message': 'تم تحديث طلب السحب'})

@app.route('/api/ai/investment-recommendation', methods=['GET'])
@token_required
def ai_investment_recommendation():
    opportunities = InvestmentOpportunity.query.order_by(InvestmentOpportunity.created_at.desc()).all()
    course_lookup = {course.id: course for course in Course.query.all()}
    if not opportunities:
        return jsonify({'title': 'لا توجد فرص مطروحة الآن', 'message': 'أضف أول فرصة استثمارية لتظهر التوصيات الذكية.', 'opportunity_id': None})
    viewer_role = user_dashboard_role(g.user)
    investor_name = user_linked_name(g.user)
    wallet = None
    avg_roi = 0
    if viewer_role in ('investor', 'trainer') and investor_name:
        wallet = get_or_create_wallet(investor_name, g.user.id)
        payload = sync_wallet(wallet)
        avg_roi = payload['avg_roi']
    ranked = sorted(
        opportunities,
        key=lambda item: ((item.expected_roi or 0) * 0.6) + (min(100, (sync_opportunity_funding(item) / max(item.target_amount or 1, 1)) * 100) * 0.3) + (15 if item.status == 'hot' else 0),
        reverse=True,
    )
    top = ranked[0]
    course = course_lookup.get(top.course_id)
    db.session.commit()
    return jsonify({
        'title': f"اقتراح اليوم: {course.title if course else 'فرصة استثمارية'}",
        'message': f"هذه الفرصة مناسبة لك بناءً على عائد متوقع {round(top.expected_roi or 0)}% ومستوى تمويل {round(sync_opportunity_funding(top) / max(top.target_amount or 1, 1) * 100)}%. متوسط عائدك الحالي {avg_roi}%.",
        'opportunity_id': top.id,
        'course_id': top.course_id,
        'status': top.status,
    })

@app.route('/api/courses/<int:id>/revenue-split', methods=['GET'])
@token_required
def get_revenue_split(id):
    course = Course.query.get_or_404(id)
    split = get_course_split(course.id)
    db.session.commit()
    return jsonify(serialize_split(split))

@app.route('/api/courses/<int:id>/revenue-split', methods=['PUT'])
@token_required
def update_revenue_split(id):
    course = Course.query.get_or_404(id)
    split = get_course_split(course.id)
    d = request.json or {}
    for key in ['trainer_percent', 'platform_percent', 'investor_percent', 'affiliate_percent', 'notes']:
        if key in d:
            setattr(split, key, d[key])
    db.session.commit()
    return jsonify(serialize_split(split))

@app.route('/api/calculator/simulate', methods=['POST'])
@token_required
def calculator_simulate():
    payload = request.json or {}
    return jsonify(simulate_distribution(payload, get_rate()))

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
    viewer_role = user_dashboard_role(g.user) if getattr(g, 'user', None) else 'admin'
    linked_name = user_linked_name(g.user) if getattr(g, 'user', None) else ''
    revenues = Revenue.query.all()
    expenses = Expense.query.filter_by(is_business=True).all()
    payouts = Payout.query.filter(Payout.status != 'waived').all()
    cash_transactions = CashTransaction.query.order_by(CashTransaction.date.desc()).all()
    campaigns = Campaign.query.all()
    courses = Course.query.all()
    assets = Asset.query.all()
    forecasts = ForecastMonth.query.order_by(ForecastMonth.month.asc()).limit(6).all()

    if viewer_role == 'trainer':
        courses = [course for course in courses if names_match(course.trainer_name, linked_name) or names_match(course.trainer_name, g.user.name)]
        course_ids = {course.id for course in courses}
        course_titles = {(course.title or '').strip() for course in courses}
        revenues = [item for item in revenues if item.course_id in course_ids or any(title and title in (item.description or '') for title in course_titles)]
        payouts = [item for item in payouts if names_match(item.name, linked_name) or names_match(item.name, g.user.name)]
        expenses = [item for item in expenses if any(title and (title in (item.description or '') or title in (item.notes or '')) for title in course_titles)]
        campaigns = [item for item in campaigns if item.course_id in course_ids]
        cash_transactions = []
        assets = []
    elif viewer_role == 'investor':
        investments = [item for item in Investment.query.all() if names_match(item.investor_name, linked_name) or names_match(item.investor_name, g.user.name)]
        course_ids = {item.course_id for item in investments}
        courses = [course for course in courses if course.id in course_ids]
        course_titles = {(course.title or '').strip() for course in courses}
        revenues = [item for item in revenues if item.course_id in course_ids or any(title and title in (item.description or '') for title in course_titles)]
        payouts = []
        expenses = [item for item in expenses if any(title and (title in (item.description or '') or title in (item.notes or '')) for title in course_titles)]
        campaigns = [item for item in campaigns if item.course_id in course_ids]
        cash_transactions = []
        assets = []
    
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

def ensure_runtime_schema():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    with db.engine.begin() as connection:
        if 'users' in existing_tables:
            user_columns = {column['name'] for column in inspector.get_columns('users')}
            if 'dashboard_role' not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN dashboard_role VARCHAR(50) DEFAULT 'admin'"))
                connection.execute(text("UPDATE users SET dashboard_role = role WHERE dashboard_role IS NULL"))
            if 'linked_to_name' not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN linked_to_name VARCHAR(255)"))
            if 'preferred_currency' not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN preferred_currency VARCHAR(10) DEFAULT 'AUTO'"))
        if 'courses' in existing_tables:
            course_columns = {column['name'] for column in inspector.get_columns('courses')}
            if 'lms_instructor_email' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN lms_instructor_email VARCHAR(255)"))
            if 'lms_synced' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN lms_synced BOOLEAN DEFAULT 0"))
            if 'open_for_investment' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN open_for_investment BOOLEAN DEFAULT 0"))
        if 'campaigns' in existing_tables:
            campaign_columns = {column['name'] for column in inspector.get_columns('campaigns')}
            if 'course_id' not in campaign_columns:
                connection.execute(text("ALTER TABLE campaigns ADD COLUMN course_id INTEGER"))
        if 'investments' in existing_tables:
            investment_columns = {column['name'] for column in inspector.get_columns('investments')}
            if 'opportunity_id' not in investment_columns:
                connection.execute(text("ALTER TABLE investments ADD COLUMN opportunity_id INTEGER"))
            if 'investor_user_id' not in investment_columns:
                connection.execute(text("ALTER TABLE investments ADD COLUMN investor_user_id INTEGER"))
            if 'share_pct' not in investment_columns:
                connection.execute(text("ALTER TABLE investments ADD COLUMN share_pct FLOAT DEFAULT 0"))
            if 'actual_return' not in investment_columns:
                connection.execute(text("ALTER TABLE investments ADD COLUMN actual_return FLOAT DEFAULT 0"))

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
    ensure_runtime_schema()
    seed()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
