# D3 — «الفلوس» على الهيكل الجديد: كل جنيه دخل وفين دلوقتي، والقرارات بزرار

**Approved concept:** https://claude.ai/artifact/7okXZj6NRzm4KMZvW6nUBa (the Money board: «كل جنيه دخل، وأين هو الآن»).
**Founder:** «نعيد هيكلة الموضوع كله… بناءً على التصوّر». No part of the «الفلوس» section may look like the old screen. Old screens survive only as a last «كل السجلات» tab.
**Founder money rules this round obeys:** `_reference/elprofessor-platform-walkthrough/SHARES-2026-10-30.md`.
- The platform's share is never below 35%; the only exception is cases (ladder).
- All percentages live in one editable place.
- Book and course prices come from the dashboard only.
- The minimum payout is a dashboard setting in «الفلوس».
- No refunds on books.

**Two repos, two branches:**
- **Dashboard:** `~/Documents/Playground/elprofessor-dashboard-v2`, branch `dash-v2-d3` (from `dash-release-all@7ebab1b`). Everything new is behind `DASH_V2_ENABLED`; flag off = byte-identical behaviour to today.
- **Platform:** `~/Documents/Playground/elprofessor-wt-d3`, branch `money-d3` (from `release-all@1d78908`). New platform behaviour must default to exactly today's values.

⛔ Stripe in production is LIVE. Nothing in this round moves money by itself.
- Every money button calls an endpoint that already exists (or one added here) with `confirmed: true` plus a reference/reason.
- Every money button goes through the existing confirmation sheet from D1/D2.
- Zero real network calls in tests: no Stripe, Paymob, email, Telegram, or production dashboard/platform.

## A) Platform (branch `money-d3`)

1. **Minimum payout as a setting.**
   - New `services/money_settings.py`, modelled on `services/shares.py` (cache + `reload(db, ttl)` + `update(db, changes, by, expect_rev)`).
   - Storage: `platform_settings` with `_id: "money"`. Log every change in `platform_settings_log` (who, when, before, after).
   - Field: `withdraw_min` (EGP, integer). Default = `EP_POLICY["withdraw"]["min"]` (500), so with no document nothing changes.
   - Allowed range: 50–20000. Anything outside ⇒ 422 with an Arabic message.
   - Readers switch to the setting:
     - `routes/wallet.py` withdraw check;
     - `routes/account.py` copy line;
     - `GET /api/policies` (`withdraw.min`).
   - Keep the existing "withdrawing the full balance is always allowed" rule untouched.
   - Bridge, secret-guarded like other bridges:
     - `GET /api/bridge/settings/money` ⇒ `{withdraw_min, rev, updated_at, updated_by, history[≤20]}`.
     - `PUT /api/bridge/settings/money` with body `{withdraw_min, by, confirmed: StrictBool, rev?}`. Without `confirmed: true` ⇒ 422. A stale `rev` ⇒ 409.
2. **The shares table, readable and editable from one place.**
   - `GET /api/bridge/shares` ⇒ `services.shares.current_shares()` after `reload_shares(db)`, plus `version` and the last 20 log rows.
   - `PUT /api/bridge/shares` with body `{changes, by, confirmed: StrictBool, version}` ⇒ `update_shares`.
     - `SharesError` ⇒ 422 (message as is).
     - `SharesConflict` ⇒ 409.
   - No new validation logic: the floors live in `shares.validate_shares`.
3. **Ad balances, overview.**
   - `GET /api/bridge/ads-ledger` (no owner) ⇒ one row per `(owner_kind, owner_id)` with:
     - balance per currency;
     - last entry date;
     - owner email if stored;
     - title (books via `BM.known_books`, courses from the course row if it exists, otherwise empty).
   - Read only. The existing per-book route stays.
4. **Stuck payments.**
   - `GET /api/bridge/payments/stuck` ⇒ card orders still `pending` more than 2 hours after creation, plus orders `paid` whose fulfilment never landed (if the payments module records that; if not, only the first kind).
   - Fields:
     - `order_id`, `kind`, `title`, `amount`, `currency`, `created_at`;
     - buyer email and name;
     - `age_hours`;
     - `provider` (stripe/paymob/manual).
   - Read only, max 200 rows, oldest first. No provider calls.
5. **Income by service.**
   - Only if the dashboard's own `Revenue.source` cannot separate «ملفات الخبراء / الدورات / الكتب / أخرى»: add `GET /api/bridge/income/by-service?month=YYYY-MM`.
     - It sums `payments` with `status` paid by `kind` and currency.
     - It excludes `ads_deposit` and refunds/reversals.
   - Otherwise skip it and use the dashboard data. Decide by reading `metrics_finance_event` and the `kind` values the platform sends, and write the decision in STATUS-D3.
6. **Tests:** new `backend/tests/test_money_d3.py`.
   - Setting defaults equal today's numbers.
   - The range is enforced.
   - `confirmed` is required.
   - 409 on a stale rev.
   - `withdraw` uses the new value.
   - The "full balance" exception still holds.
   - The shares bridge refuses a change that breaks the 35% floor.
   - Ads overview and stuck-payments shapes.
   - All new bridges reject a wrong or missing secret.
   - Run the full backend suite with the command in the main CLAUDE.md. Only the known failures are allowed:
     - `test_payments_native` SSRF;
     - `test_telegram_dark_buttons`;
     - the r13 flake.

## B) Dashboard (branch `dash-v2-d3`)

**Proxies** (admin only, `no-store`, `_platform_proxy`):
- `GET /api/v2/money/settings`, `PUT /api/v2/money/settings` (requires `confirmed:true`; `by` = the admin's email from the token, never from the body; `_audit`).
- `GET /api/v2/shares`, `PUT /api/v2/shares` (same rules).
- `GET /api/v2/ads-ledger`, `GET /api/v2/ads-ledger/<owner_id>`.
- `GET /api/v2/payments/stuck`.
- `GET /api/v2/refunds/pending` (→ `/api/bridge/refunds/pending`).
- `GET/PUT /api/v2/prices/<kind>[/<id>]` (→ `/api/bridge/prices/...`; PUT requires `confirmed:true` and passes `rev`; `kind=course` returns the platform's answer as is when its flag is off).
- `GET /api/v2/book-offers`, `POST /api/v2/book-offers/<id>/approve|reject`, `GET /api/v2/book-requests`, `PATCH /api/v2/book-requests/<id>`.

A failed source ⇒ the screen shows «غير متاح بعد», never 0.

**The «الفلوس» section, new tabs** (in `SECTIONS`, replacing the current three; the old screens move to the last tab):
1. **«نظرة»** (default), following the concept's Money board:
   - A period switch: اليوم / الشهر / السنة.
   - **Four numbers:**
     1. **دخل:** from the dashboard `Revenue` rows of the period (EGP; a foreign-currency sale shows «بعملة أخرى» separately, never converted silently).
     2. **محجوز حتى يُسلَّم العمل:** EscrowSession held.
     3. **مستحق للخبراء والمدرّبين:** pending wallet payouts.
     4. **صافي البروفيسور:** only if an honest source exists, otherwise «غير متاح بعد».
     Each number has a one-line explanation in plain Arabic.
   - **«التحويلات المستحقة»** list (top 5 + «كل التحويلات»):
     - name (→ person page), what it's for, method, amount;
     - one button «سجّل التحويل», which opens the existing settle confirmation (reference required);
     - «ارفض» lives inside the confirmation sheet with a reason.
     - No «حوّل الكل».
   - **«من أين جاء الدخل»:** bars by service (ملفات الخبراء · الدورات · الكتب · أخرى), from Revenue or the A5 bridge.
   - **«استردادات تنتظر قرارك»:** from `refunds/pending` + D2's dispute data. Each row has the brain's suggestion line and one button that opens the existing decision drawer. Books never show a refund button; they show «الكتب لا تُسترد» instead.
2. **«التحويلات»:** all pending payouts as tickets (same `v2Tickets` style with a timer since requested), then settled/rejected this month. The minimum payout is shown at the top with «غيّر».
3. **«الإيصالات والمدفوعات العالقة»:**
   - Column 1: manual receipts awaiting confirmation (the existing confirm/reject flow).
   - Column 2: stuck card payments (A4), read only with «افتح الشخص».
4. **«الأسعار»:** books and courses from the unified prices bridge.
   - One row per work: title, «ظاهر للناس», lowest price per country.
   - «عدّل» opens a focus sheet:
     - versions × countries;
     - the currency of each country written next to the box;
     - the visibility toggle;
     - a note;
     - confirmation that shows exactly what changes (before → after).
   - Courses show «الدورات لسه مقفولة» when the platform returns the flag-off answer.
5. **«النسب والإعدادات»:**
   - The shares table in plain Arabic: «الكتب: صاحب العمل ٦٠٪ · المنصة ٤٠٪»… and «القضايا حسب القيمة» as a small ladder.
   - The minimum payout.
   - «عدّل» on each opens a focus sheet with before → after and a clear warning line when the platform refuses (show its message).
   - The change log at the bottom: who, when, before → after.
6. **«إعلانات الأعمال»:** A3 overview.
   - One row per work: owner, balance, last move.
   - Clicking opens the entries.
   - Read only.
7. **«كل السجلات»:** the old finance screen and old packages screen exactly as today, for anything not covered yet.

**The «الكتب» section** gets a new first tab **«مراجعة العروض»**:
- Queue cards from `book-offers` (in_review): title, owner, requested prices.
- The brain's suggestion: a line built from the offer fields only, e.g. «السعر أعلى من متوسط الكتب في مصر بـ٣٠٪». Facts only, no invented judgement. If there's nothing to compare, no line.
- «اعتمد بالأسعار دي» opens a confirmation with the prices editable.
- «ارفض» requires a reason.

Second tab **«طلبات القرّاء»**: from `book-requests` (groups with counts), with «اعتمد» / «اخفِ». The old «الكتب والأعمال» screen stays as the last tab.

**Board tile and «ابدأ القرارات»:**
- The «الفلوس» tile's alert badge = pending payouts + receipts + stuck payments + refunds pending.
- New decision cards for:
  - a stuck payment (open the person);
  - a book offer awaiting review (the same approve/reject sheet).
  Both use the same `v2Card` path.

**Shared rules (same as D1/D2):**
- Plain standard Arabic, gender-neutral, no technical words, no «يقوّم», nothing starting with AI.
- Brand colours. Targets ≥ 44px (52px buttons on mobile). No horizontal scroll at 390.
- No new decision path: buttons call existing functions.

## C) Tests and shots
- **node** (`test_v2_d3.py` style, as D1/D2 did with pure logic in `v2-logic.js`):
  - number formatting per currency;
  - foreign currency never summed into EGP;
  - a failed source ⇒ `null`;
  - the books «لا تُسترد» rule;
  - the before→after diff builder for prices and shares;
  - badge counts.
- **pytest:**
  - every proxy is admin only;
  - PUTs require `confirmed:true`;
  - `by` comes from the token;
  - `no-store`;
  - a failed source ⇒ `null`.
- **Shots** via `backend/tests/uiharness/v2_shots.py d3` at d/t/m:
  1. نظرة (full);
  2. نظرة with sources down;
  3. a settle confirmation sheet;
  4. التحويلات;
  5. الإيصالات والعالقة;
  6. الأسعار + the edit sheet with before→after;
  7. النسب + a refused edit message;
  8. إعلانات الأعمال;
  9. مراجعة العروض + approve sheet;
  10. mobile of each.

  Rerun `d1b` and `d2` shots to prove nothing broke.
- The old dashboard suite file by file. The main session reruns the port-binding tests (`test_dash_ia_ui`, `test_dash_company_badges`, `test_dash_finance_sources`) outside the sandbox.
- Write `docs/v2/STATUS-D3.md` (what was done, sources found or missing, decisions).

## Out of scope
- Courses share ladder and trainer code (the courses round).
- The case ladder replacing `CASE_PLATFORM_RATE`.
- Removing old consultations.
- Any deploy or push.
