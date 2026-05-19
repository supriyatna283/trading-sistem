"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function SetupsPage() {
  const [setups, setSetups] = useState<any[]>([]);
  const [allSymbols, setAllSymbols] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [filter, setFilter] = useState<"ALL" | "ACTIVE" | "TRIGGERED" | "EXPIRED">("ALL");
  const [generatingSymbol, setGeneratingSymbol] = useState("");
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null);
  const [minScore, setMinScore] = useState(0);

  useEffect(() => {
    const init = async () => {
      await Promise.all([fetchSetups(), fetchSchedulerStatus(), fetchSymbols()]);
    };
    init();
    const timer = setInterval(() => { fetchSetups(); fetchSchedulerStatus(); }, 60000);
    return () => clearInterval(timer);
  }, []);

  const fetchSymbols = async () => {
    try { const res = await api.getSymbols(); setAllSymbols(Array.isArray(res?.symbols) ? res.symbols : []); } catch (_) {}
  };

  const fetchSetups = async () => {
    setIsLoading(true);
    try { const res = await api.getSetups(); setSetups(Array.isArray(res?.setups) ? res.setups : []); }
    catch (err) { console.error(err); } finally { setIsLoading(false); }
  };

  const fetchSchedulerStatus = async () => {
    try { const res = await api.getSchedulerStatus(); setSchedulerStatus(res?.scheduler || null); } catch (_) {}
  };

  const forceSchedulerRun = async () => {
    setGenerating(true); setGeneratingSymbol("auto-scanner...");
    try { await api.triggerScheduler(); await fetchSetups(); await fetchSchedulerStatus(); }
    catch (err) { console.error(err); } finally { setGenerating(false); setGeneratingSymbol(""); }
  };

  const generateAllSignals = async () => {
    setGenerating(true);
    try { setGeneratingSymbol("scanning markets..."); await api.generateAllSetups("1h"); await fetchSetups(); }
    catch (err) { console.error(err); } finally { setGenerating(false); setGeneratingSymbol(""); }
  };

  const byStatus = filter === "ALL" ? setups : setups.filter(s => s.status === filter);
  const filtered = minScore > 0 ? byStatus.filter(s => (s.signal_score ?? 0) >= minScore) : byStatus;

  const SCORE_PRESETS = [
    { label: "ALL", value: 0, color: "#94a3b8" },
    { label: "50+", value: 50, color: "#60a5fa" },
    { label: "65+", value: 65, color: "#10b981" },
    { label: "80+", value: 80, color: "#f59e0b" },
  ];

  const fmt = (p: number) => {
    if (!p && p !== 0) return "–";
    return p > 10 ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : p.toFixed(4);
  };

  const timeAgo = (d: string) => {
    if (!d) return "";
    const m = Math.floor((Date.now() - new Date(d).getTime()) / 60000);
    if (m < 1) return "just now"; if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  };

  // ── Gauge component for BB / Stoch RSI ──────────────────────────────
  function Gauge({ value, min = 0, max = 100, label, color }: any) {
    const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
    return (
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontSize: "0.6rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
          <span style={{ fontSize: "0.65rem", fontWeight: 800, color, fontFamily: "'JetBrains Mono', monospace" }}>{value?.toFixed(1) ?? "–"}</span>
        </div>
        <div style={{ height: 4, borderRadius: 99, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 99, transition: "width 0.6s ease" }} />
        </div>
      </div>
    );
  }

  function BBPosition({ upper, middle, lower, close }: any) {
    if (!upper || !lower || !close) return null;
    const range = upper - lower;
    const pct = range > 0 ? ((close - lower) / range) * 100 : 50;
    const zone = pct <= 25 ? { label: "LOWER BAND", color: "#10b981" }
      : pct >= 75 ? { label: "UPPER BAND", color: "#ef4444" }
      : { label: "MID BAND", color: "#f59e0b" };
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ flex: 1, height: 6, borderRadius: 99, background: "rgba(255,255,255,0.06)", position: "relative" }}>
          <div style={{ position: "absolute", top: 0, left: `calc(${Math.min(98, Math.max(2, pct))}% - 4px)`, width: 8, height: 8, borderRadius: "50%", background: zone.color, marginTop: -1, boxShadow: `0 0 6px ${zone.color}` }} />
        </div>
        <span style={{ fontSize: "0.6rem", fontWeight: 800, color: zone.color, whiteSpace: "nowrap" }}>{zone.label}</span>
      </div>
    );
  }

  function ScoreRing({ score }: { score: number }) {
    const color = score >= 80 ? "#f59e0b" : score >= 65 ? "#10b981" : score >= 50 ? "#3b82f6" : "#ef4444";
    const grade = score >= 80 ? "A+" : score >= 65 ? "A" : score >= 50 ? "B" : "C";
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", width: 60, height: 60, borderRadius: "50%", border: `3px solid ${color}`, boxShadow: `0 0 16px ${color}30`, position: "relative" }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "1rem", fontWeight: 900, color }}>{score}</span>
        <span style={{ fontSize: "0.5rem", fontWeight: 800, color: "var(--text-muted)", letterSpacing: "0.08em" }}>{grade}</span>
      </div>
    );
  }

  return (
    <MainLayout>
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse-dot { 0%,100%{opacity:1;} 50%{opacity:0.4;} }
        .setup-card:hover { transform: translateY(-2px); box-shadow: 0 16px 40px rgba(0,0,0,0.3); }
        .setup-card { transition: transform 0.2s, box-shadow 0.2s; }
      `}} />

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
            <span style={{ fontSize: "0.7rem", fontWeight: 800, letterSpacing: "0.14em", color: "#f59e0b", textTransform: "uppercase" }}>⚡ INTRADAY ENGINE</span>
          </div>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 900, letterSpacing: "-0.04em", margin: 0, background: "linear-gradient(135deg, #fff 40%, #94a3b8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Signal Dashboard
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", margin: "6px 0 0" }}>
            BB · Stoch RSI · SMC · Multi-TF Confluence — {allSymbols.length} pairs monitored
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn-primary" onClick={generateAllSignals} disabled={generating}
            style={{ opacity: generating ? 0.7 : 1, display: "flex", alignItems: "center", gap: 8, padding: "10px 18px", fontWeight: 700, fontSize: "0.82rem" }}>
            {generating
              ? <><span style={{ width: 13, height: 13, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.8s linear infinite", display: "inline-block" }} />Scanning {generatingSymbol}</>
              : "⚡ Scan Markets"}
          </button>
          <button onClick={forceSchedulerRun} disabled={generating}
            style={{ padding: "10px 16px", borderRadius: 10, border: "1px solid rgba(139,92,246,0.3)", background: "rgba(139,92,246,0.08)", color: "#a78bfa", cursor: "pointer", fontWeight: 700, fontSize: "0.78rem", opacity: generating ? 0.5 : 1 }}>
            🤖 Auto
          </button>
          <button onClick={async () => { if (!confirm("Delete ALL setups?")) return; try { await api.clearAllSetups(); fetchSetups(); } catch (e: any) { alert(e.message); } }}
            style={{ padding: "10px 16px", borderRadius: 10, border: "1px solid rgba(239,68,68,0.25)", background: "rgba(239,68,68,0.05)", color: "#f87171", cursor: "pointer", fontWeight: 700, fontSize: "0.78rem" }}>
            🗑
          </button>
        </div>
      </div>

      {/* Scheduler Banner */}
      {schedulerStatus && (
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap", padding: "12px 18px", marginBottom: 20, borderRadius: 12, background: "rgba(16,185,129,0.04)", border: "1px solid rgba(16,185,129,0.12)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 8px #10b981", animation: "pulse-dot 2s infinite" }} />
            <span style={{ fontWeight: 800, fontSize: "0.78rem", color: "#10b981", letterSpacing: "0.05em" }}>ENGINE LIVE</span>
          </div>
          {schedulerStatus.last_run && <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Last: <strong style={{ color: "#fff" }}>{new Date(schedulerStatus.last_run).toLocaleTimeString()}</strong></span>}
          {schedulerStatus.next_run && <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Next: <strong style={{ color: "#60a5fa" }}>{new Date(schedulerStatus.next_run).toLocaleTimeString()}</strong></span>}
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Generated: <strong style={{ color: "#10b981" }}>{schedulerStatus.last_generated ?? 0}</strong></span>
        </div>
      )}

      {/* Signal Score Filter */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: "0.72rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", whiteSpace: "nowrap" }}>
          🎯 Signal Score
        </span>
        {SCORE_PRESETS.map(p => {
          const isActive = minScore === p.value;
          const count = p.value === 0
            ? setups.length
            : setups.filter(s => (s.signal_score ?? 0) >= p.value).length;
          return (
            <button key={p.label} onClick={() => setMinScore(p.value)} style={{
              padding: "5px 14px",
              borderRadius: 8,
              border: isActive ? `1px solid ${p.color}60` : "1px solid var(--border)",
              background: isActive ? `${p.color}18` : "transparent",
              color: isActive ? p.color : "var(--text-muted)",
              fontWeight: 800,
              fontSize: "0.78rem",
              cursor: "pointer",
              transition: "all 0.15s",
              display: "flex",
              alignItems: "center",
              gap: 5,
            }}>
              {p.label}
              <span style={{ opacity: 0.65, fontSize: "0.7rem", fontWeight: 600 }}>{count}</span>
            </button>
          );
        })}
        {minScore > 0 && (
          <div style={{ marginLeft: 4, padding: "3px 10px", borderRadius: 6, background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.25)", fontSize: "0.7rem", color: "#f59e0b", fontWeight: 700 }}>
            ≥ {minScore} pts
          </div>
        )}
      </div>

      {/* Status Filter Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {(["ALL", "ACTIVE", "TRIGGERED", "EXPIRED"] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            background: filter === f ? "rgba(59,130,246,0.12)" : "transparent",
            border: filter === f ? "1px solid rgba(59,130,246,0.35)" : "1px solid var(--border)",
            color: filter === f ? "#60a5fa" : "var(--text-muted)",
            padding: "6px 16px", borderRadius: 8, fontSize: "0.8rem", fontWeight: 700, cursor: "pointer",
          }}>
            {f}{f !== "ALL" && <span style={{ opacity: 0.5, marginLeft: 5 }}>{setups.filter(s => s.status === f).length}</span>}
          </button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: "0.75rem", color: "var(--text-muted)", alignSelf: "center" }}>
          {filtered.length} signals
        </span>
      </div>

      {/* Loading */}
      {isLoading && (
        <div style={{ padding: 60, textAlign: "center", color: "var(--text-muted)" }}>
          <div style={{ width: 28, height: 28, border: "3px solid var(--border)", borderTopColor: "#3b82f6", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 14px" }} />
          Synchronizing…
        </div>
      )}

      {/* Empty */}
      {!isLoading && filtered.length === 0 && (
        <div className="glass-card" style={{ padding: 70, textAlign: "center", border: "1px dashed var(--border)" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: 16 }}>📡</div>
          <h3 style={{ fontWeight: 800, marginBottom: 8 }}>No Signals Detected</h3>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: 20, maxWidth: 400, margin: "0 auto 20px" }}>
            Engine is monitoring {allSymbols.length} pairs. No high-probability intraday setups found.
          </p>
          <button className="btn-primary" onClick={generateAllSignals} disabled={generating} style={{ padding: "11px 22px", fontWeight: 700 }}>
            ⚡ Force Deep Scan
          </button>
        </div>
      )}

      {/* Cards Grid */}
      {!isLoading && filtered.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 20 }}>
          {filtered.map((s: any, i: number) => {
            const isBuy = s.direction === "BUY";
            const accentColor = isBuy ? "#22c55e" : "#ef4444";
            const accentBg = isBuy ? "rgba(34,197,94,0.05)" : "rgba(239,68,68,0.05)";
            const details = s.confluence_details || {};
            const bb = details.bollinger_bands || {};
            const stoch = details.stoch_rsi || {};
            const rsi = details.rsi || {};
            const macd = details.macd || {};

            return (
              <div key={s.id || i} className="glass-card setup-card" style={{ padding: 0, overflow: "hidden", border: `1px solid rgba(255,255,255,0.06)` }}>

                {/* Card Header */}
                <div style={{ padding: "16px 20px", background: accentBg, borderBottom: "1px solid rgba(255,255,255,0.05)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontWeight: 900, fontSize: "1.1rem", letterSpacing: "-0.02em" }}>{s.symbol}</span>
                    <span style={{ padding: "3px 10px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 900, background: isBuy ? "rgba(34,197,94,0.18)" : "rgba(239,68,68,0.18)", color: accentColor, border: `1px solid ${accentColor}40` }}>
                      {isBuy ? "▲ LONG" : "▼ SHORT"}
                    </span>
                    <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-muted)", background: "rgba(255,255,255,0.05)", padding: "3px 8px", borderRadius: 6 }}>{s.timeframe}</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>{timeAgo(s.created_at)}</span>
                    <span style={{ fontSize: "0.65rem", fontWeight: 800, padding: "3px 8px", borderRadius: 6, background: s.status === "ACTIVE" ? "rgba(16,185,129,0.12)" : "rgba(255,255,255,0.05)", color: s.status === "ACTIVE" ? "#10b981" : "var(--text-muted)" }}>{s.status}</span>
                    <button onClick={async () => { if (!confirm(`Delete ${s.symbol}?`)) return; await api.deleteSetup(s.id); fetchSetups(); }}
                      style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "rgba(239,68,68,0.08)", color: "#f87171", cursor: "pointer", fontSize: "0.7rem" }}>✕</button>
                  </div>
                </div>

                <div style={{ padding: "18px 20px" }}>
                  {/* Score + Levels */}
                  <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 18 }}>
                    <ScoreRing score={s.signal_score ?? 0} />
                    <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                      {[
                        { label: "Entry", value: `${fmt(s.entry_low)}–${fmt(s.entry_high)}`, color: "#fff" },
                        { label: "Stop Loss", value: fmt(s.stop_loss), color: "#f87171" },
                        { label: "R:R", value: `1:${(s.risk_reward ?? 0).toFixed(1)}`, color: "#60a5fa" },
                      ].map(item => (
                        <div key={item.label}>
                          <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 3 }}>{item.label}</div>
                          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, fontSize: "0.8rem", color: item.color }}>{item.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Take Profits */}
                  <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
                    {[s.take_profit_1, s.take_profit_2, s.take_profit_3].map((tp, idx) => tp ? (
                      <div key={idx} style={{ flex: 1, background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.15)", borderRadius: 8, padding: "7px 10px", textAlign: "center" }}>
                        <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", fontWeight: 800, marginBottom: 2 }}>TP{idx + 1}</div>
                        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.78rem", color: "#10b981", fontWeight: 700 }}>{fmt(tp)}</div>
                      </div>
                    ) : null)}
                  </div>

                  {/* ── Intraday Indicator Panel ─────────────────── */}
                  <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 12, padding: "14px 16px", marginBottom: 14 }}>
                    <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 12 }}>Intraday Indicators</div>

                    {/* BB Position */}
                    <div style={{ marginBottom: 10 }}>
                      <div style={{ fontSize: "0.6rem", fontWeight: 700, color: "var(--text-muted)", marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
                        <span>Bollinger Bands (20,2)</span>
                        {bb.bandwidth_pct != null && <span style={{ color: bb.bandwidth_pct < 5 ? "#f59e0b" : "var(--text-muted)" }}>{bb.bandwidth_pct < 5 ? "🔴 SQUEEZE" : `BW ${bb.bandwidth_pct}%`}</span>}
                      </div>
                      <BBPosition upper={bb.upper} middle={bb.middle} lower={bb.lower} close={s.entry_low} />
                      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: "0.55rem", fontFamily: "'JetBrains Mono', monospace", color: "var(--text-muted)" }}>
                        <span>L: {fmt(bb.lower)}</span>
                        <span>M: {fmt(bb.middle)}</span>
                        <span>U: {fmt(bb.upper)}</span>
                      </div>
                    </div>

                    {/* Stoch RSI */}
                    <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
                      <Gauge value={stoch.k} label="Stoch %K" color={stoch.k < 20 ? "#10b981" : stoch.k > 80 ? "#ef4444" : "#f59e0b"} />
                      <Gauge value={stoch.d} label="Stoch %D" color="#94a3b8" />
                    </div>

                    {/* RSI + MACD mini row */}
                    <div style={{ display: "flex", gap: 10 }}>
                      <Gauge value={rsi.value} label="RSI (14)" color={rsi.value < 30 ? "#10b981" : rsi.value > 70 ? "#ef4444" : "#60a5fa"} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: "0.6rem", fontWeight: 700, color: "var(--text-muted)", marginBottom: 4 }}>MACD Hist</div>
                        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.7rem", fontWeight: 800, color: macd.hist > 0 ? "#10b981" : "#ef4444" }}>
                          {macd.hist != null ? (macd.hist > 0 ? "▲" : "▼") + " " + Math.abs(macd.hist).toExponential(2) : "–"}
                        </div>
                      </div>
                    </div>
                  </div>

                   {/* ── Tier 1 Institutional Indicators ────────── */}
                  {(() => {
                    const vwap = details.vwap || {};
                    const vp = details.volume_profile || {};
                    const div = details.divergence || {};
                    const hasAny = vwap.value || vp.poc || div.type !== "none";
                    if (!hasAny) return null;
                    return (
                      <div style={{ background: "rgba(139,92,246,0.04)", border: "1px solid rgba(139,92,246,0.12)", borderRadius: 12, padding: "14px 16px", marginBottom: 14 }}>
                        <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "#a78bfa", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 12 }}>
                          🏛 Institutional Indicators
                        </div>

                        {/* VWAP */}
                        {vwap.value && (
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                            <div>
                              <div style={{ fontSize: "0.6rem", fontWeight: 800, color: "var(--text-muted)", marginBottom: 2 }}>VWAP</div>
                              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.78rem", fontWeight: 700, color: "#fff" }}>
                                {fmt(vwap.value)}
                              </div>
                            </div>
                            <div style={{ textAlign: "right" }}>
                              <div style={{
                                padding: "3px 10px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 800,
                                background: vwap.position === "above" ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)",
                                color: vwap.position === "above" ? "#10b981" : "#ef4444",
                                border: `1px solid ${vwap.position === "above" ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)"}`,
                              }}>
                                {vwap.position === "above" ? "▲ ABOVE" : "▼ BELOW"} VWAP
                              </div>
                              {vwap.distance_pct != null && (
                                <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginTop: 3 }}>{vwap.distance_pct}% away</div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Volume Profile */}
                        {vp.poc && (
                          <div style={{ marginBottom: 8 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                              <span style={{ fontSize: "0.6rem", fontWeight: 800, color: "var(--text-muted)" }}>VOLUME PROFILE</span>
                              <span style={{
                                fontSize: "0.65rem", fontWeight: 800, padding: "2px 8px", borderRadius: 4,
                                background: vp.in_value_area ? "rgba(245,158,11,0.15)" : "transparent",
                                color: vp.in_value_area ? "#f59e0b" : "var(--text-muted)",
                              }}>
                                {vp.in_value_area ? "✓ IN VALUE AREA" : `${vp.poc_distance_pct}% from POC`}
                              </span>
                            </div>
                            <div style={{ display: "flex", gap: 8 }}>
                              {[
                                { label: "VAH", value: vp.vah, color: "#ef4444" },
                                { label: "POC", value: vp.poc, color: "#f59e0b" },
                                { label: "VAL", value: vp.val, color: "#10b981" },
                              ].map(item => (
                                <div key={item.label} style={{ flex: 1, textAlign: "center", background: "rgba(255,255,255,0.03)", borderRadius: 6, padding: "5px 0" }}>
                                  <div style={{ fontSize: "0.55rem", color: item.color, fontWeight: 800, marginBottom: 2 }}>{item.label}</div>
                                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.68rem", color: "#fff", fontWeight: 700 }}>{fmt(item.value)}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Divergence */}
                        {div.type && div.type !== "none" && (
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <div style={{
                              flex: 1, padding: "8px 12px", borderRadius: 8,
                              background: div.type === "bullish" ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
                              border: `1px solid ${div.type === "bullish" ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}`,
                            }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                <div>
                                  <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", fontWeight: 800, textTransform: "uppercase", marginBottom: 2 }}>
                                    {div.rsi_divergence && div.macd_divergence ? "RSI + MACD" : div.rsi_divergence ? "RSI" : "MACD"} Divergence
                                  </div>
                                  <div style={{ fontSize: "0.72rem", fontWeight: 800, color: div.type === "bullish" ? "#10b981" : "#ef4444" }}>
                                    {div.type === "bullish" ? "▲ BULLISH" : "▼ BEARISH"} DIV
                                  </div>
                                </div>
                                {div.strength > 0 && (
                                  <div style={{ fontSize: "0.65rem", fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, color: "var(--text-muted)" }}>
                                    str: {div.strength}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}

                  {/* Setup Explanation */}
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.55, background: "rgba(59,130,246,0.04)", padding: "10px 14px", borderRadius: 10, borderLeft: `3px solid ${accentColor}60`, marginBottom: 16 }}>
                    <strong style={{ color: "#fff", display: "block", marginBottom: 3, fontSize: "0.72rem" }}>{s.setup_type}</strong>
                    {s.explanation}
                  </div>

                  {/* Actions */}
                  <div style={{ display: "flex", gap: 8 }}>
                    {s.status === "ACTIVE" && (
                      <>
                        <button onClick={async () => { if (!confirm(`Execute ${s.symbol}?`)) return; try { await api.executeFromSetup(s.id); fetchSetups(); } catch (e: any) { alert(e.message); } }}
                          style={{ flex: 2, padding: "10px", borderRadius: 10, border: "none", background: `linear-gradient(135deg, ${accentColor}cc, ${accentColor})`, color: "#fff", fontSize: "0.78rem", fontWeight: 800, cursor: "pointer" }}>
                          ⚡ Execute
                        </button>
                        <button onClick={() => api.updateSetupStatus(s.id, "TRIGGERED").then(fetchSetups)}
                          style={{ flex: 1, padding: "10px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.04)", color: "var(--text-primary)", fontSize: "0.75rem", fontWeight: 700, cursor: "pointer" }}>
                          Triggered
                        </button>
                      </>
                    )}
                    {s.status === "TRIGGERED" && (
                      <div style={{ display: "flex", gap: 6, width: "100%" }}>
                        {[["WIN","#10b981"],["LOSS","#ef4444"],["BE","#94a3b8"]].map(([r, c]) => (
                          <button key={r} onClick={() => api.logSetupToJournal(s.id, { result: r }).then(fetchSetups)}
                            style={{ flex: 1, padding: "9px", borderRadius: 9, background: `${c}18`, border: `1px solid ${c}40`, color: c, fontWeight: 800, fontSize: "0.75rem", cursor: "pointer" }}>{r}</button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </MainLayout>
  );
}
