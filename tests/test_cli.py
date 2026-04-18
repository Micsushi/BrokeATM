from __future__ import annotations

from urllib.error import URLError

import app.cli as cli


def test_program_name_defaults_to_atm(monkeypatch) -> None:
    monkeypatch.delattr(cli.sys, "frozen", raising=False)
    monkeypatch.setattr(cli.sys, "executable", "/tmp/python", raising=False)

    assert cli._program_name() == "atm"


def test_program_name_uses_executable_name_when_frozen(monkeypatch) -> None:
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "executable", r"C:\Apps\BrokeATM.exe", raising=False)

    assert cli._program_name() == "BrokeATM"


def test_reload_is_disabled_for_frozen_builds(monkeypatch) -> None:
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)

    assert cli._reload_enabled(True) is False
    assert cli._reload_enabled(False) is False


def test_reload_stays_enabled_for_regular_runs(monkeypatch) -> None:
    monkeypatch.delattr(cli.sys, "frozen", raising=False)

    assert cli._reload_enabled(True) is True
    assert cli._reload_enabled(False) is False


def test_browser_host_uses_localhost_for_bind_all_addresses() -> None:
    assert cli._browser_host("0.0.0.0") == "127.0.0.1"
    assert cli._browser_host("::") == "127.0.0.1"
    assert cli._browser_host("") == "127.0.0.1"


def test_browser_host_keeps_specific_host() -> None:
    assert cli._browser_host("127.0.0.1") == "127.0.0.1"
    assert cli._browser_host("localhost") == "localhost"


def test_wait_for_app_returns_true_when_brokeatm_marker_found(monkeypatch) -> None:
    class _Response:
        status = 200

        def read(self, _size: int = -1) -> bytes:
            return b"<title>Dashboard | BrokeATM</title>"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(cli, "urlopen", lambda url, timeout=1.0: _Response())

    assert cli._wait_for_app("http://127.0.0.1:8000") is True


def test_wait_for_app_returns_false_when_server_never_matches(monkeypatch) -> None:
    def _raise_url_error(url, timeout=1.0):
        raise URLError("down")

    monkeypatch.setattr(cli, "urlopen", _raise_url_error)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    assert cli._wait_for_app("http://127.0.0.1:8000", timeout=0.01) is False


def test_uvicorn_target_uses_import_string_when_reload_is_on() -> None:
    assert cli._uvicorn_app_target(True) == "app.main:app"
