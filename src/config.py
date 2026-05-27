"""
config.py — Central configuration for the ecommerce analytics platform.

Loads environment variables, defines all data paths, expected schemas,
and Snowflake connection parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Java / PySpark bootstrap — set JAVA_HOME if not already in environment
# ---------------------------------------------------------------------------
_JAVA_CANDIDATES = [
    r"C:\Program Files\Microsoft\jdk-21.0.10.7-hotspot",
    r"C:\Program Files\Java\jdk-21",
    r"C:\Program Files\Eclipse Adoptium\jdk-21.0.0+35",
]
if not os.environ.get("JAVA_HOME"):
    for _candidate in _JAVA_CANDIDATES:
        if os.path.isfile(os.path.join(_candidate, "bin", "java.exe")):
            os.environ["JAVA_HOME"] = _candidate
            os.environ["PATH"] = os.path.join(_candidate, "bin") + os.pathsep + os.environ.get("PATH", "")
            break

# HADOOP_HOME — required on Windows for PySpark to write parquet/temp files
_HADOOP_CANDIDATES = [r"C:\winutils", r"C:\hadoop"]
if not os.environ.get("HADOOP_HOME"):
    for _h in _HADOOP_CANDIDATES:
        if os.path.isfile(os.path.join(_h, "bin", "winutils.exe")):
            os.environ["HADOOP_HOME"] = _h
            os.environ["PATH"] = os.path.join(_h, "bin") + os.pathsep + os.environ.get("PATH", "")
            break

# PYSPARK_PYTHON — must point to the real Python exe, not the Windows Store alias
import sys as _sys
if not os.environ.get("PYSPARK_PYTHON"):
    os.environ["PYSPARK_PYTHON"] = _sys.executable
if not os.environ.get("PYSPARK_DRIVER_PYTHON"):
    os.environ["PYSPARK_DRIVER_PYTHON"] = _sys.executable

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()  # reads .env if present; silently skips if missing

# ---------------------------------------------------------------------------
# Root paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = PROJECT_ROOT.parent / "archive"   # raw CSVs live here (one level up)

DATA_DIR = PROJECT_ROOT / "data"
BRONZE_PATH = DATA_DIR / "bronze"
SILVER_PATH = DATA_DIR / "silver"
GOLD_PATH = DATA_DIR / "gold"

# ---------------------------------------------------------------------------
# Expected CSV filenames
# ---------------------------------------------------------------------------
EXPECTED_FILES = [
    "olist_orders_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "product_category_name_translation.csv",
]

# ---------------------------------------------------------------------------
# Expected schemas: {filename: {column_name: expected_pandas_dtype_string}}
# Dtypes are loose — validation checks presence, not strict type matching.
# Key columns listed first (used for null-check validation).
# ---------------------------------------------------------------------------
EXPECTED_SCHEMAS = {
    "olist_orders_dataset.csv": {
        "order_id": "object",
        "customer_id": "object",
        "order_status": "object",
        "order_purchase_timestamp": "object",
        "order_approved_at": "object",
        "order_delivered_carrier_date": "object",
        "order_delivered_customer_date": "object",
        "order_estimated_delivery_date": "object",
    },
    "olist_customers_dataset.csv": {
        "customer_id": "object",
        "customer_unique_id": "object",
        "customer_zip_code_prefix": "int64",
        "customer_city": "object",
        "customer_state": "object",
    },
    "olist_order_items_dataset.csv": {
        "order_id": "object",
        "order_item_id": "int64",
        "product_id": "object",
        "seller_id": "object",
        "shipping_limit_date": "object",
        "price": "float64",
        "freight_value": "float64",
    },
    "olist_order_payments_dataset.csv": {
        "order_id": "object",
        "payment_sequential": "int64",
        "payment_type": "object",
        "payment_installments": "int64",
        "payment_value": "float64",
    },
    "olist_order_reviews_dataset.csv": {
        "review_id": "object",
        "order_id": "object",
        "review_score": "int64",
        "review_comment_title": "object",
        "review_comment_message": "object",
        "review_creation_date": "object",
        "review_answer_timestamp": "object",
    },
    "olist_products_dataset.csv": {
        "product_id": "object",
        "product_category_name": "object",
        "product_name_lenght": "float64",      # note: original has typo
        "product_description_lenght": "float64",
        "product_photos_qty": "float64",
        "product_weight_g": "float64",
        "product_length_cm": "float64",
        "product_height_cm": "float64",
        "product_width_cm": "float64",
    },
    "olist_sellers_dataset.csv": {
        "seller_id": "object",
        "seller_zip_code_prefix": "int64",
        "seller_city": "object",
        "seller_state": "object",
    },
    "olist_geolocation_dataset.csv": {
        "geolocation_zip_code_prefix": "int64",
        "geolocation_lat": "float64",
        "geolocation_lng": "float64",
        "geolocation_city": "object",
        "geolocation_state": "object",
    },
    "product_category_name_translation.csv": {
        "product_category_name": "object",
        "product_category_name_english": "object",
    },
}

# Columns that MUST NOT be null (per file) — critical data quality check
NOT_NULL_COLUMNS = {
    "olist_orders_dataset.csv": ["order_id", "customer_id", "order_status"],
    "olist_customers_dataset.csv": ["customer_id", "customer_unique_id"],
    "olist_order_items_dataset.csv": ["order_id", "product_id", "seller_id"],
    "olist_order_payments_dataset.csv": ["order_id", "payment_value"],
    "olist_order_reviews_dataset.csv": ["review_id", "order_id", "review_score"],
    "olist_products_dataset.csv": ["product_id"],
    "olist_sellers_dataset.csv": ["seller_id"],
    "olist_geolocation_dataset.csv": ["geolocation_zip_code_prefix"],
    "product_category_name_translation.csv": ["product_category_name"],
}

# Date columns to validate parseability (per file)
DATE_COLUMNS = {
    "olist_orders_dataset.csv": [
        "order_purchase_timestamp",
        "order_estimated_delivery_date",
    ],
    "olist_order_items_dataset.csv": ["shipping_limit_date"],
    "olist_order_reviews_dataset.csv": ["review_creation_date"],
}

# ---------------------------------------------------------------------------
# Silver layer output paths
# ---------------------------------------------------------------------------
SILVER_ORDERS = SILVER_PATH / "orders.parquet"
SILVER_PRODUCTS = SILVER_PATH / "products.parquet"
SILVER_CUSTOMERS = SILVER_PATH / "customers.parquet"
SILVER_SELLERS = SILVER_PATH / "sellers.parquet"
SILVER_PAYMENTS = SILVER_PATH / "payments.parquet"
SILVER_REVIEWS = SILVER_PATH / "reviews.parquet"

# ---------------------------------------------------------------------------
# Snowflake connection parameters (loaded from environment)
# ---------------------------------------------------------------------------
SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "user": os.getenv("SNOWFLAKE_USER", ""),
    "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
    "database": os.getenv("SNOWFLAKE_DATABASE", "ECOMMERCE_DB"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
}

# ---------------------------------------------------------------------------
# PySpark settings
# ---------------------------------------------------------------------------
SPARK_APP_NAME = "ecommerce-analytics"
SPARK_MASTER = "local[*]"
SPARK_DRIVER_MEMORY = "2g"
SPARK_EXECUTOR_MEMORY = "2g"
