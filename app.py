import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# Configuración de página
st.set_page_config(page_title="Quality Dashboard", layout="wide")

# Configuración del Cliente
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

# Acceso al cliente
if 'auth' not in st.session_state:
    st.session_state['auth'] = None

if st.session_state['auth'] is None:
    st.title("🔐 Acceso")
    u = st.text_input("Nombre:").strip()
    if u:
        matching = next((k for k in CLIENT_CONFIG.keys() if k.lower() == u.lower()), None)
        if matching:
            st.session_state['auth'] = matching
            st.rerun()
        else:
            st.error("Nombre no reconocido.")
    st.stop()

client = st.session_state['auth']
info = CLIENT_CONFIG[client]

# Sidebar
st.sidebar.title(f"💼 {client}")
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state['auth'] = None
    st.rerun()

st.sidebar.divider()
category = st.sidebar.radio("Categoría", ["Patients", "Cast"])
p_app = st.sidebar.number_input("Precio Approved ($)", value=0.50, min_value=0.0)
p_par = st.sidebar.number_input("Precio Partial ($)", value=0.25, min_value=0.0)

# Función de carga de datos
@st.cache_data(ttl=10, allow_output_mutation=True)
def load_data(url, gid, filters=None):
    # Función de carga de datos con validaciones y filtros
    # ...

# Carga los datos
df_raw, col_id_name = load_data(info["url"], info["sheets"][category])

# Procesamiento de filtros y métricas
# ...

# Visualización con Plotly y la exportación
# ...

