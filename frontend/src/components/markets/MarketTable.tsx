'use client';

import React, { useEffect, useState, useRef } from 'react';
import SparklineChart from './SparklineChart';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL 
  ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1` 
  : 'http://127.0.0.1:8000/api/v1';

interface CoinData {
  symbol: string;
  market_cap_rank: number;
  name: string;
  image: string;
  market_cap: number;
  price: number;
  change_24h: number;
  volume_24h: number;
  flash?: 'up' | 'down' | null;
}

interface MarketTableProps {
  onStatusChange?: (status: 'LIVE' | 'DEGRADED') => void;
}

export default function MarketTable({ onStatusChange }: MarketTableProps) {
  const [coins, setCoins] = useState<CoinData[]>([]);
  const [sparklines, setSparklines] = useState<Record<string, number[]>>({});
  const [loading, setLoading] = useState(true);
  
  // Use a ref to hold the current coins array for the SSE event listener
  // to avoid stale closures.
  const coinsRef = useRef<CoinData[]>([]);
  
  // Formatters
  const formatPrice = (val: number) => {
    if (val === 0) return '---';
    if (val < 1) return val.toFixed(6);
    if (val < 10) return val.toFixed(4);
    return val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };
  
  const formatCompact = (val: number) => {
    if (!val) return '---';
    return new Intl.NumberFormat('en-US', {
      notation: 'compact',
      compactDisplay: 'short',
      maximumFractionDigits: 2
    }).format(val);
  };

  // 1. Fetch initial snapshot
  useEffect(() => {
    let mounted = true;
    
    async function fetchSnapshot() {
      try {
        const res = await fetch(`${API_BASE_URL}/markets/snapshot?limit=100`);
        const json = await res.json();
        if (mounted && json.status === 'success') {
          setCoins(json.data);
          coinsRef.current = json.data;
          setLoading(false);
          
          // Trigger sparkline fetch after snapshot
          fetchSparklines(json.data.map((c: CoinData) => c.symbol));
        }
      } catch (err) {
        console.error("Failed to fetch market snapshot:", err);
        setLoading(false);
      }
    }
    
    fetchSnapshot();
    
    return () => { mounted = false; };
  }, []);
  
  // 2. Fetch Sparklines
  const fetchSparklines = async (symbols: string[]) => {
    try {
      const chunked = symbols.slice(0, 100); // safety
      const symStr = chunked.join(',');
      const res = await fetch(`${API_BASE_URL}/markets/sparklines?symbols=${symStr}`);
      const json = await res.json();
      if (json.status === 'success') {
        setSparklines(json.data);
      }
    } catch (err) {
      console.error("Failed to fetch sparklines:", err);
    }
  };

  // 3. Connect SSE for live updates
  useEffect(() => {
    if (loading) return;
    
    const eventSource = new EventSource(`${API_BASE_URL}/markets/stream`);
    
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (!payload) return;
        
        if (payload.status && onStatusChange) {
          onStatusChange(payload.status);
        }
        
        const updates = payload.updates;
        if (!updates || updates.length === 0) return;
        
        // Update coins state with flashes
        setCoins(prevCoins => {
          const newCoins = [...prevCoins];
          let changed = false;
          
          for (const update of updates) {
            const idx = newCoins.findIndex(c => c.symbol === update.symbol);
            if (idx !== -1) {
              const oldCoin = newCoins[idx];
              // Only trigger flash if price actually changed
              let flash: 'up' | 'down' | null = null;
              if (update.price > oldCoin.price) flash = 'up';
              else if (update.price < oldCoin.price) flash = 'down';
              
              if (flash) {
                newCoins[idx] = { ...oldCoin, ...update, flash };
                changed = true;
              }
            }
          }
          
          if (changed) {
            // Clear flashes after 500ms
            setTimeout(() => {
              setCoins(current => current.map(c => c.flash ? { ...c, flash: null } : c));
            }, 500);
            return newCoins;
          }
          
          return prevCoins;
        });
        
      } catch (e) {
        console.error("SSE parse error", e);
      }
    };
    
    eventSource.onerror = (err) => {
      console.error("SSE connection error:", err);
    };
    
    return () => {
      eventSource.close();
    };
  }, [loading]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500"></div>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-white/5 bg-gray-900/50 backdrop-blur-xl">
      <table className="w-full text-sm text-left">
        <thead className="text-xs text-gray-400 uppercase bg-black/40 border-b border-white/5">
          <tr>
            <th className="px-6 py-4 font-medium">#</th>
            <th className="px-6 py-4 font-medium">Asset</th>
            <th className="px-6 py-4 font-medium text-right">Price</th>
            <th className="px-6 py-4 font-medium text-right">24h Change</th>
            <th className="px-6 py-4 font-medium text-right">24h Volume</th>
            <th className="px-6 py-4 font-medium text-right relative group/tooltip">
              <span className="border-b border-dashed border-gray-500 cursor-help">Market Cap</span>
              <div className="absolute bottom-full right-0 mb-2 w-64 bg-gray-900 border border-gray-700 text-gray-300 text-[10px] sm:text-xs p-2 rounded shadow-xl opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all z-10 pointer-events-none normal-case font-normal text-left">
                Diukur dari rata-rata volume tertimbang lintas-bursa (CoinGecko). Harga dapat memiliki spread dengan ticker live Binance di kolom Price.
              </div>
            </th>
            <th className="px-6 py-4 font-medium text-center">Last 7 Days</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {coins.map((coin) => {
            const isPositive = coin.change_24h >= 0;
            const flashClass = coin.flash === 'up' 
              ? 'bg-emerald-500/20 text-emerald-400 transition-none' 
              : coin.flash === 'down' 
                ? 'bg-rose-500/20 text-rose-400 transition-none' 
                : 'transition-colors duration-500';

            return (
              <tr key={coin.symbol} className="hover:bg-white/[0.02] transition-colors group">
                <td className="px-6 py-4 text-gray-500 font-medium">
                  {coin.market_cap_rank || '-'}
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    {coin.image ? (
                      <img src={coin.image} alt={coin.name} className="w-8 h-8 rounded-full" />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center text-xs font-bold text-gray-400">
                        {coin.symbol.replace('USDT', '').slice(0, 2)}
                      </div>
                    )}
                    <div>
                      <div className="font-bold text-white group-hover:text-emerald-400 transition-colors">
                        {coin.name}
                      </div>
                      <div className="text-xs text-gray-500 font-medium">
                        {coin.symbol.replace('USDT', '')}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 text-right">
                  <div className={`font-mono font-medium py-1 px-2 rounded -mr-2 inline-block ${flashClass}`}>
                    ${formatPrice(coin.price)}
                  </div>
                </td>
                <td className="px-6 py-4 text-right">
                  <div className={`font-medium ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {isPositive ? '+' : ''}{coin.change_24h?.toFixed(2)}%
                  </div>
                </td>
                <td className="px-6 py-4 text-right font-mono text-gray-400">
                  ${formatCompact(coin.volume_24h)}
                </td>
                <td className="px-6 py-4 text-right font-mono text-gray-400">
                  ${formatCompact(coin.market_cap)}
                </td>
                <td className="px-6 py-4 flex justify-center">
                  <div className="w-32 h-10 opacity-70 group-hover:opacity-100 transition-opacity">
                    {sparklines[coin.symbol] ? (
                      <SparklineChart 
                        data={sparklines[coin.symbol]} 
                        isPositive={isPositive}
                      />
                    ) : (
                      <div className="w-full h-full bg-gray-800/30 animate-pulse rounded" />
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
