from tapo_care_backup.time_window import build_time_window


def test_build_time_window_uses_local_midnight_in_requested_timezone():
    start, end = build_time_window(days=1, timezone_name="Asia/Tokyo", now_iso="2026-06-20T15:30:00+09:00")

    assert start == "2026-06-19 00:00:00"
    assert end == "2026-06-21 00:00:00"
