import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re

# 1. PAGE CONFIG & ENGLISH UI
st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

st.title("📊 Scan Quality Monitoring Dashboard")

# 2. CUSTOM COLORS FOR QUALITY
# Approved: Green, Partially: Orange, Reproved: Red
quality_colors = {
    'APPROVED': '#28a745',
    'PARTIALLY APROVED': '#ff8c00',
    'REPPROVED': '#dc3545'
}

# 3. SIDEBAR CONTROLS
st.sidebar.header("Settings")
CLIENTES = {
    "Granit": "https://docs.google.com/spreadsheets/d/1nTEL5w5mEMXeyolUC8friEmRCix03aQ8NxYV8R63pLE/edit?gid=0#gid=0",
    "Cruz": "https://docs.google.com/spreadsheets/d/1F83LKwGeHxmSqvwqulmJLxx5VxQXYs5_mobIHEAKREQ/edit?gid=0#gid=0",
    # "Nuevo Cliente": "URL_AQUI"
    "Granit": st.secrets.get("URL_GRANIT", ""),
    "Cruz": st.secrets.get("URL_CRUZ", "")
}
selected_client = st.sidebar.selectbox("Select Client", list(CLIENTS.keys()))

# Manual payment input as you liked it
pay_per_scan = st.sidebar.number_input("Payment per approved scan ($/€)", value=0.50, step=0.05)

# 4. DATA LOADING & PROCESSING (Fixed for 2026 dates)
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60) # Reduced cache to 1 minute to see 2026 data faster
def load_and_process(url):
    # Read the sheet (make sure the URL is correct in Secrets)
    df = conn.read(spreadsheet=url)
    
    # Clean column names (remove extra spaces)
    df.columns = df.columns.str.strip()
    
    # Identify naming column
    col_name = 'Patient' if 'Patient' in df.columns else ('Cast' if 'Cast' in df.columns else df.columns[0])
    
    # Regex to extract YYYY_MM_DD including 2026
    def get_date(text):
        match = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
        return match.group(1) if match else None

    df['date_str'] = df[col_name].apply(get_date)
    df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
    
    # Filter out rows without valid dates
    df = df.dropna(subset=['Date'])
    
    # Time groupings
    df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
    return df, col_name

try:
    full_data, naming_col = load_and_process(CLIENTES[selected_client])

    # 5. DATE RANGE FILTER
    st.sidebar.subheader("Date Filter")
    min_date = full_data['Date'].min().date()
    max_date = full_data['Date'].max().date()
    
    # Default selection: All time
    date_range = st.sidebar.date_input("Select Range", [min_date, max_date])
    
    if len(date_range) == 2:
        mask = (full_data['Date'].dt.date >= date_range[0]) & (full_data['Date'].dt.date <= date_range[1])
        df_filtered = full_data.loc[mask]
    else:
        df_filtered = full_data

    # 6. TABS FOR PATIENTS AND CASTS
    # We filter the dataframe based on the name pattern
    df_pat = df_filtered[df_filtered[naming_col].str.contains('pat', case=False, na=False)]
    df_cast = df_filtered[df_filtered[naming_col].str.contains('model|cast', case=False, na=False)]

    tab1, tab2 = st.tabs(["👤 Patients (Pat)", "🧊 Models (Cast)"])

    def render_dashboard(df_tab, title):
        if df_tab.empty:
            st.info(f"No data found for {title} in the selected range.")
            return

        # Metrics
        total = len(df_tab)
        approved = len(df_tab[df_tab['Quality Check (um)'] == 'APPROVED'])
        total_pay = approved * pay_per_scan

        m1, m2, m3 = st.columns(3)
        m1.metric(f"Total {title} Scans", total)
        m2.metric("Approved ✅", approved)
        m3.metric("Estimated Payment", f"${total_pay:,.2f}")

        # Charts
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("Weekly Volume & Quality")
            fig_bar = px.bar(df_tab, x='Week', color='Quality Check (um)', 
                            barmode='group',
                            color_discrete_map=quality_colors,
                            labels={'Week': 'Start of Week', 'count': 'Number of Scans'})
            st.plotly_chart(fig_bar, use_container_width=True)

        with c2:
            st.subheader("Quality Distribution")
            fig_pie = px.pie(df_tab, names='Quality Check (um)', 
                            color='Quality Check (um)',
                            color_discrete_map=quality_colors)
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Raw Data Preview")
        st.dataframe(df_tab.drop(columns=['date_str']), use_container_width=True)

    with tab1:
        render_dashboard(df_pat, "Patient")

    with tab2:
        render_dashboard(df_cast, "Cast")

except Exception as e:
    st.error(f"Configuration Error: {e}")
    st.info("Please check if your Google Sheet URLs are correctly set in Streamlit Secrets.")

