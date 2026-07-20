# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ``projectpotos.base.systemd_creds`` argv helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[4] / "plugins" / "modules" / "systemd_creds.py"
_spec = importlib.util.spec_from_file_location("systemd_creds_under_test", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_format_pcr_list_joins_with_plus() -> None:
    assert mod.format_pcr_list([7, 11, 14]) == "7+11+14"


def test_format_pcr_list_empty_is_empty_string() -> None:
    assert mod.format_pcr_list([]) == ""
    assert mod.format_pcr_list(None) == ""


def test_encrypt_argv_minimal_auto_key() -> None:
    argv = mod.build_encrypt_argv(
        "systemd-creds",
        name="tok",
        with_key="auto",
        tpm2_pcrs=[],
        public_key=None,
        public_key_pcrs=["11"],
        tpm2_device=None,
        input_path="-",
        output_path="/etc/potos/x.cred",
    )
    assert argv == [
        "systemd-creds",
        "encrypt",
        "--name=tok",
        "--with-key=auto",
        "-",
        "/etc/potos/x.cred",
    ]


def test_encrypt_argv_no_public_key_pcrs_without_public_key() -> None:
    # public_key_pcrs must not appear unless a public key is given.
    argv = mod.build_encrypt_argv(
        "systemd-creds",
        name=None,
        with_key="host",
        tpm2_pcrs=[],
        public_key=None,
        public_key_pcrs=["11"],
        tpm2_device=None,
    )
    assert not any(a.startswith("--tpm2-public-key-pcrs") for a in argv)


def test_encrypt_argv_full_tpm_binding() -> None:
    argv = mod.build_encrypt_argv(
        "systemd-creds",
        name="luks",
        with_key="host+tpm2-with-public-key",
        tpm2_pcrs=[7, 14],
        public_key="/etc/secureboot/pcr-system.pub.pem",
        public_key_pcrs=[11],
        tpm2_device="auto",
        input_path="-",
        output_path="/etc/potos/luks.cred",
    )
    assert argv == [
        "systemd-creds",
        "encrypt",
        "--name=luks",
        "--with-key=host+tpm2-with-public-key",
        "--tpm2-pcrs=7+14",
        "--tpm2-public-key=/etc/secureboot/pcr-system.pub.pem",
        "--tpm2-public-key-pcrs=11",
        "--tpm2-device=auto",
        "-",
        "/etc/potos/luks.cred",
    ]


def test_validate_rejects_public_key_with_non_pk_type() -> None:
    for with_key in ("host", "tpm2", "host+tpm2", "null", "auto-initrd"):
        error = mod.validate_key_binding(with_key, "/etc/secureboot/pcr-system.pub.pem")
        assert error is not None and "silently ignored" in error


def test_validate_rejects_pk_type_without_public_key() -> None:
    for with_key in sorted(mod.PUBLIC_KEY_TYPES):
        error = mod.validate_key_binding(with_key, None)
        assert error is not None and "requires tpm2_public_key" in error


def test_validate_accepts_valid_combinations() -> None:
    assert mod.validate_key_binding("host+tpm2-with-public-key", "/etc/pk.pem") is None
    assert mod.validate_key_binding("auto", "/etc/pk.pem") is None
    assert mod.validate_key_binding("auto", None) is None
    assert mod.validate_key_binding("host+tpm2", None) is None


def test_decrypt_argv_minimal() -> None:
    argv = mod.build_decrypt_argv(
        "systemd-creds",
        name="tok",
        tpm2_signature=None,
        tpm2_device=None,
        input_path="/etc/potos/x.cred",
    )
    assert argv == ["systemd-creds", "decrypt", "--name=tok", "/etc/potos/x.cred", "-"]


def test_decrypt_argv_with_signature() -> None:
    argv = mod.build_decrypt_argv(
        "systemd-creds",
        name=None,
        tpm2_signature="/run/sig.json",
        tpm2_device=None,
        input_path="/etc/potos/x.cred",
    )
    assert argv == [
        "systemd-creds",
        "decrypt",
        "--tpm2-signature=/run/sig.json",
        "/etc/potos/x.cred",
        "-",
    ]
