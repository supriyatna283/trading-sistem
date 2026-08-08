'use client';

import React from 'react';
import { WhaleTransaction } from '@/lib/hooks/useWhaleSocket';
import { ArrowDownRight, ArrowUpRight, ArrowRightLeft, ExternalLink } from 'lucide-react';

interface WhaleFeedProps {
    transactions: WhaleTransaction[];
}

export default function WhaleFeed({ transactions }: WhaleFeedProps) {
    const formatAddress = (address: string) => {
        if (!address) return 'Unknown';
        return `${address.slice(0, 6)}...${address.slice(-4)}`;
    };

    const formatCurrency = (value: number) => {
        if (value >= 1000000) {
            return `$${(value / 1000000).toFixed(2)}M`;
        }
        return `$${(value / 1000).toFixed(0)}k`;
    };

    const getDirectionIcon = (direction: string) => {
        switch (direction) {
            case 'inflow':
                return <ArrowDownRight className="text-[#00D97E]" size={18} />;
            case 'outflow':
                return <ArrowUpRight className="text-[#FF4D4D]" size={18} />;
            case 'transfer':
            default:
                return <ArrowRightLeft className="text-[#5B8DEF]" size={18} />;
        }
    };

    const getDirectionColor = (direction: string) => {
        switch (direction) {
            case 'inflow':
                return 'text-[#00D97E] bg-[#00D97E]/10';
            case 'outflow':
                return 'text-[#FF4D4D] bg-[#FF4D4D]/10';
            case 'transfer':
            default:
                return 'text-[#5B8DEF] bg-[#5B8DEF]/10';
        }
    };

    const getChainExplorerUrl = (chain: string, txHash: string) => {
        switch (chain.toLowerCase()) {
            case 'ethereum': return `https://etherscan.io/tx/${txHash}`;
            case 'bsc': return `https://bscscan.com/tx/${txHash}`;
            case 'solana': return `https://solscan.io/tx/${txHash}`;
            default: return '#';
        }
    };

    return (
        <div className="bg-[#151A21] border border-gray-800 rounded-xl overflow-hidden font-mono text-sm shadow-xl">
            <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-[#0B0E11] border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wider">
                            <th className="p-4 font-sans font-medium">Time</th>
                            <th className="p-4 font-sans font-medium">Chain</th>
                            <th className="p-4 font-sans font-medium">Action</th>
                            <th className="p-4 font-sans font-medium">Value (USD)</th>
                            <th className="p-4 font-sans font-medium">Token</th>
                            <th className="p-4 font-sans font-medium">From / To Entity</th>
                            <th className="p-4 font-sans font-medium text-right">Tx</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800/50">
                        {transactions.length === 0 ? (
                            <tr>
                                <td colSpan={7} className="p-8 text-center text-gray-500 font-sans italic">
                                    Listening for whale transactions...
                                </td>
                            </tr>
                        ) : (
                            transactions.map((tx, idx) => {
                                // Add a subtle pulse to the newest item
                                const isNew = idx === 0;
                                
                                return (
                                    <tr 
                                        key={`${tx.chain_id}-${tx.tx_hash}-${idx}`} 
                                        className={`hover:bg-gray-800/30 transition-colors ${isNew ? 'animate-pulse bg-gray-800/20' : ''}`}
                                    >
                                        <td className="p-4 text-gray-400 whitespace-nowrap">
                                            {new Date(tx.block_time).toLocaleTimeString([], { hour12: false })}
                                        </td>
                                        <td className="p-4 uppercase text-xs font-bold text-gray-300">
                                            {tx.chain_id === 'ethereum' ? 'ETH' : tx.chain_id === 'solana' ? 'SOL' : tx.chain_id}
                                        </td>
                                        <td className="p-4">
                                            <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium uppercase tracking-wide ${getDirectionColor(tx.direction)}`}>
                                                {getDirectionIcon(tx.direction)}
                                                {tx.direction}
                                            </div>
                                        </td>
                                        <td className="p-4 text-white font-bold whitespace-nowrap">
                                            {formatCurrency(tx.usd_value)}
                                        </td>
                                        <td className="p-4 text-gray-300">
                                            {tx.amount.toLocaleString(undefined, { maximumFractionDigits: 2 })} <span className="text-gray-500">{tx.token_symbol}</span>
                                        </td>
                                        <td className="p-4">
                                            <div className="flex flex-col gap-1 text-xs">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-gray-500 w-8">From:</span>
                                                    <span className={tx.from_wallet?.label ? 'text-[#5B8DEF]' : 'text-gray-400'}>
                                                        {tx.from_wallet?.label || formatAddress(tx.from_wallet?.address || '')}
                                                    </span>
                                                    {tx.from_wallet?.entity_type && tx.from_wallet.entity_type !== 'unlabeled' && (
                                                        <span className="bg-gray-800 text-gray-300 px-1.5 py-0.5 rounded text-[10px] uppercase font-sans tracking-wide">
                                                            {tx.from_wallet.entity_type}
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-gray-500 w-8">To:</span>
                                                    <span className={tx.to_wallet?.label ? 'text-[#5B8DEF]' : 'text-gray-400'}>
                                                        {tx.to_wallet?.label || formatAddress(tx.to_wallet?.address || '')}
                                                    </span>
                                                    {tx.to_wallet?.entity_type && tx.to_wallet.entity_type !== 'unlabeled' && (
                                                        <span className="bg-gray-800 text-gray-300 px-1.5 py-0.5 rounded text-[10px] uppercase font-sans tracking-wide">
                                                            {tx.to_wallet.entity_type}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </td>
                                        <td className="p-4 text-right">
                                            <a 
                                                href={getChainExplorerUrl(tx.chain_id, tx.tx_hash)} 
                                                target="_blank" 
                                                rel="noopener noreferrer"
                                                className="inline-flex p-1.5 hover:bg-gray-700 rounded text-gray-400 hover:text-white transition-colors"
                                                title="View on Explorer"
                                            >
                                                <ExternalLink size={16} />
                                            </a>
                                        </td>
                                    </tr>
                                );
                            })
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
