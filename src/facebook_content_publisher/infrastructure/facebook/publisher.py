"""FacebookPublisher adapter over the centralized Graph client."""

from datetime import UTC, datetime
from pathlib import Path

from facebook_content_publisher.application.facebook import (
    CommentRequest,
    CommentResult,
    PageAccessStatus,
    PublishRequest,
    PublishResult,
)
from facebook_content_publisher.infrastructure.facebook.client import MetaGraphClient
from facebook_content_publisher.infrastructure.facebook.errors import (
    FacebookInvalidMediaError,
    FacebookNotConfiguredError,
)


class GraphApiFacebookPublisher:
    def __init__(
        self,
        credential_store,
        version="v24.0",
        timeout=30,
        transport=None,
        production_enabled=False,
    ):
        self.credentials = credential_store
        self.version = version
        self.timeout = timeout
        self.transport = transport
        self.production_enabled = production_enabled

    def _client(self, page_id: str) -> MetaGraphClient:
        if not self.production_enabled:
            raise FacebookNotConfiguredError(
                "PRODUCTION_DISABLED", "Production publishing safety switch is OFF"
            )
        token = self.credentials.get(page_id)
        if not token:
            raise FacebookNotConfiguredError(
                "PAGE_NOT_CONNECTED", "Facebook Page credential is not configured"
            )
        return MetaGraphClient(token, self.version, self.timeout, self.transport)

    async def validate_page_access(self, page_id: str) -> PageAccessStatus:
        client = self._client(page_id)
        try:
            result = await client.request("GET", f"/{page_id}", params={"fields": "id,name"})
        finally:
            await client.close()
        return PageAccessStatus(
            result.data.get("id") == page_id, page_id, result.data.get("name", "")
        )

    async def publish_text_post(self, request: PublishRequest) -> PublishResult:
        client = self._client(request.page_id)
        try:
            result = await client.request(
                "POST",
                f"/{request.page_id}/feed",
                data={"message": request.post_text},
                delivery_ambiguous=True,
            )
        finally:
            await client.close()
        return self._publish_result(result)

    async def publish_photo_post(self, request: PublishRequest) -> PublishResult:
        if len(request.media_assets) != 1:
            raise FacebookInvalidMediaError(
                "INVALID_MEDIA", "Photo publishing requires exactly one media asset"
            )
        return await self._upload(request, "photos", "source")

    async def publish_video_post(self, request: PublishRequest) -> PublishResult:
        if len(request.media_assets) != 1:
            raise FacebookInvalidMediaError(
                "INVALID_MEDIA", "Video publishing requires exactly one media asset"
            )
        return await self._upload(request, "videos", "source")

    async def _upload(self, request, endpoint, field):
        asset = request.media_assets[0]
        path = Path(asset.path)
        client = self._client(request.page_id)
        try:
            with path.open("rb") as stream:
                result = await client.request(
                    "POST",
                    f"/{request.page_id}/{endpoint}",
                    data={"description": request.post_text},
                    files={field: (path.name, stream, asset.mime_type)},
                    delivery_ambiguous=True,
                )
        finally:
            await client.close()
        return self._publish_result(result)

    async def create_comment(self, request: CommentRequest) -> CommentResult:
        if not request.facebook_post_id:
            raise ValueError("Facebook Post ID is required")
        client = self._client(request.page_id)
        try:
            result = await client.request(
                "POST",
                f"/{request.facebook_post_id}/comments",
                data={"message": request.comment_text},
                delivery_ambiguous=True,
            )
        finally:
            await client.close()
        return CommentResult(result.data["id"], datetime.now(UTC), result.request_id)

    @staticmethod
    def _publish_result(result):
        post_id = result.data.get("post_id") or result.data["id"]
        return PublishResult(post_id, datetime.now(UTC), None, result.request_id)
