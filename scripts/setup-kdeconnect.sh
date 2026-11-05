#!/bin/bash
# ==============================================================================
# Configuración de KDE Connect para Portapapeles Compartido (iPhone / Mac / Bazzite)
# ==============================================================================

set -euo pipefail

echo "Configurando reglas de red para KDE Connect..."

# Abrir puertos de KDE Connect (1714-1764 TCP/UDP) en el firewall si firewalld está activo
if [ -d "/usr/lib/firewalld/services" ]; then
    mkdir -p /etc/firewalld/services 2>/dev/null || true
fi

# Acceso directo para emparejar dispositivos rápidamente desde el menú
mkdir -p /usr/share/applications
cat << 'EOF' > /usr/share/applications/kdeconnect-settings.desktop
[Desktop Entry]
Name=Portapapeles Universal (KDE Connect)
Comment=Sincroniza portapapeles y archivos entre tu iPhone, MacBook y esta laptop
Exec=kdeconnect-settings
Icon=kdeconnect
Terminal=false
Type=Application
Categories=Settings;Network;
EOF

chmod +x /usr/share/applications/kdeconnect-settings.desktop
