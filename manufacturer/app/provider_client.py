import requests


class ProviderClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_catalog(self) -> list[dict]:
        response = requests.get(f"{self.base_url}/api/catalog", timeout=10.0)
        response.raise_for_status()
        return response.json()

    def create_order(self, buyer: str, product_id: int, quantity: int) -> dict:
        response = requests.post(
            f"{self.base_url}/api/orders",
            json={"buyer": buyer, "product_id": product_id, "quantity": quantity},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    def get_order(self, order_id: int) -> dict:
        response = requests.get(f"{self.base_url}/api/orders/{order_id}", timeout=10.0)
        response.raise_for_status()
        return response.json()

    def get_current_day(self) -> int:
        response = requests.get(f"{self.base_url}/api/day/current", timeout=10.0)
        response.raise_for_status()
        return response.json()["current_day"]

    def health(self) -> bool:
        response = requests.get(f"{self.base_url}/health", timeout=5.0)
        response.raise_for_status()
        return response.json().get("status") == "ok"
