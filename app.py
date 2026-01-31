import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Dashboard de Escaneos Multi-Cliente", layout="wide")

# 1. CONFIGURACIÓN DE CLIENTES
# Aquí añadirás los links de cada Google Sheet que vayas creando
CLIENTES = {
    "Granit": "https://docs.google.com/spreadsheets/d/1nTEL5w5mEMXeyolUC8friEmRCix03aQ8NxYV8R63pLE/edit?gid=0#gid=0",
    "Cruz": "https://docs.google.com/spreadsheets/d/1F83LKwGeHxmSqvwqulmJLxx5VxQXYs5_mobIHEAKREQ/edit?gid=0#gid=0",
    # "Nuevo Cliente": "URL_AQUI"
}

# Sidebar para control
st.sidebar.title("Configuración")
cliente_seleccionado = st.sidebar.selectbox("Selecciona el Cliente", list(CLIENTES.keys()))
precio_por_scan = st.sidebar.number_input("Pago por escaneo aprobado (€)", value=0.50)

st.title(f"📊 Dashboard de Escaneos: {cliente_seleccionado}")

# 2. CONEXIÓN Y CARGA
url = CLIENTES[cliente_seleccionado]
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Cargamos los datos
    df = conn.read(spreadsheet=url)
    
    # Limpieza: Identificar la columna de nombre (puede ser 'Patient' o 'Cast')
    col_nombre = 'Patient' if 'Patient' in df.columns else 'Cast'
    
    # Extraer Fecha
    def extraer_fecha(texto):
        match = re.search(r'(\d{4}_\d{2}_\d{2})', str(texto))
        return match.group(1) if match else None

    df['Fecha_Limpia'] = df[col_nombre].apply(extraer_fecha)
    df['Fecha'] = pd.to_datetime(df['Fecha_Limpia'], format='%Y_%m_%d')
    df = df.dropna(subset=['Fecha'])
    df['Semana'] = df['Fecha'].dt.to_period('W').apply(lambda r: r.start_time)

    # 3. CÁLCULOS DE PAGOS
    # Filtramos solo los aprobados para el pago
    aprobados = df[df['Quality Check (um)'] == 'APPROVED'].shape[0]
    total_pago = aprobados * precio_por_scan

    # Métricas principales
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Escaneos", len(df))
    m2.metric("Escaneos Aprobados", aprobados)
    m3.metric("Total a Pagar", f"€{total_pago:,.2f}")

    # 4. GRÁFICAS
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Volumen Semanal")
        conteo = df.groupby('Semana').size().reset_index(name='Cantidad')
        fig1 = px.line(conteo, x='Semana', y='Cantidad', markers=True)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.subheader("🛡️ Calidad Histórica")
        fig2 = px.histogram(df, x='Semana', color='Quality Check (um)', 
                           barmode='group', color_discrete_map={
                               'APPROVED': '#2ECC71', 
                               'PARTIALLY APROVED': '#F1C40F', 
                               'REPPROVED': '#E74C3C'})
        st.plotly_chart(fig2, use_container_width=True)

except Exception as e:

    st.error("No se pudo cargar la hoja. Revisa que el link de Google Sheets sea correcto y tenga permisos de lectura.")
