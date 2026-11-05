"""
Runtime JSON Schema Validation Service
Validates observations, model output envelopes, and investigation reports
against the canonical JSON schemas in the schemas/ directory.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema

SCHEMA_DIR = Path(__file__).resolve().parent

_VALIDATORS: Dict[str, jsonschema.Draft202012Validator] = {}


def _get_validator(schema_filename: str) -> Optional[jsonschema.Draft202012Validator]:
    """Retrieve or compile the validator for a given schema file."""
    if schema_filename in _VALIDATORS:
        return _VALIDATORS[schema_filename]

    schema_path = SCHEMA_DIR / schema_filename
    if not schema_path.exists():
        return None

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_data = json.load(f)
        validator = jsonschema.Draft202012Validator(schema_data)
        _VALIDATORS[schema_filename] = validator
        return validator
    except Exception:
        return None


def validate_schema(data: Dict[str, Any], schema_filename: str) -> Tuple[bool, List[str]]:
    """
    Validate data dictionary against schema_filename.
    Returns (is_valid, list_of_error_messages).
    """
    validator = _get_validator(schema_filename)
    if validator is None:
        return True, [f"Warning: Schema file {schema_filename} not available for validation."]

    errors = []
    for err in validator.iter_errors(data):
        field_path = ".".join(str(p) for p in err.path) if err.path else "root"
        errors.append(f"{field_path}: {err.message}")

    return len(errors) == 0, errors


def validate_observation(obs: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a canonical observation against schemas/observation.schema.json."""
    return validate_schema(obs, "observation.schema.json")


def validate_model_output(envelope: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a model output envelope against schemas/model-output.schema.json."""
    return validate_schema(envelope, "model-output.schema.json")


def validate_investigation_report(report: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate an investigation report against schemas/investigation-report.schema.json."""
    return validate_schema(report, "investigation-report.schema.json")
