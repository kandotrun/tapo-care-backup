"""Incremental Tapo Care monitoring helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Iterable, Mapping

from .api import TapoApiError, TapoCareClient, TapoCloudClient, TapoDevice
from .config import StoredSession, load_session, save_session
from .crypto import decrypt_tapo_payload
from .time_window import build_time_window
from .video_index import DownloadCandidate, iter_download_candidates

_URL_HASH_SUFFIX = re.compile(r"_[0-9a-f]{10}\.ts$")


@dataclass(frozen=True)
class WatchPaths:
    env_file: Path
    session_file: Path
    state_file: Path
    output_dir: Path


@dataclass(frozen=True)
class WatchSettings:
    days: int = 1
    timezone_name: str = "Asia/Tokyo"
    page_size: int = 500
    max_attachments: int = 3
    bootstrap_mode: str = "mark_seen"
    device_id: str | None = None


@dataclass(frozen=True)
class SavedClip:
    device_alias: str
    event_local_time: str
    path: Path
    clip_id: str


@dataclass(frozen=True)
class WatchResult:
    bootstrapped: bool
    checked_candidates: int
    saved: list[SavedClip]


def default_watch_paths() -> WatchPaths:
    config_dir = Path(os.environ.get("TAPO_CARE_BACKUP_CONFIG_DIR", Path.home() / ".config" / "tapo-care-backup"))
    state_dir = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "tapo-care-backup"
    return WatchPaths(
        env_file=Path(os.environ.get("TAPO_WATCH_ENV_FILE", config_dir / "monitor.env")).expanduser(),
        session_file=Path(os.environ.get("TAPO_WATCH_SESSION", config_dir / "session.json")).expanduser(),
        state_file=Path(os.environ.get("TAPO_WATCH_STATE", state_dir / "watch_state.json")).expanduser(),
        output_dir=Path(os.environ.get("TAPO_WATCH_OUTPUT_DIR", Path.home() / "TapoBackups")).expanduser(),
    )


def load_env_file(path: Path) -> dict[str, str]:
    """Load a small KEY=VALUE env file without requiring python-dotenv."""
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def apply_env_file(values: Mapping[str, str]) -> None:
    for key, value in values.items():
        if key.startswith(("TAPO_", "TAPO_WATCH_")):
            os.environ.setdefault(key, value)


def settings_from_env() -> WatchSettings:
    bootstrap_mode = os.environ.get("TAPO_WATCH_BOOTSTRAP", "mark_seen")
    if bootstrap_mode not in {"mark_seen", "download_existing"}:
        bootstrap_mode = "mark_seen"
    return WatchSettings(
        days=int(os.environ.get("TAPO_WATCH_DAYS", "1")),
        timezone_name=os.environ.get("TAPO_WATCH_TIMEZONE", "Asia/Tokyo"),
        page_size=int(os.environ.get("TAPO_WATCH_PAGE_SIZE", "500")),
        max_attachments=int(os.environ.get("TAPO_WATCH_MAX_ATTACHMENTS", "3")),
        bootstrap_mode=bootstrap_mode,
        device_id=os.environ.get("TAPO_WATCH_DEVICE_ID") or None,
    )


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "bootstrapped": False, "seen": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("version", 1)
    data.setdefault("bootstrapped", False)
    data.setdefault("seen", {})
    return data


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)


def stable_clip_id(device_id: str, candidate: DownloadCandidate) -> str:
    """Return a non-secret stable identifier for a clip.

    Tapo media URLs can be signed/temporary, so only use the generated path after
    removing its URL-hash suffix. The raw device ID and URL are never persisted.
    """
    stable_path = _URL_HASH_SUFFIX.sub(".ts", candidate.relative_path)
    material = "|".join([device_id, candidate.device_alias, candidate.event_local_time, stable_path])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _credentials_available() -> bool:
    return bool(os.environ.get("TAPO_USERNAME") and os.environ.get("TAPO_PASSWORD"))


def load_or_login_session(paths: WatchPaths) -> StoredSession | None:
    if paths.session_file.exists():
        return load_session(paths.session_file)
    if not _credentials_available():
        return None
    session = TapoCloudClient().login_legacy(os.environ["TAPO_USERNAME"], os.environ["TAPO_PASSWORD"])
    save_session(session, paths.session_file)
    return session


def _login_refresh(paths: WatchPaths) -> StoredSession:
    if not _credentials_available():
        raise TapoApiError("No saved session and TAPO_USERNAME/TAPO_PASSWORD are not configured")
    session = TapoCloudClient().login_legacy(os.environ["TAPO_USERNAME"], os.environ["TAPO_PASSWORD"])
    save_session(session, paths.session_file)
    return session


def list_camera_devices(session: StoredSession, paths: WatchPaths) -> list[TapoDevice]:
    cloud = TapoCloudClient()
    try:
        devices = cloud.list_devices(session)
    except TapoApiError:
        session = _login_refresh(paths)
        devices = cloud.list_devices(session)
    return [d for d in devices if d.device_type == "SMART.IPCAMERA" or "CAMERA" in d.device_type.upper()]


def iter_candidates_for_devices(session: StoredSession, devices: Iterable[TapoDevice], settings: WatchSettings):
    care = TapoCareClient(session)
    start, end = build_time_window(settings.days, settings.timezone_name)
    for device in devices:
        alias = device.alias or device.device_id
        for payload in care.iter_video_pages(device.device_id, start, end, page_size=settings.page_size):
            for candidate in iter_download_candidates(payload, alias):
                yield device.device_id, candidate


def safe_output_path(output_dir: Path, relative_path: str) -> Path:
    """Resolve a candidate path and ensure it stays inside output_dir."""
    base = output_dir.resolve()
    path = (base / relative_path).resolve()
    if not path.is_relative_to(base):
        raise TapoApiError("Unsafe Tapo Care output path rejected")
    return path


def run_watch_once(paths: WatchPaths | None = None, settings: WatchSettings | None = None) -> WatchResult | None:
    if paths is None:
        initial_paths = default_watch_paths()
        apply_env_file(load_env_file(initial_paths.env_file))
        paths = default_watch_paths()
    else:
        apply_env_file(load_env_file(paths.env_file))
    settings = settings or settings_from_env()

    session = load_or_login_session(paths)
    if session is None:
        # Cron-friendly: stay silent until credentials or a session token is configured.
        return None

    state = load_state(paths.state_file)
    devices = list_camera_devices(session, paths)
    if settings.device_id:
        devices = [d for d in devices if d.device_id == settings.device_id]

    try:
        candidates = list(iter_candidates_for_devices(session, devices, settings))
    except TapoApiError:
        session = _login_refresh(paths)
        candidates = list(iter_candidates_for_devices(session, devices, settings))
    seen: dict[str, dict] = state.setdefault("seen", {})
    now = datetime.now(timezone.utc).isoformat()

    if not state.get("bootstrapped") and settings.bootstrap_mode == "mark_seen":
        for device_id, candidate in candidates:
            clip_id = stable_clip_id(device_id, candidate)
            seen.setdefault(clip_id, {"first_seen_at": now, "event_local_time": candidate.event_local_time})
        state["bootstrapped"] = True
        save_state(paths.state_file, state)
        return WatchResult(bootstrapped=True, checked_candidates=len(candidates), saved=[])

    saved: list[SavedClip] = []
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    for device_id, candidate in candidates:
        clip_id = stable_clip_id(device_id, candidate)
        if clip_id in seen:
            continue
        out_path = safe_output_path(paths.output_dir, candidate.relative_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if not out_path.exists():
            content = TapoCareClient(session).download_bytes(candidate.url)
            out_path.write_bytes(decrypt_tapo_payload(content, candidate.key_b64))
        seen[clip_id] = {
            "first_seen_at": now,
            "event_local_time": candidate.event_local_time,
            "relative_path": candidate.relative_path,
            "size": out_path.stat().st_size if out_path.exists() else None,
        }
        saved.append(SavedClip(candidate.device_alias, candidate.event_local_time, out_path, clip_id))
    state["bootstrapped"] = True
    save_state(paths.state_file, state)
    return WatchResult(bootstrapped=False, checked_candidates=len(candidates), saved=saved)


def format_slack_message(result: WatchResult, max_attachments: int = 3, notify_bootstrap: bool = False) -> str:
    if result.bootstrapped:
        if not notify_bootstrap:
            return ""
        return f"📹 Tapo Care監視を開始しました。既存{result.checked_candidates}件は既読扱いにして、次回以降の新規録画だけ保存・共有します。"
    if not result.saved:
        return ""
    lines = [f"📹 Tapo Care新規録画: {len(result.saved)}件保存しました。"]
    for clip in result.saved[:max_attachments]:
        lines.append(f"- {clip.event_local_time} / {clip.device_alias} / {clip.path.name}")
        lines.append(f"MEDIA:{clip.path}")
    remaining = len(result.saved) - max_attachments
    if remaining > 0:
        lines.append(f"ほか{remaining}件はローカルに保存済みです。")
    return "\n".join(lines)
