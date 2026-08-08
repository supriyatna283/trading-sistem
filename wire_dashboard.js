const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/whale-tracker/page.tsx', 'utf8');

// 1. Add dashboardData state
code = code.replace(
    "const [copiedText, setCopiedText] = useState<string | null>(null);",
    "const [copiedText, setCopiedText] = useState<string | null>(null);\n  const [dashboardData, setDashboardData] = useState<any>(null);"
);

// 2. Add fetchDashboard inside the existing useEffect block or add a new useEffect
const fetchLiveBlock = /useEffect\(\(\) => \{\s*const fetchLive = async \(\) => \{.*?\};\s*fetchLive\(\);\s*\}, \[selectedChain, setInitialTransactions, API_URL\]\);/s;
const newFetchBlock = `
  useEffect(() => {
      const fetchLive = async () => {
          try {
              const params = new URLSearchParams({ limit: '50' });
              if (selectedChain !== 'ALL') params.append('chain', selectedChain);
              const res = await fetch(\`\${API_URL}/whale/live?\${params.toString()}\`);
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
              const res = await fetch(\`\${API_URL}/whale/dashboard\`);
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
      
      // Setup polling for dashboard every 30s
      const interval = setInterval(fetchDashboard, 30000);
      return () => clearInterval(interval);
  }, [selectedChain, setInitialTransactions, API_URL]);
`;
code = code.replace(fetchLiveBlock, newFetchBlock);

// 3. Replace calculated stats
code = code.replace(
    "const total24hVolume = useMemo(() => {\n    return transactions.reduce((acc, curr) => acc + curr.usdValue, 0);\n  }, [transactions]);",
    "const total24hVolume = dashboardData?.total_volume_24h || 0;"
);

code = code.replace(
    "const megaTransactionsCount = useMemo(() => {\n    return transactions.filter((t) => t.usdValue >= 5000000).length;\n  }, [transactions]);",
    "const megaTransactionsCount = dashboardData?.mega_moves_count || 0;"
);

code = code.replace(
    /const topToken = useMemo\(\(\) => \{.*?\}, \[transactions\]\);/s,
    "const topToken = { token: dashboardData?.top_asset || 'N/A', volume: 0 };"
);

// 4. Update Pie Chart static array
const oldPieChart = `[
                  { chain: 'Ethereum (ETH)', pct: 58, val: '$824.2M', color: 'bg-indigo-500' },
                  { chain: 'Solana (SOL)', pct: 24, val: '$341.5M', color: 'bg-purple-500' },
                  { chain: 'BNB Chain (BSC)', pct: 10, val: '$142.1M', color: 'bg-amber-500' },
                  { chain: 'Base (BASE)', pct: 5, val: '$71.0M', color: 'bg-blue-500' },
                  { chain: 'Arbitrum (ARB)', pct: 3, val: '$42.6M', color: 'bg-cyan-500' }
                ]`;

const newPieChart = `
                (dashboardData?.chain_breakdown ? Object.entries(dashboardData.chain_breakdown).map(([chain, data]: any) => {
                    const colors: any = {
                        ethereum: 'bg-indigo-500',
                        solana: 'bg-purple-500',
                        bsc: 'bg-amber-500',
                        base: 'bg-blue-500',
                        arbitrum: 'bg-cyan-500'
                    };
                    return {
                        chain: chain.toUpperCase(),
                        pct: data.percentage,
                        val: formatUsd(data.volume),
                        color: colors[chain] || 'bg-slate-500'
                    }
                }) : [])
`;
code = code.replace(oldPieChart, newPieChart);

// 5. Update Net Flow Bias
code = code.replace(
    "+$184.5M Net Accumulation (Outflow from CEX)",
    "{dashboardData?.net_flow_bias?.description || 'Loading...'}"
);
code = code.replace(
    "BULLISH FLOW",
    "{dashboardData?.net_flow_bias?.label || 'LOADING'}"
);
code = code.replace(
    "Mega whales are withdrawing ETH and SOL from Binance and Coinbase into non-custodial staking and cold wallets, indicating low immediate sell pressure.",
    "Real-time calculation of net exchange flows based on on-chain transactions exceeding minimum tracking thresholds."
);

// 6. Update Entities Array
const oldEntities = `[
                { name: 'Binance Hot Wallet #1', type: 'Exchange', volume: '$420.5M 24h', rating: 'High Liquidity', badge: 'exchange' },
                { name: 'Wintermute Trading', type: 'Market Maker', volume: '$180.2M 24h', rating: 'High Frequency', badge: 'market_maker' },
                { name: 'Jump Crypto', type: 'Institution', volume: '$95.4M 24h', rating: 'Strategic Flow', badge: 'institution' },
                { name: 'BlackRock BUIDL Vault', type: 'Institutional ETF', volume: '$210.0M 24h', rating: 'Long Term Custody', badge: 'institution' },
                { name: 'MEV Bot Arbitrage', type: 'Algorithmic', volume: '$45.1M 24h', rating: 'MEV Sandwich', badge: 'mev' },
                { name: 'Justin Sun Wallet', type: 'Whale Individual', volume: '$62.8M 24h', rating: 'High Impact', badge: 'whale' }
              ]`;
const newEntities = `
              (dashboardData?.top_entities ? dashboardData.top_entities.map((e: any) => {
                  let rating = "Active Entity";
                  if (e.type === 'exchange') rating = "High Liquidity";
                  else if (e.type === 'market_maker') rating = "High Frequency";
                  else if (e.type === 'whale') rating = "High Impact";
                  
                  return {
                      name: e.name,
                      type: e.type.replace('_', ' ').toUpperCase(),
                      volume: formatUsd(e.volume) + ' 24h',
                      rating: rating,
                      badge: e.type
                  }
              }) : [])
`;
code = code.replace(oldEntities, newEntities);

fs.writeFileSync('frontend/src/app/whale-tracker/page.tsx', code, 'utf8');
console.log('Dashboard backend data integrated successfully!');
