"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "@/lib/api";

const WS_URL = process.env.NEXT_PUBLIC_API_URL?.replace("http", "ws") || "ws://127.0.0.1:8000";
const TAPE_WS = `${WS_URL}/api/v1/orderflow/ws/tape`;

const TIER_CONFIG: Record<string, { color: string; bg: string; border: string; icon: string }> = {
  WHALE: { color: "#fbbf24", bg: "rgba(251,191,36,0.1)", border: "rgba(251,191,36,0.3)", icon: "🐋" },
  SHARK: { color: "#a78bfa", bg: "rgba(167,139,250,0.08)", border: "rgba(167,139,250,0.2)", icon: "🦈" },
  FISH:  { color: "#60a5fa", bg: "rgba(96,165,250,0.06)", border: "rgba(96,165,250,0.15)", icon: "🐟" },
  RETAIL:{ color: "var(--text-muted)", bg: "transparent", border: "var(--border)", icon: "👤" },
};

const SCAN_SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","DOGEUSDT","MATICUSDT","ARBUSDT","OPUSDT","INJUSDT"];

type Trade = {
  exchange?: string; symbol: string; price: number; qty: number; notional: number;
  side: "BUY" | "SELL"; tier: string; timestamp: number; trade_id?: string; agg_trade_id?: number;
};

function formatLocalTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("id-ID", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
}

export default function SmartTapePage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [filter, setFilter] = useState<"ALL" | "WHALE" | "SHARK" | "FISH">("ALL");
  const [sideFilter, setSideFilter] = useState<"ALL" | "BUY" | "SELL">("ALL");
  const [symbolFilter, setSymbolFilter] = useState("ALL");
  const [threshold, setThreshold] = useState(50000);
  const [connected, setConnected] = useState(false);
  const [paused, setPaused] = useState(false);
  const [scanData, setScanData] = useState<any>(null);
  const [scanning, setScanning] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(false);

  pausedRef.current = paused;

  const addTrades = useCallback((newTrades: Trade[]) => {
    if (pausedRef.current) return;
    setTrades(prev => {
      const combined = [...newTrades, ...prev].slice(0, 500);
      return combined;
    });
  }, []);

  // ── WebSocket — Multi-Exchange Direct (Binance + OKX + Bybit) ──
  useEffect(() => {
    const wsList: WebSocket[] = [];
    const timers: ReturnType<typeof setTimeout>[] = [];

    const classifyTier = (notional: number): string => {
      if (notional >= 500000) return "WHALE";
      if (notional >= 100000) return "SHARK";
      if (notional >= 20000) return "FISH";
      return "RETAIL";
    };

    // ── 1. BINANCE aggTrade ──
    const connectBinance = () => {
      const streams = SCAN_SYMBOLS.map(s => `${s.toLowerCase()}@aggTrade`).join("/");
      const ws = new WebSocket(`wss://stream.binance.com:9443/stream?streams=${streams}`);
      wsList.push(ws);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data)?.data;
          if (!d || d.e !== "aggTrade") return;
          const price = parseFloat(d.p), qty = parseFloat(d.q);
          const notional = price * qty;
          if (notional < threshold) return;
          addTrades([{ exchange: "Binance 🟡", symbol: d.s, price, qty, notional,
            side: d.m ? "SELL" : "BUY", tier: classifyTier(notional),
            timestamp: d.T, trade_id: String(d.a) }]);
        } catch {}
      };
      ws.onclose = () => { const t = setTimeout(connectBinance, 3000); timers.push(t); };
      ws.onerror = () => ws.close();
    };

    // ── 2. OKX trades ──
    const connectOKX = () => {
      const ws = new WebSocket("wss://wsaws.okx.com:8443/ws/v5/public");
      wsList.push(ws);
      ws.onopen = () => {
        const args = SCAN_SYMBOLS.map(s => ({
          channel: "trades",
          instId: s.replace("USDT", "-USDT"),
        }));
        ws.send(JSON.stringify({ op: "subscribe", args }));
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          const items: any[] = msg?.data || [];
          for (const d of items) {
            if (!d.px) continue;
            const price = parseFloat(d.px), qty = parseFloat(d.sz);
            const notional = price * qty;
            if (notional < threshold) return;
            const symbol = (d.instId as string).replace("-", "");
            addTrades([{ exchange: "OKX 🔵", symbol, price, qty, notional,
              side: d.side === "buy" ? "BUY" : "SELL", tier: classifyTier(notional),
              timestamp: parseInt(d.ts), trade_id: d.tradeId }]);
          }
        } catch {}
      };
      ws.onclose = () => { const t = setTimeout(connectOKX, 3000); timers.push(t); };
      ws.onerror = () => ws.close();
    };

    // ── 3. BYBIT publicTrade ──
    const connectBybit = () => {
      const ws = new WebSocket("wss://stream.bybit.com/v5/public/linear");
      wsList.push(ws);
      ws.onopen = () => {
        const args = SCAN_SYMBOLS.map(s => `publicTrade.${s}`);
        ws.send(JSON.stringify({ op: "subscribe", args }));
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          const items: any[] = msg?.data || [];
          for (const d of items) {
            if (!d.p) continue;
            const price = parseFloat(d.p), qty = parseFloat(d.v);
            const notional = price * qty;
            if (notional < threshold) return;
            addTrades([{ exchange: "Bybit 🟠", symbol: d.s, price, qty, notional,
              side: d.S === "Buy" ? "BUY" : "SELL", tier: classifyTier(notional),
              timestamp: d.T, trade_id: d.i }]);
          }
        } catch {}
      };
      ws.onclose = () => { const t = setTimeout(connectBybit, 3000); timers.push(t); };
      ws.onerror = () => ws.close();
    };

    connectBinance();
    connectOKX();
    connectBybit();

    return () => {
      wsList.forEach(ws => ws.close());
      timers.forEach(t => clearTimeout(t));
    };
  }, [addTrades, threshold]);


  // Auto-scroll
  useEffect(() => {
    if (autoScroll && listRef.current) {
      listRef.current.scrollTop = 0;
    }
  }, [trades, autoScroll]);

  // Multi-symbol scan
  const runScan = async () => {
    setScanning(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/v1/orderflow/whales?limit=100`
      );
      const data = await res.json();
      setScanData(data);
    } catch (e) { console.error(e); }
    finally { setScanning(false); }
  };

  useEffect(() => { runScan(); }, []);
  useEffect(() => { const t = setInterval(runScan, 60000); return () => clearInterval(t); }, [threshold]);

  const filteredTrades = trades.filter(t => {
    if (filter !== "ALL" && t.tier !== filter) return false;
    if (sideFilter !== "ALL" && t.side !== sideFilter) return false;
    if (symbolFilter !== "ALL" && t.symbol !== symbolFilter) return false;
    if (t.notional < threshold) return false;
    return true;
  });

  const symbols = Array.from(new Set(trades.map(t => t.symbol))).sort();
  const buyFlow = scanData?.summary?.buy_pressure || 0;
  const sellFlow = scanData?.summary?.sell_pressure || 0;
  const totalFlow = scanData?.summary?.total_flow || 1;
  const buyPct = Math.round((buyFlow / totalFlow) * 100) || 50;
  const sellPct = 100 - buyPct;

  return (
    <MainLayout>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h1 style={{ fontSize: "1.5rem", fontWeight: 800, margin: 0, letterSpacing: "-0.03em" }}>🎬 Smart Tape</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.82rem", margin: "4px 0 0" }}>
              Multi-exchange whale detector — Binance + OKX + Bybit
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{
              padding: "5px 12px", borderRadius: 20, fontSize: "0.72rem", fontWeight: 700,
              background: connected ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
              border: `1px solid ${connected ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
              color: connected ? "#22c55e" : "#ef4444",
            }}>
              {connected ? "🟢 LIVE" : "🔴 Reconnecting..."}
            </span>
            <button onClick={() => setPaused(p => !p)} style={{
              padding: "5px 14px", borderRadius: 20, fontSize: "0.72rem", fontWeight: 700, cursor: "pointer",
              background: paused ? "rgba(245,158,11,0.15)" : "rgba(255,255,255,0.04)",
              border: `1px solid ${paused ? "rgba(245,158,11,0.4)" : "var(--border)"}`,
              color: paused ? "#f59e0b" : "var(--text-secondary)",
            }}>
              {paused ? "▶ Resume" : "⏸ Pause"}
            </button>
            <button onClick={() => setTrades([])} style={{
              padding: "5px 12px", borderRadius: 20, fontSize: "0.72rem", fontWeight: 700, cursor: "pointer",
              background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#ef4444",
            }}>
              🗑 Clear
            </button>
          </div>
        </div>

        {/* ── Flow Pressure Bar (top) ── */}
        <div className="glass-card" style={{ padding: "12px 20px" }}>
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600, marginBottom: 8, textTransform: "uppercase" }}>
            5-min Whale Flow Pressure
          </div>
          <div style={{ display: "flex", height: 12, borderRadius: 8, overflow: "hidden", gap: 2, marginBottom: 10 }}>
            <div style={{ width: `${buyPct}%`, background: "linear-gradient(90deg, #22c55e, #16a34a)", borderRadius: "6px 0 0 6px", transition: "width 1s ease" }} />
            <div style={{ width: `${sellPct}%`, background: "linear-gradient(90deg, #ef4444, #dc2626)", borderRadius: "0 6px 6px 0", transition: "width 1s ease" }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "#22c55e", fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", fontSize: "0.78rem" }}>
              BUY {buyPct}% — ${(buyFlow/1e6).toFixed(2)}M
            </span>
            <span style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>
              {scanData?.trade_count ?? 0} trades | {scanning ? "Scanning..." : "Updated 1m"}
            </span>
            <span style={{ color: "#ef4444", fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", fontSize: "0.78rem" }}>
              ${(sellFlow/1e6).toFixed(2)}M — SELL {sellPct}%
            </span>
          </div>
        </div>

        {/* ── Stats Row ── */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
          {[
            { label: "🐋 Whales", val: scanData?.trades?.filter((t:any) => t.tier === "WHALE").length ?? 0, color: "#fbbf24" },
            { label: "🦈 Sharks", val: scanData?.trades?.filter((t:any) => t.tier === "SHARK").length ?? 0, color: "#a78bfa" },
            { label: "Total Flow", val: `$${((scanData?.summary?.total_flow ?? 0)/1e6).toFixed(2)}M`, color: "var(--accent-blue)" },
            { label: "Net Flow", val: `${(scanData?.summary?.net_flow ?? 0) >= 0 ? "+" : ""}$${((scanData?.summary?.net_flow ?? 0)/1e3).toFixed(0)}K`, color: (scanData?.summary?.net_flow ?? 0) >= 0 ? "#22c55e" : "#ef4444" },
          ].map(s => (
            <div key={s.label} className="glass-card" style={{ padding: "12px 16px" }}>
              <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", marginBottom: 4 }}>{s.label}</div>
              <div style={{ fontSize: "1.3rem", fontWeight: 800, color: s.color, fontFamily: "'JetBrains Mono', monospace" }}>{s.val}</div>
            </div>
          ))}
        </div>

        {/* ── Filters ── */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          {/* Tier filter */}
          {(["ALL","WHALE","SHARK","FISH"] as const).map(t => (
            <button key={t} onClick={() => setFilter(t)} style={{
              padding: "5px 12px", borderRadius: 8, fontSize: "0.75rem", fontWeight: 700, cursor: "pointer",
              background: filter === t ? (TIER_CONFIG[t]?.bg || "rgba(59,130,246,0.12)") : "transparent",
              border: `1px solid ${filter === t ? (TIER_CONFIG[t]?.border || "rgba(59,130,246,0.3)") : "var(--border)"}`,
              color: filter === t ? (TIER_CONFIG[t]?.color || "var(--accent-blue)") : "var(--text-muted)",
            }}>
              {t === "ALL" ? "🔍 All" : `${TIER_CONFIG[t].icon} ${t}`}
            </button>
          ))}
          <div style={{ width: 1, height: 20, background: "var(--border)" }} />
          {/* Side filter */}
          {(["ALL","BUY","SELL"] as const).map(s => (
            <button key={s} onClick={() => setSideFilter(s)} style={{
              padding: "5px 12px", borderRadius: 8, fontSize: "0.75rem", fontWeight: 700, cursor: "pointer",
              background: sideFilter === s ? (s === "BUY" ? "rgba(34,197,94,0.1)" : s === "SELL" ? "rgba(239,68,68,0.1)" : "rgba(59,130,246,0.1)") : "transparent",
              border: `1px solid ${sideFilter === s ? (s === "BUY" ? "rgba(34,197,94,0.3)" : s === "SELL" ? "rgba(239,68,68,0.3)" : "rgba(59,130,246,0.3)") : "var(--border)"}`,
              color: sideFilter === s ? (s === "BUY" ? "#22c55e" : s === "SELL" ? "#ef4444" : "var(--accent-blue)") : "var(--text-muted)",
            }}>
              {s === "ALL" ? "All Sides" : s}
            </button>
          ))}
          <div style={{ width: 1, height: 20, background: "var(--border)" }} />
          {/* Symbol filter */}
          <select
            value={symbolFilter}
            onChange={e => setSymbolFilter(e.target.value)}
            style={{
              background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)",
              borderRadius: 8, padding: "5px 10px", fontSize: "0.75rem", fontWeight: 600, cursor: "pointer",
            }}
          >
            <option value="ALL">All Symbols</option>
            {symbols.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          {/* Threshold */}
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>Min $</span>
            <select
              value={threshold}
              onChange={e => setThreshold(Number(e.target.value))}
              style={{
                background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)",
                borderRadius: 8, padding: "5px 10px", fontSize: "0.75rem", fontWeight: 600,
              }}
            >
              {[1000, 5000, 10000, 25000, 50000, 100000, 250000, 500000].map(v => (
                <option key={v} value={v}>{v >= 1000 ? `${v/1000}K` : v}</option>
              ))}
            </select>
            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{filteredTrades.length} trades</span>
          </div>
        </div>

        {/* ── Live Trade Feed ── */}
        <div className="glass-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{
            padding: "10px 16px", borderBottom: "1px solid var(--border)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <span style={{ fontWeight: 700, fontSize: "0.85rem" }}>📡 Live Trade Feed</span>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {connected && !paused && (
                <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.72rem", color: "#22c55e" }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#22c55e", animation: "pulse 1.5s infinite", display: "inline-block" }} />
                  STREAMING
                </span>
              )}
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.72rem", color: "var(--text-muted)", cursor: "pointer" }}>
                <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} /> Auto-scroll
              </label>
            </div>
          </div>

          {/* Table header */}
          <div style={{
            display: "grid", gridTemplateColumns: "80px 1fr 90px 110px 110px 90px 70px",
            padding: "6px 16px", borderBottom: "1px solid var(--border)",
            fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase",
          }}>
            <span>Time</span><span>Exchange</span><span>Symbol</span><span>Side</span><span>Notional</span><span>Price</span><span>Tier</span>
          </div>

          <div ref={listRef} style={{ height: 480, overflowY: "auto" }}>
            {filteredTrades.length === 0 ? (
              <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                {connected ? "Waiting for whale trades from Binance, OKX, Bybit..." : "Connecting to exchanges..."}
              </div>
            ) : (
              filteredTrades.map((t, i) => {
                const cfg = TIER_CONFIG[t.tier] || TIER_CONFIG.RETAIL;
                return (
                  <div
                    key={`${t.agg_trade_id}-${i}`}
                    style={{
                      display: "grid", gridTemplateColumns: "80px 1fr 90px 110px 110px 90px 70px",
                      padding: "7px 16px", borderBottom: "1px solid rgba(255,255,255,0.02)",
                      background: i === 0 ? (t.side === "BUY" ? "rgba(34,197,94,0.04)" : "rgba(239,68,68,0.04)") : "transparent",
                      fontSize: "0.78rem", alignItems: "center",
                      borderLeft: `3px solid ${t.side === "BUY" ? "rgba(34,197,94,0.4)" : "rgba(239,68,68,0.4)"}`,
                      transition: "background 0.5s",
                    }}
                  >
                    <span style={{ color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.7rem" }}>{formatLocalTime(t.timestamp)}</span>
                    <span style={{ fontSize: "0.68rem", fontWeight: 700, padding: "2px 6px", borderRadius: 4,
                      background: t.exchange === "bybit" ? "rgba(247,147,26,0.12)" : t.exchange === "okx" ? "rgba(0,180,255,0.12)" : "rgba(130,255,180,0.12)",
                      color: t.exchange === "bybit" ? "#f7931a" : t.exchange === "okx" ? "#00b4ff" : "#82ffb4",
                    }}>{(t.exchange || "unknown").toUpperCase()}</span>
                    <span style={{ fontWeight: 700 }}>{t.symbol.replace("USDT", "")}<span style={{ color: "var(--text-muted)", fontWeight: 400 }}>/USDT</span></span>
                    <span style={{ fontWeight: 700, color: t.side === "BUY" ? "#22c55e" : "#ef4444" }}>{t.side === "BUY" ? "▲ BUY" : "▼ SELL"}</span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }}>
                      ${t.notional >= 1e6 ? `${(t.notional/1e6).toFixed(2)}M` : t.notional >= 1000 ? `${(t.notional/1000).toFixed(1)}K` : t.notional.toFixed(0)}
                    </span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.72rem" }}>{t.price.toLocaleString()}</span>
                    <span style={{ padding: "2px 8px", borderRadius: 6, fontSize: "0.68rem", fontWeight: 700, background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color, textAlign: "center" }}>
                      {cfg.icon} {t.tier}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.5); }
        }
      ` }} />
    </MainLayout>
  );
}
