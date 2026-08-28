import React, { useEffect, useState, useCallback } from 'react';
import { API_URL } from '@/lib/utils';
import { Network } from 'lucide-react';
import dagre from 'dagre';
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  addEdge,
  Background,
  Controls,
  MarkerType
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { formatUsd } from './constants';

interface VisualizerTabProps {
  transactions: any[];
  setInspectTx: (tx: any) => void;
  chainFilter: string;
}

export const VisualizerTab: React.FC<VisualizerTabProps> = ({ transactions, setInspectTx, chainFilter }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchGraph = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_URL}/api/whale/graph?chain=${chainFilter}&limit=100`);
        const data = await res.json();
        
        const mappedNodes = data.nodes.map((node: any) => {
          let bgColor = '#1e293b';
          let borderColor = '#334155';
          if (node.data.type === 'exchange') {
            bgColor = '#f59e0b20';
            borderColor = '#f59e0b';
          } else if (node.data.win_rate > 65) {
            bgColor = '#eab30820'; // gold for smart money
            borderColor = '#eab308';
          }

          return {
            id: node.id,
            position: { x: 0, y: 0 }, // Will be set by dagre
            data: { 
              label: (
                <div className="flex flex-col items-center">
                  <div className="font-bold text-xs">{node.data.label}</div>
                  {node.data.win_rate > 65 && (
                    <div className="text-[9px] text-yellow-400 mt-1 flex items-center gap-1">
                      ⭐ Smart Money
                    </div>
                  )}
                  {node.data.pnl !== 0 && (
                    <div className={`text-[9px] ${node.data.pnl > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      PnL: {node.data.pnl > 0 ? '+' : ''}{formatUsd(node.data.pnl)}
                    </div>
                  )}
                </div>
              )
            },
            style: {
              background: bgColor,
              color: '#f8fafc',
              border: `1px solid ${borderColor}`,
              borderRadius: '8px',
              padding: '10px',
              width: 150,
            }
          };
        });

        const mappedEdges = data.edges.map((edge: any) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          animated: edge.animated,
          label: `${formatUsd(edge.data.usd_value)} ${edge.data.token}`,
          style: { stroke: '#06b6d4', strokeWidth: Math.max(1, Math.min(5, edge.data.usd_value / 1000000)) },
          labelStyle: { fill: '#94a3b8', fontSize: 10, fontWeight: 700 },
          labelBgStyle: { fill: '#0f172a', color: '#fff', fillOpacity: 0.8 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 20,
            height: 20,
            color: '#06b6d4',
          },
        }));

        // Apply Dagre layout
        const dagreGraph = new dagre.graphlib.Graph();
        dagreGraph.setDefaultEdgeLabel(() => ({}));
        dagreGraph.setGraph({ rankdir: 'LR', ranksep: 200, nodesep: 50 }); // Left-to-Right layout

        mappedNodes.forEach((node: any) => {
          dagreGraph.setNode(node.id, { width: 150, height: 60 });
        });

        mappedEdges.forEach((edge: any) => {
          dagreGraph.setEdge(edge.source, edge.target);
        });

        dagre.layout(dagreGraph);

        const layoutedNodes = mappedNodes.map((node: any) => {
          const nodeWithPosition = dagreGraph.node(node.id);
          node.position = {
            x: nodeWithPosition.x - 75, // subtract half width
            y: nodeWithPosition.y - 30, // subtract half height
          };
          return node;
        });

        setNodes(layoutedNodes);
        setEdges(mappedEdges);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchGraph();
  }, [chainFilter]);

  return (
    <div className="p-6 rounded-2xl border border-slate-800/80 bg-[#0d111a] shadow-2xl space-y-4">
      <div>
        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
          <Network className="w-5 h-5 text-cyan-400" />
          Whale Money Flow Network
        </h3>
        <p className="text-xs text-slate-400">
          Interactive graph showing the movement of funds between entities. Highlighted nodes indicate Smart Money.
        </p>
      </div>

      <div className="relative h-[600px] w-full rounded-xl border border-slate-800/80 overflow-hidden bg-slate-950">
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center text-cyan-400 animate-pulse">
            Loading Network Graph...
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            fitView
            colorMode="dark"
          >
            <Background color="#1e293b" gap={16} />
            <Controls />
          </ReactFlow>
        )}
      </div>
    </div>
  );
};
