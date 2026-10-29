"""
Investigation Runner Script
Command-line interface for running end-to-end investigations.
"""

import argparse
import json
import sys
from pathlib import Path

from modules.investigation.service import InvestigationService
from modules.investigation.persistence import InvestigationPersistence
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver, GraphConnectionError


def run_investigation(
    input_value: str,
    input_type: str = "observation_id",
    archive_path: str = "data/phish_sample_30k.zip",
    limit_related: int = 10,
    output_file: str = None,
    persist_neo4j: bool = True,
    persist_filesystem: bool = True,
):
    """Run investigation and persist results."""

    print(f"\n{'='*60}")
    print(f"  Cybercrime Investigation")
    print(f"{'='*60}")
    print(f"  Input: {input_type} = {input_value}")
    print(f"  Archive: {archive_path}")
    print(f"  Limit related: {limit_related}")
    print(f"{'='*60}\n")

    # Initialize service
    try:
        neo4j_driver = Neo4jDriver()
        print(f"[Init] Neo4j connected")
    except GraphConnectionError as e:
        print(f"[Init] Neo4j not available: {e}")
        print(f"[Init] Continuing without Neo4j (limited functionality)")
        neo4j_driver = None

    service = InvestigationService(
        archive_path=archive_path,
        neo4j_driver=neo4j_driver,
    )

    # Run investigation
    print(f"[Investigate] Processing {input_type}...")
    report = service.investigate(
        input_value=input_value,
        input_type=input_type,
        limit_related=limit_related,
    )

    # Print summary
    print(f"\n[Summary]")
    print(f"  Investigation ID: {report['investigation_id']}")
    print(f"  Observation ID: {report['observation_id']}")
    print(f"  Status: {report['status']}")
    print(f"  Warnings: {len(report['warnings'])}")
    print(f"  Related observations: {len(report['related_observations'])}")
    print(f"  Runtime: {report['execution_metadata']['total_runtime_ms']:.2f}ms")

    if report['warnings']:
        print(f"\n[Warnings]")
        for warning in report['warnings']:
            print(f"  [{warning['code']}] {warning['message']}")

    if report['related_observations']:
        print(f"\n[Related Observations]")
        for i, related in enumerate(report['related_observations'][:5], 1):
            print(f"  {i}. {related['observation_id']}")
            print(f"     Score: {related['similarity_score']:.3f}")
            print(f"     Type: {related['relationship_type']}")
            print(f"     Explanation: {related['explanation']}")

    # Persist results
    if persist_neo4j or persist_filesystem:
        print(f"\n[Persisting]")
        persistence = InvestigationPersistence(
            neo4j_driver=neo4j_driver,
            output_dir="output/investigations",
        )

        persistence_result = persistence.persist(
            report,
            neo4j=persist_neo4j,
            filesystem=persist_filesystem,
        )

        if persistence_result['filesystem']:
            print(f"  Filesystem: {persistence_result['filesystem']}")
        if persistence_result['neo4j']:
            print(f"  Neo4j: {persistence_result['neo4j']}")

    # Output to file if requested
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n[Output] Report saved to {output_file}")

    print(f"\n{'='*60}\n")

    return report


def main():
    parser = argparse.ArgumentParser(description="Run cybercrime investigation")
    parser.add_argument("input", help="Observation ID or URL to investigate")
    parser.add_argument("--type", choices=["observation_id", "url"], default="observation_id", help="Input type")
    parser.add_argument("--archive", default="data/phish_sample_30k.zip", help="Dataset archive path")
    parser.add_argument("--limit", type=int, default=10, help="Max related observations")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--no-neo4j", action="store_true", help="Skip Neo4j persistence")
    parser.add_argument("--no-filesystem", action="store_true", help="Skip filesystem persistence")

    args = parser.parse_args()

    report = run_investigation(
        input_value=args.input,
        input_type=args.type,
        archive_path=args.archive,
        limit_related=args.limit,
        output_file=args.output,
        persist_neo4j=not args.no_neo4j,
        persist_filesystem=not args.no_filesystem,
    )

    # Exit with error code if investigation failed
    if report['status'] == 'error':
        sys.exit(1)


if __name__ == "__main__":
    main()
