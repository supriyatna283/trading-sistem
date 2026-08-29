"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

// ─── Types ──────────────────────────────────────────────────────
interface ScanResult {
  symbol: string;
  trend: string;
  latest_price: number;
  price_change_24h: number;
  liquidity_status: string;
  setup_status: string;
  confluence_score: number;
  max_score: number;
  signal_score: number;
  signal_grade: "A+" | "VALID" | "WEAK" | "NO_TRADE";
  score_breakdown: { STR: number; PA: number; SMC: number; VOL: number; TIM: number; RR: number };
  hard_rejected: boolean;
  rejection_reasons: string[];
  mtf_confirmation: string;
  rsi_1h: number | null;
  rsi_4h: number | null;
  rsi_1d: number | null;
  strong_rsi_signal: boolean;
  btc_dominance: number;
  orderbook_ratio: number;
  orderbook_bias: string;
  nearest_support: number;
  nearest_resistance: number;
  support_distance_pct: number;
  resistance_distance_pct: number;
  liquidation_cluster_low: number;
  liquidation_cluster_high: number;
  market_cap_tier: string;
  setup: any | null;
  error?: string;
}

type FilterType = "ALL" | "A+" | "VALID" | "WEAK" | "BULLISH" | "BEARISH" | "SETUP";
type SortType = "score" | "rsi_low" | "change" | "rr";

// ─── Sub-components ─────────────────────────────────────────────

function GradeLabel({ grade }: { grade: string }) {
  const cfg: Record<string, { color: string; bg: string; border: string; label: string }> = {
    "A+":       { color: "#f59e0b", bg: "rgba(245,158,11,0.15)", border: "rgba(245,158,11,0.4)", label: "A+ PRIME" },
    "VALID":    { color: "#10b981", bg: "rgba(16,185,129,0.12)", border: "rgba(16,185,129,0.35)", label: "✓ VALID" },
    "WEAK":     { color: "#60a5fa", bg: "rgba(96,165,250,0.12)", border: "rgba(96,165,250,0.3)", label: "WATCHLIST" },
    "NO_TRADE": { color: "#64748b", bg: "rgba(100,116,139,0.08)", border: "rgba(100,116,139,0.2)", label: "NO TRADE" },
  };
  const c = cfg[grade] || cfg["NO_TRADE"];
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "4px 10px", borderRadius: 8, fontSize: "0.65rem", fontWeight: 900,
      letterSpacing: "0.06em", color: c.color, background: c.bg, border: `1px solid ${c.border}`,
    }}>{c.label}</span>
  );
}

function TrendBadge({ trend }: { trend: string }) {
  const cfg: Record<string, { color: string; bg: string; icon: string }> = {
    BULLISH:  { color: "#22c55e", bg: "rgba(34,197,94,0.1)", icon: "▲" },
    BEARISH:  { color: "#ef4444", bg: "rgba(239,68,68,0.1)", icon: "▼" },
    SIDEWAYS: { color: "#94a3b8", bg: "rgba(148,163,184,0.08)", icon: "◆" },
    UNKNOWN:  { color: "#64748b", bg: "transparent", icon: "?" },
  };
  const c = cfg[trend] || cfg.UNKNOWN;
  return (
    <span style={{ fontSize: "0.65rem", fontWeight: 800, padding: "2px 7px", borderRadius: 5, color: c.color, background: c.bg }}>
      {c.icon} {trend}
    </span>
  );
}

function MTFBadge({ level }: { level: string }) {
  const cfg: Record<string, { color: string; label: string }> = {
    STRONG:   { color: "#22c55e", label: "MTF ✓✓" },
    MODERATE: { color: "#f59e0b", label: "MTF ✓" },
    WEAK:     { color: "#94a3b8", label: "MTF ~" },
    NONE:     { color: "#475569", label: "MTF ✗" },
    MIXED:    { color: "#8b5cf6", label: "MTF ±" },
  };
  const c = cfg[level] || cfg.NONE;
  return (
    <span style={{ fontSize: "0.6rem", fontWeight: 700, color: c.color }}>{c.label}</span>
  );
}

function RSIChip({ val, label }: { val: number | null; label: string }) {
  if (val === null || val === undefined) return <span style={{ color: "#475569", fontSize: "0.65rem" }}>—</span>;
  const color = val <= 30 ? "#22c55e" : val >= 70 ? "#ef4444" : "#94a3b8";
  const bg = val <= 25 ? "rgba(34,197,94,0.1)" : val >= 75 ? "rgba(239,68,68,0.1)" : "transparent";
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: "0.5rem", color: "#475569", fontWeight: 700, marginBottom: 2 }}>{label}</div>
      <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: "0.72rem", fontWeight: 800, color, background: bg, padding: "1px 5px", borderRadius: 4 }}>
        {val.toFixed(0)}
      </span>
    </div>
  );
}

function LayerBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: "0.5rem", fontWeight: 800, color: "#475569", width: 22, letterSpacing: "0.04em", flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
        <div style={{
          width: `${Math.min(value, 100)}%`, height: "100%", borderRadius: 2,
          background: value >= 70 ? "#22c55e" : value >= 45 ? "#f59e0b" : value >= 25 ? "#60a5fa" : "#ef4444",
          transition: "width 0.8s ease",
          boxShadow: value >= 70 ? `0 0 6px ${color}60` : "none",
        }} />
      </div>
      <span style={{ fontSize: "0.5rem", fontFamily: "'JetBrains Mono',monospace", fontWeight: 800, color: value >= 70 ? "#22c55e" : value >= 45 ? "#f59e0b" : "#64748b", width: 20, textAlign: "right", flexShrink: 0 }}>
        {value}
      </span>
    </div>
  );
}

function formatPrice(p: number) {
  if (!p || p <= 0) return "—";
  if (p >= 10000) return p.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (p >= 1) return p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 3 });
  return p.toFixed(5);
}

function ScannerCard({ row, onChart }: { row: ScanResult; onChart: (sym: string) => void }) {
  const bd = row.score_breakdown || { STR: 0, PA: 0, SMC: 0, VOL: 0, TIM: 0, RR: 0 };
  const gradeGlow: Record<string, string> = {
    "A+": "rgba(245,158,11,0.08)",
    "VALID": "rgba(16,185,129,0.06)",
    "WEAK": "rgba(96,165,250,0.04)",
    "NO_TRADE": "transparent",
  };
  const borderColor: Record<string, string> = {
    "A+": "rgba(245,158,11,0.25)",
    "VALID": "rgba(16,185,129,0.2)",
    "WEAK": "rgba(96,165,250,0.15)",
    "NO_TRADE": "rgba(255,255,255,0.05)",
  };
  const hasSetup = row.setup || (row.setup_status || "").includes("setup");
  const isForming = row.setup_status === "Setup forming";
  const chgClr = row.price_change_24h > 0 ? "#22c55e" : row.price_change_24h < 0 ? "#ef4444" : "#64748b";

  return (
    <div style={{
      background: `linear-gradient(135deg, rgba(15,20,40,0.95), rgba(20,25,45,0.9))`,
      border: `1px solid ${borderColor[row.signal_grade] || "rgba(255,255,255,0.06)"}`,
      borderRadius: 14,
      padding: "14px 16px",
      position: "relative",
      overflow: "hidden",
      boxShadow: row.signal_grade === "A+" ? "0 4px 24px rgba(245,158,11,0.1)" : "none",
      opacity: row.hard_rejected ? 0.55 : 1,
      transition: "transform 0.2s, box-shadow 0.2s",
    }}
    className="scanner-card"
    >
      {/* A+ glow overlay */}
      {row.signal_grade === "A+" && (
        <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse at top right, rgba(245,158,11,0.07), transparent 65%)", pointerEvents: "none" }} />
      )}

      {/* HEADER */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
            <span style={{ fontWeight: 900, fontSize: "1rem", color: "#fff", letterSpacing: "-0.01em" }}>
              {row.symbol.replace("USDT", "")}
              <span style={{ color: "#475569", fontSize: "0.65rem", fontWeight: 400 }}>/USDT</span>
            </span>
            <TrendBadge trend={row.trend} />
            <MTFBadge level={row.mtf_confirmation} />
            {row.strong_rsi_signal && (
              <span style={{ fontSize: "0.58rem", fontWeight: 800, color: "#f59e0b", background: "rgba(245,158,11,0.1)", padding: "2px 5px", borderRadius: 4 }}>RSI!</span>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontWeight: 700, fontSize: "0.9rem", color: "#e2e8f0" }}>
              {formatPrice(row.latest_price)}
            </span>
            <span style={{ fontSize: "0.7rem", fontWeight: 700, color: chgClr }}>
              {row.price_change_24h > 0 ? "+" : ""}{row.price_change_24h.toFixed(2)}%
            </span>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 5 }}>
          <GradeLabel grade={row.signal_grade} />
          {/* Score circle */}
          <div style={{ position: "relative", width: 38, height: 38 }}>
            <svg width="38" height="38" viewBox="0 0 38 38" style={{ transform: "rotate(-90deg)" }}>
              <circle cx="19" cy="19" r="15" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="4" />
              <circle cx="19" cy="19" r="15" fill="none"
                stroke={row.signal_score >= 75 ? "#f59e0b" : row.signal_score >= 50 ? "#10b981" : row.signal_score >= 35 ? "#60a5fa" : "#475569"}
                strokeWidth="4"
                strokeDasharray={`${(row.signal_score / 100) * 94.2} 94.2`}
                strokeLinecap="round"
                style={{ transition: "stroke-dasharray 1s ease" }}
              />
            </svg>
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.58rem", fontFamily: "'JetBrains Mono',monospace", fontWeight: 900, color: "#fff" }}>
              {row.signal_score}
            </div>
          </div>
        </div>
      </div>

      {/* 6-LAYER BREAKDOWN */}
      <div style={{ marginBottom: 10, padding: "8px 10px", background: "rgba(0,0,0,0.2)", borderRadius: 8, display: "flex", flexDirection: "column", gap: 4 }}>
        <LayerBar label="STR" value={bd.STR} color="#60a5fa" />
        <LayerBar label="PA"  value={bd.PA}  color="#a78bfa" />
        <LayerBar label="SMC" value={bd.SMC} color="#f59e0b" />
        <LayerBar label="VOL" value={bd.VOL} color="#22c55e" />
        <LayerBar label="TIM" value={bd.TIM} color="#fb923c" />
        <LayerBar label="RR"  value={bd.RR}  color="#e879f9" />
      </div>

      {/* METRICS ROW */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 6, marginBottom: 10 }}>
        <RSIChip val={row.rsi_1h} label="RSI 1H" />
        <RSIChip val={row.rsi_4h} label="RSI 4H" />
        <RSIChip val={row.rsi_1d} label="RSI 1D" />
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "0.5rem", color: "#475569", fontWeight: 700, marginBottom: 2 }}>OB Ratio</div>
          <span style={{
            fontFamily: "'JetBrains Mono',monospace", fontSize: "0.68rem", fontWeight: 800,
            color: row.orderbook_bias === "BULLISH" ? "#22c55e" : row.orderbook_bias === "BEARISH" ? "#ef4444" : "#64748b"
          }}>
            {(row.orderbook_ratio || 1).toFixed(2)}x
          </span>
        </div>
      </div>

      {/* S/R + LIQUIDATION */}
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        {row.nearest_support > 0 && (
          <div style={{ flex: 1, background: "rgba(34,197,94,0.05)", border: "1px solid rgba(34,197,94,0.1)", borderRadius: 6, padding: "5px 8px" }}>
            <div style={{ fontSize: "0.5rem", color: "#22c55e", fontWeight: 700, marginBottom: 2 }}>SUPPORT</div>
            <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: "0.65rem", color: "#e2e8f0", fontWeight: 700 }}>{formatPrice(row.nearest_support)}</div>
            <div style={{ fontSize: "0.5rem", color: "#64748b" }}>{row.support_distance_pct?.toFixed(1)}% away</div>
          </div>
        )}
        {row.nearest_resistance > 0 && (
          <div style={{ flex: 1, background: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.1)", borderRadius: 6, padding: "5px 8px" }}>
            <div style={{ fontSize: "0.5rem", color: "#ef4444", fontWeight: 700, marginBottom: 2 }}>RESISTANCE</div>
            <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: "0.65rem", color: "#e2e8f0", fontWeight: 700 }}>{formatPrice(row.nearest_resistance)}</div>
            <div style={{ fontSize: "0.5rem", color: "#64748b" }}>{row.resistance_distance_pct?.toFixed(1)}% away</div>
          </div>
        )}
        {row.liquidation_cluster_low > 0 && (
          <div style={{ flex: 1, background: "rgba(232,121,249,0.05)", border: "1px solid rgba(232,121,249,0.1)", borderRadius: 6, padding: "5px 8px" }}>
            <div style={{ fontSize: "0.5rem", color: "#e879f9", fontWeight: 700, marginBottom: 2 }}>LIQ ZONE</div>
            <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: "0.55rem", color: "#e2e8f0", fontWeight: 700 }}>
              {formatPrice(row.liquidation_cluster_low)}–{formatPrice(row.liquidation_cluster_high)}
            </div>
          </div>
        )}
      </div>

      {/* REJECTION */}
      {row.hard_rejected && row.rejection_reasons?.length > 0 && (
        <div style={{ fontSize: "0.6rem", color: "#ef4444", fontWeight: 700, marginBottom: 8, background: "rgba(239,68,68,0.06)", padding: "4px 8px", borderRadius: 6 }}>
          ⚠️ {row.rejection_reasons.join(" · ")}
        </div>
      )}

      {/* SETUP STATUS + CTA */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          {hasSetup ? (
            <span style={{ fontSize: "0.62rem", fontWeight: 800, color: "#f59e0b", background: "rgba(245,158,11,0.1)", padding: "3px 8px", borderRadius: 5 }}>
              ⚡ {row.setup_status}
            </span>
          ) : isForming ? (
            <span style={{ fontSize: "0.62rem", fontWeight: 700, color: "#60a5fa", background: "rgba(96,165,250,0.08)", padding: "3px 8px", borderRadius: 5 }}>
              🔄 Setup Forming
            </span>
          ) : (
            <span style={{ fontSize: "0.6rem", color: "#475569" }}>No setup</span>
          )}
          <span style={{ marginLeft: 6, fontSize: "0.58rem", color: "#475569", fontWeight: 600 }}>
            {(row.market_cap_tier && row.market_cap_tier !== "UNKNOWN") ? `· ${row.market_cap_tier}` : ""}
          </span>
        </div>
        <button
          onClick={() => onChart(row.symbol)}
          style={{
            padding: "5px 12px", borderRadius: 7, fontSize: "0.65rem", fontWeight: 700, cursor: "pointer",
            background: hasSetup ? "rgba(245,158,11,0.15)" : "rgba(255,255,255,0.05)",
            color: hasSetup ? "#f59e0b" : "#94a3b8",
            border: hasSetup ? "1px solid rgba(245,158,11,0.3)" : "1px solid rgba(255,255,255,0.08)",
            transition: "all 0.2s",
          }}
        >
          {hasSetup ? "⚡ Open Chart" : "→ Chart"}
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────
export default function ScannerPage() {
  const router = useRouter();
  const [scannerData, setScannerData] = useState<ScanResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [lastScan, setLastScan] = useState<Date | null>(null);
  const [filter, setFilter] = useState<FilterType>("ALL");
  const [sort, setSort] = useState<SortType>("score");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const autoRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const res = await api.getScanner();
      setScannerData(Array.isArray(res?.results) ? res.results : []);
      setLastScan(new Date());
    } catch (err) {
      console.error("Scanner fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleScan = useCallback(async () => {
    setIsScanning(true);
    try {
      await api.runScanner();
      await fetchData(true);
    } catch (err) {
      console.error("Scan error:", err);
    } finally {
      setIsScanning(false);
    }
  }, [fetchData]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Auto-refresh
  useEffect(() => {
    if (autoRefresh) {
      autoRefreshRef.current = setInterval(() => fetchData(true), 60000);
    } else {
      if (autoRefreshRef.current) clearInterval(autoRefreshRef.current);
    }
    return () => { if (autoRefreshRef.current) clearInterval(autoRefreshRef.current); };
  }, [autoRefresh, fetchData]);

  // Filter
  const filtered = scannerData.filter(r => {
    if (filter === "ALL") return true;
    if (filter === "A+") return r.signal_grade === "A+";
    if (filter === "VALID") return r.signal_grade === "VALID";
    if (filter === "WEAK") return r.signal_grade === "WEAK";
    if (filter === "BULLISH") return r.trend === "BULLISH";
    if (filter === "BEARISH") return r.trend === "BEARISH";
    if (filter === "SETUP") return !!(r.setup || (r.setup_status || "").includes("setup"));
    return true;
  });

  // Sort
  const sorted = [...filtered].sort((a, b) => {
    if (sort === "score") return (b.signal_score ?? 0) - (a.signal_score ?? 0);
    if (sort === "rsi_low") return (a.rsi_1h ?? 100) - (b.rsi_1h ?? 100);
    if (sort === "change") return Math.abs(b.price_change_24h ?? 0) - Math.abs(a.price_change_24h ?? 0);
    return 0;
  });

  // Stats
  const aPlusCount = scannerData.filter(r => r.signal_grade === "A+").length;
  const validCount = scannerData.filter(r => r.signal_grade === "VALID").length;
  const weakCount  = scannerData.filter(r => r.signal_grade === "WEAK").length;
  const setupCount = scannerData.filter(r => !!(r.setup || (r.setup_status || "").includes("setup"))).length;
  const btcDominance = scannerData.find(r => r.btc_dominance > 0)?.btc_dominance ?? 0;
  const bullishCount = scannerData.filter(r => r.trend === "BULLISH").length;
  const bearishCount = scannerData.filter(r => r.trend === "BEARISH").length;

  return (
    <MainLayout>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse-dot { 0%,100%{opacity:1;} 50%{opacity:0.35;} }
        @keyframes scan-ping { 0%{transform:scale(1);opacity:0.8} 100%{transform:scale(1.8);opacity:0} }
        .scanner-card:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,0,0,0.3) !important; }
        .scanner-card { transition: transform 0.2s, box-shadow 0.2s; }
        .filter-btn { transition: all 0.18s; }
        .filter-btn:hover { border-color: rgba(96,165,250,0.4) !important; color: #e2e8f0 !important; }
      `}</style>

      {/* ── PAGE HEADER ── */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 16, marginBottom: 18 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <div style={{ position: "relative" }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: isScanning ? "#f59e0b" : "#22c55e", animation: "pulse-dot 2s infinite" }} />
                {isScanning && <div style={{ position: "absolute", inset: 0, borderRadius: "50%", background: "#f59e0b", animation: "scan-ping 1.2s ease-out infinite" }} />}
              </div>
              <span style={{ fontSize: "0.7rem", fontWeight: 800, color: "#475569", letterSpacing: "0.12em", textTransform: "uppercase" }}>
                Professional Market Scanner · V7
              </span>
            </div>
            <h1 style={{ fontSize: "1.8rem", fontWeight: 900, letterSpacing: "-0.04em", margin: 0, background: "linear-gradient(135deg, #fff 35%, #475569)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              Market Intelligence
            </h1>
            <p style={{ color: "#475569", fontSize: "0.78rem", margin: "5px 0 0" }}>
              6-Layer: STR · PA · SMC · VOL · TIM · RR · {scannerData.length} pairs scanned
              {lastScan && ` · Last updated: ${lastScan.toLocaleTimeString()}`}
            </p>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            {/* Auto-refresh toggle */}
            <button
              onClick={() => setAutoRefresh(v => !v)}
              style={{
                padding: "8px 14px", borderRadius: 9, fontSize: "0.72rem", fontWeight: 700, cursor: "pointer",
                background: autoRefresh ? "rgba(34,197,94,0.12)" : "rgba(255,255,255,0.04)",
                color: autoRefresh ? "#22c55e" : "#64748b",
                border: autoRefresh ? "1px solid rgba(34,197,94,0.3)" : "1px solid rgba(255,255,255,0.08)",
                transition: "all 0.2s",
              }}
            >
              {autoRefresh ? "⏱ Auto ON" : "⏱ Auto OFF"}
            </button>

            <button
              onClick={handleScan}
              disabled={isScanning || isLoading}
              style={{
                padding: "10px 22px", borderRadius: 10, fontSize: "0.82rem", fontWeight: 800, cursor: "pointer",
                background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
                color: "#fff", border: "none", opacity: isScanning ? 0.7 : 1,
                display: "flex", alignItems: "center", gap: 8,
                boxShadow: "0 4px 20px rgba(59,130,246,0.3)",
              }}
            >
              {isScanning ? (
                <><span style={{ width: 13, height: 13, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.8s linear infinite", display: "inline-block" }} />Scanning…</>
              ) : "⚡ Run Scan"}
            </button>
          </div>
        </div>

        {/* ── STATS BAR ── */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 10 }}>
          {[
            { label: "Total Scanned", val: scannerData.length, color: "#94a3b8", icon: "📡" },
            { label: "A+ Setups", val: aPlusCount, color: "#f59e0b", icon: "⭐" },
            { label: "Valid Signals", val: validCount, color: "#10b981", icon: "✅" },
            { label: "Watchlist", val: weakCount, color: "#60a5fa", icon: "👁" },
            { label: "Active Setups", val: setupCount, color: "#e879f9", icon: "⚡" },
            { label: "Bullish", val: bullishCount, color: "#22c55e", icon: "▲" },
            { label: "Bearish", val: bearishCount, color: "#ef4444", icon: "▼" },
            ...(btcDominance > 0 ? [{ label: "BTC Dom.", val: `${btcDominance.toFixed(1)}%`, color: "#eab308", icon: "₿" }] : []),
          ].map((s, i) => (
            <div key={i} style={{
              background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: 10, padding: "10px 14px", display: "flex", alignItems: "center", gap: 10,
            }}>
              <span style={{ fontSize: "1.1rem" }}>{s.icon}</span>
              <div>
                <div style={{ fontFamily: "'JetBrains Mono',monospace", fontWeight: 900, fontSize: "1.1rem", color: s.color }}>{s.val}</div>
                <div style={{ fontSize: "0.58rem", color: "#475569", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>{s.label}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── FILTER + SORT BAR ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {(["ALL", "A+", "VALID", "WEAK", "SETUP", "BULLISH", "BEARISH"] as FilterType[]).map(f => {
            const colors: Record<string, string> = { "A+": "#f59e0b", "VALID": "#10b981", "WEAK": "#60a5fa", "SETUP": "#e879f9", "BULLISH": "#22c55e", "BEARISH": "#ef4444", "ALL": "#94a3b8" };
            const active = filter === f;
            return (
              <button key={f} onClick={() => setFilter(f)} className="filter-btn"
                style={{
                  padding: "7px 15px", borderRadius: 8, fontSize: "0.75rem", fontWeight: 800, cursor: "pointer",
                  background: active ? `${colors[f]}18` : "rgba(255,255,255,0.03)",
                  color: active ? colors[f] : "#475569",
                  border: active ? `1px solid ${colors[f]}40` : "1px solid rgba(255,255,255,0.07)",
                }}
              >
                {f === "A+" ? "⭐ A+" : f === "SETUP" ? "⚡ SETUP" : f === "BULLISH" ? "▲ BULL" : f === "BEARISH" ? "▼ BEAR" : f}
              </button>
            );
          })}
        </div>

        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: "0.7rem", color: "#475569", fontWeight: 700 }}>Sort:</span>
          {([["score", "Score ↓"], ["rsi_low", "RSI Low ↑"], ["change", "Volatility ↓"]] as [SortType, string][]).map(([k, label]) => (
            <button key={k} onClick={() => setSort(k)} className="filter-btn"
              style={{
                padding: "6px 12px", borderRadius: 7, fontSize: "0.68rem", fontWeight: 700, cursor: "pointer",
                background: sort === k ? "rgba(96,165,250,0.12)" : "rgba(255,255,255,0.03)",
                color: sort === k ? "#60a5fa" : "#475569",
                border: sort === k ? "1px solid rgba(96,165,250,0.3)" : "1px solid rgba(255,255,255,0.07)",
              }}
            >{label}</button>
          ))}
        </div>
      </div>

      {/* ── CARDS GRID ── */}
      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 0", gap: 16, color: "#475569" }}>
          <div style={{ width: 40, height: 40, border: "3px solid rgba(59,130,246,0.2)", borderTopColor: "#3b82f6", borderRadius: "50%", animation: "spin 0.9s linear infinite" }} />
          <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>Analyzing markets…</div>
          <div style={{ fontSize: "0.75rem" }}>Fetching SMC, MTF, sentiment & order flow data</div>
        </div>
      ) : sorted.length === 0 ? (
        <div style={{ textAlign: "center", padding: "80px 0", color: "#475569" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: 14 }}>📡</div>
          <div style={{ fontWeight: 800, fontSize: "1rem", color: "#64748b", marginBottom: 8 }}>No results for this filter</div>
          <div style={{ fontSize: "0.82rem" }}>Try running a new scan or change the filter above.</div>
          <button onClick={handleScan} style={{ marginTop: 18, padding: "10px 24px", borderRadius: 9, background: "linear-gradient(135deg,#3b82f6,#8b5cf6)", color: "#fff", border: "none", fontWeight: 800, fontSize: "0.82rem", cursor: "pointer" }}>
            ⚡ Run Global Scan
          </button>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(310px, 1fr))", gap: 14 }}>
          {sorted.map(row => (
            <ScannerCard
              key={row.symbol}
              row={row}
              onChart={(sym) => router.push(`/charts?symbol=${sym}`)}
            />
          ))}
        </div>
      )}

      {sorted.length > 0 && (
        <div style={{ textAlign: "center", marginTop: 28, fontSize: "0.72rem", color: "#334155" }}>
          Showing {sorted.length} of {scannerData.length} pairs · {filter !== "ALL" ? `Filtered: ${filter}` : "All pairs"} · Sorted by {sort}
        </div>
      )}
    </MainLayout>
  );
}
