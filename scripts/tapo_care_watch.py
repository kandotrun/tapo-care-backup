#!/usr/bin/env python3
"""Cron entrypoint for incremental Tapo Care monitoring.

This script intentionally prints nothing when there are no new clips, so Hermes
cron stays quiet. When new clips are found it prints a Slack-ready message with
MEDIA: paths for a small number of attachments.
"""
from __future__ import annotations

import os

from tapo_care_backup.api import TapoApiError
from tapo_care_backup.monitor import format_slack_message, run_watch_once, settings_from_env


def main() -> int:
    try:
        result = run_watch_once()
        if result is None:
            return 0
        settings = settings_from_env()
        notify_bootstrap = os.environ.get("TAPO_WATCH_NOTIFY_BOOTSTRAP") == "1"
        message = format_slack_message(result, max_attachments=settings.max_attachments, notify_bootstrap=notify_bootstrap)
        if message:
            print(message)
        return 0
    except TapoApiError as exc:
        print(f"⚠️ Tapo Care監視エラー: {exc}")
        return 0
    except Exception as exc:
        print(f"⚠️ Tapo Care監視で予期しないエラーが出ました: {type(exc).__name__}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
