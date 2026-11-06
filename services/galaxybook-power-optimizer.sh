#!/bin/bash
# ==============================================================================
# Daemon de Optimización Térmica y Eléctrica PERMANENTE 24/7
# Específico para Intel Core i7-1165G7 + Iris Xe G7 96EUs (Samsung Galaxy Book Flex2 Alpha)
# ==============================================================================
# PERFIL FIJO PERMANENTE:
# 1. CPU capada SIEMPRE a 3.2 GHz (10W máx) -> CERO canibalismo eléctrico a la GPU
# 2. GPU Iris Xe fijada SIEMPRE a 1100 - 1300 MHz continuos (18W limpios)
# 3. RAPL PL1 = 28W continuo / PL2 = 35W pico
# 4. Protección de batería Samsung limitada al 85%
# ==============================================================================

set -u

LOG_TAG="galaxybook-power-opt"
log() {
    logger -t "${LOG_TAG}" "$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${LOG_TAG}] $1"
}

log "Aplicando Perfil Fijo Definitivo 24/7 (28W sostenido, CPU 3.2GHz, GPU 1300MHz)..."

# 1. Límites Eléctricos RAPL (28W sostenido, 35W pico)
apply_rapl_limits() {
    local rapl_base="/sys/class/powercap/intel-rapl:0"
    if [ -d "$rapl_base" ]; then
        if [ -w "$rapl_base/constraint_0_power_limit_uw" ]; then
            echo 28000000 > "$rapl_base/constraint_0_power_limit_uw" 2>/dev/null || true
        fi
        if [ -w "$rapl_base/constraint_1_power_limit_uw" ]; then
            echo 35000000 > "$rapl_base/constraint_1_power_limit_uw" 2>/dev/null || true
        fi
    fi

    # ACPI performance profile
    if [ -w "/sys/firmware/acpi/platform_profile" ]; then
        echo "performance" > /sys/firmware/acpi/platform_profile 2>/dev/null || true
    fi

    # Protección de batería al 85%
    for bat_thresh in /sys/class/power_supply/BAT*/charge_control_end_threshold; do
        if [ -w "$bat_thresh" ]; then
            echo 85 > "$bat_thresh" 2>/dev/null || true
            break
        fi
    done
}

# 2. Bloqueo Permanente de GPU Iris Xe a 1100 - 1300 MHz
apply_gpu_profile() {
    for card_dir in /sys/class/drm/card[0-9]*; do
        if [ -f "$card_dir/gt_max_freq_mhz" ] && [ -w "$card_dir/gt_max_freq_mhz" ]; then
            echo 1300 > "$card_dir/gt_max_freq_mhz" 2>/dev/null || true
            echo 1100 > "$card_dir/gt_min_freq_mhz" 2>/dev/null || true
            echo 1300 > "$card_dir/gt_boost_freq_mhz" 2>/dev/null || true
            break
        fi
    done
}

# 3. Bloqueo Permanente de CPU a 3.2 GHz (Willow Cove IPC alto con bajo consumo)
apply_cpu_profile() {
    for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
        if [ -w "$cpu/cpufreq/scaling_max_freq" ]; then
            echo 3200000 > "$cpu/cpufreq/scaling_max_freq" 2>/dev/null || true
        fi
        if [ -w "$cpu/cpufreq/scaling_min_freq" ]; then
            echo 1200000 > "$cpu/cpufreq/scaling_min_freq" 2>/dev/null || true
        fi
        if [ -w "$cpu/cpufreq/energy_performance_preference" ]; then
            echo "balance_performance" > "$cpu/cpufreq/energy_performance_preference" 2>/dev/null || true
        fi
    done
}

# Aplicar de inmediato
apply_rapl_limits
apply_gpu_profile
apply_cpu_profile
log "Perfil de potencia permanente activo. Frecuencias y voltajes bloqueados."

# Re-aplicar en bucle cada 15s por si el firmware de la BIOS intenta resetear los límites
while true; do
    apply_rapl_limits
    apply_gpu_profile
    apply_cpu_profile
    sleep 15
done
