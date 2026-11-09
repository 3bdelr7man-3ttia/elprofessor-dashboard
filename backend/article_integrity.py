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
