"""
OpenEMR OAuth2 token management: registration, password grant, refresh, cache.
Sync implementation; no tokens or secrets in logs.
"""

import threading
import time

import httpx

from openemr_mcp.config import settings
from openemr_mcp.request_auth import get_request_auth_context

OAUTH_SCOPES = (
    "openid offline_access api:oemr api:fhir "
    "user/Patient.rs user/MedicationRequest.rs user/patient.crus user/prescription.rs "
    "user/Practitioner.rs user/Appointment.rs user/appointment.crus"
)
CACHE_BUFFER_SECONDS = 60


class OpenEMROAuthError(Exception):
    """Raised on OAuth2 registration or token failure. Message must not contain tokens or secrets."""

    pass


def register_client(scopes: str, _settings=None) -> tuple[str, str]:
    s = _settings if _settings is not None else settings
    payload = {
        "application_type": "private",
        "token_endpoint_auth_method": "client_secret_post",
        "redirect_uris": ["https://localhost/callback"],
        "scope": scopes,
        "client_name": "openemr-mcp",
        "contacts": [],
    }
    base = s.openemr_api_base_url.rstrip("/")
    url = f"{base}/oauth2/{s.openemr_oauth_site}/registration"
    with httpx.Client(verify=s.openemr_api_verify_ssl) as client:
        resp = client.post(url, json=payload)
    if resp.status_code >= 400:
        safe_text = (resp.text or "")[:200].replace("client_secret", "[REDACTED]")
        raise OpenEMROAuthError(f"OpenEMR OAuth2 registration failed: HTTP {resp.status_code}. {safe_text}")
    data = resp.json()
    client_id = data.get("client_id")
    client_secret = data.get("client_secret")
    if not client_id or not client_secret:
        raise OpenEMROAuthError("OpenEMR OAuth2 registration response missing client credentials")
    return (client_id, client_secret)


class OAuth2TokenManager:
    def __init__(self, _settings=None):
        self._settings = _settings if _settings is not None else settings
        self._client_id: str | None = self._settings.openemr_oauth_client_id
        self._client_secret: str | None = self._settings.openemr_oauth_client_secret
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0
        self._lock = threading.Lock()

    def _base_url(self) -> str:
        return self._settings.openemr_api_base_url.rstrip("/")

    def _token_url(self) -> str:
        return f"{self._base_url()}/oauth2/{self._settings.openemr_oauth_site}/token"

    def _has_user_credentials(self) -> bool:
        return bool(self._settings.openemr_oauth_username and self._settings.openemr_oauth_password)

    def _request_auth_required(self) -> bool:
        return self._settings.openemr_auth_mode == "request_token" or self._settings.openemr_require_request_auth

    def _get_request_access_token(self) -> str | None:
        context = get_request_auth_context()
        return context.openemr_access_token if context else None

    def _refresh_request_token(self, refresh_token: str) -> str:
        if not self._client_id or not self._client_secret:
            raise OpenEMROAuthError("OpenEMR client credentials required for request token refresh")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        with httpx.Client(verify=self._settings.openemr_api_verify_ssl) as client:
            resp = client.post(self._token_url(), data=data)
        if resp.status_code >= 400:
            raise OpenEMROAuthError(f"OpenEMR request token refresh failed: HTTP {resp.status_code}")
        out = resp.json()
        access_token = out.get("access_token")
        if not access_token:
            raise OpenEMROAuthError("OpenEMR request token refresh response missing access_token")
        return access_token

    def _do_registration(self) -> None:
        self._client_id, self._client_secret = register_client(OAUTH_SCOPES, self._settings)

    def _password_grant(self) -> str:
        data = {
            "grant_type": "password",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "username": self._settings.openemr_oauth_username,
            "password": self._settings.openemr_oauth_password,
            "user_role": "users",
            "scope": OAUTH_SCOPES,
        }
        with httpx.Client(verify=self._settings.openemr_api_verify_ssl) as client:
            resp = client.post(self._token_url(), data=data)
        if resp.status_code >= 400:
            raise OpenEMROAuthError(f"OpenEMR OAuth2 token request failed: HTTP {resp.status_code}")
        out = resp.json()
        self._access_token = out.get("access_token")
        self._refresh_token = out.get("refresh_token") or self._refresh_token
        self._expires_at = time.time() + max(0, out.get("expires_in") or 0)
        if not self._access_token:
            raise OpenEMROAuthError("OpenEMR OAuth2 token response missing access_token")
        return self._access_token

    def _refresh_grant(self) -> str:
        if not self._refresh_token:
            return self._password_grant()
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        with httpx.Client(verify=self._settings.openemr_api_verify_ssl) as client:
            resp = client.post(self._token_url(), data=data)
        if resp.status_code >= 400:
            self._refresh_token = None
            return self._password_grant()
        out = resp.json()
        self._access_token = out.get("access_token")
        self._refresh_token = out.get("refresh_token") or self._refresh_token
        self._expires_at = time.time() + max(0, out.get("expires_in") or 0)
        if not self._access_token:
            raise OpenEMROAuthError("OpenEMR OAuth2 refresh response missing access_token")
        return self._access_token

    def _is_cache_valid(self, force_refresh: bool) -> bool:
        if force_refresh or not self._access_token:
            return False
        return time.time() < (self._expires_at - CACHE_BUFFER_SECONDS)

    def get_valid_access_token(self, force_refresh: bool = False) -> str:
        with self._lock:
            request_context = get_request_auth_context()
            if request_context and request_context.openemr_access_token and not force_refresh:
                return request_context.openemr_access_token
            if request_context and request_context.refresh_token and self._settings.openemr_enable_request_token_refresh:
                return self._refresh_request_token(request_context.refresh_token)
            if self._request_auth_required():
                raise OpenEMROAuthError("Request access token required")
            if not self._client_id or not self._client_secret:
                if self._has_user_credentials():
                    self._do_registration()
                else:
                    raise OpenEMROAuthError("OpenEMR OAuth2 credentials not configured")
            if self._is_cache_valid(force_refresh):
                return self._access_token
            if self._refresh_token and not force_refresh and self._access_token:
                return self._refresh_grant()
            return self._password_grant()
