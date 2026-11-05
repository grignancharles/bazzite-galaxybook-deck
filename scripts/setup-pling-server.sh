#!/usr/bin/env bash
# ==============================================================================
# Script de integración de Pling Server 2D para Bazzite OS
# ==============================================================================
set -euo pipefail

echo "Configurando Pling Server 2D para Meta Quest..."

if [ -d "/tmp/pling-server-linux" ]; then
    bash /tmp/pling-server-linux/install.sh
fi

echo "Pling Server 2D configurado con éxito."
