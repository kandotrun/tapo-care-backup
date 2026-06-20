"""Command-line interface for tapo-care-backup."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .api import TapoApiError, TapoCareClient, TapoCloudClient, login_from_env_or_prompt
from .config import DEFAULT_CONFIG_PATH, load_session, save_session
from .crypto import decrypt_tapo_payload
from .time_window import build_time_window
from .video_index import iter_download_candidates
from .monitor import safe_output_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tapo-care-backup", description="Back up Tapo Care cloud recordings for your own TP-Link/Tapo account.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Session cache path")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="Log in and cache a TP-Link cloud token")
    login.add_argument("--auth-mode", choices=["legacy", "signed"], default="legacy", help="legacy avoids mobile-app client signing; signed supports MFA if client keys are provided")
    login.add_argument("--strict-tls", action="store_true", help="Verify TLS certificates for cloud login when possible")

    devices = sub.add_parser("devices", help="List account cameras")
    devices.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    list_cmd = sub.add_parser("list", help="List Tapo Care cloud videos")
    _add_video_filters(list_cmd)
    list_cmd.add_argument("--json", action="store_true", help="Print raw JSON responses")

    download = sub.add_parser("download", help="Download Tapo Care cloud videos")
    _add_video_filters(download)
    download.add_argument("--path", type=Path, default=Path("backups"), help="Output directory")
    download.add_argument("--overwrite", action="store_true", help="Overwrite existing files")

    doctor = sub.add_parser("doctor", help="Probe Tapo Care API endpoint without credentials")
    doctor.add_argument("--region", default="aps1")

    return parser


def _add_video_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device-id", help="Only use a specific Tapo deviceId")
    parser.add_argument("--days", type=int, default=1, help="Number of previous local days to include, plus today")
    parser.add_argument("--timezone", default="Asia/Tokyo", help="Timezone used for date boundaries")
    parser.add_argument("--page-size", type=int, default=3000)


def _camera_devices(session_path: Path):
    session = load_session(session_path)
    cloud = TapoCloudClient()
    return [d for d in cloud.list_devices(session) if d.device_type == "SMART.IPCAMERA" or "CAMERA" in d.device_type.upper()]


def cmd_login(args: argparse.Namespace) -> int:
    session = login_from_env_or_prompt(auth_mode=args.auth_mode, verify_tls=args.strict_tls)
    save_session(session, args.config)
    print(f"Saved session for {session.email} ({session.region}) to {args.config}")
    return 0


def cmd_devices(args: argparse.Namespace) -> int:
    devices = _camera_devices(args.config)
    if args.json:
        print(json.dumps([d.__dict__ for d in devices], indent=2, ensure_ascii=False))
    else:
        for d in devices:
            print(f"{d.device_id}	{d.alias}	{d.model or ''}	{d.device_type}")
    return 0


def _selected_devices(config_path: Path, device_id: str | None):
    session = load_session(config_path)
    if device_id:
        return session, [(device_id, device_id)]
    devices = _camera_devices(config_path)
    return session, [(d.device_id, d.alias) for d in devices]


def cmd_list(args: argparse.Namespace) -> int:
    session, devices = _selected_devices(args.config, args.device_id)
    care = TapoCareClient(session)
    start, end = build_time_window(args.days, args.timezone)
    raw = {}
    for device_id, alias in devices:
        pages = list(care.iter_video_pages(device_id, start, end, page_size=args.page_size))
        raw[device_id] = pages
        if not args.json:
            total = pages[0].get("total", 0) if pages else 0
            print(f"{alias}: {total} videos across {len(pages)} page(s)")
            for payload in pages:
                for candidate in iter_download_candidates(payload, alias):
                    print(f"  {candidate.event_local_time}	{candidate.relative_path}	{candidate.url}")
    if args.json:
        print(json.dumps(raw, indent=2, ensure_ascii=False))
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    session, devices = _selected_devices(args.config, args.device_id)
    care = TapoCareClient(session)
    start, end = build_time_window(args.days, args.timezone)
    downloaded = 0
    skipped = 0
    for device_id, alias in devices:
        for payload in care.iter_video_pages(device_id, start, end, page_size=args.page_size):
            for candidate in iter_download_candidates(payload, alias):
                out_path = safe_output_path(args.path, candidate.relative_path)
                if out_path.exists() and not args.overwrite:
                    skipped += 1
                    print(f"skip existing {out_path}")
                    continue
                out_path.parent.mkdir(parents=True, exist_ok=True)
                content = care.download_bytes(candidate.url)
                out_path.write_bytes(decrypt_tapo_payload(content, candidate.key_b64))
                downloaded += 1
                print(f"downloaded {out_path}")
    print(f"done: downloaded={downloaded} skipped={skipped}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    import requests

    url = f"https://{args.region}-app-tapo-care.i.tplinknbu.com/v2/videos/list"
    response = requests.get(url, timeout=15, verify=False)
    print(f"{url} -> HTTP {response.status_code} {response.text[:160]}")
    return 0 if response.status_code in {401, 403} else 1


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "login":
            return cmd_login(args)
        if args.command == "devices":
            return cmd_devices(args)
        if args.command == "list":
            return cmd_list(args)
        if args.command == "download":
            return cmd_download(args)
        if args.command == "doctor":
            return cmd_doctor(args)
    except FileNotFoundError as exc:
        print(f"No saved session. Run `tapo-care-backup login` first. ({exc})", file=sys.stderr)
        return 2
    except TapoApiError as exc:
        print(f"Tapo API error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
