# FINAL · «الناس والدعوات» — every people screen rebuilt in the new style

**Section key:** `people` · **Worktree:** `.worktrees/people` · **Branch:** `final-people`
**Founder order (2026-10-30):** «ابدأ الجولة… الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا».
This is final work. Nothing inside this section keeps the old look, and **no «كل السجلات» tab is needed** (§12).

**Reference style:** D1-B shell (`v2-shell.*`), D2 tickets and person page (`v2-d2.*`), D3 money screens (`v2-d3.*`).
**Concept boards:** `POS-Tickets.dc.html` (columns of tickets with a coloured strip, one main button, mobile column switcher), `Person.dc.html` (one person, all roles), `POS-Home.dc.html` (paper, photos, wine).

**Hard limits for the build:** zero real network calls in tests and shots (no platform, no email, no Telegram, no AI); no push, no deploy; `git add` with explicit paths only.

---

## 0) What the founder gets

1. One place for everyone knocking at the door: visitors waiting to be let in, people on the waiting list, invites waiting for approval, people applying to offer a service, and founding experts. Each one is a ticket with one main button.
2. Invites as a pipeline (sent ⇒ opened ⇒ joined), with counts that never lie and a WhatsApp reminder one tap away.
3. All accounts as one clean, searchable list with five role chips. Each row has one button, «افتح صفحة الشخص». Account actions live on the person page under «إدارة الحساب», in a sheet of three parts.
4. Messages as conversation tickets: site contact form, messages left in the platform chat, and follow-up requests from the chat. A reply sent by mail or WhatsApp ends with one button, «نعم، علّمها منتهية».

Revision 2 (after the expert review) is recorded in «Decisions» at the end of this file.

No new roles, no new decision paths, and no money actions anywhere in this section.

---

## 1) Tabs (the `people` entry in `SECTIONS`, `dashboard-cloud/v2-logic.js`)

| # | Tab key | Label (exact) | `mod` | What it shows |
|---|---|---|---|---|
| 1 | `invites` | «الطلبات» | `invites` (old module name, now drawn by the new file) | Everyone waiting for a decision to come in (§4) |
| 2 | `pipeline` | «الدعوات» | `v2p_invites` (new pseudo module) | The invite pipeline, new invite, invite settings (§5) |
| 3 | `users` | «المستخدمون» | `users` (old module name, now drawn by the new file) | The account list (find one person); «إدارة الحساب» opens from the person page (§6) |
| 4 | `messages` | «الرسائل» | `inbox` + `st {activeFilter:'t:messages'}` + `m {activeFilter:['t:messages']}` (unchanged) | Conversation tickets (§7) |
| — | `person` | «صفحة الشخص» (hidden) | `v2person` (D2, unchanged) | The person page |

Exact entry:

```js
{ key: 'people', label: 'الناس والدعوات', img: 'people', desc: 'من ينتظر الدخول، والدعوات، والأعضاء، والرسائل', tabs: [
  T('invites', 'الطلبات', 'invites'),
  T('pipeline', 'الدعوات', 'v2p_invites'),
  T('users', 'المستخدمون', 'users'),
  T('messages', 'الرسائل', 'inbox', { activeFilter: 't:messages' }, { activeFilter: ['t:messages'] }),
  hiddenTab(T('person', 'صفحة الشخص', 'v2person'))
] },
```

### Why the tab keys are what they are
The keys and mods are chosen so that **no old link breaks and no shared table changes:**
- `#invites` is used by Telegram alerts 55–61 (visitor asks to be let in, member invite awaiting approval, waiting list, stalled invites, an invitee who finished the journey; `DASHBOARD-MAP` §ج). It still lands on `people/invites`, which is now «الطلبات». Alerts 55–57 and 59 find their item there directly. Alerts 60 (stalled invites) and 61 (journey finished) are about the pipeline. Checked in the platform: today both are text-only (`invites.py` ≈1824 `founder_alert_text("invites_stalled_digest", …)`, `invite_journey.py` 1070 `notify_ops(_ops_text(…))`), with no dashboard button, so the founder reaches the dashboard through «الطلبات» (the people tile). That is why «الطلبات» carries a second header line pointing to «الدعوات» whenever stalled or expiring invites exist (§9 B1-g). Adding a button to `#s/people/pipeline` on those two alerts is Platform need P6.
- The people tile on «اللوحة» calls `goOps('invites')` (`v2-home.js:201`), so it lands on «الطلبات» too. Its badge counts visitors, invites awaiting approval, join requests, and founding leads (`v2-logic.js` `T.people`), which are the four columns of that tab.
- `#users` stays on `people/users`. `#messages` and the inbox chip `t:messages` stay on `people/messages`. `ALIASES` and `REDIRECTS` are untouched, so `test_the_redirect_aliases_carry_the_same_inner_state_as_REDIRECTS` keeps passing.
- `focusUser(email)` (`index.html:5387`, from «اعرض الحساب») sets `pendingUserFocus` and calls `go('users')`. The new users screen reads it and opens that person page (§6.6).

### How the new file draws old module names
`v2s/people.js` registers `window.V2SECT.people = { owns, render }`.

```js
owns(mod) = !!(window.V2SHELL && V2SHELL.on) && (
  mod === 'invites' || mod === 'users' || mod === 'v2p_invites' ||
  (mod === 'inbox' && host.state().section === 'people' && host.state().tab === 'messages'))
```

- Flag off, or a non-admin role (the shell is admin-only) ⇒ `owns` is false and the old `viewUsers`/`viewInvites`/inbox render exactly as today. The employee role keeps its read-only old «المستخدمون».
- `v2OpenSection` sets `V2S` before `renderView`, so `host.state()` is already right when `owns('inbox')` is asked.
- The «رسائل» chip inside «كل الوارد» (home section) keeps drawing the old inbox there. That is the home section's screen, not ours. `v2Reconcile` may relabel the header to people/messages until the next render. This edge case is listed in §17.

---

## 2) Wiring (parallel-safe)

New files only:
- `dashboard-cloud/v2s/people.js`: render, wire, sheets. No business logic.
- `dashboard-cloud/v2s/people.css`: every rule under `.v2p` (page) or `.v2pm` (inside a modal), using D3's tokens (`--wine:#9E2B4E; --paper:#FBFAF7; --paper2:#F6F1EA; --ink:#21262E; --red:#C8102E` (late/refused only); `--line:#E9E1D6; --amber:#8F5F00; --green:#187E4E; --mute:#6B665C`).
- Pure helpers go at the **end** of `v2-logic.js`, inside `// ===== v2s:people =====` … `// ===== /v2s:people =====`, as a separate IIFE that attaches `root.V2L.v2p = {…}`. Nothing above the marker changes except the `people` entry in `SECTIONS` and the one `v2Card` string in §17 item 6.
- `backend/tests/test_v2s_people.py` and `backend/tests/uiharness/v2_shots_people.py`.

Shared edits (minimal; full list in §17):
1. `index.html`, the `<!-- v2 sections begin -->` … `<!-- v2 sections end -->` block, created right after `<script src="v2-d2.js"></script>` if it is missing. Our two lines, in this order:
   ```html
   <link rel="stylesheet" href="v2s/people.css">
   <script src="v2s/people.js"></script>
   ```
2. `index.html` `renderView()`: **one** generic registry line, placed right after the D3 line (`if(window.V2_ON&&window.V2D3&&V2D3.owns(current))…`). It must be byte-identical across all sections so the merge is clean:
   ```js
   if(window.V2_ON&&window.V2SECT){for(var _k in V2SECT){if(V2SECT[_k]&&V2SECT[_k].owns&&V2SECT[_k].owns(current)){var _ap=document.querySelector('.app');if(_ap){_ap.classList.add('v2-bare');_ap.classList.remove('v2-inbox');}return V2SECT[_k].render(current,v);}}}
   ```
   (`v2-bare` removes the old white card frame. Removing `v2-inbox` hides the old topbar search on our messages tab, so `index.html:7810` never calls `renderInbox()` on a view it doesn't own.)
3. **No `backend/app.py` change and no new server file:** every source and action already exists (§13).

Registry object (`v2s/people.js`):
```js
window.V2SECT = window.V2SECT || {};
V2SECT.people = { owns: owns, render: render, manageBtn: manageBtn /* §6.6 hook */ };
```

Polling and ticking follow D2:
- A 400 ms signature check redraws when a loader state changes, except while a sheet is open (`#epModal`), an input inside `.v2p` has focus, or an action is running.
- A 60 s tick refreshes «منذ …» texts.
- Both stop when `owns(host.current())` is false.

---

## 3) Data sources (all existing; GET only)

| Key / call | Endpoint (dashboard ⇒ platform) | Fields we read | Used by |
|---|---|---|---|
| `EP.ensure('inbox')` ⇒ `window.INBOX`, `window.INBOX_FAILED`, `INBOX_TRUNCATED` | `/api/pending-users` (requested only), `/api/platform-join-requests?status=open`, `/api/founding-leads?limit=200` (non-terminal), inside the inbox loader | rows `apiKind ∈ {pending_user, join, founding}` with `who, email/personEmail, apiId, ts, puRole, puCountry, flagLabels, details[], serviceLabel, licensed, licenceMissing, licenceNote, note, statusLabel, infoRequest, attachments[], nextStatus, fSpec, fCountry, rejectNeedsReason, canRequestInfo`. Failure labels: `'زوّار ينتظرون الفتح'`, `'طلبات تقديم الخدمة'`, `'ليدات خبير مؤسس'` | «الطلبات» columns 1, 3, 4 |
| `EP.ensure('invites')` ⇒ `EP.data.invites` | `/api/invites?limit=200` ⇒ `/api/bridge/invites` | `rows[]: id, name, email, status, stage, roles, rolesLabel, specialtyLabel, invitedByLabel, invitedByUserId, generation, note, approvalNote, link, opened, registered, revoked, at, expiresAt, docRequested`; `count`; `counts{opened, roles_chosen, exercised, declared, registered}`; `missing` | «الطلبات» col 2, «الدعوات» |
| `EP.ensure('waitlist')` ⇒ `EP.data.waitlist` | `/api/waitlist?limit=200` | `rows[]: id, name, email, phone, note, roleLabel, specialtyLabel, countryLabel, status, at`; `count`; `missing` | «الطلبات» col 1 |
| `EP.ensure('pendingUsers')` ⇒ `EP.data.pendingUsers` | `/api/pending-users?limit=200` | `rows[]: id, name, email, phone, requested, rejected, requestStatus, note, roleLabel, specialtyLabel, countryLabel, signupCountryLabel, why, aiUsed, flagLabels, lastLogin, at, requestedAt`; `count`; `missing` | «الطلبات»: the «لم يطلبوا الفتح بعد» list, and the visitor chip in «المستخدمون» |
| `EP.ensure('inviteSettings')`, `EP.ensure('founding')`, `EP.ensure('inviteVideos')` | `/api/settings/invites`, `/api/settings/founding`, `/api/settings/invite-videos` | `welcome_video_url, platform_video_url, member_invite_quota, invite_approval_from_generation` · `open` · `trainer, lawyer, consultant, researcher, graduate, multi`; `missing`/`forbidden` | settings sheet; approval-generation fact in col 2 |
| `EP.inviteDetail(id, ok, err)` | `GET /api/invites/<id>` | `inviter, user.phone, years, generation, focus, video_source, video_url, timeline[], exercises[], proposals[], demo, declaration, founding` | invite detail sheet |
| `EP.ensure('users')` ⇒ **`EP.data.users.raw`** (not `window.USERS`) | `/api/platform-users` ⇒ `/api/bridge/users?limit=500` | `id, full_name, email, phone, role, trainer_status, plan_id, is_active, created_at, last_login_at, segment, tags, is_test` (the loader's `window.USERS` drops `last_login_at`/`is_active`, which is why we read `raw`) | «المستخدمون» |
| `EP.ensure('dashboard')` ⇒ `EP.data.metrics.raw.customers` | `/api/platform-metrics` | `total, members, admins, staff, investors, trainers_approved, paid_plan, signups_today, signups_7d` | users header facts and chip counts |
| `EP.ensure('packages')` ⇒ `EP.data.packages.packages` | `/api/packages` | `id, name` | plan selector in «إدارة» |
| `GET /api/platform-users?search=<q>` | same proxy, with `search` | same as users | server search when the list is truncated |
| `EP.purgeCheck(id)` | `GET /api/users/<id>/purge-check` | `purgeable, reason, linked` | delete sheet |
| `EP.ensure('messages')` ⇒ `EP.data.messages` | `GET /api/messages` (dashboard SQLite, site contact form) | `id, name, email, phone, topic, body, status(new/replied), at` | «الرسائل» col 1 + «رُدّ عليها» list |
| own fetch `EP.api('/platform-messages?status=new')` | `/api/bridge/messages?status=new` | `id, from_name, from_email, subject, body, contact_phone, created_at` (fallbacks: `name, user_name, email, user_email, topic, text, summary`) | «الرسائل» col 2 |
| own fetch `EP.api('/platform-leads?status=new')` | `/api/bridge/leads?status=new` | `id, full_name, phone, experience, want, from_email, created_at` (fallbacks: `name, email, need, topic, summary`) | «الرسائل» col 3 |

**Why messages and leads are fetched again:** the inbox loader swallows their failures (`.catch(function(){})`, `dashboard-api.js` near 2060 and 2085), so a failure there looks like «no messages». It also reads field names the platform doesn't send (`name/email` instead of `from_name/from_email`, `need` instead of `want`). The tab keeps its own `{state, rows}` per source so a failure shows as a failure. Writes still go through `EP.resolveInboxItem` (§8).

---

## 4) Tab «الطلبات» (`invites`): everyone waiting to come in

### 4.1 Layout
- **Desktop ≥1180:** max-width 1360.
  - **Header row:** brain line (§9 B1) on the right, with the 30 px brain avatar `v2/img/brain-avatar.jpg`. When B1-g applies, a second line under it links to «الدعوات». «حدّث» (`.v2p-btn2`) on the left.
  - **Failed/partial strips** under it (§10).
  - **Board:** 4 equal columns (`grid-template-columns:repeat(4,minmax(0,1fr))`). Each column has a 5 px top border in its tone, a header with the label and a count pill, then the ticket list (first 6, then «اعرض الكل (N)»).
  - **Below the board:** the collapsible list «سجّلوا ولم يطلبوا الفتح بعد» (§4.4).
- **Tablet 820:** 2 columns × 2 rows. Same tickets.
- **Mobile (≤760, checked at 390):** the column switcher is D2's own strip, reused as is: markup `<div class="v2d-seg" role="tablist">` with `<button class="v2d-segb tone-…" role="tab" aria-selected data-col>` holding `<span>{short}</span><b>{count}</b>` (rules in `v2-d2.css`, same 60 px height, same breakpoint 760). The dashboard keeps one switcher style. The strip uses each column's **short** label (§4.2); the full label stays in the column header. Showing one column at a time is our own rule, `.v2p-cols[data-active="x"] .v2p-col[data-col="x"]`, because D2's rules are keyed on D2's column names. Tickets are full width. Buttons are 52 px. No horizontal page scroll.
  - The first visible column is the first one with items. The founder's choice is kept while they stay on the tab.

### 4.2 Columns

| Col | Key | Label (exact, column header) | Short (mobile strip) | Tone | Items from | Order |
|---|---|---|---|---|---|---|
| 1 | `visitors` | «ينتظرون فتح المنصة» | «الزوّار» | amber | (a) inbox rows `apiKind==='pending_user'`; (b) `EP.data.waitlist.rows` with `status==='new'` | oldest request first (`ts` / `at`) |
| 2 | `approval` | «دعوات تنتظر موافقتك» | «الدعوات» | amber | `EP.data.invites.rows` with `status==='awaiting_approval'` | oldest first |
| 3 | `join` | «طلبات تقديم خدمة» | «الخدمات» | ink | inbox rows `apiKind==='join'` | oldest first |
| 4 | `founding` | «خبراء مؤسسون» | «المؤسسون» | green | inbox rows `apiKind==='founding'` | oldest first |

Count pill = number of items, or «—» with the column in the failed state (§10). Never 0 for a failed source.

**Column 1 has two sources** (the inbox and the waiting list). Its state is computed from both:
- both ready ⇒ `ready`, count = a + b;
- both failed or missing ⇒ `failed`, count «—»;
- **one ready, the other failed or missing** ⇒ state `mixed`. The pill shows the ready count followed by «+؟» (for example «٣+؟»). Inside the column, after the tickets that did arrive, a line: «تعذّر جلب {label} — أعد المحاولة» (label from §10: «الزوّار» or «قائمة الانتظار»; «أعد المحاولة» reloads that key only). The label also goes to the page strip and to B1-f. A missing waiting-list bridge uses the same line with «قائمة الانتظار غير متاحة بعد من المنصة».

### 4.3 Ticket anatomy
Same visual language as D2 `.v2d-t`:
- a white card, radius 16;
- a coloured strip on top with the tag on the right and the age on the left;
- body: title, a sub-line, the brain line (§9), an optional warning line (amber background), then actions:
  - **title link rule:** the title is a person-page link (`data-person`) **only when the item belongs to an existing account**: inbox `pending_user`, inbox `join` with an email, inbox `founding` only when its email is found in `EP.data.users.raw`, and invites with `stage==='registered'`. Waiting-list entries and invites that have not finished are plain text (they have no account, and their person page would be empty). Their email shows as an ltr line inside the detail sheet;
  - one full-width primary `.v2p-btn1` (wine, 48 px; 52 px on mobile);
  - up to two secondary text buttons (`.v2p-btn2`, ≥44 px).
- Tapping the card body (not a button) opens that item's detail sheet.

**Rule for every inbox ticket (cols 1a, 3, 4):** the strip tag, title, sub, brain, reason, warning, and primary label are taken **verbatim** from `L.v2Card(row, {now})`. The same request reads the same in «ابدأ القرارات» and here. This section never writes its own copy for those fields. Only the secondary buttons and the extra lines named below are ours. The one wording fix needed («مشبوه» is forbidden by §11) is made once, inside `v2Card`, as a shared edit (§17 item 6), so both screens change together.

**Col 1a · visitor who asked to be let in** (inbox `pending_user` row). The text below is what `v2Card` gives after the §17 item 6 edit:
- Strip: «زائر ينتظر الفتح» · `card.ageText`.
- Title: `card.title` (`row.who`). Sub: `card.sub` (`[puRole, puCountry]` joined with « · »).
- Brain: `card.brain` (name · country · age). Reason: `card.reason` («طلب فتح المنصة بعد التسجيل», or «يُفتح الطلب للمراجعة قبل فتح المنصة» when flagged).
- Warning, when `flagLabels.length`: `card.warn` = «يحتاج مراجعة: » + labels joined with « · » (server-computed labels, shown as they arrive).
- Primary:
  - not flagged: `card.primary.label` «افتح المنصة للزائر» ⇒ A1 `EP.decideInboxItem(row,'approve',null,'')`;
  - flagged: «افتح وراجع» ⇒ the visitor detail sheet S1.
- Secondary: «التفاصيل» ⇒ S1.

**Col 1b · waiting-list entry** (`waitlist` row, `status==='new'`):
- Strip: «من قائمة الانتظار» · age from `at`.
- Title: `name`, or «بلا اسم». Sub: `[roleLabel≠'—', specialtyLabel≠'—', countryLabel≠'—']` joined with « · ».
- Brain: «طلب دعوة من الموقع ولا يملك حسابًا بعد». If `note`, a second line: «سبب الطلب: » + note (truncated to 140 characters, escaped).
- Primary: «أرسل دعوة» ⇒ phone-confirm sheet S6.
- Secondary: «التفاصيل» ⇒ waiting-list detail sheet (name, email, phone, role, specialty, country, reason, date).

**Col 2 · invite awaiting approval** (`invites` row):
- Strip: «دعوة من عضو» · age from `at`.
- Title: `name`, or «بلا اسم». Sub: «الداعي: » + `invitedByLabel` + (generation != null ? « · الجيل » + ar(generation) : '').
- Brain:
  - when `inviteSettings.invite_approval_from_generation` is known: «دعوات الجيل {ar(n)} وما بعده تحتاج موافقتك قبل أن يعمل رابطها»;
  - otherwise: «تحتاج موافقتك قبل أن يعمل رابطها».
  - If `note`: «ملاحظة الداعي: » + note.
- Primary: «وافق على الدعوة» ⇒ `POST /api/invites/<id>/approve` (§8 A4).
- Secondary: «ارفض» ⇒ sheet S4.

**Col 3 · service application** (inbox `join` row; text from `v2Card`):
- Strip: `card.tag` («طلب انضمام») · age.
- Title: `card.title`. Sub: `card.sub` (service · licence · attachments).
- Brain: `card.brain`. Reason line: `card.reason`. Warning: `card.warn` («رقم القيد ناقص»).
- If `row.infoRequest` (status `needs_info`), an extra line: «طُلب من صاحب الطلب: » + infoRequest + « — بانتظار رده».
- Primary: `card.primary`:
  - «اقبل» ⇒ `EP.decideInboxItem(row,'approve')`;
  - or, when `licenceMissing`, «افتح وراجع» ⇒ join detail sheet.
- Secondary: «ارفض» ⇒ sheet S5 (reason required); «اطلب استكمالًا» ⇒ sheet S5b.

**Col 4 · founding expert** (inbox `founding` row; text from `v2Card`):
- Strip: `card.tag` («خبير مؤسس») · age. Title: `card.title`. Sub: `card.sub` (the lead's note, up to 150 characters). Brain: `card.brain` (name · specialty · country). Reason: `card.reason` («تواصل عبر واتساب ثم علّم الخطوة»).
- Primary: `card.primary.label` («تم التواصل» / «أُرسلت الدعوة» / «تم التحويل إلى مدرّب») ⇒ `EP.decideInboxItem(row,'approve')`, which writes `nextStatus`.
- Secondary:
  - «واتساب» = a link `https://wa.me/<digits>` built from `details[{k:'واتساب'}]`, digits and `+` only. Shown only if at least 8 digits.
  - «ليس مناسبًا» ⇒ confirm sheet ⇒ `EP.decideInboxItem(row,'reject')`.
- Detail sheet: the details (WhatsApp, specialty, experience, country, LinkedIn as an `https` link only), plus «أنشئ دعوة بهذه البيانات», which opens S7 prefilled with name, phone, and email.

### 4.4 «سجّلوا ولم يطلبوا الفتح بعد» (below the board)
- **Source:** `EP.data.pendingUsers.rows` where `!requested`. Both `requestStatus none` and `rejected` are included; rejected rows carry the chip «رُفض طلب سابق».
- **Collapsed by default.** Header: «سجّلوا ولم يطلبوا الفتح بعد ({ar(n)})». When `count > rows.length`, add «معروض {x} من {y}».
- **Row:**
  - name (person link) and email;
  - «سجّل منذ {ago}»;
  - last login: «آخر دخول {lastLogin}», or «لم يُسجَّل دخول بعد» when the field is empty;
  - questions used: «الأسئلة المستعملة: {ar(aiUsed)}», or «غير متاح بعد» when null.
- **Buttons:** «افتح المنصة» ⇒ A2; «احذف نهائيًا» ⇒ S9 delete sheet.
- These visitors appear here only, never as tickets, because they are not waiting on a decision. This matches the inbox rule at `dashboard-api.js` 1780.

### 4.5 Visitor detail sheet (S1)
- **Title:** name.
- **Rows** (labels exact; a missing value hides the row, it never shows «—»): «البريد», «الهاتف», «الصفة», «التخصص», «البلد», «بلد التسجيل» (`signupCountryLabel`), «سبب الانضمام», «سجّل في», «طلب الفتح منذ», «الأسئلة المستعملة», «يحتاج مراجعة».
- The IP address is **never shown** (technical).
- **Actions:**
  - «افتح المنصة» (primary) ⇒ A1 or A2;
  - «ارفض ويبقى زائرًا» ⇒ an inline textarea «سبب الرفض (اختياري) — يُحفظ على الطلب، فاكتب ما لا تمانع أن يقرأه صاحبه» (max 300), then the confirm ⇒ A3.
    - Why not «لا يراه صاحبه»: the platform stores the note in `users.invite_request.note` (`pending_access.py` `set_user_access`) and returns the whole `invite_request` to the visitor in `/api/auth/me` (`auth.py` 769) and `GET /api/invite-request` (`pending_access.py` 156). The visitor screen (`InviteRequest.jsx`) does not display it today, but the visitor can read it. We do not promise what the platform does not guarantee. Platform need P5 removes it from those responses; the label can change only after that.
  - «احذف الحساب نهائيًا» ⇒ S9.

---

## 5) Tab «الدعوات» (`pipeline`): the invite pipeline

### 5.1 Layout
One thing for the eye first: the brain line and the one main button.
- **Section header:** a gear icon button «إعدادات الدعوة» (44 px, `aria-label="إعدادات الدعوة"`, the same placement as the settings gear in «الشركة») opens S8. There is no «حدّث» on this tab: the 400 ms signature check already redraws when the loader changes.
- **Top row:** brain lines (§9 B2) with the avatar on the right; the single main button «+ دعوة جديدة» (`.v2p-btn1`, sheet S7) on the left.
- **Number cards** (4, like D3 `.v3-num`, 5 px top border). The old separate funnel strip is merged into these cards, so no number appears twice:
  - «أُرسلت»
  - «فُتحت» + the percentage of sent. Under it, one small muted line with the middle steps from `counts`: «اختيار الصفة {n} · تجربة مثال {n} · الشروط {n}» (each «غير متاح بعد» when `counts` is null).
  - «انضمّ» + the percentage of sent
  - «تنتظر موافقتك» (a link to «الطلبات»)
- **Board header:** the select «الداعي» (§5.4) sits right above the columns, because it filters the board only, with the note «الأرقام أعلاه لكل الدعوات».
- **Board of 4 columns** (§5.2).
- **Tablet:** cards 2×2, columns 2×2.
- **Mobile:** cards 2×2, the select full width, the D2 column switcher strip with short labels («تنتظر» · «في الطريق» · «انضمّ» · «توقّفت»), and full-width tickets.

### 5.2 Columns
`stage` comes from the row, as derived by the loader.

| Key | Label (exact) | Rows | Primary | Secondary |
|---|---|---|---|---|
| `waiting` | «لم تُفتح بعد» | `stage==='pending'` and not revoked | «انسخ الرابط» (A9; when `link` is missing the button is replaced by «الرابط غير متاح من المنصة») | «أرسل عبر واتساب» (wa.me invite text, §11) · «اسحب الدعوة» (S10) |
| `journey` | «في الطريق» | `stage ∈ {opened, roles_chosen, pain_seen, exercised, declared}` | «ذكّر عبر واتساب» (wa.me reminder text) | «التفاصيل» · «اسحب الدعوة» |
| `joined` | «انضمّ — آخر ٧ أيام» | `stage==='registered'` and joined within the last 7 days (`registered` date, else `at`) | «افتح صفحة الشخص» if `email` (person page), otherwise «التفاصيل» | — |
| `stopped` | «توقّفت» | `stage ∈ {expired, revoked}` or `status==='rejected'` | «أعِد إصدارها» (S11) | «التفاصيل» |

- `awaiting_approval` rows are **not** in this board. They live in «الطلبات» col 2, and the card «تنتظر موافقتك» links there. One place for each action.
- Columns are sorted newest first. The first 6 show, then «اعرض الكل (N)».
- `joined` and `stopped` hold no decision, so both are dimmed (opacity .9) and collapsed to 3. `joined` shows only the last 7 days; older joins sit behind «اعرض الكل ({N})», where N is every registered row. The card «انضمّ» still counts all of them.

**Ticket:**
- Strip: stage noun (§11) · «أُرسلت منذ {ago}». For `rejected`: «رُفضت».
- Title: name, or «بلا اسم». A person-page link only in `joined` (§4.3 title link rule).
- Sub: «الداعي: {invitedByLabel}» · `rolesLabel` · `specialtyLabel` (each only if not «—»).
- Third line, only in `waiting`/`journey`: «تنتهي بعد {n} يوم», or «انتهت مهلتها» (from `expiresAt`, in Arabic digits).
- Chip «طلب توثيق من خبير» when `docRequested`.
- Rejected: «ملاحظة الفريق: {approvalNote}» when present.
- Tap ⇒ invite detail sheet S12.

### 5.3 Counts (pure helper `v2p.pipeline`, §14)
- `sent` = rows − `awaiting_approval` − `rejected` (links that actually went out). `opened` = rows with `opened`. `joined` = rows with `registered`. `awaiting` = `awaiting_approval` rows.
- Percentages = `round(n*100/sent)` + «٪ مما أُرسل». Hidden when `sent===0`.
- Middle steps under «فُتحت» = `EP.data.invites.counts` (`roles_chosen`, `exercised`, `declared`) as is. `counts` null ⇒ each shows «غير متاح بعد».
- **Partial:** `count > rows.length` ⇒ the cards carry «من آخر {ar(rows.length)} دعوة» and a strip says «معروض {x} من {y} — الأعداد من المعروض فقط». See Platform need P1.
- **Missing bridge** (`missing`) or `state==='error'` ⇒ cards and their middle-step line show «غير متاح بعد», and the board shows the failed state (§10).

### 5.4 «الداعي» filter
- A select with: «كل الداعين ({n})», «المؤسس ({n})», then each member inviter by `invitedByUserId`, with `invitedByLabel` and their count, sorted by count, then «بلا داعٍ محدد ({n})» when n>0.
- **How a row is assigned (written in `v2p.pipeline`, nothing guessed):**
  - member = `invitedByUserId` is a non-empty string ⇒ key `u:<invitedByUserId>`;
  - founder = `invitedByUserId` empty **and** `generation` is `0` or `null`/missing ⇒ key `founder`;
  - anything else (no inviter id but `generation ≥ 1`) ⇒ key `none`, «بلا داعٍ محدد».
  - Options with n=0 are not listed (except «كل الداعين»).
- It filters the board only. The cards stay global and the board header says so: «الأرقام أعلاه لكل الدعوات».
- This replaces the old «حسب الداعي» grouping toggle.

---

## 6) Tab «المستخدمون» (`users`)

The list is for **finding one person**. Every action on an account happens on that person's page (`Person.dc.html`), under «إدارة الحساب». The list itself carries no management controls.

### 6.1 Layout
- **Header:** brain facts line (§9 B3) with the avatar, and «+ دعوة جديدة» (`.v2p-btn2`, S7) on the left (§6.7).
- **Search:** one input, «ابحث بالاسم أو البريد أو الهاتف» (`type=search`, 48 px, `dir=auto`).
  - The D2 person search bar is hidden on this tab only, via CSS: `.app.v2-shell:has(.v2p[data-tab="users"]) #v2sbar{display:none}`. One search box per screen.
  - Under the input, one status line (§6.4): searching, no result, or search failed.
- **Chip row:** five chips only (§6.2), single-select, each 44 px, then one button «تصفية» (44 px). The row wraps onto two lines at 390 rather than scrolling.
  - «تصفية» opens sheet S18 (§6.2). While a filter from S18 is active the button reads «تصفية ({ar(k)})», and a removable chip per active filter shows under the row («× مستثمرون», «× محامون», «× آخر دخول»).
- **List:** one row per person, the same on every width:
  - initial avatar · name (person link) · chips (§6.2) · email (ltr, muted);
  - one muted line: «{plan} · انضمّ {date} · آخر دخول {ago}»;
  - one button «افتح صفحة الشخص» (`.v2p-btn2`, 44 px; full width and 52 px on mobile). Tapping the row also opens the person page.
- The list shows 50 rows, then «اعرض ٥٠ أخرى».
- When `metrics.total > raw.length`, a line: «معروض {ar(shown)} من {ar(total)} — اكتب في البحث للوصول إلى الباقي».

### 6.2 Chips and the «تصفية» sheet (S18)
Counts are **exact** from `metrics.customers` when available. Otherwise they are counted from rows: exact if the list is not truncated, and with no number if it is.

**Visible chips (5):**

| Chip (exact) | Filter on rows | Count source |
|---|---|---|
| «الكل» | all | `total` |
| «أعضاء» | `role==='member'` | `members` |
| «مدرّبون» | `trainer_status==='approved'` | `trainers_approved` |
| «فريق العمل» | `role==='staff'` | `staff` |
| «زوّار» | email ∈ `pendingUsers.rows` emails | `pendingUsers.count` |

**Inside S18 «تصفية»** (title «تصفية الحسابات»; side-sheet pattern of §8; one primary «اعرض النتائج», plus «امسح التصفية»):
- «الصفة» (single-select, 44 px buttons): «الإدارة» (`role==='admin'`, `admins`), «مستثمرون» (`role==='investor'`, `investors`), «طلبات مدرّب» (`trainer_status==='pending'`, rows only), «حسابات تجريبية» (`is_test`, rows only). Picking one here replaces the visible chip choice (one role filter at a time).
- «التصنيف»: a select of segments and manual tags.
- «الترتيب»: «الأحدث انضمامًا» (default) or «آخر دخول».

Chip labels on rows (several allowed): «إدارة», «فريق العمل», «عضو», «مستثمر», «مدرّب», «طلب مدرّب», «زائر» (email in pendingUsers), «تجريبي», «موقوف» (`is_active===false`), the segment label, and each manual tag (gold). At most 4 show on a row; the rest become «+{ar(n)}».

Segment labels (copied into the helper, same values as `SEG_LABEL`): `individual` «أفراد», `employee` «موظفون», `government` «حكومي», `student` «طلاب», `lawyer` «محامون», `senior` «محامٍ خبير», `prof` «أستاذ جامعة», `trainer` «مدرّبون», `company` «شركات», `firm` «شركة محاماة», `grad` «خريج جديد», `influencer` «مؤثر أو رائد أعمال», `researcher` «باحثون», `prosecutor` «وكلاء نيابة», `unknown` (hidden).

### 6.3 Row fields
- **name:** `full_name || email`.
- **plan:** the package name from `EP.data.packages` by `plan_id`. Fallbacks: `free` «مجانية», `pro` «احترافية», `premium` «بريميوم», else «الباقة غير متاحة بعد».
- **«انضمّ»:** `dateText(created_at)`.
- **«آخر دخول»:** `agoText(last_login_at)`, or «غير متاح» when empty. We cannot tell «never» from «not recorded», so we never claim «لم يدخل».

### 6.4 Search
- **Local:** each keystroke (debounced 200 ms) filters `raw` over name, email, and phone, case-insensitive.
- **Server:** if `metrics.total > raw.length` and the query is at least 2 characters, it also calls `GET /api/platform-users?search=<q>` (≤80 chars). Results are merged by `id` and tagged «من البحث».
- **States** (the status line under the input; the list area shows the card where noted):
  - while the server call runs: «…نبحث في كل الحسابات» (the local matches stay visible meanwhile);
  - server failed: «تعذّر البحث في كل الحسابات الآن — النتائج من المعروض فقط»;
  - **no result** (local empty, and the server call finished empty or was not needed): a card in the list area «لا حساب يطابق «{q}»» with the hint «اكتب البريد كاملًا واضغط إدخال لفتح صفحة الشخص». `{q}` is escaped and shortened to 40 characters.
- An Enter on a full email that matches no row opens that person page.

### 6.5 «إدارة الحساب» sheet (S13), three parts
- **The only door** is the button «إدارة الحساب» in the person page header (§6.6). The list has no «إدارة» button.
- Side-sheet pattern (§8): 480 px on desktop, full screen on mobile, sticky header, close button 44 px.
- **Header:** initial avatar, name, chips, email (ltr), phone, «انضمّ {date}», «آخر دخول {…}».
- **Three parts,** top to bottom:

1. **«الدور»:** 4 segmented buttons (44 px): «إدارة», «فريق العمل», «عضو», «مستثمر»; the current one is ink.
   - Picking a different one opens confirm S14: «تغيير الدور من {old} إلى {new}». Then **A13**.
   - **Last-admin guard:** if the user is admin and the admin count ≤1, the other three are disabled with the line «هذا آخر حساب إدارة، فلا يمكن تغيير دوره».
     - Admin count = `metrics.admins` if known.
     - Otherwise, rows with `role==='admin'`, but only if the list is not truncated.
     - Otherwise the count is unknown: the guard applies, with the same line plus «(تعذّر التأكد من عدد حسابات الإدارة)».
2. **«الظهور والمدرّب»:**
   - Visibility, one button depending on `is_test`: «أخفِ الحساب من الواجهات العامة (تجريبي)» or «أعِد إظهار الحساب». Confirm S14 states the effect («يختفي الحساب من كل الواجهات العامة، وتبقى بياناته كما هي.» / «يعود الحساب إلى الظهور في الواجهات العامة.»). Then **A16**.
   - Trainer:
     - `trainer_status==='approved'`: «إلغاء اعتماد المدرّب» ⇒ S15.
     - `pending`: the line «طلب اعتماد مدرّب قيد المراجعة في «الدورات والمدرّبون»» + link ⇒ `openSection('courses','trainers')`.
     - otherwise: nothing. There is no «اعتمد كمدرّب» button: approval happens through the trainer application, as today.
3. **«المزيد»** (collapsed; its summary line shows the current values: «الباقة: {plan} · {ar(n)} وسوم»). When opened:
   - **الباقة:** shown only if `EP.data.packages` is ready. A select of package names and «احفظ الباقة». Confirm S14: «من {a} إلى {b}. لا يُحصَّل أي مبلغ بهذا التغيير.» Then **A14**. Packages failed ⇒ «الباقات غير متاحة بعد». Link «الأسعار والخصومات في «الفلوس»» ⇒ `host.openSection('money','prices')`.
   - **الوسوم:** input «وسوم يدوية — افصل بينها بفاصلة» (prefilled with tags joined by «، ») and «احفظ الوسوم». Split on `،` or `,`, trim, drop empties, max 20. Then **A15**. Under it, when `segment` is set: «تصنيف المحادثة: {label} — يُحدَّد تلقائيًا ولا يُعدَّل من هنا».
   - **الحذف:** «احذف الحساب نهائيًا» (red outline) ⇒ S9.

- After any successful write: the sheet stays open, the changed part shows a green line («حُفظ»), and `EP.reload('users')` runs.
- Errors show inside the part (`.v2p-err`), mapped through `V2.plainError`.

### 6.6 Opening the person page and «إدارة الحساب»
- **Person page (D2), required shared edit** (§17 item 5): a button «إدارة الحساب» in the person page header actions, next to «مراسلة», rendered by `V2SECT.people.manageBtn(email)` ⇒ `<button class="v2d-btn2" data-v2p-manage="{email}">إدارة الحساب</button>`.
  - `people.js` installs one delegated `click` listener for `[data-v2p-manage]`.
  - It finds the user in `raw` by email, or else via `GET /api/platform-users?search=<email>` (exact email match), then opens S13.
  - If there is no match: S13 does not open; a line under the button reads «لا يوجد حساب بهذا البريد على المنصة».
- `pendingUserFocus`, set by `focusUser()`: on render, `try { if (typeof pendingUserFocus==='string' && pendingUserFocus) { var em=pendingUserFocus; pendingUserFocus=null; V2D2.openPerson(em); } } catch(e){}`. «اعرض الحساب» therefore lands on that person page, where «إدارة الحساب» is one tap away.

### 6.7 Old actions that are intentionally not rebuilt
- «+ إضافة مستخدم» (`EP.createUser` ⇒ `POST /api/platform-users`): **this route does not exist** in `backend/app.py` (only GET at 1710). On failure the old code added a fake row locally. It is replaced by «+ دعوة جديدة», a button in the users header that opens S7, because accounts are created through invites or signup.
- «تعديل البيانات»: the old code only toasted «غير مفعّل».
- «اعتمد كمدرّب»: the old button was disabled and pointed to the inbox. Approval happens in courses/trainers.

---

## 7) Tab «الرسائل» (`messages`)

### 7.1 Layout
- **Header:** brain line (§9 B4) + «حدّث».
- **Board:** 3 columns on desktop; on tablet 2 + 1 under them; on mobile the D2 switcher strip of 3 (`.v2d-seg three`) with the short labels.
- **Below the board:** collapsible «رسائل رُدّ عليها ({n})» (site messages with `status==='replied'`, newest first, 20 shown). Each row: name · topic · date, plus «احذف», which opens **S17** (the same confirm sheet as the tickets) and then runs **A20**. No delete happens without S17.

### 7.2 Columns

| Key | Label (exact) | Short (mobile strip) | Source | Order |
|---|---|---|---|---|
| `site` | «رسائل الموقع» | «الموقع» | `EP.data.messages` with `status==='new'` | oldest first |
| `chat` | «رسائل من المحادثة» | «المحادثة» | own fetch `/platform-messages?status=new` | oldest first |
| `follow` | «طلبات تواصل» | «تواصل» | own fetch `/platform-leads?status=new` | oldest first |

**«أُرسل الرد؟» (one decision after leaving the dashboard).** A primary that opens the mail program or WhatsApp («ردّ بالبريد», «واتساب») changes nothing on the platform, so after the tap the ticket switches to a local state:
- the actions area is replaced by the line «هل أرسلت الرد؟», a primary «نعم، علّمها منتهية» (chat message ⇒ **A21**; follow-up request ⇒ **A22**, label «نعم، تمت المتابعة»), and a secondary «ليس بعد», which returns the ticket to its normal actions;
- the state lives in memory only (keyed by source and id). A reload or leaving the tab forgets it; nothing is stored;
- while a ticket is in this state, the 400 ms redraw keeps it (the signature check skips tickets in the «أُرسل الرد؟» state).

**Site ticket:**
- Strip: «من نموذج التواصل» · `agoText(at)`. The strip is amber when older than 24 h.
- Title: name. Sub: topic. Body preview: 3 lines, `-webkit-line-clamp:3`, escaped. Email (ltr, muted).
- Brain: «وصلت منذ {ago}». Add «· مرّ عليها أكثر من يوم» when older than 24 h.
- Primary: «ردّ» ⇒ S16. Secondary: «احذف» ⇒ S17.

**Chat message ticket:**
- Strip: «من المحادثة على المنصة» · age.
- Title: `from_name || name`, or «زائر بلا اسم». Sub: `subject || topic`. Body preview. Contact line: email (ltr) and `contact_phone` when present.
- Brain: same pattern as the site ticket.
- Primary:
  - «ردّ بالبريد» (`mailto:` with subject «ردًّا على رسالتك — البروفيسور»), when an email exists ⇒ then «أُرسل الرد؟»;
  - otherwise «واتساب» (wa.me/<digits>), when the phone has at least 8 digits ⇒ then «أُرسل الرد؟»;
  - otherwise «علّمها منتهية» ⇒ A21 directly.
- Secondary: «علّمها منتهية» ⇒ A21 (when it isn't already the primary), for messages answered some other way.

**Follow-up request ticket (lead):**
- Strip: «طلب تواصل من المحادثة» · age.
- Title: `full_name || name`, or «بلا اسم». Sub: «يريد: » + `want || need || topic || summary`. If `experience`: «الخبرة: » + experience.
- Brain: «طلب التواصل دون إنشاء حساب».
- Primary: «واتساب» (wa.me/<digits of phone>) when the phone has at least 8 digits; otherwise «ردّ بالبريد» when `from_email || email`; either one ⇒ then «أُرسل الرد؟». With neither: «تمت المتابعة» ⇒ A22 directly.
- Secondary: «تمت المتابعة» ⇒ A22 (when it isn't already the primary).

---

## 8) Actions: every button ⇒ an existing endpoint

Each write is a single function in `people.js`, `PX.call(spec)`. It:
- `POST`s or `DELETE`s through `EP.api` to the **same dashboard endpoint** the old `EP.*` function uses, with the same body;
- reloads the same loader keys;
- returns `Promise<{ok, error}>`;
- shows the result inside the sheet or ticket in standard Arabic.

The reason for not calling the old `EP.*` wrappers: they toast colloquial text («اتسحبت دعوة…», «اتغيّرت باقة…»), and most return no promise, so a sheet could not show its own error. `EP.decideInboxItem` and `EP.resolveInboxItem` already return `{ok,error}` and are called directly, as D1 does.

⛔ A static test asserts each path template below appears in `dashboard-cloud/dashboard-api.js` (so the two never drift). Every write needs a confirmation step, except approve on a non-flagged visitor/join/founding ticket, which is the same one-click decision as «ابدأ القرارات».

| # | Button (exact) | Call | Body | Reload keys | Mirrors |
|---|---|---|---|---|---|
| A1 | «افتح المنصة» (ticket) | `EP.decideInboxItem(row,'approve',null,'')` | (function) | inbox, pendingUsers (inside) | D1 |
| A2 | «افتح المنصة» (not-requested list, S1) | `POST /api/pending-users/<id>/access` | `{access:'member'}` | inbox, pendingUsers | `EP.setPendingUserAccess` 2815 |
| A3 | «ارفض ويبقى زائرًا» | `POST /api/pending-users/<id>/access` | `{access:'pending', note?}` | inbox, pendingUsers | same |
| A4 | «وافق على الدعوة» | `POST /api/invites/<id>/approve` | `{}` | invites | `EP.approveInvite` 3367 |
| A5 | «ارفض» (invite, S4) | `POST /api/invites/<id>/reject` | `{note}` | invites | `EP.rejectInvite` 3375 |
| A6 | «اقبل» (join) | `EP.decideInboxItem(row,'approve')` | — | inbox | D1 |
| A7 | «ارفض» (join, S5) | `EP.decideInboxItem(row,'reject',null,reason)` | reason required | inbox | `index.html` 1271 |
| A8 | «اطلب استكمالًا» (S5b) | `EP.decideInboxItem(row,'request_info',null,ask)` | ask required | inbox | `index.html` 1281 |
| A8b | founding next step / «ليس مناسبًا» | `EP.decideInboxItem(row,'approve'\|'reject')` | — | inbox | D1 |
| A9 | «انسخ الرابط» | clipboard (`navigator.clipboard.writeText`, then a `textarea` fallback) | — | — | `copyInviteLink` |
| A10 | «اسحب الدعوة» (S10) | `POST /api/invites/<id>/revoke` | `{}` | invites | `EP.revokeInvite` 3340 |
| A11 | «أعِد إصدارها» (S11) | `POST /api/invites/<id>/reissue` | `{}` | invites; then the link sheet with the returned `link` | `EP.reissueInvite` 3350 |
| A12 | «أنشئ الرابط» (S7) | `POST /api/invites` | `{name, email, phone, note}` | invites; then the link sheet | `EP.createInvite` 3324 |
| A12b | «أنشئ الرابط» (S6, waiting list) | `POST /api/waitlist/<id>/invite` | `{phone}` | waitlist, invites; then the link sheet | `EP.inviteFromWaitlist` 3443 |
| A13 | role change | `POST /api/platform-users/<id>/role` | `{role, email}` | users | `EP.setUserRole` 2703 |
| A14 | «احفظ الباقة» | `POST /api/platform-users/<id>/plan` | `{plan_id}` | users | `EP.setUserPlan` 2715 |
| A15 | «احفظ الوسوم» | `POST /api/platform-users/<id>/tags` | `{tags}` | users | `EP.setUserTags` 2727 |
| A16 | hide / show | `POST /api/platform-users/<id>/flag-test` | `{is_test, email}` | users | `EP.flagUserTest` 3485 |
| A17 | «ألغِ الاعتماد» (S15) | `POST /api/platform-trainers/<id>/deactivate` | `{reason, is_test, email}` | users, experts | `EP.deactivateTrainer` 3468 |
| A18 | «احذف نهائيًا» (S9) | `EP.purgeCheck(id)`, then `POST /api/users/<id>/purge` | `{note:''}` | users, pendingUsers, inbox | `EP.purgeCheck/purgeUser` 2840/2850 |
| A19 | «احفظ وافتح البريد» (S16) | `POST /api/messages/<id>/reply`, then `window.open(mailto…)` | `{body}` | messages, inbox | `EP.replyMessage` 3674 (without `window.prompt`) |
| A20 | «احذف» (site message, S17) | `DELETE /api/messages/<id>` | — | messages, inbox | `EP.deleteMessage` 3683 |
| A21 | «علّمها منتهية» | `EP.resolveInboxItem({apiKind:'message', apiId:id})` | — | inbox + own refetch | `EP.resolveInboxItem` 2875 |
| A22 | «تمت المتابعة» | `EP.resolveInboxItem({apiKind:'lead', apiId:id})` | — | inbox + own refetch | same |
| A23 | founding door (S8) | `POST /api/settings/founding` | `{open}` | founding | `EP.setFounding` 3383 |
| A24 | «احفظ إعدادات الدعوة» (S8) | `POST /api/settings/invites` | changed keys only | inviteSettings | `EP.setInviteSettings` 3400 |
| A25 | «احفظ الفيديوهات» (S8) | `POST /api/settings/invite-videos` | changed keys only | inviteVideos | `EP.setInviteVideos` 3416 |

No action in this section moves money. Plan assignment (A14) does not charge anything; the confirm sheet says so.

### Sheets
All sheets use the existing `openModal(title, html)` plus `closeModal()`. The `.modal` element gets the class `v2pm`. Buttons: the primary first, then «رجوع». The primary is disabled while running and shows «جارٍ التنفيذ…». The error line sits inside the sheet. No `alert`, `confirm`, or `prompt` anywhere (a static test checks this).

**Two sizes, one pattern each:**
- **Confirm sheets** (S4, S5, S5b, S6, S7, S7b, S9, S10, S11, S14, S15, S16, S17, S1): the centred modal, class `v2pm`, max-width 520, full width minus 16 px gutters on mobile.
- **Long sheets** (S8 settings, S12 invite detail, S13 «إدارة الحساب», S18 «تصفية»): class `v2pm v2pm-side`. Desktop and tablet: a side sheet 480 px wide, full height, attached to the left edge (RTL end). Mobile ≤760: full screen. Both: a sticky header with the title and a 44 px close button; the body scrolls inside the sheet, never the page. A confirm (S14) opened from a long sheet stacks above it and returns to it.

| Sheet | Title (exact) | Body | Primary |
|---|---|---|---|
| S1 | `{name}` | §4.5 | «افتح المنصة» |
| S4 | «رفض دعوة» | «سيُرفض طلب دعوة {name}. لن يعمل الرابط، ولن تُحسب من حصة الداعي.» + textarea «سبب الرفض — يقرؤه الداعي كما تكتبه (اختياري)» (max 300) | «ارفض الدعوة» (red) |
| S5 | «رفض طلب تقديم خدمة» | «يقرأ صاحب الطلب السبب كما تكتبه.» + textarea «سبب الرفض» (required, max 1000) | «ارفض الطلب» (red) |
| S5b | «طلب استكمال» | «يبقى الطلب مفتوحًا حتى يرد صاحبه.» + textarea «المطلوب بالضبط» (required) | «أرسل الطلب» |
| S6 | «رقم واتساب لصاحب الدعوة» | known phone: «هذا الرقم المكتوب في الطلب. تُربط الدعوة به ولا يفتحها غيره. أكّده أو عدّله.»; else: «لا يوجد رقم واتساب صالح في الطلب. اكتب الرقم الذي سترسل عليه الدعوة.» + input (ltr, tel) | «أنشئ الرابط» |
| S7 | «دعوة جديدة» | «الاسم» (required, ≥2), «رقم واتساب» (required, ≥8 digits; hint «تُفتح الدعوة بهذا الرقم وحده»), «البريد (اختياري)», «ملاحظة لك (اختياري)» | «أنشئ الرابط» |
| S7b (link) | «رابط الدعوة لـ{name}» | readonly link field (ltr) + «الرابط شخصي، أرسله بنفسك.»; when no link: «أُنشئت الدعوة لكن المنصة لم ترسل الرابط. ستجده في القائمة بعد التحديث.» | «انسخ الرابط» · «أرسل عبر واتساب» · «تم» |
| S8 | «إعدادات الدعوة» | three collapsed groups (§8.1), side sheet | one save button inside each open group |
| S9 | «حذف حساب {name} نهائيًا» | «جارٍ التحقق…»; then purgeable: «لا بيانات مرتبطة بهذا الحساب. الحذف نهائي ولا رجوع فيه.» + input «اكتب كلمة «احذف» للتأكيد»; blocked: «لا يمكن الحذف النهائي. السبب: {reason}» + the alternative «أخفِ الحساب كتجريبي بدلًا من ذلك» (A16) | «احذف نهائيًا» (red, enabled only when the input equals «احذف») |
| S10 | «سحب دعوة» | «ستُسحب دعوة {name}. يتوقف الرابط ولا يمكن إنشاء حساب به. يمكنك إرسال دعوة جديدة في أي وقت.» | «اسحب الدعوة» |
| S11 | «إعادة إصدار الدعوة» | «سيُنشأ رابط جديد لـ{name} بمهلة جديدة، وتبدأ الرحلة من أولها. يبقى الرابط القديم متوقفًا، فأرسل الجديد بنفسك.» | «أعِد إصدارها» |
| S12 | `{name}` | §8.2 | per state (§5.2) |
| S13 | «إدارة الحساب» | §6.5 (three parts), side sheet | per part |
| S14 | «تأكيد التغيير» | the before ⇒ after line | «أكّد» |
| S15 | «إلغاء اعتماد {name} كمدرّب» | list: «يُلغى الاعتماد مدرّبًا وخبيرًا» · «تُسحب صلاحية تقديم العروض» · «يُفرَّغ الملف العام من الدليل» · «الحساب نفسه لا يُحذف». Then input «اكتب البريد للتأكيد: {email}» (ltr; must match, case-insensitive), checkbox «إخفاء الحساب كتجريبي أيضًا» (checked), input «السبب (اختياري، يُحفظ في السجل)». ⛔ No env-var or key names (the old text listed `expert_offers`, `FOUNDER_EMAIL`). | «ألغِ الاعتماد» (red) |
| S16 | «الرد على {name}» | the message quoted (topic + body); textarea «نص الرد» (required); «يُحفظ ردك هنا وتُعلَّم الرسالة «تم الرد»، ثم يُفتح بريدك والنص جاهز للإرسال.» | «احفظ وافتح البريد» |
| S17 | «حذف رسالة» | «ستُحذف رسالة {name} نهائيًا.» (from a ticket or from the «رُدّ عليها» list) | «احذف» (red) |
| S18 | «تصفية الحسابات» | §6.2, side sheet; no write | «اعرض النتائج» · «امسح التصفية» |

**Honesty note for S16:** `POST /api/messages/<id>/reply` records the reply and sets `replied`; it **does not send email** (`app.py` 11036: «Email delivery is a stub»). That is why the button opens the founder's mail program with the text prefilled: `mailto:{email}?subject=ردًّا على رسالتك — البروفيسور&body={text}` (encoded). The old label «ردّ — ويُعلَّم «تم الرد»» implied sending.

### 8.1 Settings sheet S8 (groups) — referenced from §5
Side sheet. The three groups are **collapsed**, and only one is open at a time (opening one closes the other). Each collapsed group shows its current state in one line, from the loaded values only:
- «باب المؤسسين: مفتوح» / «… مغلق» / «… غير متاح بعد»;
- «حصة العضو: {ar(quota)} · الموافقة من الجيل {ar(gen)}», each value «غير متاح بعد» when null;
- «{ar(set)} من ٦ فيديوهات مضبوطة» (count of non-empty urls), or «غير متاح بعد», or «للإدارة فقط» when `forbidden`.

1. **«باب المؤسسين»**
   - Status chip: «مفتوح» / «مغلق» / «غير متاح بعد».
   - Text: «ما دام الباب مفتوحًا، يحصل كل من يكمل رحلة الدعوة على صفة «مؤسس» دائمة. يمكنك إغلاقه وفتحه في أي وقت.»
   - Button: «أغلق الباب» or «افتح الباب» ⇒ S14 ⇒ A23. Disabled while unknown.
2. **«الدعوة»**
   - Fields:
     - «فيديو الترحيب» (url, ltr, placeholder «الصق رابط الفيديو»; hint «أول ما يراه صاحب الدعوة»);
     - «فيديو المنصة» (hint «يظهر بعد اختيار الصفة»);
     - «عدد الدعوات لكل عضو» (number ≥0);
     - «الموافقة مطلوبة من الجيل» (number ≥1; hint «دعوات هذا الجيل وما بعده تنتظر موافقتك قبل أن يعمل رابطها»).
   - A null value ⇒ the field is empty, with the hint «القيمة الحالية غير متاحة بعد». The old screen displayed invented defaults 5 and 2. **Only fields the founder changed are sent.**
   - Button: «احفظ إعدادات الدعوة» ⇒ A24.
3. **«فيديو لكل صفة»**
   - Six url fields: «مدرّب», «محامٍ», «مستشار», «باحث», «خريج», «أكثر من صفة».
   - Hint: «يظهر الفيديو بدل النص المكتوب لكل صفة.»
   - `forbidden` ⇒ «للإدارة فقط». `missing` or error ⇒ «غير متاح بعد».
   - Button: «احفظ الفيديوهات» ⇒ A25 (changed keys only; an emptied field sends `""`, which restores the written text).

### 8.2 Invite detail sheet S12 — referenced from §5
- Loading «…جارٍ جلب التفاصيل»; 404 «التفاصيل غير متاحة بعد من المنصة»; error «تعذّر جلب التفاصيل» + «أعد المحاولة».
- When `stage==='pending'`, no call: «لا تفاصيل بعد — لم يُفتح الرابط».
- **Rows:** «البريد», «الهاتف», «الداعي», «الصفات», «التخصص», «سنوات الخبرة», «الجيل», «طبيعة العمل» (`focus`). A missing value hides the row.
- **«الخط الزمني»:** each timeline key ⇒ label with `fmtWhen`:
  - `created` «إنشاء الدعوة»
  - `opened` «فتح الرابط»
  - `email_bound` «كتابة البريد»
  - `pain_seen` «مشاهدة التعريف»
  - `exercised` «تجربة المثال»
  - `declared` «الموافقة على الشروط»
  - `registered` «الانضمام»
- **«المثال»:** shown when `demo` is present or there are no legacy exercises.
  - «السؤال».
  - Up to 12 bubbles, 160 chars each, labelled «المساعد» / «صاحب الدعوة»; a fallback answer gets «(إجابة جاهزة)».
  - Then:
    - «الإجابة المعتمدة»
    - «الحكم»: `correct` «صحيحة», `partly` «ناقصة», `wrong` «خاطئة»
    - «التصحيح»
    - «الاقتراح»
  - Request mode: «طلب توثيق من خبير» + «ملاحظة للخبير».
  - Empty: «لم يبدأ المثال بعد».
- **«التجربة»** (legacy exercises): role label + question, assistant answer, verdict, notes, proposal.
- **Bottom rows:**
  - «فيديو الدعوة»: «فيديو المنصة» / «فيديو الداعي» / hidden;
  - «الموافقة على الشروط»: «في {date} — نسخة الشروط {v}»;
  - «صفة المؤسس»: «نعم» / «لا».
- **Actions:** per §5.2, plus «اسحب الدعوة» (live and not registered or rejected) and «أعِد إصدارها» (reissuable: expired, revoked, or rejected, and not registered).

---

## 9) Brain lines: facts only

The brain line is the one sentence next to the brain avatar. It is always computed from fields that exist. A missing source removes that part of the sentence, or the line becomes «غير متاح بعد». Nothing is invented, and there is no AI text.

| ID | Where | Text pattern (exact) | Factual basis |
|---|---|---|---|
| B1 | «الطلبات» header | «ينتظر قرارك {ar(total)}: {parts}. أقدمها منذ {ago}.» Parts, only those >0: «{n} زائر/زائران/زوّار ينتظرون الفتح», «{n} من قائمة الانتظار», «{n} دعوة/دعوتان/دعوات تنتظر موافقتك», «{n} طلب/طلبا/طلبات تقديم خدمة», «{n} خبير مؤسس/خبيران مؤسسان/خبراء مؤسسون» (via `U()`). Zero everywhere with all sources ready: «لا أحد ينتظر قرارك الآن.» | item counts per column; oldest `ts`/`at` |
| B1-f | «الطلبات» header, failed | appended: «تعذّر جلب: {labels} — العدد ناقص.» (includes the half that failed in a `mixed` column 1) | `INBOX_FAILED`, loader states |
| B1-g | «الطلبات» header, second line (only when B2b k>0 or B2c m>0, and invites ready) | a link to `#s/people/pipeline`: «{k} دعوات واقفة و{m} تنتهي مهلتها قريبًا — انظر «الدعوات»». With one part zero, that part is dropped («{k} دعوات واقفة — انظر «الدعوات»»). Counts via `U()` | the same numbers as B2b and B2c (`v2p.pipeline(...).stalled`, `.expiring`) |
| B2a | «الدعوات» | «أُرسلت {sent}، فُتح منها {opened} وانضمّ {joined}.» | rows |
| B2b | «الدعوات» | «{k} دعوات فُتحت ولم تكتمل وقد مرّ على إرسالها أكثر من ٣ أيام — ذكّر أصحابها عبر واتساب.» (only k>0; same 3-day rule as the platform's own reminder job, `invites.py` 1747) | `stage∈journey` and `now-at > 72h` |
| B2c | «الدعوات» | «{m} دعوات تنتهي مهلتها خلال يومين.» (only m>0) | `expiresAt - now ≤ 48h`, not terminal |
| B3 | «المستخدمون» | «الحسابات {total} · انضمّ هذا الأسبوع {signups_7d} · اليوم {signups_today} · مدرّبون معتمدون {trainers_approved} · باقات مدفوعة {paid_plan}» (each missing value ⇒ «غير متاح بعد» in its slot) | `metrics.customers` |
| B4 | «الرسائل» | «تنتظر الرد {n}: {site} من الموقع · {chat} من المحادثة · {follow} طلبات تواصل. أقدمها منذ {ago}.» All zero and ready: «لا رسائل تنتظر الرد.» | column counts |
| T-* | tickets | §4.3 / §5.2 / §7.2 | row fields |

The suggestion is always the ticket's primary button: the natural next step, the same one «ابدأ القرارات» shows. There is no quality judgement on a person.

---

## 10) Loading, empty, failed, partial

Common rules (same as D2/D3):
- **Loading:** skeleton columns (paper blocks), with «…جارٍ الجلب» in each column header. Counts show «…».
- **Two-source column** («الطلبات» col 1) with one half failed: state `mixed`, pill «{n}+؟», and the in-column retry line (§4.2). Never a full count that hides the failure, and never «—» that hides the tickets that did arrive.
- **Failed source:** the column count pill shows «—».
  - The column body: «تعذّر جلب {plain label} — لا تعتبر العمود فارغًا.» + «أعد المحاولة» (reloads that key).
  - The page strip: «تعذّر جلب: {labels} — القائمة ناقصة وليس معناه أنه لا شيء ينتظرك».
- **Missing bridge** (`missing:true`): «هذه البيانات غير متاحة بعد من المنصة». No path, no domain.
- **Partial** (`count > rows`, or `INBOX_TRUNCATED` matches): «معروض {x} من {y} — القائمة ناقصة».
- **Empty column** (source ready, zero items): «لا شيء هنا الآن».
- **Whole tab empty** (all sources ready, zero items): a big empty card with the photo `v2/img/people.jpg` (radius 18, 160 px tall, object-fit cover) and the text:
  - «الطلبات»: «لا أحد ينتظر قرارك الآن»
  - «الدعوات»: «لم تُرسل أي دعوة بعد» + «+ دعوة جديدة»
  - «الرسائل»: «لا رسائل تنتظر الرد»
  - «المستخدمون»: «لا حسابات بعد»
- A number that is not known is **never** shown as 0. «٠» appears only when the source answered with zero.

Plain failure labels:

| Source | Label |
|---|---|
| `'زوّار ينتظرون الفتح'` | «الزوّار» |
| `'طلبات تقديم الخدمة'` | «طلبات تقديم الخدمة» |
| `'ليدات خبير مؤسس'` | «الخبراء المؤسسون» |
| waitlist | «قائمة الانتظار» |
| invites | «الدعوات» |
| users | «الحسابات» |
| metrics | «أرقام المنصة» |
| messages | «رسائل الموقع» |
| chat | «رسائل المحادثة» |
| leads | «طلبات التواصل» |

---

## 11) Copy rules and glossary

- **Plain standard Arabic.** Gender-neutral: nouns rather than he/she verbs («صاحب الطلب», «صاحب الدعوة», «الداعي»). Arabic digits through `ar()`. Emails, phones, and links are ltr.
- **Forbidden in visible text:** «يقوّم»; any colloquial form; any English word or code (`pending`, `IP`, `https`, route paths, `expert_offers`); a headline that starts with AI/الذكاء.
- **Stage nouns** (`v2p.stageLabel`):
  - `pending` «لم تُفتح بعد»
  - `opened` «فتح الرابط»
  - `roles_chosen` «اختيار الصفة»
  - `pain_seen` «مشاهدة التعريف»
  - `exercised` «تجربة مثال»
  - `declared` «الموافقة على الشروط»
  - `registered` «الانضمام»
  - `expired` «انتهت مهلتها»
  - `revoked` «سُحبت»
  - `awaiting_approval` «تنتظر موافقتك»
  - `rejected` «رُفضت»

  The loader's `STAGE_AR` («لسه ما فتحش», «سجّل ✓») is **not** used.
- **Old ⇒ new wording:**
  - «اتبعتت» ⇒ «أُرسلت»
  - «مستنّي» ⇒ «ينتظر»
  - «لسه ما طلبش» ⇒ «لم يطلب الفتح بعد»
  - «ليه عايز ينضم» ⇒ «سبب الانضمام»
  - «جاي من فين» ⇒ (dropped)
  - «داخل من» ⇒ «بلد التسجيل»
  - «⚠️ مشبوه» ⇒ «يحتاج مراجعة»
  - «أدمن» ⇒ «إدارة»
  - «موظف» ⇒ «فريق العمل»
  - «تاجات» ⇒ «وسوم»
  - «وسم تجريبي (إخفاء)» ⇒ «أخفِ الحساب من الواجهات العامة (تجريبي)»
  - «فيديوهات الألم» ⇒ «فيديو لكل صفة»
  - «هو» (chat bubble) ⇒ «صاحب الدعوة»
  - «بروف» ⇒ «المساعد»
- **WhatsApp texts** (`v2p.waText`):
  - invite: «أهلًا {name}،\nهذه دعوتك إلى منصة البروفيسور، وهي باسمك وحدك:\n{link}»
  - reminder: «أهلًا {name}،\nدعوتك إلى منصة البروفيسور ما زالت بانتظارك، ويمكنك إكمالها من الرابط نفسه:\n{link}»
  - Without a name: «أهلًا،».
  - URL (`v2p.waUrl(phone, text)`): when the phone has at least 8 digits after keeping digits only (a leading `+` dropped), `https://wa.me/<digits>?text=` + `encodeURIComponent(text)`, which opens that chat directly, the same as the founding ticket. Otherwise `https://wa.me/?text=` + `encodeURIComponent(text)`, and the founder picks the chat. The phone comes from the invite row (`phone` when the bridge sends it), the S7/S6 field just typed, or `inviteDetail.user.phone`.
- **Escaping:** every server or user string goes through `esc()`. `href` only for `https?:` (via `safeUrl`), `mailto:` (encoded), `tel:`/`wa.me` (digits and `+` only).

---

## 12) What stays as «كل السجلات»: nothing

Every old people screen is fully covered:
- **`viewUsers`:**
  - its KPIs become B3;
  - its role and tag filters become chips and «التصنيف»;
  - its editor becomes S13 (role, plan + link to prices, tags, test flag, trainer removal, delete with the check).
  - The fake add and edit are dropped (§6.7).
- **`viewInvites`:**
  - its policy banner is dropped; the explanation lives in the S8 texts;
  - its KPIs become the pipeline cards and B1;
  - founding door, invite settings, and pain videos become S8;
  - the approval queue becomes «الطلبات» col 2;
  - the invite list becomes the pipeline: copy, WhatsApp, revoke, reissue, detail drawer (S12), and the «حسب الداعي» toggle (now the inviter filter);
  - pending visitors become col 1 plus §4.4;
  - the waiting list becomes col 1b;
  - the refresh buttons become «حدّث» on «الطلبات» and «الرسائل» (the pipeline redraws by itself).
- **The inbox `t:messages` filter and the old `viewMessages`** become «الرسائل» (site new and replied, chat messages, and follow-up requests, which the old filter missed).
- **The founding leads panel** in `viewTeam` (files › الخبراء) becomes «الطلبات» col 4, with every status step.
- **Training interests («مهتمو التدريب»).** `DASHBOARD-MAP` §٤ lists them under «الناس», but their only screen is the «مين طلب التدريب» panel inside the old `viewMarket` (`index.html` ≈6257, loader `trainingInterests`, read only, alert 64). The market spec already rebuilds that panel as the block «من طلب التدريب» in السوق › «ماذا يطلب الناس» (`SPEC-market.md` §7.5, same loader). **Decision, fixed before the build:** they live there, owned by the market agent, next to the course demand they explain. People does not draw them, so they are neither dropped nor drawn twice. The home brain counter `training_interests_24h` (`SPEC-home.md`) already points at them.

So no tab hosts an old screen. The old functions stay in `index.html`, untouched, for flag-off and for the employee role.

---

## 13) Server routes: none new

Every read and write above is an existing dashboard route (`backend/app.py`): 1710, 1775, 1809, 1823, 1850, 1869, 1915, 1925, 2873/2887 (via inbox), 3879, 3886, 4742/4755, 4783–4925, 4956, 4969, 5025, 5033, 5052–5143, 1691 (`/api/platform-metrics`), 2392 (`/api/packages`), 11011–11039.

So there is no new `backend/v2_people_routes.py` and no `app.py` line. A test pins that `app.py` has no route containing `v2/people`.

---

## 14) Pure helpers: `V2L.v2p` (end of `v2-logic.js`)

```js
// ===== v2s:people =====
(function (root) {
  var L = root.V2L; if (!L) return;   // يعيد استعمال L.util (ar, U, agoText, dateText) و L.NA و L.v2Card
  …
  L.v2p = { requests, pipeline, users, messages, stageLabel, waText, waUrl, adminGuard, planLabel, inviterKey, SEG };
})(typeof window !== 'undefined' ? window : globalThis);
// ===== /v2s:people =====
```

The functions take plain data and return view models. No DOM, no `EP`, no clock (`now` is passed in).

- **`requests(inp, now)`**
  - `inp = { inbox: rows|null, inboxState, failed: [], trunc: [], invites: EP.data.invites|null, invitesState, waitlist|null, waitlistState, pending|null, pendingState, settings|null, userEmails: Set|null }` (`userEmails` = emails in `EP.data.users.raw`, for the founding title link rule).
  - Returns:
    - `{ cols: { visitors, approval, join, founding } }`, each `{ state: 'ready'|'loading'|'failed'|'missing'|'mixed', count: n|null, countText, partial: bool, items: [Ticket], retry: [{ key, label }], label, short }`. For `mixed`, `count` is the ready half and `countText` is «{ar(n)}+؟»;
    - `later: { state, rows: [...], shown, total }` (§4.4);
    - `head: { text, failedLabels: [], invitesLine: {text, href}|null }` (`invitesLine` = B1-g).
  - `Ticket = { id, kind, tag, age, title, link: email|null, sub, brain, warn, reason, primary: {label, act}, secondary: [{label, act}], ref }`, where `act ∈ {decide:'approve'|'reject'|'request_info', approve_invite, reject_invite, wl_invite, open_sheet, wa:url, resolve}`. `link` follows the §4.3 title link rule (null ⇒ plain text).
  - Inbox kinds copy `L.v2Card(row, {now})` **verbatim** for tag, title, sub, brain, reason, warn, and primary label; only `secondary` and the extra lines are ours.
- **`inviterKey(row)`** ⇒ `'u:<invitedByUserId>'` | `'founder'` | `'none'` (rule in §5.4).
- **`pipeline(invData, invState, now, inviter)`**
  - Returns `{ state, cards: { sent, opened, joined, awaiting } (each n|null), pct: { opened, joined } (string|null), steps: [{ key, label, n|null }] (roles_chosen, exercised, declared; the line under «فُتحت»), cols: { waiting, journey, joined, stopped } (each `{ items, total, shown }`; `joined.items` = last 7 days only), inviters: [{ key, label, n }], stalled: n|null, expiring: n|null, brain: [lines], partial: { shown, total }|null }`.
- **`users(raw, opts)`**
  - `opts = { metrics|null, metricsState, pending|null, packages|null, q, chip, filter: { role|null, seg|null }, sort, limit, now, searchExtra: [], searching: bool, searchFailed: bool }`.
  - Returns `{ state, rows: [{ id, email, name, initial, chips: [{ key, label }] (max 4 + more), planText, joinedText, lastText, active, isTest, segment, tags, role, trainer }], chips: [{ key, label, n|null }] (the five visible), filterOptions: { roles: [{ key, label, n|null }], segs: [{ key, label, n }] }, activeFilters: [{ key, label }], searchLine: string|null, empty: { text, hint }|null, shown, total|null, truncated, more, head }`.
- **`adminGuard(user, metrics, raw, truncated)`** ⇒ `{ locked: bool, note: string }`.
- **`messages(site, siteState, chat, chatState, follow, followState, now)`**
  - Returns `{ cols: { site, chat, follow }, replied: [...], head }`.
  - Field fallbacks as in §3.
- **`stageLabel(stage)`**, **`waText('invite'|'remind', name, link)`**, **`waUrl(phone, text)`** (§11), **`planLabel(planId, packages)`**.

---

## 15) Tests: `backend/tests/test_v2s_people.py`

Use the node harness from `test_v2_d2.py` (`v2_node`, `_node`) and, for pytest, the Flask client with `V2Platform` fixtures. Zero real network: any host other than `https://platform.test` fails the test.

1. **Map and routing (node):**
   - `SECTIONS.people` tabs equal the §1 table exactly;
   - `routeFor('#invites')` gives people/invites;
   - `#users` gives people/users;
   - `#messages` gives people/messages with `st.activeFilter==='t:messages'`;
   - `sectionFor('inbox',{activeFilter:'t:messages'})` gives people/messages;
   - `sectionFor('v2p_invites')` gives people/pipeline;
   - `#s/people/pipeline` round-trips;
   - `ALIASES` is unchanged.
2. **`requests()`:**
   - Each kind lands in its column: pending_user and waitlist in visitors, `awaiting_approval` in approval, join in join, founding in founding.
   - A not-requested visitor is never a ticket; it goes to `later`.
   - A flagged visitor's primary is the open sheet, with the warning «يحتاج مراجعة: …».
   - Join with `licenceMissing` gets «افتح وراجع».
   - The founding primary label follows `nextStatus`.
   - A failed inbox source ⇒ that column's `state:'failed'` and `count:null` (never 0), and the head carries the label.
   - **Mixed column 1:** inbox ready with 3 visitors + waitlist failed ⇒ `state:'mixed'`, `count:3`, `countText:'٣+؟'`, `retry` holds «قائمة الانتظار», head failed labels include it; and the reverse (waitlist ready, inbox visitors failed); and waitlist `missing` ⇒ `mixed` with the «غير متاحة بعد» line.
   - Truncated ⇒ `partial`.
   - The ticket text for inbox kinds equals `v2Card` field by field (tag, title, sub, brain, reason, warn, primary label) for `pending_user` (flagged and not), `join` (with and without `licenceMissing`), and `founding`.
   - No ticket text, from any kind, contains «مشبوه».
   - Title link rule: waitlist ⇒ `link:null`; `pending_user` ⇒ email; founding with an email absent from `userEmails` ⇒ null, present ⇒ email.
   - B1-g: invites with 2 stalled (>72 h in journey) and 1 expiring (≤48 h) ⇒ `head.invitesLine.href==='#s/people/pipeline'` and the text names both; none ⇒ null; invites failed ⇒ null.
3. **`pipeline()`:**
   - Column placement for every stage;
   - `sent` excludes awaiting and rejected;
   - percentages;
   - `steps` from `counts`, and `counts` null gives `n:null`;
   - `missing` and error give null cards;
   - `count > rows` gives `partial`;
   - the B2b stalled count uses exactly 72 h;
   - B2c is 48 h;
   - the inviter filter changes the columns but not the cards;
   - `inviterKey`: `invitedByUserId:'u7'` ⇒ `u:u7`; empty id + `generation:0` ⇒ `founder`; empty id + `generation:null` ⇒ `founder`; empty id + `generation:2` ⇒ `none`, listed as «بلا داعٍ محدد (١)»;
   - `joined`: a row registered 8 days ago is counted in `cards.joined` and `cols.joined.total` but not in `cols.joined.items`; one registered 2 days ago is in `items`.
4. **`users()`:**
   - Chip counts come from metrics when present.
   - Without metrics and not truncated, counts come from rows. Truncated gives `n:null`.
   - Exactly five visible chips, in the §6.2 order; the other four role filters are in `filterOptions.roles`.
   - The visitor chip comes from the email cross-reference.
   - Search covers name, email, and phone.
   - Segment and tag filters work, and each active one appears in `activeFilters`.
   - Sort by last login works.
   - Search states: `searching:true` ⇒ `searchLine` «…نبحث في كل الحسابات»; no match and not searching ⇒ `empty.text` «لا حساب يطابق «…»» with the hint; `searchFailed` ⇒ the failure line.
   - Rows carry at most 4 chips plus a «+n» chip.
   - An empty `last_login_at` gives «غير متاح» (never «لم يدخل»).
   - `adminGuard`: last admin locked; unknown count locked with the note; two admins unlocked.
5. **`messages()`:** platform field names (`from_name`, `from_email`, `subject`, `contact_phone`, `full_name`, `want`, `experience`) and the inbox-era fallbacks; a failed source gives null; ordering oldest first; the >24 h flag.
6. **Copy (static over `v2s/people.js` + the `v2s:people` block):**
   - No «يقوّم».
   - None of the colloquial list (اتبعت, مستني, لسه, عايز, ليه, مش, دلوقتي, اتنسخ, هيتعمل, بتاع).
   - No Latin letters inside Arabic string literals, except the allowed `mailto:`, `tel:`, `https://wa.me/` builders and CSS/JS identifiers.
   - The stage labels equal §11.
   - The WhatsApp texts are exact.
   - `waUrl('+20 100 123 4567', t)` ⇒ `https://wa.me/201001234567?text=…`; `waUrl('12', t)` and `waUrl('', t)` ⇒ `https://wa.me/?text=…`.
   - The S1 reject label is the §4.5 text, and the string «ولا يراه صاحبه» does not appear.
   - `v2-logic.js` contains no visible string «مشبوه» (after the §17 item 6 edit).
7. **Actions (static):**
   - Each path template in §8 appears in `dashboard-api.js`.
   - `people.js` contains no `window.prompt`, `confirm(`, or `alert(`.
   - There is no `/api/platform-users` POST.
   - Every write in `people.js` goes through `PX.call`, `EP.decideInboxItem`, or `EP.resolveInboxItem`.
8. **Flask (pytest, fake platform):** for each write the sheet triggers (A2–A5, A10–A18, A19–A25), the dashboard route proxies to the expected platform path and method, with the body unchanged.
   - Purge refuses when `purge-check` says no.
   - Reply records `replied` and makes no outbound email call (assert no `requests` call).
9. **Wiring (static):**
   - The `index.html` sections block exists and holds exactly our two lines.
   - The registry hook line is present once, right after the D3 line.
   - `owns()` is false when the shell is off.
   - With the flag off, `viewUsers`/`viewInvites`/`viewMessages` are byte-identical to the base commit (hash the function bodies).
   - `app.py` has no `v2/people` route.
   - `v2-d2.js` `drawPerson` output contains `data-v2p-manage` when `V2SECT.people` is present, and is unchanged when it is absent.
   - The users list markup in `people.js` has no `data-v2p-manage`/«إدارة» button: S13 opens only from the person page.
10. **Shared test updates** (§17): `test_v2_d1b.py` (people row, the 35 ⇒ 36 count, `PSEUDO_MODS += {'v2p_invites'}`), `test_xss_hardening.py` (allow `v2s/[a-z_]+\.js`), `test_v2_d1.py` (add one assertion: the flagged `pending_user` card's `warn` starts with «يحتاج مراجعة: »; the existing checks at 737–743, 915, 1052 stay as they are and must still pass). Run the whole old suite file by file in the sandbox. The three port tests run outside it, by the main session.

---

## 16) Shots: `backend/tests/uiharness/v2_shots_people.py`

- **Imports:** helpers from `v2_shots.py`. Set `sys.argv[1]` to our out dir before the import, because `v2_shots` reads `OUT` at import time. Do not edit `v2_shots.py`.
- **Fixtures:** subclass `v2_fixtures.V2Platform` in the new script, adding:
  - waiting list (3 rows);
  - pending users (2 requested, one with `flag_labels`; 2 not requested; 1 rejected);
  - invites covering every stage, 2 `awaiting_approval`, 1 rejected with `approval_note`, plus `count > rows` for the partial shot;
  - invite detail (demo + timeline);
  - settings (founding open, invites with null quota, videos);
  - `/api/bridge/messages` (2 rows, platform field names);
  - `/api/bridge/leads` (2 rows, platform field names);
  - metrics `customers`;
  - packages.
  - Site messages are seeded as `Message` rows in the harness SQLite (2 new, 1 older than 24 h, 2 replied).
- **Output:** `docs/v2/final/shots-people/` at desktop 1440×900 (`d`), tablet 820×1180 (`t`), and mobile 390×844 (`m`).

| # | Shot |
|---|---|
| p01 | «الطلبات», all 4 columns filled, with the B1-g line to «الدعوات» (d, t); m: one shot per column (p01a–d), short labels in the D2 strip |
| p02 | flagged visitor ⇒ S1 open |
| p03 | S4 reject invite (with note) |
| p04 | S5 join reject, empty reason ⇒ inline error |
| p05 | founding ticket with WhatsApp + «أنشئ دعوة بهذه البيانات» |
| p06 | «سجّلوا ولم يطلبوا الفتح بعد» expanded |
| p07 | «الدعوات»: brain + one main button + 4 cards (middle-step line under «فُتحت») + 4 columns, «انضمّ» limited to 7 days (d, t, m) |
| p08 | inviter filter applied |
| p09 | S7 new invite ⇒ S7b link sheet |
| p10 | S12 invite detail (example + timeline) |
| p11 | S8 settings as a side sheet (d) and full screen (m): all groups collapsed with their state lines, then «الدعوة» open with a null quota showing «القيمة الحالية غير متاحة بعد» |
| p12 | partial invites strip «معروض … من …» |
| p13 | «المستخدمون» list (d, t, m): five chips + «تصفية», rows with «افتح صفحة الشخص»; chip «مدرّبون»; S18 open (d, m) |
| p14 | users search: «…نبحث في كل الحسابات», server results merged, and the «لا حساب يطابق» card |
| p15 | person page with «إدارة الحساب» ⇒ S13 (d side sheet, m full screen), three parts, «المزيد» open; last-admin lock visible |
| p16 | S9 purge blocked vs allowed |
| p17 | S15 trainer removal |
| p18 | «الرسائل» board (d, t, m); one chat ticket in the «هل أرسلت الرد؟» state |
| p19 | S16 reply sheet; S17 opened from the «رُدّ عليها» list |
| p20 | failed sources: «الطلبات» with inbox failed, and «الطلبات» col 1 `mixed` (pill «…+؟», in-column retry line); «الدعوات» with the bridge missing; «المستخدمون» with metrics failed; «الرسائل» with chat failed |
| p21 | empty tabs with the people photo |
| p22 | flag off: old `#invites` and `#users` unchanged, and no `.v2p` in the DOM |

The script **fails** on any of these:
- horizontal scroll at 390;
- a label inside a `.v2d-segb` that wraps to more than 2 lines (span height > 2 × line height) at 390;
- a target under 44 px (buttons under 52 px on mobile);
- a long sheet (S8, S12, S13, S18) narrower than 100% of the viewport at 390, or not 480 px at 1440;
- the word «مشبوه» anywhere inside `.v2p` or `.v2pm`;
- visible `0`/`null`/`NaN`/`undefined` where «غير متاح بعد» is expected;
- Latin digits in Arabic text;
- old classes inside `.v2p` (`.kpi`, `.panel`, `.policy`, `.inboxwrap`, `.trow`, `.filterbar`);
- a visible `#v2sbar` on the users tab;
- any request other than Google Fonts;
- a write without its confirm step (except the one-click approves listed in §8, and «نعم، علّمها منتهية» / «نعم، تمت المتابعة», which are themselves the confirmation step); the «احذف» in the «رُدّ عليها» list is checked to open S17;
- `window.prompt`/`confirm` being called.

---

## 17) Shared edits, cross-section notes, out of scope

**Shared edits** (report under `shared_edits`):
1. `dashboard-cloud/index.html`: the sections block (2 lines, ours) plus the single generic `V2SECT` hook line in `renderView` (§2). It must be identical in every section's branch.
2. `dashboard-cloud/v2-logic.js`: our `SECTIONS` entry plus the `v2s:people` block (allowed), plus item 6.
3. `backend/tests/test_v2_d1b.py`:
   - the people row in `test_the_tabs_match_the_approved_table`: `[['invites','الطلبات','invites'],['pipeline','الدعوات','v2p_invites'],['users','المستخدمون','users'],['messages','الرسائل','inbox'],['person','صفحة الشخص','v2person']]`;
   - the count in `test_section_addresses_round_trip` (+1);
   - `PSEUDO_MODS` (+`'v2p_invites'`).

   The merge owner reconciles the counts across sections.
4. `backend/tests/test_xss_hardening.py` line 628: add `v2s/[a-z_]+\.js` to the allowed script list.
5. **Required:** `dashboard-cloud/v2-d2.js` `drawPerson`, one expression inside `.v2d-pact`, after the «مراسلة» link (≈ line 350): `+ (window.V2SECT&&V2SECT.people&&V2SECT.people.manageBtn?V2SECT.people.manageBtn(email):'')`. This is the only door to S13 (§6.5). When `V2SECT.people` is absent, the output is byte-identical to today. The person page is the hidden tab of this same section, so no other section's file is touched.
6. **Required:** `dashboard-cloud/v2-logic.js` `v2Card`, case `pending_user`, one string: `card.warn = 'مشبوه: ' + …` ⇒ `card.warn = 'يحتاج مراجعة: ' + …`. «مشبوه» is a forbidden visible word (§11) and the same card is shown in «ابدأ القرارات» and in «الطلبات». No other `v2Card` text changes: this spec adopts `v2Card`'s current tag, primary label, brain, reason, and sub for `pending_user`, `join`, and `founding`, so the D1 tests at 915 and 1052 keep passing unchanged. This is the one line above the `v2s:people` marker that changes besides the `SECTIONS` entry; the merge owner should expect it.
7. `backend/tests/test_v2_d1.py`: one added assertion for the §17 item 6 wording (§15 item 10).

**Cross-section notes:**
- **Founding leads** are also drawn by the old `viewTeam` panel (files › «الخبراء», `index.html:5457`). The files agent should drop that panel from the new experts screen, because it now lives in people › «الطلبات». The data and endpoint are the same, so a double render would not be wrong, only duplicated.
- **Trainer applications** (inbox `trainer`) stay with courses › «المدرّبون». We only link there.
- **Training interests** live in السوق › «ماذا يطلب الناس» › «من طلب التدريب» (`SPEC-market.md` §7.5), owned by the market agent (§12). If the market build drops that block, the merge owner must flag it: nothing in people draws them.
- The «رسائل» chip inside home › «كل الوارد» still filters the old inbox inside home. That belongs to the home agent.
- `nginx.conf` caches `.js`/`.css` for 7 days. After deploy, add `?v=<short-hash>` to the two tags or accept a short delay (merge owner's call, same as other sections).

**Out of scope:** new platform data (below); sending email from the dashboard (the reply stays recorded plus `mailto:`); any change to the old screens.

---

## Platform needs

None of these block this round. Without them, the screen states its limits («معروض … من …», «غير متاح بعد»).

- **P1 · Invite totals beyond the last 200.**
  - `GET /api/bridge/invites/summary` ⇒
    ```json
    {"total": 0,
     "by_status": {"pending": 0, "opened": 0, "registered": 0, "revoked": 0, "expired": 0, "awaiting_approval": 0, "rejected": 0},
     "reached": {"opened": 0, "roles_chosen": 0, "exercised": 0, "declared": 0, "registered": 0},
     "stalled_3d": 0, "expiring_48h": 0, "generated_at": "ISO"}
    ```
  - Secret-guarded like the other bridges, read only.
  - Dashboard proxy: `GET /api/invites/summary` (admin). The pipeline cards and their middle-step line would read it first and fall back to rows.
- **P2 · Account fields in the users bridge.**
  - `_user_row` in `routes/admin_bridge.py` gains `"access": "member"|"pending"`, `"invited_by": {"name": str, "kind": "founder"|"member"}|null`, `"country": str` (from the signup form, when present).
  - `/api/bridge/users` gains `"total": <count of the same query without limit>`.
  - With these, the visitor chip needs no cross-reference, the list can say «بدعوة من …», and the search can say «معروض x من total» for filtered results.
- **P3 · Reply to a chat message from the dashboard** (optional).
  - `POST /api/bridge/messages/{id}/reply` with body `{"body": str, "by": email, "confirmed": true}` ⇒ notifies the member in-platform (and by email if the platform already does that for other notices), sets `status:"resolved"`, and stores `reply_body`, `replied_at`, `replied_by`.
  - Until then: `mailto:` / WhatsApp, then «علّمها منتهية».
- **P4 · Messages and leads totals.** `/api/bridge/messages` and `/api/bridge/leads` return `count = len(docs)` (capped by `limit`). Add `"total"` (uncapped count for the same filter) so the columns can say when they are partial.
- **P5 · Keep the visitor reject note internal.** `invite_request_of()` (`auth.py` 774) returns the whole `invite_request`, including `note` and `decided_by`, to the visitor in `/api/auth/me` and `GET /api/invite-request`. Strip `note` and `decided_by` from those two user-facing responses (the bridge `_pending_row` keeps them). After that ships, the S1 label may become «سبب الرفض (اختياري، للفريق فقط)».
- **P6 · Dashboard button on alerts 60 and 61.** Add `link_button("افتح الدعوات في الداشبورد", dashboard_inbox_url() + "#s/people/pipeline")` (`ops_links.py`) to the stalled-invites digest (`invites.py` ≈1824) and to the journey-finished alert (`invite_journey.py` 1070). Until then, B1-g covers it.

---

## Decisions (revision 2, after the expert review)

The review had 16 points; the text of the 16th was cut off after its location. All 16 are applied. Where the fix differs from the reviewer's suggestion, the reason is given.

| # | Point | Decision |
|---|---|---|
| 1 | Ticket text vs `v2Card` mismatch | Applied, using a third path rather than (أ) or (ب): the spec now adopts `v2Card`'s current text verbatim for every inbox kind (§4.3) and changes **only** the `warn` word «مشبوه» ⇒ «يحتاج مراجعة» inside `v2Card` (§17 item 6). Reason: path (أ) would rewrite the tag and primary label, breaking the D1 tests at 915 and 1052 and changing «ابدأ القرارات» copy outside our section; (ب) would leave «مشبوه» on the home screen and two wordings for one request. One string fixes the forbidden word in both places, and the «word for word» test stays true. |
| 2 | Mobile strip labels too long | Applied: short labels per column (§4.2, §5.1, §7.2) and D2's `.v2d-seg`/`.v2d-segb` reused as is. Kept D2's 60 px height, since that is the existing pattern. Shot check added for wrapping beyond two lines. |
| 3 | Users screen is an admin table | Applied: rows with one button «افتح صفحة الشخص», five visible chips, everything else behind «تصفية» (S18), S13 in three parts, and the person page as S13's only door (§17 item 5 is now required). `focusUser` now opens the person page. |
| 4 | «الدعوات» top row crowded | Applied: brain + one main button; settings as a header gear; «حدّث» removed; the funnel merged into the cards as one muted line under «فُتحت»; the inviter select moved above the board. |
| 5 | Alerts 60–61 landing on «الطلبات» | Applied: B1-g second line with a link to «الدعوات». Verified that these alerts carry no dashboard link today, so P6 asks for a button, not a link-text change (there is no `invite_journey.json` link to edit). |
| 6 | Two-source column state | Applied: the `mixed` state with «n+؟», an in-column retry line, and strip/B1-f labels (§4.2, §10); test and shot added. |
| 7 | Founder vs member inviter rule | Applied as written, plus «بلا داعٍ محدد» for rows with no inviter id and generation ≥1 (§5.4, `inviterKey`); test added. |
| 8 | Chat reply leaves the ticket unchanged | Applied: the local «هل أرسلت الرد؟» state with «نعم، علّمها منتهية» / «نعم، تمت المتابعة» and «ليس بعد» (§7.2). |
| 9 | Person link for people with no account | Applied: the title link rule (§4.3, §5.2); founding links only when its email has an account. |
| 10 | «انضمّ» column grows forever | Applied: last 7 days, dimmed, «اعرض الكل (N)»; the card still counts everyone. |
| 11 | S8 as a long form in a small modal | Applied: one side-sheet pattern for S8, S12, S13, S18 (§8 Sheets), with S8 groups collapsed and their state lines. |
| 12 | WhatsApp without the number | Applied: `waUrl(phone, text)` opens the chat directly when ≥8 digits are known (§11); test added. Invite rows do not always carry a phone, so the no-number link remains as the fallback. |
| 13 | Training interests missing | Applied: they live in السوق › «ماذا يطلب الناس» (`SPEC-market.md` §7.5 already rebuilds them). Fixed in §12 and §17 so they do not fall between agents. Not added as a fourth messages column, to avoid drawing them twice. |
| 14 | Search with no result or in progress | Applied: «…نبحث في كل الحسابات» and the «لا حساب يطابق» card (§6.4); test and shot added. |
| 15 | Delete in «رُدّ عليها» without confirm | Applied: S17 then A20 (§7.1); shot check added. |
| 16 | S1 reject note (text cut off) | Read as: the label «ولا يراه صاحبه» claims something unverified. Checked in the platform: the note is stored on `invite_request` and returned to the visitor by `/api/auth/me` and `GET /api/invite-request`, though the visitor screen does not display it. The label now says the note is saved and to write only what the visitor may read (§4.5); P5 asks the platform to strip it. |
