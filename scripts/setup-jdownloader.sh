#!/bin/bash
# ==============================================================================
# Script de Instalación e Integración Nativa de JDownloader 2 en Bazzite OS
# 100% Offline: Descarga y pre-empaqueta JDownloader y OpenJDK 21 durante el build
# ==============================================================================

set -euo pipefail

echo "Configurando JDownloader 2 y entorno Java 21..."

# 1. Instalar OpenJDK 21 JRE oficial de Temurin de forma autónoma
mkdir -p /usr/lib/jvm
echo "Descargando OpenJDK 21 JRE autónomo..."
curl -fsSL "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.6%2B7/OpenJDK21U-jre_x64_linux_hotspot_21.0.6_7.tar.gz" -o /tmp/jre21.tar.gz
tar -xzf /tmp/jre21.tar.gz -C /usr/lib/jvm/
mv /usr/lib/jvm/jdk-21* /usr/lib/jvm/java-21-temurin || true
ln -sf /usr/lib/jvm/java-21-temurin/bin/java /usr/bin/java
rm -f /tmp/jre21.tar.gz

# 2. Directorio del sistema inmutable para el JAR base
mkdir -p /usr/lib/jdownloader
mkdir -p /usr/share/applications
mkdir -p /usr/share/pixmaps

# 3. Descargar el archivo oficial JDownloader.jar base
curl -fsSL "http://installer.jdownloader.org/JDownloader.jar" -o /usr/lib/jdownloader/JDownloader.jar

# 4. Descargar icono oficial de JDownloader
curl -fsSL "https://upload.wikimedia.org/wikipedia/commons/d/df/JDownloader_logo.png" -o /usr/share/pixmaps/jdownloader.png 2>/dev/null || true

# 5. Crear el script lanzador global en /usr/bin/jdownloader
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

exec /usr/bin/java -Dawt.useSystemAAFontSettings=on \
                   -Dswing.aatext=true \
                   -Dsun.java2d.opengl=true \
                   -Xms128m \
                   -Xmx1024m \
                   -jar "$JD_USER_DIR/JDownloader.jar" "$@"
EOF

chmod +x /usr/bin/jdownloader

# 6. Crear el archivo .desktop para Modo Escritorio y Modo Juego
cat << 'EOF' > /usr/share/applications/jdownloader.desktop
[Desktop Entry]
Name=JDownloader 2
Comment=Gestor de descargas avanzado multiplataforma
Exec=/usr/bin/jdownloader
Icon=/usr/share/pixmaps/jdownloader.png
Terminal=false
Type=Application
Categories=Network;FileTransfer;Utility;
Keywords=download;manager;jdownloader;torrent;mega;
EOF

chmod +x /usr/share/applications/jdownloader.desktop

echo "JDownloader 2 y Java 21 pre-instalados y configurados exitosamente."
