"""Centralized, injectable and token-safe Meta Graph HTTP client."""

from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from facebook_content_publisher.infrastructure.facebook.errors import (
    FacebookConnectionError,
    FacebookProviderError,
    FacebookTimeoutError,
    FacebookUnknownDeliveryError,
    graph_error,
)

GRAPH_BASE_URL = "https://graph.facebook.com"
CONTRACT_TESTED_VERSION = "v24.0"


class GraphErrorData(BaseModel):
    message: str = "Facebook Graph API error"
    type: str | None = None
    code: int = 0
    error_subcode: int | None = None
    fbtrace_id: str | None = None


class PageData(BaseModel):
    id: str
    name: str
    tasks: list[str] = Field(default_factory=list)


class PageListResponse(BaseModel):
    data: list[PageData]
    paging: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class GraphResponse:
    data: dict[str, Any]
    request_id: str | None


class MetaGraphClient:
    def __init__(self, token: str, version=CONTRACT_TESTED_VERSION, timeout=30.0, transport=None):
        if not token:
            raise ValueError("Graph access token is required")
        self.version = version
        self._client = httpx.AsyncClient(
            base_url=f"{GRAPH_BASE_URL}/{version}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            transport=transport,
        )

    async def close(self):
        await self._client.aclose()

    async def request(
        self, method: str, path: str, *, delivery_ambiguous=False, **kwargs
    ) -> GraphResponse:
        try:
            response = await self._client.request(method, path.lstrip("/"), **kwargs)
        except httpx.TimeoutException as error:
            if delivery_ambiguous:
                raise FacebookUnknownDeliveryError(
                    "TIMEOUT", "Provider delivery is unknown", ambiguous=True
                ) from error
            raise FacebookTimeoutError(
                "TIMEOUT", "Facebook request timed out", retryable=True
            ) from error
        except httpx.ConnectError as error:
            raise FacebookConnectionError(
                "CONNECTION", "Unable to connect to Facebook", retryable=True
            ) from error
        try:
            payload = response.json()
        except ValueError as error:
            raise FacebookProviderError(
                "MALFORMED_RESPONSE", "Facebook returned malformed JSON"
            ) from error
        if response.is_error or "error" in payload:
            raw = payload.get("error", {})
            try:
                parsed = GraphErrorData.model_validate(raw)
            except ValidationError:
                raise FacebookProviderError(
                    "MALFORMED_ERROR", "Facebook returned an invalid error envelope"
                ) from None
            raise graph_error(
                parsed.code, parsed.error_subcode, parsed.message, response.status_code
            )
        request_id = response.headers.get("x-fb-trace-id") or response.headers.get(
            "x-fb-request-id"
        )
        return GraphResponse(payload, request_id)

    async def list_pages(self, limit=100) -> list[PageData]:
        pages, after = [], None
        while len(pages) < limit:
            params = {"fields": "id,name,tasks", "limit": min(100, limit - len(pages))}
            if after:
                params["after"] = after
            result = await self.request("GET", "/me/accounts", params=params)
            parsed = PageListResponse.model_validate(result.data)
            pages.extend(parsed.data)
            after = ((parsed.paging or {}).get("cursors") or {}).get("after")
            if not after or not parsed.data:
                break
        return pages[:limit]
