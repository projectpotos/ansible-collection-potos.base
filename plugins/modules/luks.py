#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Do various LUKS operations like rotate a passphrase or enroll the TPM2 as an unlock method.
If the caller provides no device, the module uses the first entry found in /etc/crypttab.
"""

from __future__ import annotations


DOCUMENTATION = r"""
---
module: luks
short_description: Do various LUKS operations
version_added: "0.1.0"
description:
  - O(action=discover) resolves the active LUKS device from C(/etc/crypttab).
  - O(action=change_key) changes a LUKS passphrase via C(cryptsetup luksChangeKey).
  - O(action=enroll_tpm2) enrolls the TPM2 as a LUKS unlock method via
    C(systemd-cryptenroll), so the disk auto-unlocks when the measured boot
    state matches.
options:
  action:
    description: The operation to perform.
    type: str
    required: true
    choices: [discover, change_key, enroll_tpm2]
  device:
    description:
      - LUKS device path. When unset, the first device from C(/etc/crypttab) is used.
    type: str
  passphrase:
    description: The current passphrase (required for O(action=change_key)).
    type: str
  new_passphrase:
    description:
      - The replacement passphrase for O(action=change_key). Mutually exclusive
        with O(generate).
    type: str
  generate:
    description:
      - Generate a random new passphrase instead of supplying O(new_passphrase).
        The generated value is returned in RV(passphrase).
    type: bool
    default: false
  length:
    description: Length of the generated passphrase when O(generate=true).
    type: int
    default: 64
  crypttab:
    description: Path to the crypttab file used for discovery.
    type: str
    default: /etc/crypttab
  tpm2_device:
    description: TPM device for O(action=enroll_tpm2) (C(--tpm2-device)).
    type: str
    default: auto
  tpm2_pcrs:
    description: Literal PCRs to bind to (C(--tpm2-pcrs)).
    type: list
    elements: str
    default: []
  tpm2_public_key:
    description: PEM public key for the signed PCR policy (C(--tpm2-public-key)).
    type: str
  tpm2_public_key_pcrs:
    description: PCRs covered by the signed policy (C(--tpm2-public-key-pcrs)).
    type: list
    elements: str
    default: ["11"]
  tpm2_with_pin:
    description: Additionally require a PIN to unlock (C(--tpm2-with-pin)).
    type: bool
    default: false
  pin:
    description: The new PIN when O(tpm2_with_pin=true).
    type: str
  wipe_slots:
    description: Slots to wipe before enrolling (C(--wipe-slot)).
    type: str
author:
  - Project Potos (@projectpotos)
"""

EXAMPLES = r"""
- name: Rotate to a random passphrase
  projectpotos.base.luks:
    action: change_key
    passphrase: "{{ iso_default_passphrase }}"
    generate: true
  register: rotated
  no_log: true

- name: Enroll the TPM2 as an unlock method
  projectpotos.base.luks:
    action: enroll_tpm2
    passphrase: "{{ rotated.passphrase }}"
    wipe_slots: tpm2
    tpm2_device: auto
    tpm2_pcrs:
      - "7"
      - "15:sha256=0000000000000000000000000000000000000000000000000000000000000000"
    tpm2_public_key_pcrs: ["11"]
    tpm2_public_key: "/etc/secureboot/pcr-initrd.pub.pem"
"""

RETURN = r"""
device:
  description: The resolved LUKS device path.
  type: str
  returned: always
encrypted:
  description: Whether an active LUKS device was found.
  type: bool
  returned: always
passphrase:
  description: The new passphrase (O(action=change_key)).
  type: str
  returned: when action=change_key
"""

import os
import secrets
import string

from ansible.module_utils.basic import AnsibleModule


_PASSPHRASE_CHOICES = string.ascii_letters + string.digits + string.punctuation


def parse_crypttab(content: str) -> list[dict[str, str]]:
    """Parse crypttab file content"""
    entries: list[dict[str, str]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        if len(fields) < 2:
            continue
        entries.append({"name": fields[0], "source": fields[1]})
    return entries


def crypttab_source_to_device(source: str) -> str:
    """Map a UUID from crypttab to a device path.

    e.g. ``UUID=xxx`` becomes ``/dev/disk/by-uuid/xxx``
    """
    if source.upper().startswith("UUID="):
        return "/dev/disk/by-uuid/" + source.split("=", 1)[1]
    return source


def build_test_passphrase_argv(cryptsetup: str, device: str) -> list[str]:
    """Build the argv that tests a passphrase against a device."""
    return [cryptsetup, "luksOpen", "--test-passphrase", "--key-file=-", device]


def build_change_key_argv(cryptsetup: str, device: str) -> list[str]:
    """Build the ``luksChangeKey`` argv."""
    return [cryptsetup, "luksChangeKey", device, "-q"]


def build_change_key_stdin(old: str, new: str) -> str:
    """Build stdin for luksChangeKey."""
    return f"{old}\n{new}\n"


def generate_passphrase(length: int) -> str:
    """Generate a random passphrase."""
    return "".join(secrets.choice(_PASSPHRASE_CHOICES) for _i in range(length))


def format_pcr_list(pcrs: list[object] | None) -> str:
    """Join PCR identifiers with '+'."""
    if not pcrs:
        return ""
    return "+".join(str(pcr) for pcr in pcrs)


def build_cryptenroll_argv(
    cryptenroll: str,
    device: str,
    *,
    tpm2_device: str,
    tpm2_pcrs: list[object] | None,
    public_key: str | None,
    public_key_pcrs: list[object] | None,
    with_pin: bool,
    wipe_slots: str | None,
) -> list[str]:
    """Build the ``systemd-cryptenroll`` argv."""
    argv = [cryptenroll]
    if wipe_slots:
        argv.append(f"--wipe-slot={wipe_slots}")
    argv.append(f"--tpm2-device={tpm2_device or 'auto'}")
    pcrs = format_pcr_list(tpm2_pcrs)
    if pcrs:
        argv.append(f"--tpm2-pcrs={pcrs}")
    if public_key:
        argv.append(f"--tpm2-public-key={public_key}")
        pk_pcrs = format_pcr_list(public_key_pcrs)
        if pk_pcrs:
            argv.append(f"--tpm2-public-key-pcrs={pk_pcrs}")
    if with_pin:
        argv.append("--tpm2-with-pin=yes")
    argv.append(device)
    return argv


def _resolve_device(module: AnsibleModule) -> str:
    """Resolve the LUKS device from params or crypttab."""
    if module.params["device"]:
        return module.params["device"]
    crypttab = module.params["crypttab"]
    if not os.path.exists(crypttab):
        return ""
    with open(crypttab, encoding="utf-8") as f:
        entries = parse_crypttab(f.read())
    if not entries:
        return ""
    device = crypttab_source_to_device(entries[0]["source"])
    return os.path.realpath(device) if os.path.exists(device) else device


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "action": {
                "type": "str",
                "required": True,
                "choices": ["discover", "change_key", "enroll_tpm2"],
            },
            "device": {"type": "str"},
            "passphrase": {"type": "str", "no_log": True},
            "new_passphrase": {"type": "str", "no_log": True},
            "generate": {"type": "bool", "default": False},
            "length": {"type": "int", "default": 64},
            "crypttab": {"type": "str", "default": "/etc/crypttab"},
            "tpm2_device": {"type": "str", "default": "auto"},
            "tpm2_pcrs": {"type": "list", "elements": "str", "default": []},
            "tpm2_public_key": {"type": "str"},
            "tpm2_public_key_pcrs": {"type": "list", "elements": "str", "default": ["11"]},
            "tpm2_with_pin": {"type": "bool", "default": False},
            "pin": {"type": "str", "no_log": True},
            "wipe_slots": {"type": "str"},
        },
        required_if=[
            ["action", "change_key", ["passphrase"]],
            ["action", "enroll_tpm2", ["passphrase"]],
        ],
        mutually_exclusive=[["new_passphrase", "generate"]],
        supports_check_mode=False,
    )

    device = _resolve_device(module)

    if module.params["action"] == "discover":
        module.exit_json(
            changed=False, device=device, encrypted=bool(device) and os.path.exists(device)
        )

    # change_key and enroll_tpm2 both require a device.
    if not device:
        module.fail_json(
            msg="No LUKS device found; pass 'device' explicitly or check that /etc/crypttab exists."
        )

    if module.params["action"] == "enroll_tpm2":
        cryptenroll = module.get_bin_path("systemd-cryptenroll", required=True)
        argv = build_cryptenroll_argv(
            cryptenroll,
            device,
            tpm2_device=module.params["tpm2_device"],
            tpm2_pcrs=module.params["tpm2_pcrs"],
            public_key=module.params["tpm2_public_key"],
            public_key_pcrs=module.params["tpm2_public_key_pcrs"],
            with_pin=module.params["tpm2_with_pin"],
            wipe_slots=module.params["wipe_slots"],
        )
        env = dict(os.environ)
        env["PASSWORD"] = module.params["passphrase"]
        if module.params["tpm2_with_pin"] and module.params["pin"]:
            env["NEWPIN"] = module.params["pin"]
        rc, _out, err = module.run_command(argv, environ_update=env)
        if rc != 0:
            module.fail_json(msg=f"systemd-cryptenroll failed for {device}: {err.strip()}")
        module.exit_json(changed=True, device=device)

    # action == change_key
    if module.params["generate"]:
        new_passphrase = generate_passphrase(module.params["length"])
    elif module.params["new_passphrase"]:
        new_passphrase = module.params["new_passphrase"]
    else:
        module.fail_json(msg="change_key requires 'new_passphrase' or generate=true.")

    cryptsetup = module.get_bin_path("cryptsetup", required=True)
    old = module.params["passphrase"]

    # check if old passphrase is correct
    rc, _out, err = module.run_command(
        build_test_passphrase_argv(cryptsetup, device), data=old, binary_data=True
    )
    if rc != 0:
        module.fail_json(msg=f"Current LUKS passphrase is incorrect for {device}: {err.strip()}")

    rc, _out, err = module.run_command(
        build_change_key_argv(cryptsetup, device),
        data=build_change_key_stdin(old, new_passphrase),
        binary_data=True,
    )
    if rc != 0:
        module.fail_json(msg=f"luksChangeKey failed for {device}: {err.strip()}")

    module.exit_json(changed=True, device=device, encrypted=True, passphrase=new_passphrase)


if __name__ == "__main__":
    main()
