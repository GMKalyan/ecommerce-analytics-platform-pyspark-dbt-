"""
spark_session.py — Reusable SparkSession factory.
"""

import logging
from pyspark.sql import SparkSession
from src.config import SPARK_APP_NAME, SPARK_DRIVER_MEMORY, SPARK_EXECUTOR_MEMORY, SPARK_MASTER

logger = logging.getLogger(__name__)


def get_spark_session(
    app_name: str = SPARK_APP_NAME,
    master: str = SPARK_MASTER,
    driver_memory: str = SPARK_DRIVER_MEMORY,
    executor_memory: str = SPARK_EXECUTOR_MEMORY,
) -> SparkSession:
    """
    Create (or retrieve existing) SparkSession configured for local mode.

    Args:
        app_name: Spark application name shown in UI.
        master: Spark master URL. Default local[*] uses all CPU cores.
        driver_memory: JVM heap for the driver process.
        executor_memory: JVM heap per executor.

    Returns:
        Active SparkSession.
    """
    spark = (
        SparkSession.builder
        .appName(app_name)
        .master(master)
        .config("spark.driver.memory", driver_memory)
        .config("spark.executor.memory", executor_memory)
        .config("spark.sql.shuffle.partitions", "8")        # reasonable for local
        .config("spark.ui.showConsoleProgress", "false")    # reduce console noise
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")  # lenient date parsing
        .config("spark.sql.ansi.enabled", "false")              # tolerate bad casts → null
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    logger.info("SparkSession ready — app: %s, master: %s", app_name, master)
    return spark
