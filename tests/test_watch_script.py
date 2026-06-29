import importlib.util
from pathlib import Path

import requests


_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tapo_care_watch.py"


def _load_watch_script():
    spec = importlib.util.spec_from_file_location("tapo_care_watch_script", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_watch_script_stays_silent_for_transient_network_errors(monkeypatch, capsys):
    script = _load_watch_script()

    def raise_timeout():
        raise requests.exceptions.ConnectTimeout("temporary connect timeout")

    monkeypatch.setattr(script, "run_watch_once", raise_timeout)

    assert script.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
