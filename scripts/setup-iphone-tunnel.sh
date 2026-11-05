#!/bin/bash
# ==============================================================================
# Instalador de Comandos y Accesos Directos para el Túnel Nativo de iPhone
# ==============================================================================

set -euo pipefail

# Crear enlace simbólico de comando global
ln -sf /usr/libexec/galaxybook-iphone-tunnel.sh /usr/bin/iphone-tunnel
ln -sf /usr/libexec/galaxybook-iphone-tunnel.sh /usr/bin/magicproxy

mkdir -p /usr/share/applications

# Acceso directo para activar
cat << 'EOF' > /usr/share/applications/iphone-tunnel-on.desktop
[Desktop Entry]
Name=🟢 Conectar Internet iPhone
Comment=Activa el túnel SOCKS5 tun2socks para navegar por el Hotspot del iPhone
Exec=/usr/bin/iphone-tunnel start
Icon=network-wireless-symbolic
Terminal=false
Type=Application
Categories=Network;Settings;
EOF

# Acceso directo para desactivar
cat << 'EOF' > /usr/share/applications/iphone-tunnel-off.desktop
[Desktop Entry]
Name=🔴 Desconectar Internet iPhone
Comment=Desactiva el túnel SOCKS5 y restaura la red estándar
Exec=/usr/bin/iphone-tunnel stop
Icon=network-offline-symbolic
Terminal=false
Type=Application
Categories=Network;Settings;
EOF

chmod +x /usr/share/applications/iphone-tunnel-*.desktop
