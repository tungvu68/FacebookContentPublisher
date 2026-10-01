"""Provider-independent translation failures."""


class TranslationError(RuntimeError):
    code = "provider_error"
    retryable = False


class MissingApiKeyError(TranslationError):
    code = "missing_api_key"


class AuthenticationTranslationError(TranslationError):
    code = "authentication"


class PermissionTranslationError(TranslationError):
    code = "permission_or_billing"


class RateLimitTranslationError(TranslationError):
    code = "rate_limit"
    retryable = True


class TimeoutTranslationError(TranslationError):
    code = "timeout"
    retryable = True


class NetworkTranslationError(TranslationError):
    code = "network"
    retryable = True


class ServerTranslationError(TranslationError):
    code = "server"
    retryable = True


class RefusalTranslationError(TranslationError):
    code = "refusal"


class IncompleteTranslationError(TranslationError):
    code = "incomplete"


class CancelledTranslationError(TranslationError):
    code = "cancelled"


def sanitize_error(error: BaseException) -> str:
    """Return a stable user-safe message without provider payloads or credentials."""

    if isinstance(error, TranslationError):
        return str(error) or error.code.replace("_", " ").title()
    return "Unexpected translation provider error"
