import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "fusion_weights.yaml"
ALL_MODALITIES = ("url", "html_nlp", "ocr", "computer_vision")
PROBABILITY_MODALITIES = ("url", "html_nlp")


class FusionConfigurationError(ValueError):
    """Raised when fusion weights are absent or malformed."""


def _load_weights(config_path=None):
    """Read and validate the small weights mapping in the project YAML file.

    PyYAML is not part of this repository's dependency set. This parser accepts
    the scalar mapping used by configs/fusion_weights.yaml and rejects nested,
    duplicate, unknown, or malformed weight entries instead of guessing.
    """
    path = Path(config_path or CONFIG_PATH)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise FusionConfigurationError(
            f"Could not read fusion weights from {path}: {exc}"
        ) from exc

    in_weights = False
    found_weights = False
    weights = {}
    for line_number, raw_line in enumerate(lines, start=1):
        content = raw_line.split("#", 1)[0].rstrip()
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip())
        stripped = content.strip()

        if indent == 0:
            in_weights = stripped == "weights:"
            found_weights = found_weights or in_weights
            continue

        if not in_weights:
            continue

        if indent != 2:
            raise FusionConfigurationError(
                f"Invalid indentation in weights at {path}:{line_number}"
            )
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):\s*([^\s]+)", stripped)
        if not match:
            raise FusionConfigurationError(
                f"Invalid weight entry at {path}:{line_number}: {stripped}"
            )
        name, raw_value = match.groups()
        if name not in ALL_MODALITIES:
            raise FusionConfigurationError(
                f"Unknown modality weight '{name}' at {path}:{line_number}"
            )
        if name in weights:
            raise FusionConfigurationError(
                f"Duplicate modality weight '{name}' at {path}:{line_number}"
            )
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise FusionConfigurationError(
                f"Weight for {name} must be a finite non-negative number"
            ) from exc
        if not math.isfinite(value) or value < 0:
            raise FusionConfigurationError(
                f"Weight for {name} must be a finite non-negative number"
            )
        weights[name] = value

    if not found_weights:
        raise FusionConfigurationError(f"Missing 'weights:' mapping in {path}")
    missing = [name for name in ALL_MODALITIES if name not in weights]
    if missing:
        raise FusionConfigurationError(
            "Missing modality weights: " + ", ".join(missing)
        )
    if sum(weights[name] for name in PROBABILITY_MODALITIES) <= 0:
        raise FusionConfigurationError(
            "At least one probability-capable modality weight must be positive"
        )
    if not math.isfinite(sum(weights[name] for name in PROBABILITY_MODALITIES)):
        raise FusionConfigurationError(
            "Probability-capable modality weights have a non-finite total"
        )
    return weights


def _warning(code, message, artifact_ref=None):
    return {"code": code, "message": message, "artifact_ref": artifact_ref}


def _evidence_for(modality, output):
    result = output.get("result") or {}
    if not isinstance(result, dict):
        result = {}
    classification = result.get("classification") or {}
    if not isinstance(classification, dict):
        classification = {}
    score = None
    limitations = []

    if modality in PROBABILITY_MODALITIES:
        raw_score = classification.get("confidence_score")
        predicted = classification.get("is_phishing_predicted")
        try:
            numeric_score = float(raw_score)
        except (TypeError, ValueError, OverflowError):
            numeric_score = float("nan")
        if (
            isinstance(raw_score, (int, float))
            and not isinstance(raw_score, bool)
            and math.isfinite(numeric_score)
            and 0 <= numeric_score <= 1
            and isinstance(predicted, bool)
        ):
            score = numeric_score
            observed = (
                f"Model classified as {'phishing' if predicted else 'not phishing'}"
            )
        else:
            observed = "No compatible classification probability was supplied"
            limitations.append(
                "Requires a finite confidence_score in [0, 1] and a boolean prediction"
            )
        limitations.append(
            "Baseline URL/HTML scores are heuristic and have not been calibrated"
        )
        if modality == "url":
            features = result.get("features") or {}
            if isinstance(features, dict):
                indicators = []
                if features.get("has_ip_in_host") is True:
                    indicators.append("IP address in host")
                if features.get("has_at_symbol") is True:
                    indicators.append("@ character in URL")
                if indicators:
                    observed += "; observed: " + ", ".join(indicators)
        else:
            dom = result.get("dom_features") or {}
            nlp = result.get("nlp_signals") or {}
            if isinstance(dom, dict):
                forms = dom.get("forms") or []
                if isinstance(forms, list) and any(
                    isinstance(form, dict) and form.get("has_password_input") is True
                    for form in forms
                ):
                    observed += "; password form present"
            if isinstance(nlp, dict):
                cues = nlp.get("urgency_cues") or []
                if isinstance(cues, list) and cues:
                    observed += f"; {len(cues)} urgency cue(s)"
    elif modality == "ocr":
        text_length = result.get("text_character_count")
        text_available = (
            isinstance(text_length, int)
            and not isinstance(text_length, bool)
            and text_length > 0
        )
        keywords = result.get("extracted_credentials_keywords") or []
        keyword_count = len(keywords) if isinstance(keywords, list) else 0
        observed = (
            f"OCR text available ({text_length} characters); "
            f"{keyword_count} credential-keyword indicator(s)"
            if text_available else "No OCR text available"
        )
        limitations.append(
            "Text and keyword indicators are not calibrated phishing probabilities"
        )
    else:
        elements = result.get("detected_elements") or []
        if not isinstance(elements, list):
            elements = []
        brand_performed = result.get("brand_match_performed") is True
        observed = (
            f"{len(elements)} logo candidate crop(s); "
            f"brand matching {'performed' if brand_performed else 'not performed'}"
        )
        limitations.append(
            "Candidate counts and visual similarity are not phishing probabilities"
        )
        if not brand_performed:
            limitations.append("No brand identity was established")

    return {
        "modality": modality,
        "observed_signal": observed,
        "score": round(score, 4) if score is not None else None,
        "limitations": limitations,
    }, score


def _base_envelope(observation_id, run_id, started, status, result, warnings, error=None):
    return {
        "schema_version": "1.0.0",
        "observation_id": observation_id,
        "run_id": run_id,
        "model": {
            "name": "multimodal_evidence_fusion",
            "version": "1.1.0",
            "modality": "multimodal_fusion",
            "execution_hardware": "cpu",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        },
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "warnings": warnings,
        "error_details": error,
    }


def fuse_predictions(observation_id, run_id, outputs):
    """Fuse compatible URL/HTML probabilities and report other evidence only."""
    started = time.perf_counter()
    try:
        weights = _load_weights()
    except FusionConfigurationError as exc:
        warning = _warning(
            "W_FUSION_CONFIG_INVALID",
            str(exc),
            "configs/fusion_weights.yaml",
        )
        return _base_envelope(
            observation_id,
            run_id,
            started,
            "error",
            {},
            [warning],
            {
                "error_type": type(exc).__name__,
                "message": str(exc),
                "stack_trace": None,
            },
        )

    warnings = []
    seen = set()
    evidence_summary = []
    probability_scores = []
    skipped = []

    for output in outputs or []:
        if not isinstance(output, dict):
            warnings.append(_warning(
                "W_INVALID_MODALITY_OUTPUT",
                "Ignored a modality output that was not an object",
            ))
            continue

        model_info = output.get("model")
        modality = model_info.get("modality") if isinstance(model_info, dict) else None
        if modality not in ALL_MODALITIES:
            warnings.append(_warning(
                "W_INVALID_MODALITY_OUTPUT",
                f"Ignored output with unsupported modality {modality!r}",
            ))
            continue
        if output.get("observation_id") != observation_id:
            warnings.append(_warning(
                "W_OBSERVATION_ID_MISMATCH",
                f"Ignored {modality} output for another observation",
            ))
            continue
        if output.get("run_id") != run_id:
            warnings.append(_warning(
                "W_RUN_ID_MISMATCH",
                f"Ignored {modality} output from another run",
            ))
            continue
        if modality in seen:
            warnings.append(_warning(
                "W_DUPLICATE_MODALITY_OUTPUT",
                f"Ignored duplicate output for modality {modality}",
            ))
            continue
        seen.add(modality)

        upstream_warnings = output.get("warnings") or []
        if isinstance(upstream_warnings, list):
            for item in upstream_warnings:
                if not isinstance(item, dict) or not isinstance(item.get("code"), str):
                    continue
                message = item.get("message")
                if not isinstance(message, str):
                    continue
                artifact_ref = item.get("artifact_ref")
                if not isinstance(artifact_ref, str):
                    artifact_ref = None
                warnings.append(_warning(
                    item["code"],
                    f"{modality}: {message}",
                    artifact_ref,
                ))

        status = output.get("status")
        if status not in ("success", "partial"):
            skipped.append(modality)
            warnings.append(_warning(
                "W_MODALITY_UNAVAILABLE",
                f"{modality} output status was {status!r}",
            ))
            continue

        evidence, score = _evidence_for(modality, output)
        evidence_summary.append(evidence)
        if modality in PROBABILITY_MODALITIES:
            if score is None:
                warnings.append(_warning(
                    "W_INVALID_MODALITY_SCORE",
                    f"{modality} output did not contain a compatible classification probability",
                ))
                skipped.append(modality)
            elif weights[modality] <= 0:
                warnings.append(_warning(
                    "W_MODALITY_ZERO_WEIGHT",
                    f"{modality} has a valid score but its configured weight is zero",
                ))
                skipped.append(modality)
            else:
                probability_scores.append((modality, score, weights[modality]))

    for modality in ALL_MODALITIES:
        if modality not in seen:
            skipped.append(modality)
            warnings.append(_warning(
                "W_MODALITY_MISSING",
                f"No {modality} output was supplied",
            ))

    active_weight = sum(weight for _, _, weight in probability_scores)
    active_modalities = [modality for modality, _, _ in probability_scores]
    limitations = [
        "OCR and CV signals are evidence only and do not contribute to the phishing score",
        "URL and HTML baseline scores are heuristic and uncalibrated",
        "No domain authorization or brand ownership is inferred",
        "Each modality contributes at most one score; duplicate modality outputs are ignored",
    ]

    if active_weight > 0:
        score = sum(
            value * (weight / active_weight)
            for _, value, weight in probability_scores
        )
        predicted = score >= 0.5
        result = {
            "classification": {
                "is_phishing_predicted": predicted,
                "confidence_score": round(score, 4),
                "verdict": "phishing" if predicted else "not_phishing",
            },
            "active_modalities": active_modalities,
            "skipped_modalities": sorted(set(skipped)),
            "supporting_evidence": [
                {"modality": modality, "score": round(value, 4)}
                for modality, value, _ in probability_scores
            ],
            "evidence_summary": evidence_summary,
            "limitations": limitations,
            "insufficient_evidence": False,
        }
        status = "partial" if warnings or skipped else "success"
    elif evidence_summary:
        result = {
            "active_modalities": [],
            "skipped_modalities": sorted(set(skipped)),
            "supporting_evidence": [],
            "evidence_summary": evidence_summary,
            "limitations": limitations,
            "insufficient_evidence": True,
        }
        warnings.append(_warning(
            "W_FUSION_INSUFFICIENT_EVIDENCE",
            "Evidence was observed, but no compatible phishing probability was available; no verdict was produced",
        ))
        status = "partial"
    else:
        result = {}
        warnings.append(_warning(
            "W_FUSION_INSUFFICIENT_EVIDENCE",
            "No usable modality evidence or compatible phishing probability was available",
        ))
        status = "skipped"

    return _base_envelope(
        observation_id,
        run_id,
        started,
        status,
        result,
        warnings,
    )
