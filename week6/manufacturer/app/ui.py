import requests
import streamlit as st


API_BASE_URL = "http://localhost:8002/api"

st.set_page_config(page_title="Week 6 Manufacturer", page_icon="🏭", layout="wide")


def api_get(path: str):
    response = requests.get(f"{API_BASE_URL}{path}", timeout=5)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict | None = None):
    response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def main():
    st.title("🏭 Week 6 Manufacturer")

    top_left, top_right = st.columns(2)
    with top_left:
        if st.button("Advance Day", type="primary"):
            api_post("/day/advance")
            st.rerun()

    with top_right:
        day = api_get("/day/current")
        st.metric("Current Day", day["current_day"])

    st.divider()

    providers = api_get("/providers")
    st.subheader("Suppliers")
    st.json(providers)

    stock_col, purchase_col = st.columns(2)
    with stock_col:
        st.subheader("Stock")
        st.json(api_get("/stock"))

    with purchase_col:
        st.subheader("Purchase Orders")
        st.json(api_get("/purchases"))

    st.divider()

    if providers:
        selected_supplier = st.selectbox("Supplier", [provider["name"] for provider in providers])
        catalog = api_get(f"/providers/{selected_supplier}/catalog")
        selected_product = st.selectbox("Product", [item["name"] for item in catalog])
        qty = st.number_input("Quantity", min_value=1, value=50)

        if st.button("Place Purchase Order"):
            api_post(
                "/purchases",
                {"supplier_name": selected_supplier, "product_name": selected_product, "quantity": qty},
            )
            st.rerun()


if __name__ == "__main__":
    main()
