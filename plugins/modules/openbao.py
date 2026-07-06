#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Interact with an OpenBao server via its CLI.

This ansible module provides options to interact with OpenBao's KV engine.
It also supports interactive OIDC logins.
"""

from __future__ import annotations


DOCUMENTATION = r"""
---
module: openbao
short_description: Interact with OpenBao KV engine
version_added: "0.1.0"
description:
  - Wraps the C(bao) CLI to interact with KV secrets.
  - Supports OIDC device-code logins with a callback notification of the verification URL and user code.
options:
  action:
    description: The operation to perform.
    type: str
    required: true
    choices: [login, kv_get, kv_put]
  url:
    description: Server address (exported as C(BAO_ADDR)/C(VAULT_ADDR)).
    type: str
    required: true
  cli:
    description:
      - CLI executable to use. When unset, C(bao) is used.
    type: str
  token:
    description:
      - Auth token for O(action=kv_get)/O(action=kv_put) (exported as
        C(BAO_TOKEN)/C(VAULT_TOKEN)). Not needed for O(action=login).
    type: str
  method:
    description: Auth method for O(action=login).
    type: str
    default: oidc
  mount:
    description: Auth mount path (C(-path)) for O(action=login).
    type: str
    default: oidc
  role:
    description: Role to request for O(action=login).
    type: str
  callback_mode:
    description:
      - OIDC callback mode for O(action=login) (login param C(callbackmode)),
        e.g. C(device) for the device-code flow.
    type: str
  callback_host:
    description: OIDC callback host for O(action=login).
    type: str
  listen_address:
    description:
      - Address the OIDC local callback listener binds to for O(action=login).
    type: str
  options:
    description:
      - Additional parameters for O(action=login) as a C(key=value) map.
    type: dict
  browser:
    description:
      - For O(action=login), open the OIDC verification URL with C(xdg-open)
        when it is detected in the CLI output.
    type: bool
    default: true
  notify_command:
    description:
      - For O(action=login), a shell command run when the OIDC verification URL
        is detected, with C(OIDC_VERIFICATION_URL) and C(OIDC_USER_CODE)
        exported in its environment. Intended to show the URL/code to the user
        (e.g. a C(yad) dialog) so the device flow can be completed on any
        device. It is started in the background and terminated once login
        finishes. If the user dismisses it first the login is aborted.
    type: str
  path:
    description: KV v2 secret path for O(action=kv_get)/O(action=kv_put).
    type: str
  field:
    description:
      - For O(action=kv_get), return only this field's value in RV(value).
    type: str
  data:
    description: Key/value map to write for O(action=kv_put).
    type: dict
author:
  - Project Potos (@projectpotos)
"""

EXAMPLES = r"""
- name: OIDC device-code login
  projectpotos.base.openbao:
    action: login
    url: https://bao.example.com
    role: device
    callback_mode: device
    callback_host: localhost
    listen_address: 127.0.0.1
  register: bao

- name: Read the specs token
  projectpotos.base.openbao:
    action: kv_get
    url: https://bao.example.com
    token: "{{ bao.token }}"
    path: kv/potos/specs
    field: token
"""

RETURN = r"""
token:
  description: The client token (O(action=login)).
  type: str
  returned: when action=login
data:
  description: The secret's key/value data (O(action=kv_get)).
  type: dict
  returned: when action=kv_get
value:
  description: The requested field's value (O(action=kv_get) with O(field)).
  type: str
  returned: when action=kv_get and field is set
"""

import glob
import json
import os
import pwd
import re
import signal
import stat
import tempfile
import threading
import time
from subprocess import DEVNULL, PIPE, Popen
from typing import Any

from ansible.module_utils.basic import AnsibleModule


def build_login_options(
    role: str | None,
    callback_mode: str | None,
    callback_host: str | None,
    listen_address: str | None,
    extra: dict[str, Any] | None,
) -> dict[str, str]:
    """Assemble the ordered ``key=value`` OIDC login parameters."""
    options: dict[str, str] = {}
    if role is not None:
        options["role"] = role
    if callback_mode is not None:
        options["callbackmode"] = callback_mode
    if callback_host is not None:
        options["callbackhost"] = callback_host
    if listen_address is not None:
        options["listenaddress"] = listen_address
    for key, value in (extra or {}).items():
        options[str(key)] = str(value)
    return options


def build_login_argv(
    cli: str, method: str, mount: str, options: dict[str, str] | None
) -> list[str]:
    """Build the ``login`` argv."""
    argv = [cli, "login", "-format=json", f"-method={method}", f"-path={mount}"]
    for key, value in (options or {}).items():
        argv.append(f"{key}={value}")
    return argv


def build_kv_get_argv(cli: str, path: str) -> list[str]:
    """Build the ``kv get`` argv."""
    return [cli, "kv", "get", "-format=json", path]


def build_kv_put_argv(cli: str, path: str, datafile: str) -> list[str]:
    """Build the ``kv put`` argv reading data from a JSON file."""
    return [cli, "kv", "put", path, f"@{datafile}"]


def parse_login_token(stdout: str) -> str:
    """Extract the client token from ``login -format=json`` output."""
    text = stdout.strip()
    brace = text.find("{")
    if brace > 0:
        text = text[brace:]
    doc = json.loads(text)
    return doc["auth"]["client_token"]


_URL_RE = re.compile(r"https?://[^\s'\"<>]+")
_USER_CODE_RE = re.compile(r"(?:user_code=|[Uu]ser[ _]?[Cc]ode[:=]\s*)([A-Za-z0-9-]+)")


def extract_verification_url(text: str) -> str | None:
    """Return the first http(s) URL found in CLI output, or None."""
    match = _URL_RE.search(text)
    return match.group(0) if match else None


def extract_user_code(text: str) -> str | None:
    """Return the OIDC device user code from the CLI output."""
    match = _USER_CODE_RE.search(text)
    return match.group(1) if match else None


def graphical_env(base_env: dict[str, str]) -> dict[str, str]:
    """Return ``base_env`` with a tuned environment to reach the users graphical session.
    ls ls

    This module is usually executed as root. Therefore we end up with ``XDG_RUNTIME_DIR=/run/user/0``.
    But we need the users wayland socket for helper tools like C(xdg-open) or C(wl-copy).
    Therefore we point `XDG_RUNTIME_DIR`` and ``WAYLAND_DISPLAY`` at the first wayland socket found.
    This assumes only one GUI session is running for the user.
    """
    env = dict(base_env)
    # TODO: isn't there a better way?
    for sock in sorted(glob.glob("/run/user/*/wayland-*")):
        try:
            if not stat.S_ISSOCK(os.stat(sock).st_mode):
                continue  # skip wayland-0.lock
        except OSError:
            continue
        env["XDG_RUNTIME_DIR"] = os.path.dirname(sock)
        env["WAYLAND_DISPLAY"] = os.path.basename(sock)
        break
    return env


def session_user(gui_env: dict[str, str]) -> tuple[int, str, str] | None:
    """Return ``(uid, name, home)`` of the graphical session."""
    runtime = gui_env.get("XDG_RUNTIME_DIR", "").rstrip("/")
    base = os.path.basename(runtime)
    if not base.isdigit():
        return None
    try:
        info = pwd.getpwuid(int(base))
    except KeyError:
        return None
    return info.pw_uid, info.pw_name, info.pw_dir


def build_browser_argv(url: str, gui_env: dict[str, str]) -> list[str]:
    """Build the argv to open ``url`` in a browser.

    Some browsers like Firefox refuse to run as root,
    so we switch back to the logged-in user via ``runuser``.
    """
    sess = session_user(gui_env)
    if sess is None or os.geteuid() != 0:
        return ["xdg-open", url]
    _uid, name, home = sess
    runtime = gui_env["XDG_RUNTIME_DIR"]
    env_args = [
        f"HOME={home}",
        f"XDG_RUNTIME_DIR={runtime}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus",
    ]
    for var in ("DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY"):
        if gui_env.get(var):
            env_args.append(f"{var}={gui_env[var]}")
    return ["runuser", "-u", name, "--", "env", *env_args, "xdg-open", url]


def _spawn_detached(cmd: Any, env: dict[str, str], shell: bool = False) -> Popen:
    """Start a detached subprocess with its own session."""
    # module.run_command blocks until exit; the browser/notify helpers must
    # keep running in their own session while the login continues.
    # pylint: disable-next=ansible-bad-function
    return Popen(  # noqa: S603
        cmd,
        shell=shell,
        env=env,
        stdin=DEVNULL,
        stdout=DEVNULL,
        stderr=DEVNULL,
        start_new_session=True,
    )


def _terminate_group(proc: Popen | None) -> None:
    """Best-effort termination of a process started with ``start_new_session`` using SIGTERM."""
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (OSError, ProcessLookupError):
        try:
            proc.terminate()
        except OSError:
            pass


def run_oidc_login(
    argv: list[str],
    env: dict[str, str],
    open_browser: bool,
    notify_command: str | None,
) -> tuple[int, str, str]:
    """Run the interactive OIDC login. surfacing the verification URL.

    Use the ``notify_command`` as a callback to show the oidc flow information.
    The ``OIDC_VERIFICATION_URL`` and ``OIDC_USER_CODE`` environment variables
    will be exposed to any command you provide.

    Returns ``(returncode, stdout, stderr)``.
    """
    # The interactive login streams output that must be scanned live for the
    # verification URL; module.run_command cannot expose it before exit.
    # pylint: disable-next=ansible-bad-function
    proc = Popen(  # noqa: S603
        argv,
        env=env,
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )
    out_buf: list[str] = []
    err_buf: list[str] = []
    state: dict[str, Any] = {"notify": None, "notify_started": 0.0}
    seen = threading.Event()
    # override envs required for GUI stuff
    gui_env = graphical_env(env)

    def on_url(line: str) -> None:
        if seen.is_set():
            return
        url = extract_verification_url(line)
        if not url:
            return
        seen.set()
        if open_browser:
            try:
                _spawn_detached(build_browser_argv(url, gui_env), gui_env)
            except OSError:
                pass
        if notify_command:
            notify_env = dict(gui_env)
            notify_env["OIDC_VERIFICATION_URL"] = url
            notify_env["OIDC_USER_CODE"] = extract_user_code(line) or ""
            try:
                state["notify"] = _spawn_detached(notify_command, notify_env, shell=True)
                state["notify_started"] = time.monotonic()
            except OSError:
                pass

    def drain(stream: Any, buf: list[str], scan: bool) -> None:
        for line in stream:
            buf.append(line)
            if scan:
                on_url(line)
        stream.close()

    t_err = threading.Thread(target=drain, args=(proc.stderr, err_buf, True), daemon=True)
    t_out = threading.Thread(target=drain, args=(proc.stdout, out_buf, False), daemon=True)
    t_err.start()
    t_out.start()

    # Wait for the login to finish. If the notification dialog is dismissed by the
    # user abort the login.
    while proc.poll() is None:
        notify = state["notify"]
        if (
            notify is not None
            and notify.poll() is not None
            and time.monotonic() - state["notify_started"] > 2.0
        ):
            _terminate_group(proc)
            break
        time.sleep(0.2)

    proc.wait()
    t_err.join()
    t_out.join()
    _terminate_group(state["notify"])
    return proc.returncode, "".join(out_buf), "".join(err_buf)


def parse_kv_get(stdout: str, field: str | None = None) -> Any:
    """Extract KV v2 data from ``kv get -format=json``.

    Returns the data dict, or the single field's value when ``field`` is set.
    Raises KeyError when the field is absent.
    """
    doc = json.loads(stdout)
    data = doc["data"]["data"]
    if field is not None:
        return data[field]
    return data


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "action": {"type": "str", "required": True, "choices": ["login", "kv_get", "kv_put"]},
            "url": {"type": "str", "required": True},
            "cli": {"type": "str"},
            "token": {"type": "str", "no_log": True},
            "method": {"type": "str", "default": "oidc"},
            "mount": {"type": "str", "default": "oidc"},
            "role": {"type": "str"},
            "callback_mode": {"type": "str"},
            "callback_host": {"type": "str"},
            "listen_address": {"type": "str"},
            "options": {"type": "dict"},
            "browser": {"type": "bool", "default": True},
            "notify_command": {"type": "str"},
            "path": {"type": "str"},
            "field": {"type": "str"},
            "data": {"type": "dict"},
        },
        required_if=[
            ["action", "kv_get", ["path"]],
            ["action", "kv_put", ["path", "data"]],
        ],
        supports_check_mode=False,
    )

    action = module.params["action"]
    cli = module.params["cli"]
    if not cli:
        cli = module.get_bin_path("bao") or module.get_bin_path("vault")
    if not cli:
        module.fail_json(msg="Neither 'bao' nor 'vault' CLI is installed.")

    env = dict(os.environ)
    env["BAO_ADDR"] = module.params["url"]
    env["VAULT_ADDR"] = module.params["url"]
    if module.params["token"]:
        env["BAO_TOKEN"] = module.params["token"]
        env["VAULT_TOKEN"] = module.params["token"]

    if action == "login":
        options = build_login_options(
            module.params["role"],
            module.params["callback_mode"],
            module.params["callback_host"],
            module.params["listen_address"],
            module.params["options"],
        )
        # Always suppress the CLI's own browser launch.
        options.setdefault("skip_browser", "true")
        argv = build_login_argv(cli, module.params["method"], module.params["mount"], options)
        rc, out, err = run_oidc_login(
            argv,
            env,
            open_browser=module.params["browser"],
            notify_command=module.params["notify_command"],
        )
        if rc != 0:
            module.fail_json(msg=f"openbao login failed: {err.strip()}")
        try:
            token = parse_login_token(out)
        except (ValueError, KeyError) as exc:
            module.fail_json(msg=f"Could not parse login token: {exc}")
        module.exit_json(changed=True, token=token)

    if action == "kv_get":
        argv = build_kv_get_argv(cli, module.params["path"])
        rc, out, err = module.run_command(argv, environ_update=env)
        if rc != 0:
            module.fail_json(msg=f"openbao kv get failed: {err.strip()}")
        try:
            data = parse_kv_get(out)
            result = {"changed": False, "data": data}
            if module.params["field"] is not None:
                result["value"] = data[module.params["field"]]
        except (ValueError, KeyError) as exc:
            module.fail_json(msg=f"Could not parse kv get output: {exc}")
        module.exit_json(**result)

    # action == kv_put
    fd, datafile = tempfile.mkstemp(prefix="potos-openbao-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(module.params["data"], handle)
        argv = build_kv_put_argv(cli, module.params["path"], datafile)
        rc, _out, err = module.run_command(argv, environ_update=env)
        if rc != 0:
            module.fail_json(msg=f"openbao kv put failed: {err.strip()}")
    finally:
        os.unlink(datafile)
    module.exit_json(changed=True)


if __name__ == "__main__":
    main()
