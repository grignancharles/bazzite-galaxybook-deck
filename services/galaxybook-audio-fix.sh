#!/bin/bash
# ==============================================================================
# Script de Corrección de Audio y Altavoces Internos para Samsung Galaxy Book
# Arquitectura: Intel Tiger Lake-LP Smart Sound Technology (SOF) + Realtek ALC298
# ==============================================================================

set -u

LOG_TAG="galaxybook-audio-fix"
log() {
    logger -t "${LOG_TAG}" "$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${LOG_TAG}] $1"
}

log "Verificando inicialización de altavoces internos Samsung..."

# Esperar a que la tarjeta de sonido esté registrada por SOF
for i in {1..10}; do
    if [ -d "/proc/asound/card0" ]; then
        break
    fi
    sleep 1
done

# Activar amplificador inteligente (Smart Amp) mediante hda-verb si está disponible
if command -v hda-verb >/dev/null 2>&1; then
    # Nodos comunes del códec Realtek ALC298 en Galaxy Book para encendido de altavoces
    hda-verb /dev/snd/hwC0D0 0x20 SET_COEF_INDEX 0x1a 2>/dev/null || true
    hda-verb /dev/snd/hwC0D0 0x20 SET_PROC_COEF 0x0103 2>/dev/null || true
    hda-verb /dev/snd/hwC0D0 0x20 SET_COEF_INDEX 0x1b 2>/dev/null || true
    hda-verb /dev/snd/hwC0D0 0x20 SET_PROC_COEF 0x0203 2>/dev/null || true
    log "Verbos HDA de inicialización aplicados al códec Realtek ALC298."
fi

# Desmutear canales principales con amixer / alsamixer
if command -v amixer >/dev/null 2>&1; then
    amixer -c 0 sset Master unmute 2>/dev/null || true
    amixer -c 0 sset Speaker unmute 2>/dev/null || true
    amixer -c 0 sset Headphone unmute 2>/dev/null || true
fi

log "Inicialización de audio completada."
