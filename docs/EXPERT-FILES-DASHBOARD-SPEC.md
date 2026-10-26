# «ملف للخبير» في الداشبورد — مواصفة تنفيذ (الجولة ٦) — 2026-10-26

**القرار:** المؤسس اعتمد تصوّر «ملف للخبير» وخطة الـ٦ جولات («تمام اعتمد وتوكل على الله»)؛ الجولة دي (٦: الداشبورد) آخرها.
**الفرع:** `expert-file-r6-dashboard` (متفرّع من `main`). ⛔ لا push، ولا main، ولا Coolify، ولا أي طلب لسيرفر حقيقي.
**النطاق:** `backend/app.py` + `dashboard-cloud/dashboard-api.js` + `dashboard-cloud/index.html` + اختبارات + أداة صور. ⛔ ولا سطر في ريبو المنصة.
**المؤسس هو اللي بيوزّع.** الداشبورد بيعرض ويبعت القرار للجسر؛ كل حركة فلوس بتحصل على المنصة بدوالّها المحروسة (ولا قرار مالي جديد هنا).

**المصادر اللي اتقرت قبل الكتابة (الكود هو الحَكَم):**
- المنصة (فرع `expert-file-r5-expert`، قراءة بس): `backend/routes/ops_bridge.py` (الجسر: `bridge_expert_files*` · `_ExpertFilesBridgeRoute` · `bridge_consultations` · `bridge_resolve_consultation` · `bridge_ops_queue`) ·
  `backend/routes/expert_files.py` (`bridge_list_files` · `_candidates` · `bridge_view` · `bridge_assign` · `bridge_reassign` · `bridge_refund` · `_settle_refund` · `bridge_resolve` · `ops_queue_snapshot` · `_unactivated_paid` · `enforce_expert_files` · `decline` · `client_problem` · `revise` · `STATUS_LABELS`/`TIER_LABELS`/`REASON_LABELS`/`NEXT_STEP_LABELS`/`CURRENCY_SYMBOL`) ·
  `backend/routes/consultations.py` (`resolve_disputed` · `bridge_list_consultations` · `_claim_refund` · `_refund_side_effects` · `_release_claimed` · `_serialize`) · `backend/ops_links.py` · `docs/expert-files/SPEC.md` (§٢ ق١–ق٢٥ · §٤ · §٨ · §٩ · §١٢-ج · §١٦).
- الداشبورد: `CLAUDE.md` · `STATUS.md` · `REF.md` · `backend/app.py` (`token_required` · `roles_required`/`role_grants` · `_audit` · `_actor_email` · `_resp_ok` · `_proxy_json` · `_platform_proxy` · `_market_proxy` · `platform_ops_queue` · `platform_verify_reassign` · `platform_market_request_close`) ·
  `dashboard-cloud/dashboard-api.js` (`api` · `LOADERS.inbox` · `LOADERS.opsQueue` · `EP.decideInboxItem` · `EP.reassignVerify` · `EP.purgeUser`) ·
  `dashboard-cloud/index.html` (`MODULES` · `opsQueueCounters` · `OPSQ_LANDINGS` · `applyNavCounts` · `opsQueuePanel` · `viewInbox` · `inboxType` · `renderInbox` · `inboxActs` · `drawInbox` · `renderEsc` · `openModal` · `userPurgeModal` · `AUDIT_LABEL` · `auditModal`) ·
  `backend/tests/test_platform_ops_proxies.py` · `backend/test_market_bridge.py` · `backend/tests/test_finance_authz.py` · `backend/tests/test_dash_ia_structure.py` · `backend/tests/uiharness/*`.

---

## ٠ — الفكرة في ٧ سطور

1. **مفيش عنصر قايمة جديد.** كل الشغل صفوف في «الوارد» تحت شريحتين جديدتين: **«ملفات للخبير»** و**«نزاعات»**، وشرايح العدّادات في «كل اللي مستنيك».
2. الصفوف جاية من الجسر **بالحرف**: `GET /api/bridge/expert-files?status=waiting|late|disputed` و`GET /api/bridge/consultations?status=disputed`. ولا ساعة بتتحسب في المتصفح (`hours_left` و`assign_overdue` من المنصة).
3. الفعل في **درج الصفّ** (زي باقي الوارد)، والفعل اللي فيه فلوس بيفتح **نافذة تأكيد جوه الصفحة** فيها المبلغ والعملة واسم الطرف، والزرار بيقفل نفسه أول ما يتداس.
4. اختيار الخبير من **`candidates[]` اللي على الصفّ نفسه** (المعتمدين اللي الجسر نفسه هيقبلهم)، مش من قايمة تانية.
5. ٨ مسارات جديدة في `app.py`، كلها `admin` بس، رفيعة فوق `_platform_proxy`، وكل كتابة ناجحة بتتسجّل في `_audit` بإيميل اللي عملها.
6. النزاع بيتعرض بالرأيين (الأصلي + تعديل الخبير) جنب بعض **من غير ما الشاشة تقول أنهي الرسمي** (قرار مفتوح عند المؤسس) — الحسم هنا على الفلوس بس.
7. الاختبارات والصور: المنصة متزيّفة بالكامل (`requests.*` بيترد عليه من الذاكرة)، والصور بـPlaywright على أصل وهمي بـ`context.route` — صفر طلبات حقيقية.

---

## ١ — قرارات عند التعارض (الطلب × الكود) — الأبسط والأأمن، والسبب

| # | القرار | السبب |
|---|---|---|
| د١ | ولا عنصر قايمة جديد: الشغل في **«الوارد»** (شريحتين: `t:files` «ملفات للخبير» و`t:disputes` «نزاعات»). وفي «الضمان والنزاعات» ← تبويب «النزاعات» سطر واحد بيحوّل للوارد. | قاعدة القايمة الثابتة (`CLAUDE.md` + `test_twelve_items_visible_plus_four_pinned`). تبويب «النزاعات» في الضمان بيقرا دفتر SQLite بتاع الداشبورد (`/api/disputes`) — دفتر تاني خالص، وخلط الاتنين في جدول واحد = رقم فوق قايمة ما تحتويهوش. |
| د٢ | «ابعته لحد تاني» **قبل الاستلام** (`assigned`) = `POST …/assign` مش `reassign`. بعد الاستلام (`claimed`/`writing`/`needs_info`) = `reassign`. الواجهة بتختار حسب `status` الصفّ. | `bridge_reassign` بيرفض أي حالة برّه `EXPERT_WORK` بـ409 «الملف ده مش عند خبير دلوقتي»، و`bridge_assign` هو اللي بيغيّر الخبير المختار قبل الاستلام (وبيبعت «الملف اتنقل» للقديم). |
| د٣ | العدّاد اسمه **`expert_files_waiting`** (`awaiting_assignment`+`assigned`) — مفيش مفتاح اسمه `expert_files_awaiting_assignment`. | `ops_queue_snapshot` بيرجّع: `expert_files_waiting` · `expert_files_late` · `expert_files_disputed` · `expert_files_open_total` · `expert_files_unactivated` · `expert_files_awaiting_payment`. |
| د٤ | قايمة الخبراء = `row.candidates[]` (مترتبة من المنصة: نفس بلد القانون الأول، بعدين اللي ما اعتذرش، بعدين بالاسم). ⛔ مش `/api/platform-experts`. | `_candidates` هو نفس فلتر `_approved_expert` اللي `assign`/`reassign` بيتحقّقوا بيه (معتمد · مش تجريبي · مش العميل · مش بريد المنصة). قايمة تانية ممكن تعرض خبير الجسر هيرفضه (404 «الخبير غير موجود أو غير معتمد»). |
| د٥ | كل المسارات الجديدة (قراءة وكتابة) `@roles_required('admin')`. وفي المتصفح مهامّ التحميل الجديدة بتتعمل لما `EP.role === 'admin'` بس، و403 ما يتسجّلش «تعذّر». | الصفوف فيها مبالغ وأجر الخبير وأسماء العملاء والطرف التاني ووقائع قانونية (نفس منطق F-095 اللي بيبعد `employee` عن الفلوس، ونفس `platform_ops_queue`). محمّل `inbox` بيتنادى كمان من شاشات الموظف («الدورات») — من غير الحارس كان هيطلع له شريط «تعذّر جلب» دايم. |
| د٦ | الرأي الرسمي بعد الحسم: الشاشة تعرض «الرأي الأصلي» و«تعديل الخبير» جنب بعض بعناوين محايدة + سطر «القرار هنا على الفلوس بس…»، و**ما فيش** زرار ولا كلمة بتختار رأي. | قرار مفتوح عند المؤسس (الطلب ⏳ + SPEC §١٦). الجسر نفسه ما بيلمسش `opinion`/`revision` في `resolve`. |
| د٧ | «رجّع الفلوس» متاح على **كل** ملف قبل التسليم (مستني خبير · متوزّع · متأخر)، كزرار تاني (مش الأساسي) في الدرج. | `bridge_refund` بيسمح بيه في `BEFORE_DELIVERY` (ق٢١) — مش قرار جديد. ملف لقانون مفيهوش خبير محتاج طريق غير إنه يستنى ٤٨ ساعة. |
| د٨ | نزاع على ملف بيظهر **مرة واحدة**: من قايمة الملفات (أغنى: السبب بالكود والملاحظة والرأيين). صفوف `/bridge/consultations` اللي فيها `expert_file_id` بتتشال — **إلا** لو قايمة الملفات رجعت `enabled:false`، ساعتها بتفضل (ما يبقاش نزاع متجمّد مستخبّي) وتتحسم من باب الاستشارات. | الجسر بيقول صراحة إن الحسم من الباب ده أو ده بيوصل لنفس `resolve_disputed` ونفس المزامنة. |
| د٩ | ٤٠٤ من جسر الملفات (المفتاح مقفول — أو الجسر مش منشور على الإنتاج لسه، والاتنين `{"detail":"Not Found"}`) ⇒ الداشبورد بيرجّع ٢٠٠ `{"enabled": false, ...}` فاضي. نفس الحاجة لجسر نزاعات الاستشارات (لسه على فرع الجولة ١). | ده مش عطل: «الوارد» ما يعلنش «تعذّر جلب» على خدمة مقفولة. والصدق محفوظ: لو المفتاح مقفول وفيه ملفات مدفوعة، `ops/queue` بيرجّع `expert_files_open_total` + سطر تنبيه بيتطبع في «كل اللي مستنيك» حرفيًا. أي كود تاني (٥٠٠ · ٥٠٢ · ٤٠١) بيعدّي زي ما هو ويبان «تعذّر». |
| د١٠ | تأكيد الفلوس جوه الصفحة (`moneyConfirmModal`) + **على الخادم** `confirmed: true` إجباري في جسم `refund` و`resolve` (وإلا ٤٠٠ ومن غير نداء للمنصة). ⛔ ولا `confirm()`/`prompt()`. | التأكيد ما يبقاش «واجهة بس»: أي نداء من غير النافذة (كود قديم، زرار جديد ناسيه) بيترفض. |
| د١١ | الكتابة بمهلة ٢٥ ثانية. لو المنصة ما ردّتش (٥٠٢) على فعل فلوس: رسالة «ما وصلناش رد…» + سطر سجل `*.no_reply` + إعادة تحميل الوارد. | الفعل ممكن يكون اتنفّذ والرد ضاع. المنصة محروسة (الضغطة التانية بترجع ٤٠٩ «الفلوس اتحرّكت…» ومش بتدفع مرتين)، بس لازم المؤسس يشوف الحالة قبل ما يدوس تاني، والسجل ما يقولش «ما حصلش حاجة». |
| د١٢ | «ملفات اتدفعت وما وصلتش للتوزيع» (`expert_files_unactivated`) = **عدّاد بس** (شريحة من غير شاشة). | الجسر ما عندوش قايمة ليها ولا فعل يقبلها (حالتها `awaiting_payment` و`bridge_refund` بيرفضها) — ناقص في جسر المنصة (§١٤ بند ١). |
| د١٣ | المستندات (`/bridge/expert-files/{id}/docs/{doc}`) **مش** في الجولة دي — الدرج بيعرض عددها وأسماءها من `docs[]` بس. | مش مطلوب للتوزيع ولا للحسم، ومحتاج بروكسي بايتات منفصل (`_platform_proxy` بيقرا JSON بس). |
| د١٤ | «مستنية الدفع» (`expert_files_awaiting_payment`) و«المفتوح إجمالًا» (`expert_files_open_total`) **مش شرايح** — سطر «للعلم» صغير تحت الشرايح. | مش شغل مستني المؤسس؛ شريحة = «فيه حاجة مستنياك». |

---

## ٢ — مكان كل حاجة في الواجهة (من غير عنصر قايمة جديد)

```
الوارد
├─ «كل اللي مستنيك — من المنصة» (opsQueuePanel)
│    شرايح جديدة:  [٣ ملفات مستنية خبير] [١ رأي متأخر] [٢ ملفات فيها «عندي مشكلة»] [١ ملف اتدفع وما وصلش للتوزيع · لا شاشة له بعد]
│    سطر للعلم:   «للعلم: ٤ ملفات مستنية الدفع · ٩ ملفات مفتوحة إجمالًا»
│    alerts[] زي ما هي (حرفيًا من المنصة)
├─ شريط الفرز (renderInbox):  الكل · [ملفات للخبير (٥)] · [نزاعات (٣)] · قرارات · رسائل · فلوس · توثيق · أخرى · متأخّر
├─ صفوف الوارد  ← صفّ الملف / صفّ النزاع (§٥-ب)، العمود الأوسط فيه المبلغ بدل «← الوجهة»
└─ الدرج (aside#drawer)  ← drawExpertFile / drawDispute (§٦-د) + الأزرار
     نوافذ جوه الصفحة: expertPickModal (اختيار خبير) · moneyConfirmModal (رجوع/تحويل فلوس) · opinionsCompareModal (الرأيين جنب بعض)

الضمان والنزاعات ← تبويب «النزاعات»
└─ سطر فوق الجدول: «نزاعات المنصة (على الملفات والاستشارات) بتتحسم من «الوارد» ← «نزاعات» (٣)» — بيودّي هناك بضغطة.
```

- **الكمبيوتر (١٤٤٠):** الصفوف يمين، والدرج ٣٣٢px شمال (`.inboxwrap` الموجود). النوافذ في النص؛ نافذة المقارنة عريضة (`.modal.wide` = ٩٦٠px، عمودين).
- **الموبايل (٣٩٠):** الصفوف عمود واحد (`@media(max-width:760px)` الموجود)، والدرج تحت القايمة — بعد ما الصفّ يتداس: `drawer.scrollIntoView({block:'start'})`. نافذة المقارنة عمود واحد (الأصلي فوق، التعديل تحت). الأزرار بعرض كامل.
- **الشارة على «الوارد» في الشريط الجانبي:** طول `INBOX` (بيشمل الصفوف الجديدة) — زي ما هي. صفّ ملف `slaWarn`/`late` بيقلبها أحمر بنفس `inboxIsLate`.

---

## ٣ — مسارات الداشبورد الجديدة (`backend/app.py`) وكل واحد بينادي إيه في المنصة

كلها: `@token_required` + `@roles_required('admin')`. مكانها بعد `platform_verify_reassign` (قسم «R1 launch-fix inboxes»). نفس السرّ (`X-ELP-Metrics-Secret` = `PLATFORM_METRICS_SECRET`) عن طريق `_platform_proxy` — ⛔ السرّ ما يطلعش للمتصفح أبدًا.

| # | الداشبورد | ⇒ المنصة (بالحرف) | الجسم/المعاملات اللي بتتبعت | المهلة | السجل لو نجح |
|---|---|---|---|---|---|
| م١ | `GET /api/platform-expert-files?status=waiting\|late\|disputed` | `GET /api/bridge/expert-files?status=…` | `params={'status': s}`؛ أي قيمة تانية (أو فاضية) ⇒ `waiting`. (`followup`/`all` مش مستعملين في الجولة دي، ومرفوضين ⇒ `waiting`) | ١٢ث | — |
| م٢ | `GET /api/platform-expert-files/<file_id>` | `GET /api/bridge/expert-files/{file_id}` | — | ١٢ث | — |
| م٣ | `POST /api/platform-expert-files/<file_id>/assign` | `POST /api/bridge/expert-files/{file_id}/assign` | `{"expert_email": <lower/strip>, "note": <strip[:1000]>}` | ٢٥ث | `expert_file.assign` |
| م٤ | `POST /api/platform-expert-files/<file_id>/reassign` | `POST /api/bridge/expert-files/{file_id}/reassign` | `{"expert_email": …, "note": …}` | ٢٥ث | `expert_file.reassign` |
| م٥ | `POST /api/platform-expert-files/<file_id>/refund` | `POST /api/bridge/expert-files/{file_id}/refund` | `{"note": <strip[:1000]>}` — ⛔ `confirmed` ما بيتبعتش للمنصة | ٢٥ث | `expert_file.refund` |
| م٦ | `POST /api/platform-expert-files/<file_id>/resolve` | `POST /api/bridge/expert-files/{file_id}/resolve` | `{"action": "release"\|"refund", "note": <strip[:2000]>}` | ٢٥ث | `expert_file.resolve` |
| م٧ | `GET /api/platform-consultation-disputes` | `GET /api/bridge/consultations?status=disputed` | `params={'status': 'disputed'}` (ثابت — الجسر بيقبل `^disputed$` بس) | ١٢ث | — |
| م٨ | `POST /api/platform-consultation-disputes/<consultation_id>/resolve` | `POST /api/bridge/consultations/{consultation_id}/resolve` | `{"action": …, "note": <strip[:2000]>}` | ٢٥ث | `consultation.resolve` |

**التحقق المحلي (قبل أي نداء للمنصة — ولا سطر سجل لو اترفض):**
- `file_id`/`consultation_id`: `re.fullmatch(r'[A-Za-z0-9_-]{1,64}', x)` وإلا ٤٠٤ `{'error': 'الملف ده مش موجود'}` (للاستشارة: «النزاع ده مش موجود»). (بيتحطّوا في مسار الـURL — ما يدخلش `/` ولا `..`.)
- `expert_email` (م٣/م٤): بعد `strip().lower()` يطابق `_COURSE_EMAIL_RE` الموجود و≤٢٠٠، وإلا ٤٠٠ `{'error': 'اختار خبير الأول'}`.
- `action` (م٦/م٨): `release` أو `refund` بس، وإلا ٤٠٠ `{'error': 'اختار: للخبير ولا للعميل'}`.
- `confirmed` (م٥/م٦/م٨): لازم `is True` (مش `"true"`)، وإلا ٤٠٠ `{'error': 'لازم تأكّد الأول من الشاشة'}`.
- `note`: نص؛ أي نوع تاني ⇒ `""`. بيتقصّ للحدّ (١٠٠٠ / ٢٠٠٠) — نفس حدود `ExpertFileAssignBody`/`ExpertFileNoteBody`/`ExpertFileResolveBody`/`ConsultationResolveBody`.

**مساعد واحد للأربع كتابات والقراءات (`_ef_bridge(method, path, params=None, json_body=None, timeout=12)`):**
```python
_EF_ERRORS_AR = {
    'Not Found': 'خدمة «ملف للخبير» مقفولة على المنصة دلوقتي',
    'Only a disputed consultation can be resolved': 'النزاع ده اتحسم قبل كده — حدّث الصفحة',
    'Already refunded manually': 'الفلوس دي رجعت للعميل يدوي قبل كده',
    'Already refunded by the payment gateway': 'الفلوس دي رجعت للعميل من بوابة الدفع قبل كده',
    'Consultation not found': 'النزاع ده مش موجود — حدّث الصفحة',
    'action must be release or refund': 'اختار: للخبير ولا للعميل',
    'Database not available': 'المنصة مش متاحة دلوقتي — جرّب بعد شوية',
    'unauthorized': 'الداشبورد مش قادر يكلّم المنصة دلوقتي',
}
NO_REPLY_AR = 'ما وصلناش رد من المنصة — حدّث الصفحة وشوف حصل إيه قبل ما تضغط تاني'
```
- بينادي `_platform_proxy(...)`، ولو الرد tuple فيه `error` موجود في الجدول ⇒ يستبدله (نفس الكود). الرسايل العربي اللي جاية من المنصة (§٤) بتعدّي زي ما هي.
- **القراءات (م١، م٧):** ٤٠٤ ⇒ `jsonify({'enabled': False, 'status': s, 'files': [], 'count': 0, 'total': 0})` (م٧: `'consultations': []`) بـ٢٠٠. ٢٠٠ ⇒ نفس حمولة المنصة **بالحرف** + `'enabled': True` (إضافة بس، ولا مفتاح بيتشال ولا بيتحسب). غير كده يعدّي زي ما هو.
- **القراءة م٢:** ٤٠٤ بـ`Not Found` ⇒ ٤٠٤ «خدمة «ملف للخبير» مقفولة…»؛ ٤٠٤ بـ«الملف ده مش موجود» يعدّي.
- **الكتابات:** ٥٠٢ (`تعذر الاتصال بالمنصة`) ⇒ ٥٠٢ `{'error': NO_REPLY_AR, 'no_reply': True}` + `_audit('<expert_file|consultation>.no_reply', target=id, meta={'attempt': 'assign|reassign|refund|resolve', 'action': …})`.
- بعد النجاح (`_resp_ok`) ⇒ `_audit(...)` بالمبالغ **من رد المنصة** (`_proxy_json(resp)`) مش من المتصفح — §٩.

**الكود المرجعي (شكل، مش نصّ نهائي):**
```python
_EF_ID_RE = re.compile(r'[A-Za-z0-9_-]{1,64}')
_EF_LIST_STATUSES = ('waiting', 'late', 'disputed')

@app.route('/api/platform-expert-files', methods=['GET'])
@token_required
@roles_required('admin')   # مبالغ + أجر الخبير + الطرف التاني + وقائع — فلوس، زي ops-queue
def platform_expert_files():
    s = (request.args.get('status') or 'waiting').strip().lower()
    if s not in _EF_LIST_STATUSES:
        s = 'waiting'
    resp = _ef_bridge('GET', '/api/bridge/expert-files', params={'status': s})
    if isinstance(resp, tuple) and int(resp[1]) == 404:
        return jsonify({'enabled': False, 'status': s, 'files': [], 'count': 0, 'total': 0})
    if _resp_ok(resp):
        return jsonify({**_proxy_json(resp), 'enabled': True})
    return resp

@app.route('/api/platform-expert-files/<file_id>/refund', methods=['POST'])
@token_required
@roles_required('admin')
def platform_expert_file_refund(file_id):
    if not _EF_ID_RE.fullmatch(file_id or ''):
        return jsonify({'error': 'الملف ده مش موجود'}), 404
    body = request.get_json(silent=True) or {}
    if body.get('confirmed') is not True:
        return jsonify({'error': 'لازم تأكّد الأول من الشاشة'}), 400
    note = _ef_note(body.get('note'), 1000)
    resp = _ef_bridge('POST', f'/api/bridge/expert-files/{file_id}/refund', json_body={'note': note}, timeout=25)
    if _resp_ok(resp):
        f = _proxy_json(resp)
        _audit('expert_file.refund', target=file_id, meta=_ef_meta(f, note=note))
    elif _ef_no_reply(resp):
        _audit('expert_file.no_reply', target=file_id, meta={'attempt': 'refund'})
    return resp
```
(`_ef_note(v, n)` = `str(v).strip()[:n]` لو نص وإلا `""` · `_ef_no_reply(resp)` = tuple بكود ٥٠٢ · `_ef_meta` في §٩.)

---

## ٤ — أشكال الجسر بالحرف (من الكود على فرع `expert-file-r5-expert`)

**الحراسة:** `/api/bridge/expert-files*` ورا `_ExpertFilesBridgeRoute`: المفتاح الأول (مقفول ⇒ ٤٠٤ `{"detail":"Not Found"}` حتى بجسم بايظ)، بعدين السرّ (غلط ⇒ ٤٠١ `{"detail":"unauthorized"}`)، بعدين قراية الجسم (غلط ⇒ ٤٢٢ والـ`detail` لستة ⇒ `_platform_proxy` بيحوّلها «المنصة رفضت البيانات المرسلة»). `/api/bridge/consultations*` ورا `_guard` بس (مش ورا المفتاح).

### ٤-أ `GET /api/bridge/expert-files?status=waiting|late|disputed|followup|all` (افتراضه `waiting`)
- `waiting` = `status ∈ {awaiting_assignment, assigned}` مترتبين بـ`claim_deadline_at` ↑ · `late` = `status ∈ {claimed, writing}` و`writing_due_at ≤ دلوقتي`، بـ`writing_due_at` ↑ · `disputed` = `status = disputed`، بـ`updated_at` ↑. الحدّ ٢٠٠ صفّ (`to_list(200)`)، و`total` = العدّ الكامل.
```json
{"status": "waiting", "count": 1, "total": 1, "files": [{
  "id": "uuid", "title": "إيجار شقة — المالك عايز يطلعني", "status": "assigned", "status_label": "بنختار لك خبير",
  "law_country": "eg", "law_label": "القانون المصري", "tier": "written", "tier_label": "رأي مكتوب",
  "amount": 500.0, "currency": "EGP", "expert_amount": 300.0,
  "paid_at": "ISO", "claim_deadline_at": "ISO", "hours_left": 9.5,
  "assigned_to": "x@y", "assigned_name": "…", "assigned_at": "ISO", "assign_overdue": true,
  "expert_email": null, "expert_name": "", "writing_due_at": null,
  "declined": [{"email": "a@b", "at": "ISO", "reason": "…"}],
  "client_first_name": "منى", "counterparty_name": "شركة النور للعقارات",
  "price_flags": ["country_mismatch", "phone_ambiguous"],
  "followup": null, "dispute": null,
  "candidates": [{"email": "e@x", "name": "…", "declined": false, "same_country": true}]
}]}
```
- `candidates` فيها حاجة بس لو الحالة في `PRE_CLAIM + EXPERT_WORK` (يعني `waiting` و`late`)؛ في `disputed` = `[]`.
- `hours_left` = ساعات لحد `claim_deadline_at` (≥ ٠، رقم عشري واحد). `assign_overdue` = `assigned` و`assign_alert_at` (التوزيع + ١٢ ساعة) عدّى.
- `dispute` (في `disputed`) = `{"reason": "unclear|not_answered|wrong_facts", "note": "…", "at": "ISO"}`.

### ٤-ب `GET /api/bridge/expert-files/{id}` ⇒ `bridge_view(f, full=True)`
الملف كله ما عدا `_id` (بما فيه `client_email` · `facts[]` · `questions[]` · `opinion` · `revision` · `dispute` · `file_no` · `declined` · `previous_experts` …) +
`law_label` · `status_label` · `docs: [{id, name, content_type, size, stage, created_at …}]` (من غير بايتات) · `client_name` · `expert_name` · `assigned_name` ·
`money: {consultation_id, status, escrow_state, held_at, delivered_at, auto_release_at, payment_id, on_platform}` (أو `null`).
- `opinion` = `{answers: [{question_id, question, text}], next_step: "self|specialist|none", next_step_note, based_on, expert_name, law_line, approved_at}`.
- `revision` = `{answers: [{question_id, question, text}], next_step, next_step_note, submitted_at}` أو `null` (الخبير يقدر يعدّل مرة واحدة وقت النزاع).
- ٤٠٤ `{"detail": "الملف ده مش موجود"}` لو مش موجود.

### ٤-ج الكتابات — كلها بترجّع `bridge_view` بعد الفعل (نفس ٤-ب)

| المسار | الجسم | من حالة | رسايل الرفض (`detail`) |
|---|---|---|---|
| `POST …/assign` | `{expert_email ≤200, note ≤1000}` | `awaiting_assignment` أو `assigned` (والمختار الجديد ≠ القديم؛ لو نفسه ⇒ ٢٠٠ من غير تغيير) | ٤٠٩ «الملف ده مش مستني توزيع» · ٤٢٢ «الخبير غير موجود أو غير معتمد» (إيميل فاضي) · ٤٠٩ «ما ينفعش تبعته للحساب ده» (العميل/بريد المنصة) · ٤٠٤ «الخبير غير موجود أو غير معتمد» · ٤٠٩ «فات ميعاد استلام الملف» · ٤٠٩ «الملف اتغيّر — حدّث الصفحة» · ٤٠٤ «الملف ده مش موجود» |
| `POST …/reassign` | `{expert_email, note}` | `claimed` · `writing` · `needs_info` | ٤٠٩ «الملف ده مش عند خبير دلوقتي» · ٤٠٩ «الملف عند الخبير ده أصلًا» · ٤٠٩ «الفلوس اتحرّكت على الملف ده — حدّث الصفحة» · ٤٠٩ «الملف اتغيّر — حدّث الصفحة» + رسايل الخبير اللي فوق |
| `POST …/refund` | `{note ≤1000}` | أي حالة قبل التسليم (`awaiting_assignment` · `assigned` · `claimed` · `writing` · `needs_info`) والاستشارة `held` | ٤٠٩ «الاسترداد من هنا قبل تسليم الرأي بس» · ٤٠٩ «الفلوس رجعت من بوابة الدفع قبل كده» · ٤٠٩ «الفلوس رجعت يدوي قبل كده» · ٤٠٩ «الفلوس اتحرّكت على الملف ده — حدّث الصفحة» |
| `POST …/resolve` | `{action: release\|refund, note ≤2000}` | `disputed` | ٤٠٩ «الملف ده مفيهوش ملاحظة مستنية قرار» · ٤٠٩ «الملف ما اتسلّمش لخبير — اختار رجّع الفلوس» · ٤٠٩ "Already refunded manually" · ٤٠٩ "Already refunded by the payment gateway" · ٤٠٩ "Only a disputed consultation can be resolved" · ٤٠٤ "Consultation not found" |

**إيه اللي بيحصل على المنصة (عشان نصوص التأكيد تبقى صادقة):**
- `assign`: الملف `assigned` + ميعاد تنبيه ١٢ ساعة جديد · جرس + إيميل للخبير الجديد · جرس «الملف اتنقل» للقديم لو فيه · سطر `audit_log` (`by: "dashboard"`). ⛔ مفيش فلوس بتتحرك. **الملاحظة ما بتوصلش للخبير** (بتتكتب في السجل بس).
- `reassign`: الفلوس المحجوزة ترجع على بريد المنصة (`held`) · الملف `assigned` للجديد بميعاد استلام **جديد = دلوقتي + ٤٨ ساعة** · مسودة القديم بتتحفظ في `previous_experts` · «الملف اتنقل» للقديم + جرس/إيميل للجديد.
- `refund`: المبلغ **كله** يرجع **لمحفظة العميل على المنصة** (`credit_wallet`) · الملف `refunded` · جرس + إيميل للعميل «رجّعنا فلوسك — المبلغ كامل في محفظتك» · جرس للخبير لو كان استلم «الملف اتقفل — رجّعنا للعميل فلوسه».
- `resolve release`: الاستشارة `released` ⇒ **أجر الخبير** (`expert_amount`) يتحوّل لمحفظته والباقي للمنصة · الملف `closed` (`closed_by: founder_release`) · جرس للعميل «خلّصنا مراجعة ملاحظتك» وللخبير «أجرك اتحوّل».
- `resolve refund`: المبلغ **كله** لمحفظة العميل · الملف `refunded` (`refund_reason: dispute`) · رمز التحقق بيتلغي.

### ٤-د `GET /api/bridge/consultations?status=disputed`
```json
{"status": "disputed", "count": 1, "total": 1, "consultations": [{
  "id": "…", "title": "…", "kind": "consultation|session|expert_opinion|verification|verify|documented_opinion|expert_file",
  "amount": 750, "currency": "EGP", "expert_amount": 600, "platform_fee": 150,
  "member_email": "…", "expert_email": "…", "client_first_name": "…", "expert_name": "…",
  "status": "disputed", "disputed_from": "held|delivered", "dispute_reason": "نص حرّ",
  "disputed_at": "ISO", "held_at": "ISO", "delivered_at": "ISO|\"\"", "payment_id": "…",
  "cancel_requested": false, "cancel_full_refund": false, "manual_refund_settled_at": "ISO|\"\"",
  "verified_by_email": "…|\"\"", "expert_file_id": "uuid|null", "created_at": "ISO"
}]}
```
مترتبين بـ`created_at` ↑، حدّ ٥٠٠. `status` غير `disputed` ⇒ ٤٢٢.

### ٤-هـ `POST /api/bridge/consultations/{id}/resolve` — `{action: release|refund, note ≤2000}`
بينادي `resolve_disputed` (نفس دالة الأدمن): من `disputed` بس، محروسة (ضغطتين ⇒ مرة واحدة والتانية ٤٠٩). `release` ⇒ نصيب الخبير لمحفظته (`expert_amount`)؛ لو `توثيق` وفلوسه على بريد المنصة ⇒ بتتحوّل للي وثّق فعلًا (`verified_by_email`). `refund` ⇒ المبلغ كله لمحفظة العميل (مرفوض لو اترجع يدوي أو من البوابة). الرد = `_serialize`: `{id, request_id, offer_id, kind, title, source_question, segment, member_email, expert_email, expert_name, client_first_name, amount, platform_fee, expert_amount, currency, status, escrow{…}, created_at, updated_at}`. الرفض: نفس الرسايل الإنجليزي اللي في ٤-ج + ٤٠٩ «الملف ما اتسلّمش لخبير — اختار رجّع الفلوس».

### ٤-و `GET /api/bridge/ops/queue` (موجود ومقروء بالفعل في `/api/platform-ops-queue`) — المفاتيح الجديدة
- المفتاح مفتوح: `expert_files_waiting` · `expert_files_late` · `expert_files_disputed` · `expert_files_open_total` · `expert_files_unactivated` · `expert_files_awaiting_payment` (كلهم أرقام صحيحة مسطّحة).
- المفتاح مقفول: `expert_files_open_total` · `expert_files_unactivated` · `expert_files_awaiting_payment` بس.
- سطور `alerts[]` (بتتطبع حرفيًا): «📁 {n} ملف مستني خبير» · «⚠️ {n} رأي متأخر» · «🛑 {n} ملف فيه ملاحظة مستنية قرارك» · «⚠️ {n} ملف اتدفع وما وصلش لقايمة التوزيع — راجعه من الداشبورد» · (مقفول) «⚠️ {n} ملف مدفوع والميزة مقفولة — افتح المفتاح أو رجّع الفلوس».

---

## ٥ — `dashboard-cloud/dashboard-api.js`

### ٥-أ جوه `LOADERS.inbox` — ٤ مهامّ جديدة (بعد «طلبات التوثيق»)
```js
if (String(EP.role || "").trim().toLowerCase() === "admin") {   // د٥ — الموظف ما بيشوفش فلوس الملفات
  [["waiting", "ملفات مستنية خبير"], ["late", "آراء متأخرة"], ["disputed", "نزاعات الملفات"]].forEach(function (L) {
    jobs.push(get("/platform-expert-files?status=" + L[0]).then(function (r) {
      if (!r || r.enabled === false) { efEnabled = false; return; }
      if ((r.total || 0) > (r.files || []).length) truncated.push(L[1] + ": معروض " + r.files.length + " من " + r.total);
      (r.files || []).forEach(function (f) { realRows.push(L[0] === "disputed" ? efDisputeRow(f) : efFileRow(f, L[0])); });
    }).catch(failUnless403(L[1])));
  });
  jobs.push(get("/platform-consultation-disputes").then(function (r) {
    if (!r || r.enabled === false) return;
    consDisputes = r.consultations || [];
  }).catch(failUnless403("نزاعات الاستشارات")));
}
```
- بعد `Promise.all` (قبل `EP.data.inbox = realRows`): `consDisputes.forEach(c => { if (c.expert_file_id && efEnabled) return; realRows.push(consDisputeRow(c)); })` — د٨.
- `failUnless403(label)` = `function (e) { if (e && e.status === 403) return; fail(label)(); }`.
- بعد أي فعل: `EP.reload("inbox", after)` **و** `EP.reload("opsQueue")` (العدّادات تتحدّث).

### ٥-ب شكل الصفوف (حقول الوارد الموجودة + حقول جديدة اختيارية)
حقول جديدة بيقراها `renderInbox`/`drawInbox`: `sub` (سطر تاني نص عادي) · `badges: [{t, tip}]` · `amountLabel` (يتعرض في العمود الأوسط بدل «← الوجهة» لو موجود) · `searchText` · `ef` (صفّ الجسر الخام) · `dsrc` (`file`\|`consultation`).

**صفّ ملف (`efFileRow(f, lane)`):**
| الحقل | القيمة |
|---|---|
| `apiKind` / `apiId` | `"expert_file"` / `f.id` |
| `efLane` | `"waiting"` أو `"late"` |
| `out` | §٧ «عنوان الصفّ» (بالترتيب: متأخر ⇐ الميعاد عدّى ⇐ ما اتستلمش ١٢ ساعة ⇐ اعتذر ⇐ مستني خبير) |
| `from` / `src` / `dest` | `"ملف للخبير"` / `"doc"` / `"inbox"` |
| `triage` | `"late"` لو `lane==="late"` أو `hours_left<=0`؛ وإلا `"human"` |
| `sla` / `slaWarn` | §٧ «سطر المهلة» / `hours_left <= 12` أو `assign_overdue` أو `lane==="late"` |
| `who` | `f.client_first_name \|\| "عميل"` |
| `sub` | `f.title + " · " + f.law_label + " · " + f.tier_label` |
| `amountLabel` | `efMoney(f.amount, f.currency)` |
| `note` | «أجر الخبير {efMoney(expert_amount)} · الطرف التاني: {counterparty_name \|\| "ما اتكتبش"}» |
| `badges` | `country_mismatch` ⇒ `{t:"⚠️ البلد مختلف", tip:"بلد تسجيل العميل مختلف عن بلد رقم تليفونه"}` · `phone_ambiguous` ⇒ `{t:"⚠️ الرقم مش واضح", tip:"الرقم مكتوب من غير كود البلد، فاتحسب بالسعر العام"}` · `declined.length` ⇒ `{t:"اعتذر " + n, tip: أسماء المعتذرين}` |
| `ref` | `"EF-" + f.id.slice(0, 8)` (للبحث بس) |
| `searchText` | `title + counterparty_name + assigned_name + expert_name + client_first_name` |
| `candidates` | `f.candidates` |

**صفّ نزاع ملف (`efDisputeRow(f)`):** `apiKind:"dispute"`, `dsrc:"file"`, `apiId:f.id`, `out:"«عندي مشكلة» على ملف"`, `from:"ملف للخبير"`, `src:"scale"`, `dest:"inbox"`, `triage:"human"`, `sla:"الفلوس واقفة لحد قرارك · " + relTime(f.dispute.at)`, `slaWarn:false`, `who: client_first_name`, `sub: title + " · الخبير: " + expert_name`, `amountLabel`, `note: REASON_AR[f.dispute.reason] + (f.dispute.note ? " — " + f.dispute.note : "")`, `ref:"DSP-"+id.slice(0,8)`.

**صفّ نزاع استشارة (`consDisputeRow(c)`):** `apiKind:"dispute"`, `dsrc:"consultation"`, `apiId:c.id`, `out: "نزاع على " + KIND_AR(c.kind)`, `from:"الاستشارات"`, `src:"scale"`, `sub: c.title + " · الخبير: " + (c.expert_name || "—")`, `note: c.dispute_reason || "ما اتكتبش سبب"`, `sla: "الفلوس واقفة لحد قرارك · " + relTime(c.disputed_at)`, `amountLabel`, `badges`: `manual_refund_settled_at` ⇒ «اترجعت يدوي قبل كده» · `cancel_requested` ⇒ «العميل كان طالب يلغي».

**جداول ثابتة (نسخة من المنصة — ⛔ ولا قيمة جديدة):**
```js
var REASON_AR = { unclear: "فيه حاجة مش فاهمها", not_answered: "الرأي ما ردّش على سؤالي", wrong_facts: "فيه غلط في الوقائع" };
var NEXT_STEP_AR = { self: "تقدر تكمّلها بنفسك", specialist: "محتاج حد متخصص يكمّل معاك", none: "مش محتاج حاجة دلوقتي" };
var CUR_AR = { EGP: "ج", SAR: "ر.س", AED: "درهم", KWD: "د.ك", QAR: "ر.ق", BHD: "د.ب", OMR: "ر.ع", USD: "$" };
function efMoney(a, cur) { return (a == null || a === "") ? "—" : money(a) + " " + (CUR_AR[cur] || cur || ""); }
function KIND_AR(k) { k = String(k || ""); if (k === "expert_file") return "ملف للخبير"; if (k === "session") return "جلسة";
  if (["expert_opinion", "verification", "verify", "documented_opinion"].indexOf(k) > -1) return "توثيق رأي";
  if (k === "consultation") return "استشارة من السوق"; return "استشارة"; }
```
⛔ العملات ما بتتجمعش ولا بتتحوّل (نفس قاعدة P&L) — كل مبلغ بعملته.

### ٥-ج أفعال جديدة على `EP` (كلها بترجّع Promise بـ`true`/`false` عشان النافذة ترجّع الزرار لو فشل — نفس `EP.purgeUser`)
| الدالة | النداء | رسالة النجاح (toast) |
|---|---|---|
| `EP.expertFileDetail(id)` | `GET /platform-expert-files/<id>` ⇒ كاش `EP.data.efDetail[id]` | — |
| `EP.expertFileSend(i, email, name, note)` | `assigned`/`awaiting_assignment` ⇒ `POST …/assign` · `claimed`/`writing`/`needs_info` ⇒ `POST …/reassign` — `{expert_email, note}` | assign: «اتبعت لـ{name} ✓» · reassign: «الملف اتنقل لـ{name} ✓» |
| `EP.expertFileRefund(i, note)` | `POST …/refund` `{note, confirmed: true}` | «رجعت {المبلغ} لمحفظة {العميل} ✓» |
| `EP.disputeDecide(i, action, note)` | `dsrc==="file"` ⇒ `POST /platform-expert-files/<id>/resolve` · `"consultation"` ⇒ `POST /platform-consultation-disputes/<id>/resolve` — `{action, note, confirmed: true}` | release: «اتحوّل أجر {الخبير} ✓» · refund: «رجعت {المبلغ} لمحفظة {العميل} ✓» |

الفشل: `quietToast(e.message)` (الرسالة العربي اللي رجعت من الخادم). لو `e.data.no_reply` ⇒ نفس الرسالة + `EP.reload("inbox", after)` فورًا.

---

## ٦ — `dashboard-cloud/index.html`

### ٦-أ العدّادات (`opsQueueCounters` + `OPSQ_LANDINGS`)
سطور جديدة في `opsQueueCounters` (بعد «دفعات يدوية» — فلوس الأول):
```js
['ملفات مستنية خبير', n(Q.expert_files_waiting), 'inbox', 'expert_files_waiting'],
['آراء متأخرة', n(Q.expert_files_late), 'inbox', 'expert_files_late'],
['ملفات فيها «عندي مشكلة»', n(Q.expert_files_disputed), 'inbox', 'expert_files_disputed'],
['ملفات اتدفعت وما وصلتش للتوزيع', n(Q.expert_files_unactivated), null, 'expert_files_unactivated'],
```
```js
// OPSQ_LANDINGS
expert_files_waiting: function(){activeFilter='t:files';renderInbox();},
expert_files_late:    function(){activeFilter='t:files';renderInbox();},
expert_files_disputed:function(){activeFilter='t:disputes';renderInbox();},
```
- `applyNavCounts` بيكتب شارة «الوارد» من `INBOX.length` بعد الشرايح (بيكتب فوقها) ⇒ ما فيش عدّ مرتين.
- سطر «للعلم» في `opsQueuePanel` تحت الشرايح لو أي واحد > ٠: «للعلم: {awaiting_payment} ملف مستني الدفع · {open_total} ملف مفتوح إجمالًا» (لون `--muted`، مش قابل للضغط). الأرقام من الطابور كما هي.

### ٦-ب الفرز (`inboxType` + `renderInbox`)
```js
if(i.apiKind==='expert_file')return 'files';
if(i.apiKind==='dispute')return 'disputes';
```
(قبل `if(i.apiKind)return 'decisions'`). الشرايح بالترتيب: `[['files','ملفات للخبير','var(--human)'],['disputes','نزاعات','var(--conflict)'],['decisions',…],…]` — شريحة ما فيهاش صفوف ما تترسمش (زي الموجود).
- البحث: `(i.out+i.from+i.who+(i.serviceLabel||'')+(i.email||'')+(i.searchText||'')+MODULES_LOOKUP[i.dest].label).includes(q)`.
- رسم الصفّ: لو `i.sub` ⇒ `<div class="from">${esc(i.sub)}</div>`؛ لو `i.badges` ⇒ شارات بنفس شكل `lic` (`<span class="status" title="${esc(tip)}">…`)؛ لو `i.amountLabel` ⇒ العمود الأوسط `<div class="amt">${esc(i.amountLabel)}</div>` بدل `destwrap`.

### ٦-ج الدرج (`drawInbox`)
أول سطر بعد `const i=INBOX[selected]`: `if(i.apiKind==='expert_file'){drawExpertFile(el,i);return;} if(i.apiKind==='dispute'){drawDispute(el,i);return;}` — الدرج العام ما يتغيّرش.

### ٦-د `drawExpertFile(el, i)` — الحقول والأزرار
رأس: `k` = «ملف للخبير» · `h3` = العنوان. شرايط فوق (لو موجودة): أعلام السعر (§٧) · «فات ميعاد الاستلام» · «ما فيش خبير معتمد…».
الحقول (`field`/`lab`/`val` الموجودين): القانون · الدرجة · المبلغ (`bigamt` + «أجر الخبير …») · العميل · الطرف التاني (+ تلميح التعارض) · اتدفع · ميعاد الاستلام / ميعاد الرأي · اتبعت لـ (لو `assigned`) · الخبير (لو استلم) · اعتذروا (لو فيه).
| الحالة | الزرار الأساسي | التاني |
|---|---|---|
| `awaiting_assignment` و`hours_left > 0` و`candidates.length` | «ابعته لـ…» ⇒ `expertPickModal(i,'assign')` | «رجّع الفلوس» |
| `assigned` و`hours_left > 0` | «ابعته لحد تاني» ⇒ `expertPickModal(i,'assign')` | «رجّع الفلوس» |
| `hours_left <= 0` (قبل الاستلام) | — (سطر «ميعاد الاستلام عدّى…») | «رجّع الفلوس» |
| `late` (`claimed`/`writing`) | «ابعته لحد تاني» ⇒ `expertPickModal(i,'reassign')` | «رجّع الفلوس» |
| مفيش مرشّحين غير الحالي | — (سطر «ما فيش خبير معتمد تاني…») | «رجّع الفلوس» |

«رجّع الفلوس» ⇒ `moneyConfirmModal` بنصّ §٧ ⇒ `EP.expertFileRefund`.

### ٦-هـ `drawDispute(el, i)`
- رأس أحمر (`.dh` بخلفية `--conflict` زي نزاع الضمان) · `k` = «نزاع · ملف للخبير» / «نزاع · {KIND_AR}» · `h3` = العنوان.
- الحقول: المبلغ المتجمّد (`bigamt`) + «أجر الخبير …» · العميل · الخبير · السبب · ملاحظة العميل (ملف) · اتفتح · (استشارة) اتفتح قبل/بعد التسليم · (توثيق) «اللي وثّق» · شرايط: اترجعت يدوي / كان طالب يلغي.
- **ملف:** الدرج بينادي `EP.expertFileDetail(id)` أول ما يتفتح («…بنجيب الرأي»)، وبعدين بلوكين: «الرأي الأصلي» (أول ٢٨٠ حرف من أول إجابة + «الخطوة الجاية» + تاريخ الإرسال) و«تعديل الخبير» (نفس الشكل، أو «الخبير ما عدّلش لسه — يقدر يعدّل مرة واحدة»). زرار «قارن الرأيين» ⇒ `opinionsCompareModal`. وسطر ثابت: «القرار هنا على الفلوس بس — أنهي رأي يفضل هو الرسمي لسه هنتفق عليه.»
- **استشارة:** «الشغل اللي اتسلّم» مش متاح من الجسر (§١٤ بند ٨) ⇒ سطر: «تفاصيل الشغل اللي اتسلّم مش ظاهرة هنا — شوفها من المنصة.»
- الأزرار: «للخبير — حوّل أجره» (`btn-primary`) · «للعميل — رجّع فلوسه» (`btn-human`). كل واحد ⇒ `moneyConfirmModal` ⇒ `EP.disputeDecide`. «للعميل» مقفول (`disabled` + سبب) لو `manual_refund_settled_at`.

### ٦-و النوافذ (كلها `openModal` الموجود — ⛔ ولا `confirm()`/`alert()`/`prompt()`)
**`expertPickModal(i, mode)`** — راديو لكل مرشّح (من غير الخبير الحالي: `assigned_to` في `assign`، `expert_email` في `reassign`)، بترتيب المنصة، وجنب الاسم شارات «من نفس بلد القانون» / «اعتذر عن الملف ده قبل كده». سطر الطرف التاني فوق. في `reassign` شريط تحذير. خانة ملاحظة اختيارية. الزرار مقفول لحد ما حد يتختار، ونصّه بيتغيّر لـ«ابعته لـ{الاسم}»؛ أول ضغطة ⇒ `disabled` + «بيتبعت…» ⇒ نجاح: يقفل النافذة ويعيد التحميل؛ فشل: يرجّع الزرار وتظهر الرسالة جوه النافذة (`.note-ai` أحمر) مش بس toast.

**`moneyConfirmModal(o)`** — `o = {title, lead, rows:[[label, value]], warn, noteLabel, btn, busy, run(note) ⇒ Promise<bool>}`:
- `lead` بيتبني بـ`esc()` لكل قيمة (المبلغ والعملة والأسماء في `<b>`).
- جدول صغير: المبلغ · العملة · الطرف (اللي هياخد) · الملف/الاستشارة.
- الزرار: `btn-warn` لرجوع الفلوس، `btn-primary` للتحويل للخبير. أول ضغطة: `if(go.dataset.busy)return; go.dataset.busy='1'; go.disabled=true; go.textContent=o.busy;` + قفل الإغلاق بالضغط برّه النافذة وزرار ✕ طول ما هو شغّال. نجاح ⇒ `closeModal()`. فشل ⇒ يرجّع الزرار + الرسالة جوه النافذة.
- ⛔ ولا كتابة كلمة (زي «مسح») — التأكيد = قراية المبلغ والاسم + ضغطة واحدة على زرار اسمه فيه المبلغ.

**`opinionsCompareModal(f)`** — `.modal.wide` (٩٦٠px، عمودين؛ موبايل عمود واحد): عمود «الرأي الأصلي» وعمود «تعديل الخبير»، لكل سؤال: السؤال (`question`) والإجابة كاملة (`text`، `white-space:pre-wrap`، كله `esc()`)، وتحت: «الخطوة الجاية: {NEXT_STEP_AR}» + ملاحظتها. فوق: «سبب العميل: …» + ملاحظته. ⛔ ولا زرار حسم جوه النافذة دي (المقارنة قراية بس).

### ٦-ز «الضمان والنزاعات» ← تبويب «النزاعات» (`renderEsc`)
أول الجدول، لو فيه صفوف `apiKind==='dispute'` في `INBOX`: `policy` سطر: «نزاعات المنصة (على الملفات والاستشارات) بتتحسم من «الوارد» ← «نزاعات» ({n})» — بيدوس ⇒ `goOps('inbox', function(){activeFilter='t:disputes';renderInbox();})`.

### ٦-ح السجل (`AUDIT_LABEL`)
```js
'expert_file.assign':'توزيع ملف على خبير',
'expert_file.reassign':'نقل ملف لخبير تاني',
'expert_file.refund':'رجوع فلوس ملف',
'expert_file.resolve':'حسم «عندي مشكلة» على ملف',
'expert_file.no_reply':'فعل على ملف ما وصلش رده',
'consultation.resolve':'حسم نزاع استشارة',
'consultation.no_reply':'حسم نزاع ما وصلش رده'
```

---

## ٧ — النصوص بالحرف

**الشرايح والعناوين**
| المكان | النص |
|---|---|
| شريحة الفرز | «ملفات للخبير ({n})» · «نزاعات ({n})» |
| شرايح الطابور | «ملفات مستنية خبير» · «آراء متأخرة» · «ملفات فيها «عندي مشكلة»» · «ملفات اتدفعت وما وصلتش للتوزيع» (+ «· لا شاشة له بعد» الموجودة) |
| سطر للعلم | «للعلم: {a} ملف مستني الدفع · {o} ملف مفتوح إجمالًا» |
| سطر الضمان | «نزاعات المنصة (على الملفات والاستشارات) بتتحسم من «الوارد» ← «نزاعات» ({n})» |

**عنوان الصفّ (`out`)**
| الحالة | النص |
|---|---|
| `late` | «رأي متأخر» |
| قبل الاستلام و`hours_left <= 0` | «فات ميعاد الاستلام» |
| `assigned` و`assign_overdue` | «ملف ما اتستلمش من ١٢ ساعة» |
| `awaiting_assignment` و`declined.length` | «خبير اعتذر — الملف مستني خبير تاني» |
| `assigned` (عادي) | «ملف مستني الخبير يستلمه» |
| `awaiting_assignment` (عادي) | «ملف مستني خبير» |
| نزاع ملف | ««عندي مشكلة» على ملف» |
| نزاع استشارة | «نزاع على {استشارة من السوق \| جلسة \| توثيق رأي \| ملف للخبير \| استشارة}» |

**سطر المهلة (`sla`)**
| الحالة | النص |
|---|---|
| قبل الاستلام، `hours_left > 0` | «فاضل {h} ساعة وفلوسه ترجع لوحدها» (`h` = `Math.floor(hours_left)` بأرقام عربي؛ أقل من ١ ⇒ «فاضل أقل من ساعة وفلوسه ترجع لوحدها») |
| قبل الاستلام، `hours_left <= 0` | «الميعاد عدّى — لو الفلوس ما رجعتش لوحدها رجّعها من هنا» |
| `late` | «ميعاد الرأي عدّى {relTime(writing_due_at)}» |
| نزاع | «الفلوس واقفة لحد قرارك · {relTime(at)}» |

**الدرج — العناوين (`lab`) والقيم**
| `lab` | القيمة |
|---|---|
| «القانون» | `law_label` |
| «الدرجة» | `tier_label` |
| «المبلغ» | `{efMoney(amount)}` كبير + تحته «أجر الخبير {efMoney(expert_amount)}» |
| «العميل» | `client_first_name` |
| «الطرف التاني» | `counterparty_name` أو «ما اتكتبش» + تحته صغير «اتأكد إن الخبير اللي هتختاره مالوش علاقة بيه» |
| «اتدفع» | `relTime(paid_at)` |
| «ميعاد الاستلام» | «فاضل {h} ساعة» / «عدّى» |
| «اتبعت لـ» | «{assigned_name} · {relTime(assigned_at)}» + (لو `assign_overdue`) «— ما استلمش من ١٢ ساعة» |
| «الخبير» | `expert_name` |
| «ميعاد الرأي» | `arDate(writing_due_at)` + «— عدّى» |
| «اعتذروا» | سطر لكل واحد: «{الاسم من candidates أو الإيميل} — {reason \|\| "من غير سبب"}» |
| «السبب» (نزاع) | `REASON_AR[reason]` (ملف) / `dispute_reason` (استشارة) |
| «ملاحظة العميل» | `dispute.note` أو «ما كتبش ملاحظة» |
| «اتفتح» | `relTime(dispute.at \|\| disputed_at)` |
| «قبل ولا بعد التسليم» (استشارة) | `disputed_from==="delivered"` ⇒ «بعد ما الشغل اتسلّم» · `"held"` ⇒ «قبل ما الشغل يتسلّم» |
| «اللي وثّق» (توثيق) | `verified_by_email` |
| «الرأي الأصلي» | معاينة + «اتبعت {arDate(approved_at)}» |
| «تعديل الخبير» | معاينة + «اتبعت {arDate(submitted_at)}» / «الخبير ما عدّلش لسه — يقدر يعدّل مرة واحدة» |

**شرايط الدرج**
- `country_mismatch`: «بلد تسجيل العميل مختلف عن بلد رقم تليفونه — السعر اتحسب على بلد الرقم. بُصّ عليه قبل ما تبعته.»
- `phone_ambiguous`: «رقم تليفون العميل مكتوب من غير كود البلد، فالسعر اتحسب بالسعر العام.»
- فات الميعاد: «ميعاد الاستلام عدّى، فمش هينفع يتبعت لخبير. لو الفلوس ما رجعتش لوحدها، رجّعها من هنا.»
- مفيش مرشّحين: «ما فيش خبير معتمد تاني تقدر تبعتله الملف ده دلوقتي.»
- نزاع — سطر الرأي الرسمي: «القرار هنا على الفلوس بس — أنهي رأي يفضل هو الرسمي لسه هنتفق عليه.»
- نزاع استشارة: «تفاصيل الشغل اللي اتسلّم مش ظاهرة هنا — شوفها من المنصة.»
- اترجعت يدوي: «الفلوس دي رجعت للعميل يدوي قبل كده — «رجّع فلوسه» مقفول.»
- كان طالب يلغي: «العميل كان طالب يلغي الحجز ده.»

**الأزرار**
«ابعته لـ…» · «ابعته لحد تاني» · «رجّع الفلوس» · «قارن الرأيين» · «للخبير — حوّل أجره» · «للعميل — رجّع فلوسه» · «إغلاق» · «رجوع».

**نافذة اختيار الخبير**
- العنوان: «ابعت «{title}» لـ…» (`reassign`: «انقل «{title}» لخبير تاني»).
- فوق القايمة: «الطرف التاني في الملف: {counterparty_name \|\| "ما اتكتبش"} — اتأكد إن الخبير اللي هتختاره مالوش علاقة بيه.»
- شارات: «من نفس بلد القانون» · «اعتذر عن الملف ده قبل كده».
- `reassign` (شريط تحذير): «الملف هيتشال من {expert_name} ومسودته هتتحفظ عندنا. اللي هتختاره قدامه ٤٨ ساعة يستلمه، والفلوس فاضلة محجوزة.»
- خانة: «ملاحظة لينا (اختياري — ما بتوصلش للخبير)».
- الزرار: «اختار خبير الأول» (مقفول) ⇒ «ابعته لـ{name}» ⇒ أثناء التنفيذ «بيتبعت…».

**نافذة رجوع فلوس ملف (`refund`)**
- العنوان: «ترجّع الفلوس؟»
- النص: «هترجّع **{efMoney(amount)}** كاملين لمحفظة **{client_first_name}** على المنصة، عن ملف «{title}».»
- لو فيه خبير (`expert_name` أو `assigned_name`): «والملف هيتقفل عند **{الاسم}** ومش هياخد أجر.»
- سطر أخير: «الخطوة دي ما ينفعش ترجع فيها.»
- الجدول: «المبلغ» `money(amount)` · «العملة» `CUR_AR[currency]` (+ الكود الصغير: `EGP`) · «هيروح لـ» «محفظة {client_first_name}» · «الملف» `title`.
- خانة: «ملاحظة لينا (اختياري)».
- الزرار: «رجّع {efMoney(amount)}» ⇒ «بيرجع…».

**نافذة حسم نزاع — للخبير (`release`)**
- العنوان: «تحوّل الأجر للخبير؟»
- النص: «هتحوّل أجر **{efMoney(expert_amount)}** لمحفظة **{expert_name}**، والباقي من **{efMoney(amount)}** للمنصة. **{client_first_name}** مش هياخد فلوس، والملف هيتقفل.» (استشارة: «والاستشارة هتتقفل»؛ لو `expert_amount` فاضي: «هتحوّل نصيب الخبير لمحفظة **{expert_name}** من **{efMoney(amount)}** — المنصة هي اللي بتحسبه.»؛ توثيق فيه `verified_by_email` مختلف عن `expert_email`: سطر زيادة «ولو الفلوس كانت لسه باسم المنصة، بتروح للي وثّق (**{verified_by_email}**).» — لأن `_judge_takes_platform_dispute` بيحوّلها للي وثّق لما تكون على بريد المنصة بس، والداشبورد ما يعرفش بريد المنصة — §١٤ بند ١٢.)
- الزرار: «حوّل {efMoney(expert_amount)} لـ{expert_name}» ⇒ «بيتحوّل…».

**نافذة حسم نزاع — للعميل (`refund`)**
- العنوان: «ترجّع الفلوس للعميل؟»
- النص: «هترجّع **{efMoney(amount)}** كاملين لمحفظة **{client_first_name}** على المنصة، و**{expert_name}** مش هياخد أجر. الخطوة دي ما ينفعش ترجع فيها.»
- الزرار: «رجّع {efMoney(amount)} لـ{client_first_name}» ⇒ «بيرجع…».
- خانة الملاحظة في النافذتين: ملف ⇒ «ملاحظة لينا (اختياري)» · استشارة ⇒ «ملاحظة (اختياري) — بتتحفظ مع القرار، فاكتبها كأن الطرفين ممكن يقروها» (§١٤ بند ٩).

**نافذة المقارنة**
العنوان «الرأيين جنب بعض» · العمودين «الرأي الأصلي» و«تعديل الخبير» · «الخطوة الجاية: …» · لو مفيش تعديل: «الخبير ما عدّلش لسه».

**رسايل النجاح (toast)** — §٥-ج. **رسايل الفشل** — اللي راجع من الخادم بالحرف (§٣ + §٤-ج)، ومنها المحلية: «اختار خبير الأول» · «اختار: للخبير ولا للعميل» · «لازم تأكّد الأول من الشاشة» · «الملف ده مش موجود» · «النزاع ده مش موجود» · «ما وصلناش رد من المنصة — حدّث الصفحة وشوف حصل إيه قبل ما تضغط تاني».

⛔ ولا كلمة تقنية ظاهرة: ولا «جسر» ولا «API» ولا «escrow» ولا «status» ولا أكواد الحالات. الإيميل يظهر بس كبديل لاسم خبير معتذر مش معتمد، و«اللي وثّق».

---

## ٨ — الصلاحيات

- التمانية مسارات: `@token_required` ثم `@roles_required('admin')` — نفس `role_grants` (الدور الفعلي `dashboard_role`، و`role` المختلف بيقلّل بس). `employee`/`trainer`/`investor`/`viewer`/`pending` ⇒ ٤٠٣ **من غير أي نداء للمنصة** ومن غير سطر سجل. من غير توكن ⇒ ٤٠١.
- المتصفح: المهامّ الجديدة جوه محمّل الوارد بتتعمل لـ`EP.role === 'admin'` بس؛ و٤٠٣ ما يتسجّلش في `INBOX_FAILED`.
- ⛔ السرّ (`METRICS_SECRET`) في رأس الطلب للمنصة بس — اختبار إنه مش في أي رد.

## ٩ — السجل (`_audit`)

بعد `_resp_ok(resp)` بس (فعل اترفض ما يتسجّلش — نفس `test_a_failed_mutation_is_never_audited`). الفاعل = `g.user.email` (افتراض `_audit`). الأرقام **من رد المنصة**:
```python
def _ef_meta(f, **extra):
    m = {k: f.get(k) for k in ('title', 'status', 'amount', 'currency', 'expert_amount',
                                'assigned_to', 'expert_email') if f.get(k) is not None}
    m.update({k: v for k, v in extra.items() if v not in (None, '')})
    return m
```
| الفعل | `target` | `meta` |
|---|---|---|
| `expert_file.assign` | `file_id` | `_ef_meta(resp, note=…)` (فيه `assigned_to` الجديد) |
| `expert_file.reassign` | `file_id` | `_ef_meta(resp, note=…, previous_expert=resp['previous_experts'][-1]['email'])` |
| `expert_file.refund` | `file_id` | `_ef_meta(resp, note=…)` |
| `expert_file.resolve` | `file_id` | `_ef_meta(resp, action=…, note=…)` |
| `consultation.resolve` | `consultation_id` | `{action, kind, amount, currency, expert_amount, status, expert_email, note}` من `_serialize` |
| `expert_file.no_reply` / `consultation.no_reply` | الـid | `{attempt: assign\|reassign\|refund\|resolve, action?}` |

المنصة كمان بتكتب سطرها (`audit_log`، `by: "dashboard"`) — الإسناد بالاسم عندنا بس (§١٤ بند ٥).

---

## ١٠ — الاختبارات (المنصة متزيّفة — ولا طلب حقيقي)

### ١٠-أ `backend/tests/test_expert_files_dashboard.py` (بنفس نمط `test_platform_ops_proxies.py`)
- fixture `calls`: `monkeypatch.setattr(appmod.requests, 'request', _fake)` + `PLATFORM_METRICS_SECRET='test-metrics-secret'`؛ `_fake` بيرد من جدول `{(method, bridge_path): FakeResp(status, payload)}`، وأي URL مش في الجدول ⇒ `AssertionError` (مش ٤٠٤ ساكت). الحمولات منسوخة بشكل §٤ بالحرف.
- الاختبارات:
  1. `test_list_forwards_status_and_defaults_to_waiting` — `status=late` يعدّي؛ فاضي/`all`/`xyz` ⇒ `waiting`.
  2. `test_list_payload_is_verbatim_plus_enabled` — الرد = حمولة المنصة + `enabled: True`.
  3. `test_feature_off_404_is_enabled_false_not_a_failure` (م١ و م٧) — ٢٠٠، `files == []`.
  4. `test_real_platform_error_passes_through` — ٥٠٠ يفضل ٥٠٠ ومن غير `enabled`.
  5. `test_every_route_is_admin_only` — مصفوفة (٨ مسارات × `employee/trainer/investor/viewer/pending`) ⇒ ٤٠٣ و`calls == []`؛ ومن غير توكن ⇒ ٤٠١.
  6. `test_secret_in_header_never_in_body` — لكل مسار.
  7. `test_assign_sends_exactly_the_bridge_model_and_audits` — الجسم `{'expert_email': 'e@x.test', 'note': 'ن'}` (الإيميل lower/strip)، ومفيش مفاتيح زيادة؛ سطر `('expert_file.assign', 'admin@…')` و`meta.assigned_to`.
  8. `test_reassign_goes_to_reassign_and_records_previous_expert`.
  9. `test_bad_expert_email_is_refused_locally` — ٤٠٠ «اختار خبير الأول»، `calls == []`، ولا سجل.
  10. `test_refund_without_confirmed_is_refused_locally` — `{}` و`{'confirmed': 'true'}` ⇒ ٤٠٠، `calls == []`.
  11. `test_refund_forwards_note_only_and_audits_platform_amounts` — الجسم للمنصة `{'note': …}` بس؛ `meta.amount/currency` من رد المنصة حتى لو المتصفح بعت مبلغ تاني.
  12. `test_resolve_validates_action` — `split` ⇒ ٤٠٠.
  13. `test_resolve_forwards_action_and_note` (ملف واستشارة).
  14. `test_english_resolve_errors_reach_the_founder_in_arabic` — ٤٠٩ "Already refunded by the payment gateway" ⇒ «الفلوس دي رجعت للعميل من بوابة الدفع قبل كده».
  15. `test_arabic_platform_errors_pass_verbatim` — ٤٠٩ «فات ميعاد استلام الملف».
  16. `test_a_rejected_write_is_never_audited` — ٤٠٩ ⇒ مفيش `expert_file.*`.
  17. `test_no_reply_on_a_money_write_is_said_and_logged` — `_fake` بيرمي `requests.Timeout` ⇒ ٥٠٢، `no_reply: True`، سطر `expert_file.no_reply`.
  18. `test_ids_are_validated_before_the_url_is_built` — `../x` / `a%2Fb` / ٦٥ حرف ⇒ ٤٠٤، `calls == []`.
  19. `test_writes_use_the_long_timeout` — `timeout >= 25` في الكتابات.
  20. `test_consultation_disputes_list_asks_for_disputed_only` — `params == {'status': 'disputed'}`.
  21. `test_detail_not_found_feature_off_message` — ٤٠٤ `Not Found` ⇒ «خدمة «ملف للخبير» مقفولة على المنصة دلوقتي».

### ١٠-ب `backend/tests/test_expert_files_ui_static.py` (قراية الملفات زي `test_dash_ia_structure.py`)
- `test_menu_did_not_grow` — نفس عدّ `MODULES` بـ`grp` (١٢ + ٤ مثبّتة) — ⛔ ولا عنصر جديد.
- `test_inbox_types_files_and_disputes_exist` — `inboxType` فيه `'files'` و`'disputes'`، وشرايحهم في `renderInbox`.
- `test_queue_counters_read_the_real_keys` — `expert_files_waiting` · `expert_files_late` · `expert_files_disputed` · `expert_files_unactivated` موجودين، و⛔ `expert_files_awaiting_assignment` مش موجود.
- `test_no_browser_dialogs_in_the_new_code` — جوه `drawExpertFile` · `drawDispute` · `expertPickModal` · `moneyConfirmModal` · `opinionsCompareModal` · `EP.expertFile*` · `EP.disputeDecide`: ولا `confirm(` ولا `prompt(` ولا `alert(`.
- `test_money_calls_send_confirmed_true` — `EP.expertFileRefund` و`EP.disputeDecide` فيهم `confirmed: true`.
- `test_audit_labels_cover_the_new_actions` — السبع مفاتيح في `AUDIT_LABEL`.
- `test_no_official_opinion_choice` — ولا نص «الرأي الرسمي هو» / «اعتمد التعديل» / «اعتمد الأصلي» في الملفين.
- `test_no_tech_words_in_new_visible_strings` — النصوص الجديدة في §٧ ما فيهاش `API` · `bridge` · `escrow` · `status` · `جسر`.

### ١٠-ج `backend/tests/test_expert_files_ui.py` (Playwright — بيتخطّى لو مش متاح)
بيستعمل نفس أداة §١١ (`tests/uiharness/ef_route_harness.py`) من غير منافذ:
- الصفوف الخمسة الأنواع بتترسم في «ملفات للخبير»، والنزاعين في «نزاعات»، ونزاع الملف ما يتكررش من قايمة الاستشارات (د٨).
- نافذة الرجوع فيها المبلغ «٥٠٠ ج» واسم العميل والعنوان قبل أي طلب `POST`.
- **ضغطتين ورا بعض** على زرار الرجوع ⇒ `POST …/refund` **مرة واحدة** (عدّاد في المنصة المزيّفة).
- بعد النجاح الصفّ يختفي (المنصة المزيّفة بتشيله من `waiting`) والشريحة تقل.
- `employee`: ولا طلب لمسارات الملفات، ولا شريط «تعذّر».
- **صفر طلبات حقيقية:** لستة `blocked` (أي أصل غير `https://dash.test`) ما فيهاش غير خطوط جوجل (اتقفلت قبل ما تطلع)، و`requests` جوه العملية ما نادتش غير `https://platform.test`.

**ملاحظة تشغيل:** جوه صندوق الأوامر (sandbox) اختبارات الواجهة القديمة اللي بتفتح منافذ محلية بتقع بـ`PermissionError: [Errno 1] Operation not permitted` (خط الأساس النهارده: ٦٤٧ ناجح · ١ فشل + ١٠٩ خطأ، **كلهم** من `bind` في `test_dash_ia_ui.py` و`test_dash_company_badges.py` و`test_dash_finance_sources.py`). الأداة الجديدة ما بتفتحش منافذ، بس Chromium نفسه بيموت جوه الصندوق (`SIGTRAP`) ⇒ تشغيل اختبار ١٠-ج والصور محتاج يتعمل برّه الصندوق (اتجرّب: بيشتغل، وأي أصل تاني بيتقفل ويتسجّل).

---

## ١١ — خطة الصور

**الأداة:** `backend/tests/uiharness/ef_route_harness.py` (مكتبة) + `backend/tests/uiharness/expert_files_shots.py <out_dir>` (السكربت).
1. قبل استيراد `app`: `DATABASE_URL=sqlite:///<tmp>` · `SECRET_KEY` قوي ثابت · `METRICS_SECRET='shots-secret'` · `PLATFORM_API_URL='https://platform.test'` · شيل كل `*_API_KEY` من البيئة.
2. بعد الاستيراد: `requests.request/get/post/put/delete` و`requests.Session.request` ⇒ `fake_platform(method, url, **kw)`: لو الأصل مش `https://platform.test` ⇒ `raise RuntimeError('طلب حقيقي ممنوع: ' + url)`. الردود من `ef_fixtures.py` (أشكال §٤ بالحرف) وفيها حالة: `refund`/`resolve`/`assign` بيعدّلوا القوايم (الصفّ يتشال أو يتنقل) عشان صورة «بعد» تبقى صادقة.
3. بذرة: أدمن `admin@local.test` + موظف `staff@local.test` في SQLite المؤقتة؛ توكن JWT بـ`app.config['SECRET_KEY']`.
4. Playwright (Chromium): `context.add_init_script("localStorage.setItem('token','<jwt>')")`، و`context.route('**/*', h)`:
   - `https://dash.test/api/...` ⇒ `app.test_client().open(path+query, method, headers={'Authorization':…, 'Content-Type':…}, data=post_data)` ⇒ `route.fulfill(status, content_type, body)`.
   - `https://dash.test/<file>` ⇒ الملف من `dashboard-cloud/` على الديسك (`/` ⇒ `index.html`).
   - أي أصل تاني ⇒ `route.abort()` + يتسجّل في `blocked`. آخر السكربت بيطبع `blocked` وبيفشل لو فيه أي أصل غير `fonts.googleapis.com`/`fonts.gstatic.com`.
5. المقاسين: كمبيوتر `1440×900`، موبايل `390×844` (`device_scale_factor=2`، `is_mobile=True`).
6. المخرج: `/private/tmp/claude-501/-Users-abdelrhman/d79b8572-ab05-46cf-afc9-f78748c27839/scratchpad/r6-shots/`.

**البيانات المزيّفة (أسماء متخيّلة):**
| # | النوع | العنوان | القانون/الدرجة | المبلغ / الأجر | الحالة | ملاحظة |
|---|---|---|---|---|---|---|
| F1 | مستني | «إيجار شقة — المالك عايز يطلعني» | مصري · رأي مكتوب | ٥٠٠ ج / ٣٠٠ ج | `awaiting_assignment`، `hours_left=41.5` | طرف تاني «شركة النور للعقارات» · ٣ مرشّحين (٢ نفس البلد) |
| F2 | قرب ٤٨ | «فصل تعسفي بعد ٧ سنين» | مصري · رأي + جلسة | ١٬٠٠٠ ج / ٦٥٠ ج | `awaiting_assignment`، `hours_left=5.2` | `country_mismatch` |
| F3 | ١٢ ساعة | «شيك من غير رصيد» | مصري · رأي مكتوب | ٥٠٠ ج / ٣٠٠ ج | `assigned`، `assign_overdue=true` | اتبعت لـ«أ. هالة سمير» |
| F4 | اعتذر | «ميراث أرض زراعية» | مصري · رأي مكتوب | ٥٠٠ ج / ٣٠٠ ج | `awaiting_assignment`، `declined=[كريم]` | `phone_ambiguous` |
| F5 | متأخر | «عقد توريد مع مورد سعودي» | سعودي · رأي مكتوب | ٥٠٠ ر.س / ٣٠٠ ر.س | `writing`، `writing_due_at` من يوم | الخبير «م. سامي فؤاد» |
| D1 | نزاع ملف | «حضانة بعد الطلاق» | مصري · رأي مكتوب | ٥٠٠ ج / ٣٠٠ ج | `disputed`، `not_answered` + ملاحظة | `opinion` + `revision` |
| D2 | نزاع استشارة | «مراجعة عقد شراكة» | `consultation` | ٧٥٠ ج / ٦٠٠ ج | `disputed_from=delivered` | |
| D3 | نزاع توثيق | «هل الإنذار على يد محضر لازم؟» | `expert_opinion` | ٢٥٠ ج / ١٥٠ ج | `manual_refund_settled_at` | «للعميل» مقفول |
| D1′ | نفس D1 من قايمة الاستشارات | — | `expert_file_id` = D1 | | | لازم ما يظهرش (د٨) |

`ops/queue`: `expert_files_waiting=4` · `expert_files_late=1` · `expert_files_disputed=1` · `expert_files_unactivated=1` · `expert_files_awaiting_payment=3` · `expert_files_open_total=8` + سطور `alerts` الأربعة بالحرف.

**اللقطات:**
| الملف | المقاس | المحتوى |
|---|---|---|
| `01-queue-chips-desktop.png` | ١٤٤٠ | «كل اللي مستنيك» بالشرايح الأربعة + سطر للعلم + التنبيهات |
| `02-files-chip-desktop.png` | ١٤٤٠ | فرز «ملفات للخبير»: F1–F5 بشاراتهم ومهلهم |
| `03-drawer-waiting-desktop.png` | ١٤٤٠ | درج F2 (علم البلد + «فاضل ٥ ساعة») |
| `04-pick-expert-desktop.png` | ١٤٤٠ | نافذة «ابعت … لـ…» على F1 (مرشّح مختار) |
| `05-reassign-late-desktop.png` | ١٤٤٠ | نافذة النقل على F5 بشريط التحذير |
| `06-refund-confirm-desktop.png` | ١٤٤٠ | نافذة رجوع F3 («رجّع ٥٠٠ ج» + اسم العميل + «أ. هالة سمير») |
| `07-refund-busy-desktop.png` | ١٤٤٠ | نفس النافذة بعد الضغطة (الزرار «بيرجع…» مقفول) — المنصة المزيّفة بتأخّر الرد ٢ث |
| `08-after-refund-desktop.png` | ١٤٤٠ | الوارد بعد الرجوع: F3 اختفى + رسالة النجاح |
| `09-disputes-chip-desktop.png` | ١٤٤٠ | فرز «نزاعات»: D1 · D2 · D3 (ومفيش D1′) |
| `10-drawer-file-dispute-desktop.png` | ١٤٤٠ | درج D1 بالرأيين + سطر «القرار هنا على الفلوس بس…» |
| `11-compare-opinions-desktop.png` | ١٤٤٠ | نافذة المقارنة (عمودين) |
| `12-resolve-release-desktop.png` | ١٤٤٠ | تأكيد «حوّل ٣٠٠ ج لـ…» على D1 |
| `13-resolve-refund-consultation-desktop.png` | ١٤٤٠ | تأكيد «رجّع ٧٥٠ ج لـ…» على D2 |
| `14-manual-refunded-disabled-desktop.png` | ١٤٤٠ | درج D3 و«للعميل» مقفول بسببه |
| `15-escrow-pointer-desktop.png` | ١٤٤٠ | «الضمان والنزاعات» ← «النزاعات» بسطر التحويل |
| `16-audit-desktop.png` | ١٤٤٠ | «سجلّ العمليات» بعد الأفعال (التسميات العربي) |
| `17-feature-off-desktop.png` | ١٤٤٠ | المنصة بترد ٤٠٤ + الطابور مقفول بـ`open_total=2`: مفيش صفوف ولا «تعذّر»، والتنبيه ظاهر |
| `18-employee-desktop.png` | ١٤٤٠ | موظف على «الدورات»: ولا شريط «تعذّر» |
| `m01-files-chip-mobile.png` | ٣٩٠ | فرز «ملفات للخبير» |
| `m02-drawer-mobile.png` | ٣٩٠ | درج F1 تحت القايمة (بعد التمرير) |
| `m03-pick-expert-mobile.png` | ٣٩٠ | نافذة اختيار الخبير |
| `m04-refund-confirm-mobile.png` | ٣٩٠ | نافذة الرجوع |
| `m05-dispute-drawer-mobile.png` | ٣٩٠ | درج D1 |
| `m06-compare-opinions-mobile.png` | ٣٩٠ | المقارنة عمود واحد |

فحوص على الصور قبل الحكم: ولا تمرير أفقي في الموبايل (`document.documentElement.scrollWidth <= 390`) · كل زرار جوه الشاشة · الأرقام العربي ما اتبعترتش جنب رموز العملة (فخّ bidi المسجّل) · مفيش «undefined»/«null»/«NaN» في نص الصفحة.

---

## ١٢ — ترتيب التنفيذ (commits محلية `feat(expert-file): …`)
1. `app.py`: المساعدات (`_ef_bridge` · `_EF_ERRORS_AR` · `_ef_note` · `_ef_meta` · `_EF_ID_RE`) + م١–م٨ + `test_expert_files_dashboard.py` (§١٠-أ) — أخضر.
2. `dashboard-api.js`: مهامّ المحمّل + الصفوف + `EP.*` الجديدة.
3. `index.html`: الشرايح والعدّادات · الفرز والرسم · `drawExpertFile` · `drawDispute` · النوافذ التلاتة · سطر الضمان · `AUDIT_LABEL` + `test_expert_files_ui_static.py`.
4. أداة الصور + `ef_fixtures.py` + `test_expert_files_ui.py` + الصور + تصليحات من الصور.
5. سطر في `STATUS.md` (الجولة ٦ + قايمة الناقص في جسر المنصة).

---

## ١٣ — خارج الجولة دي
- بايتات المستندات في الداشبورد (بروكسي بايتات بسرّ — د١٣).
- طابور «عايز حد يكمّل معايا» (`status=followup`) — الجسر جاهز، الشاشة مش في المطلوب.
- **أنهي رأي يبقى الرسمي بعد الحسم** — قرار المؤسس (⏳).
- أي حاجة من قرارات SPEC §١٦ المفتوحة (استرداد آلي للتأخير · بلد السعر · مراجعة أول ملفات الخبير · الهيئة القضائية · الأسعار · تأكيد رقم التليفون · الجلسة اللي سقطت) — ⛔ ما تتنفّذش.
- رابط مباشر من تليجرام لشريحة بعينها (`dashboard_inbox_button` بيودّي الجذر = «الوارد»، وده كفاية).

---

## ١٤ — الناقص في جسر المنصة (ما اتعدّلش — للجولة اللي بعدها في ريبو المنصة)
1. **ملفات «اتدفعت وما وصلتش للتوزيع» ما لهاش قايمة ولا فعل.** `ops/queue` بيعدّها (`expert_files_unactivated`) وتليجرام بيقول «راجعه من الداشبورد» / «رجّع الفلوس من الداشبورد»، لكن `bridge_list_files` ما بيرجّعهاش (حالة الملف `awaiting_payment`، ومش في أي فلتر غير `all`)، و`bridge_refund` بيرفضها (٤٠٩ «الاسترداد من هنا قبل تسليم الرأي بس» — `awaiting_payment` مش في `BEFORE_DELIVERY`). المطلوب: `status=unactivated` (من `_unactivated_paid`) + استرداد ملف `awaiting_payment` استشارته `held`.
2. **أختام التخطّي مش في الصفّ ولا ليها فعل:** `refund_blocked_at` · `release_blocked_at` · `approval_blocked_at` · `file_activation_blocked_at` — رسايل الكنسة بتقول «سوّيه بإيدك من الداشبورد»، بس الصفّ ما فيهوش الختم، وملف `delivered` تحريره التلقائي اتوقف ما لوش فلتر ولا فعل (`resolve` بيقبل `disputed` بس).
3. **`ops/queue` ما بيعدّش نزاعات الاستشارات العادية** (`consultations.status=disputed`) — بس `expert_files_disputed`. نزاع على استشارة سوق/جلسة/توثيق ما لوش رقم ولا سطر في الدايجست.
4. **رسايل `resolve_disputed` بالإنجليزي** ("Only a disputed consultation can be resolved" · "Already refunded manually" · "Already refunded by the payment gateway" · "Consultation not found" · "action must be release or refund") وبتعدّي من الجسرين — الداشبورد بيترجمها مؤقتًا (`_EF_ERRORS_AR`).
5. **ما فيش `by` في أجسام الجسر** (`ExpertFileAssignBody` · `ExpertFileNoteBody` · `ExpertFileResolveBody` · `ConsultationResolveBody`) ⇒ `audit_log` على المنصة بيكتب `by: "dashboard"` بس (نفس ثغرة الإسناد اللي في STATUS بند ١). الإسناد بالاسم في سجل الداشبورد بس.
6. **صفّ القايمة ناقصه:** `file_no` (موجود بعد التسليم بس في `GET /{id}`) · `reason_label` للنزاع (الداشبورد بينسخ `REASON_LABELS`) · اسم الخبير المعتذر في `declined[]` (إيميل بس — الداشبورد بيكمّل من `candidates`) · `platform_fee`.
7. **«مقفول» و«مش منشور» نفس الرد** (`404 Not Found` قبل السرّ) — مقبول، بس الداشبورد ما يقدرش يفرق، ولو المفتاح اتقفل وفيه ملفات مفتوحة ما يقدرش يعرضها ولا يرجّع فلوسها (كل `/bridge/expert-files*` ٤٠٤) — العدّاد والتنبيه بس.
8. **نزاع الاستشارة العادية من غير «الشغل اللي اتسلّم»:** `bridge_list_consultations` ما فيهوش الرأي/آخر رسالة الخبير/الرأي الموثّق — فالشاشة بتعرض السبب والمبلغ بس (الملفات بس اللي ليها الرأيين).
9. **ملاحظة الحسم بتوصل للطرفين في الاستشارات العادية:** `_claim_refund`/`_release_claimed` بيكتبوا `note` في `escrow.resolution_note`، و`_serialize` بيرجّع `escrow` كله في `GET /consultations/{id}` للعميل والخبير. (الملفات مقفولة على الأبواب العامة ٤٠٤ فمش واصلة.)
10. **`bridge_list_files` حدّه ٢٠٠ من غير ترقيم** — `total` بيقول فيه أكتر، والداشبورد بيعلن القصّ («معروض ٢٠٠ من N»). مقبول دلوقتي.
11. **الجسرين لسه على فروع** (`expert-file-r1…r5`، مش على `main`) — على الإنتاج النهارده الاتنين ٤٠٤ ⇒ الشاشة هتفضل فاضية (`enabled:false`) لحد ما يتنشروا. ده مقصود (د٩) ومش عطل.
12. **مين هيقبض لو اتحسم «للخبير» مش مكتوب في صفّ النزاع:** في التوثيق اللي فلوسه على بريد المنصة، `resolve_disputed` بيحوّلها للي وثّق (`_judge_takes_platform_dispute`) — الصفّ فيه `expert_email` و`verified_by_email` بس من غير «المستفيد». المطلوب: `payee_email`/`payee_name` في `bridge_list_consultations` عشان نافذة التأكيد تقول الاسم الصح من غير تخمين.
13. **مفيش صفحة على المنصة تعرض استشارة لحد مش طرف فيها** (`_load_for_party` بيرجّع ٤٠٤ للأدمن) ⇒ مفيش لينك ينفع من الداشبورد لـ«الشغل اللي اتسلّم» في نزاع الاستشارة. الداشبورد بيقولها صريحة في الدرج («بتحسم من غير ما تشوفه») وفي نافذة التأكيد، لحد ما بند ٨ يتعمل أو تتعمل صفحة أدمن.
14. **الخدمة مقفولة ⇒ مفيش أي طريق لرجوع فلوس ملف من الداشبورد:** كل `/bridge/expert-files*` ورا المفتاح (بما فيها `refund`)، والتنبيه «افتح المفتاح أو رجّع الفلوس» ما لوش زرار. الداشبورد بيقول «شغّل الخدمة على المنصة تاني … وهي مقفولة ما ينفعش من هنا». المطلوب: `refund` (وقايمة الملفات المفتوحة) يفضلوا شغّالين والمفتاح مقفول.
15. **`expert_amount: null` في استشارات اتموّلت قبل العمولة:** `_release_claimed` بيحوّل المبلغ كله في الحالة دي — الداشبورد بيكتب «هيتحوّل المبلغ كله» بنفس القاعدة، بس الأصح الصفّ يبعت `release_amount` (اللي هيتحوّل فعلًا) بدل ما الداشبورد يستنتجه.
16. **`ops/queue.expert_files_waiting` بيعدّ «مستني توزيع» و«اتبعت وما اتستلمش» مع بعض (`PRE_CLAIM`):** مفيش عدّاد للي محتاج فعل من المؤسس بس (`awaiting_assignment` + `assign_overdue`). الداشبورد سمّى العدّاد «ملفات لسه ما اتستلمتش»، والبنود الحقيقية هي صفوف الوارد (الملف اللي اتبعت ولسه في الـ١٢ ساعة بقى سطر «للعلم» مش بند).
17. **ردود الكتابة في الجسر بترجّع الملف كله** (`bridge_view`: إيميل العميل واسمه كامل · الوقائع · المقابلة · رقم الدفع) — الداشبورد بيقصّها في الخادم قبل ما توصل المتصفح (`{ok, status}` + الرأيين بس في التفاصيل)، بس الأنضف الجسر نفسه يرجّع اللي محتاجينه بس.
