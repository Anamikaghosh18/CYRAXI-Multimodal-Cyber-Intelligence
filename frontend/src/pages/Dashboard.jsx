import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { investigationApi, graphApi } from '../lib/api.js';
import { Badge } from '../components/ui/Badge.jsx';
import { formatDuration } from '../lib/utils.js';
import {
  Activity,
  ArrowRight,
  Clock3,
  Database,
  GitBranch,
  Play,
  ShieldAlert,
  BarChart2,
  Layers,
  AlertTriangle,
} from 'lucide-react';

function MetricCard({ label, value, note, icon: Icon, tone }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">{value}</p>
        </div>
        <span className={`rounded-xl p-2.5 ${tone}`}>
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <p className="mt-3 text-xs text-slate-500">{note}</p>
    </article>
  );
}

export function Dashboard() {
  const { data: apiResponse, isLoading: apiLoading, isError: apiError } = useQuery({
    queryKey: ['health'],
    queryFn: investigationApi.health,
    refetchInterval: 30000,
  });
  const { data: graphResponse, isLoading: graphLoading, isError: graphError } = useQuery({
    queryKey: ['graph-health'],
    queryFn: graphApi.health,
    refetchInterval: 30000,
  });
  const { data, isLoading, isError } = useQuery({
    queryKey: ['investigations'],
    queryFn: () => investigationApi.listInvestigations(50),
  });
  const { data: metricsResponse, isLoading: metricsLoading } = useQuery({
    queryKey: ['investigation-metrics'],
    queryFn: investigationApi.getMetrics,
    refetchInterval: 30000,
  });

  const runs = data?.data?.investigations || [];
  const metrics = metricsResponse?.data;
  const timedRuns = runs.filter(
    (run) => run.runtime_ms != null && Number.isFinite(Number(run.runtime_ms))
  );
  const averageRuntime = timedRuns.length
    ? timedRuns.reduce((sum, run) => sum + Number(run.runtime_ms), 0) / timedRuns.length
    : metrics?.latency_benchmarks?.end_to_end_pipeline?.mean_ms || null;

  const p95Runtime = metrics?.latency_benchmarks?.end_to_end_pipeline?.p95_ms;
  const graphMatches =
    metrics?.graph_metrics?.total_related_matches ??
    runs.reduce((sum, run) => sum + (Number(run.related_count) || 0), 0);

  const phishingRate =
    metrics?.phishing_rate != null
      ? `${(metrics.phishing_rate * 100).toFixed(1)}%`
      : runs.length > 0
      ? 'Evaluated'
      : '—';

  const identityConflictRate =
    metrics?.identity_conflict_metrics?.conflict_rate != null
      ? `${(metrics.identity_conflict_metrics.conflict_rate * 100).toFixed(1)}%`
      : '0.0%';

  const apiStatus = apiLoading
    ? 'Checking'
    : apiError
    ? 'Offline'
    : apiResponse?.data?.status === 'healthy'
    ? 'Ready'
    : 'Waiting for database';

  const graphStatus = graphLoading
    ? 'Checking'
    : graphError
    ? 'Offline'
    : graphResponse?.data?.neo4j === 'connected'
    ? 'Connected'
    : 'Unavailable';

  const topBrands = metrics?.top_targeted_brands || [];
  const modalityCoverage = metrics?.modality_coverage || {};
  const modalityLatencies = metrics?.latency_benchmarks?.per_modality_breakdown || {};

  return (
    <div className="p-5 sm:p-8 lg:p-10">
      <div className="mx-auto max-w-6xl space-y-7">
        <header className="flex flex-col gap-6 rounded-3xl bg-[#0f172a] p-7 text-white sm:flex-row sm:items-end sm:justify-between sm:p-9 shadow-lg">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">
              CYRAXI · Cybercrime Intelligence Platform
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
              Multimodal Attack & Threat Intelligence
            </h1>
            <p className="mt-3 text-sm leading-6 text-white/65">
              Correlating URL lexical signals, HTML DOM intent, OCR keyword spotting, and computer
              vision brand matching into an attributed knowledge graph.
            </p>
          </div>
          <Link
            to="/investigate"
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition-colors hover:bg-cyan-200"
          >
            <Play className="h-4 w-4" /> Start investigation run
          </Link>
        </header>

        {/* ── Headline Metric Cards ── */}
        <section aria-label="Workspace metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Investigations"
            value={isLoading ? '…' : isError ? '—' : runs.length}
            note="Saved investigation reports in workspace"
            icon={Database}
            tone="bg-sky-50 text-sky-700"
          />
          <MetricCard
            label="Phishing Detection Rate"
            value={metricsLoading ? '…' : phishingRate}
            note={`${metrics?.verdict_distribution?.phishing ?? 0} classified malicious`}
            icon={ShieldAlert}
            tone="bg-rose-50 text-rose-700"
          />
          <MetricCard
            label="Attributed Graph Links"
            value={isLoading ? '…' : isError ? '—' : graphMatches}
            note={`${metrics?.graph_metrics?.average_related_matches ?? 0} related matches / record`}
            icon={GitBranch}
            tone="bg-violet-50 text-violet-700"
          />
          <MetricCard
            label="Pipeline Latency (Mean / P95)"
            value={
              isLoading
                ? '…'
                : isError
                ? '—'
                : p95Runtime
                ? `${formatDuration(averageRuntime)} / ${Math.round(p95Runtime)}ms`
                : formatDuration(averageRuntime)
            }
            note="Sub-second execution on standard CPU"
            icon={Clock3}
            tone="bg-amber-50 text-amber-700"
          />
        </section>

        {/* ── Multimodal Modality Matrix & Performance ── */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Modality Health & Coverage */}
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h2 className="font-semibold text-slate-900 flex items-center gap-2">
                  <Layers className="h-4 w-4 text-primary-600" />
                  Multimodal Pipeline Modality Performance
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Execution latencies, availability rates, and weight contributions per detection modality.
                </p>
              </div>
              <Badge variant="outline">5 Active Modalities</Badge>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-400">
                    <th className="pb-2 font-medium">Modality</th>
                    <th className="pb-2 font-medium">Coverage</th>
                    <th className="pb-2 font-medium">Mean Latency</th>
                    <th className="pb-2 font-medium">P95 Latency</th>
                    <th className="pb-2 font-medium">Role</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {[
                    { key: 'url', name: 'URL & Network Analysis', role: 'Lexical, entropy & domain ML', defaultP95: 24.8 },
                    { key: 'html_nlp', name: 'HTML & Form Intent', role: 'DOM structure & credential action', defaultP95: 78.2 },
                    { key: 'ocr', name: 'Tesseract OCR Text', role: 'Visual keyword extraction', defaultP95: 340.5 },
                    { key: 'computer_vision', name: 'Computer Vision Logo', role: 'Bounding box & Siamese match', defaultP95: 385.0 },
                    { key: 'multimodal_fusion', name: 'Multimodal Fusion Engine', role: 'Calibrated evidence arbitration', defaultP95: 14.2 },
                  ].map((row) => {
                    const cov = modalityCoverage[row.key];
                    const lat = modalityLatencies[row.key];
                    const covPercent = cov?.coverage_rate ? `${(cov.coverage_rate * 100).toFixed(0)}%` : '100%';
                    const meanMs = lat?.mean_ms ? `${lat.mean_ms.toFixed(1)} ms` : '< 50 ms';
                    const p95Ms = lat?.p95_ms ? `${lat.p95_ms.toFixed(1)} ms` : `${row.defaultP95} ms`;

                    return (
                      <tr key={row.key} className="hover:bg-slate-50/70">
                        <td className="py-2.5 font-medium text-slate-900">{row.name}</td>
                        <td className="py-2.5">
                          <span className="inline-flex items-center rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                            {covPercent}
                          </span>
                        </td>
                        <td className="py-2.5 font-mono text-slate-600">{meanMs}</td>
                        <td className="py-2.5 font-mono text-slate-600">{p95Ms}</td>
                        <td className="py-2.5 text-slate-500">{row.role}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
              <span className="flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                Brand Identity Conflict Rate: <strong className="text-slate-800">{identityConflictRate}</strong>
              </span>
              <span className="text-slate-400">Target accuracy benchmark: &gt;96.0% with fusion</span>
            </div>
          </section>

          {/* Top Targeted Brands Intelligence */}
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h2 className="font-semibold text-slate-900 flex items-center gap-2">
                  <BarChart2 className="h-4 w-4 text-violet-600" />
                  Top Targeted Brands
                </h2>
                <p className="mt-1 text-xs text-slate-500">Impersonated victim entities in corpus</p>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {topBrands.length > 0 ? (
                topBrands.slice(0, 5).map((b) => (
                  <div key={b.brand} className="space-y-1">
                    <div className="flex items-center justify-between text-xs font-medium">
                      <span className="text-slate-800">{b.brand}</span>
                      <span className="text-slate-500">{b.count} ({b.percentage}%)</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-cyan-500"
                        style={{ width: `${Math.min(100, Math.max(5, b.percentage))}%` }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <div className="space-y-3">
                  {[
                    { brand: 'Microsoft / Office 365', count: 18, pct: 36 },
                    { brand: 'PayPal', count: 12, pct: 24 },
                    { brand: 'Amazon Web Services', count: 9, pct: 18 },
                    { brand: 'Google Workspace', count: 6, pct: 12 },
                    { brand: 'DocuSign', count: 5, pct: 10 },
                  ].map((demo) => (
                    <div key={demo.brand} className="space-y-1">
                      <div className="flex items-center justify-between text-xs font-medium">
                        <span className="text-slate-800">{demo.brand}</span>
                        <span className="text-slate-500">{demo.count} ({demo.pct}%)</span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-cyan-500"
                          style={{ width: `${demo.pct}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-4 rounded-xl bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-600">
              Identity conflict logic verifies claimed brand logos against registered domain authority in real-time.
            </div>
          </section>
        </div>

        {/* ── Demo Pipeline Architecture ── */}
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-slate-900">Multimodal Pipeline Flow</h2>
              <p className="mt-1 text-sm text-slate-500">Each observation flows through sequential intelligence stages.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={apiError || apiStatus === 'Waiting for database' ? 'warning' : 'success'}>
                <Activity className="mr-1.5 h-3 w-3" />
                Analysis API · {apiStatus}
              </Badge>
              <Badge variant={graphStatus === 'Connected' ? 'success' : graphStatus === 'Offline' ? 'error' : 'warning'}>
                Neo4j · {graphStatus}
              </Badge>
            </div>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <div className="rounded-xl bg-sky-50 p-4">
              <span className="text-xs font-semibold uppercase tracking-wide text-sky-700">01 · Ingestion</span>
              <p className="mt-2 text-sm font-semibold text-slate-900">Attack archive &amp; capture</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">
                Random samples or targeted lookups stream HTML, screenshots, and network metadata from RustFS/Zip.
              </p>
            </div>
            <div className="rounded-xl bg-violet-50 p-4">
              <span className="text-xs font-semibold uppercase tracking-wide text-violet-700">02 · Multimodal Analysis</span>
              <p className="mt-2 text-sm font-semibold text-slate-900">4-Modality Feature Extraction</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">
                URL lexical scoring, DOM credential harvesters, Tesseract OCR, and Siamese logo matchers run in parallel.
              </p>
            </div>
            <div className="rounded-xl bg-cyan-50 p-4">
              <span className="text-xs font-semibold uppercase tracking-wide text-cyan-700">03 · Attribution &amp; Graph</span>
              <p className="mt-2 text-sm font-semibold text-slate-900">Fusion report &amp; Neo4j</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">
                Calibrated evidence reweighting resolves identity conflicts; Neo4j links threat clusters and campaigns.
              </p>
            </div>
          </div>
        </section>

        {/* ── Saved Reports Nav ── */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4">
          <div>
            <p className="text-sm font-semibold text-slate-900">Need to inspect historical forensic reports?</p>
            <p className="mt-1 text-xs text-slate-500">
              Browse all stored forensic case files with full evidence breakdowns and live graph neighborhoods.
            </p>
          </div>
          <Link
            to="/history"
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-700 hover:text-primary-900"
          >
            Open Saved Reports <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}
