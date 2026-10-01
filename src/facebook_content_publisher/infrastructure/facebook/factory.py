"""Facebook provider selection; production intentionally fails closed."""

from facebook_content_publisher.infrastructure.facebook.mock import MockFacebookPublisher


class FacebookProductionNotConfigured(RuntimeError):
    pass


def create_facebook_publisher(mode: str, **mock_options):
    if mode == "mock":
        return MockFacebookPublisher(**mock_options)
    if mode == "graph_api":
        credential_store = mock_options.pop("credential_store", None)
        if credential_store is None:
            raise FacebookProductionNotConfigured(
                "Facebook production connection is not configured"
            )
        from facebook_content_publisher.infrastructure.facebook.publisher import (
            GraphApiFacebookPublisher,
        )

        return GraphApiFacebookPublisher(credential_store, **mock_options)
    raise ValueError(f"Unsupported Facebook provider mode: {mode}")
