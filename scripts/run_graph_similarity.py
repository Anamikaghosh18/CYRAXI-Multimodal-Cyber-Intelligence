"""
Graph Similarity Pipeline Script
Orchestrates candidate generation, feature extraction, similarity scoring,
and persistence for observation similarity analysis.

Usage:
  python scripts/run_graph_similarity.py --limit 1000 --run-id test_run_001
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from modules.dataset_adapter.reader import PhishpediaDatasetReader
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver, GraphConnectionError
from modules.graph_ai.candidate_generation.strategy import CandidateGenerator
from modules.graph_ai.feature_extraction.pairwise_features import PairwiseFeatureExtractor
from modules.graph_ai.similarity.scorer import SimilarityScorer
from modules.graph_ai.graph_adapter.similarity_persistence import SimilarityPersistence


def load_config(config_path: str) -> Dict:
    """Load YAML configuration file."""
    import yaml
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(
        description="Graph Similarity Pipeline: Candidate Generation -> Feature Extraction -> Scoring -> Persistence"
    )
    parser.add_argument(
        "--limit", type=int, default=1000,
        help="Number of observations to process (default: 1000)"
    )
    parser.add_argument(
        "--offset", type=int, default=0,
        help="Skip first N observations (default: 0)"
    )
    parser.add_argument(
        "--archive", default="data/phish_sample_30k.zip",
        help="Path to dataset archive"
    )
    parser.add_argument(
        "--run-id", default=None,
        help="Run ID for tracking (auto-generated if not provided)"
    )
    parser.add_argument(
        "--config", default="configs/graph_ai_similarity_weights.yaml",
        help="Path to similarity weights config"
    )
    parser.add_argument(
        "--candidate-config", default="configs/graph_ai_candidate_generation.yaml",
        help="Path to candidate generation config"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run analysis without persisting to Neo4j"
    )
    parser.add_argument(
        "--min-score", type=float, default=0.3,
        help="Minimum similarity score to persist (default: 0.3)"
    )

    args = parser.parse_args()

    # Generate run ID if not provided
    run_id = args.run_id or f"graph_sim_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    print(f"\n{'='*60}")
    print(f"  Graph Similarity Pipeline")
    print(f"  Run ID    : {run_id}")
    print(f"  Archive   : {args.archive}")
    print(f"  Limit     : {args.limit} (offset={args.offset})")
    print(f"  Dry run   : {args.dry_run}")
    print(f"{'='*60}\n")

    # Load configurations
    sim_config = load_config(args.config)
    cand_config = load_config(args.candidate_config)

    # Connect to Neo4j
    driver = None
    persistence = None
    if not args.dry_run:
        try:
            driver = Neo4jDriver()
            driver.connect()
            persistence = SimilarityPersistence(driver)
            print(f"  [neo4j] Connected\n")
        except GraphConnectionError as exc:
            print(f"\n  [neo4j] ERROR: {exc}")
            print("  Use --dry-run to test without Neo4j.\n")
            sys.exit(1)

    # Initialize components
    candidate_gen = CandidateGenerator(
        max_candidates_per_obs=cand_config.get("max_candidates_per_observation", 100),
        use_domain_index=cand_config.get("use_domain_index", True),
        use_ip_index=cand_config.get("use_ip_index", True),
        use_brand_index=cand_config.get("use_brand_index", True),
        brand_candidate_limit=cand_config.get("brand_candidate_limit", 50),
    )

    feature_extractor = PairwiseFeatureExtractor()
    scorer = SimilarityScorer(config_path=args.config)

    # Stream observations and build indexes
    print(f"  [candidate] Building indexes from {args.limit} observations...")
    reader = PhishpediaDatasetReader(archive_path=args.archive)

    obs_count = 0
    for obs in reader.stream_observations(limit=args.limit, offset=args.offset):
        obs_id = obs["observation_id"]

        # Flatten observation data for candidate generation
        obs_flat = {
            "url": obs.get("url", {}).get("raw", ""),
            "host": obs.get("url", {}).get("host", ""),
            "domain": obs.get("url", {}).get("domain", ""),
            "ip": obs.get("network", {}).get("ip", ""),
            "asn": obs.get("network", {}).get("asn", ""),
            "country_code": obs.get("network", {}).get("country_code", ""),
            "brand": obs.get("label", {}).get("ground_truth", {}).get("target_brand", ""),
            "family_id": obs.get("source", {}).get("family_id", ""),
        }

        candidate_gen.add_observation(obs_id, obs_flat)
        feature_extractor.cache_observation(obs_id, obs_flat)
        obs_count += 1

    stats = candidate_gen.get_statistics()
    print(f"  [candidate] Indexes built: {stats['total_observations']} obs, "
          f"{stats['unique_domains']} domains, {stats['unique_ips']} IPs, "
          f"{stats['unique_brands']} brands\n")

    # Generate candidates and compute similarities
    print(f"  [similarity] Computing similarity scores...")
    total_candidates = 0
    total_similarities = 0
    high_similarity_count = 0
    similarities_to_persist = []

    for obs_id_1, obs_id_2, method in candidate_gen.generate_candidates():
        total_candidates += 1

        # Extract features
        features = feature_extractor.extract_features(obs_id_1, obs_id_2)

        if not features:
            continue

        # Get observation data for constraints
        obs_data_1 = feature_extractor.observation_cache.get(obs_id_1, {})
        obs_data_2 = feature_extractor.observation_cache.get(obs_id_2, {})

        # Compute similarity
        result = scorer.compute_similarity(
            obs_id_1, obs_id_2, features, obs_data_1, obs_data_2
        )

        # Filter by minimum score
        if result["similarity_score"] >= args.min_score:
            total_similarities += 1
            if result["category"] == "high":
                high_similarity_count += 1

            if not args.dry_run:
                similarities_to_persist.append(result)

        # Progress logging
        if total_candidates % 1000 == 0:
            print(f"  [similarity] Processed {total_candidates} candidates, "
                  f"{total_similarities} similarities (high: {high_similarity_count})")

    print(f"  [similarity] Complete: {total_candidates} candidates, "
          f"{total_similarities} similarities (high: {high_similarity_count})\n")

    # Persist results
    if not args.dry_run and similarities_to_persist:
        print(f"  [persistence] Writing {len(similarities_to_persist)} similarities to Neo4j...")
        count = persistence.batch_persist_similarities(similarities_to_persist, run_id)
        print(f"  [persistence] Written {count} similarities\n")

    # Save summary
    summary = {
        "run_id": run_id,
        "archive": args.archive,
        "limit": args.limit,
        "offset": args.offset,
        "dry_run": args.dry_run,
        "total_observations": obs_count,
        "total_candidates": total_candidates,
        "total_similarities": total_similarities,
        "high_similarity_count": high_similarity_count,
        "min_score": args.min_score,
        "index_statistics": stats,
    }

    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    summary_path = outputs_dir / f"{run_id}_similarity_summary.json"

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"{'='*60}")
    print(f"  Pipeline Complete")
    print(f"  Observations   : {obs_count}")
    print(f"  Candidates     : {total_candidates}")
    print(f"  Similarities   : {total_similarities}")
    print(f"  High similarity: {high_similarity_count}")
    print(f"  Summary saved  : {summary_path}")
    print(f"{'='*60}\n")

    if driver:
        driver.close()


if __name__ == "__main__":
    main()
