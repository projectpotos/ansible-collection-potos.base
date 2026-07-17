# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ``projectpotos.base.yad`` module."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest


_MODULE_PATH = Path(__file__).resolve().parents[4] / "plugins" / "modules" / "yad.py"
_spec = importlib.util.spec_from_file_location("potos_base_yad_under_test", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
yad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(yad)


def test_build_window_args_emits_only_set_options() -> None:
    """Only options the caller set should appear on the command line."""
    args = yad._build_window_args(
        {
            "title": "Setup",
            "text": "Hello",
            "image": "/setup/logo.png",
            "image_on_top": True,
            "fullscreen": True,
            "borders": 20,
            "align": "center",
            "width": 600,
            "height": 400,
        },
    )
    assert args == [
        "--title",
        "Setup",
        "--text",
        "Hello",
        "--image",
        "/setup/logo.png",
        "--image-on-top",
        "--fullscreen",
        "--borders",
        "20",
        "--align",
        "center",
        "--width",
        "600",
        "--height",
        "400",
    ]


def test_build_window_args_omits_unset() -> None:
    """An empty params dict should yield no arguments."""
    assert yad._build_window_args({}) == []


def test_build_button_args_plain_and_action() -> None:
    """Buttons with an action should be encoded as ``label:action``."""
    args = yad._build_button_args(
        [
            {"label": "OK"},
            {"label": "Change layout", "action": "/setup/kb.sh"},
        ],
    )
    assert args == [
        "--button",
        "OK",
        "--button",
        "Change layout:/setup/kb.sh",
    ]


def test_build_button_args_numeric_id() -> None:
    """A numeric id is encoded as ``label:id`` (the button's exit code)."""
    args = yad._build_button_args([{"label": "OK", "id": 0}])
    assert args == ["--button", "OK:0"]


def test_build_button_args_action_and_id_are_mutually_exclusive() -> None:
    with pytest.raises(yad.YadError):
        yad._build_button_args([{"label": "OK", "action": "/x.sh", "id": 0}])


def test_build_button_args_none() -> None:
    assert yad._build_button_args(None) == []
    assert yad._build_button_args([]) == []


def test_build_form_args_without_defaults_skips_positional_tail() -> None:
    fields = [{"label": "Username"}, {"label": "Password", "type": "H"}]
    field_args, tail = yad._build_form_args(fields, separator="|")
    assert field_args == [
        "--separator",
        "|",
        "--field",
        "Username",
        "--field",
        "Password:H",
    ]
    assert tail == []


def test_build_form_args_with_defaults_appends_after_double_dash() -> None:
    fields = [
        {"label": "Username", "default": "alice"},
        {"label": "Password", "type": "H"},
    ]
    _field_args, tail = yad._build_form_args(fields, separator="|")
    assert tail == ["--", "alice", ""]


def test_build_list_args_flattens_rows() -> None:
    args, rows = yad._build_list_args(
        columns=["Layout", "Description"],
        items=[["us", "English (US)"], ["de", "German"]],
        print_column=1,
        separator="|",
    )
    assert args == [
        "--separator",
        "|",
        "--column",
        "Layout",
        "--column",
        "Description",
        "--print-column",
        "1",
    ]
    assert rows == ["us", "English (US)", "de", "German"]


def test_parse_output_strips_trailing_separator_and_newline() -> None:
    assert yad._parse_output("alice|s3cret|s3cret|\n", "|") == [
        "alice",
        "s3cret",
        "s3cret",
    ]


def test_parse_output_empty_returns_empty_list() -> None:
    assert yad._parse_output("", "|") == []
    assert yad._parse_output("\n", "|") == []


def test_resolve_field_by_label_and_index() -> None:
    values = ["alice", "s3cret"]
    labels = ["Username", "Password"]
    assert yad._resolve_field("Password", values, labels) == (1, "s3cret")
    assert yad._resolve_field("0", values, labels) == (0, "alice")


def test_resolve_field_unknown_raises() -> None:
    with pytest.raises(yad.YadError):
        yad._resolve_field("Nope", ["v"], ["Label"])


def test_resolve_field_none_returns_none_tuple() -> None:
    assert yad._resolve_field(None, ["v"], ["L"]) == (None, None)


def test_env_for_validation_exposes_indexed_and_slug_vars() -> None:
    env = yad._env_for_validation(
        values=["alice", "s3cret"],
        labels=["Username", "Confirm password"],
        base_env={"PATH": "/usr/bin"},
    )
    assert env["PATH"] == "/usr/bin"
    assert env["YAD_FIELD_0"] == "alice"
    assert env["YAD_FIELD_1"] == "s3cret"
    assert env["YAD_FIELD_USERNAME"] == "alice"
    assert env["YAD_FIELD_CONFIRM_PASSWORD"] == "s3cret"


@pytest.fixture()
def labels() -> list[str]:
    return ["Username", "Password", "Confirm"]


def test_validate_required_pass_and_fail(labels: list[str]) -> None:
    spec = [{"type": "required", "field": "Username", "error_message": "missing"}]
    assert yad._validate(spec, ["alice", "x", "x"], labels, {}) is None
    assert yad._validate(spec, ["", "x", "x"], labels, {}) == ("missing", False)


def test_validate_regex_pass_and_fail() -> None:
    spec = [
        {
            "type": "regex",
            "field": "0",
            "pattern": r"^[a-z][a-z0-9-]{0,62}$",
            "error_message": "bad hostname",
        },
    ]
    assert yad._validate(spec, ["host01"], ["Hostname"], {}) is None
    assert yad._validate(spec, ["BadHost"], ["Hostname"], {}) == ("bad hostname", False)


def test_validate_length_min_max(labels: list[str]) -> None:
    spec = [
        {
            "type": "length",
            "field": "Password",
            "min": 8,
            "max": 16,
            "error_message": "len",
        },
    ]
    assert yad._validate(spec, ["a", "longpassword", "x"], labels, {}) is None
    assert yad._validate(spec, ["a", "short", "x"], labels, {}) == ("len", False)
    assert yad._validate(spec, ["a", "x" * 20, "x"], labels, {}) == ("len", False)


def test_validate_match_passwords(labels: list[str]) -> None:
    spec = [
        {
            "type": "match",
            "field": "Password",
            "match": "Confirm",
            "error_message": "mismatch",
        },
    ]
    assert yad._validate(spec, ["a", "pw", "pw"], labels, {}) is None
    assert yad._validate(spec, ["a", "pw", "PW"], labels, {}) == ("mismatch", False)


def test_validate_command_uses_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """A command exiting 0 passes; non-zero produces the error message."""
    calls: list[dict[str, Any]] = []

    class FakeCompleted:
        def __init__(self, rc: int) -> None:
            self.returncode = rc
            self.stdout = ""
            self.stderr = ""

    def fake_run(cmd: str, **kwargs: Any) -> FakeCompleted:
        calls.append({"cmd": cmd, **kwargs})
        # Pass when the piped passphrase matches "correct".
        return FakeCompleted(0 if kwargs.get("input") == "correct" else 1)

    monkeypatch.setattr(yad.subprocess, "run", fake_run)

    spec = [
        {
            "type": "command",
            "field": "Password",
            "command": "fake-cryptsetup --test",
            "error_message": "bad passphrase",
        },
    ]
    labels = ["Password"]

    assert yad._validate(spec, ["correct"], labels, {"PATH": "/usr/bin"}) is None
    assert yad._validate(spec, ["wrong"], labels, {"PATH": "/usr/bin"}) == (
        "bad passphrase",
        False,
    )

    # Field values must be exposed to the validation command via env vars.
    assert calls[0]["env"]["YAD_FIELD_0"] == "correct"
    assert calls[0]["env"]["YAD_FIELD_PASSWORD"] == "correct"
    assert calls[0]["shell"] is True


def test_validate_returns_first_error_only(labels: list[str]) -> None:
    """Validations short-circuit at the first failure."""
    spec = [
        {"type": "required", "field": "Username", "error_message": "first"},
        {"type": "required", "field": "Password", "error_message": "second"},
    ]
    assert yad._validate(spec, ["", "", ""], labels, {}) == ("first", False)


def test_validate_reports_markup_flag(labels: list[str]) -> None:
    spec = [
        {
            "type": "required",
            "field": "Username",
            "error_message": "<b>missing</b>",
            "markup": True,
        },
    ]
    assert yad._validate(spec, ["", "", ""], labels, {}) == ("<b>missing</b>", True)


def _show_error_text(monkeypatch: pytest.MonkeyPatch, message: str, markup: bool) -> str:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], env: dict[str, str], stdin_data: str | None = None):
        calls.append(argv)
        return 0, "", ""

    monkeypatch.setattr(yad, "_run_yad", fake_run)
    yad._show_error(_base_params(), message, env={}, markup=markup)
    argv = calls[0]
    return argv[argv.index("--text") + 1]


def test_show_error_escapes_pango_markup_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Special characters in plain error messages must not break yad's markup parser."""
    message = "The password must contain at least 1 special character (!@#$%^&*()<>)."
    assert _show_error_text(monkeypatch, message, markup=False) == (
        "The password must contain at least 1 special character (!@#$%^&amp;*()&lt;&gt;)."
    )


def test_show_error_passes_markup_through_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = "<b>Passwords</b> do not match."
    assert _show_error_text(monkeypatch, message, markup=True) == message


def _base_params(**overrides: Any) -> dict[str, Any]:
    """Build a fully-populated params dict mirroring the argspec defaults."""
    params: dict[str, Any] = {
        "dialog": "form",
        "title": None,
        "text": None,
        "image": None,
        "image_on_top": False,
        "fullscreen": False,
        "borders": None,
        "align": None,
        "width": None,
        "height": None,
        "fields": None,
        "columns": None,
        "items": None,
        "print_column": None,
        "entry_text": None,
        "entry_hide": False,
        "buttons": None,
        "separator": "|",
        "validations": None,
        "max_attempts": 3,
        "executable": "yad",
        "display": None,
        "extra_args": None,
    }
    params.update(overrides)
    return params


def test_build_argv_form() -> None:
    params = _base_params(
        dialog="form",
        title="Setup",
        fields=[
            {"label": "Username", "type": None, "default": None},
            {"label": "Password", "type": "H", "default": None},
        ],
        buttons=[{"label": "OK", "action": None}],
    )
    argv, labels, tail = yad._build_argv(params)
    assert argv[0] == "yad"
    assert "--form" in argv
    assert "--field" in argv
    assert labels == ["Username", "Password"]
    assert tail == []


def test_build_argv_entry_with_hide() -> None:
    params = _base_params(dialog="entry", entry_text="default", entry_hide=True)
    argv, labels, tail = yad._build_argv(params)
    assert "--entry" in argv
    assert "--entry-text" in argv
    assert "--hide-text" in argv
    assert labels == []


def test_build_argv_list() -> None:
    params = _base_params(
        dialog="list",
        columns=["Layout", "Desc"],
        items=[["us", "English"]],
        print_column=1,
    )
    argv, _labels, tail = yad._build_argv(params)
    assert "--list" in argv
    assert tail == ["us", "English"]


def test_build_argv_message_adds_default_ok_button() -> None:
    params = _base_params(dialog="message", text="hello")
    argv, _labels, _tail = yad._build_argv(params)
    assert "--button" in argv
    assert yad.DEFAULT_OK_LABEL in argv


def test_build_argv_form_requires_fields() -> None:
    with pytest.raises(yad.YadError):
        yad._build_argv(_base_params(dialog="form", fields=[]))


def test_build_argv_appends_extra_args() -> None:
    params = _base_params(dialog="message", extra_args=["--undecorated"])
    argv, _labels, _tail = yad._build_argv(params)
    assert "--undecorated" in argv


def test_run_with_validation_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful single-attempt form dialog populates ``fields`` map."""
    calls: list[list[str]] = []

    def fake_run(argv: list[str], env: dict[str, str], stdin_data: str | None = None):
        calls.append(argv)
        return 0, "alice|s3cret|s3cret|\n", ""

    monkeypatch.setattr(yad, "_run_yad", fake_run)

    params = _base_params(
        dialog="form",
        fields=[
            {"label": "Username", "type": None, "default": None},
            {"label": "Password", "type": "H", "default": None},
            {"label": "Confirm", "type": "H", "default": None},
        ],
        validations=[
            {
                "type": "match",
                "field": "Password",
                "match": "Confirm",
                "error_message": "mismatch",
            },
        ],
    )
    result = yad._run_with_validation(params, env={})
    assert result["raw_values"] == ["alice", "s3cret", "s3cret"]
    assert result["fields"] == {
        "Username": "alice",
        "Password": "s3cret",
        "Confirm": "s3cret",
    }
    assert result["cancelled"] is False
    assert result["attempts"] == 1
    assert len(calls) == 1


def test_run_with_validation_retries_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A validation failure triggers an error dialog and a retry."""
    outputs = iter(
        [
            (0, "alice|pw1|pw2|\n", ""),  # first attempt: mismatch
            (0, "", ""),  # error dialog ack
            (0, "alice|pw|pw|\n", ""),  # second attempt: success
        ],
    )

    def fake_run(argv: list[str], env: dict[str, str], stdin_data: str | None = None):
        return next(outputs)

    monkeypatch.setattr(yad, "_run_yad", fake_run)

    params = _base_params(
        dialog="form",
        fields=[
            {"label": "Username", "type": None, "default": None},
            {"label": "Password", "type": "H", "default": None},
            {"label": "Confirm", "type": "H", "default": None},
        ],
        validations=[
            {
                "type": "match",
                "field": "Password",
                "match": "Confirm",
                "error_message": "mismatch",
            },
        ],
    )
    result = yad._run_with_validation(params, env={})
    assert result["attempts"] == 2
    assert result["fields"]["Password"] == "pw"


def test_run_with_validation_exhausts_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When max_attempts is reached the module raises YadError."""

    def always_mismatch(argv: list[str], env: dict[str, str], stdin_data=None):
        return 0, "a|b|c|\n", ""

    monkeypatch.setattr(yad, "_run_yad", always_mismatch)

    params = _base_params(
        dialog="form",
        max_attempts=2,
        fields=[
            {"label": "Password", "type": "H", "default": None},
            {"label": "Confirm", "type": "H", "default": None},
            {"label": "Extra", "type": None, "default": None},
        ],
        validations=[
            {
                "type": "match",
                "field": "Password",
                "match": "Confirm",
                "error_message": "mismatch",
            },
        ],
    )
    with pytest.raises(yad.YadError, match="mismatch"):
        yad._run_with_validation(params, env={})


def test_run_with_validation_cancel_stops_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-zero yad exit marks the result cancelled and stops retrying."""

    def cancel(argv: list[str], env: dict[str, str], stdin_data=None):
        return 1, "", ""

    monkeypatch.setattr(yad, "_run_yad", cancel)

    params = _base_params(
        dialog="entry",
        validations=[{"type": "required", "field": "0", "error_message": "x"}],
    )
    result = yad._run_with_validation(params, env={})
    assert result["cancelled"] is True
    assert result["raw_values"] == []
    assert result["attempts"] == 1


def test_run_with_validation_message_dialog_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Message dialogs collect no input."""

    def fake(argv, env, stdin_data=None):
        return 0, "", ""

    monkeypatch.setattr(yad, "_run_yad", fake)

    params = _base_params(dialog="message", text="hello")
    result = yad._run_with_validation(params, env={})
    assert result["raw_values"] == []
    assert result["cancelled"] is False
    assert result["attempts"] == 1
    assert "value" not in result
    assert "fields" not in result


def test_run_with_validation_single_value_sets_value_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entry dialogs return a single ``value``."""

    def fake(argv, env, stdin_data=None):
        return 0, "host01\n", ""

    monkeypatch.setattr(yad, "_run_yad", fake)

    params = _base_params(dialog="entry")
    result = yad._run_with_validation(params, env={})
    assert result["value"] == "host01"
    assert result["raw_values"] == ["host01"]
