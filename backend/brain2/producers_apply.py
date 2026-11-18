# -*- coding: utf-8 -*-
"""R24 م٣ — منتج «العقل» لمراجعة طلبات الانضمام (خبير / مدرّب): السيرة والفيديو ورقم القيد والهوية — `application_review`.

  * ما يراجعه: طلبات `trainer-applications` المعلّقة (`pending`) من الجسر. ⛔ ما بيقرأش مرفقًا ولا بيفتح فيديو: بيشوف **حقائق الطلب**
    بس (وصلت سيرة؟ وصل فيديو؟ رقم القيد مكتوب؟ وثيقة الهوية محفوظة؟) ويقول اللي فيها وإيه الناقص.
  * ما يكتبه: ملاحظة بنقط «راجعت…» (✓ تمّ · ! ناقص) + اقتراح + سبب. ⛔ ما بيقبلش ولا بيرفض طلب ولا بيبعت لحد: القرار للمؤسس.
  * نوعه `note` داخلية: على «لوحده» بتتكتب وتظهر على بطاقة الطلب، وعلى «يقترح» بتستنى «احتفظ بها».
  * طلب الذكاء بنص فقط (prompt-only) عبر المحرّك الموجود بسقوفه (`per_run_cap` · سقف الجولة واليوم)؛ لو الذكاء وقع ⇒ قالب من الحقائق نفسها.
  * facts من غير اسم ولا إيميل ولا هاتف؛ المعرّف في `meta` بس.
"""
import json
import re

from brain2.contract import Producer, SourceDown, Target

PRODUCER_ID = 'application_review'
LIST_LIMIT = 10
TEXT_MAX = 220
WHY_MAX = 160
RECS = ('approve', 'reject', 'open')
_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
_ROLE_AR = {'expert': 'خبير', 'trainer': 'مدرّب', 'both': 'خبير ومدرّب'}

_ROLE = (
    ' دورك: مراجعة طلب انضمام خبير أو مدرّب (أو طلب «إضافة صفة» من معتمد بصفة) يستنى قرار المؤسس. أنت ما شفتش السيرة ولا الفيديو ولا الوثيقة: عندك حقائق الطلب بس. '
    'افحص من الحقائق المعطاة فقط: السيرة (cv_files: عدد الملفات المرفقة) · الفيديو (video) · رقم القيد (licence_number، لو موجود) · '
    'الهوية (identity_doc، لو موجودة) · وللخبير: التخصصات (specialties) والنبذة (bio). كل شيء غير موجود في الحقائق لا تذكره ولا تفترضه. '
    'قواعد المؤسس: الفيديو إجباري للمدرّب واختياري للخبير، ورقم القيد اختياري للجميع؛ فأي حقيقة قيمتها فيها «اختياري» ليست نقصًا (ok=true). '
    'points: من ٢ إلى ٥ نقط قصيرة (حتى ١٠٠ حرف للنقطة)، كل نقطة {"ok":true|false,"text":"…"}: ok=true لما الحقيقة تؤكد وجود الشيء أو أنه اختياري، وok=false لما ينقص شيء مطلوب. '
    'لا تقل إنك قرأت السيرة أو شاهدت الفيديو أو تحققت من الوثيقة، ولا تحكم على جودتها: قل فقط وصل أو لم يصل. '
    'text: اقتراحك في جملة أو جملتين (حتى ٢٢٠ حرفًا). recommend: approve لو كل النقط ok وإلا open (فتح الطلب ومراجعته) أو reject لو الحقائق تنفي أساس الطلب. '
    'why: ليه؟ سبب اقتراحك في جملة (حتى ١٦٠ حرفًا). لا تذكر اسمًا ولا إيميلًا ولا رقمًا ليس في الحقائق. '
    'الشكل المطلوب: {"text":"…","recommend":"approve|reject|open","why":"…","points":[{"ok":true,"text":"…"}]}'
)
_OPTIONAL = 'اختياري'


def _fn(ctx, name):
    fn = ctx.ns.get(name)
    if not callable(fn):
        raise SourceDown(name)
    return fn


def _status_of(resp):
    try:
        return int(resp[1]) if isinstance(resp, tuple) else int(getattr(resp, 'status_code', 200))
    except Exception:   # noqa: BLE001
        return 0


def _ok(ctx, resp):
    fn = ctx.ns.get('_resp_ok')
    if callable(fn):
        try:
            return bool(fn(resp))
        except Exception:   # noqa: BLE001
            pass
    return 200 <= _status_of(resp) < 300


def _json_of(resp):
    try:
        r = resp[0] if isinstance(resp, tuple) else resp
        if isinstance(r, (dict, list)):
            return r
        return r.get_json(silent=True)
    except Exception:   # noqa: BLE001
        return None


def _applications(ctx):
    path = '/api/bridge/trainer-applications'
    try:
        resp = _fn(ctx, '_platform_proxy')('GET', path, params={'status': 'open'})
    except SourceDown:
        raise
    except Exception as exc:   # noqa: BLE001
        raise SourceDown('%s: %s' % (path, type(exc).__name__))
    if not _ok(ctx, resp):
        raise SourceDown('%s: http %s' % (path, _status_of(resp)))
    body = _json_of(resp)
    rows = body.get('applications') if isinstance(body, dict) else body
    if not isinstance(rows, list):
        raise SourceDown('%s: bad shape' % path)
    return [r for r in rows if isinstance(r, dict)]


def _identity_by_email(ctx):
    """{إيميل: حالة وثيقة الهوية} أو None لو المصدر ما وصلش (ساعتها نشيل بند الهوية من الحقائق بدل ما نقول «لا توجد»)."""
    try:
        resp = _fn(ctx, '_platform_proxy')('GET', '/api/bridge/identity-docs', params={'status': 'all'})
        if not _ok(ctx, resp):
            return None
        body = _json_of(resp)
        rows = body.get('items') if isinstance(body, dict) else body
        if not isinstance(rows, list):
            return None
    except Exception:   # noqa: BLE001
        return None
    out = {}
    for r in rows:
        if isinstance(r, dict) and r.get('email'):
            out[str(r['email']).strip().lower()] = str(r.get('status') or '').strip().lower()
    return out


def _text(v, n):
    return re.sub(r'\s+', ' ', str(v or '')).strip()[:n]


def _open_role_request(a):
    """R35: طلب «إضافة صفة» مفتوح على معتمد (`role_request` على نفس الطلب) أو None."""
    rr = a.get('role_request')
    if isinstance(rr, dict) and str(rr.get('status') or '') == 'pending' and str(rr.get('role') or '') in ('expert', 'trainer'):
        return rr
    return None


def _facts_of(a, idmap):
    # R35 (قرار المؤسس 2026-11-18): الحكم بقاعدة الصفة المطلوبة — الفيديو إجباري للمدرّب واختياري للخبير، ورقم القيد اختياري للجميع،
    # والخبير بيشتغل يوم القبول بتخصصاته ونبذته. «إضافة صفة» بتتراجع على حقول الصفة الجديدة (من `role_request`).
    rr = _open_role_request(a)
    src = dict(a, **{k: v for k, v in (rr or {}).items() if v not in (None, '', [])})
    role = str(rr.get('role')) if rr else str(a.get('join_as') or '').lower()
    expert_only = role == 'expert'
    attachments = a.get('attachments')
    has_video = bool(_text(src.get('intro_video_url'), 10))
    facts = {'role': _ROLE_AR.get(role, ''),
             'request': 'إضافة صفة لمعتمد بصفة أخرى' if rr else '',
             'headline': _text(a.get('headline'), 140),
             'specialty': _text(a.get('specialty') or a.get('specialization'), 60),
             'years': _text(a.get('years_experience'), 20),
             'cv_files': len(attachments) if isinstance(attachments, list) else 0,
             'video': 'وصل' if has_video else ('لم يُرسل، وهو ' + _OPTIONAL + ' للخبير' if expert_only else 'لم يصل بعد')}
    if role in ('expert', 'both'):
        specs = src.get('expert_specialties')
        facts['specialties'] = 'محددة' if isinstance(specs, list) and specs else 'غير محددة'
        facts['bio'] = 'مكتوبة' if _text(src.get('bio'), 40) else 'غير مكتوبة'
    if expert_only and not facts['cv_files']:
        facts.pop('cv_files')          # السيرة مش من حقول الخبير في الطلب الواحد ⇒ ما نعدّهاش ناقصة
    for key in ('bar_number', 'licence_number', 'license_number'):
        if key in src:
            facts['licence_number'] = 'مكتوب' if _text(src.get(key), 40) else 'غير مكتوب، وهو ' + _OPTIONAL
            break
    if idmap is not None:
        st = idmap.get(str(a.get('user_email') or a.get('email') or '').strip().lower())
        facts['identity_doc'] = ('موثّقة' if st in ('verified', 'approved') else 'وثيقة محفوظة بانتظار المراجعة') if st else 'لا توجد وثيقة'
    return {k: v for k, v in facts.items() if v not in ('', None)}


def gather(ctx):
    apps = _applications(ctx)
    idmap = _identity_by_email(ctx)
    out = []
    for a in apps:
        aid = str(a.get('id') or '').strip()
        st = a.get('status') or 'pending'
        if not _ID_RE.match(aid) or not (st == 'pending' or (st == 'approved' and _open_role_request(a))):
            continue
        name = _text(a.get('user_name') or a.get('full_name'), 60) or 'مقدّم الطلب'
        out.append(Target(ref='trainer:' + aid, label=(('مراجعة إضافة صفة: ' if _open_role_request(a) else 'مراجعة طلب انضمام: ') + name)[:120], facts=_facts_of(a, idmap),
                          meta={'application_id': aid}))
        if len(out) >= LIST_LIMIT:
            break
    return out


def prompt(target):
    user = 'راجع حقائق طلب الانضمام دي.\n\nالحقائق:\n%s' % json.dumps(target.facts, ensure_ascii=False, sort_keys=True)
    return _ROLE, user


def validate(raw, target):
    from brain2 import engine
    if not isinstance(raw, dict):
        return None
    text, why, rec = raw.get('text'), raw.get('why'), raw.get('recommend')
    if not isinstance(text, str) or not isinstance(why, str) or rec not in RECS:
        return None
    text, why = text.strip(), why.strip()
    if not text or not why or len(text) > TEXT_MAX or len(why) > WHY_MAX:
        return None
    pts = engine.clean_points(raw.get('points'))
    if not pts or len(pts) < 2:
        return None
    if rec == 'approve' and any(not p['ok'] for p in pts):
        rec = 'open'          # ⛔ ما نوصيش بالقبول ومعانا نقطة ناقصة
    return {'text': text, 'points': pts, 'why': why, 'recommend': rec, 'approve_label': 'احتفظ بها'}


def template(target):
    """لو الذكاء وقع: مراجعة جاهزة من الحقائق نفسها (من غير ذكاء ولا ادعاء)."""
    f = target.facts or {}
    pts = []
    if 'cv_files' in f:
        pts.append({'ok': bool(f.get('cv_files')), 'text': 'السيرة وصلت' if f.get('cv_files') else 'مفيش سيرة مرفقة'})
    v = str(f.get('video') or '')
    pts.append({'ok': v == 'وصل' or _OPTIONAL in v,
                'text': 'الفيديو وصل' if v == 'وصل' else ('مفيش فيديو، وهو اختياري للخبير' if _OPTIONAL in v else 'الفيديو لسه ما وصلش')})
    if 'specialties' in f:
        pts.append({'ok': f['specialties'] == 'محددة', 'text': 'التخصصات محددة' if f['specialties'] == 'محددة' else 'التخصصات مش محددة'})
    if 'bio' in f:
        pts.append({'ok': f['bio'] == 'مكتوبة', 'text': 'النبذة مكتوبة' if f['bio'] == 'مكتوبة' else 'النبذة مش مكتوبة، فمش هيظهر في دليل الخبراء'})
    if 'licence_number' in f:
        pts.append({'ok': True, 'text': 'رقم القيد مكتوب' if f['licence_number'] == 'مكتوب' else 'رقم القيد مش مكتوب، وهو اختياري'})
    if 'identity_doc' in f:
        v = f['identity_doc']
        pts.append({'ok': v == 'موثّقة', 'text': {'موثّقة': 'الهوية موثّقة', 'لا توجد وثيقة': 'مفيش وثيقة هوية محفوظة'}.get(v, 'وثيقة الهوية محفوظة وبتستنى مراجعتك')})
    pts = pts[:5]
    full = all(p['ok'] for p in pts)
    return {'text': 'الورق كامل، افتح الطلب واقرأه قبل القرار' if full else 'افتح الطلب وراجع الناقص قبل القرار',
            'points': pts, 'why': 'من حقائق الطلب بس، من غير قراءة السيرة ولا الفيديو',
            'recommend': 'open', 'approve_label': 'احتفظ بها'}


PRODUCERS = [
    Producer(
        id=PRODUCER_ID, section='people', kind='note',
        label='مراجعة طلبات الانضمام',
        sentence='عندما يصل طلب انضمام خبير أو مدرّب أو طلب إضافة صفة، يراجع العقل ما وصل (السيرة، الفيديو، التخصصات والنبذة للخبير، رقم القيد، الهوية) ويكتب اقتراحه على بطاقة الطلب. القرار لك.',
        lock_reason='', may_run_alone=True, default_mode='alone', per_run_cap=3,
        gather=gather, prompt=prompt, validate=validate, template=template, apply=None,
        tag='مراجعة طلب انضمام', approve_label='احتفظ بها',
    ),
]
