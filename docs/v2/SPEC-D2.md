# D2: Tickets with a timer in «ملفات الخبراء» and «النزاعات والاستردادات» + one page per person

**Approved concept:** https://claude.ai/artifact/7okXZj6NRzm4KMZvW6nUBa, boards «ب٤ · جوه القسم: تذاكر بعدّاد زي المطبخ» and «ب٥ · الشخص في مكان واحد بكل أدواره».
**Founder:** approved the concept and the plan (2026-10-30). He doesn't want any part to look like the old version («نعيد هيكلة الموضوع كله»).
**Branch:** `dash-v2-d1` (after `31862de`). Everything sits behind `DASH_V2_ENABLED`, and the old behaviour is unchanged when it's off.

## 1) «ملفات الخبراء» › «الملفات» = a ticket board (instead of the old inbox inside the tab)
- **Four columns:**
  1. **متأخر** (red): late or overdue for pickup.
  2. **ينتظر مراجعتك** (amber): a first opinion under review, a case price quote, or anything else that needs the founder's decision.
  3. **عند الخبراء** (green): with an expert and still within the deadline. Show the 3 closest to their deadline, then «و N في موعدها».
  4. **خلص اليوم** (dimmed): delivered today.
- **The data:** use the same inbox rows the old screen uses (`EP.data.inbox`, the `expert_file` lanes) plus the `ops/queue` counts. No new collection. Classification goes in a pure function `v2Tickets(rows)` in `v2-logic.js`.
- **The ticket:** a coloured strip at the top with the type and the timer («متأخر ٢ س» / «باقٍ ٥ س» / «منذ ٣٥ د»). Under it:
  - client ← expert;
  - one line from the brain, from the same `v2Card` (the suggestion and reason);
  - one main button from the same card (send it / move it / open and review).
- **The timer updates every minute** without reloading.
- **Tapping the ticket** opens the existing drawer for the same row (as D1 does with «غيّر/افتح»).
- **On mobile:** the columns become a horizontal strip of 4 buttons with counts. One column shows at a time, with no sideways page scroll.
- **Header line:** «التوزيع التلقائي يعمل · وزّع N ملفًا اليوم» if the auto-assign switch is on (from `ops/queue`).
- **Section tabs:** الملفات (the board) · الخبراء (the existing screen) · «كل الملفات» = the old inbox filtered to files, for anyone who needs the full old list.

## 2) «النزاعات والاستردادات» › «النزاعات» = tickets as well
- **Columns:**
  1. **نزاعات مفتوحة:** file, consultation, case milestone.
  2. **استردادات تنتظرك:** unactivated / manual refunds where a list exists. If there's only a count, show a card with the count and «افتح».
  3. **استشارات قديمة:** legacy.
- **Each ticket shows:**
  - the amount and currency;
  - the two parties;
  - how long it's been open;
  - the reason, written in standard Arabic from its fields, never raw platform text;
  - one button «افتح وقرّر», which opens the existing drawer. **No money decision from the ticket itself.**
- **The «الضمان» tab** stays as it is.

## 3) The single person page
- **Route:** `#s/people/person/<email-key>`. It opens from:
  - any name in a ticket or decision card;
  - the users list (clicking the name);
  - a new «ابحث عن شخص» search box at the top of the «الناس والدعوات» section.

  The search runs through the existing users endpoint/loader, no new endpoint unless strictly necessary.
- **New server endpoint** `GET /api/v2/person?email=` (admin only). It gathers data from **existing** sources through `_platform_proxy`/the existing loaders. **Never invent** a field. Anything without a source returns `null` and the screen shows «غير متاح بعد», never 0.
  - **identity:** name, photo, country, roles (expert/trainer/learner/visitor) from the user row, join date, `invited_by`.
  - **as an expert:** count of their files and the latest 3, from the inbox rows / expert files if there's a source by email.
  - **as a trainer:** their courses and their status.
  - **money:** what they're owed / pending payouts (from wallet payouts by email), what's been paid out.
  - **as a learner:** their courses (enrollments) if available.
  - **books:** their purchases if available (otherwise «غير متاح بعد»).
  - **log:** the latest events available (join, invite opened, file assigned, payout).
- **The page** follows the concept's «الشخص في مكان واحد» board:
  - a header with the photo, name, role chips, and one line «انضم في … بدعوة من …»;
  - buttons «راسله» (the existing message path, if one exists) and «أوقف مؤقتًا» **only if** a permissions/stop endpoint exists today, otherwise it isn't shown;
  - 4 cards: ملفاته · دوراته · فلوسه · ما تعلّمه;
  - then the log.
- **Privacy:** admin only, and nothing from the person's data gets logged.

## 4) Shared rules
- Plain standard Arabic, gender-neutral («صاحب الطلب», not he/she), no technical terms.
- The brand colours.
- Targets ≥ 44px (52px for buttons on mobile).
- No horizontal page scroll at 390.
- **No new decision path:** buttons call the same functions D1 uses.
- **Money:** any money button stays in the drawer with its existing confirmation.

## 5) Tests and screenshots
- **node:**
  - `v2Tickets` places each type in its correct column, and the timer text is correct;
  - an unknown row type doesn't drop silently: it goes to «ينتظر مراجعتك» with a generic line;
  - the person aggregation turns a source failure into `null`, not 0.
- **pytest for `/api/v2/person`:**
  - admin only;
  - every source proxied;
  - a failed source gives `null`;
  - no fake email in the response.
- **Screenshots** with `v2_shots.py d2` at d/t/m:
  1. the files board with all four columns full;
  2. the mobile board on each column;
  3. a ticket opening the drawer;
  4. the disputes board;
  5. a full person page;
  6. a person page with sources unavailable;
  7. people search.

  Plus a check that the D1/D1-B screenshots weren't broken (rerun `d1b`).
- The old suite file by file. The main session reruns the port tests outside the sandbox.
