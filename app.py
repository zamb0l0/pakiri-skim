import streamlit as st
import requests
import pandas as pd
import numpy as np
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

st.title("🌊 Pakiri Skim Forecast - Ledge Specialist")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎛️ Calibration")
    slope = st.slider("Base Beach Slope (tan beta)", 0.02, 0.15, 0.0371, format="%.4f")
    berm_steepness = st.slider("Manual Berm Sculpt", 0.1, 0.5, 0.25)
    
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
    if wind_card in ['NE', 'ENE', 'E', 'ESE', 'SE', 'NNE']:
        score -= 10
        if wind_speed > 15: return "bg-red", "🌪️ CHOPPY ONSHORE"

    if 0.3 <= h <= 0.6: score += 7
    if t >= 11: score += 5
    
    if t >= 13 and xi > 1.2 and wind_card in ['W', 'SW', 'S']: return "bg-blue", "🏆 DEC 8th BERM"
    if score > 20: return "bg-darkgreen", "PREMIUM"
    if score > 15: return "bg-lightgreen", "GOOD"
    if score > 10: return "bg-yellow", "AVERAGE"
    return "bg-red", "WASHED OUT"

# --- LIVE GAUGE ---
now = datetime.now()
idx = (df['time'] - now).abs().idxmin()
now_data = df.loc[idx]
current_bg, current_label = get_expert_score(
    now_data['xi'], now_data['swell_wave_height'], now_data['swell_wave_period'], 
    now_data['swell_wave_direction'], now_data['wind_dir'], now_data['wind_speed'], now_data['tide_level']
)

g_col1, g_col2 = st.columns([2, 1])
with g_col1:
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number", value = now_data['xi'],
        title = {'text': f"Current Ledge Quality (ξ)<br><span style='font-size:0.8em;color:gray'>{current_label}</span>"},
        gauge = {
            'axis': {'range': [0, 2.5]},
            'bar': {'color': "black"},
            'steps': [
                {'range': [0, 0.8], 'color': '#ff4b4b'},
                {'range': [0.8, 1.2], 'color': '#ffa500'},
                {'range': [1.2, 1.8], 'color': '#2ecc71'},
                {'range': [1.8, 2.5], 'color': '#1b5e20'}
            ],
            'threshold': {'line': {'color': "gold", 'width': 4}, 'value': 1.2}
        }
    ))
    fig_gauge.update_layout(height=300, margin=dict(t=50, b=10))
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

# --- THE SIMULATION ENGINE ---
st.subheader("🌀 Pakiri Ledge: Hollow Barrel & Recede")

x_range = np.linspace(0, 60, 300)
y_sand = 4 / (1 + np.exp(-berm_steepness * (x_range - 38)))
y_sand = (y_sand - y_sand.min()) * (slope * 12)
x_poly = np.concatenate([[0], x_range, [60, 0]])

current_tide = now_data['tide_level']
h_s = now_data['swell_wave_height']
xi = now_data['xi']

n_frames = 100
frames = []

for i in range(n_frames):
    t = i / n_frames
    display_y = np.full_like(x_range, current_tide)
    foam_x, foam_y, spray_x, spray_y = [], [], [], []

    if t < 0.6: # STAGES B-G
        progress = t / 0.6
        crest_x = progress * 40 
        phi = np.linspace(0, np.pi * 1.2, 60) 
        shoal_h = h_s * (1 + (crest_x / 40)) 
        lip_throw = (progress**2) * xi * 3.5 
        arc_x = crest_x + np.sin(phi) * shoal_h + (phi * lip_throw * 0.5)
        arc_y = current_tide + (1 - np.cos(phi)) * shoal_h
        wave_influence = np.interp(x_range, arc_x, arc_y, left=current_tide, right=current_tide)
        display_y = np.maximum(display_y, wave_influence)
        
        if now_data['wind_speed'] > 12 and get_cardinal(now_data['wind_dir']) in ['W', 'SW', 'S']:
            spray_x = [crest_x - 1, crest_x - 4]
            spray_y = [current_tide + shoal_h * 1.9, current_tide + shoal_h * 2.1]
        
    elif t < 0.8: # STAGE H
        progress = (t - 0.6) / 0.2
        impact_x = 40
        reach = (h_s * 15 * progress)
        mask = (x_range >= impact_x) & (x_range <= impact_x + reach)
        display_y[mask] = y_sand[mask] + 0.15
        foam_x = [impact_x + reach]
        foam_y = [y_sand[np.abs(x_range - foam_x[0]).argmin()] + 0.1]

    else: # RECEDE
        progress = (t - 0.8) / 0.2
        reach = (h_s * 15) * (1 - progress)
        mask = (x_range >= 40) & (x_range <= 40 + reach)
        display_y[mask] = y_sand[mask] + 0.1

    y_capped = np.maximum(y_sand, display_y)
    y_poly = np.concatenate([[0], y_capped, [0, 0]])

    frames.append(go.Frame(
        data=[
            go.Scatter(x=x_poly, y=np.concatenate([[0], y_sand, [0, 0]]), fill='toself', line=dict(color='#C2B280', width=2), name="Bank"),
            go.Scatter(x=x_poly, y=y_poly, fill='toself', line=dict(color='rgba(41, 128, 185, 0.8)', width=0), name="Ocean"),
            go.Scatter(x=foam_x, y=foam_y, mode='markers', marker=dict(color='white', size=12)),
            go.Scatter(x=spray_x, y=spray_y, mode='lines', line=dict(color='rgba(255,255,255,0.4)', width=2)) if spray_x else go.Scatter(x=[None], y=[None])
        ],
        name=f'f{i}'
    ))

fig_ledge = go.Figure(
    data=frames[0].data,
    layout=go.Layout(
        xaxis=dict(range=[0, 60], showgrid=False, zeroline=False, fixedrange=True),
        yaxis=dict(range=[0, 7], showgrid=False, zeroline=False, fixedrange=True),
        updatemenus=[dict(type="buttons", buttons=[dict(label="🌊 Play Set Loop", method="animate", 
                          args=[None, {"frame": {"duration": 30, "redraw": True}, "fromcurrent": True, "mode": "immediate", "loop": True}])])],
        plot_bgcolor='white', height=400
    ),
    frames=frames
)
st.plotly_chart(fig_ledge, use_container_width=True)

# --- 10-DAY GRID ---
st.subheader("🗓️ 10-Day Skim Forecast")
df['date_label'] = df['time'].dt.strftime('%a, %b %d')
daily = df.groupby('date_label').first().reindex(df['date_label'].unique())
cols = [st.columns(5), st.columns(5)]
for i, (date, row) in enumerate(daily.iterrows()):
    color, label = get_expert_score(row['xi'], row['swell_wave_height'], row['swell_wave_period'], row['swell_wave_direction'], row['wind_dir'], row['wind_speed'], row['tide_level'])
    tide_dt = get_high_tide_dt(row['time'])
    with cols[i//5][i%5]:
        st.markdown(f"""<div class='card {color}'>{date}<br><strong>{label}</strong><br>🌊 {row['swell_wave_height']:.1f}m @ {row['swell_wave_period']:.0f}s<br>ξ {row['xi']:.2f}<br><div class='session-time'>🎯 Best: {(tide_dt - timedelta(hours=1)).strftime('%I:%M')} - {(tide_dt + timedelta(minutes=90)).strftime('%I:%M %p')}</div></div>""", unsafe_allow_html=True)
