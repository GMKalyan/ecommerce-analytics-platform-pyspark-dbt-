"""
spark_payments.py — Bronze → Silver transformation for payments.

Transformations:
  - Filter out rows where payment_value <= 0
  - Aggregate per order_id:
      total_payment: sum of payment_value
      num_installments: max payment_installments
      primary_payment_type: payment_type with highest total value
  - Write to data/silver/payments.parquet
"""

import logging
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from src.config import BRONZE_PATH, SILVER_PAYMENTS
from src.ingestion.download import get_latest_bronze_folder
from src.transformation.spark_session import get_spark_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def transform_payments(
    spark: SparkSession | None = None,
    bronze_folder: Path | None = None,
    output_path: Path = SILVER_PAYMENTS,
) -> DataFrame:
    if spark is None:
        spark = get_spark_session()

    if bronze_folder is None:
        bronze_folder = get_latest_bronze_folder(BRONZE_PATH)

    csv_path = str(bronze_folder / "olist_order_payments_dataset.csv")
    logger.info("Reading payments from: %s", csv_path)

    df = spark.read.csv(csv_path, header=True, inferSchema=True)
    raw_count = df.count()
    logger.info("Raw payments count: %d", raw_count)

    # --- Filter invalid payment values ---
    df = df.filter(F.col("payment_value") > 0)
    filtered_count = df.count()
    logger.info(
        "After filtering payment_value <= 0: %d rows (removed %d)",
        filtered_count,
        raw_count - filtered_count,
    )

    # --- Primary payment type: type with highest total value per order ---
    type_value = df.groupBy("order_id", "payment_type").agg(
        F.sum("payment_value").alias("type_total")
    )
    # Rank payment types by value descending, pick top
    w = Window.partitionBy("order_id").orderBy(F.desc("type_total"))
    type_ranked = type_value.withColumn("_rn", F.row_number().over(w))
    primary_type = (
        type_ranked.filter(F.col("_rn") == 1)
        .select("order_id", F.col("payment_type").alias("primary_payment_type"))
    )

    # --- Aggregate per order ---
    agg = df.groupBy("order_id").agg(
        F.round(F.sum("payment_value"), 2).alias("total_payment"),
        F.max("payment_installments").alias("num_installments"),
    )

    # --- Join primary payment type ---
    result = agg.join(primary_type, on="order_id", how="left")

    logger.info("Aggregated payments: %d orders", result.count())

    # --- Write ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.write.mode("overwrite").parquet(str(output_path))
    logger.info("Payments silver written to: %s", output_path)

    return result


if __name__ == "__main__":
    df = transform_payments()
    df.printSchema()
    print(f"Silver payments row count: {df.count()}")
