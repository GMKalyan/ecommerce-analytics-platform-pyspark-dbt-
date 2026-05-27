"""snowflake_loader.py - Load Silver Parquet files into Snowflake staging tables."""

import logging
from pathlib import Path

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

from src.config import SNOWFLAKE_CONFIG, SILVER_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Map pandas/numpy dtypes → Snowflake column types
DTYPE_MAP = {
    "int64": "NUMBER(38,0)",
    "int32": "NUMBER(38,0)",
    "float64": "FLOAT",
    "float32": "FLOAT",
    "bool": "BOOLEAN",
    "object": "VARCHAR(16777216)",
    "datetime64[ns]": "TIMESTAMP_NTZ",
    "datetime64[us]": "TIMESTAMP_NTZ",
}


def _pandas_dtype_to_snowflake(dtype_str: str) -> str:
    """Convert a pandas dtype string to a Snowflake SQL type."""
    for key, sf_type in DTYPE_MAP.items():
        if dtype_str.startswith(key):
            return sf_type
    return "VARCHAR(16777216)"


def _get_connection(config: dict) -> snowflake.connector.SnowflakeConnection:
    """Open and return a Snowflake connection. Raises on failure with full detail."""
    try:
        conn = snowflake.connector.connect(
            account=config["account"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            schema=config["schema"],
            warehouse=config["warehouse"],
        )
        logger.info(
            "Connected to Snowflake: %s / %s / %s",
            config["account"], config["database"], config["schema"],
        )
        return conn
    except Exception as exc:
        logger.error(
            "Snowflake connection FAILED — account=%s user=%s database=%s schema=%s\n"
            "Exception type: %s\nMessage: %s",
            config["account"], config["user"],
            config["database"], config["schema"],
            type(exc).__name__, exc,
        )
        raise


def _build_create_ddl(table_name: str, df: pd.DataFrame) -> str:
    """Generate CREATE TABLE IF NOT EXISTS DDL from a DataFrame."""
    cols = []
    for col, dtype in df.dtypes.items():
        sf_type = _pandas_dtype_to_snowflake(str(dtype))
        cols.append(f'    "{col.upper()}" {sf_type}')
    col_defs = ",\n".join(cols)
    return f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n{col_defs}\n);'


def load_parquet_to_snowflake(
    parquet_path: Path,
    table_name: str,
    config: dict | None = None,
    conn: snowflake.connector.SnowflakeConnection | None = None,
) -> int:
    """
    Load a parquet file into a Snowflake table via TRUNCATE + INSERT.

    Args:
        parquet_path: Path to the .parquet directory or file.
        table_name:   Target Snowflake table name (e.g. 'STG_ORDERS').
        config:       Snowflake config dict (uses SNOWFLAKE_CONFIG if omitted).
        conn:         Existing connection to reuse (avoids re-authenticating).

    Returns:
        Number of rows loaded.
    """
    if config is None:
        config = SNOWFLAKE_CONFIG

    own_conn = conn is None
    if own_conn:
        conn = _get_connection(config)

    try:
        # Read parquet — pandas handles multi-file parquet directories
        logger.info("Reading parquet: %s", parquet_path)
        df = pd.read_parquet(parquet_path)

        # Normalise column names → UPPER (Snowflake convention)
        df.columns = [c.upper() for c in df.columns]

        # Convert Timestamp columns to timezone-naive (Snowflake TIMESTAMP_NTZ)
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.tz_localize(None) if df[col].dt.tz is not None else df[col]

        # Convert boolean columns to int (Snowflake connector compatibility)
        for col in df.columns:
            if df[col].dtype == bool:
                df[col] = df[col].astype("Int64")

        row_count = len(df)
        schema = config["schema"]
        database = config["database"]

        cur = conn.cursor()
        try:
            # Ensure correct database/schema context
            cur.execute(f'USE DATABASE "{database}"')
            cur.execute(f'USE SCHEMA "{schema}"')

            # Create table if not exists
            ddl = _build_create_ddl(table_name, df)
            logger.debug("DDL:\n%s", ddl)
            cur.execute(ddl)

            # Truncate for full refresh
            cur.execute(f'TRUNCATE TABLE IF EXISTS "{table_name}"')
            logger.info("Truncated %s.%s", schema, table_name)

            # Bulk insert using write_pandas (uses Snowflake PUT + COPY)
            success, nchunks, nrows, output = write_pandas(
                conn=conn,
                df=df,
                table_name=table_name,
                database=database,
                schema=schema,
                auto_create_table=False,
                overwrite=False,
                quote_identifiers=False,
            )

            if not success:
                raise RuntimeError(f"write_pandas reported failure for {table_name}: {output}")

            logger.info(
                "Loaded %s rows into %s.%s (%s chunks)",
                f"{nrows:,}", schema, table_name, nchunks,
            )
            return nrows

        finally:
            cur.close()

    finally:
        if own_conn:
            conn.close()


# Silver parquet → Snowflake staging table mapping
SILVER_TABLE_MAP = {
    SILVER_PATH / "orders.parquet": "STG_ORDERS",
    SILVER_PATH / "products.parquet": "STG_PRODUCTS",
    SILVER_PATH / "customers.parquet": "STG_CUSTOMERS",
    SILVER_PATH / "sellers.parquet": "STG_SELLERS",
    SILVER_PATH / "payments.parquet": "STG_PAYMENTS",
    SILVER_PATH / "reviews.parquet": "STG_REVIEWS",
}


def load_all_silver_tables(config: dict | None = None) -> dict[str, int]:
    """
    Load all Silver parquet files into Snowflake staging tables.

    Opens a single connection and reuses it for all tables.
    Returns a dict of {table_name: rows_loaded}.
    """
    if config is None:
        config = SNOWFLAKE_CONFIG

    logger.info("Loading all Silver tables to Snowflake - target: %s / %s",
                config["database"], config["schema"])

    conn = _get_connection(config)
    results: dict[str, int] = {}

    try:
        for parquet_path, table_name in SILVER_TABLE_MAP.items():
            if not parquet_path.exists():
                logger.warning(
                    "Silver file not found, skipping %s: %s", table_name, parquet_path
                )
                continue
            try:
                n = load_parquet_to_snowflake(parquet_path, table_name, config, conn)
                results[table_name] = n
            except Exception as exc:
                logger.error(
                    "Failed to load %s: %s — %s", table_name, type(exc).__name__, exc
                )
                results[table_name] = -1
    finally:
        conn.close()

    # Summary
    logger.info("Snowflake load complete")
    for tbl, n in results.items():
        status = f"{n:,} rows" if n >= 0 else "FAILED"
        logger.info("  %-20s %s", tbl, status)

    return results


if __name__ == "__main__":
    load_all_silver_tables()
