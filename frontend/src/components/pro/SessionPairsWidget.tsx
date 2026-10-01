"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { API_URL } from "@/lib/utils";

/* ─────────────────────────────────────────────────────────
   Types
───────────────────────────────────────────────────────── */
interface PairData {
  symbol: string;
  base_asset: string;
  price: number;
  change_24h: number;
  volume_24h_usd: number;
  volume_24h_fmt: string;
  volume_rank: number;
  high_24h: number;
  low_24h: number;
  is_killzone_fav: boolean;
  session_relevance: "PRIMARY" | "SECONDARY" | "BONUS";
}

interface SessionPairsData {
  current_session: string;
  session_label: string;
  session_emoji: string;
  session_color: string;
  session_description: string;
  session_focus: string;
  utc_time: string;
  utc_hour: number;
  is_killzone_active: boolean;
  minutes_to_next: number;
  next_session: string;
  total_session_vol_fmt: string;
  top_mover: PairData | null;
  top_volume: PairData | null;
  pairs: PairData[];
}

type SessionId = "ASIA" | "LONDON" | "NY_OPEN" | "NY_PM" | "DEAD";

const SESSION_COLORS: Record<string, string> = {
  ASIA:    "#f59e0b",
  LONDON:  "#3b82f6",
  NY_OPEN: "#10b981",
  NY_PM:   "#8b5cf6",
  DEAD:    "#475569",
};

const SESSION_LABELS: Record<string, string> = {
  ASIA:    "🌏 Asia",
  LONDON:  "🇬🇧 London",
  NY_OPEN: "🗽 NY Open",
  NY_PM:   "🌆 NY PM",
  DEAD:    "😴 Dead Zone",
};

/* ─── Helpers ── */
function fmt(price: number): string {
  if (!isFinite(price) || price <= 0) return "--";
  if (price >= 1000)    return price.toLocaleString("en", { maximumFractionDigits: 2 });
  if (price >= 1)       return price.toFixed(4);
  if (price >= 0.001)   return price.toFixed(5);
  return price.toExponential(3);
}

function VolBar({ pct }: { pct: number }) {
  return (
    <div style={{ height: 3, borderRadius: 99, background: "rgba(255,255,255,0.06)", overflow: "hidden", width: 48 }}>
      <div style={{ height: "100%", width: `${pct}%`, borderRadius: 99, background: "rgba(59,130,246,0.7)" }} />
    </div>
  );
}

/* ─── Session Tab Button ── */
function SessionTab({ id, active, onClick }: { id: string; active: boolean; onClick: () => void }) {
  const c = SESSION_COLORS[id] ?? "#64748b";
  return (
    <button onClick={onClick} style={{
      padding: "6px 12px", borderRadius: 8, fontSize: "0.72rem", fontWeight: 700,
      cursor: "pointer", whiteSpace: "nowrap",
      background: active ? `${c}18` : "transparent",
      border: `1px solid ${active ? `${c}40` : "transparent"}`,
      color: active ? c : "var(--text-muted)",
      transition: "all 0.2s",
    }}>
      {SESSION_LABELS[id]}
    </button>
  );
}

/* ─── Pair Row ── */
function PairRow({
  pair, rank, maxVol, onSelect, selected, livePrice,
}: {
  pair: PairData;
  rank: number;
  maxVol: number;
  onSelect: (sym: string) => void;
  selected: boolean;
  livePrice?: { price: number; change: number; flash: "up" | "down" | null };
}) {
  // Prefer WebSocket live data over REST snapshot
  const price    = livePrice?.price  ?? pair.price;
  const change   = livePrice?.change ?? pair.change_24h;
  const flash    = livePrice?.flash;
  const isGreen = change >= 0;
  const changeColor = isGreen ? "#10b981" : "#ef4444";
  const volPct = maxVol > 0 ? (pair.volume_24h_usd / maxVol) * 100 : 0;
  const isPrimary = pair.session_relevance === "PRIMARY";

  // Flash background color for price change
  const flashBg = flash === "up"
    ? "rgba(16,185,129,0.12)"
    : flash === "down"
      ? "rgba(239,68,68,0.12)"
      : undefined;

  return (
    <div
      onClick={() => onSelect(pair.symbol)}
      style={{
        display: "grid",
        gridTemplateColumns: "28px 1fr 90px 72px 60px",
        alignItems: "center",
        gap: 8,
        padding: "9px 12px",
        borderRadius: 10,
        cursor: "pointer",
        transition: "background 0.15s",
        background: flashBg ?? (selected
          ? "rgba(59,130,246,0.08)"
          : isPrimary
            ? "rgba(255,255,255,0.025)"
            : "transparent"),
        border: `1px solid ${selected ? "rgba(59,130,246,0.3)" : isPrimary ? "rgba(255,255,255,0.05)" : "transparent"}`,
        marginBottom: 4,
      }}
    >
      {/* Rank */}
      <div style={{ textAlign: "center" }}>
        {isPrimary ? (
          <span style={{ fontSize: "0.65rem", fontWeight: 900, color: "#f59e0b" }}>★</span>
        ) : (
          <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", fontFamily: "monospace" }}>
            {rank}
          </span>
        )}
      </div>

      {/* Symbol + volume bar */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontWeight: 800, fontSize: "0.78rem", fontFamily: "monospace" }}>
            {pair.base_asset}
          </span>
          <span style={{ fontSize: "0.52rem", color: "var(--text-muted)" }}>/USDT</span>
          {pair.is_killzone_fav && (
            <span style={{ fontSize: "0.48rem", padding: "1px 5px", borderRadius: 4, background: "rgba(245,158,11,0.15)", color: "#f59e0b", fontWeight: 800 }}>
              KZ
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
          <VolBar pct={volPct} />
          <span style={{ fontSize: "0.58rem", color: "var(--text-muted)" }}>{pair.volume_24h_fmt}</span>
        </div>
      </div>

      {/* Price — real-time via WS */}
      <div style={{
        textAlign: "right", fontFamily: "monospace", fontSize: "0.75rem", fontWeight: 700,
        color: flash === "up" ? "#10b981" : flash === "down" ? "#ef4444" : "#fff",
        transition: "color 0.3s",
      }}>
        {fmt(price)}
      </div>

      {/* Change — real-time */}
      <div style={{
        textAlign: "right", fontFamily: "monospace", fontSize: "0.75rem", fontWeight: 800,
        color: changeColor,
      }}>
        {isGreen ? "+" : ""}{change.toFixed(2)}%
      </div>

      {/* 24h range mini-bar */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
        <span style={{ fontSize: "0.5rem", color: "#ef4444" }}>{fmt(pair.high_24h)}</span>
        <div style={{ height: 2, width: 36, borderRadius: 99, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
          {(() => {
            const range = pair.high_24h - pair.low_24h;
            const pos = range > 0 ? ((pair.price - pair.low_24h) / range) * 100 : 50;
            return (
              <div style={{ height: "100%", width: `${pos}%`, background: isGreen ? "#10b981" : "#ef4444", borderRadius: 99 }} />
            );
          })()}
        </div>
        <span style={{ fontSize: "0.5rem", color: "#10b981" }}>{fmt(pair.low_24h)}</span>
      </div>
    </div>
  );
}

/* ─── Main Component ── */
interface SessionPairsWidgetProps {
  onSymbolSelect?: (symbol: string) => void;
  compact?: boolean;
}

// Real-time price overrides from WebSocket
type PriceMap = Record<string, { price: number; change: number; flash: "up" | "down" | null }>;

export function SessionPairsWidget({ onSymbolSelect, compact = false }: SessionPairsWidgetProps) {
  const [data, setData] = useState<SessionPairsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [viewSession, setViewSession] = useState<SessionId | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [filter, setFilter] = useState<"ALL" | "KZ" | "TOP10">("ALL");
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [prices, setPrices] = useState<PriceMap>({});
  const [wsStatus, setWsStatus] = useState<"connecting" | "live" | "error" | "off">("off");
  const wsRef = useRef<WebSocket | null>(null);
  const flashTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  /* ── REST fetch (volume + session metadata, every 60s) ── */
  const fetchData = useCallback(async (sessionOverride?: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ top_n: "25" });
      if (sessionOverride) params.set("session", sessionOverride);
      const r = await window.fetch(`${API_URL}/api/v1/pro/session-pairs?${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const json: SessionPairsData = await r.json();
      setData(json);
      setLastRefresh(new Date());
    } catch (e) {
      console.error("session-pairs error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData(viewSession ?? undefined);
    const id = setInterval(() => fetchData(viewSession ?? undefined), 60_000);
    return () => clearInterval(id);
  }, [viewSession, fetchData]);

  /* ── Direct Binance REST price fetch (every 5s) — bypasses backend ── */
  /* This is the PRIMARY price source; WS layered on top for 1s updates  */
  const fetchBinancePrices = useCallback(async () => {
    try {
      // Fetch only the symbols we display — much faster than full ticker
      const syms = JSON.stringify([
        "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
        "ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","DOTUSDT",
        "OPUSDT","ARBUSDT","NEARUSDT","INJUSDT","PEPEUSDT",
        "SUIUSDT","TONUSDT","MATICUSDT","LTCUSDT","ATOMUSDT",
      ]);
      const url = `https://api.binance.com/api/v3/ticker/24hr?symbols=${encodeURIComponent(syms)}`;
      const r = await window.fetch(url);
      if (!r.ok) return;
      const arr: Array<{ symbol: string; lastPrice: string; priceChangePercent: string; highPrice: string; lowPrice: string }> = await r.json();

      setPrices(prev => {
        const next = { ...prev };
        for (const t of arr) {
          const newPrice  = parseFloat(t.lastPrice);
          const newChange = parseFloat(t.priceChangePercent);
          if (!isFinite(newPrice) || newPrice <= 0) continue;
          const old = prev[t.symbol];

          let flash: "up" | "down" | null = null;
          if (old && Math.abs(newPrice - old.price) > 0) {
            flash = newPrice > old.price ? "up" : "down";
          }
          next[t.symbol] = { price: newPrice, change: isFinite(newChange) ? newChange : 0, flash };

          if (flash) {
            clearTimeout(flashTimers.current[t.symbol]);
            flashTimers.current[t.symbol] = setTimeout(() => {
              setPrices(p => p[t.symbol] ? { ...p, [t.symbol]: { ...p[t.symbol], flash: null } } : p);
            }, 500);
          }
        }
        return next;
      });
    } catch {
      // Silent — WS will cover if REST fails
    }
  }, []);

  useEffect(() => {
    // Fetch immediately on mount, then every 5 seconds
    fetchBinancePrices();
    const id = setInterval(fetchBinancePrices, 5_000);
    return () => clearInterval(id);
  }, [fetchBinancePrices]);

  /* ── Binance WebSocket: !miniTicker@arr → real-time price every ~1s ── */
  useEffect(() => {
    const WS_URL = "wss://stream.binance.com:9443/ws/!miniTicker@arr";

    const connect = () => {
      try {
        setWsStatus("connecting");
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => setWsStatus("live");

        ws.onmessage = (evt) => {
          try {
            const tickers: Array<{ s: string; c: string; P: string }> = JSON.parse(evt.data);
            if (!Array.isArray(tickers)) return;

            setPrices(prev => {
              const next = { ...prev };
              for (const t of tickers) {
                if (!t.s.endsWith("USDT")) continue;
                const newPrice  = parseFloat(t.c);
                const newChange = parseFloat(t.P);
                const old = prev[t.s];

                let flash: "up" | "down" | null = null;
                if (old && Math.abs(newPrice - old.price) > 0) {
                  flash = newPrice > old.price ? "up" : "down";
                }
                next[t.s] = { price: newPrice, change: newChange, flash };

                if (flash) {
                  clearTimeout(flashTimers.current[t.s]);
                  flashTimers.current[t.s] = setTimeout(() => {
                    setPrices(p => ({ ...p, [t.s]: { ...p[t.s], flash: null } }));
                  }, 400);
                }
              }
              return next;
            });
          } catch {}
        };

        ws.onerror = () => setWsStatus("error");
        ws.onclose = () => {
          setWsStatus("off");
          setTimeout(connect, 5000);
        };
      } catch {
        setWsStatus("error");
      }
    };

    connect();

    return () => {
      wsRef.current?.close();
      Object.values(flashTimers.current).forEach(clearTimeout);
    };
  }, []);

  const handleSelect = useCallback((sym: string) => {
    setSelected(sym);
    onSymbolSelect?.(sym);
  }, [onSymbolSelect]);

  if (!data && !loading) return null;

  const pairs = data?.pairs ?? [];

  // Apply filter
  const visiblePairs = pairs.filter(p => {
    if (filter === "KZ")    return p.is_killzone_fav;
    if (filter === "TOP10") return p.volume_rank <= 10;
    return true;
  });

  const maxVol = visiblePairs.length > 0 ? Math.max(...visiblePairs.map(p => p.volume_24h_usd)) : 1;
  const sessionColor = data ? (SESSION_COLORS[data.current_session] ?? "#64748b") : "#64748b";

  const allSessions: SessionId[] = ["ASIA", "LONDON", "NY_OPEN", "NY_PM", "DEAD"];

  return (
    <div>
      {/* ── Session Status Banner ── */}
      {data && (
        <div style={{
          padding: "14px 18px", borderRadius: 14, marginBottom: 14,
          background: `${sessionColor}10`,
          border: `1px solid ${sessionColor}30`,
          display: "flex", flexDirection: "column", gap: 8,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {/* Live dot */}
              <div style={{ position: "relative", width: 10, height: 10 }}>
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: data.is_killzone_active ? "#10b981" : "#475569" }} />
                {data.is_killzone_active && (
                  <div style={{ position: "absolute", inset: -3, borderRadius: "50%", border: `2px solid #10b981`, animation: "ping 1.5s ease-out infinite", opacity: 0.5 }} />
                )}
              </div>
              <div>
                <div style={{ fontWeight: 900, fontSize: "0.9rem", color: sessionColor }}>
                  {data.session_emoji} {data.session_label} Session
                </div>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: 2 }}>
                  {data.session_description}
                </div>
              </div>
            </div>

            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>{data.utc_time}</div>
              {data.is_killzone_active ? (
                <div style={{ fontSize: "0.62rem", color: "#10b981", fontWeight: 700, marginTop: 2 }}>
                  ● KILLZONE ACTIVE
                </div>
              ) : (
                <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", marginTop: 2 }}>
                  Next: {SESSION_LABELS[data.next_session]} in ~{data.minutes_to_next}m
                </div>
              )}
            </div>
          </div>

          {/* Focus tip */}
          <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", padding: "7px 10px", borderRadius: 8, background: "rgba(0,0,0,0.15)", lineHeight: 1.5 }}>
            💡 {data.session_focus}
          </div>

          {/* Stats */}
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            {data.top_volume && (
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>
                Vol leader:{" "}
                <span style={{ fontWeight: 800, fontFamily: "monospace", color: "#fff" }}>
                  {data.top_volume.base_asset}
                </span>{" "}
                <span style={{ color: "#3b82f6" }}>{data.top_volume.volume_24h_fmt}</span>
              </div>
            )}
            {data.top_mover && (
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>
                Top mover:{" "}
                <span style={{ fontWeight: 800, fontFamily: "monospace", color: "#fff" }}>
                  {data.top_mover.base_asset}
                </span>{" "}
                <span style={{ color: data.top_mover.change_24h >= 0 ? "#10b981" : "#ef4444", fontWeight: 700 }}>
                  {data.top_mover.change_24h >= 0 ? "+" : ""}{data.top_mover.change_24h.toFixed(2)}%
                </span>
              </div>
            )}
            <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>
              Total vol: <span style={{ color: "#fff", fontWeight: 700 }}>{data.total_session_vol_fmt}</span>
            </div>
            {lastRefresh && (
              <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                Updated {lastRefresh.toLocaleTimeString("en", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Session Selector ── */}
      <div style={{ display: "flex", gap: 5, marginBottom: 12, overflowX: "auto", padding: "2px 0" }}>
        <button
          onClick={() => { setViewSession(null); fetchData(undefined); }}
          style={{
            padding: "6px 12px", borderRadius: 8, fontSize: "0.72rem", fontWeight: 700,
            cursor: "pointer", whiteSpace: "nowrap",
            background: viewSession === null ? "rgba(255,255,255,0.08)" : "transparent",
            border: `1px solid ${viewSession === null ? "rgba(255,255,255,0.15)" : "transparent"}`,
            color: viewSession === null ? "#fff" : "var(--text-muted)",
          }}
        >
          Current
        </button>
        {allSessions.map(s => (
          <SessionTab
            key={s} id={s}
            active={viewSession === s}
            onClick={() => { setViewSession(s); fetchData(s); }}
          />
        ))}
        <button
          onClick={() => fetchData(viewSession ?? undefined)}
          disabled={loading}
          style={{ marginLeft: "auto", padding: "6px 12px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 700, cursor: "pointer", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "var(--text-muted)" }}
        >
          {loading ? "⟳" : "↻"}
        </button>
      </div>

      {/* ── Filter ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <div style={{ display: "flex", gap: 4 }}>
          {(["ALL", "KZ", "TOP10"] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{
              padding: "4px 10px", borderRadius: 6, fontSize: "0.65rem", fontWeight: 700, cursor: "pointer",
              background: filter === f ? "rgba(99,102,241,0.15)" : "rgba(255,255,255,0.03)",
              border: `1px solid ${filter === f ? "rgba(99,102,241,0.35)" : "rgba(255,255,255,0.05)"}`,
              color: filter === f ? "#6366f1" : "var(--text-muted)",
            }}>
              {f === "ALL" ? "All Pairs" : f === "KZ" ? "⭐ KZ Fav" : "Top 10 Vol"}
            </button>
          ))}
        </div>
        <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
          {/* WebSocket status badge */}
          <span style={{
            fontSize: "0.58rem", padding: "1px 7px", borderRadius: 4, fontWeight: 800,
            background: wsStatus === "live" ? "rgba(16,185,129,0.12)" : wsStatus === "connecting" ? "rgba(245,158,11,0.12)" : "rgba(239,68,68,0.12)",
            color:      wsStatus === "live" ? "#10b981"               : wsStatus === "connecting" ? "#f59e0b"               : "#ef4444",
            border:     `1px solid ${wsStatus === "live" ? "rgba(16,185,129,0.3)" : wsStatus === "connecting" ? "rgba(245,158,11,0.3)" : "rgba(239,68,68,0.3)"}`,
          }}>
            {wsStatus === "live" ? "● WS LIVE" : wsStatus === "connecting" ? "⟳ WS" : "○ WS OFF"}
          </span>
          {visiblePairs.length} pairs · <span style={{ color: "#f59e0b" }}>★ KZ</span>
        </div>
      </div>

      {/* ── Table Header ── */}
      <div style={{
        display: "grid", gridTemplateColumns: "28px 1fr 90px 72px 60px",
        gap: 8, padding: "5px 12px", marginBottom: 4,
      }}>
        {["#", "PAIR / VOLUME", "PRICE", "24H%", "RANGE"].map(h => (
          <div key={h} style={{ fontSize: "0.55rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", textAlign: h === "#" ? "center" : "right", letterSpacing: "0.05em" }}>
            {h === "PAIR / VOLUME" ? <span style={{ textAlign: "left", display: "block" }}>{h}</span> : h}
          </div>
        ))}
      </div>

      {/* ── Pair Rows ── */}
      {loading && !data ? (
        <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)", fontSize: "0.8rem" }}>
          <div style={{ fontSize: "1.5rem", marginBottom: 8, animation: "spin .9s linear infinite", display: "inline-block" }}>⟳</div>
          <div>Loading live volume data...</div>
        </div>
      ) : visiblePairs.length === 0 ? (
        <div style={{ textAlign: "center", padding: "30px 0", color: "var(--text-muted)", fontSize: "0.78rem" }}>No pairs found</div>
      ) : (
        <div>
          {visiblePairs.map((pair, i) => (
            <PairRow
              key={pair.symbol}
              pair={pair}
              rank={i + 1}
              maxVol={maxVol}
              selected={selected === pair.symbol}
              onSelect={handleSelect}
              livePrice={prices[pair.symbol]}
            />
          ))}
        </div>
      )}

      {selected && (
        <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 10, background: "rgba(59,130,246,0.07)", border: "1px solid rgba(59,130,246,0.2)", fontSize: "0.72rem", color: "#3b82f6", fontWeight: 700 }}>
          ✓ {selected} dipilih — akan digunakan di chart & analisis
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }
        @keyframes ping { 0% { transform:scale(1); opacity:0.6; } 100% { transform:scale(2.5); opacity:0; } }
      `}</style>
    </div>
  );
}
