#!/bin/bash
# ==============================================================================
# Daemon de Optimización Térmica y Eléctrica (RAPL / CPU Capping / GPU Boost)
# Específico para Intel Core i7-1165G7 + Iris Xe G7 (Samsung Galaxy Book Flex2 Alpha)
# ==============================================================================

set -u

LOG_TAG="galaxybook-power-opt"
log() {
    logger -t "${LOG_TAG}" "$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${LOG_TAG}] $1"
}

log "Iniciando servicio de optimización de energía para Tiger Lake..."

# 1. Configuración de límites RAPL (Running Average Power Limit)
# PL1 (Sostenido) = 28W (28,000,000 microvatios)
# PL2 (Pico) = 35W (35,000,000 microvatios)
apply_rapl_limits() {
    local rapl_base="/sys/class/powercap/intel-rapl:0"
    if [ -d "$rapl_base" ]; then
        if [ -w "$rapl_base/constraint_0_power_limit_uw" ]; then
            echo 28000000 > "$rapl_base/constraint_0_power_limit_uw" 2>/dev/null || true
            log "RAPL PL1 fijado en 28W (28000000 uW)"
        fi
        if [ -w "$rapl_base/constraint_1_power_limit_uw" ]; then
            echo 35000000 > "$rapl_base/constraint_1_power_limit_uw" 2>/dev/null || true
            log "RAPL PL2 fijado en 35W (35000000 uW)"
        fi
    fi

    # Activar perfil de rendimiento en ACPI si está disponible (samsung-galaxybook / platform_profile)
    if [ -w "/sys/firmware/acpi/platform_profile" ]; then
        echo "performance" > /sys/firmware/acpi/platform_profile 2>/dev/null || true
        log "ACPI platform_profile establecido en 'performance'"
    fi

    # Soporte para Umbral de Carga Samsung (Protección de batería al 85%)
    for bat_thresh in /sys/class/power_supply/BAT*/charge_control_end_threshold; do
        if [ -w "$bat_thresh" ]; then
            echo 85 > "$bat_thresh" 2>/dev/null || true
            log "Límite de protección de batería Samsung fijado al 85%"
            break
        fi
    done
}

# 2. Configuración de GPU Iris Xe (Forzar rango 1100 - 1300 MHz en gaming)
apply_gpu_gaming_profile() {
    for card_dir in /sys/class/drm/card[0-9]*; do
        if [ -f "$card_dir/gt_max_freq_mhz" ] && [ -w "$card_dir/gt_max_freq_mhz" ]; then
            echo 1300 > "$card_dir/gt_max_freq_mhz" 2>/dev/null || true
            echo 1100 > "$card_dir/gt_min_freq_mhz" 2>/dev/null || true
            echo 1300 > "$card_dir/gt_boost_freq_mhz" 2>/dev/null || true
            log "GPU Iris Xe bloqueada a frecuencia de alto rendimiento (1100 - 1300 MHz)"
            break
        fi
    done
}

restore_gpu_idle_profile() {
    for card_dir in /sys/class/drm/card[0-9]*; do
        if [ -f "$card_dir/gt_min_freq_mhz" ] && [ -w "$card_dir/gt_min_freq_mhz" ]; then
            echo 400 > "$card_dir/gt_min_freq_mhz" 2>/dev/null || true
            echo 1300 > "$card_dir/gt_max_freq_mhz" 2>/dev/null || true
            break
        fi
    done
}

# 3. Limitar CPU a 3.2 GHz en gaming para no canibalizar los vatios de la GPU
apply_cpu_gaming_profile() {
    for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
        if [ -w "$cpu/cpufreq/scaling_max_freq" ]; then
            echo 3200000 > "$cpu/cpufreq/scaling_max_freq" 2>/dev/null || true
        fi
        if [ -w "$cpu/cpufreq/energy_performance_preference" ]; then
            echo "balance_performance" > "$cpu/cpufreq/energy_performance_preference" 2>/dev/null || true
        fi
    done
    log "CPU i7-1165G7 capada a 3.2 GHz para garantizar los 1300 MHz continuos de la Iris Xe"
}

restore_cpu_desktop_profile() {
    for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
        if [ -f "$cpu/cpufreq/cpuinfo_max_freq" ] && [ -w "$cpu/cpufreq/scaling_max_freq" ]; then
            max_khz=$(cat "$cpu/cpufreq/cpuinfo_max_freq" 2>/dev/null || echo 4700000)
            echo "$max_khz" > "$cpu/cpufreq/scaling_max_freq" 2>/dev/null || true
        fi
        if [ -w "$cpu/cpufreq/energy_performance_preference" ]; then
            echo "balance_power" > "$cpu/cpufreq/energy_performance_preference" 2>/dev/null || true
        fi
    done
    log "CPU i7-1165G7 restaurada al límite natural (hasta 4.7 GHz) para Modo Escritorio"
}

# Aplicar límites RAPL iniciales
apply_rapl_limits

LAST_STATE="unknown"

# Bucle de supervisión continua: detecta si la sesión Gamescope está activa
while true; do
    # Re-aplicar RAPL por si la BIOS o el firmware ACPI intenta resetearlo
    apply_rapl_limits

    # Comprobar si Gamescope o algún proceso de juego Proton está activo
    if pgrep -x "gamescope" > /dev/null || pgrep -x "gamescope-wl" > /dev/null; then
        CURRENT_STATE="gaming"
    else
        CURRENT_STATE="desktop"
    fi

    if [ "$CURRENT_STATE" != "$LAST_STATE" ]; then
        if [ "$CURRENT_STATE" = "gaming" ]; then
            log "SESIÓN GAMESCOPE DETECTADA -> Aplicando perfil de Gaming (CPU @ 3.2 GHz, GPU @ 1300 MHz)"
            apply_cpu_gaming_profile
            apply_gpu_gaming_profile
        else
            log "MODO ESCRITORIO DETECTADO -> Restaurando perfiles de bajo consumo y frecuencias dinámicas"
            restore_cpu_desktop_profile
            restore_gpu_idle_profile
        fi
        LAST_STATE="$CURRENT_STATE"
    fi

    sleep 5
done
