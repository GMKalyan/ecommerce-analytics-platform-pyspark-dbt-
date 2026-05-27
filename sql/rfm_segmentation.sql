-- =============================================================================
-- rfm_segmentation.sql
-- RFM (Recency · Frequency · Monetary) customer segmentation.
--
-- Methodology:
--   R = days since last purchase (lower = better customer, so scored inversely)
--   F = total number of distinct orders placed
--   M = total spend across all orders
--
-- Each dimension is scored 1–5 using NTILE(5) decile buckets.
-- Segment labels are assigned based on R/F/M score combinations.
--
-- Run against: ecommerce_db.gold.fact_orders + dim_customers
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 1: Compute RFM raw values per unique customer
-- Using customer_unique_id (the real person, not the per-order customer_id)
-- ─────────────────────────────────────────────────────────────────────────────
with customer_orders as (
    select
        c.customer_unique_id,
        o.order_id,
        o.purchased_at,
        o.payment_amount
    from ecommerce_db.gold.fact_orders      o
    join ecommerce_db.gold.dim_customers    c on o.customer_key = c.customer_key
    where o.order_status not in ('canceled', 'unavailable')
      and o.payment_amount > 0
      and o.purchased_at is not null
),

rfm_raw as (
    select
        customer_unique_id,

        -- Recency: days since last order (relative to max date in dataset = 2018-09-03)
        datediff(
            'day',
            max(purchased_at),
            (select max(purchased_at) from customer_orders)
        )                                               as recency_days,

        -- Frequency: distinct orders placed
        count(distinct order_id)                        as frequency,

        -- Monetary: total spend
        round(sum(payment_amount), 2)                   as monetary

    from customer_orders
    group by customer_unique_id
),

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 2: Score each dimension 1–5 with NTILE(5)
-- Note: R is scored ascending (lower recency = higher score → better customer)
-- ─────────────────────────────────────────────────────────────────────────────
rfm_scored as (
    select
        customer_unique_id,
        recency_days,
        frequency,
        monetary,

        -- Recency: ascending recency_days → score 5 = most recent
        ntile(5) over (order by recency_days desc)      as r_score,

        -- Frequency: more orders = higher score
        ntile(5) over (order by frequency asc)          as f_score,

        -- Monetary: more spend = higher score
        ntile(5) over (order by monetary asc)           as m_score

    from rfm_raw
),

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 3: Combine scores and assign segment labels
-- ─────────────────────────────────────────────────────────────────────────────
rfm_segmented as (
    select
        customer_unique_id,
        recency_days,
        frequency,
        monetary,
        r_score,
        f_score,
        m_score,
        r_score + f_score + m_score                         as rfm_total,
        r_score::varchar || f_score::varchar || m_score::varchar as rfm_cell,

        -- Segment assignment (priority order — first match wins)
        case
            -- Champions: high across all three
            when r_score >= 4 and f_score >= 4 and m_score >= 4
                then 'Champions'

            -- Loyal: frequent high-spenders (may not be super recent)
            when f_score >= 3 and m_score >= 3
                then 'Loyal Customers'

            -- Recent but not yet loyal — new potential customers
            when r_score >= 4 and f_score <= 2
                then 'Recent Customers'

            -- Show promise but need nurturing
            when r_score >= 3 and f_score >= 2 and m_score >= 2
                then 'Potential Loyalists'

            -- Were good customers but haven't bought recently
            when r_score <= 2 and f_score >= 3 and m_score >= 3
                then 'At Risk'

            -- High-value customers at serious churn risk
            when r_score <= 2 and f_score >= 4
                then 'Cannot Lose Them'

            -- Low recency, some activity — need re-engagement
            when r_score between 2 and 3 and f_score <= 2
                then 'Needs Attention'

            -- Haven't bought in a long time, low engagement
            when r_score <= 2 and f_score <= 2 and m_score <= 2
                then 'Lost'

            else 'Other'
        end                                                 as segment_name

    from rfm_scored
),

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 4: Segment summary statistics
-- ─────────────────────────────────────────────────────────────────────────────
segment_summary as (
    select
        segment_name,
        count(*)                                            as customer_count,
        round(avg(recency_days), 1)                         as avg_recency_days,
        round(avg(frequency), 2)                            as avg_frequency,
        round(avg(monetary), 2)                             as avg_monetary,
        round(sum(monetary), 2)                             as total_monetary,
        round(count(*) * 100.0 / sum(count(*)) over(), 2)  as pct_of_customers
    from rfm_segmented
    group by segment_name
)

-- ─────────────────────────────────────────────────────────────────────────────
-- FINAL OUTPUT: Full customer RFM table
-- ─────────────────────────────────────────────────────────────────────────────
select
    customer_unique_id,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    rfm_cell,
    rfm_total,
    segment_name
from rfm_segmented
order by rfm_total desc, monetary desc;


-- ─────────────────────────────────────────────────────────────────────────────
-- Run separately: Segment summary
-- ─────────────────────────────────────────────────────────────────────────────
/*
select *
from segment_summary
order by total_monetary desc;
*/
