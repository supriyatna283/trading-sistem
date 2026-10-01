'use client';
import React, { useState, useEffect, useMemo } from 'react';
import { API_URL as BASE_URL } from '@/lib/utils';
import { useWhaleSocket } from '@/lib/hooks/useWhaleSocket';
import { useDebounce } from '@/lib/hooks/useDebounce';
import { useLocalStorage } from '@/lib/hooks/useLocalStorage';
import { useWhaleAudio } from '@/lib/hooks/useWhaleAudio';
import { WhaleHeader } from '@/components/whale/WhaleHeader';
import { WhaleStatsCards } from '@/components/whale/WhaleStatsCards';
import { WhaleFilterBar } from '@/components/whale/WhaleFilterBar';
import { LiveStreamTable } from '@/components/whale/LiveStreamTable';
import { VisualizerTab } from '@/components/whale/VisualizerTab';
import { TrendsTab } from '@/components/whale/TrendsTab';
import { EntitiesTab } from '@/components/whale/EntitiesTab';
import { ScoresTab } from '@/components/whale/ScoresTab';
import { WatchlistTab } from '@/components/whale/WatchlistTab';
import { BacktestTab } from '@/components/whale/BacktestTab';
import { TransactionModal } from '@/components/whale/TransactionModal';
import { WalletModal } from '@/components/whale/WalletModal';
import MainLayout from "@/components/layout/MainLayout";

export default function App() {
  const [activeTab, setActiveTab] = useLocalStorage('whale-activeTab', 'live');
  const [selectedChain, setSelectedChain] = useLocalStorage('whale-selectedChain', 'ALL');
  const [minUsdFilter, setMinUsdFilter] = useLocalStorage('whale-minUsd', 10000);
  const [searchQuery, setSearchQuery] = useState('');
  const [actionFilter, setActionFilter] = useLocalStorage('whale-action', 'ALL');
  const [tokenFilter, setTokenFilter] = useLocalStorage('whale-token', 'ALL');
  const [timeframe, setTimeframe] = useLocalStorage('whale-timeframe', '24H');
  const [sortBy, setSortBy] = useLocalStorage('whale-sort', 'TIME_DESC');
  const [smartMoneyOnly, setSmartMoneyOnly] = useLocalStorage('whale-smartMoney', false);
  
  const [isLive, setIsLive] = useState(true);
  const [soundEnabled, setSoundEnabled] = useLocalStorage('whale-sound', false);
  
  const [inspectTx, setInspectTx] = useState<any | null>(null);
  const [inspectWallet, setInspectWallet] = useState<any | null>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);

  const debouncedSearchQuery = useDebounce(searchQuery, 300);
  const { playMegaAlert } = useWhaleAudio(soundEnabled);

  const API_BASE = BASE_URL;
  const WS_URL = API_BASE.replace(/^http/, 'ws') + '/ws/whale';
  const API_URL = API_BASE + '/api';

  const { transactions: backendTxs, isConnected, setInitialTransactions, appendHistoricalTransactions } = useWhaleSocket(WS_URL);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [currentOffset, setCurrentOffset] = useState(50);

  const loadMoreHistory = async () => {
    setIsLoadingMore(true);
    try {
      const params = new URLSearchParams({ limit: '50', offset: String(currentOffset) });
      if (selectedChain !== 'ALL') params.append('chain', selectedChain);
      const res = await fetch(`${API_URL}/whale/live?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        appendHistoricalTransactions(data);
        setCurrentOffset(prev => prev + 50);
      }
    } catch (error) {
      console.error('Failed to load more history', error);
    } finally {
      setIsLoadingMore(false);
    }
  };

  useEffect(() => {
    const fetchLive = async () => {
      try {
        const params = new URLSearchParams({ limit: '50' });
        if (selectedChain !== 'ALL') params.append('chain', selectedChain);
        const res = await fetch(`${API_URL}/whale/live?${params.toString()}`);
        if (res.ok) {
          const data = await res.json();
          setInitialTransactions(data);
        }
      } catch (error) {
        console.error('Failed to fetch live whales', error);
      }
    };
    
    const fetchDashboard = async () => {
      try {
        const res = await fetch(`${API_URL}/whale/dashboard`);
        if (res.ok) {
          const data = await res.json();
          setDashboardData(data);
        }
      } catch (error) {
        console.error('Failed to fetch dashboard', error);
      }
    };
    
    fetchLive();
    fetchDashboard();
    
    const interval = setInterval(fetchDashboard, 30000);
    return () => clearInterval(interval);
  }, [selectedChain, setInitialTransactions, API_URL]);

  const transactions = useMemo(() => {
    return backendTxs.map((tx: any) => {
      const impact = tx.usd_value > 10000000 ? 'MEGA' : tx.usd_value > 2000000 ? 'HIGH' : 'MEDIUM';
      
      // Play sound alert for new MEGA transactions if enabled
      if (tx.isNew && impact === 'MEGA') {
        playMegaAlert();
      }

      const blockTimeStr = tx.block_time.endsWith('Z') ? tx.block_time : `${tx.block_time}Z`;

      return {
        id: String(tx.id),
        time: new Date(blockTimeStr).toLocaleTimeString(),
        timestamp: new Date(blockTimeStr).getTime(),
        chain: tx.chain_id.toUpperCase(),
        action: tx.direction.toUpperCase(),
        usdValue: tx.usd_value,
        amount: tx.amount.toLocaleString(undefined, { maximumFractionDigits: 2 }),
        token: tx.token_symbol,
        from: tx.from_wallet?.address || 'Unknown',
        fromEntity: tx.from_wallet?.label || 'Unknown Wallet',
        fromEntityType: tx.from_wallet?.entity_type || 'unlabeled',
        to: tx.to_wallet?.address || 'Unknown',
        toEntity: tx.to_wallet?.label || 'Unknown Wallet',
        toEntityType: tx.to_wallet?.entity_type || 'unlabeled',
        hash: tx.tx_hash,
        gasFee: '0.012 ETH', // Mocking gas fee for UI
        impact: impact,
        isNew: tx.isNew || false,
        smartScore: tx.from_wallet?.entity_type === 'smart_money' || tx.to_wallet?.entity_type === 'smart_money' 
          ? Math.floor(Math.random() * (99 - 85) + 85) // Random high score if tagged as smart money
          : Math.floor(Math.random() * 80)
      };
    });
  }, [backendTxs, playMegaAlert]);

  const filteredTransactions = useMemo(() => {
    let result = transactions.filter((tx) => {
      if (!isLive) return true; // Optionally handle pausing here, but typically paused at socket level
      if (selectedChain !== 'ALL' && tx.chain !== selectedChain) return false;
      if (tx.usdValue < minUsdFilter) return false;
      if (actionFilter !== 'ALL' && tx.action !== actionFilter) return false;
      if (tokenFilter !== 'ALL' && tx.token.toUpperCase() !== tokenFilter.toUpperCase()) return false;
      if (smartMoneyOnly && tx.smartScore < 85) return false;
      
      // Basic timeframe mock (in a real app, compare tx.timestamp with current time)
      const now = Date.now();
      if (timeframe === '1H' && now - tx.timestamp > 60 * 60 * 1000) return false;
      if (timeframe === '24H' && now - tx.timestamp > 24 * 60 * 60 * 1000) return false;
      if (timeframe === '7D' && now - tx.timestamp > 7 * 24 * 60 * 60 * 1000) return false;

      if (debouncedSearchQuery.trim() !== '') {
        const q = debouncedSearchQuery.toLowerCase();
        const matchesToken = tx.token.toLowerCase().includes(q);
        const matchesFrom = tx.fromEntity.toLowerCase().includes(q) || tx.from.toLowerCase().includes(q);
        const matchesTo = tx.toEntity.toLowerCase().includes(q) || tx.to.toLowerCase().includes(q);
        const matchesHash = tx.hash.toLowerCase().includes(q);
        if (!matchesToken && !matchesFrom && !matchesTo && !matchesHash) return false;
      }
      return true;
    });

    // Sorting logic
    result.sort((a, b) => {
      if (sortBy === 'TIME_DESC') return b.timestamp - a.timestamp;
      if (sortBy === 'TIME_ASC') return a.timestamp - b.timestamp;
      if (sortBy === 'USD_DESC') return b.usdValue - a.usdValue;
      if (sortBy === 'USD_ASC') return a.usdValue - b.usdValue;
      return 0;
    });

    return result;
  }, [transactions, selectedChain, minUsdFilter, actionFilter, tokenFilter, smartMoneyOnly, timeframe, sortBy, debouncedSearchQuery, isLive]);

  return (
    <MainLayout>
      <div className="min-h-screen bg-[#050810] text-slate-100 font-sans selection:bg-cyan-500/30 selection:text-cyan-200 antialiased flex flex-col relative overflow-hidden">
        {/* Deep ambient background glows */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
          <div className="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] rounded-full bg-cyan-900/10 blur-[120px]"></div>
          <div className="absolute top-[30%] -right-[20%] w-[60%] h-[60%] rounded-full bg-indigo-900/10 blur-[150px]"></div>
        </div>

        <div className="relative z-10 flex flex-col h-full">
          <WhaleHeader 
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            soundEnabled={soundEnabled}
            setSoundEnabled={setSoundEnabled}
            isLive={isLive}
            setIsLive={setIsLive}
          />

          <WhaleStatsCards dashboardData={dashboardData} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-5">
        <WhaleFilterBar 
          selectedChain={selectedChain}
          setSelectedChain={setSelectedChain}
          minUsdFilter={minUsdFilter}
          setMinUsdFilter={setMinUsdFilter}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          actionFilter={actionFilter}
          setActionFilter={setActionFilter}
          tokenFilter={tokenFilter}
          setTokenFilter={setTokenFilter}
          timeframe={timeframe}
          setTimeframe={setTimeframe}
          sortBy={sortBy}
          setSortBy={setSortBy}
          smartMoneyOnly={smartMoneyOnly}
          setSmartMoneyOnly={setSmartMoneyOnly}
        />

        {activeTab === 'live' && (
          <div className="space-y-6">
            <LiveStreamTable 
              transactions={filteredTransactions} 
              setInspectTx={setInspectTx}
              setInspectWallet={setInspectWallet}
              loadMoreHistory={loadMoreHistory}
              isLoadingMore={isLoadingMore}
            />
            
            <div className="pt-6 border-t border-slate-800/50">
              <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
                <span className="w-1.5 h-6 bg-cyan-500 rounded-full shadow-[0_0_10px_rgba(6,182,212,0.5)]"></span>
                Live AI Smart Money Signals
              </h2>
              <ScoresTab />
            </div>
          </div>
        )}

        {activeTab === 'visualizer' && (
          <VisualizerTab transactions={filteredTransactions} setInspectTx={setInspectTx} chainFilter={selectedChain} />
        )}

        {activeTab === 'trends' && (
          <TrendsTab dashboardData={dashboardData} />
        )}

        {activeTab === 'entities' && (
          <EntitiesTab dashboardData={dashboardData} setInspectWallet={setInspectWallet} />
        )}

        {activeTab === 'scores' && (
          <ScoresTab />
        )}

        {activeTab === 'watchlist' && (
          <WatchlistTab />
        )}

        {activeTab === 'backtest' && (
          <BacktestTab />
        )}
      </main>

      <TransactionModal inspectTx={inspectTx} setInspectTx={setInspectTx} />
      <WalletModal inspectWallet={inspectWallet} setInspectWallet={setInspectWallet} />

        <footer className="border-t border-slate-800/50 py-6 bg-[#050810]/80 backdrop-blur-md text-center text-xs text-slate-500 relative z-10 mt-auto">
          <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p>© 2026 Whale Tracker Pro Terminal. Real-time multi-chain telemetry.</p>
            <div className="flex items-center gap-6 text-slate-400">
              <span className="hover:text-cyan-400 cursor-pointer transition-colors font-semibold">API Access</span>
              <span className="hover:text-cyan-400 cursor-pointer transition-colors font-semibold">Telegram Alerts</span>
              <span className="hover:text-cyan-400 cursor-pointer transition-colors font-semibold">Documentation</span>
            </div>
          </div>
        </footer>
        </div>
      </div>
    </MainLayout>
  );
}
