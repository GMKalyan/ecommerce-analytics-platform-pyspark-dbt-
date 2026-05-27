-- stg_reviews.sql
-- One review per order (latest), null comments replaced with empty string in Silver.

with source as (
    select * from {{ source('raw', 'STG_REVIEWS') }}
),

renamed as (
    select
        REVIEW_ID                     as review_id,
        ORDER_ID                      as order_id,
        REVIEW_SCORE                  as review_score,
        REVIEW_COMMENT_TITLE          as comment_title,
        REVIEW_COMMENT_MESSAGE        as comment_message,
        REVIEW_CREATION_DATE          as review_created_at,
        REVIEW_ANSWER_TIMESTAMP       as review_answered_at
    from source
)

select * from renamed
