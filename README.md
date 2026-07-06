# Potos Base Collection

This repository contains the `potos.base` Ansible Collection.

<!--start requires_ansible-->
## Ansible version compatibility

This collection has been tested against the following Ansible versions: **>=2.15.0**.

Plugins and modules within a collection may be tested with only specific Ansible versions.
A collection may contain metadata that identifies these versions.
PEP440 is the schema used to describe the versions of Ansible.
<!--end requires_ansible-->

## External requirements

Some modules and plugins require external libraries. Please check the
requirements for each plugin or module you use in the documentation to find out
which requirements are needed.

## Included content

<!--start collection content-->
### Resolve_step_refs filter plugins
Ansible filter plugin entry point.

Name | Description
--- | ---
potos.base.resolve_step_refs|Render ``{{ steps.* }}`` and ``{{ ansible_facts.* }}`` refs in ``value``.

### Yad_password_validation filter plugins
Ansible filter plugin entry point.

Name | Description
--- | ---
potos.base.yad_password_validation|Return yad validations enforcing ``policy`` on ``password_field``.

### Modules
Name | Description
--- | ---
[potos.base.potos_luks](https://github.com/projectpotos/ansible-collection-potos.base/blob/main/docs/potos.base.potos_luks_module.rst)|Do various LUKS operations
[potos.base.potos_openbao](https://github.com/projectpotos/ansible-collection-potos.base/blob/main/docs/potos.base.potos_openbao_module.rst)|Interact with OpenBao KV engine
[potos.base.potos_set_password](https://github.com/projectpotos/ansible-collection-potos.base/blob/main/docs/potos.base.potos_set_password_module.rst)|Set a local user's password using chpasswd
[potos.base.potos_systemd_creds](https://github.com/projectpotos/ansible-collection-potos.base/blob/main/docs/potos.base.potos_systemd_creds_module.rst)|Encrypt or decrypt a secret with systemd-creds
[potos.base.yad](https://github.com/projectpotos/ansible-collection-potos.base/blob/main/docs/potos.base.yad_module.rst)|Display a YAD (GTK) dialog and return the user's input

<!--end collection content-->

## Using this collection

```bash
    ansible-galaxy collection install potos.base
```

You can also include it in a `requirements.yml` file and install it via
`ansible-galaxy collection install -r requirements.yml` using the format:

```yaml
collections:
  - name: potos.base
```

To upgrade the collection to the latest available version, run the following
command:

```bash
ansible-galaxy collection install potos.base --upgrade
```

You can also install a specific version of the collection, for example, if you
need to downgrade when something is broken in the latest version (please report
an issue in this repository). Use the following syntax where `X.Y.Z` can be any
[available version](https://galaxy.ansible.com/potos/base):

```bash
ansible-galaxy collection install potos.base:==X.Y.Z
```

See
[Ansible Using Collections](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html)
for more details.

## Release notes

See the
[changelog](https://github.com/ansible-collections/potos.base/tree/main/CHANGELOG.rst).

## Roadmap

<!-- Optional. Include the roadmap for this collection, and the proposed release/versioning strategy so users can anticipate the upgrade/update cycle. -->

## More information

<!-- List out where the user can find additional information, such as working group meeting times, slack/matrix channels, or documentation for the product this collection automates. At a minimum, link to: -->

- [Ansible collection development forum](https://forum.ansible.com/c/project/collection-development/27)
- [Ansible User guide](https://docs.ansible.com/ansible/devel/user_guide/index.html)
- [Ansible Developer guide](https://docs.ansible.com/ansible/devel/dev_guide/index.html)
- [Ansible Collections Checklist](https://docs.ansible.com/ansible/devel/community/collection_contributors/collection_requirements.html)
- [Ansible Community code of conduct](https://docs.ansible.com/ansible/devel/community/code_of_conduct.html)
- [The Bullhorn (the Ansible Contributor newsletter)](https://docs.ansible.com/ansible/devel/community/communication.html#the-bullhorn)
- [News for Maintainers](https://forum.ansible.com/tag/news-for-maintainers)

## Licensing

GNU General Public License v3.0 or later.

See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.txt) to see the full text.
