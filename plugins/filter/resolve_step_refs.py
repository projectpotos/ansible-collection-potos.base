# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Resolve ``{{ steps.<id>.<field> }}`` references.

This filter module is a helper to resolve the templated outputs from  ``steps``.
It builds a new jinja2 environment, exposing all step outputs and combines them
with ansible facts. It also exposes all of ansible's builtin filters, so that
they can be used in the step inputs.

"""

from __future__ import annotations

from typing import Any


DOCUMENTATION = r"""
---
name: resolve_step_refs
short_description: Resolve step output and fact references in step inputs
version_added: "0.1.0"
description:
  - Recursively renders Jinja2 expressions in the input, exposing the outputs
    of previously run steps as C(steps.<id>.<field>) and the host facts as
    C(ansible_facts.*).
  - Strings without Jinja2 markers, and non-string values, are returned
    unchanged. Lists and dictionaries are traversed recursively.
  - Ansible's builtin filters and tests are available inside the rendered
    expressions.
  - Undefined references raise an error instead of rendering empty strings.
  - "Note: This module is highly specific for the potos steps role. You probably don't need it in any other context."
positional: steps, ansible_facts
options:
  _input:
    description: Value to render. Usually a step's C(input) dictionary.
    type: raw
    required: true
  steps:
    description: Mapping of step id to that step's registered outputs.
    type: dict
  ansible_facts:
    description: The host's C(ansible_facts) to expose during rendering.
    type: dict
author:
  - Project Potos (@projectpotos)
"""

EXAMPLES = r"""
- name: Resolve references in the step input
  ansible.builtin.set_fact:
    step_input: >-
      {{ step.input | default({})
         | projectpotos.base.resolve_step_refs(steps, ansible_facts) }}

- name: Evaluate a step's when condition
  ansible.builtin.set_fact:
    step_run: >-
      {{ (step.when | default(true) | string)
         | projectpotos.base.resolve_step_refs(steps, ansible_facts) | bool }}
"""

RETURN = r"""
_value:
  description: The input with all C(steps.*) and C(ansible_facts.*) references rendered.
  type: raw
"""

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
