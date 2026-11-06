#!/usr/bin/env bash
# Ansible managed
# Keep the boot chain under /boot/efi/EFI/potos in sync with the packaged shim
# and the host-signed systemd-boot.
set -euo pipefail

refresh() {
  if ! cmp -s "$1" "$2"; then
    echo "updating $2 from $1"
    cp -f "$1" "$2"
  fi
}

refresh /boot/efi/EFI/fedora/shimx64.efi /boot/efi/EFI/potos/shimx64.efi
refresh /boot/efi/EFI/fedora/mmx64.efi /boot/efi/EFI/potos/mmx64.efi

if ! sbverify --cert /etc/potos/secureboot/mok.crt /boot/efi/EFI/potos/grubx64.efi >/dev/null 2>&1; then
  echo "/boot/efi/EFI/potos/grubx64.efi lost the host MOK signature; re-signing systemd-boot over it"
  sbsign --key /etc/potos/secureboot/mok.key --cert /etc/potos/secureboot/mok.crt \
    --output /boot/efi/EFI/potos/grubx64.efi /usr/lib/systemd/boot/efi/systemd-bootx64.efi
fi
refresh /boot/efi/EFI/potos/shimx64.efi /boot/efi/EFI/BOOT/BOOTX64.EFI
refresh /boot/efi/EFI/potos/mmx64.efi /boot/efi/EFI/BOOT/mmx64.efi
refresh /boot/efi/EFI/potos/grubx64.efi /boot/efi/EFI/BOOT/grubx64.efi
rm -f /boot/efi/EFI/BOOT/fbx64.efi
