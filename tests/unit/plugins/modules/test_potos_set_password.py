# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ``potos.base.potos_set_password`` module helpers."""

from __future__ import annotations

import importlib.util
import string
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[4] / "plugins" / "modules" / "potos_set_password.py"
_spec = importlib.util.spec_from_file_location("potos_set_password_under_test", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_argv_plaintext_has_no_encrypted_flag() -> None:
    assert mod.build_chpasswd_argv("/usr/sbin/chpasswd", False) == ["/usr/sbin/chpasswd"]


def test_argv_encrypted_adds_e_flag() -> None:
    assert mod.build_chpasswd_argv("/usr/sbin/chpasswd", True) == ["/usr/sbin/chpasswd", "-e"]


def test_stdin_is_user_colon_password_without_trailing_newline() -> None:
    # A trailing newline is read by some chpasswd versions as an empty second
    # record ("missing new password"), so it must be omitted.
    assert mod.build_chpasswd_stdin("operator", "s3cr3t") == "operator:s3cr3t"


def test_stdin_preserves_special_chars_in_password() -> None:
    # chpasswd splits on the first colon only, so colons in the password are fine.
    assert mod.build_chpasswd_stdin("op", "a:b#c$d") == "op:a:b#c$d"


def test_generate_password_length_and_charset() -> None:
    pw = mod.generate_password(32)
    assert len(pw) == 32
    assert set(pw) <= set(string.ascii_letters + string.digits + string.punctuation)


def test_generate_password_is_random() -> None:
    assert mod.generate_password(24) != mod.generate_password(24)
