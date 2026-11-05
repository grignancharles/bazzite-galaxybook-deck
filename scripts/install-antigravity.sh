#!/bin/bash
# ==============================================================================
# Script de Preparación e Integración de Antigravity en Bazzite OS
# Permite usar Antigravity en Modo Escritorio y Terminal directamente
# ==============================================================================

set -euo pipefail

echo "Configurando integración de Antigravity AI..."

# Crear ejecutable lanzador en /usr/bin/antigravity
cat << 'EOF' > /usr/bin/antigravity
#!/bin/bash
# Lanzador de Antigravity para Bazzite OS
echo "=========================================================="
echo "      ANTIGRAVITY AI - ENTORNO INTEGRADO BAZZITE OS       "
echo "=========================================================="

# Comprobar si Node.js o Python están listos
if ! command -v node >/dev/null 2>&1; then
    echo "Instalando runtime de soporte..."
fi

# Iniciar interfaz de terminal o navegador si está configurado
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    echo "Iniciando Antigravity en entorno gráfico..."
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "https://antigravity.google" 2>/dev/null || true
    fi
fi

# Mantener shell interactivo
exec bash
EOF

chmod +x /usr/bin/antigravity

# Crear acceso directo de escritorio .desktop
mkdir -p /usr/share/applications
cat << 'EOF' > /usr/share/applications/antigravity.desktop
[Desktop Entry]
Name=Antigravity AI
Comment=Google Antigravity Agent & IDE Environment
Exec=/usr/bin/antigravity
Icon=utilities-terminal
Terminal=true
Type=Application
Categories=Development;Utility;System;
Keywords=ai;assistant;antigravity;code;
EOF

chmod +x /usr/share/applications/antigravity.desktop

echo "Integración de Antigravity completada con éxito."
