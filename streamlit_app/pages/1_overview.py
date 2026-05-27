"""Page 1 — Overview: KPIs, order trends, revenue breakdown."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

from streamlit_app.utils.data_loader import get_orders_enriched
from streamlit_app.utils.charts import orders_over_time, revenue_by_month, delivery_histogram, review_score_bar

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")
st.title("📊 Overview")

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading data…"):
    df = get_orders_enriched()

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header("Filters")

ts_col = "order_purchase_timestamp"
df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
df = df.dropna(subset=[ts_col])

min_date = df[ts_col].min().date()
max_date = df[ts_col].max().date()

date_range = st.sidebar.date_input(
    "Order date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

status_opts = sorted(df["order_status"].dropna().unique().tolist())
selected_status = st.sidebar.multiselect("Order status", status_opts, default=["delivered"])

# Apply filters
if len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    df = df[(df[ts_col] >= start) & (df[ts_col] <= end)]

if selected_status:
    df = df[df["order_status"].isin(selected_status)]

st.sidebar.caption(f"{len(df):,} orders in view")

# ── KPI row ───────────────────────────────────────────────────────────────────
total_orders   = len(df["order_id"].unique())
total_revenue  = df["total_payment"].sum()
avg_order_val  = df["total_payment"].mean()
avg_delivery   = df["delivery_days"].dropna().mean()
avg_review     = df["review_score"].dropna().mean()
late_pct       = (df["delivery_days"] > df["estimated_delivery_days"]).mean() * 100 if "estimated_delivery_days" in df.columns else None

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Orders",    f"{total_orders:,}")
c2.metric("Total Revenue",   f"R$ {total_revenue:,.0f}")
c3.metric("Avg Order Value", f"R$ {avg_order_val:.2f}")
c4.metric("Avg Delivery",    f"{avg_delivery:.1f} days")
c5.metric("Avg Review",      f"{avg_review:.2f} / 5")

st.markdown("---")

# ── Order trends ──────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Orders Over Time")
    freq = st.selectbox("Frequency", ["ME", "W", "QE"], index=0,
                        format_func=lambda x: {"ME": "Monthly", "W": "Weekly", "QE": "Quarterly"}[x])
    st.plotly_chart(orders_over_time(df, freq=freq), use_container_width=True)

with col_right:
    st.subheader("Revenue by Month")
    st.plotly_chart(revenue_by_month(df), use_container_width=True)

# ── Payment type breakdown ─────────────────────────────────────────────────────
col_l2, col_r2 = st.columns(2)

with col_l2:
    st.subheader("Payment Type Mix")
    pay_counts = df["primary_payment_type"].value_counts().reset_index()
    pay_counts.columns = ["payment_type", "count"]
    fig_pay = px.pie(pay_counts, values="count", names="payment_type",
                     hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
    fig_pay.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig_pay, use_container_width=True)

with col_r2:
    st.subheader("Review Score Distribution")
    st.plotly_chart(review_score_bar(df), use_container_width=True)

# ── Delivery distribution ─────────────────────────────────────────────────────
st.subheader("Delivery Time Distribution")
st.plotly_chart(delivery_histogram(df), use_container_width=True)

# ── Order status breakdown ────────────────────────────────────────────────────
st.subheader("Orders by Status")
status_counts = get_orders_enriched()["order_status"].value_counts().reset_index()
status_counts.columns = ["status", "count"]
fig_status = px.bar(status_counts, x="status", y="count",
                    color="status", color_discrete_sequence=px.colors.qualitative.Pastel,
                    labels={"status": "Status", "count": "Orders"})
fig_status.update_layout(showlegend=False, margin=dict(t=10, b=30))
st.plotly_chart(fig_status, use_container_width=True)
