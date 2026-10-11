# CYRAXI URL Analysis Pipeline: Engineering & Integration Guide

**Document Status:** Production Baseline  
**Architecture Pattern:** SOLID Principles / Layered Architecture / OpenAPI 3.1  
**Schema Compliance:** [`schemas/model-output.schema.json`](../../schemas/model-output.schema.json)  

---

## 1. Architectural Architecture & SOLID Compliance

The URL Analysis module is built following software engineering best practices:

- **Single Responsibility Principle (SRP):**
  - [`StandardURLFeatureExtractor`](file:///c:/Desktop/cyraxi/modules/url_analyzer/domain/extractor.py): Pure feature extraction and character entropy calculations.
  - [`HeuristicURLClassifier`](file:///c:/Desktop/cyraxi/modules/url_analyzer/models/heuristic_baseline.py): Rule-based baseline logic.
  - [`SklearnURLClassifier`](file:///c:/Desktop/cyraxi/modules/url_analyzer/models/ml_models.py): Machine learning probability inference.
  - [`URLAnalysisService`](file:///c:/Desktop/cyraxi/modules/url_analyzer/service.py): Pipeline orchestration and envelope generation.
- **Open-Closed Principle (OCP):**
  - New models (e.g. LightGBM, Transformer, or Graph neural net) implement [`IURLClassifier`](file:///c:/Desktop/cyraxi/modules/url_analyzer/domain/interfaces.py) without modifying existing service code.
- **Liskov Substitution Principle (LSP):**
  - Baseline, Logistic Regression, Random Forest, and Ensemble are mutually swappable in any service or API endpoint.
- **Interface Segregation Principle (ISP):**
  - Extractor and classifier contracts are segregated into focused interfaces.
- **Dependency Inversion Principle (DIP):**
  - High-level orchestration depends on abstract interfaces (`IURLFeatureExtractor`, `IURLClassifier`), not concrete implementations.

---

## 2. Benchmark Evaluation Results

To prevent **Data Leakage**, 5-fold cross-validation was performed using **`GroupKFold` grouped by registered domain**. This guarantees that no phishing or benign domain present in training ever leaks into validation folds.

### Cross-Validation Comparison Table (600 Balanced Samples)

| Model Architecture | Accuracy (Mean ± Std) | F1-Score | Precision | Recall | ROC-AUC |
|---|---|---|---|---|---|
| **Majority Class Baseline** | 50.0% ± 0.0% | 0.665 | 0.500 | 1.000 | 0.500 |
| **Heuristic Rule Baseline** | 55.0% ± 6.2% | 0.176 | 0.941 | 0.100 | 0.938 |
| **Logistic Regression (L2)** | 95.5% ± 1.6% | 0.954 | 0.963 | 0.947 | 0.992 |
| **Random Forest (100 Trees)** | 95.3% ± 1.8% | 0.957 | 0.951 | 0.963 | 0.997 |
| **Soft-Voting Ensemble** | **96.5% ± 1.2%** | **0.965** | **0.970** | **0.960** | **0.997** |

### Top 5 Distinguishing URL Features (Gini Importance)
1. `url_length` (0.246): Phishing URLs in the wild are significantly longer due to tracking tokens and deceptive subpaths.
2. `entropy_full_url` (0.207): Phishing kit generation creates high Shannon randomness.
3. `path_length` (0.138): Nested paths attempting to mimic legitimate URL hierarchies.
4. `has_https` (0.112): Historical phishing crawls heavily skew towards unencrypted HTTP.
5. `num_digits` (0.089): Dynamic hexadecimal tokens and obfuscated session hashes.

---

## 3. How to Connect Backend Services to Endpoints

The URL analysis pipeline exposes high-performance REST API endpoints via FastAPI.

### Starting the Server
```bash
uvicorn modules.url_analyzer.api.server:app --host 0.0.0.0 --port 8000 --reload
```
Interactive OpenAPI documentation will be immediately accessible at `http://localhost:8000/docs`.

### Endpoint 1: Single URL Analysis
- **URL:** `POST /api/v1/url/analyze`
- **Request Body:**
```json
{
  "url": "http://192.168.1.10/paypal/login/verify.php",
  "observation_id": "obs_6f80a42371d377b212f45c4aa305609c",
  "run_id": "backend_gateway_run_01",
  "model_type": "ensemble"
}
```
- **Response Body (Matches Canonical Schema):**
```json
{
  "schema_version": "1.0.0",
  "observation_id": "obs_6f80a42371d377b212f45c4aa305609c",
  "run_id": "backend_gateway_run_01",
  "model": {
    "name": "url_multimodel_ensemble",
    "version": "1.0.0",
    "modality": "url",
    "execution_hardware": "cpu",
    "latency_ms": 2.41
  },
  "status": "success",
  "created_at": "2026-10-11T10:20:00Z",
  "result": {
    "classification": {
      "is_phishing_predicted": true,
      "confidence_score": 0.984,
      "verdict": "phishing"
    },
    "features": { ... },
    "extracted_indicators": { ... }
  },
  "warnings": [],
  "error_details": null
}
```

### Endpoint 2: High-Throughput Batch Analysis
- **URL:** `POST /api/v1/url/batch-analyze`
- **Request Body:**
```json
{
  "urls": [
    "https://google.com/search",
    "http://suspicious-apple-id.net/verify",
    ""
  ],
  "model_type": "ensemble"
}
```

### Direct Python Integration (Without HTTP Overhead)
For internal backend microservices that run in the same container or cluster:
```python
from modules.url_analyzer.service import URLAnalysisService
from modules.url_analyzer.models.ml_models import SklearnURLClassifier

# Load serialized model once at startup
rf_clf = SklearnURLClassifier.load("modules/url_analyzer/models/saved/url_rf_model.joblib")
service = URLAnalysisService(classifier=rf_clf)

# Analyze instantly
envelope = service.analyze("http://example-phish.com/login")
print(envelope.result["classification"]["verdict"])
```
