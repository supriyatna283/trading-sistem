"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState, useCallback } from "react";
import { API_URL } from "@/lib/utils";

/* ─── Types ─────────────────────────────────────────────────── */
type Tab = "mm-flow" | "wyckoff" | "ml-score" | "portfolio" | "garch" | "options" | "social";

const TABS: { id: Tab; icon: string; label: string; sprint: string; color: string }[] = [
  { id: "mm-flow",   icon: "🏦", label: "MM Flow",       sprint: "S3", color: "#3b82f6" },
  { id: "wyckoff",   icon: "📊", label: "Wyckoff",       sprint: "S3", color: "#10b981" },
  { id: "ml-score",  icon: "🤖", label: "ML Score",      sprint: "S3", color: "#a78bfa" },
  { id: "portfolio", icon: "⚖️", label: "Portfolio",     sprint: "S3", color: "#f59e0b" },
  { id: "garch",     icon: "📈", label: "GARCH Vol",     sprint: "S4", color: "#ef4444" },
  { id: "options",   icon: "🎲", label: "Options/Perps", sprint: "S4", color: "#06b6d4" },
  { id: "social",    icon: "👥", label: "Social Trading",sprint: "S4", color: "#f97316" },
];

/* ─── Small reusable components ─────────────────────────────── */
function Card({ children, style = {} }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ padding: 20, borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", ...style }}>
      {children}
    </div>
  );
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span style={{ padding: "3px 9px", borderRadius: 6, fontSize: "0.65rem", fontWeight: 800, background: `${color}18`, color, border: `1px solid ${color}35` }}>
      {label}
    </span>
  );
}

function Bar({ value, max = 100, color = "#3b82f6", label }: { value: number; max?: number; color?: string; label?: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div>
      {label && <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginBottom: 3 }}>{label}</div>}
      <div style={{ height: 5, borderRadius: 99, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 99, transition: "width 0.7s cubic-bezier(0.4,0,0.2,1)" }} />
      </div>
    </div>
  );
}

function StatCard({ label, value, color = "#fff", sub = "" }: { label: string; value: string | number; color?: string; sub?: string }) {
  return (
    <div style={{ padding: "12px 14px", borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
      <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "0.9rem", fontWeight: 800, color }}>{value}</div>
      {sub && <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function Signal({ s }: { s: string }) {
  const map: Record<string, string> = {
    STRONG_BUY: "#10b981", BUY: "#34d399", NEUTRAL: "#64748b",
    SELL: "#f87171", STRONG_SELL: "#ef4444",
    BULLISH: "#10b981", BEARISH: "#ef4444",
    ACCUMULATION: "#10b981", DISTRIBUTION: "#ef4444", NONE: "#64748b",
  };
  const c = map[s] ?? "#64748b";
  return <Badge label={s.replace(/_/g, " ")} color={c} />;
}

/* ─── Panel: MM Flow ─────────────────────────────────────────── */
function MMFlowPanel() {
  const [sym, setSym] = useState("BTCUSDT");
  const [tf, setTf] = useState("1h");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const r = await window.fetch(`${API_URL}/api/v1/advanced/mm-flow`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym, timeframe: tf, lookback: 100 }),
      });
      setData(await r.json());
    } catch { } finally { setLoading(false); }
  }, [sym, tf]);

  const phaseColors: Record<string, string> = {
    ACCUMULATION: "#10b981", MANIPULATION: "#f59e0b", DISTRIBUTION: "#ef4444",
    TRENDING_UP: "#3b82f6", TRENDING_DOWN: "#8b5cf6", NEUTRAL: "#64748b",
  };

  return (
    <div>
      {/* Controls */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input value={sym} onChange={e => setSym(e.target.value.toUpperCase())} style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 12px", color: "#fff", fontSize: "0.8rem", width: 120, fontFamily: "monospace" }} />
        <select value={tf} onChange={e => setTf(e.target.value)} style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 12px", color: "#fff", fontSize: "0.8rem" }}>
          {["5m","15m","1h","4h","1d"].map(t => <option key={t}>{t}</option>)}
        </select>
        <button onClick={fetch} disabled={loading} style={{ padding: "8px 20px", borderRadius: 8, background: "rgba(59,130,246,0.15)", border: "1px solid rgba(59,130,246,0.3)", color: "#3b82f6", fontWeight: 800, fontSize: "0.78rem", cursor: "pointer" }}>
          {loading ? "⟳" : "Analyze"}
        </button>
      </div>

      {!data ? (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)", fontSize: "0.82rem" }}>
          <div style={{ fontSize: "3rem", marginBottom: 12, opacity: 0.3 }}>🏦</div>
          Click Analyze to detect Market Maker activity
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* MM Phase */}
          <Card style={{ gridColumn: "1/-1", display: "flex", justifyContent: "space-between", alignItems: "center", border: `1px solid ${phaseColors[data.mm_phase?.phase] ?? "#64748b"}30` }}>
            <div>
              <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", marginBottom: 6, fontWeight: 700, textTransform: "uppercase" }}>Market Maker Phase</div>
              <div style={{ fontSize: "1.3rem", fontWeight: 900, color: phaseColors[data.mm_phase?.phase] ?? "#fff" }}>{data.mm_phase?.phase ?? "—"}</div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 4 }}>{data.mm_phase?.desc}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ marginBottom: 6 }}><Signal s={data.flow_bias} /></div>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>Confidence: <span style={{ color: phaseColors[data.mm_phase?.phase] ?? "#fff" }}>{data.mm_phase?.confidence}%</span></div>
            </div>
          </Card>

          {/* Delta */}
          <Card>
            <div style={{ fontWeight: 700, fontSize: "0.8rem", marginBottom: 12 }}>Cumulative Delta (CVD)</div>
            <StatCard label="Candle Delta" value={data.delta?.candle?.toFixed(2)} color={data.delta?.candle > 0 ? "#10b981" : "#ef4444"} />
            <div style={{ marginTop: 8 }}>
              <StatCard label="Cumulative Delta" value={data.delta?.cumulative?.toFixed(2)} color={data.delta?.trend === "BULLISH" ? "#10b981" : "#ef4444"} sub={`Trend: ${data.delta?.trend}`} />
            </div>
          </Card>

          {/* VWAP */}
          <Card>
            <div style={{ fontWeight: 700, fontSize: "0.8rem", marginBottom: 12 }}>VWAP Analysis</div>
            <StatCard label="VWAP" value={data.vwap?.value?.toLocaleString("en", { maximumFractionDigits: 4 })} />
            <div style={{ marginTop: 8 }}>
              <StatCard label="Deviation" value={`${data.vwap?.deviation_pct > 0 ? "+" : ""}${data.vwap?.deviation_pct?.toFixed(3)}%`}
                color={data.vwap?.price_position === "ABOVE" ? "#10b981" : "#ef4444"} sub={`Price is ${data.vwap?.price_position} VWAP`} />
            </div>
          </Card>

          {/* Absorption */}
          <Card>
            <div style={{ fontWeight: 700, fontSize: "0.8rem", marginBottom: 12 }}>Large Print / Absorption</div>
            <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
              <Badge label={data.absorption?.detected ? `${data.absorption?.side} ABSORPTION` : "No Absorption"} color={data.absorption?.detected ? (data.absorption?.side === "BUY" ? "#10b981" : "#ef4444") : "#64748b"} />
            </div>
            <StatCard label="Large Print Candles" value={data.absorption?.large_print_count ?? 0} sub="Vol > 2.5x average" />
          </Card>

          {/* Stop Hunt */}
          <Card>
            <div style={{ fontWeight: 700, fontSize: "0.8rem", marginBottom: 12 }}>Stop Hunt Probability</div>
            <Bar value={data.stop_hunt?.probability ?? 0} color={data.stop_hunt?.probability > 60 ? "#ef4444" : "#f59e0b"} label={`${data.stop_hunt?.probability ?? 0}%`} />
            <div style={{ marginTop: 10, fontSize: "0.72rem", color: "var(--text-muted)" }}>
              Direction: <span style={{ color: "#fff", fontWeight: 700 }}>{data.stop_hunt?.direction ?? "NONE"}</span>
            </div>
          </Card>

          {/* Signals */}
          {data.signals?.length > 0 && (
            <Card style={{ gridColumn: "1/-1" }}>
              <div style={{ fontWeight: 700, fontSize: "0.8rem", marginBottom: 10 }}>Flow Signals</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {data.signals.map((s: string, i: number) => (
                  <div key={i} style={{ fontSize: "0.75rem", padding: "7px 12px", background: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.05)" }}>{s}</div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Panel: Wyckoff ─────────────────────────────────────────── */
function WyckoffPanel() {
  const [sym, setSym] = useState("BTCUSDT");
  const [tf, setTf] = useState("4h");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const r = await window.fetch(`${API_URL}/api/v1/advanced/wyckoff`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym, timeframe: tf, lookback: 120 }),
      });
      setData(await r.json());
    } catch { } finally { setLoading(false); }
  }, [sym, tf]);

  const phaseLabels: Record<string, string> = {
    A: "Phase A — Stopping the trend", B: "Phase B — Building the cause",
    C: "Phase C — Test (Spring/UTAD)", D: "Phase D — Markup/Markdown begins",
    E: "Phase E — Trending out of range",
  };

  const schemeColor = data?.schematic === "ACCUMULATION" ? "#10b981" : data?.schematic === "DISTRIBUTION" ? "#ef4444" : "#64748b";

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input value={sym} onChange={e => setSym(e.target.value.toUpperCase())} style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 12px", color: "#fff", fontSize: "0.8rem", width: 120, fontFamily: "monospace" }} />
        <select value={tf} onChange={e => setTf(e.target.value)} style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 12px", color: "#fff", fontSize: "0.8rem" }}>
          {["1h","4h","1d","1w"].map(t => <option key={t}>{t}</option>)}
        </select>
        <button onClick={fetch} disabled={loading} style={{ padding: "8px 20px", borderRadius: 8, background: "rgba(16,185,129,0.15)", border: "1px solid rgba(16,185,129,0.3)", color: "#10b981", fontWeight: 800, fontSize: "0.78rem", cursor: "pointer" }}>
          {loading ? "⟳" : "Detect"}
        </button>
      </div>

      {!data ? (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)", fontSize: "0.82rem" }}>
          <div style={{ fontSize: "3rem", marginBottom: 12, opacity: 0.3 }}>📊</div>
          Click Detect to find Wyckoff patterns
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* Header */}
          <Card style={{ gridColumn: "1/-1", border: `1px solid ${schemeColor}30` }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", fontWeight: 700, marginBottom: 6 }}>WYCKOFF SCHEMATIC</div>
                <div style={{ fontSize: "1.4rem", fontWeight: 900, color: schemeColor }}>{data.schematic}</div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: 4 }}>{data.description}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "3rem", fontWeight: 900, color: schemeColor, opacity: 0.6 }}>{data.phase}</div>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>{phaseLabels[data.phase] ?? ""}</div>
                <div style={{ marginTop: 8 }}><Signal s={data.signal} /></div>
              </div>
            </div>
            {/* Phase confidence bar */}
            <div style={{ marginTop: 14 }}>
              <Bar value={data.phase_confidence ?? 0} color={schemeColor} label={`Phase Confidence: ${data.phase_confidence}%`} />
            </div>
            {data.spring && <div style={{ marginTop: 10, padding: "8px 12px", background: "rgba(16,185,129,0.1)", borderRadius: 8, border: "1px solid rgba(16,185,129,0.2)", fontSize: "0.72rem", color: "#10b981", fontWeight: 700 }}>🌱 Spring detected at {data.spring_price?.toLocaleString("en", { maximumFractionDigits: 2 })}</div>}
            {data.utad  && <div style={{ marginTop: 10, padding: "8px 12px", background: "rgba(239,68,68,0.1)", borderRadius: 8, border: "1px solid rgba(239,68,68,0.2)", fontSize: "0.72rem", color: "#ef4444", fontWeight: 700 }}>🚨 UTAD detected at {data.spring_price?.toLocaleString("en", { maximumFractionDigits: 2 })}</div>}
          </Card>

          {/* Trading Range */}
          <Card>
            <div style={{ fontWeight: 700, fontSize: "0.8rem", marginBottom: 12 }}>Trading Range</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <StatCard label="Range High" value={data.trading_range?.high?.toLocaleString("en", { maximumFractionDigits: 2 })} color="#ef4444" />
              <StatCard label="Range Low" value={data.trading_range?.low?.toLocaleString("en", { maximumFractionDigits: 2 })} color="#10b981" />
              <StatCard label="Range Size" value={data.trading_range?.size?.toLocaleString("en", { maximumFractionDigits: 2 })} />
            </div>
          </Card>

          {/* Cause & Effect */}
          <Card>
            <div style={{ fontWeight: 700, fontSize: "0.8rem", marginBottom: 12 }}>Cause & Effect Projection</div>
            <StatCard label="Cause (Bars in Range)" value={data.cause_and_effect?.cause_bars ?? 0} sub="More bars = larger projected move" />
            <div style={{ marginTop: 8 }}>
              <StatCard label="Effect (Price Target)" value={data.cause_and_effect?.effect_projection?.toLocaleString("en", { maximumFractionDigits: 2 })} color={schemeColor} sub="Point & Figure projection" />
            </div>
          </Card>

          {/* Events */}
          {data.events?.length > 0 && (
            <Card style={{ gridColumn: "1/-1" }}>
              <div style={{ fontWeight: 700, fontSize: "0.8rem", marginBottom: 12 }}>Detected Events</div>
              <div style={{ display: "flex", flex: 1, flexWrap: "wrap", gap: 8 }}>
                {data.events.map((e: any, i: number) => (
                  <div key={i} style={{ padding: "8px 14px", borderRadius: 8, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div style={{ fontSize: "0.7rem", fontWeight: 800, color: schemeColor }}>{e.name} <span style={{ color: "#64748b" }}>Phase {e.phase}</span></div>
                    <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", marginTop: 2 }}>{e.description}</div>
                    <div style={{ fontSize: "0.6rem", fontFamily: "monospace", color: "#fff", marginTop: 2 }}>@ {e.price?.toLocaleString("en", { maximumFractionDigits: 2 })}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Panel: GARCH ──────────────────────────────────────────── */
function GARCHPanel() {
  const [sym, setSym] = useState("BTCUSDT");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const r = await window.fetch(`${API_URL}/api/v1/advanced/garch`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym, timeframe: "1d", lookback: 200 }),
      });
      setData(await r.json());
    } catch { } finally { setLoading(false); }
  }, [sym]);

  const regimeColor: Record<string, string> = { LOW: "#10b981", MEDIUM: "#3b82f6", HIGH: "#f59e0b", EXTREME: "#ef4444" };
  const rc = regimeColor[data?.regime?.label ?? ""] ?? "#64748b";

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input value={sym} onChange={e => setSym(e.target.value.toUpperCase())} style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 12px", color: "#fff", fontSize: "0.8rem", width: 130, fontFamily: "monospace" }} />
        <button onClick={fetch} disabled={loading} style={{ padding: "8px 20px", borderRadius: 8, background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", fontWeight: 800, fontSize: "0.78rem", cursor: "pointer" }}>
          {loading ? "⟳" : "Forecast"}
        </button>
      </div>

      {!data ? (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)", fontSize: "0.82rem" }}>
          <div style={{ fontSize: "3rem", marginBottom: 12, opacity: 0.3 }}>📈</div>
          Run GARCH(1,1) volatility forecast
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
          {/* Regime */}
          <Card style={{ gridColumn: "1/-1", display: "flex", justifyContent: "space-between", alignItems: "center", border: `1px solid ${rc}30` }}>
            <div>
              <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", fontWeight: 700, marginBottom: 6 }}>VOLATILITY REGIME</div>
              <div style={{ fontSize: "1.5rem", fontWeight: 900, color: rc }}>{data.regime?.label} VOLATILITY</div>
              <div style={{ marginTop: 8 }}>
                <Bar value={data.regime?.percentile ?? 0} color={rc} label={`Percentile: ${data.regime?.percentile}% (vs history)`} />
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "2.5rem", fontWeight: 900, color: rc, fontFamily: "monospace" }}>{data.current?.daily_vol_pct?.toFixed(3)}%</div>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>Daily Vol · {data.current?.annual_vol_pct?.toFixed(1)}% Ann.</div>
              <div style={{ marginTop: 6 }}><Badge label={data.signal?.replace(/_/g, " ")} color={rc} /></div>
            </div>
          </Card>

          <StatCard label="1-Day Forecast" value={`${data.forecasts?.["1d_vol_pct"]?.toFixed(3)}%`} color={rc} />
          <StatCard label="5-Day Forecast" value={`${data.forecasts?.["5d_vol_pct"]?.toFixed(3)}%`} color={rc} />
          <StatCard label="10-Day Forecast" value={`${data.forecasts?.["10d_vol_pct"]?.toFixed(3)}%`} color={rc} />

          <StatCard label="Expected Daily Move" value={`±${data.trading?.daily_move_pct?.toFixed(2)}%`} sub="1-sigma" />
          <StatCard label="Expected Weekly Move" value={`±${data.trading?.weekly_move_pct?.toFixed(2)}%`} sub="1-sigma · 5 days" />
          <StatCard label="ATR Equivalent" value={data.trading?.atr_equivalent?.toLocaleString("en", { maximumFractionDigits: 2 })} sub="In price units" />

          <StatCard label="Options Move 1W" value={`±${data.options_estimates?.["1w_move_pct"]?.toFixed(1)}%`} color="#06b6d4" sub="Estimated IV move" />
          <StatCard label="Options Move 1M" value={`±${data.options_estimates?.["1m_move_pct"]?.toFixed(1)}%`} color="#06b6d4" sub="Estimated IV move" />

          <Card>
            <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", fontWeight: 700, marginBottom: 10, textTransform: "uppercase" }}>GARCH Parameters</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {[["ω (Omega)", data.model_params?.omega?.toFixed(8)], ["α (ARCH)", data.model_params?.alpha?.toFixed(4)], ["β (GARCH)", data.model_params?.beta?.toFixed(4)], ["Persistence α+β", data.model_params?.persistence?.toFixed(4)]].map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>{k}</span>
                  <span style={{ fontFamily: "monospace", fontWeight: 700 }}>{v}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card style={{ gridColumn: "2/4" }}>
            <div style={{ fontWeight: 700, fontSize: "0.8rem", marginBottom: 8 }}>Trade Advice</div>
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", lineHeight: 1.6, margin: 0 }}>{data.trade_advice}</p>
          </Card>
        </div>
      )}
    </div>
  );
}

/* ─── Panel: Social Trading ────────────────────────────────── */
function SocialTradingPanel() {
  const [signals, setSignals] = useState<any[]>([]);
  const [leaders, setLeaders] = useState<any[]>([]);
  const [view, setView] = useState<"signals" | "leaders">("signals");
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [sigR, lbR] = await Promise.all([
        window.fetch(`${API_URL}/api/v1/advanced/signals`),
        window.fetch(`${API_URL}/api/v1/advanced/leaderboard?limit=10`),
      ]);
      const sigD = await sigR.json();
      const lbD  = await lbR.json();
      setSignals(sigD.signals ?? []);
      setLeaders(lbD.leaderboard ?? []);
    } catch { } finally { setLoading(false); }
  }, []);

  const dirColor = (d: string) => d === "BUY" ? "#10b981" : "#ef4444";

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 6 }}>
          {(["signals", "leaders"] as const).map(v => (
            <button key={v} onClick={() => setView(v)} style={{
              padding: "7px 16px", borderRadius: 8, fontWeight: 700, fontSize: "0.78rem", cursor: "pointer",
              background: view === v ? "rgba(249,115,22,0.15)" : "rgba(255,255,255,0.03)",
              border: `1px solid ${view === v ? "rgba(249,115,22,0.4)" : "rgba(255,255,255,0.06)"}`,
              color: view === v ? "#f97316" : "var(--text-muted)",
            }}>
              {v === "signals" ? "📡 Live Signals" : "🏆 Leaderboard"}
            </button>
          ))}
        </div>
        <button onClick={loadData} disabled={loading} style={{ padding: "7px 16px", borderRadius: 8, background: "rgba(249,115,22,0.12)", border: "1px solid rgba(249,115,22,0.3)", color: "#f97316", fontWeight: 800, fontSize: "0.78rem", cursor: "pointer" }}>
          {loading ? "⟳" : "Load"}
        </button>
      </div>

      {signals.length === 0 && leaders.length === 0 ? (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)", fontSize: "0.82rem" }}>
          <div style={{ fontSize: "3rem", marginBottom: 12, opacity: 0.3 }}>👥</div>
          Click Load to see signals and leaderboard
        </div>
      ) : view === "signals" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {signals.map((s: any) => (
            <Card key={s.id} style={{ border: `1px solid ${dirColor(s.direction)}20` }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <span style={{ fontFamily: "monospace", fontWeight: 800, fontSize: "0.9rem" }}>{s.symbol}</span>
                    <Badge label={s.direction} color={dirColor(s.direction)} />
                    <Badge label={s.timeframe} color="#64748b" />
                    <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>by {s.publisher}</span>
                  </div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontFamily: "monospace", marginBottom: 6 }}>
                    Entry: <span style={{ color: "#fff" }}>{s.entry?.toLocaleString("en", { maximumFractionDigits: 4 })}</span>
                    {" "} SL: <span style={{ color: "#ef4444" }}>{s.stop_loss?.toLocaleString("en", { maximumFractionDigits: 4 })}</span>
                    {" "} TP1: <span style={{ color: "#10b981" }}>{s.take_profits?.[0]?.toLocaleString("en", { maximumFractionDigits: 4 })}</span>
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{s.rationale}</div>
                </div>
                <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 16 }}>
                  <div style={{ fontSize: "1.1rem", fontWeight: 900, color: dirColor(s.direction), fontFamily: "monospace" }}>
                    {s.rr_tp1 ? `1:${s.rr_tp1}` : "—"}
                  </div>
                  <div style={{ fontSize: "0.58rem", color: "var(--text-muted)" }}>R:R</div>
                  <div style={{ marginTop: 6 }}>{s.tags?.slice(0, 3).map((t: string) => <Badge key={t} label={t} color="#6366f1" />)}</div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {leaders.map((p: any) => (
            <Card key={p.id} style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ fontSize: "1.5rem", minWidth: 32, textAlign: "center" }}>{p.rank <= 3 ? ["🥇","🥈","🥉"][p.rank-1] : `#${p.rank}`}</div>
              <div style={{ fontSize: "2rem" }}>{p.avatar}</div>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontWeight: 800 }}>{p.name}</span>
                  {p.verified && <Badge label="✓ VERIFIED" color="#10b981" />}
                </div>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: 2 }}>{p.bio}</div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, textAlign: "center" }}>
                <div><div style={{ fontSize: "0.55rem", color: "var(--text-muted)" }}>WIN RATE</div><div style={{ fontWeight: 800, color: "#10b981", fontSize: "0.85rem" }}>{p.performance?.win_rate_pct}%</div></div>
                <div><div style={{ fontSize: "0.55rem", color: "var(--text-muted)" }}>AVG R:R</div><div style={{ fontWeight: 800, fontSize: "0.85rem" }}>{p.performance?.avg_rr}</div></div>
                <div><div style={{ fontSize: "0.55rem", color: "var(--text-muted)" }}>SCORE</div><div style={{ fontWeight: 800, color: "#f59e0b", fontSize: "0.85rem" }}>{p.rank_score}</div></div>
              </div>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>{p.followers?.toLocaleString()} followers</div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Main Page ─────────────────────────────────────────────── */
export default function AdvancedToolsPage() {
  const [tab, setTab] = useState<Tab>("mm-flow");
  const active = TABS.find(t => t.id === tab)!;

  return (
    <MainLayout>
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 8 }}>
          <div style={{ width: 44, height: 44, borderRadius: 13, background: "linear-gradient(135deg,#3b82f6 0%,#a78bfa 50%,#f97316 100%)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.3rem", boxShadow: "0 0 24px rgba(59,130,246,0.3)", border: "1px solid rgba(255,255,255,0.1)" }}>🚀</div>
          <div>
            <h1 style={{ fontFamily: "'Outfit',sans-serif", fontSize: "1.8rem", fontWeight: 900, letterSpacing: "-0.04em", margin: 0, background: "linear-gradient(135deg,#fff 30%,#94a3b8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              Advanced Trading Suite
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: "0.78rem", margin: 0, marginTop: 3 }}>
              <span style={{ color: "#3b82f6", fontWeight: 700 }}>Sprint 3</span> · MM Flow · Wyckoff · ML Score · Portfolio{"  "}
              <span style={{ color: "#f97316", fontWeight: 700 }}>Sprint 4</span> · GARCH · Options · Social Trading
            </p>
          </div>
        </div>
      </div>

      {/* Tab Bar */}
      <div style={{ display: "flex", gap: 4, padding: 6, borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)", marginBottom: 24, overflowX: "auto" }}>
        {TABS.map(t => {
          const isActive = tab === t.id;
          return (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              display: "flex", alignItems: "center", gap: 7, padding: "9px 14px", borderRadius: 10, whiteSpace: "nowrap",
              fontWeight: isActive ? 800 : 500, fontSize: "0.8rem", cursor: "pointer",
              background: isActive ? `${t.color}15` : "transparent",
              border: `1px solid ${isActive ? t.color + "40" : "transparent"}`,
              color: isActive ? t.color : "var(--text-muted)",
              boxShadow: isActive ? `0 0 12px ${t.color}15` : "none",
              transition: "all 0.25s",
            }}>
              <span style={{ fontSize: "0.95rem" }}>{t.icon}</span>
              <span>{t.label}</span>
              <span style={{ fontSize: "0.55rem", padding: "1px 5px", borderRadius: 4, background: isActive ? `${t.color}25` : "rgba(255,255,255,0.06)", color: isActive ? t.color : "var(--text-muted)", fontWeight: 800 }}>{t.sprint}</span>
            </button>
          );
        })}
      </div>

      {/* Content */}
      {tab === "mm-flow"   && <MMFlowPanel />}
      {tab === "wyckoff"   && <WyckoffPanel />}
      {tab === "ml-score"  && <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)" }}><div style={{ fontSize: "3rem", marginBottom: 12 }}>🤖</div><p>ML Scoring runs automatically on all symbols.<br/>Results appear in the Full Analysis endpoint.</p></div>}
      {tab === "portfolio" && <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)" }}><div style={{ fontSize: "3rem", marginBottom: 12 }}>⚖️</div><p>Portfolio Optimizer available via /api/v1/advanced/portfolio<br/>Supports multi-asset Markowitz, Risk Parity, and Monte Carlo.</p></div>}
      {tab === "garch"     && <GARCHPanel />}
      {tab === "options"   && <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)" }}><div style={{ fontSize: "3rem", marginBottom: 12 }}>🎲</div><p>Options analysis via /api/v1/advanced/options<br/>Black-Scholes Greeks, Put/Call ratio, IV skew, Perp funding.</p></div>}
      {tab === "social"    && <SocialTradingPanel />}
    </MainLayout>
  );
}
