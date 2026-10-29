import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { archiveApi } from '../lib/api.js';
import { Badge } from '../components/ui/Badge.jsx';
import { formatDate, formatDuration, truncateId } from '../lib/utils.js';
import { AlertCircle, ArrowRight, ChevronLeft, ChevronRight, Loader2, Play, Search, Shuffle } from 'lucide-react';

const PAGE_SIZE = 25;
const MODULE_LABELS = { url: 'URL', html_nlp: 'HTML', ocr: 'OCR', computer_vision: 'Visual', multimodal_fusion: 'Fusion' };

export function NewInvestigation() {
  const [mode, setMode] = useState('random');
  const [count, setCount] = useState(3);
  const [relatedLimit, setRelatedLimit] = useState(10);
  const [offset, setOffset] = useState(0);
  const [searchDraft, setSearchDraft] = useState('');
  const [search, setSearch] = useState('');
  const [selectedIds, setSelectedIds] = useState([]);
  const [experimentResult, setExperimentResult] = useState(null);
  const [error, setError] = useState('');

  const archiveQuery = useQuery({
    queryKey: ['archive-observations', search, offset],
    queryFn: () => archiveApi.listObservations({ limit: PAGE_SIZE, offset, search }),
    enabled: mode === 'selected',
    staleTime: 60000,
  });
  const runMutation = useMutation({
    mutationFn: archiveApi.runExperiment,
    onSuccess: (response) => { setExperimentResult(response.data); setError(''); },
    onError: (requestError) => setError(requestError.response?.data?.detail || requestError.message || 'The run failed.'),
  });

  const observations = archiveQuery.data?.data?.observations || [];
  const hasMore = archiveQuery.data?.data?.has_more || false;
  const results = experimentResult?.results || [];

  function toggleSelection(observationId) {
    setSelectedIds((current) => current.includes(observationId)
      ? current.filter((id) => id !== observationId)
      : [...current, observationId]);
  }

  function startRun() {
    setExperimentResult(null);
    setError('');
    runMutation.mutate(mode === 'random'
      ? { mode: 'random', count, limit_related: relatedLimit }
      : { mode: 'selected', observation_ids: selectedIds, count: selectedIds.length, limit_related: relatedLimit });
  }

  function searchArchive(event) {
    event.preventDefault();
    setOffset(0);
    setSelectedIds([]);
    setSearch(searchDraft.trim());
  }

  return (
    <div className="p-5 sm:p-8 lg:p-10">
      <div className="mx-auto max-w-5xl space-y-6">
        <header>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary-700">New investigation</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-neutral-950 sm:text-3xl">Choose attacks to analyze</h1>
          <p className="mt-2 text-sm text-neutral-600">Records come from Neo4j. CYRAXI checks the local archive for available evidence and runs the analysis automatically.</p>
        </header>

        <section className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="font-semibold text-neutral-900">Select records</h2><p className="mt-1 text-sm text-neutral-500">Random sample is the quickest way to start.</p></div>
            <Badge variant={mode === 'random' ? 'info' : 'success'}>{mode === 'random' ? `${count} random records` : `${selectedIds.length} selected`}</Badge>
          </div>

          <div className="mt-5 inline-flex rounded-xl bg-neutral-100 p-1">
            <button type="button" onClick={() => setMode('random')} className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${mode === 'random' ? 'bg-white text-neutral-900 shadow-sm' : 'text-neutral-600 hover:text-neutral-900'}`}><Shuffle className="h-4 w-4" /> Random sample</button>
            <button type="button" onClick={() => setMode('selected')} className={`rounded-lg px-4 py-2 text-sm font-medium transition ${mode === 'selected' ? 'bg-white text-neutral-900 shadow-sm' : 'text-neutral-600 hover:text-neutral-900'}`}>Choose records</button>
          </div>

          {mode === 'random' ? (
            <div className="mt-5 max-w-xs">
              <label className="block text-sm font-medium text-neutral-700">Sample size<select value={count} onChange={(event) => setCount(Number(event.target.value))} className="mt-2 w-full rounded-lg border border-neutral-300 bg-white px-3 py-2.5 text-sm text-neutral-900">{[1, 3, 5, 10, 20].map((value) => <option key={value} value={value}>{value} record{value === 1 ? '' : 's'}</option>)}</select></label>
            </div>
          ) : (
            <div className="mt-5">
              <form onSubmit={searchArchive} className="mb-3 flex gap-2">
                <div className="relative min-w-0 flex-1"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" /><input value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} placeholder="Search brand, domain, or observation ID" className="w-full rounded-lg border border-neutral-300 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100" /></div>
                <button className="rounded-lg bg-neutral-800 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700">Search</button>
              </form>
              <div className="overflow-hidden rounded-xl border border-neutral-200">
                {archiveQuery.isLoading ? <div className="flex justify-center p-8"><Loader2 className="h-5 w-5 animate-spin text-primary-700" /></div> : archiveQuery.error ? <div className="p-4 text-sm text-red-700">Could not load records: {archiveQuery.error.response?.data?.detail || archiveQuery.error.message}</div> : observations.length === 0 ? <div className="p-6 text-center text-sm text-neutral-500">No records found. Check your search or database connection.</div> : <div className="divide-y divide-neutral-100">{observations.map((observation) => {
                  const checked = selectedIds.includes(observation.observation_id);
                  return <label key={observation.observation_id} className={`flex cursor-pointer items-start gap-3 p-3.5 transition hover:bg-neutral-50 ${checked ? 'bg-primary-50/60' : ''}`}>
                    <input type="checkbox" checked={checked} disabled={!checked && selectedIds.length >= 20} onChange={() => toggleSelection(observation.observation_id)} className="mt-1 h-4 w-4 rounded border-neutral-300 accent-primary-700" />
                    <span className="min-w-0 flex-1"><span className="flex flex-wrap items-center gap-2"><strong className="text-sm text-neutral-800">{observation.target_brand || 'Unlabeled attack'}</strong><span className="text-xs text-neutral-500">{observation.domain || 'Domain unavailable'}</span></span><code className="mt-1 block truncate text-[10px] text-neutral-500">{observation.observation_id}</code><span className="mt-1 block text-[11px] text-neutral-400">Captured {formatDate(observation.captured_at)}</span></span>
                  </label>;
                })}</div>}
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-neutral-500"><span>{selectedIds.length} selected · maximum 20</span><span className="flex gap-2"><button type="button" aria-label="Previous page" disabled={offset === 0 || archiveQuery.isLoading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="rounded-md border border-neutral-200 p-1.5 disabled:opacity-40"><ChevronLeft className="h-3.5 w-3.5" /></button><button type="button" aria-label="Next page" disabled={!hasMore || archiveQuery.isLoading} onClick={() => setOffset(offset + PAGE_SIZE)} className="rounded-md border border-neutral-200 p-1.5 disabled:opacity-40"><ChevronRight className="h-3.5 w-3.5" /></button></span></div>
            </div>
          )}

          <details className="mt-5 border-t border-neutral-100 pt-4">
            <summary className="cursor-pointer text-sm font-medium text-neutral-600">Advanced options</summary>
            <label className="mt-3 block max-w-xs text-sm text-neutral-600">Maximum related graph matches<select value={relatedLimit} onChange={(event) => setRelatedLimit(Number(event.target.value))} className="mt-2 w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm">{[5, 10, 15, 25, 50].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          </details>

          <div className="mt-5 border-t border-neutral-100 pt-5">
            <button type="button" onClick={startRun} disabled={runMutation.isPending || (mode === 'selected' && selectedIds.length === 0)} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary-700 px-4 py-3.5 text-sm font-semibold text-white transition hover:bg-primary-800 disabled:cursor-not-allowed disabled:bg-neutral-300 sm:w-auto sm:min-w-56">
              {runMutation.isPending ? <><Loader2 className="h-4 w-4 animate-spin" />Running analysis…</> : <><Play className="h-4 w-4" />Run analysis</>}
            </button>
            {runMutation.isPending && <span className="ml-0 mt-2 block text-xs text-neutral-500 sm:ml-3 sm:mt-0 sm:inline">Reports are saved as each record finishes.</span>}
            {error && <div className="mt-3 flex gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div>}
          </div>
        </section>

        {experimentResult && <section className="overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral-100 px-5 py-5 sm:px-6"><div><h2 className="font-semibold text-neutral-900">Run results</h2><p className="mt-1 text-sm text-neutral-500">{experimentResult.completed_count} of {experimentResult.requested_count} records analyzed</p></div><Badge variant={experimentResult.completed_count ? 'success' : 'warning'}>{experimentResult.mode === 'random' ? 'Random sample' : 'Selected records'}</Badge></div>
          {experimentResult.missing_observation_ids?.length > 0 && <div className="border-b border-amber-200 bg-amber-50 px-5 py-3 text-xs text-amber-800">{experimentResult.missing_observation_ids.length} selected IDs were not found in Neo4j.</div>}
          {results.length === 0 ? <div className="p-8 text-center text-sm text-neutral-500">No records completed.</div> : <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="bg-neutral-50 text-[10px] uppercase tracking-wider text-neutral-500"><tr><th className="px-5 py-3">Attack</th><th className="px-4 py-3">Analysis status</th><th className="px-4 py-3">Graph matches</th><th className="px-4 py-3">Runtime</th><th className="px-5 py-3">Report</th></tr></thead><tbody className="divide-y divide-neutral-100">{results.map((result) => <tr key={result.investigation_id || result.observation_id} className="align-top hover:bg-neutral-50/70"><td className="px-5 py-4"><p className="font-semibold text-neutral-800">{result.target_brand || 'Unlabeled attack'}</p><p className="mt-1 text-neutral-500">{result.domain || 'Domain unavailable'}</p><code className="mt-1 block text-[10px] text-neutral-400">{truncateId(result.observation_id, 32)}</code></td><td className="px-4 py-4"><div className="flex flex-wrap gap-1">{Object.entries(result.module_statuses || {}).map(([key, status]) => <span key={key} className={`rounded-md px-1.5 py-1 text-[10px] font-medium ${status === 'success' ? 'bg-primary-50 text-primary-800' : status === 'partial' ? 'bg-amber-50 text-amber-800' : 'bg-neutral-100 text-neutral-500'}`}>{MODULE_LABELS[key] || key}: {status || 'not run'}</span>)}</div><p className="mt-2 text-[10px] text-neutral-500">Graph: {result.graph_status || 'not recorded'} · {result.warning_count} warnings</p></td><td className="px-4 py-4 text-neutral-700">{result.related_count ?? '—'}</td><td className="px-4 py-4 text-neutral-700">{formatDuration(result.runtime_ms)}</td><td className="px-5 py-4">{result.investigation_id ? <Link to={`/report/${result.investigation_id}`} className="inline-flex items-center gap-1.5 font-semibold text-primary-700 hover:text-primary-900">Open report <ArrowRight className="h-3.5 w-3.5" /></Link> : <span className="text-red-700">Run failed: {result.error}</span>}<p className="mt-1 text-[10px] text-neutral-400">{result.created_at ? formatDate(result.created_at) : ''}</p></td></tr>)}</tbody></table></div>}
        </section>}
      </div>
    </div>
  );
}
