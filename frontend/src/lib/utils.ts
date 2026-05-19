/* Utility helpers */

export function cn(...classes: (string | undefined | false)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function formatPrice(price: number, decimals = 2): string {
  if (price >= 1000) return price.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  if (price >= 1) return price.toFixed(decimals);
  return price.toFixed(Math.max(decimals, 4));
}

export function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function timeAgo(date: string): string {
  const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export const BIAS_COLORS: Record<string, string> = {
  BULLISH: "#22c55e",
  BEARISH: "#ef4444",
  SIDEWAYS: "#eab308",
};

export const DIRECTION_COLORS: Record<string, string> = {
  BUY: "#22c55e",
  SELL: "#ef4444",
};
