#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module wrapping the ``yad`` GTK dialog utility.

This module provides a declarative, testable interface around ``yad``
(Yet Another Dialog).
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from typing import Any

from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = r"""
---
module: yad
short_description: Display a YAD (GTK) dialog and return the user's input
version_added: "1.0.0"
description:
  - Wraps the C(yad) (Yet Another Dialog) command-line utility in a
    declarative, idempotent-friendly Ansible module.
  - Supports form, entry, list and message dialogs with optional branding
    (title, text, image, fullscreen) and custom buttons.
  - Provides a built-in validation and retry loop so callers do not need to
    re-implement input validation in shell.
options:
  dialog:
    description:
      - The kind of YAD dialog to display.
      - C(form) shows a form with one or more fields and returns their values.
      - C(entry) shows a single-line text input dialog.
      - C(list) shows a selectable list with one or more columns.
      - C(message) shows an informational dialog (no input collected).
    type: str
    required: true
    choices: [form, entry, list, message]
  title:
    description: Window title.
    type: str
  text:
    description: Text shown inside the dialog above the input widgets.
    type: str
  image:
    description: Path to an image displayed in the dialog.
    type: path
  image_on_top:
    description: If true, place the image above the text instead of next to it.
    type: bool
    default: false
  fullscreen:
    description: Display the dialog fullscreen.
    type: bool
    default: false
  borders:
    description: Pixel width of the dialog borders.
    type: int
  align:
    description: Text alignment inside the dialog.
    type: str
    choices: [left, center, right, fill]
  width:
    description: Dialog width in pixels.
    type: int
  height:
    description: Dialog height in pixels.
    type: int
  fields:
    description:
      - Form field definitions. Required when O(dialog=form).
      - Each entry describes one input field shown in the dialog.
    type: list
    elements: dict
    suboptions:
      label:
        description: Field label shown to the user. Also used as result key.
        type: str
        required: true
      type:
        description:
          - YAD field type code (e.g. C(H) hidden/password, C(NUM) numeric,
            C(CHK) checkbox, C(CB) combo, C(RO) read-only, C(FL) file,
            C(DIR) directory, C(TXT) textarea, C(LBL) label).
          - Leave unset for a plain text field.
        type: str
      default:
        description: Default value pre-filled in the field.
        type: str
  columns:
    description: Column titles for O(dialog=list).
    type: list
    elements: str
  items:
    description:
      - Rows for O(dialog=list).
      - Each row is itself a list of column values that gets flattened
        and passed to C(yad).
    type: list
    elements: list
  print_column:
    description: One-based index of the column whose value should be returned.
    type: int
  entry_text:
    description: Default value pre-filled in an O(dialog=entry) prompt.
    type: str
  entry_hide:
    description: Hide entry input (password style) for O(dialog=entry).
    type: bool
    default: false
  buttons:
    description:
      - Buttons displayed at the bottom of the dialog.
      - When omitted, YAD's default OK/Cancel buttons are used.
      - Use C(action) to bind a button to a shell command that is launched
        when the button is pressed (see C(yad)'s C(--button) syntax).
    type: list
    elements: dict
    suboptions:
      label:
        description: Button label (may use a C(gtk-) stock id, e.g. C(gtk-ok)).
        type: str
        required: true
      action:
        description: Optional shell command executed when the button is pressed.
        type: str
  separator:
    description: Field separator used by C(yad) to delimit field values.
    type: str
    default: "|"
  validations:
    description:
      - Ordered list of validations applied after each successful dialog
        invocation. If any validation fails the user is shown an error
        dialog and re-prompted, up to O(max_attempts) times.
    type: list
    elements: dict
    suboptions:
      type:
        description: Kind of validation to run.
        type: str
        required: true
        choices: [required, regex, length, match, command]
      field:
        description:
          - Field this validation applies to. Accepts a field label or a
            zero-based index. Ignored for O(validations[].type=command)
            when the command consumes all field values via environment.
        type: str
      pattern:
        description: Regular expression for O(validations[].type=regex).
        type: str
      min:
        description: Minimum length for O(validations[].type=length).
        type: int
      max:
        description: Maximum length for O(validations[].type=length).
        type: int
      match:
        description: Other field (label or index) value must equal, for O(validations[].type=match).
        type: str
      command:
        description:
          - Shell command for O(validations[].type=command).
          - Validation passes when the command exits with status 0.
          - Field values are exposed as environment variables
            C(YAD_FIELD_0), C(YAD_FIELD_1), ... and, when labels are
            available, as C(YAD_FIELD_<UPPER_SNAKE_LABEL>).
          - The value of O(validations[].field) (when set) is additionally
            passed on standard input.
        type: str
      error_message:
        description: Message shown to the user when the validation fails.
        type: str
        default: "Invalid input. Please try again."
  max_attempts:
    description:
      - Maximum number of times the dialog is re-displayed after a validation
        failure. Set to C(0) for unlimited attempts.
    type: int
    default: 3
  executable:
    description: Path to the C(yad) executable.
    type: str
    default: yad
  display:
    description:
      - Value to set for the C(DISPLAY) environment variable when invoking
        C(yad). Required when running from a session that does not already
        export C(DISPLAY).
    type: str
  extra_args:
    description: Additional raw command-line arguments appended to the C(yad) call.
    type: list
    elements: str
notes:
  - This module never reports C(changed=true); displaying a dialog is not a
    state mutation. Wrap subsequent state-changing tasks accordingly.
  - In check mode the dialog is not displayed and empty results are returned.
  - The caller is responsible for setting C(no_log=true) on the task when
    the dialog collects secrets.
requirements:
  - The C(yad) binary must be installed on the target host.
  - A reachable X11 / Wayland display when actually prompting users.
author:
  - Potos Project (@projectpotos)
"""

EXAMPLES = r"""
- name: Ask for a hostname with regex validation
  potos.base.yad:
    dialog: form
    title: "Setup"
    text: "Please enter your hostname"
    fullscreen: true
    image: /setup/logo.png
    image_on_top: true
    fields:
      - label: Hostname
        type: ""
    validations:
      - type: required
        field: Hostname
        error_message: "Please choose the hostname."
      - type: regex
        field: Hostname
        pattern: '^[a-z0-9][a-z0-9-]{0,62}$'
        error_message: "Hostname is invalid!"
    buttons:
      - label: gtk-ok
      - label: Change keyboard layout
        action: /setup/change-keyboard-layout.sh
  register: hostname_dialog

- name: Ask for a new user account
  potos.base.yad:
    dialog: form
    title: "Setup"
    text: "Please enter your new credentials"
    fields:
      - label: Username
      - label: Password
        type: H
      - label: Confirm password
        type: H
    validations:
      - type: required
        field: Username
      - type: length
        field: Password
        min: 8
        error_message: "Password must be at least 8 characters."
      - type: match
        field: Password
        match: Confirm password
        error_message: "Passwords do not match."
  register: user_dialog
  no_log: true

- name: Verify an existing LUKS passphrase via custom command
  potos.base.yad:
    dialog: form
    title: "Disk encryption"
    fields:
      - label: Current passphrase
        type: H
    validations:
      - type: command
        field: Current passphrase
        command: "cryptsetup luksOpen --test-passphrase /dev/sda3"
        error_message: "The given passphrase was incorrect. Please try again."
  no_log: true

- name: Let the user pick a keyboard layout
  potos.base.yad:
    dialog: list
    width: 600
    height: 600
    columns: ["Keyboard Layout", ""]
    items:
      - ["us", "English (US)"]
      - ["de", "German"]
    print_column: 1
  register: kb_dialog
"""

RETURN = r"""
value:
  description:
    - Single user-supplied value for O(dialog=entry), O(dialog=list) or
      single-field forms.
    - Equal to the only entry of RV(values).
  type: str
  returned: when a value was collected
values:
  description: Ordered list of raw values returned by C(yad).
  type: list
  elements: str
  returned: always
fields:
  description:
    - Mapping of field label to value for O(dialog=form).
    - Only populated when every field has a unique label.
  type: dict
  returned: when O(dialog=form)
cancelled:
  description: True when the user cancelled the dialog (non-zero yad exit).
  type: bool
  returned: always
attempts:
  description: Number of times the dialog was displayed.
  type: int
  returned: always
cmd:
  description: The final command line used to invoke C(yad).
  type: list
  elements: str
  returned: always
"""


class YadError(Exception):
    """Raised for unrecoverable errors while running yad."""


def _run_yad(
    argv: list[str],
    env: dict[str, str],
    stdin_data: str | None = None,
) -> tuple[int, str, str]:
    """Execute ``yad`` and return ``(returncode, stdout, stderr)``.

    Isolated in its own helper so unit tests can monkey-patch it and
    deterministically simulate user input without a real X server.
    """
    proc = subprocess.run(  # noqa: S603 - argv is constructed from validated params
        argv,
        env=env,
        input=stdin_data,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _build_window_args(params: dict[str, Any]) -> list[str]:
    """Translate generic window/branding options to ``yad`` flags."""
    args: list[str] = []
    if params.get("title") is not None:
        args += ["--title", params["title"]]
    if params.get("text") is not None:
        args += ["--text", params["text"]]
    if params.get("image"):
        args += ["--image", params["image"]]
    if params.get("image_on_top"):
        args.append("--image-on-top")
    if params.get("fullscreen"):
        args.append("--fullscreen")
    if params.get("borders") is not None:
        args += ["--borders", str(params["borders"])]
    if params.get("align"):
        args += ["--align", params["align"]]
    if params.get("width") is not None:
        args += ["--width", str(params["width"])]
    if params.get("height") is not None:
        args += ["--height", str(params["height"])]
    return args


def _build_button_args(buttons: list[dict[str, Any]] | None) -> list[str]:
    """Translate the ``buttons`` list to ``--button`` flags."""
    if not buttons:
        return []
    args: list[str] = []
    for btn in buttons:
        label = btn["label"]
        action = btn.get("action")
        if action:
            args += ["--button", f"{label}:{action}"]
        else:
            args += ["--button", label]
    return args


def _build_form_args(
    fields: list[dict[str, Any]],
    separator: str,
) -> tuple[list[str], list[str]]:
    """Return ``(--field args, default value args)`` for a form dialog."""
    field_args: list[str] = ["--separator", separator]
    defaults: list[str] = []
    for field in fields:
        label = field["label"]
        ftype = field.get("type") or ""
        spec = f"{label}:{ftype}" if ftype else label
        field_args += ["--field", spec]
        defaults.append(field.get("default") or "")
    # Only pass defaults after ``--`` when at least one is non-empty,
    # to keep the command line minimal and easier to inspect in tests.
    if any(defaults):
        return field_args, ["--"] + defaults
    return field_args, []


def _build_list_args(
    columns: list[str] | None,
    items: list[list[str]] | None,
    print_column: int | None,
    separator: str,
) -> tuple[list[str], list[str]]:
    """Return ``(option args, positional row args)`` for a list dialog."""
    args: list[str] = ["--separator", separator]
    for col in columns or []:
        args += ["--column", col]
    if print_column is not None:
        args += ["--print-column", str(print_column)]
    rows: list[str] = []
    for row in items or []:
        rows += [str(cell) for cell in row]
    return args, rows


def _parse_output(stdout: str, separator: str) -> list[str]:
    """Split ``yad``'s stdout into a list of field values."""
    raw = stdout.rstrip("\n")
    if not raw:
        return []
    parts = raw.split(separator)
    # YAD's --form output is terminated with a trailing separator
    # which yields an empty element; drop it for ergonomics.
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _resolve_field(
    selector: str | None,
    values: list[str],
    labels: list[str],
) -> tuple[int, str] | tuple[None, None]:
    """Resolve a field selector (label or index) to ``(index, value)``."""
    if selector is None:
        return None, None
    # Numeric index?
    try:
        idx = int(selector)
    except (TypeError, ValueError):
        idx = -1
    if 0 <= idx < len(values):
        return idx, values[idx]
    if selector in labels:
        idx = labels.index(selector)
        if idx < len(values):
            return idx, values[idx]
    raise YadError(f"Validation refers to unknown field: {selector!r}")


def _env_for_validation(
    values: list[str],
    labels: list[str],
    base_env: dict[str, str],
) -> dict[str, str]:
    """Build env vars exposing field values for command validations."""
    env = dict(base_env)
    for idx, value in enumerate(values):
        env[f"YAD_FIELD_{idx}"] = value
        if idx < len(labels) and labels[idx]:
            slug = re.sub(r"[^A-Za-z0-9]+", "_", labels[idx]).strip("_").upper()
            if slug:
                env[f"YAD_FIELD_{slug}"] = value
    return env


def _validate(
    validations: list[dict[str, Any]],
    values: list[str],
    labels: list[str],
    base_env: dict[str, str],
) -> str | None:
    """Run all validations; return the first error message or ``None``."""
    for spec in validations:
        vtype = spec["type"]
        error_message = spec.get("error_message") or "Invalid input. Please try again."

        if vtype == "required":
            idx, value = _resolve_field(spec.get("field"), values, labels)
            if idx is None or not value:
                return error_message

        elif vtype == "regex":
            idx, value = _resolve_field(spec.get("field"), values, labels)
            pattern = spec.get("pattern")
            if pattern is None:
                raise YadError("regex validation requires 'pattern'")
            if value is None or not re.search(pattern, value):
                return error_message

        elif vtype == "length":
            idx, value = _resolve_field(spec.get("field"), values, labels)
            value = value or ""
            min_len = spec.get("min")
            max_len = spec.get("max")
            if min_len is not None and len(value) < min_len:
                return error_message
            if max_len is not None and len(value) > max_len:
                return error_message

        elif vtype == "match":
            idx_a, value_a = _resolve_field(spec.get("field"), values, labels)
            idx_b, value_b = _resolve_field(spec.get("match"), values, labels)
            if idx_a is None or idx_b is None:
                raise YadError("match validation requires both 'field' and 'match'")
            if value_a != value_b:
                return error_message

        elif vtype == "command":
            command = spec.get("command")
            if not command:
                raise YadError("command validation requires 'command'")
            _, stdin_value = (
                _resolve_field(spec["field"], values, labels)
                if spec.get("field") is not None
                else (None, None)
            )
            env = _env_for_validation(values, labels, base_env)
            proc = subprocess.run(  # noqa: S602 - explicit shell requested by caller
                command,
                shell=True,
                input=stdin_value if stdin_value is not None else "",
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                return error_message

        else:  # pragma: no cover - guarded by argspec choices
            raise YadError(f"Unknown validation type: {vtype}")

    return None


def _show_error(
    module_params: dict[str, Any],
    message: str,
    env: dict[str, str],
) -> None:
    """Display a transient YAD error dialog between retry attempts."""
    argv = [module_params["executable"]]
    if module_params.get("title") is not None:
        argv += ["--title", module_params["title"]]
    if module_params.get("image"):
        argv += ["--image", module_params["image"]]
        if module_params.get("image_on_top"):
            argv.append("--image-on-top")
    if module_params.get("borders") is not None:
        argv += ["--borders", str(module_params["borders"])]
    argv += ["--button", "gtk-ok", "--text", message]
    _run_yad(argv, env=env)


def _build_argv(params: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Assemble the final command line for the requested dialog kind.

    Returns ``(argv, field_labels, positional_tail)`` where
    ``positional_tail`` are arguments that must be appended after option
    flags (e.g. list rows or form field defaults).
    """
    dialog = params["dialog"]
    argv: list[str] = [params["executable"]]
    argv += _build_window_args(params)
    argv += _build_button_args(params.get("buttons"))
    labels: list[str] = []
    tail: list[str] = []

    if dialog == "form":
        fields = params.get("fields") or []
        if not fields:
            raise YadError("dialog=form requires at least one field")
        labels = [f["label"] for f in fields]
        argv.append("--form")
        form_args, tail = _build_form_args(fields, params["separator"])
        argv += form_args

    elif dialog == "entry":
        argv.append("--entry")
        if params.get("entry_text"):
            argv += ["--entry-text", params["entry_text"]]
        if params.get("entry_hide"):
            argv.append("--hide-text")

    elif dialog == "list":
        argv.append("--list")
        list_args, tail = _build_list_args(
            params.get("columns"),
            params.get("items"),
            params.get("print_column"),
            params["separator"],
        )
        argv += list_args

    elif dialog == "message":
        # No input widget - just show text. Default to --info if the user
        # did not supply custom buttons.
        if not params.get("buttons"):
            argv += ["--button", "gtk-ok"]

    if params.get("extra_args"):
        argv += list(params["extra_args"])

    if tail:
        argv += tail

    return argv, labels, tail


def _run_with_validation(
    params: dict[str, Any],
    env: dict[str, str],
) -> dict[str, Any]:
    """Drive the prompt/validate/retry loop and return the module result."""
    argv, labels, _tail = _build_argv(params)
    validations = params.get("validations") or []
    max_attempts = params["max_attempts"]
    attempts = 0
    last_values: list[str] = []
    cancelled = False

    while True:
        attempts += 1
        rc, stdout, _ = _run_yad(argv, env=env)
        if rc != 0:
            # Cancelled / closed: stop retrying.
            cancelled = True
            last_values = []
            break

        if params["dialog"] == "message":
            last_values = []
            break

        last_values = _parse_output(stdout, params["separator"])

        if not validations:
            break

        error = _validate(validations, last_values, labels, env)
        if error is None:
            break

        if max_attempts and attempts >= max_attempts:
            raise YadError(
                f"Validation failed after {attempts} attempt(s): {error}",
            )
        _show_error(params, error, env=env)

    result: dict[str, Any] = {
        "changed": False,
        "values": last_values,
        "cancelled": cancelled,
        "attempts": attempts,
        "cmd": argv,
    }
    if len(last_values) == 1:
        result["value"] = last_values[0]
    if params["dialog"] == "form" and labels and len(set(labels)) == len(labels):
        result["fields"] = {
            label: (last_values[idx] if idx < len(last_values) else "")
            for idx, label in enumerate(labels)
        }
    return result


def _prepare_env(display: str | None) -> dict[str, str]:
    """Return the environment to pass to ``yad`` invocations."""
    env = dict(os.environ)
    if display:
        env["DISPLAY"] = display
    return env


def main() -> None:
    """Module entry point invoked by Ansible."""
    argument_spec: dict[str, Any] = {
        "dialog": {
            "type": "str",
            "required": True,
            "choices": ["form", "entry", "list", "message"],
        },
        "title": {"type": "str"},
        "text": {"type": "str"},
        "image": {"type": "path"},
        "image_on_top": {"type": "bool", "default": False},
        "fullscreen": {"type": "bool", "default": False},
        "borders": {"type": "int"},
        "align": {
            "type": "str",
            "choices": ["left", "center", "right", "fill"],
        },
        "width": {"type": "int"},
        "height": {"type": "int"},
        "fields": {
            "type": "list",
            "elements": "dict",
            "options": {
                "label": {"type": "str", "required": True},
                "type": {"type": "str"},
                "default": {"type": "str"},
            },
        },
        "columns": {"type": "list", "elements": "str"},
        "items": {"type": "list", "elements": "list"},
        "print_column": {"type": "int"},
        "entry_text": {"type": "str"},
        "entry_hide": {"type": "bool", "default": False},
        "buttons": {
            "type": "list",
            "elements": "dict",
            "options": {
                "label": {"type": "str", "required": True},
                "action": {"type": "str"},
            },
        },
        "separator": {"type": "str", "default": "|"},
        "validations": {
            "type": "list",
            "elements": "dict",
            "options": {
                "type": {
                    "type": "str",
                    "required": True,
                    "choices": ["required", "regex", "length", "match", "command"],
                },
                "field": {"type": "str"},
                "pattern": {"type": "str"},
                "min": {"type": "int"},
                "max": {"type": "int"},
                "match": {"type": "str"},
                "command": {"type": "str"},
                "error_message": {
                    "type": "str",
                    "default": "Invalid input. Please try again.",
                },
            },
        },
        "max_attempts": {"type": "int", "default": 3},
        "executable": {"type": "str", "default": "yad"},
        "display": {"type": "str"},
        "extra_args": {"type": "list", "elements": "str"},
    }

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ["dialog", "form", ["fields"]],
            ["dialog", "list", ["columns"]],
        ],
    )

    if module.check_mode:
        module.exit_json(
            changed=False,
            values=[],
            cancelled=False,
            attempts=0,
            cmd=[],
            skipped_reason="check_mode",
        )

    env = _prepare_env(module.params.get("display"))

    try:
        result = _run_with_validation(module.params, env=env)
    except FileNotFoundError as exc:
        module.fail_json(
            msg=(
                f"Could not execute {module.params['executable']!r}: {exc}. "
                "Is the 'yad' package installed?"
            ),
        )
    except YadError as exc:
        module.fail_json(msg=str(exc))
    except Exception as exc:  # pragma: no cover
        module.fail_json(
            msg=f"Unexpected error while running yad: {exc}",
            cmd=shlex.join([module.params["executable"]]),
        )

    module.exit_json(**result)


if __name__ == "__main__":
    main()
