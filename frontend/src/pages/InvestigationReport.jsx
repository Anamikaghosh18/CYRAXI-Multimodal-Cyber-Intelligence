import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { graphApi, investigationApi } from '../lib/api.js';
import { Badge } from '../components/ui/Badge.jsx';
import { ObservationGraph } from '../components/ObservationGraph.jsx';
import { formatDate, formatDuration, defangUrl, truncateId } from '../lib/utils.js';
import {
  AlertTriangle,
  Clock,
  Globe,
  Network,
  FileText,
  Image,
  ArrowLeft,
  Loader2
} from 'lucide-react';

function EvidencePanel({ title, status, children }) {
  const variant = status === 'success' ? 'success' : status === 'partial' ? 'warning' : 'neutral';
  return (
    <article className="rounded-xl border border-neutral-200 bg-white p-4">
      <div className="mb-4 flex items-center justify-between gap-2"><h3 className="text-sm font-semibold text-neutral-900">{title}</h3><Badge variant={variant}>{status || 'not run'}</Badge></div>
      <div className="space-y-2.5">{children}</div>
    </article>
  );
}

function DataPoint({ label, value }) {
  return <div className="flex items-start justify-between gap-3 border-b border-neutral-100 pb-2 last:border-0 last:pb-0"><span className="text-xs text-neutral-500">{label}</span><span className="max-w-[65%] text-right text-xs font-medium text-neutral-800">{value ?? 'Not available'}</span></div>;
}

function SignalChips({ items, empty }) {
  if (!items?.length) return <p className="pt-1 text-xs text-neutral-400">{empty}</p>;
  return <div className="flex flex-wrap gap-1.5 pt-1">{items.map((item) => <span key={item} className="rounded-md border border-accent-200 bg-accent-50 px-2 py-1 text-[10px] font-medium text-neutral-800">{item}</span>)}</div>;
}

export function InvestigationReport() {
  const { id } = useParams();

  const { data: report, isLoading, error } = useQuery({
    queryKey: ['investigation', id],
    queryFn: () => investigationApi.getInvestigation(id),
    enabled: !!id,
  });
  const observationId = report?.data?.observation_id;
  const { data: graph, isLoading: graphLoading, error: graphError } = useQuery({
    queryKey: ['graph-neighborhood', observationId],
    queryFn: () => graphApi.observationNeighborhood(observationId),
    enabled: Boolean(observationId),
  });

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-neutral-400" />
      </div>
    );
  }

  if (error || !report?.data) {
    return (
      <div className="p-8">
        <div className="max-w-3xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-red-600" />
              <div>
                <h3 className="font-medium text-red-800">Investigation Not Found</h3>
                <p className="text-sm text-red-600 mt-1">
                  The investigation report could not be loaded.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const data = report.data;
  const fusion = data.module_results?.multimodal_fusion;
  const fusionClassification = fusion?.result?.classification;
  const modules = data.module_results || {};
  const urlOutput = modules.url?.result || {};
  const htmlOutput = modules.html_nlp?.result || {};
  const ocrOutput = modules.ocr?.result || {};
  const visualOutput = modules.computer_vision?.result || {};
  const urlClass = urlOutput.classification || {};
  const htmlFeatures = htmlOutput.dom_features || {};
  const formSignals = htmlFeatures.forms || [];
  const urgencyCues = htmlOutput.nlp_signals?.urgency_cues || [];
  const credentialKeywords = ocrOutput.extracted_credentials_keywords || [];
  const visualCandidates = visualOutput.detected_elements || [];
  const availableModules = ['url', 'html_nlp', 'ocr', 'computer_vision', 'multimodal_fusion']
    .filter((key) => ['success', 'partial'].includes(modules[key]?.status)).length;
  const moduleStatusVariant = (status) => {
    if (status === 'success') return 'success';
    if (status === 'partial' || status === 'error') return 'warning';
    return 'neutral';
  };
  const describeModule = (key, result) => {
    const payload = result?.result || {};
    if (key === 'url') return payload.classification?.top_risk_factors?.join(', ')
      || payload.classification?.verdict?.replace('_', ' ')
      || payload.extracted_indicators?.domain
      || null;
    if (key === 'html_nlp') return payload.nlp_signals?.urgency_cues?.length
      ? `Urgency cues: ${payload.nlp_signals.urgency_cues.join(', ')}`
      : payload.dom_features?.form_action_count != null
        ? `${payload.dom_features.form_action_count} form(s), ${payload.dom_features.iframe_count || 0} iframe(s)`
        : null;
    if (key === 'ocr') return payload.text_character_count
      ? `${payload.text_character_count} characters · ${(payload.extracted_credentials_keywords || []).length} credential keyword(s)`
      : null;
    if (key === 'computer_vision') return payload.classification?.num_candidates_found != null
      ? `${payload.classification.num_candidates_found} logo candidate crop(s); brand match ${payload.brand_match_performed ? 'performed' : 'not performed'}`
      : null;
    if (key === 'multimodal_fusion') return payload.insufficient_evidence
      ? 'Evidence was insufficient to produce a score.'
      : payload.limitations?.[0] || null;
    return null;
  };

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link to="/history" className="inline-flex items-center gap-2 text-sm text-neutral-600 hover:text-neutral-900 mb-4">
            <ArrowLeft className="w-4 h-4" />
            Back to History
          </Link>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2"><h1 className="text-2xl font-semibold text-neutral-900">Archive investigation</h1><Badge variant="info">{availableModules}/5 modules returned evidence</Badge></div>
              <p className="text-neutral-600 mt-1">
                {data.input_type === 'url' ? defangUrl(data.input_value) : truncateId(data.input_value)}
              </p>
            </div>
            <Badge variant={data.status === 'success' ? 'success' : 'warning'}>
              {data.status === 'success' ? 'Report saved' : 'Needs review'}
            </Badge>
          </div>
          <div className="flex items-center gap-4 mt-4 text-sm text-neutral-500">
            <span className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {formatDate(data.created_at)}
            </span>
            <span className="flex items-center gap-1">
              <Network className="w-4 h-4" />
              {formatDuration(data.execution_metadata.total_runtime_ms)}
            </span>
          </div>
        </div>

        <section className="mb-6 grid gap-4 rounded-2xl border border-slate-700 bg-[#0f172a] p-5 text-white shadow-sm sm:grid-cols-2 lg:grid-cols-4 sm:p-6">
          <div className="sm:col-span-2 lg:col-span-1"><p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-accent-200">Archive label</p><p className="mt-2 text-xl font-semibold">{data.observation_data?.label?.ground_truth?.normalized_label || 'Not provided'}</p><p className="mt-1 text-xs leading-5 text-white/55">Dataset annotation; this is separate from the experimental model output.</p></div>
          <div><p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-white/45">Target brand</p><p className="mt-2 font-medium">{data.observation_data?.label?.ground_truth?.target_brand || 'Not recorded'}</p><p className="mt-1 text-xs text-white/55">Capture: {data.observation_data?.source_record_id || 'unknown'}</p></div>
          <div><p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-white/45">Observed domain</p><p className="mt-2 break-all font-mono text-sm">{data.observation_data?.url?.domain || 'Not recorded'}</p><p className="mt-1 text-xs text-white/55">Captured: {formatDate(data.observation_data?.timestamps?.captured_at)}</p></div>
          <div><p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-white/45">Artifacts in capture</p><div className="mt-2 flex flex-wrap gap-1.5">{[['HTML', data.observation_data?.availability?.has_html], ['OCR', data.observation_data?.availability?.has_ocr], ['Screenshot', data.observation_data?.availability?.has_screenshot]].map(([name, present]) => <span key={name} className={`rounded-full px-2 py-1 text-[10px] font-medium ${present ? 'bg-accent-300/15 text-accent-200' : 'bg-white/10 text-white/40'}`}>{name} {present ? 'present' : 'missing'}</span>)}</div><p className="mt-2 text-xs text-white/55">Only available artifacts can be analyzed.</p></div>
        </section>

        <div className="mb-6">
          <ObservationGraph graph={graph?.data} observationId={data.observation_id} isLoading={graphLoading} error={graphError} />
        </div>

        {/* Warnings */}
        {data.warnings.length > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h3 className="font-medium text-yellow-800 mb-2">Warnings</h3>
                <ul className="space-y-1">
                  {data.warnings.map((warning, idx) => (
                    <li key={idx} className="text-sm text-yellow-700">
                      <span className="font-mono">[{warning.code}]</span> {warning.message}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Observation Data */}
        {data.observation_data && (
          <div className="bg-white rounded-lg border border-neutral-200 mb-6">
            <div className="px-6 py-4 border-b border-neutral-200">
              <h2 className="text-lg font-semibold text-neutral-900">Observation Details</h2>
            </div>
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-sm font-medium text-neutral-600 mb-2">URL</h3>
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-neutral-400" />
                  <code className="text-sm font-mono text-neutral-700">
                    {defangUrl(data.observation_data.url.raw)}
                  </code>
                </div>
              </div>
              <div>
                <h3 className="text-sm font-medium text-neutral-600 mb-2">Domain</h3>
                <code className="text-sm font-mono text-neutral-700">
                  {data.observation_data.url.domain || 'N/A'}
                </code>
              </div>
              <div>
                <h3 className="text-sm font-medium text-neutral-600 mb-2">Target Brand</h3>
                <p className="text-sm text-neutral-700">
                  {data.observation_data.label.ground_truth.target_brand || 'N/A'}
                </p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-neutral-600 mb-2">Captured</h3>
                <p className="text-sm text-neutral-700">
                  {formatDate(data.observation_data.timestamps.captured_at)}
                </p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-neutral-600 mb-2">IP Address</h3>
                <code className="text-sm font-mono text-neutral-700">
                  {data.observation_data.network.ip || 'N/A'}
                </code>
              </div>
              <div>
                <h3 className="text-sm font-medium text-neutral-600 mb-2">ASN</h3>
                <p className="text-sm text-neutral-700">
                  {data.observation_data.network.asn_name || 'N/A'}
                </p>
              </div>
            </div>
          </div>
        )}

        <section className="mb-6 rounded-2xl border border-neutral-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-3 border-b border-neutral-100 px-5 py-5 sm:px-6">
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary-700">Investigation notes</p><h2 className="mt-1 text-lg font-semibold text-neutral-900">Signals found in the captured evidence</h2><p className="mt-1 text-sm text-neutral-500">Review each observation with its module status; empty evidence can mean the archive artifact was unavailable.</p></div>
            <Badge variant="info">{availableModules} modules produced usable output</Badge>
          </div>
          <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3 sm:p-5">
            <EvidencePanel title="URL structure" status={modules.url?.status}>
              <DataPoint label="Baseline result" value={urlClass.verdict || 'No verdict returned'} />
              <DataPoint label="Heuristic score" value={typeof urlClass.confidence_score === 'number' ? `${(urlClass.confidence_score * 100).toFixed(1)}%` : 'Not available'} />
              <DataPoint label="Host uses IP address" value={urlOutput.features?.has_ip_in_host == null ? 'Not measured' : urlOutput.features.has_ip_in_host ? 'Yes' : 'No'} />
              <DataPoint label="HTTPS in captured URL" value={urlOutput.features?.has_https == null ? 'Not measured' : urlOutput.features.has_https ? 'Yes' : 'No'} />
              <SignalChips items={urlClass.top_risk_factors || []} empty="No top risk factors returned." />
            </EvidencePanel>

            <EvidencePanel title="Page structure" status={modules.html_nlp?.status}>
              <DataPoint label="Page title" value={htmlFeatures.title || 'Not captured'} />
              <DataPoint label="Forms / password forms" value={htmlFeatures.form_action_count == null ? 'Not measured' : `${htmlFeatures.form_action_count} / ${formSignals.filter((form) => form.has_password_input).length}`} />
              <DataPoint label="External form actions" value={formSignals.filter((form) => form.is_action_external).length} />
              <DataPoint label="External links ratio" value={typeof htmlFeatures.external_links_ratio === 'number' ? `${(htmlFeatures.external_links_ratio * 100).toFixed(0)}%` : 'Not measured'} />
              <SignalChips items={urgencyCues} empty="No urgency cues returned." />
            </EvidencePanel>

            <EvidencePanel title="Text extraction" status={modules.ocr?.status}>
              <DataPoint label="Characters read" value={ocrOutput.text_character_count ?? 'Not available'} />
              <DataPoint label="Extraction source" value={ocrOutput.source || 'No text source'} />
              <DataPoint label="Mean OCR confidence" value={typeof ocrOutput.confidence_mean === 'number' ? `${(ocrOutput.confidence_mean * 100).toFixed(0)}%` : 'Not measured'} />
              <SignalChips items={credentialKeywords} empty="No credential keywords returned." />
              {ocrOutput.extracted_text_raw && <details className="mt-3"><summary className="cursor-pointer text-xs font-semibold text-primary-700">Inspect extracted text</summary><pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap rounded-lg bg-neutral-50 p-3 text-[11px] text-neutral-700">{ocrOutput.extracted_text_raw}</pre></details>}
            </EvidencePanel>

            <EvidencePanel title="Visual candidates" status={modules.computer_vision?.status}>
              <DataPoint label="Candidate crops" value={visualOutput.classification?.num_candidates_found ?? 0} />
              <DataPoint label="Brand match performed" value={visualOutput.brand_match_performed ? 'Yes' : 'No'} />
              <p className="mt-3 text-xs leading-5 text-neutral-500">Candidate regions are not brand identifications. This prototype does not claim a visual brand match.</p>
              {visualCandidates.length > 0 && <div className="mt-3 space-y-2">{visualCandidates.slice(0, 4).map((candidate) => <div key={candidate.candidate_id} className="rounded-lg bg-neutral-50 px-3 py-2 text-xs text-neutral-600">Candidate {candidate.candidate_id} · box {candidate.box_2d?.join(', ') || 'not recorded'}</div>)}</div>}
            </EvidencePanel>

            <EvidencePanel title="Combined baseline" status={fusion?.status}>
              <DataPoint label="Baseline assessment" value={fusionClassification?.verdict?.replace('_', ' ') || (fusion?.result?.insufficient_evidence ? 'Insufficient evidence' : 'No combined score')} />
              <DataPoint label="Score" value={typeof fusionClassification?.confidence_score === 'number' ? `${(fusionClassification.confidence_score * 100).toFixed(1)}% · uncalibrated` : 'Not produced'} />
              <DataPoint label="Score inputs" value={fusion?.result?.active_modalities?.join(', ') || 'None'} />
              <SignalChips items={(fusion?.result?.evidence_summary || []).map((item) => `${item.modality}: ${item.observed_signal}`)} empty="No modality evidence was combined." />
            </EvidencePanel>

            <div className="rounded-xl border border-primary-200 bg-primary-50/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary-800">Suggested investigator checks</p>
              <ul className="mt-3 space-y-3 text-xs leading-5 text-neutral-700">
                <li><strong>Compare brand and domain:</strong> confirm whether the observed registered domain is controlled by the target brand; this report does not verify ownership.</li>
                <li><strong>Inspect credential handling:</strong> review any password form and external action shown above, then validate the captured destination.</li>
                <li><strong>Follow graph links:</strong> check whether this capture shares a domain, IP, campaign label, or similarity edge with other observations.</li>
                <li><strong>Account for missing artifacts:</strong> a skipped OCR or visual module means there was no usable captured input, not that the page was safe.</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Module Results */}
        <div className="bg-white rounded-lg border border-neutral-200 mb-6">
          <div className="px-6 py-4 border-b border-neutral-200">
            <h2 className="text-lg font-semibold text-neutral-900">Pipeline run status</h2>
          </div>
          <div className="p-6">
            {fusionClassification && (
              <div className="mb-5 rounded-lg border border-indigo-200 bg-indigo-50 p-4">
                <h3 className="font-medium text-indigo-950">Combined baseline assessment</h3>
                <p className="mt-1 text-sm text-indigo-900">
                  {fusionClassification.verdict?.replace('_', ' ') || 'Assessment available'}
                  {typeof fusionClassification.confidence_score === 'number'
                    ? ` · ${(fusionClassification.confidence_score * 100).toFixed(1)}% heuristic score`
                    : ''}
                </p>
                <p className="mt-1 text-xs text-indigo-800">
                  This is an uncalibrated baseline score from available URL and HTML signals, not a confirmed verdict.
                </p>
                {(fusion.result?.active_modalities?.length > 0) && (
                  <p className="mt-2 text-xs text-indigo-800">
                    Score inputs: {fusion.result.active_modalities.join(', ')}
                  </p>
                )}
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              {[
                { key: 'url', label: 'URL Analysis', icon: Globe },
                { key: 'html_nlp', label: 'HTML/NLP', icon: FileText },
                { key: 'ocr', label: 'OCR', icon: FileText },
                { key: 'computer_vision', label: 'Computer Vision', icon: Image },
                { key: 'multimodal_fusion', label: 'Fusion', icon: Network },
              ].map((module) => {
                const result = data.module_results?.[module.key];
                const Icon = module.icon;
                return (
                  <div
                    key={module.key}
                    className="p-4 border border-neutral-200 rounded-lg"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className="w-4 h-4 text-neutral-400" />
                      <span className="text-sm font-medium text-neutral-700">{module.label}</span>
                    </div>
                    <Badge variant={moduleStatusVariant(result?.status)}>
                      {result?.status || 'Not run'}
                    </Badge>
                    {result?.result?.classification && (
                      <p className="mt-2 text-xs text-neutral-600">
                        {result.result.classification.verdict?.replace('_', ' ') || 'Classification available'}
                        {typeof result.result.classification.confidence_score === 'number'
                          ? ` · ${(result.result.classification.confidence_score * 100).toFixed(0)}%`
                          : ''}
                      </p>
                    )}
                    {result?.warnings?.[0]?.message && (
                      <p className="mt-2 text-xs text-neutral-500">{result.warnings[0].message}</p>
                    )}
                    {describeModule(module.key, result) && (
                      <p className="mt-2 text-xs text-neutral-600">
                        {describeModule(module.key, result)}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Related Observations */}
        <div className="bg-white rounded-lg border border-neutral-200 mb-6">
          <div className="px-6 py-4 border-b border-neutral-200">
            <h2 className="text-lg font-semibold text-neutral-900">
              Related Observations ({data.related_observations?.length || 0})
            </h2>
          </div>
          {(data.related_observations?.length || 0) === 0 ? (
            <div className="p-6 text-center text-neutral-500">
              No related observations found
            </div>
          ) : (
            <div className="divide-y divide-neutral-200">
              {data.related_observations.map((related, idx) => (
                <div key={idx} className="px-6 py-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <code className="text-sm font-mono text-neutral-600">
                          {truncateId(related.observation_id)}
                        </code>
                        <Badge variant="info">{related.relationship_type}</Badge>
                      </div>
                      <p className="text-sm text-neutral-600">{related.explanation}</p>
                    </div>
                    <div className="text-right ml-4">
                      <p className="text-sm font-medium text-neutral-900">
                        {(related.similarity_score * 100).toFixed(1)}%
                      </p>
                      <p className="text-xs text-neutral-500">similarity</p>
                    </div>
                  </div>
                  {related.brand && (
                    <p className="text-sm text-neutral-500">Brand: {related.brand}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Graph Intelligence */}
        <div className="bg-white rounded-lg border border-neutral-200 mb-6">
          <div className="px-6 py-4 border-b border-neutral-200">
            <h2 className="text-lg font-semibold text-neutral-900">Graph Intelligence</h2>
          </div>
          <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Community */}
            <div>
              <h3 className="text-sm font-medium text-neutral-600 mb-2">Community</h3>
              {data.graph_intelligence.community ? (
                <div>
                  <p className="text-sm text-neutral-700">
                    Cluster: {data.graph_intelligence.community.cluster_id}
                  </p>
                  <p className="text-sm text-neutral-500">
                    Size: {data.graph_intelligence.community.cluster_size}
                  </p>
                </div>
              ) : (
                <p className="text-sm text-neutral-500">Not available</p>
              )}
            </div>
            {/* Entity Ranking */}
            <div>
              <h3 className="text-sm font-medium text-neutral-600 mb-2">Entity Ranking</h3>
              {data.graph_intelligence.entity_ranking ? (
                <p className="text-sm text-neutral-700">
                  {data.graph_intelligence.entity_ranking.explanation}
                </p>
              ) : (
                <p className="text-sm text-neutral-500">Not available</p>
              )}
            </div>
            {/* Temporal */}
            <div>
              <h3 className="text-sm font-medium text-neutral-600 mb-2">Temporal Analysis</h3>
              {data.graph_intelligence.temporal_analysis ? (
                <div>
                  <p className="text-sm text-neutral-700">
                    Bucket: {data.graph_intelligence.temporal_analysis.time_bucket}
                  </p>
                  <Badge variant={data.graph_intelligence.temporal_analysis.is_burst ? 'warning' : 'neutral'}>
                    {data.graph_intelligence.temporal_analysis.is_burst ? 'Burst' : 'Normal'}
                  </Badge>
                </div>
              ) : (
                <p className="text-sm text-neutral-500">Not available</p>
              )}
            </div>
          </div>
        </div>

        {data.module_results?.graph_persistence && (
          <div className="bg-white rounded-lg border border-neutral-200 mb-6">
            <div className="px-6 py-4 border-b border-neutral-200">
              <h2 className="text-lg font-semibold text-neutral-900">Graph Update</h2>
            </div>
            <div className="p-6 flex flex-wrap items-center gap-3 text-sm text-neutral-700">
              <Badge variant={moduleStatusVariant(data.module_results.graph_persistence.status)}>
                {data.module_results.graph_persistence.status}
              </Badge>
              {data.module_results.graph_persistence.nodes_merged != null && (
                <span>{data.module_results.graph_persistence.nodes_merged} nodes and {data.module_results.graph_persistence.relationships_merged} relationships merged</span>
              )}
            </div>
          </div>
        )}

        {/* Execution Metadata */}
        <div className="bg-white rounded-lg border border-neutral-200">
          <div className="px-6 py-4 border-b border-neutral-200">
            <h2 className="text-lg font-semibold text-neutral-900">Execution Metadata</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-sm font-medium text-neutral-600 mb-2">Algorithm Versions</h3>
                <div className="space-y-1 text-sm text-neutral-700">
                  <p>Similarity: {data.algorithm_versions.similarity}</p>
                  <p>Community Detection: {data.algorithm_versions.community_detection}</p>
                  <p>Entity Ranking: {data.algorithm_versions.entity_ranking}</p>
                </div>
              </div>
              <div>
                <h3 className="text-sm font-medium text-neutral-600 mb-2">Stage Runtime</h3>
                <div className="space-y-1 text-sm text-neutral-700">
                  {Object.entries(data.execution_metadata.stages).map(([stage, time]) => (
                    <p key={stage}>
                  {stage}: {formatDuration(time)}
                    </p>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
