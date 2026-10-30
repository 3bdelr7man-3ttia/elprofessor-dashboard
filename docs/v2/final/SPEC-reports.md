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
**Revision 2 (2026-10-30):** expert review applied. What changed and what was rejected is in §14 «Decisions».

## 0) The decision in one paragraph
The old section has one tab, «تحليل الطلب» (`analysis`, `index.html:2822 viewAnalysis`). It is a read-only analysis of chat questions. **Nothing of it survives in the old look.** The section becomes three new tabs:
- **«التقرير»**: the concept board. Until the platform records visits, the real numbers (section lines, day by day) come first and the empty parts are compact (§4.0).
- **«ما يسأل عنه الناس»**: the old demand analysis, **rebuilt around its one opportunity** («خدمات يطلبها الناس ولا نقدّمها» first), with every old feature kept.
- **«تقرير الأحد»**: the weekly report view, with the dashboard side of the Sunday delivery built in this round (setting, cron route, «أرسل الآن»).

**No «كل السجلات» tab**: tab 2 covers everything the old screen did.

All numbers on tabs 1 and 3 come from **one new server route** that gathers existing sources, so the screen and the Sunday message read the same numbers. Anything the platform does not record yet shows «غير متاح بعد» and is listed under **Platform needs** (§12):
- visits;
- each person's and each payment's source;
- questions per period;
- «فتحوا ملفًا أو دورة»;
- ratings;
- the Sunday delivery itself (the Telegram send lives on the platform).

The brain lines are **deterministic sentences built only from those numbers**. There is no AI call.

---

## 1) Files (parallel-safety rules)
| File | New/edit | What |
|---|---|---|
| `dashboard-cloud/v2s/reports.js` | new | All rendering for the three tabs. It registers `window.V2SEC.reports = {owns, render}`. |
| `dashboard-cloud/v2s/reports.css` | new | Styles, all under `.v2r-*`. It reuses the existing `.v3-*` classes from `v2-d3.css` (cards, period switch, buttons, empty/warn states, brain avatar, `.v3m` sheet body) and does not edit them. |
| `backend/v2_reports_routes.py` | new | `register(app, g)` with the routes of §8. Pure builders, testable without Flask. |
| `backend/app.py` | 1 line | `import v2_reports_routes as _v2r; _v2r.register(app, globals())  # v2s:reports`, placed right before `# ---- v2 section routes end`. If the marker is missing, create it after the last v2 route (after `v2_book_request_patch`, before `@app.route('/api/platform-pnl'`). |
| `backend/requirements.txt` | 1 line | `tzdata==2024.1` (§8.1 Window). Both Dockerfiles already install from this file. |
| `dashboard-cloud/index.html` | block only | Inside `<!-- v2 sections begin -->` … `<!-- v2 sections end -->` (create it right after the `v2-d2.js` script tag if missing): `<link rel="stylesheet" href="v2s/reports.css">` and `<script src="v2s/reports.js"></script>`, one line each, alphabetical by key. |
| `dashboard-cloud/v2-logic.js` | own entry + helpers + 1 shared edit | The `reports` entry in `SECTIONS` (§2). Pure helpers at the end of the file inside `// ===== v2s:reports =====` … `// ===== /v2s:reports =====`, exported as `V2L.v2r = {...}`. The hash-query edit is shared edit 4. |
| `backend/tests/test_v2s_reports.py` | new | pytest + node (§10). |
| `backend/tests/uiharness/reports_fixtures.py` | new | Fake platform subclass + SQLite seed for this section. |
| `backend/tests/uiharness/v2_shots_reports.py` | new | Shots (§11). Imports helpers from `v2_shots.py`; edits it only as listed in §10.1. |

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
4. **`v2-logic.js` hash query (for §4.1).** In `parseSectionHash`, before `split('/')`, cut an optional `?…` suffix and parse it into `out.q` with **whitelisted keys only** (`scope`, `period`; values `[a-z]{1,12}`; anything else dropped). `routeFor` copies `p.q` onto the result as `r.q`. `sectionHash(key, tab, person, q)` gains an optional 4th argument that appends `?scope=…&period=…` (keys in that order, only those present). With no `?`, every existing hash parses exactly as today (test in §10).
5. **`v2-d3.js` exports (for the confirmation sheet).** Two lines next to `D3.openApprove = openApprove;`: `D3.openSheet = openSheet; D3.twoStage = twoStage;`. No change to either function. This lets reports use **the existing** confirmation sheet instead of a copy.

---

## 2) The section entry in `SECTIONS` (the only change in the map)
```js
{ key: 'reports', label: 'التقارير', img: 'reports', desc: 'ما الذي يعمل، وما الذي توقّف، وأين الفرصة', tabs: [
  T('report', 'التقرير', 'analysis'),
  T('demand', 'ما يسأل عنه الناس', 'v2r_demand'),
  T('sunday', 'تقرير الأحد', 'v2r_sunday')
] },
```
**The first tab's key is `report` (fixed in tests) while its module stays `analysis`:**
- The board tile already goes to `T.reports.dest = 'analysis'` (`v2-logic.js:317`, outside our entry).
- Old links `#analysis` and `go('analysis')` resolve through `sectionFor('analysis')`.
- All three now land on `('reports','report')`, with no edit to the tile code or `ALIASES`.
- `V2SEC.reports.owns(mod)` returns true for `analysis`, `v2r_demand` and `v2r_sunday` **only when `window.V2SHELL && V2SHELL.on`**. So with the switch off, and for any non-admin role, `analysis` still draws the old `viewAnalysis`.
- The courses screen's internal «demand» tab reads `EP.data.analysis` (the loader), not the view, so it is untouched.

Tile line: unchanged (`'شغّال · واقف · فرصة'`, no count). The tile has no badge: reports never wait on a decision.

---

## 3) Shared look (all three tabs)
- **Brand:**
  - عنّابي `#9E2B4E` (the one main button, the funnel's first bar, active chips);
  - paper `#FBFAF7` / `#F6F1EA`;
  - ink `#21262E` (brain strip background, active period);
  - green `#1E6B4A` on `#EEF6F1` for «▲»/«ينمو»;
  - amber `#8A4B00` on `#FCF1E3` for «▼»/«ثابت»;
  - red `#A3122A` on `#FBE9EC` only for «بلا عرض» and disputes.
- **Fonts:** Cairo 800 for numbers and headings, IBM Plex Sans Arabic for body text. All digits are Arabic-Indic via `V2L.util.ar/fmt`, with «٬» thousands and «٪».
- **One main button per screen.** «التقرير»: «نزّل التقرير». «ما يسأل عنه الناس»: «افتح الدورات» on the opportunity card. «تقرير الأحد»: «نزّل التقرير». Everything else is secondary (`.v3-btn2`) or a text link.
- **Targets:** ≥ 44px (text links included, by padding); every button 52px tall on mobile (≤ 600px). No horizontal page scroll at 390px.
- **Breakpoints (viewport):**
  - **≥ 1400 (desktop 1440):** concept layout, with the lower row in three columns (chart 1.25 · sources 1 · section lines 1.1) when `funnel==='ok'`; the order of §4.0 otherwise.
  - **1024–1399:** the chart takes the full width, then the next two cards sit in two columns.
  - **600–1023 (tablet 820):** one column. The funnel becomes a vertical list. The brain strip stacks its three lines.
  - **< 600 (mobile 390):** one column. The scope control is one `<select>` (§4.1). The period switch is full width (three equal 52px buttons). «نزّل التقرير» is full width.
- **Brain avatar:** `v2/img/brain-avatar.jpg` (existing). No new images.
- **Sheets:** every sheet in this section is **D3's existing sheet**: `V2D3.openSheet(title, html)` (shared edit 5), which is `window.openModal` with the `.v3m` body that D3 already restyles (`v2-d3.css:157`). Confirmations go through `V2D3.twoStage`. The legacy `openModal` is never called directly from `reports.js`, and no third container is invented.
- **States, the same everywhere:**
  - Loading: `.v3-empty` with «…جارٍ جمع التقرير».
  - Route failed entirely: `.v3-empty` «التقرير: غير متاح بعد» / «تعذّر الجمع الآن، فلا تعتبر الأرقام صفرًا.» + «أعد المحاولة».
  - Some sources failed: `.v3-warn` «تعذّر جلب: {labels} — ما يظهر ناقص، وليس معناه أنه لا شيء».
  - Timezone failed (§8.1): `.v3-warn` «التوقيت غير متاح، الأيام محسوبة بتوقيت جرينتش».
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
| `delivery` | «إرسال تقرير الأحد» |

`funnel` and `delivery` are listed only when the platform route exists and failed. When the route is simply absent (404), it is not a failure.

---

## 4) Tab «التقرير» (`analysis`, default)

### 4.0 Card order (decided by `sources.funnel`)
- **`funnel !== 'ok'` (today, and whenever the bridge is absent or failed):**
  1. brain strip (§4.2);
  2. «كل قسم في سطر» (§4.6);
  3. «يومًا بيوم» (§4.4);
  4. «من الزيارة إلى الدفع» in **compact mode** (§4.3): only the stages that have numbers, plus one grey line «{٣} خطوات تكتمل حين تسجّل المنصة الزيارات». Section scopes use the same rule.
  5. «من أين يأتي الناس» as **one line**, not a card: title · «غير متاح بعد» · «تكتمل حين تسجّل المنصة مصدر كل زائر وكل دفعة.»
- **`funnel === 'ok'`:** the concept order exactly: brain strip → full funnel card → lower row (chart · origins card · section lines).

Both modes get their own shots (§11).

### 4.1 Header controls
- **Scope:**
  - ≥ 600px: chips (`role="tablist"`, `aria-label="القسم"`): «المنصة كلها» (default) · «الملفات» · «الدورات» · «الكتب» · «السوق» · «المحتوى» · «التسويق». Active chip: ink background, white text. The row wraps; it never scrolls sideways.
  - < 600px: one `<select>` (52px, full width) whose visible text reads «القسم: المنصة كلها ▾».
  - Keys: `all, files, courses, books, market, content, marketing`.
- **Period switch:** reuse `.v3-seg/.v3-pb`, `aria-label="الفترة"`. Options «الأسبوع» (`week`, 7 full days) · «الشهر» (`month`, 30 full days, default) · «٣ أشهر» (`quarter`, 91 full days = 13 full weeks).
- **State in the route, not only in storage:**
  - Scope and period live in the hash: `#s/reports/report?scope=courses&period=week` (shared edit 4). Defaults are left out of the hash.
  - Changing scope or period (chip, select, period button, a section row, a brain link) sets `location.hash = V2L.sectionHash('reports','report',null,{scope,period})`, so it enters browser history and the back button restores the previous view. A link to one scope can be shared or printed.
  - `localStorage['v2r_period']` / `['v2r_scope']` (try/catch) hold only the **default** used when the hash has none.
- **Period line** under the controls, `.v3-ptxt`, from `window.label` + `prev.label`. Examples:
  - «آخر ٣٠ يومًا كاملة (من ٣٠ سبتمبر إلى ٢٩ أكتوبر) مقارنة بالثلاثين يومًا التي قبلها»
  - «آخر ٧ أيام كاملة … مقارنة بالأيام السبعة التي قبلها»
  - «آخر ١٣ أسبوعًا … مقارنة بالثلاثة عشر أسبوعًا التي قبلها»
- **Main button:** «نزّل التقرير» (`.v3-btn1`, the only main button) calls `window.print()`. The print stylesheet (§4.8) hides the shell and controls. No network, no file generation.
- **Freshness (no «حدّث» button):** a small grey line «حُدّث قبل {دقيقتين} · حدّث الآن». «حدّث الآن» is a text link (≥ 44px target) that re-fetches with `fresh=1`. While the tab is visible (`document.visibilityState`), the summary re-fetches by itself every 5 minutes (one `setInterval`, cleared when the view changes).

### 4.2 Brain strip «ملخص العقل» (`aria-label="ملخص العقل"`)
- **Look:** ink `#21262E` background, radius 24, the avatar 64px. Three columns on ≥ 1024, stacked below that. On mobile the strip comes right after the controls, so its first line is visible without scrolling at 390×844.
- **Each line** comes from `summary.brain[i]`:
  - the label in its colour: «شغّال» `#8FD3B0`, «واقف» `#F2B33D`, «فرصة» `#F0A0B8`;
  - the sentence `text` (white, 15px).
- **One button for the whole strip:** a «افتح …» button (`.v3-btn2` on dark, min 44px) appears **only on the highest-priority line that has an action**: «واقف» > «فرصة» > «شغّال». The other lines carry their action as an inline text link inside the sentence's end («← افتح الدورات»).
- **One disclosure for the whole strip:** a text link «على أي أساس؟» (≥ 44px) under the three lines. It expands all three `basis[]` lists together, each item «{label}: {value}» with its source label from §3, plus `window.label`.
- **When `text` is null:** the line shows `empty_text` in grey, or «غير متاح بعد» + `na_reason` when the needed source failed.
- **Actions call existing navigation only:** `V2_HOST.openSection(section, tab)` (= `v2OpenSection`). Labels are listed in §7. No decision is taken from this strip.
- **Scope:** only candidates of the selected scope are considered (§7). For `marketing`, all three lines read «غير متاح بعد» with `na_reason` «تكتمل مع ربط الحملات في قسم التسويق».

### 4.3 Card «من الزيارة إلى الدفع» (`summary.funnel`)
- **Header:** title plus a short period text («آخر ٣٠ يومًا مقارنة بما قبلها»).
- **Full mode (`funnel==='ok'`):**
  - ≥ 1024: five columns. Each column has the label (14px muted), the number (Cairo 28px), the change line, and a bar. Bar heights 70/52/38/26/18px, colours `#9E2B4E #B44E6E #C97590 #DB9DB1 #EBC6D2`. A stage with no number gets a dashed empty bar.
  - < 1024: a vertical list. Each row shows the label, the number and the change line, with a horizontal bar sized by `cur / max(cur of known stages)`.
- **Compact mode (`funnel!=='ok'`):** only stages with a number, as rows (label · number · change line), then one grey line «{n} خطوات تكتمل حين تسجّل المنصة الزيارات». `n` = number of stages with `cur == null`, built with `V2L.util.U` («خطوة واحدة», «خطوتان», «خطوات», «خطوة»). No dashed bars, no empty columns.
- **Stages, whole platform (key → label → interim source):**
  | key | label | source today |
  |---|---|---|
  | `visits` | «زاروا المنصة» | none, «غير متاح بعد» |
  | `asked` | «سألوا سؤالًا» | none for a period, «غير متاح بعد» |
  | `signed_up` | «سجّلوا حسابًا» | platform users (§8.1, source 2) |
  | `opened` | «فتحوا ملفًا أو دورة» | none, «غير متاح بعد» |
  | `paid` | «دفعوا» | dashboard ledger: number of payment rows in the window **for the three services only** (`experts + courses + books`; `other` is never counted) |

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
- **Interim `paid` sub-line:** «عمليات دفع في الملفات والدورات والكتب، وقد يدفع الشخص أكثر من مرة».
- **Section scopes** replace the five stages with the section's own journey. Title: «رحلة {اسم القسم}». The compact rule applies the same way.
  - **files:** «سألوا سؤالًا» (n/a) → «فتحوا ملفًا» (n/a) → «دفعوا» (ledger `experts` count)
  - **courses:** «زاروا صفحة دورة» (n/a) → «سجّلوا في دورة» (n/a) → «دفعوا» (ledger `courses` count)
  - **books:** «زاروا صفحة كتاب» (n/a) → «ضغطوا «اشترِ»» (n/a) → «دفعوا» (ledger `books` count)
  - **market:** «طلبات جديدة» (market `new`) → «جاءها عرض» (market `with_offers`) → «تمّ الاتفاق» (market `matched`)
  - **content:** «مقالات نُشرت» (content `published`) → «زيارات المقالات» (n/a) → «حسابات جاءت من مقال» (n/a)
  - **marketing:** see §4.7.

### 4.4 Card «يومًا بيوم» (`summary.daily`; title «أسبوعًا بأسبوع» for `quarter`)
- **Chart:** inline SVG (`viewBox 0 0 560 300`, `width:100%`, mobile height 220). No library. Buckets cover **full days only** (§8.1); today is never a point on the line.
  - **Series 1, «الدخل بالجنيه»:** EGP only, solid ink line `#21262E` 2.5px with a light area fill, from `daily.rows[].income_egp`.
  - **Series 2, «حسابات جديدة»:** burgundy `#9E2B4E` 3px line on its own right-hand scale, from `daily.rows[].signups`. When `users` is not complete for the window, the series is not drawn.
  - **Visitors:** drawn only when `visits_available` (N3), as a burgundy line; signups then move to a dashed line.
- **Legend:** lists **only the series that are drawn**. Anything not drawn is said once, in the card's footnote: «الزوار: غير متاح بعد» (and «الحسابات الجديدة: غير متاح بعد» when that series is hidden).
- **Today so far:** under the chart, a separate line from `summary.today`: «اليوم حتى الآن: {١٬٢٠٠ جنيه} · {٤ حسابات}» (each part «غير متاح بعد» when its source failed). It is never drawn on the line and never enters a comparison.
- **Axes:** four light grid lines (`#F0EAE1`). Bottom labels only at the first, middle and last bucket («١ أكتوبر»).
- **Interaction:** tapping or hovering a bucket shows a small ink tooltip «{التاريخ}: {الدخل} · {n} حسابًا» (keyboard: the SVG has `tabindex=0` and arrow keys move between buckets). `aria-label` example: «الدخل والحسابات الجديدة في آخر ٣٠ يومًا».
- **Foreign currency:** when `daily.income_other` is non-empty, a line under the chart reads «دخل بعملة أخرى في الفترة: {٣٠ دولار · ١٠٠ ريال}». It is never converted.
- **Empty:** «لا دخل ولا حسابات جديدة في هذه الفترة».
- **Section scope:** income for that section only (the ledger service), with no signups line. `market`, `content` and `marketing` show «غير متاح بعد» and the reason «لا يوجد دخل يومي لهذا القسم».

### 4.5 «من أين يأتي الناس» (`summary.origins`)
The concept's «الناس جايين منين» is colloquial; the founder rule is standard Arabic.
- **Without N1/N3 (today):** one line, not a card (§4.0, item 5). No empty blocks.
- **With N3 (`funnel==='ok'` and `origins.channels` non-null):** the concept card with three blocks:
  1. **«القنوات»:** bars per channel. Labels: «بحث جوجل», «فيسبوك وإنستجرام», «واتساب», «دخلوا مباشرة», «دعوات الخبراء», «مواقع أخرى». Each bar shows the share of signups as «{pct}٪» with the count in its tooltip.
  2. **«البلاد»:** chips «مصر ٦٤٪»… (share of signups), top 6 plus «بلاد أخرى».
  3. **«أكثر الصفحات التي جاءت بالناس»:** top 3 pages with visit counts.
  A single block whose value is still `null` shows «غير متاح بعد» in place. No invented split.

### 4.6 Card «كل قسم في سطر» (`summary.sections`)
- **Row:** name (flex 1) · value (Cairo 800) · chip (`.st`) · chevron. The whole row is a button ≥ 52px. Clicking it changes the route to that scope (§4.1, enters history). Inside a section scope, the card shows only that row expanded, plus a button «افتح {القسم}».
- **Rows:**
  | key | label | value | chip | under-line | «افتح» target |
  |---|---|---|---|---|---|
  | `files` | «ملفات الخبراء» | EGP income in the window from the ledger service `experts` («١١٢٬٤٠٠ جنيه») | trend | «تشمل الاستشارات العادية» while the source is the ledger (§7 note) | `files` |
  | `courses` | «الدورات» | ledger `courses` | trend | — | `courses` |
  | `books` | «الكتب» | ledger `books` | trend | — | `books` |
  | `market` | «سوق الخدمات» | «{n} طلبًا جديدًا» (market `new`) | «{u} بلا عرض» (red if > 0, otherwise grey «كلها جاءها عرض») | — | `market` |
  | `content` | «المحتوى» | «{n} مقالًا نُشر» (content `published`) | «الزيارات: غير متاح بعد» (grey) until N3 | — | `content` |
  | `satisfaction` | «رضا العملاء» | «غير متاح بعد» until N5 | `V2L.util.U(d, [«نزاع مفتوح», «نزاعان مفتوحان», «نزاعات مفتوحة», «نزاعًا مفتوحًا»])` (red if > 0; «لا نزاع مفتوح» grey at 0) from `disputes.total` — **the same number as the dispute part of the board's «النزاعات» tile** (§8.1 source 5); open now, not per window | — | `disputes` |

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
- **Footer line:** `summary.delivery.text` (§6.3) plus a text link «افتح تقرير الأحد», which opens tab `sunday`.

### 4.7 Scope = «التسويق»
The brain strip, funnel and chart show «غير متاح بعد» with the reason «تكتمل مع ربط الحملات في قسم التسويق». The section-lines card shows one line, «التسويق: افتح قسم التسويق لأرقام الحملات», with a button «افتح التسويق» (`openSection('marketing')`). Reports does not read the marketing tables, because the marketing section owns them and two readings of one number are forbidden.

### 4.8 Print (`@media print` in `reports.css`)
- Hide the shell, side menu, tabs, controls, buttons and links. Paper background, ink text, no shadows.
- Print header (hidden on screen): «البروفيسور · تقرير {النطاق} · {window.label}», plus «أُعدّ في {generated_at بتوقيت القاهرة}».
- Brain lines print with their basis lists expanded.
- The chart prints as is (SVG). Cards print in the order of §4.0.
- Cards use `page-break-inside: avoid`.

---

## 5) Tab «ما يسأل عنه الناس» (`v2r_demand`): rebuilt around the opportunity
**Data:** the existing loader `EP.ensure('analysis')` → `GET /api/platform-chat-insights` (→ `/api/bridge/chat-insights`). The response is read as is (`total, needs_expert, needs_expert_rate, anonymous, authed, by_segment, by_country, by_category, by_subcategory, by_intent, unmet, classified, unclassified, recent_questions[≤40], expert_opinions{requested, paid, conversion_rate}`). No new route.
**States:**
- `EP.state.analysis === 'loading'|'idle'`: skeleton «…جارٍ جلب الأسئلة».
- `'error'`: `.v3-empty` «أسئلة المحادثة: غير متاح بعد» / «تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.» + «أعد المحاولة» (`EP.reload('analysis')`).
- Ready with `total === 0`: «لم يصل أي سؤال بعد».

**Layout, top to bottom (one column on all sizes; max width 1040 on desktop):**
1. **Title row + numbers line.** Under the tab heading, **one compact line** of the four numbers (wraps on mobile, no cards):
   «{total} سؤالًا · {needs_expert} تحتاج رأي خبير ({rate}٪) · {authed} عضو و{anonymous} زائر · دفع {paid} من {requested} مقابل رأي خبير ({pct}٪) · من {n} بلدًا»
   - `expert_opinions` missing ⇒ that part reads «الدفع مقابل رأي خبير: غير متاح بعد».
   - n = `by_country` entries with code ≠ `unknown` and count > 0.
   - At the end of the same row, the **one secondary button** «صنّف الأسئلة الجديدة ({unclassified})» (`.v3-btn2`), hidden when `unclassified === 0` (the line then ends «· كل الأسئلة مصنّفة»). Behaviour in «Classify» below.
2. **Main card «خدمات يطلبها الناس ولا نقدّمها»** (`unmet`), wine border, first thing after the line:
   - The top row is large: «{label}: {count} سؤالًا», «مثال: {sample_question}», and the screen's **main button** «افتح الدورات» (`.v3-btn1`, `openSection('courses')`, the same destination as the old `go('courses')`).
   - Further rows (if any) are smaller, each with a text link «افتح الدورات».
   - Basis line: «من كل الأسئلة منذ البداية».
   - Empty: «لم يظهر طلب متكرّر لا نقدّم له خدمة حتى الآن.» (the card stays, grey).
   - The section's brain line «فرصة» uses the first row (§7).
3. **«أحدث الأسئلة»** card. Header: count of the filtered list and the hint «آخر ٤٠ سؤالًا تصل من المنصة» (a fact: the platform caps the list at 40).
   - **One visible filter:** chips «الكل» · «تحتاج خبيرًا».
   - **«تصفية ▾»** (≥ 44px) opens the rest: on desktop an inline panel under the chips; on mobile a D3 sheet (`V2D3.openSheet('تصفية الأسئلة', …)`) with «اعرض النتائج» (52px). Inside: selects «كل الشرائح» / «كل البلاد» / «كل المجالات» (the last only if `by_category` is non-empty); chips «لا تحتاج»; chips «كل الوقت» · «آخر ٧ أيام» · «آخر ٣٠ يومًا».
   - When a hidden filter is on, the button reads «تصفية ({n}) ▾» and a text link «امسح التصفية» appears.
   - State in a module variable (not the old global `anFilters`).
   - **Row:** a button, full width, ≥ 56px. The question text (2 lines max, ellipsis) above meta chips: segment label · country label · category (normalised) · «تحتاج خبيرًا» (wine) · «زائر» or «عضو» · «افتح المحادثة ←». Rows without `id` are not clickable.
   - **Empty:** «لا أسئلة تطابق التصفية» / «لا أسئلة بعد».
4. **«التفصيل»**: a `<details>` section, **open by default at ≥ 1024, closed below**. Summary text «التفصيل: حسب الشريحة والبلد والمجال والمطلوب». Inside, four bar cards (two columns at ≥ 1024, one below):
   - «حسب الشريحة» (`by_segment`, with `unknown` last)
   - «حسب البلد» (`by_country`)
   - «حسب المجال القانوني» (`by_category`, with a chip row «أكثر المجالات الفرعية» from `by_subcategory`, top 10)
   - «حسب المطلوب» (`by_intent`)

   Hint «على كل الأسئلة · اضغط للتصفية». Each bar is a button ≥ 44px. Pressing it sets the matching filter in block 3 and scrolls to it (the intent bar does not filter, as before). When a classification card is empty: «لم تُصنَّف الأسئلة بعد — اضغط «صنّف الأسئلة الجديدة»» if `unclassified > 0`, otherwise «لا بيانات بعد».

**Classify («صنّف الأسئلة الجديدة»).** This runs a **paid** classification on the platform (DeepSeek, per `DASHBOARD-MAP-2026-10-30.md:115`), so it is never a one-tap action:
- The button opens a D3 sheet `V2D3.openSheet('تصنيف الأسئلة الجديدة', …)`: «سيُصنَّف {min(unclassified,100)} سؤالًا جديدًا (١٠٠ بالكثير في المرة). التصنيف يعمل على المنصة وله تكلفة صغيرة.» + «صنّف الآن» (`.v3-btn1`) + «إلغاء».
- «صنّف الآن» calls the **existing endpoint** directly, `EP.api('/platform-chat-insights/classify?limit=100', {method:'POST', body:{}})`, then `EP.reload('analysis')`. We do not call `EP.runDemandClassify`, because its toasts are old colloquial copy.
  - Busy: disabled, text «…جارٍ التصنيف»; the sheet cannot close.
  - Done: sheet closes; `.v3-ok` «صُنّف {classified} سؤالًا جديدًا» (+ « · بقي {remaining}» when > 0).
  - `r.error` or failure: `.v3-err` in the sheet «تعذّر التصنيف الآن، جرّب بعد قليل».
- It is never triggered automatically, on load, or by the brain. It is not money, so it does not use `twoStage` or `confirmed:true`.

**Label maps:** reuse the existing globals `SEG_LABEL`, `COUNTRY_LABEL` and `catAr` from `index.html` through `typeof` guards (they are top-level `const`s in a classic script, so they are reachable by name). Do not duplicate them; if one is missing, fall back to the raw value. One copy fix is applied at display time only: segment `influencer` shows «مؤثر أو رائد أعمال» instead of «مؤثر/رائد أعمال».

**Conversation sheet:**
- Container: `V2D3.openSheet(title, html)` (§3 «Sheets»): D3's restyled modal with a `.v3m` body. `reports.js` adds the class `v2r-side` to the returned scrim, and `reports.css` turns `#epModal.v2r-side .modal` into a right-side panel (420px, full height) at ≥ 1024 and a full-height sheet below. A «أغلق» button (52px) sits at the bottom; Esc (a keydown listener added on open, removed on close) and the scrim also close it. `reports.js` never calls `window.openModal` itself.
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
### 6.1 Data
`GET /api/v2/reports/weekly[?week=YYYY-MM-DD]` (§8.2). The default is the last **complete** week, Sunday 00:00 to Saturday 24:00, Cairo time, compared with the week before.

### 6.2 Header
- «تقرير الأسبوع»;
- the date line «من الأحد {١٩ أكتوبر} إلى السبت {٢٥ أكتوبر ٢٠٢٦}، مقارنة بالأسبوع الذي قبله»;
- navigation «الأسبوع السابق» / «الأسبوع التالي» (buttons ≥ 44px; «التالي» disabled on the latest complete week; at most 12 weeks back, after which «السابق» is disabled);
- «نزّل التقرير» (main button, print) and «انسخ النص» (secondary). The latter copies `weekly.text` with `navigator.clipboard.writeText` (try/catch), then shows `.v3-ok` «نُسخ نص التقرير»; when the clipboard is blocked, it selects the text in a read-only box instead.

### 6.3 Delivery panel «الإرسال كل أحد» (top of the body, above the letter)
State comes from `weekly.delivery` (§8.2): `{setting: bool, bridge: 'absent'|'ok'|'failed', platform_enabled: bool|null, last_sent_week: str|null}`.
- **Status line** (also used as `summary.delivery.text` in §4.6):
  | condition | text |
  |---|---|
  | `bridge==='absent'` | «الإرسال كل أحد: غير متاح بعد — ينتظر تجهيز الإرسال على المنصة» |
  | `bridge==='failed'` | «الإرسال كل أحد: تعذّر التحقق الآن» (+ warn label «إرسال تقرير الأحد») |
  | `setting===false` | «الإرسال كل أحد: متوقف» |
  | `setting && platform_enabled` | «يصلك هذا التقرير كل أحد ٨ صباحًا على تليجرام» (+ « · آخر إرسال: أسبوع {١٩ أكتوبر}» when `last_sent_week`) |
  | `setting && !platform_enabled` | «الإرسال مفعّل هنا، والمنصة لم تفعّله بعد» |
- **Toggle «الإرسال كل أحد»** (secondary button «شغّل الإرسال» / «أوقف الإرسال»): opens `V2D3.twoStage` with a review diff «الإرسال كل أحد: متوقف ⇒ يعمل» and «أكّد»; sends `PUT /api/v2/reports/weekly/settings {enabled, confirmed:true}`. Disabled (with the status line as its reason) when `bridge==='absent'`.
- **«أرسل الآن إلى تليجرام»** (secondary): opens `V2D3.twoStage`; the review stage shows the week label, the channel «تليجرام» and the first 6 lines of `text`, then «أكّد الإرسال». It sends `POST /api/v2/reports/weekly/send {week, confirmed:true}`. Results: `sent` ⇒ `.v3-ok` «أُرسل التقرير»; `already` ⇒ `.v3-ok` «أُرسل تقرير هذا الأسبوع من قبل»; `404` ⇒ «غير متاح بعد». Disabled when `bridge==='absent'`.

### 6.4 Body (letter-like single column, max width 860, paper card)
1. «ملخص العقل»: the same three lines, one action button and the shared «على أي أساس؟» as §4.2, for the week.
2. «الأرقام»: the funnel as a compact row of the stages that have numbers (§4.3 compact rule), with change lines (vertical list on mobile).
3. «كل قسم في سطر»: same rows as §4.6.
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
4. Otherwise `text: null`, `empty_text`: «لا نموّ واضح في هذه الفترة.»

Action: «افتح {القسم}» → `openSection(key)`.

**«واقف» (`stalled`), first match wins:**
1. A money section with prev count ≥ 1 and cur count 0: «{الكتب}: لا بيع في هذه الفترة، وكان {٣} عمليات في الفترة التي قبلها.»
2. A money section with prev EGP > 0, pct ≤ −10 and prev count ≥ 3, taking the largest drop: «{دخل الكتب} نزل {٢٢}٪: من {…} إلى {…} جنيه.»
3. Market `unanswered > 0`: «{١١} طلبًا في السوق بلا عرض من خبير.» Action «افتح السوق».
4. Signups pct ≤ −10 with prev ≥ 5: «الحسابات الجديدة نزلت {١٢}٪: {٩٢} مقابل {١٠٥}.»
5. Otherwise `empty_text` «لا تراجع واضح في هذه الفترة.»

**«فرصة» (`opportunity`), first match wins, scopes all/market/courses/files:**
1. `chat.unmet[0]`, which already passes the platform's `UNMET_MIN_COUNT`: «{٤١} سؤالًا عن «{تأسيس الشركات}» ولا نقدّم له خدمة بعد.» The basis states «كل الأسئلة منذ البداية» (the platform gives no period for this). Action «افتح الدورات».
2. Market requests in the window with `need_kind == 'course'`, count ≥ 3: «{٥} طلبات في السوق تطلب دورة، ولا يوجد عرض لأغلبها.» This is used only if `unanswered` among them is > half. Action «افتح السوق».
3. Otherwise `empty_text` «لا فرصة واضحة في الأسئلة والطلبات حتى الآن.»

**Priority for the strip's single button (§4.2):** `stalled` > `opportunity` > `working`, first line that has an `action`. The payload carries `brain_primary: "stalled"|"opportunity"|"working"|null`.

**What «ملفات الخبراء» income includes.** While the source is the dashboard ledger, the `experts` service includes ordinary consultations (STATUS-D3 decision A5); the D3 bridge `/api/bridge/income/by-service` accepts only a calendar `month`, not a rolling window, so it cannot replace it here. Therefore:
- every brain sentence about `files` adds to its `basis` the item «ما يشمله الرقم: ملفات الخبراء والاستشارات العادية» (source «دفتر الإيرادات»);
- the section row keeps the under-line «تشمل الاستشارات العادية»;
- when N3 is present, `files` income comes from `sections.files.income` (expert files only), and both caveats disappear.
- The label is always «ملفات الخبراء» (never «الاستشارات»).

**General rules:**
- A failed source needed by a rule makes that rule skip (it never counts as 0).
- When every rule of a line skipped **because of failures**, the line is `text: null`, `na_reason` «تعذّر جلب {labels}».
- Percentages are rounded to whole numbers. Money is EGP only, and the basis says «النسبة بالجنيه فقط» when foreign currency exists.
- Names in sentences come from a fixed map: «دخل ملفات الخبراء», «دخل الدورات», «دخل الكتب» (in the zero-sale form: «ملفات الخبراء», «الدورات», «الكتب»).
- No sentence starts with «الذكاء» or «AI». None uses «يقوّم». All are gender-neutral (people are «الناس», «أصحاب الطلبات»).

---

## 8) Server routes (new file `backend/v2_reports_routes.py`)
The admin routes share these rules:
- `@token_required @roles_required('admin')`;
- `_v2_closed()` first (404 when the switch is off, and **no** platform call);
- `Cache-Control: no-store` via `_v2_ns`;
- GET routes are read-only (no `_audit`, nothing written);
- the response carries **no PII**: no emails, names, phones or question texts, only counts and sums.

`register(app, g)` takes the helpers from `g` (the `app.py` globals): `token_required`, `roles_required`, `_v2_closed`, `_v2_ns`, `_v2_confirmed`, `_v2_write`, `_v2_mask_auth`, `_platform_proxy`, `_resp_ok`, `_audit`, `PLATFORM_METRICS_SECRET`, `Revenue`, `Article`, `Setting`, `db`. This avoids a circular `import app`.

### 8.1 `GET /api/v2/reports/summary?period=week|month|quarter&scope=all|files|courses|books|market|content|marketing[&fresh=1]`
- **Validation:** bad `period` → 400 «فترة غير معروفة»; bad `scope` → 400 «قسم غير معروف».
- **Window (full days only):**
  - Timezone `Africa/Cairo` via `zoneinfo`, backed by the `tzdata` package (§1). A test asserts `ZoneInfo('Africa/Cairo')` loads.
  - If it still fails at runtime: compute in UTC, set `sources.window = 'failed'`, and the screen shows the timezone warn strip (§3). **No fixed offset** is ever assumed (Cairo is UTC+2 in winter and UTC+3 in summer).
  - `until` = the start of **today**, Cairo time (today is excluded).
  - `from = until − N days` (N = 7 / 30 / 91).
  - `prev = [from − N, from)`. Both windows are the same length.
  - Buckets: day for week/month; 7-day blocks aligned to `until` for quarter.
  - `today = [until, now)` is computed separately for `summary.today` (income EGP + other currencies, signups). It is never part of a comparison or a brain rule.
- **Sources:** fetched in parallel (`ThreadPoolExecutor`, one call each, 12 s timeout, no retry). Each one fails alone and becomes `null`:
  1. **`ledger`:** local SQLite. `Revenue.query.filter(Revenue.date >= prev.from, Revenue.date < now_date_end)`.
     - Per row: EGP from `amount_egp`, USD from `amount_usd`, any other currency from `amount_original` when `needs_fx`.
     - The service comes from `_service_of(source)`, mirroring `serviceOf` in `v2-logic.js:1432` exactly (`consultation|consulting|expert_file|expert_case` → experts; `course|course_offer|program` → courses; `book|knowledge` → books; else other). It is guarded by a parity test (§10).
     - It never reads `total_egp`, which is converted at an exchange rate.
     - Output per window: `{services:{experts|courses|books|other: {count, totals:[{currency, amount}]}}, paid_count, totals}`, plus per-bucket `income_egp` and `count`.
     - **`paid_count` and the daily `income_egp` count only `experts + courses + books`.** `other` (`sale`, `subscription`, `ads_deposit`, manual rows, anything unmapped) is kept in `services.other` for the record but never enters «دفعوا», a section row, a bucket or a brain rule.
  2. **`users`:** `_platform_proxy('GET','/api/bridge/users', params={'limit':1000})`.
     - Count `created_at` (converted to a Cairo date) per window and per bucket.
     - `complete_for(window)` = `len(rows) < 1000` **or** the oldest `created_at` < window start. An incomplete window → `null` (never a partial count).
  3. **`market`:** `_platform_proxy('GET','/api/bridge/market/requests', params={'author_kind':'member','include_test':'false','limit':500})`.
     - Per window: `new` (created in the window), `with_offers` (`offer_count > 0`), `matched` (`status == 'matched'`), `unanswered` (`status == 'open'` and `offer_count == 0`), `course_need` (`need_kind == 'course'`, with its own unanswered count).
     - Completeness rule as for users (`total ≤ 500` or the oldest item is before the window start).
  4. **`content`:** local SQLite `Article.query.filter(Article.status == 'published', Article.published_at >= from, < until).count()` per window.
  5. **`disputes`:** `_platform_proxy('GET','/api/bridge/ops/queue')`, the same source the board's «النزاعات» tile reads. `total = expert_files_disputed + expert_files_case_disputed + consultation_disputes`, **the exact formula of the tile's dispute part (`v2-logic.js:211`, variable `d`)**. A missing key counts as failed (→ `null`), never 0. Open now, not per window. (The old `consultations?status=disputed` read is dropped: it missed expert-file and case disputes.)
  6. **`chat`:** `_platform_proxy('GET','/api/bridge/chat-insights', params={'limit':3000})`. Only `unmet[0]`, `classified` and `unclassified` are kept (no question text in the response).
  7. **`funnel`:** `_platform_proxy('GET','/api/bridge/reports/funnel', params={'from','until','scope','tz'})`.
     - 404 → `'absent'` (silent; the interim sources are used).
     - 200 → its non-null values **replace** the interim value of the same stage, section or bucket. One number, one source: the interim reading is not shown beside it.
     - Any other error → `'failed'` (warn strip), and interim is used.
  8. **`delivery`:** the local `Setting` `v2r_weekly_delivery` (`'1'`/missing) + `_platform_proxy('GET','/api/bridge/reports/weekly/delivery')` (404 → `'absent'`, other error → `'failed'`). Used only to build `delivery` (§6.3).
- **Cache:** in-process 60 s, keyed `(scope, period, from, until)`. `fresh=1` bypasses it. (The front-end's 5-minute refresh does not pass `fresh=1`.)
- **Response:**
```json
{
 "ok": true, "scope": "all", "period": "month",
 "window": {"from": "2026-09-30", "until": "2026-10-30", "days": 30, "tz": "Africa/Cairo", "label": "آخر ٣٠ يومًا كاملة (من ٣٠ سبتمبر إلى ٢٩ أكتوبر)"},
 "prev": {"from": "2026-08-31", "until": "2026-09-30", "label": "الثلاثون يومًا التي قبلها"},
 "generated_at": "2026-10-30T09:12:00+02:00",
 "sources": {"window": "ok|failed", "ledger": "ok", "users": "ok|partial|failed", "market": "ok|partial|failed", "content": "ok", "disputes": "ok|failed", "chat": "ok|failed", "funnel": "absent|ok|failed", "delivery": "absent|ok|failed"},
 "layout": "compact|full",
 "funnel": {"title": "من الزيارة إلى الدفع", "mode": "compact", "missing": 3, "missing_text": "٣ خطوات تكتمل حين تسجّل المنصة الزيارات", "stages": [
   {"key": "visits", "label": "زاروا المنصة", "cur": null, "prev": null, "change_pct": null, "trend": "na", "conv_pct": null, "conv_text": null, "sub": null},
   {"key": "signed_up", "label": "سجّلوا حسابًا", "cur": 124, "prev": 105, "change_pct": 18, "trend": "up", "conv_pct": null, "conv_text": null, "sub": null},
   {"key": "paid", "label": "دفعوا", "cur": 31, "prev": 28, "change_pct": 11, "trend": "up", "conv_pct": null, "conv_text": null, "sub": "عمليات دفع في الملفات والدورات والكتب، وقد يدفع الشخص أكثر من مرة"}
 ]},
 "daily": {"bucket": "day|week", "rows": [{"from": "2026-09-30", "label": "٣٠ سبتمبر", "income_egp": 1200.0, "signups": 4, "visits": null}], "income_other": [{"currency": "USD", "amount": 30}], "signups_available": true, "visits_available": false},
 "today": {"income_egp": 1200.0, "income_other": [], "signups": 4},
 "origins": {"channels": null, "countries": null, "top_pages": null, "note": "تكتمل حين تسجّل المنصة مصدر كل زائر وكل دفعة."},
 "sections": [
   {"key": "files", "label": "ملفات الخبراء", "value": {"kind": "money", "egp": 112400.0, "others": [], "count": 41}, "prev": {"egp": 85800.0, "count": 33}, "trend": {"key": "up", "pct": 31}, "chip": {"text": "ينمو ٣١٪", "tone": "up"}, "note": "تشمل الاستشارات العادية", "open": "files"},
   {"key": "market", "label": "سوق الخدمات", "value": {"kind": "count", "n": 38, "text": "٣٨ طلبًا جديدًا"}, "chip": {"text": "١١ بلا عرض", "tone": "bad"}, "open": "market"},
   {"key": "satisfaction", "label": "رضا العملاء", "value": null, "chip": {"text": "نزاعان مفتوحان", "tone": "bad"}, "open": "disputes"}
 ],
 "brain": [
   {"key": "working", "label": "شغّال", "text": "…", "empty_text": null, "na_reason": null, "basis": [{"label": "دخل ملفات الخبراء الآن", "value": "١١٢٬٤٠٠ جنيه", "source": "دفتر الإيرادات"}, {"label": "ما يشمله الرقم", "value": "ملفات الخبراء والاستشارات العادية", "source": "دفتر الإيرادات"}], "action": {"label": "افتح ملفات الخبراء", "section": "files", "tab": null}},
   {"key": "stalled", "...": "..."}, {"key": "opportunity", "...": "..."}
 ],
 "brain_primary": "stalled",
 "delivery": {"setting": false, "bridge": "absent", "platform_enabled": null, "last_sent_week": null, "text": "الإرسال كل أحد: غير متاح بعد — ينتظر تجهيز الإرسال على المنصة"}
}
```
`layout` = `full` only when `sources.funnel == 'ok'`. Every Arabic number string in the payload is built with one Python helper, `_ar(n)`: Arabic-Indic digits, «٬» grouping, «٫» decimal. Numeric fields stay numeric for the front-end, which formats them with `V2L.util`.

### 8.2 `GET /api/v2/reports/weekly[?week=YYYY-MM-DD]`
- `week` must be a Sunday (Cairo) whose week has ended: `week + 7 days ≤` the start of the current week. Otherwise 400 «اختر أسبوعًا اكتمل». More than 12 weeks back → 400 «أقدم أسبوع متاح: {date}».
- Same builder with `window = [week, week+7)`, `prev = [week−7, week)`, daily buckets and scope `all`.
- Adds:
  - `"week": {"start": "…", "end": "…", "label": "من الأحد ١٩ أكتوبر إلى السبت ٢٥ أكتوبر ٢٠٢٦"}`;
  - `"nav": {"prev": "YYYY-MM-DD"|null, "next": "YYYY-MM-DD"|null}`;
  - `"text"`: plain Arabic text of the whole report (brain lines, funnel numbers, section lines, one per line, the «غير متاح بعد» items included). It is what «انسخ النص», «أرسل الآن» and the Sunday cron send. Built by one function `weekly_text(payload)`.
- Cache 10 min for the numbers (a finished week does not change); `delivery` is re-read on every call (not cached).

### 8.3 `PUT /api/v2/reports/weekly/settings` (admin)
- Body `{enabled: bool, confirmed: true}`; `_v2_confirmed` first (400 without it); `enabled` not a bool → 400 «اختر تشغيل الإرسال أو إيقافه».
- Writes the local `Setting` `v2r_weekly_delivery` = `'1'` or deletes it; `_audit('reports.weekly_delivery', target='weekly', meta={'enabled': …})`. No platform call.
- Returns the new `delivery` object.

### 8.4 `POST /api/v2/reports/weekly/send` (admin, «أرسل الآن»)
- Body `{week?: 'YYYY-MM-DD', confirmed: true}`; `_v2_confirmed` first. Default week = last complete week; the same validation as §8.2.
- Builds `weekly_text` for that week, then `_v2_write('POST', '/api/bridge/reports/weekly/deliver', {week_start, text, confirmed: True}, 'reports.weekly_send', week_start, {'by': 'manual'})` (`by` comes from the token inside `_v2_write`).
- Platform 404 → 404 `{error: 'غير متاح بعد', na: true}` with **no audit and no write**.

### 8.5 `POST /api/v2/reports/weekly/deliver` (cron, secret-gated)
- Guard: `X-ELP-Metrics-Secret` compared with `PLATFORM_METRICS_SECRET` via `secrets.compare_digest` (the same pattern as `/api/content/sync-cron`, `app.py:10746`). Wrong or missing → 401. Switch off → 404 with zero platform calls.
- Local setting off → 200 `{sent: false, reason: 'off'}`, no platform call.
- Otherwise: last complete week, `weekly_text`, then `_platform_proxy('POST', '/api/bridge/reports/weekly/deliver', json_body={week_start, text, by: 'cron', confirmed: True}, timeout=25)`.
  - Platform 404 → 200 `{sent: false, na: 'غير متاح بعد'}`, nothing written.
  - Success → `_audit('reports.weekly_cron', target=week_start, meta={'sent': …, 'already': …})` and the platform's `{sent, already}`.
  - Other error → 502 (the cron sees red; the platform's per-week claim makes a manual re-run safe).
- It never 5xx's silently and never retries by itself.
- The schedule (Sunday 08:00 Cairo) is an outside caller, like the existing crons; see «محتاج منك» (§13).

---

## 9) Buttons: what each one calls
| Button | Where | Calls |
|---|---|---|
| Scope chips / select / period switch | التقرير | route change (`#s/reports/report?scope=&period=`), then `GET /api/v2/reports/summary` (cached) |
| «حدّث الآن» (text link) | التقرير | same with `fresh=1` |
| «نزّل التقرير» | التقرير, تقرير الأحد | `window.print()` |
| «على أي أساس؟» (one per strip) | brain strip | local disclosure of all three lists |
| Brain action («افتح …», one button + text links) | brain strip | `V2_HOST.openSection(section[, tab])` (existing `v2OpenSection`) |
| Section row | كل قسم في سطر | route change to that scope |
| «افتح {القسم}» | section row in scope view | `V2_HOST.openSection(open)` |
| «افتح تقرير الأحد» | footer | `V2_HOST.openSection('reports','sunday')` |
| «افتح التسويق» | marketing scope | `V2_HOST.openSection('marketing')` |
| «صنّف الأسئلة الجديدة» → «صنّف الآن» | ما يسأل عنه الناس | confirm sheet, then existing `POST /api/platform-chat-insights/classify?limit=100`, then `EP.reload('analysis')` |
| «تصفية ▾» / filter chips / selects / bars | ما يسأل عنه الناس | local filter (sheet on mobile) |
| Question row | ما يسأل عنه الناس | existing `GET /api/platform-chat-insights/<id>` → D3 sheet |
| Person link in sheet | sheet | `V2_HOST.openPerson(email)` (existing `v2OpenPerson`) |
| «افتح الدورات» | opportunity card | `V2_HOST.openSection('courses')` |
| «الأسبوع السابق/التالي» | تقرير الأحد | `GET /api/v2/reports/weekly?week=` |
| «انسخ النص» | تقرير الأحد | `navigator.clipboard.writeText(weekly.text)` |
| «شغّل/أوقف الإرسال» | تقرير الأحد | `V2D3.twoStage` → `PUT /api/v2/reports/weekly/settings {enabled, confirmed:true}` |
| «أرسل الآن إلى تليجرام» | تقرير الأحد | `V2D3.twoStage` → `POST /api/v2/reports/weekly/send {week, confirmed:true}` |
| «أعد المحاولة» | any failed state | the same GET again |

No money action exists in this section. The two delivery actions and classify go through a confirmation sheet anyway, because they send or spend.

---

## 10) Tests: `backend/tests/test_v2s_reports.py` (zero real network, zero paid calls)
Use the same harness pattern as `test_v2_d3.py`: the Flask test client, the fake platform (`reports_fixtures.ReportsPlatform`, a subclass of `v2_fixtures.V2Platform`), and the in-memory SQLite.

**pytest, routes:**
1. Admin routes: no token → 401; `employee` → 403; switch off → 404 with **zero** platform calls; `Cache-Control: no-store`.
2. Validation: bad period/scope → 400 with the Arabic message. `week` not a Sunday, in the current week, in the future, or older than 12 weeks → 400.
3. Windows: week/month/quarter lengths 7/30/91 **full days**; `until` = start of today in Cairo; `prev` is adjacent and of equal length. The Cairo boundary is tested with a frozen clock at 23:30 UTC (= next day in Cairo) **in both summer (UTC+3) and winter (UTC+2)** dates. Quarter buckets are 13 blocks of 7 days. A ledger row dated today appears in `today` and in no bucket.
4. Timezone: `ZoneInfo('Africa/Cairo')` loads in the test environment. With `ZoneInfo` patched to raise, `sources.window == 'failed'` and the windows are UTC days (no fixed offset).
5. Ledger:
   - EGP, USD and a `needs_fx` SAR row are never summed together;
   - `total_egp` is never read (a row with only `total_egp` contributes nothing);
   - rows outside the window are excluded;
   - the mapping of every `source` value goes through `_service_of`;
   - rows with `source` = `ads_deposit`, `subscription`, `sale` and a manual row do **not** change `paid.cur`, any section row, any bucket or any brain line.
6. **Parity with D3:** for a calendar-month window, Python ledger sums per service per currency == `V2L.v2Income(rows,'month',now)` via `v2_node.logic`, using the same rows from `/api/revenues`.
7. Users completeness: 1000 rows all inside the window → `signed_up.cur` is `null` (not 1000). 999 rows → exact count. The oldest row before `prev.from` → both windows exact.
8. Market: the same completeness rule; `unanswered` counts only `open` with `offer_count == 0`; platform cards and test rows are excluded (query params asserted).
9. **Disputes parity with the board tile:** for three `ops/queue` fixtures (all zero; only expert-file disputes; mixed with `consultation_disputes` and case disputes), `disputes.total` equals the dispute part of the tile: run `V2L.v2Tiles(Q, {})` in node and assert `tile.hot === (total > 0)` and, when > 0, `tile.next` contains `U(total, ['نزاع واحد','نزاعان','نزاعات','نزاعًا'])`. A queue missing one of the three keys → `disputes` `failed`, chip «غير متاح بعد». The old `consultations?status=disputed` path is never called.
10. Each source failing alone (500/502/timeout/401) → its fields are `null`, `sources[k] == 'failed'`, the other numbers are unchanged, and **no `0` replaces a failed number** anywhere in the payload (a recursive assertion over the JSON).
11. Funnel bridge: 404 → `'absent'`, `layout == 'compact'`, `funnel.missing == 3` and interim values; 200 → `layout == 'full'`, platform values replace interim (signups from the funnel even when users also loaded; `paid` uses `paid_people`; `files` income from `sections.files.income` and the «تشمل الاستشارات العادية» note and basis item are gone); 500 → `'failed'`, compact, interim values.
12. Brain rules, one test per rule branch:
    - small-number phrasing when prev count < 3;
    - zero-after-sales;
    - unanswered market;
    - unmet opportunity;
    - all skipped because of failures → `na_reason`;
    - scope filtering (a `books` scope never mentions courses);
    - `marketing` scope → three `na_reason`;
    - `brain_primary` follows stalled > opportunity > working;
    - every `files` sentence carries the «ما يشمله الرقم» basis item while the source is the ledger;
    - empty texts are exactly «لا نموّ واضح في هذه الفترة.», «لا تراجع واضح في هذه الفترة.», «لا فرصة واضحة في الأسئلة والطلبات حتى الآن.»;
    - sentences contain Arabic-Indic digits only;
    - no sentence starts with «الذكاء»/«AI»;
    - no «يقوّم».
13. No PII: the serialized response contains none of the fixture emails, names, phones or question texts.
14. Every outbound call goes to `/api/bridge/` paths on the fake platform. The classify POST is never called by these routes.
15. Cache: a second call within 60 s makes zero platform calls; `fresh=1` calls again. The weekly `delivery` is re-read even when the numbers are cached.
16. Weekly: default week = last complete Sun–Sat in Cairo; `nav.next` is null on the latest week; `text` contains the three brain labels and every section label.
17. **Delivery:**
    - settings PUT: without `confirmed:true` → 400; `enabled` not bool → 400; success writes the `Setting`, writes one audit row, makes zero platform calls;
    - send POST: without `confirmed:true` → 400 and zero calls; platform 404 → 404 `na`, zero audit rows; success → exactly one POST to `/api/bridge/reports/weekly/deliver` with `confirmed: True`, `week_start`, the same `text` as the weekly GET, and one audit row;
    - cron: no/wrong secret → 401 and zero calls; switch off → 404 and zero calls; setting off → `{sent:false, reason:'off'}` and zero calls; platform 404 → `{sent:false, na}` and nothing written; success → one POST with `by: 'cron'`; platform 500 → 502;
    - status text for each row of the §6.3 table.

**node (pure helpers in the `v2s:reports` block of `v2-logic.js`, run through `v2_node.logic`):**
- `v2r.trendChip(trend)`: every key → text/tone.
- `v2r.stageView(stage, prevKnownStage)`: change line and conversion phrase, nothing when either side is null.
- `v2r.funnelCompact(stages)`: keeps only stages with numbers, and the «{n} خطوات…» text uses the right counting form for 1, 2, 3 and 11.
- `v2r.chartPoints(rows, w, h)`: scales, a null series is dropped, an all-zero series is drawn flat (not hidden).
- `v2r.legendItems(daily)`: only drawn series; «الزوار» appears only when `visits_available`.
- `v2r.demandFilter(recent, filters, now)`: port of the old filter. It is checked against the old `viewAnalysis` filter behaviour on the same rows (segment, country, category, needs expert, 7/30 days).
- `v2r.demandNumbers(d)`: the one-line numbers. Missing `expert_opinions` → «غير متاح بعد».
- `v2r.deliveryText(delivery)`: every row of the §6.3 table.

**Section map, hooks and hash state:**
- `sectionFor('analysis')` → `('reports','report')`;
- `routeFor('#s/reports/demand')` and `#s/reports/sunday` round-trip;
- `routeFor('#s/reports/report?scope=courses&period=week')` → tab `report`, `q = {scope:'courses', period:'week'}`; unknown keys and non `[a-z]` values are dropped; `sectionHash('reports','report',null,{scope:'courses',period:'week'})` round-trips;
- every existing hash from `test_v2_d1b.py` parses exactly as before (no `q` key);
- the tab list is exactly «التقرير · ما يسأل عنه الناس · تقرير الأحد» (no «كل السجلات»);
- `V2SEC.reports.owns('analysis')` is false when `V2SHELL.on` is false;
- `V2D3.openSheet` and `V2D3.twoStage` are functions (shared edit 5).

**Visible-copy scan:** all Arabic strings in `v2s/reports.js` and `v2_reports_routes.py` contain no «يقوّم», «AI», «API», «null», «جايين», «منين», «بالذكاء», «يصعد». Labels ending in «؟» are allowed.

### 10.1 Deliberate edits to old tests (do not «fix» them by bringing the old tab back)
| File:line | Old assertion | New assertion |
|---|---|---|
| `backend/tests/test_v2_d1b.py:98` | `'reports': [['demand', 'تحليل الطلب', 'analysis']]` | `'reports': [['report', 'التقرير', 'analysis'], ['demand', 'ما يسأل عنه الناس', 'v2r_demand'], ['sunday', 'تقرير الأحد', 'v2r_sunday']]` |
| `backend/tests/test_v2_d1b.py:118` | `landed['analysis'] == ('reports', 'demand')` | `landed['analysis'] == ('reports', 'report')` |
| `backend/tests/test_v2_d1b.py:215` | `'#analysis': ('reports', 'demand')` | `'#analysis': ('reports', 'report')` |
| `backend/tests/test_v2_d1b.py:30` (`PSEUDO_MODS`) | — | add `v2r_demand`, `v2r_sunday` to `PSEUDO_MODS` (they are pseudo-modules like D3's `v2m_*`) |
| `backend/tests/uiharness/v2_shots.py:446` | `('reports', 'demand', 'التقارير')` | `('reports', 'report', 'التقارير')` |
| `backend/tests/test_v2_d1b.py:190` | `assert len(res) == 35` | `assert len(res) == 37` (reports: 3 tabs instead of 1) |
| `backend/tests/test_xss_hardening.py:628` | allowlist | + `v2s/[a-z_]+\.js` (shared edit 3) |

The tab key `report` is fixed in all tests even though its module is `analysis`. STATUS for this round lists this table, as STATUS-D3 did.

**Old suite:** run file by file. With the switch off, `test_dash_*` (including the old analysis tests, if any) stay green. Port-binding tests are re-run outside the sandbox by the main session.

---

## 11) Shots: `backend/tests/uiharness/v2_shots_reports.py` → `docs/v2/final/shots-reports/`
Viewports: desktop 1440×900 (`d`), tablet 820×1180 (`t`), mobile 390×844 (`m`). Every shot is taken at all three. Fixtures:
- `reports_fixtures.seed_dash(app)`: about 90 days of `Revenue` rows across services, with one USD row, one `needs_fx` SAR row, one `ads_deposit` row and one `subscription` row, plus 20 published `Article` rows.
- The fake platform: 600 users spread over 200 days; 60 market member requests; an `ops/queue` with 2 expert-file disputes and 1 case dispute; a full `chat-insights` payload with 40 recent questions, unmet rows and some unclassified; detail for one signed-in and one anonymous question.
- The funnel bridge and the delivery bridge return 404 by default; variant `funnel=True` serves a full N3 payload; variant `delivery=True` serves N6 (`enabled: true`, `last_sent_week`) and accepts the deliver POST.

1. `01` التقرير, all, month, **without the bridge** (compact order: brain → sections → daily → compact funnel → origins line). The first brain line is visible above the fold at 390×844.
2. `02` week · `03` quarter (weekly buckets).
3. `04` «على أي أساس؟» open (all three lists at once).
4. `05` scope «الدورات» · `06` scope «السوق» · `07` scope «التسويق» · `07b` mobile scope select open.
5. `08` sources down (users, market, chat, ops/queue 502). The warn strip and «غير متاح بعد» show, with **no 0**.
6. `09` the route failed entirely (500) → empty state with retry.
7. `10` **with the bridge** (`funnel=True`): concept order, all five stages, channels, countries and top pages, the visitors line in the legend.
8. `11` ما يسأل عنه الناس (desktop «التفصيل» open, tablet/mobile closed; the opportunity card first) · `12` filtered by a country bar · `12b` the «تصفية ▾» sheet on mobile · `13` conversation sheet, signed-in (person link; right panel on desktop) · `14` sheet, anonymous and truncated · `15` the chat source failed · `16a` classify confirmation sheet · `16b` after «صنّف الآن» (fake platform returns `{classified: 12, remaining: 3}`; the POST is asserted and nothing else is written).
9. `17` تقرير الأحد (latest, delivery bridge absent: «غير متاح بعد», both delivery buttons disabled) · `18` the previous week · `19` «انسخ النص» confirmation · `20` `delivery=True`: «يصلك هذا التقرير كل أحد ٨ صباحًا على تليجرام» · `21` «أرسل الآن» review stage · `22` after the send (the one deliver POST asserted, with `confirmed: true`).
10. `23` print emulation (`page.emulate_media(media='print')`) of التقرير and تقرير الأحد (desktop only).
11. `24` the board tile «التقارير» clicked → lands on «التقرير» · `25` the old link `#analysis` → lands on «التقرير» · `26` `#s/reports/report?scope=books&period=week` opened directly, then the back button after clicking a section row restores it.
12. `27` switch off: `#analysis` renders the old `viewAnalysis` exactly. The test asserts that no `.v2r-` element and no `v2s/` request appears.

**The script fails on any of these:**
- visible «0», «null», «NaN» or «undefined» where a number is unavailable;
- a legend item for a series that is not drawn;
- a target < 44px, or a button < 52px on mobile;
- more than one `.v3-btn1` visible per tab;
- horizontal scroll at any viewport;
- a visible Latin digit (dates included);
- any request outside the harness (Google Fonts allowed);
- any platform write other than the single classify POST in shot 16b and the single deliver POST in shot 22;
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
  - `paid_people` / `paid_orders` = payers / payments with `status` paid/partially_refunded **for expert files, courses and books only** (no `ads_deposit`, no subscriptions);
  - `sections.files` = expert files only (no ordinary consultations);
  - test users are excluded everywhere.
- Income is per currency, never converted, net of partial refunds (the same rules as `/bridge/income/by-service`).
- Any metric not tracked yet is `null`.

**N4. Questions per period.**
- `GET /api/bridge/chat-insights?since=ISO&until=ISO` → the same shape as today, restricted to the window, plus `"window_total"`. Without the params, behaviour is unchanged. This also lets the demand tab gain the period filter later.

**N5. Customer satisfaction.**
- `GET /api/bridge/satisfaction?from=&until=` → `{"rating_avg": 4.7|null, "rating_count": 52, "sources": {"courses": {"avg": 4.8, "count": 40}, "expert_files": {"avg": null, "count": 0}}, "complaints_opened": 2}`.
- Ratings come from approved `course_testimonials.rating` and any expert-file review rating that exists. (Open disputes are **not** in this bridge: they stay on `ops/queue`, one number from one source.)

**N6. Sunday delivery (platform side; the dashboard side ships in this round, §8.3–8.5).**
- `POST /api/bridge/reports/weekly/deliver` with body `{week_start, text, by, confirmed: true}`. Without `confirmed: true` → 400. It sends `text` to the founder's existing Telegram chat once per `week_start` (idempotent claim like `marketing_digest_sends`), and returns `{sent: bool, already: bool}`.
- `GET /api/bridge/reports/weekly/delivery` → `{enabled: bool, channel: "telegram", last_sent_week: "YYYY-MM-DD"|null}`.
- Until both exist, the dashboard shows «غير متاح بعد» and its delivery buttons stay disabled; nothing is sent.

## 13) «محتاج منك» (for the founder, in the round's STATUS, plain Arabic)
- «الإرسال كل أحد جاهز في اللوحة، لكنه لن يعمل فعلًا إلا بعد أن تجهّز جلسة المنصة جزء الإرسال (N6). بعدها: اضغط «شغّل الإرسال» في «تقرير الأحد».»
- «الإرسال التلقائي يحتاج موعدًا ثابتًا: نضيف جدولة كل أحد ٨ صباحًا تنادي اللوحة، مثل جدولة المقالات الموجودة. تحتاج موافقتك على إضافتها عند النشر.»
- «أرقام الزيارات ومن أين يأتي الناس تظهر بعد أن تسجّل المنصة الزيارات والمصدر (N1–N3).»

## 14) Decisions (expert review, revision 2)
Applied as given: card order by `sources.funnel` with compact funnel and one-line origins (§4.0, §4.3, §4.5); disputes from `ops/queue` with the tile's exact formula and a parity test (§8.1-5, §10-9); the dashboard side of the Sunday delivery in this round, with setting, cron route, «أرسل الآن» through the confirmation sheet, and the founder note (§6.3, §8.3–8.5, §13); the demand tab reordered around the opportunity, with one visible filter, «تصفية ▾», a one-line numbers row and a collapsible «التفصيل» (§5); no «حدّث» button, one main button, one action button and one «على أي أساس؟» in the brain strip, and a select on mobile (§4.1, §4.2); «دفعوا» counts only the three services (§8.1-1, §10-5); scope and period in the hash (§4.1, shared edit 4); full-day windows with a separate «اليوم حتى الآن» line (§4.4, §8.1); `tzdata` plus a failed-window warning instead of a fixed offset (§8.1); the files caveat in every basis (§7); the new empty texts (§7); the legend shows drawn series only (§4.4); the old-test edits table (§10.1); the classify call behind a confirmation because it is paid (§5).

Changed from the review's wording:
- **Conversation sheet container.** The review named `.v2-sheet` from `v2-shell.css`. That class is the shell's **navigation menu** (`#v2Sheet`, a single element that drops from the top and holds the section tiles, `v2-shell.js:171–181`), so reusing it for a conversation would break the menu. The sheet D3 actually ships is `openSheet` in `v2-d3.js:392` (D3's restyled modal with a `.v3m` body). This spec names that one, exports it (shared edit 5) and forbids a third container. The review's goal (one named container, «أغلق» 52px, Esc, scrim, right panel on desktop) is kept.
- **Files income from `income/by-service`.** That bridge takes only a calendar `month` (`app.py:2525–2535`), not a rolling 30-day window, so it cannot serve the «الشهر» period here. The review's fallback (the caveat in every `basis`) is applied, and N3 now defines `sections.files` as expert files only, which removes the caveat once it ships.
- **Sunday cron route split in two.** The review asked for one route doing the cron and the button. A secret-gated cron route cannot also be the admin's button, so «أرسل الآن» is its own admin route (§8.4) with `confirmed:true` and audit; the cron is §8.5. Both build the same `weekly_text`.
- **Disputes in N5.** Removed `disputes_open` from N5 so the open-disputes number has one source only (`ops/queue`).

Not received: the review text arrived cut off in the middle of its last point (classify). That point was applied as read (a paid call needs a confirmation step). Any point after it was not received.

## 15) Out of scope
- Marketing numbers (spend and leads per campaign); the marketing section owns those.
- The brain's rules screen.
- Any write from this section other than the classify call and the Sunday delivery (setting, «أرسل الآن», cron).
- Adding the Sunday schedule itself to n8n or Coolify (founder approval, §13).
- Any push or deploy.
