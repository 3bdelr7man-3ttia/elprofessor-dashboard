# Brain round 2 (العقل يكتب شغله في كل قسم): build spec

**Founder (2026-10-31):** «الجولة التانية بحيث تكون منتجة بنفسها في كل الأقسام».
The founder ordered this round. This spec is final. It was planned by Opus and reviewed by the main session.

- **Paths:** all relative to the worktree root `.worktrees/brain2` (branch `dash-brain2`, from published main `4cf07c3`).
- **Platform:** read-only this round. Only existing bridges are called.
- **Real API calls:** zero. No network and no live LLM calls in any test or build step.

## 0) Binding facts

1. **Site message replies are not emailed.** `POST /api/messages/<id>/reply` (app.py ~11038) only stores `reply_body`; email delivery is a stub. The screen must never say a site reply was sent.
2. **Member messages have a real reply path.** The platform route is `POST /api/bridge/messages/{id}/reply` with body `{body, by, confirmed:true}`. It sends an in-platform notification. For a visitor with no account it returns 422. The dashboard does not proxy this route yet. Leads have only `/resolve`.
3. **Never call the platform agents** `/bridge/agents/vet-trainer` or `/bridge/agents/review-course`. They call DeepSeek on the platform side and skip our cap. Every AI call goes through `ai_call`. We do reuse the deterministic `/api/bridge/courses/{id}/checklist`.
4. **Production runs `gunicorn -w 1 --timeout 120`.** So every brain AI call runs in one background thread, and HTTP routes return immediately.
5. **The env model value wins over the code default.**
   - `docker-compose.yml` sets `ANTHROPIC_MODEL: ${ANTHROPIC_MODEL:-claude-sonnet-4-20250514}`, and `.env.example` has the same line.
   - `DASHBOARD_AI_MODEL` overrides the model for every provider.
6. **SPEC-brain §0 still holds.** Refunds and escrow releases (A3–A7) move money on the platform with nobody asking. The new lock text talks only about what the brain writes. It must never say money waits in general.
7. **Registration is early.** The registration line (app.py ~2698) comes before `ai_call` (~7435). So the engine reads every helper lazily from `ns` at call time.

## 1) Concept

A **producer** turns real data into one AI-written thing. There are three kinds of thing:
- an **opinion** on a decision card;
- a **draft** that would go to a customer or the public;
- an internal **note**.

Producer switches:
- Every producer has a switch with three settings: «وحده» / «يسألني» / «متوقّف».
- Drafts are locked to «يسألني».

Where outputs go:
- All outputs are stored in one table.
- An opinion replaces the static «ما يراه العقل» line. If writing fails, the static line comes back with a visible mark.
- Drafts and «يسألني» notes become decision cards with «اعتمد / عدّل / ارفض». These cards show in the section's brain bar and in «ابدأ القرارات».

Only the founder's approval calls an existing write path.

## 2) Backend

### 2.1 Files
- `backend/brain2/__init__.py`
- `backend/brain2/contract.py` (copied verbatim from §2.2)
- `backend/brain2/registry.py`: `PRODUCERS` is the concatenation of `producers_ops.PRODUCERS` and `producers_biz.PRODUCERS`. Each import is wrapped in try/except ImportError with `logger.exception`.
- `backend/brain2/engine.py`: models, hash, honesty checks, runner, queue, apply.
- `backend/brain2/producers_ops.py`
- `backend/brain2/producers_biz.py`
- `backend/v2_brain2_routes.py`: `register(app, ns)`.

### 2.2 contract.py (verbatim)
```python
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

KINDS = ('opinion', 'draft', 'note')
MODES = ('alone', 'ask', 'off')

class SourceDown(Exception):
    """gather could not read its source: the run records it and stores nothing (never an empty result)."""

@dataclass
class Target:
    ref: str                       # stable id, ≤200, e.g. 'pmsg:MSG_ab12', 'course:<id>', 'card:<v2Card id>'
    label: str                     # title the founder sees, ≤120
    facts: Dict[str, Any]          # the ONLY data the prompt may use; JSON, ≤4KB; hashed
    meta: Dict[str, Any] = field(default_factory=dict)  # apply-only (ids, emails); never sent to AI, never hashed

@dataclass
class ApplyResult:
    ok: bool
    error: str = ''                # Arabic, shown as is
    no_reply: bool = False
    copy_text: str = ''            # browser copies this after success
    info: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Ctx:
    ns: dict                       # app.py globals()
    now: Any                       # aware UTC datetime
    actor: str                     # 'cron' | admin email

@dataclass(frozen=True)
class Producer:
    id: str
    section: str                   # dashboard section key that shows it
    kind: str                      # KINDS
    label: str                     # rules-screen title (Arabic)
    sentence: str                  # «عندما…» sentence (Arabic)
    lock_reason: str               # Arabic; '' when may_run_alone
    may_run_alone: bool
    default_mode: str
    per_run_cap: int
    gather: Callable[[Ctx], List[Target]]
    prompt: Callable[[Target], tuple]                    # -> (system_ar, user_ar)
    validate: Callable[[dict, Target], Optional[dict]]   # -> body {'text': str, ...} | None
    template: Optional[Callable[[Target], Optional[dict]]] = None
    apply: Optional[Callable[[Ctx, dict, Target], ApplyResult]] = None
    tag: str = ''                  # card tag (Arabic)
    approve_label: str = ''        # main button (Arabic)
    listed: bool = True            # False = hidden hook
    version: int = 1
```

### 2.3 Tables
All tables are created inside `engine._models(db)`, using the `_MODEL` cache pattern from `v2_brain_routes.py`.

**`v2_brain_items`**

| Column | Type / note |
|---|---|
| `id` | String(32) uuid hex, primary key |
| `producer` | String(40) |
| `section` | String(20) |
| `kind` | String(10) |
| `target_ref` | String(200) |
| `target_label` | String(200) |
| `input_hash` | String(64), indexed |
| `facts_json` | Text |
| `meta_json` | Text |
| `body_json` | Text |
| `status` | String(12) |
| `source` | String(10): `ai` or `template` |
| `mode` | String(8) |
| `run_id` | String(32) |
| `created_at` | DateTime |
| `decided_at` | DateTime |
| `decided_by` | String(255) |
| `last_error` | String(300) |
| `applied_json` | Text |

- Unique key: (`producer`, `target_ref`, `input_hash`).
- Allowed `status` values: `proposed | done_alone | applying | approved | edited | rejected | discarded | expired | failed | unknown`.

**`v2_brain_switches`**: `producer` String(40) primary key, `mode` String(8), `updated_at`, `updated_by`.

**`v2_brain_runs`**: `id`, `trigger` (`cron` or `admin`), `started_at`, `finished_at`, `ai_calls`, `items`, `skipped_json`, `by`.

### 2.4 Engine rules

**Hash.** `sha256(json.dumps({'p': id, 'v': version, 'f': facts}, sort_keys=True, ensure_ascii=False))`.

**Idempotency.**
- If a row with the same (producer, ref, hash) already exists, do nothing and make no AI call.
- A `failed` row blocks the same hash until the next UTC day.
- When a ref that has a `proposed` row gets a new hash, the old row becomes `expired`.

**Effective mode.**
- The switch row decides; if there is none, `default_mode` applies.
- When `may_run_alone` is False, `alone` is coerced to `ask`. This check runs again at store time, so a tampered database can never send anything.
- `off` means `gather` is not run.

**Failures (no retries).**
- `AIUnavailable` with kind `cap` or `no_key` stops the run.
- Any other failure: if the producer has a template, store the row with `source='template'`. Otherwise store it as `status='failed'` with no card.

**Caps (env, defaults shown).**
- `DASH_BRAIN_RUN_CAP=20`: AI calls per run.
- `DASH_BRAIN_DAY_CAP=60`: brain AI calls per UTC day. It counts rows with `source='ai'` plus failed rows from today.
- `DASH_BRAIN_OPINION_CAP=40`: opinions per day, counted inside the day cap.
- `per_run_cap`: set per producer.
- Reserve: stop before a call when `ai_daily_usage_state()['remaining']` is not None and is below 25. This leaves room for the founder's own buttons and for the helpers.
- `DASH_BRAIN_WRITE=0`: stops all brain writing.

**Parse.** Run `ns['_extract_json_block'](text)`, then `producer.validate`, then these engine checks:
1. `text` is a non-empty string within its limit: opinion 220, why 160, draft 900, note 600.
2. Numbers: map Arabic-Indic digits to Latin. Every digit run in the body must appear in the canonical JSON of `facts`.
3. Every Latin word in the body must appear in `facts`.
4. The body has no «يقوّم», and it does not start with «الذكاء» or «AI».
5. The body has no email or phone pattern unless that value is in `facts`.

A body that fails any check is treated as invalid output and goes through the failure rule.

**Status at store time.**
- Mode `alone` with kind `note` gives `done_alone`.
- Everything else gives `proposed`.
- Opinions are always `done_alone`, because they are text only.

**Thread.**
- `engine.submit(fn)` hands the job to one daemon worker. The queue holds 8 and is deduplicated by hash.
- The worker runs inside `with app.app_context()` and calls `db.session.remove()` at the end.
- `app.config['BRAIN_INLINE']` runs jobs inline; this is for tests.
- When the queue is full, return `{queued:false, reason:'busy'}`.

**Run lock.** If a `v2_brain_runs` row has `finished_at` null and `started_at` less than 15 minutes ago, return 409 «العقل يكتب الآن. جرّب بعد قليل».

**Apply.**
1. A conditional update moves the row from `proposed` to `applying`. If 0 rows change, return 409 «حُسم هذا الاقتراح من قبل».
2. Call `producer.apply`:
   - ok: the row becomes `approved`, or `edited` if the text was changed;
   - `no_reply`: the row becomes `unknown`;
   - error: the row goes back to `proposed` and `last_error` is set.
3. Audit: `_audit('brain.approve', target=id, meta={producer, edited})`.

### 2.5 Routes (`v2_brain2_routes.py`)
All routes:
- are admin-only;
- return `_v2_closed()` when the flag is off;
- send `no-store`;
- take the actor from the token.

| Method and path | Behaviour |
|---|---|
| `GET /api/v2/brain/switches` | Returns the listed producers with `{id, section, kind, label, sentence, lock_reason, may_run_alone, mode, updated_at, updated_by}`, plus `writer` and `brain_today:{used, cap}`. |
| `PUT /api/v2/brain/switches/<id>` | Body `{mode, confirmed:true}`. Unknown id gives 404. `alone` on a locked producer gives 400 «هذا لا يعمل وحده: <lock_reason>». Audit `v2_brain.switch`. |
| `GET /api/v2/brain/items?section=&status=proposed\|all&since=` | Newest first, at most 100. Allow-list: `id, producer, section, kind, target_label, body, status, source, created_at, decided_at, decided_by, tag, approve_label, last_error`. Never returns `meta` or `facts`. |
| `POST /api/v2/brain/items/<id>/approve` | Body `{confirmed:true, text?}`. `text` is the founder's edit: 1–900 characters after cleaning, checked again for banned words. |
| `POST /api/v2/brain/items/<id>/reject` | Body `{confirmed:true}`. The row becomes `rejected`. |
| `POST /api/v2/brain/items/<id>/discard` | Body `{confirmed:true}`. Only a `done_alone` note can be discarded; it becomes `discarded`. This is the real undo. |
| `POST /api/v2/brain/opinion` | Body `{kind, card_id, facts}`. See the rules below this table. |
| `POST /api/v2/brain/opinions/lookup` | Body `{cards:[{kind, card_id, facts}]}`, at most 40 cards. Returns `{items:{card_id: item\|null}}`. Never calls the AI. |
| `POST /api/v2/brain/run` | Body `{confirmed:true, only?}`. Returns 202 `{run_id}` and starts the thread. |
| `GET /api/v2/brain/runs/latest` | The latest run. |
| `POST /api/v2/brain/run-cron` | Accepts only the `X-ELP-Metrics-Secret` header. Same as `/run`, with `trigger='cron'`. |

Rules for `POST /api/v2/brain/opinion`:
- The server cleans `facts`. It keeps only allow-listed keys (§3.2) and limits strings to 300 characters and lists to 6 items. It strips emails and phones.
- Total facts must be 3KB or less; over that returns 400.
- Returns `{item}` when the opinion is already cached.
- Returns `{queued:true}` when a new opinion was submitted.
- Otherwise returns `{item:null, reason}`, where `reason` is one of `off`, `cap`, `no_writer`, `busy`, `not_supported`.

In the existing `/api/ai/agents/run-cron` (app.py ~8527), add one guarded line after the agents: `_v2_brain2_kick('cron')`. It starts the thread without waiting.

### 2.6 Model and key (app.py)
1. Set the Anthropic models:
   - `AI_PROVIDERS['anthropic']['default_model'] = 'claude-sonnet-5-5'`
   - `models = ['claude-sonnet-5-5','claude-opus-5-5','claude-haiku-5-5']`
2. Leave `call_anthropic` as it is: no temperature is sent, and `max_tokens` stays at 8000.
3. Add `claude-sonnet-4-20250514`, `claude-3-5-sonnet-latest` and `claude-3-5-haiku-latest` to `AI_RETIRED_MODELS`.
4. In `ai_model_for`, ignore `DASHBOARD_AI_MODEL` when its prefix (`claude-`, `deepseek-` or `gpt-`) does not match the provider, and log that it was ignored.
5. Set the default in `docker-compose.yml` to `ANTHROPIC_MODEL: ${ANTHROPIC_MODEL:-claude-sonnet-5-5}`. Make the same change in `.env.example`.
6. Add a `writer` field:
   - Value: `'main'` when the Anthropic provider is in use, `'backup'` for any other configured provider, `null` when none is configured.
   - It is returned by `helpers-status` (B3 in `v2_brain_routes.py`) and by `/switches`.
   - The provider name is never shown.

## 3) Producers

### 3.1 Shared preamble (`engine.SYSTEM_AR`)
«اكتب بالعربية الفصحى البسيطة، بصيغة محايدة لا تخاطب مذكرًا ولا مؤنثًا، لجمهور دولي، بلا مصطلحات تقنية. استعمل الحقائق المعطاة وحدها؛ لا تخترع رقمًا ولا اسمًا ولا تاريخًا ولا وعدًا، ولا تقل إن شيئًا نُفِّذ. أعد JSON صالحًا فقط بالشكل المطلوب.»

Each producer adds its schema and a role line after this preamble.

### 3.2 producers_ops.py (P2)

#### A) `opinion`
- section `home`, kind `opinion`, `may_run_alone=True`, `default_mode='alone'`.
- The switch shows only «وحده» / «متوقّف».
- Label: «رأي العقل في كل قرار».
- Sentence: «عندما يظهر قرار ينتظرك، يكتب العقل رأيه فيه من بيانات البطاقة نفسها.»
- It is not run by the runner. It is called by `/opinion`.
- `OPINION_SPECS[kind] = {role_ar, allowed_recommend, keys}`.
- Output schema: `{"opinion":"…","recommend":"<allowed>","why":"…"}`.

Kinds:

| Group | Kinds | `recommend` values |
|---|---|---|
| Money (text only, never remapped) | `payout`, `manual_payment`, `stuck_payment`, `unactivated`, `legacy`, `file_attention`, `dispute` | — |
| Decision | `trainer`, `join`, `pending_user`, `book_offer`, `book`, `creative`, `topic`, `program` | `approve`, `reject`, `open` |
| Info | `review`, `lead`, `message`, `open_message`, `course`, `live`, `verify`, `founding`, `other` | `open`, `wait` |
| Excluded (keep the rule-based expert pick) | `file_waiting`, `file_late` | — |

The role line for `dispute` is «لخّص الطرفين بإنصاف ثم أوصِ».

Allowed fact keys:
- Common to all kinds: `tag, age, sub, warn, reason, static_line, facts, money_text`.
- `dispute`: `objection, expert_reply, hours_held`.
- `trainer`: `headline, specialty, years, attachments`.
- `payout`: `method, dispute_check, fx_alert`.
- `book_offer`: `type, suggested_price, price_note`.
- `join`: `service, licensed, licence_missing`.
- `lead` / `message`: `body, topic`.

Template: `None`. The front end keeps its own static line.

#### B) `reply_draft`
- section `people`, kind `draft`, `may_run_alone=False`, `default_mode='ask'`, `per_run_cap=6`.
- Label: «مسودات الرد على الرسائل».
- Sentence: «عندما تصل رسالة أو طلب تواصل، يكتب العقل مسودة رد تراجعها قبل أن تصل إلى صاحبها.»
- Lock: «يسألك دائمًا لأن الرد يصل إلى صاحب الرسالة.»

Gather sources:

| Source | Ref | Facts / meta |
|---|---|---|
| `_platform_proxy GET /api/bridge/messages?status=new` | `pmsg:<id>` | meta `{id, email}`; facts `{subject, body≤1200, has_account}` |
| local `Message` rows with status `new` | `smsg:<id>` | — |
| `_platform_proxy GET /api/bridge/leads?status=new` | `lead:<id>` | facts `{want, experience}`; the phone goes in meta only |

When a source fails, raise `SourceDown` for that source only.

Output: `{"text":"…"}`, at most 700 characters.

Apply, by source:

| Source | Button | What happens |
|---|---|---|
| `pmsg` with email | «أرسل الرد» | `_platform_proxy POST /api/bridge/messages/<id>/reply {body, by: actor, confirmed: true}`, then audit `brain.reply_send` |
| `pmsg` without an account | «انسخ الرد» | Copy, then resolve |
| `smsg` | «احفظ الرد وانسخه» | Same writes as `admin_message_reply` (`reply_body`, `status='replied'`, `replied_at`), plus `copy_text` |
| `lead` | «انسخ الرسالة وعلّمه تم» | Copy, then `POST /api/bridge/leads/<id>/resolve` |

### 3.3 producers_biz.py (P3)
Every producer here has a per-run cap of 3 unless stated otherwise.

#### `course_review`
- section `courses`, kind `draft`, locked, `default_mode='ask'`.
- Label: «مراجعة الدورة قبل النشر».
- Sentence: «عندما تُقدَّم دورة للنشر، يكتب العقل ما ينقصها ويقترح: انشر أو أصلح أولًا.»
- Lock: «يسألك دائمًا لأن النشر يظهر للناس.»
- Gather:
  1. `_platform_proxy GET /api/bridge/courses`, then keep only courses pending review.
  2. For each one, read `/api/bridge/courses/<id>/checklist`.
- Facts: `{title, type, short_description, lessons, outcomes[:8], level, checklist[{item,ok}]}`.
- Output schema: `{"text","recommend":"publish|fix_first"}`. If any checklist item is not ok, `publish` is downgraded to `fix_first`.
- Template: «ينقصها: <failed items>», or «بنود الفحص كلها مكتملة» when nothing failed.
- Apply:
  - `publish`: use the existing approve logic of `POST /api/v2/courses/<id>/approve` through `_v2_write`, with `confirmed`. Button: «انشر الدورة».
  - `fix_first`: no apply. Main button: «افتح الدورة».

#### `market_match`
- section `market`, kind `draft`, locked, `default_mode='ask'`.
- Label: «ربط طلبات السوق بدورة مناسبة».
- Sentence: «عندما يطلب عضو شيئًا تغطيه دورة لدينا، يقترح العقل ربطه بها.»
- Lock: «يسألك دائمًا لأنه يغيّر بيانات الطلب على المنصة.»
- Gather: open requests with no `linked_course_id`, from `_v2_get('/api/bridge/market/requests', {status:'open', limit:50})`.
- Facts: the request, plus the active course list as `{id, title}` (at most 40).
- Output schema: `{"text","course_id":"<id from list>"|null}`. When `course_id` is null, store the row as `discarded` with no card.
- Apply: `_v2_write('POST','/api/bridge/market/requests/<id>/annotate',{'linked_course_id':id},'market.link_course',…)`. Button: «اربطه بالدورة».

#### `seo_notes`
- section `content`, kind `note`, may run alone, `default_mode='alone'`.
- Label: «ملاحظات الظهور في البحث على المسودات».
- Sentence: «عندما تنتظر مسودة مقال، يكتب العقل ما يحسّن ظهورها في البحث. لا يُنشر شيء.»
- Gather: `_bridge_get('/api/bridge/articles', {'limit':60,'status':'draft'})`, then `_seo_scorecard(a)` for each article.
- Facts: `{title, score, words, issues}`.
- Output: 2–4 lines, joined into `text`.
- Template: the scorecard issues.

#### `campaign_comment`
- section `marketing`, kind `note`, may run alone, `default_mode='alone'`.
- Label: «تعليق على الحملات».
- Sentence: «عندما تتغير أرقام حملة، يكتب العقل تعليقًا قصيرًا عليها.»
- Source: local `Campaign` rows that are active or paused with `spent > 0`.
- Facts: `{name, platform, budget, spent, currency, impressions, clicks, leads, conversions, revenue_attributed}`.

#### `weekly_read`
- section `reports`, kind `note`, may run alone, `default_mode='alone'`, cap 1.
- Label: «قراءة الأسبوع».
- Sentence: «في بداية كل أسبوع، يكتب العقل قراءة قصيرة لأرقام الأسبوع الماضي.»
- Source: `v2_reports_routes.weekly_for(G, None)`, using its text and figures.
- Ref: `week:<start>`.

#### `forecast_comment`
- section `company`, kind `note`, may run alone, `default_mode='alone'`, cap 1.
- Label: «تعليق على التوقعات».
- Sentence: «عندما تتغير التوقعات أو الأرقام الفعلية، يكتب العقل تعليقًا عليها.»
- Source: `ForecastMonth` rows for the current month and the next 2, plus the financials and cashflow from `generate_ai_snapshot()`.

#### `course_lesson_draft` (hook only)
- section `courses`, kind `draft`, `listed=False`, locked.
- `gather = lambda c: []`, `apply = None`.
- Its docstring must say that the later round fills in:
  - `gather`: from the new platform bridge;
  - `validate`: returns `{'text','fields':{'title','body'}}`;
  - `apply`: calls the new bridge with `confirmed:true`.
- The front end renders `body.fields` generically.

#### Not in this round
The investor update draft is deferred, because there is no send path for it yet.

### 3.4 What may run «وحده»
**May run alone:** `opinion`, `seo_notes`, `campaign_comment`, `weekly_read`, `forecast_comment`. These are internal text only.

**Locked to «يسألني»:** `reply_draft`, `course_review`, `market_match`, `course_lesson_draft`. Each of these reaches customers, members or the public, or changes platform data.

No producer touches money. Money cards get opinions only.

## 4) Front end

### 4.1 `dashboard-cloud/v2-logic.js`
Add a new block at the end of the file, between `// ===== brain2 =====` and `// ===== /brain2 =====`. Export the functions as `V2L.v2b*`. All of them are pure.

**`v2bFacts(card)`**
- Returns `{kind, card_id, facts}`, or `null` for excluded kinds.
- Uses allow-listed keys only.
- Replaces the client's name with «صاحب الطلب».
- Strips emails and phones.
- Confirm the field names against `uiharness/ef_fixtures.py` and `v2_rows.js`.

**`v2bDecorate(card, entry, now)`**
- `entry = {state:'none'|'loading'|'ready'|'off'|'cap'|'busy'|'failed', item}`.
- Returns a copy of the card with `brain`, `brainHead`, `src` = `{text, tone}`, and possibly a new `primary` / `secondary`.
- When an AI opinion is ready:
  - `brain` = `opinion`, `reason` = `why`;
  - `src.text` = «كتبه العقل <agoText>».
- One-button remap:
  - applies to non-money kinds only, and only among the card's existing acts;
  - `reject` makes the existing reject act primary;
  - `open` makes the open act primary;
  - `approve` changes nothing.
- When there is no opinion, the static line stays, with one of these marks:
  - failed: «جملة ثابتة: تعذّرت كتابة رأي العقل الآن»
  - cap: «جملة ثابتة: بلغ العقل حدّ كتابته اليوم»
  - off: «جملة ثابتة: رأي العقل متوقّف من القواعد»
  - loading: «يكتب العقل رأيه…»

**`v2bItemCard(item, now)`** builds a decision card:

| Field | Value |
|---|---|
| `kind` | `'brain_item'` |
| `group` | lowest rank |
| `tag` | `item.tag` |
| `title` | `target_label` |
| `brain` | `body.text` |
| `brainHead` | «ما كتبه العقل» |
| `primary` | `{label: item.approve_label, act:{do:'brain_approve', id}}` |
| `secondary` | «ارفض», which runs `brain_reject` |
| extra button | «عدّل», which runs `brain_edit` |
| `img` | the section image |

Note cards use «احتفظ بها» / «احذفها» instead.

**Hooks into existing code.**
- `v2Decisions` adds `opts.brainItems` (proposed only), built with `v2bItemCard`.
- `v2Card` gets `case 'brain_item'`, which returns the prepared card.

### 4.2 `dashboard-cloud/v2-brain2.js` + `v2-brain2.css` (new)
`window.V2BRAIN` exposes:

**`pending()`**
- `GET /v2/brain/items?status=proposed`, cached for 60 seconds.
- Returns the array; `null` on failure; `undefined` before the first load.

**`decorate(card, {fetch})`**
- Looks the card up in the cache.
- With `fetch`, it POSTs `/opinion`. When the answer is queued, it polls `lookup` every 3 seconds, up to 20 times, and only while the card is on screen.

**`prefetch(cards)`**
- One `lookup` call for the visible tickets.
- `lookup` never writes.

**`act(card, act, cb)`**
- Opens a confirmation sheet with the exact text.
- «عدّل» opens a textarea filled with the draft. «احفظ وأرسل» sends approve with `text`.
- Member send sheet:
  - title «إرسال الرد»;
  - body «يصل هذا الرد إلى صاحب الرسالة إشعارًا داخل المنصة.»;
  - buttons «نعم، أرسله» / «رجوع».
- Site message sheet: «يُحفظ الرد هنا ويُنسخ لترسله بنفسك. لا يُرسل بريد من اللوحة بعد.»
- On success, copy `copy_text` with `navigator.clipboard` and show the toast «نُسخ النص».
- On `no_reply`, show «لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.» For any other error, show the server's error text.

**`mountBar(section, el)`**
- Shows the bar «ما كتبه العقل هنا» with up to 3 cards, then «اعرض الكل (<n>)».
- Hidden on `home` and `brain`, when there are no items, and when the flag is off.

**`sig()`**
- Returns a signature used to decide when to redraw.

### 4.3 Placement (P4 edits)

**`v2-home.js`**
- `gather()` adds `brainItems: V2BRAIN.pending()`.
- `drawFocus`:
  - call `c = V2BRAIN.decorate(c, {fetch:true})`;
  - prefetch the next card;
  - render `src` as a small muted line inside `.v2-brain`.
- `run()` adds the cases `brain_approve`, `brain_reject` and `brain_edit`, all via `track()`.
- `stillPending` treats a `brain_item` as pending while it is still in `pending()`.
- `signature` includes `V2BRAIN.sig()`.

**`v2-shell.js`**
- At boot, create `#v2bbar` (class `v2-bbar`, hidden) next to `#v2sbar`.
- `drawHead` calls `V2BRAIN.mountBar(sec.key, #v2bbar)`.

**`v2s/home.js`** (the tickets for files, disputes and messages, ~line 287)
- Decorate the tickets from the cache.
- Make one `prefetch` call.

**`v2s/people.js`** (the trainer and join tickets)
- Decorate from the cache.

**`index.html`**
- Add `<link rel="stylesheet" href="v2-brain2.css"><script src="v2-brain2.js"></script>` right after `v2-d3.js`.

### 4.4 Rules, log and helpers (`v2s/brain.js`, P5)
Pure helpers go in the `v2s:brain` block only.

**Rules card: new first group «ما يكتبه العقل».**
- Hint: «اقتراحات يكتبها العقل من بيانات حقيقية».
- One row per producer, taken from `/switches`.
- Control: `role=radiogroup` with «وحده | يسألني | متوقّف».
  - Locked producers show «يسألني | متوقّف», with `lock_reason` as the status line.
  - `opinion` shows «وحده | متوقّف».
- Tapping a segment opens a confirm sheet, then sends `PUT` with `confirmed:true`, then shows the toast «حُفظ الاختيار».
- The rule sheet shows the sentence, plus «أين ترى نتيجته», which calls `openSection(section)`.

**«اكتب الاقتراحات الآن» (ghost button at the bottom of the group).**
- Sheet text: «يكتب العقل الآن ما ينقص من اقتراحات، بحد أقصى <U(n)> كتابة.»
- Buttons: «نعم، ابدأ» / «رجوع».
- Confirming sends `POST /v2/brain/run` and shows the toast «بدأ العقل الكتابة».
- The button is disabled while a run is active.

**The free-text rule box stays as it is** («لم تُبنَ بعد»).

**Log rows.** Source: `GET /v2/brain/items?status=all&since=<local midnight>`.

| Status | Row text | Action |
|---|---|---|
| `done_alone` | «كتب ملاحظة على «…»» | «احذفها» (see below) |
| `proposed` | «اقترح «<tag>» على «…»» | «افتح» |
| `approved` / `edited` | «نُفّذ «<tag>» على «…» بموافقتك» | — |
| `rejected` | «رُفض اقتراح على «…»» | — |
| `discarded` | «حُذفت ملاحظة على «…»» | — |
| `failed` | «تعذّرت الكتابة عن «…»» | — |

- «احذفها» opens the sheet «تُحذف هذه الملاحظة. لم تغيّر شيئًا في المنصة.» and then shows the toast «حُذفت الملاحظة».
- Opinions are not listed one by one. They get a single summary row: «كتب رأيه في <U(n, قرار)>».

**Brain line, case 2b.** When there are proposed items, show «ينتظرك من العقل: <U(n, اقتراح)>» with the button «ابدأ القرارات», which calls `openSection('home')` and opens the focus deck.

**Helpers tab.** Two discs:
- «من يكتب الآن»: «الكاتب الأساسي», «الكاتب الاحتياطي» or «لا أحد».
- «كتابات العقل اليوم»: «<used> من <cap>».

### 4.5 Copy rules
These are tested on the new JS strings and on the Arabic strings in Python.
- Modern Standard Arabic, gender-neutral.
- None of these: «يقوّم», «اعكس», «⇒», «✓», «لما ».
- No Latin, except in emails and in AI-written blocks.
- No headline starts with «الذكاء».
- Never show «0», «null» or «undefined». Show «غير متاح بعد» instead.
- Never say that a site reply was emailed.

## 5) Tests (zero real calls)

**Shared setup for every backend test.**
- Monkeypatch `appmod.requests.post` and `appmod.requests.get` so they raise.
- Use a fake transport on `call_anthropic` / `call_openai_compatible` that returns scripted JSON.
- Set `app.config['BRAIN_INLINE']=True`.

**P1: `test_brain2_engine.py` and `test_brain2_routes.py`**

Engine:
- Idempotency: running again makes 0 calls.
- Each cap works: run, day, opinion, reserve.
- `cap` and `no_key` stop the run.
- A failed row blocks a same-day retry.
- Template rows are marked `source='template'`.
- Each honesty check rejects its case: number, Latin, banned words, email, phone.
- `off` skips gather.
- A locked producer can never run `alone`: the route returns 400, and the engine coerces a tampered row.
- An `alone` note becomes `done_alone`; a draft never does.
- Apply runs exactly once. A double approve gives 409. `no_reply` gives `unknown`. A failed apply returns the row to `proposed`.

Routes:
- `decided_by` comes from the token; a `by` field in the body is ignored.
- The items allow-list returns no `meta` and no `facts`.
- `lookup` never calls `ai_call`.
- Opinion facts are cleaned; facts over 3KB give 400.
- Every route is admin-only, returns 404 with no calls when the flag is off, and sends `no-store`.
- `run-cron` without the secret gives 401.
- The agents run-cron kick does not block (patch the starter).
- The run lock gives 409.

Model:
- The default is `claude-sonnet-5-5`.
- An env override works.
- The retired Claude names are ignored.
- A `DASHBOARD_AI_MODEL` with a mismatched prefix is ignored.
- `docker-compose.yml` has the new default.
- Update the pins in `test_ai_model_cap_and_visibility.py`.

**P2: `test_brain2_ops.py`; P3: `test_brain2_biz.py`**

Use local fakes for `_platform_proxy`, `_bridge_get` and `_v2_get`. For each producer, test that:
- gather builds the right targets, and raises `SourceDown` only for the source that failed;
- the user prompt contains no email, no phone and no meta;
- `validate` rejects a bad shape or a wrong enum, and `course_id` must come from the list;
- templates work;
- apply calls the exact existing path with the exact body (`confirmed:true`, `by` = actor);
- a visitor message gets the copy-only apply.

**P4: `test_brain2_ui.py`**

Node logic tests via `v2_node.logic`, plus static checks:
- `v2bFacts` output contains no '@', no phone digit runs, and only allow-listed keys.
- `v2bDecorate` produces every mark. Money kinds are never remapped. A remap only uses acts the card already has.
- `v2bItemCard` builds the card in §4.1.
- `v2Decisions` orders `brainItems` correctly.
- The `index.html` line and `#v2bbar` in `v2-shell.js` are present.
- Copy scan of the new strings.

Shots: `uiharness/v2_shots_brain2.py` with `brain2_fixtures.py`, at desktop, tablet and mobile sizes:
- the focus deck with an AI opinion;
- the focus deck with a failed mark;
- a reply draft card, the edit sheet and the send sheet;
- the brain bars on people and content;
- the existing checks: no horizontal scroll, target sizes, no Latin, no «0».

**P5: add to `test_v2s_brain.py`**
- Node tests for the switch rows and the log rows.
- Copy scan.
- Shots 18-switches, 19-locked-sheet, 20-log-items and 21-run-sheet, in `v2_shots_brain.py`.

## 6) Work split

**Step 0** (main session, already committed before the packages start)
- The `brain2` package skeleton, with `contract.py` and `registry.py`.
- Empty producer modules.
- `COPY` lines in the Dockerfile.
- The guarded registration line and the cron kick in `app.py`.
- The `index.html` lines.
- Stub `v2-brain2.js` / `.css`.

**Packages.** Each package owns only the files listed for it.

| Package | Owns |
|---|---|
| **P1 Engine** | `brain2/engine.py`; `v2_brain2_routes.py`; the app.py AI section (§2.6); the `writer` field in `v2_brain_routes.py` (B3); `docker-compose.yml`; `backend/.env.example`; `test_brain2_engine.py`; `test_brain2_routes.py`; the pins in `test_ai_model_cap_and_visibility.py` |
| **P2 Ops producers** | `brain2/producers_ops.py`; `test_brain2_ops.py` |
| **P3 Section producers** | `brain2/producers_biz.py`; `test_brain2_biz.py` |
| **P4 Cards, deck and bar** | `v2-brain2.js`; `v2-brain2.css`; `v2-logic.js` (the `v2Card` / `v2Decisions` hooks and the end block only); `v2-home.js`; `v2-shell.js`; `v2s/home.js`; `v2s/people.js`; `test_brain2_ui.py`; `uiharness/v2_shots_brain2.py`; `brain2_fixtures.py` |
| **P5 Rules, log and helpers** | `v2s/brain.js`; `v2s/brain.css`; the `v2s:brain` block of `v2-logic.js`; `test_v2s_brain.py`; `uiharness/v2_shots_brain.py`; `brain_fixtures.py` |

**Integration** (main session)
1. Merge in this order: Step 0, then P1, then P2 and P3, then P4, then P5.
2. Run the suites file by file.
3. Run the port-binding shots outside the sandbox.

## 7) Review checklist
- [ ] Every AI call goes through `ns['ai_call']`.
- [ ] Nothing calls the platform's `/bridge/agents/*`.
- [ ] Caps and the reserve are checked before each call.
- [ ] No AI call runs inside a request thread, and `lookup` never writes.
- [ ] Locks are enforced on the server.
- [ ] Approve requires `confirmed:true`.
- [ ] The actor comes from the token.
- [ ] Apply uses existing write paths only.
- [ ] All honesty checks are active.
- [ ] A failed write shows the static line with its mark.
- [ ] No text claims an email was sent.
- [ ] No sentence says money waits for the founder.
- [ ] `meta` never reaches the AI or the browser.
- [ ] Idempotency, no retries, run lock and queue limit all work.
- [ ] Flag off gives 404 with no calls, and `DASH_BRAIN_WRITE=0` stops all writing.
- [ ] The copy rules pass.
- [ ] No new roles.
- [ ] The course editor is excluded, and its hook is present.
- [ ] The model default is `claude-sonnet-5-5`, the compose file has the new default, and the `DASHBOARD_AI_MODEL` mismatch guard works.
- [ ] Deploy note for the founder: when the Anthropic key is added, remove or update `ANTHROPIC_MODEL` and `DASHBOARD_AI_MODEL` in Coolify.
