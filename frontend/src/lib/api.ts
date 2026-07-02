/* =============================================
   API Client
   ============================================= */

export interface AlertRecord {
  id: number;
  setup_id?: number | null;
  channel: string;
  message: string;
  sent_at?: string | null;
  status: string;
}

export interface RiskSettings {
  account_balance: number;
  risk_per_trade: number;
  max_daily_risk: number;
  max_concurrent_trades: number;
  telegram_chat_id?: string | null;
  email?: string | null;
  alert_enabled?: boolean;
}

export interface PositionSizeResult {
  position_size: number;
  risk_amount: number;
  stop_distance: number;
  stop_distance_pct: number;
  risk_reward?: number;
}

// Server-side (SSR) requires absolute URL to backend.
// Client-side (Browser) now uses absolute URL as well to bypass proxy hang up issues.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

function buildHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) headers["X-API-Key"] = API_KEY;
  return { ...headers, ...(extra as Record<string, string>) };
}

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: buildHeaders(options?.headers),
  });
  if (!res.ok) {
    let message = `API Error: ${res.status}`;
    try {
      const body = await res.json();
      message = body.detail || body.error || message;
      if (typeof message !== "string") message = JSON.stringify(message);
    } catch {
      /* ignore parse errors */
    }
    throw new Error(message);
  }
  return res.json();
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

// Market Data
export const api = {
  getSymbols: () => fetchAPI<{symbols: any[]}>("/api/v1/market/symbols"),
  getCandles: (symbol: string, tf = "1h", limit = 200) =>
    fetchAPI<any>(`/api/v1/market/candles/${symbol}?timeframe=${tf}&limit=${limit}`),

  // Analysis
  getStructure: (symbol: string, tf = "1h") =>
    fetchAPI<any>(`/api/v1/analysis/structure/${symbol}?timeframe=${tf}`),
  getSMC: (symbol: string, tf = "1h") =>
    fetchAPI<any>(`/api/v1/analysis/smc/${symbol}?timeframe=${tf}`),
  getConfluence: (symbol: string, tf = "1h") =>
    fetchAPI<any>(`/api/v1/analysis/confluence/${symbol}?entry_tf=${tf}`),

  // Setups
  getSetups: (status?: string) =>
    fetchAPI<any>(`/api/v1/setups${status ? `?status=${status}` : ""}`),
  generateSetup: (symbol: string, tf = "1h") =>
    fetchAPI<any>(`/api/v1/setups/generate/${symbol}?timeframe=${tf}`),
  generateAllSetups: (tf = "1h") =>
    fetchAPI<any>(`/api/v1/setups/generate/all?timeframe=${tf}`, { method: "POST" }),
  updateSetupStatus: (id: number, status: string) =>
    fetchAPI<any>(`/api/v1/setups/${id}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    }),
  clearAllSetups: () =>
    fetchAPI<any>("/api/v1/setups/clear/all", { method: "DELETE" }),
  clearByStatus: (status: string) =>
    fetchAPI<any>(`/api/v1/setups/clear/by-status?status=${status}`, { method: "DELETE" }),
  clearOldSetups: (hours = 48) =>
    fetchAPI<any>(`/api/v1/setups/clear/old?older_than_hours=${hours}`, { method: "DELETE" }),
  deleteSetup: (id: number) =>
    fetchAPI<any>(`/api/v1/setups/${id}`, { method: "DELETE" }),
  testTelegram: () =>
    fetchAPI<any>("/api/v1/setups/test-telegram"),

  // Scanner
  getScanner: () => fetchAPI<any>("/api/v1/scanner"),
  runScanner: (symbols?: string[]) =>
    fetchAPI<any>("/api/v1/scanner/run", {
      method: "POST",
      body: JSON.stringify(symbols),
    }),

  // Risk
  calculatePosition: (data: {
    account_balance: number;
    risk_per_trade: number;
    entry_price: number;
    stop_loss: number;
    direction: string;
    take_profit?: number;
  }) =>
    fetchAPI<{ result: PositionSizeResult }>("/api/v1/risk/calculate", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getRiskSettings: () => fetchAPI<{ settings: RiskSettings }>("/api/v1/risk/settings"),
  updateRiskSettings: (data: RiskSettings) =>
    fetchAPI<{ settings: RiskSettings }>("/api/v1/risk/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // Journal
  getJournal: () => fetchAPI<any>("/api/v1/journal"),
  createJournalEntry: (data: any) =>
    fetchAPI<any>("/api/v1/journal", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  logSetupToJournal: (setupId: number, data: { result: string; notes?: string }) =>
    fetchAPI<any>(`/api/v1/journal/from-setup/${setupId}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getAnalytics: () => fetchAPI<any>("/api/v1/journal/analytics"),


  // Alerts
  getAlerts: () => fetchAPI<{ alerts: AlertRecord[] }>("/api/v1/alerts"),
  testAlert: () => fetchAPI<{ results: { channel: string; success: boolean }[] }>("/api/v1/alerts/test", { method: "POST" }),
  updateAlertSettings: (params: { telegram_chat_id?: string; email?: string; alert_enabled?: boolean }) => {
    const q = new URLSearchParams();
    if (params.telegram_chat_id != null) q.set("telegram_chat_id", params.telegram_chat_id);
    if (params.email != null) q.set("email", params.email);
    if (params.alert_enabled != null) q.set("alert_enabled", String(params.alert_enabled));
    return fetchAPI<{ settings: Record<string, unknown> }>(`/api/v1/alerts/settings?${q}`, { method: "PUT" });
  },

  // Multi-Timeframe Confirmation
  getMTFAnalysis: (symbol: string) =>
    fetchAPI<any>(`/api/v1/analysis/mtf/${symbol}`),
  getMTFBatch: (symbols: string[]) =>
    fetchAPI<any>(`/api/v1/analysis/mtf/batch/all?symbols=${symbols.join(",")}`),

  // Economic Calendar
  getCalendar: () => fetchAPI<any>("/api/v1/calendar"),
  getCalendarToday: () => fetchAPI<any>("/api/v1/calendar/today"),
  getHighImpactEvents: () => fetchAPI<any>("/api/v1/calendar/high-impact"),

  // Strategy Builder
  getStrategyBlocks: () => fetchAPI<any>("/api/v1/strategies/blocks"),
  getStrategies: () => fetchAPI<any>("/api/v1/strategies"),
  getStrategy: (id: number) => fetchAPI<any>(`/api/v1/strategies/${id}`),
  saveStrategy: (data: any) =>
    fetchAPI<any>("/api/v1/strategies", { method: "POST", body: JSON.stringify(data) }),
  deleteStrategy: (id: number) =>
    fetchAPI<any>(`/api/v1/strategies/${id}`, { method: "DELETE" }),
  evaluateStrategy: (data: any) =>
    fetchAPI<any>("/api/v1/strategies/evaluate", { method: "POST", body: JSON.stringify(data) }),

  // Auto Scheduler
  getSchedulerStatus: () => fetchAPI<any>("/scheduler/status"),
  triggerScheduler: () => fetchAPI<any>("/scheduler/trigger", { method: "POST" }),

  // Sentiment
  getSentiment: () => fetchAPI<any>("/api/v1/sentiment"),

  // Backtest
  runBacktest: (data: any) =>
    fetchAPI<any>("/api/v1/backtest/run", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Market Intelligence
  getBtcDominance: () => fetchAPI<any>("/api/v1/market-intel/btc-dominance"),
  getOrderBook: (symbol: string) => fetchAPI<any>(`/api/v1/market-intel/orderbook/${symbol}`),
  getSupportResistance: (symbol: string, tf = "1h") =>
    fetchAPI<any>(`/api/v1/market-intel/support-resistance/${symbol}?timeframe=${tf}`),
  getLiquidationLevels: (symbol: string) =>
    fetchAPI<any>(`/api/v1/market-intel/liquidation-levels/${symbol}`),
  getMarketCap: (symbol: string) => fetchAPI<any>(`/api/v1/market-intel/market-cap/${symbol}`),
  getMarketIntelOverview: (symbol: string, tf = "1h") =>
    fetchAPI<any>(`/api/v1/market-intel/overview/${symbol}?timeframe=${tf}`),

  // Auto-Trading
  getTradingConfig: () => fetchAPI<any>("/api/v1/trading/config"),
  updateTradingConfig: (data: any) =>
    fetchAPI<any>("/api/v1/trading/config", { method: "PUT", body: JSON.stringify(data) }),
  getTradingStatus: () => fetchAPI<any>("/api/v1/trading/status"),
  executeOrder: (data: any) =>
    fetchAPI<any>("/api/v1/trading/execute", { method: "POST", body: JSON.stringify(data) }),
  executeFromSetup: (setupId: number) =>
    fetchAPI<any>(`/api/v1/trading/execute/${setupId}`, { method: "POST" }),
  closePosition: (symbol: string) =>
    fetchAPI<any>(`/api/v1/trading/close/${symbol}`, { method: "POST" }),

  // Portfolio
  getPortfolioBalance: () => fetchAPI<any>("/api/v1/portfolio/balance"),
  getPortfolioPositions: () => fetchAPI<any>("/api/v1/portfolio/positions"),
  getPortfolioPnl: () => fetchAPI<any>("/api/v1/portfolio/pnl"),
  getPortfolioHistory: (days = 30) =>
    fetchAPI<any>(`/api/v1/portfolio/history?days=${days}`),
  getPortfolioStats: (days = 30) =>
    fetchAPI<any>(`/api/v1/portfolio/stats?days=${days}`),

  // Order Flow (Footprint & Smart Tape)
  getFootprint: (symbol: string, tf = "5m", limit = 10) =>
    fetchAPI<any>(`/api/v1/orderflow/footprint/${symbol}?timeframe=${tf}&limit=${limit}`),
  getWhales: (symbol: string, threshold = 50000, lookback = 3600) =>
    fetchAPI<any>(`/api/v1/orderflow/whales/${symbol}?threshold_usdt=${threshold}&lookback_seconds=${lookback}`),
  scanMultiWhales: (symbols: string[], threshold = 50000, lookback = 300) =>
    fetchAPI<any>(`/api/v1/orderflow/whales/scan/multi?symbols=${symbols.join(",")}&threshold_usdt=${threshold}&lookback_seconds=${lookback}`),
  getCachedWhales: (symbol?: string) =>
    fetchAPI<any>(`/api/v1/orderflow/whales/live/cached${symbol ? `?symbol=${symbol}` : ""}`),
};

