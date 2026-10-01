import React, { useState, useEffect } from 'react';
import { API_URL as BASE_URL } from '@/lib/utils';
import { Plus, Trash2, Check, X, ShieldAlert, Activity } from 'lucide-react';

export const WatchlistTab = () => {
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [newSymbol, setNewSymbol] = useState('');
  const [newChain, setNewChain] = useState('ethereum');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const fetchWatchlist = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/api/whale/pro/watchlist?active_only=false`);
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

  useEffect(() => {
    fetchWatchlist();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    
    if (!newSymbol) return;

    try {
      const res = await fetch(`${BASE_URL}/api/whale/pro/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: newSymbol,
          chain_id: newChain
        })
      });

      if (res.ok) {
        setSuccess(`${newSymbol} added to watchlist`);
        setNewSymbol('');
        fetchWatchlist();
      } else {
        const data = await res.json();
        setError(data.detail || 'Failed to add asset');
      }
    } catch (e) {
      setError('Network error');
    }
  };

  const toggleActive = async (id: number, current: boolean) => {
    try {
      await fetch(`${BASE_URL}/api/whale/pro/watchlist/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !current })
      });
      fetchWatchlist();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to remove this asset?')) return;
    try {
      await fetch(`${BASE_URL}/api/whale/pro/watchlist/${id}`, {
        method: 'DELETE'
      });
      fetchWatchlist();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur-md">
        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          <ShieldAlert className="text-cyan-400 w-6 h-6" />
          Manage Watchlist
        </h2>
        <p className="text-slate-400 text-sm mb-6">
          Assets in the active watchlist are automatically scored every 15 minutes by the Whale Scoring Engine.
          Alerts will be dispatched for these assets if their scores breach the configured thresholds.
        </p>

        <form onSubmit={handleAdd} className="flex flex-col sm:flex-row gap-3 mb-8 bg-slate-800/50 p-4 rounded-lg border border-slate-700/50">
          <div className="flex-1">
            <label className="block text-xs font-semibold text-slate-400 mb-1 uppercase tracking-wider">Symbol</label>
            <input 
              type="text" 
              value={newSymbol}
              onChange={e => setNewSymbol(e.target.value.toUpperCase())}
              placeholder="e.g. BTC" 
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
              required
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-semibold text-slate-400 mb-1 uppercase tracking-wider">Chain</label>
            <select 
              value={newChain}
              onChange={e => setNewChain(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
            >
              <option value="ethereum">Ethereum</option>
              <option value="solana">Solana</option>
              <option value="bsc">BSC</option>
              <option value="hyperliquid">Hyperliquid</option>
              <option value="bitcoin">Bitcoin</option>
            </select>
          </div>
          <div className="flex items-end">
            <button 
              type="submit"
              className="w-full sm:w-auto bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-2 px-6 rounded-lg transition"
            >
              Add Asset
            </button>
          </div>
        </form>

        {error && <div className="text-red-400 bg-red-400/10 border border-red-400/20 p-3 rounded-lg mb-4 text-sm">{error}</div>}
        {success && <div className="text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 p-3 rounded-lg mb-4 text-sm">{success}</div>}

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 text-sm">
                <th className="py-3 px-4">Asset</th>
                <th className="py-3 px-4">Chain</th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-slate-500">Loading...</td>
                </tr>
              ) : watchlist.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-slate-500">Watchlist is empty.</td>
                </tr>
              ) : (
                watchlist.map((coin) => (
                  <tr key={coin.id} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition">
                    <td className="py-3 px-4 font-bold text-white">{coin.symbol}</td>
                    <td className="py-3 px-4 text-slate-300 capitalize">{coin.chain_id}</td>
                    <td className="py-3 px-4 text-center">
                      <button 
                        onClick={() => toggleActive(coin.id, coin.is_active)}
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${
                          coin.is_active 
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20' 
                            : 'bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700'
                        }`}
                      >
                        {coin.is_active ? <><Check className="w-3 h-3" /> Active</> : <><X className="w-3 h-3" /> Paused</>}
                      </button>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button 
                        onClick={() => handleDelete(coin.id)}
                        className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition"
                        title="Remove from watchlist"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
