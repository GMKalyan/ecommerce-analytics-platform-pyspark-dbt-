# dbt Project — Brazilian E-Commerce Analytics

## Overview

This dbt project transforms Snowflake staging tables (loaded from PySpark Silver layer)
into a star-schema Gold layer ready for BI and analytics.

## Architecture

```
Snowflake Staging (STG_*)
        │
        ▼
  staging/ models  ← light rename + cast
        │
        ▼
  intermediate/    ← multi-table joins
        │
        ▼
    gold/ models   ← fact + dimension tables
```

## Models

### Staging (views)
| Model | Source | Description |
|---|---|---|
| stg_orders | STG_ORDERS | Orders with delivery metrics |
| stg_customers | STG_CUSTOMERS | Customer records |
| stg_products | STG_PRODUCTS | Product attributes |
| stg_sellers | STG_SELLERS | Seller records |
| stg_payments | STG_PAYMENTS | Per-order payment aggregates |
| stg_reviews | STG_REVIEWS | Latest review per order |

### Intermediate (views)
| Model | Description |
|---|---|
| int_orders_enriched | Orders + payments + reviews — one row per order |
| int_order_items_enriched | Items + products + sellers (requires STG_ORDER_ITEMS) |

### Gold (tables — star schema)
| Model | Grain | Description |
|---|---|---|
| fact_orders | order_id | Central fact table |
| dim_customers | customer_id | Customer with region mapping |
| dim_sellers | seller_id | Seller with region mapping |
| dim_products | product_id | Product attributes |
| dim_dates | calendar day | Date spine 2016–2018 |
| dim_payment | payment_type + installments | Payment method dimension |

## Setup

```bash
# 1. Install dbt
pip install dbt-snowflake

# 2. Set environment variables (or fill .env)
export SNOWFLAKE_ACCOUNT=...
export SNOWFLAKE_USER=...
export SNOWFLAKE_PASSWORD=...
export SNOWFLAKE_DATABASE=ECOMMERCE_DB
export SNOWFLAKE_SCHEMA=PUBLIC
export SNOWFLAKE_WAREHOUSE=COMPUTE_WH

# 3. Point profiles.yml to this directory
export DBT_PROFILES_DIR=$(pwd)

# 4. Install packages
dbt deps

# 5. Test connection
dbt debug

# 6. Run all models
dbt run

# 7. Test all models
dbt test

# 8. Generate docs
dbt docs generate && dbt docs serve
```

## Running specific layers

```bash
dbt run --select staging        # staging views only
dbt run --select intermediate   # intermediate views
dbt run --select gold           # gold tables (requires staging + intermediate)
dbt run --select fact_orders    # single model
```
