"""
data_loader.py — Cached data loaders for the Streamlit dashboard.

All loaders use @st.cache_data so data is loaded once per session.
Silver parquets are the source of truth (Gold/Snowflake not required to run the app).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SILVER_PATH  = PROJECT_ROOT / "data" / "silver"
BRONZE_PATH  = PROJECT_ROOT / "data" / "bronze"
MODELS_PATH  = PROJECT_ROOT / "data" / "gold" / "models"


# ─────────────────────────────────────────────────────────────────────────────
# Raw silver loaders
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_orders() -> pd.DataFrame:
    return pd.read_parquet(SILVER_PATH / "orders.parquet")


@st.cache_data(show_spinner=False)
def load_payments() -> pd.DataFrame:
    return pd.read_parquet(SILVER_PATH / "payments.parquet")


@st.cache_data(show_spinner=False)
def load_reviews() -> pd.DataFrame:
    return pd.read_parquet(SILVER_PATH / "reviews.parquet")


@st.cache_data(show_spinner=False)
def load_customers() -> pd.DataFrame:
    return pd.read_parquet(SILVER_PATH / "customers.parquet")


@st.cache_data(show_spinner=False)
def load_sellers() -> pd.DataFrame:
    return pd.read_parquet(SILVER_PATH / "sellers.parquet")


@st.cache_data(show_spinner=False)
def load_products() -> pd.DataFrame:
    return pd.read_parquet(SILVER_PATH / "products.parquet")


@st.cache_data(show_spinner=False)
def load_order_items() -> pd.DataFrame:
    matches = sorted(BRONZE_PATH.glob("*/olist_order_items_dataset.csv"), reverse=True)
    if not matches:
        raise FileNotFoundError(f"olist_order_items_dataset.csv not found under {BRONZE_PATH}")
    return pd.read_csv(matches[0])


# ─────────────────────────────────────────────────────────────────────────────
# Enriched flat dataset (main join used by most pages)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_orders_enriched() -> pd.DataFrame:
    """
    Flat DataFrame joining orders + payments + reviews + customers + sellers
    + products (via first order item).

    Columns of interest:
      order_id, order_purchase_timestamp, order_status,
      delivery_days, delivery_delay_days, is_late,
      total_payment, primary_payment_type, num_installments,
      review_score, is_good_review,
      customer_state, seller_state, seller_id,
      product_weight_g, product_volume_cm3, product_photos_qty,
      price, freight_value,
      order_year, order_month, order_day_of_week
    """
    orders    = load_orders()
    payments  = load_payments()
    reviews   = load_reviews()
    customers = load_customers()
    sellers   = load_sellers()
    products  = load_products()
    items     = load_order_items()

    first_item = (
        items.sort_values("order_item_id")
        .groupby("order_id")
        .first()
        .reset_index()[["order_id", "product_id", "seller_id", "price", "freight_value"]]
    )

    df = (
        orders
        .merge(payments,  on="order_id",  how="left")
        .merge(reviews[["order_id", "review_score"]], on="order_id", how="left")
        .merge(customers[["customer_id", "customer_state"]], on="customer_id", how="left")
        .merge(first_item, on="order_id", how="left")
        .merge(sellers[["seller_id", "seller_state"]], on="seller_id", how="left")
        .merge(products[["product_id", "product_weight_g", "product_volume_cm3",
                          "product_photos_qty"]], on="product_id", how="left")
    )

    # Derived columns
    df["is_good_review"] = (df["review_score"] >= 4).astype("Int64")

    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["order_purchase_timestamp"]):
        df["order_purchase_timestamp"] = pd.to_datetime(
            df["order_purchase_timestamp"], errors="coerce"
        )

    # order_year / order_month if not already present
    if "order_year" not in df.columns:
        df["order_year"]  = df["order_purchase_timestamp"].dt.year
    if "order_month" not in df.columns:
        df["order_month"] = df["order_purchase_timestamp"].dt.month

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Model metric loaders
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_delivery_metrics() -> dict:
    import json
    p = MODELS_PATH / "delivery_metrics.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


@st.cache_data(show_spinner=False)
def load_review_metrics() -> dict:
    import json
    p = MODELS_PATH / "review_metrics.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


@st.cache_data(show_spinner=False)
def load_delivery_feature_importance() -> pd.DataFrame:
    p = MODELS_PATH / "delivery_feature_importance.csv"
    if p.exists():
        return pd.read_csv(p)
    return pd.DataFrame(columns=["feature", "importance"])


@st.cache_data(show_spinner=False)
def load_review_feature_importance() -> pd.DataFrame:
    p = MODELS_PATH / "review_feature_importance.csv"
    if p.exists():
        return pd.read_csv(p)
    return pd.DataFrame(columns=["feature", "importance"])
