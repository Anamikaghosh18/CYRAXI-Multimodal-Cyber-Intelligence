import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { investigationApi } from '../lib/api.js';
import { Badge } from '../components/ui/Badge.jsx';
import { formatDate, truncateId, defangUrl } from '../lib/utils.js';
import { Search, Loader2, ArrowRight } from 'lucide-react';

export function InvestigationHistory() {
  const [search, setSearch] = useState('');
  const { data, isLoading, error } = useQuery({
    queryKey: ['investigations'],
    queryFn: () => investigationApi.listInvestigations(100),
  });
  const allInvestigations = data?.data?.investigations || [];
  const filteredInvestigations = allInvestigations.filter((inv) => {
    const value = search.toLowerCase();
    return !value || (inv.observation_id || '').toLowerCase().includes(value) ||
      (inv.input_value || '').toLowerCase().includes(value);
  });

  return (
    <div className="p-8"><div className="max-w-7xl mx-auto">
      <div className="mb-8"><h1 className="text-2xl font-semibold text-neutral-900">Saved reports</h1><p className="text-neutral-600 mt-1">Open a previous analysis to review its evidence and graph links.</p></div>
      <div className="bg-white rounded-lg border border-neutral-200 p-4 mb-6"><div className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by observation ID or URL..." className="w-full pl-10 pr-4 py-2 border border-neutral-300 rounded-lg" /></div></div>
      {isLoading ? <div className="bg-white rounded-lg border p-6 flex justify-center"><Loader2 className="w-6 h-6 animate-spin" /></div> : error ? <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-red-700">Could not load saved reports: {error.message}</div> : filteredInvestigations.length === 0 ? <div className="bg-white rounded-lg border p-6 text-center text-neutral-500">{search ? <p>No reports match “{search}”</p> : <><p className="mb-4">No saved reports yet</p><Link to="/investigate" className="text-primary-600 hover:text-primary-700 font-medium">Start an investigation</Link></>}</div> : <div className="bg-white rounded-lg border border-neutral-200"><div className="px-6 py-4 border-b"><h2 className="text-lg font-semibold">Reports ({filteredInvestigations.length})</h2></div><div className="divide-y">{filteredInvestigations.map((inv) => <Link key={inv.investigation_id} to={`/report/${inv.investigation_id}`} className="block px-6 py-4 hover:bg-neutral-50"><div className="flex items-center justify-between"><div className="flex-1 min-w-0"><div className="flex items-center gap-3 mb-1"><code className="text-sm font-mono text-neutral-600">{inv.input_type === 'url' ? defangUrl(inv.input_value) : truncateId(inv.observation_id)}</code><Badge variant={inv.status === 'success' ? 'success' : 'warning'}>{inv.status === 'success' ? 'Report saved' : 'Needs review'}</Badge></div><p className="text-sm text-neutral-500">{formatDate(inv.created_at)} · {inv.related_count ?? 0} related observations</p></div><ArrowRight className="w-4 h-4 text-neutral-400" /></div></Link>)}</div></div>}
    </div></div>
  );
}
