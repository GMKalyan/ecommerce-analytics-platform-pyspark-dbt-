"""Reusable Plotly chart builders for the dashboard."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from .constants import PALETTE


# ─────────────────────────────────────────────────────────────────────────────
# KPI card helper (returns a go.Figure with a single big number)
# ─────────────────────────────────────────────────────────────────────────────
def kpi_card(value: str, label: str, delta: str | None = None, color: str = "#1f77b4") -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="number+delta" if delta else "number",
        value=None,
        number={"prefix": "", "suffix": "", "valueformat": ""},
        title={"text": f"<b>{value}</b><br><span style='font-size:0.8em;color:gray'>{label}</span>"},
        delta={"reference": 0, "valueformat": ".1f"} if delta else None,
    ))
    fig.update_layout(height=140, margin=dict(t=20, b=0, l=0, r=0),
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Line chart: orders over time
# ─────────────────────────────────────────────────────────────────────────────
def orders_over_time(df: pd.DataFrame, freq: str = "ME") -> go.Figure:
    ts = (
        df.set_index("order_purchase_timestamp")
        .resample(freq)["order_id"]
        .count()
        .reset_index()
        .rename(columns={"order_purchase_timestamp": "date", "order_id": "orders"})
    )
    fig = px.line(ts, x="date", y="orders",
                  labels={"date": "Date", "orders": "Orders"},
                  color_discrete_sequence=[PALETTE["primary"]])
    fig.update_layout(margin=dict(t=10, b=30), hovermode="x unified")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Revenue bar chart by month
# ─────────────────────────────────────────────────────────────────────────────
def revenue_by_month(df: pd.DataFrame) -> go.Figure:
    monthly = (
        df.dropna(subset=["order_purchase_timestamp", "total_payment"])
        .groupby(df["order_purchase_timestamp"].dt.to_period("M"))["total_payment"]
        .sum()
        .reset_index()
    )
    monthly["order_purchase_timestamp"] = monthly["order_purchase_timestamp"].astype(str)
    fig = px.bar(monthly, x="order_purchase_timestamp", y="total_payment",
                 labels={"order_purchase_timestamp": "Month", "total_payment": "Revenue (BRL)"},
                 color_discrete_sequence=[PALETTE["secondary"]])
    fig.update_layout(margin=dict(t=10, b=40), xaxis_tickangle=-45)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Choropleth: orders or revenue by state (Brazil)
# ─────────────────────────────────────────────────────────────────────────────
def choropleth_brazil(df_state: pd.DataFrame, state_col: str, value_col: str,
                      title: str = "", color_scale: str = "Blues") -> go.Figure:
    fig = px.choropleth(
        df_state,
        locations=state_col,
        locationmode="geojson-id",
        color=value_col,
        color_continuous_scale=color_scale,
        title=title,
        labels={value_col: value_col},
    )
    # Fallback to simple bar chart if GeoJSON not available
    fig2 = px.bar(
        df_state.sort_values(value_col, ascending=False),
        x=state_col, y=value_col,
        color=value_col, color_continuous_scale=color_scale,
        labels={state_col: "State", value_col: value_col},
        title=title,
    )
    fig2.update_layout(margin=dict(t=40, b=40), showlegend=False)
    return fig2


# ─────────────────────────────────────────────────────────────────────────────
# Delivery distribution
# ─────────────────────────────────────────────────────────────────────────────
def delivery_histogram(df: pd.DataFrame) -> go.Figure:
    data = df["delivery_days"].dropna()
    fig = px.histogram(data, nbins=50,
                       labels={"value": "Delivery Days", "count": "Orders"},
                       color_discrete_sequence=[PALETTE["primary"]])
    fig.update_layout(margin=dict(t=10, b=30), showlegend=False,
                      xaxis_title="Delivery Days", yaxis_title="Orders")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Review score distribution
# ─────────────────────────────────────────────────────────────────────────────
def review_score_bar(df: pd.DataFrame) -> go.Figure:
    counts = df["review_score"].value_counts().sort_index().reset_index()
    counts.columns = ["score", "count"]
    fig = px.bar(counts, x="score", y="count",
                 color="score", color_continuous_scale="RdYlGn",
                 labels={"score": "Review Score", "count": "Orders"})
    fig.update_layout(margin=dict(t=10, b=30), showlegend=False, coloraxis_showscale=False)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Scatter: seller performance
# ─────────────────────────────────────────────────────────────────────────────
def seller_scatter(df: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        df, x="avg_delivery_days", y="avg_review_score",
        size="order_count", color="revenue",
        hover_name="seller_id",
        color_continuous_scale="Viridis",
        labels={
            "avg_delivery_days": "Avg Delivery Days",
            "avg_review_score": "Avg Review Score",
            "order_count": "Orders",
            "revenue": "Revenue (BRL)",
        },
    )
    fig.update_layout(margin=dict(t=10, b=30))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Feature importance bar chart
# ─────────────────────────────────────────────────────────────────────────────
def feature_importance_chart(fi_df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        fi_df.sort_values("importance"),
        x="importance", y="feature",
        orientation="h",
        color="importance", color_continuous_scale="Blues",
        labels={"importance": "Importance", "feature": "Feature"},
    )
    fig.update_layout(margin=dict(t=10, b=30), showlegend=False,
                      coloraxis_showscale=False)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Confusion matrix heatmap
# ─────────────────────────────────────────────────────────────────────────────
def confusion_matrix_heatmap(cm: list[list[int]]) -> go.Figure:
    labels = ["bad (< 4)", "good (>= 4)"]
    fig = go.Figure(go.Heatmap(
        z=cm,
        x=[f"Predicted {l}" for l in labels],
        y=[f"Actual {l}" for l in labels],
        colorscale="Blues",
        text=[[str(v) for v in row] for row in cm],
        texttemplate="%{text}",
        showscale=False,
    ))
    fig.update_layout(margin=dict(t=10, b=30))
    return fig
