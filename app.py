import streamlit as st
import pandas as pd
import plotly.express as px
import re
from fpdf import FPDF
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CONFIGURACIÓN CENTRALIZADA
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

# --- FUNCIÓN PARA GENERAR EL PDF (Formato Maria F. Cruz en $) ---
def create_invoice_pdf(category, df_filtered, total_money, app_n, par_n, pay_app, pay_par, id_range):
    pdf = FPDF()
    pdf.add_page()
    
    # Simulación de Logo (Corazón)
    pdf.set_font("Arial", 'B', 24)
    pdf.set_text_color(220, 20, 60) # Rojo carmesí
    pdf.cell(0, 10, "❤️", ln=True)
    pdf.set_text_color(0, 0, 0)

    # Encabezado Maria F. Cruz
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "MARIA F. CRUZ", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, "ODONTOLOGIA INTEGRAL", ln=True)
    pdf.cell(0, 5, "Od. Maria Fernanda Cruz", ln=True)
    
    pdf.ln(10)
    
    # Bloque de Información de Factura
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(100, 7, "Cobrar a:", 0, 0)
    pdf.cell(0, 7, f"FACTURA #{datetime.now().strftime('%Y%m%d')}", 0, 1, 'R')
    
    pdf.set_font("Arial", '', 10)
    pdf.cell(100, 5, "Zaamigo, AG", 0, 0)
    pdf.cell(45, 5, "Fecha:", 0, 0, 'R')
    pdf.cell(0, 5, f" {datetime.now().strftime('%d/%m/%Y')}", 0, 1, 'R')
    
    pdf.cell(100, 5, "Enviar a: Riccardo Baravelli (CEO)", 0, 0)
    pdf.cell(45, 5, "Vencimiento:", 0, 0, 'R')
    # Vencimiento a una semana
    vencimiento = datetime.now() + timedelta(days=7)
    pdf.cell(0, 5, f" {vencimiento.strftime('%d/%m/%Y')}", 0, 1, 'R')
    
    pdf.cell(100, 5, "Hohlstrasse 186, 8004 Zürich, Switzerland", 0, 1)
    
    pdf.ln(10)
    
    # Tabla de Items
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(100, 10, f" Articulo (IDs: {id_range})", 1, 0, 'L', True)
    pdf.cell(30, 10, " Cantidad", 1, 0, 'C', True)
    pdf.cell(30, 10, " Tasa", 1, 0, 'C', True)
    pdf.cell(0, 10, " Total", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 10)
    # Línea Aprobados
    pdf.cell(100, 10, f" Scans Approved - {category}", 1)
    pdf.cell(30, 10, f" {app_n}", 1, 0, 'C')
    pdf.cell(30, 10, f" ${pay_app:.2f}", 1, 0, 'C')
    pdf.cell(0, 10, f" ${(app_n * pay_app):.2f}", 1, 1, 'C')
    
    # Línea Parciales
    pdf.cell(100, 10, f" Scans Partially Approved - {category}", 1)
    pdf.cell(30, 10, f" {par_n}", 1, 0, 'C')
    pdf.cell(30, 10, f" ${pay_par:.2f}", 1, 0, 'C')
    pdf.cell(0, 10, f" {(par_n * pay_par):.2f}", 1, 1, 'C')
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(160, 10, "TOTAL USD:", 0, 0, 'R')
    pdf.cell(0, 10, f" ${total_money:.2f}", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# --- LÓGICA DE ACCESO ---
if 'auth' not in st.session_state:
    st.session_state['auth'] = None

if st.session_state['auth'] is None:
    st.title("🔐 Acceso al Sistema")
    u = st.text_input("Ingrese nombre de Cuenta (Granit/Cruz):").strip()
    if u.lower() in [k.lower() for k in CLIENT_CONFIG.keys()]:
        st.session_state['auth'] = "Cruz" if u.lower() == "cruz" else "Granit"
        st.rerun()
    st.stop()

# --- CARGA ---
client = st.session_state['auth']
info = CLIENT_CONFIG[client]

st.sidebar.title(f"💼 {client}")
category = st.sidebar.radio("Categoría", ["Patients", "Cast"])
p_app = st.sidebar.number_input("Tasa Approved ($)", value=0.50)
p_par = st.sidebar.number_input("Tasa Partial ($)", value=0.25)

@st.cache_data(ttl=60)
def load_data(url, gid):
    try:
        df = pd.read_csv(f"{url}/export?format=csv&gid={gid}")
        df.columns = [str(c).strip() for c in df.columns]
        cid = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        def proc(x):
            d = re.search(r'(\d{4}_\d{2}_\d{2})', str(x))
            n = re.search(r'_(\d{3,5})', str(x))
            return pd.Series([d.group(1) if d else None, int(n.group(1)) if n else 0])
        df[['date_str', 'p_num']] = df[cid].apply(proc)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        return df, cid
    except: return pd.DataFrame(), None

df_raw, col_name = load_data(info["url"], info["sheets"][category])

if not df_raw.empty:
    # FILTRO POR RANGO MANUAL
    st.sidebar.divider()
    st.sidebar.subheader("Rango de IDs para Factura")
    min_v, max_v = int(df_raw['p_num'].min()), int(df_raw['p_num'].max())
    c1, c2 = st.sidebar.columns(2)
    start = c1.number_input("Desde:", value=min_v)
    end = c2.number_input("Hasta:", value=max_v)
    
    df_f = df_raw[(df_raw['p_num'] >= start) & (df_raw['p_num'] <= end)]
    
    # MÉTRICAS DASHBOARD
    st.title(f"📊 Dashboard {client}")
    app_n = len(df_f[df_f['Quality Check (um)'] == 'APPROVED'])
    par_n = len(df_f[df_f['Quality Check (um)'] == 'PARTIALLY APROVED'])
    
    ratio = p_par / p_app if p_app > 0 else 0
    total_scans = round(app_n + (par_n * ratio), 1)
    total_money = (app_n * p_app) + (par_n * p_par)
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Approved", app_n)
    st.markdown(f"<div style='margin-top:-25px'><small>Total Scans: <b>{total_scans}</b></small></div>", unsafe_allow_html=True)
    m2.metric("Partial", par_n)
    m3.metric("Earnings", f"${total_money:,.2f}")
    
    # BOTÓN DE FACTURA (SOLO CRUZ)
    if client == "Cruz":
        id_str = f"{start}-{end}"
        pdf_data = create_invoice_pdf(category, df_f, total_money, app_n, par_n, p_app, p_par, id_str)
        st.sidebar.download_button(
            label="📄 Descargar Factura Maria F. Cruz",
            data=pdf_data,
            file_name=f"Factura_Cruz_{id_str}.pdf",
            mime="application/pdf"
        )

    st.divider()
    st.dataframe(df_f.drop(columns=['date_str']), use_container_width=True)
