#!/bin/bash
# ==============================================================================
# GALAXY BOOK AGGRESSIVE GAME BOOSTER & PROCESS TRIMMER DAEMON
# Limpieza radical de RAM, congelamiento de procesos en segundo plano y
# Prioridad Real-Time para el juego activo (Steam / Gamescope / Proton)
# ==============================================================================

set -u

LOG_TAG="galaxybook-booster"
log() { logger -t "${LOG_TAG}" "$1"; echo "[$(date '+%H:%M:%S')] [BOOSTER] $1"; }

BACKGROUND_SERVICES=(
    "packagekit"
    "cups"
    "cups-browsed"
    "geoclue"
)

BACKGROUND_PROCESSES=(
    "baloo_file"
    "tracker-miner-fs"
    "tracker-extract"
    "evolution-calendar-factory"
    "evolution-addressbook-factory"
)

# 1. Función que detecta si hay un juego activo
is_game_running() {
    pgrep -f "pressure-vessel|wine64-preloader|wineserver|steamapps/common" >/dev/null 2>&1
}

# 2. Función de limpieza y aislamiento cuando inicia un juego
boost_game_start() {
    log "🚀 ¡JUEGO DETECTADO! Activando Modo Competitivo / Aislamiento Total..."

    # A. Suspender indexadores y procesos pesados de fondo para no tocar la CPU
    for proc in "${BACKGROUND_PROCESSES[@]}"; do
        pkill -STOP -f "$proc" 2>/dev/null || true
    done

    # B. Pausar servicios prescindibles
    for srv in "${BACKGROUND_SERVICES[@]}"; do
        systemctl stop "$srv.service" 2>/dev/null || true
    done

    # C. Limpieza masiva de cachés en RAM para liberar el bus LPDDR4x
    sync
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
    echo 1 > /proc/sys/vm/compact_memory 2>/dev/null || true
    log "✓ Memoria RAM y buffers purgados. Máxima VRAM unificada disponible."

    # D. Prioridad de CPU Real-Time y Nice -10 para los hilos del juego
    for game_pid in $(pgrep -f "pressure-vessel|wine64-preloader|steamapps/common"); do
        renice -n -10 -p "$game_pid" 2>/dev/null || true
        ionice -c 1 -n 0 -p "$game_pid" 2>/dev/null || true
    done
    log "✓ Prioridad de CPU e I/O en tiempo real asignada al juego."
}

# 3. Función de restauración cuando el juego se cierra
boost_game_stop() {
    log "🏁 Juego cerrado. Restaurando servicios del sistema y procesos de fondo..."

    # Reanudar procesos congelados
    for proc in "${BACKGROUND_PROCESSES[@]}"; do
        pkill -CONT -f "$proc" 2>/dev/null || true
    done

    # Reanudar servicios del sistema
    for srv in "${BACKGROUND_SERVICES[@]}"; do
        systemctl start "$srv.service" 2>/dev/null || true
    done
    log "✓ Sistema restaurado al estado de escritorio normal."
}

IS_BOOSTED=0

while true; do
    if is_game_running; then
        if [ "$IS_BOOSTED" -eq 0 ]; then
            boost_game_start
            IS_BOOSTED=1
        fi
    else
        if [ "$IS_BOOSTED" -eq 1 ]; then
            boost_game_stop
            IS_BOOSTED=0
        fi
    fi
    sleep 3
done
