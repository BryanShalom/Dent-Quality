import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re
from urllib.parse import quote # Para limpiar los espacios en los nombres

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CLIENTS & SECRETS
CLIENTS = {
    "Granit": st.secrets.get("URL_GRANIT", ""),
    "Cruz": st.secrets.get("URL_CRUZ", "")
}

st.sidebar.header("Settings")
selected_client = st.sidebar.selectbox("Select Client", list(CLIENTS.keys()))
pay_per_scan = st.sidebar.number_input("Payment per approved scan ($/€)", value=0.50, step=0.05)

quality_colors = {
    'APPROVED': '#28a745',
    'PARTIALLY APROVED': '#ff8c00',
    'REPPROVED': '#dc3545'
}

conn = st.connection("gsheets", type=GSheetsConnection)

# 2. FUNCIÓN DE CARGA ROBUSTA
@st.cache_data(ttl=60)
def load_data_safe(url, sheet_name):
    try:
        # Codificamos el nombre de la hoja (Espacios -> %20)
        safe_sheet_name = quote(sheet_name)
        
        # Leemos usando el nombre seguro
        df = conn.read(spreadsheet=url, worksheet=sheet_name)
        
        if df is None or df.empty:
            return pd.DataFrame(), f"Sheet '{sheet_name}' is empty."

        df.columns = df.columns.str.strip()
        col_id = 'Patient' if 'Patient' in df.columns else ('Cast' if 'Cast' in df.columns else df.columns[0])
        
        def get_date(text):
            match = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
            return match.group(1) if match else None

        df['date_str'] = df[col_id].apply(get_date)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

# --- DASHBOARD ---
current_url = CLIENTS[selected_client]

if not current_url:
    st.warning("⚠️ No URL found in Secrets.")
else:
    tab1, tab2 = st.tabs(["👤 Patients", "🧊 Models (Cast)"])

    with tab1:
        # El nombre debe ser EXACTO al de la pestaña de abajo en tu Excel
        df_pat, err_pat = load_data_safe(current_url, "Pattients Granit")
        
        if not df_pat.empty:
            appr = len(df_pat[df_pat['Quality Check (um)'] == 'APPROVED'])
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Patients", len(df_pat))
            c2.metric("Approved ✅", appr)
            c3.metric("Estimated Payment", f"${appr * pay_per_scan:,.2f}")
            
            fig = px.bar(df_pat, x='Week', color='Quality Check (um)', 
                         barmode='group', color_discrete_map=quality_colors)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_pat)
        else:
            st.error(f"Error: {err_pat}")

    with tab2:
        df_cast, err_cast = load_data_safe(current_url, "Cast Granit")
        
        if not df_cast.empty:
            appr_c = len(df_cast[df_cast['Quality Check (um)'] == 'APPROVED'])
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Casts", len(df_cast))
            c2.metric("Approved ✅", appr_c)
            c3.metric("Estimated Payment", f"${appr_c * pay_per_scan:,.2f}")
            
            fig_c = px.bar(df_cast, x='Week', color='Quality Check (um)', 
                           barmode='group', color_discrete_map=quality_colors)
            st.plotly_chart(fig_c, use_container_width=True)
            st.dataframe(df_cast)
        else:
            st.error(f"Error: {err_cast}")
