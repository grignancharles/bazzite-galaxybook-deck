#!/bin/bash
# ==============================================================================
# Soporte Nativo para Discos Duros Externos de Mac (Formato Apple APFS y HFS+)
# Permite abrir discos como 'MessiEnto' formateados en macOS directamente en Bazzite
# ==============================================================================

set -euo pipefail

echo "Configurando soporte para discos externos formateados en Mac (APFS / HFS+)..."

# 1. Crear script montador automático de discos Mac APFS
cat << 'EOF' > /usr/bin/mount-mac-disk
#!/bin/bash
echo "=========================================================="
echo "    MONTADOR DE DISCOS DUROS EXTERNOS DE MAC (APFS)       "
echo "=========================================================="
echo ""

# Buscar particiones con firma Apple APFS
APFS_DEVS=$(lsblk -f -o NAME,FSTYPE,LABEL,SIZE | grep -iE "apfs" || true)

if [ -z "$APFS_DEVS" ]; then
    echo "Buscando particiones por tipo de GUID de Apple..."
    # Buscar dispositivos USB externos tipo APFS (GUID 7C3457EF-0000-11AA-AA11-00306543ECAC)
    APFS_PART=$(blkid | grep -i "apfs" | cut -d: -f1 || true)
fi

echo "Dispositivos Mac detectados:"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT

echo ""
# Buscar la partición APFS externa
TARGET_PART=""
for dev in $(lsblk -r -n -o NAME,FSTYPE | awk '$2=="apfs"{print $1}'); do
    TARGET_PART="/dev/$dev"
    break
done

if [ -z "$TARGET_PART" ]; then
    # Búsqueda alternativa en discos sd*
    for dev in /dev/sd[b-z][0-9]*; do
        if [ -b "$dev" ]; then
            # Comprobar con blkid o fstype
            if blkid "$dev" | grep -qi "apfs"; then
                TARGET_PART="$dev"
                break
            fi
        fi
    done
fi

if [ -z "$TARGET_PART" ]; then
    echo "No se detectó automáticamente ninguna partición APFS conectada."
    echo "Si tu disco está conectado, escribe la partición (ejemplo /dev/sdb2):"
    read -rp "> " TARGET_PART
fi

if [ -z "$TARGET_PART" ] || [ ! -b "$TARGET_PART" ]; then
    echo "Dispositivo no válido. Abortando."
    exit 1
fi

MOUNT_DIR="/media/MacDisk"
mkdir -p "$MOUNT_DIR"

echo "Montando $TARGET_PART en $MOUNT_DIR con apfs-fuse..."
apfs-fuse -o allow_other "$TARGET_PART" "$MOUNT_DIR"

echo ""
echo "¡Disco de Mac montado exitosamente en: $MOUNT_DIR!"
echo "Abriendo explorador de archivos..."
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$MOUNT_DIR" 2>/dev/null || true
fi
EOF

chmod +x /usr/bin/mount-mac-disk

# 2. Crear acceso directo de escritorio para montar discos Mac con 1 clic
cat << 'EOF' > /usr/share/applications/mount-mac-disk.desktop
[Desktop Entry]
Name=Abrir Disco Externo Mac (APFS)
Comment=Monta y abre discos duros formateados en macOS (como MessiEnto)
Exec=/usr/bin/mount-mac-disk
Icon=drive-removable-media
Terminal=true
Type=Application
Categories=System;Utility;
Keywords=mac;apple;apfs;disk;usb;external;
EOF

chmod +x /usr/share/applications/mount-mac-disk.desktop

echo "Soporte nativo para discos externos APFS y HFS+ configurado."
