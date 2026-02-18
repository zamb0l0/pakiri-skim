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

# --- ANIMATION CONSTANTS ---
n_frames = 100  # <--- Define this to fix the NameError
x_range = np.linspace(0, 60, 300)
x_poly = np.concatenate([[0], x_range, [60, 0]])

# Define the Organic Bank (The Sand)
y_sand = 4 / (1 + np.exp(-0.25 * (x_range - 38)))
y_sand = (y_sand - y_sand.min()) * (slope * 12)

current_tide = now_data['tide_level']
h_s = now_data['swell_wave_height']
xi = now_data['xi']

frames = []

for i in range(n_frames):
    t = i / n_frames
    # display_y starts as a copy of y_sand so water never goes below it
    display_y = np.copy(y_sand)
    foam_x, foam_y, spray_x, spray_y = [], [], [], []

    # --- STAGES B-D: THE SHOAL ---
    if t < 0.35:
        progress = t / 0.35
        crest_x = progress * 35
        for j, x in enumerate(x_range):
            dist = x - crest_x
            wave_height = h_s * (np.exp(0.12 * dist) if dist < 0 else np.exp(-0.5 * dist))
            display_y[j] = np.maximum(y_sand[j], current_tide + wave_height)

    # --- STAGES E-G: THE PLUNGE (The "Throw") ---
    elif t < 0.7:
        progress = (t - 0.35) / 0.35
        crest_x = 35 + (progress * 5)
        for j, x in enumerate(x_range):
            dist = x - crest_x
            wave_height = h_s * (np.exp(0.1 * dist) if dist < 0 else np.exp(-0.7 * dist))
            display_y[j] = np.maximum(y_sand[j], current_tide + wave_height)

        # The Projectile Lip (Stage G) - Curves forward and down
        throw_dist = progress * (xi * 5.5)
        drop = 7.5 * (progress**2) 
        phi = np.linspace(0, np.pi * 0.9, 40)
        spray_x = crest_x + (throw_dist * np.sin(phi/1.3))
        spray_y = (current_tide + h_s) - drop + (h_s * 0.3 * np.cos(phi))
        # Snap spray to sand height if it impacts
        sand_heights = np.interp(spray_x, x_range, y_sand)
        spray_y = np.maximum(spray_y, sand_heights)

    # --- STAGE H: IMPACT & THINNING SWASH ---
    elif t < 0.9:
        progress = (t - 0.7) / 0.2
        impact_x = 40
        swash_reach = (h_s * 15) * np.sin(progress * (np.pi/2))
        mask = (x_range >= impact_x) & (x_range <= impact_x + swash_reach)
        thickness = 0.22 * (1 - progress)
        display_y[mask] = y_sand[mask] + thickness
        
        # Whitewash clusters
        foam_x = np.random.uniform(impact_x - 1, impact_x + swash_reach, 35)
        foam_y = [y_sand[np.abs(x_range - val).argmin()] + 0.25 for val in foam_x]

    # --- THE BACKWASH ---
    else:
        progress = (t - 0.9) / 0.1
        reach = (h_s * 15) * (1 - progress)
        mask = (x_range >= 38) & (x_range <= 40 + reach)
        display_y[mask] = y_sand[mask] + 0.06
        foam_x = np.random.uniform(38, 40 + reach, 15)
        foam_y = [y_sand[np.abs(x_range - val).argmin()] + 0.05 for val in foam_x]

    frames.append(go.Frame(
        data=[
            # Layer 1: The Sandbank (Solid base)
            go.Scatter(x=x_range, y=y_sand, fill='tozeroy', 
                       line=dict(color='#C2B280', width=3), fillcolor='#C2B280', name="Bank"),
            # Layer 2: The Water (Plotted on top of sand)
            go.Scatter(x=x_range, y=display_y, fill='tonexty', 
                       line=dict(color='rgba(41, 128, 185, 0.8)', width=1), fillcolor='rgba(41, 128, 185, 0.6)', name="Ocean"),
            # Layer 3: Foam and Lip
            go.Scatter(x=foam_x, y=foam_y, mode='markers', marker=dict(color='white', size=4, opacity=0.7)),
            go.Scatter(x=spray_x, y=spray_y, mode='lines', line=dict(color='white', width=4)) if len(spray_x) > 0 else go.Scatter(x=[None], y=[None])
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
# fig_barrel chart call removed to prevent NameError

# --- 10-DAY GRID ---
st.subheader("10-Day Skim Forecast")

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
