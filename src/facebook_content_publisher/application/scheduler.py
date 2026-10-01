"""Persistent publication preparation, execution and recovery."""

import asyncio
import hashlib
import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import and_, select, update

from facebook_content_publisher.application.facebook import (
    CommentRequest,
    MediaSnapshot,
    PublisherError,
    PublishRequest,
)
from facebook_content_publisher.domain.enums import (
    CommentJobStatus,
    MediaType,
    PublicationStatus,
    PublishMode,
    TranslationStatus,
)
from facebook_content_publisher.infrastructure.database.orm import (
    ActivityLogRecord,
    CampaignTargetRecord,
    CommentJobRecord,
    CountryProfileRecord,
    LocalizedContentRecord,
    MediaAssetRecord,
    PublicationRecord,
)


def sanitize_error(value: object) -> str:
    text = " ".join(str(value).split())[:500]
    for marker in (
        "token=",
        "access_token",
        "appsecret_proof",
        "api_key=",
        "authorization:",
        "bearer ",
        "client_secret",
        "oauth code",
    ):
        if marker in text.lower():
            return "Sensitive provider error was redacted"
    return text


def retry_delay(attempt: int, initial=30.0, maximum=1800.0, jitter=0.15, rng=None) -> float:
    base = min(maximum, initial * (2 ** max(0, attempt - 1)))
    source = rng or random.random
    return base * (1 - jitter + source() * 2 * jitter)


def resolve_link(text: str, link: str | None) -> str:
    return text.replace("{link}", link or "").strip()


def validate_media(items: list[dict]) -> tuple[MediaSnapshot, ...]:
    result = []
    for item in items:
        path = Path(item["path"])
        if not path.is_file():
            raise PublisherError("MISSING_MEDIA", f"Media file is missing: {path.name}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != item["sha256"]:
            raise PublisherError("MODIFIED_MEDIA", f"Media file changed: {path.name}")
        result.append(MediaSnapshot(path, item["mime_type"], item["sha256"]))
    return tuple(result)


class SchedulerService:
    def __init__(self, sessions, publisher, settings, clock=None, worker_id=None):
        self.sessions = sessions
        self.publisher = publisher
        self.publishers = publisher if isinstance(publisher, dict) else {"mock": publisher}
        self.settings = settings
        self.clock = clock or (lambda: datetime.now(UTC))
        self.worker_id = worker_id or f"worker-{uuid4()}"
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._paused = False
        self._thread = None
        self.listeners = []
        self._scan_lock = threading.Lock()
        self._publication_pool = ThreadPoolExecutor(
            max_workers=settings.publication_concurrency, thread_name_prefix="publication"
        )
        self._comment_pool = ThreadPoolExecutor(
            max_workers=settings.comment_concurrency, thread_name_prefix="comment"
        )
        self._active_publications = 0
        self._active_comments = 0
        self._active_lock = threading.Lock()

    def _log(
        self,
        session,
        event,
        entity_type=None,
        entity_id=None,
        correlation_id="",
        message="",
        actor="system",
        metadata=None,
        level="INFO",
    ):
        from facebook_content_publisher.domain.enums import LogLevel

        session.add(
            ActivityLogRecord(
                id=uuid4(),
                level=LogLevel(level),
                event_type=event,
                entity_type=entity_type,
                entity_id=entity_id,
                safe_message=sanitize_error(message),
                created_at=self.clock(),
                correlation_id=correlation_id,
                actor=actor,
                metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
            )
        )

    def prepare_publications(self, campaign_id: UUID) -> list[UUID]:
        now = self.clock()
        created = []
        with self.sessions.begin() as session:
            rows = session.execute(
                select(LocalizedContentRecord, CampaignTargetRecord, CountryProfileRecord)
                .join(
                    CampaignTargetRecord,
                    and_(
                        CampaignTargetRecord.campaign_id == LocalizedContentRecord.campaign_id,
                        CampaignTargetRecord.country_profile_id
                        == LocalizedContentRecord.country_profile_id,
                    ),
                )
                .join(
                    CountryProfileRecord,
                    CountryProfileRecord.id == LocalizedContentRecord.country_profile_id,
                )
                .where(
                    LocalizedContentRecord.campaign_id == campaign_id,
                    LocalizedContentRecord.translation_status == TranslationStatus.APPROVED,
                )
            ).all()
            media = session.scalars(
                select(MediaAssetRecord).where(MediaAssetRecord.campaign_id == campaign_id)
            ).all()
            media_json = json.dumps(
                [
                    {
                        "path": m.absolute_path,
                        "mime_type": m.mime_type,
                        "sha256": m.sha256,
                        "type": m.media_type.value,
                    }
                    for m in media
                ]
            )
            for content, target, country in rows:
                if not country.facebook_page_id:
                    raise ValueError(f"{country.code}: Facebook Page ID is required")
                key = f"publication:{content.id}"
                if session.scalar(
                    select(PublicationRecord.id).where(PublicationRecord.idempotency_key == key)
                ):
                    continue
                record = PublicationRecord(
                    id=uuid4(),
                    campaign_id=campaign_id,
                    localized_content_id=content.id,
                    country_profile_id=country.id,
                    facebook_page_id=country.facebook_page_id,
                    idempotency_key=key,
                    publish_mode=target.publish_mode,
                    scheduled_at_utc=target.scheduled_at_utc,
                    status=PublicationStatus.READY
                    if target.publish_mode == PublishMode.IMMEDIATE
                    else PublicationStatus.SCHEDULED,
                    attempt_count=0,
                    max_attempts=self.settings.retry_max_attempts,
                    correlation_id=str(uuid4()),
                    post_text_snapshot=content.translated_text,
                    country_code_snapshot=country.code,
                    language_code_snapshot=content.language_code,
                    comment_text_snapshot=resolve_link(
                        content.comment_text,
                        target.link_override or content.link_url or country.default_link,
                    ),
                    link_url_snapshot=target.link_override
                    or content.link_url
                    or country.default_link,
                    media_snapshot_json=media_json,
                    delayed_comment_enabled=target.delayed_comment_enabled,
                    comment_delay_minutes=target.comment_delay_minutes,
                    provider_mode_snapshot=self.settings.facebook_provider_mode,
                    created_at=now,
                    updated_at=now,
                )
                session.add(record)
                self._log(
                    session,
                    "PUBLICATION_PREPARED",
                    "Publication",
                    record.id,
                    record.correlation_id,
                    f"Prepared {country.code} publication",
                )
                created.append(record.id)
        self._wake.set()
        return created

    def recover(self) -> int:
        now = self.clock()
        with self.sessions.begin() as session:
            expired = session.scalars(
                select(PublicationRecord).where(
                    PublicationRecord.status == PublicationStatus.RUNNING,
                    PublicationRecord.lease_expires_at_utc < now,
                )
            ).all()
            for job in expired:
                job.status = (
                    PublicationStatus.UNKNOWN_RESULT
                    if job.started_at_utc
                    else PublicationStatus.READY
                )
                job.lease_owner = None
                job.lease_expires_at_utc = None
                self._log(
                    session,
                    "LEASE_EXPIRED",
                    "Publication",
                    job.id,
                    job.correlation_id,
                    "Expired publication lease recovered",
                    level="WARNING",
                )
            expired_comments = session.scalars(
                select(CommentJobRecord).where(
                    CommentJobRecord.status == CommentJobStatus.RUNNING,
                    CommentJobRecord.lease_expires_at_utc < now,
                )
            ).all()
            for job in expired_comments:
                job.status = (
                    CommentJobStatus.UNKNOWN_RESULT
                    if job.started_at_utc
                    else CommentJobStatus.PENDING
                )
                job.lease_owner = None
                job.lease_expires_at_utc = None
                self._log(
                    session,
                    "LEASE_EXPIRED",
                    "CommentJob",
                    job.id,
                    job.correlation_id,
                    "Expired comment lease recovered",
                    level="WARNING",
                )
            published = session.scalars(
                select(PublicationRecord).where(
                    PublicationRecord.status == PublicationStatus.PUBLISHED,
                    PublicationRecord.delayed_comment_enabled.is_(True),
                    PublicationRecord.comment_text_snapshot != "",
                    ~PublicationRecord.id.in_(select(CommentJobRecord.publication_id)),
                )
            ).all()
            for job in published:
                published_at = job.published_at_utc or now
                session.add(
                    CommentJobRecord(
                        id=uuid4(),
                        publication_id=job.id,
                        execute_at_utc=published_at + timedelta(minutes=job.comment_delay_minutes),
                        comment_text=job.comment_text_snapshot,
                        link_url=job.link_url_snapshot,
                        idempotency_key=f"comment:{job.id}",
                        status=CommentJobStatus.PENDING,
                        attempt_count=0,
                        max_attempts=job.max_attempts,
                        page_id_snapshot=job.facebook_page_id,
                        facebook_post_id_snapshot=job.facebook_post_id or "",
                        correlation_id=job.correlation_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
                self._log(
                    session,
                    "COMMENT_JOB_RECOVERED",
                    "Publication",
                    job.id,
                    job.correlation_id,
                    "Recovered missing comment job",
                )
            return len(expired) + len(expired_comments) + len(published)

    def run_due_once(self) -> int:
        if self._paused:
            return 0
        if not self._scan_lock.acquire(blocking=False):
            return 0
        try:
            return self._run_due_scan()
        finally:
            self._scan_lock.release()

    def _run_due_scan(self) -> int:
        now = self.clock()
        with self.sessions.begin() as session:
            cutoff = now - timedelta(minutes=self.settings.overdue_grace_minutes)
            if self.settings.require_confirmation_after_overdue:
                session.execute(
                    update(PublicationRecord)
                    .where(
                        PublicationRecord.status == PublicationStatus.SCHEDULED,
                        PublicationRecord.scheduled_at_utc < cutoff,
                    )
                    .values(attention_required=True, updated_at=now)
                )
                session.execute(
                    update(CommentJobRecord)
                    .where(
                        CommentJobRecord.status == CommentJobStatus.PENDING,
                        CommentJobRecord.execute_at_utc < cutoff,
                    )
                    .values(attention_required=True, updated_at=now)
                )
            session.execute(
                update(PublicationRecord)
                .where(
                    PublicationRecord.status == PublicationStatus.SCHEDULED,
                    PublicationRecord.scheduled_at_utc <= now,
                    PublicationRecord.attention_required.is_(False),
                )
                .values(status=PublicationStatus.READY, updated_at=now)
            )
            session.execute(
                update(PublicationRecord)
                .where(
                    PublicationRecord.status == PublicationStatus.RETRY_WAIT,
                    PublicationRecord.next_retry_at_utc <= now,
                )
                .values(status=PublicationStatus.READY, updated_at=now)
            )
            session.execute(
                update(CommentJobRecord)
                .where(
                    CommentJobRecord.status == CommentJobStatus.RETRY_WAIT,
                    CommentJobRecord.next_retry_at_utc <= now,
                )
                .values(status=CommentJobStatus.PENDING, updated_at=now)
            )
        publication_ids = []
        for _ in range(self.settings.publication_concurrency):
            job_id = self._claim_publication(now)
            if not job_id:
                break
            publication_ids.append(job_id)
        comment_ids = []
        for _ in range(self.settings.comment_concurrency):
            job_id = self._claim_comment(now)
            if not job_id:
                break
            comment_ids.append(job_id)
        futures = [
            self._publication_pool.submit(self._tracked_publication, item)
            for item in publication_ids
        ]
        futures += [self._comment_pool.submit(self._tracked_comment, item) for item in comment_ids]
        if futures:
            wait(futures)
        return len(futures)

    def _tracked_publication(self, job_id):
        with self._active_lock:
            self._active_publications += 1
        try:
            self._execute_publication(job_id)
        finally:
            with self._active_lock:
                self._active_publications -= 1

    def _tracked_comment(self, job_id):
        with self._active_lock:
            self._active_comments += 1
        try:
            self._execute_comment(job_id)
        finally:
            with self._active_lock:
                self._active_comments -= 1

    def _claim_publication(self, now):
        with self.sessions.begin() as session:
            job_id = session.scalar(
                select(PublicationRecord.id)
                .where(PublicationRecord.status == PublicationStatus.READY)
                .order_by(PublicationRecord.created_at)
                .limit(1)
            )
            if not job_id:
                return None
            changed = session.execute(
                update(PublicationRecord)
                .where(
                    PublicationRecord.id == job_id,
                    PublicationRecord.status == PublicationStatus.READY,
                )
                .values(
                    status=PublicationStatus.RUNNING,
                    lease_owner=self.worker_id,
                    lease_expires_at_utc=now + timedelta(minutes=5),
                    heartbeat_at_utc=now,
                    started_at_utc=now,
                    attempt_count=PublicationRecord.attempt_count + 1,
                    updated_at=now,
                )
            ).rowcount
            if changed:
                job = session.get(PublicationRecord, job_id)
                self._log(
                    session,
                    "JOB_CLAIMED",
                    "Publication",
                    job_id,
                    job.correlation_id,
                    f"Claimed by {self.worker_id}",
                )
            return job_id if changed else None

    def _claim_comment(self, now):
        with self.sessions.begin() as session:
            job_id = session.scalar(
                select(CommentJobRecord.id)
                .where(
                    CommentJobRecord.status == CommentJobStatus.PENDING,
                    CommentJobRecord.execute_at_utc <= now,
                    CommentJobRecord.attention_required.is_(False),
                )
                .order_by(CommentJobRecord.execute_at_utc)
                .limit(1)
            )
            if not job_id:
                return None
            changed = session.execute(
                update(CommentJobRecord)
                .where(
                    CommentJobRecord.id == job_id,
                    CommentJobRecord.status == CommentJobStatus.PENDING,
                )
                .values(
                    status=CommentJobStatus.RUNNING,
                    lease_owner=self.worker_id,
                    lease_expires_at_utc=now + timedelta(minutes=5),
                    heartbeat_at_utc=now,
                    started_at_utc=now,
                    attempt_count=CommentJobRecord.attempt_count + 1,
                    updated_at=now,
                )
            ).rowcount
            if changed:
                job = session.get(CommentJobRecord, job_id)
                self._log(
                    session,
                    "JOB_CLAIMED",
                    "CommentJob",
                    job_id,
                    job.correlation_id,
                    f"Claimed by {self.worker_id}",
                )
            return job_id if changed else None

    def _execute_publication(self, job_id):
        with self.sessions() as session:
            job = session.get(PublicationRecord, job_id)
            snapshot = {c.name: getattr(job, c.name) for c in PublicationRecord.__table__.columns}
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat,
            args=(PublicationRecord, job_id, heartbeat_stop),
            daemon=True,
        )
        heartbeat.start()
        try:
            media = validate_media(json.loads(snapshot["media_snapshot_json"]))
            request = PublishRequest(
                str(job_id),
                snapshot["idempotency_key"],
                snapshot["facebook_page_id"],
                snapshot["post_text_snapshot"],
                media,
                snapshot["country_code_snapshot"],
                snapshot["language_code_snapshot"],
                snapshot["correlation_id"],
            )
            types = {item.get("type") for item in json.loads(snapshot["media_snapshot_json"])}
            provider = self.publishers.get(snapshot["provider_mode_snapshot"])
            if provider is None:
                raise PublisherError(
                    "PROVIDER_NOT_CONFIGURED", "Facebook production connection is not configured"
                )
            method = (
                provider.publish_video_post
                if MediaType.VIDEO.value in types
                else provider.publish_photo_post
                if media
                else provider.publish_text_post
            )
            result = asyncio.run(method(request))
        except PublisherError as exc:
            self._publication_failure(job_id, exc)
            return
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=1)
        now = result.published_at_utc
        with self.sessions.begin() as session:
            job = session.get(PublicationRecord, job_id)
            job.facebook_post_id = result.facebook_post_id
            job.facebook_post_url = result.facebook_post_url
            job.provider_request_id = result.provider_request_id
            job.published_at_utc = now
            job.completed_at_utc = now
            job.status = PublicationStatus.PUBLISHED
            job.lease_owner = job.lease_expires_at_utc = None
            self._log(
                session,
                "PUBLISH_SUCCESS",
                "Publication",
                job.id,
                job.correlation_id,
                "Mock publication completed",
            )
            if job.delayed_comment_enabled and job.comment_text_snapshot.strip():
                session.add(
                    CommentJobRecord(
                        id=uuid4(),
                        publication_id=job.id,
                        execute_at_utc=now + timedelta(minutes=job.comment_delay_minutes),
                        comment_text=job.comment_text_snapshot,
                        link_url=job.link_url_snapshot,
                        idempotency_key=f"comment:{job.id}",
                        status=CommentJobStatus.PENDING,
                        attempt_count=0,
                        max_attempts=job.max_attempts,
                        page_id_snapshot=job.facebook_page_id,
                        facebook_post_id_snapshot=result.facebook_post_id,
                        correlation_id=job.correlation_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
                self._log(
                    session,
                    "COMMENT_JOB_CREATED",
                    "Publication",
                    job.id,
                    job.correlation_id,
                    "Delayed comment job created",
                )
        self._notify("Publication published", str(job_id))

    def _publication_failure(self, job_id, exc):
        now = self.clock()
        with self.sessions.begin() as session:
            job = session.get(PublicationRecord, job_id)
            job.last_error_code, job.last_error_message = exc.code, sanitize_error(exc)
            if exc.ambiguous:
                job.status = PublicationStatus.UNKNOWN_RESULT
                job.attention_required = True
                event = "UNKNOWN_RESULT"
            elif exc.retryable and job.attempt_count < job.max_attempts:
                job.status = PublicationStatus.RETRY_WAIT
                job.next_retry_at_utc = now + timedelta(
                    seconds=retry_delay(
                        job.attempt_count,
                        self.settings.retry_initial_delay_seconds,
                        self.settings.retry_max_delay_seconds,
                    )
                )
                event = "RETRY_SCHEDULED"
            else:
                job.status = PublicationStatus.FAILED
                event = "JOB_FAILED"
            job.lease_owner = job.lease_expires_at_utc = None
            job.updated_at = now
            self._log(
                session,
                event,
                "Publication",
                job.id,
                job.correlation_id,
                job.last_error_message or exc.code,
                level="WARNING" if exc.retryable else "ERROR",
            )
        if exc.ambiguous or not exc.retryable:
            self._notify("Publication needs attention", exc.code)

    def _execute_comment(self, job_id):
        with self.sessions() as session:
            job = session.get(CommentJobRecord, job_id)
            snapshot = {c.name: getattr(job, c.name) for c in CommentJobRecord.__table__.columns}
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat,
            args=(CommentJobRecord, job_id, heartbeat_stop),
            daemon=True,
        )
        heartbeat.start()
        try:
            provider = self.publishers.get(snapshot["provider_mode_snapshot"])
            if provider is None:
                raise PublisherError(
                    "PROVIDER_NOT_CONFIGURED", "Facebook production connection is not configured"
                )
            result = asyncio.run(
                provider.create_comment(
                    CommentRequest(
                        str(job_id),
                        snapshot["idempotency_key"],
                        snapshot["page_id_snapshot"],
                        snapshot["facebook_post_id_snapshot"],
                        snapshot["comment_text"],
                        snapshot["correlation_id"],
                    )
                )
            )
        except PublisherError as exc:
            now = self.clock()
            with self.sessions.begin() as session:
                job = session.get(CommentJobRecord, job_id)
                job.last_error_code, job.last_error_message = exc.code, sanitize_error(exc)
                if exc.ambiguous:
                    job.status = CommentJobStatus.UNKNOWN_RESULT
                elif exc.retryable and job.attempt_count < job.max_attempts:
                    job.status = CommentJobStatus.RETRY_WAIT
                    job.next_retry_at_utc = now + timedelta(
                        seconds=retry_delay(
                            job.attempt_count,
                            self.settings.retry_initial_delay_seconds,
                            self.settings.retry_max_delay_seconds,
                        )
                    )
                else:
                    job.status = CommentJobStatus.FAILED
                job.lease_owner = job.lease_expires_at_utc = None
            return
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=1)
        with self.sessions.begin() as session:
            job = session.get(CommentJobRecord, job_id)
            job.facebook_comment_id, job.provider_request_id = (
                result.facebook_comment_id,
                result.provider_request_id,
            )
            job.completed_at_utc, job.status = result.created_at_utc, CommentJobStatus.COMPLETED
            job.lease_owner = job.lease_expires_at_utc = None
            self._log(
                session,
                "COMMENT_SUCCESS",
                "CommentJob",
                job.id,
                job.correlation_id,
                "Mock comment completed",
            )
        self._notify("Comment created", str(job_id))

    def _heartbeat(self, record_type, job_id, stop_event):
        running_status = (
            PublicationStatus.RUNNING
            if record_type is PublicationRecord
            else CommentJobStatus.RUNNING
        )
        while not stop_event.wait(self.settings.heartbeat_interval_seconds):
            now = self.clock()
            with self.sessions.begin() as session:
                changed = session.execute(
                    update(record_type)
                    .where(
                        record_type.id == job_id,
                        record_type.status == running_status,
                        record_type.lease_owner == self.worker_id,
                    )
                    .values(
                        heartbeat_at_utc=now,
                        lease_expires_at_utc=now
                        + timedelta(seconds=self.settings.lease_duration_seconds),
                    )
                ).rowcount
                if not changed:
                    return

    def action(self, kind: str, job_id: UUID, action: str):
        now = self.clock()
        record_type = PublicationRecord if kind == "publication" else CommentJobRecord
        with self.sessions.begin() as session:
            job = session.get(record_type, job_id)
            if action == "cancel" and job.status not in {
                PublicationStatus.PUBLISHED,
                CommentJobStatus.COMPLETED,
            }:
                job.status = (
                    PublicationStatus.CANCELLED
                    if kind == "publication"
                    else CommentJobStatus.CANCELLED
                )
                job.cancelled_at_utc = now
                event = "CANCELLED"
            elif action in {"retry", "run"}:
                job.status = (
                    PublicationStatus.READY if kind == "publication" else CommentJobStatus.PENDING
                )
                job.next_retry_at_utc = None
                event = "RUN_NOW" if action == "run" else "MANUAL_RETRY"
            elif action == "complete" and job.status in {
                PublicationStatus.UNKNOWN_RESULT,
                CommentJobStatus.UNKNOWN_RESULT,
            }:
                job.status = (
                    PublicationStatus.PUBLISHED
                    if kind == "publication"
                    else CommentJobStatus.COMPLETED
                )
                job.completed_at_utc = now
                job.attention_required = False
                event = "MARK_COMPLETED"
            else:
                raise ValueError("Action is not valid for the current job state")
            job.updated_at = now
            job.version += 1
            self._log(
                session,
                event,
                record_type.__name__.removesuffix("Record"),
                job.id,
                job.correlation_id,
                f"Operator action: {action}",
                actor="operator",
            )
        self._wake.set()

    def list_jobs(self):
        with self.sessions() as session:
            pubs = [
                ("Publication", x)
                for x in session.scalars(
                    select(PublicationRecord).order_by(PublicationRecord.created_at.desc())
                ).all()
            ]
            comments = [
                ("Comment", x)
                for x in session.scalars(
                    select(CommentJobRecord).order_by(CommentJobRecord.created_at.desc())
                ).all()
            ]
            return pubs + comments

    def get_job(self, kind: str, job_id: UUID):
        record_type = PublicationRecord if kind == "publication" else CommentJobRecord
        with self.sessions() as session:
            job = session.get(record_type, job_id)
            if not job:
                raise LookupError("Job not found")
            return {
                column.name: getattr(job, column.name) for column in record_type.__table__.columns
            }

    def activity(self, entity_id: UUID):
        with self.sessions() as session:
            rows = session.scalars(
                select(ActivityLogRecord)
                .where(ActivityLogRecord.entity_id == entity_id)
                .order_by(ActivityLogRecord.created_at)
            ).all()
            return [
                {
                    column.name: getattr(row, column.name)
                    for column in ActivityLogRecord.__table__.columns
                }
                for row in rows
            ]

    def reschedule(self, kind: str, job_id: UUID, when: datetime, expected_version: int):
        if when <= self.clock():
            raise ValueError("Scheduled time must be in the future")
        record_type = PublicationRecord if kind == "publication" else CommentJobRecord
        allowed = (
            {PublicationStatus.SCHEDULED, PublicationStatus.READY, PublicationStatus.RETRY_WAIT}
            if kind == "publication"
            else {CommentJobStatus.PENDING, CommentJobStatus.RETRY_WAIT}
        )
        target = PublicationStatus.SCHEDULED if kind == "publication" else CommentJobStatus.PENDING
        time_field = "scheduled_at_utc" if kind == "publication" else "execute_at_utc"
        with self.sessions.begin() as session:
            current = session.get(record_type, job_id)
            if not current or current.status not in allowed:
                raise ValueError("Job can no longer be rescheduled; refresh first")
            result = session.execute(
                update(record_type)
                .where(
                    record_type.id == job_id,
                    record_type.version == expected_version,
                    record_type.status == current.status,
                )
                .values(
                    **{
                        time_field: when,
                        "status": target,
                        "next_retry_at_utc": None,
                        "attention_required": False,
                        "version": expected_version + 1,
                        "updated_at": self.clock(),
                    }
                )
            )
            if result.rowcount != 1:
                raise ValueError("Job changed concurrently; refresh first")
            self._log(
                session,
                "RESCHEDULED",
                record_type.__name__.removesuffix("Record"),
                job_id,
                current.correlation_id,
                f"Rescheduled to {when.isoformat()}",
                actor="operator",
            )
        self._wake.set()

    def metrics(self):
        with self.sessions() as session:
            publication = {
                status.value: session.scalar(
                    select(__import__("sqlalchemy").func.count())
                    .select_from(PublicationRecord)
                    .where(PublicationRecord.status == status)
                )
                for status in PublicationStatus
            }
            comment = {
                status.value: session.scalar(
                    select(__import__("sqlalchemy").func.count())
                    .select_from(CommentJobRecord)
                    .where(CommentJobRecord.status == status)
                )
                for status in CommentJobStatus
            }
        return {
            "publications": publication,
            "comments": comment,
            "active_publications": self._active_publications,
            "active_comments": self._active_comments,
            "paused": self._paused,
        }

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.recover()
        self._thread = threading.Thread(target=self._loop, name="persistent-scheduler", daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            with suppress(Exception):
                self.run_due_once()
            self._wake.wait(self.settings.scheduler_poll_seconds)
            self._wake.clear()

    def stop(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=self.settings.graceful_shutdown_timeout_seconds)
        self._publication_pool.shutdown(wait=True, cancel_futures=False)
        self._comment_pool.shutdown(wait=True, cancel_futures=False)

    def pause(self):
        self._paused = True
        self.audit("SCHEDULER_PAUSED", "Scheduler paused", actor="operator")

    def resume(self):
        self._paused = False
        self._wake.set()
        self.audit("SCHEDULER_RESUMED", "Scheduler resumed", actor="operator")

    def audit(self, event: str, message: str, actor="system"):
        with self.sessions.begin() as session:
            self._log(session, event, message=message, actor=actor)

    @property
    def paused(self):
        return self._paused

    def _notify(self, title, message):
        for listener in self.listeners:
            with suppress(Exception):
                listener(title, message)
