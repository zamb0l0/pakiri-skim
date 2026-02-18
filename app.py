import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Pakiri Ledge Command Center", page_icon="🌊", layout="wide")

# --- CUSTOM CSS FOR TRAFFIC LIGHTS ---
st.markdown("""
    <style>
    .card { padding: 20px; border-radius: 12px; text-align: center; color: white; font-weight: bold; margin-bottom: 10px; min-height: 150px; }
    .bg-red { background-color: #ff4b4b; }
    .bg-orange { background-color: #ffa500; }
    .bg-yellow { background-color: #f4d03f; color: black !important; }
    .bg-lightgreen { background-color: #58d68d; color: black !important; }
    .bg-darkgreen { background-color: #1d8348; }
    .bg-blue { background-color: #2e86c1; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌊 Pakiri Ledge Command Center")

# --- SIDEBAR & CALIBRATION ---
with st.sidebar:
    st.header("🎛️ Calibration")
    slope = st.slider("Beach Slope (tan beta)", 0.02, 0.15, 0.0371, format="%.4f")
    st.info("Feb 8th Gold Standard: 0.1200")
    st.header("📸 Session Log")
    uploaded_file = st.file_uploader("Upload bank photo", type=['jpg', 'png'])
    if uploaded_file: st.image(uploaded_file)

# --- DATA FETCHING (WAVES + WIND) ---
@st.cache_data(ttl=3600)
def get_full_forecast():
    # Adding wind speed and direction to the API call
    url = "https://api.open-meteo.com/v1/forecast?latitude=-36.26&longitude=174.78&hourly=wind_speed_10m,wind_direction_10m&forecast_days=10&timezone=auto"
    marine_url = "https://marine-api.open-meteo.com/v1/marine?latitude=-36.26&longitude=174.78&hourly=swell_wave_height,swell_wave_period,swell_wave_direction&forecast_days=10&timezone=auto"
    
    w_data = requests.get(url).json()['hourly']
    m_data = requests.get(marine_url).json()['hourly']
    
    df = pd.DataFrame(m_data)
    df['wind_speed'] = w_data['wind_speed_10m']
    df['wind_dir'] = w_data['wind_direction_10m']
    df['time'] = pd.to_datetime(df['time'])
    
    # Physics: Iribarren
    df['wavelength'] = (9.81 * (df['swell_wave_period']**2)) / (2 * np.pi)
    df['xi'] = slope / (np.sqrt(df['swell_wave_height'] / df['wavelength']))
    return df

df = get_full_forecast()

# --- HELPER: DEGREES TO CARDINAL ---
def get_cardinal(degrees):
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    idx = int((degrees + 11.25) / 22.5) % 16
    return dirs[idx]

# --- EXPERT SCORING LOGIC ---
def get_expert_score(xi, h, t, swell_dir, wind_deg):
    score = xi * 10
    wind_cardinal = get_cardinal(wind_deg)
    
    # Height Bonus (Your Goldilocks Zone)
    if 0.3 <= h <= 0.6: score += 7
    elif 0.6 < h <= 0.9: score += 3
    
    # Period Bonus
    if t >= 11: score += 5
    elif t <= 8: score += 3
    
    # Legend Mode Detection
    if t >= 13 and xi > 1.2: return "bg-blue", "🏆 DEC 8th BERM"
    if swell_dir < 45 and wind_cardinal in ['S', 'SSW', 'SW']: return "bg-blue", "🌪️ RIVERMOUTH WRAP"
    
    # Traffic Lights
    if score > 18: return "bg-darkgreen", "PREMIUM"
    if score > 14: return "bg-lightgreen", "GOOD"
    if score > 10: return "bg-yellow", "AVERAGE"
    if score > 6: return "bg-orange", "MUSH"
    return "bg-red", "WASHED OUT"

# --- 10-DAY GRID ---
st.subheader("🗓️ 10-Day Skim Forecast")
df['date_label'] = df['time'].dt.strftime('%a, %b %d')
daily = df.groupby('date_label').agg({
    'xi': 'max', 'swell_wave_height': 'mean', 
    'swell_wave_period': 'max', 'swell_wave_direction': 'mean',
    'wind_dir': 'mean'
}).reindex(df['date_label'].unique())

rows = [st.columns(5), st.columns(5)]
for i, (date, row) in enumerate(daily.iterrows()):
    color, label = get_expert_score(row['xi'], row['swell_wave_height'], row['swell_wave_period'], row['swell_wave_direction'], row['wind_dir'])
    with rows[i//5][i%5]:
        st.markdown(f"<div class='card {color}'>{date}<br><span style='font-size:1.4em;'>{label}</span><br>ξ {row['xi']:.2f}</div>", unsafe_allow_html=True)

# --- CHART ---
st.divider()
fig = px.area(df, x='time', y='xi', title="Hourly Ledge Quality Trend")
fig.add_hline(y=1.2, line_dash="dash", line_color="gold", annotation_text="Ledge Threshold")
st.plotly_chart(fig, use_container_width=True)
