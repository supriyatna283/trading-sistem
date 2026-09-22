"use client";

import { useEffect, useState, useCallback } from "react";

interface DerivData {
  fundingRate: number | null;
  nextFundingTime: number | null;
  openInterest: number | null;
  openInterestChange: number | null;
  longRatio: number | null;
  shortRatio: number | null;
  markPrice: number | null;
  indexPrice: number | null;
  hasFutures: boolean;
}

function fmt$(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  return `$${v.toFixed(0)}`;
}

function useCountdown(targetMs: number | null): string {
  const [remaining, setRemaining] = useState("");
  useEffect(() => {
    if (!targetMs) { setRemaining(""); return; }
    const tick = () => {
      const diff = targetMs - Date.now();
      if (diff <= 0) { setRemaining("00:00"); return; }
      const m = Math.floor(diff / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setRemaining(`${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [targetMs]);
  return remaining;
}

interface Props {
  symbol: string;
}

export default function DerivativesBar({ symbol }: Props) {
  const [data, setData] = useState<DerivData>({
    fundingRate: null, nextFundingTime: null,
    openInterest: null, openInterestChange: null,
    longRatio: null, shortRatio: null,
    markPrice: null, indexPrice: null,
    hasFutures: true,
  });
  const [loading, setLoading] = useState(true);
  const countdown = useCountdown(data.nextFundingTime);

  const fetchData = useCallback(async () => {
    // Binance Futures symbol = e.g. BTCUSDT
    const sym = symbol.toUpperCase();
    try {
      const [premRes, oiRes, lsRes] = await Promise.allSettled([
        fetch(`https://fapi.binance.com/fapi/v1/premiumIndex?symbol=${sym}`).then(r => r.json()),
        fetch(`https://fapi.binance.com/fapi/v1/openInterest?symbol=${sym}`).then(r => r.json()),
        fetch(`https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=${sym}&period=5m&limit=2`).then(r => r.json()),
      ]);

      // Check if futures pair exists
      const prem = premRes.status === "fulfilled" && !premRes.value?.code ? premRes.value : null;
      if (!prem) {
        setData(d => ({ ...d, hasFutures: false }));
        setLoading(false);
        return;
      }

      const oi = oiRes.status === "fulfilled" && !oiRes.value?.code ? oiRes.value : null;
      const ls = lsRes.status === "fulfilled" && Array.isArray(lsRes.value) && lsRes.value.length > 0 ? lsRes.value[0] : null;

      // OI change: compare latest vs previous candle
      let oiChange: number | null = null;
      if (oiRes.status === "fulfilled" && Array.isArray(oiRes.value) && oiRes.value.length >= 2) {
        const curr = parseFloat(oiRes.value[0]?.sumOpenInterestValue || "0");
        const prev = parseFloat(oiRes.value[1]?.sumOpenInterestValue || "0");
        oiChange = prev > 0 ? ((curr - prev) / prev) * 100 : null;
      }

      setData({
        hasFutures: true,
        fundingRate: prem ? parseFloat(prem.lastFundingRate) * 100 : null,
        nextFundingTime: prem ? parseInt(prem.nextFundingTime) : null,
        markPrice: prem ? parseFloat(prem.markPrice) : null,
        indexPrice: prem ? parseFloat(prem.indexPrice) : null,
        openInterest: oi ? parseFloat(oi.openInterest) * (prem ? parseFloat(prem.markPrice) : 1) : null,
        openInterestChange: oiChange,
        longRatio: ls ? parseFloat(ls.longAccount) * 100 : null,
        shortRatio: ls ? parseFloat(ls.shortAccount) * 100 : null,
      });
    } catch {
      setData(d => ({ ...d, hasFutures: false }));
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    setLoading(true);
    setData({ fundingRate: null, nextFundingTime: null, openInterest: null, openInterestChange: null, longRatio: null, shortRatio: null, markPrice: null, indexPrice: null, hasFutures: true });
    fetchData();
    const id = setInterval(fetchData, 30000);
    return () => clearInterval(id);
  }, [fetchData]);

  if (loading) {
    return (
      <div style={barStyle}>
        <span style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>Loading derivatives data…</span>
      </div>
    );
  }

  if (!data.hasFutures) {
    return (
      <div style={barStyle}>
        <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
          📊 No Binance Futures data for <strong style={{ color: "var(--text-secondary)" }}>{symbol}</strong>
        </span>
      </div>
    );
  }

  const fr = data.fundingRate;
  const frColor = fr === null ? "var(--text-muted)" : fr > 0 ? "#ef4444" : fr < 0 ? "#22c55e" : "var(--text-muted)";
  const frLabel = fr === null ? "—" : `${fr > 0 ? "+" : ""}${fr.toFixed(4)}%`;
  const frBias = fr === null ? "" : fr > 0.01 ? "⬆ Long-biased" : fr < -0.01 ? "⬇ Short-biased" : "➡ Neutral";

  const oiChgColor = (data.openInterestChange ?? 0) >= 0 ? "#22c55e" : "#ef4444";
  const basis = data.markPrice && data.indexPrice
    ? ((data.markPrice - data.indexPrice) / data.indexPrice) * 100
    : null;

  return (
    <div style={barStyle}>
      {/* Funding Rate */}
      <Chip label="FR" title="Funding Rate — positive = longs pay shorts (bearish signal), negative = shorts pay longs (bullish signal)">
        <span style={{ color: frColor, fontWeight: 800 }}>{frLabel}</span>
        {countdown && <span style={{ color: "var(--text-muted)", fontSize: "0.65rem" }}>in {countdown}</span>}
        {frBias && <span style={{ color: frColor, fontSize: "0.65rem", opacity: 0.85 }}>{frBias}</span>}
      </Chip>

      <Sep />

      {/* Open Interest */}
      <Chip label="OI" title="Open Interest — total value of open positions">
        <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>
          {data.openInterest ? fmt$(data.openInterest) : "—"}
        </span>
        {data.openInterestChange !== null && (
          <span style={{ color: oiChgColor, fontSize: "0.65rem", fontWeight: 700 }}>
            {data.openInterestChange >= 0 ? "+" : ""}{data.openInterestChange.toFixed(2)}%
          </span>
        )}
      </Chip>

      <Sep />

      {/* Long / Short Ratio */}
      {data.longRatio !== null && data.shortRatio !== null && (
        <>
          <Chip label="L/S" title="Global Long/Short Account Ratio (5m)">
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {/* Mini bar */}
              <div style={{ width: 60, height: 6, borderRadius: 3, background: "rgba(255,255,255,0.08)", overflow: "hidden", flexShrink: 0 }}>
                <div style={{ width: `${data.longRatio}%`, height: "100%", background: "linear-gradient(90deg, #22c55e, #16a34a)", borderRadius: 3 }} />
              </div>
              <span style={{ color: "#22c55e", fontWeight: 800, fontSize: "0.75rem" }}>{data.longRatio.toFixed(1)}%</span>
              <span style={{ color: "var(--text-muted)", fontSize: "0.65rem" }}>/</span>
              <span style={{ color: "#ef4444", fontWeight: 800, fontSize: "0.75rem" }}>{data.shortRatio.toFixed(1)}%</span>
            </div>
          </Chip>
          <Sep />
        </>
      )}

      {/* Basis */}
      {basis !== null && (
        <Chip label="Basis" title="Mark Price vs Index Price spread">
          <span style={{ color: basis >= 0 ? "#22c55e" : "#ef4444", fontWeight: 700 }}>
            {basis >= 0 ? "+" : ""}{basis.toFixed(4)}%
          </span>
        </Chip>
      )}
    </div>
  );
}

function Sep() {
  return <div style={{ width: 1, height: 16, background: "var(--border)", flexShrink: 0 }} />;
}

function Chip({ label, title, children }: { label: string; title: string; children: React.ReactNode }) {
  return (
    <div
      title={title}
      style={{ display: "flex", alignItems: "center", gap: 5, cursor: "help" }}
    >
      <span style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.06em", flexShrink: 0 }}>
        {label}
      </span>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        {children}
      </div>
    </div>
  );
}

const barStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 14,
  padding: "5px 14px",
  background: "rgba(255,255,255,0.02)",
  borderRadius: 8,
  border: "1px solid var(--border)",
  marginBottom: 8,
  flexShrink: 0,
  flexWrap: "wrap",
  fontSize: "0.78rem",
  minHeight: 32,
};
