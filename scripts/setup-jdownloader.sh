#!/bin/bash
# ==============================================================================
# Script de Instalación e Integración Nativa de JDownloader 2 en Bazzite OS
# 100% Offline: Descarga y pre-empaqueta JDownloader durante el build de la imagen
# ==============================================================================

set -euo pipefail

echo "Configurando JDownloader 2 como gestor de descargas nativo..."

# 1. Directorio del sistema inmutable para el JAR base
mkdir -p /usr/lib/jdownloader
mkdir -p /usr/share/applications
mkdir -p /usr/share/pixmaps

# 2. Descargar el archivo oficial JDownloader.jar base
curl -fsSL "http://installer.jdownloader.org/JDownloader.jar" -o /usr/lib/jdownloader/JDownloader.jar

# 3. Descargar icono oficial de JDownloader
curl -fsSL "https://upload.wikimedia.org/wikipedia/commons/d/df/JDownloader_logo.png" -o /usr/share/pixmaps/jdownloader.png 2>/dev/null || true

# 4. Crear el script lanzador global en /usr/bin/jdownloader
cat << 'EOF' > /usr/bin/jdownloader
#!/bin/bash
# Lanzador de JDownloader 2 para Bazzite OS (Inmutable)
# Usa el directorio de usuario para permitir auto-actualizaciones de plugins en /home

JD_USER_DIR="$HOME/.local/share/jdownloader"
mkdir -p "$JD_USER_DIR"

if [ ! -f "$JD_USER_DIR/JDownloader.jar" ]; then
    echo "Inicializando JDownloader en tu carpeta personal desde la imagen base..."
    cp /usr/lib/jdownloader/JDownloader.jar "$JD_USER_DIR/JDownloader.jar"
fi

cd "$JD_USER_DIR"

# Flags de optimización de renderizado de fuentes para Java Swing en Wayland/X11
exec java -Dawt.useSystemAAFontSettings=on \
          -Dswing.aatext=true \
          -Dsun.java2d.opengl=true \
          -Xms128m \
          -Xmx1024m \
          -jar "$JD_USER_DIR/JDownloader.jar" "$@"
EOF

chmod +x /usr/bin/jdownloader

# 5. Crear el archivo .desktop para Modo Escritorio y Modo Juego
cat << 'EOF' > /usr/share/applications/jdownloader.desktop
[Desktop Entry]
Name=JDownloader 2
Comment=Gestor de descargas avanzado multiplataforma
Exec=/usr/bin/jdownloader
Icon=jdownloader
Terminal=false
Type=Application
Categories=Network;FileTransfer;Utility;
Keywords=download;manager;jdownloader;torrent;mega;
EOF

chmod +x /usr/share/applications/jdownloader.desktop

echo "JDownloader 2 pre-instalado y configurado exitosamente."
