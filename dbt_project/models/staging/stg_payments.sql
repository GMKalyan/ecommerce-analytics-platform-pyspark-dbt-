-- stg_payments.sql
-- One row per order — already aggregated in PySpark Silver layer.

with source as (
    select * from {{ source('raw', 'STG_PAYMENTS') }}
),

renamed as (
    select
        ORDER_ID                      as order_id,
        TOTAL_PAYMENT                 as payment_amount,
        NUM_INSTALLMENTS              as installments,
        PRIMARY_PAYMENT_TYPE          as payment_type
    from source
)

select * from renamed
