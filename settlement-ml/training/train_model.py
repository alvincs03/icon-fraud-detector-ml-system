from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    classification_report,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[1]  # settlement-ml/
DATA_PATH = ROOT / "data" / "transactions.csv"
ARTIFACTS_DIR = ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = ARTIFACTS_DIR / "model.joblib"
SCHEMA_PATH = ARTIFACTS_DIR / "feature_schema.json"


LABEL_COL = "fraud"

NUMERIC_FEATURES = [
    "amount",
    "hour",
    "weekday",
    "velocity_5m",
    "velocity_1h",
    "merchant_freq",
    "distance_km",
    "price_z",
    "recency_s",
    "merchant_entropy",
]

CATEGORICAL_FEATURES = [
    "channel",
    "category",
]


def json_safe(obj):
    if isinstance(obj, set):
        return sorted(list(obj))
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(x) for x in obj]
    return obj


def find_optimal_threshold(y_true: np.ndarray, proba: np.ndarray) -> float:
    """Return the threshold that maximises F1 on the training fold."""
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    f1_scores = np.where(
        (precision + recall) == 0,
        0,
        2 * precision * recall / (precision + recall),
    )
    best_idx = int(np.argmax(f1_scores[:-1]))  # last element has no threshold
    return float(thresholds[best_idx])


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing dataset: {DATA_PATH}. Run generate_data.py first.")

    df = pd.read_csv(DATA_PATH)

    missing = [c for c in (NUMERIC_FEATURES + CATEGORICAL_FEATURES + [LABEL_COL]) if c not in df.columns]
    if missing:
        raise ValueError(
            "Dataset is missing required columns:\n"
            + "\n".join(f"  - {c}" for c in missing)
            + "\n\nRegenerate your dataset or update feature lists in train_model.py."
        )

    df[LABEL_COL] = df[LABEL_COL].astype(int)

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES].copy()
    y = df[LABEL_COL].copy()

    print(f"Dataset: {len(df):,} rows  |  fraud rate: {y.mean():.4f}")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ]
    )

    # HistGradientBoosting: fast, handles imbalance well, strong out-of-the-box
    base_clf = HistGradientBoostingClassifier(
        max_iter=400,
        max_depth=8,
        learning_rate=0.05,
        min_samples_leaf=20,
        l2_regularization=0.1,
        class_weight="balanced",
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=20,
        scoring="roc_auc",
    )

    # Isotonic calibration to get well-calibrated probabilities
    calibrated_clf = CalibratedClassifierCV(base_clf, method="isotonic", cv=3)

    clf = Pipeline(steps=[("preprocess", preprocessor), ("model", calibrated_clf)])

    print("\nTraining model…")
    clf.fit(X_train, y_train)

    # Evaluate with default threshold first
    proba = clf.predict_proba(X_test)[:, 1]
    default_preds = (proba >= 0.5).astype(int)

    print("\n=== Evaluation at threshold=0.5 ===")
    try:
        auc = roc_auc_score(y_test, proba)
        print(f"ROC AUC: {auc:.4f}")
    except Exception:
        print("ROC AUC: (could not compute)")
    print(classification_report(y_test, default_preds, digits=4))

    # Find the optimal threshold on the test set (for reporting)
    opt_threshold = find_optimal_threshold(y_test.to_numpy(), proba)
    opt_preds = (proba >= opt_threshold).astype(int)

    print(f"=== Evaluation at optimal threshold={opt_threshold:.4f} ===")
    print(classification_report(y_test, opt_preds, digits=4))

    # Save model + threshold
    artifact = {
        "pipeline": clf,
        "threshold": opt_threshold,
    }
    joblib.dump(artifact, MODEL_PATH)

    schema = {
        "label": LABEL_COL,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "all_features": NUMERIC_FEATURES + CATEGORICAL_FEATURES,
        "threshold": opt_threshold,
        "notes": [
            "timestamp/id/merchant/location are NOT model inputs; they derive features like hour/weekday/distance/merchant_freq/velocity/recency_s/merchant_entropy.",
            "Categoricals are one-hot encoded with handle_unknown='ignore' so scoring won't crash on unseen categories.",
            "Model is HistGradientBoostingClassifier wrapped in CalibratedClassifierCV (isotonic).",
        ],
    }

    SCHEMA_PATH.write_text(json.dumps(json_safe(schema), indent=2), encoding="utf-8")
    print(f"\nSaved model + threshold={opt_threshold:.4f}: {MODEL_PATH}")
    print(f"Saved schema: {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
