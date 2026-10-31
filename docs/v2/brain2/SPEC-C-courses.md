# Courses from the dashboard + their brain + trainer share: build spec

**Founder (2026-10-31):** «خلص كل ما يتعلق بالدورات الأول … ويكون في مقدرتنا الإنشاء والتعديل للدورة والمحتوى من الداشبورد والمخ بتاعها».

## Sources

**Platform contract (binding):** `_reference/elprofessor-platform-walkthrough/PARALLEL.md`:
- the section «جسر محرّر الدورات (جلسة الأبواب 2026-10-31)», which covers the shared `course` shape and routes 1–12 under `/api/bridge/courses2…`;
- the section «نسبة المدرّب جاهزة», which covers `/api/bridge/trainer-share[/{email}]` and `/api/bridge/trainer-share-rules`.

Read both sections in full.

**Platform code:** branch `pillars-courses@20da444`, which sits on main 29f1fa6. It is not published yet. Everything runs behind `COURSES_V2_ENABLED`; when the flag is off, every route returns 404.

## C1: Course editor in the dashboard

The editor lives in the «الدورات والمدرّبون» section. Its files are `v2s/courses.js` and `backend/v2_courses_routes.py`, plus a new file `backend/v2_courses2_routes.py`.

**Proxies**
- Path: `/api/v2/courses2/*` → `/api/bridge/courses2/*`.
- Access is admin only. When `DASH_V2_ENABLED` is off, return 404.
- Send `no-store`.
- For every write, set `by` from the token (the admin email) and require `confirmed:true` from the browser.
- Pass the platform's Arabic `detail` through as `error`.
- Treat no reply or a 502/504 as `{no_reply:true}`.
- Strip any price or pricing field from request bodies (the bridge ignores them anyway).
- Preview POST and `brain/draft` send no `confirmed`.

**Screens** (new look, same style as the section)
1. **List.** Merge the `courses2` list with the existing board. Show the status chip `status_ar`, the kinds, the lesson count and the open notes.
2. **«أنشئ دورة» sheet.**
   - Fields: title, plus an owner, which is either a trainer email or «دورة من المنصّة».
   - Send `idem_key` = a uuid generated in the browser, sent once.
   - After the course is created, open it.
3. **Course page.** It has these tabs:
   - **«البيانات»:** title, subtitle, description, cover (https), level, and outcomes as a list.
   - **«الهيكل»:** units and lessons.
     - Add, rename, reorder and delete, then save with the structure PUT.
     - A new lesson needs a kind: «تفاعلي / مسجّل / مباشر».
     - Deleting a lesson with content opens a confirm sheet.
     - Show the 409 text as returned.
   - **«الدروس»:** pick a lesson, then edit it by kind.
     - **Interactive:**
       - A block list: add a block by type from a picker with the Arabic type names, delete, and move up/down.
       - Each block has a form for its main fields. For any other field, an «متقدّم» textarea holds the block JSON.
       - Lesson fields: `time`, `for`, `hero`, `motion`.
       - «عاين» does a preview POST without saving and shows a simple read-only render of the blocks.
       - «احفظ» opens a confirm sheet, then does the PUT.
       - Show 400 detail text as returned.
     - **Recorded:**
       - Video, either as an upload or as a link:
         - Upload: route 12. If it returns `configured:true`, upload with the browser TUS protocol: chunked PATCH to `upload_url` using the returned headers, with a progress bar. If it returns `configured:false`, only the link field is shown.
         - Link: a pasted link (YouTube, Drive or mp4).
       - Other fields: `duration_seconds`, `is_preview`, chapters `{t, title}`, checkpoints `{t, question, options[{text, ok, explanation}]}`, summary (up to 3 lines) and transcript.
     - **Live:** `starts_at`, `duration_min`, `zoom_link`, `recording_url`, `status`, and an optional quiz.
   - **«المراجعة والنشر»:**
     - Show `gaps`, written as «ينقصها: …», or «جاهزة» when there are none.
     - Show `notes`, with `summary_ar`.
     - «أرجِعها بملاحظات» (only when status is `review`): pick one or more targets and write a note for each, then confirm.
     - «انشر»: confirm sheet. A 422 text from the platform is shown as returned.
     - «أوقفها» (only when status is `published`).
4. **«اطلب من المساعد» box** in each lesson editor and on the course page:
   - Kinds: «حوّل إلى نشاط قرار», «اقترح عناوين أقصر», «اكتب نص فيديو», «سؤال حر», «حوّل مادتي إلى دروس» (paste text of 80+ characters).
   - Use route 11. The result is shown as a draft. «أضفه إلى الدرس» puts it into the editor without saving; the founder then saves.
   - For `from_material`, «أنشئ الهيكل منها» does a structure PUT and then one lesson PUT per lesson, with one confirm sheet for all of them.
5. **Old screen.** The old «تعديل الدروس من «كل السجلات»» link becomes «حرّر الدورة» and opens the new editor. The old screen stays under «كل السجلات».

**Seeded story courses.** For courses whose slug is in the platform's seeded list (start with `marketing-basics`; also show a warning when a course is not in `courses2` but has a story), the editor shows this line:
«هذه الدورة مكتوبة في ملف أساسي؛ أي تعديل من هنا قد يُستبدل عند تحديث الملف.»

**Copy rules:** plain Arabic, gender-neutral, no «يقوّم», no prices, no mention of refunds or guarantees.

**Tests:**
- Proxy auth, the flag, `no-store`, `confirmed` and `by` from the token.
- Price fields are stripped.
- Error pass-through and `no_reply`.
- Node tests for the block list helpers, the structure diff and the TUS chunk planner.
- Shots on desktop and mobile: list, create, data, structure, interactive editor with preview, recorded editor, review tab, assistant draft.

## C2: The brain writes lessons + trainer share screen

**C2a. Producer `course_lesson_draft`**
- Fills the hook in `producers_biz.py`.
- **Gather:**
  - Read `GET /api/bridge/courses2` and then each course.
  - Keep lessons whose `state` is `draft` and that have no blocks or no transcript.
  - Limit: 3 per run, only courses in status `draft` or `changes`.
  - Facts: course meta, unit/lesson titles and the lesson kind.
- **Prompt:**
  - For an interactive lesson: blocks in the platform's JSON shape. Allowed types: `objectives, text, situation, decision, recall, quiz, summary, example, cards`. Keep it short: 4–7 blocks.
  - For a recorded lesson: `summary` (up to 3 lines) and `transcript`.
- **Validate:**
  - Check the JSON shape.
  - Then POST the lesson body to the preview route. That route is a validation-only call that writes nothing. A 400 there gives a `failed` row with its detail.
  - The engine honesty checks apply to the text fields.
- Locked to «يسألني». Label «مسودة درس». Approve button «أضف الدرس».
- **Apply:** lesson PUT with `confirmed:true` and `by` = actor.
- It uses the dashboard `ai_call` (switchable model and daily cap), not the platform assistant.

**C2b. Trainer share screen** in the «المدرّبون» tab of the courses section
- **List:** from `/api/v2/trainer-share`, which proxies to the bridge. Each row shows the name, `base_pct`, `ads_bonus_pts`, the period and the reason.
- **Row sheet:**
  - Fields: «النسبة الأساسية» 35–65, «زيادة الإعلانات» 0–25, «من» / «إلى», and «السبب» (required).
  - It shows the total «نصيب المدرّب الآن: X٪ · المنصة Y٪», computed as `min(65, …)`.
  - Under the fields, show the trainer's ad deposits by currency and country, from the existing ads-ledger read the money section uses, plus the number of sales before and after the first deposit. If either source fails, show «غير متاح بعد».
  - Save with PUT plus `confirmed`.
- **Rules card:** «الحد الأدنى مع كود المدرّب» (`code_min_pct`, 35–65) and «السقف» 65, which is fixed and shown read-only.
- **History list** for each trainer.
- **Copy:** percentages are allowed here because this is the founder's own money screen.

## C3: Platform money (branch `courses-money` from `pillars-courses@20da444`)

**1. Share stamp in `routes/payments.py`, `_course_order_stamp`** (exactly as the PARALLEL «نسبة المدرّب جاهزة» request says)
- `order["share_stamp"] = await trainer_share_for(db, instructor_email, source)`, where source is `trainer_code` or `platform` from the existing attribution.
- The split uses `share_stamp.applied_pct` when present: `_credit_course_split` / `_trainer_share_pct`. `split_affiliate(amount, applied_pct, kind="courses")` runs after the referral.
- Orders with no stamp keep the old math.
- Stamp only on the insert. Never send it to the payment gateway.

**2. Course discount codes**
- Add `"courses"` to `promo_codes.APPLIES_TO`.
- `_attribution_for` and the course price use `promo_codes.discount_for`, the same way as books. One discount per code (founder rule C).
- A trainer's own code counts as `trainer_code`, so the trainer gets at least `code_min_pct`.

**Tests:**
- A stamped order splits by `applied_pct`. An old order uses the old math.
- A referral is applied after `applied_pct`. The platform floor of 35 holds.
- A course code discount is applied once.
- Code attribution gives `trainer_code`.
- Run the full platform suite inside the sandbox.
