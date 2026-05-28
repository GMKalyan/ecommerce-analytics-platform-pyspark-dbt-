import json
import logging
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

try:
    from xgboost import XGBClassifier, XGBRegressor
    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SILVER_PATH  = PROJECT_ROOT / "data" / "silver"
BRONZE_PATH  = PROJECT_ROOT / "data" / "bronze"
MODELS_PATH  = PROJECT_ROOT / "data" / "gold" / "models"

MODELS_PATH.mkdir(parents=True, exist_ok=True)


def _haversine_km(lat1: np.ndarray, lon1: np.ndarray,
                   lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Vectorised haversine distance in km."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _load_geo_centroids() -> pd.DataFrame:
    """Return median lat/lng per zip code prefix from the geolocation CSV."""
    matches = sorted(BRONZE_PATH.glob("*/olist_geolocation_dataset.csv"), reverse=True)
    if not matches:
        logger.warning("Geolocation CSV not found — distance feature will be NaN.")
        return pd.DataFrame(columns=["zip_prefix", "lat", "lng"])
    geo = pd.read_csv(matches[0], dtype={"geolocation_zip_code_prefix": str})
    centroids = (
        geo.groupby("geolocation_zip_code_prefix")[["geolocation_lat", "geolocation_lng"]]
        .median()
        .reset_index()
        .rename(columns={
            "geolocation_zip_code_prefix": "zip_prefix",
            "geolocation_lat": "lat",
            "geolocation_lng": "lng",
        })
    )
    centroids["zip_prefix"] = centroids["zip_prefix"].astype(str)
    return centroids


def load_training_data() -> pd.DataFrame:
    logger.info("Loading Silver parquets...")
    orders    = pd.read_parquet(SILVER_PATH / "orders.parquet")
    payments  = pd.read_parquet(SILVER_PATH / "payments.parquet")
    reviews   = pd.read_parquet(SILVER_PATH / "reviews.parquet")
    customers = pd.read_parquet(SILVER_PATH / "customers.parquet")
    sellers   = pd.read_parquet(SILVER_PATH / "sellers.parquet")
    products  = pd.read_parquet(SILVER_PATH / "products.parquet")

    matches = sorted(BRONZE_PATH.glob("*/olist_order_items_dataset.csv"), reverse=True)
    if not matches:
        raise FileNotFoundError(f"olist_order_items_dataset.csv not found under {BRONZE_PATH}")
    items = pd.read_csv(matches[0])

    # Per-order item aggregates
    item_agg = items.groupby("order_id").agg(
        item_count=("order_item_id", "count"),
        total_price=("price", "sum"),
        total_freight=("freight_value", "sum"),
    ).reset_index()

    first_item = (
        items.sort_values("order_item_id")
        .groupby("order_id")
        .first()
        .reset_index()[["order_id", "product_id", "seller_id", "price", "freight_value"]]
    )

    logger.info("Joining datasets...")
    df = (
        orders
        .merge(payments, on="order_id", how="left")
        .merge(
            reviews[["order_id", "review_score",
                     "review_comment_message", "review_comment_title"]],
            on="order_id", how="left",
        )
        .merge(
            customers[["customer_id", "customer_state", "customer_zip_code_prefix"]],
            on="customer_id", how="left",
        )
        .merge(first_item, on="order_id", how="left")
        .merge(
            sellers[["seller_id", "seller_state", "seller_zip_code_prefix"]],
            on="seller_id", how="left",
        )
        .merge(
            products[["product_id", "product_category_name",
                       "product_weight_g", "product_volume_cm3", "product_photos_qty"]],
            on="product_id", how="left",
        )
        .merge(item_agg, on="order_id", how="left")
    )

    # Freight ratio: freight as share of total order cost
    total_cost = df["total_price"] + df["total_freight"]
    df["freight_ratio"] = (df["total_freight"] / total_cost.replace(0, np.nan)).round(4)

    # Product category — keep top 20, collapse rest to 'other'
    top_cats = df["product_category_name"].value_counts().nlargest(20).index
    df["product_category"] = (
        df["product_category_name"]
        .where(df["product_category_name"].isin(top_cats), other="other")
        .fillna("other")
    )

    # Geolocation distance
    logger.info("Computing geolocation distances...")
    centroids = _load_geo_centroids()
    if not centroids.empty:
        cust_geo = centroids.rename(columns={
            "zip_prefix": "customer_zip_code_prefix",
            "lat": "cust_lat", "lng": "cust_lng",
        })
        sell_geo = centroids.rename(columns={
            "zip_prefix": "seller_zip_code_prefix",
            "lat": "sell_lat", "lng": "sell_lng",
        })
        df["customer_zip_code_prefix"] = df["customer_zip_code_prefix"].astype(str)
        df["seller_zip_code_prefix"]   = df["seller_zip_code_prefix"].astype(str)
        df = df.merge(cust_geo, on="customer_zip_code_prefix", how="left")
        df = df.merge(sell_geo, on="seller_zip_code_prefix",   how="left")

        mask = df["cust_lat"].notna() & df["sell_lat"].notna()
        df["distance_km"] = np.nan
        if mask.any():
            df.loc[mask, "distance_km"] = _haversine_km(
                df.loc[mask, "cust_lat"].values,
                df.loc[mask, "cust_lng"].values,
                df.loc[mask, "sell_lat"].values,
                df.loc[mask, "sell_lng"].values,
            )
        df = df.drop(columns=["cust_lat", "cust_lng", "sell_lat", "sell_lng"])
        logger.info("Distance computed for %d/%d orders", mask.sum(), len(df))
    else:
        df["distance_km"] = np.nan

    # Seller historical features — expand mean shifted by 1 to prevent leakage
    df["order_purchase_timestamp"] = pd.to_datetime(
        df["order_purchase_timestamp"], errors="coerce"
    )
    df = df.sort_values("order_purchase_timestamp")

    df["seller_avg_delivery"] = (
        df.groupby("seller_id")["delivery_days"]
        .transform(lambda x: x.shift(1).expanding().mean())
    )
    df["seller_avg_review"] = (
        df.groupby("seller_id")["review_score"]
        .transform(lambda x: x.shift(1).expanding().mean())
    )

    # Review text signals
    df["comment_length"] = (
        df["review_comment_message"].fillna("").str.len()
        + df["review_comment_title"].fillna("").str.len()
    )
    df["has_comment"] = (df["comment_length"] > 0).astype(int)

    logger.info("Dataset shape after feature engineering: %s", df.shape)
    return df


# ── Delivery Time Regression ──────────────────────────────────────────────────

REG_FEATURES = [
    "seller_state", "customer_state",          # geographic categorical
    "distance_km",                              # seller→customer haversine km
    "product_weight_g", "product_volume_cm3",  # physical attributes
    "product_category",                         # category (encoded)
    "freight_value", "price",                  # cost signals
    "freight_ratio", "item_count",             # order-level
    "primary_payment_type",                    # payment categorical
    "num_installments",
    "order_day_of_week", "order_month",        # temporal
    "seller_avg_delivery",                     # seller history
]
REG_CATEGORICALS = [
    "seller_state", "customer_state", "primary_payment_type", "product_category"
]
REG_TARGET = "delivery_days"


def train_delivery_model(df: pd.DataFrame) -> dict:
    logger.info("Training delivery time prediction model (regression)")

    data = df[df[REG_TARGET].notna() & (df["order_status"] == "delivered")].copy()
    logger.info("Training samples: %s", f"{len(data):,}")

    encoders: dict[str, LabelEncoder] = {}
    for col in REG_CATEGORICALS:
        le = LabelEncoder()
        data[col] = le.fit_transform(data[col].fillna("unknown").astype(str))
        encoders[col] = le

    X = data[REG_FEATURES].copy()
    y = data[REG_TARGET].astype(float)

    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_imputed, y, test_size=0.2, random_state=42
    )
    logger.info("Train: %s  Test: %s", f"{len(X_train):,}", f"{len(X_test):,}")

    candidates = {
        "LinearRegression": LinearRegression(),
        "RandomForestRegressor": RandomForestRegressor(
            n_estimators=200, max_depth=12, min_samples_leaf=5,
            random_state=42, n_jobs=-1,
        ),
        "GradientBoostingRegressor": GradientBoostingRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, min_samples_leaf=10, random_state=42,
        ),
    }
    if _XGB_AVAILABLE:
        candidates["XGBRegressor"] = XGBRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
            random_state=42, n_jobs=-1, verbosity=0,
        )

    results = {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        mae  = mean_absolute_error(y_test, preds)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        r2   = r2_score(y_test, preds)
        results[name] = {"MAE": round(mae, 3), "RMSE": round(rmse, 3), "R2": round(r2, 4)}
        logger.info("  %-35s MAE=%.2f  RMSE=%.2f  R2=%.4f", name, mae, rmse, r2)

    best_name = min(results, key=lambda k: results[k]["RMSE"])
    logger.info("Best: %s  RMSE=%.3f  R2=%.4f",
                best_name, results[best_name]["RMSE"], results[best_name]["R2"])

    best_model = candidates[best_name]
    best_model.fit(X_imputed, y)

    if hasattr(best_model, "feature_importances_"):
        importances = np.asarray(best_model.feature_importances_).flatten()
    else:
        coef = np.abs(best_model.coef_).flatten()
        importances = coef / (coef.sum() + 1e-9)

    n = min(len(importances), len(REG_FEATURES))
    fi_df = (
        pd.DataFrame({"feature": REG_FEATURES[:n], "importance": importances[:n]})
        .sort_values("importance", ascending=False)
    )

    joblib.dump(
        {
            "model": best_model,
            "encoders": encoders,
            "imputer": imputer,
            "features": REG_FEATURES,
            "categoricals": REG_CATEGORICALS,
        },
        MODELS_PATH / "delivery_model.joblib",
    )
    fi_df.to_csv(MODELS_PATH / "delivery_feature_importance.csv", index=False)

    metrics_out = {
        "best_model": best_name,
        "all_models": results,
        "best_metrics": results[best_name],
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "target": REG_TARGET,
        "features": REG_FEATURES,
    }
    (MODELS_PATH / "delivery_metrics.json").write_text(json.dumps(metrics_out, indent=2))
    logger.info("Delivery model saved -> %s", MODELS_PATH)
    return metrics_out


# ── Review Score Classification ───────────────────────────────────────────────

CLF_FEATURES = [
    "delivery_days", "delivery_delay_days", "is_late_int",
    "price", "freight_value", "freight_ratio", "item_count",
    "product_weight_g", "product_photos_qty",
    "product_category",
    "num_installments",
    "seller_avg_review",
    "comment_length", "has_comment",
    "distance_km",
]
CLF_CATEGORICALS = ["product_category"]
CLF_TARGET = "is_good_review"


def train_review_model(df: pd.DataFrame) -> dict:
    logger.info("Training review score classification model (binary)")

    data = df[df["review_score"].notna()].copy()
    data[CLF_TARGET] = (data["review_score"] >= 4).astype(int)

    if "is_late" in data.columns:
        data["is_late_int"] = (
            data["is_late"].map({"True": 1, "False": 0, True: 1, False: 0}).fillna(0).astype(int)
        )
    else:
        data["is_late_int"] = 0

    logger.info("Training samples: %s", f"{len(data):,}")
    pos_rate = data[CLF_TARGET].mean()
    logger.info("Class balance - good: %.1f%%  bad: %.1f%%",
                pos_rate * 100, (1 - pos_rate) * 100)

    # Label-encode categoricals
    encoders: dict[str, LabelEncoder] = {}
    for col in CLF_CATEGORICALS:
        le = LabelEncoder()
        data[col] = le.fit_transform(data[col].fillna("unknown").astype(str))
        encoders[col] = le

    X = data[CLF_FEATURES].copy()
    y = data[CLF_TARGET]

    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_imputed, y, test_size=0.2, random_state=42, stratify=y
    )

    # scale_pos_weight for XGBoost: ratio of negatives to positives
    neg_pos_ratio = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    candidates = {
        "LogisticRegression": LogisticRegression(
            max_iter=1000, random_state=42, class_weight="balanced",
        ),
        "RandomForestClassifier": RandomForestClassifier(
            n_estimators=200, max_depth=12, min_samples_leaf=5,
            random_state=42, n_jobs=-1, class_weight="balanced",
        ),
        "GradientBoostingClassifier": GradientBoostingClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, min_samples_leaf=10, random_state=42,
        ),
    }
    if _XGB_AVAILABLE:
        candidates["XGBClassifier"] = XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
            scale_pos_weight=neg_pos_ratio,
            random_state=42, n_jobs=-1, verbosity=0, eval_metric="logloss",
        )

    results = {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        acc   = accuracy_score(y_test, preds)
        prec  = precision_score(y_test, preds, zero_division=0, average="macro")
        rec   = recall_score(y_test, preds, zero_division=0, average="macro")
        f1    = f1_score(y_test, preds, zero_division=0, average="macro")
        results[name] = {
            "accuracy": round(acc, 4),
            "precision_macro": round(prec, 4),
            "recall_macro": round(rec, 4),
            "f1_macro": round(f1, 4),
        }
        logger.info("  %-35s Acc=%.4f  F1_macro=%.4f  Prec=%.4f  Rec=%.4f",
                    name, acc, f1, prec, rec)

    best_name = max(results, key=lambda k: results[k]["f1_macro"])
    logger.info("Best: %s  F1_macro=%.4f  Acc=%.4f",
                best_name, results[best_name]["f1_macro"], results[best_name]["accuracy"])

    best_model = candidates[best_name]
    best_model.fit(X_imputed, y)

    best_eval = candidates[best_name]
    best_eval.fit(X_train, y_train)
    cm = confusion_matrix(y_test, best_eval.predict(X_test)).tolist()

    if hasattr(best_model, "feature_importances_"):
        importances = np.asarray(best_model.feature_importances_).flatten()
    else:
        coef = np.abs(best_model.coef_[0]).flatten()
        importances = coef / (coef.sum() + 1e-9)

    n = min(len(importances), len(CLF_FEATURES))
    fi_df = (
        pd.DataFrame({"feature": CLF_FEATURES[:n], "importance": importances[:n]})
        .sort_values("importance", ascending=False)
    )

    joblib.dump(
        {
            "model": best_model,
            "encoders": encoders,
            "imputer": imputer,
            "features": CLF_FEATURES,
            "categoricals": CLF_CATEGORICALS,
            "target": CLF_TARGET,
        },
        MODELS_PATH / "review_model.joblib",
    )
    fi_df.to_csv(MODELS_PATH / "review_feature_importance.csv", index=False)

    metrics_out = {
        "best_model": best_name,
        "all_models": results,
        "best_metrics": results[best_name],
        "confusion_matrix": cm,
        "class_labels": ["bad (< 4)", "good (>= 4)"],
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "target": CLF_TARGET,
        "features": CLF_FEATURES,
    }
    (MODELS_PATH / "review_metrics.json").write_text(json.dumps(metrics_out, indent=2))
    logger.info("Review model saved -> %s", MODELS_PATH)
    return metrics_out


def main():
    df = load_training_data()
    delivery_metrics = train_delivery_model(df)
    review_metrics   = train_review_model(df)

    logger.info("--- Results ---")
    logger.info("Delivery: %s  RMSE=%.3f  R2=%.4f",
                delivery_metrics["best_model"],
                delivery_metrics["best_metrics"]["RMSE"],
                delivery_metrics["best_metrics"]["R2"])
    logger.info("Review:   %s  F1_macro=%.4f  Acc=%.4f",
                review_metrics["best_model"],
                review_metrics["best_metrics"]["f1_macro"],
                review_metrics["best_metrics"]["accuracy"])


if __name__ == "__main__":
    main()
