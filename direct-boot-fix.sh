#!/usr/bin/env bash
# ==============================================================================
# REPARACIÓN DIRECTA DE ARRANQUE BAZZITE (MENUENTRY DIRECTO SIN DEPENDENCIAS)
# ==============================================================================

set -e
echo "=========================================================="
echo "🚀 INYECTANDO ARRANQUE DIRECTO DE KERNEL EN GRUB..."
echo "=========================================================="

mkdir -p /tmp/b /tmp/e /tmp/r
mount /dev/nvme0n1p2 /tmp/b 2>/dev/null || true
mount /dev/nvme0n1p1 /tmp/e 2>/dev/null || true

# 1. Detectar kernel e initramfs en la partición /boot
KERNEL=$(ls /tmp/b/vmlinuz-* 2>/dev/null | sort -V | tail -n 1 | xargs -n 1 basename || true)
INITRD=$(ls /tmp/b/initramfs-*.img 2>/dev/null | sort -V | tail -n 1 | xargs -n 1 basename || true)

echo "→ Kernel detectado: $KERNEL"
echo "→ Initramfs detectado: $INITRD"

# 2. Detectar UUIDs de las particiones
BOOT_UUID=$(blkid -s UUID -o value /dev/nvme0n1p2)
ROOT_UUID=$(blkid -s UUID -o value /dev/nvme0n1p3)

echo "→ UUID Boot (/boot): $BOOT_UUID"
echo "→ UUID Root (/): $ROOT_UUID"

# 3. Asegurar que los binarios EFI están en EFI/BOOT
mkdir -p /tmp/e/EFI/BOOT /tmp/e/EFI/fedora
if [ -f "/boot/efi/EFI/BOOT/BOOTX64.EFI" ]; then
    cp -rf /boot/efi/EFI/BOOT/* /tmp/e/EFI/BOOT/ 2>/dev/null || true
fi
if [ -f "/boot/efi/EFI/fedora/shimx64.efi" ]; then
    cp -rf /boot/efi/EFI/fedora/* /tmp/e/EFI/BOOT/ 2>/dev/null || true
    cp -f /boot/efi/EFI/fedora/shimx64.efi /tmp/e/EFI/BOOT/BOOTX64.EFI 2>/dev/null || true
fi

# 4. Crear el grub.cfg con el menú DIRECTO al kernel
cat << EOF > /tmp/e/EFI/BOOT/grub.cfg
set default=0
set timeout=2
insmod part_gpt
insmod ext2
insmod btrfs

search --no-floppy --fs-uuid --set=root $BOOT_UUID

menuentry 'Bazzite' --class bazzite --class fedora --class gnu-linux --class gnu --class os {
    linux /$KERNEL root=UUID=$ROOT_UUID rootflags=subvol=root rw quiet rhgb mitigations=off i915.enable_guc=3
    initrd /$INITRD
}
EOF

# Copiar a EFI/fedora/grub.cfg y /boot/grub2/grub.cfg
cp -f /tmp/e/EFI/BOOT/grub.cfg /tmp/e/EFI/fedora/grub.cfg 2>/dev/null || true

mkdir -p /tmp/b/grub2
cp -f /tmp/e/EFI/BOOT/grub.cfg /tmp/b/grub2/grub.cfg 2>/dev/null || true

sync
umount /tmp/b 2>/dev/null || true
umount /tmp/e 2>/dev/null || true

echo ""
echo "=========================================================="
echo "✅ ¡MENÚ DIRECTO INYECTADO CON ÉXITO!"
echo "Kernel: $KERNEL"
echo "Ya no hay intermediarios: GRUB arrancará este kernel en 2s."
echo "=========================================================="
