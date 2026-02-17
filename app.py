import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Pakiri Ledge Watch", page_icon="🌊", layout="wide")

st.title("🌊 Pakiri Ledge Dashboard")

# --- 1. Sidebar & Calibration ---
with st.sidebar:
    st.header("🎛️ Calibration")
    slope = st.slider("Beach Slope (tan beta)", 0.02, 0.15, 0.0371, format="%.4f")
    st.info("Feb 8th Gold Standard: 0.1200")
    
    st.header("📸 Session Log")
    uploaded_file = st.file_uploader("Upload a photo of the ledge", type=['jpg', 'png'])
    if uploaded_file:
        st.image(uploaded_file, caption="Current Shorebreak State")

# --- 2. Live Data Fetch ---
@st.cache_data(ttl=3600)
def get_extended_forecast():
    # Fetching 10 days of forecast data
    url = "https://marine-api.open-meteo.com/v1/marine?latitude=-36.26&longitude=174.78&hourly=swell_wave_height,swell_wave_period&forecast_days=10&timezone=auto"
    data = requests.get(url).json()
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    # Calculate Iribarren for every hour in the forecast
    # L0 = (g * T^2) / 2pi
    df['wavelength'] = (9.81 * (df['swell_wave_period']**2)) / (2 * np.pi)
    df['iribarren'] = slope / (np.sqrt(df['swell_wave_height'] / df['wavelength']))
    return df

df_forecast = get_extended_forecast()

# --- 3. Current Conditions Metrics ---
current = df_forecast.iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("Current Swell", f"{current['swell_wave_height']}m")
c2.metric("Current Period", f"{current['swell_wave_period']}s")
c3.metric("Iribarren (ξ)", f"{current['iribarren']:.2f}")

# --- 4. The 10-Day Trend Chart ---
st.subheader("📈 10-Day Ledge Forecast")
fig = px.line(df_forecast, x='time', y='iribarren', 
              title="Predicted Ledge Quality (Iribarren Number Over Time)",
              labels={'iribarren': 'Iribarren Number (ξ)', 'time': 'Date'})

# Add a 'Golden Zone' reference line
fig.add_hline(y=1.2, line_dash="dash", line_color="gold", annotation_text="Golden Ledge Zone")
fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# --- 5. Session Verdict ---
if current['iribarren'] > 1.2:
    st.success("🚀 **STATUS: GOLDEN.** The ledge is vertical. Go now!")
elif current['iribarren'] > 0.7:
    st.warning("🏄 **STATUS: INTERMEDIATE.** Shorebreak is active but might be soft.")
else:
    st.error("💨 **STATUS: WASHED OUT.** Too flat for skimming.")
