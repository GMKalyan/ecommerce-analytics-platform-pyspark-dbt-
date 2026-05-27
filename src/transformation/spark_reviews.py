"""
spark_reviews.py — Bronze → Silver transformation for reviews.

Transformations:
  - Cast review_creation_date and review_answer_timestamp to TimestampType
  - Fill null comment title/message with empty string
  - Deduplicate on review_id
  - For orders with multiple reviews, keep the latest (by review_answer_timestamp)
  - Write to data/silver/reviews.parquet
"""

import logging
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from src.config import BRONZE_PATH, SILVER_REVIEWS
from src.ingestion.download import get_latest_bronze_folder
from src.transformation.spark_session import get_spark_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def transform_reviews(
    spark: SparkSession | None = None,
    bronze_folder: Path | None = None,
    output_path: Path = SILVER_REVIEWS,
) -> DataFrame:
    if spark is None:
        spark = get_spark_session()

    if bronze_folder is None:
        bronze_folder = get_latest_bronze_folder(BRONZE_PATH)

    csv_path = str(bronze_folder / "olist_order_reviews_dataset.csv")
    logger.info("Reading reviews from: %s", csv_path)

    # multiLine=True handles embedded newlines in comment fields (common in this dataset)
    df = spark.read.option("multiLine", "true").option("escape", '"').csv(
        csv_path, header=True, inferSchema=False
    )
    logger.info("Raw reviews count: %d", df.count())

    # --- Cast timestamps (use try_cast so malformed values become null, not errors) ---
    df = df.withColumn(
        "review_creation_date",
        F.expr("try_cast(review_creation_date AS TIMESTAMP)"),
    )
    df = df.withColumn(
        "review_answer_timestamp",
        F.expr("try_cast(review_answer_timestamp AS TIMESTAMP)"),
    )

    # --- Cast review_score to int ---
    df = df.withColumn("review_score", F.col("review_score").cast("int"))

    # --- Fill null comment fields ---
    df = df.fillna({
        "review_comment_title": "",
        "review_comment_message": "",
    })

    # --- Deduplicate on review_id (keep latest by answer timestamp) ---
    w_rid = Window.partitionBy("review_id").orderBy(F.desc("review_answer_timestamp"))
    df = df.withColumn("_rn", F.row_number().over(w_rid))
    df = df.filter(F.col("_rn") == 1).drop("_rn")
    logger.info("After review_id dedup: %d rows", df.count())

    # --- For orders with multiple reviews, keep the latest ---
    w_oid = Window.partitionBy("order_id").orderBy(F.desc("review_answer_timestamp"))
    df = df.withColumn("_rn", F.row_number().over(w_oid))
    df = df.filter(F.col("_rn") == 1).drop("_rn")
    logger.info("After order_id dedup (latest review per order): %d rows", df.count())

    # --- Write ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write.mode("overwrite").parquet(str(output_path))
    logger.info("Reviews silver written to: %s", output_path)

    return df


if __name__ == "__main__":
    df = transform_reviews()
    df.printSchema()
    print(f"Silver reviews row count: {df.count()}")
