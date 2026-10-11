
import argparse
import json
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.dataset_adapter.reader import PhishpediaDatasetReader
from modules.dataset_adapter.artifacts import read_artifact
from modules.url_analyzer.service import URLAnalysisService
from modules.html_analyzer.analyzer import analyze_html
from modules.ocr_extractor.extractor import extract_ocr
from modules.cv_detector.detector import detect_logo_candidates
from modules.fusion_engine.fusion import fuse_predictions


def to_dict(result):
    """Convert Pydantic envelopes or dictionaries to JSON-compatible dictionaries."""
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if isinstance(result, dict):
        return result
    raise TypeError(
        f"Unsupported model output type: {type(result).__name__}"
    )


def get_artifact_text(archive_path, observation, artifact_name):
    """Read an artifact without extracting the dataset archive."""
    try:
        content = read_artifact(
            archive_path, observation, artifact_name
        )
        return content or ""
    except (FileNotFoundError, KeyError, OSError, ValueError):
        return ""


def run_pipeline(archive_path, output_dir, limit=10, offset=0):
    archive_path = Path(archive_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    output_path = output_dir / "model_outputs.jsonl"
    summary_path = output_dir / "run_summary.json"

    counts = {
        "observations": 0,
        "url_success": 0,
        "html_success": 0,
        "ocr_success": 0,
        "cv_success": 0,
        "fusion_success": 0,
        "fusion_skipped": 0,
        "errors": 0,
    }

    # Initialize the URL service once and reuse it for all observations.
    url_service = URLAnalysisService()

    reader = PhishpediaDatasetReader(str(archive_path))

    with output_path.open("w", encoding="utf-8") as output_file:
        for observation in reader.stream_observations(
            limit=limit, offset=offset
        ):
            observation_id = observation["observation_id"]
            url = observation.get("url", {}).get("raw", "") or ""

            # Read artifacts directly from the ZIP; do not extract the archive.
            html_text = get_artifact_text(
                archive_path, observation, "html"
            )
            ocr_text = get_artifact_text(
                archive_path, observation, "ocr"
            )
            coordinates_text = get_artifact_text(
                archive_path, observation, "yolo_coords"
            )

            # URLAnalysisService returns a Pydantic envelope.
            url_output = url_service.analyze(
                raw_url=url,
                observation_id=observation_id,
                run_id=run_id,
            )
            url_output = to_dict(url_output)

            # Other modules are expected to return dictionaries or Pydantic
            # envelopes following the project's model-output contract.
            html_output = to_dict(
                analyze_html(
                    observation_id, run_id, html_text, url
                )
            )
            ocr_output = to_dict(
                extract_ocr(
                    observation_id, run_id, ocr_text
                )
            )
            cv_output = to_dict(
                detect_logo_candidates(
                    observation_id, run_id, coordinates_text
                )
            )

            outputs = [
                url_output,
                html_output,
                ocr_output,
                cv_output,
            ]

            fusion_output = to_dict(
                fuse_predictions(
                    observation_id, run_id, outputs
                )
            )
            outputs.append(fusion_output)

            for result in outputs:
                model_info = result.get("model", {})
                modality = model_info.get("modality", "")
                status = result.get("status", "error")

                if status == "error":
                    counts["errors"] += 1

                if status in ("success", "partial"):
                    if modality == "url":
                        counts["url_success"] += 1
                    elif modality == "html_nlp":
                        counts["html_success"] += 1
                    elif modality == "ocr":
                        counts["ocr_success"] += 1
                    elif modality == "computer_vision":
                        counts["cv_success"] += 1
                    elif modality == "multimodal_fusion":
                        counts["fusion_success"] += 1

                if (
                    modality == "multimodal_fusion"
                    and status == "skipped"
                ):
                    counts["fusion_skipped"] += 1

                output_file.write(
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        default=str,
                    ) + "\n"
                )

            counts["observations"] += 1

    summary = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_archive": str(archive_path),
        "limit": limit,
        "offset": offset,
        "counts": counts,
        "model_outputs_file": str(output_path),
    }

    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Run the CYRAXI multimodal baseline pipeline."
    )
    parser.add_argument(
        "--archive",
        default="data/phish_sample_30k.zip",
        help="Path to the dataset ZIP archive.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/multimodal_run",
        help="Directory for JSONL outputs and summary.",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)

    args = parser.parse_args()

    if args.limit < 1 or args.offset < 0:
        parser.error(
            "--limit must be positive and --offset non-negative"
        )

    try:
        summary = run_pipeline(
            args.archive,
            args.output_dir,
            args.limit,
            args.offset,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(
            f"Pipeline could not start: {exc}",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
