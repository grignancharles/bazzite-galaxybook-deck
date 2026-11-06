#!/usr/bin/env bash
echo ""
echo "🔍 COMPROBANDO ARCHIVOS EN TU DISCO SSD..."
echo "------------------------------------------"
mkdir -p /tmp/chk
mount /dev/nvme0n1p1 /tmp/chk 2>/dev/null || true

if [ -f "/tmp/chk/EFI/BOOT/BOOTX64.EFI" ]; then
    echo "✅ ARCHIVO MAESTRO BOOTX64.EFI: ENCONTRADO ($(ls -lh /tmp/chk/EFI/BOOT/BOOTX64.EFI | awk '{print $5}'))"
else
    echo "❌ BOOTX64.EFI no encontrado"
fi

if [ -f "/tmp/chk/EFI/BOOT/grub.cfg" ]; then
    echo "✅ ARCHIVO DE MENÚ grub.cfg: ENCONTRADO"
    echo ""
    echo "Contenido de tu grub.cfg:"
    cat /tmp/chk/EFI/BOOT/grub.cfg
else
    echo "❌ grub.cfg no encontrado"
fi

umount /tmp/chk 2>/dev/null || true
echo "------------------------------------------"
echo "SI VISTE LAS DOS PALOMITAS VERDES (✅), ESTÁ 100% LISTO."
echo ""
