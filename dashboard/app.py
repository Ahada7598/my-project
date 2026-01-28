# dashboard/app.py - MINIMAL TEST VERSION
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Test", layout="wide")
st.title("✅ Procurement System - TEST")
st.success("If you see this, the app is working!")

# Test imports
st.write(f"Pandas version: {pd.__version__}")

# Simple CSV test
try:
    import os
    if os.path.exists("data/agencies.csv"):
        df = pd.read_csv("data/agencies.csv")
        st.write(f"Data loaded: {len(df)} rows")
        st.dataframe(df.head())
    else:
        st.warning("data/ folder not found")
except Exception as e:
    st.error(f"Error: {e}")

st.markdown("---")
st.write("Next: Add your full app code here.")