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
    .session-time { background: rgba(0,0,0,0.2); border-radius: 5px; padding: 2px 5px; font-size: 0.85em; margin-top: 10px; display: inline-block; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pakiri Ledge Command Center")

# --- HEADER & EXTERNAL LINKS ---
col_lnk1, col_lnk2 = st.columns(2)
with col_lnk1:
    st.link_button("🎥 Cross-Check Surfline Cam", SURFLINE_URL, use_container_width=True)
with col_lnk2:
    st.link_button("💨 Cross-Check Windfinder", WINDFINDER_URL, use_container_width=True)

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

# --- DATA FETCHING (Matched to Pakiri Specific Coordinates) ---
@st.cache_data(ttl=3600)
def get_full_data(current_slope):
    # Wind data (GFS)
    w_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=wind_speed_10m,wind_direction_10m&forecast_days=10&timezone=auto"
    # Swell data (MeteoFrance/LOTUS)
    m_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={LAT}&longitude={LON}&hourly=swell_wave_height,swell_wave_period,swell_wave_direction&forecast_days=10&timezone=auto"
    
    w_data = requests.get(w_url).json()['hourly']
    m_data = requests.get(m_url).json()['hourly']
    df = pd.DataFrame(m_data)
    df['wind_speed'] = w_data['wind_speed_10m']
    df['wind_dir'] = w_data['wind_direction_10m']
    df['time'] = pd.to_datetime(df['time'])
    
    # Tide Calculation (Reference: Feb 18, 2026, 08:15)
    ref = datetime(2026, 2, 18, 8, 15)
    df['hours_since_ref'] = (df['time'] - ref).dt.total_seconds() / 3600
    df['tide_level'] = 0.7 * np.cos(2 * np.pi * (df['hours_since_ref']) / 12.42) + 1.2
    
    # Ledge Physics Logic
    tide_modifier = (df['tide_level'] - 1.2) / 2
    df['dynamic_slope'] = current_slope * (1 + tide_modifier)
    df['wavelength'] = (9.81 * (df['swell_wave_period']**2)) / (2 * np.pi)
    
    # Raw Iribarren
    df['xi'] = df['dynamic_slope'] / (np.sqrt(df['swell_wave_height'] / df['wavelength']))
    
    # Reflection Coefficient
    df['R'] = (df['xi']**2) / (df['xi']**2 + 5) * 100
    
    # Wind Factor: Pakiri faces NE. NE (0-110 deg) is Onshore Penalty.
    df['wind_factor'] = np.where((df['wind_dir'] > 0) & (df['wind_dir'] < 110), 0.65, 1.0)
    df['final_score'] = df['xi'] * df['wind_factor']
    
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
    wind_card = get_cardinal(wind_deg)
    # Wind Penalty Labeling
    if wind_card in ['NNE', 'NE', 'ENE', 'E'] and wind_speed > 12:
        return "bg-red", "🌪️ CHOPPY ONSHORE"
    if xi > 1.5: return "bg-darkgreen", "PREMIUM"
    if xi > 1.2: return "bg-lightgreen", "GOOD"
    if xi > 0.8: return "bg-yellow", "AVERAGE"
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
        title = {'text': f"Ledge Quality (ξ)<br><span style='font-size:0.8em;color:gray'>{current_label}</span>", 'font': {'size': 24}},
        gauge = {'axis': {'range': [0, 2.5]}, 'bar': {'color': "black"},
                 'steps': [{'range': [0, 0.8], 'color': '#ff4b4b'}, {'range': [0.8, 1.2], 'color': '#ffa500'},
                           {'range': [1.2, 1.5], 'color': '#2ecc71'}, {'range': [1.5, 2.5], 'color': '#1b5e20'}]}
    ))
    fig_gauge.update_layout(height=350, margin=dict(t=80, b=20))
    st.plotly_chart(fig_gauge, use_container_width=True)

with g_col2:
    st.markdown(f"### Live at Pakiri\n**Swell:** {now_data['swell_wave_height']:.1f}m @ {now_data['swell_wave_period']:.0f}s {get_arrow_with_name(now_data['swell_wave_direction'])}\n**Wind:** {now_data['wind_speed']:.0f}km/h {get_arrow_with_name(now_data['wind_dir'])}\n**Tide:** {now_data['tide_level']:.1f}m\n**Reflectivity:** {now_data['R']:.0f}%")

# --- P5.JS CANVAS ---
st.divider()
st.subheader("🌊 Real-Time Fluid Dynamics")
canvas_html = f"""
<script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.4.0/p5.js"></script>
<div id="p5-container" style="width:100%; text-align:center; background:white; border-radius:12px; border:1px solid #ddd;"></div>
<script>
let hs={float(now_data['swell_wave_height'])}; let xi={float(now_data['xi'])}; let tide={float(now_data['tide_level'])}; let slope={float(slope)};
function setup(){{var c=createCanvas(windowWidth*0.9, 340); c.parent('p5-container');}}
function draw(){{
    background(255); let time=frameCount*0.02;
    fill(194,178,128); noStroke(); beginShape(); vertex(0,height);
    for(let x=0; x<=width; x+=10){{let sandY=height-(20+(1/(1+exp(-0.02*(x-width*0.7))))*(slope*2500)); vertex(x,sandY);}}
    vertex(width,height); endShape(CLOSE);
    fill(0,105,148,180); stroke(255); beginShape(); vertex(0,height);
    for(let x=0; x<=width; x+=5){{
        let prog=x/width; let cycle=(time-prog*4)%TWO_PI; let amp=(hs*40)*(1+(max(0,x-width*0.4)*0.003));
        let xOff=(sin(cycle)>0.4 && xi>1.1)?pow(sin(cycle),3)*(xi*20):0;
        let y=(height-120)-(tide*20)+sin(cycle)*amp;
        let sandL=height-(20+(1/(1+exp(-0.02*(x-width*0.7))))*(slope*2500));
        vertex(x+xOff, min(y, sandL));
    }} vertex(width,height); endShape(CLOSE);
}}
</script>"""
components.html(canvas_html, height=360)

# --- EXAGGERATED: BERM DYNAMICS, REFLECTION & SAND VOLUME ---
st.divider()
st.subheader("📐 Daily Beach Profile Comparison")
st.write("Visuals are **highly exaggerated** to show daily variance. 💥 = Ledge Strike Zone. **R%** = Backwash Power.")

df['date_label'] = df['time'].dt.strftime('%a, %b %d')
daily_geom = df.groupby('date_label').agg({
    'xi':'max', 'tide_level':'max', 'dynamic_slope':'max', 'swell_wave_height':'mean', 'wavelength':'mean', 'R':'max'
}).reindex(df['date_label'].unique())

avg_slope = daily_geom['dynamic_slope'].mean()
avg_xi = daily_geom['xi'].mean()
g_cols = [st.columns(5), st.columns(5)]
x_vals = np.linspace(10, 100, 100)

def get_extreme_profile(slope_val, xi_val):
    mu = 90 - (slope_val * 90) 
    sigma = 25 / (xi_val ** 3.0) 
    y = 3.6 * np.exp(-((x_vals - mu)**2) / (2 * sigma**2))
    y = np.where(x_vals > mu, 3.6 + (0.012 * (x_vals - mu)), y)
    return y, mu

for i, (date, row) in enumerate(daily_geom.iterrows()):
    if pd.isna(row['xi']): continue
    with g_cols[i//5][i%5]:
        y_vals, ledge_x = get_extreme_profile(row['dynamic_slope'], row['xi'])
        y_avg, _ = get_extreme_profile(avg_slope, avg_xi) 
        dy = np.abs(np.gradient(y_vals))

        fig_mini = go.Figure()
        fig_mini.add_trace(go.Scatter(x=x_vals, y=y_avg, line=dict(color='rgba(200, 200, 200, 0.08)', width=1, dash='dot'), hoverinfo='none'))
        fig_mini.add_trace(go.Bar(x=x_vals, y=y_vals, marker=dict(color=dy, colorscale='Hot', showscale=False), width=1.1))
        fig_mini.add_trace(go.Scatter(x=[10, 100], y=[row['tide_level'], row['tide_level']], line=dict(color='cyan', width=5)))

        if row['xi'] > 1.3:
            fig_mini.add_annotation(x=ledge_x, y=row['tide_level'], text="💥", showarrow=False, font=dict(size=22))
        
        fig_mini.update_layout(height=250, margin=dict(l=0, r=0, t=60, b=0),
            title={'text': f"<b>{date}</b><br><span style='color:cyan;'>R: {row['R']:.0f}%</span>", 'font': {'size': 14}, 'x': 0.5},
            xaxis=dict(visible=False), yaxis=dict(range=[0, 5.5], visible=False), showlegend=False, barmode='overlay', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')

        st.plotly_chart(fig_mini, use_container_width=True, config={'displayModeBar': False})
        
        v_state = "BUILDING" if (row['swell_wave_height']/row['wavelength']) < 0.02 else "ERODING"
        v_color = "gold" if v_state == "BUILDING" else "gray"
        st.markdown(f"<div style='text-align:center; font-size:10px; color:{v_color};'>BANK {v_state}</div>", unsafe_allow_html=True)

# --- 10-DAY FORECAST CARDS ---
st.subheader("🗓️ 10-Day Skim Forecast")
cols = [st.columns(5), st.columns(5)]
for i, (date, row) in enumerate(daily_geom.iterrows()):
    d_row = df[df['date_label'] == date].iloc[df[df['date_label'] == date]['xi'].argmax()]
    color, label = get_expert_score(d_row['xi'], d_row['swell_wave_height'], d_row['swell_wave_period'], d_row['wind_dir'], d_row['wind_speed'], d_row['tide_level'])

    card_html = f"""
<div class='card {color}'>
<div style='font-size: 0.85em; opacity: 0.8;'>{date}</div>
<div style='font-size: 1.2em; margin: 4px 0;'><strong>{label}</strong></div>
<div style='font-size: 1.0em; margin-top: 5px;'>🌊 <b>{d_row['swell_wave_height']:.1f}m</b> @ {d_row['swell_wave_period']:.0f}s</div>
<div style='font-size: 0.85em; color: #eee;'>Wind: {d_row['wind_speed']:.0f}km/h {get_arrow_with_name(d_row['wind_dir'])}</div>
<hr style='margin:10px 0; border: 0.5px solid rgba(255,255,255,0.2);'>
<div style='font-size: 1.1em;'>ξ {d_row['xi']:.2f} | R {d_row['R']:.0f}%</div>
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
        
    with doc_col2:
        st.markdown(r"""
        **3. The Iribarren Engine ($\xi$)**
        $$\xi = \frac{\tan \beta}{\sqrt{H/L}}$$
        
        **4. Reflection Coefficient ($R$)**
        Predicts the "backwash" pop:
        $$R = \frac{\xi^2}{\xi^2 + 5}$$
        """)
