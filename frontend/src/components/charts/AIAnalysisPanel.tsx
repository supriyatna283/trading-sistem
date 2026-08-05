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

interface ChatMessage { role: "user" | "assistant"; content: string; }
interface Props { symbol: string; timeframe: string; isOpen: boolean; onClose: () => void; }
type AIStatus = "idle" | "computing" | "thinking" | "streaming" | "done" | "error" | "cached";

// ─────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────
function fmt(v: number | null | undefined, dec = 4): string {
  if (v == null) return "—";
  return v.toLocaleString("en-US", { maximumFractionDigits: dec, minimumFractionDigits: dec });
}

// ─────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────

function SignalPill({ signal, pct }: { signal: "BUY" | "SELL" | "WAIT"; pct: number }) {
  const cfg = {
    BUY: { grad: "linear-gradient(135deg,#15803d,#22c55e)", glow: "rgba(34,197,94,0.35)", icon: "↑", label: "LONG" },
    SELL: { grad: "linear-gradient(135deg,#991b1b,#ef4444)", glow: "rgba(239,68,68,0.35)", icon: "↓", label: "SHORT" },
    WAIT: { grad: "linear-gradient(135deg,#92400e,#f59e0b)", glow: "rgba(245,158,11,0.25)", icon: "—", label: "WAIT" },
  };
  const c = cfg[signal];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{
        background: c.grad, boxShadow: `0 0 20px ${c.glow}`,
        borderRadius: 10, padding: "10px 18px",
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{ fontSize: "1.4rem", fontWeight: 900, color: "#fff", lineHeight: 1 }}>{c.icon}</span>
        <span style={{ fontSize: "1rem", fontWeight: 900, color: "#fff", letterSpacing: "0.08em" }}>{c.label}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <span style={{ fontSize: "0.58rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em" }}>Confluence</span>
        <span style={{
          fontSize: "1.05rem", fontWeight: 900, fontFamily: "'JetBrains Mono',monospace",
          color: pct >= 60 ? "#4ade80" : pct >= 35 ? "#fbbf24" : "#f87171",
        }}>{pct}%</span>
      </div>
    </div>
  );
}

function PriceRow({ label, value, color, mono = true, bold = false }: { label: string; value: string; color?: string; mono?: boolean; bold?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
      <span style={{ fontSize: "0.63rem", color: "var(--text-muted)", fontWeight: 600 }}>{label}</span>
      <span style={{
        fontSize: bold ? "0.78rem" : "0.72rem",
        fontWeight: bold ? 900 : 700,
        fontFamily: mono ? "'JetBrains Mono','Fira Code',monospace" : "inherit",
        color: color || "var(--text-primary)",
      }}>{value}</span>
    </div>
  );
}

function GaugeMeter({ value, max, label, color }: { value: number; max: number; label: string; color: string }) {
  const pct = Math.min(100, (value / max) * 100);
  const r = 22;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width="56" height="56" viewBox="0 0 56 56">
        <circle cx="28" cy="28" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
        <circle cx="28" cy="28" r={r} fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round"
          transform="rotate(-90 28 28)" style={{ transition: "stroke-dasharray 0.8s ease" }}
        />
        <text x="28" y="32" textAnchor="middle" fill={color} fontSize="10" fontWeight="800" fontFamily="'JetBrains Mono',monospace">{value}</text>
      </svg>
      <span style={{ fontSize: "0.55rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</span>
    </div>
  );
}

function BiasChip({ tf, bias }: { tf: string; bias: string }) {
  const clr = bias === "BULLISH" ? "#22c55e" : bias === "BEARISH" ? "#ef4444" : "#71717a";
  const bg = bias === "BULLISH" ? "rgba(34,197,94,0.1)" : bias === "BEARISH" ? "rgba(239,68,68,0.1)" : "rgba(113,113,122,0.08)";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
      <span style={{ fontSize: "0.52rem", color: "var(--text-muted)", fontWeight: 700, letterSpacing: "0.04em" }}>{tf.toUpperCase()}</span>
      <span style={{ fontSize: "0.58rem", fontWeight: 800, color: clr, background: bg, border: `1px solid ${clr}33`, padding: "2px 6px", borderRadius: 4 }}>
        {bias === "BULLISH" ? "▲ BULL" : bias === "BEARISH" ? "▼ BEAR" : "— SIDE"}
      </span>
    </div>
  );
}

function IndicatorBar({ label, value, min, max, color, displayVal }: {
  label: string; value: number | null; min: number; max: number; color: string; displayVal?: string;
}) {
  const pct = value != null ? Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100)) : 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ fontSize: "0.56rem", color: "var(--text-muted)", fontWeight: 700 }}>{label}</span>
        <span style={{ fontSize: "0.6rem", fontWeight: 800, color, fontFamily: "monospace" }}>
          {displayVal ?? (value != null ? value.toFixed(1) : "—")}
        </span>
      </div>
      <div style={{ height: 4, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 2, background: color, transition: "width 0.6s ease" }} />
      </div>
    </div>
  );
}

function CheckItem({ label, active }: { label: string; active: boolean }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, padding: "5px 8px",
      borderRadius: 6, background: active ? "rgba(34,197,94,0.04)" : "transparent",
      border: `1px solid ${active ? "rgba(34,197,94,0.12)" : "rgba(255,255,255,0.04)"}`,
      transition: "all 0.2s",
    }}>
      <div style={{
        width: 14, height: 14, borderRadius: "50%", flexShrink: 0,
        background: active ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.04)",
        border: `1.5px solid ${active ? "#22c55e" : "rgba(255,255,255,0.1)"}`,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        {active && <svg width="7" height="7" viewBox="0 0 10 10"><path d="M1.5 5.5L4 8l4.5-5.5" stroke="#22c55e" strokeWidth="1.8" fill="none" strokeLinecap="round" /></svg>}
      </div>
      <span style={{ fontSize: "0.61rem", color: active ? "var(--text-primary)" : "var(--text-muted)", fontWeight: active ? 600 : 400 }}>
        {label.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────
// Markdown parser for AI output
// ─────────────────────────────────────────────────
function ParsedAnalysis({ text }: { text: string }) {
  if (!text) return null;

  const sectionColors: Record<string, string> = {
    "Narasi": "#60a5fa",
    "Justifikasi": "#a78bfa",
    "Setup Trading": "#34d399",
    "Self-Critique": "#fb923c",
    "Risiko": "#f87171",
    "Kesimpulan": "#4ade80",
    "Waktu": "#94a3b8",
  };

  const sections = text.split(/(?=### \d\.)/g);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {sections.map((sec, idx) => {
        const titleMatch = sec.match(/### \d+\.\s*(.*)/);
        const rawTitle = titleMatch ? titleMatch[1].trim() : "";
        const title = rawTitle.replace(/[^\w\sÀ-ÿ]/g, "").trim();
        const content = sec.replace(/### \d+\.\s*.*\n?/, "").trim().replace(/\*\*/g, "");

        const accentKey = Object.keys(sectionColors).find(k => rawTitle.includes(k));
        const accent = accentKey ? sectionColors[accentKey] : "#94a3b8";

        if (!rawTitle) {
          return content ? (
            <div key={idx} style={{ fontSize: "0.73rem", color: "var(--text-muted)", lineHeight: 1.7, padding: "4px 0" }}>{content}</div>
          ) : null;
        }

        const isRisk = rawTitle.includes("Self-Critique") || rawTitle.includes("Risiko");
        const isSummary = rawTitle.includes("Kesimpulan");

        if (isSummary) {
          return (
            <div key={idx} style={{
              background: "linear-gradient(135deg, rgba(74,222,128,0.08), rgba(16,185,129,0.04))",
              border: "1px solid rgba(74,222,128,0.25)", borderRadius: 10, padding: "14px 16px",
            }}>
              <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "#4ade80", letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 8 }}>
                {rawTitle}
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-primary)", lineHeight: 1.7, fontWeight: 600 }}>{content}</div>
            </div>
          );
        }

        return (
          <div key={idx} style={{
            background: isRisk ? "rgba(239,68,68,0.04)" : "rgba(255,255,255,0.02)",
            border: `1px solid ${isRisk ? "rgba(239,68,68,0.18)" : "rgba(255,255,255,0.07)"}`,
            borderLeft: `3px solid ${accent}`,
            borderRadius: 8, padding: "10px 13px",
          }}>
            <div style={{ fontSize: "0.65rem", fontWeight: 800, color: accent, letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 7 }}>
              {rawTitle}
            </div>
            <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", lineHeight: 1.75, whiteSpace: "pre-wrap" }}>{content}</div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────
export default function AIAnalysisPanel({ symbol, timeframe, isOpen, onClose }: Props) {
  const [status, setStatus] = useState<AIStatus>("idle");
  const [answer, setAnswer] = useState("");
  const [context, setContext] = useState<any>(null);
  const [setup, setSetup] = useState<SetupData | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"setup" | "macro" | "score" | "analysis">("setup");

  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isChatting, setIsChatting] = useState(false);

  const esRef = useRef<EventSource | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const answerRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const cancelStream = useCallback(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
  }, []);

  const startAnalysis = useCallback((sym: string, tf: string) => {
    cancelStream();
    setStatus("computing");
    setAnswer(""); setError(""); setSetup(null); setContext(null);
    setChatHistory([]); setChatInput(""); setIsChatting(false);

    const es = new EventSource(`${API_URL}/api/v1/ai/analyze?symbol=${sym}&timeframe=${tf}`);
    esRef.current = es;

    es.addEventListener("status", (e) => {
      const s = (e as any).data;
      if (s === "computing_indicators") setStatus("computing");
      else if (s === "ai_thinking") setStatus("thinking");
      else if (s === "cache_hit") setStatus("cached");
    });

    es.addEventListener("context", (e) => {
      try { setContext(JSON.parse((e as any).data.replace(/\\n/g, "\n"))); } catch (_) { }
    });
    es.addEventListener("setup_data", (e) => {
      try { setSetup(JSON.parse((e as any).data.replace(/\\n/g, "\n"))); } catch (_) { }
    });
    es.addEventListener("token", (e) => {
      setStatus("streaming");
      setAnswer(prev => prev + (e as any).data.replace(/\\n/g, "\n"));
    });
    es.addEventListener("done", () => { setStatus("done"); es.close(); esRef.current = null; });
    es.addEventListener("error", (e: any) => {
      const msg = (e.data || "").replace(/\\n/g, "\n");
      setError(msg || "Connection error"); setStatus("error");
      es.close(); esRef.current = null;
    });
    es.onerror = () => {
      if (status !== "done") { setError("Stream disconnected"); setStatus("error"); es.close(); esRef.current = null; }
    };
  }, [cancelStream, status]);

  const submitChat = useCallback(async () => {
    if (!chatInput.trim() || isChatting || status !== "done") return;
    const msg = chatInput.trim();
    setChatInput(""); setIsChatting(true);
    setChatHistory(prev => [...prev, { role: "user", content: msg }]);
    try {
      const resp = await fetch(`${API_URL}/api/v1/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, timeframe, question: msg, history: chatHistory.slice(-10), market_context: context }),
      });
      if (!resp.body) throw new Error("No body");
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let ai = "";
      setChatHistory(prev => [...prev, { role: "assistant", content: "" }]);
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const line of dec.decode(value).split("\n")) {
          if (line.startsWith("data: ") && !line.includes("event: done") && !line.includes("event: status")) {
            ai += line.slice(6).replace(/\\n/g, "\n");
            setChatHistory(prev => { const n = [...prev]; n[n.length - 1].content = ai; return n; });
          }
        }
      }
    } catch (e) {
      setChatHistory(prev => [...prev, { role: "assistant", content: "⚠️ Maaf, server error." }]);
    } finally { setIsChatting(false); }
  }, [chatInput, isChatting, status, symbol, timeframe, chatHistory, context]);

  useEffect(() => {
    if (!isOpen) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => startAnalysis(symbol, timeframe), 2500);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, timeframe, isOpen]);

  useEffect(() => { if (!isOpen) cancelStream(); }, [isOpen, cancelStream]);
  useEffect(() => { if (answerRef.current && tab === "analysis") answerRef.current.scrollTop = answerRef.current.scrollHeight; }, [answer, tab]);
  useEffect(() => { if (chatEndRef.current && tab === "analysis") chatEndRef.current.scrollIntoView({ behavior: "smooth" }); }, [chatHistory, isChatting, tab]);

  if (!isOpen) return null;

  const isPulsing = status === "computing" || status === "thinking" || status === "streaming";
  const htfCtx = context?.htf_biases || setup?.htf_biases || {};
  const ind = setup?.indicators || context?.indicators || {};
  const smc = setup?.smc || context?.smc || {};
  const macro = context?.macro || {};
  const news = context?.news || {};
  const orderFlow = context?.order_flow || {};
  const highlights = setup?.highlights || {};
  const score = setup?.confluence_score ?? 0;
  const maxScore = setup?.max_score ?? 33;
  const pct = setup?.confluence_pct ?? 0;

  const statusLabel: Record<AIStatus, string> = {
    idle: "Ready", computing: "Computing pipeline…", thinking: "AI deep reasoning…",
    streaming: "Streaming analysis…", done: "Complete", error: "Error", cached: "Cached",
  };

  const rsiVal = ind.rsi;
  const rsiClr = rsiVal > 70 ? "#ef4444" : rsiVal < 30 ? "#22c55e" : "#60a5fa";
  const adxVal = ind.adx;

  return (
    <div id="ai-panel" className="glass-card">
      {/* ── Header ── */}
      <div id="ai-panel-header">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div id={isPulsing ? "ai-icon-pulse" : "ai-icon"}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="3" fill="currentColor" />
              <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.93 4.93l2.12 2.12M16.95 16.95l2.12 2.12M4.93 19.07l2.12-2.12M16.95 7.05l2.12-2.12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>
          <span id="ai-panel-title">AI Analyst</span>
          <span id="ai-symbol-badge">{symbol.replace("USDT", "")}/{timeframe.toUpperCase()}</span>
          {setup?.session && (
            <span className="ai-session-tag">{setup.session.split("/")[0]}</span>
          )}
        </div>
        <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
          <button onClick={() => startAnalysis(symbol, timeframe)} className="ai-icon-btn" disabled={isPulsing} title="Re-analyze">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <path d="M3 3v5h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
          <button onClick={onClose} className="ai-close-btn">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* ── Status bar ── */}
      <div id="ai-status-bar">
        <div id="ai-status-dot" className={isPulsing ? "dot-pulse" : status === "done" ? "dot-green" : status === "error" ? "dot-red" : "dot-idle"} />
        <span id="ai-status-text">{statusLabel[status]}</span>
        {setup && (
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 60, height: 4, borderRadius: 2, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
              <div style={{
                width: `${pct}%`, height: "100%", borderRadius: 2, transition: "width 1s ease",
                background: pct >= 60 ? "#22c55e" : pct >= 35 ? "#f59e0b" : "#ef4444",
              }} />
            </div>
            <span style={{ fontSize: "0.58rem", fontWeight: 700, color: pct >= 60 ? "#4ade80" : pct >= 35 ? "#fbbf24" : "#f87171" }}>
              {score}/{maxScore}
            </span>
          </div>
        )}
      </div>

      {/* ── HTF Bias Row ── */}
      {Object.keys(htfCtx).length > 0 && (
        <div id="ai-htf-row">
          {Object.entries(htfCtx).map(([tf, bias]) => (
            <BiasChip key={tf} tf={tf} bias={bias as string} />
          ))}
        </div>
      )}

      {/* ── Error ── */}
      {status === "error" && (
        <div id="ai-error-box">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="#f87171" strokeWidth="2" />
            <path d="M12 8v4M12 16h.01" stroke="#f87171" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      {/* ── Tabs ── */}
      {(setup || answer) && (
        <div id="ai-tabs">
          {(["setup", "score", "macro", "analysis"] as const).map(t => {
            const icons = { setup: "⚡", score: "◎", macro: "🌐", analysis: "🧠" };
            const labels = { setup: "Setup", score: "Score", macro: "Macro", analysis: "Analisis" };
            return (
              <button key={t} className={`ai-tab${tab === t ? " ai-tab-active" : ""}`} onClick={() => setTab(t)}>
                <span className="tab-icon">{icons[t]}</span>
                <span>{labels[t]}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* ═══════════════════════════════════
           TAB: SETUP
      ═══════════════════════════════════ */}
      {tab === "setup" && (
        <div id="ai-setup-tab">
          {setup ? (
            <>
              {/* Signal Hero */}
              <div id="ai-signal-hero">
                <SignalPill signal={setup.signal} pct={pct} />
                {setup.signal !== "WAIT" && setup.risk_reward && (
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
                    <span style={{ fontSize: "0.55rem", color: "var(--text-muted)", fontWeight: 700, letterSpacing: "0.05em" }}>RISK REWARD</span>
                    <span style={{
                      fontSize: "1.1rem", fontWeight: 900, fontFamily: "monospace",
                      color: setup.risk_reward >= 2 ? "#4ade80" : setup.risk_reward >= 1.5 ? "#fbbf24" : "#f87171",
                    }}>1:{setup.risk_reward.toFixed(1)}</span>
                  </div>
                )}
              </div>

              {/* Gauges Row */}
              {setup.signal !== "WAIT" && (
                <div id="ai-gauges-row">
                  <GaugeMeter value={Math.round(pct)} max={100} label="Confluence" color={pct >= 60 ? "#22c55e" : pct >= 35 ? "#f59e0b" : "#ef4444"} />
                  <GaugeMeter value={rsiVal ? Math.round(rsiVal) : 0} max={100} label="RSI" color={rsiClr} />
                  <GaugeMeter value={adxVal ? Math.round(adxVal) : 0} max={60} label="ADX" color={adxVal > 25 ? "#a78bfa" : "#71717a"} />
                </div>
              )}

              {/* Price Levels */}
              {setup.signal !== "WAIT" ? (
                <div id="ai-levels-card">
                  <div className="levels-title">Trade Levels</div>
                  <PriceRow label="Entry Zone" value={`${fmt(setup.entry_low)} – ${fmt(setup.entry_high)}`} color="#60a5fa" bold />
                  <PriceRow label="Stop Loss" value={fmt(setup.stop_loss)} color="#f87171" bold />
                  <div style={{ height: 6 }} />
                  <PriceRow label="Take Profit 1" value={fmt(setup.tp1)} color="#4ade80" />
                  <PriceRow label="Take Profit 2" value={fmt(setup.tp2)} color="#34d399" />
                  <PriceRow label="Take Profit 3" value={fmt(setup.tp3)} color="#10b981" />
                  <div style={{ height: 4 }} />
                  <PriceRow label="ATR (volatility)" value={fmt(setup.atr, 6)} color="var(--text-muted)" />
                </div>
              ) : (
                <div id="ai-wait-box">
                  <div style={{ fontSize: "2rem" }}>⏸</div>
                  <div style={{ fontWeight: 800, color: "#fbbf24", fontSize: "0.85rem" }}>No Trade Zone</div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textAlign: "center", lineHeight: 1.6 }}>
                    Confluence {pct}% — insufficient for a high-probability setup. Wait for conditions to align.
                  </div>
                </div>
              )}

              {/* SMC Summary */}
              {setup.smc && (
                <div id="ai-smc-strip">
                  {[
                    { label: "Order Blocks", val: smc.unmitigated_ob_count ?? "—", color: "#a78bfa" },
                    { label: "FVGs", val: smc.unfilled_fvg_count ?? "—", color: "#60a5fa" },
                    { label: "Liq. Levels", val: smc.liquidity_levels_count ?? "—", color: "#f59e0b" },
                    { label: "P/D Zone", val: smc.pd_zone || "—", color: smc.pd_zone === "DISCOUNT" ? "#22c55e" : smc.pd_zone === "PREMIUM" ? "#ef4444" : "var(--text-muted)" },
                  ].map(({ label, val, color }) => (
                    <div key={label} className="smc-cell">
                      <span className="smc-val" style={{ color }}>{val}</span>
                      <span className="smc-label">{label}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Indicator Bars */}
              <div id="ai-ind-bars">
                <IndicatorBar label="RSI (14)" value={rsiVal} min={0} max={100} color={rsiClr} />
                <IndicatorBar label="ADX (Trend Strength)" value={adxVal} min={0} max={60} color={adxVal > 25 ? "#a78bfa" : "#71717a"} />
                <IndicatorBar label="Stoch RSI %K" value={ind.stoch_k} min={0} max={100} color="#60a5fa" />
                {ind.macd_histogram != null && (
                  <IndicatorBar
                    label="MACD Histogram"
                    value={Math.abs(ind.macd_histogram)}
                    min={0} max={Math.abs(ind.macd_histogram) * 3 || 1}
                    color={ind.macd_histogram > 0 ? "#22c55e" : "#ef4444"}
                    displayVal={`${ind.macd_histogram > 0 ? "▲" : "▼"} ${Math.abs(ind.macd_histogram).toFixed(4)}`}
                  />
                )}
                {ind.candle_pattern && ind.candle_pattern !== "None" && (
                  <div style={{ padding: "5px 0", display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontSize: "0.56rem", color: "var(--text-muted)", fontWeight: 700 }}>Candle Pattern</span>
                    <span style={{ fontSize: "0.62rem", fontWeight: 800, color: "#f59e0b" }}>{ind.candle_pattern}</span>
                  </div>
                )}
              </div>
            </>
          ) : isPulsing ? (
            <div id="ai-loading-state">
              <div className="ai-orbital">
                <div className="orbital-ring" />
                <div className="orbital-dot" />
              </div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", fontWeight: 600 }}>
                {status === "computing" ? "Running engine pipeline…" : "AI analyst reasoning…"}
              </span>
            </div>
          ) : null}
        </div>
      )}

      {/* ═══════════════════════════════════
           TAB: SCORE
      ═══════════════════════════════════ */}
      {tab === "score" && (
        <div id="ai-score-tab">
          {setup && Object.keys(highlights).length > 0 ? (
            <>
              <div id="ai-score-header">
                <div>
                  <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", fontWeight: 700, marginBottom: 4 }}>TOTAL SCORE</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: 900, fontFamily: "monospace", color: pct >= 60 ? "#4ade80" : pct >= 35 ? "#fbbf24" : "#f87171" }}>
                    {score}<span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 500 }}>/{maxScore}</span>
                  </div>
                </div>
                <svg width="70" height="70" viewBox="0 0 70 70">
                  <circle cx="35" cy="35" r="29" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="7" />
                  <circle cx="35" cy="35" r="29" fill="none"
                    stroke={pct >= 60 ? "#22c55e" : pct >= 35 ? "#f59e0b" : "#ef4444"}
                    strokeWidth="7" strokeLinecap="round"
                    strokeDasharray={`${(pct / 100) * 2 * Math.PI * 29} ${2 * Math.PI * 29 - (pct / 100) * 2 * Math.PI * 29}`}
                    transform="rotate(-90 35 35)" style={{ transition: "stroke-dasharray 1s ease" }}
                  />
                  <text x="35" y="40" textAnchor="middle" fill="var(--text-primary)" fontSize="13" fontWeight="800" fontFamily="monospace">{pct}%</text>
                </svg>
              </div>
              <div id="ai-checklist">
                {Object.entries(highlights).map(([key, val]) => (
                  <CheckItem key={key} label={key} active={val as boolean} />
                ))}
              </div>
            </>
          ) : (
            <div id="ai-loading-state">
              <div className="ai-spinner" />
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>Loading confluence data…</span>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════
           TAB: MACRO
      ═══════════════════════════════════ */}
      {tab === "macro" && (
        <div id="ai-macro-tab">
          {macro && Object.keys(macro).length > 0 ? (
            <>
              {/* SMART MONEY (Whales) Strip — always visible */}
              {(() => {
                const hasData = orderFlow && orderFlow.buy_pct != null;
                const dom = hasData ? orderFlow.dominance : "NEUTRAL";
                const domColor = dom === "BUY" ? "#4ade80" : dom === "SELL" ? "#f87171" : "var(--text-muted)";
                const stripBg = dom === "BUY"
                  ? "linear-gradient(90deg, rgba(34,197,94,0.1), rgba(21,128,61,0.05))"
                  : dom === "SELL"
                  ? "linear-gradient(90deg, rgba(239,68,68,0.1), rgba(153,27,27,0.05))"
                  : "rgba(255,255,255,0.03)";
                const stripBorder = dom === "BUY"
                  ? "rgba(34,197,94,0.3)"
                  : dom === "SELL"
                  ? "rgba(239,68,68,0.3)"
                  : "var(--border)";

                return (
                  <div style={{
                    margin: "0 0 12px 0", padding: "10px",
                    background: stripBg,
                    border: `1px solid ${stripBorder}`,
                    borderRadius: 8, display: "flex", flexDirection: "column", gap: 6
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "0.6rem", fontWeight: 800, letterSpacing: "0.05em", color: "var(--text-primary)" }}>
                        🐋 SMART MONEY FLOW (Binance)
                      </span>
                      <span style={{ fontSize: "0.65rem", fontWeight: 900, color: domColor }}>
                        {hasData ? `${dom} DOMINANCE` : "LOADING…"}
                      </span>
                    </div>

                    {hasData ? (
                      <>
                        <div style={{ display: "flex", gap: 12 }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: "0.55rem", color: "var(--text-muted)" }}>Total Volume Delta</div>
                            <div style={{ fontSize: "0.9rem", fontWeight: 800, fontFamily: "monospace", color: orderFlow.delta_usd > 0 ? "#4ade80" : "#f87171" }}>
                              {orderFlow.delta_usd > 0 ? "+" : ""}{(orderFlow.delta_usd ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })} USD
                            </div>
                          </div>
                          <div style={{ flex: 1, borderLeft: "1px solid rgba(255,255,255,0.1)", paddingLeft: 12 }}>
                            <div style={{ fontSize: "0.55rem", color: "var(--text-muted)" }}>Whale (&gt;$50k) / Shark (&gt;$10k)</div>
                            <div style={{ fontSize: "0.85rem", fontWeight: 800, display: "flex", gap: 6 }}>
                              <span>🐋</span>
                              <span style={{ color: "#4ade80" }}>{orderFlow.whale_buy_count ?? 0}B</span>
                              <span style={{ color: "#f87171" }}>{orderFlow.whale_sell_count ?? 0}S</span>
                              <span style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>|</span>
                              <span>🦈</span>
                              <span style={{ color: "#4ade80" }}>{orderFlow.shark_buy_count ?? 0}B</span>
                              <span style={{ color: "#f87171" }}>{orderFlow.shark_sell_count ?? 0}S</span>
                            </div>
                          </div>
                        </div>
                        {/* Buy/Sell pressure bar */}
                        <div style={{ height: 4, borderRadius: 2, display: "flex", overflow: "hidden", marginTop: 2 }}>
                          <div style={{ width: `${orderFlow.buy_pct ?? 50}%`, background: "#22c55e", transition: "width 0.8s ease" }} />
                          <div style={{ width: `${orderFlow.sell_pct ?? 50}%`, background: "#ef4444", transition: "width 0.8s ease" }} />
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                          <span style={{ fontSize: "0.55rem", color: "#4ade80" }}>BUY {orderFlow.buy_pct ?? 50}%</span>
                          <span style={{ fontSize: "0.55rem", color: "#f87171" }}>SELL {orderFlow.sell_pct ?? 50}%</span>
                        </div>
                      </>
                    ) : (
                      <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                        Memuat data aliran smart money dari Binance…
                      </div>
                    )}
                  </div>
                );
              })()}



              {/* Macro cards */}
              <div id="ai-macro-grid">
                {[
                  {
                    label: "BTC Dominance", val: macro.btc_dominance ? `${macro.btc_dominance}%` : "N/A",
                    sub: macro.btc_dominance > 52 ? "Altcoin pressure ↑" : macro.btc_dominance < 45 ? "Alt season signal" : "Neutral",
                    color: macro.btc_dominance > 52 ? "#ef4444" : macro.btc_dominance < 45 ? "#22c55e" : "var(--text-muted)",
                  },
                  {
                    label: "Fear & Greed", val: macro.fear_greed_value ?? "—",
                    sub: macro.fear_greed_label || "N/A",
                    color: macro.fear_greed_value > 75 ? "#ef4444" : macro.fear_greed_value < 30 ? "#22c55e" : "#f59e0b",
                  },
                  {
                    label: "Funding Rate", val: macro.funding_rate ? `${(macro.funding_rate * 100).toFixed(4)}%` : "N/A",
                    sub: macro.funding_label || "N/A",
                    color: macro.funding_rate > 0.0005 ? "#ef4444" : macro.funding_rate < -0.0005 ? "#22c55e" : "var(--text-muted)",
                  },
                  {
                    label: "DXY Index", val: macro.dxy_value ?? "N/A",
                    sub: macro.dxy_change_1d ? `${macro.dxy_change_1d > 0 ? "+" : ""}${macro.dxy_change_1d}% 1d` : "N/A",
                    color: (macro.dxy_change_1d || 0) > 0 ? "#ef4444" : "#22c55e",
                  },
                  {
                    label: "L/S Ratio", val: macro.ls_ratio ?? "N/A",
                    sub: macro.ls_interpretation || "N/A",
                    color: "var(--text-primary)",
                  },
                  {
                    label: "Market Cap", val: macro.total_market_cap_b ? `$${macro.total_market_cap_b}B` : "N/A",
                    sub: macro.market_cap_change_24h ? `${macro.market_cap_change_24h > 0 ? "+" : ""}${macro.market_cap_change_24h}% 24h` : "",
                    color: (macro.market_cap_change_24h || 0) > 0 ? "#22c55e" : "#ef4444",
                  },
                ].map(({ label, val, sub, color }) => (
                  <div key={label} className="macro-card">
                    <span className="macro-label">{label}</span>
                    <span className="macro-val" style={{ color }}>{val}</span>
                    <span className="macro-sub">{sub}</span>
                  </div>
                ))}
              </div>

              {/* Forex News */}
              <div className="news-section-title">Forex High Impact</div>
              {news.high_impact_forex?.length > 0 ? news.high_impact_forex.map((n: any, i: number) => (
                <div key={i} className="news-item">
                  <span className="news-badge fx">{n.currency}</span>
                  <div className="news-body">
                    <div className="news-title">{n.title}</div>
                    <div className="news-meta">{n.time}{n.forecast ? ` · F: ${n.forecast}` : ""}</div>
                  </div>
                </div>
              )) : <div className="news-empty">Tidak ada event high-impact dalam 24 jam.</div>}

              {/* Crypto News */}
              <div className="news-section-title" style={{ marginTop: 12 }}>Berita Kripto</div>
              {news.crypto_news?.length > 0 ? news.crypto_news.map((n: any, i: number) => (
                <div key={i} className="news-item">
                  <span className={`news-badge ${n.sentiment === "POSITIF" ? "bull" : n.sentiment === "NEGATIF" ? "bear" : "neut"}`}>
                    {n.sentiment === "POSITIF" ? "↑" : n.sentiment === "NEGATIF" ? "↓" : "–"}
                  </span>
                  <div className="news-body">
                    <div className="news-title">{n.title}</div>
                    <div className="news-meta">{n.source}</div>
                  </div>
                </div>
              )) : <div className="news-empty">Tidak ada berita relevan.</div>}
            </>
          ) : (
            <div id="ai-loading-state">
              <div className="ai-spinner" />
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>Memuat data makro…</span>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════
           TAB: ANALYSIS + CHAT
      ═══════════════════════════════════ */}
      {tab === "analysis" && (
        <div id="ai-analysis-tab">
          <div id="ai-answer-box" ref={answerRef}>
            {answer ? (
              status === "done" ? (
                <ParsedAnalysis text={answer} />
              ) : (
                <div className="stream-bubble">
                  <div className="stream-header">AI Analyst <span style={{ color: "#a78bfa" }}>·</span> Streaming…</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", lineHeight: 1.75, whiteSpace: "pre-wrap" }}>
                    {answer}<span id="ai-cursor">▌</span>
                  </div>
                </div>
              )
            ) : isPulsing ? (
              <div id="ai-thinking-indicator">
                <div className="ai-dots"><span /><span /><span /></div>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600 }}>
                  {status === "thinking" ? "AI deep reasoning in progress…" : "Streaming expert analysis…"}
                </span>
              </div>
            ) : null}

            {chatHistory.map((msg, idx) => (
              <div key={idx} className={`chat-bubble ${msg.role === "user" ? "user-bubble" : "ai-bubble"}`}>
                <div className="bubble-header">{msg.role === "user" ? "You" : "AI Analyst"}</div>
                <div className="bubble-content">{msg.content || <span className="ai-cursor">▌</span>}</div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {status === "done" && (
            <div id="ai-chat-bar">
              <input
                type="text" placeholder="Tanya lebih lanjut…" value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") submitChat(); }}
                disabled={isChatting} className="ai-chat-input"
              />
              <button onClick={submitChat} disabled={isChatting || !chatInput.trim()} className="ai-send-btn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Styles ── */}
      <style>{`
        #ai-panel {
          width: 340px; flex-shrink: 0; display: flex; flex-direction: column;
          overflow: hidden; padding: 0;
          animation: aiSlideIn 0.25s cubic-bezier(0.22, 1, 0.36, 1);
        }
        @keyframes aiSlideIn { from { opacity:0; transform:translateX(16px); } to { opacity:1; transform:translateX(0); } }

        /* ── Header ── */
        #ai-panel-header {
          display: flex; justify-content: space-between; align-items: center;
          padding: 10px 12px 9px;
          border-bottom: 1px solid var(--border);
          background: linear-gradient(135deg, rgba(139,92,246,0.1), rgba(59,130,246,0.06));
          flex-shrink: 0;
        }
        #ai-panel-title { font-size: 0.75rem; font-weight: 800; color: var(--text-primary); letter-spacing: 0.02em; }
        #ai-symbol-badge {
          font-size: 0.62rem; font-weight: 700; padding: 2px 7px; border-radius: 5px;
          background: rgba(139,92,246,0.15); color: #a78bfa; border: 1px solid rgba(139,92,246,0.3);
        }
        .ai-session-tag {
          font-size: 0.56rem; padding: 1px 6px; border-radius: 4px;
          background: rgba(59,130,246,0.12); color: #60a5fa; border: 1px solid rgba(59,130,246,0.25);
          font-weight: 700;
        }
        #ai-icon { color: #a78bfa; display: flex; align-items: center; }
        #ai-icon-pulse { color: #a78bfa; display: flex; align-items: center; animation: aiIconPulse 1.5s ease-in-out infinite; }
        @keyframes aiIconPulse { 0%,100%{transform:scale(1);opacity:1} 50%{transform:scale(1.3);opacity:0.6} }

        .ai-icon-btn {
          width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
          border-radius: 7px; border: 1px solid rgba(139,92,246,0.3);
          background: rgba(139,92,246,0.1); color: #a78bfa; cursor: pointer; transition: all 0.15s;
        }
        .ai-icon-btn:hover:not(:disabled) { background: rgba(139,92,246,0.22); transform: rotate(-15deg); }
        .ai-icon-btn:disabled { opacity: 0.35; cursor: not-allowed; }
        .ai-close-btn {
          width: 26px; height: 26px; display: flex; align-items: center; justify-content: center;
          border-radius: 6px; border: 1px solid rgba(255,255,255,0.08);
          background: transparent; color: var(--text-muted); cursor: pointer; transition: all 0.15s;
        }
        .ai-close-btn:hover { color: #f87171; border-color: rgba(239,68,68,0.25); background: rgba(239,68,68,0.08); }

        /* ── Status bar ── */
        #ai-status-bar {
          display: flex; align-items: center; gap: 6px; padding: 5px 12px;
          background: rgba(0,0,0,0.25); flex-shrink: 0; border-bottom: 1px solid var(--border);
        }
        #ai-status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
        .dot-pulse { background: #a78bfa; animation: dotPulse 1s ease-in-out infinite; }
        .dot-green { background: #22c55e; }
        .dot-red { background: #ef4444; }
        .dot-idle { background: rgba(255,255,255,0.2); }
        @keyframes dotPulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.35;transform:scale(0.65)} }
        #ai-status-text { font-size: 0.6rem; font-weight: 600; color: var(--text-muted); letter-spacing: 0.04em; }

        /* ── HTF row ── */
        #ai-htf-row {
          display: flex; gap: 8px; padding: 7px 12px; border-bottom: 1px solid var(--border);
          flex-shrink: 0; background: rgba(0,0,0,0.18); flex-wrap: wrap; align-items: center;
        }

        /* ── Error ── */
        #ai-error-box {
          display: flex; align-items: center; gap: 8px; padding: 9px 12px; margin: 8px 12px;
          border-radius: 8px; background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2);
          color: #f87171; font-size: 0.72rem; flex-shrink: 0;
        }

        /* ── Tabs ── */
        #ai-tabs { display: flex; border-bottom: 1px solid var(--border); flex-shrink: 0; }
        .ai-tab {
          flex: 1; padding: 8px 2px; font-size: 0.6rem; font-weight: 700; border: none;
          background: transparent; color: var(--text-muted); cursor: pointer;
          border-bottom: 2px solid transparent; display: flex; flex-direction: column;
          align-items: center; gap: 2px; transition: all 0.15s;
        }
        .tab-icon { font-size: 0.8rem; }
        .ai-tab:hover { color: var(--text-primary); background: rgba(255,255,255,0.02); }
        .ai-tab-active { color: #a78bfa; border-bottom-color: #a78bfa; background: rgba(139,92,246,0.06); }

        /* ── SETUP TAB ── */
        #ai-setup-tab { flex: 1; overflow-y: auto; display: flex; flex-direction: column; padding-bottom: 8px; }
        #ai-signal-hero {
          display: flex; align-items: center; justify-content: space-between;
          padding: 12px 14px 10px;
        }
        #ai-gauges-row {
          display: flex; justify-content: space-around; padding: 8px 12px 6px;
          border-top: 1px solid rgba(255,255,255,0.04); border-bottom: 1px solid rgba(255,255,255,0.04);
          background: rgba(0,0,0,0.15);
        }
        #ai-levels-card {
          margin: 8px 10px 4px; padding: 10px 12px;
          background: rgba(0,0,0,0.25); border-radius: 10px; border: 1px solid var(--border);
          display: flex; flex-direction: column; gap: 1px;
        }
        .levels-title {
          font-size: 0.58rem; font-weight: 800; color: var(--text-muted); letter-spacing: 0.07em;
          text-transform: uppercase; margin-bottom: 6px;
        }
        #ai-smc-strip {
          display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin: 4px 10px;
          padding: 7px 8px; background: rgba(0,0,0,0.18); border-radius: 8px; border: 1px solid var(--border);
        }
        .smc-cell { display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 3px; }
        .smc-val { font-size: 0.82rem; font-weight: 900; }
        .smc-label { font-size: 0.52rem; color: var(--text-muted); font-weight: 600; text-align: center; }
        #ai-ind-bars { padding: 6px 12px 4px; display: flex; flex-direction: column; gap: 8px; }
        #ai-wait-box {
          display: flex; flex-direction: column; align-items: center; padding: 24px 16px; gap: 8px;
          margin: 10px; border-radius: 12px;
          background: rgba(234,179,8,0.06); border: 1px solid rgba(234,179,8,0.18);
        }

        /* ── SCORE TAB ── */
        #ai-score-tab { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
        #ai-score-header {
          display: flex; justify-content: space-between; align-items: center;
          padding: 14px 16px; border-bottom: 1px solid var(--border);
          background: rgba(0,0,0,0.2);
        }
        #ai-checklist { padding: 8px 10px; display: flex; flex-direction: column; gap: 4px; }

        /* ── MACRO TAB ── */
        #ai-macro-tab { flex: 1; overflow-y: auto; padding: 10px 10px; display: flex; flex-direction: column; gap: 0; }
        #ai-macro-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-bottom: 14px; }
        .macro-card {
          background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: 9px;
          padding: 9px 8px; display: flex; flex-direction: column; gap: 3px;
        }
        .macro-label { font-size: 0.52rem; color: var(--text-muted); font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; }
        .macro-val { font-size: 0.88rem; font-weight: 900; font-family: 'JetBrains Mono',monospace; }
        .macro-sub { font-size: 0.52rem; color: var(--text-muted); }
        .news-section-title { font-size: 0.58rem; font-weight: 800; color: var(--text-muted); letter-spacing: 0.07em; text-transform: uppercase; margin-bottom: 6px; }
        .news-item { display: flex; gap: 8px; align-items: flex-start; padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
        .news-badge { flex-shrink: 0; padding: 2px 5px; border-radius: 4px; font-size: 0.58rem; font-weight: 800; }
        .news-badge.fx { background: rgba(139,92,246,0.2); color: #a78bfa; border: 1px solid rgba(139,92,246,0.3); }
        .news-badge.bull { background: rgba(34,197,94,0.15); color: #4ade80; }
        .news-badge.bear { background: rgba(239,68,68,0.15); color: #f87171; }
        .news-badge.neut { background: rgba(161,161,170,0.12); color: #a1a1aa; }
        .news-body { display: flex; flex-direction: column; gap: 2px; }
        .news-title { font-size: 0.64rem; color: var(--text-primary); line-height: 1.4; }
        .news-meta { font-size: 0.52rem; color: var(--text-muted); }
        .news-empty { font-size: 0.62rem; color: var(--text-muted); font-style: italic; padding: 8px; text-align: center; border: 1px dashed var(--border); border-radius: 6px; }

        /* ── ANALYSIS TAB ── */
        #ai-analysis-tab { display: flex; flex-direction: column; flex: 1; overflow: hidden; }
        #ai-answer-box { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; }
        .stream-bubble { padding: 10px 14px; border-radius: 10px; background: rgba(167,139,250,0.07); border: 1px solid rgba(167,139,250,0.18); }
        .stream-header { font-size: 0.6rem; font-weight: 700; color: #a78bfa; margin-bottom: 6px; letter-spacing: 0.05em; }
        .chat-bubble { padding: 9px 12px; border-radius: 9px; font-size: 0.72rem; line-height: 1.65; word-break: break-word; }
        .ai-bubble { background: rgba(167,139,250,0.07); border: 1px solid rgba(167,139,250,0.18); color: var(--text-secondary); }
        .user-bubble { background: rgba(255,255,255,0.04); border: 1px solid var(--border); color: var(--text-primary); align-self: flex-end; margin-left: 20px; }
        .bubble-header { font-size: 0.58rem; font-weight: 700; margin-bottom: 5px; color: var(--text-muted); letter-spacing: 0.04em; text-transform: uppercase; }
        .bubble-content { white-space: pre-wrap; }

        #ai-chat-bar {
          display: flex; gap: 8px; padding: 10px 12px;
          border-top: 1px solid var(--border); background: rgba(0,0,0,0.25); flex-shrink: 0;
        }
        .ai-chat-input {
          flex: 1; background: rgba(0,0,0,0.35); border: 1px solid var(--border); border-radius: 20px;
          padding: 8px 14px; color: var(--text-primary); font-size: 0.7rem; outline: none; transition: border-color 0.2s;
        }
        .ai-chat-input:focus { border-color: rgba(139,92,246,0.6); }
        .ai-send-btn {
          width: 34px; height: 34px; border-radius: 50%; background: linear-gradient(135deg,#7c3aed,#a78bfa);
          color: #fff; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center;
          transition: all 0.15s; flex-shrink: 0; box-shadow: 0 0 12px rgba(139,92,246,0.3);
        }
        .ai-send-btn:hover:not(:disabled) { transform: scale(1.08); box-shadow: 0 0 18px rgba(139,92,246,0.45); }
        .ai-send-btn:disabled { opacity: 0.45; cursor: not-allowed; box-shadow: none; }

        /* ── Loading States ── */
        #ai-loading-state {
          flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; padding: 40px 20px;
        }
        .ai-orbital { position: relative; width: 40px; height: 40px; }
        .orbital-ring {
          position: absolute; inset: 0; border-radius: 50%;
          border: 2px solid transparent; border-top-color: #a78bfa; border-right-color: rgba(167,139,250,0.3);
          animation: spin 1s linear infinite;
        }
        .orbital-dot {
          position: absolute; top: 3px; left: 50%; transform: translateX(-50%);
          width: 5px; height: 5px; border-radius: 50%; background: #a78bfa;
          box-shadow: 0 0 8px #a78bfa;
        }
        .ai-spinner {
          width: 28px; height: 28px; border: 2.5px solid rgba(255,255,255,0.08);
          border-top-color: #a78bfa; border-radius: 50%; animation: spin 0.9s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        #ai-thinking-indicator { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; padding: 30px; }
        .ai-dots { display: flex; gap: 7px; }
        .ai-dots span { width: 9px; height: 9px; border-radius: 50%; background: #a78bfa; animation: dotBounce 1.2s ease-in-out infinite; }
        .ai-dots span:nth-child(1) { animation-delay: 0s; }
        .ai-dots span:nth-child(2) { animation-delay: 0.22s; }
        .ai-dots span:nth-child(3) { animation-delay: 0.44s; }
        @keyframes dotBounce { 0%,80%,100%{transform:scale(0.55);opacity:0.35} 40%{transform:scale(1);opacity:1} }

        #ai-cursor, .ai-cursor { display: inline-block; color: #a78bfa; animation: blink 1s step-end infinite; }
        @keyframes blink { 50% { opacity: 0; } }
      `}</style>
    </div>
  );
}
