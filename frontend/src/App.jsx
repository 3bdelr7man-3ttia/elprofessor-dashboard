import { useState, useEffect, useCallback, createContext, useContext, Component } from "react";
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

// ============================================================
// CONFIG & API
// ============================================================
const API = import.meta.env.VITE_API_URL || "/api";
const BRAND = { navy: "#1A2B4A", navy2: "#101B2F", gold: "#D9B34C", amber: "#F2A93B", bg: "#F6F3EC", ink: "#172033" };
const COLORS = [BRAND.gold, BRAND.navy, "#2d8659", "#c0392b", "#8e44ad", "#1abc9c", BRAND.amber, "#5b6abf"];

const api = {
  token: null,
  async req(path, opts = {}) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const r = await fetch(`${API}${path}`, { ...opts, headers });
    if (r.status === 401) { this.token = null; localStorage.removeItem("token"); window.location.reload(); }
    const data = await r.json().catch(() => ({}));
    if (!r.ok && !data.error) data.error = "حدث خطأ في الاتصال بالسيرفر";
    return data;
  },
  get: (p) => api.req(p),
  post: (p, d) => api.req(p, { method: "POST", body: JSON.stringify(d) }),
  put: (p, d) => api.req(p, { method: "PUT", body: JSON.stringify(d) }),
  del: (p) => api.req(p, { method: "DELETE" }),
};

// ============================================================
// AUTH CONTEXT
// ============================================================
const AuthCtx = createContext(null);
function useAuth() { return useContext(AuthCtx); }

// ============================================================
// HELPERS
// ============================================================
const fmt = (n) => new Intl.NumberFormat("ar-EG").format(Math.round(n || 0));
const fmtUSD = (n) => `$${new Intl.NumberFormat("en").format(Math.round(n || 0))}`;
const usdFromEgp = (egp, rate = 50) => fmtUSD((Number(egp || 0)) / (Number(rate || 50) || 50));
const egpLabel = (egp) => `${fmt(egp)} ج.م`;
const safeArray = (value) => Array.isArray(value) ? value : [];
const safeObject = (value) => (value && typeof value === "object" && !Array.isArray(value) ? value : {});
const catLabels = { tools: "أدوات وبرمجيات", hosting: "استضافة", marketing: "تسويق", travel: "سفر عمل", legal: "قانوني", office: "مكتب", bank_fees: "رسوم بنكية", asset_rent: "إيجار أصول", course_delivery: "قاعة وتنفيذ دورة", trainer: "مدربين", supervisor: "إشراف تدريبي", affiliate: "أفلييت", influencer: "إنفلونسر", other: "أخرى" };
const srcLabels = { course: "دورة تدريبية", consulting: "استشارة", subscription: "اشتراك", other: "أخرى" };
const cashKindLabels = { capital_in: "ضخ رأس مال", cash_out: "سحب/صرف من الكاش", adjustment_in: "تسوية إضافة", adjustment_out: "تسوية خصم" };
const payoutRoleLabels = { trainer: "مدرب", supervisor: "مشرف تدريبي", affiliate: "أفلييت", influencer: "إنفلونسر", partner: "شريك", other: "أخرى" };
const platLabels = { google_ads: "Google Ads", facebook: "Facebook", instagram: "Instagram", linkedin: "LinkedIn", tiktok: "TikTok", other: "أخرى" };
const statusLabels = { draft: "مسودة", active: "نشطة", paused: "متوقفة", completed: "منتهية" };
const recLabels = { continue: "✅ استمر", optimize: "🔧 حسّن", stop: "🛑 أوقف", monitor: "👁 راقب" };
const recColors = { continue: "#2d8659", optimize: "#e8913a", stop: "#c0392b", monitor: "#5b6abf" };
const userRoleLabels = { admin: "أدمن", employee: "موظف (متابعة)", viewer: "مشاهدة فقط", training_supervisor: "مشرف تدريبي", trainer: "مدرب", investor: "مستثمر/معلن" };
const investmentStatusLabels = { accrued: "مستحق", paid: "مدفوع", pending: "قيد التسوية" };
const opportunityStatusLabels = { open: "مفتوح للجميع", hot: "طلب عالٍ", invite_only: "بطلب فقط", funded: "مكتمل التمويل", closed: "مغلق" };
const opportunityStatusColors = { open: "#059669", hot: BRAND.gold, invite_only: "#98A2B3", funded: BRAND.navy, closed: "#98A2B3" };
const CUTOFF_MONTH = "2026-06";
const CUTOFF_DATE = "2026-06-01";
const sumBy = (items, picker) => safeArray(items).reduce((sum, item) => sum + (Number(picker(item)) || 0), 0);
const monthLabel = (month) => {
  if (!month) return "—";
  const [year, monthNumber] = String(month).split("-").map(Number);
  const names = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
  return `${names[(monthNumber || 1) - 1]} ${year || ""}`.trim();
};
const quarterLabel = (month, operatingStart = CUTOFF_MONTH) => {
  if (!month) return "ربع غير محدد";
  const [year, monthNumber] = String(month).split("-").map(Number);
  const quarter = Math.floor(((monthNumber || 1) - 1) / 3) + 1;
  const note = month === operatingStart ? " • أول ربع تشغيلي" : "";
  return `Q${quarter} ${year}${note}`;
};
const isPreLaunchDate = (date) => !!date && date < CUTOFF_DATE;
const getEffectiveRole = (user) => user?.dashboard_role || user?.role || "viewer";
const buildQuarterGroups = (months) => {
  const rows = safeArray(months);
  const groups = [];
  for (let index = 0; index < rows.length; index += 3) {
    const chunk = rows.slice(index, index + 3);
    groups.push({
      id: `q-${index / 3 + 1}`,
      label: quarterLabel(chunk[0]?.month),
      months: chunk,
      totals: {
        revenue: sumBy(chunk, (item) => item.revenue),
        expenses: sumBy(chunk, (item) => item.expenses),
        profit: sumBy(chunk, (item) => item.profit),
      },
    });
  }
  return groups;
};
const createCalculatorForm = () => ({
  course_id: "",
  revenue_egp: "",
  students_count: 20,
  price_per_student: 2500,
  execution_cost_egp: 0,
  supervision_cost_egp: 2000,
  total_ads_budget_egp: 500 * 50,
  investor_contribution_egp: 100 * 50,
  trainer_percent: 35,
  platform_percent: 35,
  investor_percent: 30,
  affiliate_mode: "percent",
  affiliate_percent: 0,
  affiliate_fixed_egp: 0,
});
const resolveCurrencyPreference = (user) => ((user?.preferred_currency || "AUTO").toUpperCase() === "AUTO" ? "EGP" : (user?.preferred_currency || "AUTO").toUpperCase());
const primaryMoney = (egp, rate = 50, preference = "EGP") => preference === "USD" ? fmtUSD((Number(egp || 0)) / (Number(rate || 50) || 50)) : egpLabel(egp);
const secondaryMoney = (egp, rate = 50, preference = "EGP") => preference === "USD" ? egpLabel(egp) : fmtUSD((Number(egp || 0)) / (Number(rate || 50) || 50));
const progressPercent = (value, target) => !target ? 0 : Math.max(0, Math.min(100, (Number(value || 0) / Number(target || 1)) * 100));
const currentUserName = (user) => (user?.linked_to_name || user?.name || "").trim();

function useIsMobile(breakpoint = 960) {
  const [mobile, setMobile] = useState(() => typeof window !== "undefined" ? window.innerWidth <= breakpoint : false);
  useEffect(() => {
    const onResize = () => setMobile(window.innerWidth <= breakpoint);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [breakpoint]);
  return mobile;
}

// ============================================================
// COMPONENTS
// ============================================================

function KPICard({ label, value, sub, color = "#0f4c81", icon }) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, padding: "20px 24px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)", borderRight: `4px solid ${color}`, minWidth: 0 }}>
      <div style={{ fontSize: 13, color: "#667085", marginBottom: 6, fontWeight: 700 }}>{icon} {label}</div>
      <div style={{ fontSize: 26, fontWeight: 900, color, lineHeight: 1.2, fontFeatureSettings: '"tnum"' }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

// Live operational numbers synced FROM the main platform (customers, signups,
// enrollments, AI usage). Self-contained: silently hides if the sync isn't set up.
function PlatformMetricsPanel() {
  const [m, setM] = useState(null);
  useEffect(() => {
    let on = true;
    api.get("/platform-metrics").then(r => { if (on && r && !r.error) setM(r); }).catch(() => {});
    return () => { on = false; };
  }, []);
  if (!m) return null;
  const c = m.customers || {}, e = m.enrollments || {}, ai = m.ai_usage || {}, co = m.courses || {};
  return (
    <div style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 18, fontWeight: 900, color: BRAND.navy, marginBottom: 14 }}>أرقام المنصة (مزامنة مباشرة)</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
        <KPICard icon="👥" label="إجمالي العملاء" value={c.total ?? 0} sub={`${c.signups_30d ?? 0} تسجيل خلال 30 يوم`} color={BRAND.navy} />
        <KPICard icon="🆕" label="تسجيلات جديدة اليوم" value={c.signups_today ?? 0} sub={`${c.signups_7d ?? 0} خلال 7 أيام`} color="#2d8659" />
        <KPICard icon="🎓" label="الاشتراكات بالدورات" value={e.total ?? 0} sub={`${co.total ?? 0} دورة في الكتالوج`} color="#5b6abf" />
        <KPICard icon="🤖" label="استهلاك أدوات AI" value={ai.requests_total ?? 0} sub={`${ai.document_drafts_total ?? 0} مسودة محرّرة`} color="#8e44ad" />
      </div>
    </div>
  );
}

function Modal({ open, onClose, title, children, maxWidth = 560, width = "90%" }) {
  if (!open) return null;
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div style={{ background: "#fff", borderRadius: 16, padding: 32, maxWidth, width, maxHeight: "85vh", overflow: "auto", boxShadow: "0 20px 60px rgba(0,0,0,0.15)" }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#0f4c81" }}>{title}</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 22, cursor: "pointer", color: "#9ca3af" }}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Input({ label, ...props }) {
  const isNumber = props.type === "number";
  const handleFocus = (e) => {
    if (isNumber) {
      requestAnimationFrame(() => e.target.select());
    }
    props.onFocus?.(e);
  };
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 6 }}>{label}</label>
      <input {...props} onFocus={handleFocus} style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14, boxSizing: "border-box", ...props.style }} />
    </div>
  );
}

function Select({ label, options, ...props }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 6 }}>{label}</label>
      <select {...props} style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14, boxSizing: "border-box", background: "#fff" }}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

function CurrencyFields({ form, setForm, rate = 50, egpKey = "amount_egp", usdKey = "amount_usd", egpLabel = "المبلغ (ج.م)", usdLabel = "المبلغ ($)" }) {
  const egp = Number(form[egpKey] || 0);
  const usd = Number(form[usdKey] || 0);
  const active = usd ? "usd" : "egp";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
      <Input
        label={egpLabel}
        type="number"
        value={egp}
        onChange={e => setForm({ ...form, [egpKey]: +e.target.value, [usdKey]: 0 })}
        style={{ borderColor: active === "egp" ? BRAND.gold : "#d1d5db" }}
      />
      <Input
        label={usdLabel}
        type="number"
        value={usd}
        onChange={e => setForm({ ...form, [usdKey]: +e.target.value, [egpKey]: 0 })}
        style={{ borderColor: active === "usd" ? BRAND.gold : "#d1d5db" }}
      />
      <div style={{ gridColumn: "1 / -1", marginTop: -10, marginBottom: 8, fontSize: 12, color: "#667085" }}>
        المعادل: {usd ? `${fmt(usd * rate)} ج.م` : fmtUSD(egp / rate)} على سعر صرف {fmt(rate)} ج.م
      </div>
    </div>
  );
}

function Btn({ children, color = "#0f4c81", variant = "primary", ...props }) {
  const bg = variant === "primary" ? color : "transparent";
  const fg = variant === "primary" ? "#fff" : color;
  const border = variant === "primary" ? "none" : `2px solid ${color}`;
  return <button {...props} style={{ padding: "10px 24px", borderRadius: 8, background: bg, color: fg, border, fontSize: 14, fontWeight: 600, cursor: "pointer", ...props.style }}>{children}</button>;
}

function Badge({ text, color = "#0f4c81" }) {
  return <span style={{ display: "inline-block", padding: "3px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600, background: `${color}18`, color }}>{text}</span>;
}

function PageError({ message, onRetry }) {
  return (
    <div style={{ background: "#fff", borderRadius: 14, padding: 28, border: "1px solid #f2d7d5", color: "#7b241c", boxShadow: "0 1px 4px rgba(0,0,0,0.05)" }}>
      <div style={{ fontSize: 16, fontWeight: 900, marginBottom: 8 }}>تعذر تحميل الصفحة الآن</div>
      <div style={{ fontSize: 14, lineHeight: 1.8, marginBottom: 14 }}>{message || "حدثت مشكلة مؤقتة أثناء تحميل البيانات."}</div>
      <Btn onClick={onRetry} color="#c0392b">إعادة المحاولة</Btn>
    </div>
  );
}

class PageBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(error) {
    console.error("Page crash:", error);
  }
  componentDidUpdate(prevProps) {
    if (prevProps.pageKey !== this.props.pageKey && this.state.hasError) {
      this.setState({ hasError: false });
    }
  }
  render() {
    if (this.state.hasError) {
      return <PageError message="حصل خطأ أثناء فتح الصفحة. تم منع الشاشة البيضاء ويمكنك إعادة المحاولة أو الانتقال لصفحة أخرى." onRetry={() => this.setState({ hasError: false })} />;
    }
    return this.props.children;
  }
}

function TabBar({ tabs, active, onChange }) {
  return (
    <div style={{ display: "flex", gap: 0, borderBottom: "2px solid #e5e7eb", marginBottom: 24, overflowX: "auto", flexWrap: "wrap" }}>
      {tabs.map(t => (
        <button key={t.id} onClick={() => onChange(t.id)} style={{ padding: "12px 24px", background: "none", border: "none", borderBottom: active === t.id ? "3px solid #0f4c81" : "3px solid transparent", color: active === t.id ? "#0f4c81" : "#6b7280", fontWeight: active === t.id ? 700 : 500, fontSize: 15, cursor: "pointer", marginBottom: -2, whiteSpace: "nowrap" }}>{t.label}</button>
      ))}
    </div>
  );
}

// ============================================================
// LOGIN PAGE
// ============================================================
function LoginPage({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("admin@elprofessor.com");
  const [pass, setPass] = useState("admin123");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true); setErr(""); setMsg("");
    try {
      if (mode === "login") {
        const r = await api.post("/auth/login", { email, password: pass });
        if (r.error) { setErr(r.error); setLoading(false); return; }
        api.token = r.token;
        localStorage.setItem("token", r.token);
        onLogin(r.user);
      } else {
        const r = await api.post("/auth/register", { name, email, password: pass });
        if (r.error) { setErr(r.error); setLoading(false); return; }
        setMsg(r.message || "تم إنشاء الحساب، وستقوم الإدارة بتحديد دورك.");
        setMode("login");
        setName("");
      }
    } catch (e) { setErr("خطأ في الاتصال بالسيرفر"); }
    setLoading(false);
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: BRAND.bg, padding: 24 }}>
      <div style={{ background: "#fff", borderRadius: 20, padding: "48px 40px", width: 380, boxShadow: "0 20px 60px rgba(16,27,47,0.12)", border: "1px solid #E6D7A8" }}>
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div style={{ fontSize: 36, fontWeight: 900, color: BRAND.navy, marginBottom: 4 }}>البروفيسور</div>
          <div style={{ fontSize: 14, color: BRAND.gold, letterSpacing: 1, fontWeight: 800 }}>MANAGEMENT DASHBOARD</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, background: "#f8fafc", borderRadius: 12, padding: 6, marginBottom: 18 }}>
          <button onClick={() => { setMode("login"); setErr(""); setMsg(""); }} style={{ border: "none", borderRadius: 10, background: mode === "login" ? BRAND.navy : "transparent", color: mode === "login" ? "#fff" : "#475467", fontWeight: 800, padding: "10px 12px", cursor: "pointer" }}>تسجيل الدخول</button>
          <button onClick={() => { setMode("register"); setErr(""); setMsg(""); setEmail(""); setPass(""); }} style={{ border: "none", borderRadius: 10, background: mode === "register" ? BRAND.navy : "transparent", color: mode === "register" ? "#fff" : "#475467", fontWeight: 800, padding: "10px 12px", cursor: "pointer" }}>إنشاء حساب</button>
        </div>
        {mode === "register" && <Input label="الاسم" value={name} onChange={e => setName(e.target.value)} />}
        <Input label="البريد الإلكتروني" value={email} onChange={e => setEmail(e.target.value)} type="email" />
        <Input label="كلمة المرور" value={pass} onChange={e => setPass(e.target.value)} type="password" onKeyDown={e => e.key === "Enter" && submit()} />
        {msg && <div style={{ color: "#2d8659", fontSize: 13, marginBottom: 12, lineHeight: 1.7 }}>{msg}</div>}
        {err && <div style={{ color: "#c0392b", fontSize: 13, marginBottom: 12 }}>{err}</div>}
        <Btn onClick={submit} style={{ width: "100%", marginTop: 8, padding: 14, fontSize: 16 }} disabled={loading}>
          {loading ? (mode === "login" ? "جاري الدخول..." : "جاري إنشاء الحساب...") : (mode === "login" ? "تسجيل الدخول" : "إنشاء الحساب")}
        </Btn>
        <div style={{ marginTop: 12, fontSize: 12, color: "#667085", lineHeight: 1.8 }}>
          {mode === "login" ? "لو الحساب جديد، أنشئه أولًا ثم حدّد دوره من داخل الإعدادات كأدمن." : "بعد إنشاء الحساب، سيظهر للمشرف داخل الإعدادات ليحدد لك الدور المناسب وربطك بالمدرب أو المستثمر إن لزم."}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// EXECUTIVE OVERVIEW
// ============================================================
function OverviewPage({ onNavigate }) {
  const user = useAuth();
  const effectiveRole = getEffectiveRole(user);
  const [data, setData] = useState(null);
  const [roleData, setRoleData] = useState({ courses: [], payouts: [], investments: [] });
  const load = () => api.get("/dashboard").then(setData);
  const loadRoleData = () => Promise.all([
    api.get("/courses"),
    api.get("/payouts"),
    api.get("/investments"),
  ]).then(([courses, payouts, investments]) => setRoleData({ courses: safeArray(courses), payouts: safeArray(payouts), investments: safeArray(investments) }));
  useEffect(() => {
    if (effectiveRole === "trainer" || effectiveRole === "investor") loadRoleData();
    else load();
  }, [effectiveRole]);

  if ((effectiveRole === "trainer" || effectiveRole === "investor") && !roleData) return <PageLoader />;
  if (effectiveRole !== "trainer" && effectiveRole !== "investor" && !data) return <PageLoader />;
  if (effectiveRole !== "trainer" && effectiveRole !== "investor" && (data.error || !data.financial)) return <PageError message={data.error} onRetry={load} />;

  if (effectiveRole === "viewer") {
    return (
      <div>
        <h1 style={{ fontSize: 26, fontWeight: 900, color: BRAND.navy, marginBottom: 24 }}>بانتظار التفعيل</h1>
        <PageSection title="تم إنشاء الحساب بنجاح">
          <div style={{ fontSize: 14, color: "#475467", lineHeight: 1.9 }}>
            حسابك موجود الآن داخل الداشبورد، والخطوة التالية أن يقوم الأدمن بتحديد الدور المناسب لك من صفحة المستخدمين.
            بعد تفعيل الدور ستظهر لك الصفحات والبيانات المرتبطة بك تلقائيًا.
          </div>
        </PageSection>
      </div>
    );
  }

  if (effectiveRole === "trainer") {
    const courses = roleData.courses;
    const payouts = roleData.payouts;
    const totalStudents = courses.reduce((sum, course) => sum + (course.students_count || 0), 0);
    const accrued = payouts.reduce((sum, item) => sum + (item.status !== "paid" ? (item.total_egp || 0) : 0), 0);
    const paid = payouts.reduce((sum, item) => sum + (item.status === "paid" ? (item.total_egp || 0) : 0), 0);
    return (
      <div>
        <h1 style={{ fontSize: 26, fontWeight: 900, color: BRAND.navy, marginBottom: 24 }}>لوحتي</h1>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 24 }}>
          <KPICard icon="🎓" label="عدد دوراتي" value={courses.length} color="#1abc9c" />
          <KPICard icon="👨‍🎓" label="إجمالي طلابي" value={totalStudents} color="#5b6abf" />
          <KPICard icon="💰" label="أرباحي المستحقة" value={usdFromEgp(accrued, 50)} sub={egpLabel(accrued)} color="#8e44ad" />
          <KPICard icon="✅" label="أرباح مدفوعة" value={usdFromEgp(paid, 50)} sub={egpLabel(paid)} color="#2d8659" />
        </div>
        <PageSection title="آخر العمليات المرتبطة بدوراتي">
          {payouts.length ? payouts.slice(0, 6).map(item => <div key={item.id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderTop: "1px solid #f3f4f6", fontSize: 13 }}><div><strong>{item.related_to || item.name}</strong><div style={{ color: "#667085", marginTop: 4 }}>{item.date}</div></div><div style={{ fontWeight: 900, color: item.status === "paid" ? "#2d8659" : "#8e44ad" }}>{egpLabel(item.total_egp)}</div></div>) : <EmptyState title="لا توجد مستحقات بعد" text="عند ربطك بدورات ومستحقات ستظهر هنا." />}
        </PageSection>
      </div>
    );
  }

  if (effectiveRole === "investor") {
    const investments = roleData.investments;
    const totalInvested = investments.reduce((sum, item) => sum + (item.invested_total_egp || 0), 0);
    const totalDue = investments.reduce((sum, item) => sum + (item.due_egp || 0), 0);
    const avgRoi = investments.length ? investments.reduce((sum, item) => sum + (item.roi_percent || 0), 0) / investments.length : 0;
    return (
      <div>
        <h1 style={{ fontSize: 26, fontWeight: 900, color: BRAND.navy, marginBottom: 24 }}>لوحتي</h1>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 24 }}>
          <KPICard icon="🏦" label="إجمالي استثماراتي" value={usdFromEgp(totalInvested, 50)} sub={egpLabel(totalInvested)} color={BRAND.navy} />
          <KPICard icon="💵" label="إجمالي عوائدي" value={usdFromEgp(totalDue, 50)} sub={egpLabel(totalDue)} color="#2d8659" />
          <KPICard icon="📈" label="ROI" value={`${avgRoi.toFixed(1)}%`} color={BRAND.gold} />
          <KPICard icon="📚" label="عدد الدورات المشارك فيها" value={new Set(investments.map(item => item.course_id)).size} color="#8e44ad" />
        </div>
        <PageSection title="استثماراتي الأخيرة">
          {investments.length ? investments.slice(0, 6).map(item => <div key={item.id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderTop: "1px solid #f3f4f6", fontSize: 13 }}><div><strong>{item.course_title}</strong><div style={{ color: "#667085", marginTop: 4 }}>{item.profit_percent}% من أرباح الدورة</div></div><div style={{ textAlign: "left" }}><div style={{ fontWeight: 900, color: "#2d8659" }}>{egpLabel(item.due_egp)}</div><div style={{ color: "#94a3b8", fontSize: 12 }}>{item.roi_percent}% ROI</div></div></div>) : <EmptyState title="لا توجد استثمارات بعد" text="عند إضافة استثمارات مرتبطة بك ستظهر هنا." />}
        </PageSection>
      </div>
    );
  }

  const f = data.financial || {};
  const m = data.marketing || { total_ad_spend: 0, total_leads: 0 };
  const monthly = data.monthly;
  const forecast = data.forecast;
  const alerts = data.alerts;
  const recent = data.recent;
  const partners = data.partners;
  const periods = data.periods;
  const rate = data.exchange_rate;
  const monthlyRows = safeArray(monthly);
  const forecastRows = safeArray(forecast);
  const recentRows = safeArray(recent).slice(0, 6);
  const partnerRows = safeArray(partners);

  return (
    <div>
      <h1 style={{ fontSize: 26, fontWeight: 900, color: BRAND.navy, marginBottom: 24 }}>نظرة عامة تنفيذية</h1>

      <PlatformMetricsPanel />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 28 }}>
        <KPICard icon="💰" label="إيرادات تشغيلية" value={usdFromEgp(f.total_revenue, rate)} sub={`${egpLabel(f.total_revenue)} من الدورات والاستشارات فقط`} color="#2d8659" />
        <KPICard icon="🏦" label="Cash Flow متاح" value={fmtUSD(f.cash_balance_usd)} sub={`${fmt(f.cash_balance)} ج.م رأس مال تشغيل`} color={BRAND.navy} />
        <KPICard icon="🏗️" label={`تأسيس قبل ${periods?.cutoff_month || "2026-06"}`} value={usdFromEgp(f.pre_launch_expenses, rate)} sub={`${egpLabel(f.pre_launch_expenses)} | حركة خام: ${egpLabel(f.raw_bank_expenses)}`} color="#c0392b" />
        <KPICard icon="📊" label="صافي التشغيل من يونيو" value={usdFromEgp(f.operating_net, rate)} sub={`${egpLabel(f.operating_net)} | مصروفات التشغيل: ${egpLabel(f.operating_expenses)}`} color={f.operating_net >= 0 ? "#2d8659" : "#c0392b"} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 28 }}>
        <KPICard icon="🎯" label="Target الشهر القادم" value={usdFromEgp(f.next_month_target, rate)} sub={`${egpLabel(f.next_month_target)}${f.break_even_month ? ` | Break-even: ${f.break_even_month}` : ""}`} color={BRAND.gold} />
        <KPICard icon="💼" label="القيمة المرجعية لأصول الشركاء" value={usdFromEgp(f.total_assets, rate)} sub={`${egpLabel(f.total_assets)} | إيجار مستخدم هذا الشهر: ${egpLabel(f.monthly_asset_rent)}`} color={BRAND.navy} />
        <KPICard icon="🤝" label="مستحقات مدربين/إشراف" value={usdFromEgp(f.payout_cost, rate)} sub={`${egpLabel(f.payout_cost)} ضمن تكلفة التشغيل والدورات`} color="#8e44ad" />
        <KPICard icon="📢" label="الإنفاق التسويقي" value={fmtUSD(m.total_ad_spend)} sub={`${m.total_leads} عميل محتمل`} color="#e8913a" />
      </div>

      {safeArray(alerts).length > 0 && (
        <div style={{ background: "#fef3c7", borderRadius: 12, padding: 16, marginBottom: 24, border: "1px solid #f59e0b" }}>
          <div style={{ fontWeight: 700, color: "#92400e", marginBottom: 8 }}>⚠️ تنبيهات</div>
          {safeArray(alerts).map((a, i) => <div key={i} style={{ fontSize: 14, color: "#92400e", marginBottom: 4 }}>• {a.message}</div>)}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <h3 style={{ fontSize: 16, fontWeight: 900, color: BRAND.navy, marginBottom: 16 }}>الواقع مقابل المستهدف</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={(forecastRows.length ? forecastRows : monthlyRows).map((x, i) => ({ ...x, actualRevenue: monthlyRows[i]?.revenue || 0, actualExpenses: monthlyRows[i]?.expenses || 0 }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
              <Tooltip formatter={(v) => `${fmt(v)} ج.م`} />
              <Legend />
              <Bar dataKey="revenue" name="Target Revenue" fill={BRAND.gold} radius={[4,4,0,0]} />
              <Bar dataKey="expenses" name="Target Spend" fill="#C97C30" radius={[4,4,0,0]} />
              <Bar dataKey="actualRevenue" name="Actual Revenue" fill="#2d8659" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: "#374151", marginBottom: 16 }}>آخر العمليات</h3>
          {partnerRows.length > 0 && <div style={{ marginBottom: 14, paddingBottom: 12, borderBottom: "1px solid #f3f4f6" }}>
            <div style={{ fontSize: 12, color: "#667085", marginBottom: 8, fontWeight: 800 }}>الشركاء</div>
            {partnerRows.slice(0, 3).map(p => <div key={p.name} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "4px 0" }}><strong>{p.name}</strong><span>{p.equity_percent}%</span></div>)}
            <button onClick={() => onNavigate?.("team")} style={{ marginTop: 8, background: "none", border: "none", color: BRAND.navy, fontWeight: 800, cursor: "pointer", padding: 0 }}>عرض الكل</button>
          </div>}
          {recentRows.map((t, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: i < recentRows.length - 1 ? "1px solid #f3f4f6" : "none" }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#374151" }}>{t.desc?.substring(0, 35)}</div>
                <div style={{ fontSize: 11, color: "#9ca3af" }}>{t.date}</div>
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: t.amount >= 0 ? "#2d8659" : "#c0392b" }}>
                {t.amount >= 0 ? "+" : ""}{fmt(t.amount)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// FINANCIAL DASHBOARD
// ============================================================
function useFinanceData() {
  const [state, setState] = useState({
    loading: true,
    error: "",
    revenues: [],
    expenses: [],
    assets: [],
    forecast: [],
    cashflow: { transactions: [], balance_usd: 0, balance_egp: 0, capital_in: 0, cash_out: 0 },
    partners: [],
    payouts: [],
    summary: null,
  });

  const load = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: "" }));
    try {
      const [revenues, expenses, assets, forecast, cashflow, partners, payouts, summary] = await Promise.all([
        api.get("/revenues"),
        api.get("/expenses"),
        api.get("/assets"),
        api.get("/forecast"),
        api.get("/cashflow"),
        api.get("/partners"),
        api.get("/payouts"),
        api.get("/finance/summary"),
      ]);
      const fatalError = summary?.error || revenues?.error || expenses?.error || assets?.error || forecast?.error || cashflow?.error || partners?.error || payouts?.error;
      setState({
        loading: false,
        error: fatalError || "",
        revenues: safeArray(revenues),
        expenses: safeArray(expenses),
        assets: safeArray(assets),
        forecast: safeArray(forecast),
        cashflow: cashflow?.transactions ? cashflow : { transactions: [], balance_usd: 0, balance_egp: 0, capital_in: 0, cash_out: 0 },
        partners: safeArray(partners),
        payouts: safeArray(payouts),
        summary: safeObject(summary),
      });
    } catch {
      setState(prev => ({ ...prev, loading: false, error: "تعذر تحميل البيانات المالية حاليًا." }));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: load };
}

function PageSection({ title, subtitle, action, children }) {
  return (
    <div style={{ background: "#fff", borderRadius: 16, padding: 22, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", marginBottom: 20 }}>
      {(title || action) && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 18 }}>
          <div>
            {title && <h3 style={{ margin: 0, color: BRAND.navy, fontSize: 17, fontWeight: 900 }}>{title}</h3>}
            {subtitle && <div style={{ marginTop: 6, fontSize: 12, color: "#667085", lineHeight: 1.7 }}>{subtitle}</div>}
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

function EmptyState({ title, text }) {
  return (
    <div style={{ border: "1px dashed #d8dee9", borderRadius: 14, padding: 28, textAlign: "center", color: "#667085", background: "#fafbfd" }}>
      <div style={{ fontWeight: 900, color: BRAND.navy, marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 13 }}>{text}</div>
    </div>
  );
}

function StatusPill({ text, color = BRAND.navy, subtle = false }) {
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      minHeight: 30,
      padding: "4px 12px",
      borderRadius: 999,
      background: subtle ? `${color}14` : color,
      color: subtle ? color : "#fff",
      border: subtle ? `1px solid ${color}33` : "none",
      fontSize: 12,
      fontWeight: 900,
    }}>{text}</span>
  );
}

function ProgressBar({ value = 0, color = `linear-gradient(90deg, ${BRAND.gold}, ${BRAND.amber})`, track = "#edf2f7" }) {
  return (
    <div style={{ width: "100%", height: 10, borderRadius: 999, background: track, overflow: "hidden" }}>
      <div style={{ width: `${Math.max(0, Math.min(100, Number(value || 0)))}%`, height: "100%", borderRadius: 999, background: color, transition: "width .2s ease" }} />
    </div>
  );
}

function WalletHero({ title, balanceEgp, investedEgp, returnsEgp, avgRoi, rate, preference, badgeText = "نشط", accent = BRAND.gold, onWithdraw, footerNote }) {
  return (
    <div style={{ borderRadius: 22, padding: 24, color: "#fff", background: "linear-gradient(135deg, #1a2b4a 0%, #0f4c81 60%, #1565a3 100%)", boxShadow: "0 16px 50px rgba(16,27,47,.18)", marginBottom: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,.78)", marginBottom: 8 }}>{title}</div>
          <div style={{ fontSize: 32, fontWeight: 900, lineHeight: 1.1 }}>{primaryMoney(balanceEgp, rate, preference)}</div>
          <div style={{ marginTop: 8, fontSize: 13, color: "rgba(255,255,255,.78)" }}>{secondaryMoney(balanceEgp, rate, preference)}</div>
        </div>
        <StatusPill text={badgeText} color={accent} subtle />
      </div>
      <div className="wallet-stats" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12, marginTop: 18 }}>
        {[
          ["إجمالي المُستثمر", primaryMoney(investedEgp, rate, preference)],
          ["أرباح محققة", primaryMoney(returnsEgp, rate, preference)],
          ["متوسط العائد", `${Number(avgRoi || 0).toFixed(1)}%`],
        ].map(([label, value]) => (
          <div key={label} style={{ borderRadius: 14, background: "rgba(255,255,255,.08)", padding: 14 }}>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,.72)" }}>{label}</div>
            <div style={{ marginTop: 8, fontWeight: 900, fontSize: 20 }}>{value}</div>
          </div>
        ))}
      </div>
      {(onWithdraw || footerNote) && (
        <div className="withdraw-bar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginTop: 18, paddingTop: 18, borderTop: "1px solid rgba(255,255,255,.12)" }}>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,.78)" }}>{footerNote || "يمكنك متابعة الرصيد المتاح وطلبات السحب من هنا."}</div>
          {onWithdraw && <button onClick={onWithdraw} style={{ minHeight: 44, borderRadius: 12, border: `1px solid ${accent}`, color: "#fff", background: "transparent", padding: "10px 18px", fontWeight: 800, cursor: "pointer" }}>طلب سحب</button>}
        </div>
      )}
    </div>
  );
}

function AchievementStrip({ title = "نظام التحفيز", subtitle = "", badges = [] }) {
  return (
    <PageSection title={title} subtitle={subtitle}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {badges.map((badge) => (
          <div key={badge.key || badge.label} style={{
            minWidth: 130,
            borderRadius: 16,
            padding: 14,
            border: badge.earned ? `1px solid ${BRAND.gold}` : "1px dashed #cbd5e1",
            background: badge.earned ? "#fffaf0" : "#f8fafc",
            opacity: badge.earned ? 1 : 0.6,
          }}>
            <div style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: badge.earned ? `${BRAND.gold}22` : "#fff", color: badge.earned ? BRAND.gold : "#98A2B3", border: badge.earned ? `1px solid ${BRAND.gold}40` : "1px dashed #cbd5e1", fontWeight: 900 }}>
              {badge.earned ? "✓" : "?"}
            </div>
            <div style={{ marginTop: 10, fontSize: 12, fontWeight: 900, color: BRAND.ink }}>{badge.label}</div>
            <div style={{ marginTop: 6, fontSize: 11, color: "#667085", lineHeight: 1.7 }}>{badge.description}</div>
          </div>
        ))}
      </div>
    </PageSection>
  );
}

function LegacyFinancePage() {
  const user = useAuth();
  const isTrainingSupervisor = user?.role === "training_supervisor";
  const canSeeFoundingData = !isTrainingSupervisor;
  const [tab, setTab] = useState("cashflow");
  const [revenues, setRevenues] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [assets, setAssets] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [cashflow, setCashflow] = useState(null);
  const [partners, setPartners] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});
  const [selectedMonth, setSelectedMonth] = useState("");
  const [showPreLaunch, setShowPreLaunch] = useState(false);

  const load = useCallback(() => {
    api.get("/revenues").then(data => setRevenues(safeArray(data)));
    api.get("/expenses").then(data => setExpenses(safeArray(data)));
    api.get("/assets").then(data => setAssets(safeArray(data)));
    api.get("/forecast").then(data => setForecast(safeArray(data)));
    api.get("/cashflow").then(data => setCashflow(data?.transactions ? data : { transactions: [], balance_usd: 0, balance_egp: 0, capital_in: 0, cash_out: 0 }));
    api.get("/partners").then(data => setPartners(safeArray(data)));
    api.get("/payouts").then(data => setPayouts(safeArray(data)));
    api.get("/finance/summary").then(setSummary);
  }, []);
  useEffect(load, [load]);
  useEffect(() => {
    const months = [
      ...safeArray(summary?.monthly).filter(item => isTrainingSupervisor ? item.period === "operating" : true),
      ...safeArray(forecast).filter(item => item?.month).map(item => ({ month: item.month })),
    ].filter((item, index, array) => item?.month && array.findIndex((candidate) => candidate.month === item.month) === index);
    if (!selectedMonth && months.length) setSelectedMonth(months[months.length - 1].month);
    if (selectedMonth && months.length && !months.find(item => item.month === selectedMonth)) setSelectedMonth(months[months.length - 1].month);
    if (!months.length) setSelectedMonth("");
  }, [summary, selectedMonth, isTrainingSupervisor, forecast]);

  useEffect(() => {
    if (isTrainingSupervisor && tab === "cashflow") setTab("expenses");
    if (isTrainingSupervisor && tab === "partners") setTab("expenses");
    if (isTrainingSupervisor && tab === "assets") setTab("expenses");
  }, [isTrainingSupervisor, tab]);

  const saveRevenue = async () => {
    if (form.id) await api.put(`/revenues/${form.id}`, form);
    else await api.post("/revenues", form);
    setModal(null); setForm({}); load();
  };
  const saveExpense = async () => {
    if (form.id) await api.put(`/expenses/${form.id}`, form);
    else await api.post("/expenses", form);
    setModal(null); setForm({}); load();
  };
  const saveAsset = async () => {
    if (form.id) await api.put(`/assets/${form.id}`, form);
    else await api.post("/assets", form);
    setModal(null); setForm({}); load();
  };
  const saveCashflow = async () => {
    if (form.id) await api.put(`/cashflow/${form.id}`, form);
    else await api.post("/cashflow", form);
    setModal(null); setForm({}); load();
  };
  const savePartner = async () => {
    if (form.id) await api.put(`/partners/${form.id}`, form);
    else await api.post("/partners", form);
    setModal(null); setForm({}); load();
  };
  const savePayout = async () => {
    if (form.id) await api.put(`/payouts/${form.id}`, form);
    else await api.post("/payouts", form);
    setModal(null); setForm({}); load();
  };
  const updateForecast = async (item, patch) => {
    await api.put(`/forecast/${item.id}`, { ...item, ...patch });
    load();
  };
  const deleteItem = async (type, id) => {
    if (!confirm("هل تريد الحذف؟")) return;
    await api.del(`/${type}/${id}`); load();
  };
  if (!summary) return <PageLoader />;
  if (summary?.error) return <PageError message={summary.error} onRetry={load} />;

  const rate = Number(summary?.exchange_rate || 50);
  const monthlyRows = safeArray(summary?.monthly);
  const preLaunchMonths = monthlyRows.filter(item => item.period === "pre_launch");
  const operatingMonths = monthlyRows.filter(item => item.period === "operating");
  const forecastMap = safeObject(safeArray(forecast).reduce((acc, item) => {
    if (item?.month) acc[item.month] = item;
    return acc;
  }, {}));
  const operatingTimeline = Array.from(new Set([...safeArray(forecast).map(item => item.month), ...operatingMonths.map(item => item.month)]))
    .filter(Boolean)
    .sort()
    .map((month) => {
      const actual = operatingMonths.find((item) => item.month === month);
      const plan = forecastMap[month];
      return {
        month,
        period: "operating",
        revenue: actual?.revenue || 0,
        expenses: actual?.expenses || 0,
        direct_expenses: actual?.direct_expenses || 0,
        payouts: actual?.payouts || 0,
        asset_rent: actual?.asset_rent || 0,
        profit: actual?.profit || 0,
        target_revenue: plan?.revenue_egp || 0,
        target_expenses: plan?.total_expenses || 0,
        target_students: plan?.target_students || 0,
        target_courses: plan?.target_courses || 0,
        isForecastOnly: !actual,
      };
    });
  const visibleMonths = canSeeFoundingData ? [...preLaunchMonths, ...operatingTimeline] : operatingTimeline;
  const operatingQuarterGroups = buildQuarterGroups(operatingTimeline);
  const monthRevenues = revenues.filter(item => item.date?.startsWith(selectedMonth));
  const monthExpenses = expenses.filter(item => item.date?.startsWith(selectedMonth));
  const monthPayouts = payouts.filter(item => item.date?.startsWith(selectedMonth));
  const monthCash = safeArray(cashflow?.transactions).filter(item => item.date?.startsWith(selectedMonth));
  const preLaunchTotals = {
    revenue: sumBy(preLaunchMonths, item => item.revenue),
    expenses: sumBy(preLaunchMonths, item => item.expenses),
    direct_expenses: sumBy(preLaunchMonths, item => item.direct_expenses),
    payouts: sumBy(preLaunchMonths, item => item.payouts),
    asset_rent: sumBy(preLaunchMonths, item => item.asset_rent),
    profit: sumBy(preLaunchMonths, item => item.profit),
  };
  const financeTabs = isTrainingSupervisor
    ? [
        { id: "expenses", label: `المصروفات (${expenses.length})` },
        { id: "payouts", label: `المدربين والإشراف (${payouts.length})` },
        { id: "forecast", label: "الأهداف القادمة" },
      ]
    : [
        { id: "cashflow", label: "Cash Flow" },
        { id: "revenues", label: `الإيرادات (${revenues.length})` },
        { id: "expenses", label: `المصروفات (${expenses.length})` },
        { id: "partners", label: `الشركاء (${partners.length})` },
        { id: "payouts", label: `مدربين/إشراف/أفلييت (${payouts.length})` },
        { id: "assets", label: `الأصول (${assets.length})` },
        { id: "forecast", label: "Future targets" }
      ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy }}>المالية والتوقعات</h1>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "flex-end" }}>
          {!isTrainingSupervisor && <Btn onClick={() => { setForm({ date: new Date().toISOString().split("T")[0], kind: "capital_in", amount_egp: 0, amount_usd: 0 }); setModal("cashflow"); }} color={BRAND.navy}>+ Cash Flow</Btn>}
          {!isTrainingSupervisor && <Btn onClick={() => { setForm({ date: new Date().toISOString().split("T")[0], source: "course", amount_egp: 0, amount_usd: 0 }); setModal("revenue"); }} color="#2d8659">+ إيراد جديد</Btn>}
          <Btn onClick={() => { setForm({ date: new Date().toISOString().split("T")[0], category: "tools", amount_egp: 0, amount_usd: 0, is_business: true }); setModal("expense"); }} color="#c0392b">+ مصروف جديد</Btn>
          {!isTrainingSupervisor && <Btn onClick={() => { setForm({ name: "", role: "founder", equity_percent: 0, profit_share_percent: 0, capital_egp: 0, capital_usd: 0 }); setModal("partner"); }} color="#5b6abf">+ شريك</Btn>}
          <Btn onClick={() => { setForm({ date: new Date().toISOString().split("T")[0], role: "trainer", status: "accrued", percent: 0, basis_amount_egp: 0, amount_egp: 0, amount_usd: 0 }); setModal("payout"); }} color="#8e44ad">+ مستحق</Btn>
          {!isTrainingSupervisor && <Btn onClick={() => { setForm({ category: "equipment", owner: "عبدالرحمن", value_egp: 0, monthly_rent_egp: 0, status: "leased_to_company" }); setModal("asset"); }} color={BRAND.gold}>+ أصل</Btn>}
        </div>
      </div>

      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
          {!isTrainingSupervisor && <KPICard icon="🏦" label="الرصيد المتاح الآن" value={fmtUSD(summary.cashflow?.balance_usd)} sub={`${egpLabel(summary.cashflow?.balance_egp)} من رأس المال المتبقي`} color={BRAND.navy} />}
          <KPICard icon="💰" label="إيرادات تشغيلية" value={usdFromEgp(summary.total_revenue, rate)} sub={egpLabel(summary.total_revenue)} color="#2d8659" />
          {canSeeFoundingData && <KPICard icon="🏗️" label={`تأسيس قبل ${summary.cutoff_month || "2026-06"}`} value={usdFromEgp(summary.pre_launch?.expenses, rate)} sub={`${egpLabel(summary.pre_launch?.expenses)} | صافي: ${egpLabel(summary.pre_launch?.profit)}`} color="#c0392b" />}
          <KPICard icon="⚙️" label="تشغيل من يونيو" value={usdFromEgp(summary.operating?.expenses, rate)} sub={`${egpLabel(summary.operating?.expenses)} | صافي: ${egpLabel(summary.operating?.profit)}`} color="#8e44ad" />
          {!canSeeFoundingData && <KPICard icon="🎯" label="الهدف القادم" value={usdFromEgp(forecast[0]?.revenue_egp || 0, rate)} sub={forecast[0]?.month ? monthLabel(forecast[0]?.month) : "بدون هدف بعد"} color={BRAND.gold} />}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 24 }}>
        {(operatingTimeline.length > 0 || summary?.monthly?.length > 0) && (
          <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>Cash Flow الشهري</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={operatingTimeline.length ? operatingTimeline : safeArray(summary.monthly)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={v => `${fmt(v)} ج.م`} />
                <Line type="monotone" dataKey="revenue" name="إيرادات" stroke="#2d8659" strokeWidth={2} dot={{ r: 4 }} />
                <Line type="monotone" dataKey="expenses" name="مصروفات" stroke="#c0392b" strokeWidth={2} dot={{ r: 4 }} />
                <Line type="monotone" dataKey="profit" name="صافي" stroke="#0f4c81" strokeWidth={2} strokeDasharray="5 5" />
                <Legend />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        {summary?.expense_categories?.length > 0 && (
          <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>تصنيف المصروفات</h3>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
              <Pie data={safeArray(summary.expense_categories).map(c => ({ name: catLabels[c.category] || c.category, value: c.total }))} cx="50%" cy="50%" innerRadius={45} outerRadius={82} dataKey="value" label={false}>
                  {safeArray(summary.expense_categories).map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={v => `${fmt(v)} ج.م`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {visibleMonths.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.06)", marginBottom: 24 }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid #f0eadb", background: "#fcfbf8" }}>
            <h3 style={{ margin: 0, color: BRAND.navy, fontSize: 15, fontWeight: 900 }}>هيكل التشغيل الشهري</h3>
            <div style={{ marginTop: 6, fontSize: 12, color: "#667085" }}>من قبل {summary.cutoff_month} كتأسيس مجمّع، ومن {summary.cutoff_month} تبدأ المتابعة الشهرية والربع سنوية.</div>
          </div>
          <div style={{ padding: 18 }}>
            {canSeeFoundingData && (
              <div style={{ marginBottom: 18, border: "1px solid #f2d7d5", borderRadius: 12, overflow: "hidden" }}>
                <button onClick={() => setShowPreLaunch(!showPreLaunch)} style={{ width: "100%", border: 0, background: "#fff7f6", padding: "14px 16px", textAlign: "right", cursor: "pointer" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                    <div>
                      <div style={{ fontWeight: 900, color: "#7b241c", fontSize: 14 }}>مرحلة التأسيس قبل {summary.cutoff_month}</div>
                      <div style={{ marginTop: 4, fontSize: 12, color: "#7d6a65" }}>
                        {preLaunchMonths.length} شهر | مصروفات {egpLabel(preLaunchTotals.expenses)} | صافي {egpLabel(preLaunchTotals.profit)}
                      </div>
                    </div>
                    <span style={{ color: "#7b241c", fontSize: 18 }}>{showPreLaunch ? "−" : "+"}</span>
                  </div>
                </button>
                {showPreLaunch && (
                  <div style={{ padding: 14, background: "#fff" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 14 }}>
                      <KPICard label="إيراد التأسيس" value={usdFromEgp(preLaunchTotals.revenue, rate)} sub={egpLabel(preLaunchTotals.revenue)} color="#2d8659" />
                      <KPICard label="مصروف مباشر" value={usdFromEgp(preLaunchTotals.direct_expenses, rate)} sub={egpLabel(preLaunchTotals.direct_expenses)} color="#c0392b" />
                      <KPICard label="مستحقات" value={usdFromEgp(preLaunchTotals.payouts, rate)} sub={egpLabel(preLaunchTotals.payouts)} color="#8e44ad" />
                      <KPICard label="إيجار أصول" value={usdFromEgp(preLaunchTotals.asset_rent, rate)} sub={egpLabel(preLaunchTotals.asset_rent)} color={BRAND.navy} />
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
                      {preLaunchMonths.map((row) => (
                        <button key={row.month} onClick={() => setSelectedMonth(row.month)} style={{ border: selectedMonth === row.month ? `2px solid ${BRAND.gold}` : "1px solid #eee", borderRadius: 12, background: selectedMonth === row.month ? "#fff8e8" : "#fff", padding: 14, textAlign: "right", cursor: "pointer" }}>
                          <div style={{ fontWeight: 900, color: BRAND.navy, fontSize: 13 }}>{monthLabel(row.month)}</div>
                          <div style={{ fontSize: 12, color: "#667085", marginTop: 6 }}>مصروف {egpLabel(row.expenses)}</div>
                          <div style={{ fontSize: 12, color: row.profit >= 0 ? "#2d8659" : "#c0392b", marginTop: 4 }}>صافي {egpLabel(row.profit)}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {operatingQuarterGroups.map((group) => (
              <div key={group.id} style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                  <div style={{ fontWeight: 900, color: BRAND.navy }}>{group.label}</div>
                  <div style={{ fontSize: 12, color: "#667085" }}>
                    إيراد {egpLabel(group.totals.revenue)} | مصروف {egpLabel(group.totals.expenses)} | صافي {egpLabel(group.totals.profit)}
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10 }}>
                  {group.months.map((row) => (
                    <button key={row.month} onClick={() => setSelectedMonth(row.month)} style={{ border: selectedMonth === row.month ? `2px solid ${BRAND.gold}` : "1px solid #eee", borderRadius: 12, background: selectedMonth === row.month ? "#fff8e8" : "#fff", padding: 14, textAlign: "right", cursor: "pointer" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                        <strong style={{ color: BRAND.navy, fontSize: 13 }}>{monthLabel(row.month)}</strong>
                        <Badge text={row.isForecastOnly ? "مستهدف" : "تشغيل"} color={row.isForecastOnly ? BRAND.gold : "#2d8659"} />
                      </div>
                      <div style={{ fontSize: 12, color: "#667085", lineHeight: 1.9 }}>
                        <div>إيراد: <strong style={{ color: "#2d8659" }}>{egpLabel(row.revenue)}</strong></div>
                        <div>مصروف مباشر: <strong>{egpLabel(row.direct_expenses)}</strong></div>
                        <div>مستحقات: <strong>{egpLabel(row.payouts)}</strong></div>
                        <div>إيجار أصول: <strong>{egpLabel(row.asset_rent)}</strong></div>
                        {row.target_revenue > 0 && <div>الهدف: <strong style={{ color: BRAND.navy }}>{egpLabel(row.target_revenue)}</strong></div>}
                        {row.target_expenses > 0 && <div>مصروف مستهدف: <strong>{egpLabel(row.target_expenses)}</strong></div>}
                      </div>
                      <div style={{ marginTop: 8, fontWeight: 900, color: row.profit >= 0 ? "#2d8659" : "#c0392b", fontSize: 13 }}>
                        {row.isForecastOnly ? `صافي متوقع: ${egpLabel(row.target_revenue - row.target_expenses)}` : `صافي: ${egpLabel(row.profit)}`}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {selectedMonth && (
        <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.06)", marginBottom: 24 }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid #f0eadb", background: "#fcfbf8" }}>
            <h3 style={{ margin: 0, color: BRAND.navy, fontSize: 15, fontWeight: 900 }}>تفاصيل شهر {selectedMonth}</h3>
            <div style={{ marginTop: 6, fontSize: 12, color: "#667085" }}>اضغط على أي شهر من الجدول لاستخراج إيراداته ومصروفاته وحركاته.</div>
          </div>
          <div style={{ padding: 20, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
            <KPICard label="إيرادات الشهر" value={usdFromEgp(monthRevenues.reduce((s, x) => s + (x.total_egp || 0), 0), rate)} sub={egpLabel(monthRevenues.reduce((s, x) => s + (x.total_egp || 0), 0))} color="#2d8659" />
            <KPICard label="مصروفات الشهر" value={usdFromEgp(monthExpenses.reduce((s, x) => s + (x.total_egp || 0), 0), rate)} sub={egpLabel(monthExpenses.reduce((s, x) => s + (x.total_egp || 0), 0))} color="#c0392b" />
            <KPICard label="مستحقات الشهر" value={usdFromEgp(monthPayouts.reduce((s, x) => s + (x.total_egp || 0), 0), rate)} sub={egpLabel(monthPayouts.reduce((s, x) => s + (x.total_egp || 0), 0))} color="#8e44ad" />
            <KPICard label="حركة الكاش" value={usdFromEgp(monthCash.reduce((s, x) => s + ((x.kind === "capital_in" || x.kind === "adjustment_in") ? (x.total_egp || 0) : -(x.total_egp || 0)), 0), rate)} sub={egpLabel(monthCash.reduce((s, x) => s + ((x.kind === "capital_in" || x.kind === "adjustment_in") ? (x.total_egp || 0) : -(x.total_egp || 0)), 0))} color={BRAND.navy} />
          </div>
          <div style={{ padding: "0 20px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
            <div>
              <h4 style={{ color: BRAND.navy, marginBottom: 10 }}>الإيرادات</h4>
              {monthRevenues.length ? monthRevenues.map(item => <div key={`rev-${item.id}`} style={{ padding: "10px 0", borderBottom: "1px solid #f3f4f6", fontSize: 13 }}><strong>{item.description}</strong><div style={{ color: "#667085" }}>{item.date}</div><div style={{ color: "#2d8659", fontWeight: 800 }}>{egpLabel(item.total_egp)}</div></div>) : <div style={{ color: "#9ca3af", fontSize: 13 }}>لا توجد إيرادات مسجلة لهذا الشهر.</div>}
            </div>
            <div>
              <h4 style={{ color: BRAND.navy, marginBottom: 10 }}>المصروفات</h4>
              {monthExpenses.length ? monthExpenses.map(item => <div key={`exp-${item.id}`} style={{ padding: "10px 0", borderBottom: "1px solid #f3f4f6", fontSize: 13 }}><strong>{item.description}</strong><div style={{ color: "#667085" }}>{catLabels[item.category] || item.category}</div><div style={{ color: "#c0392b", fontWeight: 800 }}>{egpLabel(item.total_egp)}</div></div>) : <div style={{ color: "#9ca3af", fontSize: 13 }}>لا توجد مصروفات مسجلة لهذا الشهر.</div>}
            </div>
            <div>
              <h4 style={{ color: BRAND.navy, marginBottom: 10 }}>المستحقات</h4>
              {monthPayouts.length ? monthPayouts.map(item => <div key={`pay-${item.id}`} style={{ padding: "10px 0", borderBottom: "1px solid #f3f4f6", fontSize: 13 }}><strong>{item.name}</strong><div style={{ color: "#667085" }}>{payoutRoleLabels[item.role] || item.role} • {item.related_to}</div><div style={{ color: "#8e44ad", fontWeight: 800 }}>{egpLabel(item.total_egp)}</div></div>) : <div style={{ color: "#9ca3af", fontSize: 13 }}>لا توجد مستحقات لهذا الشهر.</div>}
            </div>
            <div>
              <h4 style={{ color: BRAND.navy, marginBottom: 10 }}>حركات الكاش</h4>
              {monthCash.length ? monthCash.map(item => <div key={`cash-${item.id}`} style={{ padding: "10px 0", borderBottom: "1px solid #f3f4f6", fontSize: 13 }}><strong>{cashKindLabels[item.kind] || item.kind}</strong><div style={{ color: "#667085" }}>{item.description}</div><div style={{ color: item.kind === "capital_in" || item.kind === "adjustment_in" ? "#2d8659" : "#c0392b", fontWeight: 800 }}>{egpLabel(item.total_egp)}</div></div>) : <div style={{ color: "#9ca3af", fontSize: 13 }}>لا توجد حركات كاش لهذا الشهر.</div>}
            </div>
          </div>
        </div>
      )}

      <TabBar tabs={financeTabs} active={tab} onChange={setTab} />

      {tab === "cashflow" && (
        <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <div style={{ padding: 18, background: "#F7F4EB", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            <KPICard icon="🏦" label="الرصيد المتاح" value={fmtUSD(cashflow?.balance_usd)} sub={`${fmt(cashflow?.balance_egp)} ج.م متبقي للتشغيل`} color={BRAND.navy} />
            <KPICard icon="➕" label="إجمالي رأس المال المضخوخ" value={`${fmt(cashflow?.capital_in)} ج.م`} sub="كل ما دخل الشركة كرأس مال" color="#2d8659" />
            <KPICard icon="➖" label="المصروف المسحوب من رأس المال" value={`${fmt(cashflow?.cash_out)} ج.م`} sub="إنفاق تشغيلي أو تأسيسي من الكاش" color="#c0392b" />
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead><tr style={{ background: "#f8fafc" }}>{["التاريخ", "النوع", "المصدر", "الوصف", "المبلغ", ""].map(h => <th key={h} style={{ padding: "12px 16px", textAlign: "right", color: "#667085" }}>{h}</th>)}</tr></thead>
            <tbody>{cashflow?.transactions?.map(t => <tr key={t.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={{ padding: "12px 16px" }}>{t.date}</td>
              <td><Badge text={cashKindLabels[t.kind] || t.kind} color={t.kind === "capital_in" ? "#2d8659" : "#c0392b"} /></td>
              <td>{t.source}</td><td>{t.description}</td>
              <td style={{ fontWeight: 900, color: t.kind === "capital_in" ? "#2d8659" : "#c0392b" }}>{fmt(t.total_egp)} ج.م</td>
              <td><button onClick={() => { setForm(t); setModal("cashflow"); }} style={{ background: "none", border: "none", cursor: "pointer" }}>✏️</button></td>
            </tr>)}</tbody>
          </table>
        </div>
      )}

      {tab === "revenues" && (
        <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead><tr style={{ background: "#f8fafc" }}>
              {["التاريخ", "المصدر", "الوصف", "العميل", "المبلغ ج.م", ""].map(h => <th key={h} style={{ padding: "12px 16px", textAlign: "right", fontWeight: 600, color: "#6b7280", borderBottom: "1px solid #e5e7eb" }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {revenues.map(r => (
                <tr key={r.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ padding: "12px 16px" }}>{r.date}</td>
                  <td><Badge text={srcLabels[r.source] || r.source} color="#2d8659" /></td>
                  <td style={{ maxWidth: 200 }}>{r.description}</td>
                  <td>{r.client_name}</td>
                  <td style={{ fontWeight: 700, color: "#2d8659" }}>{fmt(r.total_egp)}</td>
                  <td>
                    <button onClick={() => { setForm(r); setModal("revenue"); }} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16 }}>✏️</button>
                    <button onClick={() => deleteItem("revenues", r.id)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, marginRight: 8 }}>🗑</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "expenses" && (
        <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead><tr style={{ background: "#f8fafc" }}>
              {["التاريخ", "الفئة", "الوصف", "المبلغ ج.م", "النوع", ""].map(h => <th key={h} style={{ padding: "12px 16px", textAlign: "right", fontWeight: 600, color: "#6b7280", borderBottom: "1px solid #e5e7eb" }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {expenses.map(e => (
                <tr key={e.id} style={{ borderBottom: "1px solid #f3f4f6", opacity: e.is_business ? 1 : 0.5 }}>
                  <td style={{ padding: "12px 16px" }}>{e.date}</td>
                  <td><Badge text={catLabels[e.category] || e.category} color="#e8913a" /></td>
                  <td>{e.description}</td>
                  <td style={{ fontWeight: 700, color: "#c0392b" }}>{fmt(e.total_egp)}</td>
                  <td>{e.is_business ? <Badge text="أعمال" color="#2d8659" /> : <Badge text="شخصي" color="#9ca3af" />}</td>
                  <td>
                    <button onClick={() => { setForm(e); setModal("expense"); }} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16 }}>✏️</button>
                    <button onClick={() => deleteItem("expenses", e.id)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, marginRight: 8 }}>🗑</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "partners" && (
        <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead><tr style={{ background: "#f8fafc" }}>{["الشريك", "الدور", "نسبة الملكية", "نسبة الأرباح", "مساهمة رأس مال", "ملاحظات", ""].map(h => <th key={h} style={{ padding: "12px 16px", textAlign: "right", color: "#667085" }}>{h}</th>)}</tr></thead>
            <tbody>{partners.map(p => <tr key={p.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={{ padding: "12px 16px", fontWeight: 900 }}>{p.name}</td>
              <td>{p.role}</td><td>{p.equity_percent}%</td><td>{p.profit_share_percent}%</td>
              <td>{fmt(p.total_capital_egp)} ج.م</td><td>{p.notes}</td>
              <td><button onClick={() => { setForm(p); setModal("partner"); }} style={{ background: "none", border: "none", cursor: "pointer" }}>✏️</button></td>
            </tr>)}</tbody>
          </table>
        </div>
      )}

      {tab === "payouts" && (
        <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead><tr style={{ background: "#f8fafc" }}>{["التاريخ", "الاسم", "النوع", "مرتبط بـ", "النسبة", "المستحق", "الحالة", ""].map(h => <th key={h} style={{ padding: "12px 16px", textAlign: "right", color: "#667085" }}>{h}</th>)}</tr></thead>
            <tbody>{payouts.map(p => <tr key={p.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={{ padding: "12px 16px" }}>{p.date}</td>
              <td style={{ fontWeight: 900 }}>{p.name}</td>
              <td><Badge text={payoutRoleLabels[p.role] || p.role} color="#8e44ad" /></td>
              <td>{p.related_to}</td><td>{p.percent}%</td>
              <td style={{ color: "#8e44ad", fontWeight: 900 }}>{fmt(p.total_egp)} ج.م</td>
              <td>{p.status}</td>
              <td><button onClick={() => { setForm(p); setModal("payout"); }} style={{ background: "none", border: "none", cursor: "pointer" }}>✏️</button></td>
            </tr>)}</tbody>
          </table>
        </div>
      )}

      {tab === "assets" && (
        <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead><tr style={{ background: "#FFF8E1" }}>{["الأصل", "المالك", "القيمة", "الإيجار الشهري", "ملاحظات", ""].map(h => <th key={h} style={{ padding: "12px 16px", textAlign: "right", color: BRAND.navy, borderBottom: "1px solid #E6D7A8" }}>{h}</th>)}</tr></thead>
            <tbody>{assets.map(a => <tr key={a.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={{ padding: "12px 16px", fontWeight: 800 }}>{a.name}</td><td>{a.owner}</td><td>{fmt(a.value_egp)} ج.م</td><td style={{ color: BRAND.gold, fontWeight: 900 }}>{fmt(a.monthly_rent_egp)} ج.م</td><td>{a.notes}</td>
              <td><button onClick={() => { setForm(a); setModal("asset"); }} style={{ background: "none", border: "none", cursor: "pointer" }}>✏️</button></td>
            </tr>)}</tbody>
          </table>
        </div>
      )}

      {tab === "forecast" && (
        <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead><tr style={{ background: "#f8fafc" }}>{["الشهر", "Target Revenue", "مصروفات متوقعة", "Marketing", "دورات", "طلاب", "EBITDA"].map(h => <th key={h} style={{ padding: "12px 14px", textAlign: "right", color: "#667085" }}>{h}</th>)}</tr></thead>
            <tbody>{forecast.map(f => <tr key={f.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={{ padding: "12px 14px", fontWeight: 900 }}>{f.month}</td>
              <td><input type="number" value={f.revenue_egp || 0} onChange={e => updateForecast(f, { revenue_egp: +e.target.value })} style={{ width: 110, border: "1px solid #eee", borderRadius: 8, padding: 6 }} /></td>
              <td>{fmt(f.total_expenses)} ج.م</td><td>{fmt(f.marketing_egp)} ج.م</td><td>{f.target_courses}</td><td>{f.target_students}</td>
              <td style={{ color: f.ebitda >= 0 ? "#2d8659" : "#c0392b", fontWeight: 900 }}>{fmt(f.ebitda)} ج.م</td>
            </tr>)}</tbody>
          </table>
        </div>
      )}

      {/* Revenue Modal */}
      <Modal open={modal === "revenue"} onClose={() => setModal(null)} title={form.id ? "تعديل إيراد" : "إيراد جديد"}>
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        <Select label="المصدر" value={form.source || "course"} onChange={e => setForm({ ...form, source: e.target.value })} options={Object.entries(srcLabels).map(([v, l]) => ({ value: v, label: l }))} />
        <Input label="الوصف" value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })} />
        <Input label="اسم العميل" value={form.client_name || ""} onChange={e => setForm({ ...form, client_name: e.target.value })} />
        <CurrencyFields form={form} setForm={setForm} rate={summary?.exchange_rate || 50} />
        <Select label="طريقة الدفع" value={form.payment_method || "wise"} onChange={e => setForm({ ...form, payment_method: e.target.value })} options={[{ value: "wise", label: "Wise" }, { value: "bank_transfer", label: "تحويل بنكي" }, { value: "cash", label: "كاش" }, { value: "stripe", label: "Stripe" }]} />
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={saveRevenue} color="#2d8659" style={{ width: "100%", marginTop: 8 }}>💾 حفظ</Btn>
      </Modal>

      {/* Expense Modal */}
      <Modal open={modal === "expense"} onClose={() => setModal(null)} title={form.id ? "تعديل مصروف" : "مصروف جديد"}>
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        <Select label="الفئة" value={form.category || "tools"} onChange={e => setForm({ ...form, category: e.target.value })} options={Object.entries(catLabels).map(([v, l]) => ({ value: v, label: l }))} />
        <Input label="الوصف" value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })} />
        <CurrencyFields form={form} setForm={setForm} rate={summary?.exchange_rate || 50} />
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>
            <input type="checkbox" checked={form.is_business !== false} onChange={e => setForm({ ...form, is_business: e.target.checked })} style={{ marginLeft: 8 }} />
            مصروف أعمال
          </label>
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>
            <input type="checkbox" checked={!!form.cash_impact} onChange={e => setForm({ ...form, cash_impact: e.target.checked })} style={{ marginLeft: 8 }} />
            خصم من Cash Flow
          </label>
        </div>
        <Input label="مدفوع بواسطة" value={form.paid_by || ""} onChange={e => setForm({ ...form, paid_by: e.target.value })} />
        <Btn onClick={saveExpense} color="#c0392b" style={{ width: "100%", marginTop: 8 }}>💾 حفظ</Btn>
      </Modal>

      <Modal open={modal === "cashflow"} onClose={() => setModal(null)} title={form.id ? "تعديل حركة Cash Flow" : "حركة Cash Flow"}>
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        <Select label="النوع" value={form.kind || "capital_in"} onChange={e => setForm({ ...form, kind: e.target.value })} options={Object.entries(cashKindLabels).map(([value, label]) => ({ value, label }))} />
        <Input label="المصدر / الشريك" value={form.source || ""} onChange={e => setForm({ ...form, source: e.target.value })} />
        <Input label="الوصف" value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })} />
        <CurrencyFields form={form} setForm={setForm} rate={summary?.exchange_rate || 50} />
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={saveCashflow} color={BRAND.navy} style={{ width: "100%", marginTop: 8 }}>حفظ حركة الكاش</Btn>
      </Modal>

      <Modal open={modal === "partner"} onClose={() => setModal(null)} title={form.id ? "تعديل شريك" : "شريك جديد"}>
        <Input label="اسم الشريك" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })} />
        <Input label="الدور" value={form.role || "founder"} onChange={e => setForm({ ...form, role: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="نسبة الملكية %" type="number" value={form.equity_percent || 0} onChange={e => setForm({ ...form, equity_percent: +e.target.value })} />
          <Input label="نسبة الأرباح %" type="number" value={form.profit_share_percent || 0} onChange={e => setForm({ ...form, profit_share_percent: +e.target.value })} />
        </div>
        <CurrencyFields form={form} setForm={setForm} rate={summary?.exchange_rate || 50} egpKey="capital_egp" usdKey="capital_usd" egpLabel="مساهمة رأس مال (ج.م)" usdLabel="مساهمة رأس مال ($)" />
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={savePartner} color="#5b6abf" style={{ width: "100%", marginTop: 8 }}>حفظ الشريك</Btn>
      </Modal>

      <Modal open={modal === "payout"} onClose={() => setModal(null)} title={form.id ? "تعديل مستحق" : "مستحق مدرب / مشرف / أفلييت"}>
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        <Input label="الاسم" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })} />
        <Select label="النوع" value={form.role || "trainer"} onChange={e => setForm({ ...form, role: e.target.value })} options={Object.entries(payoutRoleLabels).map(([value, label]) => ({ value, label }))} />
        <Input label="مرتبط بـ" value={form.related_to || ""} onChange={e => setForm({ ...form, related_to: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="قيمة الأساس (ج.م)" type="number" value={form.basis_amount_egp || 0} onChange={e => setForm({ ...form, basis_amount_egp: +e.target.value })} />
          <Input label="النسبة %" type="number" value={form.percent || 0} onChange={e => setForm({ ...form, percent: +e.target.value })} />
        </div>
        <CurrencyFields form={form} setForm={setForm} rate={summary?.exchange_rate || 50} />
        <Select label="الحالة" value={form.status || "accrued"} onChange={e => setForm({ ...form, status: e.target.value })} options={[{ value: "accrued", label: "مستحق" }, { value: "paid", label: "مدفوع" }, { value: "waived", label: "متنازل عنه" }]} />
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={savePayout} color="#8e44ad" style={{ width: "100%", marginTop: 8 }}>حفظ المستحق</Btn>
      </Modal>

      <Modal open={modal === "asset"} onClose={() => setModal(null)} title={form.id ? "تعديل أصل" : "أصل جديد"}>
        <Input label="اسم الأصل" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })} />
        <Input label="المالك" value={form.owner || ""} onChange={e => setForm({ ...form, owner: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="قيمة الأصل (ج.م)" type="number" value={form.value_egp || 0} onChange={e => setForm({ ...form, value_egp: +e.target.value })} />
          <Input label="الإيجار الشهري (ج.م)" type="number" value={form.monthly_rent_egp || 0} onChange={e => setForm({ ...form, monthly_rent_egp: +e.target.value })} />
        </div>
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={saveAsset} color={BRAND.gold} style={{ width: "100%", marginTop: 8, color: BRAND.navy }}>حفظ الأصل</Btn>
      </Modal>
    </div>
  );
}

function FinancePage() {
  const user = useAuth();
  const isTrainingSupervisor = user?.role === "training_supervisor";
  const { loading, error, revenues, expenses, forecast, cashflow, payouts, summary, reload } = useFinanceData();
  const [tab, setTab] = useState("summary");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});
  const [revenueFilter, setRevenueFilter] = useState({ from: "", to: "", source: "all" });
  const [expenseFilter, setExpenseFilter] = useState({ from: "", to: "", category: "all" });
  const [selectedMonth, setSelectedMonth] = useState("");

  useEffect(() => {
    if (isTrainingSupervisor && tab === "cashflow") setTab("summary");
  }, [isTrainingSupervisor, tab]);

  const saveRevenue = async () => {
    if (form.id) await api.put(`/revenues/${form.id}`, form);
    else await api.post("/revenues", form);
    setModal(null);
    setForm({});
    reload();
  };

  const saveExpense = async () => {
    if (form.id) await api.put(`/expenses/${form.id}`, form);
    else await api.post("/expenses", form);
    setModal(null);
    setForm({});
    reload();
  };

  const saveCashflow = async () => {
    if (form.id) await api.put(`/cashflow/${form.id}`, form);
    else await api.post("/cashflow", form);
    setModal(null);
    setForm({});
    reload();
  };

  const deleteItem = async (type, id) => {
    if (!confirm("هل تريد الحذف؟")) return;
    await api.del(`/${type}/${id}`);
    reload();
  };

  const rate = Number(summary?.exchange_rate || 50);
  const operatingMonths = safeArray(summary?.monthly).filter(item => item.period === "operating");
  const quarterRows = buildQuarterGroups(operatingMonths);
  const monthOptions = Array.from(new Set([
    ...operatingMonths.map(item => item.month),
    ...revenues.map(item => item.date?.slice(0, 7)),
    ...expenses.filter(item => item.is_business !== false).map(item => item.date?.slice(0, 7)),
    ...payouts.map(item => item.date?.slice(0, 7)),
    ...safeArray(cashflow.transactions).map(item => item.date?.slice(0, 7)),
  ].filter(Boolean))).sort().reverse();

  useEffect(() => {
    if (!monthOptions.length) {
      if (selectedMonth) setSelectedMonth("");
      return;
    }
    const latestMonth = monthOptions[0];
    if (!selectedMonth || !monthOptions.includes(selectedMonth)) setSelectedMonth(latestMonth);
  }, [selectedMonth, monthOptions]);

  if (loading) return <PageLoader />;
  if (error || !summary || !summary.monthly) return <PageError message={error || "بيانات المالية غير مكتملة حاليًا."} onRetry={reload} />;

  const monthRevenues = revenues.filter(item => item.date?.startsWith(selectedMonth));
  const monthExpenses = expenses.filter(item => item.date?.startsWith(selectedMonth));
  const monthPayouts = payouts.filter(item => item.date?.startsWith(selectedMonth));
  const monthCash = safeArray(cashflow.transactions).filter(item => item.date?.startsWith(selectedMonth));

  const filteredRevenues = revenues.filter((item) => {
    if (revenueFilter.from && item.date < revenueFilter.from) return false;
    if (revenueFilter.to && item.date > revenueFilter.to) return false;
    if (revenueFilter.source !== "all" && item.source !== revenueFilter.source) return false;
    return true;
  });

  const filteredExpenses = expenses.filter((item) => {
    if (expenseFilter.from && item.date < expenseFilter.from) return false;
    if (expenseFilter.to && item.date > expenseFilter.to) return false;
    if (expenseFilter.category !== "all" && item.category !== expenseFilter.category) return false;
    return true;
  });

  const tabs = isTrainingSupervisor
    ? [
        { id: "summary", label: "الملخص" },
        { id: "revenues", label: "الإيرادات" },
        { id: "expenses", label: "المصروفات" },
        { id: "monthly", label: "الشهري" },
      ]
    : [
        { id: "summary", label: "الملخص" },
        { id: "revenues", label: "الإيرادات" },
        { id: "expenses", label: "المصروفات" },
        { id: "cashflow", label: "Cash Flow" },
        { id: "monthly", label: "الشهري" },
        { id: "assets", label: "الأصول" },
      ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 18, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy, margin: 0 }}>المالية</h1>
          <div style={{ marginTop: 6, color: "#667085", fontSize: 13 }}>
            صفحة أخف ومنظمة: ملخص، إيرادات، مصروفات، Cash Flow، وعرض شهري فقط.
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {!isTrainingSupervisor && <Btn onClick={() => { setForm({ date: new Date().toISOString().split("T")[0], source: "course", amount_egp: 0, amount_usd: 0 }); setModal("revenue"); }} color="#2d8659">+ إيراد جديد</Btn>}
          <Btn onClick={() => { setForm({ date: new Date().toISOString().split("T")[0], category: "tools", amount_egp: 0, amount_usd: 0, is_business: true }); setModal("expense"); }} color="#c0392b">+ مصروف جديد</Btn>
          {!isTrainingSupervisor && <Btn onClick={() => { setForm({ date: new Date().toISOString().split("T")[0], kind: "capital_in", amount_egp: 0, amount_usd: 0 }); setModal("cashflow"); }} color={BRAND.navy}>+ Cash Flow</Btn>}
        </div>
      </div>

      <TabBar tabs={tabs} active={tab} onChange={setTab} />

      {tab === "assets" && !isTrainingSupervisor && <AssetsPanel />}

      {tab === "summary" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 16, marginBottom: 20 }}>
            {!isTrainingSupervisor && <KPICard icon="🏦" label="الرصيد المتاح الآن" value={fmtUSD(summary.cashflow?.balance_usd)} sub={egpLabel(summary.cashflow?.balance_egp)} color={BRAND.navy} />}
            <KPICard icon="💰" label="إيرادات تشغيلية" value={usdFromEgp(summary.total_revenue, rate)} sub={egpLabel(summary.total_revenue)} color="#2d8659" />
            {!isTrainingSupervisor && <KPICard icon="🏗️" label="تأسيس قبل 06-2026" value={usdFromEgp(summary.pre_launch?.expenses, rate)} sub={`صافي ${egpLabel(summary.pre_launch?.profit)}`} color="#c0392b" />}
            <KPICard icon="⚙️" label="تشغيل من يونيو" value={usdFromEgp(summary.operating?.expenses, rate)} sub={`صافي ${egpLabel(summary.operating?.profit)}`} color="#8e44ad" />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.8fr) minmax(280px, 1fr)", gap: 20, marginBottom: 20 }}>
            <PageSection title="التدفق الشهري" subtitle="من بيانات التشغيل الفعلية فقط.">
              {operatingMonths.length ? (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={operatingMonths}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={v => `${fmt(v)} ج.م`} />
                    <Legend />
                    <Line type="monotone" dataKey="revenue" name="إيرادات" stroke="#2d8659" strokeWidth={2} />
                    <Line type="monotone" dataKey="expenses" name="مصروفات" stroke="#c0392b" strokeWidth={2} />
                    <Line type="monotone" dataKey="profit" name="صافي" stroke={BRAND.navy} strokeWidth={2} strokeDasharray="6 4" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState title="لا توجد أشهر تشغيل بعد" text="ستظهر حركة التشغيل الشهرية هنا بمجرد بدء تسجيل بيانات يونيو وما بعده." />
              )}
            </PageSection>

            <PageSection title="تصنيف المصروفات" subtitle="أكبر فئات الإنفاق الحالية.">
              {safeArray(summary.expense_categories).length ? (
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie data={safeArray(summary.expense_categories).map(c => ({ name: catLabels[c.category] || c.category, value: c.total }))} dataKey="value" cx="50%" cy="50%" innerRadius={54} outerRadius={86} label={false}>
                      {safeArray(summary.expense_categories).map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={value => `${fmt(value)} ج.م`} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState title="لا توجد مصروفات مصنفة" text="سيتولد هذا التصنيف تلقائيًا عندما تتوفر مصروفات بفئات متعددة." />
              )}
            </PageSection>
          </div>

          <PageSection title="ملخص الأرباع التشغيلية" subtitle="استخدمنا الترقيم الميلادي مع توضيح بداية التشغيل في يونيو 2026.">
            {quarterRows.length ? (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc" }}>
                      {["الربع", "الأشهر", "إيراد", "مصروف", "صافي"].map(header => <th key={header} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{header}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {quarterRows.map((group) => (
                      <tr key={group.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                        <td style={{ padding: "14px", fontWeight: 900, color: BRAND.navy }}>{group.label}</td>
                        <td style={{ padding: "14px", color: "#667085" }}>{group.months.map(item => monthLabel(item.month)).join(" - ")}</td>
                        <td style={{ padding: "14px", fontWeight: 800, color: "#2d8659" }}>{usdFromEgp(group.totals.revenue, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(group.totals.revenue)}</div></td>
                        <td style={{ padding: "14px", fontWeight: 800, color: "#c0392b" }}>{usdFromEgp(group.totals.expenses, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(group.totals.expenses)}</div></td>
                        <td style={{ padding: "14px", fontWeight: 900, color: group.totals.profit >= 0 ? "#2d8659" : "#c0392b" }}>{usdFromEgp(group.totals.profit, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(group.totals.profit)}</div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title="لا يوجد ملخص ربعي بعد" text="سيظهر هنا بمجرد وجود أشهر تشغيل فعلية." />
            )}
          </PageSection>
        </div>
      )}

      {tab === "revenues" && (
        <PageSection title="كل الإيرادات" subtitle="فلترة حسب التاريخ أو المصدر.">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 16 }}>
            <Input label="من تاريخ" type="date" value={revenueFilter.from} onChange={e => setRevenueFilter({ ...revenueFilter, from: e.target.value })} />
            <Input label="إلى تاريخ" type="date" value={revenueFilter.to} onChange={e => setRevenueFilter({ ...revenueFilter, to: e.target.value })} />
            <Select label="الفئة" value={revenueFilter.source} onChange={e => setRevenueFilter({ ...revenueFilter, source: e.target.value })} options={[{ value: "all", label: "كل المصادر" }, ...Object.entries(srcLabels).map(([value, label]) => ({ value, label }))]} />
          </div>
          {filteredRevenues.length ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {["التاريخ", "المصدر", "الوصف", "العميل", "المبلغ", ""].map(header => <th key={header} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{header}</th>)}
                </tr>
              </thead>
              <tbody>
                {filteredRevenues.map((item) => (
                  <tr key={item.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "12px 14px" }}>{item.date}</td>
                    <td style={{ padding: "12px 14px" }}><Badge text={srcLabels[item.source] || item.source} color="#2d8659" /></td>
                    <td style={{ padding: "12px 14px" }}>{item.description}</td>
                    <td style={{ padding: "12px 14px" }}>{item.client_name || "—"}</td>
                    <td style={{ padding: "12px 14px", fontWeight: 900, color: "#2d8659" }}>{usdFromEgp(item.total_egp, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.total_egp)}</div></td>
                    <td style={{ padding: "12px 14px" }}>
                      {!isTrainingSupervisor && <button onClick={() => { setForm(item); setModal("revenue"); }} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16 }}>✏️</button>}
                      {!isTrainingSupervisor && <button onClick={() => deleteItem("revenues", item.id)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, marginRight: 8 }}>🗑</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState title="لا توجد إيرادات مطابقة" text="جرّب تغيير الفلاتر أو أضف إيرادًا جديدًا." />
          )}
        </PageSection>
      )}

      {tab === "expenses" && (
        <PageSection title="كل المصروفات" subtitle="المصروفات هنا شاملة التأسيس والتشغيل مع إمكان الفلترة.">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 16 }}>
            <Input label="من تاريخ" type="date" value={expenseFilter.from} onChange={e => setExpenseFilter({ ...expenseFilter, from: e.target.value })} />
            <Input label="إلى تاريخ" type="date" value={expenseFilter.to} onChange={e => setExpenseFilter({ ...expenseFilter, to: e.target.value })} />
            <Select label="الفئة" value={expenseFilter.category} onChange={e => setExpenseFilter({ ...expenseFilter, category: e.target.value })} options={[{ value: "all", label: "كل الفئات" }, ...Object.entries(catLabels).map(([value, label]) => ({ value, label }))]} />
          </div>
          {filteredExpenses.length ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {["التاريخ", "الفئة", "الوصف", "النوع", "المبلغ", ""].map(header => <th key={header} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{header}</th>)}
                </tr>
              </thead>
              <tbody>
                {filteredExpenses.map((item) => (
                  <tr key={item.id} style={{ borderBottom: "1px solid #f3f4f6", opacity: item.is_business === false ? 0.55 : 1 }}>
                    <td style={{ padding: "12px 14px" }}>{item.date}</td>
                    <td style={{ padding: "12px 14px" }}><Badge text={catLabels[item.category] || item.category} color="#e8913a" /></td>
                    <td style={{ padding: "12px 14px" }}>{item.description}</td>
                    <td style={{ padding: "12px 14px" }}>{item.is_business === false ? <Badge text="شخصي" color="#9ca3af" /> : <Badge text="أعمال" color="#2d8659" />}</td>
                    <td style={{ padding: "12px 14px", fontWeight: 900, color: "#c0392b" }}>{usdFromEgp(item.total_egp, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.total_egp)}</div></td>
                    <td style={{ padding: "12px 14px" }}>
                      <button onClick={() => { setForm(item); setModal("expense"); }} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16 }}>✏️</button>
                      <button onClick={() => deleteItem("expenses", item.id)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, marginRight: 8 }}>🗑</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState title="لا توجد مصروفات مطابقة" text="عدّل الفلاتر أو أضف مصروفًا جديدًا." />
          )}
        </PageSection>
      )}

      {tab === "cashflow" && !isTrainingSupervisor && (
        <PageSection title="Cash Flow" subtitle="فصل واضح بين رأس المال المضخوخ، المسحوب، والرصيد المتاح.">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 16, marginBottom: 18 }}>
            <KPICard label="إجمالي رأس المال المضخوخ" value={usdFromEgp(cashflow.capital_in, rate)} sub={egpLabel(cashflow.capital_in)} color="#2d8659" />
            <KPICard label="المصروف المسحوب من رأس المال" value={usdFromEgp(cashflow.cash_out, rate)} sub={egpLabel(cashflow.cash_out)} color="#c0392b" />
            <KPICard label="الرصيد المتاح" value={fmtUSD(cashflow.balance_usd)} sub={egpLabel(cashflow.balance_egp)} color={BRAND.navy} />
          </div>
          {safeArray(cashflow.transactions).length ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {["التاريخ", "النوع", "المصدر", "الوصف", "المبلغ", ""].map(header => <th key={header} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{header}</th>)}
                </tr>
              </thead>
              <tbody>
                {safeArray(cashflow.transactions).map((item) => (
                  <tr key={item.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "12px 14px" }}>{item.date}</td>
                    <td style={{ padding: "12px 14px" }}><Badge text={cashKindLabels[item.kind] || item.kind} color={item.kind === "capital_in" ? "#2d8659" : "#c0392b"} /></td>
                    <td style={{ padding: "12px 14px" }}>{item.source || "—"}</td>
                    <td style={{ padding: "12px 14px" }}>{item.description || "—"}</td>
                    <td style={{ padding: "12px 14px", fontWeight: 900, color: item.kind === "capital_in" ? "#2d8659" : "#c0392b" }}>{usdFromEgp(item.total_egp, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.total_egp)}</div></td>
                    <td style={{ padding: "12px 14px" }}><button onClick={() => { setForm(item); setModal("cashflow"); }} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16 }}>✏️</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState title="لا توجد حركات Cash Flow" text="أضف أول حركة ضخ أو سحب لتظهر هنا." />
          )}
        </PageSection>
      )}

      {tab === "monthly" && (
        <PageSection title="عرض شهري" subtitle="نعرض فقط الأشهر التي تحتوي على بيانات فعلية، بدون أشهر مستقبلية فارغة.">
          <div style={{ maxWidth: 280, marginBottom: 18 }}>
            <Select label="اختر شهرًا" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)} options={monthOptions.length ? monthOptions.map(item => ({ value: item, label: monthLabel(item) })) : [{ value: "", label: "لا توجد أشهر متاحة" }]} />
          </div>
          {selectedMonth ? (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14, marginBottom: 18 }}>
                <KPICard label="إيرادات الشهر" value={usdFromEgp(sumBy(monthRevenues, item => item.total_egp), rate)} sub={egpLabel(sumBy(monthRevenues, item => item.total_egp))} color="#2d8659" />
                <KPICard label="مصروفات الشهر" value={usdFromEgp(sumBy(monthExpenses, item => item.total_egp), rate)} sub={egpLabel(sumBy(monthExpenses, item => item.total_egp))} color="#c0392b" />
                <KPICard label="مستحقات الشهر" value={usdFromEgp(sumBy(monthPayouts, item => item.total_egp), rate)} sub={egpLabel(sumBy(monthPayouts, item => item.total_egp))} color="#8e44ad" />
                {!isTrainingSupervisor && <KPICard label="حركة الكاش" value={usdFromEgp(sumBy(monthCash, item => item.total_egp), rate)} sub={`${monthCash.length} حركة`} color={BRAND.navy} />}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
                <PageSection title="إيرادات الشهر">
                  {monthRevenues.length ? monthRevenues.map(item => <div key={item.id} style={{ padding: "10px 0", borderTop: "1px solid #f3f4f6", fontSize: 13 }}><strong>{item.description || srcLabels[item.source]}</strong><div style={{ color: "#667085", marginTop: 4 }}>{usdFromEgp(item.total_egp, rate)} - {egpLabel(item.total_egp)}</div></div>) : <EmptyState title="لا توجد إيرادات" text="لم تُسجل إيرادات في هذا الشهر." />}
                </PageSection>
                <PageSection title="مصروفات الشهر">
                  {monthExpenses.length ? monthExpenses.map(item => <div key={item.id} style={{ padding: "10px 0", borderTop: "1px solid #f3f4f6", fontSize: 13 }}><strong>{item.description}</strong><div style={{ color: "#667085", marginTop: 4 }}>{catLabels[item.category] || item.category} - {egpLabel(item.total_egp)}</div></div>) : <EmptyState title="لا توجد مصروفات" text="لم تُسجل مصروفات في هذا الشهر." />}
                </PageSection>
              </div>
            </div>
          ) : (
            <EmptyState title="لا توجد بيانات شهرية" text="عندما تُسجل أول بيانات تشغيل فعلية، ستظهر هنا تلقائيًا." />
          )}
        </PageSection>
      )}

      <Modal open={modal === "revenue"} onClose={() => setModal(null)} title={form.id ? "تعديل إيراد" : "إيراد جديد"}>
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        <Select label="المصدر" value={form.source || "course"} onChange={e => setForm({ ...form, source: e.target.value })} options={Object.entries(srcLabels).map(([value, label]) => ({ value, label }))} />
        <Input label="الوصف" value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })} />
        <Input label="اسم العميل" value={form.client_name || ""} onChange={e => setForm({ ...form, client_name: e.target.value })} />
        <CurrencyFields form={form} setForm={setForm} rate={rate} />
        <Select label="طريقة الدفع" value={form.payment_method || "wise"} onChange={e => setForm({ ...form, payment_method: e.target.value })} options={[{ value: "wise", label: "Wise" }, { value: "bank_transfer", label: "تحويل بنكي" }, { value: "cash", label: "كاش" }, { value: "stripe", label: "Stripe" }]} />
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={saveRevenue} color="#2d8659" style={{ width: "100%", marginTop: 8 }}>حفظ الإيراد</Btn>
      </Modal>

      <Modal open={modal === "expense"} onClose={() => setModal(null)} title={form.id ? "تعديل مصروف" : "مصروف جديد"}>
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        <Select label="الفئة" value={form.category || "tools"} onChange={e => setForm({ ...form, category: e.target.value })} options={Object.entries(catLabels).map(([value, label]) => ({ value, label }))} />
        <Input label="الوصف" value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })} />
        <CurrencyFields form={form} setForm={setForm} rate={rate} />
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>
            <input type="checkbox" checked={form.is_business !== false} onChange={e => setForm({ ...form, is_business: e.target.checked })} style={{ marginLeft: 8 }} />
            مصروف أعمال
          </label>
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>
            <input type="checkbox" checked={!!form.cash_impact} onChange={e => setForm({ ...form, cash_impact: e.target.checked })} style={{ marginLeft: 8 }} />
            خصم من Cash Flow
          </label>
        </div>
        <Input label="مدفوع بواسطة" value={form.paid_by || ""} onChange={e => setForm({ ...form, paid_by: e.target.value })} />
        <Btn onClick={saveExpense} color="#c0392b" style={{ width: "100%", marginTop: 8 }}>حفظ المصروف</Btn>
      </Modal>

      <Modal open={modal === "cashflow"} onClose={() => setModal(null)} title={form.id ? "تعديل حركة Cash Flow" : "حركة Cash Flow"}>
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        <Select label="النوع" value={form.kind || "capital_in"} onChange={e => setForm({ ...form, kind: e.target.value })} options={Object.entries(cashKindLabels).map(([value, label]) => ({ value, label }))} />
        <Input label="المصدر / الشريك" value={form.source || ""} onChange={e => setForm({ ...form, source: e.target.value })} />
        <Input label="الوصف" value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })} />
        <CurrencyFields form={form} setForm={setForm} rate={rate} />
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={saveCashflow} color={BRAND.navy} style={{ width: "100%", marginTop: 8 }}>حفظ الحركة</Btn>
      </Modal>
    </div>
  );
}

function FoundationPage() {
  const { loading, error, revenues, expenses, summary, reload } = useFinanceData();
  const [tab, setTab] = useState("all");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({ entryType: "expense", date: "2026-05-31" });

  if (loading) return <PageLoader />;
  if (error || !summary) return <PageError message={error || "تعذر تحميل مرحلة التأسيس."} onRetry={reload} />;

  const rate = Number(summary.exchange_rate || 50);
  const foundationRevenues = revenues.filter(item => isPreLaunchDate(item.date));
  const foundationExpenses = expenses.filter(item => isPreLaunchDate(item.date));
  const foundationEntries = [
    ...foundationRevenues.map(item => ({ ...item, entryType: "revenue", amount: item.total_egp })),
    ...foundationExpenses.map(item => ({ ...item, entryType: "expense", amount: item.total_egp })),
  ].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const foundationMonths = safeArray(summary.monthly).filter(item => item.period === "pre_launch");
  const categoryPie = Object.values(foundationExpenses.reduce((acc, item) => {
    const key = item.category || "other";
    if (!acc[key]) acc[key] = { name: catLabels[key] || key, value: 0 };
    acc[key].value += Number(item.total_egp || 0);
    return acc;
  }, {}));

  const saveEntry = async () => {
    if (form.entryType === "revenue") {
      if (form.id) await api.put(`/revenues/${form.id}`, form);
      else await api.post("/revenues", { ...form, source: form.source || "other" });
    } else {
      if (form.id) await api.put(`/expenses/${form.id}`, form);
      else await api.post("/expenses", { ...form, is_business: true });
    }
    setModal(null);
    setForm({ entryType: "expense", date: "2026-05-31" });
    reload();
  };

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy, margin: 0 }}>مرحلة التأسيس</h1>
        <div style={{ marginTop: 8, fontSize: 13, color: "#667085", lineHeight: 1.8 }}>
          هذه المرحلة تشمل كل المصروفات والإيرادات قبل بدء التشغيل الفعلي في يونيو 2026، ولا تدخل في حساب الأرباح التشغيلية الجارية.
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 16, marginBottom: 20 }}>
        <KPICard label="إجمالي مصروفات التأسيس" value={usdFromEgp(summary.pre_launch?.expenses, rate)} sub={egpLabel(summary.pre_launch?.expenses)} color="#c0392b" />
        <KPICard label="إيرادات التأسيس" value={usdFromEgp(summary.pre_launch?.revenue, rate)} sub={egpLabel(summary.pre_launch?.revenue)} color="#2d8659" />
        <KPICard label="صافي التأسيس" value={usdFromEgp(summary.pre_launch?.profit, rate)} sub={egpLabel(summary.pre_launch?.profit)} color={summary.pre_launch?.profit >= 0 ? "#2d8659" : BRAND.navy} />
        <KPICard label="عدد الأشهر" value={foundationMonths.length} sub={`من ${foundationMonths[0]?.month || "—"} إلى ${foundationMonths[foundationMonths.length - 1]?.month || "—"}`} color={BRAND.gold} />
      </div>

      <PageSection title="الخط الزمني التأسيسي" subtitle="الأشهر التي تحتوي على حركة فعلية تظهر بأرقامها، والفارغ يبقى هادئًا بصريًا.">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
          {foundationMonths.map((item) => (
            <div key={item.month} style={{ border: "1px solid #eee", borderRadius: 12, padding: 14, background: item.revenue || item.expenses ? "#fff" : "#f8fafc" }}>
              <div style={{ fontWeight: 900, color: BRAND.navy, fontSize: 13 }}>{monthLabel(item.month)}</div>
              <div style={{ marginTop: 8, fontSize: 12, color: "#667085" }}>مصروف {egpLabel(item.expenses)}</div>
              <div style={{ marginTop: 4, fontSize: 12, color: item.profit >= 0 ? "#2d8659" : "#c0392b" }}>صافي {egpLabel(item.profit)}</div>
            </div>
          ))}
        </div>
      </PageSection>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.8fr) minmax(300px, 1fr)", gap: 20 }}>
        <PageSection title="تفاصيل التأسيس" subtitle="كل البنود قبل يونيو 2026 في جدول واحد." action={<div style={{ display: "flex", gap: 10, alignItems: "center" }}><TabBar tabs={[{ id: "all", label: "الكل" }, { id: "expense", label: "مصروفات" }, { id: "revenue", label: "إيرادات" }]} active={tab} onChange={setTab} /><Btn color="#c0392b" onClick={() => { setForm({ entryType: tab === "revenue" ? "revenue" : "expense", date: "2026-05-31", amount_egp: 0, amount_usd: 0 }); setModal("entry"); }}>+ بند تأسيسي جديد</Btn></div>}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {["التاريخ", "الوصف", "الفئة", "النوع", "المبلغ"].map(header => <th key={header} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{header}</th>)}
                </tr>
              </thead>
              <tbody>
                {foundationEntries.filter(item => tab === "all" || item.entryType === tab).map((item) => (
                  <tr key={`${item.entryType}-${item.id}`} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "12px 14px" }}>{item.date}</td>
                    <td style={{ padding: "12px 14px" }}>{item.description || item.client_name || "—"}</td>
                    <td style={{ padding: "12px 14px" }}>{item.entryType === "expense" ? (catLabels[item.category] || item.category) : (srcLabels[item.source] || item.source)}</td>
                    <td style={{ padding: "12px 14px" }}>{item.entryType === "expense" ? <Badge text="مصروف" color="#c0392b" /> : <Badge text="إيراد" color="#2d8659" />}</td>
                    <td style={{ padding: "12px 14px", fontWeight: 900, color: item.entryType === "expense" ? "#c0392b" : "#2d8659" }}>{usdFromEgp(item.amount, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.amount)}</div><div style={{ marginTop: 8, display: "flex", gap: 8 }}><button onClick={() => { setForm({ ...item, entryType: item.entryType, amount_egp: item.amount_egp || item.amount, amount_usd: item.amount_usd || 0 }); setModal("entry"); }} style={{ background: "none", border: "none", cursor: "pointer" }}>✏️</button><button onClick={async () => { if (confirm("حذف؟")) { await api.del(`/${item.entryType === "expense" ? "expenses" : "revenues"}/${item.id}`); reload(); } }} style={{ background: "none", border: "none", cursor: "pointer" }}>🗑</button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </PageSection>

        <PageSection title="تصنيف مصروفات التأسيس">
          {categoryPie.length ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={categoryPie} dataKey="value" cx="50%" cy="50%" innerRadius={54} outerRadius={88} label={false}>
                  {categoryPie.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={value => `${fmt(value)} ج.م`} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState title="لا توجد مصروفات تأسيسية" text="سيظهر التصنيف هنا تلقائيًا عندما تتوفر بنود تأسيسية." />
          )}
        </PageSection>
      </div>

      <Modal open={modal === "entry"} onClose={() => setModal(null)} title={form.id ? "تعديل بند تأسيسي" : "بند تأسيسي جديد"}>
        <Select label="النوع" value={form.entryType || "expense"} onChange={e => setForm({ ...form, entryType: e.target.value })} options={[{ value: "expense", label: "مصروف" }, { value: "revenue", label: "إيراد" }]} />
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        {form.entryType === "expense" ? <Select label="الفئة" value={form.category || "tools"} onChange={e => setForm({ ...form, category: e.target.value })} options={Object.entries(catLabels).map(([value, label]) => ({ value, label }))} /> : <Select label="المصدر" value={form.source || "other"} onChange={e => setForm({ ...form, source: e.target.value })} options={Object.entries(srcLabels).map(([value, label]) => ({ value, label }))} />}
        <Input label="الوصف" value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })} />
        {form.entryType === "revenue" && <Input label="اسم العميل" value={form.client_name || ""} onChange={e => setForm({ ...form, client_name: e.target.value })} />}
        <CurrencyFields form={form} setForm={setForm} rate={rate} />
        <Btn onClick={saveEntry} color={form.entryType === "expense" ? "#c0392b" : "#2d8659"} style={{ width: "100%" }}>حفظ البند</Btn>
      </Modal>
    </div>
  );
}

// الأصول — بند مالي (قيمة + إيجار شهري)، اتنقل لقسم «المالية» كتبويب مستقل.
function AssetsPanel() {
  const { loading, error, assets, summary, reload } = useFinanceData();
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});
  if (loading) return <PageLoader />;
  if (error || !summary) return <PageError message={error || "تعذر تحميل الأصول."} onRetry={reload} />;
  const rate = Number(summary.exchange_rate || 50);
  const saveAsset = async () => {
    if (form.id) await api.put(`/assets/${form.id}`, form);
    else await api.post("/assets", form);
    setModal(false); setForm({}); reload();
  };
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, marginBottom: 20 }}>
        <KPICard label="إجمالي القيمة المرجعية" value={usdFromEgp(sumBy(assets, item => item.value_egp), rate)} sub={egpLabel(sumBy(assets, item => item.value_egp))} color={BRAND.navy} />
        <KPICard label="إجمالي الإيجار الشهري" value={usdFromEgp(sumBy(assets, item => item.monthly_rent_egp), rate)} sub={egpLabel(sumBy(assets, item => item.monthly_rent_egp))} color={BRAND.gold} />
      </div>
      <PageSection title="الأصول" action={<Btn color={BRAND.gold} onClick={() => { setForm({ value_egp: 0, monthly_rent_egp: 0 }); setModal(true); }} style={{ color: BRAND.navy }}>+ أصل جديد</Btn>}>
        {assets.length ? (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ background: "#fff8e8" }}>
                {["الأصل", "المالك", "القيمة", "الإيجار الشهري", "ملاحظات"].map(header => <th key={header} style={{ padding: "12px 14px", textAlign: "right", color: BRAND.navy, borderBottom: "1px solid #e6d7a8" }}>{header}</th>)}
              </tr>
            </thead>
            <tbody>
              {assets.map((item) => (
                <tr key={item.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ padding: "12px 14px", fontWeight: 900 }}>{item.name}</td>
                  <td style={{ padding: "12px 14px" }}>{item.owner}</td>
                  <td style={{ padding: "12px 14px", fontWeight: 800 }}>{usdFromEgp(item.value_egp, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.value_egp)}</div></td>
                  <td style={{ padding: "12px 14px", fontWeight: 900, color: BRAND.gold }}>{usdFromEgp(item.monthly_rent_egp, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.monthly_rent_egp)}</div></td>
                  <td style={{ padding: "12px 14px" }}>{item.notes || "—"}<div style={{ marginTop: 8, display: "flex", gap: 8 }}><button onClick={() => { setForm(item); setModal(true); }} style={{ background: "none", border: "none", cursor: "pointer" }}>✏️</button><button onClick={async () => { if (confirm("حذف؟")) { await api.del(`/assets/${item.id}`); reload(); } }} style={{ background: "none", border: "none", cursor: "pointer" }}>🗑</button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState title="لا توجد أصول مسجلة" text="عند تسجيل أصول جديدة ستظهر هنا." />
        )}
      </PageSection>
      <Modal open={modal} onClose={() => setModal(false)} title={form.id ? "تعديل أصل" : "أصل جديد"}>
        <Input label="اسم الأصل" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })} />
        <Input label="المالك" value={form.owner || ""} onChange={e => setForm({ ...form, owner: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="القيمة (ج.م)" type="number" value={form.value_egp || 0} onChange={e => setForm({ ...form, value_egp: +e.target.value })} />
          <Input label="الإيجار الشهري (ج.م)" type="number" value={form.monthly_rent_egp || 0} onChange={e => setForm({ ...form, monthly_rent_egp: +e.target.value })} />
        </div>
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={saveAsset} color={BRAND.gold} style={{ width: "100%", color: BRAND.navy }}>حفظ الأصل</Btn>
      </Modal>
    </div>
  );
}

// "الفريق والمدربون" (section="team") = المدربون والإشراف (مالي) + روستر المدربين
// المعتمدين (تشغيلي من المنصة). "الشركاء" (section="partners") = الشركاء لوحدهم.
function TeamPartnersPage({ section = "team" }) {
  const user = useAuth();
  const isTrainingSupervisor = user?.role === "training_supervisor";
  const showPartners = section === "partners";
  const { loading, error, partners, payouts, summary, reload } = useFinanceData();
  const [roster, setRoster] = useState([]);
  useEffect(() => {
    if (!showPartners && !isTrainingSupervisor) api.get("/platform-users").then(r => { if (r && !r.error) setRoster(r.users || []); });
  }, [showPartners, isTrainingSupervisor]);
  const tabs = showPartners
    ? [{ id: "partners", label: "الشركاء" }]
    : (isTrainingSupervisor
        ? [{ id: "payouts", label: "المدربون والإشراف" }]
        : [{ id: "payouts", label: "المدربون والإشراف" }, { id: "trainers", label: "المدربون المعتمدون" }]);
  const [tab, setTab] = useState(tabs[0].id);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});

  if (loading) return <PageLoader />;
  if (error || !summary) return <PageError message={error || "تعذر تحميل البيانات."} onRetry={reload} />;

  const rate = Number(summary.exchange_rate || 50);
  const partnerPie = partners.map(item => ({ name: item.name, value: Number(item.equity_percent || 0) }));
  const trainers = roster.filter(u => u.trainer_status === "approved" || u.trainer_status === "pending");

  const savePartner = async () => {
    const totalWithoutCurrent = partners.filter(item => item.id !== form.id).reduce((sum, item) => sum + Number(item.equity_percent || 0), 0);
    if (totalWithoutCurrent + Number(form.equity_percent || 0) > 100) {
      alert("مجموع نسب الملكية يجب ألا يتجاوز 100%");
      return;
    }
    if (form.id) await api.put(`/partners/${form.id}`, form);
    else await api.post("/partners", form);
    setModal(null); setForm({}); reload();
  };
  const savePayout = async () => {
    if (form.id) await api.put(`/payouts/${form.id}`, form);
    else await api.post("/payouts", form);
    setModal(null); setForm({}); reload();
  };

  return (
    <div>
      <div style={{ marginBottom: 18 }}>
        <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy, margin: 0 }}>{showPartners ? "الشركاء" : "الفريق والمدربون"}</h1>
        <div style={{ marginTop: 6, fontSize: 13, color: "#667085" }}>{showPartners ? "شركاء الشركة ونِسب الملكية والأرباح ومساهمات رأس المال." : "فريق العمل والمدربون والإشراف — أداؤهم ونِسبهم المالية في مكان واحد لاتخاذ القرار."}</div>
      </div>

      <TabBar tabs={tabs} active={tab} onChange={setTab} />

      {tab === "partners" && showPartners && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.8fr) minmax(300px, 1fr)", gap: 20 }}>
          <PageSection title="جدول الشركاء" action={<Btn color="#5b6abf" onClick={() => { setForm({ equity_percent: 0, profit_share_percent: 0, capital_egp: 0, capital_usd: 0 }); setModal("partner"); }}>+ شريك جديد</Btn>}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {["الشريك", "الدور", "نسبة الملكية", "نسبة الأرباح", "مساهمة رأس مال", "ملاحظات"].map(header => <th key={header} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{header}</th>)}
                </tr>
              </thead>
              <tbody>
                {partners.map((item) => (
                  <tr key={item.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "12px 14px", fontWeight: 900 }}>{item.name}</td>
                    <td style={{ padding: "12px 14px" }}>{item.role}</td>
                    <td style={{ padding: "12px 14px" }}>{item.equity_percent}%</td>
                    <td style={{ padding: "12px 14px" }}>{item.profit_share_percent}%</td>
                    <td style={{ padding: "12px 14px", fontWeight: 800 }}>{usdFromEgp(item.total_capital_egp, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.total_capital_egp)}</div></td>
                    <td style={{ padding: "12px 14px" }}>{item.notes || "—"}<div style={{ marginTop: 8, display: "flex", gap: 8 }}><button onClick={() => { setForm(item); setModal("partner"); }} style={{ background: "none", border: "none", cursor: "pointer" }}>✏️</button><button onClick={async () => { if (confirm("حذف؟")) { await api.del(`/partners/${item.id}`); reload(); } }} style={{ background: "none", border: "none", cursor: "pointer" }}>🗑</button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </PageSection>

          <PageSection title="هيكل الملكية">
            {partnerPie.length ? (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={partnerPie} dataKey="value" cx="50%" cy="50%" innerRadius={54} outerRadius={88} label={false}>
                    {partnerPie.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={value => `${value}%`} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState title="لا توجد بيانات ملكية" text="أضف أو حدّث بيانات الشركاء لتظهر هنا." />
            )}
          </PageSection>
        </div>
      )}

      {tab === "payouts" && (
        <PageSection title="المدربين والإشراف والأفلييت" subtitle="هذه البيانات مرتبطة بالدورات والتنفيذ، وليست تفصيلًا شهريًا ثابتًا." action={<Btn color="#8e44ad" onClick={() => { setForm({ role: "trainer", status: "accrued", percent: 0, amount_egp: 0, amount_usd: 0, basis_amount_egp: 0, date: new Date().toISOString().split("T")[0] }); setModal("payout"); }}>+ مدرب/مشرف/أفلييت جديد</Btn>}>
          {payouts.length ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {["الاسم", "النوع", "مرتبط بـ", "النسبة", "المستحق", "الحالة"].map(header => <th key={header} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{header}</th>)}
                </tr>
              </thead>
              <tbody>
                {payouts.map((item) => (
                  <tr key={item.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "12px 14px", fontWeight: 900 }}>{item.name}</td>
                    <td style={{ padding: "12px 14px" }}><Badge text={payoutRoleLabels[item.role] || item.role} color="#8e44ad" /></td>
                    <td style={{ padding: "12px 14px" }}>{item.related_to || "—"}</td>
                    <td style={{ padding: "12px 14px" }}>{item.percent}%</td>
                    <td style={{ padding: "12px 14px", fontWeight: 900, color: "#8e44ad" }}>{usdFromEgp(item.total_egp, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.total_egp)}</div></td>
                    <td style={{ padding: "12px 14px" }}>{item.status}<div style={{ marginTop: 8, display: "flex", gap: 8 }}><button onClick={() => { setForm(item); setModal("payout"); }} style={{ background: "none", border: "none", cursor: "pointer" }}>✏️</button><button onClick={async () => { if (confirm("حذف؟")) { await api.del(`/payouts/${item.id}`); reload(); } }} style={{ background: "none", border: "none", cursor: "pointer" }}>🗑</button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState title="لا توجد مستحقات مسجلة" text="أضف مدربًا أو مشرفًا أو أفلييت ليظهر هنا." />
          )}
        </PageSection>
      )}

      {tab === "trainers" && (
        <PageSection title="المدربون المعتمدون" subtitle="روستر المدربين القادم من المنصة (المعتمدون والمعلّقون) — الجانب التشغيلي مقابل النِسب المالية في تبويب «المدربون والإشراف».">
          {trainers.length ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {["المدرب", "الإيميل", "التليفون", "الحالة"].map(header => <th key={header} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{header}</th>)}
                </tr>
              </thead>
              <tbody>
                {trainers.map((u) => (
                  <tr key={u.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "12px 14px", fontWeight: 900 }}>{u.full_name || "—"}</td>
                    <td style={{ padding: "12px 14px", fontSize: 13, color: "#475467" }}>{u.email}</td>
                    <td style={{ padding: "12px 14px", fontSize: 13, color: "#475467", direction: "ltr", textAlign: "right" }}>{u.phone || "—"}</td>
                    <td style={{ padding: "12px 14px" }}><Badge text={u.trainer_status === "approved" ? "معتمد" : "معلّق"} color={u.trainer_status === "approved" ? "#2d8659" : "#e8913a"} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState title="لا يوجد مدربون بعد" text="المدربون المعتمدون من قسم «الدورات ← طلبات المدربين» سيظهرون هنا." />
          )}
        </PageSection>
      )}

      <Modal open={modal === "partner"} onClose={() => setModal(null)} title={form.id ? "تعديل شريك" : "شريك جديد"}>
        <Input label="اسم الشريك" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })} />
        <Input label="الدور" value={form.role || ""} onChange={e => setForm({ ...form, role: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="نسبة الملكية %" type="number" value={form.equity_percent || 0} onChange={e => setForm({ ...form, equity_percent: +e.target.value })} />
          <Input label="نسبة الأرباح %" type="number" value={form.profit_share_percent || 0} onChange={e => setForm({ ...form, profit_share_percent: +e.target.value })} />
        </div>
        <CurrencyFields form={form} setForm={setForm} rate={rate} egpKey="capital_egp" usdKey="capital_usd" egpLabel="مساهمة رأس مال (ج.م)" usdLabel="مساهمة رأس مال ($)" />
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={savePartner} color="#5b6abf" style={{ width: "100%" }}>حفظ الشريك</Btn>
      </Modal>

      <Modal open={modal === "payout"} onClose={() => setModal(null)} title={form.id ? "تعديل مستحق" : "مدرب / مشرف / أفلييت"}>
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        <Input label="الاسم" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })} />
        <Select label="النوع" value={form.role || "trainer"} onChange={e => setForm({ ...form, role: e.target.value })} options={Object.entries(payoutRoleLabels).map(([value, label]) => ({ value, label }))} />
        <Input label="مرتبط بدورة" value={form.related_to || ""} onChange={e => setForm({ ...form, related_to: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="النسبة %" type="number" value={form.percent || 0} onChange={e => setForm({ ...form, percent: +e.target.value })} />
          <Input label="قيمة الأساس" type="number" value={form.basis_amount_egp || 0} onChange={e => setForm({ ...form, basis_amount_egp: +e.target.value })} />
        </div>
        <CurrencyFields form={form} setForm={setForm} rate={rate} />
        <Select label="الحالة" value={form.status || "accrued"} onChange={e => setForm({ ...form, status: e.target.value })} options={[{ value: "accrued", label: "مستحق" }, { value: "paid", label: "مدفوع" }, { value: "waived", label: "متنازل عنه" }]} />
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={savePayout} color="#8e44ad" style={{ width: "100%" }}>حفظ</Btn>
      </Modal>
    </div>
  );
}

function TargetsPage() {
  const { loading, error, forecast, summary, reload } = useFinanceData();

  const updateForecast = async (item, patch) => {
    await api.put(`/forecast/${item.id}`, { ...item, ...patch });
    reload();
  };

  if (loading) return <PageLoader />;
  if (error || !summary) return <PageError message={error || "تعذر تحميل الأهداف والتوقعات."} onRetry={reload} />;

  const rate = Number(summary.exchange_rate || 50);
  const actualMap = safeObject(safeArray(summary.monthly).reduce((acc, item) => {
    acc[item.month] = item;
    return acc;
  }, {}));
  const chartRows = forecast.map((item) => ({ month: item.month, target: item.revenue_egp || 0, actual: actualMap[item.month]?.revenue || 0 }));

  return (
    <div>
      <div style={{ marginBottom: 18 }}>
        <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy, margin: 0 }}>الأهداف والتوقعات</h1>
        <div style={{ marginTop: 6, fontSize: 13, color: "#667085" }}>من هنا نتابع المستهدف الشهري ونقارنه بالفعلي، بدل وضعه داخل تفاصيل شهر واحد.</div>
      </div>

      <PageSection title="المستهدف مقابل الفعلي" subtitle="خط مزدوج لقراءة التقدم نحو المستهدف الشهري.">
        {chartRows.length ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartRows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={value => `${fmt(value)} ج.م`} />
              <Legend />
              <Line type="monotone" dataKey="target" name="المستهدف" stroke={BRAND.gold} strokeWidth={2} />
              <Line type="monotone" dataKey="actual" name="الفعلي" stroke="#2d8659" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState title="لا توجد أهداف مسجلة" text="أضف أو حدّث التوقعات الشهرية لتظهر المقارنة هنا." />
        )}
      </PageSection>

      <PageSection title="جدول الأهداف الشهرية">
        {forecast.length ? (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#f8fafc" }}>
                {["الشهر", "Target Revenue", "Marketing", "دورات", "طلاب", "مصروفات متوقعة", "EBITDA"].map(header => <th key={header} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{header}</th>)}
              </tr>
            </thead>
            <tbody>
              {forecast.map((item) => (
                <tr key={item.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ padding: "12px 14px", fontWeight: 900 }}>{monthLabel(item.month)}</td>
                  <td style={{ padding: "12px 14px" }}><input type="number" value={item.revenue_egp || 0} onChange={e => updateForecast(item, { revenue_egp: +e.target.value })} style={{ width: 120, border: "1px solid #e5e7eb", borderRadius: 8, padding: 8 }} /></td>
                  <td style={{ padding: "12px 14px" }}>{usdFromEgp(item.marketing_egp, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.marketing_egp)}</div></td>
                  <td style={{ padding: "12px 14px" }}>{item.target_courses}</td>
                  <td style={{ padding: "12px 14px" }}>{item.target_students}</td>
                  <td style={{ padding: "12px 14px" }}>{usdFromEgp(item.total_expenses, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.total_expenses)}</div></td>
                  <td style={{ padding: "12px 14px", fontWeight: 900, color: item.ebitda >= 0 ? "#2d8659" : "#c0392b" }}>{usdFromEgp(item.ebitda, rate)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.ebitda)}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState title="لا توجد أهداف مستقبلية" text="بمجرد إضافة أهداف شهرية ستظهر هنا كاملة." />
        )}
      </PageSection>
    </div>
  );
}

// ============================================================
// MARKETING DASHBOARD
// ============================================================
function LegacyMarketingPage() {
  const [campaigns, setCampaigns] = useState([]);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});

  const load = () => api.get("/campaigns").then(data => setCampaigns(safeArray(data)));
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (form.id) await api.put(`/campaigns/${form.id}`, form);
    else await api.post("/campaigns", form);
    setModal(false); setForm({}); load();
  };

  const totals = {
    spent: campaigns.reduce((s, c) => s + (c.spent || 0), 0),
    leads: campaigns.reduce((s, c) => s + (c.leads || 0), 0),
    conversions: campaigns.reduce((s, c) => s + (c.conversions || 0), 0),
    revenue: campaigns.reduce((s, c) => s + (c.revenue_attributed || 0), 0),
  };
  totals.cpl = totals.leads ? totals.spent / totals.leads : 0;
  totals.cac = totals.conversions ? totals.spent / totals.conversions : 0;
  totals.roas = totals.spent ? totals.revenue / totals.spent : 0;
  totals.convRate = totals.leads ? (totals.conversions / totals.leads * 100) : 0;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f4c81" }}>التسويق والحملات</h1>
        <Btn onClick={() => { setForm({ platform: "facebook", status: "active", currency: "USD", start_date: new Date().toISOString().split("T")[0] }); setModal(true); }} color="#e8913a">+ حملة جديدة</Btn>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 24 }}>
        <KPICard icon="💸" label="إجمالي الإنفاق" value={fmtUSD(totals.spent)} color="#c0392b" />
        <KPICard icon="👤" label="Leads" value={totals.leads} sub={`CPL: ${fmtUSD(totals.cpl)}`} color="#e8913a" />
        <KPICard icon="🎯" label="Conversions" value={totals.conversions} sub={`CAC: ${fmtUSD(totals.cac)}`} color="#2d8659" />
        <KPICard icon="📈" label="ROAS" value={`${totals.roas.toFixed(1)}x`} sub={`${totals.convRate.toFixed(1)}% تحويل`} color="#0f4c81" />
        <KPICard icon="💰" label="إيراد من الحملات" value={fmtUSD(totals.revenue)} color="#d4a017" />
      </div>

      {campaigns.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
          <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>مقارنة الحملات</h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={campaigns.map(c => ({ name: c.name.substring(0, 15), spent: c.spent, revenue: c.revenue_attributed }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="spent" name="إنفاق" fill="#c0392b" radius={[4,4,0,0]} />
                <Bar dataKey="revenue" name="إيراد" fill="#2d8659" radius={[4,4,0,0]} />
                <Legend />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>توزيع الإنفاق بالمنصة</h3>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={campaigns.map(c => ({ name: platLabels[c.platform] || c.platform, value: c.spent || 0 }))} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name }) => name}>
                  {campaigns.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={v => fmtUSD(v)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead><tr style={{ background: "#f8fafc" }}>
            {["الحملة", "المنصة", "الحالة", "إنفاق", "Leads", "تحويلات", "إيراد", "ROAS", "توصية", ""].map(h => <th key={h} style={{ padding: "12px 14px", textAlign: "right", fontWeight: 600, color: "#6b7280", borderBottom: "1px solid #e5e7eb" }}>{h}</th>)}
          </tr></thead>
          <tbody>
            {campaigns.map(c => (
              <tr key={c.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "12px 14px", fontWeight: 600 }}>{c.name}</td>
                <td><Badge text={platLabels[c.platform] || c.platform} /></td>
                <td><Badge text={statusLabels[c.status] || c.status} color={c.status === "active" ? "#2d8659" : "#9ca3af"} /></td>
                <td>{fmtUSD(c.spent)}</td>
                <td>{c.leads}</td>
                <td>{c.conversions}</td>
                <td style={{ color: "#2d8659", fontWeight: 600 }}>{fmtUSD(c.revenue_attributed)}</td>
                <td style={{ fontWeight: 700 }}>{c.roas.toFixed(1)}x</td>
                <td><span style={{ color: recColors[c.recommendation], fontWeight: 700 }}>{recLabels[c.recommendation]}</span></td>
                <td>
                  <button onClick={() => { setForm(c); setModal(true); }} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14 }}>✏️</button>
                  <button onClick={async () => { if (confirm("حذف؟")) { await api.del(`/campaigns/${c.id}`); load(); }}} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14 }}>🗑</button>
                </td>
              </tr>
            ))}
            {campaigns.length === 0 && <tr><td colSpan={10} style={{ padding: 40, textAlign: "center", color: "#9ca3af" }}>لا توجد حملات بعد. أضف أول حملة إعلانية.</td></tr>}
          </tbody>
        </table>
      </div>

      <Modal open={modal} onClose={() => setModal(false)} title={form.id ? "تعديل حملة" : "حملة جديدة"}>
        <Input label="اسم الحملة" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Select label="المنصة" value={form.platform || "facebook"} onChange={e => setForm({ ...form, platform: e.target.value })} options={Object.entries(platLabels).map(([v, l]) => ({ value: v, label: l }))} />
          <Select label="الحالة" value={form.status || "active"} onChange={e => setForm({ ...form, status: e.target.value })} options={Object.entries(statusLabels).map(([v, l]) => ({ value: v, label: l }))} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="تاريخ البدء" type="date" value={form.start_date || ""} onChange={e => setForm({ ...form, start_date: e.target.value })} />
          <Input label="تاريخ النهاية" type="date" value={form.end_date || ""} onChange={e => setForm({ ...form, end_date: e.target.value })} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="الميزانية ($)" type="number" value={form.budget || 0} onChange={e => setForm({ ...form, budget: +e.target.value })} />
          <Input label="المنفق ($)" type="number" value={form.spent || 0} onChange={e => setForm({ ...form, spent: +e.target.value })} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          <Input label="Impressions" type="number" value={form.impressions || 0} onChange={e => setForm({ ...form, impressions: +e.target.value })} />
          <Input label="Clicks" type="number" value={form.clicks || 0} onChange={e => setForm({ ...form, clicks: +e.target.value })} />
          <Input label="Leads" type="number" value={form.leads || 0} onChange={e => setForm({ ...form, leads: +e.target.value })} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="تحويلات" type="number" value={form.conversions || 0} onChange={e => setForm({ ...form, conversions: +e.target.value })} />
          <Input label="إيراد من الحملة ($)" type="number" value={form.revenue_attributed || 0} onChange={e => setForm({ ...form, revenue_attributed: +e.target.value })} />
        </div>
        <Input label="الجمهور المستهدف" value={form.target_audience || ""} onChange={e => setForm({ ...form, target_audience: e.target.value })} />
        <Btn onClick={save} color="#e8913a" style={{ width: "100%", marginTop: 8 }}>💾 حفظ</Btn>
      </Modal>
    </div>
  );
}

// `only` splits this page: "campaigns" → التسويق (الحملات فقط);
// "investors" → جزء الاستثمار الإعلاني (يُركَّب داخل قسم «الاستثمار»).
function MarketingPage({ only = null }) {
  const [tab, setTab] = useState(only || "campaigns");
  const [campaigns, setCampaigns] = useState([]);
  const [courses, setCourses] = useState([]);
  const [investments, setInvestments] = useState([]);
  const [campaignModal, setCampaignModal] = useState(false);
  const [investmentModal, setInvestmentModal] = useState(false);
  const [calculatorOpen, setCalculatorOpen] = useState(false);
  const [campaignForm, setCampaignForm] = useState({});
  const [investmentForm, setInvestmentForm] = useState({});
  const [calculatorForm, setCalculatorForm] = useState(createCalculatorForm);
  const [simulation, setSimulation] = useState(null);

  const load = useCallback(() => {
    api.get("/campaigns").then(data => setCampaigns(safeArray(data)));
    api.get("/courses").then(data => setCourses(safeArray(data)));
    api.get("/investments").then(data => setInvestments(safeArray(data)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.post("/calculator/simulate", calculatorForm).then(data => setSimulation(safeObject(data)));
  }, [calculatorForm]);

  const saveCampaign = async () => {
    if (campaignForm.id) await api.put(`/campaigns/${campaignForm.id}`, campaignForm);
    else await api.post("/campaigns", campaignForm);
    setCampaignModal(false);
    setCampaignForm({});
    load();
  };

  const saveInvestment = async () => {
    if (!investmentForm.course_id) return alert("اختر الدورة أولًا.");
    if (!investmentForm.investor_name) return alert("اكتب اسم المستثمر.");
    if (investmentForm.id) await api.put(`/investments/${investmentForm.id}`, investmentForm);
    else await api.post("/investments", investmentForm);
    setInvestmentModal(false);
    setInvestmentForm({});
    load();
  };

  const totals = {
    spent: campaigns.reduce((s, c) => s + (c.spent || 0), 0),
    leads: campaigns.reduce((s, c) => s + (c.leads || 0), 0),
    conversions: campaigns.reduce((s, c) => s + (c.conversions || 0), 0),
    revenue: campaigns.reduce((s, c) => s + (c.revenue_attributed || 0), 0),
  };
  totals.cpl = totals.leads ? totals.spent / totals.leads : 0;
  totals.cac = totals.conversions ? totals.spent / totals.conversions : 0;
  totals.roas = totals.spent ? totals.revenue / totals.spent : 0;
  totals.convRate = totals.leads ? (totals.conversions / totals.leads * 100) : 0;

  const investmentTotals = {
    injected: investments.reduce((sum, item) => sum + (item.invested_total_egp || 0), 0),
    distributed: investments.reduce((sum, item) => sum + (item.due_egp || 0), 0),
    active: new Set(investments.filter(item => item.status !== "paid").map(item => item.investor_name)).size,
    avgRoi: investments.length ? investments.reduce((sum, item) => sum + (item.roi_percent || 0), 0) / investments.length : 0,
  };
  const selectedCalcCourse = courses.find((course) => course.id === Number(calculatorForm.course_id));
  const applySimulationToInvestment = () => {
    if (!calculatorForm.course_id) return alert("اختر الدورة أولًا حتى نربط الاستثمار بها.");
    setInvestmentForm({
      course_id: calculatorForm.course_id ? Number(calculatorForm.course_id) : "",
      investor_name: investmentForm.investor_name || "",
      amount_egp: Number(calculatorForm.investor_contribution_egp || 0),
      amount_usd: Math.round(Number(calculatorForm.investor_contribution_egp || 0) / 50),
      profit_percent: Number(calculatorForm.investor_percent || 0),
      status: "accrued",
      notes: `من الحاسبة: مساهمة ${egpLabel(calculatorForm.investor_contribution_egp)} من أصل ميزانية إعلان ${egpLabel(calculatorForm.total_ads_budget_egp)}${selectedCalcCourse ? ` لدورة ${selectedCalcCourse.title}` : ""}`,
    });
    setCalculatorOpen(false);
    setInvestmentModal(true);
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18, gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy, margin: 0 }}>{only === "investors" ? "الاستثمارات الإعلانية" : "التسويق"}</h1>
          <div style={{ marginTop: 6, fontSize: 13, color: "#667085" }}>{only === "investors" ? "كل استثمار إعلاني مرتبط بدورة ونسبته من أرباحها، مع حاسبة محاكاة التوزيع." : "متابعة الحملات وربطها بالدورات وقياس أدائها."}</div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          {only !== "investors" && <Btn onClick={() => { setCampaignForm({ platform: "facebook", status: "active", currency: "USD", start_date: new Date().toISOString().split("T")[0] }); setCampaignModal(true); }} color="#e8913a">+ حملة جديدة</Btn>}
          {only !== "campaigns" && <Btn onClick={() => { setInvestmentForm({ status: "accrued", profit_percent: 25, amount_usd: 500 }); setInvestmentModal(true); }} color={BRAND.navy}>+ استثمار جديد</Btn>}
        </div>
      </div>

      {!only && <TabBar tabs={[{ id: "campaigns", label: "الحملات" }, { id: "investors", label: "المستثمرين والمعلنين" }]} active={tab} onChange={setTab} />}

      {tab === "campaigns" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 24 }}>
            <KPICard icon="💸" label="إجمالي الإنفاق" value={fmtUSD(totals.spent)} color="#c0392b" />
            <KPICard icon="👤" label="Leads" value={totals.leads} sub={`CPL: ${fmtUSD(totals.cpl)}`} color="#e8913a" />
            <KPICard icon="🎯" label="Conversions" value={totals.conversions} sub={`CAC: ${fmtUSD(totals.cac)}`} color="#2d8659" />
            <KPICard icon="📈" label="ROAS" value={`${totals.roas.toFixed(1)}x`} sub={`${totals.convRate.toFixed(1)}% تحويل`} color={BRAND.navy} />
            <KPICard icon="💰" label="إيراد من الحملات" value={fmtUSD(totals.revenue)} color={BRAND.gold} />
          </div>

          {campaigns.length > 0 && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
              <PageSection title="مقارنة الحملات">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={campaigns.map(c => ({ name: c.name.substring(0, 15), spent: c.spent, revenue: c.revenue_attributed }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="spent" name="إنفاق" fill="#c0392b" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="revenue" name="إيراد" fill="#2d8659" radius={[4, 4, 0, 0]} />
                    <Legend />
                  </BarChart>
                </ResponsiveContainer>
              </PageSection>
              <PageSection title="توزيع الإنفاق بالمنصة">
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie data={campaigns.map(c => ({ name: platLabels[c.platform] || c.platform, value: c.spent || 0 }))} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name }) => name}>
                      {campaigns.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={v => fmtUSD(v)} />
                  </PieChart>
                </ResponsiveContainer>
              </PageSection>
            </div>
          )}

          <PageSection title="الحملات الحالية" subtitle="تمت إضافة عمود الدورة المرتبطة لحساب الأداء لكل دورة بدقة.">
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead><tr style={{ background: "#f8fafc" }}>
                {["الحملة", "الدورة المرتبطة", "المنصة", "الحالة", "إنفاق", "Leads", "تحويلات", "إيراد", "ROAS", "توصية", ""].map(h => <th key={h} style={{ padding: "12px 14px", textAlign: "right", fontWeight: 600, color: "#6b7280", borderBottom: "1px solid #e5e7eb" }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {campaigns.map(c => (
                  <tr key={c.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "12px 14px", fontWeight: 600 }}>{c.name}</td>
                    <td style={{ padding: "12px 14px" }}>{c.course_title || "غير مرتبطة"}</td>
                    <td><Badge text={platLabels[c.platform] || c.platform} /></td>
                    <td><Badge text={statusLabels[c.status] || c.status} color={c.status === "active" ? "#2d8659" : "#9ca3af"} /></td>
                    <td>{fmtUSD(c.spent)}</td>
                    <td>{c.leads}</td>
                    <td>{c.conversions}</td>
                    <td style={{ color: "#2d8659", fontWeight: 600 }}>{fmtUSD(c.revenue_attributed)}</td>
                    <td style={{ fontWeight: 700 }}>{c.roas.toFixed(1)}x</td>
                    <td><span style={{ color: recColors[c.recommendation], fontWeight: 700 }}>{recLabels[c.recommendation]}</span></td>
                    <td>
                      <button onClick={() => { setCampaignForm(c); setCampaignModal(true); }} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14 }}>✏️</button>
                      <button onClick={async () => { if (confirm("حذف؟")) { await api.del(`/campaigns/${c.id}`); load(); }}} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14 }}>🗑</button>
                    </td>
                  </tr>
                ))}
                {campaigns.length === 0 && <tr><td colSpan={11} style={{ padding: 40, textAlign: "center", color: "#9ca3af" }}>لا توجد حملات بعد. أضف أول حملة إعلانية.</td></tr>}
              </tbody>
            </table>
          </PageSection>
        </div>
      )}

      {tab === "investors" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 24 }}>
            <KPICard icon="🏦" label="إجمالي الاستثمارات المضخوخة" value={usdFromEgp(investmentTotals.injected, 50)} sub={egpLabel(investmentTotals.injected)} color={BRAND.navy} />
            <KPICard icon="💵" label="إجمالي العوائد الموزعة" value={usdFromEgp(investmentTotals.distributed, 50)} sub={egpLabel(investmentTotals.distributed)} color="#2d8659" />
            <KPICard icon="🧑‍💼" label="عدد المستثمرين النشطين" value={investmentTotals.active} color="#8e44ad" />
            <KPICard icon="📈" label="متوسط ROI" value={`${investmentTotals.avgRoi.toFixed(1)}%`} color={BRAND.gold} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(360px, 1fr)", gap: 20, alignItems: "start" }}>
            <PageSection title="جدول الاستثمارات" subtitle="كل استثمار مرتبط بدورة ونسبة من صافي أرباحها القابلة للتوزيع.">
              {investments.length ? (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead><tr style={{ background: "#f8fafc" }}>
                    {["الدورة", "المستثمر", "المبلغ المستثمر", "نسبته", "صافي ربح الدورة", "المستحق له", "ROI", "الحالة", ""].map(h => <th key={h} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{h}</th>)}
                  </tr></thead>
                  <tbody>
                    {investments.map(item => (
                      <tr key={item.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                        <td style={{ padding: "12px 14px", fontWeight: 800 }}>{item.course_title || "—"}</td>
                        <td style={{ padding: "12px 14px" }}>{item.investor_name}</td>
                        <td style={{ padding: "12px 14px" }}>{usdFromEgp(item.invested_total_egp, 50)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.invested_total_egp)}</div></td>
                        <td style={{ padding: "12px 14px" }}>{item.profit_percent}%</td>
                        <td style={{ padding: "12px 14px" }}>{usdFromEgp(item.course_profit_egp, 50)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.course_profit_egp)}</div></td>
                        <td style={{ padding: "12px 14px", fontWeight: 900, color: "#2d8659" }}>{usdFromEgp(item.due_egp, 50)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(item.due_egp)}</div></td>
                        <td style={{ padding: "12px 14px", fontWeight: 800, color: item.roi_percent >= 0 ? "#2d8659" : "#c0392b" }}>{item.roi_percent}%</td>
                        <td style={{ padding: "12px 14px" }}><Badge text={investmentStatusLabels[item.status] || item.status} color={item.status === "paid" ? "#2d8659" : item.status === "pending" ? "#e8913a" : "#8e44ad"} /></td>
                        <td style={{ padding: "12px 14px" }}>
                          <button onClick={() => { setInvestmentForm(item); setInvestmentModal(true); }} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14 }}>✏️</button>
                          <button onClick={async () => { if (confirm("حذف؟")) { await api.del(`/investments/${item.id}`); load(); }}} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14 }}>🗑</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <EmptyState title="لا توجد استثمارات بعد" text="أضف أول استثمار إعلاني مرتبط بدورة." />
              )}
            </PageSection>

            <PageSection title="حاسبة محاكاة الاستثمار" subtitle="أدخل الأرقام أو استخدمها كنموذج ثم طبّقها على دورة فعلية." action={<Btn variant="secondary" color={BRAND.navy} onClick={() => setCalculatorOpen(true)}>فتح الحاسبة</Btn>}>
              {simulation?.distribution ? (
                <div style={{ display: "grid", gap: 10 }}>
                  <div style={{ fontSize: 13, color: "#667085" }}>العائد المتوقع على مساهمة هذا المستثمر</div>
                  <div style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy }}>{usdFromEgp(simulation.distribution.investor_due_egp, 50)}</div>
                  <div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(simulation.distribution.investor_due_egp)}</div>
                  {simulation.distribution.warning && <div style={{ padding: 12, background: "#fff1f2", color: "#b42318", borderRadius: 10, fontSize: 13 }}>{simulation.distribution.warning}</div>}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    <div style={{ border: "1px solid #edf2f7", borderRadius: 12, padding: 12 }}>
                      <div style={{ fontSize: 12, color: "#667085" }}>ميزانية الإعلان الكلية</div>
                      <div style={{ fontWeight: 900, color: BRAND.navy, marginTop: 4 }}>{usdFromEgp(simulation.inputs?.total_ads_budget_egp, 50)}</div>
                      <div style={{ fontSize: 12, color: "#94a3b8" }}>{egpLabel(simulation.inputs?.total_ads_budget_egp)}</div>
                    </div>
                    <div style={{ border: "1px solid #edf2f7", borderRadius: 12, padding: 12 }}>
                      <div style={{ fontSize: 12, color: "#667085" }}>مساهمة هذا المستثمر</div>
                      <div style={{ fontWeight: 900, color: BRAND.navy, marginTop: 4 }}>{usdFromEgp(simulation.inputs?.investor_contribution_egp, 50)}</div>
                      <div style={{ fontSize: 12, color: "#94a3b8" }}>{simulation.distribution?.investor_share_of_budget_percent || 0}% من ميزانية الإعلان</div>
                    </div>
                    {[
                      ["المدرب", simulation.distribution.allocations_egp?.trainer, simulation.distribution.trainer_percent],
                      ["المنصة", simulation.distribution.allocations_egp?.platform, simulation.distribution.platform_percent],
                      ["حصة المستثمرين كاملة", simulation.distribution.investor_pool_egp, simulation.distribution.investor_percent],
                      ["نصيب هذا المستثمر", simulation.distribution.investor_due_egp, simulation.distribution.investor_share_of_budget_percent],
                    ].map(([label, amount, percent]) => (
                      <div key={label} style={{ border: "1px solid #edf2f7", borderRadius: 12, padding: 12 }}>
                        <div style={{ fontSize: 12, color: "#667085" }}>{label}</div>
                        <div style={{ fontWeight: 900, color: BRAND.navy, marginTop: 4 }}>{usdFromEgp(amount, 50)}</div>
                        <div style={{ fontSize: 12, color: "#94a3b8" }}>{percent}%</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyState title="الحاسبة جاهزة" text="افتح الحاسبة وأدخل القيم لتشاهد التوزيع المتوقع لحظيًا." />
              )}
            </PageSection>
          </div>
        </div>
      )}

      <Modal open={campaignModal} onClose={() => setCampaignModal(false)} title={campaignForm.id ? "تعديل حملة" : "حملة جديدة"}>
        <Input label="اسم الحملة" value={campaignForm.name || ""} onChange={e => setCampaignForm({ ...campaignForm, name: e.target.value })} />
        <Select label="الدورة المرتبطة" value={campaignForm.course_id || ""} onChange={e => setCampaignForm({ ...campaignForm, course_id: e.target.value ? +e.target.value : null })} options={[{ value: "", label: "بدون ربط" }, ...courses.map(course => ({ value: course.id, label: course.title }))]} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Select label="المنصة" value={campaignForm.platform || "facebook"} onChange={e => setCampaignForm({ ...campaignForm, platform: e.target.value })} options={Object.entries(platLabels).map(([v, l]) => ({ value: v, label: l }))} />
          <Select label="الحالة" value={campaignForm.status || "active"} onChange={e => setCampaignForm({ ...campaignForm, status: e.target.value })} options={Object.entries(statusLabels).map(([v, l]) => ({ value: v, label: l }))} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="تاريخ البدء" type="date" value={campaignForm.start_date || ""} onChange={e => setCampaignForm({ ...campaignForm, start_date: e.target.value })} />
          <Input label="تاريخ النهاية" type="date" value={campaignForm.end_date || ""} onChange={e => setCampaignForm({ ...campaignForm, end_date: e.target.value })} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="الميزانية ($)" type="number" value={campaignForm.budget || 0} onChange={e => setCampaignForm({ ...campaignForm, budget: +e.target.value })} />
          <Input label="المنفق ($)" type="number" value={campaignForm.spent || 0} onChange={e => setCampaignForm({ ...campaignForm, spent: +e.target.value })} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          <Input label="Impressions" type="number" value={campaignForm.impressions || 0} onChange={e => setCampaignForm({ ...campaignForm, impressions: +e.target.value })} />
          <Input label="Clicks" type="number" value={campaignForm.clicks || 0} onChange={e => setCampaignForm({ ...campaignForm, clicks: +e.target.value })} />
          <Input label="Leads" type="number" value={campaignForm.leads || 0} onChange={e => setCampaignForm({ ...campaignForm, leads: +e.target.value })} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="تحويلات" type="number" value={campaignForm.conversions || 0} onChange={e => setCampaignForm({ ...campaignForm, conversions: +e.target.value })} />
          <Input label="إيراد من الحملة ($)" type="number" value={campaignForm.revenue_attributed || 0} onChange={e => setCampaignForm({ ...campaignForm, revenue_attributed: +e.target.value })} />
        </div>
        <Input label="الجمهور المستهدف" value={campaignForm.target_audience || ""} onChange={e => setCampaignForm({ ...campaignForm, target_audience: e.target.value })} />
        <Btn onClick={saveCampaign} color="#e8913a" style={{ width: "100%", marginTop: 8 }}>حفظ الحملة</Btn>
      </Modal>

      <Modal open={investmentModal} onClose={() => setInvestmentModal(false)} title={investmentForm.id ? "تعديل استثمار" : "استثمار جديد"}>
        <Select label="الدورة" value={investmentForm.course_id || ""} onChange={e => setInvestmentForm({ ...investmentForm, course_id: e.target.value ? +e.target.value : "" })} options={[{ value: "", label: "اختر الدورة" }, ...courses.map(course => ({ value: course.id, label: course.title }))]} />
        <Input label="اسم المستثمر" value={investmentForm.investor_name || ""} onChange={e => setInvestmentForm({ ...investmentForm, investor_name: e.target.value })} />
        <CurrencyFields form={investmentForm} setForm={setInvestmentForm} rate={50} egpLabel="المبلغ المستثمر (ج.م)" usdLabel="المبلغ المستثمر ($)" />
        <Input label="حصة المستثمر من الأرباح %" type="number" value={investmentForm.profit_percent || 0} onChange={e => setInvestmentForm({ ...investmentForm, profit_percent: +e.target.value })} />
        <Select label="الحالة" value={investmentForm.status || "accrued"} onChange={e => setInvestmentForm({ ...investmentForm, status: e.target.value })} options={Object.entries(investmentStatusLabels).map(([value, label]) => ({ value, label }))} />
        <Input label="ملاحظات" value={investmentForm.notes || ""} onChange={e => setInvestmentForm({ ...investmentForm, notes: e.target.value })} />
        <Btn onClick={saveInvestment} color={BRAND.navy} style={{ width: "100%", marginTop: 8 }}>حفظ الاستثمار</Btn>
      </Modal>

      <Modal open={calculatorOpen} onClose={() => setCalculatorOpen(false)} title="حاسبة محاكاة الاستثمار" maxWidth={1120} width="95%">
        <div style={{ display: "grid", gridTemplateColumns: "minmax(360px, 1fr) minmax(360px, 1fr)", gap: 20, alignItems: "start" }}>
          <div>
            <Select label="الدورة" value={calculatorForm.course_id || ""} onChange={e => setCalculatorForm({ ...calculatorForm, course_id: e.target.value })} options={[{ value: "", label: "اختر دورة أو اتركها عامة" }, ...courses.map(course => ({ value: course.id, label: course.title }))]} />
            <Input label="إيراد الدورة المتوقع (ج.م)" type="number" value={calculatorForm.revenue_egp ?? ""} onChange={e => setCalculatorForm({ ...calculatorForm, revenue_egp: e.target.value === "" ? "" : +e.target.value })} placeholder="اتركه فارغًا ليُحسب من الطلاب × سعر الاشتراك" />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <Input label="عدد الطلاب المتوقع" type="number" value={calculatorForm.students_count ?? 0} onChange={e => setCalculatorForm({ ...calculatorForm, students_count: +e.target.value })} />
              <Input label="سعر الاشتراك" type="number" value={calculatorForm.price_per_student ?? 0} onChange={e => setCalculatorForm({ ...calculatorForm, price_per_student: +e.target.value })} />
            </div>
            <Input label="مصاريف التنفيذ العامة" type="number" value={calculatorForm.execution_cost_egp ?? 0} onChange={e => setCalculatorForm({ ...calculatorForm, execution_cost_egp: +e.target.value })} placeholder="مثل Zoom أو تجهيزات أو قاعة إن وجدت" />
            <Input label="الإشراف التدريبي" type="number" value={calculatorForm.supervision_cost_egp ?? 0} onChange={e => setCalculatorForm({ ...calculatorForm, supervision_cost_egp: +e.target.value })} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <Input label="ميزانية الإعلان الكلية للدورة" type="number" value={calculatorForm.total_ads_budget_egp ?? 0} onChange={e => setCalculatorForm({ ...calculatorForm, total_ads_budget_egp: +e.target.value })} />
              <Input label="مساهمة هذا المستثمر" type="number" value={calculatorForm.investor_contribution_egp ?? 0} onChange={e => setCalculatorForm({ ...calculatorForm, investor_contribution_egp: +e.target.value })} />
            </div>
            <div style={{ padding: 14, borderRadius: 12, border: "1px solid #E6D7A8", background: "#F7F4EB", marginBottom: 16, fontSize: 13, color: "#5b6475", lineHeight: 1.8 }}>
              الفكرة هنا: الدورة تحتاج ميزانية إعلان كاملة، لكن المستثمر الحالي قد يضخ جزءًا منها فقط. الحاسبة ستقدّر نصيبه من حصة المستثمرين بحسب نسبة مساهمته من الميزانية الكلية.
            </div>
            {[
              ["نسبة المدرب", "trainer_percent", 25, 40],
              ["نسبة المنصة", "platform_percent", 25, 35],
              ["حصة المستثمرين من صافي الربح", "investor_percent", 15, 35],
            ].map(([label, key, min, max]) => (
              <div key={key} style={{ marginBottom: 14 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 700, marginBottom: 6 }}>{label}: {calculatorForm[key]}%</label>
                <input type="range" min={min} max={max} value={calculatorForm[key]} onChange={e => setCalculatorForm({ ...calculatorForm, [key]: +e.target.value })} style={{ width: "100%" }} />
              </div>
            ))}
            <Select
              label="طريقة احتساب الأفلييت"
              value={calculatorForm.affiliate_mode || "percent"}
              onChange={e => setCalculatorForm({ ...calculatorForm, affiliate_mode: e.target.value })}
              options={[
                { value: "percent", label: "كنسبة من صافي الربح" },
                { value: "fixed", label: "كمبلغ ثابت" },
              ]}
            />
            {calculatorForm.affiliate_mode === "percent" ? (
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 700, marginBottom: 6 }}>نسبة الأفلييت: {calculatorForm.affiliate_percent}%</label>
                <input type="range" min={0} max={10} value={calculatorForm.affiliate_percent} onChange={e => setCalculatorForm({ ...calculatorForm, affiliate_percent: +e.target.value })} style={{ width: "100%" }} />
              </div>
            ) : (
              <Input label="مبلغ الأفلييت الثابت" type="number" value={calculatorForm.affiliate_fixed_egp ?? 0} onChange={e => setCalculatorForm({ ...calculatorForm, affiliate_fixed_egp: +e.target.value })} />
            )}
          </div>
          <div>
            <PageSection title="نتائج المحاكاة" subtitle="تتحدث لحظيًا مع كل تعديل.">
              {simulation?.distribution ? (
                <div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
                    <KPICard label="إجمالي الإيراد" value={usdFromEgp(simulation.inputs?.projected_revenue_egp, 50)} sub={egpLabel(simulation.inputs?.projected_revenue_egp)} color="#2d8659" />
                    <KPICard label="إجمالي المصاريف المباشرة" value={usdFromEgp(simulation.inputs?.direct_costs_egp, 50)} sub={egpLabel(simulation.inputs?.direct_costs_egp)} color="#c0392b" />
                    <KPICard label="صافي الربح القابل للتوزيع" value={usdFromEgp(simulation.distribution?.net_distributable_profit, 50)} sub={egpLabel(simulation.distribution?.net_distributable_profit)} color={BRAND.navy} />
                    <KPICard label="ROI المستثمر" value={`${simulation.distribution?.investor_roi_percent || 0}%`} color={BRAND.gold} />
                  </div>
                  {simulation.distribution?.warning && <div style={{ padding: 12, background: "#fff1f2", color: "#b42318", borderRadius: 10, fontSize: 13, marginBottom: 16 }}>{simulation.distribution.warning}</div>}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
                    <div style={{ border: "1px solid #edf2f7", borderRadius: 12, padding: 14 }}>
                      <div style={{ fontSize: 12, color: "#667085" }}>حصة المستثمرين الكلية</div>
                      <div style={{ fontSize: 20, fontWeight: 900, color: BRAND.navy, marginTop: 6 }}>{usdFromEgp(simulation.distribution?.investor_pool_egp, 50)}</div>
                      <div style={{ fontSize: 12, color: "#94a3b8" }}>{simulation.distribution?.investor_percent}% من صافي الربح القابل للتوزيع</div>
                    </div>
                    <div style={{ border: "1px solid #edf2f7", borderRadius: 12, padding: 14 }}>
                      <div style={{ fontSize: 12, color: "#667085" }}>نصيب هذا المستثمر</div>
                      <div style={{ fontSize: 20, fontWeight: 900, color: "#2d8659", marginTop: 6 }}>{usdFromEgp(simulation.distribution?.investor_due_egp, 50)}</div>
                      <div style={{ fontSize: 12, color: "#94a3b8" }}>{simulation.distribution?.investor_share_of_budget_percent || 0}% من ميزانية الإعلان</div>
                    </div>
                  </div>
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie data={[
                        { name: "المدرب", value: simulation.distribution.allocations_egp?.trainer || 0 },
                        { name: "المنصة", value: simulation.distribution.allocations_egp?.platform || 0 },
                        { name: "حصة المستثمرين", value: simulation.distribution.allocations_egp?.investor || 0 },
                        { name: "الأفلييت", value: simulation.distribution.allocations_egp?.affiliate || 0 },
                      ]} dataKey="value" cx="50%" cy="50%" outerRadius={78} label>
                        {[0, 1, 2, 3].map(index => <Cell key={index} fill={COLORS[index]} />)}
                      </Pie>
                      <Tooltip formatter={value => egpLabel(value)} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 16 }}>
                    <div style={{ border: "1px solid #edf2f7", borderRadius: 12, padding: 14 }}>
                      <div style={{ fontSize: 12, color: "#667085" }}>المدرب</div>
                      <div style={{ fontWeight: 900, color: BRAND.navy, marginTop: 4 }}>{egpLabel(simulation.distribution.allocations_egp?.trainer || 0)}</div>
                    </div>
                    <div style={{ border: "1px solid #edf2f7", borderRadius: 12, padding: 14 }}>
                      <div style={{ fontSize: 12, color: "#667085" }}>المنصة</div>
                      <div style={{ fontWeight: 900, color: BRAND.navy, marginTop: 4 }}>{egpLabel(simulation.distribution.allocations_egp?.platform || 0)}</div>
                    </div>
                    <div style={{ border: "1px solid #edf2f7", borderRadius: 12, padding: 14 }}>
                      <div style={{ fontSize: 12, color: "#667085" }}>الأفلييت</div>
                      <div style={{ fontWeight: 900, color: BRAND.navy, marginTop: 4 }}>{egpLabel(simulation.distribution.allocations_egp?.affiliate || 0)}</div>
                      <div style={{ fontSize: 12, color: "#94a3b8" }}>
                        {simulation.distribution?.affiliate_mode === "fixed"
                          ? "مبلغ ثابت"
                          : `${simulation.distribution?.affiliate_percent || 0}% من صافي الربح`}
                      </div>
                    </div>
                    <div style={{ border: "1px solid #edf2f7", borderRadius: 12, padding: 14 }}>
                      <div style={{ fontSize: 12, color: "#667085" }}>الربح المتبقي بعد الأفلييت</div>
                      <div style={{ fontWeight: 900, color: BRAND.navy, marginTop: 4 }}>{egpLabel(simulation.distribution?.post_affiliate_pool_egp || 0)}</div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                    <Btn color={BRAND.navy} onClick={applySimulationToInvestment} style={{ flex: 1 }}>تطبيق على استثمار جديد</Btn>
                    <Btn variant="secondary" color={BRAND.gold} onClick={() => setCalculatorForm(createCalculatorForm())} style={{ flex: 1 }}>إعادة ضبط الحاسبة</Btn>
                  </div>
                </div>
              ) : <EmptyState title="الحاسبة تعمل" text="أدخل الأرقام على اليمين لتظهر نتائج التوزيع." />}
            </PageSection>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ============================================================
// TRAINING REQUESTS — trainer applications + program requests.
// Live under "الدورات" (each its own tab). Self-contained: own fetch
// + approve/reject. Employee (موظف متابعة) sees them read-only.
// ============================================================
function TrainerRequestsPanel() {
  const readOnly = false; // أدمن + موظف العمليات: الاتنين يتابعوا ويوافقوا/يرفضوا
  const [apps, setApps] = useState([]);
  const [busy, setBusy] = useState("");
  const [notes, setNotes] = useState({});
  const load = () => api.get("/platform-trainer-applications?status=pending").then(a => { if (a && !a.error) setApps(a.applications || []); });
  useEffect(() => { load(); }, []);
  const decide = (app, action) => {
    setBusy(app.id);
    api.post(`/platform-trainer-applications/${app.id}/${action}`, { admin_note: notes[app.id] || "" })
      .then(r => { setBusy(""); if (r && !r.error) load(); else alert(r.error || "تعذر تنفيذ العملية"); });
  };
  const noteInput = (id, ph) => (
    <input value={notes[id] || ""} onChange={e => setNotes(n => ({ ...n, [id]: e.target.value }))} placeholder={ph}
      style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13, flex: 1, minWidth: 160 }} />
  );
  return (
    <div style={{ display: "grid", gap: 14 }}>
      {apps.length === 0 && <div style={{ padding: 24, textAlign: "center", color: "#9ca3af", background: "#fff", borderRadius: 12 }}>لا توجد طلبات مدربين معلّقة. ✅</div>}
      {apps.map(a => (
        <div key={a.id} style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", padding: 18, borderRight: "4px solid #e8913a" }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <div style={{ fontWeight: 900, color: BRAND.navy, fontSize: 16 }}>{a.user_name || a.full_name || "—"}</div>
            <div style={{ fontSize: 13, color: "#667085" }}>{a.user_email || a.email || ""}{a.user_phone ? ` · ${a.user_phone}` : ""}</div>
          </div>
          {a.headline && <div style={{ marginTop: 6, color: "#475467", fontWeight: 700 }}>{a.headline}</div>}
          {Array.isArray(a.expertise) && a.expertise.length > 0 && (
            <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
              {a.expertise.map((x, i) => <span key={i} style={{ background: "#f1f5f9", borderRadius: 999, padding: "3px 10px", fontSize: 12, color: "#475467" }}>{x}</span>)}
            </div>
          )}
          {a.experience_summary && <div style={{ marginTop: 8, fontSize: 13, color: "#667085", whiteSpace: "pre-wrap" }}>{a.experience_summary}</div>}
          <div style={{ marginTop: 8, display: "flex", gap: 14, flexWrap: "wrap", fontSize: 13 }}>
            {a.linkedin_url && <a href={a.linkedin_url} target="_blank" rel="noreferrer" style={{ color: "#5b6abf" }}>LinkedIn ↗</a>}
            {a.portfolio_url && <a href={a.portfolio_url} target="_blank" rel="noreferrer" style={{ color: "#5b6abf" }}>أعماله ↗</a>}
          </div>
          {readOnly ? (
            <div style={{ marginTop: 12, fontSize: 12, color: "#9ca3af" }}>👁️ للمتابعة فقط — الاعتماد من المدير.</div>
          ) : (
            <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              {noteInput(a.id, "ملاحظة إدارية (اختياري)")}
              <button disabled={busy === a.id} onClick={() => decide(a, "approve")} style={{ padding: "9px 18px", borderRadius: 8, border: "none", background: "#2d8659", color: "#fff", fontWeight: 800, cursor: "pointer" }}>اعتماد</button>
              <button disabled={busy === a.id} onClick={() => decide(a, "reject")} style={{ padding: "9px 18px", borderRadius: 8, border: "1px solid #dc2626", background: "#fff", color: "#dc2626", fontWeight: 800, cursor: "pointer" }}>رفض</button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function ProgramRequestsPanel() {
  const readOnly = false; // أدمن + موظف العمليات: الاتنين يتابعوا ويوافقوا/يرفضوا
  const [reqs, setReqs] = useState([]);
  const [busy, setBusy] = useState("");
  const [notes, setNotes] = useState({});
  const [lms, setLms] = useState({});
  const load = () => api.get("/platform-program-requests?status=pending").then(a => { if (a && !a.error) setReqs(a.requests || []); });
  useEffect(() => { load(); }, []);
  const decide = (req, action) => {
    setBusy(req.id);
    const draft = lms[req.id] || {};
    const payload = action === "approve"
      ? { admin_note: notes[req.id] || "", lms_entry_url: draft.entry || "", lms_course_ref: draft.ref || "" }
      : { admin_note: notes[req.id] || "" };
    api.post(`/platform-program-requests/${req.id}/${action}`, payload)
      .then(r => { setBusy(""); if (r && !r.error) load(); else alert(r.error || "تعذر تنفيذ العملية"); });
  };
  const noteInput = (id, ph) => (
    <input value={notes[id] || ""} onChange={e => setNotes(n => ({ ...n, [id]: e.target.value }))} placeholder={ph}
      style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13, flex: 1, minWidth: 160 }} />
  );
  return (
    <div style={{ display: "grid", gap: 14 }}>
      {reqs.length === 0 && <div style={{ padding: 24, textAlign: "center", color: "#9ca3af", background: "#fff", borderRadius: 12 }}>لا توجد طلبات برامج معلّقة. ✅</div>}
      {reqs.map(req => (
        <div key={req.id} style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", padding: 18, borderRight: "4px solid #5b6abf" }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <div style={{ fontWeight: 900, color: BRAND.navy, fontSize: 16 }}>{req.user_name || "—"}</div>
            <div style={{ fontSize: 13, color: "#667085" }}>{req.user_email || ""}</div>
          </div>
          <div style={{ marginTop: 6, color: "#475467" }}>البرنامج: <b>{req.title || req.program_id || "—"}</b></div>
          {req.notes && <div style={{ marginTop: 6, fontSize: 13, color: "#667085", whiteSpace: "pre-wrap" }}>{req.notes}</div>}
          {readOnly ? (
            <div style={{ marginTop: 12, fontSize: 12, color: "#9ca3af" }}>👁️ للمتابعة فقط — الاعتماد والربط من المدير.</div>
          ) : (
            <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <input value={(lms[req.id] || {}).entry || ""} onChange={e => setLms(s => ({ ...s, [req.id]: { ...s[req.id], entry: e.target.value } }))} placeholder="رابط الدخول للدورة (LMS) — يُملأ تلقائيًا لو فاضي" style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13, flex: 2, minWidth: 200 }} />
                <input value={(lms[req.id] || {}).ref || ""} onChange={e => setLms(s => ({ ...s, [req.id]: { ...s[req.id], ref: e.target.value } }))} placeholder="مرجع الدورة (course ref)" style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13, flex: 1, minWidth: 140 }} />
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                {noteInput(req.id, "ملاحظة إدارية (اختياري)")}
                <button disabled={busy === req.id} onClick={() => decide(req, "approve")} style={{ padding: "9px 18px", borderRadius: 8, border: "none", background: "#2d8659", color: "#fff", fontWeight: 800, cursor: "pointer" }}>اعتماد وربط</button>
                <button disabled={busy === req.id} onClick={() => decide(req, "reject")} style={{ padding: "9px 18px", borderRadius: 8, border: "1px solid #dc2626", background: "#fff", color: "#dc2626", fontWeight: 800, cursor: "pointer" }}>رفض</button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ============================================================
// COURSES SNAPSHOT
// ============================================================
function CoursesPage() {
  const user = useAuth();
  const isTrainingSupervisor = user?.role === "training_supervisor";
  // الأدمن وموظف العمليات والمدرب يعدّلوا/يضيفوا/يوقفوا؛ المشرف التدريبي للعرض فقط.
  const canManage = !isTrainingSupervisor;
  const [courses, setCourses] = useState([]);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});
  const [view, setView] = useState("courses");
  // الدورات بقت مركز التدريب: الدورات + طلبات البرامج + طلبات المدربين.
  // المدير والموظف بس يشوفوا الطلبات؛ المدرب/المشرف يشوفوا دوراتهم زي ما هي.
  const effectiveRole = getEffectiveRole(user);
  const showRequests = effectiveRole === "admin" || effectiveRole === "employee";

  const load = () => {
    api.get("/courses").then(data => setCourses(safeArray(data)));
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (form.id) await api.put(`/courses/${form.id}`, form);
    else await api.post("/courses", form);
    setModal(false); setForm({}); load();
  };

  // تشغيل/إيقاف سريع — "الدورة واقفة ولا لأ" من غير ما تفتح نموذج التعديل.
  const toggleStatus = async (c) => {
    const next = c.status === "active" ? "paused" : "active";
    await api.put(`/courses/${c.id}`, { status: next });
    load();
  };
  // فتح/قفل الدورة للاستثمار — تظهر/تختفي من ماركت المستثمر.
  const toggleInvestment = async (c) => {
    await api.put(`/courses/${c.id}`, { open_for_investment: !c.open_for_investment });
    load();
  };
  const statusLabel = (s) => s === "active" ? "نشطة" : s === "completed" ? "منتهية" : s === "paused" ? "موقوفة" : s === "draft" ? "مسودة" : s === "archived" ? "مؤرشفة" : s;
  const statusColor = (s) => s === "active" ? "#2d8659" : s === "paused" ? "#c0392b" : "#9ca3af";
  // عرض الإيراد الحقيقي من ووكومرس بعملة المتجر.
  const curSymbol = { GBP: "£", USD: "$", EGP: "ج.م", EUR: "€" };
  const wooMoney = (v, cur) => `${curSymbol[cur] || (cur ? cur + " " : "")}${fmt(v || 0)}`;

  // مزامنة الدورات الحقيقية من الأكاديمية (WordPress/Tutor) عبر المنصة — للأدمن فقط.
  const [syncing, setSyncing] = useState(false);
  const isAdmin = effectiveRole === "admin";
  const syncLms = async () => {
    setSyncing(true);
    const r = await api.post("/courses/sync-lms", {});
    setSyncing(false);
    if (r && !r.error) { alert(`تمت المزامنة من الأكاديمية: ${r.total} دورة (${r.created} جديدة، ${r.updated} محدّثة)`); load(); }
    else alert(r?.error || "تعذرت المزامنة من الأكاديمية");
  };

  // إنشاء دورة على الأكاديمية (WordPress/Tutor) من هنا — أدمن أو مدرب أو موظف العمليات.
  const isTrainer = effectiveRole === "trainer";
  const canCreateLms = isAdmin || isTrainer || effectiveRole === "employee";
  const [lmsModal, setLmsModal] = useState(false);
  const [lmsForm, setLmsForm] = useState({});
  const [creatingLms, setCreatingLms] = useState(false);
  const submitLms = async () => {
    if (!(lmsForm.title || "").trim()) return alert("اكتب عنوان الدورة.");
    if (isAdmin && !(lmsForm.instructor_email || "").trim()) return alert("اكتب إيميل المحاضر (نفس إيميله على الأكاديمية).");
    setCreatingLms(true);
    const r = await api.post("/courses/create-lms", lmsForm);
    setCreatingLms(false);
    if (r && !r.error) {
      alert("تم إنشاء الدورة كمسودة على الأكاديمية ✅ بعد مراجعتها ونشرها، اضغط «مزامنة» فتظهر هنا.");
      setLmsModal(false); setLmsForm({});
    } else alert(r?.error || "تعذر إنشاء الدورة على الأكاديمية");
  };
  // مساعد AI: فكرة بسيطة → عنوان/وصف/مستوى/مدة/محاور تملأ الفورم.
  const [aiIdea, setAiIdea] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const aiDraft = async () => {
    if (!aiIdea.trim()) return alert("اكتب فكرة الدورة الأول.");
    setAiBusy(true);
    const r = await api.post("/courses/ai-draft", { idea: aiIdea });
    setAiBusy(false);
    if (r && !r.error && r.draft) {
      const d = r.draft;
      const outline = Array.isArray(d.outline) && d.outline.length ? "\n\nالمحاور:\n- " + d.outline.join("\n- ") : "";
      setLmsForm(f => ({
        ...f,
        title: d.title || f.title,
        content: (d.description || "") + outline,
        level: ["beginner", "intermediate", "expert", "all_levels"].includes(d.level) ? d.level : (f.level || "beginner"),
        duration_hours: Number(d.duration_hours) || f.duration_hours || 0,
        duration_minutes: Number(d.duration_minutes) || f.duration_minutes || 0,
      }));
    } else alert(r?.error || "تعذر توليد المسودة بالـ AI");
  };

  const totalStudents = courses.reduce((s, c) => s + (c.students_count || 0), 0);
  const totalRevenue = courses.reduce((s, c) => s + (c.total_revenue || 0), 0);
  const totalCost = courses.reduce((s, c) => s + (c.total_cost || 0), 0);
  const best = courses.length ? courses.reduce((a, b) => (a.profit || 0) > (b.profit || 0) ? a : b) : null;

  return (
    <div>
      {showRequests && (
        <div style={{ marginBottom: 18 }}>
          <TabBar tabs={[{ id: "courses", label: "الدورات الحالية" }, { id: "programs", label: `طلبات البرامج` }, { id: "trainers", label: `طلبات المدربين` }]} active={view} onChange={setView} />
        </div>
      )}
      {showRequests && view === "trainers" && <TrainerRequestsPanel />}
      {showRequests && view === "programs" && <ProgramRequestsPanel />}
      {(!showRequests || view === "courses") && (<>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, gap: 10, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f4c81" }}>الدورات التدريبية</h1>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {isAdmin && <Btn onClick={syncLms} color="#5b6abf" disabled={syncing}>{syncing ? "⏳ جاري المزامنة..." : "🔄 مزامنة من الأكاديمية"}</Btn>}
          {canCreateLms && <Btn onClick={() => { setLmsForm({ level: "beginner", price_type: "free" }); setAiIdea(""); setLmsModal(true); }} color="#d4a017" style={{ color: BRAND.navy }}>🎓 أضف دورة على الأكاديمية</Btn>}
          {canManage && <Btn onClick={() => { setForm({ status: "active" }); setModal(true); }} color="#1abc9c">+ دورة جديدة</Btn>}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 24 }}>
        <KPICard icon="📚" label="عدد الدورات" value={courses.length} color="#1abc9c" />
        <KPICard icon="👨‍🎓" label="إجمالي الطلاب" value={totalStudents} color="#5b6abf" />
        <KPICard icon="💰" label="إجمالي الإيرادات" value={`${fmt(totalRevenue)} ج.م`} color="#2d8659" />
        <KPICard icon="📊" label="صافي الربح" value={`${fmt(totalRevenue - totalCost)} ج.م`} color={totalRevenue >= totalCost ? "#2d8659" : "#c0392b"} />
        <KPICard icon="⭐" label="أفضل دورة" value={best?.title?.substring(0, 20) || "—"} sub={best ? `ربح: ${fmt(best.profit)}` : ""} color="#d4a017" />
      </div>

      {courses.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", marginBottom: 24 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>مقارنة الدورات</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={courses.map(c => ({ name: c.title.substring(0, 20), إيراد: c.total_revenue, تكلفة: c.total_cost, ربح: c.profit }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => `${fmt(v)} ج.م`} />
              <Legend />
              <Bar dataKey="إيراد" fill="#2d8659" radius={[4,4,0,0]} />
              <Bar dataKey="تكلفة" fill="#c0392b" radius={[4,4,0,0]} />
              <Bar dataKey="ربح" fill="#0f4c81" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
        {courses.map(c => (
          <div key={c.id} style={{ background: "#fff", borderRadius: 12, padding: 22, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", borderTop: `3px solid ${c.profit >= 0 ? "#2d8659" : "#c0392b"}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: "#1f2937" }}>{c.title}</h3>
              {canManage && <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                <button onClick={() => toggleInvestment(c)} title={c.open_for_investment ? "اقفل الاستثمار" : "افتح للاستثمار"} style={{ background: c.open_for_investment ? "#fef3c7" : "#f3f4f6", border: "none", borderRadius: 8, padding: "4px 10px", cursor: "pointer", fontSize: 12, fontWeight: 800, color: c.open_for_investment ? "#b45309" : "#6b7280" }}>{c.open_for_investment ? "💵 مقفول" : "💵 افتح"}</button>
                <button onClick={() => toggleStatus(c)} title={c.status === "active" ? "إيقاف الدورة" : "تشغيل الدورة"} style={{ background: c.status === "active" ? "#fdecea" : "#eaf6ef", border: "none", borderRadius: 8, padding: "4px 10px", cursor: "pointer", fontSize: 12, fontWeight: 800, color: c.status === "active" ? "#c0392b" : "#2d8659" }}>{c.status === "active" ? "⏸ إيقاف" : "▶ تشغيل"}</button>
                <button onClick={() => { setForm(c); setModal(true); }} style={{ background: "none", border: "none", cursor: "pointer" }}>✏️</button>
                <button onClick={async () => { if (confirm("حذف؟")) { await api.del(`/courses/${c.id}`); load(); }}} style={{ background: "none", border: "none", cursor: "pointer" }}>🗑</button>
              </div>}
            </div>
            <Badge text={statusLabel(c.status)} color={statusColor(c.status)} />
            {c.open_for_investment && <span style={{ fontSize: 12, color: "#b45309", marginRight: 8, fontWeight: 800 }}>💵 مفتوحة للاستثمار</span>}
            {c.lms_synced && <span title={c.lms_instructor_email || ""} style={{ fontSize: 12, color: "#5b6abf", marginRight: 8, fontWeight: 800 }}>🔗 من الأكاديمية</span>}
            {c.trainer_name && <span title={c.lms_instructor_email || ""} style={{ fontSize: 13, color: "#6b7280", marginRight: 8 }}>🎓 {c.trainer_name}</span>}
            {c.lms_synced && c.lms_currency ? (
              <div style={{ marginTop: 8, fontSize: 12, color: "#2d8659", fontWeight: 800 }}>
                🛒 إيراد الأكاديمية (حقيقي): {wooMoney(c.lms_revenue, c.lms_currency)} <span style={{ color: "#9ca3af", fontWeight: 600 }}>({c.lms_sales_count || 0} عملية بيع)</span>
              </div>
            ) : null}
            {((c.linked_expenses || []).length > 0 || (c.linked_payouts || []).length > 0) && (
              <div style={{ marginTop: 14, background: "#fcfbf8", border: "1px solid #f0eadb", borderRadius: 12, padding: 12, fontSize: 12, color: "#667085", lineHeight: 1.9 }}>
                <div style={{ fontWeight: 900, color: BRAND.navy, marginBottom: 6 }}>تفاصيل التنفيذ</div>
                {(c.linked_expenses || []).map((item) => (
                  <div key={`course-exp-${item.id}`}>{catLabels[item.category] || item.category}: <strong style={{ color: "#c0392b" }}>{fmt(item.total_egp)} ج.م</strong>{item.description ? ` - ${item.description}` : ""}</div>
                ))}
                {(c.linked_payouts || []).map((item) => (
                  <div key={`course-pay-${item.id}`}>{payoutRoleLabels[item.role] || item.role}: <strong style={{ color: "#8e44ad" }}>{item.name}</strong>{item.percent ? ` (${item.percent}%)` : ""} - <strong style={{ color: "#8e44ad" }}>{fmt(item.total_egp)} ج.م</strong></div>
                ))}
              </div>
            )}
            {c.distribution && (
              <div style={{ marginTop: 14, border: "1px solid #e8edf3", borderRadius: 12, padding: 12, background: "#fbfcfe" }}>
                <div style={{ fontWeight: 900, color: BRAND.navy, marginBottom: 8, fontSize: 13 }}>التوزيع المالي</div>
                <div style={{ display: "grid", gridTemplateColumns: "110px 1fr", gap: 12, alignItems: "center" }}>
                  <ResponsiveContainer width="100%" height={110}>
                    <PieChart>
                      <Pie data={[
                        { name: "المدرب", value: c.distribution.allocations_egp?.trainer || 0 },
                        { name: "المنصة", value: c.distribution.allocations_egp?.platform || 0 },
                        { name: "المستثمر", value: c.distribution.allocations_egp?.investor || 0 },
                        { name: "الأفلييت", value: c.distribution.allocations_egp?.affiliate || 0 },
                      ]} dataKey="value" cx="50%" cy="50%" outerRadius={42}>
                        {[0, 1, 2, 3].map(index => <Cell key={index} fill={COLORS[index]} />)}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ fontSize: 12, color: "#667085", lineHeight: 1.9 }}>
                    <div>المدرب: <strong>{egpLabel(c.distribution.allocations_egp?.trainer || 0)}</strong></div>
                    <div>المنصة: <strong>{egpLabel(c.distribution.allocations_egp?.platform || 0)}</strong></div>
                    <div>المستثمر: <strong>{egpLabel(c.distribution.allocations_egp?.investor || 0)}</strong></div>
                    <div>الأفلييت: <strong>{egpLabel(c.distribution.allocations_egp?.affiliate || 0)}</strong></div>
                    <div style={{ marginTop: 6, color: c.revenue_split?.valid ? "#2d8659" : "#c0392b", fontWeight: 800 }}>
                      {c.revenue_split?.valid ? "التوزيع مكتمل 100%" : `مجموع النسب ${c.revenue_split?.total_percent || 0}%`}
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 16 }}>
              <div style={{ textAlign: "center" }}><div style={{ fontSize: 11, color: "#9ca3af" }}>طلاب</div><div style={{ fontSize: 18, fontWeight: 700, color: "#5b6abf" }}>{c.students_count}</div></div>
              <div style={{ textAlign: "center" }}><div style={{ fontSize: 11, color: "#9ca3af" }}>إيراد</div><div style={{ fontSize: 18, fontWeight: 700, color: "#2d8659" }}>{fmt(c.total_revenue)}</div></div>
              <div style={{ textAlign: "center" }}><div style={{ fontSize: 11, color: "#9ca3af" }}>ربح</div><div style={{ fontSize: 18, fontWeight: 700, color: c.profit >= 0 ? "#2d8659" : "#c0392b" }}>{fmt(c.profit)}</div></div>
            </div>
          </div>
        ))}
        {courses.length === 0 && <div style={{ gridColumn: "1/-1", textAlign: "center", padding: 60, color: "#9ca3af" }}>لا توجد دورات. أضف أول دورة.</div>}
      </div>

      <Modal open={modal} onClose={() => setModal(false)} title={form.id ? "تعديل دورة" : "دورة جديدة"}>
        <Input label="عنوان الدورة" value={form.title || ""} onChange={e => setForm({ ...form, title: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="الفئة" value={form.category || ""} onChange={e => setForm({ ...form, category: e.target.value })} placeholder="قانون مدني، جنائي..." />
          <Input label="المدرب" value={form.trainer_name || ""} onChange={e => setForm({ ...form, trainer_name: e.target.value })} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="السعر (ج.م)" type="number" value={form.price_egp || 0} onChange={e => setForm({ ...form, price_egp: +e.target.value })} />
          <Input label="السعر ($)" type="number" value={form.price_usd || 0} onChange={e => setForm({ ...form, price_usd: +e.target.value })} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="التكلفة (ج.م)" type="number" value={form.cost_egp || 0} onChange={e => setForm({ ...form, cost_egp: +e.target.value })} />
          <Input label="التكلفة ($)" type="number" value={form.cost_usd || 0} onChange={e => setForm({ ...form, cost_usd: +e.target.value })} />
        </div>
        <Input label="عدد الطلاب" type="number" value={form.students_count || 0} onChange={e => setForm({ ...form, students_count: +e.target.value })} />
        <Select label="الحالة" value={form.status || "active"} onChange={e => setForm({ ...form, status: e.target.value })} options={[{ value: "draft", label: "مسودة" }, { value: "active", label: "نشطة" }, { value: "completed", label: "منتهية" }, { value: "archived", label: "أرشيف" }]} />
        <Btn onClick={save} color="#1abc9c" style={{ width: "100%", marginTop: 8 }}>💾 حفظ</Btn>
      </Modal>

      <Modal open={lmsModal} onClose={() => setLmsModal(false)} title="🎓 دورة جديدة على الأكاديمية">
        <div style={{ fontSize: 13, color: "#667085", marginBottom: 12, lineHeight: 1.8 }}>
          {isTrainer
            ? "هتتسجل الدورة باسمك كمحاضر (بإيميلك على الأكاديمية)، كمسودة للمراجعة قبل النشر."
            : "هتتعمل كمسودة على الأكاديمية باسم المحاضر اللي تحدده، وبعد مراجعتها ونشرها تظهر هنا بالمزامنة."}
        </div>
        <div style={{ background: "#f7f4eb", border: "1px solid #e6d7a8", borderRadius: 10, padding: 12, marginBottom: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 800, color: BRAND.navy, marginBottom: 8 }}>✨ مش عارف تبدأ؟ اكتب فكرة وسيب الـ AI يجهّزها</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input value={aiIdea} onChange={e => setAiIdea(e.target.value)} placeholder="مثال: دورة عن العقود التجارية للشركات الناشئة" style={{ flex: 1, minWidth: 200, padding: "9px 12px", borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13 }} />
            <Btn onClick={aiDraft} color="#8e44ad" disabled={aiBusy}>{aiBusy ? "⏳ بيجهّز..." : "✨ جهّز بالـ AI"}</Btn>
          </div>
        </div>
        <Input label="عنوان الدورة" value={lmsForm.title || ""} onChange={e => setLmsForm({ ...lmsForm, title: e.target.value })} />
        {isAdmin && <Input label="إيميل المحاضر (نفس إيميله على الأكاديمية)" value={lmsForm.instructor_email || ""} onChange={e => setLmsForm({ ...lmsForm, instructor_email: e.target.value })} placeholder="trainer@example.com" />}
        <Input label="وصف مختصر" value={lmsForm.content || ""} onChange={e => setLmsForm({ ...lmsForm, content: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Select label="المستوى" value={lmsForm.level || "beginner"} onChange={e => setLmsForm({ ...lmsForm, level: e.target.value })} options={[{ value: "beginner", label: "مبتدئ" }, { value: "intermediate", label: "متوسط" }, { value: "expert", label: "متقدم" }, { value: "all_levels", label: "كل المستويات" }]} />
          <Select label="النوع" value={lmsForm.price_type || "free"} onChange={e => setLmsForm({ ...lmsForm, price_type: e.target.value })} options={[{ value: "free", label: "مجانية" }, { value: "paid", label: "مدفوعة" }]} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="المدة (ساعات)" type="number" value={lmsForm.duration_hours || 0} onChange={e => setLmsForm({ ...lmsForm, duration_hours: +e.target.value })} />
          <Input label="المدة (دقائق)" type="number" value={lmsForm.duration_minutes || 0} onChange={e => setLmsForm({ ...lmsForm, duration_minutes: +e.target.value })} />
        </div>
        <Btn onClick={submitLms} color="#d4a017" disabled={creatingLms} style={{ width: "100%", marginTop: 8, color: BRAND.navy }}>{creatingLms ? "⏳ جاري الإنشاء..." : "🎓 إنشاء على الأكاديمية"}</Btn>
      </Modal>
      </>)}
    </div>
  );
}

// ============================================================
// AI ASSISTANT
// ============================================================
function roleAiConfig(role) {
  if (role === "trainer") {
    return {
      title: "مساعد المدرب الذكي",
      subtitle: "جاهز لمساعدتك في تعبئة الدورات وتوقع أرباحك وخطة التوزيع",
      placeholder: "اسأل عن دوراتك، الأرباح المتوقعة، أو توقيت الإعلانات...",
      welcome: "أنا معك كمدرب. أقدر أراجع تعبئة الدورات، موعد التوزيع، وتوقيت الإعلان الأنسب.",
      quickActions: [
        { label: "ملخص دوراتي", prompt: "لخّص أداء دوراتي الحالية: عدد الطلاب، الإيراد المتوقع، وأقرب دورة تحتاج دفعًا إعلانيًا أو تعبئة أسرع." },
        { label: "توقع أرباحي", prompt: "احسب أرباحي المتوقعة من الدورات الحالية، ووضّح ما سيتم توزيعه بعد نهاية كل برنامج بأسبوع." },
        { label: "هل أستثمر في دورتي؟", prompt: "قيّم هل يستحق أن أضخ تمويلًا إعلانيًا في دورتي الحالية، وما العائد المتوقع لو استثمرت جزءًا من الميزانية." },
        { label: "خطر الإلغاء", prompt: "هل توجد دورة معرضة للإلغاء بسبب عدم اكتمال العدد؟ اذكر السبب وما الذي يجب عمله الآن." },
      ],
    };
  }
  if (role === "investor") {
    return {
      title: "مساعد المستثمر الذكي",
      subtitle: "جاهز لقراءة الفرص والعائد والمخاطر وتوقيت السحب",
      placeholder: "اسأل عن أفضل فرصة، العائد المتوقع، أو حالة استثماراتك...",
      welcome: "أنا معك كمستثمر. أساعدك في قراءة الفرص، متابعة العائد، وفهم المخاطر قبل ضخ التمويل.",
      quickActions: [
        { label: "أفضل فرصة الآن", prompt: "اختر أفضل فرصة استثمارية متاحة الآن وفسّر لماذا هي الأفضل من حيث العائد والطلب والزمن." },
        { label: "متى أطلب سحب؟", prompt: "راجع رصيدي وعوائدي وقل لي هل هذا وقت مناسب لطلب سحب أم لإعادة الاستثمار." },
        { label: "كشف المخاطر", prompt: "حلل مخاطر الاستثمارات الحالية: هل يوجد تمويل متأخر، دورة مهددة، أو عائد أقل من المتوقع؟" },
        { label: "تقرير استثماري", prompt: "أعطني تقريرًا موجزًا عن استثماراتي الحالية والسابقة، مع العائد المتوقع والحالة لكل دورة." },
      ],
    };
  }
  return {
    title: "مساعد القرار الذكي",
    subtitle: "جاهز لاستخدام بيانات الإدارة والمالية والتسويق لاتخاذ قرار أفضل",
    placeholder: "اسأل عن المالية، الحملات، الأصول، أو الأهداف...",
    welcome: "أنا متابع الأرقام معك. أقدر ألخص الإدارة والمالية والتسويق وأكشف المخاطر بسرعة.",
    quickActions: [
      { label: "تلخيص حالة الشركة", prompt: "لخّص حالة الشركة المالية والتشغيلية في فقرتين مع أبرز الأرقام والتنبيهات." },
      { label: "تحليل مالي", prompt: "حلل الإيرادات والمصروفات وصافي التشغيل، واذكر أهم التوصيات القابلة للتنفيذ." },
      { label: "تحليل الحملات", prompt: "حلل الحملات التسويقية الحالية: الأفضل، الأضعف، وما الذي يحتاج تعديلًا فوريًا." },
      { label: "كشف المشاكل", prompt: "استخرج المخاطر أو التناقضات الحالية في البيانات وقدّم اقتراحات علاجية سريعة." },
    ],
  };
}

function buildCourseOpportunity(course, rate = 50) {
  const fundedEgp = sumBy(course.linked_investments, (item) => item.invested_total_egp || item.amount_egp || ((item.amount_usd || 0) * rate));
  const baseTarget = Math.max(
    Number(course.linked_investment_cost || 0),
    Number(course.total_revenue || 0) * 0.18,
    Number(course.students_count || 0) * 1800,
    25000,
  );
  const targetEgp = Math.round(baseTarget);
  const funding = Math.round(fundedEgp);
  const fundingPercent = progressPercent(funding, targetEgp);
  const investorPool = Number(course.distribution?.allocations_egp?.investor || 0);
  const expectedRoi = targetEgp ? Math.round(((investorPool - targetEgp) / targetEgp) * 100) : 0;
  const status = course.status === "draft"
    ? "invite_only"
    : fundingPercent >= 100
      ? "funded"
      : (course.students_count || 0) >= 5
        ? "hot"
        : "open";
  const startDate = course.start_date || "";
  const endDate = course.end_date || "";
  const expectedDistribution = endDate ? new Date(new Date(endDate).getTime() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10) : "";
  return {
    ...course,
    funded_egp: funding,
    target_egp: targetEgp,
    funded_usd: Math.round(funding / rate),
    target_usd: Math.round(targetEgp / rate),
    min_investment_usd: Math.max(80, Math.round((targetEgp / rate) * 0.15)),
    funding_percent: fundingPercent,
    status,
    expected_roi: expectedRoi,
    expected_distribution: expectedDistribution,
    investor_pool_egp: investorPool,
    direct_costs_egp: Number(course.linked_expense_cost || 0) + Number(course.linked_payout_cost || 0) + Number(course.linked_investment_cost || 0),
    execution_label: (course.linked_expenses || []).some((item) => item.category === "course_delivery") ? "حضوري / تنفيذ مباشر" : "أونلاين / تنفيذ مرن",
  };
}

function buildTrainerBadges(courses, investments, payouts) {
  const profitable = courses.some((course) => (course.profit || 0) > 0);
  return [
    { key: "first-course", label: "أول دورة", description: "أطلقت أول دورة تحت حسابك", earned: courses.length > 0 },
    { key: "five-students", label: "5 طلاب+", description: "وصلت إلى خمسة طلاب أو أكثر", earned: sumBy(courses, (course) => course.students_count) >= 5 },
    { key: "profit", label: "دورة مربحة", description: "حققت صافي ربح إيجابي", earned: profitable },
    { key: "trainer-investor", label: "مدرب مستثمر", description: "ضخيت تمويلًا في دورة من حسابك", earned: investments.length > 0 },
    { key: "paid-payout", label: "دفعة مستلمة", description: "تم سداد جزء من مستحقاتك", earned: payouts.some((item) => item.status === "paid") },
  ];
}

function buildInvestorBadges(investments) {
  const positiveRoi = investments.some((item) => (item.roi_percent || 0) > 0);
  const courseCount = new Set(investments.map((item) => item.course_id)).size;
  return [
    { key: "first-investment", label: "أول استثمار", description: "دخلت أول فرصة تمويل", earned: investments.length > 0 },
    { key: "three-courses", label: "3 دورات", description: "شاركت في ثلاث فرص أو أكثر", earned: courseCount >= 3 },
    { key: "roi-50", label: "عائد +50%", description: "حققت أو تتجه لعائد قوي", earned: investments.some((item) => (item.roi_percent || 0) >= 50) },
    { key: "profitable", label: "عائد إيجابي", description: "لديك استثمار واحد على الأقل بعائد موجب", earned: positiveRoi },
    { key: "diversified", label: "تنويع جيد", description: "استثماراتك موزعة على أكثر من دورة", earned: courseCount >= 2 },
  ];
}

function CourseOpportunityDetailsModal({ open, onClose, opportunity, rate = 50, preference = "EGP", mode = "investor", onInvest }) {
  if (!open || !opportunity) return null;
  const split = opportunity.revenue_split || {};
  const distribution = opportunity.distribution || {};
  const timeline = [
    { label: "فتح التمويل والإعلان", date: opportunity.start_date || opportunity.expected_start || "مفتوح الآن", note: "يبدأ الضخ الإعلاني ومتابعة التسجيلات." },
    { label: "بداية البرنامج", date: opportunity.start_date || "سيحدد لاحقًا", note: "تبدأ الدورة أو الورشة في التاريخ المحدد." },
    { label: "نهاية البرنامج", date: opportunity.end_date || "بحسب الخطة", note: "يُغلق باب التنفيذ وتراجع الأعداد النهائية." },
    { label: "توزيع الأرباح", date: opportunity.expected_distribution || "بعد النهاية بأسبوع", note: "يتم التوزيع بعد نهاية البرنامج بأسبوع ما لم يحدث إلغاء أو خسارة." },
  ];
  const affiliateLabel = split.affiliate_percent ? `${split.affiliate_percent}%` : "بحسب وجود أفلييت";
  return (
    <Modal open={open} onClose={onClose} title={`تفاصيل ${opportunity.title || opportunity.course_title}`} maxWidth={920} width="95%">
      <div style={{ display: "grid", gap: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 13, color: "#667085" }}>{opportunity.execution_label} • {opportunity.trainer_name || "مدرب غير محدد"}</div>
            <div style={{ marginTop: 6, fontSize: 14, color: "#475467" }}>
              {opportunity.students_count || 0} طالب حاليًا • يبدأ {opportunity.start_date || "قريبًا"} • ينتهي {opportunity.end_date || "لاحقًا"}
            </div>
          </div>
          <StatusPill text={opportunityStatusLabels[opportunity.status] || opportunity.status} color={opportunityStatusColors[opportunity.status] || BRAND.navy} subtle />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
          <KPICard label="التمويل المطلوب" value={primaryMoney(opportunity.target_egp, rate, preference)} sub={secondaryMoney(opportunity.target_egp, rate, preference)} color={BRAND.navy} />
          <KPICard label="الممول حتى الآن" value={primaryMoney(opportunity.funded_egp, rate, preference)} sub={`${Number(opportunity.funding_percent || 0).toFixed(0)}%`} color="#059669" />
          <KPICard label="العائد المتوقع للمستثمرين" value={`${Number(opportunity.expected_roi || 0).toFixed(0)}%`} sub={primaryMoney(opportunity.investor_pool_egp, rate, preference)} color={BRAND.gold} />
          <KPICard label="صافي الربح القابل للتوزيع" value={primaryMoney(distribution.net_distributable_profit, rate, preference)} sub={secondaryMoney(distribution.net_distributable_profit, rate, preference)} color="#8e44ad" />
        </div>

        <PageSection title="شريط التمويل">
          <div style={{ display: "grid", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#667085" }}>
              <span>تمويل فعلي {primaryMoney(opportunity.funded_egp, rate, preference)}</span>
              <span>{Number(opportunity.funding_percent || 0).toFixed(0)}%</span>
            </div>
            <ProgressBar value={opportunity.funding_percent} color={opportunity.status === "hot" ? `linear-gradient(90deg, ${BRAND.gold}, ${BRAND.amber})` : "linear-gradient(90deg, #059669, #10b981)"} />
          </div>
        </PageSection>

        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 18 }}>
          <PageSection title="هيكل التوزيع">
            <div style={{ display: "grid", gap: 10, fontSize: 13, color: "#475467" }}>
              <div>المدرب: <strong>{split.trainer_percent || 0}%</strong> — {primaryMoney(distribution.allocations_egp?.trainer || 0, rate, preference)}</div>
              <div>المنصة: <strong>{split.platform_percent || 0}%</strong> — {primaryMoney(distribution.allocations_egp?.platform || 0, rate, preference)}</div>
              <div>المستثمرون: <strong>{split.investor_percent || 0}%</strong> — {primaryMoney(distribution.allocations_egp?.investor || 0, rate, preference)}</div>
              <div>الأفلييت: <strong>{affiliateLabel}</strong> — {primaryMoney(distribution.allocations_egp?.affiliate || 0, rate, preference)}</div>
              <div style={{ marginTop: 6, color: split.valid ? "#059669" : "#c0392b", fontWeight: 900 }}>
                {split.valid ? "النسب مضبوطة على 100%" : `مجموع النسب الحالي ${split.total_percent || 0}%`}
              </div>
            </div>
          </PageSection>

          <PageSection title="السيناريو التشغيلي">
            <div style={{ display: "grid", gap: 10, fontSize: 13, color: "#475467", lineHeight: 1.9 }}>
              <div>إذا كانت الدورة أونلاين، فكل تسجيل جديد ينعكس مباشرة على الإيراد المتوقع، ومعه ترتفع حصة المستثمر بحسب نسبة مساهمته من بند الإعلان.</div>
              <div>إذا انتهى البرنامج خلال أسبوعين، فالتوزيع المبدئي يُقفل بعد أسبوع إضافي لمراجعة التحصيل والمصروفات النهائية.</div>
              <div>في حالة الخسارة أو الإلغاء لعدم اكتمال العدد، يظهر الملف كدورة متعثرة ويُعاد تقييم التعويض أو الزيادة في فرصة لاحقة.</div>
            </div>
          </PageSection>
        </div>

        <PageSection title="الجدول الزمني المالي">
          <div style={{ display: "grid", gap: 12 }}>
            {timeline.map((item) => (
              <div key={item.label} style={{ display: "grid", gridTemplateColumns: "170px 1fr", gap: 12, padding: "10px 0", borderTop: "1px solid #f3f4f6" }}>
                <div style={{ fontWeight: 900, color: BRAND.navy }}>{item.label}</div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 800, color: BRAND.ink }}>{item.date}</div>
                  <div style={{ marginTop: 4, fontSize: 12, color: "#667085" }}>{item.note}</div>
                </div>
              </div>
            ))}
          </div>
        </PageSection>

        {onInvest && (
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, flexWrap: "wrap" }}>
            <Btn variant="secondary" color={BRAND.navy} onClick={onClose}>إغلاق</Btn>
            <Btn color={mode === "trainer" ? BRAND.navy : BRAND.gold} onClick={onInvest} style={mode === "trainer" ? {} : { color: BRAND.navy }}>
              {mode === "trainer" ? "تقديم طلب استثمار من حساب المدرب" : "استثمر الآن"}
            </Btn>
          </div>
        )}
      </div>
    </Modal>
  );
}

function InvestmentCommitModal({ open, onClose, opportunity, rate = 50, preference = "EGP", investorName, mode = "investor", onSubmit }) {
  const [amountEgp, setAmountEgp] = useState(0);
  useEffect(() => {
    if (!open) return;
    setAmountEgp(Math.round((opportunity?.min_investment_usd || 100) * rate));
  }, [open, opportunity, rate]);
  if (!open || !opportunity) return null;
  const contributionShare = progressPercent(amountEgp, opportunity.target_egp);
  const investorPool = Number(opportunity.investor_pool_egp || 0);
  const expectedPayout = Math.round((contributionShare / 100) * investorPool);
  const expectedNet = expectedPayout - amountEgp;
  const expectedPercent = Number(opportunity.revenue_split?.investor_percent || 0) * contributionShare / 100;
  return (
    <Modal open={open} onClose={onClose} title={mode === "trainer" ? `تمويل دورة ${opportunity.title}` : `استثمر في ${opportunity.title}`} maxWidth={700}>
      <div style={{ display: "grid", gap: 16 }}>
        <div style={{ fontSize: 13, color: "#667085", lineHeight: 1.8 }}>
          سيتم تسجيل الطلب باسم <strong>{investorName}</strong> مع توضيح أنك {mode === "trainer" ? "مدرب ومستثمر في نفس الوقت" : "مستثمر"} في هذه الدورة.
        </div>
        <Input label="المبلغ المراد ضخه (ج.م)" type="number" value={amountEgp} onChange={e => setAmountEgp(+e.target.value)} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
          <div style={{ borderRadius: 12, border: "1px solid #edf2f7", padding: 14 }}>
            <div style={{ fontSize: 11, color: "#667085" }}>مساهمتك من التمويل</div>
            <div style={{ fontSize: 18, fontWeight: 900, color: BRAND.navy }}>{contributionShare.toFixed(1)}%</div>
          </div>
          <div style={{ borderRadius: 12, border: "1px solid #edf2f7", padding: 14 }}>
            <div style={{ fontSize: 11, color: "#667085" }}>حصتك من نسبة المستثمرين</div>
            <div style={{ fontSize: 18, fontWeight: 900, color: BRAND.navy }}>{expectedPercent.toFixed(1)}%</div>
          </div>
          <div style={{ borderRadius: 12, border: "1px solid #edf2f7", padding: 14 }}>
            <div style={{ fontSize: 11, color: "#667085" }}>العائد المتوقع</div>
            <div style={{ fontSize: 18, fontWeight: 900, color: "#059669" }}>{primaryMoney(expectedPayout, rate, preference)}</div>
          </div>
          <div style={{ borderRadius: 12, border: "1px solid #edf2f7", padding: 14 }}>
            <div style={{ fontSize: 11, color: "#667085" }}>صافي الربح المتوقع</div>
            <div style={{ fontSize: 18, fontWeight: 900, color: expectedNet >= 0 ? "#059669" : "#DC2626" }}>{primaryMoney(expectedNet, rate, preference)}</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Btn variant="secondary" color={BRAND.navy} onClick={onClose} style={{ flex: 1, minHeight: 44 }}>إلغاء</Btn>
          <Btn color={mode === "trainer" ? BRAND.navy : BRAND.gold} onClick={() => onSubmit?.(amountEgp)} style={{ flex: 1, minHeight: 44, ...(mode === "trainer" ? {} : { color: BRAND.navy }) }}>
            {mode === "trainer" ? "تسجيل طلب الاستثمار" : "تأكيد الاستثمار"}
          </Btn>
        </div>
      </div>
    </Modal>
  );
}

function AIPage() {
  const user = useAuth();
  const role = getEffectiveRole(user);
  const copy = roleAiConfig(role);
  const [models, setModels] = useState([]);
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get("/ai/models").then(items => {
      const safeModels = safeArray(items);
      if (!safeModels.length) return;
      setModels(safeModels);
      const firstConfigured = safeModels.find(item => item.configured) || safeModels[0];
      setProvider(firstConfigured.id);
      setModel(firstConfigured.default_model);
    });
  }, []);

  const selectedProvider = models.find(item => item.id === provider);
  const selectedModels = selectedProvider?.models || [];

  const ask = async (q) => {
    const question = q || input;
    if (!question.trim()) return;
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: question }]);
    setLoading(true);
    try {
      const data = await api.post("/ai/ask", { question, provider, model });
      setMessages(prev => [...prev, { role: "assistant", content: data.response || data.error || "لم أتمكن من الإجابة." }]);
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "تعذر الوصول إلى مساعد AI الآن." }]);
    }
    setLoading(false);
  };

  return (
    <div style={{ maxWidth: 820, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 900, color: BRAND.navy, margin: 0 }}>{copy.title}</h1>
          <div style={{ marginTop: 6, fontSize: 12, color: selectedProvider?.configured ? "#2d8659" : "#c0392b" }}>
            {selectedProvider?.configured ? copy.subtitle : "أضف API key في إعدادات السيرفر لتفعيل هذا المزود"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <select value={provider} onChange={e => {
            const nextProvider = e.target.value;
            const next = models.find(item => item.id === nextProvider);
            setProvider(nextProvider);
            setModel(next?.default_model || "");
          }} style={{ border: "1px solid #d1d5db", borderRadius: 8, padding: "8px 10px", fontSize: 12, background: "#fff" }}>
            {models.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
          <select value={model} onChange={e => setModel(e.target.value)} style={{ border: "1px solid #d1d5db", borderRadius: 8, padding: "8px 10px", fontSize: 12, background: "#fff", maxWidth: 180 }}>
            {selectedModels.map(item => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
      </div>

      <div style={{ background: "#fff", borderRadius: 16, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", overflow: "hidden", border: "1px solid #edf2f7" }}>
        <div style={{ minHeight: 400, maxHeight: "calc(100vh - 300px)", overflowY: "auto", padding: 22 }}>
          {messages.length === 0 && (
            <div style={{ textAlign: "center", padding: "42px 20px", color: "#98a2b3" }}>
              <div style={{ fontSize: 24, marginBottom: 12 }}>AI</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: BRAND.navy }}>{copy.welcome}</div>
              <div style={{ fontSize: 13, marginTop: 8 }}>{copy.subtitle}</div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", marginBottom: 14 }}>
              <div style={{ maxWidth: "78%", padding: "12px 16px", borderRadius: 16, background: m.role === "user" ? BRAND.navy : "#f4f6f8", color: m.role === "user" ? "#fff" : BRAND.ink, fontSize: 14, lineHeight: 1.8, whiteSpace: "pre-wrap" }}>{m.content}</div>
            </div>
          ))}
          {loading && <div style={{ display: "flex", justifyContent: "flex-start" }}><div style={{ padding: "12px 16px", borderRadius: 16, background: "#f4f6f8", color: "#667085", fontSize: 13 }}>جاري التحليل...</div></div>}
        </div>
        <div style={{ position: "sticky", bottom: 0, background: "#fff", borderTop: "1px solid #e5e7eb", padding: 14 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
            {copy.quickActions.map((a) => (
              <button key={a.label} onClick={() => ask(a.prompt)} disabled={loading} style={{ padding: "7px 10px", borderRadius: 999, border: "1px solid #d8dee9", background: "#fafbfd", fontSize: 12, fontWeight: 700, cursor: loading ? "not-allowed" : "pointer", color: BRAND.navy }}>
                {a.label}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && ask()} placeholder={copy.placeholder} disabled={loading} style={{ flex: 1, padding: "12px 16px", borderRadius: 12, border: "1px solid #d1d5db", fontSize: 14 }} />
            <Btn onClick={() => ask()} disabled={loading || !input.trim()} style={{ padding: "12px 20px" }}>إرسال</Btn>
          </div>
        </div>
      </div>
    </div>
  );
}

function AIAssistantDock() {
  const user = useAuth();
  const role = getEffectiveRole(user);
  const copy = roleAiConfig(role);
  const isMobile = useIsMobile(768);
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState([]);
  const [provider, setProvider] = useState("deepseek");
  const [model, setModel] = useState("deepseek-chat");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([{ role: "assistant", content: copy.welcome }]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setMessages([{ role: "assistant", content: copy.welcome }]);
  }, [copy.welcome]);

  useEffect(() => {
    api.get("/ai/models").then(items => {
      const safeModels = safeArray(items);
      if (!safeModels.length) return;
      setModels(safeModels);
      const firstConfigured = safeModels.find(item => item.configured) || safeModels[0];
      if (firstConfigured) {
        setProvider(firstConfigured.id);
        setModel(firstConfigured.default_model);
      }
    });
  }, []);

  const ask = async (preset) => {
    const question = preset || input;
    if (!question.trim()) return;
    setOpen(true);
    setInput("");
    setLoading(true);
    setMessages(prev => [...prev, { role: "user", content: question }]);
    try {
      const data = await api.post("/ai/ask", { question, provider, model });
      setMessages(prev => [...prev, { role: "assistant", content: data.response || data.error || "لم أتمكن من الإجابة." }]);
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "تعذر الوصول إلى مساعد AI الآن." }]);
    }
    setLoading(false);
  };

  return (
    <div style={{ position: "fixed", left: isMobile ? 12 : 24, bottom: isMobile ? 12 : 24, zIndex: 900 }}>
      {open && (
        <div style={{ width: isMobile ? "calc(100vw - 24px)" : 380, maxWidth: 420, background: "#fff", border: "1px solid #E6D7A8", borderRadius: 14, boxShadow: "0 24px 70px rgba(16,27,47,.18)", overflow: "hidden", marginBottom: 12 }}>
          <div style={{ background: BRAND.navy, color: "#fff", padding: "14px 16px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
            <strong>{copy.title}</strong>
            <button onClick={() => setOpen(false)} style={{ background: "transparent", border: 0, color: "#fff", fontSize: 18 }}>×</button>
          </div>
          <div style={{ padding: 12, display: "flex", gap: 8, flexWrap: "wrap", borderBottom: "1px solid #f0eadb" }}>
            {copy.quickActions.slice(0, 3).map((item) => (
              <button key={item.label} onClick={() => ask(item.prompt)} style={{ border: "1px solid #E6D7A8", background: "#FFFDF8", borderRadius: 18, padding: "7px 10px", fontSize: 12, color: BRAND.navy, fontWeight: 700 }}>{item.label}</button>
            ))}
          </div>
          <div style={{ height: 260, overflowY: "auto", padding: 14 }}>
            {messages.map((m, i) => (
              <div key={i} style={{ marginBottom: 10, display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
                <div style={{ maxWidth: "86%", whiteSpace: "pre-wrap", lineHeight: 1.65, fontSize: 13, padding: "10px 12px", borderRadius: 12, background: m.role === "user" ? BRAND.navy : "#F7F4EB", color: m.role === "user" ? "#fff" : BRAND.ink }}>{m.content}</div>
              </div>
            ))}
            {loading && <div style={{ color: "#667085", fontSize: 13 }}>جاري التحليل...</div>}
          </div>
          <div style={{ display: "flex", gap: 8, padding: 12, borderTop: "1px solid #f0eadb" }}>
            <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && ask()} placeholder={copy.placeholder} style={{ flex: 1, border: "1px solid #D9D3C4", borderRadius: 10, padding: "10px 12px", fontSize: 13 }} />
            <button onClick={() => ask()} disabled={loading} style={{ background: BRAND.gold, color: BRAND.navy, border: 0, borderRadius: 10, padding: "0 14px", fontWeight: 900 }}>إرسال</button>
          </div>
        </div>
      )}
      <button onClick={() => setOpen(!open)} style={{ background: BRAND.gold, color: BRAND.navy, border: "1px solid #C99A2E", borderRadius: 999, padding: "14px 18px", fontWeight: 900, boxShadow: "0 12px 30px rgba(217,179,76,.35)", minHeight: 48 }}>مساعد AI</button>
    </div>
  );
}

function MyEarningsPage() {
  const user = useAuth();
  const preference = resolveCurrencyPreference(user);
  const [courses, setCourses] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [allInvestments, setAllInvestments] = useState([]);
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [investOpen, setInvestOpen] = useState(false);
  const [tab, setTab] = useState("courses");
  const [rate, setRate] = useState(50);
  const trainerName = currentUserName(user);

  const load = useCallback(async () => {
    const [settings, coursesData, payoutsData, investmentsData] = await Promise.all([
      api.get("/settings"),
      api.get("/courses"),
      api.get("/payouts"),
      api.get("/investments"),
    ]);
    setRate(Number(settings?.exchange_rate || 50));
    setCourses(safeArray(coursesData));
    setPayouts(safeArray(payoutsData));
    setAllInvestments(safeArray(investmentsData).filter((item) => (item.investor_name || "").trim() === trainerName));
  }, [trainerName]);

  useEffect(() => { load(); }, [load]);

  const opportunities = courses.map((course) => buildCourseOpportunity(course, rate));
  const accrued = sumBy(payouts.filter((item) => item.status !== "paid"), (item) => item.total_egp);
  const paid = sumBy(payouts.filter((item) => item.status === "paid"), (item) => item.total_egp);
  const invested = sumBy(allInvestments, (item) => item.invested_total_egp);
  const returns = sumBy(allInvestments, (item) => item.due_egp);
  const avgRoi = allInvestments.length ? sumBy(allInvestments, (item) => item.roi_percent) / allInvestments.length : 0;
  const activeInvestments = allInvestments.filter((item) => item.status !== "paid");
  const historyInvestments = allInvestments.filter((item) => item.status === "paid" || (item.roi_percent || 0) < 0);
  const badges = buildTrainerBadges(courses, allInvestments, payouts);
  const aiTip = opportunities.slice().sort((a, b) => (a.funding_percent - b.funding_percent) || ((a.students_count || 0) - (b.students_count || 0)))[0];

  const submitTrainerInvestment = async (amountEgp) => {
    if (!selectedOpportunity) return;
    await api.post("/investments", {
      course_id: selectedOpportunity.id,
      investor_name: trainerName,
      amount_egp: Number(amountEgp || 0),
      amount_usd: Math.round(Number(amountEgp || 0) / rate),
      profit_percent: Number(selectedOpportunity.revenue_split?.investor_percent || 0),
      status: "pending",
      notes: "طلب استثمار من حساب المدرب",
    });
    setInvestOpen(false);
    load();
  };

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy, marginBottom: 18 }}>لوحة المدرب</h1>
      <WalletHero
        title="محفظة المدرب"
        balanceEgp={accrued - paid}
        investedEgp={invested}
        returnsEgp={returns}
        avgRoi={avgRoi}
        rate={rate}
        preference={preference}
        badgeText="مدرب نشط"
        accent={BRAND.gold}
        footerNote="كل دورة تنتهي، ثم تُراجع الحسابات ويبدأ توزيع المستحقات بعدها بأسبوع."
      />

      {aiTip && (
        <div style={{ borderRadius: 16, background: "#FDF8E8", border: "1px solid #f4e2a8", padding: 16, marginBottom: 20, fontSize: 13, color: "#5b6475", lineHeight: 1.8 }}>
          <strong style={{ color: BRAND.gold }}>تنبيه ذكي:</strong> دورة <strong>{aiTip.title}</strong> تحتاج قرارًا الآن. التمويل الحالي {Number(aiTip.funding_percent).toFixed(0)}%، ويمكن أن تستفيد من ضخ إعلاني مبكر قبل {aiTip.start_date || "بدء التنفيذ"}.
        </div>
      )}

      <TabBar
        tabs={[
          { id: "courses", label: "ملخص دوراتي" },
          { id: "investments", label: "استثماري" },
          { id: "payouts", label: "أرباحي" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "courses" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          {opportunities.map((opportunity) => (
            <div key={opportunity.id} style={{ background: "#fff", borderRadius: 16, border: "1px solid #e6ecf2", padding: 18, display: "grid", gap: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 900, color: BRAND.ink }}>{opportunity.title}</div>
                  <div style={{ marginTop: 6, fontSize: 12, color: "#667085" }}>{opportunity.students_count || 0} طالب • {opportunity.execution_label}</div>
                </div>
                <StatusPill text={opportunityStatusLabels[opportunity.status] || opportunity.status} color={opportunityStatusColors[opportunity.status] || BRAND.navy} subtle />
              </div>
              <div className="card-meta" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 12 }}>
                <div><div style={{ fontSize: 11, color: "#667085" }}>الإيراد</div><div style={{ fontWeight: 900 }}>{primaryMoney(opportunity.total_revenue, rate, preference)}</div></div>
                <div><div style={{ fontSize: 11, color: "#667085" }}>صافي الربح</div><div style={{ fontWeight: 900, color: opportunity.profit >= 0 ? "#059669" : "#DC2626" }}>{primaryMoney(opportunity.profit, rate, preference)}</div></div>
                <div><div style={{ fontSize: 11, color: "#667085" }}>حصة المدرب</div><div style={{ fontWeight: 900 }}>{primaryMoney(opportunity.distribution?.allocations_egp?.trainer || 0, rate, preference)}</div></div>
              </div>
              <ProgressBar value={opportunity.funding_percent} color={opportunity.status === "hot" ? `linear-gradient(90deg, ${BRAND.gold}, ${BRAND.amber})` : "linear-gradient(90deg, #059669, #10b981)"} />
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <Btn variant="secondary" color={BRAND.navy} onClick={() => { setSelectedOpportunity(opportunity); setDetailOpen(true); }} style={{ flex: 1, minHeight: 44 }}>التفاصيل المالية</Btn>
                <Btn color={BRAND.navy} onClick={() => { setSelectedOpportunity(opportunity); setInvestOpen(true); }} style={{ flex: 1, minHeight: 44 }}>استثمر في دورتي</Btn>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "investments" && (
        <PageSection title="استثمارات المدرب" subtitle="لو موّلت دورة من حسابك، تظهر هنا كأنت مدرب ومستثمر في نفس الوقت.">
          {activeInvestments.length || historyInvestments.length ? (
            <div style={{ display: "grid", gap: 12 }}>
              {[...activeInvestments, ...historyInvestments].map((item) => (
                <div key={item.id} style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center", padding: "14px 0", borderTop: "1px solid #f3f4f6", flexWrap: "wrap" }}>
                  <div>
                    <div style={{ fontWeight: 900, color: BRAND.ink }}>{item.course_title}</div>
                    <div style={{ marginTop: 6, fontSize: 12, color: "#667085" }}>استثمار {primaryMoney(item.invested_total_egp, rate, preference)} • حصة {item.profit_percent}%</div>
                  </div>
                  <div style={{ textAlign: "left" }}>
                    <div style={{ fontWeight: 900, color: "#059669" }}>{primaryMoney(item.due_egp, rate, preference)}</div>
                    <div style={{ marginTop: 6, fontSize: 12, color: "#667085" }}>{Number(item.roi_percent || 0).toFixed(1)}% ROI</div>
                  </div>
                </div>
              ))}
            </div>
          ) : <EmptyState title="لا توجد استثمارات من حساب المدرب" text="بمجرد ضخك تمويلًا في إحدى دوراتك ستبدأ المتابعة هنا." />}
        </PageSection>
      )}

      {tab === "payouts" && (
        <PageSection title="تفصيل الأرباح" subtitle="هذه هي المستحقات المباشرة للمدرب من الدورات.">
          {payouts.length ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead><tr style={{ background: "#f8fafc" }}>
                {["الدورة", "الشهر", "المستحق", "الحالة", "المتبقي"].map(h => <th key={h} style={{ padding: "12px 14px", textAlign: "right", color: "#667085", borderBottom: "1px solid #e5e7eb" }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {payouts.map(item => (
                  <tr key={item.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "12px 14px", fontWeight: 800 }}>{item.related_to || "—"}</td>
                    <td style={{ padding: "12px 14px" }}>{item.date?.slice(0, 7) || "—"}</td>
                    <td style={{ padding: "12px 14px" }}>{primaryMoney(item.total_egp, rate, preference)}<div style={{ fontSize: 12, color: "#94a3b8" }}>{secondaryMoney(item.total_egp, rate, preference)}</div></td>
                    <td style={{ padding: "12px 14px" }}><Badge text={item.status === "paid" ? "مدفوع" : "مستحق"} color={item.status === "paid" ? "#2d8659" : "#8e44ad"} /></td>
                    <td style={{ padding: "12px 14px", color: item.status === "paid" ? "#2d8659" : "#c0392b", fontWeight: 900 }}>{item.status === "paid" ? primaryMoney(0, rate, preference) : primaryMoney(item.total_egp, rate, preference)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <EmptyState title="لا توجد أرباح مسجلة" text="عند إضافة مستحقات مرتبطة بك ستظهر هنا." />}
        </PageSection>
      )}

      <AchievementStrip title="تحفيز المدرب" subtitle="كل خطوة في نمو الدورات والتمويل تظهر هنا كتقدم ملموس." badges={badges} />

      <CourseOpportunityDetailsModal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        opportunity={selectedOpportunity}
        rate={rate}
        preference={preference}
        mode="trainer"
        onInvest={() => { setDetailOpen(false); setInvestOpen(true); }}
      />
      <InvestmentCommitModal
        open={investOpen}
        onClose={() => setInvestOpen(false)}
        opportunity={selectedOpportunity}
        rate={rate}
        preference={preference}
        investorName={trainerName}
        mode="trainer"
        onSubmit={submitTrainerInvestment}
      />
    </div>
  );
}

function InvestorInvestmentsPage({ initialTab = "opportunities" }) {
  const user = useAuth();
  const preference = resolveCurrencyPreference(user);
  const [rate, setRate] = useState(50);
  const [courses, setCourses] = useState([]);
  const [investments, setInvestments] = useState([]);
  const [tab, setTab] = useState(initialTab);
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [investOpen, setInvestOpen] = useState(false);
  const investorName = currentUserName(user);

  const load = useCallback(async () => {
    const [settings, coursesData, investmentsData] = await Promise.all([
      api.get("/settings"),
      api.get("/courses?scope=marketplace"),
      api.get("/investments"),
    ]);
    setRate(Number(settings?.exchange_rate || 50));
    setCourses(safeArray(coursesData));
    setInvestments(safeArray(investmentsData));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setTab(initialTab); }, [initialTab]);

  const opportunities = courses.map((course) => buildCourseOpportunity(course, rate));
  const myInvestments = investments.filter((item) => (item.investor_name || "").trim() === investorName);
  const activeInvestments = myInvestments.filter((item) => item.status !== "paid");
  const historyInvestments = myInvestments.filter((item) => item.status === "paid" || (item.roi_percent || 0) < 0);
  const totalInvested = sumBy(myInvestments, (item) => item.invested_total_egp);
  const totalReturns = sumBy(myInvestments, (item) => item.due_egp);
  const avgRoi = myInvestments.length ? sumBy(myInvestments, (item) => item.roi_percent) / myInvestments.length : 0;
  const recommendation = opportunities.slice().sort((a, b) => ((b.expected_roi || 0) - (a.expected_roi || 0)) || ((a.funding_percent || 0) - (b.funding_percent || 0)))[0];
  const badges = buildInvestorBadges(myInvestments);

  const submitInvestment = async (amountEgp) => {
    if (!selectedOpportunity) return;
    await api.post("/investments", {
      course_id: selectedOpportunity.id,
      investor_name: investorName,
      amount_egp: Number(amountEgp || 0),
      amount_usd: Math.round(Number(amountEgp || 0) / rate),
      profit_percent: Number(selectedOpportunity.revenue_split?.investor_percent || 0),
      status: "pending",
      notes: "استثمار جديد من صفحة المستثمر",
    });
    setInvestOpen(false);
    load();
  };

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy, marginBottom: 20 }}>{initialTab === "active" ? "استثماراتي" : "ماركت الاستثمار"}</h1>
      <WalletHero
        title="محفظة المستثمر"
        balanceEgp={Math.max(0, totalReturns - totalInvested)}
        investedEgp={totalInvested}
        returnsEgp={totalReturns}
        avgRoi={avgRoi}
        rate={rate}
        preference={preference}
        badgeText="مستثمر ذهبي"
        accent={BRAND.gold}
        footerNote="الرصيد القابل للسحب يُراجع تشغيليًا خلال أسبوع عمل بعد طلب السحب."
      />

      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
        {[
          ["opportunities", "فرص استثمارية"],
          ["active", "استثماراتي النشطة"],
          ["history", "السجل"],
        ].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{ minHeight: 44, padding: "10px 16px", borderRadius: 12, border: tab === id ? "none" : "1px solid #d0d5dd", background: tab === id ? BRAND.navy : "#fff", color: tab === id ? "#fff" : "#475467", fontWeight: 800, cursor: "pointer" }}>{label}</button>
        ))}
      </div>

      {tab === "opportunities" && (
        <div style={{ display: "grid", gap: 20 }}>
          {recommendation && (
            <div style={{ borderRadius: 16, background: "#FDF8E8", border: "1px solid #f4e2a8", padding: 16, fontSize: 13, color: "#5b6475", lineHeight: 1.8 }}>
              <strong style={{ color: BRAND.gold }}>توصية AI:</strong> فرصة <strong>{recommendation.title}</strong> تبدو الأنسب الآن لأنها توازن بين عائد متوقع {recommendation.expected_roi}% وحالة تمويل {Number(recommendation.funding_percent || 0).toFixed(0)}%.
            </div>
          )}

          <PageSection title="كيف يعمل نموذج الاستثمار في البروفيسور؟" subtitle="فيديو توضيحي سيُربط لاحقًا، لكن الرؤية واضحة من داخل الكروت والتفاصيل.">
            <div style={{ borderRadius: 18, background: "#1a2b4a", minHeight: 220, display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
              <div style={{ width: 72, height: 72, borderRadius: "50%", background: BRAND.gold, color: BRAND.navy, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 26, fontWeight: 900 }}>▶</div>
            </div>
          </PageSection>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 18 }}>
            {opportunities.map((opportunity) => (
              <div key={opportunity.id} style={{ background: "#fff", borderRadius: 16, border: "1px solid #e6ecf2", padding: 18, display: "grid", gap: 14, opacity: opportunity.status === "invite_only" ? 0.72 : 1, boxShadow: "0 10px 30px rgba(16,27,47,.05)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 900, color: BRAND.ink }}>{opportunity.title}</div>
                    <div style={{ marginTop: 6, fontSize: 11, color: "#667085" }}>{opportunity.start_date || "قريبًا"} • {opportunity.execution_label}</div>
                  </div>
                  <StatusPill text={opportunityStatusLabels[opportunity.status] || opportunity.status} color={opportunityStatusColors[opportunity.status] || BRAND.navy} subtle />
                </div>
                <div className="card-meta" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 12 }}>
                  <div><div style={{ fontSize: 11, color: "#667085" }}>الحد الأدنى</div><div style={{ fontWeight: 900 }}>{preference === "USD" ? fmtUSD(opportunity.min_investment_usd) : egpLabel(opportunity.min_investment_usd * rate)}</div></div>
                  <div><div style={{ fontSize: 11, color: "#667085" }}>العائد المتوقع</div><div style={{ fontWeight: 900, color: "#059669" }}>{opportunity.status === "invite_only" ? "—" : `${opportunity.expected_roi}%`}</div></div>
                  <div><div style={{ fontSize: 11, color: "#667085" }}>التمويل المطلوب</div><div style={{ fontWeight: 900 }}>{primaryMoney(opportunity.target_egp, rate, preference)}</div></div>
                </div>
                <ProgressBar value={opportunity.funding_percent} color={opportunity.status === "hot" ? `linear-gradient(90deg, ${BRAND.gold}, ${BRAND.amber})` : "linear-gradient(90deg, #059669, #10b981)"} />
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <Btn color={opportunity.status === "invite_only" ? BRAND.navy : BRAND.gold} onClick={() => { setSelectedOpportunity(opportunity); setInvestOpen(true); }} style={{ minHeight: 44, flex: 1, ...(opportunity.status === "invite_only" ? {} : { color: BRAND.navy }) }}>{opportunity.status === "invite_only" ? "تقديم طلب انضمام" : "استثمر الآن"}</Btn>
                  <Btn variant="secondary" color={BRAND.navy} onClick={() => { setSelectedOpportunity(opportunity); setDetailOpen(true); }} style={{ minHeight: 44, flex: 1 }}>التفاصيل</Btn>
                </div>
              </div>
            ))}
          </div>

          <AchievementStrip title="إنجازاتك الاستثمارية" subtitle="تقدمك الاستثماري يظهر هنا خطوة بخطوة." badges={badges} />
        </div>
      )}

      {tab === "active" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          {activeInvestments.length ? activeInvestments.map((item) => (
            <div key={item.id} style={{ background: "#fff", borderRadius: 16, border: "1px solid #e6ecf2", padding: 18, display: "grid", gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
                <div>
                  <div style={{ fontWeight: 900, color: BRAND.ink }}>{item.course_title}</div>
                  <div style={{ marginTop: 6, fontSize: 12, color: "#667085" }}>{item.created_at?.slice(0, 10) || "—"} • {primaryMoney(item.invested_total_egp, rate, preference)}</div>
                </div>
                <StatusPill text="جارية" color="#059669" subtle />
              </div>
              <div className="card-meta" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 12 }}>
                <div><div style={{ fontSize: 11, color: "#667085" }}>عدد الطلاب</div><div style={{ fontWeight: 900 }}>{courses.find((course) => course.id === item.course_id)?.students_count || 0}</div></div>
                <div><div style={{ fontSize: 11, color: "#667085" }}>الأرباح المتوقعة</div><div style={{ fontWeight: 900, color: "#059669" }}>{primaryMoney(item.due_egp, rate, preference)}</div></div>
                <div><div style={{ fontSize: 11, color: "#667085" }}>التوزيع المتوقع</div><div style={{ fontWeight: 900 }}>{courses.find((course) => course.id === item.course_id)?.end_date || "قريبًا"} + أسبوع</div></div>
              </div>
            </div>
          )) : <EmptyState title="لا توجد استثمارات نشطة" text="عند دخولك في أي فرصة ستظهر هنا متابعة الدورة والعائد المتوقع." />}
        </div>
      )}

      {tab === "history" && (
        <PageSection title="السجل" subtitle="كل العمليات السابقة مع إبراز أي خسارة أو تعثر.">
          {historyInvestments.length ? historyInvestments.map((item) => (
            <div key={item.id} style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center", padding: "14px 0", borderTop: "1px solid #f3f4f6" }}>
              <div>
                <div style={{ fontWeight: 800, color: BRAND.ink }}>{item.course_title}</div>
                <div style={{ marginTop: 6, fontSize: 12, color: "#667085" }}>{item.created_at?.slice(0, 10) || "—"} • استثمار {primaryMoney(item.invested_total_egp, rate, preference)}</div>
                {(item.roi_percent || 0) < 0 && <div style={{ marginTop: 6, fontSize: 12, color: "#DC2626" }}>في حالة الخسارة: تُراجع فرصة تعويضية في طرح لاحق</div>}
              </div>
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 900, color: (item.roi_percent || 0) < 0 ? "#DC2626" : "#059669" }}>{primaryMoney(item.due_egp, rate, preference)}</div>
                <div style={{ marginTop: 6, fontSize: 12, color: "#667085" }}>{Number(item.roi_percent || 0).toFixed(1)}%</div>
              </div>
            </div>
          )) : <EmptyState title="لا يوجد سجل بعد" text="بعد اكتمال أول دورة ممولة ستظهر النتائج هنا." />}
        </PageSection>
      )}

      <CourseOpportunityDetailsModal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        opportunity={selectedOpportunity}
        rate={rate}
        preference={preference}
        mode="investor"
        onInvest={() => { setDetailOpen(false); setInvestOpen(true); }}
      />
      <InvestmentCommitModal
        open={investOpen}
        onClose={() => setInvestOpen(false)}
        opportunity={selectedOpportunity}
        rate={rate}
        preference={preference}
        investorName={investorName}
        mode="investor"
        onSubmit={submitInvestment}
      />
    </div>
  );
}

// ============================================================
// SETTINGS PAGE
// ============================================================
function SettingsPage() {
  const user = useAuth();
  const [settings, setSettings] = useState({});
  const [users, setUsers] = useState([]);
  const [newUser, setNewUser] = useState({ role: "viewer", linked_to_name: "", preferred_currency: "AUTO" });
  const [converter, setConverter] = useState({ usd: 1, egp: 50, active: "usd" });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get("/settings").then(data => setSettings(safeObject(data)));
    api.get("/users").then(data => setUsers(safeArray(data)));
  }, []);

  const save = async () => {
    await api.put("/settings", settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };
  const refreshUsers = () => api.get("/users").then(data => setUsers(safeArray(data)));
  const addUser = async () => {
    const r = await api.post("/users", newUser);
    if (!r.error) { setNewUser({ role: "viewer", linked_to_name: "", preferred_currency: "AUTO" }); refreshUsers(); }
  };
  const updateUser = async (editedUser) => {
    const r = await api.put(`/users/${editedUser.id}`, editedUser);
    if (!r.error) refreshUsers();
  };
  const rate = Number(settings.exchange_rate || 50);
  const isAdmin = getEffectiveRole(user) === "admin";

  if (!isAdmin) {
    return <PageError message="هذه الصفحة متاحة للأدمن فقط." onRetry={() => window.location.reload()} />;
  }

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f4c81", marginBottom: 24 }}>الإعدادات</h1>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(360px, 500px) minmax(420px, 1fr)", gap: 20 }}>
      <div style={{ background: "#fff", borderRadius: 12, padding: 32, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
        <Input label="اسم الشركة" value={settings.company_name || ""} onChange={e => setSettings({ ...settings, company_name: e.target.value })} />
        <Input label="سعر صرف الدولار (ج.م)" type="number" value={settings.exchange_rate || 50} onChange={e => setSettings({ ...settings, exchange_rate: e.target.value })} />
        <div style={{ background: "#F7F4EB", border: "1px solid #E6D7A8", borderRadius: 10, padding: 14, marginBottom: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 900, color: BRAND.navy, marginBottom: 10 }}>محول سريع</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Input label="دولار" type="number" value={converter.usd} onChange={e => setConverter({ usd: +e.target.value, egp: +(e.target.value || 0) * rate, active: "usd" })} />
            <Input label="جنيه" type="number" value={converter.egp} onChange={e => setConverter({ egp: +e.target.value, usd: +(e.target.value || 0) / rate, active: "egp" })} />
          </div>
        </div>
        <Input label="الرصيد الافتتاحي (ج.م)" type="number" value={settings.opening_balance_egp || 0} onChange={e => setSettings({ ...settings, opening_balance_egp: e.target.value })} />
        <Input label="العملة الأساسية" value={settings.currency || "EGP"} onChange={e => setSettings({ ...settings, currency: e.target.value })} />
        <Input label="إيرادات بنكية خام ($)" type="number" value={settings.raw_bank_revenue_usd || 0} onChange={e => setSettings({ ...settings, raw_bank_revenue_usd: e.target.value })} />
        <Input label="مصروفات بنكية خام ($)" type="number" value={settings.raw_bank_expenses_usd || 0} onChange={e => setSettings({ ...settings, raw_bank_expenses_usd: e.target.value })} />
        <Btn onClick={save} style={{ width: "100%", marginTop: 8 }}>💾 حفظ الإعدادات</Btn>
        {saved && <div style={{ textAlign: "center", color: "#2d8659", marginTop: 12, fontWeight: 600 }}>✅ تم الحفظ</div>}
      </div>
      <div style={{ background: "#fff", borderRadius: 12, padding: 32, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
        <h2 style={{ color: BRAND.navy, fontWeight: 900, marginBottom: 16 }}>المستخدمون</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="الاسم" value={newUser.name || ""} onChange={e => setNewUser({ ...newUser, name: e.target.value })} />
          <Input label="البريد الإلكتروني" value={newUser.email || ""} onChange={e => setNewUser({ ...newUser, email: e.target.value })} />
        </div>
        <Input label="كلمة المرور" type="password" value={newUser.password || ""} onChange={e => setNewUser({ ...newUser, password: e.target.value })} />
        <Select label="الرول" value={newUser.role || "viewer"} onChange={e => setNewUser({ ...newUser, role: e.target.value })} options={Object.entries(userRoleLabels).map(([value, label]) => ({ value, label }))} />
        <Input label="مرتبط بـ" value={newUser.linked_to_name || ""} onChange={e => setNewUser({ ...newUser, linked_to_name: e.target.value })} placeholder="اسم المدرب أو المستثمر إن وجد" />
        <Select label="العملة المفضلة" value={newUser.preferred_currency || "AUTO"} onChange={e => setNewUser({ ...newUser, preferred_currency: e.target.value })} options={[{ value: "AUTO", label: "تلقائي / محلي" }, { value: "EGP", label: "جنيه مصري" }, { value: "USD", label: "دولار" }]} />
        <Btn onClick={addUser} color={BRAND.gold} style={{ color: BRAND.navy }}>إضافة مستخدم</Btn>
        <div style={{ marginTop: 12, fontSize: 12, color: "#667085", lineHeight: 1.8 }}>
          أي شخص يمكنه الآن إنشاء حساب من شاشة الدخول، ثم يظهر هنا مباشرة لتحديد الدور وربطه بالمدرب أو المستثمر المناسب.
        </div>
        <div style={{ marginTop: 18, display: "grid", gap: 12 }}>
          {users.map(u => (
            <div key={u.id} style={{ borderTop: "1px solid #f3f4f6", paddingTop: 14 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1.2fr", gap: 12 }}>
                <Input label="الاسم" value={u.name || ""} onChange={e => setUsers(users.map(item => item.id === u.id ? { ...item, name: e.target.value } : item))} />
                <Input label="البريد الإلكتروني" value={u.email || ""} onChange={e => setUsers(users.map(item => item.id === u.id ? { ...item, email: e.target.value } : item))} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <Select label="الدور" value={u.role || "viewer"} onChange={e => setUsers(users.map(item => item.id === u.id ? { ...item, role: e.target.value, dashboard_role: e.target.value } : item))} options={Object.entries(userRoleLabels).map(([value, label]) => ({ value, label }))} />
                <Input label="مرتبط بـ" value={u.linked_to_name || ""} onChange={e => setUsers(users.map(item => item.id === u.id ? { ...item, linked_to_name: e.target.value } : item))} placeholder="اسم المدرب أو المستثمر إن وجد" />
              </div>
              <Select label="العملة المفضلة" value={u.preferred_currency || "AUTO"} onChange={e => setUsers(users.map(item => item.id === u.id ? { ...item, preferred_currency: e.target.value } : item))} options={[{ value: "AUTO", label: "تلقائي / محلي" }, { value: "EGP", label: "جنيه مصري" }, { value: "USD", label: "دولار" }]} />
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: 12, alignItems: "end" }}>
                <Input label="تغيير كلمة المرور (اختياري)" type="password" value={u.password || ""} onChange={e => setUsers(users.map(item => item.id === u.id ? { ...item, password: e.target.value } : item))} />
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#475467", marginBottom: 16 }}>
                  <input type="checkbox" checked={u.is_active !== false} onChange={e => setUsers(users.map(item => item.id === u.id ? { ...item, is_active: e.target.checked } : item))} />
                  نشط
                </label>
                <Btn onClick={() => updateUser({ ...u, dashboard_role: u.role })} color={BRAND.navy} style={{ marginBottom: 16 }}>حفظ</Btn>
              </div>
            </div>
          ))}
        </div>
      </div>
      </div>
    </div>
  );
}

// ============================================================
// LAYOUT & APP
// ============================================================
function PageLoader() {
  return <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 300 }}>
    <div style={{ fontSize: 32, animation: "spin 1s linear infinite" }}>⏳</div>
    <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
  </div>;
}

// Real website registrants (from the platform) + role control + trainer requests.
function PlatformUsersPage() {
  const readOnly = getEffectiveRole(useAuth()) === "employee";  // موظف متابعة: عرض بلا تنفيذ
  const [data, setData] = useState(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState("");

  const loadUsers = () => api.get(`/platform-users${q ? `?search=${encodeURIComponent(q)}` : ""}`).then(r => { if (r && !r.error) setData(r); });
  useEffect(() => { loadUsers(); /* eslint-disable-next-line */ }, [q]);

  const setRole = (u, role) => {
    setBusy(u.id);
    api.post(`/platform-users/${u.id}/role`, { role }).then(r => { setBusy(""); if (r && !r.error) loadUsers(); else alert(r.error || "تعذر تغيير الدور"); });
  };

  const users = (data && data.users) || [];
  const roleLabel = { admin: "مدير", staff: "موظف", investor: "مستثمر", member: "عضو" };
  const planLabel = { free: "مجانية", pro: "احترافية", premium: "بريميوم" };
  const exportCsv = () => {
    const cols = ["الاسم", "الإيميل", "التليفون", "الدور", "الباقة", "حالة المدرب", "تاريخ التسجيل"];
    const rows = users.map(u => [
      u.full_name || "", u.email || "", u.phone || "", roleLabel[u.role] || u.role || "",
      planLabel[u.plan_id] || u.plan_id || "", u.trainer_status || "", (u.created_at || "").slice(0, 10),
    ]);
    const esc = (v) => `"${String(v).replace(/"/g, '""')}"`;
    const csv = "﻿" + [cols, ...rows].map(r => r.map(esc).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = "elprofessor-users.csv"; a.click();
    URL.revokeObjectURL(url);
  };
  const approvedTrainers = users.filter(u => u.trainer_status === "approved").length;
  const investorsCount = users.filter(u => u.role === "investor").length;

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy, marginBottom: 8 }}>المستخدمون</h1>
      <p style={{ color: "#667085", marginBottom: 20 }}>كل المسجّلين على المنصة — تحليلهم، أدوارهم، وأرقام تواصلهم للتسويق والمبيعات. (طلبات المدربين والبرامج اتنقلت لقسم «الدورات».)</p>

      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <KPICard icon="👥" label="إجمالي المسجّلين" value={(data && data.count) || 0} color={BRAND.navy} />
        <KPICard icon="🎓" label="مدربون معتمدون" value={approvedTrainers} color="#2d8659" />
        <KPICard icon="💼" label="مستثمرون" value={investorsCount} color="#8e44ad" />
      </div>

      <div>
          <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
            <input placeholder="ابحث بالاسم أو الإيميل أو التليفون..." value={q} onChange={e => setQ(e.target.value)} style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #e5e7eb", width: 320, maxWidth: "100%" }} />
            <button onClick={exportCsv} disabled={users.length === 0} style={{ padding: "10px 18px", borderRadius: 10, border: "1px solid " + BRAND.navy, background: "#fff", color: BRAND.navy, fontWeight: 800, cursor: users.length ? "pointer" : "not-allowed" }}>⬇️ تصدير CSV ({users.length})</button>
          </div>
          <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {["الاسم", "الإيميل", "التليفون", "الباقة", "التسجيل", "الحالة", "الدور"].map(h => (
                    <th key={h} style={{ padding: 12, fontSize: 13, color: "#667085", textAlign: "right" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                    <td style={{ padding: 12, fontWeight: 700 }}>{u.full_name || "—"}</td>
                    <td style={{ padding: 12, fontSize: 13, color: "#475467" }}>{u.email}</td>
                    <td style={{ padding: 12, fontSize: 13, color: "#475467", direction: "ltr", textAlign: "right" }}>{u.phone || "—"}</td>
                    <td style={{ padding: 12, fontSize: 12 }}>{planLabel[u.plan_id] || u.plan_id || "—"}</td>
                    <td style={{ padding: 12, fontSize: 12, color: "#667085", direction: "ltr", textAlign: "right" }}>{(u.created_at || "").slice(0, 10) || "—"}</td>
                    <td style={{ padding: 12, fontSize: 12 }}>{u.trainer_status === "approved" ? "مدرب معتمد" : (u.trainer_status === "pending" ? "مدرب معلّق" : "—")}</td>
                    <td style={{ padding: 12 }}>
                      {readOnly ? (
                        <span style={{ fontSize: 13, color: "#475467" }}>{roleLabel[u.role] || u.role}</span>
                      ) : (
                        <select disabled={busy === u.id} value={u.role} onChange={e => setRole(u, e.target.value)} style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #e5e7eb", cursor: "pointer" }}>
                          {["member", "investor", "staff", "admin"].map(r => <option key={r} value={r}>{roleLabel[r]}</option>)}
                        </select>
                      )}
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr><td colSpan={7} style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}>لا يوجد مستخدمون بعد (أو الربط قيد التفعيل).</td></tr>
                )}
              </tbody>
            </table>
          </div>
      </div>
    </div>
  );
}

// Admin cockpit for investors: every wallet (balance / invested / returns / level)
// plus the withdrawal queue to approve → mark paid. Uses the existing admin bridges
// (/admin/wallets, /admin/withdrawals). Admin-only (nav-gated + backend roles_required).
function InvestorsAdminPage() {
  const [wallets, setWallets] = useState([]);
  const [withdrawals, setWithdrawals] = useState([]);
  const [busy, setBusy] = useState("");

  const load = () => {
    api.get("/admin/wallets").then(r => setWallets(safeArray(r)));
    api.get("/admin/withdrawals").then(r => setWithdrawals(safeArray(r)));
  };
  useEffect(() => { load(); }, []);

  const decide = (id, status) => {
    setBusy(id);
    api.put(`/admin/withdrawals/${id}`, { status }).then(r => {
      setBusy("");
      if (r && !r.error) load(); else alert(r.error || "تعذر تحديث طلب السحب");
    });
  };

  const totalBalanceEgp = wallets.reduce((s, w) => s + (w.balance_egp || 0), 0);
  const totalInvestedEgp = wallets.reduce((s, w) => s + (w.total_invested_egp || 0), 0);
  const totalReturnsEgp = wallets.reduce((s, w) => s + (w.total_returns_egp || 0), 0);
  const pending = withdrawals.filter(w => w.status === "pending");
  const levelLabel = { bronze: "برونزي", silver: "فضي", gold: "ذهبي", platinum: "بلاتيني" };
  const wStatus = { pending: { t: "معلّق", c: "#e8913a" }, approved: { t: "معتمد (بانتظار الصرف)", c: "#2563eb" }, completed: { t: "تم الصرف", c: "#2d8659" }, rejected: { t: "مرفوض", c: "#9ca3af" } };

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy, marginBottom: 8 }}>المستثمرون والمحافظ</h1>
      <p style={{ color: "#667085", marginBottom: 20 }}>كل محافظ المستثمرين وأرصدتهم وعوائدهم، وطلبات السحب — تُعتمد وتُصرف من هنا.</p>

      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <KPICard icon="💼" label="عدد المستثمرين" value={wallets.length} color={BRAND.navy} />
        <KPICard icon="💰" label="إجمالي الأرصدة" value={egpLabel(totalBalanceEgp)} color="#2d8659" />
        <KPICard icon="📥" label="إجمالي المستثمَر" value={egpLabel(totalInvestedEgp)} color="#5b6abf" />
        <KPICard icon="📈" label="إجمالي العوائد" value={egpLabel(totalReturnsEgp)} color="#d4a017" />
        <KPICard icon="⏳" label="طلبات سحب معلّقة" value={pending.length} color={pending.length ? "#c0392b" : "#9ca3af"} />
      </div>

      <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", padding: 18, marginBottom: 24 }}>
        <h3 style={{ fontSize: 16, fontWeight: 900, color: BRAND.navy, marginBottom: 14 }}>طلبات السحب</h3>
        {withdrawals.length === 0 && <div style={{ padding: 18, textAlign: "center", color: "#9ca3af" }}>لا توجد طلبات سحب.</div>}
        <div style={{ display: "grid", gap: 10 }}>
          {withdrawals.map(w => {
            const st = wStatus[w.status] || { t: w.status, c: "#9ca3af" };
            return (
              <div key={w.id} className="withdraw-bar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", border: "1px solid #eef2f6", borderRadius: 10, padding: "12px 14px", background: w.status === "pending" ? "#fffdf7" : "#fff" }}>
                <div style={{ minWidth: 180 }}>
                  <div style={{ fontWeight: 900, color: BRAND.navy }}>{w.investor_name || "—"}</div>
                  <div style={{ fontSize: 12, color: "#667085", direction: "ltr", textAlign: "right" }}>{(w.requested_at || "").slice(0, 10)}</div>
                </div>
                <div style={{ fontWeight: 900, color: "#1f2937" }}>{egpLabel(w.amount_egp)} <span style={{ fontSize: 12, color: "#9ca3af", fontWeight: 700 }}>({fmtUSD(w.amount)})</span></div>
                <span style={{ background: st.c, color: "#fff", borderRadius: 999, padding: "3px 12px", fontSize: 12, fontWeight: 800 }}>{st.t}</span>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {w.status === "pending" && <>
                    <button disabled={busy === w.id} onClick={() => decide(w.id, "approved")} style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: "#2563eb", color: "#fff", fontWeight: 800, cursor: "pointer" }}>اعتماد</button>
                    <button disabled={busy === w.id} onClick={() => decide(w.id, "rejected")} style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid #dc2626", background: "#fff", color: "#dc2626", fontWeight: 800, cursor: "pointer" }}>رفض</button>
                  </>}
                  {w.status === "approved" && <button disabled={busy === w.id} onClick={() => decide(w.id, "completed")} style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: "#2d8659", color: "#fff", fontWeight: 800, cursor: "pointer" }}>✓ تم الصرف</button>}
                  {(w.status === "completed" || w.status === "rejected") && w.processed_at && <span style={{ fontSize: 12, color: "#9ca3af", direction: "ltr" }}>{(w.processed_at || "").slice(0, 10)}</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 820 }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              {["المستثمر", "الرصيد", "إجمالي المستثمَر", "إجمالي العوائد", "متوسط العائد", "المستوى", "طلبات معلّقة"].map(h => (
                <th key={h} style={{ padding: 12, fontSize: 13, color: "#667085", textAlign: "right" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {wallets.map(w => (
              <tr key={w.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                <td style={{ padding: 12, fontWeight: 800, color: BRAND.navy }}>{w.investor_name}</td>
                <td style={{ padding: 12, fontWeight: 700, color: "#2d8659" }}>{egpLabel(w.balance_egp)}</td>
                <td style={{ padding: 12, fontSize: 13 }}>{egpLabel(w.total_invested_egp)}</td>
                <td style={{ padding: 12, fontSize: 13, color: "#d4a017", fontWeight: 700 }}>{egpLabel(w.total_returns_egp)}</td>
                <td style={{ padding: 12, fontSize: 13 }}>{w.avg_roi || 0}%</td>
                <td style={{ padding: 12, fontSize: 12 }}>{levelLabel[w.level] || w.level}</td>
                <td style={{ padding: 12, fontSize: 13, color: w.pending_requests ? "#c0392b" : "#9ca3af", fontWeight: w.pending_requests ? 800 : 400 }}>{w.pending_requests || 0}</td>
              </tr>
            ))}
            {wallets.length === 0 && (
              <tr><td colSpan={7} style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}>لا توجد محافظ مستثمرين بعد.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// قسم «الاستثمار» الموحّد: المحافظ والسحب (InvestorsAdminPage) + الاستثمارات
// الإعلانية وحاسبة التوزيع (المنقولة من التسويق). كله في مكان واحد.
function InvestmentPage() {
  const [tab, setTab] = useState("investors");
  return (
    <div>
      <div style={{ marginBottom: 18 }}>
        <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy, marginBottom: 6 }}>الاستثمار</h1>
        <div style={{ fontSize: 13, color: "#667085", marginBottom: 14 }}>المستثمرون ومحافظهم وطلبات السحب، بالإضافة لفرص الاستثمار الإعلاني المرتبطة بالدورات.</div>
        <TabBar tabs={[{ id: "investors", label: "المستثمرون والمحافظ" }, { id: "ads", label: "الاستثمارات الإعلانية" }]} active={tab} onChange={setTab} />
      </div>
      {tab === "investors" && <InvestorsAdminPage />}
      {tab === "ads" && <MarketingPage only="investors" />}
    </div>
  );
}

// ============================================================
// CONTENT / BLOG (CMS) — admin-only
// Article = {id,title,excerpt,cat,kicker,date,by,tone?,video?,body:[str],status,published_at}
// ============================================================
const emptyArticleForm = () => ({
  title: "", excerpt: "", cat: "", kicker: "", by: "", tone: "", video: "", bodyText: "",
});
// body is stored as string[] (paragraphs split on blank lines); the form edits a single textarea.
const bodyToText = (body) => safeArray(body).join("\n\n");
const textToBody = (text) => String(text || "").split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);

function ContentPage() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState(emptyArticleForm());
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api.get("/content/articles/all").then(r => {
      if (r && r.error) { setErr(r.error); setArticles([]); }
      else { setErr(""); setArticles(safeArray(r?.articles ?? r)); }
      setLoading(false);
    }).catch(() => { setErr("تعذر تحميل المقالات"); setLoading(false); });
  }, []);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setForm(emptyArticleForm()); setModal(true); };
  const openEdit = (a) => {
    setForm({
      id: a.id, title: a.title || "", excerpt: a.excerpt || "", cat: a.cat || "",
      kicker: a.kicker || "", by: a.by || "", tone: a.tone || "", video: a.video || "",
      bodyText: bodyToText(a.body),
    });
    setModal(true);
  };

  const save = async () => {
    if (!form.title.trim()) { alert("العنوان مطلوب"); return; }
    setBusy(true);
    const payload = {
      title: form.title, excerpt: form.excerpt, cat: form.cat, kicker: form.kicker,
      by: form.by, tone: form.tone, video: form.video, body: textToBody(form.bodyText),
    };
    const r = form.id ? await api.put(`/content/articles/${form.id}`, payload) : await api.post("/content/articles", payload);
    setBusy(false);
    if (r && r.error) { alert(r.error); return; }
    setModal(false); setForm(emptyArticleForm()); load();
  };

  const publish = async (a) => {
    const r = await api.post(`/content/articles/${a.id}/publish`, {});
    if (r && r.error) { alert(r.error); return; }
    load();
  };
  const remove = async (a) => {
    if (!confirm(`حذف المقال «${a.title || ""}»؟`)) return;
    const r = await api.del(`/content/articles/${a.id}`);
    if (r && r.error) { alert(r.error); return; }
    load();
  };

  const drafts = articles.filter(a => a.status !== "published");
  const published = articles.filter(a => a.status === "published");

  if (loading) return <PageLoader />;
  if (err) return <PageError message={err} onRetry={load} />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 8 }}>
        <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy }}>المحتوى والمدونة</h1>
        <Btn onClick={openNew} color={BRAND.gold}>+ مقال جديد</Btn>
      </div>
      <p style={{ color: "#667085", marginBottom: 20 }}>اكتب وحرّر مقالات المدونة، ثم انشرها لتظهر على elprofessor.net. المسودّات لا تظهر للزوّار حتى تنشرها.</p>

      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <KPICard icon="📝" label="مسودّات" value={drafts.length} color="#e8913a" />
        <KPICard icon="✅" label="منشورة" value={published.length} color="#2d8659" />
        <KPICard icon="📰" label="إجمالي المقالات" value={articles.length} color={BRAND.navy} />
      </div>

      <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 720 }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              {["العنوان", "التصنيف", "الكاتب", "الحالة", "التاريخ", "إجراءات"].map(h => (
                <th key={h} style={{ padding: 12, fontSize: 13, color: "#667085", textAlign: "right" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {articles.map(a => (
              <tr key={a.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                <td style={{ padding: 12, fontWeight: 700, maxWidth: 320 }}>
                  {a.title || "—"}
                  {a.excerpt && <div style={{ fontSize: 12, color: "#9ca3af", fontWeight: 400, marginTop: 2 }}>{a.excerpt}</div>}
                </td>
                <td style={{ padding: 12, fontSize: 13, color: "#475467" }}>{a.cat || "—"}</td>
                <td style={{ padding: 12, fontSize: 13, color: "#475467" }}>{a.by || "—"}</td>
                <td style={{ padding: 12 }}>
                  {a.status === "published"
                    ? <Badge text="منشور" color="#2d8659" />
                    : <Badge text="مسودة" color="#e8913a" />}
                </td>
                <td style={{ padding: 12, fontSize: 12, color: "#667085", direction: "ltr", textAlign: "right" }}>{(a.published_at || a.date || "").slice(0, 10) || "—"}</td>
                <td style={{ padding: 12 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <button title="تعديل" onClick={() => openEdit(a)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16 }}>✏️</button>
                    {a.status !== "published" && (
                      <button title="نشر" onClick={() => publish(a)} style={{ background: "none", border: "1px solid #2d8659", color: "#2d8659", borderRadius: 8, padding: "4px 10px", cursor: "pointer", fontSize: 12, fontWeight: 800 }}>نشر</button>
                    )}
                    <button title="حذف" onClick={() => remove(a)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16 }}>🗑</button>
                  </div>
                </td>
              </tr>
            ))}
            {articles.length === 0 && (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}>لا توجد مقالات بعد. ابدأ بإضافة أول مقال.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Modal open={modal} onClose={() => setModal(false)} title={form.id ? "تعديل مقال" : "مقال جديد"} maxWidth={680}>
        <Input label="العنوان" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
        <Input label="مقتطف (Excerpt)" value={form.excerpt} onChange={e => setForm({ ...form, excerpt: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="التصنيف (cat)" value={form.cat} onChange={e => setForm({ ...form, cat: e.target.value })} />
          <Input label="العنوان الفرعي (kicker)" value={form.kicker} onChange={e => setForm({ ...form, kicker: e.target.value })} />
          <Input label="الكاتب (by)" value={form.by} onChange={e => setForm({ ...form, by: e.target.value })} />
          <Input label="النبرة (tone) — اختياري" value={form.tone} onChange={e => setForm({ ...form, tone: e.target.value })} />
        </div>
        <Input label="رابط فيديو (video) — اختياري" value={form.video} onChange={e => setForm({ ...form, video: e.target.value })} style={{ direction: "ltr", textAlign: "left" }} />
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 6 }}>نص المقال — افصل بين الفقرات بسطر فارغ</label>
          <textarea value={form.bodyText} onChange={e => setForm({ ...form, bodyText: e.target.value })} rows={10} style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14, boxSizing: "border-box", fontFamily: "inherit", lineHeight: 1.8, resize: "vertical" }} />
        </div>
        <div style={{ display: "flex", gap: 12, justifyContent: "flex-start" }}>
          <Btn onClick={save} color={BRAND.navy} disabled={busy}>{busy ? "جارٍ الحفظ..." : (form.id ? "حفظ التعديلات" : "حفظ كمسودة")}</Btn>
          <Btn onClick={() => setModal(false)} color="#9ca3af" variant="outline">إلغاء</Btn>
        </div>
      </Modal>
    </div>
  );
}

// ============================================================
// MESSAGES (contact form inbox) — admin-only
// Message = {id,name,email,phone?,topic?,body,status:'new'|'replied',created_at}
// ============================================================
function MessagesPage() {
  const [status, setStatus] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [selected, setSelected] = useState(null);
  const [replyText, setReplyText] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const q = status ? `?status=${status}` : "";
    api.get(`/messages${q}`).then(r => {
      if (r && r.error) { setErr(r.error); setMessages([]); }
      else { setErr(""); setMessages(safeArray(r?.messages ?? r)); }
      setLoading(false);
    }).catch(() => { setErr("تعذر تحميل الرسائل"); setLoading(false); });
  }, [status]);
  useEffect(() => { load(); }, [load]);

  const newCount = messages.filter(m => m.status === "new").length;

  const open = (m) => { setSelected(m); setReplyText(""); };
  const sendReply = async () => {
    if (!replyText.trim()) { alert("اكتب نص الرد"); return; }
    setBusy(true);
    const r = await api.post(`/messages/${selected.id}/reply`, { body: replyText });
    setBusy(false);
    if (r && r.error) { alert(r.error); return; }
    setSelected(null); setReplyText(""); load();
  };
  const remove = async (m) => {
    if (!confirm(`حذف رسالة «${m.name || ""}»؟`)) return;
    const r = await api.del(`/messages/${m.id}`);
    if (r && r.error) { alert(r.error); return; }
    if (selected && selected.id === m.id) setSelected(null);
    load();
  };

  if (loading) return <PageLoader />;
  if (err) return <PageError message={err} onRetry={load} />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 8 }}>
        <h1 style={{ fontSize: 24, fontWeight: 900, color: BRAND.navy }}>الرسائل</h1>
        {newCount > 0 && <Badge text={`${newCount} جديدة`} color="#c0392b" />}
      </div>
      <p style={{ color: "#667085", marginBottom: 20 }}>رسائل نموذج التواصل القادمة من elprofessor.net — اقرأها، ردّ عليها، أو احذفها.</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {[{ id: "", label: "الكل" }, { id: "new", label: "جديدة" }, { id: "replied", label: "تم الرد" }].map(t => (
          <button key={t.id} onClick={() => setStatus(t.id)} style={{ padding: "8px 16px", borderRadius: 20, border: status === t.id ? `2px solid ${BRAND.navy}` : "1px solid #e5e7eb", background: status === t.id ? BRAND.navy : "#fff", color: status === t.id ? "#fff" : "#475467", fontWeight: 700, cursor: "pointer", fontSize: 13 }}>{t.label}</button>
        ))}
      </div>

      <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 720 }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              {["الاسم", "الإيميل", "الموضوع", "الحالة", "التاريخ", "إجراءات"].map(h => (
                <th key={h} style={{ padding: 12, fontSize: 13, color: "#667085", textAlign: "right" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {messages.map(m => (
              <tr key={m.id} style={{ borderTop: "1px solid #f1f5f9", background: m.status === "new" ? "#fffaf3" : "#fff" }}>
                <td style={{ padding: 12, fontWeight: 700 }}>{m.name || "—"}</td>
                <td style={{ padding: 12, fontSize: 13, color: "#475467", direction: "ltr", textAlign: "right" }}>{m.email}</td>
                <td style={{ padding: 12, fontSize: 13, color: "#475467" }}>{m.topic || "—"}</td>
                <td style={{ padding: 12 }}>
                  {m.status === "replied" ? <Badge text="تم الرد" color="#2d8659" /> : <Badge text="جديدة" color="#c0392b" />}
                </td>
                <td style={{ padding: 12, fontSize: 12, color: "#667085", direction: "ltr", textAlign: "right" }}>{(m.created_at || "").slice(0, 16).replace("T", " ") || "—"}</td>
                <td style={{ padding: 12 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <button title="عرض / رد" onClick={() => open(m)} style={{ background: "none", border: "1px solid " + BRAND.navy, color: BRAND.navy, borderRadius: 8, padding: "4px 10px", cursor: "pointer", fontSize: 12, fontWeight: 800 }}>عرض</button>
                    <button title="حذف" onClick={() => remove(m)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16 }}>🗑</button>
                  </div>
                </td>
              </tr>
            ))}
            {messages.length === 0 && (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}>لا توجد رسائل في هذا التصنيف.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Modal open={!!selected} onClose={() => setSelected(null)} title="رسالة تواصل" maxWidth={620}>
        {selected && (
          <div>
            <div style={{ background: "#f8fafc", borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
                <div><div style={{ fontSize: 12, color: "#9ca3af" }}>الاسم</div><div style={{ fontWeight: 700 }}>{selected.name || "—"}</div></div>
                <div><div style={{ fontSize: 12, color: "#9ca3af" }}>الإيميل</div><div style={{ fontWeight: 700, direction: "ltr", textAlign: "right" }}>{selected.email || "—"}</div></div>
                <div><div style={{ fontSize: 12, color: "#9ca3af" }}>التليفون</div><div style={{ fontWeight: 700, direction: "ltr", textAlign: "right" }}>{selected.phone || "—"}</div></div>
                <div><div style={{ fontSize: 12, color: "#9ca3af" }}>الموضوع</div><div style={{ fontWeight: 700 }}>{selected.topic || "—"}</div></div>
              </div>
              <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>الرسالة</div>
              <div style={{ fontSize: 14, lineHeight: 1.9, color: BRAND.ink, whiteSpace: "pre-wrap" }}>{selected.body || "—"}</div>
            </div>
            {selected.status === "replied" ? (
              <div style={{ padding: "10px 14px", borderRadius: 8, background: "#ecfdf3", color: "#2d8659", fontWeight: 700, fontSize: 13, marginBottom: 12 }}>✅ تم الرد على هذه الرسالة.</div>
            ) : (
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 6 }}>نص الرد</label>
                <textarea value={replyText} onChange={e => setReplyText(e.target.value)} rows={5} style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14, boxSizing: "border-box", fontFamily: "inherit", lineHeight: 1.8, resize: "vertical" }} />
              </div>
            )}
            <div style={{ display: "flex", gap: 12 }}>
              {selected.status !== "replied" && <Btn onClick={sendReply} color={BRAND.navy} disabled={busy}>{busy ? "جارٍ الإرسال..." : "إرسال الرد"}</Btn>}
              <Btn onClick={() => remove(selected)} color="#c0392b" variant="outline">حذف الرسالة</Btn>
              <Btn onClick={() => setSelected(null)} color="#9ca3af" variant="outline">إغلاق</Btn>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

const navItems = [
  { id: "overview", label: "نظرة عامة", icon: "📊" },
  { id: "platform-users", label: "المستخدمون", icon: "👥" },
  { id: "courses", label: "الدورات والتدريب", icon: "📚" },
  { id: "investors-admin", label: "الاستثمار", icon: "💼" },
  { id: "marketing", label: "التسويق", icon: "📢" },
  { id: "content", label: "المحتوى والمدونة", icon: "📝" },
  { id: "messages", label: "الرسائل", icon: "✉️" },
  { id: "finance", label: "المالية", icon: "💰" },
  { id: "partners", label: "الشركاء", icon: "🤝" },
  { id: "team", label: "الفريق والمدربون", icon: "🧑‍🏫" },
  { id: "foundation", label: "مرحلة التأسيس", icon: "🏗️" },
  { id: "targets", label: "الأهداف والتوقعات", icon: "📈" },
  { id: "ai", label: "مساعد AI", icon: "🤖" },
  { id: "settings", label: "الإعدادات", icon: "⚙️" },
];

function Layout({ page, setPage, user, onLogout }) {
  const effectiveRole = getEffectiveRole(user);
  const isMobile = useIsMobile(980);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const visibleNavItems = effectiveRole === "trainer"
    ? [
        { id: "overview", label: "لوحتي", icon: "📊" },
        { id: "courses", label: "دوراتي", icon: "🎓" },
        { id: "earnings", label: "أرباحي واستثماري", icon: "💰" },
        { id: "ai", label: "مساعد AI", icon: "🤖" },
      ]
    : effectiveRole === "investor"
      ? [
          { id: "overview", label: "لوحتي", icon: "📊" },
          { id: "marketplace", label: "ماركت الاستثمار", icon: "💵" },
          { id: "investments", label: "استثماراتي", icon: "📋" },
          { id: "ai", label: "مساعد AI", icon: "🤖" },
        ]
      : effectiveRole === "employee"
        ? [
            // موظف عمليات: الناس + الطلبات + الدورات (رفع/تعديل + فلوس كل دورة) + التسويق.
            // بلا التأسيس/الشركاء/الاستثمار/الإعدادات ولا الإجماليات المالية الكلية.
            { id: "platform-users", label: "المستخدمون", icon: "👥" },
            { id: "courses", label: "الدورات والتدريب", icon: "📚" },
            { id: "marketing", label: "التسويق", icon: "📢" },
          ]
      : effectiveRole === "viewer"
        ? [
            { id: "overview", label: "بانتظار التفعيل", icon: "⏳" },
          ]
      : navItems.filter((item) => {
          // المحتوى والمدونة + الرسائل: للأدمن فقط.
          if (effectiveRole !== "admin" && (item.id === "content" || item.id === "messages")) return false;
          if (effectiveRole === "training_supervisor" && item.id === "settings") return false;
          if (effectiveRole === "training_supervisor" && item.id === "foundation") return false;
          // الاستثمار والشركاء شأن مالي/ملكية — للأدمن فقط، تُخفى عن المشرف التدريبي.
          if (effectiveRole === "training_supervisor" && item.id === "investors-admin") return false;
          if (effectiveRole === "training_supervisor" && item.id === "partners") return false;
          return true;
        });

  // Never render a page outside the current role's allowed tabs (defends against a
  // stale `page` state or a deep link — e.g. an employee can't land on "overview").
  const allowedIds = visibleNavItems.map((n) => n.id);
  const activePage = allowedIds.includes(page) ? page : (visibleNavItems[0]?.id || "overview");

  const sidebar = (
    <div style={{ width: isMobile ? "82vw" : 250, maxWidth: 300, background: `linear-gradient(180deg, ${BRAND.navy2}, ${BRAND.navy})`, padding: "24px 0", display: "flex", flexDirection: "column", flexShrink: 0, height: "100%" }}>
      <div style={{ padding: "0 24px", marginBottom: 36 }}>
        <div style={{ fontSize: 24, fontWeight: 900, color: BRAND.gold }}>البروفيسور</div>
        <div style={{ fontSize: 11, color: "#B8C0D0", letterSpacing: 1, marginTop: 2 }}>MANAGEMENT DASHBOARD</div>
      </div>
      <nav style={{ flex: 1 }}>
        {visibleNavItems.map(n => (
          <button key={n.id} onClick={() => { setPage(n.id); setSidebarOpen(false); }} style={{ display: "flex", alignItems: "center", gap: 12, width: "100%", padding: "14px 24px", background: activePage === n.id ? "rgba(217,179,76,0.14)" : "transparent", border: "none", borderRight: activePage === n.id ? `3px solid ${BRAND.gold}` : "3px solid transparent", color: activePage === n.id ? "#fff" : "#B8C0D0", fontSize: 15, fontWeight: activePage === n.id ? 900 : 700, cursor: "pointer", textAlign: "right", transition: "all 0.15s" }}>
            <span style={{ fontSize: 18 }}>{n.icon}</span>
            {n.label}
          </button>
        ))}
      </nav>
      <div style={{ padding: "16px 24px", borderTop: "1px solid rgba(255,255,255,0.1)" }}>
        <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 8 }}>👤 {user?.name}</div>
        <div style={{ fontSize: 12, color: "#D9B34C", marginBottom: 8 }}>{userRoleLabels[user?.role] || user?.role}</div>
        <button onClick={onLogout} style={{ background: "none", border: "none", color: "#ef4444", fontSize: 13, cursor: "pointer", fontWeight: 600 }}>تسجيل الخروج</button>
      </div>
    </div>
  );

  return (
    <div style={{ display: "flex", minHeight: "100vh", direction: "rtl", fontFamily: "'IBM Plex Sans Arabic', 'Cairo', 'Tajawal', sans-serif" }}>
      <style>{`
        @media (max-width: 980px) {
          .wallet-stats { grid-template-columns: 1fr !important; }
          .card-meta { grid-template-columns: 1fr !important; }
          .withdraw-bar { flex-direction: column !important; align-items: stretch !important; }
        }
      `}</style>
      {!isMobile && sidebar}
      {isMobile && sidebarOpen && (
        <div onClick={() => setSidebarOpen(false)} style={{ position: "fixed", inset: 0, background: "rgba(16,27,47,.45)", zIndex: 1000 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ height: "100%", boxShadow: "0 24px 70px rgba(16,27,47,.28)" }}>
            {sidebar}
          </div>
        </div>
      )}

      {/* Main Content */}
      <div style={{ flex: 1, background: BRAND.bg, padding: isMobile ? "16px 14px 96px" : "28px 32px 96px", overflowY: "auto" }}>
        {isMobile && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, background: "#fff", borderRadius: 16, padding: "12px 14px", border: "1px solid #e6ecf2" }}>
            <button onClick={() => setSidebarOpen(true)} style={{ minWidth: 44, minHeight: 44, borderRadius: 12, border: "1px solid #d0d5dd", background: "#fff", fontSize: 20, cursor: "pointer" }}>☰</button>
            <div style={{ textAlign: "left" }}>
              <div style={{ fontWeight: 900, color: BRAND.navy }}>البروفيسور</div>
              <div style={{ fontSize: 12, color: "#667085" }}>{userRoleLabels[user?.role] || user?.role}</div>
            </div>
          </div>
        )}
        <PageBoundary pageKey={activePage}>
          {activePage === "overview" && <OverviewPage onNavigate={setPage} />}
          {activePage === "platform-users" && <PlatformUsersPage />}
          {activePage === "finance" && <FinancePage />}
          {activePage === "marketing" && <MarketingPage only="campaigns" />}
          {activePage === "content" && <ContentPage />}
          {activePage === "messages" && <MessagesPage />}
          {activePage === "courses" && <CoursesPage />}
          {activePage === "investors-admin" && <InvestmentPage />}
          {activePage === "earnings" && <MyEarningsPage />}
          {activePage === "marketplace" && <InvestorInvestmentsPage initialTab="opportunities" />}
          {activePage === "investments" && <InvestorInvestmentsPage initialTab="active" />}
          {activePage === "foundation" && <FoundationPage />}
          {activePage === "partners" && <TeamPartnersPage section="partners" />}
          {activePage === "team" && <TeamPartnersPage section="team" />}
          {activePage === "targets" && <TargetsPage />}
          {activePage === "ai" && <AIPage />}
          {activePage === "settings" && <SettingsPage />}
        </PageBoundary>
        <AIAssistantDock />
      </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState("overview");
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    // Single sign-on from the main platform: it redirects here with ?sso=<token>.
    const params = new URLSearchParams(window.location.search);
    const ssoToken = params.get("sso");
    if (ssoToken) {
      api.post("/auth/sso", { sso: ssoToken }).then(r => {
        if (r.token) {
          api.token = r.token;
          localStorage.setItem("token", r.token);
          setUser(r.user);
        }
        // Strip the token from the URL so it isn't re-used or bookmarked.
        params.delete("sso");
        const qs = params.toString();
        window.history.replaceState({}, "", window.location.pathname + (qs ? `?${qs}` : ""));
        setChecking(false);
      }).catch(() => setChecking(false));
      return;
    }
    const t = localStorage.getItem("token");
    if (t) {
      api.token = t;
      api.get("/auth/me").then(u => {
        if (u.id) setUser(u);
        setChecking(false);
      }).catch(() => setChecking(false));
    } else {
      setChecking(false);
    }
  }, []);

  const logout = () => {
    api.token = null;
    localStorage.removeItem("token");
    setUser(null);
  };

  if (checking) return <PageLoader />;
  if (!user) return <LoginPage onLogin={setUser} />;
  return (
    <AuthCtx.Provider value={user}>
      <Layout page={page} setPage={setPage} user={user} onLogout={logout} />
    </AuthCtx.Provider>
  );
}
