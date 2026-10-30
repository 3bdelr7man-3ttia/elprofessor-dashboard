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
| Trap 1 | old modal | The labels say «(ج)», but the modal never sends `currency`, so every row saved from the old screen is stored as **USD**. The new screen shows the stored currency as it is and lets the founder correct it in the edit sheet. It never converts. |
| Trap 2 | old modal | The «الدورة المرتبطة» select is read but **never sent** (`course_id` is always null). It is dropped. The new owner link (§6) replaces it. |
| Trap 3 | `POST /api/campaigns` | `d['name']` is required; a missing name ⇒ 500. The new form requires a name before sending. |
| Real sources the marketing screen can use | see §3 | Campaigns (manual) · platform income by service (D3) · ad balances of course/book owners (D3) · site articles (local CMS) · ops queue drafts. |
| Attribution | platform `routes/auth.py:267` (`?ref=` affiliate), `routes/payments.py:92-94` (`attribution` = trainer/platform on course orders), `marketing_ops.py:296` (`lead_magnet_leads.source`) | **No per-signup or per-payment traffic source** (no utm/referrer on users or payments). So «دخل جاء بلا إعلانات» has **no source** ⇒ «غير متاح بعد» + a source request (Platform need P1). |
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
5. `backend/Dockerfile` (**shared edit**): the image copies `app.py` only, so the new module would be missing in production. Add exactly this line after `COPY app.py .` (identical in every section, so git merges cleanly):
   ```
   COPY v2_*_routes.py ./
   ```
   The dashboard-cloud Dockerfile already copies the whole folder (`COPY . …`), so `v2s/` ships as is.

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
- The concept's «التقرير» tab is **not** a tab here. The report lives in «التقارير» (its own section, with a «التسويق» filter). A link at the bottom of «الحملات» opens it, so nothing is built twice.
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
| `owners` | `GET /v2/marketing/owners` (new, §8) | «لمن الحملة» on rows and in the detail | `items[].campaign_id, owner_kind, owner_id, owner_title` | the owner line is hidden and the detail sheet shows «غير متاح بعد» next to «لمن الحملة» |
| `income` | `GET /v2/income/by-service?month=YYYY-MM` (existing D3) | the note under number 3 | `services[].totals[] {currency, amount}` summed **per currency** with `V2L.util.sumByCurrency` | the note line is dropped (number 3 is «غير متاح بعد» anyway) |
| `ads` | `GET /v2/ads-ledger` (existing D3) | card «إعلانات نديرها لأصحاب الدورات والكتب»; owner choices in the edit sheet | `items[].owner_kind, owner_id, title, balance[] {currency, amount}, last_entry_at` | card body «غير متاح بعد» + «أعد المحاولة»; the owner select offers only «البروفيسور نفسه» with the hint «قائمة الأعمال غير متاحة الآن» |
| `published` | `GET /v2/marketing/published?days=7` (new, §8) | «خطة النشر»: published this week + drafts count | `items[] {id, title, published_at}`, `drafts` | unavailable block «مقالات الموقع: غير متاح بعد» |
| `attribution` | `GET /v2/marketing/attribution?month=YYYY-MM` (new proxy, §8 ⇒ Platform need P1) | number 3, the «بلا إعلان» table row, «جاء عبر الرابط» in the detail, the «العقل يحتاج» list | §9 P1 shape | `closed` (404 = the platform has no bridge yet) or `error` ⇒ everything that depends on it shows «غير متاح بعد» and the need stays in «العقل يحتاج» |
| ops queue | `EP.data.opsQueue` (already loaded by the shell; `EP.ensure('opsQueue')`) | not used here, so no duplicate counting | — | — |

**Loaded per tab:**
- «الحملات»: campaigns, owners, income, ads, attribution.
- «السوشيال ميديا»: campaigns, attribution.
- «خطة النشر»: published.

---

## 4) Tab «الحملات» (`marketing`, default)

### 4.1 Layout
- **Desktop ≥1180** (inside the D1-B shell content area, max width as other v2 screens):
  1. Top bar (`.v3-top`):
     - segmented control `.v3-seg`: «النشطة الآن» (default) | «كل الحملات»;
     - on the inline end, the main button `.v3-btn1` «حملة جديدة».
     - Under the bar, one `.v3-ptxt` line: «الأرقام كما سُجّلت في كل حملة. لا يصل إلى هنا شيء من حسابات الإعلانات قبل ربط «مدار»».
  2. Four numbers `.v3-nums` (4 columns), §4.2.
  3. Two columns `.v3-two` (3fr | 2fr):
     - start: the brain card «العقل يقترح» (§4.3);
     - end: the card «العقل يرى من» with the sub-block «العقل يحتاج» (§4.4).
  4. Card «الحملات: من الإعلان حتى الدفع» with the full table (§4.5).
  5. Three cards in a row (`.mk-links`, 3 columns): «إعلانات نديرها لأصحاب الدورات والكتب» · «عملاء الإعلانات بالنتيجة» · «اربط مدار» (§4.6).
  6. Footer link `.v3-link`: «تقرير التسويق الكامل في «التقارير»» ⇒ `V2_HOST.openSection('reports')`.
- **Tablet 761–1179:**
  - numbers 2×2;
  - `.v3-two` stacks (brain card first);
  - the table becomes compact, §4.5;
  - link cards in 2 columns, with «اربط مدار» spanning the full row.
- **Mobile ≤760:**
  - one column;
  - the segmented control is full width, with 52 px segments;
  - «حملة جديدة» is full width at 52 px, under the segmented control;
  - numbers in one column;
  - the table becomes cards (§4.5);
  - link cards stack;
  - every button ≥52 px;
  - no horizontal page scroll at 390.

### 4.2 The four numbers (pure helper `V2L.mk.board(campaigns, filter, extra)`)

Filter: «النشطة الآن» = `status === 'active'`; «كل الحملات» = all rows.
- Sums are **per currency**, never mixed and never converted.
- The **primary currency** = EGP if any row in the filter has EGP, otherwise the currency with the largest spend.
- Other currencies show as a chip `.v3-oth`: «وبعملة أخرى: ٣٠٠ ر.س».

| # | Label | Value | Note line (`.v3-note`) | No data |
|---|---|---|---|---|
| 1 | «صُرف على الإعلانات» | Σ `spent` (primary currency) | «{N} حملة نشطة» via `U(n,['حملة واحدة نشطة','حملتان نشطتان','حملات نشطة','حملة نشطة'])`, or with «كل الحملات»: «من {N} حملات مسجّلة» | 0 rows ⇒ value «لا حملات مسجّلة» (class `na`), never «٠» |
| 2 | «دخل جاء من الإعلانات» | Σ `revenue_attributed` (primary) | when Σspent>0 in the same currency: «كل {unit} رجع {r}» (`r` = Σrev/Σspent, one decimal, Arabic digits «٣٫٧»; unit: EGP «جنيه», SAR «ريال», USD «دولار», else «وحدة»). Otherwise: «كما سُجّل في كل حملة» | 0 rows ⇒ «لا حملات مسجّلة» |
| 3 | «دخل جاء بلا إعلانات» | attribution ready ⇒ Σ totals of every channel ≠ `ads` and ≠ `unknown` (primary currency) for the current month | ready: «منذ {date(captured_since)}، من البحث والسوشيال والدعوات والتوصيات». Not ready: «المنصة لا تسجّل بعد من أين جاء كل دافع.» plus, when `income` is ready: «دخل المنصة كله هذا الشهر: {money line}، ولا نعرف بعد كم منه جاء من إعلان.» | not ready ⇒ value **«غير متاح بعد»** (class `na`), and the number carries a small `.v3-link` «اطلب الربط» that scrolls to the need in §4.4 |
| 4 | «كلفة العميل الواحد» | Σspent ÷ Σconversions (primary currency, rows with `conversions>0` only), rounded to whole units | «من الحملات التي سُجّل لها من دفع» | no row with conversions>0 ⇒ «غير متاح بعد» + note «لم يُسجَّل بعد من دفع عن طريق حملة» |

Campaigns source failed ⇒ numbers 1, 2 and 4 show «غير متاح بعد» with the note «تعذّر جلب الحملات». Top strip `.v3-warn`: «تعذّر جلب: الحملات — ما يظهر ناقص، وليس معناه أنه لا شيء» + «أعد المحاولة».

### 4.3 The brain card «العقل يقترح» (pure helper `V2L.mk.brain(campaigns, today, skipped)`)

There is one suggestion at a time, with one main button and «بعدين».
- With more than one: a line «اقتراح {i} من {n}» and a `.v3-link` «التالي».
- «بعدين» hides that suggestion for this browser session: `sessionStorage['mk_later_'+kind+'_'+id]`, every access wrapped in try/catch; if storage fails, the hide lasts until reload.
- Facts only: every number in the text comes from the row itself.
- Only rows in the **active** filter count (independent of the segmented control).
- Ties: larger `spent` first.

| Priority | `kind` | Condition (all from the campaign row) | Text (exact) | Main button ⇒ action |
|---|---|---|---|---|
| 1 | `ended` | `status==='active'` and `end_date` < today | «حملة «{name}» انتهى موعدها في {dateText(end_date)} وما زالت «نشطة» هنا.» / suggestion line: «أقترح تسجيلها منتهية.» | «سجّلها منتهية» ⇒ confirm sheet ⇒ `EP.api('/campaigns/'+id,{method:'PUT',body:{status:'completed'}})` |
| 2 | `losing` | active, `spent>0`, `revenue_attributed < spent` (same row, one currency) | «حملة «{name}» صُرف عليها {money(spent)} وسُجّل لها دخل {money(rev)}: كل {unit} رجع {r}.» / «أقترح إيقافها.» | «أوقفها» ⇒ confirm sheet ⇒ `PUT /campaigns/{id}` `{status:'paused'}` |
| 3 | `no_results` | active, `spent>0`, and `clicks`, `leads`, `conversions`, `revenue_attributed` all 0 | «حملة «{name}» صُرف عليها {money(spent)} ولم تُسجَّل لها أي نتيجة بعد.» / «أقترح نقل نتائجها من حساب الإعلانات.» | «سجّل النتائج» ⇒ opens the edit sheet (§5.2) on that campaign |
| 4 | `over_budget` | active, `budget>0`, `spent>budget` | «حملة «{name}» صُرف عليها {money(spent)} وميزانيتها {money(budget)}.» / «راجع الميزانية أو أوقفها.» | «عدّل الحملة» ⇒ edit sheet |
| 5 | `best` (info) | none of the above; best active row with `spent>0` and ratio ≥ 3 | «أفضل حملة الآن «{name}»: كل {unit} رجع {r}.» | «افتح الحملة» ⇒ detail sheet (§5.1); no «بعدين» |
| — | `empty` | no campaigns at all (source ready) | «لا حملات مسجّلة. سجّل أول حملة لأرى ما صُرف وما جاء.» | «حملة جديدة» ⇒ create sheet |
| — | `none` | rows exist, nothing applies | «لا اقتراح الآن. الحملات النشطة تسير كما سُجّلت.» | no button |

**Confirm sheets for «أوقفها» and «سجّلها منتهية»:**
- Title: «إيقاف حملة» / «تسجيل حملة منتهية».
- Lead: «ستصبح حملة «{name}» {موقوفة|منتهية} في سجلّ الحملات هنا.»
- Warning line `.v3-warn`: «هذا لا يوقف الإعلان نفسه. أوقفه من حساب الإعلانات حتى يُربط «مدار».»
- Buttons: «أكّد» (`.btn.btn-primary`) and «إلغاء».
- On success: close the sheet, reload `campaigns`, and show `.v3-ok` «تم: حملة «{name}» {أُوقفت|سُجّلت منتهية}».
- On failure: the sheet stays open with `.v3-err` showing the server's message, or «تعذّر الحفظ — أعد المحاولة».

These are record edits and move no money. They still go through the confirmation sheet, but `confirmed` is not required by `/api/campaigns`, so no flag is sent.

The card header is «العقل يقترح», with the small avatar `v2/img/brain-avatar.jpg` (existing). The headline never starts with «الذكاء».

### 4.4 «العقل يرى من» + «العقل يحتاج» (pure helper `V2L.mk.sources(states)` ⇒ `{seen[], needs[]}`)

Each source is a chip (`.mk-src`) with a dot:
- green «متصل» when its state is `ready`;
- grey «غير مربوط» when it is not connected by design;
- amber «تعذّر الجلب» when the state is `error`.

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

Under the chips, the heading **«العقل يحتاج:»** lists every source that is not connected, in this order. Each item has a title, a «لماذا» line, a status chip, and the button `.v3-btn2` «كيف يُربط؟», which opens an explanation sheet. That button is informational and never pretends to connect anything.

| Need | «لماذا» line | Status chip | «كيف يُربط؟» sheet text |
|---|---|---|---|
| «من أين جاء كل شخص يسجّل أو يدفع» | «لأعرف كم من الدخل جاء من إعلان وكم جاء بلا إعلان، ولأربط كل دافع بحملته.» | «يحتاج تعديلًا في المنصة» | «تحفظ المنصة عند أول زيارة من أين جاء الزائر (إعلان، بحث، سوشيال، دعوة، كود مدرّب)، وتربطه بحسابه وبكل دفعة. بعدها يظهر هنا الدخل بلا إعلان، ونتيجة كل حملة حتى الدفع.» |
| «نتائج إعلانات ميتا وجوجل» | «لأرى ما صُرف وما جاء لكل حملة دون أن تكتبه بيدك.» | «يأتي مع ربط «مدار»» | «يجلب «مدار» نتائج الحملات يومًا بيوم من حسابات الإعلانات. إلى أن يُربط، سجّل أرقام كل حملة من زر «عدّل الحملة».» |
| «أرقام صفحات السوشيال» | «لأعرف أي منصة تجلب الناس وأيها متوقفة.» | «يأتي مع ربط «مدار»» | «يجلب «مدار» المتابعين والوصول وأفضل منشور لكل منصة.» |
| «زيارات الموقع» | «لأعرف كم زائرًا صار عميلًا.» | «يحتاج تعديلًا في الموقع» | «يُضاف عدّاد زيارات للموقع والمنصة يحترم اختيار الكوكيز، ويصل رقمه إلى هنا وإلى «التقارير».» |

Failed-but-existing sources (`campaigns`, `income`, `ads`) are **not** listed as needs. They appear in the amber state with «أعد المحاولة».

### 4.5 Table «الحملات: من الإعلان حتى الدفع» (pure helper `V2L.mk.rows(campaigns, owners, filter, attribution)`)

Card header: «الحملات: من الإعلان حتى الدفع»; hint «اضغط أي حملة لتفاصيلها وأزرارها».

Sort: active first, then `spent` descending, then name.

**Desktop columns** (`<table class="mk-table">`, numeric cells aligned to the inline end, Arabic digits):
- «الحملة»: name, plus a small line with the owner: «لـ{owner_title}» or «للبروفيسور»;
- «المنصة»: label map `facebook`⇒«فيسبوك», `instagram`⇒«إنستجرام», `facebook_instagram`⇒«فيسبوك وإنستجرام», `google_ads`⇒«جوجل», `linkedin`⇒«لينكدإن», `youtube`⇒«يوتيوب», `tiktok`⇒«تيك توك», anything else shown as stored;
- «الحالة»: chip «نشطة» (green) / «موقوفة» (grey) / «انتهت» (ink outline) / «مسودة» (paper);
- «صُرف»: `moneyText(spent, currency)`;
- «زيارات»: `clicks`;
- «سجّلوا»: `leads`;
- «دفعوا»: `conversions`;
- «الدخل»: `moneyText(revenue_attributed, currency)`;
- «رجع»: ratio «٥٫٢», or «—» when `spent=0`. The ratio is coloured red (`#C8102E`) when < 1 and green when ≥ 3.

Rows with `spent>0` and all four result fields 0 show the chip «لم تُسجَّل نتائج» in place of the four numbers (cells merged), so they never read as a real zero.

Every row is a `<button>`-like row (`role="button"`, `tabindex=0`, min height 52 px, Enter/Space) ⇒ detail sheet (§5.1).

**Last row «بلا إعلان»** (always shown, styled `.mk-organic`):
- name «بلا إعلان», sub «البحث والمقالات والسوشيال والدعوات».
- If attribution is not ready, the merged cells read: «غير متاح بعد — المنصة لا تسجّل بعد من أين جاء كل دافع».
- If it is ready: «سجّلوا» = Σ `signups` and «دفعوا» = Σ `payers` of the non-ads channels (excluding `unknown`); «الدخل» = the money line per currency; «رجع» = «بلا صرف».

**Attribution-ready extra:** when `attribution.campaigns[]` has `campaign === 'c'+id`, the row gets a second line under the name: «عبر الرابط: سجّلوا {s} · دفعوا {p}». These numbers come from the platform and are never mixed with the typed ones.

- **Tablet 761–1179:** the columns are «الحملة» (with platform and status folded into its sub line) · «صُرف» · «سجّلوا» · «دفعوا» · «الدخل» · «رجع».
- **Mobile ≤760:** one card per campaign (`.mk-ccard`):
  - name + status chip;
  - owner/platform line;
  - a 3×2 mini grid: صُرف · زيارات · سجّلوا · دفعوا · الدخل · رجع;
  - the whole card is the tap target.
  - «بلا إعلان» is the last card.

**Empty and failure states:**
- Empty with «النشطة الآن»: «لا حملات نشطة الآن.» plus the link «اعرض كل الحملات».
- Empty with «كل الحملات»: `.v3-empty` with «لا حملات مسجّلة بعد» and «حملة جديدة».
- Loading: `.v3-empty` «…جارٍ جلب الحملات».
- Failed: «الحملات: غير متاح بعد» / «تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.» + «أعد المحاولة».

### 4.6 Link cards

1. **«إعلانات نديرها لأصحاب الدورات والكتب»** (source `ads`):
   - Body: «{N} أعمال لها رصيد إعلانات عندنا» (with `U`), then the balance per currency via `V2L.v2MoneyLine` (existing). Never one summed number across currencies.
   - Button `.v3-btn2` «افتح إعلانات الأعمال» ⇒ `V2_HOST.openSection('money','ads')`.
   - Empty: «لا أعمال لها رصيد إعلانات بعد». Failed: «غير متاح بعد» + «أعد المحاولة».
2. **«عملاء الإعلانات بالنتيجة»:**
   - Body: «حساب كل جهة تعلن عندنا وتدفع حسب النتيجة، وكشف حسابها، في «الشركة ورأس المال».»
   - Button «افتح عملاء الإعلانات» ⇒ `V2_HOST.openSection('company','adclients')`. `v2OpenSection` falls back to the first company tab when that tab key does not exist, so the integrator aligns the key with the company round.
3. **«اربط مدار»** (`.mk-madar`, the photo `v2/img/marketing.jpg` as a 16:9 header, cropped `object-fit:cover`):
   - Text: «مدار هو نظام التسويق الذي سيجلب إلى هنا نتائج الإعلانات وأرقام الصفحات وخطة النشر، فلا تكتبها بيدك. الربط في جولة قادمة.»
   - Status chip «قريبًا».
   - Button `.v3-btn2` «ماذا سيظهر هنا؟» ⇒ sheet titled «بعد ربط مدار», a list of what will appear (no numbers):
     - «نتائج إعلانات ميتا وجوجل لكل حملة يومًا بيوم»
     - «أرقام صفحات فيسبوك وإنستجرام ولينكدإن ويوتيوب وتيك توك»
     - «خطة النشر الأسبوعية وما ينتظر موافقتك»
     - «كشف «صُرف كم وجاء بماذا» لكل صاحب حملة»

     Single button «تمام».

---

## 5) Sheets (all through `window.openModal`, wrapped in `.v3m` like D3; ≥44 px targets, 52 px on mobile; never redrawn under an open sheet)

### 5.1 Campaign detail — title «حملة: {name}»
- **Lines:**
  - «المنصة»;
  - «الحالة»;
  - «المدة» («من {start} إلى {end}» / «من {start} حتى الآن» / «بلا تاريخ»);
  - «لمن الحملة» (owner, or «البروفيسور نفسه»; owners failed ⇒ «غير متاح بعد»);
  - «الجمهور» (if any).
- **Numbers grid:** «الميزانية» · «صُرف» · «زيارات» · «سجّلوا» · «دفعوا» · «الدخل» · «رجع», each with the row currency.
- **«الرابط الذي تضعه في الإعلان»:**
  - a read-only field with `https://elprofessor.net/?utm_source={src}&utm_medium=paid&utm_campaign=c{id}`, where `src` is the platform code (`facebook`/`instagram`/`google`/`linkedin`/`youtube`/`tiktok`/`other`);
  - the button «انسخ الرابط» (`navigator.clipboard.writeText`; fallback: select the field text; toast «نُسخ الرابط»).
  - Under it, when attribution is not ready: «سيُحتسب من جاء عبر هذا الرابط حين تبدأ المنصة تسجيل مصدر كل زائر.»
  - When attribution is ready: «جاء عبره هذا الشهر: سجّلوا {s} · دفعوا {p} · دخل {money line}», or «لم يأتِ عبره أحد هذا الشهر».
- **Actions** (`.acts`):
  - main «عدّل الحملة» ⇒ §5.2;
  - «أوقفها» / «شغّلها» (status active ⇄ paused; for `completed`/`draft` the button reads «شغّلها»), via the same confirm sheet as §4.3 (for «شغّلها» the warning reads «هذا لا يشغّل الإعلان نفسه…»);
  - «انسخ الكشف» ⇒ copies the statement (§5.4);
  - «احذف» (`.btn-warn`, last) ⇒ §5.3.

### 5.2 Create / edit — title «حملة جديدة» / «تعديل: {name}»
One stage, with fields in pairs (`.row2`) on desktop/tablet and one column on mobile:
- «اسم الحملة» (required, ≤255; empty ⇒ «اكتب اسم الحملة»).
- «لمن الحملة»: select with «البروفيسور نفسه» first, then each `ads` item as «{title} — {دورة|كتاب}». Untitled items show «عمل بلا عنوان ({owner_id})».
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
- **Owner:** if «لمن الحملة» changed (or on create, when not the default), a second call `PUT /v2/marketing/campaigns/{id}/owner` (§8) runs after the campaign call succeeds.
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

- **Top:** the «اربط مدار» card in its wide form (photo at the inline start, text and button at the end; stacked on mobile).
- **Grid** `.mk-social` (desktop 3 columns, tablet 2, mobile 1) with five cards in this order: «فيسبوك» · «إنستجرام» · «لينكدإن» · «يوتيوب» · «تيك توك». Each card has:
  - a round letter mark («ف», «إ», «ل», «ي», «ت») in brand wine on paper, plus the name;
  - the big line **«غير متاح بعد»** and the small line «المتابعون والوصول وأفضل منشور يأتون مع ربط «مدار»»;
  - a fact line from the typed campaigns (pure helper `V2L.mk.byPlatform(campaigns)`):
    - «من الحملات المسجّلة هنا: {N} حملات · صُرف {money line} · دفعوا {conversions}»;
    - `facebook_instagram` rows count for both cards and are marked «(مشتركة مع إنستجرام)» / «(مشتركة مع فيسبوك)»;
    - no rows ⇒ «لا حملات مسجّلة على هذه المنصة»;
    - campaigns failed ⇒ «الحملات: غير متاح بعد»;
  - the button `.v3-btn2` «كيف يُربط؟» ⇒ the «أرقام صفحات السوشيال» explanation sheet (§4.4).
- **Bottom:** the «العقل يحتاج» block (same component as §4.4, filtered to social and ads needs).

---

## 7) Tab «خطة النشر» (`v2mk_plan`)

- **Layout:** `.v3-two` on desktop (start: site articles; end: «مدار» plan card); stacked on tablet and mobile.
- **Card «نُشر على الموقع هذا الأسبوع»** (source `published`):
  - The list `.v3-list`, newest first: title, «{dateText(published_at)} · {agoText}», and the link button «افتح على الموقع». The link is `https://elprofessor.net/article.html?id={id}` in a new tab with `noopener`, the same pattern as the content screen (`index.html:4684`).
  - Empty: «لم يُنشر مقال على الموقع في آخر ٧ أيام.»
  - Under the list, the drafts line: «مسودات مقالات لم تُنشر بعد: {drafts}» (shown only when `drafts>0`), with the button «افتح المحتوى» ⇒ `V2_HOST.openSection('content')`. Approving and publishing stay in «المحتوى»; nothing is duplicated here.
  - Failed: «مقالات الموقع: غير متاح بعد» + «أعد المحاولة».
- **Card «خطة النشر على السوشيال»:**
  - The «مدار» card body: «تُجهَّز خطة الأسبوع لكل منصة، وتنتظر موافقتك قبل النشر، بعد ربط «مدار».» + chip «قريبًا» + «ماذا سيظهر هنا؟».
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
| `GET /api/v2/marketing/owners` | Ensures the table (below). Rows whose `campaign_id` still exists in `campaigns` ⇒ `{ok:true, items:[{campaign_id, owner_kind, owner_id, owner_title, updated_at, updated_by}]}`. |
| `PUT /api/v2/marketing/campaigns/<int:cid>/owner` | Body `{owner_kind, owner_id?, owner_title?}`. `owner_kind ∈ {'platform','course','book'}`, else 400 «اختر صاحب الحملة». For `platform`, id/title are stored empty. For course/book: `owner_id` must match `V2_ID_RE` (else 400 «العمل غير صالح»), and `owner_title` is trimmed to ≤200. Unknown campaign ⇒ 404 «الحملة غير موجودة». Upsert, `updated_by=_actor_email()`, `updated_at=utcnow ISO`; `_audit('marketing.campaign_owner', target='campaign:{cid}', meta={owner_kind, owner_id})` **on success only**. ⇒ `{ok:true, item:{…}}`. |
| `GET /api/v2/marketing/attribution?month=YYYY-MM` | `month` optional (default current UTC month); bad ⇒ 400 «الشهر غير صالح». ⇒ `_v2_get('/api/bridge/attribution/summary', {'month': m})`. The platform's 404 passes through as 404 (the UI reads it as `closed` = «غير متاح بعد»); 401/403 ⇒ 502 (existing `_v2_mask_auth`). One call, no retry. |

**Table** (created lazily by every route through `_ensure()`, idempotent):
```sql
CREATE TABLE IF NOT EXISTS v2_campaign_owner (
  campaign_id INTEGER PRIMARY KEY,
  owner_kind  TEXT NOT NULL,
  owner_id    TEXT NOT NULL DEFAULT '',
  owner_title TEXT NOT NULL DEFAULT '',
  updated_at  TEXT NOT NULL,
  updated_by  TEXT NOT NULL DEFAULT ''
)
```
- It runs through `db.session.execute(text(...))` + commit, and is portable between SQLite and Postgres.
- No change to the `Campaign` model and no change to `/api/campaigns`.

---

## 9) Platform needs

**P1: per-person and per-payment source (attribution). Required for number 3, the «بلا إعلان» row, and «جاء عبر الرابط».**
- This is the same need the «التقارير» round has for «الناس جايين منين» and the visit-to-payment journey. **Build one bridge for both**; if the reports spec defines a shape, the integrator keeps one and both screens read it.
- **Capture (platform-app + site):**
  - On first landing, read `utm_source`, `utm_medium`, `utm_campaign`, `ref`, the invite code, and the referrer host.
  - Keep the first touch for 30 days in local storage, inside try/catch, and only under the cookie choice «أوافق على الكل». With «الأساسية فقط», store only `utm_campaign`/`ref`, which come from the link itself.
  - The static site keeps these query params on its links to the app.
  - Send `first_touch: {source, medium, campaign, referrer_host, landing_path, at}` (each ≤120 chars, sanitized) with register and with order creation.
  - Store `users.first_touch` only if it is absent, and stamp `payments.first_touch` from the user at order time.
- **Bridge:** `GET /api/bridge/attribution/summary?month=YYYY-MM`, guarded by `x-elp-metrics-secret`, read only:
  ```json
  {
    "ok": true,
    "month": "2026-11",
    "captured_since": "2026-11-02T10:00:00Z",
    "channels": [
      {"key": "ads", "label": "إعلانات", "signups": 12, "payers": 4,
       "totals": [{"currency": "EGP", "amount": 3400.0}]},
      {"key": "search", "label": "بحث", "signups": 30, "payers": 9, "totals": [...]},
      {"key": "social", "label": "سوشيال", ...},
      {"key": "invite", "label": "دعوات", ...},
      {"key": "trainer_code", "label": "كود مدرّب", ...},
      {"key": "affiliate", "label": "توصية", ...},
      {"key": "direct", "label": "دخلوا مباشرة", ...},
      {"key": "unknown", "label": "قبل بدء التسجيل", ...}
    ],
    "campaigns": [
      {"campaign": "c12", "source": "facebook", "signups": 9, "payers": 3,
       "totals": [{"currency": "EGP", "amount": 2100.0}]}
    ]
  }
  ```
- **Channel rules, in order:**
  1. `payments.attribution=='trainer'` ⇒ `trainer_code`.
  2. Affiliate `ref` ⇒ `affiliate`.
  3. Invite code ⇒ `invite`.
  4. `utm_medium ∈ {cpc, paid, ads, paid_social}` ⇒ `ads`.
  5. Referrer google/bing/yahoo/duckduckgo ⇒ `search`.
  6. Referrer facebook/instagram/linkedin/youtube/tiktok/t.co/x.com/whatsapp ⇒ `social`.
  7. No source and no referrer ⇒ `direct`.
  8. Anything before capture started ⇒ `unknown`.
- **Totals** follow the exact rules of `/bridge/income/by-service`:
  - paid in full, or partially refunded at the net amount;
  - `ads_deposit` excluded;
  - per currency, never converted;
  - the month by `paid_at`, otherwise `updated_at`.
- `captured_since` = the timestamp of the first stored `first_touch`, or null.
- `campaigns[]` groups payments and signups by `utm_campaign` (the dashboard link uses `c{id}`).
- **Tests:**
  - secret required;
  - the shape;
  - currencies never summed;
  - refunds netted;
  - no stored touch ⇒ `unknown`;
  - the cookie choice respected.

**P2 (optional, same round if cheap): monthly spend per owner in the ads overview.**
- `GET /api/bridge/ads-ledger?month=YYYY-MM` adds `month_spend:[{currency, amount}]` per row (sum of `entry=='spend'` in the month).
- With it, the ads card gets the line «صُرف من أرصدة أصحاب الأعمال هذا الشهر: {money line}». Without it, the line is **not shown** (never 0).

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
| `mk.board(rows, filter, extra)` | ⇒ `{numbers:[4], primary, others[]}` | §4.2; `extra = {income, attribution}` each `null` when not ready ⇒ `na:true` + exact texts. |
| `mk.ratio(rev, spent)` | ⇒ `null` or a number to one decimal | `spent<=0` ⇒ null. |
| `mk.ratioText(r, cur)` | ⇒ «كل جنيه رجع ٣٫٧» | unit map §4.2. |
| `mk.brain(rows, todayISO, skipped)` | ⇒ `{items:[{kind, id, text, line, btn, action}], empty?}` | §4.3 priorities; `skipped` = a set of `kind_id`. |
| `mk.sources(states)` | ⇒ `{seen:[{key,label,state}], needs:[{key,title,why,chip,how}]}` | §4.4. |
| `mk.rows(rows, owners, filter, attribution)` | ⇒ table view model + organic row | §4.5. |
| `mk.byPlatform(rows)` | ⇒ `{facebook:{n, spent[], conversions, shared}, …}` | §6. |
| `mk.link(id, platform)` | ⇒ URL string | §5.1. |
| `mk.statement(row, owner, todayISO)` | ⇒ text | §5.4. |
| `mk.validate(form)` | ⇒ `{ok, body, error}` | §5.2 rules, Arabic errors. |
| `mk.STR` | all visible strings in one object | the copy lint test reads it. |

---

## 11) Visual rules (`v2s/marketing.css`, `.mk-*` only)
- **Tokens:** wine `#9E2B4E`, paper `#FBFAF7`/`#F6F1EA`, ink `#21262E`, red `#C8102E` only for ratios < 1 and failure dots; green as in D3. Fonts Cairo/IBM Plex, same as D3.
- **Cards and spacing:**
  - cards: white, 18 px radius, 1 px `var(--line)`, 16–18 px padding;
  - gaps: 14–16 px.
  - No old classes (`.kpis`, `.kpi`, `.inboxwrap`, `.panel`, `.drawer`, `.row`, `.status`, `.policy`) inside any marketing view.
- **Sizes:** targets ≥44 px; on mobile, buttons and rows ≥52 px. No horizontal page scroll at 390; the desktop table never exceeds its card (`table-layout:fixed`, `overflow-wrap:anywhere` on names).
- **Real photos:** `v2/img/marketing.jpg` (the «مدار» card) and `v2/img/brain-avatar.jpg` (the brain card). No new images.
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
   - the Dockerfile copies `v2_*_routes.py`;
   - the `SECTIONS` marketing entry equals §2;
   - with the flag off, `viewMarketing` and the old loader are byte-identical to `7d1aa83`, compared by hashing those functions.

**node (via `uiharness/v2_node.py`):**

8. `board`:
   - per-currency sums;
   - an SAR row never enters the EGP total and shows in `others`;
   - ratio only with spent>0;
   - cost only with conversions>0;
   - 0 rows ⇒ «لا حملات مسجّلة»;
   - number 3 ⇒ «غير متاح بعد» without attribution, and with attribution excludes `ads` and `unknown`;
   - the income note uses the per-currency line.
9. `brain`:
   - priority order;
   - `skipped` respected;
   - every number in the text equals the row values;
   - `best` only when nothing else applies;
   - `empty`/`none` texts;
   - no suggestion from non-active rows.
10. `sources`: needs list order; a ready attribution removes its need; `error` ≠ need.
11. `rows`:
    - sort order;
    - the «لم تُسجَّل نتائج» chip;
    - organic row texts in both modes;
    - «عبر الرابط» only from `campaigns[c{id}]`.
12. `byPlatform`: shared facebook_instagram counted in both and marked.
13. `link`, `statement` (skips empty fields, keeps zeros, Arabic date), `validate` (name required, negative, end<start, «أخرى» requires a name, Arabic digits parsed).
14. **Copy lint over `mk.STR` and the rendered HTML of each tab** (jsdom-free: render functions return strings):
    - no «يقوّم»;
    - no Latin letters in our own strings (`mk.STR` and fixed labels) except the campaign URL; values typed by the founder (campaign names, a stored platform like «Google Ads») are data and are shown as stored;
    - no headline starting with «الذكاء»;
    - no «CAC/ROAS/Impressions/Clicks/API/utm» visible;
    - every unavailable value reads exactly «غير متاح بعد».

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
    2. active EGP losing (1.2, `ended` false);
    3. active with no results;
    4. paused SAR;
    5. completed USD.
  - It also seeds one owner link, four published articles (two in the last 7 days) and three drafts.

**Shot list (each at d/t/m; names `mk-{nn}-{name}-{d|t|m}.png`):**
1. `campaigns`: full tab, «النشطة الآن».
2. `campaigns-all`: «كل الحملات» (SAR chip visible).
3. `campaigns-attr`: attribution on (number 3 lit, «بلا إعلان» row filled, «عبر الرابط» line).
4. `campaigns-down`: campaigns 502 + income 502 + ads 502 (warn strip, «غير متاح بعد», «حملة جديدة» disabled).
5. `campaigns-empty`: no campaigns (brain «لا حملات مسجّلة…»).
6. `brain-stop`: the «أوقفها» confirm sheet.
7. `detail`: the campaign detail sheet (link + «انسخ الرابط»).
8. `edit`: the edit sheet with «أخرى» selected (text box visible) and USD preselected on row 5.
9. `delete`: the delete confirm.
10. `needs-how`: the «كيف يُربط؟» sheet for attribution.
11. `madar`: the «ماذا سيظهر هنا؟» sheet.
12. `social`: the social tab.
13. `plan`: the plan tab.
14. `plan-down`: the plan tab with `published` 500.
15. `old-link`: open `#marketing` ⇒ lands on «التسويق / الحملات» with the new look.
16. `flag-off` (desktop only): the old marketing screen unchanged.

**Checks on every shot (fail ⇒ exit 1, D3 style):**
- `document.documentElement.scrollWidth <= innerWidth`;
- no `.kpis/.inboxwrap/.panel/.drawer/.policy` inside `#view` (except shot 16);
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
- the old-data trap (USD default) and how the screen shows it;
- the test counts;
- the shot list.

## 15) Out of scope
- Connecting «مدار», Meta, Google, or any social API (later round).
- Sending statements to owners.
- Recording owner ad spend (P3).
- Rewriting the «التسويق» tile in `v2Tiles` (shared).
- Marketing decision cards in «ابدأ القرارات». `V2SEC.marketing.cards()` returns the §4.3 items in the `v2Card`-like shape `{kind, title, line, btn, open()}` so the home round can pick them up without editing this file.
- Any deploy or push.
