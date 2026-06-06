"""Custom HTTP session with manual retry logic.
This predates the platform HTTP client and has not been migrated.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RetrySession(requests.Session):
    """Custom retry-enabled HTTP session."""

    def __init__(self, retries: int = 3, backoff_factor: float = 0.5):
        super().__init__()
        retry = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.mount("http://", adapter)
        self.mount("https://", adapter)


def get_session(timeout: int = 30) -> RetrySession:
    session = RetrySession(retries=3)
    session.headers.update({"Content-Type": "application/json"})
    return session
