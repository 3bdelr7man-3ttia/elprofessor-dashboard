# D1: The founder's new home ("the board") + «ابدأ القرارات» — build spec

**Founder approval:** 2026-10-30, «توكل على الله وابدا اشتغل عليها», after approving the concept at https://claude.ai/artifact/7okXZj6NRzm4KMZvW6nUBa (the «المعتمد» row, boards POS-Home / POS-Phone / POS-Focus).
**The full plan:** `_reference/elprofessor-platform-walkthrough/DASHBOARD-PLAN-2026-10-30.md`.
**The code map this spec relies on:** the agent report in the session + `DASHBOARD-MAP-2026-10-30.md`.
**Branch:** `dash-v2-d1` in the worktree `~/Documents/Playground/elprofessor-dashboard-v2` (branched from `expert-file-r14@fe54d22`).

## Goal
When the founder opens the dashboard and the switch is on, he lands on one board:
1. **«الحاجة الجاية»** at the top: the brain's most urgent item.
2. A button: **«ابدأ القرارات (N)»**.
3. **12 tiles** with photos and live counts. Overdue counts are red and pulse. Clicking a tile opens the existing screen for that section.

«ابدأ القرارات» opens a focus mode that shows **one decision at a time**:
- the brain's suggestion and a one-line reason;
- one large button that runs the existing action;
- «غيّر/افتح», which opens the existing drawer;
- «بعدين».

It works the same on mobile at 390px.

## Hard rules
- **The switch:** `DASH_V2_ENABLED` (env, default off). With it off, nothing changes for anyone: the default screen and the menu stay as they are, and the new files load but do nothing.
- **No AI in D1.** The brain's suggestion is built only from data we already store: `candidates[].auto_pick`, `assign_log`, the hours, the amounts, the counts. No call to `ai_call` or to the platform agents.
- **No new decision paths except one:** a proxy for recording an expert payout, settle/reject (below). Every other button calls the existing `EP.decideInboxItem` or the existing expert-file functions in `dashboard-api.js`. Don't copy them.
- **Any button that moves money** (settle a payout, confirm a receipt, refund, resolve a dispute):
  - It shows a confirmation with the amount, the currency, and the name before it runs, using the `efRefundModal` pattern.
  - It sends `confirmed:true`.
  - The actor (`by`) is taken from the token on the server.
- **What needs reading is not a one-click approve:** an expert's first opinion under review, a dispute, a course, a book. For these the main button is «افتح وراجع», which opens the existing drawer or screen.
- **Visible text:** plain standard Arabic, gender-neutral, no technical terms, no «AI» or «ذكاء» at the start of any headline. The word for the decision engine is «العقل».
- **Don't touch:** the escrow/dispute logic or the existing drawer except to call them, and the books/courses screens (owned by the pillars session).
- **No network:** no network requests and no paid calls in tests. Use the fake platform `tests/uiharness/fake_platform.py`.

## Server (`backend/app.py`)
1. **`GET /api/v2/config`** (`@token_required` + `@roles_required('admin')`): returns `{"enabled": bool}` from `DASH_V2_ENABLED` (`'true'`/`'1'` case-insensitive).
   - Non-admin roles get `enabled:false`. The route is admin-only, so for them it returns 403 and the browser treats that as `false`.
2. **`POST /api/platform-wallet-payouts/<id>/settle`** and **`/reject`** (admin only).
   - They proxy to the platform's `POST /api/bridge/wallet-payouts/{id}/settle|reject` (`ops_bridge.py:355,399`) through `_platform_proxy`, following the pattern of `platform-manual-payments/<id>/confirm`.
   - settle requires `{reference (non-empty, ≤120), confirmed:true}`. reject requires `{reason (non-empty, ≤500), confirmed:true}`. Otherwise it returns 400 with an Arabic message.
   - Write `_audit` with the actor and the amount if the platform returned it.
   - ⚠️ Check the platform's actual body field names in `elprofessor-wt-r8/backend/routes/ops_bridge.py` before writing. If a name differs, follow the platform.
3. **Dockerfile + `deploy/Dockerfile.coolify`:** add `COPY dashboard-cloud/v2-home.js dashboard-cloud/v2-home.css /app/dist/` and `COPY dashboard-cloud/v2/img /app/dist/v2/img`. Make sure `serve_frontend` serves nested paths (`v2/img/x.jpg`) as files.

## Browser
New files (keep `index.html` changes minimal):
- **`dashboard-cloud/v2-logic.js`:** pure functions with no DOM, testable with node.
  - `v2Tiles(queue, extras)` ⇒ 12 tiles `{key, label, img, count, hot, next, dest, land?}`.
  - `v2Decisions(inboxRows, payouts, opsQueue)` ⇒ an ordered list of cards.
  - `v2Card(row)` ⇒ `{kind, tag, title, sub, brain, reason, primary:{label, act, money?}, secondary:{label, act}, img?}`.
  - `v2Next(decisions)` ⇒ the first card or null.
  - `v2Health(opsQueue)` ⇒ `{ok, alerts[]}`.
  - Export to `window.V2L` and to `module.exports` together.
- **`dashboard-cloud/v2-home.js`:** the drawing and the interaction, using `EP.ensure` to load `opsQueue`, `inbox`, `walletPayouts`, `invites`, `pendingUsers`.
- **`dashboard-cloud/v2-home.css`:** styles inherited from the brand: burgundy `#9E2B4E`, paper `#FBFAF7`/`#F6F1EA`, ink `#21262E`, red `#C8102E` for overdue counts only. Fonts Cairo / IBM Plex Sans Arabic as the dashboard already loads them.

`index.html` changes:
- Load the 3 files.
- Add `home:{label:'اللوحة',…,grp:'today'}` to `MODULES` as the **first** entry, shown only when the switch is on.
- One branch in `renderView`: `if(current==='home')return V2.render(v)`.
- When the switch is on, the default screen for an admin becomes `home` instead of `inbox`. Change it in `initialModuleFromHash` and `go` only when there's no `#` in the URL.
- Fetch `/api/v2/config` once at boot, before `renderNav`. If it fails, the switch counts as off.

### The 12 tiles (counts from `ops/queue` and the existing loaders, never computed twice)
| Tile | img | Count (red & pulsing when the first part is > 0) | Line under the name | Opens |
|---|---|---|---|---|
| ملفات الخبراء | files | **late + assign_overdue**, then + in_review + awaiting_assignment + blocked | "٢ متأخر · ٣ تنتظر مراجعتك" | `goOps('inbox', filter for the files lane if one exists)` |
| النزاعات والاستردادات | disputes | **expert_files_disputed + expert_files_case_disputed + consultation_disputes** + consultations_legacy + manual_refunds_pending + expert_files_unactivated | | `inbox` with filter `t:disputes` |
| الدورات والمدرّبون | courses | courses_pending + trainer_applications_pending + live_needs_decision.length | | `courses` |
| سوق الخدمات | market | open requests with offer_count=0 (from the existing market loader if available, otherwise hide the number) | | `market` |
| الكتب | books | knowledge `pending_review` (existing loader) | | `knowledge` |
| الناس والدعوات | people | pending visitors + invites awaiting_approval + open join requests + founding_leads_new | | `invites` |
| الفلوس | money | wallet_payouts_pending + manual_payments_pending + **stuck_card_payments** + course_split_pending | "٤ تحويلات · إيصال" | `finance` |
| المحتوى | content | topics_drafts + testimonials_pending | | `topics` |
| التسويق | marketing | no count in D1 | "الحملات والسوشيال" | `marketing` |
| التقارير | reports | no count | "شغّال · واقف · فرصة" | `analysis` |
| العقل | brain | count of the brain's own actions today (`assign_log` entries with `by:'auto'` today, from the inbox rows) | "وزّع ٣ ملفات وحده اليوم" | a small panel inside v2: «سجل العقل اليوم» listing these entries (time · what · file), with no «اعكس» in D1 |
| الشركة ورأس المال | company | no count | "الشركاء والمعدات والإعدادات" | `investment` |

- **Tile design:** the photo covers the tile, with the section color gradient from the bottom. Name 22px / next line 14px in white. The count is a white circle top-left (red & pulsing if hot), with `prefers-reduced-motion` respected.
- **Grid:** 4×3 on desktop, 2 columns on mobile.
- A tile with a count of 0 shows no circle.
- If a loader failed, show «تعذّر الجلب» in place of the number, never 0. See the trap in `empty_screen_worse_than_missing`.

### Header
- The «البروفيسور» logo.
- Health: a green dot «كل شيء يعمل», or amber «N تنبيه». Clicking it opens a list of `alerts[]` + `heartbeats`.
- A bell with the count of `alerts[]`.
- The user icon.
- No search box and no «اطلب من العقل» in D1. Nothing fake.

### «الحاجة الجاية» + «ابدأ القرارات»
A dark bar containing:
- the paper elephant avatar;
- «الحاجة الجاية» + the text of the first card;
- «العقل وزّع N ملف اليوم»;
- a burgundy button «ابدأ القرارات (N)».

With no decisions, it reads «مفيش قرارات مستنياك دلوقتي — العقل شغّال» and the button is hidden.

### Decision order (`v2Decisions`)
1. Overdue / urgent files (late, assign_overdue, urgent waiting).
2. Disputes.
3. Refunds / unactivated.
4. Payouts.
5. Receipts.
6. First opinions under review.
7. Trainers / join requests.
8. Visitors awaiting opening.
9. Founding leads.
10. Content / books / programs.
11. Messages / leads.

Within each group, oldest first.

### The card (`v2Card`), per kind (`apiKind` or source)
| Kind | tag | brain + reason (deterministic) | Main button | Secondary |
|---|---|---|---|---|
| expert_file waiting/blocked | ملف ينتظر خبيرًا | "أقترح {auto_pick.name}: {same specialty / same country / {load} open files}". If there's no candidate: "لا يوجد خبير متاح" | «أرسله إلى {name}» ⇒ existing assign | «افتح الملف» |
| expert_file late / assign_overdue | ملف متأخر | "متأخر {h} ساعة عند {current}. أقترح نقله إلى {next eligible}" | «انقله إلى {name}» ⇒ existing reassign | «افتح الملف» |
| expert_file review | أول رأي لخبير جديد | "رأي {expert} في «{title}» ينتظر مراجعتك" | «افتح وراجع» ⇒ drawer | — |
| dispute (file/consultation/case) | نزاع | "{from} يعترض على {title} · {amount}" | «افتح النزاع» ⇒ drawer | — |
| expert_file unactivated | دفع بلا ملف | "{amount} اتدفعت ولم يصل ملف" | «افتح» ⇒ drawer | — |
| payout | تحويل أرباح | "{name} · {amount} {currency} · {method}" + "راجعتها مع الاستردادات" **only if there is no open dispute for the same person (if that can't be checked, drop the sentence)** | «سجّل التحويل» ⇒ modal asking for the transfer reference + confirm amount/name ⇒ settle | «ارفض» ⇒ modal with a reason ⇒ reject |
| manual_payment | إيصال تحويل | "{method} · {amount} · {what}" + link to the receipt image | «أكّد الدفع» ⇒ money confirmation ⇒ existing confirm | «ارفض» (existing, with a reason) |
| trainer | مدرّب جديد | "{name} · {specialty} · {facts from the application: years, attachments}" | «اقبله» ⇒ existing approve | «افتح الطلب» |
| join | طلب انضمام | same | «اقبل» | «افتح» |
| pending_user | زائر ينتظر الفتح | "{name} · {country} · منذ {age}" | «افتح له المنصة» ⇒ existing access member | «افتح» |
| founding | خبير مؤسس | "{name} · {specialty}" | «تواصلت معه» ⇒ status contacted | «افتح» |
| book / course / program / topic / creative / verify | per kind | a short line | «افتح وراجع» ⇒ drawer/screen | — |
| lead / message | رسالة | first line of the message | «تم» ⇒ existing resolve | «افتح» |

- Every card shows the time («منذ ٣ ساعات») and the counter «٣ من ١٢».
- **After the main button succeeds:** the card disappears with a short motion, the next one appears, and a line is added to «أنجزت الآن» on the side. Reload `inbox`/`opsQueue` in the background.
- **On failure:** the card stays, the error message shows on it in Arabic, and it doesn't advance.
- **«بعدين»** moves the card to the end of the list for this session only.
- **«غيّر/افتح»** opens the existing screen or drawer on the same item (`goOps('inbox', …selected=i…)`). It returns to focus mode when the drawer closes, if that's simple; otherwise a «ارجع للقرارات» button.
- **The end:** the paper elephant with «خلصت. العقل يكمّل الباقي» + «ارجع للوحة».

### Mobile (390px)
- The tiles are 2 columns.
- The dark bar is compact.
- Focus mode is one column: image on top, buttons at least 52px tall and fixed at the bottom.

## Tests (required, zero network)
- **pytest `backend/tests/test_v2_d1.py`:**
  - config enabled/disabled, and that non-admins are blocked.
  - settle/reject: proxy to the right path, rejection without `confirmed`/reference/reason, `_audit` written, the platform's error passed through as an Arabic message.
  - The Dockerfile contains the new files (text check on both Dockerfiles).
- **node tests via `subprocess`, following the `test_blog_topics.py` pattern:** for `v2-logic.js`:
  - the order;
  - the tile counts from a queue fixture;
  - a failed loader gives `null`/«تعذّر», not 0;
  - the payout card drops the review sentence when it can't be checked;
  - review/dispute have no one-click approve;
  - Arabic text with no "AI"/«ذكاء» in the headlines.
- **Screenshots** with the `tests/uiharness/v2_shots.py` tool, modeled on `expert_files_shots.py` + `fake_platform` (a failure if any request goes outside it except Google fonts). Desktop 1440×900 and mobile 390×844 for:
  1. The board with the switch on (fake data in every tile).
  2. Focus mode for each kind: file awaiting an expert, overdue file, opinion under review, dispute, payout, receipt, trainer, visitor.
  3. The payout modal.
  4. The error on a card.
  5. The end state.
  6. The board with no decisions.
  7. The dashboard with the switch off (proof that nothing changed).
- Run the old dashboard suite as it is. The known failures are the port `PermissionError`s inside the sandbox and nothing else.

## Done =
- Tests pass.
- Screenshots in `docs/v2/shots-d1/`.
- A summary in `docs/v2/STATUS-D1.md`.
- A commit on `dash-v2-d1` with explicit paths. No push.
