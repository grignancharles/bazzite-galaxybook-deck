#!/bin/bash
# ==============================================================================
# Script Interactivo de Flasheo a USB para macOS (Terminal zsh/bash)
# Graba la ISO de Bazzite Galaxy Book de forma segura y optimizada
# ==============================================================================

set -euo pipefail

# Colores para la terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

clear
echo -e "${BLUE}${BOLD}==================================================================${NC}"
echo -e "${BLUE}${BOLD}   GRABADOR DE USB PARA SAMSUNG GALAXY BOOK STEAMOS (BAZZITE)     ${NC}"
echo -e "${BLUE}${BOLD}==================================================================${NC}"
echo ""

# 1. Localizar el archivo ISO
ISO_FILE="${1:-}"

if [ -z "$ISO_FILE" ]; then
    # Buscar automáticamente archivos .iso en el directorio actual o en ~/Downloads
    FOUND_ISO=$(find . ~/Downloads -maxdepth 2 -name "*galaxybook*.iso" -o -name "*bazzite*.iso" 2>/dev/null | head -n 1 || true)
    
    if [ -n "$FOUND_ISO" ]; then
        echo -e "${YELLOW}Se detectó automáticamente una ISO:${NC} $FOUND_ISO"
        read -rp "¿Deseas usar esta ISO? [S/n]: " USE_AUTO
        if [[ "$USE_AUTO" =~ ^[nN] ]]; then
            FOUND_ISO=""
        else
            ISO_FILE="$FOUND_ISO"
        fi
    fi
fi

while [ -z "$ISO_FILE" ] || [ ! -f "$ISO_FILE" ]; do
    echo -e "${YELLOW}Arrastra y suelta el archivo .iso de Bazzite aquí (o escribe la ruta) y presiona Enter:${NC}"
    read -re -p "> " INPUT_ISO
    # Quitar comillas o barras escapadas si el usuario arrastró el archivo
    ISO_FILE=$(echo "$INPUT_ISO" | sed "s/^'//; s/'$//; s/^\"//; s/\"$//; s/\\\\ / /g")
    if [ ! -f "$ISO_FILE" ]; then
        echo -e "${RED}El archivo especificado no existe. Intenta nuevamente.${NC}"
        ISO_FILE=""
    fi
done

echo -e "${GREEN}ISO seleccionada:${NC} $ISO_FILE"
echo ""

# 2. Listar unidades de almacenamiento disponibles
echo -e "${BOLD}Unidades de disco detectadas en tu Mac:${NC}"
echo "------------------------------------------------------------------"
diskutil list external physical 2>/dev/null || diskutil list
echo "------------------------------------------------------------------"
echo ""

echo -e "${RED}${BOLD}¡ATENCIÓN! NUNCA selecciones 'disk0' (es el disco interno de tu Mac).${NC}"
echo -e "Las memorias USB externas suelen ser ${BOLD}disk2, disk3 o disk4${NC}."
echo ""

read -rp "Escribe el identificador del disco USB (ejemplo: disk2 o disk3): " TARGET_DISK

# Limpiar formato
TARGET_DISK=$(echo "$TARGET_DISK" | sed 's#/dev/##; s/ //g')

if [ -z "$TARGET_DISK" ]; then
    echo -e "${RED}Identificador vacío. Abortando operación.${NC}"
    exit 1
fi

if [ "$TARGET_DISK" = "disk0" ]; then
    echo -e "${RED}${BOLD}ERROR CRÍTICO: disk0 es el sistema de arranque de tu Mac. Operación cancelada por seguridad.${NC}"
    exit 1
fi

# Verificar con diskutil
DISK_INFO=$(diskutil info "/dev/$TARGET_DISK" 2>/dev/null || true)
if [ -z "$DISK_INFO" ]; then
    echo -e "${RED}No se encontró la unidad /dev/$TARGET_DISK. Verifica con 'diskutil list'.${NC}"
    exit 1
fi

DISK_NAME=$(echo "$DISK_INFO" | grep "Device / Media Name:" | sed 's/.*Device \/ Media Name: *//')
DISK_SIZE=$(echo "$DISK_INFO" | grep "Disk Size:" | sed 's/.*Disk Size: *//')

echo ""
echo -e "${YELLOW}${BOLD}CONFIRMACIÓN DE SEGURIDAD:${NC}"
echo -e "Unidad seleccionada: ${BOLD}/dev/$TARGET_DISK${NC}"
echo -e "Nombre del dispositivo: ${BOLD}$DISK_NAME${NC}"
echo -e "Tamaño: ${BOLD}$DISK_SIZE${NC}"
echo -e "${RED}TODOS los datos en /dev/$TARGET_DISK serán completamente borrados.${NC}"
echo ""

read -rp "¿Estás absolutamente seguro de continuar? Escribe 'SI' para confirmar: " CONFIRM

if [ "$CONFIRM" != "SI" ] && [ "$CONFIRM" != "si" ] && [ "$CONFIRM" != "Si" ]; then
    echo "Operación cancelada por el usuario."
    exit 0
fi

# 3. Desmontar la unidad
echo ""
echo -e "${BLUE}Desmontando volúmenes de /dev/$TARGET_DISK...${NC}"
diskutil unmountDisk "/dev/$TARGET_DISK"

# 4. Flasheo mediante dd usando rdisk (modo raw ultra rápido en macOS)
RAW_DISK="r$TARGET_DISK"
echo -e "${BLUE}Iniciando escritura en /dev/$RAW_DISK (esto puede tardar unos minutos)...${NC}"
echo "Se solicitará la contraseña de administrador (sudo) de tu Mac para autorizar la escritura directa en el USB:"

sudo dd if="$ISO_FILE" of="/dev/$RAW_DISK" bs=4m status=progress conv=fsync

echo ""
echo -e "${BLUE}Sincronizando y expulsando USB...${NC}"
diskutil eject "/dev/$TARGET_DISK"

echo ""
echo -e "${GREEN}${BOLD}==================================================================${NC}"
echo -e "${GREEN}${BOLD}       ¡USB FLASHEADA CON ÉXITO Y LISTA PARA ARRANCAR!            ${NC}"
echo -e "${GREEN}${BOLD}==================================================================${NC}"
echo ""
echo -e "${BOLD}PASOS PARA INSTALAR EN TU SAMSUNG GALAXY BOOK FLEX2 ALPHA:${NC}"
echo "1. Conecta la USB a tu Samsung Galaxy Book Flex2 Alpha."
echo "2. Enciende la laptop y presiona repetidamente la tecla F2 (o F10) para entrar a BIOS/Boot Menu."
echo "3. En la BIOS, si Secure Boot está activado, puedes dejarlo o desactivarlo en 'Security -> Secure Boot Control'."
echo "4. En 'Boot Option Priorities', selecciona tu memoria USB UEFI como primera opción de arranque."
echo "5. Guarda y sal (F10)."
echo "6. Selecciona 'Start Bazzite-Deck Installer'."
echo "7. El instalador particionará e instalará el sistema con todos los drivers pre-configurados."
echo "8. ¡Al reiniciar entrará directamente a Steam Gaming Mode a 1080p con Antigravity preinstalado!"
echo ""
