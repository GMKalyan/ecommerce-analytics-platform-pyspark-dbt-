"""
app.py — Main entry point for the Brazilian E-Commerce Analytics Dashboard.

Run:
    cd ecommerce-analytics
    streamlit run streamlit_app/app.py

Pages (auto-discovered from pages/ directory):
    1_overview.py      — KPIs, order trends, revenue
    2_geographic.py    — Orders and revenue by state
    3_customers.py     — RFM segmentation, review analysis
    4_sellers.py       — Seller leaderboard and performance
    5_predictions.py   — ML delivery + review predictors
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports work from pages
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

st.set_page_config(
    page_title="E-Commerce Analytics",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.title("🛒 E-Commerce Analytics")
st.sidebar.caption("Brazilian Olist Dataset · 2016–2018")

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Navigate** using the pages in the sidebar. "
    "Filters applied on each page are independent."
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Stack:** PySpark · Snowflake · dbt · Airflow · scikit-learn · Streamlit"
)

# ── Landing page ──────────────────────────────────────────────────────────────
st.title("Brazilian E-Commerce Analytics Platform")
st.markdown(
    """
    End-to-end analytics platform built on the **Olist Brazilian E-Commerce** dataset
    (~100K orders, 2016–2018) using a full Medallion Architecture.

    | Layer | Technology |
    |-------|-----------|
    | Ingestion | Python + Pandas |
    | Transformation | PySpark (Silver parquets) |
    | Warehousing | Snowflake STG + dbt Gold star schema |
    | Orchestration | Apache Airflow |
    | ML Models | scikit-learn (GradientBoosting) |
    | Dashboard | Streamlit + Plotly |

    **Select a page from the sidebar to explore.**
    """
)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.info("**Overview**\n\nKPIs, order volume trends, revenue by month")
with col2:
    st.info("**Geographic**\n\nOrders and revenue by Brazilian state")
with col3:
    st.info("**Customers**\n\nRFM segmentation, review score analysis")
with col4:
    st.info("**Sellers**\n\nPerformance leaderboard, delivery scatter")

st.markdown("---")
st.caption("Source: [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) · MIT License")
