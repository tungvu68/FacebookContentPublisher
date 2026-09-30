"""Idempotent development seed data."""

from sqlalchemy.orm import Session, sessionmaker

from facebook_content_publisher.domain.models import CountryProfile
from facebook_content_publisher.infrastructure.database.repositories import (
    SqlAlchemyCountryProfileRepository,
)

SEED_COUNTRIES = (
    {
        "code": "TH",
        "country_name": "Thailand",
        "language_code": "th-TH",
        "language_name": "Thai",
        "native_reader_label": "Thai",
        "timezone": "Asia/Bangkok",
        "default_link": "https://example.com/th",
        "default_comment_template": "ดูรายละเอียดเพิ่มเติม: {link}",
    },
    {
        "code": "ID",
        "country_name": "Indonesia",
        "language_code": "id-ID",
        "language_name": "Indonesian",
        "native_reader_label": "Indonesian",
        "timezone": "Asia/Jakarta",
        "default_link": "https://example.com/id",
        "default_comment_template": "Lihat detail selengkapnya: {link}",
    },
    {
        "code": "BR",
        "country_name": "Brazil",
        "language_code": "pt-BR",
        "language_name": "Brazilian Portuguese",
        "native_reader_label": "Brazilian Portuguese speaker",
        "timezone": "America/Sao_Paulo",
        "default_link": "https://example.com/br",
        "default_comment_template": "Veja mais detalhes: {link}",
    },
)


def seed_development_data(sessions: sessionmaker[Session]) -> int:
    """Insert missing development countries and return the insertion count."""

    repository = SqlAlchemyCountryProfileRepository(sessions)
    inserted = 0
    for values in SEED_COUNTRIES:
        if repository.get_by_code(values["code"]) is None:
            repository.add(CountryProfile(**values))
            inserted += 1
    return inserted
