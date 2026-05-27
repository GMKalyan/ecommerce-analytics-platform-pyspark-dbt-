-- dim_payment.sql
-- Payment dimension: payment type + installment bucket.
-- Built from distinct combinations in the payments staging data.

with payments as (
    select distinct
        payment_type,
        installments
    from {{ ref('stg_payments') }}
    where payment_type is not null
),

with_buckets as (
    select
        {{ dbt_utils.generate_surrogate_key(['payment_type', 'installments']) }}  as payment_key,
        payment_type,
        installments,

        -- Installment bucket for analysis
        case
            when installments = 1             then '1 (cash)'
            when installments between 2 and 3 then '2-3'
            when installments between 4 and 6 then '4-6'
            when installments between 7 and 12 then '7-12'
            when installments > 12            then '12+'
            else 'unknown'
        end                                                                        as installments_bucket

    from payments
)

select * from with_buckets
