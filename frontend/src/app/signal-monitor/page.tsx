"use client";
import { useEffect, useState, useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://ucilkecil387-trading-api.hf.space";

// ── Types ─────────────────────────────────────────────────────────────────────
interface SignalRecord {
  fingerprint: string;
  symbol: string;
  direction: string;
  entry_low: number;
  entry_high: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2?: number;
  timeframe: string;
  score: number;
  grade: string;
  status: string;
  age_hours: number;
  last_price?: number;
  created_at: string;
  resolution_note: string;
}

interface ScanLog {
  symbol: string;
  tf?: string;
  direction?: string;
  price?: number;
  in_zone?: boolean;
  zone_low?: number;
  zone_high?: number;
  action?: string;
  reason?: string;
  wa_sent?: boolean;
  error?: string;
  info?: string;
}

interface ScanState {
  running: boolean;
  last_scan_at?: string;
  next_scan_at?: string;
  total_cycles: number;
  symbols_checked: number;
  alerts_fired: number;
  alerts_blocked: number;
  last_cycle_log: ScanLog[];
  errors: string[];
}

interface SignalLogData {
  active: SignalRecord[];
  history: SignalRecord[];
  total_active: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const STATUS_COLOR: Record<string, string> = {
  ACTIVE:    "#10b981",
  HIT_TP1:   "#3b82f6",
  HIT_TP2:   "#6366f1",
  HIT_SL:    "#ef4444",
  EXPIRED:   "#6b7280",
  CANCELLED: "#f59e0b",
};
const STATUS_ICON: Record<string, string> = {
  ACTIVE: "🟢", HIT_TP1: "✅", HIT_TP2: "🎯",
  HIT_SL: "❌", EXPIRED: "⏰", CANCELLED: "🚫",
};
const ACTION_ICON: Record<string, string> = {
  fire: "📱", skip: "⏭️", blocked: "🔒",
};

function pill(label: string, color: string, bg?: string) {
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 5, fontSize: "0.6rem", fontWeight: 800,
      background: bg || `${color}20`, color, border: `1px solid ${color}40`,
    }}>{label}</span>
  );
}

function timeAgo(iso?: string): string {
  if (!iso) return "—";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function timeTo(iso?: string): string {
  if (!iso) return "—";
  const diff = Math.floor((new Date(iso).getTime() - Date.now()) / 1000);
  if (diff < 0) return "now";
  if (diff < 60) return `${diff}s`;
  return `${Math.floor(diff / 60)}m ${diff % 60}s`;
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function SignalMonitorPage() {
  const [scan, setScan]       = useState<ScanState | null>(null);
  const [sigLog, setSigLog]   = useState<SignalLogData | null>(null);
  const [activeTab, setTab]   = useState<"active"|"history"|"scanner">("active");
  const [refreshIn, setRefreshIn] = useState(10);
  const [triggering, setTriggering] = useState(false);
  const [cancelling, setCancelling] = useState<string>("");
  const [lastRefresh, setLastRefresh] = useState<string>("");

  const fetchAll = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([
        fetch(`${API_URL}/api/v1/alerts/scanner/status`).then(r => r.json()),
        fetch(`${API_URL}/api/v1/alerts/signal-log?limit=100`).then(r => r.json()),
      ]);
      setScan(s);
      setSigLog(l);
      setLastRefresh(new Date().toLocaleTimeString("id-ID"));
    } catch {}
  }, []);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 10000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  // Countdown
  useEffect(() => {
    const iv = setInterval(() => setRefreshIn(r => r <= 1 ? 10 : r - 1), 1000);
    return () => clearInterval(iv);
  }, []);

  const triggerScan = async () => {
    setTriggering(true);
    try {
      await fetch(`${API_URL}/api/v1/alerts/scanner/trigger`, { method: "POST" });
      await fetchAll();
    } catch {}
    setTriggering(false);
  };

  const cancelSignal = async (symbol: string) => {
    setCancelling(symbol);
    try {
      await fetch(`${API_URL}/api/v1/alerts/signal-cancel/${symbol}?reason=user_cancelled`, { method: "POST" });
      await fetchAll();
    } catch {}
    setCancelling("");
  };

  const active  = sigLog?.active  || [];
  const history = sigLog?.history || [];
  const cycleLogs = scan?.last_cycle_log || [];
  const inZone  = cycleLogs.filter(l => l.in_zone);
  const fired   = cycleLogs.filter(l => l.action === "fire");

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)", color: "var(--text-primary)", padding: "24px", fontFamily: "'Inter', sans-serif" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: "1.6rem" }}>📡</span>
            <div>
              <h1 style={{ margin: 0, fontSize: "1.4rem", fontWeight: 900, background: "linear-gradient(135deg,#10b981,#3b82f6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                Signal Monitor
              </h1>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: 2 }}>
                Real-time WA alert tracker · auto-refresh 10s · last: {lastRefresh}
              </div>
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", padding: "4px 10px", borderRadius: 6, background: "rgba(255,255,255,0.04)", border: "1px solid var(--border)" }}>
            refresh in {refreshIn}s
          </div>
          <button onClick={fetchAll} style={{ padding: "6px 14px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 700, cursor: "pointer", background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.25)", color: "#3b82f6" }}>
            🔄 Refresh
          </button>
          <button onClick={triggerScan} disabled={triggering} style={{ padding: "6px 14px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 700, cursor: "pointer", background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.3)", color: "#10b981" }}>
            {triggering ? "Scanning…" : "⚡ Scan Now"}
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 12, marginBottom: 24 }}>
        {[
          { label: "Active Signals",   value: active.length,            icon: "🟢", color: "#10b981" },
          { label: "Alerts Fired",     value: scan?.alerts_fired ?? 0,  icon: "📱", color: "#6366f1" },
          { label: "Blocked",          value: scan?.alerts_blocked ?? 0,icon: "🔒", color: "#f59e0b" },
          { label: "Scan Cycles",      value: scan?.total_cycles ?? 0,  icon: "🔄", color: "#3b82f6" },
          { label: "Symbols Checked",  value: scan?.symbols_checked ?? 0,icon:"🔍", color: "#8b5cf6" },
          { label: "In Zone (last)",   value: inZone.length,            icon: "🎯", color: "#10b981" },
        ].map(s => (
          <div key={s.label} style={{ padding: "14px 16px", borderRadius: 12, background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", textAlign: "center" }}>
            <div style={{ fontSize: "1.4rem" }}>{s.icon}</div>
            <div style={{ fontSize: "1.3rem", fontWeight: 900, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Scanner Status Bar */}
      <div style={{ padding: "12px 16px", borderRadius: 10, background: scan?.running ? "rgba(16,185,129,0.06)" : "rgba(239,68,68,0.06)", border: `1px solid ${scan?.running ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}`, marginBottom: 20, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: "0.75rem", fontWeight: 800, color: scan?.running ? "#10b981" : "#ef4444" }}>
          {scan?.running ? "🟢 Scanner AKTIF" : "🔴 Scanner MATI"}
        </span>
        <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>
          Last scan: <strong style={{ color: "#fff" }}>{timeAgo(scan?.last_scan_at)}</strong>
        </span>
        <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>
          Next scan: <strong style={{ color: "#10b981" }}>{timeTo(scan?.next_scan_at)}</strong>
        </span>
        {inZone.length > 0 && (
          <span style={{ fontSize: "0.65rem", color: "#f59e0b", fontWeight: 700 }}>
            ⚠️ {inZone.length} koin dalam Entry Zone sekarang!
          </span>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {([["active","🟢 Active Signals"],["history","📜 Histori"],["scanner","🔍 Log Scanner"]] as [string,string][]).map(([id,label]) => (
          <button key={id} onClick={() => setTab(id as any)} style={{
            padding: "8px 16px", borderRadius: 8, fontSize: "0.72rem", fontWeight: 700, cursor: "pointer",
            background: activeTab === id ? "rgba(16,185,129,0.12)" : "transparent",
            border: `1px solid ${activeTab === id ? "rgba(16,185,129,0.35)" : "rgba(255,255,255,0.06)"}`,
            color: activeTab === id ? "#10b981" : "var(--text-muted)",
          }}>{label} {id==="active" && `(${active.length})`}</button>
        ))}
      </div>

      {/* ── ACTIVE SIGNALS ────────────────────────────────────────────────────── */}
      {activeTab === "active" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {active.length === 0 && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem", background: "rgba(255,255,255,0.02)", borderRadius: 12, border: "1px dashed var(--border)" }}>
              <div style={{ fontSize: "2rem", marginBottom: 8 }}>😴</div>
              Tidak ada signal aktif saat ini.<br/>
              <span style={{ fontSize: "0.65rem" }}>Scanner akan otomatis mendeteksi setup baru setiap 5 menit.</span>
            </div>
          )}
          {active.map(sig => (
            <div key={sig.fingerprint} style={{ padding: "16px 20px", borderRadius: 12, background: "rgba(255,255,255,0.03)", border: `1px solid ${STATUS_COLOR[sig.status]}30`, position: "relative" }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ fontSize: "1.5rem" }}>{STATUS_ICON[sig.status] || "📊"}</div>
                  <div>
                    <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                      <span style={{ fontWeight: 900, fontSize: "1rem" }}>{sig.symbol}</span>
                      {pill(sig.direction, sig.direction==="LONG" ? "#10b981" : "#ef4444")}
                      {pill(sig.grade, sig.grade==="A+" ? "#f59e0b" : "#3b82f6")}
                      {pill(sig.timeframe, "#8b5cf6")}
                      {pill(sig.status, STATUS_COLOR[sig.status])}
                    </div>
                    <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: 4 }}>
                      Score: <strong>{sig.score}/100</strong> · Age: {sig.age_hours}h · ID: {sig.fingerprint}
                    </div>
                  </div>
                </div>
                <button onClick={() => cancelSignal(sig.symbol)} disabled={cancelling === sig.symbol} style={{ padding: "5px 12px", borderRadius: 6, fontSize: "0.6rem", fontWeight: 700, cursor: "pointer", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#ef4444" }}>
                  {cancelling === sig.symbol ? "…" : "Cancel Signal"}
                </button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))", gap: 8, marginTop: 14 }}>
                {[
                  ["Entry Zone", `${sig.entry_low.toLocaleString()} – ${sig.entry_high.toLocaleString()}`],
                  ["Stop Loss",  sig.stop_loss.toLocaleString()],
                  ["TP1",        sig.take_profit_1.toLocaleString()],
                  ["TP2",        sig.take_profit_2?.toLocaleString() || "—"],
                  ["Last Price", sig.last_price?.toLocaleString() || "Fetching…"],
                ].map(([k,v]) => (
                  <div key={k} style={{ padding: "8px 10px", borderRadius: 8, background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase" }}>{k}</div>
                    <div style={{ fontSize: "0.78rem", fontWeight: 800, marginTop: 2 }}>{v}</div>
                  </div>
                ))}
              </div>

              {sig.resolution_note && (
                <div style={{ marginTop: 10, fontSize: "0.6rem", color: "#f59e0b", padding: "6px 10px", borderRadius: 6, background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.15)" }}>
                  ℹ️ {sig.resolution_note}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── HISTORY ───────────────────────────────────────────────────────────── */}
      {activeTab === "history" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {history.length === 0 && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem" }}>Belum ada histori signal.</div>
          )}
          {[...history].reverse().map((sig, i) => (
            <div key={i} style={{ padding: "12px 16px", borderRadius: 10, background: "rgba(255,255,255,0.02)", border: `1px solid ${STATUS_COLOR[sig.status]}25`, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <span style={{ fontSize: "1.2rem" }}>{STATUS_ICON[sig.status]}</span>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 800, fontSize: "0.85rem" }}>{sig.symbol}</span>
                  {pill(sig.direction, sig.direction==="LONG" ? "#10b981" : "#ef4444")}
                  {pill(sig.grade, "#f59e0b")}
                  {pill(sig.timeframe, "#8b5cf6")}
                  {pill(sig.status, STATUS_COLOR[sig.status])}
                </div>
                <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginTop: 3 }}>
                  Entry: {sig.entry_low.toLocaleString()} · SL: {sig.stop_loss.toLocaleString()} · TP1: {sig.take_profit_1.toLocaleString()} · {timeAgo(sig.created_at)}
                  {sig.resolution_note && <span style={{ color: "#f59e0b" }}> · {sig.resolution_note}</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── SCANNER LOG ───────────────────────────────────────────────────────── */}
      {activeTab === "scanner" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {scan?.errors && scan.errors.length > 0 && (
            <div style={{ padding: 10, borderRadius: 8, background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)", fontSize: "0.65rem", color: "#ef4444" }}>
              ❌ Errors: {scan.errors.join(" | ")}
            </div>
          )}
          {cycleLogs.length === 0 && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem" }}>
              Belum ada log siklus scanner. Klik ⚡ Scan Now untuk memulai.
            </div>
          )}
          {/* In-zone highlight */}
          {inZone.length > 0 && (
            <div style={{ padding: "10px 14px", borderRadius: 10, background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.25)", marginBottom: 4 }}>
              <div style={{ fontSize: "0.72rem", fontWeight: 800, color: "#10b981", marginBottom: 6 }}>🎯 {inZone.length} Koin Dalam Entry Zone Sekarang!</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {inZone.map((l,i) => (
                  <div key={i} style={{ padding: "4px 10px", borderRadius: 6, background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.25)", fontSize: "0.65rem", fontWeight: 700 }}>
                    {ACTION_ICON[l.action||"skip"]} {l.symbol} {l.direction} @ {l.price?.toLocaleString()} {l.wa_sent && "📱 WA Sent"}
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* Full log table */}
          <div style={{ overflowX: "auto", borderRadius: 12, border: "1px solid var(--border)" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.65rem" }}>
              <thead>
                <tr style={{ background: "rgba(255,255,255,0.04)" }}>
                  {["Symbol","TF","Direction","Price","Zone","Action","Reason"].map(h => (
                    <th key={h} style={{ padding: "8px 12px", textAlign: "left", color: "var(--text-muted)", fontWeight: 700, whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cycleLogs.map((l, i) => (
                  <tr key={i} style={{ borderTop: "1px solid var(--border)", background: l.in_zone ? "rgba(16,185,129,0.04)" : "transparent" }}>
                    <td style={{ padding: "7px 12px", fontWeight: 800 }}>{l.symbol || "—"}</td>
                    <td style={{ padding: "7px 12px", color: "var(--text-muted)" }}>{l.tf || "—"}</td>
                    <td style={{ padding: "7px 12px" }}>
                      {l.direction ? <span style={{ color: l.direction==="LONG" ? "#10b981" : "#ef4444", fontWeight: 700 }}>{l.direction}</span> : "—"}
                    </td>
                    <td style={{ padding: "7px 12px", fontFamily: "monospace" }}>{l.price?.toLocaleString() || "—"}</td>
                    <td style={{ padding: "7px 12px" }}>
                      {l.in_zone !== undefined ? (l.in_zone ? <span style={{ color: "#10b981", fontWeight: 800 }}>✅ IN</span> : <span style={{ color: "var(--text-muted)" }}>—</span>) : "—"}
                    </td>
                    <td style={{ padding: "7px 12px" }}>
                      <span style={{ color: l.action==="fire" ? "#10b981" : l.action==="blocked" ? "#f59e0b" : "var(--text-muted)" }}>
                        {ACTION_ICON[l.action||"skip"]} {l.action || "—"}
                      </span>
                    </td>
                    <td style={{ padding: "7px 12px", color: "var(--text-muted)", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {l.reason || l.info || l.error || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}