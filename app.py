import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Quality Control Access", layout="wide")

# 1. CONFIGURACIÓN CENTRALIZADA
CLIENT_CONFIG = {
    "Granit": {
        "url": "https://docs.google.com/spreadsheets/d/1nTEL5w5mEMXeyolUC8friEmRCix03aQ8NxYV8R63pLE",
        "sheets": {"Patients": "0", "Cast": "224883546"}
    },
    "Cruz": {
        "url": "https://docs.google.com/spreadsheets/d/1F83LKwGeHxmSqvwqulmJLxx5VxQXYs5_mobIHEAKREQ",
        "sheets": {"Patients": "0", "Cast": "224883546"}
    }
}

# --- PANTALLA DE ACCESO SIMPLIFICADA ---
if 'auth_client' not in st.session_state:
    st.session_state['auth_client'] = None

if st.session_state['auth_client'] is None:
    st.title("🔐 Acceso al Dashboard")
    # Usamos text_input normal, no tipo password para que sea más amigable
    user_input = st.text_input("Escriba el nombre de la cuenta (Granit o Cruz):").strip()
    
    if user_input:
        # Validación sin importar mayúsculas/minúsculas
        matching_client = next((c for c in CLIENT_CONFIG.keys() if c.lower() == user_input.lower()), None)
        
        if matching_client:
            st.session_state['auth_client'] = matching_client
            st.rerun()
        else:
            st.error("Cuenta no encontrada. Verifique el nombre.")
    st.stop()

# --- DASHBOARD AUTENTICADO ---
selected_client = st.session_state['auth_client']
client_info = CLIENT_CONFIG[selected_client]

if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state['auth_client'] = None
    st.rerun()

st.sidebar.header(f"💼 Cliente: {selected_client}")
category = st.sidebar.radio("Categoría", ["Patients", "Cast"])

st.sidebar.subheader("💰 Precios")
pay_app = st.sidebar.number_input("Approved ($)", value=0.50, step=0.05)
pay_par = st.sidebar.number_input("Partially Approved ($)", value=0.25, step=0.05)

quality_colors = {'APPROVED': '#28a745', 'PARTIALLY APROVED': '#ff8c00', 'REPROVED': '#dc3545'}

# 2. CARGA Y PROCESAMIENTO
@st.cache_data(ttl=60)
def load_data(base_url, gid):
    try:
        csv_url = f"{base_url}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)
        if df.empty: return pd.DataFrame(), None
        df.columns = [str(c).strip() for c in df.columns]
        col_id = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        
        def process(text):
            text = str(text)
            date_m = re.search(r'(\d{4}_\d{2}_\d{2})', text)
            num_m = re.search(r'_(\d{3,5})', text) 
            return pd.Series([date_m.group(1) if date_m else None, int(num_m.group(1)) if num_m else None])

        df[['date_str', 'p_num']] = df[col_id].apply(process)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        df['p_num'] = df['p_num'].fillna(0).astype(int)
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        return df, col_id
    except: return pd.DataFrame(), None

df_raw, col_name = load_data(client_info["url"], client_info["sheets"][category])

if not df_raw.empty:
    st.sidebar.divider()
    filter_type = st.sidebar.selectbox("🎯 Filtrar por:", ["Rango de Pacientes (ID)", "Rango de Fechas"])
    df_filtered = df_raw.copy()

    if filter_type == "Rango de Pacientes (ID)":
        min_f, max_f = int(df_raw['p_num'].min()), int(df_raw['p_num'].max())
        c1, c2 = st.sidebar.columns(2)
        start_id = c1.number_input("Desde:", value=min_f)
        end_id = c2.number_input("Hasta:", value=max_f)
        df_filtered = df_raw[(df_raw['p_num'] >= start_id) & (df_raw['p_num'] <= end_id)]
    else:
        date_range = st.sidebar.date_input("Periodo:", [df_raw['Date'].min().date(), df_raw['Date'].max().date()])
        if isinstance(date_range, list) and len(date_range) == 2:
            df_filtered = df_raw[(df_raw['Date'].dt.date >= date_range[0]) & (df_raw['Date'].dt.date <= date_range[1])]

    # --- UI DASHBOARD ---
    st.title(f"📊 Dashboard {selected_client}: {category}")
    
    if not df_filtered.empty:
        app_n = len(df_filtered[df_filtered['Quality Check (um)'] == 'APPROVED'])
        par_n = len(df_filtered[df_filtered['Quality Check (um)'] == 'PARTIALLY APROVED'])
        rep_n = len(df_filtered[df_filtered['Quality Check (um)'] == 'REPROVED'])
        
        ratio = pay_par / pay_app if pay_app > 0 else 0
        equiv_total = round(app_n + (par_n * ratio), 1)
        total_cash = (app_n * pay_app) + (par_n * pay_par)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Approved ✅", app_n)
        st.markdown(f"<div style='margin-top: -25px;'><span style='color: #555; font-size: 1.1em;'>Total Scans: </span><span style='color: #28a745; font-size: 1.1em; font-weight: 700;'>{equiv_total}</span></div>", unsafe_allow_html=True)
        m2.metric("Partial ⚠️", par_n)
        m3.metric("Reproved ❌", rep_n)
        m4.metric("Total Earnings", f"${total_cash:,.2f}")

        st.divider()
        c1, c2 = st.columns([2, 1])
        with c1: st.plotly_chart(px.bar(df_filtered, x='Week', color='Quality Check (um)', barmode='group', color_discrete_map=quality_colors), use_container_width=True)
        with c2: st.plotly_chart(px.pie(df_filtered, names='Quality Check (um)', color='Quality Check (um)', color_discrete_map=quality_colors, hole=0.4), use_container_width=True)
