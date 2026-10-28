import argparse
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.dataset_adapter.reader import PhishpediaDatasetReader
from modules.dataset_adapter.artifacts import (
    read_artifact,
    read_artifact_bytes,
)
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
    raise TypeError(f"Unsupported model output type: {type(result).__name__}")


def get_artifact_text(archive_path, observation, artifact_name):
    """Read a text artifact by its canonical manifest-relative path."""
    try:
        content = read_artifact(archive_path, observation, artifact_name)
        return content or ""
    except (FileNotFoundError, KeyError, OSError, TypeError, ValueError):
        return ""


def get_artifact_bytes(archive_path, observation, artifact_name):
    """Read bytes by canonical manifest-relative path without ZIP extraction."""
    try:
        return read_artifact_bytes(archive_path, observation, artifact_name)
    except (FileNotFoundError, KeyError, OSError, TypeError, ValueError):
        return None


def _error_output(observation_id, run_id, modality, exc, code="E_MODULE_EXECUTION"):
    return {
        "schema_version": "1.0.0",
        "observation_id": observation_id,
        "run_id": run_id,
        "model": {
            "name": f"{modality}_pipeline",
            "version": "1.0.0",
            "modality": modality,
            "execution_hardware": "cpu",
            "latency_ms": 0.0,
        },
        "status": "error",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": {},
        "warnings": [{
            "code": code,
            "message": f"{modality} output could not be used: {type(exc).__name__}",
            "artifact_ref": None,
        }],
        "error_details": {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "stack_trace": None,
        },
    }


def _run_module(function, modality, observation_id, run_id):
    try:
        output = to_dict(function())
        if output.get("observation_id") != observation_id:
            raise ValueError("module returned a mismatched observation_id")
        if output.get("run_id") != run_id:
            raise ValueError("module returned a mismatched run_id")
        output_modality = (output.get("model") or {}).get("modality")
        if output_modality != modality:
            raise ValueError(
                f"module returned modality {output_modality!r}, expected {modality!r}"
            )
        # Reject NaN, infinity, and non-JSON payloads before they can corrupt
        # the JSONL stream; the caller emits a per-module error envelope.
        json.dumps(output, allow_nan=False)
        return output
    except Exception as exc:
        return _error_output(observation_id, run_id, modality, exc)


def _json_line(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def _write_atomic(path, content):
    """Write a sibling temporary file then atomically replace the destination."""
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            if isinstance(content, str):
                stream.write(content)
            else:
                for chunk in content:
                    stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _iter_pipeline_output_lines(archive_path, limit, offset, run_id, counts):
    url_service = URLAnalysisService()
    reader = PhishpediaDatasetReader(str(archive_path))

    for observation in reader.stream_observations(limit=limit, offset=offset):
        observation_id = observation.get("observation_id")
        if not isinstance(observation_id, str):
            counts["observations"] += 1
            counts["errors"] += 1
            # A missing ID cannot produce a valid model-output envelope. Keep
            # the malformed observation out of JSONL and surface it in counts.
            continue

        url = (observation.get("url") or {}).get("raw", "") or ""
        html_text = get_artifact_text(archive_path, observation, "html")
        ocr_text = get_artifact_text(archive_path, observation, "ocr")
        screenshot_bytes = get_artifact_bytes(
            archive_path, observation, "screenshot"
        )
        coordinates_text = get_artifact_text(
            archive_path, observation, "yolo_coords"
        )

        url_output = _run_module(
            lambda: url_service.analyze(
                raw_url=url,
                observation_id=observation_id,
                run_id=run_id,
            ),
            "url", observation_id, run_id,
        )
        html_output = _run_module(
            lambda: analyze_html(
                observation_id, run_id, html_text, url
            ),
            "html_nlp", observation_id, run_id,
        )
        ocr_output = _run_module(
            lambda: extract_ocr(
                observation_id,
                run_id,
                ocr_text=ocr_text,
                screenshot_bytes=screenshot_bytes,
            ),
            "ocr", observation_id, run_id,
        )
        cv_output = _run_module(
            lambda: detect_logo_candidates(
                observation_id,
                run_id,
                coordinates_text=coordinates_text,
                screenshot_bytes=screenshot_bytes,
            ),
            "computer_vision", observation_id, run_id,
        )

        upstream_outputs = [url_output, html_output, ocr_output, cv_output]
        fusion_output = _run_module(
            lambda: fuse_predictions(observation_id, run_id, upstream_outputs),
            "multimodal_fusion", observation_id, run_id,
        )
        outputs = upstream_outputs + [fusion_output]

        for result in outputs:
            modality = (result.get("model") or {}).get("modality", "")
            status = result.get("status", "error")
            if status == "error":
                counts["errors"] += 1
            if status in ("success", "partial"):
                key = {
                    "url": "url_success",
                    "html_nlp": "html_success",
                    "ocr": "ocr_success",
                    "computer_vision": "cv_success",
                    "multimodal_fusion": "fusion_success",
                }.get(modality)
                if key:
                    counts[key] += 1
            if modality == "multimodal_fusion" and status == "skipped":
                counts["fusion_skipped"] += 1
            yield _json_line(result)
        counts["observations"] += 1


def run_pipeline(archive_path, output_dir, limit=10, offset=0, run_id=None):
    archive_path = Path(archive_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
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

    _write_atomic(
        output_path,
        _iter_pipeline_output_lines(
            archive_path, limit, offset, run_id, counts
        ),
    )
    summary = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_archive": str(archive_path),
        "limit": limit,
        "offset": offset,
        "counts": counts,
        "model_outputs_file": str(output_path),
    }
    _write_atomic(
        summary_path,
        json.dumps(
            summary,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        ) + "\n",
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
        parser.error("--limit must be positive and --offset non-negative")

    try:
        summary = run_pipeline(
            args.archive,
            args.output_dir,
            args.limit,
            args.offset,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Pipeline could not start: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
