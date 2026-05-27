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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SILVER_PATH = PROJECT_ROOT / "data" / "silver"
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze"
MODELS_PATH = PROJECT_ROOT / "data" / "gold" / "models"

MODELS_PATH.mkdir(parents=True, exist_ok=True)


def load_training_data() -> pd.DataFrame:
    logger.info("Loading Silver parquets...")
    orders    = pd.read_parquet(SILVER_PATH / "orders.parquet")
    payments  = pd.read_parquet(SILVER_PATH / "payments.parquet")
    reviews   = pd.read_parquet(SILVER_PATH / "reviews.parquet")
    customers = pd.read_parquet(SILVER_PATH / "customers.parquet")
    sellers   = pd.read_parquet(SILVER_PATH / "sellers.parquet")
    products  = pd.read_parquet(SILVER_PATH / "products.parquet")

    # order_items not in silver — load from bronze
    matches = sorted(BRONZE_PATH.glob("*/olist_order_items_dataset.csv"), reverse=True)
    if not matches:
        raise FileNotFoundError(f"olist_order_items_dataset.csv not found under {BRONZE_PATH}")
    items = pd.read_csv(matches[0])

    first_item = (
        items.sort_values("order_item_id")
        .groupby("order_id")
        .first()
        .reset_index()[["order_id", "product_id", "seller_id", "price", "freight_value"]]
    )

    logger.info("Joining datasets...")
    df = (
        orders
        .merge(payments,  on="order_id",   how="left")
        .merge(reviews[["order_id", "review_score"]],  on="order_id", how="left")
        .merge(customers[["customer_id", "customer_state"]], on="customer_id", how="left")
        .merge(first_item, on="order_id",  how="left")
        .merge(sellers[["seller_id", "seller_state"]],   on="seller_id",   how="left")
        .merge(products[["product_id", "product_weight_g", "product_volume_cm3",
                          "product_photos_qty"]], on="product_id", how="left")
    )

    logger.info("Combined dataset shape: %s", df.shape)
    return df


REG_FEATURES = [
    "seller_state", "customer_state",
    "product_weight_g", "product_volume_cm3",
    "freight_value", "price",
    "primary_payment_type",
    "order_day_of_week", "order_month",
    "num_installments",
]
REG_CATEGORICALS = ["seller_state", "customer_state", "primary_payment_type"]
REG_TARGET = "delivery_days"


def train_delivery_model(df: pd.DataFrame) -> dict:
    logger.info("Training delivery time prediction model (regression)")

    data = df[df[REG_TARGET].notna() & (df["order_status"] == "delivered")].copy()
    logger.info("Training samples: %s", f"{len(data):,}")

    # LabelEncoder for tree models — keeps dimensionality low vs OHE
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
        "LinearRegression":          LinearRegression(),
        "RandomForestRegressor":     RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
        "GradientBoostingRegressor": GradientBoostingRegressor(n_estimators=100, random_state=42),
    }

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
    logger.info("Best: %s", best_name)

    best_model = candidates[best_name]
    best_model.fit(X_imputed, y)

    if hasattr(best_model, "feature_importances_"):
        importances = best_model.feature_importances_
    else:
        importances = np.abs(best_model.coef_) / np.abs(best_model.coef_).sum()

    fi_df = pd.DataFrame({"feature": REG_FEATURES, "importance": importances})
    fi_df = fi_df.sort_values("importance", ascending=False)

    joblib.dump(
        {"model": best_model, "encoders": encoders, "imputer": imputer,
         "features": REG_FEATURES, "categoricals": REG_CATEGORICALS},
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
    logger.info("Delivery model saved -> %s", MODELS_PATH / "delivery_model.joblib")
    return metrics_out


CLF_FEATURES = [
    "delivery_days",
    "delivery_delay_days",
    "price",
    "freight_value",
    "product_weight_g",
    "product_photos_qty",
    "num_installments",
]
CLF_TARGET = "is_good_review"


def train_review_model(df: pd.DataFrame) -> dict:
    logger.info("Training review score classification model (binary)")

    data = df[df["review_score"].notna()].copy()
    data[CLF_TARGET] = (data["review_score"] >= 4).astype(int)

    if "is_late" in data.columns:
        data["is_late_int"] = data["is_late"].map({"True": 1, "False": 0, True: 1, False: 0}).fillna(0).astype(int)
        clf_features_use = CLF_FEATURES + ["is_late_int"]
    else:
        clf_features_use = CLF_FEATURES

    logger.info("Training samples: %s", f"{len(data):,}")
    logger.info("Class balance - good: %.1f%%  bad: %.1f%%",
                data[CLF_TARGET].mean() * 100,
                (1 - data[CLF_TARGET].mean()) * 100)

    X = data[clf_features_use].copy()
    y = data[CLF_TARGET]

    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_imputed, y, test_size=0.2, random_state=42, stratify=y
    )

    candidates = {
        "LogisticRegression":         LogisticRegression(max_iter=1000, random_state=42),
        "RandomForestClassifier":     RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1),
        "GradientBoostingClassifier": GradientBoostingClassifier(n_estimators=100, random_state=42),
    }

    results = {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        acc  = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, zero_division=0)
        rec  = recall_score(y_test, preds, zero_division=0)
        f1   = f1_score(y_test, preds, zero_division=0)
        results[name] = {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }
        logger.info("  %-35s Acc=%.4f  F1=%.4f  Prec=%.4f  Rec=%.4f",
                    name, acc, f1, prec, rec)

    best_name = max(results, key=lambda k: results[k]["f1"])
    logger.info("Best: %s", best_name)

    best_model = candidates[best_name]
    best_model.fit(X_imputed, y)

    best_candidate = candidates[best_name]
    best_candidate.fit(X_train, y_train)
    cm = confusion_matrix(y_test, best_candidate.predict(X_test)).tolist()

    if hasattr(best_model, "feature_importances_"):
        importances = best_model.feature_importances_
    else:
        importances = np.abs(best_model.coef_[0]) / np.abs(best_model.coef_[0]).sum()

    fi_df = pd.DataFrame({"feature": clf_features_use, "importance": importances})
    fi_df = fi_df.sort_values("importance", ascending=False)

    joblib.dump(
        {"model": best_model, "imputer": imputer,
         "features": clf_features_use, "target": CLF_TARGET},
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
        "features": clf_features_use,
    }
    (MODELS_PATH / "review_metrics.json").write_text(json.dumps(metrics_out, indent=2))
    logger.info("Review model saved -> %s", MODELS_PATH / "review_model.joblib")
    return metrics_out


def main():
    df = load_training_data()

    delivery_metrics = train_delivery_model(df)
    review_metrics   = train_review_model(df)

    logger.info("Training complete")
    logger.info("Delivery: %s  RMSE=%.3f  R2=%.4f",
                delivery_metrics["best_model"],
                delivery_metrics["best_metrics"]["RMSE"],
                delivery_metrics["best_metrics"]["R2"])
    logger.info("Review:   %s  F1=%.4f  Acc=%.4f",
                review_metrics["best_model"],
                review_metrics["best_metrics"]["f1"],
                review_metrics["best_metrics"]["accuracy"])
    logger.info("Models saved to: %s", MODELS_PATH)


if __name__ == "__main__":
    main()
