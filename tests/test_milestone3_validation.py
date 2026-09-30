from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from facebook_content_publisher.application.dto import CountryProfileCreate
from facebook_content_publisher.application.dto.schemas import CampaignTargetInput
from facebook_content_publisher.application.media import calculate_sha256, validate_media
from facebook_content_publisher.domain.enums import MediaType, PublishMode


def country_values() -> dict[str, object]:
    return {
        "code": " th ",
        "country_name": " Thailand ",
        "language_code": "th-TH",
        "language_name": "Thai",
        "timezone": "Asia/Bangkok",
        "default_comment_template": "Details: {link}",
    }


def test_country_url_and_comment_template_validation() -> None:
    data = CountryProfileCreate(**country_values(), default_link="https://example.com")
    assert data.code == "TH"
    assert data.country_name == "Thailand"

    with pytest.raises(ValidationError, match="HTTP or HTTPS"):
        CountryProfileCreate(**country_values(), default_link="ftp://example.com")
    invalid = country_values()
    invalid["default_comment_template"] = "No placeholder"
    with pytest.raises(ValidationError, match="contain"):
        CountryProfileCreate(**invalid)


def test_schedule_converts_to_utc_and_delay_to_minutes() -> None:
    local = datetime.now() + timedelta(days=2)
    target = CampaignTargetInput(
        country_profile_id=uuid4(),
        publish_mode=PublishMode.SCHEDULED,
        scheduled_at=local,
        scheduled_timezone="Asia/Bangkok",
        comment_delay_hours=5,
        comment_delay_minutes=30,
    )
    assert target.delay_minutes_total == 330
    assert target.scheduled_at_utc is not None
    assert target.scheduled_at_utc.tzinfo is UTC


def test_media_validation_and_streaming_sha256(tmp_path: Path) -> None:
    media = tmp_path / "photo.jpg"
    media.write_bytes(b"example-image")
    result = validate_media(media)
    assert result.media_type is MediaType.IMAGE
    assert result.sha256 == calculate_sha256(media, chunk_size=2)

    unsupported = tmp_path / "file.txt"
    unsupported.write_text("no")
    with pytest.raises(ValueError, match="supported media"):
        validate_media(unsupported)
