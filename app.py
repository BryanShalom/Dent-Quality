import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CONFIGURACIÓN DE CLIENTES
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

# --- SISTEMA DE ACCESO ---
if 'auth' not in st.session_state:
    st.session_state['auth'] = None

if st.session_state['auth'] is None:
    st.title("🔐 Acceso")
    u = st.text_input("Nombre:").strip()
    if u:
        matching = next((k for k in CLIENT_CONFIG.keys() if k.lower() == u.lower()), None)
        if matching:
            st.session_state['auth'] = matching
            st.rerun()
        else:
            st.error("Nombre no reconocido.")
    st.stop()

client = st.session_state['auth']
info = CLIENT_CONFIG[client]

# --- SIDEBAR (CONTROL) ---
st.sidebar.title(f"💼 {client}")
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state['auth'] = None
    st.rerun()

st.sidebar.divider()
category = st.sidebar.radio("Categoría", ["Patients", "Cast"])
p_app = st.sidebar.number_input("Precio Approved ($)", value=0.50)
p_par = st.sidebar.number_input("Precio Partial ($)", value=0.25)

# --- CARGA DE DATOS ---
@st.cache_data(ttl=60)
def load_data(url, gid):
    try:
        # Línea corregida: Aseguramos que el f-string esté bien cerrado
        csv_url = f"{url}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)
        df.columns = [str(c).strip() for c in df.columns]
        cid = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        
        def process_row(val):
            val = str(val)
            date_m = re.search(r'(\d{4}_\d{2}_\d{2})', val)
            clean_val = val.replace(date_m.group(1), "") if date_m else val
            num_m = re.search(r'(\d{3,5})', clean_val)
            return pd.Series([date_m.group(1) if date_m else None, int(num_m.group(1)) if num_m else 0])

        df[['date_str', 'p_num']] = df[cid].apply(process_row)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df['Date'] = df['Date'].fillna(pd.Timestamp('2024-01-01'))
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        return df, cid
    except:
        return pd.DataFrame(), None

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
