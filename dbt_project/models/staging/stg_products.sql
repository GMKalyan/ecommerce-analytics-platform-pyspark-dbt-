-- stg_products.sql
-- Staging: rename product columns to clean English names.

with source as (
    select * from {{ source('raw', 'STG_PRODUCTS') }}
),

renamed as (
    select
        PRODUCT_ID                        as product_id,
        PRODUCT_CATEGORY_NAME             as product_category,
        -- Original dataset has typos ("lenght") — kept as-is in Silver, renamed here
        PRODUCT_NAME_LENGHT               as name_length,
        PRODUCT_DESCRIPTION_LENGHT        as description_length,
        PRODUCT_PHOTOS_QTY                as photos_qty,
        PRODUCT_WEIGHT_G                  as weight_g,
        PRODUCT_LENGTH_CM                 as length_cm,
        PRODUCT_HEIGHT_CM                 as height_cm,
        PRODUCT_WIDTH_CM                  as width_cm,
        PRODUCT_VOLUME_CM3                as volume_cm3
    from source
)

select * from renamed
