#!/bin/bash
# ==============================================================================
# Script de Compilación Local OCI con Podman/Docker (macOS M1 -> linux/amd64)
# ==============================================================================

set -euo pipefail

IMAGE_NAME="bazzite-galaxybook-deck:latest"

echo "=========================================================="
echo "  COMPILADOR LOCAL DE IMAGEN BAZZITE (GALAXY BOOK FLEX2)  "
echo "=========================================================="

if command -v podman >/dev/null 2>&1; then
    BUILDER="podman"
elif command -v docker >/dev/null 2>&1; then
    BUILDER="docker"
else
    echo "ERROR: Ni 'podman' ni 'docker' están instalados."
    echo "Recomendación: Usa GitHub Actions (.github/workflows/build-iso.yml) para compilar en la nube sin gastar batería ni RAM."
    exit 1
fi

echo "Usando $BUILDER con emulación cruzada para arquitectura x86_64 (linux/amd64)..."
$BUILDER build --platform linux/amd64 -t "$IMAGE_NAME" -f Containerfile .

echo "Imagen construida localmente: $IMAGE_NAME"
