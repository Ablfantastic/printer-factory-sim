"""Streamlit dashboard: manufacturer ↔ provider."""
import os
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

_api_root = os.environ.get("PRINTER_SIM_API_URL", "http://localhost:8000").rstrip("/")
API_BASE_URL = f"{_api_root}/api"

st.set_page_config(
    page_title="Manufacturer",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def api_get(path: str):
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"No se pudo contactar la API ({API_BASE_URL}): {exc}")
        st.stop()


def api_post(path: str, payload: dict | None = None):
    try:
        response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"Error al enviar la petición: {exc}")
        resp = getattr(exc, "response", None)
        if resp is not None:
            try:
                st.json(resp.json())
            except Exception:
                st.code(resp.text or "")
        st.stop()


def _providers_df(data: list) -> pd.DataFrame:
    if not data:
        return pd.DataFrame(columns=["name", "url", "status", "provider_day"])
    rows = []
    for p in data:
        rows.append(
            {
                "name": p.get("name", ""),
                "url": p.get("url", ""),
                "status": p.get("status", ""),
                "provider_day": p.get("current_day"),
            }
        )
    return pd.DataFrame(rows)


def _stock_df(data: list) -> pd.DataFrame:
    if not data:
        return pd.DataFrame(columns=["product_name", "quantity", "product_id"])
    return pd.DataFrame(
        [
            {
                "product_name": x.get("product_name", ""),
                "quantity": x.get("quantity", 0),
                "product_id": x.get("product_id"),
            }
            for x in data
        ]
    )


def _purchases_df(data: list) -> pd.DataFrame:
    if not data:
        return pd.DataFrame(
            columns=[
                "id",
                "supplier",
                "product",
                "qty",
                "unit_price",
                "total",
                "placed_day",
                "eta_day",
                "status",
            ]
        )
    rows = []
    for o in data:
        rows.append(
            {
                "id": o.get("id"),
                "supplier": o.get("supplier_name", ""),
                "product": o.get("product_name", ""),
                "qty": o.get("quantity"),
                "unit_price": o.get("unit_price"),
                "total": o.get("total_price"),
                "placed_day": o.get("placed_day"),
                "eta_day": o.get("expected_delivery_day"),
                "status": o.get("status", ""),
            }
        )
    return pd.DataFrame(rows)


def _catalog_df(catalog: list) -> pd.DataFrame:
    if not catalog:
        return pd.DataFrame(columns=["name", "lead_days", "in_stock", "from_price"])
    rows = []
    for item in catalog:
        tiers = item.get("pricing_tiers") or []
        min_price = min((t.get("unit_price", t.get("price", 0)) for t in tiers), default=None)
        rows.append(
            {
                "name": item.get("name", ""),
                "lead_days": item.get("lead_time_days"),
                "in_stock": item.get("stock_quantity"),
                "from_price": min_price,
            }
        )
    return pd.DataFrame(rows)


def main():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; }
        div[data-testid="stMetricValue"] { font-size: 2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    day = api_get("/day/current")
    current = int(day["current_day"])

    h1, h2, h3 = st.columns([1.2, 1, 1])
    with h1:
        st.markdown("### Fabricante")
        st.caption("Inventario y compras al proveedor vía REST")
    with h2:
        st.metric("Día simulado", f"{current}")
    with h3:
        if st.button("Avanzar un día", type="primary", use_container_width=True):
            with st.spinner("Sincronizando con el proveedor…"):
                api_post("/day/advance")
            st.toast(f"Día avanzado → {current + 1}")
            st.rerun()

    st.divider()

    providers = api_get("/providers")
    stock = api_get("/stock")
    purchases = api_get("/purchases")

    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown("##### Proveedores")
        pdf = _providers_df(providers)
        if pdf.empty:
            st.info("No hay proveedores configurados en `config.json`.")
        else:
            st.dataframe(
                pdf,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "name": st.column_config.TextColumn("Proveedor", width="medium"),
                    "url": st.column_config.LinkColumn("URL", display_text="Abrir"),
                    "status": st.column_config.TextColumn("Estado"),
                    "provider_day": st.column_config.NumberColumn(
                        "Día (proveedor)", format="%d", width="small"
                    ),
                },
            )

    with c2:
        st.markdown("##### Stock local")
        sdf = _stock_df(stock)
        if sdf.empty:
            st.info("Sin líneas de inventario.")
        else:
            st.dataframe(
                sdf,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "product_name": st.column_config.TextColumn("Producto", width="large"),
                    "quantity": st.column_config.ProgressColumn(
                        "Cantidad",
                        format="%d",
                        min_value=0,
                        max_value=max(int(sdf["quantity"].max()), 1),
                    ),
                    "product_id": st.column_config.NumberColumn("ID", format="%d", width="small"),
                },
            )

    st.markdown("##### Pedidos de compra (al proveedor)")
    odf = _purchases_df(purchases)
    if odf.empty:
        st.info("Aún no hay pedidos. Usa el formulario de abajo para crear uno.")
    else:
        st.dataframe(
            odf,
            hide_index=True,
            use_container_width=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", format="%d", width="small"),
                "supplier": st.column_config.TextColumn("Proveedor", width="small"),
                "product": st.column_config.TextColumn("Producto", width="medium"),
                "qty": st.column_config.NumberColumn("Cant.", format="%d", width="small"),
                "unit_price": st.column_config.NumberColumn("Precio u.", format="%.2f €"),
                "total": st.column_config.NumberColumn("Total", format="%.2f €"),
                "placed_day": st.column_config.NumberColumn("Día pedido", format="%d", width="small"),
                "eta_day": st.column_config.NumberColumn("ETA día", format="%d", width="small"),
                "status": st.column_config.TextColumn("Estado", width="small"),
            },
        )

    st.divider()
    st.markdown("##### Nuevo pedido al proveedor")

    if not providers:
        st.warning("Configura al menos un proveedor en `manufacturer/config.json`.")
        return

    ok_providers = [p for p in providers if p.get("status") == "ok"]
    if not ok_providers:
        st.warning(
            "Ningún proveedor responde como **ok**. Arranca el provider en el puerto 8001 y recarga."
        )

    with st.container(border=True):
        names = [p["name"] for p in providers]
        selected_supplier = st.selectbox("Proveedor", names, key="supplier_pick")

        try:
            catalog = api_get(f"/providers/{quote(selected_supplier, safe='')}/catalog")
        except Exception:
            st.error("No se pudo cargar el catálogo.")
            return

        cdf = _catalog_df(catalog)
        st.caption("Catálogo remoto (solo lectura)")
        if cdf.empty:
            st.info("Catálogo vacío.")
        else:
            st.dataframe(
                cdf,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "name": st.column_config.TextColumn("SKU / nombre", width="medium"),
                    "lead_days": st.column_config.NumberColumn("Lead (días)", format="%d", width="small"),
                    "in_stock": st.column_config.NumberColumn("Stock proveedor", format="%d"),
                    "from_price": st.column_config.NumberColumn("Desde (€)", format="%.2f"),
                },
            )

        product_names = [item["name"] for item in catalog] if catalog else []
        if not product_names:
            st.warning("No hay productos en el catálogo para este proveedor.")
            return

        f1, f2, f3 = st.columns([2, 1, 1])
        with f1:
            selected_product = st.selectbox("Producto a pedir", product_names, key="product_pick")
        with f2:
            qty = st.number_input("Cantidad", min_value=1, value=10, step=1, key="qty_pick")
        with f3:
            st.write("")
            st.write("")
            if st.button("Enviar pedido", type="primary", use_container_width=True):
                with st.spinner("Creando pedido en el proveedor…"):
                    api_post(
                        "/purchases",
                        {
                            "supplier_name": selected_supplier,
                            "product_name": selected_product,
                            "quantity": int(qty),
                        },
                    )
                st.toast(f"Pedido: {selected_product} × {qty}")
                st.rerun()


if __name__ == "__main__":
    main()
