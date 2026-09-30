from datetime import UTC
from pathlib import Path

from sqlalchemy import inspect, text

from facebook_content_publisher.domain.enums import CampaignStatus
from facebook_content_publisher.domain.models import Campaign, CountryProfile
from facebook_content_publisher.infrastructure.database.engine import create_database
from facebook_content_publisher.infrastructure.database.migrations import upgrade_database
from facebook_content_publisher.infrastructure.database.repositories import RepositorySet
from facebook_content_publisher.infrastructure.database.seed import seed_development_data


def migrated_database(tmp_path: Path):
    path = tmp_path / "nested" / "test.db"
    upgrade_database(path)
    return create_database(path)


def test_migration_creates_all_milestone_two_tables(tmp_path: Path) -> None:
    database = migrated_database(tmp_path)
    tables = set(inspect(database.engine).get_table_names())

    assert {
        "country_profiles",
        "campaigns",
        "media_assets",
        "localized_contents",
        "publications",
        "comment_jobs",
        "activity_logs",
        "alembic_version",
    } <= tables


def test_country_repository_crud_and_utc_round_trip(tmp_path: Path) -> None:
    database = migrated_database(tmp_path)
    repository = RepositorySet(database.sessions).countries
    country = CountryProfile(
        code="TH",
        country_name="Thailand",
        language_code="th-TH",
        language_name="Thai",
        timezone="Asia/Bangkok",
        default_comment_template="Details: {link}",
    )

    repository.add(country)
    loaded = repository.get(country.id)
    assert loaded is not None
    assert loaded.created_at.tzinfo is UTC
    assert repository.get_by_code("th") == loaded

    loaded.country_name = "Kingdom of Thailand"
    repository.update(loaded)
    assert repository.get(country.id).country_name == "Kingdom of Thailand"  # type: ignore[union-attr]

    assert repository.delete(country.id)
    assert repository.get(country.id) is None
    assert not repository.delete(country.id)


def test_campaign_repository_round_trips_enum(tmp_path: Path) -> None:
    database = migrated_database(tmp_path)
    repository = RepositorySet(database.sessions).campaigns
    campaign = Campaign(title="Launch", source_text="Hello")

    repository.add(campaign)

    loaded = repository.get(campaign.id)
    assert loaded is not None
    assert loaded.status is CampaignStatus.DRAFT


def test_seed_is_idempotent(tmp_path: Path) -> None:
    database = migrated_database(tmp_path)

    assert seed_development_data(database.sessions) == 3
    assert seed_development_data(database.sessions) == 0
    countries = RepositorySet(database.sessions).countries.list()
    assert {country.code for country in countries} == {"TH", "ID", "BR"}

    with database.engine.connect() as connection:
        count = connection.scalar(text("SELECT COUNT(*) FROM country_profiles"))
    assert count == 3
