"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { API_URL } from "@/lib/utils";

/* ─── Types ──────────────────────────────────────── */
export type ProChartMode = "pd-zones" | "ob-strength" | "sweep" | "killzone" | "full";

interface ProChartProps {
  symbol?: string;
  timeframe?: string;
  mode: ProChartMode;
  height?: number;
}

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

/* ─── Helper: label to price-line config ─────────── */
function zoneColor(type: string) {
  if (type === "PREMIUM" || type === "RESISTANCE" || type === "BEARISH") return "#ef4444";
  if (type === "DISCOUNT" || type === "SUPPORT" || type === "BULLISH") return "#10b981";
  if (type === "EQUILIBRIUM" || type === "MID") return "#f59e0b";
  return "#64748b";
}

/* ─── Main Component ─────────────────────────────── */
export function ProChart({ symbol = "BTCUSDT", timeframe = "1h", mode, height = 480 }: ProChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef     = useRef<any>(null);
  const seriesRef    = useRef<any>(null);
  const volSeriesRef = useRef<any>(null);

  const [status, setStatus] = useState("idle"); // idle | loading | ready | error
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [sym, setSym] = useState(symbol);
  const [tf, setTf] = useState(timeframe);
  const [error, setError] = useState("");
  const [priceLines, setPriceLines] = useState<any[]>([]);
  const [markers, setMarkers] = useState<any[]>([]);

  /* ── 1. Init chart ─────────────────────────────── */
  useEffect(() => {
    if (!containerRef.current) return;

    // Dynamic import to avoid SSR issues
    import("lightweight-charts").then(({ createChart, CrosshairMode, LineStyle }) => {
      if (!containerRef.current) return;

      const chart = createChart(containerRef.current, {
        width:  containerRef.current.clientWidth,
        height: height - 60,
        layout: {
          background:   { color: "transparent" },
          textColor:    "#94a3b8",
          fontFamily:   "JetBrains Mono, monospace",
          fontSize:     11,
        },
        grid: {
          vertLines:   { color: "rgba(255,255,255,0.03)" },
          horzLines:   { color: "rgba(255,255,255,0.03)" },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine:   { color: "rgba(255,255,255,0.2)", labelBackgroundColor: "#1e293b" },
          horzLine:   { color: "rgba(255,255,255,0.2)", labelBackgroundColor: "#1e293b" },
        },
        rightPriceScale: {
          borderColor: "rgba(255,255,255,0.06)",
          textColor:   "#64748b",
          scaleMargins: { top: 0.06, bottom: 0.18 },
        },
        timeScale: {
          borderColor:    "rgba(255,255,255,0.06)",
          timeVisible:    true,
          secondsVisible: false,
        },
        handleScroll:  { mouseWheel: true, pressedMouseMove: true },
        handleScale:   { mouseWheel: true, pinch: true },
      });

      // Candlestick series
      const candleSeries = chart.addCandlestickSeries({
        upColor:          "#10b981",
        downColor:        "#ef4444",
        borderUpColor:    "#10b981",
        borderDownColor:  "#ef4444",
        wickUpColor:      "#10b981",
        wickDownColor:    "#ef4444",
      });

      // Volume histogram
      const volSeries = chart.addHistogramSeries({
        color:       "#3b82f620",
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
      });

      chartRef.current    = chart;
      seriesRef.current   = candleSeries;
      volSeriesRef.current = volSeries;

      // Resize handler
      const ro = new ResizeObserver(entries => {
        for (const entry of entries) {
          chart.resize(entry.contentRect.width, height - 60);
        }
      });
      ro.observe(containerRef.current);

      return () => {
        ro.disconnect();
        chart.remove();
        chartRef.current    = null;
        seriesRef.current   = null;
        volSeriesRef.current = null;
      };
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── 2. Clear all overlays ──────────────────────── */
  const clearOverlays = useCallback(() => {
    if (!seriesRef.current) return;
    // Remove all price lines
    priceLines.forEach(pl => {
      try { seriesRef.current?.removePriceLine(pl); } catch {}
    });
    setPriceLines([]);
    setMarkers([]);
    seriesRef.current?.setMarkers([]);
  }, [priceLines]);

  /* ── 3. Fetch candles ──────────────────────────── */
  const fetchCandles = useCallback(async (s: string, t: string): Promise<Candle[]> => {
    try {
      const res = await fetch(
        `${API_URL}/api/v1/market/candles/${encodeURIComponent(s)}?timeframe=${t}&limit=200`
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();

      // Standard backend format: { candles: [{open_time, open, high, low, close, volume}] }
      const raw: any[] = json.candles ?? json.data ?? json ?? [];
      return raw
        .map((c: any) => {
          // open_time is an ISO string "2024-01-01T00:00:00Z" or unix ms
          let t: number;
          if (typeof c.open_time === "string") {
            t = Math.floor(new Date(c.open_time).getTime() / 1000);
          } else if (typeof c.time === "number") {
            t = c.time > 1e10 ? Math.floor(c.time / 1000) : c.time;
          } else {
            t = Math.floor(Number(c.open_time ?? c.time ?? 0) / 1000);
          }
          return {
            time:   t,
            open:   parseFloat(c.open),
            high:   parseFloat(c.high),
            low:    parseFloat(c.low),
            close:  parseFloat(c.close),
            volume: parseFloat(c.volume ?? 0),
          };
        })
        .filter(c => !isNaN(c.open) && c.time > 0)
        .sort((a, b) => a.time - b.time);
    } catch (e: any) {
      console.error("fetchCandles error:", e.message);
      return [];
    }
  }, []);

  /* ── 4. Draw PD Zone overlays ──────────────────── */
  const drawPDZones = useCallback((data: any) => {
    if (!seriesRef.current || !data) return;
    const newLines: any[] = [];

    const levels = [
      { price: data.range_high,    title: "RANGE HIGH",     color: "#ef4444", style: 0 },
      { price: data.range_low,     title: "RANGE LOW",      color: "#10b981", style: 0 },
      { price: data.equilibrium,   title: "EQ (50%)",       color: "#f59e0b", style: 1 },
      { price: data.ote_high,      title: "OTE 0.79",       color: "#a78bfa", style: 2 },
      { price: data.ote_low,       title: "OTE 0.62",       color: "#a78bfa", style: 2 },
      { price: data.premium_start, title: "PREMIUM",        color: "#ef444460", style: 2 },
      { price: data.discount_end,  title: "DISCOUNT",       color: "#10b98160", style: 2 },
    ];

    levels.forEach(({ price, title, color, style }) => {
      if (!price || isNaN(price)) return;
      try {
        const pl = seriesRef.current.createPriceLine({
          price,
          color,
          lineWidth: style === 0 ? 2 : 1,
          lineStyle: style, // 0=solid, 1=dotted, 2=dashed
          axisLabelVisible: true,
          title,
        });
        newLines.push(pl);
      } catch {}
    });

    setPriceLines(newLines);
  }, []);

  /* ── 5. Draw OB overlays as markers ─────────────── */
  const drawOBMarkers = useCallback((data: any, candles: Candle[]) => {
    if (!seriesRef.current || !data?.order_blocks) return;
    const newLines: any[] = [];

    data.order_blocks.forEach((ob: any) => {
      const color = ob.type === "BULLISH" ? "#10b981" : "#ef4444";
      try {
        const midPrice = (ob.high + ob.low) / 2;
        const pl = seriesRef.current.createPriceLine({
          price:  ob.high,
          color,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: false,
          title: `OB ${ob.grade ?? ""}`,
        });
        const pl2 = seriesRef.current.createPriceLine({
          price:  ob.low,
          color,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: `${ob.type === "BULLISH" ? "🟢" : "🔴"} OB ${ob.grade ?? ""}`,
        });
        newLines.push(pl, pl2);
      } catch {}
    });

    // Markers on candles where OBs were formed
    const mks: any[] = [];
    if (candles.length > 0) {
      data.order_blocks.forEach((ob: any, i: number) => {
        const idx = ob.index ?? 0;
        const candleIdx = Math.max(0, candles.length - 200 + idx);
        const candle = candles[candleIdx];
        if (!candle) return;
        mks.push({
          time:     candle.time,
          position: ob.type === "BULLISH" ? "belowBar" : "aboveBar",
          color:    ob.type === "BULLISH" ? "#10b981" : "#ef4444",
          shape:    ob.type === "BULLISH" ? "arrowUp" : "arrowDown",
          text:     `OB ${ob.grade ?? ""}`,
        });
      });
    }

    if (mks.length > 0) {
      seriesRef.current.setMarkers(mks.sort((a: any, b: any) => a.time - b.time));
      setMarkers(mks);
    }
    setPriceLines(newLines);
  }, []);

  /* ── 6. Draw Liquidity Sweep markers ────────────── */
  const drawSweepMarkers = useCallback((data: any, candles: Candle[]) => {
    if (!seriesRef.current || !candles.length) return;
    const newLines: any[] = [];
    const mks: any[] = [];

    // Draw pool levels
    (data?.pools ?? []).forEach((pool: any) => {
      try {
        const pl = seriesRef.current.createPriceLine({
          price:  pool.price,
          color:  pool.type === "EQH" ? "#ef444490" : "#10b98190",
          lineWidth: 1,
          lineStyle: 1,
          axisLabelVisible: true,
          title:  pool.type === "EQH" ? `EQ-High (${pool.strength})` : `EQ-Low (${pool.strength})`,
        });
        newLines.push(pl);
      } catch {}
    });

    // Draw sweep events
    (data?.sweeps ?? []).forEach((sweep: any) => {
      const idx = sweep.bar_idx ?? 0;
      const candleIdx = Math.max(0, candles.length - 200 + idx);
      const candle = candles[candleIdx];
      if (!candle) return;

      mks.push({
        time:     candle.time,
        position: sweep.type === "SWEEP_LOW" ? "belowBar" : "aboveBar",
        color:    sweep.type === "SWEEP_LOW" ? "#10b981" : "#ef4444",
        shape:    "circle",
        size:     2,
        text:     sweep.confirmed ? "✓ SWEEP" : "SWEEP?",
      });
    });

    if (mks.length > 0) {
      seriesRef.current.setMarkers(mks.sort((a: any, b: any) => a.time - b.time));
      setMarkers(mks);
    }
    setPriceLines(newLines);
  }, []);

  /* ── 7. Draw Killzone shading as price lines ────── */
  const drawKillzoneLines = useCallback((candles: Candle[]) => {
    if (!seriesRef.current || !candles.length) return;
    const newLines: any[] = [];

    // Current session boundaries at well-known prices  
    // Just draw horizontal reference lines for current session
    const last = candles[candles.length - 1];
    if (!last) return;

    // Asia High / Low (last 8 candles proxy)
    const recent = candles.slice(-8);
    const asiaHigh = Math.max(...recent.map(c => c.high));
    const asiaLow  = Math.min(...recent.map(c => c.low));

    [
      { price: asiaHigh, title: "🌏 Asia High", color: "#06b6d4", style: 2 },
      { price: asiaLow,  title: "🌏 Asia Low",  color: "#06b6d4", style: 2 },
    ].forEach(({ price, title, color, style }) => {
      try {
        const pl = seriesRef.current.createPriceLine({ price, color, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title });
        newLines.push(pl);
      } catch {}
    });

    // Session open markers
    const sessionMks = candles.slice(-24).filter((_, i) => i % 8 === 0).map((c, i) => ({
      time:     c.time,
      position: "aboveBar" as const,
      color:    ["#06b6d4", "#10b981", "#3b82f6"][i % 3],
      shape:    "square" as const,
      size:     1,
      text:     ["ASIA", "LONDON", "NY"][i % 3],
    }));
    if (sessionMks.length > 0) {
      seriesRef.current.setMarkers(sessionMks.sort((a: any, b: any) => a.time - b.time));
    }

    setPriceLines(newLines);
  }, []);

  /* ── 8. Full analysis overlays ───────────────────── */
  const drawFullAnalysis = useCallback((data: any, candles: Candle[]) => {
    if (!seriesRef.current) return;
    const newLines: any[] = [];
    const mks: any[] = [];

    // PD levels
    const pdLevels = [
      { price: data.pd?.range_high,    title: "HIGH",     color: "#ef4444", style: 0 },
      { price: data.pd?.range_low,     title: "LOW",      color: "#10b981", style: 0 },
      { price: data.pd?.equilibrium,   title: "EQ",       color: "#f59e0b", style: 1 },
      { price: data.pd?.ote_high,      title: "OTE 0.79", color: "#a78bfa", style: 2 },
      { price: data.pd?.ote_low,       title: "OTE 0.62", color: "#a78bfa", style: 2 },
    ];
    pdLevels.forEach(({ price, title, color, style }) => {
      if (!price || isNaN(price)) return;
      try {
        const pl = seriesRef.current.createPriceLine({ price, color, lineWidth: style === 0 ? 2 : 1, lineStyle: style, axisLabelVisible: true, title });
        newLines.push(pl);
      } catch {}
    });

    // OB markers
    (data.obs ?? []).slice(0, 5).forEach((ob: any) => {
      if (!ob.high || !ob.low) return;
      const color = ob.type === "BULLISH" ? "#10b981" : "#ef4444";
      [ob.high, ob.low].forEach((p, i) => {
        try {
          const pl = seriesRef.current.createPriceLine({ price: p, color, lineWidth: 1, lineStyle: 2, axisLabelVisible: i === 1, title: i === 1 ? `OB ${ob.grade ?? ""}` : "" });
          newLines.push(pl);
        } catch {}
      });
    });

    // Sweep markers
    (data.sweeps ?? []).slice(0, 10).forEach((s: any) => {
      const c = candles[Math.max(0, candles.length - 200 + (s.bar_idx ?? 0))];
      if (!c) return;
      mks.push({
        time: c.time,
        position: s.type === "SWEEP_LOW" ? "belowBar" : "aboveBar",
        color:  s.type === "SWEEP_LOW" ? "#10b981" : "#ef4444",
        shape:  "circle", size: 2,
        text:   "SWEEP",
      });
    });

    if (mks.length) {
      seriesRef.current.setMarkers(mks.sort((a: any, b: any) => a.time - b.time));
      setMarkers(mks);
    }
    setPriceLines(newLines);
  }, []);

  /* ── 9. Main scan ────────────────────────────────── */
  const runScan = useCallback(async () => {
    if (!seriesRef.current) return;
    setStatus("loading");
    setError("");

    try {
      // Clear previous overlays
      clearOverlays();

      // Fetch candles
      const candles = await fetchCandles(sym, tf);
      if (candles.length === 0) throw new Error("No candle data returned");

      // Set candle data
      seriesRef.current.setData(candles.map(c => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })));
      volSeriesRef.current?.setData(candles.map(c => ({
        time: c.time, value: c.volume ?? 0,
        color: c.close >= c.open ? "#10b98120" : "#ef444420",
      })));

      chartRef.current?.timeScale().fitContent();

      // Fetch analysis data
      let analysisResult: any = null;

      if (mode === "pd-zones") {
        const r = await fetch(`${API_URL}/api/v1/pro/pd-zones`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol: sym, timeframe: tf, htf: "1d", limit: 200 }),
        });
        const d = await r.json();
        analysisResult = d;
        drawPDZones(d);
      }

      else if (mode === "ob-strength") {
        const r = await fetch(`${API_URL}/api/v1/pro/ob-strength`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol: sym, timeframe: tf, limit: 200 }),
        });
        const d = await r.json();
        analysisResult = d;
        drawOBMarkers(d, candles);
      }

      else if (mode === "sweep") {
        const r = await fetch(`${API_URL}/api/v1/pro/liquidity-sweep`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol: sym, timeframe: tf, limit: 200 }),
        });
        const d = await r.json();
        analysisResult = d;
        drawSweepMarkers(d, candles);
      }

      else if (mode === "killzone") {
        drawKillzoneLines(candles);
      }

      else if (mode === "full") {
        const r = await fetch(`${API_URL}/api/v1/pro/full-analysis`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol: sym, timeframe: tf, limit: 200 }),
        });
        const d = await r.json();
        analysisResult = d;
        drawFullAnalysis({
          pd:     d.pd_zones,
          obs:    d.ob_strength?.order_blocks ?? [],
          sweeps: d.liquidity_sweep?.sweeps ?? [],
        }, candles);
      }

      setAnalysisData(analysisResult);
      setStatus("ready");

    } catch (e: any) {
      setError(e.message ?? "Scan failed");
      setStatus("error");
    }
  }, [sym, tf, mode, clearOverlays, fetchCandles, drawPDZones, drawOBMarkers, drawSweepMarkers, drawKillzoneLines, drawFullAnalysis]);

  /* ── Legend colors per mode ─────────────────────── */
  const modeConfig: Record<ProChartMode, { color: string; icon: string; label: string; legend: { color: string; label: string }[] }> = {
    "pd-zones":   { color: "#3b82f6", icon: "📊", label: "P/D Zones", legend: [{ color: "#ef4444", label: "Premium / Range High" }, { color: "#f59e0b", label: "Equilibrium (50%)" }, { color: "#10b981", label: "Discount / Range Low" }, { color: "#a78bfa", label: "OTE Zone (0.62–0.79)" }] },
    "ob-strength":{ color: "#f59e0b", icon: "🧱", label: "Order Blocks", legend: [{ color: "#10b981", label: "Bullish OB" }, { color: "#ef4444", label: "Bearish OB" }, { color: "#10b981", label: "▲ Buy Entry Marker" }, { color: "#ef4444", label: "▼ Sell Entry Marker" }] },
    "sweep":      { color: "#ef4444", icon: "🌊", label: "Liquidity Sweep", legend: [{ color: "#ef444490", label: "Equal Highs Pool" }, { color: "#10b98190", label: "Equal Lows Pool" }, { color: "#10b981", label: "● Sweep Low (Long)" }, { color: "#ef4444", label: "● Sweep High (Short)" }] },
    "killzone":   { color: "#10b981", icon: "🎯", label: "Killzone Levels", legend: [{ color: "#06b6d4", label: "Asia High / Low" }, { color: "#10b981", label: "■ LONDON Session" }, { color: "#3b82f6", label: "■ NY Session" }] },
    "full":       { color: "#a78bfa", icon: "⚡", label: "Full Analysis", legend: [{ color: "#ef4444", label: "PD Levels" }, { color: "#f59e0b", label: "Order Blocks" }, { color: "#10b981", label: "Sweeps" }] },
  };

  const cfg = modeConfig[mode];

  return (
    <div style={{ borderRadius: 16, background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.06)", overflow: "hidden" }}>
      {/* Toolbar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.05)", background: "rgba(0,0,0,0.15)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: "1rem" }}>{cfg.icon}</span>
          <span style={{ fontWeight: 800, fontSize: "0.82rem", color: cfg.color }}>{cfg.label} Chart</span>

          {/* Symbol input */}
          <input
            value={sym}
            onChange={e => setSym(e.target.value.toUpperCase())}
            style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 7, padding: "5px 10px", color: "#fff", fontSize: "0.75rem", width: 110, fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}
          />

          {/* Timeframe */}
          <select
            value={tf}
            onChange={e => setTf(e.target.value)}
            style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 7, padding: "5px 10px", color: "#fff", fontSize: "0.75rem" }}
          >
            {["5m","15m","1h","4h","1d"].map(t => <option key={t} value={t}>{t}</option>)}
          </select>

          {/* Scan button */}
          <button
            onClick={runScan}
            disabled={status === "loading"}
            style={{
              padding: "6px 16px", borderRadius: 8, fontWeight: 800, fontSize: "0.75rem", cursor: "pointer",
              background: `${cfg.color}18`, border: `1px solid ${cfg.color}40`, color: cfg.color,
              opacity: status === "loading" ? 0.6 : 1,
              display: "flex", alignItems: "center", gap: 6,
            }}
          >
            {status === "loading" ? (
              <><span style={{ display: "inline-block", animation: "spin 1s linear infinite" }}>⟳</span> Scanning...</>
            ) : "Scan & Mark Chart"}
          </button>
        </div>

        {/* Status */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {status === "ready" && <span style={{ fontSize: "0.7rem", color: "#10b981", fontWeight: 700 }}>✓ Marked</span>}
          {status === "error" && <span style={{ fontSize: "0.7rem", color: "#ef4444", fontWeight: 700 }}>✗ {error}</span>}
          {markers.length > 0 && <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{markers.length} markers</span>}
        </div>
      </div>

      {/* Chart canvas */}
      <div ref={containerRef} style={{ width: "100%", height: height - 60, position: "relative" }}>
        {(status === "idle") && (
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", pointerEvents: "none", gap: 10 }}>
            <div style={{ fontSize: "3rem", opacity: 0.15 }}>{cfg.icon}</div>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", opacity: 0.6 }}>Click "Scan & Mark Chart" to load candles with overlays</div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, padding: "10px 16px", borderTop: "1px solid rgba(255,255,255,0.04)", background: "rgba(0,0,0,0.1)" }}>
        {cfg.legend.map(({ color, label }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 12, height: 3, borderRadius: 2, background: color }} />
            <span style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>{label}</span>
          </div>
        ))}
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
