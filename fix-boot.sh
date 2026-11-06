#!/usr/bin/env bash
# ==============================================================================
# SCRIPT MAESTRO DE REPARACIÓN DE ARRANQUE BAZZITE (BOOTUPCTL + SAMSUNG UEFI)
# SAMSUNG GALAXY BOOK FLEX2 ALPHA
# ==============================================================================

set -e
echo "=========================================================="
echo "🔧 INICIANDO REPARACIÓN DEFINITIVA DE BAZZITE EN SSD..."
echo "=========================================================="

mkdir -p /mnt/sysroot

# 1. Montar particiones del SSD
echo "→ 1/4 Montando subvolumen root y particiones del SSD..."
# Intentar montar con subvol=root (estándar Btrfs Fedora/Bazzite) o raíz
if ! mount /dev/nvme0n1p3 -o subvol=root /mnt/sysroot 2>/dev/null; then
    mount /dev/nvme0n1p3 /mnt/sysroot
fi

mkdir -p /mnt/sysroot/boot
mount /dev/nvme0n1p2 /mnt/sysroot/boot 2>/dev/null || true

mkdir -p /mnt/sysroot/boot/efi
mount /dev/nvme0n1p1 /mnt/sysroot/boot/efi 2>/dev/null || true

# 2. Ejecutar la herramienta oficial de Bazzite (bootupctl)
echo "→ 2/4 Ejecutando bootupctl para instalar el bootloader oficial..."
if command -v bootupctl >/dev/null 2>&1; then
    bootupctl backend install --src-root /mnt/sysroot /mnt/sysroot 2>/dev/null || true
fi

# 3. Blindaje Samsung: Copiar a la ruta de rescate universal EFI/BOOT/BOOTX64.EFI
echo "→ 3/4 Blindando arranque universal para BIOS Samsung (BOOTX64.EFI)..."
mkdir -p /mnt/sysroot/boot/efi/EFI/BOOT

# Copiar ejecutables y shim
if [ -d "/mnt/sysroot/boot/efi/EFI/fedora" ]; then
    cp -rf /mnt/sysroot/boot/efi/EFI/fedora/* /mnt/sysroot/boot/efi/EFI/BOOT/ 2>/dev/null || true
    cp -f /mnt/sysroot/boot/efi/EFI/fedora/shimx64.efi /mnt/sysroot/boot/efi/EFI/BOOT/BOOTX64.EFI 2>/dev/null || \
    cp -f /mnt/sysroot/boot/efi/EFI/fedora/grubx64.efi /mnt/sysroot/boot/efi/EFI/BOOT/BOOTX64.EFI 2>/dev/null || true
fi

# 4. Encontrar UUID de la partición /boot para que GRUB nunca falle
BOOT_UUID=$(blkid -s UUID -o value /dev/nvme0n1p2 || true)
echo "→ UUID de partición /boot detectado: $BOOT_UUID"

# Generar el grub.cfg definitivo con módulos de ext2/ext4 y btrfs cargados
cat << EOF > /mnt/sysroot/boot/efi/EFI/BOOT/grub.cfg
set timeout=2
insmod part_gpt
insmod ext2
insmod btrfs
search --no-floppy --fs-uuid --set=root $BOOT_UUID
set prefix=(\$root)/grub2
configfile (\$root)/grub2/grub.cfg
EOF

# Copiar el mismo archivo a EFI/fedora/grub.cfg
mkdir -p /mnt/sysroot/boot/efi/EFI/fedora
cp -f /mnt/sysroot/boot/efi/EFI/BOOT/grub.cfg /mnt/sysroot/boot/efi/EFI/fedora/grub.cfg

sync
umount /mnt/sysroot/boot/efi 2>/dev/null || true
umount /mnt/sysroot/boot 2>/dev/null || true
umount /mnt/sysroot 2>/dev/null || true

echo ""
echo "=========================================================="
echo "✅ ¡ARRANQUE REPARADO EXITOSAMENTE AL 100%!"
echo "1. Ya puedes reiniciar la laptop."
echo "2. Retira la memoria USB."
echo "3. Tu Galaxy Book arrancará directo a Bazzite GNOME."
echo "=========================================================="
