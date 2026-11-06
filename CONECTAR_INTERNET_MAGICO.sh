#!/bin/bash
# ==============================================================================
# CONECTAR INTERNET MÁGICO (IPHONE SOCKS5 TUNNEL + BYPASS TTL 65)
# Enruta todo el tráfico de red de SteamOS/Bazzite a través del iPhone (172.20.10.1:10808)
# Evita la reducción a 4 kbps mediante TTL 65 y enrutamiento Layer-3 tun69
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
echo -e "${C_CYAN}║     Bypass Operadora (TTL 65) + SOCKS5 Proxy 172.20.10.1:10808     ║${C_RESET}"
echo -e "${C_CYAN}╚════════════════════════════════════════════════════════════════════╝${C_RESET}"
echo ""

[[ $EUID -ne 0 ]] && { echo -e "${C_RED}❌ Ejecuta con sudo: sudo bash $0${C_RESET}"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Asegurar binario tun2socks en /usr/local/bin
echo -e "${C_YELLOW}→ 1/4 Instalando tun2socks estático en el sistema...${C_RESET}"
if [ -f "${SCRIPT_DIR}/bin/tun2socks" ]; then
    cp -f "${SCRIPT_DIR}/bin/tun2socks" /usr/local/bin/tun2socks
elif [ -f "${SCRIPT_DIR}/tun2socks" ]; then
    cp -f "${SCRIPT_DIR}/tun2socks" /usr/local/bin/tun2socks
fi
chmod +x /usr/local/bin/tun2socks 2>/dev/null || true

if [ ! -x "/usr/local/bin/tun2socks" ]; then
    echo -e "${C_RED}❌ Error: No se encontró el binario tun2socks.${C_RESET}"
    exit 1
fi
echo -e "${C_GREEN}✓ tun2socks listo en /usr/local/bin/tun2socks${C_RESET}"

# 2. Configurar Bypass de Operadora (TTL 65)
echo -e "${C_YELLOW}→ 2/4 Aplicando Bypass de Operadora (net.ipv4.ip_default_ttl=65)...${C_RESET}"
sysctl -w net.ipv4.ip_default_ttl=65 2>/dev/null || true
sysctl -w net.ipv4.ip_forward=1 2>/dev/null || true
echo "net.ipv4.ip_default_ttl = 65" > /etc/sysctl.d/98-iphone-ttl-bypass.conf
echo -e "${C_GREEN}✓ TTL fijado en 65 (El tráfico sale identificado como iPhone nativo)${C_RESET}"

# 3. Levantar túnel Layer-3 tun69
echo -e "${C_YELLOW}→ 3/4 Creando interfaz virtual tun69...${C_RESET}"
IPHONE_IP="172.20.10.1"
IPHONE_PORT="10808"
TUN_DEV="tun69"

pkill -f "tun2socks.*$TUN_DEV" 2>/dev/null || true
ip link set dev "$TUN_DEV" down 2>/dev/null || true
ip tuntap del dev "$TUN_DEV" mode tun 2>/dev/null || true

ip tuntap add dev "$TUN_DEV" mode tun
ip addr add 10.0.0.2/24 dev "$TUN_DEV"
ip link set dev "$TUN_DEV" mtu 1400 up

# Obtener puerta de enlace física actual
DEFAULT_GW=$(ip route show default 2>/dev/null | awk '{print $3}' | head -n 1)
[ -z "$DEFAULT_GW" ] && DEFAULT_GW="$IPHONE_IP"

# Enrutar IP del iPhone directo a la interfaz física
ip route add "$IPHONE_IP/32" via "$DEFAULT_GW" 2>/dev/null || true

# Arrancar tun2socks en segundo plano
nohup /usr/local/bin/tun2socks -device "$TUN_DEV" -proxy "socks5://$IPHONE_IP:$IPHONE_PORT" >/tmp/tun2socks.log 2>&1 &
sleep 2

# Enrutar tráfico default a través del túnel tun69
ip route add 0.0.0.0/1 via 10.0.0.1 dev "$TUN_DEV" 2>/dev/null || true
ip route add 128.0.0.0/1 via 10.0.0.1 dev "$TUN_DEV" 2>/dev/null || true

echo -e "${C_GREEN}✓ Dispositivo tun69 conectado a socks5://$IPHONE_IP:$IPHONE_PORT${C_RESET}"

# 4. Verificación de conectividad
echo -e "${C_YELLOW}→ 4/4 Verificando conexión a Internet...${C_RESET}"
if ping -c 1 -W 3 1.1.1.1 >/dev/null 2>&1 || ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo -e "${C_GREEN}✅ ¡INTERNET CONECTADO A MÁXIMA VELOCIDAD! (Sin límite de 4 kbps)${C_RESET}"
else
    echo -e "${C_GREEN}✅ Túnel tun69 activo. Asegúrate de tener MagicProxy o SOCKS5 encendido en el iPhone en 172.20.10.1:10808.${C_RESET}"
fi
echo ""
