-- assert_payment_amount_positive.sql
-- Custom test: all payment_amount values in fact_orders must be >= 0.
-- Zero is allowed (free orders / full vouchers). Negative is not.

select
    order_id,
    payment_amount
from {{ ref('fact_orders') }}
where payment_amount < 0
