/* ============================================================
 * dashboard-api.js — يجعل الداش بورد الجديدة «حقيقة مش مجرد شكل».
 * يضيف: طبقة دخول حقيقية (JWT Bearer) + helper للشبكة + ربط 5 شاشات
 * بالـ Flask backend عبر نفس الأصل (/api/*). كل ما عداها يبقى على
 * بياناته التصميمية كما هو، بلا كسر.
 *
 * نموذج المصادقة (مطابق لـ backend/app.py):
 *   POST /api/auth/login {email,password} -> {token, user:{id,name,email,role,...}}
 *   كل طلب محمي: header  Authorization: Bearer <token>
 *   401 -> امسح التوكن واعرض شاشة الدخول.
 * التخزين: localStorage['token'] (نفس مفتاح تطبيق React على نفس الأصل)
 *   مع نسخة مرآة في 'ep_dash_token' حسب الطلب.
 * ============================================================ */
(function () {
  "use strict";

  // مصدر الـ API: نفس الأصل افتراضيًا (الداش بورد تُخدَّم من Flask).
  // يمكن تجاوزه عبر window.EP_API_BASE لو خُدِّمت من مضيف منفصل (nginx).
  var API_BASE = (window.EP_API_BASE || "/api").replace(/\/$/, "");
  var TOKEN_KEY = "token";
  var TOKEN_MIRROR = "ep_dash_token";

  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_MIRROR) || ""; }
    catch (e) { return ""; }
  }
  function setToken(t) {
    try { localStorage.setItem(TOKEN_KEY, t); localStorage.setItem(TOKEN_MIRROR, t); } catch (e) {}
  }
  function clearToken() {
    try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(TOKEN_MIRROR); } catch (e) {}
  }

  // ---- helper الشبكة الموحّد ----
  // api(path, opts) -> Promise<json>  (يرفض الوعد عند خطأ مع .status و .data)
  function api(path, opts) {
    opts = opts || {};
    var headers = { "Content-Type": "application/json" };
    var t = getToken();
    if (t) headers["Authorization"] = "Bearer " + t;
    if (opts.headers) for (var k in opts.headers) headers[k] = opts.headers[k];
    return fetch(API_BASE + path, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body != null ? (typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body)) : undefined,
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (r.status === 401) {
          // توكن مفقود/منتهٍ -> امسح واعرض الدخول.
          clearToken();
          EP.authed = false; EP.user = null;
          showLogin("انتهت الجلسة — برجاء تسجيل الدخول من جديد.");
          var err = new Error("unauthorized"); err.status = 401; err.data = data; throw err;
        }
        if (!r.ok) {
          var e2 = new Error((data && data.error) || ("HTTP " + r.status)); e2.status = r.status; e2.data = data; throw e2;
        }
        return data;
      });
    });
  }

  var get = function (p) { return api(p); };
  var post = function (p, d) { return api(p, { method: "POST", body: d || {} }); };

  // مساعدات صغيرة آمنة (تستخدم أدوات الصفحة عند توافرها).
  function note(msg) { try { (window.notify || window.toast || function () {})(msg); } catch (e) {} }
  function quietToast(msg) { try { (window.toast || function () {})(msg); } catch (e) {} }

  // ============================================================
  // طبقة بيانات الشاشات: حالة + تخزين + محمّلات
  // ============================================================
  var EP = {
    authed: false,
    user: null,
    data: { dashboard: null, metrics: null, users: null, content: null, finance: null, messages: null, inbox: null,
            escrow: null, investment: null, marketing: null, partners: null, courses: null, settings: null },
    state: {}, // 'idle' | 'loading' | 'ready' | 'error'
    _started: {}, // منع التحميل المزدوج
    api: api, get: get, post: post,
    requireAuth: true,
  };
  window.EP = EP;

  // ensure(key, rerender): يبدأ التحميل مرة واحدة، ويعيد الرسم عند الجهوز/الخطأ.
  EP.ensure = function (key, rerender) {
    if (!EP.authed) return;
    var st = EP.state[key] || "idle";
    // ابدأ التحميل مرة واحدة فقط (idle). لا تُعِد المحاولة تلقائيًّا على
    // 'error' أو 'loading' أو 'ready' — إعادة المحاولة تتم يدويًّا عبر EP.reload.
    if (st !== "idle") return;
    EP.reload(key, rerender);
  };
  EP.reload = function (key, rerender) {
    if (!EP.authed) return;
    EP.state[key] = "loading";
    if (rerender) try { rerender(); } catch (e) {} // اعرض حالة التحميل فورًا
    var loader = LOADERS[key];
    if (!loader) { EP.state[key] = "ready"; return; }
    loader().then(function () {
      EP.state[key] = "ready";
      if (rerender) try { rerender(); } catch (e) {}
    }).catch(function (err) {
      if (err && err.status === 401) return; // عولج في api()
      EP.state[key] = "error";
      if (rerender) try { rerender(); } catch (e) {}
    });
  };

  // تنسيق رقمي عربي آمن (السكربت الداخلي يعرّف money أيضًا؛ هذا احتياط لو سبق التحميل).
  function money(n) {
    if (typeof window.money === "function") { try { return window.money(n); } catch (e) {} }
    try { return Number(n || 0).toLocaleString("ar-EG"); } catch (e) { return String(n || 0); }
  }

  // مساعد تاريخ: هل خلال آخر 7 أيام؟
  function within7(iso) {
    if (!iso) return false;
    var t = Date.parse(iso); if (isNaN(t)) return false;
    return (Date.now() - t) < 7 * 24 * 3600e3;
  }
  function arDate(iso) {
    if (!iso) return "—";
    try {
      var d = new Date(iso);
      return new Intl.DateTimeFormat("ar-EG", { day: "numeric", month: "long" }).format(d);
    } catch (e) { return (iso || "").slice(0, 10); }
  }

  // ---- المحمّلات لكل شاشة ----
  var LOADERS = {
    // نظرة عامة: /api/dashboard (+ /api/platform-metrics لعدد المستخدمين الحيّ)
    dashboard: function () {
      var jobs = [ get("/dashboard").then(function (d) { EP.data.dashboard = d; }) ];
      // المقاييس متاحة للأدمن فقط؛ نتجاهل فشلها بهدوء.
      jobs.push(
        get("/platform-metrics").then(function (m) {
          // نطبّع عدد المستخدمين الحيّ.
          var total = (m && m.customers && (m.customers.total != null)) ? m.customers.total : null;
          EP.data.metrics = { total_users: total, raw: m };
        }).catch(function () { EP.data.metrics = null; })
      );
      return Promise.all(jobs);
    },

    // المستخدمون: /api/platform-users -> {users:[...], count}
    users: function () {
      return get("/platform-users").then(function (r) {
        var list = (r && r.users) || [];
        EP.data.users = { count: r && r.count, raw: list };
        // طبّع لشكل شاشة المستخدمين الموجود.
        var roleMap = { admin: "admin", staff: "staff", investor: "investor", member: "member" };
        var planLabel = { free: "مجانية", pro: "احترافية", premium: "بريميوم" };
        window.USERS = list.map(function (u) {
          var ts = (u.trainer_status || "none");
          return {
            id: u.id,
            platform: true,                 // علامة: مستخدم حقيقي من المنصة (يفعّل POST للدور)
            name: u.full_name || u.name || u.email || "—",
            email: u.email || "",
            phone: u.phone || "—",
            role: roleMap[u.role] || "member",
            trainer: ts === "approved" ? "approved" : (ts === "pending" ? "pending" : "none"),
            plan: planLabel[u.plan_id] || u.plan_id || "—",
            joined: arDate(u.created_at),
            last7: within7(u.created_at),
            // لا يوجد حقل توثيق مستقل في الجسر — نعتبر الأدمن/الموظف/المدرّب «موثّق».
            verified: (u.role === "admin" || u.role === "staff" || ts === "approved") ? "verified" : (ts === "pending" ? "pending" : "none"),
          };
        });
      });
    },

    // المحتوى: /api/content/articles/all -> {articles:[...]}
    content: function () {
      return get("/content/articles/all").then(function (r) {
        var arts = (r && r.articles) || [];
        EP.data.content = { raw: arts };
        window.TOPICS = arts.map(function (a) {
          return {
            aid: a.id,                      // مرجع المقال الحقيقي (يفعّل النشر/التعديل عبر الـ API)
            title: a.title || "بلا عنوان",
            by: a.by || "الإدارة",
            status: a.status === "published" ? "published" : "pending",
            views: 0,
            date: a.date || arDate(a.published_at),
            cat: a.cat || "قانوني",
            kicker: a.kicker || "مقال",
            excerpt: a.excerpt || "",
          };
        });
      });
    },

    // المالية: /api/finance/summary -> {total_revenue,total_expenses,monthly:[...]}
    finance: function () {
      return get("/finance/summary").then(function (s) {
        EP.data.finance = s;
        // ابنِ سلسلة الرسم الشهري (وارد/صادر بالألف) من البيانات الحيّة.
        if (Array.isArray(s.monthly) && s.monthly.length) {
          window.FMONTHLY = s.monthly.slice(-6).map(function (m) {
            return { m: (m.month || "").slice(5) || (m.month || ""), i: Math.round((m.revenue || 0) / 1000), o: Math.round((m.expenses || 0) / 1000) };
          });
        }
      });
    },

    // الرسائل: /api/messages -> [ {id,name,email,phone,topic,body,status,created_at} ]
    messages: function () {
      return get("/messages").then(function (r) {
        var list = Array.isArray(r) ? r : ((r && r.messages) || []);
        EP.data.messages = list.map(function (m) {
          return {
            id: m.id,
            name: m.name, email: m.email, phone: m.phone || "",
            topic: m.topic || "تواصل", body: m.body || "",
            status: m.status === "replied" ? "replied" : "new",
            at: m.created_at ? Date.parse(m.created_at) || Date.now() : Date.now(),
          };
        });
      });
    },

    // الوارد: نضخّ فيه طلبات المدربين + طلبات البرامج الحقيقية (مع approve/reject).
    inbox: function () {
      var jobs = [];
      var realRows = [];
      jobs.push(
        get("/platform-trainer-applications?status=pending").then(function (a) {
          var apps = (a && a.applications) || [];
          apps.forEach(function (ap) {
            realRows.push({
              out: "طلب انضمام كمدرّب", from: "درّب معنا", src: "cap", dest: "team",
              triage: "human", sla: "بوابة التوثيق", slaWarn: false,
              note: (ap.headline || "طلب مدرّب جديد") + " — اعتمد الصفة وحدّد نسبة الإيراد.",
              ref: "TRN-" + ap.id, who: ap.user_name || ap.full_name || ap.user_email || ap.email || "—",
              apiKind: "trainer", apiId: ap.id,
            });
          });
        }).catch(function () {})
      );
      jobs.push(
        get("/platform-program-requests?status=pending").then(function (a) {
          var reqs = (a && a.requests) || [];
          reqs.forEach(function (rq) {
            realRows.push({
              out: "طلب برنامج/دورة", from: "الدورات", src: "book", dest: "courses",
              triage: "human", sla: "اعتماد", slaWarn: false,
              note: "البرنامج: " + (rq.title || rq.program_id || "—") + " — اعتمد واربط الدورة.",
              ref: "PRG-" + rq.id, who: rq.user_name || rq.user_email || "—",
              apiKind: "program", apiId: rq.id,
            });
          });
        }).catch(function () {})
      );
      return Promise.all(jobs).then(function () {
        EP.data.inbox = realRows;
        // ادمج الصفوف الحقيقية في مقدمة الوارد التصميمي (مرة واحدة).
        if (Array.isArray(window.INBOX)) {
          var base = window.INBOX.filter(function (x) { return !x.apiKind; });
          window.INBOX = realRows.concat(base);
        }
      });
    },

    // الضمان والنزاعات: /api/escrow + /api/disputes + /api/escrow/metrics
    escrow: function () {
      var data = { sessions: [], disputes: [], released: [], metrics: null };
      var jobs = [];
      jobs.push(get("/escrow").then(function (r) {
        var list = Array.isArray(r) ? r : ((r && r.sessions) || []);
        // طبّع لشكل شاشة الضمان: held/confirm/dispute في «الجلسات»؛ released في «المُحرَّر».
        list.forEach(function (e) {
          var row = {
            id: e.id,
            student: e.student_name || e.student_email || "—",
            expert: e.expert_name || e.expert_email || "—",
            amount: e.amount || 0,
            currency: e.currency || "EGP",
            held: arDate(e.held_at),
            release: escReleaseLabel(e),
            status: e.status,
            commission: e.commission, net: e.net,
            sid: e.id, raw: e,
          };
          if (e.status === "released") {
            data.released.push({ id: e.id, expert: row.expert, amount: e.amount || 0, when: arDate(e.released_at), commission: e.commission, net: e.net });
          } else if (e.status === "refunded") {
            // المسترد لا يظهر في الجلسات النشطة ولا في المُحرَّر — نتجاهله بهدوء.
          } else {
            data.sessions.push(row);
          }
        });
      }));
      jobs.push(get("/disputes").then(function (r) {
        var list = Array.isArray(r) ? r : ((r && r.disputes) || []);
        // نأخذ النزاعات غير المفصولة فقط (decision == null) للعرض كـ«مفتوحة».
        list.filter(function (d) { return !d.decision; }).forEach(function (d) {
          data.disputes.push({
            id: d.id, session: d.session_id, party: d.party === "expert" ? "الخبير" : "الطالب",
            expert: "", reason: d.reason || "—", stage: d.stage || "open",
            amount: d.amount_frozen || 0, opened: arDate(d.opened_at),
            sla: d.decision_sla ? ("القرار قبل " + arDate(d.decision_sla)) : "—",
            warn: d.decision_sla ? (Date.parse(d.decision_sla) < Date.now()) : false,
            did: d.id, raw: d,
          });
        });
      }));
      jobs.push(get("/escrow/metrics").then(function (m) { data.metrics = m; }).catch(function () { data.metrics = null; }));
      return Promise.all(jobs).then(function () { EP.data.escrow = data; });
    },

    // الاستثمار: /api/investments + /api/investment-opportunities + /api/admin/withdrawals
    investment: function () {
      var data = { investors: [], opps: [], wd: [] };
      var jobs = [];
      jobs.push(get("/investments").then(function (r) {
        var list = Array.isArray(r) ? r : [];
        // اجمع حسب المستثمر لبناء صف «محفظة» واحد لكل اسم.
        var byName = {};
        list.forEach(function (it) {
          var nm = it.investor_name || "—";
          if (!byName[nm]) byName[nm] = { name: nm, balance: 0, invested: 0, returns: 0, level: "—", uid: it.investor_user_id };
          byName[nm].invested += Math.round(it.invested_total_egp || 0);
          byName[nm].returns += Math.round(it.due_egp || 0);
        });
        data.investors = Object.keys(byName).map(function (k) { return byName[k]; });
        data.raw = list;
      }));
      jobs.push(get("/investment-opportunities").then(function (r) {
        var list = Array.isArray(r) ? r : [];
        data.opps = list.map(function (o) {
          return {
            title: o.course_title || ("فرصة #" + o.id), target: Math.round(o.target_amount || 0),
            raised: Math.round(o.current_funded || 0), roi: (o.expected_roi != null ? o.expected_roi + "٪" : "—"),
            oid: o.id, raw: o,
          };
        });
      }));
      // السحوبات للأدمن فقط — نتجاهل فشلها (403) بهدوء.
      jobs.push(get("/admin/withdrawals").then(function (r) {
        var list = Array.isArray(r) ? r : [];
        data.wd = list.filter(function (w) { return w.status === "pending"; }).map(function (w) {
          return { who: w.investor_name || "—", amount: Math.round(w.amount_egp || w.amount || 0), status: w.status, when: arDate(w.requested_at), wid: w.id, raw: w };
        });
      }).catch(function () { data.wd = []; }));
      return Promise.all(jobs).then(function () { EP.data.investment = data; });
    },

    // التسويق: /api/campaigns
    marketing: function () {
      return get("/campaigns").then(function (r) {
        var list = Array.isArray(r) ? r : [];
        EP.data.marketing = {
          campaigns: list.map(function (c) {
            return {
              id: c.id, name: c.name || "حملة", platform: c.platform || "منصة",
              spent: Math.round(c.spent || 0), leads: c.leads || 0,
              cac: Math.round(c.cac || 0), status: c.status === "active" ? "active" : "paused",
              budget: Math.round(c.budget || 0), impressions: c.impressions || 0, clicks: c.clicks || 0,
              conversions: c.conversions || 0, revenue: Math.round(c.revenue_attributed || 0),
              course_id: c.course_id, audience: c.target_audience || "", cid: c.id, raw: c,
            };
          }),
        };
      });
    },

    // الشركاء: /api/partners (+ payouts متاحة لو احتجناها لاحقًا)
    partners: function () {
      return get("/partners").then(function (r) {
        var list = Array.isArray(r) ? r : [];
        var colors = ["var(--human)", "var(--ai)", "var(--gold)", "var(--memory)", "var(--agree)", "var(--navy)"];
        EP.data.partners = {
          partners: list.map(function (p, i) {
            return {
              id: p.id, name: p.name || "شريك", role: p.role || "شريك",
              equity: p.equity_percent || 0, invested: Math.round(p.total_capital_egp || p.capital_egp || 0),
              c: colors[i % colors.length], pid: p.id, raw: p,
            };
          }),
        };
      });
    },

    // الدورات: /api/courses
    courses: function () {
      return get("/courses").then(function (r) {
        var list = Array.isArray(r) ? r : [];
        EP.data.courses = {
          courses: list.map(function (c) {
            var split = c.revenue_split || {};
            var trainerPct = Math.round(split.trainer_percent || 0);
            return {
              id: c.id, title: c.title || "دورة", inst: c.trainer_name || "—",
              enrolled: c.students_count || 0,
              price: (c.price_egp || c.price_usd) ? "مدفوعة" : "مجانية",
              from: (c.price_egp ? (money(c.price_egp) + " ج") : (c.price_usd ? ("$" + c.price_usd) : "مجانية")),
              priceNum: c.price_egp || 0, rate: trainerPct,
              owner: (c.trainer_name && trainerPct) ? "trainer" : "platform",
              status: c.status === "active" ? "published" : (c.status === "draft" ? "draft" : "published"),
              lms_synced: !!c.lms_synced, total_revenue: c.total_revenue || 0, cid: c.id, raw: c,
            };
          }),
        };
      });
    },

    // الإعدادات: /api/settings -> {key:value}
    settings: function () {
      return get("/settings").then(function (s) { EP.data.settings = s || {}; });
    },
  };

  // وصف مهلة التحرير لجلسة ضمان (نص عربي قريب من التصميم).
  function escReleaseLabel(e) {
    if (e.status === "dispute") return "مجمّد — نزاع مفتوح";
    if (e.status === "released") return "حُرِّر " + arDate(e.released_at);
    if (e.status === "refunded") return "مسترد للطالب";
    var secs = e.release_seconds_remaining;
    if (secs == null) return "بانتظار تأكيد الطالب";
    if (secs <= 0) return "حان وقت التحرير التلقائي";
    var hrs = Math.round(secs / 3600);
    return "باقٍ " + hrs + "س — تحرير تلقائي";
  }

  // ============================================================
  // إجراءات الكتابة (تُستدعى من معالجات الواجهة الموجودة)
  // ============================================================

  // تغيير دور مستخدم منصة: POST /platform-users/<id>/role {role, email}
  // roleMap عكسي: شاشة الكلاود تستخدم نفس القيم (admin/staff/member/investor).
  EP.setUserRole = function (u, rid, prev, after) {
    post("/platform-users/" + u.id + "/role", { role: rid, email: u.email })
      .then(function () { note("تم تغيير دور " + u.name + " إلى الدور الجديد"); EP.reload("users", after); })
      .catch(function (e) {
        u.role = prev; // تراجع بصري
        quietToast((e && e.message) || "تعذّر تغيير الدور");
        if (after) after();
      });
  };

  // اعتماد بند وارد حقيقي (مدرّب/برنامج)
  EP.decideInboxItem = function (i, action, after) {
    var path = i.apiKind === "trainer"
      ? "/platform-trainer-applications/" + i.apiId + "/" + action
      : "/platform-program-requests/" + i.apiId + "/" + action;
    post(path, { admin_note: "" })
      .then(function () { note(action === "approve" ? "تم الاعتماد ✓" : "تم الرفض"); EP.reload("inbox", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر تنفيذ العملية"); if (after) after(); });
  };

  // المحتوى: إنشاء/نشر/تعديل
  EP.createArticle = function (g, publish, after) {
    post("/content/articles", { title: g.t, cat: g.cat, kicker: g.k, excerpt: g.ex, by: g.by })
      .then(function (a) {
        if (publish && a && a.id) return post("/content/articles/" + a.id + "/publish", {});
        return a;
      })
      .then(function () { note(publish ? "نُشر «" + g.t + "» على الموقع" : "أُنشئ مقال «" + g.t + "» كمسودّة"); EP.reload("content", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر حفظ المقال"); if (after) after(); });
  };
  EP.updateArticle = function (t, g, after) {
    api("/content/articles/" + t.aid, { method: "PUT", body: { title: g.t, cat: g.cat, kicker: g.k, excerpt: g.ex, by: g.by } })
      .then(function () { note("حُدّث «" + g.t + "»"); EP.reload("content", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر التحديث"); if (after) after(); });
  };
  EP.publishArticle = function (t, after) {
    post("/content/articles/" + t.aid + "/publish", {})
      .then(function () { note("نُشر «" + t.title + "» على الموقع — elprofessor.net"); EP.reload("content", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر النشر"); if (after) after(); });
  };
  EP.unpublishArticle = function (t, after) {
    api("/content/articles/" + t.aid, { method: "PUT", body: { status: "draft" } })
      .then(function () { note("أُلغي نشر «" + t.title + "»"); EP.reload("content", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر إلغاء النشر"); if (after) after(); });
  };

  // الرسائل: رد (يحتاج نص) + حذف
  EP.replyMessage = function (m, after) {
    var body = window.prompt("اكتب نص الرد على «" + m.name + "»:", "");
    if (body == null) { if (after) after(); return; }
    body = String(body).trim();
    if (!body) { quietToast("نص الرد مطلوب"); if (after) after(); return; }
    post("/messages/" + m.id + "/reply", { body: body })
      .then(function () { note("تم الرد على رسالة «" + m.name + "»"); EP.reload("messages", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر إرسال الرد"); if (after) after(); });
  };
  EP.deleteMessage = function (m, after) {
    api("/messages/" + m.id, { method: "DELETE" })
      .then(function () { note("حُذفت الرسالة"); EP.reload("messages", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر الحذف"); if (after) after(); });
  };

  // ---- الضمان والنزاعات ----
  EP.escrowRelease = function (sid, after) {
    post("/escrow/" + sid + "/release", {})
      .then(function (r) { note((r && r.message) || "تم التحرير للخبير"); EP.reload("escrow", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر التحرير"); if (after) after(); });
  };
  EP.escrowRefund = function (sid, after) {
    post("/escrow/" + sid + "/refund", {})
      .then(function (r) { note((r && r.message) || "تم الاسترداد للطالب"); EP.reload("escrow", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر الاسترداد"); if (after) after(); });
  };
  EP.escrowOpenDispute = function (sid, after) {
    var party = window.prompt("الطرف المُحتج؟ اكتب student أو expert:", "student");
    if (party == null) { if (after) after(); return; }
    party = String(party).trim().toLowerCase();
    if (party !== "student" && party !== "expert") { quietToast("الطرف يجب أن يكون student أو expert"); if (after) after(); return; }
    var reason = window.prompt("سبب النزاع (اختياري):", "") || "";
    post("/escrow/" + sid + "/dispute", { party: party, reason: reason })
      .then(function (r) { note((r && r.message) || "فُتح نزاع وجُمّد المبلغ"); EP.reload("escrow", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر فتح النزاع"); if (after) after(); });
  };
  EP.disputeResolve = function (did, decision, after) {
    var body = { decision: decision };
    if (decision === "split") {
      var pct = window.prompt("نسبة حصة الخبير من المبلغ (0-100):", "50");
      if (pct == null) { if (after) after(); return; }
      var n = parseFloat(pct);
      if (isNaN(n) || n < 0 || n > 100) { quietToast("النسبة يجب أن تكون بين 0 و 100"); if (after) after(); return; }
      body.split_pct = n;
    }
    post("/dispute/" + did + "/resolve", body)
      .then(function (r) { note((r && r.message) || "تم فصل النزاع"); EP.reload("escrow", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر فصل النزاع"); if (after) after(); });
  };
  EP.escrowProcessAuto = function (after) {
    post("/escrow/process-auto-releases", {})
      .then(function (r) { note((r && r.message) || "تم التحرير التلقائي"); EP.reload("escrow", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر التحرير التلقائي"); if (after) after(); });
  };

  // ---- التسويق (حملات) ----
  EP.createCampaign = function (d, after) {
    post("/campaigns", d)
      .then(function () { note("أُنشئت حملة «" + (d.name || "") + "»"); EP.reload("marketing", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر إنشاء الحملة"); if (after) after(); });
  };
  EP.updateCampaign = function (id, d, after) {
    api("/campaigns/" + id, { method: "PUT", body: d })
      .then(function () { note("حُدّثت الحملة"); EP.reload("marketing", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر التحديث"); if (after) after(); });
  };
  EP.deleteCampaign = function (id, after) {
    api("/campaigns/" + id, { method: "DELETE" })
      .then(function () { note("حُذفت الحملة"); EP.reload("marketing", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر الحذف"); if (after) after(); });
  };

  // ---- الشركاء ----
  EP.createPartner = function (d, after) {
    post("/partners", d)
      .then(function () { note("أُضيف الشريك «" + (d.name || "") + "»"); EP.reload("partners", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر إضافة الشريك"); if (after) after(); });
  };
  EP.updatePartner = function (id, d, after) {
    api("/partners/" + id, { method: "PUT", body: d })
      .then(function () { note("حُدّث الشريك"); EP.reload("partners", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر التحديث"); if (after) after(); });
  };
  EP.deletePartner = function (id, after) {
    api("/partners/" + id, { method: "DELETE" })
      .then(function () { note("حُذف الشريك"); EP.reload("partners", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر الحذف"); if (after) after(); });
  };

  // ---- الاستثمار ----
  EP.createOpportunity = function (d, after) {
    post("/investment-opportunities", d)
      .then(function () { note("أُضيفت فرصة استثمار"); EP.reload("investment", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر إضافة الفرصة"); if (after) after(); });
  };
  EP.updateOpportunity = function (id, d, after) {
    api("/investment-opportunities/" + id, { method: "PUT", body: d })
      .then(function () { note("حُدّثت الفرصة"); EP.reload("investment", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر التحديث"); if (after) after(); });
  };
  EP.deleteOpportunity = function (id, after) {
    api("/investment-opportunities/" + id, { method: "DELETE" })
      .then(function () { note("حُذفت الفرصة"); EP.reload("investment", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر الحذف"); if (after) after(); });
  };
  EP.decideWithdrawal = function (id, status, after) {
    api("/admin/withdrawals/" + id, { method: "PUT", body: { status: status } })
      .then(function () { note(status === "approved" ? "تم اعتماد السحب" : "تم رفض السحب"); EP.reload("investment", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر تحديث طلب السحب"); if (after) after(); });
  };

  // ---- الدورات ----
  EP.createCourse = function (d, after) {
    post("/courses", d)
      .then(function () { note("أُضيفت دورة «" + (d.title || "") + "»"); EP.reload("courses", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر إنشاء الدورة"); if (after) after(); });
  };
  EP.updateCourse = function (id, d, after) {
    api("/courses/" + id, { method: "PUT", body: d })
      .then(function () { note("حُدّثت الدورة"); EP.reload("courses", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر التحديث"); if (after) after(); });
  };
  EP.syncCoursesLms = function (after) {
    post("/courses/sync-lms", {})
      .then(function (r) { note((r && r.message) || "تمت المزامنة من الأكاديمية"); EP.reload("courses", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّرت المزامنة"); if (after) after(); });
  };
  EP.createLmsCourse = function (d, after) {
    post("/courses/create-lms", d)
      .then(function (r) { note((r && r.message) || "أُنشئت الدورة على الأكاديمية"); EP.reload("courses", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر إنشاء الدورة"); if (after) after(); });
  };

  // ---- الإعدادات ----
  EP.saveSettings = function (d, after) {
    api("/settings", { method: "PUT", body: d })
      .then(function () { note("تم حفظ الإعدادات"); EP.reload("settings", after); })
      .catch(function (e) { quietToast((e && e.message) || "تعذّر حفظ الإعدادات"); if (after) after(); });
  };

  // ============================================================
  // شاشة الدخول (overlay على هوية البروفيسور)
  // ============================================================
  var MARK_SVG = '<svg viewBox="0 0 798 588" style="width:58%;height:58%"><path fill="#fff" d="M389 50 Q389 0 439 0 L672 0 Q762 0 762 90 L762 347 L675 347 L675 353 L572 353 L572 588 L496 588 L496 493 L462 493 L462 588 L386 588 L386 493 L302 493 L302 588 L228 588 L228 493 L201 493 L201 588 L104 588 L104 335 L76 335 L76 409 L0 409 L0 351 L40 351 L40 182 L108 182 L108 106 L389 106 Z"></path><path fill="#fff" d="M675 337 L762 337 L762 421 L798 421 L798 492 L675 492 Z"></path></svg>';

  function showLogin(msg) {
    var existing = document.getElementById("epLogin");
    if (existing) { if (msg) { var e0 = existing.querySelector(".err"); if (e0) { e0.textContent = msg; e0.classList.add("show"); } } return; }
    var ov = document.createElement("div");
    ov.className = "ep-login"; ov.id = "epLogin";
    ov.innerHTML =
      '<div class="card">' +
        '<div class="hd"><div class="mk">' + MARK_SVG + '</div><div><h1>البروفيسور</h1><span>غرفة التحكم — دخول</span></div></div>' +
        '<div class="bd">' +
          '<div class="ttl">تسجيل الدخول</div>' +
          '<div class="hint">ادخل ببيانات حسابك الإداري للوصول إلى غرفة العمليات.</div>' +
          '<div class="err' + (msg ? ' show' : '') + '" id="epLoginErr">' + (msg || "") + '</div>' +
          '<div class="lab">البريد الإلكتروني</div>' +
          '<input id="epEmail" type="email" inputmode="email" autocomplete="username" placeholder="admin@elprofessor.net" dir="ltr">' +
          '<div class="lab">كلمة المرور</div>' +
          '<input id="epPass" type="password" autocomplete="current-password" placeholder="••••••••" dir="ltr">' +
          '<button class="sub" id="epLoginBtn"><svg class="icon" viewBox="0 0 24 24" style="width:18px;height:18px"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5"/><path d="M15 12H3"/></svg><span>دخول</span></button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(ov);
    var emailEl = ov.querySelector("#epEmail");
    var passEl = ov.querySelector("#epPass");
    var btn = ov.querySelector("#epLoginBtn");
    var errEl = ov.querySelector("#epLoginErr");
    function showErr(t) { errEl.textContent = t; errEl.classList.add("show"); }
    function submit() {
      var email = (emailEl.value || "").trim();
      var pass = passEl.value || "";
      if (!email || !pass) { showErr("البريد وكلمة المرور مطلوبان."); return; }
      btn.disabled = true; btn.querySelector("span").textContent = "جارٍ الدخول…";
      post("/auth/login", { email: email, password: pass })
        .then(function (r) {
          if (!r || !r.token) throw new Error("استجابة غير متوقعة");
          setToken(r.token);
          EP.authed = true; EP.user = r.user || null;
          hideLogin();
          applyAccount(EP.user);
          boot();
        })
        .catch(function (e) {
          btn.disabled = false; btn.querySelector("span").textContent = "دخول";
          showErr((e && e.status === 401) ? "بيانات الدخول غير صحيحة." : ((e && e.message) || "تعذّر الاتصال بالخادم."));
        });
    }
    btn.onclick = submit;
    [emailEl, passEl].forEach(function (el) { el.addEventListener("keydown", function (ev) { if (ev.key === "Enter") submit(); }); });
    setTimeout(function () { emailEl.focus(); }, 30);
  }
  function hideLogin() { var ov = document.getElementById("epLogin"); if (ov) ov.remove(); }

  // اعرض اسم/دور المستخدم في تذييل القائمة + زر الخروج.
  function applyAccount(user) {
    if (!user) return;
    var nm = document.getElementById("meName");
    var rl = document.getElementById("meRole");
    var av = document.getElementById("meAv");
    if (nm) nm.textContent = user.name || user.email || "مستخدم";
    var roleAr = { admin: "أدمن — تحكم كامل", employee: "موظف متابعة", trainer: "مدرّب", investor: "مستثمر", viewer: "بانتظار التفعيل" };
    if (rl) rl.textContent = roleAr[user.role] || user.role || "";
    if (av) av.textContent = (user.name || user.email || "؟").trim().charAt(0) || "؟";
  }

  function logout() {
    clearToken();
    EP.authed = false; EP.user = null;
    EP.data = { dashboard: null, metrics: null, users: null, content: null, finance: null, messages: null, inbox: null };
    EP.state = {};
    window.location.reload();
  }

  // ============================================================
  // الإقلاع المحمي
  // ============================================================
  var _booted = false;
  function boot() {
    if (_booted) { return; }
    _booted = true;
    if (typeof window.EP_BOOT === "function") {
      try { window.EP_BOOT(); } catch (e) { console.error(e); }
    }
  }

  // اربط زر الخروج بمجرد توافر الـ DOM (السكربت الداخلي يبني التذييل لاحقًا،
  // لكنه موجود في الـ HTML الأصلي فعلًا).
  function wireLogout() {
    var b = document.getElementById("logoutBtn");
    if (b && !b._epWired) { b._epWired = true; b.onclick = logout; }
  }

  // نقطة البداية: ينفّذها السكربت الداخلي في نهايته (انظر EP_BOOT gate)،
  // لكننا نبدأ المصادقة هنا أيضًا في حال جهوز الـ DOM.
  EP.start = function () {
    wireLogout();
    if (getToken()) {
      // لدينا توكن — تحقّق منه عبر /auth/me قبل الإقلاع.
      EP.authed = true; // مبدئيًّا، سيُلغى عند 401
      get("/auth/me").then(function (me) {
        EP.user = me; applyAccount(me); boot();
      }).catch(function (e) {
        if (e && e.status === 401) { /* api() عرض الدخول بالفعل */ EP.authed = false; }
        else {
          // الخادم غير متاح — أقلع على البيانات التصميمية حتى لا نحجب اللوحة كليًّا.
          EP.user = null; boot();
          quietToast("تعذّر التحقق من الجلسة — عرض مؤقت بالبيانات التصميمية.");
        }
      });
    } else {
      EP.authed = false;
      showLogin("");
    }
  };

  // شغّل بعد اكتمال الـ DOM (السكربت الداخلي يلي هذا الملف ويبني الواجهة).
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { setTimeout(EP.start, 0); });
  } else {
    setTimeout(EP.start, 0);
  }
})();
