-- int_order_items_enriched.sql
-- One row per order-item: order_items + products + sellers joined.
-- The order_items table lives in STG_ORDERS source; it is NOT aggregated in Silver,
-- so we reference the raw source directly here.
-- Note: STG_ORDER_ITEMS is loaded separately by the Snowflake loader (future Phase).
-- For now, this model is a blueprint — it will activate once the items table is loaded.

{{
  config(
    enabled=false,
    description='Requires STG_ORDER_ITEMS — load this table to activate.'
  )
}}

with order_items as (
    -- Reference: {{ source('raw', 'STG_ORDER_ITEMS') }}
    -- Will be activated once order_items are loaded to Snowflake.
    select
        order_id,
        order_item_id,
        product_id,
        seller_id,
        shipping_limit_date,
        price,
        freight_value
    from {{ source('raw', 'STG_ORDER_ITEMS') }}
),

products as (
    select * from {{ ref('stg_products') }}
),

sellers as (
    select * from {{ ref('stg_sellers') }}
),

enriched as (
    select
        oi.order_id,
        oi.order_item_id,
        oi.product_id,
        oi.seller_id,
        oi.price,
        oi.freight_value,
        oi.price + oi.freight_value                         as total_item_value,
        oi.shipping_limit_date,

        -- Product attributes
        p.product_category,
        p.name_length,
        p.description_length,
        p.photos_qty,
        p.weight_g,
        p.volume_cm3,

        -- Seller attributes
        s.seller_city,
        s.seller_state

    from order_items oi
    left join products p on oi.product_id = p.product_id
    left join sellers  s on oi.seller_id  = s.seller_id
)

select * from enriched
