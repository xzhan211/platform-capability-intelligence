"""Legacy data pull module. Uses both requests and httpx inconsistently."""
import requests
import httpx

ANALYTICS_API = "https://analytics-backend.internal"


def pull_metrics(metric_type: str) -> dict:
    # Some endpoints use requests
    resp = requests.get(f"{ANALYTICS_API}/metrics/{metric_type}", timeout=15)
    return resp.json()


async def pull_realtime(stream_id: str) -> list:
    # Async endpoints use httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{ANALYTICS_API}/streams/{stream_id}")
        return resp.json()
