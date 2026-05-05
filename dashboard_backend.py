"""
ElProfessor Management Dashboard - Backend API
Flask + SQLAlchemy + SQLite (upgradeable to MySQL/PostgreSQL)
"""
import os, json, datetime, hashlib, secrets, functools
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

# ============================================================
# CONFIG
# ============================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///elprofessor.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app, origins=os.environ.get('CORS_ORIGINS', '*').split(','))
db = SQLAlchemy(app)

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

def to_egp(usd, egp, rate=None):
    if rate is None:
        rate = get_rate()
    return (egp or 0) + (usd or 0) * rate

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
    
    total_revenue = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in revenues)
    total_expenses = sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses)
    net_profit = total_revenue - total_expenses
    
    opening_balance_s = Setting.query.get('opening_balance_egp')
    opening_balance = float(opening_balance_s.value) if opening_balance_s else 0
    current_balance = opening_balance + net_profit
    
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
            rev = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in c.revenues)
            cost = to_egp(c.cost_usd, c.cost_egp, rate)
            return rev - cost
        best = max(courses, key=course_profit)
        best_course = {'id': best.id, 'title': best.title, 'profit': course_profit(best)}
    
    # Monthly trend (last 12 months)
    now = datetime.date.today()
    monthly = []
    for i in range(11, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        month_revs = [r for r in revenues if r.date and r.date.year == y and r.date.month == m]
        month_exps = [e for e in expenses if e.date and e.date.year == y and e.date.month == m]
        monthly.append({
            'month': f'{y}-{m:02d}',
            'revenue': round(sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in month_revs)),
            'expenses': round(sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in month_exps)),
        })
    
    # Alerts
    alerts = []
    if net_profit < 0:
        alerts.append({'type': 'warning', 'message': f'صافي خسارة: {abs(net_profit):,.0f} ج.م'})
    if total_revenue == 0:
        alerts.append({'type': 'info', 'message': 'لم يتم تسجيل أي إيرادات بعد'})
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
            'total_expenses': round(total_expenses),
            'net_profit': round(net_profit),
            'opening_balance': round(opening_balance),
            'current_balance': round(current_balance),
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
        'alerts': alerts,
        'recent': recent,
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
    result = []
    for c in items:
        total_revenue = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in c.revenues)
        total_cost = to_egp(c.cost_usd, c.cost_egp, rate)
        profit = total_revenue - total_cost
        result.append({
            'id': c.id, 'title': c.title, 'category': c.category,
            'trainer_name': c.trainer_name, 'status': c.status,
            'price_egp': c.price_egp, 'price_usd': c.price_usd,
            'cost_egp': c.cost_egp, 'cost_usd': c.cost_usd,
            'students_count': c.students_count,
            'start_date': serialize_date(c.start_date), 'end_date': serialize_date(c.end_date),
            'total_revenue': round(total_revenue), 'total_cost': round(total_cost),
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
# AI ASSISTANT
# ============================================================

@app.route('/api/ai/snapshot', methods=['GET'])
@token_required
def ai_snapshot():
    """Generate a structured data snapshot for AI consumption"""
    rate = get_rate()
    revenues = Revenue.query.all()
    expenses = Expense.query.filter_by(is_business=True).all()
    campaigns = Campaign.query.all()
    courses = Course.query.all()
    
    total_rev = sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in revenues)
    total_exp = sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses)
    
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
            'top_clients': [{'name': n, 'total_egp': round(t)} for n, t in top_clients],
        },
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
        'exchange_rate': rate
    }
    return jsonify(snapshot)

@app.route('/api/ai/ask', methods=['POST'])
@token_required
def ai_ask():
    """Proxy to AI model - expects {question: string, context: object}"""
    d = request.json or {}
    question = d.get('question', '')
    
    # Log the request
    log = AILog(action='ask', prompt=question)
    db.session.add(log)
    db.session.commit()
    
    # Return the snapshot + question for frontend to call AI API directly
    # This avoids storing API keys on backend
    return jsonify({
        'question': question,
        'log_id': log.id,
        'message': 'Use /api/ai/snapshot data with your AI model to answer this question'
    })

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
    
    # By month
    monthly = {}
    for r in revenues:
        if r.date:
            key = f'{r.date.year}-{r.date.month:02d}'
            if key not in monthly:
                monthly[key] = {'revenue': 0, 'expenses': 0}
            monthly[key]['revenue'] += to_egp(r.amount_usd, r.amount_egp, rate)
    for e in expenses:
        if e.date:
            key = f'{e.date.year}-{e.date.month:02d}'
            if key not in monthly:
                monthly[key] = {'revenue': 0, 'expenses': 0}
            monthly[key]['expenses'] += to_egp(e.amount_usd, e.amount_egp, rate)
    
    monthly_list = [{'month': k, 'revenue': round(v['revenue']), 'expenses': round(v['expenses']), 'profit': round(v['revenue'] - v['expenses'])} for k, v in sorted(monthly.items())]
    
    # By category
    cat_totals = {}
    for e in expenses:
        c = e.category or 'other'
        cat_totals[c] = cat_totals.get(c, 0) + to_egp(e.amount_usd, e.amount_egp, rate)
    
    return jsonify({
        'monthly': monthly_list,
        'expense_categories': [{'category': k, 'total': round(v)} for k, v in sorted(cat_totals.items(), key=lambda x: -x[1])],
        'total_revenue': round(sum(to_egp(r.amount_usd, r.amount_egp, rate) for r in revenues)),
        'total_expenses': round(sum(to_egp(e.amount_usd, e.amount_egp, rate) for e in expenses)),
    })

# ============================================================
# SEED DATA
# ============================================================

def seed():
    """Seed initial data"""
    if User.query.count() > 0:
        return
    
    # Admin user
    admin = User(
        email='admin@elprofessor.com',
        password_hash=generate_password_hash('admin123'),
        name='عبدالرحمن',
        role='admin'
    )
    db.session.add(admin)
    
    # Settings
    settings = [
        Setting(key='exchange_rate', value='50'),
        Setting(key='opening_balance_egp', value='15000'),
        Setting(key='company_name', value='البروفيسور - ElProfessor'),
        Setting(key='currency', value='EGP'),
    ]
    for s in settings:
        db.session.add(s)
    
    # Sample revenues (confirmed from bank data)
    sample_revenues = [
        Revenue(date=datetime.date(2025, 4, 19), source='course', description='دفعة تدريب - Mohamed Khalily', amount_usd=500, client_name='Mohamed Khalily', payment_method='wise'),
        Revenue(date=datetime.date(2025, 5, 3), source='course', description='دفعة تدريب - Abdulrahman Alqahtani', amount_usd=249.41, client_name='Abdulrahman Alqahtani', payment_method='wise'),
        Revenue(date=datetime.date(2025, 5, 8), source='course', description='دفعة تدريب - Mohamed Khalily', amount_usd=515, client_name='Mohamed Khalily', payment_method='wise'),
        Revenue(date=datetime.date(2025, 9, 1), source='course', description='دفعة تدريب - Baseem Dweekat', amount_usd=1025, client_name='Baseem Dweekat', payment_method='wise'),
        Revenue(date=datetime.date(2025, 10, 30), source='consulting', description='استشارة - RATTEL LTD', amount_usd=286.89, client_name='RATTEL LTD', payment_method='wise'),
        Revenue(date=datetime.date(2025, 11, 26), source='course', description='دفعة تدريب - Baseem Dweekat', amount_usd=510, client_name='Baseem Dweekat', payment_method='wise'),
        Revenue(date=datetime.date(2026, 1, 15), source='course', description='دفعة تدريب - Omrei Abumadi', amount_usd=431, client_name='Omrei Abumadi', payment_method='wise'),
        Revenue(date=datetime.date(2026, 2, 10), source='course', description='دفعة تدريب - Mohamed Khalily', amount_usd=500, client_name='Mohamed Khalily', payment_method='wise'),
        Revenue(date=datetime.date(2026, 4, 19), source='course', description='دفعة تدريب - Mohamed Khalily', amount_usd=200, client_name='Mohamed Khalily', payment_method='wise'),
    ]
    for r in sample_revenues:
        db.session.add(r)
    
    # Sample expenses (confirmed business expenses)
    sample_expenses = [
        Expense(date=datetime.date(2025, 1, 1), category='tools', description='Claude Pro - يناير', amount_usd=20, paid_by='عبدالرحمن', is_business=True),
        Expense(date=datetime.date(2025, 1, 9), category='travel', description='تذكرة طيران Flydubai - سفر عمل', amount_usd=169.66, paid_by='عبدالرحمن', is_business=True, has_receipt=True),
        Expense(date=datetime.date(2025, 5, 1), category='tools', description='ChatGPT Subscription', amount_usd=22.80, paid_by='عبدالرحمن', is_business=True),
        Expense(date=datetime.date(2025, 6, 1), category='tools', description='ChatGPT Subscription', amount_usd=22.80, paid_by='عبدالرحمن', is_business=True),
        Expense(date=datetime.date(2025, 8, 22), category='tools', description='Canva Pro', amount_egp=276, paid_by='عبدالرحمن', is_business=True),
        Expense(date=datetime.date(2025, 9, 16), category='tools', description='ChatGPT Subscription', amount_usd=22.80, paid_by='عبدالرحمن', is_business=True),
        Expense(date=datetime.date(2025, 11, 6), category='hosting', description='Google Cloud', amount_usd=10, paid_by='عبدالرحمن', is_business=True),
        Expense(date=datetime.date(2026, 2, 28), category='tools', description='Claude.ai Subscription', amount_usd=20, paid_by='عبدالرحمن', is_business=True),
        Expense(date=datetime.date(2026, 4, 28), category='tools', description='Claude.ai Subscription', amount_usd=20, paid_by='عبدالرحمن', is_business=True),
    ]
    for e in sample_expenses:
        db.session.add(e)
    
    db.session.commit()
    print("✅ Database seeded successfully")

# ============================================================
# INIT
# ============================================================

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.0.0'})

with app.app_context():
    db.create_all()
    seed()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
