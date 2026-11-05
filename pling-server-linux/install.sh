#!/usr/bin/env bash
# ==============================================================================
# Installer for Pling Server Linux on Bazzite / Fedora / SteamOS
# ==============================================================================
set -euo pipefail

PREFIX="${PREFIX:-/usr}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installing Pling Server Linux ==="

# 1. Install Python module to /usr/lib/pling or /usr/share/pling
echo "[1/6] Installing Pling server modules to ${PREFIX}/share/pling..."
mkdir -p "${PREFIX}/share/pling/pling"
mkdir -p "${PREFIX}/share/pling/assets"

cp -r "${SCRIPT_DIR}/pling/"* "${PREFIX}/share/pling/pling/"
cp -r "${SCRIPT_DIR}/assets/"* "${PREFIX}/share/pling/assets/"

# 2. Install executables to /usr/bin
echo "[2/6] Installing binary wrappers in ${PREFIX}/bin..."
mkdir -p "${PREFIX}/bin"

cat << 'EOF' > "${PREFIX}/bin/pling-server"
#!/usr/bin/env python3
import sys
sys.path.insert(0, "/usr/share/pling")
from pling.cli import main
if __name__ == "__main__":
    main()
EOF

cat << 'EOF' > "${PREFIX}/bin/pling-tray"
#!/usr/bin/env python3
import sys
sys.path.insert(0, "/usr/share/pling")
from pling.tray import main
if __name__ == "__main__":
    main()
EOF

cat << 'EOF' > "${PREFIX}/bin/pling-ctl"
#!/usr/bin/env python3
import sys
sys.path.insert(0, "/usr/share/pling")
from pling.cli import main
if __name__ == "__main__":
    main()
EOF

chmod +x "${PREFIX}/bin/pling-server" "${PREFIX}/bin/pling-tray" "${PREFIX}/bin/pling-ctl"

# 3. Install udev rule for /dev/uinput
echo "[3/6] Installing udev rules..."
mkdir -p /usr/lib/udev/rules.d
cp "${SCRIPT_DIR}/udev/99-pling-uinput.rules" /usr/lib/udev/rules.d/99-pling-uinput.rules
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules || true
    udevadm trigger --name-match=uinput || true
fi

# 4. Install Desktop launchers and icons
echo "[4/6] Installing desktop launcher and icons..."
mkdir -p "${PREFIX}/share/applications"
mkdir -p "${PREFIX}/share/icons/hicolor/scalable/apps"

cp "${SCRIPT_DIR}/systemd/pling-tray.desktop" "${PREFIX}/share/applications/pling-tray.desktop"
cp "${SCRIPT_DIR}/assets/pling-icon-active.svg" "${PREFIX}/share/icons/hicolor/scalable/apps/pling-icon-active.svg"
cp "${SCRIPT_DIR}/assets/pling-icon-idle.svg" "${PREFIX}/share/icons/hicolor/scalable/apps/pling-icon-idle.svg"
cp "${SCRIPT_DIR}/assets/pling-icon-waiting.svg" "${PREFIX}/share/icons/hicolor/scalable/apps/pling-icon-waiting.svg"

# Setup autostart in /etc/skel for new users and current user if possible
mkdir -p "/usr/etc/skel/.config/autostart"
cp "${SCRIPT_DIR}/systemd/pling-tray.desktop" "/usr/etc/skel/.config/autostart/pling-tray.desktop"

if [ -n "${HOME:-}" ] && [ -d "${HOME}/.config" ]; then
    mkdir -p "${HOME}/.config/autostart"
    cp "${SCRIPT_DIR}/systemd/pling-tray.desktop" "${HOME}/.config/autostart/pling-tray.desktop"
fi

# 5. Install systemd user service
echo "[5/6] Installing systemd user service..."
mkdir -p "${PREFIX}/lib/systemd/user"
cp "${SCRIPT_DIR}/systemd/pling-server.service" "${PREFIX}/lib/systemd/user/pling-server.service"

# 6. Ensure uinput kernel module is loaded at boot
echo "[6/6] Configuring uinput kernel module..."
mkdir -p /usr/lib/modules-load.d
echo "uinput" > /usr/lib/modules-load.d/pling-uinput.conf

echo "=== Pling Server installation complete! ==="
echo "Run 'pling-tray' to launch the system tray icon, or 'pling-server serve' to start in background."
