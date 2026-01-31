import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Scan Quality Dashboard", layout="wide")

# 1. CLIENTS & SECRETS
CLIENTS = {
    "Granit": st.secrets.get("URL_GRANIT", "").strip(),
    "Cruz": st.secrets.get("URL_CRUZ", "").strip()
}

st.sidebar.header("Settings")
selected_client = st.sidebar.selectbox("Select Client", list(CLIENTS.keys()))
pay_per_scan = st.sidebar.number_input("Payment per approved scan ($/€)", value=0.50, step=0.05)

quality_colors = {
    'APPROVED': '#28a745',
    'PARTIALLY APROVED': '#ff8c00',
    'REPPROVED': '#dc3545'
}

# 2. DATA LOADING FUNCTION
@st.cache_data(ttl=60)
def load_data(base_url, sheet_name):
    try:
        export_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={sheet_name.replace(' ', '%20')}"
        df = pd.read_csv(export_url)
        if df.empty: return pd.DataFrame()

        df.columns = [str(c).strip() for c in df.columns]
        col_id = next((c for c in ['Patient', 'Cast'] if c in df.columns), df.columns[0])
        
        def get_date(text):
            match = re.search(r'(\d{4}_\d{2}_\d{2})', str(text))
            return match.group(1) if match else None

        df['date_str'] = df[col_id].apply(get_date)
        df['Date'] = pd.to_datetime(df['date_str'], format='%Y_%m_%d', errors='coerce')
        df = df.dropna(subset=['Date'])
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
        return df
    except:
        return pd.DataFrame()

# 3. MAIN LOGIC
url = CLIENTS[selected_client]

if not url:
    st.warning("⚠️ No URL found in Secrets.")
else:
    # --- LOAD BOTH SHEETS FIRST ---
    df_patients_raw = load_data(url, "Patients")
    df_casts_raw = load_data(url, "Casts")

    # --- GLOBAL DATE FILTER ---
    st.sidebar.subheader("Date Range")
    # Get overall min and max from both sheets
    all_dates = pd.concat([df_patients_raw['Date'], df_casts_raw['Date']])
    if not all_dates.empty:
        start_date, end_date = st.sidebar.date_input("Select Range", [all_dates.min(), all_dates.max()])
        
        # Filter Function
        def filter_by_date(df):
            if df.empty: return df
            mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
            return df.loc[mask]

        df_p = filter_by_date(df_patients_raw)
        df_c = filter_by_date(df_casts_raw)
    else:
        df_p, df_c = df_patients_raw, df_casts_raw

    # --- TABS ---
    tab1, tab2 = st.tabs(["👤 Patients", "🧊 Models (Cast)"])

    def render_content(df, suffix):
        if df.empty:
            st.info(f"No data found for this category in the selected range.")
            return

        # Metrics
        total = len(df)
        appr = len(df[df['Quality Check (um)'] == 'APPROVED'])
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Scans", total)
        c2.metric("Approved ✅", appr)
        c3.metric("Estimated Payment", f"${appr * pay_per_scan:,.2f}")

        # Charts
        col_left, col_right = st.columns([2, 1])
        
        with col_left:
            st.subheader("Weekly Evolution")
            fig_bar = px.bar(df, x='Week', color='Quality Check (um)', 
                            barmode='group', color_discrete_map=quality_colors)
            st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_{suffix}")

        with col_right:
            st.subheader("Quality Distribution")
            fig_pie = px.pie(df, names='Quality Check (um)', 
                            color='Quality Check (um)', color_discrete_map=quality_colors)
            st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_{suffix}")

        st.subheader("Data Details")
        st.dataframe(df, use_container_width=True, key=f"table_{suffix}")

    with tab1:
        render_content(df_p, "patients")

    with tab2:
        render_content(df_c, "casts")
