from __future__ import annotations

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup


def _on_failure_callback(context: dict) -> None:
    task_id = context.get("task_instance").task_id
    dag_id  = context.get("dag").dag_id
    exc     = context.get("exception")
    log_url = context.get("task_instance").log_url
    logging.error(
        "[FAILURE] DAG=%s  TASK=%s\nException: %s\nLogs: %s",
        dag_id, task_id, exc, log_url,
    )


DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
    "email_on_retry": False,
    "on_failure_callback": _on_failure_callback,
}


def _download(**context) -> str:
    import src.config  # noqa: F401 — sets JAVA_HOME/HADOOP_HOME as side effect
    from src.ingestion.download import ingest_to_bronze
    folder = ingest_to_bronze()
    context["ti"].xcom_push(key="bronze_folder", value=str(folder))
    return str(folder)


def _validate(**context) -> None:
    import src.config  # noqa: F401 — sets JAVA_HOME/HADOOP_HOME as side effect
    from pathlib import Path
    from src.ingestion.validate import validate_bronze

    bronze_folder = context["ti"].xcom_pull(task_ids="ingestion.download_data", key="bronze_folder")
    reports = validate_bronze(Path(bronze_folder) if bronze_folder else None)

    critical = [r for r in reports if r.status == "CRITICAL"]
    if critical:
        raise RuntimeError(
            f"Validation CRITICAL failures: {[r.file_name for r in critical]}"
        )


def _make_spark_transform(transform_fn_path: str):
    def _transform(**context):
        import src.config  # noqa: F401 — sets JAVA_HOME/HADOOP_HOME as side effect
        import importlib
        from pathlib import Path

        bronze_folder_str = context["ti"].xcom_pull(
            task_ids="ingestion.download_data", key="bronze_folder"
        )
        bronze_folder = Path(bronze_folder_str) if bronze_folder_str else None

        module_path, fn_name = transform_fn_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        fn = getattr(module, fn_name)

        from src.transformation.spark_session import get_spark_session
        spark = get_spark_session()
        try:
            df = fn(spark=spark, bronze_folder=bronze_folder)
            count = df.count()
            logging.info("%s -> %s rows written to silver", fn_name, f"{count:,}")
        finally:
            spark.stop()

    return _transform


def _load_snowflake(**context) -> None:
    import src.config  # noqa: F401 — sets JAVA_HOME/HADOOP_HOME as side effect
    from src.loading.snowflake_loader import load_all_silver_tables
    results = load_all_silver_tables()
    failed = {k: v for k, v in results.items() if v < 0}
    if failed:
        raise RuntimeError(f"Snowflake load failed for tables: {list(failed.keys())}")
    logging.info("Snowflake load complete: %s", results)


def _train_models(**context) -> None:
    import src.config  # noqa: F401 — sets JAVA_HOME/HADOOP_HOME as side effect
    from src.ml.train import main as train_main
    train_main()


def _pipeline_complete(**context) -> None:
    dag_run = context["dag_run"]
    start   = dag_run.start_date
    elapsed = (datetime.utcnow() - start.replace(tzinfo=None)).total_seconds()
    logging.info(
        "Pipeline complete - DAG=%s  run_id=%s  elapsed=%.1fs",
        dag_run.dag_id, dag_run.run_id, elapsed,
    )


with DAG(
    dag_id="ecommerce_pipeline",
    description="Brazilian E-Commerce analytics: ingest -> transform -> load -> model -> ML",
    default_args=DEFAULT_ARGS,
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ecommerce", "analytics", "pyspark", "snowflake", "dbt"],
) as dag:

    with TaskGroup("ingestion") as tg_ingestion:
        download_data = PythonOperator(
            task_id="download_data",
            python_callable=_download,
        )
        validate_data = PythonOperator(
            task_id="validate_data",
            python_callable=_validate,
        )
        download_data >> validate_data

    with TaskGroup("transformation") as tg_transform:
        transform_orders = PythonOperator(
            task_id="transform_orders",
            python_callable=_make_spark_transform(
                "src.transformation.spark_orders.transform_orders"
            ),
        )
        transform_products = PythonOperator(
            task_id="transform_products",
            python_callable=_make_spark_transform(
                "src.transformation.spark_products.transform_products"
            ),
        )
        transform_customers = PythonOperator(
            task_id="transform_customers",
            python_callable=_make_spark_transform(
                "src.transformation.spark_customers.transform_customers"
            ),
        )
        transform_sellers = PythonOperator(
            task_id="transform_sellers",
            python_callable=_make_spark_transform(
                "src.transformation.spark_sellers.transform_sellers"
            ),
        )
        transform_payments = PythonOperator(
            task_id="transform_payments",
            python_callable=_make_spark_transform(
                "src.transformation.spark_payments.transform_payments"
            ),
        )
        transform_reviews = PythonOperator(
            task_id="transform_reviews",
            python_callable=_make_spark_transform(
                "src.transformation.spark_reviews.transform_reviews"
            ),
        )

    with TaskGroup("loading") as tg_loading:
        load_to_snowflake = PythonOperator(
            task_id="load_to_snowflake",
            python_callable=_load_snowflake,
        )

    with TaskGroup("modeling") as tg_modeling:
        dbt_run = BashOperator(
            task_id="dbt_run",
            bash_command=(
                "cd /opt/airflow/dbt_project && "
                "DBT_PROFILES_DIR=/opt/airflow/dbt_project "
                "dbt run --profiles-dir /opt/airflow/dbt_project"
            ),
        )
        dbt_test = BashOperator(
            task_id="dbt_test",
            bash_command=(
                "cd /opt/airflow/dbt_project && "
                "DBT_PROFILES_DIR=/opt/airflow/dbt_project "
                "dbt test --profiles-dir /opt/airflow/dbt_project"
            ),
        )
        dbt_run >> dbt_test

    with TaskGroup("ml") as tg_ml:
        train_models = PythonOperator(
            task_id="train_models",
            python_callable=_train_models,
        )

    pipeline_complete = PythonOperator(
        task_id="pipeline_complete",
        python_callable=_pipeline_complete,
    )

    tg_ingestion >> tg_transform >> tg_loading >> tg_modeling >> tg_ml >> pipeline_complete
