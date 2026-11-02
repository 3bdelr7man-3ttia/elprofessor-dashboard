# Item prices — every guide gets its own price in «أسعار الكتب»

**Founder request (2026-11-02):** guides are not all one price. Show every guide on its own in the dashboard, and let the founder set its price; books too.
**Branch:** `dash-item-prices` (from `main@d4c7dc1`). Pairs with the platform branch `pillars-item-prices` (`main@91343ad`).
No mock first: the founder asked for it directly, in the same shape as the existing price table.

## Contract with the platform (fixed by the parent)

| Call | Behaviour |
|---|---|
| `GET /api/bridge/prices/book` | Rows for every book (`group:"book"`), then the general guides row (`id:"_guides"`, `group:"guides_general"`, title «السعر العام للأدلّة»), then one row per guide: `{id, title, group:"guide", has_own, uses_general, visible, min_price, updated_at}`. Countries and currencies unchanged. |
| `GET/PUT /api/bridge/prices/book/<guide slug>` | Same as books (`rev`, `confirmed:true` strict, `by`, `note`). A guide with no own price answers an empty form (`rev` 0). |
| `DELETE /api/bridge/prices/book/<guide slug>` | «ارجع للسعر العام». Body `{by, confirmed:true, note?, rev?}`. Removes the guide's own price. Books and `_guides` answer 409. |

Resolution lives on the platform only: a guide uses its own doc when it has a price for the version asked, else the general doc. The dashboard never computes a sale price.

## Dashboard backend (`backend/app.py`)

- **New** `DELETE /api/v2/prices/<kind>/<item_id>`, admin only, behind `DASH_V2_ENABLED` (off = 404 with no platform call), `Cache-Control: no-store`.
  - `kind` must be `book` (`course` and others = 404 before any call). `item_id` passes the same id pattern as PUT.
  - `confirmed` must be exactly `true` (else 400 before any call).
  - The platform body is built from a whitelist: `{confirmed:true, note (≤300), rev (whole number only), by}`. `by` is the token's email; anything the browser sends as `by` is dropped.
  - One call, no retry. A lost reply (500/502/503/504) = «ما وصلناش رد» (502 `no_reply:true`) plus an audit line `prices.no_reply`, never a refusal. The platform's own refusals (409/422/404) pass through with their Arabic message. 401/403 from the shared key become 502 (a bad link, not a logout).
  - Audit `prices.reset_to_general` only on success: target `book:<id>`, meta `{kind, rev}`.
- **List passthrough.** `GET /api/v2/prices/book` already forwards the body untouched, so `group`, `has_own`, `uses_general` arrive as the platform sent them (tested).
- **Edit.** `PUT` for a guide id / `_guides` is the existing route and audit (`prices.update`, target `book:<id>`); no change.

## Dashboard screen (`dashboard-cloud/v2-logic.js`, `v2-d3.js`, `v2-d3.css`)

«الفلوس ‹ الأسعار»: the books card becomes the books and guides card.

- **Toolbar** (only when the list has guide rows; a legacy list with no `group` renders exactly as before): a search box (`type=search`, 48px, 16px font) and three chips: «الكل»، «الكتب»، «الأدلّة» with counts: the «الأدلّة» count is the guides only (same number as the section below; the general row is not counted in it). Price lines join countries with «،», never «·». Filter and search live in memory only.
- **Three groups:** «الكتب» (each book), «السعر العام للأدلّة» (one row, hint «يُباع به كل دليل ليس له سعر خاص»), «الأدلّة» (each guide).
  - «الأدلّة» chip shows the general row plus the guides; «الكتب» chip shows books only.
  - Search matches titles, ignoring diacritics, hamza forms, ى/ي, ة/ه and digit script.
- **Guide row:** title, badge «سعر خاص» or «يأخذ السعر العام», «ظاهر للناس: نعم/لا», effective minimum price per country (a guide on the general price shows the general minimum; the platform may send it or the screen reads it from the general row), «عدّل»; a guide with its own price also shows «ارجع للسعر العام».
- **Editing any row** opens the same per-country sheet as books, then «راجع التغيير» (قبل ⇒ بعد) then «أكّد التعديل».
  - A guide on the general price starts with empty cells, a line saying it takes the general price now, and a quiet button «ابدأ من السعر العام» that fills the cells from the general price (the review still shows every change). «ظاهر للناس» starts from what the guide shows today, so saving never hides a visible guide by accident.
  - The platform's refusals (for example a visible item needs a price in «باقي البلاد») are shown as it words them.
- **«ارجع للسعر العام»:** one sheet that shows the review (قبل ⇒ بعد: first line «نوع السعر: سعر خاص ⇒ السعر العام», then every price cell that changes, own price vs general price), an optional note, and «أكّد الرجوع للسعر العام». Nothing is written until that button. Then `DELETE` with `{confirmed:true, note, rev}` and the list reloads: «عاد «…» إلى السعر العام».
- **States:** loading, «غير متاح بعد» with retry when the source fails, «متجر الكتب لم يُفتح بعد» on 404, «لا أعمال بعد» when empty, «لا نتيجة» when search/filter match nothing.
- **Kept identical:** book rows, their editor, courses block, offers approval sheet.
- **Not distorted by guides:** the «متوسط الكتب» used in offer lines and the store rows of the «الكتب» section ignore `group:"guide"` rows.

## Rules this screen obeys

- Plain standard Arabic, gender-neutral, Arabic-Indic digits, no «·» beside a digit, no technical words, no yellow.
- Targets at least 44px (mobile buttons 52px), inputs at least 48px high with 16px font, no horizontal scroll at 1440 or 430.
- One filled wine button per sheet; the dashboard's existing palette tokens only.
- Zero outbound requests: tests and screenshots run against an in-memory platform (`backend/tests/uiharness/item_prices_fixtures.py`).

## Tests

- `backend/tests/test_v2_item_prices.py`: DELETE proxy (roles, switch, confirmed, `by`, whitelist, kind/id, audit, refusals, lost reply, key rejection), list passthrough, guide edit through the book PUT, pure logic in node (groups, view, search, general minimum, reset diff, books average and store rows unaffected), source checks.
- `backend/tests/uiharness/v2_shots_item_prices.py`: the shots harness (below). Must end with `problems: []`.

## Screenshots (`docs/v2/item-prices/shots/`, desktop `d*` 1440 and mobile `m*` 430)

01 list all · 02 guides chip · 03 search · 03b nothing found · 04 guide on the general price (form with «ابدأ من السعر العام») · 05 guide own price: form, review, result · 06 «ارجع للسعر العام» review and result · 07 general row: form, review, result · 08 book edit unchanged: form, review · 09 empty · 10 source down · 11 store closed.

The harness fails on: a target under 44px, an input under 48px or 16px font, horizontal scroll, Latin digits in Arabic text, «·» beside a digit, banned words, `0/null/NaN/undefined` on screen, any write before the confirm click, any write other than the expected one, any outbound request other than Google fonts.

## Known gaps

- The platform half is built by the paired branch; here it is faked per the contract. The exact `min_price` of a guide that takes the general price is read from the row, falling back to the general row.
- The «قبل» side of the reset review compares the own price with the general price cell by cell; a version the guide does not price falls back to the general price on the platform, which the review states only through the first line.

## Safe publish order

1. **Platform first** (`pillars-item-prices`, backend then app). Resolution falls back to the general price, so while no guide has its own price document nothing changes for buyers. The only visible changes: the bridge list gains rows (the general row plus one per guide), `DELETE` exists, and the store shows each guide's own price (the same general price until one is set).
2. **Dashboard second** (`dash-item-prices`: the screen and the `DELETE` proxy). Never before the platform: the screen reads `group`, `has_own` and `uses_general`, and «ارجع للسعر العام» needs the platform `DELETE`. Against an older platform the screen renders exactly as before (no toolbar, no sections), and a reset the platform cannot perform is refused and shown as an error, with nothing written. `DASH_V2_ENABLED` stays the switch: off = the new route answers 404 with no platform call.
3. **The founder sets per-guide prices** in «أسعار الكتب» (عدّل, then راجع التغيير, then أكّد التعديل). Each save is audited as `prices.update`; each return to the general price as `prices.reset_to_general`.
4. **Verify one guide (no real payment).** Open one guide with its own price and one without: the cover on the market shelf, the buy card in the reader and the store page must all show that guide's number (own price, or the general price). The checkout quote on the store page uses the same server-side amount. Do not press buy. The platform `catalog_prices_log` must show one line per change.

## Rollback

- **A wrong guide price:** «ارجع للسعر العام» on that guide (or edit it again). The platform keeps a `removed` line with the old prices; the audit log keeps `prices.reset_to_general`.
- **The dashboard:** revert `dash-item-prices`. No dashboard data changes shape (prices live on the platform), so nothing needs migrating; the audit lines already written stay.
- **The platform:** revert to `91343ad`. Guide documents written meanwhile stay in the database and are ignored by the old code (it reads only the general document), so every guide goes back to the general price.
- The money path (`payments.py`) is not touched by either branch, so there is nothing to roll back there.

## Results

Full backend suite (`cd backend && python3 -B -m pytest -q -p no:cacheprovider`, sandbox):

| | Result |
|---|---|
| BEFORE (clean tree, earlier report) | 1 failed, 4196 passed, 3 skipped, 109 errors |
| AFTER (this tree) | **1 failed, 4448 passed, 3 skipped, 109 errors** (2009 s) |

- The one failure is the known `test_dash_ia_ui` truncation test; the 109 errors are the known port-binding ones (`test_dash_company_badges` 43, `test_dash_finance_sources` 12, `test_dash_ia_ui` 54), identical to the baseline file by file.
- Collected tests: 4561 now = 4540 at `d4c7dc1` + 21 new (`test_v2_item_prices.py`). The earlier BEFORE line adds up to only 4309, so it did not run every test; the AFTER run accounts for all 4561. A second BEFORE measured from a `git archive` of `d4c7dc1` is not clean either (40 extra failures, all `FileNotFoundError` because the archive lacked the repo-root Dockerfiles and docs those tests read), so it is not used.
- A previous AFTER run showed 2 failed and 125 errors; that was a full disk (`ENOSPC`) and did not repeat with 2.4 GB free.
- Shots harness (`python3 -B tests/uiharness/v2_shots_item_prices.py ../docs/v2/item-prices/shots`): 40 images (20 desktop `d*` at 1440, 20 mobile `m*` at 430), ends with `"problems": []`, `blocked_inproc: []`, only Google Fonts blocked at the origin.

