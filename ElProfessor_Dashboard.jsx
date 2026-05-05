import { useState, useEffect, useCallback, createContext, useContext } from "react";
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

// ============================================================
// CONFIG & API
// ============================================================
const API = "http://127.0.0.1:5000/api";
const COLORS = ["#0f4c81","#e8913a","#2d8659","#c0392b","#8e44ad","#1abc9c","#d4a017","#5b6abf"];

const api = {
  token: null,
  async req(path, opts = {}) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const r = await fetch(`${API}${path}`, { ...opts, headers });
    if (r.status === 401) { this.token = null; localStorage.removeItem("token"); window.location.reload(); }
    return r.json();
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
const catLabels = { tools: "أدوات وبرمجيات", hosting: "استضافة", marketing: "تسويق", travel: "سفر عمل", legal: "قانوني", office: "مكتب", bank_fees: "رسوم بنكية", other: "أخرى" };
const srcLabels = { course: "دورة تدريبية", consulting: "استشارة", subscription: "اشتراك", other: "أخرى" };
const platLabels = { google_ads: "Google Ads", facebook: "Facebook", instagram: "Instagram", linkedin: "LinkedIn", tiktok: "TikTok", other: "أخرى" };
const statusLabels = { draft: "مسودة", active: "نشطة", paused: "متوقفة", completed: "منتهية" };
const recLabels = { continue: "✅ استمر", optimize: "🔧 حسّن", stop: "🛑 أوقف", monitor: "👁 راقب" };
const recColors = { continue: "#2d8659", optimize: "#e8913a", stop: "#c0392b", monitor: "#5b6abf" };

// ============================================================
// COMPONENTS
// ============================================================

function KPICard({ label, value, sub, color = "#0f4c81", icon }) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, padding: "20px 24px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)", borderRight: `4px solid ${color}`, minWidth: 0 }}>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 6 }}>{icon} {label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color, lineHeight: 1.2 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function Modal({ open, onClose, title, children }) {
  if (!open) return null;
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div style={{ background: "#fff", borderRadius: 16, padding: 32, maxWidth: 560, width: "90%", maxHeight: "85vh", overflow: "auto", boxShadow: "0 20px 60px rgba(0,0,0,0.15)" }} onClick={e => e.stopPropagation()}>
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
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 6 }}>{label}</label>
      <input {...props} style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14, boxSizing: "border-box", ...props.style }} />
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

function Btn({ children, color = "#0f4c81", variant = "primary", ...props }) {
  const bg = variant === "primary" ? color : "transparent";
  const fg = variant === "primary" ? "#fff" : color;
  const border = variant === "primary" ? "none" : `2px solid ${color}`;
  return <button {...props} style={{ padding: "10px 24px", borderRadius: 8, background: bg, color: fg, border, fontSize: 14, fontWeight: 600, cursor: "pointer", ...props.style }}>{children}</button>;
}

function Badge({ text, color = "#0f4c81" }) {
  return <span style={{ display: "inline-block", padding: "3px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600, background: `${color}18`, color }}>{text}</span>;
}

function TabBar({ tabs, active, onChange }) {
  return (
    <div style={{ display: "flex", gap: 0, borderBottom: "2px solid #e5e7eb", marginBottom: 24 }}>
      {tabs.map(t => (
        <button key={t.id} onClick={() => onChange(t.id)} style={{ padding: "12px 24px", background: "none", border: "none", borderBottom: active === t.id ? "3px solid #0f4c81" : "3px solid transparent", color: active === t.id ? "#0f4c81" : "#6b7280", fontWeight: active === t.id ? 700 : 500, fontSize: 15, cursor: "pointer", marginBottom: -2 }}>{t.label}</button>
      ))}
    </div>
  );
}

// ============================================================
// LOGIN PAGE
// ============================================================
function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("admin@elprofessor.com");
  const [pass, setPass] = useState("admin123");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true); setErr("");
    try {
      const r = await api.post("/auth/login", { email, password: pass });
      if (r.error) { setErr(r.error); setLoading(false); return; }
      api.token = r.token;
      localStorage.setItem("token", r.token);
      onLogin(r.user);
    } catch (e) { setErr("خطأ في الاتصال بالسيرفر"); }
    setLoading(false);
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(135deg, #0a1628 0%, #1a365d 50%, #0f4c81 100%)" }}>
      <div style={{ background: "#fff", borderRadius: 20, padding: "48px 40px", width: 380, boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div style={{ fontSize: 36, fontWeight: 800, color: "#0f4c81", marginBottom: 4 }}>البروفيسور</div>
          <div style={{ fontSize: 14, color: "#6b7280", letterSpacing: 2 }}>MANAGEMENT DASHBOARD</div>
        </div>
        <Input label="البريد الإلكتروني" value={email} onChange={e => setEmail(e.target.value)} type="email" />
        <Input label="كلمة المرور" value={pass} onChange={e => setPass(e.target.value)} type="password" onKeyDown={e => e.key === "Enter" && submit()} />
        {err && <div style={{ color: "#c0392b", fontSize: 13, marginBottom: 12 }}>{err}</div>}
        <Btn onClick={submit} style={{ width: "100%", marginTop: 8, padding: 14, fontSize: 16 }} disabled={loading}>
          {loading ? "جاري الدخول..." : "تسجيل الدخول"}
        </Btn>
      </div>
    </div>
  );
}

// ============================================================
// EXECUTIVE OVERVIEW
// ============================================================
function OverviewPage() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/dashboard").then(setData); }, []);
  if (!data) return <PageLoader />;

  const { financial: f, marketing: m, courses: c, monthly, alerts, recent } = data;

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f4c81", marginBottom: 24 }}>نظرة عامة تنفيذية</h1>
      
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 28 }}>
        <KPICard icon="💰" label="إجمالي الإيرادات" value={`${fmt(f.total_revenue)} ج.م`} color="#2d8659" />
        <KPICard icon="📤" label="إجمالي المصروفات" value={`${fmt(f.total_expenses)} ج.م`} color="#c0392b" />
        <KPICard icon="📊" label="صافي الربح" value={`${fmt(f.net_profit)} ج.م`} color={f.net_profit >= 0 ? "#2d8659" : "#c0392b"} />
        <KPICard icon="🏦" label="الرصيد الحالي" value={`${fmt(f.current_balance)} ج.م`} sub={`رصيد افتتاحي: ${fmt(f.opening_balance)}`} color="#0f4c81" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 28 }}>
        <KPICard icon="📢" label="الإنفاق التسويقي" value={fmtUSD(m.total_ad_spend)} sub={`${m.total_leads} عميل محتمل`} color="#e8913a" />
        <KPICard icon="👥" label="العملاء" value={m.total_conversions} sub={`CPL: ${fmtUSD(m.cpl)}`} color="#5b6abf" />
        <KPICard icon="📚" label="الدورات" value={c.total_courses} sub={`${c.total_students} طالب`} color="#1abc9c" />
        <KPICard icon="⭐" label="أفضل دورة" value={c.best_course?.title || "—"} sub={c.best_course ? `ربح: ${fmt(c.best_course.profit)} ج.م` : ""} color="#d4a017" />
      </div>

      {alerts.length > 0 && (
        <div style={{ background: "#fef3c7", borderRadius: 12, padding: 16, marginBottom: 24, border: "1px solid #f59e0b" }}>
          <div style={{ fontWeight: 700, color: "#92400e", marginBottom: 8 }}>⚠️ تنبيهات</div>
          {alerts.map((a, i) => <div key={i} style={{ fontSize: 14, color: "#92400e", marginBottom: 4 }}>• {a.message}</div>)}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: "#374151", marginBottom: 16 }}>الإيرادات والمصروفات الشهرية</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={monthly}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
              <Tooltip formatter={(v) => `${fmt(v)} ج.م`} />
              <Legend />
              <Bar dataKey="revenue" name="إيرادات" fill="#2d8659" radius={[4,4,0,0]} />
              <Bar dataKey="expenses" name="مصروفات" fill="#e8913a" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: "#374151", marginBottom: 16 }}>آخر العمليات</h3>
          {recent.map((t, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: i < recent.length - 1 ? "1px solid #f3f4f6" : "none" }}>
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
function FinancePage() {
  const [tab, setTab] = useState("revenues");
  const [revenues, setRevenues] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [summary, setSummary] = useState(null);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});

  const load = useCallback(() => {
    api.get("/revenues").then(setRevenues);
    api.get("/expenses").then(setExpenses);
    api.get("/finance/summary").then(setSummary);
  }, []);
  useEffect(load, [load]);

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
  const deleteItem = async (type, id) => {
    if (!confirm("هل تريد الحذف؟")) return;
    await api.del(`/${type}/${id}`); load();
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f4c81" }}>المالية</h1>
        <div style={{ display: "flex", gap: 10 }}>
          <Btn onClick={() => { setForm({ date: new Date().toISOString().split("T")[0], source: "course", amount_egp: 0, amount_usd: 0 }); setModal("revenue"); }} color="#2d8659">+ إيراد جديد</Btn>
          <Btn onClick={() => { setForm({ date: new Date().toISOString().split("T")[0], category: "tools", amount_egp: 0, amount_usd: 0, is_business: true }); setModal("expense"); }} color="#c0392b">+ مصروف جديد</Btn>
        </div>
      </div>

      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
          <KPICard icon="💰" label="إجمالي الإيرادات" value={`${fmt(summary.total_revenue)} ج.م`} color="#2d8659" />
          <KPICard icon="📤" label="إجمالي المصروفات" value={`${fmt(summary.total_expenses)} ج.م`} color="#c0392b" />
          <KPICard icon="📊" label="صافي" value={`${fmt(summary.total_revenue - summary.total_expenses)} ج.م`} color={summary.total_revenue >= summary.total_expenses ? "#2d8659" : "#c0392b"} />
          <KPICard icon="📈" label="عدد العمليات" value={revenues.length + expenses.length} color="#5b6abf" />
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 24 }}>
        {summary?.monthly?.length > 0 && (
          <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>Cash Flow الشهري</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={summary.monthly}>
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
                <Pie data={summary.expense_categories.map(c => ({ name: catLabels[c.category] || c.category, value: c.total }))} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`} labelLine={false} style={{ fontSize: 11 }}>
                  {summary.expense_categories.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={v => `${fmt(v)} ج.م`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <TabBar tabs={[{ id: "revenues", label: `الإيرادات (${revenues.length})` }, { id: "expenses", label: `المصروفات (${expenses.length})` }]} active={tab} onChange={setTab} />

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

      {/* Revenue Modal */}
      <Modal open={modal === "revenue"} onClose={() => setModal(null)} title={form.id ? "تعديل إيراد" : "إيراد جديد"}>
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        <Select label="المصدر" value={form.source || "course"} onChange={e => setForm({ ...form, source: e.target.value })} options={Object.entries(srcLabels).map(([v, l]) => ({ value: v, label: l }))} />
        <Input label="الوصف" value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })} />
        <Input label="اسم العميل" value={form.client_name || ""} onChange={e => setForm({ ...form, client_name: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="المبلغ (ج.م)" type="number" value={form.amount_egp || 0} onChange={e => setForm({ ...form, amount_egp: +e.target.value })} />
          <Input label="المبلغ ($)" type="number" value={form.amount_usd || 0} onChange={e => setForm({ ...form, amount_usd: +e.target.value })} />
        </div>
        <Select label="طريقة الدفع" value={form.payment_method || "wise"} onChange={e => setForm({ ...form, payment_method: e.target.value })} options={[{ value: "wise", label: "Wise" }, { value: "bank_transfer", label: "تحويل بنكي" }, { value: "cash", label: "كاش" }, { value: "stripe", label: "Stripe" }]} />
        <Input label="ملاحظات" value={form.notes || ""} onChange={e => setForm({ ...form, notes: e.target.value })} />
        <Btn onClick={saveRevenue} color="#2d8659" style={{ width: "100%", marginTop: 8 }}>💾 حفظ</Btn>
      </Modal>

      {/* Expense Modal */}
      <Modal open={modal === "expense"} onClose={() => setModal(null)} title={form.id ? "تعديل مصروف" : "مصروف جديد"}>
        <Input label="التاريخ" type="date" value={form.date || ""} onChange={e => setForm({ ...form, date: e.target.value })} />
        <Select label="الفئة" value={form.category || "tools"} onChange={e => setForm({ ...form, category: e.target.value })} options={Object.entries(catLabels).map(([v, l]) => ({ value: v, label: l }))} />
        <Input label="الوصف" value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Input label="المبلغ (ج.م)" type="number" value={form.amount_egp || 0} onChange={e => setForm({ ...form, amount_egp: +e.target.value })} />
          <Input label="المبلغ ($)" type="number" value={form.amount_usd || 0} onChange={e => setForm({ ...form, amount_usd: +e.target.value })} />
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>
            <input type="checkbox" checked={form.is_business !== false} onChange={e => setForm({ ...form, is_business: e.target.checked })} style={{ marginLeft: 8 }} />
            مصروف أعمال
          </label>
        </div>
        <Input label="مدفوع بواسطة" value={form.paid_by || ""} onChange={e => setForm({ ...form, paid_by: e.target.value })} />
        <Btn onClick={saveExpense} color="#c0392b" style={{ width: "100%", marginTop: 8 }}>💾 حفظ</Btn>
      </Modal>
    </div>
  );
}

// ============================================================
// MARKETING DASHBOARD
// ============================================================
function MarketingPage() {
  const [campaigns, setCampaigns] = useState([]);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});

  const load = () => api.get("/campaigns").then(setCampaigns);
  useEffect(load, []);

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

// ============================================================
// COURSES SNAPSHOT
// ============================================================
function CoursesPage() {
  const [courses, setCourses] = useState([]);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});

  const load = () => api.get("/courses").then(setCourses);
  useEffect(load, []);

  const save = async () => {
    if (form.id) await api.put(`/courses/${form.id}`, form);
    else await api.post("/courses", form);
    setModal(false); setForm({}); load();
  };

  const totalStudents = courses.reduce((s, c) => s + (c.students_count || 0), 0);
  const totalRevenue = courses.reduce((s, c) => s + (c.total_revenue || 0), 0);
  const totalCost = courses.reduce((s, c) => s + (c.total_cost || 0), 0);
  const best = courses.length ? courses.reduce((a, b) => (a.profit || 0) > (b.profit || 0) ? a : b) : null;
  const worst = courses.length ? courses.reduce((a, b) => (a.profit || 0) < (b.profit || 0) ? a : b) : null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f4c81" }}>الدورات التدريبية</h1>
        <Btn onClick={() => { setForm({ status: "active" }); setModal(true); }} color="#1abc9c">+ دورة جديدة</Btn>
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
          <div key={c.id} style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", borderTop: `3px solid ${c.profit >= 0 ? "#2d8659" : "#c0392b"}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: "#1f2937" }}>{c.title}</h3>
              <div>
                <button onClick={() => { setForm(c); setModal(true); }} style={{ background: "none", border: "none", cursor: "pointer" }}>✏️</button>
                <button onClick={async () => { if (confirm("حذف؟")) { await api.del(`/courses/${c.id}`); load(); }}} style={{ background: "none", border: "none", cursor: "pointer" }}>🗑</button>
              </div>
            </div>
            <Badge text={c.status === "active" ? "نشطة" : c.status === "completed" ? "منتهية" : c.status} color={c.status === "active" ? "#2d8659" : "#9ca3af"} />
            {c.trainer_name && <span style={{ fontSize: 13, color: "#6b7280", marginRight: 8 }}>🎓 {c.trainer_name}</span>}
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
    </div>
  );
}

// ============================================================
// AI ASSISTANT
// ============================================================
function AIPage() {
  const [snapshot, setSnapshot] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.get("/ai/snapshot").then(setSnapshot); }, []);

  const quickActions = [
    { label: "📊 تلخيص حالة الشركة", prompt: "لخّص حالة الشركة المالية والتشغيلية في فقرتين. اذكر الإيرادات والمصروفات وصافي الربح وعدد العملاء والدورات. قدم تقييمك للوضع." },
    { label: "💰 تحليل مالي", prompt: "حلل الإيرادات والمصروفات بالتفصيل. ما هي مصادر الإيراد الأساسية؟ ما هي أكبر بنود المصروفات؟ هل burn rate مستدام؟ ما توصياتك؟" },
    { label: "📢 تحليل الحملات", prompt: "حلل أداء الحملات التسويقية. ما أفضل حملة من حيث ROAS؟ ما الحملات التي يجب إيقافها أو تحسينها؟ ما CPL و CAC؟" },
    { label: "⚠️ كشف المشاكل", prompt: "اكتشف أي مشاكل أو مخاطر في البيانات. هل يوجد تناقضات؟ هل يوجد عملاء يدفعون أكثر من المتوقع؟ هل يوجد مصروفات غير مبررة؟" },
    { label: "💡 اقتراح قرارات", prompt: "بناءً على البيانات الحالية، اقترح 5 قرارات إدارية عملية لتحسين أداء الشركة. ركز على زيادة الإيرادات وخفض التكاليف وتحسين التسويق." },
    { label: "📋 تقرير شهري", prompt: "ولّد تقرير شهري باللغة العربية يتضمن: الملخص التنفيذي، الأداء المالي، أداء التسويق، الدورات التدريبية، التوصيات. اجعل التقرير مناسبًا لعرضه على مجلس الإدارة." },
  ];

  const ask = async (q) => {
    const question = q || input;
    if (!question.trim()) return;
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: question }]);
    setLoading(true);

    try {
      const systemPrompt = `أنت مساعد إداري ومالي لشركة "البروفيسور" (ElProfessor) - منصة تعليم قانوني مصرية.
أجب بالعربية. كن مختصراً ودقيقاً. استخدم الأرقام الفعلية من البيانات المرفقة.
استخدم الرموز التعبيرية للوضوح. نسّق الأرقام بالفاصلة.
إذا طُلب منك تقرير، اجعله منظماً بعناوين فرعية.`;

      const response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          system: systemPrompt,
          messages: [{ role: "user", content: `${question}\n\nبيانات الشركة الحالية:\n${JSON.stringify(snapshot, null, 2)}` }]
        })
      });
      const data = await response.json();
      const aiText = data.content?.map(c => c.text || "").join("\n") || "لم أتمكن من الإجابة.";
      setMessages(prev => [...prev, { role: "assistant", content: aiText }]);
      api.post("/ai/log", { response: aiText });
    } catch (e) {
      setMessages(prev => [...prev, { role: "assistant", content: "⚠️ خطأ في الاتصال بـ AI. تحقق من الاتصال بالإنترنت." }]);
    }
    setLoading(false);
  };

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f4c81", marginBottom: 20 }}>🤖 مساعد القرار الذكي</h1>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 24 }}>
        {quickActions.map((a, i) => (
          <button key={i} onClick={() => ask(a.prompt)} disabled={loading} style={{ padding: "10px 18px", borderRadius: 10, border: "2px solid #e5e7eb", background: "#fff", fontSize: 13, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", color: "#374151", transition: "all 0.2s" }}
            onMouseEnter={e => { e.target.style.borderColor = "#0f4c81"; e.target.style.background = "#f0f5ff"; }}
            onMouseLeave={e => { e.target.style.borderColor = "#e5e7eb"; e.target.style.background = "#fff"; }}>
            {a.label}
          </button>
        ))}
      </div>

      <div style={{ background: "#fff", borderRadius: 16, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", overflow: "hidden" }}>
        <div style={{ height: 500, overflowY: "auto", padding: 24 }}>
          {messages.length === 0 && (
            <div style={{ textAlign: "center", padding: 60, color: "#9ca3af" }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>مرحباً! أنا مساعد القرار الذكي</div>
              <div style={{ fontSize: 14, marginTop: 8 }}>اسألني عن حالة الشركة، حلل البيانات، أو اطلب تقريراً</div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", marginBottom: 16 }}>
              <div style={{ maxWidth: "80%", padding: "14px 18px", borderRadius: 14, background: m.role === "user" ? "#0f4c81" : "#f3f4f6", color: m.role === "user" ? "#fff" : "#1f2937", fontSize: 14, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 16 }}>
              <div style={{ padding: "14px 18px", borderRadius: 14, background: "#f3f4f6", color: "#6b7280", fontSize: 14 }}>⏳ جاري التحليل...</div>
            </div>
          )}
        </div>

        <div style={{ borderTop: "1px solid #e5e7eb", padding: 16, display: "flex", gap: 10 }}>
          <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && ask()} placeholder="اسأل عن أي شيء يخص الشركة..." disabled={loading}
            style={{ flex: 1, padding: "12px 16px", borderRadius: 10, border: "1px solid #d1d5db", fontSize: 14 }} />
          <Btn onClick={() => ask()} disabled={loading || !input.trim()} style={{ padding: "12px 28px" }}>إرسال</Btn>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// SETTINGS PAGE
// ============================================================
function SettingsPage() {
  const [settings, setSettings] = useState({});
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.get("/settings").then(setSettings); }, []);

  const save = async () => {
    await api.put("/settings", settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f4c81", marginBottom: 24 }}>الإعدادات</h1>
      <div style={{ background: "#fff", borderRadius: 12, padding: 32, maxWidth: 500, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
        <Input label="اسم الشركة" value={settings.company_name || ""} onChange={e => setSettings({ ...settings, company_name: e.target.value })} />
        <Input label="سعر صرف الدولار (ج.م)" type="number" value={settings.exchange_rate || 50} onChange={e => setSettings({ ...settings, exchange_rate: e.target.value })} />
        <Input label="الرصيد الافتتاحي (ج.م)" type="number" value={settings.opening_balance_egp || 0} onChange={e => setSettings({ ...settings, opening_balance_egp: e.target.value })} />
        <Input label="العملة الأساسية" value={settings.currency || "EGP"} onChange={e => setSettings({ ...settings, currency: e.target.value })} />
        <Btn onClick={save} style={{ width: "100%", marginTop: 8 }}>💾 حفظ الإعدادات</Btn>
        {saved && <div style={{ textAlign: "center", color: "#2d8659", marginTop: 12, fontWeight: 600 }}>✅ تم الحفظ</div>}
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

const navItems = [
  { id: "overview", label: "نظرة عامة", icon: "📊" },
  { id: "finance", label: "المالية", icon: "💰" },
  { id: "marketing", label: "التسويق", icon: "📢" },
  { id: "courses", label: "الدورات", icon: "📚" },
  { id: "ai", label: "مساعد AI", icon: "🤖" },
  { id: "settings", label: "الإعدادات", icon: "⚙️" },
];

function Layout({ page, setPage, user, onLogout }) {
  return (
    <div style={{ display: "flex", minHeight: "100vh", direction: "rtl", fontFamily: "'Segoe UI', Tahoma, Arial, sans-serif" }}>
      {/* Sidebar */}
      <div style={{ width: 240, background: "linear-gradient(180deg, #0a1628, #1a365d)", padding: "24px 0", display: "flex", flexDirection: "column", flexShrink: 0 }}>
        <div style={{ padding: "0 24px", marginBottom: 36 }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#fff" }}>البروفيسور</div>
          <div style={{ fontSize: 11, color: "#64748b", letterSpacing: 1, marginTop: 2 }}>MANAGEMENT DASHBOARD</div>
        </div>
        <nav style={{ flex: 1 }}>
          {navItems.map(n => (
            <button key={n.id} onClick={() => setPage(n.id)} style={{ display: "flex", alignItems: "center", gap: 12, width: "100%", padding: "14px 24px", background: page === n.id ? "rgba(255,255,255,0.12)" : "transparent", border: "none", borderRight: page === n.id ? "3px solid #3b82f6" : "3px solid transparent", color: page === n.id ? "#fff" : "#94a3b8", fontSize: 15, fontWeight: page === n.id ? 700 : 500, cursor: "pointer", textAlign: "right", transition: "all 0.15s" }}>
              <span style={{ fontSize: 18 }}>{n.icon}</span>
              {n.label}
            </button>
          ))}
        </nav>
        <div style={{ padding: "16px 24px", borderTop: "1px solid rgba(255,255,255,0.1)" }}>
          <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 8 }}>👤 {user?.name}</div>
          <button onClick={onLogout} style={{ background: "none", border: "none", color: "#ef4444", fontSize: 13, cursor: "pointer", fontWeight: 600 }}>تسجيل الخروج</button>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, background: "#f8fafc", padding: "28px 32px", overflowY: "auto" }}>
        {page === "overview" && <OverviewPage />}
        {page === "finance" && <FinancePage />}
        {page === "marketing" && <MarketingPage />}
        {page === "courses" && <CoursesPage />}
        {page === "ai" && <AIPage />}
        {page === "settings" && <SettingsPage />}
      </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState("overview");
  const [checking, setChecking] = useState(true);

  useEffect(() => {
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
