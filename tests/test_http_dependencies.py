import pytest

from app.services.http import DependencyCallError, fetch_dependency_json, request_json


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, payload):
        self.payload = payload

    def request(self, *args, **kwargs):
        return FakeResponse(self.payload)


def test_request_json_rejects_non_object_payload(monkeypatch):
    monkeypatch.setattr("app.services.http.get_http_client", lambda *args: FakeClient([]))

    with pytest.raises(ValueError, match="non-object JSON"):
        request_json("GET", "http://dependency.local/api")


def test_fetch_dependency_json_converts_bad_payload_to_dependency_error(monkeypatch):
    def bad_request_json(*args, **kwargs):
        raise ValueError("bad json")

    monkeypatch.setattr("app.services.http.dependency_urls", lambda service: ["http://dependency.local"])
    monkeypatch.setattr("app.services.http.request_json", bad_request_json)

    with pytest.raises(DependencyCallError) as exc:
        fetch_dependency_json("photon", "GET", "/api")

    assert exc.value.service == "photon"
    assert exc.value.detail == "ValueError"

