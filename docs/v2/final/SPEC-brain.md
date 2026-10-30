# Final round — section «العقل» (key `brain`): its rules, today's log, and its helpers

**Founder (2026-10-30):** «الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا».
**Approved concept:** `Brain.dc.html` (scratchpad `dash-canvas/project/`). Two cards side by side: the rules, each with a «وحده / يسألني» switch, and the log of what happened. The concept's header card is **not** copied: the D1-B shell already draws the section title and its description above the tabs (see Decisions D1).
**Map:** `DASHBOARD-MAP-2026-10-30.md` §4, appendix B §2 and §8. `DASHBOARD-PLAN` row D7: «a rules screen + a run log + اعكس».

This spec is the **plan stage, revision 2** (after the expert review). The build agent follows it exactly and works only in this worktree (`.worktrees/brain`, branch `final-brain`).

---

## 0) What is true today (the facts this section must not exaggerate)

Every line on these screens comes from one of the facts below. Anything else is «غير متاح بعد» or it is not shown.

| # | Automatic behaviour (exists today) | Where it lives | Real switch? | Real undo? | What we can read from the dashboard today |
|---|---|---|---|---|---|
| A1 | **Auto-assign a paid expert file** to the best available expert. Order: contract reviewer for contracts, then specialty, then country of law, then lowest load. | `P:expert_files.py` `auto_assign_file` / `_pick_expert` / `_write_assignment` (writes `assign_log {at,to,by:'auto',reason,why}`) | **Yes**: `auto_assign`. Read with `GET /api/platform-expert-files/settings` and write with `PUT` (the existing dashboard route, which requires `confirmed:true` to switch off). The platform also returns `explicit, updated_at, updated_by`, but the existing proxy drops them. | **No.** The founder can only *send it to another expert* before it is claimed (existing `EP.expertFileSend` → `/assign`). Nothing returns the file to «waiting» | `assign_log` on every file row (bridge `status=all` = the 200 most recently updated files; the inbox has open lanes only). The bridge also returns `assign_log[].to_name` ready (`P:expert_files.py` `_assign_log_view`) |
| A2 | **Move an unclaimed file to the next expert** after the claim window (12 h; 2 h urgent). | same sweep, `:6533-6558` | Follows A1. When A1 is off, the platform sends a Telegram alert instead | No | `assign_log` entries with `reason:'timeout'` |
| A3 | **Full refund of a file nobody claimed** within the claim window after payment. | sweep `:6640-6672` | No | No (money left) | Not readable per file today: the list row has no `refunded_at` or `refund_reason` (see Platform needs) |
| A4 | **Refund a consultation** when the expert misses the reply window (24 h; 48 h for توثيق). | `consultations.enforce_consultation_sla` | No | No | Not readable today |
| A5 | **Release the expert's fee** after delivery when no objection is raised. | sweep `:6920-6945` · `EP_POLICY.escrow.auto_release_hours` | No | No | The hours come from the platform's public `GET /api/policies` (`escrow.auto_release_hours`). Events are not readable today |
| A6 | **Release a case stage** automatically after 7 days. | sweep `:6948` | No | No | Not readable |
| A7 | **Urgent file falls back to normal** and the price difference is refunded. | `_urgent_fallback` | No | No | Not readable |
| A8 | **File reminders**: unpaid order, missing information, session in one hour. | sweep | No | — | Not readable |
| A9 | **First files of a new expert wait for your review** before they reach the client. | `EXPERT_REVIEW_FIRST_N` (3) | No (environment setting) | — | The waiting reviews appear in «ملفات الخبراء» |
| A10 | **Course price offer at or above the fair price is accepted on its own.** A lower offer waits for you. | `P:courses.py:2405` | No | No | — |
| A11 | **Live course moves on by date and seat count**: reserving → payment window → confirmed, or waits for your decision. | `live_courses` tick | No | — | heartbeat `tick_last` |
| A12 | **Session reminders** to people with an upcoming session. | `/bridge/courses/remind` | No | — | heartbeat `remind_last` |
| A13 | **Remind people whose invitation has waited** 3 days or more. | `/bridge/invites/reminders` | No | — | heartbeat `invite_reminders_last` |
| A14 | **Invitations from a far generation wait for your approval.** | `invite_approval_from_generation` | **A value, not a switch.** It is edited in «الناس والدعوات ← الدعوات» (`EP.setInviteSettings`) | — | `EP.data.inviteSettings.invite_approval_from_generation` |
| A15 | **Encouragement email to a learner who stopped for 7 days**, sent automatically once a week. | `/bridge/agents/coach-stalled` | No | No (email sent) | heartbeat `coach_stalled_last` |
| A16 | **Comments on topics are approved on their own** when on topic and not abusive; otherwise they wait for a person. | `P:topics.py:575-625` | No | — | — |
| A17 | **The helpers** («المساعدون», 11 today in `AI_AGENTS`; the screen never hard-codes the count) write reports from real numbers. They change nothing. | `D:app.py` `AI_AGENTS`, `/api/ai/agents*`, daily cap `ai_daily_usage_state()` | — | — | `GET /api/ai/agents`. Today's usage needs a new read route (B3) |

Health of the automatic runs: `GET /api/platform-ops-queue` → `heartbeats.{sla_last, remind_last, tick_last, invite_reminders_last, coach_stalled_last}`. The platform's `alerts[]` names a stopped run by its platform label: «حارس المهلة والاسترداد», «تذكيرات المواعيد», «ساعة الدورات الحيّة», «تذكير أصحاب الدعوات», «متابعة المتدرّبين المتوقّفين».

**Three consequences, binding on the build:**
1. **No «اعكس» button anywhere in this round.** None of the automatic actions has a real undo. For an automatic assignment that is still unclaimed, the honest action is «أرسله لخبير آخر». It opens the existing file drawer, which uses the existing `assign`. «اعكس» comes when Platform need P3 exists.
2. **No number from code constants.** A rule sentence contains a number only when a source returns it at runtime: B2 `release_hours` (from the platform's `/api/policies`), or `inviteSettings.invite_approval_from_generation`. Every other duration (12 h, 48 h, 7 days, 3 days, first 3 files…) waits for Platform need P2. Until then the sentence uses words like «في مهلته». The same applies to the number of helpers: it is `agents.length` at runtime.
3. **The concept's subtitle «الفلوس والنشر يسألك فيهما دائمًا» is false today**, because A3, A4, A5, A6 and A7 move money on their own. It must not appear. The rules screen shows the truth: these rows say «وحده دائمًا». The founder decides later whether any of them should ask first (Platform needs P4).

---

## 1) Tabs (`SECTIONS` entry `brain` only)

The nav label stays «العقل», so the D1-B tests and shots keep working. The shell draws it as the section's `h1`, with `desc` under it. **The tabs draw no second heading and no photo.**

```js
{ key: 'brain', label: 'العقل', img: 'brain', desc: 'ما يفعله العقل وحده، وما ينتظر قرارك. ما له مفتاح تغيّره من هنا.', tabs: [
  T('log', 'القواعد وسجل اليوم', 'v2s_brain'),
  T('helpers', 'المساعدون', 'ai')
] }
```

- `log` keeps its key, so `#s/brain/log` and the board's brain tile still work. The tile calls `host().openSection('brain','log')`. Its module becomes the virtual `v2s_brain`, which exists only under the new shell.
- `helpers` keeps the old module id `ai`. With the shell on, the brain module **owns `ai`** and draws the new helpers screen instead of `viewAI`. Old links therefore keep working: `#ai` lands on `brain/helpers` in the new look. With the switch off, `viewAI` renders exactly as today.
- **«كل السجلات»: none.** Everything the old `ai` screen did is covered below: run one, run all, master, details. The old D1 brain panel (`v2-home.js drawBrain`) is replaced by tab 1.

---

## 2) Files and wiring (parallel-safety rules)

| What | Where |
|---|---|
| Front-end | **NEW** `dashboard-cloud/v2s/brain.js`, `dashboard-cloud/v2s/brain.css` |
| Pure helpers | `dashboard-cloud/v2-logic.js`, at the end, inside `// ===== v2s:brain =====` … `// ===== /v2s:brain =====`, exported as `V2L.v2sBrain*` |
| Server routes | **NEW** `backend/v2_brain_routes.py` with `register(app, ns)`, registered by ONE line before `# ---- v2 section routes end` (create the marker right after the `/api/v2/person` route if missing) |
| Tests | **NEW** `backend/tests/test_v2s_brain.py` |
| Shots | **NEW** `backend/tests/uiharness/v2_shots_brain.py` (imports helpers from `v2_shots.py`, never edits it) and fixtures in **NEW** `backend/tests/uiharness/brain_fixtures.py` → `docs/v2/final/shots-brain/` |

**index.html.** Two lines inside the block `<!-- v2 sections begin -->` … `<!-- v2 sections end -->`. Create the block right after `<script src="v2-d2.js"></script>` if it is missing. Keep the lines alphabetical by key:
```html
<link rel="stylesheet" href="v2s/brain.css">
<script src="v2s/brain.js"></script>
```

**The module contract.** `brain.js` registers:
```js
window.V2SEC = window.V2SEC || {};
V2SEC.brain = { owns: function (mod) { return mod === 'v2s_brain' || mod === 'ai'; },
                render: function (mod, view) { … }, tileCount: function () { … } };
```
⛔ Do **not** use `window.V2S`: `index.html` already uses a global `V2S` for `{section, tab}` (`v2GoShell`, `v2OpenSection`).

**The generic dispatcher (shared edit, minimal).** `renderView()` needs one dispatcher line after the D3 line (`if(window.V2_ON&&window.V2D3&&V2D3.owns(current))…`):
```js
if(window.V2_ON&&window.V2SHELL&&V2SHELL.on&&window.V2SEC){for(const k in V2SEC){const s=V2SEC[k];if(s&&s.owns&&s.owns(current)){const ap=document.querySelector('.app');if(ap)ap.classList.add('v2-bare');return s.render(current,v);}}}
```
If the integrate stage or another section already added an identical `V2SEC` dispatcher, reuse it and do not add a second one. List it under shared_edits.

**Dockerfile (shared edit, minimal).** Without these lines the container cannot start:
- `COPY backend/v2_*_routes.py /app/`
- `COPY dashboard-cloud/v2s /app/dist/v2s`

Use the glob form so every section shares the same two lines. **The registration line in app.py is guarded:**
```python
try:
    from v2_brain_routes import register as _v2_brain_register; _v2_brain_register(app, globals())
except Exception: logger.exception('v2 brain routes not loaded')
```
The routes are behind the flag anyway. A test asserts both Dockerfile lines and the import.

**`ns = globals()` of app.py.** The route module reads helpers lazily at request time: `ns['token_required']`, `ns['roles_required']`, `ns['_v2_closed']`, `ns['_v2_ns']`, `ns['_v2_body']`, `ns['_platform_proxy']`, `ns['_ef_bridge']`, `ns['_resp_ok']`, `ns['_proxy_json']`, `ns['_audit']`, `ns['_actor_email']`, `ns['ai_daily_usage_state']`, `ns['AI_PROVIDERS']`, `ns['AuditLog']`, `ns['AgentReport']`, `ns['db']`. The decorators `token_required` and `roles_required` are defined before the registration line, so they can be applied at registration. Everything defined later (`ai_daily_usage_state` is at ~7337) is looked up inside the handler.

---

## 3) New server routes (`backend/v2_brain_routes.py`)

All routes are admin only (`@token_required @roles_required('admin')`). When the flag is off they return `_v2_closed()`, which is a 404 with no platform call. Every response is `no-store`. **No route makes more platform calls than the ones listed under it, and none retries.** **No route calls `ai_call` or any outside service except the platform proxy.**

**Time stamps.** Every ISO time a route returns carries a zone. A naive `datetime` (SQLite `created_at`, `AuditLog.at`) is treated as UTC and sent with `+00:00`. The front end also guards (see `v2sBrainTime` in §6), because `/api/ai/agents` sends `created_at` without a zone today (`D:app.py:8494`).

### B1. `GET /api/v2/brain/today?since=<ISO-8601 UTC>`
The source of the log and of the two numbers.
- `since` = start of the viewer's local day, computed in the browser. It is required and must parse as ISO. It is clamped to at most 8 days ago and never in the future; otherwise 400 «تاريخ غير صالح».
- One call: `_ef_bridge('GET', '/api/bridge/expert-files', params={'status': 'all'})`. That gives the 200 most recently updated files, each with `assign_log`.
- Response (allow-list only; **no client data, no amounts**):
```json
{ "files_ok": true, "partial": false, "service": "open|allowlist|closed|null",
  "entries": [ { "file_id": "…", "title": "…", "status": "assigned", "at": "ISO", "by": "auto|founder",
                 "reason": "paid|declined|timeout|manual", "why": "…", "to_email": "…", "to_name": "…",
                 "pre_claim": true, "current": true } ] }
```
- `entries` holds every `assign_log` entry with `at >= since`, newest first.
- `title` is the client's own wording as the platform stores it (admin-only route). It is cut to 80 characters. It is never shown outside the founder's screen.
- `to_name` = the entry's own `to_name` from the bridge when present. Fallbacks, in order: the row's `assigned_name`/`expert_name` when the email matches, then the names in `candidates[]` or `declined[]`. If none matches, it is `null`; the screen shows the email's local part, never an invented name.
- `pre_claim` = the row's `status == 'assigned'`. `current` = this entry is the latest `assign_log` entry and `to_email == assigned_to`.
- `partial` = `total > count` **and** the oldest `updated_at` in the page is `>= since`. Some of today's files may then be missing.
- Bridge 404 ⇒ `{"files_ok": false, "entries": null, "missing": true}` (the platform has no bridge). Any other failure ⇒ `{"files_ok": false, "entries": null}` with status 200. **Never `entries: []` on failure.** A 401/403 from the platform is treated as down, never as the admin's session (same rule as `_v2_mask_auth`).

### B2. `GET /api/v2/brain/rules`
The switch, values and history. **Two independent platform calls, no retry. Each fails on its own, and the response is always 200:**
- Call 1 `_ef_bridge('GET', '/api/bridge/expert-files/settings')` → `auto_assign: {value: bool|null, explicit: bool|null, updated_at, updated_by}`. 404 ⇒ `auto_assign: null` with `auto_assign_missing: true`. Any other failure, or a non-bool value ⇒ `auto_assign: null`.
- Call 2 `_platform_proxy('GET', '/api/policies')` → `release_hours`, which is `escrow.auto_release_hours` only when it is a positive int. Failure or any other value ⇒ `release_hours: null`.
- `requested`: the founder's requested rules from the new table (newest first, max 50). Local, no platform call.
- `history`: the last 20 `AuditLog` rows with `action in ('expert_file.auto_assign', 'v2_brain.rule_add', 'v2_brain.rule_delete')`, as `{at, actor_email, action, meta}`. Local.

### B3. `GET /api/v2/brain/helpers-status`
No platform call. Returns `{configured: bool, cap: int|null, used: int|null, remaining: int|null, blocked: bool}`:
- `configured` = any provider key in `AI_PROVIDERS` is set (same test as `/api/ai/agents`).
- The other fields come from `ai_daily_usage_state()`. That function is read-only and never raises. `cap == 0` means no cap: send `cap: null, remaining: null`. `counter_error` ⇒ `used/remaining: null`.

### B4. `POST /api/v2/brain/rules`
Body: `{text, confirmed: true}`. The screen's single «احفظها» press sends `confirmed:true`; there is no confirmation sheet (it moves no money and changes nothing on the platform).
- `text`: strip control characters and collapse spaces, then require 6–300 chars. Otherwise 400 «اكتب القاعدة في جملة واحدة واضحة (٦ أحرف على الأقل)».
- Missing `confirmed:true` ⇒ 400 (`_v2_confirmed`).
- More than 50 stored ⇒ 409 «وصلت إلى ٥٠ قاعدة محفوظة. احذف واحدة قبل إضافة غيرها».
- Stores `{id: uuid4 hex, text, status: 'requested', created_at, created_by: actor email from token}` and writes `_audit('v2_brain.rule_add', target=id, meta={'text': text[:120]})`.
- Returns the row.
- **Nothing reads these rules to act.** `status` is always `requested` in this round.

### B5. `DELETE /api/v2/brain/rules/<id>`
Body: `{confirmed: true}`.
- `id` must match `^[0-9a-f]{32}$`, otherwise 400. Unknown ⇒ 404.
- Deletes the row and writes `_audit('v2_brain.rule_delete', target=id, meta={'text': …[:120]})`.

**Storage.** New SQLite table `v2_brain_rules`, defined inside `register()` as `class V2BrainRule(db.Model)` with columns `id String(32) pk`, `text Text`, `status String(16)`, `created_at DateTime`, `created_by String(255)`. The model must be defined before `db.create_all()` at the end of app.py, which the registration line placement guarantees. Do **not** use the shared `Setting` table: `/api/settings` returns and overwrites every key.

**The switch itself needs no new route.** It uses the existing `PUT /api/platform-expert-files/settings`, which audits `expert_file.auto_assign`. The module calls it directly through `EP.api` (see §4.3), not through `EP.expertFileAutoAssign`, so that the toasts are ours.

---

## 4) Tab 1 «القواعد وسجل اليوم» (`v2s_brain`)

### Layout
The shell already shows «العقل» and the section description above the tabs. The tab starts directly with the brain line. Nothing in this tab is an `h1`; card headings are `h2`.

- **Desktop ≥1180:**
  1. **The brain line** (§4.5): one slim strip in the D3 style (`.v3-top` + `.v3-brain`): the brain avatar 28px (`.v3-bav`), one sentence, at most one button. On its end side, the two number discs (`#FBF6F0`, radius 14): disc 1 «وُزّع وحده اليوم», disc 2 «غيّرت خبيره يدويًا».
  2. **Two cards side by side:** «القواعد» (`flex 1.3`) on the start side, «سجل اليوم» (`flex 1`) on the end side. The «قاعدة تريدها» box sits at the **bottom of the rules card**.
- **Tablet 761–1179 and mobile ≤760:** the brain line, then a `.v3-seg` switcher with two segments «القواعد» | «سجل اليوم» (as the period switcher in D3), then only the selected card. Default: «القواعد». The choice is kept per viewer in `localStorage` (wrapped in try/catch; the screen works without it). The discs wrap under the sentence as a 2-column grid.
- **Mobile ≤760 (390):**
  - In the rules card all groups are folded except «ملفات الخبراء والاستشارات». A group heading is a `<button aria-expanded>` ≥52px with its row count.
  - A rule row is one line of title + control, with the short status line under it (see §4.2). Chips stay compact on the end side; they are labels, not targets, and are never stretched full width. Only the real switch (`assign`) moves under the title at full width.
  - Size rules: every `<button>` and every switch segment (`[role=radio]`) is **≥52px** high; links (`<a>`) and other targets are ≥44px. The rule's title is a `<button>` (it opens the sheet), so it is ≥52px.
  - 16px side gutter, no horizontal page scroll.
- **Row structure (all sizes):** the row is a `<div>`. Inside it, the title is a `<button class="v2sb-rt">` that opens the rule sheet, and the control sits next to it. The switch is never nested inside another button.
- **Colours:** burgundy `#9E2B4E` for the active «يسألني» and the main button; ink `#21262E`; paper `#FBFAF7`/`#F6F1EA`; red `#C8102E` only for a stopped run. Fonts Cairo/IBM Plex Sans Arabic. Reuse the D3 classes where they fit (`.v3-top`, `.v3-card`, `.v3-brain`, `.v3-bav`, `.v3-btn1/2`, `.v3-empty`, `.v3-err`, `.v3-seg`). New classes are prefixed `v2sb-`.

### 4.1 The two numbers
| Disc | Value | Source | Not available |
|---|---|---|---|
| «وُزّع وحده اليوم» | count of B1 entries with `by:'auto'` | B1 | B1 failed and the inbox fallback failed ⇒ «غير متاح بعد». B1 `partial` ⇒ the number gets a prefix «على الأقل ». The inbox fallback is used ⇒ prefix «على الأقل » as well |
| «غيّرت خبيره يدويًا» | number of distinct files that have an auto entry today **and** a later `by:'founder'` entry today | B1 | same rule |

Numbers use Arabic-Indic digits (`U.ar`). Zero is shown as «لا شيء» and never as «٠».

### 4.2 «القواعد» card
Heading «القواعد» plus a muted hint «ما يحدث وحده كلما وقع أمر». The rows are grouped by small group titles. Each row shows **only**:
- **title** (600, 15), the button that opens the rule sheet (§4.4);
- on the end side, **the control**: the real switch or a chip;
- **a short status line** (12, muted), for example «آخر تشغيل: منذ ٢٠ دقيقة».

The «عندما…» sentence is **not** in the row; it is in the rule sheet under «متى يعمل».

Chips (all in the founder's own voice, like the switch):
- «وحده» / «وحده دائمًا» on ink background: it runs alone and has no switch.
- «يسألني» on `#F7E9EE` with `#7A1F3B` text: it waits for your decision.
- «متوقّف» in red: the platform alert names its run.
- «غير متاح بعد» on grey `#EEE9E2`: the state could not be read.
- «لم تُبنَ بعد» on grey `#EEE9E2`: a rule you asked for (§4.7).

**Rows, exact strings** (the sentence column is shown in the rule sheet only):

Group «ملفات الخبراء والاستشارات»
| key | Title | Sentence | Control | Status line |
|---|---|---|---|---|
| `assign` (A1) | «توزيع الملفات على الخبراء» | «عندما يُدفع ملف، يُرسل وحده إلى أنسب خبير متاح: حسب التخصص، ثم بلد القانون، ثم الأقل انشغالًا.» | **Real switch** `[وحده | يسألني]`, value from B2 `auto_assign.value`. `null` ⇒ no switch; chip «غير متاح بعد» and the line «تعذّر جلب حالة التوزيع». `auto_assign_missing` ⇒ line «التوزيع التلقائي غير موجود على المنصة بعد» | «آخر تغيير: <agoText(updated_at)> بواسطة <updated_by>» when `explicit` is true; «لم يُغيَّر من قبل» when `explicit` is false. The sheet also shows «آخر تشغيل: …» from `sla_last` |
| `move` (A2) | «نقل الملف إن لم يُستلم» | On: «عندما لا يستلم الخبير الملف في مهلته، يُرسل وحده إلى الخبير التالي.» Off: «عندما لا يستلم الخبير الملف في مهلته، يصلك تنبيه لترسله بنفسك.» Unknown: the «On» sentence unchanged | Follows `assign`: `true` ⇒ chip «وحده»; `false` ⇒ chip «يسألني»; `null` ⇒ chip «غير متاح بعد» | `true`/`false` ⇒ run text of `sla_last`; `null` ⇒ «تعذّر جلب حالة التوزيع» |
| `unclaimed_refund` (A3) | «ردّ مبلغ الملف الذي لم يستلمه أحد» | «عندما تمر مهلة الاستلام بعد الدفع دون أن يستلم أي خبير الملف، يُردّ المبلغ كاملًا إلى صاحب الطلب.» | chip «وحده دائمًا» | `sla_last` |
| `consult_refund` (A4) | «ردّ مبلغ الاستشارة عند تأخر الرد» | «عندما لا يرد الخبير على الاستشارة في المهلة الموعودة، يُردّ المبلغ إلى محفظة صاحب الطلب.» | chip «وحده دائمًا» | `sla_last` |
| `release` (A5) | «تحرير أجر الخبير بعد التسليم» | When B2 `release_hours` exists: «عندما تمر <U(hours/24 when divisible by 24, else hours)> على التسليم دون اعتراض، يتحرّر أجر الخبير.» When it is null: «عندما تمر مهلة الاعتراض بعد التسليم دون اعتراض، يتحرّر أجر الخبير.» | chip «وحده دائمًا» | `sla_last` |
| `case_release` (A6) | «تحرير مراحل القضية» | «عندما تمر مهلة المرحلة دون اعتراض، يتحرّر أجرها.» | chip «وحده دائمًا» | `sla_last` |
| `urgent` (A7) | «الملف المستعجل الذي لم يُستلم في وقته» | «عندما لا يُستلم الملف المستعجل في وقته، يصبح عاديًا ويُردّ فرق السعر إلى صاحب الطلب.» | chip «وحده دائمًا» | `sla_last` |
| `reminders` (A8) | «تذكيرات الملفات» | «عندما يتأخر الدفع، أو تنقص معلومات، أو يقترب موعد جلسة، يصل تذكير إلى صاحبه.» | chip «وحده» | `sla_last` |
| `first_review` (A9) | «مراجعة أول ملفات الخبير الجديد» | «عندما يسلّم خبير جديد أحد ملفاته الأولى، ينتظر الرأي مراجعتك قبل أن يصل إلى صاحب الطلب.» | chip «يسألني» | «في ملفات الخبراء» |

Group «الدورات»
| `offer_accept` (A10) | «عروض الأسعار على الدورات» | «عندما يعرض متعلّم السعر العادل أو أكثر، يُقبل العرض وحده. وما هو أقل ينتظر قرارك.» | chip «وحده» | «يعمل لحظة العرض» |
| `live` (A11) | «الدورات المباشرة» | «عندما يكتمل العدد في موعده، تُفتح مهلة الدفع وحدها. وإن لم يكتمل، تنتظر الدورة قرارك.» | chip «وحده» | `tick_last` |
| `session_remind` (A12) | «تذكير مواعيد الجلسات» | «عندما تقترب جلسة، يصل تذكير إلى كل مشارك.» | chip «وحده» | `remind_last` |
| `coach` (A15) | «متابعة المتعلّمين المتوقّفين» | «عندما يتوقف متعلّم عن دورته مدة، تصله رسالة تشجيع وحدها، ولا تتكرر له قبل مهلة.» (numbers only after Platform need P2) | chip «وحده» | `coach_stalled_last` |

Group «الناس والدعوات»
| `invite_remind` (A13) | «تذكير الدعوات المنتظرة» | «عندما يطول انتظار دعوة، يصل تذكير إلى المدعو أو إلى صاحب الدعوة.» (the number of days only after P2) | chip «وحده» | `invite_reminders_last` |
| `invite_approval` (A14) | «دعوات الأجيال البعيدة» | When `inviteSettings.invite_approval_from_generation` is set: «عندما يدعو عضو من الجيل <ar(n)> أو بعده، تنتظر الدعوة موافقتك.» When it is null: «عندما تأتي دعوة من جيل بعيد، تنتظر موافقتك.» | chip «يسألني». The sheet adds the link «غيّرها من الدعوات» (opens `host().openSection('people','invites')`) | set ⇒ «من الجيل <ar(n)>»; null ⇒ «الجيل: غير متاح بعد» |

Group «المحتوى»
| `comments` (A16) | «التعليقات على الموضوعات» | «عندما يكون التعليق في الموضوع وبلا إساءة، يُنشر وحده. وغير ذلك ينتظر مراجعة.» | chip «وحده» | «يعمل لحظة التعليق» |

Group «قواعد طلبتها» (last group, only if B2 `requested` has rows), followed by the «قاعدة تريدها» box (§4.7)
- One row per requested rule: its text as the title (not a button; there is no sheet); the status line «حُفظت <agoText(created_at)>»; chip «لم تُبنَ بعد»; and a ghost button «احذف» (≥44px; 52 on mobile).
- «احذف» opens a confirmation sheet: «تُحذف هذه القاعدة من القائمة. لم تكن تعمل، فلن يتغيّر شيء في المنصة.», with «احذفها» and «رجوع». It calls B5 with `confirmed:true`.

**«متوقّف».** A row whose run has a platform alert gets the red chip «متوقّف» **instead of** its normal chip. The alert is found by matching the platform label inside the cleaned alerts (`v2Health(Q).alerts`). The status line then reads the cleaned alert, for example «حارس المهلة والاسترداد: متوقفة منذ ٥ ساعات — …». This replaces the chip only and never hides the switch.

**Status line wording** (`v2sBrainRunText(at, now)`):
- «آخر تشغيل: منذ <durShort>»;
- missing stamp ⇒ «لم يعمل حتى الآن»;
- opsQueue failed ⇒ «آخر تشغيل: غير متاح بعد».

### 4.3 The switch (rule `assign` only)
- A segmented control with exactly two segments, `«وحده»` and `«يسألني»`, using `role="radiogroup"`. The active segment is ink `#21262E` with white text for «وحده», and burgundy `#9E2B4E` for «يسألني».
- Tapping the inactive segment opens a **confirmation sheet** (existing `openModal`, same `.v3m` frame as D3). Nothing changes until the main button is pressed.
  - To «يسألني»: title «إيقاف التوزيع التلقائي». Body: «إذا أوقفته، ينتظر كل ملف يُدفع بعد الآن أن توزّعه بنفسك، ولن تُرسل الملفات المنتظرة الآن وحدها. ويصلك تنبيه عن كل ملف لم يُستلم.» Buttons: «نعم، أوقفه» (main) and «رجوع».
  - To «وحده»: title «تشغيل التوزيع التلقائي». Body: «إذا شغّلته، يُرسل كل ملف مدفوع ينتظر الآن، وكل ملف يُدفع بعده، إلى أنسب خبير متاح وحده. ويمكنك إرسال أي ملف إلى خبير آخر قبل أن يستلمه.» When opsQueue has `expert_files_awaiting_assignment` > 0, add a line «ينتظر الآن: <U(n, ملف)>». Buttons: «نعم، شغّله» and «رجوع».
- The main button calls **`EP.api('/platform-expert-files/settings', {method:'PUT', body:{auto_assign: value, confirmed: true}})`** directly. The sheet is busy («جارٍ الحفظ…», both buttons disabled) until the promise settles.
  - Success ⇒ set `EP.data.efSettings = {auto_assign: <bool from reply, else value>}` (D2 reads it), close the sheet, toast «شُغّل التوزيع التلقائي» or «أُوقف التوزيع التلقائي», then reload B2 and B1, `EP.reload('inbox')` and `EP.reload('opsQueue')`.
  - Error mapping (our own strings, in place of the old colloquial ones):
    - no status, or ≥500 without a server message ⇒ «لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.»; the main button stays disabled, and B2, inbox and opsQueue are reloaded;
    - 401 ⇒ «انتهت الجلسة. سجّل الدخول من جديد ثم جرّب.» (`EP.api` already shows the login);
    - otherwise the server's `error` text, else «تعذّر تنفيذ العملية».
    The sheet stays open with the error line.
- Not a money action, so there is no money sheet.

### 4.4 Rule sheet (opened from the rule's title)
A focus sheet:
- title = rule title;
- «متى يعمل» = the sentence;
- «آخر تشغيل» = the run text (for `assign`, from `sla_last`; plus the status line «آخر تغيير…»);
- «أين ترى نتيجته» = one link button:
  - files rules ⇒ «افتح ملفات الخبراء» (`openSection('files')`);
  - `consult_refund`/`release` ⇒ «افتح النزاعات والاستردادات» (`openSection('disputes')`);
  - `offer_accept`/`live`/`session_remind`/`coach` ⇒ «افتح الدورات» (`openSection('courses')`);
  - invites ⇒ «افتح الدعوات» (for `invite_approval` the label is «غيّرها من الدعوات»);
  - `comments` ⇒ «افتح المحتوى».
- For `release` only: «المهلة: <hours>» or «المهلة: غير متاح بعد».
- For `assign` only: the change history from B2 `history` rows with `expert_file.auto_assign`, formatted «<agoText> — شُغّل بواسطة <actor_email>» or «… — أُوقف بواسطة …». No history ⇒ «لم يتغيّر من هذه اللوحة».
- Closes with «إغلاق».

### 4.5 The brain line (facts only, at most one button)
Pick the **first** case that is true:
1. opsQueue alerts contain a run used by a rule ⇒ «<cleaned alert>» with no button. It is a fact; the founder cannot restart a run from here.
2. B2 `auto_assign.value === false` and opsQueue `expert_files_awaiting_assignment` > 0 ⇒ «التوزيع التلقائي متوقّف، و<U(n, ملف)> ينتظر توزيعك» with the button «افتح الملفات» (`openSection('files')`).
3. Today's auto count > 0 ⇒ «وُزّع اليوم <U(n, ملف)> وحده<, وغُيّر خبير <U(m)> منها يدويًا when m > 0>.» with no button.
4. Sources ok and nothing happened ⇒ «لم يوزّع العقل شيئًا اليوم، وكل ما يعمل وحده يعمل.» with no button. The second clause is only included when there are no alerts **and** opsQueue loaded.
5. A source failed ⇒ «تعذّر جلب بعض ما يفعله العقل: <names>. لا نعرف الصورة كاملة.» Names: «الملفات» (B1), «حالة ما يعمل وحده» (opsQueue), «القواعد» (B2).

The counts use the existing `U.U(n, ['ملف واحد','ملفان','ملفات','ملفًا'])` forms. Never write a judgement such as «أداء ممتاز».

### 4.6 «سجل اليوم» card
- Heading «سجل اليوم» plus the date (`ar-EG` long day).
- Rows, newest first. Each row: time `hh:mm` (Arabic digits, 44px wide, muted), text, and one action link.

| Entry kind | Text | Action |
|---|---|---|
| B1 `by:'auto'`, `reason:'paid'` | «وزّع «<title>» على <name>» | see below |
| `reason:'declined'` | «وزّع «<title>» على <name> بعد اعتذار خبير» | |
| `reason:'timeout'` | «نقل «<title>» إلى <name> لأن الملف لم يُستلم في وقته» | |
| B1 `by:'founder'` that follows an auto entry on the same file today | «أُرسل «<title>» يدويًا إلى <name>» (muted, so the founder's own change is visible next to the brain's) | «اعرض» |
| Helper report written today (`/api/ai/agents` row whose `created_at`, read through `v2sBrainTime`, is `>= since`) | «كتب مساعد «<plain label>» تقريره» | «اعرض» ⇒ the helper sheet (§5.3) |

- Under an auto entry, `why` (shortened to 160) appears as a second muted line when present.
- `<name>` = `to_name`, or else the email's local part. It is a link to the person page via `V2D2.link(name, email)` when available.

**Action on an auto entry:**
- `pre_claim && current` ⇒ «أرسله لخبير آخر». It opens the file the way the files board does: when the row is in `window.INBOX`, call `host().openRowAt('files','all', row)`; otherwise `host().openSection('files')`. The expert change happens in the existing drawer through `EP.expertFileSend`. **The label is never «اعكس».**
- Otherwise ⇒ «اعرض», which opens the same file.

**States:**
- Loading: three grey skeleton rows (no numbers).
- Empty with sources ok: the paper elephant (`v2/img/brain-avatar.jpg`, 64px) and «لم يحدث شيء وحده اليوم حتى الآن».
- B1 failed: try the fallback `V2L.v2sBrainLogFromInbox(window.INBOX incl. fyi rows, since)`. When the fallback has rows, show them with a note «من الملفات المفتوحة فقط، وقد يكون السجل ناقصًا». When the fallback fails too, show the error box «تعذّر جلب سجل الملفات» with «أعد المحاولة» (reloads B1).
- B1 `partial`: a note «معروض أحدث ٢٠٠ ملف فقط، وقد يكون في سجل اليوم ما لم يظهر».
- B1 `missing`: «سجل التوزيع غير موجود على المنصة بعد».
- More than 12 rows ⇒ the first 12, then a button «اعرض الكل (<n>)» that expands in place.

### 4.7 «قاعدة تريدها» box (last element of the rules card, `#FBF6F0`, radius 16)
- Heading «قاعدة تريدها».
- One text input, ≥46px (52 on mobile), with `aria-label="اكتب القاعدة التي تريدها"` and placeholder «مثلًا: لا توزّع ملفات الخليج على خبير من مصر».
- A muted hint under it: «تُحفظ هنا حتى تُبنى في المنصة، ولا تعمل الآن.»
- Button «احفظها» (main, ≥44; 52 on mobile).
  - Disabled while the text is shorter than 6 chars, and while the save is in flight.
  - One press calls B4 with `confirmed:true`. **No confirmation sheet.**
  - Success ⇒ clear the input, toast «حُفظت القاعدة», reload B2; the row appears under «قواعد طلبتها».
  - 400/409 ⇒ show the server message under the input.
- The box holds no AI and no parsing. The brain does not read or interpret the text in this round.

### 4.8 Loading, data, refresh, and the board tile
- Sources: existing `EP.ensure('opsQueue')`, `EP.ensure('inbox')` (fallback and drawer rows), `EP.ensure('aiAgents')`, `EP.ensure('inviteSettings')`, plus B1, B2 and B3, each loaded by the module with `EP.api`.
- Each source fails on its own: its own elements show «غير متاح بعد», never 0 or an empty list.
- Redraw on a source signature change, polling every 400 ms only while the tab is current, as D3 does.
- A minute tick refreshes the «منذ» texts. No redraw while `#epModal` is open.
- **`tileCount()`** — one number for the board tile, the files board header and this screen:
  - first call starts a B1 load (shared with the screen, cached 60 s, refetched after the cache expires on the next call) and returns `undefined`;
  - B1 loaded ⇒ the auto count (number, may be 0);
  - B1 failed ⇒ `null`.
  - It only fetches when `window.V2_ON` is true.
- **The tile and the files header use it (shared edits, this round):**
  - `v2-home.js`, where `extras` is built: add `brainToday: (window.V2SEC && V2SEC.brain && V2SEC.brain.tileCount) ? V2SEC.brain.tileCount() : undefined`.
  - `v2-logic.js` `v2Tiles`, brain tile: when `extras.brainToday` is a number, use it as `n` (instead of `v2BrainLog(rows, now).length`); when it is `null`, `failTile(t)`; when `undefined`, keep today's code. The `t.next` sentence is unchanged.
  - `v2-d2.js` `gather()`: `brainToday` = `tileCount()` when it is a number, else today's expression.
  - The existing home redraw (signature polling) picks up the number once B1 arrives.

---

## 5) Tab 2 «المساعدون» (module `ai`, drawn by `brain.js` under the shell)

### 5.1 Layout
- **Brain line** (same slim strip as tab 1, `.v3-top` + `.v3-brain`, avatar 28px). On its end side a single disc «تحديثات اليوم» with the value «<used> من <cap>» from B3. When `cap` is null ⇒ «بلا سقف». When B3 failed ⇒ «غير متاح بعد». The first true case:
  1. B3 `blocked` ⇒ «وصلت تحديثات اليوم إلى حدّها، وتعود بعد منتصف الليل بتوقيت غرينتش.»
  2. `configured === false` ⇒ «التحليل المكتوب غير مفعّل الآن، فيكتب المساعدون الأرقام وحدها.»
  3. The master report exists ⇒ «آخر صورة كاملة كُتبت <agoText(created_at)>.»
  4. Otherwise ⇒ «لم تُكتب الصورة الكاملة بعد.»
  Next to the disc, the ghost button «حدّث الكل» (see below).
- **«الصورة الكاملة» card** (full width, burgundy start-side border 4px):
  - the master's `summary` (15, line-height 1.8);
  - up to 3 `actions` as «اقتراحات» lines with a small check;
  - «آخر تحديث: …»;
  - main button «حدّث الصورة الكاملة» ⇒ run `master` (see «Runs» below).
  - Empty ⇒ «لم تُكتب بعد. حدّثها بعد أن يكتب المساعدون تقاريرهم.»
- **Helpers grid:**
  - 3 columns ≥1180, 2 columns 761–1179, 1 column on mobile.
  - Each card: photo strip 72px (cover, radius 14); plain label (Cairo 800 16); plain description (13, muted); a «آخر تحديث» line; the summary clamped to 3 lines; then the buttons «اعرض» (ghost) and «حدّث» (secondary).
  - A report with `source === 'data'` or `ai_unavailable` gets a chip «أرقام فقط».
  - No report ⇒ «لم يكتب تقريرًا بعد», only «حدّث» is shown.
- **«حدّث الكل»** opens the confirmation sheet: «سيكتب المساعدون <U(n, ['مساعد واحد','مساعدان','مساعدين','مساعدًا'])> تقاريرهم الآن، وتُحسب <U(n, ['تحديث واحد','تحديثان','تحديثات','تحديثًا'])> من تحديثات اليوم (المتبقي: <remaining | غير متاح بعد | بلا سقف>).» where `n` = number of helpers in `/api/ai/agents` (master included, as `agent=all` runs it). Buttons «نعم، حدّثها كلها» and «رجوع». It is disabled with the reason «لا يكفي المتبقي من تحديثات اليوم» when `remaining !== null && remaining < n`.
- All «حدّث» buttons are disabled when B3 `blocked`.

**Runs (the module owns them; it does not call `EP.runAgents`):**
- State `S.running = {id, since}` is set **before** the request and cleared when it settles (success or failure).
- The request is `EP.api('/ai/agents/run?agent=' + encodeURIComponent(id), {method:'POST', body:{}})`.
- While `S.running` is set, **every** run control on both tabs — each card's «حدّث», «حدّث الصورة الكاملة», «حدّث الكل», the sheet's «نعم، حدّثها كلها» and «حدّث هذا التقرير» — is disabled and the pressed one reads «جارٍ الكتابة…». A second press therefore sends nothing. The «حدّث الكل» sheet stays open and busy until the request settles.
- Toasts (our own): one helper ⇒ «كُتب تقرير «<plain label>»»; all ⇒ «كُتبت <U(k, ['تقرير واحد','تقريران','تقارير','تقريرًا'])>» with `k = reply.agents.length`, or «لم يُكتب أي تقرير» when `k` is 0; failure ⇒ server `error` text, else «تعذّر كتابة التقارير الآن». Then `EP.reload('aiAgents')` and reload B3.

### 5.2 Plain labels, descriptions and photos (front-end map; server labels contain «SEO/AEO», «Master», «n8n»)
| id | Label | Description | Photo |
|---|---|---|---|
| master | «الصورة الكاملة» | «يجمع ما كتبه المساعدون في صورة واحدة وأهم ثلاث خطوات» | `brain-avatar` |
| articles | «المقالات» | «المسودات التي تنتظر الاعتماد، وما لم نكتب عنه بعد» | `content` |
| seo | «الظهور في البحث» | «هل تظهر مقالاتنا لمن يبحث عنها، وهل ننشر بانتظام» | `content` |
| automation | «الأعمال المتكرّرة» | «ما يتكرّر كل يوم في اللوحة ويمكن أن يعمل وحده» | `brain` |
| sales | «المبيعات» | «من سأل ولم يشترِ بعد، والخطوة التالية مع كل واحد» | `market` |
| marketing | «التسويق» | «أي بلد وأي فئة نخاطب، بناءً على ما يطلبه الناس» | `marketing` |
| platform | «المنصة» | «ما ينتظر الاعتماد، وما يبدو غير معتاد في الأرقام» | `company` |
| topics | «الموضوعات» | «ما نكتب عنه بعد ذلك، من أسئلة الناس الحقيقية» | `content` |
| incoming | «ما يطلبه الزوار» | «من أين يأتي الناس وماذا يسألون» | `reports` |
| dev | «سلامة الأنظمة» | «الأعطال وما يحتاج إصلاحًا» | `company` |
| finance | «المالية» | «الدخل والمصروف وما قد يتأخر» | `money` |

An unknown id falls back to its server label as given, with the photo `brain`.

### 5.3 Helper sheet («اعرض»)
- Title «تقرير: <plain label>».
- The summary in a brain block, with avatar.
- «ما لاحظه»: `bullets`. Empty ⇒ «لا ملاحظات».
- «ما يقترحه»: `actions` as text lines with **no buttons**. The suggestions are text, and nothing here pretends to execute them. Empty ⇒ «لا اقتراحات».
- «آخر تحديث: …».
- Buttons «حدّث هذا التقرير» (a run of this `id`, under the same `S.running` lock; the sheet re-renders after the reload) and «إغلاق».
- The texts written by the helper (summary, bullets, actions) are shown as received, inside a block labelled «كتبه المساعد». This is content, not our copy.

### 5.4 States
- `aiAgents` loading ⇒ skeleton cards.
- `aiAgents` error ⇒ an error box «تعذّر جلب تقارير المساعدين» with «أعد المحاولة» (`EP.reload('aiAgents')`). The grid is not drawn; no zeros appear.
- B3 failed ⇒ the disc shows «غير متاح بعد»; the buttons stay enabled (except during a run), because the server cap still protects.

---

## 6) Pure helpers (`v2-logic.js`, block `// ===== v2s:brain =====`)

All are pure and unit-tested in node. A failed source is `null`, and they return `null` for it, never zero.

- `v2sBrainTime(s)`: parses an ISO stamp; when it has no zone (`/(Z|[+-]\d\d:?\d\d)$/` does not match) it appends `Z` first. Returns ms or `null`. **Every** time comparison and «منذ» text in this section goes through it.
- `v2sBrainEntries(todayResp, since)`:
  - `todayResp` = B1 body or `null`;
  - returns `{entries, autoCount, changedCount, partial, missing}`, or `null` when `files_ok` is false and the body is not `missing`.
  - Sorts newest first and dedupes on `file_id|at|to_email`.
  - `changedCount` = distinct `file_id` that have an auto entry and a later founder entry, both `>= since`.
- `v2sBrainLogFromInbox(rows, since)`: the same output shape, built from `INBOX` rows **including fyi** (`r.ef.assign_log`). It is used only as a fallback and always has `partial:true`.
- `v2sBrainRules(input)`:
  - `input = {settings: B2|null, queue: opsQueue|null, invite: inviteSettings|null, now}`;
  - returns the ordered groups and rows `{key, group, title, sentence, control:{type:'switch'|'chip', value, label, tone}, run:{text, stopped, alert}, link}`, with every string exactly as in §4.2.
- `v2sBrainRunText(at, now)` and `v2sBrainStopped(queue, platformLabel)`.
- `v2sBrainLine(ctx)`: the five cases of §4.5, returning `{text, button|null}`.
- `v2sBrainHelpers(agentsResp, status, running)`: cards in the order master first, then the server order. It applies the plain labels and the flags `dataOnly`, `canRun`, `canRunAll`, `runAllReason`, `count` (= number of agents). `canRun`/`canRunAll` are false while `running` is set.
- `v2sBrainLogText(entry)`: the log sentence per `reason`/`by`.

---

## 7) Visible copy rules (tested)
- Plain standard Arabic, gender-neutral («صاحب الطلب»). No «يقوّم».
- No colloquial or technical words in our strings: never «لما », «⇒», «الكنسة», «نداء», «الوضع الافتراضي», «التشغيلات», «✓».
- No Latin letters and no Latin digits in our strings, except inside an email address or a helper-written text block.
- No headline starts with «الذكاء» or «AI».
- Never «اعكس» in this round.
- «0», «null», «NaN» and «undefined» never appear. A missing value is «غير متاح بعد».
- The toasts in §4.3, §4.7 and §5.1 are part of our copy and are scanned too.

---

## 8) Tests (`backend/tests/test_v2s_brain.py`)

⛔ Zero real network. The platform is an in-memory fake (`brain_fixtures.BrainPlatform`, reusing `ef_fixtures` and `v2_fixtures` shapes). Any URL outside `https://platform.test` fails the test. `ai_call`, `call_anthropic` and `requests.post` to any AI host are monkeypatched to raise, which proves zero paid calls.

**pytest (routes):**
1. B1–B5: admin only. `employee`, `trainer`, `investor`, `viewer` and `pending` get 403. With the flag off, each returns 404 **with no platform call**. Every response is `no-store`.
2. B1:
   - the shape is the allow-list exactly: no `client_*`, `amount`, `expert_amount`, `platform_fee` or `currency` keys anywhere;
   - entries are filtered `>= since`;
   - a bad or old `since` ⇒ 400 or clamp;
   - `partial` is computed correctly in both directions;
   - `to_name` comes from the entry's `to_name` first, then the fallbacks; `title` is cut to 80;
   - bridge 404 ⇒ `missing`; bridge 500 or timeout ⇒ `files_ok:false, entries:null` (not `[]`);
   - platform 401/403 does not log the admin out (the response is not 401);
   - exactly one platform call.
3. B2:
   - `auto_assign` passes `explicit`, `updated_at` and `updated_by` through; a bad `auto_assign` type ⇒ `null`;
   - `release_hours` is `null` unless it is a positive int;
   - settings fails, policies ok ⇒ 200, `auto_assign: null`, `release_hours` set; policies fails, settings ok ⇒ 200, `auto_assign` set, `release_hours: null`; both fail ⇒ 200 with both `null`; at most two platform calls;
   - history is filtered to the three actions; every `at` carries a zone.
4. B3: `ai_daily_usage_state` values map correctly; `cap 0` ⇒ `null`; `counter_error` ⇒ `null`; **`ai_call` is never called**; no platform call.
5. B4/B5:
   - B4 without `confirmed:true` ⇒ 400; text length and control-char cleanup; the 51st rule ⇒ 409; stored `status` is `requested`;
   - `created_by` comes from the token and never from the body (a body `by`/`created_by` is ignored);
   - an AuditLog row is written on success only;
   - B5 rejects a bad id with 400, an unknown id with 404, and deletes plus audits.
6. Switch path: `PUT /api/platform-expert-files/settings` from the screen carries `confirmed:true`. This is an existing route; assert through the shots fake.

**node (pure, via `v2_node`):**
1. `v2sBrainEntries`: counts, dedupe, the founder-change count, `null` on failure, «على الأقل» when partial.
2. `v2sBrainLogFromInbox` includes fyi rows: a file auto-assigned 1 h ago (still in its claim window, `fyi:true`) counts. This pins the D1 gap where `v2BrainLog` received only non-fyi rows.
3. `v2sBrainRules`:
   - `auto_assign` true/false/null ⇒ switch/switch/chip «غير متاح بعد»;
   - `move` with `assign` true ⇒ chip «وحده»; false ⇒ «يسألني» and the alert sentence; null ⇒ chip «غير متاح بعد», the original sentence, and the line «تعذّر جلب حالة التوزيع»;
   - chips use only «وحده», «وحده دائمًا», «يسألني», «متوقّف», «غير متاح بعد», «لم تُبنَ بعد» (never «يسألك»);
   - a platform alert «حارس المهلة والاسترداد: متوقّفة منذ 5 ساعة…» marks every `sla` rule «متوقّف»;
   - `release_hours` 72 ⇒ «٣ أيام» (via `U(3, ['يوم','يومان','أيام','يومًا'])`); 36 ⇒ «٣٦ ساعة», `null` ⇒ the no-number sentence;
   - invite generation `null` ⇒ «الجيل: غير متاح بعد»;
   - every sentence starts with «عندما» and contains no «⇒».
4. `v2sBrainLine`: each of the five cases and their priority.
5. `v2sBrainHelpers`: plain labels with no Latin letters; master first; `count` = number of agents; `canRunAll` false when `remaining < count` (tested with 11 and with 4 agents); `canRun`/`canRunAll` false while `running`; `dataOnly` chip.
6. `v2sBrainTime`: `'2026-10-30T22:30:00'` (no zone) equals `'2026-10-30T22:30:00Z'`; a stamp with `+02:00` is unchanged; with `since` = local midnight in Cairo (UTC+2/+3), a report stamped `2026-10-30T21:30:00` (no zone) counts as the next local day, not today.
7. Tile agreement: with B1 loaded, `v2Tiles(Q, {…, brainToday: n}).brain.count === n` and equals `v2sBrainEntries(...).autoCount`; `brainToday: null` ⇒ the tile is failed (no number); `undefined` ⇒ today's `v2BrainLog` result.
8. Copy scan: every string literal in `v2s/brain.js` (toasts included) and the `v2s:brain` block has no «يقوّم», «اعكس», «لما », «⇒», «الكنسة», «نداء», «الوضع الافتراضي», «التشغيلات», «✓», no Latin word or Latin digit (emails excepted) and no headline starting with «الذكاء».

**static:**
- `index.html` has the block markers and exactly the two brain lines in order.
- The `V2SEC` dispatcher exists once and sits after the D3 line.
- The `SECTIONS` brain entry is exactly as in §1 (label «العقل», the new `desc`).
- `sectionFor('ai')` ⇒ `brain/helpers`; `#ai` ⇒ `brain/helpers`; `#s/brain/log` round-trips.
- `v2s/brain.js` contains no `<h1` and does not call `EP.runAgents` or `EP.expertFileAutoAssign`.
- `v2-home.js` passes `brainToday` from `V2SEC.brain.tileCount`; `v2-d2.js` uses it too.
- The Dockerfile copies `v2s` and `v2_*_routes.py`.
- app.py has the guarded registration line before `# ---- v2 section routes end`.

**Old suites to re-run file by file:**
- `test_v2_d1.py` and `test_v2_d1b.py`. The latter needs a minimal shared edit: line 99 expects `['log','سجل اليوم','home']`, which becomes `['log','القواعد وسجل اليوم','v2s_brain']`. Line 163, `('home', {'v2mode':'brain'}) ⇒ ('brain','log')`, is removed or changed to expect `('home','board')`, because the log tab is no longer the home module. If a D1-B test pins the brain section's `desc`, update it to the new text.
- `test_v2_d2.py`, `test_v2_d3.py`, `test_dash_ia_structure.py`.
- The port-binding tests are re-run outside the sandbox by the main session.

---

## 9) Shots (`backend/tests/uiharness/v2_shots_brain.py` → `docs/v2/final/shots-brain/`)

Sizes: desktop 1440×900 (`d`), tablet 820×1180 (`t`), mobile 390×844 (`m`). Each shot is taken at all three unless noted.
1. `01-rules-log`: auto-assign on, 4 auto entries today (one `timeout`, one changed by the founder), all runs fresh, 2 helper reports today. Desktop: the brain line with the two discs is the first thing under the tabs (no second heading, no photo), rules and log side by side, «قاعدة تريدها» at the bottom of the rules card. Tablet and mobile: the «القواعد | سجل اليوم» switcher on «القواعد», groups folded except the first; plus `01b` with the switcher on «سجل اليوم».
2. `02-auto-off`: the switch on «يسألني», 3 files waiting, and the brain line with «افتح الملفات».
3. `03-confirm-off`: the confirmation sheet to stop auto-assign.
4. `04-confirm-on`: the confirmation sheet to start it, with «ينتظر الآن».
5. `05-stopped-run`: an `sla` alert, so the file rules show «متوقّف» and the brain line shows the alert.
6. `06-sources-down`: opsQueue failed, B1 failed with inbox fallback rows, B2 failed. Every unavailable element shows «غير متاح بعد» (`assign` and `move` both «غير متاح بعد») and the notes are visible (on tablet/mobile, shot both switcher positions).
7. `07-empty-day`: nothing happened today, and the elephant shows (log view on tablet/mobile).
8. `08-requested-rule`: after saving «لا توزّع ملفات الخليج على خبير من مصر» with one press: the «قواعد طلبتها» group with «لم تُبنَ بعد» at the end of the rules card, then the box; plus the delete confirmation.
9. `09-rule-sheet`: the sheet of `assign` with «متى يعمل» and the history.
10. `10-helpers`: the brain line with the disc «تحديثات اليوم» and «حدّث الكل» (no second heading, no photo), master plus 10 cards, one «أرقام فقط».
11. `11-helper-sheet`: a helper's report sheet.
12. `12-helpers-cap`: B3 `blocked`, with every «حدّث» disabled and the brain line.
13. `13-run-all-confirm`: the «حدّث الكل» sheet, with the count taken from the fixture's agents.
14. `14-running`: after one press on a card's «حدّث» (the fake delays its answer): every run button disabled, the pressed one reads «جارٍ الكتابة…». The script presses «حدّث» a second time and «حدّث الكل», then lets the fake answer: **exactly one** request reached `/api/ai/agents/run`. Then the toast «كُتب تقرير «…»» is visible.
15. `15-old-link`: opening `#ai` with the shell on lands on `#s/brain/helpers` in the new look (desktop and mobile).
16. `16-flag-off`: `#ai` with the flag off shows the old `viewAI` unchanged (desktop only, as proof).
17. `17-tile`: the board with B1 loaded: the brain tile shows the same number as disc 1 in shot 01 (desktop only).

The script fails on any of:
- horizontal page scroll at any size;
- a target under 44px; on mobile, a `<button>` or `[role=radio]` under 52px;
- visible «0», «null», «NaN», «undefined» or «[object Object]» where a value belongs;
- Latin text outside emails and helper-written blocks;
- the texts «اعكس», «لما », «⇒», «الكنسة», «نداء», «✓» in the page or in any toast;
- more than one `h1` in the page;
- any request outside the fake platform and Google Fonts;
- any write without `confirmed:true`;
- any request to `/api/ai/agents/run` other than those caused by the run buttons the script presses on purpose, which the fake answers without an AI call.

Re-run `v2_shots.py d1b` (brain tab label check: the line «('brain','log','العقل')» checks the **section** label, so it still holds) to prove nothing else broke.

---

## 10) Shared edits (keep minimal; list them in the report)
1. `dashboard-cloud/index.html`: the `V2SEC` dispatcher line in `renderView()`, unless it already exists, plus the two lines inside the `v2 sections` block.
2. `Dockerfile`: `COPY backend/v2_*_routes.py /app/` and `COPY dashboard-cloud/v2s /app/dist/v2s` (identical lines for all sections).
3. `backend/app.py`: the marker `# ---- v2 section routes end` (if missing) and the one guarded registration line.
4. `backend/tests/test_v2_d1b.py`: the two brain expectations (§8), and the brain `desc` if pinned.
5. `dashboard-cloud/v2-logic.js` `SECTIONS` brain entry (§1) — the `desc` text.
6. Tile agreement (§4.8): `dashboard-cloud/v2-home.js` (one `extras.brainToday` line), `dashboard-cloud/v2-logic.js` `v2Tiles` brain tile (number / `null` / `undefined` branch, ~3 lines), `dashboard-cloud/v2-d2.js` `gather()` `brainToday` (one expression).

---

## Decisions (on the expert review, revision 2)

All review points were applied. Where the fix differs from the reviewer's wording:
- **D1 — No header card.** Applied as proposed. The section title and description live in `SECTIONS` and are drawn by the shell. The numbers moved to discs on the brain line. Each tab has one `h1` only (the shell's), and the shots check it.
- **D2 — Run lock.** Applied. The module does not call `EP.runAgents` at all (it neither sets a loading state nor returns a promise); it calls `EP.api` itself, under `S.running`.
- **D3 — Toasts.** Chose the direct `EP.api` option over a `{quiet:true}` flag, because `EP.runAgents` also has to return a promise and the auto-assign error mapping (`efFailed`) is colloquial too. The module therefore writes the side effect that `EP.expertFileAutoAssign` had (`EP.data.efSettings`), and its own error strings. No edit to `dashboard-api.js`.
- **D4 — Tile agreement.** The reviewer's location was not exact: `dashboard-cloud/v2-logic.js:1012` reads `opts.brainToday` inside `v2Tickets` (the files board header, fed by `v2-d2.js:58`), while the board tile in `v2Tiles` counts `v2BrainLog(rows)` and does not read `extras.brainToday` at all. So there are **three** counts, not two. The fix covers all three: `extras.brainToday` in `v2-home.js`, a branch in `v2Tiles`, and the D2 `gather()` expression. While B1 has not loaded yet, both keep their current count (`undefined`), so nothing shows a false failure on first paint.
- **D5 — Requested rules.** Applied, with one change: the stored status value is `requested` (not `draft`) to match the new wording. B4 still requires `confirmed:true`; the single button sends it.
- **D6 — Mobile sizes (review item cut off in the message).** Interpreted as the conflict between «switch or chip full width» and «every segment ≥52px»: chips are labels, not targets, so they stay compact; only the real switch goes full width. The 52px rule on mobile applies to `<button>` and `[role=radio]`; links stay ≥44px. The row is a `<div>` with a title button and a separate control, so no control is nested inside a button.
- **D7 — Rows.** The sentence moved to the rule sheet, as proposed. A row of the «قواعد طلبتها» group has no sheet, so its title is plain text.

---

## Platform needs

None of these block this round. Without them the screens say what is missing and show only what exists.

**P1 — A log of every automatic action** (it feeds the log, the monthly number and future «اعكس»):
- New collection `ops_auto_log`, written once per action. Write it inside the same guarded writes that perform the action: sweep lanes, `auto_assign_file`, course offer auto-accept, invite reminders, coach emails and comment auto-approval. A write failure never blocks the action.
- `GET /api/bridge/ops/auto-log?since=<ISO>&until=<ISO>&limit=<1..500, default 200>` (secret-guarded, newest first) returns:
```json
{ "rows": [ { "id": "uuid", "at": "ISO", "rule": "assign|move|unclaimed_refund|consult_refund|release|case_release|urgent|reminder|offer_accept|live|session_remind|invite_remind|coach|comment_approve",
              "target": { "kind": "expert_file|consultation|case|course_offer|course|invite|learner|comment", "id": "…", "title": "…" },
              "who": { "email": "…", "name": "…" } , "amount": 0, "currency": "EGP", "note": "…",
              "undo": { "action": "unassign", "until": "ISO" } } ],
  "total": 0, "partial": false, "counts_by_rule": { "assign": 0 } }
```
- `who`, `amount`, `currency` and `undo` are `null` when they do not apply.
- `counts_by_rule` is computed in the store for `[since, until)`. It feeds «مهمة هذا الشهر».
- Dashboard proxy (next round): `GET /api/v2/brain/auto-log`.

**P2 — The rules' real numbers and on/off state, in one read:**
- `GET /api/bridge/ops/rules` returns:
```json
{ "rules": [ { "key": "assign", "on": true, "switchable": true },
             { "key": "move", "on": true, "switchable": false, "values": { "claim_hours": 12, "urgent_claim_hours": 2 } },
             { "key": "unclaimed_refund", "on": true, "switchable": false, "values": { "refund_after_hours": 48 } },
             { "key": "consult_refund", "on": true, "switchable": false, "values": { "reply_hours": 24, "verify_hours": 48 } },
             { "key": "release", "on": true, "switchable": false, "values": { "after_hours": 72 } },
             { "key": "case_release", "on": true, "switchable": false, "values": { "after_days": 7 } },
             { "key": "first_review", "on": true, "switchable": false, "values": { "first_n": 3 } },
             { "key": "invite_remind", "on": true, "switchable": false, "values": { "after_days": 3 } },
             { "key": "coach", "on": true, "switchable": false, "values": { "idle_days": 7, "cooldown_days": 14 } } ] }
```
- The values are read from the same functions the code uses (`claim_hours()`, `assign_alert_hours()`, `urgent_claim_hours()`, `EP_POLICY`, `EXPERT_REVIEW_FIRST_N`, …), so the screen can put real numbers in the sentences.

**P3 — A real undo for an automatic assignment (enables «اعكس»):**
- `POST /api/bridge/expert-files/{id}/unassign` with body `{by, confirmed: true}`.
- Allowed only while `status == 'assigned'` (pre-claim) **and** the last `assign_log` entry is `by:'auto'`.
- It returns the file to waiting for assignment and pushes `assign_log {by:'founder', reason:'undo'}`, which stops the auto pick from re-sending it to the same expert in this wave. It notifies the expert «moved», keeps `claim_deadline_at` unchanged, and audits.
- 409 when the file is already claimed or the race is lost.
- Dashboard: `POST /api/v2/brain/undo/<file_id>` with `confirmed:true`. The log button «اعكس» appears only on entries with `undo` in P1.

**P4 — Founder decision needed before any build:** should the money rules A3, A4, A5, A6 and A7 get a «يسألني» mode? Today they are client promises («بنوعد باسترداد تلقائي»), so this spec shows them as «وحده دائمًا» with no switch. If the founder wants a switch, each needs a platform setting with the same shape as `auto_assign`: `GET/PUT /api/bridge/ops/rules/{key}` with body `{on, by, confirmed}`. While a rule is off, its due items go to «ابدأ القرارات» as decision cards. Not built in this round.

**P5 — Fields on the file list row** (smaller alternative to P1 for files only): add `refunded_at`, `refund_reason`, `closed_at` and `closed_by` to `_bridge_row`. The brain's log could then show «ردّ مبلغ «…» لأن أحدًا لم يستلمه» and «تحرّر أجر «…» بعد التسليم» from `status=all` today.

**P6 — Zone on helper report times** (dashboard, small): `D:app.py:8494` sends `created_at.isoformat()` without a zone. This round guards it on the front end (`v2sBrainTime`); adding `+00:00` at the source would fix the old screens too.
