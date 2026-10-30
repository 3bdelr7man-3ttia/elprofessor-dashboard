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
  def('add', function (o) { R._o.push(o); });
  def('take', function (mod, v) {
    if (!window.V2_ON || !(window.V2SHELL && window.V2SHELL.on)) return false;
    for (var i = 0; i < R._o.length; i++) { if (R._o[i].take(mod, v)) return true; }
    return false;
  });
})();
