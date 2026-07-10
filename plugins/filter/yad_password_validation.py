# Copyright: (c) 2026, Potos Project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Build a yad ``validations`` list from a password policy.

This ansible filter plugin is a helper for potos roles, to validate passwords from interactive user inputs.
Password policies can be expressed in human terms, and this filter will translate them to regex rules.
If a password doesn't meet the requirements, the filter will provide a human readable error message.

Policy options:
  min_length       int  minimum number of characters
  max_length       int  maximum number of characters
  min_uppercase    int  minimum count of A-Z characters
  min_lowercase    int  minimum count of a-z characters
  min_digits       int  minimum count of 0-9 characters
  min_special      int  minimum count of characters from ``special_chars``
  special_chars    str  the set that counts as "special"
  forbidden_chars  str  characters that must not appear at all
  regex            str  an extra regex rule
  regex_message    str  error message for the ``regex`` rule
"""

from __future__ import annotations

import re
from typing import Any


DOCUMENTATION = r"""
---
name: yad_password_validation
short_description: Build yad dialog validations from a password policy
version_added: "0.1.0"
description:
  - Translates a human-readable password policy into a list of validation
    rules for the M(projectpotos.base.yad) module.
  - Each policy option is turned into a rule with a human-readable error
    message.
positional: password_field, confirm_field
options:
  _input:
    description: The password policy. An empty or omitted policy yields only the C(required) rule.
    type: dict
    required: true
    suboptions:
      min_length:
        description: Minimum number of characters.
        type: int
      max_length:
        description: Maximum number of characters.
        type: int
      min_uppercase:
        description: Minimum count of C(A-Z) characters.
        type: int
      min_lowercase:
        description: Minimum count of C(a-z) characters.
        type: int
      min_digits:
        description: Minimum count of C(0-9) characters.
        type: int
      min_special:
        description: Minimum count of characters from O(_input.special_chars).
        type: int
      special_chars:
        description: The set of characters that counts as "special".
        type: str
        default: "!@#$%^&*()-_=+[]{};:,.<>?/~"
      forbidden_chars:
        description: Characters that must not appear at all.
        type: str
      regex:
        description: An extra regex rule the password must match.
        type: str
      regex_message:
        description: Error message for the O(_input.regex) rule.
        type: str
        default: The password does not meet the policy requirements.
  password_field:
    description: Name of the dialog field holding the password.
    type: str
    required: true
  confirm_field:
    description: Name of the confirmation field. When set, a C(match) rule against O(password_field) is added.
    type: str
author:
  - Project Potos (@projectpotos)
"""

EXAMPLES = r"""
- name: Ask for a password enforcing policy
  vars:
    password_policy:
      min_length: 12
      min_uppercase: 1
      min_digits: 1
      min_special: 1
      forbidden_chars: " "
  projectpotos.base.yad:
    fields:
      - {label: "Password", type: password}
      - {label: "Confirm password", type: password}
    validations: >-
      {{ password_policy
         | projectpotos.base.yad_password_validation('Password', 'Confirm password') }}
"""

RETURN = r"""
_value:
  description: Validation rules for the M(projectpotos.base.yad) module. Each rule has C(type), C(field), C(error_message), and type-specific keys.
  type: list
  elements: dict
"""


_DEFAULT_REQUIRED_MSG = "A password is required."
_DEFAULT_MATCH_MSG = "The passwords did not match. Please try again."
_DEFAULT_REGEX_MSG = "The password does not meet the policy requirements."

# A sensible default set of "special" characters.
DEFAULT_SPECIAL_CHARS = "!@#$%^&*()-_=+[]{};:,.<>?/~"


def _plural(n: int) -> str:
    """Veeeery simple pluralization."""
    return "" if n == 1 else "s"


def _regex_escape(chars: str) -> str:
    """Make sure to escape any special regex chars."""
    return "".join(re.escape(c) for c in chars)


def _count_rule(field: str, count: int, class_body: str, message: str) -> dict[str, Any]:
    """Build a regex validation requiring at least ``count`` members of a class."""
    pattern = f"^(?=(?:[^{class_body}]*[{class_body}]){{{count}}})"
    return {
        "type": "regex",
        "field": field,
        "pattern": pattern,
        "error_message": message,
    }


def yad_password_validation(
    policy: dict[str, Any] | None,
    password_field: str,
    confirm_field: str | None = None,
) -> list[dict[str, Any]]:
    """Return yad validations enforcing ``policy`` on ``password_field``."""
    policy = policy or {}
    validations: list[dict[str, Any]] = [
        {"type": "required", "field": password_field, "error_message": _DEFAULT_REQUIRED_MSG},
    ]

    if confirm_field:
        validations.append(
            {
                "type": "match",
                "field": password_field,
                "match": confirm_field,
                "error_message": _DEFAULT_MATCH_MSG,
            }
        )

    min_length = policy.get("min_length")
    max_length = policy.get("max_length")
    if min_length is not None or max_length is not None:
        rule: dict[str, Any] = {"type": "length", "field": password_field}
        bounds = []
        if min_length is not None:
            rule["min"] = min_length
            bounds.append(f"at least {min_length}")
        if max_length is not None:
            rule["max"] = max_length
            bounds.append(f"at most {max_length}")
        rule["error_message"] = f"The password must be {' and '.join(bounds)} characters long."
        validations.append(rule)

    min_upper = policy.get("min_uppercase")
    if min_upper:
        validations.append(
            _count_rule(
                password_field,
                min_upper,
                "A-Z",
                f"The password must contain at least {min_upper} uppercase letter{_plural(min_upper)}.",
            )
        )

    min_lower = policy.get("min_lowercase")
    if min_lower:
        validations.append(
            _count_rule(
                password_field,
                min_lower,
                "a-z",
                f"The password must contain at least {min_lower} lowercase letter{_plural(min_lower)}.",
            )
        )

    min_digits = policy.get("min_digits")
    if min_digits:
        validations.append(
            _count_rule(
                password_field,
                min_digits,
                "0-9",
                f"The password must contain at least {min_digits} digit{_plural(min_digits)}.",
            )
        )

    min_special = policy.get("min_special")
    if min_special:
        special_chars = policy.get("special_chars") or DEFAULT_SPECIAL_CHARS
        validations.append(
            _count_rule(
                password_field,
                min_special,
                _regex_escape(special_chars),
                f"The password must contain at least {min_special} "
                f"special character{_plural(min_special)} ({special_chars}).",
            )
        )

    forbidden = policy.get("forbidden_chars")
    if forbidden:
        validations.append(
            {
                "type": "regex",
                "field": password_field,
                "pattern": f"^[^{_regex_escape(forbidden)}]*$",
                "error_message": (
                    f"The password must not contain any of these characters: {forbidden}"
                ),
            }
        )

    regex = policy.get("regex")
    if regex:
        validations.append(
            {
                "type": "regex",
                "field": password_field,
                "pattern": regex,
                "error_message": policy.get("regex_message") or _DEFAULT_REGEX_MSG,
            }
        )

    return validations


class FilterModule:
    """Ansible filter plugin entry point."""

    def filters(self) -> dict[str, Any]:
        return {"yad_password_validation": yad_password_validation}
