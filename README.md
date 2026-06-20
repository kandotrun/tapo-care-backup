# tapo-care-backup

Unofficial, personal CLI for backing up **your own** Tapo Care cloud recordings from a TP-Link/Tapo account.

This project was built as a safer, Kan-usable rewrite inspired by [`dimme/tapo-cli`](https://github.com/dimme/tapo-cli), without copying its unlicensed source. It targets the practical flow:

1. Log in with your TP-Link ID.
2. List Tapo camera devices.
3. Query Tapo Care cloud video clips.
4. Download MPEG-TS video streams and decrypt AES-128-CBC payloads when Tapo returns a decryption key.

> This is not affiliated with TP-Link or Tapo. Tapo Care cloud-video endpoints are private/mobile-app endpoints and may change without notice.

## What works

- `login` — cache a TP-Link cloud token locally at `~/.config/tapo-care-backup/session.json` with `0600` permissions.
- `devices` — list camera devices in the account.
- `list` — list Tapo Care cloud video clips for a time window.
- `download` — paginate through all clips in the selected window and download them into date/camera folders as `.ts` files.
- `doctor` — unauthenticated endpoint probe; a `401 token invalid` response means the regional Tapo Care endpoint is reachable.

## Important constraints

- Use the **owner TP-Link account**. Tapo shared accounts generally cannot access Tapo Care cloud recordings.
- Tapo Care stores event clips, not full 24/7 recordings. For continuous future recording, RTSP/ONVIF + NAS/NVR is usually more stable.
- Some Tapo accounts/regions/firmware may require newer signed mobile auth. This repo includes signing helpers, but does **not** ship mobile-app client keys in the public repo.
- The default region fallback is `aps1`, which is likely the useful default for Japan/APAC accounts. If login returns an `appServerUrl`, the region is auto-detected.

## Install / run

```bash
git clone https://github.com/kandotrun/tapo-care-backup.git
cd tapo-care-backup
uv run tapo-care-backup --help
```

## Usage

### 1. Log in

Interactive:

```bash
uv run tapo-care-backup login
```

Or with environment variables:

```bash
export TAPO_USERNAME='you@example.com'
export TAPO_PASSWORD='your-password'
uv run tapo-care-backup login
```

The token is saved to:

```text
~/.config/tapo-care-backup/session.json
```

### 2. Confirm the Tapo Care endpoint for Japan/APAC

```bash
uv run tapo-care-backup doctor --region aps1
```

Expected unauthenticated result:

```text
HTTP 401 {"code":15000,"message":"token invalid, expired or replaced"}
```

### 3. List cameras

```bash
uv run tapo-care-backup devices
```

### 4. List cloud clips

```bash
uv run tapo-care-backup list --days 7 --timezone Asia/Tokyo
```

### 5. Download cloud clips

```bash
uv run tapo-care-backup download --days 7 --timezone Asia/Tokyo --path ~/TapoBackups
```

Existing files are skipped by default. To re-download:

```bash
uv run tapo-care-backup download --days 7 --path ~/TapoBackups --overwrite
```

If device discovery is flaky but you know the camera `deviceId`:

```bash
uv run tapo-care-backup download --device-id 'YOUR_DEVICE_ID' --days 7 --path ~/TapoBackups
```

## Signed auth mode

Default login uses the older TP-Link cloud login flow because it does not require publishing Tapo mobile-app client keys.

If your account requires MFA or the legacy login path stops working, the CLI also has a signed-auth path. Signed auth intentionally requires you to provide the reverse-engineered Tapo mobile client material through environment variables instead of hardcoding it in this public repo:

```bash
export TAPO_CLIENT_ACCESS_KEY='...'
export TAPO_CLIENT_SECRET='...'
uv run tapo-care-backup login --auth-mode signed
```

Those values are **not TP-Link account credentials**, but this repo still avoids committing them because they are reverse-engineered app-client material and may be sensitive/unstable.

## Development

```bash
uv run pytest -q
uv build
```

The tests mock behavior and do not require a Tapo account.

## Security notes

- Never commit `session.json`, TP-Link passwords, tokens, or downloaded videos.
- Do not expose RTSP/ONVIF ports directly to the internet. Use VPN if remote access is needed.
- This tool is intended only for backing up recordings from accounts/devices you own or are explicitly authorized to administer.
