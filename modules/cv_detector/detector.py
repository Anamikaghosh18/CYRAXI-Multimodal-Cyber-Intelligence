import time
from datetime import datetime, timezone


def detect_logo_candidates(observation_id, run_id, coordinates_text=None):
    started = time.perf_counter()

    if not coordinates_text or not coordinates_text.strip():
        return {
            "schema_version": "1.0.0",
            "observation_id": observation_id,
            "run_id": run_id,
            "model": {
                "name": "cv_logo_detector",
                "version": "1.0.0",
                "modality": "computer_vision",
                "execution_hardware": "cpu",
                "latency_ms": 0.0,
            },
            "status": "skipped",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": {},
            "warnings": [{
                "code": "W_CV_COORDINATES_MISSING",
                "message": "No precomputed logo coordinates were supplied",
                "artifact_ref": "artifacts.auxiliary.yolo_coords_path",
            }],
            "error_details": None,
        }

    boxes = []
    warnings = []

    for line_number, line in enumerate(
        coordinates_text.splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue

        try:
            values = [float(value) for value in line.split()]
            if len(values) < 4:
                raise ValueError("Expected at least four coordinates")

            boxes.append({
                "coordinates": values[:4],
                "extra_values": values[4:],
            })
        except ValueError:
            warnings.append({
                "code": "W_CV_INVALID_COORDINATE_LINE",
                "message": f"Could not parse line {line_number}",
                "artifact_ref": "yolo_coords.txt",
            })

    return {
        "schema_version": "1.0.0",
        "observation_id": observation_id,
        "run_id": run_id,
        "model": {
            "name": "cv_logo_detector",
            "version": "1.0.0",
            "modality": "computer_vision",
            "execution_hardware": "cpu",
            "latency_ms": round(
                (time.perf_counter() - started) * 1000, 2
            ),
        },
        "status": "partial" if warnings else "success",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": {
            "logo_candidates": boxes,
            "candidate_count": len(boxes),
            "identified_brands": [],
            "brand_match_performed": False,
        },
        "warnings": warnings,
        "error_details": None,
    }
