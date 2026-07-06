# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ``potos.base.potos_openbao`` argv/parse helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_MODULE_PATH = Path(__file__).resolve().parents[4] / "plugins" / "modules" / "potos_openbao.py"
_spec = importlib.util.spec_from_file_location("potos_openbao_under_test", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_login_argv_with_role() -> None:
    assert mod.build_login_argv("bao", "oidc", "oidc", {"role": "potos"}) == [
        "bao",
        "login",
        "-format=json",
        "-method=oidc",
        "-path=oidc",
        "role=potos",
    ]


def test_login_argv_without_options() -> None:
    argv = mod.build_login_argv("vault", "oidc", "mymount", None)
    assert argv == ["vault", "login", "-format=json", "-method=oidc", "-path=mymount"]


def test_login_argv_appends_options_as_key_value_after_flags() -> None:
    argv = mod.build_login_argv(
        "bao",
        "oidc",
        "oidc",
        {"role": "device", "callbackmode": "device", "listenaddress": "127.0.0.1"},
    )
    assert argv == [
        "bao",
        "login",
        "-format=json",
        "-method=oidc",
        "-path=oidc",
        "role=device",
        "callbackmode=device",
        "listenaddress=127.0.0.1",
    ]


def test_login_options_device_flow_order_and_mapping() -> None:
    # Mirrors: bao login -method=oidc callbackhost=localhost
    #          listenaddress=127.0.0.1 role=device callbackmode=device
    opts = mod.build_login_options(
        role="device",
        callback_mode="device",
        callback_host="localhost",
        listen_address="127.0.0.1",
        extra=None,
    )
    assert opts == {
        "role": "device",
        "callbackmode": "device",
        "callbackhost": "localhost",
        "listenaddress": "127.0.0.1",
    }


def test_login_options_omits_unset_and_stringifies_extra() -> None:
    opts = mod.build_login_options(
        role=None,
        callback_mode=None,
        callback_host=None,
        listen_address=None,
        extra={"callbackport": 8250},
    )
    assert opts == {"callbackport": "8250"}


def test_login_options_extra_overrides_dedicated() -> None:
    opts = mod.build_login_options(
        role="device",
        callback_mode="device",
        callback_host=None,
        listen_address=None,
        extra={"callbackmode": "direct"},
    )
    assert opts["callbackmode"] == "direct"


def test_kv_get_argv() -> None:
    assert mod.build_kv_get_argv("bao", "kv/potos/specs") == [
        "bao",
        "kv",
        "get",
        "-format=json",
        "kv/potos/specs",
    ]


def test_kv_put_argv_reads_from_file() -> None:
    assert mod.build_kv_put_argv("bao", "kv/potos/specs", "/tmp/x.json") == [
        "bao",
        "kv",
        "put",
        "kv/potos/specs",
        "@/tmp/x.json",
    ]


def test_parse_login_token() -> None:
    out = '{"auth": {"client_token": "s.abc123"}}'
    assert mod.parse_login_token(out) == "s.abc123"


def test_parse_login_token_tolerates_leading_noise() -> None:
    out = 'Success! You are now authenticated.\n{"auth": {"client_token": "s.abc123"}}'
    assert mod.parse_login_token(out) == "s.abc123"


def test_extract_verification_url_from_device_prompt() -> None:
    text = (
        "Complete the login via your OIDC provider. Launching browser to:\n\n"
        "    https://login.example.com/realms/potos/device?user_code=VISH-KVVU\n"
    )
    assert (
        mod.extract_verification_url(text)
        == "https://login.example.com/realms/potos/device?user_code=VISH-KVVU"
    )


def test_extract_verification_url_none() -> None:
    assert mod.extract_verification_url("Waiting for OIDC authentication...") is None


def test_extract_user_code_from_url() -> None:
    assert mod.extract_user_code("https://x/device?user_code=VISH-KVVU") == "VISH-KVVU"


def test_extract_user_code_from_label() -> None:
    assert mod.extract_user_code("Enter code -> User Code: ABCD-1234") == "ABCD-1234"


def test_extract_user_code_none() -> None:
    assert mod.extract_user_code("no code present here") is None


def test_graphical_env_points_at_wayland_socket(tmp_path, monkeypatch) -> None:
    import socket as _socket

    runtime = tmp_path / "run" / "user" / "1000"
    runtime.mkdir(parents=True)
    (runtime / "wayland-0.lock").write_text("")
    sock_path = runtime / "wayland-0"
    srv = _socket.socket(_socket.AF_UNIX)
    srv.bind(str(sock_path))
    try:
        monkeypatch.setattr(
            mod.glob, "glob", lambda pattern: [str(runtime / "wayland-0.lock"), str(sock_path)]
        )
        env = mod.graphical_env({"XDG_RUNTIME_DIR": "/run/user/0", "PATH": "/bin"})
    finally:
        srv.close()
    assert env["XDG_RUNTIME_DIR"] == str(runtime)
    assert env["WAYLAND_DISPLAY"] == "wayland-0"
    assert env["PATH"] == "/bin"


def test_graphical_env_no_socket_leaves_env_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(mod.glob, "glob", lambda pattern: [])
    env = mod.graphical_env({"XDG_RUNTIME_DIR": "/run/user/0"})
    assert env == {"XDG_RUNTIME_DIR": "/run/user/0"}


def test_session_user_resolves_uid_from_runtime_dir(monkeypatch) -> None:
    fake = type("PW", (), {"pw_uid": 1000, "pw_name": "alice", "pw_dir": "/home/alice"})
    monkeypatch.setattr(mod.pwd, "getpwuid", lambda uid: fake if uid == 1000 else None)
    assert mod.session_user({"XDG_RUNTIME_DIR": "/run/user/1000"}) == (
        1000,
        "alice",
        "/home/alice",
    )


def test_session_user_none_when_no_runtime_dir() -> None:
    assert mod.session_user({}) is None


def test_build_browser_argv_drops_to_user_as_root(monkeypatch) -> None:
    fake = type("PW", (), {"pw_uid": 1000, "pw_name": "alice", "pw_dir": "/home/alice"})
    monkeypatch.setattr(mod.pwd, "getpwuid", lambda uid: fake)
    monkeypatch.setattr(mod.os, "geteuid", lambda: 0)
    argv = mod.build_browser_argv(
        "https://idp/device?user_code=X",
        {"XDG_RUNTIME_DIR": "/run/user/1000", "DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0"},
    )
    assert argv[:5] == ["runuser", "-u", "alice", "--", "env"]
    assert "HOME=/home/alice" in argv
    assert "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus" in argv
    assert "DISPLAY=:0" in argv
    assert "WAYLAND_DISPLAY=wayland-0" in argv
    assert argv[-2:] == ["xdg-open", "https://idp/device?user_code=X"]


def test_build_browser_argv_plain_when_not_root(monkeypatch) -> None:
    monkeypatch.setattr(mod.os, "geteuid", lambda: 1000)
    argv = mod.build_browser_argv("https://idp/x", {"XDG_RUNTIME_DIR": "/run/user/1000"})
    assert argv == ["xdg-open", "https://idp/x"]


def test_parse_kv_get_returns_full_data() -> None:
    out = '{"data": {"data": {"token": "t", "user": "u"}}}'
    assert mod.parse_kv_get(out) == {"token": "t", "user": "u"}


def test_parse_kv_get_returns_single_field() -> None:
    out = '{"data": {"data": {"token": "t", "user": "u"}}}'
    assert mod.parse_kv_get(out, field="token") == "t"


def test_parse_kv_get_missing_field_raises() -> None:
    out = '{"data": {"data": {"token": "t"}}}'
    with pytest.raises(KeyError):
        mod.parse_kv_get(out, field="nope")
