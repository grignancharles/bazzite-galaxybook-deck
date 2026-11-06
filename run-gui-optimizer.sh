#!/usr/bin/env bash
# ==============================================================================
# OPTIMIZADOR GRÁFICO AUTOMÁTICO 100% OFFLINE - GALAXY BOOK FLEX2 ALPHA
# Doble clic y listo: interfaz visual con Zenity, funciona SIN internet y con internet
# ==============================================================================

set -e
export DISPLAY="${DISPLAY:-:0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Verificar permisos de administrador
run_as_root() {
    local cmd="$1"
    if command -v pkexec >/dev/null 2>&1; then
        pkexec bash -c "$cmd"
    elif command -v sudo >/dev/null 2>&1; then
        sudo bash -c "$cmd"
    else
        bash -c "$cmd"
    fi
}

show_gui() {
    zenity --question \
        --title="Optimizador Galaxy Book Flex2 Alpha" \
        --text="<b>¿Deseas aplicar todas las optimizaciones ahora?</b>\n\n• Reparar tecla Enter (usar tecla '\\')\n• Perfil de energía 24/7 (CPU 3.2 GHz / GPU 1300 MHz)\n• Bloqueo a 30 FPS tipo consola (MangoHud) + Atajo <b>Alt + 9</b>\n• Soporte para discos de Mac (<b>APFS y HFS+</b>)\n• Audio Realtek ALC298 (Bocinas activas)\n• Spoofing de VRAM a 4.5 GB\n• Gestos de trackpad estilo Mac" \
        --ok-label="Sí, Optimizar Todo" \
        --cancel-label="Cancelar" \
        --width=480 2>/dev/null

    if [ $? -ne 0 ]; then
        exit 0
    fi

    (
        echo "10"; echo "# Buscando archivos de optimización..."; sleep 1
        
        # Modo 1: Si install-all-in-one.sh está junto a este script (modo offline USB / disco)
        if [ -f "$SCRIPT_DIR/install-all-in-one.sh" ]; then
            echo "30"; echo "# Ejecutando optimizaciones (Modo Offline)..."
            run_as_root "bash '$SCRIPT_DIR/install-all-in-one.sh'"
        elif [ -f "/tmp/install-all-in-one.sh" ]; then
            echo "30"; echo "# Ejecutando optimizaciones guardadas..."
            run_as_root "bash /tmp/install-all-in-one.sh"
        else
            echo "30"; echo "# Descargando paquete maestro desde GitHub..."
            curl -sL "https://raw.githubusercontent.com/grignancharles/bazzite-galaxybook-deck/main/install-all-in-one.sh" -o "/tmp/install-all-in-one.sh"
            run_as_root "bash /tmp/install-all-in-one.sh"
        fi
        
        echo "100"; echo "# ¡Optimización completada con éxito!"
    ) | zenity --progress \
        --title="Optimizando Sistema..." \
        --text="Iniciando configuración..." \
        --percentage=0 \
        --auto-close \
        --width=420 2>/dev/null

    zenity --info \
        --title="¡Listo!" \
        --text="<b>¡Tu Galaxy Book está optimizada al 100%!</b>\n\n• Ahora puedes usar la tecla <b>'\\'</b> como Enter.\n• Presiona <b>Alt + 9</b> en juegos para ver los FPS.\n• Tus discos Mac (<b>APFS</b>) se montarán automáticamente.\n• Las bocinas, la GPU y el perfil de consola están activos." \
        --width=420 2>/dev/null
}

if command -v zenity >/dev/null 2>&1; then
    show_gui
else
    # Fallback si se ejecuta desde consola directa
    if [ -f "$SCRIPT_DIR/install-all-in-one.sh" ]; then
        run_as_root "bash '$SCRIPT_DIR/install-all-in-one.sh'"
    else
        run_as_root "curl -sL https://raw.githubusercontent.com/grignancharles/bazzite-galaxybook-deck/main/install-all-in-one.sh | bash"
    fi
fi
