# Dashboard Overhaul Plan — D1–D9 (control-room «غرفة العمليات»)

Spec source: `../elprofessor/docs/launch-readiness-spec.md` (items D1–D9, round-2 founder notes 2026-07-02).
Scope of this doc: the **dashboard** app only (`dashboard-cloud/index.html` + `dashboard-cloud/dashboard-api.js` + `backend/app.py`), plus the **platform bridge contracts** it depends on (`../elprofessor/backend/routes/admin_bridge.py`, `.../conversations.py`, `.../experts.py`).

Prime directive check (from MEMORY): every block below must move the business toward a **paying transaction** or toward **measuring demand so we build the right paid thing**. D2 (demand) + D4 (courses = the product we sell) are therefore first. Nothing here is "measure only" — each area removes fake data, wires the real source, and adds the missing control.

---

## 0. Architecture you are building on (read once)

Two apps, one identity, joined by **email** + a shared **service secret**:

- **Dashboard UI** = a single static file `dashboard-cloud/index.html` (~3000 lines, self-contained: CSS + `MODULES` registry + `view*()` render functions + modals). No framework. Nav is data-driven from `MODULES` (index.html:297) via `renderNav()` (index.html:369) → `go(mod)` (index.html:386) → `renderView()` switch (index.html:391-427).
- **Dashboard data layer** = `dashboard-cloud/dashboard-api.js` — the `EP` object. `api()/get/post` (dashboard-api.js:36-64) attach `Authorization: Bearer <token>`. `EP.LOADERS` (dashboard-api.js:168) fetch each screen's data into `EP.data.<key>` and mirror to `window.<GLOBAL>` (e.g. `window.USERS`, `window.PTOPICS`). Views call `EP.ensure('<key>', reRender)` at the top and read `EP.data`/globals, falling back to in-file design arrays when the bridge is cold.
- **Dashboard backend** = `backend/app.py` (Flask + SQLite). Two kinds of routes:
  1. **Local SQLite** resources (dashboard-owned): `User` (auth/admins, app.py:125 — note `role` + `dashboard_role`), `Course` ledger (190), `Revenue/Expense/Campaign/Partner/Investment/...`, `Article` CMS (371), `Message` (388), `EscrowSession` (401), `Setting` (290).
  2. **Platform proxies** (`/api/platform-*`) that forward to the platform over `X-ELP-Metrics-Secret` via `_platform_proxy()` (app.py:1240). Config: `PLATFORM_API_URL` (app.py:1059), `PLATFORM_METRICS_SECRET` (app.py:1127). Auth gates: `@token_required` (451) + `@roles_required(...)` (469) + `is_last_admin()` (503).
- **Platform backend** = `../elprofessor/backend` (FastAPI + Mongo). Exposes `/api/bridge/*` guarded by the same secret (`admin_bridge.py`), plus `/api/admin/*`.

**Golden rule for this overhaul:** platform-owned truth (users, real courses, chat, topics, experts) is READ/WRITTEN through the **bridge**; dashboard-owned truth (finance ledger, CMS articles, contact messages, dashboard admins, settings, AI-team reports) lives in **SQLite**. Do not duplicate a source.

---

## 1. Current-state map (what exists vs what D1–D9 need)

| Item | Module id / view (file:line) | Loader / endpoint | State today | Gap vs spec |
|---|---|---|---|---|
| D1 Overview | `overview` `viewOverview` (index.html:984) | `dashboard` loader (dashboard-api.js:170) → `/api/dashboard`; inbox loader (381) | KPIs real; **"الوارد من المنصة" (`inbox`, index.html:430)** = only trainer-apps + program-requests (dashboard-api.js:381-417) | Inbox is thin; should also surface chat hand-offs / messages / course-requests (see D2+D4+D7). |
| **D2 Demand** | `analysis` `viewAnalysis` (index.html:822-850) | `analysis` loader (dashboard-api.js:184) → `/api/platform-chat-insights` (app.py:1167) → platform `compute_chat_insights` (conversations.py:335) | Shows total, by_segment, needs_expert, anon/authed, recent Qs, expert-opinion funnel. **No geo, no AI category classification, no gap detection, no filters.** | Add geo, AI categories+sub-categories, "demanded-but-unoffered" gaps, filters, analytical agent summary. |
| **D3 Users** | `users` `viewUsers` (index.html:852), `renderUsers` (872), `drawUser` (896), `addUserModal` (960) | `users` loader (dashboard-api.js:191) → `/api/platform-users` (app.py:1148); role write `EP.setUserRole` (926) → `/api/platform-users/{id}/role` (app.py:1187) | Role chips (admin/staff/member/investor), verify badge, trainer approve, add/edit/delete (create falls back local). **Dead duplicate `drawUserOld` (931-959).** | No **primary-role** distinct from tags, no **segment/tag** column or tag-by filter, no **assign-package**, no **promo/discount** control. Trainer/lawyer/expert not shown as roles. |
| **D4 Courses** | `courses` `viewCourses` (index.html:1059), 6 tabs (1079-1086), `renderCourses` (1104), `drawCourse` (1165), `courseVideoModal` (1251) | loaders `courses`/`course_offers`/`platform_courses`/`schedules` (dashboard-api.js:540-599); writes 1010-1027, 1285-1332 | Tabs: platform / إدارة / programs / trainers / offers / schedules. Publish/approve/bid/videos wired. **Videos are FLAT (`courseVideoModal` 1251) — no sections, no per-lecture questions.** Drive-import panel is wedged into the platform tab (index.html:1109). Offers tab live. | Duplicate "الدورات على المنصة" vs "دورات الإدارة" confusion; missing **sections + lectures + Titch questions authoring**; **course-request aggregation/stats** (live vs recorded vs "wants a course"); trainer-parity contract. |
| **D5 Experts/Trainers** | `team` `viewTeam` (index.html:2324), `tmAdmins`/`tmTrainers` (2321-2322), `teamModal` (2349) | `team`… **no dedicated loader** — `viewTeam` reads `EP.data.team` which is never populated by any LOADER; falls back to empty `TEAM_MEMBERS` (2320) | Shows admins + approved trainers as **names only**. **No experts, no specialties, no referral counts, no accounts, no ratings.** | Platform has a full experts directory (`experts.py`) + referral data (`consultations`) NOT exposed to dashboard. Need a trainers/experts management tab. |
| **D6 Topics/Blog** | THREE modules: `topics` `viewTopics` (1953), `news` `viewNews` (2040), `content` `viewContent` (1757) + `viewArticlesAuto` (1913, not in nav switch) | loaders `platformTopics` (261), `platformNews` (302), `content` (219), `platformArticles` (282) | Topics: research→AI-draft→publish to platform board. News: curated→publish. Content: CMS articles→site blog. `viewArticlesAuto` exists but is **orphaned** (no `MODULES` entry, not routed in renderView 391-427). `renderContentOther` news/media/pages tabs are **disabled stubs** (1849, arrays empty 1840-1842). | Spec wants ONE «المواضيع» with the full pipeline idea→news→topic→discussion→article→blog(SEO)→series, and two article streams (auto-features vs approved-topics). Today it's 3 disconnected modules + 1 orphan. |
| **D7 AI Team** | `ai` `viewAI` (index.html:2200), `renderAIDecisions` (2229) | none — `AI_DECISIONS=[]` (2228), responses hardcoded "قريبًا" (2202). `/api/ai/*` exist (app.py:3864-3915) but view ignores them. `ai` is `soon:true` in MODULES (320). | A single "coming soon" chat + empty decisions log. | Spec wants a **named AI-team**: one agent per business function, each writing a report into its section, a **master** aggregator, drill-down, and a **hand-off contract** from the platform chat sub-agents (P15). Nothing of this exists. |
| **D8 Foundation/Goals** | `foundation` `viewFoundation` (2368), `targets` `viewTargets` (2474) | `targets` loader (dashboard-api.js:639) → `/api/dashboard`; else fabricated `TARGETS` (index.html:2466) + empty `GOALS` (2469) | `TARGETS=[{يوليو..},{أغسطس..},{سبتمبر..},{أكتوبر..}]` fabricated (2466). `qPct` "16%" (2485) = 30÷187 derived from that fake array. | Clean fabricated months + "16% هدف الربع" → derive live or empty. |
| **D9 Settings** | `settings` `viewSettings` (2584), `renderRoles` (2646), `roleModal` (2656) | `settings` loader (610) → `/api/settings` (app.py:2872/2878, SQLite `Setting`) | FX + company data persist. **Roles section `ROLES_DEF` (2639) is a pure in-file design array** — add/edit/delete never persist; buttons 2FA/audit/backup are toasts (2635). No add-admin. | Need real add-another-admin (SQLite `User`), roles/permissions that actually gate modules, usage/audit — professional settings. |

Dead/misc to clean while here: `drawUserOld` (index.html:931-959, unused); orphan `viewArticlesAuto` (1913) — fold into D6; disabled news/media/pages tabs in `renderContentOther` (1849).

---

## 2. Cross-cutting foundations (build once, all areas use)

**F1 — bridge proxy helper is ready.** `_platform_proxy(method, path, params, json_body)` (app.py:1240) already factors the secret call. Every NEW dashboard proxy route below is ~6 lines using it. Keep `@roles_required('admin')` for mutations, `('admin','employee')` for reads (matches existing pattern at app.py:1150/1169).

**F2 — loader registration pattern.** Each new screen = (a) add key to `EP.data` init, (b) add `LOADERS.<key>` in dashboard-api.js, (c) view calls `EP.ensure('<key>', reRender)`. Follow `analysis`/`platform_courses` loaders verbatim.

**F3 — module registry + role-gating.** New/renamed modules go in `MODULES` (index.html:297) with `grp` and (optionally) `soon`. Non-admin visibility via `ROLE_NAV` (index.html:356). Add a route line in `renderView()` (391-427). This is the ONLY wiring needed to add a section.

**F4 — AI call path.** Dashboard already has `/api/ai/ask` (app.py:3870), `/api/ai/snapshot` (3864), `/api/ai/goals-advisor` (4208), `/api/ai/models` (3696). D2 classification and D7 agents reuse this LLM plumbing (server-side, key stays in backend) rather than calling models from the browser.

**F5 — audit log table (new SQLite).** Introduce `AuditLog(id, actor_email, action, target, meta_json, created_at)`. Every mutation route appends one row. Powers D9 "سجل العمليات" (currently a toast at app.py-less line index.html:2635) and D7 platform-mgmt agent. Small, unblocks several areas.

---

## 3. Per-area specs

Order of build inside this doc follows value: **D2, D4** first (highest), then D3, D5, D6, D7, D9, D8.

### D2 — Demand analysis (HIGHEST) «تحليل الطلب»

**Concept.** This is the "measure while you build" engine (Founder's Playbook framing in MEMORY). It must answer: who's asking, from where, for what, and **which demanded services we don't yet sell** — so D4/D5/D6 build against real demand, not guesses.

**Data source (already flowing, under-used).** Every chat turn (auth + anonymous) writes a `chat_insights` doc on the platform: `{question, profile, needs_expert, anonymous, created_at}` (conversations.py:218 and :314). `profile` is the silently-extracted `user_profile` whose schema (legal_search.py:244) already includes **`country` (egypt|saudi|uae|qatar|other|unknown)** and **`segment`** (individual/lawyer/trainer/author/student/company/prosecutor/…) plus `topic`, `need`, `title`. `compute_chat_insights()` (conversations.py:335) aggregates total/by_segment/needs_expert/anon/recent + the expert-opinion paid funnel — but **drops country and does no topical classification**. The pipe from platform→dashboard already exists: `/api/bridge/chat-insights` (admin_bridge.py:99) → `/api/platform-chat-insights` (app.py:1167) → `analysis` loader (dashboard-api.js:184) → `viewAnalysis` (index.html:822).

**Platform-side changes (`../elprofessor/backend`):**
- Extend `compute_chat_insights()` (conversations.py:335) to also return:
  - `by_country: [{country, count}]` (group on `profile.country`; data already stored).
  - `by_category` + `by_subcategory`: run an **AI classifier** over the recent questions. Cheap + robust design: a scheduled classifier (see below) writes `category`/`subcategory` back onto each `chat_insights` doc; `compute_chat_insights` then just groups the stored labels (no per-request model cost).
  - `unmet: [{label, count, sample_question}]`: categories whose questions did NOT map to an offered service (see gap detection).
- **New classifier job** `classify_chat_insights(db, limit)` (put in `conversations.py` or a new `services/demand_classifier.py`): pull docs missing a `category`, batch them to the LLM with a fixed **legal taxonomy** (e.g. عمل/أحوال شخصية/عقاري/جنائي/تجاري/إداري/ملكية فكرية/…) + sub-category + a mapped `intent` (صياغة / مراجعة / بحث معلومة / دورة / رأي خبير / تسجيل / آخر). Persist labels back. Expose `POST /api/bridge/chat-insights/classify` (guarded) so the dashboard can trigger it and n8n can schedule it daily.
- **Gap detection:** keep a small `OFFERED_INTENTS`/`OFFERED_CATEGORIES` set (drafting, review, library-search, courses, expert-opinion). Any classified `intent`/`category` NOT in the set with count ≥ N → an `unmet` row. This is literally "الخدمات المطلوبة اللي إحنا مش مقدّمينها".

**Dashboard-side changes:**
- Proxy already exists; extend the `analysis` loader (dashboard-api.js:184) to pass through the new fields and add a trigger method `EP.runDemandClassify()` → `POST /api/platform-chat-insights/classify` (new thin proxy in app.py next to line 1167, using `_platform_proxy`).
- Rebuild `viewAnalysis` (index.html:822) into a filterable analytics view:
  - KPI row (reuse existing 4 KPIs, add a 5th "دول نشطة").
  - **Filter bar** (reuse `.filterbar`/`.chip` pattern from `renderInbox` index.html:452): filter by segment, country, needs_expert, category, timeframe.
  - **Panels:** "الطلب حسب الشريحة" (exists 843), NEW "الطلب حسب الدولة" (bar list, same markup), NEW "التصنيف بالـAI (فئة ← فئة فرعية)" (grouped list with counts + drill to sample questions), NEW "خدمات مطلوبة لا نقدّمها" (`unmet` rows, styled as a gold-bordered `.policy` call-to-action linking to D4/D6), and "أحدث الأسئلة" (exists 846).
  - **Analytical agent summary** at the top: reuse the D7 "incoming-analysis" agent (below) to render a 3–5 bullet "رايحين فين / جايين منين / عايزين إيه" narrative from the aggregates.

**Reuse vs new.** Reuse: the whole bridge pipe, `viewAnalysis` scaffold, `.filterbar`/`.chip`/bar-list markup, `SEG_LABEL` (index.html:821). New: platform classifier + `by_country`/`by_category`/`unmet` in `compute_chat_insights`, one classify proxy route, filter state + 3 panels in the view.

### D4 — Courses (HIGHEST) «الدورات والتدريب»

**Resolve the "duplicate/broken tab".** The two tabs are legitimately different but badly labelled: `platform` = live native catalog from Mongo (`csPlatformCourses` dashboard-api.js:589) and `courses` = the dashboard SQLite ledger (`csCourses` :540). The confusion + the "part shows, part doesn't" is because (a) the Drive-library import panel is injected INTO the platform tab body (`renderCourses` index.html:1109-1111,1116) and (b) both tabs claim the title "الدورات على المنصة" (index.html:1080-1081, header 1106/1120). Fixes:
  - Rename tabs to **«الكتالوج (على المنصة)»** and **«سجل الإدارة»**; OR (preferred) **merge** — treat the SQLite ledger as a financial mirror shown only inside a course's drawer ("الإيراد/النسبة"), and make the platform catalog the single course list. This kills the duplication the founder saw.
  - Move the Drive-import panel OUT of the courses list into D6/library or a dedicated collapsible in Settings/Knowledge (it's a RAG concern, not a course).
  - `courseTab==='pricing'` is force-reset (index.html:1066) — remove the dead branch.
  - Confirm **عروض الأسعار**: live and correct (`course_offers` loader dashboard-api.js:564, decide `EP.decideCourseOffer` :965 → app.py:1393). The per-course "فعّل المزايدة" toggle appears BOTH in the offers tab (index.html:1150) and the platform drawer (1181) — keep the drawer one, drop the duplicate toggle block in the offers tab body to de-duplicate.

**Full LMS create/manage with sections + lectures + questions.** Platform course model is a flat `videos[]` (each = title/video_url/order/is_preview, added via `append_course_video`, admin_bridge.py:660) **plus** a Titch `curriculum.lessons[]` (bodies + quizzes, gated; courses.py:1344). There is **no section grouping and no manual quiz authoring** through the dashboard. Needed:
- **Platform-side (`admin_bridge.py` + `courses.py`):**
  - Add an optional `section` (title + order) to each video/lesson, or a `curriculum.sections: [{id,title,order,lessons:[...]}]` structure. Minimal path: add `section_title`/`section_order` fields on the video doc and group in `bridge_course_detail` (admin_bridge.py:632). Cleaner path: introduce `sections[]` and migrate `videos[]` into `sections[].lessons[]`.
  - New bridge routes: `POST /bridge/courses/{id}/sections`, `PUT/DELETE /bridge/courses/{id}/sections/{sid}`, and extend the video add (660) to accept `section_id`.
  - **Questions via «علّمني» (Titch):** reuse `POST /bridge/courses/generate` (admin_bridge.py:857, `EP.generateCourse` dashboard-api.js:1291) to generate a quiz for a lecture from its material; add `POST /bridge/courses/{id}/lessons/{lid}/questions` for manual add/edit of quiz items. Store on the lesson's `quiz` (same shape the learner curriculum already reads, courses.py:1344).
- **Dashboard-side:** replace flat `courseVideoModal` (index.html:1251) with a **curriculum builder**: a section list, each with "+ محاضرة" (title + Drive/YouTube link + preview flag) and "+ أسئلة (علّمني)" (either generate via Titch or hand-author). Reuse the existing add-video call for the lecture link, add `EP.addSection/EP.addLessonQuestions`. Show the tree read-only in the course drawer.

**Trainer parity (contract, not dashboard code).** The trainer's own management lives on the **platform** (their `/app` trainer panel), not this dashboard. Contract: the same section/lecture/questions operations must be callable by an **approved trainer for their own courses** via authenticated platform endpoints (not the secret bridge). Action item handed to the platform-chat plan: expose `POST /courses/{id}/sections|lessons|questions` gated by `is_expert()`/ownership (mirror `append_course_video`'s trainer path courses.py:1297). This doc's job is only to keep the **dashboard admin** and **trainer** writing to the SAME course document shape so parity is automatic.

**Request routing + stats (course demand loop).**
- Today: `programs` tab = existing-catalog access requests (`program_requests`, account.py:89) and `trainers` tab = trainer applications; both surface via the `inbox` loader (dashboard-api.js:381-411) with approve/reject.
- Spec wants three demand buckets aggregated with counts: (1) **طلب دورة معيّنة** (many want course X), (2) **طلب عمل دورة مسجّلة**, (3) **"عايز دورة" (wants a course that doesn't exist)**. Sources:
  - (1) = existing `program_requests` grouped by `program_id`/title → add `GET /bridge/program-requests/stats` returning `[{title, count}]`. New dashboard panel "أكثر الدورات طلبًا".
  - (3) = derive from **D2** demand where `intent=='course'` and no matching catalog course → feed the D4 "طلبات جديدة مقترحة" panel from the same `unmet`/classified insights. This closes the loop: chat demand → dashboard sees "20 person asked for a labor-law course we don't have" → one click "أنشئ دورة".
- Route each request kind to its home (already partly done): course/program → courses module, trainer → team/experts (D5). Keep the `inbox` triage `dest` mapping (dashboard-api.js:389/403) as the single router.

**Reuse vs new.** Reuse: all existing course loaders/writes/tabs, offers flow, schedules flow, `generateCourse` (Titch), video-add. New: platform sections model + routes, manual questions route, program-request stats route, D2-fed "wants a course" panel; dashboard curriculum-builder modal; tab rename/merge + de-dup.

### D3 — Users «المستخدمون»

**Primary-role vs tag/classification.** Platform role model (see `../elprofessor/backend/routes/experts.py:3` note) = 3 system roles (member/staff/admin, + investor) and **trainer/expert is a capability (`trainer_status`), not a role**; **segment (محامي/طالب/شركة…) is a behaviour-derived TAG** (auth.py:503, extracted into `user_profile.segment`). So:
- Keep the role chips (`ROLES_LIST` index.html:809, write via `EP.setUserRole` :926) as the **primary role** control.
- Add a **tag/segment column + filter** using the chat-derived `segment`. Requires the bridge to return it per user: extend `GET /bridge/users` (admin_bridge.py:83) to include each user's latest `profile.segment` (join from `conversations.user_profile` or `chat_insights`), and a manual override `tags: []`. Surface in `users` loader (dashboard-api.js:191) → new column in `renderUsers` (index.html:872) + tag chips in the filter bar (reuse the trainer-chip pattern at :878). "Show/hide by tag" = the filter. This directly answers "فين المدرب/المحامي/الخبير" — they show as tags/capabilities, filterable.

**Per-user controls.**
- **Assign a package:** add a "الباقة" control in `drawUser` (index.html:896). Package list already loaded (`packages` loader dashboard-api.js:615, `/api/packages`). Write via new bridge `POST /bridge/users/{id}/plan {plan_id}` (mirror the role write at admin_bridge.py:111) → new dashboard proxy `POST /api/platform-users/{id}/plan` (next to app.py:1187). `EP.setUserPlan`.
- **Promo/discount:** two honest options — (a) **delegate to financials**: a link/button "أنشئ خصمًا في الماليات" opening the packages/pricing area (cleanest, avoids a half-built coupon engine); or (b) a real **coupon** entity if we commit: SQLite `Coupon(code, percent|amount, scope, expires)` + a bridge to apply at checkout. **Recommend (a) for launch** (label the button clearly, no fake success), build (b) only when a paid funnel needs it. Do NOT render a fake "تم إصدار الخصم" toast.

**Cleanup.** Delete dead `drawUserOld` (index.html:931-959).

**Reuse vs new.** Reuse: users loader, role write, packages loader, filter/chip markup, `SEG_LABEL`. New: bridge segment/tags on `/bridge/users`, plan-assign bridge+proxy+`EP.setUserPlan`, drawer package control, tag column/filter, promo delegation link.

### D5 — Experts & Trainers «الخبراء والمدربون»

**Answer "where are trainers, where are experts".** On the platform an **expert == an approved trainer** (`experts.py:3`, `is_expert()` :48 = `trainer_status=="approved"`). The nuance the founder feels: a trainer *teaches courses*; an expert *takes referrals/consultations*. Same person, two hats. Today the dashboard `team` view (index.html:2324) shows only names and **has no loader at all** (`EP.data.team` is never populated), so specialties/referrals/accounts are invisible.

**Platform-side new bridge `GET /bridge/experts`** (in `admin_bridge.py`, guarded): return the directory built from `experts.py` data + referral counts:
```
[{ email, full_name, expertise:[..], bio, trainer_status,
   rating_avg, rating_count,            # experts.py rating_for() :72
   online, last_seen_at,                # experts.py presence
   referral_count,                      # count db.consultations by expert_email (consultations.py:371)
   courses_count, students_count }]     # from db.courses by instructor
```
Referrals = group `db.consultations` on `expert_email` (field present, consultations.py:111/303/371). Specialties/rating/presence already maintained by `experts.py`.

**Dashboard-side:**
- New loader `experts` (dashboard-api.js) → new proxy `GET /api/platform-experts` (app.py, `_platform_proxy` to `/bridge/experts`).
- Rebuild `team` module (index.html:2324) — rename to **«الخبراء والمدربون»**, give it tabs: **الخبراء** (directory: name, specialties, rating, referrals, online, account link) · **المدربون** (approved trainers + their courses/students) · **الفريق الإداري** (existing admins, keep). KPIs: عدد الخبراء / أكثر خبير إحالات / مدربون معتمدون / متصلون الآن. Reuse `.row`/`.drawer` list markup. Wire trainer approve/reject from here (it already flows through the `inbox`/team dest at dashboard-api.js:389).
- Drill-down drawer per expert: specialties, referral history, ratings, "اعرض الحساب" → deep-link to D3 user.

**Reuse vs new.** Reuse: `experts.py` (data already exists), consultations collection, team view scaffold, trainer-decision flow. New: `/bridge/experts` aggregation, dashboard proxy+loader, retabbed team view.

### D6 — Topics unification «المواضيع» (one section, full pipeline)

**Today = 3 modules + 1 orphan.** `topics` (index.html:1953, platform discussion board), `news` (2040, curated legal news), `content` (1757, CMS→site blog), and orphaned `viewArticlesAuto` (1913, auto platform-feature articles — has no `MODULES` entry and isn't in `renderView` 391-427). Loaders: `platformTopics` (dashboard-api.js:261), `platformNews` (302), `content` (219), `platformArticles` (282).

**Target = ONE «المواضيع» with the pipeline** idea → (خبر) → موضوع → نقاش → مقالة → مدونة (SEO, بموافقة) → (سلسلة اختيارية), and **two article streams**:
- **آلي (features):** platform-feature / value-of-legal-training / human-tempered-AI articles → auto-generate + auto-publish. Backed by `platformArticles` (dashboard-api.js:282) + platform `POST /bridge/articles/generate-feature` (admin_bridge.py:1008) + `daily-run` (1041). NOTE: auto-publish for features was paused to draft-pending in the dashboard branch — spec says features MAY stay auto; keep feature stream auto, gate only sensitive/topic-derived ones.
- **من المواضيع (approved):** approved topic / news→topic / user-submitted → "اعمل مقال" → SEO → publish-on-approval → site blog (`content` CMS, `EP.createArticle`/`publishArticle` dashboard-api.js:1029/1043 → SQLite `Article` app.py:371, which syncs to elprofessor.net).

**Implementation:**
- Make `المواضيع` the single module; give it **tabs**: مواضيع (board) · الأخبار (curated + "حوّل لموضوع", already exists via `derive-topic` admin_bridge / app.py:1856) · مقالات آلية (fold the orphan `viewArticlesAuto`) · مدونة الموقع (the `content` CMS). Fold `news`/`content`/`articles-auto` `MODULES` entries into tabs of `topics`; remove the standalone entries (index.html:311-313) and the orphan.
- Wire the **flow buttons** end-to-end so a single item can walk the pipeline: news → "حوّل لموضوع" (exists) → topic → "اعمل مقال" (new button calling `EP.createArticle` with the topic's `ai_answer` as body) → article draft → "اعتمد وانشر (SEO)" → site. Add optional "ولّد سلسلة" (calls the daily-run/generate with a series seed).
- Remove disabled media/pages stubs (`renderContentOther` index.html:1849, arrays 1840-1842) or clearly gate as "قريبًا".

**Reuse vs new.** Reuse: all 4 loaders/views + their platform routes (topics/news/articles/content) — this is mostly **re-composition into tabs**, not new backend. New: the cross-stage buttons (topic→article, news→topic already exists, series seed) and MODULES/nav consolidation.

### D7 — AI Team «الفريق (AI Team)»

**Concept.** Replace the empty `ai` "coming soon" (index.html:2200, `soon:true` at 320) with a **named AI team**: one agent per business function, each renders a **report** in its section; a **master agent** aggregates; drill-down to each. Agents also **receive hand-offs** from the platform chat sub-agents (P15 contract).

**Agents (function → data it reads → report):**
| Agent | Reads | Output |
|---|---|---|
| Articles | `platformArticles`/`content` + D2 topics | drafts to approve, coverage gaps |
| Automation-spotter | AuditLog (F5) + repetitive actions | "these ops can be automated" + a proposed n8n flow |
| Sales | consultations funnel, offers, course enrolments | leads, stuck deals, next actions |
| Marketing | `campaigns` (dashboard-api.js:504) + D2 demand | which segment/country to target |
| Platform-mgmt | metrics, users, courses health | anomalies, approvals waiting |
| Topics | D2 demand + topics board | next topics/series to write |
| Incoming-analysis | **D2 chat-insights** (shared) | "رايحين فين/جايين منين/عايزين إيه" narrative |
| Dev | error logs / health (`/api/health` app.py:5497) | bugs, tech debt |
| Finance | `/api/finance/summary` (3915), `/api/dashboard` | cashflow, forecast, risks |
| **Master** | all agent reports | one-screen company picture + top 3 actions |

**How they run.** Two modes: **on-demand** ("شغّل التقرير" per agent + "حدّث الصورة الكاملة" for master) and **scheduled** (n8n hits a new `POST /api/ai/agents/run?agent=<name>` daily). Each agent = one server-side LLM call (reuse `/api/ai/ask` plumbing app.py:3870 + a per-agent prompt + its data bundle). **Outputs live in a new SQLite table** `AgentReport(agent, summary, bullets_json, actions_json, created_at)` — so reports persist, are cheap to render, and are auditable. Endpoints: `GET /api/ai/agents` (latest report per agent), `POST /api/ai/agents/run` (regenerate one/all).

**Hand-off FROM the platform chat sub-agents (P15 contract).** The chat plan defines a master chat agent delegating to sub-agents (topics/editor/library/courses/registration/unknown). The contract with THIS dashboard:
- Registration/unknown chat sub-agent → writes a **Message** (`/api/messages` app.py:5045, SQLite `Message` 388) → surfaces in `messages` module (index.html:2896). ("استنى هرد عليك / سجّل طلبك" → «الرسائل».)
- Each chat sub-agent's structured demand → the `chat_insights` doc (already) → D2 → the matching D7 agent (topics→Topics agent, registration→Sales/Incoming, etc). So the "AI team member in the dashboard" for a function is fed by the corresponding chat sub-agent via the shared insights + messages tables. No new transport needed beyond F5 audit + the messages/insights pipes that already exist.

**Reuse vs new.** Reuse: `/api/ai/*` LLM plumbing, all existing data loaders as agent inputs, `messages`/`chat_insights` as the chat hand-off. New: `AgentReport` table + `/api/ai/agents[/run]`, per-agent prompts, the D7 view (agent cards → report drawer, master summary on top). Flip `ai` off `soon`.

### D9 — Settings «الإعدادات» (professional)

- **Add another admin (real).** `renderRoles`/`ROLES_DEF` (index.html:2639-2668) is an in-file array that never persists. Wire the Settings "الأدوار والصلاحيات" section to the real SQLite `User` table: `/api/users` GET/POST already exist (app.py:2066/2075) with `role`+`dashboard_role` (User model 125). Add a "+ مدير/موظف" modal that POSTs a real dashboard user (email + temp password + role), guarded by `is_last_admin()` on demotion/delete (503). List real admins/employees from `/api/users`.
- **Roles/permissions that actually gate.** Define a `permissions` map per role (which `MODULES` + which actions). Persist as a `Setting` row (`Setting` model app.py:290, `/api/settings` 2872/2878) or a small `Role` table. Enforce on the **frontend** via `ROLE_NAV` (index.html:356) already, and on the **backend** via `@roles_required` (469) — extend to read persisted permissions instead of hardcoded role lists.
- **Usage/audit.** Wire the "سجل العمليات (Audit Log)" button (currently a toast, index.html:2635) to real `AuditLog` (F5): `GET /api/audit`. Add a usage panel (AI calls from `AILog` app.py:296, logins, actions/day).
- **Real controls, no fakes.** 2FA/backup buttons (2616-2618): either implement or hide behind "قريبًا" honestly. FX + company data already persist (keep).

**Reuse vs new.** Reuse: `/api/users`, `/api/settings`, `is_last_admin`, `roles_required`, `AILog`. New: `AuditLog` table + `/api/audit`, persisted permissions + backend enforcement, add-admin modal, usage panel.

### D8 — Foundation/Goals cleanup (small)

- Delete fabricated `TARGETS` (index.html:2466) → `const TARGETS=[]`. This alone removes يوليو/أغسطس/سبتمبر AND the derived **"16%"** (`qPct` computed 30÷187 at index.html:2485 collapses to 0/empty). `GOALS` already `[]` (2469).
- `viewTargets` already prefers live `EP.data.targets` (dashboard-api.js:639 → `/api/dashboard` forecast/monthly) and the AI goals-advisor (index.html:2507 → `/api/ai/goals-advisor` app.py:4208). With the fake array gone it shows live-or-empty honestly.
- Audit `viewFoundation` (index.html:2368) for any remaining design constants (capital/tools arrays are already emptied at 2360-2363) — leave the section, ensure empty-states, no fabricated capital/status.

**Reuse vs new.** Pure cleanup + rely on existing live loaders. No new backend.

---

## 4. Platform ↔ Dashboard data contracts (consolidated)

All bridge calls carry `X-ELP-Metrics-Secret` (dashboard `_platform_proxy` app.py:1240 → platform `_guard` in admin_bridge.py). Join key = **email**.

| Concern | Platform (source, FastAPI/Mongo) | Dashboard proxy (Flask) | Loader / view |
|---|---|---|---|
| Chat demand (D2) | `chat_insights` coll; `compute_chat_insights` conversations.py:335; **+classifier (new)** `POST /bridge/chat-insights/classify` | `/api/platform-chat-insights` app.py:1167; **+`/classify` (new)** | `analysis` dashboard-api.js:184 → `viewAnalysis` |
| Users + segment/tag/plan (D3) | `/bridge/users` admin_bridge.py:83 **(+segment/tags/plan, extend)**; role `/bridge/users/{id}/role` :111; **plan `/bridge/users/{id}/plan` (new)** | `/api/platform-users` app.py:1148; `.../role` :1187; **`.../plan` (new)** | `users` :191, `EP.setUserRole` :926, **`EP.setUserPlan` (new)** |
| Courses catalog + curriculum (D4) | `/bridge/courses` :460, detail :632, videos :660, schedules :696, offers :420, generate(Titch) :857, approve/reject :1117/1131; **+sections/questions routes (new)** | existing `/api/platform-courses*` app.py:1412-1543; **+sections/questions proxies (new)** | `platform_courses`/`schedules`/`course_offers` :564-599; writes :1010-1027,1285-1332 |
| Course-request stats (D4) | `program_requests` account.py:89; **`/bridge/program-requests/stats` (new)** | `/api/platform-program-requests` app.py:1351; **+`/stats` (new)** | `inbox` loader :381; new stats panel |
| Experts/Trainers (D5) | `experts.py` directory + `expert_ratings` + `consultations` referrals; **`/bridge/experts` (new)** | **`/api/platform-experts` (new)** | **`experts` loader (new)** → retabbed `team` view |
| Topics/News/Articles/Blog (D6) | topics `topics.py:548-650`; news `derive-topic`; articles `generate-feature`/`daily-run` admin_bridge.py:1008-1107 | existing app.py:1695-1863; content CMS `/api/content/*` (SQLite `Article`) | `platformTopics`/`platformNews`/`platformArticles`/`content` :261-302,219 |
| AI-team reports (D7) | reads platform data via existing bridges; chat hand-off via `chat_insights` + `Message` | LLM via `/api/ai/*` app.py:3864-3915; **`/api/ai/agents[/run]` (new)** + `AgentReport` (new SQLite) | new `ai`/team view |
| Chat hand-off / messages (D7/P15) | chat sub-agents POST contact → | `/api/messages` app.py:5045 (SQLite `Message` 388) | `messages` :365 → `viewMessages` 2896 |
| Dashboard admins/roles/audit (D9) | — (local) | `/api/users` 2066/2075, `/api/settings` 2872/2878, **`/api/audit` (new)** | Settings view 2584 |

Failure mode is uniform: proxies return 502/503 on secret-unset or platform-down; loaders set `EP.state.<key>='error'`; views render the amber retry `.policy` banner (pattern already in every view, e.g. index.html:835,857,1071). Keep it.

---

## 5. Ordered, shippable phases (each = branch + PR + verify, deploy only on «انشر»)

Sequencing rule: highest business value first (D2 demand → D4 courses), then the areas that unblock them (D3/D5 feed D4/D2), then composition (D6/D7), then hygiene (D9/D8). Each phase is independently shippable.

- **Phase A — D2 demand analysis, part 1 (geo + filters).** Platform: add `by_country` to `compute_chat_insights` (data already stored). Dashboard: filterable `viewAnalysis` + country panel. Ships value immediately with zero new AI cost. *Verify: real chat rows show country + filters work.*
- **Phase B — D2 part 2 (AI classification + gap detection).** Platform: `classify_chat_insights` job + `/bridge/chat-insights/classify` + `by_category`/`unmet`. Dashboard: category panel + "خدمات مطلوبة لا نقدّمها" + trigger button + n8n daily schedule. *Verify: labels persist, unmet list populated.*
- **Phase C — D4 courses cleanup + de-dup.** Rename/merge the two course tabs, move Drive-import out, drop dead `pricing` branch + duplicate bid toggle, confirm offers. Frontend-only, low risk, removes the visible "broken tab". *Verify: one clear catalog, offers still decide.*
- **Phase D — D4 curriculum builder (sections + lectures + Titch questions).** Platform sections/questions model + routes; dashboard curriculum-builder modal replacing flat video modal; reuse Titch generate. *Verify: build a course with 2 sections, add lecture link + generated quiz, learner curriculum reads it.*
- **Phase E — D4 course-request loop.** `program-requests/stats` + D2-fed "wants a course" panel + one-click create. *Verify: aggregated counts + create-from-demand works.*
- **Phase F — D3 users (primary-role + tags + assign-package + promo delegation).** Extend `/bridge/users`, add plan-assign bridge/proxy, drawer controls, tag column/filter; delete `drawUserOld`. *Verify: tag filter shows lawyers/trainers; assign a package writes through.*
- **Phase G — D5 experts/trainers.** `/bridge/experts` + proxy + loader + retabbed team view (experts/trainers/admin). *Verify: an approved trainer shows specialties + referral count.*
- **Phase H — D6 topics unification.** Fold news/articles-auto/content into tabs of one «المواضيع»; wire cross-stage buttons; remove orphan + stubs. *Verify: news→topic→article→blog walk works end-to-end.*
- **Phase I — D7 AI team.** `AgentReport` table + `/api/ai/agents[/run]` + per-agent prompts + view (agents + master). Flip `ai` off `soon`; wire chat hand-off (messages/insights already flow). *Verify: run master, get a real aggregated report from live data.*
- **Phase J — D9 settings (add-admin + real roles/permissions + audit) and D8 cleanup.** `AuditLog` + `/api/audit`, add-admin modal on real `User`, persisted permissions enforced by `roles_required`; delete fabricated `TARGETS`. *Verify: create a second admin, demote guarded by last-admin; no fake months/16%.*

(F5 AuditLog is prerequisite for I's automation-spotter and J's audit — introduce it at the start of Phase I or as a tiny Phase 0.)

---

## 6. "Measure while you build" (instrumentation, per Founder's Playbook)

- D2 is the measurement backbone — ship it first so every later phase is validated against real demand, not opinion.
- F5 `AuditLog` = the internal measurement (what admins actually do → what to automate in D7).
- Track the **paid funnel** explicitly in D2/D7: `expert_opinions.requested→paid` (already in `compute_chat_insights` :374) and course enrolments. First paid transaction = MVP-exit proof; the dashboard should show it on Overview.

---

## 7. Open questions for the founder

1. **D4 tabs — merge or rename?** Merge (SQLite ledger becomes a drawer-only financial mirror, one catalog) vs keep two clearly-renamed tabs. Merge is cleaner but touches the finance mirror.
2. **D4 sections model — minimal (`section_title` on each video) or structured (`sections[].lessons[]` migration)?** Structured is correct long-term but needs a Mongo migration of existing `videos[]`.
3. **D3 promo/discount — delegate to financials (recommended, no coupon engine) or build a real `Coupon` entity now?** Depends on whether a discounted paid funnel is imminent.
4. **D5 — do we treat "expert" and "trainer" as one entity with two hats (matches platform model) or force a visible split?** Recommend one entity, two capability tags.
5. **D6 auto-features — keep fully auto-publish, or draft-pending like the current dashboard branch?** Spec leans "features auto, sensitive by approval"; confirm the line.
6. **D7 agent cadence + cost** — daily scheduled for all agents, or on-demand only until traffic justifies the LLM spend?
7. **RAG/Drive** — where does the Drive-import panel (currently mis-placed in courses) belong: Knowledge, Settings, or D6 library? (Founder still owes the Drive folder share.)
