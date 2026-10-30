# SPEC — final round · section «roles»: every non-admin view in the new look

**Branch / worktree:** `final-roles` · `~/Documents/Playground/elprofessor-dashboard-v2/.worktrees/roles`
**Founder order (2026-10-30):** «الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا». This is final work, not a draft.
**Scope:** the four non-admin roles that `epBootCore()` routes to (`index.html` ~L7782): **trainer** (`t_home`, `t_courses`, `t_earnings`), **investor** (`i_home`, `i_market`, `i_invest`), **employee** (read-only staff: `users`, `courses`, `topics`, `tutorials`) and **viewer/pending** (`v_pending`). No new roles, no new permissions, and the same data. The only action change is that fake buttons are removed and one existing endpoint gets its first real button (see §0.3).
**Reference look:** D1-B shell (`v2-shell.css` side list, section header, tabs, mobile sheet), D3 money screens (`v2-d3.css` number cards, buttons, empty/failed states), the money confirmation sheet in `v2-home.js` `confirmModal` (amount · currency · name, busy lock, lost-reply lock). Concept boards: there is no board for role panels. These screens borrow the approved language of `POS-Phone` (photo tiles), `Person` (white boxes on paper, one fact per line) and `Money` (four numbers, «غير متاح بعد» for a missing source).

---

## 0. What exists today (read before building)

### 0.1 Wiring
- `ROLE_NAV` (`index.html` L618): `employee:['users','courses','topics','tutorials']`, `trainer:['t_home','t_courses','t_earnings']`, `investor:['i_home','i_market','i_invest']`, `viewer:['v_pending']`.
- `roleNavFor(r)` (L666) intersects `ROLE_NAV[r]` with the saved `role_permissions` map (`EP.data.settings.role_permissions`; `/api/settings` returns only that key to non-admins). The server enforces the same map with `module_required` (`app.py` L861).
- `setRole(r)` (L7610) adds `.app.ro` for employee/viewer, fills `#roBanner` from `ROLE_MSG` (emoji + text), forces `current` into the role's list, then calls `renderNav()` and `renderView()`.
- `epBootCore()` (L7782) maps any unknown role (incl. `pending`) to `viewer`. `EP.role` comes from `/auth/me` → `reported_role()` (`app.py` L1037). A split identity (role≠dashboard_role) is reported as `viewer`.
- The new shell (`V2SHELL`) and `/api/v2/config` are **admin only**. Every non-admin role still gets the old dark rail, the old `.kpi` cards and the emoji banner, even with `DASH_V2_ENABLED=true` in production.

### 0.2 Old screens and their data
| Module | Old function | Loader → endpoint | Problems found (each one is fixed by this spec) |
|---|---|---|---|
| `t_home` | `viewTHome` L7393 | `t_data` (`dashboard-api.js` L2607) → `GET /api/courses` + `GET /api/payouts` | «نسبتي» shows `0٪` when nothing is loaded. The «مساعد AI» button calls `go('ai')`, an admin screen the trainer cannot use (403s). |
| `t_courses` | `viewTCourses` L7415 | same | The «دافع» column is invented (= students count for any paid course; the loader comment says «تقديري»). |
| `t_earnings` | `viewTEarnings` L7428 | same | **«اطلب صرف» is a fake button.** It prints «تم تسجيل طلب الصرف…» and sends nothing. «في الضمان» sums payout statuses `escrow/held`, which never exist (`Payout.status` ∈ `accrued, paid, waived`), so it is always a false `0`. «ترتفع إلى ٥٠٪ بعد ١٠ دورات ناجحة» is an invented promise that contradicts `SHARES-2026-10-30.md`. The label says «واستثماري» but shows no investment. |
| `i_home` | `viewIHome` L7458 | `i_data` (L2649) → `/me/investor-wallet`, `/investor/badges`, `/investments/active`, `/investments/history`, `/investment-opportunities` | Every job `.catch()`es into `null`/`[]`, so a failed source prints `0` or «لا توجد». «متاح للسحب» has no withdraw button, although `EP.investorWithdraw` (L3794) and `POST /api/investor/withdraw` exist and have no caller. «مساعد AI» → admin screen. |
| `i_market` | `viewIMarket` L7477 | same | **«استثمر» is a fake button** («تم تسجيل اهتمامك… سيتواصل الفريق», nothing is recorded). Amounts are labelled «ج», but opportunity amounts are **US dollars**: `sync_opportunity_funding` sums `Investment.amount_usd`. The label «ماركت» is not plain Arabic. |
| `i_invest` | `viewIInvest` L7491 | same | Only active investments are shown; the history is loaded but never displayed. |
| `v_pending` | `viewViewer` L7505 | `EP.user` | Old placeholder look. The only way out is the old dark rail's logout button. |
| employee | `viewUsers` / `viewCourses` / `viewTopics` / `viewTutorials` | `users`, `courses`+`inbox`+`course_offers`+`platform_courses`+`schedules`, `platformTopics`…, `tutorials` | These are the admin screens with `.app.ro .acts{display:none}`. They show the old look, with the emoji banner «⚠ وضع موظف المتابعة». `platform_courses` collapses a failure into `[]` («لا توجد دورات»). |

### 0.3 Rules applied here
- Same data: every number below comes from an endpoint the role already calls today.
- Same actions, except two cases:
  - **Removed:** the three fake buttons («اطلب صرف», «استثمر», «مساعد AI»). They never did anything.
  - **Wired:** the existing withdraw endpoint (`POST /api/investor/withdraw`, already open to `investor` and `trainer` via `wallet_owner_name`). It gets its first button, behind the money confirmation sheet and a new thin `confirmed:true` guard route (§5).
- A missing source shows «غير متاح بعد» plus a retry. It never shows `0`. A real zero shows `٠`.
- The founder's «العقل» belongs to the founder's dashboard only. Role screens carry a plain **«الخطوة التالية»** line built from facts (§6). It is never branded as the brain, and it never comes from a model.

---

## 1. Architecture (parallel-safe)

### 1.1 Files
| File | New/edit | Content |
|---|---|---|
| `dashboard-cloud/v2s/roles.js` | new | `window.V2R`: the roles shell, the screens, the sources, the withdraw sheet, and the install hook (§1.3). |
| `dashboard-cloud/v2s/roles.css` | new | All rules under `.app.v2-roles` or classes prefixed `v2r-`. It also holds the legacy restyle under `.app.v2-roles.v2r-legacy #view`. |
| `dashboard-cloud/v2-logic.js` | append only | One block at the very end, `// ===== v2s:roles =====` … `// ===== /v2s:roles =====`. It is a separate IIFE that attaches `V2L.roles = {…}` (pure helpers, §7). No `SECTIONS` entry: roles are not an admin section. |
| `dashboard-cloud/index.html` | block only | Inside `<!-- v2 sections begin -->` … `<!-- v2 sections end -->` (create it right after `<script src="v2-d2.js"></script>` if missing). Add two lines, alphabetical by key: `<link rel="stylesheet" href="v2s/roles.css">` and `<script src="v2s/roles.js"></script>`. **No other edit to index.html.** |
| `backend/v2_roles_routes.py` | new | `register(app)` adds two routes (§5). |
| `backend/app.py` | one line | Before the marker `# ---- v2 section routes end`. If the marker is missing, create it right after the `v2_book_request_patch` function (the last `/api/v2/*` route, ~L2692) and before `@app.route('/api/platform-pnl'`. The line: `__import__('v2_roles_routes').register(app)   # v2s:roles` |
| `backend/Dockerfile` | **shared edit** | `COPY app.py .` ⇒ `COPY app.py v2_*_routes.py ./`. Without it, no section's route file reaches production. List it under shared_edits, and the merger keeps one copy. |
| `backend/tests/test_v2s_roles.py` | new | §9 |
| `backend/tests/uiharness/v2_shots_roles.py` | new | §10, saving to `docs/v2/final/shots-roles/` |

`register(app)` gets the app module with `M = sys.modules[app.import_name]` (`'app'` under gunicorn and tests, `'__main__'` when run directly). It reads only existing helpers from `M`: `token_required`, `roles_required`, `_v2_enabled`, `_v2_ns`, `reported_role`, `entitlement_key`, `_audit`, `V2_CONFIRM_AR`, and `app.view_functions['request_withdrawal']`. It defines no second copy of any money rule.

### 1.2 The switch
- New `GET /api/v2/roles/config` (§5.1) is open to **any** signed-in role, because `/api/v2/config` is admin-only.
- Switch closed (or no reply within 3 s, or any error) ⇒ the role keeps today's screens byte-for-byte, and roles.js does nothing else.
- To avoid a flash of the old look, copy the D1-B memo pattern:
  - Store `localStorage['ep_v2_roles']='1'` after an `enabled:true` reply. Remove it after any decisive `false`.
  - While the memo is set and the reply is pending, add `.app.v2-pre` (it already hides `.rail` and sets `.main` to `visibility:hidden`).
- The admin path is never touched: every patched function first checks `EP.role` (mapped like `epBootCore`) and calls the original for `admin`.

### 1.3 Install hook (no index.html edits outside the block)
`roles.js` loads before the inline script, so it installs on `DOMContentLoaded`. Its listener is registered after `dashboard-api.js`'s, and runs before the `setTimeout(EP.start,0)` that `dashboard-api.js` schedules there.

On `DOMContentLoaded`:
1. Guard: `typeof window.renderView==='function' && typeof window.setRole==='function' && typeof window.go==='function' && typeof window.roleNavFor==='function'`. If any is missing, do nothing (old screens stay).
2. Wrap `window.setRole`:
   - `r==='admin'` ⇒ call the original.
   - Otherwise:
     - set `V2R.role=r`;
     - if the memo is set, add `.app.v2-pre`;
     - call the original (it sets `role`, `.ro`, `current`, and calls `renderNav`/`renderView`, which the next patch catches);
     - start `V2R.loadFlag()`.
3. Wrap `window.renderView`:
   - If `V2R.active` and the mapped role ≠ admin ⇒ `V2R.render()`.
   - Else if the flag is still pending and the memo is set ⇒ `V2R.renderSkeleton()` (a neutral paper card with «…جارٍ التحميل»).
   - Else call the original.
4. On flag reply:
   - `enabled:true` ⇒ `V2R.activate()`: build the shell (§2), remove `.app.v2-pre`, and call `renderView()`.
   - Otherwise ⇒ remove `.app.v2-pre` and call `renderView()` (old screen).

Function declarations in the inline classic script are writable `window` properties, so `go()`→`renderView()` resolves to the wrapper. `ROLE_NAV`, `current`, `topicsTab`, `role` are top-level `let/const` in a classic script, and are readable from roles.js by bare identifier at run time (always behind `typeof x!=='undefined'`). roles.js **never writes** them; it only calls `go(mod)`.

Navigation always goes through the existing `go(mod)`. It keeps the old hashes (`#t_home`, `#i_market`, `#users`…), so deep links and old bookmarks work. One exception, for tutorials: `go('tutorials')` resolves through `REDIRECTS` to `current='topics'` with `topicsTab='tutorials'`. Right after, roles.js calls `history.replaceState(null,'','#tutorials')`, so a reload lands on the tutorials tab again.

---

## 2. The roles shell (all four roles)

`V2R.activate()`:
- Adds `v2-shell v2-roles v2-bare` to `.app`, plus `v2r-<role>` (`v2r-trainer`, `v2r-investor`, `v2r-staff`, `v2r-viewer`).
- This reuses the D1-B layout rules in `v2-shell.css`: old rail, `#coPin` and `#roBanner` hidden; paper background; topbar on narrow screens.
- It builds its own nodes with the **D1-B classes** but **its own ids**, so `V2SHELL` never touches them:
  - `<aside id="v2rSide" class="v2-side">` after `.rail`;
  - `<div id="v2rSec" class="v2-sec">` before `#view`;
  - `<div id="v2rSheet" class="v2-sheet" aria-hidden="true">` on `body`;
  - `<span class="v2-tb-logo">` (the elephant SVG) before `.topbar .ttl`;
  - `#menuBtn.onclick` is replaced so it opens/closes `#v2rSheet` (same focus trap and Esc as `V2SHELL`; copy the 15 lines rather than calling V2SHELL internals).

### 2.1 Side list (desktop ≥1180 px, 264 px wide; same markup as `sideItem()`)
- Brand block: `.v2s-brand` with the mark, «البروفيسور», and a role subtitle:
  - trainer «لوحة المدرّب»
  - investor «لوحة المستثمر»
  - employee «فريق المتابعة»
  - viewer «حسابك»
- Items: one `a.v2s-item` per id in `roleNavFor(role)`, in that order. Each has `href="#<id>"` and `data-mod`, a photo circle `.v2s-ph` from `v2/img/<img>.jpg` (no new images), and the label below.
- No count badges: roles have no queues. Click ⇒ `go(id)` (Ctrl/⌘-click keeps the default link behaviour).

| id | Label in the new shell (exact) | Photo | Header line under the title (exact) |
|---|---|---|---|
| `t_home` | «لوحتي» | grid icon (`.v2s-ph-home`) | «دوراتك ومستحقاتك كما سجّلتها الإدارة» |
| `t_courses` | «دوراتي» | `courses` | «الدورات المربوطة باسمك وحالة كل دورة» |
| `t_earnings` | «أرباحي» | `money` | «مستحقاتك من الدورات، ومحفظتك إن كانت لك استثمارات» |
| `i_home` | «محفظتي» | grid icon | «رصيدك وما استثمرته وعوائدك» |
| `i_market` | «فرص الاستثمار» | `company` | «الفرص المفتوحة الآن وما جُمع لكل فرصة» |
| `i_invest` | «استثماراتي» | `money` | «كل استثمار باسمك وحالته» |
| `users` | «الأعضاء» | `people` | «أعضاء المنصة للاطلاع فقط» |
| `courses` | «الدورات» | `courses` | «دورات المنصة وحالتها للاطلاع فقط» |
| `topics` | «الموضوعات» | `content` | «موضوعات المنصة وحالتها للاطلاع فقط» |
| `tutorials` | «دليل الاستخدام» | `books` | «شروحات المنصة كما يراها الأعضاء» |

(`ROLE_MODULES`/`MODULES` labels are **not** edited; the new labels live in `V2L.roles.NAV`.)

- User block (`.v2s-me`):
  - initial avatar, the name (`EP.user.name || EP.user.email`), and a small role line:
    - trainer «مدرّب»
    - investor «مستثمر»
    - employee «فريق المتابعة · للاطلاع فقط»
    - viewer «بانتظار التفعيل»
  - the logout button `.v2s-out` (aria-label «تسجيل الخروج») ⇒ `document.getElementById('logoutBtn').click()`.

### 2.2 Header (`#v2rSec`, same classes `.v2c-h`, `.v2c-tabs`)
- `h1` = the label above. `p` = the header line above.
- Tabs (`.v2c-tab`, 48 px) appear **only** where the screen has sub-views. They are V2R internal state, not in the hash:
  - `i_invest`: «الجارية» · «المنتهية»
  - `courses` (employee): «الكتالوج» · «كل السجلات»
  - `topics` (employee): «الموضوعات» · «دليل الاستخدام» (if `tutorials` is allowed) · «كل السجلات». The tutorials tab is the same view as the `tutorials` nav item.
- `#pageTitle` gets the new label (mobile topbar).

### 2.3 Narrow screens (<1180 px: tablet 820, phone 390)
- The topbar shows: logo · title · bell (employee only, §2.4) · menu button (44×44).
- The menu opens `#v2rSheet`:
  - title «القائمة»;
  - a 2-column grid (3 columns ≥601 px) of `.v2s-tile` photo tiles for the role's items (the same `--rgb` colours as `v2-shell.js` `RGB`: courses `91,74,170`, money `26,43,74`, company `58,60,72`, people `24,126,78`, content `190,88,48`, books `14,120,130`, grid tiles `158,43,78`);
  - the user block with logout at the bottom.
- The viewer has a single screen: no menu button and no sheet. Logout sits inside the card.

### 2.4 Bell
- trainer/investor/viewer: `/api/notifications` deliberately returns an empty list for them (`app.py` L7890). Hide `#bellBtn` with `.app.v2-roles:not(.v2r-staff) #bellBtn{display:none}`.
- employee: keep today's bell and panel (`renderNotifPanel`, same data). It gets the D1-B style already applied by `.app.v2-shell .topbar #bellBtn`.

### 2.5 Shared visual rules (`roles.css`)
- Tokens on `.app.v2-roles` (same values as D3): `--wine:#9E2B4E; --paper:#FBFAF7; --paper2:#F6F1EA; --ink:#21262E; --red:#C8102E; --line:#E9E1D6; --mute:#6B665C; --green:#187E4E; --amber:#8F5F00; --amber-bg:#FFF6DD`. Fonts: Cairo for titles and numbers; 'IBM Plex Sans Arabic' for body text.
- Page width: `.v2r` max 1120 px, centred.
- **Number card** `.v2r-num`:
  - white, 1 px `--line`, radius 18, top border 5 px in the card's colour;
  - `h3` 15.5 px `--mute`; value `.v2r-big` 30 px/800 (26 px <600);
  - fine line `.v2r-note` 13.5 px.
  - State «غير متاح بعد» uses `.v2r-big.na` (20 px, `#8A8478`).
- **Grid of numbers**: `repeat(4,minmax(0,1fr))` ≥1180 · 2 columns 600–1179 · 1 column <600.
- **Hero** `.v2r-hero` (home screens only):
  - a photo banner 168 px (124 px <600), radius 22, `background-size:cover`;
  - gradient `linear-gradient(to left, rgba(33,38,46,.0) 30%, rgba(33,38,46,.78))`;
  - white text: `h2` 26 px «أهلًا، {الاسم}», plus one line.
  - Photo: trainer `courses.jpg`, investor `company.jpg`.
- **List card** `.v2r-row`: white, radius 16, min-height 64, padding 14/18, `grid-template-columns: 1fr auto` on desktop and stacked <600; title 16.5 px/800 Cairo; meta line 14 px `--mute`; status chip `.v2r-chip` (min-height 32, radius 999, 13.5 px/700).
  - Chip tones: green `#E8F6EE/#0F5A37`, amber `#FFF6DD/#6B4A00`, wine `#FBF0F3/#9E2B4E`, grey `#F1EEE8/#5D584F`, red `#FDECEF/#8E1228` (red only for «خسارة» and «مرفوضة»).
- **Buttons**:
  - `.v2r-btn1`: wine, white, min-height 48 (52 <600, full width), radius 14, Cairo 800 15.5 px.
  - `.v2r-btn2`: white with a wine outline, min-height 44 (52 <600).
  - `.v2r-link`: wine text link, min-height 44.
  - No target below 44 px. No horizontal page scroll at 390 px (long emails get `overflow-wrap:anywhere` and `direction:ltr; unicode-bidi:isolate`).
- **States**:
  - loading `.v2r-load` «…جارٍ التحميل»;
  - empty `.v2r-empty` (dashed card, `b` title + one line);
  - failed strip `.v2r-fail` (amber `#FFF8E6`/`#EBD38E`/`#6B4A00`): «تعذّر جلب {المصدر}. الأرقام التي تعتمد عليه تظهر «غير متاح بعد».» plus `.v2r-link` «أعد المحاولة» ⇒ reload that source only.
- **Next line** `.v2r-next`: a white card with a 4 px wine inline-start border, an icon dot, 15 px text, and an optional `.v2r-link`.
- Focus ring `outline:3px solid rgba(158,43,78,.45)`. `prefers-reduced-motion` turns off transitions.

---

## 3. Sources (roles.js owns its own fetch state; same endpoints)

The old loaders collapse failures into `[]`/`null`/`0`, so V2R keeps its own source table, the D3 `SRC` pattern:
- Each source is `{state:'idle'|'loading'|'ready'|'error', data, status}`.
- Each load is **one** call with `EP.api(path)` and no automatic retry.
- `V2R.reload(key)` re-runs it, and redraws on settle.

| Key | Endpoint (existing) | Roles that load it | Notes |
|---|---|---|---|
| `me` | `GET /api/v2/roles/config` (new, §5.1) | all | Gives `linked` (does this account have an admin-set money link?). |
| `courses` | `GET /api/courses` | trainer | The server scopes to own courses. `revenue_split.trainer_percent` is present on own courses only. |
| `payouts` | `GET /api/payouts` | trainer | The server scopes to own rows (`payout_visible_to`). |
| `wallet` | `GET /api/me/investor-wallet` | trainer, investor | `id:null` = no wallet (unlinked, `empty_wallet_payload`). The values are **USD** with `_egp` twins. |
| `badges` | `GET /api/investor/badges` | investor | |
| `active` | `GET /api/investments/active` | trainer, investor | |
| `history` | `GET /api/investments/history` | trainer, investor | |
| `opps` | `GET /api/investment-opportunities` | investor | Admin+investor only. Never requested for a trainer (it would 403). |
| `people` | `GET /api/platform-users` | employee (if `users` allowed) | `{users:[…], count}` |
| `pcourses` | `GET /api/platform-courses` | employee (if `courses` allowed) | `{courses:[…]}` (bridge row: `title, instructor_name, type, source, approval_status, is_active, archived_at, price_amount, price_currency, total_enrolled, lesson_count, story`) |
| `topics` | `GET /api/platform-topics` | employee (if `topics` allowed) | list or `{topics:[…]}` |
| `tutorials` | `GET /api/tutorials` | employee (if `tutorials` allowed) | list or `{tutorials:[…]}` |

Lazy loading: a source loads the first time a screen that needs it is drawn. The trainer home loads `me, courses, payouts`. The trainer earnings screen adds `wallet, active, history`.

A 401 is handled by `EP.api` (login screen). A 403 from `module_required` is shown as a failed source with the server's Arabic text («هذا القسم غير متاح لدورك»).

---

## 4. Screens

### 4.1 Trainer · «لوحتي» (`t_home`)
Desktop layout, top to bottom:
1. **Hero** (`courses.jpg`): «أهلًا، {EP.user.name}» / «هذه دوراتك ومستحقاتك كما سجّلتها الإدارة.»
2. **Unlinked notice**, only when `me.linked===false` (amber, no button): «حسابك غير مربوط باسمك في سجلات الإدارة بعد، لذلك لا تظهر دوراتك ولا مستحقاتك هنا. تواصل مع الإدارة لربطه.» In this case all numbers below show «غير متاح بعد» (not `٠`).
3. **«الخطوة التالية»** (§6.1), if any.
4. **Three numbers**:

| Card (h3, exact) | Value | Fine line (exact) | Colour |
|---|---|---|---|
| «دوراتي» | `courses.length` | «مربوطة باسمك» | `--wine` |
| «المسجّلون في دوراتي» | Σ `students_count` | «في كل دوراتك» | `--ink` |
| «مستحق لك» | Σ `total_egp` of payouts with `status ∈ {accrued, pending}` → «{fmt} جنيه» | «مسجّل في دفتر الإدارة ولم يُحوَّل بعد» | `--green` |

   Source states:
   - `courses` failed ⇒ cards 1 and 2 show «غير متاح بعد»;
   - `payouts` failed ⇒ card 3 shows «غير متاح بعد»;
   - while loading, the value shows «…».
5. **«آخر دوراتي»**: up to 3 rows from `courses` (same row as §4.2), then `.v2r-link` «كل دوراتي» ⇒ `go('t_courses')`. Empty: «لا توجد دورات مربوطة بحسابك بعد.»
6. **Platform link card** (`.v2r-row`): «لوحتك الكاملة على المنصة» / «المبيعات والطلاب والحلقات كما تظهر لك على المنصة.» plus `.v2r-btn2` «افتح على المنصة» ⇒ `https://app.elprofessor.net/?page=trainer`, `target="_blank" rel="noopener"`. This deep link is the one the platform already sends in emails (`platform-app/src/app-root.jsx` L237). It is a link, not a request.

- Tablet: the numbers go into 2 columns (third card full width).
- Phone: everything stacks; the hero is 124 px; the platform button is full width at 52 px.
- **Removed:** «مساعد AI» (it opened an admin screen) and «نسبتي» on the home screen (the percentage is per course; it lives on each course row).

### 4.2 Trainer · «دوراتي» (`t_courses`)
- A count line «{n} دورة» (`U.U` plural forms: «دورة واحدة / دورتان / دورات / دورة»).
- One `.v2r-row` per course in `courses` (server order = newest first):
  - **title**: `title`.
  - **chip** from `status`:
    - `active` «مفتوحة» (green)
    - `draft` «مسودة» (grey)
    - `completed` «انتهت» (wine)
    - `archived` «مؤرشفة» (grey)
    - anything else ⇒ «غير معروفة» (grey)
  - **meta line** (joined with « · »):
    - «{students_count} مسجّل»
    - price: `price_egp>0` ⇒ «{fmt} جنيه», else `price_usd>0` ⇒ «{fmt} دولار», else «مجانية»
    - `start_date` ⇒ «تبدأ {dateText}»
  - **share line**: `revenue_split.trainer_percent > 0` ⇒ «نصيبك من الدورة: {ar}٪», else «نصيبك من الدورة: غير محدد بعد».
- Empty (ready, 0 rows): `.v2r-empty` «لا توجد دورات مربوطة بحسابك بعد» / «تظهر هنا كل دورة تربطها الإدارة باسمك.»
- Failed: the `.v2r-fail` strip «تعذّر جلب دوراتك…» + «أعد المحاولة».
- **Removed:** the «دافع» column (invented estimate).
- No buttons on rows (the trainer had none before).

### 4.3 Trainer · «أرباحي» (`t_earnings`)
**Part A: «من الدورات»** (h2 22 px)

| Card | Value | Fine line |
|---|---|---|
| «مستحق لك» | Σ `total_egp` with `status ∈ {accrued, pending}` | «لم يُحوَّل بعد» |
| «حُوّل إليك» | Σ with `status==='paid'` | «منذ البداية» |
| «آخر ٣٠ يومًا» | Σ of rows whose `date` is within 30 days of `now` and `status!=='waived'` | «مستحق أو محوَّل» |

- Below the cards: a list **«سجل المستحقات»**, one row per payout (newest first).
  - Title: `related_to` or «مستحق».
  - Meta: `dateText(date)`.
  - Amount: «{fmt} جنيه».
  - Chip: `accrued`/`pending` «مستحق» (amber), `paid` «حُوّل» (green), `waived` «أُسقط» (grey).
- Empty: «لا توجد مستحقات مسجّلة باسمك بعد.»
- Fine line under Part A (fact, no promise of timing): «المستحقات تحوّلها الإدارة إليك، وتظهر هنا حين تُسجَّل.»
- **Removed:**
  - «في الضمان» (no such status exists);
  - the invented «ترتفع إلى ٥٠٪ بعد ١٠ دورات ناجحة»;
  - the fake «اطلب صرف» button (there is no endpoint for course payouts; the admin settles them).

**Part B: «محفظة الاستثمار»**, drawn only if `wallet.id != null`:
- If `wallet` failed: show the strip and stop.
- If `id==null`: one line «لا توجد لك استثمارات مسجّلة.» and stop.
- Otherwise the same block as the investor's «محفظتي» numbers (§4.4 item 4), the same withdraw button (§4.8), and a compact list of `active` (same row as §4.6).

### 4.4 Investor · «محفظتي» (`i_home`)
1. **Hero** (`company.jpg`): «أهلًا، {الاسم}» / «رصيدك واستثماراتك كما سجّلتها الإدارة.»
2. **Unlinked** (`wallet` ready with `id==null`), amber: «حسابك غير مربوط بمحفظة بعد، لذلك لا يظهر رصيدك هنا. تواصل مع الإدارة لربطه.» All money cards show «غير متاح بعد».
3. **«الخطوة التالية»** (§6.2).
4. **Four numbers** (wallet values are stored in dollars; the `_egp` twins are converted at today's rate):

| Card | Value | Fine line |
|---|---|---|
| «متاح للسحب» | `balance_egp` → «{fmt} جنيه» | «بعد خصم طلبات السحب قيد المراجعة» |
| «إجمالي ما استثمرته» | `total_invested_egp` | «كل استثماراتك» |
| «عوائد مستلمة» | `total_returns_egp` | «من الاستثمارات المنتهية» |
| «سحب قيد المراجعة» | `pending_withdrawals` → `moneyText(x,'USD')` | «تراجعه الإدارة» |

   - Under the grid, `.v2r-note`: «القيم مسجّلة بالدولار وتظهر بالجنيه بسعر الصرف الحالي.»
   - Card 4 shows dollars because the server sends no EGP twin for it. That is not hidden.
5. **Withdraw**: `.v2r-btn1` «اطلب سحب الرصيد».
   - Shown when `wallet.id!=null && balance_egp>0` and `wallet` is ready.
   - Otherwise no button. When `balance_egp===0` (real zero), the fine line reads «لا يوجد رصيد متاح للسحب الآن.»
   - Opens §4.8.
6. **«المستوى»** row: «مستواك: {برونزي|فضي|ذهبي|بلاتيني}» (from `wallet.level`; an unknown value is shown as is). Badges from `badges`:
   - earned ones as wine chips with `label`;
   - then «{ar(earned)} من {ar(total)} شارات»;
   - unearned ones are not listed.
   - `badges` failed ⇒ the badges line shows «غير متاح بعد».
7. **Shortcuts** (two `.v2r-row`):
   - «فرص الاستثمار» / «{n} فرصة مفتوحة الآن» (opps count with status ∈ open, hot, invite_only), or «غير متاح بعد» if `opps` failed ⇒ `go('i_market')`;
   - «استثماراتي» / «{n} استثمار جارٍ» ⇒ `go('i_invest')`.
- **Removed:** «مساعد AI».

### 4.5 Investor · «فرص الاستثمار» (`i_market`)
- Count line «{n} فرصة».
- One card per opportunity (server order):
  - title `course_title`; meta «المدرّب: {trainer_name}» (omitted if empty) · «{students_count} مسجّل».
  - **Progress bar** `.v2r-bar`: 10 px, radius 6, `--paper2` track, wine fill = `funding_percent` (clamped 0–100). Under it: «جُمع {moneyText(current_funded,'USD')} من {moneyText(target_amount,'USD')} · {ar(funding_percent)}٪».
  - Facts list (two columns desktop, one column phone):
    - «العائد المتوقع» `{ar(expected_roi)}٪`, with a tiny fine line «رقم تقديري حدّدته الإدارة»;
    - «الحد الأدنى للمشاركة» `moneyText(min_investment,'USD')`;
    - «تبدأ» `dateText(expected_start)` (omitted if null);
    - «تنتهي» `dateText(expected_end)` (omitted if null).
  - Chip from `status`:
    - `open` «مفتوحة» (green)
    - `hot` «إقبال مرتفع» (wine)
    - `invite_only` «بدعوة» (amber)
    - `funded` «اكتمل التمويل» (grey)
- **No button on the card.** One fact line at the top of the list: «للمشاركة في فرصة، تواصل مع الإدارة.» (A real request button is a founder decision, see §12.)
- **Fixed:** amounts are dollars (were wrongly labelled «ج»).
- Empty: «لا توجد فرص استثمار مفتوحة الآن» / «تظهر هنا كل فرصة تفتحها الإدارة.»
- Failed: strip.

### 4.6 Investor · «استثماراتي» (`i_invest`)
- Tabs «الجارية» (`active`) · «المنتهية» (`history`), each tab label with its count in Arabic digits: «الجارية ({n})».
- Row:
  - title `course_title` (empty ⇒ «استثمار»);
  - meta «استثمرت {fmt(invested_total_egp)} جنيه» · `dateText(created_at)`;
  - chip from `status`:
    - `active` «جارٍ» (green)
    - `pending` «بانتظار» (amber)
    - `accrued` «قيد الاحتساب» (amber)
    - `completed` «مكتمل» (wine)
    - `paid` «صُرف» (green)
    - `loss` «خسارة» (red)
  - second line: if `course_title` is non-empty ⇒ «العائد المحسوب حتى الآن: {ar(roi_percent)}٪»; else «العائد: غير متاح بعد» (the server computes roi from the course; no course = no basis).
  - For `history`: if `actual_return>0`, add «العائد الفعلي: {moneyText(actual_return,'USD')}».
- Empty, active: «لا توجد استثمارات جارية باسمك.» plus `.v2r-link` «تصفّح فرص الاستثمار» ⇒ `go('i_market')`. Empty, history: «لا توجد استثمارات منتهية بعد.»
- Failed (per tab source): strip.

### 4.7 Viewer · «بانتظار التفعيل» (`v_pending`)
- No side list and no tabs (`.app.v2r-viewer .v2-side,.v2-sec{display:none}`).
- One centred card (max 560 px, white, radius 22, overflow hidden):
  - top photo band `people.jpg` 140 px with the wine elephant mark in a 56 px circle overlapping its bottom edge.
  - `h1` 26 px «حسابك بانتظار التفعيل»
  - `p` «سجّلت بنجاح. تراجع الإدارة حسابك وتحدّد صفته، ثم تظهر لوحتك هنا.»
  - identity box (paper2, radius 14): «الحساب: {name}» and the email on its own line (`dir="ltr"`).
  - buttons:
    - `.v2r-btn1` «تحقّق من جديد» ⇒ `location.reload()` (re-runs `/auth/me`; nothing new is called);
    - `.v2r-btn2` «تسجيل الخروج» ⇒ `#logoutBtn.click()`.
- Phone: the card fills the width with a 16 px gutter; the buttons stack at 52 px.

### 4.8 Withdraw sheet (trainer Part B and investor «محفظتي»)
This is the money confirmation sheet pattern: `window.openModal`, the D2/D3 markup (`.mc-lead`, `.mc-tab`, `.acts` inside the modal, which lives outside `.app`, so `.app.ro .acts` cannot hide it), and two stages.

**Stage 1, form** (title «طلب سحب من محفظتك»):
- `.mc-lead`: «يصل طلبك إلى الإدارة لمراجعته وتحويله. يُخصم المبلغ من رصيدك المتاح فور إرسال الطلب.»
- Field label «المبلغ بالجنيه»:
  - `<input inputmode="numeric" dir="ltr">` prefilled with `Math.floor(balance_egp)`.
  - Fine line «الرصيد المتاح: {fmt(balance_egp)} جنيه».
  - If `balance>0`, also «الحد الأدنى للسحب ٥٠ دولارًا (نحو {fmt(round(50*balance_egp/balance))} جنيه)». The rate is derived from the wallet's own two numbers. If `balance==0`, this part is omitted.
- Buttons: «راجع الطلب» (primary) · «إلغاء».
- Client checks before review: a whole number >0 and ≤ `floor(balance_egp)`. Otherwise show the inline error «اكتب مبلغًا صحيحًا لا يزيد على رصيدك المتاح.» The minimum is checked by the server (its Arabic message is shown as is, with Arabic digits).

**Stage 2, review**:
- `.mc-lead` «راجع الطلب قبل التأكيد».
- Table rows:
  - «المبلغ» **{fmt} جنيه**
  - «العملة» «جنيه مصري»
  - «الاسم» `EP.user.name`
  - «من» «محفظة الاستثمار»
- Buttons: «أكّد طلب السحب» (primary) · «رجوع للتعديل».

**Send**:
- `EP.api('/v2/roles/withdraw',{method:'POST',body:{amount:N,currency:'EGP',confirmed:true}})`.
- The button locks on the first press (`dataset.busy`), its text becomes «جارٍ الإرسال…», and the second press does nothing.

**Results**:
- **200**: close; toast «أُرسل طلب السحب»; reload `wallet`.
- **400/403/404**: inline `.v3-err`-style message. Use the server text with digits converted (for example «الحد الأدنى للسحب هو ٥٠ دولار», «الرصيد المتاح لا يكفي», «هذا الحساب غير مرتبط بمحفظة مستثمر»). The button is re-enabled.
- **no reply** (no status, or 5xx without a message): «لم يصل رد. حدّث الصفحة وتأكّد من رصيدك قبل أي محاولة جديدة.» The button stays disabled. Reload `wallet` (the D3 lost-reply rule).
- **401**: `EP.api` shows the login screen.

### 4.9 Employee (read-only «فريق المتابعة»)
`.app.ro` stays (set by `setRole`).
- The new screens render **no write buttons at all**. Only navigation, filters, search, expand/collapse and retry.
- Each nav item appears only if it is in `roleNavFor('employee')`. If the list is empty, the screen shows the viewer card's body with «لا توجد شاشات متاحة لحسابك الآن. تواصل مع الإدارة.» and logout.

**«الأعضاء»** (`users`, source `people`):
- Bar:
  - search input (placeholder «ابحث بالاسم أو البريد أو الهاتف», 48 px, local filter, case-insensitive on `full_name/name`, `email`, `phone`);
  - chips (44 px) with counts:
    - «الكل»
    - «المدرّبون» (`trainer_status==='approved'`)
    - «طلبات تدريب» (`trainer_status==='pending'`)
    - «الإدارة» (`role ∈ {admin, staff}`)
    - «المستثمرون» (`role==='investor'`)
    - «تجريبي» (`is_test`)
- Count line «{n} عضو». It uses `count` from the reply when present, else the length.
- Row:
  - initial avatar;
  - name (`full_name||name||email`);
  - email line (`dir=ltr`);
  - chips: role (admin «إدارة», staff «فريق», investor «مستثمر», else «عضو»), trainer («مدرّب» green / «طلب تدريب» amber), «تجريبي» (grey) if `is_test`;
  - meta «انضم {dateText(created_at)}» · plan (`plan_id`: free «مجانية», pro «احترافية», premium «بريميوم», else as is).
- Tap ⇒ an **expand-in-place** details block (no drawer; works at 390 px):
  - «الهاتف» `phone||'—'`
  - «الفئة» (`SEG_LABEL[segment]` via `typeof SEG_LABEL` guard, else `segment||'—'`)
  - «الوسوم» (chips or «—»)
  - «يظهر في الدليل العام» (`public_ready`: true «نعم» / false «لا» / null «غير متاح بعد»)
- Empty filter result: «لا يوجد أعضاء بهذا الشرط.»

**«الدورات»** (`courses`):
- Tab «الكتالوج» (source `pcourses`):
  - one row per course:
    - title;
    - chip by the same rule as `pcStatus`, re-implemented pure in `V2L.roles.courseStatus`: `approval_status==='pending'` «بانتظار الاعتماد» amber · `rejected` «مرفوضة» red · `!is_active&&archived_at` «مؤرشفة» grey · `is_active` «منشورة» green · else «مسودة» grey;
    - meta: `instructor_name||'بلا مدرّب'` · type (`recorded_paid` «مسجّلة مدفوعة», `recorded_free` «مسجّلة مجانية», `live_upcoming` «مباشرة», else as is) · price (`price_amount>0` ⇒ `moneyText(price_amount, price_currency)`, else `type==='recorded_free'` ⇒ «مجانية», else «—») · «{total_enrolled} مسجّل» · lessons («{story.lessons||lesson_count} درس»).
  - Chips: «الكل» · «منشورة» · «بانتظار الاعتماد» · «مسودات».
  - **Removed vs old:** the «Titch» source emoji tag (technical wording).
- Tab «كل السجلات»: see §4.10.

**«الموضوعات»** (`topics`):
- Tab «الموضوعات» (source `topics`):
  - chips by status:
    - «الكل»
    - «منشورة» (`published`)
    - «على البورد» (`open`)
    - «قيد العمل» (`merged`)
    - «مقترحة من الأعضاء» (`pending_review`)
    - «مسودات» (`draft`)
    - «مرفوضة» (`rejected`)
    - «مؤرشفة» (`archived`)
  - Row:
    - title (or `question`);
    - chip with the same Arabic status words as `topStatusAr`;
    - meta: source (`news` «خبر», `expert` «خبير», `idea` «فكرة», `human` «عضو») · `category` · «{comments} تعليق · {reactions} تفاعل» · `dateText(created_at||published_at)`.
    - Tap ⇒ expand `summary` (escaped text, max 600 chars, then «…»).
- Tab «دليل الاستخدام» = the `tutorials` view below (only if `tutorials` is allowed).
- Tab «كل السجلات»: §4.10.

**«دليل الاستخدام»** (`tutorials`, source `tutorials`):
- Grouped by `section` (heading 18 px; empty section ⇒ «عام»), sorted by `order`.
- Row: title + chip «منشور» green / «مسودة» grey.
- Tap ⇒ expand the body as escaped text with line breaks kept, plus `.v2r-link` «شاهد الشرح» ⇒ `video_url` (new tab) if present.

### 4.10 «كل السجلات» (employee only, last tab of «الدورات» and «الموضوعات»)
Why it stays: the old employee screens also show the founder's decision queues (program requests, trainer applications, price offers, live schedules, news, comments). They are read-only for staff, and rebuilding them is the courses/content sections' job. Dropping them would change the data the employee sees.

How:
- `.app` gets `v2r-legacy`.
- roles.js calls the **original** `viewCourses(#view)` / `viewTopics(#view)` (captured before patching).
- Today's `.ro` keeps every `.acts` hidden.
- Restyle in `roles.css`, scoped `.app.v2-roles.v2r-legacy #view`:
  - `.policy` ⇒ paper2 note with a wine inline border, 14 px;
  - `.kpis`/`.kpi` ⇒ the `.v2r-num` look (white, radius 18, top 5 px border, Cairo 28 px numbers);
  - `.panel` ⇒ white, radius 18, `--line` border;
  - `.ph h3` ⇒ Cairo 18 px;
  - `.tabbar .tab` ⇒ `.v2c-tab` look (48 px, wine underline when `.on`, horizontal scroll inside the bar only);
  - `.chip` ⇒ 44 px pills;
  - `.row` ⇒ min-height 56, 14 px meta;
  - `.status` ⇒ `.v2r-chip` tones;
  - `.drawer` ⇒ white card radius 18;
  - `.inboxwrap` ⇒ one column below 1100 px;
  - inline `font-size:11px`/`12px` overridden to ≥13 px.
- No horizontal page scroll at 390 px.
- A one-line note above the old screen (`.v2r-note`): «كل السجلات كما كانت، للاطلاع فقط.»
- «الأعضاء» and «دليل الاستخدام» have **no** «كل السجلات»: the new screens cover all their data.

### 4.11 Removed old elements (all roles)
- `#roBanner` with emojis (⚠ 🎓 💼 ⏳) and the phrase «mirror من الداش بورد». It is hidden by the shell CSS, and its job moves to the user block's role line and the header line.
- The old `.placeholder` look of `v_pending`.

---

## 5. New server routes (`backend/v2_roles_routes.py`)

### 5.1 `GET /api/v2/roles/config`
- `@token_required` only: any active signed-in account. An unauthenticated request ⇒ 401 (existing behaviour).
- Reply: `{"enabled": _v2_enabled(), "role": reported_role(g.user), "linked": bool(entitlement_key(g.user))}`, with `Cache-Control: no-store`.
- `linked` is the same key every money filter uses (`linked_to_name`, admin-set). It is a boolean only; the name itself is never sent.

### 5.2 `POST /api/v2/roles/withdraw`
- `@token_required` + `@roles_required('investor','trainer')`.
- Order of checks (no write before all pass):
  1. Switch closed ⇒ 404 `{"error":"غير متاح"}`.
  2. `body.confirmed is not True` (strict boolean) ⇒ 400 `{"error": V2_CONFIRM_AR}`.
  3. `amount` not a number >0, or `currency` not exactly `"EGP"` ⇒ 400 `{"error":"اكتب مبلغًا صحيحًا"}`.
- Then **delegate**: `return app.view_functions['request_withdrawal']()`.
  - It runs in the same request context, so it re-reads the same JSON (`amount`, `currency`).
  - Its `token_required` re-checks the token.
  - All money rules stay in one place: wallet key, minimum 50 USD, ≤ balance, row creation, `sync_wallet`.
- On 2xx, also `_audit('roles.withdraw', target=<new id>, meta={'amount': amount, 'currency': 'EGP'})`.
- Every reply gets `no-store`.
- `by` and actor are the token's user (the delegated function already keys by `g.user`). Nothing from the body names a person.
- No platform call and no network: the wallet is the dashboard's SQLite.

No other new route. Every other screen reads existing endpoints.

---

## 6. «الخطوة التالية» lines (facts only, at most one per screen, never branded «العقل»)

Each line is computed by a pure helper (§7) and is `null` when its source is not `ready`.

### 6.1 Trainer home
1. `payouts` ready and Σ due >0 ⇒ «لك {fmt} جنيه مستحقة في دفتر الإدارة ولم تُحوَّل بعد.» + link «التفاصيل» ⇒ `go('t_earnings')`.
2. Else `courses` ready and length 0 and `me.linked` ⇒ «لا توجد دورات مربوطة بحسابك بعد. تواصل مع الإدارة لربط دوراتك.»
3. Else none.

### 6.2 Investor home
1. `wallet` ready, linked, `pending_withdrawals>0` ⇒ «طلب سحب بقيمة {moneyText(x,'USD')} قيد المراجعة لدى الإدارة.»
2. Else `balance_egp>0` ⇒ «لك {fmt} جنيه متاحة للسحب.» + the withdraw button (same as §4.4 item 5; not drawn twice: the line takes the button and the card row omits it).
3. Else `opps` ready and the open count >0 ⇒ «{n} فرص استثمار مفتوحة الآن.» + link «اعرضها» ⇒ `go('i_market')`.
4. Else none.

### 6.3 Employee
| Screen | Line | Basis |
|---|---|---|
| «الأعضاء» | «{n} طلبات تدريب قيد المراجعة لدى الإدارة.» | `trainer_status==='pending'` count >0 |
| «الدورات» | «{n} دورات بانتظار اعتماد الإدارة.» | `approval_status==='pending'` count >0 |
| «الموضوعات» | «{n} موضوعات مقترحة من الأعضاء تنتظر المراجعة.» | `status==='pending_review'` count >0 |

There are no buttons: staff only follow up.

### 6.4 Viewer
None.

---

## 7. Pure helpers (`V2L.roles`, appended to `v2-logic.js`)

A separate IIFE at the end of the file:
`(function(root){ var L=root.V2L; if(!L) return; … L.roles={…}; })(typeof window!=='undefined'?window:globalThis);`

`module.exports` is the same object, so `v2_apply.js` can call `roles.trainerView`. No DOM, no clock: `now` is passed in.

| Function | Input | Output |
|---|---|---|
| `NAV` | constant | the label/photo/header map of §2.1 |
| `navFor(role, base, perms)` | `ROLE_NAV[role]`, the saved map (object or JSON string) | ordered `[{id,label,img,desc}]`. The same intersection rule as `roleNavFor` (no entry ⇒ base). |
| `trainerView(src, now)` | `{me, courses, payouts}`, each `{state, data}` | `{linked, nums:{courses, students, due}, rows:[…], next}`. Each num is `null` when its source is not ready. |
| `trainerEarnings(src, now)` | `{payouts, wallet, active}` | `{due, paid, last30, list:[{title,date,amountText,chip}], wallet: walletView(...)}`. `waived` is excluded from sums. |
| `courseRow(c)` | `/api/courses` row | `{title, chip:{t,tone}, meta, share}` (share text per §4.2) |
| `walletView(w)` | wallet or `null` | `null` (failed) · `{linked:false}` (`id==null`) · `{linked:true, balanceEgp, investedEgp, returnsEgp, pendingUsdText, level, canWithdraw, minEgp}` |
| `investorNext(src)` | `{wallet, opps}` | the line of §6.2 or `null` |
| `oppCard(o)` | opportunity | `{title, trainer, students, fundedText, targetText, pct, roiText, minText, start, end, chip}` (USD everywhere) |
| `investmentRow(x, tab)` | investment | per §4.6 |
| `withdrawCheck(input, wallet)` | raw text, wallet | `{ok, amount}` or `{ok:false, error:'اكتب مبلغًا صحيحًا لا يزيد على رصيدك المتاح.'}`. Accepts Arabic digits. |
| `peopleFilter(rows, chip, q)` · `peopleCounts(rows)` | bridge users | filtered rows · chip counts |
| `courseStatus(c)` | bridge course | `{t, tone}` (the §4.9 rule) |
| `topicRow(t)` · `topicCounts(rows)` | bridge topic | per §4.9 |
| `tutorialGroups(rows)` | tutorials | `[{section, items:[…]}]` sorted |
| `staffNext(screen, src)` | | the §6.3 line or `null` |

---

## 8. States matrix (every screen)

| State | What shows |
|---|---|
| switch closed / reply late (>3 s) / error | today's screens, untouched |
| source `loading` | numbers «…», lists `.v2r-load` «…جارٍ التحميل» |
| source `error` | strip «تعذّر جلب {اسم المصدر}…» + «أعد المحاولة»; numbers «غير متاح بعد»; no `٠` |
| source ready, empty | the exact empty text of each screen |
| unlinked account | amber notice (§4.1 / §4.4); money numbers «غير متاح بعد» |
| 403 by role permissions | strip with the server's Arabic text |

Source names for the strip:
- `courses` «دوراتك»
- `payouts` «مستحقاتك»
- `wallet` «محفظتك»
- `badges` «الشارات»
- `active`/`history` «استثماراتك»
- `opps` «فرص الاستثمار»
- `people` «الأعضاء»
- `pcourses` «الدورات»
- `topics` «الموضوعات»
- `tutorials` «دليل الاستخدام»

---

## 9. Tests (`backend/tests/test_v2s_roles.py`)

Zero network: the Flask test client only. The employee bridge calls are never made in pytest. Node runs the pure helpers through `v2_node.logic('roles.<fn>', …)`. Seed SQLite users: admin, employee, trainer (linked `linked_to_name='م. سارة'`), trainer unlinked, investor linked, investor unlinked, viewer, and pending-but-active. Seed: Course rows (`trainer_name='م. سارة'`, one with `revenue_split` via payout/percent), Payout rows (accrued, paid, waived, one 40 days old), an InvestmentOpportunity, Investments (active + completed with `actual_return`), and a wallet.

**A. Routes**
1. `GET /api/v2/roles/config`:
   - each role ⇒ 200 with the right `role`;
   - `enabled` follows `DASH_V2_ENABLED` (true/false/missing);
   - `linked` true/false by `linked_to_name`;
   - the body never contains `linked_to_name` text;
   - `Cache-Control: no-store`;
   - no token ⇒ 401.
2. `POST /api/v2/roles/withdraw`:
   - switch off ⇒ 404 and **zero** `WithdrawalRequest` rows;
   - admin/employee/viewer ⇒ 403;
   - `confirmed` missing / `"true"` / `1` ⇒ 400 `V2_CONFIRM_AR`, zero rows;
   - `currency:'USD'` ⇒ 400; `amount` 0 / negative / text ⇒ 400;
   - unlinked investor ⇒ 400 «هذا الحساب غير مرتبط بمحفظة مستثمر»;
   - below 50 USD ⇒ 400 «الحد الأدنى…»; above balance ⇒ 400 «الرصيد المتاح لا يكفي»;
   - happy path (investor, and a linked trainer) ⇒ 200, exactly one row (`amount` = EGP/rate), an `AuditLog` row `roles.withdraw`, `no-store`;
   - a second identical request for the full balance ⇒ 400 (balance reduced by the pending one).
3. The delegated function stays the only rule: assert that `v2_roles_routes.py` contains no `50` minimum and no `WithdrawalRequest(` (grep).

**B. Wiring (static)**
4. `index.html` has exactly one `<!-- v2 sections begin -->` … `end` block, and the roles lines are inside it in alphabetical order.
5. `index.html` still defines `function renderView(`, `function setRole(`, `function go(`, `function roleNavFor(` (patch targets exist).
6. `app.py` has one `register(app)   # v2s:roles` line directly above `# ---- v2 section routes end`.
7. `backend/Dockerfile` copies `v2_*_routes.py`.
8. `roles.css` rules are all scoped (`.app.v2-roles`, `.v2r-`, or inside `.app.v2-roles.v2r-legacy`). Regex: no top-level `.kpi`, `.panel`, `.row`, `body`, `html` selectors.
9. Visible strings in `roles.js` contain none of: «يقوّم», «AI», «ماركت», «mirror», emojis, «ذكاء» at the start of any heading, «العقل».

**C. Pure logic (node)**
10. `trainerView`:
    - nums are `null` per failed source (never 0);
    - due = accrued+pending; `waived` is ignored;
    - `last30` uses the passed `now` (a 40-day-old row is excluded);
    - share text «غير محدد بعد» when the percent is 0/missing.
11. `walletView`:
    - `null` ⇒ failed; `id:null` ⇒ `{linked:false}`;
    - `canWithdraw` only when `balance_egp>0`;
    - `minEgp = round(50*balance_egp/balance)`, and `null` when `balance==0`.
12. `oppCard` formats every amount as «دولار». The chip map is complete, and an unknown status falls back to «غير معروفة».
13. `investmentRow`: roi «غير متاح بعد» when `course_title` is empty; the history row shows the actual return.
14. `withdrawCheck`: Arabic digits accepted; above floor(balance) is rejected; 0 is rejected; decimals are rejected.
15. `navFor`:
    - perms as an object and as a JSON string;
    - a role missing from perms ⇒ full base;
    - perms that remove `topics` ⇒ no topics item;
    - bad JSON ⇒ base.
16. `courseStatus`, `topicCounts`, `peopleFilter` (search on name/email/phone, case-insensitive; chips), `tutorialGroups` (order, «عام» for empty section).
17. `investorNext` / `staffNext`: each rule fires only on a ready source; the priority order is as in §6.

---

## 10. Shots (`backend/tests/uiharness/v2_shots_roles.py`)

Run: `cd backend && python3 -B tests/uiharness/v2_shots_roles.py ../docs/v2/final/shots-roles`. It imports `Harness`, `DASH`, `shot` helpers and `Browsers` from `v2_shots.py` / `ef_route_harness.py` without editing them.

Setup:
- `os.environ['DASH_V2_ENABLED']='true'`.
- A `RolesPlatform(v2fx.V2Platform)` subclass whose `_extra` adds `GET /api/tutorials` (three rows, two sections, one draft).
- Seed the trainer/investor/viewer users and SQLite rows as in §9.
- Mint JWTs with `app.config['SECRET_KEY']` and add them to `h.tokens['trainer'|'investor'|'viewer'|'trainer_unlinked'|'investor_unlinked']`.
- Viewports: desktop 1440×900 (`d`), tablet 820×1180 (`t`), phone 390×844 (`m`, mobile flags).

Shots (each at d/t/m):
1. `trainer-home` · `trainer-home-unlinked` · `trainer-home-failed` (Playwright `ctx.route('**/api/payouts', fulfill 500)`, registered after the harness route so it wins, in-process) · `trainer-courses` · `trainer-courses-empty` · `trainer-earnings` (with wallet Part B) · `trainer-menu-sheet` (t, m only).
2. `investor-home` · `investor-home-unlinked` · `investor-withdraw-form` · `investor-withdraw-review` · `investor-withdraw-error` (amount below the minimum ⇒ the server's message) · `investor-withdraw-done` (toast + reduced balance) · `investor-market` · `investor-market-failed` · `investor-invest-active` · `investor-invest-history`.
3. `staff-people` · `staff-people-open` (one row expanded) · `staff-courses` · `staff-courses-legacy` («كل السجلات») · `staff-topics` · `staff-topics-legacy` · `staff-tutorials` · `staff-bell` (panel open).
4. `viewer`.
5. `switch-off-trainer`, `switch-off-investor`, `switch-off-staff`: run with `DASH_V2_ENABLED` unset; assert the old rail `.rail` is visible and `#v2rSide` does not exist (proof nothing changed).

The script **fails** if any of the following happens:
- any request leaves `DASH` (besides Google Fonts);
- horizontal scroll at any viewport (`document.documentElement.scrollWidth > innerWidth`);
- any visible clickable target is <44 px high, or any `.v2r-btn1/.v2r-btn2` is <52 px on phone;
- visible text matches `\b(undefined|null|NaN)\b`, or a money/number card shows `٠`/`0` where its source failed or the account is unlinked (expected «غير متاح بعد»);
- the old rail, `#roBanner` or an emoji is visible while the switch is on;
- a POST to `/api/v2/roles/withdraw` lacks `confirmed:true`, or `/api/investor/withdraw` is called directly;
- `/api/investment-opportunities` is requested by the trainer session;
- the admin session (one `admin-home` shot) shows any `v2r-` element.

The script prints the JSON report (shots, blocked, problems) like `v2_shots.py`, and exits 1 on any problem.

---

## 11. Platform needs

**None for this round.** Every screen reads existing dashboard routes (SQLite ledger + existing bridges), and the one new write delegates to an existing dashboard route.

Optional, **not built, not required**. Listed because the trainer sees two money pictures:
- **«مستحق لك»** here is the admin's ledger (`/api/payouts`).
- **Platform course sales** live in the platform's wallet («لوحتي» on the platform).

To show one number later, the platform would need:
`GET /api/bridge/trainer-earnings?email=<email>` ⇒ `{"currency_totals":[{"currency":"EGP","due":int,"paid":int,"in_escrow":int}], "updated_at": iso}` (secret-guarded, read-only, `null` totals when unknown). Until then the screen says where its numbers come from, and links to the platform panel.

---

## 12. Open founder decisions (not built; the spec stays honest without them)

1. **«أريد الاستثمار»:** today the investor cannot ask to invest from the dashboard (the old button was fake). A real request needs one new route plus a decision card in «ابدأ القرارات». Until he decides, the card says «للمشاركة في فرصة، تواصل مع الإدارة.»
2. **Trainer payout request:** course payouts are settled by the admin from the ledger. No request button is shown.
3. `DASHBOARD-MAP-2026-10-30.md` §364 once suggested deleting the trainer/investor/viewer panels («المنصة فيها لوحتها»). This round follows the latest order instead: no old look anywhere, and nothing removed. Deleting them stays a one-line decision later (empty `ROLE_NAV` entries ⇒ the viewer card).

---

## 13. shared_edits (for the merge report)
- `backend/Dockerfile`: `COPY app.py v2_*_routes.py ./` (every section with a route file needs it).
- `backend/app.py`: the one `register` line and, if missing, the marker `# ---- v2 section routes end`.
- `dashboard-cloud/index.html`: the sections block (created if missing) with the two roles lines.
- `dashboard-cloud/v2-logic.js`: the appended `// ===== v2s:roles =====` block only.

## 14. Done means
- With the switch on, every non-admin login lands in the new look at 1440, 820 and 390:
  - the trainer (3 screens), the investor (3 screens), staff (4 screens, with «كل السجلات» restyled in two of them), and the viewer card;
  - no old rail, no emoji banner, no fake button, no false `0`, no `ج` on dollar amounts.
- With the switch off, every role is byte-identical to today.
- The admin path is untouched (the D1/D1B/D2/D3 test files still pass).
- `test_v2s_roles.py` is green, and the shots script exits 0 with every shot in `docs/v2/final/shots-roles/`.
