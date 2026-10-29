import { useMemo, useState } from 'react';
import { Badge } from './ui/Badge.jsx';

const NODE_COLORS = {
  Observation: '#f97316', URL: '#0ea5e9', Domain: '#14b8a6', IPAddress: '#8b5cf6',
  AutonomousSystem: '#64748b', Brand: '#ec4899', CampaignCandidate: '#f59e0b',
  WebPageCapture: '#84cc16', ModelRun: '#6366f1', Prediction: '#ef4444', EvidenceItem: '#06b6d4',
};

function nodeTitle(node) {
  const properties = node.properties || {};
  return properties.name || properties.raw_url || properties.ip || properties.observation_id ||
    properties.family_id || properties.model_name || properties.verdict || node.labels?.[0] || 'Node';
}

export function ObservationGraph({ graph, observationId, isLoading, error }) {
  const [selectedId, setSelectedId] = useState(null);
  const nodes = graph?.nodes || [];
  const root = nodes.find((node) => node.properties?.observation_id === observationId) || nodes[0];
  const visibleNodes = useMemo(() => root ? [root, ...nodes.filter((node) => node.id !== root.id).slice(0, 24)] : [], [nodes, root]);
  const positions = useMemo(() => {
    const result = new Map();
    if (!root) return result;
    result.set(root.id, { x: 510, y: 290 });
    const others = visibleNodes.filter((node) => node.id !== root.id);
    others.forEach((node, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(others.length, 1) - Math.PI / 2;
      result.set(node.id, { x: 510 + 320 * Math.cos(angle), y: 290 + 205 * Math.sin(angle) });
    });
    return result;
  }, [visibleNodes, root]);
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const edges = (graph?.edges || []).filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
  const selected = nodes.find((node) => node.id === selectedId) || root;

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4 sm:px-6">
        <div><h2 className="font-semibold text-slate-900">Connected entities</h2><p className="mt-1 text-xs text-slate-500">Select a node to inspect its details. {graph ? `${visibleNodes.length} nodes · ${edges.length} links · 2 hops` : ''}</p></div>
        <div className="flex flex-wrap gap-2">{[...new Set(visibleNodes.flatMap((node) => node.labels || []))].map((label) => <span key={label} className="inline-flex items-center gap-1.5 rounded-full bg-slate-50 px-2.5 py-1 text-[10px] text-slate-600"><i className="h-2 w-2 rounded-full" style={{ backgroundColor: NODE_COLORS[label] || '#94a3b8' }} />{label}</span>)}</div>
      </div>

      {isLoading ? <div className="p-12 text-center text-sm text-slate-500">Loading this record’s graph…</div> : error ? <div className="p-8 text-sm text-rose-700">Could not load the graph: {error.message}</div> : nodes.length === 0 ? <div className="p-10 text-center"><p className="font-medium text-slate-800">No linked graph entities yet</p><p className="mt-1 text-sm text-slate-500">Run analysis to add this record and its available links to Neo4j.</p></div> : (
        <div className="grid xl:grid-cols-[minmax(0,1fr)_260px]">
          <div className="overflow-x-auto bg-[#f7f9fc]">
            <svg viewBox="0 0 1020 580" className="min-w-[700px] w-full" role="img" aria-label="Graph of entities connected to this attack record">
              {edges.map((edge) => {
                const a = positions.get(edge.source); const b = positions.get(edge.target);
                if (!a || !b) return null;
                const mx = (a.x + b.x) / 2; const my = (a.y + b.y) / 2;
                return <g key={edge.id}>
                  <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#b9c6d8" strokeWidth="2" />
                  <rect x={mx - 42} y={my - 13} width="84" height="18" rx="9" fill="white" stroke="#e2e8f0" />
                  <text x={mx} y={my} textAnchor="middle" fill="#64748b" fontSize="8" fontWeight="600">{edge.type}</text>
                </g>;
              })}
              {visibleNodes.map((node) => {
                const point = positions.get(node.id); const label = node.labels?.[0] || 'Node';
                const isRoot = node.id === root?.id; const title = String(nodeTitle(node));
                const shortTitle = title.length > 25 ? `${title.slice(0, 23)}…` : title;
                return <g key={node.id} onClick={() => setSelectedId(node.id)} className="cursor-pointer">
                  {isRoot && <circle cx={point.x} cy={point.y} r="47" fill="none" stroke="#fdba74" strokeWidth="3" />}
                  <circle cx={point.x} cy={point.y} r={isRoot ? 39 : 31} fill={NODE_COLORS[label] || '#64748b'} stroke={selected?.id === node.id ? '#0f172a' : 'white'} strokeWidth={selected?.id === node.id ? 4 : 2} />
                  <text x={point.x} y={point.y + 3} textAnchor="middle" fill="white" fontSize="10" fontWeight="700">{label === 'Observation' ? 'ATTACK' : label.length > 10 ? label.slice(0, 9) : label}</text>
                  <text x={point.x} y={point.y + (isRoot ? 53 : 46)} textAnchor="middle" fill="#334155" fontSize="10" fontWeight={isRoot ? '700' : '500'}>{shortTitle}</text>
                </g>;
              })}
            </svg>
          </div>
          <aside className="border-t border-slate-100 p-5 xl:border-l xl:border-t-0">
            <h3 className="text-sm font-semibold text-slate-800">Node details</h3>
            {selected ? <>
              <div className="mt-3"><Badge variant="info">{selected.labels?.join(' · ') || 'Node'}</Badge></div>
              <p className="mt-3 break-all text-sm font-medium text-slate-800">{nodeTitle(selected)}</p>
              <dl className="mt-4 space-y-3">{Object.entries(selected.properties || {}).slice(0, 8).map(([key, value]) => <div key={key}><dt className="text-[10px] uppercase tracking-wide text-slate-400">{key.replaceAll('_', ' ')}</dt><dd className="mt-0.5 break-all text-xs text-slate-700">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>)}</dl>
            </> : <p className="mt-2 text-sm text-slate-500">Select a node to inspect it.</p>}
          </aside>
        </div>
      )}
    </section>
  );
}
