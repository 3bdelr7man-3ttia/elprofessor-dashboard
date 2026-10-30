# SPEC — «الكتب» (the rest of the section): rebuild «الكتب والأعمال»

**Round:** the final dashboard round («الداشبورد يخلص نهائيًا», founder order 2026-10-30).
**Worktree / branch:** `elprofessor-dashboard-v2/.worktrees/books` · `final-books` (from `dash-v2-d3@7d1aa83`). Merged later into `dash-final`.
**Section key:** `books`. **Stage of this document:** plan, **revision 2** (after the expert review; what changed and what was rejected is in §13). The build stage implements it as written. No question is left open for the builder; every decision is made below and the founder-facing ones are listed in §11.

**What D3 already built (do not touch):** the tabs «مراجعة العروض» (`v2b_offers`) and «طلبات القرّاء» (`v2b_requests`) in `v2-d3.js/.css`, the proxies `/api/v2/book-offers*`, `/api/v2/book-requests*`, `/api/v2/prices/*`, `/api/v2/ads-ledger*` in `backend/app.py`, and «الفلوس › الأسعار».

**What this round rebuilds:** the last old tab «الكتب والأعمال» (old module `knowledge`, `index.html:3624-3699 viewKnowledge`, `addBookModal`, `knowledgeEditModal`). After this round, nothing in the «الكتب» section has the old look, and **nothing stays as «كل السجلات»** (§9).

---

## 0. Rules this section obeys (binding)

- Plain standard Arabic, gender-neutral («صاحب العمل»), no technical words in visible copy, never «يقوّم», no headline that starts with AI, international audience. Arabic digits everywhere (`L.util.ar`), except inside a pasted link.
- Facts only. A source that failed shows «غير متاح بعد», never 0. A real zero from a source that answered is written as a sentence («لم تُبع منه نسخة بعد»), never as a bare «٠».
- The brain suggests; the founder decides with **one main button**. Every brain line in §6 names its exact factual basis. No line when its basis is missing.
- **Prices of store books are edited only in «الفلوس › الأسعار».** This screen shows them and links there. The one documented exception (old market works whose prices are not in the unified price list) is §11 D-1, with its platform need P3.
- Books are never refunded. Nothing on this screen moves money.
- No new roles, no new decision path: every write button calls an endpoint that already exists today (§5). The two new server routes are read-only (§7).
- Brand: wine `#9E2B4E`, paper `#FBFAF7`, ink `#21262E`. Targets ≥ 44px, buttons 52px at ≤ 760px. No horizontal page scroll at 390px. The only photo on the tab is `dashboard-cloud/v2/img/books.jpg` on the brain card (no new image generation). **No covers of any kind** (no typographic fake cover, no work image; the only `<img>` tags are `books.jpg` and the brain avatar; the dashboard CSP is `img-src 'self' data:`, so a platform cover URL cannot load and we never try).
- Platform share never below 35%. This screen sets no share; where a work still sells under the old split, the screen states it as a fact (§5.2, B7) and P3 removes it.
- Zero real network calls in tests and shots. No push, no deploy.

---

## 1. Files (parallel-safe layout)

| File | New/edit | Content |
|---|---|---|
| `dashboard-cloud/v2s/books.js` | **new** | Rendering, sources, sheets for the tab. Registers module `knowledge` in the shared registry `window.V2SX` (§1.1). |
| `dashboard-cloud/v2s/books.css` | **new** | Styles under `.v2s-books` (page) and `.v2s-bm` (inside a sheet). Reuses D3 tokens/classes (`.v3`, `.v3-card`, `.v3-btn1/2`, `.v3-empty`, `.v3-warn`, `.v3-ok`, `.v3-brain`, `.v3-vis`, `.v3-person`, `.v3-err`), adds `bk-*` classes only. |
| `dashboard-cloud/v2-logic.js` | edit (own parts only) | (a) the `books` entry in `SECTIONS`: only `desc` changes (§2). (b) pure helpers appended at the very end of the file inside `// ===== v2s:books =====` … `// ===== /v2s:books =====` (§8). |
| `backend/v2_books_routes.py` | **new** | `register(app, g)` with two read-only routes (§7). |
| `backend/app.py` | edit (1 line + marker) | One registration line right before `# ---- v2 section routes end` (§7.1). |
| `dashboard-cloud/index.html` | edit (block + hook) | Two lines inside the `<!-- v2 sections begin -->` block; one dispatch line in `renderView` (§1.1). |
| `backend/tests/test_v2s_books.py` | **new** | pytest + node tests (§10.1). |
| `backend/tests/uiharness/v2s_books_fixtures.py` | **new** | In-memory platform for this section (extends `d3_fixtures.D3Platform`). |
| `backend/tests/uiharness/v2_shots_books.py` | **new** | Shots (§10.2), imports helpers from `v2_shots.py` (no edit there). |
| `docs/v2/final/shots-books/` | **new** | Shots output. |
| `docs/v2/final/STATUS-books.md` | **new** | Build report (what was done, sources found/missing, deviations), with a section «قرارات تحتاج المؤسس» that lists at least D-1 and D-8 (old split of market works), and a note that «مكتبة المراجع» moves to «العقل» (D-9). |

### 1.1 Dispatch: the shared section registry (shared edit, kept minimal)

The shell renders a module through `renderView()` (`index.html:702-711`). D2 and D3 each have a hard-coded hook. Eleven sections cannot each add their own hook without colliding, so this section uses **one generic registry** that any `v2s/<key>.js` can join. ⛔ The name `V2S` is taken (`index.html:7662`, the current section state), so the registry is `window.V2SX`.

In `v2s/books.js` (top, idempotent, safe in any load order):
```js
var R = window.V2SX = window.V2SX || { mods: {}, owns: function (m) { var e = this.mods[m]; return !!(e && e.owns()); }, render: function (m, v) { return this.mods[m].render(v); } };
R.mods.knowledge = { owns: function () { return !!(window.V2SHELL && V2SHELL.on); }, render: drawWorks, summary: summary, library: openLibrarySheet };
```
`summary()` is §6.3. `library()` opens the «مكتبة المراجع» sheet (§5.7) from anywhere, so the «العقل» section (D7), which is the final home of that job, can open the same sheet without copying it.

In `index.html` `renderView()`, exactly one new line, placed **directly after** the D3 line (`if(window.V2_ON&&window.V2D3&&V2D3.owns(current))return V2D3.render(current,v);`), byte-for-byte:
```js
  if(window.V2_ON&&window.V2SX&&V2SX.owns(current)){const ap2=document.querySelector('.app');if(ap2)ap2.classList.add('v2-bare');return V2SX.render(current,v);}
```
If the merged base already has this exact line (another section added it), do not add a second one. It adds `v2-bare` itself, so line 706 is not touched.

**Why the module stays `knowledge`:** the tab keeps `T('books', 'الكتب والأعمال', 'knowledge')`. Under the shell (`V2SHELL.on`, admin only) the registry owns `knowledge`, so every old door lands on the new screen with no alias change: `#knowledge`, `go('knowledge')`, the home tile `dest:'knowledge'` (`v2-logic.js:251`), inbox rows `dest:"knowledge"` (`dashboard-api.js:1946`). With the flag off, or for non-admin roles, `owns()` is false and the old `viewKnowledge` renders exactly as today. Existing tests that pin this tab (`test_v2_d1b.py:89,117,214`, `test_v2_d3.py:916,926`, `test_v2_d1.py:504`, `v2_shots.py:1194`) keep passing unchanged.

Script/link tags, inside the block `<!-- v2 sections begin -->` … `<!-- v2 sections end -->` (create the block right after `<script src="v2-d2.js"></script>` if missing; one line per file, alphabetical by key):
```html
<link rel="stylesheet" href="v2s/books.css">
<script src="v2s/books.js"></script>
```
⚠️ The block sits **before** `v2-d3.js`. `books.js` does not use `window.V2D3` at all: everything it calls is its own code, `window.V2L`, `window.EP`, `window.V2_HOST`, `window.openModal`/`closeModal` (all defined before the block or at call time).

---

## 2. Tabs of the section (the `SECTIONS` entry)

```js
{ key: 'books', label: 'الكتب', img: 'books', desc: 'كل كتاب وعمل، وعروض تنتظر المراجعة، وطلبات القرّاء', tabs: [
  T('offers', 'مراجعة العروض', 'v2b_offers'),
  T('requests', 'طلبات القرّاء', 'v2b_requests'),
  T('books', 'الكتب والأعمال', 'knowledge')
] },
```
Only `desc` changes (old: «عروض الكتب بانتظار المراجعة وطلبات القرّاء والمتجر»). Tab keys, labels, modules and order are unchanged (tests pin them). No hidden tab. No «كل السجلات» tab.

---

## 3. Data sources (each loads and fails on its own)

`books.js` keeps a `SRC` map like `v2-d3.js:46-74` (`state: idle|loading|ready|error|closed`, `seq`, `data`). `closed` = the endpoint answered 404 (store flag off, or a platform bridge not built yet). Every source is loaded with `EP.api(path)`; a 401 is left to `EP` (session expired); anything else sets `error`/`closed`. **No source is ever turned into an empty list.** (The old `EP` loader `knowledge` turns a failure into `[]`, `dashboard-api.js:2350`; this screen does not use it.)

| Key | Request (dashboard) | Platform | Used for | When |
|---|---|---|---|---|
| `knowledge` | `GET /api/platform-knowledge` (exists, `app.py:4192`) | `GET /api/bridge/knowledge` | market works (old shelf): `id, slug, title, type, owner_email, owner_name, rights, is_active, bid_enabled, price_amount, price_currency, total_acquired` (+ `status, created_at, has_file, review_note, legacy_split, owner_pct, platform_pct` once P1 lands) | tab open |
| `revPending` | `GET /api/v2/books/review?status=pending_review` (**new**, §7) | `GET /api/bridge/knowledge/review` | status «في المراجعة», `has_file`, `created_at` | only if `knowledge` items have no `status` field |
| `revRejected` | `GET /api/v2/books/review?status=rejected` (**new**) | same | status «مرفوض», `review_note` | same condition |
| `prices` | `GET /api/v2/prices/book` (D3) | `GET /api/bridge/prices/book` | store books: `id`(=slug), `title`, `visible`, `has_prices`, `min_price` (via `L.v2Prices`) | tab open |
| `offers` | `GET /api/v2/book-offers?status=all` (D3, `all` is allowed) | `GET /api/bridge/book-offers` | (a) the **count** of offers `in_review` for the link line in the review lane (§4.2), never rows; (b) offers `rejected` as rows of the «مرفوض» lane (they have no other home); (c) owner/type/agreement/`catalog_id` of live books (fallback when `store` is closed) | tab open |
| `store` | `GET /api/v2/books/store` (**new**, §7) | `GET /api/bridge/books/works` (**P2, not built yet**) | store books: owner, source (ours/member), type, plan, sales count, `catalog_id` | tab open |
| `ads` | `GET /api/v2/ads-ledger` (D3) | `GET /api/bridge/ads-ledger` | ad balance of one store book (`owner_id == catalog_id`) via `L.v2AdsLedger` | lazily, when a store-book work page opens |

Reload rules: opening the tab loads every source in state `idle`, and reloads any source older than 60 s. After a write, reload only the source the write changed (§5). A redraw happens on every source change (same `changed()`/`redraw()` pattern as D3, with the sheet-busy guard). A once-a-minute redraw keeps «منذ …» texts fresh while the tab is open (`setInterval`, cleared when `owns()` is false for the current module).

Store flag: when `prices` is `closed`, the store is not open yet. Store rows are absent and the list shows the note in §4.6. When `prices` is ready but `store` is `closed`, the platform bridge P2 is not there yet: owner falls back to the offer join and sales show «غير متاح بعد».

---

## 4. Screen 1 — the list «الكتب والأعمال» (lanes, like the approved board POS-Tickets)

Root: `<div class="v3 v2s-books" data-board="works">`. The shell already draws the section title, description and tab bar above `#view`.

The screen is a kitchen display: work that waits for a decision comes first, in lanes with a counter, and each waiting item carries its brain line and its decision buttons **on the item itself** (same as D3 `offerCard`: one tap to the sheet, one tap to confirm). Work that waits for nothing comes after, as compact rows. There are **no filter chips** (the lanes are the filter) and **no persisted filter** (nothing in `localStorage`).

### 4.1 Order of blocks (top → bottom)

1. **Note strip** (after a write): `.v3-ok` with the result text (§5), auto-hides after 12 s.
2. **Failed-sources strip** (`.v3-warn`): «تعذّر جلب: {labels} — ما يظهر ناقص، وليس معناه أنه لا شيء». Labels: `knowledge` «أعمال السوق», `revPending`/`revRejected` «حالة المراجعة», `prices` «كتب المتجر», `offers` «عروض الكتب», `store` is **not** listed here when `closed` (that is «not built yet», shown in-place as «غير متاح بعد»); `store` in `error` is listed as «بيانات المتجر».
3. **Brain card** (`.bk-brain`, photo `v2/img/books.jpg` as a side image on desktop/tablet, hidden at ≤ 760px): avatar `v2/img/brain-avatar.jpg` + **one** summary line + at most **one** button that scrolls to the first lane with items (§6.1). Nothing else on the card.
4. **Search** (only when the total number of rows across all lanes is > 12): one `<input type="search">` full width of the content column, placeholder «ابحث بالعنوان أو باسم صاحب العمل», `aria-label="ابحث في الأعمال"`, `min-height:48px` (52px at ≤ 760px), `font-size:16px` (no zoom on iPhone). Client-side, normalised by `L.v2kKey` (§8): hamza forms → «ا», «ة» → «ه», «ى» → «ي», diacritics removed, Arabic/Latin digits equal. It filters every lane at once; a lane with no match is not drawn; no match anywhere ⇒ `.v3-none` «لا أعمال بهذا الوصف» + `.v3-link` «امسح البحث». The text lives in memory only (`S.q`), for the session.
5. **Lanes** (§4.2), in this fixed order, each drawn only when it has items: «ينتظر مراجعتك» · «بلا سعر» · «مخفي وبيعت منه نسخ» · «ظاهر للناس» · «مخفي» · «لم تصل حالتها» · «مرفوض» (collapsed).
6. **«أضف كتابًا»**: one `.v3-btn2`, at the very end of the lanes (not in the toolbar; there is no toolbar). Opens §5.6.
7. **«مكتبة المراجع» link row** (last thing on the page): one muted line `<p class="bk-libline">مكتبة المراجع: ملفات تقرأ منها إجابات المنصة · <button class="v3-link" data-a="library">استورد ملفات</button></p>` (the button ≥ 44px, 52px at ≤ 760px). Opens §5.7. No card, no title.

### 4.2 Lanes

Each lane: `<section class="bk-lane" data-lane="<key>" id="bk-lane-<key>">` with header `<h2 class="v3-h2">{title} <span class="v3-cnt">{ar(n)}</span></h2>` (`tabindex="-1"` so the brain button can focus it). A count that may be partial (a status source failed) is shown as «{ar(n)}+» with `title="العدد ناقص لأن بعض المصادر لم تصل"`.

| Order | Key | Title | Rows (status from §4.3) | Container | Item variant | Sort |
|---|---|---|---|---|---|---|
| 1 | `review` | «ينتظر مراجعتك» | market works `review` | `.bk-tgrid` (3 cols ≥ 1180, 2 cols 761–1179, 1 col ≤ 760) | decision | oldest first (`created_at`), unknown time last, then title |
| 2 | `noprice` | «بلا سعر» | store books `noprice` | `.bk-tgrid` | decision | title |
| 3 | `hiddenSold` | «مخفي وبيعت منه نسخ» | market works `hidden`, for sale, `sold > 0` (B5) | `.bk-tgrid` | decision | most sold first, then title |
| 4 | `live` | «ظاهر للناس» | market works `live` + store books `live` | `.bk-list` (one column) | compact | most sold first; unknown sales after known; then title |
| 5 | `hidden` | «مخفي» | every other `hidden` row (market without sales, store books with prices but hidden) | `.bk-list` | compact | title |
| 6 | `unknown` | «لم تصل حالتها» | market works `unknown` | `.bk-list` | compact | title |
| 7 | `rejected` | «مرفوض» | market works `rejected` + offers `rejected` | `.bk-list`, **collapsed by default** | compact | most recent first (`updated_at`/`decided_at`), then title |

Ties by title use `localeCompare('ar')`. Row identity: `kn:<id>`, `st:<slug>`, `of:<offer id>`.

**Review lane link to offers.** When the `offers` source is ready and has `n > 0` offers `in_review`, the review lane header gets one line under it: `<a class="v3-lnk" data-a="offers">و{U(n, ['عرض واحد','عرضان','عروض','عرضًا'])} في «مراجعة العروض»</a>` → `V2_HOST.openSection('books','offers')`. Offers in review are **never rows on this tab** (they have one home: the D3 tab that owns their decision). When the review lane has no market works but `n > 0`, the lane is still drawn: header «ينتظر مراجعتك» **without** a counter, the line `.v3-none` «لا أعمال من السوق تنتظر مراجعتك» and the link line. When `offers` failed, no link line (it is listed in the failed strip).

**Rejected lane, collapsed.** The header is a `<button class="bk-fold" aria-expanded="false" aria-controls="bk-lane-rejected-body">` holding the title and counter plus «اعرض»/«أخفِ» text, ≥ 44px (52px at ≤ 760px). Not `<details>` (old-look marker). The open/closed state lives in memory only and starts closed every time the tab opens.

**Every lane empty** (all sources ready, zero rows): no lanes, no search, one `.v3-empty` «لا أعمال بعد» + «يظهر هنا كل كتاب أو عمل يُضاف إلى المنصة.» + «أضف كتابًا» (`.v3-btn1`); the bottom «أضف كتابًا» (§4.1 item 6) is then not drawn a second time; the library line stays.

### 4.3 One item component (`<article class="bk-item">`), same markup at every width

```
┌───────────────────────────────────────────────┐
│ [type pill «كتاب»] [status pill]   since/time   │   strip (decision variant only: coloured strip like .v3-t)
│ title (h3, 2 lines max)                         │
│ صاحب العمل: <person link> · sales text          │
│ (brain line, decision variant only)             │
│ [ main action ] [ secondary ] [ التفاصيل ]      │   decision variant
│                                    [ افتح ]     │   compact variant (one button at the end)
└───────────────────────────────────────────────┘
```
- **Type pill:** `typeText` from the source type («كتاب»، «دليل»، «بحث»، «عمل»؛ unknown type ⇒ «عمل»). For a store book the pill also says «من المتجر» (e.g. «كتاب من المتجر»); market works say nothing more. No separate «source tag».
- **Title:** `h3`, from the source (`title`; empty ⇒ «عمل بلا عنوان»).
- **Owner:** «صاحب العمل: » + person link (same markup as D3 `personLink`: `<a class="v3-person" href="#s/people/person/<email>" data-person="<email>">name</a>`, click → `V2_HOST.openPerson(email)`). Name only (no link) when the email is empty or invalid. «صاحب العمل: غير متاح بعد» when no source gives the owner (§3).
- **Status pill** (`.v3-vis` + modifier): «في المراجعة» (amber), «ظاهر للناس» (green `.on`), «مخفي» (grey `.off`), «بلا سعر» (amber), «مرفوض» (red), «الحالة: غير متاح بعد» (grey).
- **Sales text:** §4.5 (offer rows have none).
- **Price** is **not** on the item (it lives on the work page and in «الفلوس › الأسعار»); exception: a rejected offer shows «السعر المقترح: …» when it had one.
- **Decision variant** (lanes 1–3): strip on top (`tone-wait` amber for review/noprice, `tone-late` red when the B1 line applies) with the type pill and, for review, «منذ {agoText}» (`<time>`); the brain line (`.v3-brain`, §6.2, one line); then the actions row `.v3-acts`:
  - review: main `.v3-btn1` «اعتمد وانشر» + `.v3-btn2` «ارفض» (B1 case: main «ارفض» with the prefilled reason, secondary «اعتمد وانشر»); both open the same sheets as §5.5.
  - noprice: main «ضع سعرًا» → `V2_HOST.openSection('money','prices')`.
  - hiddenSold: main «أظهر للناس» → show confirm sheet (§5.5).
  - plus, in every decision item, `.v3-link` «التفاصيل» → work page (§5).
- **Compact variant** (lanes 4–7): no strip, no brain line (the page shows it), one `.v3-btn2` «افتح» at the inline-end → work page.
- Layout: ≥ 761px the item is a grid `minmax(0,1fr) auto` in compact rows (text start, button end) and a card in the decision grid; ≤ 760px the action buttons go full width under the text (each 52px). The action button is the target at every width; the item itself is not a button or a link.

### 4.4 Statuses (one map for all sources; computed by `L.v2kWorks`)

| Row source | Condition | Status key | Pill |
|---|---|---|---|
| market work (`knowledge`) | `status==='pending_review'` (P1 field, else id in `revPending`) | `review` | «في المراجعة» |
| market work | `status==='rejected'` (or id in `revRejected`) | `rejected` | «مرفوض» |
| market work | published (status `published`/missing in P1; or both review sources ready and id in neither) and `is_active` | `live` | «ظاهر للناس» |
| market work | published and `!is_active` | `hidden` | «مخفي» |
| market work | no P1 field and a review source failed and id not found in the ready one | `unknown` | «الحالة: غير متاح بعد» |
| store book (`prices` row) | `has_prices===false` | `noprice` | «بلا سعر» |
| store book | `has_prices && visible` | `live` | «ظاهر للناس» |
| store book | `has_prices && !visible` | `hidden` | «مخفي» |
| offer (`offers`) | `status==='rejected'` | `rejected` | «مرفوض» |
| offer | `in_review` | — not a row; counted for the review-lane link only (§4.2) | |
| offer | `draft` | — not listed (the owner has not sent it) | |
| offer | `live` | — not a row; it is the store book with `slug === catalog_slug` (used only for owner/type/agreement/`catalog_id`) | |

### 4.5 Sales text (facts only)

| Case | Text |
|---|---|
| market work for sale, `total_acquired` is a number | n > 0: «بيعت منه {U(n)}» with `U(n, ['نسخة واحدة','نسختان','نسخ','نسخة'])`; n = 0: «لم تُبع منه نسخة بعد» |
| market work free (`public_domain_feed`) | n > 0: «{U(n)} مجانية» with `U(n, ['نسخة واحدة','نسختان','نسخ','نسخة'])`; n = 0: «لم يأخذه أحد بعد» |
| store book, `store` ready, slug present | `paid_owners` > 0: «بيعت منه {U(paid_owners)}»; 0: «لم تُبع منه نسخة بعد». On the **work page only**, when `by_version` is present and `paid_owners > 0`, a second muted line: «منها {U(read, ['نسخة واحدة','نسختان','نسخ','نسخة'])} للقراءة على المنصة و{U(pdf, …)} للتحميل» (a part that is 0 is written «ولا نسخة للتحميل» / «ولا نسخة للقراءة على المنصة»). No «PDF» and no bare digit in visible copy. |
| store book, `store` closed/error, or slug absent from it | «المبيعات: غير متاح بعد» |
| offer row | no sales text |

`total_acquired` already counts paid copies minus reversals for a work for sale (`payments.py:1525,1835`) and free copies for a free work (`knowledge.py:716`); that is why the two wordings differ.

### 4.6 States of the list

- **Loading (nothing ready yet):** `.v3-empty` «…جارٍ جلب الكتب والأعمال».
- **Every list source failed** (`knowledge`, `prices`, `offers` all error): `.v3-empty` «الكتب والأعمال: غير متاح بعد» + «تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.» + «أعد المحاولة» (`.v3-btn2`, reloads all with `force`).
- **Some failed:** the strip in §4.1 item 2, and the lanes show what came (counts with «+» where partial).
- **Store closed (`prices` 404):** a muted line above the lanes: «متجر الكتب لم يُفتح بعد، فتظهر هنا أعمال السوق وحدها.»
- **Empty:** §4.2 last paragraph.
- **Search with no match:** §4.1 item 4.

### 4.7 Layout per width

- **Desktop (≥ 1180px, shot at 1440):** max width 1360 (`.v3`). Brain card as a row: photo 220px wide on the inline-end, text and button on the inline-start. Decision lanes: `.bk-tgrid` 3 columns, gap 14px. Compact lanes: one column, rows max width 1360.
- **Tablet (761–1179px, shot at 820):** brain photo 160px. `.bk-tgrid` 2 columns.
- **Mobile (≤ 760px, shot at 390):** 16px side gutter (from the shell). Brain card without photo. One column everywhere; every button 52px and full width; search 52px. No horizontal page scroll; no horizontal strip anywhere on this tab.

---

## 5. Screen 2 — the work page (same tab, in-view)

Opened by «افتح» (compact items) or «التفاصيل» (decision items). State `S.open = '<row key>'`; the list scroll position is saved.

**Back button (decided: a history entry, no hash change).** Opening the page calls `history.pushState({v2sBooks: key}, '', location.hash)` (same URL). `books.js` adds **one** `popstate` listener (added once, at script load): when the current module is not owned by the registry, it does nothing; otherwise it sets `S.open = (e.state && e.state.v2sBooks && the row still exists) ? e.state.v2sBooks : null`, redraws, and restores the saved list scroll when `S.open` becomes `null`. The shell's own `popstate` handler (`v2OnHash`, `index.html:7750`) returns early because the hash still equals `#s/books/books`, so the two never fight. The link «→ كل الأعمال» calls `history.back()` when `history.state && history.state.v2sBooks`, else just closes. Result: the phone's Back returns to the list, a second Back leaves the section as before. (The hash variant `#s/books/books/<key>` was not chosen: it needs edits in `V2L.parseSectionHash` and `v2OnHash`, shared code of every section.)

If the opened row disappears after a reload (deleted on the platform), the page shows `.v3-empty` «هذا العمل غير موجود» + «كل الأعمال».

### 5.1 Layout

- Top: `.v3-link` «→ كل الأعمال» (44px; 52px at ≤ 760px).
- **Desktop:** two columns `minmax(0,1fr) 360px`. Start column: header (title `h2` + type pill + owner line + status pill; **no cover**), then the **facts list** (`<dl class="bk-facts">`). End column: **decision panel** (`.v3-card`, `position:sticky; top:16px`): brain line (if any) + the main button (if any) + secondary buttons + the price note for store books. When there is no main button, the panel starts with the lead «لا شيء ينتظرك في هذا العمل.»
- **Tablet:** one column; the decision panel comes right after the header.
- **Mobile:** one column. The decision panel stays in the page right under the header (brain line + secondary actions as full-width `.v3-btn2`, 52px). **Only when the work has a main button**, that button is also shown in a fixed bottom dock `.bk-dock` (one button, full width, 52px, padding `8px 16px calc(8px + env(safe-area-inset-bottom))`, `z-index:60`, below the shell sheet's 80 and the `#epModal` scrim), and the page root gets `data-dock="1"` with `padding-bottom: calc(76px + env(safe-area-inset-bottom))` so the last fact is never covered. In the panel the main button is not repeated on mobile. While a sheet is open the dock is hidden: CSS `body:has(#epModal) .bk-dock{display:none}` plus `books.js` setting `dock.hidden = true` before `openModal` and `false` after `closeModal` (both, because `:has` is the backup, not the only guard). No main button ⇒ no dock and no extra padding.

### 5.2 Facts list (label → value; a missing fact shows «غير متاح بعد», never omitted silently)

| Label | Market work | Store book | Rejected offer |
|---|---|---|---|
| «الحالة» | status pill text | status pill text | status pill text |
| «المبيعات» | §4.5 | §4.5 (with the second line) | — |
| «السعر» | `rights==='owned_for_sale'` ⇒ `L.util.moneyText(price_amount, price_currency)`; `public_domain_feed` ⇒ «مجاني للجميع» | all countries from the `prices` row: `minText` (D3 format «مصر: … · السعودية: …»), or «لا سعر بعد» | suggested price or «لم يقترح سعرًا» |
| «اتفاقية البيع» | for sale: P1 present with `legacy_split===true` ⇒ «صاحب العمل {ar(owner_pct)}٪ · المنصة {ar(platform_pct)}٪ — النسبة القديمة، إلى أن يُنقل إلى قائمة الأسعار الموحّدة»; P1 absent ⇒ «غير متاح بعد». Free work ⇒ «مجاني، لا بيع فيه» | from `store` (`plan_label`, `owner_pct`, `platform_pct`) else from the live offer's `agreement`: «{plan_label}: صاحب العمل {ar(owner_pct)}٪ · المنصة {ar(platform_pct)}٪»; seed book (`source==='ours'`): «كتاب من البروفيسور»; none: «غير متاح بعد» | same from the offer's `agreement` |
| «رصيد الإعلان» | — | only when `catalog_id` is known: `ads` row with `owner_id === catalog_id` ⇒ `balanceText` + «آخر حركة: {last}» + `.v3-lnk` «إعلانات الأعمال» (→ `V2_HOST.openSection('money','ads')`); no row in a ready `ads` ⇒ «لا رصيد إعلان»; `ads` failed ⇒ «غير متاح بعد» | — |
| «الملف» | `has_file` (P1 or review row): «مرفق» / «لا يوجد ملف»; unknown ⇒ «غير متاح بعد» | — (the store checks files itself) | — |
| «أُضيف» | `created_at` ⇒ `L.util.dateText` (P1 or review row); unknown ⇒ «غير متاح بعد» | — | «أُرسل للمراجعة»: `submitted_at` |
| «ملاحظة المراجعة» | only when `review_note` is non-empty | — | only when `review_note` is non-empty |
| «رقم العمل» | small muted `id` (Latin allowed: it is a reference, same exception D3 made for references) | small muted `slug` | small muted `id` |

(There is no «يراه الناس» row: the status pill is the single truth for visibility.)

### 5.3 Actions by row type (each calls an EXISTING endpoint; the same sheets serve the list items and the page)

**Market work, status `review`:**
- Main «اعتمد وانشر» → one-line confirm sheet (§5.5) → `POST /api/platform-knowledge/<id>/decide` `{decision:'approve', admin_note:''}` (exists, `app.py:3043` → `/api/bridge/knowledge/<id>/decide`). Exception: when the brain line B1 (no file, for sale) applies, the main button is «ارفض» and «اعتمد وانشر» becomes secondary.
- Secondary «ارفض» → reason sheet (§5.5) → same endpoint `{decision:'reject', admin_note:<reason>}`.
- On success: note «اعتُمد «{title}» وظهر للناس» / «رُفض «{title}»، ووصل السبب إلى صاحب العمل»; reload `knowledge`, `revPending`, `revRejected`; also `EP.reload('inbox')` so the inbox row disappears. Decided from the list ⇒ stay on the list; decided from the page ⇒ stay on the page (it now shows the new status).
- Platform 422 (no file) / 409 (already decided): show the platform message as is (digits converted) in the sheet's error box; 409 also reloads the row.

**Market work, status `hidden`:**
- Main «أظهر للناس» → show confirm (§5.5) → `PUT /api/platform-knowledge/<id>` `{is_active:true}`.
- Secondary «عدّل» → two-stage edit sheet (§5.4) → `PUT /api/platform-knowledge/<id>` (exists, `app.py:4201`).

**Market work, status `live`:** no main button (nothing waits for a decision); panel lead «لا شيء ينتظرك في هذا العمل.»
- `.v3-btn2` «أخفِ عن الناس» → hide confirm (§5.5) → `PUT /api/platform-knowledge/<id>` `{is_active:false}`. (The old «حذف» button called `DELETE /api/platform-knowledge/<id>`, which on the platform only sets `is_active:false` (`admin_bridge.py:1268`). It is the same act, so it is folded into «أخفِ»; `DELETE` is not called from the new screen.)
- `.v3-btn2` «عدّل» → §5.4.

On success of any of these: note «حُفظ «{title}»» / «أُخفي «{title}» عن الناس» / «ظهر «{title}» للناس»; reload `knowledge`.

**Market work, status `rejected` or `unknown`:** no write action (the platform has no "reopen" path; unknown has no basis). Panel lead «لا شيء ينتظرك في هذا العمل.» Facts + «ملاحظة المراجعة».

**Store book:**
- `noprice`: main «ضع سعرًا» → `V2_HOST.openSection('money','prices')`.
- `hidden` (with prices): main «عدّل الأسعار والظهور» → same target (B4).
- `live`: no main button; `.v3-btn2` «عدّل الأسعار والظهور» → same target; panel lead «لا شيء ينتظرك في هذا العمل.»
- Under the button, muted: «الأسعار وظهور الكتاب للناس تُعدَّل من «الفلوس › الأسعار» فقط.» No other write: the dashboard has no endpoint to edit a store book's title/file (the old screen never had one either).

**Rejected offer:** no action; facts + review note.

### 5.4 Edit sheet (market work) — two stages, same pattern as D3 `twoStage` (`v2-d3.js:406`), re-implemented in `books.js` (D3 does not export it)

Title: «تعديل: {title}». Stage 1 (form):
- «العنوان» `<input>` prefilled (required; empty ⇒ error «اكتب عنوان العمل»).
- Only for `rights==='owned_for_sale'`: «السعر ({curLong(price_currency)})» numeric text input (`inputmode="decimal"`, `dir="ltr"`, `font-size:16px`), parsed with `L.util.parseAmount`; invalid ⇒ «اكتب السعر رقمًا، مثل ١٥٠ أو ١٥٠٫٥٠». Under it, muted: «سعر أعمال السوق يُعدَّل من هنا إلى أن تنتقل إلى «الفلوس › الأسعار».» (§11 D-1).
- Only for `owned_for_sale`: checkbox «يسمح للأعضاء بأن يعرضوا سعرًا («اعرض سعرك»)» from `bid_enabled`.
- Visibility is **not** in this sheet (it has its own button, §5.3).
- Buttons «راجع التغيير» (primary) · «إلغاء».
Stage 2 (review): lead «ستغيّر «{title}». راجع ما سيتغير:», a diff table «البند · الآن · بعد التعديل» built by `L.v2kEditDiff` (§8) with rows «العنوان», «السعر», ««اعرض سعرك»» («مفعّل»/«غير مفعّل»). Nothing changed ⇒ stay on stage 1 with «لم تغيّر أي شيء». When the price changes and `total_acquired > 0`, an extra line under the table: «السعر الجديد يسري على المشترين القادمين فقط.» (fact: each sale stores its own price, NOTES 2026-10-30). When P1 says `legacy_split===true`, one more muted line: «ويبقى البيع بالنسبة القديمة: المنصة {ar(platform_pct)}٪.» Buttons «أكّد التعديل» · «رجوع للتعديل».
Send: body with **only the changed fields**: `title`, `price_egp` (the new number; the platform writes it in the shown currency, `admin_bridge.py:1244-1262`), `bid_enabled`. While sending: «جارٍ الحفظ…», sheet locked.
Errors: 400/422 ⇒ «رفضت المنصة هذا التعديل: {message}»; 404 ⇒ «هذا العمل غير موجود» + reload; 401 ⇒ «انتهت الجلسة — سجّل الدخول من جديد ثم جرّب»; other ⇒ «تعذّر تنفيذ العملية».

### 5.5 One-line confirm and reason sheets

- **Approve:** title «اعتماد: {title}»; text «سيظهر «{title}» للناس في السوق، ويصل إلى صاحب العمل بريد بالنتيجة.»; buttons «اعتمد وانشر» · «إلغاء».
- **Reject:** title «رفض: {title}»; `<textarea>` label «سبب الرفض (يصل إلى صاحب العمل)», maxlength 2000, `font-size:16px`; prefilled «أرفق ملف العمل ثم أرسله للمراجعة من جديد.» only when B1 applies; empty ⇒ «اكتب سبب الرفض، فهو يصل إلى صاحب العمل»; buttons «أرسل الرفض» · «إلغاء».
- **Hide:** title «إخفاء: {title}»; text «لن يظهر «{title}» للناس في السوق.» and, when `total_acquired > 0` and the work is for sale, a warning line (`.v3-warn`): «بيعت منه {U(n)}، ومن اشتراه لا يستطيع تحميله ما دام مخفيًا.» (fact: the download route requires `is_active`, `knowledge.py:731-736,754`). Buttons «أخفِ عن الناس» · «إلغاء».
- **Show:** title «إظهار: {title}»; text «سيظهر «{title}» للناس في السوق.»; buttons «أظهر للناس» · «إلغاء».
All sheets use `window.openModal`/`closeModal` with content wrapped in `<div class="v3m v2s-bm">`, lock while sending, never close on scrim click while busy, and hide the mobile dock while open (§5.1).

### 5.6 «أضف كتابًا» sheet (existing action, same endpoint and fields as the old `addBookModal`)

Title «أضف كتابًا إلى السوق». Lead: «يُضاف الكتاب إلى أعمال السوق على المنصة. كتب المتجر تصل من عروض الأعضاء بعد مراجعتها.» Fields (labels exact; every input `font-size:16px`, `min-height:48px`, 52px at ≤ 760px):
- «عنوان الكتاب» (required; «اكتب عنوان الكتاب»)
- «اسم المؤلف أو الجهة» (optional)
- «وصف قصير يظهر مع الكتاب» (textarea, optional, max 2000)
- «السعر» (text, `inputmode="decimal"`, empty or ٠ = free; muted hint «اتركه فارغًا ليكون مجانيًا للجميع») + «العملة» select: «جنيه مصري» (`EGP`), «دولار أمريكي» (`USD`) — the two the old form offered.
- «رابط ملف الكتاب» (required, `dir="ltr"`; must start with `https://`, else «الصق رابطًا يبدأ بـ https://»)
- «رابط صورة الغلاف» (optional, `dir="ltr"`)
- checkbox «ظاهر للناس فور إضافته» (checked by default)
Buttons «أضف الكتاب» · «إلغاء». One stage (creation, not an edit). Send `POST /api/platform-books` with exactly `{title, author, description, price, currency, file_url, cover_url, is_active}` (exists, `app.py:4242`, admin only, audited `book.create`). Success: close, note «أُضيف «{title}» إلى السوق», reload `knowledge`. Error: platform/proxy message in the sheet (digits converted).

### 5.7 «مكتبة المراجع» sheet (existing action; opened by the link row §4.1 item 7 and by `V2SX.mods.knowledge.library()`)

Title «استيراد إلى مكتبة المراجع». Lead: «ملفات تقرأ منها إجابات المنصة ومحرّر المذكرات، ولا تُعرض للبيع. يُستورد حتى ٤٠ ملفًا في كل مرة. الملفات المصوّرة (صور صفحات) لا تُقرأ بعد وتُتخطى. يلزم ربط حساب Google Drive من المنصة مرة واحدة قبل أول استيراد.» Fields:
- «رابط المجلد في Google Drive» (`dir="ltr"`, placeholder «الصق رابط المجلد»). Accepts a full folder link or the bare id; `L.v2kFolderId(text)` (§8) extracts the id; none ⇒ «الصق رابط مجلد من Google Drive».
- «نوع الملفات» select: «صيغ ونماذج» (`memo_template`, default), «قوانين وتشريعات» (`law`), «أحكام» (`ruling`), «أخرى» (`custom`).
Buttons «استورد» · «إلغاء». Busy text «جارٍ الاستيراد… قد يستغرق دقيقة». Send `POST /api/platform-library/ingest-folder` `{folder_id, category, max_files:40}` (exists, `app.py:3971`). Success: the sheet shows «استُورد {ar(ingested)} من {ar(found)} ملفًا» (numbers from the response; a missing field ⇒ that number «غير متاح بعد»), button «تم». Error: platform message or «تعذّر الاستيراد الآن».

---

## 6. The brain lines (suggest; the founder decides)

All lines are computed by pure helpers from the loaded sources. Each names its basis. No AI call anywhere.

### 6.1 Summary line on the brain card (`L.v2kBrainSummary(result)`)
Parts, in this order, only when > 0 and only from statuses that are known, written as «label: count» so no verb has to agree with the number: «في انتظار مراجعتك: {U(n, ['عمل واحد','عملان','أعمال','عملًا'])} من السوق» (market works only; offers are counted in their own tab), «بلا سعر: {U(n, ['كتاب واحد','كتابان','كتب','كتابًا'])}», «مخفي وبيعت منه نسخ: {U(n, ['عمل واحد','عملان','أعمال','عملًا'])}». Joined with « · ».
- None of them and every status source ready: «لا شيء ينتظرك في الكتب والأعمال الآن.» (no button).
- Some status source failed: append « — وبعض المصادر لم تصل، فقد يكون العدد أكبر».
Button (one at most): it always **scrolls to the first lane that has items** among `review`, `noprice`, `hiddenSold` (`scrollIntoView({block:'start'})` then focus the lane `h2`). Label by that lane: «ابدأ المراجعة» / «اعرض الكتب بلا سعر» / «اعرض المخفي المبيع». It never changes tab and never filters.

### 6.2 Per-work lines (`L.v2kBrainLine(row, now)`; at most one per work; shown on decision items and in the work page's decision panel)

| Id | Applies when | Line | Main button it gives |
|---|---|---|---|
| B1 | market work `review`, `rights==='owned_for_sale'`, `has_file===false` | «لا يوجد ملف مرفق، والمنصة لا تنشر عملًا للبيع بلا ملف.» | «ارفض» (reason prefilled, §5.5) |
| B2 | market work `review`, waiting time known | «ينتظر المراجعة منذ {agoText(created_at)}.» | «اعتمد وانشر» |
| B3 | store book `noprice` | «لا سعر لهذا الكتاب بعد، فهو غير معروض للبيع.» | «ضع سعرًا» |
| B4 | store book `hidden` | «له أسعار، لكنه مخفي عن الناس.» | «عدّل الأسعار والظهور» |
| B5 | market work `hidden`, for sale, `total_acquired > 0` | «مخفي الآن، و{U(n)} بيعت منه لا يستطيع أصحابها تحميلها ما دام مخفيًا.» | «أظهر للناس» |
| B6 | market work `live`, for sale, `total_acquired === 0`, `created_at` known and ≥ 30 days ago | «لم تُبع منه نسخة منذ أُضيف قبل {ar(days)} يومًا.» | none (fact only) |
| B7 | market work for sale (`live` or `hidden`), P1 `legacy_split===true` and `platform_pct < 35` | «يُباع بالنسبة القديمة (المنصة {ar(platform_pct)}٪، أقل من الحد ٣٥٪) إلى أن يُنقل إلى قائمة الأسعار الموحّدة.» | none (fact only; P3 fixes it) |

Priority when several apply: B1 > B5 > B3 > B4 > B2 > B7 > B6. Facts used: `rights`, `has_file`, `status`/review lists, `is_active`, `total_acquired`, `created_at`, `has_prices`, `visible`, `legacy_split`, `platform_pct`. B2, B6 need `created_at`, B7 needs P1; without the field there is no line. No price comparison here (that line already lives in «مراجعة العروض»). Compact items do not show the line; the work page does.

### 6.3 Exposed for other sections
`window.V2SX.mods.knowledge.summary()` returns `{review, noprice, hiddenSold, legacySplit, offersWaiting, partial}` (numbers or `null` when unknown) from the last computed rows, so the home and brain sections may read it without fetching. It never triggers a fetch.

---

## 7. Server routes (new file `backend/v2_books_routes.py`, read only)

```python
def register(app, g):
    """g = backend/app.py globals(). Handlers look names up in g at REQUEST time
    (`_platform_proxy` is defined below the registration line in app.py)."""
```
Both routes: `@g['token_required']`, `@g['roles_required']('admin')`, `g['_v2_closed']()` first (flag off ⇒ 404 with no platform call), `Cache-Control: no-store` via `g['_v2_ns']`, platform 401/403 masked to 502 via `g['_v2_mask_auth']` (same as D3 `_v2_get`), one call, no retry, no invented body.

1. **`GET /api/v2/books/review?status=pending_review|rejected`**
   - `status` must be exactly one of the two, else 400 `{"error":"حالة غير معروفة"}` before any call.
   - Calls `GET /api/bridge/knowledge/review?status=<status>`.
   - On 200: returns `{"items":[...], "count": n}` where every item is rebuilt from a whitelist: `id, slug, title, type, owner_email, owner_name, rights, is_active, status, created_at, updated_at, review_note, total_acquired` plus `has_file: bool(str(file_url).strip())`. ⛔ `material_text`, `file_url`, `file_path`, `pricing`, `owns_it` and every other field are dropped (today the inbox loader receives the full document; this route never forwards the private text).
   - Non-200: status and `{error}` as `_platform_proxy` gave them (after the mask).
2. **`GET /api/v2/books/store`**
   - Calls `GET /api/bridge/books/works` (P2). 404 passes through as 404 (store closed or bridge not built ⇒ UI «غير متاح بعد»).
   - On 200: whitelist per item: `slug, title, source, type, owner_email, owner_name, catalog_id, offer_id, plan, plan_label, owner_pct, platform_pct, paid_owners, owners_total, by_version{read,pdf}, last_sold_at`.

### 7.1 Registration in `backend/app.py`
- If missing, add the marker comment `# ---- v2 section routes end` on its own line **directly after** the function `v2_book_request_patch` (ends ~`app.py:2692`) and before `@app.route('/api/platform-pnl'`.
- Add exactly one line right before the marker:
```python
__import__('v2_books_routes').register(app, globals())
```

---

## 8. Pure helpers in `v2-logic.js` (end of file, `// ===== v2s:books =====` block)

The block is its own IIFE: `(function (root) { var L = root.V2L; if (!L) return; … })(typeof window !== 'undefined' ? window : globalThis);`. It uses only exported things: `L.util` (`ar, U, agoText, moneyText, dateText, curLong, parseAmount`), `L.v2Prices`, `L.v2AdsLedger`, `L.NA`, `L.COUNTRY_LABEL`. No DOM, no network. Functions are attached to `L` (so `v2_apply.js` can run them):

| Function | In → out |
|---|---|
| `v2kWorks(src, now)` | `src = {knowledge, revPending, revRejected, prices, offers, store}` (each the raw response or `null`; `prices`/`store` may also be the string `'closed'`) ⇒ `{rows:[row], lanes:{review, noprice, hiddenSold, live, hidden, unknown, rejected}, counts:{<lane>:n}, partial:{<lane>:bool}, offersWaiting:number|null, storeClosed:bool, failed:[label]}` or `null` when `knowledge`, `prices`, `offers` are all `null`. `lanes.<key>` is the ordered array of row keys per §4.2 (lane assignment and sort live here, not in the DOM code); `offersWaiting` is the count of offers `in_review` (`null` when `offers` failed). `row = {key, kind:'market'|'store'|'offer', id, title, typeText, ownerName, ownerEmail, ownerNA, status, statusText, lane, salesText, salesNA, salesSub, priceText, createdText, createdAt, waitingSince, hasFile:true|false|null, reviewNote, agreementText, legacySplit:bool|null, platformPct:number|null, catalogId, brain:{id,text,action}|null, forSale, sold:number|null, isActive, bid, priceAmount, priceCurrency, raw}` (no `visibleText`, no `sourceText`; the type pill carries «من المتجر») |
| `v2kSearch(result, q)` | ⇒ the same `lanes` shape with only the matching keys (search over title + owner name through `v2kKey`); empty `q` ⇒ unchanged |
| `v2kKey(text)` | normalised search key (hamza/ta marbuta/alef maqsura/diacritics/digits) |
| `v2kBrainLine(row, now)` | §6.2 ⇒ `{id, text, action}` or `null` |
| `v2kBrainSummary(result)` | §6.1 ⇒ `{text, action:{label, lane}|null}` (`lane` = the key of the lane to scroll to) |
| `v2kEditDiff(row, input)` | `input = {title, priceText, bid}` ⇒ `{ok, error, changed, lines:[{label, from, to}], body}`; `body` holds only changed fields (`price_egp` as a number) |
| `v2kAddBook(input)` | form values ⇒ `{ok, error, body}` with the exact 8 fields of §5.6 |
| `v2kFolderId(text)` | link or id ⇒ id string or `''` (accepts `drive.google.com/drive/folders/<id>`, `…/drive/u/0/folders/<id>?…`, `open?id=<id>`, bare `[A-Za-z0-9_-]{10,}`) |
| `v2kHideWarning(row)` | ⇒ text of the hide warning (§5.5) or `''` |

Visible strings that these helpers return must pass the clean-copy test (§10.1 item 12).

---

## 9. What stays as «كل السجلات»

**Nothing.** The old `viewKnowledge` is no longer reachable under the shell. Each of its parts has a new home:

| Old part (`index.html`) | New home |
|---|---|
| Policy banner «سوق المعرفة: …» | dropped (internal explanation; the lead lines carry what the founder needs) |
| KPIs «للبيع / للتغذية العامة / اقتناءات» | lane counters + per-work sales text (the summed «اقتناءات» across free and paid mixed two meanings, so it is not repeated) |
| «استيراد مكتبة قانونية من Google Drive» | one muted link row at the bottom + sheet (§4.1 item 7, §5.7); final home «العقل» (D7) through `V2SX.mods.knowledge.library()` |
| «عناصر السوق» rows | lane items (§4.2, §4.3) |
| «+ إضافة كتاب» | «أضف كتابًا» (§5.6) |
| «تعديل» (title, price, active, bid) | «عدّل» (§5.4) + «أخفِ/أظهر» (§5.3) |
| «حذف» (soft hide) | «أخفِ عن الناس» (same platform effect) |
| Review decisions (only in the inbox before) | on the review-lane item and the work page (same endpoint, same sheet) |

The old code stays in `index.html` unchanged for the flag-off path.

---

## 10. Tests and shots

### 10.1 `backend/tests/test_v2s_books.py` (zero real network; platform = `v2s_books_fixtures.BooksPlatform`, extends `d3_fixtures.D3Platform` with `knowledge`, `knowledge/review`, `books/works` and the write routes; any URL outside `https://platform.test` fails the test)

pytest — routes:
1. `/api/v2/books/review` and `/api/v2/books/store`: admin only (each of `employee, trainer, investor, viewer, pending` ⇒ 403; no token ⇒ 401); flag off ⇒ 404 **and** zero platform calls; `Cache-Control: no-store` on every response (200 and errors).
2. `review`: `status` other than the two ⇒ 400 with no call; the response never contains `material_text`, `file_url`, `file_path`, `pricing`; `has_file` true/false computed right (including a whitespace-only `file_url` ⇒ false).
3. `store`: platform 404 ⇒ 404 passes; platform 401/403 ⇒ 502 `{"error":"تعذّر الاتصال بالمنصة"}`; platform 500 ⇒ error status with `{error}` only; whitelist enforced.
4. Registration: `app.py` contains the marker once and the books line once, directly before it; `v2_books_routes.register` resolves `_platform_proxy` at request time (a test patches `app._platform_proxy` after import and sees it used).
5. The existing write routes are unchanged (the screen calls them): a smoke call to `PUT /api/platform-knowledge/<id>`, `POST /api/platform-knowledge/<id>/decide`, `POST /api/platform-books`, `POST /api/platform-library/ingest-folder` through the fixture returns what it returned before.

node — logic (`v2_node.logic`):
6. `v2kWorks` with every source ready: statuses per §4.4, lane assignment and order per §4.2 (B5 works go to `hiddenSold`, not `hidden`), sort inside each lane, owner join (store ⇒ offers fallback when `store` is `'closed'`), offers `in_review`/`draft`/`live` never rows, `offersWaiting` counts `in_review` offers, rejected offers in `rejected`, counts.
7. Failed sources: `store` null ⇒ every store row `salesText === 'المبيعات: غير متاح بعد'` and `sold === null` (never 0); `revPending` null and no P1 field ⇒ affected rows `unknown`, `partial.review === true`; `offers` null ⇒ `offersWaiting === null`; all three list sources null ⇒ `null`. Market work for sale without P1 ⇒ `agreementText === 'غير متاح بعد'`, `legacySplit === null`.
8. P1 fields present ⇒ review sources ignored (a test passes contradicting review lists and the P1 `status` wins).
9. Sales wording: for sale 0/1/2/3/11/100 and free 0/1/2, Arabic digits, plural forms; store `by_version` line with read/pdf 0/1/3 (no «PDF», no Latin digit).
10. Brain lines B1–B7 each fire on their exact basis and not without it (B6 with `created_at` missing ⇒ `null`; 29 days ⇒ `null`; 30 ⇒ line; B7 with `platform_pct` 35 ⇒ `null`, 20 ⇒ line, P1 absent ⇒ `null`); priority order; summary text (market works only, offers excluded), its single action and the lane it points to.
11. `v2kEditDiff` (no change ⇒ `changed:false`; title only; price with Arabic digits «١٥٠٫٥» ⇒ 150.5; invalid price ⇒ error; bid toggle; `body` holds only changed fields); `v2kAddBook` (missing title/link, non-https link, price empty ⇒ 0); `v2kFolderId` (5 link shapes + garbage); `v2kHideWarning`; `v2kSearch`/`v2kKey` (أ/إ/آ/ا, ة/ه, ى/ي, diacritics; a lane with no match is dropped).
12. Clean copy: every string any helper returns, plus every literal string in `v2s/books.js`, contains no «يقوّم», no Latin digit (except inside `dir="ltr"` inputs and the muted reference id), none of the words `API, ID, RAG, OCR, PDF, Folder, bridge, null, undefined, NaN`, and no headline starting with «الذكاء».
12b. No persistence: `v2s/books.js` contains no `localStorage`/`sessionStorage`.

files — wiring:
13. `index.html`: both tags inside the `v2 sections` block, alphabetical; the `V2SX` dispatch line exactly once, right after the D3 line; `viewKnowledge` still present (flag-off path).
14. `SECTIONS.books` tabs unchanged (keys/labels/modules) and `desc` is the new text.
15. Flag off: `V2SX.owns('knowledge')` is false when `V2SHELL.on` is false (node with a stub window).
16. Registry exposes `V2SX.mods.knowledge.summary` and `.library` as functions.
Also rerun unchanged: `test_v2_d1.py`, `test_v2_d1b.py`, `test_v2_d2.py`, `test_v2_d3.py` (expected counts 129 / 29 / 67 / 110 plus whatever the shared allowlist change in §12 needs in `test_xss_hardening.py`).

### 10.2 Shots — `backend/tests/uiharness/v2_shots_books.py`

Run: `cd backend && python3 -B tests/uiharness/v2_shots_books.py ../docs/v2/final/shots-books`. Viewports: desktop `d*` 1440×900, tablet `t*` 820×1180, mobile `m*` 390×844. Uses `Harness`, `Browsers`, `open_shell`, `go_section`, `d3_check`-style checks imported from `v2_shots.py`.

| # | Shot | State |
|---|---|---|
| 01 | `NN-01-list` | full list, all sources ready: lanes «ينتظر مراجعتك» (with the offers link line), «بلا سعر», «مخفي وبيعت منه نسخ», «ظاهر للناس», «مخفي», «مرفوض» collapsed; brain summary with «ابدأ المراجعة»; > 12 rows so the search shows |
| 01b | `NN-01b-brain-scroll` | after clicking the brain button: the review lane header at the top, focused |
| 01c | `NN-01c-search` | search «دليل» (Arabic normalisation hit), lanes without a match gone |
| 01d | `NN-01d-nomatch` | search with no match ⇒ «لا أعمال بهذا الوصف» + «امسح البحث» |
| 01e | `NN-01e-rejected-open` | «مرفوض» lane opened (market work + rejected offer) |
| 01f | `NN-01f-few` | ≤ 12 rows: no search box |
| 02 | `NN-02-sources-down` | `knowledge` ok, `store` 502, `revPending` 502: warn strip, «المبيعات: غير متاح بعد», lane «لم تصل حالتها», counters with «+» |
| 02b | `NN-02b-store-closed` | `prices` 404: note «متجر الكتب لم يُفتح بعد…», market works only |
| 02c | `NN-02c-all-down` | every list source down: «الكتب والأعمال: غير متاح بعد» + retry |
| 02d | `NN-02d-offers-only` | no market work in review, 2 offers in review: review lane with «لا أعمال من السوق تنتظر مراجعتك» + «وعرضان في «مراجعة العروض»» |
| 03 | `NN-03-work-market-live` | market work page, for sale, sold, no main button, lead «لا شيء ينتظرك في هذا العمل.», «اتفاقية البيع» with the old split (P1 fixture) and B7 line |
| 03b | `NN-03b-work-hidden-sold` | hidden work with sales: B5 line + main «أظهر للناس» (mobile: dock) |
| 03c | `NN-03c-back` | page opened, then `history.back()` ⇒ the list at the saved scroll, still `#s/books/books` |
| 03d | `NN-03d-no-p1` | market work for sale without P1: «اتفاقية البيع: غير متاح بعد», no B7 |
| 04 | `NN-04-review-item` | review-lane item with B2 and the inline «اعتمد وانشر» / «ارفض» |
| 04b | `NN-04b-approve` | approve confirm sheet opened **from the list item** (mobile: no dock visible behind it) |
| 04c | `NN-04c-reject-nofile` | B1 item (red strip, main «ارفض»): reject sheet with the prefilled reason |
| 04d | `NN-04d-after-approve` | note strip after approval, the work moved to «ظاهر للناس» |
| 05 | `NN-05-work-store` | store book page: prices (all countries), agreement, ad balance, sales with the version line, «عدّل الأسعار والظهور» as secondary (live) |
| 05b | `NN-05b-store-noprice` | «بلا سعر» item, «ضع سعرًا»; clicking lands on «الفلوس › الأسعار» (shot of the landing) |
| 06 | `NN-06-edit` | edit sheet stage 1 |
| 06b | `NN-06b-edit-diff` | stage 2 before→after with the price line note |
| 06c | `NN-06c-edit-refused` | platform 422 message in the sheet |
| 07 | `NN-07-hide-warning` | hide confirm with the buyers warning |
| 08 | `NN-08-add` | «أضف كتابًا» sheet (opened from the bottom button) with a validation error |
| 09 | `NN-09-library` | the bottom link row, then the sheet, then `09b` the result «استُورد …» |
| 10 | `NN-10-empty` | no works at all: one `.v3-empty` with «أضف كتابًا», no lanes, no second add button |
| 12 | `NN-12-flag-off` | flag off: `#knowledge` renders the old screen (proof nothing changed); no `.v2s-books` in the DOM; `/api/v2/books/*` ⇒ 404 |

The script fails (`exit 1`) when: a «٠/0/null/NaN/undefined» shows where a source failed; a target < 44px (buttons < 52px at 390); horizontal page scroll; a Latin digit outside the allowed places; any write reaches the fake platform other than the four existing endpoints, or a write is recorded before the script clicks the sheet's confirm button (the fixture logs every write with a timestamp; the script compares it with the click time, so no test-only code goes into `books.js`); any request leaves the process except Google Fonts; any old-look marker under the shell on this tab (`.kpis`, `.policy`, `#knRows`, `details`, `.esc-row`, `.bk-cover`, `[role=tablist]` chips); any `<img>` on the tab other than `v2/img/books.jpg` and the brain avatar; a search input or textarea with computed `font-size` < 16px or height < 48px (52px at 390); on the 390 work page with a dock, the last `<dd>` not fully visible after scrolling to the bottom (its bottom edge must be above the dock's top edge); the dock visible while `#epModal` exists; after `history.back()` from a work page the view is not the list or the hash is not `#s/books/books`; `localStorage` holds any key starting with `v2s_books`.

Also rerun `v2_shots.py d1b` and `d3` (unchanged scripts) to prove the shared hook broke nothing.

---

## 11. Decisions (made here; flagged for the founder in STATUS)

- **D-1 — prices of old market works.** «الفلوس › الأسعار» lists only store books (the unified price list, `/bridge/prices/book` = seed + catalog). Old market works (`knowledge_items`) keep their price inside the work's own document and are absent from that list. Removing their price field would remove an existing action. So the edit sheet (§5.4) keeps the price for **these works only**, with a before→after review and the muted line saying it moves to «الأسعار» later. Store books never get a price field here. P3 removes the exception.
- **D-2 — «حذف» folded into «أخفِ عن الناس».** Same platform effect (`is_active:false`), reversible, and honest wording.
- **D-3 — module key stays `knowledge`.** All old links and the home/inbox destinations land on the new screen with zero alias changes (§1.1).
- **D-4 — owner of a store book with no source.** Without P2, a store book with no matching live offer shows «صاحب العمل: غير متاح بعد» rather than assuming «البروفيسور».
- **D-5 — review decisions on the list item and the work page.** Same endpoint and same sheet as the inbox row; the inbox keeps its copy. One decision, one endpoint, one sheet; not a new path.
- **D-7 — offers in review live only in «مراجعة العروض».** This tab never lists them; the review lane shows one link line with their count. Rejected offers stay here (in «مرفوض») because they have no other home.
- **D-8 — old market works still sell at the old split (founder-visible).** Market works for sale are paid through `KNOWLEDGE_SELLER_PCT = 80` (`payments.py:1111`), so the platform takes 20%, below the 35% floor (`SHARES-2026-10-30.md`). This screen does not change it (no share is set from here); it states it on every such work («اتفاقية البيع» + B7) once P1 returns the split, and shows «غير متاح بعد» before that. P3 moves these works under `clamp_owner_share`. STATUS-books.md must list this under «قرارات تحتاج المؤسس», not only here.
- **D-9 — «مكتبة المراجع» is not a books job.** It feeds the platform's answers, so on this tab it is one muted link row at the bottom, and its final home is the «العقل» section (D7), which opens the same sheet through `V2SX.mods.knowledge.library()`. STATUS-books.md notes this hand-over.
- **D-10 — Back on a work page returns to the list** through a same-URL history entry (§5), not a new hash, to keep shared shell code untouched.
- **D-6 — no Drive "Folder ID" in visible copy.** The founder pastes the folder link; the id is extracted client-side.

---

## 12. shared_edits (minimal; list them in the build report)

1. `dashboard-cloud/index.html` `renderView()`: the one `V2SX` dispatch line (§1.1). Identical bytes for every section that uses the registry, so a merge of two identical additions is clean.
2. `deploy/Dockerfile.coolify`: the image copies frontend files one by one and only `backend/app.py`. Add after the `v2/img` line:
   `COPY dashboard-cloud/v2s /app/dist/v2s` and, after `COPY backend/app.py /app/app.py`: `COPY backend/v2_*_routes.py /app/`. (Without these the deployed dashboard 404s `v2s/books.js` and `app.py` fails to import the routes.) Same two lines for every section; merge-identical.
3. `backend/tests/test_xss_hardening.py:628`: the script allowlist regex must accept `v2s/<key>.js`: change the negative lookahead to `(?!site-content\.js|dashboard-api\.js|v2-logic\.js|v2-home\.js|v2-shell\.js|v2-d2\.js|v2-d3\.js|v2s/[a-z0-9_-]+\.js)`.
4. `backend/app.py`: the marker comment (if missing) + the one registration line (§7.1).

No edit to `v2-d3.js`, `v2-d3.css`, `v2-shell.js`, `v2-home.js`, `dashboard-api.js`, or other sections' files.

---

## 13. Revision 2 — expert review: what was applied, what was not

| # | Point | Result |
|---|---|---|
| 1 | List was a store-admin catalog; decisions took 3–4 taps | **Applied.** §4 rebuilt as lanes with counters; review / no-price / hidden-sold items carry the brain line and the decision buttons inline (same sheets as the page); chips removed; search only when > 12 rows; «أضف كتابًا» moved to the end; brain card = one line + one scroll button; empty ⇒ one `.v3-empty`. |
| 2 | Two components (card with fake cover + mobile row-button) | **Applied.** One `.bk-item` at every width (§4.3); `.bk-cover` and `.bk-rowbtn` deleted; the only photo is `books.jpg` on the brain card. Two densities (decision/compact) of the same component, as the board shows. |
| 3 | Offers in review shown twice in one section | **Applied.** Not rows here; one link line with their count in the review lane; brain summary counts market works only; rejected offers kept under «مرفوض». |
| 4 | Back leaves the section | **Applied** with the same-URL history entry (§5); the hash variant was rejected because it edits shared shell code (`parseSectionHash`, `v2OnHash`) that every section depends on. |
| 5 | Share row omitted for market works | **Applied, extended.** «غير متاح بعد» without P1; with P1 the real split from the platform constant (owner/platform %) and B7 when platform < 35%. P1 returns the two percentages as well as the boolean, so the screen states a number from a source rather than the vague «النسبة القديمة». P3 now includes moving these works under `clamp_owner_share`. Listed as founder-visible D-8. |
| 6 | Persisted filter | **Applied.** No `localStorage`; search text in memory only; test 12b and a shot check guard it. |
| 7 | Mobile dock covers facts / sheets | **Applied.** Dock = main button only, only when there is one; page padding; hidden while `#epModal` exists (JS + `:has`); shot checks the last `<dd>`. |
| 8 | «مكتبة المراجع» card on a sales screen | **Applied.** One muted link row at the bottom; `V2SX.mods.knowledge.library()` for the «العقل» section; noted in STATUS. |
| 9 | Wine «عدّل» on a live work | **Applied.** Live ⇒ no main button, two `.v3-btn2`, lead «لا شيء ينتظرك في هذا العمل.»; hidden ⇒ main «أظهر للناس». Same rule applied to store books (live ⇒ secondary). |
| 10 | Chips 44px / search height unspecified | **Applied** to what survives: chips are gone; search, inputs, textarea 48px (52px on phone), 16px font; fold button and links 52px on phone; added to the shot checks. |
| 11 | «يراه الناس» duplicates «الحالة» | **Applied.** Row removed. |
| 12 | «قراءة {ar(read)} · PDF …» (the review text arrived cut off after this) | **Applied as understood:** a bare count after a Latin word is unclear and breaks the clean-copy rule, so the line is now a sentence («منها نسختان للقراءة على المنصة ونسخة واحدة للتحميل»), shown on the work page only, and «PDF» joins the clean-copy word list. The add-book field label lost its «(PDF)» for the same reason. |

Rejected: nothing in substance. The only alternative not taken is the hash route in point 4 (reason above).

---

## Platform needs

Built on the platform branch `money-d3` (`~/Documents/Playground/elprofessor-wt-d3`). ⛔ Not in `routes/money_bridge.py`, `services/money_settings.py`, `routes/books_bridge.py`, `services/catalog_prices.py` (owned by other sessions). Same secret guard as the other bridges (`X-ELP-Metrics-Secret`), read only, no AI call, defaults change nothing for existing callers.

**P1 — more fields on the existing market-works list (additive).** `GET /api/bridge/knowledge` (`routes/admin_bridge.py:1185`), each item gains:
```json
{ "status": "pending_review | published | rejected",   // missing in the document ⇒ "published" (same rule as knowledge.py:140)
  "created_at": "ISO-8601 | \"\"",
  "updated_at": "ISO-8601 | \"\"",
  "has_file": true,                                      // bool(str(file_url).strip()); the link itself is NOT returned
  "review_note": "string (\"\" when none)" }
```
For works with `rights==="owned_for_sale"`, three more fields (the split that `payments.py` applies today, read from the constant at request time, never typed into the bridge):
```json
{ "legacy_split": true,                                  // false or absent for free works
  "owner_pct": 80,                                       // KNOWLEDGE_SELLER_PCT
  "platform_pct": 20 }                                   // 100 - KNOWLEDGE_SELLER_PCT
```
Effect: the dashboard stops calling the review list twice, gets `created_at` for every work (brain lines B2/B6, «أُضيف»), and can state the split of market works («اتفاقية البيع», B7). Until P1 ships, the dashboard falls back to `/api/v2/books/review` (works today) and shows «اتفاقية البيع: غير متاح بعد».

**P2 — store books facts (new).** `GET /api/bridge/books/works` in a **new** file (suggested `routes/books_works_bridge.py`), gated like `books_bridge._guard(kind="book")`: `BOOKS_STORE_ENABLED` off ⇒ 404 before the secret check; bad secret ⇒ 401; no DB ⇒ 503.
```json
{ "ok": true,
  "count": 2,
  "items": [
    { "slug": "lawyer-first-client",
      "title": "دليل المحامي إلى العميل الأول",
      "source": "ours | member",               // ours = load_books() seed; member = book_catalog (from an approved offer)
      "type": "book | guide | research | other",
      "owner_email": "", "owner_name": "البروفيسور",   // member: from book_catalog.owner_*; ours: "" and "البروفيسور"
      "catalog_id": "BK_… | null",             // book_catalog.id (= ads_ledger owner_id); null for ours
      "offer_id": "… | null",
      "plan": "normal | ads | null", "plan_label": "string | \"\"",
      "owner_pct": 60, "platform_pct": 40,     // from book_catalog.shares_snapshot; null when absent
      "owners_total": 7,                       // rows in knowledge_acquisitions with kind="book" and item_slug="book:<slug>"
      "paid_owners": 5,                        // of those, rows with a non-empty payment_id
      "by_version": { "read": 3, "pdf": 2 },   // paid rows by current version ("read" when missing, as books_store._version_of)
      "last_sold_at": "ISO-8601 | null" } ] }  // max(acquired_at, pdf_at) over paid rows
```
Rules: one row per known book (`BM.known_books(db)`), sorted by title; counts are `count_documents`/aggregation only (no PII returned); a book with no rows ⇒ zeros (a real zero, because the source answered).

**P3 — later, removes decision D-1.** Bring old market works that are for sale into the unified price list so «الفلوس › الأسعار» shows and edits them: either `GET /api/bridge/prices/book` lists `knowledge_items` with `rights="owned_for_sale"` (id `kn:<id>`) and `PUT` writes through to their `pricing`, or those works are migrated into `book_catalog`. Owner: the books session (it owns `catalog_prices`). In the same move these works must be paid under `clamp_owner_share` (platform ≥ 35%) instead of `KNOWLEDGE_SELLER_PCT`; existing sales keep their stored split. When P3 lands, the dashboard removes the price field from §5.4, links to «الأسعار» like store books, and B7 disappears by itself (`legacy_split` false).
