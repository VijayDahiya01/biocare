"""Unit tests for the ZepIris adapter against the VERIFIED Doc 7 wire format.

These pin the contract: multipart upload, `tenant` form field, camelCase
`requestId`, and search returning 200 + empty matches on a bad image.
"""
import base64

import httpx
import pytest
import respx

from app.adapters.zepiris import ZepIrisClient, ZepIrisError

BASE = "http://zepiris-test:8000"
PIXEL = base64.b64encode(b"\xff\xd8\xff\xd9fakejpeg").decode()  # stand-in image bytes


def client() -> ZepIrisClient:
    return ZepIrisClient(base_url=BASE, timeout=5)


@respx.mock
def test_insert_sends_multipart_with_tenant_and_parses_camelcase():
    route = respx.post(f"{BASE}/v1/faces/insert").mock(
        return_value=httpx.Response(200, json={
            "requestId": "a1b2c3d4",
            "imageQualityAssessment": {
                "passed": True,
                "nudity": {"is_safe": True, "probability": 0.02},
                "spoof": {"is_spoof": False, "probability": 0.05},
                "blur": {"is_sharp": True, "probability": 0.10},
            },
            "userOperationResult": {"operation": "INSERT", "status": "success"},
        })
    )
    res = client().insert(tenant="acme_corp", face_id="employee_001", image_b64=PIXEL)

    assert res.request_id == "a1b2c3d4"
    assert res.stored is True
    assert res.quality.passed is True
    # verify it was a multipart upload carrying id + tenant form fields + a file
    sent = route.calls.last.request
    assert sent.headers["content-type"].startswith("multipart/form-data")
    body = sent.content
    assert b'name="tenant"' in body and b"acme_corp" in body
    assert b'name="id"' in body and b"employee_001" in body
    assert b'name="file"' in body


@respx.mock
def test_search_returns_best_match():
    respx.post(f"{BASE}/v1/faces/search").mock(
        return_value=httpx.Response(200, json={
            "requestId": "d4e5f6a7",
            "imageQualityAssessment": {"passed": True},
            "searchResult": {"matches": [
                {"id": "employee_001", "score": 0.92},
                {"id": "employee_044", "score": 0.41},
            ]},
        })
    )
    res = client().search(tenant="acme_corp", image_b64=PIXEL, top_k=5)
    assert res.best.id == "employee_001"
    assert res.best.score == pytest.approx(0.92)
    assert len(res.matches) == 2


@respx.mock
def test_search_bad_image_is_200_with_empty_matches_not_error():
    # VERIFIED: ZepIris does NOT 422 on a bad search image — empty matches.
    respx.post(f"{BASE}/v1/faces/search").mock(
        return_value=httpx.Response(200, json={
            "requestId": "x", "imageQualityAssessment": {"passed": False},
            "searchResult": {"matches": []},
        })
    )
    res = client().search(tenant="acme_corp", image_b64=PIXEL)
    assert res.matches == []
    assert res.best is None
    assert res.quality.passed is False


@respx.mock
def test_insert_duplicate_raises_409():
    respx.post(f"{BASE}/v1/faces/insert").mock(return_value=httpx.Response(409))
    with pytest.raises(ZepIrisError) as ei:
        client().insert(tenant="t", face_id="dup", image_b64=PIXEL)
    assert ei.value.status_code == 409


@respx.mock
def test_insert_bad_quality_raises_422():
    respx.post(f"{BASE}/v1/faces/insert").mock(return_value=httpx.Response(422))
    with pytest.raises(ZepIrisError) as ei:
        client().insert(tenant="t", face_id="x", image_b64=PIXEL)
    assert ei.value.code == "IMAGE_QUALITY_FAILED"


@respx.mock
def test_delete_uses_query_param_and_reports_success():
    route = respx.delete(f"{BASE}/v1/faces/delete").mock(
        return_value=httpx.Response(200, json={
            "requestId": "z", "userOperationResult": {"operation": "DELETE", "status": "success"},
        })
    )
    assert client().delete("employee_001") is True
    assert route.calls.last.request.url.params["id"] == "employee_001"


def test_data_url_prefix_is_stripped():
    from app.adapters.zepiris.client import _decode_base64_image
    raw = _decode_base64_image(f"data:image/jpeg;base64,{PIXEL}")
    assert raw == base64.b64decode(PIXEL)


def test_invalid_base64_raises():
    from app.adapters.zepiris.client import _decode_base64_image
    with pytest.raises(ZepIrisError):
        _decode_base64_image("!!!not base64!!!")


@respx.mock
def test_readyz_true_only_on_ok_status():
    respx.get(f"{BASE}/readyz").mock(return_value=httpx.Response(200, json={"status": "ok"}))
    assert client().readyz() is True
    respx.get(f"{BASE}/readyz").mock(return_value=httpx.Response(503, json={"status": "loading"}))
    assert client().readyz() is False
