from __future__ import annotations

import json
import subprocess
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

DATA_PATH = ROOT / "transactions.csv"
GEN_SCRIPT = ROOT / "generate_data.py"

# Your dataset label column name:
LABEL_COL = "fraud"


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


def _missing_required_cols(df: pd.DataFrame) -> List[str]:
    return [c for c in FEATURE_COLS + [LABEL_COL] if c not in df.columns]


def _maybe_regenerate_dataset() -> None:
    """
    If generate_data.py exists, run it to produce a fresh transactions.csv.
    """
    if GEN_SCRIPT.exists():
        print(f"[train] Regenerating dataset using: {GEN_SCRIPT.name}")
        subprocess.check_call(["python", str(GEN_SCRIPT)], cwd=str(ROOT))
    else:
        print("[train] generate_data.py not found; cannot regenerate dataset.")


def _coerce_and_validate(df: pd.DataFrame) -> pd.DataFrame:
    # Ensure required columns exist
    missing = _missing_required_cols(df)
    if missing:
        raise ValueError(
            "transactions.csv is missing required columns.\n"
            f"Missing: {missing}\n"
            f"Required features: {FEATURE_COLS}\n"
            f"Required label: {LABEL_COL}\n"
        )

    out = df.copy()

    # numeric
    for c in NUMERIC_COLS:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)

    # categorical
    for c in CATEGORICAL_COLS:
        out[c] = out[c].astype(str).fillna("")

    # label
    out[LABEL_COL] = pd.to_numeric(out[LABEL_COL], errors="coerce").fillna(0).astype(int)
    bad_vals = set(out[LABEL_COL].unique()) - {0, 1}
    if bad_vals:
        raise ValueError(f"Label column '{LABEL_COL}' must be binary 0/1. Found: {sorted(bad_vals)}")

    return out


def build_pipeline() -> Pipeline:
    """
    Must support:
      model.predict_proba(pd.DataFrame([feats]))
    """
    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLS),
            ("num", "passthrough", NUMERIC_COLS),
        ],
        remainder="drop",
    )

    clf = LogisticRegression(
        max_iter=600,
        class_weight="balanced",
        solver="lbfgs",
    )

    return Pipeline(steps=[("pre", pre), ("clf", clf)])


def load_dataset_or_regenerate() -> pd.DataFrame:
    if not DATA_PATH.exists():
        print(f"[train] {DATA_PATH.name} not found; attempting regeneration.")
        _maybe_regenerate_dataset()

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {DATA_PATH}\n"
            "Expected transactions.csv in settlement-ml/. "
            "Either commit it or ensure generate_data.py creates it during build."
        )

    print(f"[train] Loading dataset: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)

    missing = _missing_required_cols(df)
    if missing:
        print(f"[train] Dataset missing columns {missing}; attempting regeneration.")
        _maybe_regenerate_dataset()
        df = pd.read_csv(DATA_PATH)

    return df


def main() -> None:
    df = load_dataset_or_regenerate()
    df = _coerce_and_validate(df)

    X = df[FEATURE_COLS].copy()
    y = df[LABEL_COL].copy()

    fraud_rate = float(df[LABEL_COL].mean()) if len(df) else 0.0
    print(f"[train] Rows: {len(df)} | Fraud rate: {fraud_rate:.4f}")

    model = build_pipeline()
    model.fit(X, y)

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
    print("[train] Done.")


if __name__ == "__main__":
    main()
