import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

st.set_page_config(page_title="Quality Dashboard", layout="wide")

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

# --- SIDEBAR ---
st.sidebar.title(f"💼 {client}")
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state['auth'] = None
    st.rerun()

st.sidebar.divider()
category = st.sidebar.radio("Categoría", ["Patients", "Cast"])
p_app = st.sidebar.number_input("Precio Approved ($)", value=0.50)
p_par = st.sidebar.number_input("Precio Partial ($)", value=0.25)

# --- CARGA Y NORMALIZACIÓN ---
@st.cache_data(ttl=10)
def load_data(url, gid):
    try:
        csv_url = f"{url}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)
        df.columns = [str(c).strip() for c in df.columns]
        cid = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        qcol = 'Quality Check (um)'
        
        # Filtro de seguridad
        df = df[df[cid].notna() & df[qcol].notna()].copy()
        
        # Normalización para errores de dedo (REPPROVED, REPROBADO, etc)
        def normalize(val):
            v = str(val).upper()
            if "PARTIAL" in v: return "PARTIALLY APROVED"
            if "REP" in v: return "REPROVED"
            if "APP" in v: return "APPROVED"
            return v

        df[qcol] = df[qcol].apply(normalize)

        def process_id(val):
            val = str(val)
            date_m = re.search(r'(\d{4}_\d{2}_\d{2})', val)
            num_m = re.search(r'(\d{3,5})', val.replace(date_m.group(1), "") if date_m else val)
            return pd.Series([date_m.group(1) if date_m else None, int(num_m.group(1)) if num_m else 0])

        df[['date_str', 'p_num']] = df[cid].apply(process_id)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df[df['Date'].notna() & (df['p_num'] > 0)].copy()
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        return df, cid
    except:
        return pd.DataFrame(), None

df_raw, col_id_name = load_data(info["url"], info["sheets"][category])

if not df_raw.empty:
    st.sidebar.divider()
    f_mode = st.sidebar.selectbox("🎯 Filtrar por:", ["Rango de IDs", "Rango de Fechas"])
    
    if f_mode == "Rango de IDs":
        min_v, max_v = int(df_raw['p_num'].min()), int(df_raw['p_num'].max())
        c1, c2 = st.sidebar.columns(2)
        start, end = c1.number_input("Desde:", value=min_v), c2.number_input("Hasta:", value=max_v)
        df_f = df_raw[(df_raw['p_num'] >= start) & (df_raw['p_num'] <= end)].copy()
    else:
        dr = st.sidebar.date_input("Periodo:", [df_raw['Date'].min().date(), df_raw['Date'].max().date()])
        if isinstance(dr, (list, tuple)) and len(dr) == 2:
            df_f = df_raw[(df_raw['Date'].dt.date >= dr[0]) & (df_raw['Date'].dt.date <= dr[1])].copy()
        else:
            df_f = df_raw.copy()

    # --- CÁLCULOS ---
    app_n = len(df_f[df_f['Quality Check (um)'] == 'APPROVED'])
    par_n = len(df_f[df_f['Quality Check (um)'] == 'PARTIALLY APROVED'])
    rep_n = len(df_f[df_f['Quality Check (um)'] == 'REPROVED'])
    acc_n = round(app_n + (par_n * (p_par/p_app if p_app > 0 else 0.5)), 1)
    money = (app_n * p_app) + (par_n * p_par)

    # --- UI ---
    st.title(f"📊 Dashboard {client}: {category}")
    m = st.columns(5)
    m[0].metric("Total Coll.", len(df_f))
    m[1].metric("Approved ✅", app_n)
    st.markdown(f"<div style='margin-top:-25px; margin-left: 21%;'><span style='color:#28a745; font-weight:700'>Total Scans: {acc_n}</span></div>", unsafe_allow_html=True)
    m[2].metric("Partial ⚠️", par_n)
    m[3].metric("Reproved ❌", rep_n)
    m[4].metric("Earnings", f"${money:,.2f}")

    st.divider()
    c1, c2 = st.columns([2, 1])
    colors = {'APPROVED': '#28a745', 'PARTIALLY APROVED': '#ff8c00', 'REPROVED': '#dc3545'}
    
    with c1:
        st.plotly_chart(px.bar(df_f, x='Week', color='Quality Check (um)', barmode='group', color_discrete_map=colors, category_orders={"Quality Check (um)": ["APPROVED", "PARTIALLY APROVED", "REPROVED"]}), use_container_width=True)
    with c2:
        st.plotly_chart(px.pie(df_f, names='Quality Check (um)', hole=0.4, color='Quality Check (um)', color_discrete_map=colors), use_container_width=True)

    # --- DESCARGA ---
    st.sidebar.divider()
    csv_h = f"Total Coll: {len(df_f)}\nScans Accepted: {acc_n}\nReproved: {rep_n}\nEarnings: ${money:.2f}\n\n"
    st.sidebar.download_button("📥 Descargar Reporte", csv_h + df_f[[col_id_name, 'Quality Check (um)', 'Date']].to_csv(index=False), f"Reporte_{client}.csv")
    
    with st.expander("🔍 Ver Tabla"):
        st.dataframe(df_f.drop(columns=['date_str', 'p_num', 'Week']), use_container_width=True)
else:
    st.warning("Sin datos.")
