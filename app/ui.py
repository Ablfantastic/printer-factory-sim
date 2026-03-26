"""Streamlit dashboard for 3D Printer Production Simulator."""
import streamlit as st
import requests
from datetime import datetime
import matplotlib.pyplot as plt

# API configuration
API_BASE_URL = "http://localhost:8000/api"

st.set_page_config(
    page_title="3D Printer Factory Simulator",
    page_icon="🏭",
    layout="wide"
)


def api_get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to the API."""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {e}")
        return None


def api_post(endpoint: str, data: dict = None) -> dict:
    """Make a POST request to the API."""
    try:
        response = requests.post(f"{API_BASE_URL}{endpoint}", json=data, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {e}")
        return None


def main():
    st.title("🏭 3D Printer Production Simulator")
    
    # Sidebar with controls
    with st.sidebar:
        st.header("Controls")
        
        if st.button("⏩ Advance Day", type="primary"):
            with st.spinner("Running simulation..."):
                result = api_post("/day/advance")
                if result:
                    st.success(f"Day {result['current_day']} completed!")
                    st.info(f"Events generated: {result['events_generated']}")
                    st.rerun()
        
        st.divider()
        st.caption("Production Planner Dashboard")
    
    # Header: Current simulated day
    calendar = api_get("/calendar")
    if calendar:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("Current Day", f"Day {calendar['current_day']}")
        with col2:
            st.metric("Simulated Date", calendar['simulated_date'])
    
    st.divider()
    
    # Main dashboard layout
    col_inventory, col_orders = st.columns(2)
    
    # Inventory Panel
    with col_inventory:
        st.subheader("📦 Inventory Levels")
        inventory = api_get("/inventory")
        if inventory:
            if not inventory:
                st.info("No inventory data yet. Run simulation or add stock.")
            else:
                for item in inventory:
                    qty = item['quantity']
                    color = "🟢" if qty >= 20 else "🟡" if qty >= 5 else "🔴"
                    st.write(f"{color} **{item['product_name']}**: {qty}")
        else:
            st.warning("Unable to fetch inventory.")
    
    # Pending Orders Panel
    with col_orders:
        st.subheader("📋 Pending Orders")
        orders = api_get("/orders/pending")
        if orders:
            if not orders:
                st.info("No pending orders.")
            else:
                for order in orders:
                    with st.expander(f"Order #{order['id']} - {order['quantity']} units"):
                        st.write(f"**Created:** {order['created_date']}")
                        st.write(f"**BOM Requirements:**")
                        bom = order.get('bom', [])
                        for b in bom:
                            st.write(f"  - Material {b['material_id']}: {b['quantity']}")
                        
                        if st.button(f"Release #{order['id']}", key=f"rel_{order['id']}"):
                            result = api_post(f"/orders/{order['id']}/release")
                            if result and result.get('success'):
                                st.success("Order released!")
                                st.rerun()
                            elif result:
                                st.error(result.get('error', 'Failed'))
        else:
            st.warning("Unable to fetch orders.")
    
    st.divider()
    
    # Purchasing Panel
    st.subheader("🛒 Purchase Orders")
    p_col1, p_col2, p_col3 = st.columns(3)
    
    with p_col1:
        suppliers = api_get("/suppliers")
        supplier_options = {s['name']: s['id'] for s in suppliers} if suppliers else {}
        selected_supplier = st.selectbox("Supplier", list(supplier_options.keys()) if supplier_options else [])
    
    with p_col2:
        products = api_get("/products")
        product_options = {p['name']: p['id'] for p in products if p['type'] == 'raw'} if products else {}
        selected_product = st.selectbox("Product", list(product_options.keys()) if product_options else [])
    
    with p_col3:
        quantity = st.number_input("Quantity", min_value=1, value=10)
    
    if st.button("Issue Purchase Order"):
        if selected_supplier and selected_product:
            result = api_post("/purchases", {
                "supplier_id": supplier_options[selected_supplier],
                "product_id": product_options[selected_product],
                "quantity": quantity
            })
            if result:
                st.success(f"PO created! Expected delivery: {result.get('expected_delivery', 'N/A')}")
                st.rerun()
        else:
            st.warning("Please select both supplier and product.")
    
    st.divider()
    
    # Charts Section
    st.subheader("📊 History & Analytics")
    events = api_get("/events")
    
    if events:
        # Count events by type
        event_types = {}
        for event in events:
            etype = event['type']
            event_types[etype] = event_types.get(etype, 0) + 1
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        
        # Event counts pie chart
        ax1.pie(event_types.values(), labels=event_types.keys(), autopct='%1.1f%%')
        ax1.set_title("Events by Type")
        
        # Events over time
        dates = {}
        for event in events:
            d = event['sim_date']
            dates[d] = dates.get(d, 0) + 1
        
        ax2.plot(list(dates.keys()), list(dates.values()), marker='o')
        ax2.set_title("Events Per Day")
        ax2.tick_params(axis='x', rotation=45)
        
        st.pyplot(fig)
    else:
        st.info("Run the simulation to see charts.")


if __name__ == "__main__":
    main()
