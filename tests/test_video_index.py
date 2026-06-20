from tapo_care_backup.video_index import DownloadCandidate, iter_download_candidates


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
        DownloadCandidate("Front Door", "2026-06-20 12:34:56", "https://example.test/plain.mp4", None, "Front_Door/2026-06-20/2026-06-20_12-34-56_0.mp4"),
        DownloadCandidate("Front Door", "2026-06-20 12:34:56", "https://example.test/encrypted.mp4", "ZmFrZS1rZXk=", "Front_Door/2026-06-20/2026-06-20_12-34-56_1.mp4"),
        DownloadCandidate("Front Door", "2026-06-20 12:34:56", "https://example.test/no-method.mp4", None, "Front_Door/2026-06-20/2026-06-20_12-34-56_2.mp4"),
    ]


def test_iter_download_candidates_skips_items_without_uri():
    payload = {"index": [{"eventLocalTime": "2026-06-20 12:34:56", "video": [{"duration": 3}]}]}

    assert list(iter_download_candidates(payload, device_alias="cam")) == []
