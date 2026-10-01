# -*- coding: utf-8 -*-
"""Content-refresh rules — the ONE implementation of «what a refresh may change».

⛔ Two byte-identical copies, on purpose (memory: two_implementations_of_one_trap):
     platform   elprofessor/backend/services/refresh_rules.py   (generator pre-checks before posting)
     dashboard  elprofessor-dashboard/backend/refresh_rules.py  (the refresh endpoint — the AUTHORITY)
   Both repos run the same JSON fixtures (refresh_fixtures.json) and a parity test that fails if the
   two files ever differ. Edit one ⇒ copy it to the other in the same change.

Spec: EXPERT_REVIEW_2026-10-02 §3.1d «validate(out,cur)» + §3.2-5 (ElProfessor port).
A refresh may: expand thin sections, add 1–2 H2s, add FAQ, change title/description for CTR,
fix internal links. It may NEVER: change the URL/slug, shrink the page, drop an existing H2,
add a number/fact that was not already on the page (YMYL), or change the title without a CTR reason.

Blocks are the dashboard's body format: a list of strings, '## ' = heading, '• ' = bullet,
everything else = paragraph. Link sections («اقرأ أيضًا» / cluster nav) are rendered from data and
are NOT content — they never count toward words, numbers, headings, the hash or «material».

Pure functions, stdlib only, no I/O.
"""
from __future__ import annotations

import datetime as _dt
import difflib
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

# Rendered-from-data link sections. A heading here + the '• [..](..)' bullets that follow it.
RELATED_HEADING = '## اقرأ أيضًا'                      # اقرأ أيضًا
SAME_GUIDE_HEADING = '## في نفس الدليل'          # في نفس الدليل
HUB_NAV_HEADING = ('## تفاصيل أكثر في '
                   'هذا الدليل')                         # تفاصيل أكثر في هذا الدليل
LINK_HEADINGS = (RELATED_HEADING, SAME_GUIDE_HEADING, HUB_NAV_HEADING)

TITLE_REASONS = frozenset({'ctr', 'striking'})
TITLE_MAX = 90
WORDS_MAX_GROWTH = 1.6
MATERIAL_TEXT_DIFF = 0.10
KW_COVER_MIN = 0.75

# \uXXXX escapes, never literal Arabic inside a regex class (memory: arabic_bidi_code_trap)
_TASHKEEL = re.compile('[ً-ٰٟـ]')
_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩'
                        '۰۱۲۳۴۵۶۷۸۹',
                        '01234567890123456789')
_NORM = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',
                       'ى': 'ي', 'ة': 'ه'})
_MD_LINK = re.compile(r'\[([^\]]*)\]\(([^)]*)\)')
_SAME_SITE = re.compile(r'^(?:https://elprofessor\.net)?/blog/[A-Za-z0-9%\-_.~]+$')
_NUM = re.compile(r'\d+(?:[.,]\d+)?')
_REMOVED_OUTDATED = re.compile(r'^\s*removed\s*:\s*outdated\b', re.IGNORECASE)


def norm(text: Any) -> str:
    s = _TASHKEEL.sub('', str(text or '')).translate(_NORM).translate(_DIGITS).lower()
    s = re.sub(r'[^\w\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def is_link_bullet(block: Any) -> bool:
    return str(block).lstrip().startswith('• [')


def content_blocks(blocks: Sequence[Any]) -> List[str]:
    """Body minus every rendered link section (heading + its link bullets)."""
    out: List[str] = []
    skipping = False
    for b in blocks or []:
        s = str(b)
        if s.strip() in LINK_HEADINGS:
            skipping = True
            continue
        if skipping and is_link_bullet(s):
            continue
        skipping = False
        out.append(s)
    return out


def _plain(block: str) -> str:
    s = _MD_LINK.sub(lambda m: m.group(1), str(block))
    if s.startswith('## '):
        s = s[3:]
    elif s.startswith('• '):
        s = s[2:]
    return s


def h2s(blocks: Sequence[Any]) -> List[str]:
    return [norm(b[3:]) for b in content_blocks(blocks) if str(b).startswith('## ')]


def words(blocks: Sequence[Any]) -> int:
    return sum(len(_plain(b).split()) for b in content_blocks(blocks))


def first_paragraph(blocks: Sequence[Any]) -> str:
    for b in content_blocks(blocks):
        if not str(b).startswith('## ') and not str(b).startswith('• '):
            return _plain(b)
    return ''


def _faq_text(faq: Iterable[Any]) -> List[str]:
    out = []
    for f in faq or []:
        if isinstance(f, dict):
            out += [str(f.get('q') or ''), str(f.get('a') or '')]
    return out


def all_text(page: Dict[str, Any]) -> str:
    parts = [str(page.get('title') or ''), str(page.get('meta_description') or '')]
    parts += [_plain(b) for b in content_blocks(page.get('body') or [])]
    parts += _faq_text(page.get('faq') or [])
    return '\n'.join(parts)


def numbers(text: str, today: Optional[_dt.date] = None) -> set:
    """Digit tokens a refresh could have invented. The current year and small ordinals (1–10)
    are not facts; everything else is (fees, article numbers, deadlines, percentages, years)."""
    today = today or _dt.date.today()
    out = set()
    for tok in _NUM.findall(str(text or '').translate(_DIGITS)):
        t = tok.replace(',', '.')
        try:
            v = float(t)
        except ValueError:
            continue
        if v == int(v):
            v = int(v)
            if 1 <= v <= 10 or v == today.year:
                continue
        out.add(str(v))
    return out


def kw_cover(kw: str, text: str) -> float:
    """Fraction of the keyword's tokens present in `text` (a token counts when it appears inside
    a text token, so «العقود» covers «عقود» and «والعقد» covers «العقد»)."""
    k = [t for t in norm(kw).split() if len(t) >= 2]
    if not k:
        return 1.0
    toks = norm(text).split()
    hit = sum(1 for t in k if any(t in w for w in toks))
    return hit / len(k)


def text_diff(a_blocks: Sequence[Any], b_blocks: Sequence[Any]) -> float:
    a = norm(' '.join(_plain(x) for x in content_blocks(a_blocks))).split()
    b = norm(' '.join(_plain(x) for x in content_blocks(b_blocks))).split()
    if not a and not b:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def is_material(cur: Dict[str, Any], new: Dict[str, Any]) -> bool:
    """Spec: material = textDiff ≥ 0.10 || faq added || h2 added. Link-only and title/meta-only
    changes are NOT material ⇒ dateModified does not move for them."""
    if len([f for f in (new.get('faq') or []) if isinstance(f, dict)]) > \
            len([f for f in (cur.get('faq') or []) if isinstance(f, dict)]):
        return True
    if len(h2s(new.get('body') or [])) > len(h2s(cur.get('body') or [])):
        return True
    return text_diff(cur.get('body') or [], new.get('body') or []) >= MATERIAL_TEXT_DIFF


def _stale_year(text: str, today: _dt.date) -> bool:
    for y in re.findall(r'\b(19\d\d|20\d\d)\b', str(text).translate(_DIGITS)):
        if int(y) < today.year:
            return True
    return False


def validate(cur: Dict[str, Any], new: Dict[str, Any], reasons: Iterable[str] = (), *,
             ymyl: bool = True, primary_kw: Optional[str] = None,
             change_log: Iterable[str] = (), today: Optional[_dt.date] = None) -> Dict[str, Any]:
    """cur/new = {title, meta_description, body: [blocks], faq: [{q,a}], slug}. `new` is the FULL
    page after the refresh (unchanged fields already carried over by the caller).
    Returns {ok, errors: [..], warnings: [..], material: bool}."""
    today = today or _dt.date.today()
    reasons = {str(r).split(':')[0].strip().lower() for r in (reasons or [])}
    change_log = [str(c) for c in (change_log or [])]
    errors: List[str] = []
    warnings: List[str] = []

    # 1) the URL is frozen
    if new.get('slug') and cur.get('slug') and str(new['slug']) != str(cur['slug']):
        errors.append('slug_changed')

    # 2) title: only for a CTR/striking reason, and never too long
    title_changed = norm(new.get('title')) != norm(cur.get('title'))
    if title_changed and not (reasons & TITLE_REASONS):
        errors.append('title_change_not_allowed')
    if len(str(new.get('title') or '')) > TITLE_MAX:
        errors.append('title_too_long')
    if not str(new.get('title') or '').strip():
        errors.append('title_empty')

    body_new = list(new.get('body') or [])
    body_cur = list(cur.get('body') or [])
    if not content_blocks(body_new):
        errors.append('body_empty')

    # 3) the primary keyword stays in the title and the first paragraph (only where it already was)
    if primary_kw:
        for slot, cur_txt, new_txt in (('title', cur.get('title'), new.get('title')),
                                       ('first_paragraph', first_paragraph(body_cur), first_paragraph(body_new))):
            if kw_cover(primary_kw, new_txt or '') < KW_COVER_MIN:
                if kw_cover(primary_kw, cur_txt or '') >= KW_COVER_MIN:
                    errors.append('kw_missing_' + slot)
                else:
                    warnings.append('kw_missing_' + slot)

    # 4) words: never shrink, never balloon
    w_cur, w_new = words(body_cur), words(body_new)
    if w_new < w_cur:
        errors.append('words_decreased:%d<%d' % (w_new, w_cur))
    elif w_cur and w_new > WORDS_MAX_GROWTH * w_cur:
        errors.append('words_grew_too_much:%d>%d' % (w_new, int(WORDS_MAX_GROWTH * w_cur)))

    # 5) every existing H2 survives (a stale-year one may go if the change_log says so)
    new_h2 = set(h2s(body_new))
    removed_ok = [norm(c) for c in change_log if _REMOVED_OUTDATED.match(c)]
    for raw in content_blocks(body_cur):
        if not str(raw).startswith('## '):
            continue
        h = norm(raw[3:])
        if h in new_h2:
            continue
        if _stale_year(raw, today) and any(h and h in c for c in removed_ok):
            continue
        errors.append('h2_missing:' + h[:60])

    # 6) NEW NUMBERS GUARD — a refresh never adds a figure that was not already on the page
    added = sorted(numbers(all_text(new), today) - numbers(all_text(cur), today))
    if added:
        (errors if ymyl else warnings).append('new_numbers:' + ','.join(added[:10]))

    # 7) FAQ never shrinks
    if len([f for f in (new.get('faq') or []) if isinstance(f, dict)]) < \
            len([f for f in (cur.get('faq') or []) if isinstance(f, dict)]):
        errors.append('faq_decreased')

    # 8) links in the body: same-site article pages only
    for b in content_blocks(body_new):
        for m in _MD_LINK.finditer(str(b)):
            if not _SAME_SITE.match((m.group(2) or '').strip()):
                errors.append('foreign_link')
                break

    return {'ok': not errors, 'errors': errors, 'warnings': warnings,
            'material': is_material(cur, new), 'words': {'before': w_cur, 'after': w_new}}
