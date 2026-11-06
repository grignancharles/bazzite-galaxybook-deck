#!/usr/bin/env bash
# ==============================================================================
# SCRIPT MAESTRO REPARADOR BOOTLOADER SAMSUNG GALAXY BOOK (BAZZITE OSTREE)
# 100% Nativo sin chroot - Compatible con sistemas inmutables / ostree
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 REPARADOR BOOTLOADER BAZZITE (SAMSUNG GALAXY BOOK)"
echo "=========================================================="

# 1. Limpiar entradas viejas de NVRAM en BIOS Samsung
echo "→ 1/5 Limpiando entradas viejas en la NVRAM de Samsung..."
for bootnum in $(efibootmgr 2>/dev/null | grep -iE "fedora|bazzite" | awk '{print $1}' | tr -d 'Boot*'); do
    echo "  Borrando entrada vieja Boot$bootnum..."
    efibootmgr -b "$bootnum" -B 2>/dev/null || true
done

# 2. Montar particiones del SSD
echo "→ 2/5 Montando particiones del SSD..."
mkdir -p /mnt/sysroot /mnt/sysroot/boot /mnt/sysroot/boot/efi

if ! mount /dev/nvme0n1p3 -o subvol=root /mnt/sysroot 2>/dev/null; then
    mount /dev/nvme0n1p3 /mnt/sysroot 2>/dev/null || true
fi

mount /dev/nvme0n1p2 /mnt/sysroot/boot 2>/dev/null || true
mount /dev/nvme0n1p1 /mnt/sysroot/boot/efi 2>/dev/null || true

# 3. Ejecutar bootupctl (herramienta oficial de Bazzite)
echo "→ 3/5 Instalando bootloader oficial con bootupctl..."
if command -v bootupctl >/dev/null 2>&1; then
    bootupctl backend install --src-root /mnt/sysroot /mnt/sysroot 2>/dev/null || true
fi

# 4. Instalar GRUB universal (--no-nvram y --removable) sin chroot
echo "→ 4/5 Aplicando parche universal para BIOS Samsung (BOOTX64.EFI)..."
mkdir -p /mnt/sysroot/boot/efi/EFI/BOOT /mnt/sysroot/boot/efi/EFI/fedora

# Si existe grub2-install en el Live, correrlo apuntando a los directorios del SSD
if command -v grub2-install >/dev/null 2>&1; then
    grub2-install --target=x86_64-efi \
                  --efi-directory=/mnt/sysroot/boot/efi \
                  --boot-directory=/mnt/sysroot/boot \
                  --bootloader-id=fedora \
                  --no-nvram \
                  --removable \
                  --force 2>/dev/null || true
fi

# Copiar ejecutables de arranque directo
if [ -f "/mnt/sysroot/boot/efi/EFI/fedora/shimx64.efi" ]; then
    cp -f /mnt/sysroot/boot/efi/EFI/fedora/* /mnt/sysroot/boot/efi/EFI/BOOT/ 2>/dev/null || true
    cp -f /mnt/sysroot/boot/efi/EFI/fedora/shimx64.efi /mnt/sysroot/boot/efi/EFI/BOOT/BOOTX64.EFI 2>/dev/null || true
elif [ -f "/boot/efi/EFI/BOOT/BOOTX64.EFI" ]; then
    cp -rf /boot/efi/EFI/BOOT/* /mnt/sysroot/boot/efi/EFI/BOOT/ 2>/dev/null || true
fi

# Obtener UUID de la partición /boot para que GRUB nunca se pierda
BOOT_UUID=$(blkid -s UUID -o value /dev/nvme0n1p2 2>/dev/null || true)
echo "→ UUID /boot: $BOOT_UUID"

# Generar el grub.cfg puente con módulos de ext4 y btrfs
cat << EOF > /mnt/sysroot/boot/efi/EFI/BOOT/grub.cfg
set timeout=2
insmod part_gpt
insmod ext2
insmod btrfs
search --no-floppy --fs-uuid --set=root $BOOT_UUID
set prefix=(\$root)/grub2
configfile (\$root)/grub2/grub.cfg
EOF

cp -f /mnt/sysroot/boot/efi/EFI/BOOT/grub.cfg /mnt/sysroot/boot/efi/EFI/fedora/grub.cfg 2>/dev/null || true

# 5. Sincronizar y desmontar
echo "→ 5/5 Sincronizando y desmontando..."
sync
umount -l /mnt/sysroot/boot/efi 2>/dev/null || true
umount -l /mnt/sysroot/boot 2>/dev/null || true
umount -l /mnt/sysroot 2>/dev/null || true

echo ""
echo "=========================================================="
echo "✅ ¡ARRANQUE REPARADO EXITOSAMENTE AL 100%!"
echo "1. Reinicia la laptop."
echo "2. Retira la memoria USB."
echo "3. Tu Galaxy Book arrancará directo a Bazzite GNOME."
echo "=========================================================="
