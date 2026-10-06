"use client";

import { useState, useEffect, useRef, useCallback } from "react";

/* ─── Pairs to show in ticker ── */
const TICKER_SYMBOLS = [
  "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
  "ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","DOTUSDT",
  "OPUSDT","ARBUSDT","NEARUSDT","INJUSDT","PEPEUSDT",
  "SUIUSDT","TONUSDT","MATICUSDT","LTCUSDT","ATOMUSDT",
];

interface TickerData {
  symbol: string;
  base: string;
  price: number;
  change: number;
  flash: "up" | "down" | null;
}

function fmt(price: number): string {
  if (!isFinite(price) || price <= 0) return "--";
  if (price >= 10000) return price.toLocaleString("en", { maximumFractionDigits: 0 });
  if (price >= 100)   return price.toLocaleString("en", { maximumFractionDigits: 2 });
  if (price >= 1)     return price.toFixed(4);
  if (price >= 0.001) return price.toFixed(5);
  return price.toFixed(8);
}

export function LiveTickerBar() {
  const [tickers, setTickers] = useState<Record<string, TickerData>>({});
  const [wsStatus, setWsStatus] = useState<"connecting" | "live" | "error" | "off">("off");
  const wsRef = useRef<WebSocket | null>(null);
  const flashTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    setWsStatus("connecting");

    try {
      const ws = new WebSocket("wss://stream.binance.com:9443/ws/!miniTicker@arr");
      wsRef.current = ws;

      ws.onopen = () => setWsStatus("live");

      ws.onmessage = (evt) => {
        try {
          // miniTicker@arr fields: s=symbol, c=close, o=open, h=high, l=low, v=baseVol, q=quoteVol
          // NOTE: `P` (priceChangePercent) does NOT exist in miniTicker. Calculate from o and c.
          const arr: Array<{ s: string; c: string; o: string }> = JSON.parse(evt.data);
          if (!Array.isArray(arr)) return;

          setTickers(prev => {
            const next = { ...prev };
            for (const t of arr) {
              if (!TICKER_SYMBOLS.includes(t.s)) continue;
              const newPrice  = parseFloat(t.c);
              const openPrice = parseFloat(t.o);
              // Calculate 24h change % from open price (miniTicker provides 24h rolling open)
              const newChange = isFinite(openPrice) && openPrice > 0
                ? ((newPrice - openPrice) / openPrice) * 100
                : (prev[t.s]?.change ?? 0);
              if (!isFinite(newPrice) || newPrice <= 0) continue;
              const old = prev[t.s];

              let flash: "up" | "down" | null = null;
              if (old && newPrice !== old.price) {
                flash = newPrice > old.price ? "up" : "down";
              }

              next[t.s] = { symbol: t.s, base: t.s.replace("USDT", ""), price: newPrice, change: newChange, flash };

              if (flash) {
                clearTimeout(flashTimers.current[t.s]);
                flashTimers.current[t.s] = setTimeout(() => {
                  setTickers(p => p[t.s] ? { ...p, [t.s]: { ...p[t.s], flash: null } } : p);
                }, 500);
              }
            }
            return next;
          });
        } catch {}
      };

      ws.onerror = () => setWsStatus("error");
      ws.onclose = () => {
        setWsStatus("off");
        reconnectTimer.current = setTimeout(connect, 4000);
      };
    } catch {
      setWsStatus("error");
    }
  }, []);

  /* ── Direct Binance REST fetch (primary price source, every 5s) ── */
  const fetchRestPrices = useCallback(async () => {
    try {
      const syms = JSON.stringify(TICKER_SYMBOLS);
      const url = `https://api.binance.com/api/v3/ticker/24hr?symbols=${encodeURIComponent(syms)}`;
      const r = await window.fetch(url);
      if (!r.ok) return;
      const arr: Array<{ symbol: string; lastPrice: string; priceChangePercent: string }> = await r.json();

      setTickers(prev => {
        const next = { ...prev };
        for (const t of arr) {
          const newPrice  = parseFloat(t.lastPrice);
          const newChange = parseFloat(t.priceChangePercent);
          if (!isFinite(newPrice) || newPrice <= 0) continue;
          const old = prev[t.symbol];
          let flash: "up" | "down" | null = null;
          if (old && Math.abs(newPrice - old.price) > 0) flash = newPrice > old.price ? "up" : "down";
          next[t.symbol] = { symbol: t.symbol, base: t.symbol.replace("USDT",""), price: newPrice, change: newChange, flash };
          if (flash) {
            clearTimeout(flashTimers.current[t.symbol]);
            flashTimers.current[t.symbol] = setTimeout(() => {
              setTickers(p => p[t.symbol] ? { ...p, [t.symbol]: { ...p[t.symbol], flash: null } } : p);
            }, 500);
          }
        }
        return next;
      });
    } catch {}
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      Object.values(flashTimers.current).forEach(clearTimeout);
    };
  }, [connect]);

  // Fetch live prices immediately from Binance REST, then every 5s
  useEffect(() => {
    fetchRestPrices();
    const id = setInterval(fetchRestPrices, 5_000);
    return () => clearInterval(id);
  }, [fetchRestPrices]);

  const ordered = TICKER_SYMBOLS
    .map(s => tickers[s])
    .filter((t): t is TickerData => !!t && isFinite(t.price) && t.price > 0);

  // Duplicate list for seamless infinite scroll
  const doubled = [...ordered, ...ordered];

  const wsColor = wsStatus === "live" ? "#10b981" : wsStatus === "connecting" ? "#f59e0b" : "#ef4444";
  const wsLabel = wsStatus === "live" ? "LIVE" : wsStatus === "connecting" ? "..." : "OFF";

  return (
    <div style={{
      width: "100%", height: 34,
      background: "rgba(0,0,0,0.45)",
      borderBottom: "1px solid rgba(255,255,255,0.06)",
      display: "flex", alignItems: "center",
      overflow: "hidden", position: "relative",
      backdropFilter: "blur(12px)",
      flexShrink: 0,
    }}>
      {/* WS Status */}
      <div style={{
        flexShrink: 0, padding: "0 12px",
        display: "flex", alignItems: "center", gap: 5,
        borderRight: "1px solid rgba(255,255,255,0.07)",
        height: "100%",
      }}>
        <div style={{ position: "relative", width: 7, height: 7 }}>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: wsColor }} />
          {wsStatus === "live" && (
            <div style={{
              position: "absolute", inset: -2, borderRadius: "50%",
              border: `1px solid ${wsColor}`,
              animation: "ticker-ping 2s ease-out infinite",
            }} />
          )}
        </div>
        <span style={{ fontSize: "0.55rem", fontWeight: 800, color: wsColor, letterSpacing: "0.05em" }}>
          {wsLabel}
        </span>
      </div>

      {/* Scrolling ticker */}
      {ordered.length === 0 ? (
        <div style={{ padding: "0 16px", fontSize: "0.6rem", color: "var(--text-muted)" }}>
          Connecting to live feed...
        </div>
      ) : (
        <div style={{
          display: "flex", alignItems: "center",
          animation: `ticker-scroll ${ordered.length * 3.2}s linear infinite`,
          willChange: "transform",
        }}>
          {doubled.map((t, i) => {
            const isGreen = t.change >= 0;
            const changeColor = isGreen ? "#10b981" : "#ef4444";
            const priceColor = t.flash === "up" ? "#10b981" : t.flash === "down" ? "#ef4444" : "#e2e8f0";
            return (
              <div key={`${t.symbol}-${i}`} style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "0 18px", whiteSpace: "nowrap",
                borderRight: "1px solid rgba(255,255,255,0.04)",
                height: 34,
              }}>
                <span style={{ fontSize: "0.65rem", fontWeight: 800, color: "#94a3b8", letterSpacing: "0.02em" }}>
                  {t.base}
                </span>
                <span style={{
                  fontSize: "0.68rem", fontFamily: "monospace", fontWeight: 700,
                  color: priceColor, transition: "color 0.3s",
                }}>
                  {fmt(t.price)}
                </span>
                <span style={{
                  fontSize: "0.6rem", fontWeight: 800, color: changeColor,
                  background: `${changeColor}12`,
                  padding: "1px 5px", borderRadius: 4,
                }}>
                  {isGreen ? "+" : ""}{t.change.toFixed(2)}%
                </span>
              </div>
            );
          })}
        </div>
      )}

      <style>{`
        @keyframes ticker-scroll {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        @keyframes ticker-ping {
          0%   { transform: scale(1); opacity: 0.7; }
          100% { transform: scale(2.8); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
