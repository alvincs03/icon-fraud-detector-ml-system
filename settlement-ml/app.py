from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import math

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import joblib


# -----------------------------
# FastAPI app
# -----------------------------
app = FastAPI(title="Settlement ML", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Schemas
# -----------------------------
class Tx(BaseModel):
    id: str
    amount: float
    merchant: Optional[str] = None
    location: Optional[str] = None
    channel: str
    timestamp: str  # ISO string expected
    category: Optional[str] = "Other"


class ScoreRequest(BaseModel):
    transaction: Tx
    history: List[Tx] = Field(default_factory=list)


class Reason(BaseModel):
    feature: str
    impact: float
    note: str


class ScoreResponse(BaseModel):
    riskScore: float
    velocity: int
    reasons: List[Reason]


# -----------------------------
# Config / paths
# -----------------------------
ROOT = Path(__file__).resolve().parent

# IMPORTANT: training saves to /artifacts/model.joblib
MODEL_PATH = ROOT / "artifacts" / "model.joblib"

# (Optional) schema you wrote in training — not required to run,
# but useful for debugging/validation later.
SCHEMA_PATH = ROOT / "artifacts" / "feature_schema.json"


@dataclass
class FeatureConfig:
    window_5m_s: int = 5 * 60
    window_1h_s: int = 60 * 60


CFG = FeatureConfig()


# -----------------------------
# Globals (load once)
# -----------------------------
MODEL: Optional[Any] = None


@app.on_event("startup")
def _load_model_on_startup() -> None:
    global MODEL
    if MODEL_PATH.exists():
        MODEL = joblib.load(MODEL_PATH)
    else:
        MODEL = None


# -----------------------------
# Utilities
# -----------------------------
def parse_iso(ts: str) -> datetime:
    """
    Accepts ISO timestamps like:
      2026-01-06T21:10:00-06:00
      2026-01-06T21:10:00Z
      2026-01-06T21:10:00
    If no timezone is present, assume UTC.
    """
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def count_in_window(times: List[datetime], now: datetime, window_s: int) -> int:
    cutoff = now - timedelta(seconds=window_s)
    c = 0
    for t in reversed(times):
        if t >= cutoff:
            c += 1
        else:
            break
    return c


def location_to_distance_km(location: Optional[str]) -> float:
    """
    Current rule:
    - If location looks like "lat,lon", compute distance from a fixed home baseline
    - Otherwise 0.0 (unknown)
    """
    if not location:
        return 0.0
    s = location.strip()
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        if len(parts) == 2:
            try:
                lat = float(parts[0])
                lon = float(parts[1])
                home_lat, home_lon = 41.8781, -87.6298  # baseline
                return float(clamp(haversine_km(home_lat, home_lon, lat, lon), 0, 5000))
            except Exception:
                return 0.0
    return 0.0


def merchant_frequency(history: List[Tx], merchant: str) -> float:
    if not merchant:
        return 0.0
    m = merchant.strip().lower()
    if not m or len(history) == 0:
        return 0.0
    c = 0
    for h in history:
        hm = (h.merchant or "").strip().lower()
        if hm and hm == m:
            c += 1
    return c / max(1, len(history))


def price_zscore(history: List[Tx], merchant: str, amount: float) -> float:
    m = (merchant or "").strip().lower()
    if not m:
        return 0.0

    amounts: List[float] = []
    for h in history:
        hm = (h.merchant or "").strip().lower()
        if hm == m:
            try:
                amounts.append(float(h.amount))
            except Exception:
                pass

    if len(amounts) < 6:
        return 0.0

    mu = sum(amounts) / len(amounts)
    var = sum((x - mu) ** 2 for x in amounts) / max(1, (len(amounts) - 1))
    sigma = math.sqrt(var) if var > 1e-9 else 1.0
    z = (float(amount) - mu) / sigma
    return float(clamp(z, -6, 6))


def extract_features(tx: Tx, history: List[Tx]) -> Dict[str, Any]:
    """
    IMPORTANT:
    This returns ONLY the columns your sklearn pipeline expects:
      numeric: amount, hour, weekday, velocity_5m, velocity_1h, merchant_freq, distance_km, price_z
      categorical: channel, category
    """
    tx_time = parse_iso(tx.timestamp)

    hist_times: List[datetime] = []
    for h in history:
        try:
            hist_times.append(parse_iso(h.timestamp))
        except Exception:
            pass
    hist_times.sort()

    all_times = hist_times + [tx_time]
    all_times.sort()

    velocity_5m = count_in_window(all_times, tx_time, CFG.window_5m_s)
    velocity_1h = count_in_window(all_times, tx_time, CFG.window_1h_s)

    hour = tx_time.hour
    weekday = tx_time.weekday()

    merchant = (tx.merchant or "").strip()
    category = (tx.category or "Other").strip() or "Other"

    feats: Dict[str, Any] = {
        "amount": float(tx.amount),
        "hour": int(hour),
        "weekday": int(weekday),
        "velocity_5m": int(velocity_5m),
        "velocity_1h": int(velocity_1h),
        "merchant_freq": float(merchant_frequency(history, merchant)),
        "distance_km": float(location_to_distance_km(tx.location)),
        "price_z": float(price_zscore(history, merchant, float(tx.amount))),
        "channel": (tx.channel or "card").strip().lower(),
        "category": category,
    }
    return feats


def build_reasons(feats: Dict[str, Any], proba: float) -> List[Reason]:
    reasons: List[Reason] = []

    amount = float(feats.get("amount", 0))
    velocity_5m = int(feats.get("velocity_5m", 0))
    velocity_1h = int(feats.get("velocity_1h", 0))
    merchant_freq = float(feats.get("merchant_freq", 0))
    distance_km = float(feats.get("distance_km", 0))
    price_z = float(feats.get("price_z", 0))
    hour = int(feats.get("hour", 0))
    category = str(feats.get("category", "Other"))

    # Amount
    if amount >= 300:
        reasons.append(Reason(feature="amount", impact=0.30, note=f"High amount: ${amount:.2f}"))
    elif amount >= 150:
        reasons.append(Reason(feature="amount", impact=0.18, note=f"Unusually large amount: ${amount:.2f}"))
    else:
        reasons.append(Reason(feature="amount", impact=-0.05, note=f"Amount appears typical: ${amount:.2f}"))

    # Velocity
    if velocity_5m >= 4:
        reasons.append(Reason(feature="velocity_5m", impact=0.28, note=f"{velocity_5m} transactions in last 5 minutes"))
    elif velocity_5m >= 3:
        reasons.append(Reason(feature="velocity_5m", impact=0.18, note=f"{velocity_5m} transactions in last 5 minutes"))
    else:
        reasons.append(Reason(feature="velocity_5m", impact=-0.04, note="No unusual burst detected (5m)"))

    if velocity_1h >= 12:
        reasons.append(Reason(feature="velocity_1h", impact=0.14, note=f"{velocity_1h} transactions in last hour"))
    elif velocity_1h >= 8:
        reasons.append(Reason(feature="velocity_1h", impact=0.08, note=f"Elevated activity: {velocity_1h} in last hour"))

    # Distance
    if distance_km >= 500:
        reasons.append(Reason(feature="distance_km", impact=0.30, note=f"Far from baseline (~{distance_km:.0f} km)"))
    elif distance_km >= 120:
        reasons.append(Reason(feature="distance_km", impact=0.14, note=f"Unusual distance (~{distance_km:.0f} km)"))
    elif distance_km > 0:
        reasons.append(Reason(feature="distance_km", impact=-0.03, note="Location appears consistent with baseline"))

    # Merchant familiarity
    if merchant_freq < 0.03:
        reasons.append(Reason(feature="merchant_freq", impact=0.20, note="Merchant is rare for this user"))
    elif merchant_freq < 0.08:
        reasons.append(Reason(feature="merchant_freq", impact=0.12, note="Merchant is less common for this user"))
    else:
        reasons.append(Reason(feature="merchant_freq", impact=-0.03, note="Merchant is common for this user"))

    # Price deviation
    if abs(price_z) >= 2.5:
        reasons.append(Reason(feature="price_z", impact=0.14, note="Amount deviates from this merchant’s typical pricing"))
    elif abs(price_z) >= 1.8:
        reasons.append(Reason(feature="price_z", impact=0.08, note="Slight price outlier for this merchant"))

    # Time of day
    if hour <= 5:
        reasons.append(Reason(feature="hour", impact=0.08, note="Unusual time of day (overnight activity)"))

    # Category
    if category in {"Electronics", "Travel", "Hotels"} and amount >= 250:
        reasons.append(Reason(feature="category", impact=0.10, note=f"{category} purchase with high spend"))
    else:
        reasons.append(Reason(feature="category", impact=0.00, note=f"Category: {category}"))

    reasons = sorted(reasons, key=lambda r: abs(r.impact), reverse=True)
    return reasons[:6]


def score_with_model(model: Any, feats: Dict[str, Any]) -> Tuple[float, float]:
    """
    Returns (proba, riskScore 0..10).
    Model is a sklearn Pipeline with predict_proba.
    """
    import pandas as pd  # keep here so app can still boot without pandas until /score is hit

    X = pd.DataFrame([feats])
    proba = float(model.predict_proba(X)[0][1])
    proba = float(clamp(proba, 0.0, 1.0))
    risk = float(clamp(round(proba * 10, 1), 0.0, 10.0))
    return proba, risk


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def root() -> Dict[str, str]:
    return {"status": "running"}


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "modelLoaded": MODEL is not None,
        "modelPath": str(MODEL_PATH),
        "schemaPath": str(SCHEMA_PATH),
        "schemaExists": SCHEMA_PATH.exists(),
    }


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    feats = extract_features(req.transaction, req.history)

    if MODEL is None:
        # Stub fallback keeps frontend functional if model missing
        proba = 0.50
        risk = 5.0
        reasons = [
            Reason(feature="stub", impact=0.0, note="Model file not found; returning default score"),
            Reason(feature="tip", impact=0.0, note=f"Train and save model to: {MODEL_PATH}"),
        ]
        return ScoreResponse(riskScore=risk, velocity=int(feats["velocity_5m"]), reasons=reasons)

    proba, risk = score_with_model(MODEL, feats)
    reasons = build_reasons(feats, proba)

    return ScoreResponse(
        riskScore=risk,
        velocity=int(feats["velocity_5m"]),
        reasons=reasons,
    )
