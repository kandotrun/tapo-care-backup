import requests

from tapo_care_backup.api import TapoCareClient, TapoCloudClient
from tapo_care_backup.config import StoredSession
import tapo_care_backup.api as api


def test_legacy_login_extracts_token_and_region(requests_mock):
    requests_mock.post(
        "https://eu-wap.tplinkcloud.com/",
        json={
            "error_code": 0,
            "result": {
                "token": "tok_123",
                "appServerUrl": "https://aps1-app-server.iot.i.tplinknbu.com",
            },
        },
    )

    session = TapoCloudClient().login_legacy("kan@example.com", "pw", terminal_uuid="uuid")

    assert session == StoredSession(
        token="tok_123",
        email="kan@example.com",
        region="aps1",
        app_server_url="https://aps1-app-server.iot.i.tplinknbu.com",
    )


def test_tapo_care_list_videos_uses_regional_v2_endpoint_and_auth_header(requests_mock):
    session = StoredSession(token="tok_123", email="kan@example.com", region="aps1")
    matcher = requests_mock.get(
        "https://aps1-app-tapo-care.i.tplinknbu.com/v2/videos/list",
        json={"total": 0, "index": []},
    )

    payload = TapoCareClient(session).list_videos("device-1", "2026-06-20 00:00:00", "2026-06-21 00:00:00")

    assert payload == {"total": 0, "index": []}
    assert matcher.last_request.headers["Authorization"] == "ut|tok_123"
    assert matcher.last_request.qs["deviceid"] == ["device-1"]


def test_tapo_care_iter_video_pages_until_total_is_seen(requests_mock):
    session = StoredSession(token="tok_123", email="kan@example.com", region="aps1")
    matcher = requests_mock.get(
        "https://aps1-app-tapo-care.i.tplinknbu.com/v2/videos/list",
        [
            {"json": {"total": 3, "index": [{"eventLocalTime": "a"}, {"eventLocalTime": "b"}]}},
            {"json": {"total": 3, "index": [{"eventLocalTime": "c"}]}},
        ],
    )

    pages = list(TapoCareClient(session).iter_video_pages("device-1", page_size=2))

    assert [len(page["index"]) for page in pages] == [2, 1]
    assert [request.qs["page"] for request in matcher.request_history] == [["0"], ["1"]]


def test_tapo_care_list_videos_retries_transient_timeout(requests_mock, monkeypatch):
    monkeypatch.setattr(api.time, "sleep", lambda seconds: None)
    session = StoredSession(token="tok_123", email="kan@example.com", region="aps1")
    matcher = requests_mock.get(
        "https://aps1-app-tapo-care.i.tplinknbu.com/v2/videos/list",
        [
            {"exc": requests.exceptions.ConnectTimeout("temporary connect timeout")},
            {"json": {"total": 0, "index": []}},
        ],
    )

    payload = TapoCareClient(session).list_videos("device-1")

    assert payload == {"total": 0, "index": []}
    assert matcher.call_count == 2


def test_tapo_care_download_bytes_retries_transient_timeout(requests_mock, monkeypatch):
    monkeypatch.setattr(api.time, "sleep", lambda seconds: None)
    session = StoredSession(token="tok_123", email="kan@example.com", region="aps1")
    matcher = requests_mock.get(
        "https://media.example.test/clip.ts",
        [
            {"exc": requests.exceptions.ReadTimeout("temporary read timeout")},
            {"content": b"video-bytes"},
        ],
    )

    content = TapoCareClient(session).download_bytes("https://media.example.test/clip.ts")

    assert content == b"video-bytes"
    assert matcher.call_count == 2


def test_list_devices_retries_transient_timeout(requests_mock, monkeypatch):
    monkeypatch.setattr(api.time, "sleep", lambda seconds: None)
    session = StoredSession(token="tok_123", email="kan@example.com", region="aps1")
    matcher = requests_mock.post(
        "https://eu-wap.tplinkcloud.com/",
        [
            {"exc": requests.exceptions.ConnectTimeout("temporary connect timeout")},
            {"json": {"error_code": 0, "result": {"deviceList": []}}},
        ],
    )

    assert TapoCloudClient().list_devices(session) == []
    assert matcher.call_count == 2


def test_list_devices_falls_back_to_signed_endpoint_when_legacy_token_is_rejected(requests_mock, monkeypatch):
    monkeypatch.setenv("TAPO_CLIENT_ACCESS_KEY", "access-key")
    monkeypatch.setenv("TAPO_CLIENT_SECRET", "client-secret")
    session = StoredSession(
        token="signed-token",
        email="kan@example.com",
        region="aps1",
        app_server_url="https://aps1-app-server.iot.i.tplinknbu.com",
    )
    requests_mock.post("https://eu-wap.tplinkcloud.com/", json={"error_code": -1, "msg": "Token incorrect"})
    signed = requests_mock.post(
        "https://aps1-app-server.iot.i.tplinknbu.com/api/v2/common/getDeviceListByPage",
        json={
            "error_code": 0,
            "result": {
                "deviceList": [
                    {
                        "deviceId": "camera-1",
                        "alias": "Front Door",
                        "deviceType": "SMART.IPCAMERA",
                        "deviceModel": "C200",
                        "appServerUrl": "https://aps1-app-server.iot.i.tplinknbu.com",
                    }
                ]
            },
        },
    )

    devices = TapoCloudClient().list_devices(session)

    assert devices[0].device_id == "camera-1"
    assert devices[0].alias == "Front Door"
    assert signed.last_request.qs["token"] == ["signed-token"]
    assert signed.last_request.headers["Content-Md5"]
    assert signed.last_request.headers["X-Authorization"].startswith("Timestamp=")
