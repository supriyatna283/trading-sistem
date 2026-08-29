"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { formatPrice, timeAgo } from "@/lib/utils";
import { Gauge, ScoreRing } from "@/components/setups/SetupComponents";
import toast from "react-hot-toast";

// Helper for live time ago (instead of TimeAgo component from page to avoid circular deps, or just define it here)
function TimeAgo({ date }: { date: string }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTick(t => t + 1), 60000);
    return () => clearInterval(timer);
  }, []);
  return <span>{timeAgo(date)}</span>;
}

function getStarRating(score: number) {
  if (score >= 85) return <span title="High Probability (S-Tier)">🌟🌟🌟</span>;
  if (score >= 70) return <span title="Solid Setup (A-Tier)">🌟🌟</span>;
  return <span title="Risky (B-Tier)">🌟</span>;
}

export default function SetupCard({
  s, i, expandedIds, toggleExpand, executingId, handleExecute, setConfirmAction, fetchSetups, router
}: any) {
  const [activeTab, setActiveTab] = useState<"overview" | "indicators" | "institutional">("overview");

  const score = s.signal_score ?? s.confluence_score ?? 0;
  const isBuy = s.direction === "BUY";
  const accentColor = isBuy ? "#22c55e" : "#ef4444";
  const accentBg = isBuy ? "rgba(34,197,94,0.05)" : "rgba(239,68,68,0.05)";
  const details = s.confluence_details || {};
  const fib = details.fibonacci || {};
  const rsi = details.rsi || {};
  const macd = details.macd || {};
  const isExpanded = expandedIds.has(s.id || i);
  const isExecuting = executingId === s.id;

  const handleCopySignal = async () => {
    const text = `${isBuy ? "LONG" : "SHORT"} ${s.symbol} (${s.timeframe})
Entry: ${s.entry_low} - ${s.entry_high}
SL: ${s.stop_loss}
TP1: ${s.take_profit_1 || "-"} | TP2: ${s.take_profit_2 || "-"} | TP3: ${s.take_profit_3 || "-"}
R:R: 1:${(s.risk_reward ?? 0).toFixed(1)}
Score: ${score}/100`;

    try {
      await navigator.clipboard.writeText(text);
      toast.success("Signal copied to clipboard!");
    } catch (err) {
      toast.error("Failed to copy signal");
    }
  };

  return (
    <div className="glass-card setup-card" style={{ padding: 0, overflow: "hidden", border: `1px solid rgba(255,255,255,0.06)` }}>
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
          <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>
            <TimeAgo date={s.created_at} />
          </span>
          <span style={{ fontSize: "0.65rem", fontWeight: 800, padding: "3px 8px", borderRadius: 6, background: s.status === "ACTIVE" ? "rgba(16,185,129,0.12)" : "rgba(255,255,255,0.05)", color: s.status === "ACTIVE" ? "#10b981" : "var(--text-muted)" }}>
            {s.status}
          </span>
          <Link 
            href={`/charts?symbol=${s.symbol}&tf=${s.timeframe}&ai=true`}
            style={{ 
              background: "rgba(167,139,250,0.15)", color: "#a78bfa",
              border: "1px solid rgba(167,139,250,0.3)", borderRadius: 6,
              padding: "3px 8px", fontSize: "0.6rem", fontWeight: 800, textDecoration: "none",
              display: "flex", alignItems: "center", gap: 4, transition: "all 0.2s"
            }}
            onMouseOver={(e) => { e.currentTarget.style.background = "rgba(167,139,250,0.25)"; e.currentTarget.style.transform = "scale(1.05)"; }}
            onMouseOut={(e) => { e.currentTarget.style.background = "rgba(167,139,250,0.15)"; e.currentTarget.style.transform = "scale(1)"; }}
            title="Run AI Analyst"
          >
            🧠
          </Link>
          <button
            onClick={() => setConfirmAction({ type: "delete_one", id: s.id, symbol: s.symbol })}
            style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "rgba(239,68,68,0.08)", color: "#f87171", cursor: "pointer", fontSize: "0.7rem" }}
          >
            ✕
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid rgba(255,255,255,0.05)", background: "rgba(0,0,0,0.2)" }}>
        {[
          { id: "overview", label: "Overview" },
          { id: "indicators", label: "Technicals" },
          { id: "institutional", label: "Institutional" }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            style={{
              flex: 1, padding: "10px 0", border: "none", background: "transparent",
              color: activeTab === tab.id ? "#fff" : "var(--text-muted)",
              fontWeight: activeTab === tab.id ? 800 : 600, fontSize: "0.7rem", cursor: "pointer",
              borderBottom: activeTab === tab.id ? `2px solid ${accentColor}` : "2px solid transparent",
              transition: "all 0.2s"
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={{ padding: "18px 20px" }}>
        
        {/* OVERVIEW TAB */}
        <div style={{ display: activeTab === "overview" ? "block" : "none" }}>
          <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 18 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <ScoreRing score={score} />
              <div style={{ fontSize: "1.1rem" }}>{getStarRating(score)}</div>
            </div>
            <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
              {[
                { label: "Entry", value: `${formatPrice(s.entry_low)}–${formatPrice(s.entry_high)}`, color: "#fff" },
                { label: "Stop Loss", value: formatPrice(s.stop_loss), color: "#f87171" },
                { label: "R:R", value: `1:${(s.risk_reward ?? 0).toFixed(1)}`, color: "#60a5fa" },
              ].map(item => (
                <div key={item.label}>
                  <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 3 }}>{item.label}</div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, fontSize: "0.8rem", color: item.color }}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
            {[s.take_profit_1, s.take_profit_2, s.take_profit_3].map((tp, idx) => tp ? (
              <div key={idx} style={{ flex: 1, background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.15)", borderRadius: 8, padding: "7px 10px", textAlign: "center" }}>
                <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", fontWeight: 800, marginBottom: 2 }}>TP{idx + 1}</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.78rem", color: "#10b981", fontWeight: 700 }}>{formatPrice(tp)}</div>
              </div>
            ) : null)}
          </div>
          
          {/* Setup Explanation with truncation */}
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.55, background: "rgba(59,130,246,0.04)", padding: "10px 14px", borderRadius: 10, borderLeft: `3px solid ${accentColor}60`, marginBottom: 16 }}>
            <strong style={{ color: "#fff", display: "block", marginBottom: 3, fontSize: "0.72rem" }}>{s.setup_type}</strong>
            <span style={!isExpanded ? { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" } : {}}>
              {s.explanation}
            </span>
            {s.explanation && s.explanation.length > 100 && (
              <button
                onClick={() => toggleExpand(s.id || i)}
                style={{ background: "none", border: "none", color: "#60a5fa", fontSize: "0.7rem", cursor: "pointer", padding: "4px 0 0", fontWeight: 700 }}
              >
                {isExpanded ? "▲ Show less" : "▼ Show more"}
              </button>
            )}
          </div>
        </div>

        {/* TECHNICALS TAB */}
        <div style={{ display: activeTab === "indicators" ? "block" : "none" }}>
          {/* Intraday Indicators */}
          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 12, padding: "14px 16px", marginBottom: 14 }}>
            <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 12 }}>Intraday Indicators</div>
            <div style={{ display: "flex", gap: 10, marginBottom: 10, background: "rgba(0,0,0,0.15)", borderRadius: 8, padding: "10px 14px" }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "0.55rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 3 }}>Fib Level</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.75rem", fontWeight: 800, color: fib.is_near_key_level ? "#10b981" : "#a78bfa" }}>
                  {fib.current_level || "N/A"}
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "0.55rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 3 }}>Swing H/L</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.65rem", fontWeight: 700, color: "var(--text-secondary)" }}>
                  {formatPrice(fib.swing_high)} / {formatPrice(fib.swing_low)}
                </div>
              </div>
            </div>
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
          
          {/* Phase 3 Power Features */}
          {(() => {
            const adx = details.adx || {};
            const cp = details.candle_pattern || {};
            const oi = details.open_interest || {};
            const hasAny = adx.value != null || cp.pattern || oi.trend;
            if (!hasAny) return null;
            return (
              <div style={{ background: "rgba(245,158,11,0.03)", border: "1px solid rgba(245,158,11,0.15)", borderRadius: 12, padding: "14px 16px", marginBottom: 14 }}>
                <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "#f59e0b", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 12 }}>⚡ Phase 3: Power Features</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                  {adx.value != null && (
                    <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 8, padding: "8px 10px", border: adx.penalty < 0 ? "1px solid rgba(239,68,68,0.25)" : "1px solid rgba(255,255,255,0.06)" }}>
                      <div style={{ fontSize: "0.55rem", fontWeight: 800, color: "var(--text-muted)", marginBottom: 4 }}>ADX (14)</div>
                      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.82rem", fontWeight: 900, color: adx.value >= 25 ? "#10b981" : adx.value >= 20 ? "#f59e0b" : "#ef4444" }}>{adx.value}</div>
                      <div style={{ fontSize: "0.55rem", color: adx.value >= 25 ? "#10b981" : adx.value >= 20 ? "#f59e0b" : "#ef4444", fontWeight: 700, marginTop: 2 }}>
                        {adx.value >= 25 ? "TRENDING" : adx.value >= 20 ? "WEAK" : "RANGING"}
                        {adx.penalty < 0 && <span style={{ color: "#ef4444", marginLeft: 4 }}>({adx.penalty})</span>}
                      </div>
                    </div>
                  )}
                  {cp.pattern && (
                    <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 8, padding: "8px 10px", border: cp.aligned ? "1px solid rgba(16,185,129,0.25)" : "1px solid rgba(255,255,255,0.06)" }}>
                      <div style={{ fontSize: "0.55rem", fontWeight: 800, color: "var(--text-muted)", marginBottom: 4 }}>PATTERN</div>
                      <div style={{ fontSize: "0.68rem", fontWeight: 800, color: cp.aligned ? "#10b981" : "#94a3b8", textTransform: "capitalize" }}>{cp.pattern?.replace("_", " ")}</div>
                      <div style={{ fontSize: "0.55rem", color: cp.aligned ? "#10b981" : "var(--text-muted)", fontWeight: 700, marginTop: 2 }}>{cp.aligned ? `+${cp.score}pts` : "No Match"}</div>
                    </div>
                  )}
                  {oi.trend && (
                    <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 8, padding: "8px 10px", border: oi.aligned ? "1px solid rgba(139,92,246,0.25)" : "1px solid rgba(255,255,255,0.06)" }}>
                      <div style={{ fontSize: "0.55rem", fontWeight: 800, color: "var(--text-muted)", marginBottom: 4 }}>OPEN INT.</div>
                      <div style={{ fontSize: "0.68rem", fontWeight: 800, color: oi.trend === "increasing" ? "#a78bfa" : oi.trend === "decreasing" ? "#ef4444" : "#94a3b8" }}>
                        {oi.trend === "increasing" ? "▲ RISING" : oi.trend === "decreasing" ? "▼ FALLING" : "→ FLAT"}
                      </div>
                      <div style={{ fontSize: "0.55rem", color: oi.aligned ? "#a78bfa" : "var(--text-muted)", fontWeight: 700, marginTop: 2 }}>{oi.aligned ? `+${oi.score}pts` : "No Boost"}</div>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
        </div>

        {/* INSTITUTIONAL TAB */}
        <div style={{ display: activeTab === "institutional" ? "block" : "none" }}>
          {(() => {
            const vwap = details.vwap || {};
            const vp = details.volume_profile || {};
            const div = details.divergence || {};
            const hasAny = vwap.value || vp.poc || div.type !== "none";
            if (!hasAny) return (
              <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem", border: "1px dashed rgba(255,255,255,0.1)", borderRadius: 12 }}>
                No significant institutional data for this setup.
              </div>
            );
            return (
              <div style={{ background: "rgba(139,92,246,0.04)", border: "1px solid rgba(139,92,246,0.12)", borderRadius: 12, padding: "14px 16px", marginBottom: 14 }}>
                <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "#a78bfa", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 12 }}>🏛 Institutional Indicators</div>
                {vwap.value && (
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <div>
                      <div style={{ fontSize: "0.6rem", fontWeight: 800, color: "var(--text-muted)", marginBottom: 2 }}>VWAP</div>
                      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.78rem", fontWeight: 700, color: "#fff" }}>{formatPrice(vwap.value)}</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ padding: "3px 10px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 800, background: vwap.position === "above" ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)", color: vwap.position === "above" ? "#10b981" : "#ef4444", border: `1px solid ${vwap.position === "above" ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)"}` }}>
                        {vwap.position === "above" ? "▲ ABOVE" : "▼ BELOW"} VWAP
                      </div>
                      {vwap.distance_pct != null && <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginTop: 3 }}>{vwap.distance_pct}% away</div>}
                    </div>
                  </div>
                )}
                {vp.poc && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: "0.6rem", fontWeight: 800, color: "var(--text-muted)" }}>VOLUME PROFILE</span>
                      <span style={{ fontSize: "0.65rem", fontWeight: 800, padding: "2px 8px", borderRadius: 4, background: vp.in_value_area ? "rgba(245,158,11,0.15)" : "transparent", color: vp.in_value_area ? "#f59e0b" : "var(--text-muted)" }}>
                        {vp.in_value_area ? "✓ IN VALUE AREA" : `${vp.poc_distance_pct}% from POC`}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: 8 }}>
                      {[{ label: "VAH", value: vp.vah, color: "#ef4444" }, { label: "POC", value: vp.poc, color: "#f59e0b" }, { label: "VAL", value: vp.val, color: "#10b981" }].map(item => (
                        <div key={item.label} style={{ flex: 1, textAlign: "center", background: "rgba(255,255,255,0.03)", borderRadius: 6, padding: "5px 0" }}>
                          <div style={{ fontSize: "0.55rem", color: item.color, fontWeight: 800, marginBottom: 2 }}>{item.label}</div>
                          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.68rem", color: "#fff", fontWeight: 700 }}>{formatPrice(item.value)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {div.type && div.type !== "none" && (
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ flex: 1, padding: "8px 12px", borderRadius: 8, background: div.type === "bullish" ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)", border: `1px solid ${div.type === "bullish" ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}` }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div>
                          <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", fontWeight: 800, textTransform: "uppercase", marginBottom: 2 }}>
                            {div.rsi_divergence && div.macd_divergence ? "RSI + MACD" : div.rsi_divergence ? "RSI" : "MACD"} Divergence
                          </div>
                          <div style={{ fontSize: "0.72rem", fontWeight: 800, color: div.type === "bullish" ? "#10b981" : "#ef4444" }}>
                            {div.type === "bullish" ? "▲ BULLISH" : "▼ BEARISH"} DIV
                          </div>
                        </div>
                        {div.strength > 0 && <div style={{ fontSize: "0.65rem", fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, color: "var(--text-muted)" }}>str: {div.strength}</div>}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={handleCopySignal}
            title="Copy Signal"
            style={{ padding: "10px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.04)", color: "var(--text-primary)", fontSize: "0.85rem", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
          >
            📋
          </button>
          
          <button
            onClick={() => router.push(`/charts?symbol=${s.symbol}`)}
            title="View on Chart"
            style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.04)", color: "var(--text-muted)", fontSize: "0.75rem", fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap" }}
          >
            📈 Chart
          </button>

          {s.status === "ACTIVE" && (
            <>
              <button
                onClick={() => !isExecuting && handleExecute(s.id)}
                disabled={isExecuting}
                style={{ flex: 2, padding: "10px", borderRadius: 10, border: "none", background: isExecuting ? "rgba(255,255,255,0.08)" : `linear-gradient(135deg, ${accentColor}cc, ${accentColor})`, color: isExecuting ? "var(--text-muted)" : "#fff", fontSize: "0.78rem", fontWeight: 800, cursor: isExecuting ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}
              >
                {isExecuting
                  ? <><span style={{ width: 12, height: 12, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.8s linear infinite", display: "inline-block" }} /> Executing…</>
                  : "⚡ Execute"}
              </button>
              <button
                onClick={() => api.updateSetupStatus(s.id, "TRIGGERED").then(fetchSetups)}
                style={{ flex: 1, padding: "10px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.04)", color: "var(--text-primary)", fontSize: "0.75rem", fontWeight: 700, cursor: "pointer" }}
              >
                Triggered
              </button>
            </>
          )}
          {s.status === "TRIGGERED" && (
            <div style={{ display: "flex", gap: 6, flex: 1 }}>
              {[["WIN", "#10b981"], ["LOSS", "#ef4444"], ["BE", "#94a3b8"]].map(([r, c]) => (
                <button
                  key={r}
                  onClick={() => api.logSetupToJournal(s.id, { result: r as string }).then(fetchSetups)}
                  style={{ flex: 1, padding: "9px", borderRadius: 9, background: `${c}18`, border: `1px solid ${c}40`, color: c as string, fontWeight: 800, fontSize: "0.75rem", cursor: "pointer" }}
                >
                  {r}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
