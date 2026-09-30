import pytest
from pydantic import ValidationError

from facebook_content_publisher.application.dto import CampaignCreate, CountryProfileCreate


def valid_country() -> dict[str, object]:
    return {
        "code": "th",
        "country_name": "Thailand",
        "language_code": "th-TH",
        "language_name": "Thai",
        "timezone": "Asia/Bangkok",
        "default_comment_template": "Details: {link}",
    }


def test_country_schema_normalizes_code_and_validates_timezone() -> None:
    country = CountryProfileCreate.model_validate(valid_country())
    assert country.code == "TH"

    values = valid_country()
    values["timezone"] = "Invalid/Timezone"
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        CountryProfileCreate.model_validate(values)


def test_campaign_requires_non_empty_source() -> None:
    with pytest.raises(ValidationError):
        CampaignCreate(title="Example", source_text="")
