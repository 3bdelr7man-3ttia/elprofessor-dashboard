# Brain round 2, part B: keys, Telegram, file review, email, MCP, website

**Founder, 2026-10-31 (verbatim):**

> «تعمل خانة في العقل ان احنا ممكن نزود API لأي موديل اخر … ديب سيك لو GLM اي موديل» · «يقدر يسألنا كمان على التليجرام» · «يراجع الملفات ويبعت ايميلات» · «MCP جاهز يتربط ما بين اي سيستم تاني … التسويق للمبيعات» · «جزء للويب سايت … يفكر القرارات اللي اتخذت واللي عايز تعدل في الويب سايت ونعدله من خلال الداشبورد» · «هو يدير لنفسه وبذاته، ونقدر ندير من خلاله، مع امكانية تغيير اي موديل في اي وقت».

**Base:** part A (SPEC.md). Part B starts after the P1 engine is merged. It uses the same contract (`brain2/contract.py`), the same `v2_brain_items` table, and the same rules: the actor comes from the token, every write needs `confirmed:true`, and there are no retries.

**Testing:** zero real calls in every test and build step. The main session does the live check itself, with the founder's key and a hard cap.

---

## Facts from scouting (binding)

**Keys and models**
- Keys are read from env only (`app.py` `ai_call` ~7450).
- Base URLs are hard-coded for openai and deepseek.
- There is no encrypted storage.
- `GET /api/settings` returns every key to admins. So API keys must never go into the `settings` table.

**Telegram**
- The bot lives on the platform: `services/telegram_service.py`.
- The webhook is on the platform: `POST /api/telegram/webhook` (`routes/telegram_webhook.py:433`), with its `_HANDLERS` map, `ops_links.callback_data/parse_callback_data`, and `answer_callback_query` / `edit_message_text`.
- Telegram allows one webhook per bot. So the dashboard cannot get callbacks directly; the platform must forward them.

**Email**
- The platform sends through Brevo (`services/email_service.send_email(to_email, to_name, subject, html_content)`).
- No bridge sends free-form email.
- The platform member reply (`POST /api/bridge/messages/{id}/reply`) sends an in-app notification only.
- The dashboard's site-message reply is a stub.

**Expert files**
- Detail: `GET /api/bridge/expert-files/{id}`. It returns `facts`, `questions`, `opinion`, `pending_opinion` and `review`.
- The dashboard's `_EF_DETAIL_KEYS` (`app.py:3196`) drops `facts` and `questions`.
- Review: `POST /api/platform-expert-files/<id>/review {action: approve|return, note, confirmed}`. Approving delivers the opinion to the client.

**MCP**
- There is none in the dashboard or the platform.
- Flask 3.0 with sync gunicorn, no streaming.
- Madar has an MCP server at `/api/mcp`: bearer token, read-only tools `jobs_health, access_grants_status, kpis_get, metrics_get, alerts_list`, minted with `python -m app.mcp.mint`.

**Website (`~/elprofessor-site`)**
- Static HTML pages:
  - `Company-Site.html` (the home page);
  - `contact`, `founders`, `platform`, `pricing`, `training`, `privacy`, `terms`, `404`;
  - `haq-masr/*`.
- Only the blog is fed from the dashboard (articles feed + prerender over SFTP, using the `PRERENDER_SSH_*` env vars).
- Every other page is deployed by hand.
- The repo is behind the live server. Never deploy from the repo; edit the live file only.

---

## B1: «المفاتيح والكاتب» (any model, switchable at any time)

**Backend.** New module `backend/brain2/keys.py`, plus routes in `v2_brain2_routes.py`.

**Table `v2_brain_keys`**

| Column | Type / values |
|---|---|
| `id` | |
| `label` | String(60) |
| `kind` | `anthropic` \| `openai_compat` |
| `base_url` | String(200). Required for `openai_compat`, https only. |
| `model` | String(80) |
| `key_enc` | Text |
| `key_tail` | String(4) |
| `role` | `main` \| `backup` \| `off` |
| `created_at`, `created_by` | |
| `last_test_at`, `last_test_ok`, `last_test_error` | |

**Encryption.**
- AES-GCM via `cryptography`. Add `cryptography` to `backend/requirements.txt`.
- Key: HKDF-SHA256 over `DASH_KEYS_SECRET` when it is set, otherwise over `SECRET_KEY`, with info `b"brain-keys-v1"`.
- Store a version prefix so rotation stays possible later.
- If decryption fails, that key is treated as missing and the screen says «تعذّرت قراءة هذا المفتاح؛ أضِفه من جديد».
- Plaintext never leaves the server. Responses show only `key_tail` («ينتهي بـ ••••abcd»).

**Presets.** The browser gets labels only; the URLs live on the server.

| Preset | kind | Base URL | Default model |
|---|---|---|---|
| Claude | `anthropic` | — | `claude-sonnet-5-5` |
| DeepSeek | `openai_compat` | `https://api.deepseek.com/v1` | `deepseek-v4-flash` |
| GLM | `openai_compat` | `https://api.z.ai/api/paas/v4` | `glm-4.6` |
| OpenAI | `openai_compat` | `https://api.openai.com/v1` | `gpt-4.1-mini` |
| OpenRouter | `openai_compat` | `https://openrouter.ai/api/v1` | — |
| «أخرى» | `openai_compat` | founder's https URL | founder's model |

The model name stays editable for every preset.

**`ai_call` resolution order** (only the provider and key selection changes; caps, `max_tokens` and errors stay the same):
1. The database key with role `main`.
2. Then the one with role `backup`, but only when the main call raised `AIUnavailable` of kind `error` or `empty`. That means one fallback per call, not a retry loop. It is logged.
3. Then the current env behaviour, unchanged.

The 8000 `max_tokens` stays.

**Routes**

| Route | Behaviour |
|---|---|
| `GET /api/v2/brain/keys` | Returns rows with no `key_enc`, plus `presets` (label, needs_url). |
| `POST /api/v2/brain/keys` | Body `{preset, label?, base_url?, model, key, role, confirmed}`. Validates https and length, then stores. Audit `brain.key_add` with meta {preset, tail}. |
| `PUT /api/v2/brain/keys/<id>` | Body `{role?, model?, label?, confirmed}`. Setting `role=main` demotes the current main to `backup`. |
| `DELETE /api/v2/brain/keys/<id>` | Body `{confirmed}`. |
| `POST /api/v2/brain/keys/<id>/test` | One tiny call («أجب بكلمة: تم»), `max_tokens` 8000 untouched, counts in the daily cap. Stores the result. Errors are shown in plain Arabic with no provider jargon: «المفتاح غير صحيح» / «الموديل غير موجود» / «لم يصل رد». |

**UI.** A new card in the brain's helpers tab, «المفاتيح والكاتب», placed above the discs:
- Rows: label + «ينتهي بـ ••••abcd» + role chip («الأساسي» / «الاحتياطي» / «موقوف») + «جرّبه» + «احذفه».
- The «أضف مفتاحًا» sheet has:
  - a preset picker that always includes «أخرى» (founder rule);
  - a model field;
  - a URL field, only for «أخرى» / OpenRouter;
  - a key field (`type=password`, never echoed);
  - role buttons.
- After saving, the field is cleared from the DOM.
- The «من يكتب الآن» disc shows the active label, for example «Claude (الأساسي)». This is a founder-facing label, so the provider name is allowed here.

**Tests**
- Encryption round-trip, and a wrong secret yields «missing».
- No route ever returns `key_enc` or plaintext.
- `ai_call` order: database main → backup on error → env.
- The test call is counted in the cap.
- All of it with a fake transport.

---

## B2: Asking on Telegram (platform + dashboard)

**Platform.** New branch `brain-tg` from `origin/main@29f1fa6`. No other platform file changes.

**`POST /api/bridge/brain/ask`** (metrics-secret, same auth as the other bridges)
- Body `{item_id, title ≤120, text ≤900, buttons:[{label, action: 'approve'|'reject'|'open'}] ≤3, open_url}`.
- It sends to the admin chat with `send_ops_checked`. Callback buttons carry `ops_links.callback_data('brain', item_id + ':' + action)`, and «افتح في اللوحة» is a URL button.
- Returns `{sent: bool}`.
- It is idempotent per (`item_id`, action set) using a small `brain_asks` collection, so the same item is never sent twice.

**New `_HANDLERS['brain']`.** Add `'brain'` to `CALLBACK_ACTIONS` (the import-time assert must still pass). The handler:
1. Calls the dashboard `POST {DASHBOARD_URL}/api/v2/brain/telegram-decide` with the `X-ELP-Metrics-Secret` header and body `{item_id, action, tg_user_id}`.
2. On `ok`, edits the message to «✔︎ اعتُمد» / «رُفض» plus the result line from the dashboard. On failure, edits it to «تعذّر التنفيذ، افتحه من اللوحة».

**Dashboard URL.** `DASHBOARD_URL` is a new optional env var with default `https://dashboard.elprofessor.net`; it is not a secret. If the existing webhook locks (secret header, admin chat and user ids) are not armed, `receiver_armed()` is false. The buttons then degrade to the link only, which is existing behaviour.

**Dashboard: `POST /api/v2/brain/telegram-decide`**
- Metrics secret only, no JWT.
- Actor = `telegram:<tg_user_id>`.
- `approve` runs the same apply as the approve route, with no edit.
- `reject` rejects the item.
- `open` does nothing.
- An item that is not `proposed` returns `{ok:false, reason:'decided'}`.

**Money items can never be approved from Telegram:**
- A producer flag `telegram_ok=False` means the item gets only the «افتح في اللوحة» button.
- Opinions are never sent to Telegram.

**Engine hook.** When a new `proposed` item is stored and the producer's switch is not `off`, queue one ask (in the worker thread).

**Per-producer setting «اسألني على تليجرام»** (on/off), stored in `v2_brain_switches.telegram`:
- default on for `reply_draft`, `file_review` and `course_review`;
- off for the others.

Daily cap `DASH_BRAIN_TG_CAP=20`.

**Founder deploy note.** Telegram buttons work only when the platform webhook is armed (`TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_ADMIN_USER_IDS`). Otherwise the message arrives with the link only.

---

## B3: File review notes (`file_review` producer, `producers_files.py`)

**What it reviews.** Files in `in_review`, meaning a new expert's first opinions waiting for the founder.

**Gather**
- List: `/api/platform-expert-files?status=in_review`, via the existing proxy helpers.
- Detail per file: a new **server-only** helper `_ef_detail_for_brain(id)` that calls the platform detail and keeps `facts`, `questions`, `pending_opinion` and `title`.
- `_EF_DETAIL_KEYS` and the browser response stay unchanged.
- Client contacts are already scrubbed by the platform. Strip the client's name anyway.

**Output.** Schema `{"text": notes ≤600, "recommend": "approve"|"return", "return_note": "…"}`.
- `return_note` is required when `recommend` is `return`.
- Notes check three things: whether every question was answered, whether the stance follows from the facts, and whether there is a missing next step.

**Settings.** Locked to «يسألني». Lock reason: «يسألك دائمًا لأن الاعتماد يرسل الرأي إلى العميل.»

**Apply.** It goes through the existing review route logic:
- `approve` sends `{action:'approve', confirmed:true}`. Button «اعتمد الرأي وأرسله».
- `return` sends `{action:'return', note: return_note (the founder may edit it), confirmed:true}`. Button «أرجِعه بالملاحظة».

Telegram is allowed (`telegram_ok=True`).

The brain only reviews and recommends. Money is not touched.

---

## B4: Email (platform bridge + dashboard)

**Platform, `brain-tg` branch: `POST /api/bridge/email/send`**
- Body `{to_email, subject ≤120, text ≤4000, by, confirmed:true, idem_key, context:{kind:'message'|'lead'|'user', id}}`.
- `to_email` must belong to one of:
  - an existing user;
  - the sender of the platform message `context.id`;
  - the lead `context.id`.
  Anything else returns 422 «هذا البريد غير معروف لدينا».
- It renders the plain text into the existing branded email shell and calls `send_email`.
- Rate limit: 30/day, plus idempotency by `idem_key`.
- It logs to a `bridge_emails` collection (no body stored beyond 500 characters) and returns `{sent: bool}`.
- Missing `BREVO_API_KEY` returns `{sent:false, reason:'not_configured'}`.

**Dashboard**
- `reply_draft` apply for `smsg` (site contact form) and for `pmsg` without an account becomes «أرسل الرد بالبريد». It calls the bridge.
- If the bridge returns `not_configured` or fails, it falls back to today's copy behaviour, and the sheet says so honestly.
- `pmsg` with an account does both: the in-app reply (existing) and an email.
- Sheet text: «يصل هذا الرد إلى بريد صاحب الرسالة.» Never claim a send unless the result is `sent:true`.
- Leads: «أرسل بالبريد» only when the lead has an email; otherwise copy.

---

## B5: MCP (connect other systems both ways)

### B5a: The dashboard as an MCP server

**Endpoint.** `POST /api/mcp`: hand-written stateless JSON-RPC 2.0 over HTTP, MCP protocol `2025-06-18`, plain JSON responses with no SSE. `GET /api/mcp` returns 405.

**Methods:** `initialize`, `notifications/initialized`, `tools/list`, `tools/call`, `ping`.

**Auth**
- `Authorization: Bearer <token>`.
- Tokens are stored as sha256 in `v2_mcp_tokens` (`id`, `name`, `hash`, `scopes`, `created_by`, `created_at`, `last_used_at`, `revoked_at`).
- A token is minted from the brain screen and shown once.
- Scopes: `read`, `propose`.

**Tools**

| Scope | Tool | Returns / does |
|---|---|---|
| `read` | `business_summary` | Counts per section, from existing summary routes. No customer data. |
| `read` | `decisions_waiting` | Kind, title, age. No names, emails or amounts. |
| `read` | `brain_items` | Items with status and section. |
| `read` | `reports_weekly` | The weekly text and figures. |
| `read` | `content_published` | Article titles and links. |
| `read` | `courses_catalog` | Public course list. |
| `propose` | `propose_note` | `{section, title, text}`: creates a `v2_brain_items` row with producer `mcp:<token name>`, kind `note`, status `proposed`. |
| `propose` | `propose_campaign_idea` | Same, with section `marketing`. |

Nothing in MCP can approve, send, publish or touch money.

**Limits.** 60 calls/hour per token. Each call is audited (`mcp.call`, tool name, token name).

### B5b: The dashboard as an MCP client, «الأنظمة المتصلة»

**Table `v2_brain_links`:** `name`, `url` (https), `token_enc` (same AES-GCM as B1), `enabled`, `last_ok_at`, `last_error`.

**Client.** A minimal JSON-RPC client: `initialize` + `tools/list` + `tools/call`. It reads JSON, or the first `data:` event when the server answers with SSE. Timeout 15s, no retries.

**Producer `links_digest`**
- Kind `note`, may run alone, section `reports`.
- For each enabled link, it calls a fixed allow-list of read tools per known system. For Madar: `kpis_get`, `alerts_list`.
- It passes the JSON as facts and writes «من مدار هذا الأسبوع: …».
- An unknown system shows only its `tools/list` on the screen. No automatic calls.

**UI.** In the helpers tab, «الأنظمة المتصلة»:
- add link: name + URL + token (password field);
- «جرّب الاتصال» runs `initialize` + `tools/list` and shows the tool count;
- the MCP tokens of this dashboard: «أنشئ رمزًا» shows the token once with a copy button, plus «ألغِه»;
- the server address to give to other systems: `https://dashboard.elprofessor.net/api/mcp`.

---

## B6: The website from the dashboard (`producers_site.py` + `backend/site_edit.py`)

**Goal.** The founder controls every page of the marketing site from the dashboard. The brain also proposes edits that follow decisions already made.

**Read side**
- `site_edit.fetch_live(page)` does an HTTPS GET of `https://elprofessor.net/<page>` for the page allow-list (the pages listed in Facts). The home page is `Company-Site.html`.
- It extracts editable text blocks with a strict HTML parser: `h1`–`h3`, `p`, `li`, `a` text, `button` text, `title`, and `meta[name=description]`.
- Each block has a stable path (css path + index) and its text.
- Scripts, styles and attributes are never editable.

**Decisions list.** Table `v2_site_decisions` (`id`, `text` ≤300, `created_by`, `created_at`, `active`).
- Seed it once from a constant list in code. Take that list from the founder's decisions recorded in NOTES/memory that concern public copy, for example:
  - «لا نبدأ أي عنوان بالذكاء الاصطناعي»;
  - «لا كلمة يقوّم»;
  - «تواصل في الفوتر فقط»;
  - «الشهادة باسمنا بلا سطر نفي»;
  - «خصم الطالب ملغى»;
  - «المجتمع دولي، لا مصر فقط»;
  - «نصيب المنصة ٣٥٪ على الأقل» (internal, do not show).
- The builder collects about 10–15 public-copy rules from `_reference/elprofessor-platform-walkthrough/NOTES.md` and memory text quoted in SPEC files. Each one must be cited with its source line in a code comment.
- The founder can add and remove rules from the screen.

**Producer `site_review`**
- Kind `draft`, locked to «يسألني». Lock reason: «يسألك دائمًا لأن التعديل يظهر على الموقع للناس.»
- Per page, per run (cap 2 pages/run): facts = the blocks + the active decisions.
- Output `{"edits":[{"path", "old", "new", "why"}] ≤5, "text": summary}`.
- Every `old` must equal the live block text exactly, or that edit is dropped.

**Founder manual edit.** A «الموقع» tab inside «المحتوى»:
- page picker → list of blocks → «عدّل» on any block → a proposed item, source `founder`, approved by the founder's own approve.
- This is always available, even with the brain off.

**Apply (one page at a time, all or nothing)**
1. SFTP download of the live file into `site_backups` (table: page, sha256, html gz, created_at). Keep the last 20 per page.
2. If the live sha differs from the sha at proposal time, return 409 «تغيّرت الصفحة منذ الاقتراح؛ أعد التوليد».
3. Apply the replacements on text nodes only. Each `old` must match exactly once.
4. Upload to a temp name, then rename.
5. Verify with an HTTPS GET that the new text is present. If it is not, restore the backup and report «لم يظهر التعديل؛ أعدنا الصفحة كما كانت».

**Undo.** «أرجِع الصفحة» restores any of the last 20 backups (confirm sheet).

**Infrastructure.** SFTP reuses the existing `PRERENDER_SSH_*` settings and `PRERENDER_SITE_ROOT`. Never touch `.htaccess`, never upload a non-allow-listed page, and never delete files.

**Tests.** A fake SFTP and a fake HTTPS GET. Cover:
- the exact-match rule;
- the sha 409;
- verify failure restores the backup;
- the allow-list;
- the backup limit.

---

## B7: Courses (later, after the pillars session says «جاهز»)

The `course_lesson_draft` hook (part A) gets the new bridge `/api/bridge/courses2…` plus `brain/draft`. That work is a separate package in branch `dash-courses`.

---

## Work split (after part A is integrated)

| Package | Owns | Branch |
|---|---|---|
| **B1 Keys** | `brain2/keys.py`, the app.py `ai_call` provider-selection lines, `requirements.txt`, the keys routes (new file `v2_brain2_keys_routes.py`, registered next to brain2), the keys card in `v2s/brain.js` (helpers tab), tests | dashboard `b2-k` |
| **B2+B4 Platform** | new `routes/brain_bridge.py` (ask + email send), the `telegram_webhook` `'brain'` handler, `ops_links` `CALLBACK_ACTIONS`, server mount, tests | platform `brain-tg` |
| **B2+B3+B4 Dashboard** | `brain2/producers_files.py`, the `telegram-decide` route, the engine ask hook, `reply_draft` email apply, `_ef_detail_for_brain`, tests | dashboard `b2-tf` |
| **B5 MCP** | `backend/mcp_server.py`, `backend/brain2/links.py`, routes, the «الأنظمة المتصلة» card, tests | dashboard `b2-m` |
| **B6 Website** | `backend/site_edit.py`, `brain2/producers_site.py`, the «الموقع» tab in `v2s/content.js`, tests | dashboard `b2-s` |

**Ordering.** B1 first, because it changes `ai_call` and B5 reuses its encryption. B2, B3, B5 and B6 build in parallel after B1 is merged.

**Copy rules (all packages).** Plain Arabic, gender-neutral, no «يقوّم», never claim a send that did not succeed, «غير متاح بعد» for missing values.
