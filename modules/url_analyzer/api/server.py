import os
import time
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from modules.url_analyzer.domain.schemas import (
    AnalyzeURLRequest,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    URLModelOutputEnvelope,
)
from modules.url_analyzer.domain.extractor import StandardURLFeatureExtractor
from modules.url_analyzer.models.heuristic_baseline import HeuristicURLClassifier
from modules.url_analyzer.models.ml_models import SklearnURLClassifier, URLEnsembleClassifier
from modules.url_analyzer.service import URLAnalysisService


def create_app(models_dir: str = "modules/url_analyzer/models/saved") -> FastAPI:
    """
    Application factory for the CYRAXI URL Analysis FastAPI service.

    Available model_type values for POST /api/v1/url/analyze:
      - "baseline"      → fast heuristic rule-based classifier
      - "logistic"      → calibrated Logistic Regression (Platt scaling)
      - "random_forest" → Random Forest Classifier
      - "hgb"           → Calibrated HistGradientBoostingClassifier (primary)
      - "ensemble"      → Soft-Voting Ensemble (default)
    """
    app = FastAPI(
        title="CYRAXI URL Analysis Intelligence API",
        version="2.0.0",
        description=(
            "High-performance URL feature extraction, heuristic analysis, and ML classification "
            "conforming to canonical CYRAXI model contracts. "
            "Features: 25 lexical/structural/anti-spoofing features, "
            "calibrated probability scores, top-3 risk factor explainability."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    extractor = StandardURLFeatureExtractor()
    heuristic_clf = HeuristicURLClassifier()

    # Load ML models if available; fallback to heuristic so the service starts cleanly
    lr_path  = os.path.join(models_dir, "url_logistic_model.joblib")
    rf_path  = os.path.join(models_dir, "url_rf_model.joblib")
    hgb_path = os.path.join(models_dir, "url_hgb_model.joblib")

    lr_clf  = SklearnURLClassifier.load(lr_path)  if os.path.exists(lr_path)  else heuristic_clf
    rf_clf  = SklearnURLClassifier.load(rf_path)  if os.path.exists(rf_path)  else heuristic_clf
    hgb_clf = SklearnURLClassifier.load(hgb_path) if os.path.exists(hgb_path) else heuristic_clf

    # Ensemble weights match training: heuristic 0.10 + LR_cal 0.25 + HGB_cal 0.65
    ensemble_clf = URLEnsembleClassifier(
        classifiers=[
            (heuristic_clf, 0.10),
            (lr_clf,        0.25),
            (hgb_clf,       0.65),
        ],
        model_name="url_multimodel_ensemble",
        version="2.0.0",
    )

    services = {
        "baseline":      URLAnalysisService(classifier=heuristic_clf, extractor=extractor),
        "logistic":      URLAnalysisService(classifier=lr_clf,        extractor=extractor),
        "random_forest": URLAnalysisService(classifier=rf_clf,        extractor=extractor),
        "hgb":           URLAnalysisService(classifier=hgb_clf,       extractor=extractor),
        "ensemble":      URLAnalysisService(classifier=ensemble_clf,   extractor=extractor),
    }

    @app.get("/health", tags=["Health"])
    def health_check():
        return {
            "status":           "healthy",
            "module":           "url_analyzer",
            "api_version":      "2.0.0",
            "feature_count":    25,
            "available_models": list(services.keys()),
            "hgb_loaded":       os.path.exists(hgb_path),
            "lr_loaded":        os.path.exists(lr_path),
            "rf_loaded":        os.path.exists(rf_path),
        }

    @app.post(
        "/api/v1/url/analyze",
        response_model=URLModelOutputEnvelope,
        status_code=status.HTTP_200_OK,
        summary="Analyze a single URL",
        description=(
            "Returns a canonical ModelOutputEnvelope with 25-feature extraction, "
            "ML classification score, verdict (phishing/suspicious/benign), "
            "and top-3 contributing risk factors for explainability."
        ),
        tags=["URL Analysis"],
    )
    def analyze_single_url(request: AnalyzeURLRequest):
        model_key = (request.model_type or "ensemble").lower()
        service = services.get(model_key, services["ensemble"])
        return service.analyze(
            raw_url=request.url,
            observation_id=request.observation_id,
            run_id=request.run_id or "api_ad_hoc_run",
        )

    @app.post(
        "/api/v1/url/batch-analyze",
        response_model=BatchAnalyzeResponse,
        status_code=status.HTTP_200_OK,
        summary="Batch analyze multiple URLs",
        description=(
            "Analyze up to 1000 URLs in a single request. "
            "Returns envelopes with per-URL risk scores and risk factors."
        ),
        tags=["URL Analysis"],
    )
    def batch_analyze_urls(request: BatchAnalyzeRequest):
        model_key = (request.model_type or "ensemble").lower()
        service = services.get(model_key, services["ensemble"])
        t0 = time.perf_counter()

        envelopes = [
            service.analyze(raw_url=u, run_id=request.run_id or "batch_api_run")
            for u in request.urls
        ]

        duration = round((time.perf_counter() - t0) * 1000, 2)
        return BatchAnalyzeResponse(
            total_processed=len(envelopes),
            duration_ms=duration,
            envelopes=envelopes,
        )

    return app


# Default app instance for ASGI servers (uvicorn modules.url_analyzer.api.server:app)
app = create_app()

