-- stg_customers.sql
-- Staging: rename columns and alias cleaned city name.

with source as (
    select * from {{ source('raw', 'STG_CUSTOMERS') }}
),

renamed as (
    select
        CUSTOMER_ID                   as customer_id,
        CUSTOMER_UNIQUE_ID            as customer_unique_id,
        CUSTOMER_ZIP_CODE_PREFIX      as zip_code_prefix,
        CUSTOMER_CITY                 as customer_city,       -- already lowercase-trimmed
        CUSTOMER_STATE                as customer_state
    from source
)

select * from renamed
