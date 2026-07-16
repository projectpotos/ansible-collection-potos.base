.. _projectpotos.base.uki_cmdline_module:


*****************************
projectpotos.base.uki_cmdline
*****************************

**Derive and persist the kernel cmdline embedded into the signed UKI**


Version added: 0.3.0

.. contents::
   :local:
   :depth: 1


Synopsis
--------
- Derives the base kernel cmdline for the UKI build once, persists it to O(base_dest) and writes the effective cmdline (base + hardening + O(extra)) to O(dest) on every run, so a changed O(extra) is applied while the derived base stays stable.
- The base is seeded from the first non-rescue BLS entry under O(bls_dir) (the state anaconda leaves behind). The module fails when neither a persisted base nor a BLS entry with options exists.
- Installer-only flags (``rd.live.*``, ``inst.*``, ``systemd.machine_id=``) and rescue-shell flags are stripped; ``quiet rd.shell=0 rd.emergency=reboot`` and O(extra) are appended.




Parameters
----------

.. raw:: html

    <table  border=0 cellpadding=0 class="documentation-table">
        <tr>
            <th colspan="1">Parameter</th>
            <th>Choices/<font color="blue">Defaults</font></th>
            <th width="100%">Comments</th>
        </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>base_dest</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">path</span>
                    </div>
                </td>
                <td>
                        <b>Default:</b><br/><div style="color: blue">"/var/lib/potos/uki-cmdline-base"</div>
                </td>
                <td>
                        <div>File the derived base cmdline is persisted to.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>bls_dir</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">path</span>
                    </div>
                </td>
                <td>
                        <b>Default:</b><br/><div style="color: blue">"/boot/efi/loader/entries"</div>
                </td>
                <td>
                        <div>Directory holding the BLS loader entries.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>dest</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">path</span>
                    </div>
                </td>
                <td>
                        <b>Default:</b><br/><div style="color: blue">"/etc/kernel/cmdline"</div>
                </td>
                <td>
                        <div>File the effective cmdline is written to.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>extra</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">string</span>
                    </div>
                </td>
                <td>
                        <b>Default:</b><br/><div style="color: blue">""</div>
                </td>
                <td>
                        <div>Extra tokens appended to the cmdline.</div>
                </td>
            </tr>
    </table>
    <br/>




Examples
--------

.. code-block:: yaml

    - name: Derive and write the embedded kernel cmdline
      projectpotos.base.uki_cmdline:
        bls_dir: /boot/efi/loader/entries
        extra: "audit=1"



Return Values
-------------
Common return values are documented `here <https://docs.ansible.com/ansible/latest/reference_appendices/common_return_values.html#common-return-values>`_, the following are the fields unique to this module:

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
                    <b>cmdline</b>
                    <a class="ansibleOptionLink" href="#return-" title="Permalink to this return value"></a>
                    <div style="font-size: small">
                      <span style="color: purple">string</span>
                    </div>
                </td>
                <td>always</td>
                <td>
                            <div>The effective cmdline at O(dest).</div>
                    <br/>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="return-"></div>
                    <b>source</b>
                    <a class="ansibleOptionLink" href="#return-" title="Permalink to this return value"></a>
                    <div style="font-size: small">
                      <span style="color: purple">string</span>
                    </div>
                </td>
                <td>always</td>
                <td>
                            <div>Where the base cmdline came from (V(base) for the persisted base file, V(bls) on first derivation).</div>
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
