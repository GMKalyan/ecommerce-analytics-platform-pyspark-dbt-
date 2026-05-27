"""
spark_sellers.py — Bronze → Silver transformation for sellers.

Transformations:
  - Lowercase + strip whitespace from seller_city
  - Deduplicate on seller_id
  - Write to data/silver/sellers.parquet
"""

import logging
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from src.config import BRONZE_PATH, SILVER_SELLERS
from src.ingestion.download import get_latest_bronze_folder
from src.transformation.spark_session import get_spark_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def transform_sellers(
    spark: SparkSession | None = None,
    bronze_folder: Path | None = None,
    output_path: Path = SILVER_SELLERS,
) -> DataFrame:
    if spark is None:
        spark = get_spark_session()

    if bronze_folder is None:
        bronze_folder = get_latest_bronze_folder(BRONZE_PATH)

    csv_path = str(bronze_folder / "olist_sellers_dataset.csv")
    logger.info("Reading sellers from: %s", csv_path)

    df = spark.read.csv(csv_path, header=True, inferSchema=True)
    logger.info("Raw sellers count: %d", df.count())

    # --- Clean city name ---
    df = df.withColumn(
        "seller_city",
        F.lower(F.trim(F.col("seller_city"))),
    )

    # --- Deduplicate on seller_id ---
    window = Window.partitionBy("seller_id").orderBy(F.lit(1))
    df = df.withColumn("_rn", F.row_number().over(window))
    df = df.filter(F.col("_rn") == 1).drop("_rn")
    logger.info("After dedup: %d rows", df.count())

    # --- Write ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write.mode("overwrite").parquet(str(output_path))
    logger.info("Sellers silver written to: %s", output_path)

    return df


if __name__ == "__main__":
    df = transform_sellers()
    df.printSchema()
    print(f"Silver sellers row count: {df.count()}")
