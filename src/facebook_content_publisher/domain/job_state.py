"""Strict state machines for persistent jobs."""

from enum import StrEnum

from facebook_content_publisher.domain.enums import CommentJobStatus, PublicationStatus


class InvalidTransition(ValueError):
    pass


PUBLICATION_TRANSITIONS = {
    PublicationStatus.DRAFT: {PublicationStatus.SCHEDULED, PublicationStatus.READY},
    PublicationStatus.SCHEDULED: {PublicationStatus.READY, PublicationStatus.CANCELLED},
    PublicationStatus.READY: {PublicationStatus.RUNNING, PublicationStatus.CANCELLED},
    PublicationStatus.RUNNING: {
        PublicationStatus.PUBLISHED,
        PublicationStatus.RETRY_WAIT,
        PublicationStatus.FAILED,
        PublicationStatus.UNKNOWN_RESULT,
    },
    PublicationStatus.RETRY_WAIT: {PublicationStatus.READY, PublicationStatus.CANCELLED},
    PublicationStatus.FAILED: {PublicationStatus.READY, PublicationStatus.CANCELLED},
    PublicationStatus.UNKNOWN_RESULT: {
        PublicationStatus.PUBLISHED,
        PublicationStatus.READY,
        PublicationStatus.CANCELLED,
    },
}

COMMENT_TRANSITIONS = {
    CommentJobStatus.PENDING: {CommentJobStatus.RUNNING, CommentJobStatus.CANCELLED},
    CommentJobStatus.RUNNING: {
        CommentJobStatus.COMPLETED,
        CommentJobStatus.RETRY_WAIT,
        CommentJobStatus.FAILED,
        CommentJobStatus.UNKNOWN_RESULT,
    },
    CommentJobStatus.RETRY_WAIT: {CommentJobStatus.PENDING, CommentJobStatus.CANCELLED},
    CommentJobStatus.FAILED: {CommentJobStatus.PENDING, CommentJobStatus.CANCELLED},
    CommentJobStatus.UNKNOWN_RESULT: {
        CommentJobStatus.COMPLETED,
        CommentJobStatus.PENDING,
        CommentJobStatus.CANCELLED,
    },
}


def ensure_transition(current: StrEnum, target: StrEnum) -> None:
    transitions = (
        PUBLICATION_TRANSITIONS if isinstance(current, PublicationStatus) else COMMENT_TRANSITIONS
    )
    if target not in transitions.get(current, set()):
        raise InvalidTransition(f"Invalid transition: {current.value} -> {target.value}")
