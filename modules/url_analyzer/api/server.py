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
    """Application factory for FastAPI service."""
    app = FastAPI(
        title="CYRAXI URL Analysis Intelligence API",
        version="1.0.0",
        description="High-performance URL feature extraction, heuristic analysis, and ML classification conforming to canonical CYRAXI model contracts."
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

    # Load ML models if available, otherwise fallback cleanly
    lr_path = os.path.join(models_dir, "url_logistic_model.joblib")
    rf_path = os.path.join(models_dir, "url_rf_model.joblib")

    lr_clf = SklearnURLClassifier.load(lr_path) if os.path.exists(lr_path) else heuristic_clf
    rf_clf = SklearnURLClassifier.load(rf_path) if os.path.exists(rf_path) else heuristic_clf

    ensemble_clf = URLEnsembleClassifier(
        classifiers=[
            (heuristic_clf, 0.2),
            (lr_clf, 0.3),
            (rf_clf, 0.5)
        ],
        model_name="url_multimodel_ensemble",
        version="1.0.0"
    )

    services = {
        "baseline": URLAnalysisService(classifier=heuristic_clf, extractor=extractor),
        "logistic": URLAnalysisService(classifier=lr_clf, extractor=extractor),
        "random_forest": URLAnalysisService(classifier=rf_clf, extractor=extractor),
        "ensemble": URLAnalysisService(classifier=ensemble_clf, extractor=extractor),
    }

    @app.get("/health", tags=["Health"])
    def health_check():
        return {
            "status": "healthy",
            "module": "url_analyzer",
            "version": "1.0.0",
            "available_models": list(services.keys())
        }

    @app.post(
        "/api/v1/url/analyze",
        response_model=URLModelOutputEnvelope,
        status_code=status.HTTP_200_OK,
        summary="Analyze a single URL",
        tags=["URL Analysis"]
    )
    def analyze_single_url(request: AnalyzeURLRequest):
        model_key = (request.model_type or "ensemble").lower()
        service = services.get(model_key, services["ensemble"])
        envelope = service.analyze(
            raw_url=request.url,
            observation_id=request.observation_id,
            run_id=request.run_id or "api_ad_hoc_run"
        )
        return envelope

    @app.post(
        "/api/v1/url/batch-analyze",
        response_model=BatchAnalyzeResponse,
        status_code=status.HTTP_200_OK,
        summary="Batch analyze multiple URLs",
        tags=["URL Analysis"]
    )
    def batch_analyze_urls(request: BatchAnalyzeRequest):
        model_key = (request.model_type or "ensemble").lower()
        service = services.get(model_key, services["ensemble"])
        t0 = time.perf_counter()

        envelopes = []
        for u in request.urls:
            env = service.analyze(raw_url=u, run_id=request.run_id or "batch_api_run")
            envelopes.append(env)

        duration = round((time.perf_counter() - t0) * 1000, 2)
        return BatchAnalyzeResponse(
            total_processed=len(envelopes),
            duration_ms=duration,
            envelopes=envelopes
        )

    return app


# Default app instance for ASGI servers
app = create_app()
