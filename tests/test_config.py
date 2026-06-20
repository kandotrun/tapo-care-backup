import json
import stat

from tapo_care_backup.config import StoredSession, load_session, save_session


def test_save_session_writes_user_only_permissions(tmp_path):
    path = tmp_path / "config.json"
    session = StoredSession(token="token", email="kan@example.com", region="aps1", app_server_url="https://aps1-app-server.iot.i.tplinknbu.com")

    save_session(session, path)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text())["token"] == "token"
    assert load_session(path) == session
