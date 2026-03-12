"""Tests that index.html is always served with Cache-Control: no-store."""
import pytest
from fastapi.testclient import TestClient


def test_root_returns_no_store_header():
    """GET / must return Cache-Control: no-store so browsers never cache stale JS."""
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"


def test_index_html_returns_no_store_header():
    """GET /index.html must also return Cache-Control: no-store.

    StaticFiles would serve this path without a cache header, so a dedicated
    route is needed to ensure browsers always fetch the latest version.
    """
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/index.html")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"
