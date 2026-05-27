-- int_orders_enriched.sql
-- One row per order: orders + payments + reviews joined into a single wide record.
-- Powers both fact_orders and RFM segmentation downstream.

with orders as (
    select * from {{ ref('stg_orders') }}
),

payments as (
    select * from {{ ref('stg_payments') }}
),

reviews as (
    select * from {{ ref('stg_reviews') }}
),

enriched as (
    select
        -- Order identity
        o.order_id,
        o.customer_id,
        o.order_status,

        -- Timestamps
        o.purchased_at,
        o.approved_at,
        o.shipped_at,
        o.delivered_at,
        o.estimated_delivery_at,

        -- Delivery metrics
        o.delivery_days,
        o.estimated_delivery_days,
        o.is_late,
        o.delivery_delay_days,

        -- Time dimensions
        o.order_year,
        o.order_month,
        o.order_day_of_week,

        -- Payment fields (null if no payment record — edge case)
        p.payment_amount,
        p.installments,
        p.payment_type,

        -- Review fields (null if no review submitted)
        r.review_score,
        r.review_id,
        r.review_created_at,
        r.review_answered_at

    from orders o
    left join payments p on o.order_id = p.order_id
    left join reviews  r on o.order_id = r.order_id
)

select * from enriched
