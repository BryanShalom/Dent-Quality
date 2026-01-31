import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CLIENTS & SECRETS
CLIENTS = {
    "Granit": st.secrets.get("URL_GRANIT", "").strip(),
    "Cruz": st.secrets.get("URL_CRUZ", "").strip()
}

st.sidebar.header("Settings")
selected_client = st.sidebar.selectbox("Select Client", list(CLIENTS.keys()))
pay_per_scan = st.sidebar.number_input("Payment per approved scan ($/€)", value=0.50, step=0.05)

quality_colors = {
    'APPROVED': '#28a745',
    'PARTIALLY APROVED': '#ff8c00',
    'REPPROVED': '#dc3545'
}

# 2. DATA LOADING
@st.cache_data(ttl=60)
def load_data(base_url, sheet_name):
    try:
        # Construimos la URL de exportación directa
        export_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={sheet_name.replace(' ', '%20')}"
        df = pd.read_csv(export_url)
        
        if df.empty:
            return pd.DataFrame()

        df.columns = [str(c).strip() for c in df.columns]
        
        # Identificar columna
        col_id = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        
        def get_date(text):
            match = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
            return match.group(1) if match else None

        df['date_str'] = df[col_id].apply(get_date)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        
        return df
    except Exception:
        return pd.DataFrame()

# --- INTERFACE ---
url = CLIENTS[selected_client]

if not url:
    st.warning("⚠️ No URL found in Secrets.")
else:
    tab1, tab2 = st.tabs(["👤 Patients", "🧊 Models (Cast)"])

    with tab1:
        df_p = load_data(url, "Patients")
        if not df_p.empty:
            appr = len(df_p[df_p['Quality Check (um)'] == 'APPROVED'])
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Patients", len(df_p))
            c2.metric("Approved ✅", appr)
            c3.metric("Estimated Payment", f"${appr * pay_per_scan:,.2f}")
            
            fig = px.bar(df_p, x='Week', color='Quality Check (um)', 
                         barmode='group', color_discrete_map=quality_colors)
            # AÑADIMOS KEY ÚNICA AQUÍ
            st.plotly_chart(fig, use_container_width=True, key="chart_patients")
            st.dataframe(df_p, use_container_width=True, key="table_patients")
        else:
            st.error("No data found in 'Patients' sheet. Check tab name and sharing settings.")

    with tab2:
        df_c = load_data(url, "Casts")
        if not df_c.empty:
            appr_c = len(df_c[df_c['Quality Check (um)'] == 'APPROVED'])
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Casts", len(df_c))
            c2.metric("Approved ✅", appr_c)
            c3.metric("Estimated Payment", f"${appr_c * pay_per_scan:,.2f}")
            
            fig_c = px.bar(df_c, x='Week', color='Quality Check (um)', 
                           barmode='group', color_discrete_map=quality_colors)
            # AÑADIMOS KEY ÚNICA AQUÍ
            st.plotly_chart(fig_c, use_container_width=True, key="chart_casts")
            st.dataframe(df_c, use_container_width=True, key="table_casts")
        else:
            st.error("No data found in 'Casts' sheet. Check tab name and sharing settings.")
