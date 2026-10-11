import time
from datetime import datetime, timezone


WEIGHTS = {
    "url": 0.35,
    "html_nlp": 0.25,
    "ocr": 0.20,
    "computer_vision": 0.20,
}


def fuse_predictions(observation_id, run_id, outputs):
    started = time.perf_counter()

    active = []
    skipped = []
    warnings = []

    for output in outputs:
        if output.get("observation_id") != observation_id:
            warnings.append({
                "code": "W_OBSERVATION_ID_MISMATCH",
                "message": "Ignored a prediction for another observation",
                "artifact_ref": None,
            })
            continue

        modality = output.get("model", {}).get("modality")
        if modality not in WEIGHTS:
            continue

        if output.get("status") not in ("success", "partial"):
            skipped.append(modality)
            continue

        classification = output.get("result", {}).get(
            "classification", {}
        )

        # OCR/CV without a calibrated classifier cannot contribute
        # a probability to the fusion score.
        score = classification.get("confidence_score")
        if score is None:
            continue

        if not isinstance(score, (int, float)) or not 0 <= score <= 1:
            warnings.append({
                "code": "W_INVALID_MODALITY_SCORE",
                "message": f"Invalid score from modality {modality}",
                "artifact_ref": None,
            })
            continue

        active.append((modality, float(score)))

    weight_total = sum(WEIGHTS[name] for name, _ in active)

    if not active or weight_total == 0:
        status = "skipped"
        result = {}
        warnings.append({
            "code": "W_NO_USABLE_MODALITY_SCORES",
            "message": "No compatible modality probabilities were available",
            "artifact_ref": None,
        })
    else:
        score = sum(
            WEIGHTS[name] * value for name, value in active
        ) / weight_total

        result = {
            "classification": {
                "is_phishing_predicted": score >= 0.5,
                "confidence_score": round(score, 4),
                "verdict": "phishing" if score >= 0.5 else "not_phishing",
            },
            "active_modalities": [name for name, _ in active],
            "skipped_modalities": skipped,
            "supporting_evidence": [
                {
                    "modality": name,
                    "score": round(value, 4),
                }
                for name, value in active
            ],
        }
        status = "partial" if skipped or warnings else "success"

    return {
        "schema_version": "1.0.0",
        "observation_id": observation_id,
        "run_id": run_id,
        "model": {
            "name": "multimodal_evidence_fusion",
            "version": "1.0.0",
            "modality": "multimodal_fusion",
            "execution_hardware": "cpu",
            "latency_ms": round(
                (time.perf_counter() - started) * 1000, 2
            ),
        },
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "warnings": warnings,
        "error_details": None,
    }
