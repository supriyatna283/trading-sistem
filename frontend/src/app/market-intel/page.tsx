"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function MarketIntelPage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [overview, setOverview] = useState<any>(null);
  const [sentiment, setSentiment] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [symbols, setSymbols] = useState<string[]>([
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT"
  ]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ovRes, sentRes] = await Promise.all([
        api.getMarketIntelOverview(symbol).catch(() => null),
        api.getSentiment().catch(() => null),
      ]);
      setOverview(ovRes);
      setSentiment(sentRes);
    } catch (err) {
      console.error("Market Intel fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [symbol]);

  const fng = sentiment?.fear_and_greed || { value: 50, classification: "Neutral" };
  const btcDom = overview?.btc_dominance || {};
  const ob = overview?.orderbook || {};
  const sr = overview?.support_resistance || {};
  const liq = overview?.liquidation || {};
  const mcap = overview?.market_cap || {};

  const getFngColor = (val: number) => {
    if (val < 25) return "#ef4444";
    if (val < 45) return "#f97316";
    if (val < 55) return "#eab308";
    if (val < 75) return "#84cc16";
    return "#22c55e";
  };

  const formatNum = (n: number) => {
    if (!n) return "—";
    if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
    if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    return n.toLocaleString();
  };

  const formatPrice = (p: number) => {
    if (!p || p <= 0) return "—";
    return p > 10 ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : p.toFixed(6);
  };

  return (
    <MainLayout>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>🧠 Market Intelligence</h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
            Deep market data feeding into signal generation pipeline
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            style={{
              background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: 8,
              padding: "8px 12px", color: "var(--text-primary)", fontSize: "0.85rem", fontWeight: 600,
            }}
          >
            {symbols.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <button className="btn-primary" onClick={fetchData} disabled={loading} style={{ opacity: loading ? 0.7 : 1 }}>
            {loading ? "⏳" : "🔄"} Refresh
          </button>
        </div>
      </div>

      {/* Top Row: F&G + BTC Dominance + Market Cap */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 20 }}>
        {/* Fear & Greed */}
        <div className="glass-card" style={{ padding: 24, textAlign: "center" }}>
          <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
            Fear & Greed Index
          </div>
          <div style={{ fontSize: "3rem", fontWeight: 900, color: getFngColor(fng.value), lineHeight: 1 }}>
            {fng.value}
          </div>
          <div style={{ fontSize: "0.85rem", fontWeight: 700, color: getFngColor(fng.value), marginTop: 4, textTransform: "uppercase" }}>
            {fng.classification}
          </div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 8 }}>
            {fng.value <= 25 ? "🟢 Extreme Fear = Potential Buy" : fng.value >= 75 ? "🔴 Extreme Greed = Potential Sell" : "⚪ Neutral Zone"}
          </div>
        </div>

        {/* BTC Dominance */}
        <div className="glass-card" style={{ padding: 24, textAlign: "center" }}>
          <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
            BTC Dominance
          </div>
          <div style={{ fontSize: "3rem", fontWeight: 900, color: "var(--accent-yellow)", lineHeight: 1 }}>
            {(btcDom.btc_dominance || 0).toFixed(1)}%
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: 8 }}>
            ETH.D: {(btcDom.eth_dominance || 0).toFixed(1)}%
          </div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 4 }}>
            24h MCap: <span style={{ color: (btcDom.market_cap_change_24h_pct || 0) > 0 ? "var(--accent-green)" : "var(--accent-red)" }}>
              {(btcDom.market_cap_change_24h_pct || 0) > 0 ? "+" : ""}{(btcDom.market_cap_change_24h_pct || 0).toFixed(2)}%
            </span>
          </div>
        </div>

        {/* Market Cap */}
        <div className="glass-card" style={{ padding: 24, textAlign: "center" }}>
          <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
            {symbol} Market Cap
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 900, color: "var(--accent-blue)", lineHeight: 1 }}>
            {formatNum(mcap.market_cap_usd || 0)}
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 16, marginTop: 12, fontSize: "0.7rem" }}>
            <div>
              <span style={{ color: "var(--text-muted)" }}>Circ Supply: </span>
              <span style={{ color: "var(--text-secondary)" }}>{formatNum(mcap.circulating_supply || 0)}</span>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)" }}>Rank: </span>
              <span style={{ color: "var(--accent-purple)", fontWeight: 700 }}>#{mcap.market_cap_rank || "—"}</span>
            </div>
          </div>
          <div style={{ marginTop: 8 }}>
            <span style={{
              fontSize: "0.7rem", fontWeight: 700, padding: "2px 8px", borderRadius: 4,
              background: mcap.tier === "LARGE" ? "rgba(34,197,94,0.1)" : mcap.tier === "MID" ? "rgba(59,130,246,0.1)" : "rgba(234,179,8,0.1)",
              color: mcap.tier === "LARGE" ? "var(--accent-green)" : mcap.tier === "MID" ? "var(--accent-blue)" : "var(--accent-yellow)",
            }}>{mcap.tier || "UNKNOWN"} CAP</span>
          </div>
        </div>
      </div>

      {/* Middle Row: Order Book + Support/Resistance */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        {/* Order Book Depth */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 700, marginBottom: 16 }}>📊 Order Book Depth — {symbol}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 4 }}>Buy Volume</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--accent-green)", fontFamily: "JetBrains Mono, monospace" }}>
                {(ob.bid_volume || 0).toFixed(2)}
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 4 }}>Sell Volume</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--accent-red)", fontFamily: "JetBrains Mono, monospace" }}>
                {(ob.ask_volume || 0).toFixed(2)}
              </div>
            </div>
          </div>
          {/* Ratio Bar */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", marginBottom: 4 }}>
              <span style={{ color: "var(--accent-green)" }}>Buy {((ob.buy_sell_ratio / (ob.buy_sell_ratio + 1)) * 100 || 50).toFixed(0)}%</span>
              <span style={{ color: "var(--accent-red)" }}>Sell {((1 / (ob.buy_sell_ratio + 1)) * 100 || 50).toFixed(0)}%</span>
            </div>
            <div style={{ height: 8, borderRadius: 4, overflow: "hidden", display: "flex", background: "var(--bg-secondary)" }}>
              <div style={{ width: `${((ob.buy_sell_ratio || 1) / ((ob.buy_sell_ratio || 1) + 1)) * 100}%`, background: "var(--accent-green)", borderRadius: "4px 0 0 4px" }} />
              <div style={{ flex: 1, background: "var(--accent-red)", borderRadius: "0 4px 4px 0" }} />
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem" }}>
            <span style={{ color: "var(--text-muted)" }}>Ratio: <span style={{ color: "var(--text-primary)", fontWeight: 700 }}>{(ob.buy_sell_ratio || 1).toFixed(3)}x</span></span>
            <span style={{
              padding: "2px 8px", borderRadius: 4, fontSize: "0.7rem", fontWeight: 700,
              background: ob.bias === "BULLISH" ? "rgba(34,197,94,0.1)" : ob.bias === "BEARISH" ? "rgba(239,68,68,0.1)" : "rgba(255,255,255,0.05)",
              color: ob.bias === "BULLISH" ? "var(--accent-green)" : ob.bias === "BEARISH" ? "var(--accent-red)" : "var(--text-muted)",
            }}>{ob.bias || "NEUTRAL"}</span>
          </div>
        </div>

        {/* Support & Resistance */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 700, marginBottom: 16 }}>📐 Support & Resistance — {symbol}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <div style={{ fontSize: "0.65rem", color: "var(--accent-green)", textTransform: "uppercase", fontWeight: 600, marginBottom: 8 }}>Support Levels</div>
              {(sr.supports || []).slice(0, 4).map((s: number, i: number) => (
                <div key={i} style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "0.8rem", color: "var(--accent-green)", padding: "4px 0", borderBottom: "1px solid rgba(34,197,94,0.1)" }}>
                  S{i + 1}: {formatPrice(s)}
                </div>
              ))}
              {(!sr.supports || sr.supports.length === 0) && <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>No data</div>}
            </div>
            <div>
              <div style={{ fontSize: "0.65rem", color: "var(--accent-red)", textTransform: "uppercase", fontWeight: 600, marginBottom: 8 }}>Resistance Levels</div>
              {(sr.resistances || []).slice(0, 4).map((r: number, i: number) => (
                <div key={i} style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "0.8rem", color: "var(--accent-red)", padding: "4px 0", borderBottom: "1px solid rgba(239,68,68,0.1)" }}>
                  R{i + 1}: {formatPrice(r)}
                </div>
              ))}
              {(!sr.resistances || sr.resistances.length === 0) && <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>No data</div>}
            </div>
          </div>
          {sr.pivot > 0 && (
            <div style={{ marginTop: 12, textAlign: "center", fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Pivot: <span style={{ color: "var(--accent-purple)", fontWeight: 700 }}>{formatPrice(sr.pivot)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Row: Liquidation + Funding Rates */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Liquidation Levels */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 700, marginBottom: 16 }}>🔥 Liquidation Levels — {symbol}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 12 }}>
            Current: <span style={{ color: "var(--text-primary)", fontWeight: 700 }}>{formatPrice(liq.current_price || 0)}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
            {(liq.levels || []).filter((l: any) => [3, 5, 10, 25].includes(l.leverage)).map((l: any) => (
              <div key={l.leverage} style={{ background: "var(--bg-secondary)", borderRadius: 8, padding: 10, textAlign: "center" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--accent-yellow)", fontWeight: 700, marginBottom: 6 }}>{l.leverage}x</div>
                <div style={{ fontSize: "0.65rem", color: "var(--accent-green)", marginBottom: 2 }}>
                  Long: {formatPrice(l.long_liquidation)}
                </div>
                <div style={{ fontSize: "0.65rem", color: "var(--accent-red)" }}>
                  Short: {formatPrice(l.short_liquidation)}
                </div>
              </div>
            ))}
          </div>
          {liq.cluster_zone && (
            <div style={{ marginTop: 12, background: "rgba(234,179,8,0.05)", border: "1px solid rgba(234,179,8,0.2)", borderRadius: 8, padding: 10 }}>
              <div style={{ fontSize: "0.7rem", color: "var(--accent-yellow)", fontWeight: 700 }}>⚡ High-Risk Cluster (10x-25x)</div>
              <div style={{ fontSize: "0.75rem", fontFamily: "JetBrains Mono, monospace", color: "var(--text-secondary)", marginTop: 4 }}>
                {formatPrice(liq.cluster_zone.low)} — {formatPrice(liq.cluster_zone.high)}
              </div>
            </div>
          )}
        </div>

        {/* Funding Rates from Sentiment */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 700, marginBottom: 16 }}>💰 Funding Rates (Binance)</div>
          <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginBottom: 12 }}>
            Positive = Longs pay Shorts (bearish pressure) | Negative = Shorts pay Longs (bullish pressure)
          </div>
          {(sentiment?.market_metrics || []).map((m: any) => (
            <div key={m.symbol} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <span style={{ fontWeight: 700, fontSize: "0.8rem" }}>{m.symbol}</span>
              <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                <span style={{
                  fontFamily: "JetBrains Mono, monospace", fontSize: "0.8rem", fontWeight: 700,
                  color: m.funding_rate > 0 ? "var(--accent-red)" : m.funding_rate < 0 ? "var(--accent-green)" : "var(--text-muted)",
                }}>
                  {(m.funding_rate * 100).toFixed(4)}%
                </span>
                <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                  OI: {formatNum(m.open_interest || 0)}
                </span>
              </div>
            </div>
          ))}
          {(!sentiment?.market_metrics || sentiment.market_metrics.length === 0) && (
            <div style={{ color: "var(--text-muted)", textAlign: "center", padding: 20, fontSize: "0.85rem" }}>
              Loading funding data...
            </div>
          )}
        </div>
      </div>
    </MainLayout>
  );
}
