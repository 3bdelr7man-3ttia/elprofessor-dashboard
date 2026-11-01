/* ============================================================================
 * v2s/saha_glossary.js — لوحة «القاموس» (تبويب في قسم «المحتوى») على المحرّك المشترك `V2S_SAHA_KIT.board` من saha.js (ولهذا اسمه `saha_glossary.js` ويُحمَّل بعد `saha_diwan.js`؛ المنطق النقي في `glossary.js`).
 * مربّعات بصور: المصطلحات · نقاشات المصطلحات (نقاش «الساحة» لكل منشور) · الاستيراد، ومعها حين تُفعَّل مراجعات المتخصصين: تنتظر مراجعة خبير · مراجعات القاموس · شرط المراجعة.
 * (قرار المؤسس ٢٠٢٦-١١-٠١: المراجعات مطفأة افتراضيًا، فالحالات «مسودة / منشور» والأربعة الأخرى لا تظهر، و«راجعه» ختم داخلي في شاشة المصطلح.)
 * وكل مصطلح له شاشة: النص كاملًا · الحالة والمراجعة · النقاش في الساحة (افتح نقاشًا جديدًا أو اربط موجودًا). وكل مراجعة لها شاشة: ما كتبه المتخصص وما هو عليه المصطلح الآن.
 * ⛔ لا منطق عمل هنا: كل التحقق والنصوص من `V2L.v2sGlossary`. ولا طلب شبكة إلا `/api/v2/content/glossary/*` (أدمن بس).
 * ⛔ كل كتابة تمرّ على ورقة مراجعة ثم تأكيد وتذهب بـ`confirmed: true` (والمعاينة وحدها بلا تأكيد لأنها لا تكتب). مفيش confirm()/alert()/prompt() ولا حفظ في المتصفح.
 * ⛔ المفتاح مقفول: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو index.html نادى `render` (والغلاف الجديد شغّال).
 * ========================================================================== */
(function () {
  'use strict';
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  var L = window.V2L, Kit = window.V2S_SAHA_KIT;
  if (!L || !L.v2sGlossary || !Kit || !Kit.board) return;
  var G = L.v2sGlossary, U = L.util, ar = U.ar;
  var bdi = function (v) { return '<bdi>' + Kit.esc(v) + '</bdi>'; };   // اسم المراجع نص من زائر: يُعزل اتجاهه عمّا حوله
  var esc = Kit.esc, q1 = Kit.q1, qa = Kit.qa, fld = Kit.fld, inp = Kit.inp, txt = Kit.txt, sel = Kit.sel;

  var BASE = '/v2/content/glossary';
  var P = { all: BASE + '?limit=500', topics: BASE + '/topics', reviews: BASE + '/reviews?status=all&limit=500' };
  var HUB = [P.all];
  var B = null;
  var searchT = null;

  function termsView() { var d = B.data(P.all); return d ? G.terms(d) : null; }
  function topicsView() { var d = B.data(P.topics); return d ? G.topics(d) : null; }
  function reviewsView() { var d = B.data(P.reviews); return d ? G.reviews(d) : null; }
  function reviewById(id) { var v = reviewsView(); if (v) for (var i = 0; i < v.rows.length; i++) if (v.rows[i].id === String(id)) return v.rows[i]; return null; }
  function rvPath(rv, tail) { return BASE + '/reviews/' + encodeURIComponent(rv.id) + (tail || ''); }
  function reviewsOn() { var v = termsView(); return !!(v && v.reviewsEnabled); }
  function stateClass(r) { return !r.reviewsOn ? (r.published ? 'green' : '') : (r.confirmed ? 'green' : (r.underReview ? 'gold' : '')); }
  function requireReview() { var v = termsView(); return v ? v.requireReview : false; }
  function rowById(id) { var v = termsView(); if (v) for (var i = 0; i < v.rows.length; i++) if (v.rows[i].id === String(id)) return v.rows[i]; return null; }
  function path(r, tail) { return BASE + '/' + encodeURIComponent(r.id) + (tail || ''); }
  function ltr(html) { return html.replace(/^<(input|textarea) /, '<$1 dir="ltr" '); }
  function toTop() { try { var c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); } catch (e) {} }
  function goSub(sub) { B.S.sub = sub; B.redraw(); toTop(); }

  // —— ورقة المراجعة: القيم بعلامة الاتجاه (الإنجليزي لاتيني بأرقامه، والعربي بأرقام هندية) والتحذيرات بعد الفروق
  function gDiff(lines) {
    if (!lines || !lines.length) return '';
    return '<ul class="sh-diff">' + lines.map(function (l) {
      var change = l.from != null && l.from !== '', dir = l.ltr ? 'ltr' : 'auto', fix = function (t) { return l.ltr ? t : G.arDigits(t); };
      return '<li><b>' + esc(l.label) + '</b><span>' + (change ? '<s dir="' + dir + '">' + esc(fix(l.from)) + '</s><i aria-hidden="true">←</i>' : '') + '<em dir="' + dir + '">' + esc(fix(l.to)) + '</em></span></li>';
    }).join('') + '</ul>';
  }
  function warnsHtml(warns) { return warns && warns.length ? '<ul class="sh-warns">' + warns.map(function (w) { return '<li>' + esc(w) + '</li>'; }).join('') + '</ul>' : ''; }
  function withDiff(res) {
    if (res && res.ok && !res.extraHtml) { res.extraHtml = gDiff(res.lines) + warnsHtml(res.warns); res.lines = []; res.warns = []; }
    return res;
  }

  // ------------------------------------------------------------------ المربّعات
  function tiles() {
    var on = reviewsOn();
    var all = Kit.count(B, P.all, function () { var v = termsView(); return v ? { n: ar(v.counts.all), note: v.counts.all ? G.summary(v.counts) : 'لا مصطلحات بعد، استورد القاموس الأساسي' } : null; });
    var tp = Kit.count(B, P.all, function () { var v = termsView(); return v ? { n: ar(v.counts.publishedNoTopic), note: v.counts.publishedNoTopic ? 'مصطلح منشور بلا نقاش في الساحة' : 'لكل منشور نقاشه', hot: v.counts.publishedNoTopic > 0 } : null; });
    var imp = { n: 'استورد', note: 'القاموس الأساسي أو ملف', word: true };
    var list = [Object.assign({ sub: 'terms', name: 'المصطلحات', img: 'books' }, all), Object.assign({ sub: 'topics', name: 'نقاشات المصطلحات', img: 'people' }, tp)];
    if (on) {
      var wait = Kit.count(B, P.all, function () { var v = termsView(); return v ? { n: ar(v.counts.unreviewed), note: v.counts.unreviewed ? 'مصطلح ينتظر مراجعة خبير' : 'لا مصطلحات تنتظر', hot: v.counts.unreviewed > 0 } : null; });
      var rvw = Kit.count(B, P.all, function () { var v = termsView(); return v ? { n: ar(v.counts.reviewsPending), note: v.counts.reviewsPending ? 'مراجعة من متخصصين تنتظر قرارك' : 'لا مراجعات تنتظر', hot: v.counts.reviewsPending > 0 } : null; });
      var rules = Kit.count(B, P.all, function () { var r = G.rulesView(termsView()); return r ? { n: r.word, note: 'مراجعة الخبير قبل النشر', word: true, hot: r.on } : null; });
      list.push(Object.assign({ sub: 'wait', name: 'تنتظر مراجعة خبير', img: 'disputes' }, wait), Object.assign({ sub: 'reviews', name: 'مراجعات القاموس', img: 'content' }, rvw));
      list.push(Object.assign({ sub: 'import', name: 'استيراد المصطلحات', img: 'files' }, imp), Object.assign({ sub: 'rules', name: 'شرط المراجعة', img: 'company' }, rules));
      return list;
    }
    list.push(Object.assign({ sub: 'import', name: 'استيراد المصطلحات', img: 'files' }, imp));
    return list;
  }
  // شاشة مراجعات المتخصصين مطفأة: لا نداء لها ولا عرض
  function offScreen(title, img) { return { title: title, sub: '', img: img, html: B.empty('غير مفعّلة الآن', 'ارجع إلى مربّعات القاموس.') }; }

  // ------------------------------------------------------------------ ١ · قائمة المصطلحات
  function filters(mode) {
    var on = reviewsOn(), st = B.f('gst', 'all');
    if (!on && (st === 'confirmed' || st === 'under_review')) st = 'published';          // شرائح الحالة الثلاث تختفي والمراجعات مطفأة
    return { q: B.f('gq', ''), area: B.f('garea', 'all'), status: st, review: on ? (mode === 'wait' ? 'unreviewed' : B.f('grev', 'all')) : 'all' };
  }
  function listCols(on) {
    var cols = [
      { h: 'المصطلح', c: function (r) { return '<b class="sh-t">' + esc(r.ar) + '</b><span class="sh-sub" dir="ltr">' + esc(r.en) + '</span>' + (r.fr ? '<span class="sh-sub" dir="ltr">' + esc(r.fr) + '</span>' : ''); } },
      { h: 'المجال', c: function (r) { return esc(r.areaText); } },
      { h: 'الحالة', c: function (r) { return Kit.pill(r.statusText, stateClass(r)); } }
    ];
    if (on) cols.push({ h: 'المراجعة', c: function (r) { return r.reviewed ? Kit.pill('راجعه خبير', 'green') + '<span class="sh-sub">' + bdi(r.reviewerName) + '، ' + bdi(r.reviewerRole) + '</span>' : Kit.pill('ينتظر خبيرًا', 'gold'); } });
    return cols;
  }
  function listActs(r) {
    var id = ' data-id="' + esc(r.id) + '"';
    var main = r.reviewsOn && !r.reviewed ? '<button type="button" class="ep-b1" data-a="grev"' + id + '>راجعه</button>'
      : (!r.published ? '<button type="button" class="ep-b1" data-a="gpub"' + id + '>انشر</button>' : '<button type="button" class="ep-b2" data-a="gunpub"' + id + '>ألغِ النشر</button>');
    return '<button type="button" class="ep-b2" data-a="gopen"' + id + '>افتح</button>' + main;
  }
  function listBody(v, mode) {
    var f = filters(mode), rows = G.filterRows(v.rows, f);
    if (!v.rows.length) return B.empty('لا مصطلحات بعد', 'استورد القاموس الأساسي أو أضف مصطلحًا بيدك') + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="gimport">استورد المصطلحات</button></div>';
    if (!rows.length) {
      var clean = !f.q && f.area === 'all' && f.status === 'all' && (mode === 'wait' || f.review === 'all');
      return clean && mode === 'wait' ? B.empty('لا مصطلحات تنتظر مراجعة خبير', 'كل مصطلح في القاموس عليه ختم مراجعة') : B.empty('لا مصطلحات تطابق بحثك', 'جرّب كلمة أخرى أو امسح الفلاتر');
    }
    return '<p class="sh-count">' + esc(G.termCountText(rows.length)) + '</p>' + B.list(rows, listCols(v.reviewsEnabled), listActs);
  }
  function screenList(mode) {
    return function () {
      B.need(P.all);
      var v = termsView(), f = filters(mode), wait = mode === 'wait' && !!(v && v.reviewsEnabled), body;
      if (!v) body = B.stateBlock(P.all, 'المصطلحات');
      else {
        var c = v.counts, on = v.reviewsEnabled;
        body = '<div class="sh-top"><button type="button" class="ep-b1" data-a="gnew">أضف مصطلحًا</button><button type="button" class="ep-b2" data-a="gimport">استورد مصطلحات</button></div>'
          + '<ul class="sh-nums" aria-label="أعداد المصطلحات">' + (on ? '<li><b>' + esc(ar(c.confirmed)) + '</b><span>مؤكّد</span></li><li><b>' + esc(ar(c.underReview)) + '</b><span>تحت التأكيد</span></li>'
              : '<li><b>' + esc(ar(c.published)) + '</b><span>منشور</span></li>')
          + '<li><b>' + esc(ar(c.draft)) + '</b><span>مسودة</span></li></ul>'
          + '<div class="sh-sbox"><label for="shQ">ابحث في المصطلحات</label><input id="shQ" type="text" dir="auto" autocomplete="off" value="' + esc(f.q) + '" placeholder="بالعربية أو الإنجليزية أو الفرنسية أو في التعريف"></div>'
          + '<span class="sh-flabel">المجال</span>' + B.chips('garea', G.areaChips(c), f.area)
          + '<span class="sh-flabel">الحالة</span>' + B.chips('gst', G.statusChips(on), f.status)
          + (wait || !on ? '' : '<span class="sh-flabel">المراجعة</span>' + B.chips('grev', G.REVIEW_CHIPS, f.review))
          + (v.truncated ? '<p class="sh-fine">يعرض الجدول أول ' + esc(ar(v.rows.length)) + ' مصطلح من أصل ' + esc(ar(v.total)) + '.</p>' : '')
          + '<div id="gList">' + listBody(v, mode) + '</div>';
      }
      return { title: wait ? 'تنتظر مراجعة خبير' : 'المصطلحات', sub: v ? G.summary(v.counts) : '', img: wait ? 'disputes' : 'books', html: body, after: function (vw) {
        var i = q1('#shQ', vw);
        if (!i) return;
        i.addEventListener('input', function () {
          B.set('gq', i.value);
          clearTimeout(searchT);
          searchT = setTimeout(function () { var box = q1('#gList'), tv = termsView(); if (box && tv) box.innerHTML = listBody(tv, mode); }, 120);
        });
      } };
    };
  }

  // ------------------------------------------------------------------ ٢ · شاشة المصطلح
  function line(label, inner) { return '<p class="g-line"><b>' + esc(label) + '</b><span>' + inner + '</span></p>'; }
  function screenTerm() {
    B.need(P.all); B.need(P.topics);
    var v = termsView(), r = v ? rowById(B.f('gopen', '')) : null;
    var fromRv = B.f('gfrom', 'terms') === 'review' || B.f('gfrom', 'terms') === 'reviews';
    var back = '<div class="sh-top"><button type="button" class="ep-bs" data-a="gtolist">' + (fromRv ? '→ مراجعات القاموس' : '→ كل المصطلحات') + '</button></div>';
    if (!v) return { title: 'المصطلح', sub: '', img: 'books', html: back + B.stateBlock(P.all, 'المصطلح') };
    if (!r) return { title: 'المصطلح', sub: '', img: 'books', html: back + B.empty('لم نجد هذا المصطلح', 'ربما حُذف أو تغيّر. ارجع إلى القائمة.') };
    var req = v.requireReview, id = ' data-id="' + esc(r.id) + '"', rel = G.relatedView(r, v.rows);
    var sug = suggestionFor(r);
    var term = (sug ? sugPanel(sug) : '') + '<div class="sh-panel g-term"><div class="g-top">' + Kit.pill(r.areaText) + Kit.pill(r.statusText, stateClass(r)) + '</div>'
      + '<h3 class="g-ar">' + esc(r.ar) + '</h3>'
      + '<p class="g-lang" dir="ltr"><b>EN</b><span>' + esc(r.en) + '</span></p>' + (r.fr ? '<p class="g-lang" dir="ltr"><b>FR</b><span>' + esc(r.fr) + '</span></p>' : '')
      + '<h4 class="g-h">التعريف</h4><p class="g-def">' + esc(G.arDigits(r.definition)) + '</p>'
      + (r.exampleEn || r.exampleAr ? '<h4 class="g-h">مثال</h4>' + (r.exampleEn ? '<p class="g-ex" dir="ltr">' + esc(r.exampleEn) + '</p>' : '') + (r.exampleAr ? '<p class="g-ex">' + esc(G.arDigits(r.exampleAr)) + '</p>' : '') : '')
      + (r.falseFriend ? '<div class="g-false"><b>خطأ شائع</b><p>' + esc(G.arDigits(r.falseFriend)) + '</p></div>' : '')
      + (r.countries ? '<h4 class="g-h">ملاحظة الدول</h4><p class="g-def">' + esc(G.arDigits(r.countries)) + '</p>' + (r.confirmed || !r.reviewsOn ? '' : '<p class="sh-fine">لا تظهر هذه الملاحظة على الموقع قبل أن يؤكّد خبير المصطلح.</p>') : '')
      + (rel.length ? '<h4 class="g-h">مصطلحات قريبة</h4><div class="g-rel">' + rel.map(function (x) {
          return x.known ? '<button type="button" class="sh-chip" data-a="gopen" data-id="' + esc(x.id) + '">' + esc(x.label) + '</button>'
            : '<span class="sh-st mute" dir="ltr">' + esc(x.slug) + '</span><small class="sh-sub">لم يُستورد بعد</small>';
        }).join('') + '</div>' : '')
      + '<p class="g-line"><b>رابط المصطلح</b><span><bdi dir="ltr">' + esc(r.slug) + '</bdi>' + (r.frozen ? ' (لا يتغيّر بعد أول نشر)' : '') + '</span></p>'
      + (r.previewUrl ? '<p class="g-line">' + Kit.link(r.previewUrl, 'معاينة صفحة المصطلح على الموقع') + '</p>' : '') + '</div>';
    var why = G.publishBlock(r, req);
    var acts = '<button type="button" class="ep-b2" data-a="gedit"' + id + '>عدّل المصطلح</button>'
      + (r.reviewed ? '<button type="button" class="ep-b2" data-a="grev"' + id + '>جدّد ختم المراجعة</button><button type="button" class="ep-bs" data-a="gunrev"' + id + '>امسح الختم</button>'
          : '<button type="button" class="ep-b1" data-a="grev"' + id + '>راجعه</button>')
      + (r.published ? '<button type="button" class="ep-b2" data-a="gunpub"' + id + '>ألغِ النشر</button>'
          : '<button type="button" class="ep-b' + (r.reviewed || !req ? '1' : '2') + '" data-a="gpub"' + id + (why ? ' disabled aria-describedby="gWhy"' : '') + '>انشر المصطلح</button>')
      + (r.canDelete ? '<button type="button" class="ep-bs" data-a="gdel"' + id + '>احذف</button>' : '');
    var stamp = r.reviewed ? '<b>راجعه: ' + bdi(r.reviewerName) + '، ' + bdi(r.reviewerRole) + '</b>' + (r.reviewedOn ? ' <small class="sh-sub">' + esc(r.reviewedOn) + '</small>' : '') : 'لم يراجعه خبير بعد';
    var status = r.reviewsOn
      ? '<div class="sh-panel"><h3>الحالة والمراجعة</h3>' + line('الحالة', Kit.pill(r.statusText, stateClass(r))) + line('المراجعة', stamp)
        + (r.reviewed ? line('ظهور الاسم', r.namePublic ? 'يظهر للناس' : 'لا يظهر، وتقول الصفحة «راجعه متخصص»') : '')
        + (r.siteBadge ? line('على الموقع', esc(r.siteBadge)) : '')
        + (why ? '<p class="g-why" id="gWhy" role="status">' + esc(why) + '</p>' : '') + '<div class="sh-acts">' + acts + '</div></div>'
      : '<div class="sh-panel"><h3>الحالة</h3>' + line('الحالة', Kit.pill(r.statusText, stateClass(r)))
        + '<h4 class="g-h">مراجعة داخلية، لا تظهر على الموقع</h4>' + line('المراجعة', r.reviewed ? stamp : 'لم تُسجَّل مراجعة')
        + (why ? '<p class="g-why" id="gWhy" role="status">' + esc(why) + '</p>' : '') + '<div class="sh-acts">' + acts + '</div></div>';
    return { title: r.ar, sub: r.areaText, img: 'books', html: back + term + status + topicPanel(r), after: function (vw) {
      var s = q1('#gTopic', vw);
      if (s) s.addEventListener('change', function () { var e = q1('#gTopicErr', vw); if (e) e.textContent = ''; });
    } };
  }
  function topicPanel(r) {
    var id = ' data-id="' + esc(r.id) + '"', tv = topicsView(), body;
    if (r.topicId) {
      var title = G.topicTitle(tv, r.topicId);
      body = '<p class="g-line"><b>النقاش المرتبط</b><span>' + (title ? esc(title) : 'نقاش في الساحة') + '</span></p>' + '<p class="g-line">' + Kit.link(G.topicUrl(r.topicId), 'فتح النقاش في الساحة') + '</p>'
        + '<div class="sh-acts"><button type="button" class="ep-b2" data-a="gdetach"' + id + '>افصل النقاش</button></div>';
    } else {
      var can = G.canOpenTopic(r);
      body = '<p class="sh-fine">يُفتح في الساحة نقاش يدعو كل من يرى خطأً في الترجمة أو التعريف إلى كتابة اعتراضه أو اقتراحه، ويظهر في صفحة المصطلح زرّ «ناقشه في الساحة».</p>'
        + (can.ok ? '' : '<p class="g-why" role="status">' + esc(can.error) + '</p>')
        + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="gtopen"' + id + (can.ok ? '' : ' disabled') + '>افتح نقاشًا لهذا المصطلح</button></div>';
      if (!tv) body += B.stateBlock(P.topics, 'قائمة النقاشات');
      else if (tv.rows.length) body += '<h4 class="g-h">أو اربط نقاشًا موجودًا في الساحة</h4>'
        + '<div class="sh-sbox"><label for="gTopic">النقاش</label><select id="gTopic"><option value="">اختر نقاشًا</option>' + tv.rows.map(function (t) { return '<option value="' + esc(t.id) + '">' + esc(t.title) + '</option>'; }).join('') + '</select>'
        + '<small class="ferr g-err" id="gTopicErr" role="alert"></small></div><div class="sh-acts"><button type="button" class="ep-b2" data-a="gattach"' + id + '>اربط النقاش</button></div>';
    }
    return '<div class="sh-panel"><h3>النقاش في الساحة</h3>' + body + '</div>';
  }

  // ------------------------------------------------------------------ اقتراح متخصص بجانب المصطلح (بعد «اعتمد» على اقتراح)
  function suggestionFor(r) { var sg = B.f('gsug', null); return sg && String(sg.termId) === String(r.id) ? sg : null; }
  function sugBody(sg) { return '<b>' + bdi(sg.name) + '</b><small class="sh-sub">' + bdi(sg.specialtyText) + '</small><p>' + esc(G.arDigits(sg.text)) + '</p>'; }
  function sugPanel(sg) {
    return '<div class="sh-panel g-sug"><h3>اقتراح تعديل من متخصص</h3><div class="g-sugtxt">' + sugBody(sg) + '</div>'
      + '<div class="sh-acts"><button type="button" class="ep-bs" data-a="gsugx">أخفِ الاقتراح</button></div></div>';
  }
  function sugBox(sg) { return '<div class="g-sugbox" role="note"><span class="g-sugh">الاقتراح الذي وصلنا</span>' + sugBody(sg) + '</div>'; }

  // ------------------------------------------------------------------ تدفّقات الكتابة
  function termFlow(r) {
    var v = termsView();
    if (!v) return;
    var create = !r, rows = v.rows, req = v.requireReview, names = G.bySlug(rows), rel = [];
    function nameOf(s) { return names[s] ? names[s].ar : s; }
    function gather(root) { var o = Kit.collect(root); o.related = rel.slice(); return o; }
    function relBox(root) {
      var box = q1('#gRel', root);
      if (!box) return;
      var opts = G.relatedOptions(rows, r ? r.slug : '', rel), full = rel.length >= G.RELATED_MAX;
      box.innerHTML = (rel.length ? '<div class="g-rel">' + rel.map(function (s) {
          return '<span class="g-rc"><span' + (names[s] ? '' : ' dir="ltr"') + '>' + esc(nameOf(s)) + '</span>' + (names[s] ? '' : '<small>لم يُستورد بعد</small>')
            + '<button type="button" class="g-rx" data-relx="' + esc(s) + '" aria-label="احذف ' + esc(nameOf(s)) + '">×</button></span>';
        }).join('') + '</div>' : '<p class="sh-fine">لا مصطلحات قريبة بعد.</p>')
        + (full ? '<p class="sh-fine">وصلت إلى الحد الأقصى من المصطلحات القريبة.</p>' : '<div class="g-relpick"><select id="gRelPick" aria-label="اختر مصطلحًا قريبًا"><option value="">اختر مصطلحًا قريبًا</option>'
          + opts.map(function (o) { return '<option value="' + esc(o[0]) + '">' + esc(o[1]) + '</option>'; }).join('') + '</select><button type="button" class="ep-bs" id="gRelAdd">أضف</button></div>');
      var add = q1('#gRelAdd', box), pick = q1('#gRelPick', box);
      if (add) add.onclick = function () { if (pick.value && rel.indexOf(pick.value) < 0) { rel.push(pick.value); relBox(root); } };
      qa('[data-relx]', box).forEach(function (b) { b.onclick = function () { var s = b.getAttribute('data-relx'); rel = rel.filter(function (x) { return x !== s; }); relBox(root); }; });
    }
    var frozen = !!(r && r.frozen);
    B.flow({
      title: create ? 'مصطلح جديد' : 'تعديل المصطلح',
      intro: create ? 'يُحفظ المصطلح مسودة' + (req ? '، ولا يظهر على الموقع قبل أن يراجعه خبير وتنشره.' : '، ولا يظهر على الموقع حتى تنشره.')
        : (r.reviewed ? 'راجعه ' + r.reviewerName + '. تعديل النص يُلغي ختم المراجعة، وسنوضح لك أثر ذلك قبل الحفظ.' : ''),
      init: G.termForm(r),
      collect: gather,
      form: function (vals) {
        rel = (vals.related || []).slice();
        var sg = r ? suggestionFor(r) : null;
        return (sg ? sugBox(sg) : '') + fld('المصطلح بالعربية', inp('ar', vals.ar, { max: 300 }), 'ar')
          + fld('المصطلح بالإنجليزية', inp('en', vals.en, { max: 300, ltr: true }), 'en')
          + fld('المصطلح بالفرنسية (اختياري)', inp('fr', vals.fr, { max: 300, ltr: true }), 'fr')
          + fld('المجال', sel('area', vals.area, G.AREAS, create ? 'اختر المجال' : null), 'area')
          + fld('التعريف', txt('definition_ar', vals.definition_ar, 4, 3000), 'definition_ar')
          + fld('المثال بالإنجليزية (اختياري)', ltr(txt('example_en', vals.example_en, 3, 1500)), 'example_en')
          + fld('المثال بالعربية (اختياري)', txt('example_ar', vals.example_ar, 3, 1500), 'example_ar')
          + fld('الخطأ الشائع (اختياري)', txt('false_friend_note_ar', vals.false_friend_note_ar, 3, 2000), 'false_friend_note_ar', 'تنبيه من خلط شائع بين هذا المصطلح وما يشبهه.')
          + fld('ملاحظة الدول (اختياري)', txt('countries_note_ar', vals.countries_note_ar, 3, 2000), 'countries_note_ar', (v.reviewsEnabled ? 'تظهر في صفحة المصطلح بعد أن يراجعه خبير.' : 'تظهر في صفحة المصطلح.'))
          + '<div class="fld"><label>المصطلحات القريبة</label><div id="gRel"></div><small class="ferr" data-e="related" role="alert"></small></div>'
          + fld('رابط المصطلح', frozen ? inp('slug', vals.slug, { max: 64, ltr: true }).replace('<input ', '<input disabled ') : inp('slug', vals.slug, { max: 64, ltr: true, ph: 'force-majeure' }), 'slug',
              frozen ? 'لا يتغيّر بعد أول نشر.' : (create ? 'يُشتق من الاسم الإنجليزي لو تركته فارغًا، ويتجمّد عند أول نشر.' : 'يمكن تغييره قبل أول نشر فقط.'));
      },
      hook: function (h) { relBox(h.root); },
      check: function (vals) { return withDiff(G.termCheck(vals, create ? 'create' : 'edit', r, req, nameOf)); },
      send: function (res) {
        return create ? B.api(BASE, Object.assign({}, res.body, { confirmed: true })) : B.api(path(r), Object.assign({}, res.body, { confirmed: true }), 'PUT');
      },
      done: function (out) { return G.termDone(create ? 'create' : 'edit', out, v.reviewsEnabled); }
    });
  }
  function reviewFlow(r) {
    var on = r.reviewsOn;
    B.flow({
      title: r.reviewed ? 'تجديد ختم المراجعة' : 'راجعه خبير',
      intro: on ? 'اكتب اسم الخبير الذي راجع المصطلح وصفته. لا يظهر الاسم للناس إلا إذا وافق صاحبه.' : 'اكتب اسم الخبير الذي راجع المصطلح وصفته. مراجعة داخلية، لا تظهر على الموقع.',
      init: { reviewer_name: r.reviewerName, reviewer_role: r.reviewerRole, reviewer_name_public: r.namePublic },
      form: function (vals) {
        return fld('اسم المراجع', inp('reviewer_name', vals.reviewer_name, { max: 120 }), 'reviewer_name')
          + fld('صفته', inp('reviewer_role', vals.reviewer_role, { max: 80, ph: 'مثل: محامٍ أو أستاذ قانون' }), 'reviewer_role', 'تاريخ المراجعة يُسجَّل تلقائيًا.')
          + (on ? '<div class="fld">' + Kit.chk('reviewer_name_public', vals.reviewer_name_public, 'وافق المراجع على ظهور اسمه') + '</div>' : '');
      },
      check: function (vals) { return withDiff(G.reviewCheck(on ? vals : Object.assign({}, vals, { reviewer_name_public: r.namePublic }), r)); },
      send: function (res) { return B.api(path(r, '/review'), Object.assign({}, res.body, { confirmed: true })); },
      done: function () { return G.reviewDone(r); }
    });
  }
  function unreviewFlow(r) {
    B.flow({ title: 'مسح ختم المراجعة', check: function () { return withDiff(G.unreviewCheck(r, requireReview())); },
      send: function () { return B.api(path(r, '/unreview'), { confirmed: true }); }, done: function (out) { return G.unreviewDone(out, r.reviewsOn); } });
  }
  function publishFlow(r) {
    B.flow({ title: 'نشر المصطلح', check: function () { return withDiff(G.publishCheck(r, requireReview())); },
      send: function () { return B.api(path(r, '/publish'), { confirmed: true }); }, done: function () { return G.publishDone(r); } });
  }
  function unpublishFlow(r) {
    B.flow({ title: 'إلغاء نشر المصطلح', check: function () { return withDiff(G.unpublishCheck(r)); },
      send: function () { return B.api(path(r, '/unpublish'), { confirmed: true }); }, done: function () { return G.unpublishDone(r); } });
  }
  function deleteFlow(r) {
    B.flow({ title: 'حذف المصطلح', check: function () { return withDiff(G.deleteCheck(r)); },
      send: function () { return B.api(path(r), { confirmed: true }, 'DELETE'); }, done: function () { return 'حُذف المصطلح «' + r.ar + '»'; },
      after: function () { B.S.sub = B.f('gfrom', 'terms') === 'wait' ? 'wait' : 'terms'; } });
  }
  function attachFlow(r) {
    var s = q1('#gTopic'), err = q1('#gTopicErr');
    var res = G.attachCheck(s ? s.value : '', topicsView(), r);
    if (!res.ok) { if (err) err.textContent = res.error; return; }
    if (err) err.textContent = '';
    B.flow({ title: 'ربط نقاش بالمصطلح', check: function () { return withDiff(res); },
      send: function () { return B.api(path(r, '/attach-topic'), { saha_topic_id: res.body.saha_topic_id, confirmed: true }); }, done: function () { return 'رُبط النقاش بالمصطلح «' + r.ar + '»'; } });
  }
  function detachFlow(r) {
    B.flow({ title: 'فصل النقاش', check: function () { return withDiff(G.detachCheck(r, topicsView())); },
      send: function () { return B.api(path(r, '/detach-topic'), { confirmed: true }); }, done: function () { return 'فُصل النقاش عن المصطلح «' + r.ar + '»'; } });
  }

  // فتح نقاش جديد للمصطلح: نموذج (العنوان والسؤال) ⇒ معاينة من الخادم بلا كتابة (تظهر في ورقة المراجعة) ⇒ تأكيد.
  function openTopicFlow(r) {
    var ck = G.canOpenTopic(r);
    if (!ck.ok) { B.setNote(ck.error); B.redraw(); return; }
    var d = G.topicDefaults(r);
    B.flow({
      title: 'فتح نقاش لهذا المصطلح',
      intro: 'يُفتح النقاش في الساحة بهذا العنوان وهذا السؤال، ويدعو الناس إلى مراجعة الترجمة والتعريف. عدّلهما إن أردت.',
      init: d, nextLabel: 'راجع ثم افتح',
      form: function (vals) {
        return fld('عنوان النقاش', txt('title', vals.title, 2, 200), 'title') + fld('سؤال النقاش', txt('question', vals.question, 3, 5000), 'question');
      },
      check: function (vals) {
        var f = G.topicFormCheck(vals);
        if (!f.ok) return f;
        return B.api(path(r, '/saha-topic/preview'), f.body).then(function (pv) { return withDiff(G.topicOpenCheck(r, pv)); })
          .catch(function (e) { return { ok: false, error: G.writeError(e && e.status, e && e.data) }; });
      },
      send: function (res) { return B.api(path(r, '/saha-topic/open'), Object.assign({}, res.body, { confirmed: true })); },
      done: function (out) { return G.topicOpenDone(out, r); }
    });
  }

  // ------------------------------------------------------------------ ٢ب · نقاشات المصطلحات (كل المنشور بلا نقاش دفعةً)
  function groupList(rows, kind, cap) {
    var list = rows.filter(function (x) { return x.kind === kind; });
    if (!list.length) return '';
    var shown = cap && list.length > cap ? list.slice(0, cap) : list;
    return '<ul class="g-tl">' + shown.map(function (x) {
      return '<li><b>' + esc(x.ar) + '</b> <small dir="ltr">' + esc(x.en) + '</small>' + (kind === 'problem' && x.message ? '<span class="g-tm">' + esc(x.message) + '</span>' : '') + '</li>';
    }).join('') + (shown.length < list.length ? '<li class="g-tmore">و' + esc(U.U(list.length - shown.length, ['مصطلح آخر', 'مصطلحان آخران', 'مصطلحات أخرى', 'مصطلحًا آخر'])) + '</li>' : '') + '</ul>';
  }
  function bulkNums(v) {
    return '<ul class="sh-nums"><li><b>' + esc(ar(v.create)) + '</b><span>' + (v.applied ? 'نقاش جديد فُتح' : 'نقاش جديد سيُفتح') + '</span></li>'
      + '<li><b>' + esc(ar(v.link)) + '</b><span>' + (v.applied ? 'رُبط بنقاش موجود' : 'سيُربط بنقاش موجود') + '</span></li>'
      + '<li><b>' + esc(ar(v.problem)) + '</b><span>' + (v.applied ? 'تُرك لمشكلة' : 'مشكلة تمنع فتحه') + '</span></li></ul>';
  }
  function bulkGroups(v, cap) {
    return (v.problem ? '<div class="sh-warns"><b>مصطلحات بها مشكلة، تُترك كما هي</b>' + groupList(v.rows, 'problem') + '</div>' : '')
      + (v.link ? '<h4 class="g-h">' + (v.applied ? 'رُبطت بنقاش موجود' : 'ستُربط بنقاش موجود') + '</h4>' + groupList(v.rows, 'link') : '')
      + (v.create ? '<h4 class="g-h">' + (v.applied ? 'نقاش جديد فُتح لها' : 'سيُفتح لها نقاش جديد') + '</h4>' + groupList(v.rows, 'create', cap) : '');
  }
  function screenTopics() {
    B.need(P.all);
    var v = termsView(), pv = G.bulkView(B.f('gtpPrev', null)), res = G.bulkView(B.f('gtpRes', null)), busy = B.f('gtpBusy', false), err = B.f('gtpErr', ''), html;
    if (!v) html = B.stateBlock(P.all, 'المصطلحات');
    else {
      var n = v.counts.publishedNoTopic;
      html = '<div class="sh-panel"><p class="sh-fine">يُفتح لكل مصطلح منشور نقاش واحد في الساحة عنوانه «المصطلح بالعربية (بالإنجليزية): هل الترجمة والتعريف دقيقان؟»، ويدعو كل من يرى خطأً إلى كتابة اعتراضه أو اقتراحه. نجمع الاعتراضات ونصلح بناءً عليها. جرّب أولًا لترى ما سيحدث بلا أن يُفتح شيء، ثم أكِّد.</p>'
        + '<p class="sh-cur"><b>منشور بلا نقاش</b><span>' + esc(n ? U.U(n, ['مصطلح واحد', 'مصطلحان', 'مصطلحات', 'مصطلحًا']) : 'لا مصطلحات، لكل منشور نقاشه') + '</span></p>'
        + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="gbprev"' + (busy || !n ? ' disabled' : '') + '>' + (busy ? 'جارٍ التجربة…' : 'جرّب فتح النقاشات (بلا فتح)') + '</button></div>'
        + (err ? '<div class="sh-err" role="alert">' + esc(err) + '</div>' : '') + '</div>';
      if (res) {
        html += '<div class="sh-panel" data-r="gtpres"><h3>' + (res.stopped ? 'توقفت العملية' : 'نتيجة فتح النقاشات') + '</h3><p class="sh-fine">' + esc(G.bulkSummary(res) || 'لم يتغيّر شيء') + '.</p>'
          + bulkNums(res) + bulkGroups(res, 0) + '</div>';
      } else if (pv) {
        html += '<div class="sh-panel" data-r="gtpprev"><h3>نتيجة التجربة</h3><p class="sh-fine">لم يُفتح شيء بعد، والمجموع ' + esc(U.U(pv.rows.length, ['مصطلح واحد', 'مصطلحان', 'مصطلحات', 'مصطلحًا'])) + '.</p>'
          + bulkNums(pv) + bulkGroups(pv, 12)
          + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="gbgo"' + (pv.create + pv.link ? '' : ' disabled') + '>راجع ثم افتح النقاشات</button>' + (pv.create + pv.link ? '' : '<span class="sh-fine">لا شيء يمكن فتحه الآن.</span>') + '</div></div>';
      }
    }
    return { title: 'نقاشات المصطلحات', sub: v ? (v.counts.publishedNoTopic ? U.U(v.counts.publishedNoTopic, ['مصطلح واحد منشور', 'مصطلحان منشوران', 'مصطلحات منشورة', 'مصطلحًا منشورًا']) + ' بلا نقاش' : 'لكل مصطلح منشور نقاشه') : '', img: 'people', html: html };
  }
  function bulkPreview() {
    if (B.f('gtpBusy', false)) return;
    B.set('gtpBusy', true); B.set('gtpErr', ''); B.set('gtpRes', null); B.redraw();
    B.api(BASE + '/saha-topics/bulk/preview', {}).then(function (d) { B.set('gtpBusy', false); B.set('gtpPrev', d); B.redraw(); })
      .catch(function (e) { B.set('gtpBusy', false); B.set('gtpPrev', null); B.set('gtpErr', G.writeError(e && e.status, e && e.data)); B.redraw(); });
  }
  function bulkFlow() {
    var pv = G.bulkView(B.f('gtpPrev', null));
    if (!pv) return;
    B.flow({ title: 'فتح نقاشات المصطلحات', check: function () { return withDiff(G.bulkCheck(pv)); },
      send: function () {
        return B.api(BASE + '/saha-topics/bulk/open', { confirmed: true }).catch(function (e) {
          var part = e && e.data && Array.isArray(e.data.results) ? e.data : null;      // توقفت في وسط الدفعات: ما تمّ قبلها يُعرض
          if (part) { B.set('gtpRes', part); B.set('gtpPrev', null); B.refresh(); B.redraw(); e = { status: e.status, data: Object.assign({}, e.data, { error: G.bulkStopText(e.data, e.status), no_reply: true }) }; }   // no_reply ⇒ محرّك الأوراق يعرض النص كما هو
          throw e;
        });
      },
      done: function (out) { return G.bulkDone(G.bulkView(out)); }, after: function (out) { B.set('gtpRes', out); B.set('gtpPrev', null); } });
  }

  // ------------------------------------------------------------------ ٣ · الاستيراد (تجربة بلا حفظ ثم تأكيد)
  function screenImport() {
    var src = B.f('gimpSrc', 'seed'), file = B.f('gimpFile', null), prev = B.f('gimpPrev', null), busy = B.f('gimpBusy', false), err = B.f('gimpErr', ''), v = prev ? G.importView(prev) : null;
    var chips = '<div class="sh-ctl" role="group">' + G.IMPORT_SOURCES.map(function (c) {
      return '<button type="button" class="sh-chip' + (c[0] === src ? ' on' : '') + '" data-a="gsrc" data-v="' + c[0] + '" aria-pressed="' + (c[0] === src) + '">' + esc(c[1]) + '</button>';
    }).join('') + '</div>';
    var html = '<div class="sh-panel"><p class="sh-fine">يستورد مصطلحات جاهزة إلى القاموس مسودات بلا ختم مراجعة، ولا يكتب فوق مصطلح موجود. جرّب أولًا لترى ما سيحدث بلا أن يُحفظ شيء، ثم أكِّد الاستيراد.</p>'
      + '<span class="sh-flabel">المصدر</span>' + chips
      + (src === 'upload' ? '<div class="sh-sbox"><span class="sh-flabel">ملف المصطلحات</span><label class="ep-bs sh-filebtn"><input id="gImpFile" class="sh-fileinp" type="file" accept=".json,application/json">' + (file ? 'اختر ملفًا آخر' : 'اختر ملفًا') + '</label></div>'
        + (file ? '<p class="sh-cur"><b>الملف المختار</b><span><bdi dir="ltr">' + esc(file.name) + '</bdi>، ' + esc(U.U(file.count, ['مصطلح واحد', 'مصطلحان', 'مصطلحات', 'مصطلحًا'])) + '</span></p>' : '') : '')
      + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="gprev"' + (busy ? ' disabled' : '') + '>' + (busy ? 'جارٍ التجربة…' : 'جرّب الاستيراد (بلا حفظ)') + '</button></div>'
      + (err ? '<div class="sh-err" role="alert">' + esc(err) + '</div>' : '') + '</div>';
    if (v) {
      html += '<div class="sh-panel" data-r="gimp"><h3>نتيجة التجربة</h3><p class="sh-fine">لم يُحفظ شيء بعد، والمجموع ' + esc(U.U(v.total, ['مصطلح واحد', 'مصطلحان', 'مصطلحات', 'مصطلحًا'])) + '.</p>'
        + '<ul class="sh-nums">' + v.rows.map(function (r) { return '<li><b>' + esc(ar(r.n)) + '</b><span>' + esc(r.label) + '</span></li>'; }).join('') + '</ul>'
        + (v.sample.length ? '<div class="sh-warns g-sample"><b>أمثلة من الجديد</b><ul>' + v.sample.map(function (s) { return '<li>' + esc(s.ar) + ' <small dir="ltr">' + esc(s.en) + '</small> (' + esc(s.areaText) + ')</li>'; }).join('') + '</ul></div>' : '')
        + (v.problems.length ? '<div class="sh-warns"><b>صفوف فيها خطأ (' + esc(ar(v.problems.length)) + ')</b><ul>' + v.problems.map(function (p) {
            return '<li>' + (p.row ? 'الصف ' + esc(p.row) : 'صف') + (p.slug ? ' <bdi dir="ltr">' + esc(p.slug) + '</bdi>' : '') + ': ' + esc(p.text) + '</li>'; }).join('') + '</ul></div>' : '')
        + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="ggo"' + (v.changes ? '' : ' disabled') + '>راجع ثم استورد</button>' + (v.changes ? '' : '<span class="sh-fine">لا شيء جديد يُستورد.</span>') + '</div></div>';
    }
    return { title: 'استيراد المصطلحات', sub: 'جرّب أولًا ثم أكِّد', img: 'files', html: html, after: function (vw) {
      var fi = q1('#gImpFile', vw);
      if (fi) fi.onchange = function () {
        var f = fi.files && fi.files[0];
        if (!f) return;
        var rd = new FileReader();
        rd.onload = function () {
          var obj = null;
          try { obj = JSON.parse(String(rd.result)); } catch (e) { obj = null; }
          var ck = G.importFileCheck(obj);
          if (!ck.ok) { B.set('gimpErr', obj === null ? 'تعذّرت قراءة الملف، اختر ملفًا صحيحًا' : ck.error); B.set('gimpFile', null); }
          else { B.set('gimpErr', ''); B.set('gimpFile', { name: f.name, list: ck.list, count: ck.count }); }
          B.set('gimpPrev', null); B.redraw();
        };
        rd.onerror = function () { B.set('gimpErr', 'تعذّرت قراءة الملف'); B.redraw(); };
        rd.readAsText(f);
      };
    } };
  }
  function importPreview() {
    if (B.f('gimpBusy', false)) return;
    var src = B.f('gimpSrc', 'seed'), file = B.f('gimpFile', null), ck = G.importCanPreview(src, file);
    if (!ck.ok) { B.set('gimpErr', ck.error); B.redraw(); return; }
    B.set('gimpBusy', true); B.set('gimpErr', ''); B.redraw();
    B.api(BASE + '/seed/preview', G.importBody(src, file)).then(function (d) { B.set('gimpBusy', false); B.set('gimpPrev', d); B.redraw(); })
      .catch(function (e) { B.set('gimpBusy', false); B.set('gimpPrev', null); B.set('gimpErr', G.writeError(e && e.status, e && e.data)); B.redraw(); });
  }
  function importFlow() {
    var v = G.importView(B.f('gimpPrev', null)), src = B.f('gimpSrc', 'seed'), file = B.f('gimpFile', null);
    if (!v || !v.changes) return;
    B.flow({ title: 'تأكيد الاستيراد', check: function () {
        return withDiff({ ok: true, lead: 'سيُضاف الآن ما رأيته في التجربة إلى القاموس مسودات بلا ختم مراجعة، ولا تظهر على الموقع حتى يراجعها خبير وتنشرها:', goLabel: 'استورد المصطلحات',
                          lines: v.rows.map(function (r) { return { label: r.label, to: ar(r.n) }; }), warns: v.problems.length ? [U.U(v.problems.length, ['صف واحد فيه خطأ', 'صفان فيهما خطأ', 'صفوف فيها خطأ', 'صفًّا فيه خطأ']) + ' ظهرت في التجربة وستُترك'] : [] });
      },
      send: function () { return B.api(BASE + '/seed/import', Object.assign({}, G.importBody(src, file), { confirmed: true })); },
      done: function (out) { return G.importDone(G.importView(out)); }, after: function () { B.set('gimpPrev', null); B.set('gimpFile', null); } });
  }

  // ------------------------------------------------------------------ ٤ · شرط المراجعة
  function screenRules() {
    B.need(P.all);
    if (termsView() && !reviewsOn()) return offScreen('شرط المراجعة', 'company');
    var v = termsView(), r = G.rulesView(v), body;
    if (!r) body = B.stateBlock(P.all, 'شرط المراجعة');
    else {
      body = '<div class="sh-panel"><div class="sh-stat"><b class="sh-big ' + (r.on ? 'gold' : 'green') + '">مراجعة الخبير قبل النشر: ' + esc(r.word) + '</b></div>'
        + '<p class="sh-fine">' + esc(r.text) + '</p>'
        + '<dl class="g-rules"><dt>عند التفعيل</dt><dd>' + esc(r.onText) + '</dd><dt>عند الإغلاق، وهو الوضع الافتراضي</dt><dd>' + esc(r.offText) + '</dd></dl>'
        + (r.publishedUnreviewed ? '<div class="sh-warn" role="status"><span>' + esc(r.puText) + '</span><button type="button" class="ep-bs" data-a="gwaitpub">اعرضها</button></div>' : '')
        + '<div class="sh-acts"><button type="button" class="ep-b' + (r.on ? '2' : '1') + '" data-a="grules">' + (r.on ? 'أغلق شرط المراجعة' : 'اجعل المراجعة مطلوبة') + '</button></div></div>';
    }
    return { title: 'شرط المراجعة', sub: r ? 'مراجعة الخبير قبل النشر: ' + r.word : '', img: 'company', html: body };
  }
  function rulesFlow() {
    var v = termsView();
    if (!v) return;
    var want = !v.requireReview;
    B.flow({ title: want ? 'جعل المراجعة مطلوبة' : 'إغلاق شرط المراجعة', check: function () { return withDiff(G.settingsCheck(want, v.requireReview, v.counts.publishedUnreviewed)); },
      send: function (res) { return B.api(BASE + '/settings', Object.assign({}, res.body, { confirmed: true }), 'PUT'); }, done: function (out) { return G.settingsDone(out); } });
  }

  // ------------------------------------------------------------------ ٥ · مراجعات القاموس (ما يقدّمه المتخصصون من الموقع)
  function rvFilters() { return { status: B.f('grst', 'pending'), kind: B.f('grk', 'all') }; }
  function rvCols() {
    return [
      { h: 'المراجعة', c: function (r) { return '<b class="sh-t">' + esc(r.title) + '</b><span class="sh-sub">' + esc(r.kindText) + '</span><span class="sh-sub">' + bdi(r.name) + '، ' + bdi(r.specialtyText) + '</span>'; } },
      { h: 'رأيه', c: function (r) { return Kit.pill(r.verdictText, r.suggests ? 'gold' : 'green') + (r.text ? '<span class="sh-sub">' + esc(G.arDigits(r.text.length > 90 ? r.text.slice(0, 90) + '…' : r.text)) + '</span>' : ''); } },
      { h: 'الحالة', c: function (r) { return Kit.pill(r.statusText, r.pending ? 'gold' : (r.status === 'approved' ? 'green' : '')) + (r.createdOn ? '<span class="sh-sub">' + esc(r.createdOn) + '</span>' : '') + (r.termChanged && r.pending ? '<span class="sh-sub">تغيّر المصطلح بعدها</span>' : ''); } }
    ];
  }
  function rvActs(r) {
    var id = ' data-id="' + esc(r.id) + '"';
    return '<button type="button" class="ep-b2" data-a="rvopen"' + id + '>افتح</button>'
      + (r.pending ? '<button type="button" class="ep-b1" data-a="rvok"' + id + '>' + esc(G.approveLabel(r)) + '</button><button type="button" class="ep-bs" data-a="rvno"' + id + '>ارفض</button>' : '');
  }
  function rvListBody(v, f) {
    var rows = G.filterReviews(v.rows, f);
    if (!v.rows.length) return B.empty('لا مراجعات بعد', 'تصلك هنا مراجعات المتخصصين حين يرسلونها من صفحة المصطلح على الموقع');
    if (!rows.length) return f.status === 'pending' && f.kind === 'all' ? B.empty('لا مراجعات تنتظر قرارك', 'كل ما وصل تم البتّ فيه') : B.empty('لا مراجعات تطابق اختيارك', 'غيّر الاختيار لتراها');
    return '<p class="sh-count">' + esc(G.reviewCountText(rows.length)) + '</p>' + B.list(rows, rvCols(), rvActs);
  }
  function screenReviews() {
    B.need(P.all);
    if (!reviewsOn()) return termsView() ? offScreen('مراجعات القاموس', 'content') : { title: 'مراجعات القاموس', sub: '', img: 'content', html: B.stateBlock(P.all, 'المصطلحات') };
    B.need(P.reviews);
    var v = reviewsView(), f = rvFilters(), body;
    if (!v) body = B.stateBlock(P.reviews, 'مراجعات القاموس');
    else {
      var c = v.counts;
      body = '<p class="sh-fine">متخصصون يؤكدون ترجمة مصطلح وتعريفه أو يقترحون تعديلًا من صفحة المصطلح على الموقع. «اعتمد» على تأكيد يختم المصطلح، وعلى اقتراح يفتح المحرّر ومعه الاقتراح. ولا يصل إلى صاحب المراجعة أي رد من هنا.</p>'
        + '<ul class="sh-nums" aria-label="أعداد المراجعات"><li><b>' + esc(ar(c.pending)) + '</b><span>تنتظر القرار</span></li><li><b>' + esc(ar(c.approved)) + '</b><span>اعتُمدت</span></li><li><b>' + esc(ar(c.rejected)) + '</b><span>رُفضت</span></li></ul>'
        + '<span class="sh-flabel">الحالة</span>' + B.chips('grst', G.REVIEW_STATUS_CHIPS, f.status)
        + '<span class="sh-flabel">النوع</span>' + B.chips('grk', G.REVIEW_KIND_CHIPS, f.kind)
        + '<div id="rvList">' + rvListBody(v, f) + '</div>';
    }
    return { title: 'مراجعات القاموس', sub: v ? (v.counts.pending ? G.reviewCountText(v.counts.pending) + ' تنتظر قرارك' : 'لا مراجعات تنتظر قرارك') : '', img: 'content', html: body };
  }
  function screenReview() {
    B.need(P.all);
    if (!reviewsOn()) return offScreen('مراجعة متخصص', 'content');
    B.need(P.reviews);
    var v = reviewsView(), rv = v ? reviewById(B.f('rvopen', '')) : null;
    var back = '<div class="sh-top"><button type="button" class="ep-bs" data-a="rvtolist">→ كل المراجعات</button></div>';
    if (!v) return { title: 'المراجعة', sub: '', img: 'content', html: back + B.stateBlock(P.reviews, 'المراجعة') };
    if (!rv) return { title: 'المراجعة', sub: '', img: 'content', html: back + B.empty('لم نجد هذه المراجعة', 'ربما تغيّرت. ارجع إلى القائمة.') };
    var id = ' data-id="' + esc(rv.id) + '"', t = rv.term;
    var main = '<div class="sh-panel g-term"><div class="g-top">' + Kit.pill(rv.kindText) + Kit.pill(rv.statusText, rv.pending ? 'gold' : (rv.status === 'approved' ? 'green' : '')) + Kit.pill(rv.verdictText, rv.suggests ? 'gold' : 'green') + '</div>'
      + '<h3 class="g-ar">' + esc(rv.title) + '</h3>'
      + line('المتخصص', bdi(rv.name)) + line('التخصص', bdi(rv.specialtyText))
      + line('للتواصل', '<bdi dir="ltr">' + esc(rv.email) + '</bdi>') + line('ظهور الاسم', esc(rv.showNameText))
      + (rv.createdOn ? line('وصلت في', esc(rv.createdOn)) : '')
      + (rv.text ? '<h4 class="g-h">' + (rv.suggests ? 'الاقتراح' : 'ملاحظته') + '</h4><p class="g-def">' + esc(G.arDigits(rv.text)) + '</p>' : '')
      + (rv.decidedOn ? line('البتّ فيها', esc(rv.decidedOn)) : '') + (rv.note ? line('ملاحظتك الخاصة', esc(G.arDigits(rv.note))) : '') + '</div>';
    var ctx = '';
    if (rv.isTerm) {
      ctx = t ? '<div class="sh-panel"><h3>المصطلح الآن</h3>' + line('الحالة', Kit.pill(t.statusText, stateClass(t)))
          + line('بالعربية', esc(t.ar)) + '<p class="g-line"><b>بالإنجليزية</b><span dir="ltr">' + esc(t.en) + '</span></p>' + (t.fr ? '<p class="g-line"><b>بالفرنسية</b><span dir="ltr">' + esc(t.fr) + '</span></p>' : '')
          + '<h4 class="g-h">التعريف</h4><p class="g-def">' + esc(G.arDigits(t.definition)) + '</p>'
          + (rv.termChanged ? '<p class="g-why" role="status">تغيّر نص المصطلح بعد وصول هذه المراجعة، فراجع النص الحالي قبل أن تقرّر.</p>' : '')
          + '<div class="sh-acts"><button type="button" class="ep-b2" data-a="gopen" data-id="' + esc(t.id) + '">افتح المصطلح</button></div></div>'
        : '<div class="sh-panel"><p class="sh-fine">لم نجد هذا المصطلح، ربما حُذف.</p></div>';
    }
    var acts = rv.pending ? '<div class="sh-panel"><h3>القرار</h3><div class="sh-acts"><button type="button" class="ep-b1" data-a="rvok"' + id + '>' + esc(G.approveLabel(rv)) + '</button><button type="button" class="ep-b2" data-a="rvno"' + id + '>ارفض</button></div></div>' : '';
    return { title: 'مراجعة متخصص', sub: rv.title, img: 'content', html: back + main + ctx + acts };
  }
  function approveFlow(rv) {
    B.flow({ title: rv.isTerm ? (rv.suggests ? 'اعتماد الاقتراح' : 'اعتماد المراجعة') : 'تمّت المراجعة', check: function () { return withDiff(G.approveCheck(rv)); },
      send: function () { return B.api(rvPath(rv, '/approve'), { confirmed: true }); }, done: function (out) { return G.approveDone(rv, out); },
      after: function () { if (rv.isTerm && rv.suggests && rv.termId) openSuggestion(rv); } });
  }
  function openSuggestion(rv) {
    B.set('gsug', G.suggestionView(rv)); B.set('gopen', String(rv.termId)); B.set('gfrom', 'reviews'); goSub('term');
    setTimeout(function () { var t = rowById(rv.termId); if (t) termFlow(t); }, 80);
  }
  function rejectFlow(rv) {
    B.flow({ title: 'رفض المراجعة', intro: 'يمكنك كتابة ملاحظة خاصة بك تُحفظ مع القرار ولا تصل إلى صاحب المراجعة.', init: { admin_note: '' }, nextLabel: 'راجع ثم ارفض',
      form: function (vals) { return fld('ملاحظة خاصة (اختيارية)', txt('admin_note', vals.admin_note, 3, G.NOTE_MAX), 'admin_note'); },
      check: function (vals) { return withDiff(G.rejectCheck(rv, vals)); },
      send: function (res) { return B.api(rvPath(rv, '/reject'), Object.assign({}, res.body, { confirmed: true })); }, done: function () { return G.rejectDone(); } });
  }

  // ------------------------------------------------------------------ التسجيل
  function rowAct(fn) { return function (b, a, id) { var r = rowById(id); if (r) fn(r); }; }
  B = Kit.board({
    key: 'glossary', mod: 'v2s_glossary', label: 'القاموس', lead: 'اختر ما تريد إدارته في القاموس',
    hub: function () { return HUB; }, tiles: tiles,
    screens: { terms: screenList('all'), wait: screenList('wait'), term: screenTerm, topics: screenTopics, reviews: screenReviews, review: screenReview, import: screenImport, rules: screenRules },
    act: {
      gopen: function (b, a, id) { b.set('gfrom', b.S.sub === 'wait' ? 'wait' : (b.S.sub === 'review' ? 'review' : (b.S.sub === 'term' ? b.f('gfrom', 'terms') : 'terms'))); b.set('gopen', String(id)); goSub('term'); },
      gtolist: function (b) { var from = b.f('gfrom', 'terms'); goSub(from === 'wait' ? 'wait' : (from === 'review' ? 'review' : (from === 'reviews' ? 'reviews' : 'terms'))); },
      gsugx: function (b) { b.set('gsug', null); b.redraw(); },
      rvopen: function (b, a, id) { b.set('rvopen', String(id)); goSub('review'); },
      rvtolist: function () { goSub('reviews'); },
      rvok: function (b, a, id) { var rv = reviewById(id); if (rv) approveFlow(rv); },
      rvno: function (b, a, id) { var rv = reviewById(id); if (rv) rejectFlow(rv); },
      gnew: function () { termFlow(null); },
      gedit: rowAct(termFlow),
      grev: rowAct(reviewFlow),
      gunrev: rowAct(unreviewFlow),
      gpub: rowAct(publishFlow),
      gunpub: rowAct(unpublishFlow),
      gdel: rowAct(deleteFlow),
      gattach: rowAct(attachFlow),
      gdetach: rowAct(detachFlow),
      gtopen: rowAct(openTopicFlow),
      gbprev: bulkPreview,
      gbgo: bulkFlow,
      gimport: function () { goSub('import'); },
      gsrc: function (b, a) { b.set('gimpSrc', a.getAttribute('data-v')); b.set('gimpPrev', null); b.set('gimpErr', ''); b.redraw(); },
      gprev: importPreview,
      ggo: importFlow,
      grules: rulesFlow,
      gwaitpub: function (b) { b.set('gst', 'under_review'); goSub('wait'); }
    }
  });
  window.V2S_GLOSSARY = B;
})();
