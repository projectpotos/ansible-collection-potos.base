# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ``potos.base.yad_password_validation`` filter."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path


_MODULE_PATH = (
    Path(__file__).resolve().parents[4] / "plugins" / "filter" / "yad_password_validation.py"
)
_spec = importlib.util.spec_from_file_location("yad_password_under_test", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

build = mod.yad_password_validation


def _rule_for(out, message_substr):
    """Return the (single) validation whose error message contains a substring."""
    matches = [v for v in out if message_substr in v.get("error_message", "")]
    assert len(matches) == 1, f"expected exactly one rule mentioning {message_substr!r}"
    return matches[0]


def _passes(rule, value):
    """Mirror the yad module's regex check: validation passes when re.search hits."""
    return re.search(rule["pattern"], value) is not None


def test_minimal_policy_emits_required_and_match() -> None:
    out = build({}, "Password", "Confirm password")
    assert [v["type"] for v in out] == ["required", "match"]
    assert out[0]["field"] == "Password"
    assert out[1]["match"] == "Confirm password"


def test_no_confirm_field_omits_match() -> None:
    out = build(None, "Password")
    assert [v["type"] for v in out] == ["required"]


def test_min_length_emits_length_validation() -> None:
    out = build({"min_length": 8}, "Password", "Confirm password")
    length = next(v for v in out if v["type"] == "length")
    assert length["min"] == 8
    assert "max" not in length
    assert "at least 8" in length["error_message"]


def test_min_and_max_length() -> None:
    out = build({"min_length": 8, "max_length": 128}, "Password", "Confirm password")
    length = next(v for v in out if v["type"] == "length")
    assert length["min"] == 8
    assert length["max"] == 128
    assert "at least 8" in length["error_message"]
    assert "at most 128" in length["error_message"]


def test_regex_uses_custom_message_when_given() -> None:
    out = build(
        {"regex": "(?=.*[0-9])", "regex_message": "Need a digit."},
        "Password",
        "Confirm password",
    )
    rgx = next(v for v in out if v["type"] == "regex")
    assert rgx["pattern"] == "(?=.*[0-9])"
    assert rgx["error_message"] == "Need a digit."


def test_regex_falls_back_to_default_message() -> None:
    out = build({"regex": "(?=.*[0-9])"}, "Password")
    rgx = next(v for v in out if v["type"] == "regex")
    assert rgx["error_message"]  # non-empty default


def test_full_policy_ordering() -> None:
    out = build(
        {"min_length": 10, "regex": "x"},
        "Password",
        "Confirm password",
    )
    assert [v["type"] for v in out] == ["required", "match", "length", "regex"]


def test_character_class_rules_ordering() -> None:
    out = build(
        {
            "min_length": 12,
            "min_uppercase": 1,
            "min_lowercase": 1,
            "min_digits": 1,
            "min_special": 1,
            "forbidden_chars": " ",
            "regex": "x",
        },
        "Password",
        "Confirm password",
    )
    # required, match, length, then the four class counts, forbidden, raw regex.
    assert [v["type"] for v in out] == [
        "required",
        "match",
        "length",
        "regex",  # uppercase
        "regex",  # lowercase
        "regex",  # digits
        "regex",  # special
        "regex",  # forbidden
        "regex",  # custom regex
    ]


def test_min_uppercase_pattern_accepts_and_rejects() -> None:
    rule = _rule_for(build({"min_uppercase": 2}, "Password"), "uppercase")
    assert _passes(rule, "aAbB")
    assert _passes(rule, "ABc")
    assert not _passes(rule, "Abc")
    assert not _passes(rule, "abc")


def test_min_digits_pattern_counts_correctly() -> None:
    rule = _rule_for(build({"min_digits": 3}, "Password"), "digit")
    assert _passes(rule, "a1b2c3")
    assert not _passes(rule, "a1b2")


def test_min_lowercase_pattern() -> None:
    rule = _rule_for(build({"min_lowercase": 1}, "Password"), "lowercase")
    assert _passes(rule, "ABCd")
    assert not _passes(rule, "ABC1")


def test_min_special_uses_default_set_and_counts() -> None:
    rule = _rule_for(build({"min_special": 2}, "Password"), "special")
    assert _passes(rule, "ab!@")
    assert not _passes(rule, "ab!")
    assert mod.DEFAULT_SPECIAL_CHARS in rule["error_message"]


def test_min_special_honors_custom_set_with_class_metacharacters() -> None:
    # A set containing regex class metacharacters (] ^ - \) must stay literal.
    rule = _rule_for(build({"min_special": 1, "special_chars": "]^-."}, "Password"), "special")
    assert _passes(rule, "abc-")
    assert _passes(rule, "abc]")
    assert _passes(rule, "abc^")
    assert _passes(rule, "abc.")
    assert not _passes(rule, "abcd")


def test_forbidden_chars_rejects_only_those_chars() -> None:
    rule = _rule_for(build({"forbidden_chars": " /"}, "Password"), "must not contain")
    assert _passes(rule, "safe-password")
    assert not _passes(rule, "has space")
    assert not _passes(rule, "has/slash")
    assert rule["error_message"].endswith(" /")


def test_pluralization_in_messages() -> None:
    one = _rule_for(build({"min_digits": 1}, "Password"), "digit")
    many = _rule_for(build({"min_digits": 3}, "Password"), "digit")
    assert "1 digit." in one["error_message"]
    assert "3 digits." in many["error_message"]


def test_zero_counts_are_ignored() -> None:
    out = build({"min_uppercase": 0, "min_digits": 0}, "Password")
    assert [v["type"] for v in out] == ["required"]
