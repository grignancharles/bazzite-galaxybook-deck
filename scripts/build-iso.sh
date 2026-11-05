#!/bin/bash
set -euxo pipefail

REPO_OWNER="${1:-grignancharles}"
WORK_DIR="/work"

echo "=== 1. Instalando herramientas de Fedora ==="
dnf install -y lorax curl

echo "=== 2. Descargando Fedora 41 Everything Netinst oficial (944 MB) ==="
curl -Lo /tmp/boot.iso "https://archives.fedoraproject.org/pub/archive/fedora/linux/releases/41/Everything/x86_64/iso/Fedora-Everything-netinst-x86_64-41-1.4.iso"

echo "=== 3. Creando archivo Kickstart ==="
cat > "${WORK_DIR}/galaxybook.ks" << EOF
text
keyboard us
lang en_US.UTF-8
timezone America/New_York
network --bootproto=dhcp --device=link --activate

# Despliegue de la imagen Bazzite personalizada con todas las optimizaciones
ostreecontainer --url=ghcr.io/${REPO_OWNER}/bazzite-galaxybook-deck:latest --transport=registry --no-signature-verification

reboot
EOF

echo "=== 4. Inyectando Kickstart con mkksiso ==="
mkksiso --ks "${WORK_DIR}/galaxybook.ks" /tmp/boot.iso "${WORK_DIR}/bazzite-galaxybook-tigerlake.iso"

echo "=== 5. Generando Checksum SHA256 ==="
cd "${WORK_DIR}"
sha256sum bazzite-galaxybook-tigerlake.iso > bazzite-galaxybook-tigerlake.iso.sha256

echo "=== ISO GENERADO CON ÉXITO ==="
ls -lh "${WORK_DIR}/bazzite-galaxybook-tigerlake.iso"
