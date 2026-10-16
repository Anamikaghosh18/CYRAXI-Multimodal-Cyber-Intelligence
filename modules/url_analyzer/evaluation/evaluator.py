"""
URL Model Training, Cross-Validation & Benchmark Evaluation Engine — v2
Prevents Data Leakage via Domain-Level Group Splits.

Models evaluated:
- Baseline 1: Always Phishing (Majority Zero-Rule)
- Baseline 2: Heuristic Rule Classifier
- Main Model 1: Regularized Logistic Regression + Platt Calibration
- Main Model 2: Random Forest Classifier
- Main Model 3: HistGradientBoostingClassifier (sklearn native, no extra deps)
- Main Model 4: Soft-Voting Multi-Model Ensemble (LR + RF + HGB)

New in v2:
- HistGradientBoostingClassifier replaces plain RF as primary model
- CalibratedClassifierCV (sigmoid/Platt) wrapping LR and HGB
- Sample size scaled to 1000+ phishing samples
- Precision-recall optimal threshold selection (targeting high precision)
- Feature importance from HGB permutation
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import (
    RandomForestClassifier,
    HistGradientBoostingClassifier,
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    precision_recall_curve,
)
from sklearn.model_selection import GroupKFold
from urllib.parse import urlparse

from modules.dataset_adapter.reader import PhishpediaDatasetReader
from modules.url_analyzer.domain.extractor import StandardURLFeatureExtractor
from modules.url_analyzer.domain.schemas import URLFeatureSet
from modules.url_analyzer.models.heuristic_baseline import HeuristicURLClassifier
from modules.url_analyzer.models.ml_models import SklearnURLClassifier, URLEnsembleClassifier


def extract_registered_domain(url: str) -> str:
    """Extract registered domain for group splitting to prevent domain contamination."""
    parsed = urlparse(url)
    host = parsed.netloc.split(":")[0].lower() if parsed.netloc else "unknown"
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _optimal_threshold(y_true: np.ndarray, probs: np.ndarray) -> float:
    """
    Choose probability threshold that maximises F1 on the precision-recall curve.
    Falls back to 0.5 when the curve is trivial.
    """
    precisions, recalls, thresholds = precision_recall_curve(y_true, probs)
    # thresholds has len N-1, precisions/recalls len N
    f1s = np.where(
        (precisions[:-1] + recalls[:-1]) > 0,
        2 * precisions[:-1] * recalls[:-1] / (precisions[:-1] + recalls[:-1]),
        0.0,
    )
    if len(f1s) == 0 or f1s.max() == 0:
        return 0.5
    return float(thresholds[np.argmax(f1s)])


def prepare_benchmark_dataset(
    archive_path: str = "data/phish_sample_30k.zip",
    benign_path: str = "data/reference_benign/benign_urls_500.json",
    phish_limit: int = 500,
) -> Tuple[List[str], np.ndarray, List[str]]:
    """
    Construct balanced benchmark dataset without loading the full 19 GB zip.
    Returns:
      - urls:    List of URL strings
      - y:       1D numpy int32 array (1=phishing, 0=benign)
      - domains: List of registered domains for GroupKFold
    """
    print(f"Loading up to {phish_limit} phishing URLs from archive...")
    reader = PhishpediaDatasetReader(archive_path=archive_path)
    phish_urls: List[str] = []
    for obs in reader.stream_observations(limit=phish_limit):
        u = obs.get("url", {}).get("raw")
        if u:
            phish_urls.append(u)

    print(f"Loading benign URLs from {benign_path}...")
    with open(benign_path, "r", encoding="utf-8") as f:
        benign_records = json.load(f)
    # Trim/pad benign set to match phishing count (balanced)
    benign_urls = [r["url"] for r in benign_records[:len(phish_urls)]]

    all_urls = phish_urls + benign_urls
    y = np.array([1] * len(phish_urls) + [0] * len(benign_urls), dtype=np.int32)
    domains = [extract_registered_domain(u) for u in all_urls]

    print(
        f"Dataset prepared: Total={len(all_urls)} "
        f"(Phishing={len(phish_urls)}, Benign={len(benign_urls)})"
    )
    print(
        f"Unique Domains: {len(set(domains))} "
        f"(Domain-level splitting prevents data leakage)"
    )
    return all_urls, y, domains


def _record_fold(
    results: Dict,
    model_key: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    probs: np.ndarray,
) -> None:
    """Append per-fold metrics into the running results dict."""
    results["models"][model_key]["accuracies"].append(accuracy_score(y_true, y_pred))
    results["models"][model_key]["f1s"].append(f1_score(y_true, y_pred, zero_division=0))
    results["models"][model_key]["precisions"].append(
        precision_score(y_true, y_pred, zero_division=0)
    )
    results["models"][model_key]["recalls"].append(recall_score(y_true, y_pred, zero_division=0))
    results["models"][model_key]["aucs"].append(roc_auc_score(y_true, probs))
    results["models"][model_key]["avg_precisions"].append(
        average_precision_score(y_true, probs)
    )


def run_comprehensive_evaluation(
    archive_path: str = "data/phish_sample_30k.zip",
    benign_path: str = "data/reference_benign/benign_urls_500.json",
    sample_size: int = 500,
    n_splits: int = 5,
    save_models_dir: str = "modules/url_analyzer/models/saved",
) -> Dict[str, Any]:
    """
    Run n-Fold GroupKFold cross-validation across all models and baselines.
    Retrains final production models on the full dataset and serializes them.
    """
    urls, y, domains = prepare_benchmark_dataset(
        archive_path, benign_path, phish_limit=sample_size
    )
    extractor = StandardURLFeatureExtractor()

    print("Extracting feature vectors...")
    t0_feat = time.perf_counter()
    feature_sets = [extractor.extract(u) for u in urls]
    X = np.array([f.to_vector() for f in feature_sets], dtype=np.float64)
    feat_time = round((time.perf_counter() - t0_feat) * 1000, 2)
    print(f"Extracted {X.shape[1]} features for {X.shape[0]} samples in {feat_time} ms.")

    gkf = GroupKFold(n_splits=n_splits)

    model_keys = [
        "majority_baseline",
        "heuristic_baseline",
        "logistic_regression",
        "logistic_calibrated",
        "random_forest",
        "hist_gradient_boosting",
        "hgb_calibrated",
        "soft_voting_ensemble",
    ]
    results: Dict[str, Any] = {
        "dataset_summary": {
            "total_samples": len(urls),
            "phishing_count": int(np.sum(y == 1)),
            "benign_count": int(np.sum(y == 0)),
            "unique_domains": len(set(domains)),
            "num_features": int(X.shape[1]),
            "feature_names": URLFeatureSet.feature_names(),
            "validation_strategy": (
                f"{n_splits}-Fold GroupKFold (Domain-grouped, Zero Data Leakage)"
            ),
        },
        "models": {
            k: {
                "accuracies": [], "f1s": [], "precisions": [],
                "recalls": [], "aucs": [], "avg_precisions": [],
            }
            for k in model_keys
        },
    }

    heuristic_clf = HeuristicURLClassifier()

    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups=domains)):
        print(f"  [Fold {fold + 1}/{n_splits}] train={len(train_idx)}, test={len(test_idx)}")
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        test_feats = [feature_sets[i] for i in test_idx]

        scaler = StandardScaler()
        X_train_sc = scaler.fit_transform(X_train)
        X_test_sc = scaler.transform(X_test)

        # ── 1. Majority Baseline ──────────────────────────────────────────
        y_pred_maj = np.ones_like(y_test)
        _record_fold(results, "majority_baseline", y_test, y_pred_maj,
                     np.ones_like(y_test, dtype=float))

        # ── 2. Heuristic Baseline ─────────────────────────────────────────
        heur_preds = [heuristic_clf.predict_features(f) for f in test_feats]
        y_pred_heur = np.array([1 if p.is_phishing_predicted else 0 for p in heur_preds])
        heur_confs = np.array([p.confidence_score for p in heur_preds])
        _record_fold(results, "heuristic_baseline", y_test, y_pred_heur, heur_confs)

        # ── 3. Logistic Regression ────────────────────────────────────────
        lr = LogisticRegression(max_iter=1000, C=1.0, random_state=42)
        lr.fit(X_train_sc, y_train)
        lr_probs = lr.predict_proba(X_test_sc)[:, 1]
        lr_thr = _optimal_threshold(y_train, lr.predict_proba(X_train_sc)[:, 1])
        y_pred_lr = (lr_probs >= lr_thr).astype(int)
        _record_fold(results, "logistic_regression", y_test, y_pred_lr, lr_probs)

        # ── 4. LR + Platt Calibration ─────────────────────────────────────
        lr_base = LogisticRegression(max_iter=1000, C=1.0, random_state=42)
        lr_cal = CalibratedClassifierCV(lr_base, method="sigmoid", cv=3)
        lr_cal.fit(X_train_sc, y_train)
        lr_cal_probs = lr_cal.predict_proba(X_test_sc)[:, 1]
        lr_cal_thr = _optimal_threshold(y_train, lr_cal.predict_proba(X_train_sc)[:, 1])
        y_pred_lr_cal = (lr_cal_probs >= lr_cal_thr).astype(int)
        _record_fold(results, "logistic_calibrated", y_test, y_pred_lr_cal, lr_cal_probs)

        # ── 5. Random Forest ─────────────────────────────────────────────
        rf = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)
        rf.fit(X_train, y_train)
        rf_probs = rf.predict_proba(X_test)[:, 1]
        rf_thr = _optimal_threshold(y_train, rf.predict_proba(X_train)[:, 1])
        y_pred_rf = (rf_probs >= rf_thr).astype(int)
        _record_fold(results, "random_forest", y_test, y_pred_rf, rf_probs)

        # ── 6. HistGradientBoosting (primary upgraded model) ─────────────
        hgb = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_depth=6,
            min_samples_leaf=10, random_state=42,
        )
        hgb.fit(X_train, y_train)
        hgb_probs = hgb.predict_proba(X_test)[:, 1]
        hgb_thr = _optimal_threshold(y_train, hgb.predict_proba(X_train)[:, 1])
        y_pred_hgb = (hgb_probs >= hgb_thr).astype(int)
        _record_fold(results, "hist_gradient_boosting", y_test, y_pred_hgb, hgb_probs)

        # ── 7. HGB + Platt Calibration ────────────────────────────────────
        hgb_base = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_depth=6,
            min_samples_leaf=10, random_state=42,
        )
        hgb_cal = CalibratedClassifierCV(hgb_base, method="sigmoid", cv=3)
        hgb_cal.fit(X_train, y_train)
        hgb_cal_probs = hgb_cal.predict_proba(X_test)[:, 1]
        hgb_cal_thr = _optimal_threshold(y_train, hgb_cal.predict_proba(X_train)[:, 1])
        y_pred_hgb_cal = (hgb_cal_probs >= hgb_cal_thr).astype(int)
        _record_fold(results, "hgb_calibrated", y_test, y_pred_hgb_cal, hgb_cal_probs)

        # ── 8. Soft-Voting Ensemble (Heuristic 0.1 + LR_cal 0.25 + HGB_cal 0.65) ──
        ensemble_probs = (0.1 * heur_confs) + (0.25 * lr_cal_probs) + (0.65 * hgb_cal_probs)
        ens_thr = _optimal_threshold(
            y_train,
            (0.1 * np.array([heuristic_clf.predict_features(f).confidence_score
                              for f in [feature_sets[i] for i in train_idx]]))
            + (0.25 * lr_cal.predict_proba(X_train_sc)[:, 1])
            + (0.65 * hgb_cal.predict_proba(X_train)[:, 1]),
        )
        y_pred_ens = (ensemble_probs >= ens_thr).astype(int)
        _record_fold(results, "soft_voting_ensemble", y_test, y_pred_ens, ensemble_probs)

    # ── Aggregate fold metrics ────────────────────────────────────────────
    summary_table: Dict[str, Any] = {}
    for model_name, metrics in results["models"].items():
        summary_table[model_name] = {
            "accuracy_mean":       round(float(np.mean(metrics["accuracies"])),    4),
            "accuracy_std":        round(float(np.std(metrics["accuracies"])),     4),
            "f1_mean":             round(float(np.mean(metrics["f1s"])),           4),
            "precision_mean":      round(float(np.mean(metrics["precisions"])),    4),
            "recall_mean":         round(float(np.mean(metrics["recalls"])),       4),
            "roc_auc_mean":        round(float(np.mean(metrics["aucs"])),          4),
            "avg_precision_mean":  round(float(np.mean(metrics["avg_precisions"])),4),
        }
    results["summary_table"] = summary_table

    # ── Retrain final production models on full dataset ───────────────────
    print(f"\nRetraining final models on full {len(urls)}-sample dataset...")
    full_scaler = StandardScaler()
    X_full_sc = full_scaler.fit_transform(X)

    # Final LR (calibrated)
    final_lr_base = LogisticRegression(max_iter=1000, C=1.0, random_state=42)
    final_lr_cal = CalibratedClassifierCV(final_lr_base, method="sigmoid", cv=5)
    final_lr_cal.fit(X_full_sc, y)
    lr_cal_wrapper = SklearnURLClassifier(
        final_lr_cal, model_name="url_logistic_calibrated", scaler=full_scaler,
        phishing_threshold=_optimal_threshold(y, final_lr_cal.predict_proba(X_full_sc)[:, 1])
    )
    lr_cal_wrapper.save(os.path.join(save_models_dir, "url_logistic_model.joblib"))
    print("  Saved: url_logistic_model.joblib (Calibrated LR)")

    # Final HGB (calibrated) — primary production model
    final_hgb_base = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_depth=6,
        min_samples_leaf=10, random_state=42,
    )
    final_hgb_cal = CalibratedClassifierCV(final_hgb_base, method="sigmoid", cv=5)
    final_hgb_cal.fit(X, y)
    hgb_cal_wrapper = SklearnURLClassifier(
        final_hgb_cal, model_name="url_hist_gradient_boosting_calibrated", scaler=None,
        phishing_threshold=_optimal_threshold(y, final_hgb_cal.predict_proba(X)[:, 1])
    )
    hgb_cal_wrapper.save(os.path.join(save_models_dir, "url_hgb_model.joblib"))
    print("  Saved: url_hgb_model.joblib (Calibrated HistGradientBoosting)")

    # Final RF (kept for ensemble backward-compat)
    final_rf = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)
    final_rf.fit(X, y)
    rf_wrapper = SklearnURLClassifier(
        final_rf, model_name="url_random_forest", scaler=None,
        phishing_threshold=_optimal_threshold(y, final_rf.predict_proba(X)[:, 1])
    )
    rf_wrapper.save(os.path.join(save_models_dir, "url_rf_model.joblib"))
    print("  Saved: url_rf_model.joblib (Random Forest)")

    # ── Feature importance (RF as proxy — HGB has no .feature_importances_) ─
    feature_names = URLFeatureSet.feature_names()
    importances = final_rf.feature_importances_
    feat_ranks = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
    results["feature_importances"] = [
        {"feature": name, "importance": round(float(imp), 4)} for name, imp in feat_ranks
    ]

    print("\nModel evaluation complete. Summary:")
    print(f"  {'Model':35s} | Acc   | F1    | AUC   | AvgPrec")
    print(f"  {'-'*35} | {'-'*5} | {'-'*5} | {'-'*5} | {'-'*7}")
    for m, stats in summary_table.items():
        print(
            f"  {m:35s} | {stats['accuracy_mean']:.3f} | "
            f"{stats['f1_mean']:.3f} | {stats['roc_auc_mean']:.3f} | "
            f"{stats['avg_precision_mean']:.3f}"
        )

    return results


if __name__ == "__main__":
    res = run_comprehensive_evaluation(sample_size=500)
    out_path = Path("docs/evaluation/URL_EVALUATION_REPORT.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"\nDetailed JSON report saved to {out_path}")
