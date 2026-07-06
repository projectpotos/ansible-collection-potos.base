# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Resolve ``{{ steps.<id>.<field> }}`` references.

This filter module is a helper to resolve the templated outputs from  ``potos_steps``.
It builds a new jinja2 environment, exposing all step outputs and combines them
with ansible facts. It also exposes all of ansible's builtin filters, so that
they can be used in the step inputs.

"""

from __future__ import annotations

from typing import Any

from ansible.errors import AnsibleFilterError
from ansible.plugins.loader import filter_loader, test_loader
from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import TemplateError


_MARKERS = ("{{", "{%")

# Cache of Ansible's filter plugins
_ANSIBLE_FILTERS: dict[str, Any] | None = None
_ANSIBLE_TESTS: dict[str, Any] | None = None


def _ansible_extras() -> tuple[dict[str, Any], dict[str, Any]]:
    """Collect Ansible's Jinja filters and tests, e.g. ``to_yaml``/``combine``.

    We need to expose them to our custom jinja environment.
    """
    global _ANSIBLE_FILTERS, _ANSIBLE_TESTS
    if _ANSIBLE_FILTERS is None or _ANSIBLE_TESTS is None:
        _ANSIBLE_FILTERS = _collect(filter_loader)
        _ANSIBLE_TESTS = _collect(test_loader)
    return _ANSIBLE_FILTERS, _ANSIBLE_TESTS


def _collect(loader: Any) -> dict[str, Any]:
    """Map both short and fully-qualified plugin names."""
    collected: dict[str, Any] = {}
    for plugin in loader.all():
        func = plugin.j2_function
        collected[plugin.ansible_name] = func
        # TODO: remove if ansible ever only supports FQCNs.
        collected[plugin.ansible_name.rpartition(".")[2]] = func
    return collected


def _render(value: Any, env: Environment, ctx: dict[str, Any]) -> Any:
    """Recursively render strings in ``value``"""
    if isinstance(value, str):
        if not any(marker in value for marker in _MARKERS):
            return value
        try:
            return env.from_string(str(value)).render(**ctx)
        except TemplateError as exc:
            raise AnsibleFilterError(
                f"resolve_step_refs: failed to resolve {value!r}: {exc}"
            ) from exc
    if isinstance(value, list):
        return [_render(item, env, ctx) for item in value]
    if isinstance(value, dict):
        return {key: _render(item, env, ctx) for key, item in value.items()}
    return value


def resolve_step_refs(
    value: Any,
    steps: dict[str, Any] | None = None,
    ansible_facts: dict[str, Any] | None = None,
) -> Any:
    """Render ``{{ steps.* }}`` and ``{{ ansible_facts.* }}`` refs in ``value``."""
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    filters, tests = _ansible_extras()
    env.filters.update(filters)
    env.tests.update(tests)
    ctx = {"steps": steps or {}, "ansible_facts": ansible_facts or {}}
    return _render(value, env, ctx)


class FilterModule:
    """Ansible filter plugin entry point."""

    def filters(self) -> dict[str, Any]:
        return {"resolve_step_refs": resolve_step_refs}
