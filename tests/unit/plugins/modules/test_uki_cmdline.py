# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ``projectpotos.base.uki_cmdline`` helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[4] / "plugins" / "modules" / "uki_cmdline.py"
_spec = importlib.util.spec_from_file_location("uki_cmdline_under_test", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_pick_bls_entry_skips_rescue_and_sorts() -> None:
    paths = [
        "/boot/efi/loader/entries/zzz-later.conf",
        "/boot/efi/loader/entries/abc-rescue.conf",
        "/boot/efi/loader/entries/def-main.conf",
    ]
    assert mod.pick_bls_entry(paths) == "/boot/efi/loader/entries/def-main.conf"


def test_pick_bls_entry_none_when_only_rescue() -> None:
    assert mod.pick_bls_entry(["/x/1-rescue.conf"]) is None
    assert mod.pick_bls_entry([]) is None


def test_parse_bls_options_first_options_line() -> None:
    content = "title Fedora\nlinux /vmlinuz\noptions root=UUID=abc ro quiet\noptions ignored\n"
    assert mod.parse_bls_options(content) == "root=UUID=abc ro quiet"


def test_parse_bls_options_missing() -> None:
    assert mod.parse_bls_options("title Fedora\n") == ""


def test_build_cmdline_strips_installer_flags() -> None:
    src = (
        "root=UUID=abc ro rootflags=subvol=@ rd.live.check inst.stage2=hd:LABEL=F "
        "systemd.machine_id=0123 rd.shell=1 rd.emergency=poweroff rhgb quiet"
    )
    assert mod.build_cmdline(src, "") == (
        "root=UUID=abc ro rootflags=subvol=@ quiet rd.shell=0 rd.emergency=reboot"
    )


def test_build_cmdline_keeps_similar_prefixes() -> None:
    # only inst./rd.live./rd.shell flags are stripped.
    src = "rd.luks.uuid=luks-abc root=UUID=def ro installonce=1 rd.shellac=2"
    out = mod.build_cmdline(src, "")
    assert "rd.luks.uuid=luks-abc" in out
    assert "installonce=1" in out
    assert "rd.shellac=2" in out


def test_build_cmdline_appends_extra_tokens() -> None:
    assert mod.build_cmdline("root=UUID=abc ro", "audit=1 foo=bar").endswith("audit=1 foo=bar")


def test_strip_options_removes_installer_flags() -> None:
    src = "root=UUID=abc ro rd.live.check inst.stage2=hd:LABEL=F rhgb quiet"
    assert mod.strip_options(src) == "root=UUID=abc ro"


def test_build_cmdline_stable_for_stripped_base() -> None:
    # recomputing from the persisted base must be a no-op
    base = mod.strip_options("root=UUID=abc ro rd.live.check quiet")
    assert mod.build_cmdline(base, "audit=1") == mod.build_cmdline(base + " quiet", "audit=1")


def test_strip_options_keeps_lvm_tokens() -> None:
    # anaconda BLS options for an LVM (-on-LUKS) install
    src = (
        "root=/dev/mapper/fedora-root ro rd.lvm.lv=fedora/root rd.lvm.lv=fedora/swap "
        "resume=/dev/mapper/fedora-swap rd.luks.uuid=luks-1111-2222 rhgb quiet"
    )
    assert mod.strip_options(src) == (
        "root=/dev/mapper/fedora-root ro rd.lvm.lv=fedora/root rd.lvm.lv=fedora/swap "
        "resume=/dev/mapper/fedora-swap rd.luks.uuid=luks-1111-2222"
    )


def test_build_cmdline_lvm_entry_hardened() -> None:
    src = "root=/dev/mapper/vg-root ro rd.lvm.lv=vg/root inst.repo=cdrom rhgb quiet"
    assert mod.build_cmdline(src, "audit=1") == (
        "root=/dev/mapper/vg-root ro rd.lvm.lv=vg/root quiet rd.shell=0 rd.emergency=reboot audit=1"
    )
