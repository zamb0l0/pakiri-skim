import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(page_title="Pakiri Ledge Watch", page_icon="🌊")

st.title("🌊 Pakiri Ledge Forecast")
st.write("Predicting 'Feb 8th' magic based on live swell data.")

# --- 1. Sidebar Inputs ---
with st.sidebar:
    st.header("Beach State")
    # Using your current slope from the analysis
    current_slope = st.slider("Current Beach Slope (tan beta)", 0.02, 0.15, 0.0371)
    st.info(f"0.10+ = Reflective (Ledge)\n0.04- = Dissipative (Flat)")

# --- 2. Live Data Fetch ---
@st.cache_data(ttl=3600)
def get_marine_data():
    lat, lon = -36.26, 174.78
    url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly=swell_wave_height,swell_wave_period&timezone=auto"
    try:
        data = requests.get(url).json()
        return pd.DataFrame(data['hourly'])
    except:
        return pd.DataFrame()

df = get_marine_data()

# --- 3. The Logic (The Fix is here!) ---
if not df.empty:
    # Get the next available swell (index 0 is current hour)
    h = df['swell_wave_height'][0]
    t = df['swell_wave_period'][0]
    
    # Calculate Iribarren Number (xi)
    # Formula: xi = slope / sqrt(height / wavelength)
    # Wavelength L = (g * T^2) / 2pi
    wavelength = (9.81 * (t**2)) / (2 * np.pi)
    predicted_xi = current_slope / ((h / wavelength)**0.5)

    # --- 4. Display Results ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Swell Height", f"{h}m")
    col2.metric("Swell Period", f"{t}s")
    col3.metric("Iribarren (ξ)", f"{predicted_xi:.2f}")

    st.divider()

    if predicted_xi > 1.2:
        st.success("🚀 **GOLDEN SESSION:** Ledge is active. Heavy wedges expected.")
    elif predicted_xi > 0.7:
        st.warning("🏄 **INTERMEDIATE:** Bank is holding. Possible skimming.")
    else:
        st.error("💨 **WASHED OUT:** The beach is too flat for this swell.")
        
    st.caption(f"Based on current conditions: {h}m @ {t}s")
else:
    st.error("Unable to fetch live swell data. Check your internet connection!")
