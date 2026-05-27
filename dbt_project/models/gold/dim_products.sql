-- dim_products.sql
-- Product dimension: category, physical attributes, surrogate key.

with products as (
    select * from {{ ref('stg_products') }}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['product_id']) }}    as product_key,
        product_id,
        coalesce(product_category, 'unknown')                     as product_category,
        name_length,
        description_length,
        photos_qty,
        weight_g,
        length_cm,
        height_cm,
        width_cm,
        volume_cm3
    from products
)

select * from final
