import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pakiri Ledge Command Center", page_icon="🌊", layout="wide")

# --- GLOBAL PAGE TITLE ---
st.markdown(f"""
<div style="background-color: #2d3436; color: white; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 30px; border: 2px solid #000;">
    <h1 style="margin: 0; font-size: 2.2rem; letter-spacing: 3px; text-transform: uppercase; font-weight: 900;"> SKIM PAKIRI</h1>
    <p style="margin: 8px 0 0 0; font-family: monospace; font-size: 1rem; opacity: 0.9; letter-spacing: 1px;">📍36°14'10.4"S 174°43'05.6"E</p>
</div>
""", unsafe_allow_html=True)

# --- PAKIRI METADATA ---
LAT = -36.264
LON = 174.721

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

# --- DATA FETCHING ---
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

# --- LIVE GAUGE & SATELLITE OVERLAY ---
now = datetime.now()
idx = (df['time'] - now).abs().idxmin()
now_data = df.loc[idx]

# Fix: Calculate tide_arrow for the 'Now' data
prev_idx = max(0, idx - 1)
tide_arrow = "↑" if now_data['tide_level'] > df.loc[prev_idx, 'tide_level'] else "↓"

current_bg, current_label = get_expert_score(
    now_data['xi'], now_data['swell_wave_height'], 
    now_data['swell_wave_period'], now_data['wind_dir'], 
    now_data['wind_speed'], now_data['tide_level']
)

# This layout defines two clear areas: Gauge/Stats on left, Map on right
g_col1, g_col2 = st.columns([1.2, 1.8])

with g_col1:
    # 1. THE GAUGE
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number", value = now_data['xi'],
        title = {'text': f"Ledge Quality (ξ)<br><span style='font-size:0.8em;color:gray'>{current_label}</span>", 
                 'font': {'color': 'black'}},
        gauge = {'axis': {'range': [0, 2.5]}, 'bar': {'color': "black"},
                 'steps': [{'range': [0, 0.8], 'color': '#ff4b4b'}, {'range': [0.8, 1.2], 'color': '#ffa500'},
                           {'range': [1.2, 1.5], 'color': '#2ecc71'}, {'range': [1.5, 2.5], 'color': '#1b5e20'}]}
    ))
    fig_gauge.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_gauge, use_container_width=True)
    
    # 2. THE STATS CARD
    st.markdown(f"""
    <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #2d3436; color: #2d3436;">
        <div style="font-size: 1.1rem; font-weight: 900; margin-bottom: 5px;">LIVE CONDITIONS</div>
        <b>Swell:</b> {now_data['swell_wave_height']:.1f}m @ {now_data['swell_wave_period']:.0f}s<br>
        <b>Wind:</b> {now_data['wind_speed']:.0f}km/h {get_arrow_with_name(now_data['wind_dir'])}<br>
        <b>Tide:</b> {now_data['tide_level']:.1f}m ({tide_arrow})
    </div>
    """, unsafe_allow_html=True)

with g_col2:
    # 3. HIGH-FIDELITY COMPASS: 15° INTERNAL TICKS
    LAT, LON = -36.236222, 174.718222
    fig_map = go.Figure()

    # --- 1. THE CIRCLE & TICKS ---
    ring_dist = 0.0028 
    lat_correction = 1.25 
    
    # Main White Ring
    angles = np.linspace(0, 2*np.pi, 100)
    fig_map.add_trace(go.Scattermapbox(
        mode = "lines",
        lon = LON + ring_dist * np.sin(angles),
        lat = LAT + (ring_dist / lat_correction) * np.cos(angles),
        line = dict(width=2, color="white"),
        opacity=0.8, hoverinfo='none'
    ))

    # Tick Marks (Every 15° on the inside)
    for d in range(0, 360, 15):
        rad = np.radians(d)
        # Inside the ring
        t_start_dist = ring_dist - 0.0003
        t_end_dist = ring_dist
        
        fig_map.add_trace(go.Scattermapbox(
            mode = "lines",
            lon = [LON + t_start_dist * np.sin(rad), LON + t_end_dist * np.sin(rad)],
            lat = [LAT + (t_start_dist / lat_correction) * np.cos(rad), LAT + (t_end_dist / lat_correction) * np.cos(rad)],
            line = dict(width=1.5, color="white"),
            hoverinfo='none'
        ))
        
        # Degree Labels (Every 45° on the outside)
        if d % 45 == 0:
            label_dist = ring_dist + 0.0008
            fig_map.add_trace(go.Scattermapbox(
                mode = "text",
                lon = [LON + label_dist * np.sin(rad)],
                lat = [LAT + (label_dist / lat_correction) * np.cos(rad)],
                text = [f"{d}°"],
                textfont = dict(size=12, color="white", family="Arial Black"),
                hoverinfo='none'
            ))

    # --- 2. THE WHITE WIND ARROW (From center) ---
    w_deg = now_data['wind_dir']
    w_rad = np.radians(w_deg)
    w_tip_dist = ring_dist * 0.6
    w_tip_lon = LON + w_tip_dist * np.sin(w_rad)
    w_tip_lat = LAT + (w_tip_dist / lat_correction) * np.cos(w_rad)
    wl_lon = LON + (w_tip_dist * 0.7) * np.sin(w_rad - 0.2)
    wl_lat = LAT + ((w_tip_dist * 0.7) / lat_correction) * np.cos(w_rad - 0.2)
    wr_lon = LON + (w_tip_dist * 0.7) * np.sin(w_rad + 0.2)
    wr_lat = LAT + ((w_tip_dist * 0.7) / lat_correction) * np.cos(w_rad + 0.2)

    fig_map.add_trace(go.Scattermapbox(
        mode = "lines", fill = "toself",
        lon = [LON, wl_lon, w_tip_lon, wr_lon, LON],
        lat = [LAT, wl_lat, w_tip_lat, wr_lat, LAT],
        fillcolor = "white", line = dict(width=0),
        name = "Wind"
    ))

    # --- 3. THE WHITE SWELL PAPER PLANE (On Ring pointing IN) ---
    s_deg = now_data['swell_wave_direction']
    s_rad = np.radians(s_deg)
    p_lon = LON + ring_dist * np.sin(s_rad)
    p_lat = LAT + (ring_dist / lat_correction) * np.cos(s_rad)
    sl_lon = LON + (ring_dist * 1.25) * np.sin(s_rad - 0.15)
    sl_lat = LAT + ((ring_dist * 1.25) / lat_correction) * np.cos(s_rad - 0.15)
    sr_lon = LON + (ring_dist * 1.25) * np.sin(s_rad + 0.15)
    sr_lat = LAT + ((ring_dist * 1.25) / lat_correction) * np.cos(s_rad + 0.15)
    sn_lon = LON + (ring_dist * 1.1) * np.sin(s_rad)
    sn_lat = LAT + ((ring_dist * 1.1) / lat_correction) * np.cos(s_rad)

    fig_map.add_trace(go.Scattermapbox(
        mode = "lines", fill = "toself",
        lon = [p_lon, sl_lon, sn_lon, sr_lon, p_lon],
        lat = [p_lat, sl_lat, sn_lat, sr_lat, p_lat],
        fillcolor = "white", line = dict(width=1, color="rgba(0,0,0,0.2)"),
        name = "Swell"
    ))

    # --- 4. DYNAMIC CONTOURS ---
    base_spacing = 0.00003 / now_data['dynamic_slope'] 
    for i, color in enumerate(['#e67e22', '#d35400']):
        offset = i * base_spacing
        fig_map.add_trace(go.Scattermapbox(
            mode = "lines",
            lon = [174.715 + offset, 174.718 + offset, 174.722 + offset, 174.726 + offset],
            lat = [-36.233 - offset, -36.236 - offset, -36.239 - offset, -36.242 - offset],
            line = dict(width=1, color=color),
            opacity=0.6, showlegend=False
        ))

    fig_map.update_layout(
        margin = {'l':0,'t':0,'b':0,'r':0}, height = 500,
        mapbox = {
            'style': "white-bg",
            'layers': [{
                'below': 'traces', 'sourcetype': 'raster',
                'source': ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]
            }],
            'center': {'lon': LON, 'lat': LAT}, 'zoom': 15.6
        }, showlegend = False
    )
    st.plotly_chart(fig_map, use_container_width=True)

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

g_cols = st.columns(5) + st.columns(5)
x_vals = np.linspace(10, 100, 150)

for i, (date, row) in enumerate(daily_geom.iterrows()):
    if pd.isna(row['xi']): continue
    
    # Safely handle grid overflow if more than 10 dates
    if i >= len(g_cols): break

    with g_cols[i]:
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

all_cols = st.columns(5) + st.columns(5)
available_dates = sorted(df['date_label'].unique(), key=lambda x: datetime.strptime(x.split(', ')[1], '%b %d'))[:10]

traffic_light_hex = {
    "bg-red": "#ff4b4b", "bg-orange": "#ffa500", "bg-yellow": "#f1c40f",
    "bg-lightgreen": "#2ecc71", "bg-darkgreen": "#1b5e20", "bg-purple": "#8e44ad"
}

for i, date in enumerate(available_dates):
    day_data = df[df['date_label'] == date]
    if day_data.empty: continue
    
    best_hour_idx = day_data['xi'].idxmax()
    d_row = df.loc[best_hour_idx]
    tide_arrow = "↑" if (best_hour_idx > 0 and d_row['tide_level'] > df.loc[best_hour_idx-1, 'tide_level']) else "↓"

    color_class, label = get_expert_score(d_row['xi'], d_row['swell_wave_height'], d_row['swell_wave_period'], d_row['wind_dir'], d_row['wind_speed'], d_row['tide_level'])
    bg_color = traffic_light_hex.get(color_class, "#333333")
    
    # Text color logic
    header_text = "black" if bg_color in ["#f1c40f", "#2ecc71"] else "white"
    body_text = "#2d3436" # Keep body text dark for readability on pastel
    
    swell_deg = d_row['swell_wave_direction']
    paper_plane = f"➤" 
    swell_cardinal = get_cardinal(swell_deg)
    wind_cardinal = get_cardinal(d_row['wind_dir'])

    # THE PASTEL REJIG: Left-aligned for safety
    card_html = f"""
<div style="font-family: sans-serif; margin-bottom: 25px; border-radius: 12px; overflow: hidden; border: 1px solid rgba(0,0,0,0.1); min-height: 420px; display: flex; flex-direction: column;">
<div style="background-color: {bg_color}; color: {header_text}; padding: 12px; text-align: center;">
<div style="font-weight: 900; font-size: 0.75rem; text-transform: uppercase; opacity: 0.8; margin-bottom: 2px;">{date}</div>
<div style="font-weight: 900; font-size: 1.2rem; text-transform: uppercase;">{label}</div>
</div>

<div style="background-color: {bg_color}99; color: {body_text}; padding: 15px; flex-grow: 1; text-align: center; display: flex; flex-direction: column; justify-content: space-between;">
<div>
<div style="margin-bottom: 15px;">
<div style="font-size: 1.5rem; font-weight: 900;">🌊 {d_row['swell_wave_height']:.1f}m @ {d_row['swell_wave_period']:.0f}s</div>
<div style="font-size: 0.95rem; font-weight: 700;">{swell_cardinal} <span style="display:inline-block; transform: rotate({swell_deg}deg);">{paper_plane}</span></div>
</div>

<div style="margin-bottom: 15px;">
<div style="font-size: 0.65rem; font-weight: 900; text-transform: uppercase; opacity: 0.6;">Wind</div>
<div style="font-size: 1.1rem; font-weight: 900;">💨 {d_row['wind_speed']:.0f}km/h</div>
<div style="font-size: 0.95rem; font-weight: 700;">{wind_cardinal} {get_arrow_with_name(d_row['wind_dir']).split(' ')[1]}</div>
</div>

<div style="background: rgba(255,255,255,0.3); padding: 10px; border-radius: 8px; border: 1px solid rgba(0,0,0,0.05);">
<div style="font-size: 1.2rem; font-weight: 900;">{d_row['tide_level']:.1f}m {tide_arrow}</div>
<div style="font-size: 1.0rem; font-weight: 900;">{d_row['time'].strftime('%I:%M %p')}</div>
</div>
</div>

<div style="margin-top: 20px; padding-top: 10px; border-top: 1px solid rgba(0,0,0,0.1);">
<div style="font-weight: 900; font-size: 1.1rem; text-transform: uppercase; margin-bottom: 4px;">{get_drop_logic(d_row['xi'], d_row['swell_wave_period'])[1]}</div>
<div style="font-size: 0.95rem; font-weight: 800; opacity: 0.9;">{get_drop_logic(d_row['xi'], d_row['swell_wave_period'])[0]}</div>
<div style="font-size: 0.85rem; font-family: monospace; font-weight: 900; margin-top: 5px;">ξ {d_row['xi']:.2f} | R {d_row['R']:.0f}%</div>
</div>
</div>
</div>
"""

    with all_cols[i]:
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
