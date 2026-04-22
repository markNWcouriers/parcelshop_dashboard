import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
import plotly.express as px
import difflib

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Parcelshop Performance",
    layout="wide"
)

# ====================== BRAND COLOURS ======================
BRAND_BLUE = "#0072CE"
BRAND_LIGHT_BLUE = "#4DB8FF"
BRAND_NAVY = "#0A1A2F"
BRAND_GREY_BG = "#F2F4F7"
ERROR_RED = "#E74C3C"
WARNING_ORANGE = "#E67E22"

# ====================== PAGE BACKGROUND ======================
st.markdown(
    f"""
    <style>
        .main {{ background-color: {BRAND_GREY_BG}; }}
        h1, h2, h3, h4 {{ color: {BRAND_NAVY} !important; }}
        .stMetric label {{ color: {BRAND_NAVY} !important; }}
    </style>
    """,
    unsafe_allow_html=True
)

# ====================== HEADER WITH BIG LOGO ======================
try:
    logo = Image.open("nw_logo.png")
except:
    logo = None
    st.warning("⚠️ Logo file 'nw_logo.png' not found. Place it in the same folder as your script.")

header = st.container()
with header:
    if logo:
        st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
        st.image(logo, width=420)
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown(
        f"""
        <div style='text-align:center; margin-top:-20px;'>
            <h1 style='color:{BRAND_NAVY}; margin-bottom:-5px;'>
                Parcelshop Performance
            </h1>
            <p style='color:{BRAND_NAVY}; font-size:16px;'>
                Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

# ====================== LOAD DATA ======================
report_path = "OOH_report.xlsx"
lookup_path = "drivers_lookup.xlsx"

if not os.path.exists(report_path):
    st.error("❌ OOH_report.xlsx not found!")
    st.stop()

df = pd.read_excel(report_path, sheet_name="Sheet1")
df.columns = [col.strip() for col in df.columns]

# ====================== CLEAN ROWS ======================
df = df[
    df['Shop ID'].notna() &
    df['Shop Name'].notna() &
    (df['Shop ID'].astype(str).str.strip() != "") &
    (df['Shop Name'].astype(str).str.strip() != "")
]

# ====================== DRIVER NAME & DEPOT LOOKUP ======================
driver_names = {}
if os.path.exists(lookup_path):
    lookup = pd.read_excel(lookup_path, sheet_name="Sheet1")
    lookup.columns = [col.strip() for col in lookup.columns]
    if 'Driver ID' in lookup.columns and 'Driver Name' in lookup.columns:
        driver_names = dict(zip(
            lookup['Driver ID'].astype(str).str.strip(),
            lookup['Driver Name'].astype(str).str.strip()
        ))

df['Driver Name'] = df['Driver ID'].astype(str).map(driver_names).fillna(df['Driver ID'].astype(str))

# Depot lookup
try:
    depot_lookup = pd.read_excel(lookup_path, sheet_name="Sheet3")
    depot_lookup.columns = [col.strip() for col in depot_lookup.columns]
    driver_depot_map = depot_lookup.set_index(
        depot_lookup['Driver ID'].astype(str).str.strip()
    )['DEPOT'].to_dict()
except:
    driver_depot_map = {}

df['Depot'] = df['Driver ID'].astype(str).map(driver_depot_map).fillna("Unknown")

# ====================== CLEAN NUMERIC COLUMNS ======================
numeric_cols = ['Collection Volume', 'Collected', 'Delivery Volume', 
                'Delivered', 'Failed Collections', 'Not Delivered']

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

# ====================== FILTER SYSTEM ======================
st.sidebar.header("Filters")

# ---------------------- DRIVER SEARCH (Live Search) ----------------------
st.sidebar.markdown("### 🔍 Driver Search")

search_query = st.sidebar.text_input(
    "Search by Driver Name, ID, Depot, or Shop",
    value="",
    placeholder="Type here... (e.g. mik, DUKI2, Halifax)",
    help="Live search — results update as you type"
).strip().lower()

if search_query:
    fuzzy_matches = difflib.get_close_matches(
        search_query, 
        df['Driver Name'].str.lower().unique(), 
        n=30, 
        cutoff=0.4
    )

    mask = (
        df['Driver Name'].str.lower().str.contains(search_query, na=False) |
        df['Driver ID'].astype(str).str.lower().str.contains(search_query, na=False) |
        df['Depot'].str.lower().str.contains(search_query, na=False) |
        df['Shop Name'].str.lower().str.contains(search_query, na=False) |
        df['Driver Name'].str.lower().isin(fuzzy_matches)
    )

    filtered_df = df[mask].copy()

    if len(filtered_df) > 0:
        st.sidebar.success(f"✅ Found {len(filtered_df)} matching records")
    else:
        st.sidebar.warning("⚠️ No matches found for your search")
        filtered_df = pd.DataFrame()

else:
    # ---------------------- NORMAL FILTER MODE ----------------------
    st.sidebar.markdown("### 🎛 Global Controls")
    
    if 'global_select' not in st.session_state:
        st.session_state.global_select = "Select All"
    
    global_select = st.sidebar.radio(
        "Select Mode",
        ["Select All", "Deselect All"],
        horizontal=True,
        key="global_radio"
    )
    
    if global_select != st.session_state.get('global_select'):
        st.session_state.global_select = global_select
        st.rerun()

    default_value = global_select == "Select All"

    depots = sorted(df['Depot'].unique())
    selected_depots = []

    st.sidebar.markdown("## 🏭 Depots")
    for i, depot in enumerate(depots):
        depot_key = f"depot_cb_{i}_{depot}"
        if st.sidebar.checkbox(f"🚚 {depot}", value=True, key=depot_key):
            selected_depots.append(depot)

    filtered_df = df[df['Depot'].isin(selected_depots)].copy()

    # ---------------------- Driver Selection ----------------------
    st.sidebar.markdown("## 👥 Drivers")
    selected_driver_ids = []

    for depot in selected_depots:
        with st.sidebar.expander(f"🚚 {depot} — Drivers", expanded=True):
            depot_drivers = (
                df[df['Depot'] == depot][['Driver ID', 'Driver Name']]
                .drop_duplicates()
                .sort_values('Driver Name')
            )
            
            for _, row in depot_drivers.iterrows():
                driver_key = f"driver_cb_{depot}_{row['Driver ID']}"
                
                if driver_key not in st.session_state:
                    st.session_state[driver_key] = default_value
                
                if st.sidebar.checkbox(
                    row['Driver Name'], 
                    value=st.session_state[driver_key], 
                    key=driver_key
                ):
                    selected_driver_ids.append(row['Driver ID'])

    if selected_driver_ids:
        filtered_df = filtered_df[filtered_df['Driver ID'].isin(selected_driver_ids)]
    else:
        filtered_df = filtered_df.iloc[0:0]

# ====================== KPIs ======================
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)

total_drivers = len(filtered_df['Driver ID'].unique()) if not filtered_df.empty else 0
total_shops = len(filtered_df) if not filtered_df.empty else 0
total_collection_volume = int(filtered_df['Collection Volume'].sum()) if not filtered_df.empty else 0
total_collected = int(filtered_df['Collected'].sum()) if not filtered_df.empty else 0
total_failed = int(filtered_df['Failed Collections'].sum()) if not filtered_df.empty else 0

coll_rate = (total_collected / total_collection_volume * 100) if total_collection_volume > 0 else 0
del_rate = (filtered_df['Delivered'].sum() / filtered_df['Delivery Volume'].sum() * 100) if not filtered_df.empty and filtered_df['Delivery Volume'].sum() > 0 else 0

c1.metric("Active Drivers", total_drivers)
c2.metric("Total Shops", total_shops)
c3.metric("Total Collection Volume", total_collection_volume)
c4.metric("Total Collected", total_collected)
c5.metric("Total Failed Collections", total_failed)
c6.metric("Collection Success", f"{coll_rate:.1f}%")
c7.metric("Delivery Success", f"{del_rate:.1f}%")

# ====================== NETWORK PIE ======================
st.subheader("🌍 Network Collection Performance")
if not filtered_df.empty and filtered_df['Collection Volume'].sum() > 0:
    network_df = filtered_df[filtered_df['Collection Volume'] > 0]
    net_collected = float(network_df['Collected'].sum())
    net_volume = float(network_df['Collection Volume'].sum())
    net_remaining = net_volume - net_collected

    pie_network = pd.DataFrame({
        "Status": ["Collected", "Remaining"],
        "Value": [net_collected, net_remaining]
    })

    fig_network = px.pie(
        pie_network, 
        names="Status", 
        values="Value",
        title=f"Network Collection — {net_collected / net_volume * 100:.1f}%",
        color="Status",
        color_discrete_map={"Collected": BRAND_BLUE, "Remaining": ERROR_RED},
        hole=0.45
    )
    fig_network.update_traces(textinfo="percent", pull=[0.02, 0], marker=dict(line=dict(color="white", width=2)))
    st.plotly_chart(fig_network, use_container_width=True)
else:
    st.info("No data to display for Network Performance.")

# ====================== DEPOT PIE GRID ======================
st.subheader("🏭 Depot Collection Performance")
if not filtered_df.empty:
    depots = sorted(filtered_df['Depot'].unique())
    cols_per_row = 4

    for i in range(0, len(depots), cols_per_row):
        row = st.columns(cols_per_row)
        for j, depot in enumerate(depots[i:i + cols_per_row]):
            depot_df = filtered_df[(filtered_df['Depot'] == depot) & (filtered_df['Collection Volume'] > 0)]
            dep_collected = float(depot_df['Collected'].sum())
            dep_volume = float(depot_df['Collection Volume'].sum()) or 0.0001
            dep_remaining = dep_volume - dep_collected

            pie_depot = pd.DataFrame({"Status": ["Collected", "Remaining"], "Value": [dep_collected, dep_remaining]})

            fig = px.pie(
                pie_depot, 
                names="Status", 
                values="Value",
                title=f"{depot} — {dep_collected / dep_volume * 100:.1f}%",
                color="Status",
                color_discrete_map={"Collected": BRAND_BLUE, "Remaining": ERROR_RED},
                hole=0.45
            )
            fig.update_traces(textinfo="percent", pull=[0.02, 0], marker=dict(line=dict(color="white", width=2)))
            
            with row[j]:
                st.plotly_chart(fig, use_container_width=True)

# ====================== VISUAL OVERVIEW ======================
st.subheader("📈 Visual Overview")
if not filtered_df.empty:
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        failed_per_driver = filtered_df.groupby('Driver Name')['Failed Collections'].sum().reset_index().sort_values('Failed Collections', ascending=False)
        fig_failed = px.bar(
            failed_per_driver, 
            x='Failed Collections', 
            y='Driver Name', 
            orientation='h',
            title="Failed Collections per Driver", 
            color='Failed Collections',
            color_continuous_scale=[ERROR_RED, WARNING_ORANGE]
        )
        fig_failed.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_failed, use_container_width=True)

    with chart_col2:
        volume_per_driver = filtered_df.groupby('Driver Name')['Collection Volume'].sum().reset_index().sort_values('Collection Volume', ascending=False)
        fig_volume = px.bar(
            volume_per_driver, 
            x='Collection Volume', 
            y='Driver Name', 
            orientation='h',
            title="Collection Volume per Driver", 
            color='Collection Volume',
            color_continuous_scale=[BRAND_LIGHT_BLUE, BRAND_BLUE]
        )
        fig_volume.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_volume, use_container_width=True)

# ====================== DRIVER SUMMARY ======================
st.subheader("📊 Driver Performance Summary")
if not filtered_df.empty:
    summary = filtered_df.groupby('Driver ID').agg({
        'Driver Name': 'first',
        'Shop ID': 'nunique',
        'Collected': 'sum',
        'Collection Volume': 'sum',
        'Failed Collections': 'sum',
        'Delivered': 'sum',
        'Delivery Volume': 'sum',
        'Not Delivered': 'sum'
    }).reset_index()

    summary['Collection %'] = (summary['Collected'] / summary['Collection Volume'] * 100).round(1)
    summary['Delivery %'] = (summary['Delivered'] / summary['Delivery Volume'] * 100).round(1)
    summary['Failed %'] = (summary['Failed Collections'] / summary['Collection Volume'] * 100).round(1)
    summary = summary.rename(columns={'Shop ID': 'Shops'})

    summary = summary[['Driver Name', 'Driver ID', 'Shops', 'Collection Volume', 'Collected', 
                       'Failed Collections', 'Failed %', 'Delivery Volume', 'Delivered', 
                       'Not Delivered', 'Delivery %', 'Collection %']]

    st.dataframe(
        summary.style
            .format({
                'Collection Volume': '{:,.0f}', 'Collected': '{:,.0f}', 'Failed Collections': '{:,.0f}',
                'Delivery Volume': '{:,.0f}', 'Delivered': '{:,.0f}', 'Not Delivered': '{:,.0f}',
                'Collection %': '{:.1f}%', 'Delivery %': '{:.1f}%', 'Failed %': '{:.1f}%'
            })
            .background_gradient(subset=['Failed Collections'], cmap='Reds'),
        use_container_width=True,
        hide_index=True
    )

# ====================== FAILED SHOPS ======================
st.subheader("⚠️ Shops with Failed Collections")
if not filtered_df.empty:
    failed_shops = filtered_df[filtered_df['Failed Collections'] > 0].copy()

    if len(failed_shops) > 0:
        failed_shops['Failed %'] = (failed_shops['Failed Collections'] / failed_shops['Collection Volume'] * 100).round(1)
        failed_shops = failed_shops.sort_values(by='Failed Collections', ascending=False)
        
        st.dataframe(
            failed_shops[['Driver Name', 'Driver ID', 'Shop Name', 'Collection Volume', 
                          'Collected', 'Failed Collections', 'Failed %']]
            .style.format({
                'Collection Volume': '{:,.0f}', 'Collected': '{:,.0f}', 
                'Failed Collections': '{:,.0f}', 'Failed %': '{:.1f}%'
            })
            .background_gradient(subset=['Failed Collections'], cmap='Reds'),
            use_container_width=True,
            hide_index=True
        )
        st.info(f"🔴 Showing {len(failed_shops)} shops with failed collections.")
    else:
        st.success("✅ No failed collections today!")
else:
    st.info("No data available.")

st.caption("💡 Update drivers_lookup.xlsx when names change • Refresh after updating OOH_report.xlsx")