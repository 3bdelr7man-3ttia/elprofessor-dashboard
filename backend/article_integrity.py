# -*- coding: utf-8 -*-
"""R19 — فحص اكتمال مقال قبل نشره آليًّا.

القياس (٢٠٢٦-١١-٠٩): ١٥ من ٢٢٤ مقالًا منشورًا كانت مبتورة وسط الجملة/العنوان/القائمة («٦ خطوات» تقف عند ٤،
وعنوان `## س`، وجدول ينقطع). السبب في المنصّة: `call_deepseek` يطلب max_tokens=8000 ولا يقرأ finish_reason،
فيصل نصٌّ مقطوع إلى المزامنة كأنه كامل. هذا هو الحزام الثاني عند مدخل المدوّنة: لا يعتمد على أن المنصّة
أخبرتنا بشيء — يقرأ المتن نفسه.

دالة نقيّة (بلا Flask ولا قاعدة بيانات) ليسهل اختبارها وإعادة استعمالها من أي مسار نشر.
متحفّظة عمدًا: تُرجِع أسبابًا فقط عند علامة قاطعة، لأن الخطأ الإيجابي = مقال سليم يتأخّر في المسودات.
"""
import re

import refresh_rules as _rr

_AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
# ما يجوز أن تُختم به الجملة الأخيرة. النقطتان «:» ليست منها: متن ينتهي بتمهيدٍ لقائمة لم تأتِ مبتور.
_TERMINALS = ('.', '!', '؟', '?', '…', '»', '"', '”', ')', '*', '،.')
# «خطوات/مراحل» فقط: عناوينها الفرعية مرقّمة بالضرورة. «٦ محاور/معايير» تُشرح غالبًا بعناوين غير مرقّمة
# (مقالا ٣٣٩ و٢٩٢ سليمان وعنوانهما «٦ محاور») فالمقارنة هناك خطأ إيجابي.
_COUNTED = r'(?:خطوات|مراحل)'
_TITLE_COUNT = re.compile(r'(\d{1,2})\s*' + _COUNTED)
_NUMBERED_H2 = re.compile(r'^##\s*(\d{1,2})\s*[.\-:)،]')


def incomplete_reasons(blocks, title=''):
    """أسباب الاشتباه في بتر المتن — قائمة فارغة = يبدو مكتملًا."""
    main = [str(b).strip() for b in _rr.content_blocks(blocks or []) if str(b).strip()]
    if not main:
        return ['empty_body']
    reasons = []
    last = main[-1]
    if last.startswith('## '):
        reasons.append('ends_on_heading')
    elif last.startswith('|'):
        reasons.append('ends_in_table')
    elif not last.endswith(_TERMINALS):
        reasons.append('no_terminal_punctuation')
    # العنوان يعد بعدد (٦ خطوات) والمتن فيه عناوين مرقّمة تقف قبله.
    m = _TITLE_COUNT.search((title or '').translate(_AR_DIGITS))
    if m:
        promised = int(m.group(1))
        got = [int(x.translate(_AR_DIGITS)) for b in main
               for x in [(_NUMBERED_H2.match(b.translate(_AR_DIGITS)) or [None, ''])[1]] if x]
        if 3 <= promised <= 12 and len(got) >= 2 and max(got) < promised:
            reasons.append('promised_%d_got_%d' % (promised, max(got)))
    if sum(1 for b in main if b.startswith('```')) % 2:
        reasons.append('unclosed_code_fence')
    return reasons


# ---------------------------------------------------------------------------
# R19 — إصلاح ذيل مقال مبتور (مرة واحدة على المقالات المنشورة اللي اتقاست 2026-11-09)
# ---------------------------------------------------------------------------
_SENT_END = ('.', '!', '؟', '?', '…')


def _main_indices(blocks):
    """مواضع كتل المتن (نفس منطق refresh_rules.content_blocks) — عشان نعدّل المتن ونسيب أقسام الروابط زي ما هي."""
    out, skipping = [], False
    for i, b in enumerate(blocks or []):
        s = str(b)
        if s.strip() in _rr.LINK_HEADINGS:
            skipping = True
            continue
        if skipping and _rr.is_link_bullet(s):
            continue
        skipping = False
        if s.strip():
            out.append(i)
    return out


def _last_sentence_end(s):
    """آخر موضع علامة نهاية جملة — مع تجاهل نقطة ترقيم البنود («5.») عشان القصّ ما يسيبش رقم بند لوحده."""
    for j in range(len(s) - 1, -1, -1):
        if s[j] in _SENT_END:
            if s[j] == '.' and j > 0 and s[j - 1].translate(_AR_DIGITS).isdigit():
                continue
            return j
    return -1


def repair_tail(blocks):
    """يقصّ آخر كتلة مبتورة لآخر جملة كاملة (أو يشيلها لو مفيهاش جملة كاملة)، ثم يشيل عنوانًا بقى في الآخر بلا متن.
    بيرجّع (الكتل الجديدة، الإجراءات). ⛔ ما بيكتبش كلام جديد — قصّ بس."""
    blocks = list(blocks or [])
    acts = []
    idx = _main_indices(blocks)
    if not idx:
        return blocks, acts
    i = idx[-1]
    s = str(blocks[i]).rstrip()
    if not s.startswith('## ') and not s.startswith('|') and not s.endswith(_TERMINALS):
        lines = s.split('\n')
        while len(lines) > 1 and not lines[-1].rstrip().endswith(_TERMINALS):
            lines.pop()   # قائمة في كتلة واحدة: سطر البند المقطوع يتشال كله
        if len(lines) < len(s.split('\n')) and lines[-1].rstrip().endswith(_TERMINALS):
            blocks[i] = '\n'.join(lines).rstrip()
            acts.append('drop_line')
        else:
            cut = _last_sentence_end(s)
            if cut >= 40:
                blocks[i] = s[:cut + 1]
                acts.append('trim_sentence')
            else:
                del blocks[i]
                acts.append('drop_fragment')
    idx = _main_indices(blocks)
    if idx and str(blocks[idx[-1]]).strip().startswith('## '):
        del blocks[idx[-1]]
        acts.append('drop_heading')
    return blocks, acts
