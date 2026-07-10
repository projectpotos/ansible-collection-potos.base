===================================
Potos Base Collection Release Notes
===================================

.. contents:: Topics

v0.1.0
======

Minor Changes
-------------

- Added `DOCUMENTATION`, `EXAMPLES` and `RETURN` to the `resolve_step_refs` and `yad_password_validation` filter plugins.
- Added `stderr` to the outputs of the `script/run` step, allowing scripts to return error messages.
- Introduced the ``steps`` role, a declarative, ordered step framework whose steps can consume each other's outputs.
- Reworked the ``firstboot`` role to use the new step framework instead of hard-coded task files.

Breaking Changes / Porting Guide
--------------------------------

- All filenames, paths and systemd units installed by the ``basics`` role now use literal ``potos`` instead of the short client name - ``/var/lib/potos``, ``/var/log/potos``, ``potos_inventory``, ``/usr/local/bin/potos-ansible-pull``, ``potos-ansible-pull@.service``, ``potos-ansible-pull-<runtype>.timer``, ``/etc/logrotate.d/potos-ansible-pull`` and ``/var/lock/potos.lock``. ``basics_client_name`` is a display label only (unit descriptions, dialog titles, notifications).
- Removed the undocumented ``potos_plays_client_short_name`` fallback from ``basics_client_name`` and ``firstboot_client_name``. Both default to ``potos`` and are overridden at run time by ``client_name.short`` from the system config; use ``role_vars`` or the role variables directly for overrides.
- Renamed all role variables to match the new role names, e.g. ``potos_basics_*`` becomes ``basics_*``, ``potos_firstboot_*`` becomes ``firstboot_*`` and ``potos_steps_*`` becomes ``steps_*``.
- Renamed the modules ``potos_luks``, ``potos_openbao``, ``potos_set_password`` and ``potos_systemd_creds`` to ``luks``, ``openbao``, ``set_password`` and ``systemd_creds``.
- Renamed the roles ``potos_basics``, ``potos_firstboot`` and ``potos_steps`` to ``basics``, ``firstboot`` and ``steps``.
- The collection namespace changed from ``potos`` to ``projectpotos``. All content must now be referenced as ``projectpotos.base.*``.

Bugfixes
--------

- The ``firstboot`` role now applies ``client_name.short`` from the system config (``/etc/potos/config.yml``) to ``firstboot_client_name``, so firstboot dialogs are labelled with the configured client name instead of always showing ``potos``.
- The ``potos-ansible-pull`` wrapper no longer greps the accumulated ``ansible-pull.log`` for ``failed=`` recap lines to detect failures. The log is appended across runs and only rotated weekly, so a single failed run caused every following successful run to broadcast a failure notification until rotation. The playbook exit code is now the sole failure signal. This is subject to change if we ever switch to a log file per run.
- The copy button shown by the ``openbao/login`` step doesn't crash anymore.

New Plugins
-----------

Filter
~~~~~~

- resolve_step_refs - Resolve step output and fact references in step inputs
- yad_password_validation - Build yad dialog validations from a password policy

New Modules
-----------

- luks - Do various LUKS operations
- openbao - Interact with OpenBao KV engine
- set_password - Set a local user's password using chpasswd
- systemd_creds - Encrypt or decrypt a secret with systemd\-creds
- yad - Display a YAD (GTK) dialog and return the user's input
