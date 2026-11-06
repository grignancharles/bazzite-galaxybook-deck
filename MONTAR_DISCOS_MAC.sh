#!/bin/bash
# ==============================================================================
# MONTADOR UNIVERSAL PARA DISCOS DE MAC (APPLE APFS / HFS+) - BAZZITE
# Soporta cualquier disco APFS y HFS+ externo o interno conectado
# Detección dinámica de usuario (rafa / usuario activo) y permisos completos
# ==============================================================================

set -u

C_RESET="\033[0m"
C_GREEN="\033[1;32m"
C_CYAN="\033[1;36m"
C_YELLOW="\033[1;33m"
C_RED="\033[1;31m"
C_BOLD="\033[1m"

clear
echo -e "${C_CYAN}╔════════════════════════════════════════════════════════════════════╗${C_RESET}"
echo -e "${C_CYAN}║     MONTADOR UNIVERSAL DE DISCOS MAC (APFS / HFS+) - BAZZITE       ║${C_RESET}"
echo -e "${C_CYAN}║     Soporte para cualquier disco conectado (MessiEnto y más)       ║${C_RESET}"
echo -e "${C_CYAN}╚════════════════════════════════════════════════════════════════════╝${C_RESET}"
echo ""

[[ $EUID -ne 0 ]] && { echo -e "${C_RED}❌ Ejecuta con sudo: sudo bash $0${C_RESET}"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detección dinámica de usuario (rafa o usuario activo en /home)
detect_target_user() {
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        echo "$SUDO_USER"
        return
    fi
    local active_user
    active_user=$(loginctl list-sessions --no-legend 2>/dev/null | awk '{print $3}' | grep -vE "^root$|^gdm$|^sddm$|^lightdm$" | head -n 1)
    if [ -n "$active_user" ] && id "$active_user" >/dev/null 2>&1; then
        echo "$active_user"
        return
    fi
    if [ -d "/home/rafa" ] && id "rafa" >/dev/null 2>&1; then
        echo "rafa"
        return
    fi
    for u in /home/*; do
        if [ -d "$u" ]; then
            local un
            un=$(basename "$u")
            if [ "$un" != "lost+found" ] && id "$un" >/dev/null 2>&1; then
                echo "$un"
                return
            fi
        fi
    done
    echo "bazzite"
}

ACTUAL_USER=$(detect_target_user)
USER_UID=$(id -u "$ACTUAL_USER" 2>/dev/null || echo "1000")
USER_GID=$(id -g "$ACTUAL_USER" 2>/dev/null || echo "1000")

echo -e "👤 Usuario destino detectado: ${C_GREEN}${ACTUAL_USER}${C_RESET} (UID: ${USER_UID}, GID: ${USER_GID})"

# 1. Habilitar user_allow_other en /etc/fuse.conf (Fix 'allow_other is not allowed')
mkdir -p /etc
if [ -f "/etc/fuse.conf" ]; then
    sed -i 's/#user_allow_other/user_allow_other/' /etc/fuse.conf
    grep -q "^user_allow_other" /etc/fuse.conf || echo "user_allow_other" >> /etc/fuse.conf
else
    echo "user_allow_other" > /etc/fuse.conf
fi
chmod 644 /etc/fuse.conf

# 2. Instalar binarios y wrappers si vienen en el paquete
mkdir -p /usr/local/bin /usr/local/sbin /etc/udisks2

if [ -f "${SCRIPT_DIR}/bin/apfs-fuse" ]; then
    cp -f "${SCRIPT_DIR}/bin/apfs-fuse" /usr/local/bin/apfs-fuse
    chmod +x /usr/local/bin/apfs-fuse
fi

if [ -f "${SCRIPT_DIR}/bin/mount.apfs" ]; then
    cp -f "${SCRIPT_DIR}/bin/mount.apfs" /usr/local/sbin/mount.apfs
    cp -f "${SCRIPT_DIR}/bin/mount.apfs" /usr/local/bin/mount.apfs
    chmod +x /usr/local/sbin/mount.apfs /usr/local/bin/mount.apfs
fi

# Limpiar cualquier opción conflictiva de udisks2
rm -f /etc/udisks2/mount_options.conf 2>/dev/null || true

if [ ! -x "/usr/local/bin/apfs-fuse" ] && ! command -v apfs-fuse >/dev/null 2>&1; then
    echo -e "${C_RED}❌ Error: apfs-fuse no encontrado en /usr/local/bin nem en PATH${C_RESET}"
    exit 1
fi

APFS_EXEC="/usr/local/bin/apfs-fuse"
[ ! -x "$APFS_EXEC" ] && APFS_EXEC=$(command -v apfs-fuse)

# Asegurar módulos del kernel cargados
modprobe fuse 2>/dev/null || true
modprobe hfs 2>/dev/null || true
modprobe hfsplus 2>/dev/null || true

echo -e "${C_YELLOW}→ Escaneando discos, contenedores APFS y particiones HFS+...${C_RESET}"
FOUND=0

# Lista de dispositivos con APFS o HFS+
while IFS= read -r line; do
    [ -z "$line" ] && continue
    dev_name=$(echo "$line" | awk '{print $1}')
    [ -z "$dev_name" ] && continue
    
    DEV_PATH="/dev/$dev_name"
    [ ! -b "$DEV_PATH" ] && continue
    
    label=$(lsblk -no LABEL "$DEV_PATH" 2>/dev/null | head -n 1 || true)
    fstype=$(lsblk -no FSTYPE "$DEV_PATH" 2>/dev/null | head -n 1 || true)
    parttype=$(lsblk -no PARTTYPE "$DEV_PATH" 2>/dev/null | head -n 1 || true)
    
    # Comprobar si es APFS o HFS+
    IS_APFS=0
    IS_HFS=0
    if echo "$fstype" | grep -qi "apfs" || [ "${parttype,,}" = "7c3457ef-0000-11aa-aa11-00306543ecac" ]; then
        IS_APFS=1
    elif echo "$fstype" | grep -qi "hfs"; then
        IS_HFS=1
    fi
    
    if [ "$IS_APFS" -eq 1 ] || [ "$IS_HFS" -eq 1 ]; then
        FOUND=$((FOUND + 1))
        TARGET_NAME="${label:-$dev_name}"
        if [ "$IS_APFS" -eq 1 ]; then
            REAL_APFS_NAME=$(/usr/local/bin/apfsutil "$DEV_PATH" 2>/dev/null | awk -F': ' '/volname/{print $2; exit}' | tr -d '\r\n')
            [ -n "$REAL_APFS_NAME" ] && TARGET_NAME="$REAL_APFS_NAME"
        fi
        [ -z "$TARGET_NAME" ] && TARGET_NAME="MacDisk_${dev_name}"
        
        MOUNT_POINT="/run/media/${ACTUAL_USER}/${TARGET_NAME}"
        mkdir -p "$MOUNT_POINT"
        
        if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
            echo -e "${C_GREEN}✓ ${DEV_PATH} ya está montado en ${MOUNT_POINT}${C_RESET}"
            continue
        fi
        
        echo -e "${C_YELLOW}  Montando ${DEV_PATH} (${TARGET_NAME}) en ${MOUNT_POINT}...${C_RESET}"
        if [ "$IS_APFS" -eq 1 ]; then
            "$APFS_EXEC" -o allow_other,uid=$USER_UID,gid=$USER_GID "$DEV_PATH" "$MOUNT_POINT" 2>/dev/null || \
            /usr/local/sbin/mount.apfs "$DEV_PATH" "$MOUNT_POINT" 2>/dev/null || true
        else
            mount -t hfsplus -o ro,uid=$USER_UID,gid=$USER_GID "$DEV_PATH" "$MOUNT_POINT" 2>/dev/null || true
        fi
        
        if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
            chown -R "$ACTUAL_USER:$ACTUAL_USER" "$MOUNT_POINT" 2>/dev/null || true
            echo -e "${C_GREEN}  ✅ ¡${TARGET_NAME} montado con éxito! Visible en la barra de Archivos (Nautilus).${C_RESET}"
        else
            echo -e "${C_RED}  ⚠️ No se pudo montar ${DEV_PATH} directamente.${C_RESET}"
        fi
    fi
done < <(lsblk -r -n -o NAME,FSTYPE,PARTTYPE 2>/dev/null)

if [ "$FOUND" -eq 0 ]; then
    echo -e "${C_YELLOW}No se detectaron discos o particiones Mac conectadas en este momento.${C_RESET}"
    echo -e "Conecta cualquier disco USB de Mac y el servicio en segundo plano lo montará al instante."
fi

echo ""
