"""spark_orders.py - Bronze to Silver transformation for orders."""

import logging
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import TimestampType

from src.config import BRONZE_PATH, SILVER_ORDERS
from src.ingestion.download import get_latest_bronze_folder
from src.transformation.spark_session import get_spark_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

TIMESTAMP_COLS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

STATUSES_TO_DROP = {"unavailable", "created"}


def transform_orders(
    spark: SparkSession | None = None,
    bronze_folder: Path | None = None,
    output_path: Path = SILVER_ORDERS,
) -> DataFrame:
    """
    Read orders CSV from bronze, apply transformations, write silver parquet.

    Returns the transformed DataFrame.
    """
    if spark is None:
        spark = get_spark_session()

    if bronze_folder is None:
        bronze_folder = get_latest_bronze_folder(BRONZE_PATH)

    csv_path = str(bronze_folder / "olist_orders_dataset.csv")
    logger.info("Reading orders from: %s", csv_path)

    df = spark.read.csv(csv_path, header=True, inferSchema=False)
    raw_count = df.count()
    logger.info("Raw orders count: %d", raw_count)

    # --- Cast timestamps ---
    for col in TIMESTAMP_COLS:
        df = df.withColumn(col, F.to_timestamp(F.col(col)))

    # --- Derived date features ---
    df = df.withColumn(
        "delivery_days",
        F.when(
            F.col("order_delivered_customer_date").isNotNull()
            & F.col("order_purchase_timestamp").isNotNull(),
            F.datediff(
                F.col("order_delivered_customer_date"),
                F.col("order_purchase_timestamp"),
            ),
        ).otherwise(F.lit(None).cast("int")),
    )

    df = df.withColumn(
        "estimated_delivery_days",
        F.when(
            F.col("order_estimated_delivery_date").isNotNull()
            & F.col("order_purchase_timestamp").isNotNull(),
            F.datediff(
                F.col("order_estimated_delivery_date"),
                F.col("order_purchase_timestamp"),
            ),
        ).otherwise(F.lit(None).cast("int")),
    )

    df = df.withColumn(
        "is_late",
        F.when(
            F.col("order_delivered_customer_date").isNotNull()
            & F.col("order_estimated_delivery_date").isNotNull(),
            F.col("order_delivered_customer_date") > F.col("order_estimated_delivery_date"),
        ).otherwise(F.lit(None).cast("boolean")),
    )

    df = df.withColumn(
        "delivery_delay_days",
        F.when(
            F.col("is_late") == True,
            F.datediff(
                F.col("order_delivered_customer_date"),
                F.col("order_estimated_delivery_date"),
            ),
        ).otherwise(F.lit(0).cast("int")),
    )

    # --- Time-based features ---
    df = df.withColumn("order_year", F.year(F.col("order_purchase_timestamp")))
    df = df.withColumn("order_month", F.month(F.col("order_purchase_timestamp")))
    df = df.withColumn(
        "order_day_of_week", F.dayofweek(F.col("order_purchase_timestamp"))
    )

    # --- Filter out non-progressed statuses ---
    before_filter = df.count()
    df = df.filter(~F.col("order_status").isin(list(STATUSES_TO_DROP)))
    after_filter = df.count()
    logger.info(
        "Dropped %d rows with status in %s (before=%d, after=%d)",
        before_filter - after_filter,
        STATUSES_TO_DROP,
        before_filter,
        after_filter,
    )

    # --- Deduplicate on order_id ---
    from pyspark.sql.window import Window
    window = Window.partitionBy("order_id").orderBy("order_purchase_timestamp")
    df = df.withColumn("_row_num", F.row_number().over(window))
    df = df.filter(F.col("_row_num") == 1).drop("_row_num")
    deduped_count = df.count()
    logger.info("After dedup: %d rows", deduped_count)

    # --- Write to silver ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write.mode("overwrite").parquet(str(output_path))
    logger.info("Orders silver written to: %s", output_path)

    return df


if __name__ == "__main__":
    df = transform_orders()
    df.printSchema()
    print(f"Silver orders row count: {df.count()}")
