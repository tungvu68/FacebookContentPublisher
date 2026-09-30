"""Provider-neutral structured translation orchestration."""

from typing import Protocol

from pydantic import ValidationError

from facebook_content_publisher.application.translation.prompt import (
    PromptBuilder,
    PromptContext,
)
from facebook_content_publisher.application.translation.schemas import (
    ProviderResponse,
    TranslationOutput,
    TranslationResult,
)
from facebook_content_publisher.domain.models import CountryProfile


class TranslationProvider(Protocol):
    def translate(self, prompt: str, *, prompt_version: str) -> ProviderResponse: ...


class TranslationValidationError(ValueError):
    pass


class TranslationService:
    def __init__(self, provider: TranslationProvider, builder: PromptBuilder | None = None) -> None:
        self._provider = provider
        self._builder = builder or PromptBuilder()

    def translate(
        self, country: CountryProfile, source_text: str, link_url: str | None = None
    ) -> TranslationResult:
        context = PromptContext(
            target_country_name=country.country_name,
            target_language_name=country.language_name,
            target_language_code=country.language_code,
            target_native_reader=country.native_reader_label or country.language_name,
            localization_level=country.localization_level,
            comment_template=country.default_comment_template,
            link_url=link_url or country.default_link,
            default_hashtags=country.default_hashtags,
            source_text=source_text,
            country_prompt_override=country.translation_prompt_override,
        )
        prompt = self._builder.render(context)
        response = self._provider.translate(prompt, prompt_version=self._builder.version)
        try:
            output = TranslationOutput.model_validate(response.output)
        except ValidationError as error:
            raise TranslationValidationError(
                "provider returned invalid structured output"
            ) from error
        if output.language_code.casefold() != country.language_code.casefold():
            raise TranslationValidationError(
                f"provider locale {output.language_code!r} does not match {country.language_code!r}"
            )
        return TranslationResult(output, response.usage, self._builder.version, response.request_id)
