# Final round: the «التقارير» section, rebuilt on the approved concept

**Founder order (2026-10-30):** «ابدأ الجولة… الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا». This is final work, not a draft.
**Concept:** `dash-canvas/project/Reports.dc.html`. It covers:
- the whole platform or one section at a time;
- «شغّال / واقف / فرصة» from the brain;
- the journey from visit to payment;
- where people come from;
- every section in one line;
- «يصلك هذا التقرير كل أحد صباحًا».

Plan row D4 in `DASHBOARD-PLAN-2026-10-30.md`.
**Worktree / branch:** `.worktrees/reports` · `final-reports`. Everything new sits behind `DASH_V2_ENABLED`. With the switch off, the dashboard is byte-identical to today, and the old `viewAnalysis` stays exactly as it is.

## 0) The decision in one paragraph
The old section has one tab, «تحليل الطلب» (`analysis`, `index.html:2822 viewAnalysis`). It is a read-only analysis of chat questions. **Nothing of it survives in the old look.** The section becomes three new tabs:
- **«التقرير»**: the concept board.
- **«ما يسأل عنه الناس»**: the old demand analysis, rebuilt in the new style, with every feature kept.
- **«تقرير الأحد»**: the weekly report view.

**No «كل السجلات» tab**: tab 2 covers everything the old screen did.

All numbers on tabs 1 and 3 come from **one new server route** that gathers existing sources, so the screen and a future Sunday message read the same numbers. Anything the platform does not record yet shows «غير متاح بعد» and is listed under **Platform needs**:
- visits;
- each person's and each payment's source;
- questions per period;
- «فتحوا ملفًا أو دورة»;
- ratings;
- the Sunday delivery.

The brain lines are **deterministic sentences built only from those numbers**. There is no AI call.

---

## 1) Files (parallel-safety rules)
| File | New/edit | What |
|---|---|---|
| `dashboard-cloud/v2s/reports.js` | new | All rendering for the three tabs. It registers `window.V2SEC.reports = {owns, render}`. |
| `dashboard-cloud/v2s/reports.css` | new | Styles, all under `.v2r-*`. It reuses the existing `.v3-*` classes from `v2-d3.css` (cards, period switch, buttons, empty/warn states, brain avatar) and does not edit them. |
| `backend/v2_reports_routes.py` | new | `register(app, g)` with two GET routes (§8). Pure builders, testable without Flask. |
| `backend/app.py` | 1 line | `import v2_reports_routes as _v2r; _v2r.register(app, globals())  # v2s:reports`, placed right before `# ---- v2 section routes end`. If the marker is missing, create it after the last v2 route (after `v2_book_request_patch`, before `@app.route('/api/platform-pnl'`). |
| `dashboard-cloud/index.html` | block only | Inside `<!-- v2 sections begin -->` … `<!-- v2 sections end -->` (create it right after the `v2-d2.js` script tag if missing): `<link rel="stylesheet" href="v2s/reports.css">` and `<script src="v2s/reports.js"></script>`, one line each, alphabetical by key. |
| `dashboard-cloud/v2-logic.js` | own entry + helpers | The `reports` entry in `SECTIONS` (§2). Pure helpers at the end of the file inside `// ===== v2s:reports =====` … `// ===== /v2s:reports =====`, exported as `V2L.v2r = {...}`. |
| `backend/tests/test_v2s_reports.py` | new | pytest + node (§10). |
| `backend/tests/uiharness/reports_fixtures.py` | new | Fake platform subclass + SQLite seed for this section. |
| `backend/tests/uiharness/v2_shots_reports.py` | new | Shots (§11). Imports helpers from `v2_shots.py` and does not edit it. |

### shared_edits (unavoidable, minimal, identical for every section — if another section already merged the same line, do not add it again)
1. **`index.html` `renderView()`**, the generic hook. One line right after the D3 hook line (`if(window.V2_ON&&window.V2D3&&V2D3.owns(current))return V2D3.render(current,v);`):
   ```js
   if(window.V2_ON&&window.V2SEC){const _k=Object.keys(V2SEC).find(function(k){return V2SEC[k].owns(current);});if(_k)return V2SEC[_k].render(current,v);}
   ```
   In the shell-class line, after `if(window.V2D3&&V2D3.owns(current))ap.classList.add('v2-bare');`, add:
   ```js
   if(window.V2SEC&&Object.keys(V2SEC).some(function(k){return V2SEC[k].owns(current);}))ap.classList.add('v2-bare');
   ```
2. **`Dockerfile` and `deploy/Dockerfile.coolify`.** Both copy files one by one, so without this edit the new files never ship. Add two lines next to the existing v2 COPY lines:
   - `COPY dashboard-cloud/v2s /app/dist/v2s`
   - `COPY backend/v2_*_routes.py /app/`
3. **`backend/tests/test_xss_hardening.py:628`** has a script-src allowlist regex. Add `|v2s/[a-z_]+\.js` inside the negative lookahead. Without it, the new `<script src="v2s/reports.js">` fails the test.

---

## 2) The section entry in `SECTIONS` (the only change in the map)
```js
{ key: 'reports', label: 'التقارير', img: 'reports', desc: 'ما الذي يعمل، وما الذي توقّف، وأين الفرصة', tabs: [
  T('report', 'التقرير', 'analysis'),
  T('demand', 'ما يسأل عنه الناس', 'v2r_demand'),
  T('sunday', 'تقرير الأحد', 'v2r_sunday')
] },
```
**Why the first tab keeps the module name `analysis`:**
- The board tile already goes to `T.reports.dest = 'analysis'` (`v2-logic.js:317`, outside our entry).
- Old links `#analysis` and `go('analysis')` resolve through `sectionFor('analysis')`.
- All three now land on «التقرير», with no edit to the tile code or `ALIASES`.
- `V2SEC.reports.owns(mod)` returns true for `analysis`, `v2r_demand` and `v2r_sunday` **only when `window.V2SHELL && V2SHELL.on`**. So with the switch off, and for any non-admin role, `analysis` still draws the old `viewAnalysis`.
- The courses screen's internal «demand» tab reads `EP.data.analysis` (the loader), not the view, so it is untouched.

Tile line: unchanged (`'شغّال · واقف · فرصة'`, no count). The tile has no badge: reports never wait on a decision.

---

## 3) Shared look (all three tabs)
- **Brand:**
  - عنّابي `#9E2B4E` (main buttons, the funnel's first bar, active chips);
  - paper `#FBFAF7` / `#F6F1EA`;
  - ink `#21262E` (brain strip background, active period);
  - green `#1E6B4A` on `#EEF6F1` for «▲»/«ينمو»;
  - amber `#8A4B00` on `#FCF1E3` for «▼»/«ثابت»;
  - red `#A3122A` on `#FBE9EC` only for «بلا عرض» and complaints.
- **Fonts:** Cairo 800 for numbers and headings, IBM Plex Sans Arabic for body text. All digits are Arabic-Indic via `V2L.util.ar/fmt`, with «٬» thousands and «٪».
- **Targets:** ≥ 44px; every button 52px tall on mobile (≤ 600px). No horizontal page scroll at 390px. Chip rows scroll inside their own `overflow-x:auto` box.
- **Breakpoints (viewport):**
  - **≥ 1400 (desktop 1440):** concept layout, with the lower row in three columns (chart 1.25 · sources 1 · section lines 1.1).
  - **1024–1399:** the chart takes the full width, then sources and section lines sit in two columns.
  - **600–1023 (tablet 820):** one column. The funnel becomes a vertical list. The brain strip stacks its three lines.
  - **< 600 (mobile 390):** one column. The period switch is full width (three equal 52px buttons). The scope chips scroll horizontally inside their row. «نزّل التقرير» and «حدّث» sit side by side, each 50% wide.
- **Brain avatar:** `v2/img/brain-avatar.jpg` (existing). No new images.
- **States, the same everywhere:**
  - Loading: `.v3-empty` with «…جارٍ جمع التقرير».
  - Route failed entirely: `.v3-empty` «التقرير: غير متاح بعد» / «تعذّر الجمع الآن، فلا تعتبر الأرقام صفرًا.» + «أعد المحاولة».
  - Some sources failed: `.v3-warn` «تعذّر جلب: {labels} — ما يظهر ناقص، وليس معناه أنه لا شيء».
  - Any single missing number: the text «غير متاح بعد» in grey (`.v3-big.na` style). **Never `0`, never `—`.**

Source labels for the warn strip:
| key | label |
|---|---|
| `ledger` | «دفتر الإيرادات» |
| `users` | «الحسابات الجديدة» |
| `market` | «طلبات السوق» |
| `content` | «مقالات الموقع» |
| `disputes` | «النزاعات» |
| `chat` | «أسئلة المحادثة» |
| `funnel` | «رحلة الزائر» |

`funnel` is listed only when the platform route exists and failed. When the route is simply absent, it is not a failure.

---

## 4) Tab «التقرير» (`analysis`, default)

### 4.1 Header controls (one row on desktop; wraps on tablet and mobile)
- **Scope chips** (`role="tablist"`, `aria-label="القسم"`): «المنصة كلها» (default) · «الملفات» · «الدورات» · «الكتب» · «السوق» · «المحتوى» · «التسويق».
  - Keys: `all, files, courses, books, market, content, marketing`.
  - Active chip: ink background, white text.
- **Period switch:** reuse `.v3-seg/.v3-pb`, `aria-label="الفترة"`. Options «الأسبوع» (`week`, 7 days) · «الشهر» (`month`, 30 days, default) · «٣ أشهر» (`quarter`, 91 days = 13 full weeks).
  - The choice is remembered in `localStorage['v2r_period']` and `['v2r_scope']` (try/catch).
- **Period line** under the controls, `.v3-ptxt`, from `window.label` + `prev.label`. Examples:
  - «آخر ٣٠ يومًا (من ١ إلى ٣٠ أكتوبر) مقارنة بالثلاثين يومًا التي قبلها»
  - «آخر ٧ أيام … مقارنة بالأيام السبعة التي قبلها»
  - «آخر ١٣ أسبوعًا … مقارنة بالثلاثة عشر أسبوعًا التي قبلها»
- **Buttons:**
  - «نزّل التقرير» (`.v3-btn1`) calls `window.print()`. The print stylesheet (§4.8) hides the shell and controls. No network, no file generation.
  - «حدّث» (`.v3-btn2`) re-fetches the summary with `fresh=1`.

### 4.2 Brain strip «ملخص العقل» (`aria-label="ملخص العقل"`)
- **Look:** ink `#21262E` background, radius 24, the avatar 64px. Three columns on ≥1024, stacked below that.
- **Each line** comes from `summary.brain[i]`:
  - the label in its colour: «شغّال» `#8FD3B0`, «واقف» `#F2B33D`, «فرصة» `#F0A0B8`;
  - the sentence `text` (white, 15px);
  - when `action` exists, **one** button (`.v3-btn2` on dark, min 44px);
  - a disclosure «على أي أساس؟» (button ≥ 44px). It lists `basis[]` as «{label}: {value}», each with its source label from §3, plus `window.label`.
- **When `text` is null:** the line shows `empty_text` in grey (for example «لم يصعد شيء بوضوح في هذه الفترة.»), or «غير متاح بعد» + `na_reason` when the needed source failed.
- **Action buttons call existing navigation only:** `V2_HOST.openSection(section, tab)` (= `v2OpenSection`). Labels are listed in §7 (for example «افتح الدورات»). No decision is taken from this strip.
- **Scope:** only candidates of the selected scope are considered (§7). For `marketing`, all three lines read «غير متاح بعد» with `na_reason` «تكتمل مع ربط الحملات في قسم التسويق».

### 4.3 Card «من الزيارة إلى الدفع» (`summary.funnel`)
- **Header:** title plus a short period text («آخر ٣٠ يومًا مقارنة بما قبلها»).
- **Layout:**
  - ≥1024: five columns. Each column has the label (14px muted), the number (Cairo 28px), the change line, and a bar.
    - Bar heights 70/52/38/26/18px, using the concept's colours `#9E2B4E #B44E6E #C97590 #DB9DB1 #EBC6D2`.
    - A stage with no number gets a dashed empty bar.
  - <1024: a vertical list. Each row shows the label, the number and the change line, with a horizontal bar sized by `cur / max(cur of known stages)`.
- **Stages, whole platform (key → label → interim source):**
  | key | label | source today |
  |---|---|---|
  | `visits` | «زاروا المنصة» | none, «غير متاح بعد» |
  | `asked` | «سألوا سؤالًا» | none for a period, «غير متاح بعد» |
  | `signed_up` | «سجّلوا حسابًا» | platform users (§8.1, source 2) |
  | `opened` | «فتحوا ملفًا أو دورة» | none, «غير متاح بعد» |
  | `paid` | «دفعوا» | dashboard ledger: number of payment rows in the window |

  When the funnel bridge exists (Platform need N3), each stage takes its platform value instead. `paid` then uses `paid_people`.
- **Change line:**
  - When `prev` is known and `prev > 0`: «▲ {pct}٪» (green), «▼ {pct}٪» (amber), or «كما هو» (|pct| < 1).
  - `prev == 0` and `cur > 0`: «جديد».
  - `prev` unknown: no change line.
- **Conversion part:** appended to the change line («· ٤٠٪ ممن سألوا») only when this stage and the previous **known** adjacent stage both have numbers. Phrases:
  - `asked`: «من الزوار»
  - `signed_up`: «ممن سألوا»
  - `opened`: «من المسجّلين»
  - `paid`: «ممن فتحوا»
- **Interim `paid` sub-line:** «عمليات دفع، وقد يدفع الشخص أكثر من مرة».
- **Footnote** when any stage is unavailable: «الخانات الفارغة تكتمل حين تسجّل المنصة الزيارات ومصدر كل زائر.»
- **Section scopes** replace the five stages with the section's own journey. Labels below; anything without a source shows «غير متاح بعد». Title: «رحلة {اسم القسم}».
  - **files:** «سألوا سؤالًا» (n/a) → «فتحوا ملفًا» (n/a) → «دفعوا» (ledger `experts` count)
  - **courses:** «زاروا صفحة دورة» (n/a) → «سجّلوا في دورة» (n/a) → «دفعوا» (ledger `courses` count)
  - **books:** «زاروا صفحة كتاب» (n/a) → «ضغطوا «اشترِ»» (n/a) → «دفعوا» (ledger `books` count)
  - **market:** «طلبات جديدة» (market `new`) → «جاءها عرض» (market `with_offers`) → «تمّ الاتفاق» (market `matched`)
  - **content:** «مقالات نُشرت» (content `published`) → «زيارات المقالات» (n/a) → «حسابات جاءت من مقال» (n/a)
  - **marketing:** «صُرف على الإعلانات» (n/a) → «زيارات من الإعلانات» (n/a) → «دفعوا» (n/a), with the footnote «تكتمل مع ربط الحملات في قسم التسويق»

### 4.4 Card «يومًا بيوم» (`summary.daily`; title «أسبوعًا بأسبوع» for `quarter`)
- **Chart:** inline SVG (`viewBox 0 0 560 300`, `width:100%`, mobile height 220). No library.
  - **Series 1, «الدخل بالجنيه»:** EGP only, solid ink line `#21262E` 2.5px with a light area fill. It comes from `daily.rows[].income_egp`.
  - **Series 2, «حسابات جديدة»:** burgundy `#9E2B4E` 3px line on its own right-hand scale. It comes from `daily.rows[].signups`. When `users` is not complete for the window, the series is hidden and the legend shows «حسابات جديدة: غير متاح بعد».
  - **Visitors:** the legend always shows a third item, «الزوار: غير متاح بعد», until the funnel bridge sends `by_day[].visits`. It then becomes a burgundy line, and signups move to a dashed line.
- **Axes:** four light grid lines (`#F0EAE1`). Bottom labels only at the first, middle and last bucket («١ أكتوبر»).
- **Interaction:** tapping or hovering a bucket shows a small ink tooltip «{التاريخ}: {الدخل} · {n} حسابًا» (keyboard: the SVG has `tabindex=0` and arrow keys move between buckets).
  - `aria-label` example: «الدخل والحسابات الجديدة في آخر ٣٠ يومًا».
- **Foreign currency:** when `daily.income_other` is non-empty, a line under the chart reads «دخل بعملة أخرى في الفترة: {٣٠ دولار · ١٠٠ ريال}». It is never converted.
- **Empty:** «لا دخل ولا حسابات جديدة في هذه الفترة».
- **Section scope:** income for that section only (the ledger service), with no signups line. `market`, `content` and `marketing` show «غير متاح بعد» and the reason «لا يوجد دخل يومي لهذا القسم».

### 4.5 Card «من أين يأتي الناس» (`summary.origins`)
The concept's «الناس جايين منين» is colloquial; the founder rule is standard Arabic. The card has three blocks, each «غير متاح بعد» until Platform needs N1 and N3 ship:
1. **«القنوات»:** bars per channel. Labels: «بحث جوجل», «فيسبوك وإنستجرام», «واتساب», «دخلوا مباشرة», «دعوات الخبراء», «مواقع أخرى». Each bar shows the share of signups as «{pct}٪» with the count in its tooltip.
2. **«البلاد»:** chips «مصر ٦٤٪»… (share of signups), top 6 plus «بلاد أخرى».
3. **«أكثر الصفحات التي جاءت بالناس»:** top 3 pages with visit counts.

Interim body: the block titles, «غير متاح بعد» under each, and one line: «تكتمل حين تسجّل المنصة مصدر كل زائر وكل دفعة.» No invented split.

### 4.6 Card «كل قسم في سطر» (`summary.sections`)
- **Row:** name (flex 1) · value (Cairo 800) · chip (`.st`) · chevron. The whole row is a button ≥ 52px. Clicking it sets the scope chip to that section (same page, filtered). Inside a section scope, the card shows only that row expanded, plus a button «افتح {القسم}».
- **Rows:**
  | key | label | value | chip | under-line | «افتح» target |
  |---|---|---|---|---|---|
  | `files` | «ملفات الخبراء» | EGP income in the window from the ledger service `experts` («١١٢٬٤٠٠ جنيه») | trend | «تشمل الاستشارات العادية» (D3 rule) | `files` |
  | `courses` | «الدورات» | ledger `courses` | trend | — | `courses` |
  | `books` | «الكتب» | ledger `books` | trend | — | `books` |
  | `market` | «سوق الخدمات» | «{n} طلبًا جديدًا» (market `new`) | «{u} بلا عرض» (red if > 0, otherwise grey «كلها جاءها عرض») | — | `market` |
  | `content` | «المحتوى» | «{n} مقالًا نُشر» (content `published`) | «الزيارات: غير متاح بعد» (grey) until N3 | — | `content` |
  | `satisfaction` | «رضا العملاء» | «غير متاح بعد» until N5 | `V2L.util.U(d, [«نزاع مفتوح», «نزاعان مفتوحان», «نزاعات مفتوحة», «نزاعًا مفتوحًا»])` (red if > 0; «لا نزاع مفتوح» grey at 0) from `disputes.total` (open now, not per window) | — | `disputes` |

  - When a value has foreign currency, it adds «· وبعملة أخرى» and the tooltip lists the amounts.
  - Arabic counting forms use `V2L.util.U` (for example «طلب واحد», «طلبان», «طلبات», «طلبًا»).
- **Trend chip** (`trend.key` → text and tone):
  | key | rule | text | tone |
  |---|---|---|---|
  | `up` | pct ≥ +5 | «ينمو {pct}٪» | green |
  | `down` | pct ≤ −5 | «يتراجع {pct}٪» | amber |
  | `flat` | −5 < pct < +5 | «ثابت» | amber-light |
  | `new` | prev 0, cur > 0 | «جديد» | green |
  | `none` | both 0 | «لا بيع» | grey |
  | `na` | source failed | «غير متاح بعد» | grey |

  The percentage is computed on EGP only. When any foreign currency exists in either window, the chip's tooltip says «النسبة بالجنيه فقط».
- **Footer line:** `summary.delivery.text`. Today that is «إرسال التقرير كل أحد: لم يُفعَّل بعد» plus a link-button «افتح تقرير الأحد», which opens tab `sunday`. When the delivery bridge ships (N6) and reports `enabled:true`, the line becomes «يصلك هذا التقرير كل أحد صباحًا».

### 4.7 Scope = «التسويق»
The brain strip, funnel and chart show «غير متاح بعد» with the reason «تكتمل مع ربط الحملات في قسم التسويق». The section-lines card shows one line, «التسويق: افتح قسم التسويق لأرقام الحملات», with a button «افتح التسويق» (`openSection('marketing')`). Reports does not read the marketing tables, because the marketing section owns them and two readings of one number are forbidden.

### 4.8 Print (`@media print` in `reports.css`)
- Hide the shell, side menu, tabs, controls, buttons and disclosures. Paper background, ink text, no shadows.
- Print header (hidden on screen): «البروفيسور · تقرير {النطاق} · {window.label}», plus «أُعدّ في {generated_at بتوقيت القاهرة}».
- Brain lines print with their basis lists expanded.
- The chart prints as is (SVG).
- Cards use `page-break-inside: avoid`.

---

## 5) Tab «ما يسأل عنه الناس» (`v2r_demand`): the old screen, rebuilt
**Data:** the existing loader `EP.ensure('analysis')` → `GET /api/platform-chat-insights` (→ `/api/bridge/chat-insights`). The response is read as is (`total, needs_expert, needs_expert_rate, anonymous, authed, by_segment, by_country, by_category, by_subcategory, by_intent, unmet, classified, unclassified, recent_questions[≤40], expert_opinions{requested, paid, conversion_rate}`). No new route.
**States:**
- `EP.state.analysis === 'loading'|'idle'`: skeleton «…جارٍ جلب الأسئلة».
- `'error'`: `.v3-empty` «أسئلة المحادثة: غير متاح بعد» / «تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.» + «أعد المحاولة» (`EP.reload('analysis')`).
- Ready with `total === 0`: «لم يصل أي سؤال بعد».

**Layout, top to bottom (desktop: blocks 3–4 in two columns; tablet/mobile: one column):**
1. **Numbers row** (`.v3-nums`, four cards; 2×2 at < 1024; 1 column at < 600):
   - «كل الأسئلة»: `total`. Note «من المحادثة: أعضاء وزوار».
   - «تحتاج رأي خبير»: «{needs_expert} · {round(rate·100)}٪». Note «وصلت إلى موقف يستحق خبيرًا».
   - «أعضاء وزوار»: «{authed} عضو · {anonymous} زائر». Note «حساب مسجّل مقابل زائر بلا حساب».
   - «دفعوا مقابل رأي خبير»: «{paid} من {requested} · {pct}٪». Note «من طلبات رأي الخبير». If `expert_opinions` is missing: «غير متاح بعد».

   Second small line under the row: «يسأل الناس من {n} بلدًا». n = `by_country` entries with code ≠ `unknown` and count > 0.
2. **Classification bar** (`.v3-card` slim):
   - Text: «صُنّف {classified} سؤالًا · ينتظر التصنيف {unclassified}».
   - Button «صنّف الأسئلة الجديدة» (`.v3-btn2`), hidden when `unclassified === 0`, in which case the text reads «كل الأسئلة مصنّفة».
   - The button calls the **existing endpoint** directly, `EP.api('/platform-chat-insights/classify?limit=100', {method:'POST', body:{}})`, then `EP.reload('analysis')`.
     - We do not call `EP.runDemandClassify`, because its toasts are old colloquial copy.
     - Busy: disabled, with text «…جارٍ التصنيف».
     - Done: `.v3-ok` «صُنّف {classified} سؤالًا جديدًا» (+ « · بقي {remaining}» when > 0).
     - `r.error` or failure: `.v3-err` «تعذّر التصنيف الآن، جرّب بعد قليل».
   - No confirmation sheet: no money, and nothing is published.
3. **«أحدث الأسئلة»** card. The header has a count of the filtered list and the hint «آخر ٤٠ سؤالًا تصل من المنصة» (a fact: the platform caps the list at 40).
   - **Filter row** (wraps; each control ≥ 44px):
     - selects «كل الشرائح» / «كل البلاد» / «كل المجالات» (the last only if `by_category` is non-empty);
     - chips «الكل» · «تحتاج خبيرًا» · «لا تحتاج»;
     - chips «كل الوقت» · «آخر ٧ أيام» · «آخر ٣٠ يومًا»;
     - «امسح التصفية» (only when a filter is on).
     - State in a module variable (not the old global `anFilters`).
   - **Row:** a button, full width, ≥ 56px. The question text (2 lines max, ellipsis) above meta chips: segment label · country label · category (normalised) · «تحتاج خبيرًا» (wine) · «زائر» or «عضو» · «افتح المحادثة ←». Rows without `id` are not clickable.
   - **Empty:** «لا أسئلة تطابق التصفية» / «لا أسئلة بعد».
4. **Four bar cards:**
   - «حسب الشريحة» (`by_segment`, with `unknown` last)
   - «حسب البلد» (`by_country`)
   - «حسب المجال القانوني» (`by_category`, with a chip row «أكثر المجالات الفرعية» from `by_subcategory`, top 10)
   - «حسب المطلوب» (`by_intent`)

   Hint «على كل الأسئلة · اضغط للتصفية». Each bar is a button ≥ 44px. Pressing it toggles the matching filter in block 3 and scrolls to it (the intent bar does not filter, as before). When a classification card is empty: «لم تُصنَّف الأسئلة بعد — اضغط «صنّف الأسئلة الجديدة»» if `unclassified > 0`, otherwise «لا بيانات بعد».
5. **«خدمات يطلبها الناس ولا نقدّمها»** (`unmet`):
   - Each row shows «{label}: {count} سؤالًا», the line «مثال: {sample_question}», and one button «افتح الدورات» (`openSection('courses')`, the same destination as the old `go('courses')`).
   - Empty: «لم يظهر طلب متكرّر لا نقدّم له خدمة حتى الآن».
   - The section's brain line «فرصة» uses the first row (§7).

**Label maps:** reuse the existing globals `SEG_LABEL`, `COUNTRY_LABEL` and `catAr` from `index.html` through `typeof` guards (they are top-level `const`s in a classic script, so they are reachable by name). Do not duplicate them; if one is missing, fall back to the raw value. One copy fix is applied at display time only: segment `influencer` shows «مؤثر أو رائد أعمال» instead of «مؤثر/رائد أعمال».

**Conversation sheet** (new style, replaces the old `openModal`):
- A right-side sheet on desktop and a full-height sheet on mobile, using the same sheet container classes as D3's focus sheets. Close button «أغلق» ≥ 52px; Esc and the scrim also close it.
- Data: `EP.api('/platform-chat-insights/' + encodeURIComponent(id))`, an existing admin-only route; the platform writes its own audit row.
- Contents:
  - «من سأل»: the name plus a person link (`V2L.sectionHash('people','person',email)`, opened with `V2_HOST.openPerson`) when `identity.email` exists; otherwise «زائر بلا حساب».
  - «التصنيف»: category · intent.
  - «التاريخ»: `V2L.util.dateText`.
  - Then the bubbles: «السائل» on the paper background, «بروف» on light wine.
  - When `truncated`: an amber note «هذه نسخة محفوظة من الرد وليست المحادثة كاملة: جلسة الزائر لا تُحفظ، والأسئلة الأقدم بلا رد محفوظ.»
- Loading: «…جارٍ فتح المحادثة». Failure: `.v3-err` «تعذّر فتح المحادثة» + «أعد المحاولة».

---

## 6) Tab «تقرير الأحد» (`v2r_sunday`)
- **Data:** `GET /api/v2/reports/weekly[?week=YYYY-MM-DD]` (§8). The default is the last **complete** week, Sunday 00:00 to Saturday 24:00, Cairo time, compared with the week before.
- **Header:**
  - «تقرير الأسبوع»;
  - the date line «من الأحد {١٩ أكتوبر} إلى السبت {٢٥ أكتوبر ٢٠٢٦}، مقارنة بالأسبوع الذي قبله»;
  - navigation «الأسبوع السابق» / «الأسبوع التالي» (buttons ≥ 44px; «التالي» disabled on the latest complete week; at most 12 weeks back, after which «السابق» is disabled);
  - «نزّل التقرير» (print) and «انسخ النص». The latter copies `weekly.text` with `navigator.clipboard.writeText` (try/catch). It then shows `.v3-ok` «نُسخ نص التقرير»; when the clipboard is blocked, it selects the text in a read-only box instead.
- **Body** (letter-like single column, max width 860, paper card):
  1. «ملخص العقل»: the same three lines and basis disclosures as §4.2, for the week.
  2. «الأرقام»: the funnel as a compact row of five numbers with change lines (vertical list on mobile).
  3. «كل قسم في سطر»: same rows as §4.6.
  4. The delivery line: «الإرسال كل أحد صباحًا: لم يُفعَّل بعد» (or «يُرسل كل أحد صباحًا إلى {channel label}» once N6 ships).
- **States:** same as §3. A week before the first ledger row reads normally («لا بيع»). That is a fact, not a failure.

---

## 7) The brain lines: rules (server-side, deterministic, no AI)
Built in `v2_reports_routes.build_brain(facts, scope)` from the numbers already in the payload, and nothing else. Every line carries `basis` = the exact numbers used, with sources.

**Candidates per scope:**
- `all` uses every section.
- A section scope uses only its own candidates.
- `marketing` has none.

**«شغّال» (`working`):**
1. Among the money sections in scope (`files`, `courses`, `books`), pick the one with the largest EGP increase where all of these hold:
   - prev EGP > 0;
   - pct ≥ +10;
   - cur count ≥ 2.

   Text when prev count ≥ 3: «{دخل الدورات} زاد {٣١}٪: من {١٢٬٠٠٠} إلى {١٥٬٧٢٠} جنيه.»

   When prev count < 3, no percentage (small numbers mislead): «{الكتب}: {٤} عمليات بيع مقابل {عملية واحدة} في الفترة التي قبلها.»
2. Otherwise, signups (whole scope only, `users` complete for both windows) with pct ≥ +10 and prev ≥ 5: «الحسابات الجديدة زادت {١٨}٪: {١٢٤} مقابل {١٠٥}.»
3. Otherwise, market (scope all/market) `new` with pct ≥ +10 and prev ≥ 3: «طلبات السوق زادت {٢٠}٪: {١٨} مقابل {١٥}.»
4. Otherwise `text: null`, `empty_text`: «لم يصعد شيء بوضوح في هذه الفترة.»

Action: «افتح {القسم}» → `openSection(key)`.

**«واقف» (`stalled`), first match wins:**
1. A money section with prev count ≥ 1 and cur count 0: «{الكتب}: لا بيع في هذه الفترة، وكان {٣} عمليات في الفترة التي قبلها.»
2. A money section with prev EGP > 0, pct ≤ −10 and prev count ≥ 3, taking the largest drop: «{دخل الكتب} نزل {٢٢}٪: من {…} إلى {…} جنيه.»
3. Market `unanswered > 0`: «{١١} طلبًا في السوق بلا عرض من خبير.» Action «افتح السوق».
4. Signups pct ≤ −10 with prev ≥ 5: «الحسابات الجديدة نزلت {١٢}٪: {٩٢} مقابل {١٠٥}.»
5. Otherwise `empty_text` «لم يتراجع شيء بوضوح في هذه الفترة.»

**«فرصة» (`opportunity`), first match wins, scopes all/market/courses/files:**
1. `chat.unmet[0]`, which already passes the platform's `UNMET_MIN_COUNT`: «{٤١} سؤالًا عن «{تأسيس الشركات}» ولا نقدّم له خدمة بعد.» The basis states «كل الأسئلة منذ البداية» (the platform gives no period for this). Action «افتح الدورات».
2. Market requests in the window with `need_kind == 'course'`, count ≥ 3: «{٥} طلبات في السوق تطلب دورة، ولا يوجد عرض لأغلبها.» This is used only if `unanswered` among them is > half. Action «افتح السوق».
3. Otherwise `empty_text` «لا توجد فرصة واضحة في الأسئلة والطلبات حتى الآن.»

**General rules:**
- A failed source needed by a rule makes that rule skip (it never counts as 0).
- When every rule of a line skipped **because of failures**, the line is `text: null`, `na_reason` «تعذّر جلب {labels}».
- Percentages are rounded to whole numbers. Money is EGP only, and the basis says «النسبة بالجنيه فقط» when foreign currency exists.
- Names in sentences come from a fixed map: «دخل ملفات الخبراء», «دخل الدورات», «دخل الكتب» (in the zero-sale form: «ملفات الخبراء», «الدورات», «الكتب»).
- No sentence starts with «الذكاء» or «AI». None uses «يقوّم». All are gender-neutral (people are «الناس», «أصحاب الطلبات»).

---

## 8) Server routes (new file `backend/v2_reports_routes.py`)
Both routes share these rules:
- `@token_required @roles_required('admin')`;
- `_v2_closed()` first (404 when the switch is off, and **no** platform call);
- `Cache-Control: no-store` via `_v2_ns`;
- read-only (no `_audit`, nothing written);
- the response carries **no PII**: no emails, names, phones or question texts, only counts and sums.

`register(app, g)` takes the helpers from `g` (the `app.py` globals): `token_required`, `roles_required`, `_v2_closed`, `_v2_ns`, `_platform_proxy`, `_resp_ok`, `PLATFORM_METRICS_SECRET`, `Revenue`, `Article`, `db`. This avoids a circular `import app`.

### 8.1 `GET /api/v2/reports/summary?period=week|month|quarter&scope=all|files|courses|books|market|content|marketing[&fresh=1]`
- **Validation:** bad `period` → 400 «فترة غير معروفة»; bad `scope` → 400 «قسم غير معروف».
- **Window:**
  - Timezone `Africa/Cairo` via `zoneinfo`. If tzdata is missing, use a fixed UTC+3 and set `window.tz_note`.
  - `until` = the start of tomorrow, Cairo time.
  - `from = until − N days` (N = 7 / 30 / 91).
  - `prev = [from − N, from)`.
  - Buckets: day for week/month; 7-day blocks aligned to `until` for quarter.
- **Sources:** fetched in parallel (`ThreadPoolExecutor`, one call each, 12 s timeout, no retry). Each one fails alone and becomes `null`:
  1. **`ledger`:** local SQLite. `Revenue.query.filter(Revenue.date >= prev.from, Revenue.date < until)`.
     - Per row: EGP from `amount_egp`, USD from `amount_usd`, any other currency from `amount_original` when `needs_fx`.
     - The service comes from `_service_of(source)`, mirroring `serviceOf` in `v2-logic.js:1432` exactly (`consultation|consulting|expert_file|expert_case` → experts; `course|course_offer|program` → courses; `book|knowledge` → books; else other). It is guarded by a parity test (§10).
     - It never reads `total_egp`, which is converted at an exchange rate.
     - Output per window: `{services:{experts|courses|books|other: {count, totals:[{currency, amount}]}}, count, totals}`, plus per-bucket `income_egp` and `count`.
  2. **`users`:** `_platform_proxy('GET','/api/bridge/users', params={'limit':1000})`.
     - Count `created_at` (converted to a Cairo date) per window and per bucket.
     - `complete_for(window)` = `len(rows) < 1000` **or** the oldest `created_at` < window start. An incomplete window → `null` (never a partial count).
  3. **`market`:** `_platform_proxy('GET','/api/bridge/market/requests', params={'author_kind':'member','include_test':'false','limit':500})`.
     - Per window: `new` (created in the window), `with_offers` (`offer_count > 0`), `matched` (`status == 'matched'`), `unanswered` (`status == 'open'` and `offer_count == 0`), `course_need` (`need_kind == 'course'`, with its own unanswered count).
     - Completeness rule as for users (`total ≤ 500` or the oldest item is before the window start).
  4. **`content`:** local SQLite `Article.query.filter(Article.status == 'published', Article.published_at >= from, < until).count()` per window.
  5. **`disputes`:** `_platform_proxy('GET','/api/bridge/consultations', params={'status':'disputed'})` → `total` (open now, not per window).
  6. **`chat`:** `_platform_proxy('GET','/api/bridge/chat-insights', params={'limit':3000})`. Only `unmet[0]`, `classified` and `unclassified` are kept (no question text in the response).
  7. **`funnel`:** `_platform_proxy('GET','/api/bridge/reports/funnel', params={'from','until','scope','tz'})`.
     - 404 → `'absent'` (silent; the interim sources are used).
     - 200 → its non-null values **replace** the interim value of the same stage, section or bucket. One number, one source: the interim reading is not shown beside it.
     - Any other error → `'failed'` (warn strip), and interim is used.
- **Cache:** in-process 60 s, keyed `(scope, period, from, until)`. `fresh=1` bypasses it.
- **Response:**
```json
{
 "ok": true, "scope": "all", "period": "month",
 "window": {"from": "2026-10-01", "until": "2026-10-31", "days": 30, "tz": "Africa/Cairo", "label": "آخر ٣٠ يومًا (من ١ إلى ٣٠ أكتوبر)"},
 "prev": {"from": "2026-09-01", "until": "2026-10-01", "label": "الثلاثون يومًا التي قبلها"},
 "generated_at": "2026-10-30T09:12:00+03:00",
 "sources": {"ledger": "ok", "users": "ok|partial|failed", "market": "ok|partial|failed", "content": "ok", "disputes": "ok|failed", "chat": "ok|failed", "funnel": "absent|ok|failed"},
 "funnel": {"title": "من الزيارة إلى الدفع", "stages": [
   {"key": "visits", "label": "زاروا المنصة", "cur": null, "prev": null, "change_pct": null, "trend": "na", "conv_pct": null, "conv_text": null, "sub": null},
   {"key": "signed_up", "label": "سجّلوا حسابًا", "cur": 124, "prev": 105, "change_pct": 18, "trend": "up", "conv_pct": null, "conv_text": null, "sub": null},
   {"key": "paid", "label": "دفعوا", "cur": 31, "prev": 28, "change_pct": 11, "trend": "up", "conv_pct": null, "conv_text": null, "sub": "عمليات دفع، وقد يدفع الشخص أكثر من مرة"}
 ], "footnote": "الخانات الفارغة تكتمل حين تسجّل المنصة الزيارات ومصدر كل زائر."},
 "daily": {"bucket": "day|week", "rows": [{"from": "2026-10-01", "label": "١ أكتوبر", "income_egp": 1200.0, "signups": 4, "visits": null}], "income_other": [{"currency": "USD", "amount": 30}], "signups_available": true, "visits_available": false},
 "origins": {"channels": null, "countries": null, "top_pages": null, "note": "تكتمل حين تسجّل المنصة مصدر كل زائر وكل دفعة."},
 "sections": [
   {"key": "files", "label": "ملفات الخبراء", "value": {"kind": "money", "egp": 112400.0, "others": [], "count": 41}, "prev": {"egp": 85800.0, "count": 33}, "trend": {"key": "up", "pct": 31}, "chip": {"text": "ينمو ٣١٪", "tone": "up"}, "note": "تشمل الاستشارات العادية", "open": "files"},
   {"key": "market", "label": "سوق الخدمات", "value": {"kind": "count", "n": 38, "text": "٣٨ طلبًا جديدًا"}, "chip": {"text": "١١ بلا عرض", "tone": "bad"}, "open": "market"},
   {"key": "satisfaction", "label": "رضا العملاء", "value": null, "chip": {"text": "نزاعان مفتوحان", "tone": "bad"}, "open": "disputes"}
 ],
 "brain": [
   {"key": "working", "label": "شغّال", "text": "…", "empty_text": null, "na_reason": null, "basis": [{"label": "دخل ملفات الخبراء الآن", "value": "١١٢٬٤٠٠ جنيه", "source": "دفتر الإيرادات"}], "action": {"label": "افتح ملفات الخبراء", "section": "files", "tab": null}},
   {"key": "stalled", "...": "..."}, {"key": "opportunity", "...": "..."}
 ],
 "delivery": {"enabled": false, "text": "إرسال التقرير كل أحد: لم يُفعَّل بعد"}
}
```
Every Arabic number string in the payload is built with one Python helper, `_ar(n)`: Arabic-Indic digits, «٬» grouping, «٫» decimal. Numeric fields stay numeric for the front-end, which formats them with `V2L.util`.

### 8.2 `GET /api/v2/reports/weekly[?week=YYYY-MM-DD]`
- `week` must be a Sunday (Cairo) whose week has ended: `week + 7 days ≤` the start of the current week. Otherwise 400 «اختر أسبوعًا اكتمل». More than 12 weeks back → 400 «أقدم أسبوع متاح: {date}».
- Same builder with `window = [week, week+7)`, `prev = [week−7, week)`, daily buckets and scope `all`.
- Adds:
  - `"week": {"start": "…", "end": "…", "label": "من الأحد ١٩ أكتوبر إلى السبت ٢٥ أكتوبر ٢٠٢٦"}`;
  - `"nav": {"prev": "YYYY-MM-DD"|null, "next": "YYYY-MM-DD"|null}`;
  - `"text"`: plain Arabic text of the whole report (brain lines, funnel numbers, section lines, one per line, the «غير متاح بعد» items included). It is ready for «انسخ النص» and, later, for the Sunday delivery (N6).
- Cache 10 min (a finished week does not change).

---

## 9) Buttons: what each one calls (no new decision path anywhere)
| Button | Where | Calls |
|---|---|---|
| Scope chips / period switch | التقرير | re-render, then `GET /api/v2/reports/summary` (cached) |
| «حدّث» | التقرير | same with `fresh=1` |
| «نزّل التقرير» | التقرير, تقرير الأحد | `window.print()` |
| «على أي أساس؟» | brain lines | local disclosure |
| Brain action («افتح …») | brain lines | `V2_HOST.openSection(section[, tab])` (existing `v2OpenSection`) |
| Section row | كل قسم في سطر | sets the scope (local) |
| «افتح {القسم}» | section row in scope view | `V2_HOST.openSection(open)` |
| «افتح تقرير الأحد» | footer | `V2_HOST.openSection('reports','sunday')` |
| «افتح التسويق» | marketing scope | `V2_HOST.openSection('marketing')` |
| «صنّف الأسئلة الجديدة» | ما يسأل عنه الناس | existing `POST /api/platform-chat-insights/classify?limit=100`, then `EP.reload('analysis')` |
| Filter chips / selects / bars | ما يسأل عنه الناس | local filter |
| Question row | ما يسأل عنه الناس | existing `GET /api/platform-chat-insights/<id>` → sheet |
| Person link in sheet | sheet | `V2_HOST.openPerson(email)` (existing `v2OpenPerson`) |
| «افتح الدورات» | unmet rows | `V2_HOST.openSection('courses')` |
| «الأسبوع السابق/التالي» | تقرير الأحد | `GET /api/v2/reports/weekly?week=` |
| «انسخ النص» | تقرير الأحد | `navigator.clipboard.writeText(weekly.text)` |
| «أعد المحاولة» | any failed state | the same GET again |

No money action exists in this section, so no confirmation sheet is involved.

---

## 10) Tests: `backend/tests/test_v2s_reports.py` (zero real network, zero paid calls)
Use the same harness pattern as `test_v2_d3.py`: the Flask test client, the fake platform (`reports_fixtures.ReportsPlatform`, a subclass of `v2_fixtures.V2Platform`), and the in-memory SQLite.

**pytest, routes:**
1. Both routes: no token → 401; `employee` → 403; switch off → 404 with **zero** platform calls; `Cache-Control: no-store`.
2. Validation: bad period/scope → 400 with the Arabic message. `week` not a Sunday, in the current week, in the future, or older than 12 weeks → 400.
3. Windows: week/month/quarter lengths 7/30/91. `prev` is adjacent. The Cairo boundary is tested with a frozen clock at 23:30 UTC (= next day in Cairo). Quarter buckets are 13 blocks of 7 days.
4. Ledger:
   - EGP, USD and a `needs_fx` SAR row are never summed together;
   - `total_egp` is never read (a row with only `total_egp` contributes nothing);
   - rows outside the window are excluded;
   - the mapping of every `source` value goes through `_service_of`.
5. **Parity with D3:** for a calendar-month window, Python ledger sums per service per currency == `V2L.v2Income(rows,'month',now)` via `v2_node.logic`, using the same rows from `/api/revenues`.
6. Users completeness: 1000 rows all inside the window → `signed_up.cur` is `null` (not 1000). 999 rows → exact count. The oldest row before `prev.from` → both windows exact.
7. Market: the same completeness rule; `unanswered` counts only `open` with `offer_count == 0`; platform cards and test rows are excluded (query params asserted).
8. Each source failing alone (500/502/timeout/401) → its fields are `null`, `sources[k] == 'failed'`, the other numbers are unchanged, and **no `0` replaces a failed number** anywhere in the payload (a recursive assertion over the JSON).
9. Funnel bridge: 404 → `'absent'` and interim values; 200 → platform values replace interim (signups from the funnel even when users also loaded; `paid` uses `paid_people`); 500 → `'failed'` and interim values.
10. Brain rules, one test per rule branch:
    - small-number phrasing when prev count < 3;
    - zero-after-sales;
    - unanswered market;
    - unmet opportunity;
    - all skipped because of failures → `na_reason`;
    - scope filtering (a `books` scope never mentions courses);
    - `marketing` scope → three `na_reason`;
    - sentences contain Arabic-Indic digits only;
    - no sentence starts with «الذكاء»/«AI»;
    - no «يقوّم».
11. No PII: the serialized response contains none of the fixture emails, names, phones or question texts.
12. Every outbound call goes to `/api/bridge/` paths on the fake platform. The classify POST is never called by these routes.
13. Cache: a second call within 60 s makes zero platform calls; `fresh=1` calls again.
14. Weekly: default week = last complete Sun–Sat in Cairo; `nav.next` is null on the latest week; `text` contains the three brain labels and every section label.

**node (pure helpers in the `v2s:reports` block of `v2-logic.js`, run through `v2_node.logic`):**
- `v2r.trendChip(trend)`: every key → text/tone.
- `v2r.stageView(stage, prevKnownStage)`: change line and conversion phrase, nothing when either side is null.
- `v2r.chartPoints(rows, w, h)`: scales, a null series is dropped, an all-zero series is drawn flat (not hidden).
- `v2r.demandFilter(recent, filters, now)`: port of the old filter. It is checked against the old `viewAnalysis` filter behaviour on the same rows (segment, country, category, needs expert, 7/30 days).
- `v2r.demandNumbers(d)`: the four cards. Missing `expert_opinions` → «غير متاح بعد».

**Section map and hooks:**
- `sectionFor('analysis')` → reports/report;
- `routeFor('#s/reports/demand')` and `#s/reports/sunday` round-trip;
- the tab list is exactly «التقرير · ما يسأل عنه الناس · تقرير الأحد» (no «كل السجلات»);
- `V2SEC.reports.owns('analysis')` is false when `V2SHELL.on` is false.

**Visible-copy scan:** all Arabic strings in `v2s/reports.js` and `v2_reports_routes.py` contain no «يقوّم», «AI», «API», «null», «جايين», «منين», «بالذكاء». Labels ending in «؟» are allowed.

**Old suite:** run file by file. With the switch off, `test_dash_*` (including the old analysis tests, if any) stay green. Port-binding tests are re-run outside the sandbox by the main session.

---

## 11) Shots: `backend/tests/uiharness/v2_shots_reports.py` → `docs/v2/final/shots-reports/`
Viewports: desktop 1440×900 (`d`), tablet 820×1180 (`t`), mobile 390×844 (`m`). Every shot is taken at all three. Fixtures:
- `reports_fixtures.seed_dash(app)`: about 90 days of `Revenue` rows across services, with one USD and one `needs_fx` SAR row, plus 20 published `Article` rows.
- The fake platform: 600 users spread over 200 days; 60 market member requests; 3 disputes; a full `chat-insights` payload with 40 recent questions, unmet rows and some unclassified; detail for one signed-in and one anonymous question.
- The funnel bridge returns 404 by default; variant `funnel=True` serves a full N3 payload.

1. `01` التقرير, all, month (full).
2. `02` week · `03` quarter (weekly buckets).
3. `04` brain «على أي أساس؟» open on all three lines.
4. `05` scope «الدورات» · `06` scope «السوق» · `07` scope «التسويق».
5. `08` sources down (users, market, chat 502). The warn strip and «غير متاح بعد» show, with **no 0**.
6. `09` the route failed entirely (500) → empty state with retry.
7. `10` funnel bridge present (`funnel=True`): all five stages, channels, countries and top pages filled.
8. `11` ما يسأل عنه الناس (full) · `12` filtered by a country bar · `13` conversation sheet, signed-in (person link) · `14` sheet, anonymous and truncated · `15` the chat source failed · `16` after «صنّف الأسئلة الجديدة» (fake platform returns `{classified: 12, remaining: 3}`; the POST is asserted and nothing else is written).
9. `17` تقرير الأحد (latest) · `18` the previous week · `19` «انسخ النص» confirmation.
10. `20` print emulation (`page.emulate_media(media='print')`) of التقرير and تقرير الأحد (desktop only).
11. `21` the board tile «التقارير» clicked → lands on «التقرير» · `22` the old link `#analysis` → lands on «التقرير».
12. `23` switch off: `#analysis` renders the old `viewAnalysis` exactly. The test asserts that no `.v2r-` element and no `v2s/` request appears.

**The script fails on any of these:**
- visible «0», «null», «NaN» or «undefined» where a number is unavailable;
- a target < 44px, or a button < 52px on mobile;
- horizontal scroll at any viewport;
- a visible Latin digit (dates included);
- any request outside the harness (Google Fonts allowed);
- any platform write other than the single classify POST in shot 16;
- an old-style element (`.panel`, `.kpis`, `.filterbar`, `.an-grid`) inside the section with the switch on.

The script prints the JSON summary like `v2_shots.py` and exits 1 on problems.

---

## 12) Platform needs (for the platform agent; exact shapes)
Every new bridge uses the `X-ELP-Metrics-Secret` guard and is read-only unless stated otherwise. With no data, a field is `null`, never `0`, and any new behaviour defaults to exactly today's.

**N1. Record the source of each person and each payment (attribution).**
- **Capture:**
  - The app and the static site set a first-party first-touch cookie `ep_acq` (essential-only consent safe: no third-party IDs) holding `{utm_source, utm_medium, utm_campaign, utm_content, utm_term, referrer_host, landing_path, first_seen_at}`.
  - All four signup doors (`auth.register`, `auth_code.verify`, invite journey, chat signup) copy it to `users.acq`. They also add `acq.channel`, derived server-side by one function `services/attribution.channel_of(acq, user)`:
    - `google`: referrer `google.*` or `utm_source=google`;
    - `meta`: facebook/instagram referrers, `utm_source` ∈ {facebook, instagram, meta, fb, ig}, or `fbclid`;
    - `whatsapp`: `wa.me`, `whatsapp`, or `utm_source=whatsapp`;
    - `invite`: `journey_invite_id`, `invited_by_user_id` or `referred_by_code`;
    - `direct`: none of the above;
    - `other`.
  - Every `payments` doc at creation copies `users.acq` (first touch) and the session's last-touch `{utm_*, referrer_host, landing_path}` as `payments.acq_last`.
- **Bridge row:** add to `_user_row` in `admin_bridge.py`: `"signup_country"`, `"country"`, `"channel"` (from `acq.channel` or `null`), `"is_test"`.

**N2. Count visits (no personal data).**
- `POST /api/track/visit` (public, rate-limited, no cookie needed): `{path, referrer_host, utm_source?, utm_medium?, utm_campaign?}`. The server adds the country (geo) and a daily-salted hash of IP+UA for unique visitors. The hash is never stored raw beyond the day.
- Stored as daily aggregates: `visits_daily {date (Cairo), path, channel, country, visits, visitors}`.
- Called by the app router and by the static site (article pages, «اعرف مسارك», the video page).

**N3. Funnel and origins for any window.**
- `GET /api/bridge/reports/funnel?from=YYYY-MM-DD&until=YYYY-MM-DD&scope=all|files|courses|books|market|content&tz=Africa/Cairo` →
```json
{"ok": true, "from": "…", "until": "…", "tz": "Africa/Cairo", "generated_at": "…",
 "stages": {"visits": 12400, "visitors": 9100, "asked": 3100, "signed_up": 1240, "opened": 410, "paid_people": 268, "paid_orders": 301},
 "by_day": [{"date": "2026-10-01", "visits": 410, "signups": 41, "paid_orders": 9, "income": [{"currency": "EGP", "amount": 4200.0}]}],
 "origins": {"channels": [{"key": "google", "label": "بحث جوجل", "visits": 4700, "signups": 470, "paid_people": 101}],
             "countries": [{"code": "EG", "signups": 790, "paid_people": 170}],
             "top_pages": [{"path": "/blog/…", "title": "فسخ عقد الإيجار", "visits": 1900, "signups": 120}]},
 "sections": {"files": {"opened": 160, "paid_orders": 41, "income": [{"currency": "EGP", "amount": 112400.0}]},
              "courses": {"page_visits": 2100, "enrolled": 300, "paid_orders": 60, "income": []},
              "books": {"page_visits": 900, "buy_clicks": 270, "paid_orders": 33, "income": []},
              "content": {"published": 24, "visits": 4200, "signups_from_articles": 85}}}
```
- Stage definitions:
  - `asked` = distinct askers in `chat_insights` (anonymous by session id);
  - `opened` = distinct people who created an expert file or started a course (enrolled or opened lesson 1);
  - `paid_people` = distinct payers with `status` paid/partially_refunded, excluding `ads_deposit`;
  - test users are excluded everywhere.
- Income is per currency, never converted, net of partial refunds (the same rules as `/bridge/income/by-service`).
- Any metric not tracked yet is `null`.

**N4. Questions per period.**
- `GET /api/bridge/chat-insights?since=ISO&until=ISO` → the same shape as today, restricted to the window, plus `"window_total"`. Without the params, behaviour is unchanged. This also lets the demand tab gain the period filter later.

**N5. Customer satisfaction.**
- `GET /api/bridge/satisfaction?from=&until=` → `{"rating_avg": 4.7|null, "rating_count": 52, "sources": {"courses": {"avg": 4.8, "count": 40}, "expert_files": {"avg": null, "count": 0}}, "complaints_opened": 2, "disputes_open": 1}`.
- Ratings come from approved `course_testimonials.rating` and any expert-file review rating that exists.

**N6. Sunday delivery.**
- `POST /api/bridge/reports/weekly/deliver` with body `{week_start, text, by, confirmed: true}`. It sends `text` to the founder's existing Telegram chat once per `week_start` (idempotent claim like `marketing_digest_sends`), and returns `{sent: bool, already: bool}`.
- `GET /api/bridge/reports/weekly/delivery` → `{enabled: bool, channel: "telegram", last_sent_week: "YYYY-MM-DD"|null}`.
- The dashboard will add a secret-guarded cron route that calls it on Sunday 08:00 Cairo. This is **not in this round**, and until it exists the screens say «لم يُفعَّل بعد».

## 13) Out of scope
- Marketing numbers (spend and leads per campaign); the marketing section owns those.
- The brain's rules screen.
- Any write from this section other than the existing classify call.
- Any push or deploy.
