-- =============================================================================
-- cohort_analysis.sql
-- Monthly cohort retention analysis.
--
-- Methodology:
--   1. COHORT DEFINITION: A customer's cohort is determined by the month of
--      their FIRST purchase (using customer_unique_id to identify the person).
--
--   2. COHORT INDEX: For each subsequent order by that customer, we measure
--      how many months elapsed since their first purchase (index 0 = cohort month).
--
--   3. RETENTION RATE: The % of customers who placed at least one order in
--      cohort_month + N months.
--
--   4. OUTPUT: A retention matrix where rows = cohort months, columns = month indices.
--      The diagonal represents the original cohort size (100% at index 0).
--
-- Run against: ecommerce_db.gold.fact_orders + dim_customers
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 1: Get each unique customer's first purchase date (cohort assignment)
-- ─────────────────────────────────────────────────────────────────────────────
with customer_first_purchase as (
    select
        c.customer_unique_id,
        date_trunc('month', min(o.purchased_at))        as cohort_month
    from ecommerce_db.gold.fact_orders      o
    join ecommerce_db.gold.dim_customers    c on o.customer_key = c.customer_key
    where o.order_status not in ('canceled', 'unavailable')
      and o.purchased_at is not null
    group by c.customer_unique_id
),

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 2: For each customer × order, compute the cohort month index
--   index 0 = cohort month (first purchase)
--   index 1 = 1 month after cohort month
--   etc.
-- ─────────────────────────────────────────────────────────────────────────────
customer_activity as (
    select
        c.customer_unique_id,
        fp.cohort_month,
        date_trunc('month', o.purchased_at)             as order_month,

        -- Month index: 0 = same month as first purchase
        datediff(
            'month',
            fp.cohort_month,
            date_trunc('month', o.purchased_at)
        )                                               as cohort_index

    from ecommerce_db.gold.fact_orders      o
    join ecommerce_db.gold.dim_customers    c  on o.customer_key  = c.customer_key
    join customer_first_purchase            fp on c.customer_unique_id = fp.customer_unique_id
    where o.order_status not in ('canceled', 'unavailable')
      and o.purchased_at is not null
),

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 3: Count distinct active customers per cohort × month index
-- ─────────────────────────────────────────────────────────────────────────────
cohort_counts as (
    select
        cohort_month,
        cohort_index,
        count(distinct customer_unique_id)              as active_customers
    from customer_activity
    group by cohort_month, cohort_index
),

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 4: Cohort sizes (customers at index 0 = starting cohort size)
-- ─────────────────────────────────────────────────────────────────────────────
cohort_sizes as (
    select
        cohort_month,
        active_customers                                as cohort_size
    from cohort_counts
    where cohort_index = 0
),

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 5: Compute retention rate for each cohort × month index
-- ─────────────────────────────────────────────────────────────────────────────
retention as (
    select
        cc.cohort_month,
        to_char(cc.cohort_month, 'YYYY-MM')             as cohort_label,
        cc.cohort_index,
        cs.cohort_size,
        cc.active_customers,
        round(
            cc.active_customers * 100.0 / cs.cohort_size,
            2
        )                                               as retention_rate_pct
    from cohort_counts       cc
    join cohort_sizes        cs on cc.cohort_month = cs.cohort_month
)

-- ─────────────────────────────────────────────────────────────────────────────
-- FINAL OUTPUT: Long-format retention table (easy to pivot in BI tools)
-- ─────────────────────────────────────────────────────────────────────────────
select
    cohort_label,
    cohort_size,
    cohort_index            as months_since_first_order,
    active_customers,
    retention_rate_pct
from retention
where cohort_index <= 12    -- show first year of retention
order by cohort_month, cohort_index;


-- ─────────────────────────────────────────────────────────────────────────────
-- Pivoted retention matrix (Snowflake PIVOT syntax)
-- Shows first 7 months (0–6); adjust as needed.
-- ─────────────────────────────────────────────────────────────────────────────
/*
select *
from (
    select cohort_label, cohort_index, retention_rate_pct
    from retention
    where cohort_index <= 6
)
pivot (
    max(retention_rate_pct)
    for cohort_index in (0, 1, 2, 3, 4, 5, 6)
) as pvt (
    cohort_label,
    "Month 0", "Month 1", "Month 2", "Month 3",
    "Month 4", "Month 5", "Month 6"
)
order by cohort_label;
*/
