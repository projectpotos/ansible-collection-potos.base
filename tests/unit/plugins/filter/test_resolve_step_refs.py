# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ``projectpotos.base.resolve_step_refs`` filter."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from ansible.errors import AnsibleFilterError


_MODULE_PATH = Path(__file__).resolve().parents[4] / "plugins" / "filter" / "resolve_step_refs.py"
_spec = importlib.util.spec_from_file_location("potos_base_resolve_under_test", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

resolve = mod.resolve_step_refs

STEPS = {
    "set_hostname": {"hostname": "client01"},
    "luks_random": {"passphrase": "s3cr3t"},
}


def test_resolves_a_reference() -> None:
    assert resolve("{{ steps.set_hostname.hostname }}", STEPS) == "client01"


def test_resolves_ansible_facts_reference() -> None:
    out = resolve(
        "kv/data/luks/{{ ansible_facts['machine_id'] }}",
        STEPS,
        {"machine_id": "abc123"},
    )
    assert out == "kv/data/luks/abc123"


def test_undefined_fact_raises() -> None:
    with pytest.raises(AnsibleFilterError):
        resolve("{{ ansible_facts['machine_id'] }}", STEPS, {})


def test_resolves_reference_inside_surrounding_text() -> None:
    out = resolve("host={{ steps.set_hostname.hostname }}\n", STEPS)
    assert out == "host=client01\n"


def test_passes_plain_strings_through_unchanged() -> None:
    assert resolve("/etc/motd", STEPS) == "/etc/motd"


def test_preserves_non_string_scalar_types() -> None:
    assert resolve(420, STEPS) == 420
    assert resolve(True, STEPS) is True


def test_recurses_into_dicts_and_lists() -> None:
    spec = {
        "path": "/etc/motd",
        "content": "{{ steps.set_hostname.hostname }}",
        "args": ["--pass", "{{ steps.luks_random.passphrase }}"],
    }
    assert resolve(spec, STEPS) == {
        "path": "/etc/motd",
        "content": "client01",
        "args": ["--pass", "s3cr3t"],
    }


def test_supports_jinja_filters() -> None:
    assert resolve("{{ steps.set_hostname.hostname | upper }}", STEPS) == "CLIENT01"


def test_supports_ansible_filters() -> None:
    steps = {"bao_read": {"data": {"username": "client01", "enabled": True}}}
    out = resolve("{{ steps.bao_read.data | to_yaml }}", steps)
    assert "username: client01" in out
    assert "enabled: true" in out


def test_supports_ansible_filters_fqcn() -> None:
    steps = {"bao_read": {"data": {"username": "client01", "enabled": True}}}
    out = resolve("{{ steps.bao_read.data | ansible.builtin.to_yaml }}", steps)
    assert "username: client01" in out
    assert "enabled: true" in out


def test_undefined_reference_raises_clear_error() -> None:
    with pytest.raises(AnsibleFilterError):
        resolve("{{ steps.missing.field }}", STEPS)


def test_no_steps_argument_defaults_to_empty_registry() -> None:
    assert resolve("plain", None) == "plain"
