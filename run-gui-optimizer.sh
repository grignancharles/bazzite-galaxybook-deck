#!/usr/bin/env bash
# ==============================================================================
# OPTIMIZADOR GRÁFICO AUTOMÁTICO - GALAXY BOOK FLEX2 ALPHA
# Doble clic y listo: interfaz visual con Zenity y ejecución con permisos de admin
# ==============================================================================

set -e

# Asegurar entorno visual
export DISPLAY="${DISPLAY:-:0}"

if command -v zenity >/dev/null 2>&1; then
    zenity --question \
        --title="Optimizador Galaxy Book Flex2 Alpha" \
        --text="<b>¿Deseas aplicar todas las optimizaciones ahora?</b>\n\n• Reparar tecla Enter (usar tecla '\\')\n• Perfil de energía 24/7 (CPU 3.2 GHz / GPU 1300 MHz)\n• Bloqueo a 30 FPS tipo consola (MangoHud)\n• Audio Realtek ALC298 (Bocinas activas)\n• Spoofing de VRAM a 4.5 GB\n• Gestos de trackpad estilo Mac" \
        --ok-label="Sí, Optimizar Todo" \
        --cancel-label="Cancelar" \
        --width=450 2>/dev/null

    if [ $? -ne 0 ]; then
        exit 0
    fi

    # Ejecutar con pkexec o sudo a través de una barra de progreso visual
    (
        echo "10"; echo "# Descargando optimizador maestro..."; sleep 1
        TMP_SCRIPT="/tmp/install-all-in-one.sh"
        curl -sL "https://raw.githubusercontent.com/grignancharles/bazzite-galaxybook-deck/main/install-all-in-one.sh" -o "$TMP_SCRIPT"
        chmod +x "$TMP_SCRIPT"
        
        echo "30"; echo "# Aplicando remapeo de tecla Enter y perfil de energía..."; sleep 1
        if command -v pkexec >/dev/null 2>&1; then
            pkexec bash "$TMP_SCRIPT"
        else
            sudo bash "$TMP_SCRIPT"
        fi
        
        echo "100"; echo "# ¡Optimización completada con éxito!"
    ) | zenity --progress \
        --title="Optimizando Sistema..." \
        --text="Iniciando configuración..." \
        --percentage=0 \
        --auto-close \
        --width=400 2>/dev/null

    zenity --info \
        --title="¡Listo!" \
        --text="<b>¡Tu Galaxy Book está optimizada al 100%!</b>\n\n• Ahora puedes usar la tecla <b>'\\'</b> como Enter.\n• Las bocinas, la GPU y el perfil de consola están activos." \
        --width=380 2>/dev/null
else
    # Fallback si por alguna razón no hay Zenity: abrir terminal directamente
    if command -v ptyxis >/dev/null 2>&1; then
        ptyxis -- bash -c "curl -sL https://raw.githubusercontent.com/grignancharles/bazzite-galaxybook-deck/main/install-all-in-one.sh | sudo bash; echo 'Presiona Enter para salir...'; read"
    elif command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal -- bash -c "curl -sL https://raw.githubusercontent.com/grignancharles/bazzite-galaxybook-deck/main/install-all-in-one.sh | sudo bash; echo 'Presiona Enter para salir...'; read"
    else
        xterm -e "curl -sL https://raw.githubusercontent.com/grignancharles/bazzite-galaxybook-deck/main/install-all-in-one.sh | sudo bash"
    fi
fi
