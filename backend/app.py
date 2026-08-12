"""
ElProfessor Management Dashboard - Backend API
Flask + SQLAlchemy + SQLite (upgradeable to MySQL/PostgreSQL)
"""
import os, json, datetime, hashlib, secrets, functools, logging, time, re, html
from collections import deque
from urllib.parse import quote
from xml.sax.saxutils import escape as xesc
from flask import Flask, request, jsonify, g, send_from_directory, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import jwt
import requests

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('elprofessor.dashboard')

# ============================================================
# CONFIG
# ============================================================
app = Flask(__name__)

# Are we running in production? (any of these signals)
_flask_env = (os.environ.get('FLASK_ENV') or '').strip().lower()
_app_env = (os.environ.get('ENV') or os.environ.get('APP_ENV') or '').strip().lower()
IS_PRODUCTION = (
    _flask_env == 'production'
    or _app_env == 'production'
    or (os.environ.get('PROD') or '').strip().lower() in ('1', 'true', 'yes')
)

_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    if IS_PRODUCTION:
        # In production a missing SECRET_KEY is fatal: an ephemeral key would
        # silently invalidate every issued JWT on each redeploy (logs everyone out)
        # and makes sessions forgeable across instances. Fail fast instead.
        raise RuntimeError(
            "SECRET_KEY is not set in production. Set a strong, stable SECRET_KEY "
            "env var (e.g. `python -c 'import secrets;print(secrets.token_hex(32))'`) "
            "before starting the dashboard backend."
        )
    logger.warning(
        "SECRET_KEY is not set — generating an ephemeral key (dev only). "
        "This INVALIDATES all issued JWTs on restart; SET SECRET_KEY in production."
    )
    _secret_key = secrets.token_hex(32)
app.config['SECRET_KEY'] = _secret_key
database_url = os.environ.get('DATABASE_URL', 'sqlite:///elprofessor.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Emit real UTF-8 in every JSON response instead of \uXXXX escapes. These payloads are
# almost entirely Arabic, so escaping inflates them ~2.7x — the public articles feed that
# every marketing-site page load blocks on measured 2,007,714 bytes escaped vs 737,192
# unescaped (-63%). Safe for every client: the response was already served as UTF-8
# (RFC 8259 mandates UTF-8 for JSON) and parsers read raw UTF-8 and \uXXXX identically.
# NOTE: Flask >= 2.2 API (requirements pin flask==3.0.0). On Flask < 2.2 this line must be
# `app.config['JSON_AS_ASCII'] = False` instead.
app.json.ensure_ascii = False

# CORS allow-list. Default to the dashboard + brand origins; override via CORS_ORIGINS
# (comma-separated). A literal '*' is honoured but discouraged with credentials.
_DEFAULT_CORS_ORIGINS = [
    'https://dashboard.elprofessor.net',
    'https://elprofessor.net',
    'https://www.elprofessor.net',
    'https://api.elprofessor.net',
]
_cors_env = (os.environ.get('CORS_ORIGINS') or '').strip()
if _cors_env:
    CORS_ORIGINS = [o.strip() for o in _cors_env.split(',') if o.strip()]
else:
    CORS_ORIGINS = list(_DEFAULT_CORS_ORIGINS)
CORS(
    app,
    origins=CORS_ORIGINS,
    supports_credentials=True,
    allow_headers=['Content-Type', 'Authorization', 'X-ELP-Metrics-Secret'],
    methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
)
db = SQLAlchemy(app)


# Paths that must stay crawlable even if this host is ever blanket-noindexed.
# `/sitemap-articles.xml` is served for elprofessor.net (its /.htaccess 301s here); a
# `X-Robots-Tag: noindex` on it would stop Google reading the article URLs entirely —
# silently, with no error anywhere. Keep this list in sync with any noindex work.
_ROBOTS_EXEMPT_PATHS = frozenset({'/sitemap-articles.xml'})


# ---- baseline security headers on every response (clickjacking / MIME-sniff / TLS-downgrade) ----
@app.after_request
def _security_headers(resp):
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    if IS_PRODUCTION:
        resp.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    # ⚠️ If you add `X-Robots-Tag: noindex, nofollow` to this host, add it ABOVE this
    # guard — never below it, and never in a proxy/nginx layer Flask cannot reach.
    if request.path in _ROBOTS_EXEMPT_PATHS:
        resp.headers.pop('X-Robots-Tag', None)
    return resp


# ---- tiny in-memory per-IP rate limiter (the admin dashboard is single-process + low-traffic;
# this blunts credential-stuffing on the auth endpoints the platform already protects) ----
_RATE_BUCKETS = {}


def _client_ip():
    xff = request.headers.get('CF-Connecting-IP') or request.headers.get('X-Forwarded-For', '')
    return (xff.split(',')[0].strip() if xff else request.remote_addr) or 'unknown'


def _rate_ok(key, limit, window_sec):
    now = time.time()
    dq = _RATE_BUCKETS.setdefault(key, deque())
    while dq and dq[0] <= now - window_sec:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    return True


CUT_OFF_DATE = datetime.date(2026, 6, 1)
SEED_PREFIX = 'seed:v3'
# REAL (not demo) founder records — restored into seed() idempotently. Tagged so
# they are distinguishable from demo rows but, unlike demo rows, are NEVER deleted
# or re-injected on boot once present (they are real, editable, persistent data).
REAL_PREFIX = 'real:v1'

# ============================================================
# MODELS
# ============================================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255))
    # FAIL CLOSED: a row created without an explicit role is the LEAST privileged
    # one, never an admin. Every creation path (register / sso / create_user /
    # seed) sets both fields explicitly.
    role = db.Column(db.String(50), default='viewer')
    dashboard_role = db.Column(db.String(50), default='viewer')
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
    payment_id = db.Column(db.String(255), unique=True, nullable=True)  # idempotency key for platform finance-events (re-delivery safe)
    # FX honesty for finance-events in a currency that isn't EGP/USD: amount_egp/usd
    # stay NULL/0 (no guessed conversion) and the true figure lives here instead of
    # being silently dropped. needs_fx=True flags it for reports ("بعملة أجنبية —
    # بانتظار تسوية") until someone books the real conversion manually.
    amount_original = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(8), nullable=True)
    needs_fx = db.Column(db.Boolean, default=False)
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
    lms_sales_count = db.Column(db.Integer, default=0)   # real units sold (WooCommerce)
    lms_revenue = db.Column(db.Float, default=0)          # real gross revenue (WooCommerce, store currency)
    lms_currency = db.Column(db.String(8))               # WooCommerce store currency (e.g. GBP)
    platform_course_id = db.Column(db.String(50))        # native platform (Mongo) course id — set when published to the platform
    platform_course_slug = db.Column(db.String(200))     # native platform course slug (app.elprofessor.net link)
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

class AuditLog(db.Model):
    """Append-only trail of dashboard mutations (F5). One row per key admin action
    (role/plan change, article publish/reject, course changes, settings, add-admin…).
    Powers D9 «سجل العمليات» and feeds the D7 automation-spotter agent."""
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    actor_email = db.Column(db.String(255))          # who did it (g.user.email) or 'system'
    action = db.Column(db.String(120))               # dotted verb, e.g. 'user.role_change'
    target = db.Column(db.String(255))               # affected entity id/ref (free-form)
    meta_json = db.Column(db.Text)                    # JSON blob of extra context (optional)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class AgentReport(db.Model):
    """Latest report written by an AI-team agent (D7). Persisted so the view renders
    cheaply and reports are auditable. One agent may have many rows over time; the
    view reads the most recent per agent."""
    __tablename__ = 'agent_reports'
    id = db.Column(db.Integer, primary_key=True)
    agent = db.Column(db.String(60), nullable=False)  # articles / sales / master / …
    summary = db.Column(db.Text)                       # 2-3 sentence narrative
    bullets_json = db.Column(db.Text)                  # JSON list[str] of findings
    actions_json = db.Column(db.Text)                  # JSON list[str] of suggested actions
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

class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    excerpt = db.Column(db.Text)
    cat = db.Column(db.String(120))         # category
    kicker = db.Column(db.String(255))
    date = db.Column(db.String(40))         # display date (free-form, as authored)
    by = db.Column(db.String(255))          # author byline
    tone = db.Column(db.String(80))
    video = db.Column(db.Text)              # optional video URL
    image_url = db.Column(db.Text)          # optional external cover image URL (http/https)
    body = db.Column(db.Text)               # JSON-encoded list[str] of paragraphs
    meta_description = db.Column(db.Text)   # SEO <meta name=description> (from the platform generator)
    keywords = db.Column(db.Text)           # JSON-encoded list[str] of focus keywords
    faq = db.Column(db.Text)                # JSON-encoded list[{q,a}] → FAQPage JSON-LD (AEO)
    target_audience = db.Column(db.Text)    # «الفئوية» → site audience filter (المحامون/وكلاء النيابة/…)
    status = db.Column(db.String(20), default='draft')  # draft | published
    published_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(80))
    topic = db.Column(db.String(255))
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='new')    # new | replied
    reply_body = db.Column(db.Text)
    replied_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class EscrowSession(db.Model):
    """Money held in escrow for a paid platform service (consultation/course).
    Commission (default 15%) is deducted AT RELEASE, never at hold.
    net = amount*(1-commission_rate); commission = amount*commission_rate."""
    __tablename__ = 'escrow_sessions'
    id = db.Column(db.String(20), primary_key=True)   # 'ESC-0001'
    student_name = db.Column(db.String(255))
    student_email = db.Column(db.String(255))
    expert_name = db.Column(db.String(255))
    expert_email = db.Column(db.String(255))
    amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(8), default='EGP')
    status = db.Column(db.String(20), default='held')  # held|confirm|released|refunded|dispute
    held_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    release_at = db.Column(db.DateTime)                # held_at + 72h
    released_at = db.Column(db.DateTime, nullable=True)
    commission_rate = db.Column(db.Float, default=0.15)
    revenue_id = db.Column(db.Integer, db.ForeignKey('revenues.id'), nullable=True, unique=True)  # idempotency guard (nullable-unique: DB-enforced single commission row)
    ref = db.Column(db.String(255))                   # course/consultation ref
    source = db.Column(db.String(50), default='platform')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    @property
    def commission(self):
        return round((self.amount or 0) * (self.commission_rate or 0), 2)

    @property
    def net(self):
        return round((self.amount or 0) * (1 - (self.commission_rate or 0)), 2)

class Dispute(db.Model):
    __tablename__ = 'disputes'
    id = db.Column(db.String(20), primary_key=True)   # 'DSP-0001'
    session_id = db.Column(db.String(20), db.ForeignKey('escrow_sessions.id'), nullable=False)
    party = db.Column(db.String(20))                  # student|expert
    reason = db.Column(db.Text)
    stage = db.Column(db.String(20), default='open')  # open|review|decision
    amount_frozen = db.Column(db.Float, default=0)
    opened_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    decision_sla = db.Column(db.DateTime)             # opened_at + 3 business days
    decision = db.Column(db.String(20), nullable=True)  # null|student|expert|split
    split_pct = db.Column(db.Float, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
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
    """Coarse role gate. Delegates to role_grants() — the SINGLE source of truth
    shared with every data-scoping filter — so a route gate and a row filter can
    never disagree about who this user is (see role_grants for the rule)."""
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if not getattr(g, 'user', None):
                return jsonify({'error': 'Unauthorized'}), 401
            if not role_grants(g.user, *allowed_roles):
                return jsonify({'error': 'Forbidden'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# --- Persisted per-role module permissions (D9). The admin edits a map
# {dashboard_role: {"modules": [...]}} stored in the `settings` table (key
# ROLE_PERMISSIONS_KEY). It gates which MODULES a non-admin role may reach — the
# SAME map the frontend nav reads, so UI and API agree. Backward-compatible:
# admin always bypasses, and a role with NO entry is left permissive (nothing
# changes for existing deployments until the admin sets restrictions). ---
ROLE_PERMISSIONS_KEY = 'role_permissions'

def _role_permissions():
    s = Setting.query.get(ROLE_PERMISSIONS_KEY)
    if not s or not s.value:
        return {}
    try:
        data = json.loads(s.value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def role_allows_module(user, module):
    """True if `user` may access `module`. Unambiguous admin → always; a role
    absent from the persisted map → permissive (no restriction configured yet).

    Takes the USER, not a raw role string: «is this an admin?» has exactly one
    answer in this file (is_admin_scope), and a bare `role == 'admin'` here
    disagreed with it — a split-identity row (dashboard_role='admin',
    role='trainer') that every other gate denies used to sail past every
    module restriction."""
    if not user:
        return False
    if is_admin_scope(user):
        return True
    role = user_dashboard_role(user)
    entry = _role_permissions().get(role)
    if not entry:
        return True
    mods = entry.get('modules') if isinstance(entry, dict) else entry
    if not isinstance(mods, list):
        return True
    return module in mods

def module_required(module):
    """Gate a route by the persisted role→module map (D9). Layered ON TOP of
    roles_required — the coarse role allowlist still applies first."""
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if not getattr(g, 'user', None):
                return jsonify({'error': 'Unauthorized'}), 401
            if not role_allows_module(g.user, module):
                return jsonify({'error': 'هذا القسم غير متاح لدورك'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# ============================================================
# HELPER
# ============================================================

def normalize_role(value):
    """Canonical form of a role string. 'Admin ' → 'admin'. Every comparison in
    this file MUST go through this — a literal comparison locked real admins out
    of their own dashboard whenever the stored value carried case/whitespace."""
    return (value or '').strip().lower()


def role_grants(user, *allowed_roles):
    """THE authority on «does this user hold one of these roles?».

    A user carries TWO role fields (`role`, the legacy column, and
    `dashboard_role`, what the UI renders). They used to be read by different
    layers — route gates read `role`, data filters read `dashboard_role` — so a
    row with role='admin'/dashboard_role='trainer' walked through every admin
    gate while its UI said «trainer», and the reverse (role='trainer'/
    dashboard_role='admin', which the old buggy dashboard_role migration created
    wholesale) read the whole money ledger.

    Rule: the EFFECTIVE role is `dashboard_role` (the identity the user is
    actually operating under), but a divergent `role` may only ever DOWNGRADE —
    when the two fields disagree, BOTH have to be allowed. Consequences:
      * real admin (admin/admin)                 → allowed  (never locked out)
      * admin/trainer split                      → denied admin routes (its UI is a trainer's anyway)
      * trainer/admin split (legacy migration)   → denied admin routes (no escalation)
      * dashboard_role empty (pre-migration row) → falls back to `role`, so a
        seed-created admin with only `role='admin'` still passes.
    Neither field alone can escalate, which is why this is safer than either the
    strict `dashboard_role` preference or the permissive `_is_admin_user` OR.
    """
    if not user:
        return False
    allowed = {normalize_role(r) for r in allowed_roles}
    dash = normalize_role(getattr(user, 'dashboard_role', None))
    raw = normalize_role(getattr(user, 'role', None))
    effective = dash or raw or 'viewer'
    if effective not in allowed:
        return False
    for other in (dash, raw):
        if other and other != effective and other not in allowed:
            return False
    return True


def is_admin_scope(user):
    """True only for an unambiguous admin — the gate for FULL-ledger reads
    (every payout / every investment / every course's money rows)."""
    return role_grants(user, 'admin')


def _is_admin_user(user):
    """Permissive «might be an admin» — used ONLY by the last-admin protection,
    where over-counting is the safe direction (it refuses to demote/delete an
    account that could still be the last way back in). NEVER use it to grant
    access; use role_grants()/is_admin_scope() for that."""
    if not user:
        return False
    return 'admin' in {
        normalize_role(getattr(user, 'role', None)),
        normalize_role(getattr(user, 'dashboard_role', None)),
    }

def active_admin_count(exclude_id=None):
    """Count active local dashboard admins, optionally excluding one user id."""
    # Counts only accounts that can ACTUALLY act as admin (role_grants), not the
    # permissive «might be». Under-counting is the safe direction here: it makes
    # the last-admin guard fire MORE often, so a split-identity row that cannot
    # really administer anything can never be mistaken for the spare key.
    count = 0
    for u in User.query.filter_by(is_active=True).all():
        if exclude_id is not None and u.id == exclude_id:
            continue
        if role_grants(u, 'admin'):
            count += 1
    return count

def is_last_admin(user):
    """True if `user` is an active admin and the ONLY remaining active admin."""
    if not _is_admin_user(user) or not getattr(user, 'is_active', False):
        return False
    return active_admin_count(exclude_id=user.id) == 0

def _audit(action, target='', meta=None, actor=None):
    """Append one AuditLog row for a mutation (F5). Best-effort — an audit-write
    failure must NEVER break the caller's request, so it swallows exceptions and
    rolls back only the audit row. Actor defaults to the authenticated user."""
    try:
        actor_email = actor or (getattr(g, 'user', None) and getattr(g.user, 'email', None)) or 'system'
        row = AuditLog(
            actor_email=str(actor_email)[:255],
            action=str(action or '')[:120],
            target=str(target if target is not None else '')[:255],
            meta_json=(json.dumps(meta, ensure_ascii=False)[:4000] if meta is not None else None),
        )
        db.session.add(row)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

def _actor_email():
    """The signed-in dashboard user's email, for platform-side attribution (`closed_by`,
    `hidden_by`…). Falls back to 'dashboard' so a write is never blocked by a missing session —
    but an anonymous write is impossible anyway: every caller is @token_required.

    Clamped to 120 chars because that is the platform's declared limit for `by`
    (BridgeMarketClose/BridgeMarketHide, max_length=120). Our column allows 255, and a longer
    value would 422 the whole moderation write — losing the ACTION to save the attribution."""
    try:
        email = (getattr(g, 'user', None) and getattr(g.user, 'email', None)) or 'dashboard'
    except Exception:
        return 'dashboard'
    return str(email)[:120]


def _resp_ok(resp):
    """True when a Flask view return value carries a 2xx status. Handles both a bare
    Response (status 200 by default) and a (body, status) tuple (our proxy error shape)."""
    try:
        if isinstance(resp, tuple):
            return 200 <= int(resp[1]) < 300
        return 200 <= int(getattr(resp, 'status_code', 200)) < 300
    except Exception:
        return False

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
    """The role the user is OPERATING under (what the UI renders), normalized.
    Use it to choose WHICH scope applies; use role_grants()/is_admin_scope() to
    decide whether a privilege is granted."""
    return normalize_role(getattr(user, 'dashboard_role', None)) or normalize_role(getattr(user, 'role', None)) or 'viewer'

def reported_role(user):
    """The role we may TELL the client it has — i.e. the one the gates honour.

    `user_dashboard_role()` answers «which scope applies»; it happily returns
    'admin' for a split row (role='trainer'/dashboard_role='admin') that
    `role_grants()` denies at every admin route. Reporting that to the client
    painted the full admin rail and then 403'd every request behind it — a
    broken screen with no explanation, and the buggy dashboard_role migration
    created such rows wholesale. When the two fields disagree the account holds
    no role either field alone can grant, so we report the harmless 'viewer'
    (the «بانتظار التفعيل» screen) instead of a promise the server will refuse.
    """
    dash = normalize_role(getattr(user, 'dashboard_role', None))
    raw = normalize_role(getattr(user, 'role', None))
    if dash and raw and dash != raw:
        return 'viewer'
    return dash or raw or 'viewer'


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

# Honorific prefixes dropped from the FRONT of a person's name before an
# entitlement (money) comparison. Anchored to the start on purpose: the general
# normalize_name() above does a blanket str.replace that eats the «د » sitting
# INSIDE «أحمد عادل», which is harmless while both sides are mangled the same way
# but is exactly the kind of lossiness you do not want under a strict equality.
# Written in ALREADY-normalized form (أ/إ/آ→ا, ى→ي, ة→ه) — see below.
_ENTITLEMENT_HONORIFICS = (
    'د.', 'د', 'دكتور', 'الدكتور', 'دكتوره',
    'ا.', 'استاذ', 'الاستاذ', 'استاذه',
    'م.', 'مهندس', 'المهندس',
    'dr.', 'dr', 'prof.', 'prof', 'mr.', 'mr', 'mrs.', 'mrs', 'ms.', 'ms',
)

_HARAKAT_RE = re.compile('[ً-ْٰ]')


def normalize_person_name(value):
    """Canonical form of a PERSON's name, for entitlement matching ONLY.

    Lossless apart from cosmetics an Arabic name legitimately varies by:
    case/whitespace, tatweel + harakat, the alef/yaa/taa-marbuta spelling
    variants, and a LEADING honorific («د. أحمد عادل» ≡ «أحمد عادل»). It never
    strips the only remaining token, so a name that IS an honorific cannot
    collapse to the empty string and start matching everything.

    Deliberately separate from normalize_name()/names_match(): those two are the
    fuzzy course-linking rule and must not change.
    """
    raw = (value or '').strip().lower()
    if not raw:
        return ''
    raw = raw.replace('ـ', '')          # tatweel
    raw = _HARAKAT_RE.sub('', raw)           # harakat / dagger alef
    for src, dst in (('أ', 'ا'), ('إ', 'ا'), ('آ', 'ا'), ('ٱ', 'ا'), ('ى', 'ي'), ('ة', 'ه')):
        raw = raw.replace(src, dst)
    parts = raw.split()
    while len(parts) > 1 and parts[0] in _ENTITLEMENT_HONORIFICS:
        parts.pop(0)
    return ' '.join(parts)


def entitlement_key(user):
    """The ONE name this account may claim money rows under: `linked_to_name`,
    which ONLY an admin can write (/api/users POST+PUT). Never `user.name` —
    that is the platform's `full_name`, i.e. USER-CONTROLLED via /api/auth/sso,
    and under the old substring match an account that renamed itself to the
    single letter «ا» read every payout and every investment in the ledger.
    Empty (an account the admin has not linked) claims NOTHING."""
    if not user:
        return ''
    return normalize_person_name(getattr(user, 'linked_to_name', None))


def entitlement_name_matches(row_name, user):
    """Row name ⟷ account link, EXACT after normalization. No containment:
    containment let a one-character name be a substring of every row."""
    key = entitlement_key(user)
    if not key:
        return False
    return normalize_person_name(row_name) == key


def payout_visible_to(payout, user):
    """Is this ONE payout row the user's own? The single matching rule for
    entitlement rows — /api/payouts and the per-course ledger both call it, so
    there is exactly one definition of «my row» in the codebase."""
    if not user:
        return False
    return entitlement_name_matches(getattr(payout, 'name', ''), user)


def investment_visible_to(investment, user):
    """Is this ONE investment row the user's own? Same single rule for
    /api/investments, /active, /history and the per-course ledger.
    The investor_user_id link is a hard foreign key (set when the investor
    themself created the row) and stays authoritative; the name path is the
    strict, admin-controlled one."""
    if not user:
        return False
    owner_id = getattr(investment, 'investor_user_id', None)
    if owner_id is not None and getattr(user, 'id', None) is not None and owner_id == user.id:
        return True
    return entitlement_name_matches(getattr(investment, 'investor_name', ''), user)


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
    if not _rate_ok('login:' + _client_ip(), 10, 300):
        return jsonify({'error': 'محاولات كتير — استنى شوية وجرّب تاني'}), 429
    data = request.json or {}
    email = (data.get('email') or '').lower().strip()
    password = data.get('password') or ''
    if not email or len(email) > 255 or len(password) > 256:
        return jsonify({'error': 'Invalid credentials'}), 401
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    dashboard_role = reported_role(user)
    _audit('auth.login', target=user.id, meta={'role': dashboard_role}, actor=user.email)
    return jsonify({'token': token, 'user': {'id': user.id, 'email': user.email, 'name': user.name, 'role': dashboard_role, 'dashboard_role': dashboard_role, 'linked_to_name': user_linked_name(user), 'preferred_currency': (user.preferred_currency or 'AUTO')}})

@app.route('/api/auth/register', methods=['POST'])
def register():
    if not _rate_ok('register:' + _client_ip(), 5, 3600):
        return jsonify({'error': 'محاولات كتير — استنى شوية وجرّب تاني'}), 429
    data = request.json or {}
    email = (data.get('email') or '').lower().strip()
    password = data.get('password') or ''
    name = (data.get('name') or '').strip()
    if not email or not password or not name:
        return jsonify({'error': 'الاسم والبريد وكلمة المرور مطلوبة'}), 400
    if len(email) > 255 or len(password) > 256 or len(name) > 120 or '@' not in email:
        return jsonify({'error': 'بيانات غير صالحة'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'هذا البريد مسجل بالفعل'}), 409
    # Public self-registration must NOT mint a usable account. The new user is
    # created PENDING + INACTIVE with the lowest role: token_required rejects
    # inactive users, so they get ZERO data access until an admin activates them
    # and assigns a real role. (A self-registered 'viewer' previously read the
    # full company P&L + cap-table — this closes that hole.)
    user = User(
        email=email,
        password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
        name=name,
        role='pending',
        dashboard_role='pending',
        linked_to_name='',
        preferred_currency='AUTO',
        is_active=False,
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'تم استلام طلبك. الحساب قيد المراجعة — ستتمكن من الدخول بعد موافقة الإدارة.'}), 201

@app.route('/api/auth/me', methods=['GET'])
@token_required
def me():
    dashboard_role = reported_role(g.user)
    return jsonify({'id': g.user.id, 'email': g.user.email, 'name': g.user.name, 'role': dashboard_role, 'dashboard_role': dashboard_role, 'linked_to_name': user_linked_name(g.user), 'preferred_currency': (g.user.preferred_currency or 'AUTO')})

# --- Single sign-on FROM the main platform (one identity reaches the BI brain) ---
PLATFORM_API_URL = os.environ.get('PLATFORM_API_URL', 'https://api.elprofessor.net').rstrip('/')
PLATFORM_SSO_AUD = 'elprofessor-dashboard'
# Platform system role -> this dashboard's role.
# staff = a follow-up employee (limited), NOT a full admin; admin stays admin.
_PLATFORM_ROLE_MAP = {'admin': 'admin', 'staff': 'employee', 'investor': 'investor'}

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
    trainer_status = (platform_user.get('trainer_status') or '').strip().lower()
    mapped_role = _PLATFORM_ROLE_MAP.get(platform_role, 'viewer')
    # A trainer is an approved STATUS on the platform, not a system role — land them
    # as a dashboard trainer (unless they already hold a stronger management role).
    if mapped_role == 'viewer' and trainer_status == 'approved':
        mapped_role = 'trainer'

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
        if not normalize_role(getattr(user, 'dashboard_role', None)):
            user.dashboard_role = mapped_role
        # Never leave the two identity fields split (role_grants denies a split).
        if not normalize_role(getattr(user, 'role', None)):
            user.role = normalize_role(user.dashboard_role) or mapped_role
        if not user.is_active:
            user.is_active = True
    db.session.commit()

    token_out = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    role_out = reported_role(user)
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
@module_required('users')              # D9: admin can revoke per-role module access
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

@app.route('/api/platform-chat-insights', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_chat_insights():
    """Demand analysis from the platform chat (proxied via the METRICS_SECRET bridge)."""
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط الربط بعد'}), 503
    try:
        r = requests.get(
            f"{PLATFORM_API_URL}/api/bridge/chat-insights",
            params={'limit': 3000},
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=15,
        )
    except Exception:
        return jsonify({'error': 'تعذر الاتصال بالمنصة'}), 502
    if r.status_code != 200:
        return jsonify({'error': 'تعذر جلب التحليل'}), 502
    return jsonify(r.json() if r.content else {})

@app.route('/api/platform-chat-insights/<insight_id>', methods=['GET'])
@token_required
@roles_required('admin')
def platform_chat_insight_detail(insight_id):
    """Open ONE question from «تحليل الطلب»: its full text, what «بروف» answered, and —
    when the turn was signed-in — who asked. The list route above is open to `employee`
    and carries no identity; this one does, so it is admin-only. The platform writes an
    audit entry on every open."""
    return _platform_proxy('GET', f"/api/bridge/chat-insights/{insight_id}")


@app.route('/api/platform-chat-insights/classify', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_chat_insights_classify():
    """Trigger the platform's AI demand-classifier over un-classified chat_insights docs
    (idempotent — only touches docs missing a category). Powers the «حدّث التصنيف» button
    in «تحليل الطلب» and the n8n daily schedule. Returns {classified, remaining} (never 5xx)."""
    try:
        limit = int(request.args.get('limit') or 50)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(200, limit))
    return _platform_proxy('POST', '/api/bridge/chat-insights/classify', params={'limit': limit})

@app.route('/api/platform-users/<user_id>/role', methods=['POST'])
@token_required
@roles_required('admin')
def platform_users_set_role(user_id):
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط الربط بعد'}), 503
    body = request.json or {}
    role = (body.get('role') or '').strip()

    # LAST-ADMIN protection: if this role change demotes the platform user that maps
    # (by email) to the only remaining active local dashboard admin, refuse it.
    target_email = (body.get('email') or '').lower().strip()
    if role and role.lower() != 'admin' and target_email:
        local = User.query.filter_by(email=target_email).first()
        if local and is_last_admin(local):
            return jsonify({
                'error': 'لا يمكن تنزيل دور المدير الوحيد المتبقي. أضف مديرًا آخر أولًا.'
            }), 409

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
    _audit('user.role_change', target=user_id, meta={'role': role, 'email': target_email})
    return jsonify(r.json() if r.content else {})

@app.route('/api/platform-users/<user_id>/plan', methods=['POST'])
@token_required
@roles_required('admin')
def platform_users_set_plan(user_id):
    """Assign a subscription plan to a platform user from the D3 «الباقة» control.
    The platform validates plan_id against the real plan catalog (422 «باقة غير معروفة»
    on an unknown id, 404 when the user is missing) and returns the updated user summary."""
    body = request.json or {}
    plan_id = (body.get('plan_id') or '').strip()
    resp = _platform_proxy('POST', f"/api/bridge/users/{user_id}/plan", json_body={'plan_id': plan_id})
    if _resp_ok(resp):
        _audit('user.plan_assign', target=user_id, meta={'plan_id': plan_id})
    return resp

@app.route('/api/platform-users/<user_id>/tags', methods=['POST'])
@token_required
@roles_required('admin')
def platform_users_set_tags(user_id):
    """Persist the manual tag override on a platform user (D3). Blanks are dropped, values
    trimmed and capped at 20 on the platform side; the chat-derived `segment` is never touched.
    Returns the updated user summary (tags reflect the write)."""
    body = request.json or {}
    raw = body.get('tags')
    tags = [str(t).strip() for t in raw if str(t).strip()][:20] if isinstance(raw, list) else []
    return _platform_proxy('POST', f"/api/bridge/users/{user_id}/tags", json_body={'tags': tags})

# --- Remove a trainer/expert profile (the «محمد افندي» problem) -----------------
# There was NO way to remove a seeded/demo trainer from anywhere: the dashboard buttons were
# hard-disabled because no platform endpoint existed, the only revoke path needs a
# `trainer_applications` row a seeded trainer never had, and the bulk launch-clean sweep also
# purges every course. These two proxies expose the platform's single-user primitives.
#
# DEACTIVATE, not DELETE — deliberately. The public directory already hides a profile that
# isn't `profile_public_ready`, and a true purge would have to cascade ~40 collections. More
# importantly the platform re-approves anyone still holding a granted provider section key on
# every boot (backfill_provider_status) and on every authenticated request
# (migrate_legacy_user_doc), so the deactivate MUST write a non-empty `rejected` sentinel AND
# revoke the section keys in the same update — that logic lives on the platform, server-side.
# ⚠️ FOUNDER_EMAIL on the platform still defaults to admin@demo.com (ops_command.py): set that
# env var to the founder's real account BEFORE removing that specific trainer, or the Telegram
# «اعمل دورة» action ends up drafting courses under a deactivated owner.
@app.route('/api/platform-trainers/<user_id>/deactivate', methods=['POST'])
@token_required
@roles_required('admin')               # revoking a provider identity is admin-only
def platform_trainer_deactivate(user_id):
    body = request.json or {}
    payload = {
        'reason': (body.get('reason') or '')[:200],
        # Also tag the account as test data → hidden from every public board/directory at the
        # query layer, not just by the profile-completeness gate.
        'is_test': bool(body.get('is_test')),
    }
    resp = _platform_proxy('POST', f"/api/bridge/trainers/{user_id}/deactivate", json_body=payload)
    if _resp_ok(resp):
        _audit('trainer.deactivate', target=user_id,
               meta={'email': (body.get('email') or ''), 'is_test': payload['is_test'],
                     'reason': payload['reason']})
    return resp


@app.route('/api/platform-users/<user_id>/flag-test', methods=['POST'])
@token_required
@roles_required('admin')
def platform_users_flag_test(user_id):
    """The cheap hide-everywhere switch: mark a platform account as test data (or clear it).
    Public directories/boards filter `is_test` at the query layer, so this removes a demo
    account from every public surface without touching its data."""
    body = request.json or {}
    is_test = bool(body.get('is_test', True))
    resp = _platform_proxy('POST', f"/api/bridge/users/{user_id}/flag-test",
                           json_body={'is_test': is_test})
    if _resp_ok(resp):
        _audit('user.flag_test', target=user_id,
               meta={'email': (body.get('email') or ''), 'is_test': is_test})
    return resp


@app.route('/api/platform-experts', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee = read-only directory (no mutations)
def platform_experts():
    """Experts & trainers directory for the D5 «الخبراء والمدربون» module. Reads the platform's
    experts.py projection (rating + presence) joined with referral / course / student counts.
    An expert == an approved trainer (same person, two hats)."""
    return _platform_proxy('GET', '/api/bridge/experts')

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


@app.route('/api/platform-leads', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_leads():
    """Chat hand-off leads captured on the platform (D1 overview inbox enrichment).
    Thin proxy to the platform bridge; returns 502/503 when the bridge is cold or the
    platform hasn't shipped this endpoint yet — the loader degrades silently."""
    return _platform_proxy('GET', '/api/bridge/leads', params={'status': request.args.get('status') or 'new'})


@app.route('/api/platform-messages', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_messages():
    """Chat hand-off messages captured on the platform (D1 overview inbox enrichment).
    Thin proxy to the platform bridge; degrades silently when unavailable."""
    return _platform_proxy('GET', '/api/bridge/messages', params={'status': request.args.get('status') or 'new'})


def _platform_proxy(method, path, params=None, json_body=None, timeout=12):
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
            timeout=timeout,
        )
    except Exception:
        return jsonify({'error': 'تعذر الاتصال بالمنصة'}), 502
    if r.status_code != 200:
        try:
            body = r.json() if r.content else {}
        except Exception:
            body = {}
        detail = body.get('detail') if isinstance(body, dict) else None
        # FastAPI's `detail` is not always a string: our bridge raises STRUCTURED errors
        # ({error, message, allowed} — e.g. 422 «فئة غير معروفة»), and pydantic raises a LIST of
        # field errors. Surface the human message; never hand the browser the raw object, which
        # renders as «[object Object]» and reads as a dashboard bug instead of a rejected value.
        if isinstance(detail, dict):
            msg = detail.get('message') or detail.get('error')
        elif isinstance(detail, list):
            msg = 'المنصة رفضت البيانات المرسلة'
        else:
            msg = detail
        return jsonify({'error': msg or 'تعذر تنفيذ العملية'}), r.status_code
    return jsonify(r.json() if r.content else {})


def _platform_create_course(c):
    """Mirror a dashboard Course onto the platform as a NATIVE course (so it shows on
    app.elprofessor.net, not just the dashboard ledger). Returns {id, slug} or None on failure."""
    if not PLATFORM_METRICS_SECRET:
        return None
    ctype = 'recorded_paid' if (c.price_egp or 0) > 0 else 'recorded_free'
    payload = {
        'title': c.title,
        'type': ctype,
        'trainer_name': c.trainer_name or '',
        'category': c.category or '',
        'price_egp': c.price_egp or 0,
        'price_usd': c.price_usd or 0,
        'is_active': True,
        'dashboard_course_id': c.id,
    }
    try:
        r = requests.post(
            f"{PLATFORM_API_URL}/api/bridge/courses",
            json=payload,
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=12,
        )
    except Exception as exc:
        app.logger.warning("platform course mirror failed (network): %s", exc)
        return None
    if r.status_code != 200:
        app.logger.warning("platform course mirror failed: HTTP %s — %s", r.status_code, (r.text or '')[:200])
        return None
    try:
        data = r.json()
    except ValueError:
        app.logger.warning("platform course mirror: non-JSON 200 response — %s", (r.text or '')[:200])
        return None
    return {'id': data.get('id'), 'slug': data.get('slug')}


def _platform_update_course(platform_id, fields):
    """Push edits to a linked native course. Returns True on success (best-effort, non-fatal)."""
    if not (PLATFORM_METRICS_SECRET and platform_id and fields):
        return False
    try:
        r = requests.put(
            f"{PLATFORM_API_URL}/api/bridge/courses/{platform_id}",
            json=fields,
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=12,
        )
        if r.status_code == 200:
            return True
        app.logger.warning("platform course edit failed: HTTP %s — %s", r.status_code, (r.text or '')[:200])
    except Exception as exc:
        app.logger.warning("platform course edit failed (network): %s", exc)
    return False


def _platform_delete_course(platform_id):
    """Soft-delete a linked native course (best-effort, non-fatal). Returns True on success."""
    if not (PLATFORM_METRICS_SECRET and platform_id):
        return False
    try:
        r = requests.delete(
            f"{PLATFORM_API_URL}/api/bridge/courses/{platform_id}",
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=12,
        )
        if r.status_code == 200:
            return True
        app.logger.warning("platform course delete failed: HTTP %s — %s", r.status_code, (r.text or '')[:200])
    except Exception as exc:
        app.logger.warning("platform course delete failed (network): %s", exc)
    return False


@app.route('/api/platform-trainer-applications/<application_id>/<action>', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_trainer_decide(application_id, action):
    if action not in ('approve', 'reject'):
        return jsonify({'error': 'إجراء غير معروف'}), 400
    body = request.json or {}
    return _platform_proxy(
        'POST',
        f"/api/bridge/trainer-applications/{application_id}/{action}",
        json_body={'admin_note': body.get('admin_note') or ''},
    )


@app.route('/api/platform-join-requests', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW pending join requests (follow-up)
def platform_join_requests():
    """Section-key join requests captured on the platform (Phase 2). Thin proxy to the platform
    bridge; the admin grants/rejects → the platform flips the user's section key."""
    return _platform_proxy(
        'GET',
        '/api/bridge/join-requests',
        params={'status': request.args.get('status') or 'all',
                'section': request.args.get('section') or ''},
    )


@app.route('/api/platform-join-requests/<request_id>/<action>', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_join_request_decide(request_id, action):
    if action not in ('approve', 'reject'):
        return jsonify({'error': 'إجراء غير معروف'}), 400
    body = request.json or {}
    return _platform_proxy(
        'POST',
        f"/api/bridge/join-requests/{request_id}/decide",
        json_body={'decision': action, 'admin_note': body.get('admin_note') or ''},
    )


@app.route('/api/platform-pending-topics', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW topics pending review
def platform_pending_topics():
    """Member-authored topics awaiting review before they hit the public board (founder review
    2026-07-09). Thin proxy to the platform bridge, filtered to status=pending_review."""
    return _platform_proxy('GET', '/api/bridge/topics', params={'status': 'pending_review'})


@app.route('/api/platform-pending-topics/<topic_id>/<action>', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_pending_topic_decide(topic_id, action):
    """Approve/reject a MEMBER-proposed topic. Must stay on these two routes: approve flips it to
    the public board AND notifies its author, reject marks it rejected — whereas the generic
    PUT/DELETE pair silently skips the notification and hard-deletes the member's topic with its
    comments. The Topics module's «مقترحة من الأعضاء» tab calls this, not the CRUD routes."""
    if action not in ('approve', 'reject'):
        return jsonify({'error': 'إجراء غير معروف'}), 400
    resp = _platform_proxy('POST', f"/api/bridge/topics/{topic_id}/{action}")
    if _resp_ok(resp):
        _audit(f'topic.{action}', target=topic_id)
    return resp


# --------------------------------------------------------------------------- R1 launch-fix inboxes
# Four inflows whose platform bridges existed but had no dashboard row, plus the two brand-new
# bridges (verify queue + live-course reservations). All thin proxies — fulfillment/email stay
# SERVER-SIDE on the platform; the dashboard only forwards the decision.
@app.route('/api/platform-manual-payments', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_manual_payments():
    """Manual (InstaPay/Vodafone) payments awaiting confirmation. Confirm/reject drives grant +
    finance event + customer email on the PLATFORM — never re-implement that here."""
    return _platform_proxy('GET', '/api/bridge/manual-payments',
                           params={'status': request.args.get('status') or 'pending_review'})


@app.route('/api/platform-manual-payments/<payment_id>/<action>', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_manual_payment_decide(payment_id, action):
    if action not in ('confirm', 'reject'):
        return jsonify({'error': 'إجراء غير معروف'}), 400
    body = request.json or {}
    return _platform_proxy('POST', f"/api/bridge/manual-payments/{payment_id}/decide",
                           json_body={'decision': action, 'admin_note': body.get('admin_note') or ''})


@app.route('/api/platform-creative', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_creative():
    """ركن الإبداع works awaiting review (pending_review)."""
    return _platform_proxy('GET', '/api/bridge/creative',
                           params={'status': request.args.get('status') or 'pending_review'})


@app.route('/api/platform-creative/<item_id>/<action>', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_creative_decide(item_id, action):
    if action not in ('approve', 'reject'):
        return jsonify({'error': 'إجراء غير معروف'}), 400
    body = request.json or {}
    return _platform_proxy('POST', f"/api/bridge/creative/{item_id}/decide",
                           json_body={'decision': action, 'note': body.get('admin_note') or ''})


@app.route('/api/platform-knowledge-review', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_knowledge_review():
    """Books/works awaiting review (status=pending_review) — the review-status view that the
    marketplace listing (/platform-knowledge, filtered by rights) does not provide."""
    return _platform_proxy('GET', '/api/bridge/knowledge/review',
                           params={'status': request.args.get('status') or 'pending_review'})


@app.route('/api/platform-knowledge/<item_id>/decide', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_knowledge_decide(item_id):
    body = request.json or {}
    action = body.get('decision') or ''
    if action not in ('approve', 'reject'):
        return jsonify({'error': 'إجراء غير معروف'}), 400
    return _platform_proxy('POST', f"/api/bridge/knowledge/{item_id}/decide",
                           json_body={'decision': action, 'note': body.get('admin_note') or ''})


@app.route('/api/platform-verify', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_verify_queue():
    """Answer-verification requests with no available expert (routed_admin) — the product core
    loop. The founder reassigns each to a specific approved expert."""
    return _platform_proxy('GET', '/api/bridge/verify',
                           params={'status': request.args.get('status') or 'routed_admin'})


@app.route('/api/platform-verify/<req_id>/reassign', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_verify_reassign(req_id):
    body = request.json or {}
    return _platform_proxy('POST', f"/api/bridge/verify/{req_id}/reassign",
                           json_body={'expert_email': body.get('expert_email') or ''})


@app.route('/api/platform-courses/<slug>/reservations', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_course_reservations(slug):
    """Seat roster for a live course (who reserved, status)."""
    return _platform_proxy('GET', f"/api/bridge/courses/{slug}/reservations",
                           params={'status': request.args.get('status') or 'all'})


@app.route('/api/platform-leads/<lead_id>/resolve', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_lead_resolve(lead_id):
    return _platform_proxy('POST', f"/api/bridge/leads/{lead_id}/resolve")


@app.route('/api/platform-messages/<message_id>/resolve', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_message_resolve(message_id):
    return _platform_proxy('POST', f"/api/bridge/messages/{message_id}/resolve")


@app.route('/api/platform-program-requests', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW pending program requests (follow-up)
def platform_program_requests():
    return _platform_proxy(
        'GET',
        '/api/bridge/program-requests',
        params={'status': request.args.get('status') or 'all'},
    )


@app.route('/api/platform-program-requests/stats', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_program_requests_stats():
    """Aggregated course-demand for the D4 «أكثر الدورات طلبًا» panel:
    {stats:[{title,count}], count}. (`/stats` is a static segment so it never collides
    with the two-segment `/<request_id>/<action>` decide route below.)"""
    return _platform_proxy('GET', '/api/bridge/program-requests/stats')


@app.route('/api/platform-program-requests/<request_id>/<action>', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
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


# --- «عروض الأسعار» (Course price bids): a buyer proposed a price for a bid-enabled course;
# the founder approves / rejects / counters it here. Proxied to the platform via METRICS_SECRET. ---
@app.route('/api/platform-course-offers', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_course_offers():
    return _platform_proxy(
        'GET',
        '/api/bridge/course-offers',
        params={'status': request.args.get('status') or 'pending'},
    )


@app.route('/api/platform-course-offers/<offer_id>/decide', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_course_offer_decide(offer_id):
    body = request.json or {}
    decision = (body.get('decision') or '').strip()
    if decision not in ('approve', 'reject', 'counter'):
        return jsonify({'error': 'القرار لازم يكون approve أو reject أو counter'}), 400
    json_body = {'decision': decision}
    if body.get('amount') is not None:
        try:
            json_body['amount'] = float(body.get('amount'))
        except (TypeError, ValueError):
            return jsonify({'error': 'مبلغ غير صالح'}), 400
    return _platform_proxy('POST', f"/api/bridge/course-offers/{offer_id}/decide", json_body=json_body)


# --- Native platform courses + their bid settings («اعرض سعرك» on/off per course). The dashboard's
# own «الكتالوج» is a separate legacy LMS-synced store; these target the REAL native courses. ---
@app.route('/api/platform-courses', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_courses_list():
    return _platform_proxy('GET', '/api/bridge/courses')


@app.route('/api/platform-library/ingest-folder', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_library_ingest_folder():
    """استيراد مكتبة قانونية من فولدر Google Drive إلى كوربوس الـRAG (صيغ/مذكرات/قوانين)."""
    body = request.json or {}
    fid = (body.get('folder_id') or '').strip()
    if not fid:
        return jsonify({'error': 'folder_id مطلوب'}), 400
    json_body = {
        'folder_id': fid,
        'category': (body.get('category') or 'memo_template').strip(),
        'country': (body.get('country') or 'egypt').strip(),
        'max_files': int(body.get('max_files') or 30),
    }
    return _platform_proxy('POST', '/api/bridge/library/ingest-drive-folder', json_body=json_body)


@app.route('/api/platform-courses/<course_id>/approve', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_course_approve(course_id):
    """اعتماد دورة «بانتظار الاعتماد» (مثلاً كتاب اتحوّل دورة) → تروح live في «الدورات»."""
    resp = _platform_proxy('POST', f"/api/bridge/courses/{course_id}/approve")
    if _resp_ok(resp):
        _audit('course.approve', target=course_id)
    return resp


@app.route('/api/platform-courses/<course_id>/reject', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_course_reject(course_id):
    resp = _platform_proxy('POST', f"/api/bridge/courses/{course_id}/reject")
    if _resp_ok(resp):
        _audit('course.reject', target=course_id)
    return resp


@app.route('/api/platform-courses/<course_id>/bid', methods=['PUT'])
@token_required
@roles_required('admin', 'employee')
def platform_course_set_bid(course_id):
    body = request.json or {}
    json_body = {}
    if 'bid_enabled' in body:
        json_body['bid_enabled'] = bool(body.get('bid_enabled'))
    if body.get('segment_pricing_mode') in ('discount_only', 'full'):
        json_body['segment_pricing_mode'] = body.get('segment_pricing_mode')
    if not json_body:
        return jsonify({'error': 'لا يوجد تغيير صالح'}), 400
    return _platform_proxy('PUT', f"/api/bridge/courses/{course_id}", json_body=json_body)


@app.route('/api/platform-courses/<course_id>', methods=['PUT'])
@token_required
@roles_required('admin', 'employee')
def platform_course_edit(course_id):
    """Full edit of a native course from the dashboard (title/desc/price/instructor/level/active)."""
    body = request.json or {}
    json_body = {}
    for key in ('title', 'short_description', 'description', 'instructor_name', 'level', 'category'):
        if isinstance(body.get(key), str):
            json_body[key] = body.get(key)
    if 'is_active' in body:
        json_body['is_active'] = bool(body.get('is_active'))
    if 'bid_enabled' in body:
        json_body['bid_enabled'] = bool(body.get('bid_enabled'))
    for key in ('price_egp', 'price_usd'):
        if body.get(key) is not None:
            try:
                json_body[key] = float(body.get(key))
            except (TypeError, ValueError):
                return jsonify({'error': 'سعر غير صالح'}), 400
    if not json_body:
        return jsonify({'error': 'لا يوجد تغيير صالح'}), 400
    return _platform_proxy('PUT', f"/api/bridge/courses/{course_id}", json_body=json_body)


@app.route('/api/platform-courses/<course_id>', methods=['DELETE'])
@token_required
@roles_required('admin', 'employee')
def platform_course_delete(course_id):
    """Delete a native course from the dashboard (soft-delete → disappears from the platform)."""
    return _platform_proxy('DELETE', f"/api/bridge/courses/{course_id}")


@app.route('/api/platform-courses/<course_id>/detail', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_course_detail(course_id):
    """A native course + its episodes (for the dashboard video manager)."""
    return _platform_proxy('GET', f"/api/bridge/courses/{course_id}/detail")


@app.route('/api/platform-courses/<course_id>/videos', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_course_add_video(course_id):
    """Add an episode (Drive/YouTube link) to a native course, optionally inside a
    curriculum section (section_title/section_order group the lecture in the tree)."""
    body = request.json or {}
    json_body = {
        'title': (body.get('title') or '').strip(),
        'video_url': (body.get('video_url') or '').strip(),
        'youtube_url': (body.get('youtube_url') or '').strip(),
        'is_preview': bool(body.get('is_preview')),
    }
    if isinstance(body.get('section_title'), str):
        json_body['section_title'] = body.get('section_title').strip()
    if body.get('section_order') is not None:
        try:
            json_body['section_order'] = int(body.get('section_order'))
        except (TypeError, ValueError):
            pass
    if body.get('duration_seconds') is not None:
        try:
            json_body['duration_seconds'] = int(body.get('duration_seconds'))
        except (TypeError, ValueError):
            pass
    return _platform_proxy('POST', f"/api/bridge/courses/{course_id}/videos", json_body=json_body)


@app.route('/api/platform-courses/<course_id>/videos/<video_id>', methods=['DELETE'])
@token_required
@roles_required('admin', 'employee')
def platform_course_delete_video(course_id, video_id):
    return _platform_proxy('DELETE', f"/api/bridge/courses/{course_id}/videos/{video_id}")


@app.route('/api/platform-courses/<course_id>/sections', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_course_add_section(course_id):
    """Create/rename/assign a curriculum section (groups lectures) on a native course.
    from_title → rename+reorder that section; video_ids → stamp section onto those lectures;
    neither → a logical placeholder that materializes when a lecture is added with this title."""
    body = request.json or {}
    json_body = {'title': (body.get('title') or '').strip()}
    if not json_body['title']:
        return jsonify({'error': 'عنوان القسم مطلوب'}), 400
    try:
        json_body['order'] = int(body.get('order') or 0)
    except (TypeError, ValueError):
        json_body['order'] = 0
    if isinstance(body.get('from_title'), str):
        json_body['from_title'] = body.get('from_title')
    if isinstance(body.get('video_ids'), list):
        json_body['video_ids'] = [str(x) for x in body.get('video_ids')]
    return _platform_proxy('POST', f"/api/bridge/courses/{course_id}/sections", json_body=json_body)


@app.route('/api/platform-courses/<course_id>/lessons/<lesson_id>/questions', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_course_lesson_questions(course_id, lesson_id):
    """Add/replace the quiz of a Titch curriculum lesson («علّمني»). Body:
    {questions:[{question,options,answer_index}], mode:'replace'|'append'}."""
    body = request.json or {}
    questions = body.get('questions')
    if not isinstance(questions, list) or not questions:
        return jsonify({'error': 'الأسئلة مطلوبة'}), 400
    mode = body.get('mode') if body.get('mode') in ('replace', 'append') else 'replace'
    return _platform_proxy(
        'POST',
        f"/api/bridge/courses/{course_id}/lessons/{lesson_id}/questions",
        json_body={'questions': questions, 'mode': mode},
    )


@app.route('/api/platform-schedules', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_schedules():
    """Live courses + schedules to review/confirm trainer appointments."""
    return _platform_proxy('GET', '/api/bridge/schedules')


@app.route('/api/platform-courses/generate', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_course_generate():
    """«أنشئ الدورة بـ Titch» — generate a native course curriculum from a brief/material."""
    body = request.json or {}
    json_body = {
        'title': (body.get('title') or '').strip(),
        'material': body.get('material') or '',
        'mission': body.get('mission') or '',
        'type': body.get('type') or 'recorded_paid',
        'instructor_name': (body.get('instructor_name') or '').strip(),
    }
    if not json_body['title']:
        return jsonify({'error': 'العنوان مطلوب'}), 400
    if body.get('price_egp') is not None:
        try:
            json_body['price_egp'] = float(body.get('price_egp'))
        except (TypeError, ValueError):
            return jsonify({'error': 'سعر غير صالح'}), 400
    return _platform_proxy('POST', '/api/bridge/courses/generate', json_body=json_body)


@app.route('/api/platform-knowledge', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_knowledge_list():
    """Knowledge-marketplace items (سوق المعرفة) for review/edit/remove."""
    return _platform_proxy('GET', '/api/bridge/knowledge',
                           params={'rights': request.args.get('rights') or ''})


@app.route('/api/platform-knowledge/<item_id>', methods=['PUT'])
@token_required
@roles_required('admin', 'employee')
def platform_knowledge_edit(item_id):
    body = request.json or {}
    json_body = {}
    for key in ('title', 'description'):
        if isinstance(body.get(key), str):
            json_body[key] = body.get(key)
    if 'is_active' in body:
        json_body['is_active'] = bool(body.get('is_active'))
    if 'bid_enabled' in body:
        json_body['bid_enabled'] = bool(body.get('bid_enabled'))
    if body.get('price_egp') is not None:
        try:
            json_body['price_egp'] = float(body.get('price_egp'))
        except (TypeError, ValueError):
            return jsonify({'error': 'سعر غير صالح'}), 400
    if not json_body:
        return jsonify({'error': 'لا يوجد تغيير صالح'}), 400
    return _platform_proxy('PUT', f"/api/bridge/knowledge/{item_id}", json_body=json_body)


@app.route('/api/platform-knowledge/<item_id>', methods=['DELETE'])
@token_required
@roles_required('admin', 'employee')
def platform_knowledge_delete(item_id):
    return _platform_proxy('DELETE', f"/api/bridge/knowledge/{item_id}")


# --- «إضافة كتاب» لسوق المعرفة (bridge /api/bridge/books) ---
# الأدمن يضيف كتابًا من اللوحة → يُنشأ على المنصة بنفس شكل عناصر المتجر (Store/knowledge)
# فيظهر فورًا في قائمة «سوق المعرفة» هنا وفي متجر المنصة. الجسر السرّي server-side فقط.
@app.route('/api/platform-books', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_books_list():
    """قائمة كتب سوق المعرفة عبر الجسر (قراءة فقط)."""
    return _platform_proxy('GET', '/api/bridge/books')


@app.route('/api/platform-books', methods=['POST'])
@token_required
@roles_required('admin')
def platform_books_create():
    """إنشاء كتاب في سوق المعرفة. العقد المشترك:
    {title, author?, description?, price?, currency?, file_url, cover_url?, is_active}."""
    d = request.json or {}
    title = (d.get('title') or '').strip()
    file_url = (d.get('file_url') or '').strip()
    if not title:
        return jsonify({'error': 'عنوان الكتاب مطلوب'}), 400
    if not file_url:
        return jsonify({'error': 'رابط ملف الكتاب (PDF) مطلوب'}), 400
    try:
        price = float(d.get('price') or 0)
    except (TypeError, ValueError):
        return jsonify({'error': 'سعر غير صالح'}), 400
    if price < 0:
        return jsonify({'error': 'السعر لا يكون سالبًا'}), 400
    payload = {
        'title': title[:300],
        'author': (d.get('author') or '').strip()[:200],
        'description': (d.get('description') or '').strip()[:2000],
        'price': price,
        'currency': ((d.get('currency') or 'EGP').strip() or 'EGP')[:8],
        'file_url': file_url[:1000],
        'cover_url': (d.get('cover_url') or '').strip()[:1000],
        'is_active': bool(d.get('is_active', True)),
    }
    resp = _platform_proxy('POST', '/api/bridge/books', json_body=payload)
    status = resp[1] if isinstance(resp, tuple) else 200
    if status == 200:
        _audit('book.create', target=title[:80],
               meta={'price': payload['price'], 'currency': payload['currency']})
    return resp


@app.route('/api/platform-courses/<course_id>/schedule', methods=['PUT'])
@token_required
@roles_required('admin', 'employee')
def platform_course_schedule(course_id):
    """Confirm/edit a live course's schedule (zoom/dates/seats) from the dashboard."""
    body = request.json or {}
    json_body = {}
    for key in ('zoom_link', 'start_date', 'end_date', 'timezone', 'registration_deadline'):
        if isinstance(body.get(key), str):
            json_body[key] = body.get(key).strip()
    if body.get('max_seats') is not None:
        try:
            json_body['max_seats'] = int(body.get('max_seats'))
        except (TypeError, ValueError):
            return jsonify({'error': 'عدد المقاعد غير صالح'}), 400
    if 'confirmed' in body:
        json_body['confirmed'] = bool(body.get('confirmed'))
    if not json_body:
        return jsonify({'error': 'لا يوجد تغيير صالح'}), 400
    return _platform_proxy('PUT', f"/api/bridge/courses/{course_id}/schedule", json_body=json_body)


# --- «الدليل» (Tutorials): proxy to the platform guide so the team manages it here ---
# Read goes to the PUBLIC platform endpoint (with the secret + include_unpublished so the
# dashboard sees drafts too); writes go to the SECRET bridge. The METRICS_SECRET is sent
# server-side ONLY — the browser never sees it.
@app.route('/api/tutorials', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW the guide (read-only)
@module_required('tutorials')          # D9: admin can revoke per-role module access
def tutorials_list():
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط الربط بعد'}), 503
    try:
        r = requests.get(
            f"{PLATFORM_API_URL}/api/tutorials",
            params={'include_unpublished': 'true'},
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=12,
        )
    except Exception:
        return jsonify({'error': 'تعذر الاتصال بالمنصة'}), 502
    if r.status_code != 200:
        return jsonify({'error': 'تعذر جلب الدليل'}), 502
    return jsonify(r.json() if r.content else [])


@app.route('/api/tutorials', methods=['POST'])
@token_required
@roles_required('admin')
def tutorials_create():
    body = request.json or {}
    return _platform_proxy('POST', '/api/bridge/tutorials', json_body={
        'title': (body.get('title') or '').strip(),
        'section': (body.get('section') or '').strip(),
        'body': body.get('body') or '',
        'video_url': (body.get('video_url') or '').strip(),
        'order': int(body.get('order') or 0),
        'is_published': bool(body.get('is_published', True)),
    })


@app.route('/api/tutorials/<tutorial_id>', methods=['PUT'])
@token_required
@roles_required('admin')
def tutorials_update(tutorial_id):
    body = request.json or {}
    payload = {}
    for key in ('title', 'section', 'body', 'video_url'):
        if key in body:
            payload[key] = body.get(key)
    if 'order' in body:
        payload['order'] = int(body.get('order') or 0)
    if 'is_published' in body:
        payload['is_published'] = bool(body.get('is_published'))
    return _platform_proxy('PUT', f"/api/bridge/tutorials/{tutorial_id}", json_body=payload)


@app.route('/api/tutorials/<tutorial_id>', methods=['DELETE'])
@token_required
@roles_required('admin')
def tutorials_delete(tutorial_id):
    return _platform_proxy('DELETE', f"/api/bridge/tutorials/{tutorial_id}")


# --- «المواضيع» (Topics): research/draft -> review AI draft -> publish ----------
# Mirrors the tutorials proxy above. The team researches a topic here (create =
# DRAFT + AI draft), reviews the returned ai_answer, then publishes it to the
# public board. Reads go through the SECRET bridge (lists drafts too); writes go
# to the SECRET bridge as well. METRICS_SECRET is sent server-side ONLY — the
# browser never sees it.
@app.route('/api/platform-topics', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW topics (incl drafts)
@module_required('topics')             # D9: admin can revoke per-role module access
def platform_topics_list():
    return _platform_proxy('GET', '/api/bridge/topics')


@app.route('/api/platform-topics', methods=['POST'])
@token_required
@roles_required('admin', 'employee')   # research/draft a new topic
def platform_topics_create():
    body = request.json or {}
    payload = {
        'title': (body.get('title') or '').strip(),
        'question': (body.get('question') or '').strip(),
        'specialty': (body.get('specialty') or '').strip(),
    }
    # Optional source label (news|expert|idea|human) — only forward a valid value so the
    # bridge never 400s on a stray string; it defaults to 'human' when omitted.
    src = (body.get('source') or '').strip()
    if src in ('news', 'expert', 'idea', 'human'):
        payload['source'] = src
    return _platform_proxy('POST', '/api/bridge/topics', json_body=payload)


@app.route('/api/platform-topics/<topic_id>/publish', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_topics_publish(topic_id):
    return _platform_proxy('POST', f"/api/bridge/topics/{topic_id}/publish")


@app.route('/api/platform-topics/<topic_id>', methods=['PUT'])
@token_required
@roles_required('admin', 'employee')
def platform_topics_update(topic_id):
    body = request.json or {}
    payload = {}
    # source/status/merged_article added so the dashboard can label the source, route a
    # topic between the internal sections (draft/open/merged/published), and store a
    # merged article. The bridge validates source & status against its own enums.
    # linked_article_id/article_made_at added (FIX1) so «اعمل مقال» can PERSIST the topic↔article
    # link on the platform → the topic then shows «✓ له مقال» across refreshes (non-empty id links
    # + auto-stamps article_made_at; "" unlinks). The bridge (BridgeTopicPatch) validates them.
    for key in ('title', 'question', 'specialty', 'ai_answer', 'source', 'status', 'merged_article',
                'linked_article_id', 'article_made_at'):
        if key in body:
            payload[key] = body.get(key)
    return _platform_proxy('PUT', f"/api/bridge/topics/{topic_id}", json_body=payload)


@app.route('/api/platform-topics/<topic_id>', methods=['DELETE'])
@token_required
@roles_required('admin', 'employee')
def platform_topics_delete(topic_id):
    return _platform_proxy('DELETE', f"/api/bridge/topics/{topic_id}")


# --- «الفئة» (segment) on a topic ------------------------------------------------
# The founder's segmentation ask: every topic belongs to ONE audience lane (خريجون جدد /
# النيابة الإدارية / جنائي / طلاب حقوق …) so each group finds its own conversations.
#
# ⛔ THE VOCABULARY IS OWNED BY THE PLATFORM (routes/topics.TOPIC_SEGMENTS) AND IS NEVER
#    REDEFINED HERE. The dashboard reads it from /api/platform-topic-segments below and posts
#    back the `id` it got. A second list in this repo is how the two sides drift apart.
#
# ⚠️ The body key MUST be `segment`. The platform's BridgeSegmentIn reads `segment` only, and an
#    empty/absent value is its EXPLICIT «clear the human choice, hand the lane back to the
#    classifier» signal — so the old `target_audience` key was dropped by pydantic, arrived as
#    "", WIPED the stored lane and still answered 200. Nothing about that failure was visible.
#    `target_audience` is a different (older, news) axis and is not writable here at all.
@app.route('/api/platform-topic-segments', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
@module_required('topics')
def platform_topic_segments():
    """The LOCKED «الفئات» vocabulary + live counts, straight from the platform:
    [{id, label, count}]. The dashboard's dropdown is built from THIS — never from a local list."""
    return _platform_proxy('GET', '/api/bridge/topics/segments')


@app.route('/api/platform-topics/<topic_id>/segment', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
@module_required('topics')
def platform_topics_set_segment(topic_id):
    body = request.json or {}
    # Accept the id under any of the keys the UI has historically sent; forward ONE key.
    seg = (body.get('segment') or body.get('target_audience')
           or body.get('audience') or '').strip()[:60]
    if not seg:
        return jsonify({'error': 'اختر الفئة المستهدفة أولًا'}), 400
    resp = _platform_proxy('POST', f"/api/bridge/topics/{topic_id}/segment",
                           json_body={'segment': seg})
    # A value outside the locked vocabulary comes back 422 with the platform's own Arabic
    # message (surfaced by _platform_proxy) — it is NOT audited and NOT reported as success.
    if _resp_ok(resp):
        _audit('topic.set_segment', target=topic_id, meta={'segment': seg})
    return resp


# --- «اعمل مقال» (generate an SEO article FROM a topic): the platform LLM AUTHORS a fresh
# article (new headline/excerpt/body — NOT a copy of the topic text). This is a synchronous
# LLM generation (~600-1000 words) so it needs a longer timeout than the shared 12s proxy;
# hence a dedicated handler rather than _platform_proxy. On success returns the structured
# article for the dashboard to store as a CMS draft. On LLM failure surfaces an honest error
# (503 ai_unavailable / 502 generation_failed) — never a fake success and never the topic text.
@app.route('/api/platform-topics/<topic_id>/generate-article', methods=['POST'])
@token_required
@roles_required('admin')               # LLM generation + downstream CMS create are admin-gated
def platform_topics_generate_article(topic_id):
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط الربط بعد'}), 503
    try:
        r = requests.post(
            f"{PLATFORM_API_URL}/api/bridge/topics/{topic_id}/generate-article",
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            # Must exceed the platform's own DeepSeek timeout (90s for deepseek-chat) so a slow
            # 600-1000-word generation isn't guillotined here at 60s while the platform still
            # succeeds — which would burn the LLM call and return a false failure to the operator.
            timeout=120,
        )
    except Exception:
        return jsonify({'error': 'تعذّر الاتصال بالمنصة'}), 502
    if r.status_code != 200:
        body = r.json() if r.content else {}
        detail = body.get('detail') if isinstance(body, dict) else None
        # the platform's error `detail` is a dict {error, message, cause} — surface its message
        if isinstance(detail, dict):
            msg = detail.get('message') or detail.get('error')
        elif isinstance(detail, str):
            msg = detail
        else:
            msg = None
        return jsonify({'error': msg or 'تعذّر توليد المقال بالذكاء'}), r.status_code
    return jsonify(r.json() if r.content else {})


# --- «لوحة تحليل AI» for the Topics module: top topics by engagement, counts by
# category/source, and the categories most in demand (from chat). Reads the platform's
# real aggregation via the SECRET bridge — no fabricated numbers here.
@app.route('/api/platform-topics-analysis', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW the analysis panel
@module_required('topics')             # D9: admin can revoke per-role module access
def platform_topics_analysis():
    try:
        limit = int(request.args.get('limit') or 10)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(50, limit))
    return _platform_proxy('GET', '/api/bridge/topics/analysis', params={'limit': limit})


# --- «آراء بانتظار المراجعة» (Opinions/comments moderation): users comment on topics; the
# platform auto-approves on-topic, non-abusive opinions and flags the rest as `pending` for
# human review here. GET lists them (with the AI-moderation verdict); approve/reject act on
# them. Reads + writes go through the SECRET bridge (server-side secret only).
@app.route('/api/platform-opinions', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW + moderate opinions
@module_required('topics')             # D9: admin can revoke per-role module access
def platform_opinions_list():
    status = (request.args.get('status') or 'pending').strip()
    if status not in ('pending', 'all', 'approved', 'rejected'):
        status = 'pending'
    return _platform_proxy('GET', '/api/bridge/opinions', params={'status': status})


@app.route('/api/platform-opinions/<opinion_id>/approve', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_opinions_approve(opinion_id):
    return _platform_proxy('POST', f"/api/bridge/opinions/{opinion_id}/approve")


@app.route('/api/platform-opinions/<opinion_id>/reject', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_opinions_reject(opinion_id):
    return _platform_proxy('POST', f"/api/bridge/opinions/{opinion_id}/reject")


@app.route('/api/platform-opinions/<opinion_id>', methods=['DELETE'])
@token_required
@roles_required('admin', 'employee')
@module_required('topics')
def platform_opinions_delete(opinion_id):
    """Editors delete a comment on the platform."""
    return _platform_proxy('DELETE', f"/api/bridge/opinions/{opinion_id}")


@app.route('/api/platform-opinions/<opinion_id>/reply', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
@module_required('topics')
def platform_opinions_reply(opinion_id):
    """Editors reply to a comment (manual text, or AI-drafted when {ai:true} with no text).
    Longer timeout because the AI draft round-trips through the platform's LLM."""
    body = request.get_json(silent=True) or {}
    return _platform_proxy('POST', f"/api/bridge/opinions/{opinion_id}/reply",
                           json_body={'reply': body.get('reply', ''), 'ai': bool(body.get('ai'))}, timeout=60)


# --- «تحليل التعليقات و«استنتاجات»» (Opinions analytics/insights): real aggregation from the
# platform — pending/approved/rejected counts, top topics by APPROVED-comment count, by-category
# distribution, and a best-effort AI «استنتاجات» summary (honest empty state when unavailable).
# Thin proxy over the SECRET, secret-guarded bridge endpoint (server-side secret only).
@app.route('/api/platform-opinions-analysis', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW the analytics panel
@module_required('topics')             # D9: admin can revoke per-role module access
def platform_opinions_analysis():
    try:
        limit = int(request.args.get('limit') or 10)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(50, limit))
    # summarize: default true (also run the AI «استنتاجات» pass); accept common falsy strings to skip it.
    raw = (request.args.get('summarize') or '').strip().lower()
    summarize = 'false' if raw in ('0', 'false', 'no', 'off') else 'true'
    return _platform_proxy('GET', '/api/bridge/opinions/analysis',
                           params={'limit': limit, 'summarize': summarize})


# =========================================================================== «السوق» (MARKET)
# The founder's #1 competitive feature had NO management surface at all: the nav item was
# removed on 2026-07-20 as a lying zero, and no market bridge endpoint existed on either side.
# These are the dashboard's read/act proxies over the platform's market bridge. Same rule as
# every block above: the METRICS_SECRET is sent SERVER-SIDE only, the browser never sees it.
#
# Lanes mirror the live market's `kind` EXACTLY as the bridge declares them
# (marketplace.bridge_market_requests: request|public_service|course_request|training_offer|all):
#   request (خبرة) · course_request (دورة/تدريب) · public_service (خدمة للجمهور) ·
#   training_offer (مدرّب بيعرض خدمته — عرض لا طلب).
# `knowledge` is NOT one of them: it is a members-board lane over `knowledge_items`, a collection
# the market bridge never reads — keeping it here bought a permanent «٠» tab and, once the query
# name is correct, a hard 422. `need_kind` is the demand classification the chat captured.
_MARKET_KINDS = ('request', 'course_request', 'public_service', 'training_offer', 'all')
_MARKET_STATUSES = ('open', 'matched', 'closed', 'all')


def _market_proxy(method, path, params=None, json_body=None):
    """_platform_proxy + one distinction that matters for a bridge shipping concurrently:
    a 404 means «the market bridge isn't deployed on the platform yet», not «this failed».
    Tagging it lets the dashboard render an honest «قيد النشر» state instead of an error that
    looks like a bug. Anything else passes through unchanged."""
    resp = _platform_proxy(method, path, params=params, json_body=json_body)
    if isinstance(resp, tuple) and int(resp[1]) == 404:
        return jsonify({'error': 'جسر «السوق» لم يُنشر على المنصة بعد',
                        'bridge_missing': True}), 404
    return resp


@app.route('/api/platform-market-requests', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW the board (decisions are admin-only)
def platform_market_requests():
    """The live market board, management view: every lane, every status, full PII (the platform
    serializes with is_admin=True) plus offer counts. Filters are forwarded, never re-implemented
    here — the platform owns what a lane means."""
    kind = (request.args.get('kind') or 'all').strip()
    if kind not in _MARKET_KINDS:
        kind = 'all'
    status = (request.args.get('status') or 'all').strip()
    if status not in _MARKET_STATUSES:
        status = 'all'
    try:
        limit = int(request.args.get('limit') or 200)
    except (TypeError, ValueError):
        limit = 200
    # The bridge's query parameter is `lane`, not `kind` — FastAPI silently IGNORES an unknown
    # query name, so `kind=` filtered nothing and every lane came back as «all» (masked only
    # because the browser re-filters client-side, and broken the moment the list is paged).
    # We keep accepting `?kind=` inbound; only the outbound name changes.
    params = {'lane': kind, 'status': status, 'limit': max(1, min(500, limit))}
    need_kind = (request.args.get('need_kind') or '').strip()[:40]
    if need_kind and need_kind != 'all':
        params['need_kind'] = need_kind
    return _market_proxy('GET', '/api/bridge/market/requests', params=params)


@app.route('/api/platform-market-requests/<request_id>', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_market_request_detail(request_id):
    """One request + the offers bid on it (who bid, how much, ETA, accepted/declined)."""
    return _market_proxy('GET', f"/api/bridge/market/requests/{request_id}")


@app.route('/api/platform-market-requests/<request_id>/close', methods=['POST'])
@token_required
@roles_required('admin')               # closing someone's request is a real, visible act
def platform_market_request_close(request_id):
    body = request.json or {}
    # The platform's model is BridgeMarketClose{by, reason} — it stores `closed_by`/`closed_reason`
    # from exactly those two. `admin_note` was an invented key: pydantic dropped it, so the close
    # succeeded while the operator's note vanished and `closed_by` recorded the literal "dashboard".
    note = (body.get('reason') or body.get('admin_note') or '')[:300]
    resp = _market_proxy('POST', f"/api/bridge/market/requests/{request_id}/close",
                         json_body={'by': _actor_email(), 'reason': note})
    if _resp_ok(resp):
        _audit('market.close_request', target=request_id, meta={'note': note})
    return resp


@app.route('/api/platform-market-requests/<request_id>/hide', methods=['POST'])
@token_required
@roles_required('admin')
def platform_market_request_hide(request_id):
    """Hide / un-hide a request on every public board.

    MODERATION, NOT DELETION and NOT a test tag: `hidden` is the switch the platform actually
    enforces end-to-end (_public_gate excludes it, get_request 404s non-owners, create_offer
    refuses bids on it) and it is reversible + attributed. The old button posted to
    `/flag-test`, a route that does not exist on the platform — per-request `is_test` is owned
    by the batch sweep (POST /api/bridge/flag-test-data), keyed on the owner's email — so every
    click 404'd and the UI blamed an «undeployed bridge» that was in fact deployed."""
    body = request.json or {}
    hidden = bool(body.get('hidden', True))
    resp = _market_proxy('POST', f"/api/bridge/market/requests/{request_id}/hide",
                         json_body={'hidden': hidden, 'by': _actor_email(),
                                    'reason': (body.get('reason') or '')[:300]})
    if _resp_ok(resp):
        _audit('market.hide_request', target=request_id, meta={'hidden': hidden})
    return resp


@app.route('/api/platform-market-demand', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_market_demand():
    """«الطلب الحقيقي» — the founder's decision surface: aggregated demand grouped by need kind
    (+ specialty), with the courses that repeated demand suggests building next. This is the
    join the dashboard never had: the old «الطلب على الدورات» panel read a legacy collection
    the market never writes to, plus a 40-row chat sample."""
    try:
        days = int(request.args.get('days') or 90)
    except (TypeError, ValueError):
        days = 90
    return _market_proxy('GET', '/api/bridge/market/demand',
                         params={'days': max(1, min(365, days))})


# --- «أتمتة المقالات» (Articles automation): one daily AI run fills «المقالات» on the platform
# with DRAFTS (1 platform explainer + a few news-derived analyses) that the founder approves here.
@app.route('/api/platform-articles', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW article drafts
def platform_articles_list():
    status = (request.args.get('status') or '').strip()
    return _platform_proxy('GET', '/api/bridge/articles', params={'status': status} if status else None)


@app.route('/api/platform-articles/daily-run', methods=['POST'])
@token_required
@roles_required('admin')               # only admin triggers a generation run
def platform_articles_daily_run():
    body = request.json or {}
    # Presence check (not `or`) so an explicit 0 is respected — the platform allows topics=0 to
    # disable topic derivation; `int(x or 3)` would silently coerce a requested 0 back to the default.
    return _platform_proxy('POST', '/api/bridge/content/daily-run', json_body={
        'articles': int(body['articles']) if body.get('articles') is not None else 3,
        'topics': int(body['topics']) if body.get('topics') is not None else 2,
        'publish': bool(body.get('publish') or False),
    })


@app.route('/api/platform-articles/<article_id>/publish', methods=['POST'])
@token_required
@roles_required('admin')
def platform_articles_publish(article_id):
    return _platform_proxy('POST', f"/api/bridge/articles/{article_id}/publish")


@app.route('/api/platform-articles/<article_id>/unpublish', methods=['POST'])
@token_required
@roles_required('admin')
def platform_articles_unpublish(article_id):
    return _platform_proxy('POST', f"/api/bridge/articles/{article_id}/unpublish")


@app.route('/api/platform-articles/<article_id>', methods=['DELETE'])
@token_required
@roles_required('admin')
def platform_articles_delete(article_id):
    return _platform_proxy('DELETE', f"/api/bridge/articles/{article_id}")


# --- «الأخبار» (News): curated legal-news feed -> review our-voice summary -> publish.
# Mirrors the topics/tutorials proxies above. Reads + writes both go through the
# SECRET bridge (so the dashboard sees drafts too). The METRICS_SECRET is sent
# server-side ONLY — the browser never sees it. Plus per-country RSS sources +
# per-club keywords curation via /api/bridge/news-sources.
@app.route('/api/platform-news', methods=['GET'])
@token_required
@roles_required('admin', 'employee')   # employee may VIEW news (incl drafts)
def platform_news_list():
    return _platform_proxy('GET', '/api/bridge/news')


# Map the dashboard UI's `sources:[{name|title,url}]` list to the platform news contract
# (source_name + source_url for the primary, extra_sources for the rest).
def _split_news_sources(raw):
    items = []
    for s in (raw or []):
        if not isinstance(s, dict):
            continue
        name = (s.get('name') or s.get('title') or '').strip()
        url = (s.get('url') or '').strip()
        if url:
            items.append({'name': name, 'url': url})
    primary = items[0] if items else {'name': '', 'url': ''}
    return primary.get('name', ''), primary.get('url', ''), items[1:]


@app.route('/api/platform-news', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def platform_news_create():
    body = request.json or {}
    name, url, extra = _split_news_sources(body.get('sources'))
    return _platform_proxy('POST', '/api/bridge/news', json_body={
        'title': (body.get('title') or '').strip(),
        'summary': (body.get('summary') or '').strip(),
        'body': (body.get('body') or '').strip(),
        'country': (body.get('country') or '').strip(),
        'specialty': (body.get('specialty') or '').strip(),
        'source_name': name,
        'source_url': url,
        'extra_sources': extra,
        # news auto-publishes by default; honor an explicit is_published=false (draft)
        'publish': bool(body.get('is_published', True)),
    })


@app.route('/api/platform-news/<news_id>', methods=['PUT'])
@token_required
@roles_required('admin', 'employee')
def platform_news_update(news_id):
    body = request.json or {}
    payload = {}
    for key in ('title', 'summary', 'body', 'country', 'specialty'):
        if key in body:
            payload[key] = body.get(key)
    if 'sources' in body:
        name, url, extra = _split_news_sources(body.get('sources'))
        payload['source_name'] = name
        payload['source_url'] = url
        payload['extra_sources'] = extra
    if 'is_published' in body:
        payload['status'] = 'published' if bool(body.get('is_published')) else 'draft'
    return _platform_proxy('PUT', f"/api/bridge/news/{news_id}", json_body=payload)


@app.route('/api/platform-news/<news_id>', methods=['DELETE'])
@token_required
@roles_required('admin', 'employee')
def platform_news_delete(news_id):
    return _platform_proxy('DELETE', f"/api/bridge/news/{news_id}")


@app.route('/api/platform-news/<news_id>/derive-topic', methods=['POST'])
@token_required
@roles_required('admin', 'employee')   # «حوّل لموضوع»: spin a news item into a Topic
def platform_news_derive_topic(news_id):
    return _platform_proxy('POST', f"/api/bridge/news/{news_id}/derive-topic")


@app.route('/api/platform-news-sources', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def platform_news_sources_get():
    return _platform_proxy('GET', '/api/bridge/news-sources')


@app.route('/api/platform-news-sources', methods=['PUT'])
@token_required
@roles_required('admin', 'employee')
def platform_news_sources_update():
    body = request.json or {}
    payload = {}
    for key in ('feeds', 'club_keywords'):
        if key in body:
            payload[key] = body.get(key)
    return _platform_proxy('PUT', '/api/bridge/news-sources', json_body=payload)


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


def _metrics_secret_ok():
    """True iff the request carries the shared platform<->dashboard service secret.
    Mirrors the verification used by the other bridge endpoints (investor_wallet_bridge)."""
    secret = request.headers.get('X-ELP-Metrics-Secret', '')
    return bool(
        PLATFORM_METRICS_SECRET
        and secret
        and secrets.compare_digest(secret, PLATFORM_METRICS_SECRET)
    )


def _course_for_finance_event(course_id, course_slug, course_title):
    """Resolve the Course record a finance-event's course_id/slug/course_title
    refers to, so a bridge sale attaches to the real course instead of relying on
    revenues_for_course()'s fragile title-in-description scan. Tries the
    platform's own identifiers first (exact, survives course renames), then an
    exact title match; returns None if nothing matches — the old substring scan
    in revenues_for_course()/expenses_for_course() still covers it on read."""
    course = None
    cid = str(course_id).strip() if course_id else ''
    if cid:
        course = (Course.query.filter_by(platform_course_id=cid).first()
                  or Course.query.filter_by(lms_id=cid).first())
    slug = str(course_slug).strip() if course_slug else ''
    if not course and slug:
        course = Course.query.filter_by(platform_course_slug=slug).first()
    title = str(course_title).strip() if course_title else ''
    if not course and title:
        course = Course.query.filter_by(title=title).first()
    return course


@app.route('/api/metrics/finance-event', methods=['POST'])
def metrics_finance_event():
    """LINKAGE RECEIVER — the platform POSTs each real money event here so the
    dashboard ledger reflects live sales (and escrow transitions) instead of the
    405 that previously swallowed them silently.

    Auth: shared service secret (X-ELP-Metrics-Secret) — NOT a user JWT.

    Body: { payment_id, amount, amount_original, currency, kind, source,
            occurred_at, course_id, course_slug, course_title, meta? }
      kind = 'sale'|'course'|'consulting'|'subscription'|... → idempotent Revenue row.
      kind = 'escrow_hold'  → mirror an EscrowSession in 'held' (read-mirror only).
      kind = 'escrow_release'|'escrow_refund'|'escrow_dispute' → reflect the status
              transition on the mirrored EscrowSession. No real money is moved here.

    Currency honesty: EGP/USD post to amount_egp/amount_usd as usual. Any other
    currency does NOT get zeroed out — the true amount lands in amount_original
    (+ currency) and needs_fx=True, so reports can show «بعملة أجنبية — بانتظار
    تسوية» instead of silently losing the sale.

    course_id/course_slug/course_title (top-level or inside meta) are matched
    against the Course table (see _course_for_finance_event) to set course_id
    directly, rather than depending on the description substring scan.

    Idempotency: Revenue.payment_id is unique → re-delivery never double-counts.
    Escrow mirroring is keyed by payment_id (stored in EscrowSession.ref)."""
    if not _metrics_secret_ok():
        return jsonify({'error': 'unauthorized'}), 401

    d = request.json or {}
    payment_id = (str(d.get('payment_id') or '')).strip()
    if not payment_id:
        return jsonify({'error': 'payment_id required'}), 400
    try:
        amount = round(float(d.get('amount') or 0), 2)
    except (TypeError, ValueError):
        amount = 0.0
    currency = (d.get('currency') or 'EGP').strip().upper()[:8]
    kind = (d.get('kind') or 'sale').strip().lower()
    source = (d.get('source') or 'platform').strip()[:100]
    meta = d.get('meta') or {}

    # amount_original — the platform's own pre-FX figure in `currency`. Falls back
    # to `amount` so this stays backward compatible with senders that don't send it.
    try:
        raw_original = d.get('amount_original')
        amount_original = round(float(raw_original), 2) if raw_original is not None else amount
    except (TypeError, ValueError):
        amount_original = amount

    course_id_in = d.get('course_id') or meta.get('course_id')
    course_slug_in = d.get('course_slug') or d.get('slug') or meta.get('course_slug') or meta.get('slug')
    course_title_in = d.get('course_title') or meta.get('course_title')

    # occurred_at → a date for the ledger (fall back to today on bad input).
    occurred_raw = (d.get('occurred_at') or '').strip()
    occurred_date = datetime.date.today()
    if occurred_raw:
        try:
            occurred_date = datetime.datetime.fromisoformat(
                occurred_raw.replace('Z', '+00:00')
            ).date()
        except (ValueError, TypeError):
            try:
                occurred_date = datetime.date.fromisoformat(occurred_raw[:10])
            except (ValueError, TypeError):
                occurred_date = datetime.date.today()

    # ---- ESCROW transition events: mirror only (no money movement here) ----
    if kind.startswith('escrow'):
        # Mirror keyed by payment_id (stored in .ref) so re-delivery is idempotent.
        session = EscrowSession.query.filter_by(ref=payment_id).first()
        now = datetime.datetime.utcnow()
        if kind == 'escrow_hold':
            if not session:
                session = EscrowSession(
                    id=_next_seq_id(EscrowSession, 'ESC'),
                    student_name=(meta.get('student_name') or '').strip(),
                    student_email=(meta.get('student_email') or '').strip().lower(),
                    expert_name=(meta.get('expert_name') or '').strip(),
                    expert_email=(meta.get('expert_email') or '').strip().lower(),
                    amount=amount,
                    currency=currency if currency in ESCROW_SUPPORTED_CURRENCIES else 'EGP',
                    status='held',
                    held_at=now,
                    release_at=now + datetime.timedelta(hours=ESCROW_HOLD_HOURS),
                    ref=payment_id,
                    source=source or 'platform',
                    notes='mirror:platform-escrow',
                )
                db.session.add(session)
        elif session:
            status_map = {
                'escrow_release': 'released',
                'escrow_refund': 'refunded',
                'escrow_dispute': 'dispute',
                'escrow_confirm': 'confirm',
            }
            new_status = status_map.get(kind)
            if new_status:
                session.status = new_status
                if new_status == 'released' and not session.released_at:
                    session.released_at = now
        db.session.commit()
        return jsonify({'ok': True, 'mirrored': 'escrow',
                        'session': serialize_escrow(session) if session else None}), 200

    # ---- Normal money-in event → idempotent Revenue row ----
    existing = Revenue.query.filter_by(payment_id=payment_id).first()
    if existing:
        # Already recorded — re-delivery is a no-op (do NOT double-count).
        return jsonify({'ok': True, 'revenue_id': existing.id, 'duplicate': True}), 200

    is_egp = currency == 'EGP'
    is_usd = currency == 'USD'
    foreign = not (is_egp or is_usd)  # neither EGP nor USD → don't guess an FX rate
    matched_course = _course_for_finance_event(course_id_in, course_slug_in, course_title_in)

    rev = Revenue(
        date=occurred_date,
        source=kind if kind else 'sale',
        description=(meta.get('description') or f'Platform {kind} {payment_id}')[:1000],
        amount_egp=(amount if is_egp else (None if foreign else 0)),
        amount_usd=(amount if is_usd else 0),
        amount_original=(amount_original if foreign else None),
        currency=(currency if foreign else None),
        needs_fx=foreign,
        client_name=(meta.get('client_name') or meta.get('buyer_email') or '')[:255],
        course_id=(matched_course.id if matched_course else None),
        payment_method=(meta.get('payment_method') or source or 'platform')[:50],
        payment_id=payment_id,
        notes=f'bridge:finance-event:{source}',
    )
    db.session.add(rev)
    try:
        db.session.commit()
    except IntegrityError:
        # Concurrent re-delivery raced us on the unique payment_id → fetch & no-op.
        db.session.rollback()
        existing = Revenue.query.filter_by(payment_id=payment_id).first()
        return jsonify({'ok': True, 'revenue_id': existing.id if existing else None,
                        'duplicate': True}), 200
    return jsonify({'ok': True, 'revenue_id': rev.id}), 200


@app.route('/api/bridge/escrow', methods=['GET'])
def bridge_escrow():
    """ESCROW read-mirror — lets the platform (service secret) OR an admin (JWT)
    read the dashboard's escrow ledger. READ ONLY; never moves money."""
    authorized = _metrics_secret_ok()
    if not authorized:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if token:
            try:
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                u = User.query.get(data['user_id'])
                authorized = bool(u and u.is_active and role_grants(u, 'admin'))
            except Exception:
                authorized = False
    if not authorized:
        return jsonify({'error': 'unauthorized'}), 401

    status = (request.args.get('status') or '').strip()
    q = EscrowSession.query
    if status:
        q = q.filter(EscrowSession.status == status)
    items = q.order_by(EscrowSession.held_at.desc()).all()
    now = datetime.datetime.utcnow()
    return jsonify([serialize_escrow(e, now) for e in items])

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
    # ONE normalized decision written to BOTH identity fields — 'Admin' and
    # 'admin ' must not become a different (and un-grantable) role.
    new_role = normalize_role(d.get('dashboard_role') or d.get('role')) or 'viewer'
    user = User(
        email=email,
        password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
        name=d.get('name') or email.split('@')[0],
        role=new_role,
        dashboard_role=new_role,
        linked_to_name=d.get('linked_to_name') or '',
        preferred_currency=(d.get('preferred_currency') or 'AUTO').upper(),
        is_active=True
    )
    db.session.add(user)
    db.session.commit()
    _audit('admin.add_user', target=user.id, meta={'email': user.email, 'role': user.dashboard_role})
    return jsonify({'id': user.id, 'message': 'تم إضافة المستخدم'}), 201

@app.route('/api/users/<int:id>', methods=['PUT'])
@token_required
@roles_required('admin')
def update_user(id):
    user = User.query.get_or_404(id)
    d = request.json or {}

    # LAST-ADMIN protection: never let the only remaining active admin be
    # demoted, deactivated, or have their email changed (they'd lock everyone out).
    if is_last_admin(user):
        demotes = False
        for rk in ('role', 'dashboard_role'):
            if rk in d and (str(d.get(rk) or '').strip().lower() != 'admin'):
                demotes = True
        deactivates = ('is_active' in d) and (not d.get('is_active'))
        changes_email = (
            'email' in d
            and (str(d.get('email') or '').lower().strip() != (user.email or '').lower().strip())
        )
        if demotes or deactivates or changes_email:
            return jsonify({
                'error': 'لا يمكن تعديل المدير الوحيد المتبقي (الدور/التفعيل/البريد). أضف مديرًا آخر أولًا.'
            }), 409

    # NORMALIZE + KEEP THE TWO IDENTITY FIELDS IN SYNC. `role` and
    # `dashboard_role` are one decision: a payload touching only one of them used
    # to mint a split identity (one field says admin, the other trainer), which
    # role_grants() then has to deny on BOTH sides. Writing both from one
    # normalized value makes divergence unrepresentable going forward.
    if ('role' in d) or ('dashboard_role' in d):
        chosen = ''
        for rk in ('dashboard_role', 'role'):
            if normalize_role(d.get(rk)):
                chosen = normalize_role(d.get(rk))
                break
        chosen = chosen or 'viewer'
        d['role'] = chosen
        d['dashboard_role'] = chosen

    for key in ['name', 'email', 'role', 'dashboard_role', 'linked_to_name', 'preferred_currency', 'is_active']:
        if key in d:
            value = d[key]
            if key == 'email' and value:
                value = value.lower().strip()
            if key in ('role', 'dashboard_role'):
                value = normalize_role(value) or 'viewer'
            if key == 'preferred_currency':
                value = (value or 'AUTO').upper()
            setattr(user, key, value)
    if d.get('password'):
        user.password_hash = generate_password_hash(d['password'], method='pbkdf2:sha256')
    db.session.commit()
    _audit('admin.update_user', target=user.id, meta={
        'email': user.email,
        'fields': [k for k in d.keys() if k != 'password'],
        'password_changed': bool(d.get('password')),
    })
    return jsonify({'message': 'تم تحديث المستخدم'})

# ============================================================
# AUDIT LOG (F5) — recent dashboard mutations, admin-only
# ============================================================

@app.route('/api/audit', methods=['GET'])
@token_required
@roles_required('admin')
def list_audit():
    """Recent audit rows (D9 «سجل العمليات»). Bounded: newest-first, capped at 500."""
    try:
        limit = int(request.args.get('limit') or 100)
    except (TypeError, ValueError):
        limit = 100
    limit = max(1, min(500, limit))
    action = (request.args.get('action') or '').strip()
    q = AuditLog.query
    if action:
        q = q.filter(AuditLog.action == action)
    rows = q.order_by(AuditLog.created_at.desc()).limit(limit).all()
    def _meta(r):
        if not r.meta_json:
            return None
        try:
            return json.loads(r.meta_json)
        except Exception:
            return None
    return jsonify([{
        'id': r.id,
        'actor_email': r.actor_email,
        'action': r.action,
        'target': r.target,
        'meta': _meta(r),
        'created_at': r.created_at.isoformat() if r.created_at else None,
    } for r in rows])


@app.route('/api/usage', methods=['GET'])
@token_required
@roles_required('admin')
def usage_stats():
    """Usage panel for D9 Settings: AI calls (AILog), logins + actions/day (AuditLog).
    All figures are real counts — no estimates."""
    now = datetime.datetime.utcnow()
    since_7d = now - datetime.timedelta(days=7)
    ai_total = AILog.query.count()
    ai_errors = AILog.query.filter(AILog.response.like('ERROR:%')).count()
    audit_total = AuditLog.query.count()
    logins_7d = AuditLog.query.filter(AuditLog.action == 'auth.login', AuditLog.created_at >= since_7d).count()
    actions_7d = AuditLog.query.filter(AuditLog.created_at >= since_7d).count()
    # actions per day for the last 7 days (from AuditLog)
    recent = AuditLog.query.filter(AuditLog.created_at >= since_7d).all()
    by_day = {}
    for r in recent:
        if r.created_at:
            key = r.created_at.date().isoformat()
            by_day[key] = by_day.get(key, 0) + 1
    return jsonify({
        'ai_calls': ai_total,
        'ai_errors': ai_errors,
        'audit_total': audit_total,
        'logins_7d': logins_7d,
        'actions_7d': actions_7d,
        'by_day': [{'day': k, 'count': v} for k, v in sorted(by_day.items())],
    })

# ============================================================
# DASHBOARD / KPIs
# ============================================================

@app.route('/api/dashboard', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
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
@roles_required('admin', 'employee')
def list_revenues():
    items = Revenue.query.order_by(Revenue.date.desc()).all()
    rate = get_rate()
    return jsonify([{
        'id': r.id, 'date': serialize_date(r.date), 'source': r.source,
        'description': r.description, 'amount_egp': r.amount_egp, 'amount_usd': r.amount_usd,
        'total_egp': round(to_egp(r.amount_usd, r.amount_egp, rate)),
        'client_name': r.client_name, 'course_id': r.course_id, 'campaign_id': r.campaign_id,
        'payment_method': r.payment_method, 'notes': r.notes,
        'amount_original': r.amount_original, 'currency': r.currency, 'needs_fx': bool(r.needs_fx),
    } for r in items])

@app.route('/api/revenues', methods=['POST'])
@token_required
@roles_required('admin')
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
@roles_required('admin')
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
@roles_required('admin')
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
@roles_required('admin', 'employee')
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
@roles_required('admin', 'employee')
def list_assets():
    items = Asset.query.order_by(Asset.category.asc(), Asset.value_egp.desc()).all()
    return jsonify([{
        'id': a.id, 'name': a.name, 'category': a.category, 'owner': a.owner,
        'value_egp': a.value_egp, 'monthly_rent_egp': a.monthly_rent_egp,
        'status': a.status, 'notes': a.notes
    } for a in items])

@app.route('/api/assets', methods=['POST'])
@token_required
@roles_required('admin')
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
@roles_required('admin')
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
@roles_required('admin')
def delete_asset(id):
    a = Asset.query.get_or_404(id)
    db.session.delete(a)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

@app.route('/api/forecast', methods=['GET'])
@token_required
@roles_required('admin')               # full P&L forecast (revenue/payroll/rent) — no non-admin screen calls it
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
@roles_required('admin')               # financial WRITE — never open to trainer/investor/viewer
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
@roles_required('admin')
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
@roles_required('admin')
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
@roles_required('admin')
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
@roles_required('admin')               # ad budget/spend/CAC — only the admin «marketing» module calls it
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
@roles_required('admin')               # marketing budget/spend WRITE — admin only
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
@roles_required('admin')               # marketing budget/spend WRITE — admin only
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
@roles_required('admin')               # marketing budget/spend WRITE — admin only
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
@module_required('courses')            # D9: admin can revoke per-role module access
def list_courses():
    viewer_role = user_dashboard_role(g.user)
    is_admin = is_admin_scope(g.user)
    is_staff = role_grants(g.user, 'admin', 'employee')
    items = Course.query.order_by(Course.created_at.desc()).all()

    def is_own_trainer_course(course):
        """The SAME predicate that scopes the trainer's list below — so every
        course a trainer can see, it can also see its own percentage for. Using
        a stricter rule here would blank «نسبتي» on courses the filter already
        handed them.

        Uses the strict entitlement rule, NOT names_match(): the loose one is a
        containment test against `user.name`, which is the platform `full_name`
        the USER writes via SSO — an account renamed to «ا» matched every course.
        Every other money surface already moved to this helper; this route was
        the last one left holding the old rule."""
        return entitlement_name_matches(course.trainer_name, g.user)

    # WHICH COURSES. Staff (admin + the read-only employee, whose ROLE_NAV owns
    # the «courses» module) see the catalogue; everyone else is scoped, and an
    # unrecognised/viewer role sees NOTHING. Previously only trainer/investor
    # were scoped, so a self-created SSO `viewer` listed the whole catalogue.
    if is_staff:
        pass
    elif viewer_role == 'trainer':
        items = [item for item in items if is_own_trainer_course(item)]
    elif viewer_role == 'investor':
        if request.args.get('scope') == 'marketplace':
            # المستثمر يشوف بس الدورات اللي الأدمن فتحها للاستثمار.
            items = [item for item in items if item.open_for_investment]
        else:
            # Same rule as /api/investments — the investor_user_id foreign key
            # first, then the admin-controlled name. Matching on the raw
            # user-supplied name (the old filter_by) let a chosen display name
            # claim someone else's portfolio.
            course_ids = {
                item.course_id for item in Investment.query.all()
                if investment_visible_to(item, g.user)
            }
            items = [item for item in items if item.id in course_ids]
    else:
        items = []
    rate = get_rate()
    result = []
    for c in items:
        financial = course_financials(c, rate)
        # WHICH MONEY ROWS. These two lists name individuals and their amounts —
        # the same data /api/payouts and /api/investments protect. Serving them
        # unfiltered here was a COMPLETE bypass of those filters, so they obey
        # exactly the same per-row rule (same helper, no second matching logic):
        # admin → all rows; trainer → its own payout rows; investor → its own
        # investments; anyone else (employee, viewer) → nothing.
        visible_payouts = [
            p for p in financial['linked_payouts_models']
            if is_admin or payout_visible_to(p, g.user)
        ]
        visible_investments = [
            i for i in financial['investments']
            if is_admin or investment_visible_to(i, g.user)
        ]
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
            for p in visible_payouts
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
        # THE NON-FINANCIAL COURSE ROW — everything a non-admin screen actually
        # renders. Verified against the two consumers in dashboard-cloud:
        #   employee «الدورات» (loader `courses` → viewCourses/renderCourses):
        #     id, title, trainer_name, students_count, price_egp/price_usd,
        #     status, lms_synced, platform_course_id, platform_course_slug
        #   trainer «دوراتي/أرباحي» (loader `t_data`):
        #     id, title, students_count, price_egp/price_usd, status,
        #     revenue_split.trainer_percent  (added back below, own courses only)
        row = {
            'id': c.id, 'title': c.title, 'category': c.category,
            'trainer_name': c.trainer_name, 'status': c.status,
            'price_egp': c.price_egp, 'price_usd': c.price_usd,
            'students_count': c.students_count,
            'start_date': serialize_date(c.start_date), 'end_date': serialize_date(c.end_date),
            'lms_id': c.lms_id, 'notes': c.notes,
            'platform_course_id': c.platform_course_id, 'platform_course_slug': c.platform_course_slug,
            'lms_synced': bool(c.lms_synced), 'lms_instructor_email': c.lms_instructor_email,
            'open_for_investment': bool(c.open_for_investment),
        }
        if is_admin:
            # THE COMPANY LEDGER FOR THIS COURSE. Revenue, cost, profit and the
            # distribution are the same numbers /api/finance protects; serving
            # them on the course row was a side door around it. The employee mode
            # promises «قراءة فقط: المستخدمون والدورات، بلا أرقام مالية» — this is
            # where that promise is kept.
            row.update({
                'cost_egp': c.cost_egp, 'cost_usd': c.cost_usd,
                'total_revenue': financial['total_revenue'], 'total_cost': financial['total_cost'],
                'linked_expense_cost': financial['linked_expense_cost'],
                'linked_payout_cost': financial['linked_payout_cost'],
                'linked_investment_cost': financial['linked_investment_cost'],
                'linked_expenses': linked_expenses,
                'profit': financial['profit'],
                'revenue_split': financial['split'],
                'distribution': financial['distribution'],
                'lms_sales_count': c.lms_sales_count or 0,
                'lms_revenue': c.lms_revenue or 0,
                'lms_currency': c.lms_currency or '',
            })
        elif viewer_role == 'trainer' and is_own_trainer_course(c):
            # ONLY the owning trainer's own percentage — the one financial field
            # a trainer screen renders («نسبتي» in t_home / t_earnings). No
            # amounts: no revenue, no cost, no profit, no distribution.
            row['revenue_split'] = financial['split']
        # Own entitlement rows (already filtered per row above) travel with the
        # course for every role: a trainer's own payouts, an investor's own
        # investments. For an employee/viewer both lists are empty by construction.
        row['linked_payouts'] = linked_payouts
        row['linked_investments'] = [serialize_investment(item, rate, {c.id: c}) for item in visible_investments]
        result.append(row)
    return jsonify(result)

@app.route('/api/courses', methods=['POST'])
@token_required
@roles_required('admin', 'employee')   # creating a course auto-mirrors to the platform → staff only
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
    # flush() assigns the autoincrement id (needed as dashboard_course_id) WITHOUT committing, so the
    # course + its platform link persist in ONE atomic commit below — no half-mirrored state on error.
    db.session.flush()
    # Mirror it onto the platform so it actually appears on app.elprofessor.net (not just here),
    # unless the caller opts out. Failure is non-fatal — the dashboard record still saves.
    linked = None
    if d.get('publish_to_platform', True):
        linked = _platform_create_course(c)
        if linked:
            c.platform_course_id = linked.get('id')
            c.platform_course_slug = linked.get('slug')
    db.session.commit()
    _audit('course.create', target=c.id, meta={'title': c.title, 'platform_published': bool(linked)})
    return jsonify({
        'id': c.id,
        'platform_course_id': c.platform_course_id,
        'platform_course_slug': c.platform_course_slug,
        'platform_published': bool(linked),
        'message': 'تم إضافة الدورة' + (' ونشرها على المنصة' if linked else ''),
    }), 201


@app.route('/api/courses/<int:id>/publish-platform', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
def publish_course_to_platform(id):
    """Push an EXISTING dashboard course onto the platform as a native course (for courses created
    before the auto-mirror, or whose first mirror attempt failed)."""
    c = Course.query.get_or_404(id)
    if c.platform_course_id:
        return jsonify({'ok': True, 'already': True,
                        'platform_course_id': c.platform_course_id,
                        'platform_course_slug': c.platform_course_slug})
    linked = _platform_create_course(c)
    if not linked:
        return jsonify({'error': 'تعذّر النشر على المنصة — تأكد من الربط (METRICS_SECRET)'}), 502
    c.platform_course_id = linked.get('id')
    c.platform_course_slug = linked.get('slug')
    db.session.commit()
    return jsonify({'ok': True, 'platform_course_id': c.platform_course_id,
                    'platform_course_slug': c.platform_course_slug})

@app.route('/api/courses/<int:id>', methods=['PUT'])
@token_required
@roles_required('admin', 'employee')   # edits mirror to the native platform course → staff only
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
    # Mirror the core edits to the linked native course so the platform stays in sync.
    native = None
    if c.platform_course_id:
        fields = {}
        if 'title' in d:
            fields['title'] = c.title
        if 'trainer_name' in d:
            fields['instructor_name'] = c.trainer_name or ''
        if 'category' in d:
            fields['category'] = c.category or ''
        if 'price_egp' in d:
            fields['price_egp'] = c.price_egp or 0
        if 'price_usd' in d:
            fields['price_usd'] = c.price_usd or 0
        if 'status' in d:
            fields['is_active'] = (c.status == 'active')
        native = _platform_update_course(c.platform_course_id, fields) if fields else None
    _audit('course.update', target=c.id, meta={'fields': [k for k in d.keys()]})
    return jsonify({'message': 'تم التحديث', 'platform_synced': bool(native)})

@app.route('/api/courses/<int:id>', methods=['DELETE'])
@token_required
@roles_required('admin', 'employee')   # also deletes the native platform course → staff only
def delete_course(id):
    c = Course.query.get_or_404(id)
    # Soft-delete the linked native course first (so it disappears from the platform), then drop
    # the local row. Native delete is best-effort — a link failure must not block the local delete.
    if c.platform_course_id:
        _platform_delete_course(c.platform_course_id)
    _title = c.title
    db.session.delete(c)
    db.session.commit()
    _audit('course.delete', target=id, meta={'title': _title})
    return jsonify({'message': 'تم الحذف'})


# Pull the REAL courses from the academy (WordPress/Tutor, via the platform bridge) and
# upsert them into our Course table keyed by lms_id = tutor_id, tied to each course's
# instructor (by email). Manual financials (price/cost) are preserved on update.
_LMS_STATUS_MAP = {'publish': 'active', 'draft': 'draft', 'pending': 'draft', 'trash': 'archived', 'private': 'draft'}


@app.route('/api/courses/sync-lms', methods=['POST'])
@token_required
@roles_required('admin', 'employee')
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
        # Real revenue from WooCommerce (if matched by product name on the platform side).
        if 'woo_revenue' in row:
            c.lms_sales_count = int(row.get('woo_sales') or 0)
            c.lms_revenue = float(row.get('woo_revenue') or 0)
            c.lms_currency = row.get('woo_currency') or c.lms_currency
    db.session.commit()
    return jsonify({
        'message': 'تمت المزامنة من الأكاديمية',
        'total': len(rows), 'created': created, 'updated': updated,
    })


# Create a course ON the academy (WordPress/Tutor) from here, tied to its instructor by
# email. Admin can set any instructor; a trainer creates only under their own email.
# Created as a draft; once published it flows back via the sync above.
@app.route('/api/courses/create-lms', methods=['POST'])
@token_required
@roles_required('admin', 'trainer', 'employee')
def create_lms_course():
    if not PLATFORM_METRICS_SECRET:
        return jsonify({'error': 'لم يتم ضبط الربط بعد'}), 503
    d = request.json or {}
    if not (d.get('title') or '').strip():
        return jsonify({'error': 'عنوان الدورة مطلوب'}), 400
    # A trainer can only create a course under their own (academy) email.
    if user_dashboard_role(g.user) == 'trainer':
        instructor_email = (g.user.email or '').strip().lower()
    else:
        instructor_email = (d.get('instructor_email') or '').strip().lower()
    if not instructor_email:
        return jsonify({'error': 'إيميل المحاضر مطلوب'}), 400
    payload = {
        'title': d['title'].strip(),
        'content': d.get('content', ''),
        'level': d.get('level', 'beginner'),
        'price_type': 'paid' if d.get('price_type') == 'paid' else 'free',
        'duration_hours': int(d.get('duration_hours') or 0),
        'duration_minutes': int(d.get('duration_minutes') or 0),
        'instructor_email': instructor_email,
        'status': 'draft',
    }
    try:
        r = requests.post(
            f"{PLATFORM_API_URL}/api/bridge/lms-courses",
            json=payload,
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=30,
        )
    except Exception:
        return jsonify({'error': 'تعذر الاتصال بالمنصة'}), 502
    body = r.json() if r.content else {}
    if r.status_code != 200:
        return jsonify({'error': body.get('detail') or body.get('error') or 'تعذر إنشاء الدورة على الأكاديمية'}), r.status_code
    return jsonify({'message': 'تم إنشاء الدورة كمسودة على الأكاديمية', **body})

# ============================================================
# SETTINGS
# ============================================================

# Settings keys a NON-admin session is allowed to read. The settings table also
# holds integration keys and raw bank figures, so it is an allowlist, never a
# denylist. `role_permissions` is here because the shell asks for it on EVERY
# login (renderNav → EP.ensure('settings')) to build a non-admin's own menu —
# 403-ing the whole route would silently drop the D9 menu restrictions.
NON_ADMIN_SETTING_KEYS = {ROLE_PERMISSIONS_KEY}


@app.route('/api/settings', methods=['GET'])
@token_required
def get_settings():
    items = Setting.query.all()
    if not is_admin_scope(g.user):
        return jsonify({s.key: s.value for s in items if s.key in NON_ADMIN_SETTING_KEYS})
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
    _audit('settings.update', target='settings', meta={'keys': list(d.keys())})
    return jsonify({'message': 'تم التحديث'})

# ============================================================
# PACKAGES / GEO-PRICING (الباقات والأسعار)
# ============================================================
# مصدر الحقيقة القابل للتعديل لأسعار الباقات حسب بلد الزائر (EG/SA/AE/KW/QA/default).
# يُخزَّن كـ JSON واحد في جدول settings (نفس نمط /api/settings: مفتاح/قيمة نصية).
# المنصّة نفسها تحمل خرائط أسعار في الكود؛ هذه النقطة هي المخزن الذي يديره الأدمن.

PACKAGES_SETTING_KEY = 'packages_config'
PACKAGE_COUNTRIES = ['EG', 'SA', 'AE', 'KW', 'QA', 'default']
PACKAGE_COUNTRY_CURRENCY = {
    'EG': 'ج.م', 'SA': 'ر.س', 'AE': 'د.إ', 'KW': 'د.ك', 'QA': 'ر.ق', 'default': '$',
}

def default_packages():
    """الباقات الافتراضية (الخطط المعروفة: مجانية/أدوات/برو/شركات) — تُزرع عند أول تشغيل."""
    return [
        {
            'id': 'free', 'name': 'الباقة المجانية', 'cycle': 'مجانية', 'active': True,
            'features': ['تصفّح الكتالوج', 'المحاضرة الأولى مجانًا', 'مقالات المدونة'],
            'prices': {'EG': 0, 'SA': 0, 'AE': 0, 'KW': 0, 'QA': 0, 'default': 0},
            'currency_per_country': dict(PACKAGE_COUNTRY_CURRENCY),
        },
        {
            'id': 'ai_plus', 'name': 'باقة الأدوات', 'cycle': 'شهري', 'active': True,
            'features': ['المحرر القانوني الذكي', 'قوالب ومكتبة أحكام', 'إملاء وتدقيق'],
            'prices': {'EG': 199, 'SA': 39, 'AE': 39, 'KW': 3, 'QA': 39, 'default': 15},
            'currency_per_country': dict(PACKAGE_COUNTRY_CURRENCY),
        },
        {
            'id': 'training', 'name': 'باقة برو', 'cycle': 'شهري', 'active': True,
            'features': ['كل أدوات الباقة', 'استشارة شهرية بخصم', 'أولوية الدعم', 'شهادات معتمدة'],
            'prices': {'EG': 399, 'SA': 79, 'AE': 79, 'KW': 6, 'QA': 79, 'default': 29},
            'currency_per_country': dict(PACKAGE_COUNTRY_CURRENCY),
        },
        {
            'id': 'hybrid', 'name': 'باقة الشركات', 'cycle': 'شهري', 'active': False,
            'features': ['حتى ١٠ مستخدمين', 'تدريب مخصّص', 'حساب مدير', 'فوترة B2B'],
            'prices': {'EG': 1500, 'SA': 300, 'AE': 300, 'KW': 22, 'QA': 300, 'default': 99},
            'currency_per_country': dict(PACKAGE_COUNTRY_CURRENCY),
        },
    ]

def _normalize_package(p):
    """يُعيد باقة منظَّمة بحقول ثابتة وأسعار/عملات لكل بلد معروف."""
    p = p or {}
    prices_in = p.get('prices') or {}
    cur_in = p.get('currency_per_country') or {}
    prices, currency = {}, {}
    for cc in PACKAGE_COUNTRIES:
        try:
            prices[cc] = float(prices_in.get(cc, 0) or 0)
        except (TypeError, ValueError):
            prices[cc] = 0
        currency[cc] = str(cur_in.get(cc) or PACKAGE_COUNTRY_CURRENCY[cc])
    features = p.get('features') or []
    if not isinstance(features, list):
        features = [str(features)]
    return {
        'id': str(p.get('id') or '').strip() or secrets.token_hex(4),
        'name': str(p.get('name') or 'باقة').strip() or 'باقة',
        'cycle': str(p.get('cycle') or 'شهري').strip() or 'شهري',
        'active': bool(p.get('active', True)),
        'features': [str(f) for f in features],
        'prices': prices,
        'currency_per_country': currency,
    }

def _load_packages():
    """يقرأ تهيئة الباقات من settings؛ يزرع الافتراضي عند الفراغ (نفس نمط get_setting_*)."""
    s = Setting.query.get(PACKAGES_SETTING_KEY)
    if s and s.value:
        try:
            parsed = json.loads(s.value)
            if isinstance(parsed, list) and parsed:
                return [_normalize_package(p) for p in parsed]
        except (TypeError, ValueError):
            pass
    # زرع الافتراضي على أول تشغيل وحفظه ليصبح مصدر الحقيقة القابل للتعديل.
    pkgs = default_packages()
    seed = Setting.query.get(PACKAGES_SETTING_KEY)
    payload = json.dumps(pkgs, ensure_ascii=False)
    if seed:
        seed.value = payload
        seed.updated_at = datetime.datetime.utcnow()
    else:
        db.session.add(Setting(key=PACKAGES_SETTING_KEY, value=payload))
    db.session.commit()
    return pkgs

# The dashboard «الباقات والأسعار» now CONTROLS the live platform plans via the METRICS_SECRET
# bridge. The platform stores price as {country:{amount,currency}}; the dashboard UI uses a flat
# {COUNTRY: amount} with currency implied per country — so we transform both ways.
_PKG_CC_CURRENCY = {'EG': 'EGP', 'SA': 'SAR', 'AE': 'AED', 'KW': 'KWD', 'QA': 'QAR', 'default': 'USD'}


def _platform_plan_to_pkg(p):
    prices = {}
    for cc, v in (p.get('prices') or {}).items():
        key = 'default' if cc == 'default' else cc.upper()
        prices[key] = (v or {}).get('amount', 0)
    return {
        'id': p.get('id'),
        'name': p.get('name', ''),
        'cycle': 'مجانية' if p.get('is_free') else 'شهري',
        'active': p.get('active', True),
        'features': p.get('features', []),
        'prices': prices,
    }


@app.route('/api/packages', methods=['GET'])
@token_required
# NOT admin-only: the employee «المستخدمون» screen loads packages to label each
# platform user's plan (index.html viewUsers → EP.ensure('packages')). Closing it
# to admin would break a screen ROLE_NAV grants the employee. Content = public
# plan names/prices, so staff-wide is the right blast radius.
@roles_required('admin', 'employee')
def get_packages():
    # Prefer the LIVE platform plans (via the bridge); fall back to the local copy if the bridge
    # isn't reachable so the screen never goes blank.
    if PLATFORM_METRICS_SECRET:
        try:
            r = requests.get(
                f"{PLATFORM_API_URL}/api/bridge/plans",
                headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET}, timeout=15,
            )
            if r.status_code == 200 and r.content:
                plans = (r.json() or {}).get('plans', [])
                return jsonify({
                    'packages': [_platform_plan_to_pkg(p) for p in plans],
                    'countries': PACKAGE_COUNTRIES,
                    'currency_per_country': PACKAGE_COUNTRY_CURRENCY,
                    'source': 'platform',
                })
        except Exception:
            pass
    return jsonify({
        'packages': _load_packages(),
        'countries': PACKAGE_COUNTRIES,
        'currency_per_country': PACKAGE_COUNTRY_CURRENCY,
    })


@app.route('/api/packages', methods=['PUT'])
@token_required
@roles_required('admin')
def update_packages():
    d = request.json or {}
    incoming = d.get('packages') if isinstance(d, dict) else d
    if not isinstance(incoming, list):
        return jsonify({'error': 'packages must be a list'}), 400

    # Push edits to the platform for plans it actually defines (free/pro). Each plan is updated
    # individually via the bridge PUT.
    synced = []
    if PLATFORM_METRICS_SECRET:
        for p in incoming:
            pid = str(p.get('id') or '').strip().lower()
            if pid not in ('free', 'pro'):
                continue  # extra dashboard-only packages stay local (platform has no slot for them)
            prices = {}
            for cc, amt in (p.get('prices') or {}).items():
                key = 'default' if str(cc) == 'default' else str(cc).lower()
                cur = _PKG_CC_CURRENCY.get('default' if str(cc) == 'default' else str(cc).upper())
                try:
                    amtf = float(amt)
                except (TypeError, ValueError):
                    continue
                if cur and amtf > 0:
                    prices[key] = {'amount': amtf, 'currency': cur}
            body = {
                'plan_id': pid, 'prices': prices, 'active': bool(p.get('active', True)),
                'name': p.get('name'), 'features': p.get('features'),
            }
            try:
                rr = requests.put(
                    f"{PLATFORM_API_URL}/api/bridge/plans", json=body,
                    headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET}, timeout=15,
                )
                if rr.status_code == 200:
                    synced.append(pid)
            except Exception:
                pass

    # Keep a local copy too (the dashboard supports extra local-only packages).
    pkgs = [_normalize_package(p) for p in incoming]
    payload = json.dumps(pkgs, ensure_ascii=False)
    s = Setting.query.get(PACKAGES_SETTING_KEY)
    if s:
        s.value = payload
        s.updated_at = datetime.datetime.utcnow()
    else:
        db.session.add(Setting(key=PACKAGES_SETTING_KEY, value=payload))
    db.session.commit()
    return jsonify({'message': 'تم تحديث الباقات', 'synced_to_platform': synced, 'packages': pkgs})

# ============================================================
# CASH FLOW / PARTNERS / PAYOUTS
# ============================================================

@app.route('/api/cashflow', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
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
@roles_required('admin')
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
@roles_required('admin')
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
@roles_required('admin')
def delete_cashflow(id):
    t = CashTransaction.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

@app.route('/api/partners', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
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
@roles_required('admin')
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
@roles_required('admin')
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
@roles_required('admin')
def delete_partner(id):
    p = Partner.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

@app.route('/api/payouts', methods=['GET'])
@token_required
# NOTE: intentionally NOT locked to admin/employee — this GET is role-scoped:
# trainers/investors only see rows matching their own linked name (see filter below).
# Locking it would break the trainer home dashboard. Company-wide totals live in
# /api/dashboard + /api/finance/summary, which ARE admin/employee-gated.
def list_payouts():
    rate = get_rate()
    items = Payout.query.order_by(Payout.date.desc()).all()
    # ONLY an unambiguous admin reads the whole payout ledger; EVERY other role
    # (employee included — its mode promises «no financial numbers», and it has
    # no finance module in ROLE_NAV) sees only rows carrying its own name.
    if not is_admin_scope(g.user):
        items = [item for item in items if payout_visible_to(item, g.user)]
    return jsonify([{
        'id': p.id, 'date': serialize_date(p.date), 'name': p.name, 'role': p.role,
        'related_to': p.related_to, 'basis_amount_egp': p.basis_amount_egp,
        'percent': p.percent, 'amount_egp': p.amount_egp, 'amount_usd': p.amount_usd,
        'total_egp': round(to_egp(p.amount_usd, p.amount_egp, rate) or ((p.basis_amount_egp or 0) * (p.percent or 0) / 100)),
        'status': p.status, 'notes': p.notes
    } for p in items])

@app.route('/api/payouts', methods=['POST'])
@token_required
@roles_required('admin')
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
@roles_required('admin')
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
@roles_required('admin')
def delete_payout(id):
    p = Payout.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'})

@app.route('/api/investments', methods=['GET'])
@token_required
# NOT locked: role-scoped — investors only see their OWN investments (filter below).
# Admins/employees see all. Locking would break the investor home dashboard.
def list_investments():
    rate = get_rate()
    items = Investment.query.order_by(Investment.created_at.desc()).all()
    course_lookup = {course.id: course for course in Course.query.all()}
    opportunity_lookup = {item.id: item for item in InvestmentOpportunity.query.all()}
    # ONLY an unambiguous admin reads the full cap table; EVERY other role
    # (employee included) sees only its OWN investments.
    if not is_admin_scope(g.user):
        items = [item for item in items if investment_visible_to(item, g.user)]
    return jsonify([serialize_investment(item, rate, course_lookup, opportunity_lookup) for item in items])

@app.route('/api/investments', methods=['POST'])
@token_required
@roles_required('admin')
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
@roles_required('admin')
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
@roles_required('admin')
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
    items = Investment.query.filter(Investment.status.in_(['active', 'pending', 'accrued'])).order_by(Investment.created_at.desc()).all()
    # Same scoping rule as /api/investments — otherwise this route is a bypass.
    if not is_admin_scope(g.user):
        items = [item for item in items if investment_visible_to(item, g.user)]
    course_lookup = {course.id: course for course in Course.query.all()}
    opportunity_lookup = {item.id: item for item in InvestmentOpportunity.query.all()}
    return jsonify([serialize_investment(item, rate, course_lookup, opportunity_lookup) for item in items])

@app.route('/api/investments/history', methods=['GET'])
@token_required
def investment_history():
    rate = get_rate()
    items = Investment.query.filter(Investment.status.in_(['completed', 'loss', 'paid'])).order_by(Investment.created_at.desc()).all()
    # Same scoping rule as /api/investments — otherwise this route is a bypass.
    if not is_admin_scope(g.user):
        items = [item for item in items if investment_visible_to(item, g.user)]
    course_lookup = {course.id: course for course in Course.query.all()}
    opportunity_lookup = {item.id: item for item in InvestmentOpportunity.query.all()}
    return jsonify([serialize_investment(item, rate, course_lookup, opportunity_lookup) for item in items])

@app.route('/api/investment-opportunities', methods=['GET'])
@token_required
# The deal sheet: target_amount / current_funded / expected_roi / trainer_name /
# students_count per opportunity. Only the two screens that exist for it may
# read it — admin «الاستثمار» (loader `investment`) and the investor portal
# (loader `i_data`). No employee/trainer/viewer screen calls this route: the
# employee nav is ROLE_NAV.employee = users·courses·topics·tutorials, and both
# investor-portal jobs already `.catch()`, so a 403 degrades, never breaks.
@roles_required('admin', 'investor')
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

def wallet_owner_name(user):
    """The investor-wallet key THIS account may open, or '' for none.

    get_or_create_wallet() WRITES a row, so whatever reaches it becomes a
    permanent `InvestorWallet`. It used to receive user_linked_name(), which
    falls back to the user's own display name — so any authenticated viewer or
    employee minted a wallet under their display name, polluting
    /api/admin/wallets, and an exact display-name collision opened a REAL
    investor's wallet. Two locks now: the account must actually hold a
    money-bearing role, and the key must be the admin-set `linked_to_name`
    (never a name the user picked for themself)."""
    if not role_grants(user, 'investor', 'trainer'):
        return ''
    return (getattr(user, 'linked_to_name', None) or '').strip()


def empty_wallet_payload():
    """A VALID, all-zero wallet — not a 403 and not an error. The investor
    portal's `i_data` loader calls /me/investor-wallet unconditionally and its
    ivMe() falls back to hard-coded DESIGN numbers whenever the wallet is null,
    so an error here would print fake balances on the screen. Zeros are both
    honest and unbreakable."""
    return {
        'id': None, 'investor_name': '', 'investor_user_id': None,
        'balance': 0, 'balance_egp': 0,
        'total_invested': 0, 'total_invested_egp': 0,
        'total_returns': 0, 'total_returns_egp': 0,
        'avg_roi': 0, 'level': 'bronze', 'pending_withdrawals': 0,
        'created_at': None,
    }


@app.route('/api/me/investor-wallet', methods=['GET'])
@token_required
def get_investor_wallet():
    rate = get_rate()
    # Reading ANOTHER investor's wallet by name is an admin-only privilege — it
    # must use the same authority as every other admin decision, otherwise a
    # split-identity row (dashboard_role='admin') reads any wallet it names.
    if is_admin_scope(g.user):
        investor_name = request.args.get('investor_name', '').strip()
        owner_user_id = None
    else:
        investor_name = wallet_owner_name(g.user)
        owner_user_id = g.user.id
    if not investor_name:
        return jsonify(empty_wallet_payload())
    wallet = get_or_create_wallet(investor_name, owner_user_id)
    payload = sync_wallet(wallet)
    db.session.commit()
    return jsonify(serialize_wallet(payload['wallet'], rate, payload['avg_roi'], payload['pending_withdrawals']))

@app.route('/api/investor/withdraw', methods=['POST'])
@token_required
def request_withdrawal():
    rate = get_rate()
    # A MONEY WRITE keyed by the same wallet name — it must not accept a
    # self-chosen display name either (it would both mint a wallet and file a
    # withdrawal request against whatever name collided).
    investor_name = wallet_owner_name(g.user)
    if not investor_name:
        return jsonify({'error': 'هذا الحساب غير مرتبط بمحفظة مستثمر'}), 400
    wallet = get_or_create_wallet(investor_name, g.user.id)
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
    # Same wallet-minting hazard as /me/investor-wallet: this route also CREATES
    # a row. Same key, same two locks; [] for anyone without one (the portal
    # already renders an empty badge list fine).
    investor_name = wallet_owner_name(g.user)
    if not investor_name:
        return jsonify([])
    wallet = get_or_create_wallet(investor_name, g.user.id)
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
# Same deal-sheet data, plus an expected_return_value derived from the course's
# REAL revenue. Verified: no caller at all in dashboard-cloud/dashboard-api.js or
# index.html (grep «investment-recommendation» → 0 hits), so nothing can break.
@roles_required('admin', 'investor')
def ai_investment_recommendation():
    opportunities = InvestmentOpportunity.query.order_by(InvestmentOpportunity.created_at.desc()).all()
    course_lookup = {course.id: course for course in Course.query.all()}
    if not opportunities:
        return jsonify({'title': 'لا توجد فرص مطروحة الآن', 'message': 'أضف أول فرصة استثمارية لتظهر التوصيات الذكية.', 'opportunity_id': None})
    # Third wallet-MINTING path (it calls get_or_create_wallet). Same key as
    # /me/investor-wallet and /investor/badges — admin-set link only, so this
    # route can no longer create a row under a self-chosen display name either.
    investor_name = wallet_owner_name(g.user)
    wallet = None
    avg_roi = 0
    if investor_name:
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
@roles_required('admin')               # profit shares of ANY course — no frontend caller outside admin
def get_revenue_split(id):
    course = Course.query.get_or_404(id)
    split = get_course_split(course.id)
    db.session.commit()
    return jsonify(serialize_split(split))

@app.route('/api/courses/<int:id>/revenue-split', methods=['PUT'])
@token_required
@roles_required('admin')               # trainer/platform/investor profit shares — admin only
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
@roles_required('admin', 'employee')
def ai_models():
    return jsonify(ai_models_payload())


def _extract_json_block(text):
    """Pull the first JSON object out of an AI reply (models sometimes wrap it in prose)."""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find('{'), text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


# AI helper for course creation: trainer/admin types a short idea → AI drafts the course
# (title, description, level, duration, outline) to prefill the "create on academy" form.
@app.route('/api/courses/ai-draft', methods=['POST'])
@token_required
@roles_required('admin', 'trainer', 'employee')
def ai_course_draft():
    idea = ((request.json or {}).get('idea') or '').strip()
    if not idea:
        return jsonify({'error': 'اكتب فكرة الدورة الأول'}), 400
    provider = next((k for k, c in AI_PROVIDERS.items() if os.environ.get(c['env_key'])), None)
    if not provider:
        return jsonify({'error': 'مفيش مفتاح AI متظبط على الخادم (زي ANTHROPIC_API_KEY).'}), 503
    cfg = AI_PROVIDERS[provider]
    model = os.environ.get(cfg['model_env'], cfg['default_model'])
    system_prompt = (
        'أنت مساعد لإنشاء دورات تدريبية قانونية لمنصة "البروفيسور". المستخدم سيكتب فكرة بسيطة، '
        'وأنت ترجع JSON فقط بدون أي كلام خارجه، بالشكل التالي:\n'
        '{"title": "عنوان جذاب ومحدد", "description": "وصف تسويقي مختصر جملتين أو ثلاث", '
        '"level": "beginner أو intermediate أو expert", "duration_hours": عدد, "duration_minutes": عدد, '
        '"outline": ["محور 1", "محور 2", "محور 3"]}\n'
        'اكتب بالعربية الفصحى المبسطة. اجعل المحاور بين 4 و8 محاور عملية.'
    )
    try:
        api_key = os.environ[cfg['env_key']]
        if provider == 'anthropic':
            text = call_anthropic(api_key, model, system_prompt, f'فكرة الدورة: {idea}')
        elif provider == 'openai':
            text = call_openai_compatible('https://api.openai.com/v1', api_key, model, system_prompt, f'فكرة الدورة: {idea}')
        else:
            text = call_openai_compatible('https://api.deepseek.com/v1', api_key, model, system_prompt, f'فكرة الدورة: {idea}')
    except Exception:
        return jsonify({'error': 'تعذر توليد المسودة بالـ AI، جرّب تاني'}), 502
    draft = _extract_json_block(text)
    if not isinstance(draft, dict) or not draft.get('title'):
        return jsonify({'error': 'الـ AI رجّع رد غير متوقع، جرّب تاني أو عدّل الفكرة'}), 502
    return jsonify({'draft': draft})

def generate_ai_snapshot():
    """Generate a structured data snapshot for AI consumption."""
    rate = get_rate()
    viewer_role = user_dashboard_role(g.user) if getattr(g, 'user', None) else 'admin'
    # No g.user = an internal/cron caller that already passed its own gate.
    viewer = getattr(g, 'user', None)
    is_admin = is_admin_scope(viewer) if viewer else True
    revenues = Revenue.query.all()
    expenses = Expense.query.filter_by(is_business=True).all()
    payouts = Payout.query.filter(Payout.status != 'waived').all()
    cash_transactions = CashTransaction.query.order_by(CashTransaction.date.desc()).all()
    campaigns = Campaign.query.all()
    courses = Course.query.all()
    assets = Asset.query.all()
    forecasts = ForecastMonth.query.order_by(ForecastMonth.month.asc()).limit(6).all()

    # This snapshot is the whole ledger in one response — revenues, expenses, payouts,
    # the cash box and the assets. It scoped `trainer`/`investor` with the loose
    # containment rule (bypassable by a self-chosen display name) and did not scope
    # `employee` AT ALL, handing the read-only staff role every figure the finance
    # module is supposed to withhold from it. Now: admin scope → everything; the two
    # money roles → their own rows via the strict entitlement rule; anyone else → nothing.
    if is_admin:
        pass
    elif viewer_role == 'trainer':
        courses = [course for course in courses if entitlement_name_matches(course.trainer_name, viewer)]
        course_ids = {course.id for course in courses}
        course_titles = {(course.title or '').strip() for course in courses}
        revenues = [item for item in revenues if item.course_id in course_ids or any(title and title in (item.description or '') for title in course_titles)]
        payouts = [item for item in payouts if payout_visible_to(item, viewer)]
        expenses = [item for item in expenses if any(title and (title in (item.description or '') or title in (item.notes or '')) for title in course_titles)]
        campaigns = [item for item in campaigns if item.course_id in course_ids]
        cash_transactions = []
        assets = []
    elif viewer_role == 'investor':
        investments = [item for item in Investment.query.all() if investment_visible_to(item, viewer)]
        course_ids = {item.course_id for item in investments}
        courses = [course for course in courses if course.id in course_ids]
        course_titles = {(course.title or '').strip() for course in courses}
        revenues = [item for item in revenues if item.course_id in course_ids or any(title and title in (item.description or '') for title in course_titles)]
        payouts = []
        expenses = [item for item in expenses if any(title and (title in (item.description or '') or title in (item.notes or '')) for title in course_titles)]
        campaigns = [item for item in campaigns if item.course_id in course_ids]
        cash_transactions = []
        assets = []
    else:
        # employee / viewer / anything unrecognised: no money at all.
        revenues, expenses, payouts, cash_transactions = [], [], [], []
        campaigns, courses, assets, forecasts = [], [], [], []

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
@roles_required('admin', 'employee')
def ai_snapshot():
    return jsonify(generate_ai_snapshot())

@app.route('/api/ai/ask', methods=['POST'])
@token_required
@roles_required('admin')
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
@roles_required('admin')
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
@roles_required('admin', 'employee')
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
# NOTIFICATIONS — real pending events that drive the dashboard bell.
# Aggregates ONLY live events from real tables / the platform bridge.
# Returns [] (empty) when nothing is pending. No hardcoded/fake items.
# ============================================================

def _bridge_get(path, params=None):
    """Best-effort GET against the platform bridge. Returns parsed JSON or None on
    any failure (no secret configured, network error, non-200). Never raises —
    notifications must degrade gracefully when the bridge is unreachable."""
    if not PLATFORM_METRICS_SECRET:
        return None
    try:
        r = requests.get(
            f"{PLATFORM_API_URL}{path}",
            params=params or {},
            headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
            timeout=8,
        )
    except Exception:
        return None
    if r.status_code != 200:
        return None
    try:
        return r.json() if r.content else None
    except Exception:
        return None


def _bridge_list(payload, *keys):
    """Pull a list out of a bridge payload that may be a bare list or a dict
    wrapping the list under one of `keys` (e.g. 'applications', 'items', 'users')."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in keys:
            v = payload.get(k)
            if isinstance(v, list):
                return v
    return []


@app.route('/api/notifications', methods=['GET'])
@token_required
def notifications():
    """Aggregate REAL pending events into a notification list + unread count.
    Each item: {id, title, detail, kind, route, when, unread}.
    Computed live from real tables (and the platform bridge); [] when nothing pending."""
    # STAFF-ONLY CONTENT, but NOT a 403. The bell lives in the app shell, which
    # every role renders, and its loader has no error branch — a 403 turned a
    # trainer's click into a red failure state. An empty list is the same
    # information (there is nothing here for you) with no broken screen.
    # The gate stays server-side: the items below name real people and amounts.
    if not role_grants(g.user, 'admin', 'employee'):
        return jsonify({'count': 0, 'total': 0, 'items': []})   # same shape as the real reply

    items = []

    # 1) Unreplied contact messages (local table — always available).
    for m in (Message.query.filter_by(status='new')
              .order_by(Message.created_at.desc()).limit(20).all()):
        items.append({
            'id': f'message:{m.id}',
            'title': 'رسالة جديدة من نموذج التواصل',
            'detail': f'{m.name or "زائر"}: {(m.topic or m.body or "")[:80]}',
            'kind': 'message',
            'route': '/messages',
            'when': m.created_at.isoformat() if m.created_at else None,
            'unread': True,
        })

    # 2) Pending investor withdrawal requests (local table).
    for w in (WithdrawalRequest.query.filter_by(status='pending')
              .order_by(WithdrawalRequest.requested_at.desc()).limit(20).all()):
        wallet = InvestorWallet.query.get(w.wallet_id)
        items.append({
            'id': f'withdrawal:{w.id}',
            'title': 'طلب سحب بانتظار المراجعة',
            'detail': f'{(wallet.investor_name if wallet else "مستثمر")} — {round(w.amount or 0, 2)} USD',
            'kind': 'withdrawal',
            'route': '/investors',
            'when': w.requested_at.isoformat() if w.requested_at else None,
            'unread': True,
        })

    # 3) Pending trainer applications (platform bridge — best effort).
    trainer_payload = _bridge_get('/api/bridge/trainer-applications', {'status': 'pending'})
    for app_item in _bridge_list(trainer_payload, 'applications', 'items', 'data'):
        if not isinstance(app_item, dict):
            continue
        status = (app_item.get('status') or 'pending').strip().lower()
        if status not in ('', 'pending'):
            continue
        aid = app_item.get('id') or app_item.get('application_id') or app_item.get('_id')
        who = app_item.get('name') or app_item.get('full_name') or app_item.get('email') or 'متقدّم'
        items.append({
            'id': f'trainer-app:{aid}',
            'title': 'طلب انضمام مدرب جديد',
            'detail': f'{who} بانتظار الموافقة',
            'kind': 'trainer_application',
            'route': '/approvals',
            'when': app_item.get('created_at') or app_item.get('submitted_at'),
            'unread': True,
        })

    # 4) Pending program / course requests (platform bridge — best effort).
    program_payload = _bridge_get('/api/bridge/program-requests', {'status': 'pending'})
    for req in _bridge_list(program_payload, 'requests', 'items', 'data'):
        if not isinstance(req, dict):
            continue
        status = (req.get('status') or 'pending').strip().lower()
        if status not in ('', 'pending'):
            continue
        rid = req.get('id') or req.get('request_id') or req.get('_id')
        title = req.get('title') or req.get('program') or req.get('course') or 'برنامج'
        who = req.get('requester') or req.get('name') or req.get('email') or ''
        detail = f'{title}{(" — " + who) if who else ""}'.strip()
        items.append({
            'id': f'program-req:{rid}',
            'title': 'طلب برنامج / دورة بانتظار المراجعة',
            'detail': detail,
            'kind': 'program_request',
            'route': '/approvals',
            'when': req.get('created_at') or req.get('requested_at'),
            'unread': True,
        })

    # 5) Recent platform signups (informational — best effort).
    users_payload = _bridge_get('/api/bridge/users', {'limit': 5, 'sort': 'recent'})
    for u in _bridge_list(users_payload, 'users', 'items', 'data')[:5]:
        if not isinstance(u, dict):
            continue
        uid = u.get('id') or u.get('user_id') or u.get('_id') or u.get('email')
        who = u.get('name') or u.get('full_name') or u.get('email') or 'مستخدم جديد'
        items.append({
            'id': f'signup:{uid}',
            'title': 'تسجيل جديد على المنصة',
            'detail': f'{who} أنشأ حسابًا',
            'kind': 'signup',
            'route': '/people',
            'when': u.get('created_at') or u.get('joined_at'),
            'unread': False,  # informational, not an action item
        })

    # Newest first; rows without a timestamp sink to the bottom.
    items.sort(key=lambda x: x.get('when') or '', reverse=True)
    unread = sum(1 for it in items if it.get('unread'))
    return jsonify({'count': unread, 'total': len(items), 'items': items})


# ============================================================
# GOALS AI ADVISOR — grounded guidance for next-period targets.
# Reads the SAME real numbers /api/dashboard exposes (revenue, students,
# courses, growth, finance). Uses the configured AI provider if available;
# otherwise a deterministic, data-driven heuristic. Never fabricated.
# ============================================================

def _goals_real_metrics():
    """Collect the real performance numbers used by /api/dashboard, plus
    month-over-month growth, into a compact dict for the advisor."""
    rate = get_rate()
    revenues = Revenue.query.all()
    expenses = Expense.query.filter_by(is_business=True).all()
    payouts = Payout.query.filter(Payout.status != 'waived').all()
    courses = Course.query.all()

    total_revenue = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in revenues)
    total_expenses = sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses) + payout_total(payouts, rate)
    net_profit = total_revenue - total_expenses
    total_students = sum(c.students_count or 0 for c in courses)
    active_courses = sum(1 for c in courses if (c.status or '') in ('active', 'completed'))

    # Month-over-month revenue from the same monthly rows the dashboard uses.
    monthly_rows = monthly_financial_rows(revenues, expenses, payouts, rate)
    months = [r for r in monthly_rows if r.get('month')]
    last_rev = months[-1]['revenue'] if months else 0
    prev_rev = months[-2]['revenue'] if len(months) >= 2 else 0
    if prev_rev > 0:
        growth_pct = round((last_rev - prev_rev) / prev_rev * 100, 1)
    elif last_rev > 0:
        growth_pct = 100.0
    else:
        growth_pct = 0.0

    return {
        'total_revenue_egp': round(total_revenue),
        'total_expenses_egp': round(total_expenses),
        'net_profit_egp': round(net_profit),
        'total_students': total_students,
        'total_courses': len(courses),
        'active_courses': active_courses,
        'last_month_revenue_egp': round(last_rev),
        'prev_month_revenue_egp': round(prev_rev),
        'revenue_growth_pct': growth_pct,
        'exchange_rate': rate,
    }


def _goals_heuristic(m):
    """Deterministic, data-grounded advisor when no AI key is configured.
    Every number is derived from the real metrics in `m`."""
    growth = m['revenue_growth_pct']
    base_rev = m['last_month_revenue_egp'] or m['total_revenue_egp']

    insights = []
    if m['total_revenue_egp'] == 0:
        insights.append('لا توجد إيرادات مسجّلة بعد — الهدف الأول هو إغلاق أول عملية بيع وتسجيلها في الإيرادات.')
    if m['net_profit_egp'] < 0:
        insights.append(f'صافي الربح سالب حاليًا ({m["net_profit_egp"]:,} ج.م) — راقب المصروفات الثابتة والاشتراكات الشهرية.')
    if growth < 0:
        insights.append(f'إيراد الشهر الأخير انخفض بنسبة {abs(growth)}% عن الشهر السابق — راجع قنوات التسويق والتحويل.')
    elif growth > 0:
        insights.append(f'الإيراد ينمو بنسبة {growth}% شهريًا — حافظ على الزخم وزِد الطاقة الاستيعابية للدورات.')
    if m['total_courses'] > 0 and m['total_students'] / max(1, m['total_courses']) < 10:
        insights.append('متوسط عدد الطلاب لكل دورة منخفض — ركّز على ملء الدورات الحالية قبل إطلاق دورات جديدة.')
    if not insights:
        insights.append('الأرقام مستقرة — استهدف نموًا تدريجيًا بنسبة 20% في الإيراد والطلاب للشهر القادم.')

    # Targets: grow declining/flat metrics by 20%, sustain healthy growth.
    rev_factor = 1.2 if growth >= 0 else 1.1  # gentler push when declining
    rev_target = round(base_rev * rev_factor) if base_rev else round(m['total_expenses_egp'] * 1.1)
    student_target = max(m['total_students'] + 5, round(m['total_students'] * 1.2)) if m['total_students'] else 10
    course_target = max(m['active_courses'] + 1, round(m['active_courses'] * 1.2)) if m['active_courses'] else 1

    suggested_targets = [
        {
            'label': 'إيراد الشهر القادم (ج.م)',
            'current': base_rev,
            'target': rev_target,
            'rationale': f'استهداف نمو {"20%" if growth >= 0 else "10%"} بناءً على إيراد آخر شهر مُسجَّل.'
                          if base_rev else 'تغطية المصروفات الحالية + هامش 10% كنقطة تعادل أولى.',
        },
        {
            'label': 'إجمالي الطلاب',
            'current': m['total_students'],
            'target': student_target,
            'rationale': 'زيادة 20% أو +5 طلاب على الأقل لتوسيع القاعدة الطلابية.',
        },
        {
            'label': 'الدورات النشطة',
            'current': m['active_courses'],
            'target': course_target,
            'rationale': 'إطلاق دورة إضافية مع الحفاظ على امتلاء الدورات الحالية.',
        },
    ]

    if growth >= 0:
        headline = f'الأداء إيجابي — استهدف إيراد {rev_target:,} ج.م الشهر القادم'
    else:
        headline = f'الإيراد يتراجع — هدف تعافٍ متحفّظ عند {rev_target:,} ج.م'

    return {
        'headline': headline,
        'insights': insights,
        'suggested_targets': suggested_targets,
        'source': 'heuristic',
        'metrics': m,
    }


@app.route('/api/ai/goals-advisor', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def ai_goals_advisor():
    """AI guidance for next-period targets, grounded in REAL platform numbers.
    Shape: { headline, insights:[...], suggested_targets:[{label,current,target,rationale}],
             source:'ai'|'heuristic', metrics:{...} }."""
    m = _goals_real_metrics()
    heuristic = _goals_heuristic(m)  # deterministic baseline + safe fallback

    provider = next((k for k, c in AI_PROVIDERS.items() if os.environ.get(c['env_key'])), None)
    if not provider:
        return jsonify(heuristic)

    cfg = AI_PROVIDERS[provider]
    model = os.environ.get(cfg['model_env'], cfg['default_model'])
    system_prompt = (
        'أنت مستشار نمو لشركة "البروفيسور" (منصة تعليم قانوني مصرية). '
        'ستحصل على أرقام أداء حقيقية. حلّلها واقترح أهدافًا واقعية للشهر القادم. '
        'استخدم الأرقام الفعلية فقط ولا تختلق بيانات. أعد JSON فقط بدون أي نص خارجه بالشكل:\n'
        '{"headline": "جملة موجزة", "insights": ["ملاحظة 1", "ملاحظة 2"], '
        '"suggested_targets": [{"label": "اسم المؤشر", "current": رقم, "target": رقم, "rationale": "السبب"}]}\n'
        'اجعل الأهداف مبنية على الأرقام (مثلًا نمو ~20% للمؤشرات الصحية، تعافٍ متحفّظ للمتراجعة).'
    )
    user_content = (
        'الأرقام الحقيقية الحالية:\n'
        + json.dumps(m, ensure_ascii=False, indent=2)
        + '\n\nاقترح الأهداف بناءً على هذه الأرقام فقط.'
    )
    try:
        api_key = os.environ[cfg['env_key']]
        if provider == 'anthropic':
            text = call_anthropic(api_key, model, system_prompt, user_content)
        elif provider == 'openai':
            text = call_openai_compatible('https://api.openai.com/v1', api_key, model, system_prompt, user_content)
        else:
            text = call_openai_compatible('https://api.deepseek.com/v1', api_key, model, system_prompt, user_content)
    except Exception:
        return jsonify(heuristic)  # AI unreachable → grounded heuristic

    parsed = _extract_json_block(text)
    if not isinstance(parsed, dict) or not parsed.get('suggested_targets'):
        return jsonify(heuristic)  # unexpected reply → grounded heuristic

    # Always attach the real metrics + mark the source so the client knows it's grounded.
    parsed.setdefault('headline', heuristic['headline'])
    parsed.setdefault('insights', heuristic['insights'])
    parsed['source'] = 'ai'
    parsed['metrics'] = m
    return jsonify(parsed)

# ============================================================
# AI TEAM (D7) — one agent per business function + a master aggregator.
# Each agent = one server-side LLM call (reuses the /api/ai plumbing above) over a
# real data bundle. Reports persist in AgentReport so the view renders cheaply.
# Modes: on-demand (buttons) now; n8n can POST /api/ai/agents/run?agent=all daily.
# The platform-chat hand-off (P15) reaches these agents through the shared
# chat_insights (demand) + Message (contact) tables — Incoming/Sales read them.
# ============================================================

# Ordered registry — id → Arabic label + persona (LLM role) + one-line description.
AI_AGENTS = [
    {'id': 'articles',   'label': 'المقالات والمحتوى', 'persona': 'محرر محتوى ومسؤول تحرير',
     'desc': 'المسودّات المطلوب اعتمادها وفجوات التغطية.'},
    {'id': 'seo',        'label': 'تحسين الظهور (SEO/AEO)',
     'persona': 'خبير SEO وتحسين الظهور في محركات البحث ومحركات الذكاء الاصطناعي',
     'desc': 'جودة المقالات لمحركات البحث والذكاء الاصطناعي، ومتابعة النشر اليومي.'},
    {'id': 'automation', 'label': 'رصد الأتمتة', 'persona': 'مهندس أتمتة عمليات',
     'desc': 'العمليات المتكرّرة في سجل العمليات المرشّحة للأتمتة (n8n).'},
    {'id': 'sales',      'label': 'المبيعات', 'persona': 'مدير مبيعات',
     'desc': 'العملاء المحتملون، الصفقات المتعثّرة، والخطوة التالية.'},
    {'id': 'marketing',  'label': 'التسويق', 'persona': 'مدير تسويق',
     'desc': 'أي شريحة/دولة نستهدف بناءً على الطلب والحملات.'},
    {'id': 'platform',   'label': 'إدارة المنصة', 'persona': 'مدير منصة',
     'desc': 'الشذوذ، الاعتمادات المعلّقة، وصحة المنصة.'},
    {'id': 'topics',     'label': 'المواضيع', 'persona': 'مسؤول تحرير المواضيع',
     'desc': 'المواضيع/السلاسل التالية للكتابة من الطلب الحقيقي.'},
    {'id': 'incoming',   'label': 'تحليل الوارد', 'persona': 'محلل بيانات الطلب',
     'desc': 'رايحين فين / جايين منين / عايزين إيه — من الشات.'},
    {'id': 'dev',        'label': 'التطوير', 'persona': 'مسؤول هندسة',
     'desc': 'الأعطال، الدين التقني، وصحة الأنظمة.'},
    {'id': 'finance',    'label': 'المالية', 'persona': 'مدير مالي',
     'desc': 'التدفّق النقدي، التوقّع، والمخاطر.'},
    {'id': 'master',     'label': 'الصورة الكاملة (Master)', 'persona': 'كبير المستشارين',
     'desc': 'تجميع كل التقارير في صورة واحدة + أهم ٣ إجراءات.'},
]
AI_AGENT_IDS = [a['id'] for a in AI_AGENTS]
AI_AGENT_MAP = {a['id']: a for a in AI_AGENTS}


def _agent_action_counts(limit=800):
    """Aggregate recent AuditLog rows for the automation-spotter agent."""
    rows = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    by_action, by_actor = {}, {}
    for r in rows:
        by_action[r.action] = by_action.get(r.action, 0) + 1
        by_actor[r.actor_email] = by_actor.get(r.actor_email, 0) + 1
    return {
        'total': len(rows),
        'by_action': sorted([{'action': k, 'count': v} for k, v in by_action.items()], key=lambda x: -x['count']),
        'by_actor': sorted([{'actor': k, 'count': v} for k, v in by_actor.items()], key=lambda x: -x['count'])[:10],
    }


_SEO_COMPETITORS = re.compile(r'coursera|udemy|udacity|edx|linkedin|youtube|يوتيوب|كورسيرا|يوديمي', re.I)


def _seo_scorecard(a):
    """Deterministic SEO/AEO checks on ONE platform article (dict from /bridge/articles).
    Returns a scorecard {score 0-100, issues[]} — the objective 'verification' the founder asked
    for; the agent's LLM then turns the aggregate into a readable report + fix list."""
    title = (a.get('title') or '').strip()
    body = a.get('body') or ''
    meta = (a.get('meta_description') or '').strip()
    kws = a.get('keywords') or []
    faq = a.get('faq') or []
    words = len(re.findall(r'\S+', body))
    h2 = len(re.findall(r'(?m)^##\s', body))
    score, issues = 100, []
    if not (20 <= len(title) <= 70):
        issues.append('طول العنوان غير مثالي (٢٠-٧٠ حرفًا)'); score -= 8
    if not meta:
        issues.append('لا يوجد وصف ميتا (meta description)'); score -= 20
    elif not (110 <= len(meta) <= 165):
        issues.append('طول وصف الميتا غير مثالي (١١٠-١٦٥ حرفًا)'); score -= 8
    if len(kws) < 3:
        issues.append('كلمات مفتاحية قليلة (أقل من ٣)'); score -= 15
    if words < 300:
        issues.append('المقال قصير جدًا (أقل من ٣٠٠ كلمة)'); score -= 22
    elif words < 600:
        issues.append('المقال أقصر من المثالي (أقل من ٦٠٠ كلمة)'); score -= 8
    if h2 < 2:
        issues.append('بنية عناوين ضعيفة (أقل من عنوانين فرعيين)'); score -= 12
    if not faq:
        issues.append('لا يوجد قسم أسئلة شائعة (مهم لمحركات الذكاء الاصطناعي)'); score -= 15
    if kws and not any((str(k).split() or [''])[0] and (str(k).split()[0] in title) for k in kws):
        issues.append('الكلمة المفتاحية غير ظاهرة في العنوان'); score -= 6
    if _SEO_COMPETITORS.search(body):
        issues.append('⚠️ يذكر منصة منافسة (ممنوع) — يحتاج تصحيحًا فوريًا'); score -= 35
    if re.search(r'https?://', body):
        issues.append('يحتوي روابط خارجية'); score -= 8
    return {
        'id': a.get('id'), 'title': title[:80], 'status': a.get('status'), 'category': a.get('category'),
        'score': max(0, min(100, score)), 'words': words, 'h2': h2,
        'has_faq': bool(faq), 'keywords_count': len(kws), 'issues': issues[:6],
    }


def _seo_bundle():
    """Audit the LIVE published blog (what's actually on elprofessor.net — the persistent corpus we
    MONITOR) + count platform drafts still awaiting approval (the pre-publish quality gate)."""
    # 1) live published blog articles — the real, persistent corpus the agent monitors day to day
    try:
        live = (Article.query.filter_by(status='published')
                .order_by(Article.published_at.desc().nullslast(), Article.created_at.desc()).limit(150).all())
    except Exception:
        live = []
    cards = [_seo_scorecard({
        'id': a.id, 'title': a.title, 'status': 'published', 'category': a.cat,
        'body': '\n'.join(_article_body_list(a)),  # newline-join so the (?m)^##  heading regex matches blocks
        'meta_description': a.meta_description or a.excerpt or '',
        'keywords': _json_list(a.keywords), 'faq': _json_faq(a.faq),
    }) for a in live]
    scores = [c['score'] for c in cards]
    pub_dates = sorted([a.published_at.isoformat() for a in live if a.published_at], reverse=True)
    issue_freq = {}
    for c in cards:
        for it in c['issues']:
            issue_freq[it] = issue_freq.get(it, 0) + 1
    # 2) platform drafts still awaiting the founder's approval (not yet on the site)
    plat = (_bridge_get('/api/bridge/articles', {'limit': 60, 'status': 'draft'}) or {}).get('articles') or []
    return {
        'live_published_articles': len(cards),
        'awaiting_approval_platform_drafts': len(plat),
        'avg_seo_score': round(sum(scores) / len(scores), 1) if scores else None,
        'passing_80plus': sum(1 for s in scores if s >= 80),
        'needs_work_below_60': sum(1 for s in scores if s < 60),
        'competitor_mentions': sum(1 for c in cards if any('منافسة' in i for i in c['issues'])),
        'weakest_articles': sorted(cards, key=lambda c: c['score'])[:8],
        'common_issues': sorted(
            [{'issue': k, 'count': v} for k, v in issue_freq.items()], key=lambda x: -x['count'])[:6],
        'recent_published_dates': pub_dates[:10],
    }


def _agent_bundle(agent):
    """Build the real data bundle handed to an agent's LLM call. Best-effort — every
    source degrades to None/0 instead of raising, so an agent still runs offline."""
    b = {}
    if agent == 'seo':
        b['seo'] = _seo_bundle()
    # Shared chat-demand insights (P15 hand-off) — used by several agents.
    if agent in ('sales', 'marketing', 'topics', 'incoming'):
        ci = _bridge_get('/api/bridge/chat-insights', {'limit': 1500}) or {}
        keys = ('total', 'by_segment', 'by_country', 'by_category', 'by_subcategory',
                'by_intent', 'needs_expert', 'anonymous', 'authed', 'unmet',
                'expert_opinions', 'recent')
        demand = {k: ci.get(k) for k in keys if k in ci}
        if isinstance(demand.get('recent'), list):
            demand['recent'] = demand['recent'][:20]   # cap prompt size
        b['demand'] = demand
    if agent == 'articles':
        b['articles'] = {
            'total': Article.query.count(),
            'published': Article.query.filter_by(status='published').count(),
            'drafts': Article.query.filter_by(status='draft').count(),
            'recent': [{'title': a.title, 'status': a.status, 'cat': a.cat}
                       for a in Article.query.order_by(Article.created_at.desc()).limit(15).all()],
        }
        b['topics_board'] = _bridge_get('/api/bridge/topics') or None
    if agent == 'automation':
        b['audit'] = _agent_action_counts()
    if agent == 'sales':
        b['courses'] = {
            'total': Course.query.count(),
            'paid': Course.query.filter((Course.price_egp > 0) | (Course.price_usd > 0)).count(),
            'total_students': int(sum((c.students_count or 0) for c in Course.query.all())),
        }
        b['new_messages'] = Message.query.filter_by(status='new').count()
    if agent == 'marketing':
        try:
            b['marketing'] = generate_ai_snapshot().get('marketing')
        except Exception:
            b['marketing'] = None
    if agent == 'platform':
        b['metrics'] = _bridge_get('/api/admin/metrics') or None
        b['courses'] = {
            'dashboard_count': Course.query.count(),
            'active': Course.query.filter_by(status='active').count(),
        }
        b['pending'] = {
            'trainer_apps': (_bridge_get('/api/bridge/trainer-applications', {'status': 'pending'}) or {}).get('count'),
            'program_requests': (_bridge_get('/api/bridge/program-requests', {'status': 'pending'}) or {}).get('count'),
            'open_disputes': Dispute.query.filter(Dispute.decision.is_(None)).count(),
            'new_messages': Message.query.filter_by(status='new').count(),
        }
    if agent == 'incoming':
        b['new_messages'] = Message.query.filter_by(status='new').count()
    if agent == 'dev':
        b['health'] = {
            'platform_linked': bool(PLATFORM_METRICS_SECRET),
            'platform_reachable': (_bridge_get('/api/admin/metrics') is not None),
            'ai_configured': bool(next((k for k, c in AI_PROVIDERS.items() if os.environ.get(c['env_key'])), None)),
            'ai_errors_recent': AILog.query.filter(AILog.response.like('ERROR:%')).count(),
            'open_disputes': Dispute.query.filter(Dispute.decision.is_(None)).count(),
        }
    if agent == 'finance':
        try:
            snap = generate_ai_snapshot()
            b['financials'] = snap.get('financials')
            b['cashflow'] = snap.get('cashflow')
            b['forecast'] = snap.get('forecast')
        except Exception:
            b['financials'] = None
    return b


def _master_bundle():
    """Master reads the latest report of every other agent (not raw data)."""
    reports = {}
    for aid in AI_AGENT_IDS:
        if aid == 'master':
            continue
        row = _latest_agent_report(aid)
        if row:
            reports[aid] = {
                'label': AI_AGENT_MAP[aid]['label'],
                'summary': row.summary,
                'actions': _json_list(row.actions_json),
            }
    return {'reports': reports}


def _json_list(raw):
    try:
        val = json.loads(raw) if raw else []
        return [str(x) for x in val] if isinstance(val, list) else []
    except Exception:
        return []


def _json_faq(raw):
    """Parse a stored JSON faq → [{q,a}] (for FAQPage JSON-LD). Never raises."""
    try:
        val = json.loads(raw) if raw else []
    except Exception:
        return []
    out = []
    if isinstance(val, list):
        for it in val:
            if isinstance(it, dict) and it.get('q') and it.get('a'):
                out.append({'q': str(it['q']), 'a': str(it['a'])})
    return out[:8]


def _latest_agent_report(agent):
    return (AgentReport.query.filter_by(agent=agent)
            .order_by(AgentReport.created_at.desc()).first())


def _bundle_highlights(bundle):
    """Flatten a bundle into honest numeric bullets — used only for the data-only
    fallback so a report NEVER fabricates a narrative when the AI is unavailable."""
    out = []
    def walk(prefix, val, depth):
        if depth > 2 or len(out) >= 12:
            return
        if isinstance(val, dict):
            for k, v in val.items():
                walk((prefix + ' · ' if prefix else '') + str(k), v, depth + 1)
        elif isinstance(val, list):
            out.append(f"{prefix}: {len(val)} عنصر")
        elif isinstance(val, bool):
            out.append(f"{prefix}: {'نعم' if val else 'لا'}")
        elif isinstance(val, (int, float)):
            out.append(f"{prefix}: {val}")
    walk('', bundle, 0)
    return out[:12]


def _agent_llm(persona, bundle):
    """One LLM call for an agent. Returns the raw text or None when no key is set."""
    provider = next((k for k, c in AI_PROVIDERS.items() if os.environ.get(c['env_key'])), None)
    if not provider:
        return None
    cfg = AI_PROVIDERS[provider]
    model = os.environ.get(cfg['model_env'], cfg['default_model'])
    system_prompt = (
        f'أنت {persona} ضمن فريق ذكاء اصطناعي يدير شركة "البروفيسور" (منصة تعليم قانوني '
        'مصرية). ستحصل على بيانات حقيقية عن الشركة. حلّلها بإيجاز شديد باللغة العربية. '
        'استخدم الأرقام الفعلية فقط ولا تختلق أي بيانات غير موجودة. أعد JSON فقط بدون أي '
        'نص خارجه بالشكل:\n'
        '{"summary": "جملتان موجزتان عن الوضع", '
        '"bullets": ["ملاحظة مبنية على رقم", "..."], '
        '"actions": ["إجراء عملي مقترح", "..."]}\n'
        'اجعل bullets بين 2 و5، و actions بين 1 و3.'
    )
    user_content = 'البيانات الحقيقية:\n' + json.dumps(bundle, ensure_ascii=False, indent=2)
    api_key = os.environ[cfg['env_key']]
    if provider == 'anthropic':
        return call_anthropic(api_key, model, system_prompt, user_content)
    if provider == 'openai':
        return call_openai_compatible('https://api.openai.com/v1', api_key, model, system_prompt, user_content)
    return call_openai_compatible('https://api.deepseek.com/v1', api_key, model, system_prompt, user_content)


def _run_agent(agent):
    """Build the bundle, call the LLM, persist an AgentReport, return the serialized report.
    On any AI failure it persists an HONEST data-only report (source='data') — never a
    fabricated narrative."""
    meta = AI_AGENT_MAP.get(agent)
    if not meta:
        return None
    bundle = _master_bundle() if agent == 'master' else _agent_bundle(agent)
    summary, bullets, actions, source = '', [], [], 'data'
    try:
        text = _agent_llm(meta['persona'], bundle)
    except Exception:
        text = None
    parsed = _extract_json_block(text) if text else None
    if isinstance(parsed, dict) and (parsed.get('summary') or parsed.get('bullets')):
        summary = str(parsed.get('summary') or '')[:2000]
        bullets = [str(x)[:400] for x in (parsed.get('bullets') or []) if str(x).strip()][:8]
        actions = [str(x)[:400] for x in (parsed.get('actions') or []) if str(x).strip()][:5]
        source = 'ai'
    else:
        # Honest fallback — real numbers, no invented analysis.
        summary = ('تعذّر توليد تحليل بالذكاء الآن (المفتاح غير مهيّأ أو الخدمة غير متاحة). '
                   'هذه أرقام حقيقية بلا تحليل نصّي.')
        bullets = _bundle_highlights(bundle) or ['لا توجد بيانات كافية بعد لهذا الوكيل.']
        actions = []
        source = 'data'
    row = AgentReport(
        agent=agent,
        summary=summary,
        bullets_json=json.dumps(bullets, ensure_ascii=False),
        actions_json=json.dumps(actions, ensure_ascii=False),
    )
    db.session.add(row)
    db.session.commit()
    return _serialize_report(agent, row, source=source)


def _serialize_report(agent, row, source=None):
    meta = AI_AGENT_MAP.get(agent, {})
    base = {
        'agent': agent,
        'label': meta.get('label', agent),
        'desc': meta.get('desc', ''),
        'summary': None,
        'bullets': [],
        'actions': [],
        'created_at': None,
        'source': source,
    }
    if row:
        base.update({
            'summary': row.summary,
            'bullets': _json_list(row.bullets_json),
            'actions': _json_list(row.actions_json),
            'created_at': row.created_at.isoformat() if row.created_at else None,
        })
    return base


@app.route('/api/ai/agents', methods=['GET'])
@token_required
@roles_required('admin')
def ai_agents_list():
    """Latest report per agent (D7). Renders cheap from persisted AgentReport rows;
    agents with no report yet come back with null summary so the card still shows."""
    return jsonify({
        'agents': [_serialize_report(a['id'], _latest_agent_report(a['id'])) for a in AI_AGENTS],
        'ai_configured': bool(next((k for k, c in AI_PROVIDERS.items() if os.environ.get(c['env_key'])), None)),
    })


@app.route('/api/ai/agents/run-cron', methods=['POST'])
def ai_agents_run_cron():
    """n8n (secret-gated): DAILY autonomous run of the AI team — so the SEO agent verifies article
    quality + monitors publishing every day with nobody logging in. ?agent=seo|all (default all)."""
    secret = request.headers.get('X-ELP-Metrics-Secret', '')
    if not (PLATFORM_METRICS_SECRET and secret and secrets.compare_digest(secret, PLATFORM_METRICS_SECRET)):
        return jsonify({'error': 'unauthorized'}), 401
    agent = (request.args.get('agent') or (request.json or {}).get('agent') or 'all').strip().lower()
    ran = []
    try:
        if agent == 'all':
            for aid in AI_AGENT_IDS:
                if aid != 'master':
                    _run_agent(aid); ran.append(aid)
            _run_agent('master'); ran.append('master')
        elif agent in AI_AGENT_MAP:
            _run_agent(agent); ran.append(agent)
        else:
            return jsonify({'error': 'unknown agent'}), 400
    except Exception:
        logging.getLogger(__name__).exception('ai_agents_run_cron failed')
        return jsonify({'ok': False, 'ran': ran}), 200  # never 5xx to the cron
    _audit('ai.agents_run_cron', target=agent, meta={'ran': len(ran)})
    return jsonify({'ok': True, 'ran': ran})


@app.route('/api/ai/agents/run', methods=['POST'])
@token_required
@roles_required('admin')
def ai_agents_run():
    """Regenerate one agent (?agent=sales), all agents (?agent=all → each + master),
    or the master aggregator (?agent=master). Persists fresh reports and returns them."""
    agent = (request.args.get('agent') or (request.json or {}).get('agent') or 'all').strip().lower()
    if agent == 'all':
        results = []
        for aid in AI_AGENT_IDS:
            if aid == 'master':
                continue
            results.append(_run_agent(aid))
        results.append(_run_agent('master'))   # master last — aggregates the fresh set
        _audit('ai.agents_run', target='all', meta={'count': len(results)})
        return jsonify({'agents': [r for r in results if r]})
    if agent not in AI_AGENT_MAP:
        return jsonify({'error': 'وكيل غير معروف'}), 400
    report = _run_agent(agent)
    _audit('ai.agent_run', target=agent)
    return jsonify({'agents': [report] if report else []})

# ============================================================
# SEED DATA
# ============================================================

# REAL, substantive, SEO-friendly Arabic blog articles — seeded PUBLISHED so the marketing
# blog (elprofessor.net) is never empty and survives redeploys. Idempotent: guarded by title,
# so a reboot never duplicates them. On-brand for البروفيسور: legal training + AI-in-law +
# human-tempered legal tech + genuine legal explainers. image_url stays None on purpose — the
# marketing site renders a graceful themed gradient hero when there is no cover image (no
# fabricated/broken image URLs).
_SEED_ARTICLES = [
    {
        'title': 'تعديلات قانون الشركات ٢٠٢٦: ما الذي تغيّر عمليًّا؟',
        'cat': 'قانون الشركات', 'kicker': 'تشريعات', 'tone': 't1', 'date': '٢٨ يونيو ٢٠٢٦',
        'by': 'الذكاء + رأي خبير قانون شركات',
        'excerpt': 'قراءة مبسّطة لأبرز تعديلات قانون الشركات لعام ٢٠٢٦ وأثرها المباشر على التأسيس والحوكمة وحقوق الشركاء.',
        'body': [
            'شهد قانون الشركات لعام ٢٠٢٦ حزمة تعديلات تمسّ التأسيس والحوكمة وحقوق الشركاء. في هذا المقال نقرأ أبرزها بلغة عملية، ونوضّح أثرها المباشر على من يفكّر في تأسيس شركة أو في إدارة واحدة قائمة بالفعل.',
            '## أولًا: تبسيط إجراءات التأسيس',
            'خفّضت التعديلات الحدّ الأدنى لرأس المال في عدّة أنماط، وأتاحت التأسيس الإلكتروني الكامل دون الحاجة إلى الحضور الورقي. النتيجة العملية أن زمن بدء النشاط تقلّص من أسابيع إلى أيام، مع خفض واضح في التكلفة على روّاد الأعمال.',
            '## ثانيًا: حوكمة أوضح لمجلس الإدارة',
            'أصبح توثيق قرارات المجلس في سجلّ معتمد التزامًا لا خيارًا، مع فصلٍ أوضح بين الملكية والإدارة. الهدف حماية صغار الشركاء وضمان الشفافية في القرارات الكبرى التي تمسّ مصير الشركة.',
            '## ثالثًا: حماية الشريك الأقلية',
            'منحت التعديلات الشركاء الأقلية حقوقًا أوسع في الاطّلاع والاعتراض على الصفقات ذات المصلحة. هذه نقطة جوهرية لأي مستثمر يدخل بحصّة غير مسيطرة، إذ توازن بين سلطة الأغلبية وحقّ الأقلية في الحماية.',
            '## الخلاصة العملية',
            'إن كنت بصدد التأسيس فاستفد من المسار الإلكتروني المبسّط. وإن كنت تدير شركة قائمة فراجع لائحة الحوكمة لديك لتتوافق مع المتطلبات الجديدة قبل انتهاء المهلة الانتقالية. ولأي حالة خاصة، تبقى استشارة خبير قانوني هي ما يترجم النصّ العام إلى قرار يخصّك أنت.',
        ],
    },
    {
        'title': 'حماية حقوق العامل في عقود العمل: دليل عملي',
        'cat': 'قانون العمل', 'kicker': 'حقوق', 'tone': 't2', 'date': '٢٥ يونيو ٢٠٢٦',
        'by': 'الذكاء + رأي خبير عمالي',
        'excerpt': 'ما الذي يضمنه القانون للعامل داخل عقد العمل، وكيف تقرأ بنوده قبل التوقيع لتحمي حقّك بثقة.',
        'body': [
            'عقد العمل هو خطّ الدفاع الأول عن حقوق العامل. كثيرون يوقّعون دون قراءة متأنّية، فيفاجَأون لاحقًا ببنودٍ تُضعِف موقفهم. هذا الدليل يوضّح أهمّ ما ينبغي الانتباه إليه قبل التوقيع وبعده.',
            '## البنود التي لا يصحّ التنازل عنها',
            'الأجر، وساعات العمل، والإجازات، ومدّة الإخطار، وسبب الفصل المشروع — هذه حقوق يكفلها القانون ولا يجوز أن يُسقِطها العقد. أيّ بند يتنازل عنها يُعدّ باطلًا حتى لو وقّع عليه الطرفان.',
            '## الفصل التعسّفي',
            'ينشأ الفصل التعسّفي حين يُنهى العقد دون سبب مشروع أو دون اتّباع الإجراءات القانونية. في هذه الحالة يستحقّ العامل تعويضًا يقدّره القانون، ويقع عبء إثبات مشروعية الفصل على صاحب العمل لا على العامل.',
            '## مستحقّات نهاية الخدمة',
            'تشمل مكافأة نهاية الخدمة، ورصيد الإجازات غير المستخدمة، وأيّ مستحقّات متأخّرة. احتفظ دائمًا بنسخة موقّعة من العقد وبكشوف الأجر، فهي أدلّتك الأقوى عند أيّ نزاع.',
            '## متى تلجأ للخبير؟',
            'قبل التوقيع على عقد غامض، أو عند الفصل، أو عند الامتناع عن صرف المستحقّات — استشارة خبير عمالي مبكرًا توفّر عليك أشهرًا من التقاضي. القاعدة الذهبية: وثّق كلّ شيء كتابةً، ولا تعتمد على الوعود الشفهية.',
        ],
    },
    {
        'title': 'التوقيع الإلكتروني وحجيته القانونية',
        'cat': 'المعاملات الإلكترونية', 'kicker': 'دليل عملي', 'tone': 't3', 'date': '٢٢ يونيو ٢٠٢٦',
        'by': 'الذكاء + رأي خبيرة معاملات رقمية',
        'excerpt': 'متى يكون التوقيع الإلكتروني مُلزِمًا كالتوقيع الورقي، وما الشروط التي تمنحه حجّيته الكاملة أمام القضاء.',
        'body': [
            'مع تحوّل الأعمال إلى الرقمية، صار التوقيع الإلكتروني أداةً يومية في إبرام العقود. لكن السؤال الذي يشغل الجميع: هل له الحجّية نفسها التي للتوقيع الورقي؟ الإجابة القصيرة: نعم، بشروط.',
            '## ما هو التوقيع الإلكتروني؟',
            'هو كلّ بيانات في شكل إلكتروني تُستخدَم لتحديد هويّة الموقّع والتعبير عن رضاه بمضمون المحرَّر. يتدرّج من التوقيع البسيط (صورة أو اسم) إلى التوقيع الرقمي المعتمد الموثّق بشهادة تصديق.',
            '## شروط الحجّية الكاملة',
            'يكتسب التوقيع الإلكتروني حجّيته حين يرتبط بالموقّع وحده، ويكون تحت سيطرته المنفردة، ويمكن كشف أيّ تعديل يطرأ على المحرَّر بعد توقيعه، وأن يصدر عبر جهة تصديق معتمدة. باجتماع هذه الشروط يتساوى مع التوقيع الخطّي في الإثبات.',
            '## أين يُقبَل وأين يُتحفَّظ؟',
            'يُقبَل التوقيع الإلكتروني في أغلب العقود التجارية والمدنية والمعاملات البنكية. لكن تبقى بعض التصرّفات — كالمحرّرات الرسمية وبعض عقود الأحوال الشخصية — بحاجة إلى شكل خاصّ ينصّ عليه القانون صراحةً.',
            '## نصيحة عملية',
            'قبل الاعتماد على التوقيع الإلكتروني في عقد مهمّ، تأكّد من أنّ مزوّد الخدمة معتمد، ومن حفظ سجلّ التوقيع (طابع الوقت وسلسلة التحقّق). فالحجّية لا تُثبَت بالتوقيع وحده، بل بقدرتك على إثبات سلامته عند النزاع.',
        ],
    },
    {
        'title': 'الذكاء الاصطناعي في مهنة المحاماة: أداة تُضاعِف الخبير لا تستبدله',
        'cat': 'التقنية القانونية', 'kicker': 'رؤية', 'tone': 't4', 'date': '١٩ يونيو ٢٠٢٦',
        'by': 'فريق البروفيسور',
        'excerpt': 'كيف يعيد الذكاء الاصطناعي تشكيل العمل القانوني، ولماذا يبقى الخبير البشري هو من يقود القرار.',
        'body': [
            'يثير الذكاء الاصطناعي في المجال القانوني موجةً من الحماس والقلق معًا. البعض يراه تهديدًا للمهنة، والبعض يراه ثورة. الحقيقة أقرب إلى منظورٍ ثالث: أداةٌ تُضاعِف قدرة الخبير، لا تحلّ محلّه.',
            '## أين يتفوّق الذكاء الاصطناعي؟',
            'في المهام كثيفة التكرار: البحث في آلاف السوابق، وتلخيص المستندات الطويلة، ومراجعة العقود بحثًا عن بنود ناقصة أو متعارضة. ما كان يستغرق ساعات صار يُنجَز في دقائق، فيتفرّغ المحامي لما يتطلّب حكمًا وخبرة.',
            '## حدود الآلة',
            'لا يملك النموذج مسؤولية مهنية، ولا يفهم سياق الموكّل الإنساني، ولا يتحمّل تبعات خطأٍ في الرأي. كما أنّه قد «يهلوس» مراجع غير موجودة. لذلك يبقى التحقّق البشري شرطًا لا تنازل عنه قبل أيّ استخدام فعلي.',
            '## نموذج «الإنسان الخبير يقود»',
            'الصيغة الأنجع أن يصوغ الذكاء المسوّدة والبحث الأوّلي، ثم يراجعها خبيرٌ مختصّ ويقرّها ويتحمّل مسؤوليتها. هذا بالضبط ما نبني عليه في البروفيسور: الذكاء يضاعف السرعة، والخبير يضمن الجودة والمساءلة.',
            '## ماذا يعني ذلك للمحامي؟',
            'المحامي الذي يتقن توظيف هذه الأدوات سيتقدّم على من يتجاهلها — لا لأنّ الآلة أذكى منه، بل لأنّه سيخدم موكّليه أسرع وأدقّ. المستقبل ليس «محامٍ مقابل ذكاء اصطناعي»، بل «محامٍ يستعين بالذكاء» في مواجهة من لا يفعل.',
        ],
    },
    {
        'title': 'لماذا لم يعد التدريب القانوني المستمر رفاهية؟',
        'cat': 'التدريب القانوني', 'kicker': 'قيمة مضافة', 'tone': 't5', 'date': '١٦ يونيو ٢٠٢٦',
        'by': 'فريق البروفيسور',
        'excerpt': 'التشريعات تتغيّر بسرعة والممارسة تتعقّد — والتدريب المستمرّ صار شرطًا للبقاء المهني لا ترفًا.',
        'body': [
            'اعتاد كثير من المحامين أن يكتفوا بما درسوه في الجامعة وبما راكموه من خبرة عملية. لكنّ وتيرة تغيّر التشريعات وتعقيد المعاملات جعلت هذا الاكتفاء مخاطرة حقيقية على المهنة وعلى الموكّل.',
            '## القانون يتحرّك أسرع من أيّ وقت مضى',
            'تُصدر الجهات التشريعية تعديلات متلاحقة في الشركات والعمل والضرائب والمعاملات الرقمية. المحامي الذي لا يتابع هذه التحديثات قد يبني رأيه على نصٍّ لم يعد ساريًا — وهو خطأ مكلِف لا يُغتفَر أمام الموكّل.',
            '## التخصّص صار ميزة تنافسية',
            'لم يعد العميل يبحث عن «محامٍ عام»، بل عن خبيرٍ في مسألته تحديدًا. التدريب المتخصّص هو ما يحوّل الممارس العامّ إلى مرجعٍ في مجاله، ويرفع قيمة خدمته وسعرها في السوق.',
            '## المهارات لا تقلّ أهمية عن المعرفة',
            'صياغة العقود، والتفاوض، وإدارة الملفات رقميًّا، وتوظيف أدوات الذكاء الاصطناعي — كلّها مهارات لا تُكتسَب بالصدفة بل بتدريبٍ مقصود ومنهجي، وهي التي تصنع الفارق في الممارسة اليومية.',
            '## من أين تبدأ؟',
            'ابدأ بتشخيص فجواتك: أين تشعر بأنّك أقلّ ثقة؟ ثمّ اختر مسارًا مركّزًا بدل التشتّت. في البروفيسور نبني مسارات تدريبية يقودها خبراء ممارسون، مصمَّمة لتترجم المعرفة إلى قرارٍ عملي في ملفّاتك — لأنّ الاستثمار في مهارتك هو أضمن استثمار لمستقبلك المهني.',
        ],
    },
]


def _seed_published_articles():
    """Bootstrap-only seed of the demo blog articles: runs ONLY when the blog is completely empty,
    so a brand-new deploy isn't blank — but once there is ANY article (real content or a kept demo),
    it never re-seeds. This makes deleting the demo articles PERMANENT (a redeploy won't resurrect
    them, now that the blog DB is on a persistent volume)."""
    base = datetime.datetime.utcnow()
    created = 0
    if Article.query.first():
        return 0  # blog already has content → do not (re-)seed demos
    for i, s in enumerate(_SEED_ARTICLES):
        if Article.query.filter_by(title=s['title']).first():
            continue
        art = Article(
            title=s['title'][:500],
            excerpt=s.get('excerpt', ''),
            cat=s.get('cat'),
            kicker=s.get('kicker'),
            date=s.get('date'),
            by=s.get('by'),
            tone=s.get('tone'),
            image_url=None,  # graceful: site renders a themed gradient hero when no cover image
            body=json.dumps(s.get('body', []), ensure_ascii=False),
            status='published',
        )
        art.published_at = base - datetime.timedelta(minutes=i)
        db.session.add(art)
        created += 1
    if created:
        db.session.commit()
        logger.info("Seeded %d published blog articles.", created)
    return created


def seed():
    """Seed initial data"""
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@elprofessor.com').lower().strip()
    admin_password = os.environ.get('ADMIN_PASSWORD')
    existing_admin = User.query.filter_by(email=admin_email).first()
    if not existing_admin:
        if admin_password:
            # First boot with a configured password → create the admin.
            admin = User(
                email=admin_email,
                password_hash=generate_password_hash(admin_password, method='pbkdf2:sha256'),
                name=os.environ.get('ADMIN_NAME', 'عبدالرحمن'),
                role='admin',
                dashboard_role='admin',   # explicit: the column default is 'viewer' now
                is_active=True,
            )
            db.session.add(admin)
        else:
            # No password configured → do NOT seed a default-password admin.
            logger.warning(
                "ADMIN_PASSWORD is not set and no admin (%s) exists — skipping admin seed. "
                "Set ADMIN_PASSWORD and redeploy to provision the admin account.",
                admin_email,
            )
    elif admin_password:
        # Admin exists and a password is configured → rotate it to match the env
        # (rotating ADMIN_PASSWORD + redeploy rotates the live password).
        existing_admin.password_hash = generate_password_hash(admin_password, method='pbkdf2:sha256')

    db.session.commit()
    print("✅ Admin/user initialization complete")

    # Real published blog articles — idempotent (guarded by title). Guarantees the
    # marketing blog (elprofessor.net) is never empty and survives redeploys.
    try:
        _seed_published_articles()
    except Exception as e:
        logger.warning("Seeding published articles failed (non-fatal): %s", e)

    # NOTE: restore_real_business_data() was REMOVED — the partners' amounts and
    # foundation assets it seeded were fabricated/wrong (founder confirmed). Real
    # business data must now be entered manually via the admin endpoints. The data
    # MODELS (Partner/Asset/Expense/CashTransaction/…) remain intact for that.


def reset_business_data():
    """ENV-GATED full reset of business/test data. Runs ONLY when RESET_BUSINESS_DATA
    is truthy; otherwise a no-op.

    WIPES (all rows): Partner, Asset, Expense, Revenue, CashTransaction, Payout,
    EscrowSession, Dispute, Message, WithdrawalRequest, Investment,
    InvestmentOpportunity, InvestorWallet, InvestorBadge, RevenueSplit, Campaign,
    Course, AILog — plus any leftover 'seed:v3%'/'real:v1%' tagged rows.

    KEEPS: User (but deletes every non-admin user and re-seeds the admin fresh from
    ADMIN_EMAIL/ADMIN_PASSWORD so login still works); Setting (packages_config /
    packages and all other settings); ForecastMonth (الأهداف والتوقعات — forecast +
    goals/targets data).
    """
    flag = (os.environ.get('RESET_BUSINESS_DATA') or '').strip().lower()
    if flag not in ('1', 'true', 'yes', 'on'):
        logger.info("RESET_BUSINESS_DATA not set — skipping business data reset.")
        return

    logger.warning("RESET_BUSINESS_DATA is on — wiping business/test data.")
    summary = {}

    # --- Delete dependent/child rows first to respect FKs, then parents. ---
    wipe_models = [
        # children / leaf tables first
        ('disputes', Dispute),
        ('escrow_sessions', EscrowSession),
        ('investor_badges', InvestorBadge),
        ('withdrawal_requests', WithdrawalRequest),
        ('investments', Investment),
        ('investor_wallets', InvestorWallet),
        ('investment_opportunities', InvestmentOpportunity),
        ('revenue_splits', RevenueSplit),
        ('payouts', Payout),
        ('cash_transactions', CashTransaction),
        ('expenses', Expense),
        ('revenues', Revenue),       # depends on courses/campaigns → delete before them
        ('messages', Message),
        ('campaigns', Campaign),
        ('courses', Course),
        ('partners', Partner),
        ('assets', Asset),
        ('ai_logs', AILog),
    ]
    for table_name, model in wipe_models:
        try:
            n = model.query.delete()
        except Exception:
            n = 0
        summary[table_name] = n
    db.session.commit()

    # --- Sweep any leftover seed:v3% / real:v1% tagged rows across tables that have
    # a `notes` column (defensive — most are already gone above). ---
    tagged_removed = 0
    for model in (Partner, Asset, Expense, Revenue, CashTransaction, Payout,
                  Campaign, Course, Investment, InvestmentOpportunity, RevenueSplit):
        if not hasattr(model, 'notes'):
            continue
        for prefix in (f'{SEED_PREFIX}%', f'{REAL_PREFIX}%'):
            try:
                tagged_removed += model.query.filter(model.notes.like(prefix)).delete(
                    synchronize_session=False
                )
            except Exception:
                pass
    if tagged_removed:
        db.session.commit()
    summary['tagged_seed_real_rows_swept'] = tagged_removed

    # --- Users: delete every NON-admin user, KEEP the table, re-seed admin fresh. ---
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@elprofessor.com').lower().strip()
    admin_password = os.environ.get('ADMIN_PASSWORD')
    non_admin_deleted = 0
    for u in User.query.all():
        if (u.email or '').lower().strip() == admin_email:
            continue
        db.session.delete(u)
        non_admin_deleted += 1
    db.session.commit()
    summary['non_admin_users_deleted'] = non_admin_deleted

    existing_admin = User.query.filter_by(email=admin_email).first()
    if admin_password:
        if existing_admin:
            existing_admin.password_hash = generate_password_hash(
                admin_password, method='pbkdf2:sha256')
            existing_admin.role = 'admin'
            existing_admin.dashboard_role = 'admin'   # keep the two identity fields in sync
            existing_admin.is_active = True
            summary['admin'] = f'reset password for {admin_email}'
        else:
            db.session.add(User(
                email=admin_email,
                password_hash=generate_password_hash(admin_password, method='pbkdf2:sha256'),
                name=os.environ.get('ADMIN_NAME', 'عبدالرحمن'),
                role='admin',
                dashboard_role='admin',   # explicit: the column default is 'viewer' now
                is_active=True,
            ))
            summary['admin'] = f'created fresh admin {admin_email}'
        db.session.commit()
    else:
        summary['admin'] = 'ADMIN_PASSWORD not set — admin left unchanged'
        logger.warning(
            "RESET_BUSINESS_DATA on but ADMIN_PASSWORD unset — admin password NOT reset.")

    kept = {
        'users': 'KEPT table; non-admins deleted; admin re-seeded from env',
        'settings': f'KEPT (incl. {PACKAGES_SETTING_KEY}/packages)',
        'forecast_months': 'KEPT (الأهداف والتوقعات — forecast + goals/targets)',
    }
    logger.warning("RESET_BUSINESS_DATA complete. Wiped: %s | Kept: %s", summary, kept)
    print(f"✅ RESET_BUSINESS_DATA complete. Wiped={summary} Kept={kept}")


def seed_demo():
    """Seed DEMO/business data (founder's sample financials, cap-table, payouts,
    forecasts, assets, investments — all tagged notes LIKE 'seed:v3%').

    Runs ONLY when SEED_DEMO_DATA == 'true'. This is OFF by default so production
    boots do NOT re-inject fake financials/ownership on every redeploy.
    """
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
    print("✅ Demo data seeded successfully")

def ensure_runtime_schema():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    with db.engine.begin() as connection:
        if 'users' in existing_tables:
            user_columns = {column['name'] for column in inspector.get_columns('users')}
            if 'dashboard_role' not in user_columns:
                # NO DB-level DEFAULT here, deliberately. SQLite backfills an
                # ADDed column with its DEFAULT, so the previous
                # `DEFAULT 'admin'` promoted EVERY pre-existing row to admin and
                # the follow-up `WHERE dashboard_role IS NULL` then matched
                # nothing. Adding the column NULL-able and copying `role` into it
                # keeps the row's real, pre-existing role as the source of truth.
                connection.execute(text("ALTER TABLE users ADD COLUMN dashboard_role VARCHAR(50)"))
            # Backfill is OUTSIDE the add-column branch and matches only rows the
            # column carries no decision for (NULL/empty), so it is idempotent,
            # safe to re-run on every boot, and can never downgrade a real admin.
            # NOTE: a database ALREADY migrated by the buggy version cannot be
            # repaired automatically — a row reading role='trainer',
            # dashboard_role='admin' is indistinguishable from a deliberate
            # promotion, so it is left alone (role_grants() denies admin to such
            # split rows, which contains the damage). See the founder SQL in the
            # handover notes to inspect and correct those rows by hand.
            connection.execute(text(
                "UPDATE users SET dashboard_role = role "
                "WHERE role IS NOT NULL AND TRIM(role) <> '' "
                "AND (dashboard_role IS NULL OR TRIM(dashboard_role) = '')"
            ))
            if 'linked_to_name' not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN linked_to_name VARCHAR(255)"))
            if 'preferred_currency' not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN preferred_currency VARCHAR(10) DEFAULT 'AUTO'"))
        if 'articles' in existing_tables:
            article_columns = {column['name'] for column in inspector.get_columns('articles')}
            if 'image_url' not in article_columns:
                try:
                    connection.execute(text("ALTER TABLE articles ADD COLUMN image_url TEXT"))
                except Exception:
                    pass
            for _seo_col in ('meta_description', 'keywords', 'faq', 'target_audience'):
                if _seo_col not in article_columns:
                    try:
                        connection.execute(text(f"ALTER TABLE articles ADD COLUMN {_seo_col} TEXT"))
                    except Exception:
                        pass
        if 'courses' in existing_tables:
            course_columns = {column['name'] for column in inspector.get_columns('courses')}
            if 'lms_instructor_email' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN lms_instructor_email VARCHAR(255)"))
            if 'lms_synced' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN lms_synced BOOLEAN DEFAULT 0"))
            if 'open_for_investment' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN open_for_investment BOOLEAN DEFAULT 0"))
            if 'lms_sales_count' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN lms_sales_count INTEGER DEFAULT 0"))
            if 'lms_revenue' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN lms_revenue FLOAT DEFAULT 0"))
            if 'lms_currency' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN lms_currency VARCHAR(8)"))
            if 'platform_course_id' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN platform_course_id VARCHAR(50)"))
            if 'platform_course_slug' not in course_columns:
                connection.execute(text("ALTER TABLE courses ADD COLUMN platform_course_slug VARCHAR(200)"))
        if 'revenues' in existing_tables:
            revenue_columns = {column['name'] for column in inspector.get_columns('revenues')}
            if 'payment_id' not in revenue_columns:
                connection.execute(text("ALTER TABLE revenues ADD COLUMN payment_id VARCHAR(255)"))
                # Partial unique index: enforce idempotency on bridge payment_ids
                # while leaving manually-entered revenues (NULL payment_id) unconstrained.
                try:
                    connection.execute(text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_revenues_payment_id "
                        "ON revenues (payment_id) WHERE payment_id IS NOT NULL"
                    ))
                except Exception:
                    # Dialects without partial-index support: fall back to a plain
                    # unique index (NULLs are distinct in SQLite/Postgres, so OK).
                    try:
                        connection.execute(text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS ux_revenues_payment_id "
                            "ON revenues (payment_id)"
                        ))
                    except Exception:
                        pass
            if 'amount_original' not in revenue_columns:
                connection.execute(text("ALTER TABLE revenues ADD COLUMN amount_original FLOAT"))
            if 'currency' not in revenue_columns:
                connection.execute(text("ALTER TABLE revenues ADD COLUMN currency VARCHAR(8)"))
            if 'needs_fx' not in revenue_columns:
                connection.execute(text("ALTER TABLE revenues ADD COLUMN needs_fx BOOLEAN DEFAULT 0"))
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

# ============================================================
# CMS / CONTENT + MESSAGES (public site feed + admin authoring)
# ============================================================

def _article_body_list(article):
    raw = getattr(article, 'body', None)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
        return [str(data)]
    except (ValueError, TypeError):
        # Legacy/plain text → split into paragraphs.
        return [p for p in str(raw).split('\n\n') if p.strip()]

def _slugify_ar(text, fallback='article'):
    """Stable, URL-friendly slug from a title. Keeps unicode word chars (incl. Arabic)
    and turns every run of other characters into a single hyphen. Empty → fallback."""
    s = (text or '').strip().lower()
    s = re.sub(r'[^\w\s-]', '', s)          # drop punctuation (keeps Arabic + latin + digits)
    s = re.sub(r'[\s_]+', '-', s).strip('-')  # whitespace/underscore runs → single hyphen
    return s or fallback


def _article_slug(article):
    """Stable per-article slug. The marketing site currently resolves articles by numeric
    `id`; `slug` is additive (SEO-friendly, stable links) and suffixed with the id so it is
    globally unique even when two titles collide."""
    base = _slugify_ar(getattr(article, 'title', None))
    return f"{base}-{article.id}" if getattr(article, 'id', None) else base


def serialize_article(article):
    return {
        'id': article.id,
        'slug': _article_slug(article),
        'title': article.title,
        'excerpt': article.excerpt or '',
        'cat': article.cat or '',
        'kicker': article.kicker or '',
        'date': article.date or '',
        'by': article.by or '',
        'tone': article.tone or None,
        'video': article.video or None,
        'image_url': article.image_url or None,
        'body': _article_body_list(article),
        'meta_description': article.meta_description or article.excerpt or '',
        'keywords': _json_list(article.keywords),
        'faq': _json_faq(article.faq),
        'target_audience': article.target_audience or 'عام',   # «الفئوية» → site audience filter
        'status': article.status or 'draft',
        'published_at': article.published_at.isoformat() if article.published_at else None,
    }

def _apply_article_fields(article, d):
    if 'title' in d:
        article.title = (d.get('title') or '').strip()
    for key in ('excerpt', 'cat', 'kicker', 'date', 'by', 'video'):
        if key in d:
            setattr(article, key, d.get(key))
    if 'tone' in d:
        # `tone` is the one article field the marketing site drops RAW into a class="..."
        # attribute (every other field is HTML-escaped there). Pin it to the known design
        # tones so it can never carry markup; anything else → None (site falls back to a
        # per-index tone). Backward-compatible: all seed/synced tones are t1..t6.
        tone = (d.get('tone') or '').strip()
        article.tone = tone if re.match(r'^t[1-6]$', tone) else None
    if 'image_url' in d:
        url = (d.get('image_url') or '').strip()
        if not url:
            article.image_url = None
        elif len(url) <= 2000 and re.match(r'^https?://', url, re.IGNORECASE):
            article.image_url = url
        # else: silently ignore an invalid/oversized URL (keep existing value)
    if 'body' in d:
        body = d.get('body')
        if isinstance(body, str):
            body = [p for p in body.split('\n\n') if p.strip()]
        if not isinstance(body, list):
            body = []
        article.body = json.dumps([str(x) for x in body], ensure_ascii=False)
    # SEO/AEO metadata (so «اعمل مقال» articles carry the same meta/keywords/FAQ → JSON-LD on the site)
    if 'meta_description' in d:
        article.meta_description = (d.get('meta_description') or '')[:400]
    if 'keywords' in d:
        kw = d.get('keywords')
        article.keywords = json.dumps([str(x) for x in kw][:12], ensure_ascii=False) if isinstance(kw, list) else None
    if 'faq' in d:
        fq = d.get('faq')
        article.faq = json.dumps([f for f in fq if isinstance(f, dict) and f.get('q') and f.get('a')][:8],
                                 ensure_ascii=False) if isinstance(fq, list) else None
    if 'target_audience' in d:
        article.target_audience = (d.get('target_audience') or 'عام')[:60]  # «الفئوية»

def _no_store(resp):
    resp.headers['Cache-Control'] = 'no-store'
    resp.headers['Pragma'] = 'no-cache'
    return resp

# ——— AI content sync: pull platform-generated article drafts → the blog (this SQLite feed the
# marketing site reads). Feature explainers publish straight away; news/legal analyses stay DRAFT
# for the founder to approve. The platform is just the generator; THIS is the single blog store. ———
_AR_MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
              'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
_AR_DIGITS = str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')
_ART_CAT_LABEL = {'feature': 'عن المنصة', 'news': 'تحليل قانوني', 'law': 'قانوني',
                  'guide': 'دليل', 'regulation': 'تشريعات', 'other': 'مقال'}


def _ar_date_today():
    n = datetime.datetime.utcnow()
    return f"{n.day} {_AR_MONTHS[n.month - 1]} {n.year}".translate(_AR_DIGITS)


def _ar_date_from(ts):
    """Format an ISO timestamp (the platform's real created/published date) as an Arabic date."""
    if ts:
        try:
            dt = datetime.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
            return f"{dt.day} {_AR_MONTHS[dt.month - 1]} {dt.year}".translate(_AR_DIGITS)
        except Exception:
            pass
    return _ar_date_today()


def _strip_inline_md(s):
    s = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', s)   # [text](url) → text (no external links on the site)
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)           # **bold** → bold
    s = re.sub(r'__(.+?)__', r'\1', s)
    s = re.sub(r'\*(.+?)\*', r'\1', s)               # *italic* → italic
    s = re.sub(r'`(.+?)`', r'\1', s)                 # `code` → code
    s = re.sub(r'^\s*>\s?', '', s)                   # blockquote marker
    # NOTE: no html.escape here — the marketing site html-escapes every block once at render
    # (its single XSS layer). Escaping here too caused double-escaping («&quot;» showing literally).
    return s.strip()


def _md_to_blocks(md):
    """Convert the platform's markdown article body → the marketing site's block format:
      • a heading line ('# '..'###### ', even a malformed '### ## ') → '## <text>' (site renders <h2>/<h3>)
      • a bullet line ('- '/'* ') → '• <text>'
      • everything else → a paragraph (consecutive text lines merged)
    LINE-based so a heading glued to its paragraph by a single newline is SPLIT (not merged into one
    bold block), and ALL leading hash markers are stripped so no literal '#'/'##' ever renders."""
    import re
    blocks, para = [], []

    def flush():
        if para:
            blocks.append(_strip_inline_md(' '.join(para)))
            para.clear()

    for line in (md or '').replace('\r', '').split('\n'):
        ln = line.strip()
        if not ln:
            flush()
            continue
        h = re.match(r'^#{1,6}[#\s]*(\S.*?)\s*$', ln)   # heading (strips nested/extra hashes)
        b = re.match(r'^[-*•]\s+(\S.*?)\s*$', ln)        # bullet
        if h:
            flush()
            blocks.append('## ' + _strip_inline_md(h.group(1)))
        elif b:
            flush()
            blocks.append(_strip_inline_md('• ' + b.group(1)))
        else:
            para.append(ln)
    flush()
    return blocks


def _delete_platform_article(aid):
    if not aid or not PLATFORM_METRICS_SECRET:
        return
    try:
        requests.delete(f"{PLATFORM_API_URL}/api/bridge/articles/{aid}",
                        headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET}, timeout=10)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# دفع صفحات المقالات المُسبقة العرض إلى elprofessor.net
# ---------------------------------------------------------------------------
# المشكلة اللي بيحلّها: صفحات /blog/<slug> بتتعرض بالـJS. الزواحف اللي ما بتنفّذش JS
# (GPTBot و ClaudeBot و PerplexityBot و Bingbot وكل معاينات المشاركة) بتشوف قوقعة
# فاضية إلا لو فيه نسخة ثابتة في blog/_pre/<id>.html على استضافة الموقع.
#
# كان بيتشغّل بالإيد. في 2026-08-02 اتكشف إن آخر تشغيل كان 2026-07-21 ⇒ ٣٦ مقال
# (ids 78–113) وصلوا للزواحف بعنوان عام «مقال — البروفيسور» وبلا نص، بصمت، لمدة
# اتناشر يوم. الربط هنا بيمنع تكرار ده: كل مزامنة تنشر مقالًا بتدفع النسخ فورًا.
#
# ليه هنا وليس في n8n: ورك فلو المزامنة بينده /api/content/sync-cron ٦ مرات يوميًا
# بعد كل توليد مباشرة. الربط جوّه المزامنة بيخلّي التغطية تلقائية بلا أي تعديل على n8n.
#
# ⚠️ عقد السلامة: الداشبورد ده بيخدّم فيد المقالات وسايت‌ماب elprofessor.net — لو وقع،
# الموقع يفضى. علشان كده كل شيء هنا fail-soft: كل الاستيرادات كسولة، وكل فشل بيتسجّل
# ويرجع، وما بيرفعش استثناء للطلب اللي ناداه. غياب node أو paramiko أو متغيّرات SSH
# = الميزة متعطّلة والداشبورد شغّال عادي.
PRERENDER_ENABLED = os.environ.get('PRERENDER_ENABLED', 'true').strip().lower() == 'true'
PRERENDER_ORIGIN = os.environ.get('PRERENDER_ORIGIN', 'https://elprofessor.net').rstrip('/')
PRERENDER_SSH_HOST = os.environ.get('PRERENDER_SSH_HOST', '')
PRERENDER_SSH_PORT = int(os.environ.get('PRERENDER_SSH_PORT', '65002') or 65002)
PRERENDER_SSH_USER = os.environ.get('PRERENDER_SSH_USER', '')
PRERENDER_SSH_PASSWORD = os.environ.get('PRERENDER_SSH_PASSWORD', '')
PRERENDER_SITE_ROOT = os.environ.get(
    'PRERENDER_SITE_ROOT', 'domains/elprofessor.net/public_html').strip('/')
_PRERENDER_SCRIPT = os.environ.get('PRERENDER_SCRIPT', '/app/prerender.py')
_PRERENDER_HASHES = '/data/prerender-hashes.json'

_prerender_lock = None          # threading.Lock, أول استخدام
_prerender_running = False
_prerender_last = {'state': 'never-run'}


def _prerender_ready():
    """(ok, reason) — كل المتطلبات موجودة؟ بلا أي استيراد ثقيل لو الجواب لا."""
    import shutil as _sh
    if not PRERENDER_ENABLED:
        return False, 'disabled by PRERENDER_ENABLED'
    if not (PRERENDER_SSH_HOST and PRERENDER_SSH_USER and PRERENDER_SSH_PASSWORD):
        return False, 'ssh credentials not configured'
    if not os.path.isfile(_PRERENDER_SCRIPT):
        return False, 'generator missing at %s' % _PRERENDER_SCRIPT
    if not _sh.which('node'):
        return False, 'node not installed in image'
    try:
        import paramiko  # noqa: F401
    except Exception as exc:                    # noqa: BLE001
        return False, 'paramiko unavailable: %s' % exc
    return True, ''


def _prerender_feed_json():
    """نفس شكل /api/content/articles — بيتكتب لملف ويتمرّر بـ--feed-file.

    ⚠️ عمدًا مش بننده الـendpoint العام عبر HTTP: جونيكورن شغّال بـworker واحد،
    فطلب من الخدمة لنفسها جوّه معالِج طلب = قفل ميّت يعلّق الداشبورد كله."""
    items = Article.query.filter_by(status='published').order_by(
        Article.published_at.desc().nullslast(),
        Article.created_at.desc(),
    ).all()
    return json.dumps({'source': 'dashboard', 'articles': [serialize_article(a) for a in items]},
                      ensure_ascii=False)


def _prerender_push(reason=''):
    """يولّد صفحات المقالات ويرفع المتغيّر منها فقط. لا يرفع استثناءً أبدًا."""
    global _prerender_last
    import subprocess, tempfile, shutil as _sh                       # noqa: E401
    started = time.time()
    ok, why = _prerender_ready()
    if not ok:
        _prerender_last = {'state': 'skipped', 'reason': why, 'at': datetime.datetime.utcnow().isoformat()}
        app.logger.info('prerender: skipped (%s)', why)
        return _prerender_last
    tmp = tempfile.mkdtemp(prefix='prerender-')
    try:
        os.makedirs(os.path.join(tmp, 'blog', '_pre'), exist_ok=True)
        # القوالب من الموقع الحيّ — المولّد بيستخرج مُصيِّر article.html منها ويشغّله
        for name in ('article.html', 'blog.html'):
            r = requests.get('%s/%s' % (PRERENDER_ORIGIN, name), timeout=30,
                             headers={'User-Agent': 'elprofessor-prerender/1.0'})
            if r.status_code != 200:
                raise RuntimeError('template %s HTTP %s' % (name, r.status_code))
            with open(os.path.join(tmp, name), 'w', encoding='utf-8') as fh:
                fh.write(r.text)
        feed_path = os.path.join(tmp, '_feed.json')
        with open(feed_path, 'w', encoding='utf-8') as fh:
            fh.write(_prerender_feed_json())

        proc = subprocess.run(
            ['python3', _PRERENDER_SCRIPT, '--site', tmp, '--feed-file', feed_path],
            capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            # عقد المولّد all-or-nothing: أي فشل تحقّق ⇒ ما كتبش حاجة. مفيش نصف رفع.
            raise RuntimeError('generator exit %s: %s' % (
                proc.returncode, (proc.stderr or proc.stdout or '')[-600:]))

        # نرفع المتغيّر فقط — ٦ تشغيلات يوميًا × ١١٥ ملف رفعٌ كامل هدر بلا داعٍ
        try:
            with open(_PRERENDER_HASHES, encoding='utf-8') as fh:
                known = json.load(fh)
        except Exception:                        # noqa: BLE001
            known = {}
        wanted, fresh = [], {}
        for rel in ['blog.html', 'feed.xml', 'blog/_pre/manifest.txt'] + [
                'blog/_pre/' + n for n in sorted(os.listdir(os.path.join(tmp, 'blog', '_pre')))
                if n.endswith('.html')]:
            path = os.path.join(tmp, rel)
            if not os.path.isfile(path):
                continue
            with open(path, 'rb') as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            fresh[rel] = digest
            if known.get(rel) != digest:
                wanted.append(rel)

        uploaded = 0
        if wanted:
            import paramiko
            cl = paramiko.SSHClient()
            cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cl.connect(PRERENDER_SSH_HOST, port=PRERENDER_SSH_PORT, username=PRERENDER_SSH_USER,
                       password=PRERENDER_SSH_PASSWORD, timeout=30, allow_agent=False,
                       look_for_keys=False)
            try:
                sftp = cl.open_sftp()
                home = sftp.normalize('.')
                root = '%s/%s' % (home.rstrip('/'), PRERENDER_SITE_ROOT)
                for d in ('blog', 'blog/_pre'):
                    try:
                        sftp.stat('%s/%s' % (root, d))
                    except IOError:
                        sftp.mkdir('%s/%s' % (root, d))
                for rel in wanted:
                    # .tmp ثم rename: الرفع المباشر بيخلّي الملف نصّه مقروء للزاحف
                    # لو وصل طلب أثناء النقل. rename على نفس نظام الملفات ذرّي.
                    dst = '%s/%s' % (root, rel)
                    sftp.put(os.path.join(tmp, rel), dst + '.tmp')
                    try:
                        sftp.remove(dst)
                    except IOError:
                        pass
                    sftp.rename(dst + '.tmp', dst)
                    uploaded += 1
                sftp.close()
            finally:
                cl.close()
            try:
                with open(_PRERENDER_HASHES, 'w', encoding='utf-8') as fh:
                    json.dump(fresh, fh)
            except Exception:                    # noqa: BLE001
                pass                             # كاش تحسين فقط — فقدانه = رفع كامل مرة

        _prerender_last = {
            'state': 'ok', 'reason': reason, 'articles': len(fresh) - 3,
            'uploaded': uploaded, 'unchanged': len(fresh) - len(wanted),
            'seconds': round(time.time() - started, 1),
            'at': datetime.datetime.utcnow().isoformat(),
        }
        app.logger.info('prerender: ok (%s) uploaded=%s', reason, uploaded)
    except Exception as exc:                     # noqa: BLE001
        _prerender_last = {'state': 'error', 'reason': reason, 'error': str(exc)[:500],
                           'seconds': round(time.time() - started, 1),
                           'at': datetime.datetime.utcnow().isoformat()}
        app.logger.warning('prerender: FAILED (%s): %s', reason, exc)
    finally:
        _sh.rmtree(tmp, ignore_errors=True)
    return _prerender_last


def _prerender_push_async(reason=''):
    """بيرجّع فورًا. التوليد والرفع ممكن ياخدوا دقيقة، والداشبورد بـworker واحد —
    فتشغيله داخل الطلب بيجمّد فيد المقالات للموقع الحيّ طول المدة دي."""
    global _prerender_lock, _prerender_running
    import threading
    if _prerender_lock is None:
        _prerender_lock = threading.Lock()

    def run():
        global _prerender_running
        with _prerender_lock:
            _prerender_running = True
            try:
                with app.app_context():
                    _prerender_push(reason)
            finally:
                _prerender_running = False

    if _prerender_running:
        app.logger.info('prerender: already running, skipping (%s)', reason)
        return {'state': 'already-running'}
    threading.Thread(target=run, name='prerender', daemon=True).start()
    return {'state': 'started', 'reason': reason}


@app.route('/api/content/prerender-cron', methods=['POST', 'GET'])
def content_prerender_cron():
    """GET = حالة آخر تشغيل (تشخيص). POST مؤمَّن بنفس سرّ المزامنة = شغّل الآن.
    POST ?sync=1 بينتظر النتيجة — للتحقّق اليدوي بعد النشر."""
    if request.method == 'GET':
        ready, why = _prerender_ready()
        return jsonify({'ready': ready, 'reason': why or None, 'running': _prerender_running,
                        'last': _prerender_last})
    secret = request.headers.get('X-ELP-Metrics-Secret', '')
    if not (PLATFORM_METRICS_SECRET and secret
            and secrets.compare_digest(secret, PLATFORM_METRICS_SECRET)):
        return jsonify({'error': 'unauthorized'}), 401
    if (request.args.get('sync') or '') == '1':
        return jsonify(_prerender_push('manual-sync'))
    return jsonify(_prerender_push_async('manual'))


def _sync_platform_articles():
    """Import platform-generated article drafts into the blog. Returns (dict, status)."""
    if not PLATFORM_METRICS_SECRET:
        return {'error': 'الربط بالمنصة غير مضبوط'}, 503
    try:
        # ONLY unapproved DRAFTS — never pull (and then delete) the platform's own published articles.
        r = requests.get(f"{PLATFORM_API_URL}/api/bridge/articles",
                         headers={'X-ELP-Metrics-Secret': PLATFORM_METRICS_SECRET},
                         params={'status': 'draft'}, timeout=12)
        arts = (r.json() or {}).get('articles', []) if r.status_code == 200 else []
    except Exception:
        return {'error': 'تعذّر الاتصال بالمنصة'}, 502
    imported = published = drafts = 0
    for a in arts:
        title = (a.get('title') or '').strip()
        if not title:
            continue
        # already in the blog? skip — but do NOT delete the platform copy (a genuinely-different
        # article that happens to share a title must never be silently destroyed).
        if Article.query.filter_by(title=title).first():
            continue
        cat = a.get('category') or 'other'
        is_feature = (cat == 'feature')
        # Publish policy (founder chose AUTO-PUBLISH ALL, 2026-07-04): everything the daily engine
        # generates goes live on elprofessor.net automatically. Reversible without a deploy via env
        # BLOG_AUTOPUBLISH_ALL=false → falls back to the old two-stream (only feature explainers auto-
        # publish; news/legal/topic land as DRAFT for review). Rendering stays XSS-safe (blocks are
        # html-escaped at render on the site).
        autopublish_all = os.environ.get('BLOG_AUTOPUBLISH_ALL', 'true').strip().lower() == 'true'
        is_published = autopublish_all or is_feature or (a.get('status') == 'published')
        art = Article(
            title=title[:500],
            excerpt=(a.get('excerpt') or '')[:1000],
            cat=_ART_CAT_LABEL.get(cat, 'قانوني'),
            kicker='عن المنصة' if is_feature else 'تحليل قانوني',
            by=a.get('author') or 'فريق البروفيسور',
            date=_ar_date_from(a.get('published_at') or a.get('created_at')),
            body=json.dumps(_md_to_blocks(a.get('body') or ''), ensure_ascii=False),
            meta_description=(a.get('meta_description') or a.get('excerpt') or '')[:400],
            keywords=json.dumps([str(k) for k in (a.get('keywords') or [])][:12], ensure_ascii=False),
            faq=json.dumps([f for f in (a.get('faq') or []) if isinstance(f, dict) and f.get('q') and f.get('a')][:8],
                           ensure_ascii=False),
            target_audience=(a.get('target_audience') or 'عام')[:60],  # «الفئوية» → site audience filter
            status='published' if is_published else 'draft',
        )
        if is_published:
            art.published_at = datetime.datetime.utcnow()
        db.session.add(art)
        db.session.commit()
        imported += 1
        if is_published:
            published += 1
        else:
            drafts += 1
        _delete_platform_article(a.get('id'))  # only AFTER a successful import
    out = {'ok': True, 'imported': imported, 'published': published, 'drafts': drafts}
    # مقال جديد منشور = صفحة الزواحف بتاعته لسه مش موجودة على الاستضافة. الدفع هنا
    # هو اللي بيمنع تكرار انحسار يوليو ٢٠٢٦ (٣٦ مقال قواقع فاضية اتناشر يوم).
    # لاحق (Thread) عمدًا: المزامنة لازم ترجّع بسرعة، والتوليد+الرفع بياخدوا دقيقة.
    if published:
        out['prerender'] = _prerender_push_async('sync:+%d' % published)
    return out, 200


@app.route('/api/content/sync-from-platform', methods=['POST'])
@token_required
@roles_required('admin')
def content_sync_from_platform():
    """Admin button: pull any platform-generated drafts into the blog now."""
    body, status = _sync_platform_articles()
    return jsonify(body), status


@app.route('/api/content/sync-cron', methods=['POST'])
def content_sync_cron():
    """n8n (secret-gated): after a daily generation run, flush platform drafts into the blog so
    feature articles auto-publish to elprofessor.net without anyone opening the dashboard."""
    secret = request.headers.get('X-ELP-Metrics-Secret', '')
    if not (PLATFORM_METRICS_SECRET and secret and secrets.compare_digest(secret, PLATFORM_METRICS_SECRET)):
        return jsonify({'error': 'unauthorized'}), 401
    body, status = _sync_platform_articles()
    return jsonify(body), status


# Card-sized subset of serialize_article() for `?fields=summary`: everything the
# blog.html and Company-Site.html card renderers read, without the `body`/`faq`/
# `keywords` bulk that only an article page needs. `kicker`/`tone`/`video` are NOT
# optional — dropping them silently kills the card kicker line, the tone colour class
# (falls back to a positional default) and the video badge on both renderers.
_ARTICLE_SUMMARY_KEYS = ('id', 'slug', 'title', 'cat', 'by', 'date', 'excerpt', 'image_url',
                         'kicker', 'tone', 'video')


@app.route('/api/content/articles', methods=['GET'])
def public_articles_feed():
    """PUBLIC: published articles feed for the marketing site. No auth, no cache.
    Hard-pinned to published — an arbitrary ?status param must NOT leak drafts.
    Admins read every status via the gated /api/content/articles/all.
    Optional `?fields=summary` trims each article to the listing fields; without the
    param the payload keeps every key it has always had (content-loader.js unchanged)."""
    query = Article.query.filter_by(status='published')
    items = query.order_by(
        Article.published_at.desc().nullslast(),
        Article.created_at.desc(),
    ).all()
    rows = [serialize_article(a) for a in items]
    if (request.args.get('fields') or '').strip().lower() == 'summary':
        # `if k in r` on purpose: if serialize_article() ever renames/drops one of these
        # keys, a card loses one field instead of the whole PUBLIC feed 500-ing (which
        # would drop the blog to the «لا مقالات منشورة بعد» fallback for users AND Googlebot).
        rows = [{k: r[k] for k in _ARTICLE_SUMMARY_KEYS if k in r} for r in rows]
    resp = jsonify({'source': 'dashboard', 'articles': rows})
    return _no_store(resp)


@app.route('/sitemap-articles.xml', methods=['GET'])
def public_articles_sitemap():
    """PUBLIC: sitemap of every published article, served for elprofessor.net (whose
    /.htaccess 301s /sitemap-articles.xml here). The slug in <loc> comes from the SAME
    _article_slug() the feed serializes, so the clean /blog/<slug> URLs resolve.

    ⚠️ This path MUST stay indexable. If `X-Robots-Tag: noindex, nofollow` is ever added
    to the dashboard host, it has to exempt this route — see _ROBOTS_EXEMPT_PATHS."""
    items = Article.query.filter_by(status='published').order_by(
        Article.published_at.desc().nullslast(),
        Article.created_at.desc(),
    ).all()
    rows = []
    for a in items:
        loc = 'https://elprofessor.net/blog/' + quote(_article_slug(a), safe='')
        lm = a.published_at or a.created_at
        # A dateless article emits NO <lastmod> element at all: an empty <lastmod></lastmod>
        # invalidates the ENTIRE sitemap in Search Console, not just that one <url>.
        lastmod = ('<lastmod>%s</lastmod>' % lm.strftime('%Y-%m-%d')) if lm else ''
        rows.append('<url><loc>%s</loc>%s<changefreq>monthly</changefreq></url>'
                    % (xesc(loc), lastmod))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + ''.join(rows) + '</urlset>')
    return Response(xml, mimetype='application/xml')


@app.route('/api/content/articles/all', methods=['GET'])
@token_required
@roles_required('admin')
def admin_articles_all():
    items = Article.query.order_by(
        Article.created_at.desc()
    ).all()
    return jsonify({'source': 'dashboard', 'articles': [serialize_article(a) for a in items]})

@app.route('/api/content/articles', methods=['POST'])
@token_required
@roles_required('admin')
def admin_article_create():
    d = request.json or {}
    if not (d.get('title') or '').strip():
        return jsonify({'error': 'العنوان مطلوب'}), 400
    article = Article(title=(d.get('title') or '').strip(), status='draft')
    _apply_article_fields(article, d)
    article.status = 'draft'  # always created as a draft
    db.session.add(article)
    db.session.commit()
    return jsonify(serialize_article(article)), 201

@app.route('/api/content/articles/<int:id>', methods=['PUT'])
@token_required
@roles_required('admin')
def admin_article_update(id):
    article = Article.query.get_or_404(id)
    d = request.json or {}
    _apply_article_fields(article, d)
    was_published = article.status == 'published'
    if 'status' in d and (d.get('status') in ('draft', 'published')):
        article.status = d['status']
        if article.status == 'published' and not article.published_at:
            article.published_at = datetime.datetime.utcnow()
    db.session.commit()
    # أي تعديل على مقال منشور (أو نشر/سحب) يغيّر ما يجب أن تراه الزواحف
    if was_published or article.status == 'published':
        _prerender_push_async('article-update:%s' % id)
    return jsonify(serialize_article(article))

@app.route('/api/content/articles/<int:id>', methods=['DELETE'])
@token_required
@roles_required('admin')
def admin_article_delete(id):
    article = Article.query.get_or_404(id)
    _title = article.title
    _was_published = article.status == 'published'
    db.session.delete(article)
    db.session.commit()
    _audit('article.reject_delete', target=id, meta={'title': _title})
    # المولّد بيشيل ملفات _pre اللي مبقاش ليها مقال منشور (prune) — بدون الدفع هنا
    # تفضل صفحة مقال محذوف مُقدَّمة للزواحف إلى ما لا نهاية.
    if _was_published:
        _prerender_push_async('article-delete:%s' % id)
    return jsonify({'ok': True})

@app.route('/api/content/articles/<int:id>/publish', methods=['POST'])
@token_required
@roles_required('admin')
def admin_article_publish(id):
    article = Article.query.get_or_404(id)
    article.status = 'published'
    article.published_at = datetime.datetime.utcnow()
    db.session.commit()
    _audit('article.publish', target=id, meta={'title': article.title})
    _prerender_push_async('article-publish:%s' % id)
    return jsonify(serialize_article(article))

def serialize_message(m):
    return {
        'id': m.id,
        'name': m.name,
        'email': m.email,
        'phone': m.phone or '',
        'topic': m.topic or '',
        'body': m.body,
        'status': m.status or 'new',
        'created_at': m.created_at.isoformat() if m.created_at else None,
    }

@app.route('/api/messages', methods=['POST'])
def public_message_create():
    """PUBLIC: contact-form submissions from the marketing site. No auth."""
    d = request.json or {}
    # Honeypot: bots fill hidden fields. Pretend success, store nothing.
    if (d.get('website') or d.get('hp') or '').strip():
        return jsonify({'ok': True})
    name = (d.get('name') or '').strip()
    email = (d.get('email') or '').strip().lower()
    body = (d.get('body') or '').strip()
    if not name or not email or not body:
        return jsonify({'error': 'الاسم والبريد والرسالة مطلوبة'}), 400
    if '@' not in email or len(email) > 255:
        return jsonify({'error': 'بريد إلكتروني غير صالح'}), 400
    # Length cap (light spam guard).
    if len(name) > 255 or len(body) > 5000:
        return jsonify({'error': 'المحتوى طويل جدًا'}), 400
    msg = Message(
        name=name[:255],
        email=email[:255],
        phone=(d.get('phone') or '').strip()[:80] or None,
        topic=(d.get('topic') or '').strip()[:255] or None,
        body=body,
        status='new',
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/messages', methods=['GET'])
@token_required
@roles_required('admin')
def admin_messages_list():
    status = (request.args.get('status') or '').strip().lower()
    query = Message.query
    if status in ('new', 'replied'):
        query = query.filter_by(status=status)
    items = query.order_by(Message.created_at.desc()).all()
    return jsonify([serialize_message(m) for m in items])

@app.route('/api/messages/<int:id>/reply', methods=['POST'])
@token_required
@roles_required('admin')
def admin_message_reply(id):
    msg = Message.query.get_or_404(id)
    d = request.json or {}
    reply = (d.get('body') or '').strip()
    if not reply:
        return jsonify({'error': 'نص الرد مطلوب'}), 400
    msg.reply_body = reply
    msg.status = 'replied'
    msg.replied_at = datetime.datetime.utcnow()
    db.session.commit()
    # Email delivery is a stub for now — log the intent.
    logger.info("Message reply to %s (id=%s) recorded; email delivery stubbed.", msg.email, msg.id)
    return jsonify({'ok': True})

@app.route('/api/messages/<int:id>', methods=['DELETE'])
@token_required
@roles_required('admin')
def admin_message_delete(id):
    msg = Message.query.get_or_404(id)
    db.session.delete(msg)
    db.session.commit()
    return jsonify({'ok': True})

# ============================================================
# ESCROW & DISPUTES  (the founder's #1 money gap)
# ------------------------------------------------------------
# Money flow rules (server-authoritative):
#   * commission (15% default) is deducted AT RELEASE, never at hold.
#   * release is idempotent — a session can be released exactly once and
#     records exactly one commission Revenue row (guarded by revenue_id).
#   * status transitions are validated (no release of refunded, no double-dispute).
#   * employee = read-only (enforced server-side via roles_required, not just UI).
# ============================================================

ESCROW_HOLD_HOURS = 72
ESCROW_COMMISSION_CATEGORY = 'عمولة ضمان'
_ESCROW_RELEASABLE = {'held', 'confirm'}   # 'dispute' becomes releasable only after a resolution
_ESCROW_TERMINAL = {'released', 'refunded'}
# The Revenue ledger only has amount_egp/amount_usd columns, so any other currency
# would silently book commission as 0. Only accept currencies the ledger can represent.
ESCROW_SUPPORTED_CURRENCIES = {'EGP', 'USD'}

def _next_seq_id(model, prefix):
    """Generate the next zero-padded id like 'ESC-0001' for a string-PK model."""
    last = model.query.order_by(model.id.desc()).first()
    n = 0
    if last and isinstance(last.id, str) and '-' in last.id:
        try:
            n = int(last.id.split('-')[-1])
        except (ValueError, IndexError):
            n = model.query.count()
    return f'{prefix}-{n + 1:04d}'

def _add_business_days(start, days):
    d = start
    added = 0
    while added < days:
        d = d + datetime.timedelta(days=1)
        if d.weekday() < 5:   # Mon-Fri (0-4); Egypt's weekend is Fri/Sat but Mon-Fri is a safe SLA proxy
            added += 1
    return d

def _escrow_metrics_authorized():
    """Accept EITHER an admin JWT OR the shared platform metrics secret.
    Used by /escrow/hold so the platform bridge can open a hold server-to-server."""
    secret = request.headers.get('X-ELP-Metrics-Secret', '')
    if PLATFORM_METRICS_SECRET and secret and secrets.compare_digest(secret, PLATFORM_METRICS_SECRET):
        return True
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return False
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = User.query.get(data['user_id'])
        return bool(user and user.is_active and role_grants(user, 'admin'))
    except Exception:
        return False

def serialize_escrow(e, now=None):
    now = now or datetime.datetime.utcnow()
    remaining = None
    if e.release_at and e.status in ('held', 'confirm'):
        remaining = int((e.release_at - now).total_seconds())
    return {
        'id': e.id,
        'student_name': e.student_name, 'student_email': e.student_email,
        'expert_name': e.expert_name, 'expert_email': e.expert_email,
        'amount': round(e.amount or 0, 2), 'currency': e.currency,
        'commission_rate': e.commission_rate,
        'commission': e.commission, 'net': e.net,
        'status': e.status,
        'held_at': e.held_at.isoformat() if e.held_at else None,
        'release_at': e.release_at.isoformat() if e.release_at else None,
        'released_at': e.released_at.isoformat() if e.released_at else None,
        'release_seconds_remaining': remaining,
        'ref': e.ref, 'source': e.source, 'notes': e.notes,
    }

def serialize_dispute(d):
    return {
        'id': d.id, 'session_id': d.session_id, 'party': d.party,
        'reason': d.reason, 'stage': d.stage, 'amount_frozen': round(d.amount_frozen or 0, 2),
        'opened_at': d.opened_at.isoformat() if d.opened_at else None,
        'decision_sla': d.decision_sla.isoformat() if d.decision_sla else None,
        'decision': d.decision, 'split_pct': d.split_pct,
        'resolved_at': d.resolved_at.isoformat() if d.resolved_at else None,
    }

def _open_dispute_for(session_id):
    return Dispute.query.filter(
        Dispute.session_id == session_id,
        Dispute.decision.is_(None),
    ).first()

def _lock_escrow_session(sid):
    """Fetch an escrow session, taking a row lock when the dialect supports it.
    with_for_update is a no-op on SQLite (ignored), which is fine for the tests."""
    return EscrowSession.query.with_for_update().get(sid)

def _record_commission_revenue(session):
    """Record exactly one commission Revenue row for a released session.
    Idempotent: if the session already points at a revenue row, do nothing.
    The UNIQUE constraint on revenue_id makes this safe under concurrent releases —
    a racing insert raises IntegrityError, which we treat as already-recorded success."""
    if session.revenue_id:
        return Revenue.query.get(session.revenue_id)
    amount = session.commission
    rev = Revenue(
        date=datetime.date.today(),
        source='escrow_commission',
        description=f'عمولة ضمان {int((session.commission_rate or 0) * 100)}% — جلسة {session.id}',
        amount_egp=amount if (session.currency or 'EGP').upper() == 'EGP' else 0,
        amount_usd=amount if (session.currency or 'EGP').upper() == 'USD' else 0,
        client_name=session.student_name,
        payment_method='escrow',
        notes=f'{ESCROW_COMMISSION_CATEGORY} · {session.ref or ""} · صافي للخبير {session.net}',
    )
    db.session.add(rev)
    try:
        db.session.flush()
    except IntegrityError:
        # A concurrent release already booked the commission (revenue_id UNIQUE).
        # Roll back our duplicate and return the row that won the race.
        db.session.rollback()
        winner = EscrowSession.query.get(session.id)
        return Revenue.query.get(winner.revenue_id) if winner and winner.revenue_id else None
    session.revenue_id = rev.id
    return rev

@app.route('/api/escrow/hold', methods=['POST'])
def escrow_hold():
    # Admin JWT OR platform bridge secret (employees may NOT create holds).
    if not _escrow_metrics_authorized():
        return jsonify({'error': 'غير مصرح'}), 403
    d = request.json or {}
    try:
        amount = round(float(d.get('amount') or 0), 2)
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        return jsonify({'error': 'المبلغ مطلوب ويجب أن يكون أكبر من صفر'}), 400
    if not (d.get('expert_email') or d.get('expert_name')):
        return jsonify({'error': 'بيانات الخبير مطلوبة'}), 400
    currency = (d.get('currency') or 'EGP').strip().upper()[:8]
    if currency not in ESCROW_SUPPORTED_CURRENCIES:
        return jsonify({'error': f'العملة غير مدعومة — المسموح: {", ".join(sorted(ESCROW_SUPPORTED_CURRENCIES))} فقط (دفتر الإيرادات لا يمثّل غيرها)'}), 400
    now = datetime.datetime.utcnow()
    rate = d.get('commission_rate')
    try:
        rate = float(rate) if rate is not None else 0.15
    except (TypeError, ValueError):
        rate = 0.15
    rate = min(max(rate, 0.0), 1.0)
    session = EscrowSession(
        id=_next_seq_id(EscrowSession, 'ESC'),
        student_name=(d.get('student_name') or '').strip(),
        student_email=(d.get('student_email') or '').strip().lower(),
        expert_name=(d.get('expert_name') or '').strip(),
        expert_email=(d.get('expert_email') or '').strip().lower(),
        amount=amount,
        currency=currency,
        status='held',
        held_at=now,
        release_at=now + datetime.timedelta(hours=ESCROW_HOLD_HOURS),
        commission_rate=rate,
        ref=(d.get('ref') or '').strip(),
        source=(d.get('source') or 'platform').strip(),
    )
    db.session.add(session)
    db.session.commit()
    return jsonify({'message': 'تم حجز المبلغ في الضمان', 'session': serialize_escrow(session)}), 201

@app.route('/api/escrow/<sid>/release', methods=['POST'])
@token_required
@roles_required('admin')
def escrow_release(sid):
    session = _lock_escrow_session(sid)   # row lock (Postgres) so concurrent releases can't double-book
    if session is None:
        return jsonify({'error': 'الجلسة غير موجودة'}), 404
    if session.status in _ESCROW_TERMINAL:
        return jsonify({'error': 'هذه الجلسة محسومة بالفعل ولا يمكن تحريرها مرة أخرى'}), 409
    # Only from held/confirm, or a dispute that already has a resolution recorded.
    if session.status == 'dispute' and _open_dispute_for(session.id):
        return jsonify({'error': 'لا يمكن التحرير وعليها نزاع مفتوح — افصل النزاع أولًا'}), 409
    if session.status not in _ESCROW_RELEASABLE and session.status != 'dispute':
        return jsonify({'error': 'حالة غير صالحة للتحرير'}), 409
    rev = _record_commission_revenue(session)   # idempotent (IntegrityError-safe)
    session.status = 'released'
    session.released_at = datetime.datetime.utcnow()
    db.session.commit()
    return jsonify({
        'message': f'تم تحرير {session.net} للخبير (عمولة {session.commission})',
        'session': serialize_escrow(session), 'revenue_id': rev.id if rev else None,
    })

@app.route('/api/escrow/<sid>/refund', methods=['POST'])
@token_required
@roles_required('admin')
def escrow_refund(sid):
    session = EscrowSession.query.get_or_404(sid)
    if session.status in _ESCROW_TERMINAL:
        return jsonify({'error': 'هذه الجلسة محسومة بالفعل'}), 409
    if session.status == 'dispute' and _open_dispute_for(session.id):
        return jsonify({'error': 'عليها نزاع مفتوح — افصل النزاع أولًا'}), 409
    session.status = 'refunded'   # full refund to student — NO commission recorded
    db.session.commit()
    return jsonify({'message': f'تم استرداد {round(session.amount or 0, 2)} للطالب', 'session': serialize_escrow(session)})

@app.route('/api/escrow/<sid>/dispute', methods=['POST'])
@token_required
@roles_required('admin')
def escrow_dispute(sid):
    session = EscrowSession.query.get_or_404(sid)
    if session.status in _ESCROW_TERMINAL:
        return jsonify({'error': 'لا يمكن فتح نزاع على جلسة محسومة'}), 409
    if session.status == 'dispute' or _open_dispute_for(session.id):
        return jsonify({'error': 'يوجد نزاع مفتوح بالفعل على هذه الجلسة'}), 409
    d = request.json or {}
    party = (d.get('party') or '').strip().lower()
    if party not in ('student', 'expert'):
        return jsonify({'error': 'الطرف المُحتج (student/expert) مطلوب'}), 400
    now = datetime.datetime.utcnow()
    dispute = Dispute(
        id=_next_seq_id(Dispute, 'DSP'),
        session_id=session.id,
        party=party,
        reason=(d.get('reason') or '').strip(),
        stage='open',
        amount_frozen=round(session.amount or 0, 2),
        opened_at=now,
        decision_sla=_add_business_days(now, 3),
    )
    session.status = 'dispute'   # freeze
    db.session.add(dispute)
    db.session.commit()
    return jsonify({'message': 'تم تجميد المبلغ وفتح نزاع', 'dispute': serialize_dispute(dispute), 'session': serialize_escrow(session)}), 201

@app.route('/api/dispute/<did>/resolve', methods=['POST'])
@token_required
@roles_required('admin')
def dispute_resolve(did):
    dispute = Dispute.query.get_or_404(did)
    if dispute.decision:
        return jsonify({'error': 'تم فصل هذا النزاع بالفعل'}), 409
    session = _lock_escrow_session(dispute.session_id)   # row lock (Postgres) on the commission path
    if not session:
        return jsonify({'error': 'الجلسة غير موجودة'}), 404
    if session.status in _ESCROW_TERMINAL:
        return jsonify({'error': 'الجلسة محسومة بالفعل'}), 409
    d = request.json or {}
    decision = (d.get('decision') or '').strip().lower()
    if decision not in ('student', 'expert', 'split'):
        return jsonify({'error': 'القرار يجب أن يكون student أو expert أو split'}), 400

    result = {}
    if decision == 'student':
        # Full refund to the student — no commission.
        session.status = 'refunded'
        dispute.split_pct = None
        result['refunded'] = round(session.amount or 0, 2)
    elif decision == 'expert':
        # Release in the expert's favour — commission IS taken (idempotent).
        rev = _record_commission_revenue(session)
        session.status = 'released'
        session.released_at = datetime.datetime.utcnow()
        dispute.split_pct = None
        result['released_net'] = session.net
        result['commission'] = session.commission
        result['revenue_id'] = rev.id if rev else None
    else:  # split
        try:
            split_pct = float(d.get('split_pct'))
        except (TypeError, ValueError):
            return jsonify({'error': 'نسبة التقسيم (split_pct) مطلوبة للتقسيم'}), 400
        if not (0 <= split_pct <= 100):
            return jsonify({'error': 'نسبة التقسيم يجب أن تكون بين 0 و 100'}), 400
        # split_pct = share that goes to the EXPERT (post-commission on that share);
        # the remainder is refunded to the student. Commission only on the expert share.
        amount = round(session.amount or 0, 2)
        expert_gross = round(amount * split_pct / 100, 2)
        commission = round(expert_gross * (session.commission_rate or 0), 2)
        # Record commission revenue on the partial expert share (idempotent).
        if commission > 0 and not session.revenue_id:
            rev = Revenue(
                date=datetime.date.today(), source='escrow_commission',
                description=f'عمولة ضمان (تقسيم {split_pct}%) — جلسة {session.id}',
                amount_egp=commission if (session.currency or 'EGP').upper() == 'EGP' else 0,
                amount_usd=commission if (session.currency or 'EGP').upper() == 'USD' else 0,
                client_name=session.student_name, payment_method='escrow',
                notes=f'{ESCROW_COMMISSION_CATEGORY} · تقسيم · للخبير {round(expert_gross - commission, 2)}',
            )
            db.session.add(rev)
            try:
                db.session.flush()
            except IntegrityError:
                # Concurrent resolve already booked this commission (revenue_id UNIQUE) — treat as idempotent.
                db.session.rollback()
                session = EscrowSession.query.get(dispute.session_id)
                return jsonify({'message': 'تم فصل النزاع مسبقًا', 'decision': decision,
                                'result': {'revenue_id': session.revenue_id if session else None},
                                'session': serialize_escrow(session) if session else None}), 200
            session.revenue_id = rev.id
            result['revenue_id'] = rev.id
        # A 0% expert share is effectively a full refund to the student (no commission).
        if expert_gross == 0:
            session.status = 'refunded'
        else:
            session.status = 'released'
        session.released_at = datetime.datetime.utcnow()
        dispute.split_pct = split_pct
        result['expert_net'] = round(expert_gross - commission, 2)
        result['student_refund'] = round(amount - expert_gross, 2)
        result['commission'] = commission

    dispute.decision = decision
    dispute.stage = 'decision'
    dispute.resolved_at = datetime.datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'تم فصل النزاع', 'decision': decision, 'result': result,
                    'dispute': serialize_dispute(dispute), 'session': serialize_escrow(session)})

@app.route('/api/escrow/process-auto-releases', methods=['POST'])
@token_required
@roles_required('admin')
def escrow_process_auto_releases():
    """Lazy/manual trigger (no cron): release every session past its release_at that is
    still in held/confirm and has no open dispute."""
    now = datetime.datetime.utcnow()
    due = EscrowSession.query.filter(
        EscrowSession.status.in_(['held', 'confirm']),
        EscrowSession.release_at <= now,
    ).all()
    released = []
    for due_session in due:
        if _open_dispute_for(due_session.id):
            continue
        session = _lock_escrow_session(due_session.id)   # row lock (Postgres) on the commission path
        if session is None or session.status not in ('held', 'confirm'):
            continue
        _record_commission_revenue(session)
        session.status = 'released'
        session.released_at = now
        released.append(session.id)
    db.session.commit()
    return jsonify({'message': f'تم التحرير التلقائي لـ {len(released)} جلسة', 'released': released, 'count': len(released)})

@app.route('/api/escrow', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def escrow_list():
    status = (request.args.get('status') or '').strip()
    q = EscrowSession.query
    if status:
        q = q.filter(EscrowSession.status == status)
    items = q.order_by(EscrowSession.held_at.desc()).all()
    now = datetime.datetime.utcnow()
    return jsonify([serialize_escrow(e, now) for e in items])

@app.route('/api/disputes', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def disputes_list():
    items = Dispute.query.order_by(Dispute.opened_at.desc()).all()
    return jsonify([serialize_dispute(d) for d in items])

@app.route('/api/escrow/metrics', methods=['GET'])
@token_required
@roles_required('admin', 'employee')
def escrow_metrics():
    now = datetime.datetime.utcnow()
    all_sessions = EscrowSession.query.all()
    held = [e for e in all_sessions if e.status in ('held', 'confirm')]
    released = [e for e in all_sessions if e.status == 'released']
    refunded = [e for e in all_sessions if e.status == 'refunded']
    awaiting = [e for e in held if e.release_at and e.release_at <= now and not _open_dispute_for(e.id)]
    open_disputes = Dispute.query.filter(Dispute.decision.is_(None)).all()
    return jsonify({
        'held_count': len(held),
        'held_sum': round(sum(e.amount or 0 for e in held), 2),
        'awaiting_release_count': len(awaiting),
        'awaiting_release_sum': round(sum(e.amount or 0 for e in awaiting), 2),
        'released_count': len(released),
        'released_sum': round(sum(e.amount or 0 for e in released), 2),
        'released_commission_sum': round(sum(e.commission for e in released), 2),
        'refunded_count': len(refunded),
        'disputes_count': len(open_disputes),
        'disputes_frozen_sum': round(sum(d.amount_frozen or 0 for d in open_disputes), 2),
    })

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
    seed()  # admin/user init only — always safe
    reset_business_data()  # ENV-GATED full wipe (RESET_BUSINESS_DATA) — no-op when unset
    if (os.environ.get('SEED_DEMO_DATA') or '').strip().lower() == 'true':
        seed_demo()  # founder's sample financials — OFF by default in production
    else:
        logger.info("SEED_DEMO_DATA != 'true' — skipping demo data seed.")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
