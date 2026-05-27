# Brazilian E-Commerce Analytics Platform

> End-to-end analytics platform on the Olist Brazilian E-Commerce dataset (~100K orders, 2016-2018).
> Full Medallion Architecture: PySpark Silver layer, Snowflake + dbt Gold star schema, Airflow orchestration, scikit-learn ML models, and a Streamlit dashboard.

---

## Architecture

```
Raw CSVs (archive/ — 9 Olist tables)
        |
        | Python ingestion + schema validation
        v
BRONZE  data/bronze/{YYYY-MM-DD}/          — raw CSV copies
        |
        | PySpark transforms (6 jobs)
        v
SILVER  data/silver/*.parquet              — typed, deduped, enriched
        |
        +——————————————————————————+
        |                          |
        | Snowflake connector       | scikit-learn ML
        v                          v
GOLD    Snowflake STG_*            data/gold/models/
        |                            delivery_model.joblib
        | dbt (14 models)            review_model.joblib
        v
        Snowflake Gold (star schema)
          fact_orders / dim_customers / dim_sellers
          dim_products / dim_dates / dim_payment
        |
        | Streamlit
        v
DASHBOARD  streamlit_app/  — 5 pages (Overview, Geographic, Customers, Sellers, Predictions)
```

Orchestrated end-to-end by **Apache Airflow** (docker-compose), with 5 TaskGroups:
`ingestion → transformation → loading → modeling (dbt) → ml`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Big Data | PySpark 4.1 |
| Data Warehouse | Snowflake |
| SQL Modeling | dbt-snowflake 1.11 (14 models, star schema) |
| Orchestration | Apache Airflow 2.9 |
| ML | scikit-learn 1.6 (GradientBoosting) |
| Dashboard | Streamlit 1.45 + Plotly 6 |
| Testing | pytest (50 tests) |
| Infrastructure | Docker Compose |

---

## ML Models

Two models trained on the full Silver dataset (96K+ delivered orders):

| Model | Algorithm | Key Metric |
|---|---|---|
| Delivery Time Prediction | GradientBoostingRegressor | RMSE = 8.12 days, R² = 0.28 |
| Review Score Classification | GradientBoostingClassifier | F1 = 0.889, Accuracy = 81% |

**Delivery model features:** seller state, customer state, product weight/volume, freight value, price, payment type, order day/month, installments.

**Review model features:** delivery days, delay days, price, freight, product weight, photo count, installments, is_late flag.

---

## dbt Star Schema

```
fact_orders ──── dim_customers   (customer_id, state, region)
           |─── dim_sellers      (seller_id, state, region)
           |─── dim_products     (product_id, weight, volume, photos)
           |─── dim_dates        (date_key, year, month, quarter, day_of_week)
           └─── dim_payment      (payment_key, type, installments_bucket)
```

14 SQL models: 6 staging views → 2 intermediate views → 6 Gold tables.
Custom `dbt_utils.generate_surrogate_key` and `date_spine` macros.

---

## Dataset

[Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — ~100K orders, 2016-2018.

| Table | Bronze | Silver |
|---|---|---|
| orders | 99,441 | 98,827 |
| customers | 99,441 | 99,441 |
| products | 32,951 | 32,951 |
| sellers | 3,095 | 3,095 |
| payments | 103,886 | 99,437 |
| reviews | 99,224 | 98,167 |

---

## Project Structure

```
ecommerce-analytics/
├── src/
│   ├── config.py                    # Paths, env bootstrap (JAVA_HOME / Hadoop)
│   ├── ingestion/
│   │   ├── download.py              # Idempotent CSV → bronze copy
│   │   └── validate.py              # 6-check schema + quality validation
│   ├── transformation/
│   │   ├── spark_session.py         # SparkSession factory (Windows-compatible)
│   │   ├── spark_orders.py          # Timestamps, delivery_days, is_late
│   │   ├── spark_products.py        # Volume + category enrichment
│   │   ├── spark_customers.py       # State normalization
│   │   ├── spark_sellers.py         # Seller state
│   │   ├── spark_payments.py        # primary_payment_type, num_installments
│   │   └── spark_reviews.py         # multiLine CSV, dedup on review_id→order_id
│   ├── loading/
│   │   └── snowflake_loader.py      # TRUNCATE + write_pandas to STG_* tables
│   └── ml/
│       ├── train.py                 # Model selection (3 candidates each), joblib save
│       └── predict.py               # Lazy-loaded inference with graceful fallbacks
├── dbt_project/
│   ├── models/staging/              # 6 STG_* source views
│   ├── models/intermediate/         # int_orders_enriched, int_payments_agg
│   └── models/gold/                 # fact_orders + 5 dims
├── dags/
│   └── ecommerce_pipeline.py        # @daily Airflow DAG, 5 TaskGroups
├── streamlit_app/
│   ├── app.py                       # Entry point + landing page
│   ├── utils/
│   │   ├── data_loader.py           # @st.cache_data Silver parquet loaders
│   │   ├── charts.py                # Reusable Plotly chart builders
│   │   └── constants.py             # State names, region map, color palette
│   └── pages/
│       ├── 1_overview.py            # KPIs, order trends, revenue, payment mix
│       ├── 2_geographic.py          # State bars, region pie, delivery heatmap
│       ├── 3_customers.py           # RFM segmentation, review vs delivery scatter
│       ├── 4_sellers.py             # Leaderboard, performance scatter
│       └── 5_predictions.py         # Live ML predictor + model cards + feature importance
├── sql/
│   ├── rfm_segmentation.sql
│   ├── cohort_analysis.sql
│   ├── seller_performance.sql
│   └── revenue_trends.sql
├── tests/                           # 50 pytest tests (ingestion + transforms + quality)
├── run_pipeline.py                  # One-command pipeline runner (--skip-spark / --skip-snow)
├── docker-compose.yml               # Airflow + Postgres
├── requirements.txt
└── .env.example
```

---

## Setup

### Prerequisites

- Python 3.11+
- Java 11+ (for PySpark — Microsoft OpenJDK 21 tested on Windows)
- Windows: `winutils.exe` + `hadoop.dll` at `C:\winutils\bin\` (Hadoop 3.3.6)
- Snowflake account (optional — use `--skip-snow` to run without it)
- Docker Desktop (optional — for Airflow)

### Installation

```bash
cd ecommerce-analytics
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env with SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD
```

---

## Running

### Full Pipeline (Phases 1 + 2)

```bash
# Full pipeline: ingest → validate → PySpark → Snowflake
python run_pipeline.py

# Skip PySpark (Silver already exists)
python run_pipeline.py --skip-spark

# Skip Snowflake
python run_pipeline.py --skip-snow
```

### dbt (run after Snowflake load)

```bash
cd dbt_project
export DBT_PROFILES_DIR=$(pwd)
dbt deps
dbt run
dbt test
```

### ML Training (Phase 3)

```bash
python -m src.ml.train
# Saves to data/gold/models/
```

### Streamlit Dashboard

```bash
streamlit run streamlit_app/app.py
# Opens at http://localhost:8501
```

### Tests

```bash
pytest tests/ -v
# 50 tests: ingestion, transformations, data quality
```

### Airflow (Docker)

```bash
docker-compose up -d
# http://localhost:8080  (admin / admin)
# Enable + trigger: ecommerce_pipeline
```

---

## Key Engineering Decisions

| Decision | Rationale |
|---|---|
| LabelEncoder over OneHotEncoder for ML | Tree models handle ordinal codes; keeps dimensionality low for GBM |
| `SimpleImputer(median)` before models | Robustness to missing freight/weight values in production |
| Silver parquets as ML source (not Snowflake) | Avoids connector dependency for local ML training |
| `spark.sql.ansi.enabled=false` | Olist reviews CSV has embedded newlines causing column misalignment |
| `multiLine=True` + `try_cast()` for reviews | Handle malformed review text without dropping rows |
| PySpark tests use CSV files (not `createDataFrame`) | PySpark 4.1 + Python 3.13 workers crash with `createDataFrame` on Windows |
| `write_pandas` (PUT+COPY) for Snowflake load | Bulk load via internal staging; avoids row-by-row INSERT overhead |

---

## Resume Bullets

- Built end-to-end data lakehouse on 100K-row Brazilian e-commerce dataset using Medallion Architecture (Bronze/Silver/Gold) with PySpark, Snowflake, and dbt star schema (6 tables, 14 SQL models)
- Engineered 6 PySpark ETL jobs handling schema validation, timestamp parsing, deduplication, and feature derivation (delivery days, is_late, order cadence features)
- Trained delivery-time regression (RMSE = 8.1 days) and review-score classifier (F1 = 0.89) using scikit-learn GradientBoosting; models serve live predictions in Streamlit dashboard
- Designed Airflow DAG with 5 TaskGroups and 9 tasks, including 6 parallel PySpark transforms; deployed via docker-compose with PostgreSQL metadata store
- Built 5-page Streamlit dashboard (KPIs, geographic heatmaps, RFM segmentation, seller leaderboard, live ML predictor) with cached data loading and Plotly visualizations

---

## License

MIT
