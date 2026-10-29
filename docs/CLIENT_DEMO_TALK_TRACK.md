# CYRAXI Client Demo Talk Track

This guide gives a clear, accurate way to present the current CYRAXI prototype. The live investigation UI uses records from the local Phishpedia archive and reads saved graph results from Neo4j. It does not crawl arbitrary live URLs or run every detection model when the user clicks **Start Investigation**.

## 30-second introduction

> CYRAXI is a cybercrime intelligence workspace for connecting phishing observations into a broader campaign picture. It brings archived URL and network data together with saved model evidence and Neo4j relationships. An analyst can investigate an observation, review its report, search the graph by brand or infrastructure, and compare how much related graph context is returned.

## What is in the project

- **Dashboard:** recent saved investigations, runtime and success summaries, service status, and shortcuts to the investigation and experiment workspaces.
- **Investigation workspace:** looks up an observation ID or an exact URL in the configured archive and creates a report.
- **Investigation reports:** show archived observation metadata, stored module-result availability, related observations, warnings, graph fields, and timings.
- **Graph Explorer:** searches Neo4j observations by brand, IP address, or campaign family.
- **Experiment Lab:** runs the same investigation at two related-observation limits and compares the returned graph context. This is a retrieval-depth experiment; it does not tune model weights or change the phishing verdict.
- **Backend and data tools:** FastAPI services, a ZIP-streaming dataset adapter, graph ingestion, URL analysis, and offline graph-similarity and temporal-analysis runners.

Think of the project as three connected layers: **the archive supplies observations**, **analysis jobs create signals and graph links**, and **the web app lets an analyst inspect what has been saved**. It is not yet a live website scanner that runs every model on demand.

## Use this sample record

This record is already present in the local saved reports and is a known example for demonstrating the lookup and report screens:

- **Observation ID to enter:** `obs_5defe88b6365fae970616012cf8ef3a2`
- **Target brand:** 1&1 Ionos
- **Domain shown in the report:** `serv-acamai.com`
- **Archive URL, defanged:** `hxxp://serv-acamai[.]com/1und1/de/index[.]php`

Enter the **observation ID** in the form. The URL above is defanged and is included only to identify the record; do not open it. The currently saved report for this record has no stored module results and zero related observations. It is useful for showing the lookup/report flow, but it is not a good example of populated graph similarity.

For a more complete report and Experiment Lab demo, prepare the graph first, then find a record with many saved similarity links using the query below in Neo4j Browser:

```cypher
MATCH (o:Observation)-[:CANDIDATE_SIMILAR_TO]->(related:Observation)
WITH o, count(related) AS links
WHERE links >= 10
RETURN o.observation_id AS observation_id, links
ORDER BY links DESC
LIMIT 10
```

Copy one returned ID into the investigation form. For the Graph Explorer, find a brand that actually exists in the loaded graph:

```cypher
MATCH (:Observation)-[:TARGETS_BRAND]->(b:Brand)
RETURN b.name AS brand, count(*) AS observations
ORDER BY observations DESC
LIMIT 10
```

## Suggested five-minute demo

### 1. Open the dashboard

Say:

> This is the analyst workspace. The overview summarizes recent saved reports and shows whether the investigation and graph services are responding. The workflow is to look up an observation, inspect its report, then explore related graph context.

Point out the recent-investigation count is based on the latest 50 saved reports. It is not a live count of every record in the archive.

### 2. Run an investigation

In **New Investigation**, select **Observation ID**, paste the sample ID above, and click **Start Investigation**. To show populated graph results, use an ID returned by the similarity query after preparing the graph. Say:

> I’m looking up this observation in the local archive. CYRAXI then checks stored module-result availability and graph relationships for it and saves a report we can revisit.

The current investigation endpoint searches the archive for the record. It does not fetch the submitted URL from the internet. An arbitrary URL that is not present in the archive will return an observation-not-found report. For the most compelling report, use an ID that the similarity query returned.

### 3. Walk through the report

Show the observation metadata, status, warnings, runtime, and related-observation section. Say:

> The report keeps the source observation and the graph context together. Where similarity relationships have been computed and saved, we can review the related observation IDs, scores, and explanations here. Empty module or relationship sections mean that evidence has not been stored for this record yet.

Be clear that the current UI reports whether module results are available in stored data. It does not run URL, HTML/NLP, OCR, computer-vision, and fusion models on demand as part of this button click.

### 4. Explore the graph

Search by a brand, IP address, or campaign family known to exist in the loaded graph. Say:

> This view lets an analyst pivot from one indicator to observations already connected in Neo4j. A result depends on those observations and relationships having been ingested first.

### 5. Show the Experiment Lab

Use the same archived observation and choose different related-observation limits for Run A and Run B. Say:

> Here I’m comparing a smaller and a larger graph-context request. Both runs are saved as reports, and the panel shows which additional observations appear in the expanded result. This demonstrates retrieval behavior; it is not a model-training or threshold-tuning interface.

Use an observation with at least 10 similarity links for this step. If both result cards show zero observations, the graph-similarity preparation did not create links for that input; use another ID returned by the Cypher query.

## What to say about each module

Use these answers if someone asks what a named component contributes. The distinction between **available in the repository** and **run by the current investigation button** matters.

| Module | Plain-language explanation | What is actually run today |
|---|---|---|
| Dataset adapter | Reads the Phishpedia ZIP a record at a time and turns each entry into a standard observation with URL, labels, timestamps, network fields, and artifact references. | Used by the batch scripts and investigation lookup. It reads the local archive, not a live feed. |
| URL analysis | Extracts URL and host indicators, then scores them with a saved scikit-learn model when available or a heuristic fallback. | `run_pipeline.py` performs URL analysis and writes its output into Neo4j. The web investigation request does not run this model again. |
| HTML/NLP | Looks for page structure and basic phishing cues, such as password forms, external form actions, and urgency words. | `run_multimodal.py` runs this baseline offline and writes JSONL output. It is not wired into the investigation button. |
| OCR | Reads captured OCR text or screenshot text with Tesseract and reports credential-related words. | Available in the offline multimodal runner when the record has usable artifacts and Tesseract is installed. |
| Computer vision | Uses supplied logo-coordinate data and screenshot bytes to crop candidate regions. | The current detector does not independently identify a brand from the screenshot; it reports candidate crops and limitations. It runs in the offline multimodal pipeline. |
| Fusion | Combines compatible URL and HTML scores using the configured weights; OCR and visual outputs are treated as supporting evidence, not equivalent calibrated probabilities. | Runs in `run_multimodal.py`. The current implementation describes its URL/HTML baseline scores as heuristic and not calibrated. |
| Graph enrichment | Stores observations and connections such as URL, domain, IP, ASN, brand, model run, prediction, and evidence in Neo4j. | `run_pipeline.py` writes this base graph. The Graph API reads it for brand, IP, and campaign searches. |
| Graph similarity | Finds candidate pairs using shared indicators, computes similarity features and scores, and saves `CANDIDATE_SIMILAR_TO` relationships. | `scripts/run_graph_similarity.py` is an offline preparation job. The investigation report can display its saved links; the UI does not compute them on demand. |
| Near-duplicate and temporal analysis | Looks for similar captured HTML and clusters activity over time. | Separate offline runner; it is not part of the normal investigation request. |

### Short answer to “What are you doing?”

> I’m building an analyst workflow that turns a phishing archive into a searchable evidence graph. The ingestion jobs normalize observations and save analysis results; similarity jobs add links between related observations; the web app lets an analyst inspect one record, pivot through the graph, and compare how much related context is returned. The current prototype uses preprocessed local data rather than live crawling.

## How the pieces work together

1. `modules/dataset_adapter` streams observations from the configured archive and converts records into the project’s canonical observation shape.
2. `run_pipeline.py` runs the URL-analysis pipeline and writes observation, URL, brand, network, prediction, and evidence entities to Neo4j.
3. `scripts/run_graph_similarity.py` computes candidate similarities and persists `CANDIDATE_SIMILAR_TO` links. The investigation report reads those saved links.
4. `backend_main.py` starts the investigation API on port 8002 and graph API on port 8001.
5. The React app in `frontend/` calls those APIs and presents reports and graph queries.

Near-duplicate and temporal analysis are additional offline runners. They are separate preparation jobs, not automatic stages of the investigation button.

## Demo setup

The archive is local and is not included in Git. Confirm `data/phish_sample_30k.zip` is available before the demo. Prepare the graph before presenting if you want populated graph and similarity results.

### Prepare Neo4j data

Start Neo4j:

```powershell
cd C:\Desktop\cyraxi
docker compose up -d
```

In a terminal, ingest a demonstration slice. Do not pass `--dry-run` when you want graph writes:

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --limit 1000
```

Then compute similarity relationships for the same slice:

```powershell
.\.venv\Scripts\python.exe scripts\run_graph_similarity.py --limit 1000
```

For a reliable report comparison, choose an observation included in the processed slice. Larger slices provide more candidates but take longer to prepare. The near-duplicate and temporal runner is optional:

```powershell
.\.venv\Scripts\python.exe scripts\run_near_duplicate_temporal.py --limit 1000 --mode both
```

### Start the APIs and frontend

In one terminal, start both APIs:

```powershell
cd C:\Desktop\cyraxi
.\.venv\Scripts\python.exe backend_main.py
```

In another terminal, start the frontend:

```powershell
cd C:\Desktop\cyraxi\frontend
npm run dev -- --force
```

Open the local URL printed by Vite. It is usually `http://localhost:3000`; if Vite selects another port, use the printed URL. For a fresh checkout, first install frontend dependencies with `npm ci`.

## Questions you may get

**Does CYRAXI open a submitted phishing URL?**

> No. The current investigation flow looks for an exact URL match in the configured archive; it does not browse to the submitted URL.

**Why might the graph or related-observation section be empty?**

> Those results depend on graph data and similarity relationships having been prepared in Neo4j. The dashboard and APIs can run before that data is loaded, but they cannot return relationships that are not there.

**Does the Experiment Lab compare model accuracy?**

> No. It compares the related-observation retrieval depth for two runs. It does not retrain models or alter their verdicts.

**Are all detection modalities running live in this demo?**

> The repository contains URL, HTML/NLP, OCR, computer-vision, and fusion components. The current investigation endpoint primarily retrieves an archived observation and stored results; it does not execute every modality on demand.

**Why do I see warnings that module results are missing?**

> The report distinguishes an archived observation from model results saved for that observation. The multimodal runner currently writes JSONL files; those outputs are not automatically imported into the report API's Neo4j result lookup. The warning is a data-integration gap, not a verdict that the record is benign.

**What would production readiness add?**

> The next steps are to wire live model execution into the investigation workflow, expose data-ingestion and graph-preparation status in the UI, add authentication and role-based access, and validate performance and data quality at the intended deployment scale.

## Keep the demo honest

- Call the current product a working prototype or analyst-workspace demo.
- Use only archive records and graph relationships that have actually been prepared.
- Do not describe the Experiment Lab as model tuning.
- Do not claim live URL crawling or live multimodal inference from the investigation form.
- If results are empty, explain which preparation step supplies that data rather than implying the graph is populated automatically.
