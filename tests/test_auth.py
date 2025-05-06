# tests/test_auth.py

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from httpx import AsyncClient, Response
from app.main import app
from app.services.keycloak import KeycloakService
from unittest.mock import AsyncMock, patch, MagicMock
import json


def create_mock_response(status_code: int, data: dict) -> JSONResponse:
    """Create a mock response with cookies"""
    response = JSONResponse(content=data, status_code=status_code)
    response.set_cookie(
        "access_token",
        data["access_token"],
        httponly=True,
        secure=True,
        samesite="lax"
    )
    response.set_cookie(
        "refresh_token",
        data["refresh_token"],
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return response


@pytest.mark.asyncio
async def test_login():
    mock_tokens = {
        "access_token": "sample_access_token",
        "refresh_token": "sample_refresh_token",
        "id_token": "sample_id_token",
        "expires_in": 360,
        "refresh_expires_in": 1800,
    }

    with patch.object(KeycloakService, 'authenticate_user', new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = mock_tokens

        async with AsyncClient(
            app=app,
            base_url="http://test",
            follow_redirects=True
        ) as ac:
            response = await ac.post(
                "/auth/login",
                json={
                    "username": "testuser",
                    "password": "password"
                }
            )

            assert response.status_code == 200
            assert "access_token" in response.cookies
            assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_refresh_token():
    mock_tokens = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "id_token": "new_id_token",
        "expires_in": 300,
        "refresh_expires_in": 1800
    }

    with patch.object(KeycloakService, 'refresh_token', new_callable=AsyncMock) as mock_refresh:
        mock_refresh.return_value = mock_tokens

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/refresh-token",
                json={"refresh_token": "old_refresh_token"}
            )

            assert response.status_code == 200
            assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_invalid_login():
    with patch.object(KeycloakService, 'authenticate_user', new_callable=AsyncMock) as mock_auth:
        mock_auth.side_effect = HTTPException(
            status_code=401, detail="Invalid credentials")
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/login",
                json={
                    "username": "invaliduser",
                    "password": "wrongpassword"
                }
            )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_callback():
    mock_tokens = {
        "access_token": "callback_access_token",
        "refresh_token": "callback_refresh_token",
        "id_token": "callback_id_token",
        "expires_in": 300,
        "refresh_expires_in": 1800
    }

    with patch.object(KeycloakService, 'exchange_code', new_callable=AsyncMock) as mock_exchange:
        mock_exchange.return_value = mock_tokens
        mock_response = create_mock_response(200, mock_tokens)
        mock_exchange.return_value = mock_response

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get(
                "/auth/callback",
                params={
                    "code": "sample_code",
                    "state": "/",
                    "redirect_uri": "http://localhost:8000/auth/callback"
                }
            )
            assert response.status_code == 200
            assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_logout():
    with patch.object(KeycloakService, 'logout', new_callable=AsyncMock) as mock_logout:
        mock_logout.return_value = True
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/logout",
                headers={"Authorization": "Bearer sample_valid_token"}
            )
            assert response.status_code == 200
