"""Normalize Tapo Care video-list responses into download candidates."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class DownloadCandidate:
    device_alias: str
    event_local_time: str
    url: str
    key_b64: str | None
    relative_path: str


def safe_name(value: str) -> str:
    cleaned = _SAFE_CHARS.sub("_", value.strip()).strip("_")
    return cleaned or "camera"


def _event_path(device_alias: str, event_local_time: str, index: int) -> str:
    date_part = event_local_time[:10] if len(event_local_time) >= 10 else "unknown-date"
    time_part = event_local_time.replace(":", "-").replace(" ", "_") or "unknown-time"
    return f"{safe_name(device_alias)}/{date_part}/{time_part}_{index}.ts"


def iter_download_candidates(payload: dict[str, Any], device_alias: str) -> Iterable[DownloadCandidate]:
    """Yield downloadable videos from a `/v1/videos` or `/v2/videos/list` response.

    `encryptionMethod: NONE` and missing `encryptionMethod` are treated as plain
    media. `AES-128-CBC` uses `decryptionInfo.key`.
    """
    for item in payload.get("index", []) or []:
        event_local_time = item.get("eventLocalTime") or item.get("createdLocalTime") or "unknown-time"
        videos = item.get("video") or []
        for idx, video in enumerate(videos):
            url = video.get("uri") or video.get("url")
            if not url:
                continue
            method = (video.get("encryptionMethod") or "NONE").upper()
            if method == "AES-128-CBC":
                key_b64 = (video.get("decryptionInfo") or {}).get("key")
                if not key_b64:
                    raise ValueError(f"Encrypted video at {event_local_time} is missing decryptionInfo.key")
            elif method in {"NONE", ""}:
                key_b64 = None
            else:
                raise ValueError(f"Unsupported Tapo Care encryption method: {method}")
            yield DownloadCandidate(device_alias, event_local_time, url, key_b64, _event_path(device_alias, event_local_time, idx))
