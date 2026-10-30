# Final round — «الشركة ورأس المال» (section key `company`)

**Founder order (2026-10-30):** «الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا». This is final work, not a draft.
**Concept:** `dash-canvas/project/Company.dc.html` (one board: a brain strip with three lines, then four cards: «المؤسسون والشركاء» · «المعدات والاشتراكات» · «الاتفاقات والرعاة» · «عملاء الإعلانات: نحسب لهم بالنتيجة»; the gear in the header = «الإعدادات والفريق والصلاحيات»).
**Plan row D6:** partners and contributions, equipment and subscriptions, agreements and sponsors, ad clients billed by results (statement of account). Light local tables.
**Worktree / branch:** `.worktrees/company` / `final-company`. Everything is behind `DASH_V2_ENABLED` (closed by default). Switch off = byte-identical behaviour to today (the old `viewInvestment` / `viewTargets` / `viewSettings` keep rendering).

Reference style: D1-B shell, D2 tickets, D3 money screens (`v2-d3.js` / `v2-d3.css`: paper cards, burgundy primary button, two-stage «راجع ⇒ أكّد» sheet).

---

## 0) Decisions taken in this spec (read first)

1. **Nothing stays in «كل السجلات».** Every piece of the three old screens is either rebuilt here, moved to its real home, or removed for a stated reason (§9). No old-look tab remains in this section.
2. **The three old module keys stay as tab modules** (`investment`, `targets`, `settings`) so every old link, alias and test mapping keeps landing in the right place (`#investment`, `#partners`, `#targets`, `#foundation`, `#settings`). With the shell on, the new renderer takes over these three modules; with it off, the old screens render as today. Four new virtual modules (`v2c_partners`, `v2c_assets`, `v2c_deals`, `v2c_ads`) hold the focused lists.
3. **New local tables** (SQLite, dashboard only, admin only): contributions, subscriptions, agreements, ad clients, ad results. Equipment reuses the existing `assets` table (it already feeds `/api/dashboard` `total_assets`, so one number stays in one place). Partners reuse the existing `partners` table.
4. **Money entries are written once, in the existing ledgers:** a cash contribution also writes one `CashTransaction(kind='capital_in')`; a collected sponsor or ad-client amount writes one `Revenue` row; a paid subscription writes one `Expense` row. The link is stored so delete/undo stays consistent. Every one of these goes through the two-stage confirmation sheet and the server requires `confirmed: true`.
5. **«العقل» lines are computed from facts only** (rows that exist, dates, sums). No target is suggested by the brain; the old AI goals advisor (`/api/ai/goals-advisor`, a paid AI call on every screen open) is not called by the new screens.
6. **Amounts by result are computed in one place: the server.** The client only formats. Currencies are never added together or converted; each currency is its own line.

---

## 1) Tabs (the `company` entry in `SECTIONS`, `v2-logic.js`)

Replace the current entry with exactly:

```js
{ key: 'company', label: 'الشركة ورأس المال', img: 'company', desc: 'الشركاء ورأس المال والمعدات والاتفاقات والإعدادات', tabs: [
  T('invest',   'نظرة',                 'investment'),
  T('partners', 'الشركاء ورأس المال',    'v2c_partners'),
  T('assets',   'المعدات والاشتراكات',   'v2c_assets'),
  T('deals',    'الاتفاقات والرعاة',     'v2c_deals'),
  T('ads',      'عملاء الإعلانات',       'v2c_ads'),
  T('targets',  'الأهداف',               'targets'),
  T('settings', 'الإعدادات',             'settings')
] }
```

- Tab keys `invest`, `targets`, `settings` are kept on purpose (old hashes `#s/company/invest|targets|settings` and the alias landings `partners ⇒ company/invest`, `foundation ⇒ company/targets` stay valid). `targets` keeps an empty `st` (test_v2_d1b line 376).
- No `«كل السجلات»` tab.
- **Foundation alias:** when the renderer is asked for module `targets` while the global `tgTab === 'foundation'` (old `#foundation` link), it calls `host().openSection('company', 'assets')` once (replace), because «التأسيس والأصول» now lives in «المعدات والاشتراكات» and «الشركاء ورأس المال».
- The board tile stays as it is (`T.company.dest = 'investment'`, next line «الشركاء والمعدات والإعدادات»). No count on the tile this round (out of scope §12).

---

## 2) Files (parallel-safe layout)

| File | What |
|---|---|
| `dashboard-cloud/v2s/company.js` (new) | All rendering, sheets and calls for the section. Registers `window.V2SEC.company = {owns, render}`. |
| `dashboard-cloud/v2s/company.css` (new) | All styles, scoped under `.co` (page) and `.com` (inside a sheet). |
| `dashboard-cloud/v2-logic.js` | Only: the `company` entry in `SECTIONS` (§1) + a pure block at the very end `// ===== v2s:company =====` that attaches `V2L.co = {...}` (§7). |
| `dashboard-cloud/index.html` | Only inside `<!-- v2 sections begin -->…<!-- v2 sections end -->` (create it right after `<script src="v2-d2.js"></script>` if missing): `<link rel="stylesheet" href="v2s/company.css">` and `<script src="v2s/company.js"></script>`, one per line. Plus the one shared hook line in `renderView` (see «Shared edits»). |
| `backend/v2_company_routes.py` (new) | Models + routes, `register(app, ns)` (§5). |
| `backend/app.py` | One line before `# ---- v2 section routes end` (create the marker after the last `/api/v2/book-requests/<request_id>` route if missing): `__import__('v2_company_routes').register(app, globals())  # v2s:company` |
| `backend/tests/test_v2s_company.py` (new) | pytest + node + static checks (§10). |
| `backend/tests/uiharness/co_fixtures.py` (new) | Seeds the dashboard SQLite for shots. |
| `backend/tests/uiharness/v2_shots_company.py` (new) | Shots (§11), saves to `docs/v2/final/shots-company/`. |

### Shared edits (minimal, identical text for every section so merges are clean)

1. **`index.html` `renderView`** — one generic line right after the D3 line `if(window.V2_ON&&window.V2D3&&V2D3.owns(current))return V2D3.render(current,v);`:
   ```js
   if(window.V2_ON&&window.V2SEC){for(var _k in V2SEC){var _o=V2SEC[_k];if(_o&&_o.owns&&_o.owns(current)){var _ap=document.querySelector('.app');if(_ap)_ap.classList.add('v2-bare');return _o.render(current,v);}}}
   ```
   Without it no v2s section can render. Any section that already added this exact line satisfies it.
2. **Root `Dockerfile`** — two lines (identical for all sections):
   `COPY backend/v2_*_routes.py /app/` right after `COPY backend/app.py /app/app.py`, and
   `COPY dashboard-cloud/v2s /app/dist/v2s` right after `COPY dashboard-cloud/v2/img /app/dist/v2/img`.
3. **`backend/tests/test_v2_d1b.py` line 100** — the expected `company` tab list becomes:
   `[['invest','نظرة','investment'],['partners','الشركاء ورأس المال','v2c_partners'],['assets','المعدات والاشتراكات','v2c_assets'],['deals','الاتفاقات والرعاة','v2c_deals'],['ads','عملاء الإعلانات','v2c_ads'],['targets','الأهداف','targets'],['settings','الإعدادات','settings']]`.

### `owns` / `render`
- `owns(mod)` = `window.V2_ON && window.V2SHELL && V2SHELL.on && MODS[mod]`, with `MODS = {investment, targets, settings, v2c_partners, v2c_assets, v2c_deals, v2c_ads}`.
- `render(mod, view)` follows `V2D3.render`: draw once, start one 400 ms signature poll (redraw only when a source state changed) and one 60 s minute tick (days-left chips), never redraw while `#epModal` is open.
- Navigation inside the section uses `host().openSection('company', tabKey)` (`window.V2_HOST`). Person links use `host().openPerson(email)` when an email is known.

---

## 3) Data sources (each loads and fails on its own)

Source table in `company.js` (same `SRC/PATHS/load/data/srcState` pattern as `v2-d3.js:37-74`, all through `EP.api`):

| Key | Path (`/api` prefix implied) | Existing? | Used by | Label in failure line |
|---|---|---|---|---|
| `summary` | `GET /v2/company/summary` | new | نظرة, brain lines | «ملخّص الشركة» |
| `partners` | `GET /partners` | yes (`app.py` `list_partners`) | نظرة, الشركاء | «الشركاء» |
| `contribs` | `GET /v2/company/contributions` | new | الشركاء | «دفعات الشركاء» |
| `cash` | `GET /cashflow` | yes | الشركاء («حركات رأس المال») | «حركات رأس المال» |
| `invest` | `GET /investments` | yes | الشركاء (investors) | «سجل الاستثمارات» |
| `opps` | `GET /investment-opportunities` | yes | الشركاء | «فرص الاستثمار» |
| `wd` | `GET /admin/withdrawals` | yes | الشركاء (link only) | — (silent: failure hides the link, as today) |
| `assets` | `GET /assets` | yes | المعدات | «المعدات» |
| `subs` | `GET /v2/company/subscriptions` | new | المعدات | «الاشتراكات» |
| `deals` | `GET /v2/company/agreements` | new | الاتفاقات | «الاتفاقات» |
| `visits` | `GET /v2/company/visits?codes=…&from=…&to=…` | new proxy, platform route missing (Platform needs 1) | الاتفاقات, عملاء الإعلانات | «الزيارات» |
| `ads` | `GET /v2/company/ad-clients` | new | عملاء الإعلانات | «عملاء الإعلانات» |
| `ledger` | `GET /v2/ads-ledger` | yes (D3 proxy) | عملاء الإعلانات (linked clients only) | «أرصدة الإعلانات» |
| `forecast` | `GET /forecast` | yes | الأهداف | «الأهداف الشهرية» |
| `dash` | `GET /dashboard` | yes | الأهداف (actual revenue per month, courses, students) | «الدفتر المالي» |

Existing EP loaders reused as they are (so other screens stay in sync): `EP.ensure('settings'|'dashUsers'|'usage'|'aiModels'|'users'|'courses')`, `EP.reload('audit')`.

**States, everywhere:**
- loading: `<div class="co-empty"><b>…جارٍ جلب {label}</b></div>`
- failed (`error`/`closed`): a warn strip «تعذّر جلب: {labels joined by «، »} — الأرقام الناقصة مكتوب مكانها «غير متاح بعد».» + button «أعد المحاولة» (reloads only failed keys). The number itself shows «غير متاح بعد» with `data-na="1"`. Never `0`.
- empty: per-list text in §4 + its primary add button.
- 401 from any source: do nothing (the auth layer handles it, same as D3).

---

## 4) Screens

Shared layout tokens (company.css): page `.co` max-width 1360px, paper background inherited from shell; cards `.co-card` white, border `#E6DED3`, radius 22px, padding 18px; row `.co-row` min-height 52px, bottom border `#F3EEE7`; chips `.co-st` radius 999px 12px/700 (green `#EEF6F1/#1E6B4A` = done/active, amber `#FCF1E3/#8A4B00` = soon/remaining, red `#FBE9EC/#A3122A` = ended/overdue only, neutral `#F3EEE7/#3D4652`); buttons reuse the D3 look: `.co-btn1` (burgundy `#9E2B4E`, white, min-height 48px, 52px under 700px), `.co-btn2` (white, burgundy text, 44px / 52px mobile), `.co-link` (text link, 44px tall). Fonts Cairo (headings, numbers) and IBM Plex Sans Arabic (body). All targets ≥ 44px; ≥ 52px for buttons under 700px. No horizontal page scroll at 390px: long names wrap, tables turn into stacked cards under 700px.

Breakpoints: **desktop ≥ 1180px**, **tablet 700–1179px** (820 is the reference), **mobile < 700px** (390 is the reference).

### 4.1 «نظرة» (`invest`, module `investment`) — the concept board

**Desktop:**
1. **Brain strip** `.co-brain` (ink `#21262E` background, white text, radius 22px, padding 14px 18px): avatar `v2/img/brain-avatar.jpg` (50px circle, 3px burgundy ring) then up to **3** lines in a 3-column grid; each line ends with one small text button (white underline). Lines come from `V2L.co.brain(summary, now)` (§6). No line ⇒ one sentence «لا شيء يحتاج قرارك في الشركة الآن.» Summary failed ⇒ «ملخّص الشركة غير متاح بعد.» + «أعد المحاولة».
2. **Grid** `grid-template-columns: 1.15fr 1fr 1fr`, two rows, gap 16px:
   - **Card «المؤسسون والشركاء»** (column 1, spans 2 rows). Header link «أضف شريكًا» (opens the partner sheet §5.1).
     - Two stat boxes (background `#FBF6F0`, radius 14px): «رأس المال المتفق عليه» = `summary.partners.agreed_total` (one line per currency, e.g. «٤٠٠٬٠٠٠ جنيه» then «٤٬٥٠٠ دولار») and «دُفع منه» = `summary.partners.paid_total`; if `any_contribution` is false ⇒ «لم تُسجَّل دفعات بعد».
     - Equity bar (14px, radius 10px, `aria-label="توزيع الحصص"`), segment per partner by `equity`, colours in order `#9E2B4E #1F4E79 #2E6B5A #8F5F00 #5A4E8C`, reserve `#D9CFC2`.
     - One row per partner (max 5, then «الكل (n)» ⇒ tab `partners`): avatar (first letter, partner colour) · name + second line «{role label} · {equity}٪» · amount «{paid} من {agreed}» (or «{agreed}» when paid equals agreed) · chip from `V2L.co.partnerChip(row)`: «دفع كاملًا» (green) · «باقٍ {x}» (amber) · «لم تُسجَّل دفعات» (neutral).
     - Reserve row (role `pool` or name «غير موزّع» / «Unallocated / Option Pool»): avatar shows «{equity}٪», text = the partner's `notes` if set, otherwise «حصص غير موزّعة»; no amount, no chip.
     - Footer «آخر الحركات»: last 3 of `summary.capital_moves` as «{description}» ⟷ «{date} · {amount}». Empty ⇒ «لا حركات مسجّلة».
   - **Card «المعدات والاشتراكات»** (col 2, row 1). Header link «أضف» ⇒ opens a two-choice sheet «معدة أو أصل» / «اشتراك». Rows (max 4): first subscriptions renewing within 14 days (from `summary.subscriptions.next`) then equipment by value (from `assets`): name · amount («٢٦٬٠٠٠ جنيه» for equipment; «٣٬٤٠٠ جنيه شهريًا» for a monthly subscription) · chip (equipment: status label; subscription: `V2L.co.renewChip`). Footer line: «قيمة المعدات {value_egp} جنيه · اشتراكات {monthly per currency} شهريًا». Link «الكل» ⇒ tab `assets`.
   - **Card «الاتفاقات والرعاة»** (col 3, row 1). Header link «أضف اتفاقًا». Rows (max 4, active only, soonest `ends_on` first, then undated): «{kind label}: {party}» + second line `summary` · amount if any · chip from `V2L.co.agreementChip(row, now)`: «ينتهي بعد {n} يومًا» (amber ≤ 30 days; red ≤ 7), «ينتهي اليوم» (red), «ساري» (green), «انتهى» (neutral, only in the deals tab). Link «الكل» ⇒ tab `deals`.
   - **Card «عملاء الإعلانات: نحسب لهم بالنتيجة»** (cols 2–3, row 2). Header link «أضف عميلًا». A 2-column grid of mini cards (background `#FBF6F0`, radius 16px), one per active client (max 4, then «الكل» ⇒ tab `ads`), each showing its latest period: name (bold) · `offer` + «·» + deal text from `V2L.co.dealText(client)` · «{count_label}» ⟷ count · «دخلهم منها» ⟷ income · (fixed deals) «المبلغ الثابت» ⟷ fixed · «مستحق لنا» ⟷ `due` (burgundy). A missing value prints «غير متاح بعد». Under the grid, when `summary.ad_clients.unsent > 0`: primary button «جهّز كشوف الحساب ({n})» (opens the statement sheet §5.7 for all unsent results).
3. **First-run empty state** (no partners, no assets, no subscriptions, no agreements and no ad clients, all sources ready): one `.co-hero` card with the photo `v2/img/company.jpg` (cover, radius 22px, max-height 260px), title «سجّل الشركة هنا مرة واحدة», line «الشركاء وما دفعه كل واحد، والمعدات والاشتراكات، والاتفاقات وعملاء الإعلانات — في مكان واحد يراه العقل.», button «ابدأ بالشركاء» (⇒ partner sheet).

**Tablet (700–1179):** brain lines stacked (one per row); grid 2 columns: partners card full width, then equipment | agreements, then ad clients full width (its inner grid 2 columns).
**Mobile (< 700):** everything single column in this order: brain strip, partners, agreements, equipment, ad clients. Partner rows: name line, then «amount · chip» on a second line. Ad client mini cards one per row. Header links become full-width `.co-btn2` at the bottom of each card (52px).

### 4.2 «الشركاء ورأس المال» (`partners`, module `v2c_partners`)

Top bar: title is the tab; right side buttons «سجّل دفعة» (primary) and «أضف شريكًا» (secondary).

Sections, in order:
1. **Summary row** (3 stat boxes, wrap on mobile): «رأس المال المتفق عليه», «دُفع منه», «الباقي» (= agreed − paid per currency, only for currencies with any recorded payment; otherwise «غير متاح بعد» with the hint «سجّل دفعات الشركاء لتعرف الباقي»). Source: `summary.partners`. Then the equity bar with a legend (name + percent) under it. If `equity_total` differs from 100 by more than 0.05: amber line «مجموع الحصص المسجّلة {x}٪.»
2. **«الشركاء»** list (desktop table columns: «الشريك» · «الحصة» · «المتفق عليه» · «دُفع» · «الحالة» · actions; mobile stacked cards). Source: `partners` (raw fields `name, role, equity_percent, capital_egp, capital_usd, notes`) joined with `summary.partners.rows` (paid per currency, contributions count, `last_paid_at`). Role label map: `founder` «مؤسس», `cofounder` «شريك مؤسس», `investor` «مستثمر», `partner` «شريك», `pool` «حصص غير موزّعة»; any other stored text is shown as is. Row actions: «سجّل دفعة» (`.co-btn2`, preselects the partner) and «عدّل» (`.co-link`). Empty: «لا شركاء مسجّلون بعد.» + «أضف شريكًا».
3. **«دفعات الشركاء»** (newest first; filter chips «الكل» + one per partner). Source `contribs`. Row: date · partner · kind label («نقدًا» / «معدات أو أصول» / «أخرى: {kind_other}») · amount · badge «في حركة الكاش» when `cash_tx_id` is set · `note` · action «احذف» (review sheet, §5.2). Empty: «لا دفعات مسجّلة.»
4. **«حركات رأس المال»**: last 10 of `cash.transactions` (date · `description` or `source` · signed amount with currency; `capital_in`/`adjustment_in` shown as «داخل», others «خارج»). Read only. Empty: «لا حركات مسجّلة.»
5. **«المستثمرون»** — only when `invest` returns rows: grouped by `investor_name` (same grouping as `EP.loaders.investment`): name · «استثمر {invested_total_egp sum} جنيه» · «مستحق له {due_egp sum} جنيه». Read only, line under the title «من سجل الاستثمارات». If `wd` returns pending rows: link «طلبات سحب المستثمرين ({n}) — في «الفلوس»» which runs the old path exactly: `go('finance'); finTab='investorwd'; viewFinance(document.getElementById('view'))` inside try/catch, falling back to `host().openSection('money','all')`.
6. **«فرص الاستثمار ({n})»** — collapsed `<details>` (closed by default). Rows: course title · «{raised} من {target} جنيه» · «العائد المتوقع {roi}٪» · «عدّل» / «احذف». Button «أضف فرصة». Calls the existing `EP.createOpportunity(body, after)`, `EP.updateOpportunity(id, body, after)`, `EP.deleteOpportunity(id, after)` with the same body as today (`course_id`, `target_amount`, `current_funded`, `expected_roi`); the course list comes from `EP.ensure('courses')`. Empty: «لا فرص مطروحة.»

### 4.3 «المعدات والاشتراكات» (`assets`, module `v2c_assets`)

Two sections side by side on desktop (1fr 1fr), stacked on tablet/mobile.

1. **«المعدات والأصول»** — source `assets` (`GET /api/assets`). Summary line: «{count} بندًا · القيمة {sum value_egp} جنيه · إيجار شهري للشركة {sum monthly_rent_egp} جنيه». Rows: name · category label · «ملك: {owner}» · value · «إيجار {monthly_rent_egp} شهريًا» (only if > 0) · status chip · «عدّل». Button «أضف معدة». Empty: «لا معدات مسجّلة بعد.»
   - Category labels: `computers` «أجهزة كمبيوتر», `phones` «هواتف», `camera` «كاميرات», `lenses` «عدسات», `microphone` «صوت», `lighting` «إضاءة», `tripod` «حوامل», `teleprompter` «جهاز قراءة النص», `hardware` «ملحقات», `equipment` «معدات», `other` «أخرى»; unknown stored value shown as is.
   - Status labels: `leased_to_company` «مؤجَّر للشركة», `owned_by_company` «ملك الشركة», `in_studio` «في الاستوديو», `with_person` «مع أحد الفريق», `out_of_service` «خارج الخدمة», `other` «أخرى».
2. **«الاشتراكات»** — source `subs`. Summary: «شهريًا: {sum per currency}» and «سنويًا: {sum per currency}» (never mixed, never converted). Rows sorted: overdue, then soonest `renews_on`, then stopped at the bottom (muted): name · «{amount} {cycle label}» («شهريًا» / «سنويًا» / «{cycle_other}») · renew chip `V2L.co.renewChip(row, now)`: «فات موعد التجديد منذ {n} يوم» (red), «يتجدد بعد {n} أيام» (amber ≤ 7), «يتجدد {date}» (neutral), «متوقف» (neutral) · «يدفعه: {paid_by}» if set. Actions: «سجّل الدفع» (primary on overdue/≤ 7 days, else `.co-btn2`; review sheet §5.4), «عدّل», «أوقفه» / «أعد تشغيله». Button «أضف اشتراكًا». Empty: «لا اشتراكات مسجّلة بعد.»

Brain line at the top of the tab (only when true): from `V2L.co.brain` restricted to the subscription line.

### 4.4 «الاتفاقات والرعاة» (`deals`, module `v2c_deals`)

Groups (each a card with a title and count): «تنتهي خلال ٣٠ يومًا» · «سارية» · «مسودات» · «انتهت» (a closed `<details>`). Source `deals`, visits from `visits` (codes = all `ref_code` of active agreements, range = `starts_on`..today).

Row: «{kind label}: {party}» · `summary` · `terms` · amount if set · «من {starts_on} إلى {ends_on}» (or «بلا تاريخ انتهاء») · chip (§4.1) · «استلمنا {received per currency}» (from the agreement's `received`; hidden when empty) · «الزيارات: {n}» when `ref_code` is set (from `visits`; source missing ⇒ «الزيارات: غير متاح بعد»).
Actions: «سجّل مبلغًا مستلمًا» (review sheet §5.6), «جدّد» (sheet §5.5), «عدّل», «أنهِ الاتفاق» (sets status `ended` after a one-line confirm sheet), «احذف» (only drafts or agreements with no received amount; review sheet).
Kind labels: `sponsor` «راعٍ», `content` «اتفاق محتوى», `book` «اتفاق كتاب», `company_paper` «أوراق الشركة» (registration, tax card… with a renewal date), `other` «أخرى» (+ the stored `kind_other`).
Button «أضف اتفاقًا». Empty: «لا اتفاقات مسجّلة بعد.»

### 4.5 «عملاء الإعلانات» (`ads`, module `v2c_ads`)

Top: one line «نحسب لكل عميل بالنتيجة: نسبة من دخل الحملة أو مبلغ ثابت أو الاثنان.» + button «أضف عميلًا»; when unsent results exist, primary «جهّز كشوف الحساب ({n})».

One card per client (active first, ended in a closed `<details>` «عملاء انتهى الاتفاق معهم»). Source `ads` (each client carries its results with server-computed `due`).
- Header: name · `offer` · deal text (`V2L.co.dealText`): «نأخذ {p}٪ من دخل الحملة» · «مبلغ ثابت {f} + {p}٪ من دخل الحملة» · «مبلغ ثابت {f}» · «أخرى: {deal_other}».
- If linked to a work in the ad balance ledger (`ledger_kind` + `ledger_owner_id` set): line «رصيد إعلاناته عندنا: {balance per currency}» from the `ledger` row with the same `(owner_kind, owner_id)`; missing ⇒ «غير متاح بعد».
- **Results table** (latest 6 periods; «الأقدم» expands): «الشهر» · `count_label` · «دخلهم منها» · «مستحق لنا» · «الحالة» · actions. Status: «حُصّل {date}» (green) when `revenue_id`; «أُرسل الكشف {date}» (amber) when `sent_at`; «لم يُرسل الكشف» (neutral). Actions per row: «كشف الحساب» (§5.7), «سجّل التحصيل» (§5.6, hidden once collected or when `due` is null), «عدّل» (hidden once collected), «احذف» (hidden once collected; review sheet).
- Card buttons: «سجّل نتيجة شهر» (primary), «عدّل الاتفاق».
- Empty client list: «لا عملاء إعلانات بعد.» Empty results: «لم تُسجَّل نتائج بعد.»
- `income` empty for a percent deal ⇒ due «غير متاح بعد» (server returns `due: null`), never «٠».

### 4.6 «الأهداف» (`targets`, module `targets`)

Sources: `forecast` (founder-set monthly targets, with `id`) and `dash` (`monthly[]` actual revenue/expenses per month, `courses.total_courses`, `courses.total_students`, `financial.break_even_month`).
1. Brain line (top): `V2L.co.monthLine(forecast, dash, now)`: «دخل {الشهر} حتى الآن {X} جنيه من هدف {Y} ({pct}٪).» · no target ⇒ «لم يُحدَّد هدف دخل لهذا الشهر.» + button «حدّد الهدف» · `dash` failed ⇒ «دخل هذا الشهر غير متاح بعد.»
2. **«الدخل مقابل الهدف»** bar chart (last 6 months that have a target or a revenue row): two bars per month, actual (green `#2E6B5A`) and target (burgundy outline). Values labelled under bars in Arabic digits («بالألف جنيه» in the legend). A month with a target but no revenue row shows «لا دخل مسجّل» instead of a zero bar. Mobile: horizontal scroll inside the chart box only (not the page), or 3 months per view.
3. **«المؤشرات»** (facts only, rows): «طلاب الدورات» `total_students` / next target `target_students` · «الدورات المنشورة» `total_courses` / `target_courses` · «أول شهر يغطي فيه الدخل المصروف المتوقع» `break_even_month` (or «لم يُحدَّد»). Each row: current, target, chip «تحقّق» (green) or «باقٍ {n}» (amber). No «متأخّر» judgement.
4. **«الأهداف الشهرية»** table: month · «هدف الدخل» · «المصروف المتوقع» (sum of cogs/marketing/payroll/rent/other) · «دورات» · «طلاب» · «عدّل». Button «أضف شهرًا». Empty: «لا أهداف شهرية بعد.» + «أضف شهرًا».
   - «عدّل» ⇒ forecast sheet ⇒ existing `PUT /api/forecast/<id>`.
   - «أضف شهرًا» ⇒ new `POST /api/v2/company/forecast` (no POST exists today).

### 4.7 «الإعدادات» (`settings`, module `settings`)

Desktop two columns, tablet/mobile one column. All sources are the existing EP loaders.
1. **«بيانات الشركة»** (`EP.data.settings`): fields «الاسم» (`company_name`), «بداية السنة المالية» (`fiscal_year_start`), «يوم التقرير الشهري» (`monthly_report_day`); read-only line «عنوان اللوحة: {company_domain or dashboard.elprofessor.net}». Button «احفظ بيانات الشركة» ⇒ `EP.saveSettings({company_name, fiscal_year_start, monthly_report_day}, after)`.
2. **«العملة»**: «سعر الدولار بالجنيه» (`exchange_rate`) + «غيّر» ⇒ review sheet (before ⇒ after, line «يغيّر هذا تحويل الدولار إلى الجنيه في التقارير.») ⇒ `EP.saveSettings({exchange_rate})`. When `exchange_rate` is missing: «غير متاح بعد» and the input disabled (as today). Countries line: «البلاد المفعّلة: مصر · السعودية · قطر · الإمارات · باقي البلاد» (plain chips, no flags emoji).
3. **«فريق الإدارة»** (`EP.data.dashUsers`): rows name · email · role («مدير» / «موظف متابعة» / «بانتظار التفعيل») · chip «مفعّل»/«موقوف» · «عدّل» · «أوقف»/«فعّل» (last active admin: «آخر مدير — محميّ», no button). Button «أضف مديرًا أو موظفًا». Sheet fields as today (name, email, role, temporary password ≥ 8). Calls `EP.createDashUser`, `EP.updateDashUser`. Stop/activate goes through a one-line confirm sheet (replaces the native `confirm()`).
4. **«صلاحيات الموظف»**: four checkboxes (48px rows) «المستخدمون» (`users`), «الدورات» (`courses`), «المحتوى» (`topics`), «دليل الاستخدام» (`tutorials`) from `role_permissions` (same parsing as `rolePermsMap`, missing entry = all checked). «احفظ الصلاحيات» ⇒ `EP.saveSettings({role_permissions: JSON.stringify(map)})` then `renderNav()` if defined.
5. **«خدمة الذكاء»** (`EP.data.aiModels`): one row per provider: `label` · «جاهزة» (green) / «غير جاهزة» (neutral). No model ids, no key names. Note «تُضبط من الخادم.»
6. **«الاستخدام في آخر ٧ أيام»** (`EP.data.usage`): «طلبات للعقل» `ai_calls` (+ «تعذّر منها {ai_errors}»), «مرات الدخول» `logins_7d`, «عمليات» `actions_7d`. Missing ⇒ «غير متاح بعد».
7. **«سجل العمليات»** inline (replaces the modal): `EP.reload('audit')` on open; first 20 rows, then «المزيد» shows up to 120. Row: label (global `AUDIT_LABEL[action]` if defined, else the company labels below, else «عملية») · detail (global `auditEfDetail(r)` if defined) · time (`auditWhen` if defined, else `V2L.util.dateText`) · actor email (LTR, small). Empty: «لا عمليات مسجّلة بعد.»
   Company labels: `company.contribution.add` «تسجيل دفعة شريك» · `company.contribution.delete` «حذف دفعة شريك» · `company.subscription.add|update|delete` «إضافة/تعديل/حذف اشتراك» · `company.subscription.paid` «تسجيل دفع اشتراك» · `company.agreement.add|update|delete|renew|end` «إضافة/تعديل/حذف/تجديد/إنهاء اتفاق» · `company.adclient.add|update|delete` «إضافة/تعديل/حذف عميل إعلانات» · `company.adresult.add|update|delete|sent` «إضافة/تعديل/حذف نتيجة شهر / إرسال كشف حساب» · `company.income.add` «تسجيل مبلغ مستلم» · `company.forecast.add` «إضافة هدف شهر».

---

## 5) Sheets (all through the existing `window.openModal` / `closeModal`, content wrapped in `.com`)

Common: inputs ≥ 48px, `inputmode="decimal"` for amounts, currency `<select>` next to the amount, dates `type="date"`, error box `.co-err` inside the sheet showing the server message as is, buttons «احفظ» / «إلغاء». While sending: button text «جارٍ الحفظ…», disabled, sheet not closable. A lost reply (500/502/503/504) shows «لم يصلنا رد — تأكّد من القائمة قبل المحاولة مرة أخرى.» and reloads the list.

**Two-stage money sheet** (same shape as `twoStage` in `v2-d3.js:406`): stage 1 form ⇒ «راجع» ⇒ stage 2 shows a table «البند | الآن | بعد» (or for a new entry a list «سيُسجَّل:») + «أكّد» (primary) + «رجوع». «أكّد» sends `confirmed: true` and `op_id` (random 16+ char id made once per sheet). Used by: §5.2, §5.4, §5.6, rate change, partner equity/capital change, and every delete of a money record.

1. **Partner (add/edit)** «أضف شريكًا» / «تعديل شريك»: on add, «اختر من المستخدمين المسجّلين» (searchable select from `window.USERS` after `EP.ensure('users')`; the existing rule «التسجيل من المنصة فقط» stays); on edit, «الاسم» text. «الصفة» select (مؤسس · شريك مؤسس · مستثمر · شريك · حصص غير موزّعة · أخرى + text), «الحصة ٪» (0–100), «رأس المال المتفق عليه بالجنيه», «… بالدولار», «ملاحظة». Review stage when equity or capital changes. Calls `EP.createPartner({name, role, equity_percent, capital_egp, capital_usd, notes}, after)` / `EP.updatePartner(id, body, after)`. «احذف الشريك» (edit only, not when contributions > 0: text «للشريك دفعات مسجّلة — احذف دفعاته أولًا.») ⇒ review ⇒ `EP.deletePartner(id, after)`.
2. **Contribution** «سجّل دفعة»: «الشريك» (select), «نوع الدفعة» (نقدًا · معدات أو أصول · أخرى + text), «المبلغ», «العملة» (جنيه · دولار), «التاريخ» (default today), «ملاحظة», checkbox «أدخلها في حركة الكاش كرأس مال داخل» (visible and checked only for «نقدًا»). Review: «سيُسجَّل: دفعة {amount} من {partner} بتاريخ {date}{، وتدخل حركة الكاش}». ⇒ `POST /api/v2/company/contributions`. Delete review: «ستُحذف دفعة {amount} من {partner}{ وحركة الكاش المرتبطة بها}.» ⇒ `DELETE /api/v2/company/contributions/<id>` body `{confirmed:true}`.
3. **Equipment** «أضف معدة» / «تعديل معدة»: «الاسم», «النوع» (category labels + أخرى), «المالك» (default «الشركة»), «القيمة بالجنيه», «إيجار شهري للشركة بالجنيه» (optional), «الحالة» (status labels + أخرى), «ملاحظة». ⇒ existing `POST /api/assets`, `PUT /api/assets/<id>`; delete ⇒ confirm sheet ⇒ `DELETE /api/assets/<id>`.
4. **Subscription** «أضف اشتراكًا» / «تعديل اشتراك»: «الاسم», «المبلغ», «العملة» (جنيه · دولار), «كل» (شهر · سنة · أخرى + text), «موعد التجديد القادم», «يدفعه», «ملاحظة». ⇒ `POST/PUT /api/v2/company/subscriptions[/<id>]`. **«سجّل الدفع»** review: «سيُسجَّل مصروف {amount} لـ«{name}» بتاريخ {date}، وموعد التجديد يصبح {next}.» ⇒ `POST /api/v2/company/subscriptions/<id>/paid`. «أوقفه»/«أعد تشغيله» ⇒ `PUT` `{status}`.
5. **Agreement** «أضف اتفاقًا» / «تعديل اتفاق» / «تجديد اتفاق»: «النوع» (راعٍ · اتفاق محتوى · اتفاق كتاب · أوراق الشركة · أخرى + text), «الطرف الآخر», «ماذا نقدّم» (`summary`), «المقابل أو القسمة» (`terms`, e.g. «نصف الدخل لكل طرف»), «المبلغ» + «العملة» (optional), «يبدأ», «ينتهي» (optional), «الحالة» (ساري · مسودة), «الكود لعدّ الزيارات» (optional, lowercase letters, digits, dash), «ملاحظة». Renew prefill: starts = old end + 1 day, end = start + old duration, same amount ⇒ `POST /api/v2/company/agreements/<id>/renew`.
6. **Money received** «سجّل مبلغًا مستلمًا» (agreement) / «سجّل التحصيل» (ad result): «المبلغ» (prefilled with `due` for an ad result, not editable then), «العملة» (agreement: its currency; ad result: the client's), «التاريخ», «طريقة الاستلام» (تحويل بنكي · نقدًا · أخرى). Review: «سيُسجَّل دخل {amount} من {party} بتاريخ {date}.» ⇒ `POST /api/v2/company/income`.
7. **Statement of account** «كشف الحساب» (one result) / «كشوف الحساب» (all unsent): one block per result with the exact text below in a `<pre class="co-stmt">` + buttons «انسخ» (clipboard; on failure select the text), «اطبع» (adds `body.co-printing` and calls `window.print()`; print CSS shows only `#coPrint`), «علّمه مُرسلًا» ⇒ `POST /api/v2/company/ad-results/<id>/sent`. The concept's «أرسل كشف الحساب للعميلين» becomes «جهّز كشوف الحساب» because the dashboard does not send email; sending stays with the founder, and the dashboard records that it was sent.
   ```
   كشف حساب — {client.name}
   الفترة: {period as «أكتوبر ٢٠٢٦»}
   {count_label}: {count or «غير مسجّل»}
   دخلكم من الحملة: {income} {currency name}   (line omitted for fixed-only deals)
   الاتفاق: {deal text}
   المستحق للبروفيسور: {due} {currency name}
   رقم الكشف: CO-{client.id}-{period}
   ```
8. **Ad client** «أضف عميلًا» / «عدّل الاتفاق»: «الاسم», «البريد» (optional), «ماذا نقدّم لهم» (`offer`), «طريقة الحساب» (نسبة من دخل الحملة · مبلغ ثابت + نسبة · مبلغ ثابت · أخرى + text), «النسبة ٪», «المبلغ الثابت», «العملة» (any of the allowlist), «اسم العدد في الكشف» (default «عملاء جاؤوا من الحملة»), «الكود لعدّ الزيارات» (optional), «مرتبط برصيد إعلانات عمل على المنصة» (optional: kind دورة/كتاب + work picked from the `ledger` rows by title), «الحالة» (نشط · انتهى). ⇒ `POST/PUT /api/v2/company/ad-clients[/<id>]`.
9. **Ad result** «سجّل نتيجة شهر» / «تعديل نتيجة»: «الشهر» (`type="month"`), `count_label` (integer ≥ 0, optional), «دخلهم من الحملة» (optional; required for percent deals to compute what is due), «المستحق» (only for deal «أخرى»), «ملاحظة». ⇒ `POST /api/v2/company/ad-clients/<id>/results`, `PUT /api/v2/company/ad-results/<rid>`; delete ⇒ review ⇒ `DELETE /api/v2/company/ad-results/<rid>`.
10. **Forecast month** «أضف شهرًا» / «تعديل هدف شهر»: «الشهر», «هدف الدخل بالجنيه», «تكلفة التنفيذ», «التسويق», «الرواتب», «الإيجار», «مصروفات أخرى», «عدد الدورات المستهدف», «عدد الطلاب المستهدف», «ملاحظة». Add ⇒ `POST /api/v2/company/forecast`; edit ⇒ existing `PUT /api/forecast/<id>` (fields `revenue_egp, cogs_egp, marketing_egp, payroll_egp, rent_egp, other_sga_egp, target_courses, target_students, notes`).

After every successful write: a green note `.co-ok` for 12 s («حُفظ.» / «سُجّلت الدفعة.» / «سُجّل الدخل.» …), reload only the affected sources + `summary`.

---

## 6) The brain lines (`V2L.co.brain(summary, now)` ⇒ `[{key, text, act:{tab, id?, do?}}]`, max 3)

Order of priority; a line appears only when its facts exist; a failed block (`null`) gives no line (and never «٠»):

| # | Condition (facts) | Exact text | Button ⇒ action |
|---|---|---|---|
| 1 | `money` present and `expenses > 0` | revenue ≥ expenses: «مصروف {month} كان {expenses} جنيه، والدخل غطّاه{ منذ {covered_since}}.» (the «منذ» part only when `covered_since` is earlier than `month`) · revenue < expenses: «مصروف {month} كان {expenses} جنيه، والدخل غطّى {floor(revenue/expenses·100)}٪ منه.» | «افتح الفلوس» ⇒ `openSection('money','overview')` |
| 2 | an active agreement with `ends_on` within 30 days (soonest) | «اتفاق «{party}» ينتهي بعد {n يوم}{، وجلب {visits} زيارة}.» / «… ينتهي اليوم.» (visits part only when the visits source returned a number for its code) | «افتح الاتفاق» ⇒ tab `deals`, row highlighted |
| 2b | else an active subscription with `renews_on` within 7 days or overdue | «اشتراك «{name}» يتجدد بعد {n يوم} بمبلغ {amount}.» / «فات موعد تجديد «{name}» منذ {n يوم}.» | «سجّل الدفع» ⇒ §5.4 paid sheet |
| 3 | partners with ≥ 1 contribution and paid < agreed in a currency | one: «شريك واحد باقٍ عليه {x} من حصته.» · n: «{n} شركاء باقٍ عليهم {sum} من حصصهم.» | «سجّل دفعة» ⇒ §5.2 |
| 3b | else partners exist and `any_contribution` is false | «لم تُسجَّل دفعات الشركاء بعد، فالمدفوع من رأس المال غير معروف.» | «سجّل دفعة» |
| 4 | `ad_clients.unsent > 0` | «{n كشف} حساب جاهزة للإرسال، والمستحق لنا {due_open}.» | «جهّز الكشوف» ⇒ §5.7 |
| 5 | partners exist and abs(equity_total − 100) > 0.05 | «مجموع الحصص المسجّلة {x}٪.» | «راجع الحصص» ⇒ tab `partners` |

Numbers use `V2L.util.fmt` / `moneyText` (Arabic digits, «جنيه»/«دولار»…), day counts use `V2L.util.U` plural forms (يوم واحد · يومين · أيام · يومًا). Months «أكتوبر ٢٠٢٦». The «money» numbers are the dashboard ledger's monthly rows (`monthly_financial_rows`, EGP after the dashboard's own exchange rate, the same numbers the old reports print).

---

## 7) Pure helpers (end of `v2-logic.js`, block `// ===== v2s:company =====`)

Appended after the main IIFE as `(function (root) { var L = root.V2L; if (!L) return; L.co = {...}; })(typeof window !== 'undefined' ? window : globalThis);` so `require()` in node sees `module.exports.co`:
- `brain(summary, now)` — §6.
- `partnerChip(row)` ⇒ `{text, tone}` from `agreed[]`, `paid[]`, `contributions`.
- `remaining(agreed, paid)` ⇒ per-currency list (only currencies with any payment); never negative (overpaid ⇒ «دفع كاملًا»).
- `agreementChip(row, now)`, `renewChip(row, now)` ⇒ `{text, tone, days}` (days by local calendar date, not 24 h windows).
- `dealText(client)`, `statementText(client, result)` (§5.7 exact template).
- `monthLine(forecast, dash, now)`, `forecastBars(forecast, dash, now)` (⇒ months with `actual: null` when no revenue row).
- `sumLines(list)` ⇒ «٤٠٠٬٠٠٠ جنيه · ٤٬٥٠٠ دولار» (never adds two currencies).
- `naText` = «غير متاح بعد».

---

## 8) Server: `backend/v2_company_routes.py`

`register(app, ns)` takes `ns = globals()` of `app.py` and uses from it: `db`, `token_required`, `roles_required`, `_audit`, `_v2_closed`, `_v2_ns`, `_v2_body`, `_v2_confirmed`, `Partner`, `CashTransaction`, `Revenue`, `Expense`, `Asset`, `ForecastMonth`, `monthly_financial_rows`, `get_rate`, `Payout`, `serialize_date`. Models are built once inside `register` (module-level cache `M`) so `db.create_all()` at the bottom of `app.py` creates them; nothing is altered on existing tables.

**Every route:** `@token_required @roles_required('admin')`, then `_v2_closed()` (switch off ⇒ 404 `{"error":"غير متاح"}`), `Cache-Control: no-store` on every reply, JSON errors in plain Arabic, list replies capped at 500 rows, audit row on success only (actor from the token). Writes never take `by` from the body.

### Models (new tables)

| Table | Columns |
|---|---|
| `co_contributions` | `id` PK · `partner_id` int not null · `kind` str(20) `cash|asset|other` · `kind_other` str(60) null · `date` date · `amount` float · `currency` str(3) `EGP|USD` · `note` str(300) · `cash_tx_id` int null · `created_at` · `created_by` str(255) |
| `co_subscriptions` | `id` · `name` str(120) · `amount` float · `currency` `EGP|USD` · `cycle` `monthly|yearly|other` · `cycle_other` str(60) null · `renews_on` date null · `status` `active|stopped` · `paid_by` str(120) null · `note` str(300) · `created_at` · `updated_at` · `created_by` |
| `co_agreements` | `id` · `kind` `sponsor|content|book|company_paper|other` · `kind_other` str(60) null · `party` str(160) · `summary` str(300) · `terms` str(300) · `amount` float null · `currency` str(3) null · `starts_on` date null · `ends_on` date null · `status` `active|draft|ended` · `ref_code` str(40) null · `renewed_from` int null · `note` str(500) · `created_at` · `updated_at` · `created_by` |
| `co_ad_clients` | `id` · `name` str(160) · `email` str(200) null · `offer` str(300) · `deal` `percent|fixed_plus_percent|fixed|other` · `deal_other` str(120) null · `percent` float null · `fixed_amount` float null · `currency` str(3) · `count_label` str(60) default «عملاء جاؤوا من الحملة» · `ref_code` str(40) null · `ledger_kind` `course|book` null · `ledger_owner_id` str(200) null · `status` `active|ended` · `note` str(500) · `created_at` · `updated_at` · `created_by` |
| `co_ad_results` | `id` · `client_id` int · `period` str(7) `YYYY-MM` · `count` int null · `income` float null · `due_manual` float null · `source` `manual|platform` · `note` str(300) · `sent_at` datetime null · `sent_by` str(255) null · `revenue_id` int null · `created_at` · `updated_at` · `created_by` · unique(`client_id`,`period`) |

**Validation (422 + Arabic message):** amounts `0 < x ≤ 100,000,000` (forecast and counts `≥ 0`); currency `EGP|USD` for contributions and subscriptions («العملة لازم جنيه أو دولار»), and `EGP|USD|SAR|AED|KWD|QAR|EUR|GBP` elsewhere; percent `0 < p ≤ 100`; dates ISO `YYYY-MM-DD`, `ends_on ≥ starts_on`; `period` and forecast `month` `YYYY-MM`; enums as listed (unknown ⇒ «النوع غير معروف»); `kind=other` requires `kind_other` (1–60 chars); `ref_code` `^[a-z0-9-]{3,40}$` and unique among active agreements and clients; text lengths as the columns; `deal=percent` needs `percent`; `fixed` needs `fixed_amount`; `fixed_plus_percent` needs both; `other` needs `deal_other`; `op_id` `^[A-Za-z0-9_-]{8,64}$`.

**Due (one place, the server):** `percent`: `round2(income × p / 100)` or `null` if `income` is null · `fixed_plus_percent`: `fixed + round2(income × p / 100)`, `null` if `income` is null · `fixed`: `fixed` · `other`: `due_manual` or `null`. Rounding half up to cents. Currency = the client's. Example checks: 10% of 48,000 = 4,800; 6,000 + 5% of 31,000 = 7,550.

### Routes

| Method & path | Body / query | Reply |
|---|---|---|
| `GET /api/v2/company/summary` | — | `{generated_at, partners, capital_moves, assets, subscriptions, agreements, ad_clients, money}` — each block computed in its own try/except; a failed block is `null` (logged). Shapes: `partners = {rows:[{id,name,role,equity,reserve,agreed:[{currency,amount}],paid:[…],contributions,last_paid_at}], equity_total, agreed_total:[…], paid_total:[…], any_contribution}` (reserve = role `pool` or name «غير موزّع»/«Unallocated / Option Pool»; agreed from `capital_egp`/`capital_usd` > 0) · `capital_moves = [{date,kind,description,amount,currency}]` (last 5 `CashTransaction`, `amount_egp` > 0 ⇒ EGP else USD) · `assets = {count, value_egp, rent_egp_monthly}` · `subscriptions = {active, monthly:[…], yearly:[…], next:[{id,name,renews_on,amount,currency,cycle}]}` (≤ 3, active with a date, soonest first, overdue included) · `agreements = {active, ending:[{id,kind,party,ends_on,amount,currency,ref_code}]}` (active, `ends_on` within 45 days) · `ad_clients = {active, unsent, due_open:[…], latest:[{client_id,name,period,count,income,due:[…]}]}` · `money = {month, revenue, expenses, covered_since}` (`month` = the last complete calendar month present in `monthly_financial_rows`; `covered_since` = first month of the trailing run of months with revenue ≥ expenses ending at `month`, `null` if `month` itself is not covered). This is also the brain's read of the company (D7 reads the same endpoint). |
| `GET /api/v2/company/contributions` | `?partner_id=` optional | `{items:[{id,partner_id,partner_name,kind,kind_other,date,amount,currency,note,cash_tx_id}]}` newest first |
| `POST /api/v2/company/contributions` | `{partner_id, kind, kind_other?, date, amount, currency, note?, record_cash: bool, confirmed: true, op_id}` | 400 without `confirmed:true`; 404 unknown partner; 201 `{item}`. With `record_cash` and `kind=cash`: one `CashTransaction(kind='capital_in', source='شريك: {name}', description='دفعة رأس مال من {name}', amount_egp|amount_usd by currency, date, notes='co:contribution:{id}')` in the **same** DB transaction; its id stored in `cash_tx_id`. Same `op_id` within 10 minutes ⇒ the first item with `duplicate: true` (no second row). |
| `DELETE /api/v2/company/contributions/<id>` | `{confirmed: true}` | deletes the row and its linked `CashTransaction` (same transaction) ⇒ `{ok:true}` |
| `GET /api/v2/company/subscriptions` | — | `{items:[…all columns…]}` |
| `POST /api/v2/company/subscriptions` · `PUT /…/<id>` · `DELETE /…/<id>` | columns; DELETE body `{confirmed:true}` | `{item}` / `{ok:true}` |
| `POST /api/v2/company/subscriptions/<id>/paid` | `{date, confirmed: true, op_id}` | Creates one `Expense(date, category='tools', description='اشتراك: {name}', amount_egp|amount_usd, is_business=True, paid_by, notes='co:subscription:{id}:{renews_on or date}')`; 409 «سُجّل دفع هذه الفترة من قبل» if an Expense with the same notes exists; advances `renews_on` by one cycle (monthly: same day next month, clamped to the month's last day; yearly: +1 year; other: unchanged) ⇒ `{item, expense_id}`. Stopped subscription ⇒ 409. |
| `GET /api/v2/company/agreements` | — | `{items:[{…columns…, received:[{currency,amount}]}]}` — `received` = sum of `Revenue` with `payment_id LIKE 'co:agreement:{id}:%'` per currency (`amount_egp`/`amount_usd`/`amount_original`+`currency`) |
| `POST /api/v2/company/agreements` · `PUT /…/<id>` · `DELETE /…/<id>` | columns; DELETE body `{confirmed:true}`; 409 «للاتفاق مبالغ مستلمة مسجّلة» when `received` is not empty | `{item}` / `{ok:true}` |
| `POST /api/v2/company/agreements/<id>/renew` | `{starts_on, ends_on?, amount?, currency?}` | new agreement copying the old one (`renewed_from`=id, status active) and the old one set to `ended`, one transaction ⇒ `{item, previous}` |
| `GET /api/v2/company/ad-clients` | — | `{items:[{…client…, results:[{…result…, due:[{currency,amount}]|null}]}]}` results newest first |
| `POST /api/v2/company/ad-clients` · `PUT /…/<id>` · `DELETE /…/<id>` | columns; DELETE `{confirmed:true}`, 409 when any result is collected | `{item}` / `{ok:true}` |
| `POST /api/v2/company/ad-clients/<id>/results` | `{period, count?, income?, due_manual?, note?}` | 409 «لهذا الشهر نتيجة مسجّلة — عدّلها» on duplicate period; 201 `{item}` with `due` |
| `PUT /api/v2/company/ad-results/<rid>` · `DELETE /…/<rid>` | fields; DELETE `{confirmed:true}`; both 409 «حُصّل مبلغ هذا الشهر — لا يُعدَّل» once `revenue_id` is set | `{item}` / `{ok:true}` |
| `GET /api/v2/company/ad-clients/<id>/statement` | `?from=YYYY-MM&to=YYYY-MM` (default: all) | `{client, rows:[{period,count,income,due,sent_at,collected}], totals:{due:[…], collected:[…], open:[…]}}` |
| `POST /api/v2/company/ad-results/<rid>/sent` | `{}` | sets `sent_at`, `sent_by` ⇒ `{item}` |
| `POST /api/v2/company/income` | `{from_kind: 'agreement'|'ad_result', from_id, amount, currency, date, method: 'bank_transfer'|'cash'|'other', confirmed: true, op_id}` | One `Revenue`: `date`, `source` = `sponsor` (agreement) or `ad_client`, `description` = «راعٍ: {party}» / «عميل إعلانات: {name} · {period}», `client_name`, `payment_method`, `payment_id` = `co:agreement:{id}:{op_id}` or `co:adresult:{rid}`; EGP ⇒ `amount_egp`, USD ⇒ `amount_usd`, other ⇒ `amount_original` + `currency` + `needs_fx=True`. Ad result: amount must equal its `due` (422 otherwise), `revenue_id` set; already collected ⇒ 409. Duplicate `payment_id` ⇒ 200 with the existing row and `duplicate: true`. |
| `GET /api/v2/company/visits` | `?codes=a,b&from=&to=` | Proxy (`_v2_get`) to the platform route in Platform needs 1. Until it exists the platform 404 passes through ⇒ the screen shows «غير متاح بعد». |
| `POST /api/v2/company/forecast` | `{month, revenue_egp, cogs_egp, marketing_egp, payroll_egp, rent_egp, other_sga_egp, target_courses, target_students, notes}` | 409 if the month exists; 201 `{id}` |

Audit actions: as listed in §4.7 (`company.*`), `target` = the row id, `meta` = amount/currency/period where relevant.

---

## 9) What happened to each old piece (nothing left in «كل السجلات»)

| Old piece | New home / decision |
|---|---|
| `viewInvestment` KPIs (owners, capital, biggest share, unallocated) | «نظرة» partners card + «الشركاء ورأس المال» summary (capital per currency, not converted) |
| Owners table (partners + investors) + partner modal | «الشركاء ورأس المال» list + partner sheet (same `EP.createPartner/updatePartner/deletePartner`) |
| Investor drawer (read only) | «المستثمرون» list in the partners tab |
| Opportunities tab + modal | «فرص الاستثمار» collapsed section (same `EP.*Opportunity` calls) |
| «طلبات السحب ← في المالية» | Same link, only when pending rows exist |
| `investorModal` (in-memory only, never saved) | Removed — it wrote to a page array, not the server |
| `viewFoundation` assets / tools | «المعدات والاشتراكات» (assets via `/api/assets`; subscriptions now a real table — the old screen guessed them from asset categories) |
| Foundation «رأس المال» tab | Partners tab (agreed vs paid, contributions) |
| Foundation «حالة الكيان» (always empty, no source) | Agreements kind «أوراق الشركة» |
| `viewTargets` goals (derived) + bars | «الأهداف» (facts only, chips «تحقّق» / «باقٍ») |
| Manual goals / months added in memory | Removed (never saved). Months are now saved: `POST /api/v2/company/forecast` + existing `PUT /api/forecast/<id>` |
| AI goals advisor (`/api/ai/goals-advisor`, paid AI call on every open) | Not called. Brain line §4.6 is computed from facts. The route itself stays for the old screen (switch off) |
| `viewSettings` (all sections) | «الإعدادات», same EP calls; audit log inline; native `confirm()` replaced by the sheet; key names and model ids removed from visible text |

---

## 10) Tests — `backend/tests/test_v2s_company.py`

Run: `cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_company.py`. Zero network: no platform call except the `visits` proxy, which is tested against a stubbed `_platform_proxy` (any real URL ⇒ test failure, same guard as `test_v2_d3.py`).

**pytest (server):**
1. Switch off ⇒ every `/api/v2/company/*` route (all methods) returns 404, writes nothing.
2. No token ⇒ 401; roles `employee, trainer, investor, viewer, pending` ⇒ 403 on every route.
3. `Cache-Control: no-store` on every reply (success and error).
4. Validation table-driven: bad currency, contributions/subscriptions in SAR ⇒ 422; amount ≤ 0 or > 100M; percent 0 or 101; bad dates; `ends_on < starts_on`; unknown enum; `other` without its text ⇒ 422; `other` with text ⇒ 201; bad `ref_code`; duplicate active `ref_code` ⇒ 409; overlong text.
5. Contributions: no `confirmed` / `confirmed: "true"` ⇒ 400; cash + `record_cash` ⇒ one linked `CashTransaction` (EGP in `amount_egp`, USD in `amount_usd`, kind `capital_in`); asset kind never writes cash; same `op_id` twice ⇒ one row, `duplicate: true`; delete ⇒ both rows gone; unknown partner ⇒ 404.
6. Income: no `confirmed` ⇒ 400; EGP/USD/SAR land in the right `Revenue` columns (`needs_fx` for SAR); agreement same `op_id` twice ⇒ one Revenue; ad result collected twice ⇒ 409; amount ≠ due ⇒ 422; collected result cannot be edited or deleted (409); agreement with received money cannot be deleted (409).
7. Due math: 10% × 48,000 = 4,800; 6,000 + 5% × 31,000 = 7,550; fixed only; other ⇒ `due_manual`; percent with no income ⇒ `null` (not 0); half-up rounding to cents; statement totals per currency, never mixed.
8. Subscription paid: creates one `Expense` (right currency column, category `tools`); repeat for the same period ⇒ 409; `renews_on` advances (Jan 31 monthly ⇒ Feb 28/29; yearly +1; other unchanged); stopped ⇒ 409.
9. Renew: new row with `renewed_from`, old row `ended`, one transaction.
10. Summary: each block present with seeded data; force one block to raise (monkeypatch) ⇒ that key is `null`, others intact, status 200; `equity_total`; `covered_since` across a seeded run of months; `ending` window 45 days; reserve detection by role `pool` and by name.
11. Forecast POST: 201, duplicate month 409, bad month 422.
12. Audit: one row per successful write with the token's email; none on failures.
13. Existing endpoints untouched: `/api/partners`, `/api/assets`, `/api/forecast`, `/api/settings` replies unchanged (golden keys).

**node (pure helpers via `v2_node.logic('co.<fn>', …)`):**
- `brain`: each line from its facts; priority order; max 3; a `null` block gives no line; no «٠» or `NaN` in any text; plural forms (يوم واحد · يومين · ٣ أيام · ١٢ يومًا); «منذ» part only when earlier than `month`.
- `partnerChip` / `remaining` (per currency, overpaid ⇒ «دفع كاملًا», no payments ⇒ «لم تُسجَّل دفعات»).
- `agreementChip` / `renewChip` thresholds (30 / 7 / today / overdue), local dates.
- `dealText`, `statementText` exact strings (fixed-only omits the income line).
- `forecastBars` (`actual: null` ⇒ «لا دخل مسجّل»), `monthLine` three cases.
- `sumLines` never adds two currencies.

**static:**
- `index.html`: the two tags inside the `v2 sections` block, alphabetical; the generic `V2SEC` hook line exists once in `renderView` after the D3 line.
- `app.py`: exactly one `v2_company_routes` registration line, right before `# ---- v2 section routes end`.
- Root `Dockerfile` copies `dashboard-cloud/v2s` and `backend/v2_*_routes.py`.
- `company.js` never references `goals-advisor`, `ANTHROPIC`, `OPENAI`, `DEEPSEEK`, `api_key`; uses `localStorage` only for the last opened tab; contains no «يقوّم»; no visible headline starting with «الذكاء» or «AI».
- `SECTIONS` company entry equals §1; every old key (`investment`, `targets`, `settings`, `partners`, `foundation`) still lands on `company` (`test_v2_d1b.py` line 100 updated).

Then run the old suite file by file (`test_v2_d1.py`, `test_v2_d1b.py`, `test_v2_d2.py`, `test_v2_d3.py`, `test_dash_company_badges.py`, `test_finance_authz.py`, `test_xss_hardening.py`, `test_xss_sinks_round2.py`). Port-binding UI tests are re-run by the main session outside the sandbox.

---

## 11) Shots — `backend/tests/uiharness/v2_shots_company.py`

`cd backend && python3 -B tests/uiharness/v2_shots_company.py ../docs/v2/final/shots-company` — imports `Harness, DASH` from `ef_route_harness`, `Browsers, check` style helpers from `v2_shots` (imported, not edited), seeds with `co_fixtures.seed_dash(h.app)` (3 partners + a pool row, contributions with one partner owing 25,000, cash moves, 6 assets, 4 subscriptions with one renewing in 5 days, 4 agreements with one ending in 12 days and one ended, 2 ad clients matching the concept numbers with 3 months of results, 6 forecast months, revenues/expenses so the coverage line has a «منذ», 3 dashboard users, 30 audit rows). Viewports: desktop 1440×900 (`d`), tablet 820×1180 (`t`), mobile 390×844 (`m`).

Shots (each at d/t/m): `01-board` · `02-board-sources-down` (summary + visits failing) · `03-board-first-run` (empty DB) · `04-partners` · `05-contribution-form` · `06-contribution-review` · `07-assets` · `08-subscription-paid-review` · `09-deals` · `10-agreement-renew` · `11-ads` · `12-statement` · `13-collect-review` · `14-targets` · `15-forecast-sheet` · `16-settings` · `17-rate-review` · `18-old-link-foundation` (lands on «المعدات والاشتراكات») · `19-switch-off` (old investment screen unchanged).

The script fails when: any text «undefined», «NaN», «null», «[object Object]»; an element with `data-na` not reading «غير متاح بعد»; horizontal scroll at 390; a visible button under 52px on mobile or 44px elsewhere; a button outside the viewport; any write request without `confirmed: true` where §8 requires it (route interception log); any request leaving localhost except Google Fonts; switch off shows any `.co` element.

---

## 12) Out of scope (later rounds)
- A count on the «الشركة ورأس المال» tile and company cards in «ابدأ القرارات» (needs a shared edit of `v2Tiles`/`v2Decisions`; the summary endpoint is ready for it).
- Sending statements by email from the dashboard.
- Automatic results for ad clients and sponsor visits (Platform needs below).
- Removing the old screens' code (they stay for the switch-off path).
- Any deploy or push.

---

## Platform needs

1. **Visits and results by code** (sponsors and ad clients; depends on D4 attribution recording `?ref=` first-touch on visit, signup and payment):
   `GET /api/bridge/visits/by-ref?codes=<c1,c2,…≤50>&from=YYYY-MM-DD&to=YYYY-MM-DD` (header `X-ELP-Metrics-Secret`, read only)
   ⇒ `{"ok": true, "from": "…", "to": "…", "items": [{"code": "smart-office", "tracked": true, "visits": 180, "signups": 12, "paid_orders": 3, "paid": [{"currency": "EGP", "amount": 4500.0}]}]}`
   A code the platform never saw ⇒ `{"code": "…", "tracked": false}` (no zeros invented). Dashboard proxy: `GET /api/v2/company/visits` (already in §8).
2. **Course owners in the ad ledger detail:** `GET /api/bridge/ads-ledger/{owner_id}?kind=course|book&month=YYYY-MM` — today the route hard-codes `k = "book"` (`routes/books_bridge.py:229`). Same reply shape as today (`{ok, owner_id, owner_kind, balance, report, entries}`).
3. **Income attributed to ads for a linked work (ad clients who are course/book owners):**
   `GET /api/bridge/ads-ledger/{owner_id}/attributed?kind=course|book&month=YYYY-MM`
   ⇒ `{"ok": true, "owner_id": "…", "owner_kind": "book", "month": "2026-10", "sales": 14, "income": [{"currency": "EGP", "amount": 48000.0}]}` (sales of that work in the month whose order carries an ad campaign of that owner; refunds excluded). When present, «سجّل نتيجة شهر» offers «املأ من المنصة» (source `platform`).
