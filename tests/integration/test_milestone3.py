from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from facebook_content_publisher.application.dto import CountryProfileCreate
from facebook_content_publisher.application.dto.schemas import (
    CampaignDraftInput,
    CampaignTargetInput,
    MediaInput,
)
from facebook_content_publisher.application.services import CampaignService, CountryService
from facebook_content_publisher.domain.enums import CampaignStatus
from facebook_content_publisher.domain.exceptions import DuplicateEntityError
from facebook_content_publisher.domain.models import Campaign, CampaignTarget
from facebook_content_publisher.infrastructure.database.campaign_store import (
    SqlAlchemyCampaignStore,
)
from facebook_content_publisher.infrastructure.database.engine import create_database
from facebook_content_publisher.infrastructure.database.migrations import upgrade_database
from facebook_content_publisher.infrastructure.database.orm import Base
from facebook_content_publisher.infrastructure.database.repositories import RepositorySet
from facebook_content_publisher.infrastructure.database.seed import seed_development_data


def services(tmp_path: Path):
    database = create_database(tmp_path / "app.db")
    upgrade_database(database.path)
    repositories = RepositorySet(database.sessions)
    return (
        database,
        CountryService(repositories.countries),
        CampaignService(SqlAlchemyCampaignStore(database.sessions)),
    )


def country_input(code: str = "TH") -> CountryProfileCreate:
    return CountryProfileCreate(
        code=code,
        country_name="Thailand",
        language_code="th-TH",
        language_name="Thai",
        timezone="Asia/Bangkok",
        default_comment_template="Details: {link}",
    )


def test_country_crud_and_duplicate_code(tmp_path: Path) -> None:
    _, countries, _ = services(tmp_path)
    country = countries.create(country_input())
    with pytest.raises(DuplicateEntityError):
        countries.create(country_input("th"))
    changed = country_input()
    changed.country_name = "Kingdom of Thailand"
    assert countries.update(country.id, changed).country_name == "Kingdom of Thailand"
    assert not countries.set_enabled(country.id, False).enabled
    countries.delete(country.id)
    assert countries.list() == []


def test_campaign_create_update_duplicate_archive_and_delete(tmp_path: Path) -> None:
    _, countries, campaigns = services(tmp_path)
    thailand = countries.create(country_input())
    indonesia = countries.create(
        CountryProfileCreate(
            code="ID",
            country_name="Indonesia",
            language_code="id-ID",
            language_name="Indonesian",
            timezone="Asia/Jakarta",
            default_comment_template="Details: {link}",
        )
    )
    media_path = tmp_path / "photo.png"
    media_path.write_bytes(b"png")
    draft = CampaignDraftInput(
        title="Launch",
        source_text="Hello",
        targets=[
            CampaignTargetInput(country_profile_id=thailand.id),
            CampaignTargetInput(
                country_profile_id=indonesia.id, link_override="https://example.com/id"
            ),
        ],
        media=[MediaInput(path=media_path)],
    )
    saved = campaigns.save_draft(draft)
    assert len(saved.targets) == 2
    assert len(saved.media) == 1
    assert campaigns.get(saved.campaign.id).campaign.title == "Launch"

    draft.title = "Updated"
    assert campaigns.save_draft(draft, saved.campaign.id).campaign.title == "Updated"
    duplicate = campaigns.duplicate(saved.campaign.id)
    assert duplicate.campaign.id != saved.campaign.id
    assert duplicate.campaign.status is CampaignStatus.DRAFT
    assert duplicate.campaign.title.endswith("(Copy)")
    assert len(duplicate.targets) == 2

    assert campaigns.archive(saved.campaign.id).campaign.status is CampaignStatus.ARCHIVED
    with pytest.raises(ValueError, match="safe draft"):
        campaigns.delete_draft(saved.campaign.id)
    campaigns.delete_draft(duplicate.campaign.id)


def test_campaign_target_unique_and_country_restrict(tmp_path: Path) -> None:
    database, countries, _ = services(tmp_path)
    country = countries.create(country_input())
    repositories = RepositorySet(database.sessions)
    campaign = repositories.campaigns.add(Campaign("Title", "Text"))
    target = CampaignTarget(campaign.id, country.id)
    repositories.campaign_targets.add(target)
    with pytest.raises(IntegrityError):
        repositories.campaign_targets.add(CampaignTarget(campaign.id, country.id))
    with pytest.raises(IntegrityError):
        countries.delete(country.id)


def test_upgrade_to_head_and_seed_remain_idempotent(tmp_path: Path) -> None:
    database = create_database(tmp_path / "upgrade.db")
    Base.metadata.create_all(database.engine)
    with database.engine.begin() as connection:
        connection.execute(text("DROP TABLE campaign_targets"))
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('0001')"))
    upgrade_database(database.path)
    assert "campaign_targets" in inspect(database.engine).get_table_names()
    assert seed_development_data(database.sessions) == 3
    assert seed_development_data(database.sessions) == 0
