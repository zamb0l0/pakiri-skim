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
    .card { padding: 15px; border-radius: 12px; text-align: center; color: white; font-weight: bold; margin-bottom: 10px; min-height: 220px; border: 1px solid rgba(255,255,255,0.1); }
    .bg-red { background-color: #ff4b4b; }
    .bg-orange { background-color: #ffa500; }
    .bg-yellow { background-color: #f1c40f; color: black !important; }
    .bg-lightgreen { background-color: #2ecc71; color: black !important; }
    .bg-darkgreen { background-color: #1b5e20; }
    .bg-blue { background-color: #2980b9; border: 2px solid gold; }
    .session-time { background: rgba(0,0,0,0.2); border-radius: 5px; padding: 2px 5px; font-size: 0.85em; margin-top: 5px; display: inline-block; }
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
    st.write(r"**The Iribarren Number** ($\xi$) describes how waves break. High $\xi$ (>1.2) means the beach is steep enough for a **Ledge**.")

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
    
    # Smooth Tide Approximation
    ref = datetime(2026, 2, 18, 8, 15)
    df['hours_since_ref'] = (df['time'] - ref).dt.total_seconds() / 3600
    df['tide_level'] = 0.7 * np.cos(2 * np.pi * (df['hours_since_ref']) / 12.42) + 1.2
    
    # DYNAMIC SLOPE: Beach is steeper at high tide
    tide_modifier = (df['tide_level'] - 1.2) / 2
    df['dynamic_slope'] = current_slope * (1 + tide_modifier)
    
    # Physics
    df['wavelength'] = (9.81 * (df['swell_wave_period']**2)) / (2 * np.pi)
    df['xi'] = df['dynamic_slope'] / (np.sqrt(df['swell_wave_height'] / df['wavelength']))
    
    return df

# Helper to define data first
df = get_full_data(slope)

# --- HELPERS ---
def get_cardinal(degrees):
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    return dirs[int((degrees + 11.25) / 22.5) % 16]

def get_arrow_with_name(deg):
    name = get_cardinal(deg)
    arrows = ['↓', '↙', '←', '↖', '↑', '↗', '→', '↘']
    arrow = arrows[int((deg + 22.5) / 45) % 8]
    return f"{name} {arrow}"

def get_high_tide_dt(dt_obj):
    ref = datetime(2026, 2, 18, 8, 15)
    days_diff = (dt_obj.replace(tzinfo=None) - ref).days
    return ref + timedelta(minutes=days_diff * 50)

def get_expert_score(xi, h, t, swell_dir, wind_deg, wind_speed, tide_h):
    score = xi * 10
    if tide_h > 1.6: score += 5
    elif tide_h < 0.8: score -= 5
    
    wind_card = get_cardinal(wind_deg)
    
    # --- INTEGRATED ONSHORE PENALTY ---
    # NE, E, SE winds create chop that ruins the ledge face
    if wind_card in ['NNE', 'NE', 'ENE', 'E', 'ESE', 'SE']:
        score -= 12
        if wind_speed > 15: return "bg-red", "🌪️ CHOPPY ONSHORE"

    if 0.3 <= h <= 0.6: score += 7
    if t >= 11: score += 5
    
    if t >= 13 and xi > 1.2 and wind_card in ['W', 'SW', 'S']: return "bg-blue", "🏆 DEC 8th BERM"
    if swell_dir < 45 and wind_card in ['S', 'SSW', 'SW']: return "bg-blue", "🌪️ RIVERMOUTH WRAP"
    if wind_speed > 25: return "bg-orange", "TOO WINDY"
    
    if score > 20: return "bg-darkgreen", "PREMIUM"
    if score > 15: return "bg-lightgreen", "GOOD"
    if score > 10: return "bg-yellow", "AVERAGE"
    return "bg-red", "WASHED OUT"

# --- LIVE GAUGE SECTION ---
now = datetime.now()
idx = (df['time'] - now).abs().idxmin()
now_data = df.loc[idx]

current_bg, current_label = get_expert_score(
    now_data['xi'], now_data['swell_wave_height'], now_data['swell_wave_period'], 
    now_data['swell_wave_direction'], now_data['wind_dir'], now_data['wind_speed'], now_data['tide_level']
)

fig_gauge = go.Figure(go.Indicator(
    mode = "gauge+number",
    value = now_data['xi'],
    title = {'text': f"Current Ledge Quality (ξ)<br><span style='font-size:0.8em;color:gray'>{current_label}</span>", 'font': {'size': 20}},
    gauge = {
        'axis': {'range': [0, 2.5], 'tickwidth': 1},
        'bar': {'color': "black"},
        'steps': [
            {'range': [0, 0.8], 'color': '#ff4b4b'},
            {'range': [0.8, 1.2], 'color': '#ffa500'},
            {'range': [1.2, 1.8], 'color': '#2ecc71'},
            {'range': [1.8, 2.5], 'color': '#1b5e20'}],
        'threshold': {'line': {'color': "gold", 'width': 4}, 'thickness': 0.75, 'value': 1.2}
    }
))
fig_gauge.update_layout(height=300, margin=dict(t=80, b=20, l=30, r=30))

g_col1, g_col2 = st.columns([2, 1])
with g_col1:
    st.plotly_chart(fig_gauge, use_container_width=True)
with g_col2:
    st.markdown(f"""
        ### Right Now at Pakiri
        **Swell:** {now_data['swell_wave_height']:.1f}m @ {now_data['swell_wave_period']:.0f}s {get_arrow_with_name(now_data['swell_wave_direction'])}  
        **Wind:** {now_data['wind_speed']:.0f}km/h {get_arrow_with_name(now_data['wind_dir'])}  
        **Tide:** {now_data['tide_level']:.1f}m  
        **Session:** {current_label}
    """)
st.divider()

import numpy as np
import plotly.graph_objects as go
import streamlit as st

# --- 1. SETUP ---
# Slowed down: 120 frames at 50ms = 6 second cycle
n_frames = 120 
x_base = np.linspace(0, 60, 200)

# The Bank (Static)
y_sand = 4 / (1 + np.exp(-0.25 * (x_base - 42)))
y_sand = (y_sand - y_sand.min()) * (slope * 12)

h_s = now_data['swell_wave_height']
xi = now_data['xi'] 
tide = now_data['tide_level']

frames = []

for i in range(n_frames):
    t = i / n_frames
    
    # We build a single closed loop for the water
    path_x = []
    path_y = []

    # --- STAGES B-D: THE ROUND LUMP (0.0 - 0.4) ---
    if t < 0.4:
        p = t / 0.4
        crest_x = p * 40
        amp = h_s * (1 + p * 0.5)
        # Rounder lump using Gaussian curve
        width = 8 - (p * 4) 
        
        # Build surface
        surface_x = list(x_base)
        surface_y = [max(y_sand[j], tide + amp * np.exp(-((x - crest_x)**2) / (2 * width**2))) 
                     for j, x in enumerate(x_base)]
        path_x, path_y = surface_x, surface_y

    # --- STAGES E-G: THE PITCHING BARREL (0.4 - 0.75) ---
    elif t < 0.75:
        p = (t - 0.4) / 0.35
        crest_x = 40 + (p * 5)
        amp = h_s * 1.6
        
        # 1. Back of wave
        back_x = np.linspace(0, crest_x, 80)
        back_y = [max(np.interp(x, x_base, y_sand), tide + amp * np.exp(-((x - crest_x)**2) / (2 * 6**2))) 
                  for x in back_x]
        
        # 2. The Overhanging Lip (The 'C' Curve)
        # Higher Iribarren (xi) = More 'Throw' forward
        throw = p * (xi * 6)
        drop = 8 * (p**1.8)
        phi = np.linspace(0, np.pi * 1.1, 40) # This creates the loop
        r = (h_s * 0.7) # Radius of the barrel
        
        lip_x = crest_x + (throw) + r * np.sin(phi)
        lip_y = (tide + amp) - drop + r * np.cos(phi)
        
        # 3. Connection to shore
        shore_x = np.linspace(max(lip_x), 60, 80)
        shore_y = [np.interp(x, x_base, y_sand) for x in shore_x]
        
        path_x = list(back_x) + list(lip_x) + list(shore_x)
        path_y = list(back_y) + list(lip_y) + list(shore_y)

    # --- STAGE H: REFLECTION & SWASH (0.75 - 1.0) ---
    else:
        p = (t - 0.75) / 0.25
        impact_x = 42
        # Surge and Reflect
        reach = (h_s * 15) * np.sin(p * np.pi)
        
        path_x = list(x_base)
        path_y = []
        for j, x in enumerate(x_base):
            if x < impact_x:
                path_y.append(max(y_sand[j], tide + (h_s * 0.1 * (1-p))))
            elif impact_x <= x <= impact_x + reach:
                path_y.append(y_sand[j] + (0.3 * (1-p))) # Thin swash sheet
            else:
                path_y.append(y_sand[j])

    # --- CLOSE THE POLYGON (Avoid water under sand) ---
    # We go from the end of the surface, down to 0, back to start, and up
    full_x = path_x + [60, 0]
    full_y = path_y + [0, 0]

    frames.append(go.Frame(
        data=[
            # Sand Layer (Drawn first)
            go.Scatter(x=list(x_base) + [60, 0], y=list(y_sand) + [0, 0], fill='toself', 
                       fillcolor='#C2B280', line=dict(color='#A68D60', width=1), hoverinfo='skip'),
            # Water Layer (Drawn on top)
            go.Scatter(x=full_x, y=full_y, fill='toself', 
                       fillcolor='rgba(0, 105, 148, 0.7)', line=dict(color='#006994', width=2), hoverinfo='skip')
        ],
        name=f'f{i}'
    ))

# --- RENDER ---
fig_ledge = go.Figure(
    data=frames[0].data,
    layout=go.Layout(
        xaxis=dict(range=[0, 60], fixedrange=True, showgrid=False, zeroline=False),
        yaxis=dict(range=[0, 9], fixedrange=True, showgrid=False, zeroline=False),
        updatemenus=[{"type": "buttons", "buttons": [{"label": "🌊 Play Ledge Cycle", "method": "animate", 
                     "args": [None, {"frame": {"duration": 50, "redraw": False}, "fromcurrent": True}]}]}],
        plot_bgcolor='white', height=450, margin=dict(l=0, r=0, t=0, b=0)
    ),
    frames=frames
)

st.plotly_chart(fig_ledge, use_container_width=True)

# --- SCROLLABLE CHART ---
st.divider()
st.subheader("📈 10-Day Detail: Quality vs Tide")

fig = go.Figure()
fig.add_trace(go.Scatter(x=df['time'], y=df['tide_level'], name="Tide", line=dict(color='black', width=1.5, shape='spline'), yaxis="y2"))
fig.add_trace(go.Scatter(x=df['time'], y=df['xi'], name="Quality", line=dict(color='#f1c40f', width=5, shape='spline')))

fig.update_layout(
    hovermode="x unified", height=500, width=1800,
    yaxis=dict(title="Quality (ξ)", range=[0, 2.5]),
    yaxis2=dict(title="Tide", overlaying="y", side="right", range=[0, 5], showgrid=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

fig.add_hline(y=1.2, line_dash="dash", line_color="rgba(0,0,0,0.3)", annotation_text="Ledge Threshold")
fig.add_trace(go.Scatter(x=[datetime.now(), datetime.now()], y=[0, 2], mode="lines+text", text=["", "NOW"], textposition="bottom center", line=dict(color="red", width=2), showlegend=False))

st.components.v1.html(f'<div style="overflow-x: auto; white-space: nowrap; border-radius: 10px;">{fig.to_html(include_plotlyjs="cdn", full_html=False)}</div>', height=550)
