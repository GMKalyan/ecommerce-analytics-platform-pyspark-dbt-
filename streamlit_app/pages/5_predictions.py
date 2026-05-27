"""Page 5 — Predictions: ML delivery time + review score predictors."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go

from streamlit_app.utils.data_loader import (
    load_delivery_metrics,
    load_review_metrics,
    load_delivery_feature_importance,
    load_review_feature_importance,
)
from streamlit_app.utils.charts import feature_importance_chart, confusion_matrix_heatmap
from streamlit_app.utils.constants import STATE_NAMES, PAYMENT_TYPES

st.set_page_config(page_title="Predictions", page_icon="🤖", layout="wide")
st.title("🤖 ML Predictions")

# ─────────────────────────────────────────────────────────────────────────────
# Load model artifacts
# ─────────────────────────────────────────────────────────────────────────────
delivery_metrics = load_delivery_metrics()
review_metrics   = load_review_metrics()
delivery_fi      = load_delivery_feature_importance()
review_fi        = load_review_feature_importance()

# ─────────────────────────────────────────────────────────────────────────────
# Model Cards
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("Trained Models")
col1, col2 = st.columns(2)

with col1:
    if delivery_metrics:
        bm = delivery_metrics.get("best_model", "—")
        bmet = delivery_metrics.get("best_metrics", {})
        st.success(f"**Delivery Time Regression**\n\n"
                   f"Best: `{bm}`\n\n"
                   f"RMSE: **{bmet.get('RMSE', '—')}** days · "
                   f"MAE: **{bmet.get('MAE', '—')}** days · "
                   f"R²: **{bmet.get('R2', '—')}**")
    else:
        st.warning("Delivery model not found — run `python -m src.ml.train`")

with col2:
    if review_metrics:
        bm = review_metrics.get("best_model", "—")
        bmet = review_metrics.get("best_metrics", {})
        st.success(f"**Review Score Classification**\n\n"
                   f"Best: `{bm}`\n\n"
                   f"F1: **{bmet.get('f1', '—')}** · "
                   f"Accuracy: **{bmet.get('accuracy', '—')}** · "
                   f"Precision: **{bmet.get('precision', '—')}**")
    else:
        st.warning("Review model not found — run `python -m src.ml.train`")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# All-model comparison tables
# ─────────────────────────────────────────────────────────────────────────────
cmp1, cmp2 = st.columns(2)

with cmp1:
    st.markdown("**Regression — all candidates**")
    if delivery_metrics:
        import pandas as pd
        rows = [{"model": k, **v} for k, v in delivery_metrics.get("all_models", {}).items()]
        df_d = pd.DataFrame(rows)
        best_name = delivery_metrics.get("best_model", "")
        st.dataframe(df_d.style.apply(
            lambda row: ["background-color: #d4edda" if row["model"] == best_name else "" for _ in row],
            axis=1
        ), use_container_width=True, hide_index=True)

with cmp2:
    st.markdown("**Classification — all candidates**")
    if review_metrics:
        import pandas as pd
        rows = [{"model": k, **v} for k, v in review_metrics.get("all_models", {}).items()]
        df_r = pd.DataFrame(rows)
        best_name = review_metrics.get("best_model", "")
        st.dataframe(df_r.style.apply(
            lambda row: ["background-color: #d4edda" if row["model"] == best_name else "" for _ in row],
            axis=1
        ), use_container_width=True, hide_index=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Feature importance
# ─────────────────────────────────────────────────────────────────────────────
fi1, fi2 = st.columns(2)
with fi1:
    st.subheader("Delivery Model — Feature Importance")
    if not delivery_fi.empty:
        st.plotly_chart(feature_importance_chart(delivery_fi), use_container_width=True)

with fi2:
    st.subheader("Review Model — Feature Importance")
    if not review_fi.empty:
        st.plotly_chart(feature_importance_chart(review_fi), use_container_width=True)

# ── Confusion matrix ──────────────────────────────────────────────────────────
if review_metrics and "confusion_matrix" in review_metrics:
    st.subheader("Review Model — Confusion Matrix (test set)")
    st.plotly_chart(confusion_matrix_heatmap(review_metrics["confusion_matrix"]),
                    use_container_width=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Live Predictor
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("Live Predictor")
st.caption("Enter order features to get real-time predictions from the trained models.")

states = sorted(STATE_NAMES.keys())

with st.form("predictor_form"):
    c1, c2, c3 = st.columns(3)

    with c1:
        seller_state  = st.selectbox("Seller State",   states, index=states.index("SP"))
        customer_state= st.selectbox("Customer State", states, index=states.index("RJ"))
        payment_type  = st.selectbox("Payment Type",   PAYMENT_TYPES)

    with c2:
        price         = st.number_input("Product Price (BRL)", min_value=1.0, value=89.90, step=10.0)
        freight       = st.number_input("Freight Value (BRL)", min_value=0.0, value=15.0, step=1.0)
        installments  = st.slider("Num Installments", 1, 24, 3)

    with c3:
        weight_g      = st.number_input("Product Weight (g)", min_value=0, value=500, step=100)
        volume_cm3    = st.number_input("Product Volume (cm³)", min_value=0, value=2000, step=100)
        photos_qty    = st.slider("Product Photos", 1, 20, 3)

    col_dow, col_month = st.columns(2)
    with col_dow:
        day_of_week  = st.selectbox("Order Day of Week",
                                    [0,1,2,3,4,5,6],
                                    format_func=lambda x: ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][x])
    with col_month:
        month = st.selectbox("Order Month", list(range(1,13)),
                             format_func=lambda x: ["Jan","Feb","Mar","Apr","May","Jun",
                                                     "Jul","Aug","Sep","Oct","Nov","Dec"][x-1])

    submitted = st.form_submit_button("Predict", type="primary")

if submitted:
    try:
        from src.ml.predict import predict_delivery_time, predict_review_score

        delivery_features = {
            "seller_state":         seller_state,
            "customer_state":       customer_state,
            "product_weight_g":     weight_g,
            "product_volume_cm3":   volume_cm3,
            "freight_value":        freight,
            "price":                price,
            "primary_payment_type": payment_type,
            "order_day_of_week":    day_of_week,
            "order_month":          month,
            "num_installments":     installments,
        }

        predicted_days = predict_delivery_time(delivery_features)
        is_late_int    = 0  # baseline: assume on time

        review_features = {
            "delivery_days":       predicted_days,
            "delivery_delay_days": 0.0,
            "price":               price,
            "freight_value":       freight,
            "product_weight_g":    weight_g,
            "product_photos_qty":  photos_qty,
            "num_installments":    installments,
            "is_late_int":         is_late_int,
        }

        review_result = predict_review_score(review_features)

        # ── Results ────────────────────────────────────────────────────────
        st.markdown("---")
        r1, r2 = st.columns(2)

        with r1:
            st.metric("Predicted Delivery Time", f"{predicted_days} days")
            # Gauge chart
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=predicted_days,
                gauge={
                    "axis": {"range": [0, 60]},
                    "bar":  {"color": "#1f77b4"},
                    "steps": [
                        {"range": [0, 10], "color": "#d4edda"},
                        {"range": [10, 20], "color": "#fff3cd"},
                        {"range": [20, 60], "color": "#f8d7da"},
                    ],
                    "threshold": {"line": {"color": "red", "width": 4},
                                  "thickness": 0.75, "value": 30},
                },
                title={"text": "Delivery Days"},
                number={"suffix": " days"},
            ))
            fig_gauge.update_layout(height=280, margin=dict(t=20, b=0))
            st.plotly_chart(fig_gauge, use_container_width=True)

        with r2:
            prob = review_result["probability_good"]
            label = review_result["label"]
            color = "success" if review_result["predicted_class"] == 1 else "error"
            st.metric("Predicted Review", label, f"P(good) = {prob:.1%}")

            fig_prob = go.Figure(go.Indicator(
                mode="gauge+number",
                value=prob * 100,
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar":  {"color": "#2ca02c" if prob >= 0.5 else "#d62728"},
                    "steps": [
                        {"range": [0, 50],  "color": "#f8d7da"},
                        {"range": [50, 100],"color": "#d4edda"},
                    ],
                },
                title={"text": "Probability of Good Review (%)"},
                number={"suffix": "%"},
            ))
            fig_prob.update_layout(height=280, margin=dict(t=20, b=0))
            st.plotly_chart(fig_prob, use_container_width=True)

    except FileNotFoundError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Prediction failed: {e}")
