-- dim_dates.sql
-- Date dimension: spine from 2016-01-01 to 2018-12-31.
-- Uses dbt_utils.date_spine macro to generate one row per calendar day.

{{ config(materialized='table') }}

with date_spine as (
    {{
        dbt_utils.date_spine(
            datepart="day",
            start_date="cast('2016-01-01' as date)",
            end_date="cast('2019-01-01' as date)"
        )
    }}
),

dates as (
    select
        cast(date_day as date)                                                    as full_date,

        -- Surrogate key: integer YYYYMMDD
        cast(to_char(date_day, 'YYYYMMDD') as integer)                           as date_key,

        extract(year  from date_day)::integer                                     as year,
        extract(month from date_day)::integer                                     as month,
        extract(day   from date_day)::integer                                     as day,
        extract(quarter from date_day)::integer                                   as quarter,

        -- Day of week: 1=Sunday in Snowflake (DAYOFWEEK), 1=Monday in ISO
        dayofweek(date_day)                                                       as day_of_week,         -- 0=Mon in Snowflake
        dayofweekiso(date_day)                                                    as day_of_week_iso,     -- 1=Mon

        -- Human-readable names
        to_char(date_day, 'Day')                                                  as day_name,
        to_char(date_day, 'Month')                                                as month_name,

        -- Flags
        case when dayofweek(date_day) in (0, 6) then true else false end          as is_weekend,

        -- Period labels
        year(date_day)::varchar || '-Q' || extract(quarter from date_day)::varchar as year_quarter,
        to_char(date_day, 'YYYY-MM')                                              as year_month

    from date_spine
)

select * from dates
order by full_date
