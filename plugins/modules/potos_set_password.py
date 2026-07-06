#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Set a local user's password via ``chpasswd``..

The password may be supplied or randomly generated (O(generate=true)). The
effective password is returned as module output.
"""

from __future__ import annotations


DOCUMENTATION = r"""
---
module: potos_set_password
short_description: Set a local user's password using chpasswd
version_added: "0.1.0"
description:
  - Sets the password of an existing local user
  - This module is not idempotent. C(chpasswd) cannot report whether the
    password already matched, so the task always reports C(changed=true).
options:
  name:
    description: Login name of the user whose password needs changing.
    type: str
    required: true
  password:
    description:
      - The password to set. Plaintext by default, or a crypted hash when
        O(encrypted=true). Mutually exclusive with O(generate).
    type: str
  encrypted:
    description:
      - When true, O(password) is already a crypted hash and is passed to
        C(chpasswd -e). When false, O(password) is plaintext and C(chpasswd)
        hashes it. Cannot be combined with O(generate).
    type: bool
    default: false
  generate:
    description:
      - Generate a random plaintext password instead of supplying O(password).
        The generated value is returned in RV(password).
    type: bool
    default: false
  length:
    description: Length of the generated password when O(generate=true).
    type: int
    default: 32
author:
  - Project Potos (@projectpotos)
"""

EXAMPLES = r"""
- name: Set the operator's password
  potos.base.potos_set_password:
    name: operator
    password: "{{ chosen_password }}"
  no_log: true

- name: Rotate the admin account to a random password
  potos.base.potos_set_password:
    name: admin
    generate: true
  register: rotated
  no_log: true
"""

RETURN = r"""
name:
  description: The user whose password was set.
  type: str
  returned: always
password:
  description: The password that was set.
  type: str
  returned: always
"""

import secrets
import string

from ansible.module_utils.basic import AnsibleModule


_PASSPHRASE_CHOICES = string.ascii_letters + string.digits + string.punctuation


def generate_password(length: int) -> str:
    """Generate a random password."""
    return "".join(secrets.choice(_PASSPHRASE_CHOICES) for _i in range(length))


def build_chpasswd_argv(chpasswd: str, encrypted: bool) -> list[str]:
    """Build the chpasswd command line."""
    argv = [chpasswd]
    if encrypted:
        argv.append("-e")
    return argv


def build_chpasswd_stdin(name: str, password: str) -> str:
    """Build the ``user:password`` line fed to chpasswd."""
    return f"{name}:{password}"


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "name": {"type": "str", "required": True},
            "password": {"type": "str", "no_log": True},
            "encrypted": {"type": "bool", "default": False},
            "generate": {"type": "bool", "default": False},
            "length": {"type": "int", "default": 32},
        },
        mutually_exclusive=[["password", "generate"]],
        supports_check_mode=True,
    )

    name = module.params["name"]
    encrypted = module.params["encrypted"]

    if module.params["generate"]:
        if encrypted:
            module.fail_json(
                msg="generate=true produces a plaintext password; encrypted must be false."
            )
        password = generate_password(module.params["length"])
    elif module.params["password"] is not None:
        password = module.params["password"]
    else:
        module.fail_json(msg="provide 'password' or set generate=true.")

    chpasswd = module.get_bin_path("chpasswd", required=True)
    argv = build_chpasswd_argv(chpasswd, encrypted)
    stdin = build_chpasswd_stdin(name, password)

    if module.check_mode:
        module.exit_json(changed=True, name=name, password=password)

    rc, _out, err = module.run_command(argv, data=stdin, binary_data=False)
    if rc != 0:
        module.fail_json(msg=f"chpasswd failed for user '{name}': {err.strip()}", name=name)

    module.exit_json(changed=True, name=name, password=password)


if __name__ == "__main__":
    main()
