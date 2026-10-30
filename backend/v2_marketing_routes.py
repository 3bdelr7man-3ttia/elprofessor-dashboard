# -*- coding: utf-8 -*-
"""«التسويق» (الجولة النهائية) — مسارات الخادم الجديدة. تُسجَّل بسطر واحد في app.py:

    __import__('v2_marketing_routes').register(app, globals())   # v2s:marketing

⛔ كل مسار: أدمن بس + المفتاح (`DASH_V2_ENABLED`) مفتوح وإلا ٤٠٤ بلا أي كتابة ولا نداء للمنصة + `Cache-Control: no-store`.
⛔ الفاعل من التوكن فقط (`_actor_email`) — أي `by` في الجسم يُتجاهل.
⛔ لا تغيير في نموذج `Campaign` ولا في `/api/campaigns`: ربط الحملة بصاحبها في جدول جانبي، وحدّ «حملات الشاشة القديمة» في جدول مفاتيح.
الجدولان بيتعملوا كسولًا (`CREATE TABLE IF NOT EXISTS`) عبر `db.session.execute` فيشتغلوا على SQLite وPostgres.
"""
import datetime

from sqlalchemy import text

OWNER_KINDS = ('platform', 'course', 'book')
TITLE_MAX = 200
PUBLISHED_CAP = 50
LEGACY_KEY = 'legacy_max_campaign_id'
CHECKED_KEY = 'legacy_checked'
CUTOFF_KEY = 'legacy_cutoff'           # لحظة أول تشغيل: كل حملة أُنشئت قبلها «من الشاشة القديمة»


def register(app, env):
    token_required = env['token_required']
    roles_required = env['roles_required']
    closed = env['_v2_closed']
    ns = env['_v2_ns']
    v2_get = env['_v2_get']
    v2_body = env['_v2_body']
    audit = env['_audit']
    actor = env['_actor_email']
    id_re = env['V2_ID_RE']
    month_re = env['V2_MONTH_RE']
    db = env['db']
    Article = env['Article']
    Campaign = env['Campaign']
    jsonify = env['jsonify']
    request = env['request']

    def err(msg, status):
        return ns((jsonify({'error': msg}), status))

    def now_iso():
        return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

    def ensure():
        """ينشئ الجدولين لو ناقصين، ويكتب حدّ حملات الشاشة القديمة مرة واحدة (أول تشغيل والمفتاح مفتوح)."""
        db.session.execute(text(
            'CREATE TABLE IF NOT EXISTS v2_campaign_owner ('
            'campaign_id INTEGER PRIMARY KEY, owner_kind TEXT NOT NULL, owner_id TEXT NOT NULL DEFAULT \'\', '
            'owner_title TEXT NOT NULL DEFAULT \'\', updated_at TEXT NOT NULL, updated_by TEXT NOT NULL DEFAULT \'\')'))
        db.session.execute(text('CREATE TABLE IF NOT EXISTS v2_marketing_meta (k TEXT PRIMARY KEY, v TEXT NOT NULL)'))
        try:
            db.session.execute(text(
                'INSERT INTO v2_marketing_meta (k, v) SELECT :k, CAST(COALESCE(MAX(id), 0) AS TEXT) FROM campaigns '
                'WHERE NOT EXISTS (SELECT 1 FROM v2_marketing_meta WHERE k = :k)'), {'k': LEGACY_KEY})
            db.session.commit()
            db.session.execute(text(
                'INSERT INTO v2_marketing_meta (k, v) SELECT :c, :t WHERE NOT EXISTS (SELECT 1 FROM v2_marketing_meta WHERE k = :c)'),
                {'c': CUTOFF_KEY, 't': datetime.datetime.utcnow().isoformat()})
            db.session.commit()
        except Exception:
            db.session.rollback()          # سباق مع طلب تاني كتب نفس المفتاح: كفاية

    def meta(key):
        row = db.session.execute(text('SELECT v FROM v2_marketing_meta WHERE k = :k'), {'k': key}).fetchone()
        return row[0] if row else None

    def as_dt(v):
        """يحوّل نص/تاريخ إلى datetime بلا منطقة زمنية، أو None."""
        if isinstance(v, datetime.datetime):
            return v.replace(tzinfo=None)
        try:
            return datetime.datetime.fromisoformat(str(v).replace('Z', '').replace(' ', 'T'))
        except (TypeError, ValueError):
            return None

    def legacy_max():
        """أعلى رقم حملة أُنشئت قبل أول تشغيل. SQLite يعيد استخدام أعلى رقم بعد حذفه، فحملة جديدة بنفس الرقم تُحسب بتاريخ إنشائها لا برقمها."""
        stored = int(meta(LEGACY_KEY) or 0)
        cut = as_dt(meta(CUTOFF_KEY))
        if stored <= 0 or cut is None:
            return stored
        top = 0
        for cid, made in db.session.query(Campaign.id, Campaign.created_at).filter(Campaign.id <= stored).all():
            made = as_dt(made)
            if (made is None or made <= cut) and cid > top:
                top = cid
        return top

    def owner_item(row):
        return {'campaign_id': row[0], 'owner_kind': row[1], 'owner_id': row[2], 'owner_title': row[3], 'updated_at': row[4], 'updated_by': row[5]}

    def guard():
        gate = closed()
        if gate:
            return gate
        try:
            ensure()
        except Exception:
            db.session.rollback()
            return err('تعذّر تجهيز سجل التسويق', 500)
        return None

    # ---------------------------------------------------------------- المقالات المنشورة
    @app.route('/api/v2/marketing/published', methods=['GET'], endpoint='v2mk_published')
    @token_required
    @roles_required('admin')
    def v2mk_published():
        gate = closed()
        if gate:
            return gate
        raw = request.args.get('days', '7')
        try:
            days = int(raw)
        except (TypeError, ValueError):
            days = 0
        if not str(raw).strip().isdigit() or days < 1 or days > 31:
            return err('المدة غير صالحة', 400)
        since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        rows = (Article.query.filter(Article.status == 'published', Article.published_at != None, Article.published_at >= since)   # noqa: E711
                .order_by(Article.published_at.desc()).limit(PUBLISHED_CAP).all())
        drafts = Article.query.filter(Article.status == 'draft').count()
        items = [{'id': a.id, 'title': a.title or '', 'published_at': a.published_at.replace(microsecond=0).isoformat() + 'Z'} for a in rows]
        return ns(jsonify({'ok': True, 'days': days, 'since': since.replace(microsecond=0).isoformat() + 'Z', 'items': items, 'drafts': drafts}))

    # ---------------------------------------------------------------- أصحاب الحملات + حدّ الحملات القديمة
    @app.route('/api/v2/marketing/owners', methods=['GET'], endpoint='v2mk_owners')
    @token_required
    @roles_required('admin')
    def v2mk_owners():
        gate = guard()
        if gate:
            return gate
        # صفوف يتيمة (حملة حُذفت) تُمسح، وصف أقدم من إنشاء الحملة (رقم أُعيد استخدامه) لا يُعرض ويُمسح
        db.session.execute(text('DELETE FROM v2_campaign_owner WHERE campaign_id NOT IN (SELECT id FROM campaigns)'))
        made = {cid: as_dt(at) for cid, at in db.session.query(Campaign.id, Campaign.created_at).all()}
        rows, stale = [], []
        for r in db.session.execute(text(
                'SELECT campaign_id, owner_kind, owner_id, owner_title, updated_at, updated_by FROM v2_campaign_owner ORDER BY campaign_id')).fetchall():
            born, saved = made.get(r[0]), as_dt(r[4])
            if born is not None and saved is not None and saved < born.replace(microsecond=0):
                stale.append(r[0])
            else:
                rows.append(r)
        for cid in stale:
            db.session.execute(text('DELETE FROM v2_campaign_owner WHERE campaign_id = :c'), {'c': cid})
        db.session.commit()
        legacy = 0 if meta(CHECKED_KEY) else legacy_max()
        return ns(jsonify({'ok': True, 'items': [owner_item(r) for r in rows], 'legacy_max_id': legacy}))

    @app.route('/api/v2/marketing/legacy-checked', methods=['POST'], endpoint='v2mk_legacy_checked')
    @token_required
    @roles_required('admin')
    def v2mk_legacy_checked():
        gate = guard()
        if gate:
            return gate
        if not meta(CHECKED_KEY):
            db.session.execute(text('INSERT INTO v2_marketing_meta (k, v) VALUES (:k, :v)'), {'k': CHECKED_KEY, 'v': '1'})
            db.session.commit()
        audit('marketing.legacy_currency_checked', target='campaigns')
        return ns(jsonify({'ok': True}))

    @app.route('/api/v2/marketing/campaigns/<int:cid>/owner', methods=['PUT'], endpoint='v2mk_owner_put')
    @token_required
    @roles_required('admin')
    def v2mk_owner_put(cid):
        gate = guard()
        if gate:
            return gate
        body = v2_body()
        kind = body.get('owner_kind')
        if kind not in OWNER_KINDS:
            return err('اختر صاحب الحملة', 400)
        owner_id, title = '', ''
        if kind != 'platform':
            owner_id = str(body.get('owner_id') or '')
            if not id_re.match(owner_id):
                return err('العمل غير صالح', 400)
            title = str(body.get('owner_title') or '').strip()[:TITLE_MAX]
        exists = db.session.execute(text('SELECT 1 FROM campaigns WHERE id = :i'), {'i': cid}).fetchone()
        if not exists:
            return err('الحملة غير موجودة', 404)
        who, at = actor(), now_iso()
        db.session.execute(text(
            'INSERT INTO v2_campaign_owner (campaign_id, owner_kind, owner_id, owner_title, updated_at, updated_by) '
            'VALUES (:c, :k, :i, :t, :a, :b) ON CONFLICT(campaign_id) DO UPDATE SET owner_kind = :k, owner_id = :i, owner_title = :t, '
            'updated_at = :a, updated_by = :b'), {'c': cid, 'k': kind, 'i': owner_id, 't': title, 'a': at, 'b': who})
        db.session.commit()
        audit('marketing.campaign_owner', target='campaign:%d' % cid, meta={'owner_kind': kind, 'owner_id': owner_id})
        return ns(jsonify({'ok': True, 'item': {'campaign_id': cid, 'owner_kind': kind, 'owner_id': owner_id, 'owner_title': title,
                                                'updated_at': at, 'updated_by': who}}))

    # ---------------------------------------------------------------- من أين جاء كل شخص (جسر المنصة — نداء واحد)
    @app.route('/api/v2/marketing/attribution', methods=['GET'], endpoint='v2mk_attribution')
    @token_required
    @roles_required('admin')
    def v2mk_attribution():
        gate = closed()
        if gate:
            return gate
        month = (request.args.get('month') or '').strip()
        if not month:
            month = datetime.datetime.utcnow().strftime('%Y-%m')
        if not month_re.match(month):
            return err('الشهر غير صالح', 400)
        return v2_get('/api/bridge/attribution/summary', {'month': month})
