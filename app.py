import streamlit as st
from geopy.geocoders import Nominatim
import math
import pandas as pd
import plotly.graph_objects as go

# --- 1. MARKET DATA (NOVEMBER 2025 ESTIMATES) ---
PRICES = {
    "panel_500w": 145000,     "battery_220ah": 340000, 
    "inverter_3kva": 650000,  "inverter_5kva": 1100000, 
    "inverter_10kva": 2600000,
    "install_base": 150000,   "install_heavy": 350000   
}

# Default Sun Data (Fallbacks)
SOLAR_DATA = {
    "Lagos": 4.4, "Abuja": 5.2, "Kano": 5.8, "Ibadan": 4.6, 
    "Port Harcourt": 3.8, "Enugu": 4.5, "Sokoto": 6.0
}

# Full Appliance Database with Surge Flags
APPLIANCES = {
    "Essentials": [
        {"name": "LED Bulb", "watts": 10, "surge": False},
        {"name": "Ceiling Fan (Ox)", "watts": 85, "surge": False},
        {"name": "Standing Fan", "watts": 55, "surge": False},
        {"name": "Phone/Tablet", "watts": 15, "surge": False},
        {"name": "Router/WiFi", "watts": 12, "surge": False}
    ],
    "Work & Tech": [
        {"name": "Laptop (Mac/HP)", "watts": 65, "surge": False},
        {"name": "Starlink Kit", "watts": 75, "surge": False},
        {"name": "Monitor (24in)", "watts": 35, "surge": False},
        {"name": "Desktop PC", "watts": 250, "surge": False}
    ],
    "Kitchen & Cooling": [
        {"name": "Small Fridge", "watts": 120, "surge": True},
        {"name": "Medium Freezer", "watts": 250, "surge": True},
        {"name": "Big Freezer (Chest)", "watts": 350, "surge": True},
        {"name": "Inverter AC (1HP)", "watts": 900, "surge": True},
        {"name": "Inverter AC (1.5HP)", "watts": 1400, "surge": True}
    ],
    "Heavy Duty": [
        {"name": "Pumping Machine (Sumo)", "watts": 750, "surge": True},
        {"name": "Washing Machine", "watts": 500, "surge": True},
        {"name": "Electric Kettle", "watts": 1500, "surge": False},
        {"name": "Microwave", "watts": 1200, "surge": False},
        {"name": "Ironing (Steam)", "watts": 1500, "surge": False}
    ]
}

# --- 2. LOGIC FUNCTIONS ---
def get_sun_hours(city_name):
    # 1. Check hardcoded list first
    for key in SOLAR_DATA:
        if key.lower() in city_name.lower():
            return SOLAR_DATA[key], f"Using historical data for {key}"
    # 2. Use GeoPy for others
    try:
        geolocator = Nominatim(user_agent="naijasolar_app")
        location = geolocator.geocode(f"{city_name}, Nigeria")
        if location:
            lat = location.latitude
            if lat > 11: hours = 5.8 # North
            elif lat > 9: hours = 5.2 # Middle Belt
            elif lat > 7: hours = 4.6 # South West
            else: hours = 4.0 # Delta/South
            return hours, f"Detected Lat: {lat:.2f} (Est. Sun: {hours}h)"
    except:
        pass
    return 4.6, "Using Nigeria Average (4.6h)"

# --- 3. APP UI ---
st.set_page_config(page_title="NaijaSolarOps Ultimate", page_icon="⚡", layout="wide")

with st.sidebar:
    st.header("📍 Project Context")
    city_input = st.text_input("City Location", "Ibadan")
    sun_hours, loc_msg = get_sun_hours(city_input)
    st.caption(f"☀️ {loc_msg}")
    st.metric("Peak Sun Hours", f"{sun_hours} hrs")
    
    st.divider()
    mode = st.radio("System Mode", 
        ["Reliability (24/7)", "Smart Saver (Day Only)"],
        help="Smart Saver excludes heavy appliances from Battery calculations."
    )

st.title("⚡ NaijaSolarOps: Professional Solar Engine")

# --- 4. APPLIANCE INPUTS ---
user_items = []
tabs = st.tabs(APPLIANCES.keys())

for i, (category, items) in enumerate(APPLIANCES.items()):
    with tabs[i]:
        for item in items:
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{item['name']}** ({item['watts']}W)")
            qty = c2.number_input("Qty", 0, 10, 0, key=f"q_{item['name']}")
            # Smart Defaults: High watt items default to low hours
            def_hr = 0.5 if item['watts'] > 1000 else 6.0
            hrs = c3.number_input("Hrs/Day", 0.0, 24.0, def_hr, key=f"h_{item['name']}")
            
            if qty > 0:
                user_items.append({**item, "qty": qty, "hours": hrs, "cat": category})

# --- 5. CALCULATION ENGINE ---
if st.button("🚀 Run Feasibility Analysis", type="primary"):
    if not user_items:
        st.error("Please select at least one appliance.")
    else:
        # A. Load Analysis
        total_daily_wh = 0
        peak_load_watts = 0
        night_load_wh = 0
        heavy_consumers = []
        
        for item in user_items:
            daily_use = item['watts'] * item['qty'] * item['hours']
            total_daily_wh += daily_use
            
            # Peak Power (For Inverter)
            peak_load_watts += (item['watts'] * item['qty'])
            
            # Identification for "The Why"
            if daily_use > 1000: 
                heavy_consumers.append(f"{item['name']} ({daily_use/1000:.1f} kWh)")

            # Battery Logic
            is_heavy = item['cat'] in ["Heavy Duty", "Kitchen & Cooling"]
            if mode.startswith("Smart") and is_heavy:
                pass # 0% Night usage
            else:
                night_load_wh += (daily_use * 0.6)

        # B. Sizing Hardware
        # Panels (Daily Load + 30% Loss Factor / Sun Hours)
        req_panel_kw = (total_daily_wh / 0.7) / (sun_hours * 1000)
        num_panels = math.ceil((req_panel_kw * 1000) / 500)
        
        # Inverter (Peak Load + 25% Safety Margin)
        req_inv_watts = peak_load_watts * 1.25
        if req_inv_watts < 3000: 
            inv_name, inv_price, sys_v = "3kVA (24V)", PRICES['inverter_3kva'], 24
        elif req_inv_watts < 5000: 
            inv_name, inv_price, sys_v = "5kVA (48V)", PRICES['inverter_5kva'], 48
        else: 
            inv_name, inv_price, sys_v = "10kVA (48V)", PRICES['inverter_10kva'], 48
            
        # Batteries (Night Load / 50% DoD)
        batt_wh_needed = night_load_wh / 0.5
        total_batt_ah = batt_wh_needed / sys_v
        # Calculate physical batteries (pairs for voltage)
        series_string = sys_v / 12 # e.g. 2 for 24V
        parallel_strings = math.ceil(total_batt_ah / 220)
        num_batteries = int(series_string * parallel_strings)
        if num_batteries < series_string: num_batteries = int(series_string)

        # C. Financials
        cost_panels = num_panels * PRICES['panel_500w']
        cost_batts = num_batteries * PRICES['battery_220ah']
        cost_install = PRICES['install_heavy'] if sys_v > 24 else PRICES['install_base']
        total_cost = cost_panels + cost_batts + inv_price + cost_install

        # --- 6. DISPLAY RESULTS ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Daily Load", f"{total_daily_wh/1000:.1f} kWh")
        m2.metric("Inverter", inv_name)
        m3.metric("Panels (500W)", num_panels)
        m4.metric("Batteries", num_batteries)
        
        st.success(f"💰 **Project Budget: ₦{total_cost:,.0f}**")

        # --- 7. VISUALIZATION (PLOTLY) ---
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("📊 Energy Balance")
            gen_wh = num_panels * 500 * sun_hours * 0.75
            
            # Chart Data
            df_chart = pd.DataFrame({
                "Metric": ["Required Energy", "Solar Generation"],
                "Value (kWh)": [total_daily_wh/1000, gen_wh/1000],
                "Color": ["#FF4B4B", "#00CC96"]
            })
            
            fig = go.Figure(data=[go.Bar(
                x=df_chart['Metric'], 
                y=df_chart['Value (kWh)'],
                marker_color=df_chart['Color'],
                text=df_chart['Value (kWh)'].map('{:,.1f}'.format),
                textposition='auto'
            )])
            fig.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)
            
            if gen_wh < total_daily_wh:
                st.warning("⚠️ Careful: Your consumption is higher than generation. You need more panels or less load!")

        with c2:
            st.subheader("🧐 Analysis")
            with st.expander("Why is this the cost?", expanded=True):
                if heavy_consumers:
                    st.write("**Top Energy Drainers:**")
                    for c in heavy_consumers:
                        st.caption(f"- {c}")
                else:
                    st.caption("Your load is very efficient!")
                
                st.write(f"**Battery Bank:** You need {num_batteries} batteries to survive the night.")
                if mode.startswith("Reliability"):
                    st.info("Tip: Switch to 'Smart Saver' mode to see if reducing night-time heavy loads saves money.")

        # --- 8. DOWNLOADS ---
        csv_data = f"Item,Qty,Unit Cost,Total\nPanels,{num_panels},{PRICES['panel_500w']},{cost_panels}\nBatteries,{num_batteries},{PRICES['battery_220ah']},{cost_batts}\nInverter ({inv_name}),1,{inv_price},{inv_price}\nInstallation,1,{cost_install},{cost_install}\nTOTAL,,-,{total_cost}"
        
        st.download_button(
            label="📄 Download Quote (CSV)",
            data=csv_data,
            file_name="naijasolar_quote.csv",
            mime="text/csv"
        )