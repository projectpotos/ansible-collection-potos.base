#!/usr/bin/env bash
# Ansible managed
# Restore the host-signed systemd-boot at /boot/efi/EFI/fedora/grubx64.efi if another package
# replaced it.
set -euo pipefail

if ! sbverify --cert /etc/potos/secureboot/mok.crt /boot/efi/EFI/fedora/grubx64.efi >/dev/null 2>&1; then
  echo "/boot/efi/EFI/fedora/grubx64.efi lost the host MOK signature; re-signing systemd-boot over it"
  sbsign --key /etc/potos/secureboot/mok.key --cert /etc/potos/secureboot/mok.crt \
    --output /boot/efi/EFI/fedora/grubx64.efi /usr/lib/systemd/boot/efi/systemd-bootx64.efi
fi
if ! sbverify --cert /etc/potos/secureboot/mok.crt /boot/efi/EFI/BOOT/grubx64.efi >/dev/null 2>&1; then
  echo "refreshing removable-media fallback copy of grubx64.efi"
  cp -f /boot/efi/EFI/fedora/grubx64.efi /boot/efi/EFI/BOOT/grubx64.efi
fi
