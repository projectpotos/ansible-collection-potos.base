# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ``projectpotos.base.luks`` helpers."""

from __future__ import annotations

import importlib.util
import string
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[4] / "plugins" / "modules" / "luks.py"
_spec = importlib.util.spec_from_file_location("luks_under_test", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_parse_crypttab_skips_comments_and_blanks() -> None:
    content = """
    # a comment
    luks-root UUID=abc none luks

    luks-data /dev/sdb1 none luks
    """
    assert mod.parse_crypttab(content) == [
        {"name": "luks-root", "source": "UUID=abc"},
        {"name": "luks-data", "source": "/dev/sdb1"},
    ]


def test_parse_crypttab_ignores_incomplete_lines() -> None:
    assert mod.parse_crypttab("onlyname\n") == []


def test_source_to_device_uuid() -> None:
    assert mod.crypttab_source_to_device("UUID=abc-123") == "/dev/disk/by-uuid/abc-123"


def test_source_to_device_uuid_case_insensitive() -> None:
    assert mod.crypttab_source_to_device("uuid=abc") == "/dev/disk/by-uuid/abc"


def test_source_to_device_plain_path() -> None:
    assert mod.crypttab_source_to_device("/dev/sdb1") == "/dev/sdb1"


def test_test_passphrase_argv() -> None:
    assert mod.build_test_passphrase_argv("/sbin/cryptsetup", "/dev/sda3") == [
        "/sbin/cryptsetup",
        "luksOpen",
        "--test-passphrase",
        "--key-file=-",
        "/dev/sda3",
    ]


def test_change_key_argv() -> None:
    assert mod.build_change_key_argv("/sbin/cryptsetup", "/dev/sda3") == [
        "/sbin/cryptsetup",
        "luksChangeKey",
        "/dev/sda3",
        "-q",
    ]


def test_change_key_stdin_order_is_old_then_new() -> None:
    assert mod.build_change_key_stdin("oldpw", "newpw") == "oldpw\nnewpw\n"


def test_generate_passphrase_length_and_charset() -> None:
    pw = mod.generate_passphrase(64)
    assert len(pw) == 64
    assert set(pw) <= set(string.ascii_letters + string.digits + string.punctuation)


def test_generate_passphrase_is_random() -> None:
    assert mod.generate_passphrase(32) != mod.generate_passphrase(32)


def test_format_pcr_list() -> None:
    assert mod.format_pcr_list([7, 11]) == "7+11"
    assert mod.format_pcr_list([]) == ""
    assert mod.format_pcr_list(None) == ""


def test_cryptenroll_argv_minimal_defaults_tpm2_device_auto() -> None:
    argv = mod.build_cryptenroll_argv(
        "systemd-cryptenroll",
        "/dev/sda3",
        tpm2_device="auto",
        tpm2_pcrs=[],
        public_key=None,
        public_key_pcrs=["11"],
        with_pin=False,
        wipe_slots=None,
    )
    assert argv == ["systemd-cryptenroll", "--tpm2-device=auto", "/dev/sda3"]


def test_cryptenroll_argv_no_public_key_pcrs_without_public_key() -> None:
    argv = mod.build_cryptenroll_argv(
        "systemd-cryptenroll",
        "/dev/sda3",
        tpm2_device="auto",
        tpm2_pcrs=[],
        public_key=None,
        public_key_pcrs=["11"],
        with_pin=False,
        wipe_slots=None,
    )
    assert not any(a.startswith("--tpm2-public-key-pcrs") for a in argv)


def test_cryptenroll_argv_full_signed_policy_with_pin_and_wipe() -> None:
    argv = mod.build_cryptenroll_argv(
        "systemd-cryptenroll",
        "/dev/sda3",
        tpm2_device="auto",
        tpm2_pcrs=[7],
        public_key="/etc/secureboot/pcr-initrd.pub.pem",
        public_key_pcrs=[11],
        with_pin=True,
        wipe_slots="tpm2",
    )
    assert argv == [
        "systemd-cryptenroll",
        "--wipe-slot=tpm2",
        "--tpm2-device=auto",
        "--tpm2-pcrs=7",
        "--tpm2-public-key=/etc/secureboot/pcr-initrd.pub.pem",
        "--tpm2-public-key-pcrs=11",
        "--tpm2-with-pin=yes",
        "/dev/sda3",
    ]


def test_cryptenroll_argv_device_is_last() -> None:
    argv = mod.build_cryptenroll_argv(
        "systemd-cryptenroll",
        "/dev/mapper/luks-x",
        tpm2_device="auto",
        tpm2_pcrs=[7],
        public_key="/k.pem",
        public_key_pcrs=[11],
        with_pin=False,
        wipe_slots=None,
    )
    assert argv[-1] == "/dev/mapper/luks-x"
