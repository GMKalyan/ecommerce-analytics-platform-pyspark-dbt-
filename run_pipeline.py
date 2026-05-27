"""
run_pipeline.py - End-to-end pipeline runner (no Airflow required).

Steps:
  1. Ingest CSVs -> bronze layer
  2. Validate bronze data
  3. PySpark transformations -> silver parquets
  4. Load silver parquets -> Snowflake staging tables

Usage:
  python run_pipeline.py              # full pipeline
  python run_pipeline.py --skip-spark # use existing silver files
  python run_pipeline.py --skip-snow  # skip Snowflake load

dbt gold layer:
  cd dbt_project && dbt run && dbt test
"""

import sys
import time
import logging
import argparse

import src.config  # noqa: F401 - bootstraps JAVA_HOME / HADOOP_HOME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_pipeline")


def main(skip_spark: bool = False, skip_snow: bool = False) -> None:
    pipeline_start = time.time()

    logger.info("Step 1: Ingesting CSVs to Bronze layer")
    from src.ingestion.download import ingest_to_bronze
    bronze_folder = ingest_to_bronze()
    logger.info("Bronze folder: %s", bronze_folder)

    logger.info("Step 2: Validating Bronze data")
    from src.ingestion.validate import validate_bronze
    reports = validate_bronze(bronze_folder)
    failed_validation = [r for r in reports if not r.is_ok()]
    if failed_validation:
        logger.warning("%d validation issues (non-critical - continuing):", len(failed_validation))
        for r in failed_validation:
            logger.warning("  %s", r.summary())
    else:
        logger.info("All %d files passed validation.", len(reports))

    silver_counts: dict[str, int] = {}

    if skip_spark:
        logger.info("Step 3: Skipping PySpark (--skip-spark)")
        import pandas as pd
        from src.config import SILVER_PATH
        for name in ["orders", "products", "customers", "sellers", "payments", "reviews"]:
            p = SILVER_PATH / f"{name}.parquet"
            if p.exists():
                silver_counts[name] = len(pd.read_parquet(p))
    else:
        logger.info("Step 3: Running PySpark Silver transformations")
        from src.transformation.spark_session import get_spark_session
        from src.transformation.spark_orders import transform_orders
        from src.transformation.spark_products import transform_products
        from src.transformation.spark_customers import transform_customers
        from src.transformation.spark_sellers import transform_sellers
        from src.transformation.spark_payments import transform_payments
        from src.transformation.spark_reviews import transform_reviews

        spark = get_spark_session()
        try:
            transforms = [
                ("orders",    transform_orders),
                ("products",  transform_products),
                ("customers", transform_customers),
                ("sellers",   transform_sellers),
                ("payments",  transform_payments),
                ("reviews",   transform_reviews),
            ]
            for name, fn in transforms:
                t0 = time.time()
                df = fn(spark=spark, bronze_folder=bronze_folder)
                silver_counts[name] = df.count()
                logger.info("  %s -> %s rows (%.1fs)", name, f"{silver_counts[name]:,}", time.time() - t0)
        finally:
            spark.stop()

    snowflake_results: dict[str, int] = {}

    if skip_snow:
        logger.info("Step 4: Skipping Snowflake load (--skip-snow)")
    else:
        logger.info("Step 4: Loading Silver tables to Snowflake")
        try:
            from src.loading.snowflake_loader import load_all_silver_tables
            snowflake_results = load_all_silver_tables()
        except Exception as exc:
            logger.error("Snowflake load failed: %s - %s", type(exc).__name__, exc)

    elapsed = time.time() - pipeline_start
    logger.info("Pipeline done in %.1fs", elapsed)

    import pandas as pd
    bronze_file_map = {
        "orders":    "olist_orders_dataset.csv",
        "products":  "olist_products_dataset.csv",
        "customers": "olist_customers_dataset.csv",
        "sellers":   "olist_sellers_dataset.csv",
        "payments":  "olist_order_payments_dataset.csv",
        "reviews":   "olist_order_reviews_dataset.csv",
    }

    print()
    print(f"{'Table':<15} {'Bronze':>12} {'Silver':>12} {'Snowflake':>12}")
    print("-" * 55)
    for name, fname in bronze_file_map.items():
        csv_path = bronze_folder / fname
        try:
            bronze_count = len(pd.read_csv(csv_path, low_memory=False))
        except Exception:
            bronze_count = -1

        silver_count = silver_counts.get(name, -1)
        sf_count = snowflake_results.get(f"STG_{name.upper()}", None)
        sf_str = f"{sf_count:,}" if isinstance(sf_count, int) and sf_count >= 0 else ("skipped" if sf_count is None else "FAILED")

        print(f"{name:<15} {bronze_count:>12,} {silver_count:>12,} {sf_str:>12}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E-Commerce Analytics Pipeline")
    parser.add_argument("--skip-spark", action="store_true", help="Skip PySpark transforms")
    parser.add_argument("--skip-snow",  action="store_true", help="Skip Snowflake loading")
    args = parser.parse_args()
    main(skip_spark=args.skip_spark, skip_snow=args.skip_snow)
