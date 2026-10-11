"""
URL Model Training, Cross-Validation & Benchmark Evaluation Engine
Prevents Data Leakage via Domain-Level Group Splits.
Evaluates:
- Baseline 1: Always Phishing (Majority Zero-Rule)
- Baseline 2: Heuristic Rule Classifier
- Main Model 1: Regularized Logistic Regression
- Main Model 2: Random Forest Classifier
- Main Model 3: Soft-Voting Multi-Model Ensemble
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
from urllib.parse import urlparse

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)
from sklearn.model_selection import GroupKFold

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


def prepare_benchmark_dataset(
    archive_path: str = "data/phish_sample_30k.zip",
    benign_path: str = "data/reference_benign/benign_urls_500.json",
    phish_limit: int = 500
) -> Tuple[List[str], np.ndarray, List[str]]:
    """
    Construct balanced benchmark dataset without loading 19 GB zip.
    Returns:
    - urls: List of URL strings
    - y: 1D numpy array of binary labels (1=phishing, 0=benign)
    - domains: List of domains for GroupKFold
    """
    print(f"Loading {phish_limit} phishing URLs from archive...")
    reader = PhishpediaDatasetReader(archive_path=archive_path)
    phish_urls = []
    for obs in reader.stream_observations(limit=phish_limit):
        u = obs.get("url", {}).get("raw")
        if u:
            phish_urls.append(u)

    print(f"Loading benign URLs from {benign_path}...")
    with open(benign_path, "r", encoding="utf-8") as f:
        benign_records = json.load(f)
    benign_urls = [r["url"] for r in benign_records[:len(phish_urls)]]

    all_urls = phish_urls + benign_urls
    y = np.array([1] * len(phish_urls) + [0] * len(benign_urls), dtype=np.int32)
    domains = [extract_registered_domain(u) for u in all_urls]

    print(f"Dataset prepared: Total={len(all_urls)} (Phishing={len(phish_urls)}, Benign={len(benign_urls)})")
    print(f"Unique Domains: {len(set(domains))} (Domain-level splitting will prevent leakage)")
    return all_urls, y, domains


def run_comprehensive_evaluation(
    archive_path: str = "data/phish_sample_30k.zip",
    benign_path: str = "data/reference_benign/benign_urls_500.json",
    sample_size: int = 400,
    n_splits: int = 5,
    save_models_dir: str = "modules/url_analyzer/models/saved"
) -> Dict[str, Any]:
    """
    Run 5-Fold GroupKFold cross-validation across all models and baselines.
    """
    urls, y, domains = prepare_benchmark_dataset(archive_path, benign_path, phish_limit=sample_size)
    extractor = StandardURLFeatureExtractor()

    # Extract features for all URLs
    print("Extracting feature vectors...")
    t0_feat = time.perf_counter()
    feature_sets = [extractor.extract(u) for u in urls]
    X = np.array([f.to_vector() for f in feature_sets], dtype=np.float64)
    feat_time = round((time.perf_counter() - t0_feat) * 1000, 2)
    print(f"Extracted {X.shape[1]} features for {X.shape[0]} samples in {feat_time} ms.")

    gkf = GroupKFold(n_splits=n_splits)

    results = {
        "dataset_summary": {
            "total_samples": len(urls),
            "phishing_count": int(np.sum(y == 1)),
            "benign_count": int(np.sum(y == 0)),
            "unique_domains": len(set(domains)),
            "validation_strategy": f"{n_splits}-Fold GroupKFold (Domain-grouped, Zero Data Leakage)"
        },
        "models": {
            "majority_baseline": {"accuracies": [], "f1s": [], "precisions": [], "recalls": [], "aucs": []},
            "heuristic_baseline": {"accuracies": [], "f1s": [], "precisions": [], "recalls": [], "aucs": []},
            "logistic_regression": {"accuracies": [], "f1s": [], "precisions": [], "recalls": [], "aucs": []},
            "random_forest": {"accuracies": [], "f1s": [], "precisions": [], "recalls": [], "aucs": []},
            "soft_voting_ensemble": {"accuracies": [], "f1s": [], "precisions": [], "recalls": [], "aucs": []},
        }
    }

    heuristic_clf = HeuristicURLClassifier()

    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups=domains)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        test_feats = [feature_sets[i] for i in test_idx]

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # 1. Baseline: Majority Class
        y_pred_maj = np.ones_like(y_test)
        results["models"]["majority_baseline"]["accuracies"].append(accuracy_score(y_test, y_pred_maj))
        results["models"]["majority_baseline"]["f1s"].append(f1_score(y_test, y_pred_maj, zero_division=0))
        results["models"]["majority_baseline"]["precisions"].append(precision_score(y_test, y_pred_maj, zero_division=0))
        results["models"]["majority_baseline"]["recalls"].append(recall_score(y_test, y_pred_maj, zero_division=0))
        results["models"]["majority_baseline"]["aucs"].append(0.50)

        # 2. Heuristic Baseline
        heur_preds = [heuristic_clf.predict_features(f) for f in test_feats]
        y_pred_heur = np.array([1 if p.is_phishing_predicted else 0 for p in heur_preds])
        heur_confs = np.array([p.confidence_score for p in heur_preds])
        results["models"]["heuristic_baseline"]["accuracies"].append(accuracy_score(y_test, y_pred_heur))
        results["models"]["heuristic_baseline"]["f1s"].append(f1_score(y_test, y_pred_heur, zero_division=0))
        results["models"]["heuristic_baseline"]["precisions"].append(precision_score(y_test, y_pred_heur, zero_division=0))
        results["models"]["heuristic_baseline"]["recalls"].append(recall_score(y_test, y_pred_heur, zero_division=0))
        results["models"]["heuristic_baseline"]["aucs"].append(roc_auc_score(y_test, heur_confs))

        # 3. Logistic Regression
        lr = LogisticRegression(max_iter=1000, random_state=42)
        lr.fit(X_train_scaled, y_train)
        lr_probs = lr.predict_proba(X_test_scaled)[:, 1]
        y_pred_lr = (lr_probs >= 0.5).astype(int)
        results["models"]["logistic_regression"]["accuracies"].append(accuracy_score(y_test, y_pred_lr))
        results["models"]["logistic_regression"]["f1s"].append(f1_score(y_test, y_pred_lr, zero_division=0))
        results["models"]["logistic_regression"]["precisions"].append(precision_score(y_test, y_pred_lr, zero_division=0))
        results["models"]["logistic_regression"]["recalls"].append(recall_score(y_test, y_pred_lr, zero_division=0))
        results["models"]["logistic_regression"]["aucs"].append(roc_auc_score(y_test, lr_probs))

        # 4. Random Forest
        rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        rf.fit(X_train, y_train) # Tree models don't require scaling
        rf_probs = rf.predict_proba(X_test)[:, 1]
        y_pred_rf = (rf_probs >= 0.5).astype(int)
        results["models"]["random_forest"]["accuracies"].append(accuracy_score(y_test, y_pred_rf))
        results["models"]["random_forest"]["f1s"].append(f1_score(y_test, y_pred_rf, zero_division=0))
        results["models"]["random_forest"]["precisions"].append(precision_score(y_test, y_pred_rf, zero_division=0))
        results["models"]["random_forest"]["recalls"].append(recall_score(y_test, y_pred_rf, zero_division=0))
        results["models"]["random_forest"]["aucs"].append(roc_auc_score(y_test, rf_probs))

        # 5. Soft-Voting Ensemble (Heuristic 0.2 + LR 0.3 + RF 0.5)
        ensemble_probs = (0.2 * heur_confs) + (0.3 * lr_probs) + (0.5 * rf_probs)
        y_pred_ens = (ensemble_probs >= 0.5).astype(int)
        results["models"]["soft_voting_ensemble"]["accuracies"].append(accuracy_score(y_test, y_pred_ens))
        results["models"]["soft_voting_ensemble"]["f1s"].append(f1_score(y_test, y_pred_ens, zero_division=0))
        results["models"]["soft_voting_ensemble"]["precisions"].append(precision_score(y_test, y_pred_ens, zero_division=0))
        results["models"]["soft_voting_ensemble"]["recalls"].append(recall_score(y_test, y_pred_ens, zero_division=0))
        results["models"]["soft_voting_ensemble"]["aucs"].append(roc_auc_score(y_test, ensemble_probs))

    # Summarize mean & std
    summary_table = {}
    for model_name, metrics in results["models"].items():
        summary_table[model_name] = {
            "accuracy_mean": round(float(np.mean(metrics["accuracies"])), 4),
            "accuracy_std": round(float(np.std(metrics["accuracies"])), 4),
            "f1_mean": round(float(np.mean(metrics["f1s"])), 4),
            "precision_mean": round(float(np.mean(metrics["precisions"])), 4),
            "recall_mean": round(float(np.mean(metrics["recalls"])), 4),
            "roc_auc_mean": round(float(np.mean(metrics["aucs"])), 4)
        }
    results["summary_table"] = summary_table

    # Retrain final production models on full benchmark dataset and serialize
    print(f"Retraining final models on full {len(urls)} dataset...")
    full_scaler = StandardScaler()
    X_full_scaled = full_scaler.fit_transform(X)

    final_lr = LogisticRegression(max_iter=1000, random_state=42)
    final_lr.fit(X_full_scaled, y)
    lr_wrapper = SklearnURLClassifier(final_lr, model_name="url_logistic_regression", scaler=full_scaler)
    lr_wrapper.save(os.path.join(save_models_dir, "url_logistic_model.joblib"))

    final_rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    final_rf.fit(X, y)
    rf_wrapper = SklearnURLClassifier(final_rf, model_name="url_random_forest", scaler=None)
    rf_wrapper.save(os.path.join(save_models_dir, "url_rf_model.joblib"))

    # Feature Importance analysis from RF
    feature_names = URLFeatureSet.feature_names()
    importances = final_rf.feature_importances_
    feat_ranks = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
    results["feature_importances"] = [
        {"feature": name, "importance": round(float(imp), 4)} for name, imp in feat_ranks
    ]

    print("Model evaluation complete. Summary:")
    for m, stats in summary_table.items():
        print(f"  {m:25s} | Acc: {stats['accuracy_mean']:.3f} | F1: {stats['f1_mean']:.3f} | AUC: {stats['roc_auc_mean']:.3f}")

    return results


if __name__ == "__main__":
    res = run_comprehensive_evaluation(sample_size=300)
    out_path = Path("docs/evaluation/URL_EVALUATION_REPORT.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"Detailed JSON report saved to {out_path}")
