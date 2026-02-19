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
    /* 1. Clear the Streamlit gray boxes BUT ignore our skim-cards */
    [data-testid="stMarkdownContainer"] > div:not(.skim-card) {
        background-color: transparent !important;
    }

    /* 2. Remove Streamlit's white background on the markdown block itself */
    .stMarkdown {
        background-color: transparent !important;
    }

    /* 3. Force OUR card to be an opaque solid block */
    .skim-card {
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        opacity: 1 !important;
        visibility: visible !important;
    }

    /* 4. Hide the annoying code leakage */
    code { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

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

# --- SIMPLIFIED STYLING (STOPS THE BLEACHING) ---
st.markdown(r"""
    <style>
    /* Stop Streamlit from adding gray boxes but don't force transparency on our HTML */
    [data-testid="stMarkdownContainer"] { background-color: transparent !important; }
    div[data-testid="stMarkdownContainer"] > div { border: none !important; }
    code { display: none !important; }
    
    /* Ensure the cards look uniform */
    .skim-card-container {
        border: 1px solid rgba(128,128,128,0.2);
        border-radius: 15px;
        overflow: hidden;
        text-align: center;
        min-height: 400px;
        display: flex;
        flex-direction: column;
        background-color: rgba(128,128,128,0.05);
        font-family: sans-serif;
    }
    </style>
    """, unsafe_allow_html=True)

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
    text_color = "black" if bg_color in ["#f1c40f", "#2ecc71"] else "white"

    # THE HTML: COLOR IS NOW IN THE TOP BAR ONLY
    card_html = f"""
<div class="skim-card-container">
    <div style="background-color: {bg_color} !important; color: {text_color} !important; padding: 12px; font-weight: 900; font-size: 1.2em; border-bottom: 2px solid rgba(0,0,0,0.1);">
        {label}
    </div>
    
    <div style="padding: 10px; font-size: 0.8em; opacity: 0.7; font-weight: bold;">{date}</div>

    <div style="padding: 10px; border-top: 1px solid rgba(128,128,128,0.1); border-bottom: 1px solid rgba(128,128,128,0.1); margin: 0 10px;">
        <div style="font-size: 1.0em; font-weight: bold;">🌊 {d_row['swell_wave_height']:.1f}m @ {d_row['swell_wave_period']:.0f}s</div>
        <div style="font-size: 0.8em; margin-top: 4px;">{get_arrow_with_name(d_row['swell_wave_direction'])} | 💨 {d_row['wind_speed']:.0f}km/h</div>
    </div>

    <div style="padding: 15px 10px; flex-grow: 1;">
        <div style="font-size: 0.9em;"><b>Best Window:</b></div>
        <div style="font-size: 1.0em;">{d_row['time'].strftime('%I:%M %p')}</div>
        <div style="font-size: 1.1em; font-weight: bold; margin-top: 5px;">Tide: {d_row['tide_level']:.1f}m {tide_arrow}</div>
    </div>

    <div style="padding: 10px; background: rgba(0,0,0,0.05);">
        <div style="font-size: 0.9em; font-weight: bold;">{get_drop_logic(d_row['xi'], d_row['swell_wave_period'])[1]} {get_drop_logic(d_row['xi'], d_row['swell_wave_period'])[0]}</div>
        <div style="font-size: 0.9em; margin-top: 2px;">ξ {d_row['xi']:.2f} | R {d_row['R']:.0f}%</div>
    </div>
</div>"""

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
