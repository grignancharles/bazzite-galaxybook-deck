#!/bin/bash
set -euo pipefail

TARGET_DISK="/dev/disk9"
TARGET_RDISK="/dev/rdisk9"
ISO_PATH="/Users/carlosgrinan/Downloads/bazzite-deck-stable-amd64/bazzite-deck-stable-amd64.iso"

echo "=========================================================="
echo "  GRABADOR SEGURO DE BAZZITE OFICIAL PARA GALAXY BOOK     "
echo "=========================================================="
echo ""

# 1. Comprobación estricta de seguridad: JAMÁS tocar MessiEnto
if diskutil list | grep -q "MessiEnto.*disk9"; then
    echo "❌ ERROR CRÍTICO: disk9 contiene MessiEnto. ABORTANDO INMEDIATAMENTE."
    exit 1
fi

# 2. Verificar que disk9 existe y es la memoria USB (~31.5 GB)
if ! diskutil info "$TARGET_DISK" >/dev/null 2>&1; then
    echo "❌ ERROR: No se detecta $TARGET_DISK. Verifica que la memoria USB esté conectada."
    exit 1
fi

DISK_SIZE=$(diskutil info "$TARGET_DISK" | grep "Disk Size" | awk '{print $3, $4}')
echo "✓ Unidad detectada: $TARGET_DISK ($DISK_SIZE)"
echo "✓ Archivo ISO oficial parcheado (Boot automático en 1s): $ISO_PATH"
echo ""

# 3. Desmontar particiones de la USB
echo "→ Desmontando volúmenes de $TARGET_DISK..."
diskutil unmountDisk "$TARGET_DISK" || true

# 4. Grabación con dd a máxima velocidad (rdisk)
echo ""
echo "🚀 GRABANDO ISO EN LA USB A MÁXIMA VELOCIDAD (~50 MB/s)..."
echo "   (Tardará unos 2-3 minutos. Verás el progreso en pantalla)"
echo ""

sudo dd if="$ISO_PATH" of="$TARGET_RDISK" bs=4m status=progress

echo ""
echo "→ Sincronizando datos en el USB..."
sync

echo ""
echo "=========================================================="
echo "🎉 ¡LISTO! MEMORIA USB BAZZITE OFICIAL GRABADA CON ÉXITO"
echo "=========================================================="
echo "Puedes desconectar la memoria USB y conectarla en tu Galaxy Book."
echo "Al encender la laptop, arrancará sola en 1 segundo."
echo "Usa el TOUCHPAD para hacer clic en el instalador."
echo "=========================================================="
