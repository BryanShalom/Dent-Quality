import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CONFIGURACIÓN DE CLIENTES Y GIDs (Basado en tus enlaces)
CLIENTS = {
    "Granit": {
        "url": "https://docs.google.com/spreadsheets/d/1nTEL5w5mEMXeyolUC8friEmRCix03aQ8NxYV8R63pLE",
        "sheets": {
            "Patients": "0",
            "Cast": "224883546"
        }
    }
}

st.sidebar.header("🛠️ Dashboard Control")
selected_client = st.sidebar.selectbox("1. Select Client", list(CLIENTS.keys()))

# Selector de categoría (Patients o Cast)
category = st.sidebar.radio("2. Select Category", ["Patients", "Cast"])

pay_per_scan = st.sidebar.number_input("3. Payment per approved scan ($)", value=0.50, step=0.05)
quality_colors = {'APPROVED': '#28a745', 'PARTIALLY APROVED': '#ff8c00', 'REPPROVED': '#dc3545'}

# 2. FUNCIÓN DE CARGA POR GID
@st.cache_data(ttl=60)
def load_by_gid(base_url, gid):
    try:
        # Construimos la URL de descarga directa usando el GID proporcionado
        csv_url = f"{base_url}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)
        
        if df.empty: return pd.DataFrame()
        
        # Limpiar nombres de columnas
        df.columns = [str(c).strip() for c in df.columns]
        
        # Identificar la columna que contiene la fecha (Patient o Cast)
        col_id = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        
        # Extraer fecha con formato YYYY_MM_DD
        def extract_date(text):
            m = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
            return m.group(1) if m else None

        df['date_str'] = df[col_id].apply(extract_date)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        
        # Limpiar filas sin fecha válida
        df = df.dropna(subset=['Date'])
        
        # Crear columna de semana para el gráfico
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        return df
    except Exception as e:
        st.error(f"Error accessing sheet GID {gid}: {e}")
        return pd.DataFrame()

# 3. RENDERIZADO DEL DASHBOARD
client_info = CLIENTS[selected_client]
current_gid = client_info["sheets"][category]

df = load_by_gid(client_info["url"], current_gid)

if not df.empty:
    # Filtro de fechas en el sidebar
    st.sidebar.subheader("4. Filter Dates")
    min_date = df['Date'].min().date()
    max_date = df['Date'].max().date()
    date_range = st.sidebar.date_input("Date Range", [min_date, max_date])
    
    # Aplicar filtro de fecha
    if isinstance(date_range, list) and len(date_range) == 2:
        df_filtered = df[(df['Date'].dt.date >= date_range[0]) & (df['Date'].dt.date <= date_range[1])]
    else:
        df_filtered = df

    st.title(f"📊 {selected_client} Scan Analysis: {category}")
    
    # Métricas principales
    m1, m2, m3 = st.columns(3)
    total_scans = len(df_filtered)
    approved_scans = len(df_filtered[df_filtered['Quality Check (um)'] == 'APPROVED'])
    
    m1.metric(f"Total {category}", total_scans)
    m2.metric("Approved ✅", approved_scans)
    m3.metric("Estimated Earnings", f"${approved_scans * pay_per_scan:,.2f}")

    st.divider()

    # Gráficos
    col_chart1, col_chart2 = st.columns([2, 1])
    
    with col_chart1:
        st.subheader("Weekly Evolution")
        fig_bar = px.bar(df_filtered, x='Week', color='Quality Check (um)', 
                        barmode='group', color_discrete_map=quality_colors)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_chart2:
        st.subheader("Quality Distribution")
        fig_pie = px.pie(df_filtered, names='Quality Check (um)', 
                        color='Quality Check (um)', color_discrete_map=quality_colors,
                        hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    # Tabla detallada
    with st.expander("🔍 View Raw Data Table"):
        st.dataframe(df_filtered.drop(columns=['date_str']), use_container_width=True)
else:
    st.warning(f"No data found for {category}. Verify the GID and that the sheet is shared as 'Anyone with the link can view'.")
