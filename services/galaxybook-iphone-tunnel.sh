#!/bin/bash
# ==============================================================================
# Daemon Permanente y 100% Automático de Red para iPhone Hotspot (MagicProxy 1:1)
# Plug & Play Total: Sin botones, sin configuración manual, transparente 24/7
# ==============================================================================

set -u

if [ -x "/usr/local/bin/magicproxy-daemon" ]; then
    exec /usr/local/bin/magicproxy-daemon
elif [ -f "/usr/local/share/magicproxy/daemon.py" ]; then
    exec python3 /usr/local/share/magicproxy/daemon.py
else
    # Fallback si tun2socks estuviera suelto
    TUN_DEV="tun69"
    pkill -f "tun2socks.*$TUN_DEV" 2>/dev/null || true
    ip link set dev "$TUN_DEV" down 2>/dev/null || true
fi
