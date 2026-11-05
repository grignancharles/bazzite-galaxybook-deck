#!/bin/bash
# ==============================================================================
# Script de Configuración del Lector de Huellas para Samsung Galaxy Book
# Compatible con sensores EgisTec (1c7a:*), FocalTech (2808:*) y Elan (04f3:*)
# ==============================================================================

set -euo pipefail

echo "Configurando soporte para lector de huellas biométrico..."

# 1. Habilitar la característica de huellas en PAM mediante authselect
if command -v authselect >/dev/null 2>&1; then
    authselect enable-feature with-fingerprint 2>/dev/null || true
    echo "PAM authselect: Característica 'with-fingerprint' habilitada."
fi

# 2. Crear script amigable para registrar huellas con un solo comando o clic
cat << 'EOF' > /usr/bin/galaxybook-enroll-fingerprint
#!/bin/bash
echo "=========================================================="
echo "    REGISTRO DE HUELLA DACTILAR - SAMSUNG GALAXY BOOK    "
echo "=========================================================="
echo ""
echo "Identificando sensor USB..."
FP_DEV=$(lsusb | grep -iE "fingerprint|egis|1c7a|2808|04f3" || true)

if [ -n "$FP_DEV" ]; then
    echo "Sensor detectado: $FP_DEV"
else
    echo "Buscando lector de huellas en el bus USB..."
fi

echo ""
echo "Iniciando registro de tu dedo índice derecho..."
echo "Pasa o presiona tu dedo varias veces sobre el sensor del teclado:"
echo ""

fprintd-enroll "$USER"

echo ""
echo "¡Huella registrada con éxito! Ahora puedes iniciar sesión y usar 'sudo' con tu huella."
EOF

chmod +x /usr/bin/galaxybook-enroll-fingerprint

# 3. Crear acceso directo de escritorio para registrar huellas fácilmente
mkdir -p /usr/share/applications
cat << 'EOF' > /usr/share/applications/galaxybook-enroll-fingerprint.desktop
[Desktop Entry]
Name=Registrar Huella Dactilar
Comment=Configura el lector de huellas de tu Samsung Galaxy Book
Exec=/usr/bin/galaxybook-enroll-fingerprint
Icon=dialog-password
Terminal=true
Type=Application
Categories=Settings;System;
EOF

chmod +x /usr/share/applications/galaxybook-enroll-fingerprint.desktop

echo "Soporte biométrico y asistente de registro configurados."
