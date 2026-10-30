# -*- coding: utf-8 -*-
"""جسر بايثون ⇐ node للّوحة الجديدة: `logic(fn, *args)` يشغّل v2-logic.js، و`real_rows(client, heads)` يطلّع صفوف الوارد
الحقيقية (dashboard-api.js جوه node:vm) من ردود الداشبورد نفسه. ⛔ صفر شبكة."""
import json
import os
import shutil
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
NODE = shutil.which('node')


def _run(script, payload, tz='UTC'):
    env = dict(os.environ, TZ=tz)
    proc = subprocess.run([NODE, os.path.join(_HERE, script)], input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, timeout=60, env=env)
    if proc.returncode != 0:
        raise RuntimeError('node failed: ' + proc.stderr[-2000:])
    return json.loads(proc.stdout)


def logic(fn, *args):
    return _run('v2_apply.js', {'fn': fn, 'args': list(args)})


def decide(row, action, reply, reason='', extra=None):
    """يشغّل `EP.decideInboxItem` الحقيقي على ردّ جاهز (`{'status','body'}` أو `{'throw': True}`) ⇒ {result, calls}."""
    return _run('v2_decide.js', {'row': row, 'action': action, 'reason': reason, 'extra': extra, 'reply': reply})


def real_rows(client, headers, keys=None):
    """مرحلتين: الأولى تعرف المسارات المطلوبة، التانية تديها ردود الداشبورد الحقيقية لكل مسار."""
    first = _run('v2_rows.js', {'responses': {}, 'keys': keys})
    responses = {}
    for p in first['asked']:
        r = client.get(p, headers=headers)
        try:
            body = r.get_json()
        except Exception:
            body = None
        responses[p] = {'status': r.status_code, 'body': body if body is not None else {}}
    out = _run('v2_rows.js', {'responses': responses, 'keys': keys})
    out['responses'] = responses
    return out
