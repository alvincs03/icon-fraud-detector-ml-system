from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]  # settlement-ml/
DATA_PATH = ROOT / "data" / "transactions.csv"
ARTIFACTS_DIR = ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = ARTIFACTS_DIR / "model.joblib"
SCHEMA_PATH = ARTIFACTS_DIR / "feature_schema.json"


# Columns in your synthetic dataset (you can add more later)
LABEL_COL = "fraud"

# Explicitly list the model input columns (keeps things stable as your CSV evolves)
NUMERIC_FEATURES = [
    "amount",
    "hour",
    "weekday",
    "velocity_5m",
    "velocity_1h",
    "merchant_freq",
    "distance_km",
    "price_z",
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

def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing dataset: {DATA_PATH}. Generate it first (Step 1).")

    df = pd.read_csv(DATA_PATH)

    # Basic sanity checks
    missing = [c for c in (NUMERIC_FEATURES + CATEGORICAL_FEATURES + [LABEL_COL]) if c not in df.columns]
    if missing:
        raise ValueError(
            "Dataset is missing required columns:\n"
            + "\n".join(f"- {c}" for c in missing)
            + "\n\nRegenerate your dataset or update the feature lists in train_model.py."
        )

    # Ensure label is int {0,1}
    df[LABEL_COL] = df[LABEL_COL].astype(int)

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES].copy()
    y = df[LABEL_COL].copy()

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    # Preprocess: numeric passthrough, categorical one-hot (handle_unknown for new categories)
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", "passthrough", NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )

    # Model
    model = RandomForestClassifier(
        n_estimators=350,
        max_depth=None,
        min_samples_split=10,
        min_samples_leaf=4,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced_subsample",
    )

    clf = Pipeline(steps=[("preprocess", preprocessor), ("model", model)])

    clf.fit(X_train, y_train)

    # Evaluate
    proba = clf.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)

    print("\n=== Evaluation (holdout) ===")
    try:
        auc = roc_auc_score(y_test, proba)
        print(f"ROC AUC: {auc:.4f}")
    except Exception:
        print("ROC AUC: (could not compute)")

    print("\nClassification report:")
    print(classification_report(y_test, preds, digits=4))

    # Save artifacts
    joblib.dump(clf, MODEL_PATH)

    schema = {
        "label": LABEL_COL,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "all_features": NUMERIC_FEATURES + CATEGORICAL_FEATURES,
        "notes": {
            "timestamp/id/merchant/location are NOT model inputs; they’re used to derive features like hour/weekday/distance/merchant_freq/velocity.",
            "Categoricals are one-hot encoded with handle_unknown='ignore' so scoring won’t crash on unseen categories.",
        },
    }

    SCHEMA_PATH.write_text(json.dumps(json_safe(schema), indent=2), encoding="utf-8")
    print(f"\nSaved model: {MODEL_PATH}")
    print(f"Saved schema: {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
