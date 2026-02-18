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
    if uploaded_file: 
        st.image(uploaded_file)
    
    st.divider()
    st.subheader("📖 What is ξ (Iribarren)?")
    st.write(r"""
    **The Iribarren Number** ($\xi$) describes how waves break based on beach steepness.
    - **High ξ (>1.2):** *Reflective*. Waves bounce off the sand. **This is the Ledge.**
    - **Low ξ (<0.4):** *Dissipative*. Waves crumble far out. **This is Flat.**
    """)
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
    
    # Smooth Tide Approximation (Subtle Sine Wave)
    ref = datetime(2026, 2, 18, 8, 15)
    df['hours_since_ref'] = (df['time'] - ref).dt.total_seconds() / 3600
    # 0.7 amplitude makes the curve smooth and "shorter"
    df['tide_level'] = 0.7 * np.cos(2 * np.pi * (df['hours_since_ref']) / 12.42) + 1.2
    
    return df

df = get_full_data()

# --- HELPERS ---
def get_cardinal(degrees):
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    return dirs[int((degrees + 11.25) / 22.5) % 16]

def get_high_tide(dt_obj):
    ref = datetime(2026, 2, 18, 8, 15)
    days_diff = (dt_obj.replace(tzinfo=None) - ref).days
    tide_dt = ref + timedelta(minutes=days_diff * 50)
    return tide_dt.strftime('%I:%M %p')

def get_expert_score(xi, h, t, swell_dir, wind_deg, wind_speed):
    score = xi * 10
    wind_card = get_cardinal(wind_deg)
    
    if 0.3 <= h <= 0.6: score += 7
    elif 0.6 < h <= 0.9: score += 3
    
    if t >= 11: score += 5
    elif t <= 8: score += 3
    
    if t >= 13 and xi > 1.2: return "bg-blue", "🏆 DEC 8th BERM"
    if swell_dir < 45 and wind_card in ['S', 'SSW', 'SW']: return "bg-blue", "🌪️ RIVERMOUTH WRAP"
    if wind_speed > 25: return "bg-orange", "TOO WINDY"
    
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

# --- SCROLLABLE CHART ---
st.divider()
st.subheader("📈 10-Day Detail: Quality vs Tide")
st.write("*(Scroll sideways on mobile to see the full week)*")

fig = go.Figure()

# 1. Smooth Black Tide Line (Squashed to bottom)
fig.add_trace(go.Scatter(
    x=df['time'], y=df['tide_level'], name="Tide Height", 
    line=dict(color='black', width=1.5, shape='spline'), 
    yaxis="y2"
))

# 2. Quality Line (Bold Gold)
fig.add_trace(go.Scatter(
    x=df['time'], y=df['xi'], name="Quality (ξ)", 
    line=dict(color='#f1c40f', width=5, shape='spline')
))

fig.update_layout(
    hovermode="x unified",
    height=500, width=1800,
    margin=dict(l=50, r=50, t=30, b=30),
    yaxis=dict(title="Quality (ξ)", range=[0, 2]),
    yaxis2=dict(title="Tide", overlaying="y", side="right", range=[0, 5], showgrid=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

fig.add_hline(y=1.2, line_dash="dash", line_color="rgba(0,0,0,0.3)", annotation_text="Ledge Threshold")
# Convert now to a string format Plotly handles better for vlines
# Create a dedicated trace for the "NOW" line to avoid the vline error
fig.add_trace(go.Scatter(
    x=[datetime.now(), datetime.now()],
    y=[0, 2],
    mode="lines+text",
    name="Current Time",
    line=dict(color="red", width=2, dash="solid"),
    text=["", "NOW"],
    textposition="top center",
    showlegend=False
))
st.components.v1.html(
    f'<div style="overflow-x: auto; white-space: nowrap; border-radius: 10px;">{fig.to_html(include_plotlyjs="cdn", full_html=False)}</div>',
    height=550,
)
