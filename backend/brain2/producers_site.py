# -*- coding: utf-8 -*-
"""منتجو «الموقع» (SPEC docs/v2/brain2/SPEC-B.md §B6): `site_review` (العقل يقترح) و`site_edit_manual` (المؤسس يكتب بنفسه).

القاعدة الحاكمة: ⛔ لا شيء يصل الموقع إلا بعد اعتماد المؤسس نفسه. المنتجان مقفولان على «يسألني»، والتنفيذ (`apply`) يمرّ على
`site_edit.apply_edits` وحدها: نسخة احتياطية ⇒ بصمة ⇒ استبدال عُقد النص ⇒ رفع مؤقت وإعادة تسمية ⇒ تحقّق ⇒ إرجاع عند الفشل.

قواعد الملف:
  * كل قراءة من الموقع بنداء `site_edit.fetch_live` القابل للحقن (لا شبكة في الاختبارات).
  * `facts` ≤ ٤ك: القرارات المعتمدة + كتل الصفحة القصيرة بأسماء مختصرة (b1…)؛ المسارات الحقيقية والنصوص الكاملة في `meta` فقط.
  * كل `old` يجب أن يساوي نص الكتلة الحية حرفيًا وإلا سقط ذلك التعديل (لا نصلحه بالتخمين).
  * لا استيراد للمحرّك في الأعلى (المحرّك يستورد السجل الذي يستورد هذا الملف): كل ما يخصه يُستورد داخل الدوال.
"""
import datetime
import json
import re
import uuid

import site_edit
from brain2.contract import ApplyResult, Producer, SourceDown, Target

# ------------------------------------------------------------------ قرارات المؤسس المتعلقة بالنص العام (بذرة تُكتب مرة واحدة)
# كل قاعدة بمصدرها (ملف:سطر). المصادر: مواصفات اللوحة `docs/v2/final/SPEC-*.md` (للقراءة فقط) وملاحظات جولة المنصة
# `_reference/elprofessor-platform-walkthrough/NOTES.md` وذاكرة المشروع `~/.claude/projects/-Users-abdelrhman/memory/*.md`.
# ⛔ نصيب المنصة ٣٥٪ (elprofessor_platform_share_floor_35.md) قرار داخلي: لا يدخل هذه القائمة ولا يظهر في أي نص عام.
SEED_DECISIONS = (
    # docs/v2/final/SPEC-market.md:164 («No line starts with «الذكاء الاصطناعي»») وSPEC-courses.md:18 و SPEC-books.md:15
    'لا يبدأ أي عنوان بعبارة «الذكاء الاصطناعي».',
    # docs/v2/final/SPEC-books.md:15 («never «يقوّم»») وSPEC-market.md:164
    'لا تُستعمل كلمة «يقوّم» في أي نص.',
    # ~/.claude/projects/-Users-abdelrhman/memory/elprofessor_homepage_vision_2026-10-21.md:99 («تواصل» اتشال من القائمة العليا، فاضل في الفوتر بس)
    'كلمة «تواصل» تظهر في أسفل الصفحة فقط، لا في القائمة العليا.',
    # ~/.claude/projects/-Users-abdelrhman/memory/feedback_certificate_no_disclaimer.md:13 (ممنوع أي سطر نفي في الشهادة)
    'الشهادة تصدر باسم منصة البروفيسور بلا أي سطر نفي أو إخلاء.',
    # ~/.claude/projects/-Users-abdelrhman/memory/elprofessor_student_discount_removed.md:11 (خصم الطالب يُشال تمامًا)
    'لا ذكر لخصم الطالب في أي مكان.',
    # ~/.claude/projects/-Users-abdelrhman/memory/elprofessor_no_tech_in_visible_copy.md:10 («إحنا مش جوا مصر بس»)
    'الجمهور دولي: لا أمثلة ولا صياغة تخص مصر وحدها.',
    # ~/.claude/projects/-Users-abdelrhman/memory/elprofessor_no_tech_in_visible_copy.md:8 (الإفصاح التقني في صفحة الخصوصية وحدها)
    'لا شرح تقني في أي نص مرئي؛ الإفصاح التقني مكانه صفحة الخصوصية فقط.',
    # _reference/elprofessor-platform-walkthrough/NOTES.md:123 («الكلام بالعربي الأبيض مش العامية») وdocs/v2/final/SPEC-market.md:164 (محايدة)
    'عربية فصحى بسيطة بلا عامية، وبصيغة محايدة لا تخاطب مذكرًا ولا مؤنثًا.',
    # _reference/elprofessor-platform-walkthrough/NOTES.md:108 (نشيل السعر من كارت «افتح ملف للخبير»)
    'لا سعر على بطاقة «افتح ملفًا للخبير»؛ السعر يظهر في آخر الملف فقط.',
    # _reference/elprofessor-platform-walkthrough/NOTES.md:143 («كريدت كارت، أو ديبت مفعّل للدفع الدولي»)
    'الدفع بالبطاقة يُكتب هكذا: كريدت كارت، أو ديبت مفعّل للدفع الدولي.',
    # _reference/elprofessor-platform-walkthrough/NOTES.md:138 (الدفع المحلي فودافون كاش وإنستاباي لمصر بس)
    'الدفع المحلي (فودافون كاش وإنستاباي) يُذكر لمصر وحدها.',
    # _reference/elprofessor-platform-walkthrough/NOTES.md:26 (رأي الذكاء تحت عنوان «الإجابة المبدئية قبل المراجعة»)
    'ما يكتبه الذكاء داخل الملف يُسمّى «الإجابة المبدئية قبل المراجعة».',
    # ~/.claude/projects/-Users-abdelrhman/memory/feedback_marketing_first_not_law.md:11 (التسويق أولًا، والقانون حدود مختصرة)
    'دورات القانونيين تبدأ بالتسويق، والقانون يدخل حدودًا مختصرة لا ملعبًا.',
    # docs/v2/final/SPEC-courses.md:18 (Zoom ⇒ «رابط اللقاء»، Titch ⇒ «منهج مكتوب»)
    'تُكتب «رابط اللقاء» بدل اسم أداة الاجتماع، و«منهج مكتوب» بدل اسم أداة المنهج.',
    # docs/v2/final/SPEC-courses.md:18 (العملة تُكتب باسمها، لا «ج»)
    'العملة تُكتب باسمها الكامل لا برمز مختصر.',
)

DECISION_MAX = 300
DECISIONS_MAX_ACTIVE = 40
FACTS_BUDGET = 3900          # بايت (الحد في المحرّك ٤٠٩٦)
DECISIONS_BUDGET = 2200      # البذرة كاملة ≈ ١٫٦ك؛ والباقي لقواعد المؤسس
BLOCK_FACT_MAX = 140         # كتلة أطول من هذا لا يراها الذكاء (لا يستطيع نسخها حرفيًا)
EDITS_MAX = 5
PAGES_PER_RUN = 2
TEXT_LIMIT = 880             # حد المحرّك للمسودة ٩٠٠
WHY_MAX = 160
SITE_REVIEW_ID = 'site_review'
MANUAL_ID = 'site_edit_manual'
APPROVE_LABEL = 'انشر التعديل على الموقع'
LOCK_REASON = 'يسألك دائمًا لأن التعديل يظهر على الموقع للناس.'
NO_EDITS_TEXT = 'لا تعديل مقترح على هذه الصفحة'

# ------------------------------------------------------------------ فحوص النص (نسخة محلية من فحوص المحرّك لتفادي الاستيراد الدائري)
_BANNED_RE = re.compile('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ[ً-ْ]*م')
_AI_START_RE = re.compile(r'^[\s«"\'(\[\-*]*(?:الذكاء\s+الاصطناعي|الذكاء|AI\b)')
_DIGITS_RE = re.compile(r'\d+')
_LATIN_RE = re.compile(r'[A-Za-z]+')
_DIGIT_MAP = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
_HEADINGS = ('title', 'h1', 'h2', 'h3')
_PRIORITY = {'title': 0, 'h1': 1, 'h2': 2, 'h3': 3, 'button': 4, 'a': 5, 'p': 6, 'li': 7}


def _norm(s):
    return s.translate(_DIGIT_MAP) if isinstance(s, str) else s


def _canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False)


def _size(o):
    return len(_canon(o).encode('utf-8'))


def _system_ar():
    try:
        from brain2.engine import SYSTEM_AR
        return SYSTEM_AR
    except Exception:   # noqa: BLE001
        return ''


def check_public_text(new, tag, allowed_blob=None):
    """قواعد النص العام الآلية على نص جديد. يرجع رمز العلة أو None.
    `allowed_blob`: نص الحقائق؛ إن مُرّر فكل رقم وكل كلمة لاتينية في الجديد يجب أن تظهر فيه (لا اختراع من الذكاء)."""
    if _BANNED_RE.search(new):
        return 'banned'
    if tag in _HEADINGS and _AI_START_RE.match(new):
        return 'ai_lead'
    if allowed_blob is not None:
        blob = _norm(allowed_blob)
        low = blob.lower()
        for run in _DIGITS_RE.findall(_norm(new)):
            if run not in blob:
                return 'number'
        for w in _LATIN_RE.findall(new):
            if w.lower() not in low:
                return 'latin'
    return None


# ------------------------------------------------------------------ جدول القرارات
_MODEL = {}


def decision_model(db):
    """`v2_site_decisions` (id · text ≤300 · created_by · created_at · active). الحذف «ناعم»: active=False، فلا تُعاد البذرة."""
    if 'cls' in _MODEL:
        return _MODEL['cls']

    class V2SiteDecision(db.Model):
        __tablename__ = 'v2_site_decisions'
        __table_args__ = {'extend_existing': True}
        id = db.Column(db.String(32), primary_key=True)
        text = db.Column(db.String(DECISION_MAX), nullable=False)
        created_by = db.Column(db.String(255))
        created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
        active = db.Column(db.Boolean, default=True, nullable=False)

    _MODEL['cls'] = V2SiteDecision
    return V2SiteDecision


def ensure_seed(db):
    """تُكتب البذرة مرة واحدة فقط: الجدول فارغ تمامًا (حتى المحذوف ناعمًا يُحسب)."""
    D = decision_model(db)
    if D.query.count() > 0:
        return False
    now = datetime.datetime.utcnow()
    for i, t in enumerate(SEED_DECISIONS):
        db.session.add(D(id=uuid.uuid4().hex, text=t, created_by='seed', created_at=now + datetime.timedelta(microseconds=i),
                         active=True))
    db.session.commit()
    return True


def list_decisions(db):
    ensure_seed(db)
    D = decision_model(db)
    return D.query.filter_by(active=True).order_by(D.created_at.asc(), D.id.asc()).all()


def add_decision(db, text, actor):
    """يرجع (row, error). النص نظيف من ٣ إلى ٣٠٠ حرف، لا يتكرر، والقواعد الفعّالة ≤ ٤٠."""
    t = site_edit.collapse(site_edit._CTRL_RE.sub('', text if isinstance(text, str) else ''))
    if len(t) < 3 or len(t) > DECISION_MAX:
        return None, 'اكتب قاعدة من ٣ إلى ٣٠٠ حرف'
    D = decision_model(db)
    ensure_seed(db)
    act = D.query.filter_by(active=True).all()
    if any(r.text == t for r in act):
        return None, 'هذه القاعدة موجودة بالفعل'
    if len(act) >= DECISIONS_MAX_ACTIVE:
        return None, 'بلغت الحد الأقصى من القواعد. احذف قاعدة قديمة أولًا'
    row = D(id=uuid.uuid4().hex, text=t, created_by=str(actor or '')[:255], created_at=datetime.datetime.utcnow(), active=True)
    db.session.add(row)
    db.session.commit()
    return row, None


def remove_decision(db, decision_id):
    D = decision_model(db)
    changed = D.query.filter(D.id == decision_id, D.active.is_(True)).update({'active': False}, synchronize_session=False)
    db.session.commit()
    return changed == 1


def decision_out(r):
    ca = r.created_at.replace(tzinfo=None).isoformat() + 'Z' if r.created_at else None
    return {'id': r.id, 'text': r.text, 'created_by': r.created_by or '', 'created_at': ca,
            'seed': (r.created_by or '') == 'seed'}


# ------------------------------------------------------------------ نص البطاقة
def _cut(s, n):
    s = site_edit.collapse(s)
    if len(s) <= n:
        return s
    c = s[:n]
    sp = c.rfind(' ')
    if sp > n // 2:
        c = c[:sp]
    return c.rstrip(' ،,.') + '…'


def compose_text(label, edits):
    """ما يراه المؤسس على بطاقة القرار: كل تعديل «من … إلى …». يُقصّ عند حدود الكلمات لئلا ينكسر رقم أو كلمة لاتينية."""
    head = 'تعديلات مقترحة على «%s»:' % label
    lines = [head]
    for e in edits:
        lines.append('• من «%s» إلى «%s»' % (_cut(e['old'], 70), _cut(e['new'], 70)))
        if len('\n'.join(lines)) > TEXT_LIMIT:
            lines.pop()
            lines.append('وتعديلات أخرى في التفاصيل')
            break
    return '\n'.join(lines)[:TEXT_LIMIT]


# ------------------------------------------------------------------ جمع الصفحات للمراجعة
def pages_for_today(now=None):
    """صفحتان في الجولة بالتناوب اليومي (بلا حالة محفوظة): ٦ أيام لتمرّ كل الصفحات الاثنتي عشرة."""
    n = len(site_edit.ALLOWED)
    d = (now or datetime.datetime.utcnow()).toordinal()
    i = (d * PAGES_PER_RUN) % n
    return [site_edit.ALLOWED[(i + k) % n] for k in range(PAGES_PER_RUN)]


def _decision_facts(texts):
    out = []
    for t in texts:
        out.append(site_edit.collapse(t)[:160])
        if _size(out) > DECISIONS_BUDGET:
            out.pop()
            break
    return out


def build_target(page, live, decision_texts):
    """هدف مراجعة صفحة. يرجع None لو لا كتلة صالحة يراها الذكاء."""
    label = site_edit.LABELS[page]
    cands = [(i, b) for i, b in enumerate(live['blocks'])
             if b['editable'] and 3 <= len(b['text']) <= BLOCK_FACT_MAX]
    facts = {'page': label, 'decisions': _decision_facts(decision_texts), 'blocks': []}
    chosen = []
    for i, b in sorted(cands, key=lambda x: (_PRIORITY.get(x[1]['tag'], 9), x[0])):
        trial = {'path': 'b99', 'text': b['text']}
        facts['blocks'].append(trial)
        if _size(facts) > FACTS_BUDGET:
            facts['blocks'].pop()
            continue
        chosen.append((i, b))
    chosen.sort(key=lambda x: x[0])
    facts['blocks'] = []
    meta = {'page': page, 'sha': live['sha'], 'paths': {}, 'texts': {}, 'tags': {}}
    for n, (_, b) in enumerate(chosen, 1):
        alias = 'b%d' % n
        facts['blocks'].append({'path': alias, 'text': b['text']})
        meta['paths'][alias] = b['path']
        meta['texts'][alias] = b['text']
        meta['tags'][alias] = b['tag']
    if not chosen:
        return None
    return Target(ref='site:' + page, label=label, facts=facts, meta=meta)


def _gather_site_review(ctx):
    db = ctx.ns['db']
    rows = list_decisions(db)
    # قواعد المؤسس المضافة أولًا (الأحدث فالأقدم) كي لا يقطعها سقف الحقائق؛ ثم البذرة بترتيبها.
    mine = sorted([r for r in rows if r.created_by != 'seed'], key=lambda r: r.created_at, reverse=True)
    texts = [r.text for r in mine] + [r.text for r in rows if r.created_by == 'seed']
    targets, failed = [], 0
    for page in pages_for_today():
        try:
            live = site_edit.fetch_live(page)
        except site_edit.SiteError:
            failed += 1
            continue
        t = build_target(page, live, texts)
        if t is not None:
            targets.append(t)
    if failed == PAGES_PER_RUN:
        raise SourceDown('site')
    return targets


_ROLE = (
    ' دورك: مراجعة نصوص صفحة من موقع البروفيسور على ضوء القرارات المعتمدة في decisions. اقترح في edits حتى خمسة تعديلات '
    'فقط على كتل تخالف قرارًا أو تحتاج صياغة أوضح، ولا تقترح شيئًا إن لم يلزم. لكل تعديل: path كما هو في blocks، '
    'وold نسخة حرفية من نص الكتلة بلا أي تغيير، وnew النص الجديد بالفصحى البسيطة دون أي رقم أو اسم لاتيني من عندك، '
    'وwhy سبب قصير يذكر القرار. في text جملة أو جملتان تلخصان ما تقترحه. '
    'الشكل المطلوب: {"edits":[{"path":"b1","old":"…","new":"…","why":"…"}],"text":"…"}'
)


def _prompt_site_review(target):
    return (_system_ar() + _ROLE, 'راجع نصوص هذه الصفحة.\n\nالحقائق:\n' + json.dumps(target.facts, ensure_ascii=False, sort_keys=True))


def _validate_site_review(raw, target):
    """يُسقط كل تعديل يخالف الحي (`old` ≠ نص الكتلة) أو القواعد. لا تعديل صالح ⇒ جسم «لا تعديل» يُخزَّن بلا بطاقة."""
    if not isinstance(raw, dict) or not isinstance(raw.get('edits', []), list):
        return None
    meta = target.meta if isinstance(target.meta, dict) else {}
    paths, texts, tags = meta.get('paths') or {}, meta.get('texts') or {}, meta.get('tags') or {}
    blob = _canon(target.facts)
    edits, seen = [], set()
    for e in raw.get('edits', []):
        if len(edits) >= EDITS_MAX:
            break
        if not isinstance(e, dict):
            continue
        alias, old, new, why = e.get('path'), e.get('old'), e.get('new'), e.get('why', '')
        if not (isinstance(alias, str) and alias in paths and isinstance(old, str) and old == texts.get(alias)):
            continue                                   # old ≠ نص الكتلة الحي ⇒ يسقط
        if alias in seen or not isinstance(new, str):
            continue
        try:
            new_c = site_edit.clean_new_text(new, tags.get(alias, ''))
        except site_edit.SiteError:
            continue
        if new_c == old or check_public_text(new_c, tags.get(alias, ''), blob) is not None:
            continue
        why_c = site_edit.collapse(site_edit._CTRL_RE.sub('', why)) if isinstance(why, str) else ''
        if len(why_c) > WHY_MAX or _BANNED_RE.search(why_c) or check_public_text(why_c, '', blob) is not None:
            why_c = ''
        seen.add(alias)
        edits.append({'path': paths[alias], 'old': old, 'new': new_c, 'why': why_c})
    if not edits:
        # لا بطاقة: المحرّك يخزّن الصف `discarded` حين يرى course_id=None (نفس عقد market_match).
        return {'text': NO_EDITS_TEXT, 'edits': [], 'course_id': None}
    label = site_edit.LABELS.get(meta.get('page'), '')
    body = {'text': compose_text(label, edits), 'edits': edits, 'page': meta.get('page'), 'page_label': label}
    summary = raw.get('text')
    if isinstance(summary, str):
        s = site_edit.collapse(summary)
        if s and len(s) <= 300 and not _BANNED_RE.search(s) and check_public_text(s, '', blob) is None and not _AI_START_RE.match(s):
            body['summary'] = s
    return body


# ------------------------------------------------------------------ التنفيذ (بعد اعتماد المؤسس فقط)
def _apply_site(ctx, body, target):
    meta = target.meta if isinstance(target.meta, dict) else {}
    page = meta.get('page') or body.get('page')
    edits = body.get('edits')
    if not site_edit.page_allowed(page) or not isinstance(edits, list) or not edits:
        return ApplyResult(ok=False, error='تعذّر تحديد الصفحة أو التعديلات')
    res = site_edit.apply_edits(ctx.ns['db'], page, meta.get('sha'), edits, ctx.actor)
    try:
        ctx.ns['_audit']('v2_site.apply', target=page,
                         meta={'ok': bool(res.get('ok')), 'code': res.get('code', ''), 'edits': len(edits),
                               'backup_id': res.get('backup_id')}, actor=ctx.actor)
    except Exception:   # noqa: BLE001
        pass
    if res.get('ok'):
        return ApplyResult(ok=True, info={'page': page, 'edits': len(edits), 'backup_id': res.get('backup_id')})
    return ApplyResult(ok=False, error=res.get('error') or 'تعذّر تنفيذ التعديل الآن', no_reply=bool(res.get('unknown')))


# ------------------------------------------------------------------ تعديل المؤسس اليدوي ⇒ اقتراح بانتظار اعتماده
MANUAL_MAX_EDITS = site_edit.MAX_EDITS


def validate_manual_edit(live, path, old, new):
    """يتحقق من تعديل المؤسس على الصفحة الحية. يرجع (block, new_clean) أو يرفع SiteError."""
    block = next((b for b in live['blocks'] if b['path'] == path), None)
    if block is None:
        raise site_edit.SiteError('no_match', site_edit.ERR_NO_MATCH, 422)
    if not block['editable']:
        raise site_edit.SiteError('multi_match', site_edit.ERR_MULTI_MATCH, 422)
    if not isinstance(old, str) or site_edit.collapse(old) != block['text']:
        raise site_edit.SiteError('no_match', site_edit.ERR_NO_MATCH, 422)
    new_c = site_edit.clean_new_text(new, block['tag'])
    if new_c == block['text']:
        raise site_edit.SiteError('bad_edit', 'النص الجديد مطابق للقديم')
    why = check_public_text(new_c, block['tag'])
    if why == 'banned':
        raise site_edit.SiteError('bad_edit', 'في النص عبارة غير مقبولة. عدّلها ثم أعد المحاولة')
    if why == 'ai_lead':
        raise site_edit.SiteError('bad_edit', 'لا يبدأ العنوان بعبارة «الذكاء». عدّل الصياغة')
    return block, new_c


def propose_manual(ns, live, path, old, new, actor):
    """يضيف تعديل المؤسس إلى اقتراح مفتوح لنفس الصفحة وبنفس البصمة، أو يفتح اقتراحًا جديدًا (مصدره `founder`).
    الاقتراح يُعتمد من مسار الاعتماد العادي لـ«العقل». يرجع الصف."""
    from brain2 import engine
    page = live['page']
    block, new_c = validate_manual_edit(live, path, old, new)
    db = ns['db']
    Item = engine._models(db)[0]
    ref = 'site:' + page
    label = site_edit.LABELS[page]
    entry = {'path': block['path'], 'old': block['text'], 'new': new_c, 'why': 'تعديل من المؤسس'}
    rows = Item.query.filter_by(producer=MANUAL_ID, target_ref=ref, status='proposed').all()
    row = None
    for r in rows:
        m = engine._loads(r.meta_json, {})
        if m.get('sha') == live['sha'] and row is None:
            row = r
        else:
            r.status = 'expired'                       # بصمة قديمة: لا يصلح للتنفيذ
    now = engine.utcnow()
    if row is not None:
        body = engine._loads(row.body_json, {})
        edits = [e for e in (body.get('edits') or []) if isinstance(e, dict) and e.get('path') != entry['path']]
        if len(edits) >= MANUAL_MAX_EDITS:
            raise site_edit.SiteError('too_many', 'بلغت الحد الأقصى من التعديلات في اقتراح واحد. اعتمده أو ارفضه أولًا')
        edits.append(entry)
    else:
        edits = [entry]
    facts = {'page': label, 'edits': [{'path': e['path'], 'old': e['old'], 'new': e['new']} for e in edits],
             'at': now.isoformat()}
    body = {'text': compose_text(label, edits), 'edits': edits, 'page': page, 'page_label': label,
            'approve_label': APPROVE_LABEL}
    meta = {'page': page, 'sha': live['sha'], 'manual': True}
    h = engine.input_hash(_manual_producer(), facts)
    if row is None:
        row = Item(id=uuid.uuid4().hex, producer=MANUAL_ID, section='content', kind='draft', target_ref=ref,
                   target_label=label, input_hash=h, facts_json=_canon(facts), meta_json=json.dumps(meta, ensure_ascii=False),
                   body_json=json.dumps(body, ensure_ascii=False), status='proposed', source='founder', mode='ask',
                   run_id=None, created_at=now)
        db.session.add(row)
    else:
        row.input_hash, row.facts_json = h, _canon(facts)
        row.body_json = json.dumps(body, ensure_ascii=False)
        row.meta_json = json.dumps(meta, ensure_ascii=False)
    db.session.commit()
    return row


def _manual_producer():
    return next(p for p in PRODUCERS if p.id == MANUAL_ID)


def _gather_manual(ctx):
    return []                                          # لا يعمل في الجولات: يُنشأ فقط من شاشة المؤسس


def _prompt_manual(target):
    return ('', '')


def _validate_manual(raw, target):
    return None


# ------------------------------------------------------------------ السجل
PRODUCERS = [
    Producer(
        id=SITE_REVIEW_ID, section='content', kind='draft',
        label='مراجعة نصوص الموقع',
        sentence='عندما تخالف صفحة من الموقع قرارًا معتمدًا، يقترح العقل تعديل نصها لتراجعه.',
        lock_reason=LOCK_REASON,
        may_run_alone=False, default_mode='ask', per_run_cap=PAGES_PER_RUN,
        gather=_gather_site_review, prompt=_prompt_site_review, validate=_validate_site_review,
        apply=_apply_site, tag='تعديل الموقع', approve_label=APPROVE_LABEL,
    ),
    Producer(
        id=MANUAL_ID, section='content', kind='draft',
        label='تعديلات الموقع بيد المؤسس',
        sentence='تعديل تكتبه بنفسك على نص في الموقع، ويظهر هنا لتعتمده.',
        lock_reason=LOCK_REASON,
        may_run_alone=False, default_mode='ask', per_run_cap=1,
        gather=_gather_manual, prompt=_prompt_manual, validate=_validate_manual,
        apply=_apply_site, tag='تعديل الموقع', approve_label=APPROVE_LABEL, listed=False,
    ),
]
