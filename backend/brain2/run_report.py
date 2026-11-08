# -*- coding: utf-8 -*-
"""«آخر تشغيل للعقل» — يحوّل سجل الجولة (رموز فقط في `skipped_json`) إلى جمل عربية يقرؤها المؤسس كما هي.

لماذا هنا لا في المتصفح: أسماء المنتجين وأسباب التوقف معروفة على الخادم وحده، والجملة الواحدة تُختبر مرة واحدة.

قواعد ثابتة:
  * ⛔ لا تفاصيل تقنية في الجمل (لا مسارات ولا أسماء استثناءات). التفصيل في سجل الخادم.
  * ⛔ لا رقم مخترع: كل رقم من سجل الجولة نفسه أو من إعداد الخادم الفعلي.
  * ⛔ لا «·» جنب رقم عربي، وصيغة محايدة (مصادر لا أفعال أمر لمذكّر أو مؤنث).
  * ⛔ لا قيمة مفتاح تخرج أبدًا: نقول أين يُضبط المفتاح فقط.
"""
import datetime

from brain2 import registry

_AR_DIGITS = str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')

# أين يُضبط مفتاح الموديل (خانة «من يكتب للعقل» الموجودة في تبويب «المساعدون»).
KEY_WHERE = ('الإضافة من قسم «العقل» ← تبويب «المساعدون» ← بطاقة «من يكتب للعقل» ← زرّ «أضف مفتاحًا»: '
             'اختيار الجهة من القائمة، ولصق مفتاحها، وجعل دوره «الأساسي»، ثم تجربته بزرّ «جرّبه».')
KEY_MISSING = 'لا يوجد مفتاح موديل يكتب به العقل، فلم يُكتب شيء.'
KEY_TEST = ('تجربة المفتاح الأساسي بزرّ «جرّبه» في بطاقة «من يكتب للعقل» (تبويب «المساعدون»)، '
            'ولو فشلت التجربة: إضافة مفتاح جديد وجعله «الأساسي».')

# الأسماء: [واحد، اثنان، جمع ٣–١٠، تمييز ١١ فأكثر] (نفس صيغة `U()` في الواجهة).
F_PROPOSAL = ['اقتراحًا واحدًا', 'اقتراحين', 'اقتراحات', 'اقتراحًا']
F_NOTE = ['ملاحظة واحدة', 'ملاحظتين', 'ملاحظات', 'ملاحظة']
F_TIME = ['مرة واحدة', 'مرتين', 'مرات', 'مرة']
F_QUESTION = ['سؤالًا واحدًا', 'سؤالين', 'أسئلة', 'سؤالًا']
# صيغة الرفع حين يكون العدد فاعلًا أو نائب فاعل («أُرسل سؤالان»، «لم يصل سؤال واحد»).
F_QUESTION_NOM = ['سؤال واحد', 'سؤالان', 'أسئلة', 'سؤالًا']
F_WRITE = ['كتابة واحدة', 'كتابتين', 'كتابات', 'كتابة']


def ar(n):
    return str(int(n)).translate(_AR_DIGITS)


def count(n, forms):
    n = int(n or 0)
    if n == 1:
        return forms[0]
    if n == 2:
        return forms[1]
    if 3 <= n % 100 <= 10:
        return ar(n) + ' ' + forms[2]
    return ar(n) + ' ' + forms[3]


def _label(pid):
    p = registry.by_id(pid)
    return (p.label if p is not None else '') or 'كتابة'


# سبب توقف الجولة كلها ⇒ (جملة الفشل، ما يلزم لإصلاحه أو '').
def stop_text(reason, run_cap=None, ai_reason=''):
    if reason in ('no_key', 'no_writer'):
        return KEY_MISSING, KEY_WHERE
    if reason == 'cap':
        return 'بلغت نداءات الموديل حدّها اليوم، فتوقّف التشغيل.', 'يعود تلقائيًا بعد منتصف الليل بتوقيت جرينتش.'
    if reason in ('day_cap', 'opinion_cap'):
        return 'بلغت كتابات العقل حدّها اليوم، فتوقّف التشغيل.', 'يكمل التشغيل التالي ما بقي، بعد منتصف الليل بتوقيت جرينتش.'
    if reason == 'run_cap':
        cap = ('، وهو ' + count(run_cap, F_WRITE)) if run_cap else ''
        return 'وصل التشغيل إلى حدّه في المرة الواحدة' + cap + '.', 'يكمل التشغيل التالي ما بقي.'
    if reason == 'reserve':
        return 'توقّف التشغيل ليترك ما بقي من نداءات اليوم لأزرار اللوحة.', 'يعود بعد منتصف الليل بتوقيت جرينتش.'
    if reason == 'off':
        return 'كتابة العقل موقوفة من إعداد الخادم.', 'يلزم إزالة إعداد إيقاف كتابة العقل من إعدادات الخادم ثم إعادة النشر.'
    if reason == 'ai_error':
        why = (' (' + ai_reason.strip()[:120] + ')') if isinstance(ai_reason, str) and ai_reason.strip() else ''
        return 'لم يرد الموديل أكثر من مرة متتالية' + why + '، فتوقّف التشغيل.', KEY_TEST
    if reason == 'error':
        return 'توقّف التشغيل بسبب عطل داخلي قبل أن يكتمل.', 'التفصيل في سجل الخادم. يمكن التشغيل مرة أخرى بزرّ «شغّل الآن».'
    if reason == 'busy':
        return 'كان تشغيل آخر يعمل في الوقت نفسه، فلم يبدأ هذا.', ''
    return 'توقّف التشغيل قبل أن يكتمل.', ''


def _producer_lines(pid, r, done, failed):
    lab = '«' + _label(pid) + '»'
    st = r.get('state') or ''
    proposed, noted = int(r.get('proposed') or 0), int(r.get('done_alone') or 0)
    fails, exists = int(r.get('failed') or 0), int(r.get('exists') or 0)
    discarded, errors = int(r.get('discarded') or 0), int(r.get('errors') or 0)
    wrote = False
    if proposed:
        done.append(lab + ': كتب ' + count(proposed, F_PROPOSAL) + ' تنتظر قرارك.')
        wrote = True
    if noted:
        done.append(lab + ': كتب ' + count(noted, F_NOTE) + '.')
        wrote = True
    if discarded and not wrote:
        done.append(lab + ': لم يجد ما يناسب، فلم يكتب اقتراحًا.')
        wrote = True
    if fails:
        failed.append(lab + ': تعذّرت الكتابة ' + count(fails, F_TIME) + ' (لم يرد الموديل أو جاء المكتوب غير صالح).')
    if errors:
        failed.append(lab + ': حدث عطل أثناء الكتابة ' + count(errors, F_TIME) + '.')
    if st == 'source_down':
        failed.append(lab + ': تعذّرت قراءة بياناته من المنصة الآن.')
    elif st == 'gather_error':
        failed.append(lab + ': حدث عطل أثناء جمع بياناته.')
    elif st == 'not_reached':
        failed.append(lab + ': لم يصل إليه الدور لأن التشغيل توقّف.')
    elif st == 'interrupted':
        failed.append(lab + ': لم يكتمل لأن التشغيل توقّف في أثنائه.')
    elif not wrote and not fails and not errors:
        if st == 'off':
            done.append(lab + ': متوقّف من القواعد.')
        elif exists:
            done.append(lab + ': لا جديد؛ ما كُتب من قبل ما زال صالحًا.')
        elif st in ('none', 'done'):
            done.append(lab + ': لا يوجد ما يُكتب عنه الآن.')
    for src in r.get('sources_down') or []:
        failed.append(lab + ': تعذّرت قراءة ' + {'pmsg': 'رسائل المنصة', 'messages': 'رسائل الموقع', 'smsg': 'رسائل الموقع',
                                                  'leads': 'طلبات التواصل'}.get(src, 'أحد مصادره') + ' الآن.')


def _tg_lines(tg, done, failed):
    if not isinstance(tg, dict):
        return ''
    fix = ''
    sent = int(tg.get('sent') or 0)
    bad = int(tg.get('failed') or 0)
    sk = tg.get('skipped') if isinstance(tg.get('skipped'), dict) else {}
    if sent:
        done.append('تليجرام: أُرسل ' + count(sent, F_QUESTION_NOM) + ' للقرار.')
    if bad:
        failed.append('تليجرام: لم يصل ' + count(bad, F_QUESTION_NOM) + '؛ المنصة لم تؤكّد الإرسال.')
        fix = 'يلزم التأكد من ربط بوت تليجرام في المنصة. الاقتراحات نفسها موجودة في «ابدأ القرارات».'
    if sk.get('cap'):
        failed.append('تليجرام: لم يُرسل ' + count(sk['cap'], F_QUESTION_NOM) + ' لأن أسئلة اليوم بلغت حدّها.')
    if sk.get('no_proxy'):
        failed.append('تليجرام: الربط مع المنصة غير مضبوط، فلم يُرسل شيء.')
        fix = fix or 'يلزم ضبط ربط اللوحة بالمنصة في إعدادات الخادم.'
    return fix


def describe(run, report, now=None, run_cap=None):
    """run: صف `v2_brain_runs` · report: dict من `skipped_json['_report']` (قد يكون فاضيًا لجولة قديمة).
    يرجع {state, trigger_text, done[], failed[], fix, headline}."""
    now = now or datetime.datetime.utcnow()
    report = report if isinstance(report, dict) else {}
    done, failed, fix = [], [], ''
    trig = 'تلقائيًا' if (run.trigger == 'cron') else 'بطلب من اللوحة'
    if run.finished_at is None:
        started = run.started_at or now
        if (now - started) < datetime.timedelta(minutes=15):
            return {'state': 'running', 'trigger_text': trig, 'done': [], 'failed': [], 'fix': '',
                    'headline': 'العقل يعمل الآن.'}
        return {'state': 'stale', 'trigger_text': trig, 'done': [], 'failed': ['انقطع التشغيل قبل أن يكتمل (غالبًا أُعيد تشغيل الخادم في أثنائه).'],
                'fix': 'يمكن التشغيل مرة أخرى بزرّ «شغّل الآن».', 'headline': 'انقطع آخر تشغيل.'}
    by = report.get('producers') if isinstance(report.get('producers'), dict) else {}
    for pid in by:
        if isinstance(by[pid], dict):
            _producer_lines(pid, by[pid], done, failed)
    stop = report.get('stop') or ''
    if stop:
        line, fx = stop_text(stop, run_cap=run_cap, ai_reason=report.get('ai_reason') or '')
        failed.insert(0, line)
        fix = fx
    tfix = _tg_lines(report.get('tg'), done, failed)
    fix = fix or tfix
    # ⛔ «كتب» تُقال فقط عمّا كُتب فعلًا (اقتراح ينتظر القرار أو ملاحظة نُفّذت وحدها). `run.items` يعدّ الصفوف الفاشلة
    # والمستبعدة أيضًا، فلا يصلح للعنوان إلا لجولة قديمة بلا سجل.
    if report:
        written = sum(int(r.get('proposed') or 0) + int(r.get('done_alone') or 0) for r in by.values() if isinstance(r, dict))
    else:
        written = int(run.items or 0)
    if stop == 'busy':
        state = 'busy'
    elif not written:
        state = 'failed' if failed else 'nothing'
    else:
        state = 'partial' if failed else 'ok'
    if not report:
        # جولة قديمة قبل هذا السجل: نذكر ما نعرفه فقط.
        done = ['كتب ' + count(written, F_WRITE) + '.'] if written else ['لم يكتب شيئًا جديدًا.']
    if state == 'busy':
        head = 'لم يبدأ هذا التشغيل لأن تشغيلًا آخر كان يعمل.'
    elif state == 'ok':
        head = 'عمل العقل وكتب ' + count(written, F_WRITE) + '.'
    elif state == 'nothing':
        head = 'عمل العقل ولم يجد جديدًا يكتب عنه.'
    elif state == 'partial':
        head = 'عمل العقل وكتب ' + count(written, F_WRITE) + '، وتعذّر جزء.'
    else:
        head = 'لم يكتب العقل شيئًا في آخر تشغيل.'
    return {'state': state, 'trigger_text': trig, 'done': done[:14], 'failed': failed[:10], 'fix': fix, 'headline': head}
