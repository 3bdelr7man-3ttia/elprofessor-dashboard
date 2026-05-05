# خطة بناء Dashboard داخلية - منصة البروفيسور (ElProfessor)
## تحليل شامل + خطة تنفيذ + Database Schema + AI Actions

**تاريخ التحليل:** مايو 2026
**المحلل:** AI System Architect
**المصادر:** ملف النظام الأصلي (ElProfessor-Internal-System.zip) + ملف البيانات الكاملة (ElProfessor_Complete.zip)

---

# 1. Executive Summary

منصة البروفيسور شركة ناشئة في مرحلة بداية الإيرادات، تعمل في التعليم القانوني والأدوات القانونية بالذكاء الاصطناعي. الشركة مبنية على نموذج "صفر موظفين" معتمدة بالكامل على AI والأتمتة.

**الوضع الحالي:**
- 4 مؤسسين (عبدالرحمن 70.8% - مصطفي 10.8% - سمير 5.5% - أبوضيف 6.1%)
- رأس مال مستثمر: 15,000 ج.م
- إيرادات فعلية من البنك: ~$4,920 دولار (~246,000 ج.م بسعر 50)
- مصروفات أعمال: ~$827 دولار + ~2,725 ج.م
- 59 مستخدم مسجل (من الموقع القديم WordPress)
- 5 عملاء دافعين فقط (Mohamed Khalily, baseem dweekat, Abdulrahman Alqahtani, omrei abumadi, elprofessor.net)
- أدوات: $50/شهر (Claude + ChatGPT + Copilot)
- أصول معدات: ~$7,242

**المشكلة الرئيسية:** البيانات موزعة بين JSON + Excel + كشوف بنكية مع تناقضات كبيرة، لا توجد Dashboard مركزية، والقرارات الإدارية تُتخذ بدون رؤية واضحة للأرقام.

**الحل المقترح:** بناء Dashboard داخلية واحدة تجمع كل البيانات المالية والتشغيلية مع AI Assistant مخصص لتحليل الأداء واتخاذ القرارات.

---

# 2. مراجعة النظام الحالي (Current System Review)

## 2.1 النظام الأصلي (Internal System)

النظام الأصلي مصمم كـ file-based system يعمل مع DeepSeek عبر OpenFlow:

| المجلد | الغرض | الحالة |
|--------|--------|--------|
| 01_prompts/ | 9 برومبتات لإدارة النظام | مكتملة التصميم |
| 02_company/ | بيانات الشركة + Cap Table + قرارات مجلس الإدارة | مملوءة |
| 03_finance/ | مصروفات + إيرادات + اشتراكات + ملخص مالي | فارغ القيم (template) |
| 04_trainers/ | سجل المدربين | فارغ |
| 05_courses/ | الدورات + التسجيلات | فارغ |
| 06_operations/ | استضافة + tech stack | جزئي |
| 07_legal/ | سجل العقود + نماذج | فارغ |

**تقييم:** النظام الأصلي تصميم جيد كـ schema ولكن لم يُملأ بأي بيانات حقيقية. كل الملفات المالية فارغة (أصفار).

## 2.2 البيانات الجديدة (Complete Archive)

الملف الثاني يحتوي على بيانات حقيقية مستخرجة من:
- كشوف حساب Wise (5 عملات: USD, GBP, EUR, EGP, AED)
- شيت إكسل يدوي للتحويلات والمصروفات
- قائمة عملاء مصدرة من WordPress القديم
- بيانات تسجيل دخول المستخدمين (WordPress export)
- سجل أصول كامل
- تقرير مالي كامل
- ملف ضريبي
- نموذج عقد

---

# 3. مشاكل جودة البيانات (Data Quality Issues)

## 3.1 🔴 مشاكل حرجة

### 3.1.1 تناقض كبير في الأرقام المالية
الملفات المختلفة تعطي أرقام متضاربة تماماً:

| المصدر | الإيرادات | المصروفات | صافي |
|--------|-----------|-----------|------|
| financial_summary.json | 500 ج.م | 20,005 ج.م | -19,505 ج.م |
| full_financial_report.xlsx | 247,538 ج.م | 32,970 ج.م | +214,567 ج.م |
| كشف بنك USD الفعلي | ~$4,793 واردات | ~$4,687 صادرات | +$106 |

**السبب:** financial_summary.json لم يُحدّث بالبيانات الفعلية، والتقرير الكامل يحتسب بسعر 50 ج.م/دولار لكن financial_summary لا يحتسب الدولار.

### 3.1.2 خلط المصروفات الشخصية بالتجارية
كشف حساب USD يحتوي على 591 عملية، منها:
- مصروفات أعمال: ~$827 (17.6%)
- مصروفات شخصية: ~$1,170 (25%) - طلبات (Talabat)، سوبرماركت (فتح الله)، شحن موبايل
- غير مصنّف: ~$2,689 (57.4%)

**المشكلة:** الحساب البنكي مشترك بين الشخصي والتجاري. لم يتم فصل المصروفات.

### 3.1.3 تواريخ خاطئة في ملفات "2025"
ملف 2025_revenues.json يحتوي على:
- إيرادات من 2024 (مثل REV-2025-002 بتاريخ 2024-05-13)
- إيرادات من 2026 (مثل REV-2025-012 بتاريخ 2026-01-15)
- نفس المشكلة في المصروفات (EXP-2025-002 بتاريخ 2026-04-30)

### 3.1.4 Monthly Totals لا تتطابق
في revenue JSON:
```
monthly_totals: { "2025-01": 0, "2025-04": 0, "2025-05": 500, ... }
```
لكن الإيرادات الفعلية في يناير 2025: $203 (basim ghazi)
وفي أبريل 2025: $500 (Mohamed Khalily)
**كل القيم الشهرية تقريباً خاطئة.**

## 3.2 🟡 مشاكل متوسطة

### 3.2.1 بيانات فارغة بالكامل
| الجدول | الحالة | التأثير |
|--------|--------|--------|
| trainers_registry | فارغ تماماً (array: []) | لا يوجد سجل مدربين |
| courses_registry | فارغ تماماً | لا يوجد سجل دورات |
| enrollments | فارغ تماماً | لا يوجد سجل تسجيلات |
| contracts_registry | فارغ تماماً | لا يوجد سجل عقود |
| trainers_data.xlsx | 3 صفوف فارغة (TR-001, TR-002, TR-003 بدون بيانات) | templates بدون بيانات |

### 3.2.2 لا ربط بين العملاء والإيرادات
- 59 مستخدم مسجل في clients_list.xlsx
- 5 عملاء دافعين في الإيرادات
- **لا يوجد ربط** بين القائمتين (العملاء الدافعين ليسوا بالضرورة في قائمة المسجلين)
- أسماء العملاء في الإيرادات بأشكال مختلفة (مثلاً: "basim ghazi" و "baseem dweekat" و "basim ghazi fawzi dwikat")

### 3.2.3 ملفات مكررة
- `_Bank Transfers, Revenues & Expenses Log_.xlsx` موجود في مكانين:
  - `03_finance/`
  - `03_finance/bank_statements/`
  - نفس المحتوى بالضبط

### 3.2.4 بيانات حساسة مكشوفة
- `user_login البروفيسور.xlsx` يحتوي على كلمات سر مشفرة (hashed passwords)
- لا يجب تخزين هذا الملف خارج نظام آمن

## 3.3 🟢 بيانات جيدة ومكتملة

| البيانات | الجودة | ملاحظات |
|----------|--------|---------|
| company_info.json | ✅ ممتازة | بيانات الشركة كاملة ودقيقة |
| cap_table.json | ✅ ممتازة | توزيع الحصص واضح ومفصل |
| tools_subscriptions.json | ✅ جيدة | 8 أدوات مسجلة بتفاصيل |
| assets_register.json | ✅ ممتازة | $3,386 أصول أساسية |
| assets_complete.json | ✅ ممتازة | $7,242 أصول كاملة مع تأجير 5% |
| كشوف البنك (5 عملات) | ✅ ممتازة | بيانات خام من Wise كاملة |
| tax_plan.md | ✅ جيدة | خطة ضريبية واضحة |
| contract_template.md | ✅ جيدة | نموذج عقد جاهز |

---

# 4. العملاء الدافعين - تحليل فعلي من البنك

| العميل | عدد التحويلات | إجمالي USD | أول دفعة | آخر دفعة |
|--------|--------------|------------|----------|----------|
| Mohamed Khalily | 4 | $1,715 | 2025-04-19 | 2026-04-19 |
| baseem dweekat / basim ghazi | 4 | $1,953.88 | 2024-12-27 | 2025-11-26 |
| Abdulrahman Alqahtani | 1 | $249.41 | 2025-05-03 | 2025-05-03 |
| omrei abumadi | 1 | $431 | 2026-01-15 | 2026-01-15 |
| elprofessor.net | 1 | $284 | 2024-05-13 | 2024-05-13 |
| RATTEL LTD | 1 | $286.89 | 2025-10-30 | 2025-10-30 |
| **الإجمالي** | **12** | **$4,920.18** | | |

**ملاحظة مهمة:** baseem dweekat و basim ghazi fawzi dwikat على الأرجح نفس الشخص (بأشكال اسم مختلفة).

---

# 5. Dashboard المقترحة - التصميم

## 5.1 الموديولات (Modules)

### Module 1: Financial Dashboard 💰
- ملخص مالي حي (إيرادات، مصروفات، صافي)
- تصنيف المصروفات (أعمال vs شخصي)
- Cash flow شهري
- Burn rate وrunway
- أرصدة البنك بكل العملات
- مقارنة شهر بشهر
- تنبيهات المصروفات غير المعتادة

### Module 2: Clients Dashboard 👥
- قائمة العملاء الكاملة (59 + أي جديد)
- تصنيف: lead / registered / paying / churned
- ربط العميل بالدفعات والدورات
- تاريخ التفاعل مع كل عميل
- Customer Lifetime Value
- العملاء غير المدفوعين
- Pipeline جديد

### Module 3: Courses Dashboard 📚
- قائمة الدورات (مخططة / جارية / منتهية)
- عدد المسجلين لكل دورة
- إيرادات كل دورة
- ربط بـ LMS (Chamilo)
- تقييمات ونتائج

### Module 4: Trainers Dashboard 🎓
- سجل المدربين
- حالة العقود
- المستحقات المالية
- تقييم الأداء
- الدورات المسندة

### Module 5: Partners Dashboard 🤝
- Cap Table تفاعلي
- استثمارات كل شريك
- مسؤوليات كل شريك
- قرارات مجلس الإدارة
- تاريخ التحديثات

### Module 6: Legal Documents Dashboard 📄
- سجل العقود
- نماذج العقود
- الملف الضريبي
- تواريخ التجديد والانتهاء
- تنبيهات قانونية

### Module 7: Ads & Marketing Dashboard 📊
- حملات إعلانية (Google Ads, Facebook, Instagram)
- تكلفة الاستحواذ لكل عميل (CAC)
- ROI لكل حملة
- أداء المحتوى
- مصادر التسجيل

### Module 8: Reports Dashboard 📈
- تقرير شهري تلقائي
- تقرير ربع سنوي
- مقارنة فترات
- تصدير PDF/Excel
- KPIs ومؤشرات الأداء

### Module 9: AI Assistant 🤖
- تحليل فوري للأرقام
- اقتراحات قرارات
- كشف الأخطاء
- توليد تقارير
- أسئلة وأجوبة عن حالة الشركة

---

# 6. AI Actions المخصصة

## 6.1 تحليل مالي
```
Action: analyze_financials
Input: period (month/quarter/year)
Output: إيرادات، مصروفات، صافي، مقارنة بالفترة السابقة
مثال: "حلل الأداء المالي لشهر أبريل 2026"
```

## 6.2 حساب صافي الربح
```
Action: calculate_net_profit
Input: date_from, date_to, exchange_rate
Output: إيرادات EGP + USD (محوّلة)، مصروفات، صافي
يحل مشكلة: التناقض الحالي بين الملفات
```

## 6.3 تحليل الحملات الإعلانية
```
Action: analyze_campaign
Input: campaign_id or period
Output: تكلفة، عملاء جدد، CAC، ROI
ملاحظة: يحتاج بيانات حملات (غير موجودة حالياً)
```

## 6.4 استخراج العملاء غير المدفوعين
```
Action: find_unpaid_clients
Input: none
Output: قائمة بالمسجلين الذين لم يدفعوا أي شيء
حالياً: 54 من 59 مسجل لم يدفعوا
```

## 6.5 مستحقات المدربين
```
Action: trainer_dues
Input: trainer_id or all
Output: المبالغ المستحقة لكل مدرب
ملاحظة: يحتاج بيانات مدربين (فارغة حالياً)
```

## 6.6 توليد تقارير
```
Action: generate_report
Input: type (monthly/quarterly/annual), format (pdf/xlsx)
Output: تقرير مفصل جاهز للتحميل
```

## 6.7 اقتراح قرارات إدارية
```
Action: suggest_decisions
Input: context (financial/operational/growth)
Output: 3-5 قرارات مقترحة مع مبررات بالأرقام
مثال: "الإيرادات تتركز في عميلين فقط - اقتراح: تنويع مصادر الإيرادات"
```

## 6.8 كشف الأخطاء والتكرارات
```
Action: data_audit
Input: table (all/revenues/expenses/clients)
Output: تكرارات، تناقضات، بيانات ناقصة
مثال حالي: "basim ghazi" و"baseem dweekat" = نفس العميل
```

## 6.9 تلخيص حالة الشركة
```
Action: company_snapshot
Input: none
Output: ملخص تنفيذي بصفحة واحدة (رقم واحد لكل مؤشر)
```

## 6.10 فصل المصروفات الشخصية عن التجارية
```
Action: classify_expenses
Input: bank_statement
Output: تصنيف كل عملية (business/personal/unknown) + قواعد التصنيف
```

---

# 7. Database Schema

```sql
-- ========================
-- CORE TABLES
-- ========================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name_ar VARCHAR(255),
    name_en VARCHAR(255),
    phone VARCHAR(50),
    role VARCHAR(50) DEFAULT 'admin', -- admin, viewer, accountant
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ========================
-- COMPANY & PARTNERS
-- ========================

CREATE TABLE partners (
    id VARCHAR(10) PRIMARY KEY, -- F001, F002...
    name_ar VARCHAR(255) NOT NULL,
    name_en VARCHAR(255),
    role VARCHAR(255),
    equity_pct DECIMAL(5,2) NOT NULL,
    cash_invested_egp DECIMAL(12,2) DEFAULT 0,
    responsibilities TEXT[], -- PostgreSQL array
    status VARCHAR(20) DEFAULT 'active', -- active, inactive, exited
    vesting_info TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE board_decisions (
    id VARCHAR(20) PRIMARY KEY, -- BD-001
    decision_date DATE NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    decided_by TEXT[],
    status VARCHAR(20) DEFAULT 'approved', -- draft, approved, rejected, superseded
    related_files TEXT[],
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ========================
-- CLIENTS & LEADS
-- ========================

CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    client_type VARCHAR(20) DEFAULT 'lead', -- lead, registered, paying, churned
    source VARCHAR(50), -- website, referral, ad_campaign, manual
    source_detail VARCHAR(255), -- campaign name, referrer name, etc.
    registration_date DATE,
    first_payment_date DATE,
    total_paid_usd DECIMAL(12,2) DEFAULT 0,
    total_paid_egp DECIMAL(12,2) DEFAULT 0,
    notes TEXT,
    wp_user_id INTEGER, -- legacy WordPress user ID
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    interest VARCHAR(255), -- course name, service type
    source VARCHAR(50),
    status VARCHAR(20) DEFAULT 'new', -- new, contacted, qualified, converted, lost
    assigned_to VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ========================
-- TRAINERS
-- ========================

CREATE TABLE trainers (
    id VARCHAR(10) PRIMARY KEY, -- TR-001
    name_ar VARCHAR(255) NOT NULL,
    name_en VARCHAR(255),
    specialization VARCHAR(255),
    phone VARCHAR(50),
    email VARCHAR(255),
    contract_status VARCHAR(20) DEFAULT 'none', -- none, pending, active, expired
    payment_terms VARCHAR(20), -- per_session, monthly, per_course
    rate_egp DECIMAL(10,2),
    rate_usd DECIMAL(10,2),
    rating DECIMAL(3,2),
    joined_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ========================
-- COURSES & ENROLLMENTS
-- ========================

CREATE TABLE courses (
    id VARCHAR(10) PRIMARY KEY, -- CRS-001
    title_ar VARCHAR(500) NOT NULL,
    title_en VARCHAR(500),
    category VARCHAR(100), -- قانون مدني، جنائي، تجاري، عام
    trainer_id VARCHAR(10) REFERENCES trainers(id),
    status VARCHAR(20) DEFAULT 'draft', -- draft, scheduled, active, completed, archived
    lms_platform VARCHAR(20) DEFAULT 'chamilo', -- chamilo, wordpress
    lms_course_id VARCHAR(50),
    price_egp DECIMAL(10,2),
    price_usd DECIMAL(10,2),
    sessions_count INTEGER DEFAULT 0,
    start_date DATE,
    end_date DATE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE enrollments (
    id VARCHAR(10) PRIMARY KEY, -- ENR-001
    client_id UUID REFERENCES clients(id),
    course_id VARCHAR(10) REFERENCES courses(id),
    enrollment_date DATE NOT NULL,
    payment_status VARCHAR(20) DEFAULT 'pending', -- free, paid, pending, refunded
    amount_paid_egp DECIMAL(10,2),
    amount_paid_usd DECIMAL(10,2),
    lms_enrolled BOOLEAN DEFAULT false,
    completion_status VARCHAR(20) DEFAULT 'enrolled', -- enrolled, in_progress, completed, dropped
    certificate_issued BOOLEAN DEFAULT false,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ========================
-- FINANCE
-- ========================

CREATE TABLE payments (
    id VARCHAR(20) PRIMARY KEY, -- REV-2025-001
    payment_date DATE NOT NULL,
    source VARCHAR(50) NOT NULL, -- client_payment, commission, subscription, course, consulting, other
    description TEXT,
    amount_egp DECIMAL(12,2) DEFAULT 0,
    amount_usd DECIMAL(12,2) DEFAULT 0,
    exchange_rate DECIMAL(8,2), -- EGP per USD at time of payment
    payment_method VARCHAR(30), -- stripe, bank_transfer, cash, wise, other
    client_id UUID REFERENCES clients(id),
    course_id VARCHAR(10) REFERENCES courses(id),
    bank_reference VARCHAR(100), -- Wise transaction ID
    notes TEXT,
    recorded_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE expenses (
    id VARCHAR(20) PRIMARY KEY, -- EXP-2025-001
    expense_date DATE NOT NULL,
    category VARCHAR(50) NOT NULL, -- tools_subscriptions, hosting, marketing, legal, office, travel, bank_fees, other
    description TEXT,
    amount_egp DECIMAL(12,2) DEFAULT 0,
    amount_usd DECIMAL(12,2) DEFAULT 0,
    exchange_rate DECIMAL(8,2),
    is_business BOOLEAN DEFAULT true, -- false = personal (flagged for separation)
    paid_by VARCHAR(100),
    has_receipt BOOLEAN DEFAULT false,
    receipt_path TEXT,
    bank_reference VARCHAR(100),
    notes TEXT,
    recorded_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE bank_transactions (
    id VARCHAR(100) PRIMARY KEY, -- Wise transaction ID
    transaction_date TIMESTAMPTZ NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(5) NOT NULL, -- USD, EGP, GBP, EUR, AED
    description TEXT,
    payment_reference VARCHAR(100),
    running_balance DECIMAL(12,2),
    exchange_from VARCHAR(5),
    exchange_to VARCHAR(5),
    classification VARCHAR(20), -- business, personal, unknown
    linked_payment_id VARCHAR(20) REFERENCES payments(id),
    linked_expense_id VARCHAR(20) REFERENCES expenses(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tool_subscriptions (
    id VARCHAR(10) PRIMARY KEY, -- T001
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50), -- AI, Development, Infrastructure, LMS, Payments, Automation
    plan VARCHAR(50),
    monthly_cost_usd DECIMAL(8,2) DEFAULT 0,
    monthly_cost_egp DECIMAL(8,2) DEFAULT 0,
    billing_cycle VARCHAR(20), -- monthly, annual, per_transaction, none
    usage_description TEXT,
    status VARCHAR(20) DEFAULT 'active', -- active, paused, cancelled
    start_date DATE,
    renewal_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ========================
-- MARKETING & ADS
-- ========================

CREATE TABLE ad_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_name VARCHAR(255) NOT NULL,
    platform VARCHAR(50), -- google_ads, facebook, instagram, linkedin, twitter, tiktok
    campaign_type VARCHAR(50), -- awareness, traffic, conversion, retargeting
    start_date DATE,
    end_date DATE,
    budget_usd DECIMAL(10,2),
    spent_usd DECIMAL(10,2) DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    leads_generated INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    revenue_attributed_usd DECIMAL(10,2) DEFAULT 0,
    target_audience TEXT,
    ad_copy TEXT,
    landing_page_url TEXT,
    status VARCHAR(20) DEFAULT 'draft', -- draft, active, paused, completed
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ========================
-- LEGAL DOCUMENTS
-- ========================

CREATE TABLE legal_documents (
    id VARCHAR(20) PRIMARY KEY, -- CON-2025-001
    doc_type VARCHAR(50) NOT NULL, -- trainer, partnership, service, consulting, employment, nda
    title VARCHAR(500),
    party_name VARCHAR(255), -- الطرف الثاني
    start_date DATE,
    end_date DATE,
    value_egp DECIMAL(12,2),
    value_usd DECIMAL(12,2),
    payment_terms VARCHAR(50),
    status VARCHAR(20) DEFAULT 'draft', -- draft, active, expired, terminated
    file_path TEXT,
    related_trainer_id VARCHAR(10) REFERENCES trainers(id),
    related_partner_id VARCHAR(10) REFERENCES partners(id),
    alert_before_days INTEGER DEFAULT 30, -- تنبيه قبل الانتهاء
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE company_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_type VARCHAR(50), -- registration, tax, license, policy, template
    title VARCHAR(500) NOT NULL,
    description TEXT,
    file_path TEXT,
    expiry_date DATE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ========================
-- ASSETS
-- ========================

CREATE TABLE assets (
    id VARCHAR(10) PRIMARY KEY, -- AST-001
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50), -- laptop, camera, microphone, lighting, tripod, software, other
    value_usd DECIMAL(10,2),
    quantity INTEGER DEFAULT 1,
    owner VARCHAR(100),
    location VARCHAR(100),
    purchase_date DATE,
    notes TEXT,
    status VARCHAR(20) DEFAULT 'active', -- active, broken, sold, lost
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ========================
-- REPORTS & AI
-- ========================

CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type VARCHAR(50) NOT NULL, -- monthly, quarterly, annual, custom, ai_generated
    title VARCHAR(500),
    period_start DATE,
    period_end DATE,
    content JSONB, -- structured report data
    file_path TEXT, -- generated PDF/Excel path
    generated_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE ai_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type VARCHAR(50) NOT NULL, -- analyze_financials, data_audit, suggest_decisions, etc.
    input_params JSONB,
    output_result JSONB,
    prompt_used TEXT,
    model_used VARCHAR(50),
    user_id UUID REFERENCES users(id),
    execution_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(50) NOT NULL, -- create, update, delete, login, export
    table_name VARCHAR(50),
    record_id VARCHAR(255),
    old_value JSONB,
    new_value JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    related_table VARCHAR(50) NOT NULL,
    related_id VARCHAR(255) NOT NULL,
    file_name VARCHAR(255),
    file_path TEXT NOT NULL,
    file_type VARCHAR(50),
    file_size_bytes INTEGER,
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ========================
-- INDEXES
-- ========================

CREATE INDEX idx_payments_date ON payments(payment_date);
CREATE INDEX idx_payments_client ON payments(client_id);
CREATE INDEX idx_expenses_date ON expenses(expense_date);
CREATE INDEX idx_expenses_category ON expenses(category);
CREATE INDEX idx_bank_transactions_date ON bank_transactions(transaction_date);
CREATE INDEX idx_bank_transactions_currency ON bank_transactions(currency);
CREATE INDEX idx_clients_type ON clients(client_type);
CREATE INDEX idx_enrollments_course ON enrollments(course_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);

-- ========================
-- INITIAL SETTINGS
-- ========================

INSERT INTO settings (key, value, description) VALUES
('exchange_rate_usd_egp', '50', 'سعر صرف الدولار مقابل الجنيه'),
('company_name', '"البروفيسور - ElProfessor"', 'اسم الشركة'),
('currency_primary', '"EGP"', 'العملة الأساسية'),
('fiscal_year_start', '"01-01"', 'بداية السنة المالية'),
('monthly_report_day', '1', 'يوم إعداد التقرير الشهري'),
('lease_rate_pct', '0.05', 'نسبة تأجير الأصول الشهرية');
```

---

# 8. Tech Stack المقترح

## الخيار الموصى به: Supabase + Next.js

| الطبقة | التقنية | السبب |
|--------|---------|-------|
| Database | Supabase (PostgreSQL) | مجاني حتى 500MB، API تلقائي، Auth مدمج، Row Level Security |
| Backend API | Supabase Edge Functions | بدون سيرفر منفصل، TypeScript |
| Frontend | Next.js 14+ (App Router) | SSR، RTL جاهز، Tailwind CSS |
| UI Components | shadcn/ui + Recharts | مكونات جاهزة، Charts سهلة |
| AI | Anthropic Claude API | متكامل مع الـ system الحالي |
| Auth | Supabase Auth | بدون إعداد إضافي |
| Hosting | Vercel (Frontend) + Supabase (Backend) | مجاني للمشاريع الصغيرة |
| File Storage | Supabase Storage | للإيصالات والعقود |

**التكلفة المتوقعة:** $0/شهر (Free tier) حتى تكبر البيانات

**بديل أبسط:** إذا أردت شيء أسرع بكثير، يمكن بناء MVP كـ React artifact (مثل هذا المشروع) مع Supabase backend فقط.

---

# 9. Implementation Roadmap

---

## Phase 0: Data Audit & Cleanup (أسبوع 1)

**الهدف:** تنظيف البيانات وتوحيدها قبل البناء

**المهام:**
1. فصل المصروفات الشخصية عن التجارية في كشف USD
2. توحيد أسماء العملاء (basim ghazi = baseem dweekat)
3. تصحيح التواريخ (فصل 2024 و 2025 و 2026)
4. إعادة حساب monthly_totals
5. حذف الملفات المكررة
6. إنشاء ملف clients_master موحد (ربط WordPress users + revenue payers)
7. إنشاء ملف financial_reconciled (أرقام نهائية متفق عليها)
8. تصنيف كل عملية بنكية
9. حذف ملف كلمات السر من النظام

**الجداول المتأثرة:** payments, expenses, bank_transactions, clients

**الشاشات:** لا يوجد (عمل داخلي)

**AI Features:** 
- classify_expenses: تصنيف تلقائي للعمليات البنكية
- deduplicate_clients: اكتشاف العملاء المكررين

**الملفات المطلوبة:**
- كشوف البنك الخمسة (xlsx)
- clients_list.xlsx
- 2025_revenues.json
- 2025_expenses.json

**الاختبارات:**
- التحقق من أن مجموع الإيرادات المنظفة = مجموع واردات البنك
- التحقق من عدم وجود تكرار في العملاء
- التحقق من أن كل عملية بنكية مصنفة

**Prompt تنفيذي:**
```
أنت مهندس بيانات. لديك الملفات التالية:
1. كشوف بنك Wise لـ 5 عملات (USD 592 عملية, GBP 81, EUR 10, EGP 44, AED 27)
2. قائمة عملاء (59 عميل)
3. إيرادات JSON (14 إدخال)
4. مصروفات JSON (38 إدخال)

المطلوب:
1. أنشئ ملف cleaned_revenues.json يحتوي فقط على الإيرادات الحقيقية مع تصحيح التواريخ والأسماء
2. أنشئ ملف cleaned_expenses.json مع فصل المصروفات الشخصية (طلبات، سوبرماركت، شحن موبايل) عن التجارية
3. أنشئ ملف clients_master.json يجمع بين WordPress users والعملاء الدافعين
4. أنشئ ملف reconciliation.json يحتوي على الأرقام النهائية الصحيحة

القواعد:
- basim ghazi fawzi dwikat = baseem dweekat = نفس الشخص
- أي عملية من Talabat, Fathallah, Dokkan Faroj, coffee shop = شخصي
- أي عملية من OpenAI, Anthropic, Canva, Google Cloud, Elevenlabs = أعمال
- Flydubai, Al Emad Car Rental = سفر عمل
- العملة الأساسية EGP بسعر 50 للدولار
```

---

## Phase 1: MVP Dashboard (أسبوع 2-3)

**الهدف:** Dashboard أساسية تعمل مع البيانات المنظفة

**المهام:**
1. إعداد Supabase project + تنفيذ الـ schema
2. استيراد البيانات المنظفة من Phase 0
3. بناء صفحة Login
4. بناء الصفحة الرئيسية (Overview)
5. بناء Financial Module (إيرادات + مصروفات + ملخص)
6. بناء Clients Module (قائمة + تفاصيل)
7. إضافة / تعديل / حذف للسجلات
8. RTL وعربي بالكامل

**الجداول:** users, partners, payments, expenses, clients, settings

**الشاشات:**
1. `/login` - تسجيل دخول
2. `/dashboard` - نظرة عامة (4 بطاقات: إيرادات، مصروفات، صافي، عملاء)
3. `/finance` - جدول الإيرادات + جدول المصروفات + chart شهري
4. `/finance/add` - إضافة إيراد أو مصروف
5. `/clients` - قائمة العملاء مع فلتر وبحث
6. `/clients/:id` - تفاصيل عميل

**AI Features:** لا يوجد في MVP

**الملفات المطلوبة:**
- schema.sql (من القسم 7)
- seed_data.sql (من البيانات المنظفة)
- Next.js project structure

**الاختبارات:**
- تسجيل دخول يعمل
- عرض الأرقام المالية صحيح
- إضافة إيراد جديد يحدث الملخص
- البحث في العملاء يعمل

**Prompt تنفيذي:**
```
أنت مطور Full Stack. ابنِ MVP Dashboard لشركة البروفيسور بالمواصفات التالية:

Tech Stack: Next.js 14 (App Router) + Supabase + Tailwind CSS + shadcn/ui
اللغة: عربي - RTL بالكامل
التصميم: نظيف، احترافي، ألوان أساسية (#1a365d أزرق داكن + #e2e8f0 رمادي فاتح)

الصفحات المطلوبة:
1. Login page (email + password)
2. Dashboard Overview:
   - 4 بطاقات (إجمالي إيرادات, إجمالي مصروفات, صافي, عدد العملاء)
   - Chart شهري (line chart لآخر 12 شهر)
   - آخر 5 عمليات
3. Financial page:
   - Tabs: إيرادات | مصروفات
   - جدول مع فلتر بالتاريخ والفئة
   - زر إضافة جديد
   - إجمالي في الأسفل
4. Clients page:
   - جدول عملاء مع بحث
   - فلتر: كل العملاء | دافعين | مسجلين فقط
   - عند الضغط على عميل: صفحة تفاصيل مع تاريخ الدفعات

Database: استخدم الـ schema المرفق
البيانات الأولية: استورد من ملفات الـ seed المرفقة

ملاحظات:
- Supabase URL و Anon Key يؤخذان من environment variables
- استخدم Supabase Auth لتسجيل الدخول
- كل الأرقام تظهر بالجنيه المصري (مع تحويل الدولار بسعر 50)
- الـ layout يكون responsive
- لا تستخدم Server Components للجداول (client-side filtering)
```

---

## Phase 2: Operations Dashboard (أسبوع 4)

**الهدف:** إضافة الدورات والمدربين والأصول

**المهام:**
1. Courses CRUD
2. Trainers CRUD
3. Enrollments (ربط عميل بدورة)
4. Assets register
5. Tool subscriptions management
6. Partners / Cap Table view

**الجداول:** courses, trainers, enrollments, assets, tool_subscriptions, partners

**الشاشات:**
1. `/courses` - قائمة الدورات
2. `/courses/:id` - تفاصيل دورة مع المسجلين
3. `/trainers` - قائمة المدربين
4. `/trainers/:id` - تفاصيل مدرب مع دوراته ومستحقاته
5. `/assets` - سجل الأصول
6. `/partners` - Cap Table تفاعلي (pie chart + جدول)
7. `/subscriptions` - إدارة اشتراكات الأدوات

**AI Features:** لا يوجد بعد

**الاختبارات:**
- تسجيل عميل في دورة يحدث enrollment
- عند إضافة مدرب، العقد يظهر في Legal
- إجمالي الأصول يحسب صحيح

**Prompt تنفيذي:**
```
أكمل الـ Dashboard بإضافة الصفحات التالية:

1. صفحة الدورات (/courses):
   - جدول بكل الدورات (العنوان، المدرب، الحالة، السعر، المسجلين)
   - فلتر بالحالة: مخطط | جاري | منتهي
   - زر إضافة دورة جديدة (form: عنوان، فئة، مدرب، سعر، تاريخ)
   - عند الضغط على دورة: تفاصيل + قائمة المسجلين + إيراد الدورة

2. صفحة المدربين (/trainers):
   - جدول (الاسم، التخصص، حالة العقد، عدد الدورات، المستحقات)
   - form إضافة مدرب (الاسم بالعربي والإنجليزي، التخصص، الموبايل، الإيميل، شروط الدفع)

3. سجل الأصول (/assets):
   - جدول بكل الأصول مع القيمة
   - إجمالي القيمة في الأعلى
   - تصنيف: أجهزة | كاميرات | ميكروفونات | إضاءة | برمجيات

4. الشركاء (/partners):
   - Pie Chart للحصص (Recharts)
   - جدول الشركاء مع نسبة كل واحد واستثماره
   - 6.8% غير موزعة تظهر في الـ chart

5. الاشتراكات (/subscriptions):
   - قائمة الأدوات مع التكلفة الشهرية
   - إجمالي $50/شهر
   - تنبيه عند قرب التجديد

استخدم نفس التصميم والألوان من Phase 1.
```

---

## Phase 3: Marketing & Ads Dashboard (أسبوع 5)

**الهدف:** تتبع الحملات الإعلانية ومصادر العملاء

**المهام:**
1. Ad campaigns CRUD
2. Campaign metrics tracking
3. Source attribution (من أين جاء العميل)
4. CAC و ROI حساب تلقائي
5. ربط حملة بعملاء

**الجداول:** ad_campaigns, clients (source field)

**الشاشات:**
1. `/marketing` - ملخص الحملات
2. `/marketing/campaigns` - كل الحملات مع الأداء
3. `/marketing/campaigns/new` - إنشاء حملة جديدة
4. `/marketing/sources` - تحليل مصادر العملاء (pie chart)

**AI Features:**
- تحليل ROI لكل حملة
- اقتراح ميزانية مثلى

**Prompt تنفيذي:**
```
أضف Marketing Dashboard:

1. صفحة ملخص التسويق (/marketing):
   - بطاقات: إجمالي الإنفاق الإعلاني | عملاء جدد | CAC | أفضل حملة
   - Chart: عملاء جدد شهرياً مع المصدر (bar chart stacked)

2. صفحة الحملات (/marketing/campaigns):
   - جدول الحملات (الاسم، المنصة، الميزانية، المنفق، النقرات، العملاء، ROI)
   - فلتر: كل المنصات | Google | Facebook | Instagram
   - زر إنشاء حملة جديدة

3. تحليل المصادر (/marketing/sources):
   - Pie chart لمصادر العملاء
   - جدول تفصيلي

4. في صفحة كل عميل أضف حقل "مصدر العميل" قابل للتعديل
```

---

## Phase 4: AI Assistant & Reports (أسبوع 6-7)

**الهدف:** مساعد AI مخصص + تقارير تلقائية

**المهام:**
1. Chat interface مع Claude API
2. Predefined AI actions (10 actions)
3. Monthly report generator
4. Quarterly review generator
5. PDF/Excel export
6. Data audit tool

**الجداول:** reports, ai_actions, audit_logs

**الشاشات:**
1. `/ai` - واجهة المحادثة مع AI
2. `/ai/actions` - الأوامر المحددة مسبقاً (10 أزرار)
3. `/reports` - قائمة التقارير المولدة
4. `/reports/monthly` - تقرير شهري تلقائي
5. `/reports/quarterly` - مراجعة ربع سنوية

**AI Features:**
- كل الـ 10 AI Actions المذكورة في القسم 6
- System prompt مخصص للشركة
- الـ AI يقرأ من الـ database مباشرة عبر Supabase

**Prompt تنفيذي:**
```
أضف AI Assistant:

1. صفحة الـ AI (/ai):
   - واجهة chat عربية (مثل ChatGPT لكن مبسطة)
   - في الأعلى: 5 أزرار سريعة (تلخيص حالة الشركة | تحليل مالي | كشف أخطاء | اقتراح قرارات | تقرير شهري)
   - عند الضغط على زر، يبعث prompt جاهز لـ Claude API
   - الـ response يظهر كـ markdown مع جداول

2. System Prompt للـ AI:
   "أنت مساعد إداري ومالي لشركة البروفيسور (ElProfessor)، منصة تعليم قانوني مصرية.
   الشركة في مرحلة بداية الإيرادات.
   4 مؤسسين. 0 موظفين. معتمدين على AI.
   إيرادات فعلية ~$4,920 USD. مصروفات أعمال ~$827 USD.
   59 مستخدم مسجل. 5 عملاء دافعين.
   أجب بالعربية. كن مختصراً ودقيقاً. استخدم الأرقام الفعلية."

3. التقارير (/reports):
   - قائمة التقارير السابقة
   - زر "تقرير شهري جديد" → يولّد التقرير من الـ database
   - زر تحميل PDF / Excel

4. استخدم Claude API عبر:
   fetch('https://api.anthropic.com/v1/messages', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       model: 'claude-sonnet-4-20250514',
       max_tokens: 1000,
       system: SYSTEM_PROMPT,
       messages: [{ role: 'user', content: userQuery + '\n\nالبيانات:\n' + JSON.stringify(dashboardData) }]
     })
   })
```

---

## Phase 5: Website/API Integration (أسبوع 8)

**الهدف:** ربط Dashboard بالموقع الرئيسي والـ LMS

**المهام:**
1. API endpoint لاستقبال تسجيلات جديدة من الموقع
2. Webhook لاستقبال دفعات Stripe
3. ربط بـ Chamilo LMS (تسجيل طالب تلقائي)
4. Sync clients بين الموقع والـ Dashboard
5. API لعرض الدورات على الموقع

**الجداول:** كل الجداول (تحديث)

**الشاشات:** لا شاشات جديدة (backend فقط)

**الاختبارات:**
- عميل يسجل من الموقع → يظهر في Dashboard
- عميل يدفع عبر Stripe → الدفعة تتسجل تلقائي
- عميل يُقبل للدورة → يتسجل في Chamilo تلقائي

---

## Phase 6: Deployment & Security (أسبوع 9)

**الهدف:** نشر آمن وجاهز للاستخدام اليومي

**المهام:**
1. إعداد environment variables
2. تفعيل Row Level Security في Supabase
3. إضافة audit logging لكل العمليات
4. Backup تلقائي (Supabase يوفر)
5. Custom domain (dashboard.elprofessor.com)
6. SSL certificate
7. Rate limiting على API
8. اختبار أمان شامل

**الاختبارات:**
- محاولة وصول بدون تسجيل دخول = ممنوع
- كل تعديل يظهر في audit log
- Backup يشتغل يومياً

---

# 10. MVP Scope - ما يُبنى أولاً

**الحد الأدنى القابل للاستخدام (Phase 0 + Phase 1):**

✅ يُبنى:
- تنظيف البيانات المالية
- صفحة Login
- Dashboard overview (4 بطاقات + chart)
- جدول إيرادات مع إضافة
- جدول مصروفات مع إضافة
- جدول عملاء مع بحث
- تفاصيل عميل مع دفعاته

❌ لا يُبنى في MVP:
- AI Assistant (يأتي في Phase 4)
- حملات إعلانية (Phase 3)
- تكامل مع الموقع (Phase 5)
- تقارير PDF/Excel (Phase 4)
- Courses & Trainers CRUD (Phase 2)

**الوقت المقدر للـ MVP:** 2-3 أسابيع

---

# 11. What to Avoid - ما يجب تجنبه

1. **لا تبنِ CRM كامل** - الشركة فيها 5 عملاء دافعين فقط. لا تحتاج Salesforce-level complexity.
2. **لا تبنِ accounting system** - استخدم Dashboard بسيط. المحاسبة الحقيقية تُعمل بـ Excel أو محاسب.
3. **لا تربط بالبنك مباشرة** - استيراد كشوف يدوياً أكفأ وأأمن في هذه المرحلة.
4. **لا تبنِ LMS خاص** - Chamilo موجود ويعمل. Dashboard للإدارة فقط.
5. **لا تعقّد الصلاحيات** - مؤسس واحد يستخدم النظام. admin فقط يكفي حالياً.
6. **لا تبنِ mobile app** - Dashboard ويب responsive يكفي.
7. **لا تستخدم microservices** - monolith (Next.js + Supabase) أبسط وأسرع.
8. **لا تبنِ multi-tenancy** - شركة واحدة فقط.

---

# 12. Questions / بيانات مطلوبة

قبل البدء، نحتاج إجابات على:

1. **هل basim ghazi fawzi dwikat = baseem dweekat?** (نظن نعم لكن نحتاج تأكيد)
2. **ما الخدمة المقدمة لكل عميل دافع؟** (Mohamed Khalily دفع $1,715 - مقابل ماذا؟)
3. **هل RATTEL LTD عميل استشارات أم شريك؟**
4. **ما تكلفة الاستضافة الفعلية؟** (hosting.json يقول $0 وهذا غير منطقي)
5. **هل يوجد حملات إعلانية سابقة؟** (لا يوجد أي بيانات تسويق)
6. **هل يوجد مدربين متعاقد معهم فعلاً؟** (الملفات فارغة)
7. **أين subdomain الـ Dashboard المفضل؟** (dashboard.elprofessor.com؟)
8. **هل Supabase مقبول كـ backend أم تفضل شيء آخر؟**
9. **من سيستخدم الـ Dashboard؟** (عبدالرحمن فقط؟ أم كل المؤسسين؟)
10. **هل تريد ربط الـ Dashboard بـ n8n automations؟**

---

# 13. First Executable Prompt - Phase 0

```
أنا أعمل على بناء Dashboard داخلية لشركة البروفيسور (ElProfessor).

المهمة الأولى: تنظيف البيانات المالية.

لديّ البيانات التالية (مرفقة):

1. كشف حساب Wise بالدولار (592 عملية من فبراير 2024 حتى مايو 2026)
2. ملف إيرادات JSON (14 إدخال)
3. ملف مصروفات JSON (38 إدخال)
4. قائمة عملاء (59 مسجل)

المشاكل المكتشفة:
- مصروفات شخصية مخلوطة بالتجارية في كشف البنك
- أسماء عملاء متكررة بأشكال مختلفة (basim ghazi = baseem dweekat)
- تواريخ في ملف "2025" تخص 2024 و 2026
- Monthly totals كلها خاطئة
- Financial summary يتناقض مع التقرير الكامل

المطلوب:
1. أنشئ 4 ملفات JSON منظفة:
   - cleaned_revenues.json (مع تصحيح التواريخ والأسماء وحساب monthly_totals صحيح)
   - cleaned_expenses.json (مع فصل business=true/false لكل عملية)
   - clients_master.json (دمج قائمة المسجلين مع الدافعين، بدون تكرار)
   - financial_reconciled.json (ملخص نهائي بأرقام صحيحة)

2. قواعد التصنيف:
   - شخصي: Talabat, Fathallah, Aswak, Dokkan, coffee, We-Fbb, We-Mobile, Vodafone, Uber, Careem
   - أعمال: OpenAI, Anthropic, Claude, ChatGPT, Canva, Google Cloud, ElevenLabs, Hsoub, GitHub
   - سفر عمل: Flydubai, Al Emad Car Rental
   - سعر الصرف: 50 ج.م/دولار

3. النتيجة النهائية يجب أن تحقق:
   - مجموع إيرادات USD = $4,920.18
   - مجموع إيرادات EGP = 1,529.39
   - الملفات متسقة مع بعضها (لا تناقضات)
```

---

# 14. Second Executable Prompt - Phase 1

```
ابنِ MVP Dashboard لشركة البروفيسور.

Tech Stack:
- Next.js 14 (App Router)
- Supabase (PostgreSQL + Auth + Storage)
- Tailwind CSS + shadcn/ui
- Recharts للـ charts
- RTL عربي بالكامل

الصفحات:

1. /login
   - تسجيل دخول بـ email + password
   - الـ auth عبر Supabase
   - redirect لـ /dashboard بعد الدخول

2. /dashboard (الصفحة الرئيسية)
   - 4 بطاقات:
     * إجمالي الإيرادات (247,538 ج.م)
     * إجمالي المصروفات (32,970 ج.م)
     * صافي الربح (+214,567 ج.م)
     * عدد العملاء الدافعين (5)
   - Line chart: إيرادات vs مصروفات شهرياً (آخر 12 شهر)
   - جدول: آخر 5 عمليات مالية

3. /finance
   - Tab: إيرادات
     * جدول (التاريخ، العميل، المبلغ $, المبلغ ج.م, المصدر)
     * فلتر بالتاريخ والعميل
     * إجمالي في الأسفل
   - Tab: مصروفات
     * جدول (التاريخ، الفئة، الوصف، المبلغ $, المبلغ ج.م)
     * فلتر بالفئة والتاريخ
     * تمييز: أعمال (أخضر) / شخصي (رمادي)
   - زر "إضافة إيراد" / "إضافة مصروف" → modal form

4. /clients
   - جدول (الاسم، الإيميل، النوع، إجمالي المدفوع، تاريخ التسجيل)
   - فلتر: الكل | دافعين | مسجلين فقط
   - بحث بالاسم

5. /clients/[id]
   - بيانات العميل
   - قائمة دفعاته (payments مربوطة بـ client_id)
   - إجمالي المدفوع

التصميم:
- الألوان: أزرق داكن (#1e3a5f) للـ sidebar + أبيض للمحتوى + رمادي فاتح (#f8fafc) للخلفية
- Sidebar ثابت على اليمين (RTL)
- شعار "البروفيسور" في أعلى الـ sidebar
- Navigation: لوحة التحكم | المالية | العملاء

Database:
- أنشئ الجداول: users, payments, expenses, clients, settings
- استورد البيانات من الملفات المنظفة (Phase 0 output)

الأمان:
- Supabase Auth
- Protected routes (redirect to /login if not authenticated)
- Row Level Security على كل الجداول
```

---

*نهاية الوثيقة*
*تم إعداد هذا التحليل بناءً على فحص كامل لملفات النظام الأصلي (24 ملف) وملف البيانات الكاملة (56 ملف) بما في ذلك 5 كشوف بنكية و15 ملف Excel وجميع ملفات JSON.*
