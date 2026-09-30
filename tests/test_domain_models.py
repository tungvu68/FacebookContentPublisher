from datetime import UTC

from facebook_content_publisher.domain.enums import CampaignStatus
from facebook_content_publisher.domain.models import Campaign, CountryProfile


def test_entities_use_uuid_and_utc_timestamps() -> None:
    country = CountryProfile(
        code="TH",
        country_name="Thailand",
        language_code="th-TH",
        language_name="Thai",
        timezone="Asia/Bangkok",
        default_comment_template="Details: {link}",
    )
    campaign = Campaign(title="Launch", source_text="Hello")

    assert country.id.version == 4
    assert country.created_at.tzinfo is UTC
    assert campaign.status is CampaignStatus.DRAFT
    assert campaign.created_at.tzinfo is UTC
