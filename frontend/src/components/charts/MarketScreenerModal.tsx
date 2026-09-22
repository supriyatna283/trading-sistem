"use client";

import { useEffect, useState, useMemo } from "react";

interface ScreenerItem {
  symbol: string;
  lastPrice: number;
  priceChangePercent: number;
  quoteVolume: number;
}

interface Props {
  onSelect: (symbol: string) => void;
  onClose: () => void;
}

export default function MarketScreenerModal({ onSelect, onClose }: Props) {
  const [data, setData] = useState<ScreenerItem[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    const fetchTopPairs = async () => {
      try {
        const res = await fetch("https://api.binance.com/api/v3/ticker/24hr");
        if (!res.ok) throw new Error("Failed to fetch");
        const json = await res.json();
        
        if (!active) return;

        // Filter only USDT pairs, ignore stablecoins and leveraged tokens if possible
        const usdtPairs = json.filter((t: any) => 
          t.symbol.endsWith("USDT") && 
          !t.symbol.includes("UPUSDT") && 
          !t.symbol.includes("DOWNUSDT") &&
          !t.symbol.includes("BULLUSDT") &&
          !t.symbol.includes("BEARUSDT") &&
          t.symbol !== "USDCUSDT" &&
          t.symbol !== "TUSDUSDT" &&
          t.symbol !== "FDUSDUSDT"
        );

        // Sort by quoteVolume (USDT volume)
        const sorted = usdtPairs.sort((a: any, b: any) => parseFloat(b.quoteVolume) - parseFloat(a.quoteVolume));
        
        // Take top 50 to allow searching within liquid pairs
        const top50 = sorted.slice(0, 50).map((t: any) => ({
          symbol: t.symbol,
          lastPrice: parseFloat(t.lastPrice),
          priceChangePercent: parseFloat(t.priceChangePercent),
          quoteVolume: parseFloat(t.quoteVolume),
        }));

        setData(top50);
        setLoading(false);
      } catch (err) {
        console.error("Screener fetch error:", err);
        if (active) setLoading(false);
      }
    };

    fetchTopPairs();
    const interval = setInterval(fetchTopPairs, 10000); // refresh every 10s

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  // Keyboard support for closing modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const filteredData = useMemo(() => {
    if (!search.trim()) return data.slice(0, 20); // show top 20 by default
    const q = search.toLowerCase().trim();
    return data.filter(d => d.symbol.toLowerCase().includes(q));
  }, [data, search]);

  const formatVolume = (vol: number) => {
    if (vol >= 1e9) return `$${(vol / 1e9).toFixed(2)}B`;
    if (vol >= 1e6) return `$${(vol / 1e6).toFixed(2)}M`;
    if (vol >= 1e3) return `$${(vol / 1e3).toFixed(2)}K`;
    return `$${vol.toFixed(0)}`;
  };

  const formatPrice = (price: number) => {
    if (price < 0.01) return price.toFixed(6);
    if (price < 1) return price.toFixed(4);
    if (price < 10) return price.toFixed(3);
    return price.toLocaleString("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 10000,
      background: "rgba(10,14,23,0.85)", backdropFilter: "blur(8px)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 20
    }} onClick={onClose}>
      
      <div 
        className="glass-card" 
        style={{ 
          width: "100%", maxWidth: 640, maxHeight: "85vh", 
          display: "flex", flexDirection: "column", padding: 0,
          overflow: "hidden", border: "1px solid rgba(255,255,255,0.1)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)"
        }}
        onClick={e => e.stopPropagation()} // prevent modal close on content click
      >
        
        {/* Header */}
        <div style={{ 
          padding: "20px 24px", borderBottom: "1px solid rgba(255,255,255,0.06)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          background: "linear-gradient(to right, rgba(59,130,246,0.05), transparent)"
        }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <h2 style={{ margin: 0, fontSize: "1.1rem", color: "#fff", display: "flex", alignItems: "center", gap: 8 }}>
              📊 Market Screener 
              <span style={{ fontSize: "0.65rem", background: "rgba(59,130,246,0.15)", color: "#93c5fd", padding: "2px 8px", borderRadius: 12, fontWeight: 700 }}>
                Top Liquid Pairs
              </span>
            </h2>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Choose a pair to start analyzing</span>
          </div>
          <button 
            onClick={onClose}
            style={{ 
              background: "rgba(255,255,255,0.05)", border: "none", color: "var(--text-muted)", 
              width: 32, height: 32, borderRadius: "50%", cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center",
              transition: "all 0.2s"
            }}
            onMouseOver={e => e.currentTarget.style.background = "rgba(239,68,68,0.15)"}
            onMouseOut={e => e.currentTarget.style.background = "rgba(255,255,255,0.05)"}
          >
            ✕
          </button>
        </div>

        {/* Search */}
        <div style={{ padding: "16px 24px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
          <div style={{ position: "relative" }}>
            <span style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)", fontSize: "1rem" }}>🔍</span>
            <input 
              autoFocus
              type="text" 
              placeholder="Search pair (e.g. PEPE, SOL)..." 
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ 
                width: "100%", padding: "12px 16px 12px 42px", 
                background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.1)", 
                borderRadius: 8, color: "#fff", fontSize: "0.9rem", outline: "none",
                fontFamily: "inherit", transition: "border 0.2s"
              }}
              onFocus={e => e.currentTarget.style.borderColor = "var(--accent-blue)"}
              onBlur={e => e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)"}
            />
          </div>
        </div>

        {/* Table */}
        <div style={{ flex: 1, overflowY: "auto", padding: "0 24px 24px" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
            <thead style={{ position: "sticky", top: 0, background: "rgba(10,14,23,0.95)", backdropFilter: "blur(4px)", zIndex: 1 }}>
              <tr>
                <th style={{ textAlign: "left", padding: "12px 8px", fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>SYMBOL</th>
                <th style={{ textAlign: "right", padding: "12px 8px", fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>PRICE</th>
                <th style={{ textAlign: "right", padding: "12px 8px", fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>24H CHG</th>
                <th style={{ textAlign: "right", padding: "12px 8px", fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>VOLUME 24H</th>
                <th style={{ textAlign: "right", padding: "12px 8px", fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>ACTION</th>
              </tr>
            </thead>
            <tbody>
              {loading && data.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                    <div style={{ width: 24, height: 24, border: "2px solid rgba(255,255,255,0.1)", borderTopColor: "var(--accent-blue)", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 12px" }} />
                    Scanning Market...
                  </td>
                </tr>
              ) : filteredData.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                    No liquid pair found matching "{search}"
                  </td>
                </tr>
              ) : (
                filteredData.map((item) => (
                  <tr 
                    key={item.symbol} 
                    style={{ borderBottom: "1px solid rgba(255,255,255,0.02)", cursor: "pointer" }}
                    onClick={() => onSelect(item.symbol)}
                  >
                    <td style={{ padding: "12px 8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ fontWeight: 800, color: "var(--text-primary)", fontSize: "0.9rem" }}>{item.symbol.replace("USDT", "")}</span>
                        <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", background: "rgba(255,255,255,0.05)", padding: "2px 4px", borderRadius: 4 }}>USDT</span>
                      </div>
                    </td>
                    <td style={{ padding: "12px 8px", textAlign: "right", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.85rem", color: "var(--text-primary)" }}>
                      {formatPrice(item.lastPrice)}
                    </td>
                    <td style={{ padding: "12px 8px", textAlign: "right", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.85rem", fontWeight: 700, color: item.priceChangePercent >= 0 ? "#4ade80" : "#f87171" }}>
                      <span style={{ padding: "2px 6px", borderRadius: 4, background: item.priceChangePercent >= 0 ? "rgba(74,222,128,0.1)" : "rgba(248,113,113,0.1)" }}>
                        {item.priceChangePercent > 0 ? "+" : ""}{item.priceChangePercent.toFixed(2)}%
                      </span>
                    </td>
                    <td style={{ padding: "12px 8px", textAlign: "right", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                      {formatVolume(item.quoteVolume)}
                    </td>
                    <td style={{ padding: "12px 8px", textAlign: "right" }}>
                      <button 
                        style={{ 
                          background: "var(--accent-blue)", color: "#fff", border: "none", 
                          padding: "6px 12px", borderRadius: 6, fontSize: "0.75rem", fontWeight: 700, 
                          cursor: "pointer", boxShadow: "0 4px 12px rgba(59,130,246,0.3)",
                          display: "inline-flex", alignItems: "center", gap: 4
                        }}
                      >
                        Chart <span>→</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
      </div>
    </div>
  );
}
