from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.domain.catalogs import SCHEMA_VERSION, SEED_VERSION
from app.domain.city import (
    CITY_NAME,
    CITY_TIMEZONE,
    CONTROL_POINT,
    DISTRICTS,
    CityName,
    DistrictCode,
)
from app.domain.entities import Venue
from app.domain.errors import DomainError
from app.domain.rules import validate
from app.infrastructure.seed import SAMPLE_VENUES, sample_id
from app.main import create_app
from app.presentation.schemas import VenueCreate, VenuePatch

API = "/api/v1"


@pytest.fixture
def venue_fields():
    return {
        "name": "Test venue",
        "city": "Казань",
        "district_code": "VAH",
        "street": "площадь Свободы",
        "house": "2",
        "formatted_address": "Казань, площадь Свободы, 2",
        "latitude": 55.795518,
        "longitude": 49.124544,
        "capacity": 100,
    }


def test_city_contract_and_seed_identity():
    assert get_args(CityName) == (CITY_NAME,)
    assert set(get_args(DistrictCode)) == set(DISTRICTS)
    assert len(DISTRICTS) == 7
    assert {venue[1] for venue in SAMPLE_VENUES} == set(DISTRICTS)
    assert SAMPLE_VENUES[0][-2:] == (CONTROL_POINT["latitude"], CONTROL_POINT["longitude"])
    assert CITY_TIMEZONE == "Europe/Moscow"
    for resource, count in (
        ("artists", 14),
        ("venues", 10),
        ("series", 3),
        ("events", 36),
        ("reservations", 60),
    ):
        kazan_ids = {sample_id(resource, index) for index in range(count)}
        other_dataset_ids = {
            uuid5(NAMESPACE_URL, f"other-dataset/sample/{resource}/{index}")
            for index in range(count)
        }
        assert len(kazan_ids) == count
        assert kazan_ids.isdisjoint(other_dataset_ids)


@pytest.mark.parametrize("changes", [{"city": "Другой город"}, {"district_code": "UNKNOWN"}])
def test_domain_and_request_models_reject_another_city(venue_fields, changes):
    now = datetime.now(UTC)
    venue = Venue(id=uuid4(), created_at=now, updated_at=now, **venue_fields)
    validate(venue)
    with pytest.raises(DomainError) as error:
        validate(replace(venue, **changes))
    assert error.value.code in {"INVALID_CITY", "INVALID_DISTRICT"}
    for model, payload in ((VenueCreate, venue_fields | changes), (VenuePatch, changes)):
        with pytest.raises(ValidationError):
            model.model_validate(payload)


def test_published_openapi_matches_city_contract(venue_fields):
    document = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docs/openapi.yml").read_text(encoding="utf-8")
    )
    components = document["components"]
    assert document["info"]["title"] == "Kazan Events API"
    assert set(components["schemas"]["DistrictCode"]["enum"]) == set(DISTRICTS)
    for name, model in (("VenueCreate", VenueCreate), ("VenuePatch", VenuePatch)):
        declared = components["schemas"][name]["properties"]
        generated = model.model_json_schema()["properties"]
        assert declared["city"]["const"] == generated["city"]["const"] == CITY_NAME
        assert declared["district_code"]["enum"] == generated["district_code"]["enum"]
    query_schema = components["parameters"]["DistrictCode"]["schema"]["anyOf"][0]
    assert set(query_schema["enum"]) == set(DISTRICTS)
    examples = components["examples"]
    assert {row["code"]: row["name"] for row in examples["Districts"]["value"]["data"]} == DISTRICTS
    for name in ("Metadata", "DatasetSummary"):
        example = examples[name]["value"]
        assert example["schema_version"] == example["dataset"]["schema_version"] == SCHEMA_VERSION
        assert example["dataset"]["sample_seed_version"] == SEED_VERSION
        assert example["control_point"] == CONTROL_POINT
    example = examples["VenueCreate"]["value"]
    VenueCreate.model_validate(example)
    for field in ("city", "district_code", "street", "house", "latitude", "longitude"):
        assert example[field] == venue_fields[field]


@pytest.mark.integration
def test_all_kazan_districts_work_in_api_and_database(client, venue_fields):
    rows = client.get(f"{API}/meta/districts").json()["data"]
    assert {row["code"]: row["name"] for row in rows} == DISTRICTS
    for district in DISTRICTS:
        response = client.post(f"{API}/venues", json=venue_fields | {"district_code": district})
        assert response.status_code == 201, response.text
        venue_id = response.json()["id"]
        filtered = client.get(f"{API}/venues", params={"district_code": district}).json()
        assert [venue["id"] for venue in filtered["data"]] == [venue_id]
    for changes in ({"city": "Другой город"}, {"district_code": "UNKNOWN"}):
        assert client.post(f"{API}/venues", json=venue_fields | changes).status_code == 422
        assert client.patch(f"{API}/venues/{venue_id}", json=changes).status_code == 422
    assert client.get(f"{API}/venues?district_code=UNKNOWN").status_code == 400
    for statement in (
        "UPDATE venues SET city='Другой город'",
        "UPDATE venues SET district_code='UNKNOWN'",
    ):
        with pytest.raises(IntegrityError), client.app.state.database.engine.begin() as connection:
            connection.execute(text(statement))


@pytest.mark.integration
def test_kazan_sample_metadata_and_geosearch(client_factory):
    client = client_factory("sample")
    metadata = client.get(f"{API}/meta").json()
    assert metadata["schema_version"] == SCHEMA_VERSION
    assert metadata["dataset"]["sample_seed_version"] == SEED_VERSION
    assert metadata["control_point"] == CONTROL_POINT
    venues = client.get(f"{API}/venues?page_size=100").json()["data"]
    assert {venue["city"] for venue in venues} == {"Казань"}
    assert {venue["district_code"] for venue in venues} == set(DISTRICTS)
    nearby = client.get(f"{API}/events/nearby", params=CONTROL_POINT | {"radius_m": 1}).json()
    assert nearby["data"]
    assert all(event["venue_id"] == str(sample_id("venues", 0)) for event in nearby["data"])


@pytest.mark.integration
def test_incompatible_schema_is_rejected_without_changing_data(database_factory, settings_factory):
    application = create_app(settings_factory(database_factory(), retry_seconds=60))
    database = application.state.database
    with database.engine.begin() as connection:
        connection.execute(text("CREATE TABLE schema_migrations (version text PRIMARY KEY)"))
        connection.execute(text("INSERT INTO schema_migrations VALUES ('unsupported')"))
        connection.execute(text("CREATE TABLE original_data (value text)"))
        connection.execute(text("INSERT INTO original_data VALUES ('preserve me')"))
    try:
        with pytest.raises(DomainError) as error:
            database.initialize()
        assert error.value.code == "SCHEMA_MISMATCH"
        with TestClient(application) as client:
            assert client.get("/health/live").status_code == 200
            assert client.get("/health/ready").status_code == 503
            with database.engine.connect() as connection:
                assert (
                    connection.scalar(text("SELECT version FROM schema_migrations"))
                    == "unsupported"
                )
                assert connection.scalar(text("SELECT value FROM original_data")) == "preserve me"
                assert connection.scalar(text("SELECT to_regclass('public.venues')")) is None
    finally:
        database.engine.dispose()
