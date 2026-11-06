#!/bin/bash
# ==============================================================================
# FIX VISUAL INMEDIATO PARA LA BARRA SUPERIOR Y AJUSTES RÁPIDOS (GNOME BAZZITE)
# 1. Elimina para siempre el selector 'Power Mode' (Performance/Balanced)
# 2. Quita el icono de la tilde ('fijar apretado') de la barra superior
# 3. Pone el icono de Pling 🎮 en la barra superior
# ==============================================================================

set -u

echo "→ 1/5 Eliminando selector de Power Mode del sistema..."
sudo systemctl stop power-profiles-daemon.service 2>/dev/null || true
sudo systemctl mask power-profiles-daemon.service 2>/dev/null || true

echo "→ 2/5 Habilitando user_allow_other en /etc/fuse.conf (Fix discos Mac)..."
sudo mkdir -p /etc
if [ -f "/etc/fuse.conf" ]; then
    sudo sed -i 's/#user_allow_other/user_allow_other/' /etc/fuse.conf
    grep -q "^user_allow_other" /etc/fuse.conf 2>/dev/null || echo "user_allow_other" | sudo tee -a /etc/fuse.conf >/dev/null
else
    echo "user_allow_other" | sudo tee /etc/fuse.conf >/dev/null
fi
sudo chmod 644 /etc/fuse.conf

echo "→ 3/5 Eliminando icono de 'fijar apretado' de la barra superior..."
gsettings set org.gnome.shell.extensions.accent-hold show-indicator false 2>/dev/null || true
if [ -f "$HOME/.local/share/gnome-shell/extensions/accent-hold@griffit.gmail.com/extension.js" ]; then
    sed -i 's/this._addIndicator()/\/\/ this._addIndicator()/g' "$HOME/.local/share/gnome-shell/extensions/accent-hold@griffit.gmail.com/extension.js" 2>/dev/null || true
fi

echo "→ 3/4 Instalando extensión nativa de Pling en la barra superior..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$HOME/.local/share/gnome-shell/extensions"
if [ -d "$SCRIPT_DIR/config/gnome-extensions/pling-indicator@galaxybook" ]; then
    cp -rf "$SCRIPT_DIR/config/gnome-extensions/pling-indicator@galaxybook" "$HOME/.local/share/gnome-shell/extensions/"
fi
gnome-extensions enable pling-indicator@galaxybook 2>/dev/null || true

echo "→ 4/4 Asegurando que el servicio de Pling Server esté activo en el fondo..."
sudo systemctl enable --now pling-server.service 2>/dev/null || true

echo ""
echo "✅ ¡Listo! Reiniciando sesión gráfica en 2 segundos para que la barra se pinte limpia..."
sleep 2
gnome-session-quit --logout --no-prompt 2>/dev/null || systemctl restart --user gnome-shell 2>/dev/null || true
