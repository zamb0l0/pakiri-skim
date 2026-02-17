import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Pakiri Ledge Watch", page_icon="🌊", layout="wide")

# --- CUSTOM CSS FOR TRAFFIC LIGHTS ---
st.markdown("""
    <style>
    .reportview-container .main .block-container{ max-width: 1200px; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    .card { padding: 15px; border-radius: 10px; text-align: center; color: white; font-weight: bold; margin-bottom: 10px; }
    .bg-red { background-color: #ff4b4b; }
    .bg-orange { background-color: #ffa500; }
    .bg-yellow { background-color: #ffff00; color: black !important; }
    .bg-lightgreen { background-color: #90ee90; color: black !important; }
    .bg-darkgreen { background-color: #008000; }
    .bg-blue { background-color: #0000ff; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌊 Pakiri Ledge Command Center")

# --- SIDEBAR & CALIBRATION ---
with st.sidebar:
    st.header("🎛️ Calibration")
    slope = st.slider("Beach Slope (tan beta)", 0.02, 0.15, 0.0371, format="%.4f")
    st.header("📸 Session Log")
    uploaded_file = st.file_uploader("Drop a photo to log the bank", type=['jpg', 'png'])

# --- DATA FETCHING (WAVES + WIND) ---
@st.cache_data(ttl=3600)
def get_full_forecast():
    # Fetching 10 days of swell and wind
    url = "https://marine-api.open-meteo.com/v1/marine?latitude=-36.26&longitude=174.78&hourly=swell_wave_height,swell_wave_period,swell_wave_direction&forecast_days=10&timezone=auto"
    res = requests.get(url).json()
    df = pd.DataFrame(res['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    # Iribarren Logic
    df['wavelength'] = (9.81 * (df['swell_wave_period']**2)) / (2 * np.pi)
    df['xi'] = slope / (np.sqrt(df['swell_wave_height'] / df['wavelength']))
    return df

df = get_full_forecast()

# --- TRAFFIC LIGHT LOGIC ---
def get_color_class(xi, period, direction):
    # 🔵 BLUE: The "Dec 8th" Berm (Long Period + High Iribarren)
    if xi > 1.6 and period > 13:
        return "bg-blue", "🏆 BEST EVER (Dec 8th Berm)"
    
    # 🌀 CYAN: The "Oct 5th" Peeler (North Swell + Rivermouth Bank)
    if direction < 45 and xi > 1.1:
        return "bg-blue", "🌪️ RIVERMOUTH WRAP (Oct 5th Mode)"
    
    # Standard Traffic Lights
    if xi > 1.2: return "bg-darkgreen", "GOLDEN LEDGE"
    if xi > 0.9: return "bg-lightgreen", "GOOD"
    if xi > 0.7: return "bg-yellow", "AVERAGE"
    if xi > 0.4: return "bg-orange", "MUSH"
    return "bg-red", "FLAT"

# --- 10-DAY GRID ---
st.subheader("🗓️ 10-Day Ledge Forecast")

# 1. Update aggregation to include period and direction so the function has them
df['date'] = df['time'].dt.strftime('%a, %b %d')
daily_summary = df.groupby('date').agg({
    'xi': 'max', 
    'swell_wave_height': 'mean', 
    'swell_wave_period': 'max',      # We want the peak period of the day
    'swell_wave_direction': 'mean'   # Average direction for the day
}).reindex(df['date'].unique())

cols = st.columns(5) # Row 1
cols2 = st.columns(5) # Row 2
all_cols = cols + cols2

for i, (date, row) in enumerate(daily_summary.iterrows()):
    # 2. PASS ALL THREE: xi, swell_wave_period, and swell_wave_direction
    color_class, label = get_color_class(row['xi'], row['swell_wave_period'], row['swell_wave_direction'])
    
    with all_cols[i]:
        st.markdown(f"""
            <div class="card {color_class}">
                {date}<br>
                <span style="font-size: 1.5em;">ξ {row['xi']:.2f}</span><br>
                <small>{label}</small>
            </div>
            """, unsafe_allow_html=True)
        st.caption(f"Peak: {row['swell_wave_height']:.1f}m @ {row['swell_wave_period']:.0f}s")

# --- INTERACTIVE CHART ---
st.divider()
st.subheader("📈 Detailed Hourly Trend")
fig = px.area(df, x='time', y='xi', title="Ledge Quality (Iribarren Number)")
fig.add_hline(y=1.2, line_dash="dash", line_color="gold", annotation_text="Golden Zone")
st.plotly_chart(fig, use_container_width=True)
