"""Page 2 — Geographic: Orders and revenue by Brazilian state."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

from streamlit_app.utils.data_loader import get_orders_enriched
from streamlit_app.utils.constants import STATE_NAMES, REGION_MAP, REGION_COLORS

st.set_page_config(page_title="Geographic", page_icon="🗺️", layout="wide")
st.title("🗺️ Geographic Analysis")

with st.spinner("Loading data…"):
    df = get_orders_enriched()

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header("Filters")
df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"], errors="coerce")
df = df.dropna(subset=["order_purchase_timestamp"])

years = sorted(df["order_purchase_timestamp"].dt.year.dropna().unique().tolist())
sel_years = st.sidebar.multiselect("Year", years, default=years)
if sel_years:
    df = df[df["order_purchase_timestamp"].dt.year.isin(sel_years)]

metric = st.sidebar.selectbox("Metric", ["order_count", "revenue", "avg_review_score", "avg_delivery_days"])

# ── Customer state aggregation ────────────────────────────────────────────────
cust_agg = (
    df.groupby("customer_state")
    .agg(
        order_count=("order_id", "count"),
        revenue=("total_payment", "sum"),
        avg_review_score=("review_score", "mean"),
        avg_delivery_days=("delivery_days", "mean"),
    )
    .reset_index()
)
cust_agg["state_name"] = cust_agg["customer_state"].map(STATE_NAMES)
cust_agg["region"] = cust_agg["customer_state"].map(REGION_MAP)

# ── Seller state aggregation ──────────────────────────────────────────────────
seller_agg = (
    df.dropna(subset=["seller_state"])
    .groupby("seller_state")
    .agg(
        order_count=("order_id", "count"),
        revenue=("total_payment", "sum"),
        avg_delivery_days=("delivery_days", "mean"),
    )
    .reset_index()
)

st.markdown("---")

# ── Top states bar charts ─────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader(f"Top 10 Customer States — {metric}")
    top_cust = cust_agg.sort_values(metric, ascending=False).head(10)
    fig = px.bar(
        top_cust, x="customer_state", y=metric,
        color=metric, color_continuous_scale="Blues",
        hover_data=["state_name", "region"],
        labels={"customer_state": "State", metric: metric},
    )
    fig.update_layout(margin=dict(t=10, b=30), coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Top 10 Seller States — order_count")
    top_sell = seller_agg.sort_values("order_count", ascending=False).head(10)
    fig2 = px.bar(
        top_sell, x="seller_state", y="order_count",
        color="order_count", color_continuous_scale="Oranges",
        labels={"seller_state": "State", "order_count": "Orders"},
    )
    fig2.update_layout(margin=dict(t=10, b=30), coloraxis_showscale=False)
    st.plotly_chart(fig2, use_container_width=True)

# ── Full state table ──────────────────────────────────────────────────────────
st.subheader("All States — Customer Metrics")
display_cols = ["customer_state", "state_name", "region", "order_count", "revenue",
                "avg_review_score", "avg_delivery_days"]
display = cust_agg[display_cols].sort_values("order_count", ascending=False).copy()
display["revenue"] = display["revenue"].round(0)
display["avg_review_score"] = display["avg_review_score"].round(2)
display["avg_delivery_days"] = display["avg_delivery_days"].round(1)
st.dataframe(display, use_container_width=True, hide_index=True)

# ── Region breakdown ──────────────────────────────────────────────────────────
st.subheader("Orders by Region")
region_agg = cust_agg.groupby("region")["order_count"].sum().reset_index()
fig_region = px.pie(
    region_agg, values="order_count", names="region",
    color="region",
    color_discrete_map=REGION_COLORS,
    hole=0.35,
)
fig_region.update_layout(margin=dict(t=10, b=10))
st.plotly_chart(fig_region, use_container_width=True)

# ── Delivery heatmap: customer_state vs seller_state ─────────────────────────
st.subheader("Avg Delivery Days: Customer State vs Seller State (Top 10 Each)")
top_c_states = cust_agg.nlargest(10, "order_count")["customer_state"].tolist()
top_s_states = seller_agg.nlargest(10, "order_count")["seller_state"].tolist()

heat_df = (
    df[df["customer_state"].isin(top_c_states) & df["seller_state"].isin(top_s_states)]
    .groupby(["customer_state", "seller_state"])["delivery_days"]
    .mean()
    .reset_index()
)
heat_pivot = heat_df.pivot(index="customer_state", columns="seller_state", values="delivery_days")

fig_heat = px.imshow(
    heat_pivot, color_continuous_scale="RdYlGn_r",
    labels=dict(color="Avg Days", x="Seller State", y="Customer State"),
    aspect="auto",
)
fig_heat.update_layout(margin=dict(t=10, b=30))
st.plotly_chart(fig_heat, use_container_width=True)
