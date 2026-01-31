import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re

# 1. PAGE CONFIG & ENGLISH UI
st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 2. DEFINE CLIENTS FIRST (To avoid NameError)
# We look for URLs in secrets, if not found, we leave it empty to avoid crashes
CLIENTS = {
    "Granit": st.secrets.get("URL_GRANIT", ""),
    "Cruz": st.secrets.get("URL_CRUZ", "")
}

st.sidebar.header("Settings")
# Use the keys from the dictionary we just defined
selected_client = st.sidebar.selectbox("Select Client", list(CLIENTS.keys()))

# Manual payment input
pay_per_scan = st.sidebar.number_input("Payment per approved scan ($/€)", value=0.50, step=0.05)

st.title(f"📊 Scan Quality Monitoring: {selected_client}")

# 3. CUSTOM COLORS FOR QUALITY
quality_colors = {
    'APPROVED': '#28a745',
    'PARTIALLY APROVED': '#ff8c00',
    'REPPROVED': '#dc3545'
}

# 4. DATA LOADING & PROCESSING
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_and_process(url):
    if not url:
        return None, None
    
    # Read the sheet
    df = conn.read(spreadsheet=url)
    
    # Clean column names
    df.columns = df.columns.str.strip()
    
    # Identify naming column (Patient or Cast)
    col_name = 'Patient' if 'Patient' in df.columns else ('Cast' if 'Cast' in df.columns else df.columns[0])
    
    # Regex to extract YYYY_MM_DD
    def get_date(text):
        match = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
        return match.group(1) if match else None

    df['date_str'] = df[col_name].apply(get_date)
    df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
    
    # Filter out rows without valid dates and filter for 2026 data
    df = df.dropna(subset=['Date'])
    
    # Time groupings
    df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
    return df, col_name

# --- MAIN LOGIC ---
current_url = CLIENTS[selected_client]

if not current_url:
    st.warning(f"⚠️ No URL found for {selected_client}. Please add it to Streamlit Secrets.")
else:
    try:
        full_data, naming_col = load_and_process(current_url)

        if full_data is not None:
            # 5. DATE RANGE FILTER
            st.sidebar.subheader("Date Filter")
            min_date = full_data['Date'].min().date()
            max_date = full_data['Date'].max().date()
            
            date_range = st.sidebar.date_input("Select Range", [min_date, max_date])
            
            if len(date_range) == 2:
                mask = (full_data['Date'].dt.date >= date_range[0]) & (full_data['Date'].dt.date <= date_range[1])
                df_filtered = full_data.loc[mask]
            else:
                df_filtered = full_data

            # 6. TABS FOR PATIENTS AND CASTS
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
                                    barmode='group', color_discrete_map=quality_colors)
                    st.plotly_chart(fig_bar, use_container_width=True)

                with c2:
                    st.subheader("Quality Distribution")
                    fig_pie = px.pie(df_tab, names='Quality Check (um)', 
                                    color='Quality Check (um)', color_discrete_map=quality_colors)
                    st.plotly_chart(fig_pie, use_container_width=True)

                st.subheader("Raw Data Preview")
                st.dataframe(df_tab.drop(columns=['date_str']), use_container_width=True)

            with tab1:
                render_dashboard(df_pat, "Patient")
            with tab2:
                render_dashboard(df_cast, "Cast")
                
    except Exception as e:
        st.error(f"Error: {e}")
