import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pakiri Ledge Command Center", page_icon="🌊", layout="wide")

st.markdown("""
    <style>
    .card { padding: 15px; border-radius: 12px; text-align: center; color: white; font-weight: bold; margin-bottom: 10px; min-height: 270px; border: 1px solid rgba(255,255,255,0.1); transition: transform 0.2s; }
    .card:hover { transform: scale(1.02); }
    .bg-red { background-color: #ff4b4b; }
    .bg-orange { background-color: #ffa500; }
    .bg-yellow { background-color: #f1c40f; color: black !important; }
    .bg-lightgreen { background-color: #2ecc71; color: black !important; }
    .bg-darkgreen { background-color: #1b5e20; border: 2px solid gold; }
    .bg-blue { background-color: #2980b9; border: 2px solid gold; }
    .bg-purple { background-color: #8e44ad; border: 2px solid #ff00ff; }
    .session-time { background: rgba(0,0,0,0.2); border-radius: 5px; padding: 2px 5px; font-size: 0.85em; margin-top: 10px; display: inline-block; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pakiri Skim Forecast - Beach Gradient Inclusive")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎛️ Calibration")
    slope = st.slider("Base Beach Slope (tan beta)", 0.02, 0.15, 0.0371, format="%.4f")
    st.info("Dynamic slope is currently syncing with the tide cycle.")
    
    st.header("📸 Session Log")
    uploaded_file = st.file_uploader("Upload bank photo", type=['jpg', 'png'])
    if uploaded_file: st.image(uploaded_file)
    
    st.divider()
    st.subheader("📖 What is ξ (Iribarren)?")
    st.write(r"**The Iribarren Number** ($\xi$) describes how waves break. High $\xi$ (>1.5) means the beach is steep enough for a **Premium Ledge**.")

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_full_data(current_slope):
    url = "https://api.open-meteo.com/v1/forecast?latitude=-36.26&longitude=174.78&hourly=wind_speed_10m,wind_direction_10m&forecast_days=10&timezone=auto"
    m_url = "https://marine-api.open-meteo.com/v1/marine?latitude=-36.26&longitude=174.78&hourly=swell_wave_height,swell_wave_period,swell_wave_direction&forecast_days=10&timezone=auto"
    w_data = requests.get(url).json()['hourly']
    m_data = requests.get(m_url).json()['hourly']
    df = pd.DataFrame(m_data)
    df['wind_speed'] = w_data['wind_speed_10m']
    df['wind_dir'] = w_data['wind_direction_10m']
    df['time'] = pd.to_datetime(df['time'])
    ref = datetime(2026, 2, 18, 8, 15)
    df['hours_since_ref'] = (df['time'] - ref).dt.total_seconds() / 3600
    df['tide_level'] = 0.7 * np.cos(2 * np.pi * (df['hours_since_ref']) / 12.42) + 1.2
    tide_modifier = (df['tide_level'] - 1.2) / 2
    df['dynamic_slope'] = current_slope * (1 + tide_modifier)
    df['wavelength'] = (9.81 * (df['swell_wave_period']**2)) / (2 * np.pi)
    df['xi'] = df['dynamic_slope'] / (np.sqrt(df['swell_wave_height'] / df['wavelength']))
    return df

df = get_full_data(slope)

# --- HELPERS ---
def get_cardinal(degrees):
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    return dirs[int((degrees + 11.25) / 22.5) % 16]

def get_arrow_with_name(deg):
    name = get_cardinal(deg)
    arrows = ['↓', '↙', '←', '↖', '↑', '↗', '→', '↘']
    return f"{name} {arrows[int((deg + 22.5) / 45) % 8]}"

def get_high_tide_dt(dt_obj):
    ref = datetime(2026, 2, 18, 8, 15)
    days_diff = (dt_obj.replace(tzinfo=None) - ref).days
    return ref + timedelta(minutes=days_diff * 50)

def get_expert_score(xi, h, t, wind_deg, wind_speed, tide_h):
    if wind_speed > 35: return "bg-purple", "⚠️ DANGER WIND"
    score = xi * 10
    if tide_h > 1.6: score += 5
    elif tide_h < 0.8: score -= 5
    
    wind_card = get_cardinal(wind_deg)
    if wind_card in ['NNE', 'NE', 'ENE', 'E', 'ESE', 'SE']:
        score -= 12
        if wind_speed > 15: return "bg-red", "🌪️ CHOPPY ONSHORE"
    
    if 0.3 <= h <= 0.6: score += 7
    if t >= 11: score += 5
    if t >= 13 and xi > 1.4 and wind_card in ['W', 'SW', 'S']: return "bg-blue", "🏆 DEC 8th BERM"
    if wind_speed > 25: return "bg-orange", "TOO WINDY"
    
    if xi > 1.5 and score > 20: return "bg-darkgreen", "PREMIUM"
    if xi > 1.2: return "bg-lightgreen", "GOOD"
    if xi > 0.8: return "bg-yellow", "AVERAGE"
    return "bg-red", "WASHED OUT"

# --- LIVE GAUGE SECTION ---
now = datetime.now()
idx = (df['time'] - now).abs().idxmin()
now_data = df.loc[idx]
current_bg, current_label = get_expert_score(
    now_data['xi'], now_data['swell_wave_height'], now_data['swell_wave_period'], 
    now_data['wind_dir'], now_data['wind_speed'], now_data['tide_level']
)

g_col1, g_col2 = st.columns([2, 1])
with g_col1:
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number", value = now_data['xi'],
        title = {'text': f"Current Ledge Quality (ξ)<br><span style='font-size:0.8em;color:gray'>{current_label}</span>", 'font': {'size': 24}},
        gauge = {'axis': {'range': [0, 2.5]}, 'bar': {'color': "black"},
                 'steps': [{'range': [0, 0.8], 'color': '#ff4b4b'}, {'range': [0.8, 1.2], 'color': '#ffa500'},
                           {'range': [1.2, 1.5], 'color': '#2ecc71'}, {'range': [1.5, 2.5], 'color': '#1b5e20'}]}
    ))
    # Margin fix for Gauge Title
    fig_gauge.update_layout(height=400, margin=dict(t=120, b=20, l=30, r=30))
    st.plotly_chart(fig_gauge, use_container_width=True)

with g_col2:
    st.markdown(f"### Right Now at Pakiri\n**Swell:** {now_data['swell_wave_height']:.1f}m @ {now_data['swell_wave_period']:.0f}s {get_arrow_with_name(now_data['swell_wave_direction'])}\n**Wind:** {now_data['wind_speed']:.0f}km/h {get_arrow_with_name(now_data['wind_dir'])}\n**Tide:** {now_data['tide_level']:.1f}m\n**Session:** {current_label}")

st.divider()

# --- P5.JS FLUID CANVAS ---
st.subheader("🌊 Real-Time Fluid Dynamics (Pakiri Ledge)")
canvas_html = f"""
<script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.4.0/p5.js"></script>
<div id="canvas-container" style="width: 100%; text-align: center; background: white; border-radius: 15px; border: 1px solid #eee;"></div>
<script>
let hs = {float(now_data['swell_wave_height'])};
let xi = {float(now_data['xi'])};
let tide = {float(now_data['tide_level'])};
let slope = {float(slope)};

function setup() {{
  var canvas = createCanvas(windowWidth * 0.95, 350);
  canvas.parent('canvas-container');
}}

function draw() {{
  background(255);
  let time = frameCount * 0.02;
  fill(194, 178, 128); noStroke();
  beginShape();
  vertex(0, height);
  for (let x = 0; x <= width; x += 10) {{
    let sandY = height - (20 + (1 / (1 + exp(-0.02 * (x - width*0.7)))) * (slope * 2500));
    vertex(x, sandY);
  }}
  vertex(width, height);
  endShape(CLOSE);

  push();
  fill(0, 105, 148, 180); stroke(255); strokeWeight(1);
  beginShape();
  vertex(0, height);
  for (let x = 0; x <= width; x += 5) {{
    let progress = (x / width);
    let cycle = (time - progress * 4) % TWO_PI;
    let localAmp = (hs * 40) * (1 + (max(0, x - width * 0.4) * 0.003));
    let xOffset = (sin(cycle) > 0.4 && xi > 1.1) ? pow(sin(cycle), 3) * (xi * 20) : 0;
    let y = (height - 120) - (tide * 20) + sin(cycle) * localAmp;
    let sandY = height - (20 + (1 / (1 + exp(-0.02 * (x - width*0.7)))) * (slope * 2500));
    vertex(x + xOffset, min(y, sandY));
  }}
  vertex(width, height);
  endShape(CLOSE);
  pop();
}}
</script>
"""
components.html(canvas_html, height=370)

# --- 10-DAY GRID ---
st.subheader("🗓️ 10-Day Skim Forecast")

df['date_label'] = df['time'].dt.strftime('%a, %b %d')
daily = df.groupby('date_label').agg({
    'xi': 'max', 'swell_wave_height': 'mean', 
    'swell_wave_period': 'max', 'swell_wave_direction': 'mean',
    'wind_dir': 'mean', 'wind_speed': 'max', 'time': 'first', 'tide_level': 'max'
}).reindex(df['date_label'].unique())

cols = [st.columns(5), st.columns(5)]
for i, (date, row) in enumerate(daily.iterrows()):
    color, label = get_expert_score(row['xi'], row['swell_wave_height'], row['swell_wave_period'], row['swell_wave_direction'], row['wind_dir'], row['wind_speed'], row['tide_level'])
    tide_dt = get_high_tide_dt(row['time'])
    session_start = (tide_dt - timedelta(hours=1)).strftime('%I:%M')
    session_end = (tide_dt + timedelta(minutes=90)).strftime('%I:%M %p')

    with cols[i//5][i%5]:
        st.markdown(f"""
            <div class='card {color}'>
                <div style='font-size: 0.85em; opacity: 0.8;'>{date}</div>
                <div style='font-size: 1.2em; margin: 4px 0;'><strong>{label}</strong></div>
                <div style='font-size: 1.0em;'>🌊 <b>{row['swell_wave_height']:.1f}m</b> @ {row['swell_wave_period']:.0f}s</div>
                <div style='font-size: 0.85em; opacity: 0.9;'>Swell: {get_arrow_with_name(row['swell_wave_direction'])}</div>
                <div style='font-size: 0.85em; opacity: 0.9;'>Wind: {get_arrow_with_name(row['wind_dir'])}</div>
                <div class='session-time'>🎯 Best: {session_start} - {session_end}</div>
                <hr style='margin:8px 0; border: 0.5px solid rgba(255,255,255,0.2);'>
                <div style='font-size: 1.1em;'>ξ {row['xi']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)

# --- CHART ---
st.divider()
st.subheader("📈 Quality vs Tide")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df['time'], y=df['tide_level'], name="Tide", line=dict(color='black', width=1), yaxis="y2"))
fig.add_trace(go.Scatter(x=df['time'], y=df['xi'], name="Quality", line=dict(color='#f1c40f', width=4)))
fig.update_layout(height=400, width=1500, yaxis=dict(title="Quality", range=[0, 2.5]), yaxis2=dict(overlaying="y", side="right", range=[0, 5]))
st.plotly_chart(fig, use_container_width=True)
