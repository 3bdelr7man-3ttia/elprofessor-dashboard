# -*- coding: utf-8 -*-
"""منصّة وهمية لقسم «العقل» (الجولة الأخيرة): فوق `D3Platform` تضيف ما يقرؤه القسم —

  * `assign_log` على ملفات مختارة بأوقات **اليوم** (بتوقيت القاهرة) · توزيع تلقائي ودفع، نقل لانتهاء المهلة، وتغيير يدوي لاحق من المؤسس.
  * `GET/PUT /api/bridge/expert-files/settings` بحقول الجولة الأخيرة: `explicit` · `updated_at` · `updated_by`.
  * `GET /api/policies` (مهلة تحرير أجر الخبير) · `GET /api/bridge/settings/invites` (جيل موافقة الدعوات).
  * نبضات الحارس كلها حديثة، وتنبيه «متوقّف» اختياري.
  * مفاتيح الأعطال: `down` (مسار يرجع ٥٠٢) · `today_status` (ردّ `status=all` بحالة معيّنة) · `partial` (يُعلن أن الصفحة مقصوصة).

كل أوقات السجل مبنية من منتصف ليل القاهرة الحالي، فالسجل «اليوم» ثابت مهما كانت ساعة التشغيل. ⛔ صفر شبكة.
"""
import copy
import datetime
import os
import sys

try:
    from zoneinfo import ZoneInfo
    CAIRO = ZoneInfo('Africa/Cairo')
except Exception:                                    # pragma: no cover
    CAIRO = datetime.timezone(datetime.timedelta(hours=2))

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ef_fixtures as fx          # noqa: E402
import d3_fixtures as d3fx        # noqa: E402

UTC = datetime.timezone.utc
HALA, NADA, KARIM, SAMI = 'hala@experts.test', 'nada@experts.test', 'karim@experts.test', 'sami@experts.test'
ALERT_SLA = '⚠️ حارس المهلة والاسترداد: متوقّفة منذ 5.2 ساعة، والحدّ المسموح 2 ساعة'


def local_now():
    return datetime.datetime.now(CAIRO)


def local_midnight():
    return local_now().replace(hour=0, minute=0, second=0, microsecond=0)


def today_at(frac):
    """وقت داخل يوم القاهرة الحالي: `frac` من 0 إلى 1 من الزمن المنقضي منذ منتصف الليل. ISO بمنطقة UTC."""
    mid = local_midnight()
    return (mid + (local_now() - mid) * frac).astimezone(UTC).isoformat()


def yesterday_at():
    return (local_midnight() - datetime.timedelta(hours=3)).astimezone(UTC).isoformat()


def today_naive_utc(frac):
    """نفس `today_at` لكن بلا منطقة (طريقة SQLite) — لتقارير المساعدين."""
    return datetime.datetime.fromisoformat(today_at(frac)).replace(tzinfo=None)


def entry(at, to, by='auto', reason='paid', why='', to_name=None):
    e = {'at': at, 'to': to, 'by': by, 'reason': reason, 'why': why}
    if to_name:
        e['to_name'] = to_name
    return e


def _sent(fid, title, expert, client, entries, status='assigned'):
    f = fx._file(fid, title=title, status=status, law='eg', tier='written', amount=500.0, currency='EGP', expert_amount=300.0,
                 paid_h=-4.0, deadline_h=40.0, client=client, assigned_to=expert if status == 'assigned' else None,
                 expert_email=expert if status != 'assigned' else None, assigned_h=-3.0 if status == 'assigned' else None,
                 writing_due_h=20.0 if status == 'writing' else None,
                 pool=[HALA, NADA, KARIM])
    f['assign_log'] = entries
    return f


def brain_files():
    """أربع ملفات: A وزّع وحده (لم يُستلم) · B نُقل لانتهاء المهلة · C استلمه الخبير · D وزّعه العقل ثم غيّره المؤسس."""
    a = _sent('ef-ba-11aa22bb', 'عقد إيجار تجاري — بند الإخلاء', HALA, 'منى',
              [entry(today_at(.30), HALA, why='نفس التخصص · أقل حمل')])
    b = _sent('ef-bb-22bb33cc', 'إنذار بسداد متأخرات الإيجار', KARIM, 'ليلى',
              [entry(yesterday_at(), NADA, why='نفس بلد القانون'), entry(today_at(.45), KARIM, reason='timeout', why='لم يُستلم في 12 ساعة · أقل حمل')])
    c = _sent('ef-bc-33cc44dd', 'نفقة زوجة بعد الانفصال', SAMI, 'عمر',
              [entry(today_at(.20), SAMI, why='نفس التخصص')], status='writing')
    d = _sent('ef-bd-44dd55ee', 'ميراث وتقسيم تركة', NADA, 'رنا',
              [entry(today_at(.55), HALA, why='نفس بلد القانون'), entry(today_at(.70), NADA, by='founder', reason='manual', why='')])
    return a, b, c, d


class BrainPlatform(d3fx.D3Platform):
    """`D3Platform(d2=True)` + مدخلات سجل العقل. المعاملات: entries (يزرع الملفات الأربعة) · alert (تنبيه «متوقّف») · keep_alerts."""

    def __init__(self, entries=True, alert=False, keep_alerts=False, auto=True, release_hours=72, generation=2, **kw):
        super(BrainPlatform, self).__init__(d2=True, **kw)
        self.alert = alert
        self.keep_alerts = keep_alerts
        self.auto_assign = auto
        self.release_hours = release_hours
        self.generation = generation
        self.explicit = True
        self.updated_at = today_at(.05)
        self.updated_by = 'admin@local.test'
        self.down = set()
        self.today_status = None          # (status, payload) لرد `status=all`
        self.partial = False
        self.policies_body = None
        # لا سجل قديم يتسرّب إلى «اليوم»: كل ملفات الأساس بلا assign_log
        for lane in self._lanes():
            for f in lane:
                f['assign_log'] = []
        for f in self.person_files:
            f['assign_log'] = []
        self.brain_rows = []
        if entries:
            a, b, c, d = brain_files()
            self.waiting = sorted(self.waiting + [a, b, d], key=lambda f: f['claim_deadline_at'])
            self.person_files = list(self.person_files) + [c]
            self.brain_rows = [a, b, c, d]

    def queue(self):
        q = super(BrainPlatform, self).queue()
        fresh = {'tick_last': fx.iso(-0.2), 'remind_last': fx.iso(-0.5), 'sla_last': fx.iso(-0.3), 'backup_last': fx.iso(-20),
                 'invite_reminders_last': fx.iso(-1), 'coach_stalled_last': fx.iso(-5)}
        q['heartbeats'] = fresh
        if not self.keep_alerts:
            q['alerts'] = []
        if self.alert:
            q['alerts'] = list(q.get('alerts', [])) + [ALERT_SLA]
        return q

    def _route(self, method, path, params, body):
        m = method.upper()
        if path in self.down:
            return 502, {'detail': 'تعذر الاتصال'}
        if path == '/api/policies' and m == 'GET':
            return 200, (self.policies_body if self.policies_body is not None else {'escrow': {'auto_release_hours': self.release_hours}})
        if path == '/api/bridge/settings/invites' and m == 'GET':
            return 200, {'welcome_video_url': '', 'platform_video_url': '', 'member_invite_quota': None,
                         'invite_approval_from_generation': self.generation}
        if path == '/api/bridge/expert-files/settings':
            if not self.settings_enabled:
                return 404, {'detail': 'Not Found'}
            if m == 'GET':
                return 200, {'auto_assign': self.auto_assign, 'explicit': self.explicit, 'updated_at': self.updated_at, 'updated_by': self.updated_by}
            if m == 'PUT':
                if self.settings_fail:
                    return self.settings_fail
                v = (body or {}).get('auto_assign')
                if not isinstance(v, bool):
                    return 422, {'detail': 'auto_assign لازم true أو false'}
                self.auto_assign = v
                self.explicit = True
                self.updated_at = datetime.datetime.now(UTC).isoformat()
                self.updated_by = (body or {}).get('by') or 'admin@local.test'
                self.settings_puts.append(copy.deepcopy(body))
                return 200, {'auto_assign': v}
        if path == '/api/bridge/expert-files' and m == 'GET' and (params or {}).get('status') == 'all':
            if self.today_status is not None:
                return self.today_status
            out = super(BrainPlatform, self)._route(method, path, params, body)
            if out and out[0] == 200 and self.partial:
                payload = out[1]
                payload['total'] = payload.get('count', 0) + 40
                for f in payload['files']:
                    f['updated_at'] = datetime.datetime.now(UTC).isoformat()
            return out
        return super(BrainPlatform, self)._route(method, path, params, body)


# ---------------------------------------------------------------- بيانات الداشبورد نفسه (SQLite): تقارير المساعدين وعدّاد اليوم
AGENTS = [('articles', 'المقالات والمحتوى'), ('seo', 'تحسين الظهور (SEO/AEO)'), ('automation', 'رصد الأتمتة'), ('sales', 'المبيعات'),
          ('marketing', 'التسويق'), ('platform', 'إدارة المنصة'), ('topics', 'المواضيع'), ('incoming', 'تحليل الوارد'), ('dev', 'التطوير'),
          ('finance', 'المالية'), ('master', 'الصورة الكاملة (Master)')]


def seed_brain_dash(appmod, used=3, today_reports=('articles', 'master'), data_only=('marketing',), reset=True):
    """يزرع تقريرًا لكل مساعد: القديم قبل ثلاثة أيام، وما في `today_reports` اليوم. `data_only` تقاريره أرقام فقط. ويضبط عدّاد اليوم `used`."""
    m = appmod
    import v2_brain_routes
    with m.app.app_context():
        if reset:
            v2_brain_routes._model(m.db).query.delete()
            m.AgentReport.query.delete()
            m.AIDailyUsage.query.delete()
            m.AuditLog.query.filter(m.AuditLog.action.in_(v2_brain_routes.HISTORY_ACTIONS)).delete(synchronize_session=False)
            m.db.session.commit()
            # تاريخ تغيير نظيف: أُوقف قبل ٣ ساعات ثم شُغّل قبل ساعتين (فلا تظهر في الورقة «الآن» من خطوات اللقطة).
            now = datetime.datetime.utcnow()
            for hrs, on in ((3, False), (2, True)):
                m.db.session.add(m.AuditLog(actor_email='admin@local.test', action='expert_file.auto_assign', target='settings',
                                            meta_json=m.json.dumps({'auto_assign': on}), created_at=now - datetime.timedelta(hours=hrs)))
            m.db.session.commit()
        for aid, label in AGENTS:
            fresh = aid in today_reports
            when = today_naive_utc(.5 if aid == 'master' else .35) if fresh else (datetime.datetime.utcnow() - datetime.timedelta(days=3))
            only = aid in data_only
            summary = ('تعذّر التحليل الآن — هذه أرقام حقيقية بلا تحليل نصّي.' if only else
                       'ثلاث مسودات تنتظر الاعتماد، وموضوعان مهمّان لم نكتب عنهما بعد.' if aid != 'master' else
                       'الصورة اليوم مستقرة: ملفان ينتظران خبيرًا، ومسودتان للمقالات، ولا شيء متأخر في الفلوس.')
            m.db.session.add(m.AgentReport(agent=aid, summary=summary, created_at=when,
                                           bullets_json=m.json.dumps(['عدد المسودات المنتظرة: 3', 'آخر نشر منذ يومين'], ensure_ascii=False),
                                           actions_json=m.json.dumps(['اعتمد المسودة الأقدم اليوم', 'اطلب مقالًا عن عقود الإيجار', 'راجع ملف الخبير المتأخر'] if aid == 'master' else ['اعتمد مسودة واحدة'], ensure_ascii=False)))
        if used is not None:
            m.db.session.add(m.AIDailyUsage(day=m._ai_utc_day(), calls=used))
        m.db.session.commit()


# ---------------------------------------------------------------- «ما يكتبه العقل» (الجولة الثانية): مسارات `/api/v2/brain/{switches,items,run,runs/latest}` المزيّفة
# الخادم الحقيقي لها في الباكدج P1؛ هنا جدول في الذاكرة بنفس الأشكال المعتمدة في SPEC brain2 §2.5 (لا شبكة ولا ذكاء).
PRODUCERS = [
    # id, section, kind, label, sentence, lock_reason, may_run_alone, default_mode
    ('opinion', 'home', 'opinion', 'رأي العقل في كل قرار', 'عندما يظهر قرار ينتظرك، يكتب العقل رأيه فيه من بيانات البطاقة نفسها.', '', True, 'alone'),
    ('reply_draft', 'people', 'draft', 'مسودات الرد على الرسائل', 'عندما تصل رسالة أو طلب تواصل، يكتب العقل مسودة رد تراجعها قبل أن تصل إلى صاحبها.',
     'يسألك دائمًا لأن الرد يصل إلى صاحب الرسالة.', False, 'ask'),
    ('course_review', 'courses', 'draft', 'مراجعة الدورة قبل النشر', 'عندما تُقدَّم دورة للنشر، يكتب العقل ما ينقصها ويقترح: انشر أو أصلح أولًا.',
     'يسألك دائمًا لأن النشر يظهر للناس.', False, 'ask'),
    ('market_match', 'market', 'draft', 'ربط طلبات السوق بدورة مناسبة', 'عندما يطلب عضو شيئًا تغطيه دورة لدينا، يقترح العقل ربطه بها.',
     'يسألك دائمًا لأنه يغيّر بيانات الطلب على المنصة.', False, 'ask'),
    ('seo_notes', 'content', 'note', 'ملاحظات الظهور في البحث على المسودات', 'عندما تنتظر مسودة مقال، يكتب العقل ما يحسّن ظهورها في البحث. لا يُنشر شيء.', '', True, 'alone'),
    ('campaign_comment', 'marketing', 'note', 'تعليق على الحملات', 'عندما تتغير أرقام حملة، يكتب العقل تعليقًا قصيرًا عليها.', '', True, 'alone'),
    ('weekly_read', 'reports', 'note', 'قراءة الأسبوع', 'في بداية كل أسبوع، يكتب العقل قراءة قصيرة لأرقام الأسبوع الماضي.', '', True, 'alone'),
    ('forecast_comment', 'company', 'note', 'تعليق على التوقعات', 'عندما تتغير التوقعات أو الأرقام الفعلية، يكتب العقل تعليقًا عليها.', '', True, 'alone'),
]


def make_item(iid, producer, section, kind, label, status, text='', tag='', approve='', at=.3, decided=None, by='', source='ai'):
    return {'id': iid, 'producer': producer, 'section': section, 'kind': kind, 'target_label': label, 'body': {'text': text}, 'status': status,
            'source': source, 'created_at': today_at(at), 'decided_at': today_at(decided) if decided is not None else None, 'decided_by': by,
            'tag': tag, 'approve_label': approve, 'last_error': ''}


def brain2_items():
    """ملاحظتان (واحدة تبقى وأخرى تُحذف في اللقطة) · اقتراحان ينتظران · مُنفَّذ · مرفوض · محذوف · فاشل · ثلاثة آراء."""
    return [
        make_item('bi-note-1', 'seo_notes', 'content', 'note', 'مقال: عقود الإيجار التجاري', 'done_alone', 'العنوان أطول من اللازم، ولا يوجد وصف قصير.', at=.62),
        make_item('bi-note-2', 'campaign_comment', 'marketing', 'note', 'حملة الإيجار — فيسبوك', 'done_alone', 'الإنفاق ارتفع والنتائج ثابتة.', at=.58),
        make_item('bi-prop-1', 'reply_draft', 'people', 'draft', 'رسالة من منى عن موعد الاستشارة', 'proposed', 'مسودة الرد على الرسالة.', tag='مسودة رد', approve='أرسل الرد', at=.55),
        make_item('bi-prop-2', 'course_review', 'courses', 'draft', 'دورة أساسيات التسويق القانوني', 'proposed', 'ينقصها وصف المخرجات.', tag='مراجعة دورة', approve='افتح الدورة', at=.5),
        make_item('bi-done-1', 'market_match', 'market', 'draft', 'طلب: تدريب على عقود العمل', 'approved', 'اربطه بدورة عقود العمل.', tag='ربط بدورة', approve='اربطه بالدورة', at=.4, decided=.45, by='admin@local.test'),
        make_item('bi-rej-1', 'reply_draft', 'people', 'draft', 'رسالة من كريم', 'rejected', 'مسودة.', tag='مسودة رد', approve='أرسل الرد', at=.35, decided=.38, by='admin@local.test'),
        make_item('bi-disc-1', 'seo_notes', 'content', 'note', 'مقال: نفقة الزوجة', 'discarded', 'ملاحظة قديمة.', at=.3, decided=.33, by='admin@local.test'),
        make_item('bi-fail-1', 'weekly_read', 'reports', 'note', 'الأسبوع الماضي', 'failed', '', at=.25),
        make_item('bi-op-1', 'opinion', 'home', 'opinion', 'تحويل للخبير', 'done_alone', 'راجع الحساب قبل التحويل.', at=.2),
        make_item('bi-op-2', 'opinion', 'home', 'opinion', 'طلب انضمام', 'done_alone', 'الملف مكتمل.', at=.21),
        make_item('bi-op-3', 'opinion', 'home', 'opinion', 'نزاع على ملف', 'done_alone', 'اسمع الطرفين.', at=.22),
    ]


class Brain2Fake(object):
    """يرد على مسارات العقل الجديدة. `handle(method, path, query, body)` ⇒ (status, payload) أو None لو المسار ليس من نصيبه.

    المعاملات: items (قائمة العناصر · الافتراضي فاضية) · writer ('main'|'backup'|None) · used/cap (عدّاد اليوم) · active (جولة جارية) · down (مجموعة مسارات ترجع ٥٠٢)."""
    OWN = ('/api/v2/brain/switches', '/api/v2/brain/items', '/api/v2/brain/run', '/api/v2/brain/runs/latest')

    def __init__(self, items=None, writer='main', used=12, cap=60, active=False, down=()):
        self.modes = {p[0]: p[7] for p in PRODUCERS}
        self.stamp = {}
        self.items = copy.deepcopy(items) if items else []
        self.writer = writer
        self.used = used
        self.cap = cap
        self.active = active
        self.down = set(down)
        self.writes = []            # (method, path, body)
        self.item_queries = []

    def owns(self, path):
        return path in self.OWN or path.startswith('/api/v2/brain/switches/') or (path.startswith('/api/v2/brain/items/') and path.endswith('/discard'))

    def _switch(self, p):
        st = self.stamp.get(p[0])
        return {'id': p[0], 'section': p[1], 'kind': p[2], 'label': p[3], 'sentence': p[4], 'lock_reason': p[5], 'may_run_alone': p[6],
                'mode': self.modes[p[0]], 'updated_at': st[0] if st else None, 'updated_by': st[1] if st else ''}

    def handle(self, method, path, query, body):
        m = method.upper()
        if not self.owns(path):
            return None
        if path in self.down:
            return 502, {'error': 'تعذر الاتصال'}
        if path == '/api/v2/brain/switches' and m == 'GET':
            return 200, {'switches': [self._switch(p) for p in PRODUCERS], 'writer': self.writer, 'brain_today': {'used': self.used, 'cap': self.cap}}
        if path.startswith('/api/v2/brain/switches/') and m == 'PUT':
            pid = path.rsplit('/', 1)[1]
            prod = [p for p in PRODUCERS if p[0] == pid]
            self.writes.append((m, path, copy.deepcopy(body)))
            if not prod:
                return 404, {'error': 'غير موجود'}
            mode = (body or {}).get('mode')
            if (body or {}).get('confirmed') is not True or mode not in ('alone', 'ask', 'off'):
                return 400, {'error': 'تعذّر تنفيذ العملية'}
            if mode == 'alone' and not prod[0][6]:
                return 400, {'error': 'هذا لا يعمل وحده: ' + prod[0][5]}
            self.modes[pid] = mode
            self.stamp[pid] = (datetime.datetime.now(UTC).isoformat(), 'admin@local.test')
            return 200, {'ok': True, 'id': pid, 'mode': mode}
        if path == '/api/v2/brain/items' and m == 'GET':
            self.item_queries.append(dict(query))
            return 200, {'items': copy.deepcopy(self.items)}
        if path.startswith('/api/v2/brain/items/') and path.endswith('/discard') and m == 'POST':
            iid = path.split('/')[-2]
            self.writes.append((m, path, copy.deepcopy(body)))
            it = [i for i in self.items if i['id'] == iid]
            if not it or it[0]['status'] != 'done_alone' or it[0]['kind'] != 'note':
                return 409, {'error': 'حُسم هذا الاقتراح من قبل'}
            it[0]['status'] = 'discarded'
            it[0]['decided_at'] = datetime.datetime.now(UTC).isoformat()
            it[0]['decided_by'] = 'admin@local.test'
            return 200, {'ok': True}
        if path == '/api/v2/brain/runs/latest' and m == 'GET':
            if self.active:
                return 200, {'run': {'id': 'run1', 'trigger': 'admin', 'started_at': datetime.datetime.now(UTC).isoformat(), 'finished_at': None, 'items': 0}}
            return 200, {'run': None}
        if path == '/api/v2/brain/run' and m == 'POST':
            self.writes.append((m, path, copy.deepcopy(body)))
            if (body or {}).get('confirmed') is not True:
                return 400, {'error': 'تعذّر تنفيذ العملية'}
            if self.active:
                return 409, {'error': 'العقل يكتب الآن. جرّب بعد قليل'}
            self.active = True
            return 202, {'run_id': 'run1'}
        return None
