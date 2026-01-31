import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re

# 1. PAGE CONFIG
st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 2. CLIENTS & SECRETS
CLIENTS = {
    "Granit": st.secrets.get("URL_GRANIT", ""),
    "Cruz": st.secrets.get("URL_CRUZ", "")
}

st.sidebar.header("Settings")
selected_client = st.sidebar.selectbox("Select Client", list(CLIENTS.keys()))
pay_per_scan = st.sidebar.number_input("Payment per approved scan ($/€)", value=0.50, step=0.05)

st.title(f"📊 Scan Quality Monitoring: {selected_client}")

# 3. COLORS & THEME
quality_colors = {
    'APPROVED': '#28a745',          # Green
    'PARTIALLY APROVED': '#ff8c00', # Orange
    'REPPROVED': '#dc3545'          # Red
}

# 4. DATA LOADING FUNCTION (Now supports Sheet Selection)
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_sheet_data(url, sheet_name):
    try:
        # Load specific worksheet
        df = conn.read(spreadsheet=url, worksheet=sheet_name)
        df.columns = df.columns.str.strip()
        
        # Identify naming column (Patient or Cast)
        col_name = 'Patient' if 'Patient' in df.columns else ('Cast' if 'Cast' in df.columns else df.columns[0])
        
        # Extract Date YYYY_MM_DD
        def get_date(text):
            match = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
            return match.group(1) if match else None

        df['date_str'] = df[col_name].apply(get_date)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        
        return df, col_name
    except Exception:
        return pd.DataFrame(), None

# --- MAIN DASHBOARD LOGIC ---
current_url = CLIENTS[selected_client]

if not current_url:
    st.warning("⚠️ Please check your Secrets configuration for the Spreadsheet URL.")
else:
    # 5. DEFINE TABS
    tab1, tab2 = st.tabs(["👤 Patients (Pat)", "🧊 Models (Cast)"])

    # Sidebar Filter for Date Range
    st.sidebar.subheader("Global Date Filter")
    
    with tab1:
        # Explicitly load "Pattients Granit" sheet 
        df_pat, col_p = load_sheet_data(current_url, "Pattients Granit")
        
        if not df_pat.empty:
            # Metrics & Charts logic
            approved = len(df_pat[df_pat['Quality Check (um)'] == 'APPROVED'])
            st.metric("Total Patient Scans", len(df_pat), f"Payment: ${approved * pay_per_scan:,.2f}")
            
            fig_p = px.bar(df_pat, x='Week', color='Quality Check (um)', 
                          color_discrete_map=quality_colors, title="Patient Quality Trend")
            st.plotly_chart(fig_p, use_container_width=True)
            st.dataframe(df_pat)
        else:
            st.info("No data found in 'Pattients Granit' sheet.")

    with tab2:
        # Explicitly load "Cast Granit" sheet 
        df_cast, col_c = load_sheet_data(current_url, "Cast Granit")
        
        if not df_cast.empty:
            # Metrics & Charts logic
            approved_c = len(df_cast[df_cast['Quality Check (um)'] == 'APPROVED'])
            st.metric("Total Cast Scans", len(df_cast), f"Payment: ${approved_c * pay_per_scan:,.2f}")
            
            fig_c = px.bar(df_cast, x='Week', color='Quality Check (um)', 
                          color_discrete_map=quality_colors, title="Cast Quality Trend")
            st.plotly_chart(fig_c, use_container_width=True)
            st.dataframe(df_cast)
        else:
            st.info("No data found in 'Cast Granit' sheet. Check the sheet name in your Google File.")
