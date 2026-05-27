-- =============================================================================
-- revenue_trends.sql
-- Monthly and quarterly GMV analysis with growth rates and category breakdown.
-- Designed for Snowflake Gold layer (fact_orders + dim_customers + dim_products).
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- SECTION 1: Monthly GMV, AOV, and MoM Growth
-- ─────────────────────────────────────────────────────────────────────────────
with monthly_base as (
    -- Aggregate key metrics at monthly grain
    select
        o.order_year,
        o.order_month,
        to_char(o.purchased_at, 'YYYY-MM')              as year_month,
        date_trunc('month', o.purchased_at)             as period_start,

        count(distinct o.order_id)                      as order_count,
        count(distinct o.customer_id)                   as unique_customers,
        sum(o.payment_amount)                           as gmv,
        avg(o.payment_amount)                           as avg_order_value,
        avg(o.review_score)                             as avg_review_score,
        sum(case when o.is_late then 1 else 0 end)
            / nullif(count(*), 0) * 100                 as late_delivery_pct

    from ecommerce_db.gold.fact_orders o
    where o.order_status not in ('canceled', 'unavailable')
      and o.purchased_at is not null
    group by 1, 2, 3, 4
),

with_growth as (
    -- Add month-over-month growth using LAG
    select
        year_month,
        order_year,
        order_month,
        order_count,
        unique_customers,
        round(gmv, 2)                                   as gmv,
        round(avg_order_value, 2)                       as avg_order_value,
        round(avg_review_score, 2)                      as avg_review_score,
        round(late_delivery_pct, 1)                     as late_delivery_pct,

        lag(gmv)          over (order by period_start)  as prev_month_gmv,
        lag(order_count)  over (order by period_start)  as prev_month_orders,

        round(
            (gmv - lag(gmv) over (order by period_start))
            / nullif(lag(gmv) over (order by period_start), 0) * 100,
            2
        )                                               as mom_gmv_growth_pct,

        -- 3-month rolling average GMV
        round(
            avg(gmv) over (
                order by period_start
                rows between 2 preceding and current row
            ), 2
        )                                               as rolling_3m_avg_gmv

    from monthly_base
),

-- ─────────────────────────────────────────────────────────────────────────────
-- SECTION 2: Quarterly GMV
-- ─────────────────────────────────────────────────────────────────────────────
quarterly as (
    select
        order_year,
        extract(quarter from purchased_at)::integer     as quarter,
        order_year::varchar || '-Q'
            || extract(quarter from purchased_at)::varchar as year_quarter,
        count(distinct order_id)                        as order_count,
        round(sum(payment_amount), 2)                   as quarterly_gmv,
        round(avg(payment_amount), 2)                   as avg_order_value
    from ecommerce_db.gold.fact_orders
    where order_status not in ('canceled', 'unavailable')
    group by 1, 2, 3
),

-- ─────────────────────────────────────────────────────────────────────────────
-- SECTION 3: Revenue by State
-- ─────────────────────────────────────────────────────────────────────────────
by_state as (
    select
        c.customer_state,
        c.customer_region,
        count(distinct o.order_id)                      as order_count,
        round(sum(o.payment_amount), 2)                 as total_gmv,
        round(avg(o.payment_amount), 2)                 as avg_order_value,
        round(
            sum(o.payment_amount) * 100.0
            / sum(sum(o.payment_amount)) over (), 2
        )                                               as gmv_share_pct
    from ecommerce_db.gold.fact_orders      o
    join ecommerce_db.gold.dim_customers    c on o.customer_key = c.customer_key
    where o.order_status not in ('canceled', 'unavailable')
    group by 1, 2
),

-- ─────────────────────────────────────────────────────────────────────────────
-- SECTION 4: Top 10 Product Categories by Revenue
-- (requires STG_ORDER_ITEMS to be loaded — approximated via dim_products join)
-- ─────────────────────────────────────────────────────────────────────────────
-- Note: fact_orders is at order grain, not item grain.
-- Category breakdown here is a placeholder — full breakdown needs fact_order_items.
monthly_final as (
    select * from with_growth
)

-- ─────────────────────────────────────────────────────────────────────────────
-- FINAL OUTPUT: Monthly trend
-- ─────────────────────────────────────────────────────────────────────────────
select
    year_month,
    order_count,
    unique_customers,
    gmv,
    avg_order_value,
    mom_gmv_growth_pct,
    rolling_3m_avg_gmv,
    avg_review_score,
    late_delivery_pct
from monthly_final
order by year_month;


-- ─────────────────────────────────────────────────────────────────────────────
-- Run separately: Quarterly breakdown
-- ─────────────────────────────────────────────────────────────────────────────
/*
select * from quarterly order by order_year, quarter;
*/

-- ─────────────────────────────────────────────────────────────────────────────
-- Run separately: Revenue by state (top 10)
-- ─────────────────────────────────────────────────────────────────────────────
/*
select *
from by_state
order by total_gmv desc
limit 10;
*/
