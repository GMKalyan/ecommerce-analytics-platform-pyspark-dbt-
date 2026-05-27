"""
spark_products.py — Bronze → Silver transformation for products.

Transformations:
  - Lowercase + trim product_category_name
  - Fill null name/description/photos length with 0
  - Add product_volume_cm3 = length * height * width
  - Deduplicate on product_id
  - Write to data/silver/products.parquet
"""

import logging
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F

from src.config import BRONZE_PATH, SILVER_PRODUCTS
from src.ingestion.download import get_latest_bronze_folder
from src.transformation.spark_session import get_spark_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def transform_products(
    spark: SparkSession | None = None,
    bronze_folder: Path | None = None,
    output_path: Path = SILVER_PRODUCTS,
) -> DataFrame:
    if spark is None:
        spark = get_spark_session()

    if bronze_folder is None:
        bronze_folder = get_latest_bronze_folder(BRONZE_PATH)

    csv_path = str(bronze_folder / "olist_products_dataset.csv")
    logger.info("Reading products from: %s", csv_path)

    df = spark.read.csv(csv_path, header=True, inferSchema=True)
    logger.info("Raw products count: %d", df.count())

    # --- Clean category name ---
    df = df.withColumn(
        "product_category_name",
        F.lower(F.trim(F.col("product_category_name"))),
    )

    # --- Handle nulls in length/qty columns ---
    # Original dataset has typos: "lenght" instead of "length"
    null_fill_cols = [
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
    ]
    fill_map = {col: 0 for col in null_fill_cols if col in df.columns}
    df = df.fillna(fill_map)

    # --- Add volume ---
    dim_cols = ["product_length_cm", "product_height_cm", "product_width_cm"]
    all_present = all(c in df.columns for c in dim_cols)
    if all_present:
        df = df.withColumn(
            "product_volume_cm3",
            F.col("product_length_cm") * F.col("product_height_cm") * F.col("product_width_cm"),
        )
    else:
        logger.warning("Dimension columns missing; skipping product_volume_cm3.")

    # --- Deduplicate on product_id ---
    from pyspark.sql.window import Window
    window = Window.partitionBy("product_id").orderBy(F.lit(1))
    df = df.withColumn("_rn", F.row_number().over(window))
    df = df.filter(F.col("_rn") == 1).drop("_rn")
    logger.info("After dedup: %d rows", df.count())

    # --- Write ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write.mode("overwrite").parquet(str(output_path))
    logger.info("Products silver written to: %s", output_path)

    return df


if __name__ == "__main__":
    df = transform_products()
    df.printSchema()
    print(f"Silver products row count: {df.count()}")
