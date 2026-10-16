"""
End-to-End Pipeline Bridge: Dataset → URL Analysis → Knowledge Graph
Streams observations, runs URL analysis, ingests results into Neo4j.

Usage:
  python run_pipeline.py --limit 100
  python run_pipeline.py --limit 500 --offset 0 --batch-size 50
  python run_pipeline.py --dry-run --limit 10   (skips Neo4j write, prints output)

The bridge:
  1. Streams N observations from phish_sample_30k.zip
  2. Extracts URL + metadata from each canonical observation
  3. Runs url_analyzer (HGB calibrated model via SklearnURLClassifier)
  4. Builds a GraphIngestRequest from metadata + model envelope
  5. Writes all nodes/edges into Neo4j via GraphEnrichmentMapper
  6. Reports progress every batch_size records
  7. Saves a JSONL run log to outputs/pipeline_run_<timestamp>.jsonl
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Module imports ─────────────────────────────────────────────────────────
from modules.dataset_adapter.reader import PhishpediaDatasetReader
from modules.url_analyzer.domain.extractor import StandardURLFeatureExtractor
from modules.url_analyzer.models.ml_models import SklearnURLClassifier
from modules.url_analyzer.models.heuristic_baseline import HeuristicURLClassifier
from modules.url_analyzer.service import URLAnalysisService
from modules.graph_enrichment_mapper.domain.schemas import GraphIngestRequest
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver, GraphConnectionError
from modules.graph_enrichment_mapper.mapper import GraphEnrichmentMapper


# ── Config defaults ────────────────────────────────────────────────────────
ARCHIVE_PATH   = os.getenv("PHISHPEDIA_ARCHIVE_PATH", "data/phish_sample_30k.zip")
HGB_MODEL_PATH = "modules/url_analyzer/models/saved/url_hgb_model.joblib"
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "cyraxi_dev")
OUTPUTS_DIR    = Path("outputs")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_graph_meta(obs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten a canonical observation dict into the flat metadata dict
    that GraphEnrichmentMapper.ingest() expects.
    """
    net     = obs.get("network", {})
    url_obj = obs.get("url",     {})
    label   = obs.get("label",   {}).get("ground_truth", {})
    src     = obs.get("source",  {})
    ts      = obs.get("timestamps", {})

    return {
        "observation_id":  obs.get("observation_id", ""),
        "source_record_id": obs.get("source_record_id", ""),
        "dataset_id":      obs.get("dataset", {}).get("dataset_id", "phishpedia_primary"),
        "url":             url_obj.get("raw", ""),
        "host":            url_obj.get("host", ""),
        "tld":             url_obj.get("tld", ""),
        "brand":           label.get("target_brand", ""),
        "sector":          label.get("target_sector", ""),
        "ip":              net.get("ip", ""),
        "asn":             net.get("asn", ""),
        "asn_name":        net.get("asn_name", ""),
        "country_code":    net.get("country_code", ""),
        "country_name":    net.get("country_name", ""),
        "family_id":       src.get("family_id", ""),
        "isotime":         ts.get("captured_at", _now_iso()),
    }


def load_url_service(model_path: str) -> URLAnalysisService:
    """Load the best available ML model; fall back to heuristic if model file missing."""
    extractor = StandardURLFeatureExtractor()
    if os.path.exists(model_path):
        clf = SklearnURLClassifier.load(model_path)
        print(f"  [model] Loaded: {model_path} ({clf.model_name})")
    else:
        clf = HeuristicURLClassifier()
        print(f"  [model] WARNING: {model_path} not found — using heuristic baseline")
    return URLAnalysisService(classifier=clf, extractor=extractor)


def run_pipeline(
    limit: int = 100,
    offset: int = 0,
    batch_size: int = 50,
    dry_run: bool = False,
    archive_path: str = ARCHIVE_PATH,
    model_path: str = HGB_MODEL_PATH,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Main pipeline function. Returns a summary dict.

    Args:
        limit:       Total number of observations to process.
        offset:      Skip this many observations from the start of the archive.
        batch_size:  Log progress every N records.
        dry_run:     If True, skip Neo4j writes (useful for testing).
        archive_path: Path to phish_sample_30k.zip.
        model_path:  Path to the HGB .joblib model file.
        verbose:     Print per-record output.
    """
    run_id   = f"pipeline_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUTS_DIR / f"{run_id}.jsonl"

    print(f"\n{'='*60}")
    print(f"  CYRAXI Pipeline Bridge")
    print(f"  Run ID    : {run_id}")
    print(f"  Archive   : {archive_path}")
    print(f"  Limit     : {limit} (offset={offset})")
    print(f"  Dry run   : {dry_run}")
    print(f"{'='*60}\n")

    # ── 1. Load URL analysis service ───────────────────────────────────────
    url_service = load_url_service(model_path)

    # ── 2. Connect to Neo4j (skip if dry_run) ─────────────────────────────
    driver: Optional[Neo4jDriver] = None
    mapper: Optional[GraphEnrichmentMapper] = None

    if not dry_run:
        try:
            driver = Neo4jDriver(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)
            driver.apply_schema_constraints()
            mapper = GraphEnrichmentMapper(driver)
            print(f"  [neo4j] Connected to {NEO4J_URI}\n")
        except GraphConnectionError as exc:
            print(f"\n  [neo4j] ERROR: {exc}")
            print("  Run 'docker compose up -d' to start Neo4j, then retry.")
            print("  Or use --dry-run to test without Neo4j.\n")
            sys.exit(1)

    # ── 3. Stream + process ────────────────────────────────────────────────
    reader = PhishpediaDatasetReader(archive_path=archive_path)

    total_processed = 0
    total_phishing  = 0
    total_nodes     = 0
    total_rels      = 0
    errors: List[str] = []

    t_start = time.perf_counter()
    batch_t = t_start

    with open(log_path, "w", encoding="utf-8") as log_f:

        for obs in reader.stream_observations(limit=limit, offset=offset):
            total_processed += 1
            obs_id  = obs.get("observation_id", "")
            raw_url = obs.get("url", {}).get("raw", "")

            try:
                # ── URL Analysis ───────────────────────────────────────────
                envelope = url_service.analyze(
                    raw_url=raw_url,
                    observation_id=obs_id,
                    run_id=run_id,
                )
                env_dict = envelope.model_dump()

                verdict = (
                    env_dict.get("result", {})
                    .get("classification", {})
                    .get("verdict", "unknown")
                )
                conf = (
                    env_dict.get("result", {})
                    .get("classification", {})
                    .get("confidence_score", 0.0)
                )
                if verdict == "phishing":
                    total_phishing += 1

                # ── Graph Ingestion ────────────────────────────────────────
                graph_meta = _build_graph_meta(obs)
                ingest_req = GraphIngestRequest(
                    observation_meta=graph_meta,
                    model_outputs=[env_dict],
                    run_id=run_id,
                )

                nodes_merged = 0
                rels_merged  = 0

                if mapper is not None:
                    result = mapper.ingest(ingest_req)
                    nodes_merged = result.nodes_merged
                    rels_merged  = result.relationships_merged
                    total_nodes += nodes_merged
                    total_rels  += rels_merged

                # ── Log record ─────────────────────────────────────────────
                log_record = {
                    "obs_id":        obs_id,
                    "url":           raw_url[:120],
                    "verdict":       verdict,
                    "confidence":    conf,
                    "nodes_merged":  nodes_merged,
                    "rels_merged":   rels_merged,
                    "dry_run":       dry_run,
                    "timestamp":     _now_iso(),
                }
                log_f.write(json.dumps(log_record) + "\n")

                if verbose and total_processed % batch_size == 0:
                    elapsed = time.perf_counter() - batch_t
                    rate    = batch_size / max(elapsed, 0.001)
                    print(
                        f"  [{total_processed:>5}/{limit}] "
                        f"phishing={total_phishing} "
                        f"nodes_total={total_nodes} "
                        f"rels_total={total_rels} "
                        f"rate={rate:.1f} obs/s"
                    )
                    batch_t = time.perf_counter()

            except Exception as exc:
                err_msg = f"obs_id={obs_id} url={raw_url[:60]} error={exc}"
                errors.append(err_msg)
                if verbose:
                    print(f"  [ERROR] {err_msg}")

    # ── 4. Clean up ────────────────────────────────────────────────────────
    if driver:
        driver.close()

    total_elapsed = round(time.perf_counter() - t_start, 2)

    summary = {
        "run_id":           run_id,
        "archive":          archive_path,
        "limit":            limit,
        "offset":           offset,
        "dry_run":          dry_run,
        "total_processed":  total_processed,
        "total_phishing":   total_phishing,
        "total_nodes":      total_nodes,
        "total_rels":       total_rels,
        "error_count":      len(errors),
        "elapsed_seconds":  total_elapsed,
        "rate_obs_per_sec": round(total_processed / max(total_elapsed, 0.001), 2),
        "log_path":         str(log_path),
    }

    print(f"\n{'='*60}")
    print(f"  Pipeline Complete")
    print(f"  Processed   : {total_processed} observations")
    print(f"  Phishing    : {total_phishing}")
    print(f"  Nodes merged: {total_nodes}")
    print(f"  Rels merged : {total_rels}")
    print(f"  Errors      : {len(errors)}")
    print(f"  Elapsed     : {total_elapsed}s ({summary['rate_obs_per_sec']} obs/s)")
    print(f"  Log         : {log_path}")
    print(f"{'='*60}\n")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="CYRAXI Pipeline Bridge: Dataset → URL Analysis → Neo4j Knowledge Graph"
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Number of observations to process (default: 100)"
    )
    parser.add_argument(
        "--offset", type=int, default=0,
        help="Skip first N observations in archive (default: 0)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=50,
        help="Print progress every N records (default: 50)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run URL analysis but skip Neo4j writes"
    )
    parser.add_argument(
        "--archive", default=ARCHIVE_PATH,
        help=f"Path to dataset zip (default: {ARCHIVE_PATH})"
    )
    parser.add_argument(
        "--model", default=HGB_MODEL_PATH,
        help=f"Path to .joblib model file (default: {HGB_MODEL_PATH})"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-batch progress output"
    )

    args = parser.parse_args()

    summary = run_pipeline(
        limit=args.limit,
        offset=args.offset,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        archive_path=args.archive,
        model_path=args.model,
        verbose=not args.quiet,
    )

    # Save summary JSON alongside log
    summary_path = Path(summary["log_path"]).with_suffix(".summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
