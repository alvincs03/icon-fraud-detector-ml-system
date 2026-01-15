from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import List

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "artifacts" / "model.joblib"
SCHEMA_PATH = ROOT / "artifacts" / "feature_schema.json"

DATA_PATH = ROOT / "transactions.csv"
GEN_SCRIPT = ROOT / "generate_data.py"

LABEL_COL = "fraud"

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


def _print_dataset_debug(df: pd.DataFrame) -> None:
    print("\n[train][debug] CWD:", os.getcwd())
    print("[train][debug] DATA_PATH:", str(DATA_PATH))
    if DATA_PATH.exists():
        print("[train][debug] DATA_SIZE_BYTES:", DATA_PATH.stat().st_size)
    print("[train][debug] COLUMNS:", list(df.columns))

    # Print first 1-2 rows safely (avoid huge output)
    try:
        print("[train][debug] HEAD:\n", df.head(2).to_string(index=False))
    except Exception as e:
        print("[train][debug] Could not print head:", repr(e))

    # Print raw first line of file (header)
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        print("[train][debug] RAW_HEADER_LINE:", first_line)
    except Exception as e:
        print("[train][debug] Could not read raw header:", repr(e))
    print("")


def _maybe_regenerate_dataset() -> None:
    if GEN_SCRIPT.exists():
        print(f"[train] Regenerating dataset using: {GEN_SCRIPT.name}")
        subprocess.check_call(["python", str(GEN_SCRIPT)], cwd=str(ROOT))
    else:
        print("[train] generate_data.py not found; cannot regenerate dataset.")


def _coerce_and_validate(df: pd.DataFrame) -> pd.DataFrame:
    missing = _missing_required_cols(df)
    if missing:
        raise ValueError(
            "transactions.csv is missing required columns.\n"
            f"Missing: {missing}\n"
            f"Required features: {FEATURE_COLS}\n"
            f"Required label: {LABEL_COL}\n"
        )

    out = df.copy()

    for c in NUMERIC_COLS:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)

    for c in CATEGORICAL_COLS:
        out[c] = out[c].astype(str).fillna("")

    out[LABEL_COL] = pd.to_numeric(out[LABEL_COL], errors="coerce").fillna(0).astype(int)

    bad_vals = set(out[LABEL_COL].unique()) - {0, 1}
    if bad_vals:
        raise ValueError(f"Label column '{LABEL_COL}' must be binary 0/1. Found: {sorted(bad_vals)}")

    return out


def build_pipeline() -> Pipeline:
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


def load_df() -> pd.DataFrame:
    if not DATA_PATH.exists():
        print(f"[train] {DATA_PATH.name} not found; attempting regeneration.")
        _maybe_regenerate_dataset()

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {DATA_PATH}. "
            "Either commit settlement-ml/transactions.csv or ensure generate_data.py creates it."
        )

    df = pd.read_csv(DATA_PATH)
    _print_dataset_debug(df)

    missing = _missing_required_cols(df)
    if missing:
        print(f"[train] Missing columns detected: {missing}")
        print("[train] Attempting regeneration, then reload...")
        _maybe_regenerate_dataset()
        df = pd.read_csv(DATA_PATH)
        _print_dataset_debug(df)

    return df


def main() -> None:
    df = load_df()
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
        "notes": "Must match app.py extract_features() output keys.",
    }
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2))

    print(f"[train] Saved model: {MODEL_PATH}")
    print("[train] Done.")


if __name__ == "__main__":
    main()
