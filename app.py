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

# 2. FUNCIÓN PARA DETECTAR NOMBRES DE PESTAÑAS (Versión mejorada)
@st.cache_data(ttl=300) # Cache de 5 minutos para nombres de hojas
def fetch_sheet_names(url):
    try:
        # Intentamos extraer nombres de hojas del código fuente de la página de Google
        response = requests.get(url, timeout=10)
        # Regex para capturar nombres entre comillas después de 'sheet=' o en el JSON de metadatos
        sheets = re.findall(r'name\\":\\"(.*?)\\"', response.text)
        if not sheets:
            # Fallback a los nombres conocidos si el scrape falla
            return ["Patients", "Casts"]
        # Filtrar nombres duplicados o basura técnica de Google
        valid_sheets = [s for s in sheets if len(s) > 1 and "\\" not in s]
        return list(dict.fromkeys(valid_sheets)) # Elimina duplicados manteniendo orden
    except:
        return ["Patients", "Casts"]

# --- SIDEBAR ---
st.sidebar.header("🛠️ Dashboard Control")
selected_client = st.sidebar.selectbox("1. Select Client", list(CLIENTS.keys()))

url = CLIENTS[selected_client]

if not url:
    st.warning("⚠️ Please configure the URL in Streamlit Secrets.")
else:
    # Obtener pestañas reales
    all_sheets = fetch_sheet_names(url)
    
    # SELECTOR ÚNICO (Para evitar confusión entre pestañas)
    current_sheet = st.sidebar.selectbox("2. Select Category / Sheet", all_sheets)
    
    pay_per_scan = st.sidebar.number_input("3. Payment per approved scan", value=0.50, step=0.05)

    quality_colors = {
        'APPROVED': '#28a745',
        'PARTIALLY APROVED': '#ff8c00',
        'REPPROVED': '#dc3545'
    }

    # 3. CARGA DE DATOS POR CATEGORÍA SELECCIONADA
    @st.cache_data(ttl=60)
    def get_data_safe(base_url, sheet_name):
        try:
            # URL de exportación directa codificando el nombre de la hoja
            sheet_encoded = sheet_name.replace(' ', '%20')
            export_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={sheet_encoded}"
            
            df = pd.read_csv(export_url)
            if df.empty: return pd.DataFrame()

            df.columns = [str(c).strip() for c in df.columns]
            
            # Buscamos la columna de ID (Patient, Cast, o la primera)
            col_id = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
            
            # Extraer fecha YYYY_MM_DD
            def extract_date(text):
                m = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
                return m.group(1) if m else None

            df['date_str'] = df[col_id].apply(extract_date)
            df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
            df = df.dropna(subset=['Date'])
            df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
            
            return df
        except:
            return pd.DataFrame()

    # Cargar los datos de la pestaña seleccionada
    df_data = get_data_safe(url, current_sheet)

    if not df_data.empty:
        # 4. RANGO DE FECHAS (Dinámico)
        st.sidebar.subheader("4. Filter Dates")
        min_date = df_data['Date'].min().date()
        max_date = df_data['Date'].max().date()
        
        # Seleccionamos rango
        date_range = st.sidebar.date_input("Date Range", [min_date, max_date])
        
        # Filtrar dataframe
        if len(date_range) == 2:
            df_filtered = df_data[(df_data['Date'].dt.date >= date_range[0]) & 
                                  (df_data['Date'].dt.date <= date_range[1])]
        else:
            df_filtered = df_data

        # --- MOSTRAR DASHBOARD ---
        st.title(f"📊 {selected_client}: {current_sheet}")
        
        # Métricas
        total_s = len(df_filtered)
        appr_s = len(df_filtered[df_filtered['Quality Check (um)'] == 'APPROVED'])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Scans", total_s)
        col2.metric("Approved ✅", appr_s)
        col3.metric("Earnings", f"${appr_s * pay_per_scan:,.2f}")

        # Gráficos
        left_c, right_c = st.columns([2, 1])
        
        with left_c:
            st.subheader("Weekly Trend")
            fig_bar = px.bar(df_filtered, x='Week', color='Quality Check (um)', 
                            barmode='group', color_discrete_map=quality_colors)
            st.plotly_chart(fig_bar, use_container_width=True)

        with right_c:
            st.subheader("Quality Distribution")
            fig_pie = px.pie(df_filtered, names='Quality Check (um)', 
                            color='Quality Check (um)', color_discrete_map=quality_colors)
            st.plotly_chart(fig_pie, use_container_width=True)

        # Tabla de datos
        with st.expander("🔍 Click to see raw data"):
            st.dataframe(df_filtered.drop(columns=['date_str']), use_container_width=True)

    else:
        st.error(f"No valid data found in '{current_sheet}'. Verify that the column names and date format (YYYY_MM_DD) are correct.")
        st.info("Note: Your Google Sheet must be 'Public' (Anyone with the link can view).")
