# Final round — «التسويق» (section key `marketing`)

**Founder order (2026-10-30):** «الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا».
This is final work. No part of the «التسويق» section may keep the old look.

**Approved concept:** `dash-canvas/project/Marketing.dc.html`.
- Its tabs are «الحملات · السوشيال ميديا · خطة النشر · التقرير».
- It has four numbers, a brain suggestion, the table «الحملات: من الإعلان حتى الدفع», a weekly publishing plan, social cards, and the strip «العقل يرى من».

**Plan line D5:** connect «مدار» and Meta/Google. Each campaign runs from ad to payment and is tied to its owner. The brain asks to connect any missing source.

**Worktree:** `.worktrees/marketing`, branch `final-marketing` (from `7d1aa83`).
- Everything sits behind `DASH_V2_ENABLED`.
- With the flag off, behaviour stays byte-identical to today.

**Revision 2 (2026-10-30):** revised after the expert review. Every change is listed in §16 «Decisions».

**Hard limits for the build:**
- Zero real network calls and zero paid calls.
- No push and no deploy.
- `git add` with explicit paths only.
- Never touch the main checkout.

---

## 0) What exists today (read before building)

| Piece | Where | Fact |
|---|---|---|
| Old screen | `dashboard-cloud/index.html:4142-4236` (`viewMarketing`, `renderMkt`, `drawMkt`, `createCampaignModal`) | Old look: `.kpis` + `.inboxwrap/.panel/.drawer`. Four KPIs (active campaigns, spend, leads, «CAC»), a campaign list, and a drawer with «إيقاف/تشغيل · تعديل · حذف». The modal has Latin labels («Impressions», «Clicks», «Google Ads»). |
| Old loader | `dashboard-api.js:2210-2227` (`loaders.marketing`) | `GET /api/campaigns`. It **collapses status** to active/paused (loses `draft`/`completed`) and **drops `currency`, dates, `recommendation`**. |
| Old writes | `dashboard-api.js:3730-3744` | `EP.createCampaign` / `EP.updateCampaign` / `EP.deleteCampaign` ⇒ `POST /api/campaigns`, `PUT /api/campaigns/<id>`, `DELETE /api/campaigns/<id>`. |
| Server | `backend/app.py:416-437` (model `Campaign`), `6089-6165` (CRUD, admin only) | Local SQLite, **typed by hand**. Fields: `name, platform, status(draft/active/paused/completed), start_date, end_date, budget, spent, currency (default 'USD'), impressions, clicks, leads, conversions, revenue_attributed, course_id, target_audience, notes`. GET adds `cpl, cac, roas, conversion_rate, recommendation`. |
| Trap 1 | old modal | The labels say «(ج)», but the modal never sends `currency`, so every row saved from the old screen is stored as **USD** although the founder typed pounds. The new screen never converts. It shows a one-time strip above the numbers that lists these rows and fixes them all in one confirmed step (§4.2a). |
| Trap 2 | old modal | The «الدورة المرتبطة» select is read but **never sent** (`course_id` is always null). It is dropped. The new owner link (§6) replaces it. |
| Trap 3 | `POST /api/campaigns` | `d['name']` is required; a missing name ⇒ 500. The new form requires a name before sending. |
| Real sources the marketing screen can use | see §3 | Campaigns (manual) · platform income by service (D3) · ad balances of course/book owners (D3) · site articles (local CMS) · ops queue drafts. |
| Attribution | platform `routes/auth.py:267` (`?ref=` affiliate), `routes/payments.py:92-94` (`attribution` = trainer/platform on course orders), `marketing_ops.py:296` (`lead_magnet_leads.source`) | **No per-signup or per-payment traffic source** (no utm/referrer on users or payments). So «دخل جاء بلا إعلانات» has **no source** ⇒ «غير متاح بعد» + a source request (Platform need P1, which builds on the reports round's N1). |
| Social / ad platforms / «مدار» | — | Nothing connected. «مدار» is a separate system (madar.afandy.me) and its integration comes later. **No fake data anywhere.** |
| Ad clients billed by results | concept `Company.dc.html` («عملاء الإعلانات: نحسب لهم بالنتيجة») | They live in «الشركة ورأس المال». Marketing only links there. |

---

## 1) Files and parallel-safety

New files (all ours):
- `dashboard-cloud/v2s/marketing.js`: the screens (DOM, loaders, sheets).
- `dashboard-cloud/v2s/marketing.css`: only `.mk-*` classes. It **reuses** the D3 classes already loaded globally (`.v3-card .v3-ch .v3-nums .v3-num .v3-big .v3-note .v3-oth .v3-btn1 .v3-btn2 .v3-link .v3-seg .v3-pb .v3-empty .v3-warn .v3-ok .v3-err .v3m .v3-two .v3-twocol .v3-list`). Do not edit `v2-d3.css`.
- `backend/v2_marketing_routes.py`: the new routes (§8), exposing `register(app, env)`.
- `backend/tests/test_v2s_marketing.py`: pytest + node.
- `backend/tests/uiharness/mk_fixtures.py`:
  - `MKPlatform(d3_fixtures.D3Platform)` plus the attribution bridge (on/off);
  - `seed_mk(appmod)` seeds the Campaign and Article rows.
- `backend/tests/uiharness/v2_shots_marketing.py`: imports helpers from `v2_shots.py` without editing it, and saves to `docs/v2/final/shots-marketing/`.
- `docs/v2/final/STATUS-marketing.md`: written at the end of the build.

Edits to shared files (each minimal, exact text; the integrator dedupes identical lines):

1. `dashboard-cloud/index.html`, inside the block `<!-- v2 sections begin -->` … `<!-- v2 sections end -->`.
   - If the block is missing, create it right after `<script src="v2-d2.js"></script>`.
   - Add these two lines in alphabetical order by key:
   ```html
   <link rel="stylesheet" href="v2s/marketing.css">
   <script src="v2s/marketing.js"></script>
   ```
2. `dashboard-cloud/index.html`, `renderView()`: **shared hook** (listed under shared_edits). Add one generic registry dispatch so that every section file can own modules without further edits. Use exactly these two lines; if another section already added them, add nothing.
   - In the `if(ap&&sh){…}` line, after the D3 `v2-bare` toggle, append:
     `if(window.V2SEC_OWNS&&V2SEC_OWNS(current))ap.classList.add('v2-bare');`
   - Right after the D3 render line (`if(window.V2_ON&&window.V2D3&&V2D3.owns(current))return V2D3.render(current,v);`), add:
     `if(window.V2_ON&&window.V2SEC_OWNS&&V2SEC_OWNS(current))return V2SEC_RENDER(current,v);`
   - `v2s/marketing.js` defines the registry defensively (first file wins, others reuse):
   ```js
   window.V2SEC = window.V2SEC || {};
   window.V2SEC_OWNS = window.V2SEC_OWNS || function (m) { for (var k in window.V2SEC) if (window.V2SEC[k] && window.V2SEC[k].owns(m)) return true; return false; };
   window.V2SEC_RENDER = window.V2SEC_RENDER || function (m, v) { for (var k in window.V2SEC) if (window.V2SEC[k] && window.V2SEC[k].owns(m)) return window.V2SEC[k].render(m, v); };
   window.V2SEC.marketing = { owns: …, render: …, cards: …, _state: S, _src: SRC, _tick: … };
   ```
   - With the flag off, `V2_ON` is false, so the hook never runs and the old `viewMarketing` is untouched.
3. `dashboard-cloud/v2-logic.js`: edit only the `marketing` entry in `SECTIONS` (§2). Pure helpers go at the end of the file in the block `// ===== v2s:marketing =====` … `// ===== /v2s:marketing =====` as a separate IIFE that attaches `V2L.mk = {…}` (works in the browser and in node, because `module.exports` is the same `api` object).
4. `backend/app.py`: one line right before `# ---- v2 section routes end`. If the marker is missing, create it after the last D3 v2 route (`/api/v2/book-requests/<request_id>` PATCH, ~line 2690):
   ```python
   __import__('v2_marketing_routes').register(app, globals())   # v2s:marketing
   ```
5. **The three Dockerfiles (shared edit).** No Dockerfile copies a whole folder. Each one copies an explicit list of files, so without these lines production would miss both `v2s/` and the route module:
   - `v2s/marketing.js` would return 404, `V2SEC` would be undefined, the hook would never run, and the old screen would come back in the old look;
   - `import v2_marketing_routes` in `app.py` would raise `ImportError` and take the whole dashboard server down.

   Add exactly these lines (identical in every section, so git merges cleanly; if another section added them already, add nothing):
   - **`Dockerfile` (repo root, the image used today)** and **`deploy/Dockerfile.coolify`**: after the line `COPY dashboard-cloud/v2/img /app/dist/v2/img`:
     ```
     COPY dashboard-cloud/v2s /app/dist/v2s
     COPY backend/v2_*_routes.py /app/
     ```
   - **`backend/Dockerfile`** (build context `backend/`): after `COPY app.py .`:
     ```
     COPY v2_*_routes.py ./
     ```
   - `serve_frontend` already serves nested paths (`v2/img/x.jpg`), so `v2s/marketing.js` is served with no code change.
   - Observation for the integrator, not ours to fix: `deploy/Dockerfile.coolify` does not copy `backend/refresh_rules.py`, which `app.py:19` imports at start. The root `Dockerfile` does.

The «التسويق» tile code in `v2Tiles` (`T.marketing.next = 'الحملات والسوشيال'`) is **not** ours to edit and stays as is.

---

## 2) Section entry (`SECTIONS` in v2-logic.js)

```js
{ key: 'marketing', label: 'التسويق', img: 'marketing', desc: 'الحملات من الإعلان حتى الدفع، والسوشيال، وخطة النشر', tabs: [
  T('campaigns', 'الحملات', 'marketing'),
  T('social', 'السوشيال ميديا', 'v2mk_social'),
  T('plan', 'خطة النشر', 'v2mk_plan')
] },
```

- **The first tab keeps the old module key `marketing`.** `V2SEC.marketing.owns('marketing')` is true, so with the flag on the new screen renders for `marketing`.
  - Every old link (`#marketing`, `go('marketing')`, Telegram links) lands on the new screen through the existing `sectionFor`, with no alias needed.
  - With the flag off, `viewMarketing` runs as today.
- `owns(mod)` ⇔ `mod ∈ {'marketing','v2mk_social','v2mk_plan'}`.
- The concept's «التقرير» tab is **postponed**, not moved. It has no source until attribution is connected (§9 P1), and a tab full of «غير متاح بعد» is worse than no tab.
  - «التسويق» does **not** link to «التقارير». The reports round's «التسويق» scope shows «غير متاح بعد» and links back here (`SPEC-reports.md §4.7`), so a link from here would send the founder round in a circle.
  - The direction is one way: «التقارير» links to «التسويق», never the reverse. When attribution is ready, the report tab is added in the round that connects «مدار».
- **No «كل السجلات» tab.** Every action of the old screen (list · add · edit · pause/run · delete · KPIs) is covered by the new «الحملات» tab (§4). Nothing remains uncovered.

Addresses: `#s/marketing` · `#s/marketing/campaigns` · `#s/marketing/social` · `#s/marketing/plan`.

---

## 3) Data sources (loaders in `v2s/marketing.js`)

These follow the D3 `SRC` pattern: `{state: idle|loading|ready|error|closed, data, status, seq}`, read with `EP.api(path)`.
- `closed` = HTTP 404.
- One call, no automatic retry; «أعد المحاولة» reloads.
- Redraw on signature change every 400 ms, and never while `#epModal` is open (D3 pattern). A minute tick refreshes «منذ …» texts.

| Key | Path (`EP.api`) | Feeds | Fields used | Failure ⇒ |
|---|---|---|---|---|
| `campaigns` | `GET /campaigns` (existing) | numbers 1·2·4, brain, table, detail, social per-platform lines | `id, name, platform, status, start_date, end_date, budget, spent, currency, clicks, leads, conversions, revenue_attributed, target_audience, notes` (the server's `roas/cac/recommendation` are **not** trusted for display; recomputed per currency in `V2L.mk`) | numbers 1·2·4 «غير متاح بعد»; table ⇒ unavailable block + «أعد المحاولة»; «حملة جديدة» disabled with the line «تعذّر جلب الحملات — أعد المحاولة أولًا حتى لا تتكرر حملة» |
| `owners` | `GET /v2/marketing/owners` (new, §8) | «لمن الحملة» on rows, in the detail and in the edit sheet; the old-currency strip (§4.2a) | `items[].campaign_id, owner_kind, owner_id, owner_title`, `legacy_max_id` | the owner line is hidden; the detail sheet shows «غير متاح بعد» next to «لمن الحملة»; the edit sheet locks «لمن الحملة» (§5.2); the old-currency strip is not shown |
| `income` | `GET /v2/income/by-service?month=YYYY-MM` (existing D3) | the note under number 3 | `services[].totals[] {currency, amount}` summed **per currency** with `V2L.util.sumByCurrency` | the note line is dropped (number 3 is «غير متاح بعد» anyway) |
| `ads` | `GET /v2/ads-ledger` (existing D3) | the line «أعمال لها رصيد إعلانات» under the table (§4.6); owner choices in the edit sheet | `items[].owner_kind, owner_id, title, balance[] {currency, amount}, last_entry_at` | the line reads «أرصدة إعلانات الأعمال: غير متاح بعد»; the owner select follows §5.2 «when `ads` is not ready» (it never offers a choice that would overwrite a stored owner) |
| `published` | `GET /v2/marketing/published?days=7` (new, §8) | «خطة النشر»: published this week + drafts count | `items[] {id, title, published_at}`, `drafts` | unavailable block «مقالات الموقع: غير متاح بعد» |
| `attribution` | `GET /v2/marketing/attribution?month=YYYY-MM` (new proxy, §8 ⇒ Platform need P1) | number 3, the «بلا إعلان» table row, the «عبر الرابط» column, «جاء عبر الرابط» in the detail, the «العقل يحتاج» lines | §9 P1 shape | `closed` (404 = the platform has no bridge yet) or `error` ⇒ everything that depends on it shows «غير متاح بعد», the «عبر الرابط» column is not drawn, and the need stays in «العقل يحتاج» |
| ops queue | `EP.data.opsQueue` (already loaded by the shell; `EP.ensure('opsQueue')`) | not used here, so no duplicate counting | — | — |

**Loaded per tab:**
- «الحملات»: campaigns, owners, income, ads, attribution.
- «السوشيال ميديا»: campaigns.
- «خطة النشر»: published.

---

## 4) Tab «الحملات» (`marketing`, default)

### 4.1 Layout

**One main button on the screen.** Only one `.v3-btn1` is visible at any time:
- normally it is the brain strip's button (§4.3);
- when the brain is `none` (no button), the top bar's «حملة جديدة» becomes `.v3-btn1`;
- when the brain is `empty`, its button *is* «حملة جديدة», so the top bar button is hidden.

Everything else is `.v3-btn2` or a text link `.v3-link`. There are no explanation boxes and no link cards on this tab.

- **Desktop ≥1180** (inside the D1-B shell content area, max width as other v2 screens), top to bottom:
  1. Top bar (`.v3-top`):
     - segmented control `.v3-seg`: «النشطة الآن» (default) | «كل الحملات»;
     - on the inline end, «حملة جديدة» as `.v3-btn2` (see the rule above).
     - Under the bar, one `.v3-ptxt` line: «أرقام الحملات منذ بدايتها كما سُجّلت، ودخل المنصة بالشهر. لا يصل إلى هنا شيء من حسابات الإعلانات قبل ربط «مدار».»
  2. The old-currency strip, only when it applies (§4.2a).
  3. Four numbers `.v3-nums` (4 columns), §4.2.
  4. The brain strip `.mk-brainstrip`, full width, directly under the numbers (§4.3).
  5. Card «الحملات: من الإعلان حتى الدفع» (§4.5), which ends with:
     - the ads-balances line with its two text links (§4.6);
     - the tail `.mk-tail`: «العقل يرى من» chips and the compact «العقل يحتاج» lines with one link (§4.4).
- **Tablet 761–1179:**
  - numbers 2×2;
  - the brain strip keeps the photo and the sentence on one row, and its two buttons move to a second row (each ≥44 px);
  - the table becomes compact, §4.5.
- **Mobile ≤760:**
  - one column;
  - the segmented control is full width, with 52 px segments;
  - «حملة جديدة», when shown, is full width at 52 px, under the segmented control;
  - numbers in one column;
  - the brain strip stacks: photo and sentence, then the main button full width at 52 px, then «بعدين» full width at 52 px;
  - the table becomes cards (§4.5);
  - every button ≥52 px;
  - no horizontal page scroll at 390.

### 4.2 The four numbers (pure helper `V2L.mk.board(campaigns, filter, extra)`)

Filter: «النشطة الآن» = `status === 'active'`; «كل الحملات» = all rows.
- Sums are **per currency**, never mixed and never converted.
- Each number picks its **primary currency** the same way: EGP if its own sums contain EGP, otherwise the currency with the largest amount.
- Other currencies show as a chip `.v3-oth`: «وبعملة أخرى: ٣٠٠ ر.س».
- **Every note line names its period**, because the campaign rows have no monthly split while platform income is monthly. Numbers 1, 2 and 4 cover each campaign since it started; number 3 covers this month. The two periods are never added or compared in one sentence.

| # | Label | Value | Note line (`.v3-note`) | No data |
|---|---|---|---|---|
| 1 | «صُرف على الإعلانات» | Σ `spent` (primary currency) | «{N} حملات نشطة · منذ بداية كل حملة» via `U(n,['حملة واحدة نشطة','حملتان نشطتان','حملات نشطة','حملة نشطة'])`, or with «كل الحملات»: «من {N} حملات مسجّلة · منذ بداية كل حملة» | 0 rows ⇒ value «لا حملات مسجّلة» (class `na`), never «٠» |
| 2 | «دخل جاء من الإعلانات» | Σ `revenue_attributed` (primary) | Σspent>0 and Σrev>0 in the same currency: «كل {unit} رجع {r} · منذ بداية كل حملة» (`r` = Σrev/Σspent, one decimal, Arabic digits «٣٫٧»; unit: EGP «جنيه», SAR «ريال», USD «دولار», else «وحدة»). Σspent=0: «كما سُجّل في كل حملة منذ بدايتها». | 0 rows ⇒ «لا حملات مسجّلة». Σspent>0 and Σrev=0 ⇒ value **«لم يُسجَّل دخل بعد»** (class `na`, never «٠») and note «منذ بداية كل حملة» |
| 3 | «دخل جاء بلا إعلانات» | attribution ready ⇒ Σ totals of every `channels[]` row with `paid:false` (the `untracked` block is never counted), primary currency, current month | ready: «هذا الشهر، منذ بدء التسجيل في {date(captured_since)}: من البحث والسوشيال والدعوات والدخول المباشر». Not ready: «هذا الشهر: المنصة لا تسجّل بعد من أين جاء كل دافع.» plus, when `income` is ready: «دخل المنصة كله هذا الشهر: {money line}، ولا نعرف بعد كم منه جاء من إعلان.» | not ready ⇒ value **«غير متاح بعد»** (class `na`). No link on the number: the need is listed in the campaign card's tail (§4.4). |
| 4 | «كلفة العميل الواحد» | Σspent ÷ Σconversions over rows with `conversions>0` only (primary currency), rounded to whole units | «من الحملات التي سُجّل لها من دفع، منذ بدايتها» | no row with conversions>0 ⇒ «غير متاح بعد» + note «لم يُسجَّل بعد من دفع عن طريق حملة» |

Campaigns source failed ⇒ numbers 1, 2 and 4 show «غير متاح بعد» with the note «تعذّر جلب الحملات». Top strip `.v3-warn`: «تعذّر جلب: الحملات — ما يظهر ناقص، وليس معناه أنه لا شيء» + «أعد المحاولة».

A real monthly split for numbers 1, 2 and 4 needs daily spend, which arrives with «مدار» (`month_spent`). It is not built now.

### 4.2a The old-currency strip (pure helper `V2L.mk.legacyUsd(rows, legacyMaxId)`)

**Why:** the old screen never sent `currency`, so every campaign it saved is stored as «دولار» although the founder typed pounds (§0 Trap 1). Shown as stored, the four numbers would read «دولار» on pound amounts.

**Which rows:** `legacyUsd` returns the rows with `currency === 'USD'` and `id ≤ legacyMaxId`.
- `legacyMaxId` comes from `GET /v2/marketing/owners` (§8). It is the highest campaign id that existed when the new screen first ran, so rows saved later from the new sheet (where the currency is chosen on purpose) are never flagged.
- `legacyMaxId` is 0 after the founder confirms «هي بالدولار فعلًا», so the strip never returns.
- `owners` not ready ⇒ no strip.

**Strip** (`.v3-warn`, above the numbers, only when the list is not empty):
- Text: «{N} حملات سُجّلت من الشاشة القديمة، وكانت تلك الشاشة تحفظ كل حملة بعملة «دولار» مهما كُتب.» (with `U` for the count).
- Button `.v3-btn2` «راجع العملة» ⇒ sheet «عملة الحملات القديمة».

**Sheet «عملة الحملات القديمة»:**
- Lead: «هذه الحملات محفوظة بعملة «دولار». لا يُحوَّل أي رقم؛ تتغيّر العملة فقط.»
- The list: each name with its stored `spent` and `budget` numbers (as plain digits, no currency word).
- Buttons:
  - main «اجعلها كلها بالجنيه» (`.btn.btn-primary`) ⇒ `PUT /campaigns/{id}` `{currency:'EGP'}` for each row, one after another (a record edit; no money moves). When done, reload `campaigns` and show `.v3-ok` «تم: {N} حملات صارت بالجنيه». If some fail, the sheet stays open and lists them: «تعذّر تعديل: {names} — أعد المحاولة».
  - «هي بالدولار فعلًا» (`.btn`) ⇒ `POST /v2/marketing/legacy-checked` (§8) ⇒ reload `owners`; the strip disappears for good.
  - «سأراجعها واحدة واحدة» (`.btn`) ⇒ closes the sheet and hides the strip for this browser session (`sessionStorage['mk_legacy_later']`, try/catch). Each campaign can then be corrected from «عدّل الحملة».
- While busy, the sheet is locked (`dataset.busy`) and nothing is sent twice.

### 4.3 The brain strip «العقل يقترح» (pure helper `V2L.mk.brain(campaigns, today, skipped)`)

**Look (as in the approved concept, `Marketing.dc.html`):** `.mk-brainstrip` is full width, directly under the numbers.
- Background ink `#21262E`, text white, radius 22 px, padding 14–18 px, items in one row (`gap:16px`, centred).
- The photo `v2/img/brain-avatar.jpg`, 50 px round, with a 2 px wine `#9E2B4E` border.
- The text block: a small muted label «العقل يقترح» (plus «· اقتراح {i} من {n}» when n>1), the sentence, and the suggestion line under it.
- The single main button `.v3-btn1` (wine on ink).
- «بعدين»: transparent, white text, 1 px white border at 40 % opacity.
- This is the only main button on the tab (§4.1). The headline never starts with «الذكاء».

**Behaviour:**
- There is one suggestion at a time.
- «بعدين» hides that suggestion for this browser session and shows the next one: `sessionStorage['mk_later_'+kind+'_'+id]`, every access wrapped in try/catch; if storage fails, the hide lasts until reload. There is no «التالي» link.
- Facts only: every number in the text comes from the row itself.
- Only rows in the **active** filter count (independent of the segmented control).
- Ties: larger `spent` first.

**Maturity rule (for `losing` and `no_results` only).** A row is *mature* when both hold:
- `start_date` is empty, or `start_date ≤ today − 7 days`;
- `budget ≤ 0`, or `spent ≥ 25 %` of `budget`.

A row that is not mature never enters `losing` or `no_results`. Results are typed by hand days later, so a young campaign with no income is not a finding.

| Priority | `kind` | Condition (all from the campaign row) | Text (exact) | Main button ⇒ action |
|---|---|---|---|---|
| 1 | `ended` | `status==='active'` and `end_date` < today | «حملة «{name}» انتهى موعدها في {dateText(end_date)} وما زالت «نشطة» هنا.» / suggestion line: «أقترح تسجيلها منتهية.» | «سجّلها منتهية» ⇒ confirm sheet ⇒ `EP.api('/campaigns/'+id,{method:'PUT',body:{status:'completed'}})` |
| 2 | `losing` | active, mature, `spent>0`, **not** `noResults` (at least one of clicks/leads/conversions/revenue > 0), `revenue_attributed < spent` (same row, one currency) | rev>0: «حملة «{name}» صُرف عليها {money(spent)} وسُجّل لها دخل {money(rev)}: كل {unit} رجع {r}.» rev=0: «حملة «{name}» صُرف عليها {money(spent)} ولم يُسجَّل لها دخل بعد.» / «أقترح إيقافها.» | «أوقفها» ⇒ confirm sheet ⇒ `PUT /campaigns/{id}` `{status:'paused'}` |
| 3 | `no_results` | active, mature, `spent>0`, and `clicks`, `leads`, `conversions`, `revenue_attributed` all 0 | «حملة «{name}» صُرف عليها {money(spent)} ولم تُسجَّل لها أي نتيجة بعد.» / «أقترح نقل نتائجها من حساب الإعلانات.» | «سجّل النتائج» ⇒ opens the edit sheet (§5.2) on that campaign |
| 4 | `over_budget` | active, `budget>0`, `spent>budget` | «حملة «{name}» صُرف عليها {money(spent)} وميزانيتها {money(budget)}.» / «راجع الميزانية أو أوقفها.» | «عدّل الحملة» ⇒ edit sheet |
| 5 | `best` (info) | none of the above; best active row with `spent>0` and ratio ≥ 3 | «أفضل حملة الآن «{name}»: كل {unit} رجع {r}.» | «افتح الحملة» ⇒ detail sheet (§5.1); no «بعدين» |
| — | `empty` | no campaigns at all (source ready) | «لا حملات مسجّلة. سجّل أول حملة لأرى ما صُرف وما جاء.» | «حملة جديدة» ⇒ create sheet |
| — | `young` | rows exist, nothing applies, and at least one active row with `spent>0` was left out only by the maturity rule | «الحملات الجديدة ما زالت في أيامها الأولى، فلا اقتراح عليها الآن.» | no button |
| — | `none` | rows exist, nothing applies | «لا اقتراح الآن. الحملات النشطة تسير كما سُجّلت.» | no button |

Note: without the «not `noResults`» condition, every `no_results` row would also satisfy `losing` (revenue 0 < spent) and `no_results` could never appear. The condition keeps the two apart.

**Confirm sheets for «أوقفها» and «سجّلها منتهية»:**
- Title: «إيقاف حملة» / «تسجيل حملة منتهية».
- Lead: «ستصبح حملة «{name}» {موقوفة|منتهية} في سجلّ الحملات هنا.»
- Warning line `.v3-warn`: «هذا لا يوقف الإعلان نفسه. أوقفه من حساب الإعلانات حتى يُربط «مدار».»
- Buttons: «أكّد» (`.btn.btn-primary`) and «إلغاء».
- On success: close the sheet, reload `campaigns`, and show `.v3-ok` «تم: حملة «{name}» {أُوقفت|سُجّلت منتهية}».
- On failure: the sheet stays open with `.v3-err` showing the server's message, or «تعذّر الحفظ — أعد المحاولة».

These are record edits and move no money. They still go through the confirmation sheet, but `confirmed` is not required by `/api/campaigns`, so no flag is sent.

### 4.4 «العقل يرى من» + «العقل يحتاج» (pure helper `V2L.mk.sources(states)` ⇒ `{seen[], needs[], failed[]}`)

Both live in the tail of the campaigns card (`.mk-tail`, top border `var(--line)`, 14 px padding), as in the concept. They are small and quiet; the eye stays on the brain strip.

**«العقل يرى من»:** one row of small chips (`.mk-src`, 32 px tall, not clickable), each with a dot:
- green when its state is `ready`;
- grey when it is not connected by design;
- amber when the state is `error`.

| Chip label | Connected when |
|---|---|
| «الحملات المسجّلة هنا» | `campaigns` ready |
| «دخل المنصة» | `income` ready |
| «أرصدة إعلانات أصحاب الأعمال» | `ads` ready |
| «من أين جاء كل شخص» | `attribution` ready |
| «إعلانات ميتا» | never this round (via «مدار») |
| «إعلانات جوجل» | never this round |
| «صفحات السوشيال» | never this round |
| «زيارات الموقع» | never this round |

When any chip is amber, one `.v3-link` «أعد المحاولة» follows the chips and reloads every failed source. Failed-but-existing sources (`campaigns`, `income`, `ads`) are **not** needs.

**«العقل يحتاج:»** one compact line (`.mk-need`, no button) per source that is not connected, in this order: title · a short «لماذا» · a status chip.

| Need | Short «لماذا» | Status chip |
|---|---|---|
| «من أين جاء كل شخص يسجّل أو يدفع» | «لأعرف كم من الدخل جاء بلا إعلان» | «يحتاج تعديلًا في المنصة» |
| «نتائج إعلانات ميتا وجوجل» | «لأرى نتيجة كل حملة دون كتابتها» | «يأتي مع ربط «مدار»» |
| «أرقام صفحات السوشيال» | «لأعرف أي منصة تجلب الناس» | «يأتي مع ربط «مدار»» |
| «زيارات الموقع» | «لأعرف كم زائرًا صار عميلًا» | «يحتاج تعديلًا في الموقع» |

Under the lines, one `.v3-link` «كيف تُربط هذه المصادر؟» opens **one** sheet, «كيف تُربط هذه المصادر», with a short heading and paragraph per open need (informational only; it never pretends to connect anything; single button «تمام»):
- «من أين جاء كل شخص»: «تحفظ المنصة عند أول زيارة من أين جاء الزائر (إعلان، بحث، سوشيال، دعوة)، وتربطه بحسابه وبكل دفعة. بعدها يظهر هنا الدخل بلا إعلان، ونتيجة كل حملة حتى الدفع.»
- «نتائج إعلانات ميتا وجوجل»: «يجلب «مدار» نتائج الحملات يومًا بيوم من حسابات الإعلانات. إلى أن يُربط، سجّل أرقام كل حملة من زر «عدّل الحملة».»
- «أرقام صفحات السوشيال»: «يجلب «مدار» المتابعين والوصول وأفضل منشور لكل منصة.»
- «زيارات الموقع»: «يُضاف عدّاد زيارات للموقع والمنصة يحترم اختيار الكوكيز، ويصل رقمه إلى هنا وإلى «التقارير».»

This link is the only way into the sheet; no «كيف يُربط؟» button exists anywhere in the section.

### 4.5 Table «الحملات: من الإعلان حتى الدفع» (pure helper `V2L.mk.rows(campaigns, owners, filter, attribution)`)

Card header: «الحملات: من الإعلان حتى الدفع»; hint «اضغط أي حملة لتفاصيلها وأزرارها».

Sort: active first, then `spent` descending, then name.

**Two kinds of numbers, never mixed.** The typed numbers are what the founder recorded in each campaign since it started. The platform numbers are what the platform counted this month for people who came through the campaign's link. They sit in different columns with different labels and colours.

**Desktop columns** (`<table class="mk-table">`, numeric cells aligned to the inline end, Arabic digits):
- «الحملة»: name, plus a small line with the owner: «لـ{owner_title}» or «للبروفيسور»;
- «المنصة»: label map `facebook`⇒«فيسبوك», `instagram`⇒«إنستجرام», `facebook_instagram`⇒«فيسبوك وإنستجرام», `google_ads`⇒«جوجل», `linkedin`⇒«لينكدإن», `youtube`⇒«يوتيوب», `tiktok`⇒«تيك توك», anything else shown as stored;
- «الحالة»: chip «نشطة» (green) / «موقوفة» (grey) / «انتهت» (ink outline) / «مسودة» (paper);
- «صُرف»: `moneyText(spent, currency)`;
- «زيارات»: `clicks`;
- «سجّلوا»: `leads`, with a small second header line «كما سُجّل» and `title="الرقم كما كتبته في الحملة"`;
- «دفعوا»: `conversions`, with the same second line «كما سُجّل» and the same `title`;
- «الدخل»: `moneyText(revenue_attributed, currency)`;
- «رجع»: ratio «٥٫٢», or «—» when `spent=0`. The ratio is coloured red (`#C8102E`) when < 1 and green when ≥ 3;
- **«عبر الرابط»** (only when attribution is ready): header with the small second line «من المنصة · هذا الشهر»; cells on a paper background `#F6F1EA`; value «سجّلوا {s} · دفعوا {p}» from `attribution.campaigns[]` where `campaign === 'c'+id`, or «—» when the campaign has no entry. When attribution is not ready, the column is not drawn at all.

Rows with `spent>0` and all four result fields 0 show the chip «لم تُسجَّل نتائج» in place of the four typed numbers (cells merged), so they never read as a real zero.

Every row is a `<button>`-like row (`role="button"`, `tabindex=0`, min height 52 px, Enter/Space) ⇒ detail sheet (§5.1).

**Last row «بلا إعلان»** (always shown, styled `.mk-organic` on paper):
- name «بلا إعلان», sub «من المنصة · هذا الشهر · البحث والسوشيال والدعوات والدخول المباشر».
- If attribution is not ready, the merged cells read: «غير متاح بعد — المنصة لا تسجّل بعد من أين جاء كل دافع».
- If it is ready: «سجّلوا» = Σ `signups` and «دفعوا» = Σ `paid_people` of the `paid:false` channel rows (the `untracked` block excluded); «الدخل» = the money line per currency; «رجع» = «بلا صرف». The sub line already says these are platform numbers for this month.

- **Tablet 761–1179:** the columns are «الحملة» (with platform and status folded into its sub line) · «صُرف» · «سجّلوا» · «دفعوا» · «الدخل» · «رجع». When attribution is ready, the platform numbers move under the name as a paper chip `.mk-via`: «عبر الرابط هذا الشهر: سجّلوا {s} · دفعوا {p}».
- **Mobile ≤760:** one card per campaign (`.mk-ccard`):
  - name + status chip;
  - owner/platform line;
  - a 3×2 mini grid: صُرف · زيارات · سجّلوا · دفعوا · الدخل · رجع (these are the typed numbers);
  - when attribution is ready, a separate paper row at the bottom of the card: «عبر الرابط هذا الشهر: سجّلوا {s} · دفعوا {p}»;
  - the whole card is the tap target.
  - «بلا إعلان» is the last card.

**Empty and failure states:**
- Empty with «النشطة الآن»: «لا حملات نشطة الآن.» plus the link «اعرض كل الحملات».
- Empty with «كل الحملات»: `.v3-empty` «لا حملات مسجّلة بعد» (the brain strip carries «حملة جديدة», §4.1).
- Loading: `.v3-empty` «…جارٍ جلب الحملات».
- Failed: «الحملات: غير متاح بعد» / «تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.» + «أعد المحاولة».

### 4.6 The ads-balances line (inside the campaigns card, above the tail)

The concept has no link cards, so there are none. One line (`.mk-adsline`, source `ads`) sits under the table:
- Ready with items: «{N} أعمال لها رصيد إعلانات عندنا: {money line}» (with `U`; the balance per currency via `V2L.v2MoneyLine`; never one summed number across currencies).
- Ready and empty: «لا أعمال لها رصيد إعلانات بعد».
- Failed: «أرصدة إعلانات الأعمال: غير متاح بعد» (the retry is the single «أعد المحاولة» of §4.4).
- Followed in every state by two text links `.v3-link`:
  - «إعلانات الأعمال» ⇒ `V2_HOST.openSection('money','ads')` (tab `ads` exists in `SECTIONS.money`);
  - «عملاء الإعلانات» ⇒ `V2_HOST.openSection('company','ads')` (the company round names this tab `T('ads','عملاء الإعلانات','v2c_ads')`, `SPEC-company.md:33`).

The «اربط مدار» photo card appears **once**, at the top of the social tab (§6). Its sheet «بعد ربط مدار» (opened by «ماذا سيظهر هنا؟») is one shared sheet:
- title «بعد ربط مدار», a list of what will appear (no numbers):
  - «نتائج إعلانات ميتا وجوجل لكل حملة يومًا بيوم»
  - «أرقام صفحات فيسبوك وإنستجرام ولينكدإن ويوتيوب وتيك توك»
  - «خطة النشر الأسبوعية وما ينتظر موافقتك»
  - «كشف «صُرف كم وجاء بماذا» لكل صاحب حملة»
- single button «تمام».

---

## 5) Sheets (all through `window.openModal`, wrapped in `.v3m` like D3; ≥44 px targets, 52 px on mobile; never redrawn under an open sheet)

### 5.1 Campaign detail — title «حملة: {name}»
- **Lines:**
  - «المنصة»;
  - «الحالة»;
  - «المدة» («من {start} إلى {end}» / «من {start} حتى الآن» / «بلا تاريخ»);
  - «لمن الحملة» (owner, or «البروفيسور نفسه»; owners failed ⇒ «غير متاح بعد»);
  - «الجمهور» (if any).
- **Numbers grid**, headed «كما سُجّل منذ بداية الحملة»: «الميزانية» · «صُرف» · «زيارات» · «سجّلوا» · «دفعوا» · «الدخل» · «رجع», each with the row currency.
- **«الرابط الذي تضعه في الإعلان»:**
  - a read-only field with `https://elprofessor.net/?utm_source={src}&utm_medium=paid&utm_campaign=c{id}`, where `src` follows the platform: `facebook`⇒`facebook`, `instagram`⇒`instagram`, `facebook_instagram`⇒`meta`, `google_ads`⇒`google`, `linkedin`/`youtube`/`tiktok` as is, anything else ⇒ `other`. These values match the reports round's `channel_of` (`meta` and `google` are recognised by `utm_source`; the rest land in `other`), and `utm_medium=paid` marks the visit as paid (§9 P1);
  - the button «انسخ الرابط» (`navigator.clipboard.writeText`; fallback: select the field text; toast «نُسخ الرابط»).
  - Under it, when attribution is not ready: «سيُحتسب من جاء عبر هذا الرابط حين تبدأ المنصة تسجيل مصدر كل زائر.»
  - When attribution is ready, on a paper background and labelled «من المنصة»: «جاء عبره هذا الشهر: سجّلوا {s} · دفعوا {p} · دخل {money line}», or «لم يأتِ عبره أحد هذا الشهر».
- **Actions** (`.acts`):
  - main «عدّل الحملة» ⇒ §5.2;
  - «أوقفها» / «شغّلها» (status active ⇄ paused; for `completed`/`draft` the button reads «شغّلها»), via the same confirm sheet as §4.3 (for «شغّلها» the warning reads «هذا لا يشغّل الإعلان نفسه…»);
  - «انسخ الكشف» ⇒ copies the statement (§5.4);
  - «احذف» (`.btn-warn`, last) ⇒ §5.3.

### 5.2 Create / edit — title «حملة جديدة» / «تعديل: {name}»
One stage, with fields in pairs (`.row2`) on desktop/tablet and one column on mobile:
- «اسم الحملة» (required, ≤255; empty ⇒ «اكتب اسم الحملة»).
- «لمن الحملة»: select with «البروفيسور نفسه» first, then each `ads` item as «{title} — {دورة|كتاب}». Untitled items show «عمل بلا عنوان ({owner_id})».
  - **The loaded owner is always the preselected value.** On edit, the select starts at the owner stored in `owners` for this campaign (or «البروفيسور نفسه» when there is none). If that owner is not in the `ads` list (for example its balance row was removed), it is added as an extra option «{owner_title} — الحالي», so it is never silently replaced.
  - **When `ads` is not ready** (loading, failed or closed):
    - campaign with a stored course/book owner ⇒ the select is **disabled**, with the single option «{owner_title} — الحالي» and the hint «قائمة الأعمال غير متاحة الآن، فلا يمكن تغيير صاحب الحملة»;
    - campaign without an owner, or a new campaign ⇒ the select is disabled with the single option «البروفيسور نفسه» and the same hint.
  - **When `owners` is not ready** on edit ⇒ the select is disabled with the hint «صاحب الحملة غير متاح الآن، فلا يمكن تغييره»; the campaign fields can still be saved.
- «المنصة»: select with «فيسبوك وإنستجرام» (`facebook_instagram`) · «فيسبوك» · «إنستجرام» · «جوجل» (`google_ads`) · «لينكدإن» · «يوتيوب» · «تيك توك» · **«أخرى»**. «أخرى» reveals a text box «اسم المنصة» (required when chosen; stored as typed). This follows the always-«أخرى» rule.
- «العملة»: «جنيه مصري» (EGP, default for new) · «ريال سعودي» (SAR) · «دولار» (USD) · «أخرى» ⇒ a 3-letter code box. On edit, the stored value is preselected; a stored USD row shows as «دولار» so the founder can see and correct it.
- «الحالة»: «نشطة» · «موقوفة» · «انتهت» · «مسودة».
- «تاريخ البدء» / «تاريخ النهاية» (`type=date`; the end must not be before the start ⇒ «تاريخ النهاية قبل البدء»).
- «الميزانية» / «صُرف».
- «الزيارات (النقرات على الإعلان)» / «سجّلوا».
- «دفعوا» / «الدخل الذي جاء منها».
- «الجمهور» (free text ≤500).

Number boxes accept Arabic or Latin digits (`V2L.util.parseAmount`); negative ⇒ «الأرقام لا تكون سالبة». Counts are whole numbers.

**Save:**
- **Create:** `EP.api('/campaigns',{method:'POST',body})` (existing endpoint). The body is whitelisted: `{name, platform, status, start_date?, end_date?, budget, spent, currency, impressions:0, clicks, leads, conversions, revenue_attributed, target_audience}`.
- **Edit:** `EP.api('/campaigns/'+id,{method:'PUT',body})` with the same keys minus `impressions`. `PUT` does not clear dates; to clear a date, leave the field as it was. The sheet notes «لا يمكن مسح التاريخ بعد حفظه، غيّره فقط».
- **Owner:** the second call `PUT /v2/marketing/campaigns/{id}/owner` (§8) runs after the campaign call succeeds **only** when the chosen value differs from the value loaded from `owners` (on create: only when it is not «البروفيسور نفسه»). A disabled select never sends it. `V2L.mk.validate(form, loadedOwner)` returns `ownerChanged:true` only in that case.
  - On create, `id` comes from the POST reply `{id}`.
  - If the owner call fails, the campaign stays saved and the note says «حُفظت الحملة، وتعذّر حفظ صاحبها — أعد المحاولة من «عدّل الحملة»».
- **Buttons:** «احفظ» (or «أنشئ الحملة») and «إلغاء». While busy, the sheet is locked (`dataset.busy`), the label is «جارٍ الحفظ…», and nothing is sent twice.
- **Result:** success ⇒ close, reload `campaigns` + `owners`, `.v3-ok` «حُفظت حملة «{name}»». Failure ⇒ `.v3-err` with the server message.

### 5.3 Delete — title «حذف حملة»
- Lead: «ستُحذف حملة «{name}» وأرقامها من السجل نهائيًا.» Warning: «لا يمكن التراجع.»
- Buttons: «احذف نهائيًا» (`.btn-warn`) and «إلغاء».
- Action: `EP.api('/campaigns/'+id,{method:'DELETE'})` (existing).
- Success ⇒ reload and show «حُذفت حملة «{name}»». The owner link row stays orphaned in SQLite but is filtered out by `GET /v2/marketing/owners` (§8).

### 5.4 «انسخ الكشف» (pure helper `V2L.mk.statement(c, owner, today)`)
Plain text. A line is skipped when its field is empty; zeros stay, because they are recorded values.
```
كشف حملة «{name}» — {لـ{owner_title} | للبروفيسور}
المنصة: {platform label} · {المدة}
صُرف: {spent} من ميزانية {budget}
زيارات: {clicks} · سجّلوا: {leads} · دفعوا: {conversions}
الدخل المسجّل: {revenue}
الأرقام كما سُجّلت في لوحة البروفيسور بتاريخ {dateText(today)}.
```
Toast: «نُسخ الكشف — أرسله لصاحب الحملة». **Nothing is sent automatically.** Sending the statement to the owner is the platform's job later, with «مدار» (out of scope).

---

## 6) Tab «السوشيال ميديا» (`v2mk_social`)

**One button on the whole tab:** «ماذا سيظهر هنا؟» in the «اربط مدار» card. The platform cards have no buttons and no explanation boxes. Each card leads with the facts we do have; what is missing is one small line.

- **Top: the «اربط مدار» card** (`.mk-madar`, the only place the photo card appears in the section):
  - wide form: the photo `v2/img/marketing.jpg` at the inline start (`object-fit:cover`, 16:9 on mobile where it stacks on top), text and button at the end;
  - text: «مدار هو نظام التسويق الذي سيجلب إلى هنا نتائج الإعلانات وأرقام الصفحات وخطة النشر، فلا تكتبها بيدك. الربط في جولة قادمة.»;
  - status chip «قريبًا»;
  - the single button `.v3-btn2` «ماذا سيظهر هنا؟» ⇒ the shared sheet «بعد ربط مدار» (§4.6).
- **Grid** `.mk-social` (desktop 3 columns, tablet 2, mobile 1) with five cards in this order: «فيسبوك» · «إنستجرام» · «لينكدإن» · «يوتيوب» · «تيك توك». Each card (pure helper `V2L.mk.byPlatform(campaigns)`) has:
  - a round letter mark («ف», «إ», «ل», «ي», «ت») in brand wine on paper, plus the name;
  - **the big line = what was spent there**, from the typed campaigns: Σ `spent` in the primary currency (EGP if present, otherwise the largest), other currencies as a `.v3-oth` chip; small caption «صُرف على حملاتها منذ بداية كل حملة»;
  - under it, one fact line: «{N} حملات · دفعوا {conversions} · كل {unit} رجع {r}». The ratio part is shown only when spent>0 and revenue>0; when spent>0 and revenue=0 it reads «لم يُسجَّل دخل بعد» instead;
  - `facebook_instagram` rows count for both cards and are marked «(مشتركة مع إنستجرام)» / «(مشتركة مع فيسبوك)»;
  - no rows ⇒ the big line is «لا حملات مسجّلة على هذه المنصة» (class `na`, never «٠»);
  - campaigns failed ⇒ the big line is «غير متاح بعد» with the caption «تعذّر جلب الحملات», and one `.v3-warn` strip above the grid with «أعد المحاولة»;
  - the last line, small and muted: «المتابعون والوصول: غير متاح بعد».
- There is no «العقل يحتاج» block on this tab. The needs live once, in the campaigns tab (§4.4).

---

## 7) Tab «خطة النشر» (`v2mk_plan`)

- **Layout:** `.v3-two` on desktop (start: site articles; end: «مدار» plan card); stacked on tablet and mobile.
- **Card «نُشر على الموقع هذا الأسبوع»** (source `published`):
  - The list `.v3-list`, newest first: title, «{dateText(published_at)} · {agoText}», and the link button «افتح على الموقع». The link is `https://elprofessor.net/article.html?id={id}` in a new tab with `noopener`, the same pattern as the content screen (`index.html:4684`).
  - Empty: «لم يُنشر مقال على الموقع في آخر ٧ أيام.»
  - Under the list, the drafts line: «مسودات مقالات لم تُنشر بعد: {drafts}» (shown only when `drafts>0`), with the button «افتح المحتوى» ⇒ `V2_HOST.openSection('content')`. Approving and publishing stay in «المحتوى»; nothing is duplicated here.
  - Failed: «مقالات الموقع: غير متاح بعد» + «أعد المحاولة».
- **Card «خطة النشر على السوشيال»:**
  - A plain card without the photo (the photo card lives once, in the social tab): «تُجهَّز خطة الأسبوع لكل منصة، وتنتظر موافقتك قبل النشر، بعد ربط «مدار».» + chip «قريبًا» + the text link `.v3-link` «ماذا سيظهر هنا؟» ⇒ the same shared sheet «بعد ربط مدار» (§4.6).
  - No placeholder rows, no fake days.

---

## 8) New server routes — `backend/v2_marketing_routes.py`

`register(app, env)` takes everything from `env` (the `globals()` of app.py), which avoids a circular import:
`token_required, roles_required, _v2_closed, _v2_ns, _v2_get, _v2_body, _audit, _actor_email, V2_ID_RE, V2_MONTH_RE, db, Article, Campaign, jsonify, request`.

Every route:
- is `@token_required` + `@roles_required('admin')`;
- calls `_v2_closed()` first (flag off ⇒ 404 with no DB write and no platform call);
- returns `Cache-Control: no-store` via `_v2_ns`;
- reads the actor from the token only; any `by` in the body is ignored.

| Route | Behaviour |
|---|---|
| `GET /api/v2/marketing/published?days=7` | `days` int 1–31 (default 7; anything else ⇒ 400 «المدة غير صالحة»). Local `Article` rows with `status=='published'` and `published_at >= utcnow − days`, newest first, max 50. ⇒ `{ok:true, days, since:ISO, items:[{id, title, published_at:ISO}], drafts:<count of Article status=='draft'>}`. No network. |
| `GET /api/v2/marketing/owners` | Ensures the tables (below). Rows whose `campaign_id` still exists in `campaigns` ⇒ `{ok:true, items:[{campaign_id, owner_kind, owner_id, owner_title, updated_at, updated_by}], legacy_max_id:<int>}`. `legacy_max_id` = the stored meta value `legacy_max_campaign_id` (written once, by the first `_ensure()` that finds it missing, as `COALESCE(MAX(campaigns.id),0)`), or 0 when `legacy_checked` is set. |
| `POST /api/v2/marketing/legacy-checked` | No body needed. Sets meta `legacy_checked='1'` (idempotent) and `_audit('marketing.legacy_currency_checked')` on success only. ⇒ `{ok:true}`. Used by «هي بالدولار فعلًا» (§4.2a). |
| `PUT /api/v2/marketing/campaigns/<int:cid>/owner` | Body `{owner_kind, owner_id?, owner_title?}`. `owner_kind ∈ {'platform','course','book'}`, else 400 «اختر صاحب الحملة». For `platform`, id/title are stored empty. For course/book: `owner_id` must match `V2_ID_RE` (else 400 «العمل غير صالح»), and `owner_title` is trimmed to ≤200. Unknown campaign ⇒ 404 «الحملة غير موجودة». Upsert, `updated_by=_actor_email()`, `updated_at=utcnow ISO`; `_audit('marketing.campaign_owner', target='campaign:{cid}', meta={owner_kind, owner_id})` **on success only**. ⇒ `{ok:true, item:{…}}`. |
| `GET /api/v2/marketing/attribution?month=YYYY-MM` | `month` optional (default current UTC month); bad ⇒ 400 «الشهر غير صالح». ⇒ `_v2_get('/api/bridge/attribution/summary', {'month': m})`. The platform's 404 passes through as 404 (the UI reads it as `closed` = «غير متاح بعد»); 401/403 ⇒ 502 (existing `_v2_mask_auth`). One call, no retry. |

**Tables** (created lazily by every route through `_ensure()`, idempotent):
```sql
CREATE TABLE IF NOT EXISTS v2_campaign_owner (
  campaign_id INTEGER PRIMARY KEY,
  owner_kind  TEXT NOT NULL,
  owner_id    TEXT NOT NULL DEFAULT '',
  owner_title TEXT NOT NULL DEFAULT '',
  updated_at  TEXT NOT NULL,
  updated_by  TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS v2_marketing_meta (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
```
- `_ensure()` inserts `legacy_max_campaign_id` only when the key is missing, so the first run with the flag on fixes the line between old-screen rows and new-screen rows. With the flag off, `_v2_closed()` returns first and nothing is written.
- It runs through `db.session.execute(text(...))` + commit, and is portable between SQLite and Postgres.
- No change to the `Campaign` model and no change to `/api/campaigns`.

---

## 9) Platform needs

**P1: per-person and per-payment source (attribution). Required for number 3, the «بلا إعلان» row, the «عبر الرابط» column and «جاء عبر الرابط».**

**The shape belongs to the reports spec, N1 (`.worktrees/reports/docs/v2/final/SPEC-reports.md` §12 N1). Marketing adds only `campaigns[]` and the `paid` flag on top of it.** There is one capture, one channel function and one set of keys for both screens. Marketing defines no capture of its own.

- **Taken as is from reports N1 (not repeated here, not changed):**
  - the first-party first-touch cookie `ep_acq` and its fields `{utm_source, utm_medium, utm_campaign, utm_content, utm_term, referrer_host, landing_path, first_seen_at}`;
  - `users.acq` (with `acq.channel`) set by the four signup doors;
  - `payments.acq` (first touch, copied from `users.acq` at creation) and `payments.acq_last`;
  - the single function `services/attribution.channel_of(acq, user)` and its keys: `google`, `meta`, `whatsapp`, `invite`, `direct`, `other`.
- **Added by marketing: one read-only bridge** `GET /api/bridge/attribution/summary?month=YYYY-MM`, guarded by `X-ELP-Metrics-Secret`. It reads the same `users.acq` and `payments.acq`; it never computes a channel itself (it calls `channel_of`).
  ```json
  {
    "ok": true,
    "month": "2026-11",
    "captured_since": "2026-11-02T10:00:00Z",
    "channels": [
      {"key": "meta",   "paid": true,  "signups": 12, "paid_people": 4,
       "totals": [{"currency": "EGP", "amount": 3400.0}]},
      {"key": "meta",   "paid": false, "signups": 20, "paid_people": 5, "totals": [...]},
      {"key": "google", "paid": false, "signups": 30, "paid_people": 9, "totals": [...]},
      {"key": "invite", "paid": false, ...},
      {"key": "direct", "paid": false, ...}
    ],
    "untracked": {"signups": 40, "paid_people": 11, "totals": [...]},
    "campaigns": [
      {"campaign": "c12", "source": "facebook", "signups": 9, "paid_people": 3,
       "totals": [{"currency": "EGP", "amount": 2100.0}]}
    ]
  }
  ```
- **Rules:**
  - `channels[]` has one row per (`key`, `paid`) pair that has data. `key` = `acq.channel` (the reports keys, unchanged).
  - `paid` = `true` when `acq.utm_medium` (lower-cased) ∈ {`cpc`, `paid`, `ads`, `paid_social`}, otherwise `false`. There is **no separate «ads» channel**: a paid visit from Meta is `{key:'meta', paid:true}`.
  - `untracked` = people and payments with no `acq` (they came before capture started). It is a separate block, never a channel, so no new key is added to the reports set.
  - «دخل جاء بلا إعلانات» on the dashboard = Σ of `channels[]` rows with `paid:false`. The `untracked` block is never counted.
  - `signups` = users created in the month, by `users.acq`. `paid_people` = distinct payers in the month (same definition as reports N3: status paid/partially_refunded, `ads_deposit` excluded, test users excluded), by `payments.acq`.
  - **Totals** follow the exact rules of `/bridge/income/by-service`: paid in full, or partially refunded at the net amount; `ads_deposit` excluded; per currency, never converted; the month by `paid_at`, otherwise `updated_at`.
  - `campaigns[]` groups by `acq.utm_campaign` (the dashboard link uses `c{id}`), with `source` = `acq.utm_source`.
  - `captured_since` = the earliest `users.acq.first_seen_at`, or `null`. Any field not tracked is `null`, never `0`.
- **Tests (platform):** secret required; the shape; keys only from `channel_of`; `paid` set only for the four media; currencies never summed; refunds netted; no `acq` ⇒ counted in `untracked` only; `campaigns[]` grouped by `utm_campaign`.

**P2 (optional, same round if cheap): monthly spend per owner in the ads overview.**
- `GET /api/bridge/ads-ledger?month=YYYY-MM` adds `month_spend:[{currency, amount}]` per row (sum of `entry=='spend'` in the month).
- With it, the ads-balances line (§4.6) gains «· صُرف منها هذا الشهر: {money line}». Without it, that part is **not shown** (never 0).

**P3 (later, not this round): recording ad spend against an owner's balance from the dashboard.**
- `POST /api/bridge/ads-ledger/{owner_id}/entries` with `{owner_kind, entry:'spend', amount, currency, campaign_id:'c{id}', by, confirmed:true}` ⇒ 422 over balance.
- This is a money action, so it would go through the confirmation sheet with `confirmed:true`.
- It is listed so that the «مدار» round can wire «صُرف كم وجاب إيه» to the owner. **No dashboard UI for it this round.**

«مدار» itself has no platform need. It is a separate system and is integrated in a later round.

---

## 10) Pure helpers — `V2L.mk` (node-testable, in the `// ===== v2s:marketing =====` block)

| Helper | In ⇒ Out | Rules |
|---|---|---|
| `mk.norm(raw[])` | ⇒ rows `{id, name, platform, platformLabel, status, statusLabel, currency, start, end, budget, spent, clicks, leads, conversions, revenue, audience, noResults}` | `currency` uppercased; missing ⇒ `'EGP'` **only for display of a missing value**, and a stored value is kept as is. Unknown status ⇒ `'paused'` label «موقوفة». Numbers via `Number()||0`. |
| `mk.board(rows, filter, extra)` | ⇒ `{numbers:[4]}`, each `{label, value, na, primary, others[], note}` | §4.2; each number picks its own primary currency; every note names its period; `extra = {income, attribution}` each `null` when not ready ⇒ `na:true` + exact texts. |
| `mk.legacyUsd(rows, legacyMaxId)` | ⇒ rows | §4.2a: `currency==='USD'` and `id ≤ legacyMaxId`; `legacyMaxId` 0/null ⇒ `[]`. |
| `mk.mature(row, todayISO)` | ⇒ bool | §4.3 maturity rule. |
| `mk.ratio(rev, spent)` | ⇒ `null` or a number to one decimal | `spent<=0` ⇒ null. |
| `mk.ratioText(r, cur)` | ⇒ «كل جنيه رجع ٣٫٧» | unit map §4.2. |
| `mk.brain(rows, todayISO, skipped)` | ⇒ `{items:[{kind, id, text, line, btn, action}], state:'items'|'empty'|'young'|'none'}` | §4.3 priorities and maturity rule; `skipped` = a set of `kind_id`. |
| `mk.mainButton(brainState)` | ⇒ `{main:'brain'|'top', topHidden:bool}` | §4.1: `items` ⇒ brain; `empty` ⇒ brain + top hidden; `young`/`none` ⇒ top. |
| `mk.sources(states)` | ⇒ `{seen:[{key,label,state}], needs:[{key,title,why,chip,how}], failed:[key]}` | §4.4. |
| `mk.rows(rows, owners, filter, attribution)` | ⇒ table view model (typed numbers, plus `via:{signups, paid_people}|null` from `campaigns[]`, plus `viaColumn:bool`) + organic row | §4.5. |
| `mk.byPlatform(rows)` | ⇒ `{facebook:{n, spent[], revenue[], conversions, shared}, …}` | §6. |
| `mk.ownerChoices(adsState, adsItems, loadedOwner)` | ⇒ `{disabled, options[], selected, hint}` | §5.2: the loaded owner is always selected; `ads` not ready ⇒ disabled single option. |
| `mk.link(id, platform)` | ⇒ URL string | §5.1. |
| `mk.statement(row, owner, todayISO)` | ⇒ text | §5.4. |
| `mk.validate(form, loadedOwner)` | ⇒ `{ok, body, error, ownerChanged}` | §5.2 rules, Arabic errors; `ownerChanged` only when the chosen owner differs from `loadedOwner` and the select was enabled. |
| `mk.STR` | all visible strings in one object | the copy lint test reads it. |

---

## 11) Visual rules (`v2s/marketing.css`, `.mk-*` only)
- **Tokens:** wine `#9E2B4E`, paper `#FBFAF7`/`#F6F1EA`, ink `#21262E`, red `#C8102E` only for ratios < 1 and failure dots; green as in D3. Fonts Cairo/IBM Plex, same as D3.
- **Cards and spacing:**
  - cards: white, 18 px radius, 1 px `var(--line)`, 16–18 px padding;
  - gaps: 14–16 px.
  - No old classes (`.kpis`, `.kpi`, `.inboxwrap`, `.panel`, `.drawer`, `.row`, `.status`, `.policy`) inside any marketing view.
- **Sizes:** targets ≥44 px; on mobile, buttons and rows ≥52 px. No horizontal page scroll at 390; the desktop table never exceeds its card (`table-layout:fixed`, `overflow-wrap:anywhere` on names).
- **One main button per screen:** at most one visible `.v3-btn1` on each tab (§4.1; none while the campaigns source has failed; the social and plan tabs have none, their actions are `.v3-btn2` or text links).
- **The brain strip** `.mk-brainstrip`: ink `#21262E` background, white text, 22 px radius; the main button stays wine `#9E2B4E` with white text; «بعدين» transparent with a white border at 40 % opacity. Focus rings are visible on the ink background (white 2 px outline).
- **Platform numbers** (the «عبر الرابط» column, the `.mk-via` chip, the organic row, the detail's platform line) always sit on paper `#F6F1EA`, so they never look like the typed numbers on white.
- **Real photos:** `v2/img/marketing.jpg` (the «مدار» card, social tab only) and `v2/img/brain-avatar.jpg` (the brain strip, 50 px round, 2 px wine border). No new images.
- **Motion:** respect `prefers-reduced-motion`.

---

## 12) Tests — `backend/tests/test_v2s_marketing.py`

Run: `cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_marketing.py`.
- Zero real network: `requests` is patched so that any host other than `https://platform.test` fails the test.
- Port-binding tests are rerun outside the sandbox by the main session.

**pytest (routes):**
1. Every new route: 401 without a token; 403 for `employee/trainer/investor/viewer/pending`; flag off ⇒ 404 with zero platform calls and zero rows created; `Cache-Control: no-store` on 200/400/404/502.
2. `published`:
   - window filter (8-day-old excluded at `days=7`);
   - only `published`;
   - newest first;
   - cap 50;
   - `drafts` count;
   - `days=0/32/abc` ⇒ 400.
3. `owners` PUT:
   - kind whitelist;
   - `V2_ID_RE`;
   - title trim to 200;
   - unknown campaign 404;
   - upsert (second PUT replaces);
   - `by` taken from the token even when the body carries `by`;
   - audit row on success only;
   - `platform` clears id/title.
4. `owners` GET hides rows of deleted campaigns.
4a. **Legacy currency:**
   - the first GET with the flag on stores `legacy_max_campaign_id` = the current `MAX(campaigns.id)` and returns it as `legacy_max_id`;
   - a campaign created afterwards does not move it (second GET returns the same value);
   - an empty `campaigns` table ⇒ 0;
   - `POST /legacy-checked` ⇒ the next GET returns `legacy_max_id: 0`; a second POST is harmless; audit on success only;
   - flag off ⇒ 404 and no meta row written.
5. `attribution`:
   - bad month 400;
   - passes `month` to `/api/bridge/attribution/summary`;
   - platform 404 ⇒ 404;
   - platform 401 ⇒ 502;
   - platform 200 passes the body through untouched;
   - one call only.
6. `/api/campaigns` unchanged: POST with `currency:'EGP'` stores EGP; PUT `status:'completed'` works; DELETE works (guards against any accidental edit).
7. **Files:**
   - the `index.html` block has our two lines between the markers, alphabetical;
   - the `renderView` hook lines exist and are gated by `V2_ON`;
   - `app.py` has the registration line before `# ---- v2 section routes end`;
   - **each of the three Dockerfiles** has the lines of §1 item 5: `Dockerfile` and `deploy/Dockerfile.coolify` contain both `COPY dashboard-cloud/v2s /app/dist/v2s` and `COPY backend/v2_*_routes.py /app/`; `backend/Dockerfile` contains `COPY v2_*_routes.py ./`. The test fails if any one is missing;
   - every `openSection(sec, tab)` call in `v2s/marketing.js` names a tab that exists: `V2L.tabByKey('money','ads')` is present now; `V2L.tabByKey('company','ads')` is asserted when the company entry carries tabs (skipped with a clear message until the company round is merged, and required by the integrator after the merge);
   - `v2s/marketing.js` contains no `openSection('reports'` (the one-way rule of §2);
   - the `SECTIONS` marketing entry equals §2;
   - with the flag off, `viewMarketing` and the old loader are byte-identical to `7d1aa83`, compared by hashing those functions.

**node (via `uiharness/v2_node.py`):**

8. `board`:
   - per-currency sums;
   - an SAR row never enters the EGP total and shows in `others`;
   - ratio only with spent>0;
   - cost only with conversions>0;
   - 0 rows ⇒ «لا حملات مسجّلة»;
   - number 3 ⇒ «غير متاح بعد» without attribution, and with attribution sums only `paid:false` rows and never `untracked`;
   - the income note uses the per-currency line;
   - **periods:** notes 1, 2 and 4 contain «منذ بداية» / «منذ بدايتها», and note 3 starts with «هذا الشهر»;
   - Σspent>0 and Σrev=0 ⇒ number 2 value «لم يُسجَّل دخل بعد» with `na:true`, never «٠»;
   - each number picks its own primary currency.
9. `brain`:
   - priority order;
   - `skipped` respected; «بعدين» advances to the next item;
   - every number in the text equals the row values;
   - `best` only when nothing else applies;
   - `empty`/`young`/`none` texts;
   - no suggestion from non-active rows;
   - **maturity:** a row that started yesterday with clicks and revenue 0 gives no `losing`; a row 10 days old with spent < 25 % of its budget gives no `losing`/`no_results`; the same row at ≥25 % does; an empty `start_date` counts as mature;
   - **`no_results` is reachable:** a mature row with all four results 0 yields `no_results`, not `losing`;
   - `losing` with revenue 0 (but clicks>0) reads «ولم يُسجَّل لها دخل بعد» and never «رجع ٠».
9a. `mainButton`: `items` ⇒ brain; `empty` ⇒ brain and the top button hidden; `young`/`none` ⇒ top. The rendered HTML of the campaigns tab contains exactly one `.v3-btn1` in each of these states.
9b. `legacyUsd`: only USD rows with `id ≤ legacyMaxId`; SAR/EGP rows never; `legacyMaxId` 0 ⇒ empty.
10. `sources`: needs list order; a ready attribution removes its need; `error` ≠ need and appears in `failed`; the rendered tail has no button per need and exactly one «كيف تُربط هذه المصادر؟» link.
11. `rows`:
    - sort order;
    - the «لم تُسجَّل نتائج» chip;
    - organic row texts in both modes, with the sub line «من المنصة · هذا الشهر …»;
    - `via` only from `campaigns[c{id}]`; `viaColumn` false when attribution is not ready; the typed `leads`/`conversions` are never replaced by platform numbers.
12. `byPlatform`: shared facebook_instagram counted in both and marked; spent per currency; revenue 0 ⇒ «لم يُسجَّل دخل بعد».
13. `link` (the `src` map of §5.1, `facebook_instagram` ⇒ `meta`), `statement` (skips empty fields, keeps zeros, Arabic date), `validate` (name required, negative, end<start, «أخرى» requires a name, Arabic digits parsed).
13a. **Owner safety:** `ownerChoices` with `ads` failed and a campaign owned by a course ⇒ disabled, single option «{owner_title} — الحالي»; `validate(form, loadedOwner)` on that form ⇒ `ownerChanged:false`. With `ads` ready and the same owner kept ⇒ `ownerChanged:false`; with a different owner chosen ⇒ `true`. An owner missing from the `ads` list is kept as an extra option.
14. **Copy lint over `mk.STR` and the rendered HTML of each tab** (jsdom-free: render functions return strings):
    - no «يقوّم»;
    - no Latin letters in our own strings (`mk.STR` and fixed labels) except the campaign URL; values typed by the founder (campaign names, a stored platform like «Google Ads») are data and are shown as stored;
    - no headline starting with «الذكاء»;
    - no «CAC/ROAS/Impressions/Clicks/API/utm» visible;
    - every unavailable value reads exactly «غير متاح بعد»;
    - the social tab HTML has exactly one button (`.v3-btn2` «ماذا سيظهر هنا؟») besides any «أعد المحاولة», and no «العقل يحتاج» block;
    - the campaigns tab HTML has no `.mk-links` / link cards and no «اربط مدار» photo card.

Also rerun `test_v2_d1.py`, `test_v2_d1b.py`, `test_v2_d2.py` and `test_v2_d3.py`. The SECTIONS map test must still pass (`marketing` lands on `marketing/campaigns`).

---

## 13) Shots — `backend/tests/uiharness/v2_shots_marketing.py`

```
cd backend && python3 -B tests/uiharness/v2_shots_marketing.py ../docs/v2/final/shots-marketing
```
- **Sizes:** desktop 1440×900, tablet **820×1180**, mobile 390×844.
- **Fixtures:**
  - `MKPlatform` (subclass of `D3Platform`): income/ads from D3, plus `/api/bridge/attribution/summary` when `attribution=True`.
  - `seed_mk(app)` seeds five campaigns:
    1. active EGP winning (ratio 5.2);
    2. active EGP losing (1.2, `ended` false, started 20 days ago, spent ≥25 % of budget);
    3. active with no results (started 15 days ago, spent ≥25 %);
    4. paused SAR;
    5. completed USD (seeded before the first `_ensure()`, so it is an old-screen row for §4.2a);
    6. active EGP young (started yesterday, clicks > 0, revenue 0): it must never be suggested.
  - It also seeds one owner link (on campaign 2, a course), four published articles (two in the last 7 days) and three drafts.

**Shot list (each at d/t/m; names `mk-{nn}-{name}-{d|t|m}.png`):**
1. `campaigns`: full tab, «النشطة الآن».
2. `campaigns-all`: «كل الحملات» (SAR chip visible).
3. `campaigns-attr`: attribution on (number 3 lit, «بلا إعلان» row filled, the «عبر الرابط» column on desktop, the `.mk-via` chip on tablet, the paper row on mobile).
4. `campaigns-down`: campaigns 502 + income 502 + ads 502 (warn strip, «غير متاح بعد», «حملة جديدة» disabled).
5. `campaigns-empty`: no campaigns (brain strip «لا حملات مسجّلة…» carries «حملة جديدة»; the top button is hidden).
6. `brain-stop`: the «أوقفها» confirm sheet.
7. `detail`: the campaign detail sheet (link + «انسخ الرابط»).
8. `edit`: the edit sheet with «أخرى» selected (text box visible) and USD preselected on row 5.
9. `edit-owner-locked`: `ads` 502, the edit sheet on campaign 2 (owner select disabled, «… — الحالي»).
10. `delete`: the delete confirm.
11. `legacy`: the old-currency strip and its sheet «عملة الحملات القديمة».
12. `needs-how`: the single sheet «كيف تُربط هذه المصادر».
13. `madar`: the «ماذا سيظهر هنا؟» sheet.
14. `social`: the social tab.
15. `plan`: the plan tab.
16. `plan-down`: the plan tab with `published` 500.
17. `old-link`: open `#marketing` ⇒ lands on «التسويق / الحملات» with the new look.
18. `flag-off` (desktop only): the old marketing screen unchanged.

**Checks on every shot (fail ⇒ exit 1, D3 style):**
- `document.documentElement.scrollWidth <= innerWidth`;
- no `.kpis/.inboxwrap/.panel/.drawer/.policy` inside `#view` (except shot 18);
- at most one visible `.v3-btn1` inside `#view` (sheets excluded);
- every visible button/row ≥44 px tall (≥52 px at 390);
- zero requests outside `platform.test` and the local app;
- the text «غير متاح بعد» present where the fixture removed a source;
- no Latin letters in visible text outside the URL field and the founder-typed fixture values.

Rerun `v2_shots.py d1b` and `d3` to prove nothing broke.

---

## 14) Status file
`docs/v2/final/STATUS-marketing.md`:
- what was built;
- the sources found and missing (with the 404/502 behaviour seen in fixtures);
- the shared edits made (exact lines);
- the old-data trap (USD default): the `legacy_max_id` seen in fixtures and the strip's behaviour (fix all · keep as dollar · later);
- the test counts;
- the shot list.

## 15) Out of scope
- Connecting «مدار», Meta, Google, or any social API (later round).
- Sending statements to owners.
- Recording owner ad spend (P3).
- Rewriting the «التسويق» tile in `v2Tiles` (shared).
- The concept's «التقرير» tab (postponed until attribution and «مدار» give it a source, §2).
- A monthly split of campaign spend (`month_spent`), which needs daily figures from «مدار».
- Marketing decision cards in «ابدأ القرارات». `V2SEC.marketing.cards()` returns the §4.3 items in the `v2Card`-like shape `{kind, title, line, btn, open()}` so the home round can pick them up without editing this file.
- Any deploy or push.

---

## 16) Decisions (revision 2, after the expert review)

All points received were accepted. Where the fix was adjusted, the reason is given.

| # | Review point | Decision |
|---|---|---|
| 1 | Dockerfiles copy explicit lists; `v2s/` and the route module would not ship (critical) | **Accepted.** §1 item 5 now edits all three Dockerfiles with exact lines, and the wrong sentence («copies the whole folder») is gone. §12 item 7 fails if any Dockerfile lacks its lines. |
| 2 | Two contradicting attribution shapes, marketing vs reports N1 (critical) | **Accepted.** §9 P1 adopts reports N1 as is (`ep_acq`, `users.acq`, `payments.acq`, `channel_of` and its keys) and drops marketing's own capture. Marketing adds only the summary bridge with `campaigns[]` and the `paid` flag. Adjustment: rows with no `acq` go to a separate `untracked` block instead of an `unknown` channel, so the reports key set stays exactly as defined. Payers are counted as `paid_people`, the reports name. |
| 3 | `openSection('company','adclients')` names a tab that does not exist | **Accepted.** Now `('company','ads')`, matching `SPEC-company.md:33`; §12 asserts the tab once the company round is merged. |
| 4 | Circular link between «التسويق» and «التقارير» | **Accepted.** The footer link and the «report lives in التقارير» sentence are removed. The rule is one way: reports links here. The concept's «التقرير» tab is postponed until it has a source (§2, §15). The optional conditional link was not kept: one fewer target, and the reports round already provides the way in. |
| 5 | Mixed periods in one row of numbers | **Accepted.** Every note names its period (§4.2), the `.v3-ptxt` line says so, and Σspent>0 with Σrev=0 reads «لم يُسجَّل دخل بعد» instead of «٠». `month_spent` waits for «مدار». |
| 6 | The brain did not match the concept's dark strip | **Accepted.** §4.3 is now the full-width ink strip under the numbers. «العقل يرى من» chips and the compact «العقل يحتاج» lines move to the campaigns card's tail with one link to one sheet (§4.4). |
| 7 | About 14 targets and several main buttons on one tab | **Accepted.** At most one `.v3-btn1` per tab (§4.1, with the `mainButton` helper and a test). «حملة جديدة» is `.v3-btn2` except when the brain has no button. The three link cards are replaced by one line with two text links (§4.6). The «اربط مدار» photo card appears once, in the social tab. Also removed: the «اطلب الربط» link on number 3, the «التالي» link (now «بعدين» shows the next suggestion), and the four «كيف يُربط؟» buttons. |
| 8 | The social tab was five boxes of «غير متاح بعد» | **Accepted.** Each card leads with the recorded spend; «المتابعون والوصول: غير متاح بعد» is one small line; one button on the tab; the repeated needs block is removed (§6). |
| 9 | A failed `ads` source could overwrite a campaign's owner | **Accepted.** §5.2 keeps the loaded owner selected, locks the select when `ads` (or `owners`) is not ready, and sends the owner call only on a real change. `ownerChoices` and `validate(form, loadedOwner)` are tested (§12 item 13a). |
| 10 | `losing`/`no_results` fire on day one and read «رجع ٠٫٠» | **Accepted**, with the maturity rule of §4.3 and the `young` state. One more fix found while applying it: in the old table every `no_results` row also matched `losing` (priority 2), so `no_results` could never appear. `losing` now excludes rows with no results at all. |
| 11 | Old-screen campaigns stored as USD would make the numbers read «دولار» on pound amounts | **Accepted**, adjusted. The reviewer's simple test («any USD row») would nag forever about campaigns that really are in dollars. The strip uses `legacy_max_id` instead: the highest campaign id that existed when the new screen first ran, stored once in `v2_marketing_meta`. So only old-screen rows are listed, and a third choice «هي بالدولار فعلًا» closes the strip for good (§4.2a, §8). Converting is a currency-label change on the record; no amount is converted. |
| 12 | «سجّلوا/دفعوا» shown twice with different sources and the same word | **Accepted.** The typed headers carry «كما سُجّل»; platform numbers live in a separate «عبر الرابط» column on paper with «من المنصة · هذا الشهر», a `.mk-via` chip on tablet, and a separate paper row on mobile (§4.5, §11). The review text was cut off in the middle of this point (after «تابلت/موبايل»). The tablet and mobile treatment here is our completion of it, and **no review points after this one were received.** |

Observation outside our scope, for the integrator: `deploy/Dockerfile.coolify` does not copy `backend/refresh_rules.py`, which `app.py` imports at start (§1 item 5).



> Amendment (fix round): the button named «بعدين» above ships as «لاحقًا» (plain standard Arabic; D1 source guard). `legacy_max_id` is computed from campaigns created before the first run (`legacy_cutoff`), not from the raw max id, because SQLite reuses the top id after a delete.
