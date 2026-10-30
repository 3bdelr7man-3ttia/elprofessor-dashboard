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
