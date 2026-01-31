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

# 2. MEJORADO: FUNCIÓN PARA OBTENER NOMBRES
@st.cache_data(ttl=300)
def fetch_sheet_names(url):
    try:
        response = requests.get(url, timeout=10)
        # Buscamos nombres de pestañas en el código de Google
        sheets = re.findall(r'name\\":\\"(.*?)\\"', response.text)
        valid_sheets = [s for s in sheets if len(s) > 1 and "\\" not in s and s != "Basics"]
        return list(dict.fromkeys(valid_sheets)) if valid_sheets else ["Patients", "Casts"]
    except:
        return ["Patients", "Casts"]

# --- SIDEBAR ---
st.sidebar.header("🛠️ Dashboard Control")
selected_client = st.sidebar.selectbox("1. Select Client", list(CLIENTS.keys()))
url = CLIENTS[selected_client]

if not url:
    st.warning("⚠️ Please configure the URL in Streamlit Secrets.")
else:
    # Obtener pestañas sugeridas
    suggested_sheets = fetch_sheet_names(url)
    if "➕ Custom Sheet..." not in suggested_sheets:
        suggested_sheets.append("➕ Custom Sheet...")

    # SELECTOR
    sheet_choice = st.sidebar.selectbox("2. Select Category / Sheet", suggested_sheets)

    # Si elige "Custom", aparece un cuadro para escribir
    if sheet_choice == "➕ Custom Sheet...":
        current_sheet = st.sidebar.text_input("Write the sheet name exactly:", placeholder="Example: Copia")
    else:
        current_sheet = sheet_choice

    pay_per_scan = st.sidebar.number_input("3. Payment per approved scan", value=0.50, step=0.05)

    quality_colors = {'APPROVED': '#28a745', 'PARTIALLY APROVED': '#ff8c00', 'REPPROVED': '#dc3545'}

    # 3. CARGA DE DATOS
    @st.cache_data(ttl=60)
    def get_data_safe(base_url, sheet_name):
        if not sheet_name or sheet_name == "➕ Custom Sheet...":
            return pd.DataFrame()
        try:
            sheet_encoded = sheet_name.replace(' ', '%20')
            export_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={sheet_encoded}"
            df = pd.read_csv(export_url)
            
            if df.empty: return pd.DataFrame()
            df.columns = [str(c).strip() for c in df.columns]
            
            # Buscamos la columna de ID
            col_id = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
            
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

    if current_sheet:
        df_data = get_data_safe(url, current_sheet)

        if not df_data.empty:
            # Filtro de fechas
            st.sidebar.subheader("4. Filter Dates")
            date_range = st.sidebar.date_input("Date Range", [df_data['Date'].min().date(), df_data['Date'].max().date()])
            
            if isinstance(date_range, list) and len(date_range) == 2:
                df_filtered = df_data[(df_data['Date'].dt.date >= date_range[0]) & (df_data['Date'].dt.date <= date_range[1])]
            else:
                df_filtered = df_data

            # --- UI ---
            st.title(f"📊 {selected_client}: {current_sheet}")
            
            m1, m2, m3 = st.columns(3)
            appr_s = len(df_filtered[df_filtered['Quality Check (um)'] == 'APPROVED'])
            m1.metric("Total Scans", len(df_filtered))
            m2.metric("Approved ✅", appr_s)
            m3.metric("Earnings", f"${appr_s * pay_per_scan:,.2f}")

            c1, c2 = st.columns([2, 1])
            with c1:
                st.plotly_chart(px.bar(df_filtered, x='Week', color='Quality Check (um)', barmode='group', color_discrete_map=quality_colors), use_container_width=True)
            with c2:
                st.plotly_chart(px.pie(df_filtered, names='Quality Check (um)', color='Quality Check (um)', color_discrete_map=quality_colors), use_container_width=True)

            with st.expander("🔍 Raw Data"):
                st.dataframe(df_filtered.drop(columns=['date_str']), use_container_width=True)
        else:
            if current_sheet != "➕ Custom Sheet...":
                st.warning(f"Waiting for valid data from sheet: '{current_sheet}'...")
                st.info("💡 Make sure the sheet name is spelled exactly as in Google Sheets.")
