/* =============================================
   Trading Intelligence Platform — Types
   ============================================= */

export interface Candle {
  symbol: string;
  timeframe: string;
  open_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SwingPoint {
  index: number;
  price: number;
  type: "HIGH" | "LOW";
  time?: string;
}

export interface StructureLabel {
  index: number;
  label: "HH" | "HL" | "LH" | "LL" | "BOS" | "CHOCH" | "MSS";
  price: number;
  time?: string;
}

export interface MarketBias {
  symbol: string;
  timeframe: string;
  bias: "BULLISH" | "BEARISH" | "SIDEWAYS";
  structure_labels: StructureLabel[];
  swing_points: SwingPoint[];
}

export interface OrderBlock {
  type: "BULLISH" | "BEARISH";
  high: number;
  low: number;
  index: number;
  time?: string;
  tested: boolean;
}

export interface FairValueGap {
  type: "BULLISH" | "BEARISH";
  high: number;
  low: number;
  index: number;
  time?: string;
}

export interface LiquidityLevel {
  price: number;
  type: "EQUAL_HIGH" | "EQUAL_LOW" | "STOP_CLUSTER";
  strength: number;
  swept: boolean;
}

export interface SmartMoneyAnalysis {
  symbol: string;
  timeframe: string;
  order_blocks: OrderBlock[];
  fvgs: FairValueGap[];
  liquidity_levels: LiquidityLevel[];
  premium_discount_mid?: number;
}

export interface TradeSetup {
  id?: number;
  symbol: string;
  direction: "BUY" | "SELL";
  entry_low: number;
  entry_high: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2?: number;
  take_profit_3?: number;
  risk_reward: number;
  setup_type: string;
  confluence_score: number;
  status: "ACTIVE" | "TRIGGERED" | "INVALIDATED" | "CLOSED";
  timeframe: string;
  explanation?: string;
  created_at?: string;
}

export interface ConfluenceResult {
  symbol: string;
  total_score: number;
  max_score: number;
  details: Record<string, any>;
  recommendation: string;
  setups: TradeSetup[];
}

export interface RiskSettings {
  account_balance: number;
  risk_per_trade: number;
  max_daily_risk: number;
  max_concurrent_trades: number;
}

export interface PositionSizeResult {
  position_size: number;
  risk_amount: number;
  stop_distance: number;
  stop_distance_pct: number;
  risk_reward?: number;
}

export interface JournalEntry {
  id?: number;
  setup_id?: number;
  symbol: string;
  direction: "BUY" | "SELL";
  entry_price: number;
  exit_price?: number;
  stop_loss: number;
  take_profit: number;
  position_size: number;
  pnl?: number;
  r_multiple?: number;
  result?: "WIN" | "LOSS" | "BREAKEVEN";
  notes?: string;
  entered_at?: string;
  closed_at?: string;
}

export interface JournalAnalytics {
  total_trades: number;
  wins: number;
  losses: number;
  breakeven: number;
  win_rate: number;
  profit_factor: number;
  avg_r_multiple: number;
  total_pnl: number;
  max_drawdown: number;
  expectancy: number;
  best_trade: number;
  worst_trade: number;
  avg_win: number;
  avg_loss: number;
}

export interface ScannerResult {
  symbol: string;
  trend: string;
  liquidity_status: string;
  setup_status: string;
  confluence_score: number;
  setup?: TradeSetup;
}

export interface Symbol {
  symbol: string;
  name: string;
  category: string;
}
