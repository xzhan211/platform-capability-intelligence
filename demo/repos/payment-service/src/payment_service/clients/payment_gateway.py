"""Payment gateway client using the platform HTTP client."""
from platform_http_client import PlatformHttpClient, HttpClientConfig

_config = HttpClientConfig(
    base_url="https://payment-gateway.internal",
    timeout_seconds=30,
    retry_attempts=3,
)


class PaymentGatewayClient:
    def __init__(self):
        self._http = PlatformHttpClient(config=_config)

    def submit_payment(self, payload: dict) -> dict:
        response = self._http.post("/v1/payments", json=payload)
        response.raise_for_status()
        return response.json()

    def get_payment_status(self, payment_id: str) -> dict:
        response = self._http.get(f"/v1/payments/{payment_id}")
        response.raise_for_status()
        return response.json()
