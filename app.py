import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# Configuración de página
st.set_page_config(page_title="Quality Dashboard", layout="wide")

# Configuración del Cliente
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

# Acceso al cliente
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

# Sidebar
st.sidebar.title(f"💼 {client}")
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state['auth'] = None
    st.rerun()

st.sidebar.divider()
category = st.sidebar.radio("Categoría", ["Patients", "Cast"])
p_app = st.sidebar.number_input("Precio Approved ($)", value=0.50, min_value=0.0)
p_par = st.sidebar.number_input("Precio Partial ($)", value=0.25, min_value=0.0)

# Función de carga de datos
@st.cache_data(ttl=10, allow_output_mutation=True)
def load_data(url, gid, filters=None):
    try:
        csv_url = f"{url}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)
        
        # Limpiar nombres de columnas
        df.columns = [str(c).strip() for c in df.columns]
        cid = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        qcol = 'Quality Check (um)'
        
        # FILTRO CRÍTICO: Eliminar filas donde el ID o la Calidad estén vacíos
        df = df[df[cid].notna() & df[qcol].notna()].copy()

        def process_row(val):
            val = str(val)
            date_m = re.search(r'(\d{4}_\d{2}_\d{2})', val)
            clean_val = val.replace(date_m.group(1) if date_m else "", "")
            num_m = re.search(r'(\d{3,5})', clean_val)
            return pd.Series([date_m.group(1) if date_m else None, int(num_m.group(1)) if num_m else 0])

        df[['date_str', 'p_num']] = df[cid].apply(process_row)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        
        # Solo mantener si tiene fecha válida y p_num > 0
        df = df[df['Date'].notna() & (df['p_num'] > 0)].copy()
        
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        return df, cid
    except Exception as e:
        st.error(f"Hubo un error al cargar los datos: {str(e)}")
        return pd.DataFrame(), str(e)

# Carga los datos
df_raw, col_id_name = load_data(info["url"], info["sheets"][category])

# Verificación si los datos fueron cargados correctamente
if not df_raw.empty:
    # Sidebar para filtros
    st.sidebar.divider()
    filter_mode = st.sidebar.selectbox("🎯 Filtrar por:", ["Rango de IDs", "Rango de Fechas"])
    
    # Filtro por ID
    if filter_mode == "Rango de IDs":
        min_v, max_v = int(df_raw['p_num'].min()), int(df_raw['p_num'].max())
        c1, c2 = st.sidebar.columns(2)
        start = c1.number_input("Desde ID:", value=min_v)
        end = c2.number_input("Hasta ID:", value=max_v)
        df_f = df_raw[(df_raw['p_num'] >= start) & (df_raw['p_num'] <= end)].copy()
    # Filtro por Fechas
    else:
        d_min, d_max = df_raw['Date'].min().date(), df_raw['Date'].max().date()
        dr = st.sidebar.date_input("Periodo:", [d_min, d_max])
        if isinstance(dr, (list, tuple)) and len(dr) == 2:
            df_f = df_raw[(df_raw['Date'].dt.date >= dr[0]) & (df_raw['Date'].dt.date <= dr[1])].copy()
        else:
            df_f = df_raw.copy()

    # Cálculo de métricas
    total_coll = len(df_f)
    app_n = len(df_f[df_f['Quality Check (um)'] == 'APPROVED'])
    par_n = len(df_f[df_f['Quality Check (um)'] == 'PARTIALLY APPROVED'])
    
    ratio = p_par / p_app if p_app > 0 else 0.5
    acc_n = round(app_n + (par_n * ratio), 1)
    money = (app_n * p_app) + (par_n * p_par)

    # Título del Dashboard
    st.title(f"📊 Dashboard {client}: {category}")
    
    # Muestra las métricas en columnas
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Collected", total_coll)
    m2.metric("Approved ✅", app_n)
    st.markdown(f"<div style='margin-top:-25px; margin-left: 25%;'><span style='color:#555; font-size:1.0em'>Total Scans: </span><span style='color:#28a745; font-size:1.0em; font-weight:700'>{acc_n}</span></div>", unsafe_allow_html=True)
    m3.metric("Partial ⚠️", par_n)
    m4.metric("Total Earnings", f"${money:,.2f}")

    # Gráficos
    st.divider()
    col1, col2 = st.columns([2, 1])
    colors = {'APPROVED': '#28a745', 'PARTIALLY APPROVED': '#ff8c00', 'REPROVED': '#dc3545'}
    
    with col1:
        st.plotly_chart(px.bar(df_f, x='Week', color='Quality Check (um)', title="Evolución Semanal", barmode='group', color_discrete_map=colors), use_container_width=True)
    with col2:
        st.plotly_chart(px.pie(df_f, names='Quality Check (um)', hole=0.4, title="Calidad", color='Quality Check (um)', color_discrete_map=colors), use_container_width=True)

    # Descarga de datos
    st.sidebar.divider()
    header = f"""Total Patients Collected: {total_coll}
Patients Accepted: {acc_n}
Total Earnings: ${money:.2f}

"""
    csv_body = df_f[[col_id_name, 'Quality Check (um)', 'Date']].to_csv(index=False)
    st.sidebar.download_button("📥 Descargar Resumen", header + csv_body, f"Reporte_{client}_{category}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")

    with st.expander("🔍 Ver Tabla de Datos"):
        st.dataframe(df_f.drop(columns=['date_str', 'p_num', 'Week']), use_container_width=True)
else:
    st.warning("No hay datos que coincidan con los filtros seleccionados.")
