import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { investigationApi, graphApi } from '../lib/api.js';
import { Badge } from '../components/ui/Badge.jsx';
import { formatDuration } from '../lib/utils.js';
import { Activity, ArrowRight, Clock3, Database, GitBranch, Play, ShieldCheck } from 'lucide-react';

function MetricCard({ label, value, note, icon: Icon, tone }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div><p className="text-sm font-medium text-slate-500">{label}</p><p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">{value}</p></div>
        <span className={`rounded-xl p-2.5 ${tone}`}><Icon className="h-5 w-5" /></span>
      </div>
      <p className="mt-3 text-xs text-slate-500">{note}</p>
    </article>
  );
}

export function Dashboard() {
  const { data: apiResponse, isLoading: apiLoading, isError: apiError } = useQuery({
    queryKey: ['health'], queryFn: investigationApi.health, refetchInterval: 30000,
  });
  const { data: graphResponse, isLoading: graphLoading, isError: graphError } = useQuery({
    queryKey: ['graph-health'], queryFn: graphApi.health, refetchInterval: 30000,
  });
  const { data, isLoading, isError } = useQuery({
    queryKey: ['investigations'], queryFn: () => investigationApi.listInvestigations(50),
  });

  const runs = data?.data?.investigations || [];
  const successful = runs.filter((run) => run.status === 'success').length;
  const timedRuns = runs.filter((run) => run.runtime_ms != null && Number.isFinite(Number(run.runtime_ms)));
  const averageRuntime = timedRuns.length
    ? timedRuns.reduce((sum, run) => sum + Number(run.runtime_ms), 0) / timedRuns.length
    : null;
  const graphMatches = runs.reduce((sum, run) => sum + (Number(run.related_count) || 0), 0);
  const apiStatus = apiLoading ? 'Checking' : apiError ? 'Offline' : apiResponse?.data?.status === 'healthy' ? 'Ready' : 'Waiting for database';
  const graphStatus = graphLoading ? 'Checking' : graphError ? 'Offline' : graphResponse?.data?.neo4j === 'connected' ? 'Connected' : 'Unavailable';

  return (
    <div className="p-5 sm:p-8 lg:p-10">
      <div className="mx-auto max-w-6xl space-y-7">
        <header className="flex flex-col gap-6 rounded-3xl bg-[#0f172a] p-7 text-white sm:flex-row sm:items-end sm:justify-between sm:p-9">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">CYRAXI · Demo workbench</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Archive-to-investigation demo</h1>
            <p className="mt-3 text-sm leading-6 text-white/65">Show how archived attack records move through automated analysis and into a connected graph report.</p>
          </div>
          <Link to="/investigate" className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-200"><Play className="h-4 w-4" /> Start demo run</Link>
        </header>

        <section aria-label="Workspace metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Reports in workspace" value={isLoading ? '…' : isError ? '—' : runs.length} note="Up to 50 saved reports loaded" icon={Database} tone="bg-sky-50 text-sky-700" />
          <MetricCard label="Completed reports" value={isLoading ? '…' : isError ? '—' : `${successful} / ${runs.length}`} note="Report completion, not detection accuracy" icon={ShieldCheck} tone="bg-emerald-50 text-emerald-700" />
          <MetricCard label="Graph matches" value={isLoading ? '…' : isError ? '—' : graphMatches} note="Related observations across these reports" icon={GitBranch} tone="bg-violet-50 text-violet-700" />
          <MetricCard label="Average runtime" value={isLoading ? '…' : isError ? '—' : formatDuration(averageRuntime)} note="Across reports with timing data" icon={Clock3} tone="bg-amber-50 text-amber-700" />
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="font-semibold text-slate-900">Demo pipeline</h2><p className="mt-1 text-sm text-slate-500">One run automatically moves through these stages.</p></div>
            <div className="flex flex-wrap gap-2"><Badge variant={apiError || apiStatus === 'Waiting for database' ? 'warning' : 'success'}><Activity className="mr-1.5 h-3 w-3" />Analysis API · {apiStatus}</Badge><Badge variant={graphStatus === 'Connected' ? 'success' : graphStatus === 'Offline' ? 'error' : 'warning'}>Neo4j · {graphStatus}</Badge></div>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <div className="rounded-xl bg-sky-50 p-4"><span className="text-xs font-semibold uppercase tracking-wide text-sky-700">01 · Source</span><p className="mt-2 text-sm font-semibold text-slate-900">Attack archive</p><p className="mt-1 text-xs leading-5 text-slate-600">Choose a random sample or select indexed records from Neo4j; local files provide capture evidence.</p></div>
            <div className="rounded-xl bg-violet-50 p-4"><span className="text-xs font-semibold uppercase tracking-wide text-violet-700">02 · Analysis</span><p className="mt-2 text-sm font-semibold text-slate-900">Evidence modules</p><p className="mt-1 text-xs leading-5 text-slate-600">URL, page structure, OCR, visual checks, and baseline evidence fusion run automatically.</p></div>
            <div className="rounded-xl bg-cyan-50 p-4"><span className="text-xs font-semibold uppercase tracking-wide text-cyan-700">03 · Output</span><p className="mt-2 text-sm font-semibold text-slate-900">Report and graph</p><p className="mt-1 text-xs leading-5 text-slate-600">Each record gets a report with findings, warnings, and its connected graph in the same view.</p></div>
          </div>
        </section>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4">
          <div><p className="text-sm font-semibold text-slate-900">Need to review a previous run?</p><p className="mt-1 text-xs text-slate-500">Saved Reports contains the report list; this workbench summarizes workspace activity.</p></div>
          <Link to="/history" className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-700 hover:text-primary-900">Open Saved Reports <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </div>
    </div>
  );
}
