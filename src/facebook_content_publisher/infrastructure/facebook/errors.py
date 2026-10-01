"""Typed Graph API failures consumed by scheduler retry classification."""

from facebook_content_publisher.application.facebook import PublisherError


class FacebookProviderError(PublisherError):
    pass


class FacebookNotConfiguredError(FacebookProviderError):
    pass


class FacebookAuthenticationError(FacebookProviderError):
    pass


class FacebookTokenExpiredError(FacebookAuthenticationError):
    pass


class FacebookPermissionError(FacebookProviderError):
    pass


class FacebookPageAccessError(FacebookProviderError):
    pass


class FacebookRateLimitError(FacebookProviderError):
    pass


class FacebookTemporaryError(FacebookProviderError):
    pass


class FacebookInvalidContentError(FacebookProviderError):
    pass


class FacebookInvalidMediaError(FacebookProviderError):
    pass


class FacebookUploadError(FacebookProviderError):
    pass


class FacebookTimeoutError(FacebookProviderError):
    pass


class FacebookConnectionError(FacebookProviderError):
    pass


class FacebookUnknownDeliveryError(FacebookProviderError):
    pass


def graph_error(code: int, subcode: int | None, message: str, http_status: int):
    safe = " ".join(message.split())[:500]
    if code == 190:
        cls = (
            FacebookTokenExpiredError
            if subcode in {458, 459, 460, 463, 464, 467}
            else FacebookAuthenticationError
        )
        return cls("TOKEN_EXPIRED", safe)
    if code in {10, 200, 299}:
        return FacebookPermissionError("PERMISSION", safe)
    if code in {4, 17, 32, 613} or http_status == 429:
        return FacebookRateLimitError("RATE_LIMIT", safe, retryable=True)
    if code in {1, 2} or http_status >= 500:
        return FacebookTemporaryError("TEMPORARY", safe, retryable=True)
    if code in {100, 2500}:
        return FacebookInvalidContentError("INVALID_CONTENT", safe)
    return FacebookProviderError("GRAPH_ERROR", safe)
