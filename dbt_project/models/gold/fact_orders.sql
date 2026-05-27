-- fact_orders.sql
-- Central fact table: one row per order.
-- Joins to dim_customers, dim_dates, dim_payment via surrogate keys.
-- Note: seller_key and product_key are order-level approximations
-- (a single order can have multiple items/sellers; exact item-level
-- granularity requires STG_ORDER_ITEMS — see int_order_items_enriched).

with orders as (
    select * from {{ ref('int_orders_enriched') }}
),

dim_customers as (
    select customer_key, customer_id from {{ ref('dim_customers') }}
),

dim_payment as (
    select payment_key, payment_type, installments from {{ ref('dim_payment') }}
),

fact as (
    select
        -- Surrogate key for the fact row
        {{ dbt_utils.generate_surrogate_key(['o.order_id']) }}      as order_key,

        o.order_id,

        -- Foreign keys to dimensions
        dc.customer_key,
        dp.payment_key,

        -- Date key (integer YYYYMMDD) — joins to dim_dates
        cast(to_char(o.purchased_at, 'YYYYMMDD') as integer)        as date_key,

        -- Measures
        o.order_status,
        coalesce(o.payment_amount, 0)                               as payment_amount,
        o.installments,
        o.payment_type,
        o.delivery_days,
        o.estimated_delivery_days,
        coalesce(o.is_late, false)                                  as is_late,
        coalesce(o.delivery_delay_days, 0)                          as delivery_delay_days,
        o.review_score,

        -- Timestamps
        o.purchased_at,
        o.approved_at,
        o.shipped_at,
        o.delivered_at,
        o.estimated_delivery_at,

        -- Time grain helpers
        o.order_year,
        o.order_month,
        o.order_day_of_week

    from orders o
    left join dim_customers dc
           on o.customer_id = dc.customer_id
    left join dim_payment dp
           on o.payment_type = dp.payment_type
          and coalesce(o.installments, 1) = dp.installments
)

select * from fact
