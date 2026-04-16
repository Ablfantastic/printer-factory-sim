"""Streamlit dashboard for 3D Printer Production Simulator."""
import os
import streamlit as st
import requests
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

# API base (override when UI and API run on different hosts)
_api_root = os.environ.get("PRINTER_SIM_API_URL", "http://localhost:8000").rstrip("/")
API_BASE_URL = f"{_api_root}/api"

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
                    st.success(
                        f"Simulated **{result.get('simulated_date', '')}**. "
                        f"Calendar now at day **{result.get('current_day', '?')}**."
                    )
                    st.info(f"Events generated: {result['events_generated']}")
                    st.rerun()

        st.divider()
        st.markdown("**Restart simulation**")
        st.caption(
            "Resets the calendar to day 1, restores default inventory, and removes "
            "all manufacturing orders, purchase orders, and event history."
        )
        if st.button("🔄 Restart simulation", type="secondary"):
            with st.spinner("Resetting database..."):
                result = api_post("/simulation/reset")
                if result and result.get("success"):
                    st.success(result.get("message", "Reset complete."))
                    st.rerun()
                elif result is not None:
                    st.error("Reset failed.")
        
        st.divider()
        st.caption("Production planner — raw stock arrives on the PO expected delivery date when you advance the day.")
    
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
        if inventory is not None:
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
        if orders is not None:
            if not orders:
                st.info("No pending orders. Advance the day to generate demand.")
            else:
                for order in orders:
                    with st.expander(f"Order #{order['id']} - {order['quantity']} units"):
                        st.write(f"**Created:** {order['created_date']}")
                        st.write("**BOM requirements:**")
                        bom = order.get("bom", [])
                        for b in bom:
                            label = b.get("material_name") or f"id {b['material_id']}"
                            st.write(f"  - {label}: {b['quantity']}")

                        if st.button(f"Release #{order['id']}", key=f"rel_{order['id']}"):
                            result = api_post(f"/orders/{order['id']}/release")
                            if result and result.get("success"):
                                st.success("Order released!")
                                st.rerun()
                            elif result:
                                st.error(result.get("error", "Failed"))
        else:
            st.warning("Unable to fetch orders (is the API running?).")
    
    st.divider()

    # Supplier lead times & open PO ETAs
    st.subheader("🚚 Supplier lead times & arrivals")
    eta = api_get("/purchasing/eta")
    if eta is not None:
        st.caption(
            f"Simulated **today**: {eta.get('simulated_date', '')} — "
            "“If ordered today” assumes a PO issued now; inventory still updates on that arrival date when you advance days."
        )
        cat = eta.get("catalog") or []
        if cat:
            df_cat = pd.DataFrame(
                [
                    {
                        "Supplier": r["supplier_name"],
                        "Supplier #": r["supplier_id"],
                        "Material": r["material_name"],
                        "Lead (days)": r["lead_time_days"],
                        "Arrives on (if ordered today)": r["arrival_date_if_ordered_today"],
                        "Days to arrival": r["days_to_arrival_if_ordered_today"],
                    }
                    for r in cat
                ]
            )
            st.dataframe(df_cat, use_container_width=True, hide_index=True)
        opens = eta.get("open_purchase_orders") or []
        if opens:
            st.markdown("**Open purchase orders (not yet delivered)**")
            df_open = pd.DataFrame(
                [
                    {
                        "PO #": r["id"],
                        "Supplier": r["supplier_name"],
                        "Material": r["material_name"],
                        "Qty": r["quantity"],
                        "Issued": r["issue_date"],
                        "Expected delivery": r["expected_delivery"],
                        "Days until delivery": r["days_until_delivery"],
                        "Status": r["status"],
                    }
                    for r in opens
                ]
            )
            st.dataframe(df_open, use_container_width=True, hide_index=True)
        elif not cat:
            st.info("No supplier rows.")
    else:
        st.warning("Could not load purchasing ETA.")

    st.divider()

    # Purchasing Panel
    st.subheader("🛒 Purchase Orders")
    p_col1, p_col2, p_col3 = st.columns(3)
    
    with p_col1:
        suppliers = api_get("/suppliers")
        supplier_options = (
            {f"{s['name']} (#{s['id']})": s["id"] for s in suppliers}
            if suppliers
            else {}
        )
        selected_supplier = st.selectbox("Supplier", list(supplier_options.keys()) if supplier_options else [])
    
    with p_col2:
        products = api_get("/products")
        product_options = {p['name']: p['id'] for p in products if p['type'] == 'raw'} if products else {}
        selected_product = st.selectbox("Product", list(product_options.keys()) if product_options else [])
    
    with p_col3:
        quantity = st.number_input("Quantity", min_value=1, value=10)
    
    st.caption(
        "Materials are added to inventory on the **expected delivery** date "
        "(issue date + supplier lead time). Advance days until that date."
    )
    if st.button("Issue Purchase Order"):
        if selected_supplier and selected_product:
            result = api_post("/purchases", {
                "supplier_id": supplier_options[selected_supplier],
                "product_id": product_options[selected_product],
                "quantity": quantity
            })
            if result:
                st.success(
                    f"PO #{result.get('id', '')} created. "
                    f"Expected delivery: **{result.get('expected_delivery', 'N/A')}** "
                    f"(inventory updates on that simulated date)."
                )
                st.rerun()
        else:
            st.warning("Please select both supplier and product.")
    
    st.divider()
    
    # Charts Section
    st.subheader("📊 History & Analytics")
    events = api_get("/events")

    if events is not None:
        if not events:
            st.info("No events logged yet. Advance the day or issue a purchase order.")
        else:
            event_types = {}
            for event in events:
                etype = event["type"]
                event_types[etype] = event_types.get(etype, 0) + 1

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

            ax1.pie(event_types.values(), labels=event_types.keys(), autopct="%1.1f%%")
            ax1.set_title("Events by Type")

            dates = {}
            for event in events:
                d = event["sim_date"]
                dates[d] = dates.get(d, 0) + 1

            ax2.plot(list(dates.keys()), list(dates.values()), marker="o")
            ax2.set_title("Events Per Day")
            ax2.tick_params(axis="x", rotation=45)

            st.pyplot(fig)
    else:
        st.warning("Unable to load events (is the API running?).")


if __name__ == "__main__":
    main()
