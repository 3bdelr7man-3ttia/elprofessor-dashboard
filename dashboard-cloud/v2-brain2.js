/* ============================================================================
 * v2-brain2.js — «العقل» الجولة ٢: رأي العقل على بطاقات القرار، وبطاقات اقتراحاته، وشريط «ما كتبه العقل هنا» (SPEC docs/v2/brain2 §4.2).
 * ⛔ لا منطق عمل هنا: الحقائق والتزيين وبطاقة الاقتراح من `V2L.v2b*` (نقي في v2-logic.js). هنا الشبكة والذاكرة المؤقتة والأوراق فقط.
 * ⛔ كل فشل يُبتلع بصمت: المسار غائب/مقفول/واقع ⇒ تبقى الجملة الثابتة القديمة كما هي، ولا شيء ينكسر.
 * ⛔ لا نداء ذكاء اصطناعي من المتصفح: رأي جديد يُطلب من الخادم (`/opinion`) وهو يكتبه في الخلفية، والتحقق بـ`lookup` فقط.
 * ⛔ كل اعتماد بورقة تأكيد بنصها، و`confirmed:true`، والفاعل من التوكن (لا نرسل اسمًا).
 * ========================================================================== */
(function () {
  'use strict';
  window.V2BRAIN = window.V2BRAIN || null;
  var L = window.V2L;
  if (!L || !L.v2bFacts) return;
  var UT = L.util;

  var CACHE_MS = 60000, POLL_MS = 3000, POLL_MAX = 20, LOOKUP_MAX = 40, BAR_MAX = 3;
  var NO_REPLY_TEXT = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.';
  var FAIL_TEXT = 'تعذّر تنفيذ العملية';
  var SESSION_TEXT = 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';

  var P = { state: 'idle', items: null, at: 0, loading: false, waiters: [] };    // اقتراحات منتظرة
  var O = {};                                                                      // رأي لكل بطاقة: card_id ⇒ مدخل
  var ver = 0, listeners = [], used = false, closedOpinion = false, bar = { all: false, section: '', el: null };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function ep() { return window.EP || null; }
  function on() { return !!(window.V2SHELL && window.V2SHELL.on && ep() && ep().authed && typeof ep().api === 'function'); }
  function call(method, path, body) { return ep().api(path, { method: method, body: body }); }
  function ar(n) { return UT.ar(n); }
  function toast(t) { try { if (typeof window.toast === 'function') window.toast(t); } catch (e) {} }
  function changed() {
    ver++;
    listeners.slice().forEach(function (fn) { try { fn(); } catch (e) {} });
  }
  function errText(e) {
    if (e && e.status === 401) return SESSION_TEXT;
    var d = (e && e.data) || {};
    return typeof d.error === 'string' && d.error ? d.error : FAIL_TEXT;
  }

  // ------------------------------------------------------------------ الاقتراحات المنتظرة (proposed)
  function finishLoad(ok, items) {
    P.loading = false; P.at = Date.now();
    P.state = ok ? 'ready' : 'error';
    P.items = ok ? items : null;
    var w = P.waiters; P.waiters = [];
    w.forEach(function (fn) { try { fn(P.items); } catch (e) {} });
    changed();
  }
  function load(cb) {
    if (!on()) { if (cb) cb(null); return; }
    if (cb) P.waiters.push(cb);
    if (P.loading) return;
    P.loading = true;
    call('GET', '/v2/brain/items?status=proposed').then(function (d) {
      var list = d && Array.isArray(d.items) ? d.items : (Array.isArray(d) ? d : null);
      if (!list) { finishLoad(false); return; }
      finishLoad(true, list.filter(function (it) { return it && it.id && (it.status == null || it.status === 'proposed'); }));
    }).catch(function () { finishLoad(false); });
  }
  // المصفوفة · null عند الفشل · undefined قبل أول وصول (أو والمفتاح مقفول).
  function pending() {
    if (!on()) return undefined;
    used = true;
    if (P.state === 'idle') load();
    else if (!P.loading && Date.now() - P.at > CACHE_MS) load();
    return P.state === 'ready' ? P.items : (P.state === 'error' ? null : undefined);
  }
  function reload(cb) { P.at = 0; load(cb); }
  function removeItem(id) {
    if (P.items) P.items = P.items.filter(function (it) { return it.id !== id; });
    P.at = 0;
    changed();
  }

  // ------------------------------------------------------------------ رأي العقل على البطاقة
  function onScreen(id) {
    try {
      var n = document.querySelectorAll('[data-bid]');
      for (var i = 0; i < n.length; i++) if (n[i].getAttribute('data-bid') === id) return true;
      return false;
    } catch (e) { return true; }
  }
  function touch(card, f) {
    var key = JSON.stringify(f.facts), e = O[card.id];
    if (!e || e.key !== key) {
      if (e && e.timer) clearTimeout(e.timer);
      e = O[card.id] = { id: card.id, key: key, kind: f.kind, facts: f.facts, state: 'none', item: null, tries: 0, timer: null, asked: false, looked: false, closed: false };
    }
    return e;
  }
  function setReady(e, item) {
    if (e.timer) { clearTimeout(e.timer); e.timer = null; }
    var ok = item && item.body && typeof item.body === 'object' && typeof item.body.text === 'string' && item.body.text.trim();
    e.item = ok ? item : null;
    e.state = ok ? 'ready' : 'failed';
  }
  function poll(e) {
    if (e.timer || e.state !== 'loading') return;
    if (e.tries >= POLL_MAX) { e.state = 'failed'; changed(); return; }
    e.timer = setTimeout(function () {
      e.timer = null;
      if (O[e.id] !== e || e.state !== 'loading') return;
      if (!onScreen(e.id)) return;                          // البطاقة غادرت الشاشة: نتوقف، ويُستأنف حين تظهر ثانية
      e.tries++;
      call('POST', '/v2/brain/opinions/lookup', { cards: [{ kind: e.kind, card_id: e.id, facts: e.facts }] }).then(function (d) {
        var it = d && d.items && d.items[e.id];
        if (it) { setReady(e, it); changed(); } else poll(e);
      }).catch(function () { poll(e); });
    }, POLL_MS);
  }
  var REASON_STATE = { off: 'off', cap: 'cap', busy: 'busy', no_writer: 'failed', not_supported: 'none' };
  function ask(e) {
    e.asked = true; e.state = 'loading';
    call('POST', '/v2/brain/opinion', { kind: e.kind, card_id: e.id, facts: e.facts }).then(function (d) {
      if (d && d.item) setReady(e, d.item);
      else if (d && d.queued) { e.state = 'loading'; poll(e); }
      else { e.state = (d && REASON_STATE[d.reason]) || 'failed'; if (e.state === 'none') e.closed = true; }
      changed();
    }).catch(function (err) {
      if (err && err.status === 404) { e.state = 'none'; e.closed = true; closedOpinion = true; }     // الخادم لا يعرف المسار أو المفتاح مقفول: بصمت
      else e.state = 'failed';
      changed();
    });
  }
  // decorate(card, {fetch, remap}) ⇒ نسخة البطاقة. بلا fetch: من الذاكرة فقط (لا طلب رأي جديد).
  function decorate(card, o) {
    o = o || {};
    if (!card || !on()) return card;
    var f = L.v2bFacts(card, Date.now());
    if (!f) return card;
    var e = touch(card, f);
    if (o.fetch && !e.asked && !e.closed && !closedOpinion) ask(e);
    else if (e.state === 'loading' && !e.timer) poll(e);
    return L.v2bDecorate(card, { state: e.state, item: e.item, remap: o.remap !== false }, Date.now());
  }
  // prefetch(cards): نداء `lookup` واحد لما لم نسأل عنه بعد. لا يكتب ولا يستدعي الذكاء أبدًا.
  function prefetch(cards) {
    if (!on() || closedOpinion) return;
    var list = [];
    (cards || []).forEach(function (c) {
      if (!c || list.length >= LOOKUP_MAX) return;
      var f = L.v2bFacts(c, Date.now());
      if (!f) return;
      var e = touch(c, f);
      if (e.looked || e.asked || e.state !== 'none') return;
      e.looked = true;
      list.push(e);
    });
    if (!list.length) return;
    call('POST', '/v2/brain/opinions/lookup', { cards: list.map(function (e) { return { kind: e.kind, card_id: e.id, facts: e.facts }; }) }).then(function (d) {
      var any = false;
      list.forEach(function (e) {
        var it = d && d.items && d.items[e.id];
        if (it && O[e.id] === e && e.state === 'none') { setReady(e, it); any = true; }
      });
      if (any) changed();
    }).catch(function () {});
  }

  // ------------------------------------------------------------------ الأوراق
  function sheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v2b-m">' + html + '</div>');
    var x = s.querySelector('[data-x]');
    var close = function () { if (!s.dataset.busy) window.closeModal(); };
    if (x) x.onclick = close;
    s.onclick = function (e) { if (e.target === s) close(); };
    return s;
  }
  // وصف الاعتماد بحسب الزر الذي كتبه الخادم (القائمة المسموحة لا تحمل المصدر): عنوان · نص · زر التأكيد · زر الحفظ في التعديل.
  function approveInfo(item) {
    var lab = String(item.approve_label || '');
    if (item.kind === 'note') return { title: 'حفظ الملاحظة', body: 'تبقى هذه الملاحظة محفوظة. لم يتغيّر شيء في المنصة.', go: 'نعم، احتفظ بها', save: 'احفظ التعديل', copy: false };
    if (lab === 'أرسل الرد') return { title: 'إرسال الرد', body: 'يصل هذا الرد إلى صاحب الرسالة إشعارًا داخل المنصة.', go: 'نعم، أرسله', save: 'احفظ وأرسل', copy: false };
    if (lab === 'احفظ الرد وانسخه') return { title: 'حفظ الرد', body: 'يُحفظ الرد هنا ويُنسخ لترسله بنفسك. لا يُرسل بريد من اللوحة بعد.', go: 'نعم، احفظه وانسخه', save: 'احفظ وانسخ', copy: true };
    if (lab === 'انسخ الرد' || lab === 'انسخ الرسالة وعلّمه تم') return { title: lab, body: 'يُنسخ النص لترسله بنفسك، ثم تُعلَّم الرسالة منتهية. لا يُرسل شيء من اللوحة.', go: 'نعم، انسخه', save: 'احفظ وانسخ', copy: true };
    if (lab === 'انشر الدورة') return { title: 'نشر الدورة', body: 'تُنشر الدورة ويراها الناس بعد التأكيد.', go: 'نعم، انشرها', save: 'احفظ واعتمد', copy: false };
    if (lab === 'اربطه بالدورة') return { title: 'ربط الطلب بدورة', body: 'يُربط الطلب بالدورة المقترحة على المنصة بعد التأكيد.', go: 'نعم، اربطه', save: 'احفظ واعتمد', copy: false };
    return { title: lab || 'اعتماد الاقتراح', body: 'يُنفَّذ هذا الاقتراح بعد تأكيدك.', go: 'نعم، اعتمده', save: 'احفظ واعتمد', copy: false };
  }
  function rejectInfo(item) {
    if (item.kind === 'note') return { title: 'حذف الملاحظة', body: 'تُحذف هذه الملاحظة. لم تغيّر شيئًا في المنصة.', go: 'نعم، احذفها' };
    return { title: 'رفض الاقتراح', body: 'يُرفض هذا الاقتراح ولا يُنفَّذ شيء.', go: 'نعم، ارفضه' };
  }
  function doneToast(which, item, edited) {
    if (which === 'reject') return item.kind === 'note' ? 'حُذفت الملاحظة' : 'رُفض الاقتراح';
    if (item.kind === 'note') return 'حُفظت الملاحظة';
    return edited ? 'اعتُمد الاقتراح بعد تعديله' : 'اعتُمد الاقتراح';
  }
  function copyText(t) {
    return new Promise(function (resolve) {
      var fallback = function () {
        try {
          var ta = document.createElement('textarea');
          ta.value = t; ta.setAttribute('readonly', ''); ta.style.cssText = 'position:fixed;top:-1000px;opacity:0';
          document.body.appendChild(ta); ta.select();
          var ok = document.execCommand && document.execCommand('copy');
          ta.remove(); resolve(!!ok);
        } catch (e) { resolve(false); }
      };
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(function () { resolve(true); }, fallback);
        else fallback();
      } catch (e) { fallback(); }
    });
  }
  function copyOf(d) {
    d = d || {};
    return (typeof d.copy_text === 'string' && d.copy_text) || (d.result && d.result.copy_text) || (d.info && d.info.copy_text) || (d.item && d.item.copy_text) || '';
  }

  // الإرسال الفعلي من داخل ورقة مفتوحة. `text` = تعديل المؤسس (اعتماد فقط). cb(res) يُستدعى مرة واحدة عند النجاح أو القفل.
  function send(s, item, which, text, cb, ui) {
    var go = s.querySelector('#v2b_go'), x = s.querySelector('#v2b_x'), err = s.querySelector('#v2b_err');
    if (go.dataset.busy) return;
    go.dataset.busy = '1'; s.dataset.busy = '1'; go.disabled = true; x.disabled = true; err.innerHTML = '';
    var label = go.textContent; go.textContent = 'جارٍ التنفيذ…';
    var path = which === 'reject' ? (item.kind === 'note' && item.status === 'done_alone' ? 'discard' : 'reject') : 'approve';
    var body = { confirmed: true };
    if (which === 'approve' && text != null) body.text = text;
    var fail = function (msg, lock, text) {
      delete s.dataset.busy; x.disabled = false;
      err.innerHTML = '<div class="v2b-err" role="alert">' + esc(msg) + '</div>'
        + (text ? '<p class="v2b-p">يمكنك نسخ النص من هنا:</p><textarea class="v2b-ta" readonly rows="5">' + esc(text) + '</textarea>' : '');
      if (lock) { go.textContent = 'حدّث الصفحة أولًا'; return; }
      delete go.dataset.busy; go.disabled = false; go.textContent = label;
    };
    call('POST', '/v2/brain/items/' + encodeURIComponent(item.id) + '/' + path, body).then(function (d) {
      if (d && d.no_reply) { removeItem(item.id); fail(NO_REPLY_TEXT, true); cb({ ok: false, final: true, error: NO_REPLY_TEXT }); return; }
      var ct = which === 'approve' ? copyOf(d) : '';
      var finish = function () {
        delete s.dataset.busy;
        window.closeModal();
        removeItem(item.id);
        reload();
        cb({ ok: true, text: doneToast(which, item, text != null && text !== ui.original) });
      };
      if (!ct) { toast(doneToast(which, item, text != null && text !== ui.original)); finish(); return; }
      copyText(ct).then(function (okc) {
        if (okc) { toast('نُسخ النص'); finish(); return; }
        // لم يسمح المتصفح بالنسخ: النص يبقى أمامه ليأخذه بنفسه.
        delete s.dataset.busy; x.disabled = false; x.textContent = 'تم';
        removeItem(item.id); reload();
        go.style.display = 'none';
        err.innerHTML = '<p class="v2b-p">لم يُنسخ النص تلقائيًا. انسخه من هنا:</p><textarea class="v2b-ta" readonly rows="6">' + esc(ct) + '</textarea>';
        x.onclick = function () { window.closeModal(); cb({ ok: true, text: doneToast(which, item, false) }); };
      });
    }).catch(function (e) {
      var status = e && e.status, data = (e && e.data) || {}, msg = errText(e);
      if (data.no_reply || !status) { removeItem(item.id); fail(NO_REPLY_TEXT, true); cb({ ok: false, final: true, error: NO_REPLY_TEXT }); return; }
      if (status === 409) { removeItem(item.id); fail(msg, true); cb({ ok: false, final: true, error: msg }); return; }
      fail(msg, false, typeof data.copy_text === 'string' ? data.copy_text : '');     // ٤٢٢ مع نص جاهز للنسخ (زائر بلا حساب مثلًا): الخطأ ومعه النص
    });
  }

  function quote(text) { return text ? '<blockquote class="v2b-quote">' + esc(text) + '</blockquote>' : ''; }
  // قائمة تعديلات الموقع كاملة (كل تعديل: القديم ⇒ الجديد + السبب)؛ لا اختصار ولا قصّ، فالمؤسس يعتمد ما يراه كله.
  function editsList(edits) {
    if (!edits || !edits.length) return '';
    return '<ol class="v2b-edits">' + edits.map(function (e) {
      return '<li><div class="v2b-e-old"><small>القديم</small><span>' + esc(e.old) + '</span></div>'
        + '<div class="v2b-e-new"><small>الجديد</small><span>' + esc(e.new) + '</span></div>'
        + (e.why ? '<div class="v2b-e-why"><small>السبب</small><span>' + esc(e.why) + '</span></div>' : '') + '</li>';
    }).join('') + '</ol>';
  }
  function confirmSheet(card, item, which, cb) {
    var info = which === 'reject' ? rejectInfo(item) : approveInfo(item);
    var edits = which === 'approve' ? ((card && card.edits) || (L.v2bItemCard(item, Date.now()) || {}).edits || []) : [];
    var s = sheet(info.title, '<p class="v2b-p">' + esc(info.body) + '</p>' + (edits.length ? editsList(edits) : quote(item.body && item.body.text))
      + '<div id="v2b_err"></div><div class="acts"><button type="button" class="btn ' + (which === 'reject' ? 'btn-human' : 'btn-primary') + '" id="v2b_go">' + esc(info.go) + '</button>'
      + '<button type="button" class="btn btn-ghost" id="v2b_x">رجوع</button></div>');
    if (!s) return;
    s.querySelector('#v2b_x').onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    s.querySelector('#v2b_go').onclick = function () { send(s, item, which, null, cb, { original: item.body && item.body.text }); };
  }
  function editSheet(card, item, cb) {
    var info = approveInfo(item), orig = (item.body && item.body.text) || '';
    var s = sheet('عدّل النص', '<p class="v2b-p">' + esc(info.body) + '</p>'
      + '<div class="fld"><label for="v2b_t">النص</label><textarea id="v2b_t" class="v2b-ta" rows="8" maxlength="900">' + esc(orig) + '</textarea></div>'
      + '<div id="v2b_err"></div><div class="acts"><button type="button" class="btn btn-primary" id="v2b_go">' + esc(info.save) + '</button>'
      + '<button type="button" class="btn btn-ghost" id="v2b_x">رجوع</button></div>');
    if (!s) return;
    var t = s.querySelector('#v2b_t'), go = s.querySelector('#v2b_go');
    var sync = function () { if (!go.dataset.busy) go.disabled = !String(t.value || '').trim(); };
    t.addEventListener('input', sync); sync();
    setTimeout(function () { try { t.focus(); } catch (e) {} }, 30);
    s.querySelector('#v2b_x').onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    go.onclick = function () { send(s, item, 'approve', String(t.value || '').trim(), cb, { original: orig }); };
  }
  // act(card, act, cb): cb({ok:true,text}) عند النجاح · cb({ok:false,final:true,error}) عند القفل (ردّ ضائع أو حُسم من قبل). الإلغاء لا يستدعي cb.
  function act(card, a, cb) {
    var item = card && card.brainItem;
    cb = cb || function () {};
    if (!item || !a || !on()) return;
    if (a.do === 'brain_edit') return editSheet(card, item, cb);
    if (a.do === 'brain_approve') return confirmSheet(card, item, 'approve', cb);
    if (a.do === 'brain_reject') return confirmSheet(card, item, 'reject', cb);
  }

  // ------------------------------------------------------------------ شريط «ما كتبه العقل هنا»
  function barCard(c) {
    var note = c.brainItem && c.brainItem.kind === 'note';
    return '<article class="v2b-c" data-bid="' + esc(c.id) + '" data-id="' + esc(c.brainItem.id) + '">'
      + '<div class="v2b-top"><span class="v2b-tag">' + esc(c.tag) + '</span>' + (c.ageText ? '<time>' + esc(c.ageText) + '</time>' : '') + '</div>'
      + '<h3>' + esc(c.title) + '</h3><p class="v2b-t">' + esc(c.brain) + '</p>'
      + '<div class="v2b-acts"><button type="button" class="v2b-b1" data-a="brain_approve">' + esc(c.primary.label) + '</button>'
      + (c.edit && !note ? '<button type="button" class="v2b-b2" data-a="brain_edit">' + esc(c.edit.label) + '</button>' : '')
      + '<button type="button" class="v2b-b2" data-a="brain_reject">' + esc(c.secondary.label) + '</button></div></article>';
  }
  function hide(el) { if (el && (!el.hidden || el.innerHTML)) { el.hidden = true; el.innerHTML = ''; el.__v2bh = ''; } }
  function mountBar(section, el) {
    if (!el) return;
    bar.section = section; bar.el = el;
    if (!on() || !section || section === 'home' || section === 'brain') { hide(el); return; }
    var items = pending();
    var mine = Array.isArray(items) ? items.filter(function (it) { return it.section === section; }) : [];
    if (!mine.length) { hide(el); return; }
    var now = Date.now();
    var cards = mine.map(function (it) { return L.v2bItemCard(it, now); }).filter(Boolean);
    var many = cards.length > BAR_MAX;
    var shown = (bar.all && many) ? cards : cards.slice(0, BAR_MAX);
    var html = '<section class="v2b-bar" aria-label="ما كتبه العقل هنا"><header class="v2b-h"><img class="v2b-av" src="v2/img/brain-avatar.jpg" alt="">'
      + '<div><b>ما كتبه العقل هنا</b><small>اقتراحات تنتظر قرارك</small></div><span class="v2b-n">' + esc(ar(cards.length)) + '</span></header>'
      + '<div class="v2b-list">' + shown.map(barCard).join('') + '</div>'
      + (many ? '<button type="button" class="v2b-all" data-a="all" aria-expanded="' + (bar.all ? 'true' : 'false') + '">' + (bar.all ? 'اعرض أقل' : 'اعرض الكل (' + esc(ar(cards.length)) + ')') + '</button>' : '')
      + '</section>';
    el.hidden = false;
    if (el.__v2bh === html) return;
    el.__v2bh = html;
    el.innerHTML = html;
    var byId = {};
    cards.forEach(function (c) { byId[c.brainItem.id] = c; });
    Array.prototype.forEach.call(el.querySelectorAll('.v2b-c'), function (art) {
      var c = byId[art.getAttribute('data-id')];
      Array.prototype.forEach.call(art.querySelectorAll('[data-a]'), function (b) {
        b.onclick = function () {
          act(c, { do: b.getAttribute('data-a') }, function (res) { if (res && res.ok) changed(); });
        };
      });
    });
    var all = el.querySelector('.v2b-all');
    if (all) all.onclick = function () { bar.all = !bar.all; el.__v2bh = ''; mountBar(bar.section, el); };
  }

  // توقيع التغيّر: يتغير عند وصول اقتراحات أو آراء. ومعه نتأكد أن الذاكرة المؤقتة لا تشيخ فوق دقيقة (بعد أول استعمال).
  function sig() {
    if (!on()) return '';
    if (used && P.state !== 'idle' && !P.loading && Date.now() - P.at > CACHE_MS) load();
    return String(ver);
  }
  function listen(fn) {
    listeners.push(fn);
    return function () { listeners = listeners.filter(function (x) { return x !== fn; }); };
  }

  window.V2BRAIN = { pending: pending, reload: reload, decorate: decorate, prefetch: prefetch, act: act, mountBar: mountBar, sig: sig, listen: listen,
                     remove: removeItem, isOn: on, _state: { P: P, O: O } };
})();
