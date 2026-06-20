# Agent instructions

This repository is a small, user-owned CLI for backing up the owner's own Tapo Care cloud recordings.

Rules for future agents:

- Do not commit TP-Link IDs, passwords, tokens, downloaded videos, or local config files.
- Keep all network calls behind explicit CLI commands; tests must mock HTTP.
- Prefer owner-account workflows only. Shared Tapo accounts generally cannot access Tapo Care cloud recordings.
- Preserve compatibility with Python 3.11+ and `uv`.
- Follow TDD for behavior changes: add a failing test, implement the smallest fix, then run the full test suite.
- This is unofficial and can break if TP-Link changes private endpoints; keep errors clear and actionable.
