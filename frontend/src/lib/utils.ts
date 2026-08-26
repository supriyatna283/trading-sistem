/* Utility helpers */

export function cn(...classes: (string | undefined | false)[]): string {
  return classes.filter(Boolean).join(" ");
}

/**
 * Format price for display:
 * - val > 10  → locale string with 2 decimal places
 * - val ≤ 10  → 5 decimal places (altcoin/satoshi range)
 * Overloads the original to match chart component expectations.
 */
export function formatPrice(val: number | null | undefined, decimals = 2): string {
  if (val == null || (typeof val === 'number' && isNaN(val))) return "–";
  const n = val as number;
  if (n > 10)
    return n.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  return n.toFixed(Math.max(decimals, 4));
}

export function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function timeAgo(date: string | null | undefined): string {
  if (!date) return "";
  const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

/**
 * Debounce: returns a debounced version of fn.
 */
export function debounce<T extends (...args: any[]) => void>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Clamp a number between min and max.
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * API_URL: single source of truth across the app.
 */
export const API_URL = typeof window !== "undefined"
  ? `http://${window.location.hostname}:8000`
  : (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000");

export const BIAS_COLORS: Record<string, string> = {
  BULLISH: "#22c55e",
  BEARISH: "#ef4444",
  SIDEWAYS: "#eab308",
};

export const DIRECTION_COLORS: Record<string, string> = {
  BUY: "#22c55e",
  SELL: "#ef4444",
};
