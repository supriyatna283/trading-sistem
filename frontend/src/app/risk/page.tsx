"use client";

import MainLayout from "@/components/layout/MainLayout";
import { notifyApiError } from "@/components/ui/ApiStatusBanner";
import { api, type PositionSizeResult, type RiskSettings } from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

export default function RiskPage() {
  const [balance, setBalance] = useState(10000);
  const [riskPct, setRiskPct] = useState(1);
  const [maxDailyRisk, setMaxDailyRisk] = useState(3);
  const [maxConcurrent, setMaxConcurrent] = useState(3);
  const [entry, setEntry] = useState(67100);
  const [sl, setSl] = useState(66680);
  const [tp, setTp] = useState(68400);
  const [direction, setDirection] = useState<"BUY" | "SELL">("BUY");
  const [result, setResult] = useState<PositionSizeResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [calcLoading, setCalcLoading] = useState(false);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getRiskSettings();
      const s: RiskSettings = res.settings;
      setBalance(s.account_balance);
      setRiskPct(s.risk_per_trade);
      setMaxDailyRisk(s.max_daily_risk);
      setMaxConcurrent(s.max_concurrent_trades);
    } catch (e) {
      notifyApiError(e instanceof Error ? e.message : "Gagal memuat pengaturan risk");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const runCalculate = useCallback(async () => {
    setCalcLoading(true);
    try {
      const res = await api.calculatePosition({
        account_balance: balance,
        risk_per_trade: riskPct,
        entry_price: entry,
        stop_loss: sl,
        direction,
        take_profit: tp,
      });
      setResult(res.result);
    } catch (e) {
      notifyApiError(e instanceof Error ? e.message : "Gagal menghitung posisi");
      setResult(null);
    } finally {
      setCalcLoading(false);
    }
  }, [balance, riskPct, entry, sl, tp, direction]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (!loading) runCalculate();
    }, 400);
    return () => clearTimeout(t);
  }, [runCalculate, loading]);

  const saveSettings = async () => {
    setSaving(true);
    try {
      await api.updateRiskSettings({
        account_balance: balance,
        risk_per_trade: riskPct,
        max_daily_risk: maxDailyRisk,
        max_concurrent_trades: maxConcurrent,
      });
    } catch (e) {
      notifyApiError(e instanceof Error ? e.message : "Gagal menyimpan pengaturan");
    } finally {
      setSaving(false);
    }
  };

  const rr = result?.risk_reward != null ? result.risk_reward.toFixed(2) : "—";
  const maxDailyLoss = balance * (maxDailyRisk / 100);

  return (
    <MainLayout>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Risk Management</h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
          Position size calculator — terhubung ke backend risk engine
        </p>
      </div>

      <RiskGrid>
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: "0.9rem", fontWeight: 700, margin: "0 0 20px 0" }}>Position Calculator</h3>

          <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
            {(["BUY", "SELL"] as const).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDirection(d)}
                style={{
                  flex: 1,
                  padding: "10px",
                  borderRadius: 10,
                  fontWeight: 700,
                  fontSize: "0.9rem",
                  border: direction === d ? "none" : "1px solid var(--border)",
                  background:
                    direction === d
                      ? d === "BUY"
                        ? "rgba(34,197,94,0.15)"
                        : "rgba(239,68,68,0.15)"
                      : "transparent",
                  color:
                    direction === d
                      ? d === "BUY"
                        ? "var(--accent-green)"
                        : "var(--accent-red)"
                      : "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                {d === "BUY" ? "▲" : "▼"} {d}
              </button>
            ))}
          </div>

          <RiskField label="Account Balance ($)" value={balance} onChange={setBalance} />
          <RiskField label="Risk Per Trade (%)" value={riskPct} onChange={setRiskPct} step={0.1} />
          <RiskField label="Entry Price" value={entry} onChange={setEntry} />
          <RiskField label="Stop Loss" value={sl} onChange={setSl} />
          <RiskField label="Take Profit" value={tp} onChange={setTp} />

          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "20px 0" }} />

          <h4 style={{ fontSize: "0.8rem", fontWeight: 700, margin: "0 0 12px 0" }}>Portfolio Limits</h4>
          <RiskField label="Max Daily Risk (%)" value={maxDailyRisk} onChange={setMaxDailyRisk} step={0.1} />
          <RiskField label="Max Concurrent Trades" value={maxConcurrent} onChange={setMaxConcurrent} step={1} />

          <button className="btn-primary" style={{ width: "100%", marginTop: 8 }} onClick={saveSettings} disabled={saving}>
            {saving ? "Menyimpan…" : "Simpan ke Database"}
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <ResultCard
            label="Position Size"
            value={calcLoading ? "…" : (result?.position_size?.toFixed(6) ?? "—")}
            unit="units"
            color="var(--accent-blue)"
            icon="📏"
            glow="glow-blue"
          />
          <ResultCard
            label="Risk Amount"
            value={calcLoading ? "…" : result ? `$${result.risk_amount.toFixed(2)}` : "—"}
            color="var(--accent-red)"
            icon="⚠️"
            glow="glow-red"
          />
          <ResultCard
            label="Risk : Reward"
            value={calcLoading ? "…" : `1 : ${rr}`}
            color="var(--accent-purple)"
            icon="⚖️"
            glow="glow-purple"
          />
          <ResultCard
            label="Stop Distance"
            value={calcLoading ? "…" : (result?.stop_distance?.toFixed(2) ?? "—")}
            unit={result ? `(${result.stop_distance_pct.toFixed(3)}%)` : ""}
            color="var(--accent-yellow)"
            icon="📐"
            glow="glow-green"
          />

          <div className="glass-card" style={{ padding: 20 }}>
            <h4 style={{ fontSize: "0.8rem", fontWeight: 700, margin: "0 0 12px 0" }}>Daily Risk Limits</h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <Stat label="Max Daily Risk" value={`${maxDailyRisk.toFixed(2)}%`} color="var(--accent-yellow)" />
              <Stat label="Max Daily Loss" value={`$${maxDailyLoss.toFixed(2)}`} color="var(--accent-red)" />
              <Stat label="Max Concurrent" value={`${maxConcurrent} trades`} color="var(--accent-blue)" />
              <Stat label="Risk / Trade" value={`${riskPct}%`} color="var(--accent-purple)" />
            </div>
          </div>
        </div>
      </RiskGrid>
    </MainLayout>
  );
}

function RiskGrid({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>{children}</div>;
}

function RiskField({
  label,
  value,
  onChange,
  step,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontWeight: 600, display: "block", marginBottom: 6 }}>
        {label}
      </label>
      <input
        className="input-field"
        type="number"
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function ResultCard({
  label,
  value,
  unit,
  color,
  icon,
  glow,
}: {
  label: string;
  value: string;
  unit?: string;
  color: string;
  icon: string;
  glow: string;
}) {
  return (
    <div className={`glass-card ${glow}`} style={{ padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <ResultLabel text={label} />
          <div style={{ fontSize: "1.6rem", fontWeight: 800, fontFamily: "'JetBrains Mono', monospace", color, marginTop: 4 }}>
            {value}
          </div>
          {unit && <ResultUnit text={unit} />}
        </div>
        <span style={{ fontSize: "2rem" }}>{icon}</span>
      </div>
    </div>
  );
}

function ResultLabel({ text }: { text: string }) {
  return (
    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
      {text}
    </div>
  );
}

function ResultUnit({ text }: { text: string }) {
  return <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>{text}</div>;
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div>
      <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 600 }}>{label}</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color }}>{value}</div>
    </div>
  );
}
