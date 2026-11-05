#!/bin/bash
# ==============================================================================
# Script de Inyección de OptiScaler con Intel XeSS (Aceleración DP4a por Hardware)
# Para juegos con soporte DLSS/FSR en Intel Iris Xe G7 (96 EUs)
# ==============================================================================

set -euo pipefail

GAME_DIR="${1:-}"

if [ -z "$GAME_DIR" ] || [ ! -d "$GAME_DIR" ]; then
    echo "Uso: $0 <directorio_del_juego>"
    exit 1
fi

echo "Inyectando OptiScaler (XeSS DP4a) en: $GAME_DIR"

# Configuración de OptiScaler para forzar backend XeSS DP4a
cat << 'EOF' > "$GAME_DIR/OptiScaler.ini"
[General]
; Forzar el backend XeSS nativo con soporte DP4a
Backend=xess

[XeSS]
; Modo de compilación DP4a para GPUs sin matrices XMX (Iris Xe Gen12)
BuildPipelines=true
NetworkModel=1

[Upscaling]
; Escala interna: Balanced (60%) o Performance (50%)
Quality=Balanced
Sharpness=0.4
OverrideAutoExposure=true

[Framerate]
TargetFPS=30
SyncInterval=1
EOF

echo "OptiScaler configurado correctamente con Intel XeSS DP4a."
