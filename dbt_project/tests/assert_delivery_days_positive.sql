-- assert_delivery_days_positive.sql
-- Custom test: delivery_days must be >= 0 wherever it is not null.
-- Returns rows that FAIL the test (non-empty result = test failure).

select
    order_id,
    delivery_days
from {{ ref('fact_orders') }}
where delivery_days is not null
  and delivery_days < 0
