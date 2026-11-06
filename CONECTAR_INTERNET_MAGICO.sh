#!/bin/bash
# ==============================================================================
# CONECTAR INTERNET MÁGICO (MAGICPROXY - PORT 1:1 DE PAIRAPP MACOS)
# Enruta todo el tráfico de red de SteamOS/Bazzite a través del iPhone mediante
# descubrimiento Bonjour mDNS (_magicproxy._tcp.local) y túnel Layer-3 tun69
# ==============================================================================

set -eu

C_RESET="\033[0m"
C_GREEN="\033[1;32m"
C_CYAN="\033[1;36m"
C_YELLOW="\033[1;33m"
C_RED="\033[1;31m"

clear
echo -e "${C_CYAN}╔════════════════════════════════════════════════════════════════════╗${C_RESET}"
echo -e "${C_CYAN}║     CONECTOR MÁGICO DE INTERNET - TÚNEL IPHONE LAYER-3 (tun69)     ║${C_RESET}"
echo -e "${C_CYAN}║       Port 1:1 de PairApp macOS (MDNSBrowser + tun2socks)          ║${C_RESET}"
echo -e "${C_CYAN}╚════════════════════════════════════════════════════════════════════╝${C_RESET}"
echo ""

[[ $EUID -ne 0 ]] && { echo -e "${C_RED}❌ Ejecuta con sudo: sudo bash $0${C_RESET}"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Asegurar binario tun2socks en /usr/local/bin
echo -e "${C_YELLOW}→ 1/4 Instalando tun2socks estático en el sistema...${C_RESET}"
mkdir -p /usr/local/bin /usr/local/share/magicproxy
if [ -f "${SCRIPT_DIR}/bin/tun2socks" ]; then
    cp -f "${SCRIPT_DIR}/bin/tun2socks" /usr/local/bin/tun2socks
elif [ -f "${SCRIPT_DIR}/tun2socks" ]; then
    cp -f "${SCRIPT_DIR}/tun2socks" /usr/local/bin/tun2socks
fi
chmod +x /usr/local/bin/tun2socks 2>/dev/null || true

# 2. Instalar paquete magicproxy-linux si existe
if [ -d "${SCRIPT_DIR}/magicproxy-linux" ]; then
    cp -rf "${SCRIPT_DIR}/magicproxy-linux/"* /usr/local/share/magicproxy/ 2>/dev/null || true
    chmod +x /usr/local/share/magicproxy/*.py /usr/local/share/magicproxy/magicproxy-cli 2>/dev/null || true
fi

# 3. Iniciar o reiniciar el demonio
echo -e "${C_YELLOW}→ 2/4 Reiniciando demonio MagicProxy...${C_RESET}"
systemctl restart galaxybook-iphone-tunnel.service 2>/dev/null || true
sleep 1

# 4. Estado de conexión
echo -e "${C_YELLOW}→ 3/4 Verificando estado del servicio...${C_RESET}"
if [ -x "/usr/local/bin/magicproxy" ]; then
    /usr/local/bin/magicproxy status
else
    python3 "${SCRIPT_DIR}/magicproxy-linux/magicproxy-cli" status 2>/dev/null || true
fi

echo ""
echo -e "${C_GREEN}✅ Demonio MagicProxy activo en segundo plano.${C_RESET}"
echo -e "${C_CYAN}Detectará tu iPhone automáticamente en cuanto abras la app MagicProxy en iOS.${C_RESET}"
echo ""
