import streamlit as st
import pandas as pd
import re

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
    u = st.text_input("Cuenta (Granit/Cruz):").strip()
    if u:
        matching = next((k for k in CLIENT_CONFIG.keys() if k.lower() == u.lower()), None)
        if matching:
            st.session_state['auth'] = matching
            st.rerun()
        else:
            st.error("Nombre de cuenta no reconocido.")
    st.stop()

client = st.session_state['auth']
info = CLIENT_CONFIG[client]

# --- CARGA DE DATOS CORREGIDA ---
@st.cache_data(ttl=60)
def load_data(url, gid):
    try:
        csv_url = f"{url}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)
        if df.empty:
            return pd.DataFrame(), None
        
        # Limpiar nombres de columnas
        df.columns = [str(c).strip() for c in df.columns]
        
        # Identificar columna principal
        cid = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        
        def extract_info(val):
            val = str(val)
            # Buscar fecha: YYYY_MM_DD
            date_match = re.search(r'(\d{4}_\d{2}_\d{2})', val)
            # Buscar número: busca 3 a 5 dígitos
            num_match = re.search(r'(\d{3,5})', val.replace(date_match.group(1) if date_match else "", ""))
            
            d_str = date_match.group(1) if date_match else None
            n_val = int(num_match.group(1)) if num_match else 0
            return pd.Series([d_str, n_val])

        df[['date_str', 'p_num']] = df[cid].apply(extract_info)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        
        # Si la fecha falló, usamos una fecha ficticia para no borrar la fila
        df['Date'] = df['Date'].fillna(pd.Timestamp('2024-01-01'))
        df['p_num'] = df['p_num'].fillna(0).astype(int)
        
        return df, cid
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), None

# --- SIDEBAR Y FILTROS ---
st.sidebar.title(f"💼 {client}")
category = st.sidebar.radio("Categoría", ["Patients", "Cast"])
p_app = st.sidebar.number_input("Precio Approved ($)", value=0.50)
p_par = st.sidebar.number_input("Precio Partial ($)", value=0.25)

df_raw, col_id_name = load_data(info["url"], info["sheets"][category])

if not df_raw.empty:
    st.sidebar.divider()
    mode = st.sidebar.selectbox("🎯 Filtrar por:", ["Rango de IDs", "Rango de Fechas"])
    
    if mode == "Rango de IDs":
        min_v, max_v = int(df_raw['p_num'].min()), int(df_raw['p_num'].max())
        c1, c2 = st.sidebar.columns(2)
        start = c1.number_input("Desde:", value=min_v)
        end = c2.number_input("Hasta:", value=max_v)
        df_f = df_raw[(df_raw['p_num'] >= start) & (df_raw['p_num'] <= end)]
    else:
        # Filtro de fecha simplificado para evitar errores de zona horaria
        d_min, d_max = df_raw['Date'].min().date(), df_raw['Date'].max().date()
        dr = st.sidebar.date_input("Periodo:", [d_min, d_max])
        if isinstance(dr, list) and len(dr) == 2:
            df_f = df_raw[(df_raw['Date'].dt.date >= dr[0]) & (df_raw['Date'].dt.date <= dr[1])]
        else:
            df_f = df_raw

    # --- MÉTRICAS ---
    st.title(f"📊 Resumen: {client}")
    
    total_coll = len(df_f)
    app_n = len(df_f[df_f['Quality Check (um)'] == 'APPROVED'])
    par_n = len(df_f[df_f['Quality Check (um)'] == 'PARTIALLY APROVED'])
    
    ratio = p_par / p_app if p_app > 0 else 0.5
    acc_n = round(app_n + (par_n * ratio), 1)
    money = (app_n * p_app) + (par_n * p_par)

    c_a, c_b, c_c = st.columns(3)
    c_a.metric("Total Patients Collected", total_coll)
    c_b.metric("Patients Accepted", acc_n)
    c_c.metric("Total Earnings", f"${money:,.2f}")

    # --- BOTÓN DESCARGA ---
    csv_text = f"Total Patients Collected: {total_coll}\nPatients Accepted: {acc_n}\nEarnings: ${money}\n\n"
    csv_text += df_f[[col_id_name, 'Quality Check (um)']].to_csv(index=False)
    
    st.sidebar.download_button("📥 Descargar Resumen", csv_text, f"Reporte_{client}.csv")

    st.divider()
    st.dataframe(df_f.drop(columns=['date_str', 'p_num']), use_container_width=True)
else:
    st.warning("No se encontraron datos en la hoja de cálculo. Revisa el link de Google Sheets.")

if st.sidebar.button("Logout"):
    st.session_state['auth'] = None
    st.rerun()
