import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# --- PAKIRI METADATA ---
LAT = -36.264
LON = 174.721
SURFLINE_URL = "https://www.surfline.com/surf-report/pakiri/617874e830bff6bfe69db04e"
WINDFINDER_URL = "https://www.windfinder.com/forecast/pakiri"

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pakiri Ledge Command Center", page_icon="🌊", layout="wide")

st.markdown(r"""
    <style>
    .card { padding: 15px; border-radius: 12px; text-align: center; color: white; font-weight: bold; margin-bottom: 10px; min-height: 280px; border: 1px solid rgba(255,255,255,0.1); transition: transform 0.2s; }
    .card:hover { transform: scale(1.02); }
    .bg-red { background-color: #ff4b4b; }
    .bg-orange { background-color: #ffa500; }
    .bg-yellow { background-color: #f1c40f; color: black !important; }
    .bg-lightgreen { background-color: #2ecc71; color: black !important; }
    .bg-darkgreen { background-color: #1b5e20; border: 2px solid gold; }
    .bg-blue { background-color: #2980b9; border: 2px solid gold; }
    .bg-purple { background-color: #8e44ad; border: 2px solid #ff00ff; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pakiri Ledge Command Center")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎛️ Calibration")
    slope = st.slider("Base Beach Slope (tan beta)", 0.02, 0.15, 0.0371, format="%.4f")
    st.info("Tide is calibrated to 2.4m Local Peak.")
    
    st.header("📸 Session Log")
    uploaded_file = st.file_uploader("Upload bank photo", type=['jpg', 'png'])
    if uploaded_file: st.image(uploaded_file)

# --- DROP LOGIC ENGINE ---
def get_drop_logic(xi, period):
    """Determines strategy based on drainage: Steepness vs Period."""
    if xi > 1.4:
        if period > 10:
            return "⏳ SAND DROP", "🏜️", "Full drainage. Drop on wet sand."
        else:
            return "⚡ QUICK SAND", "🏃", "Fast suck-back. High tempo."
    else:
        if period > 9:
            return "🌊 WATER DROP", "🏄", "Gliding. Catch the rush up."
        else:
            return "🌀 WASHY WATER", "🌊", "Constant flood. High friction."

# --- WIND RULES ---
def get_wind_multiplier(deg, speed):
    if not (135 <= deg <= 315):
        dir_mult = 0.5 
    else:
        offshore_error = abs(deg - 225)
        dir_mult = 1.2 - (offshore_error / 450)
    if speed < 5: speed_mult = 1.3
    elif speed < 12: speed_mult = 1.0
    elif speed > 25: speed_mult = 0.6
    else: speed_mult = 0.8
    return dir_mult * speed_mult

@st.cache_data(ttl=3600)
def get_full_data(current_slope):
    w_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=wind_speed_10m,wind_direction_10m&forecast_days=10&timezone=auto"
    m_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={LAT}&longitude={LON}&hourly=swell_wave_height,swell_wave_period,swell_wave_direction&forecast_days=10&timezone=auto"
    
    w_data = requests.get(w_url).json()['hourly']
    m_data = requests.get(m_url).json()['hourly']
    df = pd.DataFrame(m_data)
    df['wind_speed'] = w_data['wind_speed_10m']
    df['wind_dir'] = w_data['wind_direction_10m']
    df['time'] = pd.to_datetime(df['time'])
    
    # Tide Calibration (2.4m Peak)
    ref = datetime(2026, 2, 18, 8, 15)
    df['hours_since_ref'] = (df['time'] - ref).dt.total_seconds() / 3600
    df['tide_level'] = 0.7 * np.cos(2 * np.pi * (df['hours_since_ref']) / 12.42) + 1.7
    
    tide_modifier = (df['tide_level'] - 1.7) / 2
    df['dynamic_slope'] = current_slope * (1 + tide_modifier)
    df['wavelength'] = (9.81 * (df['swell_wave_period']**2)) / (2 * np.pi)
    df['xi_raw'] = df['dynamic_slope'] / (np.sqrt(df['swell_wave_height'] / df['wavelength']))
    df['wind_mult'] = df.apply(lambda x: get_wind_multiplier(x['wind_dir'], x['wind_speed']), axis=1)
    df['xi'] = df['xi_raw'] * df['wind_mult']
    df['R'] = (df['xi']**2) / (df['xi']**2 + 5) * 100
    df['steepness'] = df['swell_wave_height'] / df['wavelength']
    df['date_label'] = df['time'].dt.strftime('%a, %b %d')
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

def get_expert_score(xi, h, t, wind_deg, wind_speed, tide_h):
    if wind_speed > 35: return "bg-purple", "⚠️ DANGER WIND"
    is_glassy = wind_speed < 5 and (135 <= wind_deg <= 315)
    if xi > 1.6: return "bg-darkgreen", ("💎 MINT GLASS" if is_glassy else "PREMIUM")
    if xi > 1.2: return "bg-lightgreen", "GOOD"
    if xi > 0.8: return "bg-yellow", "AVERAGE"
    if not (135 <= wind_deg <= 315): return "bg-red", "🌪️ CHOPPY ONSHORE"
    return "bg-red", "WASHED OUT"

# --- LIVE GAUGE ---
now = datetime.now()
idx = (df['time'] - now).abs().idxmin()
now_data = df.loc[idx]
current_bg, current_label = get_expert_score(now_data['xi'], now_data['swell_wave_height'], now_data['swell_wave_period'], now_data['wind_dir'], now_data['wind_speed'], now_data['tide_level'])

g_col1, g_col2 = st.columns([2, 1])
with g_col1:
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number", value = now_data['xi'],
        title = {'text': f"Ledge Quality (ξ)<br><span style='font-size:0.8em;color:gray'>{current_label}</span>"},
        gauge = {'axis': {'range': [0, 2.5]}, 'bar': {'color': "black"},
                 'steps': [{'range': [0, 0.8], 'color': '#ff4b4b'}, {'range': [0.8, 1.2], 'color': '#ffa500'},
                           {'range': [1.2, 1.5], 'color': '#2ecc71'}, {'range': [1.5, 2.5], 'color': '#1b5e20'}]}
    ))
    st.plotly_chart(fig_gauge, use_container_width=True)

with g_col2:
    st.markdown(f"### Live at Pakiri\n**Swell:** {now_data['swell_wave_height']:.1f}m @ {now_data['swell_wave_period']:.0f}s\n**Wind:** {now_data['wind_speed']:.0f}km/h {get_arrow_with_name(now_data['wind_dir'])}\n**Tide:** {now_data['tide_level']:.1f}m\n**Steepness:** {now_data['steepness']:.3f}")

# --- VISUALS: DAILY PROFILE COMPARISON ---
def get_extreme_profile(slope_val, xi_val):
    x_p = np.linspace(10, 100, 150)
    mu = 90 - (slope_val * 90) 
    sigma = 25 / (xi_val ** 3.0) 
    y = 3.6 * np.exp(-((x_p - mu)**2) / (2 * sigma**2))
    y = np.where(x_p > mu, 3.6 + (0.012 * (x_p - mu)), y)
    return y, mu

st.divider()
st.subheader("📐 Daily Beach Profile & Drop Strategy")
daily_geom = df.groupby('date_label').agg({
    'xi':'max', 'tide_level':'max', 'dynamic_slope':'max', 
    'swell_wave_height':'mean', 'swell_wave_period':'mean', 
    'wavelength':'mean', 'R':'max', 'steepness':'mean'
}).reindex(df['date_label'].unique())

g_cols = [st.columns(5), st.columns(5)]
x_vals = np.linspace(10, 100, 150)

for i, (date, row) in enumerate(daily_geom.iterrows()):
    if pd.isna(row['xi']): continue
    with g_cols[i//5][i%5]:
        y_vals, ledge_x = get_extreme_profile(row['dynamic_slope'], row['xi'])
        drop_mode, drop_emoji, drop_desc = get_drop_logic(row['xi'], row['swell_wave_period'])
        
        fig_mini = go.Figure()
        fig_mini.add_trace(go.Scatter(x=x_vals, y=y_vals, fill='tozeroy', mode='lines',
            line=dict(width=3, color='#2ecc71', shape='spline', smoothing=1.3),
            fillcolor='rgba(46, 204, 113, 0.2)', hoverinfo='none'))

        fig_mini.add_trace(go.Scatter(x=[10, 100], y=[row['tide_level'], row['tide_level']],
            line=dict(color='rgba(52, 152, 219, 0.5)', width=2), mode='lines'))
        
        # Dimension & Drop Label
        fig_mini.add_trace(go.Scatter(x=[15, 15], y=[0, row['tide_level']], mode='lines', line=dict(color='#2c3e50', width=1)))
        fig_mini.add_annotation(x=55, y=0.6, text=f"<b>{drop_emoji} {drop_mode}</b>", showarrow=False, 
                                font=dict(size=9, family="monospace", color="white"), bgcolor="rgba(0,0,0,0.6)", borderpad=4)

        fig_mini.update_layout(height=260, margin=dict(l=0, r=0, t=50, b=0), title={'text': f"<b>{date}</b>", 'x': 0.5},
            xaxis=dict(visible=False), yaxis=dict(range=[0, 6.0], visible=False), showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')

        st.plotly_chart(fig_mini, use_container_width=True, config={'displayModeBar': False})
        st.markdown(f"<div style='text-align:center; font-size:10px; color:#95a5a6; font-style:italic;'>{drop_desc}</div>", unsafe_allow_html=True)

# --- 10-DAY FORECAST CARDS ---
st.subheader("🗓️ 10-Day Skim Forecast")
cols = [st.columns(5), st.columns(5)]

for i, (date, row) in enumerate(daily_geom.iterrows()):
    day_data = df[df['date_label'] == date]
    if day_data.empty: continue
    
    d_row = day_data.iloc[day_data['xi'].argmax()]
    color, label = get_expert_score(d_row['xi'], d_row['swell_wave_height'], d_row['swell_wave_period'], d_row['wind_dir'], d_row['wind_speed'], d_row['tide_level'])
    drop_m, _, _ = get_drop_logic(d_row['xi'], d_row['swell_wave_period'])
    wind_info = f"{d_row['wind_speed']:.0f}km/h {get_arrow_with_name(d_row['wind_dir'])}"
    best_time = d_row['time'].strftime('%I:%M %p')

    # FIX: No leading spaces in the HTML string prevents the "Code Box" look
    card_html = f"""<div class='card {color}'>
<div style='font-size: 0.8em; opacity: 0.8;'>{date}</div>
<div style='font-size: 1.1em; margin: 2px 0;'><strong>{label}</strong></div>
<div style='font-size: 0.85em; margin-bottom: 8px; color: #f1c40f; font-weight: bold;'>{drop_m}</div>
<div style='font-size: 0.95em;'>🌊 <b>{d_row['swell_wave_height']:.1f}m</b> @ {d_row['swell_wave_period']:.0f}s</div>
<div style='font-size: 0.85em; opacity: 0.9; margin-top: 2px;'>💨 {wind_info}</div>
<div style='background: rgba(0,0,0,0.3); padding: 2px 8px; border-radius: 4px; margin: 8px auto; font-size: 0.8em; width: fit-content;'>Best Window: {best_time}</div>
<hr style='margin:10px 0; border: 0.5px solid rgba(255,255,255,0.2);'>
<div style='font-size: 1.0em;'>ξ {d_row['xi']:.2f} | R {d_row['R']:.0f}%</div>
<div style='font-size: 0.75em; opacity: 0.7; margin-top: 4px;'>Tide at peak: {d_row['tide_level']:.1f}m</div>
</div>"""

    with cols[i//5][i%5]:
        st.markdown(card_html, unsafe_allow_html=True)

# --- TREND CHART ---
st.divider()
st.subheader("📈 Quality vs Tide Trend")
fig_trend = go.Figure()
fig_trend.add_trace(go.Scatter(x=df['time'], y=df['tide_level'], name="Tide", line=dict(color='black', width=1), yaxis="y2"))
fig_trend.add_trace(go.Scatter(x=df['time'], y=df['xi'], name="Quality", line=dict(color='#f1c40f', width=4)))
fig_trend.update_layout(height=400, width=1500, yaxis=dict(title="Quality", range=[0, 2.5]), yaxis2=dict(overlaying="y", side="right", range=[0, 5]))
st.plotly_chart(fig_trend, use_container_width=True)

# --- TECHNICAL DOCUMENTATION ---
with st.expander("🔬 How the Pakiri Ledge Engine Works"):
    st.markdown("### 🛰️ The Data Pipeline: From Ocean to Forecast")
    doc_col1, doc_col2 = st.columns([1, 1])
    with doc_col1:
        st.markdown(r"""
        **1. Raw Data Acquisition**
        Pulling live data for coordinates ($36.26^\circ S, 174.72^\circ E$):
        * **GFS:** Wind speed and direction (matches Windfinder).
        * **MeteoFrance:** Swell heights and periods (matches Surfline).

        **2. The Pakiri Transformation**
        * **Wavelength ($L$):** $L = \frac{g \cdot T^2}{2\pi}$.
        * **Dynamic Slope:** The beach slope peaks at High Tide.
        """)
