#!/bin/bash
# ==============================================================================
# Script de Instalación Automatizada de Decky Loader + Plugins para Tiger Lake
# ==============================================================================

set -euo pipefail

echo "Configurando Decky Loader en Bazzite..."

# Descarga oficial e instalación desatendida de Decky Loader
export DEBIAN_FRONTEND=noninteractive
curl -L https://github.com/SteamDeckHomebrew/decky-installer/releases/latest/download/install_release.sh | sh || true

echo "Decky Loader configurado. Los plugins PowerControl y OptiScaler se pueden sincronizar en el primer arranque."
