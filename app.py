import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CONFIGURACIÓN DE CLIENTES
CLIENTS = {
    "Granit": {
        "url": "https://docs.google.com/spreadsheets/d/1nTEL5w5mEMXeyolUC8friEmRCix03aQ8NxYV8R63pLE",
        "sheets": {"Patients": "0", "Cast": "224883546"}
    },
    "Cruz": {
        "url": "https://docs.google.com/spreadsheets/d/1F83LKwGeHxmSqvwqulmJLxx5VxQXYs5_mobIHEAKREQ",
        "sheets": {"Patients": "0", "Cast": "224883546"}
    }
}

# --- SIDEBAR ---
st.sidebar.header("🛠️ Dashboard Control")
selected_client = st.sidebar.selectbox("1. Seleccionar Cliente", list(CLIENTS.keys()))
category = st.sidebar.radio("2. Categoría", ["Patients", "Cast"])

st.sidebar.subheader("💰 Precios por Estado")
pay_approved = st.sidebar.number_input("Approved ($)", value=0.50, step=0.05)
pay_partial = st.sidebar.number_input("Partially Approved ($)", value=0.25, step=0.05)

quality_colors = {'APPROVED': '#28a745', 'PARTIALLY APROVED': '#ff8c00', 'REPROVED': '#dc3545'}

# 2. PROCESAMIENTO DE DATOS
@st.cache_data(ttl=60)
def load_and_process(base_url, gid):
    try:
        csv_url = f"{base_url}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)
        if df.empty: return pd.DataFrame(), None
        
        df.columns = [str(c).strip() for c in df.columns]
        col_id = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        
        def process_row(text):
            text = str(text)
            date_m = re.search(r'(\d{4}_\d{2}_\d{2})', text)
            num_m = re.search(r'_(\d{3,5})', text) 
            d_val = date_m.group(1) if date_m else None
            n_val = int(num_m.group(1)) if num_m else None
            return pd.Series([d_val, n_val])

        df[['date_str', 'p_num']] = df[col_id].apply(process_row)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        
        if df['p_num'].isnull().all():
            df['p_num'] = range(1, len(df) + 1)
        else:
            df['p_num'] = df['p_num'].fillna(0).astype(int)
            
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        return df, col_id
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame(), None

# 3. FILTRADO
client_info = CLIENTS[selected_client]
df_raw, col_name = load_and_process(client_info["url"], client_info["sheets"][category])

if not df_raw.empty:
    st.sidebar.divider()
    filter_type = st.sidebar.selectbox("🎯 Filtrar por:", ["Rango de Pacientes (ID)", "Rango de Fechas"])

    df_filtered = df_raw.copy()
    if filter_type == "Rango de Pacientes (ID)":
        min_f, max_f = int(df_raw['p_num'].min()), int(df_raw['p_num'].max())
        col_r1, col_r2 = st.sidebar.columns(2)
        start_id = col_r1.number_input("Desde:", value=min_f)
        end_id = col_r2.number_input("Hasta:", value=max_f)
        df_filtered = df_raw[(df_raw['p_num'] >= start_id) & (df_raw['p_num'] <= end_id)]
    else:
        min_d, max_d = df_raw['Date'].min().date(), df_raw['Date'].max().date()
        date_range = st.sidebar.date_input("Seleccionar periodo:", [min_d, max_d])
        if isinstance(date_range, list) and len(date_range) == 2:
            df_filtered = df_raw[(df_raw['Date'].dt.date >= date_range[0]) & (df_filtered['Date'].dt.date <= date_range[1])]

    # --- UI DASHBOARD ---
    st.title(f"📊 {selected_client}: {category}")
    
    if not df_filtered.empty:
        # CÁLCULOS
        appr = len(df_filtered[df_filtered['Quality Check (um)'] == 'APPROVED'])
        part = len(df_filtered[df_filtered['Quality Check (um)'] == 'PARTIALLY APROVED'])
        repr = len(df_filtered[df_filtered['Quality Check (um)'] == 'REPROVED'])
        combined_total = appr + part
        total_money = (appr * pay_approved) + (part * pay_partial)

        # MÉTRICAS CON ESTILO
        m1, m2, m3, m4 = st.columns(4)
        
        # Métrica combinada usando HTML para el texto pequeño
        m1.metric("Approved ✅", appr)
        st.markdown(f"<p style='color: gray; font-size: 0.8em; margin-top: -25px;'>Total incl. Parciales: {combined_total}</p>", unsafe_allow_html=True)
        
        m2.metric("Partial ⚠️", part)
        m3.metric("Reproved ❌", reproved_count := repr) # Variable asignada para claridad
        m4.metric("Total Earnings", f"${total_money:,.2f}")

        st.divider()
        c1, c2 = st.columns([2, 1])
        with c1:
            st.plotly_chart(px.bar(df_filtered, x='Week', color='Quality Check (um)', barmode='group', color_discrete_map=quality_colors), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_filtered, names='Quality Check (um)', color='Quality Check (um)', color_discrete_map=quality_colors, hole=0.4), use_container_width=True)

        with st.expander("🔍 Ver Tabla de Datos"):
            st.dataframe(df_filtered.drop(columns=['date_str', 'p_num']), use_container_width=True)
