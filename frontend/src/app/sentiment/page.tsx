"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { 
  ArrowTrendingUpIcon, 
  ArrowTrendingDownIcon, 
  ChartBarIcon, 
  ExclamationTriangleIcon,
  ArrowPathIcon,
  PresentationChartLineIcon,
} from "@heroicons/react/24/outline";

export default function SentimentPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await api.getSentiment();
      setData(res);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch sentiment:", err);
      setError("Failed to load sentiment data. Please try again later.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000 * 5); // Refresh every 5 mins
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        </div>
      </MainLayout>
    );
  }

  const fng = data?.fear_and_greed || { value: 50, classification: "Neutral" };
  const getFngColor = (val: number) => {
    if (val < 25) return "#ef4444"; // Extreme Fear
    if (val < 45) return "#f97316"; // Fear
    if (val < 55) return "#eab308"; // Neutral
    if (val < 75) return "#84cc16"; // Greed
    return "#22c55e"; // Extreme Greed
  };

  return (
    <MainLayout>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Market Sentiment</h1>
          <p className="text-muted-foreground">Macro analysis, Funding Rates, and Fear & Greed index.</p>
        </div>
        <button 
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary hover:bg-secondary/80 transition-colors disabled:opacity-50"
        >
          <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded-lg mb-6 flex items-center gap-2">
          <ExclamationTriangleIcon className="w-5 h-5" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
        {/* Fear & Greed Gauge Card */}
        <div className="bg-card border border-border rounded-xl p-8 flex flex-col items-center justify-center relative overflow-hidden group">
          <div className="absolute top-4 left-6 flex items-center gap-2 text-muted-foreground text-sm font-medium">
             <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6a7.5 7.5 0 1 0 7.5 7.5h-7.5V6Z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5H21A7.5 7.5 0 0 0 13.5 3v7.5Z" />
            </svg>
            Fear & Greed Index
          </div>
          
          <div className="relative mt-8 mb-6 h-48 w-48">
            {/* SVG Gauge */}
            <svg viewBox="0 0 100 60" className="w-full h-full">
              <path
                d="M 10 50 A 40 40 0 0 1 90 50"
                fill="none"
                stroke="currentColor"
                strokeWidth="8"
                className="text-muted/20"
                strokeLinecap="round"
              />
              <path
                d="M 10 50 A 40 40 0 0 1 90 50"
                fill="none"
                stroke={getFngColor(fng.value)}
                strokeWidth="8"
                strokeDasharray="126"
                strokeDashoffset={126 - (fng.value / 100) * 126}
                strokeLinecap="round"
                className="transition-all duration-1000 ease-out"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center pt-8">
              <span className="text-5xl font-black transition-colors duration-500" style={{ color: getFngColor(fng.value) }}>
                {fng.value}
              </span>
              <span className="text-sm font-bold uppercase tracking-widest mt-1 opacity-80" style={{ color: getFngColor(fng.value) }}>
                {fng.classification}
              </span>
            </div>
          </div>
          
          <div className="w-full flex justify-between text-xs font-medium text-muted-foreground mt-2 border-t border-border pt-4">
            <div className="flex flex-col items-start italic">
              <span>Yesterday</span>
              <span className="text-foreground not-italic font-bold">{fng.previous_value} ({fng.previous_classification})</span>
            </div>
            <div className="text-right flex flex-col items-end italic">
              <span>Last Update</span>
              <span className="text-foreground not-italic font-bold">
                {new Date(fng.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
        </div>

        {/* Global Stats or Micro-indicators */}
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-card border border-border rounded-xl p-6 flex flex-col justify-between overflow-hidden relative">
            <div>
              <p className="text-sm font-medium text-muted-foreground uppercase tracking-widest mb-1">Market Bias</p>
              <h3 className="text-2xl font-bold flex items-center gap-2">
                {fng.value > 60 ? (
                  <>
                    <ArrowTrendingUpIcon className="text-green-500 w-6 h-6" /> Bullish Expectation
                  </>
                ) : fng.value < 40 ? (
                  <>
                    <ArrowTrendingDownIcon className="text-red-500 w-6 h-6" /> Bearish Expectation
                  </>
                ) : (
                  <>
                    <PresentationChartLineIcon className="text-yellow-500 w-6 h-6" /> Neutral / Ranging
                  </>
                )}
              </h3>
            </div>
            <p className="text-xs text-muted-foreground mt-4 leading-relaxed">
              Based on the Fear & Greed Index and current market dynamics. Extremely high greed often precedes a correction, while extreme fear often presents buying opportunities.
            </p>
          </div>

          <div className="bg-card border border-border rounded-xl p-6 flex flex-col justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground uppercase tracking-widest mb-1">Funding Strategy</p>
              <h3 className="text-xl font-bold">Watch Perpetual Swaps</h3>
            </div>
            <div className="space-y-3 mt-4">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground italic">Positive Funding</span>
                <span className="text-red-400 font-bold">Longs pay Shorts</span>
              </div>
              <div className="flex justify-between text-xs border-t border-border/50 pt-2">
                <span className="text-muted-foreground italic">Negative Funding</span>
                <span className="text-green-400 font-bold">Shorts pay Longs</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Funding Rates & OI Table */}
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
        <ChartBarIcon className="w-5 h-5 text-primary" />
        Market Metrics (Binance Perpetual)
      </h2>
      <div className="bg-card border border-border rounded-xl overflow-hidden mb-12">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-muted/30 border-b border-border">
                <th className="px-6 py-4 text-sm font-bold uppercase tracking-wider">Asset</th>
                <th className="px-6 py-4 text-sm font-bold uppercase tracking-wider">Funding Rate</th>
                <th className="px-6 py-4 text-sm font-bold uppercase tracking-wider">Open Interest</th>
                <th className="px-6 py-4 text-sm font-bold uppercase tracking-wider">OI (Coin)</th>
                <th className="px-6 py-4 text-sm font-bold uppercase tracking-wider">Trend</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {data?.market_metrics?.map((metric: any) => (
                <tr key={metric.symbol} className="hover:bg-muted/20 transition-colors">
                  <td className="px-6 py-4 font-bold text-white uppercase">
                    {metric.symbol}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`font-mono font-bold ${metric.funding_rate > 0 ? 'text-red-400' : metric.funding_rate < 0 ? 'text-green-400' : 'text-foreground'}`}>
                      {(metric.funding_rate * 100).toFixed(4)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-muted-foreground">
                    {new Intl.NumberFormat().format(metric.open_interest)} <span className="text-[10px] opacity-70">CONT</span>
                  </td>
                  <td className="px-6 py-4 font-mono text-muted-foreground">
                    {new Intl.NumberFormat().format(metric.open_interest_coin)}
                  </td>
                  <td className="px-6 py-4">
                    {metric.funding_rate > 0.01 ? (
                      <span className="px-2 py-1 bg-red-500/10 text-red-500 text-[10px] font-black rounded border border-red-500/20 uppercase">Overheated</span>
                    ) : metric.funding_rate < -0.01 ? (
                      <span className="px-2 py-1 bg-green-500/10 text-green-500 text-[10px] font-black rounded border border-green-500/20 uppercase">Short Squeeze?</span>
                    ) : (
                      <span className="px-2 py-1 bg-muted text-muted-foreground text-[10px] font-black rounded border border-border uppercase">Normal</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </MainLayout>
  );
}
