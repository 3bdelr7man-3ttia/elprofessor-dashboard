/* ============================================================================
 * v2s/identity_docs.js — «توثيق هوية» في الوارد (R22، «هوية محفوظة»).
 * وثيقة هوية خبير بانتظار قرار المؤسس: يفتح الوثيقة (صورة داخل الصفحة، وPDF بنزّل وافتح)، ثم يقرّر:
 *   «وثّق الهوية»  ⇒ يوسَم الخبير «هوية محفوظة» · «محتاج مستند أوضح» ⇒ سبب مكتوب يقرؤه الخبير كما تكتبه (مطلوب، ٥ أحرف على الأقل).
 * الصفّ نفسه يبنيه dashboard-api.js (`apiKind: 'identity_doc'`) والقرار يمرّ من `EP.decideInboxItem` (verify / needs_another).
 * ⛔ الاسم الحقيقي والوثيقة للمؤسس وحده (البروكسي للأدمن بس). ⛔ الوثيقة بالتوكن ⇒ blob؛ لا رابط عام ولا كاش.
 * ⛔ نصوص ظاهرة: فصحى بسيطة، بلا مصطلحات تقنية، و«·» لا تلاصق رقمًا. الدرج يُرسَم من `drawerHtml` (نقية) و`wire` يربط الأزرار.
 * ========================================================================== */
(function (root) {
  'use strict';
  var DIG = '٠١٢٣٤٥٦٧٨٩';
  var NOTE_MIN = 5, NOTE_MAX = 300;   // نفس حد المنصة
  var NEED_REASON_AR = 'اكتب سبب طلب مستند آخر بوضوح — يقرؤه الخبير كما تكتبه';
  var FILE_ERR = { 404: 'الوثيقة غير متاحة', 422: 'تعذّر عرض هذا الملف', other: 'تعذّر جلب الوثيقة، حاول مرة أخرى' };

  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function arDigits(s) { return String(s == null ? '' : s).replace(/\d/g, function (d) { return DIG.charAt(+d); }); }
  // «·» ما تلاصق رقمًا أبدًا: تتحول «،».
  function fixSep(s) { return String(s == null ? '' : s).replace(/([\d٠-٩])\s*·\s*/g, '$1، ').replace(/\s*·\s*([\d٠-٩])/g, '، $1'); }
  function plain(s) { return fixSep(arDigits(s)); }

  // سبب «محتاج مستند أوضح» ⇒ {ok, text} | {ok:false, error}. الخبير يقرؤه حرفًا، فلا قرار بسبب فارغ أو أقصر من خمسة أحرف.
  function reasonCheck(text) {
    var t = str(text).slice(0, NOTE_MAX);
    if (t.length < NOTE_MIN) return { ok: false, error: NEED_REASON_AR };
    return { ok: true, text: t };
  }
  function fileError(status) { return FILE_ERR[status] || FILE_ERR.other; }
  function fileIdOk(id) { return /^[A-Za-z0-9_-]{8,64}$/.test(str(id)); }

  function field(lab, val, ltr) {
    val = str(val);
    return val ? '<div class="field"><div class="lab">' + esc(lab) + '</div><div class="val"' + (ltr ? ' style="direction:ltr;text-align:right"' : '') + '>' + esc(val) + '</div></div>' : '';
  }

  // الدرج كله من صفّ الوارد. الأزرار بسمة `data-idd` (لا `data-a`: حلقة الدرج العامة تكتب فوق `data-a`).
  function drawerHtml(row) {
    row = row || {};
    var title = str(row.idTitle), name = str(row.idName);
    var fileId = str(row.idFileId);
    var doc = fileIdOk(fileId)
      ? '<button type="button" class="btn btn-ghost" data-idd="view" id="iddView">عرض الوثيقة</button><div id="iddOut" aria-live="polite" style="margin-top:10px"></div>'
      : '<div class="val" style="color:var(--conflict)">لا ملف مرفوع مع هذا الطلب، فلا يمكن توثيقه الآن. اطلب من الخبير مستندًا.</div>';
    return '<div class="dh"><div class="k">توثيق هوية</div><h3>' + esc(row.out || ('توثيق هوية — ' + (title || 'خبير'))) + '</h3></div><div class="db">'
      + '<div class="note-ai"><div>راجع الوثيقة، وقارن الاسم المكتوب فيها بصفته المعلنة، ثم قرّر: وثّق الهوية، أو اطلب مستندًا أوضح.</div></div>'
      + field('الاسم الحقيقي (يراه المؤسس وحده)', name)
      + field('الصفة المعلنة', title)
      + field('البريد', row.email || row.personEmail, true)
      + field('وقت التقديم', plain(row.whenLabel || ''))
      + '<div class="field"><div class="lab">الوثيقة</div><div class="val">' + doc + '</div></div>'
      + '<div class="field"><div class="lab">سبب طلب مستند أوضح</div><div class="val">'
      + '<textarea data-idd-reason rows="2" maxlength="' + NOTE_MAX + '" placeholder="مثال: الصورة غير واضحة، ارفع صورة أوضح للوجه الأمامي بالكامل" '
      + 'style="width:100%;padding:8px 10px;border-radius:9px;border:1px solid var(--line);background:var(--surface);color:inherit;font:inherit;font-size:12.5px;resize:vertical"></textarea>'
      + '<div class="from" style="margin-top:4px;font-weight:400">مطلوب عند «محتاج مستند أوضح» فقط، ويقرؤه الخبير كما تكتبه.</div></div></div>'
      + '<div data-idd-msg role="alert" style="min-height:18px;margin:6px 0;font-size:12.5px"></div>'
      + '<div class="acts">'
      + '<button type="button" class="btn btn-human" data-idd="ok" id="iddOk">وثّق الهوية</button>'
      + '<button type="button" class="btn btn-ask" data-idd="no" id="iddNo">محتاج مستند أوضح</button>'
      + '<button type="button" class="btn btn-ghost" data-idd="close" id="iddClose">إغلاق</button>'
      + '</div></div>';
  }

  // يربط الأزرار. h = { api(path, opts)⇒Promise<Blob>, decide(action, reason)⇒Promise<{ok, error}>, close(), toast(text) }.
  function wire(el, row, h) {
    function q(sel) { return el.querySelector(sel); }
    var msg = q('[data-idd-msg]'), view = q('#iddView'), out = q('#iddOut'), ok = q('#iddOk'), no = q('#iddNo'), cl = q('#iddClose');
    var shown = null, busy = false;
    function say(text, bad) { if (!msg) return; msg.textContent = text || ''; msg.style.color = bad ? 'var(--conflict)' : 'var(--ok, inherit)'; }
    function lock(on) { busy = on; [ok, no].forEach(function (b) { if (b) b.disabled = on; }); }
    function hideDoc() {
      if (out) out.innerHTML = '';
      if (shown && shown.revoke) { try { URL.revokeObjectURL(shown.revoke); } catch (e) {} }
      shown = null;
      if (view) view.textContent = 'عرض الوثيقة';
    }
    if (view && out) {
      view.onclick = function () {
        if (view.dataset.busy) return;
        if (shown) { hideDoc(); return; }
        view.dataset.busy = '1'; view.disabled = true; view.textContent = 'جارٍ جلب الوثيقة…'; out.innerHTML = '';
        function fin(failed) { delete view.dataset.busy; view.disabled = false; view.textContent = failed ? 'عرض الوثيقة' : 'أخفِ الوثيقة'; }
        h.api('/platform-identity-docs/files/' + encodeURIComponent(str(row.idFileId)), { blob: true }).then(function (blob) {
          var type = String(blob && blob.type || '').toLowerCase();
          if (type.indexOf('image/') === 0) {
            var fr = new FileReader();
            fr.onload = function () { out.innerHTML = '<img alt="صورة وثيقة الهوية" style="max-width:100%;border-radius:9px;border:1px solid var(--line)" src="' + esc(String(fr.result)) + '">'; shown = {}; fin(); };
            fr.onerror = function () { out.innerHTML = '<div role="alert" style="color:var(--conflict)">' + esc(fileError(0)) + '</div>'; fin(true); };
            fr.readAsDataURL(blob);
          } else if (type === 'application/pdf') {
            var href = URL.createObjectURL(blob);
            out.innerHTML = '<p class="from">الوثيقة بصيغة PDF.</p><a class="btn btn-ghost" href="' + href + '" download="identity-document.pdf" target="_blank" rel="noopener">نزّل الوثيقة وافتحها</a>';
            shown = { revoke: href }; fin();
          } else { out.innerHTML = '<div role="alert" style="color:var(--conflict)">' + esc(fileError(422)) + '</div>'; fin(true); }
        }).catch(function (e) {
          if (e && e.status === 401) return;   // الجلسة انتهت: الغلاف بيعرض الدخول
          out.innerHTML = '<div role="alert" style="color:var(--conflict)">' + esc(fileError(e && e.status)) + '</div>'; fin(true);
        });
      };
    }
    function run(action, reason) {
      if (busy) return;
      lock(true); say('جارٍ التنفيذ…', false);
      Promise.resolve(h.decide(action, reason)).then(function (res) {
        res = res || {};
        if (res.ok) { say(action === 'approve' ? 'وُثّقت الهوية.' : 'طُلب من الخبير مستند أوضح.', false); return; }
        lock(false); say(res.error || 'تعذّر تنفيذ القرار، حاول مرة أخرى', true);
      }).catch(function () { lock(false); say('تعذّر تنفيذ القرار، حاول مرة أخرى', true); });
    }
    if (ok) ok.onclick = function () { run('approve', ''); };
    if (no) no.onclick = function () {
      var ta = q('[data-idd-reason]'), c = reasonCheck(ta ? ta.value : '');
      if (!c.ok) { say(c.error, true); if (ta) ta.focus(); return; }   // ⛔ قبل أي نداء
      run('reject', c.text);
    };
    if (cl) cl.onclick = function () { hideDoc(); if (h.close) h.close(); };
  }

  var API = { reasonCheck: reasonCheck, fileError: fileError, fileIdOk: fileIdOk, drawerHtml: drawerHtml, wire: wire, NEED_REASON_AR: NEED_REASON_AR, NOTE_MIN: NOTE_MIN };
  if (typeof window !== 'undefined') root.V2S_IDENTITY = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
