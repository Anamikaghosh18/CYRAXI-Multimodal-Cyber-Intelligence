#!/usr/bin/env python3
"""
Pipeline Runner: Dataset-to-Model Vertical Slice
Reads 20-50 canonical observations from Phishpedia archive without full extraction,
validates each record, runs the URL feature extraction baseline,
and writes structured ModelOutputEnvelope outputs to a designated output directory.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

# Ensure repository root is on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from modules.dataset_adapter.reader import PhishpediaDatasetReader
from modules.url_analyzer.features import URLBaselineClassifier


def validate_observation_record(obs: Dict[str, Any]) -> List[Dict[str, str]]:
    """Validate observation structure, IDs, and required fields according to canonical schema."""
    warnings = []
    
    # Check observation_id
    obs_id = obs.get("observation_id", "")
    if not obs_id.startswith("obs_") or len(obs_id) != 36:
        warnings.append({
            "code": "W_INVALID_OBS_ID",
            "message": f"Malformed observation ID: {obs_id}",
            "artifact_ref": None
        })
        
    # Check URL
    raw_url = obs.get("url", {}).get("raw", "")
    if not raw_url:
        warnings.append({
            "code": "W_MISSING_URL",
            "message": "Raw URL is missing or empty in observation",
            "artifact_ref": "url.raw"
        })
        
    # Check artifacts
    artifacts = obs.get("artifacts", {})
    if not artifacts.get("screenshot"):
        warnings.append({
            "code": "W_MISSING_SCREENSHOT_REF",
            "message": "Screenshot artifact reference is missing",
            "artifact_ref": "artifacts.screenshot"
        })

    return warnings


def run_pipeline(
    archive_path: str,
    output_dir: str,
    limit: int = 30,
    offset: int = 0,
    run_id: str = "run_vertical_slice_v1"
) -> Dict[str, Any]:
    """Execute the dataset-to-model vertical slice."""
    print(f"=== CYRAXI Vertical Slice Pipeline ===")
    print(f"Archive Source: {archive_path}")
    print(f"Output Directory: {output_dir}")
    print(f"Records to Process: {limit} (Offset: {offset})")
    print(f"Run Identifier: {run_id}")

    os.makedirs(output_dir, exist_ok=True)
    manifest_records_path = Path(output_dir) / "processed_observations.jsonl"
    model_outputs_path = Path(output_dir) / "url_model_outputs.jsonl"

    reader = PhishpediaDatasetReader(archive_path=archive_path)
    classifier = URLBaselineClassifier(phishing_threshold=0.50)

    stats = {
        "total_read": 0,
        "success": 0,
        "skipped": 0,
        "partial": 0,
        "error": 0,
        "total_warnings": 0,
        "total_duration_ms": 0.0
    }

    start_total_time = time.perf_counter()

    with open(manifest_records_path, "w", encoding="utf-8") as f_obs, \
         open(model_outputs_path, "w", encoding="utf-8") as f_out:

        for obs in reader.stream_observations(limit=limit, offset=offset):
            stats["total_read"] += 1
            obs_id = obs["observation_id"]
            obs_warnings = validate_observation_record(obs)
            
            # Save validated observation to jsonl
            f_obs.write(json.dumps(obs) + "\n")

            # Check if URL is usable
            raw_url = obs.get("url", {}).get("raw", "")
            if not raw_url:
                # Modality cannot run: emit skipped envelope
                envelope = {
                    "schema_version": "1.0.0",
                    "observation_id": obs_id,
                    "run_id": run_id,
                    "model": {
                        "name": classifier.model_name,
                        "version": classifier.version,
                        "modality": "url",
                        "execution_hardware": "cpu",
                        "latency_ms": 0.0
                    },
                    "status": "skipped",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "result": {},
                    "warnings": obs_warnings + [{
                        "code": "W_URL_MISSING",
                        "message": "URL analysis skipped due to missing raw URL string",
                        "artifact_ref": "url.raw"
                    }],
                    "error_details": None
                }
                stats["skipped"] += 1
            else:
                t0 = time.perf_counter()
                try:
                    pred_result = classifier.predict(raw_url)
                    latency = round((time.perf_counter() - t0) * 1000, 2)
                    status = "partial" if obs_warnings else "success"

                    envelope = {
                        "schema_version": "1.0.0",
                        "observation_id": obs_id,
                        "run_id": run_id,
                        "model": {
                            "name": classifier.model_name,
                            "version": classifier.version,
                            "modality": "url",
                            "execution_hardware": "cpu",
                            "latency_ms": latency
                        },
                        "status": status,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "result": pred_result,
                        "warnings": obs_warnings,
                        "error_details": None
                    }
                    if status == "success":
                        stats["success"] += 1
                    else:
                        stats["partial"] += 1

                except Exception as e:
                    stats["error"] += 1
                    envelope = {
                        "schema_version": "1.0.0",
                        "observation_id": obs_id,
                        "run_id": run_id,
                        "model": {
                            "name": classifier.model_name,
                            "version": classifier.version,
                            "modality": "url",
                            "execution_hardware": "cpu",
                            "latency_ms": 0.0
                        },
                        "status": "error",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "result": {},
                        "warnings": obs_warnings,
                        "error_details": {
                            "error_type": type(e).__name__,
                            "message": str(e),
                            "stack_trace": None
                        }
                    }

            stats["total_warnings"] += len(envelope["warnings"])
            f_out.write(json.dumps(envelope) + "\n")

    stats["total_duration_ms"] = round((time.perf_counter() - start_total_time) * 1000, 2)

    # Write summary metadata
    summary_path = Path(output_dir) / "run_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f_sum:
        json.dump(stats, f_sum, indent=2)

    print("\n=== Execution Summary ===")
    print(f"Observations Processed: {stats['total_read']}")
    print(f"Status Success:        {stats['success']}")
    print(f"Status Partial:        {stats['partial']}")
    print(f"Status Skipped:        {stats['skipped']}")
    print(f"Status Error:          {stats['error']}")
    print(f"Total Warnings:        {stats['total_warnings']}")
    print(f"Total Elapsed Time:    {stats['total_duration_ms']} ms")
    print(f"Outputs written to:    {output_dir}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="CYRAXI Dataset-to-Model Vertical Slice Pipeline")
    parser.add_argument("--archive", default="data/phish_sample_30k.zip", help="Path to Phishpedia zip archive")
    parser.add_argument("--output-dir", default="outputs/slice_run_01", help="Output directory for generated envelopes")
    parser.add_argument("--limit", type=int, default=30, help="Number of records to stream-process (default: 30)")
    parser.add_argument("--offset", type=int, default=0, help="Record offset to begin streaming")
    parser.add_argument("--run-id", default=f"run_{int(time.time())}", help="Unique run identifier")

    args = parser.parse_args()
    run_pipeline(
        archive_path=args.archive,
        output_dir=args.output_dir,
        limit=args.limit,
        offset=args.offset,
        run_id=args.run_id
    )


if __name__ == "__main__":
    main()
