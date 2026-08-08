import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  Filter,
  DollarSign,
  Wallet,
  ExternalLink,
  Zap,
  Flame,
  Search,
  Bell,
  Pause,
  Play,
  BarChart2,
  TrendingUp,
  Cpu,
  ChevronRight,
  Eye,
  Copy,
  Check,
  X,
  Sliders,
  Radio,
  ArrowRight,
  Shield,
  Layers,
  PieChart,
  Download,
  AlertTriangle,
  Volume2,
  VolumeX,
  Share2
} from 'lucide-react';

const INITIAL_TRANSACTIONS = [
  {
    id: 'tx-1',
    time: 'Just now',
    timestamp: Date.now(),
    chain: 'ETH',
    action: 'TRANSFER',
    usdValue: 32510000,
    amount: '10,835.4',
    token: 'ETH',
    from: '0x28C6...1d60',
    fromEntity: 'Binance Hot Wallet',
    fromEntityType: 'exchange',
    to: '0x56Ed...b17F',
    toEntity: 'Unknown Whale 🐋',
    toEntityType: 'whale',
    hash: '0x8f2a1b9c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a',
    gasFee: '$14.20',
    impact: 'HIGH',
    isNew: false
  },
  {
    id: 'tx-2',
    time: '12s ago',
    timestamp: Date.now() - 12000,
    chain: 'SOL',
    action: 'BUY',
    usdValue: 6420000,
    amount: '45,000',
    token: 'SOL',
    from: '2jyF...VKKt',
    fromEntity: 'Jump Trading',
    fromEntityType: 'institution',
    to: 'Unkn...iver',
    toEntity: 'Raydium Liquidity Pool',
    toEntityType: 'dex',
    hash: '5KdZ9xW...mNp2',
    gasFee: '$0.002',
    impact: 'MEDIUM',
    isNew: false
  },
  {
    id: 'tx-3',
    time: '24s ago',
    timestamp: Date.now() - 24000,
    chain: 'ETH',
    action: 'SELL',
    usdValue: 18400000,
    amount: '6,133.3',
    token: 'ETH',
    from: '0x1A07...7a2D',
    fromEntity: 'Wintermute Trading',
    fromEntityType: 'market_maker',
    to: '0xbe75...77a8',
    toEntity: 'Coinbase Prime',
    toEntityType: 'exchange',
    hash: '0x3c2b1a4f5e6d7c8b9a0f1e2d3c4b5a6f7e8d9c0b',
    gasFee: '$18.90',
    impact: 'HIGH',
    isNew: false
  },
  {
    id: 'tx-4',
    time: '45s ago',
    timestamp: Date.now() - 45000,
    chain: 'BSC',
    action: 'TRANSFER',
    usdValue: 12500000,
    amount: '20,833.3',
    token: 'BNB',
    from: '0x9C3a...88F1',
    fromEntity: 'BSC Bridge Vault',
    fromEntityType: 'bridge',
    to: '0xF3e8...11A9',
    toEntity: 'PancakeSwap Router',
    toEntityType: 'dex',
    hash: '0x11223344556677889900aabbccddeeff11223344',
    gasFee: '$0.45',
    impact: 'HIGH',
    isNew: false
  },
  {
    id: 'tx-5',
    time: '1m ago',
    timestamp: Date.now() - 60000,
    chain: 'ETH',
    action: 'SWAP',
    usdValue: 8900000,
    amount: '2,680.5',
    token: 'WBTC',
    from: '0xDFa...00b8',
    fromEntity: 'MEV Bot 0x41',
    fromEntityType: 'mev',
    to: '0x4d13...aADc',
    toEntity: 'Uniswap V3 Pool',
    toEntityType: 'dex',
    hash: '0xaa99887766554433221100fedcba9876543210fe',
    gasFee: '$42.10',
    impact: 'MEDIUM',
    isNew: false
  },
  {
    id: 'tx-6',
    time: '1m 15s ago',
    timestamp: Date.now() - 75000,
    chain: 'BASE',
    action: 'BUY',
    usdValue: 2450000,
    amount: '850,000',
    token: 'AERO',
    from: '0x6cC...5824',
    fromEntity: 'Unknown Wallet',
    fromEntityType: 'unknown',
    to: '0x9cA...B2E5',
    toEntity: 'Aerodrome Vault',
    toEntityType: 'dex',
    hash: '0x778899aabbccddeeff0011223344556677889900',
    gasFee: '$0.04',
    impact: 'MEDIUM',
    isNew: false
  },
  {
    id: 'tx-7',
    time: '1m 40s ago',
    timestamp: Date.now() - 100000,
    chain: 'SOL',
    action: 'TRANSFER',
    usdValue: 15200000,
    amount: '106,440',
    token: 'SOL',
    from: '8zTR...pQ9v',
    fromEntity: 'Kraken Cold Storage',
    fromEntityType: 'exchange',
    to: '4mKL...xY2z',
    toEntity: 'Cumberland DRW',
    toEntityType: 'institution',
    hash: '3aB8c...9xLq',
    gasFee: '$0.001',
    impact: 'HIGH',
    isNew: false
  },
  {
    id: 'tx-8',
    time: '2m ago',
    timestamp: Date.now() - 120000,
    chain: 'ETH',
    action: 'STAKE',
    usdValue: 45000000,
    amount: '15,000',
    token: 'ETH',
    from: '0x02E0...F3c2',
    fromEntity: 'Lido Staking Deposit',
    fromEntityType: 'protocol',
    to: '0x1405...405A',
    toEntity: 'Beacon Chain Contract',
    toEntityType: 'protocol',
    hash: '0x44556677889900aabbccddeeff11223344556677',
    gasFee: '$22.50',
    impact: 'MEGA',
    isNew: false
  }
];

const CHAINS = [
  { id: 'ALL', name: 'All Chains', color: 'bg-slate-700 text-slate-100' },
  { id: 'ETH', name: 'Ethereum', color: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' },
  { id: 'SOL', name: 'Solana', color: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
  { id: 'BSC', name: 'BNB Chain', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
  { id: 'BASE', name: 'Base', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  { id: 'ARB', name: 'Arbitrum', color: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30' }
];

const ACTION_COLORS = {
  TRANSFER: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  BUY: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  SELL: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  SWAP: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  STAKE: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  BRIDGE: 'bg-blue-500/10 text-blue-400 border-blue-500/20'
};

const ENTITY_BADGES = {
  exchange: { bg: 'bg-amber-500/15 text-amber-300 border-amber-500/30', label: 'Exchange' },
  institution: { bg: 'bg-blue-500/15 text-blue-300 border-blue-500/30', label: 'Fund/Inst' },
  market_maker: { bg: 'bg-purple-500/15 text-purple-300 border-purple-500/30', label: 'MM' },
  dex: { bg: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', label: 'DEX Pool' },
  whale: { bg: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30', label: 'Whale 🐋' },
  mev: { bg: 'bg-rose-500/15 text-rose-300 border-rose-500/30', label: 'MEV Bot' },
  bridge: { bg: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30', label: 'Bridge' },
  protocol: { bg: 'bg-violet-500/15 text-violet-300 border-violet-500/30', label: 'Protocol' },
  unknown: { bg: 'bg-slate-700/50 text-slate-400 border-slate-600/30', label: 'Wallet' }
};

export default function App() {
  const [transactions, setTransactions] = useState(INITIAL_TRANSACTIONS);
  const [activeTab, setActiveTab] = useState('live'); // 'live' | 'visualizer' | 'trends' | 'entities'
  const [selectedChain, setSelectedChain] = useState('ALL');
  const [minUsdFilter, setMinUsdFilter] = useState(10000);
  const [searchQuery, setSearchQuery] = useState('');
  const [actionFilter, setActionFilter] = useState('ALL');
  const [isLive, setIsLive] = useState(true);
  const [soundEnabled, setSoundEnabled] = useState(true);
  
  // Slideover & Modal states
  const [inspectTx, setInspectTx] = useState(null);
  const [inspectWallet, setInspectWallet] = useState(null);
  const [expandedTxId, setExpandedTxId] = useState(null);
  const [copiedText, setCopiedText] = useState(null);

  // Live stream generator interval simulation
  useEffect(() => {
    if (!isLive) return;

    const tokensByChain = {
      ETH: ['ETH', 'WBTC', 'USDT', 'USDC', 'LINK', 'UNI', 'PEPE'],
      SOL: ['SOL', 'JUP', 'PYTH', 'BONK', 'WIF', 'RAY'],
      BSC: ['BNB', 'CAKE', 'USDT', 'FDUSD'],
      BASE: ['ETH', 'AERO', 'BRETT', 'DEGEN'],
      ARB: ['ETH', 'ARB', 'GMX', 'PENDLE']
    };

    const actions = ['TRANSFER', 'BUY', 'SELL', 'SWAP', 'BRIDGE', 'STAKE'];
    const entityNames = [
      { name: 'Binance Hot Wallet', type: 'exchange' },
      { name: 'Wintermute Trading', type: 'market_maker' },
      { name: 'Jump Crypto', type: 'institution' },
      { name: 'Kraken Prime', type: 'exchange' },
      { name: 'Uniswap V3 Router', type: 'dex' },
      { name: 'Unknown Mega Whale 🐋', type: 'whale' },
      { name: 'MEV Bot Arbitrage', type: 'mev' },
      { name: 'BlackRock BUIDL Vault', type: 'institution' },
      { name: 'Aave V3 Reserve', type: 'protocol' },
      { name: 'Cumberland DRW', type: 'market_maker' }
    ];

    const interval = setInterval(() => {
      const chainKeys = ['ETH', 'SOL', 'BSC', 'BASE', 'ARB'];
      const randomChain = chainKeys[Math.floor(Math.random() * chainKeys.length)];
      const chainTokens = tokensByChain[randomChain];
      const randomToken = chainTokens[Math.floor(Math.random() * chainTokens.length)];
      const randomAction = actions[Math.floor(Math.random() * actions.length)];
      
      const rawUsd = Math.floor(Math.random() * Math.random() * 80000000) + 15000;
      const formattedUsd = rawUsd;
      
      let amountVal = 0;
      if (randomToken === 'ETH') amountVal = (rawUsd / 3000).toFixed(1);
      else if (randomToken === 'SOL') amountVal = (rawUsd / 140).toFixed(0);
      else if (randomToken === 'WBTC') amountVal = (rawUsd / 62000).toFixed(2);
      else if (randomToken === 'BNB') amountVal = (rawUsd / 580).toFixed(1);
      else amountVal = (rawUsd / 1.2).toFixed(0);

      const fromE = entityNames[Math.floor(Math.random() * entityNames.length)];
      let toE = entityNames[Math.floor(Math.random() * entityNames.length)];
      while (toE.name === fromE.name) {
        toE = entityNames[Math.floor(Math.random() * entityNames.length)];
      }

      const newTx = {
        id: `tx-${Date.now()}`,
        time: 'Just now',
        timestamp: Date.now(),
        chain: randomChain,
        action: randomAction,
        usdValue: formattedUsd,
        amount: Number(amountVal).toLocaleString(),
        token: randomToken,
        from: `0x${Math.random().toString(16).substr(2, 4)}...${Math.random().toString(16).substr(2, 4)}`,
        fromEntity: fromE.name,
        fromEntityType: fromE.type,
        to: `0x${Math.random().toString(16).substr(2, 4)}...${Math.random().toString(16).substr(2, 4)}`,
        toEntity: toE.name,
        toEntityType: toE.type,
        hash: `0x${Math.random().toString(16).substr(2, 32)}`,
        gasFee: `$${(Math.random() * 15 + 0.1).toFixed(2)}`,
        impact: formattedUsd > 10000000 ? 'MEGA' : formattedUsd > 2000000 ? 'HIGH' : 'MEDIUM',
        isNew: true
      };

      setTransactions((prev) => [newTx, ...prev.slice(0, 49)]);

      // Audio notification simulation chime
      if (soundEnabled && formattedUsd > 5000000) {
        // Subtle alert indication state
      }
    }, 3500);

    return () => clearInterval(interval);
  }, [isLive, soundEnabled]);

  const filteredTransactions = useMemo(() => {
    return transactions.filter((tx) => {
      if (selectedChain !== 'ALL' && tx.chain !== selectedChain) return false;
      if (tx.usdValue < minUsdFilter) return false;
      if (actionFilter !== 'ALL' && tx.action !== actionFilter) return false;
      if (searchQuery.trim() !== '') {
        const q = searchQuery.toLowerCase();
        const matchesToken = tx.token.toLowerCase().includes(q);
        const matchesFrom = tx.fromEntity.toLowerCase().includes(q) || tx.from.toLowerCase().includes(q);
        const matchesTo = tx.toEntity.toLowerCase().includes(q) || tx.to.toLowerCase().includes(q);
        const matchesHash = tx.hash.toLowerCase().includes(q);
        if (!matchesToken && !matchesFrom && !matchesTo && !matchesHash) return false;
      }
      return true;
    });
  }, [transactions, selectedChain, minUsdFilter, actionFilter, searchQuery]);

  // Calculated Stats
  const total24hVolume = useMemo(() => {
    return transactions.reduce((acc, curr) => acc + curr.usdValue, 0);
  }, [transactions]);

  const megaTransactionsCount = useMemo(() => {
    return transactions.filter((t) => t.usdValue >= 5000000).length;
  }, [transactions]);

  const topToken = useMemo(() => {
    const tokenCounts = {};
    transactions.forEach((t) => {
      tokenCounts[t.token] = (tokenCounts[t.token] || 0) + t.usdValue;
    });
    let maxT = 'ETH';
    let maxV = 0;
    Object.entries(tokenCounts).forEach(([tk, val]) => {
      if (val > maxV) {
        maxV = val;
        maxT = tk;
      }
    });
    return { token: maxT, volume: maxV };
  }, [transactions]);

  // Helpers
  const formatUsd = (val) => {
    if (val >= 1000000) return `$${(val / 1000000).toFixed(2)}M`;
    if (val >= 1000) return `$${(val / 1000).toFixed(0)}k`;
    return `$${val.toLocaleString()}`;
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedText(text);
    setTimeout(() => setCopiedText(null), 2000);
  };

  return (
    <div className="min-h-screen bg-[#0a0d14] text-slate-100 font-sans selection:bg-cyan-500/30 selection:text-cyan-200 antialiased flex flex-col">
      {}
      <header className="border-b border-slate-800/80 bg-[#0d111a]/90 backdrop-blur-md sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          {/* Logo & Live Pulse */}
          <div className="flex items-[#10b981] justify-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/30 text-cyan-400 shadow-lg shadow-cyan-500/10">
              <Activity className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-wider bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                  WHALE<span className="text-cyan-400 font-extrabold">TRACKER</span>
                  <span className="text-xs font-semibold px-2 py-0.5 ml-2 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300">
                    PRO
                  </span>
                </h1>
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  LIVE STREAM
                </div>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">
                Real-time multi-chain institutional flow & mega-whale alert terminal
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden lg:flex items-center gap-1 p-1 rounded-xl bg-slate-900/80 border border-slate-800">
            <button
              onClick={() => setActiveTab('live')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'live'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Zap className="w-3.5 h-3.5" /> Live Stream
            </button>
            <button
              onClick={() => setActiveTab('visualizer')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'visualizer'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <BarChart2 className="w-3.5 h-3.5" /> Flow Scatter Visualizer
            </button>
            <button
              onClick={() => setActiveTab('trends')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'trends'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" /> Market Heatmap
            </button>
            <button
              onClick={() => setActiveTab('entities')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'entities'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Shield className="w-3.5 h-3.5" /> Smart Money Directory
            </button>
          </nav>

          {/* Quick Utility Toggles */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSoundEnabled(!soundEnabled)}
              title="Toggle Audio Alert Chime"
              className={`p-2 rounded-lg border transition-all ${
                soundEnabled
                  ? 'bg-slate-800 border-slate-700 text-cyan-400'
                  : 'bg-slate-900 border-slate-800 text-slate-500'
              }`}
            >
              {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>

            <button
              onClick={() => setIsLive(!isLive)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
                isLive
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                  : 'bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20'
              }`}
            >
              {isLive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              <span>{isLive ? 'Pause Feed' : 'Resume Feed'}</span>
            </button>
          </div>
        </div>
      </header>

      {}
      <section className="bg-[#0f1420] border-b border-slate-800/80 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400 tracking-wider uppercase">Detected 24h Flow</p>
              <p className="text-xl font-black text-slate-100 tracking-tight mt-0.5">
                {formatUsd(total24hVolume)}
              </p>
            </div>
            <div className="p-2.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <DollarSign className="w-5 h-5" />
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400 tracking-wider uppercase">Mega Whale Moves (&gt;$5M)</p>
              <p className="text-xl font-black text-amber-400 tracking-tight mt-0.5 flex items-center gap-1.5">
                {megaTransactionsCount}
                <span className="text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                  +18%
                </span>
              </p>
            </div>
            <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Flame className="w-5 h-5" />
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400 tracking-wider uppercase">Top Accumulated Asset</p>
              <p className="text-xl font-black text-emerald-400 tracking-tight mt-0.5">
                {topToken.token}
              </p>
            </div>
            <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400 tracking-wider uppercase">Network Telemetry</p>
              <div className="flex items-center gap-3 text-xs font-semibold mt-1">
                <span className="text-slate-300">
                  <span className="text-slate-500">ETH Gas:</span> 14 Gwei
                </span>
                <span className="text-slate-300">
                  <span className="text-slate-500">SOL TPS:</span> 2,840
                </span>
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <Cpu className="w-5 h-5" />
            </div>
          </div>
        </div>
      </section>

      {}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-5">
        {/* Filter Controls Bar */}
        <div className="p-4 rounded-2xl bg-[#0f1420] border border-slate-800/80 shadow-xl space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            {/* Chain Selector Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-1 flex items-center gap-1">
                <Filter className="w-3.5 h-3.5 text-cyan-400" /> Chains:
              </span>
              {CHAINS.map((chain) => (
                <button
                  key={chain.id}
                  onClick={() => setSelectedChain(chain.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${
                    selectedChain === chain.id
                      ? 'bg-cyan-500 text-slate-950 border-cyan-400 shadow-lg shadow-cyan-500/20'
                      : 'bg-slate-900/80 text-slate-400 border-slate-800 hover:bg-slate-800 hover:text-slate-200'
                  }`}
                >
                  {chain.name}
                </button>
              ))}
            </div>

            {/* Threshold Filter Buttons */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-1">
                Min Size:
              </span>
              {[
                { label: 'All ($10k+)', val: 10000 },
                { label: '$100k+', val: 100000 },
                { label: '$1M+ 🐋', val: 1000000 },
                { label: '$10M+ 🚀', val: 10000000 }
              ].map((opt) => (
                <button
                  key={opt.val}
                  onClick={() => setMinUsdFilter(opt.val)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all border ${
                    minUsdFilter === opt.val
                      ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
                      : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:text-slate-200'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800/60 flex flex-wrap items-center justify-between gap-3">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[240px]">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search token symbol, entity, wallet or transaction hash..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Action Type Dropdown / Selector */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-medium">Action:</span>
              <select
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                className="bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500/50"
              >
                <option value="ALL">All Actions</option>
                <option value="TRANSFER">Transfers Only</option>
                <option value="BUY">Buys / Swaps</option>
                <option value="SELL">Sells</option>
                <option value="STAKE">Staking</option>
                <option value="BRIDGE">Bridge Cross-chain</option>
              </select>

              <button
                onClick={() => {
                  setSelectedChain('ALL');
                  setMinUsdFilter(10000);
                  setSearchQuery('');
                  setActionFilter('ALL');
                }}
                className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-semibold"
              >
                Reset
              </button>
            </div>
          </div>
        </div>

        {/* TAB 1: LIVE FEED TABLE */}
        {activeTab === 'live' && (
          <div className="rounded-2xl border border-slate-800/80 bg-[#0d111a] shadow-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/40">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></div>
                <h3 className="text-sm font-bold text-slate-200">
                  Real-time Transaction Stream
                </h3>
                <span className="text-xs text-slate-500">
                  ({filteredTransactions.length} whale movements matching filters)
                </span>
              </div>
              <span className="text-xs text-slate-400">Click any row for route visualization</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-900/80 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-4">Time</th>
                    <th className="py-3 px-4">Chain</th>
                    <th className="py-3 px-4">Action</th>
                    <th className="py-3 px-4 text-right">Value (USD)</th>
                    <th className="py-3 px-4">Token Amount</th>
                    <th className="py-3 px-4">From Entity</th>
                    <th className="py-3 px-4">To Entity</th>
                    <th className="py-3 px-4 text-center">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50 text-xs font-medium">
                  {filteredTransactions.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-slate-500">
                        <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-slate-600" />
                        No whale transactions match your active filters. Try lowering the threshold or resetting filters.
                      </td>
                    </tr>
                  ) : (
                    filteredTransactions.map((tx) => {
                      const isExpanded = expandedTxId === tx.id;
                      const fromBadge = ENTITY_BADGES[tx.fromEntityType] || ENTITY_BADGES.unknown;
                      const toBadge = ENTITY_BADGES[tx.toEntityType] || ENTITY_BADGES.unknown;

                      return (
                        <React.Fragment key={tx.id}>
                          <tr
                            onClick={() => setExpandedTxId(isExpanded ? null : tx.id)}
                            className={`group cursor-pointer transition-colors ${
                              tx.isNew
                                ? 'bg-cyan-500/10'
                                : isExpanded
                                ? 'bg-slate-800/60'
                                : 'hover:bg-slate-800/30'
                            }`}
                          >
                            {/* Time */}
                            <td className="py-3 px-4 font-mono text-slate-400 whitespace-nowrap">
                              {tx.time}
                            </td>

                            {/* Chain */}
                            <td className="py-3 px-4 whitespace-nowrap">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${
                                  CHAINS.find((c) => c.id === tx.chain)?.color || 'bg-slate-800 text-slate-300'
                                }`}
                              >
                                {tx.chain}
                              </span>
                            </td>

                            {/* Action */}
                            <td className="py-3 px-4 whitespace-nowrap">
                              <span
                                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                                  ACTION_COLORS[tx.action] || 'bg-slate-800 text-slate-300'
                                }`}
                              >
                                {tx.action === 'BUY' && <ArrowDownRight className="w-3 h-3 text-emerald-400" />}
                                {tx.action === 'SELL' && <ArrowUpRight className="w-3 h-3 text-rose-400" />}
                                {tx.action === 'TRANSFER' && <RefreshCw className="w-3 h-3 text-cyan-400" />}
                                {tx.action}
                              </span>
                            </td>

                            {/* Value USD */}
                            <td className="py-3 px-4 text-right whitespace-nowrap font-mono font-bold text-slate-100 text-sm">
                              {formatUsd(tx.usdValue)}
                              {tx.impact === 'MEGA' && (
                                <span className="ml-1.5 inline-block text-[10px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-sans">
                                  MEGA
                                </span>
                              )}
                            </td>

                            {/* Token Amount */}
                            <td className="py-3 px-4 whitespace-nowrap font-mono">
                              <span className="text-slate-200 font-bold">{tx.amount}</span>{' '}
                              <span className="text-cyan-400 text-xs font-semibold">{tx.token}</span>
                            </td>

                            {/* From Entity */}
                            <td className="py-3 px-4 whitespace-nowrap">
                              <div className="flex items-center gap-1.5">
                                <span
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setInspectWallet({ name: tx.fromEntity, type: tx.fromEntityType, address: tx.from });
                                  }}
                                  className="font-bold text-slate-200 hover:text-cyan-300 hover:underline"
                                >
                                  {tx.fromEntity}
                                </span>
                                <span
                                  className={`px-1.5 py-0.2 rounded text-[9px] font-semibold border ${fromBadge.bg}`}
                                >
                                  {fromBadge.label}
                                </span>
                              </div>
                              <span className="text-[10px] text-slate-500 font-mono">{tx.from}</span>
                            </td>

                            {/* To Entity */}
                            <td className="py-3 px-4 whitespace-nowrap">
                              <div className="flex items-center gap-1.5">
                                <span
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setInspectWallet({ name: tx.toEntity, type: tx.toEntityType, address: tx.to });
                                  }}
                                  className="font-bold text-slate-200 hover:text-cyan-300 hover:underline"
                                >
                                  {tx.toEntity}
                                </span>
                                <span
                                  className={`px-1.5 py-0.2 rounded text-[9px] font-semibold border ${toBadge.bg}`}
                                >
                                  {toBadge.label}
                                </span>
                              </div>
                              <span className="text-[10px] text-slate-500 font-mono">{tx.to}</span>
                            </td>

                            {/* Action Buttons */}
                            <td className="py-3 px-4 text-center whitespace-nowrap">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setInspectTx(tx);
                                }}
                                className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 transition-colors"
                                title="Detailed Route Inspection"
                              >
                                <Eye className="w-3.5 h-3.5" />
                              </button>
                            </td>
                          </tr>

                          {/* Expanded Visual Flow Row */}
                          {isExpanded && (
                            <tr className="bg-slate-900/90 border-b border-slate-800">
                              <td colSpan={8} className="p-4">
                                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                                  <div className="flex items-center justify-between text-xs text-slate-400">
                                    <span className="font-semibold text-slate-300 flex items-center gap-1">
                                      <Zap className="w-3.5 h-3.5 text-amber-400" /> Transaction Route Visualizer
                                    </span>
                                    <div className="flex items-center gap-3">
                                      <span>Est. Gas: <strong className="text-slate-200">{tx.gasFee}</strong></span>
                                      <span>Tx Hash: <code className="text-cyan-400">{tx.hash}</code></span>
                                      <button
                                        onClick={() => copyToClipboard(tx.hash)}
                                        className="text-slate-400 hover:text-slate-200"
                                      >
                                        {copiedText === tx.hash ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                                      </button>
                                    </div>
                                  </div>

                                  {/* Route Path Flow Diagram */}
                                  <div className="flex items-center justify-between gap-4 py-3 px-6 rounded-lg bg-slate-900 border border-slate-800/80">
                                    {/* Source Node */}
                                    <div className="text-center">
                                      <p className="text-[10px] text-slate-500 uppercase tracking-wider">Origin</p>
                                      <p className="font-bold text-slate-200 text-sm">{tx.fromEntity}</p>
                                      <p className="text-[10px] text-slate-400 font-mono">{tx.from}</p>
                                    </div>

                                    {/* Path Line with Token Info */}
                                    <div className="flex-1 flex flex-col items-center">
                                      <span className="text-xs font-bold text-cyan-400 mb-1">
                                        {tx.amount} {tx.token} ({formatUsd(tx.usdValue)})
                                      </span>
                                      <div className="w-full flex items-center">
                                        <div className="h-0.5 flex-1 bg-gradient-to-r from-cyan-500 to-indigo-500"></div>
                                        <div className="p-1 rounded-full bg-indigo-600 text-slate-100 shadow-md">
                                          <ArrowRight className="w-4 h-4" />
                                        </div>
                                        <div className="h-0.5 flex-1 bg-gradient-to-r from-indigo-500 to-emerald-500"></div>
                                      </div>
                                      <span className="text-[10px] text-slate-400 mt-1">
                                        Action: {tx.action} via {tx.chain} Network
                                      </span>
                                    </div>

                                    {/* Destination Node */}
                                    <div className="text-center">
                                      <p className="text-[10px] text-slate-500 uppercase tracking-wider">Destination</p>
                                      <p className="font-bold text-slate-200 text-sm">{tx.toEntity}</p>
                                      <p className="text-[10px] text-slate-400 font-mono">{tx.to}</p>
                                    </div>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {}
        {activeTab === 'visualizer' && (
          <div className="p-6 rounded-2xl border border-slate-800/80 bg-[#0d111a] shadow-2xl space-y-4">
            <div>
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <BarChart2 className="w-5 h-5 text-cyan-400" />
                Whale Flow Scatter Visualizer
              </h3>
              <p className="text-xs text-slate-400">
                Bubble size represents transaction volume USD. Y-axis represents USD size, X-axis represents relative arrival time.
              </p>
            </div>

            {/* Bubble Canvas Simulation Container */}
            <div className="relative h-96 w-full rounded-xl bg-slate-950 border border-slate-800/80 p-4 flex flex-col justify-between overflow-hidden">
              {/* Grid Lines */}
              <div className="absolute inset-0 grid grid-rows-4 grid-cols-6 border-slate-800/20 pointer-events-none">
                {[...Array(24)].map((_, i) => (
                  <div key={i} className="border-b border-r border-slate-800/30"></div>
                ))}
              </div>

              {/* Y-Axis Scale Labels */}
              <div className="absolute left-3 top-3 text-[10px] font-mono text-slate-500">$50M+</div>
              <div className="absolute left-3 top-1/3 text-[10px] font-mono text-slate-500">$10M</div>
              <div className="absolute left-3 top-2/3 text-[10px] font-mono text-slate-500">$1M</div>

              {/* Plotted Bubbles */}
              <div className="relative w-full h-full">
                {filteredTransactions.map((tx, idx) => {
                  const yPos = Math.max(10, Math.min(90, 100 - (tx.usdValue / 50000000) * 85));
                  const xPos = Math.max(5, Math.min(92, 95 - (idx / filteredTransactions.length) * 88));
                  const bubbleSize = Math.max(24, Math.min(64, (tx.usdValue / 50000000) * 50 + 20));

                  const isBuy = tx.action === 'BUY';
                  const isSell = tx.action === 'SELL';

                  return (
                    <div
                      key={tx.id}
                      onClick={() => setInspectTx(tx)}
                      style={{
                        top: `${yPos}%`,
                        left: `${xPos}%`,
                        width: `${bubbleSize}px`,
                        height: `${bubbleSize}px`
                      }}
                      className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full cursor-pointer transition-all duration-300 hover:scale-125 hover:z-20 flex items-center justify-center border shadow-lg ${
                        isBuy
                          ? 'bg-emerald-500/30 border-emerald-400 text-emerald-200 shadow-emerald-500/20'
                          : isSell
                          ? 'bg-rose-500/30 border-rose-400 text-rose-200 shadow-rose-500/20'
                          : 'bg-cyan-500/30 border-cyan-400 text-cyan-200 shadow-cyan-500/20'
                      }`}
                      title={`${tx.token}: ${formatUsd(tx.usdValue)} (${tx.fromEntity} -> ${tx.toEntity})`}
                    >
                      <span className="text-[9px] font-black tracking-tighter truncate px-1">
                        {tx.token}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* X-Axis Footer */}
              <div className="flex justify-between text-[10px] font-mono text-slate-500 pt-2 border-t border-slate-800">
                <span>Older Activity</span>
                <span>Real-time Streams ➔</span>
              </div>
            </div>
          </div>
        )}

        {}
        {activeTab === 'trends' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-6 rounded-2xl border border-slate-800/80 bg-[#0d111a] shadow-2xl space-y-4">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <PieChart className="w-4 h-4 text-cyan-400" />
                Chain Volume Breakdown
              </h3>
              <div className="space-y-3">
                {[
                  { chain: 'Ethereum (ETH)', pct: 58, val: '$824.2M', color: 'bg-indigo-500' },
                  { chain: 'Solana (SOL)', pct: 24, val: '$341.5M', color: 'bg-purple-500' },
                  { chain: 'BNB Chain (BSC)', pct: 10, val: '$142.1M', color: 'bg-amber-500' },
                  { chain: 'Base (BASE)', pct: 5, val: '$71.0M', color: 'bg-blue-500' },
                  { chain: 'Arbitrum (ARB)', pct: 3, val: '$42.6M', color: 'bg-cyan-500' }
                ].map((c) => (
                  <div key={c.chain} className="space-y-1">
                    <div className="flex justify-between text-xs font-semibold text-slate-300">
                      <span>{c.chain}</span>
                      <span className="font-mono">{c.val} ({c.pct}%)</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-slate-900 overflow-hidden">
                      <div
                        className={`h-full ${c.color}`}
                        style={{ width: `${c.pct}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-6 rounded-2xl border border-slate-800/80 bg-[#0d111a] shadow-2xl space-y-4">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                Institutional Net Flow Bias
              </h3>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-slate-400">24h Net Exchange Inflow / Outflow</p>
                    <p className="text-lg font-bold text-emerald-400 mt-0.5">
                      +$184.5M Net Accumulation (Outflow from CEX)
                    </p>
                  </div>
                  <span className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold text-xs">
                    BULLISH FLOW
                  </span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Mega whales are withdrawing ETH and SOL from Binance and Coinbase into non-custodial staking and cold wallets, indicating low immediate sell pressure.
                </p>
              </div>
            </div>
          </div>
        )}

        {}
        {activeTab === 'entities' && (
          <div className="p-6 rounded-2xl border border-slate-800/80 bg-[#0d111a] shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Shield className="w-5 h-5 text-indigo-400" />
              Tracked Smart Money Entities & Institutional Profiles
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { name: 'Binance Hot Wallet #1', type: 'Exchange', volume: '$420.5M 24h', rating: 'High Liquidity', badge: 'exchange' },
                { name: 'Wintermute Trading', type: 'Market Maker', volume: '$180.2M 24h', rating: 'High Frequency', badge: 'market_maker' },
                { name: 'Jump Crypto', type: 'Institution', volume: '$95.4M 24h', rating: 'Strategic Flow', badge: 'institution' },
                { name: 'BlackRock BUIDL Vault', type: 'Institutional ETF', volume: '$210.0M 24h', rating: 'Long Term Custody', badge: 'institution' },
                { name: 'MEV Bot Arbitrage', type: 'Algorithmic', volume: '$45.1M 24h', rating: 'MEV Sandwich', badge: 'mev' },
                { name: 'Justin Sun Wallet', type: 'Whale Individual', volume: '$62.8M 24h', rating: 'High Impact', badge: 'whale' }
              ].map((entity) => (
                <div
                  key={entity.name}
                  onClick={() => setInspectWallet({ name: entity.name, type: entity.badge, address: '0x71C...88B1' })}
                  className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-cyan-500/50 cursor-pointer transition-all space-y-2 group"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-200 text-sm group-hover:text-cyan-300">
                      {entity.name}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${ENTITY_BADGES[entity.badge].bg}`}>
                      {ENTITY_BADGES[entity.badge].label}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-400">
                    <span>24h Flow: <strong className="text-slate-200">{entity.volume}</strong></span>
                    <span className="text-cyan-400">{entity.rating}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {}
      {inspectTx && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
          <div className="bg-[#0f1420] border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative space-y-5">
            <button
              onClick={() => setInspectTx(null)}
              className="absolute top-4 right-4 p-1.5 rounded-lg bg-slate-800/80 text-slate-400 hover:text-slate-200"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                <Zap className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-100">
                  Transaction Deep Dive
                </h3>
                <p className="text-xs text-slate-400">Verified On-Chain Multi-Chain Event</p>
              </div>
            </div>

            <div className="space-y-3 p-4 rounded-xl bg-slate-950 border border-slate-800/80 text-xs font-mono">
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-500">Amount & Asset:</span>
                <span className="text-cyan-300 font-bold">{inspectTx.amount} {inspectTx.token}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-500">USD Value:</span>
                <span className="text-slate-100 font-bold">{formatUsd(inspectTx.usdValue)}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-500">Origin Entity:</span>
                <span className="text-slate-200 font-bold">{inspectTx.fromEntity}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-500">Destination Entity:</span>
                <span className="text-slate-200 font-bold">{inspectTx.toEntity}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-500">Est. Gas Fee:</span>
                <span className="text-slate-300">{inspectTx.gasFee}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Transaction Hash:</span>
                <span className="text-cyan-400 truncate max-w-[180px]">{inspectTx.hash}</span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => copyToClipboard(inspectTx.hash)}
                className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs flex items-center justify-center gap-2"
              >
                <Copy className="w-4 h-4" /> Copy Hash
              </button>
              <a
                href="#"
                onClick={(e) => e.preventDefault()}
                className="flex-1 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20"
              >
                <ExternalLink className="w-4 h-4" /> Block Explorer
              </a>
            </div>
          </div>
        </div>
      )}

      {}
      {inspectWallet && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/70 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md bg-[#0d111a] border-l border-slate-800 h-full p-6 shadow-2xl flex flex-col justify-between space-y-6">
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-base font-bold text-slate-100">{inspectWallet.name}</h3>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">{inspectWallet.address}</p>
                </div>
                <button
                  onClick={() => setInspectWallet(null)}
                  className="p-1.5 rounded-lg bg-slate-800/80 text-slate-400 hover:text-slate-200"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Wallet Summary KPI */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <p className="text-xs text-slate-400">Estimated On-Chain Balance</p>
                <p className="text-2xl font-black text-emerald-400">$248,510,000</p>
                <div className="flex items-center gap-2 text-xs text-slate-400 pt-1">
                  <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                    Risk Score: Low (0.04)
                  </span>
                </div>
              </div>

              {/* Asset Holdings Distribution */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Top Token Holdings</h4>
                {[
                  { token: 'ETH', amount: '45,200 ETH', val: '$135.6M', pct: 54 },
                  { token: 'USDC', amount: '68,000,000 USDC', val: '$68.0M', pct: 27 },
                  { token: 'SOL', amount: '250,000 SOL', val: '$35.0M', pct: 14 }
                ].map((item) => (
                  <div key={item.token} className="p-3 rounded-lg bg-slate-900 border border-slate-800/80 flex items-center justify-between">
                    <div>
                      <p className="font-bold text-slate-200 text-xs">{item.token}</p>
                      <p className="text-[10px] text-slate-400">{item.amount}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-xs font-bold text-slate-100">{item.val}</p>
                      <p className="text-[10px] text-cyan-400">{item.pct}% of portfolio</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={() => setInspectWallet(null)}
              className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs"
            >
              Close Profile
            </button>
          </div>
        </div>
      )}

      {}
      <footer className="border-t border-slate-800/80 py-4 bg-[#0d111a] text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>© 2026 Whale Tracker Pro Terminal. Real-time multi-chain telemetry.</p>
          <div className="flex items-center gap-4 text-slate-400">
            <span className="hover:text-cyan-400 cursor-pointer">API Access</span>
            <span className="hover:text-cyan-400 cursor-pointer">Telegram Alerts</span>
            <span className="hover:text-cyan-400 cursor-pointer">Documentation</span>
          </div>
        </div>
      </footer>
    </div>
  );
}