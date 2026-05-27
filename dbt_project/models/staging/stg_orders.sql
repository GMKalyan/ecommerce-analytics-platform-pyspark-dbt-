-- stg_orders.sql
-- Staging: light renaming and type casting from STG_ORDERS source.
-- Already cleaned in PySpark Silver layer; this model formalises the contract.

with source as (
    select * from {{ source('raw', 'STG_ORDERS') }}
),

renamed as (
    select
        ORDER_ID                                             as order_id,
        CUSTOMER_ID                                          as customer_id,
        ORDER_STATUS                                         as order_status,

        -- Timestamps
        ORDER_PURCHASE_TIMESTAMP                             as purchased_at,
        ORDER_APPROVED_AT                                    as approved_at,
        ORDER_DELIVERED_CARRIER_DATE                         as shipped_at,
        ORDER_DELIVERED_CUSTOMER_DATE                        as delivered_at,
        ORDER_ESTIMATED_DELIVERY_DATE                        as estimated_delivery_at,

        -- Derived delivery metrics (computed in PySpark)
        DELIVERY_DAYS                                        as delivery_days,
        ESTIMATED_DELIVERY_DAYS                              as estimated_delivery_days,
        IS_LATE                                              as is_late,
        DELIVERY_DELAY_DAYS                                  as delivery_delay_days,

        -- Time-based features
        ORDER_YEAR                                           as order_year,
        ORDER_MONTH                                          as order_month,
        ORDER_DAY_OF_WEEK                                    as order_day_of_week
    from source
)

select * from renamed
