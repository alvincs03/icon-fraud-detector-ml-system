from __future__ import annotations

import json
from pathlib import Path
from typing import List

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


# -----------------------------
# Paths (MUST match app.py)
# -----------------------------
ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "artifacts" / "model.joblib"
SCHEMA_PATH = ROOT / "artifacts" / "feature_schema.json"

# Your generator writes to settlement-ml/transactions.csv
DATA_PATH = ROOT / "transactions.csv"

# -----------------------------
# Feature columns (MUST match app.py extract_features())
# -----------------------------
NUMERIC_COLS: List[str] = [
    "amount",
    "hour",
    "weekday",
    "velocity_5m",
    "velocity_1h",
    "merchant_freq",
    "distance_km",
    "price_z",
]

CATEGORICAL_COLS: List[str] = [
    "channel",
    "category",
]

FEATURE_COLS: List[str] = NUMERIC_COLS + CATEGORICAL_COLS

# Your dataset label column name:
LABEL_COL = "fraud"


def validate_df(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in FEATURE_COLS + [LABEL_COL] if c not in df.columns]
    if missing:
        raise ValueError(
            "transactions.csv is missing required columns.\n"
            f"Missing: {missing}\n\n"
            f"Required features: {FEATURE_COLS}\n"
            f"Required label: {LABEL_COL}\n"
        )

    # Clean / coerce types
    out = df.copy()

    for c in NUMERIC_COLS:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)

    for c in CATEGORICAL_COLS:
        out[c] = out[c].astype(str).fillna("")

    out[LABEL_COL] = pd.to_numeric(out[LABEL_COL], errors="coerce").fillna(0).astype(int)

    # ensure labels are binary 0/1
    bad_vals = set(out[LABEL_COL].unique()) - {0, 1}
    if bad_vals:
        raise ValueError(f"Label column '{LABEL_COL}' must be binary 0/1. Found: {sorted(bad_vals)}")

    return out


def build_pipeline() -> Pipeline:
    """
    Must output a pipeline that supports:
      model.predict_proba(pd.DataFrame([feats]))
    which is exactly what app.py score_with_model() calls.
    """
    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLS),
            ("num", "passthrough", NUMERIC_COLS),
        ],
        remainder="drop",
    )

    clf = LogisticRegression(
        max_iter=500,
        class_weight="balanced",  # fraud is rare, helps training
        solver="lbfgs",
    )

    return Pipeline(steps=[("pre", pre), ("clf", clf)])


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {DATA_PATH}\n\n"
            "Fix options:\n"
            "1) Run generate_data.py locally to create transactions.csv\n"
            "2) Ensure transactions.csv is committed to your repo under settlement-ml/\n"
        )

    print(f"[train] Loading dataset: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    df = validate_df(df)

    X = df[FEATURE_COLS].copy()
    y = df[LABEL_COL].copy()

    print(f"[train] Rows: {len(df)} | Fraud rate: {df[LABEL_COL].mean():.4f}")

    model = build_pipeline()
    model.fit(X, y)

    # Save artifacts to the exact location app.py loads from
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    schema = {
        "numeric": NUMERIC_COLS,
        "categorical": CATEGORICAL_COLS,
        "all": FEATURE_COLS,
        "label": LABEL_COL,
        "notes": "This schema must match app.py extract_features() output keys.",
    }
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2))

    print(f"[train] Saved model: {MODEL_PATH}")
    print(f"[train] Saved schema: {SCHEMA_PATH}")
    print("[train] Done.")


if __name__ == "__main__":
    main()
