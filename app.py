import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Pakiri Ledge Watch", page_icon="🌊")

st.title("🌊 Pakiri Ledge Forecast")
st.write("Predicting the 'Feb 8th' magic based on beach slope and wave energy.")

# --- INPUT SECTION ---
with st.sidebar:
    st.header("Settings")
    # You can update this once a week when you run CoastSat
    current_slope = st.slider("Current Beach Slope (tan beta)", 0.02, 0.15, 0.0371)
    memory_score = st.number_input("Starting Memory Score", value=-10)

# --- LIVE DATA FETCH ---
@st.cache_data(ttl=3600) # Only fetch data once per hour
def get_marine_forecast():
    url = "https://marine-api.open-meteo.com/v1/marine?latitude=-36.26&longitude=174.78&hourly=swell_wave_height,swell_wave_period&timezone=auto"
    return pd.DataFrame(requests.get(url).json()['hourly'])

df = get_marine_forecast()

# --- LEDGE CALCULATION ---
# (Apply the logic we built previously)
# ... [Ledge builder logic goes here] ...

# --- THE RESULTS DIAL ---
st.metric(label="Predicted Iribarren Number", value=f"{predicted_xi:.2f}")

if predicted_xi > 1.5:
    st.success("🚀 STATUS: GOLDEN SESSION. Go now.")
elif predicted_xi > 0.8:
    st.warning("🏄 STATUS: MODERATE. Ledge is thin but working.")
else:
    st.error("💨 STATUS: FLAT. Stay home, sand is washed out.")
