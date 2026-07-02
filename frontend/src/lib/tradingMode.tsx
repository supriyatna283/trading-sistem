"use client";

import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────
export type TradingMode = "scalping" | "day_trading" | "swing_trading";

export interface TradingModeConfig {
  id: TradingMode;
  label: string;
  shortLabel: string;
  icon: string;
  color: string;
  bg: string;
  description: string;
  /** Recommended timeframes (ordered by priority) */
  timeframes: string[];
  /** Default chart timeframe */
  defaultTF: string;
  /** Minimum signal score to show */
  minScore: number;
  /** Holding period text */
  holdingPeriod: string;
  /** Default chart indicators preset */
  indicators: {
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
  };
}

// ── Mode Configurations ───────────────────────────────────────────────────────
export const TRADING_MODES: Record<TradingMode, TradingModeConfig> = {
  scalping: {
    id: "scalping",
    label: "Scalping",
    shortLabel: "SCALP",
    icon: "⚡",
    color: "#ef4444",
    bg: "rgba(239,68,68,0.1)",
    description: "Fast entries, small targets, high frequency",
    timeframes: ["1m", "5m", "15m"],
    defaultTF: "5m",
    minScore: 50,
    holdingPeriod: "1m – 30m",
    indicators: {
      ema20: true,
      ema50: false,
      ema200: false,
      volume: true,
      smcZones: true,
      bollingerBands: true,
      rsi: true,
      stochRsi: true,
      macd: false,
      supportResistance: true,
    },
  },
  day_trading: {
    id: "day_trading",
    label: "Day Trading",
    shortLabel: "DAY",
    icon: "🌅",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.1)",
    description: "Intraday momentum, open & close same day",
    timeframes: ["15m", "1h", "4h"],
    defaultTF: "1h",
    minScore: 65,
    holdingPeriod: "30m – 8h",
    indicators: {
      ema20: true,
      ema50: true,
      ema200: false,
      volume: true,
      smcZones: true,
      bollingerBands: false,
      rsi: true,
      stochRsi: false,
      macd: true,
      supportResistance: true,
    },
  },
  swing_trading: {
    id: "swing_trading",
    label: "Swing Trading",
    shortLabel: "SWING",
    icon: "🌊",
    color: "#3b82f6",
    bg: "rgba(59,130,246,0.1)",
    description: "Multi-day trends, higher timeframe structure",
    timeframes: ["4h", "1d"],
    defaultTF: "4h",
    minScore: 75,
    holdingPeriod: "1d – 2w",
    indicators: {
      ema20: false,
      ema50: true,
      ema200: true,
      volume: true,
      smcZones: true,
      bollingerBands: false,
      rsi: true,
      stochRsi: false,
      macd: true,
      supportResistance: true,
    },
  },
};

// ── Context ───────────────────────────────────────────────────────────────────
interface TradingModeContextValue {
  mode: TradingMode;
  config: TradingModeConfig;
  setMode: (m: TradingMode) => void;
  allModes: TradingModeConfig[];
}

const TradingModeContext = createContext<TradingModeContextValue>({
  mode: "day_trading",
  config: TRADING_MODES.day_trading,
  setMode: () => {},
  allModes: Object.values(TRADING_MODES),
});

const STORAGE_KEY = "trading-mode";

export function TradingModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<TradingMode>("day_trading");

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as TradingMode | null;
      if (saved && TRADING_MODES[saved]) setModeState(saved);
    } catch (_) {}
  }, []);

  const setMode = useCallback((m: TradingMode) => {
    setModeState(m);
    try { localStorage.setItem(STORAGE_KEY, m); } catch (_) {}
  }, []);

  return (
    <TradingModeContext.Provider
      value={{
        mode,
        config: TRADING_MODES[mode],
        setMode,
        allModes: Object.values(TRADING_MODES),
      }}
    >
      {children}
    </TradingModeContext.Provider>
  );
}

export function useTradingMode() {
  return useContext(TradingModeContext);
}

// ── Compact Mode Badge ────────────────────────────────────────────────────────
export function TradingModeBadge({ size = "md" }: { size?: "sm" | "md" }) {
  const { config } = useTradingMode();
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: size === "sm" ? 4 : 5,
        padding: size === "sm" ? "2px 7px" : "4px 10px",
        borderRadius: 8,
        fontSize: size === "sm" ? "0.62rem" : "0.7rem",
        fontWeight: 800,
        letterSpacing: "0.06em",
        color: config.color,
        background: config.bg,
        border: `1px solid ${config.color}40`,
        whiteSpace: "nowrap",
      }}
    >
      {config.icon} {size === "sm" ? config.shortLabel : config.label.toUpperCase()}
    </span>
  );
}

// ── Mode Switcher Inline ──────────────────────────────────────────────────────
export function TradingModeSwitcher({ compact = false }: { compact?: boolean }) {
  const { mode, setMode, allModes } = useTradingMode();
  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        background: "rgba(255,255,255,0.03)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: 3,
      }}
    >
      {allModes.map((m) => {
        const isActive = mode === m.id;
        return (
          <button
            key={m.id}
            onClick={() => setMode(m.id)}
            title={`${m.label}: ${m.description}`}
            style={{
              padding: compact ? "4px 8px" : "6px 12px",
              borderRadius: 7,
              border: "none",
              background: isActive ? m.bg : "transparent",
              color: isActive ? m.color : "var(--text-muted)",
              fontSize: compact ? "0.65rem" : "0.72rem",
              fontWeight: 800,
              cursor: "pointer",
              transition: "all 0.18s",
              display: "flex",
              alignItems: "center",
              gap: 4,
              whiteSpace: "nowrap",
              boxShadow: isActive ? `0 0 10px ${m.color}25` : "none",
              letterSpacing: "0.04em",
            }}
          >
            <span>{m.icon}</span>
            {!compact && <span>{m.shortLabel}</span>}
          </button>
        );
      })}
    </div>
  );
}
