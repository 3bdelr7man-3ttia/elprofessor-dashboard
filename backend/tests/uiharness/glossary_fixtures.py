# -*- coding: utf-8 -*-
"""بيانات لقطات تبويب «القاموس» (docs/v2/glossary/SPEC.md): مصطلحات في قاعدة الداشبورد (الحقيقية داخل العملية) + منصّة وهميّة بجسر النقاشات فقط.

  * `seed_terms(h)`  ⇒ يمسح جدول المصطلحات ويكتب ١٤ مصطلحًا بكل الحالات: مؤكَّد بنقاش وبموافقة ظهور الاسم · تحت التأكيد (منشور بلا ختم) · مسودة مُراجَعة ·
                       مسودات بلا ختم في مجالات مختلفة منها «أخرى» · قريب لم يُستورد بعد · أرقام لاتينية في المثال العربي لنختبر عرضها هندية.
                       وصفّ «published» في ROWS اختصار: يصير confirmed لو عليه ختم وإلا under_review.
  * `seed_reviews(h)` ⇒ مراجعات المتخصصين المعلّقة والمنتهية (مصطلح · دورة · مسار) في جدول `expert_review_submissions` (لا IP ولا متصفح).
  * `GlossaryPlatform` ⇒ `GET /api/bridge/topics` فقط (المصطلح لا يُنشئ نقاشًا). أي كتابة تصل المنصة = عطل يلتقطه السكربت (`h.platform_calls`).
  * `down = {path}` ⇒ ٥٠٣ لهذا المسار.
⛔ صفر شبكة: كله في الذاكرة. الأرقام في النصوص العربية لاتينية عمدًا في حقل واحد (example_ar) كي تثبت الشاشة أنها تعرضها هندية.
"""
import copy
import datetime
import json

TOPIC_PUB = 'c0ffee00-1111-4222-8333-444455556666'
TOPIC_OPEN = 'aaaaaaaa-0000-4000-8000-000000000001'
TOPIC_PUB2 = 'bbbbbbbb-0000-4000-8000-000000000002'
TOPIC_DRAFT = 'dddddddd-0000-4000-8000-000000000003'

TOPICS = [
    {'id': TOPIC_PUB, 'title': 'متى تُعفي القوة القاهرة من التنفيذ؟', 'status': 'published'},
    {'id': TOPIC_OPEN, 'title': 'هل يكفي شرط التحكيم وحده؟', 'status': 'open'},
    {'id': TOPIC_PUB2, 'title': 'كيف تُثبت الضرر في العقود الدولية؟', 'status': 'published'},
    {'id': TOPIC_DRAFT, 'title': 'مسودة لم تُنشر', 'status': 'draft'},
]

REVIEWER = ('أ. هبة الجندي', 'محامية')
D = datetime.datetime


class GlossaryPlatform(object):
    def __init__(self, topics=None):
        self.topics = copy.deepcopy(TOPICS if topics is None else topics)
        self.down = set()

    def handle(self, method, path, params, body):
        if path == '/api/bridge/topics' and method == 'GET':
            if path in self.down:
                return 503, {'detail': 'تعذر الاتصال'}
            return 200, copy.deepcopy(self.topics)
        return None


def _term(slug, ar, en, fr, area, definition, status='draft', reviewed=False, **kw):
    if status == 'published':
        status = 'confirmed' if reviewed else 'under_review'
    pub = status != 'draft'
    return dict(slug=slug, ar=ar, en=en, fr=fr, area=area, definition_ar=definition, status=status, source=kw.pop('source', 'seed'),
                example_en=kw.pop('example_en', None), example_ar=kw.pop('example_ar', None), false_friend_note_ar=kw.pop('false_friend_note_ar', None),
                countries_note_ar=kw.pop('countries_note_ar', None), related=json.dumps(kw.pop('related', []), ensure_ascii=False),
                saha_topic_id=kw.pop('saha_topic_id', None), published_at=D(2026, 10, 20, 9) if pub else None,
                reviewer_name_public=bool(kw.pop('public', False)) and reviewed, reviewed_by_name=REVIEWER[0] if reviewed else None, reviewed_by_role=REVIEWER[1] if reviewed else None,
                reviewed_at=D(2026, 10, 25, 10) if reviewed else None, created_at=D(2026, 10, 1), updated_at=D(2026, 10, 25), **kw)


ROWS = [
    _term('force-majeure', 'القوة القاهرة', 'force majeure', 'force majeure', 'contracts', 'حدث خارج عن إرادة الطرفين لا يمكن توقعه ولا دفعه، يعفي من تنفيذ الالتزام أو يؤجله.',
          status='published', reviewed=True, public=True, saha_topic_id=TOPIC_PUB, related=['frustration', 'hardship-clause', 'not-imported-yet'],
          example_en='The Seller is not liable for delay caused by force majeure exceeding 30 days.',
          example_ar='لا يسأل البائع عن التأخير بسبب القوة القاهرة إذا تجاوز 30 يومًا، ولا يتجاوز التعويض 50,000 دينار.',
          false_friend_note_ar='ليست القضاء والقدر بالمعنى العام، فالمصطلح القانوني يشترط الاستحالة وعدم التوقع.',
          countries_note_ar='القانون المدني المصري يعالجها في باب انقضاء الالتزام، وتختلف الشروط في الدول الأخرى.'),
    _term('injunction', 'الأمر القضائي المؤقت', 'injunction', 'injonction', 'litigation', 'أمر تصدره المحكمة بمنع فعل أو إلزام بفعل بصفة عاجلة ريثما يُفصل في الموضوع.',
          status='published', reviewed=False, example_en='The court granted an interim injunction.', example_ar='أصدرت المحكمة أمرًا مؤقتًا بوقف التنفيذ.'),
    _term('frustration', 'استحالة التنفيذ', 'frustration', 'impossibilité d\'exécution', 'contracts', 'زوال أساس العقد بحدث لاحق يجعل تنفيذه مستحيلًا أو مختلفًا جذريًا.',
          reviewed=True, related=['force-majeure']),
    _term('hardship-clause', 'شرط المشقة', 'hardship clause', 'clause de hardship', 'contracts', 'بند يتيح إعادة التفاوض حين ينقلب توازن العقد بسبب ظرف طارئ.'),
    _term('arbitral-award', 'حكم التحكيم', 'arbitral award', 'sentence arbitrale', 'arbitration', 'القرار النهائي الصادر عن هيئة التحكيم في النزاع المعروض عليها.',
          example_en='The award is final and binding on the parties.'),
    _term('burden-of-proof', 'عبء الإثبات', 'burden of proof', 'charge de la preuve', 'litigation', 'التزام أحد الخصمين بإقامة الدليل على ما يدّعيه أمام المحكمة.'),
    _term('shareholders-agreement', 'اتفاق المساهمين', "shareholders' agreement", 'pacte d\'associés', 'corporate', 'اتفاق بين مساهمي الشركة ينظّم الإدارة والتصويت ونقل الأسهم.'),
    _term('mens-rea', 'القصد الجنائي', 'mens rea', 'élément moral', 'criminal', 'الركن المعنوي للجريمة، أي نية الجاني ومعرفته بما يفعل.'),
    _term('trademark', 'العلامة التجارية', 'trademark', 'marque', 'ip', 'إشارة مميزة تُستعمل لتمييز سلع أو خدمات منشأة عن غيرها.'),
    _term('probation-period', 'فترة التجربة', 'probation period', "période d'essai", 'labor', 'مدة أولية يجوز فيها إنهاء عقد العمل بشروط أخف.'),
    _term('child-custody', 'الحضانة', 'child custody', 'garde de l\'enfant', 'family', 'رعاية الصغير وتربيته وحفظه في سن معينة لدى من يستحقها قانونًا.'),
    _term('misc-term', 'مصطلح متفرّق', 'miscellaneous term', None, 'other', 'مصطلح لا يندرج تحت مجال محدد من المجالات المعروفة.'),
    _term('consideration', 'المقابل', 'consideration', 'contrepartie', 'contracts', 'ما يقدّمه كل طرف في العقد مقابل التزام الطرف الآخر، وهو شرط لصحة العقد في القانون الإنجليزي.',
          reviewed=True, countries_note_ar='لا يُشترط المقابل بهذا المعنى في القوانين المدنية.'),
    _term('indemnity', 'التعويض الاتفاقي', 'indemnity', 'indemnité', 'contracts', 'التزام أحد الطرفين بتعويض الآخر عن خسارة محددة، وفق ما يتفقان عليه في العقد. ' * 4),
]


def seed_terms(h, rows=None, require_review=None):
    """يكتب المصطلحات في قاعدة الداشبورد (الحقيقية داخل العملية) ويضبط إعداد المراجعة (None = غياب الصف = مغلق، وهو الافتراضي)."""
    m = h.app
    with m.app.app_context():
        m.db.create_all()
        m.GlossaryTerm.query.delete()
        m.ExpertReviewSubmission.query.delete()
        m.Setting.query.filter_by(key='glossary.require_review').delete()
        m.AuditLog.query.filter(m.AuditLog.action.like('glossary%')).delete(synchronize_session=False)
        for r in (ROWS if rows is None else rows):
            m.db.session.add(m.GlossaryTerm(**copy.deepcopy(r)))
        if require_review is not None:
            m.db.session.add(m.Setting(key='glossary.require_review', value='1' if require_review else '0'))
        m.db.session.commit()


def term(h, slug):
    """صف من القاعدة كقاموس (أو None)."""
    m = h.app
    with m.app.app_context():
        t = m.GlossaryTerm.query.filter_by(slug=slug).first()
        if t is None:
            return None
        return {c.name: getattr(t, c.name) for c in t.__table__.columns}


def count(h):
    m = h.app
    with m.app.app_context():
        return m.GlossaryTerm.query.count()


def audits(h, action=None):
    m = h.app
    with m.app.app_context():
        q = m.AuditLog.query.filter(m.AuditLog.action.like('glossary%'))
        if action:
            q = q.filter_by(action=action)
        return [(a.actor_email, a.action, a.target, json.loads(a.meta_json or '{}')) for a in q.order_by(m.AuditLog.id).all()]


def setting(h):
    m = h.app
    with m.app.app_context():
        s = m.Setting.query.get('glossary.require_review')
        return None if s is None else s.value


def seed_reviews(h):
    """مراجعات المتخصصين: ٥ معلّقة (تأكيد على «تحت التأكيد» · اقتراح على مؤكَّد · تأكيد على مصطلح تغيّر بعدها · دورة · مسار) ومنتهيتان.
    ⇒ {الرمز: المعرّف}. term_updated_at = لقطة وقت التقديم؛ المصطلح تغيّر بعدها لو أقدم من updated_at (٢٠٢٦-١٠-٢٥)."""
    m = h.app
    ids = {}
    snap, old = D(2026, 10, 25), D(2026, 10, 10)

    def add(key, **kw):
        base = dict(status='pending', created_at=D(2026, 10, 28, 9), show_name=False, specialty='law_practice', verdict='confirm', term_updated_at=None)
        base.update(kw)
        r = m.ExpertReviewSubmission(**base)
        m.db.session.add(r)
        m.db.session.flush()
        ids[key] = r.id
    with m.app.app_context():
        add('confirm', kind='glossary_term', ref='injunction', ref_title='الأمر القضائي المؤقت', name='د. نادر فؤاد', email='nader@example.test', specialty='law_teaching',
            show_name=True, text='الترجمة والتعريف صحيحان، وأوافق عليهما.', term_updated_at=snap)
        add('suggest', kind='glossary_term', ref='force-majeure', ref_title='القوة القاهرة', name='ليلى حسن', email='laila@example.test', specialty='other', verdict='suggest',
            show_name=False, text='أقترح أن يُضاف إلى التعريف شرط عدم إمكان الدفع، فهو ركن في أغلب الأنظمة.', created_at=D(2026, 10, 29, 9), term_updated_at=snap)
        add('changed', kind='glossary_term', ref='force-majeure', ref_title='القوة القاهرة', name='كريم سالم', email='karim@example.test', specialty='judiciary', show_name=True,
            text='يصلح التعريف كما هو.', created_at=D(2026, 10, 27, 9), term_updated_at=old)
        add('course', kind='course', ref='legal-english-101', ref_title='الإنجليزية القانونية الأساسية', name='منى عادل', email='mona@example.test', specialty='legal_translation',
            text='الدرس الثالث يحتاج مثالًا إضافيًا.', created_at=D(2026, 10, 30, 9), verdict='suggest')
        add('track', kind='track', ref='contracts-track', ref_title='مسار العقود', name='سامي رشاد', email='sami@example.test', specialty='corporate_counsel', show_name=True,
            created_at=D(2026, 10, 26, 9))
        add('done_ok', kind='glossary_term', ref='frustration', ref_title='استحالة التنفيذ', name='هالة يوسف', email='hala@example.test', specialty='law_practice', status='approved',
            decided_at=D(2026, 10, 27, 12), decided_by='admin@local.test', term_updated_at=snap, created_at=D(2026, 10, 20, 9))
        add('done_no', kind='course', ref='legal-english-101', ref_title='الإنجليزية القانونية الأساسية', name='رامي كمال', email='rami@example.test', specialty='judiciary',
            status='rejected', decided_at=D(2026, 10, 27, 13), decided_by='admin@local.test', admin_note='خارج النطاق', created_at=D(2026, 10, 21, 9))
        m.db.session.commit()
    return ids


def review(h, rid):
    m = h.app
    with m.app.app_context():
        r = m.db.session.get(m.ExpertReviewSubmission, rid)
        return None if r is None else {c.name: getattr(r, c.name) for c in r.__table__.columns}
