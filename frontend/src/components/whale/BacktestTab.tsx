import React, { useState } from 'react';
import { API_URL as BASE_URL } from '@/lib/utils';
import { Play, TrendingUp, TrendingDown, Target, Info } from 'lucide-react';

export const BacktestTab = () => {
  const [symbol, setSymbol] = useState('HYPE');
  const [chainId, setChainId] = useState('hyperliquid');
  const [forwardDays, setForwardDays] = useState(7);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const runBacktest = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const res = await fetch(`${BASE_URL}/api/whale/pro/backtest/${symbol}?chain_id=${chainId}&forward_days=${forwardDays}`);
      const data = await res.json();
      
      if (!res.ok || data.total_samples === 0) {
        setError(data.note || 'Not enough historical data for backtest. Need at least 5 samples.');
      } else {
        setResult(data);
      }
    } catch (e) {
      setError('Network error running backtest.');
    } finally {
      setLoading(false);
    }
  };

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A': return 'text-emerald-400';
      case 'B': return 'text-green-400';
      case 'C': return 'text-yellow-400';
      case 'D': return 'text-orange-400';
      case 'F': return 'text-red-400';
      default: return 'text-slate-400';
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6">
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur-md">
        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          <Target className="text-cyan-400 w-6 h-6" />
          Whale Score Backtesting Engine
        </h2>
        <p className="text-slate-400 text-sm mb-6 max-w-3xl">
          Test the predictive power of historical whale scores against actual forward price returns. 
          This tool calculates the correlation between the score on Day T and the price change over the subsequent N days.
        </p>

        <form onSubmit={runBacktest} className="flex flex-col sm:flex-row gap-4 mb-8 bg-slate-800/30 p-5 rounded-lg border border-slate-700/50">
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1">ASSET SYMBOL</label>
            <input 
              type="text" 
              value={symbol}
              onChange={e => setSymbol(e.target.value.toUpperCase())}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 w-32"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1">CHAIN</label>
            <select 
              value={chainId}
              onChange={e => setChainId(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500"
            >
              <option value="hyperliquid">Hyperliquid</option>
              <option value="ethereum">Ethereum</option>
              <option value="solana">Solana</option>
              <option value="bitcoin">Bitcoin</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1">FORWARD DAYS</label>
            <select 
              value={forwardDays}
              onChange={e => setForwardDays(Number(e.target.value))}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500"
            >
              <option value={1}>1 Day</option>
              <option value={3}>3 Days</option>
              <option value={7}>7 Days</option>
              <option value={14}>14 Days</option>
            </select>
          </div>
          <div className="flex items-end flex-1 justify-end">
            <button 
              type="submit"
              disabled={loading}
              className="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-bold py-2 px-6 rounded-lg transition flex items-center gap-2"
            >
              {loading ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Play className="w-4 h-4" />}
              Run Backtest
            </button>
          </div>
        </form>

        {error && <div className="text-red-400 bg-red-400/10 border border-red-400/20 p-4 rounded-lg mb-4">{error}</div>}

        {result && (
          <div className="space-y-6 animate-in fade-in">
            {/* Overview Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                <div className="text-sm text-slate-400 mb-1">Total Samples</div>
                <div className="text-3xl font-bold text-white">{result.total_samples}</div>
                <div className="text-xs text-slate-500 mt-1">
                  {new Date(result.period_start).toLocaleDateString()} to {new Date(result.period_end).toLocaleDateString()}
                </div>
              </div>
              <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                <div className="text-sm text-slate-400 mb-1">Correlation (Pearson r)</div>
                <div className={`text-3xl font-bold ${result.overall_correlation > 0.3 ? 'text-emerald-400' : result.overall_correlation < -0.3 ? 'text-red-400' : 'text-slate-200'}`}>
                  {result.overall_correlation > 0 ? '+' : ''}{result.overall_correlation.toFixed(3)}
                </div>
                <div className="text-xs text-slate-500 mt-1">Score vs {result.forward_days}d Forward Return</div>
              </div>
              <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                <div className="text-sm text-slate-400 mb-1">Analysis Note</div>
                <div className="text-sm text-slate-300 leading-snug flex items-start gap-2">
                  <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                  {result.note}
                </div>
              </div>
            </div>

            {/* Grade Performance Table */}
            <div>
              <h3 className="text-lg font-bold text-white mb-3">Performance by Grade</h3>
              <div className="overflow-x-auto rounded-lg border border-slate-700">
                <table className="w-full text-left border-collapse bg-slate-900/50">
                  <thead>
                    <tr className="border-b border-slate-700 text-slate-400 text-sm bg-slate-800/80">
                      <th className="py-3 px-4 font-semibold">Grade</th>
                      <th className="py-3 px-4 font-semibold">Count</th>
                      <th className="py-3 px-4 font-semibold">Win Rate</th>
                      <th className="py-3 px-4 font-semibold">Avg Return</th>
                      <th className="py-3 px-4 font-semibold">Median Return</th>
                      <th className="py-3 px-4 font-semibold text-right">Best / Worst</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.grade_stats.map((stat: any) => (
                      <tr key={stat.grade} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                        <td className={`py-3 px-4 font-bold text-lg ${getGradeColor(stat.grade)}`}>{stat.grade}</td>
                        <td className="py-3 px-4 text-slate-300">{stat.count}</td>
                        <td className="py-3 px-4">
                          <span className={`font-semibold ${stat.win_rate_pct >= 50 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {stat.win_rate_pct.toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`flex items-center gap-1 font-semibold ${stat.avg_forward_return_pct > 0 ? 'text-emerald-400' : stat.avg_forward_return_pct < 0 ? 'text-red-400' : 'text-slate-400'}`}>
                            {stat.avg_forward_return_pct > 0 ? <TrendingUp className="w-3 h-3" /> : stat.avg_forward_return_pct < 0 ? <TrendingDown className="w-3 h-3" /> : ''}
                            {stat.avg_forward_return_pct > 0 ? '+' : ''}{stat.avg_forward_return_pct.toFixed(2)}%
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-300">
                          {stat.median_return_pct > 0 ? '+' : ''}{stat.median_return_pct.toFixed(2)}%
                        </td>
                        <td className="py-3 px-4 text-right text-xs">
                          <span className="text-emerald-400">+{stat.best_pct.toFixed(1)}%</span>
                          <span className="text-slate-500 mx-1">/</span>
                          <span className="text-red-400">{stat.worst_pct.toFixed(1)}%</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
