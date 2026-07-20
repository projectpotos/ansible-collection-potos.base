#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Encrypt/decrypt secrets with ``systemd-creds``.

Stores a secret as an encrypted credential, optionally bound to the TPM. The
three bindings Potos cares about are:
  - host / TPM / both         -> --with-key=host|tpm2|host+tpm2
  - PCR 11 signed policy      -> --with-key=*-with-public-key
                                 --tpm2-public-key=PEM --tpm2-public-key-pcrs=11
  - extra literal PCRs        -> --tpm2-pcrs=7+14+...

systemd-creds only honors --tpm2-public-key when the key type carries the
public-key property (or in auto mode); with plain tpm2/host+tpm2 it silently
seals WITHOUT the signed policy. The module refuses such combinations.
"""

from __future__ import annotations


DOCUMENTATION = r"""
---
module: systemd_creds
short_description: Encrypt or decrypt a secret with systemd-creds
version_added: "0.1.0"
description:
  - O(action=encrypt) encrypts O(secret) into an encrypted credential written to
    O(output_path), optionally bound to the TPM.
  - O(action=decrypt) decrypts O(input_path) and returns the plaintext.
options:
  action:
    description: Operation to perform.
    type: str
    default: encrypt
    choices: [encrypt, decrypt]
  name:
    description: Credential name.
    type: str
  secret:
    description: Plaintext to encrypt (O(action=encrypt)) from stdin.
    type: str
  input_path:
    description: Path to the encrypted blob to decrypt (O(action=decrypt)).
    type: str
  output_path:
    description: Where to write the encrypted blob (O(action=encrypt)).
    type: str
  with_key:
    description:
      - Encryption key selection.
      - The V(*-with-public-key) types additionally bind to the signed PCR
        policy and require O(tpm2_public_key). The other explicit types make
        systemd-creds silently ignore a public key, so combining them with
        O(tpm2_public_key) fails.
    type: str
    default: auto
    choices:
      [
        "host",
        "tpm2",
        "host+tpm2",
        "tpm2-with-public-key",
        "host+tpm2-with-public-key",
        "tpm2-with-public-key+host",
        "null",
        "auto",
        "auto-initrd",
      ]
  tpm2_pcrs:
    description: Literal PCRs to bind to.
    type: list
    elements: str
    default: []
  tpm2_public_key:
    description:
      - PEM public key for the signed PCR policy.
      - Requires a V(*-with-public-key) O(with_key) type (or V(auto)).
    type: str
  tpm2_public_key_pcrs:
    description: PCRs covered by the signed policy.
    type: list
    elements: str
    default: ["11"]
  tpm2_signature:
    description: Signature JSON for O(action=decrypt).
    type: str
  tpm2_device:
    description: TPM device.
    type: str
author:
  - Project Potos (@projectpotos)
"""

EXAMPLES = r"""
- name: Store a secret, TPM-bound to the PCR 11 signature
  projectpotos.base.systemd_creds:
    action: encrypt
    name: secret
    secret: "super-secret"
    output_path: /etc/potos/secret.cred
    with_key: host+tpm2-with-public-key
    tpm2_public_key: /etc/secureboot/pcr-system.pub.pem
  no_log: true
"""

RETURN = r"""
path:
  description: The blob path written (O(action=encrypt)).
  type: str
  returned: when action=encrypt
plaintext:
  description: The decrypted plaintext (O(action=decrypt)).
  type: str
  returned: when action=decrypt
"""

import os
from typing import Any

from ansible.module_utils.basic import AnsibleModule


PUBLIC_KEY_TYPES = frozenset(
    ["tpm2-with-public-key", "host+tpm2-with-public-key", "tpm2-with-public-key+host"]
)


def format_pcr_list(pcrs: list[Any] | None) -> str:
    """Join PCR identifiers with '+'"""
    if not pcrs:
        return ""
    return "+".join(str(pcr) for pcr in pcrs)


def validate_key_binding(with_key: str, public_key: str | None) -> str | None:
    """Return an error message when with_key and tpm2_public_key conflict.

    systemd-creds only loads --tpm2-public-key when the key type carries the
    public-key property (or resolves it in auto mode); with the other explicit
    types the option is silently ignored and the blob is sealed without the
    signed PCR policy. A *-with-public-key type without an explicit key falls
    back to the booted UKI's /run/systemd/tpm2-pcr-public-key.pem.
    """
    if public_key and with_key not in PUBLIC_KEY_TYPES and with_key != "auto":
        return (
            f"tpm2_public_key is silently ignored by systemd-creds with with_key={with_key}; "
            "use one of " + ", ".join(sorted(PUBLIC_KEY_TYPES)) + " (or auto)"
        )
    if not public_key and with_key in PUBLIC_KEY_TYPES:
        return (
            f"with_key={with_key} requires tpm2_public_key; without it systemd-creds "
            "falls back to the booted UKI's public key from /run"
        )
    return None


def build_encrypt_argv(
    exe: str,
    *,
    name: str | None,
    with_key: str,
    tpm2_pcrs: list[Any] | None,
    public_key: str | None,
    public_key_pcrs: list[Any] | None,
    tpm2_device: str | None,
    input_path: str = "-",
    output_path: str = "-",
) -> list[str]:
    """Build the ``systemd-creds encrypt`` argv."""
    argv = [exe, "encrypt"]
    if name:
        argv.append(f"--name={name}")
    if with_key:
        argv.append(f"--with-key={with_key}")
    pcrs = format_pcr_list(tpm2_pcrs)
    if pcrs:
        argv.append(f"--tpm2-pcrs={pcrs}")
    if public_key:
        argv.append(f"--tpm2-public-key={public_key}")
        pk_pcrs = format_pcr_list(public_key_pcrs)
        if pk_pcrs:
            argv.append(f"--tpm2-public-key-pcrs={pk_pcrs}")
    if tpm2_device:
        argv.append(f"--tpm2-device={tpm2_device}")
    argv += [input_path, output_path]
    return argv


def build_decrypt_argv(
    exe: str,
    *,
    name: str | None,
    tpm2_signature: str | None,
    tpm2_device: str | None,
    input_path: str,
    output_path: str = "-",
) -> list[str]:
    """Build the ``systemd-creds decrypt`` argv."""
    argv = [exe, "decrypt"]
    if name:
        argv.append(f"--name={name}")
    if tpm2_signature:
        argv.append(f"--tpm2-signature={tpm2_signature}")
    if tpm2_device:
        argv.append(f"--tpm2-device={tpm2_device}")
    argv += [input_path, output_path]
    return argv


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "action": {"type": "str", "default": "encrypt", "choices": ["encrypt", "decrypt"]},
            "name": {"type": "str"},
            "secret": {"type": "str", "no_log": True},
            "input_path": {"type": "str"},
            "output_path": {"type": "str"},
            "with_key": {
                "type": "str",
                "default": "auto",
                "choices": [
                    "host",
                    "tpm2",
                    "host+tpm2",
                    "tpm2-with-public-key",
                    "host+tpm2-with-public-key",
                    "tpm2-with-public-key+host",
                    "null",
                    "auto",
                    "auto-initrd",
                ],
            },
            "tpm2_pcrs": {"type": "list", "elements": "str", "default": []},
            "tpm2_public_key": {"type": "str"},
            "tpm2_public_key_pcrs": {"type": "list", "elements": "str", "default": ["11"]},
            "tpm2_signature": {"type": "str"},
            "tpm2_device": {"type": "str"},
        },
        required_if=[
            ["action", "encrypt", ["secret", "output_path"]],
            ["action", "decrypt", ["input_path"]],
        ],
        supports_check_mode=False,
    )

    exe = module.get_bin_path("systemd-creds", required=True)

    # action == encrypt
    if module.params["action"] == "encrypt":
        error = validate_key_binding(module.params["with_key"], module.params["tpm2_public_key"])
        if error:
            module.fail_json(msg=error)
        argv = build_encrypt_argv(
            exe,
            name=module.params["name"],
            with_key=module.params["with_key"],
            tpm2_pcrs=module.params["tpm2_pcrs"],
            public_key=module.params["tpm2_public_key"],
            public_key_pcrs=module.params["tpm2_public_key_pcrs"],
            tpm2_device=module.params["tpm2_device"],
            input_path="-",
            output_path=module.params["output_path"],
        )
        # binary_data=True so run_command does not append a newline to stdin
        rc, _out, err = module.run_command(argv, data=module.params["secret"], binary_data=True)
        if rc != 0:
            module.fail_json(msg=f"systemd-creds encrypt failed: {err.strip()}")
        os.chmod(module.params["output_path"], 0o600)
        module.exit_json(changed=True, path=module.params["output_path"])

    # action == decrypt
    argv = build_decrypt_argv(
        exe,
        name=module.params["name"],
        tpm2_signature=module.params["tpm2_signature"],
        tpm2_device=module.params["tpm2_device"],
        input_path=module.params["input_path"],
        output_path="-",
    )
    rc, out, err = module.run_command(argv, binary_data=False)
    if rc != 0:
        module.fail_json(msg=f"systemd-creds decrypt failed: {err.strip()}")
    module.exit_json(changed=False, plaintext=out)


if __name__ == "__main__":
    main()
