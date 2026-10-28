# Standard Model Input/Output Contracts

**Document Version:** 1.0.0  
**Status:** Canonical Multi-Team Engineering Contract  
**Schema Reference:** `schemas/model-output.schema.json`

---

## 1. Architectural Philosophy & The Common Envelope

Every model module (URL, HTML/NLP, OCR, CV, and Multimodal Fusion) operates on an isolated container/function interface and reports its inferences wrapped in a **strict common envelope**.

Independent teammates can develop, evaluate, and test their microservices or scripts against these contracts without depending on other teammates' internal code.

### 1.1 The Common Model Output Envelope

All model outputs MUST follow this structure:

```json
{
  "schema_version": "1.0.0",
  "observation_id": "obs_6f80a42371d377b212f45c4aa305609c",
  "run_id": "run_20261010_baseline_v1",
  "model": {
    "name": "module_name",
    "version": "1.0.0",
    "modality": "url | html_nlp | ocr | computer_vision | multimodal_fusion | graph_enrichment",
    "execution_hardware": "cpu",
    "latency_ms": 42.5
  },
  "status": "success | partial | skipped | error",
  "created_at": "2026-10-10T23:50:00Z",
  "result": { ... },
  "warnings": [],
  "error_details": null
}
```

### 1.2 Execution Status Conventions

- `success`: Target artifact was available, inference completed nominally, predictions and features produced.
- `partial`: Artifact was partially corrupted, truncated, or secondary features failed, but valid partial inference was returned.
- `skipped`: Required input artifact was absent for this observation (e.g. `html.txt` or `ocr.txt` missing). The result payload is empty, and an explanatory warning is attached. No exception thrown.
- `error`: Unhandled inference crash or severe decoding error. The `error_details` block must contain error type and stack trace.

---

## 2. Module A — URL Analysis Contract

- **Module Name:** `url_feature_classifier`
- **Modality:** `url`
- **Execution Target:** CPU baseline (Scikit-Learn / LightGBM / Lexical heuristics).

### Expected Inputs
- `observation_id`: string
- `url.raw`: string (URI)
- `url.host`: string / null
- `network.ip`: string / null

### `result` Payload Specification

```json
{
  "classification": {
    "is_phishing_predicted": true,
    "confidence_score": 0.942,
    "verdict": "phishing"
  },
  "features": {
    "url_length": 45,
    "domain_length": 15,
    "subdomain_count": 0,
    "path_depth": 3,
    "entropy": 4.12,
    "num_digits": 2,
    "num_special_chars": 5,
    "is_ip_in_hostname": false,
    "has_https": false,
    "has_at_symbol": false,
    "has_suspicious_tld": false,
    "lexical_similarity_to_brands": [
      { "brand": "1&1 Ionos", "edit_distance": 8, "jaro_winkler": 0.45 }
    ]
  },
  "extracted_indicators": {
    "canonical_url": "http://serv-acamai.com/1und1/de/index.php",
    "registered_domain": "serv-acamai.com",
    "tld": "com"
  }
}
```

---

## 3. Module B — HTML & NLP Analysis Contract

- **Module Name:** `html_nlp_detector`
- **Modality:** `html_nlp`
- **Execution Target:** CPU baseline (BeautifulSoup DOM parsing + FastText/TF-IDF/Small Transformer).

### Expected Inputs
- `observation_id`: string
- `artifacts.html.relative_path`: string (or null if missing)

### Missing Artifact Handling
If `artifacts.html` is null:
- `status`: `"skipped"`
- `result`: `{}`
- `warnings`: `[{"code": "W_HTML_MISSING", "message": "HTML artifact was not captured for observation"}]`

### `result` Payload Specification (on success)

```json
{
  "classification": {
    "is_phishing_predicted": true,
    "confidence_score": 0.885,
    "verdict": "phishing"
  },
  "dom_features": {
    "title": "1&1 Kunden-Login",
    "meta_tags_count": 4,
    "form_action_count": 1,
    "forms": [
      {
        "action": "de/login.php",
        "method": "POST",
        "has_password_input": true,
        "is_action_external": false
      }
    ],
    "external_links_ratio": 0.83,
    "empty_anchor_ratio": 0.12,
    "has_obfuscated_javascript": false,
    "iframe_count": 0
  },
  "nlp_signals": {
    "detected_language": "de",
    "urgency_cues": ["sichern", "sofort"],
    "credential_harvesting_intent_score": 0.91,
    "brand_mentions": ["1&1", "Ionos"]
  }
}
```

---

## 4. Module C — OCR Analysis Contract

- **Module Name:** `ocr_text_extractor`
- **Modality:** `ocr`
- **Execution Target:** CPU baseline (PaddleOCR / Tesseract 5 / EasyOCR). Optional GPU speedup.

### Expected Inputs
- `observation_id`: string
- `artifacts.screenshot.relative_path`: string
- `artifacts.ocr.relative_path`: string (optional precomputed fallback)

### `result` Payload Specification

```json
{
  "extracted_text_raw": "1&1 Kunden-Login\nKundennummer, Nutzername oder E-Mail-Adresse\nPasswort\nEingeloggt bleiben",
  "text_character_count": 94,
  "confidence_mean": 0.941,
  "bounding_boxes": [
    {
      "text": "1&1 Kunden-Login",
      "box_2d": [19, 29, 118, 79],
      "confidence": 0.982
    },
    {
      "text": "Passwort",
      "box_2d": [130, 115, 334, 165],
      "confidence": 0.965
    }
  ],
  "extracted_credentials_keywords": ["kunden-login", "passwort", "e-mail-adresse"],
  "identified_brands": ["1&1"]
}
```

OCR `box_2d` is `[x1, y1, x2, y2]` in screenshot pixel coordinates, with the
bottom-right edge exclusive. OCR confidence values are normalized to `[0, 1]`;
`confidence_mean` is null when the source is precomputed text or no word has a
usable Tesseract confidence. Boxes are word-level when generated by Tesseract.

---

## 5. Module D — Computer Vision Analysis Contract

- **Module Name:** `cv_logo_detector`
- **Modality:** `computer_vision`
- **Execution Target:** CPU baseline (ResNet/EfficientNet embeddings + nearest neighbor logo matching; optional YOLOv8 logo locator).

### Expected Inputs
- `observation_id`: string
- `artifacts.screenshot.relative_path`: string
- `artifacts.auxiliary.yolo_coords_path`: string (precomputed boxes from Phishpedia)

### Compatibility Notice on Original Checkpoints
> [!WARNING]
> The original Phishpedia repository used older Detectron2 / Faster R-CNN or early YOLOv3/v5 PyTorch weights not included in the dataset archive. Teammates must test lightweight, modern ONNX/TorchScript weights or use the precomputed `yolo_coords.txt` bounding boxes before training custom object detectors.

### `result` Payload Specification

```json
{
  "classification": {
    "has_detected_logo": true,
    "num_candidates_found": 3
  },
  "detected_elements": [
    {
      "element_type": "logo",
      "box_2d": [0.0, 10.58, 108.88, 52.80],
      "detector_confidence": 0.991,
      "brand_matches": [
        {
          "candidate_brand": "1&1 Ionos",
          "similarity_metric": "cosine",
          "similarity_score": 0.924,
          "is_above_threshold": true
        },
        {
          "candidate_brand": "Telekom",
          "similarity_score": 0.312,
          "is_above_threshold": false
        }
      ]
    }
  ],
  "visual_identity_verdict": {
    "top_matched_brand": "1&1 Ionos",
    "top_similarity_score": 0.924,
    "confidence": 0.924
  }
}
```

CV candidate `box_2d` uses the same absolute screenshot pixel convention
`[x1, y1, x2, y2]`, with the bottom-right edge exclusive. Inspection of real
archive samples verified rows in the form `(x1, y1, x2, y2)\tconfidence`; the
four coordinates are pixel bounds and the final numeric value is a source
confidence. The parser also accepts the repository's four-value pixel fixture.
Source confidence is range-checked but not surfaced as this pipeline's detector
confidence or as a phishing probability. Other extra-column formats are
rejected. Candidate boxes do not identify a brand; brand matching requires
verified weights and a reference gallery. The archive was sampled, not
exhaustively validated.

---

## 6. Module E — Multimodal Evidence Fusion Contract

- **Module Name:** `multimodal_evidence_fusion`
- **Modality:** `multimodal_fusion`
- **Execution Target:** CPU rule & logistic evidence fusion engine.

### Fusion Principles & Thresholds
- **Configured Weights:** Weights are read from `configs/fusion_weights.yaml`, validated as finite and non-negative, and renormalized over active probability-capable modalities. Current URL and HTML/NLP scores are heuristic and uncalibrated.
- **Handling Missing Modalities:** If a modality was `skipped` (e.g. missing HTML), the fusion engine renormalizes the active weights over available modalities:
  $$W_{active} = \sum_{m \in \text{Available}} w_m, \quad w'_m = \frac{w_m}{W_{active}}$$
- **OCR/CV Evidence:** Text presence, credential-keyword indicators, logo candidate counts, and visual similarity are evidence features only. They do not contribute phishing probabilities unless a calibrated classifier is implemented and emits a compatible classification score.
- **No Unsupported Identity Claims:** Fusion does not infer brand ownership, domain authorization, or confirmed identity conflicts from the current modules.
- **Insufficient Evidence:** If no compatible URL/HTML score is available, no classification or confidence score is emitted. Evidence-only outputs use `status: "partial"` with `insufficient_evidence: true`; when no usable evidence exists, fusion uses `status: "skipped"` and an empty result.

The fusion result adds `evidence_summary` entries with `modality`, an observed signal, an optional valid `score`, and limitations. `limitations` explains score calibration and modality scope. `insufficient_evidence` indicates that the result has no phishing verdict. These are additive result fields; the canonical output envelope schema permits modality-specific result properties.

### `result` Payload Specification

The following is an illustrative baseline result. Its score is a weighted
combination of the URL and HTML/NLP model scores; it is not calibrated
probability. OCR and CV remain evidence-only.

```json
{
  "classification": {
    "is_phishing_predicted": true,
    "confidence_score": 0.6136,
    "verdict": "phishing"
  },
  "active_modalities": ["url", "html_nlp"],
  "skipped_modalities": [],
  "supporting_evidence": [
    {"modality": "url", "score": 0.75},
    {"modality": "html_nlp", "score": 0.45}
  ],
  "evidence_summary": [
    {
      "modality": "url",
      "observed_signal": "Model classified as phishing",
      "score": 0.75,
      "limitations": ["Baseline URL/HTML scores are heuristic and have not been calibrated"]
    },
    {
      "modality": "html_nlp",
      "observed_signal": "Model classified as not phishing",
      "score": 0.45,
      "limitations": ["Baseline URL/HTML scores are heuristic and have not been calibrated"]
    },
    {
      "modality": "ocr",
      "observed_signal": "OCR text available (25 characters); 1 credential-keyword indicator(s)",
      "score": null,
      "limitations": ["Text and keyword indicators are not calibrated phishing probabilities"]
    },
    {
      "modality": "computer_vision",
      "observed_signal": "1 logo candidate crop(s); brand matching not performed",
      "score": null,
      "limitations": ["Candidate counts and visual similarity are not phishing probabilities", "No brand identity was established"]
    }
  ],
  "limitations": [
    "OCR and CV signals are evidence only and do not contribute to the phishing score",
    "URL and HTML baseline scores are heuristic and uncalibrated",
    "No domain authorization or brand ownership is inferred",
    "Each modality contributes at most one score; duplicate modality outputs are ignored"
  ],
  "insufficient_evidence": false
}
```

---

## 7. Module F — Knowledge Graph Integration Contract

- **Module Name:** `graph_enrichment_mapper`
- **Modality:** `graph_enrichment`
- Translates canonical observations and upstream model envelopes into atomic Cypher mutation records (see `docs/architecture/NEO4J_DATA_MODEL.md`).
