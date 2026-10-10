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

---

## 6. Module E — Multimodal Evidence Fusion Contract

- **Module Name:** `multimodal_evidence_fusion`
- **Modality:** `multimodal_fusion`
- **Execution Target:** CPU rule & logistic evidence fusion engine.

### Fusion Principles & Thresholds
- **No Arbitrary Hardcoding:** All weights ($w_{url}, w_{dom}, w_{cv}, w_{ocr}$) are managed via external configuration files (`configs/fusion_weights.yaml`) and must undergo cross-validation.
- **Handling Missing Modalities:** If a modality was `skipped` (e.g. missing HTML), the fusion engine renormalizes the active weights over available modalities:
  $$W_{active} = \sum_{m \in \text{Available}} w_m, \quad w'_m = \frac{w_m}{W_{active}}$$
- **Identity Consistency Check:** Phishing is confirmed when the visual target brand (from CV/OCR) conflicts with the domain brand authority (from URL/Whois/Registered Domain).

### `result` Payload Specification

```json
{
  "final_verdict": {
    "classification": "phishing",
    "confidence_score": 0.958,
    "is_phishing": true,
    "threat_level": "critical"
  },
  "targeted_brand_consensus": {
    "identified_brand": "1&1 Ionos",
    "confidence": 0.924,
    "cross_modal_agreement": true
  },
  "identity_conflict_assessment": {
    "claimed_brand": "1&1 Ionos",
    "actual_registered_domain": "serv-acamai.com",
    "is_authorized_domain": false,
    "brand_domain_mismatch_detected": true
  },
  "evidence_summary": {
    "supporting_evidence": [
      {
        "modality": "computer_vision",
        "description": "Visual logo matched '1&1 Ionos' with 92.4% similarity.",
        "weight_contribution": 0.38
      },
      {
        "modality": "url",
        "description": "Domain 'serv-acamai.com' lacks authority for '1&1 Ionos'.",
        "weight_contribution": 0.32
      },
      {
        "modality": "html_nlp",
        "description": "Credential harvesting form detected on unverified domain.",
        "weight_contribution": 0.25
      }
    ],
    "conflicting_evidence": [],
    "active_modalities": ["url", "html_nlp", "ocr", "computer_vision"],
    "omitted_modalities": []
  }
}
```

---

## 7. Module F — Knowledge Graph Integration Contract

- **Module Name:** `graph_enrichment_mapper`
- **Modality:** `graph_enrichment`
- Translates canonical observations and upstream model envelopes into atomic Cypher mutation records (see `docs/architecture/NEO4J_DATA_MODEL.md`).
