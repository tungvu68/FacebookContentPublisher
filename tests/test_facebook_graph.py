import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from facebook_content_publisher.application.facebook import CommentRequest, PublishRequest
from facebook_content_publisher.application.facebook_connection import (
    OAuthStateStore,
    PageCredentialStore,
)
from facebook_content_publisher.application.secrets import InMemorySecretStore
from facebook_content_publisher.infrastructure.facebook.client import MetaGraphClient
from facebook_content_publisher.infrastructure.facebook.errors import (
    FacebookPermissionError,
    FacebookRateLimitError,
    FacebookTokenExpiredError,
    FacebookUnknownDeliveryError,
)
from facebook_content_publisher.infrastructure.facebook.publisher import (
    GraphApiFacebookPublisher,
)


def test_graph_url_header_and_page_pagination_do_not_put_token_in_url():
    requests = []

    def handler(request):
        requests.append(request)
        after = request.url.params.get("after")
        payload = (
            {"data": [{"id": "2", "name": "Two"}]}
            if after
            else {
                "data": [{"id": "1", "name": "One", "tasks": ["CREATE_CONTENT"]}],
                "paging": {"cursors": {"after": "next"}},
            }
        )
        return httpx.Response(200, json=payload)

    client = MetaGraphClient("top-secret", "v24.0", transport=httpx.MockTransport(handler))
    pages = asyncio.run(client.list_pages())
    asyncio.run(client.close())
    assert [page.id for page in pages] == ["1", "2"]
    assert all(request.url.path.startswith("/v24.0/") for request in requests)
    assert all("top-secret" not in str(request.url) for request in requests)
    assert requests[0].headers["authorization"] == "Bearer top-secret"


@pytest.mark.parametrize(
    "payload,status,error_type",
    [
        (
            {"error": {"code": 190, "error_subcode": 463, "message": "expired"}},
            400,
            FacebookTokenExpiredError,
        ),
        ({"error": {"code": 200, "message": "permission"}}, 403, FacebookPermissionError),
        ({"error": {"code": 4, "message": "limit"}}, 429, FacebookRateLimitError),
    ],
)
def test_graph_error_mapping(payload, status, error_type):
    client = MetaGraphClient(
        "secret", transport=httpx.MockTransport(lambda _: httpx.Response(status, json=payload))
    )
    with pytest.raises(error_type):
        asyncio.run(client.request("GET", "/me"))
    asyncio.run(client.close())


def test_ambiguous_timeout_mapping():
    def timeout(request):
        raise httpx.ReadTimeout("late", request=request)

    client = MetaGraphClient("secret", transport=httpx.MockTransport(timeout))
    with pytest.raises(FacebookUnknownDeliveryError) as caught:
        asyncio.run(client.request("POST", "/page/feed", delivery_ambiguous=True))
    assert caught.value.ambiguous
    asyncio.run(client.close())


def test_text_and_comment_contract_and_safety_switch():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={"id": "page_post" if request.url.path.endswith("feed") else "comment"},
            headers={"x-fb-trace-id": "trace"},
        )

    credentials = PageCredentialStore(InMemorySecretStore())
    credentials.save("page", "secret")
    disabled = GraphApiFacebookPublisher(credentials, transport=httpx.MockTransport(handler))
    with pytest.raises(Exception, match="safety switch"):
        asyncio.run(disabled.publish_text_post(PublishRequest("1", "key", "page", "hello")))
    publisher = GraphApiFacebookPublisher(
        credentials, transport=httpx.MockTransport(handler), production_enabled=True
    )
    post = asyncio.run(publisher.publish_text_post(PublishRequest("1", "key", "page", "hello")))
    comment = asyncio.run(
        publisher.create_comment(
            CommentRequest("2", "key2", "page", post.facebook_post_id, "details")
        )
    )
    assert post.facebook_post_id == "page_post" and comment.facebook_comment_id == "comment"
    assert [request.url.path for request in seen] == [
        "/v24.0/page/feed",
        "/v24.0/page_post/comments",
    ]


def test_oauth_state_is_single_use_and_expires():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = [now]
    states = OAuthStateStore(lambda: clock[0])
    value = states.issue(10)
    states.consume(value)
    with pytest.raises(ValueError):
        states.consume(value)
    expired = states.issue(10)
    clock[0] += timedelta(seconds=11)
    with pytest.raises(ValueError):
        states.consume(expired)
