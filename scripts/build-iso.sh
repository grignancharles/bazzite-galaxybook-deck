#!/bin/bash
set -euxo pipefail

REPO_OWNER="${1:-grignancharles}"
WORK_DIR="/work"

echo "=== 1. Instalando herramientas de Fedora (lorax, skopeo, curl, xorriso) ==="
dnf install -y lorax skopeo curl xorriso

echo "=== 2. Descargando Fedora 41 Everything Netinst oficial (944 MB) ==="
curl -Lo /tmp/boot.iso "https://archives.fedoraproject.org/pub/archive/fedora/linux/releases/41/Everything/x86_64/iso/Fedora-Everything-netinst-x86_64-41-1.4.iso"

echo "=== 3. Exportando contenedor Bazzite completo como OCI Archive OFFLINE (~3.5 GB) ==="
skopeo copy --insecure-policy "docker://ghcr.io/${REPO_OWNER}/bazzite-galaxybook-deck:latest" "oci-archive:/tmp/container.tar.gz"

echo "=== 4. Creando archivo Kickstart 100% NO-INTERACTIVO (CMDLINE) Y REMAP DE TECLA ENTER ==="
cat > "${WORK_DIR}/galaxybook.ks" << 'EOF'
cmdline
keyboard us
lang en_US.UTF-8
timezone America/New_York

# Formateo automatico completo a ciegas (Zero prompts, Zero clicks, Zero Enter)
zerombr
clearpart --all --initlabel
autopart --type=btrfs

# Instalacion 100% OFFLINE desde el archivo incrustado en el USB (Sin Wi-Fi ni Hotspot)
ostreecontainer --transport oci-archive --url /container.tar.gz --no-signature-verification

reboot

# Script Post-Instalacion: Remapea la tecla directamente arriba de Enter (\ / | backslash) como ENTER
%post --erroronfail
mkdir -p /etc/udev/hwdb.d /usr/lib/udev/hwdb.d

cat << 'HWDB' > /etc/udev/hwdb.d/90-galaxybook-enter-key.hwdb
# Remap physical Backslash key (\ / | directly above Enter) to ENTER
evdev:atkbd:dmi:*
 KEYBOARD_KEY_2b=enter

evdev:input:b0003v*p*
 KEYBOARD_KEY_70031=enter

evdev:input:b0018v*p*
 KEYBOARD_KEY_2b=enter
HWDB

cp /etc/udev/hwdb.d/90-galaxybook-enter-key.hwdb /usr/lib/udev/hwdb.d/90-galaxybook-enter-key.hwdb 2>/dev/null || true

systemd-hwdb update || true
udevadm trigger || true
%end
EOF

echo "=== 5. Inyectando Kickstart, Parche de Grub Timeout y Contenedor Offline con mkksiso ==="
mkksiso --cmdline "inst.cmdline quiet" -a /tmp/container.tar.gz --ks "${WORK_DIR}/galaxybook.ks" /tmp/boot.iso "${WORK_DIR}/bazzite-galaxybook-tigerlake-offline.iso"

echo "=== 6. Generando Checksum SHA256 ==="
cd "${WORK_DIR}"
sha256sum bazzite-galaxybook-tigerlake-offline.iso > bazzite-galaxybook-tigerlake-offline.iso.sha256

echo "=== ISO OFFLINE 100% DESATENDIDO GENERADO CON ÉXITO ==="
ls -lh "${WORK_DIR}/bazzite-galaxybook-tigerlake-offline.iso"
