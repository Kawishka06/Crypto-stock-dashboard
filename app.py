import time
from datetime import datetime
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# -------------------------
# Page config + simple styling
# -------------------------
st.set_page_config(
    page_title="Stock Market and Crypto Forecast Dashboard",
    page_icon="📈",
    layout="wide",
)

st.markdown("""
<style>
.small-muted { color: rgba(255,255,255,0.65); font-size: 0.9rem; }
.kpi { padding: 14px 14px 10px 14px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.10); }
.kpi-title { font-size: 0.85rem; opacity: 0.7; }
.kpi-value { font-size: 1.5rem; font-weight: 700; margin-top: 4px; }
.kpi-sub { font-size: 0.85rem; opacity: 0.7; margin-top: 4px; }
hr { border: none; height: 1px; background: rgba(255,255,255,0.12); margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helpers
# -------------------------
def fmt_num(x, asset):
    if x is None:
        return "-"
    # SL20 looks like an index; crypto looks like price. You can tweak formatting.
    if asset == "SL20_SYN":
        return f"{x:,.2f}"
    return f"{x:,.2f}"

@st.cache_data(ttl=30)
def get_json(url, params=None):
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def build_forecast_fig(history_df, pred_df, asset):
    fig = go.Figure()

    # Actual
    if history_df is not None and not history_df.empty:
        fig.add_trace(go.Scatter(
            x=history_df["date"], y=history_df["close"],
            mode="lines", name="Actual",
        ))

    # Forecast (and connect from last actual point)
    if pred_df is not None and not pred_df.empty:
        if history_df is not None and not history_df.empty:
            last_actual_date = history_df["date"].iloc[-1]
            last_actual_val = history_df["close"].iloc[-1]

            # connect last actual -> first forecast
            x_conn = [last_actual_date, pred_df["date"].iloc[0]]
            y_conn = [last_actual_val, pred_df["yhat"].iloc[0]]

            fig.add_trace(go.Scatter(
                x=x_conn, y=y_conn,
                mode="lines",
                line=dict(dash="dot"),
                name="Transition",
                showlegend=False
            ))

            # vertical line where forecast starts
            fig.add_vline(x=pred_df["date"].iloc[0], line_dash="dash", opacity=0.4)

        fig.add_trace(go.Scatter(
            x=pred_df["date"], y=pred_df["yhat"],
            mode="lines+markers",
            line=dict(dash="dot"),
            name="Forecast",
        ))

    fig.update_layout(
        title=f"{asset} — Actual vs Forecast",
        xaxis_title="Date",
        yaxis_title="Value",
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=55, b=10)
    )
    return fig


def build_residual_fig(history_df, pred_df):
    # Residuals only make sense where dates overlap between actual and predicted
    if history_df is None or pred_df is None or history_df.empty or pred_df.empty:
        return None, None

    a = history_df.copy()
    p = pred_df.copy()
    merged = pd.merge(a, p, on="date", how="inner")
    if merged.empty:
        return None, None

    merged["residual"] = merged["close"] - merged["yhat"]
    merged["abs_error"] = merged["residual"].abs()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=merged["date"], y=merged["residual"], name="Residual (Actual - Forecast)"
    ))
    fig.update_layout(
        title="Residuals on overlapping dates",
        xaxis_title="Date",
        yaxis_title="Residual",
        height=360,
        margin=dict(l=10, r=10, t=55, b=10)
    )

    mae = float(merged["abs_error"].mean())
    return fig, mae

# -------------------------
# Sidebar (controls)
# -------------------------
st.sidebar.title("⚙️ Controls")

API_BASE = st.sidebar.text_input(
    "Prediction API base URL",
    value="https://crypto-and-stock.onrender.com"
).rstrip("/")

assets = ["SL20_SYN", "BTC-USD", "ETH-USD"]
asset = st.sidebar.selectbox("Asset", assets, index=0)

horizon = st.sidebar.slider("Forecast horizon", 1, 14, 7)
history_days = st.sidebar.selectbox("History window", [90, 180, 365, 730], index=2)

auto_refresh = st.sidebar.checkbox("Auto-refresh", True)
refresh_sec = st.sidebar.number_input("Refresh interval (seconds)", 10, 600, 60)

st.sidebar.markdown("---")
st.sidebar.caption("Tip: If you redeploy the API, refresh the dashboard page.")

# -------------------------
# Header
# -------------------------
st.title("📈 Stock Market and Crypto Forecast Dashboard")
st.write(
    f"<span class='small-muted'>Backend:</span> <code>{API_BASE}</code>",
    unsafe_allow_html=True
)

# -------------------------
# API connectivity + data fetch
# -------------------------
# Health check
health_ok = False
health_msg = ""
try:
    health = get_json(f"{API_BASE}/health")
    health_ok = (health.get("status") == "ok")
    health_msg = str(health)
except Exception as e:
    health_msg = str(e)

if not health_ok:
    st.error(f"API not reachable or unhealthy: {health_msg}")
    st.stop()

# Fetch predictions
pred_data = None
pred_df = pd.DataFrame()
try:
    pred_data = get_json(f"{API_BASE}/predict", params={"asset": asset, "horizon": horizon})
    pred_df = pd.DataFrame(pred_data.get("predictions", []))
    if not pred_df.empty:
        pred_df["date"] = pd.to_datetime(pred_df["date"]).dt.date.astype(str)
except Exception as e:
    st.error(f"/predict failed: {e}")
    st.stop()

# Fetch history (optional — requires /history endpoint in API)
history_df = pd.DataFrame()
history_supported = True
try:
    hist = get_json(f"{API_BASE}/history", params={"asset": asset, "period_days": history_days})
    history_df = pd.DataFrame(hist.get("history", []))
    if not history_df.empty:
        history_df["date"] = pd.to_datetime(history_df["date"]).dt.date.astype(str)
except Exception:
    history_supported = False
    history_df = pd.DataFrame()

# -------------------------
# KPIs row
# -------------------------
last_date = pred_data.get("last_date")
last_value = pred_data.get("last_value")

# 7-day (horizon) change: last forecast vs last actual
end_pred = None
if not pred_df.empty:
    end_pred = float(pred_df.iloc[-1]["yhat"])

delta_h = None
pct_h = None
if (last_value is not None) and (end_pred is not None):
    delta_h = end_pred - float(last_value)
    pct_h = (delta_h / float(last_value)) * 100.0 if float(last_value) != 0 else None

next_pred = None
if not pred_df.empty:
    next_pred = float(pred_df.iloc[0]["yhat"])

delta = None
pct = None
if (last_value is not None) and (next_pred is not None):
    delta = next_pred - float(last_value)
    if float(last_value) != 0:
        pct = (delta / float(last_value)) * 100.0

run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

c1, c2, c3, c4,c5 = st.columns(5)

with c1:
    st.markdown(
        f"<div class='kpi'><div class='kpi-title'>Asset</div>"
        f"<div class='kpi-value'>{asset}</div>"
        f"<div class='kpi-sub'>Updated: {run_time}</div></div>",
        unsafe_allow_html=True
    )

with c2:
    st.markdown(
        f"<div class='kpi'><div class='kpi-title'>Last value</div>"
        f"<div class='kpi-value'>{fmt_num(last_value, asset)}</div>"
        f"<div class='kpi-sub'>Last date: {last_date}</div></div>",
        unsafe_allow_html=True
    )

with c3:
    st.markdown(
        f"<div class='kpi'><div class='kpi-title'>Next forecast</div>"
        f"<div class='kpi-value'>{fmt_num(next_pred, asset)}</div>"
        f"<div class='kpi-sub'>Horizon: {horizon} steps</div></div>",
        unsafe_allow_html=True
    )

with c4:
    if delta is None:
        st.markdown(
            "<div class='kpi'><div class='kpi-title'>Change (next vs last)</div>"
            "<div class='kpi-value'>-</div><div class='kpi-sub'>-</div></div>",
            unsafe_allow_html=True
        )
    else:
        arrow = "▲" if delta >= 0 else "▼"
        st.markdown(
            f"<div class='kpi'><div class='kpi-title'>Change (next vs last)</div>"
            f"<div class='kpi-value'>{arrow} {delta:,.2f}</div>"
            f"<div class='kpi-sub'>{pct:,.3f}%</div></div>",
            unsafe_allow_html=True
        )

with c5:
    if delta_h is None or pct_h is None:
        st.markdown(
            "<div class='kpi'><div class='kpi-title'>Horizon change</div>"
            "<div class='kpi-value'>-</div><div class='kpi-sub'>-</div></div>",
            unsafe_allow_html=True
        )
    else:
        arrow = "▲" if delta_h >= 0 else "▼"
        st.markdown(
            f"<div class='kpi'><div class='kpi-title'>Horizon change ({horizon}d)</div>"
            f"<div class='kpi-value'>{arrow} {delta_h:,.2f}</div>"
            f"<div class='kpi-sub'>{pct_h:,.3f}%</div></div>",
            unsafe_allow_html=True
        )

st.markdown("<hr/>", unsafe_allow_html=True)

# -------------------------
# Main charts + table
# -------------------------
left, right = st.columns([2.2, 1])

with left:
    fig = build_forecast_fig(history_df if history_supported else None, pred_df, asset)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Forecast table")
    if pred_df.empty:
        st.info("No forecast returned.")
    else:
        show_df = pred_df.rename(columns={"date": "Date", "yhat": "Predicted"})
        st.dataframe(show_df, use_container_width=True, height=420)

        csv = show_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download forecast CSV",
            data=csv,
            file_name=f"{asset}_forecast_{horizon}.csv",
            mime="text/csv"
        )

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.subheader("Data status")
    st.write(f"History endpoint: {'✅ available' if history_supported else '⚠️ not available'}")
    st.caption("If history is unavailable, only the forecast line will be shown.")

# -------------------------
# Residuals section (if history overlaps forecast)
# -------------------------
st.markdown("<hr/>", unsafe_allow_html=True)
st.subheader("Diagnostics")

if history_supported:
    res_fig, mae = build_residual_fig(history_df, pred_df)
    if res_fig is None:
        st.info("No overlapping dates between actual history and forecast (normal if forecasts are future dates).")
    else:
        st.plotly_chart(res_fig, use_container_width=True)
        st.metric("MAE on overlapping dates", f"{mae:,.4f}")
else:
    st.info("Enable /history in your API to show residual diagnostics.")

# -------------------------
# Auto refresh
# -------------------------
if auto_refresh:
    st.caption(f"Auto-refresh enabled: every {int(refresh_sec)} seconds.")
    st_autorefresh(interval=int(refresh_sec)*1000,key="auto_refresh")