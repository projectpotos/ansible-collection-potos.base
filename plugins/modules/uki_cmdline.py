#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Derive the kernel cmdline embedded into the signed UKI.

Seeds the base cmdline from the BLS loader entry anaconda left behind,
it strips all installer-only flags and hardens the initrd. The base is derived only
once (when converting a system to UKI) and persisted; the effective cmdline
is recomputed on every run, so a changed ``extra`` (e.g. from the specs repo)
is applied without re-deriving the base. When neither a persisted base nor a
usable BLS entry exists the module fails rather than guessing a cmdline from
the mounted root filesystem.
"""

from __future__ import annotations


DOCUMENTATION = r"""
---
module: uki_cmdline
short_description: Derive and persist the kernel cmdline embedded into the signed UKI
version_added: "0.3.0"
description:
  - Derives the base kernel cmdline for the UKI build once, persists it to
    O(base_dest) and writes the effective cmdline (base + hardening +
    O(extra)) to O(dest) on every run, so a changed O(extra) is applied while
    the derived base stays stable.
  - The base is seeded from the first non-rescue BLS entry under O(bls_dir)
    (the state anaconda leaves behind). The module fails when neither a
    persisted base nor a BLS entry with options exists.
  - Installer-only flags (C(rd.live.*), C(inst.*), C(systemd.machine_id=)) and
    rescue-shell flags are stripped; C(quiet rd.shell=0 rd.emergency=reboot)
    and O(extra) are appended.
options:
  dest:
    description: File the effective cmdline is written to.
    type: path
    default: /etc/kernel/cmdline
  base_dest:
    description: File the derived base cmdline is persisted to.
    type: path
    default: /var/lib/potos/uki-cmdline-base
  bls_dir:
    description: Directory holding the BLS loader entries.
    type: path
    default: /boot/efi/loader/entries
  extra:
    description: Extra tokens appended to the cmdline.
    type: str
    default: ""
author:
  - Project Potos (@projectpotos)
"""

EXAMPLES = r"""
- name: Derive and write the embedded kernel cmdline
  projectpotos.base.uki_cmdline:
    bls_dir: /boot/efi/loader/entries
    extra: "audit=1"
"""

RETURN = r"""
cmdline:
  description: The effective cmdline at O(dest).
  type: str
  returned: always
source:
  description: >-
    Where the base cmdline came from (V(base) for the persisted base file,
    V(bls) on first derivation).
  type: str
  returned: always
"""

import glob
import os
import re
import tempfile

from ansible.module_utils.basic import AnsibleModule


STRIP_PATTERN = re.compile(
    r"(rd\.live\..*|inst\..*|systemd\.machine_id=.*|rd\.shell=.*|rd\.emergency=.*|quiet|rhgb)$"
)
HARDENING_TOKENS = ["quiet", "rd.shell=0", "rd.emergency=reboot"]


def pick_bls_entry(paths: list[str]) -> str | None:
    """Return the first non-rescue BLS entry, sorted by name."""
    for path in sorted(paths):
        if "rescue" not in os.path.basename(path):
            return path
    return None


def parse_bls_options(content: str) -> str:
    """Extract the value of the first ``options`` line of a BLS entry."""
    for line in content.splitlines():
        if line.startswith("options "):
            return line[len("options ") :].strip()
    return ""


def strip_options(src_options: str) -> str:
    """Drop installer-only and rescue-shell flags from the source options."""
    return " ".join(tok for tok in src_options.split() if not STRIP_PATTERN.match(tok))


def build_cmdline(src_options: str, extra: str) -> str:
    """Strip installer-only flags, then harden and extend the cmdline."""
    return " ".join(strip_options(src_options).split() + HARDENING_TOKENS + extra.split())


def write_file(module: AnsibleModule, path: str, content: str) -> None:
    """Atomically write ``content`` to ``path`` with mode 0644."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content + "\n")
    module.atomic_move(tmp, path)
    module.set_mode_if_different(path, "0644", changed=True)


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "dest": {"type": "path", "default": "/etc/kernel/cmdline"},
            "base_dest": {"type": "path", "default": "/var/lib/potos/uki-cmdline-base"},
            "bls_dir": {"type": "path", "default": "/boot/efi/loader/entries"},
            "extra": {"type": "str", "default": ""},
        },
        supports_check_mode=True,
    )
    dest = module.params["dest"]
    base_dest = module.params["base_dest"]

    if os.path.exists(base_dest):
        with open(base_dest, encoding="utf-8") as f:
            base = f.read().strip()
        source = "base"
    else:
        entry = pick_bls_entry(glob.glob(os.path.join(module.params["bls_dir"], "*.conf")))
        base = ""
        if entry:
            with open(entry, encoding="utf-8") as f:
                base = parse_bls_options(f.read())
        if not base:
            module.fail_json(
                msg=(
                    f"No BLS entry with options found under {module.params['bls_dir']} "
                    f"and no persisted base at {base_dest}; cannot derive the UKI cmdline."
                )
            )
        source = "bls"

        base = strip_options(base)
        if not module.check_mode:
            write_file(module, base_dest, base)

    cmdline = build_cmdline(base, module.params["extra"])

    existing = None
    if os.path.exists(dest):
        with open(dest, encoding="utf-8") as f:
            existing = f.read().strip()

    changed = existing != cmdline or source == "bls"
    if changed and not module.check_mode:
        write_file(module, dest, cmdline)

    module.exit_json(changed=changed, cmdline=cmdline, source=source)


if __name__ == "__main__":
    main()
