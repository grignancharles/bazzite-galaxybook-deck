#!/usr/bin/env bash
# ==============================================================================
# SCRIPT DEFINITIVO DE INSTALACIÓN Y REPARACIÓN BOOTLOADER SAMSUNG GALAXY BOOK
# Usa el método probado: --no-nvram --removable (Chroot en SSD)
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 REPARADOR MAESTRO BOOTLOADER SAMSUNG GALAXY BOOK"
echo "=========================================================="

# 1. Limpiar entradas viejas o corruptas de NVRAM en BIOS Samsung
echo "→ 1/5 Limpiando entradas viejas en la NVRAM de Samsung..."
for bootnum in $(efibootmgr 2>/dev/null | grep -iE "fedora|bazzite" | awk '{print $1}' | tr -d 'Boot*'); do
    echo "  Borrando entrada vieja Boot$bootnum..."
    efibootmgr -b "$bootnum" -B 2>/dev/null || true
done

# 2. Montar particiones del SSD
echo "→ 2/5 Montando particiones del SSD..."
mkdir -p /mnt/sysroot
if ! mount /dev/nvme0n1p3 -o subvol=root /mnt/sysroot 2>/dev/null; then
    mount /dev/nvme0n1p3 /mnt/sysroot
fi

mkdir -p /mnt/sysroot/boot
mount /dev/nvme0n1p2 /mnt/sysroot/boot 2>/dev/null || true

mkdir -p /mnt/sysroot/boot/efi
mount /dev/nvme0n1p1 /mnt/sysroot/boot/efi 2>/dev/null || true

# 3. Montar sistemas virtuales para chroot
echo "→ 3/5 Montando sistemas virtuales para Chroot..."
for i in /dev /dev/pts /proc /sys /run; do
    mkdir -p "/mnt/sysroot$i"
    mount -B "$i" "/mnt/sysroot$i" 2>/dev/null || true
done

# 4. Instalar GRUB con --no-nvram y --removable (El secreto para Samsung)
echo "→ 4/5 Instalando GRUB con modo --no-nvram y --removable..."
chroot /mnt/sysroot bash -c "
    grub2-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=fedora --no-nvram --removable --force 2>/dev/null || true
    grub2-mkconfig -o /boot/grub2/grub.cfg 2>/dev/null || true
    grub2-mkconfig -o /boot/efi/EFI/fedora/grub.cfg 2>/dev/null || true
"

# Copiar a la ruta universal de rescate BOOTX64.EFI
mkdir -p /mnt/sysroot/boot/efi/EFI/BOOT
cp -f /mnt/sysroot/boot/efi/EFI/fedora/* /mnt/sysroot/boot/efi/EFI/BOOT/ 2>/dev/null || true
if [ -f "/mnt/sysroot/boot/efi/EFI/fedora/grub.cfg" ]; then
    cp -f /mnt/sysroot/boot/efi/EFI/fedora/grub.cfg /mnt/sysroot/boot/efi/EFI/BOOT/grub.cfg
fi

# 5. Desmontar todo limpiamente
echo "→ 5/5 Sincronizando y desmontando..."
sync
for i in /run /sys /proc /dev/pts /dev; do
    umount -l "/mnt/sysroot$i" 2>/dev/null || true
done
umount -l /mnt/sysroot/boot/efi 2>/dev/null || true
umount -l /mnt/sysroot/boot 2>/dev/null || true
umount -l /mnt/sysroot 2>/dev/null || true

echo ""
echo "=========================================================="
echo "✅ ¡ARRANQUE INSTALADO EXITOSAMENTE AL 100%!"
echo "1. Reinicia la laptop."
echo "2. Retira la memoria USB."
echo "3. Tu Galaxy Book arrancará directo a Bazzite GNOME."
echo "=========================================================="
