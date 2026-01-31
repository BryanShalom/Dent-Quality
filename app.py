import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re

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

# 2. FUNCIÓN DE CARGA CON DIAGNÓSTICO
@st.cache_data(ttl=60)
def load_data_with_check(url, sheet_name):
    try:
        # Intentamos leer la pestaña específica
        df = conn.read(spreadsheet=url, worksheet=sheet_name)
        
        if df is None or df.empty:
            return pd.DataFrame(), f"Sheet '{sheet_name}' is empty or not found."

        # Limpieza de columnas
        df.columns = df.columns.str.strip()
        
        # Buscar columna de ID (Patient o Cast)
        col_name = next((c for c in df.columns if c in ['Patient', 'Cast']), df.columns[0])
        
        # Extraer fecha
        def get_date(text):
            match = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
            return match.group(1) if match else None

        df['date_str'] = df[col_name].apply(get_date)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        
        # Agrupar por semana
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

# --- LÓGICA PRINCIPAL ---
current_url = CLIENTS[selected_client]

if not current_url:
    st.warning("⚠️ URL not found. Please check your Streamlit Secrets.")
else:
    # MOSTRAR TABS
    tab1, tab2 = st.tabs(["👤 Patients", "🧊 Models (Cast)"])

    with tab1:
        # Usando el nombre exacto de tus archivos: "Pattients Granit"
        df_pat, error_pat = load_data_with_check(current_url, "Pattients Granit")
        
        if not df_pat.empty:
            # Filtro de fecha
            min_d, max_d = df_pat['Date'].min().date(), df_pat['Date'].max().date()
            
            # Métricas
            appr = len(df_pat[df_pat['Quality Check (um)'] == 'APPROVED'])
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Patients", len(df_pat))
            c2.metric("Approved ✅", appr)
            c3.metric("Total Payment", f"${appr * pay_per_scan:,.2f}")
            
            # Gráfico
            fig = px.bar(df_pat, x='Week', color='Quality Check (um)', 
                         barmode='group', color_discrete_map=quality_colors)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_pat)
        else:
            st.error(f"Error loading Patients: {error_pat}")
            st.info("💡 Hint: Make sure the tab name is exactly 'Pattients Granit' in Google Sheets.")

    with tab2:
        df_cast, error_cast = load_data_with_check(current_url, "Cast Granit")
        
        if not df_cast.empty:
            appr_c = len(df_cast[df_cast['Quality Check (um)'] == 'APPROVED'])
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Casts", len(df_cast))
            c2.metric("Approved ✅", appr_c)
            c3.metric("Total Payment", f"${appr_c * pay_per_scan:,.2f}")
            
            fig_c = px.bar(df_cast, x='Week', color='Quality Check (um)', 
                           barmode='group', color_discrete_map=quality_colors)
            st.plotly_chart(fig_c, use_container_width=True)
            st.dataframe(df_cast)
        else:
            st.error(f"Error loading Casts: {error_cast}")
            st.info("💡 Hint: Make sure the tab name is exactly 'Cast Granit'.")

# 3. HERRAMIENTA DE AYUDA (Sidebar)
with st.sidebar.expander("🔍 Help & Diagnostics"):
    st.write("If you see errors, verify that:")
    st.write("1. Sheet names are exactly 'Pattients Granit' and 'Cast Granit'.")
    st.write("2. The Google Sheet is shared as 'Anyone with the link can view'.")
