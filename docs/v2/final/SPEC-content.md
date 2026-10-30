# Final round · Section «المحتوى» (key `content`) — rebuild in the new style

**Founder order (2026-10-30):** «الشاشات القديمة دي تظبطها، والزرار تظبط، والاشكال وكل حاجة تظبط، بحيث ان يخلص الداشبورد نهائيا». This is FINAL work, not a draft.
**Worktree / branch:** `.worktrees/content` · `final-content` (from `dash-v2-d3@7d1aa83`). Merged later with 10 other sections.
**Reference style:** D1-B shell, D2 ticket boards (`v2-d2.js/css`, `.v2d-*`), D3 sheets and source handling (`v2-d3.js/css`, `.v3-*`, `twoStage`, `warnStrip`, `unavailable`).
**Concept boards:** there is no dedicated Content board. The approved row gives the pattern: POS-Home tile «المحتوى» («٦ مقالات جاهزة · تعليقان»), POS-Tickets (columns of tickets with a coloured strip, a timer, one brain line and one button), POS-Focus (one decision at a time). This section applies POS-Tickets to the content pipeline.

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

Two inflows that the old dashboard only shows inside the old inbox («كل الوارد») but which belong here: **ركن الإبداع** works (`GET /api/platform-creative?status=pending_review`, decided with `EP.decideInboxItem({apiKind:'creative',apiId},…)`), and **course testimonials** (the content tile already counts `opsQueue.testimonials_pending`, but there is no screen anywhere; the platform bridge `GET /api/bridge/testimonials` + `POST /api/bridge/testimonials/{id}/approve|reject` exists and the dashboard has no proxy).

Two old behaviours this round deliberately drops (both violate founder rules):
- `publishSchedulePanel` prints a **hardcoded** list of 5 daily times. It is not read from any source, so it is not a fact. It is removed. A real schedule line comes back only through «Platform needs» §P1.
- The old comments screen loads `/api/platform-opinions-analysis` with the default `summarize=true` on **every visit**, which makes the platform call DeepSeek every time (a paid call, `routes/topics.py:2527`). The new screen always reads it with `summarize=false`. The written summary is fetched only when the founder presses «اكتب خلاصة».

Also removed from visible copy: the raw English `engagement_note` («comments = approved opinions…»), the «DEEPSEEK_API_KEY» hint, every «AI», «SEO», «الوكيل الذكي», «(app.elprofessor.net)» domain in titles, and «الذكاء» at the start of any headline.

**«كل السجلات»: none.** Every old tab, panel, sheet and action above has a new home (coverage table in §9). The section has no tab with an old-look screen.

## 1) Routing: keep the old module name, render it new (no shared routing changes)
The six new tabs all keep `mod: 'topics'` and are told apart by `topicsTab` (exactly as `money/all` + `money/manual` did with `finTab`/`escTab`). That keeps every old door working without touching `sectionFor`, `ALIASES`, `REDIRECTS` or `MODULES`:
- `#topics`, `#tutorials`, `go('topics')`, inbox rows with `dest:'topics'`, `OPSQ_LANDINGS.topics_drafts` (sets `topicsTab='ideas'`), the home tile (`goOps('topics','topics_drafts')`) and `ALIASES.tutorials` all resolve through the existing `sectionFor('topics', {topicsTab})`.
- Under the shell, `renderView()` hands `current==='topics'` to the new section renderer (§1.3) **before** the old `if(current==='topics')` branch. The old branch is only reachable with the switch off (and for the `employee` role, which never gets the shell). The old code stays in `index.html` untouched.

### 1.1 `SECTIONS` entry (the only edit in the shared map, `dashboard-cloud/v2-logic.js`)
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
- `'pipeline'` is a new `topicsTab` value used only under the shell. `STATE_DEFAULTS.topicsTab` stays `'ideas'` (shared), so `routeFor('#topics')` still lands on `content/topics` (the existing d1b test expects that).
- Sub-state inside a tab (the chips in «الموضوعات», the «على الموقع / على المنصة» switch in «المقالات») is written with `window.v2OpenSection('content', tab, {replace:true, st:{topicsTab:v}})`. `V2_SETTERS.topicsTab` already exists, so the header, the hash `#s/content/<tab>` and `v2Reconcile` all stay right. The category filter and the open item live in the section's own state `S` (not in shared state).

### 1.2 Pure helpers (end of `v2-logic.js`)
A separate IIFE at the very end of the file, inside `// ===== v2s:content =====` … `// ===== /v2s:content =====`. It reads `root.V2L` (the exported `api`, which is also `module.exports`) and attaches functions to it, so node tests reach them as `L.v2Content…`. It reuses `L.util.ar`, `L.util.U`, `L.util.agoText`, `L.v2TimerText`, `L.v2TimerTone`, `L.NA`. No DOM, no `EP`, no `Date.now()` (the caller passes `now`).

- `v2ContentTabFor(topicsTab)` → `'pipeline'|'articles'|'topics'|'news'|'comments'|'tutorials'` (`blog`/`auto` → `articles`; the six topic states → `topics`; unknown → `pipeline`).
- `v2ContentBoard(src, now)` → `{cols:{idea,draft,wait,done}, counts, partial, failed, top}` (§2.2). `src` holds each source as an array, or `null` when it failed, or `undefined` while loading.
- `v2ContentFacts(articleMeta, publishedTitles)` → `{words, hasImage, hasMeta, reviewer, dupTitle, line}` for one site article (§2.3).
- `v2ContentSuggest(item)` → `{label, act}` (the one main button; §2.3).
- `v2ContentCommentVerdict(moderation)` → `{key:'abusive'|'offtopic'|'open', text, suggest:'reject'|'approve'}`.
- `v2ContentPrerender(p, now)` → `{text, tone}` from the overview route's `prerender` block (§2.1).
- `v2ContentTopicChips(PTOPICS, PTOPICS_PENDING, active)` → chip list with counts (§4); reuses the old `topicTabOf` rules verbatim (copied into the helper; the old function stays in `index.html`).
- `v2ContentSegments(analysis)` → the lanes from `by_segment` in the locked order, zeros kept, plus `{gap: label|null}` = the first lane with count 0.

### 1.3 Front-end files (new)
- `dashboard-cloud/v2s/content.js` — `window.V2SEC = window.V2SEC || {}; V2SEC.content = { owns(mod), render(mod, view) }`. `owns('topics')` is `true` (under the shell only, enforced by the dispatcher). It also exposes `V2SEC.content.tabFor` for tests.
- `dashboard-cloud/v2s/content.css` — every rule under the root class `.v2ct` (and `.v2ct-m` for sheet bodies inside `#epModal`). Tokens copied from `.v2d`: `--wine:#9E2B4E; --paper:#FBFAF7; --paper2:#F6F1EA; --ink:#21262E; --red:#C8102E; --line:#E9E1D6; --amber:#8F5F00; --amber-bg:#FFF6DD; --green:#187E4E; --mute:#6B665C`. Section accent (from the tile RGB) `--accent: rgb(190,88,48)` is used only on the column headers and the section photo strip. Fonts: 'IBM Plex Sans Arabic' body, 'Cairo' 800 for headings and buttons.
- `index.html`, inside `<!-- v2 sections begin -->` … `<!-- v2 sections end -->` (created right after the `v2-d2.js` script tag if missing), one line each, alphabetical by key: `<link rel="stylesheet" href="v2s/content.css">` and `<script src="v2s/content.js"></script>`.

Rendering contract (same as D2/D3): `render(mod, view)` draws `<div class="v2ct">…</div>` into `#view`, keeps its own state `S = {view, tab, sub, cat, open, busy:{}, note, generating:{}, sig}`, redraws on a signature of its sources' states, runs a 60 s timer tick for ticket times (no reload), never redraws while `#epModal` is open with a busy flag, and stops when `host().current() !== 'topics'`. Reads the current inner tab with `window.v2Snapshot().topicsTab` (global function in `index.html`).

## 2) Tab «خط النشر» (default) — the pipeline board

### 2.1 Top bar (brain line + facts)
Left to right (RTL): the brain avatar `v2/img/brain-avatar.jpg` + one sentence; then up to three fact pills; then the button «محتوى جديد» (secondary) which opens a small chooser sheet: «مقال للموقع» · «موضوع للنقاش» · «خبر» · «قسم في دليل الاستخدام» (each opens the same editor sheet as its tab).

Brain sentence, first rule that applies (all counts from the board, §2.2):
1. member topics > 0: «ابدأ بموضوعات الأعضاء: {N} ينتظر صاحبه قرارك، أقدمها منذ {age}.»
2. else waiting comments/works/testimonials > 0: «{N} ينتظر قرارك من الأعضاء والمتعلّمين.»
3. else site drafts > 0: «{N} مسودة للموقع جاهزة للقراءة.»
4. else: «لا شيء ينتظر قرارك الآن.»
If the source behind a rule failed, that rule is skipped and the strip in §2.4 says so (never «٠»).

Fact pills (each hidden when its source is loading; «غير متاح بعد» when it failed):
- «نُشر على الموقع اليوم: {n}» and «هذا الأسبوع: {m}» — from `GET /api/v2/content/overview` → `articles[].published_at` (status `published`), counted in the viewer's local day / last 7×24 h relative to `now`.
- Search pages: `v2ContentPrerender(overview.prerender)`:
  - `ok` → «صفحات محركات البحث حُدّثت منذ {age}» (green)
  - `running` → «صفحات محركات البحث تتحدّث الآن» (neutral)
  - `error` → «تعذّر آخر تحديث لصفحات محركات البحث (منذ {age}) — يُعاد مع أول نشر» (red)
  - `skipped` / `never-run` / missing → «تحديث صفحات محركات البحث: غير متاح بعد»
  Basis: `_prerender_last` / `_prerender_running` in `backend/app.py`, which `_prerender_push_async` sets after every publish, edit of a published article, delete of a published article, blog-topic save, bulk unpublish and the cron. «يُعاد مع أول نشر» is literally what the code does.

### 2.2 Columns (pure `v2ContentBoard`)
Four columns, D2 look (`.v2d-cols` geometry, re-declared under `.v2ct`): a header with the label and a count chip, then tickets. The split is by **who is waiting**, which is a fact, not a judgement.

| Column | Label | Header note | Strip tone | What goes in (source → filter) | Order |
|---|---|---|---|---|---|
| `idea` | «أفكار» | «مادة خام تنتظر أن تتحول إلى نقاش أو خبر منشور» | ink | topics `status:'draft'` and `source!=='expert'` (`PTOPICS`) · topics `source:'expert'` and status not `open/published/merged/pending_review/rejected/archived` · news `status:'draft'` (`PNEWS`) | newest first |
| `draft` | «مسودات» | «ما نكتبه نحن، ولا أحد ينتظره» | amber | site articles `status:'draft'` (overview) · platform articles `status:'draft'` (`PARTS`) · topics `status:'merged'` · topics being written now (`S.generating`) | generating first, then oldest first |
| `wait` | «ينتظر قرارك» | «أصحابها ينتظرون» | wine; red when older than 48 h | member topics (`PTOPICS_PENDING`) · testimonials pending · comments pending (`POPINIONS`) · creative works `pending_review` | member topics oldest first, then testimonials, comments, works (each oldest first) |
| `done` | «نُشر هذا الأسبوع» | «على الموقع خلال ٧ أيام» | green, dimmed | site articles `status:'published'` with `published_at` within 7×24 h of `now` | newest first |

- Each column shows at most 6 tickets, then a button «و{n} أخرى — افتح القائمة» that opens the matching tab and chip (`idea` → «الموضوعات › أفكار», `draft` → «المقالات», `wait` → the chip of the first hidden kind, `done` → «المقالات › منشورة»).
- Excluded: topics `archived`; topics `open/published` (they live in «الموضوعات › على اللوحة»); news `published`; platform articles `published` (they have no ticket, only the list).
- Counts: `counts[col]` = number of items from sources that loaded. If any source of that column failed → `partial[col] = true` and the chip reads «{n}+» with the title «العدد ناقص — تعذّر جلب بعض المصادر». If **every** source of the column failed → the chip reads «غير متاح بعد» and the column body is the D3 `unavailable` block «{column}: غير متاح بعد» + «أعد المحاولة». Never «٠» for a failed source. An empty but loaded column shows «لا شيء هنا الآن».
- Testimonials count fallback: if `/api/v2/testimonials` failed but `opsQueue.testimonials_pending` is a number, the `wait` column shows one count card «{n} رأي متعلّم ينتظر المراجعة» with «أعد المحاولة» (count from the existing queue, no list).

### 2.3 Tickets
Same anatomy as `ticketHtml` in D2: coloured strip with the type label and the time, title as a button (opens the item), one «who» line, one brain line (avatar + sentence), one main button. Times use `L.v2TimerText` (`«منذ ٣ س»`), refreshed by the 60 s tick. Slim tickets (strip + title + one line, no button) in `done`.

| Kind | Strip label | Time from | «Who» line | Brain line (facts only) | Main button (`v2ContentSuggest`) |
|---|---|---|---|---|---|
| member topic | «موضوع من عضو» | `PTOPICS_PENDING[].at` | `category` or «بلا تخصص» | «القرار يصل إلى صاحب الموضوع · الفئة: {segment_label}{ (اختيار آلي)} » or «… · بلا فئة» | «اعتمد وبلّغ» → confirm sheet §6.1 → `EP.decidePendingTopic(t,'approve',cb)` |
| testimonial | «رأي متعلّم» | `created_at` | `name` → person link by `user_email` | «{course_title} · التقييم {rating} من ٥ · وافق كاتبه على النشر باسمه» (rating part omitted when null) | «اعتمد» → confirm sheet → `POST /api/v2/testimonials/<id>/approve {confirmed:true}` |
| comment | «تعليق» | `POPINIONS[].at` | «على: {topic_title}» | `v2ContentCommentVerdict`: abusive → «الفحص الآلي على المنصة: قد يحوي إساءة»; `on_topic===false` → «الفحص الآلي على المنصة: خارج الموضوع»; else «لم يحسمه الفحص الآلي» | abusive/off-topic → «ارفض» (confirm §6.1) → `EP.rejectOpinion`; else «اعتمد» → `EP.approveOpinion` (one tap, as today) |
| creative work | «عمل إبداعي» | `created_at` | `creator_name` → person link by `creator_email` | «{kind: أغنية/فيديو/قصيدة/عمل آخر} · {has media_url ? 'معه رابط' : 'بلا رابط'}» | «افتح وراجع» → reader sheet §6.4 |
| site draft | «مقال للموقع» | overview `created_at` | `by` | `v2ContentFacts.line`: «{words} كلمة · {بصورة/بلا صورة} · {بوصف لمحركات البحث/بلا وصف لمحركات البحث} · {راجعه {reviewer}/لم يراجعه أحد}»; if `dupTitle` → «عنوانه مطابق لمقال منشور» | `dupTitle` → «افتح وقارن»; else «اقرأ وانشر» → article reader §3.2 |
| platform draft | «مقال على المنصة» | `PARTS` raw `created_at` | category label (`feature` «شرح المنصة», `news` «تحليل خبر», `law` «قانوني», `guide` «دليل», `platform` «المنصة», `other` «أخرى») | stale (same trimmed title published on the site) → «عنوانه منشور بالفعل على الموقع، وحذف هذه النسخة آمن»; else «تظهر في صفحة المقالات على المنصة بعد النشر» | stale → «احذف المكرر» (confirm) → `EP.deleteArticleP`; else «اقرأ وانشر» → reader §3.3 |
| topic being written | «يُكتب من النقاش» | topic `at` | category | `merged_article` or `ai_answer` non-empty → «النص جاهز للمراجعة»; else «لم يُكتب النص بعد» | ready → «انشر على اللوحة» (confirm) → `EP.publishTopic`; else «افتح» → topic sheet §4.2 |
| generating now | «يُكتب المقال الآن» | start time in `S.generating` | topic title | «يكتب النظام مقالًا جديدًا من هذا الموضوع، ويظهر مسودة عند انتهائه» | none (status text «جارٍ الكتابة…») |
| idea topic | «فكرة» / «من خبر» (source `news`) / «من خبير» (source `expert`) | topic `at` | category | «{source label} · {category} · الفئة: {segment_label}/بلا فئة»; plus «معه إجابة مقترحة» when `ai_answer` | has `ai_answer` → «اعتمد للنقاش» (confirm) → `EP.updateTopic(id,{title,status:'open'})`; else «افتح وراجع» → topic sheet |
| news draft | «خبر» | news `at` | `country` · `specialty` | «{n} مصدر» or «بلا مصدر» · «{بملخص/بلا ملخص}» | sources ≥1 and summary → «انشر الخبر» (confirm) → `EP.updateNews(id,{title,is_published:true})`; else «أكمل الخبر» → news sheet |
| published (done) | «نُشر» | `published_at` | `by` | — | link «اعرضه على الموقع» (same URL as today: `https://elprofessor.net/article.html?id=<id>`) |

`dupTitle`: exact equality of trimmed titles against published site articles (never "contains"; the CLAUDE.md lesson). Stale platform draft: same rule against the site list (the old `_blogTitles` logic).

### 2.4 Failure / loading
- Loading (any pipeline source `idle/loading`): each column shows two grey placeholder tickets; the brain line reads «…جارٍ جمع المحتوى».
- Failed sources: one strip under the top bar (D3 `warnStrip`): «تعذّر جلب: {labels joined by ' · '} — ما يظهر ناقص، وليس معناه أنه لا شيء» + «أعد المحاولة» (reloads only the failed ones). Labels: `content` «مقالات الموقع» · `overview` «حالة مقالات الموقع» · `platformArticles` «مقالات المنصة» · `platformTopics` «الموضوعات» · `platformPendingTopics` «موضوعات الأعضاء» · `platformOpinions` «التعليقات» · `platformNews` «الأخبار» · `creative` «أعمال ركن الإبداع» · `testimonials` «آراء المتعلّمين».

### 2.5 Layout
- **Desktop (≥1180, 1440 shot):** 4 equal columns (`grid-template-columns: repeat(4, minmax(0,1fr))`, gap 14px) inside the 1360px container; column background `--paper2`, radius 22px; tickets white, radius 18px.
- **Tablet (820):** 2×2 grid (`idea draft` / `wait done`), `wait` first in reading order (DOM order: wait, draft, idea, done so screen readers meet the waiting items first; visual order by CSS `order`).
- **Mobile (390):** a strip of 4 segment buttons with counts («أفكار» · «مسودات» · «ينتظرك» · «نُشر»), 60px tall, the active one dark (`.v2d-segb` look); one column at a time, default `wait` if it has items, else `draft`. Tickets full width; main button 52px; no horizontal page scroll (the segment strip is a 4-column grid, not a scroller).

## 3) Tab «المقالات» (`topicsTab: articles|blog|auto`)

### 3.1 Screen
- A two-option switch at the top: «على الموقع» (`articles`, default; `blog` lands here) · «على المنصة» (`auto`). Under it one line explaining the difference in plain words:
  - site: «مقالات elprofessor.net: يقرؤها الناس ومحركات البحث.»
  - platform: «مقالات صفحة المقالات داخل المنصة.»
- Toolbar (site): «مقال جديد» (primary) · «موضوعات المدوّنة» · «اسحب الجاهز من المنصة» · «اكتب مقالات الآن». Toolbar (platform): «اكتب مقالات الآن».
- Filter chips (site): «مسودات ({n})» · «منشورة ({m})» (counts from `content` loader, `status`).
- List of article cards (one column on all widths, max 880px, centred): title (Cairo 800 17px), «{by} · {date}», status pill («مسودة» amber / «منشور» green), fact chips from `v2ContentFacts` («{n} كلمة», «بلا صورة», «بلا وصف لمحركات البحث», «راجعه {x}»), «عنوانه مطابق لمقال منشور» (amber) when `dupTitle`. Whole card is a button → reader. On the platform list: title, excerpt (2 lines), category label, status pill («مسودة» / «منشور على المنصة»), «عنوانه منشور بالفعل على الموقع» badge for stale drafts, and at the top a brain line when stale > 0: «{n} مسودة هنا عناوينها منشورة على الموقع، وحذفها آمن.»
- Data: site list = `content` loader (`TOPICS` for list, `EP.data.content.raw` for body/meta/image), joined by id with `overview.articles` (words, `has_meta`, `created_at`). If `overview` failed, the fact chips are hidden and the strip says «حالة مقالات الموقع: غير متاح بعد»; the list still works. Platform list = `platformArticles` (`PARTS` + raw).
- Empty: site drafts «لا مسودات الآن. اكتب مقالًا جديدًا أو اسحب الجاهز من المنصة.»; platform «لا مقالات على المنصة بعد.»

### 3.2 Site article reader + editor (focus sheet)
Opened in `#epModal` (via `window.openModal`) with the body class `.v2ct-m`; full screen on mobile, 920px wide on desktop/tablet. Two stages in one sheet (D3 `twoStage` style, not the old drawer):
- **Read stage:** kicker line «{cat} · {kicker}»; title; status pill; the facts line; excerpt (bold); body rendered from `raw.body` (lines starting with `## ` → `<h3>`, others → `<p>`, all escaped — same rendering rule as the old `drawContent`); image preview if `image_url`. Buttons:
  - draft: «انشر على الموقع» (primary) · «عدّل» · «احذف المسودة» (danger, text button).
  - published: «اعرضه على الموقع» (link, same URL as today) · «عدّل» · «أوقف النشر».
- **Edit stage** (also used for «مقال جديد»): exactly the old fields and mapping of `createArticleModal`, in this order, labels in plain Arabic:
  «العنوان» (`a_t`) · «التصنيف» (`cat`, placeholder «قانون الشركات») · «الوسم» (`kicker`, placeholder «تشريعات») · «المقتطف» · «نص المقال» (textarea, «افصل بين الفقرات بسطر فارغ، وابدأ العنوان الفرعي بـ ##») · «الكاتب» (`by`, default «الذكاء + رأي خبير» on new — **changed to «فريق البروفيسور»** per «لا نبدأ بالذكاء») · «رابط صورة المقال» (ltr) · «وصف محركات البحث» («الجملة التي تظهر تحت العنوان في جوجل، وتبدأ بالإجابة المختصرة») · «راجعه (اختياري)» («اسم من راجع المقال فعلًا، واتركه فارغًا إن لم يُراجَع»).
  The `gather()` defaults stay byte-for-byte (`'مقال بلا عنوان'`, `'قانوني'`, `'مقال'`, `'الإدارة'`) and the payload goes through the same functions: edit → `EP.updateArticle(t, g, cb)`; new → «احفظ مسودة» `EP.createArticle(g, false, cb)` or «احفظ وانشر الآن» → confirm sheet → `EP.createArticle(g, true, cb)`. The edit note «رابط المقال المنشور ثابت ولا يتغيّر بتغيير العنوان، وتاريخ آخر تحديث يتحرك فقط عند تعديل جوهري في النص.» stays.
- **Publish confirm** (§6.1): lead «سيظهر «{title}» على الموقع الآن، وتتحدّث صفحته لمحركات البحث خلال دقائق.» → `EP.publishArticle(t, cb)`. After the reload, success is checked (`status==='published'` in the reloaded list) → note «نُشر على الموقع. صفحته لمحركات البحث تتحدّث خلال دقائق.»; then `overview` is reloaded once after 60 s so the prerender pill shows the new state.
- **Unpublish confirm:** «سيختفي «{title}» من الموقع وتُحذف صفحته من محركات البحث مع التحديث القادم.» → `EP.unpublishArticle`.
- **Delete draft confirm:** «ستُحذف هذه المسودة نهائيًا ولا يمكن استرجاعها.» → `EP.rejectArticle`.
- ⛔ No new write route for articles; no change to `backend/prerender.py`, `_prerender_push(_async)`, `serialize_article`, `_apply_article_fields`, `/api/content/*`. The prerender triggers fire exactly where they fire today (publish, update of a published article, delete of a published article, blog-topic save).

### 3.3 Platform article reader
Same sheet, read stage only (body from `EP.data.platformArticles.raw[].body`, array or string — same branches as `artDetailModal`). Buttons: draft → «انشر على المنصة» (confirm «سيظهر في صفحة المقالات داخل المنصة.») → `EP.publishArticleP`; published → «أوقف النشر» → `EP.unpublishArticleP`; always «احذف» (confirm «سيُحذف «{title}» من المنصة نهائيًا.») → `EP.deleteArticleP`.

### 3.4 Toolbar sheets
- «موضوعات المدوّنة» → sheet listing `EP.blogTopics(cb)` rows: path line (ltr) «/blog/topic/{slug}» · «{count} مقال منشور», «العنوان» input (max 120), «الوصف» textarea (max 400), «احفظ» → `EP.saveBlogTopic(cluster_id, {label, description}, cb)` (server triggers prerender as today), «اعرض الصفحة» link when `count>0`. Lead: «العنوان والوصف يظهران على صفحة الموضوع وفي قائمة الموضوعات بالمدوّنة. الرابط ثابت ولا يتغيّر.» Errors inline in the row.
- «اسحب الجاهز من المنصة» → no sheet, one tap → `EP.syncContent(cb)` (button shows «جارٍ السحب…»).
- «اكتب مقالات الآن» → confirm sheet: «يبدأ النظام كتابة ٣ مقالات وموضوعين كمسودات. الكتابة تستهلك من رصيد الكتابة الآلية، وتظهر المسودات هنا خلال دقائق.» Buttons «ابدأ الكتابة» / «رجوع» → `EP.runDailyContent(cb)` (unchanged: its own 30 s × 6 sync polling).

## 4) Tab «الموضوعات» (`topicsTab: pending|ideas|incoming|working|board|rejected`)

### 4.1 Screen
- Chips (pure `v2ContentTopicChips`), each with a count: «من الأعضاء» (`pending`, count from `PTOPICS_PENDING` when loaded, else from `PTOPICS`) · «أفكار» (`ideas`) · «من الخبراء» (`incoming`) · «يُكتب» (`working`, includes `S.generating`) · «على اللوحة» (`board`) · «مرفوضة» (`rejected`, shown only when >0 or active). Chip = `v2OpenSection('content','topics',{replace:true,st:{topicsTab:x}})`. On mobile the chips wrap in a 3×2 grid (44px).
- Second filter «التخصص»: a `<select>` built from the categories present in the active list + `analysis.by_category` (old `topicCatChips` sources), default «كل التخصصات». State in `S.cat`.
- Brain line per chip (facts only):
  - `pending`: «{n} موضوعًا كتبه أعضاء، وهو مخفي عن اللوحة حتى تقرّر. القرار يصل إلى صاحبه.»
  - `ideas`: «{n} فكرة. الاعتماد يضعها على اللوحة العامة، والرفض يحذفها.»
  - `board`: from `v2ContentSegments`: «أقل الفئات موضوعات: {label} ({n}).» (only when the analysis loaded).
  - others: none.
- «موضوع جديد» (primary) → sheet: «العنوان» · «السؤال» · «التخصص» · «المصدر» (`human` «كتبه الفريق», `idea` «فكرة», `expert` «من خبير», `news` «من خبر») — lead «يكتب النظام إجابة مقترحة كمسودة، ولا يُنشر شيء قبل اعتمادك.» → `EP.createTopic(g, cb)` (same payload).
- Topic cards: title; pills: source, category, segment («الفئة: {label}» + « · اختيار آلي» when `segment_auto`, or «بلا فئة»), «له مقال» (green) when `linked_article_id`; meta line: country · «{n} تعليق معتمد» (board only) · date. Actions per chip (same functions as `topRowActions`, renamed):

| Chip | Main button | Others (in a «…» menu on mobile, inline on desktop) |
|---|---|---|
| `pending` | «اعتمد وبلّغ» → confirm → `EP.decidePendingTopic(t,'approve')` | «ارفض» → confirm «لن يظهر على اللوحة، ويبقى محفوظًا بلا حذف.» → `decidePendingTopic(t,'reject')`; segment select |
| `ideas` | «اعتمد للنقاش» → confirm «سيظهر على اللوحة العامة.» → `EP.updateTopic(id,{title,status:'open'})` | «ارفض واحذف» → confirm «سيُحذف الموضوع نهائيًا.» → `EP.deleteTopic`; segment select |
| `incoming` | «اعتمد للنقاش» (same) | «حوّله للكتابة» → `EP.updateTopic(id,{title,status:'merged'})`; «احذف» |
| `working` | «انشر على اللوحة» → confirm → `EP.publishTopic` | «اكتب منه مقالًا» / «افتح المقال»; «احذف» |
| `board` | «اكتب منه مقالًا» (or «افتح المقال» when linked) | segment select; «احذف» |
| `rejected` | «اعتمد بعد المراجعة» → `EP.decidePendingTopic(t,'approve')` | «احذف نهائيًا» → `EP.deleteTopic` |

Segment select = the old `tpSegSelect` behaviour: options only from `PTOPIC_SEGMENTS` (`GET /api/platform-topic-segments`), disabled with «…جارٍ تحميل الفئات» until loaded, saves on change via `EP.setTopicSegment(t, id, cb)`; label «الفئة المستهدفة». Never a local list.

### 4.2 Topic sheet (tap a card)
- Member topic (`pending`): read only (the old `topPendingModal` rule). Title, «السؤال أو النص», «التخصص», «الفئة المستهدفة» (select), note «صاحب الموضوع محفوظ على المنصة ولا يظهر على اللوحة.» Buttons «اعتمد وانشر وبلّغ صاحبه» / «ارفض بلا حذف» / «إغلاق».
- Other topics: the old `topReviewModal` fields, renamed: «العنوان», «التخصص», «المصدر», «الفئة المستهدفة (تُحفظ فور الاختيار)», «الحالة» (`draft` «مسودة», `open` «على اللوحة», `merged` «يُكتب», `published` «منشور»), «السؤال», «الإجابة المقترحة» (`ai_answer`, placeholder «لم تُكتب إجابة مقترحة بعد»), «النص المدموج» (`merged_article`, only if present). Buttons: «احفظ التعديلات» → `EP.updateTopic(id, g)` (same keys) · «انشر على اللوحة» (not when published) · «اكتب منه مقالًا» / «افتح المقال» (+ «اكتب مقالًا آخر» when linked) · «احذف».
- «اكتب منه مقالًا»: confirm «يكتب النظام مقالًا جديدًا مبنيًا على هذا الموضوع، ولا ينسخ نصه. يظهر مسودة في «المقالات» لتقرأها ثم تنشرها.» (linked: «لهذا الموضوع مقال بالفعل. تكتب مقالًا آخر؟») → sequence identical to `topMakeArticle`: `S.generating[id]=Date.now()` → `EP.generateArticleFromTopic(t, (ok,newId,msg)=>…)` → on ok `EP.markTopicArticled(t,newId,…)` then open «المقالات» with the new draft's reader (`S.openArticle=newId`); on failure the error sheet «تعذّر كتابة المقال» + «لم يُنشأ أي مقال، والموضوع بقي كما هو.» + the platform message (Arabic digits) + «أعد المحاولة» / «إغلاق». No technical hint text.
- «افتح المقال» → «المقالات» tab with the linked article's reader open (or the strip «المقال المرتبط لم يعد موجودًا» when not found).

### 4.3 «أرقام الموضوعات» (bottom card, replaces «لوحة تحليل AI»)
Source `platformTopicsAnalysis` (`GET /api/platform-topics-analysis`, no paid call). Shows: «موضوعات» `total_topics` · «تعليقات معتمدة» `total_comments`; «الأكثر تعليقًا» (top 5: title, source pill, «{n} تعليق»); «حسب الفئة المستهدفة» bars from `by_segment` (locked order, zeros shown — new, the old panel never showed it); «حسب التخصص» bars from `by_category` (top 8); «ما يسأل عنه الناس في المحادثة» chips from `categories_in_demand` (`{category} · {count}`). `engagement_note` is never shown. Failed → «أرقام الموضوعات: غير متاح بعد» + retry. Button «حدّث» → `EP.reload('platformTopicsAnalysis')`.

## 5) Tabs «الأخبار», «التعليقات», «دليل الاستخدام»

### 5.1 «الأخبار» (`news`)
- Chips «مسودات ({n})» · «منشورة ({m})» · «الكل». Toolbar «خبر جديد» (primary) · «مصادر الأخبار».
- Card: title; pills «خبر», specialty; summary (2 lines, «بلا ملخص بعد» when empty); sources as links (`target=_blank rel=noopener`, max width, ellipsis) or «بلا مصدر»; country · date; status pill «مسودة»/«منشور».
- Buttons: draft → «انشر» (confirm «سيظهر الخبر للأعضاء على المنصة.») → `EP.updateNews(id,{title,is_published:true})`; published → «أوقف النشر» → `EP.updateNews(id,{title,is_published:false})`; «حوّله لموضوع» → confirm «يصبح الخبر موضوع نقاش على اللوحة.» → `EP.deriveTopicFromNews(t, (topic,newId)=>…)` then open «الموضوعات» on the chip of the new topic (from the reloaded `PTOPICS`, old `topicGotoNew` rule) with the card highlighted once; «عدّل» → sheet; «احذف» → confirm → `EP.deleteNews`.
- News sheet = old `nwsModal` fields and parsing, relabelled: «العنوان» · «الملخص (بصوت البروفيسور، ويظهر للأعضاء)» · «الدولة» · «التخصص» · «روابط المصادر (سطر لكل مصدر: الرابط | الاسم)» (ltr) · checkbox «منشور (ظاهر للأعضاء)» → `EP.createNews(g)` / `EP.updateNews(id,g)`.
- Sources sheet = old `nwsSourcesModal`, relabelled: «مصادر الأخبار (سطر لكل مصدر: الدولة | الرابط)» and «كلمات التصنيف (سطر لكل مجموعة: الاسم : كلمة، كلمة)» → `EP.saveNewsSources({feeds, club_keywords})` (same shape).

### 5.2 «التعليقات» (`comments`)
Three cards stacked:
1. «تنتظر قرارك» (`POPINIONS`): body text, «على: {topic_title}», author email (ltr, person link), date, verdict line (`v2ContentCommentVerdict`), and when the founder opens «لماذا؟» the platform's `moderation.reason` labelled «سبب الفحص الآلي» (never on the ticket face). Buttons: the suggested one as main («اعتمد» or «ارفض»), the other secondary, «احذف نهائيًا» (confirm «يُحذف التعليق من المنصة نهائيًا.»). Functions: `EP.approveOpinion`, `EP.rejectOpinion`, `EP.deleteOpinion`. Empty: «لا تعليقات تنتظر قرارك. التعليق المطابق للموضوع يُعتمد تلقائيًا، والمشكوك فيه فقط يصل هنا.»
2. «ظاهرة الآن» (`POPINIONS_APPROVED`): body, topic, author, date, the editor reply box when present («ردّ {editor_reply_by|هيئة التحرير}»). Buttons: «ردّ» / «عدّل الرد» → sheet with textarea («اكتب ردّ هيئة التحرير») → `EP.replyOpinion(o,{reply})`; «ردّ آلي» (only when no reply) → confirm «يكتب النظام ردًّا ويظهر تحت التعليق باسم هيئة التحرير مباشرة.» → `EP.replyOpinion(o,{ai:true})`; «احذف» → confirm → `EP.deleteOpinion`. (The old prompt()/confirm() dialogs are replaced by sheets.)
3. «أرقام التعليقات»: own source `GET /api/platform-opinions-analysis?summarize=false` → «تنتظر» `status_counts.pending` · «معتمدة» `approved` · «مرفوضة» `rejected`; «الأكثر تعليقًا» (top 5); «حسب التخصص» bars. Button «اكتب خلاصة» → one call `GET /api/platform-opinions-analysis?summarize=true` → shows `insights` under the heading «خلاصة مكتوبة آليًا من آخر التعليقات المعتمدة», or `insights_note` when empty. The summary is kept in `S` for the session (no second paid call on redraw).

### 5.3 «دليل الاستخدام» (`tutorials`)
- Toolbar «قسم جديد». Grouped by `section` (group heading; «بلا تصنيف» for empty), ordered by `order`.
- Card: title, «ترتيب {order}», «فيديو» pill when `video_url`, status pill «منشور»/«مسودة». Buttons: «عدّل» (sheet) · quick «أخفِ» / «انشر» → `EP.updateTutorial(id,{title,is_published:!x})` · «احذف» → confirm «يُحذف هذا القسم من الدليل.» → `EP.deleteTutorial`.
- Sheet = old `tutModal` fields: «العنوان» · «القسم» · «الترتيب» · «النص (يظهر للأعضاء)» · «رابط الفيديو (اختياري، يوتيوب)» (ltr) · checkbox «منشور (ظاهر للأعضاء)» → `EP.createTutorial(g)` / `EP.updateTutorial(id,g)` (same keys: title, section, order, body, video_url, is_published).
- Facts line at top: «{p} قسمًا منشورًا · {d} مسودة · {v} بفيديو». Failed → «دليل الاستخدام: غير متاح بعد» + retry.

## 6) Shared pieces inside the section

### 6.1 Confirmation sheet (publishing and deleting always ask)
`confirmSheet({title, lead, okLabel, danger, run})` built on `window.openModal` like D3 `openSheet`: lead paragraph, buttons «{okLabel}» (primary, or danger red for deletes) and «رجوع». On press: busy text «جارٍ التنفيذ…», both buttons disabled, `#epModal` marked busy (no close on scrim), then `run(done)`. Because the EP action functions call their callback on success **and** failure (they toast the error themselves), `run` verifies the outcome from the reloaded data (e.g. the article is now `published`; the pending topic is gone from `PTOPICS_PENDING`) and the section shows a note strip «تمّ: {what}» (12 s, D3 `setNote`) or keeps the sheet open with «لم يتم. {platform message}». No money actions exist in this section, so the money sheet (`V2.openMoney`) is not used.

### 6.2 Person links
Any email shown (member topic author when present, comment author, creative creator, testimonial author) links to `#s/people/person/<key>` with `L.sectionHash('people','person',email)` (D2 pattern).

### 6.3 Visible copy rules
Plain standard Arabic, gender-neutral («صاحب الموضوع», «كاتبه»), Arabic digits via `L.util.ar`, no «يقوّم», no headline starting with «الذكاء», no English words, no domains in headings (domains only in links and ltr fields). The automatic writing is called «النظام» / «الكتابة الآلية», the platform's moderation «الفحص الآلي على المنصة».

### 6.4 Creative work sheet
Title, kind label, creator, `body` (pre-wrap, max 40vh), `media_url` link «افتح الرابط», cover image when `cover_url`. Buttons «اعتمد وانشر» → confirm → `EP.decideInboxItem({apiKind:'creative', apiId:id}, 'approve', cb, '')` (returns a Promise `{ok,error}`, used for the inline result) · «ارفض» → sheet with required reason («اكتب سبب الرفض، ويصل إلى صاحب العمل») → `decideInboxItem(…, 'reject', cb, reason)`.

### 6.5 Testimonial sheet
Course title, name, rating stars (text «{r} من ٥»), text. «اعتمد» → confirm «سيظهر الرأي باسم كاتبه على صفحة الدورة.» → `POST /api/v2/testimonials/<id>/approve` `{confirmed:true}`. «ارفض» → `POST /api/v2/testimonials/<id>/reject` (no reason field exists on the platform).

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
2. **`index.html`** script/link block (allowed).
3. **`backend/app.py`** one registration line + marker (allowed).
4. **`backend/tests/test_v2_d1b.py`** — update only the `'content'` expectation to the six tabs above (all `mod 'topics'`), the total tab count (+4 for this section), and the case `('topics', {'topicsTab': 'news'}, 'content', 'topics')` → `'content', 'news'`.
5. Not edited, recommended to the «اللوحة» section: let the content tile open `openSection('content')` (the pipeline) like files/disputes/money/books do in `v2-home.js` `openTile`. Without it the tile still lands correctly on «الموضوعات › أفكار» through `topics_drafts`.
6. Possible overlap: testimonials are course testimonials. If the courses section also adds a testimonials proxy, keep one (this spec's `/api/v2/testimonials`) and show it in both places.

## 9) Coverage (old → new), so nothing needs «كل السجلات»
| Old | New |
|---|---|
| tabbar with 9–10 tabs | 6 section tabs + chips |
| مقترحة من الأعضاء / أفكار / واردة / قيد العمل / المنشورة / مرفوضة | «الموضوعات» chips + pipeline columns |
| فلتر الفئة (chips) | «التخصص» select |
| tpSegSelect / tpSegBadge | same behaviour in cards and sheets |
| topCreateModal / topReviewModal / topPendingModal / topMakeArticle / topArticleError / topOpenArticle / topicGotoNew | §4.1–4.2 |
| لوحة تحليل AI | «أرقام الموضوعات» (+ lanes) |
| viewContent + drawContent + createArticleModal | «المقالات › على الموقع» + reader/editor |
| blogTopicsModal | «موضوعات المدوّنة» sheet |
| ولّد بالذكاء / جلب | «اكتب مقالات الآن» / «اسحب الجاهز من المنصة» |
| publishSchedulePanel (hardcoded) | dropped (not a source); see P1 |
| viewArticlesAuto + artDetailModal | «المقالات › على المنصة» |
| viewNews / nwsModal / nwsSourcesModal | «الأخبار» |
| viewComments (3 panels) | «التعليقات» (3 cards; summary only on demand) |
| viewTutorials / tutModal | «دليل الاستخدام» |
| creative rows in the old inbox | pipeline `wait` + creative sheet (the inbox keeps its rows too) |
| testimonials (count only) | pipeline `wait` + testimonial sheet |

## 10) Tests — `backend/tests/test_v2s_content.py` (new)
Node (pure, via the same `_node` helper style as `test_v2_d3.py`):
1. `SECTIONS` content entry exactly as §1.1; every tab recognises itself via `sectionFor('topics', tab.st)`; every legacy `topicsTab` value (`pending ideas incoming working board rejected news articles blog auto comments tutorials pipeline`) lands on the right tab; `routeFor('#topics')` → `content/topics`; `routeFor('#tutorials')` and `sectionFor('tutorials')` → `content/tutorials`; `v2ContentTabFor` mapping incl. unknown → `pipeline`.
2. `v2ContentBoard` places each kind in its column (fixture with one of each, incl. `archived`, published news, published platform article, `open` topic → excluded); ordering in `wait` (member topics oldest first, then testimonials, comments, works); `done` keeps only `published_at` within 7×24 h; today/week counts against a fixed `now`.
3. Failed source ⇒ `partial[col]` and «{n}+»; all sources of a column failed ⇒ count `null` (renders «غير متاح بعد»), never 0; loading ⇒ `undefined` handled; testimonials fallback card from `opsQueue.testimonials_pending`.
4. `v2ContentFacts`: words, image, meta, reviewer, `dupTitle` by trimmed equality only (a title that merely contains another is **not** a duplicate); stale platform draft rule.
5. `v2ContentCommentVerdict` + `v2ContentSuggest` for every kind (labels exactly as §2.3).
6. `v2ContentPrerender` for `ok/error/skipped/never-run/running/missing`.
7. `v2ContentTopicChips` counts equal the old `topicTabOf` split on the same fixture; `rejected` chip hidden at 0 unless active; `v2ContentSegments` keeps zero lanes in order and reports the gap.
8. Copy guard over `v2s/content.js` + the `v2s:content` block: no «يقوّم», no `AI`, no «SEO», no «DEEPSEEK», no «الوكيل الذكي», no visible string starting with «الذكاء»; every Arabic string in §2–§6 present verbatim.
9. Static: `content.js` writes only through `EP.decidePendingTopic, setTopicSegment, updateTopic, deleteTopic, publishTopic, createTopic, generateArticleFromTopic, markTopicArticled, createArticle, updateArticle, publishArticle, unpublishArticle, rejectArticle, syncContent, runDailyContent, blogTopics, saveBlogTopic, publishArticleP, unpublishArticleP, deleteArticleP, createNews, updateNews, deleteNews, deriveTopicFromNews, saveNewsSources, approveOpinion, rejectOpinion, deleteOpinion, replyOpinion, createTutorial, updateTutorial, deleteTutorial, decideInboxItem` and `EP.api` POST only to `/v2/testimonials/`; it never calls `EP.ensure('platformOpinionsAnalysis')` and every `/platform-opinions-analysis` URL in it carries `summarize=false` except the one behind «اكتب خلاصة»; no reference to `prerender`.
Server (pytest, Flask test client, `requests` monkeypatched, zero network):
10. `/api/v2/content/overview`: 401 anonymous, 403 employee, 200 admin, `Cache-Control: no-store`; no `body`/`meta_description` keys; `words` right for `## ` headings; excerpt-only article ⇒ `has_meta: false`; `prerender` maps `_prerender_last` and never contains `reason`/`error`; `_prerender_running=True` ⇒ `running`; no outgoing request.
11. `/api/v2/testimonials`: admin only; status passthrough and fallback to `pending`; approve without `confirmed` ⇒ 400 and no proxy call; approve with it ⇒ proxied to `/api/bridge/testimonials/<id>/approve` and audited; reject proxied; bad action/id ⇒ 400; platform 403 ⇒ 502.
12. CMS contract regression: `POST /api/content/articles/<id>/publish`, `PUT` of a published article, `DELETE` of a published article each call the monkeypatched `_prerender_push_async` with the same reason strings as today (`article-publish:<id>`, `article-update:<id>`, `article-delete:<id>`); a draft delete does not; the key set of `serialize_article` is unchanged; `backend/prerender.py` has no diff against the branch base (`git diff --quiet dash-v2-d3 -- backend/prerender.py`).
Run the old suite file by file as before; port-binding UI tests are rerun by the main session outside the sandbox.

## 11) Shots — `backend/tests/uiharness/v2_shots_content.py` (new; imports helpers from `v2_shots.py`, does not edit it)
Fixtures in a new `backend/tests/uiharness/content_fixtures.py` on top of `v2_fixtures.V2Platform`: bridge topics (every status/source, segments, linked article), pending topics, segments `[{id,label,count}]`, topics analysis (with `by_segment` zeros), opinions pending (one abusive, one off-topic, one open) and approved (one with reply), opinions analysis (asserts `summarize=false` unless the summary shot), news (draft with/without sources, published), news sources, platform articles (draft, stale duplicate, published), tutorials (2 sections, one with video, one draft), creative (song with link, poem), testimonials (two, one without rating); local SQLite seeded with site articles (draft complete, draft without meta/image, draft duplicating a published title, 3 published in the last 7 days with one today, one older). `_prerender_push_async` stubbed; `_prerender_last` set to `ok` (and `error` for one shot). Every platform write is recorded; no real origin is reachable.
Saved to `docs/v2/final/shots-content/` at desktop 1440×900 (`d-`), tablet 820×1180 (`t-`), mobile 390×844 (`m-`):
1. `pipeline` full (all four columns filled) — d/t/m, plus mobile on each of the 4 segments.
2. `pipeline-down` with `platformOpinions`, `creative` and `overview` failing (strip + «+» counts + «غير متاح بعد» pill).
3. `confirm-member-topic` (approve sheet) and `confirm-comment-reject`.
4. `articles-site` list, `article-read` (draft), `article-edit`, `article-publish-confirm`, `article-published-note`.
5. `articles-platform` with the duplicate badge and brain line; `blog-topics` sheet; `write-now` confirm.
6. `topics-pending`, `topics-ideas`, `topics-board` (segment select), `topic-sheet`, `make-article-confirm`, `make-article-failed` (generate route forced 503), `topics-numbers`.
7. `news` list, `news-edit`, `news-sources`.
8. `comments` (three cards, no summary), `comments-summary` (after «اكتب خلاصة»), `reply-sheet`.
9. `tutorials` list and `tutorial-edit`.
10. `empty` (all sources empty) and `old-links` (`#topics`, `#tutorials`, `#s/content/topics` land on the new tabs; no `#topicsTabs` / `.tabbar` / `.kpis` / `.inboxwrap` in `#view`).
The script fails on: horizontal page scroll at 390; a visible target under 44px, or a `.v2ct` main button / sheet button under 52px on mobile; «undefined/NaN/null/[object Object]» visible; «٠»/«0» shown in a slot whose source failed; any request to a non-fixture origin; any write that happened without its confirm sheet; any call to `/platform-opinions-analysis` without `summarize=false` outside shot 8b; any call to `/platform-articles/daily-run` or `generate-article` outside shots 5/6 (the fixture answers them; nothing real is reached).
Also rerun `v2_shots.py d1b` to prove the shell still renders the section header with six tabs.

## Platform needs
Only one, and the section works without it (the line is simply not shown, never «٠»):
- **P1. Read-only content health for the brain line «الكتابة الآلية اليوم».** Today the only source is `POST /api/bridge/content/health-check`, which is not usable from a screen: it can send a Telegram alert and it queries the DeepSeek balance. Needed:
  `GET /api/bridge/content/health` (header `X-ELP-Metrics-Secret`; no side effects: no Telegram, no balance call, no generation) →
  ```json
  {"date": "2026-10-30", "articles_today": 3, "expected_today": 5,
   "last_run": {"at": "ISO", "ok": true, "articles": 3, "topics": 2} ,
   "empty_runs": [{"track": "news|segment|feature|topic", "reason": "bank_empty|generation_failed|duplicate"}],
   "bank_runway_days": 12}
  ```
  (`last_run` may be `null`; `expected_today` may be `null` when no schedule is configured.) The dashboard would proxy it as `GET /api/v2/content/health` (admin, no-store) and the pipeline top bar would add the pill «الكتابة الآلية اليوم: {articles_today} من {expected_today}» and, on an empty run, the brain line «مسار {track} لم يكتب شيئًا اليوم: {plain reason}». Not built in this round.
