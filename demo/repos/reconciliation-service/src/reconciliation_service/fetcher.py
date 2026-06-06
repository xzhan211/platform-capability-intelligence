"""Fetches reconciliation data from upstream services.
Uses plain requests without retry configuration.
"""
import requests


BASE_URL = "https://ledger-service.internal"


def fetch_transactions(account_id: str, date: str) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/accounts/{account_id}/transactions",
        params={"date": date},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_balances(account_id: str) -> dict:
    resp = requests.get(f"{BASE_URL}/accounts/{account_id}/balance", timeout=10)
    resp.raise_for_status()
    return resp.json()
