import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(page_title="Pakiri Ledge Watch", page_icon="🌊")

# --- UI HEADER ---
st.title("🌊 Pakiri Ledge Forecast")
st.write("Predicting 'Feb 8th' magic based on live swell data.")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("🎛️ Calibration")
    # This is the 'Slope' you found in your analysis
    slope = st.slider("Current Beach Slope", 0.02, 0.15, 0.0371, format="%.4f")
    st.info("Feb 8th was ~0.1200")

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_data():
    url = "https://marine-api.open-meteo.com/v1/marine?latitude=-36.26&longitude=174.78&hourly=swell_wave_height,swell_wave_period&timezone=auto"
    res = requests.get(url).json()
    return pd.DataFrame(res['hourly'])

df = get_data()

if not df.empty:
    # Current Conditions
    h = df['swell_wave_height'][0]
    t = df['swell_wave_period'][0]
    
    # Iribarren Logic
    L0 = (9.81 * (t**2)) / (2 * np.pi)
    xi = slope / (np.sqrt(h / L0))
    
    # 48-Hour Accretion Logic (Is the ledge building right now?)
    recent_h = df['swell_wave_height'].iloc[:48].mean()
    recent_t = df['swell_wave_period'].iloc[:48].mean()
    building = "✅ Building" if recent_h < 1.0 and recent_t > 10 else "❌ Eroding"

    # --- DASHBOARD ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Swell", f"{h}m")
    c2.metric("Period", f"{t}s")
    c3.metric("Iribarren (ξ)", f"{xi:.2f}")

    st.subheader(f"Current Status: {building}")
    
    if xi > 1.2:
        st.success("🚀 **GOLDEN SESSION:** Ledge is active. Heavy vertical wedges.")
    elif xi > 0.7:
        st.warning("🏄 **INTERMEDIATE:** Bank is holding. Possible side-wash.")
    else:
        st.error("💨 **WASHED OUT:** Beach is too shallow. Wait for smaller/longer swell.")

    st.divider()
    st.write("### 📅 Sunday Feb 22 Strategy")
    st.write("**High Tide:** 11:33 AM (2.4m)")
    st.write("**Best Window:** 10:00 AM - 12:30 PM")
