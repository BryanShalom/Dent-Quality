import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CONFIGURACIÓN
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

# --- ACCESO ---
if 'auth' not in st.session_state:
    st.session_state['auth'] = None

if st.session_state['auth'] is None:
    st.title("🔐 Acceso")
    u = st.text_input("Cuenta (Granit/Cruz):").strip()
    if u.lower() in [k.lower() for k in CLIENT_CONFIG.keys()]:
        st.session_state['auth'] = "Cruz" if u.lower() == "cruz" else "Granit"
        st.rerun()
    st.stop()

client = st.session_state['auth']
info = CLIENT_CONFIG[client]

# --- SIDEBAR ---
st.sidebar.title(f"💼 {client}")
category = st.sidebar.radio("Categoría", ["Patients", "Cast"])
p_app = st.sidebar.number_input("Precio Approved ($)", value=0.50)
p_par = st.sidebar.number_input("Precio Partial ($)", value=0.25)

@st.cache_data(ttl=60)
def load_data(url, gid):
    try:
        df = pd.read_csv(f"{url}/export?format=csv&gid={gid}")
        df.columns = [str(c).strip() for c in df.columns]
        cid = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        def proc(x):
            d = re.search(r'(\d{4}_\d{2}_\d_2})', str(x))
            n = re.search(r'_(\d{3,5})', str(x))
            return pd.Series([d.group(1) if d else None, int(n.group(1)) if n else 0])
        df[['date_str', 'p_num']] = df[cid].apply(proc)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        return df, cid
    except: return pd.DataFrame(), None

df_raw, col_id_name = load_data(info["url"], info["sheets"][category])

if not df_raw.empty:
    st.sidebar.divider()
    filter_mode = st.sidebar.selectbox("🎯 Filtrar por:", ["Rango de IDs", "Rango de Fechas"])
    
    if filter_mode == "Rango de IDs":
        min_v, max_v = int(df_raw['p_num'].min()), int(df_raw['p_num'].max())
        c1, c2 = st.sidebar.columns(2)
        start = c1.number_input("Desde:", value=min_v)
        end = c2.number_input("Hasta:", value=max_v)
        df_f = df_raw[(df_raw['p_num'] >= start) & (df_raw['p_num'] <= end)]
    else:
        date_range = st.sidebar.date_input("Periodo:", [df_raw['Date'].min().date(), df_raw['Date'].max().date()])
        if isinstance(date_range, list) and len(date_range) == 2:
            df_f = df_raw[(df_raw['Date'].dt.date >= date_range[0]) & (df_raw['Date'].dt.date <= date_range[1])]
        else:
            df_f = df_raw

    # --- CÁLCULOS DEL RESUMEN ---
    total_patients_collected = len(df_f) # Todos los escaneos en el rango
    app_n = len(df_f[df_f['Quality Check (um)'] == 'APPROVED'])
    par_n = len(df_f[df_f['Quality Check (um)'] == 'PARTIALLY APROVED'])
    
    # Patients Accepted = Approved + (Partial * ratio)
    ratio = p_par / p_app if p_app > 0 else 0.5
    patients_accepted = round(app_n + (par_n * ratio), 1)
    
    total_money = (app_n * p_app) + (par_n * p_par)

    # --- UI DASHBOARD ---
    st.title(f"📊 Resumen de Cobro: {client}")
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Total Patients Collected", total_patients_collected)
    with col_b:
        st.metric("Patients Accepted", patients_accepted)
    with col_c:
        st.metric("Total Earnings", f"${total_money:,.2f}")

    st.divider()

    # --- BOTÓN DE DESCARGA ---
    # Creamos un texto formateado para el CSV
    resumen_texto = f"RESUMEN DE COBRO - {client}\n"
    resumen_texto += f"Total Patients Collected: {total_patients_collected}\n"
    resumen_texto += f"Patients Accepted: {patients_accepted}\n"
    resumen_texto += f"Total Earnings: ${total_money:.2f}\n\n"
    resumen_texto += df_f[[col_id_name, 'Quality Check (um)', 'Date']].to_csv(index=False)

    st.sidebar.download_button(
        label="📥 Descargar Resumen",
        data=resumen_texto,
        file_name=f"Resumen_{client}.csv",
        mime="text/csv"
    )

    st.subheader("Detalle del Rango Seleccionado")
    st.dataframe(df_f.drop(columns=['date_str', 'p_num']), use_container_width=True)
