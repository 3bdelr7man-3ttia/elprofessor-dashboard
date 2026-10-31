# -*- coding: utf-8 -*-
"""قراءة تفاصيل «ملف للخبير» للعقل فقط (SPEC-B §B3) — على الخادم، لا تصل المتصفح أبدًا.

الداشبورد يحذف `facts` و`questions` من رد التفاصيل للمتصفح (`_EF_DETAIL_KEYS`)، والعقل يحتاجهما ليراجع الرأي.
هذه الدالة تنادي المنصة عبر `ns['_platform_proxy']` وتحتفظ بخمسة أشياء فقط: العنوان والوقائع والأسئلة والرأي المنتظر
ودورة المراجعة. اسم العميل وبريده وهاتفه تُمسح من كل نص. ⛔ لا نداء شبكة غير هذا النداء الواحد.
"""
import re

from brain2.contract import SourceDown

_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
_EMAIL_RE = re.compile(r'[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+')
_PHONE_RE = re.compile(r'\+?\d[\d\s\-().]{6,}\d')
_URL_RE = re.compile(r'https?://\S+')

FACT_ITEMS = 12
QUESTION_ITEMS = 8
ANSWER_ITEMS = 8
TODO_ITEMS = 8
_TEXT_KEYS = ('question', 'q', 'text', 'label', 'title', 'answer', 'a', 'value')


def _status_of(resp):
    try:
        if isinstance(resp, tuple):
            return int(resp[1])
        return int(getattr(resp, 'status_code', 200))
    except Exception:
        return 0


def _json_of(resp):
    try:
        r = resp[0] if isinstance(resp, tuple) else resp
        if isinstance(r, (dict, list)):
            return r
        return r.get_json(silent=True)
    except Exception:
        return None


def _ok(ns, resp):
    fn = ns.get('_resp_ok')
    if callable(fn):
        try:
            return bool(fn(resp))
        except Exception:
            pass
    return 200 <= _status_of(resp) < 300


def _names_of(f):
    """أسماء العميل والطرف الآخر كما جاءت من المنصة ⇒ [(الاسم, بديله)] تُمسح من النصوص. للعميل: الاسم الكامل والأول فقط
    (لا تقسيم إلى كلمات: «عبد» و«الله» كلمتان عاديتان). الأطول أولًا."""
    pairs = {}
    for k in ('client_name', 'client_first_name'):
        v = f.get(k)
        if isinstance(v, str) and v.strip():
            v = ' '.join(v.split())
            pairs[v] = 'العميل'
            first = v.split(' ')[0]
            if len(first) >= 2:
                pairs[first] = 'العميل'
    v = f.get('counterparty_name')
    if isinstance(v, str) and len(v.strip()) >= 2:
        pairs[' '.join(v.split())] = 'الطرف الآخر'
    return sorted(pairs.items(), key=lambda kv: len(kv[0]), reverse=True)


def _attach(prefix, word):
    """حرف جر/عطف + «العميل»: «ل» + «العميل» = «للعميل» (تسقط الألف)."""
    if prefix == 'ل' and word.startswith('ال'):
        return 'ل' + word[1:]
    return prefix + word


def _scrub(value, limit, names=()):
    s = value if isinstance(value, str) else ('' if value is None else str(value))
    s = _URL_RE.sub('', _EMAIL_RE.sub('', s))
    s = _PHONE_RE.sub('', s)
    for n, repl in names:
        # حرف عطف/جر لاصق بالاسم (وسمر · لسمر) يبقى كما هو.
        s = re.sub(r'(?<!\w)([وفبلك]?)' + re.escape(n) + r'(?!\w)', lambda m, r=repl: _attach(m.group(1), r), s)
    return re.sub(r'\s+', ' ', s).strip()[:limit]


def _item_text(x, names, limit):
    """عنصر نصي من وقائع/أسئلة المنصة: نص مباشر، أو أول مفتاحين نصيين من قاموس."""
    if isinstance(x, str):
        return _scrub(x, limit, names)
    if isinstance(x, dict):
        parts = []
        for k in _TEXT_KEYS:
            v = x.get(k)
            if isinstance(v, str) and v.strip():
                parts.append(_scrub(v, limit, names))
            if len(parts) == 2:
                break
        return ' — '.join(p for p in parts if p)[:limit]
    return ''


def _texts(items, names, n, limit):
    if not isinstance(items, list):
        return []
    out = []
    for x in items:
        t = _item_text(x, names, limit)
        if t:
            out.append(t)
        if len(out) >= n:
            break
    return out


def clean_pending(po, names=()):
    """الرأي المنتظر ⇒ {answers:[{question,text}], stance, case_note, todo, next_step}. غير القاموس ⇒ {}."""
    if not isinstance(po, dict):
        return {}
    answers = []
    for a in (po.get('answers') if isinstance(po.get('answers'), list) else [])[:ANSWER_ITEMS]:
        if not isinstance(a, dict):
            continue
        q, t = _scrub(a.get('question'), 200, names), _scrub(a.get('text'), 500, names)
        if t:
            answers.append({'question': q, 'text': t})
    stance = po.get('stance') if isinstance(po.get('stance'), str) and po.get('stance').strip() else po.get('verdict')
    note = po.get('case_note') if isinstance(po.get('case_note'), str) and po.get('case_note').strip() else po.get('next_step_note')
    step = po.get('next_step_label') if isinstance(po.get('next_step_label'), str) and po.get('next_step_label').strip() \
        else po.get('next_step')
    out = {'answers': answers, 'stance': _scrub(stance, 120, names), 'case_note': _scrub(note, 300, names),
           'todo': _texts(po.get('todo'), names, TODO_ITEMS, 200), 'next_step': _scrub(step, 200, names)}
    return out


def clean_detail(f):
    """رد المنصة الكامل ⇒ ما يحتفظ به العقل فقط."""
    names = _names_of(f)
    review = f.get('review') if isinstance(f.get('review'), dict) else {}
    rnd = review.get('round')
    return {'id': str(f.get('id') or ''), 'title': _scrub(f.get('title'), 120, names), 'status': str(f.get('status') or '')[:30],
            'facts': _texts(f.get('facts'), names, FACT_ITEMS, 300),
            'questions': _texts(f.get('questions'), names, QUESTION_ITEMS, 200),
            'pending_opinion': clean_pending(f.get('pending_opinion'), names),
            'round': rnd if isinstance(rnd, int) and not isinstance(rnd, bool) and 0 < rnd < 100 else None}


def _ef_detail_for_brain(ns, file_id):
    """تفاصيل ملف واحد للعقل. يرفع `SourceDown` لو تعذّرت القراءة (فشل/٤٠٤/شكل غريب) ⇒ لا نكتب شيئًا على ملف لم نقرأه."""
    fid = str(file_id or '')
    if not _ID_RE.match(fid):
        raise SourceDown('bad file id')
    proxy = ns.get('_platform_proxy')
    if not callable(proxy):
        raise SourceDown('platform proxy missing')
    path = '/api/bridge/expert-files/' + fid
    try:
        resp = proxy('GET', path)
    except Exception as exc:   # noqa: BLE001
        raise SourceDown('%s: %s' % (path, type(exc).__name__))
    if not _ok(ns, resp):
        raise SourceDown('%s: http %s' % (path, _status_of(resp)))
    body = _json_of(resp)
    if not isinstance(body, dict):
        raise SourceDown('%s: bad shape' % path)
    return clean_detail(body)
