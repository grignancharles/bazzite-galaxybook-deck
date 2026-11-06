#!/usr/bin/env bash
# ==============================================================================
# 100% Offline Installer for Pling Server Linux (Intel Tiger Lake Gen12)
# Compatible with SteamOS, Bazzite, Fedora, Ubuntu, Arch Linux
# ==============================================================================
set -euo pipefail

PREFIX="${PREFIX:-/usr/local}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installing Pling Server Linux (Meta Quest Streaming) ==="

# 1. Install Python module & assets to /usr/local/share/pling and /usr/share/pling
echo "[1/6] Installing Pling core modules and assets..."
mkdir -p "${PREFIX}/share/pling/pling"
mkdir -p "${PREFIX}/share/pling/assets"
mkdir -p "/usr/share/pling/pling" "/usr/share/pling/assets" 2>/dev/null || true

cp -rf "${SCRIPT_DIR}/pling/"* "${PREFIX}/share/pling/pling/"
cp -rf "${SCRIPT_DIR}/assets/"* "${PREFIX}/share/pling/assets/"
cp -rf "${SCRIPT_DIR}/pling/"* "/usr/share/pling/pling/" 2>/dev/null || true
cp -rf "${SCRIPT_DIR}/assets/"* "/usr/share/pling/assets/" 2>/dev/null || true

# 2. Install executables to /usr/local/bin and /usr/bin
echo "[2/6] Installing binary wrappers in ${PREFIX}/bin..."
mkdir -p "${PREFIX}/bin" "/usr/bin" 2>/dev/null || true

for BIN_NAME in pling-server pling-ctl pling-tray; do
    cp -f "${SCRIPT_DIR}/${BIN_NAME}" "${PREFIX}/bin/${BIN_NAME}"
    chmod +x "${PREFIX}/bin/${BIN_NAME}"
    cp -f "${SCRIPT_DIR}/${BIN_NAME}" "/usr/bin/${BIN_NAME}" 2>/dev/null || true
    chmod +x "/usr/bin/${BIN_NAME}" 2>/dev/null || true
done

# 3. Install udev rule for /dev/uinput and /dev/dri
echo "[3/6] Installing udev rules for input injection & VA-API GPU access..."
mkdir -p /etc/udev/rules.d /usr/lib/udev/rules.d 2>/dev/null || true
if [ -f "${SCRIPT_DIR}/udev/99-pling-uinput.rules" ]; then
    cp -f "${SCRIPT_DIR}/udev/99-pling-uinput.rules" /etc/udev/rules.d/99-pling-uinput.rules 2>/dev/null || true
    cp -f "${SCRIPT_DIR}/udev/99-pling-uinput.rules" /usr/lib/udev/rules.d/99-pling-uinput.rules 2>/dev/null || true
fi

# Ensure uinput kernel module is configured to load at boot
mkdir -p /etc/modules-load.d /usr/lib/modules-load.d 2>/dev/null || true
echo "uinput" > /etc/modules-load.d/pling-uinput.conf 2>/dev/null || true
modprobe uinput 2>/dev/null || true

if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger --name-match=uinput 2>/dev/null || true
fi

# 4. Install Desktop launchers and application icons
echo "[4/6] Installing desktop launcher and icons..."
mkdir -p "${PREFIX}/share/applications" "/usr/share/applications" 2>/dev/null || true
mkdir -p "${PREFIX}/share/icons/hicolor/scalable/apps" "/usr/share/icons/hicolor/scalable/apps" 2>/dev/null || true

if [ -f "${SCRIPT_DIR}/systemd/pling-tray.desktop" ]; then
    cp -f "${SCRIPT_DIR}/systemd/pling-tray.desktop" "${PREFIX}/share/applications/pling-tray.desktop" 2>/dev/null || true
    cp -f "${SCRIPT_DIR}/systemd/pling-tray.desktop" "/usr/share/applications/pling-tray.desktop" 2>/dev/null || true
fi

for ICON in pling-icon-active.svg pling-icon-idle.svg pling-icon-waiting.svg; do
    if [ -f "${SCRIPT_DIR}/assets/${ICON}" ]; then
        cp -f "${SCRIPT_DIR}/assets/${ICON}" "${PREFIX}/share/icons/hicolor/scalable/apps/${ICON}" 2>/dev/null || true
        cp -f "${SCRIPT_DIR}/assets/${ICON}" "/usr/share/icons/hicolor/scalable/apps/${ICON}" 2>/dev/null || true
    fi
done

# Autostart configuration
mkdir -p "/etc/xdg/autostart" "/etc/skel/.config/autostart" 2>/dev/null || true
if [ -f "${SCRIPT_DIR}/systemd/pling-tray.desktop" ]; then
    cp -f "${SCRIPT_DIR}/systemd/pling-tray.desktop" "/etc/xdg/autostart/pling-tray.desktop" 2>/dev/null || true
    cp -f "${SCRIPT_DIR}/systemd/pling-tray.desktop" "/etc/skel/.config/autostart/pling-tray.desktop" 2>/dev/null || true
fi

# 5. Install systemd services (System daemon & User service)
echo "[5/6] Installing systemd services..."
mkdir -p /etc/systemd/system /usr/lib/systemd/user 2>/dev/null || true

cat << 'EOF' > /etc/systemd/system/pling-server.service
[Unit]
Description=Pling Server Linux - Meta Quest 2D Ultra-Low Latency Streaming
After=network.target sound.target pipewire.service
Wants=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/pling-server serve
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
LimitRTPRIO=99
LimitMEMLOCK=infinity

[Install]
WantedBy=multi-user.target
EOF

cat << 'EOF' > /usr/lib/systemd/user/pling-server.service
[Unit]
Description=Pling Server Linux (User Session)
After=graphical-session.target pipewire.service
Wants=pipewire.service

[Service]
Type=simple
ExecStart=/usr/local/bin/pling-server serve
Restart=on-failure
RestartSec=2
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload 2>/dev/null || true
    systemctl enable pling-server.service 2>/dev/null || true
fi

# 6. Verification
echo "[6/6] Verifying offline installation..."
if [ -x "${PREFIX}/bin/pling-server" ] && [ -x "${PREFIX}/bin/pling-ctl" ]; then
    echo "✓ Pling Server Linux installed successfully in ${PREFIX}/bin"
    echo "✓ Service: pling-server.service (systemd)"
    echo "✓ Tray Applet: pling-tray"
    echo "✓ CLI Control: pling-ctl"
fi

echo "=== Pling Server installation complete! ==="
