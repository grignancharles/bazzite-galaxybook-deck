#!/bin/bash
# ==============================================================================
# Daemon Automático de Inyección Quirúrgica de Juegos para Bazzite OS
# Monitorea la creación de prefijos de Proton e inyecta configs optimizadas
# ==============================================================================

set -u

LOG_TAG="galaxybook-game-injector"
TEMPLATES_DIR="/usr/share/game-optimizations/templates"

log() {
    logger -t "${LOG_TAG}" "$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${LOG_TAG}] $1"
}

log "Iniciando monitor de inyección de juegos..."

find_steam_compat_dirs() {
    for user_home in /home/*; do
        if [ -d "$user_home/.steam/steam/steamapps/compatdata" ]; then
            echo "$user_home/.steam/steam/steamapps/compatdata"
        fi
        if [ -d "$user_home/.local/share/Steam/steamapps/compatdata" ]; then
            echo "$user_home/.local/share/Steam/steamapps/compatdata"
        fi
    done
}

inject_silent_hill_2() {
    local pfx_dir="$1"
    local target_cfg="$pfx_dir/pfx/drive_c/users/steamuser/AppData/Local/SilentHill2/Saved/Config/Windows"
    mkdir -p "$target_cfg"
    if [ ! -f "$target_cfg/.injected_by_galaxybook" ]; then
        log "Inyectando optimizaciones (Sin Lumen/VSM) para Silent Hill 2 (AppID 2124490)..."
        cp "$TEMPLATES_DIR/2124490_silent_hill_2/Engine.ini" "$target_cfg/Engine.ini" 2>/dev/null || true
        cp "$TEMPLATES_DIR/2124490_silent_hill_2/dxvk.conf" "$pfx_dir/pfx/dxvk.conf" 2>/dev/null || true
        touch "$target_cfg/.injected_by_galaxybook"
        log "Silent Hill 2 optimizado con éxito."
    fi
}

inject_the_last_of_us() {
    local pfx_dir="$1"
    local flag_file="$pfx_dir/pfx/.injected_by_galaxybook"
    if [ ! -f "$flag_file" ]; then
        log "Inyectando optimizaciones DXVK/VKD3D para The Last of Us (AppID 1888930)..."
        cp "$TEMPLATES_DIR/1888930_the_last_of_us/dxvk.conf" "$pfx_dir/pfx/dxvk.conf" 2>/dev/null || true
        touch "$flag_file"
        log "The Last of Us optimizado con éxito."
    fi
}

inject_re_engine() {
    local pfx_dir="$1"
    local app_id="$2"
    local flag_file="$pfx_dir/pfx/.injected_by_galaxybook"
    if [ ! -f "$flag_file" ]; then
        log "Inyectando configuración para RE Engine (AppID $app_id)..."
        cp "$TEMPLATES_DIR/resident_evil/config.ini" "$pfx_dir/pfx/drive_c/config.ini" 2>/dev/null || true
        touch "$flag_file"
        log "RE Engine (AppID $app_id) optimizado con éxito."
    fi
}

inject_horizon() {
    local pfx_dir="$1"
    local target_cfg="$pfx_dir/pfx/drive_c/users/steamuser/Documents/Horizon Forbidden West Complete Edition"
    mkdir -p "$target_cfg"
    if [ ! -f "$target_cfg/.injected_by_galaxybook" ]; then
        log "Inyectando configuración para Horizon Forbidden West (AppID 2420110)..."
        cp "$TEMPLATES_DIR/2420110_horizon_forbidden_west/graphic_settings.json" "$target_cfg/graphic_settings.json" 2>/dev/null || true
        touch "$target_cfg/.injected_by_galaxybook"
        log "Horizon Forbidden West optimizado con éxito."
    fi
}

while true; do
    for compat_root in $(find_steam_compat_dirs); do
        # Silent Hill 2
        if [ -d "$compat_root/2124490" ]; then
            inject_silent_hill_2 "$compat_root/2124490"
        fi

        # The Last of Us Part 1
        if [ -d "$compat_root/1888930" ]; then
            inject_the_last_of_us "$compat_root/1888930"
        fi

        # Resident Evil Games (RE2: 883710, RE3: 952060, RE4: 2050650, RE7: 418370, RE Village: 1196590)
        for re_id in 883710 952060 2050650 418370 1196590; do
            if [ -d "$compat_root/$re_id" ]; then
                inject_re_engine "$compat_root/$re_id" "$re_id"
            fi
        done

        # Horizon Forbidden West
        if [ -d "$compat_root/2420110" ]; then
            inject_horizon "$compat_root/2420110"
        fi
    done

    sleep 10
done
