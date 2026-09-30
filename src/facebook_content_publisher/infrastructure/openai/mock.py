"""Offline structured translation provider for tests and development."""

import re

from facebook_content_publisher.application.translation.schemas import (
    ProviderResponse,
    TokenUsage,
)


class MockTranslationProvider:
    """Return deterministic schema-valid content without network access."""

    def translate(self, prompt: str, *, prompt_version: str) -> ProviderResponse:
        locale = re.search(r"^locale: (.+)$", prompt, re.MULTILINE)
        source = prompt.rsplit("SOURCE:\n", 1)[-1]
        language_code = locale.group(1).strip() if locale else "unknown"
        ending_emoji = source[-1] if source and ord(source[-1]) > 0xFFFF else ""
        body = f"[MOCK {language_code}] {source}"
        if ending_emoji and not body.endswith(ending_emoji):
            body += ending_emoji
        return ProviderResponse(
            output={
                "language_code": language_code,
                "post_text": body,
                "comment_text": body,
                "hashtags": [],
                "quality_warnings": ["Mock translation; not for publishing."],
            },
            usage=TokenUsage(input_tokens=len(prompt.split()), output_tokens=len(body.split())),
            request_id=f"mock-{prompt_version}",
        )
