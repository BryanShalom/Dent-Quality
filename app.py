import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CONFIGURACIÓN DE CLIENTES, URLs y GIDs
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
selected_client = st.sidebar.selectbox("1. Select Client", list(CLIENTS.keys()))
category = st.sidebar.radio("2. Select Category", ["Patients", "Cast"])
pay_per_scan = st.sidebar.number_input("3. Payment per approved scan ($)", value=0.50, step=0.05)

quality_colors = {
    'APPROVED': '#28a745', 
    'PARTIALLY APROVED': '#ff8c00', 
    'REPPROVED': '#dc3545'
}

# 2. FUNCIÓN DE CARGA POR GID
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
    # Filtro de fechas
    st.sidebar.subheader("4. Filter Dates")
    min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
    date_range = st.sidebar.date_input("Date Range", [min_d, max_d])
    
    if isinstance(date_range, list) and len(date_range) == 2:
        df_filtered = df[(df['Date'].dt.date >= date_range[0]) & (df['Date'].dt.date <= date_range[1])]
    else:
        df_filtered = df

    # --- UI ---
    st.title(f"📊 {selected_client} Analysis: {category}")
    
    # Métricas
    m1, m2, m3 = st.columns(3)
    appr_count = len(df_filtered[df_filtered['Quality Check (um)'] == 'APPROVED'])
    m1.metric(f"Total {category}", len(df_filtered))
    m2.metric("Approved ✅", appr_count)
    m3.metric("Earnings", f"${appr_count * pay_per_scan:,.2f}")

    st.divider()

    # Gráficos
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Weekly Evolution")
        fig_bar = px.bar(df_filtered, x='Week', color='Quality Check (um)', 
                        barmode='group', color_discrete_map=quality_colors)
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
