from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import joblib


# -----------------------------
# FastAPI app
# -----------------------------
app = FastAPI(title="Settlement ML", version="0.3.0")

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
MODEL_PATH = ROOT / "artifacts" / "model.joblib"
SCHEMA_PATH = ROOT / "artifacts" / "feature_schema.json"


@dataclass
class FeatureConfig:
    window_5m_s: int = 5 * 60
    window_1h_s: int = 60 * 60


CFG = FeatureConfig()


# -----------------------------
# Globals (load once at startup)
# -----------------------------
PIPELINE: Optional[Any] = None
THRESHOLD: float = 0.5


@app.on_event("startup")
def _load_model_on_startup() -> None:
    global PIPELINE, THRESHOLD
    if MODEL_PATH.exists():
        artifact = joblib.load(MODEL_PATH)
        if isinstance(artifact, dict):
            PIPELINE = artifact.get("pipeline")
            THRESHOLD = float(artifact.get("threshold", 0.5))
        else:
            # Legacy: raw pipeline object
            PIPELINE = artifact
            THRESHOLD = 0.5
    else:
        PIPELINE = None
        THRESHOLD = 0.5


# -----------------------------
# Utilities
# -----------------------------
def parse_iso(ts: str) -> datetime:
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
    if not location:
        return 0.0
    s = location.strip()
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        if len(parts) == 2:
            try:
                lat = float(parts[0])
                lon = float(parts[1])
                home_lat, home_lon = 41.8781, -87.6298
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
    c = sum(1 for h in history if (h.merchant or "").strip().lower() == m)
    return c / max(1, len(history))


def price_zscore(history: List[Tx], merchant: str, amount: float) -> float:
    m = (merchant or "").strip().lower()
    if not m:
        return 0.0

    amounts: List[float] = []
    for h in history:
        if (h.merchant or "").strip().lower() == m:
            try:
                amounts.append(float(h.amount))
            except Exception:
                pass

    if len(amounts) < 6:
        return 0.0

    mu = sum(amounts) / len(amounts)
    var = sum((x - mu) ** 2 for x in amounts) / max(1, (len(amounts) - 1))
    sigma = math.sqrt(var) if var > 1e-9 else 1.0
    return float(clamp((float(amount) - mu) / sigma, -6, 6))


def recency_seconds(hist_times: List[datetime], tx_time: datetime) -> float:
    """Seconds since the most recent prior transaction. Returns 3600 if no history."""
    past = [t for t in hist_times if t < tx_time]
    if not past:
        return 3600.0
    delta = (tx_time - max(past)).total_seconds()
    return float(clamp(delta, 0, 86400))


def merchant_entropy_score(recent_merchants: List[str]) -> float:
    """Shannon entropy of merchant distribution, normalised to [0,1]."""
    if not recent_merchants:
        return 0.0
    counts: Dict[str, int] = {}
    for m in recent_merchants:
        counts[m] = counts.get(m, 0) + 1
    total = len(recent_merchants)
    entropy = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            entropy -= p * math.log2(p)
    max_entropy = math.log2(len(counts)) if len(counts) > 1 else 1.0
    return float(clamp(entropy / max_entropy if max_entropy > 0 else 0.0, 0.0, 1.0))


def extract_features(tx: Tx, history: List[Tx]) -> Dict[str, Any]:
    tx_time = parse_iso(tx.timestamp)

    hist_times: List[datetime] = []
    for h in history:
        try:
            hist_times.append(parse_iso(h.timestamp))
        except Exception:
            pass
    hist_times.sort()

    all_times = sorted(hist_times + [tx_time])

    velocity_5m = count_in_window(all_times, tx_time, CFG.window_5m_s)
    velocity_1h = count_in_window(all_times, tx_time, CFG.window_1h_s)

    hour = tx_time.hour
    weekday = tx_time.weekday()

    merchant = (tx.merchant or "").strip()
    category = (tx.category or "Other").strip() or "Other"

    # Recent merchants in 1h window for entropy
    cutoff_1h = tx_time - timedelta(seconds=CFG.window_1h_s)
    recent_merchants = [
        (h.merchant or "").strip()
        for h, t in zip(history, hist_times)
        if t >= cutoff_1h and (h.merchant or "").strip()
    ] + ([merchant] if merchant else [])

    feats: Dict[str, Any] = {
        "amount": float(tx.amount),
        "hour": int(hour),
        "weekday": int(weekday),
        "velocity_5m": int(velocity_5m),
        "velocity_1h": int(velocity_1h),
        "merchant_freq": float(merchant_frequency(history, merchant)),
        "distance_km": float(location_to_distance_km(tx.location)),
        "price_z": float(price_zscore(history, merchant, float(tx.amount))),
        "recency_s": float(recency_seconds(hist_times, tx_time)),
        "merchant_entropy": float(merchant_entropy_score(recent_merchants)),
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
    recency_s = float(feats.get("recency_s", 3600))
    merchant_entropy = float(feats.get("merchant_entropy", 0))

    # Amount
    if amount >= 300:
        reasons.append(Reason(feature="amount", impact=0.30, note=f"High amount: ${amount:.2f}"))
    elif amount >= 150:
        reasons.append(Reason(feature="amount", impact=0.18, note=f"Unusually large amount: ${amount:.2f}"))
    else:
        reasons.append(Reason(feature="amount", impact=-0.05, note=f"Amount appears typical: ${amount:.2f}"))

    # Velocity 5m
    if velocity_5m >= 4:
        reasons.append(Reason(feature="velocity_5m", impact=0.28, note=f"{velocity_5m} transactions in last 5 minutes"))
    elif velocity_5m >= 3:
        reasons.append(Reason(feature="velocity_5m", impact=0.18, note=f"{velocity_5m} transactions in last 5 minutes"))
    else:
        reasons.append(Reason(feature="velocity_5m", impact=-0.04, note="No unusual burst detected (5m)"))

    # Velocity 1h
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
        reasons.append(Reason(feature="price_z", impact=0.14, note="Amount deviates from this merchant's typical pricing"))
    elif abs(price_z) >= 1.8:
        reasons.append(Reason(feature="price_z", impact=0.08, note="Slight price outlier for this merchant"))

    # Recency
    if 0 < recency_s < 30:
        reasons.append(Reason(feature="recency_s", impact=0.22, note=f"Rapid-fire: {recency_s:.0f}s since last transaction"))
    elif recency_s < 120:
        reasons.append(Reason(feature="recency_s", impact=0.12, note=f"Short gap: {recency_s:.0f}s since last transaction"))
    else:
        reasons.append(Reason(feature="recency_s", impact=-0.03, note=f"Normal gap: {recency_s:.0f}s since last transaction"))

    # Merchant entropy
    if merchant_entropy > 0.85:
        reasons.append(Reason(feature="merchant_entropy", impact=0.18, note="High merchant diversity in recent window"))
    elif merchant_entropy > 0.65:
        reasons.append(Reason(feature="merchant_entropy", impact=0.08, note="Moderately diverse merchant pattern"))
    else:
        reasons.append(Reason(feature="merchant_entropy", impact=-0.03, note="Consistent merchant pattern"))

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


def score_with_model(pipeline: Any, feats: Dict[str, Any]) -> Tuple[float, float]:
    import pandas as pd

    X = pd.DataFrame([feats])
    proba = float(pipeline.predict_proba(X)[0][1])
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
        "modelLoaded": PIPELINE is not None,
        "threshold": THRESHOLD,
        "modelPath": str(MODEL_PATH),
        "schemaPath": str(SCHEMA_PATH),
        "schemaExists": SCHEMA_PATH.exists(),
    }


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    feats = extract_features(req.transaction, req.history)

    if PIPELINE is None:
        proba = 0.50
        risk = 5.0
        reasons = [
            Reason(feature="stub", impact=0.0, note="Model file not found; returning default score"),
            Reason(feature="tip", impact=0.0, note=f"Train and save model to: {MODEL_PATH}"),
        ]
        return ScoreResponse(riskScore=risk, velocity=int(feats["velocity_5m"]), reasons=reasons)

    proba, risk = score_with_model(PIPELINE, feats)
    reasons = build_reasons(feats, proba)

    return ScoreResponse(
        riskScore=risk,
        velocity=int(feats["velocity_5m"]),
        reasons=reasons,
    )
