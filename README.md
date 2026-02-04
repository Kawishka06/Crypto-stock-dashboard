# 📈 Market Forecast Dashboard

An interactive **web-based dashboard** for visualizing stock and cryptocurrency forecasts, historical price movements, and model predictions in real time.

This dashboard consumes a deployed **ML prediction API** and presents results in a clean, user-friendly interface suitable for analysis and demonstrations.

---

## 🔹 Features

- Interactive visualization of:
  - Historical price data
  - LSTM-based future forecasts
- Supports multiple assets:
  - BTC, ETH (Crypto)
  - SL20 Synthetic Index (Sri Lankan stock market use case)
- Configurable forecast horizon
- Auto-refresh for live updates
- Downloadable forecast data (CSV)
- Clear separation between actual data and predicted values

---

## 🧠 Purpose

The dashboard is designed as a **decision-support visualization layer**, not just a plotting tool.  
It helps users:
- Understand market trends
- Compare historical behavior with model forecasts
- Interpret predictions visually rather than relying on raw numbers

---

## 🛠️ Tech Stack

- HTML
- CSS
- JavaScript
- Plotly.js
- REST API (FastAPI backend)

---

## ▶️ How to Run Locally

```bash
# Open index.html using Live Server or any static server
