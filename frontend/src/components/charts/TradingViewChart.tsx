"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
  LineStyle,
  SeriesMarker,
  HistogramData,
  LineData,
  ColorType,
} from "lightweight-charts";

// ---------------------------------------------------------------
// Prop Types
// ---------------------------------------------------------------
export interface SetupOverlay {
  direction: "BUY" | "SELL";
  entry_low: number;
  entry_high: number;
  stop_loss: number;
  take_profit_1?: number;
  take_profit_2?: number;
  take_profit_3?: number;
}

export interface OrderBlockOverlay {
  type: "BULLISH" | "BEARISH";
  low: number;
  high: number;
  start_index?: number;
  mitigated?: boolean;
}

export interface FVGOverlay {
  type: "BULLISH" | "BEARISH";
  low: number;
  high: number;
}

export interface StructureMarker {
  time: number;
  label: "BOS" | "CHOCH" | "HH" | "HL" | "LH" | "LL";
  price: number;
}

interface Props {
  symbol?: string;
  data?: any[];
  setup?: SetupOverlay | null;
  orderBlocks?: OrderBlockOverlay[];
  fvgs?: FVGOverlay[];
  structureMarkers?: StructureMarker[];
  autoFetchSMC?: boolean;
  timeframeInterval?: string;
}

// Indicator visibility state
interface IndicatorState {
  ema20: boolean;
  ema50: boolean;
  ema200: boolean;
  volume: boolean;
  smcZones: boolean;
  bollingerBands: boolean;
  rsi: boolean;
  stochRsi: boolean;
  macd: boolean;
  supportResistance: boolean;
}

type ChartStyle = "candlestick" | "line" | "area";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const WS_RECONNECT_DELAY = 3000;

// ---------------------------------------------------------------
// Calculation Helpers
// ---------------------------------------------------------------
function priceLine(
  series: ISeriesApi<"Candlestick"> | ISeriesApi<"Line"> | ISeriesApi<"Area">,
  price: number,
  title: string,
  color: string,
  style: LineStyle = LineStyle.Solid,
  lineWidth: 1 | 2 | 3 | 4 = 1,
) {
  return series.createPriceLine({ price, color, lineStyle: style, lineWidth, axisLabelVisible: true, title });
}

function calculateEMA(data: any[], period: number): LineData<Time>[] {
  if (data.length === 0) return [];
  const k = 2 / (period + 1);
  let ema = data[0].close;
  return data.map(d => {
    ema = (d.close - ema) * k + ema;
    return { time: d.time, value: ema };
  });
}

function calculateRSI(data: any[], period: number = 14): LineData<Time>[] {
  if (data.length < period + 1) return [];
  const rsiData: LineData<Time>[] = [];
  let gains = 0, losses = 0;

  for (let i = 1; i <= period; i++) {
    const diff = data[i].close - data[i - 1].close;
    if (diff > 0) gains += diff;
    else losses -= diff;
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;
  let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  rsiData.push({ time: data[period].time, value: 100 - 100 / (1 + rs) });

  for (let i = period + 1; i < data.length; i++) {
    const diff = data[i].close - data[i - 1].close;
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsiData.push({ time: data[i].time, value: 100 - 100 / (1 + rs) });
  }
  return rsiData;
}

function calculateStochRSI(data: any[], period = 14, smoothK = 3, smoothD = 3) {
  if (data.length < period) return { kLine: [], dLine: [] };

  const rsiData = calculateRSI(data, period);
  if (rsiData.length < period) return { kLine: [], dLine: [] };

  const stochRsiData: { time: Time; value: number }[] = [];

  for (let i = period - 1; i < rsiData.length; i++) {
    const slice = rsiData.slice(i - period + 1, i + 1);
    const minRsi = Math.min(...slice.map(s => s.value));
    const maxRsi = Math.max(...slice.map(s => s.value));

    let stochRsi = 0;
    if (maxRsi !== minRsi) {
      stochRsi = ((rsiData[i].value - minRsi) / (maxRsi - minRsi)) * 100;
    }

    stochRsiData.push({ time: rsiData[i].time, value: stochRsi });
  }

  const kLine: LineData<Time>[] = [];
  if (stochRsiData.length >= smoothK) {
    for (let i = smoothK - 1; i < stochRsiData.length; i++) {
      const slice = stochRsiData.slice(i - smoothK + 1, i + 1);
      const avg = slice.reduce((sum, d) => sum + d.value, 0) / smoothK;
      kLine.push({ time: stochRsiData[i].time, value: avg });
    }
  }

  const dLine: LineData<Time>[] = [];
  if (kLine.length >= smoothD) {
    for (let i = smoothD - 1; i < kLine.length; i++) {
      const slice = kLine.slice(i - smoothD + 1, i + 1);
      const avg = slice.reduce((sum, d) => sum + d.value, 0) / smoothD;
      dLine.push({ time: kLine[i].time, value: avg });
    }
  }

  return { kLine, dLine };
}

function calculateMACD(data: any[], fast = 12, slow = 26, signal = 9) {
  if (data.length < slow + signal) return { macdLine: [], signalLine: [], histogram: [] };

  const emaFast = calculateEMA(data, fast);
  const emaSlow = calculateEMA(data, slow);

  const macdLine: LineData<Time>[] = [];
  for (let i = 0; i < emaFast.length; i++) {
    const sVal = emaSlow[i]?.value ?? 0;
    const fVal = emaFast[i]?.value ?? 0;
    macdLine.push({ time: emaFast[i].time, value: fVal - sVal });
  }

  // Signal line (EMA of MACD)
  const signalLine: LineData<Time>[] = [];
  if (macdLine.length >= signal) {
    const k = 2 / (signal + 1);
    let ema = macdLine[0].value;
    for (let i = 0; i < macdLine.length; i++) {
      ema = (macdLine[i].value - ema) * k + ema;
      signalLine.push({ time: macdLine[i].time, value: ema });
    }
  }

  // Histogram
  const histogram: HistogramData<Time>[] = [];
  for (let i = 0; i < macdLine.length; i++) {
    const sig = signalLine[i]?.value ?? 0;
    const val = macdLine[i].value - sig;
    histogram.push({
      time: macdLine[i].time,
      value: val,
      color: val >= 0
        ? (i > 0 && val >= (histogram[i - 1]?.value ?? 0) ? "rgba(34,197,94,0.8)" : "rgba(34,197,94,0.4)")
        : (i > 0 && val <= (histogram[i - 1]?.value ?? 0) ? "rgba(239,68,68,0.8)" : "rgba(239,68,68,0.4)"),
    });
  }

  return { macdLine, signalLine, histogram };
}

function calculateBollingerBands(data: any[], period = 20, stdDev = 2) {
  const upper: LineData<Time>[] = [];
  const middle: LineData<Time>[] = [];
  const lower: LineData<Time>[] = [];

  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const avg = slice.reduce((s: number, d: any) => s + d.close, 0) / period;
    const variance = slice.reduce((s: number, d: any) => s + Math.pow(d.close - avg, 2), 0) / period;
    const sd = Math.sqrt(variance);

    const t = data[i].time;
    middle.push({ time: t, value: avg });
    upper.push({ time: t, value: avg + stdDev * sd });
    lower.push({ time: t, value: avg - stdDev * sd });
  }
  return { upper, middle, lower };
}

function formatPrice(val: number): string {
  if (!val && val !== 0) return "-";
  return val > 10
    ? val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : val.toFixed(5);
}

// ---------------------------------------------------------------
// Component
// ---------------------------------------------------------------
export default function TradingViewChart({
  symbol = "BTCUSDT",
  data,
  setup,
  orderBlocks = [],
  fvgs = [],
  structureMarkers = [],
  autoFetchSMC = false,
  timeframeInterval = "1h",
}: Props) {
  // Main chart container
  const mainContainerRef = useRef<HTMLDivElement>(null);
  const rsiContainerRef = useRef<HTMLDivElement>(null);
  const stochRsiContainerRef = useRef<HTMLDivElement>(null);
  const macdContainerRef = useRef<HTMLDivElement>(null);

  const chartRef = useRef<IChartApi | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);
  const stochRsiChartRef = useRef<IChartApi | null>(null);
  const macdChartRef = useRef<IChartApi | null>(null);

  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lineSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const areaSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ema20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema50SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema200SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  // Bollinger Bands
  const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbMiddleRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null);

  // RSI pane
  const rsiSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  // Stoch RSI pane
  const stochRsiKRef = useRef<ISeriesApi<"Line"> | null>(null);
  const stochRsiDRef = useRef<ISeriesApi<"Line"> | null>(null);
  // MACD pane
  const macdLineRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdHistRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const wsReconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsDestroyedRef = useRef(false);
  const priceLineRefs = useRef<any[]>([]);
  const chartDataRef = useRef<any[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [interval, setInterval_TF] = useState(timeframeInterval);
  const [smcData, setSmcData] = useState<{ orderBlocks: OrderBlockOverlay[]; fvgs: FVGOverlay[] } | null>(null);
  const [smcStructure, setSmcStructure] = useState<StructureMarker[]>([]);
  const [wsStatus, setWsStatus] = useState<"connecting" | "live" | "disconnected">("connecting");
  const [chartStyle, setChartStyle] = useState<ChartStyle>("candlestick");
  const [showIndicatorPanel, setShowIndicatorPanel] = useState(false);
  const [indicators, setIndicators] = useState<IndicatorState>({
    ema20: true, ema50: false, ema200: true, volume: true,
    smcZones: true, bollingerBands: false, rsi: true, stochRsi: false, macd: false,
    supportResistance: true,
  });

  const [tooltip, setTooltip] = useState<{
    open: number; high: number; low: number; close: number;
    volume: number; time: string; direction: "up" | "down";
    changeAbs: number; changePct: number;
  } | null>(null);

  const [countdown, setCountdown] = useState("");
  const [srLevels, setSrLevels] = useState<{ supports: number[]; resistances: number[] }>({ supports: [], resistances: [] });

  // Drawing tool state
  const [drawingMode, setDrawingMode] = useState<"none" | "hline">("none");
  const [drawingsCount, setDrawingsCount] = useState(0); // reactive count for Clear button
  const userDrawingsRef = useRef<any[]>([]);

  // ── Countdown Timer (fixed for 4h/1d candle boundaries) ──
  useEffect(() => {
    const tfMs: Record<string, number> = { "1m": 60000, "5m": 300000, "15m": 900000, "1h": 3600000, "4h": 14400000, "1d": 86400000 };
    const updateCountdown = () => {
      const ms = tfMs[interval] || 3600000;
      const now = Date.now();
      // Binance candle boundaries are aligned to UTC epoch multiples of the interval
      const currentCandleStart = Math.floor(now / ms) * ms;
      const nextCandleStart = currentCandleStart + ms;
      const remaining = Math.max(0, Math.floor((nextCandleStart - now) / 1000));
      const h = Math.floor(remaining / 3600);
      const m = Math.floor((remaining % 3600) / 60);
      const s = remaining % 60;
      let str = "";
      if (h > 0) str += `${h}h `;
      str += `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
      setCountdown(str);
    };
    updateCountdown();
    const timer = setInterval(updateCountdown, 1000);
    return () => clearInterval(timer);
  }, [interval]);

  // ── ESC key handler for drawing mode ──
  useEffect(() => {
    if (drawingMode === "none") return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDrawingMode("none");
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [drawingMode]);

  useEffect(() => { setInterval_TF(timeframeInterval); }, [timeframeInterval]);

  // ── Effective overlays ──
  const effectiveOBs = orderBlocks.length > 0 ? orderBlocks : (smcData?.orderBlocks ?? []);
  const effectiveFVGs = fvgs.length > 0 ? fvgs : (smcData?.fvgs ?? []);
  const effectiveMarkers = structureMarkers.length > 0 ? structureMarkers : smcStructure;

  // ── Fetch SMC ──
  const fetchSMC = useCallback(async (sym: string, tf: string) => {
    if (!autoFetchSMC) return;
    try {
      const [smcRes, structRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/analysis/smc/${sym}?timeframe=${tf}&demo=false`).then(r => r.json()),
        fetch(`${API_URL}/api/v1/analysis/structure/${sym}?timeframe=${tf}&demo=false`).then(r => r.json()),
      ]);
      const obs: OrderBlockOverlay[] = (smcRes?.order_blocks ?? []).map((ob: any) => ({
        type: ob.type, low: ob.low, high: ob.high, mitigated: ob.mitigated,
      }));
      const fvgsData: FVGOverlay[] = (smcRes?.fvgs ?? []).map((f: any) => ({
        type: f.type, low: f.low, high: f.high,
      }));
      setSmcData({ orderBlocks: obs, fvgs: fvgsData });
      const markers: StructureMarker[] = (structRes?.structure_labels ?? []).map((l: any) => ({
        time: l.time ? new Date(l.time).getTime() : Date.now(), label: l.label, price: l.price ?? 0,
      }));
      setSmcStructure(markers);
    } catch (e) { console.warn("SMC fetch failed:", e); }
  }, [autoFetchSMC]);

  // ── Fetch S/R levels ──
  const fetchSR = useCallback(async (sym: string, tf: string) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/market-intel/support-resistance/${sym}?timeframe=${tf}`);
      const data = await res.json();
      setSrLevels({
        supports: data.supports || [],
        resistances: data.resistances || [],
      });
    } catch (e) { console.warn("S/R fetch failed:", e); }
  }, []);

  // ── Clear price lines ──
  const clearPriceLines = () => {
    const activeSeries = seriesRef.current || lineSeriesRef.current || areaSeriesRef.current;
    if (activeSeries) {
      priceLineRefs.current.forEach(pl => {
        try { activeSeries.removePriceLine(pl); } catch (_) { }
      });
    }
    priceLineRefs.current = [];
  };

  // ── Draw annotations ──
  const drawAnnotations = useCallback((showSMC = true) => {
    const series = seriesRef.current || lineSeriesRef.current || areaSeriesRef.current;
    if (!series) return;

    clearPriceLines();
    const lines: any[] = [];

    // Setup levels
    const s = setup;
    if (s) {
      if (s.stop_loss) lines.push(priceLine(series, s.stop_loss, "⛔ SL", "#ef4444", LineStyle.Dashed, 2));
      if (s.entry_low) lines.push(priceLine(series, s.entry_low, "▶ Entry Lo", "#f59e0b", LineStyle.Solid, 2));
      if (s.entry_high) lines.push(priceLine(series, s.entry_high, "▶ Entry Hi", "#f59e0b", LineStyle.Solid, 1));
      if (s.take_profit_1) lines.push(priceLine(series, s.take_profit_1, "🎯 TP1", "#10b981", LineStyle.Dashed, 1));
      if (s.take_profit_2) lines.push(priceLine(series, s.take_profit_2, "🎯 TP2", "#34d399", LineStyle.Dashed, 1));
      if (s.take_profit_3) lines.push(priceLine(series, s.take_profit_3, "🎯 TP3", "#6ee7b7", LineStyle.Dashed, 1));
    }

    // S/R lines
    if (indicators.supportResistance) {
      srLevels.supports.slice(0, 3).forEach((s, i) => {
        lines.push(priceLine(series, s, `S${i + 1}`, "rgba(34,197,94,0.6)", LineStyle.Dashed, 1));
      });
      srLevels.resistances.slice(0, 3).forEach((r, i) => {
        lines.push(priceLine(series, r, `R${i + 1}`, "rgba(239,68,68,0.6)", LineStyle.Dashed, 1));
      });
    }

    if (showSMC) {
      effectiveOBs.slice(-6).forEach((ob) => {
        if (ob.mitigated) return;
        const color = ob.type === "BULLISH" ? "rgba(16,185,129,0.8)" : "rgba(239,68,68,0.8)";
        const label = ob.type === "BULLISH" ? "📦 Bull OB" : "📦 Bear OB";
        lines.push(priceLine(series, ob.low, `${label} Lo`, color, LineStyle.Dotted, 1));
        lines.push(priceLine(series, ob.high, `${label} Hi`, color, LineStyle.Dotted, 1));
      });
      effectiveFVGs.slice(-4).forEach((fvg) => {
        const color = fvg.type === "BULLISH" ? "rgba(16,185,129,0.5)" : "rgba(239,68,68,0.5)";
        const label = fvg.type === "BULLISH" ? "FVG ▲" : "FVG ▼";
        lines.push(priceLine(series, fvg.low, `${label} Lo`, color, LineStyle.Dotted, 1));
        lines.push(priceLine(series, fvg.high, `${label} Hi`, color, LineStyle.Dotted, 1));
      });
    }

    priceLineRefs.current = lines;

    // Structure markers
    const LABEL_CONFIG: Record<string, { position: "aboveBar" | "belowBar"; color: string; shape: "arrowUp" | "arrowDown" | "circle" }> = {
      BOS: { position: "aboveBar", color: "#f59e0b", shape: "circle" },
      CHOCH: { position: "aboveBar", color: "#a78bfa", shape: "circle" },
      HH: { position: "aboveBar", color: "#10b981", shape: "arrowUp" },
      HL: { position: "belowBar", color: "#34d399", shape: "arrowUp" },
      LH: { position: "aboveBar", color: "#f87171", shape: "arrowDown" },
      LL: { position: "belowBar", color: "#ef4444", shape: "arrowDown" },
    };

    if (effectiveMarkers.length > 0 && seriesRef.current) {
      const markers: SeriesMarker<Time>[] = effectiveMarkers
        .filter(m => m.time > 0)
        .map(m => {
          const cfg = LABEL_CONFIG[m.label] ?? { position: "aboveBar" as const, color: "#6b7280", shape: "circle" as const };
          return { time: (m.time / 1000) as Time, position: cfg.position, color: cfg.color, shape: cfg.shape, text: m.label, size: m.label === "BOS" || m.label === "CHOCH" ? 2 : 1 };
        })
        .sort((a, b) => (a.time as number) - (b.time as number));
      seriesRef.current.setMarkers(markers);
    }
  }, [setup, effectiveOBs, effectiveFVGs, effectiveMarkers, srLevels, indicators.supportResistance]);

  useEffect(() => { drawAnnotations(indicators.smcZones); }, [drawAnnotations, indicators.smcZones]);

  const toggleIndicator = useCallback((key: keyof IndicatorState) => {
    setIndicators(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Apply indicator visibility + trigger resize for sub-pane charts
  useEffect(() => {
    ema20SeriesRef.current?.applyOptions({ visible: indicators.ema20 });
    ema50SeriesRef.current?.applyOptions({ visible: indicators.ema50 });
    ema200SeriesRef.current?.applyOptions({ visible: indicators.ema200 });
    volumeSeriesRef.current?.applyOptions({ visible: indicators.volume });
    bbUpperRef.current?.applyOptions({ visible: indicators.bollingerBands });
    bbMiddleRef.current?.applyOptions({ visible: indicators.bollingerBands });
    bbLowerRef.current?.applyOptions({ visible: indicators.bollingerBands });

    // Fix: force sub-chart resize after display toggle (prevents blank panes)
    requestAnimationFrame(() => {
      if (indicators.rsi && rsiContainerRef.current && rsiChartRef.current) {
        rsiChartRef.current.applyOptions({ width: rsiContainerRef.current.clientWidth });
        rsiChartRef.current.timeScale().fitContent();
      }
      if (indicators.stochRsi && stochRsiContainerRef.current && stochRsiChartRef.current) {
        stochRsiChartRef.current.applyOptions({ width: stochRsiContainerRef.current.clientWidth });
        stochRsiChartRef.current.timeScale().fitContent();
      }
      if (indicators.macd && macdContainerRef.current && macdChartRef.current) {
        macdChartRef.current.applyOptions({ width: macdContainerRef.current.clientWidth });
        macdChartRef.current.timeScale().fitContent();
      }
    });
  }, [indicators]);

  const setupWebSocket = useCallback((sym: string, tf: string) => {
    if (wsReconnectRef.current) { clearTimeout(wsReconnectRef.current); wsReconnectRef.current = null; }
    if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); }
    if (wsDestroyedRef.current) return;

    try {
      setWsStatus("connecting");

      // Binance kline stream — reliable, works directly in browser, no proxy needed
      const bnSymbol = sym.toLowerCase().replace("-", "");
      const bnInterval = tf === "1d" ? "1d" : tf; // Binance uses same format
      const wsUrl = `wss://stream.binance.com:9443/ws/${bnSymbol}@kline_${bnInterval}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => setWsStatus("live");

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const k = msg?.k; // Binance kline object
          if (!k) return;

          const tick: CandlestickData<Time> = {
            time: (Math.floor(k.t / 1000)) as Time,
            open: parseFloat(k.o),
            high: parseFloat(k.h),
            low: parseFloat(k.l),
            close: parseFloat(k.c),
          };
          const volValue = parseFloat(k.v);

          seriesRef.current?.update(tick);
          lineSeriesRef.current?.update({ time: tick.time, value: tick.close });
          areaSeriesRef.current?.update({ time: tick.time, value: tick.close });
          volumeSeriesRef.current?.update({
            time: tick.time, value: volValue,
            color: tick.close >= tick.open ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)",
          });
        } catch (e) { console.warn("WS message parse error:", e); }
      };

      ws.onerror = (e) => { console.warn("Binance WS error:", e); setWsStatus("disconnected"); };
      ws.onclose = () => {
        setWsStatus("disconnected");
        if (!wsDestroyedRef.current) {
          wsReconnectRef.current = setTimeout(() => setupWebSocket(sym, tf), WS_RECONNECT_DELAY);
        }
      };
    } catch (err) { console.error("WS init failed:", err); setWsStatus("disconnected"); }
  }, []);

  // ── WebSocket ──


  // ---------------------------------------------------------------
  // Chart theme config
  // ---------------------------------------------------------------
  const chartOptions = {
    autoSize: true,  // Smooth high-DPI/retina rendering + auto-resize
    layout: {
      background: { type: ColorType.Solid, color: "transparent" },
      textColor: "#8b95a9",
      fontFamily: "'Inter', sans-serif",
      fontSize: 11,
    },
    grid: {
      vertLines: { color: "rgba(42, 49, 66, 0.25)" },
      horzLines: { color: "rgba(42, 49, 66, 0.25)" },
    },
    crosshair: {
      mode: 0,
      vertLine: { color: "rgba(59, 130, 246, 0.3)", width: 1, style: 2 },
      horzLine: { color: "rgba(59, 130, 246, 0.3)", width: 1, style: 2, labelBackgroundColor: "#3b82f6" },
    },
    rightPriceScale: {
      borderColor: "rgba(42, 49, 66, 0.4)",
      scaleMargins: { top: 0.05, bottom: 0.15 },
    },
    timeScale: {
      borderColor: "rgba(42, 49, 66, 0.4)",
      timeVisible: true,
      secondsVisible: false,
      minBarSpacing: 3,  // Smoother zoom levels
    },
    handleScroll: { mouseWheel: true, pressedMouseMove: true },
    handleScale: { axisPressedMouseMove: true, mouseWheel: true },
  };

  // ---------------------------------------------------------------
  // Main Chart + Sub-pane init
  // ---------------------------------------------------------------
  useEffect(() => {
    if (!mainContainerRef.current) return;
    wsDestroyedRef.current = false;

    // Clean up any existing chart instances before creating new ones
    // (handles React strict mode double-mounting without breaking React DOM)
    if (chartRef.current) { try { chartRef.current.remove(); } catch (_) {} chartRef.current = null; }
    if (rsiChartRef.current) { try { rsiChartRef.current.remove(); } catch (_) {} rsiChartRef.current = null; }
    if (stochRsiChartRef.current) { try { stochRsiChartRef.current.remove(); } catch (_) {} stochRsiChartRef.current = null; }
    if (macdChartRef.current) { try { macdChartRef.current.remove(); } catch (_) {} macdChartRef.current = null; }

    // --- Main Chart ---
    const chart = createChart(mainContainerRef.current, chartOptions as any);

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e", downColor: "#ef4444",
      borderUpColor: "#22c55e", borderDownColor: "#ef4444",
      wickUpColor: "#22c55e", wickDownColor: "#ef4444",
      visible: chartStyle === "candlestick",
    });

    const lineSeries = chart.addLineSeries({ 
      color: "#3b82f6", lineWidth: 2, 
      visible: chartStyle === "line" 
    });
    
    const areaSeries = chart.addAreaSeries({ 
      lineColor: "#3b82f6", topColor: "rgba(59,130,246,0.4)", bottomColor: "rgba(59,130,246,0.0)", 
      visible: chartStyle === "area" 
    });

    // Volume
    const volumeSeries = chart.addHistogramSeries({
      color: "#26a69a", priceFormat: { type: "volume" }, priceScaleId: "",
    });
    chart.priceScale("").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

    // EMAs
    const ema20Series = chart.addLineSeries({ color: "rgba(59,130,246,0.9)", lineWidth: 1, crosshairMarkerVisible: false });
    const ema50Series = chart.addLineSeries({ color: "rgba(245,158,11,0.9)", lineWidth: 1, crosshairMarkerVisible: false, visible: false });
    const ema200Series = chart.addLineSeries({ color: "rgba(236,72,153,0.9)", lineWidth: 2, crosshairMarkerVisible: false });

    // Bollinger Bands
    const bbUpper = chart.addLineSeries({ color: "rgba(147,51,234,0.5)", lineWidth: 1, crosshairMarkerVisible: false, visible: false });
    const bbMiddle = chart.addLineSeries({ color: "rgba(147,51,234,0.3)", lineWidth: 1, crosshairMarkerVisible: false, lineStyle: LineStyle.Dashed, visible: false });
    const bbLower = chart.addLineSeries({ color: "rgba(147,51,234,0.5)", lineWidth: 1, crosshairMarkerVisible: false, visible: false });

    chartRef.current = chart;
    seriesRef.current = candleSeries;
    lineSeriesRef.current = lineSeries;
    areaSeriesRef.current = areaSeries;
    volumeSeriesRef.current = volumeSeries;
    ema20SeriesRef.current = ema20Series;
    ema50SeriesRef.current = ema50Series;
    ema200SeriesRef.current = ema200Series;
    bbUpperRef.current = bbUpper;
    bbMiddleRef.current = bbMiddle;
    bbLowerRef.current = bbLower;

    // --- RSI Sub-Chart ---
    let rsiChart: IChartApi | null = null;
    let rsiSeries: ISeriesApi<"Line"> | null = null;

    if (rsiContainerRef.current) {
      rsiChart = createChart(rsiContainerRef.current, {
        ...chartOptions as any,
        rightPriceScale: {
          borderColor: "rgba(42,49,66,0.4)",
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: { visible: false },
      });

      rsiSeries = rsiChart.addLineSeries({
        color: "#f59e0b", lineWidth: 2,
        priceFormat: { type: "custom", minMove: 0.01, formatter: (p: number) => p.toFixed(1) },
      });

      // OB/OS bands
      rsiSeries.createPriceLine({ price: 70, color: "rgba(239,68,68,0.4)", lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "" });
      rsiSeries.createPriceLine({ price: 30, color: "rgba(34,197,94,0.4)", lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "" });
      rsiSeries.createPriceLine({ price: 50, color: "rgba(255,255,255,0.1)", lineStyle: LineStyle.Dotted, lineWidth: 1, axisLabelVisible: false, title: "" });

      rsiChartRef.current = rsiChart;
      rsiSeriesRef.current = rsiSeries;
    }

    // --- STOCH RSI Sub-Chart ---
    let stochRsiChart: IChartApi | null = null;
    let stochRsiK: ISeriesApi<"Line"> | null = null;
    let stochRsiD: ISeriesApi<"Line"> | null = null;

    if (stochRsiContainerRef.current) {
      stochRsiChart = createChart(stochRsiContainerRef.current, {
        ...chartOptions as any,
        rightPriceScale: {
          borderColor: "rgba(42,49,66,0.4)",
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: { visible: false },
      });

      stochRsiK = stochRsiChart.addLineSeries({
        color: "#10b981", lineWidth: 2,
        priceFormat: { type: "custom", minMove: 0.01, formatter: (p: number) => p.toFixed(1) },
      });
      stochRsiD = stochRsiChart.addLineSeries({
        color: "#ef4444", lineWidth: 1,
        priceFormat: { type: "custom", minMove: 0.01, formatter: (p: number) => p.toFixed(1) },
      });

      // OB/OS bands
      stochRsiK.createPriceLine({ price: 80, color: "rgba(239,68,68,0.4)", lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "" });
      stochRsiK.createPriceLine({ price: 20, color: "rgba(34,197,94,0.4)", lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "" });
      stochRsiK.createPriceLine({ price: 50, color: "rgba(255,255,255,0.1)", lineStyle: LineStyle.Dotted, lineWidth: 1, axisLabelVisible: false, title: "" });

      stochRsiChartRef.current = stochRsiChart;
      stochRsiKRef.current = stochRsiK;
      stochRsiDRef.current = stochRsiD;
    }

    // --- MACD Sub-Chart ---
    let macdChart: IChartApi | null = null;
    let macdLineSeries: ISeriesApi<"Line"> | null = null;
    let macdSignalSeries: ISeriesApi<"Line"> | null = null;
    let macdHistSeries: ISeriesApi<"Histogram"> | null = null;

    if (macdContainerRef.current) {
      macdChart = createChart(macdContainerRef.current, {
        ...chartOptions as any,
        rightPriceScale: {
          borderColor: "rgba(42,49,66,0.4)",
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: { visible: false },
      });

      macdHistSeries = macdChart.addHistogramSeries({
        color: "#26a69a",
        priceFormat: { type: "custom", minMove: 0.01, formatter: (p: number) => p.toFixed(4) },
      });
      macdLineSeries = macdChart.addLineSeries({ color: "#3b82f6", lineWidth: 2 });
      macdSignalSeries = macdChart.addLineSeries({ color: "#ef4444", lineWidth: 1 });

      macdChartRef.current = macdChart;
      macdLineRef.current = macdLineSeries;
      macdSignalRef.current = macdSignalSeries;
      macdHistRef.current = macdHistSeries;
    }

    // Sync time scales (with guard to prevent infinite sync loops)
    let isSyncing = false;
    const syncFrom = (source: IChartApi, targets: (IChartApi | null)[]) => {
      source.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range || isSyncing) return;
        isSyncing = true;
        targets.forEach(t => { if (t) t.timeScale().setVisibleLogicalRange(range); });
        isSyncing = false;
      });
    };
    const subCharts = [rsiChart, stochRsiChart, macdChart].filter(Boolean) as IChartApi[];
    syncFrom(chart, subCharts);
    subCharts.forEach(sub => syncFrom(sub, [chart]));

    // OHLCV Tooltip
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) { setTooltip(null); return; }
      const candle = param.seriesData.get(candleSeries) as CandlestickData<Time> | undefined;
      const vol = param.seriesData.get(volumeSeries) as HistogramData<Time> | undefined;
      if (candle && typeof candle.open !== "undefined") {
        const ts = typeof param.time === "number"
          ? new Date(param.time * 1000).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
          : String(param.time);
        const changeAbs = candle.close - candle.open;
        const changePct = candle.open > 0 ? (changeAbs / candle.open) * 100 : 0;
        setTooltip({
          open: candle.open, high: candle.high, low: candle.low, close: candle.close,
          volume: vol?.value ?? 0, time: ts,
          direction: candle.close >= candle.open ? "up" : "down",
          changeAbs, changePct,
        });
      }
    });

    // ── Load Data ──
    const fillChartData = async () => {
      setIsLoading(true);
      try {
        let chartData: any[] = [];

        if (data && data.length > 0) {
          chartData = data.map((c) => ({
            time: (new Date(c.open_time).getTime() / 1000) as Time,
            open: parseFloat(c.open), high: parseFloat(c.high),
            low: parseFloat(c.low), close: parseFloat(c.close),
            volume: parseFloat(c.volume || 0),
          })).sort((a, b) => (a.time as number) - (b.time as number));
        } else {
          try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000);
            const res = await fetch(`${API_URL}/api/v1/market/candles/${symbol}?timeframe=${interval}&limit=500`, { signal: controller.signal });
            clearTimeout(timeoutId);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            if (json.candles && Array.isArray(json.candles)) {
              chartData = json.candles.map((c: any) => ({
                time: (new Date(c.open_time).getTime() / 1000) as Time,
                open: parseFloat(c.open), high: parseFloat(c.high),
                low: parseFloat(c.low), close: parseFloat(c.close),
                volume: parseFloat(c.volume || 0),
              })).sort((a: any, b: any) => a.time - b.time);
            }
          } catch (e: any) {
            if (e.name !== "AbortError") console.error("Fetch failed:", e);
          }
        }

        chartDataRef.current = chartData;

        if (chartData.length > 0) {
          // Main data
          candleSeries.setData(chartData as CandlestickData<Time>[]);
          const lineData = chartData.map(d => ({ time: d.time, value: d.close }));
          lineSeries.setData(lineData);
          areaSeries.setData(lineData);

          // Volume
          const volumeData: HistogramData<Time>[] = chartData.map((d: any) => ({
            time: d.time, value: d.volume,
            color: d.close >= d.open ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)",
          }));
          volumeSeries.setData(volumeData);

          // EMAs
          ema20Series.setData(calculateEMA(chartData, 20));
          ema50Series.setData(calculateEMA(chartData, 50));
          ema200Series.setData(calculateEMA(chartData, 200));

          // Bollinger Bands
          const bb = calculateBollingerBands(chartData);
          bbUpper.setData(bb.upper);
          bbMiddle.setData(bb.middle);
          bbLower.setData(bb.lower);

          // RSI
          if (rsiSeries) {
            const rsiData = calculateRSI(chartData, 14);
            rsiSeries.setData(rsiData);
          }

          // Stoch RSI
          if (stochRsiK && stochRsiD) {
            const stochRsiData = calculateStochRSI(chartData, 14, 3, 3);
            stochRsiK.setData(stochRsiData.kLine);
            stochRsiD.setData(stochRsiData.dLine);
          }

          // MACD
          if (macdLineSeries && macdSignalSeries && macdHistSeries) {
            const macd = calculateMACD(chartData);
            macdLineSeries.setData(macd.macdLine);
            macdSignalSeries.setData(macd.signalLine);
            macdHistSeries.setData(macd.histogram);
          }
        }

        chart.timeScale().fitContent();
        rsiChart?.timeScale().fitContent();
        stochRsiChart?.timeScale().fitContent();
        macdChart?.timeScale().fitContent();
        drawAnnotations(indicators.smcZones);
      } catch (error) {
        console.error("Error loading chart:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fillChartData();
    if (autoFetchSMC) fetchSMC(symbol, interval);
    fetchSR(symbol, interval);
    setupWebSocket(symbol, interval);

    // Resize
    const handleResize = () => {
      if (mainContainerRef.current) chart.applyOptions({ width: mainContainerRef.current.clientWidth });
      if (rsiContainerRef.current && rsiChart) rsiChart.applyOptions({ width: rsiContainerRef.current.clientWidth });
      if (stochRsiContainerRef.current && stochRsiChart) stochRsiChart.applyOptions({ width: stochRsiContainerRef.current.clientWidth });
      if (macdContainerRef.current && macdChart) macdChart.applyOptions({ width: macdContainerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);
    handleResize();

    // Drawing tool: click to add horizontal line (stored for deletion)
    chart.subscribeClick((param) => {
      if (drawingMode === "hline" && param.point) {
        const price = candleSeries.coordinateToPrice(param.point.y);
        if (price !== null) {
          const pl = candleSeries.createPriceLine({
            price, color: "#818cf8", lineStyle: LineStyle.Solid,
            lineWidth: 1, axisLabelVisible: true, title: `📏 ${formatPrice(price)}`,
          });
          userDrawingsRef.current.push(pl);
          setDrawingsCount(c => c + 1); // trigger re-render to show Clear button
          setDrawingMode("none");
        }
      }
    });

    // Reset drawing state when chart rebuilds
    return () => {
      wsDestroyedRef.current = true;
      if (wsReconnectRef.current) clearTimeout(wsReconnectRef.current);
      if (wsRef.current) wsRef.current.close();
      window.removeEventListener("resize", handleResize);
      userDrawingsRef.current = [];
      setDrawingsCount(0);
      chart.remove();
      rsiChart?.remove();
      stochRsiChart?.remove();
      macdChart?.remove();
      chartRef.current = null;
      seriesRef.current = null;
      rsiChartRef.current = null;
      stochRsiChartRef.current = null;
      macdChartRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, data, interval, autoFetchSMC, fetchSMC, fetchSR, setupWebSocket]);

  // ── Sync Chart Style Visibility ──
  useEffect(() => {
    if (seriesRef.current) seriesRef.current.applyOptions({ visible: chartStyle === "candlestick" });
    if (lineSeriesRef.current) lineSeriesRef.current.applyOptions({ visible: chartStyle === "line" });
    if (areaSeriesRef.current) areaSeriesRef.current.applyOptions({ visible: chartStyle === "area" });
  }, [chartStyle]);

  const hasSMC = effectiveOBs.length > 0 || effectiveFVGs.length > 0;
  const hasSetup = !!setup;

  return (
    <div className="glass-card" style={{ padding: 0, overflow: "hidden", position: "relative", height: "100%", display: "flex", flexDirection: "column" }}>

      {/* ── Chart Header ── */}
      <div style={{ padding: "8px 16px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0, gap: 8 }}>
        {/* Left */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontWeight: 800, fontSize: "1rem" }}>{symbol}</span>
          {/* WS Status */}
          <span className="badge badge-active" style={{ padding: "2px 7px", display: "flex", alignItems: "center", gap: 4, cursor: "default" }}>
            <span style={{
              width: 6, height: 6, borderRadius: "50%",
              background: wsStatus === "live" ? "#22c55e" : wsStatus === "connecting" ? "#f59e0b" : "#ef4444",
              display: "inline-block",
              animation: wsStatus !== "disconnected" ? "pulse-dot 1.4s infinite" : "none",
            }} />
            {wsStatus === "live" ? "LIVE" : wsStatus === "connecting" ? "..." : "⟳"}
          </span>
          {/* Countdown */}
          <div style={{
            display: "flex", alignItems: "center", gap: 4,
            background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)",
            padding: "2px 8px", borderRadius: 6, fontSize: "0.72rem",
            fontFamily: "'JetBrains Mono', monospace", color: "var(--text-secondary)"
          }}>
            <span style={{ color: "var(--accent-blue)" }}>🕒</span>
            <span style={{ fontWeight: 700 }}>{countdown || "--:--"}</span>
          </div>
          {hasSetup && <span style={{ fontSize: "0.68rem", padding: "2px 6px", borderRadius: 6, background: "rgba(245,158,11,0.15)", color: "#f59e0b", fontWeight: 700 }}>📐 Setup</span>}
          {hasSMC && indicators.smcZones && <span style={{ fontSize: "0.68rem", padding: "2px 6px", borderRadius: 6, background: "rgba(139,92,246,0.15)", color: "#a78bfa", fontWeight: 700 }}>📦 SMC</span>}
        </div>

        {/* Right: Chart Style + Timeframes */}
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          {/* Chart Style Selector */}
          {(["candlestick", "line", "area"] as ChartStyle[]).map(st => (
            <button key={st} onClick={() => setChartStyle(st)} style={{
              background: chartStyle === st ? "rgba(139,92,246,0.15)" : "transparent",
              border: chartStyle === st ? "1px solid rgba(139,92,246,0.3)" : "1px solid transparent",
              color: chartStyle === st ? "#a78bfa" : "var(--text-muted)",
              padding: "2px 6px", borderRadius: 4, fontSize: "0.68rem", fontWeight: 600,
              cursor: "pointer", transition: "all 0.15s", textTransform: "capitalize",
            }}>
              {st === "candlestick" ? "🕯️" : st === "line" ? "📈" : "📊"}
            </button>
          ))}

          <div style={{ width: 1, height: 16, background: "var(--border)", margin: "0 4px" }} />

          {/* Timeframes */}
          {TIMEFRAMES.map((tf) => (
            <button key={tf} onClick={() => setInterval_TF(tf)} style={{
              background: tf === interval ? "rgba(59,130,246,0.15)" : "transparent",
              border: tf === interval ? "1px solid rgba(59,130,246,0.3)" : "1px solid transparent",
              color: tf === interval ? "var(--accent-blue)" : "var(--text-secondary)",
              padding: "2px 8px", borderRadius: 6, fontSize: "0.72rem", fontWeight: 600,
              cursor: "pointer", fontFamily: "'JetBrains Mono', monospace", transition: "all 0.15s",
            }}>
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* ── Indicator & Tools Bar ── */}
      <div style={{
        padding: "5px 16px", borderBottom: "1px solid var(--border)",
        display: "flex", gap: 6, alignItems: "center", flexShrink: 0,
        background: "rgba(0,0,0,0.12)", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginRight: 2, fontWeight: 600 }}>INDICATORS</span>
          {([
            { key: "ema20", label: "EMA 20", color: "rgba(59,130,246,0.9)" },
            { key: "ema50", label: "EMA 50", color: "rgba(245,158,11,0.9)" },
            { key: "ema200", label: "EMA 200", color: "rgba(236,72,153,0.9)" },
            { key: "bollingerBands", label: "BB", color: "rgba(147,51,234,0.9)" },
            { key: "volume", label: "VOL", color: "rgba(38,166,154,0.9)" },
            { key: "rsi", label: "RSI", color: "rgba(245,158,11,0.9)" },
            { key: "stochRsi", label: "STOCH RSI", color: "rgba(16,185,129,0.9)" },
            { key: "macd", label: "MACD", color: "rgba(59,130,246,0.9)" },
            { key: "supportResistance", label: "S/R", color: "rgba(34,197,94,0.9)" },
            { key: "smcZones", label: "SMC", color: "rgba(139,92,246,0.9)" },
          ] as { key: keyof IndicatorState; label: string; color: string }[]).map(({ key, label, color }) => (
            <button key={key} onClick={() => toggleIndicator(key)} style={{
              padding: "2px 8px", borderRadius: 20,
              border: `1px solid ${indicators[key] ? color : "var(--border)"}`,
              background: indicators[key] ? `${color.replace("0.9)", "0.12)")}` : "transparent",
              color: indicators[key] ? color : "var(--text-muted)",
              fontSize: "0.68rem", fontWeight: 700, cursor: "pointer", transition: "all 0.15s",
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {label}
            </button>
          ))}
        </div>

        {/* Drawing Tools */}
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginRight: 2, fontWeight: 600 }}>TOOLS</span>
          <button
            onClick={() => setDrawingMode(drawingMode === "hline" ? "none" : "hline")}
            title="Horizontal Line"
            style={{
              padding: "2px 8px", borderRadius: 20,
              border: `1px solid ${drawingMode === "hline" ? "rgba(129,140,248,0.6)" : "var(--border)"}`,
              background: drawingMode === "hline" ? "rgba(129,140,248,0.12)" : "transparent",
              color: drawingMode === "hline" ? "#818cf8" : "var(--text-muted)",
              fontSize: "0.68rem", fontWeight: 700, cursor: "pointer", transition: "all 0.15s",
            }}
          >
            ── H-Line
          </button>
          {drawingsCount > 0 && (
            <button
              onClick={() => {
                const activeSeries = seriesRef.current || lineSeriesRef.current || areaSeriesRef.current;
                if (activeSeries) {
                  userDrawingsRef.current.forEach(pl => {
                    try { activeSeries.removePriceLine(pl); } catch (_) {}
                  });
                  userDrawingsRef.current = [];
                  setDrawingsCount(0);
                }
              }}
              title="Clear all drawn lines"
              style={{
                padding: "2px 8px", borderRadius: 20,
                border: "1px solid rgba(239,68,68,0.4)",
                background: "rgba(239,68,68,0.08)",
                color: "rgba(239,68,68,0.8)",
                fontSize: "0.68rem", fontWeight: 700, cursor: "pointer", transition: "all 0.15s",
              }}
            >
              ✕ Clear ({drawingsCount})
            </button>
          )}
        </div>
      </div>

      {/* ── Main Chart Canvas ── */}
      <div ref={mainContainerRef} style={{ flexGrow: 1, width: "100%", position: "relative", minHeight: 300 }}>
        {/* OHLCV Tooltip */}
        {tooltip && (
          <div style={{
            position: "absolute", top: 8, left: 8, zIndex: 15,
            background: "rgba(10,14,23,0.92)", backdropFilter: "blur(12px)",
            border: `1px solid ${tooltip.direction === "up" ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)"}`,
            borderRadius: 8, padding: "8px 12px",
            fontFamily: "'JetBrains Mono', monospace", fontSize: "0.7rem",
            pointerEvents: "none", display: "flex", flexDirection: "column", gap: 2,
          }}>
            <div style={{ color: "var(--text-muted)", fontSize: "0.62rem", marginBottom: 1 }}>{tooltip.time}</div>
            <div style={{ display: "flex", gap: 10 }}>
              <span style={{ color: "var(--text-muted)" }}>O <span style={{ color: "var(--text-primary)" }}>{formatPrice(tooltip.open)}</span></span>
              <span style={{ color: "var(--text-muted)" }}>H <span style={{ color: "#22c55e" }}>{formatPrice(tooltip.high)}</span></span>
              <span style={{ color: "var(--text-muted)" }}>L <span style={{ color: "#ef4444" }}>{formatPrice(tooltip.low)}</span></span>
              <span style={{ color: "var(--text-muted)" }}>C <span style={{ color: tooltip.direction === "up" ? "#22c55e" : "#ef4444", fontWeight: 700 }}>{formatPrice(tooltip.close)}</span></span>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <span style={{ color: "var(--text-muted)" }}>
                Chg <span style={{ color: tooltip.direction === "up" ? "#22c55e" : "#ef4444", fontWeight: 700 }}>
                  {tooltip.changeAbs > 0 ? "+" : ""}{formatPrice(tooltip.changeAbs)} ({tooltip.changePct > 0 ? "+" : ""}{tooltip.changePct.toFixed(2)}%)
                </span>
              </span>
              <span style={{ color: "var(--text-muted)" }}>
                Vol <span style={{ color: "rgba(38,166,154,0.9)" }}>{tooltip.volume.toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>
              </span>
            </div>
          </div>
        )}

        {/* EMA Legend */}
        <div style={{ position: "absolute", bottom: 8, left: 8, zIndex: 10, pointerEvents: "none", display: "flex", gap: 8, fontSize: "0.68rem", fontFamily: "'JetBrains Mono', monospace" }}>
          {indicators.ema20 && <span style={{ color: "rgba(59,130,246,1)", fontWeight: 700 }}>EMA 20</span>}
          {indicators.ema50 && <span style={{ color: "rgba(245,158,11,1)", fontWeight: 700 }}>EMA 50</span>}
          {indicators.ema200 && <span style={{ color: "rgba(236,72,153,1)", fontWeight: 700 }}>EMA 200</span>}
          {indicators.bollingerBands && <span style={{ color: "rgba(147,51,234,1)", fontWeight: 700 }}>BB(20,2)</span>}
        </div>

        {/* Drawing mode cursor indicator */}
        {drawingMode !== "none" && (
          <div style={{
            position: "absolute", top: 8, right: 8, zIndex: 20,
            background: "rgba(129,140,248,0.15)", border: "1px solid rgba(129,140,248,0.4)",
            borderRadius: 8, padding: "6px 12px", fontSize: "0.72rem", color: "#818cf8", fontWeight: 700,
          }}>
            🎯 Click to place {drawingMode === "hline" ? "Horizontal Line" : ""} — press ESC to cancel
          </div>
        )}
      </div>

      {/* ── RSI Sub-Pane (always rendered, toggled via display) ── */}
      <div style={{ borderTop: "1px solid var(--border)", position: "relative", display: indicators.rsi ? "block" : "none" }}>
        <div style={{
          position: "absolute", top: 4, left: 12, zIndex: 10, pointerEvents: "none",
          fontSize: "0.65rem", fontWeight: 700, color: "rgba(245,158,11,0.8)",
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          RSI(14)
        </div>
        <div ref={rsiContainerRef} style={{ width: "100%", height: 100 }} />
      </div>

      {/* ── STOCH RSI Sub-Pane (always rendered, toggled via display) ── */}
      <div style={{ borderTop: "1px solid var(--border)", position: "relative", display: indicators.stochRsi ? "block" : "none" }}>
        <div style={{
          position: "absolute", top: 4, left: 12, zIndex: 10, pointerEvents: "none",
          fontSize: "0.65rem", fontWeight: 700, color: "rgba(16,185,129,0.8)",
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          STOCH RSI(14,3,3)
        </div>
        <div ref={stochRsiContainerRef} style={{ width: "100%", height: 100 }} />
      </div>

      {/* ── MACD Sub-Pane (always rendered, toggled via display) ── */}
      <div style={{ borderTop: "1px solid var(--border)", position: "relative", display: indicators.macd ? "block" : "none" }}>
        <div style={{
          position: "absolute", top: 4, left: 12, zIndex: 10, pointerEvents: "none",
          fontSize: "0.65rem", fontWeight: 700, color: "rgba(59,130,246,0.8)",
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          MACD(12,26,9)
        </div>
        <div ref={macdContainerRef} style={{ width: "100%", height: 100 }} />
      </div>

      {/* ── Loading Overlay ── */}
      {isLoading && (
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, zIndex: 20, background: "rgba(10,14,23,0.6)", backdropFilter: "blur(4px)" }}>
          <div style={{ width: 28, height: 28, border: "2px solid var(--border)", borderTopColor: "var(--accent-blue)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
          <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Loading {symbol} ({interval})...</span>
        </div>
      )}

      {/* Animations moved to globals.css — no duplicate dangerouslySetInnerHTML needed */}
    </div>
  );
}

