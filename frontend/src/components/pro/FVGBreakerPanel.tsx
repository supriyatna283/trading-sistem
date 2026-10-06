"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { API_URL } from "@/lib/utils";

/* ─────────────────────────────────────────────────────────
   Types
───────────────────────────────────────────────────────── */
interface EntryZone {
  entry: number; stop_loss: number;
  tp1: number; tp2: number; tp3: number;
  rr_tp1: number; rr_tp2: number;
  risk_pct: number; quality: string;
}
interface FVG {
  id: number; type: "BULLISH" | "BEARISH";
  gap_high: number; gap_low: number; ce_level: number;
  size: number; size_atr_mult: number;
  bar_idx: number; bar_age: number;
  status: string; is_inverted: boolean; fill_pct: number;
  vol_ratio: number;
  is_institutional: boolean; is_stacked: boolean; stack_count: number;
  strength: number;
  entry_zone: EntryZone | null;
}
interface BreakerBlock {
  id: number; type: string;
  ob_high: number; ob_low: number; midpoint: number; ote_entry: number;
  break_price: number; break_direction: string; break_strength: number;
  status: string; test_count: number; has_returned: boolean;
  strength: number; entry_zone: EntryZone | null;
}
interface RejectionBlock {
  id: number; type: string;
  zone_high: number; zone_low: number;
  wick_pct: number; bar_idx: number; strength: number;
}
interface FVGStack { zone_high: number; zone_low: number; count: number; types: string[]; strength: number; }
interface ICTSetup {
  total: number; grade: string; description: string;
  components: Record<string, number>;
  has_fvg: boolean; has_breaker: boolean; has_displacement: boolean;
}
interface FVGResult {
  current_price: number; atr: number;
  summary: { total_fvgs: number; fresh_fvgs: number; inverted_fvgs: number; institutional_fvgs: number; total_breakers: number; stacked_zones: number };
  bullish_fvgs: FVG[]; bearish_fvgs: FVG[]; top_fvgs: FVG[];
  bullish_breakers: BreakerBlock[]; bearish_breakers: BreakerBlock[];
  rejection_blocks: RejectionBlock[];
  fvg_stacks: FVGStack[];
  nearest: { bullish_fvg: FVG | null; bearish_fvg: FVG | null; breaker: BreakerBlock | null };
  ict_setup: ICTSetup;
  signals: { fvg_signal: string; breaker_signal: string; entry_bias: string; confluence_score: number; messages: string[]; warnings: string[] };
}

/* ─────────────────────────────────────────────────────────
   Micro components
───────────────────────────────────────────────────────── */
const FG: Record<string, string> = {
  BULLISH: "#10b981", BEARISH: "#ef4444", NEUTRAL: "#64748b",
  BULLISH_BREAKER: "#10b981", BEARISH_BREAKER: "#ef4444",
  BULLISH_RB: "#10b981", BEARISH_RB: "#ef4444",
};

function Badge({ label, color, size = "sm" }: { label: string; color: string; size?: "xs" | "sm" }) {
  const p = size === "xs" ? "1px 6px" : "2px 9px";
  const fs = size === "xs" ? "0.55rem" : "0.62rem";
  return (
    <span style={{ padding: p, borderRadius: 5, fontSize: fs, fontWeight: 800, background: `${color}18`, color, border: `1px solid ${color}35`, whiteSpace: "nowrap" }}>{label}</span>
  );
}

function Bar({ v, max = 100, color = "#3b82f6", h = 5 }: { v: number; max?: number; color?: string; h?: number }) {
  return (
    <div style={{ height: h, borderRadius: 99, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
      <div style={{ height: "100%", width: `${Math.min(100, (v / max) * 100)}%`, background: color, borderRadius: 99, transition: "width .7s cubic-bezier(.4,0,.2,1)" }} />
    </div>
  );
}

function GradeRing({ grade, score }: { grade: string; score: number }) {
  const c: Record<string, string> = { "A+": "#10b981", A: "#34d399", B: "#3b82f6", C: "#f59e0b", D: "#f97316", WAIT: "#64748b" };
  const color = c[grade] ?? "#64748b";
  const r = 28, circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <div style={{ position: "relative", width: 80, height: 80, flexShrink: 0 }}>
      <svg width={80} height={80} viewBox="0 0 80 80">
        <circle cx={40} cy={40} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={6} />
        <circle cx={40} cy={40} r={r} fill="none" stroke={color} strokeWidth={6}
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
          transform="rotate(-90 40 40)" style={{ transition: "stroke-dasharray .8s ease" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: "1rem", fontWeight: 900, color, lineHeight: 1 }}>{grade}</div>
        <div style={{ fontSize: "0.5rem", color: "var(--text-muted)" }}>{score.toFixed(0)}/100</div>
      </div>
    </div>
  );
}

function EntryCard({ ez, direction, price }: { ez: EntryZone; direction: "BUY" | "SELL"; price: number }) {
  const c = direction === "BUY" ? "#10b981" : "#ef4444";
  const dist = Math.abs(price - ez.entry) / price * 100;
  return (
    <div style={{ padding: "12px 14px", borderRadius: 10, background: `${c}07`, border: `1px solid ${c}25`, marginTop: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
        <span style={{ fontSize: "0.65rem", fontWeight: 800, color: c }}>Entry Zone ({ez.quality})</span>
        <Badge label={`${dist.toFixed(2)}% from price`} color="#64748b" size="xs" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 5 }}>
        {[
          ["ENTRY", ez.entry,     c],
          ["SL",    ez.stop_loss, "#ef4444"],
          ["TP1",   ez.tp1,       "#10b981"],
          ["TP2",   ez.tp2,       "#10b981"],
          ["TP3",   ez.tp3,       "#a78bfa"],
        ].map(([lbl, val, col]) => (
          <div key={lbl as string} style={{ textAlign: "center", padding: "5px 4px", borderRadius: 6, background: "rgba(255,255,255,0.03)" }}>
            <div style={{ fontSize: "0.48rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 2 }}>{lbl}</div>
            <div style={{ fontSize: "0.62rem", fontFamily: "monospace", fontWeight: 700, color: col as string }}>
              {(val as number).toLocaleString("en", { maximumFractionDigits: 2 })}
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
        <div style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>
          R:R TP1 <span style={{ color: "#f59e0b", fontWeight: 800 }}>1:{ez.rr_tp1}</span>
        </div>
        <div style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>
          R:R TP2 <span style={{ color: "#10b981", fontWeight: 800 }}>1:{ez.rr_tp2}</span>
        </div>
        <div style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>
          Risk <span style={{ color: "#ef4444", fontWeight: 700 }}>{ez.risk_pct.toFixed(3)}%</span>
        </div>
      </div>
    </div>
  );
}

function FVGCard({ fvg, price, expanded, onToggle }: { fvg: FVG; price: number; expanded: boolean; onToggle: () => void }) {
  const c = FG[fvg.type];
  const statC: Record<string, string> = { FRESH: "#10b981", PARTIAL: "#f59e0b", FILLED: "#475569", INVERTED: "#a78bfa" };
  const distCE = ((price - fvg.ce_level) / price * 100).toFixed(2);
  const dir = fvg.type === "BULLISH" ? "BUY" : "SELL";
  return (
    <div style={{ borderRadius: 12, background: `${c}07`, border: `1px solid ${c}20`, overflow: "hidden", marginBottom: 8 }}>
      {/* Header row */}
      <div onClick={onToggle} style={{ padding: "12px 14px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
          <span style={{ fontFamily: "monospace", fontWeight: 900, fontSize: "0.72rem", color: c }}>
            {fvg.gap_low.toLocaleString("en",{maximumFractionDigits:2})} – {fvg.gap_high.toLocaleString("en",{maximumFractionDigits:2})}
          </span>
          <Badge label={fvg.type === "BULLISH" ? "BULL FVG" : "BEAR FVG"} color={c} />
          <Badge label={fvg.status} color={statC[fvg.status] ?? "#64748b"} />
          {fvg.is_inverted && <Badge label="IFVG" color="#a78bfa" />}
          {fvg.is_institutional && <Badge label="INST" color="#6366f1" />}
          {fvg.is_stacked && <Badge label={`STACK x${fvg.stack_count}`} color="#f97316" />}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.7rem", fontWeight: 900, color: c }}>{fvg.strength}</div>
            <div style={{ fontSize: "0.52rem", color: "var(--text-muted)" }}>strength</div>
          </div>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: `${c}15`, display: "flex", alignItems: "center", justifyContent: "center", color: c, fontSize: "0.7rem" }}>
            {expanded ? "▲" : "▼"}
          </div>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div style={{ padding: "0 14px 14px" }}>
          {/* Stats grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 6, marginBottom: 10 }}>
            {[
              ["CE Level", fvg.ce_level.toLocaleString("en",{maximumFractionDigits:2}), "#f59e0b"],
              ["ATR Mult", `${fvg.size_atr_mult}x`, "var(--text-secondary)"],
              ["Vol Ratio", `${fvg.vol_ratio}x`, fvg.vol_ratio > 1.5 ? "#10b981" : "var(--text-muted)"],
              ["Fill%", `${fvg.fill_pct.toFixed(0)}%`, fvg.fill_pct > 0 ? "#f59e0b" : "var(--text-muted)"],
              ["CE Dist", `${distCE}%`, c],
            ].map(([l, v, col]) => (
              <div key={l as string} style={{ padding: "7px 8px", borderRadius: 7, background: "rgba(255,255,255,0.02)", textAlign: "center" }}>
                <div style={{ fontSize: "0.48rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 2 }}>{l}</div>
                <div style={{ fontSize: "0.68rem", fontFamily: "monospace", fontWeight: 700, color: col as string }}>{v}</div>
              </div>
            ))}
          </div>
          {/* Strength bar */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.58rem", color: "var(--text-muted)", marginBottom: 3 }}>
              <span>Strength</span><span>{fvg.strength}/100</span>
            </div>
            <Bar v={fvg.strength} color={c} h={5} />
          </div>
          {/* Fill progress */}
          {fvg.fill_pct > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.58rem", color: "var(--text-muted)", marginBottom: 3 }}>
                <span>Fill Progress</span><span>{fvg.fill_pct.toFixed(0)}%</span>
              </div>
              <Bar v={fvg.fill_pct} color="#f59e0b" h={4} />
            </div>
          )}
          {/* Entry zone */}
          {fvg.entry_zone && fvg.status !== "FILLED" && (
            <EntryCard ez={fvg.entry_zone} direction={dir as "BUY" | "SELL"} price={price} />
          )}
        </div>
      )}
    </div>
  );
}

function BreakerCard({ bb, price, expanded, onToggle }: { bb: BreakerBlock; price: number; expanded: boolean; onToggle: () => void }) {
  const c = FG[bb.type];
  const dir = bb.type === "BULLISH_BREAKER" ? "BUY" : "SELL";
  const dist = ((price - bb.midpoint) / price * 100).toFixed(2);
  return (
    <div style={{ borderRadius: 12, background: `${c}07`, border: `1px solid ${c}22`, overflow: "hidden", marginBottom: 8 }}>
      <div onClick={onToggle} style={{ padding: "12px 14px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
          <span style={{ fontFamily: "monospace", fontWeight: 900, fontSize: "0.72rem", color: c }}>
            {bb.midpoint.toLocaleString("en",{maximumFractionDigits:2})}
          </span>
          <Badge label={bb.type.replace("_", " ")} color={c} />
          <Badge label={bb.status} color={bb.status === "ACTIVE" ? "#f59e0b" : "#64748b"} />
          {bb.has_returned && <Badge label={`TESTED x${bb.test_count}`} color="#3b82f6" />}
          <Badge label={`${bb.break_direction} ${bb.break_strength}xATR`} color="#94a3b8" size="xs" />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.7rem", fontWeight: 900, color: c }}>{bb.strength}</div>
            <div style={{ fontSize: "0.52rem", color: "var(--text-muted)" }}>{Number(dist) > 0 ? "+" : ""}{dist}%</div>
          </div>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: `${c}15`, display: "flex", alignItems: "center", justifyContent: "center", color: c, fontSize: "0.7rem" }}>
            {expanded ? "▲" : "▼"}
          </div>
        </div>
      </div>
      {expanded && (
        <div style={{ padding: "0 14px 14px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 6, marginBottom: 10 }}>
            {[
              ["Zone High", bb.ob_high.toLocaleString("en",{maximumFractionDigits:2}), "#ef4444"],
              ["OTE Entry", bb.ote_entry.toLocaleString("en",{maximumFractionDigits:2}), c],
              ["Zone Low",  bb.ob_low.toLocaleString("en",{maximumFractionDigits:2}), "#10b981"],
              ["Break Str", `${bb.break_strength}x`, "#f59e0b"],
            ].map(([l,v,col]) => (
              <div key={l as string} style={{ padding:"7px 8px", borderRadius:7, background:"rgba(255,255,255,0.02)", textAlign:"center" }}>
                <div style={{ fontSize:"0.48rem", color:"var(--text-muted)", textTransform:"uppercase", marginBottom:2 }}>{l}</div>
                <div style={{ fontSize:"0.68rem", fontFamily:"monospace", fontWeight:700, color:col as string }}>{v}</div>
              </div>
            ))}
          </div>
          <div style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.58rem", color: "var(--text-muted)", marginBottom: 3 }}>
              <span>Strength</span><span>{bb.strength}/100</span>
            </div>
            <Bar v={bb.strength} color={c} h={5} />
          </div>
          {bb.entry_zone && (
            <EntryCard ez={bb.entry_zone} direction={dir as "BUY" | "SELL"} price={price} />
          )}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Main Panel
───────────────────────────────────────────────────────── */
interface FVGBreakerPanelProps {
  symbol?: string;
  timeframe?: string;
  autoLoad?: boolean;
  onSetWAAlert?: (data: any) => void;
}

export function FVGBreakerPanel({ symbol, timeframe, autoLoad = true, onSetWAAlert }: FVGBreakerPanelProps = {}) {
  const [sym,   setSym]    = useState(symbol || "BTCUSDT");
  const [tf,    setTf]     = useState(timeframe || "1h");

  // Sync with global selector
  useEffect(() => { if (symbol) setSym(symbol); }, [symbol]);
  useEffect(() => { if (timeframe) setTf(timeframe); }, [timeframe]);
  const [data,  setData]   = useState<FVGResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [view,  setView]   = useState<"fvg" | "breaker" | "stacks" | "rb">("fvg");
  const [filter, setFilter] = useState<"ALL" | "BULLISH" | "BEARISH">("ALL");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const startRef = useRef<number>(0);
  const [scanMs, setScanMs] = useState(0);

  const toggle = useCallback((key: string) =>
    setExpanded(prev => ({ ...prev, [key]: !prev[key] })), []);

  const scan = useCallback(async () => {
    setLoading(true); startRef.current = Date.now();
    try {
      const r = await fetch(`${API_URL}/api/v1/pro/fvg-breaker`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym, timeframe: tf, limit: 150 }),
      });
      setData(await r.json());
      setScanMs(Date.now() - startRef.current);
    } catch {}
    finally { setLoading(false); }
  }, [sym, tf]);

  // Auto-scan when symbol/TF changes (debounced so typing doesn't spam API)
  useEffect(() => {
    if (!autoLoad || sym.length < 5) return;
    const t = setTimeout(() => { scan(); }, 600);
    return () => clearTimeout(t);
  }, [scan, autoLoad, sym, tf]);

  const biasC: Record<string, string> = { STRONG_BUY:"#10b981", BUY:"#34d399", SELL:"#f87171", STRONG_SELL:"#ef4444", NEUTRAL:"#64748b" };
  const gradeC: Record<string, string> = { "A+":"#10b981", A:"#34d399", B:"#3b82f6", C:"#f59e0b", D:"#f97316", WAIT:"#64748b" };

  const fvgsToShow = data ? [
    ...(filter !== "BEARISH" ? data.bullish_fvgs : []),
    ...(filter !== "BULLISH" ? data.bearish_fvgs : []),
  ].filter(f => f.status !== "FILLED").sort((a,b) => b.strength - a.strength) : [];

  const breakersToShow = data ? [
    ...(filter !== "BEARISH" ? data.bullish_breakers : []),
    ...(filter !== "BULLISH" ? data.bearish_breakers : []),
  ].sort((a,b) => b.strength - a.strength) : [];

  return (
    <div>
      {/* ── Toolbar ── */}
      <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:20, flexWrap:"wrap" }}>
        <input value={sym} onChange={e => setSym(e.target.value.toUpperCase())}
          style={{ background:"rgba(255,255,255,0.05)", border:"1px solid rgba(255,255,255,0.08)", borderRadius:8, padding:"8px 12px", color:"#fff", fontSize:"0.8rem", width:120, fontFamily:"monospace", fontWeight:700 }} />
        <select value={tf} onChange={e => setTf(e.target.value)}
          style={{ background:"rgba(255,255,255,0.05)", border:"1px solid rgba(255,255,255,0.08)", borderRadius:8, padding:"8px 12px", color:"#fff", fontSize:"0.8rem" }}>
          {["5m","15m","1h","4h","1d"].map(t => <option key={t}>{t}</option>)}
        </select>
        <button onClick={scan} disabled={loading} style={{ padding:"8px 20px", borderRadius:8, background:"rgba(99,102,241,0.15)", border:"1px solid rgba(99,102,241,0.35)", color:"#6366f1", fontWeight:800, fontSize:"0.78rem", cursor:"pointer", display:"flex", alignItems:"center", gap:6 }}>
          {loading ? <><span style={{ display:"inline-block", animation:"spin .9s linear infinite" }}>⟳</span> Scanning...</> : "Scan FVG + Breakers"}
        </button>
        {scanMs > 0 && <span style={{ fontSize:"0.62rem", color:"var(--text-muted)" }}>{scanMs}ms</span>}
        {/* WA Alert Button — shows when data has a valid entry zone */}
        {(() => {
          if (!onSetWAAlert || !data) return null;
          const bias = data.signals?.entry_bias;
          let entry = null;
          if (bias?.includes("BUY")) entry = data.nearest?.bullish_fvg?.entry_zone;
          else if (bias?.includes("SELL")) entry = data.nearest?.bearish_fvg?.entry_zone;
          
          if (!entry) return null;

          return (
            <button
              onClick={() => {
                onSetWAAlert({ symbol: sym, score: data.signals?.confluence_score, grade: data.ict_setup?.grade, entry, bias });
              }}
              style={{ padding:"8px 16px", borderRadius:8, background:"rgba(16,185,129,0.12)", border:"1px solid rgba(16,185,129,0.3)", color:"#10b981", fontWeight:800, fontSize:"0.75rem", cursor:"pointer", display:"flex", alignItems:"center", gap:6 }}
            >
              📱 Set WA Alert
            </button>
          );
        })()}

        {/* Filter */}
        <div style={{ marginLeft:"auto", display:"flex", gap:4 }}>
          {(["ALL","BULLISH","BEARISH"] as const).map(f => {
            const fc = f === "BULLISH" ? "#10b981" : f === "BEARISH" ? "#ef4444" : "#6366f1";
            return (
              <button key={f} onClick={() => setFilter(f)} style={{ padding:"6px 12px", borderRadius:7, fontSize:"0.7rem", fontWeight:700, cursor:"pointer",
                background: filter === f ? `${fc}15` : "rgba(255,255,255,0.03)",
                border:`1px solid ${filter === f ? `${fc}40` : "rgba(255,255,255,0.06)"}`,
                color: filter === f ? fc : "var(--text-muted)" }}>
                {f}
              </button>
            );
          })}
        </div>
      </div>

      {!data ? (
        <div style={{ textAlign:"center", padding:"80px 0" }}>
          <div style={{ fontSize:"4rem", marginBottom:16, opacity:0.12 }}>⬜</div>
          <div style={{ fontWeight:800, fontSize:"0.95rem", marginBottom:8 }}>FVG + Breaker Block Scanner</div>
          <div style={{ fontSize:"0.75rem", color:"var(--text-muted)", maxWidth:480, margin:"0 auto" }}>
            Deteksi Fair Value Gap, Inversion FVG, FVG Stacks, Breaker Blocks, dan Rejection Blocks secara otomatis dengan entry zone dan RR calculator.
          </div>
        </div>
      ) : (
        <div style={{ display:"flex", flexDirection:"column", gap:16 }}>

          {/* ── ICT Setup + Bias ── */}
          <div style={{ display:"grid", gridTemplateColumns:"auto 1fr", gap:16 }}>
            {/* Grade Ring */}
            <div style={{ padding:"16px 20px", borderRadius:16, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.06)", display:"flex", alignItems:"center", gap:16 }}>
              <GradeRing grade={data.ict_setup.grade} score={data.ict_setup.total} />
              <div>
                <div style={{ fontSize:"0.62rem", color:"var(--text-muted)", textTransform:"uppercase", fontWeight:700, marginBottom:4 }}>ICT Setup Score</div>
                <div style={{ fontSize:"0.95rem", fontWeight:900, color:gradeC[data.ict_setup.grade] ?? "#64748b", marginBottom:4 }}>{data.ict_setup.description}</div>
                <div style={{ display:"flex", flexWrap:"wrap", gap:6 }}>
                  {data.ict_setup.has_fvg && <Badge label="FVG" color="#6366f1" size="xs" />}
                  {data.ict_setup.has_breaker && <Badge label="BREAKER" color="#f59e0b" size="xs" />}
                  {data.ict_setup.has_displacement && <Badge label="DISPLACEMENT" color="#10b981" size="xs" />}
                </div>
              </div>
            </div>

            {/* Component breakdown */}
            <div style={{ padding:"16px 20px", borderRadius:16, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.06)" }}>
              <div style={{ fontSize:"0.62rem", color:"var(--text-muted)", textTransform:"uppercase", fontWeight:700, marginBottom:10 }}>Score Components</div>
              <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
                {Object.entries(data.ict_setup.components).map(([k,v]) => (
                  <div key={k} style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <div style={{ fontSize:"0.62rem", color:"var(--text-muted)", width:110, flexShrink:0 }}>{k}</div>
                    <div style={{ flex:1 }}><Bar v={v} max={25} color={v >= 15 ? "#10b981" : v >= 8 ? "#f59e0b" : "#ef4444"} h={5} /></div>
                    <div style={{ fontSize:"0.6rem", fontFamily:"monospace", width:28, textAlign:"right", color:v >= 15 ? "#10b981" : v >= 8 ? "#f59e0b" : "#ef4444" }}>{v.toFixed(0)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Summary Stats ── */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(6,1fr)", gap:8 }}>
            {[
              { label:"Total FVGs", val:data.summary.total_fvgs, sub:"active", color:"#6366f1" },
              { label:"Fresh",      val:data.summary.fresh_fvgs, sub:"untested", color:"#10b981" },
              { label:"Inverted",   val:data.summary.inverted_fvgs, sub:"IFVG", color:"#a78bfa" },
              { label:"Inst. FVG",  val:data.summary.institutional_fvgs, sub:">1.5x ATR", color:"#6366f1" },
              { label:"Breakers",   val:data.summary.total_breakers, sub:"blocks", color:"#f59e0b" },
              { label:"Stacks",     val:data.summary.stacked_zones, sub:"overlapping", color:"#f97316" },
            ].map(({ label, val, sub, color }) => (
              <div key={label} style={{ padding:"12px 14px", borderRadius:12, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.05)", textAlign:"center" }}>
                <div style={{ fontSize:"0.52rem", color:"var(--text-muted)", textTransform:"uppercase", marginBottom:5 }}>{label}</div>
                <div style={{ fontSize:"1.5rem", fontWeight:900, color, lineHeight:1 }}>{val}</div>
                <div style={{ fontSize:"0.55rem", color:"var(--text-muted)", marginTop:3 }}>{sub}</div>
              </div>
            ))}
          </div>

          {/* ── Entry Bias ── */}
          <div style={{ padding:"14px 18px", borderRadius:12, background:`${biasC[data.signals.entry_bias] ?? "#64748b"}10`, border:`1px solid ${biasC[data.signals.entry_bias] ?? "#64748b"}30`, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
            <div>
              <div style={{ fontSize:"0.6rem", color:"var(--text-muted)", fontWeight:700, textTransform:"uppercase", marginBottom:4 }}>Entry Bias · ATR {data.atr?.toFixed(2)}</div>
              <div style={{ fontSize:"1.2rem", fontWeight:900, color:biasC[data.signals.entry_bias] ?? "#64748b" }}>{data.signals.entry_bias.replace("_"," ")}</div>
            </div>
            <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
              <Badge label={data.signals.fvg_signal.replace(/_/g," ")} color="#6366f1" />
              <Badge label={data.signals.breaker_signal.replace(/_/g," ")} color="#f59e0b" />
              <Badge label={`Confluence ${data.signals.confluence_score}/10`} color={data.signals.confluence_score >= 6 ? "#10b981" : "#f59e0b"} />
            </div>
          </div>

          {/* ── Signal Messages ── */}
          {data.signals.messages.length > 0 && (
            <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
              {data.signals.messages.map((m,i) => (
                <div key={i} style={{ fontSize:"0.75rem", padding:"9px 14px", background:"rgba(255,255,255,0.02)", borderRadius:9, border:"1px solid rgba(255,255,255,0.05)", lineHeight:1.5 }}>{m}</div>
              ))}
              {data.signals.warnings.map((w,i) => (
                <div key={`w${i}`} style={{ fontSize:"0.73rem", padding:"9px 14px", background:"rgba(245,158,11,0.06)", borderRadius:9, border:"1px solid rgba(245,158,11,0.2)", color:"#f59e0b", lineHeight:1.5 }}>{w}</div>
              ))}
            </div>
          )}

          {/* ── Nearest Key Levels ── */}
          {(data.nearest.bullish_fvg || data.nearest.bearish_fvg || data.nearest.breaker) && (
            <div style={{ padding:"14px 16px", borderRadius:14, background:"rgba(99,102,241,0.05)", border:"1px solid rgba(99,102,241,0.18)" }}>
              <div style={{ fontWeight:800, fontSize:"0.78rem", color:"#6366f1", marginBottom:10 }}>Nearest Key Levels to Price</div>
              <div style={{ display:"flex", gap:10, flexWrap:"wrap" }}>
                {data.nearest.bullish_fvg && (() => {
                  const f = data.nearest.bullish_fvg!;
                  const d = ((data.current_price - f.gap_high) / data.current_price * 100).toFixed(2);
                  return (
                    <div style={{ flex:1, minWidth:160, padding:"10px 12px", borderRadius:10, background:"rgba(16,185,129,0.07)", border:"1px solid rgba(16,185,129,0.2)" }}>
                      <div style={{ fontSize:"0.6rem", color:"#10b981", fontWeight:700, marginBottom:4 }}>Nearest Bullish FVG</div>
                      <div style={{ fontFamily:"monospace", fontSize:"0.78rem", fontWeight:700 }}>CE: {f.ce_level.toLocaleString("en",{maximumFractionDigits:2})}</div>
                      <div style={{ fontSize:"0.6rem", color:"var(--text-muted)", marginTop:2 }}>{f.gap_low.toLocaleString("en",{maximumFractionDigits:2})} – {f.gap_high.toLocaleString("en",{maximumFractionDigits:2})}</div>
                      <div style={{ fontSize:"0.6rem", color:"#10b981", marginTop:2 }}>{d}% below · str {f.strength}</div>
                    </div>
                  );
                })()}
                {data.nearest.bearish_fvg && (() => {
                  const f = data.nearest.bearish_fvg!;
                  const d = ((f.gap_low - data.current_price) / data.current_price * 100).toFixed(2);
                  return (
                    <div style={{ flex:1, minWidth:160, padding:"10px 12px", borderRadius:10, background:"rgba(239,68,68,0.07)", border:"1px solid rgba(239,68,68,0.2)" }}>
                      <div style={{ fontSize:"0.6rem", color:"#ef4444", fontWeight:700, marginBottom:4 }}>Nearest Bearish FVG</div>
                      <div style={{ fontFamily:"monospace", fontSize:"0.78rem", fontWeight:700 }}>CE: {f.ce_level.toLocaleString("en",{maximumFractionDigits:2})}</div>
                      <div style={{ fontSize:"0.6rem", color:"var(--text-muted)", marginTop:2 }}>{f.gap_low.toLocaleString("en",{maximumFractionDigits:2})} – {f.gap_high.toLocaleString("en",{maximumFractionDigits:2})}</div>
                      <div style={{ fontSize:"0.6rem", color:"#ef4444", marginTop:2 }}>{d}% above · str {f.strength}</div>
                    </div>
                  );
                })()}
                {data.nearest.breaker && (() => {
                  const b = data.nearest.breaker!;
                  const c = FG[b.type];
                  const d = ((data.current_price - b.midpoint) / data.current_price * 100).toFixed(2);
                  return (
                    <div style={{ flex:1, minWidth:160, padding:"10px 12px", borderRadius:10, background:`${c}08`, border:`1px solid ${c}25` }}>
                      <div style={{ fontSize:"0.6rem", color:c, fontWeight:700, marginBottom:4 }}>Nearest Breaker</div>
                      <div style={{ fontFamily:"monospace", fontSize:"0.78rem", fontWeight:700 }}>{b.midpoint.toLocaleString("en",{maximumFractionDigits:2})}</div>
                      <div style={{ fontSize:"0.6rem", color:"var(--text-muted)", marginTop:2 }}>{b.type.replace("_BREAKER"," Breaker")}</div>
                      <div style={{ fontSize:"0.6rem", color:c, marginTop:2 }}>{Number(d) > 0 ? "+" : ""}{d}% · {b.status}</div>
                    </div>
                  );
                })()}
              </div>
            </div>
          )}

          {/* ── Tab Navigation ── */}
          <div style={{ display:"flex", gap:4, padding:5, borderRadius:12, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.04)", width:"fit-content" }}>
            {([
              ["fvg",     `FVGs (${fvgsToShow.length})`,       "#6366f1"],
              ["breaker", `Breakers (${breakersToShow.length})`, "#f59e0b"],
              ["stacks",  `Stacks (${data.fvg_stacks.length})`, "#f97316"],
              ["rb",      `Rejection (${data.rejection_blocks.length})`, "#a78bfa"],
            ] as const).map(([v, label, c]) => (
              <button key={v} onClick={() => setView(v as any)} style={{
                padding:"7px 14px", borderRadius:8, fontWeight:700, fontSize:"0.75rem", cursor:"pointer",
                background: view === v ? `${c}15` : "transparent",
                border:`1px solid ${view === v ? `${c}40` : "transparent"}`,
                color: view === v ? c : "var(--text-muted)",
                whiteSpace:"nowrap",
              }}>{label}</button>
            ))}
          </div>

          {/* ── FVG List ── */}
          {view === "fvg" && (
            <div>
              {fvgsToShow.length === 0 ? (
                <div style={{ textAlign:"center", padding:"30px 0", color:"var(--text-muted)", fontSize:"0.8rem" }}>No active FVGs found for the selected filter</div>
              ) : fvgsToShow.map(f => (
                <FVGCard key={`${f.type}-${f.id}`} fvg={f} price={data.current_price}
                  expanded={!!expanded[`fvg-${f.id}`]}
                  onToggle={() => toggle(`fvg-${f.id}`)} />
              ))}
            </div>
          )}

          {/* ── Breaker List ── */}
          {view === "breaker" && (
            <div>
              {breakersToShow.length === 0 ? (
                <div style={{ textAlign:"center", padding:"30px 0", color:"var(--text-muted)", fontSize:"0.8rem" }}>No breaker blocks detected</div>
              ) : breakersToShow.map(b => (
                <BreakerCard key={`${b.type}-${b.id}`} bb={b} price={data.current_price}
                  expanded={!!expanded[`bb-${b.id}`]}
                  onToggle={() => toggle(`bb-${b.id}`)} />
              ))}
            </div>
          )}

          {/* ── Stacks ── */}
          {view === "stacks" && (
            <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
              {data.fvg_stacks.length === 0 ? (
                <div style={{ textAlign:"center", padding:"30px 0", color:"var(--text-muted)", fontSize:"0.8rem" }}>No FVG stacks detected — no overlapping FVGs</div>
              ) : data.fvg_stacks.map((s, i) => {
                const isBull = s.types.filter(t => t === "BULLISH").length >= s.types.length / 2;
                const c = isBull ? "#10b981" : "#ef4444";
                return (
                  <div key={i} style={{ padding:"14px 16px", borderRadius:12, background:`${c}08`, border:`1px solid ${c}25` }}>
                    <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10 }}>
                      <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                        <Badge label={`STACK x${s.count}`} color="#f97316" />
                        {s.types.map((t,j) => <Badge key={j} label={t === "BULLISH" ? "BULL" : "BEAR"} color={FG[t]} size="xs" />)}
                      </div>
                      <div style={{ fontSize:"0.7rem", fontWeight:900, color:"#f97316" }}>str {s.strength}</div>
                    </div>
                    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:8 }}>
                      <div style={{ padding:"7px 10px", borderRadius:8, background:"rgba(255,255,255,0.02)", textAlign:"center" }}>
                        <div style={{ fontSize:"0.52rem", color:"var(--text-muted)", marginBottom:2 }}>ZONE HIGH</div>
                        <div style={{ fontSize:"0.72rem", fontFamily:"monospace", fontWeight:700, color:"#ef4444" }}>{s.zone_high.toLocaleString("en",{maximumFractionDigits:2})}</div>
                      </div>
                      <div style={{ padding:"7px 10px", borderRadius:8, background:"rgba(255,255,255,0.02)", textAlign:"center" }}>
                        <div style={{ fontSize:"0.52rem", color:"var(--text-muted)", marginBottom:2 }}>SIZE</div>
                        <div style={{ fontSize:"0.72rem", fontFamily:"monospace", fontWeight:700 }}>{(s.zone_high - s.zone_low).toFixed(2)}</div>
                      </div>
                      <div style={{ padding:"7px 10px", borderRadius:8, background:"rgba(255,255,255,0.02)", textAlign:"center" }}>
                        <div style={{ fontSize:"0.52rem", color:"var(--text-muted)", marginBottom:2 }}>ZONE LOW</div>
                        <div style={{ fontSize:"0.72rem", fontFamily:"monospace", fontWeight:700, color:"#10b981" }}>{s.zone_low.toLocaleString("en",{maximumFractionDigits:2})}</div>
                      </div>
                    </div>
                    <div style={{ marginTop:8 }}>
                      <Bar v={s.strength} color="#f97316" h={4} />
                    </div>
                    <div style={{ fontSize:"0.65rem", color:"var(--text-muted)", marginTop:6 }}>
                      FVG Stack = multiple imbalances overlapping — strongest possible magnet zone for price
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── Rejection Blocks ── */}
          {view === "rb" && (
            <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
              {data.rejection_blocks.length === 0 ? (
                <div style={{ textAlign:"center", padding:"30px 0", color:"var(--text-muted)", fontSize:"0.8rem" }}>No rejection blocks detected</div>
              ) : data.rejection_blocks.map((r, i) => {
                const isBull = r.type === "BULLISH_RB";
                const c = isBull ? "#10b981" : "#ef4444";
                const dist = ((data.current_price - r.zone_low) / data.current_price * 100).toFixed(2);
                return (
                  <div key={i} style={{ padding:"12px 14px", borderRadius:11, background:`${c}07`, border:`1px solid ${c}22`, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
                    <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                      <Badge label={r.type.replace("_RB"," RB")} color={c} />
                      <div style={{ fontFamily:"monospace", fontSize:"0.72rem" }}>
                        {r.zone_low.toLocaleString("en",{maximumFractionDigits:2})} – {r.zone_high.toLocaleString("en",{maximumFractionDigits:2})}
                      </div>
                      <Badge label={`Wick ${r.wick_pct.toFixed(0)}%`} color="#94a3b8" size="xs" />
                    </div>
                    <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                      <div style={{ fontSize:"0.62rem", color:"var(--text-muted)" }}>{Number(dist)>0?"+":""}{dist}%</div>
                      <div style={{ fontSize:"0.7rem", fontWeight:900, color:c }}>{r.strength}</div>
                      <div style={{ width:50 }}><Bar v={r.strength} color={c} h={4} /></div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <style>{`@keyframes spin { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }`}</style>
    </div>
  );
}
