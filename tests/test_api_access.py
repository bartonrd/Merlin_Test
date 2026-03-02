"""Tests for CORS middleware and API key authentication."""
import pytest
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers – build a minimal FastAPI app that mirrors app/main.py behaviour
# ---------------------------------------------------------------------------

def _build_app(api_key: str = "", cors_origins: str = "*") -> TestClient:
    """Build a minimal test app wired with CORS middleware and API key auth."""
    app = FastAPI()

    origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _hdr = APIKeyHeader(name="X-API-Key", auto_error=False)

    async def _key_dep(key: str = Security(_hdr)) -> None:
        if api_key and key != api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    @app.get("/probe")
    async def probe(_: None = Depends(_key_dep)):
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# CORS tests
# ---------------------------------------------------------------------------


def test_cors_wildcard_allows_any_origin():
    client = _build_app(cors_origins="*")
    resp = client.options(
        "/probe",
        headers={
            "Origin": "https://external-app.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") in (
        "*",
        "https://external-app.example.com",
    )


def test_cors_specific_origin_allowed():
    client = _build_app(cors_origins="https://my-app.example.com")
    resp = client.options(
        "/probe",
        headers={
            "Origin": "https://my-app.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://my-app.example.com"


def test_cors_specific_origin_blocked():
    client = _build_app(cors_origins="https://my-app.example.com")
    resp = client.options(
        "/probe",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Origin not in allow list → no ACAO header
    assert "access-control-allow-origin" not in resp.headers


# ---------------------------------------------------------------------------
# API key tests
# ---------------------------------------------------------------------------


def test_api_key_disabled_allows_unauthenticated():
    """When api_key is empty, all requests should be allowed."""
    client = _build_app(api_key="")
    resp = client.get("/probe")
    assert resp.status_code == 200


def test_api_key_enabled_rejects_missing_key():
    client = _build_app(api_key="secret-key")
    resp = client.get("/probe")
    assert resp.status_code == 401


def test_api_key_enabled_rejects_wrong_key():
    client = _build_app(api_key="secret-key")
    resp = client.get("/probe", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


def test_api_key_enabled_accepts_correct_key():
    client = _build_app(api_key="secret-key")
    resp = client.get("/probe", headers={"X-API-Key": "secret-key"})
    assert resp.status_code == 200

