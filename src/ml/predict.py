"""
predict.py — Inference helpers for saved ML models.

Loads delivery_model.joblib and review_model.joblib from data/gold/models/.
Models are lazy-loaded on first call and cached in module-level variables.

Public API
----------
predict_delivery_time(features: dict) -> float
    Predicted delivery days (regression).

predict_review_score(features: dict) -> dict
    {"predicted_class": int, "probability_good": float, "label": str}

Both functions accept partial dicts — missing features fall back to 0 / "unknown".
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Any

import joblib
import numpy as np

warnings.filterwarnings("ignore", message="X does not have valid feature names")

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_PATH  = PROJECT_ROOT / "data" / "gold" / "models"

# ─────────────────────────────────────────────────────────────────────────────
# Lazy model cache
# ─────────────────────────────────────────────────────────────────────────────
_delivery_artifact: dict | None = None
_review_artifact:   dict | None = None


def _load_delivery() -> dict:
    global _delivery_artifact
    if _delivery_artifact is None:
        path = MODELS_PATH / "delivery_model.joblib"
        if not path.exists():
            raise FileNotFoundError(
                f"Delivery model not found at {path}. "
                "Run `python -m src.ml.train` first."
            )
        _delivery_artifact = joblib.load(path)
        logger.info("Delivery model loaded from %s", path)
    return _delivery_artifact


def _load_review() -> dict:
    global _review_artifact
    if _review_artifact is None:
        path = MODELS_PATH / "review_model.joblib"
        if not path.exists():
            raise FileNotFoundError(
                f"Review model not found at {path}. "
                "Run `python -m src.ml.train` first."
            )
        _review_artifact = joblib.load(path)
        logger.info("Review model loaded from %s", path)
    return _review_artifact


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────
def _build_feature_row(features: dict[str, Any], feature_names: list[str]) -> list:
    """Build an ordered list of raw feature values; missing keys → np.nan."""
    row = []
    for name in feature_names:
        val = features.get(name, None)
        row.append(np.nan if val is None else val)
    return row


def _encode_categoricals(
    row: list,
    feature_names: list[str],
    categoricals: list[str],
    encoders: dict,
) -> list:
    """
    Apply LabelEncoder to each categorical column.
    Unknown categories fall back to "unknown" (encoder was trained with that sentinel).
    """
    row = list(row)
    for i, name in enumerate(feature_names):
        if name in categoricals:
            le = encoders[name]
            raw = str(row[i]) if (row[i] is not None and not (isinstance(row[i], float) and np.isnan(row[i]))) else "unknown"
            if raw not in le.classes_:
                raw = "unknown" if "unknown" in le.classes_ else le.classes_[0]
            row[i] = le.transform([raw])[0]
    return row


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def predict_delivery_time(features: dict[str, Any]) -> float:
    """
    Predict delivery time in days for an order.

    Parameters
    ----------
    features : dict
        Keys matching REG_FEATURES from train.py. Missing keys get defaults.
        Expected keys:
          seller_state, customer_state, product_weight_g, product_volume_cm3,
          freight_value, price, primary_payment_type, order_day_of_week,
          order_month, num_installments

    Returns
    -------
    float
        Predicted delivery days (rounded to 1 decimal).
    """
    art = _load_delivery()
    model        = art["model"]
    encoders     = art["encoders"]
    imputer      = art["imputer"]
    feat_names   = art["features"]
    categoricals = art["categoricals"]

    row = _build_feature_row(features, feat_names)
    row = _encode_categoricals(row, feat_names, categoricals, encoders)

    X = np.array(row, dtype=object).reshape(1, -1)
    X_imputed = imputer.transform(X)

    pred = model.predict(X_imputed)[0]
    return round(float(pred), 1)


def predict_review_score(features: dict[str, Any]) -> dict:
    """
    Predict whether an order will receive a good review (score >= 4).

    Parameters
    ----------
    features : dict
        Keys matching CLF_FEATURES from train.py. Missing keys get defaults.
        Expected keys:
          delivery_days, delivery_delay_days, price, freight_value,
          product_weight_g, product_photos_qty, num_installments,
          is_late_int (0 or 1)

    Returns
    -------
    dict with keys:
        predicted_class  : int   — 1 (good) or 0 (bad)
        probability_good : float — probability of class 1
        label            : str   — "good (>= 4)" or "bad (< 4)"
    """
    art = _load_review()
    model      = art["model"]
    imputer    = art["imputer"]
    feat_names = art["features"]

    row = _build_feature_row(features, feat_names)

    X = np.array(row, dtype=float).reshape(1, -1)
    X_imputed = imputer.transform(X)

    pred_class = int(model.predict(X_imputed)[0])

    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X_imputed)[0]
        # class order is [0, 1]; index 1 = "good"
        prob_good = float(proba[1])
    else:
        prob_good = float(pred_class)

    label = "good (>= 4)" if pred_class == 1 else "bad (< 4)"

    return {
        "predicted_class":  pred_class,
        "probability_good": round(prob_good, 4),
        "label":            label,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    sample_delivery = {
        "seller_state":         "SP",
        "customer_state":       "RJ",
        "product_weight_g":     500,
        "product_volume_cm3":   2000,
        "freight_value":        15.0,
        "price":                89.90,
        "primary_payment_type": "credit_card",
        "order_day_of_week":    2,
        "order_month":          6,
        "num_installments":     3,
    }
    days = predict_delivery_time(sample_delivery)
    print(f"Predicted delivery time: {days} days")

    sample_review = {
        "delivery_days":       days,
        "delivery_delay_days": 0.0,
        "price":               89.90,
        "freight_value":       15.0,
        "product_weight_g":    500,
        "product_photos_qty":  3,
        "num_installments":    3,
        "is_late_int":         0,
    }
    result = predict_review_score(sample_review)
    print(f"Predicted review:       {result['label']}  (p_good={result['probability_good']:.3f})")
