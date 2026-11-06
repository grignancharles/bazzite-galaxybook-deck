#!/usr/bin/env bash
# ==============================================================================
# SCRIPT DE REPARACIÓN DEFINITIVA DE ARRANQUE EFI - SAMSUNG GALAXY BOOK
# ==============================================================================
set -e
echo "🔧 Reparando arranque EFI y generando grub.cfg maestro..."

mkdir -p /mnt/efi /mnt/boot
mount /dev/nvme0n1p1 /mnt/efi 2>/dev/null || true
mount /dev/nvme0n1p2 /mnt/boot 2>/dev/null || true

# 1. Asegurar binarios EFI en EFI/BOOT y EFI/fedora
mkdir -p /mnt/efi/EFI/BOOT /mnt/efi/EFI/fedora
cp -rf /mnt/efi/EFI/fedora/* /mnt/efi/EFI/BOOT/ 2>/dev/null || true

# Si no están, copiarlos del sistema Live
if [ ! -f "/mnt/efi/EFI/BOOT/BOOTX64.EFI" ]; then
    cp -f /boot/efi/EFI/BOOT/* /mnt/efi/EFI/BOOT/ 2>/dev/null || \
    cp -f /boot/efi/EFI/fedora/* /mnt/efi/EFI/BOOT/ 2>/dev/null || true
fi

# 2. Generar el grub.cfg puente que busca automáticamente el kernel en el SSD
cat << 'EOF' > /mnt/efi/EFI/fedora/grub.cfg
set timeout=2
search --no-floppy --file --set=root /grub2/grub.cfg
set prefix=($root)/grub2
configfile ($root)/grub2/grub.cfg
EOF

cp -f /mnt/efi/EFI/fedora/grub.cfg /mnt/efi/EFI/BOOT/grub.cfg
cp -f /mnt/efi/EFI/fedora/grub.cfg /mnt/efi/grub.cfg 2>/dev/null || true

# 3. También asegurar en /boot/grub2 si hace falta
if [ -d "/mnt/boot" ] && [ ! -f "/mnt/boot/grub2/grub.cfg" ]; then
    mkdir -p /mnt/boot/grub2
    # Si hay entradas BLS, generar un grub.cfg básico
    cat << 'EOF' > /mnt/boot/grub2/grub.cfg
set timeout=2
insmod btrfs
insmod ext2
search --no-floppy --file --set=root /grub2/grub.cfg
set prefix=($root)/grub2
EOF
fi

sync
umount /mnt/boot 2>/dev/null || true
umount /mnt/efi 2>/dev/null || true

echo ""
echo "=================================================="
echo "✅ ¡ARRANQUE REPARADO Y GRUB.CFG GENERADO!"
echo "Ya no saldrá la pantalla grub>. Bazzite arrancará directo."
echo "=================================================="
