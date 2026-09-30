"""Strict structured translation output and usage metadata."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class TranslationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language_code: str = Field(min_length=2)
    post_text: str = Field(min_length=1)
    comment_text: str = Field(min_length=1)
    hashtags: list[str]
    quality_warnings: list[str]


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    output: dict[str, object]
    usage: TokenUsage = TokenUsage()
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class TranslationResult:
    output: TranslationOutput
    usage: TokenUsage
    prompt_version: str
    request_id: str | None = None
