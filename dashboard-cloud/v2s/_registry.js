/* ============================================================================
 * سجلّ أقسام الداشبورد (الجولة النهائية): مكان واحد تسجّل فيه كل شاشة نفسها.
 * ⛔ يُحمَّل قبل أي ملف قسم. كل قسم يضيف `V2SEC.<key> = { owns(mod), render(mod, view) }`،
 *    و`index.html` يسأل `V2SEC.owner(mod)` فقط — لا خطّاف جديد لكل قسم.
 * `take/add` للشاشات القديمة اللي لها حارس يسأل السجلّ (الدورات).
 * الدوال المساعدة غير قابلة للعدّ (non-enumerable) فلا تظهر في التكرار على الأقسام.
 * ========================================================================== */
(function () {
  'use strict';
  var R = window.V2SEC = window.V2SEC || {};
  function def(name, fn) {
    try { Object.defineProperty(R, name, { value: fn, writable: true, configurable: true, enumerable: false }); }
    catch (e) { R[name] = fn; }
  }
  def('owner', function (mod) {
    for (var k in R) {
      var s = R[k];
      if (s && typeof s.owns === 'function') { try { if (s.owns(mod)) return s; } catch (e) {} }
    }
    return null;
  });
  def('_o', []);
  // ترويسة القسم: كل قسم يعطي السطر الذي تحت عنوانه من القائمة نفسها التي يرسمها (لا عدّ ثانٍ من مربّع اللوحة).
  // يرجع نصًّا، أو null فيُستعمل سطر المربّع. القسم الذي تعذّر مصدره يرجع «غير متاح بعد».
  def('head', function (key) {
    var cand = [R[key]];
    for (var i = 0; i < R._o.length; i++) { if (R._o[i] && R._o[i].key === key) cand.push(R._o[i]); }
    if (key === 'files' || key === 'disputes') cand.push(window.V2D2);
    if (key === 'books') cand.push(window.V2D3);
    for (var j = 0; j < cand.length; j++) {
      var c = cand[j];
      if (c && typeof c.head === 'function') {
        try { var h = c.head(key); if (typeof h === 'string' && h) return h; } catch (e) {}
      }
    }
    return null;
  });
  def('add', function (o) { R._o.push(o); });
  def('take', function (mod, v) {
    if (!window.V2_ON || !(window.V2SHELL && window.V2SHELL.on)) return false;
    for (var i = 0; i < R._o.length; i++) { if (R._o[i].take(mod, v)) return true; }
    return false;
  });
})();
