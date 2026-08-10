export const CHAINS = [
  { id: 'ALL', name: 'All Chains', color: 'bg-slate-700 text-slate-100' },
  { id: 'ETH', name: 'Ethereum', color: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' },
  { id: 'SOL', name: 'Solana', color: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
  { id: 'BSC', name: 'BNB Chain', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
  { id: 'BASE', name: 'Base', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  { id: 'ARB', name: 'Arbitrum', color: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30' },
  { id: 'BITCOIN', name: 'Bitcoin', color: 'bg-orange-500/20 text-orange-400 border-orange-500/30' },
  { id: 'HYPERLIQUID', name: 'Hyperliquid', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' }
];

export const ACTION_COLORS: any = {
  INFLOW: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  OUTFLOW: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  TRANSFER: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  BUY: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  SELL: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  SWAP: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  STAKE: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  BRIDGE: 'bg-blue-500/10 text-blue-400 border-blue-500/20'
};

export const ENTITY_BADGES: any = {
  exchange: { bg: 'bg-amber-500/15 text-amber-300 border-amber-500/30', label: 'Exchange' },
  institution: { bg: 'bg-blue-500/15 text-blue-300 border-blue-500/30', label: 'Fund/Inst' },
  market_maker: { bg: 'bg-purple-500/15 text-purple-300 border-purple-500/30', label: 'MM' },
  dex: { bg: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', label: 'DEX Pool' },
  whale: { bg: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30', label: 'Whale 🐋' },
  mev: { bg: 'bg-rose-500/15 text-rose-300 border-rose-500/30', label: 'MEV Bot' },
  bridge: { bg: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30', label: 'Bridge' },
  protocol: { bg: 'bg-violet-500/15 text-violet-300 border-violet-500/30', label: 'Protocol' },
  unknown: { bg: 'bg-slate-700/50 text-slate-400 border-slate-600/30', label: 'Wallet' },
  unlabeled: { bg: 'bg-slate-700/50 text-slate-400 border-slate-600/30', label: 'Wallet' }
};

export const getBlockExplorerUrl = (chain: string, hash: string) => {
  const chainUpper = chain.toUpperCase();
  switch (chainUpper) {
    case 'ETH':
    case 'ETHEREUM':
      return `https://etherscan.io/tx/${hash}`;
    case 'SOL':
    case 'SOLANA':
      return `https://solscan.io/tx/${hash}`;
    case 'BSC':
    case 'BINANCE':
    case 'BNB':
      return `https://bscscan.com/tx/${hash}`;
    case 'BASE':
      return `https://basescan.org/tx/${hash}`;
    case 'ARB':
    case 'ARBITRUM':
      return `https://arbiscan.io/tx/${hash}`;
    case 'BTC':
    case 'BITCOIN':
      return `https://mempool.space/tx/${hash}`;
    case 'HYPERLIQUID':
      return `https://app.hyperliquid.xyz/explorer/tx/${hash}`;
    default:
      return '#';
  }
};

export const formatUsd = (val: number) => {
  if (val >= 1000000) return `$${(val / 1000000).toFixed(2)}M`;
  if (val >= 1000) return `$${(val / 1000).toFixed(0)}k`;
  return `$${val.toLocaleString()}`;
};
