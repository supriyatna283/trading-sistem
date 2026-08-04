"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { API_URL } from "@/lib/utils";

// ─────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────
interface SetupData {
  symbol: string;
  timeframe: string;
  signal: "BUY" | "SELL" | "WAIT";
  confidence: "LOW" | "MEDIUM" | "HIGH";
  confluence_score: number;
  max_score: number;
  confluence_pct: number;
  recommendation: string;
  session?: string;
  entry: number | null;
  entry_low: number | null;
  entry_high: number | null;
  stop_loss: number | null;
  tp1: number | null;
  tp2: number | null;
  tp3: number | null;
  risk_reward: number | null;
  atr?: number | null;
  htf_biases: Record<string, string>;
  indicators: Record<string, any>;
  smc: Record<string, any>;
  highlights?: Record<string, boolean>;
}

interface Props {
  symbol: string;
  timeframe: string;
  isOpen: boolean;
  onClose: () => void;
}

type AIStatus =
  | "idle"
  | "computing"
  | "thinking"
  | "streaming"
  | "done"
  | "error"
  | "cached";

// ─────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────
function fmt(v: number | null | undefined, dec = 4): string {
  if (v == null) return "—";
  return v.toLocaleString("en-US", { maximumFractionDigits: dec, minimumFractionDigits: dec });
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function BiasTag({ bias }: { bias: string }) {
  const map: Record<string, [string, string]> = {
    BULLISH: ["rgba(34,197,94,0.15)", "#22c55e"],
    BEARISH: ["rgba(239,68,68,0.15)", "#ef4444"],
    SIDEWAYS: ["rgba(161,161,170,0.15)", "#a1a1aa"],
    UNKNOWN: ["rgba(113,113,122,0.1)", "#71717a"],
  };
  const [bg, color] = map[bias] ?? map.UNKNOWN;
  return (
    <span style={{ padding: "2px 7px", borderRadius: 5, fontSize: "0.63rem", fontWeight: 700, background: bg, color }}>
      {bias}
    </span>
  );
}

function SignalBadge({ signal }: { signal: "BUY" | "SELL" | "WAIT" }) {
  const cfg = {
    BUY: { bg: "rgba(34,197,94,0.15)", border: "rgba(34,197,94,0.4)", color: "#22c55e", icon: "▲" },
    SELL: { bg: "rgba(239,68,68,0.15)", border: "rgba(239,68,68,0.4)", color: "#ef4444", icon: "▼" },
    WAIT: { bg: "rgba(234,179,8,0.15)", border: "rgba(234,179,8,0.4)", color: "#eab308", icon: "⏸" },
  };
  const c = cfg[signal];
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "5px 14px", borderRadius: 8,
      background: c.bg, border: `1px solid ${c.border}`, color: c.color,
      fontWeight: 900, fontSize: "1rem", letterSpacing: "0.06em",
    }}>
      {c.icon} {signal}
    </span>
  );
}

function ConfidenceBadge({ conf }: { conf: "LOW" | "MEDIUM" | "HIGH" }) {
  const cfg = {
    HIGH: { color: "#22c55e", bg: "rgba(34,197,94,0.1)" },
    MEDIUM: { color: "#f59e0b", bg: "rgba(245,158,11,0.1)" },
    LOW: { color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
  };
  const c = cfg[conf];
  return (
    <span style={{ fontSize: "0.68rem", fontWeight: 700, color: c.color, background: c.bg, padding: "3px 8px", borderRadius: 5 }}>
      {conf} CONFIDENCE
    </span>
  );
}

function HighlightRow({ label, active }: { label: string; active: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "2px 0" }}>
      <span style={{ fontSize: "0.63rem", color: active ? "var(--text-secondary)" : "var(--text-muted)" }}>
        {label.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
      </span>
      <span style={{ fontSize: "0.68rem" }}>{active ? "✅" : "❌"}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────
export default function AIAnalysisPanel({ symbol, timeframe, isOpen, onClose }: Props) {
  const [status, setStatus] = useState<AIStatus>("idle");
  const [reasoning, setReasoning] = useState("");
  const [answer, setAnswer] = useState("");
  const [context, setContext] = useState<any>(null);
  const [setup, setSetup] = useState<SetupData | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"setup" | "confluence" | "analysis">("setup");
  const [showRawReasoning, setShowRawReasoning] = useState(false);

  const esRef = useRef<EventSource | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const answerRef = useRef<HTMLDivElement>(null);

  const cancelStream = useCallback(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
  }, []);

  const startAnalysis = useCallback((sym: string, tf: string) => {
    cancelStream();
    setStatus("computing");
    setReasoning(""); setAnswer(""); setError(""); setSetup(null); setContext(null);

    const url = `${API_URL}/api/v1/ai/analyze?symbol=${sym}&timeframe=${tf}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("status", (e) => {
      const s = (e as any).data;
      if (s === "computing_indicators") setStatus("computing");
      else if (s === "ai_thinking") setStatus("thinking");
      else if (s === "cache_hit") setStatus("cached");
    });

    es.addEventListener("context", (e) => {
      try { setContext(JSON.parse((e as any).data.replace(/\\n/g, "\n"))); } catch (_) {}
    });

    es.addEventListener("setup_data", (e) => {
      try { setSetup(JSON.parse((e as any).data.replace(/\\n/g, "\n"))); } catch (_) {}
    });

    es.addEventListener("reasoning", (e) => {
      setStatus("thinking");
      setReasoning(prev => prev + (e as any).data.replace(/\\n/g, "\n"));
    });

    es.addEventListener("token", (e) => {
      setStatus("streaming");
      setAnswer(prev => prev + (e as any).data.replace(/\\n/g, "\n"));
    });

    es.addEventListener("done", () => { setStatus("done"); es.close(); esRef.current = null; });

    es.addEventListener("error", (e: any) => {
      const msg = (e.data || "").replace(/\\n/g, "\n");
      setError(msg || "Connection error");
      setStatus("error");
      es.close(); esRef.current = null;
    });

    es.onerror = () => {
      if (status !== "done") {
        setError("Stream disconnected");
        setStatus("error");
        es.close(); esRef.current = null;
      }
    };
  }, [cancelStream, status]);

  // Auto-trigger with 2.5s debounce
  useEffect(() => {
    if (!isOpen) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => startAnalysis(symbol, timeframe), 2500);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, timeframe, isOpen]);

  useEffect(() => { if (!isOpen) cancelStream(); }, [isOpen, cancelStream]);

  useEffect(() => {
    if (answerRef.current) answerRef.current.scrollTop = answerRef.current.scrollHeight;
  }, [answer]);

  if (!isOpen) return null;

  const isPulsing = status === "computing" || status === "thinking" || status === "streaming";

  const statusLabel: Record<AIStatus, string> = {
    idle: "Ready",
    computing: "Computing indicators…",
    thinking: "AI is reasoning…",
    streaming: "Streaming analysis…",
    done: "Analysis complete",
    error: "Error",
    cached: "Cached result",
  };

  const htfCtx = context?.htf_biases || setup?.htf_biases || {};
  const ind = setup?.indicators || context?.indicators || {};
  const smc = setup?.smc || context?.smc || {};
  const highlights = setup?.highlights || {};

  const rsiColor = (rsi: number) => rsi > 70 ? "#ef4444" : rsi < 30 ? "#22c55e" : "var(--text-primary)";
  const adxLabel = (adx: number) => adx > 25 ? "Trending" : "Ranging";

  return (
    <div id="ai-panel" className="glass-card">
      {/* ── Header ── */}
      <div id="ai-panel-header">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div id={isPulsing ? "ai-icon-pulse" : "ai-icon"}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span id="ai-panel-title">AI Analyst</span>
          <span id="ai-symbol-badge">{symbol.replace("USDT", "")}/{timeframe.toUpperCase()}</span>
          {setup?.session && (
            <span style={{ fontSize: "0.58rem", padding: "1px 6px", borderRadius: 4, background: "rgba(59,130,246,0.12)", color: "#60a5fa", border: "1px solid rgba(59,130,246,0.25)" }}>
              {setup.session.split("/")[0]}
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <button onClick={() => startAnalysis(symbol, timeframe)} className="ai-refresh-btn" disabled={isPulsing} title="Re-analyze">
            {isPulsing ? "…" : "↺"}
          </button>
          <button onClick={onClose} className="ai-close-btn">✕</button>
        </div>
      </div>

      {/* ── Status Bar ── */}
      <div id="ai-status-bar">
        <div id="ai-status-dot" className={isPulsing ? "dot-pulse" : status === "done" ? "dot-green" : status === "error" ? "dot-red" : "dot-idle"} />
        <span id="ai-status-text">{statusLabel[status]}</span>
        {setup && (
          <span style={{ marginLeft: "auto", fontSize: "0.6rem", color: "var(--text-muted)" }}>
            ⚡ {setup.confluence_score}/{setup.max_score} pts · ATR: {fmt(setup.atr, 2)}
          </span>
        )}
      </div>

      {/* ── HTF Bias Row (instant) ── */}
      {Object.keys(htfCtx).length > 0 && (
        <div id="ai-context-row">
          {Object.entries(htfCtx).map(([tf, bias]) => (
            <div key={tf} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
              <span style={{ fontSize: "0.56rem", color: "var(--text-muted)", fontWeight: 700 }}>{tf.toUpperCase()}</span>
              <BiasTag bias={bias as string} />
            </div>
          ))}
        </div>
      )}

      {/* ── Error ── */}
      {status === "error" && (
        <div id="ai-error-box">⚠️ <span>{error}</span></div>
      )}

      {/* ── Tabs ── */}
      {(setup || answer) && (
        <div id="ai-tabs">
          <button className={`ai-tab${tab === "setup" ? " ai-tab-active" : ""}`} onClick={() => setTab("setup")}>📐 Setup</button>
          <button className={`ai-tab${tab === "confluence" ? " ai-tab-active" : ""}`} onClick={() => setTab("confluence")}>⚡ Score</button>
          <button className={`ai-tab${tab === "analysis" ? " ai-tab-active" : ""}`} onClick={() => setTab("analysis")}>🧠 Analysis</button>
        </div>
      )}

      {/* ── SETUP TAB ── */}
      {tab === "setup" && (
        <div id="ai-setup-tab">
          {setup ? (
            <>
              {/* Signal + Confidence */}
              <div id="ai-signal-card">
                <SignalBadge signal={setup.signal} />
                <ConfidenceBadge conf={setup.confidence} />
              </div>

              {/* Confluence bar */}
              <div style={{ padding: "0 12px 8px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.63rem", color: "var(--text-muted)", marginBottom: 4 }}>
                  <span>Confluence Score</span>
                  <span style={{ fontWeight: 700, color: setup.confluence_pct >= 60 ? "#22c55e" : setup.confluence_pct >= 35 ? "#f59e0b" : "#ef4444" }}>
                    {setup.confluence_score}/{setup.max_score} ({setup.confluence_pct}%)
                  </span>
                </div>
                <div id="conf-bar-bg">
                  <div id="conf-bar-fill" style={{
                    width: `${setup.confluence_pct}%`,
                    background: setup.confluence_pct >= 60
                      ? "linear-gradient(90deg, #22c55e, #16a34a)"
                      : setup.confluence_pct >= 35
                      ? "linear-gradient(90deg, #f59e0b, #d97706)"
                      : "linear-gradient(90deg, #ef4444, #dc2626)",
                  }} />
                </div>
              </div>

              {/* Price levels */}
              {setup.signal !== "WAIT" && (
                <div id="ai-price-table">
                  <div className="price-row">
                    <span className="price-label">Entry Zone</span>
                    <span className="price-val price-blue">{fmt(setup.entry_low)} – {fmt(setup.entry_high)}</span>
                  </div>
                  <div className="price-row">
                    <span className="price-label">Stop Loss</span>
                    <span className="price-val price-red">{fmt(setup.stop_loss)}</span>
                  </div>
                  <div className="price-row" style={{ paddingTop: 4, borderTop: "1px solid var(--border)", marginTop: 2 }}>
                    <span className="price-label">TP 1</span>
                    <span className="price-val price-green">{fmt(setup.tp1)}</span>
                  </div>
                  <div className="price-row">
                    <span className="price-label">TP 2</span>
                    <span className="price-val price-green">{fmt(setup.tp2)}</span>
                  </div>
                  <div className="price-row">
                    <span className="price-label">TP 3</span>
                    <span className="price-val price-green">{fmt(setup.tp3)}</span>
                  </div>
                  <div className="price-row" style={{ borderTop: "1px solid var(--border)", marginTop: 4, paddingTop: 5 }}>
                    <span className="price-label">R:R Ratio</span>
                    <span className="price-val" style={{ color: (setup.risk_reward || 0) >= 2 ? "#4ade80" : (setup.risk_reward || 0) >= 1.5 ? "#f59e0b" : "#f87171" }}>
                      1:{(setup.risk_reward || 0).toFixed(1)}
                    </span>
                  </div>
                  <div className="price-row">
                    <span className="price-label">ATR</span>
                    <span className="price-val" style={{ color: "var(--text-muted)" }}>{fmt(setup.atr, 2)}</span>
                  </div>
                </div>
              )}

              {setup.signal === "WAIT" && (
                <div id="ai-wait-box">
                  <div style={{ fontSize: "1.5rem", marginBottom: 6 }}>⏸</div>
                  <div style={{ fontWeight: 700, color: "#eab308", marginBottom: 4 }}>No Trade Zone</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textAlign: "center", lineHeight: 1.5 }}>
                    Confluence score {setup.confluence_pct}% — too low for a reliable setup. Wait for better conditions.
                  </div>
                </div>
              )}

              {/* SMC Summary */}
              {setup.smc && (
                <div id="ai-smc-row">
                  <div className="smc-cell">
                    <span className="smc-label">Order Blocks</span>
                    <span className="smc-val" style={{ color: "#a78bfa" }}>{smc.unmitigated_ob_count ?? "—"}</span>
                  </div>
                  <div className="smc-cell">
                    <span className="smc-label">FVGs</span>
                    <span className="smc-val" style={{ color: "#60a5fa" }}>{smc.unfilled_fvg_count ?? "—"}</span>
                  </div>
                  <div className="smc-cell">
                    <span className="smc-label">Liquidity</span>
                    <span className="smc-val" style={{ color: "#f59e0b" }}>{smc.liquidity_levels_count ?? smc.liquidity_levels ?? "—"}</span>
                  </div>
                  <div className="smc-cell">
                    <span className="smc-label">P/D Zone</span>
                    <span className="smc-val" style={{ color: smc.pd_zone === "DISCOUNT" ? "#22c55e" : smc.pd_zone === "PREMIUM" ? "#ef4444" : "var(--text-muted)" }}>
                      {smc.pd_zone || "—"}
                    </span>
                  </div>
                </div>
              )}

              {/* Indicators mini-grid */}
              <div id="ai-indicators-grid">
                {[
                  { label: "RSI", val: ind.rsi != null ? ind.rsi.toFixed(1) : "—", color: ind.rsi != null ? rsiColor(ind.rsi) : undefined },
                  { label: "ADX", val: ind.adx != null ? `${ind.adx.toFixed(1)} (${adxLabel(ind.adx)})` : "—" },
                  { label: "MACD", val: ind.macd_histogram != null ? `${ind.macd_histogram > 0 ? "▲" : "▼"} ${Math.abs(ind.macd_histogram).toFixed(4)}` : "—", color: ind.macd_histogram != null ? (ind.macd_histogram > 0 ? "#22c55e" : "#ef4444") : undefined },
                  { label: "VWAP", val: ind.vwap_position ? (ind.vwap_position === "above" ? "▲ Above" : "▼ Below") : "—", color: ind.vwap_position === "above" ? "#22c55e" : "#ef4444" },
                  { label: "StochRSI K", val: ind.stoch_k != null ? ind.stoch_k.toFixed(1) : "—" },
                  { label: "BB Width", val: ind.bb_bandwidth != null ? ind.bb_bandwidth.toFixed(2) : "—" },
                  { label: "Pattern", val: ind.candle_pattern ? (typeof ind.candle_pattern === "string" && ind.candle_pattern.includes("pattern") ? JSON.parse(ind.candle_pattern.replace(/'/g, '"'))?.pattern || "—" : ind.candle_pattern) : "None" },
                  { label: "RSI Div", val: ind.rsi_divergence || "None" },
                ].map(({ label, val, color }) => (
                  <div key={label} className="ind-cell">
                    <span className="ind-label">{label}</span>
                    <span className="ind-val" style={color ? { color } : {}}>{val}</span>
                  </div>
                ))}
              </div>
            </>
          ) : isPulsing ? (
            <div id="ai-loading-state">
              <div className="ai-spinner" />
              <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                {status === "computing" ? "Computing all indicators…" : "AI analyst thinking…"}
              </span>
            </div>
          ) : null}
        </div>
      )}

      {/* ── CONFLUENCE TAB ── */}
      {tab === "confluence" && (
        <div id="ai-confluence-tab">
          {setup && Object.keys(highlights).length > 0 ? (
            <>
              <div style={{ padding: "10px 12px 6px", borderBottom: "1px solid var(--border)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-primary)" }}>Confluence Score</span>
                  <span style={{
                    fontSize: "0.9rem", fontWeight: 900,
                    color: setup.confluence_pct >= 60 ? "#22c55e" : setup.confluence_pct >= 35 ? "#f59e0b" : "#ef4444"
                  }}>
                    {setup.confluence_score}/{setup.max_score}
                  </span>
                </div>
                {/* Big score bar */}
                <div style={{ height: 8, borderRadius: 4, background: "var(--border)", overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 4,
                    width: `${setup.confluence_pct}%`,
                    background: setup.confluence_pct >= 60
                      ? "linear-gradient(90deg, #22c55e, #16a34a)"
                      : setup.confluence_pct >= 35
                      ? "linear-gradient(90deg, #f59e0b, #d97706)"
                      : "linear-gradient(90deg, #ef4444, #dc2626)",
                    transition: "width 0.8s ease",
                  }} />
                </div>
              </div>
              <div style={{ padding: "8px 12px", display: "flex", flexDirection: "column", gap: 2, overflowY: "auto", flex: 1 }}>
                {Object.entries(highlights).map(([key, val]) => (
                  <HighlightRow key={key} label={key} active={val as boolean} />
                ))}
              </div>
            </>
          ) : (
            <div id="ai-loading-state">
              <div className="ai-spinner" />
              <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>Loading confluence data…</span>
            </div>
          )}
        </div>
      )}

      {/* ── ANALYSIS TAB ── */}
      {tab === "analysis" && (
        <div id="ai-reasoning-tab">
          {reasoning && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "5px 12px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
              <span style={{ fontSize: "0.6rem", color: "#a78bfa", fontWeight: 700 }}>🧠 DEEP REASONING</span>
              <button onClick={() => setShowRawReasoning(v => !v)} style={{ fontSize: "0.6rem", color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer" }}>
                {showRawReasoning ? "Hide" : "Show"}
              </button>
            </div>
          )}
          {showRawReasoning && reasoning && (
            <div id="ai-reasoning-box">
              <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: "0.62rem", lineHeight: 1.5, color: "#a78bfa" }}>{reasoning}</pre>
            </div>
          )}
          <div id="ai-answer-box" ref={answerRef}>
            {answer ? (
              <div id="ai-answer-text">
                {answer}
                {status === "streaming" && <span id="ai-cursor">▌</span>}
              </div>
            ) : isPulsing ? (
              <div id="ai-thinking-indicator">
                <div className="ai-dots"><span /><span /><span /></div>
                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                  {status === "thinking" ? "AI analyst deep reasoning…" : "Streaming expert analysis…"}
                </span>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* ── Styles ── */}
      <style>{`
        #ai-panel {
          width: 310px;
          flex-shrink: 0;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          padding: 0;
          animation: aiPanelIn 0.2s ease;
        }
        @keyframes aiPanelIn { from { opacity:0; transform:translateX(12px); } to { opacity:1; transform:translateX(0); } }

        #ai-panel-header {
          display: flex; justify-content: space-between; align-items: center;
          padding: 10px 12px 8px;
          border-bottom: 1px solid var(--border);
          background: linear-gradient(135deg, rgba(139,92,246,0.08), rgba(59,130,246,0.08));
          flex-shrink: 0;
        }
        #ai-panel-title { font-size: 0.78rem; font-weight: 800; color: var(--text-primary); letter-spacing: 0.02em; }
        #ai-symbol-badge {
          font-size: 0.62rem; font-weight: 700; padding: 2px 7px; border-radius: 5px;
          background: rgba(139,92,246,0.15); color: #a78bfa; border: 1px solid rgba(139,92,246,0.3);
        }
        #ai-icon { color: #a78bfa; display: flex; align-items: center; justify-content: center; }
        #ai-icon-pulse { color: #a78bfa; display: flex; align-items: center; justify-content: center; animation: aiIconPulse 1.5s ease-in-out infinite; }
        @keyframes aiIconPulse { 0%,100% { transform:scale(1); opacity:1; } 50% { transform:scale(1.25); opacity:0.6; } }

        .ai-refresh-btn {
          background: rgba(139,92,246,0.12); border: 1px solid rgba(139,92,246,0.3); border-radius: 7px;
          padding: 4px 10px; color: #a78bfa; font-size: 0.9rem; cursor: pointer; transition: all 0.15s;
        }
        .ai-refresh-btn:hover:not(:disabled) { background: rgba(139,92,246,0.22); }
        .ai-refresh-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .ai-close-btn { background: none; border: none; color: var(--text-muted); font-size: 0.85rem; cursor: pointer; padding: 4px 6px; border-radius: 5px; transition: all 0.15s; }
        .ai-close-btn:hover { color: var(--text-primary); background: rgba(255,255,255,0.05); }

        #ai-status-bar {
          display: flex; align-items: center; gap: 6px; padding: 5px 12px;
          background: rgba(0,0,0,0.2); flex-shrink: 0; border-bottom: 1px solid var(--border);
        }
        #ai-status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
        .dot-pulse { background: #a78bfa; animation: dotPulse 1s ease-in-out infinite; }
        .dot-green { background: #22c55e; }
        .dot-red { background: #ef4444; }
        .dot-idle { background: var(--border); }
        @keyframes dotPulse { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:0.4; transform:scale(0.7); } }
        #ai-status-text { font-size: 0.62rem; font-weight: 600; color: var(--text-muted); letter-spacing: 0.04em; }

        #ai-context-row {
          display: flex; gap: 6px; padding: 7px 12px; border-bottom: 1px solid var(--border);
          flex-shrink: 0; background: rgba(0,0,0,0.15); flex-wrap: wrap;
        }

        #ai-error-box {
          display: flex; align-items: center; gap: 8px; padding: 10px 12px; margin: 8px 12px;
          border-radius: 8px; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.25);
          color: #f87171; font-size: 0.75rem; flex-shrink: 0;
        }

        #ai-tabs { display: flex; border-bottom: 1px solid var(--border); flex-shrink: 0; }
        .ai-tab {
          flex: 1; padding: 7px 4px; font-size: 0.67rem; font-weight: 700; border: none;
          background: transparent; color: var(--text-muted); cursor: pointer; transition: all 0.15s;
          border-bottom: 2px solid transparent;
        }
        .ai-tab:hover { color: var(--text-primary); background: rgba(255,255,255,0.02); }
        .ai-tab-active { color: #a78bfa; border-bottom-color: #a78bfa; background: rgba(139,92,246,0.05); }

        /* Setup Tab */
        #ai-setup-tab { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
        #ai-signal-card { display: flex; align-items: center; gap: 8px; padding: 12px 12px 8px; flex-wrap: wrap; }
        #conf-bar-bg { width: 100%; height: 5px; border-radius: 3px; background: var(--border); overflow: hidden; }
        #conf-bar-fill { height: 100%; border-radius: 3px; transition: width 0.6s ease; }

        #ai-price-table {
          display: flex; flex-direction: column; gap: 4px;
          padding: 8px 10px; margin: 4px 8px 4px;
          background: rgba(0,0,0,0.2); border-radius: 8px; border: 1px solid var(--border);
        }
        .price-row { display: flex; justify-content: space-between; align-items: center; }
        .price-label { font-size: 0.67rem; color: var(--text-muted); }
        .price-val { font-size: 0.71rem; font-weight: 700; font-family: 'JetBrains Mono','Fira Code',monospace; color: var(--text-primary); }
        .price-red { color: #f87171 !important; }
        .price-green { color: #4ade80 !important; }
        .price-blue { color: #60a5fa !important; }

        #ai-smc-row {
          display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 4px;
          padding: 6px 8px; margin: 0 8px 4px;
          background: rgba(0,0,0,0.15); border-radius: 7px; border: 1px solid var(--border);
        }
        .smc-cell { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 4px 2px; }
        .smc-label { font-size: 0.55rem; color: var(--text-muted); font-weight: 600; text-align: center; }
        .smc-val { font-size: 0.75rem; font-weight: 800; }

        #ai-indicators-grid {
          display: grid; grid-template-columns: 1fr 1fr; gap: 4px; padding: 6px 8px 8px;
        }
        .ind-cell {
          display: flex; flex-direction: column; gap: 1px; padding: 5px 7px;
          border-radius: 6px; background: rgba(255,255,255,0.02); border: 1px solid var(--border);
        }
        .ind-label { font-size: 0.56rem; color: var(--text-muted); font-weight: 600; letter-spacing: 0.04em; }
        .ind-val { font-size: 0.68rem; font-weight: 700; color: var(--text-primary); font-family: 'JetBrains Mono',monospace; word-break: break-all; }

        #ai-wait-box {
          display: flex; flex-direction: column; align-items: center; padding: 20px 12px;
          margin: 8px; border-radius: 10px;
          background: rgba(234,179,8,0.06); border: 1px solid rgba(234,179,8,0.2);
        }

        #ai-loading-state {
          flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
          gap: 14px; padding: 40px 20px;
        }
        .ai-spinner {
          width: 28px; height: 28px; border: 2px solid var(--border);
          border-top-color: #a78bfa; border-radius: 50%; animation: spin 0.9s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Confluence Tab */
        #ai-confluence-tab { flex: 1; display: flex; flex-direction: column; overflow-y: auto; min-height: 0; }

        /* Analysis Tab */
        #ai-reasoning-tab { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0; }
        #ai-reasoning-box {
          max-height: 120px; overflow-y: auto; padding: 8px 12px;
          background: rgba(167,139,250,0.05); border-bottom: 1px solid var(--border); flex-shrink: 0;
        }
        #ai-answer-box { flex: 1; overflow-y: auto; padding: 10px 12px; min-height: 0; }
        #ai-answer-text { font-size: 0.71rem; line-height: 1.75; color: var(--text-secondary); white-space: pre-wrap; word-break: break-word; }
        #ai-cursor { display: inline-block; color: #a78bfa; animation: blink 1s step-end infinite; }
        @keyframes blink { 50% { opacity: 0; } }
        #ai-thinking-indicator {
          flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; padding: 30px;
        }
        .ai-dots { display: flex; gap: 6px; }
        .ai-dots span { width: 8px; height: 8px; border-radius: 50%; background: #a78bfa; animation: dotBounce 1.2s ease-in-out infinite; }
        .ai-dots span:nth-child(1) { animation-delay: 0s; }
        .ai-dots span:nth-child(2) { animation-delay: 0.2s; }
        .ai-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes dotBounce { 0%,80%,100% { transform:scale(0.6); opacity:0.4; } 40% { transform:scale(1); opacity:1; } }
      `}</style>
    </div>
  );
}
