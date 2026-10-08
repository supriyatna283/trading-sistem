"use client";

import { useState, useCallback, useEffect } from "react";
import { API_URL } from "@/lib/utils";

interface SizingResult {
  position_size: number;
  position_value: number;
  risk_amount: number;
  risk_pct: number;
  stop_distance: number;
  stop_distance_pct: number;
  take_profit_1: number | null;
  take_profit_2: number | null;
  take_profit_3: number | null;
  rr_1: number | null;
  rr_2: number | null;
  rr_3: number | null;
  kelly: {
    full_kelly_pct: number;
    quarter_kelly_pct: number;
    recommended_risk_pct: number;
  };
  risk_metrics: {
    risk_of_ruin_pct: number;
    max_consecutive_losses: number;
    breakeven_win_rate: number;
    expected_value: number;
  };
  leverage_sizes: { "1x": number; "5x": number; "10x": number };
  size_grade: string;
  warnings: string[];
}

const GRADE_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  OPTIMAL:      { color: "#10b981", bg: "rgba(16,185,129,0.12)",  label: "✅ OPTIMAL" },
  MODERATE:     { color: "#3b82f6", bg: "rgba(59,130,246,0.12)",  label: "📊 MODERATE" },
  CONSERVATIVE: { color: "#a78bfa", bg: "rgba(167,139,250,0.12)", label: "🛡️ CONSERVATIVE" },
  AGGRESSIVE:   { color: "#ef4444", bg: "rgba(239,68,68,0.12)",   label: "🚨 AGGRESSIVE" },
};

function GaugeArc({ value, max = 100, color }: { value: number; max?: number; color: string }) {
  const pct  = Math.min(1, value / max);
  const r    = 36;
  const circ = Math.PI * r;   // half-circle circumference
  const dash = pct * circ;

  return (
    <svg width={90} height={52} viewBox="0 0 90 52">
      {/* Track */}
      <path d={`M 9 45 A ${r} ${r} 0 0 1 81 45`} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={10} strokeLinecap="round" />
      {/* Fill */}
      <path
        d={`M 9 45 A ${r} ${r} 0 0 1 81 45`}
        fill="none" stroke={color} strokeWidth={10} strokeLinecap="round"
        strokeDasharray={`${dash} ${circ}`}
        style={{ transition: "stroke-dasharray 0.8s cubic-bezier(0.34,1.56,0.64,1)" }}
      />
      <text x="45" y="44" textAnchor="middle" fontSize="12" fontWeight="800" fill={color} fontFamily="JetBrains Mono, monospace">
        {value.toFixed(1)}
      </text>
    </svg>
  );
}

export function PositionSizingCalculator() {
  const [form, setForm] = useState({
    account_balance: typeof window !== "undefined" ? (localStorage.getItem("psCalc_balance") || "") : "",
    risk_pct: "1",
    entry: "",
    stop_loss: "",
    take_profit_1: "",
    take_profit_2: "",
    take_profit_3: "",
    direction: "BUY",
    win_rate: "55",
    avg_rr: "2",
  });
  const [result, setResult] = useState<SizingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  // Persist account balance to localStorage
  useEffect(() => {
    if (form.account_balance) {
      localStorage.setItem("psCalc_balance", form.account_balance);
    }
  }, [form.account_balance]);

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  // Preset risk profiles
  const applyPreset = (preset: "conservative" | "moderate" | "aggressive") => {
    const presets = {
      conservative: { risk_pct: "0.5",  win_rate: "60", avg_rr: "2.5" },
      moderate:     { risk_pct: "1.0",  win_rate: "55", avg_rr: "2.0" },
      aggressive:   { risk_pct: "2.0",  win_rate: "50", avg_rr: "1.5" },
    };
    setForm(f => ({ ...f, ...presets[preset] }));
  };

  const calculate = useCallback(async () => {
    const { account_balance, risk_pct, entry, stop_loss } = form;
    if (!account_balance || !entry || !stop_loss) {
      setError("Fill Account Balance, Entry, and Stop Loss.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const tps: number[] = [];
      if (form.take_profit_1) tps.push(parseFloat(form.take_profit_1));
      if (form.take_profit_2) tps.push(parseFloat(form.take_profit_2));
      if (form.take_profit_3) tps.push(parseFloat(form.take_profit_3));

      const body: any = {
        account_balance: parseFloat(account_balance),
        risk_pct:        parseFloat(risk_pct),
        entry:           parseFloat(entry),
        stop_loss:       parseFloat(stop_loss),
        direction:       form.direction,
        win_rate:        parseFloat(form.win_rate) / 100,
        avg_rr:          parseFloat(form.avg_rr),
      };
      if (tps.length > 0) body.take_profits = tps;

      const res  = await fetch(`${API_URL}/api/v1/pro/position-size`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        setError(err.detail || `HTTP ${res.status}`);
        return;
      }
      const json = await res.json();
      if (json.result) setResult(json.result);
      else setError(json.error ?? "Calculation failed");
    } catch (e: any) {
      setError(e.message ?? "Error");
    } finally {
      setLoading(false);
    }
  }, [form]);

  const grad = result ? GRADE_CONFIG[result.size_grade] ?? GRADE_CONFIG.MODERATE : null;
  const rorColor = result
    ? (result.risk_metrics.risk_of_ruin_pct < 5 ? "#10b981" : result.risk_metrics.risk_of_ruin_pct < 20 ? "#f59e0b" : "#ef4444")
    : "#64748b";

  const inputStyle: React.CSSProperties = {
    width: "100%", background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8,
    padding: "9px 12px", color: "#fff", fontSize: "0.82rem",
    fontFamily: "'JetBrains Mono', monospace", outline: "none",
    boxSizing: "border-box",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: "0.62rem", fontWeight: 700, color: "var(--text-muted)",
    textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4, display: "block",
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
      {/* ── LEFT: Input Form ── */}
      <div style={{ padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
          <div style={{ width: 4, height: 20, borderRadius: 99, background: "linear-gradient(180deg,#3b82f6,#a78bfa)" }} />
          <span style={{ fontWeight: 800, fontSize: "0.95rem" }}>Position Size Calculator</span>
        </div>

        {/* Direction toggle */}
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>Direction</label>
          <div style={{ display: "flex", gap: 8 }}>
            {["BUY", "SELL"].map(d => (
              <button key={d} onClick={() => set("direction", d)} style={{
                flex: 1, padding: "8px 0", borderRadius: 8, fontWeight: 800, fontSize: "0.78rem",
                cursor: "pointer", transition: "all 0.2s",
                background: form.direction === d
                  ? (d === "BUY" ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)")
                  : "rgba(255,255,255,0.04)",
                border: form.direction === d
                  ? `1px solid ${d === "BUY" ? "#10b981" : "#ef4444"}`
                  : "1px solid rgba(255,255,255,0.08)",
                color: form.direction === d ? (d === "BUY" ? "#10b981" : "#ef4444") : "var(--text-muted)",
              }}>{d === "BUY" ? "▲ BUY" : "▼ SELL"}</button>
            ))}
          </div>
        </div>

        {/* Risk Preset Buttons */}
        <div style={{ marginBottom: 14 }}>
          <label style={labelStyle}>⚡ Quick Preset</label>
          <div style={{ display: "flex", gap: 6 }}>
            {[
              { label: "🛡️ Conservative", preset: "conservative" as const, color: "#a78bfa" },
              { label: "📊 Moderate",     preset: "moderate"     as const, color: "#3b82f6" },
              { label: "🚨 Aggressive",   preset: "aggressive"   as const, color: "#ef4444" },
            ].map(({ label, preset, color }) => (
              <button key={preset} onClick={() => applyPreset(preset)} style={{
                flex: 1, padding: "6px 4px", borderRadius: 7, fontSize: "0.6rem", fontWeight: 700,
                cursor: "pointer", border: `1px solid ${color}30`,
                background: `${color}10`, color, transition: "all 0.2s",
              }}
                onMouseEnter={e => (e.currentTarget.style.background = `${color}20`)}
                onMouseLeave={e => (e.currentTarget.style.background = `${color}10`)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Inputs */}
        {[
          { key: "account_balance", label: "Account Balance (USDT)", placeholder: "e.g. 10000", icon: "💰" },
          { key: "risk_pct",        label: "Risk per Trade (%)",     placeholder: "e.g. 1.0",  icon: "⚠️" },
          { key: "entry",           label: "Entry Price",            placeholder: "e.g. 64000", icon: "🎯" },
          { key: "stop_loss",       label: "Stop Loss",              placeholder: "e.g. 63000", icon: "🛑" },
        ].map(({ key, label, placeholder, icon }) => (
          <div key={key} style={{ marginBottom: 12 }}>
            <label style={labelStyle}>{icon} {label}</label>
            <input
              type="number" value={(form as any)[key]} placeholder={placeholder}
              onChange={e => set(key, e.target.value)} style={inputStyle}
            />
          </div>
        ))}

        {/* Take Profits — Bug #3 fix: TP1/TP2/TP3 */}
        <div style={{ marginBottom: 12 }}>
          <label style={labelStyle}>✅ Take Profits (optional)</label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
            {["take_profit_1", "take_profit_2", "take_profit_3"].map((key, i) => (
              <input
                key={key}
                type="number" value={(form as any)[key]}
                placeholder={`TP${i + 1}`}
                onChange={e => set(key, e.target.value)}
                style={{ ...inputStyle, borderColor: ["rgba(16,185,129,0.3)", "rgba(16,185,129,0.2)", "rgba(167,139,250,0.2)"][i] }}
              />
            ))}
          </div>
          <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", marginTop: 4 }}>Kosongkan untuk auto-kalkulasi dari R:R</div>
        </div>

        {/* Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>Win Rate (%)</label>
            <input type="number" value={form.win_rate} onChange={e => set("win_rate", e.target.value)} style={inputStyle} placeholder="55" min={1} max={99} />
          </div>
          <div>
            <label style={labelStyle}>Avg R:R</label>
            <input type="number" value={form.avg_rr} onChange={e => set("avg_rr", e.target.value)} style={inputStyle} placeholder="2.0" step={0.1} min={0.1} />
          </div>
        </div>

        {error && <div style={{ color: "#ef4444", fontSize: "0.75rem", marginBottom: 12, padding: "8px 12px", background: "rgba(239,68,68,0.1)", borderRadius: 8 }}>{error}</div>}

        <button
          onClick={calculate} disabled={loading}
          style={{
            width: "100%", padding: "12px", borderRadius: 10, fontWeight: 800, fontSize: "0.85rem",
            cursor: loading ? "not-allowed" : "pointer", border: "none",
            background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
            color: "#fff", opacity: loading ? 0.7 : 1, transition: "all 0.2s",
            boxShadow: "0 4px 20px rgba(59,130,246,0.3)",
          }}
        >
          {loading ? "⟳ Calculating..." : "🧮 Calculate Position Size"}
        </button>
      </div>

      {/* ── RIGHT: Results ── */}
      <div style={{ padding: 24, borderRadius: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
        {!result ? (
          <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
            <div style={{ fontSize: "3rem", marginBottom: 12, opacity: 0.4 }}>⚖️</div>
            <div style={{ fontSize: "0.82rem" }}>Enter trade parameters and click Calculate</div>
          </div>
        ) : (
          <div>
            {/* Grade Badge */}
            {grad && (
              <div style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                padding: "8px 16px", borderRadius: 20, marginBottom: 20,
                background: grad.bg, border: `1px solid ${grad.color}40`,
                fontSize: "0.78rem", fontWeight: 800, color: grad.color,
              }}>
                {grad.label}
              </div>
            )}

            {/* Primary Result */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
              <div style={{ gridColumn: "1 / -1", padding: 16, borderRadius: 10, background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.2)", textAlign: "center" }}>
                <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.1em" }}>Position Size</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "1.8rem", fontWeight: 900, color: "#3b82f6" }}>
                  {result.position_size.toFixed(4)}
                </div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                  ≈ ${result.position_value.toLocaleString("en", { maximumFractionDigits: 0 })} USDT
                </div>
              </div>

              {[
                { label: "Risk Amount",  value: `$${result.risk_amount.toFixed(2)}`, color: "#ef4444" },
                { label: "Stop Dist",    value: `${result.stop_distance_pct.toFixed(2)}%`, color: "#f59e0b" },
                { label: "EV / Trade",   value: `$${result.risk_metrics.expected_value.toFixed(2)}`, color: result.risk_metrics.expected_value > 0 ? "#10b981" : "#ef4444" },
                { label: "Break WR",     value: `${result.risk_metrics.breakeven_win_rate}%`, color: "#6366f1" },
              ].map(f => (
                <div key={f.label} style={{ padding: "12px", borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: "0.55rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>{f.label}</div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.85rem", fontWeight: 800, color: f.color }}>{f.value}</div>
                </div>
              ))}
            </div>

            {/* Bug #3 fix: TP1 / TP2 / TP3 panel */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: "0.62rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>Take Profit Levels</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                {[
                  { label: "TP1",  price: result.take_profit_1, rr: result.rr_1, color: "#10b981", icon: "✅" },
                  { label: "TP2",  price: result.take_profit_2, rr: result.rr_2, color: "#10b981", icon: "✅" },
                  { label: "TP3",  price: result.take_profit_3, rr: result.rr_3, color: "#a78bfa", icon: "🏆" },
                ].map(tp => (
                  <div key={tp.label} style={{ padding: "10px 8px", borderRadius: 10, background: tp.price ? `${tp.color}08` : "rgba(255,255,255,0.02)", border: `1px solid ${tp.price ? tp.color + "25" : "rgba(255,255,255,0.07)"}`, textAlign: "center" }}>
                    <div style={{ fontSize: "0.52rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 3 }}>{tp.icon} {tp.label}</div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.7rem", fontWeight: 900, color: tp.price ? tp.color : "#334155" }}>
                      {tp.price ? tp.price.toLocaleString("en", { maximumFractionDigits: 5 }) : "—"}
                    </div>
                    <div style={{ fontSize: "0.5rem", color: tp.rr ? tp.color : "var(--text-muted)", marginTop: 2 }}>
                      {tp.rr ? `R:R 1:${tp.rr}` : "—"}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Kelly + Risk of Ruin Gauges */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 }}>
              <div style={{ padding: 12, borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", textAlign: "center" }}>
                <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", marginBottom: 4, fontWeight: 700 }}>¼-KELLY RECOMMEND</div>
                <GaugeArc value={result.kelly.quarter_kelly_pct} max={10} color="#a78bfa" />
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>Optimal: <span style={{ color: "#a78bfa" }}>{result.kelly.recommended_risk_pct.toFixed(2)}%</span></div>
              </div>
              <div style={{ padding: 12, borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", textAlign: "center" }}>
                <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", marginBottom: 4, fontWeight: 700 }}>RISK OF RUIN</div>
                <GaugeArc value={result.risk_metrics.risk_of_ruin_pct} max={100} color={rorColor} />
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>
                  Max streak: <span style={{ color: rorColor }}>{result.risk_metrics.max_consecutive_losses} losses</span>
                </div>
              </div>
            </div>

            {/* Leverage Sizes */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", fontWeight: 700, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>Leverage Sizes</div>
              <div style={{ display: "flex", gap: 8 }}>
                {(["1x", "5x", "10x"] as const).map(lev => (
                  <div key={lev} style={{ flex: 1, padding: "8px", borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.58rem", color: "var(--text-muted)" }}>{lev}</div>
                    <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "#3b82f6", fontFamily: "monospace" }}>
                      {result.leverage_sizes[lev].toFixed(3)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {result.warnings.map((w, i) => (
                  <div key={i} style={{ fontSize: "0.7rem", color: "#f59e0b", padding: "6px 10px", background: "rgba(245,158,11,0.08)", borderRadius: 6, border: "1px solid rgba(245,158,11,0.2)" }}>
                    {w}
                  </div>
                ))}
              </div>
            )}

            <div style={{ marginTop: 10, fontSize: "0.62rem", color: "var(--text-muted)", textAlign: "center" }}>
              Break-even WR: <span style={{ color: "#fff" }}>{result.risk_metrics.breakeven_win_rate}%</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
