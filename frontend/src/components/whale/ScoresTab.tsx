import React, { useState, useEffect } from 'react';
import { API_URL as BASE_URL } from '@/lib/utils';
import { Activity, Search, RefreshCw, AlertTriangle, CheckCircle, TrendingUp, TrendingDown, Info } from 'lucide-react';

export const ScoresTab = () => {
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCoin, setSelectedCoin] = useState<string | null>(null);
  const [scoreDetails, setScoreDetails] = useState<any>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  const fetchWatchlist = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/api/whale/pro/watchlist?active_only=true`);
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchScore = async (symbol: string, chainId: string) => {
    setLoadingDetails(true);
    setSelectedCoin(symbol);
    try {
      const res = await fetch(`${BASE_URL}/api/whale/pro/scores/${symbol}?chain_id=${chainId}`);
      if (res.ok) {
        const data = await res.json();
        setScoreDetails(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDetails(false);
    }
  };

  useEffect(() => {
    fetchWatchlist();
  }, []);

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A': return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20';
      case 'B': return 'text-green-400 bg-green-400/10 border-green-400/20';
      case 'C': return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20';
      case 'D': return 'text-orange-400 bg-orange-400/10 border-orange-400/20';
      case 'F': return 'text-red-400 bg-red-400/10 border-red-400/20';
      default: return 'text-slate-400 bg-slate-400/10 border-slate-400/20';
    }
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 w-full h-full">
      {/* Left panel: Watchlist Overview */}
      <div className="w-full lg:w-1/3 flex flex-col gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 backdrop-blur-md">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-cyan-400" /> Tracked Assets
            </h3>
            <button onClick={fetchWatchlist} className="text-slate-400 hover:text-white transition">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          
          <div className="space-y-3">
            {loading && watchlist.length === 0 ? (
              <div className="text-center py-8 text-slate-500 animate-pulse">Loading tracked assets...</div>
            ) : watchlist.length === 0 ? (
              <div className="text-center py-8 text-slate-500">No assets in watchlist.</div>
            ) : (
              watchlist.map((coin) => (
                <div 
                  key={coin.id} 
                  onClick={() => fetchScore(coin.symbol, coin.chain_id)}
                  className={`p-3 rounded-lg border transition cursor-pointer flex justify-between items-center ${
                    selectedCoin === coin.symbol 
                      ? 'bg-cyan-900/30 border-cyan-500/50' 
                      : 'bg-slate-800/50 border-slate-700/50 hover:border-slate-500 hover:bg-slate-800'
                  }`}
                >
                  <div>
                    <div className="font-bold text-white">{coin.symbol}</div>
                    <div className="text-xs text-slate-400">{coin.chain_id}</div>
                  </div>
                  {coin.latest_score ? (
                    <div className="flex flex-col items-end">
                      <div className={`px-2 py-0.5 rounded text-xs font-bold border ${getGradeColor(coin.latest_score.grade)}`}>
                        Grade {coin.latest_score.grade}
                      </div>
                      <div className="text-lg font-bold mt-1 text-slate-200">
                        {coin.latest_score.score.toFixed(1)}
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 italic">No score yet</div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Right panel: Score Breakdown */}
      <div className="w-full lg:w-2/3 flex flex-col gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur-md min-h-[400px]">
          {loadingDetails ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400">
              <RefreshCw className="w-8 h-8 animate-spin mb-4 text-cyan-500" />
              <p>Analyzing on-chain data for {selectedCoin}...</p>
            </div>
          ) : !scoreDetails ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-500">
              <Activity className="w-12 h-12 mb-4 opacity-50" />
              <p>Select an asset from the list to view its Pro Score breakdown.</p>
            </div>
          ) : (
            <div className="space-y-6 animate-in fade-in">
              <div className="flex justify-between items-start border-b border-slate-800 pb-4">
                <div>
                  <h2 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
                    {scoreDetails.symbol} Score Analysis
                    {scoreDetails.is_stale && (
                      <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs border border-yellow-500/30 rounded-full flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> Stale (Price Moved)
                      </span>
                    )}
                  </h2>
                  <p className="text-slate-400 text-sm">
                    {scoreDetails.chain_id} • Computed {new Date(scoreDetails.scored_at).toLocaleString()} {scoreDetails.cached ? '(Cached)' : ''}
                  </p>
                </div>
                <div className="text-right">
                  <div className={`inline-block px-3 py-1 rounded text-lg font-bold border mb-1 ${getGradeColor(scoreDetails.grade)}`}>
                    Grade {scoreDetails.grade}
                  </div>
                  <div className="text-3xl font-extrabold text-white">
                    {scoreDetails.score.toFixed(1)}<span className="text-sm text-slate-500 font-normal">/100</span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">{scoreDetails.grade_label}</div>
                </div>
              </div>

              {scoreDetails.flags && scoreDetails.flags.length > 0 && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                  <div className="text-red-400 font-semibold flex items-center gap-2 mb-2 text-sm">
                    <AlertTriangle className="w-4 h-4" /> Risk Flags Detected
                  </div>
                  <ul className="list-disc pl-5 text-sm text-red-200/80 space-y-1">
                    {scoreDetails.flags.map((flag: string, i: number) => (
                      <li key={i}>{flag.replace(/_/g, ' ')}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Signal Breakdown</h4>
                <div className="space-y-3">
                  {scoreDetails.breakdown.map((signal: any, i: number) => (
                    <div key={i} className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <div className="font-semibold text-white flex items-center gap-2">
                          {signal.contribution > 0 ? (
                            <TrendingUp className="w-4 h-4 text-emerald-400" />
                          ) : signal.contribution < 0 ? (
                            <TrendingDown className="w-4 h-4 text-red-400" />
                          ) : (
                            <Info className="w-4 h-4 text-slate-400" />
                          )}
                          {signal.signal.replace(/_/g, ' ').replace(/\b\w/g, (l:string) => l.toUpperCase())}
                        </div>
                        <div className={`font-bold ${signal.contribution > 0 ? 'text-emerald-400' : signal.contribution < 0 ? 'text-red-400' : 'text-slate-400'}`}>
                          {signal.contribution > 0 ? '+' : ''}{signal.contribution.toFixed(1)} pts
                        </div>
                      </div>
                      <p className="text-sm text-slate-300">{signal.detail}</p>
                      
                      {signal.flags && signal.flags.length > 0 && (
                        <div className="mt-2 flex gap-2 flex-wrap">
                          {signal.flags.map((flag: string, j: number) => (
                            <span key={j} className="px-2 py-0.5 bg-red-900/30 text-red-400 text-xs rounded border border-red-800/50">
                              {flag.replace(/_/g, ' ')}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              
              <div className="text-xs text-slate-500 border-t border-slate-800 pt-4 mt-4">
                {scoreDetails.disclaimer}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
