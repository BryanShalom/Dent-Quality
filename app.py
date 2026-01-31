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

# --- SIDEBAR: CONFIGURACIÓN DE PRECIOS ---
st.sidebar.header("🛠️ Dashboard Control")
selected_client = st.sidebar.selectbox("1. Select Client", list(CLIENTS.keys()))
category = st.sidebar.radio("2. Select Category", ["Patients", "Cast"])

st.sidebar.subheader("💰 Pricing per Status")
pay_approved = st.sidebar.number_input("Approved ($)", value=0.50, step=0.05)
pay_partial = st.sidebar.number_input("Partially Approved ($)", value=0.25, step=0.05)

# Colores consistentes para los estados
quality_colors = {
    'APPROVED': '#28a745',          # Verde
    'PARTIALLY APROVED': '#ff8c00', # Naranja
    'REPROVED': '#dc3545'           # Rojo
}

# 2. FUNCIÓN DE CARGA
@st.cache_data(ttl=60)
def load_by_gid(base_url, gid):
    try:
        csv_url = f"{base_url}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)
        if df.empty: return pd.DataFrame()
        
        df.columns = [str(c).strip() for c in df.columns]
        col_id = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        
        def extract_date(text):
            m = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
            return m.group(1) if m else None

        df['date_str'] = df[col_id].apply(extract_date)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        return df
    except Exception as e:
        st.error(f"Error accessing sheet: {e}")
        return pd.DataFrame()

# 3. LÓGICA PRINCIPAL
client_info = CLIENTS[selected_client]
df = load_by_gid(client_info["url"], client_info["sheets"][category])

if not df.empty:
    st.sidebar.subheader("📅 Filter Dates")
    min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
    date_range = st.sidebar.date_input("Date Range", [min_d, max_d])
    
    if isinstance(date_range, list) and len(date_range) == 2:
        df_filtered = df[(df['Date'].dt.date >= date_range[0]) & (df['Date'].dt.date <= date_range[1])]
    else:
        df_filtered = df

    st.title(f"📊 {selected_client} Analysis: {category}")
    
    # --- CÁLCULO DE MÉTRICAS ---
    appr_count = len(df_filtered[df_filtered['Quality Check (um)'] == 'APPROVED'])
    partial_count = len(df_filtered[df_filtered['Quality Check (um)'] == 'PARTIALLY APROVED'])
    reproved_count = len(df_filtered[df_filtered['Quality Check (um)'] == 'REPROVED'])
    
    total_earnings = (appr_count * pay_approved) + (partial_count * pay_partial)

    # Mostrar Métricas en 4 columnas
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Approved ✅", appr_count)
    m2.metric("Partial ⚠️", partial_count)
    m3.metric("Reproved ❌", reproved_count)
    m4.metric("Total Earnings", f"${total_earnings:,.2f}")

    st.divider()

    # Gráficos
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Weekly Evolution")
        fig_bar = px.bar(df_filtered, x='Week', color='Quality Check (um)', 
                        barmode='group', color_discrete_map=quality_colors,
                        category_orders={"Quality Check (um)": ["APPROVED", "PARTIALLY APROVED", "REPROVED"]})
        st.plotly_chart(fig_bar, use_container_width=True)
    with c2:
        st.subheader("Quality Share")
        fig_pie = px.pie(df_filtered, names='Quality Check (um)', 
                        color='Quality Check (um)', color_discrete_map=quality_colors, hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    with st.expander("🔍 View Raw Data"):
        st.dataframe(df_filtered.drop(columns=['date_str']), use_container_width=True)
else:
    st.warning(f"No data found for {selected_client} - {category}. Check permissions.")
