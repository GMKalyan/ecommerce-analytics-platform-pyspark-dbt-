"""
test_data_quality.py — Post-transformation Silver layer quality checks.

Reads actual Parquet files from data/silver/ and validates:
  - No nulls in primary keys
  - delivery_days >= 0 where not null
  - payment_value > 0
  - Row counts are non-zero
"""

import pytest
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


SILVER_PATH = Path(__file__).resolve().parent.parent / "data" / "silver"


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder
        .appName("test-data-quality")
        .master("local[1]")
        .config("spark.driver.memory", "1g")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.ansi.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session


def _skip_if_missing(path: Path):
    if not path.exists():
        pytest.skip(f"Silver file not found (run transformations first): {path}")


class TestSilverOrders:
    def test_primary_key_not_null(self, spark):
        p = SILVER_PATH / "orders.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        null_count = df.filter(F.col("order_id").isNull()).count()
        assert null_count == 0, f"Found {null_count} null order_ids in silver orders"

    def test_customer_id_not_null(self, spark):
        p = SILVER_PATH / "orders.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        null_count = df.filter(F.col("customer_id").isNull()).count()
        assert null_count == 0, f"Found {null_count} null customer_ids in silver orders"

    def test_delivery_days_nonnegative(self, spark):
        p = SILVER_PATH / "orders.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        neg = df.filter(
            F.col("delivery_days").isNotNull() & (F.col("delivery_days") < 0)
        ).count()
        assert neg == 0, f"Found {neg} rows with negative delivery_days"

    def test_row_count_nonzero(self, spark):
        p = SILVER_PATH / "orders.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        assert df.count() > 0

    def test_no_dropped_statuses(self, spark):
        p = SILVER_PATH / "orders.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        bad = df.filter(F.col("order_status").isin(["unavailable", "created"])).count()
        assert bad == 0


class TestSilverProducts:
    def test_primary_key_not_null(self, spark):
        p = SILVER_PATH / "products.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        null_count = df.filter(F.col("product_id").isNull()).count()
        assert null_count == 0

    def test_row_count_nonzero(self, spark):
        p = SILVER_PATH / "products.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        assert df.count() > 0

    def test_no_dup_product_id(self, spark):
        p = SILVER_PATH / "products.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        total = df.count()
        distinct = df.select("product_id").distinct().count()
        assert total == distinct


class TestSilverCustomers:
    def test_primary_key_not_null(self, spark):
        p = SILVER_PATH / "customers.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        assert df.filter(F.col("customer_id").isNull()).count() == 0

    def test_row_count_nonzero(self, spark):
        p = SILVER_PATH / "customers.parquet"
        _skip_if_missing(p)
        assert spark.read.parquet(str(p)).count() > 0


class TestSilverSellers:
    def test_primary_key_not_null(self, spark):
        p = SILVER_PATH / "sellers.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        assert df.filter(F.col("seller_id").isNull()).count() == 0

    def test_row_count_nonzero(self, spark):
        p = SILVER_PATH / "sellers.parquet"
        _skip_if_missing(p)
        assert spark.read.parquet(str(p)).count() > 0


class TestSilverPayments:
    def test_payment_value_positive(self, spark):
        p = SILVER_PATH / "payments.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        neg = df.filter(F.col("total_payment") <= 0).count()
        assert neg == 0, f"Found {neg} rows with total_payment <= 0"

    def test_order_id_not_null(self, spark):
        p = SILVER_PATH / "payments.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        assert df.filter(F.col("order_id").isNull()).count() == 0

    def test_row_count_nonzero(self, spark):
        p = SILVER_PATH / "payments.parquet"
        _skip_if_missing(p)
        assert spark.read.parquet(str(p)).count() > 0


class TestSilverReviews:
    def test_primary_key_not_null(self, spark):
        p = SILVER_PATH / "reviews.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        assert df.filter(F.col("review_id").isNull()).count() == 0

    def test_order_id_not_null(self, spark):
        p = SILVER_PATH / "reviews.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        assert df.filter(F.col("order_id").isNull()).count() == 0

    def test_row_count_nonzero(self, spark):
        p = SILVER_PATH / "reviews.parquet"
        _skip_if_missing(p)
        assert spark.read.parquet(str(p)).count() > 0

    def test_one_review_per_order(self, spark):
        p = SILVER_PATH / "reviews.parquet"
        _skip_if_missing(p)
        df = spark.read.parquet(str(p))
        total = df.count()
        distinct_orders = df.select("order_id").distinct().count()
        assert total == distinct_orders
