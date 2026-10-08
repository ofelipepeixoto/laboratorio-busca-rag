"""Regression tests for local candidate patches. Synthetic inputs; no network."""
import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request, ClientDisconnect

from mineru.parser import api_server as api
from mineru.doclib.core.db import DatabaseManager
from mineru.doclib.telemetry import TelemetryService, TelemetryStore
from mineru.doclib.telemetry import service as telemetry_module


def request_data(size=3):
    return dict(filename="fixture.pdf", bytes=size, mime_type="application/pdf")


@pytest.mark.parametrize("size", [True, "3", 3.0, float("nan"), float("inf"), 209715201])
def test_reject_invalid_or_over_limit_upload_size(size):
    with pytest.raises(ValidationError):
        api.CreateUploadRequest(**request_data(size))


def test_advertised_maximum_is_accepted_as_metadata():
    assert api.CreateUploadRequest(**request_data(209715200)).bytes == 209715200


@pytest.mark.parametrize("key", ["", "   ", "\n", " key", "key "])
def test_blank_or_surrounding_whitespace_api_key_fails_closed(tmp_path, key):
    with pytest.raises(ValueError, match="api_key"):
        api.create_app(tier="flash", upload_dir=str(tmp_path), api_key=key)


def test_valid_auth_and_upload_roundtrip(tmp_path):
    with TestClient(api.create_app(tier="flash", upload_dir=str(tmp_path), api_key="fixture-key")) as client:
        assert client.post("/v1/uploads", json=request_data()).status_code == 401
        client.headers["Authorization"] = "Bearer fixture-key"
        upload = client.post("/v1/uploads", json=request_data()).json()
        assert client.put(f"/v1/uploads/{upload['id']}/content", content=b"abc", headers={"content-type":"application/octet-stream"}).status_code == 200
        completed = client.post(f"/v1/uploads/{upload['id']}/complete", json={})
        assert completed.status_code == 200
        assert completed.json()["file"]["bytes"] == 3


def run_stream(tmp_path, messages, *, expected=3, headers=(), before_receive=None):
    store = api.FileStore(tmp_path)
    upload = store.create_upload(api.CreateUploadRequest(**request_data(expected)))
    calls = []
    async def receive():
        if before_receive:
            before_receive(len(calls), upload)
        message = messages[len(calls)]
        calls.append(message)
        return message
    request = Request({"type":"http", "method":"PUT", "path":"/fixture", "headers":list(headers)}, receive=receive)
    return store, upload, calls, api.upload_content(request=request, upload_id=upload.id, store=store)


def message(data, more=False):
    return {"type":"http.request", "body":data, "more_body":more}


def assert_clean(store):
    assert list((store._blobs / "_uploads").glob("*")) == []


def test_chunked_upload_accepts_exact_length(tmp_path):
    store, upload, calls, coro = run_stream(tmp_path, [message(b"a", True), message(b"bc")])
    assert asyncio.run(coro).status_code == 200
    assert store.complete_upload(upload.id, None).file.bytes == 3


def test_chunked_upload_stops_at_limit_and_cleans_temporary_file(tmp_path):
    store, _, calls, coro = run_stream(tmp_path, [message(b"ab", True), message(b"cd", True), message(b"never read")])
    with pytest.raises(api.ApiServerError) as error:
        asyncio.run(coro)
    assert error.value.status_code == 413
    assert len(calls) == 2
    assert_clean(store)


def test_content_length_rejected_before_read(tmp_path):
    store, _, calls, coro = run_stream(tmp_path, [message(b"abcd")], headers=[(b"content-length", b"4")])
    with pytest.raises(api.ApiServerError) as error:
        asyncio.run(coro)
    assert error.value.status_code == 413
    assert calls == []


def test_false_content_length_still_enforces_actual_bytes(tmp_path):
    store, _, _, coro = run_stream(tmp_path, [message(b"abcd")], headers=[(b"content-length", b"3")])
    with pytest.raises(api.ApiServerError):
        asyncio.run(coro)
    assert_clean(store)


def test_short_body_does_not_publish_partial_upload(tmp_path):
    store, _, _, coro = run_stream(tmp_path, [message(b"ab")])
    with pytest.raises(api.ApiServerError):
        asyncio.run(coro)
    assert_clean(store)


def test_disconnect_cleans_partial_upload(tmp_path):
    store, _, _, coro = run_stream(tmp_path, [message(b"a", True), {"type":"http.disconnect"}])
    with pytest.raises(ClientDisconnect):
        asyncio.run(coro)
    assert_clean(store)


def test_expiry_during_stream_does_not_publish_upload(tmp_path, monkeypatch):
    def expire(index, upload):
        if index == 1:
            monkeypatch.setattr(api.time, "time", lambda: upload.expires_at + 1)
    store, _, _, coro = run_stream(tmp_path, [message(b"a", True), message(b"bc")], before_receive=expire)
    with pytest.raises(api.ApiServerError) as error:
        asyncio.run(coro)
    assert error.value.status_code == 409
    assert_clean(store)


@pytest.mark.parametrize("state,expected", [("unset",0),("disabled",0),("invalid",0),("enabled",1)])
def test_telemetry_requires_explicit_enabled_state(tmp_path, monkeypatch, state, expected):
    sent=[]
    async def send(payload):
        sent.append(payload)
        return "success"
    monkeypatch.setattr(telemetry_module,"send_payload",send)
    async def scenario():
        db=DatabaseManager(str(tmp_path/'telemetry.db'))
        await db.initialize()
        service=TelemetryService(TelemetryStore(db))
        await service.initialize()
        await service.record_count('search.request.count',timestamp_ms=1700000000000)
        await service.store.set_state('consent_state',state)
        await service.flush_once()
        assert len(sent)==expected
        await db.close()
    asyncio.run(scenario())


def test_consent_revoked_during_preparation_stops_send(tmp_path, monkeypatch):
    async def scenario():
        db=DatabaseManager(str(tmp_path/'telemetry.db'))
        await db.initialize()
        service=TelemetryService(TelemetryStore(db))
        await service.initialize()
        await service.store.set_consent_state('enabled')
        await service.record_count('search.request.count',timestamp_ms=1700000000000)
        original=service.store.list_aggregates
        async def revoke(*args):
            rows=await original(*args)
            await service.store.set_consent_state('disabled')
            return rows
        async def forbidden(payload):
            pytest.fail('Telemetry send after consent was revoked')
        monkeypatch.setattr(service.store,'list_aggregates',revoke)
        monkeypatch.setattr(telemetry_module,'send_payload',forbidden)
        await service.flush_once()
        await db.close()
    asyncio.run(scenario())
