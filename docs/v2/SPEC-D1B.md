# D1-B: Rebuild the dashboard skeleton on the approved concept (with the switch on)

**Founder decision (2026-10-30):** «شايف نفس القائمة الجانبية موجودة بنفس تفاصيلها. احنا عايزين نعيد هيكلة الموضوع كله على الداشبورد دي، بناءً على التصوّر اللي عملناه ويبقى فيها كل التفاصيل».
**Concept:** https://claude.ai/artifact/7okXZj6NRzm4KMZvW6nUBa (the «المعتمد» row)
**Branch:** `dash-v2-d1` (after `8ebfc9b`).

## Goal
With `DASH_V2_ENABLED` on, the founder sees the new dashboard only:
- **No old sidebar at all.** No «الوارد», «الدعوات», «المالية», «الضمان والنزاعات»… as separate items.
- **New shell:** «اللوحة» + the 12 sections of the concept, each with its photo and badge.
- **Inside each section:** a strip of large internal tabs. These hold the existing screens for that section, so **nothing is lost**. Later rounds replace each tab with its new design.
- **With the switch off:** everything stays exactly as it is today, byte for byte.

## 1) Old screens ⇐ new section (tabs)
| New section | Tabs inside (existing screens via their current function/module) |
|---|---|
| **اللوحة** (`home`) | The board + «ابدأ القرارات» (D1) · «كل الوارد» = `inbox` as it is (temporary reference until D2) |
| **ملفات الخبراء** | «الملفات» = `inbox` filtered to the file lanes · «الخبراء» = `team` (experts tab) · «التحقق من الإجابات» (if it has its own screen) |
| **النزاعات والاستردادات** | «النزاعات» = `inbox` filter `t:disputes` · «الضمان» = `escrow` |
| **الدورات والمدرّبون** | «الدورات» = `courses` · «المدرّبون» = `team` (trainers tab) |
| **سوق الخدمات** | «الطلبات» = `market` |
| **الكتب** | «الكتب والأعمال» = `knowledge` (as the pillars session left it) |
| **الناس والدعوات** | «المستخدمون» = `users` · «الدعوات» = `invites` · «الرسائل» = `inbox` filter `t:messages` |
| **الفلوس** | «المالية» = `finance` · «الباقات والأسعار» = `finance` with `finTab='packages'` |
| **المحتوى** | «المحتوى» = `topics` · «دليل الاستخدام» = `topics` with `topicsTab='tutorials'` |
| **التسويق** | «الحملات» = `marketing` |
| **التقارير** | «تحليل الطلب» = `analysis` |
| **العقل** | «سجل اليوم» (the D1 panel) · «المساعدون» = `ai` (temporary until D7) |
| **الشركة ورأس المال** | «الاستثمار والشركاء» = `investment` · «الأهداف والتأسيس» = `targets` · «الإعدادات» = `settings` |

- Each section has a **key** (`files`, `disputes`, `courses`, `market`, `books`, `people`, `money`, `content`, `marketing`, `reports`, `brain`, `company`).
- The address is `#s/<key>[/<tab>]`, so refresh and back work.
- **Old links** (`#inbox`, `#finance`, …) with the switch on land on their section and the right tab, using the same `REDIRECTS` idea. No old link breaks.
- **Telegram/email links** that open old screens follow the same mapping.
- Use the existing functions: `goOps`, `renderView`, and the filter variables. **Don't copy any old screen.** The old screen renders inside the section's content area.

## 2) The new shell (switch on)
- **Desktop ≥ 1180px:** a new light side menu (paper/burgundy, not the old dark navy), ~260px wide:
  - top: the elephant logo + «البروفيسور»;
  - «اللوحة»;
  - the 12 sections, each with a small round photo (thumbnail from `v2/img/<key>.jpg`) + the name + the red/white count badge from the same `v2Tiles` (counted once);
  - bottom: the user + sign out.
- **Narrower than 1180 and mobile:**
  - a slim top bar: logo · the active section name · bell · menu button;
  - the menu button opens a sheet with the 12 sections as photo tiles, 2–3 columns (the same tiles as the board, smaller).
  - No bottom bar.
- **Section header:**
  - a large name + a one-line description from `t.next`;
  - then the tabs, ≥ 44px, burgundy underline on the active one, horizontal scroll on mobile with no page scroll;
  - then the content.
- **The old pieces are hidden with the switch on:** the `.rail` and its groups, `coPin`, and the old page titles where they duplicate the section name.
- **Non-admin roles** (employee and others) keep their current screens as they are. The new shell is for the admin when the switch is on.

## 3) Styling
- Same as D1: burgundy `#9E2B4E`, paper `#FBFAF7`/`#F6F1EA`, ink `#21262E`, red `#C8102E` for overdue counts only, Cairo/IBM Plex.
- The old screens inside the sections keep their internal style for now. A light shared frame goes around them (card on paper background) so the page looks unified.

## 4) Tests and screenshots
- **pytest + node:**
  - `sectionFor(oldModule)` and the map: every old module key (MODULES + REDIRECTS) lands on a section and a tab, with no orphan key.
  - The address `#s/x/y` round-trips.
  - With the switch off, `renderNav` and `MODULES` don't change.
  - The badges come from `v2Tiles` itself.
- **Screenshots** (`v2_shots.py`): d/m for:
  1. the board in the new shell;
  2. the mobile menu open;
  3. one section from each group with its tabs (files, money, people, company);
  4. an old link `#finance` landing on الفلوس;
  5. switch off.

  ⛔ Make sure **there is no trace of the old sidebar** in any screenshot with the switch on.
- **The old suite file by file.** Port tests can't run in the sandbox, and are re-run outside it by the session.

## Out of scope (next rounds, in order)
- **D2:** tickets with a timer inside «ملفات الخبراء» and «النزاعات», and the single person page.
- **D3:** money and the ad balance.
- **D4:** reports and the source of every person.
- **D5:** marketing and connecting the sources.
- **D6:** the company and its capital.
- **D7:** the brain's rules and «اعكس».
