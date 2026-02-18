import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Pakiri Ledge Command Center", page_icon="🌊", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .card { padding: 15px; border-radius: 12px; text-align: center; color: white; font-weight: bold; margin-bottom: 10px; min-height: 180px; border: 1px solid rgba(255,255,255,0.1); }
    .bg-red { background-color: #ff4b4b; }
    .bg-orange { background-color: #ffa500; }
    .bg-yellow { background-color: #f1c40f; color: black !important; }
    .bg-lightgreen { background-color: #2ecc71; color: black !important; }
    .bg-darkgreen { background-color: #1b5e20; }
    .bg-blue { background-color: #2980b9; border: 2px solid gold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌊 Pakiri Ledge Command Center")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎛️ Calibration")
    slope = st.slider("Beach Slope (tan beta)", 0.02, 0.15, 0.0371, format="%.4f")
    st.info("Feb 8th Gold Standard: 0.1200")
    
    st.header("📸 Session Log")
    uploaded_file = st.file_uploader("Upload bank photo", type=['jpg', 'png'])
    if uploaded_file: st.image(uploaded_file)
    
    st.divider()
    st.subheader("📖 What is ξ (Iribarren)?")
   st.divider()
    st.subheader("📖 What is ξ (Iribarren)?")
    # Notice the 'r' right before the triple quotes below!
    st.write(r"""
    **The Iribarren Number** ($\xi$) describes how waves break based on beach steepness.
    - **High ξ (>1.2):** *Reflective*. Waves bounce off the sand. **This is the Ledge.**
    - **Low ξ (<0.4):** *Dissipative*. Waves crumble far out. **This is Flat.**
    """)
    # Notice the 'r' here too
    st.write(r"$$\xi = \frac{\tan \beta}{\sqrt{H / L_0}}$$")

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_full_data():
    url = "https://api.open-meteo.com/v1/forecast?latitude=-36.26&longitude=174.78&hourly=wind_speed_10m,wind_direction_10m&forecast_days=10&timezone=auto"
    m_url = "https://marine-api.open-meteo.com/v1/marine?latitude=-36.26&longitude=174.78&hourly=swell_wave_height,swell_wave_period,swell_wave_direction&forecast_days=10&timezone=auto"
    
    w_data = requests.get(url).json()['hourly']
    m_data = requests.get(m_url).json()['hourly']
    
    df = pd.DataFrame(m_data)
    df['wind_speed'] = w_data['wind_speed_10m']
    df['wind_dir'] = w_data['wind_direction_10m']
    df['time'] = pd.to_datetime(df['time'])
    
    # Physics
    df['wavelength'] = (9.81 * (df['swell_wave_period']**2)) / (2 * np.pi)
    df['xi'] = slope / (np.sqrt(df['swell_wave_height'] / df['wavelength']))
    
    # Simple Tide Approximation (Sine wave overlay for the chart)
    ref = datetime(2026, 2, 18, 8, 15)
    df['hours_since_ref'] = (df['time'] - ref).dt.total_seconds() / 3600
    df['tide_level'] = 1.2 * np.cos(2 * np.pi * (df['hours_since_ref']) / 12.4) + 1.2
    
    return df

df = get_full_data()

# --- HELPERS ---
def get_cardinal(degrees):
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    return dirs[int((degrees + 11.25) / 22.5) % 16]

def get_high_tide(dt_obj):
    # Reference Tide: Feb 18, 2026 @ 08:15 AM
    ref = datetime(2026, 2, 18, 8, 15)
    days_diff = (dt_obj.replace(tzinfo=None) - ref).days
    tide_dt = ref + timedelta(minutes=days_diff * 50)
    return tide_dt.strftime('%I:%M %p')

def get_expert_score(xi, h, t, swell_dir, wind_deg, wind_speed):
    score = xi * 10
    wind_card = get_cardinal(wind_deg)
    
    # Height Sweet Spot
    if 0.3 <= h <= 0.6: score += 7
    elif 0.6 < h <= 0.9: score += 3
    
    # Period Logic
    if t >= 11: score += 5
    elif t <= 8: score += 3
    
    # Legend Detection
    if t >= 13 and xi > 1.2: return "bg-blue", "🏆 DEC 8th BERM"
    if swell_dir < 45 and wind_card in ['S', 'SSW', 'SW']: return "bg-blue", "🌪️ RIVERMOUTH WRAP"
    
    # Wind Penalty (If blowing over 25km/h, it ruins the face)
    if wind_speed > 25: return "bg-orange", "TOO WINDY"
    
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
    'wind_dir': 'mean', 'wind_speed': 'max', 'time': 'first'
}).reindex(df['date_label'].unique())

cols = [st.columns(5), st.columns(5)]
for i, (date, row) in enumerate(daily.iterrows()):
    # Pass wind_speed into the expert logic
    color, label = get_expert_score(row['xi'], row['swell_wave_height'], row['swell_wave_period'], row['swell_wave_direction'], row['wind_dir'], row['wind_speed'])
    t_time = get_high_tide(row['time'])
    
    with cols[i//5][i%5]:
        st.markdown(f"""
            <div class='card {color}'>
                {date}<br>
                <span style='font-size:1.1em;'>{label}</span><br>
                <small>{row['swell_wave_height']:.1f}m @ {row['swell_wave_period']:.0f}s</small><br>
                <small>Wind: {row['wind_speed']:.0f}km/h {get_cardinal(row['wind_dir'])}</small><br>
                <small>High Tide: {t_time}</small>
                <hr style='margin:5px 0;'>ξ {row['xi']:.2f}
            </div>
            """, unsafe_allow_html=True)

# --- CHART WITH TIDE OVERLAY ---
st.divider()
st.subheader("📈 Quality Trend + Tide Overlay")
fig = go.Figure()

# Plot 1: Tide Level (Blue Fill)
fig.add_trace(go.Scatter(x=df['time'], y=df['tide_level'], name="Tide Level (m)", fill='tozeroy', line_color='rgba(0, 100, 255, 0.2)'))

# Plot 2: Quality Line (Gold Line)
fig.add_trace(go.Scatter(x=df['time'], y=df['xi'], name="Quality (ξ)", line=dict(color='gold', width=4)))

fig.update_layout(title="Gold Line = Ledge Quality | Blue Area = Tide Height", hovermode="x unified", height=500)
fig.add_hline(y=1.2, line_dash="dash", annotation_text="Ledge Threshold")

st.plotly_chart(fig, use_container_width=True)
