from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


# -----------------------------
# Configuration
# -----------------------------
@dataclass
class Config:
    n_rows: int = 55000
    fraud_base_rate: float = 0.02

    min_gap_s: int = 5
    max_gap_s: int = 3600

    window_5m_s: int = 5 * 60
    window_1h_s: int = 60 * 60

    home_lat: float = 41.8781
    home_lon: float = -87.6298

    n_merchants: int = 80
    common_merchant_share: float = 0.25
    common_merchant_weight: float = 0.70

    avg_amount: float = 40.0
    high_amount_threshold: float = 300.0


CFG = Config()

CATEGORIES = [
    "Groceries",
    "Dining",
    "Coffee",
    "Gas",
    "Transportation",
    "Travel",
    "Hotels",
    "Entertainment",
    "Streaming/Subscriptions",
    "Shopping - General",
    "Clothing",
    "Electronics",
    "Home Improvement",
    "Pharmacy/Health",
    "Medical",
    "Insurance",
    "Utilities",
    "Telecom/Internet",
    "Education",
    "Gifts/Donations",
    "Fees/Interest",
    "ATM/Cash Withdrawal",
    "Rent/Mortgage",
    "Services",
    "Other",
]

CATEGORY_WEIGHTS = [
    0.10,  # Groceries
    0.10,  # Dining
    0.04,  # Coffee
    0.05,  # Gas
    0.06,  # Transportation
    0.03,  # Travel
    0.02,  # Hotels
    0.05,  # Entertainment
    0.05,  # Streaming
    0.09,  # Shopping - General
    0.05,  # Clothing
    0.06,  # Electronics
    0.04,  # Home Improvement
    0.04,  # Pharmacy/Health
    0.02,  # Medical
    0.02,  # Insurance
    0.04,  # Utilities
    0.03,  # Telecom/Internet
    0.02,  # Education
    0.02,  # Gifts/Donations
    0.02,  # Fees/Interest
    0.02,  # ATM/Cash Withdrawal
    0.02,  # Rent/Mortgage
    0.04,  # Services
    0.03,  # Other
]


# -----------------------------
# Helpers
# -----------------------------
def weighted_choice(items: List[str], weights: List[float]) -> str:
    return random.choices(items, weights=weights, k=1)[0]


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def gaussian_distance_km() -> float:
    if random.random() < 0.90:
        return abs(random.gauss(12, 18))
    return abs(random.gauss(900, 700))


def generate_amount(avg: float) -> float:
    amt = random.expovariate(1 / avg)
    return round(amt + random.choice([0.00, 0.49, 0.99]), 2)


def make_merchants(n: int) -> Tuple[List[str], List[float], Dict[str, float]]:
    merchants = [f"Merchant_{i:03d}" for i in range(1, n + 1)]

    n_common = max(1, int(n * CFG.common_merchant_share))
    common = merchants[:n_common]
    rare = merchants[n_common:]

    common_mass = CFG.common_merchant_weight
    rare_mass = 1.0 - common_mass

    common_weights = [common_mass / len(common)] * len(common)
    rare_weights = [rare_mass / len(rare)] * len(rare) if rare else []

    weights = common_weights + rare_weights

    typical_price: Dict[str, float] = {}
    for m in merchants:
        if m in common:
            typical_price[m] = random.uniform(10, 80)
        else:
            typical_price[m] = random.uniform(20, 250)

    return merchants, weights, typical_price


def count_in_window(timestamps: List[datetime], now: datetime, window_s: int) -> int:
    cutoff = now - timedelta(seconds=window_s)
    c = 0
    for t in reversed(timestamps):
        if t >= cutoff:
            c += 1
        else:
            break
    return c


def price_zscore(amount: float, merchant: str, typical_price: Dict[str, float]) -> float:
    mu = typical_price[merchant]
    sigma = max(8.0, mu * 0.35)
    z = (amount - mu) / sigma
    return float(clamp(z, -6, 6))


def merchant_entropy_score(recent_merchants: List[str]) -> float:
    """Shannon entropy of merchant distribution in recent window. Higher = more diverse = more suspicious."""
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
    # Normalize to [0, 1] by dividing by log2(total unique) max entropy
    max_entropy = math.log2(len(counts)) if len(counts) > 1 else 1.0
    return float(clamp(entropy / max_entropy if max_entropy > 0 else 0.0, 0.0, 1.0))


# -----------------------------
# Fraud labeling logic (synthetic)
# -----------------------------
def fraud_probability(
    amount: float,
    velocity_5m: int,
    velocity_1h: int,
    distance_km: float,
    merchant_freq: float,
    hour: int,
    price_z: float,
    channel: str,
    category: str,
    recency_s: float,
    merchant_entropy: float,
) -> float:
    p = CFG.fraud_base_rate

    if amount >= CFG.high_amount_threshold:
        p += 0.22
    elif amount >= 150:
        p += 0.10

    if velocity_5m >= 4:
        p += 0.22
    elif velocity_5m >= 3:
        p += 0.12

    if velocity_1h >= 12:
        p += 0.10
    elif velocity_1h >= 8:
        p += 0.06

    if distance_km > 500:
        p += 0.22
    elif distance_km > 120:
        p += 0.08

    if merchant_freq < 0.03:
        p += 0.15
    elif merchant_freq < 0.08:
        p += 0.08

    if hour <= 5:
        p += 0.06

    if abs(price_z) >= 2.5:
        p += 0.08
    elif abs(price_z) >= 1.8:
        p += 0.04

    if channel == "wire":
        p += 0.06
    if channel == "wallet":
        p += 0.03

    if category in {"Electronics", "Travel", "Hotels"} and amount >= 300:
        p += 0.08
    if category in {"ATM/Cash Withdrawal"}:
        p += 0.06
    if category in {"Fees/Interest"} and amount >= 150:
        p += 0.04

    # Recency: very short time since last tx is suspicious (rapid-fire fraud)
    if 0 < recency_s < 30:
        p += 0.12
    elif recency_s < 120:
        p += 0.06

    # High merchant entropy in recent window = hitting many different merchants fast
    if merchant_entropy > 0.85:
        p += 0.10
    elif merchant_entropy > 0.65:
        p += 0.05

    # Interaction boosts (key)
    if amount >= CFG.high_amount_threshold and distance_km > 500:
        p += 0.30
    if amount >= CFG.high_amount_threshold and velocity_5m >= 3:
        p += 0.25
    if distance_km > 500 and velocity_5m >= 3:
        p += 0.25
    if recency_s < 60 and velocity_5m >= 3:
        p += 0.15

    return float(clamp(p, 0.0, 0.95))


# -----------------------------
# Main generation
# -----------------------------
def main() -> None:
    random.seed(42)

    out_path = Path(__file__).resolve().parent / "transactions.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    merchants, merchant_weights, typical_price = make_merchants(CFG.n_merchants)

    channels = ["card", "ach", "wire", "wallet", "cash"]
    channel_weights = [0.62, 0.16, 0.06, 0.12, 0.04]

    merchant_counts: Dict[str, int] = {m: 0 for m in merchants}
    timestamps: List[datetime] = []
    merchant_history_1h: List[str] = []  # merchants in 1h window

    current_time = datetime.now().replace(microsecond=0)

    rows: List[Dict] = []

    for i in range(CFG.n_rows):
        gap_s = random.randint(CFG.min_gap_s, CFG.max_gap_s)
        current_time = current_time + timedelta(seconds=gap_s)
        timestamps.append(current_time)

        merchant = weighted_choice(merchants, merchant_weights)
        channel = weighted_choice(channels, channel_weights)
        category = weighted_choice(CATEGORIES, CATEGORY_WEIGHTS)

        amount = generate_amount(CFG.avg_amount)

        velocity_5m = count_in_window(timestamps, current_time, CFG.window_5m_s)
        velocity_1h = count_in_window(timestamps, current_time, CFG.window_1h_s)

        prior = merchant_counts[merchant]
        merchant_freq = prior / max(1, i)

        distance_km = float(clamp(gaussian_distance_km(), 0, 5000))

        hour = current_time.hour
        weekday = current_time.weekday()

        pz = price_zscore(amount, merchant, typical_price)

        # Recency: seconds since previous transaction (large value = first tx)
        recency_s = float(gap_s) if i > 0 else 3600.0
        recency_s = float(clamp(recency_s, 0, 86400))

        # Merchant entropy in 1h window (take last velocity_1h entries from history)
        recent_merchants_1h = merchant_history_1h[-velocity_1h:] if velocity_1h > 0 else []
        m_entropy = merchant_entropy_score(recent_merchants_1h + [merchant])
        merchant_history_1h.append(merchant)

        p_fraud = fraud_probability(
            amount=amount,
            velocity_5m=velocity_5m,
            velocity_1h=velocity_1h,
            distance_km=distance_km,
            merchant_freq=merchant_freq,
            hour=hour,
            price_z=pz,
            channel=channel,
            category=category,
            recency_s=recency_s,
            merchant_entropy=m_entropy,
        )
        # Deterministic label with small Gaussian jitter to avoid perfectly sharp boundaries
        jitter = random.gauss(0, 0.04)
        fraud = 1 if (p_fraud + jitter) >= 0.42 else 0

        merchant_counts[merchant] += 1

        rows.append(
            {
                "id": f"tx_{i+1:06d}",
                "timestamp": current_time.isoformat(),
                "amount": amount,
                "merchant": merchant,
                "location": "synthetic",
                "channel": channel,
                "category": category,
                "hour": hour,
                "weekday": weekday,
                "velocity_5m": velocity_5m,
                "velocity_1h": velocity_1h,
                "merchant_freq": merchant_freq,
                "distance_km": distance_km,
                "price_z": pz,
                "recency_s": recency_s,
                "merchant_entropy": m_entropy,
                "fraud": fraud,
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)

    print(f"Wrote {len(df)} rows to: {out_path}")
    print(df.head(5).to_string(index=False))
    print("\nFraud rate:", round(df["fraud"].mean(), 4))


if __name__ == "__main__":
    main()
