#!/usr/bin/env python3
"""
Lightweight schema and example validation script.
Validates JSON syntax, schema structure, and sample instance conformity without heavy external dependencies.
"""
import json
import re
from pathlib import Path

def validate_json_file(file_path: Path):
    print(f"Validating JSON syntax: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def validate_observation(sample: dict, schema: dict):
    print("Validating sample_observation.json against observation.schema.json...")
    required_fields = schema.get("required", [])
    for field in required_fields:
        assert field in sample, f"Missing required top-level field: {field}"
    
    # Check ID pattern
    id_pattern = schema["properties"]["observation_id"]["pattern"]
    assert re.match(id_pattern, sample["observation_id"]), f"observation_id {sample['observation_id']} does not match pattern {id_pattern}"
    
    # Check dataset
    assert sample["dataset"]["dataset_id"] in ["phishpedia_primary", "benign_reference", "external_feed"]
    
    # Check label ground truth
    label = sample["label"]["ground_truth"]
    assert label["normalized_label"] in ["phishing", "benign", "suspicious", "unknown"]
    
    # Check artifacts
    assert "screenshot" in sample["artifacts"]
    assert "metadata_annotation" in sample["artifacts"]
    
    # Check availability booleans
    avail = sample["availability"]
    for k in ["has_screenshot", "has_html", "has_ocr", "has_metadata"]:
        assert isinstance(avail[k], bool), f"availability.{k} must be boolean"
    
    print("[OK] sample_observation.json passed validation!")

def validate_model_output(sample: dict, schema: dict):
    print("Validating sample_model_output.json against model-output.schema.json...")
    required_fields = schema.get("required", [])
    for field in required_fields:
        assert field in sample, f"Missing required top-level field: {field}"
    
    # Check status enum
    status_enums = schema["properties"]["status"]["enum"]
    assert sample["status"] in status_enums, f"Status {sample['status']} not in {status_enums}"
    
    # Check model
    model = sample["model"]
    assert model["modality"] in ["url", "html_nlp", "ocr", "computer_vision", "multimodal_fusion", "graph_enrichment"]
    
    # Check observation_id pattern
    id_pattern = schema["properties"]["observation_id"]["pattern"]
    assert re.match(id_pattern, sample["observation_id"]), f"observation_id does not match pattern {id_pattern}"
    
    print("[OK] sample_model_output.json passed validation!")

def main():
    base_dir = Path(__file__).resolve().parent.parent
    obs_schema_path = base_dir / "schemas" / "observation.schema.json"
    model_schema_path = base_dir / "schemas" / "model-output.schema.json"
    sample_obs_path = base_dir / "examples" / "sample_observation.json"
    sample_model_path = base_dir / "examples" / "sample_model_output.json"
    
    obs_schema = validate_json_file(obs_schema_path)
    model_schema = validate_json_file(model_schema_path)
    sample_obs = validate_json_file(sample_obs_path)
    sample_model = validate_json_file(sample_model_path)
    
    validate_observation(sample_obs, obs_schema)
    validate_model_output(sample_model, model_schema)
    print("\nAll JSON schemas and sample payloads validated successfully!")

if __name__ == "__main__":
    main()
