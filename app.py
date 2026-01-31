import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CONFIGURACIÓN
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

st.sidebar.subheader("💰 Pricing")
pay_approved = st.sidebar.number_input("Approved ($)", value=0.50, step=0.05)
pay_partial = st.sidebar.number_input("Partially Approved ($)", value=0.25, step=0.05)

quality_colors = {'APPROVED': '#28a745', 'PARTIALLY APROVED': '#ff8c00', 'REPROVED': '#dc3545'}

# 2. CARGA Y PROCESAMIENTO
@st.cache_data(ttl=60)
def load_data_with_numbers(base_url, gid):
    try:
        csv_url = f"{base_url}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)
        if df.empty: return pd.DataFrame(), None
        
        df.columns = [str(c).strip() for c in df.columns]
        col_id = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        
        # Extraer Fecha y Número de ID del texto
        def process_id(text):
            text = str(text)
            # Busca fecha YYYY_MM_DD
            date_match = re.search(r'(\d{4}_\d{2}_\d{2})', text)
            # Busca un número aislado (ID del paciente) que suele ir tras la fecha
            # Intentamos capturar el número que mencionas (ej. 400)
            num_match = re.search(r'_(\d{3,4})_', text) # Busca 3 o 4 dígitos entre guiones bajos
            
            date_val = date_match.group(1) if date_match else None
            num_val = int(num_match.group(1)) if num_match else None
            return pd.Series([date_val, num_val])

        df[['date_str', 'patient_num']] = df[col_id].apply(process_id)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        
        # Si no detecta números, asignamos el índice de la fila para que el filtro no falle
        if df['patient_num'].isnull().all():
            df['patient_num'] = range(1, len(df) + 1)
        else:
            df['patient_num'] = df['patient_num'].fillna(0).astype(int)
            
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        return df, col_id
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame(), None

# 3. LÓGICA DE FILTRADO
client_info = CLIENTS[selected_client]
df_raw, col_name = load_data_with_numbers(client_info["url"], client_info["sheets"][category])

if not df_raw.empty:
    # --- FILTRO POR RANGO NUMÉRICO ---
    st.sidebar.subheader(f"🔢 Range of {category}")
    min_idx = int(df_raw['patient_num'].min())
    max_idx = int(df_raw['patient_num'].max())
    
    # El usuario selecciona el rango, ej: 400 a 449
    range_select = st.sidebar.slider(
        "Select ID Range",
        min_value=min_idx,
        max_value=max_idx,
        value=(min_idx, max_idx)
    )

    # Aplicar Filtro
    df_filtered = df_raw[(df_raw['patient_num'] >= range_select[0]) & 
                         (df_raw['patient_num'] <= range_select[1])]

    # --- UI ---
    st.title(f"📊 {selected_client}: {category}")
    st.info(f"Showing {category} IDs from **{range_select[0]}** to **{range_select[1]}**")
    
    if df_filtered.empty:
        st.warning("No hay pacientes en este rango.")
    else:
        # Métricas
        appr = len(df_filtered[df_filtered['Quality Check (um)'] == 'APPROVED'])
        part = len(df_filtered[df_filtered['Quality Check (um)'] == 'PARTIALLY APROVED'])
        repr = len(df_filtered[df_filtered['Quality Check (um)'] == 'REPROVED'])
        earnings = (appr * pay_approved) + (part * pay_partial)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Approved ✅", appr)
        m2.metric("Partial ⚠️", part)
        m3.metric("Reproved ❌", repr)
        m4.metric("Total Earnings", f"${earnings:,.2f}")

        # Gráficos
        c1, c2 = st.columns([2, 1])
        with c1:
            st.plotly_chart(px.bar(df_filtered, x='Week', color='Quality Check (um)', 
                                   barmode='group', color_discrete_map=quality_colors,
                                   title="Weekly Trend in Range"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_filtered, names='Quality Check (um)', 
                                   color='Quality Check (um)', color_discrete_map=quality_colors, 
                                   hole=0.4, title="Range Quality Share"), use_container_width=True)

        with st.expander("🔍 Detailed Table (Filtered)"):
            st.dataframe(df_filtered.drop(columns=['date_str', 'patient_num']), use_container_width=True)
