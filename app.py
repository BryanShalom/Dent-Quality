import streamlit as st
import pandas as pd
import plotly.express as px
import re
import requests

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CLIENTS & SECRETS
CLIENTS = {
    "Granit": st.secrets.get("URL_GRANIT", "").strip(),
    "Cruz": st.secrets.get("URL_CRUZ", "").strip()
}

# --- SIDEBAR SETTINGS ---
st.sidebar.header("🛠️ Dashboard Configuration")
selected_client = st.sidebar.selectbox("1. Select Client", list(CLIENTS.keys()))

# 2. FUNCIÓN PARA DETECTAR TODAS LAS PESTAÑAS (NUEVA)
def get_all_sheet_names(base_url):
    try:
        # Usamos el endpoint de visualización de Google para obtener metadatos
        meta_url = f"{base_url}/gviz/tq?tqx=out:csv&tq=select%20*"
        # Nota: Para obtener nombres de hojas dinámicamente sin API Key, 
        # lo más robusto en Streamlit es dejar que el usuario escriba o 
        # pre-cargar las conocidas, pero aquí intentaremos una técnica de scrape ligero:
        response = requests.get(base_url)
        # Buscamos nombres de hojas dentro del HTML de Google Sheets
        sheets = re.findall(r'gid=\d+&sheet=([^"]+)', response.text)
        if not sheets:
            # Si falla el scrape, devolvemos las básicas por defecto
            return ["Patients", "Casts"]
        return list(set([requests.utils.unquote(s) for s in sheets]))
    except:
        return ["Patients", "Casts"]

# 3. INTERFAZ DINÁMICA
url = CLIENTS[selected_client]

if not url:
    st.warning("⚠️ No URL found in Secrets.")
else:
    # Obtenemos las pestañas actuales del archivo
    available_sheets = get_all_sheet_names(url)
    
    # El usuario ahora selecciona de una lista REAL de lo que hay en Google
    category = st.sidebar.selectbox("2. Select Category (Auto-detected)", available_sheets)

    pay_per_scan = st.sidebar.number_input("3. Payment per approved scan ($/€)", value=0.50, step=0.05)

    quality_colors = {
        'APPROVED': '#28a745',
        'PARTIALLY APROVED': '#ff8c00',
        'REPPROVED': '#dc3545'
    }

    # 4. DATA LOADING FUNCTION
    @st.cache_data(ttl=60)
    def load_data(base_url, sheet_name):
        try:
            export_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={sheet_name.replace(' ', '%20')}"
            df = pd.read_csv(export_url)
            if df.empty: return pd.DataFrame()
            
            df.columns = [str(c).strip() for c in df.columns]
            # Buscamos la columna de ID (puede ser Patient, Cast, o la primera que encuentre)
            col_id = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
            
            def get_date(text):
                match = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
                return match.group(1) if match else None

            df['date_str'] = df[col_id].apply(get_date)
            df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
            df = df.dropna(subset=['Date'])
            df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
            return df
        except:
            return pd.DataFrame()

    # Carga de datos
    df_raw = load_data(url, category)

    if not df_raw.empty:
        # Filtro de fecha
        st.sidebar.subheader("4. Date Range")
        start_date, end_date = st.sidebar.date_input("Select Range", [df_raw['Date'].min(), df_raw['Date'].max()])
        
        mask = (df_raw['Date'].dt.date >= start_date) & (df_raw['Date'].dt.date <= end_date)
        df = df_raw.loc[mask]

        # --- DASHBOARD UI ---
        st.title(f"📊 {selected_client}: {category}")
        
        # Métricas
        appr = len(df[df['Quality Check (um)'] == 'APPROVED'])
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Scans", len(df))
        m2.metric("Approved ✅", appr)
        m3.metric("Total Payment", f"${appr * pay_per_scan:,.2f}")

        # Gráficos
        c1, c2 = st.columns([2, 1])
        with c1:
            fig_bar = px.bar(df, x='Week', color='Quality Check (um)', barmode='group', color_discrete_map=quality_colors)
            st.plotly_chart(fig_bar, use_container_width=True)
        with c2:
            fig_pie = px.pie(df, names='Quality Check (um)', color='Quality Check (um)', color_discrete_map=quality_colors)
            st.plotly_chart(fig_pie, use_container_width=True)

        st.dataframe(df.drop(columns=['date_str']), use_container_width=True)
    else:
        st.info(f"The sheet '{category}' was detected but it seems empty or doesn't follow the date format (YYYY_MM_DD).")
