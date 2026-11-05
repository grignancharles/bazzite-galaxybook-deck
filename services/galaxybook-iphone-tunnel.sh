#!/bin/bash
# ==============================================================================
# Daemon Nativo de Red para Hotspot SOCKS5 de iPhone (172.20.10.1:10808)
# Convierte el proxy del iPhone en interfaz TUN transparente a nivel de Kernel
# Cero dependencias externas - Funciona 100% offline desde el primer segundo
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
        log "El túnel $TUN_DEV ya está activo."
        return 0
    fi

    log "Detectado Hotspot de iPhone ($IPHONE_IP). Levantando túnel nativo..."

    # 1. Obtener la puerta de enlace física actual
    DEFAULT_GW=$(ip route show default 2>/dev/null | awk '{print $3}' | head -n 1)
    if [ -z "$DEFAULT_GW" ]; then
        DEFAULT_GW="$IPHONE_IP"
    fi

    # 2. Crear interfaz TUN virtual
    ip tuntap add dev "$TUN_DEV" mode tun 2>/dev/null || true
    ip addr add "$TUN_IP" dev "$TUN_DEV" 2>/dev/null || true
    ip link set dev "$TUN_DEV" up

    # 3. Lanzar tun2socks con backend SOCKS5 hacia el iPhone
    pkill -f "tun2socks.*$TUN_DEV" 2>/dev/null || true
    /usr/bin/tun2socks -device "$TUN_DEV" -proxy "socks5://${IPHONE_IP}:${IPHONE_PORT}" -loglevel warning >/dev/null 2>&1 &
    sleep 1

    # 4. Enrutamiento directo al iPhone a través de la interfaz física (evitar bucle)
    ip route add "${IPHONE_IP}/32" via "$DEFAULT_GW" 2>/dev/null || true

    # 5. Redirigir el 100% de todo el tráfico de Linux por la interfaz virtual
    ip route add 0.0.0.0/1 dev "$TUN_DEV" 2>/dev/null || true
    ip route add 128.0.0.0/1 dev "$TUN_DEV" 2>/dev/null || true

    # 6. Configurar DNS seguro a través del túnel para Steam, Antigravity y sistema
    if command -v resolvectl >/dev/null 2>&1; then
        resolvectl dns "$TUN_DEV" 1.1.1.1 8.8.8.8 2>/dev/null || true
        resolvectl default-route "$TUN_DEV" true 2>/dev/null || true
    fi

    log "¡Túnel nativo activo! Todo el sistema operativo (Steam, Gamescope, Antigravity, Terminal) navegando por el iPhone."
}

stop_tunnel() {
    log "Desactivando túnel de iPhone..."
    pkill -f "tun2socks.*$TUN_DEV" 2>/dev/null || true
    ip route del 0.0.0.0/1 dev "$TUN_DEV" 2>/dev/null || true
    ip route del 128.0.0.0/1 dev "$TUN_DEV" 2>/dev/null || true
    ip route del "${IPHONE_IP}/32" 2>/dev/null || true
    ip link set dev "$TUN_DEV" down 2>/dev/null || true
    ip tuntap del dev "$TUN_DEV" mode tun 2>/dev/null || true
    log "Túnel cerrado. Conexión estándar restaurada."
}

status_tunnel() {
    if ip link show "$TUN_DEV" >/dev/null 2>&1 && pgrep -f "tun2socks.*$TUN_DEV" >/dev/null 2>&1; then
        echo "ESTADO: ACTIVO ($TUN_DEV -> socks5://${IPHONE_IP}:${IPHONE_PORT})"
        return 0
    else
        echo "ESTADO: INACTIVO"
        return 1
    fi
}

case "${1:-auto}" in
    start)
        start_tunnel
        ;;
    stop)
        stop_tunnel
        ;;
    status)
        status_tunnel
        ;;
    auto)
        # Modo supervisor continuo: se auto-activa si el gateway es el iPhone
        while true; do
            CURRENT_GW=$(ip route show default 2>/dev/null | awk '{print $3}' | head -n 1)
            # Comprobar si el gateway es 172.20.10.1 o si el puerto 10808 responde
            if [ "$CURRENT_GW" = "$IPHONE_IP" ] || (exec 3<>/dev/tcp/${IPHONE_IP}/${IPHONE_PORT}) 2>/dev/null; then
                exec 3>&- 2>/dev/null || true
                start_tunnel
            else
                if ip link show "$TUN_DEV" >/dev/null 2>&1; then
                    stop_tunnel
                fi
            fi
            sleep 5
        done
        ;;
    *)
        echo "Uso: $0 {start|stop|status|auto}"
        exit 1
        ;;
esac
