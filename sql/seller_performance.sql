-- =============================================================================
-- seller_performance.sql
-- Comprehensive seller performance scorecard.
--
-- Metrics computed:
--   - Revenue and order volume
--   - Average review score
--   - On-time delivery rate
--   - Seller reliability score (weighted composite)
--   - Rankings via RANK() and DENSE_RANK()
--   - Geographic analysis by state
--
-- Note: This query uses fact_orders (order-level grain).
-- For per-item seller revenue, STG_ORDER_ITEMS is required.
-- Run against: ecommerce_db.gold.fact_orders + dim_customers + dim_sellers
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 1: Build seller-level metrics from fact_orders
--
-- Since fact_orders does not carry seller_id directly (seller is at item grain),
-- we approximate by joining through a customer → seller bridge in the source.
-- Here we use STG_ORDERS joined to the raw order_items in the source schema.
-- Adjust the join path based on your warehouse structure.
-- ─────────────────────────────────────────────────────────────────────────────
with seller_orders as (
    -- Join raw order_items to get seller_id per order
    -- (STG_ORDER_ITEMS needed for exact item-level attribution)
    -- This CTE uses the Snowflake source tables directly
    select
        oi.seller_id,
        oi.order_id,
        oi.price,
        oi.freight_value
    from ecommerce_db.public.stg_order_items  oi   -- placeholder; update to gold ref when available
),

seller_metrics as (
    select
        s.seller_id,
        s.seller_city,
        s.seller_state,
        s.seller_region,

        count(distinct so.order_id)                             as total_orders,
        round(sum(so.price), 2)                                 as total_revenue,
        round(avg(so.price), 2)                                 as avg_item_price,
        round(sum(so.freight_value), 2)                         as total_freight,

        -- Review metrics joined via orders
        round(avg(o.review_score), 2)                           as avg_review_score,
        count(case when o.review_score is not null then 1 end)  as review_count,

        -- Delivery performance
        round(avg(o.delivery_days), 1)                          as avg_delivery_days,
        sum(case when o.is_late then 1 else 0 end)              as late_orders,
        round(
            100.0 - (sum(case when o.is_late then 1 else 0 end) * 100.0
            / nullif(count(distinct so.order_id), 0)),
            2
        )                                                       as on_time_rate_pct

    from ecommerce_db.gold.dim_sellers          s
    join seller_orders                          so on s.seller_id    = so.seller_id
    join ecommerce_db.gold.fact_orders          o  on so.order_id    = o.order_id
    where o.order_status not in ('canceled', 'unavailable')
    group by s.seller_id, s.seller_city, s.seller_state, s.seller_region
),

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 2: Compute seller reliability score
--
-- Weighted formula:
--   reliability = (avg_review_score/5 * 40%)
--               + (on_time_rate_pct/100 * 40%)
--               + (log(total_orders+1)/log(max_orders+1) * 20%)
--
-- Scores all normalize to 0-100 range.
-- ─────────────────────────────────────────────────────────────────────────────
with_scores as (
    select
        *,
        round(
            (coalesce(avg_review_score, 0) / 5.0 * 40)
            + (coalesce(on_time_rate_pct, 0) / 100.0 * 40)
            + (
                ln(total_orders + 1)
                / nullif(ln(max(total_orders + 1) over()), 0)
                * 20
              ),
            2
        )                                               as reliability_score
    from seller_metrics
),

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 3: Rankings
-- ─────────────────────────────────────────────────────────────────────────────
ranked as (
    select
        *,
        rank()       over (order by total_revenue desc)         as revenue_rank,
        rank()       over (order by total_orders  desc)         as volume_rank,
        dense_rank() over (order by avg_review_score desc)      as review_rank,
        rank()       over (order by on_time_rate_pct desc)      as ontime_rank,
        rank()       over (order by reliability_score desc)     as reliability_rank
    from with_scores
),

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 4: State-level geographic summary
-- ─────────────────────────────────────────────────────────────────────────────
state_summary as (
    select
        seller_state,
        seller_region,
        count(distinct seller_id)                       as seller_count,
        round(avg(avg_review_score), 2)                 as state_avg_review,
        round(avg(on_time_rate_pct), 2)                 as state_ontime_pct,
        round(sum(total_revenue), 2)                    as state_total_revenue,
        rank() over (order by avg(avg_review_score) desc) as state_review_rank
    from with_scores
    group by seller_state, seller_region
)

-- ─────────────────────────────────────────────────────────────────────────────
-- FINAL OUTPUT 1: Full seller scorecard
-- ─────────────────────────────────────────────────────────────────────────────
select
    seller_id,
    seller_city,
    seller_state,
    seller_region,
    total_orders,
    total_revenue,
    avg_item_price,
    avg_review_score,
    review_count,
    avg_delivery_days,
    late_orders,
    on_time_rate_pct,
    reliability_score,
    revenue_rank,
    volume_rank,
    review_rank,
    ontime_rank,
    reliability_rank
from ranked
order by reliability_rank;


-- ─────────────────────────────────────────────────────────────────────────────
-- Run separately: Bottom 10 sellers by reliability
-- ─────────────────────────────────────────────────────────────────────────────
/*
select seller_id, seller_state, reliability_score, avg_review_score,
       on_time_rate_pct, total_orders
from ranked
order by reliability_score asc
limit 10;
*/

-- ─────────────────────────────────────────────────────────────────────────────
-- Run separately: State geographic analysis
-- ─────────────────────────────────────────────────────────────────────────────
/*
select * from state_summary order by state_avg_review desc;
*/
