import hashlib

from tapo_care_backup.video_index import DownloadCandidate, iter_download_candidates


def suffix(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


def test_iter_download_candidates_handles_unencrypted_and_encrypted_videos():
    payload = {
        "index": [
            {
                "eventLocalTime": "2026-06-20 12:34:56",
                "video": [
                    {"uri": "https://example.test/plain.mp4", "encryptionMethod": "NONE"},
                    {
                        "uri": "https://example.test/encrypted.mp4",
                        "encryptionMethod": "AES-128-CBC",
                        "decryptionInfo": {"key": "ZmFrZS1rZXk="},
                    },
                    {"uri": "https://example.test/no-method.mp4"},
                ],
            }
        ]
    }

    candidates = list(iter_download_candidates(payload, device_alias="Front Door"))

    assert candidates == [
        DownloadCandidate("Front Door", "2026-06-20 12:34:56", "https://example.test/plain.mp4", None, f"Front_Door/2026-06-20/2026-06-20_12-34-56_0_{suffix('https://example.test/plain.mp4')}.ts"),
        DownloadCandidate("Front Door", "2026-06-20 12:34:56", "https://example.test/encrypted.mp4", "ZmFrZS1rZXk=", f"Front_Door/2026-06-20/2026-06-20_12-34-56_1_{suffix('https://example.test/encrypted.mp4')}.ts"),
        DownloadCandidate("Front Door", "2026-06-20 12:34:56", "https://example.test/no-method.mp4", None, f"Front_Door/2026-06-20/2026-06-20_12-34-56_2_{suffix('https://example.test/no-method.mp4')}.ts"),
    ]


def test_iter_download_candidates_skips_items_without_uri():
    payload = {"index": [{"eventLocalTime": "2026-06-20 12:34:56", "video": [{"duration": 3}]}]}

    assert list(iter_download_candidates(payload, device_alias="cam")) == []


def test_iter_download_candidates_extracts_event_types_from_tapo_metadata():
    payload = {
        "index": [
            {
                "eventLocalTime": "2026-06-20 12:34:56",
                "eventTypeList": ["MOTION", "PD"],
                "eventTypeInfos": [
                    {"eventTypeName": "PD", "eventTimestamp": 1781950000000},
                    {"eventTypeName": "MOTION", "eventTimestamp": 1781950000000},
                ],
                "video": [{"uri": "https://example.test/person.ts"}],
            }
        ]
    }

    candidate = next(iter_download_candidates(payload, device_alias="cam"))

    assert candidate.event_types == ("MOTION", "PD")
