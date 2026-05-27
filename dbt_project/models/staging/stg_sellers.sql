-- stg_sellers.sql

with source as (
    select * from {{ source('raw', 'STG_SELLERS') }}
),

renamed as (
    select
        SELLER_ID                    as seller_id,
        SELLER_ZIP_CODE_PREFIX       as zip_code_prefix,
        SELLER_CITY                  as seller_city,
        SELLER_STATE                 as seller_state
    from source
)

select * from renamed
