-- dim_sellers.sql
-- Seller dimension with surrogate key and region mapping.

with sellers as (
    select * from {{ ref('stg_sellers') }}
),

with_region as (
    select
        {{ dbt_utils.generate_surrogate_key(['seller_id']) }}    as seller_key,
        seller_id,
        seller_city,
        seller_state,

        case seller_state
            when 'SP' then 'Southeast'
            when 'RJ' then 'Southeast'
            when 'MG' then 'Southeast'
            when 'ES' then 'Southeast'
            when 'RS' then 'South'
            when 'SC' then 'South'
            when 'PR' then 'South'
            when 'BA' then 'Northeast'
            when 'PE' then 'Northeast'
            when 'CE' then 'Northeast'
            when 'MA' then 'Northeast'
            when 'PB' then 'Northeast'
            when 'RN' then 'Northeast'
            when 'AL' then 'Northeast'
            when 'SE' then 'Northeast'
            when 'PI' then 'Northeast'
            when 'AM' then 'North'
            when 'PA' then 'North'
            when 'RO' then 'North'
            when 'AC' then 'North'
            when 'AP' then 'North'
            when 'RR' then 'North'
            when 'TO' then 'North'
            when 'DF' then 'Central-West'
            when 'GO' then 'Central-West'
            when 'MT' then 'Central-West'
            when 'MS' then 'Central-West'
            else 'Unknown'
        end                                                       as seller_region
    from sellers
)

select * from with_region
