#!/bin/bash
# ==============================================================================
# Daemon Permanente y 100% Automático de Red para iPhone Hotspot (tun2socks)
# Plug & Play Total: Sin botones, sin configuración manual, transparente 24/7
# ==============================================================================

set -u

LOG_TAG="iphone-native-tunnel"
IPHONE_IP="172.20.10.1"
IPHONE_PORT="10808"
TUN_DEV="tun69"
TUN_IP="10.0.0.2/24"

log() {
    logger -t "${LOG_TAG}" "$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${LOG_TAG}] $1"
}

start_tunnel() {
    if ip link show "$TUN_DEV" >/dev/null 2>&1 && pgrep -f "tun2socks.*$TUN_DEV" >/dev/null 2>&1; then
        return 0
    fi

    log "Enlazando túnel permanente con el Hotspot del iPhone ($IPHONE_IP)..."

    DEFAULT_GW=$(ip route show default 2>/dev/null | awk '{print $3}' | head -n 1)
    if [ -z "$DEFAULT_GW" ]; then
        DEFAULT_GW="$IPHONE_IP"
    fi

    # 1. Crear interfaz TUN virtual
    ip tuntap add dev "$TUN_DEV" mode tun 2>/dev/null || true
    ip addr add "$TUN_IP" dev "$TUN_DEV" 2>/dev/null || true
    ip link set dev "$TUN_DEV" up

    # 2. Iniciar tun2socks sin límites y con reconexión automática
    pkill -f "tun2socks.*$TUN_DEV" 2>/dev/null || true
    /usr/bin/tun2socks -device "$TUN_DEV" -proxy "socks5://${IPHONE_IP}:${IPHONE_PORT}" -loglevel warning >/dev/null 2>&1 &
    sleep 1

    # 3. Enrutamiento directo al iPhone
    ip route add "${IPHONE_IP}/32" via "$DEFAULT_GW" 2>/dev/null || true

    # 4. Enrutar el 100% del tráfico de Linux a través del túnel
    ip route add 0.0.0.0/1 dev "$TUN_DEV" 2>/dev/null || true
    ip route add 128.0.0.0/1 dev "$TUN_DEV" 2>/dev/null || true

    # 5. DNS automático a través del túnel
    if command -v resolvectl >/dev/null 2>&1; then
        resolvectl dns "$TUN_DEV" 1.1.1.1 8.8.8.8 2>/dev/null || true
        resolvectl default-route "$TUN_DEV" true 2>/dev/null || true
    fi

    log "Conexión transparente establecida. Todo el sistema navegando por el iPhone."
}

# Supervisor de bucle infinito: mantiene el túnel levantado siempre
while true; do
    start_tunnel
    sleep 3
done
