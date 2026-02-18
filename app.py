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
    w_url = "https://api.open-meteo.com/v1/forecast?latitude=-36.26&longitude=174.78&hourly=wind_speed_10m,wind_direction_10m&forecast_days=10&timezone=auto"
    m_url = "https://marine-api.open-meteo.com/v1/marine?latitude=-36.26&longitude=174.78&hourly=swell_wave_height,swell_wave_period,swell_wave_direction&forecast_days=10&timezone=auto"
    w_data = requests.get(w_url).json()['hourly']
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
    if wind_card in ['NNE', 'NE', 'ENE', 'E', 'ESE', 'SE'] and wind_speed > 15:
        return "bg-red", "🌪️ CHOPPY ONSHORE"
    if t >= 13 and xi > 1.4 and wind_card in ['W', 'SW', 'S']: return "bg-blue", "🏆 DEC 8th BERM"
    if xi > 1.5 and score > 20: return "bg-darkgreen", "PREMIUM"
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
        title = {'text': f"Current Ledge Quality (ξ)<br><span style='font-size:0.8em;color:gray'>{current_label}</span>", 'font': {'size': 24}},
        gauge = {'axis': {'range': [0, 2.5]}, 'bar': {'color': "black"},
                 'steps': [{'range': [0, 0.8], 'color': '#ff4b4b'}, {'range': [0.8, 1.2], 'color': '#ffa500'},
                           {'range': [1.2, 1.5], 'color': '#2ecc71'}, {'range': [1.5, 2.5], 'color': '#1b5e20'}]}
    ))
    fig_gauge.update_layout(height=400, margin=dict(t=120, b=20, l=30, r=30))
    st.plotly_chart(fig_gauge, use_container_width=True)

with g_col2:
    st.markdown(f"### Right Now at Pakiri\n**Swell:** {now_data['swell_wave_height']:.1f}m @ {now_data['swell_wave_period']:.0f}s {get_arrow_with_name(now_data['swell_wave_direction'])}\n**Wind:** {now_data['wind_speed']:.0f}km/h {get_arrow_with_name(now_data['wind_dir'])}\n**Tide:** {now_data['tide_level']:.1f}m\n**Status:** {current_label}")

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

# 1. Grouping and Prep
df['date_label'] = df['time'].dt.strftime('%a, %b %d')
daily_geom = df.groupby('date_label').agg({
    'xi':'max', 
    'tide_level':'max', 
    'dynamic_slope':'max',
    'swell_wave_height':'mean',
    'wavelength':'mean'
}).reindex(df['date_label'].unique())

avg_slope = daily_geom['dynamic_slope'].mean()
avg_xi = daily_geom['xi'].mean()

g_cols = [st.columns(5), st.columns(5)]
x_vals = np.linspace(10, 100, 100)

def get_extreme_profile(slope_val, xi_val, h, wav_len):
    # POSITION: Move the 'Step' based on slope
    mu = 90 - (slope_val * 90) 
    
    # SHAPE: Massive scaling. Divisor power of 3.0 creates huge visual difference.
    sigma = 25 / (xi_val ** 3.0) 
    
    # 1. The Ledge Face
    y = 3.6 * np.exp(-((x_vals - mu)**2) / (2 * sigma**2))
    
    # 2. The Rising Dune (Diagrammatic rise behind the ledge)
    y = np.where(x_vals > mu, 3.6 + (0.012 * (x_vals - mu)), y)
    
    # 3. Reflection Coefficient (R%)
    reflection = (xi_val**2) / (xi_val**2 + 4.5) * 100
    
    # 4. Sand Volume (Dean's Parameter approach: H / (fall_velocity * period))
    # If wave steepness (H/L) is low, sand builds. If high, it erodes.
    steepness_ratio = h / wav_len
    volume_state = "BUILDING" if steepness_ratio < 0.02 else "ERODING"
    vol_color = "gold" if volume_state == "BUILDING" else "gray"
    
    return y, reflection, mu, volume_state, vol_color

for i, (date, row) in enumerate(daily_geom.iterrows()):
    if pd.isna(row['xi']): continue
        
    with g_cols[i//5][i%5]:
        y_vals, reflection, ledge_x, v_state, v_color = get_extreme_profile(
            row['dynamic_slope'], row['xi'], row['swell_wave_height'], row['wavelength']
        )
        y_avg, _, _, _, _ = get_extreme_profile(avg_slope, avg_xi, 1.0, 100) 
        
        # Calculate local gradient for the "Heat Map" coloring
        dy = np.abs(np.gradient(y_vals))

        fig_mini = go.Figure()

        # Ghost Reference
        fig_mini.add_trace(go.Scatter(
            x=x_vals, y=y_avg, 
            line=dict(color='rgba(200, 200, 200, 0.08)', width=1, dash='dot'),
            hoverinfo='none'
        ))

        # The Profile (Sand)
        fig_mini.add_trace(go.Bar(
            x=x_vals, y=y_vals,
            marker=dict(color=dy, colorscale='Hot', showscale=False),
            width=1.1
        ))

        # The Tide Line
        fig_mini.add_trace(go.Scatter(
            x=[10, 100], y=[row['tide_level'], row['tide_level']], 
            line=dict(color='cyan', width=5)
        ))

        # Strike Annotation
        if row['xi'] > 1.3:
            fig_mini.add_annotation(
                x=ledge_x, y=row['tide_level'], text="💥",
                showarrow=False, font=dict(size=22)
            )
        
        fig_mini.update_layout(
            height=250, margin=dict(l=0, r=0, t=60, b=0),
            title={
                'text': f"<b>{date}</b><br><span style='color:cyan;'>R: {reflection:.0f}%</span>", 
                'font': {'size': 14}, 'x': 0.5
            },
            xaxis=dict(visible=False), 
            yaxis=dict(range=[0, 5.5], visible=False),
            showlegend=False, barmode='overlay', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
        )

        st.plotly_chart(fig_mini, use_container_width=True, config={'displayModeBar': False})
        
        # Sand Volume Indicator
        st.markdown(f"<div style='text-align:center; font-size:10px; color:{v_color};'>BANK {v_state}</div>", unsafe_allow_html=True)

# --- 10-DAY FORECAST CARDS ---
st.subheader("🗓️ 10-Day Skim Forecast")
cols = [st.columns(5), st.columns(5)]
for i, (date, row) in enumerate(daily_geom.iterrows()):
    d_row = df[df['date_label'] == date].iloc[df[df['date_label'] == date]['xi'].argmax()]
    color, label = get_expert_score(d_row['xi'], d_row['swell_wave_height'], d_row['swell_wave_period'], d_row['wind_dir'], d_row['wind_speed'], d_row['tide_level'])
    t_dt = get_high_tide_dt(d_row['time'])
    s_start, s_end = (t_dt - timedelta(hours=1)).strftime('%I:%M'), (t_dt + timedelta(minutes=90)).strftime('%I:%M %p')

    card_html = f"""
<div class='card {color}'>
<div style='font-size: 0.85em; opacity: 0.8;'>{date}</div>
<div style='font-size: 1.2em; margin: 4px 0;'><strong>{label}</strong></div>
<div style='font-size: 1.0em; margin-top: 5px;'>🌊 <b>{d_row['swell_wave_height']:.1f}m</b> @ {d_row['swell_wave_period']:.0f}s</div>
<div style='font-size: 0.85em; margin-top: 3px;'>Swell: {get_arrow_with_name(d_row['swell_wave_direction'])}</div>
<div style='font-size: 0.85em; color: #eee;'>Wind: {d_row['wind_speed']:.0f}km/h {get_arrow_with_name(d_row['wind_dir'])}</div>
<div class='session-time' style='margin-top: 10px;'>🎯 Best: {s_start} - {s_end}</div>
<hr style='margin:10px 0; border: 0.5px solid rgba(255,255,255,0.2);'>
<div style='font-size: 1.1em;'>ξ {d_row['xi']:.2f}</div>
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

# --- TECHNICAL DOCUMENTATION SECTION ---
with st.expander("🔬 How the Pakiri Ledge Engine Works"):
    st.markdown("### 🛰️ The Data Pipeline: From Ocean to Forecast")
    
    doc_col1, doc_col2 = st.columns([1, 1])
    
    with doc_col1:
        st.markdown("""
        **1. Raw Data Acquisition**
        The system pulls live, high-resolution data from global engines via the **Open-Meteo API**:
        * **Global Forecast System (GFS):** For wind speed and direction.
        * **MeteoFrance Wave Model:** For swell height, period, and direction, derived from satellite altimetry and Pacific buoy networks.

        **2. The Pakiri Transformation**
        We process raw swell through three mathematical layers:
        * **Wavelength ($L$):** Calculated using $L = \frac{g \cdot T^2}{2\pi}$. This determines the wave's energy density.
        * **Dynamic Slope:** Unlike static models, this app adjusts the beach slope based on the **Tide Cycle**. As water reaches the berm, the slope $(\tan \beta)$ increases.
        """)
    
    with doc_col2:
        st.markdown("""
        **3. The Iribarren Engine ($\xi$)**
        This is the core "Ledge" metric. It calculates the transition between energy absorption and wave reflection:
        $$\\xi = \\frac{\\tan \\beta}{\\sqrt{H/L}}$$
        
        **4. Reflection Coefficient ($R$)**
        To predict backwash power, we calculate the percentage of wave energy reflected back off the sand:
        $$R = \\frac{\\xi^2}{\\xi^2 + 5}$$
        """)

    st.divider()
    
    st.markdown("### 📊 Deciphering the Visuals")
    
    
    tab1, tab2, tab3 = st.tabs(["Breaking Types", "Bank Health", "The Ledge Visual"])
    
    with tab1:
        st.table(pd.DataFrame({
            "Iribarren (ξ)": ["< 0.5", "0.5 - 1.2", "> 1.5"],
            "Break Type": ["Spilling", "Plunging", "Surging"],
            "Skim Quality": ["Washed Out (Flat)", "Average (Shorebreak)", "Premium (The Ledge)"]
        }))
        
        
    with tab2:
        st.write("**Bank Volume Tracking** is determined by the *Swell Steepness Ratio*.")
        st.write("If $H/L < 0.02$, long-period energy pushes sand shoreward (**Building**). If the ratio is higher, short-period energy pulls sand away (**Eroding**).")
        
        
    with tab3:
        st.write("The Daily Profile graphs use **Non-Linear Geometric Scaling**. On 'Good' days, the $x$-axis is compressed to visually represent a 'Ledge Wall'. On 'Bad' days, it is stretched to show a 'Dissipative Ramp'.")
