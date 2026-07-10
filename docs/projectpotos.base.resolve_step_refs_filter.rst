.. _projectpotos.base.resolve_step_refs_filter:


***********************************
projectpotos.base.resolve_step_refs
***********************************

**Resolve step output and fact references in step inputs**


Version added: 0.1.0

.. contents::
   :local:
   :depth: 1


Synopsis
--------
- Recursively renders Jinja2 expressions in the input, exposing the outputs of previously run steps as ``steps.<id>.<field>`` and the host facts as ``ansible_facts.*``.
- Strings without Jinja2 markers, and non-string values, are returned unchanged. Lists and dictionaries are traversed recursively.
- Ansible's builtin filters and tests are available inside the rendered expressions.
- Undefined references raise an error instead of rendering empty strings.
- Note: This module is highly specific for the potos steps role. You probably don't need it in any other context.




Parameters
----------

.. raw:: html

    <table  border=0 cellpadding=0 class="documentation-table">
        <tr>
            <th colspan="1">Parameter</th>
            <th>Choices/<font color="blue">Defaults</font></th>
                <th>Configuration</th>
            <th width="100%">Comments</th>
        </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>_input</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">raw</span>
                         / <span style="color: red">required</span>
                    </div>
                </td>
                <td>
                </td>
                    <td>
                    </td>
                <td>
                        <div>Value to render. Usually a step&#x27;s <code>input</code> dictionary.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>ansible_facts</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">dictionary</span>
                    </div>
                </td>
                <td>
                </td>
                    <td>
                    </td>
                <td>
                        <div>The host&#x27;s <code>ansible_facts</code> to expose during rendering.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>steps</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">dictionary</span>
                    </div>
                </td>
                <td>
                </td>
                    <td>
                    </td>
                <td>
                        <div>Mapping of step id to that step&#x27;s registered outputs.</div>
                </td>
            </tr>
    </table>
    <br/>




Examples
--------

.. code-block:: yaml

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



Return Values
-------------
Common return values are documented `here <https://docs.ansible.com/ansible/latest/reference_appendices/common_return_values.html#common-return-values>`_, the following are the fields unique to this filter:

.. raw:: html

    <table border=0 cellpadding=0 class="documentation-table">
        <tr>
            <th colspan="1">Key</th>
            <th>Returned</th>
            <th width="100%">Description</th>
        </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="return-"></div>
                    <b>_value</b>
                    <a class="ansibleOptionLink" href="#return-" title="Permalink to this return value"></a>
                    <div style="font-size: small">
                      <span style="color: purple">raw</span>
                    </div>
                </td>
                <td></td>
                <td>
                            <div>The input with all <code>steps.*</code> and <code>ansible_facts.*</code> references rendered.</div>
                    <br/>
                </td>
            </tr>
    </table>
    <br/><br/>


Status
------


Authors
~~~~~~~

- Project Potos (@projectpotos)


.. hint::
    Configuration entries for each entry type have a low to high priority order. For example, a variable that is lower in the list will override a variable that is higher up.
