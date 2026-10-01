"""Official OpenAI Responses API structured-output adapter."""

import random
import time
from collections.abc import Callable
from threading import Event
from typing import Any

import openai
from openai import OpenAI

from facebook_content_publisher.application.secrets import SecretStore
from facebook_content_publisher.application.settings import ApplicationSettings
from facebook_content_publisher.application.translation.errors import (
    AuthenticationTranslationError,
    CancelledTranslationError,
    IncompleteTranslationError,
    MissingApiKeyError,
    NetworkTranslationError,
    PermissionTranslationError,
    RateLimitTranslationError,
    RefusalTranslationError,
    ServerTranslationError,
    TimeoutTranslationError,
    TranslationError,
)
from facebook_content_publisher.application.translation.schemas import (
    ProviderResponse,
    TokenUsage,
    TranslationOutput,
)

OPENAI_API_KEY = "openai_api_key"


class OpenAIErrorMapper:
    @staticmethod
    def map(error: BaseException) -> TranslationError:
        if isinstance(error, openai.AuthenticationError):
            return AuthenticationTranslationError("The OpenAI API key is invalid")
        if isinstance(error, openai.PermissionDeniedError):
            return PermissionTranslationError("OpenAI permission or billing access was denied")
        if isinstance(error, openai.RateLimitError):
            return RateLimitTranslationError("OpenAI rate limit reached")
        if isinstance(error, openai.APITimeoutError):
            return TimeoutTranslationError("OpenAI request timed out")
        if isinstance(error, openai.APIConnectionError):
            return NetworkTranslationError("Unable to connect to OpenAI")
        if isinstance(error, openai.InternalServerError):
            return ServerTranslationError("OpenAI is temporarily unavailable")
        if isinstance(error, openai.BadRequestError):
            return PermissionTranslationError("OpenAI rejected the request")
        return TranslationError("Unexpected OpenAI provider error")


class OpenAIResponsesProvider:
    """Parse strict Pydantic output with one bounded retry layer."""

    def __init__(
        self,
        settings: ApplicationSettings,
        secrets: SecretStore,
        client_factory: Callable[[str], Any] | None = None,
        cancel_event: Event | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.secrets = secrets
        self.client_factory = client_factory or (
            lambda key: OpenAI(api_key=key, timeout=settings.openai_timeout_seconds, max_retries=0)
        )
        self.cancel_event = cancel_event or Event()
        self.sleeper = sleeper

    def translate(self, prompt: str, *, prompt_version: str) -> ProviderResponse:
        key = self.secrets.get_secret(OPENAI_API_KEY)
        if not key:
            raise MissingApiKeyError("OpenAI API key is not configured")
        client = self.client_factory(key)
        last_error: TranslationError | None = None
        for attempt in range(1, self.settings.retry_max_attempts + 1):
            if self.cancel_event.is_set():
                raise CancelledTranslationError("Translation was cancelled")
            try:
                response = client.responses.parse(
                    model=self.settings.openai_model,
                    input=prompt,
                    text_format=TranslationOutput,
                    store=False,
                    timeout=self.settings.openai_timeout_seconds,
                )
                return self._convert(response)
            except TranslationError:
                raise
            except Exception as error:
                mapped = OpenAIErrorMapper.map(error)
                last_error = mapped
                if not mapped.retryable or attempt >= self.settings.retry_max_attempts:
                    raise mapped from error
                delay = min(
                    self.settings.retry_initial_delay_seconds * (2 ** (attempt - 1)),
                    self.settings.retry_max_delay_seconds,
                )
                self.sleeper(delay + random.uniform(0, min(1.0, delay / 4)))
        raise last_error or TranslationError("OpenAI request failed")

    @staticmethod
    def _convert(response: Any) -> ProviderResponse:
        status = getattr(response, "status", "completed")
        if status != "completed":
            raise IncompleteTranslationError("OpenAI returned an incomplete response")
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            output_items = getattr(response, "output", []) or []
            if any(
                getattr(item, "type", "") == "refusal"
                or any(
                    getattr(content, "type", "") == "refusal"
                    for content in (getattr(item, "content", []) or [])
                )
                for item in output_items
            ):
                raise RefusalTranslationError("OpenAI refused the translation request")
            raise IncompleteTranslationError("OpenAI returned no structured output")
        output = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
        usage = getattr(response, "usage", None)
        details = getattr(usage, "input_tokens_details", None) if usage else None
        return ProviderResponse(
            output=output,
            usage=TokenUsage(
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                cached_input_tokens=getattr(details, "cached_tokens", None),
            ),
            request_id=getattr(response, "_request_id", None),
            model_name=getattr(response, "model", None),
        )
