-- generate_schema_name.sql
-- Override dbt's default schema naming to NOT prefix schema names with the target name.
-- e.g. dbt default: "dev_staging" → with this macro: "staging"

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
