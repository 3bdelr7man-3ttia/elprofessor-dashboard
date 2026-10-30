# Final round · Section «المحتوى» (key `content`) — rebuild in the new style

**Founder order (2026-10-30):** «الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا». This is FINAL work, not a draft. Build all of it in one pass.
**Worktree / branch:** `.worktrees/content` · `final-content` (from `dash-v2-d3@7d1aa83`). Merged later with 10 other sections.
**Reference style:** D1-B shell, D2 ticket boards (`v2-d2.js/css`, `.v2d-*`), D3 sheets and source handling (`v2-d3.js/css`, `.v3-*`, `twoStage`, `warnStrip`, `unavailable`).
**Concept boards:** there is no dedicated Content board. The approved row gives the pattern: POS-Home tile «المحتوى», POS-Tickets (columns of tickets with a coloured strip, a timer, one brain line and one button; the urgent column first; no create button on the board), POS-Focus (one decision at a time). This section applies POS-Tickets to the content pipeline.
**Revision 2 (2026-10-30):** expert review applied. What changed and what was not taken is in §12 «Decisions».

**Three rules that run through the whole section (read before building):**
- **One main button.** Every screen, card and sheet has at most one primary button. Everything else on an item lives inside that item's sheet. No «…» popover menus (D2/D3 have none).
- **Public or paid ⇒ a confirm sheet** (§6.1). Publishing, unpublishing, approving, rejecting, deleting and anything that spends automatic-writing credit always ask first. The short exempt list is in §6.1 and nothing else is exempt.
- **Facts only.** A brain line states what the data says. When there is no fact to back a suggestion, the main button is «افتح واقرأ», not a verdict. A failed source shows «غير متاح بعد», never «٠» and never a number from another source.

## 0) What the old screen is (read in full, `dashboard-cloud/index.html` 4240–5590 + `dashboard-api.js`)
One old module `topics` with an internal `topicsTab` and 11 internal tabs, all of which must be covered:

| Old internal tab (`topicsTab`) | Old view | Data (loader → window var) | Old actions (EP function → dashboard route → platform) |
|---|---|---|---|
| `pending` «مقترحة من الأعضاء» | `viewTopics` | `platformPendingTopics` → `PTOPICS_PENDING` (`GET /api/platform-pending-topics`) | `EP.decidePendingTopic(t,'approve'|'reject')` → `POST /api/platform-pending-topics/<id>/<action>`; `EP.setTopicSegment` |
| `ideas` «أفكار للاعتماد» | `viewTopics` | `platformTopics` → `PTOPICS` (draft, source≠expert) | approve `EP.updateTopic(id,{title,status:'open'})`; reject = `EP.deleteTopic` (**hard delete**); segment |
| `incoming` «واردة» | `viewTopics` | `PTOPICS` (source=expert, not published) | approve (status open); «للوكيل» `EP.updateTopic(id,{title,status:'merged'})`; delete |
| `working` «قيد العمل (الوكيل)» | `viewTopics` | `PTOPICS` status `merged` + `TOPIC_GENERATING` | `EP.publishTopic`; «اعمل مقال» `topMakeArticle`; delete |
| `board` «المنشورة» | `viewTopics` | `PTOPICS` status open/published | segment; «اعمل مقال»/«افتح المقال»; delete |
| `rejected` «مرفوضة» | `viewTopics` | `PTOPICS` status rejected | `EP.decidePendingTopic(t,'approve')`; delete |
| `news` «الأخبار» | `viewNews` | `platformNews` → `PNEWS`; `platformNewsSources` | `EP.createNews/updateNews/deleteNews`, `EP.deriveTopicFromNews`, `EP.saveNewsSources` |
| `articles`/`blog` «المقالات» | `viewContent` | `content` → `TOPICS` + `EP.data.content.raw` (`GET /api/content/articles/all`) | `EP.createArticle(g,publish)`, `EP.updateArticle`, `EP.publishArticle`, `EP.unpublishArticle`, `EP.rejectArticle` (**hard delete**), `EP.syncContent`, `EP.runDailyContent`, `EP.blogTopics`/`EP.saveBlogTopic` |
| `auto` (platform articles) | `viewArticlesAuto` | `platformArticles` → `PARTS` + raw | `EP.publishArticleP`, `EP.unpublishArticleP`, `EP.deleteArticleP`, `EP.runDailyContent` |
| `comments` «التعليقات» | `viewComments` | `platformOpinions` → `POPINIONS`; `platformOpinionsApproved` → `POPINIONS_APPROVED`; `platformOpinionsAnalysis` | `EP.approveOpinion`, `EP.rejectOpinion`, `EP.deleteOpinion`, `EP.replyOpinion(o,{reply}|{ai:true})` |
| `tutorials` «دليل الاستخدام» | `viewTutorials` | `tutorials` → `TUTORIALS` | `EP.createTutorial/updateTutorial/deleteTutorial` |
| (panels) | `topicsAIAnalysisPanel`, `opinionsAnalyticsPanel`, `publishSchedulePanel` | `platformTopicsAnalysis`, `platformOpinionsAnalysis`, a **hardcoded** slot list | refresh only |

Two inflows that the old dashboard only shows inside the old inbox («كل الوارد») but which belong here: **ركن الإبداع** works (`GET /api/platform-creative?status=pending_review`, fetched today only *inside* the `inbox` loader, decided with `EP.decideInboxItem({apiKind:'creative',apiId},…)`), and **course testimonials** (the content tile already counts `opsQueue.testimonials_pending`, but there is no screen anywhere; the platform bridge `GET /api/bridge/testimonials` + `POST /api/bridge/testimonials/{id}/approve|reject` exists — `elprofessor-wt-d3/backend/routes/engagement.py:614-665`, full rows incl. `consent_public`, `rating`, `user_email`, `course_title`, `decided_at` — and the dashboard has no proxy).

Two old behaviours this round deliberately drops (both violate founder rules):
- `publishSchedulePanel` prints a **hardcoded** list of 5 daily times. It is not read from any source, so it is not a fact. It is removed. A real schedule line comes back only through «Platform needs» P1.
- The old comments screen loads `/api/platform-opinions-analysis` with the default `summarize=true` on **every visit**, which makes the platform call DeepSeek every time (a paid call). The new screen always reads it with `summarize=false` (`backend/app.py:4579` already passes the flag through). The written summary is fetched only when the founder confirms «اكتب خلاصة» (§5.2).

Also removed from visible copy: the raw English `engagement_note`, the «DEEPSEEK_API_KEY» hint, every «AI», «SEO», «الوكيل الذكي», «(app.elprofessor.net)» domain in titles, «الذكاء» at the start of any headline, and the colloquial toasts the section triggers (§1.4).

**«كل السجلات»: none.** Every old tab, panel, sheet and action above has a new home (coverage table in §9). The section has no tab with an old-look screen.

## 1) Routing: keep the old module name, render it new
The six new tabs all keep `mod: 'topics'` and are told apart by `topicsTab` (exactly as `money/all` + `money/manual` did with `finTab`/`escTab`). That keeps every old door working without touching `sectionFor`, `ALIASES`, `REDIRECTS` or `MODULES`:
- `#tutorials`, `go('topics')`, inbox rows with `dest:'topics'`, `OPSQ_LANDINGS.topics_drafts` (sets `topicsTab='ideas'` ⇒ «الموضوعات › أفكار», which is exactly what that inbox chip counts) and `ALIASES.tutorials` all resolve through the existing `sectionFor('topics', {topicsTab})`.
- **One front door.** The home tile (§8.5), the bare hash `#topics` and the old inbox row `testimonials_pending` all land on `content/pipeline`. `#topics` does it through one line at the top of `routeFor` (§8.6); `STATE_DEFAULTS.topicsTab` stays `'ideas'` because the old screen (switch off) needs it.
- Under the shell, `renderView()` hands `current==='topics'` to the new section renderer (§1.3) **before** the old `if(current==='topics')` branch. The old branch is only reachable with the switch off (and for the `employee` role, which never gets the shell). The old code stays in `index.html` untouched.

### 1.1 `SECTIONS` entry (`dashboard-cloud/v2-logic.js`)
```js
{ key: 'content', label: 'المحتوى', img: 'content', desc: 'المقالات والموضوعات والأخبار والتعليقات ودليل الاستخدام', tabs: [
  T('pipeline',  'خط النشر',       'topics', { topicsTab: 'pipeline' },  { topicsTab: ['pipeline'] }),
  T('articles',  'المقالات',        'topics', { topicsTab: 'articles' },  { topicsTab: ['articles', 'blog', 'auto'] }),
  T('topics',    'الموضوعات',       'topics', { topicsTab: 'pending' },   { topicsTab: ['pending', 'ideas', 'incoming', 'working', 'board', 'rejected'] }),
  T('news',      'الأخبار',         'topics', { topicsTab: 'news' },      { topicsTab: ['news'] }),
  T('comments',  'التعليقات',       'topics', { topicsTab: 'comments' },  { topicsTab: ['comments'] }),
  T('tutorials', 'دليل الاستخدام', 'topics', { topicsTab: 'tutorials' }, { topicsTab: ['tutorials'] })
] }
```
- `'pipeline'` is a new `topicsTab` value used only under the shell.
- Sub-state inside a tab (the chips in «الموضوعات», the «على الموقع / على المنصة» switch in «المقالات») is written with `window.v2OpenSection('content', tab, {replace:true, st:{topicsTab:v}})`. `V2_SETTERS.topicsTab` already exists, so the header, the hash `#s/content/<tab>` and `v2Reconcile` all stay right. The category filter, the mobile column and the open item live in the section's own state `S` (not in shared state).

### 1.2 Pure helpers (end of `v2-logic.js`)
A separate IIFE at the very end of the file, inside `// ===== v2s:content =====` … `// ===== /v2s:content =====`. It reads `root.V2L` (the exported `api`, which is also `module.exports`) and attaches functions to it, so node tests reach them as `L.v2Content…`. It reuses `L.util.ar`, `L.util.U`, `L.util.agoText`, `L.v2TimerText`, `L.v2TimerTone`, `L.NA`. No DOM, no `EP`, no `Date.now()` (the caller passes `now`).

- `v2ContentTabFor(topicsTab)` → `'pipeline'|'articles'|'topics'|'news'|'comments'|'tutorials'` (`blog`/`auto` → `articles`; the six topic states → `topics`; unknown → `pipeline`).
- `v2ContentBoard(src, now)` → `{order:['wait','draft','idea','done'], cols:{wait,draft,idea,done}, counts, partial, failed, top}` (§2.2). `src` holds each source as an array, or `null` when it failed, or `undefined` while loading.
- `v2ContentFacts(articleMeta, publishedTitles)` → `{words, hasImage, hasMeta, reviewer, dupTitle, line}` for one site article (§2.3).
- `v2ContentSuggest(item)` → `{label, act}` (the one main button; §2.3).
- `v2ContentCommentVerdict(moderation)` → `{key:'abusive'|'offtopic'|'open', text, suggest:'reject'|'read'}`. `open` never suggests «اعتمد».
- `v2ContentPrerender(p, now)` → `{text, tone, live:boolean}` from the overview route's `prerender` block (§2.1); `live` is `true` only for `ok`/`running`.
- `v2ContentPublishLead(title, prerender)` → the publish-confirm lead of §3.2 (with or without the search-pages clause).
- `v2ContentTopicChips(PTOPICS, PTOPICS_PENDING, active)` → chip list with counts (§4); reuses the old `topicTabOf` rules verbatim (copied into the helper; the old function stays in `index.html`). `PTOPICS_PENDING === null` ⇒ that chip's count is `null` (never read from `PTOPICS`).
- `v2ContentSegments(analysis)` → the lanes from `by_segment` in the locked order, zeros kept, plus `{gap: label|null}` = the first lane with count 0.

### 1.3 Front-end files (new)
- `dashboard-cloud/v2s/content.js` — `window.V2SEC = window.V2SEC || {}; V2SEC.content = { owns(mod), render(mod, view) }`. `owns('topics')` is `true` (under the shell only, enforced by the dispatcher). It also exposes `V2SEC.content.tabFor` for tests.
- `dashboard-cloud/v2s/content.css` — every rule under the root class `.v2ct` (and `.v2ct-m` for sheet bodies inside `#epModal`). Tokens copied from `.v2d`: `--wine:#9E2B4E; --paper:#FBFAF7; --paper2:#F6F1EA; --ink:#21262E; --red:#C8102E; --line:#E9E1D6; --amber:#8F5F00; --amber-bg:#FFF6DD; --green:#187E4E; --mute:#6B665C`. Section accent (from the tile RGB) `--accent: rgb(190,88,48)` is used only on the column headers and the section photo strip. Fonts: 'IBM Plex Sans Arabic' body, 'Cairo' 800 for headings and buttons.
- `index.html`, inside `<!-- v2 sections begin -->` … `<!-- v2 sections end -->` (created right after the `v2-d2.js` script tag if missing), one line each, alphabetical by key: `<link rel="stylesheet" href="v2s/content.css">` and `<script src="v2s/content.js"></script>`.

Rendering contract (same as D2/D3): `render(mod, view)` draws `<div class="v2ct">…</div>` into `#view`, keeps its own state `S = {view, tab, sub, cat, col, open, busy:{}, note, generating:{}, summary, sig}`, redraws on a signature of its sources' states (`EP.state[key]` for every key in §1.4), runs a 60 s timer tick for ticket times (no reload), never redraws while `#epModal` is open with a busy flag, and stops when `host().current() !== 'topics'`. Reads the current inner tab with `window.v2Snapshot().topicsTab`. On start it sets `EP.muteNotes = true`; on stop it sets it back to `false` (§1.4).

### 1.4 Sources and `dashboard-api.js` edits
Every source the section reads is an `EP` loader with its own state, so the signature redraw and «أعد المحاولة» (reload only the failed ones) work the same for all of them. Existing loaders used as they are: `content`, `platformArticles`, `platformTopics`, `platformPendingTopics`, `platformTopicSegments`, `platformTopicsAnalysis`, `platformOpinions`, `platformOpinionsApproved`, `platformNews`, `platformNewsSources`, `tutorials`. `platformOpinionsAnalysis` is **never** used (it calls with `summarize=true`).

**New loaders** in `LOADERS` (same pattern as the others: set `EP.data.<key>` and one `window` var; throw on failure so `EP.state[key]='error'`):

| Key | Request | Sets |
|---|---|---|
| `contentOverview` | `GET /v2/content/overview` | `EP.data.contentOverview` = the response (§7.1) |
| `platformCreative` | `GET /platform-creative?status=pending_review` | `EP.data.platformCreative = {raw: items}`, `window.PCREATIVE` |
| `testimonials` | `GET /v2/testimonials?status=pending` | `EP.data.testimonials = {raw: rows}`, `window.PTESTIMONIALS` |
| `testimonialsApproved` | `GET /v2/testimonials?status=approved` | `EP.data.testimonialsApproved = {raw: rows}` |
| `platformOpinionsNumbers` | `GET /platform-opinions-analysis?summarize=false` | `EP.data.platformOpinionsNumbers` = the response |

The `inbox` loader keeps its own creative fetch (the old inbox still lists those rows).

**Edits to existing `EP` functions (behaviour of the old screen unchanged):**
1. `EP.runDailyContent(after, opts)` — new optional `opts = {isOpen: fn}`. When `opts.isOpen` is given it replaces the `#ctRows/#artRows` check: up to 6 times every 30 s, while `opts.isOpen()` is true, `post('/content/sync-from-platform')` then `EP.reload('content')`, `EP.reload('platformArticles')`, `EP.reload('contentOverview')`, then `after()`. Without `opts` the old code path runs byte-for-byte as today.
2. `EP.muteNotes` (default `false`) and `EP.lastError` (string). `note(msg)` does nothing while `EP.muteNotes` is true. `quietToast(msg)` always sets `EP.lastError = msg` and toasts only while `EP.muteNotes` is false. The section shows its own note strip (`«تمّ: …»`) and failure text (`«لم يتم. {EP.lastError}»`), so nothing is said twice and no colloquial toast appears inside the new section.
3. Reworded strings (they appear in the old screen too, which is harmless): `runDailyContent` «فيه توليد شغّال بالفعل — استنّاه.» → «الكتابة الآلية تعمل الآن بالفعل.»; «بدأ التوليد بالذكاء — …» → «بدأت الكتابة الآلية. تظهر المسودات بعد انتهائها.»; `syncContent` «اتسحب {n} مقال من الذكاء للمدونة» → «سُحب {n} مقال جاهز من المنصة إلى الموقع.» and «مفيش مقالات جديدة من الذكاء دلوقتي» → «لا مقالات جاهزة جديدة على المنصة الآن.».

No other edit in `dashboard-api.js`.

## 2) Tab «خط النشر» (default) — the pipeline board
A decision board, like POS-Tickets: no create button here (each tab has its own «جديد»).

### 2.1 Top bar (brain line + facts)
Right to left: the brain avatar `v2/img/brain-avatar.jpg` + one sentence; then up to three fact pills.

Brain sentence, first rule that applies (all counts from the board, §2.2):
1. member topics > 0: «ابدأ بموضوعات الأعضاء: {N} ينتظر صاحبه قرارك، أقدمها منذ {age}.»
2. else other `wait` items > 0: «{N} ينتظر قرارك من الأعضاء والمتعلّمين.»
3. else site drafts > 0: «{N} مسودة للموقع جاهزة للقراءة.»
4. else, only when every pipeline source loaded: «لا شيء ينتظر قرارك الآن.»
If the source behind a rule failed, that rule is skipped and the strip in §2.4 says so (never «٠»). If rule 4 would apply but a source failed, the sentence is «بعض المصادر لم تصل، فلا أستطيع القول إن لا شيء ينتظرك.»

Fact pills (each hidden while its source is loading; «غير متاح بعد» when it failed):
- «نُشر على الموقع اليوم: {n}» and «هذا الأسبوع: {m}» — from `contentOverview.articles[].published_at` (status `published`), counted in the viewer's local day / last 7×24 h relative to `now`.
- Search pages: `v2ContentPrerender(contentOverview.prerender)`:
  - `ok` → «صفحات محركات البحث حُدّثت منذ {age}» (green)
  - `running` → «صفحات محركات البحث تتحدّث الآن» (neutral)
  - `error` → «تعذّر آخر تحديث لصفحات محركات البحث (منذ {age}) — يُعاد مع أول نشر» (red)
  - `skipped` / `never-run` / missing → «تحديث صفحات محركات البحث: غير متاح بعد»
  Basis: `_prerender_last` / `_prerender_running` in `backend/app.py`, which `_prerender_push_async` sets after every publish, edit of a published article, delete of a published article, blog-topic save, bulk unpublish and the cron. «يُعاد مع أول نشر» is literally what the code does.

### 2.2 Columns (pure `v2ContentBoard`)
Four columns, D2 look (`.v2d-cols` geometry, re-declared under `.v2ct`): a header with the label and a count chip, then tickets. The split is by **who is waiting**, which is a fact. **One order on every width and in the DOM** (no CSS `order`): «ينتظرك» · «مسودات» · «أفكار» · «نُشر هذا الأسبوع» (first = right-most in RTL, the urgent column first as on the approved board).

| Column | Label | Header note | Strip tone | What goes in (source → filter) | Order |
|---|---|---|---|---|---|
| `wait` | «ينتظرك» | «أصحابها ينتظرون قرارك» | wine; red when older than 48 h | member topics (`PTOPICS_PENDING`) · testimonials (`testimonials`) · comments pending (`POPINIONS`) · creative works (`platformCreative`) | member topics oldest first, then testimonials, comments, works (each oldest first) |
| `draft` | «مسودات» | «لم تُنشر بعد» | amber | site articles `status:'draft'` (`contentOverview`) · platform articles `status:'draft'` (`PARTS`) · topics `status:'merged'` · topics being written now (`S.generating`) | generating first, then oldest first |
| `idea` | «أفكار» | «مادة خام تنتظر أن تتحول إلى نقاش أو خبر منشور» | ink | topics `status:'draft'` and `source!=='expert'` (`PTOPICS`) · topics `source:'expert'` and status not `open/published/merged/pending_review/rejected/archived` · news `status:'draft'` (`PNEWS`) | newest first |
| `done` | «نُشر هذا الأسبوع» | «ما نُشر أو اعتُمد خلال ٧ أيام» | green, dimmed | site articles `published_at` · news `published_at` (raw) · comments approved by a person (`platformOpinionsApproved.raw[].moderation.decided_by==='human'`, `decided_at`) · testimonials approved (`testimonialsApproved.raw[].decided_at`) — each only when its **decision date** is within 7×24 h of `now`; an item without that date is not listed (never guessed from `created_at`) | newest first |

- Each column shows at most 6 tickets, then a button «و{n} أخرى — افتح القائمة» that opens the matching tab and chip (`wait` → the chip of the first hidden kind, `draft` → «المقالات», `idea` → «الموضوعات › أفكار», `done` → «المقالات › منشورة»).
- Excluded: topics `archived`; topics `open/published` (they live in «الموضوعات › على اللوحة»; the platform stores no opening date, see P3); platform articles `published` (no ticket, only the list).
- Counts: `counts[col]` = number of items from sources that loaded. If any source of that column failed → `partial[col] = true` and the chip reads «{n}+» with the title «العدد ناقص — تعذّر جلب بعض المصادر». If **every** source of the column failed → the chip reads «غير متاح بعد» and the column body is the D3 `unavailable` block «{column}: غير متاح بعد» + «أعد المحاولة». Never «٠» for a failed source. An empty but loaded column shows «لا شيء هنا الآن».
- Testimonials count fallback: if `testimonials` failed but `opsQueue.testimonials_pending` is a number, the `wait` column shows one count card «{n} رأي متعلّم ينتظر المراجعة» with «أعد المحاولة» (count from the existing queue, no list).

### 2.3 Tickets
Same anatomy as `ticketHtml` in D2: coloured strip with the type label and the time, title as a button (opens the item's sheet), one «who» line, one brain line (avatar + sentence), one main button. Times use `L.v2TimerText` («منذ ٣ س»), refreshed by the 60 s tick. Slim tickets (strip + title + one line, no button) in `done`.

| Kind | Strip label | Time from | «Who» line | Brain line (facts only) | Main button (`v2ContentSuggest`) |
|---|---|---|---|---|---|
| member topic | «موضوع من عضو» | `PTOPICS_PENDING[].at` | `category` or «بلا تخصص» | «القرار يصل إلى صاحب الموضوع · الفئة: {segment_label}{ (اختيار آلي)}» or «… · بلا فئة» | «اعتمد وبلّغ» → confirm §6.1 → `EP.decidePendingTopic(t,'approve',cb)` |
| testimonial | «رأي متعلّم» | `created_at` | `name` → person link by `user_email` | «{course_title} · التقييم {rating} من ٥» (rating part omitted when null) + ` · وافق كاتبه على النشر باسمه` only when `consent_public === true`, ` · لم يوافق على ذكر اسمه` when it is `false`, nothing when the field is missing | «اعتمد» → confirm §6.5 → `POST /api/v2/testimonials/<id>/approve {confirmed:true}` |
| comment | «تعليق» | `POPINIONS[].at` | «على: {topic_title}» | `v2ContentCommentVerdict`: abusive → «الفحص الآلي على المنصة: قد يحوي إساءة»; `on_topic===false` → «الفحص الآلي على المنصة: خارج الموضوع»; else «لم يحسمه الفحص الآلي» | abusive/off-topic → «ارفض» → confirm §6.1 → `EP.rejectOpinion`; undecided → «افتح واقرأ» → comment sheet §6.6 |
| creative work | «عمل إبداعي» | `created_at` | `creator_name` → person link by `creator_email` | «{kind: أغنية/فيديو/قصيدة/عمل آخر} · {has media_url ? 'معه رابط' : 'بلا رابط'}» | «افتح وراجع» → creative sheet §6.4 |
| site draft | «مقال للموقع» | overview `created_at` | `by` | `v2ContentFacts.line`: «{words} كلمة · {بصورة/بلا صورة} · {بوصف لمحركات البحث/بلا وصف لمحركات البحث} · {راجعه {reviewer}/لم يراجعه أحد}»; if `dupTitle` → «عنوانه مطابق لمقال منشور على الموقع» | `dupTitle` → «افتح وقارن» → reader §3.2 with the compare row; else «اقرأ وانشر» → reader §3.2 |
| platform draft | «مقال على المنصة» | `PARTS` raw `created_at` | category label (`feature` «شرح المنصة», `news` «تحليل خبر», `law` «قانوني», `guide` «دليل», `platform` «المنصة», `other` «أخرى») | stale (same trimmed title published on the site) → «عنوانه مطابق لمقال منشور على الموقع»; else «تظهر في صفحة المقالات على المنصة بعد النشر» | stale → «افتح وقارن» → reader §3.3 with the compare row; else «اقرأ وانشر» → reader §3.3 |
| topic being written | «يُكتب من النقاش» | topic `at` | category | `merged_article` or `ai_answer` non-empty → «النص جاهز للمراجعة»; else «لم يُكتب النص بعد» | ready → «انشر على اللوحة» (confirm) → `EP.publishTopic`; else «افتح» → topic sheet §4.2 |
| generating now | «يُكتب المقال الآن» | start time in `S.generating` | topic title | «يكتب النظام مقالًا جديدًا من هذا الموضوع، ويظهر مسودة عند انتهائه» | none (status text «جارٍ الكتابة…») |
| idea topic | «فكرة» / «من خبر» (source `news`) / «من خبير» (source `expert`) | topic `at` | category | «{source label} · {category} · الفئة: {segment_label}/بلا فئة»; plus «معه إجابة مقترحة» when `ai_answer` | has `ai_answer` → «اعتمد للنقاش» (confirm) → `EP.updateTopic(id,{title,status:'open'})`; else «افتح وراجع» → topic sheet |
| news draft | «خبر» | news `at` | `country` · `specialty` | «{n} مصدر» or «بلا مصدر» · «{بملخص/بلا ملخص}» | sources ≥1 and summary → «انشر الخبر» (confirm) → `EP.updateNews(id,{title,is_published:true})`; else «أكمل الخبر» → news sheet |
| done (slim) | «مقال نُشر» · «خبر نُشر» · «تعليق اعتُمد» · «رأي اعتُمد» | the decision date | `by` / topic / course | — | article: link «اعرضه على الموقع» (`https://elprofessor.net/article.html?id=<id>`); others: the title opens their tab |

`dupTitle`: exact equality of trimmed titles against published site articles (never "contains"; the CLAUDE.md lesson). Stale platform draft: same rule against the site list (the old `_blogTitles` logic). The compare row in the reader shows «المقال المنشور بنفس العنوان: {title} · {date}» with the link «اعرضه على الموقع»; the delete button for the duplicate lives there (§3.2, §3.3).

### 2.4 Failure / loading
- Loading (any pipeline source `idle/loading`): each column shows two grey placeholder tickets; the brain line reads «…جارٍ جمع المحتوى».
- Failed sources: one strip under the top bar (D3 `warnStrip`): «تعذّر جلب: {labels joined by ' · '} — ما يظهر ناقص، وليس معناه أنه لا شيء» + «أعد المحاولة» (calls `EP.reload` only for the failed keys). Labels: `content` «مقالات الموقع» · `contentOverview` «حالة مقالات الموقع» · `platformArticles` «مقالات المنصة» · `platformTopics` «الموضوعات» · `platformPendingTopics` «موضوعات الأعضاء» · `platformOpinions` «التعليقات» · `platformOpinionsApproved` «التعليقات المعتمدة» · `platformNews` «الأخبار» · `platformCreative` «أعمال ركن الإبداع» · `testimonials` «آراء المتعلّمين» · `testimonialsApproved` «الآراء المعتمدة».

### 2.5 Layout
- **Desktop (≥1180, 1440 shot):** 4 equal columns (`grid-template-columns: repeat(4, minmax(0,1fr))`, gap 14px) inside the 1360px container; column background `--paper2`, radius 22px; tickets white, radius 18px.
- **Tablet (820):** 2×2 grid in the same order (`wait draft` / `idea done`).
- **Mobile (390):** a strip of 4 segment buttons with counts in the same order («ينتظرك» · «مسودات» · «أفكار» · «نُشر»), 60px tall, the active one dark (`.v2d-segb` look); one column at a time (`S.col`), default `wait` if it has items, else `draft`. Tickets full width; main button 52px; no horizontal page scroll (the segment strip is a 4-column grid, not a scroller).

## 3) Tab «المقالات» (`topicsTab: articles|blog|auto`)

### 3.1 Screen
- A two-option switch at the top: «على الموقع» (`articles`, default; `blog` lands here) · «على المنصة» (`auto`). Under it one plain line:
  - site: «مقالات elprofessor.net: يقرؤها الناس ومحركات البحث.»
  - platform: «مقالات صفحة المقالات داخل المنصة.»
- Buttons (site): «مقال جديد» (the one primary) · «أدوات الكتابة» (secondary) → tools sheet §3.4. Buttons (platform): «أدوات الكتابة» only (the sheet then shows only «اكتب مقالات الآن»).
- Filter chips (site): «مسودات ({n})» · «منشورة ({m})» (counts from `content` loader, `status`).
- List of article cards (one column on all widths, max 880px, centred): title (Cairo 800 17px), «{by} · {date}», status pill («مسودة» amber / «منشور» green), fact chips from `v2ContentFacts` («{n} كلمة», «بلا صورة», «بلا وصف لمحركات البحث», «راجعه {x}»), «عنوانه مطابق لمقال منشور» (amber) when `dupTitle`. The whole card is the button → reader. On the platform list: title, excerpt (2 lines), category label, status pill («مسودة» / «منشور على المنصة»), the badge «عنوانه مطابق لمقال على الموقع» for stale drafts, and at the top a brain line when stale > 0: «{n} مسودة هنا عناوينها مطابقة لمقالات منشورة على الموقع.»
- Data: site list = `content` loader (`TOPICS` for list, `EP.data.content.raw` for body/meta/image), joined by id with `contentOverview.articles` (words, `has_meta`, `created_at`). If `contentOverview` failed, the fact chips are hidden and the strip says «حالة مقالات الموقع: غير متاح بعد» + «أعد المحاولة»; the list still works. Platform list = `platformArticles` (`PARTS` + raw).
- Empty: site drafts «لا مسودات الآن. اكتب مقالًا جديدًا أو اسحب الجاهز من المنصة من «أدوات الكتابة».»; platform «لا مقالات على المنصة بعد.»

### 3.2 Site article reader + editor (focus sheet)
Opened in `#epModal` (via `window.openModal`) with the body class `.v2ct-m`; full screen on mobile, 920px wide on desktop/tablet. Two stages in one sheet (D3 `twoStage` style, not the old drawer):
- **Read stage:** kicker line «{cat} · {kicker}»; title; status pill; the facts line; the compare row when `dupTitle` (§2.3); excerpt (bold); body rendered from `raw.body` (lines starting with `## ` → `<h3>`, others → `<p>`, all escaped — same rendering rule as the old `drawContent`); image preview if `image_url`. Buttons:
  - draft: «انشر على الموقع» (primary) · «عدّل» · «احذف المسودة» (danger text button). With `dupTitle` the primary is «احذف المكرر» (danger) and «انشر على الموقع» becomes secondary.
  - published: «اعرضه على الموقع» (link, same URL as today) · «عدّل» · «أوقف النشر». **No delete on a published article:** to remove it, the founder stops publishing first, then deletes the draft. The sheet says so under the buttons: «لحذف مقال منشور: أوقف نشره أولًا، ثم احذفه من المسودات.»
- **Edit stage** (also used for «مقال جديد»): exactly the old fields and mapping of `createArticleModal`, in this order, labels in plain Arabic:
  «العنوان» (`a_t`) · «التصنيف» (`cat`, placeholder «قانون الشركات») · «الوسم» (`kicker`, placeholder «تشريعات») · «المقتطف» · «نص المقال» (textarea, «افصل بين الفقرات بسطر فارغ، وابدأ العنوان الفرعي بـ ##») · «الكاتب» (`by`; default on new **«فريق البروفيسور»**, not the old «الذكاء + رأي خبير», per «لا نبدأ بالذكاء») · «رابط صورة المقال» (ltr) · «وصف محركات البحث» («الجملة التي تظهر تحت العنوان في جوجل، وتبدأ بالإجابة المختصرة») · «راجعه (اختياري)» («اسم من راجع المقال فعلًا، واتركه فارغًا إن لم يُراجَع»).
  The `gather()` defaults stay byte-for-byte (`'مقال بلا عنوان'`, `'قانوني'`, `'مقال'`, `'الإدارة'`) and the payload goes through the same functions: new → «احفظ مسودة» (primary, no confirm, exempt) `EP.createArticle(g, false, cb)` or «احفظ وانشر الآن» → confirm → `EP.createArticle(g, true, cb)`; edit of a draft → «احفظ» (exempt) `EP.updateArticle(t, g, cb)`; edit of a **published** article → «احفظ» → confirm «يظهر التعديل على الموقع فور الحفظ.» → `EP.updateArticle(t, g, cb)`. The edit note «رابط المقال المنشور ثابت ولا يتغيّر بتغيير العنوان، وتاريخ آخر تحديث يتحرك فقط عند تعديل جوهري في النص.» stays.
- **Publish confirm** (§6.1), lead from `v2ContentPublishLead`:
  - `prerender.state ∈ {ok, running}` → «سيظهر «{title}» على الموقع الآن، وتتحدّث صفحته لمحركات البحث خلال دقائق.»
  - otherwise (`error`, `skipped`, `never-run`, missing, or `contentOverview` failed) → «سيظهر «{title}» على الموقع الآن.»
  → `EP.publishArticle(t, cb)`. After the reload, success is checked (`status==='published'` in the reloaded list) → note «نُشر على الموقع.»; then `contentOverview` is reloaded once after 60 s so the prerender pill shows the new state. If that reload reads `error`, the red pill of §2.1 is also shown as a strip under the note.
- **Unpublish confirm:** «سيختفي «{title}» من الموقع وتُحذف صفحته من محركات البحث مع التحديث القادم.» → `EP.unpublishArticle`.
- **Delete draft confirm:** «ستُحذف هذه المسودة نهائيًا ولا يمكن استرجاعها.» → `EP.rejectArticle`. For a duplicate («احذف المكرر») the lead also shows both titles: «المسودة: {title} · المنشور: {published title} ({date})».
- ⛔ No new write route for articles; no change to `backend/prerender.py`, `_prerender_push(_async)`, `serialize_article`, `_apply_article_fields`, `/api/content/*`. The prerender triggers fire exactly where they fire today.

### 3.3 Platform article reader
Same sheet, read stage only (body from `EP.data.platformArticles.raw[].body`, array or string — same branches as `artDetailModal`), plus the compare row for stale drafts. Buttons: draft → «انشر على المنصة» (primary; confirm «سيظهر في صفحة المقالات داخل المنصة.») → `EP.publishArticleP`; stale draft → primary «احذف المكرر» (confirm with both titles, as §3.2) → `EP.deleteArticleP`, publish secondary; published → «أوقف النشر» (confirm «سيختفي من صفحة المقالات داخل المنصة.») → `EP.unpublishArticleP`; always «احذف» (danger text; confirm «سيُحذف «{title}» من المنصة نهائيًا.») → `EP.deleteArticleP`.

### 3.4 «أدوات الكتابة» sheet
One sheet, three rows, each a row with a one-line explanation and its own button (secondary):
- «موضوعات المدوّنة» («عناوين صفحات الموضوعات في المدوّنة ووصفها») → opens the blog-topics sheet: `EP.blogTopics(cb)` rows: path line (ltr) «/blog/topic/{slug}» · «{count} مقال منشور», «العنوان» input (max 120), «الوصف» textarea (max 400), «احفظ» → confirm «يظهر العنوان والوصف الجديدان على صفحة الموضوع في المدوّنة.» → `EP.saveBlogTopic(cluster_id, {label, description}, cb)` (server triggers prerender as today), «اعرض الصفحة» link when `count>0`. Lead: «العنوان والوصف يظهران على صفحة الموضوع وفي قائمة الموضوعات بالمدوّنة. الرابط ثابت ولا يتغيّر.» Errors inline in the row.
- «اسحب الجاهز من المنصة» («ينقل المقالات التي انتهت كتابتها على المنصة إلى مسودات الموقع») → one tap, exempt (it creates drafts only) → `EP.syncContent(cb)` (button shows «جارٍ السحب…»; result note from §1.4).
- «اكتب مقالات الآن» («يكتب ٣ مقالات وموضوعين كمسودات») → confirm: «يبدأ النظام كتابة ٣ مقالات وموضوعين كمسودات. يستهلك ذلك من رصيد الكتابة الآلية. تظهر المسودات هنا بعد انتهاء الكتابة، ويسحبها النظام تلقائيًا ما دامت هذه الصفحة مفتوحة.» Buttons «ابدأ الكتابة» / «رجوع» → `EP.runDailyContent(cb, {isOpen: function(){ return host().current()==='topics'; }})` (§1.4). On the platform list the sheet shows only this row.

## 4) Tab «الموضوعات» (`topicsTab: pending|ideas|incoming|working|board|rejected`)

### 4.1 Screen
- Chips (pure `v2ContentTopicChips`), each with a count: «من الأعضاء» (`pending`, count from `PTOPICS_PENDING` only) · «أفكار» (`ideas`) · «من الخبراء» (`incoming`) · «يُكتب» (`working`, includes `S.generating`) · «على اللوحة» (`board`) · «مرفوضة» (`rejected`, shown only when >0 or active). If `platformPendingTopics` failed, «من الأعضاء» shows «—» with the title «غير متاح بعد», and the chip's screen shows the `warnStrip` «موضوعات الأعضاء: غير متاح بعد» + «أعد المحاولة». Chip = `v2OpenSection('content','topics',{replace:true,st:{topicsTab:x}})`. On mobile the chips wrap in a 3×2 grid (44px).
- Second filter «التخصص»: a `<select>` built from the categories present in the active list + `analysis.by_category` (old `topicCatChips` sources), default «كل التخصصات». State in `S.cat`.
- Brain line per chip (facts only):
  - `pending`: «{n} موضوعًا كتبه أعضاء، وهو مخفي عن اللوحة حتى تقرّر. القرار يصل إلى صاحبه.»
  - `ideas`: «{n} فكرة. الاعتماد يضعها على اللوحة العامة، والرفض يحذفها.»
  - `board`: from `v2ContentSegments`: «أقل الفئات موضوعات: {label} ({n}).» (only when the analysis loaded).
  - others: none.
- «موضوع جديد» (primary) → editor sheet: «العنوان» · «السؤال» · «التخصص» · «المصدر» (`human` «كتبه الفريق», `idea` «فكرة», `expert` «من خبير», `news` «من خبر»). Lead: «يكتب النظام إجابة مقترحة كمسودة، ويستهلك ذلك من رصيد الكتابة الآلية. لا يُنشر شيء قبل اعتمادك.» Button «احفظ واكتب الإجابة المقترحة» → `EP.createTopic(g, cb)` (same payload). The lead names the cost before the press, so this sheet is its own confirmation (no second sheet).
- Topic cards: title; pills: source, category, segment («الفئة: {label}» + « · اختيار آلي» when `segment_auto`, or «بلا فئة»), «له مقال» (green) when `linked_article_id`; meta line: country · «{n} تعليق معتمد» (board only) · date. **One main button per card** (below); tapping the card opens the topic sheet §4.2, which holds every other action and the segment select. Same on desktop and mobile.

| Chip | Card main button | In the topic sheet (§4.2) |
|---|---|---|
| `pending` | «اعتمد وبلّغ» → confirm «سيظهر على اللوحة العامة، ويصل القرار إلى صاحبه.» → `EP.decidePendingTopic(t,'approve')` | «ارفض» → confirm «لن يظهر على اللوحة، ويبقى محفوظًا بلا حذف.» → `decidePendingTopic(t,'reject')`; segment select |
| `ideas` | «اعتمد للنقاش» → confirm «سيظهر على اللوحة العامة.» → `EP.updateTopic(id,{title,status:'open'})` | «ارفض واحذف» → confirm «سيُحذف الموضوع نهائيًا.» → `EP.deleteTopic`; segment select; edit fields |
| `incoming` | «اعتمد للنقاش» (same) | «حوّله للكتابة» (exempt) → `EP.updateTopic(id,{title,status:'merged'})`; «احذف»; edit fields |
| `working` | «انشر على اللوحة» → confirm «سيظهر على اللوحة العامة بنصه الحالي.» → `EP.publishTopic` | «اكتب منه مقالًا» / «افتح المقال»; «احذف»; edit fields |
| `board` | «اكتب منه مقالًا» (or «افتح المقال» when linked) | segment select; «احذف»; edit fields |
| `rejected` | «اعتمد بعد المراجعة» → confirm «سيظهر على اللوحة العامة، ويصل القرار إلى صاحبه.» → `EP.decidePendingTopic(t,'approve')` | «احذف نهائيًا» → `EP.deleteTopic` |

Segment select = the old `tpSegSelect` behaviour: options only from `PTOPIC_SEGMENTS` (`GET /api/platform-topic-segments`), disabled with «…جارٍ تحميل الفئات» until loaded, saves on change via `EP.setTopicSegment(t, id, cb)` (exempt: an internal label, not public); label «الفئة المستهدفة (تُحفظ فور الاختيار)». Never a local list.

### 4.2 Topic sheet (tap a card)
- Member topic (`pending`): read only (the old `topPendingModal` rule). Title, «السؤال أو النص», «التخصص», «الفئة المستهدفة» (select), note «صاحب الموضوع محفوظ على المنصة ولا يظهر على اللوحة.» Buttons «اعتمد وانشر وبلّغ صاحبه» (primary, confirm) / «ارفض بلا حذف» (confirm) / «إغلاق».
- Other topics: the old `topReviewModal` fields, renamed: «العنوان», «التخصص», «المصدر», «الفئة المستهدفة (تُحفظ فور الاختيار)», «الحالة» (`draft` «مسودة», `open` «على اللوحة», `merged` «يُكتب», `published` «منشور»), «السؤال», «الإجابة المقترحة» (`ai_answer`, placeholder «لم تُكتب إجابة مقترحة بعد»), «النص المدموج» (`merged_article`, only if present). Buttons: the chip's main action (primary) · «احفظ التعديلات» → `EP.updateTopic(id, g)` (same keys; exempt while the topic is not on the board; when it is `open/published`, or when the edit changes «الحالة» to `open/published`, confirm «يظهر التعديل على اللوحة العامة فور الحفظ.») · the chip's other actions from the table above · «احذف» (danger text, confirm).
- «اكتب منه مقالًا»: confirm «يكتب النظام مقالًا جديدًا مبنيًا على هذا الموضوع، ولا ينسخ نصه، ويستهلك ذلك من رصيد الكتابة الآلية. يظهر مسودة في «المقالات» لتقرأها ثم تنشرها.» (linked: «لهذا الموضوع مقال بالفعل. تكتب مقالًا آخر؟ يستهلك ذلك من رصيد الكتابة الآلية.») → sequence identical to `topMakeArticle`: `S.generating[id]=Date.now()` → `EP.generateArticleFromTopic(t, (ok,newId,msg)=>…)` → on ok `EP.markTopicArticled(t,newId,…)` then open «المقالات» with the new draft's reader (`S.open=newId`); on failure the error sheet «تعذّر كتابة المقال» + «لم يُنشأ أي مقال، والموضوع بقي كما هو.» + the platform message (Arabic digits) + «أعد المحاولة» / «إغلاق». No technical hint text.
- «افتح المقال» → «المقالات» tab with the linked article's reader open (or the strip «المقال المرتبط لم يعد موجودًا» when not found).

### 4.3 «أرقام الموضوعات» (bottom card, replaces «لوحة تحليل AI»)
Source `platformTopicsAnalysis` (`GET /api/platform-topics-analysis`, no paid call). Shows: «موضوعات» `total_topics` · «تعليقات معتمدة» `total_comments`; «الأكثر تعليقًا» (top 5: title, source pill, «{n} تعليق»); «حسب الفئة المستهدفة» bars from `by_segment` (locked order, zeros shown); «حسب التخصص» bars from `by_category` (top 8); «ما يسأل عنه الناس في المحادثة» chips from `categories_in_demand` (`{category} · {count}`). `engagement_note` is never shown. Failed → «أرقام الموضوعات: غير متاح بعد» + retry. Button «حدّث» → `EP.reload('platformTopicsAnalysis')`.

## 5) Tabs «الأخبار», «التعليقات», «دليل الاستخدام»
Same card rule as §4.1: one main button per card; the card opens the item's sheet, which holds every other action.

### 5.1 «الأخبار» (`news`)
- Chips «مسودات ({n})» · «منشورة ({m})» · «الكل». Buttons «خبر جديد» (primary) · «مصادر الأخبار» (secondary).
- Card: title; pills «خبر», specialty; summary (2 lines, «بلا ملخص بعد» when empty); sources as links (`target=_blank rel=noopener`, max width, ellipsis) or «بلا مصدر»; country · date; status pill «مسودة»/«منشور». Main button: draft with ≥1 source and a summary → «انشر» (confirm «سيظهر الخبر للأعضاء على المنصة.») → `EP.updateNews(id,{title,is_published:true})`; incomplete draft → «أكمل الخبر» → news sheet; published → «عدّل» → news sheet.
- News sheet = old `nwsModal` fields and parsing, relabelled: «العنوان» · «الملخص (بصوت البروفيسور، ويظهر للأعضاء)» · «الدولة» · «التخصص» · «روابط المصادر (سطر لكل مصدر: الرابط | الاسم)» (ltr) · checkbox «منشور (ظاهر للأعضاء)» → «احفظ» → `EP.createNews(g)` / `EP.updateNews(id,g)` (exempt when the result is unpublished; confirm «سيظهر الخبر للأعضاء على المنصة.» when it saves a published news item). Other actions in the sheet: «أوقف النشر» (published; confirm «سيختفي الخبر من المنصة.») → `EP.updateNews(id,{title,is_published:false})`; «حوّله لموضوع» → confirm «يصبح الخبر موضوع نقاش على اللوحة.» → `EP.deriveTopicFromNews(t, (topic,newId)=>…)` then open «الموضوعات» on the chip of the new topic (from the reloaded `PTOPICS`, old `topicGotoNew` rule) with the card highlighted once; «احذف» (danger text, confirm) → `EP.deleteNews`.
- Sources sheet = old `nwsSourcesModal`, relabelled: «مصادر الأخبار (سطر لكل مصدر: الدولة | الرابط)» and «كلمات التصنيف (سطر لكل مجموعة: الاسم : كلمة، كلمة)» → «احفظ» → `EP.saveNewsSources({feeds, club_keywords})` (same shape; exempt: internal settings).

### 5.2 «التعليقات» (`comments`)
Three cards stacked:
1. «تنتظر قرارك» (`POPINIONS`): each row: body text (3 lines), «على: {topic_title}», author email (ltr, person link), date, verdict line (`v2ContentCommentVerdict`). Main button = `v2ContentSuggest` (abusive/off-topic «ارفض» → confirm «لن يظهر التعليق على المنصة.» → `EP.rejectOpinion`; undecided «افتح واقرأ» → comment sheet §6.6). Tapping the row opens the comment sheet too. Empty: «لا تعليقات تنتظر قرارك. التعليق المطابق للموضوع يُعتمد تلقائيًا، والمشكوك فيه فقط يصل هنا.»
2. «ظاهرة الآن» (`POPINIONS_APPROVED`): body, topic, author, date, the editor reply box when present («ردّ {editor_reply_by|هيئة التحرير}»). Main button «ردّ» / «عدّل الرد» → reply sheet: lead «يظهر الرد للجميع تحت التعليق باسم هيئة التحرير.», textarea («اكتب ردّ هيئة التحرير»), button «انشر الرد» → `EP.replyOpinion(o,{reply})` (the lead names the public effect, so the sheet is its own confirmation). Inside the same sheet: «اكتب ردًّا آليًا» (only when no reply) → confirm «يكتب النظام ردًّا ويظهر تحت التعليق باسم هيئة التحرير مباشرة، ويستهلك ذلك من رصيد الكتابة الآلية.» → `EP.replyOpinion(o,{ai:true})`; «احذف التعليق» (danger text) → confirm «يُحذف التعليق من المنصة نهائيًا.» → `EP.deleteOpinion`.
3. «أرقام التعليقات»: source `platformOpinionsNumbers` (`summarize=false`) → «تنتظر» `status_counts.pending` · «معتمدة» `approved` · «مرفوضة» `rejected`; «الأكثر تعليقًا» (top 5); «حسب التخصص» bars. Button «اكتب خلاصة» (secondary) → confirm «يكتب النظام خلاصة من آخر التعليقات المعتمدة، ويستهلك ذلك من رصيد الكتابة الآلية.» → one call `EP.api('GET','/platform-opinions-analysis?summarize=true')` → shows `insights` under the heading «خلاصة مكتوبة آليًا من آخر التعليقات المعتمدة», or `insights_note` when empty. The summary is kept in `S.summary` for the session (no second paid call on redraw). Failed → «أرقام التعليقات: غير متاح بعد» + retry.

### 5.3 «دليل الاستخدام» (`tutorials`)
- Button «قسم جديد» (primary). Grouped by `section` (group heading; «بلا تصنيف» for empty), ordered by `order`.
- Card: title, «ترتيب {order}», «فيديو» pill when `video_url`, status pill «منشور»/«مسودة». Main button «عدّل» → sheet.
- Sheet = old `tutModal` fields: «العنوان» · «القسم» · «الترتيب» · «النص (يظهر للأعضاء)» · «رابط الفيديو (اختياري، يوتيوب)» (ltr) · checkbox «منشور (ظاهر للأعضاء)» → «احفظ» → `EP.createTutorial(g)` / `EP.updateTutorial(id,g)` (same keys: title, section, order, body, video_url, is_published; exempt when the result is unpublished; confirm «يظهر هذا القسم للأعضاء فور الحفظ.» when it saves a published section). Other actions in the sheet: «أخفِ» (published; exempt, hiding is immediate) → `EP.updateTutorial(id,{title,is_published:false})`; «انشر» (draft; confirm «يظهر هذا القسم للأعضاء في دليل الاستخدام.») → `EP.updateTutorial(id,{title,is_published:true})`; «احذف» (danger text, confirm «يُحذف هذا القسم من الدليل.») → `EP.deleteTutorial`.
- Facts line at top: «{p} قسمًا منشورًا · {d} مسودة · {v} بفيديو». Failed → «دليل الاستخدام: غير متاح بعد» + retry.

## 6) Shared pieces inside the section

### 6.1 Confirmation sheet
`confirmSheet({title, lead, okLabel, danger, run})` built on `window.openModal` like D3 `openSheet`: lead paragraph, buttons «{okLabel}» (primary, or danger red for deletes) and «رجوع». On press: `window.__v2ctConfirmAt = Date.now()` (read by the shots guard), busy text «جارٍ التنفيذ…», both buttons disabled, `#epModal` marked busy (no close on scrim), then `run(done)`. Because the EP action functions call their callback on success **and** failure, `run` verifies the outcome from the reloaded data (e.g. the article is now `published`; the pending topic is gone from `PTOPICS_PENDING`; the work is gone from `PCREATIVE`) and the section shows a note strip «تمّ: {what}» (12 s, D3 `setNote`) or keeps the sheet open with «لم يتم. {EP.lastError}». No money actions exist in this section, so the money sheet (`V2.openMoney`) is not used.

**Always confirmed:** every publish, unpublish, approve, reject and delete; every save of an item that is already public (published article, news, tutorial section, topic on the board); every action that spends automatic-writing credit («اكتب مقالات الآن», «اكتب منه مقالًا», «اكتب ردًّا آليًا», «اكتب خلاصة», «موضوع جديد»). The lead of every credit action contains «يستهلك ذلك من رصيد الكتابة الآلية». A composer sheet whose lead already names the public or paid effect and whose button names the action («انشر الرد», «احفظ واكتب الإجابة المقترحة», the creative reject reason sheet) counts as the confirmation and sets `__v2ctConfirmAt` on press.

**Exempt (no sheet), and nothing else:** choosing «الفئة المستهدفة» · «اسحب الجاهز من المنصة» · «حوّله للكتابة» · saving a draft or an unpublished item («احفظ مسودة», «احفظ» on a draft article / unpublished news / unpublished tutorial / topic not on the board) · «أخفِ» a tutorial section · saving news sources. None of these shows anything new to the public or spends credit.

### 6.2 Person links
Any email shown (member topic author when present, comment author, creative creator, testimonial author) links to `#s/people/person/<key>` with `L.sectionHash('people','person',email)` (D2 pattern).

### 6.3 Visible copy rules
Plain standard Arabic, gender-neutral («صاحب الموضوع», «كاتبه»), Arabic digits via `L.util.ar`, no «يقوّم», no headline starting with «الذكاء», no English words, no domains in headings (domains only in links and ltr fields). The automatic writing is called «النظام» / «الكتابة الآلية», the platform's moderation «الفحص الآلي على المنصة». No judgement words without a fact behind them («آمن», «لا أحد ينتظره», etc.).

### 6.4 Creative work sheet
Title, kind label, creator, `body` (pre-wrap, max 40vh), `media_url` link «افتح الرابط», cover image when `cover_url`. Buttons «اعتمد وانشر» (primary) → confirm «سيظهر العمل للجميع في ركن الإبداع.» → `EP.decideInboxItem({apiKind:'creative', apiId:id}, 'approve', cb, '')` (returns a Promise `{ok,error}`, used for the inline result) · «ارفض» → sheet with a required reason (lead «اكتب سبب الرفض، ويصل إلى صاحب العمل.», button «ارفض وأرسل السبب») → `decideInboxItem(…, 'reject', cb, reason)`. After either decision: `EP.reload('platformCreative')` (and `EP.reload('inbox')`, which `decideInboxItem` already does), then verify the work left `PCREATIVE`.

### 6.5 Testimonial sheet
Course title, name, rating (text «{r} من ٥»), text, and the consent line from §2.3. «اعتمد» (primary) → confirm, lead by `consent_public`: `true` → «سيظهر الرأي باسم كاتبه على صفحة الدورة.»; `false` → «سيظهر الرأي بلا اسم على صفحة الدورة.»; missing → «سيظهر الرأي على صفحة الدورة.» → `POST /api/v2/testimonials/<id>/approve` `{confirmed:true}`. «ارفض» → confirm «لن يظهر الرأي على صفحة الدورة.» → `POST /api/v2/testimonials/<id>/reject` (no reason field exists on the platform). After either: `EP.reload('testimonials')` and `EP.reload('testimonialsApproved')`, then verify the row left `PTESTIMONIALS`.

### 6.6 Comment sheet (undecided comments)
Full body text, «على: {topic_title}», author (person link), date, the verdict line, and «سبب الفحص الآلي: {moderation.reason}» when present. Buttons: «اعتمد» (primary) → confirm «سيظهر التعليق للجميع تحت الموضوع.» → `EP.approveOpinion`; «ارفض» → confirm «لن يظهر التعليق على المنصة.» → `EP.rejectOpinion`; «احذف نهائيًا» (danger text) → confirm «يُحذف التعليق من المنصة نهائيًا.» → `EP.deleteOpinion`. For abusive/off-topic comments the same sheet opens from the row with «ارفض» as primary and «اعتمد» secondary.

## 7) Server (new file `backend/v2_content_routes.py`)
`def register(app, ns):` — `ns` is `globals()` of `app.py`, passed at registration; handlers look names up in `ns` **at request time** (`ns['Article']`, `ns['_platform_proxy']`, `ns['_audit']`, `ns['_no_store']`, `ns['_prerender_last']`, `ns['_prerender_running']`, `ns['_article_body_list']`), so the module never imports `app` and works under any module name. Decorators: `ns['token_required']`, `ns['roles_required']('admin')`. Registration: one line in `app.py` right before `# ---- v2 section routes end` (create the marker after the last `/api/v2/book-requests` route if missing):
`import v2_content_routes as _v2s_content; _v2s_content.register(app, globals())`

1. `GET /api/v2/content/overview` (admin, `no-store`) → read-only from local SQLite, no platform call, no prerender trigger:
   ```json
   {"articles": [{"id": 12, "title": "…", "status": "draft|published", "by": "…", "cat": "…", "date": "…", "slug": "…",
                  "created_at": "ISO|null", "published_at": "ISO|null", "updated_at": "ISO|null",
                  "words": 840, "has_image": true, "has_meta": false, "reviewed_by": "…|null"}],
    "prerender": {"state": "ok|error|skipped|never-run|running", "at": "ISO|null", "uploaded": 3},
    "now": "ISO"}
   ```
   `words` = whitespace tokens across `_article_body_list(a)` with a leading `## ` stripped; `has_meta` = the raw `meta_description` column is non-empty (the excerpt fallback in `serialize_article` does not count); `has_image` = `image_url` non-empty. `prerender.state` = `'running'` when `_prerender_running`, else `_prerender_last['state']`; `reason`/`error` text is never returned. Ordered by `created_at` desc. No body, no meta text, no keywords.
2. `GET /api/v2/testimonials?status=pending|approved|rejected` (admin, `no-store`; any other value ⇒ `pending`) → `_platform_proxy('GET','/api/bridge/testimonials',params={'status':s})`.
3. `POST /api/v2/testimonials/<id>/<action>` (admin; `action ∈ {approve,reject}` else 400 «إجراء غير معروف»; `id` must match `^[A-Za-z0-9_-]{1,64}$` else 400) — `approve` requires JSON `{"confirmed": true}` else 400 «أكّد النشر أولًا» → `_platform_proxy('POST', f'/api/bridge/testimonials/{id}/{action}')`; `_audit('testimonial.'+action, target=id)` only when `_resp_ok`. A platform 401/403 is returned as 502 «تعذّر الوصول إلى المنصة» (same rule as the D3 proxies).

No other server change. ⛔ `backend/prerender.py` and every `/api/content/*` route stay byte-identical.

## 8) Shared edits (minimal, listed for the integrator)
1. **`index.html` `renderView()`** — one generic dispatcher for all v2 sections, placed right after the D3 line, plus the bare-page class. If another section already added an equivalent registry, use that one and do not add a second:
   `if(window.V2_ON&&window.V2SEC){for(var _k in V2SEC){var _s=V2SEC[_k];if(_s&&_s.owns&&_s.owns(current)){var _ap=document.querySelector('.app');if(_ap&&window.V2SHELL&&V2SHELL.on)_ap.classList.add('v2-bare');return _s.render(current,v);}}}`
   (`V2S` is already taken by the current-section variable, hence `V2SEC`.)
2. **`index.html`** script/link block, and one new row in `OPSQ_LANDINGS` (today the inbox chip «شهادات بانتظار المراجعة» at line ~901 points to a key that does not exist):
   `testimonials_pending:function(){if(window.V2SHELL&&V2SHELL.on&&window.v2OpenSection){v2OpenSection('content','pipeline');return;}topicsTab='ideas';renderView();},`
   and rename that chip's label to «آراء متعلّمين بانتظار المراجعة».
3. **`backend/app.py`** one registration line + marker.
4. **`backend/tests/test_v2_d1b.py`** — update the `'content'` expectation to the six tabs above (all `mod 'topics'`), the total tab count (+4 for this section), the case `('topics', {'topicsTab': 'news'}, 'content', 'topics')` → `'content', 'news'`, and `'#topics': ('content', 'topics')` → `('content', 'pipeline')`.
5. **Home tile (required, not optional).** `v2-home.js` `openTile`: add `'content'` to the list that calls `host().openSection(key)` (files/disputes/money/books), so the tile opens «خط النشر». In `v2-logic.js` (the `// —— المحتوى` tile block) use the same words as the board: forms `['فكرة واحدة','فكرتان','أفكار','فكرة']` and `['رأي متعلّم واحد','رأيان لمتعلّمَين','آراء متعلّمين','رأيًا لمتعلّمين']`, fallback text «خط النشر», and `t.land = 'topics_drafts'` only (drop the branch to `testimonials_pending`). The tile still reads `ops/queue` (`topics_drafts` + `testimonials_pending`), the only counts the queue has; a full «ينتظرك» number on the tile needs P2.
6. **`v2-logic.js` `routeFor`** — one line after the `home` check: `if (s === 'topics') return pack(secOf('content'), tabOf('content', 'pipeline'));` (a bare old `#topics` link opens the section's front door; every call with an explicit `topicsTab` still goes through `sectionFor`).
7. **`dashboard-cloud/dashboard-api.js`** — exactly the edits in §1.4.
8. Possible overlap: testimonials are course testimonials. If the courses section also adds a testimonials proxy, keep one (this spec's `/api/v2/testimonials` and the `testimonials` loader) and show it in both places.

## 9) Coverage (old → new), so nothing needs «كل السجلات»
| Old | New |
|---|---|
| tabbar with 9–10 tabs | 6 section tabs + chips |
| مقترحة من الأعضاء / أفكار / واردة / قيد العمل / المنشورة / مرفوضة | «الموضوعات» chips + pipeline columns |
| فلتر الفئة (chips) | «التخصص» select |
| tpSegSelect / tpSegBadge | segment pill on cards; select in the topic sheet |
| topCreateModal / topReviewModal / topPendingModal / topMakeArticle / topArticleError / topOpenArticle / topicGotoNew | §4.1–4.2 |
| لوحة تحليل AI | «أرقام الموضوعات» (+ lanes) |
| viewContent + drawContent + createArticleModal | «المقالات › على الموقع» + reader/editor |
| delete of a published site article | «أوقف النشر» then «احذف المسودة» (two confirmed steps, §3.2) |
| blogTopicsModal | «أدوات الكتابة › موضوعات المدوّنة» |
| ولّد بالذكاء / جلب | «أدوات الكتابة › اكتب مقالات الآن / اسحب الجاهز من المنصة» |
| publishSchedulePanel (hardcoded) | dropped (not a source); see P1 |
| viewArticlesAuto + artDetailModal | «المقالات › على المنصة» |
| viewNews / nwsModal / nwsSourcesModal | «الأخبار» |
| viewComments (3 panels) | «التعليقات» (3 cards; summary only on confirmed demand) |
| prompt()/confirm() reply dialogs | reply sheet + confirm sheets |
| viewTutorials / tutModal | «دليل الاستخدام» |
| creative rows in the old inbox | pipeline `wait` + creative sheet (the inbox keeps its rows too) |
| testimonials (count only) | pipeline `wait` + testimonial sheet |

## 10) Tests — `backend/tests/test_v2s_content.py` (new)
Node (pure, via the same `_node` helper style as `test_v2_d3.py`):
1. `SECTIONS` content entry exactly as §1.1; every tab recognises itself via `sectionFor('topics', tab.st)`; every legacy `topicsTab` value (`pending ideas incoming working board rejected news articles blog auto comments tutorials pipeline`) lands on the right tab; `routeFor('#topics')` → `content/pipeline`; `routeFor('#tutorials')` and `sectionFor('tutorials')` → `content/tutorials`; `v2ContentTabFor` mapping incl. unknown → `pipeline`.
2. `v2ContentBoard`: `order` is `['wait','draft','idea','done']`; each kind in its column (fixture with one of each, incl. `archived`, `open` topic, published platform article → excluded); ordering in `wait` (member topics oldest first, then testimonials, comments, works); `done` holds site articles, news, human-approved comments and approved testimonials whose decision date is within 7×24 h, excludes an AI-approved comment and an item with no decision date; today/week counts against a fixed `now`.
3. Failed source ⇒ `partial[col]` and «{n}+»; all sources of a column failed ⇒ count `null` (renders «غير متاح بعد»), never 0; loading ⇒ `undefined` handled; testimonials fallback card from `opsQueue.testimonials_pending`; brain rule 4 not returned when a source failed.
4. `v2ContentFacts`: words, image, meta, reviewer, `dupTitle` by trimmed equality only (a title that merely contains another is **not** a duplicate); stale platform draft rule.
5. `v2ContentCommentVerdict` + `v2ContentSuggest` for every kind (labels exactly as §2.3): undecided comment ⇒ «افتح واقرأ» (never «اعتمد»); duplicate site/platform draft ⇒ «افتح وقارن»; testimonial consent line for `true` / `false` / missing.
6. `v2ContentPrerender` for `ok/error/skipped/never-run/running/missing` (+ `live`); `v2ContentPublishLead` includes the search-pages clause only for `ok/running`.
7. `v2ContentTopicChips` counts equal the old `topicTabOf` split on the same fixture; `PTOPICS_PENDING === null` ⇒ pending count `null` (not the `PTOPICS` number); `rejected` chip hidden at 0 unless active; `v2ContentSegments` keeps zero lanes in order and reports the gap.
8. Copy guard over `v2s/content.js`, the `v2s:content` block and the reworded strings in `dashboard-api.js`: no «يقوّم», no `AI`, no «SEO», no «DEEPSEEK», no «الوكيل الذكي», no «آمن», no «ولا أحد ينتظره», no «بالذكاء», no «استنّاه», no visible string starting with «الذكاء»; every Arabic string in §2–§6 present verbatim; every credit-action lead contains «رصيد الكتابة الآلية».
9. Static: `content.js` writes only through `EP.decidePendingTopic, setTopicSegment, updateTopic, deleteTopic, publishTopic, createTopic, generateArticleFromTopic, markTopicArticled, createArticle, updateArticle, publishArticle, unpublishArticle, rejectArticle, syncContent, runDailyContent, saveBlogTopic, publishArticleP, unpublishArticleP, deleteArticleP, createNews, updateNews, deleteNews, deriveTopicFromNews, saveNewsSources, approveOpinion, rejectOpinion, deleteOpinion, replyOpinion, createTutorial, updateTutorial, deleteTutorial, decideInboxItem` and `EP.api` POST only to `/v2/testimonials/`; it reads only the loaders of §1.4 (incl. `contentOverview, platformCreative, testimonials, testimonialsApproved, platformOpinionsNumbers`); it never references `platformOpinionsAnalysis`; the only `/platform-opinions-analysis` URL in it carries `summarize=true` and sits inside the «اكتب خلاصة» confirm `run`; `runDailyContent` is called with an `isOpen` option; no reference to `prerender` writes; no element with a «…» menu.
10. `dashboard-api.js` (node, with a stub `post`/`get`): the five new loaders hit the URLs of §1.4 and set `EP.state` to `error` on failure; `EP.muteNotes=true` silences `note` and `quietToast` but `EP.lastError` is still set; `runDailyContent(cb, {isOpen})` polls while `isOpen()` is true and stops when false, and without `opts` still checks `#ctRows/#artRows`.
11. Home tile: `v2-logic` content tile text uses «فكرة/أفكار» and «رأي متعلّم/آراء متعلّمين» (no «شهادة»), `land` is always `topics_drafts`; `v2-home.js` `openTile` contains `'content'` in the `openSection` list; `index.html` `OPSQ_LANDINGS` has `testimonials_pending`.
Server (pytest, Flask test client, `requests` monkeypatched, zero network):
12. `/api/v2/content/overview`: 401 anonymous, 403 employee, 200 admin, `Cache-Control: no-store`; no `body`/`meta_description` keys; `words` right for `## ` headings; excerpt-only article ⇒ `has_meta: false`; `prerender` maps `_prerender_last` and never contains `reason`/`error`; `_prerender_running=True` ⇒ `running`; no outgoing request.
13. `/api/v2/testimonials`: admin only; status passthrough and fallback to `pending`; approve without `confirmed` ⇒ 400 and no proxy call; approve with it ⇒ proxied to `/api/bridge/testimonials/<id>/approve` and audited; reject proxied; bad action/id ⇒ 400; platform 403 ⇒ 502.
14. CMS contract regression: `POST /api/content/articles/<id>/publish`, `PUT` of a published article, `DELETE` of a published article each call the monkeypatched `_prerender_push_async` with the same reason strings as today (`article-publish:<id>`, `article-update:<id>`, `article-delete:<id>`); a draft delete does not; the key set of `serialize_article` is unchanged; `backend/prerender.py` has no diff against the branch base (`git diff --quiet dash-v2-d3 -- backend/prerender.py`). (The new screen never deletes a published article directly — §3.2 — but the route stays and is still guarded.)
Run the old suite file by file as before; port-binding UI tests are rerun by the main session outside the sandbox.

## 11) Shots — `backend/tests/uiharness/v2_shots_content.py` (new; imports helpers from `v2_shots.py`, does not edit it)
Fixtures in a new `backend/tests/uiharness/content_fixtures.py` on top of `v2_fixtures.V2Platform`: bridge topics (every status/source, segments, linked article), pending topics, segments `[{id,label,count}]`, topics analysis (with `by_segment` zeros), opinions pending (one abusive, one off-topic, one undecided) and approved (one human-approved this week with reply, one AI-approved), opinions analysis (asserts `summarize=false` unless the summary shot), news (draft with/without sources, published this week), news sources, platform articles (draft, stale duplicate, published), tutorials (2 sections, one with video, one draft), creative (song with link, poem), testimonials pending (two: one without rating, one with `consent_public:false`) and approved (one this week); local SQLite seeded with site articles (draft complete, draft without meta/image, draft duplicating a published title, 3 published in the last 7 days with one today, one older). `_prerender_push_async` stubbed; `_prerender_last` set to `ok` (and `error` for one shot). Every platform write is recorded; no real origin is reachable.
Saved to `docs/v2/final/shots-content/` at desktop 1440×900 (`d-`), tablet 820×1180 (`t-`), mobile 390×844 (`m-`):
1. `pipeline` full (all four columns filled, order ينتظرك · مسودات · أفكار · نُشر) — d/t/m, plus mobile on each of the 4 segments.
2. `pipeline-down` with `platformOpinions`, `platformCreative` and `contentOverview` failing (strip + «+» counts + «غير متاح بعد» pill).
3. `confirm-member-topic`, `comment-sheet` (undecided, from «افتح واقرأ»), `confirm-comment-approve`, `testimonial-confirm-no-name`.
4. `articles-site` list, `article-read` (draft), `article-compare` (duplicate), `article-edit`, `article-publish-confirm` (`ok`) and `article-publish-confirm-plain` (`error`), `article-published-note`, `article-read-published` (no delete; the two-step line).
5. `articles-platform` with the duplicate badge and brain line; `writing-tools` sheet; `blog-topics` sheet; `write-now` confirm.
6. `topics-pending` (incl. `pending-down` with `platformPendingTopics` failing ⇒ «—»), `topics-ideas`, `topics-board`, `topic-sheet` (segment select inside), `new-topic` (credit lead), `make-article-confirm`, `make-article-failed` (generate route forced 503), `topics-numbers`.
7. `news` list, `news-edit`, `news-sources`.
8. `comments` (three cards, no summary), `summary-confirm`, `comments-summary` (after the confirmed «اكتب خلاصة»), `reply-sheet`.
9. `tutorials` list and `tutorial-edit`.
10. `empty` (all sources empty) and `old-links` (`#topics` → «خط النشر», `#tutorials`, `#s/content/topics` land on the new tabs; the home tile «المحتوى» opens «خط النشر»; no `#topicsTabs` / `.tabbar` / `.kpis` / `.inboxwrap` in `#view`).
The script fails on: horizontal page scroll at 390; a visible target under 44px, or a `.v2ct` main button / sheet button under 52px on mobile; more than one primary button in any card or sheet; any «…» menu; «undefined/NaN/null/[object Object]» visible; «٠»/«0» shown in a slot whose source failed; any request to a non-fixture origin; **any recorded platform write not preceded (within 5 s) by a `__v2ctConfirmAt` press, unless the shot step that caused it is one of the exempt actions of §6.1 (the script lists those steps by name)**; any call to `/platform-opinions-analysis` without `summarize=false` outside shot 8 `comments-summary`; any call to `/platform-articles/daily-run` or `generate-article` outside shots 5/6 (the fixture answers them; nothing real is reached).
Also rerun `v2_shots.py d1b` to prove the shell still renders the section header with six tabs.

## 12) Decisions (expert review, revision 2)
All fifteen points received were valid and are applied; the parts not taken as written are below. (The review text was cut off after the fifteenth point; nothing beyond it was received.)
1. **Tile = column.** Applied: the tile opens «خط النشر» (§8.5, now required), uses the board's words («فكرة», «رأي متعلّم», never «شهادة»), `#topics` and the old `testimonials_pending` chip land on the pipeline, `OPSQ_LANDINGS.testimonials_pending` added. **Not taken:** making the tile number equal the «ينتظرك» column. `ops/queue` only has `topics_drafts` and `testimonials_pending` (`ops_bridge.py:1030-1039`); counting more on the home screen means loading five platform lists for one tile. The tile states exactly what it counts, and P2 asks the platform for the missing counts. `OPSQ_LANDINGS.topics_drafts` stays on «الموضوعات › أفكار» for the old inbox chip, because that chip counts exactly that list.
2. **Real loaders** for creative, testimonials (pending and approved), the overview and the comment numbers; reload after every decision. Applied (§1.4, §6.4, §6.5).
3. **Confirm vs exempt.** Applied: one explicit exempt list (§6.1), the same list drives the shots guard (§11). Approving a comment and publishing a tutorial now confirm; hiding a tutorial stays direct. Saves of already-public items also confirm (same rule, the reviewer's principle carried to edits).
4. **Write-now polling.** Applied by the `isOpen` option (one place for the polling, old screen untouched) plus the honest lead and muted/reworded toasts (§1.4, §3.4).
5. **Testimonial consent** conditioned on `consent_public` (§2.3, §6.5). The bridge returns the full row; the platform only accepts a testimonial with consent, but the screen does not rely on that.
6. **Undecided comment ⇒ «افتح واقرأ»**, never «اعتمد» (§2.3, §6.6).
7. **One main button.** Applied everywhere (articles, topics, news, comments, tutorials; «محتوى جديد» removed; no «…» menu). Extended to news, tutorials and comments cards, which had the same problem.
8. **Judgement words** removed («لا أحد ينتظره», «آمن»); duplicates open a compare view and delete from there.
9. **Search-pages promise** conditioned on the prerender state (§3.2).
10. **No fallback count** for member topics (§4.1).
11. **Deleting a published article:** chose the two-step path (stop publishing, then delete the draft), stated in the sheet and in §9. One fewer destructive button on a public item.
12. **One column order** in DOM and on every width, «ينتظرك» first and named the same everywhere (§2.2, §2.5).
13. **Credit actions confirm** with the same sentence; «موضوع جديد» names the cost in its own sheet instead of a second sheet (one sheet, one decision).
14. **«نُشر هذا الأسبوع»** now includes news, human-approved comments and approved testimonials. **Not taken:** topics opened on the board — the platform keeps no opening date for topics (only `updated_at`, which any edit moves), so listing them would invent a date (P3). AI-approved comments are left out: they are not the founder's decisions.

## Platform needs
None blocks this round; each missing source simply hides its line (never «٠»).
- **P1. Read-only content health for the brain line «الكتابة الآلية اليوم».** Today the only source is `POST /api/bridge/content/health-check`, which is not usable from a screen: it can send a Telegram alert and it queries the DeepSeek balance. Needed:
  `GET /api/bridge/content/health` (header `X-ELP-Metrics-Secret`; no side effects: no Telegram, no balance call, no generation) →
  ```json
  {"date": "2026-10-30", "articles_today": 3, "expected_today": 5,
   "last_run": {"at": "ISO", "ok": true, "articles": 3, "topics": 2},
   "empty_runs": [{"track": "news|segment|feature|topic", "reason": "bank_empty|generation_failed|duplicate"}],
   "bank_runway_days": 12}
  ```
  (`last_run` may be `null`; `expected_today` may be `null` when no schedule is configured.) The dashboard would proxy it as `GET /api/v2/content/health` (admin, no-store) and the pipeline top bar would add the pill «الكتابة الآلية اليوم: {articles_today} من {expected_today}» and, on an empty run, the brain line «مسار {track} لم يكتب شيئًا اليوم: {plain reason}». Not built in this round.
- **P2. Counts for the home tile.** Add to `GET /api/bridge/ops/queue`: `topics_pending_review` (member topics awaiting a decision), `opinions_pending`, `creative_pending`. Then the tile can read «{n} ينتظرك» with the same number as the «ينتظرك» column.
- **P3. Topic opening date.** Stamp `opened_at` when a topic moves to `open/published`, so topics opened this week can join «نُشر هذا الأسبوع».
