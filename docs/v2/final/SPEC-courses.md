# Final round · Section «الدورات والمدرّبون» (key `courses`)

**Founder order (2026-10-30):** «الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا».
This spec is the build contract for the courses section. It replaces both old screens (`courses` with its 7 internal tabs, and `team` › «المدربون») with screens in the new look. Nothing is drafted here; the builder implements it as written.

**Worktree / branch:** `/Users/abdelrhman/Documents/Playground/elprofessor-dashboard-v2/.worktrees/courses` · `final-courses` (from `7d1aa83`, end of D3).
**Concept:** `Courses.dc.html` (approved row). `Create-Course.dc.html` is reference only: the trainer course builder is **not** in this round.
**Reference style:** D1-B shell, D2 tickets (`v2-d2.js/css`), D3 sheets (`v2-d3.js/css`: `twoStage`, `openSheet`, `warnStrip`, `unavailable`).
**Read-only platform reference:** `/Users/abdelrhman/Documents/Playground/elprofessor-wt-d3/backend` (`routes/admin_bridge.py`, `routes/ops_bridge.py`, `routes/live_courses.py`, `routes/account.py`).

**Revision 2 (after the expert review, 2026-10-30).** Changes: course page has its own address `#s/courses/course/<id>` (§2.2); every publish/hide/archive/delete/schedule/bid/offer/create write goes through a new `/api/v2/courses/*` wrapper with `confirmed:true` (§10); the create sheet makes a hidden draft with no price (§8); the legacy tab hides its old decision tabs and buttons (§9); the platform additions A/B/C/D are tasks for the platform agent in this same workflow (§14); facts re-checked against the platform code (§7.1, §7.12, §8); paper covers instead of one repeated photo (§3.4); review timer honest without `submitted_at` (§3.4); the unknown-checklist decision block (§4); simpler trainer ticket (§5.2); tablet tables (§3.9, §6.2). Rejected or adjusted points are explained in §16 «Decisions».

---

## 0) Binding rules (repeat of the founder rules, applied to this section)

- **No old look anywhere in the section.** Every tab below is new. The old courses screen survives only inside the last tab «كل السجلات», restyled (§9).
- **Visible copy:** plain standard Arabic, gender-neutral («صاحب الدورة», «مقدّم الطلب», «صاحب العرض»), no technical words (no «Zoom»/«Titch»/«slug»/«API» in visible text: Zoom ⇒ «رابط اللقاء», Titch ⇒ «منهج مكتوب»), never «يقوّم», no headline starting with «الذكاء». International audience: currency is always written as its name (`util.curLong`), never «ج».
- **Facts only.** The brain («العقل») line is built from fields that exist. A missing source shows «غير متاح بعد», never 0, never an empty list presented as "none".
- **One main button** per ticket/page (the brain's suggestion). Other actions are secondary (ghost style) or inside the sheet.
- **Publishing and money always ask, on the screen and on the server.** Every write that creates, publishes, hides, archives, deletes, changes a live schedule, toggles price offers, decides a price offer or decides a live course goes through a sheet (D3 `twoStage` pattern or a one-step confirm sheet in the same look) **and** through one of our `/api/v2/courses/*` routes, which refuse anything but `confirmed: true` (§10). The new screens never call the old `/api/platform-courses*` / `/api/platform-course-offers*` write routes directly.
- **Prices are not edited here — not even at creation.** Course prices live in «الفلوس › الأسعار» (D3, `#s/money/prices`). This section only shows the current price and links there with «غيّر السعر من «الفلوس»». The create sheet (§8) has no price field.
- **Shares are not edited here.** The share line in the approve sheet only reads D3's `GET /api/v2/shares` (`courses.base`) and links to `#s/money/shares`.
- Brand: عنّابي `#9E2B4E`, paper `#FBFAF7`/`#F6F1EA`, ink `#21262E`, red `#C8102E` only for overdue timers. Cairo (headings) + IBM Plex Sans Arabic (text). Targets ≥ 44px; buttons 52px on mobile. No horizontal page scroll at 390px. Images: reuse `dashboard-cloud/v2/img/*.jpg` only. Course cards without `thumbnail_url` get the **paper cover** drawn in CSS (§3.4), never the same photo repeated; `v2/img/courses.jpg` is used only as the hero of a course page without a thumbnail. Trainer fallback = initial letter disc; brain = `v2/img/brain-avatar.jpg`. No new image generation.
- **Zero real network calls** in tests and shots. No push, no deploy.

---

## 1) Files (parallel-safety)

| File | New / edit | Content |
|---|---|---|
| `dashboard-cloud/v2s/courses.js` | NEW | All rendering + sources + sheets for the section. Global `window.V2CO`. Registers itself in `window.V2SEC` (§1.1). |
| `dashboard-cloud/v2s/courses.css` | NEW | All styles, every rule prefixed `.v2co-` (⛔ `v2c-` is already used by the shell tabs; `crs-` by the old screen). Legacy restyle rules scoped under `.v2co-legacy` and `html.v2co-legacy-modal` (§9). |
| `dashboard-cloud/v2-logic.js` | EDIT (own parts only) | (a) the `courses` entry in `SECTIONS` (§2); (b) the course-page address lines in `sectionHash`/`parseSectionHash`/`routeFor` + `courseKey`/`courseIdOf` (§1.1 item 7); (c) pure helpers appended at the very end of the file inside `// ===== v2s:courses =====` … `// ===== /v2s:courses =====`, attached as `V2L.v2s.courses = {...}` (see §1.2). |
| `backend/v2_courses_routes.py` | NEW | `register(app, g)` adding the new `/api/v2/courses/*` routes (§10). |
| `backend/app.py` | EDIT (1 line + marker) | Right before the line containing `# ---- v2 section routes end` add `import v2_courses_routes; v2_courses_routes.register(app, globals())`. If the marker does not exist yet, create it as its own line right after the last D3 route (`v2_book_request_patch`, the `/api/v2/book-requests/<request_id>` PATCH, ~line 2680), together with an opening marker `# ---- v2 section routes begin` immediately above it. |
| `dashboard-cloud/index.html` | EDIT (tags + 2 guard lines + course address lines §1.1 item 7) | Block `<!-- v2 sections begin -->` … `<!-- v2 sections end -->` right after `<script src="v2-d3.js"></script>` (create if missing). Our lines, alphabetical by key: `<link rel="stylesheet" href="v2s/courses.css">` and `<script src="v2s/courses.js"></script>`. Guard lines: §1.1. |
| `backend/tests/test_v2s_courses.py` | NEW | §12. |
| `backend/tests/uiharness/courses_fixtures.py` | NEW | Stateful fake platform data for this section (subclass/extend `v2_fixtures.V2Platform`; do not edit it). |
| `backend/tests/uiharness/v2_shots_courses.py` | NEW | Shots §13. Imports helpers from `v2_shots.py` (do not edit it). |
| `docs/v2/final/shots-courses/` | NEW | Shot output (`d*` 1440×900, `t*` 820×1180, `m*` 390×844). |
| `docs/v2/final/STATUS-courses.md` | NEW | Build report (what was built, sources found/missing, deviations, shared edits, which fixture mode is the main one, and the «جاهز حين تنشر المنصة أ/ب/ج/د» line of §14). |

### 1.1 Shared edits (unavoidable, minimal — list them in the report under `shared_edits`)

The old screens are reachable through paths that bypass `renderView` (the `OPSQ_LANDINGS` functions call `viewCourses(...)`/`viewTeam(...)` directly; old Telegram/inbox links do the same). The only bullet-proof interception is one guard line at the top of each old view:

1. `dashboard-cloud/index.html`, first line inside `function viewCourses(v){`:
   `if(window.V2SEC&&V2SEC.take('courses',v))return;`
2. `dashboard-cloud/index.html`, first line inside `function viewTeam(v){`:
   `if(window.V2SEC&&V2SEC.take('team',v))return;`
3. The registry is defined (idempotently) at the top of `v2s/courses.js` with exactly this shape so other sections can share it without conflict:
   ```js
   window.V2SEC = window.V2SEC || { _o: [], add: function (o) { this._o.push(o); },
     take: function (mod, v) { if (!window.V2_ON || !(window.V2SHELL && V2SHELL.on)) return false;
       for (var i = 0; i < this._o.length; i++) { if (this._o[i].take(mod, v)) return true; } return false; } };
   ```
   Our registration: `V2SEC.add({ key: 'courses', take: V2CO.take })`.
4. `deploy/Dockerfile.coolify`: add one line after the `COPY dashboard-cloud/v2/img …` line: `COPY dashboard-cloud/v2s /app/dist/v2s` (identical line for every section). `dashboard-cloud/Dockerfile` already copies the whole folder.
5. `backend/tests/test_xss_hardening.py` line ~628: allow `v2s/[a-z]+\.js` in the script-src whitelist regex (one alternation added: `|v2s/[a-z]+\.js`).
6. Intended edits to old tests (the map changed on purpose): `test_v2_d1b.py` line ~86 (tab table of `courses`) and line ~163 (`('courses', {'courseTab': 'demand'}, 'courses', 'demand')`). Nothing else in D1/D2/D3 tests may change.
7. Course page address (§2.2) — the same pattern D2 uses for the person page, nothing more:
   - `v2-logic.js` `sectionHash(key, tab, arg)`: one extra line `if (arg && key === 'courses' && tab === 'course') return '#s/courses/course/' + courseKey(arg);`.
   - `v2-logic.js` `parseSectionHash`: inside the existing `if (tab && tab.hidden)` branch, for `courses/course` read `courseIdOf(parts[3])`; valid ⇒ `out.course = id`, else first tab (same as an invalid person email).
   - `v2-logic.js` `routeFor`: `if (p.course) r.course = p.course;` next to the `p.person` line.
   - `v2-logic.js`: two small pure functions next to `personKey`: `courseKey(id) = encodeURIComponent(String(id).trim())` and `courseIdOf(key)` = decoded, trimmed, matches `^[A-Za-z0-9_-]{1,100}$` else `''`. Exported beside `personKey`.
   - `index.html` `v2OpenSection(key,tabKey,opts)`: after `V2S={section:sec.key,tab:tab.key};` add `if(opts&&opts.course&&sec.key==='courses'&&tab.key==='course')V2S.course=String(opts.course);`.
   - `index.html` `v2Commit` and `v2OnHash`: `V2L.sectionHash(V2S.section,V2S.tab,V2S.person||V2S.course)` (two call sites).
   - `index.html` `v2OnHash` and `v2ShellBoot`: pass `course:rt.course` in the `opts` given to `v2OpenSection`.
   - `index.html` `V2_HOST`: add `openCourse:function(id){v2OpenSection('courses','course',{course:id});}`. `state()` already returns `V2S`, so `V2_HOST.state().course` is the open course id.

No edit to `v2-home.js`, `v2-shell.js`, `v2Tiles`, `v2Card`, `ALIASES`. The board tile and the «ابدأ القرارات» cards keep calling `goOps('courses'|'team', land)`; the guard lines turn that into the new screens, and `v2Reconcile` puts the header on the right tab (on the course page `courseTab='page'` matches the hidden tab, so `v2Reconcile` returns early and keeps `V2S.course`).

### 1.2 Pure helpers in `v2-logic.js` (own block at the end)

```js
// ===== v2s:courses =====
(function (root) {
  var L = root.V2L || (typeof module !== 'undefined' && module.exports);
  if (!L) return;
  var U = L.util;
  L.v2s = L.v2s || {};
  L.v2s.courses = { /* helpers below */ };
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
// ===== /v2s:courses =====
```
No DOM, no network. Inputs are the raw source payloads (or `null` for a failed source); outputs are view models. Node tests call them as `v2s.courses.<name>` through `v2_apply.js` (dotted path already supported).

| Helper | Input ⇒ output |
|---|---|
| `board(courses, opts)` | `/platform-courses` `courses[]` or `null`, `opts={now, checklists, schedules, stats}` ⇒ `{review[], building[], published[], hidden[], archived[], rejected[], counts{}, summary, na:bool}` |
| `courseFacts(c, ctx)` | one course + `{schedule, checklist, now}` ⇒ `{items:[{key,label,ok:true|false|null}], line, suggestion:'publish'|'return'|'open', returnNote, complete:bool}` |
| `summaryLine(counts)` | ⇒ the header line (§3.1) |
| `appTickets(apps, opts)` | trainer applications or `null` ⇒ tickets `{id, name, email, headline, timer{at,mode:'since'}, tone, line, suggestion, missing[]}` |
| `trainerRows(experts, courses)` | ⇒ `[{email, name, expertise, coursesCount, students, statusLine, tone, inReview, building, published}]` (facts from both sources; a failed source ⇒ `null`) |
| `liveTickets(schedules, queue, opts)` | ⇒ `{decide[], all[]}` |
| `offerTickets(offers, opts)` | ⇒ tickets with `line`, `suggestion:'approve'|'counter'` |
| `demand(stats, requests, analysis)` | ⇒ `{top[], programs[], chat{sample, groups[]}|null}` |
| `pageModel(c, detail, stat, checklist, schedule)` | ⇒ the course page view model (§4) |
| `tone(hours)` | `<24 ⇒ 'ok'`, `24–72 ⇒ 'warn'`, `>72 ⇒ 'late'` (constants `WARN_H=24`, `LATE_H=72`, colour only, never a judgement in text). Applied **only** to a real `submitted_at` (§3.4). |
| `reviewTimer(c, now)` | ⇒ `{at, label, tone}`: `submitted_at` ⇒ `{at: submitted_at, label: v2TimerText(since), tone: tone(h)}`; else `created_at` ⇒ `{at: created_at, label: 'أُنشئت ' + v2TimerText(since), tone: 'none'}`; neither ⇒ `null` |
| `cover(title)` | ⇒ `{letter}`: first Arabic/Latin letter of the trimmed title (skipping «ال» is **not** done — the first letter as written), `'؟'` when empty. Used for the paper cover. |

---

## 2) The section map (`SECTIONS` entry)

Replace the current `courses` entry with (keep the first two tab keys `courses` and `trainers` so old addresses survive):

```js
{ key: 'courses', label: 'الدورات والمدرّبون', img: 'courses', desc: 'الدورات وطلبات المدرّبين وما يطلبه الناس', tabs: [
  T('courses', 'الدورات', 'courses', { courseTab: 'platform' }, { courseTab: ['platform'] }),
  T('trainers', 'المدرّبون', 'team', { teamTab: 'trainers' }, { teamTab: ['trainers'] }),
  T('live', 'الدورات الحيّة', 'courses', { courseTab: 'schedules' }, { courseTab: ['schedules'] }),
  T('demand', 'ما يطلبه الناس', 'courses', { courseTab: 'demand' }, { courseTab: ['demand', 'programs'] }),
  T('offers', 'عروض الأسعار', 'courses', { courseTab: 'offers' }, { courseTab: ['offers'] }),
  hiddenTab(T('course', 'صفحة الدورة', 'courses', { courseTab: 'page' }, { courseTab: ['page'] })),
  T('all', 'كل السجلات', 'courses', { courseTab: 'courses' }, { courseTab: { not: [] } })
] }
```

Resolution guarantees (tested, §12):
- `sectionFor('courses', {courseTab: v})` with no hint: `platform ⇒ courses`, `schedules ⇒ live`, `demand|programs ⇒ demand`, `offers ⇒ offers`, `courses` (the old «سجل الإدارة») `⇒ all`, `trainers` (old internal tab «طلبات المدربين», only reachable from inside «كل السجلات») `⇒ all`.
- With hint `{courses, all}` any `courseTab` stays in `all` (tie ⇒ hint), so browsing the old internal tabs inside «كل السجلات» never jumps out.
- `sectionFor('team', {teamTab:'trainers'}) ⇒ courses/trainers`; `teamTab:'experts' ⇒ files/experts` (unchanged); `teamTab:'admins'` with hint `courses/trainers` stays (unchanged D1-B behaviour).
- `#courses` ⇒ `courses/courses`; `#s/courses/course/<id>` ⇒ `courses/course` with `course: id`; `#s/courses/course` without an id (or with an invalid one) ⇒ first tab.

### 2.1 `V2CO.take(mod, v)` (the guard target)

```
take('courses', v):
  st = V2_HOST.state()                      // {section, tab}
  if st.section === 'courses' && st.tab === 'all':
      if window.courseTab not in ['courses','platform'] → window.courseTab = 'courses'   // hidden old tabs never render (§9)
      if v is our legacy host (#v2coLegacyHost) → return false   // let the old screen draw inside the frame
      draw the legacy frame into v and call window.viewCourses(host) → return true
  map window.courseTab: 'platform'|'courses'|'trainers' (outside 'all')→board · 'schedules'→live · 'demand'|'programs'→demand
                        'offers'→offers · 'page'→course page
  render that screen into v → return true          // 'page' without V2_HOST.state().course ⇒ the board
take('team', v):
  return (window.v2Snapshot && v2Snapshot().teamTab === 'trainers') ? (render trainers screen into v, true) : false
```
Inside «كل السجلات» only the two old internal tabs that are not covered by the new screens render («سجل الإدارة» `courses` and «الكتالوج» `platform`, the latter for lesson editing only, §9); any other old `courseTab` value that reaches «كل السجلات» falls back to `courses` there. There is no redirect out of it, so the back button can never loop. `take` never calls `openSection` itself (that would push history from inside a render). `courseTab` values set by old code outside «كل السجلات» (e.g. `'courses'` after the old create modal) simply render the board.

### 2.2 Course page address
`V2CO.openCourse(id)` = `V2_HOST.openCourse(id)` ⇒ the address becomes `#s/courses/course/<id>` (pushed, so «رجوع» works). Refresh, a Telegram link or a link from «ابدأ القرارات» with that address opens the same course page. The course id is read from `V2_HOST.state().course` (no module copy). When the courses list has loaded and the id is not in it ⇒ `unavailable('الدورة')` with the link «‹ كل الدورات» (never the board in its place); while the list is still loading ⇒ the page skeleton.

---

## 3) Tab «الدورات» (board) — concept `Courses.dc.html`

### 3.1 Header row (inside the content, under the shell's section header)
- Left (RTL start): summary line from `summaryLine(counts)`:
  - published: `U(n, ['دورة واحدة منشورة','دورتان منشورتان','دورات منشورة','دورة منشورة'])`
  - building: `ar(n) + ' تحت البناء'`
  - waiting (review): `U(k, ['دورة واحدة تنتظرك','دورتان تنتظرانك','دورات تنتظرك','دورة تنتظرك'])`, or «لا شيء ينتظرك» when `k = 0`.
  - joined with « · ». Courses source failed ⇒ the whole line is «الدورات: غير متاح بعد».
- Right (RTL end): main button «أنشئ دورة» (burgundy, plus icon, min-height 48 desktop / 52 mobile) ⇒ the create sheet §8.

### 3.2 Layout
- **Desktop ≥ 1180px:** four columns, equal width, gap 16: «في المراجعة» · «تحت البناء» · «منشورة» · «المدرّبون» (summary card). Note: the concept shows «تحت البناء» first; we put «في المراجعة» first because it is the only column that waits on the founder (it carries the timer and the main button). Each column header: bold 16px title + count on the opposite end (`ar(n)`, grey).
- **Tablet 820px:** two columns: row 1 «في المراجعة» + «تحت البناء», row 2 «منشورة» (full width, rows), then the trainers summary card full width.
- **Mobile 390px:** a segmented strip of three buttons (≥ 52px high, equal width, each «label + count»): «في المراجعة ٢» · «تحت البناء ٣» · «منشورة ١١». One column visible at a time. Default: «في المراجعة» when it has items, else «منشورة». Choice remembered in `localStorage['v2co_col']` (try/catch). Under the active column: the trainers summary as one row card «المدرّبون · طلبات انضمام جديدة: ٢» ⇒ trainers tab. No horizontal page scroll.

### 3.3 Classification (`board`)
Source: `GET /api/platform-courses` (existing proxy ⇒ `/api/bridge/courses`) fetched by our own source loader (§11) so a failure is an error, not an empty list. Fields used: `id, slug, title, type, is_active, approval_status, archived_at, source, created_at, short_description, instructor_name, lesson_count, story{units,lessons,minutes}, total_enrolled, price_amount, price_currency, bid_enabled` + when present (Platform need A): `instructor_email, thumbnail_url, updated_at, submitted_at, review_note, agreement_signed, platform_owned, payout_model`.

| Column | Rule |
|---|---|
| «في المراجعة» (`review`) | `approval_status === 'pending'` (regardless of `is_active`) |
| «منشورة» (`published`) | `is_active === true` and not pending |
| «تحت البناء» (`building`) | `!is_active && !archived_at && approval_status !== 'pending' && approval_status !== 'rejected'` |
| «تحت البناء» with mark «أُعيدت بملاحظات» (`rejected`) | `approval_status === 'rejected' && !is_active && !archived_at` (sent back = still being built) |
| not on the board (`archived`) | `!is_active && archived_at` — only in «كل الدورات» list filter «مؤرشفة» |

Sort: review = §3.4 (by `submitted_at` only); building = newest `updated_at || created_at` first; published = most `total_enrolled` first.

### 3.4 Review ticket («في المراجعة») — D2 ticket look
```
┌ strip: «دورة جديدة» | «دورة حيّة» (type live_upcoming)      timer «منذ ٣ أيام» (tone colour) ┐
│ cover 100% × 110px (thumbnail_url as <img>, else the paper cover), radius 12                  │
│ title (15px bold, button ⇒ course page)                                                        │
│ «{trainer} · {lessons}»  trainer = person link when email known (D2 `personLink`)             │
│ [brain avatar 22px] brain line (§3.5)                                                          │
│ [main button by suggestion]            «افتح الدورة» (text link ⇒ course page)                │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Paper cover** (`.v2co-cover`, used by every course card, row thumb and list thumb when `thumbnail_url` is empty): background `#F6F1EA`, a 4px burgundy `#9E2B4E` bar on the inline-start edge, the letter from `cover(title)` in Cairo 800 (48px on the 110px cover, 28px on the 72px thumb, 20px on the 40px list thumb) in burgundy at 85% opacity, centred; `aria-hidden="true"` (the title is next to it). As soon as Platform need A delivers `thumbnail_url`, the `<img>` (object-fit cover) replaces it with no other change; an `<img>` that fails to load (`onerror`) falls back to the paper cover.
- Timer: `reviewTimer(c, now)` (§1.2), refreshed every minute (same pattern as D2, no reload).
  - With `submitted_at`: «منذ ٣ أيام», coloured by `tone(hours)` (24/72h limits apply here only).
  - Without `submitted_at` (until Platform need A): grey, no tone, text «أُنشئت منذ ٩٠ يومًا» — the age of the course, never presented as waiting time, never red.
- Sort of the «في المراجعة» column: by `submitted_at` (oldest first) when every item has it; items without it come after, sorted by title (Arabic collation). We do not sort by `created_at`, which would rank by age, not by waiting.
- The first review ticket (oldest by `submitted_at`) gets the 2px burgundy border (concept); without `submitted_at` on it, no ticket gets the border.
- When `suggestion === 'open'` the main button already opens the course, so the text link «افتح الدورة» is not shown (the title stays clickable).
- `{lessons}`: `U(n,['درس واحد','درسان','دروس','درسًا'])` from `story.lessons` when `story` exists else `lesson_count`; `0` ⇒ «لا دروس بعد» (a real zero from a working source is a fact, allowed).
- `{trainer}`: `instructor_name`, or «البروفيسور» when `platform_owned === true`, or «بلا اسم مدرّب» when empty.

### 3.5 Brain line and suggestion for a course in review (`courseFacts`)
Known facts (from the list + schedules), each `ok: true|false|null`:

| key | label (when false) | rule |
|---|---|---|
| `content` | «لا دروس فيها» | recorded: lessons > 0 (story or lesson_count); live: schedule `start_date` not empty |
| `price` | «بلا سعر» | `type === 'recorded_free'` ⇒ true; else `price_amount > 0` |
| `zoom` (live only) | «بلا رابط للقاء» | schedule `zoom_link` not empty; schedules source failed ⇒ `null` |
| `agreement` | «لم يوقّع صاحب الدورة الاتفاقية» | `agreement_signed` (Platform need A); absent field ⇒ `null`; `platform_owned` ⇒ not shown |
| checklist items | label from the platform | Platform need B (`GET /api/v2/courses/<id>/checklist`); 404/failed ⇒ items absent and `complete=false` |

Line text (joined by « · », max ~120 chars):
- positive facts: lessons phrase («فيها ٩ دروس»), price («مجانية» or «السعر {moneyText}»), live («رابط اللقاء موجود»).
- When the checklist is available and all ok: «اجتازت الفحص: {n} من {n}».
- When something failed: «ينقصها: {labels joined by '، '}».
- When the checklist is unavailable: append «بقية بنود الفحص: غير متاح بعد».

Suggestion ⇒ main button:
| Condition | Suggestion | Main button | Action |
|---|---|---|---|
| any known item false | `return` | «أعِدها بملاحظات» | reject sheet §7.2, note prefilled `returnNote` = «ينقص الدورة قبل النشر: {labels joined by '، '}.» (editable, required) |
| checklist complete and all ok | `publish` | «انشرها» | approve sheet §7.1 |
| otherwise (unknowns remain) | `open` | «افتح وراجع» | course page |

The brain never recommends publishing while any item is unknown.

### 3.6 Building card («تحت البناء»)
Cover 110px (thumbnail or paper cover, §3.4) · title · «{trainer} · {lessons} حتى الآن» · one status line:
- rejected: «أُعيدت بملاحظات» + (`review_note` ? «: » + first 80 chars : '') in amber `#8A4B00`.
- else `updated_at` known: «آخر تعديل {agoText}».
- else nothing (no invented deadline; the concept's «باقٍ ٦ أيام على المهلة» needs Platform need D and appears only when `first_course_due_at` exists: «باقٍ {durShort} على مهلة أول دورة», amber when < 3 days, red when passed «انتهت مهلة أول دورة منذ …»).
- Whole card is a button ⇒ course page. No main action (nothing waits on the founder). No progress bar (no planned lesson count exists).

### 3.7 Published rows («منشورة»)
Row card: 72×72 thumb (thumbnail or paper cover) · title · line 1 «{U(total_enrolled,['متعلّم واحد','متعلّمان','متعلّمين','متعلّمًا'])} · {price or «مجانية»}» · when the course is recorded, has no `story` and its lesson count is 0: an amber line «لا تظهر للناس بعد: لا دروس فيها» (fact: the platform hides a recorded course with no lessons from its catalog and refuses to sell it — `courses.py` `_is_course_public_ready` / `course_sale_block_reason`) · line 2 from stats (Platform need C): «المبيعات: {per currency moneyText joined ' + '}» and, when known, «يكملها {pct}٪» or the stall fact «يتوقف أغلبهم عند الدرس {ar(n)}» (amber). Stats source missing/failed ⇒ line 2 = «المبيعات ونسبة الإكمال: غير متاح بعد» (grey). `bid_enabled` ⇒ small chip «يقبل عروض الأسعار».
Show top 5, then link «كل الدورات ({ar(N)})» ⇒ list mode (§3.9).

### 3.8 Trainers summary card (4th column / row on mobile)
Title «المدرّبون». Up to 3 rows from `trainerRows` with the most relevant status: 44px avatar (initial disc; burgundy-tinted), name (person link), status line (§5.3). Footer: «طلبات انضمام جديدة: {ar(n)}» + link «راجعها» ⇒ `#s/courses/trainers`. Applications source failed ⇒ «طلبات الانضمام: غير متاح بعد». Experts source failed ⇒ «المدرّبون: غير متاح بعد» + «أعد المحاولة».

### 3.9 List mode «كل الدورات»
Inside the same tab (module state `S.list = true`, back link «‹ اللوحة»). Filter chips (≥44px): «منشورة» · «تحت البناء» · «في المراجعة» · «مخفية» (inactive drafts) · «مؤرشفة» · «أُعيدت» — each with its count. Search box «ابحث بعنوان الدورة أو اسم المدرّب» (client-side filter).
- Desktop ≥ 1180px: table — columns «الدورة» (40px thumb + title) · «المدرّب» · «النوع» · «المتعلّمون» · «السعر» · «الحالة» (chip). Row click ⇒ course page. Table sits in a card with 12px radius, header row paper `#F6F1EA`, 52px rows, no vertical borders, `table-layout: fixed` with the title cell ellipsised.
- Tablet 600–1179px: 4 columns — «الدورة» (thumb + title, and under the title a grey line «{المدرّب} · {النوع}») · «المتعلّمون» · «السعر» · «الحالة». Nothing scrolls sideways inside the card.
- Mobile < 600px: the rows as cards (thumb, title, «المدرّب · النوع», «المتعلّمون · السعر», chip).
Type labels: `recorded_paid` «مسجّلة مدفوعة» · `recorded_free` «مسجّلة مجانية» · `live_upcoming` «حيّة» · plus «تفاعلية» chip when `story` exists. Status chips: «منشورة» (green tint) · «في المراجعة» (amber) · «تحت البناء» (grey) · «أُعيدت» (amber) · «مؤرشفة» (grey).

### 3.10 States
- Loading (first load): three skeleton cards per column + «…جارٍ جلب الدورات».
- Courses source failed: the board area shows D3's `unavailable('الدورات')` block: «الدورات: غير متاح بعد» / «تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.» + «أعد المحاولة». Trainers card still renders from its own sources.
- Stats or checklist **not on the platform yet** (404 = closed): no warn strip; the affected lines say «غير متاح بعد» in grey (that is the truth until Platform needs B/C are published).
- Partial (schedules/stats/checklist failed with an error, not 404): `warnStrip` «تعذّر جلب: {labels} — ما يظهر ناقص، وليس معناه أنه لا شيء».
- Empty columns (source OK): «لا دورات تنتظر المراجعة» · «لا دورات تحت البناء» · «لا دورات منشورة بعد».

---

## 4) Course page (hidden tab `course`)

Opened from any course card/row/ticket: `V2CO.openCourse(id)` ⇒ address `#s/courses/course/<id>` (§2.2). Refresh and shared links reopen the same page. Id not in the loaded list ⇒ `unavailable('الدورة')` + «‹ كل الدورات» (never the board in its place).

Sources: the course row (list) · `GET /api/platform-courses/<id>/detail` (existing) · schedules row (live) · `GET /api/v2/courses/<id>/checklist` (new proxy, Platform need B) · `GET /api/v2/courses/stats` (new proxy, Platform need C) · `GET /api/platform-courses/<slug>/reservations` (existing, live only, on demand).

Layout (desktop: two columns 2fr/1fr; tablet + mobile: one column in this order):
1. Back link «‹ كل الدورات».
2. **Hero:** image 16:9, max-height 280 desktop / 200 mobile (`thumbnail_url`, else `v2/img/courses.jpg` — the only place that photo is used), title (Cairo 800, 28px desktop / 22px mobile), chips: status · type · «تفاعلية» when story · source (`dashboard` «أنشأتها الإدارة», `native` «من بناء المدرّب», `story-seed` «دورة تفاعلية», `titch` «منهج مكتوب»), trainer person link (or «البروفيسور» when platform-owned).
3. **Numbers (4 tiles, 2×2 on mobile):**
   - «المتعلّمون» = `total_enrolled`.
   - «الدروس» = story ⇒ «{lessons} في {units} أجزاء · نحو {minutes} دقيقة»; else `lesson_count`.
   - «السعر» = `price_amount` + `curLong(price_currency)` or «مجانية»; under it the link «غيّر السعر من «الفلوس»» ⇒ `V2_HOST.openSection('money','prices')`.
   - «المبيعات» = stats `sales[]` per currency (never summed across currencies) or «غير متاح بعد».
   Second line under the tiles: «يكملها {completion_pct}٪» and «يتوقف أغلبهم عند الدرس {n}: {title}» when stats has them; else «نسبة الإكمال: غير متاح بعد».
4. **Brain card «فحص النشر»** (right column on desktop): avatar + checklist list (✓ green / ✗ amber with label / «غير متاح بعد» grey) from `courseFacts` + checklist; suggestion line; **one main button by state**:
   | Course state | Main button | Secondary |
   |---|---|---|
   | in review, suggestion `publish` / `return` | «انشرها» / «أعِدها بملاحظات» (§3.5) | the other decision (ghost) |
   | in review, suggestion `open` (some item unknown) | the **«القرار لك»** block below | — |
   | in review, checklist source **failed** (error, not 404) | «أعد جلب الفحص» (reloads `checklist:<id>`) | the «القرار لك» block's two buttons stay visible under it |
   | building (draft, not rejected) | none | «انشرها الآن» (secondary; publish sheet §7.3, warns it skips the review) |
   | rejected | none | «انشرها الآن» (same) |
   | published | none | «أوقف ظهورها» (secondary, sheet §7.3) |
   | archived | «أعِد نشرها» | — |
   **«القرار لك» block** (in review with unknown items): a paper card (`#F6F1EA`, radius 14) titled «القرار لك» (Cairo 700, 18px); under it the brain line «لا أستطيع أن أقترح: {missing sources joined '، '} غير متاح بعد» where the missing sources are the labels of the `null` items («بنود الفحص», «رابط اللقاء», «توقيع الاتفاقية»); then two equal full-width buttons stacked on mobile / side by side on desktop, both burgundy outline (white fill, 2px `#9E2B4E` border, burgundy text, 52px): «انشرها» (sheet §7.1, its stage 2 also lists «لم يكتمل فحص النشر: {missing}») and «أعِدها بملاحظات» (sheet §7.2, empty note). Neither is filled, so the screen never looks like the brain chose.
   Share line in the approve sheet only (§7.1).
5. **«البيع»** card (published and `type !== 'recorded_free'` only): toggle «يقبل عروض الأسعار» (`bid_enabled`) ⇒ sheet §7.4. Line: «يستطيع المشتري أن يقترح سعرًا أقل، وتصلك العروض في «عروض الأسعار»».
6. **«المحتوى»** card: read-only tree from `/detail`: sections ⇒ lectures (title + «معاينة مجانية» chip when `is_preview`), or written lessons («{n} درسًا مكتوبًا، وفيها {q} سؤالًا»), or story summary + link «شاهدها كما يراها المتعلّم» (existing `pcPreviewUrl(c)` URL, `target=_blank`, only when `story` and `slug`). Detail failed ⇒ «المحتوى: غير متاح بعد» + «أعد المحاولة». Footer link «تعديل الدروس من «كل السجلات»» ⇒ opens the `all` tab with `courseTab='platform'` and the old drawer selected on this course (set globals `courseTab='platform'` via `V2_SETTERS.courseTab` and `selected='P'+index` before `viewCourses`).
7. **Live card** (type `live_upcoming`): start date (formatted `dateText`), «المقاعد: {booked} من {max}», «الحد الأدنى للتشغيل: {quorum}», status chip (§6), «رابط اللقاء: موجود/غير موجود», button «عدّل الموعد» ⇒ schedule sheet §7.6, link «من حجز» ⇒ reservations sheet §7.7.
8. **Danger zone** (bottom, ghost-red): «أرشف الدورة» or «احذفها نهائيًا» using the existing rule `pcCanHardDelete(c)` (`!is_active && !archived_at && total_enrolled == 0` ⇒ delete; else archive); archived ⇒ nothing. Sheet §7.5.

States: list source failed and the course row is unknown ⇒ the whole page is `unavailable('الدورة')`.

---

## 5) Tab «المدرّبون» (old `team` › trainers)

### 5.1 Layout
- Desktop: two columns 3fr/2fr: left «طلبات المدرّبين» tickets (grid of 2 ticket columns), right «المدرّبون» list card.
- Tablet: one column: tickets (2 per row), then the list.
- Mobile: segmented strip «الطلبات {n}» · «المدرّبون {m}», one view at a time (default the requests when n > 0). Choice remembered in `localStorage['v2co_tr']` (try/catch).

### 5.2 Application ticket (`appTickets`)
Source: `GET /api/platform-trainer-applications?status=pending` (existing proxy) ⇒ `applications[]` fields: `id, user_name, user_email, headline, expertise[], experience_summary, linkedin_url, portfolio_url, cv_url, founding_lead_id, created_at, updated_at`.
```
strip «طلب مدرّب جديد»                                timer «منذ ٢ يوم» (since created_at || updated_at)
name (button ⇒ the detail sheet §7.10, like a D2 ticket title) · headline (1 line)
chips: expertise (max 3, «+N»)
[brain] line
[main]  «ارفض» (ghost)
```
Two actions only: the main button and «ارفض». Opening the application is a click on the name (no third button). The person page stays reachable from the detail sheet («افتح صفحة الشخص», D2 `personLink`).
Brain facts (exact phrases, joined « · »):
- expertise: `U(n,['مجال واحد','مجالان','مجالات','مجالًا'])`; none ⇒ «بلا مجال محدّد».
- links present: «لينكدإن» / «سيرة ذاتية» / «نماذج أعمال» (each only if the URL is non-empty); none ⇒ «بلا روابط».
- summary: `experience_summary.length < 40` ⇒ «نبذة الخبرة قصيرة».
- `founding_lead_id` ⇒ «جاء من دعوة الخبراء المؤسسين».
Suggestion: `(linkedin_url || cv_url) && experience_summary.length >= 40 && expertise.length >= 1` ⇒ main «اقبله وأرسل الاتفاقية» (sheet §7.8); else main «افتح الطلب» (detail sheet) and the line ends with «ينقص الطلب: {missing joined '، '}» (missing ∈ «سيرة ذاتية أو لينكدإن», «نبذة خبرة كافية», «مجال واحد على الأقل»). «اطلب مستندًا» from the concept is **not** offered: the platform has no route that asks an applicant for a document (Platform need G, §14).
Empty (source OK): «لا طلبات انضمام جديدة». Failed: `unavailable('طلبات المدرّبين')`.

### 5.3 Trainers list (`trainerRows`)
Sources: `GET /api/platform-experts` (existing) ⇒ `experts[]` (`email, full_name, expertise, courses_count, students_count, rating_avg, rating_count, is_test, public_ready`) joined with the courses list (by `instructor_email` when present — Platform need A — else exact `instructor_name === full_name`).
Who is listed: experts with `courses_count > 0` or at least one course in any board column. Others: one line at the bottom «و{ar(n)} خبيرًا معتمدًا بلا دورات بعد» + link «اعرضهم في «ملفات الخبراء»» ⇒ `#s/files/experts`.
Row: 44px avatar disc · name (person link) · «{U(courses_count,['دورة واحدة','دورتان','دورات','دورة'])} · {U(students_count,['متعلّم واحد','متعلّمان','متعلّمين','متعلّمًا'])}» · status line (first that applies):
- has a course in review ⇒ «دورة في المراجعة» (amber);
- has a rejected course ⇒ «تُعدَّل ملاحظات المراجعة»;
- has a building course ⇒ «دورة تحت البناء»;
- `agreement_signed === false` (Platform need D) ⇒ «لم يوقّع الاتفاقية بعد» (amber); field absent ⇒ no line;
- `first_course_due_at` (Platform need D) ⇒ «مهلة أول دورة بعد {durShort}» (amber) / «انتهت مهلة أول دورة» (red);
- `is_test` ⇒ «حساب تجريبي — مخفي عن الناس»; `public_ready === false` ⇒ «مخفي عن الدليل: الملف ناقص».
- else `U(n,['دورة منشورة واحدة','دورتان منشورتان','دورات منشورة','دورة منشورة'])`.
Row menu (kebab, 44px) ⇒ «افتح صفحة الشخص» (person page) · «أوقف كمدرّب» (sheet §7.9).

---

## 6) Tab «الدورات الحيّة» (old «مواعيد الحيّة» + the missing live decision)

Sources: `GET /api/platform-schedules` (existing) ⇒ `schedules[]` (`id, slug, title, instructor_name, is_active, start_date, end_date, timezone, zoom_link, registration_deadline, max_seats, booked_count, quorum, payment_window_hours, reserved_count, live_status, payment_deadline, quorum_met, confirmed`) + `EP.data.opsQueue.live_needs_decision[]` (`slug, title, live_status, reserved_count, quorum`).

Layout: desktop: «تحتاج قرارك» tickets row (up to 3 per row) above «كل الدورات الحيّة» table; tablet: tickets 2 per row; mobile: stacked.

### 6.1 Decision tickets (`liveTickets.decide`) — slugs in `live_needs_decision`
Strip «دورة حيّة تحتاج قرارك» + timer: `live_status==='payment_window'` ⇒ `{at: payment_deadline, mode:'over'}`; `reserving` ⇒ `{at: registration_deadline, mode:'over'}`; `needs_decision` ⇒ no timer, label «تنتظر قرارك».
Body: title · trainer · «حجز {reserved} من {quorum}» (the quorum is «الحد الأدنى للتشغيل») · start «تبدأ {dateText(start_date)}».
| Facts | Brain line | Main | Secondary |
|---|---|---|---|
| reserved ≥ quorum and zoom | «اكتمل الحد الأدنى: {r} من {q} · رابط اللقاء موجود» | «ثبّت الدورة» ⇒ live sheet `confirm` | «ألغِ الدورة» |
| reserved ≥ quorum, no zoom | «اكتمل الحد الأدنى، وينقص رابط اللقاء» | «أضف رابط اللقاء» ⇒ schedule sheet §7.6 | «ألغِ الدورة» |
| reserved < quorum | «حجز {r} من {q}، وانتهت مهلة {التسجيل|الدفع}» | «مدّد ٤٨ ساعة» ⇒ live sheet `extend` | «ثبّت رغم ذلك» · «ألغِ الدورة» |
(The platform refuses `confirm` without a link — its message is shown as is.)

### 6.2 «كل الدورات الحيّة» table
- Desktop ≥ 1180px: table — «الدورة» · «الموعد» (`dateText` + time) · «المقاعد» («{booked} من {max}») · «الحد الأدنى» · «الحالة» chip · «رابط اللقاء» («موجود»/«غير موجود») · actions «عدّل الموعد», «من حجز» (ghost, 44px).
- Tablet 600–1179px: cards, two per row (the mobile card), not a table.
- Mobile < 600px: one card per row: title · «{dateText} · {time}» · «المقاعد: {booked} من {max} · الحد الأدنى: {quorum}» · status chip · «رابط اللقاء: موجود/غير موجود» · the two actions as full-width ghost buttons (52px).
- A canceled course (`live_status === 'canceled'`) also shows «من دفع» ⇒ the reservations sheet §7.7 filtered to `paid` (the list the founder refunds by hand).
Status chips: `reserving` «يجمع الحجوزات» · `payment_window` «نافذة الدفع حتى {dateText(payment_deadline)}» · `confirmed` «مثبّتة» · `canceled` «أُلغيت» · `needs_decision` «تنتظر قرارك».
Empty: «لا توجد دورات حيّة بعد». Failed: `unavailable('الدورات الحيّة')`; queue failed ⇒ tickets block replaced by «الدورات التي تحتاج قرارًا: غير متاح بعد» while the table still renders.

---

## 7) Sheets (all in the D3 look: `openSheet` + `.v3m`-equivalent `.v2co-m`, two-stage where something publishes or touches money)

Common: title 20px Cairo; body 15px; inputs ≥ 44px (52px mobile); error box `role=alert` with the platform's Arabic message passed as is (`errMsg`); busy text «جارٍ التنفيذ…»; lost reply (`no_reply`) ⇒ «لم يصلنا رد من المنصة — حدّث الصفحة وتأكد قبل أن تعيد المحاولة» and the button stays locked; 409 ⇒ «تغيّرت الحالة على المنصة — حدّث الصفحة». After success: close, success strip `v3-ok` style for 12s, reload only the affected sources.

### 7.1 Approve course «انشر الدورة»
Stage 1 (form): facts table: «الدورة» · «صاحب الدورة» · «النوع» · «السعر» · «فحص النشر» summary. When `instructor_email` is known and the course is not platform-owned, radio «طريقة الدفع لصاحب الدورة»: «نسبة من كل بيعة» (value `share`, default) / «أجر بالساعة بلا نسبة» (value `hourly`); hidden otherwise (nothing is sent). Line: «النسبة الأساسية لأصحاب الدورات في جدول النسب: {pct(shares.courses.base)}» + link «جدول النسب في «الفلوس»» (`GET /api/v2/shares` failed ⇒ «النسبة: غير متاح بعد»).
Stage 2 (review): «ما سيحدث:» list — «تظهر الدورة للناس في المنصة» · «يصل إلى صاحب الدورة بريد بالنشر» (only when trainer-owned; verified: the bridge approve goes through `courses.py` `review_course_doc`, which calls `dispatch_course_reviewed` once per approval of a pending course) · «لم يكتمل فحص النشر: {missing}» when opened from the «القرار لك» block. The platform also refuses publishing when the owner has not signed the current agreement or a live course has no start date; its Arabic message is shown as is.
Button «أكّد النشر» ⇒ `POST /api/v2/courses/<id>/approve` `{confirmed:true, payout_model?}`.

### 7.2 Return course «أعِد الدورة بملاحظات»
One stage: textarea «ملاحظاتك لصاحب الدورة» (required, ≤ 600, counter), prefilled with `returnNote` when the brain suggested it; hint «تصل إلى صاحب الدورة في بريد كما تكتبها» (verified: `review_course_doc` sends the note with `dispatch_course_reviewed(approved=False, note=…)`). Button «أعِدها» ⇒ `POST /api/v2/courses/<id>/reject` `{confirmed:true, note}`. Empty note ⇒ «اكتب ملاحظاتك أولًا، فهي تصل إلى صاحب الدورة».

### 7.3 Publish / hide «انشرها الآن» · «أوقف ظهورها» · «أعِد نشرها»
Two-stage confirm. Publish copy: «تظهر الدورة للناس الآن.» + for a never-reviewed course: «هذه الدورة لم تمر بالمراجعة.» Hide copy: «تختفي الدورة من المنصة للمتعلّمين الجدد، ويكمل المسجّلون ({n}) دراستهم.»
Calls `POST /api/v2/courses/<id>/visibility` `{confirmed:true, is_active:true|false}` (§10).

### 7.4 «يقبل عروض الأسعار» toggle
One-step confirm: «تفعيل عروض الأسعار على «{title}»؟» / «إيقاف…». Calls `POST /api/v2/courses/<id>/bid` `{confirmed:true, bid_enabled}` (§10).

### 7.5 Archive / delete
Copy in fusha (replacing the old dialect text in `pcRemoveModal`):
- Archive: «تُؤرشف «{title}»:» • «تختفي من قائمة الدورات في المنصة، ولا يراها متعلّمون جدد.» • «{n} مسجّلًا ودفعاتهم وتقدّمهم تبقى كما هي، ويكمل المسجّل الحالي دراسته.» • «لا حذف: يمكنك إعادة نشرها من صفحة الدورة.» Button «أرشفها».
- Delete: «تُحذف «{title}» من المنصة نهائيًا:» • «تختفي من قائمة الدورات ومن المنصة.» • «تُحذف دروسها ومنهجها وأسئلتها معها.» • «لا تراجع بعد الحذف.» + note «الحذف متاح لأن الدورة مسودة بلا مسجّلين. إن وُجد عليها اشتراك أو دفعة سترفض المنصة الحذف، وعندها استعمل الأرشفة.» Button «احذفها نهائيًا» (red), enabled only after typing the course title.
Calls `POST /api/v2/courses/<id>/archive` `{confirmed:true, hard:false|true}` (§10); the success strip follows the response (`deleted` ⇒ «حُذفت الدورة نهائيًا» else «أُرشفت الدورة»). Platform refusal shown inside the sheet; the sheet stays open.

### 7.6 Schedule «موعد الدورة الحيّة»
Fields: «تاريخ البدء ووقته» (`<input type="datetime-local">`, converted to ISO with the browser's offset; the timezone is shown under it: «بتوقيت جهازك: {offset}»), «رابط اللقاء» (url, `dir=ltr`), «عدد المقاعد» (number ≥ 0), checkbox «ثبّت الموعد للمتعلّمين». Two-stage review (before ⇒ after table, D3 `diffTable`). Calls `POST /api/v2/courses/<id>/schedule` `{confirmed:true, start_date, zoom_link, max_seats, pin_schedule}` (§10). ⛔ `confirmed` is our confirmation flag; the checkbox «ثبّت الموعد للمتعلّمين» travels as `pin_schedule` and our route forwards it to the platform's own `confirmed` field.

### 7.7 Reservations «من حجز» / «من دفع» (read-only)
`GET /api/platform-courses/<slug>/reservations?status=all` (existing read). List: name (person link) · status chip («حجز» / «دُعي للدفع» / «دفع» / «أُلغي») · date. «من دفع» = the same list filtered client-side to the paid status. Failed ⇒ «قائمة الحجوزات: غير متاح بعد».

### 7.8 Accept trainer «اقبله وأرسل الاتفاقية»
One-step confirm: «قبول {name} مدرّبًا؟» • «يصل إلى مقدّم الطلب بريد فيه اتفاقية التدريب ليوقّعها.» (verified: `account.py` `approve_trainer_application_doc`, one email per first approval) • «لا تُنشر أي دورة لمقدّم الطلب قبل توقيع الاتفاقية.» (verified: the publish gate in `approve_course_doc`). No sentence about a deadline or reminders until Platform need D is published; once `first_course_due_at` exists on the experts source, the trainers list shows it (§5.3) — the sheet still promises nothing the platform does not do. Button «اقبل وأرسل الاتفاقية». Calls the existing path `EP.decideInboxItem({apiKind:'trainer', apiId:id}, 'approve', null, '')` (returns `{ok, error, noReply}`), i.e. `POST /api/platform-trainer-applications/<id>/approve`.
Reject «ارفض الطلب»: textarea «سبب الرفض» required (hint «يقرؤه مقدّم الطلب كما تكتبه»), `EP.decideInboxItem(..., 'reject', null, reason)` (server already refuses an empty reason).

### 7.9 Stop trainer «أوقف كمدرّب»
Copy: «يُلغى اعتماد {name} مدرّبًا، ويختفي من دليل الخبراء.» • «الدورات المنشورة لصاحب الحساب لا تُحذف.» Checkbox «وسم الحساب تجريبيًا (لحسابات التجربة فقط)» default off. Field «اكتب البريد للتأكيد» (must equal the email, case-insensitive) and «السبب (اختياري)».
On confirm: `GET /api/platform-users?search=<email>` ⇒ exact email match ⇒ `POST /api/platform-trainers/<id>/deactivate` `{reason, is_test, email}` (existing; same as `EP.deactivateTrainer`). No match ⇒ «لم نجد حساب هذا المدرّب على المنصة».

### 7.10 Application detail «طلب {name}» (read-only + the two decisions)
All application fields in label/value rows: «العنوان المهني» · «المجالات» · «نبذة الخبرة» · «لينكدإن» / «السيرة الذاتية» / «نماذج الأعمال» (links, `target=_blank rel=noopener`) · «تاريخ التقديم» · the brain line of the ticket with its «ينقص الطلب» part. Footer: main «اقبله وأرسل الاتفاقية» (burgundy) · «ارفض الطلب» (ghost) · text link «افتح صفحة الشخص».

### 7.11 Course price offer
All three go to `POST /api/v2/courses/offers/<offer_id>/decide` (§10) with `confirmed:true`.
Verified platform behaviour (`courses.py` `decide_course_offer_doc`): approve ⇒ the offer is approved at the offered amount, **raised to the floor when it is below it**; counter ⇒ the offer is approved at the counter amount (also raised to the floor); reject ⇒ rejected. No email is sent by this step, so no sheet promises one.
Accept: two-stage (money) «قبول عرض {buyer} على «{course}» بمبلغ {moneyText(offered,currency)}؟». Stage 2 «ما سيحدث:» • «يصبح المبلغ المتفق عليه {moneyText(agreed,currency)}، ويستطيع صاحب العرض الشراء به.» where `agreed = max(offered, floor)`; when `offered < floor` add «العرض أقل من الحد الأدنى، فيُعتمد بالحد الأدنى لا بالمبلغ المعروض.» ⇒ `{confirmed:true, decision:'approve'}`.
Counter «اعرض سعرًا آخر»: number field (≥ floor; client check «لا يقل المبلغ عن {moneyText(floor,currency)}»), two-stage with the same «ما سيحدث» line at the typed amount ⇒ `{confirmed:true, decision:'counter', amount}`. Reject: one-step ⇒ `{confirmed:true, decision:'reject'}`.

### 7.12 Live decision
`confirm`: «تثبيت «{title}»؟» • «يُدعى كل من حجز ولم يدفع إلى الدفع.» ⇒ `POST /api/v2/courses/live/<slug>/decide {action:'confirm', confirmed:true}`.
`extend`: «تمديد مهلة الدفع ٤٨ ساعة؟» • «يُدعى من لم يدفع مرة أخرى.» ⇒ `{action:'extend', extend_hours:48, confirmed:true}`.
`cancel` (red, two-stage, type the course title): «إلغاء «{title}»؟» • «يصل إلى كل من حجز أو دفع بريد وتنبيه بالإلغاء.» (verified: `live_courses.py` `_cancel_live` sends `dispatch_live_canceled` + an in-app notification to every holder and paid buyer, once) • «المنصة لا تردّ المال تلقائيًا: من دفع تردّ له يدويًا، وتظهر قائمتهم بعد الإلغاء مباشرة.» ⇒ `{action:'cancel', confirmed:true}`.
After success the sheet does **not** close: it turns into the result view «أُلغيت الدورة» with the refund list from the response itself (`refunds[]` of `_collect_paid_refunds`): one row per buyer — name/email (person link) · phone when present (`dir=ltr`) · `moneyText(amount, currency)` per row (never summed across currencies; `amount` null ⇒ «المبلغ: غير متاح بعد») · «لم نجد دفعة» grey when `no_payment_found` — and the line «{U(n,['شخص واحد','شخصان','أشخاص','شخصًا'])} يحتاجون استردادًا يدويًا» (n = rows without `no_payment_found`). Empty list ⇒ «لا أحد دفع، فلا استرداد». Button «تمّ» closes. The same list stays reachable later from the table (`من دفع`, §6.2). ⛔ No link to «النزاعات والاستردادات»: its source (`/bridge/refunds/pending`) reads consultations only, so live-course refunds do not appear there (Platform need F, §14).

---

## 8) «أنشئ دورة» (header button)

The new trainer builder is not in this round, so the button opens a **new-style sheet** that creates a **hidden draft** through our new route `POST /api/v2/courses/create` (§10).

Verified facts behind the copy (decided here, not at build time):
- The old path (`POST /api/courses` ⇒ `_platform_create_course`) always sends `is_active: True`, and `CourseBridgeCreate.is_active` defaults to `True` (`admin_bridge.py` ~605). An empty recorded course is then hidden from the public catalog and refused at checkout (`courses.py` `_is_course_public_ready` / `course_sale_block_reason`), but it **appears by itself the moment a first lesson is added**, without any review. That is why the new sheet does not use the old path.
- The bridge accepts `is_active: false` and an explicit `type` (`create_native_course_from_bridge` keeps `recorded_paid` even with no price).

Sheet:
- Fields: «عنوان الدورة» (required, ≤ 160) · «صاحب الدورة» (select: «البروفيسور» ⇒ `platform_owned:true`; or an approved trainer from the experts source ⇒ `instructor_email`, `trainer_name`) · «النوع» («مسجّلة مدفوعة» / «مسجّلة مجانية»). **No price field** (§0).
- Two-stage review: «ما سيحدث:» • «تُنشأ الدورة مسودة على المنصة باسم {owner}، ولا يراها الناس.» • «تضيف دروسها من «كل السجلات»، ثم تنشرها من صفحة الدورة.» • for paid: «تحدّد سعرها من «الفلوس › الأسعار».».
- Body: `{confirmed:true, title, type:'recorded_paid'|'recorded_free', instructor_email, trainer_name}` or `{confirmed:true, title, type, platform_owned:true}`.
- Success (`platform_course_id` returned): close; success strip «أُنشئت الدورة مسودة.» + for paid «حدّد سعرها من «الفلوس › الأسعار»» (link `#s/money/prices`); then open the new course page (§2.2). It sits in «تحت البناء».
- Platform refused (4xx): the platform's Arabic message in the sheet; nothing is kept (our route removes the ledger row it added, §10).
- Lost reply: the D3 `no_reply` message; the button stays locked. (If the platform did create it, it appears in «تحت البناء» after a refresh.)
- The demand tab's «أنشئ دورة بهذا العنوان» opens the same sheet with the title prefilled.
- Titch generation (paid AI) is **not** offered in the new sheet; it remains reachable in «كل السجلات».

---

## 9) Tab «كل السجلات» (the old courses screen, restyled and reduced)

Why it stays: three things are not covered by the new screens this round — lesson/section/question editing (`courseCurriculumModal`, from the old catalog drawer «المنهج والمحاضرات» and the ledger drawer), Titch generation («منهج مكتوب»), and the dashboard's own course ledger («سجل الإدارة») as a **read-only** record (cost, revenue split, link to the platform copy). The trainer builder (D7, pillars) will replace them. Everything else of the old screen is now a new tab, so it is **hidden** here: one decision, one surface.

- Rendering: `V2CO.take` draws `<div class="v2co-legacy"><p class="v2co-legacy-note">…</p><div id="v2coLegacyHost"></div></div>` and calls `viewCourses(host)`; re-renders by the old code that target `#view` come back through the guard and are re-wrapped (§2.1). Old `courseTab` values other than `courses`/`platform` fall back to `courses` before drawing (§2.1).
- Note at the top (one line, grey): «هنا ما بقي من الشاشة السابقة للدورات: تعديل الدروس والمنهج، وإنشاء منهج مكتوب، وسجلّ الإدارة للاطلاع. القرارات كلها في التبويبات الجديدة.»

### 9.1 What is hidden (CSS inside `.v2co-legacy`, behaviour code untouched)
- Old internal tabs: every `#cTabs .tab[data-t]` except `data-t="courses"` («سجل الإدارة») and `data-t="platform"` («الكتالوج»). Selector: `.v2co-legacy #cTabs .tab:not([data-t="courses"]):not([data-t="platform"]){display:none!important}`.
- Old catalog drawer decision buttons: `[data-a="pcapprove"]`, `[data-a="pcreject"]`, `[data-a="pctoggle"]`, `[data-a="pcbidtoggle"]`, and the row buttons `.pcDel` (archive / delete). They live on the course page now, with confirmation (§4, §7).
- Old ledger drawer write buttons: `[data-a="editc"]` (its modal edits the price and the visible state and mirrors both to the platform without confirmation), `[data-a="delc"]` (deletes the platform course too), `[data-a="pub"]`, `[data-a="pubplatform"]`, the ledger create button `#cCreate`, and inside a legacy modal `html.v2co-legacy-modal #epModal #vp_pub` (the curriculum modal's «انشر على المنصة» for a ledger row without a platform copy; that modal then shows only its note and «إغلاق»). Creating is the new sheet (§8); price is «الفلوس › الأسعار»; publish/hide/archive/delete are the course page.
- Kept: «المنهج والمحاضرات» (`[data-a="pcvideo"]`, `[data-a="video"]`), the preview link, «منهج مكتوب» generation, the rows and drawer facts.
- `.v2co-legacy .kpis` hidden (the numbers live on the board now).

### 9.2 Restyle (`courses.css`; look only — copy untouched)
The old markup carries many inline styles, and normal CSS does not beat them. Inside `.v2co-legacy` and `html.v2co-legacy-modal #epModal` **only**, `!important` is allowed, and `courses.css` lists these inline-styled elements explicitly (one rule each): `#cCreate` (hidden anyway), the empty/error/loading states (`.v2co-legacy [style*="padding:40px"]`, `.v2co-legacy .policy[style]`), `.note-ai` (including its inline gold background/border ⇒ paper `#F6F1EA`, border `#E9E1D6`, ink text), `.field .lab` / `.field .val`, `.kpis`, the inline-sized drawer buttons (`.v2co-legacy .btn[style]` ⇒ `font-size:14px!important; padding:0 16px!important; min-height:44px!important`), and the drawer header `.dh .k`.
- `.policy` banners ⇒ paper cards (`#F6F1EA`, radius 14, no coloured border, ink text); `.tabbar` ⇒ the shell tab look (44px, burgundy underline; with only two tabs left nothing scrolls).
- `.panel`, `.drawer` ⇒ white cards, radius 16, border `#E9E1D6`; `.row` ⇒ 52px min height, 14px padding, hover `#FBFAF7`, selected `#F6F1EA` with a burgundy inline-start bar.
- `.btn-primary` ⇒ burgundy `#9E2B4E`; `.btn-ghost` ⇒ white with `#E9E1D6` border; `.btn-warn` ⇒ white with red text `#C8102E`; `.btn-human` ⇒ burgundy outline; all ≥ 44px (52px under 600px); fonts IBM Plex Sans Arabic, Cairo for `h3`.
- `.status` chips ⇒ the chip palette of §3.9. Old palette variables are overridden inside the frame: `.v2co-legacy, html.v2co-legacy-modal #epModal { --navy:#21262E; --gold:#9E2B4E; --memory:#9E2B4E; --human:#9E2B4E; --human-bg:#F6F1EA; --conflict:#C8102E; }` (and the same for any other old colour token the builder finds used inside the frame), so inline `var(--navy)`/`var(--gold)` resolve to brand colours.
- Under 820px the `.inboxwrap` drawer stacks under the list (no side-by-side), no horizontal scroll.
- Modals opened from this tab (`#epModal`): while `#view .v2co-legacy` exists, `html` gets class `v2co-legacy-modal` (a `MutationObserver` on `#view` toggles it), and the modal gets the same paper/burgundy restyle; it is removed as soon as the legacy frame leaves `#view`.

---

## 10) New server routes — `backend/v2_courses_routes.py`

`register(app, g)` where `g = globals()` of `app.py` (gives `token_required`, `roles_required`, `_v2_closed`, `_v2_ns`, `_v2_body`, `_v2_mask_auth`, `_v2_confirmed`, `V2_ID_RE`, `_platform_proxy`, `_resp_ok`, `_proxy_json`, `_audit`, `_actor_email`, `_ef_no_reply`, `_ef_no_reply_resp`, `_course_owner_fields`, `Course`, `db`, `jsonify`, `request`, `quote`). Rules for every route (same as D3):
- Admin only (`@token_required` + `@roles_required('admin')`); flag off ⇒ `_v2_closed()` 404 before any platform call; `Cache-Control: no-store` (`_v2_ns`).
- Ids/slugs checked with `V2_ID_RE` (and `quote(..., safe='')` in the path) ⇒ 400 «معرّف غير صالح».
- Writes: `_v2_confirmed(body)` first (`confirmed is True` exactly, else 400 `V2_CONFIRM_AR`, no call); the body sent to the platform is built from a whitelist only. One local helper `_write(method, path, platform_body, audit_action, target, meta, params=None)` = a copy of D3's `_v2_write` **without** adding `by` (the course bridges' pydantic models do not declare it; the actor goes to `_audit` from the token); one call, no retry, `timeout=25`; lost reply ⇒ `_ef_no_reply_resp`; platform 401/403 ⇒ 502 via `_v2_mask_auth`; platform 4xx (422/409/404/503) passes through with its Arabic message; `_audit` only on success.
- The old `/api/platform-courses*` and `/api/platform-course-offers*` write routes stay as they are (the legacy tab and old code use them); the new screens never call them.

| Route | Platform call | Notes |
|---|---|---|
| `POST /api/v2/courses/create` body `{confirmed:true, title, type, instructor_email?, trainer_name?, platform_owned?}` | `POST /api/bridge/courses` body `{title, type, trainer_name, instructor_email|platform_owned, is_active:false, dashboard_course_id}` | `title` trimmed, 1–160 chars else 400 «اكتب عنوان الدورة»; `type ∈ {recorded_paid, recorded_free}` else 400 «نوع غير معروف»; owner through `_course_owner_fields(body)` (its Arabic error ⇒ 400). Steps: add a ledger `Course(title, trainer_name, status='active', price_egp=0, price_usd=0)` and **commit** (the bridge's idempotency key is `dashboard_course_id`); call the bridge; success ⇒ store `platform_course_id`/`platform_course_slug` on the ledger row, commit, `_audit('course.create', meta={'title','platform_owned','type'})`, return `{ok, platform_course_id, platform_course_slug}`; platform 4xx/401/403 ⇒ delete the ledger row, commit, return the platform's message (masked for 401/403); lost reply ⇒ keep the ledger row (the platform may have created it) and return the `no_reply` shape. No price is ever sent. |
| `POST /api/v2/courses/<course_id>/approve` body `{confirmed:true, payout_model?: 'share'|'hourly'}` | `POST /api/bridge/courses/{id}/approve` body `{payout_model}` only when given | `trainer_share_pct` in our body is **ignored** (never forwarded): shares come from the shares table. Bad `payout_model` ⇒ 400. Audit `course.approve` meta `{payout_model}`. |
| `POST /api/v2/courses/<course_id>/reject` body `{confirmed:true, note}` | `POST /api/bridge/courses/{id}/reject` body `{note}` | `note` trimmed, required (empty ⇒ 400 «اكتب ملاحظاتك أولًا، فهي تصل إلى صاحب الدورة»), cut to 600. Audit `course.reject` meta `{note_len}`. |
| `POST /api/v2/courses/<course_id>/visibility` body `{confirmed:true, is_active: bool}` | `PUT /api/bridge/courses/{id}` body `{is_active}` | `is_active` must be a real boolean else 400 «قيمة غير صالحة». Audit `course.show` / `course.hide`. |
| `POST /api/v2/courses/<course_id>/bid` body `{confirmed:true, bid_enabled: bool}` | `PUT /api/bridge/courses/{id}` body `{bid_enabled}` | Boolean check as above. Audit `course.bid_on` / `course.bid_off`. |
| `POST /api/v2/courses/<course_id>/archive` body `{confirmed:true, hard: bool}` | `DELETE /api/bridge/courses/{id}` with `params={'hard':'true'}` only when `hard is True` | Audit by **what happened**: `_proxy_json(resp).get('deleted') is True` ⇒ `course.delete`, else `course.archive` (same rule as the old route). |
| `POST /api/v2/courses/<course_id>/schedule` body `{confirmed:true, start_date?, zoom_link?, max_seats?, pin_schedule?}` | `PUT /api/bridge/courses/{id}/schedule` body from the whitelist `{start_date, zoom_link}` (strings, trimmed), `max_seats` (int ≥ 0 else 400 «عدد المقاعد غير صالح»), `confirmed: bool(pin_schedule)` only when `pin_schedule` is present | ⛔ our `confirmed` is never forwarded; the platform's `confirmed` comes only from `pin_schedule`. Nothing to change ⇒ 400 «لا يوجد تغيير». Audit `live.schedule` meta = the keys sent. |
| `POST /api/v2/courses/offers/<offer_id>/decide` body `{confirmed:true, decision, amount?}` | `POST /api/bridge/course-offers/{id}/decide` body `{decision, amount?}` | `decision ∈ {approve, reject, counter}` else 400 «قرار غير معروف»; `counter` needs `amount` > 0 (number, not bool) else 400 «اكتب المبلغ»; `amount` is ignored for `reject`. Audit `course_offer.{decision}` meta `{amount}`. |
| `POST /api/v2/courses/live/<slug>/decide` body `{confirmed:true, action, extend_hours?}` | `POST /api/bridge/live/{slug}/decide` body `{action, extend_hours}` | `action ∈ {confirm, extend, cancel}` else 400 «إجراء غير معروف»; `extend_hours` int 1–720, default 48. The response passes through (cancel returns `refunds[]`, shown in §7.12). Audit `live.{action}`. |
| `GET /api/v2/courses/<course_id>/checklist` | `GET /api/bridge/courses/{id}/checklist` | Platform need B. 404 passes through (screen shows «غير متاح بعد»). |
| `GET /api/v2/courses/stats` | `GET /api/bridge/courses/stats` | Platform need C. 404 passes through. |

Unchanged existing endpoints used by the new screens: reads only (`/platform-courses`, `/platform-courses/<id>/detail`, `/platform-schedules`, `/platform-course-offers`, `/platform-trainer-applications`, `/platform-experts`, `/platform-program-requests*`, `/platform-courses/<slug>/reservations`, `/platform-users?search=`), plus the non-money decisions on people: trainer application approve/reject and program request approve/reject (`EP.decideInboxItem`), and stop-trainer (`/platform-trainers/<id>/deactivate`). These keep their confirmation sheets on screen (§7.8–7.10, §11).

---

## 11) Front-end sources (`v2s/courses.js`)

Same loader pattern as D3 (`load(k)`: `EP.api(path)`; ready/error/closed(404); stale-sequence guard; 401 ignored; `changed()` ⇒ debounced redraw). Each source fails alone.

| Key | Path | Label in `warnStrip` |
|---|---|---|
| `courses` | `/platform-courses` | «الدورات» |
| `apps` | `/platform-trainer-applications?status=pending` | «طلبات المدرّبين» |
| `experts` | `/platform-experts` | «المدرّبون» |
| `schedules` | `/platform-schedules` | «مواعيد الدورات الحيّة» |
| `offers` | `/platform-course-offers?status=pending` | «عروض الأسعار» |
| `progStats` | `/platform-program-requests/stats` | «أكثر الدورات طلبًا» |
| `programs` | `/platform-program-requests?status=pending` | «طلبات البرامج» |
| `stats` | `/v2/courses/stats` | «المبيعات ونسبة الإكمال» (404 = closed ⇒ «غير متاح بعد», not in the warn strip) |
| `shares` | `/v2/shares` | «جدول النسب» (approve sheet only) |
| `checklist:<id>` | `/v2/courses/<id>/checklist` | per course, on demand (review tickets visible + course page); 404 = closed |
| `detail:<id>` | `/platform-courses/<id>/detail` | course page only |
| EP `opsQueue` | existing loader (`EP.ensure('opsQueue')`) | «طابور القرارات» |
| EP `analysis` | existing loader, demand tab only | «أسئلة الشات» |

Each tab loads only what it shows. Poll: none (the shell's existing refresh is enough); timers re-render every 60s only while a tab of this section is open (like D2/D3). Signature-based redraw so typing in a sheet is never interrupted (`S.sheetBusy`).

Tab «ما يطلبه الناس» (§ from the old «الطلب على الدورات» + «طلبات البرامج»):
- Desktop: left 2/3 «طلبات تنتظرك» tickets; right 1/3 «أكثر الدورات طلبًا» bars (top 10, title + `U(count,['طلب واحد','طلبان','طلبات','طلبًا'])`, burgundy bar width ∝ count) and below it «من أسئلة الشات». Tablet/mobile: stacked in that order.
- Program ticket: strip «طلب برنامج» + timer since `created_at`; title; requester (`user_name` or `user_email`, person link); brain line «طلبه {ar(n)} أشخاص بنفس العنوان» when `progStats` count for the same title > 1, else «أول طلب بهذا العنوان»; main «اقبل الطلب» ⇒ `EP.decideInboxItem({apiKind:'program', apiId:id}, 'approve', null, '')` (existing `POST /api/platform-program-requests/<id>/approve`) after a one-step confirm «قبول طلب «{title}»؟ يصل إلى صاحب الطلب رابط الدخول إلى البرنامج.»; secondary «ارفض» with a required reason.
- «من أسئلة الشات»: groups of `analysis.recent_questions` with `intent === 'دورة'` by `category` («غير مصنّف» when empty), sorted by count; header line «من عيّنة آخر {ar(sample)} سؤالًا في الشات» (sample = `recent_questions.length`); each group: category + count + one example (≤ 90 chars) + text button «أنشئ دورة بهذا العنوان» (title prefill «دورة في {category}»). `analysis` failed ⇒ «أسئلة الشات: غير متاح بعد».
- Section-top brain line (only when `progStats` ready and non-empty): «أكثر ما يُطلب: «{title}» ({count})».

Tab «عروض الأسعار»:
- Ticket grid (3 per row desktop, 2 tablet, 1 mobile). Strip «عرض سعر» + timer since `created_at`. Body: course title · buyer (person link by `buyer_email`) · segment label (`SEG_LABEL` from the old screen, copied as a constant in our file; unknown ⇒ «فرد») · amounts table: «العرض» `offered_amount` · «السعر المناسب له» `situational_amount` · «الحد الأدنى» `floor_amount` (all `moneyText(x, currency)`).
- Brain line: `pct = round((situational - offered) / situational × 100)`; offered ≥ floor ⇒ «العرض أقل من السعر المناسب بـ{pct}٪، وفوق الحد الأدنى» ⇒ main «اقبل العرض»; offered < floor ⇒ «العرض أقل من الحد الأدنى» ⇒ main «اعرض سعرًا آخر»; message from the buyer (`message`) shown as a quote «سبب العرض: …» when present.
- Secondary: the other of accept/counter + «ارفض».
- Empty: «لا عروض أسعار تنتظرك». Failed: `unavailable('عروض الأسعار')`.

---

## 12) Tests — `backend/tests/test_v2s_courses.py`

Run: `cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_courses.py`. Zero real network: `requests` patched to an in-memory platform (`courses_fixtures.CoursesPlatform`); any URL outside `https://platform.test/api/bridge/` fails the test.

**pytest (routes):**
1. Each new route: non-admin roles (`employee, trainer, investor, viewer, pending`) ⇒ 403; no token ⇒ 401; flag off ⇒ 404 and zero platform calls; `Cache-Control: no-store` on every response.
2. Writes: `confirmed` missing / `'true'` / `1` / `False` / `null` ⇒ 400 with `V2_CONFIRM_AR`, zero calls.
3. Approve: body sent = `{}` or `{payout_model}` only; `trainer_share_pct: 90` in our body never reaches the platform; bad `payout_model` ⇒ 400.
4. Reject: empty/whitespace note ⇒ 400 Arabic, zero calls; 700-char note ⇒ 600 forwarded; body = `{note}` only.
5. Live: action whitelist; `extend_hours` 0/721/'x' ⇒ 400; default 48; platform 503 «قرار الدورات الحية غير متاح بعد…» and 422 pass through unchanged.
6. Platform 401/403 ⇒ 502 «تعذّر الاتصال بالمنصة»; lost reply (timeout/500/502) on a write ⇒ the `no_reply` shape; exactly one platform call (no retry).
7. `_audit` row written only on success, actor = token email, never the body's `by`.
8. Bad ids (`../x`, 300 chars) ⇒ 400, zero calls.
9. Checklist/stats 404 pass through as 404.
9a. Create: `confirmed` rules; title empty/161 chars ⇒ 400; bad type ⇒ 400; owner error from `_course_owner_fields` ⇒ 400 and no ledger row; body sent = whitelist with `is_active: False` and no `price_*`; success ⇒ ledger row has the platform id; platform 422 ⇒ no ledger row left and the Arabic message passes; lost reply ⇒ ledger row kept + `no_reply` shape.
9b. Visibility / bid: non-boolean (`'true'`, `1`) ⇒ 400; body sent = `{is_active}` / `{bid_enabled}` only.
9c. Archive: `hard:true` ⇒ `hard=true` param, otherwise none; audit action follows the response (`deleted:true` ⇒ `course.delete`, else `course.archive`).
9d. Schedule: our `confirmed:true` never reaches the platform as `confirmed`; `pin_schedule:false` ⇒ platform `confirmed:false`; absent ⇒ key absent; `max_seats:'x'` ⇒ 400; empty change ⇒ 400.
9e. Offers: decision whitelist; counter without amount / `amount:true` ⇒ 400; reject drops `amount`.
10. `app.py` contains exactly one `v2_courses_routes.register(app, globals())` line, placed before `# ---- v2 section routes end`.

**node (pure helpers via `v2_node.logic('v2s.courses.<fn>', …)`):**
11. `board`: classification table §3.3 for every combination (pending+active, rejected, archived, draft); `null` source ⇒ `na:true` and no counts (never 0); sort orders.
12. `summaryLine`: singular/dual/plural forms, «لا شيء ينتظرك», Arabic digits only.
13. `courseFacts`: free course price ok; paid without price ⇒ return + note text exact; live without zoom; schedules failed ⇒ zoom `null` ⇒ suggestion `open` (never `publish` with an unknown); full checklist all ok ⇒ `publish` + «اجتازت الفحص: ٦ من ٦».
14. `tone`: 23h ok · 24h warn · 73h late.
15. `appTickets`: each fact phrase; suggestion rule; `founding_lead_id` line; missing list text.
16. `trainerRows`: join by email when present, by exact name otherwise; experts failed ⇒ `null`; status-line priority.
17. `liveTickets`: the three rows of §6.1; queue failed ⇒ `decide:null`.
18. `offerTickets`: pct rounding; below floor branch; currency name written, never «ج».
19. `demand`: chat grouping and sample size; stats title match count.
20. Copy lint over every string produced by the helpers and every literal in `v2s/courses.js`: no Latin digits in visible text (except inside links/ids), no «يقوّم», no string starting with «الذكاء», no «Zoom»/«Titch»/«API»/«slug».

**Map / files:**
21. `SECTIONS` `courses` entry: tab keys/labels/mods exactly as §2; every `sectionFor` case in §2 (incl. the hint cases and `team` experts/admins unchanged); `routeFor('#s/courses/course/abc-123')` ⇒ `courses/course` with `course:'abc-123'`; `routeFor('#s/courses/course')` and `'#s/courses/course/..%2Fx'` ⇒ first tab; `sectionHash('courses','course','abc-123') === '#s/courses/course/abc-123'`; `routeFor('#courses')` ⇒ `courses/courses`; the D2 person cases still pass unchanged.
21a. `reviewTimer`: with `submitted_at` ⇒ tone by hours; with only `created_at` ⇒ label starts with «أُنشئت» and tone `none` even at 90 days; neither ⇒ `null`. `cover('')` ⇒ `'؟'`. `board` review sort puts items without `submitted_at` last, by title.
21b. `index.html`: `v2OpenSection` stores `V2S.course` only for `courses/course`; `v2Commit`/`v2OnHash` pass `V2S.person||V2S.course`; `V2_HOST.openCourse` exists.
22. `index.html`: the `v2 sections` block exists after `v2-d3.js` and contains our two tags; the two guard lines are the first statements of `viewCourses` and `viewTeam`; with the flag off nothing of ours renders (`V2SEC.take` returns false when `V2_ON` is falsy — node vm check).
23. `Dockerfile.coolify` copies `dashboard-cloud/v2s`.
24. Rerun `test_v2_d1.py`, `test_v2_d1b.py` (with the two intended edits), `test_v2_d2.py`, `test_v2_d3.py`, `test_xss_hardening.py`: all green. The old dashboard suite file by file in the sandbox (the three port-binding tests are rerun outside by the main session).

---

## 13) Shots — `backend/tests/uiharness/v2_shots_courses.py`

`python3 -B tests/uiharness/v2_shots_courses.py docs/v2/final/shots-courses` (sets `v2_shots.OUT`, reuses `Browsers`, `open_shell`, `go_section`, `d3_check`-style checks). Viewports: `d` 1440×900, `t` 820×1180, `m` 390×844. Fixture modes: `CoursesPlatform(with_abc=True|False)`. The **main run** uses the mode that matches the platform branch at build time: if Platform needs A/B/C are merged on the platform branch (§14), `with_abc=True`; otherwise `with_abc=False` (no `thumbnail_url`/`submitted_at`/…, checklist and stats 404), and the `with_abc=True` shots are written with a `-abc` suffix to show what the founder will see once the platform publishes. The report says which mode is the main one. Fixture data in `courses_fixtures.py`: 11 published (one interactive, one with `bid_enabled`, one recorded with 0 lessons), 3 building (one rejected with a note), 2 in review (one complete with checklist, one missing price; in `with_abc=False` mode one was created 90 days ago), 1 live needing a decision (below quorum) + 1 live confirmed, 3 trainer applications (one complete, one missing links, one from founding leads), 6 approved experts (3 with courses), 2 course offers (one above floor, one below), 5 program requests + stats, chat sample with 4 «دورة» questions. Stats/checklist endpoints present for the main run and absent (404) for the «unavailable» shots.

| # | Shot |
|---|---|
| 01 | Board full (d/t/m; mobile on each of the three column buttons: `01m-review`, `01m-building`, `01m-published`), with fixture thumbnails; `01-covers` = the same board without `thumbnail_url` (paper covers, no repeated photo) |
| 02 | Board with the courses source down (unavailable block + trainers card still alive) |
| 03 | Board with stats/checklist 404 (published rows «غير متاح بعد», review line ends «بقية بنود الفحص: غير متاح بعد», main «افتح وراجع») |
| 04 | «كل الدورات» list mode + a filter (d/m) |
| 05 | Course page in review (checklist complete) + `05b` approve sheet stage 1 + `05c` stage 2 + `05d` after success + `05e` course page in review with the checklist absent («القرار لك» block) + `05f` after a browser reload on `#s/courses/course/<id>` (same page) + `05g` unknown id (`unavailable('الدورة')`) |
| 06 | Return sheet with the prefilled note + `06b` platform refusal message |
| 07 | Course page published (numbers, sales, completion, bid toggle, content tree) + `07b` hide sheet |
| 08 | Archive sheet and delete sheet (typed title) |
| 09 | Trainers tab (d/t/m both segments) + `09b` accept sheet + `09c` reject sheet + `09d` application detail + `09e` stop-trainer sheet |
| 10 | Live tab (decision tickets + table d / cards t,m) + `10b` cancel sheet stage 2 + `10b2` cancel result with the refund list + `10c` schedule sheet with before ⇒ after |
| 11 | «ما يطلبه الناس» (d/m) + `11b` program accept confirm |
| 12 | «عروض الأسعار» + `12b` counter sheet with a below-floor client error |
| 13 | Create course sheet stage 1/2 (`13`, `13b`) + `13c` success (new draft page in «تحت البناء» + price link) |
| 14 | «كل السجلات» restyled (only «سجل الإدارة» and «الكتالوج» tabs) + `14a` catalog drawer of a course in review (no decision buttons) + `14b` an old modal restyled (curriculum) |
| 15 | Home tile «الدورات والمدرّبون» tapped ⇒ lands on the board; a «دورة تنتظر الاعتماد» card ⇒ board; old link `#courses` ⇒ board; `#team` with trainers state ⇒ trainers tab |
| 16 | Flag off: the old screens exactly as before (proof of no trace) |

The script fails when: any «0/null/NaN/undefined» is visible where a source is missing; a target < 44px (buttons < 52px on mobile); horizontal scroll at any viewport; a Latin digit in visible text (except links/ids); any request outside the in-process app + Google Fonts; any write without `confirmed:true` on the new routes; any element with class `rail` visible with the flag on; any old-look class (`.kpis`, `.tabbar`, `.inboxwrap`) visible outside `.v2co-legacy`; **inside** `.v2co-legacy` (shots 14/14a/14b): any visible `.tab[data-t]` other than `courses`/`platform`, any visible element matching `[data-a="pcapprove"],[data-a="pcreject"],[data-a="pctoggle"],[data-a="pcbidtoggle"],.pcDel,[data-a="editc"],[data-a="delc"],[data-a="pub"],[data-a="pubplatform"],#cCreate,#vp_pub`, or any visible element whose computed `color`/`background-color`/`border-color` equals the old navy or gold values (read the old `--navy`/`--gold` from `:root` before the frame loads); **anywhere in the section**: any element under `[class*="v2co-"]` with `scrollWidth > clientWidth + 1` and computed `overflow-x` not `hidden` (no sideways scroll inside cards or tables, at d/t/m); a review timer in red/amber on a course without `submitted_at`. Rerun `v2_shots.py <out> d1b` afterwards to prove D1-B shots still pass.

---

## 14) Platform needs — tasks for the platform agent in this same workflow

A, B, C and D are **platform-agent tasks of this round** (read-only, additive bridge changes on `/Users/abdelrhman/Documents/Playground/elprofessor-wt-d3`, branch `money-d3`, in `routes/admin_bridge.py` + pure helpers in `routes/courses.py`; no DeepSeek or any paid call; tests in the platform's own suite; no push, no deploy). The dashboard does not wait for them: every screen already handles their absence («غير متاح بعد», paper covers, grey timer, «القرار لك»). `STATUS-courses.md` must carry the line: «اللوحة جاهزة. تكتمل الاقتراحات والصور والمبيعات حين تنشر المنصة الإضافات أ/ب/ج/د» with, per letter, built-on-branch yes/no. If the platform agent postpones any of them, the main fixture runs without it (§13), so the shots show the truth.

**A. Extra fields on `GET /api/bridge/courses` items (additive, defaults keep today's shape):**
```json
{ "instructor_email": "trainer@x.com",      // "" when none
  "platform_owned": false,
  "thumbnail_url": "https://…",              // "" when none
  "updated_at": "2026-10-29T10:00:00+00:00",
  "submitted_at": "2026-10-28T09:00:00+00:00", // when approval_status became "pending"; "" if unknown
  "review_note": "…",                        // last reject note; ""
  "agreement_signed": true,                  // current agreement version signed by the owner; null for platform-owned
  "payout_model": "share",                   // "share" | "hourly" | null
  "trainer_share_pct": 35 }                  // stamped share or null
```

**B. `GET /api/bridge/courses/{course_id}/checklist`** — the deterministic part of `bridge_agent_review_course` with **no DeepSeek call**:
```json
{ "course_id": "…", "slug": "…",
  "checklist": [ {"key": "content", "item": "فيها محتوى (دروس مسجّلة أو موعد بدء للدورة الحيّة)", "ok": true},
                 {"key": "outcomes", "item": "نواتج التعلّم مذكورة", "ok": true},
                 {"key": "intro_video", "item": "فيديو تعريفي مرفوع", "ok": false},
                 {"key": "level", "item": "مستوى الدورة محدّد", "ok": true},
                 {"key": "pricing", "item": "التسعير سليم", "ok": true},
                 {"key": "zoom", "item": "رابط اللقاء للدورة الحيّة", "ok": true},
                 {"key": "agreement", "item": "صاحب الدورة وقّع الاتفاقية", "ok": true} ],
  "all_ok": false,
  "sale_block_reason": "" }                  // course_sale_block_reason text in plain Arabic, "" when sellable
```
404 when the course does not exist. Item texts in plain standard Arabic. Deterministic only: the same checks as `bridge_agent_review_course` minus its DeepSeek memo, plus the publish gate of `approve_course_doc` (signature + live start date) and `course_sale_block_reason`.

**C. `GET /api/bridge/courses/stats`**:
```json
{ "generated_at": "…",
  "courses": [ { "course_id": "…", "slug": "…",
                 "enrolled": 312,
                 "paid_count": 140,
                 "sales": [ {"currency": "EGP", "amount": 168000.0}, {"currency": "SAR", "amount": 1200.0} ],  // paid course + course_offer payments, net of refunds, never converted
                 "completed": 200, "certificates": 190,
                 "completion_pct": 64,                       // completed / enrolled, null when enrolled = 0
                 "stall_lesson": {"index": 4, "title": "…", "learners": 51} } ] }   // lesson where most active-but-stalled learners stopped; null when unknown
```

**D. Trainer first-course deadline (NOTES 2026-10-30: «العقل … يدّي مهلة لأول دورة»)** — on `GET /api/bridge/experts` items: `user_id` (to stop a trainer without a users lookup), `first_course_due_at` (ISO|null), `last_reminder_at` (ISO|null), `agreement_signed` (bool|null). Until it exists, no deadline, reminder or agreement line is shown for trainers, and the accept sheet promises only the agreement email (§7.8).

**F. Live-course refunds in the refunds queue.** `GET /api/bridge/refunds/pending` reads consultations only (`scheduling.py` ~1031), so paid buyers of a canceled live course never appear in «النزاعات والاستردادات». Until it does, the list is shown from the cancel response and from «من دفع» (§6.2, §7.12). Not in this round (it belongs to the disputes/money section); recorded here so it is not lost.

**G. «اطلب مستندًا» for trainer applications.** No platform route asks an applicant for a missing document (the approved concept shows it). Not in this round; the ticket does not offer it (§5.2).

**E. Existing platform inconsistencies to fix on the platform side (found while mapping; not dashboard work):** `CourseApproveBridgeBody.trainer_share_pct` allows up to 90 (owner) — above the 65% owner cap of `SHARES-2026-10-30.md`; it should go through `clamp_owner_share`. The dashboard never sends it.

---

## 15) Out of scope (this round)
- Platform needs F and G (§14).
- The trainer course builder (`Create-Course.dc.html`) and replacing the ledger create path.
- Course share ladder / trainer code / «إعلانات دورتك» (platform courses round).
- AI review memos (`agents/review-course`, `agents/vet-trainer` call DeepSeek ⇒ paid; not called from the dashboard until the dashboard has its own key and the founder says so).
- Learner course refunds (no platform path exists).
- Changes to the home tiles, the «ابدأ القرارات» cards, or other sections.

---

## 16) Decisions (expert review of 2026-10-30)

All twelve points were applied; where the fix differs from the review's wording, this is why:

1. **Legacy tabs and buttons (high).** Applied, and widened: besides the catalog decision buttons, the ledger's «تعديل» (its modal edits the price and the visible state and mirrors both to the platform without confirmation), «حذف» (deletes the platform course too), «انشر على المنصة» and the curriculum modal's `#vp_pub` are hidden too, because each is a money or publish write without `confirmed:true`. The old demand view is hidden as well: its two sources (program-request stats and chat questions) are both in the new «ما يطلبه الناس». Cost: a ledger title can no longer be edited from the dashboard this round (rare; the trainer builder replaces the ledger).
2. **Course page address (high).** Applied with D2's exact pattern. This needs a few shared lines in `v2-logic.js` and `index.html` (listed in §1.1 item 7) — the original "no edit to `parseSectionHash`" rule is lifted for these lines only.
3. **Platform needs A/B/C as same-round tasks (high).** Applied (§14), with D added. The dashboard part is not blocked by them; the main shots follow whatever the platform branch really has.
4. **Create sheet (high).** Decided now from the platform code, not at build time: the old path makes an active course that becomes public by itself once a lesson is added, so the new sheet uses a new route that creates an inactive draft (`is_active:false`) with no price. The price field is removed.
5. **Writes on old routes without `confirmed` (high).** Applied: visibility, bid, archive/delete, schedule, offers and create all have `/api/v2/courses/*` wrappers. The schedule's own platform flag `confirmed` (pin the date) is renamed `pin_schedule` on our side so it can never be confused with the confirmation. Trainer accept/reject, program accept/reject and stop-trainer stay on their existing routes: they decide about people, not money or publishing, and they already have on-screen confirmation sheets.
6. **Timer without `submitted_at` (medium).** Applied: grey «أُنشئت منذ …», no tone; tone and sort only on `submitted_at`.
7. **One repeated photo (medium).** Applied: CSS paper cover with the title's first letter; `courses.jpg` only as the course-page hero.
8. **Unknown checklist (medium).** Applied: the «القرار لك» block with two equal outline buttons, «أعد جلب الفحص» when the source failed, and no duplicate «افتح الدورة» on a ticket whose main button already opens it.
9. **Trainer flow (medium).** Applied: two actions per ticket, name opens the application, main button «اقبله وأرسل الاتفاقية» (the email is real), no deadline promise until D, «اطلب مستندًا» recorded as Platform need G.
10. **Unverified sentences (medium).** Checked now against the platform code: approval and rejection emails are real (`review_course_doc` ⇒ `dispatch_course_reviewed`), the cancel email and in-app notice are real (`_cancel_live`), but «النزاعات والاستردادات» does **not** list live-course refunds (consultations only) — so the cancel sheet shows the refund list from the response and links nowhere (Platform need F). The same check found that approving a price offer below the floor silently raises it to the floor; the offer sheet now says so.
11. **Inline styles in the legacy screen (medium).** Applied: `!important` allowed only inside `.v2co-legacy` / `html.v2co-legacy-modal #epModal`, an explicit list of inline-styled elements, old colour tokens remapped inside the frame, and a computed-colour check in shot 14.
12. **Tablet tables (medium).** Applied: live courses are cards below 1180px; the courses list has 4 columns on tablet; the shot script fails on any sideways scroll inside a `v2co-` element. (The review text was cut after "no horizont…"; this is the evident intent.)

