from types import SimpleNamespace

import httpx
import openai
import pytest

from facebook_content_publisher.application.secrets import InMemorySecretStore
from facebook_content_publisher.application.settings import ApplicationSettings
from facebook_content_publisher.application.translation.errors import (
    AuthenticationTranslationError,
    IncompleteTranslationError,
    MissingApiKeyError,
    NetworkTranslationError,
    PermissionTranslationError,
    RateLimitTranslationError,
    RefusalTranslationError,
    ServerTranslationError,
    TimeoutTranslationError,
)
from facebook_content_publisher.application.translation.schemas import TranslationOutput
from facebook_content_publisher.infrastructure.openai.adapter import (
    OPENAI_API_KEY,
    OpenAIErrorMapper,
    OpenAIResponsesProvider,
)


class FakeResponses:
    def __init__(self, response=None, error=None) -> None:
        self.response, self.error, self.kwargs = response, error, None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, responses) -> None:
        self.responses = responses


def success_response(with_usage: bool = True):
    usage = (
        SimpleNamespace(
            input_tokens=20,
            output_tokens=10,
            input_tokens_details=SimpleNamespace(cached_tokens=8),
        )
        if with_usage
        else None
    )
    return SimpleNamespace(
        status="completed",
        output_parsed=TranslationOutput(
            language_code="th-TH",
            post_text="โพสต์",
            comment_text="ความคิดเห็น",
            hashtags=[],
            quality_warnings=[],
        ),
        usage=usage,
        _request_id="req_safe",
    )


def provider(responses: FakeResponses, secrets=None, **settings):
    secret_store = secrets or InMemorySecretStore()
    secret_store.set_secret(OPENAI_API_KEY, "test-value")
    return OpenAIResponsesProvider(
        ApplicationSettings(**settings),
        secret_store,
        client_factory=lambda key: FakeClient(responses),
        sleeper=lambda delay: None,
    )


def test_responses_parse_uses_strict_pydantic_and_usage() -> None:
    responses = FakeResponses(success_response())
    result = provider(responses).translate("prompt", prompt_version="v2")
    assert responses.kwargs["text_format"] is TranslationOutput
    assert responses.kwargs["store"] is False
    assert "tools" not in responses.kwargs
    assert result.usage.cached_input_tokens == 8
    assert result.request_id == "req_safe"


def test_optional_usage_and_incomplete_response() -> None:
    result = provider(FakeResponses(success_response(False))).translate(
        "prompt", prompt_version="v2"
    )
    assert result.usage.input_tokens is None
    with pytest.raises(IncompleteTranslationError):
        provider(FakeResponses(SimpleNamespace(status="incomplete"))).translate(
            "prompt", prompt_version="v2"
        )


def test_missing_key_and_rate_limit_mapping() -> None:
    with pytest.raises(MissingApiKeyError):
        OpenAIResponsesProvider(
            ApplicationSettings(), InMemorySecretStore(), client_factory=lambda key: None
        ).translate("prompt", prompt_version="v2")
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    error = openai.RateLimitError(
        "rate limited", response=httpx.Response(429, request=request), body=None
    )
    assert isinstance(OpenAIErrorMapper.map(error), RateLimitTranslationError)


def test_retry_is_bounded_for_retryable_error() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    error = openai.RateLimitError("rate", response=httpx.Response(429, request=request), body=None)
    responses = FakeResponses(error=error)
    with pytest.raises(RateLimitTranslationError):
        provider(responses, retry_max_attempts=2).translate("prompt", prompt_version="v2")


def test_provider_error_mapping_and_refusal() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")

    def response(status: int) -> httpx.Response:
        return httpx.Response(status, request=request)

    cases = [
        (
            openai.AuthenticationError("bad", response=response(401), body=None),
            AuthenticationTranslationError,
        ),
        (
            openai.PermissionDeniedError("denied", response=response(403), body=None),
            PermissionTranslationError,
        ),
        (openai.APITimeoutError(request=request), TimeoutTranslationError),
        (openai.APIConnectionError(request=request), NetworkTranslationError),
        (
            openai.InternalServerError("server", response=response(500), body=None),
            ServerTranslationError,
        ),
    ]
    for error, expected in cases:
        assert isinstance(OpenAIErrorMapper.map(error), expected)

    refusal = SimpleNamespace(
        status="completed",
        output_parsed=None,
        output=[SimpleNamespace(type="message", content=[SimpleNamespace(type="refusal")])],
    )
    with pytest.raises(RefusalTranslationError):
        provider(FakeResponses(refusal)).translate("prompt", prompt_version="v2")
