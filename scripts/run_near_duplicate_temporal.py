"""
Near-Duplicate and Temporal Analysis Pipeline
"""

import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from modules.dataset_adapter.reader import PhishpediaDatasetReader
from modules.graph_ai.near_duplicate.detector import NearDuplicateDetector
from modules.graph_ai.temporal.analyzer import TemporalGraphAnalyzer
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver, GraphConnectionError
from modules.graph_ai.graph_adapter.temporal_persistence import NearDuplicatePersistence, TemporalPersistence


def run_near_duplicate_analysis(
    limit: int = 1000,
    archive_path: str = "data/phish_sample_30k.zip",
    threshold: float = 0.7,
    run_id: str = None,
    dry_run: bool = False,
):
    """Run near-duplicate detection on HTML content."""
    run_id = run_id or f"near_dup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    print(f"\n{'='*60}")
    print(f"  Near-Duplicate Analysis")
    print(f"  Run ID: {run_id}")
    print(f"  Limit: {limit}")
    print(f"  Threshold: {threshold}")
    print(f"{'='*60}\n")

    detector = NearDuplicateDetector(threshold=threshold)
    reader = PhishpediaDatasetReader(archive_path=archive_path)

    print(f"[Indexing] Processing HTML content...")
    count = 0
    for obs in reader.stream_observations(limit=limit, offset=0):
        obs_id = obs["observation_id"]

        # Read HTML from zip
        source_id = obs.get("source_record_id")
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                html_path = f"{source_id}/html.txt"
                if html_path in zf.namelist():
                    html_bytes = zf.read(html_path)
                    html_text = html_bytes.decode("utf-8", errors="replace")
                    detector.add_html(obs_id, html_text)
                    count += 1

                    if count % 100 == 0:
                        print(f"  Processed {count} HTML documents")
        except Exception:
            pass

    stats = detector.get_statistics()
    print(f"\n[Statistics] {stats}\n")

    # Query duplicates for a sample
    print(f"[Querying] Finding near-duplicates for sample observations...")
    sample_obs_ids = list(detector.minhashes.keys())[:10]

    for obs_id in sample_obs_ids:
        duplicates = detector.query_duplicates(obs_id)
        if duplicates:
            print(f"  {obs_id}: {len(duplicates)} near-duplicates")
            for dup_id, jaccard in duplicates[:3]:
                print(f"    -> {dup_id} (Jaccard: {jaccard:.3f})")

    # Persist to Neo4j
    if not dry_run:
        try:
            driver = Neo4jDriver()
            driver.connect()
            persistence = NearDuplicatePersistence(driver)
            print(f"\n[Persistence] Writing to Neo4j...")

            dup_count = 0
            for obs_id in sample_obs_ids:
                for dup_id, jaccard in detector.query_duplicates(obs_id):
                    persistence.persist_near_duplicate(obs_id, dup_id, jaccard, run_id)
                    dup_count += 1

            print(f"  Persisted {dup_count} near-duplicate relationships")
            driver.close()
        except GraphConnectionError as e:
            print(f"  ERROR: {e}")

    print(f"\n{'='*60}\n")


def run_temporal_analysis(
    limit: int = 1000,
    archive_path: str = "data/phish_sample_30k.zip",
    window_days: int = 7,
    run_id: str = None,
    dry_run: bool = False,
):
    """Run temporal graph analysis."""
    run_id = run_id or f"temporal_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    print(f"\n{'='*60}")
    print(f"  Temporal Graph Analysis")
    print(f"  Run ID: {run_id}")
    print(f"  Limit: {limit}")
    print(f"  Window: {window_days} days")
    print(f"{'='*60}\n")

    analyzer = TemporalGraphAnalyzer()
    reader = PhishpediaDatasetReader(archive_path=archive_path)

    print(f"[Indexing] Processing timestamps...")
    obs_data = {}
    count = 0
    for obs in reader.stream_observations(limit=limit, offset=0):
        obs_id = obs["observation_id"]
        timestamp = obs.get("timestamps", {}).get("captured_at", "")

        analyzer.add_observation(obs_id, timestamp)

        # Store observation data for cluster analysis
        obs_data[obs_id] = {
            "brand": obs.get("label", {}).get("ground_truth", {}).get("target_brand", ""),
        }
        count += 1

    stats = analyzer.get_statistics()
    print(f"\n[Statistics] {stats}\n")

    # Detect bursts
    print(f"[Burst Detection] Finding time periods with high activity...")
    bursts = analyzer.detect_bursts(window_days=window_days)
    print(f"  Found {len(bursts)} bursts")
    for burst in bursts[:5]:
        print(f"    {burst['time_bucket']}: {burst['observation_count']} obs (threshold: {burst['threshold']:.1f})")

    # Build time-windowed graph
    print(f"\n[Graph] Building time-windowed graph ({window_days}-day window)...")
    graph = analyzer.build_time_windowed_graph(window_days=window_days)
    print(f"  Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    # Analyze temporal clusters
    print(f"\n[Clusters] Analyzing temporal patterns...")
    clusters = analyzer.analyze_temporal_clusters(obs_data)
    print(f"  Found {len(clusters)} time buckets with multiple observations")
    for cluster in clusters[:5]:
        print(f"    {cluster['time_bucket']}: {cluster['observation_count']} obs, {cluster['unique_brands']} brands")

    # Persist to Neo4j
    if not dry_run:
        try:
            driver = Neo4jDriver()
            driver.connect()
            persistence = TemporalPersistence(driver)
            print(f"\n[Persistence] Writing bursts to Neo4j...")

            for burst in bursts:
                persistence.persist_burst(
                    burst["time_bucket"],
                    burst["observation_count"],
                    burst["threshold"],
                    run_id,
                )

            print(f"  Persisted {len(bursts)} temporal bursts")
            driver.close()
        except GraphConnectionError as e:
            print(f"  ERROR: {e}")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Near-Duplicate and Temporal Analysis")
    parser.add_argument("--limit", type=int, default=1000, help="Number of observations")
    parser.add_argument("--archive", default="data/phish_sample_30k.zip", help="Dataset archive path")
    parser.add_argument("--mode", choices=["near-duplicate", "temporal", "both"], default="both")
    parser.add_argument("--threshold", type=float, default=0.7, help="Jaccard threshold for near-duplicates")
    parser.add_argument("--window-days", type=int, default=7, help="Time window in days")
    parser.add_argument("--run-id", default=None, help="Run ID")
    parser.add_argument("--dry-run", action="store_true", help="Skip Neo4j writes")

    args = parser.parse_args()

    if args.mode in ["near-duplicate", "both"]:
        run_near_duplicate_analysis(
            limit=args.limit,
            archive_path=args.archive,
            threshold=args.threshold,
            run_id=args.run_id,
            dry_run=args.dry_run,
        )

    if args.mode in ["temporal", "both"]:
        run_temporal_analysis(
            limit=args.limit,
            archive_path=args.archive,
            window_days=args.window_days,
            run_id=args.run_id,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
