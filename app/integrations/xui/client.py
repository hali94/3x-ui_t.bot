"""
3x-ui API integration client.

Built against the current 3x-ui OpenAPI spec (v2+ client-centric endpoints).
Auth: session cookie (POST /login) with automatic re-auth on 401.
Retries: tenacity exponential backoff on connection/timeout errors.
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.integrations.xui.exceptions import (
    XUIAuthException,
    XUIClientNotFoundException,
    XUIConnectionException,
    XUIServerException,
    XUITimeoutException,
)
from app.integrations.xui.models import XUIClientSettings, XUIClientTraffic, XUIInbound

logger = logging.getLogger(__name__)

_RETRY_EXCEPTIONS = (XUIConnectionException, XUITimeoutException)
_RETRY_KWARGS = dict(
    retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class XUIClient:
    """
    Async HTTP client for the 3x-ui REST API.

    One instance per server — sessions are per-instance so that
    multiple servers can be managed concurrently without cookie bleed.
    """

    def __init__(self, base_url: str, username: str, password: str, timeout: float = 15.0):
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._timeout = timeout
        self._session_cookie: dict[str, str] = {}
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "XUIClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            follow_redirects=True,
        )
        await self._authenticate()
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def _authenticate(self) -> None:
        try:
            resp = await self._client.post(
                "/login",
                data={"username": self._username, "password": self._password},
            )
            resp.raise_for_status()
            body = resp.json()
            if not body.get("success"):
                raise XUIAuthException(f"3x-ui login failed: {body.get('msg')}")
            self._session_cookie = dict(resp.cookies)
            logger.info("xui_auth_success", extra={"url": self._base_url})
        except httpx.ConnectError as exc:
            raise XUIConnectionException(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise XUITimeoutException(str(exc)) from exc

    async def _ensure_auth(self) -> None:
        if not self._session_cookie:
            await self._authenticate()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        await self._ensure_auth()
        try:
            resp = await self._client.request(
                method,
                path,
                cookies=self._session_cookie,
                **kwargs,
            )
        except httpx.ConnectError as exc:
            raise XUIConnectionException(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise XUITimeoutException(str(exc)) from exc

        if resp.status_code == 401:
            logger.info("xui_session_expired_reauth", extra={"url": self._base_url})
            await self._authenticate()
            resp = await self._client.request(
                method, path, cookies=self._session_cookie, **kwargs
            )

        if resp.status_code >= 500:
            raise XUIServerException(f"3x-ui server error {resp.status_code}: {resp.text[:256]}")

        body = resp.json()
        if not body.get("success", True):
            raise XUIServerException(f"3x-ui error: {body.get('msg', 'unknown')}")

        return body

    @retry(**_RETRY_KWARGS)
    async def _get(self, path: str, **kwargs) -> dict[str, Any]:
        return await self._request("GET", path, **kwargs)

    @retry(**_RETRY_KWARGS)
    async def _post(self, path: str, **kwargs) -> dict[str, Any]:
        return await self._request("POST", path, **kwargs)

    # ------------------------------------------------------------------
    # Inbounds
    # ------------------------------------------------------------------

    async def list_inbounds(self) -> list[XUIInbound]:
        body = await self._get("/panel/api/inbounds/list")
        return [XUIInbound.from_dict(item) for item in body.get("obj", [])]

    async def get_inbound(self, inbound_id: int) -> XUIInbound:
        body = await self._get(f"/panel/api/inbounds/get/{inbound_id}")
        obj = body.get("obj")
        if not obj:
            raise XUIClientNotFoundException(f"Inbound {inbound_id} not found")
        return XUIInbound.from_dict(obj)

    # ------------------------------------------------------------------
    # Clients  (new /panel/api/clients/* endpoints)
    # ------------------------------------------------------------------

    async def add_client(self, inbound_id: int, client: XUIClientSettings) -> None:
        """Create a new client and attach it to the given inbound."""
        payload = {
            "client": client.to_dict(),
            "inboundIds": [inbound_id],
        }
        await self._post("/panel/api/clients/add", json=payload)
        logger.info(
            "xui_client_added",
            extra={"inbound_id": inbound_id, "email": client.email, "uuid": client.id},
        )

    async def update_client(self, inbound_id: int, client: XUIClientSettings) -> None:
        """Update an existing client identified by email."""
        payload = {
            "client": client.to_dict(),
            "inboundIds": [inbound_id],
        }
        await self._post(f"/panel/api/clients/update/{quote(client.email, safe='')}", json=payload)
        logger.info("xui_client_updated", extra={"email": client.email})

    async def delete_client(self, email: str) -> None:
        """Delete a client by email address."""
        await self._post(f"/panel/api/clients/del/{quote(email, safe='')}")
        logger.info("xui_client_deleted", extra={"email": email})

    # ------------------------------------------------------------------
    # Traffic
    # ------------------------------------------------------------------

    async def get_client_traffic(self, email: str) -> XUIClientTraffic | None:
        """Fetch client details including current traffic counters."""
        try:
            body = await self._get(f"/panel/api/clients/get/{quote(email, safe='')}")
            obj = body.get("obj")
            if not obj:
                return None
            return XUIClientTraffic.from_dict(obj)
        except XUIServerException:
            return None

    async def reset_client_traffic(self, email: str) -> None:
        """Reset traffic counters for a single client."""
        await self._post("/panel/api/clients/bulkResetTraffic", json={"emails": [email]})
        logger.info("xui_traffic_reset", extra={"email": email})


class XUIClientFactory:
    @staticmethod
    def create(base_url: str, username: str, password: str) -> XUIClient:
        return XUIClient(base_url=base_url, username=username, password=password)
