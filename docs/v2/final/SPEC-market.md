# Final round — «سوق الخدمات» (`market`): tickets with a timer, the brain's line, one button

**Founder order (2026-10-30):** «ابدأ الجولة… الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا». This is final work, not a draft.
**Approved concept:** the «المعتمد» row of the dashboard canvas — `POS-Tickets.dc.html` («ب٤ · جوه القسم: تذاكر بعدّاد زي المطبخ»; it even shows «طلبات السوق ٤» as a ticket tab), `POS-Home.dc.html` / `POS-Phone.dc.html` (tile «سوق الخدمات · ٤ طلبات بلا خبير مناسب»).
**Reference style:** D1-B shell, D2 ticket boards (`v2-d2.js/.css`), D3 sheets (`v2-d3.js` `openSheet`/`twoStage`).
**Worktree / branch:** `.worktrees/market` / `final-market` (from `7d1aa83`). Everything sits behind `DASH_V2_ENABLED` + the new shell; flag off = byte-identical behaviour.
**Founder priority to keep in mind:** «السوق للداتا» (NOTES 2026-10-30). The market is mostly a demand signal today; the screen must make the signal readable and keep every moderation lever, not invent new money paths.

⛔ Zero real network calls. Zero paid API calls. No push/deploy. No money action exists in this section (market offers are accepted by the request owner on the platform, never from the dashboard).

---

## 0) What exists today (the old `market` screen) and where each piece goes

Old screen: `dashboard-cloud/index.html` `viewMarket()` (≈ line 6037), `drawMarketReq()`, `mkDemandPanel()`, `wireMarketDemand()`, `trainingInterestPanel()`, `wireTrainingInterest()`. Data: `dashboard-api.js` loaders `market` (`mapMarket`), `marketDemand`, `trainingInterests`; actions `EP.marketRequestDetail`, `EP.closeMarketRequest`, `EP.hideMarketRequest`. Server: `backend/app.py` `/api/platform-market-requests` (+ `/<id>`, `/<id>/close`, `/<id>/hide`), `/api/platform-market-demand`, `/api/training-interests` → platform bridge `marketplace.py` `/api/bridge/market/requests*`, `ops_bridge.py` `/api/bridge/market/demand`, `/api/bridge/training-interests`.

| Old piece | New home | Notes |
|---|---|---|
| Policy banner «السوق: العضو بيكتب…» | removed | explanation boxes are banned (feedback_mock_design_effort). |
| «جسر لسه ما اتنشرش» card (shows `/api/bridge/...`, `api.elprofessor.net`) | «غير متاح بعد» state on each tab | no technical words in visible copy. |
| 4 KPIs (إجمالي · مفتوحة · بلا عرض · تمّت مطابقتها) | one header line on the board (§3.2) | numbers from the bridge's `counts.by_status`, not a page count. |
| Lane tabs (`MK_LANES`) | lane chips on the board (demand lanes) + lane chips in «كل الطلبات» (all lanes incl. «عروض المدرّبين») | |
| need_kind chips + status chips | «كل الطلبات» filters | |
| Request list + right drawer | tickets (§3) + new drawer (§4) | same row data, same detail endpoint. |
| «إغلاق الطلب» | drawer + ticket button where the brain suggests it (§5.1) | same endpoint `POST /api/platform-market-requests/<id>/close`. |
| «إخفاء عن البورد العام» / «أظهر الطلب على البورد» | drawer (§5.2/§5.3) | same endpoint `POST /api/platform-market-requests/<id>/hide`. |
| «الطلب الحقيقي — نبني إيه بعد كده؟» panel + «حدّث» + «اعمل الدورة» | tab «ماذا يطلب الناس» (§7) | same loader `marketDemand`, same `createCourseModal(title)`. |
| «مين طلب التدريب» panel + «حدّث» + `tel:` links | tab «ماذا يطلب الناس», block «من طلب التدريب» (§7.5) | same loader `trainingInterests`. |

New levers (platform endpoints that already exist but had no dashboard button, listed as missing in `DASHBOARD-MAP-2026-10-30.md` §bridge «market relane/annotate ❌»):
- «انقله إلى …» → bridge `POST /api/bridge/market/requests/{id}/relane` (the brain suggests it only on a factual lane mismatch).
- «اربط دورة» → bridge `POST /api/bridge/market/requests/{id}/annotate {linked_course_id}` (the brain suggests it only when an open-demand card reached its goal without a course).

**Nothing stays as «كل السجلات».** Every old block is rebuilt; the old `viewMarket` keeps running only for the old shell (flag off) and for non-admin roles (employee).

---

## 1) Section map (only our `SECTIONS` entry in `v2-logic.js`)

```js
{ key: 'market', label: 'سوق الخدمات', img: 'market', desc: 'طلبات الأعضاء وعروض الخبراء', tabs: [
  T('requests', 'الطلبات', 'market'),
  T('all', 'كل الطلبات', 'v2s_market_all'),
  T('demand', 'ماذا يطلب الناس', 'v2s_market_demand')
] },
```

- The first tab keeps the **old module key `market`** on purpose: every old link (`#market`), the home tile (`T.market.dest = 'market'`), Telegram links (rows 68–71 in DASHBOARD-MAP «🛒 طلب جديد في السوق…») and `go('market')` keep landing on the board through `sectionFor('market')`, with no alias/redirect edit. Under the new shell our module **owns** `market`, so `viewMarket` is never reached there.
- `v2s_market_all` / `v2s_market_demand` are pseudo modules (like `v2files`), reachable only through `#s/market/all` and `#s/market/demand`.
- Addresses: `#s/market` = `#s/market/requests` (board) · `#s/market/all` · `#s/market/demand`.

---

## 2) Files and wiring (parallel-safe)

New files:
- `dashboard-cloud/v2s/market.js` — the whole front end of this section (IIFE, `window.V2S_MARKET`).
- `dashboard-cloud/v2s/market.css` — all styles, every rule scoped under `.v2s-mk` (plus reused `.v2d-*` ticket classes from `v2-d2.css`, read-only, for an identical ticket look).
- `backend/v2_market_routes.py` — `register(app, ns)` with the 3 new routes (§8).
- `backend/tests/test_v2s_market.py`, `backend/tests/uiharness/market_fixtures.py`, `backend/tests/uiharness/v2_shots_market.py`.

Edits to shared files (minimal, listed again in the report as `shared_edits`):
1. `dashboard-cloud/index.html`, block `<!-- v2 sections begin -->` … `<!-- v2 sections end -->` (create it right after `<script src="v2-d2.js"></script>` if missing), alphabetical by key, one line per file:
   ```html
   <link rel="stylesheet" href="v2s/market.css">
   <script src="v2s/market.js"></script>
   ```
2. `dashboard-cloud/index.html` `renderView()` — **one generic hook**, placed right after the D3 line (`if(window.V2_ON&&window.V2D3&&V2D3.owns(current))…`). This is unavoidable: without it no new section can render. Every section uses the same text, so the merge keeps one copy:
   ```js
   // v2 sections (final round): كل قسم يسجّل نفسه في window.V2SEC = [{owns(mod), render(mod, view)}].
   if(window.V2_ON&&window.V2SEC){for(var _i=0;_i<V2SEC.length;_i++){if(V2SEC[_i].owns(current)){var _ap=document.querySelector('.app');if(_ap)_ap.classList.add('v2-bare');return V2SEC[_i].render(current,v);}}}
   ```
   `market.js` registers: `(window.V2SEC = window.V2SEC || []).push({ owns: M.owns, render: M.render })`.
   `M.owns(mod)` is true only when `window.V2SHELL && V2SHELL.on && window.V2_ON` **and** `mod ∈ {market, v2s_market_all, v2s_market_demand}`. So the old D1 mode (flag on, no shell) and non-admin roles keep `viewMarket`.
3. `dashboard-cloud/v2-logic.js`: only the `market` entry in `SECTIONS` (§1), plus pure helpers appended at the end of the file inside `// ===== v2s:market =====` … `// ===== /v2s:market =====` as a second IIFE that attaches `V2L.v2sMarket = {...}` (the same object `module.exports` points to, so node tests see it).
4. `backend/app.py`: one line right before `# ---- v2 section routes end` (create the marker once, right after the last v2 route `v2_book_request_patch`, before `@app.route('/api/platform-pnl'`):
   ```python
   import v2_market_routes as _v2s_market; _v2s_market.register(app, globals())  # noqa: E402
   ```
   ⛔ `_platform_proxy` (line ≈2710) and `_market_proxy` are defined **after** the marker, so `register()` reads every helper **lazily** from `ns` inside each handler (`ns['_platform_proxy'](...)`), never at registration. Only `token_required` / `roles_required` (defined at ≈788/806) are taken at registration.
5. `backend/tests/test_v2_d1b.py` line 87: the expected tabs for `market` become `[['requests','الطلبات','market'], ['all','كل الطلبات','v2s_market_all'], ['demand','ماذا يطلب الناس','v2s_market_demand']]`. Nothing else in old tests changes (the old link `#market` still lands on `('market','requests')`).

No edit to `dashboard-api.js`, `v2-home.js`, `v2-shell.js`, `v2-d2.*`, `v2-d3.*`.

---

## 3) Tab «الطلبات» — the ticket board

### 3.1 Data
- Source: the existing loader `market` (`EP.ensure('market', redraw)`) → `EP.data.market = {rows, count, counts, missing}` from `mapMarket()` (fields per row: `id, kind, need_kind, title, body, specialty, service, status, visibility, member_alias, member_email, member_name, preferred_expert_email, budget, currency, offer_count, accepted_offer_id, consultation_id, is_test, hidden, hidden_reason, created_at, at`).
- ⚠️ `mapMarket()` drops bridge fields the board needs. `market.js` reads them from `EP.data.market.raw` (the unsorted bridge list; `rows` are sorted, so match by `id`, never by index): `author_kind`, `open_demand`, `join_goal`, `joined_count`, `goal_reached_at`, `last_offer_at`, `updated_at`, `stale_unanswered`, `linked_course_id`, `linked_course_slug`, `source`, `catalog_name`, `last_activity_at`. A pure helper `v2sMarket.merge(rows, raw)` returns rows enriched with these keys (absent ⇒ `undefined`, never 0). No change to `dashboard-api.js`.
- The same loader feeds the home tile, so the tile and the board never disagree about the source.
- `counts.by_status` / `count` (bridge `total`) are whole-collection numbers.

### 3.2 Board header (above the columns)
Left to right (RTL), wraps on narrow screens:
1. **Brain line** (`.v2d-auto` pill with `v2/img/brain-avatar.jpg`):
   - N > 0: «العقل: {U(N, ['طلب واحد بلا عرض','طلبان بلا عرض','طلبات بلا عرض','طلبًا بلا عرض'])}، أقدمها منذ {durShort(oldest)}».
   - N = 0 and open requests exist: «العقل: كل طلب مفتوح وصله عرض أو يجمع المنضمّين».
   - No open requests: «العقل: لا طلبات مفتوحة الآن».
   - N = the **same formula as the home tile** (`v2-home.js marketCount`): `status==='open' && !hidden && !is_test && kind!=='training_offer' && !offer_count`. The test pins that this equals the number of non-hidden tickets in columns «طلب جديد» + «ينتظر خبيرًا».
2. **Totals line** (`.v2d-open-total`): «في السوق الآن: {ar(open)} مفتوح · {ar(matched)} تمّت مطابقته · {ar(closed)} أُغلق». From `counts.by_status` (missing key = 0 only when `counts.by_status` itself exists, because the bridge omits zero buckets by contract). If `counts` is null: computed from rows + suffix « (من المعروض فقط)».
3. **Lane chips** (44px, `role=tablist`): «كل الطلبات ({n})» · «طلبات الخبرة ({n})» · «طلبات الدورات ({n})» · «خدمات للجمهور ({n})». Counts from `counts.by_lane` (`request`, `course_request`, `public_service`); «كل الطلبات» = sum of the three. Chips with 0 still show (a lane with nothing is a fact). In-memory state `S.lane`, default `all`.
4. **Supply link** (text button, 44px): «عروض المدرّبين ({n}) في «كل الطلبات»» → opens `#s/market/all` with lane `training_offer`. Shown only when `counts.by_lane.training_offer > 0`. Training offers are supply, so the platform never mixes them into the demand board (`marketplace.py` line ≈1303), and neither do we.
5. **Test toggle** (only when test rows exist): «أظهر التجريبي ({n})» / «أخفِ التجريبي». Default hidden.

Warning strips (`.v2d-warn`, above the columns):
- Truncated (`count > rows.length`): «معروض {ar(rows)} من {ar(count)} طلب، فالأعمدة ناقصة. القائمة الكاملة في «كل الطلبات»» + button «افتح كل الطلبات».

### 3.3 Columns — pure classifier `V2L.v2sMarket.tickets(rows, opts)`
`opts = {now, lane:'all'|'request'|'course_request'|'public_service', showTest:false}` ⇒ `{cols:{new:[],waiting:[],offered:[],done:[]}, counts, shown, more, doneOlder, testCount, hiddenCount}`.

Rows dropped first: `kind === 'training_offer'`; `is_test` unless `showTest`; lane filter.

| Column key | Label | Rule (first match wins) | Strip tone | Timer (`V2L.v2TimerText`) | Order |
|---|---|---|---|---|---|
| `done` | «انتهى» | `status ∈ {matched, closed}` | grey `#8FA89D` (as D2 «خلص») | `updated_at`: today ⇒ `hh:mm`, else `dateText`; missing ⇒ none | newest first; only `updated_at` (fallback `created_at`) within 7 days; the rest counted in `doneOlder` |
| `offered` | «وصله عرض» | `status` open (`''`/missing = open, as the platform) and `offer_count > 0` | green `#2E6B5A` | «آخر عرض منذ …» from `last_offer_at` (`mode:'since'`); missing ⇒ «وصله عرض» with no time | oldest `last_offer_at` first |
| `waiting` | «ينتظر خبيرًا» | open, `offer_count == 0`, and (`open_demand` **or** age ≥ 24h from `created_at`) | amber `#D98A1F`; red `#C8102E` when `stale_unanswered === true` or (`goal_reached_at` and no `linked_course_id`); green when an open-demand card has `linked_course_id` | «منذ …» from `created_at` (open demand: from `goal_reached_at` when reached) | red first, then oldest first |
| `new` | «طلب جديد» | open, `offer_count == 0`, age < 24h | wine `#9E2B4E` | «منذ …» from `created_at` | oldest first |

- Unparsable `created_at` ⇒ the row goes to `waiting` with no timer (never «منذ NaN», never dropped). Unknown `status` value (not open/matched/closed) ⇒ `waiting` with strip label «حالة غير معروفة» and brain line «حالته على المنصة غير معروفة؛ افتحه للتأكد» (nothing disappears silently, as D2).
- Per column on desktop: show 8, then a button «اعرض الباقي ({ar(n)})» that expands that column; `done` shows its 8 and a note «و{ar(doneOlder)} أقدم في «كل الطلبات»» when `doneOlder > 0`.
- Empty column texts: new «لا طلبات جديدة اليوم» · waiting «لا طلب ينتظر خبيرًا» · offered «لا طلبات عليها عروض الآن» · done «لم يُغلق أي طلب هذا الأسبوع».
- Timer refresh: every 60 s while `current` is ours (`setInterval`, cleared when `current` changes); `M._tick(nowMs)` re-renders with a forced clock (for shots).

### 3.4 The ticket (same anatomy as D2, `.v2d-t`)
1. **Strip**: type label + timer.
   - Type label: open demand ⇒ «طلب مفتوح من المنصة»; otherwise lane label «طلب خبرة» / «طلب دورة» / «خدمة للجمهور»; then ` · {catalog_name}` when present. Done tickets: «تمّت المطابقة» or «أُغلق».
2. **Title**: `title` (button, opens the drawer). Empty title ⇒ «طلب بلا عنوان».
3. **Who line**: «{member_name || member_alias}» (person link via `V2D2.link(name, member_email)` when `author_kind !== 'platform'` and email exists) · specialty chip when present · badges: «خاص» (visibility private) · «مخفي عن البورد العام» (hidden) · «تجريبي» (is_test) · «من محادثة بروف» (`source === 'chat'`).
4. **Open-demand progress** (only `open_demand`): a thin bar + «انضم {ar(joined)} من {ar(goal)}» (`goal > 0`), or «انضم {ar(joined)}» (`goal == 0`, no bar).
5. **Brain line** (`.v2d-reason`, prefixed by the brain avatar): from `V2L.v2sMarket.brain(row, now)` (§3.5).
6. **One main button** (`.v2d-btn1`, 48px desktop / 52px mobile) from the same `brain()` result. Done tickets have no button (tap opens the drawer).
7. Inline result/error area under the button (`role=status` / `role=alert`), exactly like D2 (`S.busy/S.err/S.done`).

### 3.5 The brain — `V2L.v2sMarket.brain(row, now)` ⇒ `{line, primary:{label, act}}`
Facts only. Every number comes from a row field. Rules in order, first match wins:

| # | When (fields) | Line (exact) | Main button | `act` |
|---|---|---|---|---|
| B0 | `status` matched | «اختار صاحب الطلب عرضًا {agoText(updated_at)}» (no time ⇒ «اختار صاحب الطلب عرضًا») | none | — |
| B1 | `status` closed | «أُغلق {agoText(updated_at)}» | none | — |
| B2 | `hidden` | «مخفي عن البورد العام{ بسبب: «hidden_reason»}؛ صاحبه ما زال يراه» | «افتح الطلب» | `open` |
| B3 | `open_demand` and `goal_reached_at` and no `linked_course_id` | «اكتمل العدد {agoText(goal_reached_at)}: انضم {ar(joined)} من {ar(goal)}، ولم تُربط دورة بعد» | «اربط دورة» | `link` |
| B4 | `open_demand` and `linked_course_id` | «رُبطت به دورة، والحجز مفتوح لمن انضم ({ar(joined)})» | «افتح الطلب» | `open` |
| B5 | `open_demand` | «طلب مفتوح من المنصة يجمع المنضمّين: {ar(joined)} من {ar(goal)}» (goal 0 ⇒ «…: انضم {ar(joined)}») | «افتح الطلب» | `open` |
| B6 | open, `offer_count == 0`, and `laneOf(need_kind) !== kind` (table below) | «نوعه «{needLabel}» لكنه معروض مع {laneLabelPlural(kind)}» | «انقله إلى {laneLabelPlural(target)}» | `relane` |
| B7 | open, `stale_unanswered === true` | «بلا أي عرض {agoText(created_at)}، لذلك لم يعد يظهر على البورد العام» | «أغلق الطلب» | `close` |
| B8 | open, `offer_count > 0` | «وصله {U(n,['عرض واحد','عرضان','عروض','عرضًا'])}{، آخرها {agoText(last_offer_at)}}. الاختيار لصاحب الطلب» | «اعرض العروض» | `offers` |
| B9 | open, age ≥ 24h, public | «بلا عرض {agoText(created_at)}. يختفي من البورد العام بعد ٧ أيام بلا عرض» | «افتح الطلب» | `open` |
| B10 | open, private (`visibility !== 'public'`) | with `preferred_expert_email`: «طلب خاص موجَّه إلى خبير بعينه، بلا عرض {agoText(created_at)}»; without: «طلب خاص لا يظهر على البورد العام، بلا عرض {agoText(created_at)}» | «افتح الطلب» | `open` |
| B11 | open, age < 24h, public | «وصل {agoText(created_at)}، وهو ظاهر للخبراء على البورد العام» | «افتح الطلب» | `open` |

- `laneOf` mirrors the platform table `_NEED_KIND_LANE` (`marketplace.py` ≈2660) exactly: `course→course_request`, `service→public_service`, `expert|book|other→request`. `training_offer` never suggested. Unknown `need_kind` ⇒ no B6.
- The «٧ أيام» in B9 is the platform constant `STALE_REQUEST_DAYS = 7` (`marketplace.py` ≈131), written into the helper as a named constant with that comment.
- Labels: lane plural «طلبات الخبرة» / «طلبات الدورات» / «خدمات للجمهور»; need label `expert «خبير» · service «خدمة» · course «دورة أو تدريب» · book «كتاب أو معرفة» · training_offer «عرض مدرّب» · other «غير مصنّف»`, unknown ⇒ «غير مصنّف» (never the raw English value; the fixtures' `consult` must read «غير مصنّف»).
- No line starts with «الذكاء الاصطناعي»; no «يقوّم»; numbers always in Arabic digits; gender-neutral («صاحب الطلب»).
- Exposed for the brain section: `V2L.v2sMarket.cards(rows, now)` returns the tickets with B3/B6/B7 (the ones with an action) as `{kind:'market', title, line, primary}` so the brain/home can list them later without re-deriving. Not wired into home in this round (no edit to other sections).

### 3.6 Main-button actions (all through existing endpoints except relane/link)
| `act` | What happens | Endpoint / function |
|---|---|---|
| `open` | opens the drawer (§4) for this row | `EP.marketRequestDetail(id, ok, err)` (existing) |
| `offers` | opens the drawer scrolled to «العروض» | same |
| `close` | confirm sheet §5.1 | `EP.api('/platform-market-requests/<id>/close', {method:'POST', body:{reason}})` — the same route `EP.closeMarketRequest` calls; called via `EP.api` so the sheet can show the platform's answer inline |
| `relane` | confirm sheet §5.4 | new `POST /api/v2/market/requests/<id>/relane` |
| `link` | sheet §5.5 | new `POST /api/v2/market/requests/<id>/link-course` |

After any successful write: `S.done[id]` = result text («أُغلق «{title}»» · «نُقل إلى {lane}» · «رُبطت الدورة»), detail cache for the row dropped, `EP.reload('market', redraw)`; if the «كل الطلبات» tab has a loaded page, it is refetched too.

### 3.7 Layout
- **Desktop ≥ 1180:** 4 columns `repeat(4, minmax(0,1fr))` (`.v2d-cols.cols4`), order right→left: «طلب جديد» · «ينتظر خبيرًا» · «وصله عرض» · «انتهى». Drawer = side panel 440px on the inline end, board stays visible (the board narrows, no overlay on desktop).
- **Tablet 761–1179 (shot at 820):** 2×2 grid of columns; drawer = sheet from the bottom, max-width 720px, 88vh, scrim behind.
- **Mobile ≤ 760 (shot at 390):** the D2 segmented strip `.v2d-seg` of 4 buttons (label + count, min-height 60px), one column at a time; auto-select the first non-empty column until the person picks one. Lane chips scroll horizontally **inside their own strip** (`overflow-x:auto`), never the page. Drawer = full-screen sheet with a sticky header (✕ 44px) and a sticky bottom action bar. Buttons 52px.
- No horizontal page scroll at 390. All targets ≥ 44px.

### 3.8 States
- Loading (`EP.state.market` idle/loading, no data): 4 columns with 2 skeleton tickets each (`.v2s-mk-sk`, animated only without `prefers-reduced-motion`) + header «جارٍ تحميل طلبات السوق…». Never a «٠».
- Failed (`error`): `.v2d-warn` «تعذّر جلب طلبات السوق من المنصة، وليس معناه أنه لا شيء ينتظرك» + «أعد المحاولة» (44px) → `EP.reload('market', redraw)`. Columns not drawn.
- Not available (`missing:true`, platform answered 404): a card with `v2/img/market.jpg` (rounded, 16:9) + «سوق الخدمات غير متاح بعد على المنصة» + «ستظهر الطلبات هنا تلقائيًا حين يصبح متاحًا». No technical words.
- Empty (ready, 0 demand rows): card with `market.jpg` + «لا طلبات في السوق بعد» + «أول طلب يصل من محادثة بروف أو من صفحة السوق على المنصة».

---

## 4) The drawer «تفاصيل الطلب» (`.v2s-mk-dr`)
Opened from a ticket, a row in «كل الطلبات», or `act` open/offers. One drawer at a time; `Esc` and ✕ close it; focus moves into it and back to the opener.

Top (sticky): type label · status chip («مفتوح» / «تمّت المطابقة» / «أُغلق») · timer · ✕ («أغلق التفاصيل», 44px).
Body:
1. `h2` title.
2. Brain line + main button (the same `brain()` result as the ticket; one main button only).
3. «نص الطلب»: `body` (pre-wrap, max 12 lines then «اعرض النص كاملًا»). Empty ⇒ «لم يكتب صاحب الطلب نصًا».
4. Facts grid (2 columns desktop, 1 column mobile; label above value):
   - «صاحب الطلب»: name (person link) + email (`dir=ltr`) + «يظهر على البورد العام باسم: {member_alias}». Platform card: «المنصة».
   - «التخصص»: `specialty` or «لم يُحدَّد».
   - «الميزانية»: `moneyText(budget, currency)`; `budget` 0/empty ⇒ «لم يحدّد صاحب الطلب ميزانية».
   - «الظهور»: «عام على البورد» / «خاص، لا يظهر على البورد العام»; + «مخفي بقرار إشراف{: reason}» when hidden.
   - «وصل في»: `dateText(created_at)` + `agoText`.
   - «المصدر»: «محادثة بروف» when `source==='chat'`; «المنصة» when `author_kind==='platform'`; else «صفحة السوق».
   - «موجَّه إلى» (only when `preferred_expert_email`): the email, `dir=ltr`.
   - Open demand only: «المنضمّون» «{ar(joined)} من {ar(goal)}» · «اكتمل العدد» `dateText(goal_reached_at)` or «لم يكتمل بعد» · «الدورة المرتبطة» `linked_course_slug` resolved to a title from the `courses` loader when loaded, else the slug; none ⇒ «لا دورة مرتبطة».
   - Any field the row does not carry (bridge older than this spec) ⇒ «غير متاح بعد».
5. «العروض ({ar(n)})» — from `EP.marketRequestDetail(id)` → `data.offers` (each `{expert_display, price, currency, eta_days, status, message, created_at, course}`):
   - row: expert name (bold) · price `moneyText(price, currency)` · «خلال {U(eta,['يوم واحد','يومين','أيام','يومًا'])}» when `eta_days > 0` · status «ينتظر قرار صاحب الطلب» (pending) / «مقبول» (accepted, or `id === accepted_offer_id`) / «لم يُختر» (declined) · `agoText(created_at)` · message (pre-wrap) · attached course title when `course`.
   - loading «جارٍ جلب العروض…»; 404 ⇒ «هذا الطلب لم يعد موجودًا على المنصة»; other error ⇒ «تعذّر جلب العروض» + «أعد المحاولة»; none ⇒ «لم يصل أي عرض بعد».
   - ⛔ No accept/decline buttons: only the request owner accepts, on the platform.
6. Secondary actions (bottom bar, `.v2d-btn2`, each 44px desktop / 52px mobile; the main one is not repeated here):
   - «أغلق الطلب» — only when status open (a matched request is refused by the platform with 409, so the button is not shown). → §5.1.
   - «أخفِه عن البورد العام» (not hidden) → §5.2 · «أظهره على البورد العام» (hidden) → §5.3.
   - «انقله إلى …» — only when open, `offer_count == 0`, need/lane mismatch (same rule as B6); label with the target lane. → §5.4.
   - «اربط دورة» / «غيّر الدورة المرتبطة» / «ألغِ ربط الدورة» — only on `open_demand` cards. → §5.5.
   - «اعمل دورة بهذا الطلب» — only when `need_kind === 'course'` or `kind === 'course_request'` → `createCourseModal(title)` (existing, index.html ≈3870).
   - «صفحة صاحب الطلب» — when a member email exists → `V2_HOST.openPerson(member_email)` (D2 person page).

---

## 5) Sheets (all via the D3 sheet pattern: `openModal` + `.v3m` look, busy lock, inline error, no close while busy)

### 5.1 Close
- Title: «إغلاق الطلب».
- Text: «إغلاق «{title}»؟ لن يقبل عروضًا جديدة.» + when `offer_count > 0`: «وصله {U(n,…)} لم يختر صاحب الطلب منها شيئًا.»
- Field: «سبب الإغلاق (اختياري، يُحفظ في السجل)» textarea, ≤300 chars (counter).
- Buttons: «أغلق الطلب» (primary, wine) · «تراجع».
- Call: `POST /api/platform-market-requests/<id>/close {reason}` (existing; server sends `by` from the token and audits `market.close_request`).
- Errors: 409 ⇒ «تمّت مطابقة هذا الطلب، فلا يمكن إغلاقه»; 404 ⇒ «هذا الطلب لم يعد موجودًا على المنصة»; other ⇒ «تعذّر إغلاق الطلب، حاول مرة أخرى». `already:true` ⇒ success text «كان مغلقًا من قبل».

### 5.2 Hide
- Title: «إخفاء عن البورد العام». Text: «يختفي «{title}» من كل بورد عام ولا يقبل عروضًا جديدة، ويبقى ظاهرًا لصاحبه وهنا. يمكنك إظهاره في أي وقت.»
- Field: «السبب (اختياري، يُحفظ في السجل)», ≤300. (The platform stores `hidden_reason` but does not show it to the owner, so the label must not promise that.)
- Buttons: «أخفِه» (primary) · «تراجع». Errors: 404 ⇒ «هذا الطلب لم يعد موجودًا على المنصة»; other ⇒ «تعذّر الإخفاء، حاول مرة أخرى».
- Call: `POST /api/platform-market-requests/<id>/hide {hidden:true, reason}` (existing).
### 5.3 Show again
- No sheet (reversible, harmless): the drawer button goes busy «جارٍ التنفيذ…», then `POST …/hide {hidden:false, reason:''}`; success «رجع الطلب إلى البورد العام».
### 5.4 Move lane (new route)
- Title: «نقل الطلب». Text: «نقل «{title}» من {laneLabelPlural(kind)} إلى {laneLabelPlural(target)}؟ لا يتغير نصه ولا صاحبه، ويمكن إرجاعه.»
- Field: «السبب (اختياري)» ≤300.
- Call: `POST /api/v2/market/requests/<id>/relane {need_kind: row.need_kind, reason, confirmed:true}`.
- Errors: 409 ⇒ «وصله عرض بالفعل، فلا يمكن نقله الآن»; 422 ⇒ «نوع الطلب غير معروف»; 404 ⇒ «هذا الطلب لم يعد موجودًا على المنصة».
### 5.5 Link a course (new route)
- Title: «ربط دورة بالطلب».
- Body: «اكتمل العدد: انضم {ar(joined)} من {ar(goal)}» (or the current numbers), then a list of radio cards (each ≥52px) from the existing `courses` loader (`EP.ensure('courses', …)` → `EP.data.courses.courses`), only rows with `on_platform && platform_slug`: title + trainer (`inst`). Search box when > 8 courses.
- Notice (must be shown, it is a real side effect): «سيصل إشعار داخل المنصة لكل من انضم ({ar(joined)}) بأن الدورة صارت متاحة للحجز.» (bridge `annotate` notifies joiners on the first link).
- Buttons: «اربط الدورة» (disabled until one is chosen) · «تراجع». When linked already: «ألغِ ربط الدورة» as a secondary (sends `course:""`).
- No courses on the platform: «لا دورات منشورة على المنصة بعد» + «اعمل دورة بهذا الطلب» → `createCourseModal(title)`.
- Courses loader failed: «تعذّر جلب الدورات» + «أعد المحاولة» → `EP.reload('courses', …)`.
- Call: `POST /api/v2/market/requests/<id>/link-course {course: platform_slug, confirmed:true}`. Errors: 404 ⇒ «الدورة غير موجودة على المنصة»; 422 ⇒ platform message passed through (Arabic, digits converted).

---

## 6) Tab «كل الطلبات» (`v2s_market_all`) — the full list in the new look

### 6.1 Data — new route `GET /api/v2/market/requests` (§8.1)
Called with `EP.api('/v2/market/requests?' + V2L.v2sMarket.query(S.all))`; `query()` is pure and tested. Response = bridge payload `{items, total, counts:{by_lane, by_need_kind, by_status, by_author_kind}}`; rows go through the same `merge`/label helpers as the board (`items` are bridge rows, so every field is present directly).

### 6.2 Layout
- Search box (`type=search`, 48px, label «ابحث في الطلبات», placeholder «العنوان أو النص أو البريد»), debounce 400 ms, ≤80 chars; `Enter` searches at once.
- Filter row 1 — lane chips: «كل الأنواع» · «طلبات الخبرة» · «طلبات الدورات» · «خدمات للجمهور» · «عروض المدرّبين», each with `(n)` from `counts.by_lane`.
- Filter row 2 — status chips: «كل الحالات» · «مفتوح» · «تمّت المطابقة» · «أُغلق» with `counts.by_status`.
- Filter row 3 — two selects (48px): «نوع الاحتياج» (الكل + need labels with counts from `by_need_kind`) · «كاتب الطلب» («الكل» · «الأعضاء» · «المنصة», counts `by_author_kind`). Checkbox «أظهر التجريبي» (default on — management sees everything, rows carry the badge).
- Result line: «{ar(total)} طلبًا» (U-form) + when filtered «— امسح الفلاتر» (text button).
- **Desktop/tablet table** (`.v2s-mk-tb`, sticky header, zebra on paper): columns «الطلب» (title + lane chip + badges) · «صاحب الطلب» · «العروض» (`ar(offer_count)`; open demand ⇒ «انضم {joined}») · «الحالة» (chip) · «وصل» (`dateText`). Tablet hides «وصل» (shown under the title). Row = button (≥52px) → drawer §4.
- **Mobile list:** cards (title, chips, who, status chip, «منذ …»), each ≥64px, tap → full-screen drawer.
- Paging: 50 per page; «اعرض ٥٠ أخرى» appends (`skip += 50`) while `items.length < total`; line «معروض {a} من {b}».
- Opened with a preset from the board link (lane `training_offer`).

### 6.3 States
Loading: 6 skeleton rows. Failed: `.v2d-warn` «تعذّر جلب الطلبات من المنصة» + «أعد المحاولة». 404 (`bridge_missing`): the §3.8 «غير متاح بعد» card. Empty with filters: «لا طلبات تطابق هذا البحث» + «امسح الفلاتر». Empty without filters: §3.8 empty card.

---

## 7) Tab «ماذا يطلب الناس» (`v2s_market_demand`)

### 7.1 Data
Existing loaders `marketDemand` (`/api/platform-market-demand` → bridge `/api/bridge/market/demand`, 90 days) and `trainingInterests` (`/api/training-interests?limit=200`). Each block has its own state; one failing never blanks the other. View model = pure `V2L.v2sMarket.demand(resp)` (null source ⇒ null, never 0).

### 7.2 Header
- Brain line: from `signals`: «العقل: {U(unanswered_requests, ['طلب مفتوح بلا عرض','طلبان مفتوحان بلا عرض','طلبات مفتوحة بلا عرض','طلبًا مفتوحًا بلا عرض'])} من {ar(total_requests)} خلال آخر {ar(window_days)} يومًا». Any of the three missing ⇒ that part is dropped; all missing ⇒ no brain line.
- Second line when `signals.open_demand_cards` exists: «طلبات المنصة المفتوحة: {ar(cards)}، انضم إليها {ar(joins)}، واكتمل عدد {ar(goal_reached)}» (platform cards are always reported apart from member demand, as the bridge does).
- Button «حدّث الأرقام» (44px) → `EP.reload('marketDemand')` + `EP.reload('trainingInterests')`.

### 7.3 Cards (desktop: 2-column grid; tablet/mobile: one column)
1. **«الطلب حسب النوع»** — `by_need_kind[]`: label (need label map), horizontal bar (width ∝ `count`, wine), number `ar(count)` «مفتوح», then small facts «{ar(zero_offer)} بلا عرض» (amber when > 0) · «{ar(with_offers)} عليها عروض» · «{ar(total)} في المدة». Empty ⇒ «لا احتياجات مسجّلة بعد».
2. **«حسب التخصص»** — aggregate `suggested_courses[].specialty` weighted by `signal_count` (same rule as the old panel); if none ⇒ fall back to `top_topics[] {term,count}` and title becomes «مواضيع تتكرر» (so an inferred word is never presented as a recorded specialty). Top 8, bars in gold `#B0760C` (the market tile colour `176,118,12`). Empty ⇒ «لا تخصصات مسجّلة بعد».
3. **«دورات يطلبها الناس»** — `suggested_courses[]`: title `title_hint` («بلا عنوان» when empty, and then no «اعمل الدورة» button), badge «طلبها شخص صراحة» (`origin==='explicit'`) or «مستنتجة من المحادثات» (`chat_terms`), number «{ar(signal_count)} إشارة», reason line from `sources` («{n} طلب في السوق · {n} اهتمام بالتدريب · {n} اهتمام بدورة · {n} من المحادثات · {n} انضمام لطلبات المنصة», zero parts omitted) or first of `samples`. Button «اعمل الدورة» (`.v2d-btn2`, 44px) → `createCourseModal(title_hint)`. Empty ⇒ «لا طلب متكرر يكفي لاقتراح دورة بعد».
   - Brain line on the card when the top suggestion is explicit: «العقل: أكثر ما طُلب صراحةً «{title_hint}» ({ar(signal_count)} إشارة)». Inferred-only ⇒ no brain line (weak signal is not promoted).

### 7.4 States per block
Loading: skeleton bars. Failed: «تعذّر جلب أرقام الطلب» + «أعد المحاولة». 404: «أرقام الطلب غير متاحة بعد على المنصة».

### 7.5 Block «من طلب التدريب» (training interests)
- Title + count «({ar(rows)})»; when `count > rows` «معروض {a} من {b}».
- Desktop/tablet table: «الاسم» (+ email under it, `dir=ltr`) · «طلب» (`wanted_course` or «لم يحدّد دورة») · «الهاتف» (`tel:` link with `tiTel` sanitising — digits and `+` only — 44px target; none ⇒ «بلا رقم») · «متى» (`when`) · «الحالة» chip: new «جديد» · contacted «تم التواصل» · enrolled «سجّل» · converted «تحوّل إلى متدرّب» · closed «أُغلق»; unknown ⇒ «غير معروفة».
- Mobile: cards with a full-width «اتصل» button (52px) when a phone exists.
- Empty: «لم يسجّل أحد اهتمامًا بالتدريب بعد». Failed/404 as §7.4 with «طلبات التدريب».
- ⛔ Contact data stays behind admin auth (unchanged rule from the old panel); nothing from this block is logged.

---

## 8) Server — `backend/v2_market_routes.py` (`register(app, ns)`)
All three: `@token_required` + `@roles_required('admin')`; first line `closed = ns['_v2_closed']()` (flag off ⇒ 404 and **zero** platform calls); every reply `Cache-Control: no-store` (`_v2_ns`); platform 401/403 ⇒ 502 «تعذّر الاتصال بالمنصة» (`_v2_mask_auth`); platform 404 on the list ⇒ `{"error":"سوق الخدمات غير متاح بعد على المنصة","bridge_missing":true}` 404.

### 8.1 `GET /api/v2/market/requests`
Query in → bridge `GET /api/bridge/market/requests` params out:
- `lane` ∈ `request|course_request|public_service|training_offer|all` (else `all`) → `lane`.
- `status` ∈ `open|matched|closed|all` (else `all`) → `status`.
- `need_kind` ∈ `expert|service|course|book|training_offer|other` → `need_kind` (else omitted).
- `author_kind` ∈ `member|platform|all` (else `all`) → `author_kind`.
- `q`: stripped, ≤80 chars, omitted when empty → `q`.
- `include_test`: `'0'|'false'` ⇒ `false`, else `true` → `include_test`.
- `limit`: int 1..100, default 50 → `limit`; `skip`: int 0..100000, default 0 → `skip`.
- Response passed through unchanged (`_v2_get` semantics).
### 8.2 `POST /api/v2/market/requests/<id>/relane`
- `V2_ID_RE` on `id` (else 404 «هذا الطلب غير موجود»); `confirmed` must be exactly `true` (`_v2_confirmed`, else 400 «لازم تأكّد الأول من الشاشة»).
- `need_kind` ∈ `expert|service|course|book|other` (⛔ `training_offer` refused: demand never moves into the supply lane) else 400 «نوع الطلب غير معروف».
- `reason` → `_ef_note(reason, 300)`.
- `_v2_write('POST', '/api/bridge/market/requests/<id>/relane', {need_kind, reason}, 'market.relane', id, {'need_kind': need_kind})` — `by` from the token, audit on success only, lost reply ⇒ «ما وصلناش رد» path, 404/409/422 pass through.
### 8.3 `POST /api/v2/market/requests/<id>/link-course`
- Same id/confirm checks. `course`: string, stripped, ≤200, may be `""` (unlink); non-string ⇒ 400 «اختر دورة».
- `_v2_write('POST', '/api/bridge/market/requests/<id>/annotate', {linked_course_id: course}, 'market.link_course', id, {'course': course})`.
- ⛔ Only `linked_course_id` is ever sent (no `evidence_note`, `join_goal`, `specialty` from this route — whitelist).

Existing routes reused unchanged: `GET /api/platform-market-requests` (+ `/<id>`), `POST …/<id>/close`, `POST …/<id>/hide`, `GET /api/platform-market-demand`, `GET /api/training-interests`, `GET /api/courses` (loader `courses`).

---

## 9) Visual rules (`v2s/market.css`)
- Tokens on `.v2s-mk`: `--wine:#9E2B4E; --paper:#FBFAF7; --paper2:#F6F1EA; --ink:#21262E; --red:#C8102E` (late/stale only); gold `#B0760C` only for the demand bars. Cairo for headings/numbers, IBM Plex Sans Arabic for text (already loaded by the shell).
- Ticket, column, segmented strip, warn strip, brain pill: reuse `.v2d-*` classes from `v2-d2.css` so tickets look identical to the files board. New classes only for: drawer `.v2s-mk-dr`, chips `.v2s-mk-chip`, table `.v2s-mk-tb`, demand bars `.v2s-mk-bar`, skeleton `.v2s-mk-sk`, empty card `.v2s-mk-empty`, progress `.v2s-mk-prog`.
- ⛔ No old classes inside `#view` for this section: `.kpis`, `.inboxwrap`, `.policy`, `.tabbar`, `.panel`, `.row.esc-row`, `.drawer#drawer`, old `.chip`.
- Breakpoints: 1180 / 760 (same as D2). Focus ring `3px solid rgba(158,43,78,.45)`. `prefers-reduced-motion` disables skeleton shimmer and drawer slide.

---

## 10) Tests — `backend/tests/test_v2s_market.py`
Run: `cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_market.py`. Fake platform only (`https://platform.test`); any other host fails the test.

**pytest — routes**
1. Each of the 3 routes: non-admin roles (`employee, trainer, investor, viewer, pending`) ⇒ 403; flag off ⇒ 404 with zero platform calls; `Cache-Control: no-store`.
2. List: exact outbound params for a full query; invalid `lane/status/author_kind` ⇒ `all`; invalid `need_kind` dropped; `q` trimmed to 80; `limit` clamped 1..100 (0 ⇒ 1, 999 ⇒ 100, junk ⇒ 50); `skip` clamped; `include_test=false` forwarded as false; platform 404 ⇒ 404 `bridge_missing:true`; platform 401/403 ⇒ 502; platform 500 passes through as an error (no invented body).
3. Relane: `confirmed` missing / `"true"` / `1` ⇒ 400 and no platform call; `need_kind=training_offer` ⇒ 400; bad id ⇒ 404; `by` comes from the token even if the body sends `by`; audit row `market.relane` only on 2xx; platform 409 detail passes through; lost reply ⇒ «ما وصلناش رد».
4. Link-course: same confirm/id checks; `course` non-string ⇒ 400; `""` forwarded (unlink); only `linked_course_id` + `by` reach the platform; audit `market.link_course` only on success; platform 404 passes through.
5. Wiring: `app.py` contains the marker exactly once and exactly one `v2_market_routes` registration line directly above it; `register` reads `_platform_proxy` lazily (monkeypatching `app._platform_proxy` after import is honoured).

**node (via `uiharness/v2_node.logic`) — pure helpers**
6. `tickets()`: a fixture row per rule lands in the expected column; `training_offer` excluded; `is_test` excluded unless `showTest` and counted in `testCount`; hidden rows kept; unknown status ⇒ `waiting` with «حالة غير معروفة»; bad `created_at` ⇒ `waiting`, no timer; `done` window 7 days and `doneOlder`; sort orders; lane filter.
7. Invariant: non-hidden, non-test tickets in `new` + `waiting` == the tile formula (`status open && !hidden && !is_test && kind!=='training_offer' && !offer_count`) on a mixed fixture of ≥20 rows.
8. Timer texts at a fixed `now` for each column; `offered` without `last_offer_at` ⇒ no time text.
9. `brain()`: each rule B0–B11 returns the exact Arabic line and button; B6 uses the platform lane table; unknown need ⇒ «غير مصنّف» and no B6; goal 0 ⇒ no «من ٠»; no output contains Latin digits, `null`, `undefined`, `NaN`, «يقوّم», or starts with «الذكاء الاصطناعي».
10. `merge()`: enrich by `id`, absent fields stay `undefined`.
11. `query()`: exact query strings for default, full, and preset (`training_offer`) states.
12. `demand()`: need labels Arabic; missing `signals` parts dropped; failed source ⇒ `null`; specialty aggregation and the «مواضيع تتكرر» fallback flag; origin labels; zero parts omitted from the sources line.

**files**
13. `SECTIONS.market` has the three tabs; `sectionFor('market')` ⇒ `('market','requests')`; `#s/market/all` and `#s/market/demand` round-trip.
14. `index.html`: the `v2 sections` block contains the two `v2s/market.*` lines; the generic `V2SEC` hook exists once in `renderView`; with the flag off `viewMarket` still renders (old screen untouched, byte-identical function body).
15. `v2s/market.js` and `v2s/market.css` exist on disk and are served: `dashboard-cloud/Dockerfile` does `COPY . /usr/share/nginx/html` and nginx serves any `.js/.css` path, so no Dockerfile/nginx edit is needed (the test asserts both files exist and the `COPY .` line is unchanged).

Also rerun: `test_v2_d1b.py` (with the updated line 87), `test_v2_d1.py`, `test_v2_d2.py`, `test_v2_d3.py`, file by file.

---

## 11) Shots — `backend/tests/uiharness/v2_shots_market.py`
`cd backend && python3 -B tests/uiharness/v2_shots_market.py ../docs/v2/final/shots-market` · imports helpers from `v2_shots.py` (`open_shell`, `go_section`, `check`, `d2_check`-style checks), never edits it. Fixtures in new `market_fixtures.py` (subclass of `v2_fixtures.V2Platform` adding `/api/bridge/market/requests/{id}` with offers, `close`, `hide`, `relane`, `annotate`, `/api/bridge/market/demand`, `/api/bridge/training-interests`, and paged/filtered list with `counts`). Fixture rows cover every column and every brain rule B0–B11, an open-demand card at goal, one linked, one gathering, a stale public request, a private request to a named expert, a need/lane mismatch, a hidden row, a test row, a matched and a closed row, and 2 training offers.

Each at desktop 1440×900 (`d`), tablet 820×1180 (`t`), mobile 390×844 (`m`):
1. `board-full` — all four columns filled, header brain line + totals + lane chips.
2. `board-col-{new,waiting,offered,done}` — mobile only, one per segment.
3. `board-lane-course` — lane chip «طلبات الدورات».
4. `drawer-offers` — ticket with 3 offers opened (desktop side panel, tablet/mobile sheet).
5. `drawer-open-demand` — goal reached, no course.
6. `sheet-close`, `sheet-hide`, `sheet-relane`, `sheet-link` (with courses), `sheet-link-none` (no platform courses).
7. `after-close` — the closed ticket now in «انتهى» with «أُغلق «…»».
8. `error-409` — close refused on a matched row (fixture forces 409), inline error.
9. `board-loading` (held request), `board-failed` (500), `board-missing` (404), `board-empty`.
10. `all-default`, `all-filtered` (course lane + open), `all-search-none`, `all-paged` (after «اعرض ٥٠ أخرى»), `all-supply` (opened from the board link).
11. `demand-full`, `demand-failed`, `demand-training-empty`.
12. `old-link` — `#market` lands on `#s/market/requests`; asserts the home tile badge number == the board header number.
13. `flag-off` — old `viewMarket` renders exactly as before.

The script fails on: horizontal scroll at any width; any target < 44px (buttons < 52px on mobile); visible `undefined/NaN/null/[object Object]`; visible Latin technical words (`bridge`, `api`, `need_kind`, `lane`, `/api/`, `api.elprofessor.net`); any old class (§9) inside `#view`; a «٠» where the fixture source failed; a write to `/api/v2/market/*` without `confirmed:true`; any request leaving the in-process fake (except Google Fonts).

---

## 12) Platform needs (nothing in this spec depends on them; each one only adds a brain fact later)
All additions are new **keys on existing bridge rows** of `GET /api/bridge/market/requests` and `GET /api/bridge/market/requests/{id}` (`marketplace.py` `_bridge_row`). Until a key exists the dashboard treats it as absent («غير متاح بعد» / no line), never 0.

1. **Who was told about a public request** (market plan 2026-10-26 §2, approved, not built — `_fanout_invite_experts` today only covers invitations):
   `"notified_experts": int | null` (null = feature not built), `"notified_at": "ISO" | ""`.
   Brain line it unlocks: «بُلِّغ {n} خبير في تخصصه {منذ …}، ولم يصل عرض».
2. **Approved experts matching the specialty** (so «ينتظر خبيرًا» can say whether anyone could answer):
   `"matching_experts": int | null` — count of approved, non-suspended experts whose specialty matches the request (same matcher as §2 of the market plan).
   Brain line: «لا خبير معتمد في تخصص «{specialty}» بعد» → main button «ادعُ خبيرًا» (to the invites section).
3. **Lowest offer on the list row** (avoid one detail call per ticket):
   `"offer_min": {"amount": number, "currency": "EGP"} | null`.
   Brain line B8 becomes «وصله ٣ عروض، أقلها ٤٠٠ جنيه…».
4. **Close/hide trail on the row** (the platform stores them but `_serialize_request` drops them):
   `"closed_at": "ISO"|"", "closed_by": str, "closed_reason": str, "hidden_at": "ISO"|"", "hidden_by": str`.
   Lets B1 read «أُغلق {منذ …} بسبب: «…»».
5. ⚠️ **Rule conflict to fix on the platform (not a dashboard change):** accepting a market offer creates an old-style consultation at `consultations.py PLATFORM_FEE_RATE = 0.20`, below the 35% floor (`SHARES-2026-10-30.md`, «Old marketplace consultations — being removed»). The dashboard shows no share or money number for market requests and adds no money action; the platform round that removes old consultations must decide what an accepted market offer becomes (a fixed-price «ملف» at ≥35%).

---

## 13) Out of scope
- Accepting/declining offers (owner-only, on the platform).
- Seeding open-demand cards (`/bridge/market/seed`), `evidence_note`, `join_goal`, `specialty` annotate fields.
- Feeding market cards into the home «ابدأ القرارات» queue (exposed as `V2L.v2sMarket.cards()` for the brain/home owners).
- The «تحليل الطلب» screen of «التقارير» (another section); «ماذا يطلب الناس» here is the market's own demand view.
- Restyling `createCourseModal` (owned by the courses section); after merge, if «الدورات» exposes a new create flow, the two «اعمل الدورة» calls switch to it in one line.
