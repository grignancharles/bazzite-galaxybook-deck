#!/usr/bin/env bash
# ==============================================================================
# SCRIPT DE REPARACIÓN DE ARRANQUE EFI - SAMSUNG GALAXY BOOK
# ==============================================================================
set -e
echo "🔧 Reparando arranque EFI para Samsung Galaxy Book..."

mkdir -p /mnt/efi
mount /dev/nvme0n1p1 /mnt/efi

mkdir -p /mnt/efi/EFI/BOOT
cp -rf /mnt/efi/EFI/fedora/* /mnt/efi/EFI/BOOT/ 2>/dev/null || true
cp -f /mnt/efi/EFI/BOOT/shimx64.efi /mnt/efi/EFI/BOOT/BOOTX64.EFI 2>/dev/null || \
cp -f /mnt/efi/EFI/BOOT/grubx64.efi /mnt/efi/EFI/BOOT/BOOTX64.EFI 2>/dev/null || true

# Asegurar archivo grub.cfg en ambas carpetas
if [ -f "/mnt/efi/EFI/fedora/grub.cfg" ]; then
    cp -f /mnt/efi/EFI/fedora/grub.cfg /mnt/efi/EFI/BOOT/grub.cfg 2>/dev/null || true
fi

sync
umount /mnt/efi

echo ""
echo "=================================================="
echo "✅ ¡ARRANQUE REPARADO CON ÉXITO!"
echo "Ya puedes reiniciar y retirar la memoria USB."
echo "=================================================="
