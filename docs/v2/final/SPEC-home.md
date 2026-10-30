# SPEC-home — «اللوحة» final round: board polish · «كل الوارد» · the shared drawer · the bell · the login screen

**Authorization:** the founder ordered this round on 2026-10-30: «ابدأ الجولة… الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا». This spec is the plan for the final build. It is not a draft. The build stage builds all of it.
**Section key:** `home` · **Worktree:** `.worktrees/home` · **Branch:** `final-home` (from `7d1aa83`, after D3).
**Reference style:** D1-B shell (`v2-shell.*`), D2 tickets (`v2-d2.*`), D3 money screens (`v2-d3.*`), and the approved boards `POS-Home`, `POS-Phone`, `POS-Focus`, `POS-Tickets` («المعتمد» row).
**Hard limits (repeat for the builder):** zero real network calls, zero paid calls, no push, no deploy. Use `git add` with explicit paths only. Everything sits behind `DASH_V2_ENABLED`. **With the switch off, every screen in this spec, including the login screen, stays exactly as it is today** (see §9 for the single, documented edge case).

---

## 0. What this round delivers (one paragraph)
With the switch on, the founder never sees the old inbox look again:
- **«كل الوارد»** is rebuilt as burgundy/paper tickets with a few clear filter chips, its own search box and a brain line.
- The **side drawer**, used by every section, is restyled in the new look. A switch-only copy layer turns its colloquial text into plain standard Arabic. No decision or money logic changes.
- The **confirmation sheet** (`#epModal`) and the **toasts** get the same look.
- The **two bells** become **one bell**. Today the board has a health bell and the top bar has a notifications bell. The new bell has two parts: «حالة المنصة» and «الإشعارات».
- The **login screen** and the **first-load splash** get the brand look.
- The **board** gets a light polish. It loses its orphan health pill, gets tablet and mobile spacing fixes, and its own focus and grid stay unchanged.
- **Nothing remains as «كل السجلات»** in this section.

---

## 1. Ground truth (read before building — every line checked in this worktree)

| Fact | Where | Consequence for this round |
|---|---|---|
| The home section tabs are `board` («اللوحة والقرارات», mod `home`) and `inbox` («كل الوارد», mod `inbox`, `activeFilter:'all'`). | `v2-logic.js:1220-1223` | **No change to the `SECTIONS` entry.** Tab keys and labels stay, so `test_v2_d1b.py:82` keeps passing. |
| Mod `inbox` is also the module for **«كل الملفات»** (files/all), **«كل النزاعات»** (disputes/all) and **«الرسائل»** (people/messages). These differ only by `activeFilter`. | `v2-logic.js:1227,1232,1251` | The new inbox renderer serves **all four tabs**. It must honour the `activeFilter` that the tab set, and it shows only the chips that belong to that tab (§4.3). |
| `viewInbox(v)` is the single entry point. It is called from `renderView`, `refreshInbox`, `efRefreshInbox`, `efReloadKeep`, `v2OpenRowAt`, `V2_HOST.openRow` and the old retry links. `renderInbox()` is called from ~15 places: chip clicks, `efLand`, `efAutoWire`, the drawer close buttons (`ef_close`, `cs_close`…), the `#q` input listener and the FYI toggle. | `index.html:1031,1103,…` | Hook **both** functions at their first line (§9). Do not edit their bodies. |
| The old inbox shows: a failed-source strip, a truncation strip, `ovKpiStrip` (users · net profit · held in escrow), `opsQueuePanel` (23 counters), 4 KPI cards (all · «بانتظار اعتماد بشري» · «عالجها الذكاء آليًّا» · late), up to 16 chips, and 3-column rows. | `index.html:1031-1060,1103-1162` | The map already recorded the founder's complaint: «حارات الوارد الكتير: ١٠+ شريحة فرز + ٢٣ عدّاد = المؤسس بيضيع» (`DASHBOARD-MAP:289`). The new screen keeps **one** chip row (plus a sub-row only in the files context) and moves the 23 counters into a closed «أرقام المنصة» panel. |
| «محجوز في الضمان» in `ovKpiStrip` reads the local SQLite escrow mirror. The platform never calls `/api/escrow/hold`, so the number is almost always a false 0. | `DASHBOARD-MAP:26,105` | **Drop `ovKpiStrip` from the new screen.** Users and profit belong to «التقارير» and «الفلوس». A false 0 breaks the «غير متاح بعد, never 0» rule. |
| Inbox rows carry colloquial text (`out`, `sub`, `triLabel`, `sla`, for example «اتدفع وما وصلش لقايمة التوزيع»). `V2L.v2Card(row,{now})` already rebuilds every row kind in standard Arabic: `tag`, `title`, `sub`, `brain`, `ageText`, `group`, `ts`, `person`. | `v2-logic.js:485-757` | **Tickets are drawn from `v2Card`, never from `row.out/sub/sla`.** |
| **The old bell is always empty.** `GET /api/notifications` returns `{count,total,items}`, but the loader reads `Array.isArray(r) ? r : r.notifications`. `items` is never read, so `EP.data.notifications` is always `[]`. | `app.py:7967` vs `dashboard-api.js:2575` | The new bell reads the reply itself (`EP.api('/notifications')`, field `items`). **`dashboard-api.js` is not edited**, so switch-off behaviour stays the same. Report this bug to the main session for the old screen. |
| There are two bells today. One is the board header's (`v2-home.js` `header()`: health pill + alerts bell). The other is the top bar's `#bellBtn` (notifications). In the shell, `v2-shell.css` hides the board's bell and user, and leaves a lone health pill on its own row above the dark bar (shot `docs/v2/shots-d3/d11-home.jpg`). | `v2-shell.css:… .v2-head`, `v2-home.js:116-128` | One bell (§7). The orphan pill row goes. |
| The notification text from the server includes «{who} أنشأ حسابًا» (gendered) and «… USD» (Latin). | `app.py:7907,7948` | The bell maps titles **by `kind`** and cleans the detail through a pure helper (§7.3). The server is not changed. |
| The login overlay (`#epLogin`, `.ep-login`) is built by `dashboard-api.js:3931 showLogin()` **before** any token exists, so `/api/v2/config` (admin-only) cannot be asked. D1-B already stores the last decisive config answer in `localStorage['ep_v2_shell']` (`'1'` = on; it is removed when the server says off). | `index.html:7748-7753` | The login look follows that stored flag (§8). No new public route. |
| While the first config answer is pending, `.app.v2-pre .main{visibility:hidden}` shows a blank page for up to 3 s. | `v2-shell.css:9-10` | A brand splash (§8.3). This is CSS only. |
| `test_xss_hardening.py:628` rejects any `<script src=` outside an allowlist that does not include `v2s/…`. Both Dockerfiles copy v2 files by explicit name. | — | Shared edits S3 and S4 (§9). These are the same one-liners every section needs. |
| The drawer's colloquial strings are pinned by 40+ old UI tests (`test_expert_files_*`), which run with the switch off. | `backend/tests/test_expert_files_ui*.py` | **Never edit drawer strings in `index.html`.** Copy changes happen only through the switch-on copy layer (§5.3). |

---

## 2. Files (parallel-safety)

| File | New/edit | Content |
|---|---|---|
| `dashboard-cloud/v2s/home.js` | **new** | Everything in the browser for this section: the inbox renderer, the drawer wrapper and copy layer, the bell, the login flag and the board polish hooks. Namespace `window.V2SEC.home` (create `window.V2SEC = window.V2SEC || {}`). ⛔ **Never use the global name `V2S`.** It is already the section-state variable in `index.html:7663`. |
| `dashboard-cloud/v2s/home.css` | **new** | All styles. Every rule is scoped under `.app.v2-shell …`, `body:has(> .app.v2-shell) …` (for `#epModal`, `#toasts`, `#v2HBell`), or `html.v2h-login …`. With the switch off, no selector can match. |
| `dashboard-cloud/v2-logic.js` | edit at the **end only** | Pure helpers inside `// ===== v2s:home =====` … `// ===== /v2s:home =====` (§10). They attach to the existing `V2L` object: `(function(root){var L=root.V2L; if(!L)return; L.v2hChips=…;})(typeof window!=='undefined'?window:globalThis);`. Because `module.exports === V2L` in node, the helpers are exported automatically. **No edit to `SECTIONS`.** |
| `dashboard-cloud/index.html` | 2 hook lines + block | §9 S1/S2. |
| `Dockerfile`, `deploy/Dockerfile.coolify` | 1 line each | §9 S3. |
| `backend/tests/test_xss_hardening.py` | 1 regex | §9 S4. |
| `backend/tests/test_v2s_home.py` | **new** | §12. |
| `backend/tests/uiharness/v2_shots_home.py` | **new** | §13. Imports helpers from `v2_shots.py` and does not edit it. |
| `docs/v2/final/STATUS-home.md`, `docs/v2/final/shots-home/` | **new** | The report and the screenshots. |
| `backend/app.py` | **no edit** | **No new server routes in this section.** Do not add the `# ---- v2 section routes end` marker from this branch, because another section that needs it creates it. |
| `dashboard-cloud/v2-home.js`, `v2-shell.js/.css`, `v2-d2.*`, `v2-d3.*`, `dashboard-api.js` | **no edit** | Board polish is CSS plus additive JS in `v2s/home.js` (§3). Any edit here would collide with other sections at merge. |

**Ownership claim, for the merge and for the other ten sections.** Home owns the **shared chrome** below. Other sections must not restyle it in their own CSS:
- `.drawer` and everything inside `#drawer`;
- `#epModal` (`.scrim` / `.modal`);
- `#toasts` / `.toast`;
- `#bellBtn` and the new `#v2HBell`;
- `#epLogin`;
- the `.app.v2-pre` splash.

If another section needs a variant, it adds a class on its own container. Put this paragraph in the round report under `shared_edits`.

---

## 3. Screen A — «اللوحة والقرارات» (polish only)

The board, the dark bar, «ابدأ القرارات», the focus mode, the payout/receipt sheets and the tiles **stay as built in D1–D3**. That covers their logic, order, counts and copy. The polish is CSS in `v2s/home.css` plus one small DOM hook in `v2s/home.js`.

### 3.1 Changes
1. **Remove the orphan health row.** `.app.v2-shell .v2 .v2-head{display:none}` hides it in board, focus and brain modes. Health now lives in the bell (§7). That one rule replaces the old partial hides, which keep working.
2. **The dark bar gets one fact line about health,** added by `v2s/home.js` after each board render. Use a `MutationObserver` on `#view` that runs only when `host.isHome()` and mode is `board`. Insert `<button class="v2h-healthline" data-a="bell">…</button>` as the **last child of `.v2-nt`**. Text, from `V2L.v2Health(Q, now)`:
   - while `opsQueue` is loading: «حالة المنصة: جارٍ الفحص…»;
   - when it failed: «حالة المنصة: تعذّر الفحص — افتح التنبيهات»;
   - when it is ok: «حالة المنصة: كل شيء يعمل»;
   - otherwise: «حالة المنصة: {U(n,['تنبيه واحد','تنبيهان','تنبيهات','تنبيهًا'])} — افتح التنبيهات».
   
   Clicking it opens the bell panel on its «حالة المنصة» part. Style it as a text button, 44px tall, `#F3CF72` when there are alerts and `#BDB8AD` when all is ok, and underline it on hover.
3. **Grid breakpoints:**
   - desktop ≥1180 stays 4 columns;
   - **tablet 761–1179 gets 3 columns with tiles at `aspect-ratio:4/3`, `min-height:170px`**, because at 820 the 16/9 tiles are too short for two lines of `next`;
   - mobile ≤760 keeps 2 columns at 168px (unchanged).
   
   At tablet width, `.v2-tt small` uses `-webkit-line-clamp:3`.
4. **Dark bar on tablet:** at 761–1179 the start button wraps under the text at full width, with `min-height:56px`. Today it squeezes the text at 820.
5. **Focus mode:** no visual change. Check in the shots that `.v2-acts` at 820 is not fixed to the bottom (it is mobile only) and that every button is ≥44px.
6. **`.v2-pill` («العودة إلى القرارات»)** gets `z-index:75` so it sits above the mobile drawer overlay (§5.2, z 60/65).

### 3.2 Data
Unchanged: `V2.render` / `compute()` in `v2-home.js`. The health line reads `EP.data.opsQueue` (when `EP.state.opsQueue==='ready'`) through `V2L.v2Health`. A failed source shows the failure text, never «كل شيء يعمل».

---

## 4. Screen B — «كل الوارد» (rebuilt)

### 4.1 Layout
The outer element is `<div class="v2h" data-ctx="{ctx}">`. `ctx` is `home | files | disputes | messages`, read from `V2_HOST.state().section` (`people` → `messages`). Add `v2-bare` to `.app` while this screen is shown, so there is no white frame and the paper background shows like D2/D3.

**Desktop ≥1180** (content ≈1100px wide next to the 264px side menu):
```
┌──────────────────────────────────────── list column (minmax(0,1fr)) ─────┬── drawer column (440px, sticky) ──┐
│ [search box ……………………………………]                         [«أرقام المنصة»] │                                   │
│ brain line (avatar + one fact sentence)                                   │   #drawer (old drawers, restyled) │
│ status strips (failed / truncated / service mode / auto-assign / FYI)     │   empty: elephant + hint          │
│ chips row  ·  (sub-row in files context)                                  │                                   │
│ group «متأخر (n)» → tickets (1 column, full width)                        │                                   │
│ group «ينتظر قرارك (n)» → tickets                                        │                                   │
│ group «عولجت تلقائيًا (n)» → tickets                                      │                                   │
│ [اعرض المزيد (n)]                                                         │                                   │
│ <details> «أرقام المنصة كما يرسلها التقرير اليومي» (closed)             │                                   │
└───────────────────────────────────────────────────────────────────────────┴───────────────────────────────────┘
```
The drawer column is `position:sticky; top:16px; max-height:calc(100vh - 32px); overflow:auto`.

**Tablet 761–1179:**
- one column;
- tickets in a **2-column grid**;
- no drawer column;
- selecting a ticket opens the drawer as a **side sheet** from the inline-end side (left in RTL), `width:min(560px,92vw)`, full height, over a scrim `rgba(33,38,46,.45)`.

**Mobile ≤760:**
- one column; tickets in 1 column;
- the chips row scrolls horizontally inside its own box (`overflow-x:auto`, no page scroll);
- the drawer opens as a **full-screen sheet** (`position:fixed; inset:0`) with a sticky top bar holding «رجوع إلى الوارد» (button ≥52px);
- the page scroll is locked with `html.v2-noscroll`, which already exists.

### 4.2 Markup and IDs (keep the old IDs the old code relies on)
```html
<div class="v2h" data-ctx="home">
  <div class="v2h-top">
    <label class="v2h-search"><svg…/><input id="v2hq" type="search" autocomplete="off"
           placeholder="ابحث باسم صاحب الطلب أو بريده أو الخدمة" aria-label="ابحث في الوارد"></label>
    <a class="v2h-qlink" href="#v2hQueue">أرقام المنصة</a>          <!-- jumps to the <details> and opens it -->
  </div>
  <div id="v2hHead"></div>        <!-- brain line + strips: redrawn by list() -->
  <div class="filterbar" id="filters"></div>   <!-- id kept: efFiltersIntoView() scrolls to it -->
  <div class="v2h-wrap">
    <section class="v2h-list" aria-label="بنود الوارد"><div id="rows"></div></section>   <!-- id kept -->
    <div class="v2h-dw" id="v2hDw" aria-hidden="true">
      <div class="v2h-dbar"><button type="button" data-a="dclose">رجوع إلى الوارد</button></div>
      <aside class="drawer" id="drawer"></aside>                                        <!-- id kept: every drawer writes here -->
    </div>
  </div>
  <details class="v2h-q" id="v2hQueue"><summary>…</summary><div class="v2h-qgrid"></div></details>
  <span id="inboxN" hidden></span>   <!-- id kept: old code may write a count here; hidden -->
</div>
```
`#v2hq` keeps its value across list redraws. Only `#v2hHead`, `#filters`, `#rows` and the `<details>` body are rewritten.

### 4.3 Chips (one row; a sub-row only in the files context)
- **Counts:** every number is `INBOX.filter(r => inboxMatches(r, key)).length`. The existing global `inboxMatches` is the **only** matcher. The pure helper never matches rows.
- **Filtering:** the list itself is filtered with `inboxMatches(r, activeFilter)` plus the search (§4.6).
- **Clicking a chip:** set `activeFilter = key; selected = null;` and call `renderInbox()`. This goes through the hook, so `v2Reconcile` moves the header exactly as today. For example, the chip «النزاعات» in the home context lands on disputes/all, which is the current D1-B behaviour (`test_inbox_chips_do_not_move_the_user_out_of_files`).

Visible chips per context. A count of 0 hides the chip, except «الكل» and the active chip.

| ctx | Row 1 (in this order) | Row 2 |
|---|---|---|
| `home` | «الكل (N)» `all` · «متأخر (n)» `late` (red) · «ملفات الخبراء (n)» `t:files` · «النزاعات (n)» `t:disputes` · «استشارات قديمة (n)» `t:legacy` · «إيصالات التحويل (n)» `t:money` · «طلبات تنتظر قرارك (n)» `t:decisions` · «توثيق (n)» `t:verify` · «الرسائل (n)» `t:messages` · «أخرى (n)» `t:other` · «عولجت تلقائيًا (n)» `auto` | none |
| `files` | «كل الملفات (n)» `t:files` · «متأخر (n)» `late` | «يحتاج تدخّلك (n)» `attn` · «ينتظر مراجعتك (n)» `review` · «مستعجل (n)» `urgent` · «لا خبير متاح (n)» `nocand` · «مراجعة عقود (n)» `contract` · «قضايا عليها ملاحظة (n)» `case` |
| `disputes` | «النزاعات (n)» `t:disputes` · «استشارات قديمة (n)» `t:legacy` | none |
| `messages` | none. The tab is the list of `t:messages` and the chips row is hidden. | none |

- Within the `files` context, «متأخر» uses `late`, which `sectionFor` maps to home/inbox. That chip therefore **filters in place without changing tab**: set `activeFilter='late'`, render, and do **not** call `v2Reconcile`. Verify against `sectionFor` that the header stays on files/all. If it moves, drop that chip from the files context (the files board already has a late column).
- Chip markup: `<button type="button" class="v2h-chip{ on}{ tone-late}" data-f="{key}" aria-pressed="{bool}">{label} <b>{n in Arabic digits}</b></button>`. Height 44px (48 on mobile), 999px radius, active = burgundy fill and white text.
- The row with the most chips (home) is ≤11 chips and scrolls inside its box on mobile.

### 4.4 Tickets
One ticket per row, built from `c = V2L.v2Card(row, {now})` plus row booleans. Rows where `v2Card` returns `null` still get a ticket from the generic fallback (`tag:'بند'`, `title: row.who || 'بند ينتظر قرارك'`). No row may be dropped silently.

```html
<article class="v2h-t tone-{tone}{ sel}" data-i="{index in INBOX}" tabindex="0" role="button"
         aria-label="{tag}: {title}" aria-current="{selected? 'true'}">
  <div class="v2h-ttop"><span>{c.tag}</span><span class="v2h-age">{timeText}</span></div>
  <div class="v2h-tbody">
    <b class="v2h-ttl">{c.title}</b>
    <p class="v2h-sub">{c.sub}</p>                                   <!-- if non-empty -->
    <div class="v2h-flags">{flags}</div>                             <!-- if any -->
    <p class="v2h-brain"><img src="v2/img/brain-avatar.jpg" alt=""><span>{c.brain}</span></p>  <!-- if c.brain && c.brain !== c.tag -->
    <span class="v2h-amt">{row.amountLabel}</span>                   <!-- if present; digits already Arabic -->
  </div>
</article>
```
- **Tone** (`v2hTone`):
  - `late` (red `#C8102E` strip) when `inboxIsLate(row)`;
  - otherwise `money` (ink `#21262E`) for kinds `payout|manual_payment|stuck_payment|unactivated|legacy`;
  - otherwise `done` (grey `#8FA89D`) when `row.triage==='auto'`;
  - otherwise `wait` (burgundy `#9E2B4E`).
- **timeText:** `c.ageText` («منذ ٣ ساعات»). If it is empty, use «غير معروف الوقت».
- **flags** (pure helper `v2hFlags(row)`; each flag is a small pill):

| Condition | Pill |
|---|---|
| `row.urgent` | «مستعجل» |
| `row.contract` | «مراجعة عقد» |
| `row.noCandidate` | «لا خبير متاح» |
| `row.needsAttention` | «يحتاج تدخّلك» |
| `row.licenceMissing` | «خدمة مرخّصة بلا رقم قيد» |
| else `row.licensed` | «خدمة مرخّصة» |
| `row.flagLabels?.length` | «حساب عليه علامات» (tooltip = the labels joined with « · ») |
| `row.msgSource==='site'` | «من الموقع» |
| `row.msgSource` (any other value) | «من المنصة» |

- **Person link:** if `c.person && window.V2D2`, the title uses `V2D2.link(c.title, c.person.email)`, the same as the focus card. The click on that link must not open the drawer: stop propagation when `e.target.closest('a')`.
- **Open:** click, Enter or Space on the ticket runs the **exact old sequence**: `selected = i; efDspOpen.id = null; efVoiceDrop(); efCaseUiReset(); renderInbox();`. The hook redraws and calls `drawInbox()`. Then:
  - on narrow screens, open the sheet and move focus to the drawer's first heading/button;
  - on desktop, call `#drawer.scrollTop = 0`.
- **There is no money or decision button on a ticket.** Decisions happen in the drawer, which has its existing buttons and confirmations, or in «ابدأ القرارات». The ticket carries the brain's suggestion as text.
- **Groups** (`v2hGroups`):
  - «متأخر» holds tone `late`;
  - «ينتظر قرارك» holds everything else except `auto`;
  - «عولجت تلقائيًا» holds `triage==='auto'`.
  
  Inside a group, sort by `c.group` (the D1 rank) and then by `c.ts`, oldest first. Unknown `ts` goes last and keeps the original order. The sort is stable.
- **Paging:** show the first 60 tickets across groups in order, then a button «اعرض المزيد ({U(rest)})» that adds 60 more. The page size resets when the filter or search changes.
- **FYI rows** (`row.fyi`) never appear unless `activeFilter==='fyi'`. `inboxMatches` already does this.

### 4.5 The brain line and strips (`#v2hHead`)
Shown in this order. Each line appears only when its condition holds.
1. **Brain line** (`v2hBrainLine(cards, brainLogLen, state)`, facts only):
   - inbox state `error`: no brain line (strip 2 says it);
   - there are late tickets: «{U(nLate,['بند متأخر واحد','بندان متأخران','بنود متأخرة','بندًا متأخرًا'])} — أقدمها «{title}» {ageText}»;
   - otherwise, if a ticket has an `ageText`: «أقدم ما ينتظرك: «{title}» {ageText}»;
   - otherwise, with no tickets and every source ok: «لا شيء ينتظرك في الوارد الآن»;
   - the suffix « · وزّع العقل {U(n,['ملفًا واحدًا','ملفين','ملفات','ملفًا'])} اليوم» is added only when `V2L.v2BrainLog(rows, now).length > 0`;
   - in the `files`, `disputes` and `messages` contexts, the line counts only the rows visible under `activeFilter`.
   
   Markup: `<p class="v2h-bl"><img src="v2/img/brain-avatar.jpg" alt=""><b>العقل:</b> {text}</p>`.
2. **Inbox failed** (`EP.state.inbox==='error'`): «تعذّر جلب الوارد — لا نعرف إن كان شيء ينتظرك» + button «أعد المحاولة» → `EP.reload('inbox', rerender)`.
3. **Partial** (`INBOX_FAILED.length`): «تعذّر جلب: {names joined « · »} — العدد ناقص، وما ظهر ليس كل شيء» + «أعد المحاولة» (`EP.reload('inbox', …)`).
4. **Truncated** (`INBOX_TRUNCATED.length`): «معروض جزء فقط من: {names} — الباقي موجود ولا يظهر هنا».
5. **Service mode.** Shown only in contexts `home`/`files`/`disputes` and only if the inbox has an `expert_file` row, or a `dispute` row with `dsrc==='file'`. The data is the existing globals `efServiceMode()` / `EP.data.efAllowlistSize`:
   - `closed`: «خدمة «ملف للخبير» متوقفة للناس الآن، والأموال لا تتحرك تلقائيًا. الملفات المفتوحة ما زالت هنا: يمكنك إعادة أموالها أو حسم نزاعها، ولا يمكن إرسالها إلى خبير.»;
   - `allowlist`: «الخدمة مفتوحة للتجربة فقط ({U(n,['حساب واحد','حسابان','حسابات','حسابًا'])}) — يُرسل الملف فقط إلى خبير من قائمة التجربة، وترفض المنصة غير ذلك.». If `n` is unknown, drop the brackets.
6. **Auto-assign** (contexts `home` with `activeFilter` in `all|t:files|attn|review|urgent|nocand|contract`, and `files`). The data is `efAutoOn()` (global) and the line is hidden when it returns `null`. Local UI state is `{confirm, busy, err}`, held in `V2SEC.home`.
   - **On:** «**التوزيع التلقائي يعمل** — يُرسل كل ملف مدفوع وحده إلى أنسب خبير متاح، ويمكنك تغيير الخبير في أي وقت.» Button «أوقفه». It opens an inline confirm: «إذا أوقفت التوزيع التلقائي، سينتظر كل ملف يُدفع بعد الآن أن توزّعه بنفسك، ولن تُرسل الملفات المنتظرة الآن وحدها. هل توقفه؟» with buttons «نعم، أوقفه» and «رجوع».
   - **Off:** «**التوزيع التلقائي متوقف** — الملفات المدفوعة تنتظر أن توزّعها بنفسك. إذا شغّلته يُرسل كل ملف مدفوع ومنتظر وحده.» Button «شغّله».
   - **Action:** `EP.expertFileAutoAssign(value, rerender)`, the existing function. It already sends `confirmed:true` and reloads the inbox. Read `{ok,error}`. While busy, the label is «جارٍ التنفيذ…» and the button is disabled. On error, show `V2.plainError(res)` under the line. Do not call `efAutoLine()` or `efAutoWire()`, whose copy is colloquial.
7. **FYI.** Contexts `home` (`all`) and `files` (`t:files`), with `n = inboxFyi().length > 0`, and only if the service is not `closed`:
   - when auto-assign is on: «للعلم: {U(n,['ملف واحد أُرسل','ملفان أُرسلا','ملفات أُرسلت','ملفًا أُرسل'])} إلى خبير وما زال ضمن مهلة الاثنتي عشرة ساعة، ولا يحتاج منك شيئًا الآن. إن لم يُستلم يُرسل إلى خبير آخر تلقائيًا.»;
   - otherwise the second sentence becomes «… إن لم يُستلم يعود إلى هنا.»;
   - link button «اعرضها» → `activeFilter='fyi'`;
   - in `fyi` mode: «هذه ملفات أُرسلت إلى خبير وما زالت ضمن مهلته — لا تحتاج منك شيئًا الآن.» + «رجوع إلى الكل» → `activeFilter` back to the context default (`all` or `t:files`).

### 4.6 Search
- Data: `v2hSearchText(row, destLabel)` concatenates the same fields the old search used: `row.out`, `row.from`, `row.who`, `row.serviceLabel`, `row.email`, `row.searchText`, and `MODULES_LOOKUP[row.dest].label` passed in as `destLabel`. It also adds `c.tag` and `c.title`.
- Match: `v2hNorm(query)` is contained in `v2hNorm(text)`. `v2hNorm` lower-cases, strips tashkeel and tatweel, maps `أ إ آ ٱ → ا`, `ة → ه`, `ى → ي`, maps Arabic digits to Latin, and collapses spaces.
- Typing redraws **only** `#v2hHead`, `#filters` and `#rows`, with a 120ms debounce. It does **not** call `drawInbox()`, so a reason being typed in the drawer is never lost.
- No match: «لا بنود تطابق «{q}»» + button «امسح البحث».

### 4.7 Empty, loading and error states for the list
| State | Shown |
|---|---|
| `EP.state.inbox` is `idle`/`loading` and `INBOX` is empty | 3 skeleton tickets + «جارٍ جلب الوارد…» |
| inbox `error` and `INBOX` is empty | strip 2 only, no «لا شيء». The list area reads «لا نعرف الآن ما ينتظرك». |
| ready, every source ok, 0 rows in the context | elephant (`v2/img/brain-avatar.jpg`, 120px) + «لا شيء ينتظرك هنا الآن» |
| ready, some source failed (`INBOX_FAILED`), 0 rows | «لا بنود ظهرت، لكن تعذّر جلب {names} — لا تعتبر القائمة فارغة» |
| ready, filter gives 0 but the context has rows | «لا بنود في هذا الاختيار» + button «اعرض الكل» (sets the context default filter) |

### 4.8 «أرقام المنصة» (closed `<details>` at the bottom)
- Summary: «أرقام المنصة كما يرسلها التقرير اليومي ({U(n,['بند واحد','بندان','بنود','بندًا'])})». If `opsQueue` failed: «أرقام المنصة: تعذّر الجلب» + «أعد المحاولة» (`EP.reload('opsQueue', …)`).
- Body: one button per counter from the existing `opsQueueCounters(Q)`. Each tuple is `[label, n, mod, key, land]`. **The label is not shown.** The visible label comes from the pure map `V2L.v2hQueueLabel(key)` (standard Arabic; table below). An unknown key shows «بند من المنصة».
- Click: `goOps(mod, land)`, the existing function. When `mod` is `null` («لا شاشة له»), render it as a non-clickable `<div>` with the suffix « · لا شاشة له بعد».

| key | label |
|---|---|
| trainer_applications_pending | طلبات مدرّبين |
| courses_pending | دورات تنتظر الاعتماد |
| manual_payments_pending | إيصالات تحويل |
| expert_files_in_review | آراء تنتظر مراجعتك |
| expert_files_awaiting_assignment | ملفات تنتظر التوزيع |
| expert_files_assign_overdue | ملفات لم تُستلم منذ ١٢ ساعة |
| expert_files_late | آراء متأخرة |
| expert_files_disputed | ملفات عليها ملاحظة من صاحب الطلب |
| consultation_disputes | نزاعات على استشارات |
| consultations_legacy | استشارات قديمة تنتظر قرارك |
| expert_files_blocked | ملفات توقفت أموالها |
| expert_files_unactivated | ملفات دُفعت ولم تصل إلى التوزيع |
| wallet_payouts_pending | طلبات سحب من المحافظ |
| stuck_card_payments | دفعات بطاقة عالقة |
| course_interests_24h | اهتمام بالدورات في آخر ٢٤ ساعة |
| training_interests_24h | مهتمون بالتدريب في آخر ٢٤ ساعة |
| course_split_pending | اقتسام إيراد معلّق |
| testimonials_pending | شهادات تنتظر المراجعة |
| topics_drafts | مسودات موضوعات |
| founding_leads_new | طلبات خبير مؤسس جديدة |
| pending_users_requested | زوّار ينتظرون فتح المنصة |
| lead_magnet_awaiting_asset | ملفات وُعد بها ولم تُسلَّم |
| live_needs_decision | دورات حيّة تحتاج قرارًا |

### 4.9 Data sources (all existing; no new route)
| Element | Source |
|---|---|
| rows | `window.INBOX` (loader `EP.ensure('inbox')`), `INBOX_FAILED`, `INBOX_TRUNCATED`, `EP.state.inbox` |
| ticket text | `V2L.v2Card(row,{now:Date.now()})` |
| late / match / fyi | `inboxIsLate`, `inboxMatches`, `inboxFyi` (globals in `index.html`) |
| brain log | `V2L.v2BrainLog(INBOX, now)` |
| counters | `EP.data.opsQueue` (`EP.ensure('opsQueue')`) through `opsQueueCounters` |
| auto-assign / service | `efAutoOn()`, `efServiceMode()`, `EP.data.efAllowlistSize` |

`V2SEC.home.inbox(v)` starts with `EP.ensure` for `inbox`, `opsQueue`, `pendingUsers` and `escrow`, the same keys old `viewInbox` ensured minus `dashboard`, which is no longer shown. Each ensure gets a callback that redraws only while this screen is still mounted (`document.getElementById('v2hDw')`).

---

## 5. The shared drawer (`#drawer`) — new look, same logic

### 5.1 What must not change
- No edit to `drawInbox`, `drawExpertFile`, `drawDispute`, `drawCase`, `drawLegacy`, `inboxActs`, `efRefundModal`, any `EP.*` call, any `data-a` value or any confirmation flow.
- Money stays behind the existing sheets with `confirmed:true`.

### 5.2 Restyle (`v2s/home.css`, all under `.app.v2-shell .drawer`)
- **Card:** `#fff`, border `#E9E1D6`, radius 20px, `box-shadow:0 10px 30px rgba(33,38,46,.08)`, overflow visible.
- **`.dh` (header):** no navy. The background is paper `#F6F1EA` with a 4px burgundy top border. `.k` is the burgundy kicker (Cairo 800, 12.5px). `h3` is ink (Cairo 800, 19px, line-height 1.5). Padding is 18px 20px.
- **`.db`:** padding 18px 20px 22px. `font-family:'IBM Plex Sans Arabic','Cairo'`. `overflow-wrap:anywhere` on every descendant, so long emails, links or references never cause horizontal scroll.
- **`.field`:** a two-line block. `.lab` is 12.5px `#7A7468` weight 700 and `.val` is 15px ink weight 600. There is a 1px `#F1EBE2` divider between fields.
- **`.route`:** pill row on `#FBFAF7`, radius 12.
- **`.note-ai`:** this is the brain's note. Render it as `.v2-brain`: paper background, the 36px brain avatar via a `::before` background image, and burgundy small heading text through CSS `content:'ما يراه العقل'` on `::before` of a wrapper. If that is impossible because of the markup, keep the existing icon with a burgundy colour.
- **`.policy`, `.ef-fyi-line`, `.ef-strip` and the inline `efStrip` boxes:** radius 14, no thick side border (`border-inline-start-width:4px`), padding 12px 14px, 14px text. Tones are keyed off the existing inline colours: conflict → `#FCEDEF`/`#9C0F25`; gold → `#FFF8E6`/`#7A5200`; ai → `#EEF3FA`/`#1F4E79`. Because the old markup uses inline `style` colours, override with `!important` on `background` and `color` inside `.app.v2-shell .drawer .policy`, and keep the inline border colour as the tone signal.
- **`.acts`:** `display:flex; flex-wrap:wrap; gap:10px`. Every `.btn` is `min-height:48px` (**52px at ≤760**), radius 14, `font:800 15.5px Cairo`, `padding:0 18px`, `flex:1 1 200px`.

| Button class | Look |
|---|---|
| `.btn-primary` and `.btn-human` | burgundy fill `#9E2B4E`, white text, hover `#85233F` |
| `.btn-ghost` | white, border `#E9E1D6`, ink text, hover `#FBF0F3` |
| `.btn-warn` and `.btn-refund` (money out) | white, border `#C8102E`, text `#C8102E`, hover `#FCEDEF` (the money action still opens its sheet) |
| `.btn-ask` | paper `#F6F1EA`, ink |
| `.btn-purge-ghost` | text `#9C0F25`, no border |
| `:disabled` | opacity .55 |
| focus | `outline:3px solid rgba(158,43,78,.45)` |

- **Inputs inside the drawer** (`select`, `textarea`, `input`): radius 12, border `#E9E1D6`, background `#FBFAF7`, `min-height:48px` (textarea `min-height:88px`), 15px text. Override the old inline `style` sizes with `!important` where needed.
- **`.ef-chip`, `.ef-pill`, `.status`, `.triage`:** 999px pills, 12.5px, 700, tone backgrounds as above.
- **`.ef-log`:** a timeline with burgundy dots. **`.ef-op`/`.ef-clause`:** paper cards, radius 14. **`.ef-verdict`:** a big pill.
- **`.empty`:** the elephant (`v2/img/brain-avatar.jpg`, 96px, round) via `::before`, then the hint text.
- **Narrow screens:** `#v2hDw` is the sheet wrapper. Its `.v2h-dbar` is visible below 1180, and the drawer's own top border is removed there.
  - The open state is `.v2h-dw.open`. At 761–1179 it is a side sheet (z 65) with a scrim `::before` (z 60). At ≤760 it is full screen, with padding bottom `calc(80px + env(safe-area-inset-bottom))` so the D1 pill never covers the last button.
  - It opens when `selected !== null`. **Close** («رجوع إلى الوارد», Escape, or a scrim tap) sets `selected=null; efDspOpen.id=null; efVoiceDrop(); efCaseUiReset();` and then calls `renderInbox()`.
  - The drawer's own «إغلاق» buttons already set `selected=null` and call `renderInbox()`, so the sheet closes through the same path.
  - Focus trap inside the open sheet; focus returns to the ticket on close.
- **Old screens of other sections** that render their own `<aside class="drawer" id="drawer">` (escrow, courses, market, invites…) get the same look automatically. That is intended.

### 5.3 Copy layer (switch on only): colloquial → plain standard Arabic, without touching `index.html`
- **Mechanism:** `V2SEC.home.copy` installs one `MutationObserver` on `document.body` (`childList:true, subtree:true`) when the shell boots. For each added element, or for the parent of an added text node, that is inside `.drawer`, `#epModal` or `#toasts`, it walks the text nodes plus the attributes `placeholder`, `title` and `aria-label` and applies `V2L.v2hCopy(text)`.
- **`v2hCopy(text)`** returns the replacement or `null`. It holds (a) an **exact-match map** of whole trimmed text nodes and (b) an ordered list of **regex rules** with capture groups for interpolated strings. It must be idempotent: a replaced string never matches again.
- **Textareas:** `TEXTAREA` default text is replaced only when `ta.value === ta.defaultValue`, meaning the founder has not typed yet.
- **Never touched:** `INPUT` values, anything inside `a[href]` text that is a URL or email, `.ef-quote` (the client's or expert's own words), `.ef-voice-msg`, `.ef-op` bodies that come from the platform (the expert's opinion text), the inline style or class of any element, and any `data-*` attribute.
- **Building the dictionary** is part of the build:
  1. Run the shots flow (§13) over every drawer kind in the fixtures (generic: join, trainer, pending_user, founding, verify, message site/platform, manual_payment, lead; expert_file in every lane: waiting, assigned, late, review, blocked, unactivated, contract, case_disputed; dispute file/consultation; legacy) and over every modal opened from those drawers (refund, send-to-expert pick, compare opinions, legacy decide, case decide, purge check) **without submitting**.
  2. Collect every visible text node and placeholder.
  3. Every string that contains a colloquial marker (list in §12.3) must get an entry.
  4. Write the replacements in plain standard Arabic, gender-neutral («صاحب الطلب», «الخبير» as role nouns), with no technical words and never «يقوّم».
  5. Keep numbers, names, amounts and currency exactly as captured.
- **Seed entries** (verified to exist in `index.html`):

| From (exact) | To |
|---|---|
| «اختر بندًا من الوارد لرؤية مساره الكامل والإجراء.» | «اختر بندًا من القائمة لترى تفاصيله وما يمكنك فعله.» |
| «رجّع الفلوس» | «أعد الأموال إلى صاحب الطلب» |
| «ابعته لحد تاني» | «أرسله إلى خبير آخر» |
| «رجّعه للخبير» | «أعده إلى الخبير» |
| «قارن الرأيين» | «قارن بين الرأيين» |
| «اعتبرها منتهية» | «اعتبرها منتهية» (already standard; keep) |
| «اعتمد وحوّل للموديول» | «اعتمد الطلب» |
| «عُولجت — عرض» | «عولجت تلقائيًا — اعرض» |
| «حوّل للخبير المحدَّد» | «أرسل إلى الخبير المختار» |
| «اطلب عيّنة/مستندًا — الصفّ يفضل مفتوح» | «اطلب مستندًا أو عيّنة — يبقى الطلب مفتوحًا» |
| textarea default «ابعتلنا رقم قيدك بالنقابة — أو رابط صورة الكارنيه — واكتبه في خانة «رقم القيد» في الاستمارة.» | «يُرجى إرسال رقم القيد في النقابة أو رابط صورة البطاقة، وكتابته في خانة «رقم القيد» في الاستمارة.» |
| field label «يُدار في موديول» | «القسم» |
| field label «حالة الفرز» | «الحالة» |
| «لا يوجد خبير معتمد في هذا التخصص بعد — اعتمد خبيرًا أولًا من «الخبراء والمدربون».» | «لا يوجد خبير معتمد في هذا التخصص بعد — اعتمد خبيرًا أولًا من «ملفات الخبراء ← الخبراء».» |
| regex `^اتبعت تلقائي لـ(.+)$` | `أُرسل تلقائيًا إلى $1` |
| regex `^اتبعت بإيدك لـ(.+)$` | `أرسلته بنفسك إلى $1` |
| regex `^فتح (.+)$` (the generic `goto` button) | `افتح $1` |

- **Exactness test:** for every exact key, the string appears verbatim in `index.html` **or** in a capture taken by the shots run, which is saved to `docs/v2/final/shots-home/copy-capture.json`. For every regex rule, at least one captured string matches. No dead entries.
- **Out of the copy layer:** server or platform error messages that pass through, such as «رفضت المنصة…». The platform's text stays as received, as D3 decided.

### 5.4 The confirmation sheet and toasts (shared chrome, same look)
Scope these under `body:has(> .app.v2-shell)`.

**`#epModal`:**
- `.scrim` is `rgba(33,38,46,.5)`;
- `.modal` is white, radius 22px, `max-width:560px` (D3's `:has(.v3m)` widths stay because they are more specific), and has a `.mh` header in paper with a 4px burgundy top;
- the title is Cairo 800 19px and the close button is a 44px square;
- `.mb` padding is 20px;
- `.mc-tab` rows are 15px with paper zebra striping, and the amount row is Cairo 800 18px;
- `.fld input/textarea` follow the drawer inputs;
- `.acts .btn` follow the drawer buttons (≥48px, 52px on mobile);
- **≤760: the sheet docks to the bottom** (`align-items:end`), at full width, with radius `22px 22px 0 0` and `max-height:92dvh; overflow:auto`.

**`.toast`:** ink `#21262E`, radius 14px, 14.5px text, a burgundy check icon, `bottom:20px; inset-inline-start:20px`. At ≤760 it is full width minus 32px and sits above the pill.

No logic changes in either.

---

## 6. Tabs summary for the section
| Tab | key | Screen | Status |
|---|---|---|---|
| «اللوحة والقرارات» | `board` | D1 board + focus (§3 polish) | new look kept |
| «كل الوارد» | `inbox` | rebuilt (§4) | **new** |
| «كل السجلات» | — | — | **none needed.** Every function of the old inbox has a place: rows → tickets; KPIs → chips; 23 counters → «أرقام المنصة»; auto-assign/FYI/service → strips; the drawer is kept and restyled. `ovKpiStrip` is dropped on purpose (§1). |

---

## 7. The bell — one panel: «حالة المنصة» + «الإشعارات»

### 7.1 Trigger and badge
- Keep the existing `#bellBtn` in the top bar. Make it 44×44, white, border `#E9E1D6`, radius 12 (the shell sets 42px today).
- When the shell is on, `V2SEC.home.bell.mount()` sets `bellBtn.onclick` to toggle `#v2HBell`. This is a property assignment that replaces the old toggle. The old document-click listener only hides `#notifPanel`, which CSS keeps hidden: `body:has(> .app.v2-shell) #notifPanel, … #bellCount {display:none!important}`.
- Add `<em class="v2h-bn">` inside `#bellBtn`. Its value is `v2hBellBadge(health, notif, seen)`:
  - the count is `health.alerts.length` (when not failed) plus the unseen notifications (`unread && !seen[id]`);
  - 0 → hidden;
  - both sources failed → «!» on amber;
  - one source failed → the count of the other source followed by «+».
  
  Burgundy circle with white Cairo 800 11px text. `aria-label` on `#bellBtn` is «التنبيهات · {n} جديدة», or «التنبيهات» when there are none.

### 7.2 Panel `#v2HBell` (appended to `body`)
- **Shape:**
  - desktop: a dropdown anchored under the bell, `width:420px`, `max-height:70vh`, radius 18;
  - tablet and mobile: a sheet from the top (`inset-inline:0; top:0`), `max-height:88dvh`, radius `0 0 22px 22px`, over a scrim;
  - in all cases it has the role `dialog` and is labelled «التنبيهات».
- **Behaviour:** Escape closes the panel. Clicking outside closes it. Focus moves to the close button, and the Tab key is trapped while it is open.
- **Header:** «التنبيهات» (Cairo 800 18px) + a close button «إغلاق» (44px).

**Part 1 — «حالة المنصة»**
Data: `EP.data.opsQueue` → `V2L.v2Health(Q, Date.now())`.
- Loading: «جارٍ الفحص…».
- Failed: «تعذّر فحص حالة المنصة — لا تعتبرها سليمة» + «أعد المحاولة» → `EP.reload('opsQueue', redraw)`.
- OK: a green dot + «كل شيء يعمل».
- Alerts: one amber card per alert text, already plain Arabic from `plainAlert`. If `v2hAlertSection(text)` returns a section key, the card gets a small button «افتح» → `V2_HOST.openSection(key)` and the panel closes:
  - files: «ملف», «رأي»;
  - disputes: «نزاع», «استشارة قديمة», «حجز»;
  - courses: «الالتحاق»;
  - otherwise no button.
- Below the alerts or the OK line: «آخر تشغيل للمهام الدورية». One row per heartbeat: `label` + `ago` (from `v2Health.heartbeats`). If there are none, omit this block.

**Part 2 — «الإشعارات»**
Data: `GET /api/notifications` via `EP.api('/notifications')`, which reads the reply field `items[]`. Accept a bare array too.
- **Fetch timing:**
  - once when the shell boots;
  - again each time the panel opens, if the last fetch is more than 60 s old;
  - never on a timer.
- Each fetch is one request with no retry loop.
- **States:**
  - loading: 2 skeleton rows;
  - error: «تعذّر جلب الإشعارات» + «أعد المحاولة»;
  - empty: «لا إشعارات جديدة».
- **Row:**
  - an unseen dot;
  - title `v2hNotif(item).title`;
  - detail `v2hNotif(item).detail`;
  - time `V2L.util.agoText(Date.parse(item.when), now)`, or nothing when it is unknown.
  
  The whole row is a button, ≥56px tall. Click: mark it seen, then `V2_HOST.openSection(dest.section, dest.tab)` when `dest` is known, then close the panel.
- **Header action:** «علّم الكل كمقروء» marks every current id as seen.
- **«Seen»** is a per-viewer convenience: `localStorage['ep_v2h_seen']` holds a JSON array of ids, capped at the newest 300, and every read or write is in try/catch. Server truth is unchanged. Items with `unread:false` (signups) never count in the badge.
- Session-local `NOTIFS` from the old `notify()` are **not** shown. They already appeared as toasts, and the old bell's mixing of them with server items was its own source of noise.

### 7.3 `v2hNotif(item)` — the mapping by `kind` (pure; tested)
| kind | title | detail | dest |
|---|---|---|---|
| `message` | «رسالة جديدة من نموذج التواصل» | the server detail as is (`name: topic`) | `people/messages` |
| `withdrawal` | «طلب سحب من مستثمر ينتظر المراجعة» | the server detail with a trailing ` USD` → ` دولار`, and Latin digits → Arabic digits | `company/invest` |
| `trainer_application` | «طلب انضمام مدرّب جديد» | `{who}` only: drop the suffix « بانتظار الموافقة» | `courses/trainers` |
| `program_request` | «طلب برنامج أو دورة ينتظر المراجعة» | server detail | `courses/courses` |
| `signup` | «حساب جديد على المنصة» | `{who}` only: drop the suffix « أنشأ حسابًا» | `people/users` |
| unknown | the server `title` if it has no Latin letters, otherwise «إشعار» | server detail | `null` |

---

## 8. The login screen and the first-load splash

### 8.1 Which look
At the top of `v2s/home.js`, which runs before `EP.start` because `EP.start` waits for `DOMContentLoaded` + `setTimeout 0`, run:
`try{ if(localStorage.getItem('ep_v2_shell')==='1') document.documentElement.classList.add('v2h-login'); }catch(e){}`
When the shell boots, also add the class, so a later 401 that re-shows the login overlay gets the new look.

### 8.2 New look (CSS only, `html.v2h-login .ep-login …`; the IDs and JS of `showLogin` are untouched)
- **Background:** paper `#FBFAF7`. On desktop ≥900 there are two halves:
  - the start (right) half is the form card;
  - the end (left) half is a photo panel built from `.ep-login::before` with `background:linear-gradient(to top, rgba(158,43,78,.92), rgba(158,43,78,.25)), url(v2/img/company.jpg) center/cover`, `border-radius:28px`, inset 24px.
  
  The panel carries the line «غرفة التحكم في البروفيسور» through `.ep-login::after` (`content`), in Aref Ruqaa 40px, white, at the bottom with 40px padding.
- **Card:** white, radius 24, `max-width:420px`, shadow `0 20px 50px rgba(33,38,46,.12)`, no navy.
  - `.hd` is transparent with the burgundy mark (52px, radius 14) and the burgundy «البروفيسور» (Aref Ruqaa 28px); the small line is in `#7A7468`.
  - `.bd` padding is 8px 28px 28px.
  - `.ttl` is Cairo 800 24px ink.
  - `.hint` is 14.5px `#6B665C`.
  - `.lab` is 13px 700.
  - Inputs are 52px tall, radius 14, background `#FBFAF7`, border `#E9E1D6`, with a burgundy focus ring.
  - `.sub` is 56px, burgundy, Cairo 800 17px, radius 14.
  - `.err` is `#FCEDEF`/`#9C0F25`, radius 12.
- **Mobile ≤760:** the photo becomes a 180px top banner (`::before` static, `inset:auto`), the card is full width with a 16px gutter, nothing scrolls horizontally, and the inputs keep `font-size:16px` so iOS does not zoom.
- **Copy stays** (already standard Arabic): «تسجيل الدخول», «ادخل ببيانات حسابك الإداري للوصول إلى غرفة العمليات.», «البريد الإلكتروني», «كلمة المرور», «دخول», «جارٍ الدخول…», «البريد وكلمة المرور مطلوبان.», «بيانات الدخول غير صحيحة.».

### 8.3 Splash while the switch answer is pending (`.app.v2-pre`, CSS only)
`.app.v2-pre::after{content:'جارٍ فتح لوحتك…'; position:fixed; inset:0; display:grid; place-items:center; padding-top:150px; background:#FBFAF7 url(v2/img/brain-avatar.jpg) center calc(50% - 40px)/120px no-repeat; font:800 18px Cairo; color:#21262E; z-index:5}`.
Respect `prefers-reduced-motion`: no animation. A gentle fade is allowed otherwise.

### 8.4 The one known switch-off edge
If the server switch is turned off after the founder last loaded the dashboard with it on, the very next login screen on that same browser still shows the new look once. The first authed `/api/v2/config` answer removes the flag, and from then on the screen is the old one. No logic differs and only colours change. Write this in STATUS.

---

## 9. Shared edits (exact; keep them minimal; list them in the report as `shared_edits`)

**S1. `dashboard-cloud/index.html`, `viewInbox`, as its first statement:**
```js
function viewInbox(v){
  if(window.V2SEC&&V2SEC.home&&V2SEC.home.inbox&&V2SEC.home.inbox(v))return;
```
`V2SEC.home.inbox(v)` returns `true` only when `window.V2_ON && window.V2SHELL && V2SHELL.on && role==='admin'`. Otherwise it returns `false` and does nothing. In that case the old body runs byte for byte.

**S2. `renderInbox`, as its first statement:**
```js
function renderInbox(){
  if(window.V2SEC&&V2SEC.home&&V2SEC.home.list&&V2SEC.home.list())return;
```
`list()` returns `true` only when the same condition holds **and** `#v2hDw` exists, meaning the new screen is mounted. It redraws the head, chips and rows and then calls `drawInbox()`.

**S0. The block** (create it if missing, right after `<script src="v2-d2.js"></script>`, one line per file, alphabetical by key):
```html
<!-- v2 sections begin -->
<link rel="stylesheet" href="v2s/home.css">
<script src="v2s/home.js"></script>
<!-- v2 sections end -->
```
The script must load **after** `v2-logic.js`, `v2-home.js` and `v2-shell.js`, which it is, and **before** the inline script, which is fine because it only defines functions and the login flag.

**S3. Both Dockerfiles,** after the `COPY dashboard-cloud/v2/img …` line: `COPY dashboard-cloud/v2s /app/dist/v2s`. Copying the whole directory means every section's files go with one identical line, and identical hunks merge cleanly.

**S4. `backend/tests/test_xss_hardening.py:628`:** add `|v2s/[a-z0-9_]+\.js` inside the negative lookahead. The test still forbids any external script.

**No other edit outside the section's own files.**

---

## 10. Pure helpers (`v2-logic.js`, block `// ===== v2s:home =====`)
All of them have no DOM and no network, use Arabic digits through `L.util.ar`, and never invent a number. An unknown input gives `null` or `''`, never 0.

| Function | In → out |
|---|---|
| `v2hChips(ctx, counts, active)` | `ctx ∈ home/files/disputes/messages`; `counts` = `{filterKey: n}` (computed by the caller with `inboxMatches`); returns `{row1:[{key,label,n,on,tone}], row2:[…]}` following §4.3 (zero hidden unless active or `all`) |
| `v2hTone(row, card, isLate)` | → `'late'|'money'|'done'|'wait'` |
| `v2hFlags(row)` | → `[{t, tip?}]` (§4.4 table) |
| `v2hGroups(items)` | `items=[{card,row,late}]` → `[{key:'late'|'wait'|'auto', label, items}]`, with the stable sort of §4.4. Empty groups are dropped. |
| `v2hNorm(s)` / `v2hSearchText(row, destLabel, card)` | §4.6 |
| `v2hBrainLine(items, brainLogLen, state)` | §4.5 (1). `state ∈ ready/error/loading`. Returns `null` on error or loading. |
| `v2hQueueLabel(key)` | §4.8 table |
| `v2hAlertSection(text)` | §7.2 |
| `v2hNotif(item)` | §7.3 → `{id, title, detail, when, unread, dest:{section,tab}|null}` |
| `v2hNotifList(reply)` | accepts `{items:[…]}`, `{notifications:[…]}` or `[…]`; anything else → `null` (meaning failed) |
| `v2hBellBadge(health, notifs, seen)` | §7.1 → `{text, tone:'none'|'count'|'warn'}` |
| `v2hCopy(text)` | §5.3 → the replacement or `null` |
| `V2H_COLLOQUIAL` | the marker list of §12.3, used by the tests and the shots |

---

## 11. Visible strings (exact; all new strings in this round)
Section and tab names are unchanged. New strings are gathered here so a reviewer can scan them in one place:
- **Search:** «ابحث باسم صاحب الطلب أو بريده أو الخدمة» (placeholder), «ابحث في الوارد» (label), «امسح البحث», «لا بنود تطابق «{q}»».
- **Groups:** «متأخر» · «ينتظر قرارك» · «عولجت تلقائيًا» · «اعرض المزيد ({n})».
- **Chips:** see §4.3. **Flags:** see §4.4. **Queue labels:** see §4.8.
- **Head lines:** see §4.5 (brain line, failed, partial, truncated, service, auto-assign including the confirm, FYI).
- **Empty states:** «جارٍ جلب الوارد…» · «لا نعرف الآن ما ينتظرك» · «لا شيء ينتظرك هنا الآن» · «لا بنود ظهرت، لكن تعذّر جلب {names} — لا تعتبر القائمة فارغة» · «لا بنود في هذا الاختيار» · «اعرض الكل» · «غير معروف الوقت».
- **Drawer sheet:** «رجوع إلى الوارد».
- **Bell:**
  - frame: «التنبيهات», «إغلاق», «حالة المنصة», «جارٍ الفحص…», «تعذّر فحص حالة المنصة — لا تعتبرها سليمة», «أعد المحاولة», «كل شيء يعمل», «افتح», «آخر تشغيل للمهام الدورية»;
  - notifications: «الإشعارات», «تعذّر جلب الإشعارات», «لا إشعارات جديدة», «علّم الكل كمقروء», «التنبيهات · {n} جديدة»;
  - item titles: see §7.3.
- **Board health line:** see §3.1 (2).
- **Splash:** «جارٍ فتح لوحتك…». **Login photo line:** «غرفة التحكم في البروفيسور».

**Rules the tests enforce on every string in `v2s/home.js` and on the values of `v2hCopy`:**
- No Latin letters, except the CSS/JS identifiers that are not shown.
- No «ذكاء» or «AI» at the start of any headline.
- No «يقوّم».
- No colloquial marker (§12.3).
- No gendered address to a third party: «صاحب الطلب» and «الخبير» are used as role nouns.

---

## 12. Tests — `backend/tests/test_v2s_home.py` (zero network; node through `uiharness/v2_node.py`)

### 12.1 Wiring and switch safety
1. `index.html` holds the `<!-- v2 sections begin -->…<!-- v2 sections end -->` block exactly once, placed after `v2-d2.js`, with the `home` link and script lines.
2. `viewInbox` and `renderInbox` each start with the exact S1/S2 line, and each line appears once.
3. **Switch off = old path.** Load `v2s/home.js` in `node:vm` with a fake `window`/`document`. In each of these cases, `V2SEC.home.inbox(v)` and `.list()` return `false` and make no DOM write:
   - (a) `V2SHELL` is missing;
   - (b) `V2SHELL.on=false`;
   - (c) `role='employee'`;
   - (d) `V2_ON=false`.
4. The bell is not mounted and `#bellBtn.onclick` is untouched when the shell is off (node vm).
5. The login class is added only when `localStorage.ep_v2_shell==='1'`, and nothing throws when `localStorage` throws.
6. Both Dockerfiles contain `COPY dashboard-cloud/v2s /app/dist/v2s`.
7. `test_xss_hardening` still passes. Assert that the regex allows only `v2s/<name>.js`.
8. **Every selector in `v2s/home.css`** starts with one of `.app.v2-shell`, `body:has(> .app.v2-shell)`, `html.v2h-login`, `.app.v2-pre` or `@media`/`@keyframes` (parsed with a simple regex). Nothing global.
9. `backend/app.py` is unchanged by this branch: `git diff --stat 7d1aa83 -- backend/app.py` is empty.

### 12.2 Pure helpers (node)
- `v2hChips`:
  - home order and labels;
  - zero-count chips hidden, while `all` and the active chip always show;
  - the files context gives row 2 only there;
  - the messages context gives empty rows;
  - counts pass through unchanged, with Arabic digits.
- `v2hGroups`: late first; then rank; then oldest; unknown `ts` last; stable on ties; empty groups dropped.
- `v2hTone` and `v2hFlags`: every branch, plus licensed vs licence-missing exclusivity.
- `v2hNorm` and the search: hamza/ta-marbuta/ya forms; tashkeel; Arabic digits; email substring.
- `v2hBrainLine`:
  - late wording for 1, 2, 3 and 11 items;
  - the oldest title;
  - the brain-log suffix only when >0;
  - `null` on error;
  - «لا شيء ينتظرك…» only with zero items **and** state ready.
- `v2hQueueLabel`: all 23 keys of `opsQueueCounters` (parse the `index.html` source for `'…',n(Q.<key>)` / the fourth element) have a label. Unknown → «بند من المنصة».
- `v2hNotifList`: the server shape `{count,total,items}` (**the regression for the old bug**), a bare array, a legacy `{notifications}`, and garbage → `null`.
- `v2hNotif`: each kind; signup detail without «أنشأ حسابًا»; `USD` → «دولار» and digits Arabic; unknown kind with a Latin title → «إشعار»; dest mapping.
- `v2hBellBadge`: 0 → hidden; alerts + unseen; seen ids excluded; `unread:false` excluded; both failed → «!»; one failed → `n+`.
- `v2hAlertSection`: one example per section, plus `null`.
- `v2hCopy`:
  - every exact key is found verbatim in `index.html` or in `docs/v2/final/shots-home/copy-capture.json`;
  - every regex matches at least one captured string;
  - the output is idempotent (`v2hCopy(v2hCopy(x)) === null`);
  - no output contains a colloquial marker or «يقوّم».

### 12.3 Copy rules (applied to every visible string in `v2s/home.js`, to the `v2hCopy` outputs and to the shots captures)
- `V2H_COLLOQUIAL` = `['مش ', 'دلوقتي', 'اتبعت', 'اتدفع', 'اتستلم', 'بتاع', 'عايز', 'هيت', 'ابعته', 'رجّع', 'مستني', 'لوحده', 'لوحدها', 'إيه', ' ليه', 'كده', 'اللي', 'تاني', 'مالهاش', 'بقى', 'إزاي', 'خالص', 'يقوّم']`.
- No string starts with «ذكاء»/«الذكاء»/«AI».
- No Latin letters in visible text, except emails, URLs and transfer references inside drawer fields.

### 12.4 Old suites (re-run file by file, in the sandbox)
- `test_v2_d1.py` (129), `test_v2_d1b.py` (29), `test_v2_d2.py` (67), `test_v2_d3.py` (110) — expected unchanged.
- `test_expert_files_*`, `test_dash_*`, `test_xss_*` — unchanged, because the switch-off path is byte-identical.
- The three port tests (`test_dash_ia_ui`, `test_dash_company_badges`, `test_dash_finance_sources`) are known sandbox failures. List them for the main session.

---

## 13. Shots — `backend/tests/uiharness/v2_shots_home.py` → `docs/v2/final/shots-home/`

**Setup:**
- `cd backend && python3 -B tests/uiharness/v2_shots_home.py ../docs/v2/final/shots-home`.
- Import `Harness, DASH` from `ef_route_harness`, `v2_fixtures as v2fx`, `d3_fixtures as d3fx`, and `check`, `shell_check`, `Browsers`, `open_shell`, `go_section` from `v2_shots` (read-only).
- Viewports: desktop `d` 1440×900, tablet `t` 820×1180, mobile `m` 390×844 (`mobile=True`).
- `DASH_V2_ENABLED=true`, except in shot 30.
- **Seed** (in-process, before the flows, inside `h.app.app_context()`): 2 `Message(status='new')` rows and 1 `WithdrawalRequest(status='pending')` row with a wallet, so `/api/notifications` has local items. The fake platform already serves trainer applications and users.

**Shots (each at d, t and m unless marked):**

| # | Name | What |
|---|---|---|
| 01 | `board` | the board, polished: no pill row, health line in the dark bar |
| 02 | `board-health-alerts` | the board with fixture alerts: amber health line |
| 03 | `bell-open` | the bell with alerts + 3 notifications (1 seen) + heartbeats |
| 04 | `bell-failed` | opsQueue 503 + notifications 500 → the two failure texts and badge «!» |
| 05 | `inbox-all` | «كل الوارد» full: brain line, auto-assign line, FYI line, groups |
| 06 | `inbox-late` | chip «متأخر» |
| 07 | `inbox-files-sub` | files/all tab (`#s/files/all`) with sub-chips |
| 08 | `inbox-search` | search «عقد» |
| 09 | `inbox-nomatch` | search with no match |
| 10 | `inbox-partial` | one inbox source failing (`INBOX_FAILED`) |
| 11 | `inbox-error` | inbox load error, empty |
| 12 | `inbox-empty` | all sources ok, zero rows |
| 13 | `drawer-file` | expert file drawer open (t/m = sheet) |
| 14 | `drawer-dispute` | dispute drawer |
| 15 | `drawer-join` | generic drawer with the reason and request-info textareas (copy layer applied) |
| 16 | `drawer-receipt-modal` | manual payment → confirmation sheet open (not submitted) |
| 17 | `drawer-refund-modal` | expert file → «أعد الأموال» sheet open (not submitted) |
| 18 | `auto-off-confirm` | «أوقفه» inline confirm |
| 19 | `fyi` | FYI view |
| 20 | `queue-open` | «أرقام المنصة» open |
| 21 | `disputes-all` | `#s/disputes/all` |
| 22 | `messages` | `#s/people/messages` |
| 23 | `focus-open-drawer` | focus card «غيّر / افتح» → drawer, with the pill visible above it (m) |
| 24 | `login` | logged out with `ep_v2_shell='1'` |
| 25 | `login-error` | wrong password («بيانات الدخول غير صحيحة.») via a fixture 401 |
| 26 | `splash` | `.v2-pre` held (delay `/api/v2/config` with the harness `hold`) |
| 30 | `switch-off` | d and m only: the inbox and the login with the switch off. Assert the old DOM: `#ovKpis`, `.kpis .kpi` ×4, `#filters .chip`, `.row.inbox-row`, `.ep-login` without the `v2h-login` class. |

**Checks** (the script fails on any of these):
- `check()` and `shell_check()` from D1/D1-B;
- horizontal scroll at 390 or 820;
- any visible `button`, `[role=button]` or `.v2h-chip` under 44px;
- at ≤760, any `.drawer .acts .btn`, `#epModal .acts .btn` or `.v2h-dbar button` under 52px;
- any `V2H_COLLOQUIAL` marker visible inside `.v2h`, `#drawer`, `#epModal`, `#v2HBell`, `.v2-next` or `#epLogin` (switch-on shots only);
- «undefined», «NaN», «null» or a raw `0` where the spec says «غير متاح بعد» or «تعذّر»;
- any request outside `DASH` except Google Fonts;
- any `POST`/`PUT`/`PATCH`/`DELETE` to the dashboard during the flows (no shot submits anything);
- a switch-off shot whose old selectors are missing;
- writing `copy-capture.json` (every distinct visible text node and placeholder inside `#drawer` and `#epModal` across shots 13–17 plus the extra drawer kinds listed in §5.3) for test 12.2.

---

## 14. Platform needs
**Nothing in this round needs new platform data.** Every element reads an existing dashboard loader or route. Two **optional** platform improvements would remove fragile text-matching. Log them for the platform session; nothing here waits for them:
1. **Structured alerts in `GET /api/bridge/ops/queue`.** Next to the current `alerts: [string]`, add `alerts_v2: [{"key": "expert_files_late", "count": 3, "oldest_hours": 26.5, "section": "files"}]`. `key` uses the same names as the existing counters. `section` is one of `files|disputes|courses|money|people|content|system`. With it, `v2Health`/`v2hAlertSection` stop parsing colloquial Arabic with regexes (`v2-logic.js:817-848`).
2. **The person's email and an ISO time on every bridge row that feeds the inbox** (`created_at` for trainer applications, join requests, founding leads, platform messages and `program-requests`). Rows whose `ts` is 0 today show «غير معروف الوقت» and sort last. The shape is unchanged; only fill the missing `created_at` (ISO-8601 UTC).

---

## 15. Out of scope (owned elsewhere or deliberately left)
- The ticket boards in «ملفات الخبراء» and «النزاعات» (D2, files/disputes sections), the person page, and the money and books screens.
- **The old bell bug in `dashboard-api.js:2575`.** It is not fixed here, because fixing it changes switch-off behaviour. Report it to the main session as a one-line fix for when the old screen is retired: `(r && (r.items || r.notifications))`.
- Server-side read state for notifications.
- Any AI call. The brain lines are facts computed from stored data.
- The colloquial **toasts written by `dashboard-api.js` `note()`** (for example «التوزيع التلقائي اشتغل ✓») are covered by the copy layer through `#toasts`. Add their keys to the dictionary when captured.

## 16. Done =
1. `test_v2s_home.py` passes. The D1/D1-B/D2/D3 suites keep their counts. The old suites pass file by file (minus the 3 known port tests).
2. The shots exist in `docs/v2/final/shots-home/` with `problems: []`.
3. `docs/v2/final/STATUS-home.md` contains:
   - what was built;
   - the `shared_edits` (S0–S4);
   - the ownership claim (§2);
   - the switch-off edge (§8.4);
   - the copy dictionary size;
   - the old bell bug.
4. One commit (or a few) on `final-home` with explicit paths and an Arabic message. No push.
