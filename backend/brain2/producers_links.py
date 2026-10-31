# -*- coding: utf-8 -*-
"""منتج `links_digest` (SPEC-B B5b): العقل يقرأ أرقام الأنظمة المتصلة ويكتب ملخصًا قصيرًا.

* ⛔ نداءات تلقائية لقائمة بيضاء فقط من أدوات القراءة لكل نظام معروف (`KNOWN_SYSTEMS`). نظام غير معروف ⇒ لا نداء تلقائي أبدًا
  (تظهر أدواته في شاشة «الأنظمة المتصلة» فقط حين يضغط المؤسس «جرّب الاتصال»).
* ⛔ `initialize` و`tools/list` ليسا «نداء أداة»؛ لا يُنادى أي اسم خارج القائمة البيضاء حتى لو ظهر في `tools/list`.
* أداة تطلب وسيطًا غير `brand_id` تُتخطّى؛ و`brand_id` يؤخذ من حقل العلامة في الرابط، وغيابه ⇒ تُتخطّى الأداة.
* فشل قراءة كل أدوات النظام ⇒ `SourceDown` (لا نكتب شيئًا ولا نخلط «فاضي» بـ«تعذّر»).
"""
import json
import logging

from brain2 import links as LK
from brain2.contract import Producer, SourceDown, Target

logger = logging.getLogger(__name__)

FACTS_MAX_BYTES = 3800
# نظام معروف ⇐ {match: كلمات في اسم الرابط (صغيرة)، label: الاسم في الجملة، tools: القائمة البيضاء (للقراءة فقط)}.
KNOWN_SYSTEMS = {
    'madar': {'match': ('madar', 'مدار'), 'label': 'مدار', 'tools': ('kpis_get', 'alerts_list')},
}
ROLE = (
    ' دورك: ملخص قصير لأرقام نظام متصل. في text اكتب ثلاثة أسطر أو أربعة تبدأ أولها بعبارة «من {label} هذا الأسبوع:». '
    'انقل الأرقام كما وردت تمامًا ولا تحسب أرقامًا جديدة، وما لم يصل فقل «غير متاح بعد». لا تنصح بإنفاق مال، '
    'ولا تتجاوز ٥٠٠ حرف. الشكل المطلوب: {"text":"…"}'
)


def system_of(name):
    """مفتاح النظام المعروف لاسم رابط، أو None (غير معروف ⇒ لا نداء تلقائي)."""
    n = (name or '').strip().lower()
    for key, spec in KNOWN_SYSTEMS.items():
        if any(m in n for m in spec['match']):
            return key
    return None


def _shrink(v, depth=0):
    """يقصّ ردّ نظام آخر إلى شكل صغير: أرقام ونصوص قصيرة وقوائم قصيرة. ⛔ لا بريد ولا هاتف يمرّ."""
    from brain2.producers_biz import _scrub
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        return _scrub(v, 120)
    if depth >= 4:
        return None
    if isinstance(v, list):
        return [_shrink(x, depth + 1) for x in v[:8]]
    if isinstance(v, dict):
        return {str(k)[:40]: _shrink(x, depth + 1) for k, x in list(v.items())[:20]}
    return None


def _size(o):
    return len(json.dumps(o, ensure_ascii=False, sort_keys=True).encode('utf-8'))


def _fit(results):
    """يقلّص القوائم الأطول أولًا حتى يسع في الحد."""
    guard = 0
    while _size(results) > FACTS_MAX_BYTES and guard < 200:
        guard += 1
        longest = None

        def walk(o):
            nonlocal longest
            if isinstance(o, list) and o and (longest is None or len(o) > len(longest)):
                longest = o
            for x in (o.values() if isinstance(o, dict) else o if isinstance(o, list) else []):
                walk(x)
        walk(results)
        if longest is None or len(longest) <= 1:
            break
        longest.pop()
    return results


def _args_for(tool, brand_id):
    """وسطاء أداة من مخططها: لا وسيط ⇒ {}؛ `brand_id` وحده مطلوب ⇒ من الرابط؛ غير ذلك ⇒ None (تُتخطّى)."""
    schema = tool.get('inputSchema') if isinstance(tool.get('inputSchema'), dict) else {}
    required = [r for r in (schema.get('required') or []) if isinstance(r, str)]
    args = {}
    for r in required:
        if r == 'brand_id' and brand_id:
            args['brand_id'] = brand_id
        else:
            return None
    return args


def gather_link(row, client):
    """رابط معروف ⇒ (facts|None, أسباب التخطي). يرفع LinkError لو فشل الاتصال نفسه."""
    key = system_of(row.name)
    spec = KNOWN_SYSTEMS[key]
    client.initialize()
    listed = {t['name']: t for t in client.list_tools()}
    results, skipped = {}, []
    for name in spec['tools']:            # ⛔ القائمة البيضاء وحدها
        tool = listed.get(name)
        if tool is None:
            skipped.append(name + ':missing')
            continue
        args = _args_for(tool, row.brand_id)
        if args is None:
            skipped.append(name + ':args')
            continue
        try:
            results[name] = _shrink(client.call_tool(name, args))
        except LK.LinkError as exc:
            skipped.append(name + ':fail')
            logger.warning('links_digest: tool %s failed for link %s: %s', name, row.id, exc.message)
    if not results:
        return None, skipped
    return _fit({'system': spec['label'], 'results': results}), skipped


def gather(ctx):
    db = ctx.ns['db']
    Link = LK._models(db)
    try:
        rows = Link.query.filter_by(enabled=True).order_by(Link.created_at, Link.id).all()
    except Exception:
        raise SourceDown('v2_brain_links')
    targets, failures, known = [], 0, 0
    for row in rows:
        if system_of(row.name) is None:
            continue                      # نظام غير معروف: لا نداء
        known += 1
        try:
            client = LK.client_for(row)
            facts, skipped = gather_link(row, client)
        except LK.LinkError as exc:
            LK.mark(db, row, False, exc.message)
            failures += 1
            continue
        if facts is None:
            LK.mark(db, row, False, 'لم تصل أرقام من النظام الآخر')
            failures += 1
            continue
        LK.mark(db, row, True)
        targets.append(Target(ref='link:%s' % row.id, label=('أرقام %s' % facts['system'])[:120], facts=facts,
                              meta={'link_id': row.id}))
    if known and failures == known and not targets:
        raise SourceDown('links')
    return targets


def prompt(target):
    from brain2.producers_biz import _system_ar, _user_prompt
    label = str(target.facts.get('system') or 'النظام')
    return (_system_ar() + ROLE.replace('{label}', label), _user_prompt(target, 'اكتب ملخص الأسبوع من هذه الأرقام.'))


def validate(raw, target):
    from brain2.producers_biz import _text_of
    t = _text_of(raw, 550)
    return {'text': t} if t else None


PRODUCERS = [
    Producer(
        id='links_digest', section='reports', kind='note',
        label='من الأنظمة المتصلة',
        sentence='يقرأ العقل أرقام الأنظمة المتصلة ويكتب ملخصًا قصيرًا.',
        lock_reason='', may_run_alone=True, default_mode='alone', per_run_cap=2,
        gather=gather, prompt=prompt, validate=validate,
        tag='من الأنظمة المتصلة', approve_label='احتفظ بها',
    ),
]
