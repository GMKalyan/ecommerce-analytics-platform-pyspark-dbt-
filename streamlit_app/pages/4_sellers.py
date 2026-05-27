"""Page 4 — Sellers: Leaderboard and performance scatter."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

from streamlit_app.utils.data_loader import get_orders_enriched
from streamlit_app.utils.constants import STATE_NAMES, REGION_MAP
from streamlit_app.utils.charts import seller_scatter

st.set_page_config(page_title="Sellers", page_icon="🏪", layout="wide")
st.title("🏪 Seller Performance")

with st.spinner("Loading data…"):
    df = get_orders_enriched()

df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"], errors="coerce")
df = df[df["order_status"] == "delivered"].dropna(subset=["seller_id"])

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header("Filters")

min_orders = st.sidebar.slider("Min orders per seller", 1, 100, 10)

all_states = sorted(df["seller_state"].dropna().unique().tolist())
sel_states = st.sidebar.multiselect("Seller states", all_states, default=all_states)
if sel_states:
    df = df[df["seller_state"].isin(sel_states)]

# ── Seller aggregation ────────────────────────────────────────────────────────
seller_agg = (
    df.groupby("seller_id")
    .agg(
        order_count=("order_id", "count"),
        revenue=("total_payment", "sum"),
        avg_delivery_days=("delivery_days", "mean"),
        avg_review_score=("review_score", "mean"),
        seller_state=("seller_state", "first"),
    )
    .reset_index()
)
seller_agg = seller_agg[seller_agg["order_count"] >= min_orders].copy()
seller_agg["region"] = seller_agg["seller_state"].map(REGION_MAP)
seller_agg["revenue_per_order"] = seller_agg["revenue"] / seller_agg["order_count"]

st.sidebar.caption(f"{len(seller_agg):,} sellers in view")

# ── KPIs ──────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Sellers",     f"{len(seller_agg):,}")
c2.metric("Avg Orders/Seller",  f"{seller_agg['order_count'].mean():.0f}")
c3.metric("Avg Delivery Days",  f"{seller_agg['avg_delivery_days'].mean():.1f}")
c4.metric("Avg Review Score",   f"{seller_agg['avg_review_score'].mean():.2f}")

st.markdown("---")

# ── Leaderboard top 20 by revenue ─────────────────────────────────────────────
st.subheader("Top 20 Sellers by Revenue")
top20 = seller_agg.nlargest(20, "revenue")[
    ["seller_id", "seller_state", "order_count", "revenue", "avg_delivery_days", "avg_review_score"]
].copy()
top20["seller_id_short"] = top20["seller_id"].str[:8] + "…"
top20["revenue"] = top20["revenue"].round(0)
top20["avg_delivery_days"] = top20["avg_delivery_days"].round(1)
top20["avg_review_score"] = top20["avg_review_score"].round(2)

fig_lb = px.bar(
    top20, x="seller_id_short", y="revenue",
    color="avg_review_score",
    color_continuous_scale="RdYlGn",
    hover_data=["seller_state", "order_count", "avg_delivery_days"],
    labels={"seller_id_short": "Seller", "revenue": "Revenue (BRL)"},
    range_color=[1, 5],
)
fig_lb.update_layout(margin=dict(t=10, b=50), xaxis_tickangle=-45,
                     coloraxis_colorbar_title="Avg Review")
st.plotly_chart(fig_lb, use_container_width=True)

# ── Performance scatter ───────────────────────────────────────────────────────
st.subheader("Delivery Speed vs Review Score (bubble = order volume)")
st.plotly_chart(seller_scatter(seller_agg), use_container_width=True)

# ── Revenue by seller state ───────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("Revenue by Seller State")
    state_rev = (
        seller_agg.groupby("seller_state")["revenue"].sum()
        .sort_values(ascending=False).head(15).reset_index()
    )
    fig_state = px.bar(
        state_rev, x="seller_state", y="revenue",
        color="revenue", color_continuous_scale="Blues",
        labels={"seller_state": "State", "revenue": "Revenue (BRL)"},
    )
    fig_state.update_layout(margin=dict(t=10, b=30), coloraxis_showscale=False)
    st.plotly_chart(fig_state, use_container_width=True)

with col2:
    st.subheader("Delivery Speed Distribution")
    fig_del = px.histogram(
        seller_agg, x="avg_delivery_days", nbins=40,
        color_discrete_sequence=["#ff7f0e"],
        labels={"avg_delivery_days": "Avg Delivery Days", "count": "Sellers"},
    )
    fig_del.update_layout(margin=dict(t=10, b=30), showlegend=False,
                          yaxis_title="Sellers")
    st.plotly_chart(fig_del, use_container_width=True)

# ── Full seller table ─────────────────────────────────────────────────────────
st.subheader("Seller Detail Table")
sort_col = st.selectbox("Sort by", ["revenue", "order_count", "avg_review_score", "avg_delivery_days"],
                        index=0)
display = seller_agg.sort_values(sort_col, ascending=False).head(100).copy()
display["revenue"] = display["revenue"].round(0)
display["avg_delivery_days"] = display["avg_delivery_days"].round(1)
display["avg_review_score"] = display["avg_review_score"].round(2)
display["seller_id"] = display["seller_id"].str[:16] + "…"
st.dataframe(
    display[["seller_id", "seller_state", "region", "order_count", "revenue",
             "avg_delivery_days", "avg_review_score"]],
    use_container_width=True,
    hide_index=True,
)
