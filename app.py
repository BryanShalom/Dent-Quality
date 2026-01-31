import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re

# Configuración avanzada de la página
st.set_page_config(page_title="Granit & Cruz | Quality Control", layout="wide", initial_sidebar_state="expanded")

# Estilos personalizados para que se vea más limpio
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# 1. GESTIÓN DE CLIENTES DESDE SECRETS
CLIENTES = {
    "Granit": st.secrets.get("URL_GRANIT", ""),
    "Cruz": st.secrets.get("URL_CRUZ", "")
}

st.sidebar.header("🛠️ Panel de Control")
cliente = st.sidebar.selectbox("Seleccionar Cliente", list(CLIENTES.keys()))
pago_unidad = st.sidebar.slider("Pago por scan aprobado (€)", 0.0, 5.0, 0.50)

# 2. CARGA Y PROCESAMIENTO
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600) # Guarda los datos por 10 min para que la página sea más rápida
def cargar_datos(url):
    df = conn.read(spreadsheet=url)
    # Detectar columna de nombre (Granit usa 'Patient', otros pueden usar 'Cast')
    col_id = 'Patient' if 'Patient' in df.columns else 'Cast'
    
    # Extraer fecha con Regex
    df['fecha_str'] = df[col_id].astype(str).apply(lambda x: re.search(r'(\d{4}_\d{2}_\d{2})', x).group(1) if re.search(r'(\d{4}_\d{2}_\d{2})', x) else None)
    df['Fecha'] = pd.to_datetime(df['fecha_str'], format='%Y_%m_%d')
    df = df.dropna(subset=['Fecha'])
    
    # Crear dimensiones de tiempo
    df['Semana'] = df['Fecha'].dt.to_period('W').apply(lambda r: r.start_time)
    df['Mes'] = df['Fecha'].dt.strftime('%B %Y')
    return df

try:
    data = cargar_datos(CLIENTES[cliente])

    # --- FILTROS EN SIDEBAR ---
    st.sidebar.subheader("Filtros")
    rango_fechas = st.sidebar.date_input("Rango de fechas", [data['Fecha'].min(), data['Fecha'].max()])
    
    # Filtrar el dataframe
    mask = (data['Fecha'].dt.date >= rango_fechas[0]) & (data['Fecha'].dt.date <= rango_fechas[1])
    df_filtrado = data.loc[mask]

    # --- MÉTRICAS ---
    st.title(f"📈 Dashboard {cliente}")
    m1, m2, m3, m4 = st.columns(4)
    
    total_scans = len(df_filtrado)
    aprobados = len(df_filtrado[df_filtrado['Quality Check (um)'] == 'APPROVED'])
    errores_imagen = len(df_filtrado[df_filtrado['Enough images'] == False])
    pago_total = aprobados * pago_unidad

    m1.metric("Total Scans", total_scans)
    m2.metric("Aprobados ✅", aprobados, f"{int(aprobados/total_scans*100)}% del total")
    m3.metric("Faltan Imágenes ⚠️", errores_imagen, delta_color="inverse")
    m4.metric("Presupuesto Estimado", f"€{pago_total:,.2f}")

    # --- GRÁFICAS ---
    c1, c2 = st.columns([2, 1])

    with c1:
        st.subheader("Evolución Semanal de Calidad")
        fig_evol = px.bar(df_filtrado, x='Semana', color='Quality Check (um)', 
                          barmode='stack', color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_evol, use_container_width=True)

    with c2:
        st.subheader("Distribución de Calidad")
        fig_pie = px.pie(df_filtrado, names='Quality Check (um)', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- ALERTAS DE ERRORES ---
    if errores_imagen > 0:
        with st.expander("🚨 Ver escaneos con falta de imágenes (Enough images = False)"):
            st.warning(f"Se han detectado {errores_imagen} escaneos que necesitan revisión técnica.")
            st.dataframe(df_filtrado[df_filtrado['Enough images'] == False][[col_id, 'Number of images']])

except Exception as e:
    st.error("Error al cargar los datos. Verifica que las URLs en Secrets sean correctas.")
