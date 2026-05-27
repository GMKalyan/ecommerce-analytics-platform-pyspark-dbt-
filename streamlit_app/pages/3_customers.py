"""Page 3 — Customers: RFM segmentation and review analysis."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from streamlit_app.utils.data_loader import get_orders_enriched

st.set_page_config(page_title="Customers", page_icon="👤", layout="wide")
st.title("👤 Customer Analysis")

with st.spinner("Loading data…"):
    df = get_orders_enriched()

df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"], errors="coerce")
df = df[df["order_status"] == "delivered"].dropna(subset=["order_purchase_timestamp"])

# ── RFM Segmentation ─────────────────────────────────────────────────────────
st.subheader("RFM Segmentation")

snapshot_date = df["order_purchase_timestamp"].max() + pd.Timedelta(days=1)

rfm = (
    df.groupby("customer_id")
    .agg(
        recency=("order_purchase_timestamp", lambda x: (snapshot_date - x.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("total_payment", "sum"),
    )
    .reset_index()
)

# Score each dimension 1–4 using percentile rank (immune to duplicate bin edges)
def _score(series: pd.Series, ascending: bool = True) -> pd.Series:
    pct = series.rank(pct=True, method="average")
    score = pd.cut(pct, bins=[0, 0.25, 0.5, 0.75, 1.0],
                   labels=[1, 2, 3, 4], include_lowest=True).astype(int)
    return score if ascending else (5 - score)

rfm["recency_score"]  = _score(rfm["recency"],  ascending=False)  # lower = fresher = better
rfm["frequency_score"] = _score(rfm["frequency"], ascending=True)
rfm["monetary_score"]  = _score(rfm["monetary"],  ascending=True)

rfm["rfm_score"] = rfm["recency_score"] + rfm["frequency_score"] + rfm["monetary_score"]

def _segment(score: int) -> str:
    if score >= 10: return "Champions"
    if score >= 7:  return "Loyal"
    if score >= 5:  return "At Risk"
    return "Lost"

rfm["segment"] = rfm["rfm_score"].apply(_segment)

seg_palette = {
    "Champions": "#2ca02c",
    "Loyal":     "#1f77b4",
    "At Risk":   "#ff7f0e",
    "Lost":      "#d62728",
}

col1, col2 = st.columns(2)
with col1:
    seg_counts = rfm["segment"].value_counts().reset_index()
    seg_counts.columns = ["segment", "count"]
    fig_seg = px.pie(seg_counts, values="count", names="segment",
                     color="segment", color_discrete_map=seg_palette, hole=0.35)
    fig_seg.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig_seg, use_container_width=True, key="seg_pie")

with col2:
    seg_monetary = rfm.groupby("segment")["monetary"].mean().reset_index()
    fig_mon = px.bar(seg_monetary, x="segment", y="monetary",
                     color="segment", color_discrete_map=seg_palette,
                     labels={"segment": "Segment", "monetary": "Avg Revenue (BRL)"},)
    fig_mon.update_layout(showlegend=False, margin=dict(t=10, b=30))
    st.plotly_chart(fig_mon, use_container_width=True, key="seg_bar")

# RFM stats table
st.markdown("**Segment Summary**")
seg_summary = (
    rfm.groupby("segment")
    .agg(
        customers=("customer_id", "count"),
        avg_recency=("recency", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_monetary=("monetary", "mean"),
    )
    .round(1)
    .reset_index()
)
st.dataframe(seg_summary, use_container_width=True, hide_index=True)

st.markdown("---")

# ── Review Analysis ────────────────────────────────────────────────────────────
st.subheader("Review Score Analysis")

col3, col4 = st.columns(2)
with col3:
    # Review score vs delivery days scatter
    scatter_df = df[["delivery_days", "review_score", "total_payment"]].dropna()
    scatter_df = scatter_df[scatter_df["delivery_days"] <= 60]  # remove outliers
    fig_sc = px.scatter(
        scatter_df.sample(min(5000, len(scatter_df)), random_state=42),
        x="delivery_days", y="review_score",
        opacity=0.3, trendline="lowess",
        color_discrete_sequence=["#1f77b4"],
        labels={"delivery_days": "Delivery Days", "review_score": "Review Score"},
    )
    fig_sc.update_layout(margin=dict(t=10, b=30))
    st.plotly_chart(fig_sc, use_container_width=True, key="review_scatter")

with col4:
    # Late vs on-time review comparison
    if "is_late" in df.columns:
        late_map = {"True": "Late", "False": "On Time", True: "Late", False: "On Time"}
        df["late_label"] = df["is_late"].map(late_map).fillna("Unknown")
        late_review = df.groupby("late_label")["review_score"].mean().reset_index()
        fig_late = px.bar(
            late_review, x="late_label", y="review_score",
            color="late_label",
            color_discrete_map={"Late": "#d62728", "On Time": "#2ca02c", "Unknown": "#7f7f7f"},
            labels={"late_label": "Delivery Status", "review_score": "Avg Review Score"},
            range_y=[0, 5],
        )
        fig_late.update_layout(showlegend=False, margin=dict(t=10, b=30))
        st.plotly_chart(fig_late, use_container_width=True, key="late_bar")

# ── Cohort retention (monthly) ─────────────────────────────────────────────────
st.subheader("Monthly Order Cohort Volume")
df["cohort_month"] = df["order_purchase_timestamp"].dt.to_period("M")
cohort_vol = df.groupby("cohort_month")["order_id"].count().reset_index()
cohort_vol["cohort_month"] = cohort_vol["cohort_month"].astype(str)
fig_cohort = px.bar(
    cohort_vol, x="cohort_month", y="order_id",
    labels={"cohort_month": "Month", "order_id": "Orders"},
    color_discrete_sequence=["#9467bd"],
)
fig_cohort.update_layout(margin=dict(t=10, b=40), xaxis_tickangle=-45)
st.plotly_chart(fig_cohort, use_container_width=True, key="cohort_bar")
