import { useState, useEffect, useCallback, useRef } from 'react';
import { API_URL } from '@/lib/utils';

export interface WalletInfo {
    id: number;
    chain_id: string;
    address: string;
    label: string | null;
    entity_type: string;
    confidence: number | null;
}

export interface WhaleTransaction {
    id: number;
    chain_id: string;
    tx_hash: string;
    from_wallet: WalletInfo | null;
    to_wallet: WalletInfo | null;
    token_symbol: string;
    token_address: string | null;
    amount: number;
    usd_value: number;
    direction: 'inflow' | 'outflow' | 'transfer';
    block_time: string;
    detected_at: string;
    raw_source: string;
    isNew?: boolean;
}

const getWsUrl = () => {
    return API_URL.replace(/^http/, 'ws') + '/ws/whale';
};

export function useWhaleSocket(url: string = getWsUrl()) {
    const [transactions, setTransactions] = useState<WhaleTransaction[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const ws = new WebSocket(url);

        ws.onopen = () => {
            console.log('Connected to Whale WS');
            setIsConnected(true);
        };

        ws.onmessage = (event) => {
            try {
                const tx: WhaleTransaction = JSON.parse(event.data);
                tx.isNew = true; // Flag for UI highlight
                // Prepend the new transaction and keep up to 500 items
                setTransactions((prev) => [tx, ...prev].slice(0, 500));
            } catch (error) {
                console.error('Failed to parse whale tx data:', error);
            }
        };

        ws.onclose = () => {
            console.log('Disconnected from Whale WS, reconnecting in 5s...');
            setIsConnected(false);
            setTimeout(connect, 5000);
        };

        ws.onerror = (error) => {
            console.error('Whale WS Error:', error);
            ws.close();
        };

        wsRef.current = ws;
    }, [url]);

    useEffect(() => {
        connect();
        return () => {
            wsRef.current?.close();
        };
    }, [connect]);

    // Used to set initial data fetched from REST API
    const setInitialTransactions = useCallback((initialData: WhaleTransaction[]) => {
        setTransactions(initialData);
    }, []);

    // Used to append historical data fetched via "Load More"
    const appendHistoricalTransactions = useCallback((historyData: WhaleTransaction[]) => {
        setTransactions((prev) => {
            // Filter out duplicates just in case
            const existingIds = new Set(prev.map(t => t.id));
            const newTxs = historyData.filter(t => !existingIds.has(t.id));
            // Append older data to the end
            return [...prev, ...newTxs].slice(0, 500);
        });
    }, []);

    return { transactions, isConnected, setInitialTransactions, appendHistoricalTransactions };
}
