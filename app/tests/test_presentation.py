import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.presentation.errors import install_error_handlers
from app.presentation.schemas import EventAnalytics, ReservationAnalytics


@pytest.mark.parametrize(
    ("model", "valid", "invalid"),
    [
        (EventAnalytics, "event_count,sold_tickets", "revenue_rub"),
        (ReservationAnalytics, "revenue_rub,sold_tickets", "event_count"),
    ],
)
def test_analytics_subclasses_keep_their_metric_contract(model, valid, invalid):
    class CustomAnalytics(model):
        pass

    assert CustomAnalytics(metrics=valid).metrics == valid
    for metrics in (invalid, "", valid + ","):
        with pytest.raises(ValidationError, match="Unknown metric"):
            CustomAnalytics(metrics=metrics)


def test_method_not_allowed_preserves_allow_header():
    application = FastAPI()
    install_error_handlers(application)

    @application.get("/resource")
    def read_resource():
        return {}

    with TestClient(application) as client:
        response = client.post("/resource")

    assert response.status_code == 405
    assert response.headers["allow"] == "GET"
    assert response.json()["error"]["code"] == "HTTP_ERROR"
