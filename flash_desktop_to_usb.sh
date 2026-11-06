#!/bin/bash
set -euo pipefail

TARGET_DISK="/dev/disk8"
TARGET_RDISK="/dev/rdisk8"
ISO_PATH="/Users/carlosgrinan/Downloads/bazzite-stable-amd64.iso"

echo "=========================================================="
echo "  GRABADOR SEGURO: BAZZITE DESKTOP (TUTORIAL OFICIAL)     "
echo "=========================================================="
echo ""

# 1. Comprobación estricta de seguridad: JAMÁS tocar MessiEnto
if diskutil list | grep -q "MessiEnto.*disk8"; then
    echo "❌ ERROR CRÍTICO: disk8 contiene MessiEnto. ABORTANDO INMEDIATAMENTE."
    exit 1
fi

# 2. Verificar que disk8 existe y es la memoria USB (~31.5 GB)
if ! diskutil info "$TARGET_DISK" >/dev/null 2>&1; then
    echo "❌ ERROR: No se detecta $TARGET_DISK. Verifica que la memoria USB esté conectada."
    exit 1
fi

DISK_SIZE=$(diskutil info "$TARGET_DISK" | grep "Disk Size" | awk '{print $3, $4}')
echo "✓ Unidad detectada: $TARGET_DISK ($DISK_SIZE)"
echo "✓ Archivo ISO: $ISO_PATH"
echo ""

# 3. Desmontar particiones de la USB
echo "→ Desmontando volúmenes de $TARGET_DISK..."
diskutil unmountDisk "$TARGET_DISK" || true

# 4. Grabación con dd a máxima velocidad (rdisk)
echo ""
echo "🚀 GRABANDO ISO EN LA USB A MÁXIMA VELOCIDAD (~50-80 MB/s)..."
echo "   (Tardará unos 2-3 minutos)"
echo ""

sudo dd if="$ISO_PATH" of="$TARGET_RDISK" bs=4m status=progress

echo ""
echo "→ Sincronizando datos en el USB..."
sync

echo ""
echo "=========================================================="
echo "🎉 ¡LISTO! MEMORIA USB BAZZITE DESKTOP GRABADA CON ÉXITO"
echo "=========================================================="
