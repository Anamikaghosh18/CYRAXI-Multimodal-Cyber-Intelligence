# Multimodal Cybercrime Intelligence Platform: Data Contracts Guide

**Document Status:** Core Collaborative Standard  
**Audience:** Platform Engineers, Data Scientists, Model Developers  
**Scope:** Universal schema, model input/output contracts, and team conventions  

---

## 1. Quick Navigation

- **Canonical Observation Schema:** [`schemas/observation.schema.json`](../../schemas/observation.schema.json)
- **Model Output Envelope Schema:** [`schemas/model-output.schema.json`](../../schemas/model-output.schema.json)
- **Phishpedia Manifest Spec:** [`docs/dataset/PHISHPEDIA_MANIFEST_SPEC.md`](../dataset/PHISHPEDIA_MANIFEST_SPEC.md)
- **Model Module Contracts:** [`docs/contracts/MODEL_CONTRACTS.md`](./MODEL_CONTRACTS.md)
- **Neo4j Graph Model:** [`docs/architecture/NEO4J_DATA_MODEL.md`](../architecture/NEO4J_DATA_MODEL.md)
- **Dataset Findings & Open Questions:** [`docs/dataset/DATASET_FINDINGS_AND_OPEN_QUESTIONS.md`](../dataset/DATASET_FINDINGS_AND_OPEN_QUESTIONS.md)
- **Implementation Plan:** [`docs/IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md)

---

## 2. Identifier Conventions & Key Generation

All entities in the platform share strict deterministic identifiers to ensure idempotency across distributed nodes:

| Entity | Identifier Format | Generation Strategy | Example |
|---|---|---|---|
| **Observation** | `obs_<hash>` | `obs_` + `md5(dataset_id + ":" + source_record_id)` | `obs_6f80a42371d377b212f45c4aa305609c` |
| **URL** | `url_<hash>` | `url_` + `sha256(canonical_url)` | `url_3a18e001851e3c837...` |
| **Model Run** | `run_<timestamp>_<tag>` | Human/timestamp string | `run_20261010_url_baseline_v1` |
| **Evidence** | `evi_<hash>` | `evi_` + `md5(observation_id + ":" + metric)` | `evi_9a8bc431...` |
| **Brand** | `slug` | Lowercase alphanumeric snake_case | `1_1_ionos`, `paypal_inc` |

---

## 3. Ground Truth vs. Model Prediction Separation

- **Ground Truth:** Lives strictly in `Observation.label.ground_truth`. Never mutate or overwrite this based on model predictions.
- **Model Prediction:** Lives strictly inside `ModelOutputEnvelope.result.classification` and Neo4j `Prediction` nodes.
- Preserving original provenance prevents data pollution and ensures reproducible benchmark evaluations.

---

## 4. Handling Missing Artifacts

Modality coverage is not uniform:
- Screenshots (`shot.png`) exist for 100% of observations.
- HTML (`html.txt`) exists for 98.48% (448 missing).
- OCR (`ocr.txt`) exists for only 14.66% (25,171 missing).

**Rule for Model Developers:**
When an artifact is missing for a given observation:
1. Set envelope `status: "skipped"`.
2. Set `result: {}`.
3. Append a warning with code `W_<MODALITY>_MISSING` and a descriptive message.
4. **Never raise an unhandled exception or crash the pipeline.**

---

## 5. Proposing Schema Changes & Contract Evolution

1. All schemas follow Semantic Versioning (`MAJOR.MINOR.PATCH`).
2. Additive, backwards-compatible fields increment `MINOR` (e.g., `1.1.0`).
3. Renaming or removing fields increments `MAJOR` (e.g., `2.0.0`) and requires architectural review.
4. To propose a change:
   - Edit the corresponding schema in `schemas/`.
   - Update `examples/` to reflect valid changes.
   - Run `python scripts/validate_schemas.py` to confirm zero lint or validation failures before opening a pull request.
