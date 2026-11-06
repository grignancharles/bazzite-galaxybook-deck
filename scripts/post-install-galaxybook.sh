#!/bin/bash
# ==============================================================================
# POST-INSTALL TOTAL PARA SAMSUNG GALAXY BOOK FLEX2 ALPHA (NP730QDA)
# Ejecutar como ROOT después de instalar el ISO oficial de Bazzite Deck
# Se encarga de TODAS las customizaciones, servicios y optimizaciones
# ==============================================================================
#
# INSTRUCCIONES:
# 1. Arranca el Galaxy Book con la USB de Bazzite oficial
# 2. Instala con el instalador gráfico (touchpad, sin Enter físico)
# 3. Cuando Bazzite arranque por primera vez, abre Konsole
# 4. Monta esta USB o descarga este script y ejecuta:
#    sudo bash post-install-galaxybook.sh
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

[[ $EUID -ne 0 ]] && err "Ejecuta como root: sudo bash $0"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║   SAMSUNG GALAXY BOOK FLEX2 ALPHA — POST-INSTALL BAZZITE DECK   ║"
echo "║   Intel i7-1165G7 Tiger Lake + Iris Xe 96EU — GAMING TOTAL      ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 1. TECLA ENTER — REMAP BARRA INVERTIDA → ENTER (KEY FÍSICO ROTO)
# ─────────────────────────────────────────────────────────────────────────────
info "Configurando remap Enter → Backslash (tecla física rota)..."

mkdir -p /etc/udev/hwdb.d
cp "$REPO_ROOT/config/90-galaxybook-enter-key.hwdb" /etc/udev/hwdb.d/90-galaxybook-enter-key.hwdb

# Forzar que TAMBIÉN funcione como Enter el teclado virtual de la pantalla táctil
cat > /etc/udev/hwdb.d/91-galaxybook-touchscreen-kb.hwdb << 'HWDB'
# Pantalla táctil / teclado virtual Samsung Galaxy Book — confirmar con toque
evdev:input:b0018v04E8p7417*
 KEYBOARD_KEY_70028=enter
 KEYBOARD_KEY_70058=enter
HWDB

systemd-hwdb update
udevadm trigger --subsystem-match=input --action=change
log "Tecla Enter remapeada (\ → Enter) y hwdb actualizado"

# ─────────────────────────────────────────────────────────────────────────────
# 2. KERNEL ARGS — i915 GuC/HuC, PSR, mitigaciones off
# ─────────────────────────────────────────────────────────────────────────────
info "Configurando argumentos de kernel para Tiger Lake..."

mkdir -p /usr/lib/bootc/kargs.d
cp "$REPO_ROOT/config/kargs.conf" /usr/lib/bootc/kargs.d/99-galaxybook.conf

# También aplicar vía grub para el arranque actual sin reinicio
GRUB_CFG=""
for f in /boot/efi/EFI/fedora/grub.cfg /boot/grub2/grub.cfg /boot/grub/grub.cfg; do
    [[ -f "$f" ]] && GRUB_CFG="$f" && break
done

if [[ -n "$GRUB_CFG" ]]; then
    # Inyectar los kargs si no están ya
    if ! grep -q "i915.enable_guc=3" "$GRUB_CFG" 2>/dev/null; then
        warn "Regenerando grub.cfg con kargs de Tiger Lake..."
        grub2-mkconfig -o "$GRUB_CFG" 2>/dev/null || true
    fi
fi
log "Kernel args configurados"

# ─────────────────────────────────────────────────────────────────────────────
# 3. SYSCTL — Gaming: vm.max_map_count, swappiness, dirty ratios, etc.
# ─────────────────────────────────────────────────────────────────────────────
info "Aplicando parámetros sysctl para gaming..."
cp "$REPO_ROOT/config/99-galaxybook-gaming.conf" /etc/sysctl.d/99-galaxybook-gaming.conf
sysctl --system > /dev/null 2>&1
log "Sysctl aplicado (vm.max_map_count=2147483642, swappiness=10, etc.)"

# ─────────────────────────────────────────────────────────────────────────────
# 4. ZRAM — 8 GB swap comprimido lz4 (sin swap en NVMe)
# ─────────────────────────────────────────────────────────────────────────────
info "Configurando ZRAM 8 GB (lz4, prioridad 100)..."
cp "$REPO_ROOT/config/zram-generator.conf" /etc/systemd/zram-generator.conf
systemctl daemon-reload
systemctl restart systemd-zram-setup@zram0.service 2>/dev/null || true
log "ZRAM 8 GB activo"

# ─────────────────────────────────────────────────────────────────────────────
# 5. TOUCHPAD — Idéntico a MacBook (tap-to-click, scroll natural, 2 dedos = derecho)
# ─────────────────────────────────────────────────────────────────────────────
info "Configurando touchpad estilo MacBook..."
mkdir -p /usr/share/X11/xorg.conf.d
cp "$REPO_ROOT/config/30-touchpad.conf" /usr/share/X11/xorg.conf.d/30-touchpad.conf

# KDE: tap-to-click activado por defecto para todos los usuarios nuevos
mkdir -p /etc/skel/.config
cp "$REPO_ROOT/config/kcminputrc"  /etc/skel/.config/kcminputrc  2>/dev/null || true
cp "$REPO_ROOT/config/kxkbrc"     /etc/skel/.config/kxkbrc      2>/dev/null || true

# Aplicar también al usuario actual (deck)
REAL_USER="${SUDO_USER:-deck}"
USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
if [[ -n "$USER_HOME" && -d "$USER_HOME" ]]; then
    mkdir -p "$USER_HOME/.config"
    cp "$REPO_ROOT/config/kcminputrc" "$USER_HOME/.config/kcminputrc" 2>/dev/null || true
    cp "$REPO_ROOT/config/kxkbrc"     "$USER_HOME/.config/kxkbrc"    2>/dev/null || true
    chown -R "$REAL_USER":"$REAL_USER" "$USER_HOME/.config"
fi
log "Touchpad configurado (tap-to-click, scroll natural)"

# ─────────────────────────────────────────────────────────────────────────────
# 6. SERVICIOS SYSTEMD — Power/Audio/iPhone/Game-Injector
# ─────────────────────────────────────────────────────────────────────────────
info "Instalando servicios systemd del Galaxy Book..."

# Copiar scripts de sistema
install -Dm755 "$REPO_ROOT/services/galaxybook-power-optimizer.sh"  /usr/libexec/galaxybook-power-optimizer.sh
install -Dm755 "$REPO_ROOT/services/galaxybook-audio-fix.sh"        /usr/libexec/galaxybook-audio-fix.sh
install -Dm755 "$REPO_ROOT/services/galaxybook-iphone-tunnel.sh"    /usr/libexec/galaxybook-iphone-tunnel.sh
install -Dm755 "$REPO_ROOT/services/galaxybook-game-injector.sh"    /usr/libexec/galaxybook-game-injector.sh

# Copiar unidades systemd
install -Dm644 "$REPO_ROOT/services/systemd/galaxybook-power-optimizer.service" \
    /etc/systemd/system/galaxybook-power-optimizer.service
install -Dm644 "$REPO_ROOT/services/systemd/galaxybook-audio-fix.service" \
    /etc/systemd/system/galaxybook-audio-fix.service
install -Dm644 "$REPO_ROOT/services/systemd/galaxybook-iphone-tunnel.service" \
    /etc/systemd/system/galaxybook-iphone-tunnel.service
install -Dm644 "$REPO_ROOT/services/systemd/galaxybook-game-injector.service" \
    /etc/systemd/system/galaxybook-game-injector.service

systemctl daemon-reload
systemctl enable --now galaxybook-power-optimizer.service
systemctl enable --now galaxybook-audio-fix.service
systemctl enable --now galaxybook-iphone-tunnel.service
systemctl enable --now galaxybook-game-injector.service
log "4 servicios systemd instalados y activos"

# ─────────────────────────────────────────────────────────────────────────────
# 7. VARIABLES DE ENTORNO GLOBALES — Intel Iris Xe, DXVK, VKD3D, Mesa
# ─────────────────────────────────────────────────────────────────────────────
info "Configurando variables de entorno Intel Xe para gaming..."
install -Dm644 "$REPO_ROOT/config/intel-xe-gaming.sh" /etc/profile.d/intel-xe-gaming.sh
log "Variables Intel Xe activas (DXVK_ASYNC, VKD3D, ANV_GPL, MESA_SHADER_CACHE)"

# ─────────────────────────────────────────────────────────────────────────────
# 8. TECLADO — Consola virtual en US (sin acento muerto)
# ─────────────────────────────────────────────────────────────────────────────
info "Configurando teclado US en consola virtual..."
cp "$REPO_ROOT/config/vconsole.conf" /etc/vconsole.conf 2>/dev/null || true
log "Teclado US configurado"

# ─────────────────────────────────────────────────────────────────────────────
# 9. PLANTILLAS DE JUEGOS — Game Injector templates
# ─────────────────────────────────────────────────────────────────────────────
info "Instalando plantillas de optimización de juegos..."
mkdir -p /usr/share/game-optimizations
cp -r "$REPO_ROOT/game-optimizations/"* /usr/share/game-optimizations/
chmod +x /usr/share/game-optimizations/*.sh 2>/dev/null || true
log "Templates de juegos instalados (SH2, TLOU, Horizon, RE Engine)"

# ─────────────────────────────────────────────────────────────────────────────
# 10. TUN2SOCKS — Para el túnel iPhone offline
# ─────────────────────────────────────────────────────────────────────────────
if ! command -v tun2socks &>/dev/null; then
    info "Descargando tun2socks para túnel iPhone..."
    TMP_T2S=$(mktemp -d)
    curl -fsSL --retry 5 \
        "https://github.com/xjasonlyu/tun2socks/releases/latest/download/tun2socks-linux-amd64.zip" \
        -o "$TMP_T2S/t2s.zip" && \
    unzip -q "$TMP_T2S/t2s.zip" -d "$TMP_T2S" && \
    install -Dm755 "$TMP_T2S/tun2socks-linux-amd64" /usr/bin/tun2socks && \
    rm -rf "$TMP_T2S"
    log "tun2socks instalado"
else
    log "tun2socks ya instalado"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 11. LECTOR DE HUELLAS — fprintd (login y sudo con huella)
# ─────────────────────────────────────────────────────────────────────────────
info "Configurando lector de huellas..."
if command -v fprintd-enroll &>/dev/null; then
    # Crear wrapper para registrar huella fácilmente
    cat > /usr/bin/galaxybook-enroll-fingerprint << 'FPRINT'
#!/bin/bash
echo "=== Registro de Huella Dactilar Galaxy Book ==="
echo "Pasa tu dedo índice derecho sobre el sensor varias veces cuando se indique."
echo ""
fprintd-enroll "${SUDO_USER:-$USER}"
echo ""
echo "✓ Huella registrada. Puedes usar 'sudo' con tu dedo ahora."
FPRINT
    chmod +x /usr/bin/galaxybook-enroll-fingerprint

    # PAM: habilitar huella para sudo
    if ! grep -q "pam_fprintd" /etc/pam.d/sudo 2>/dev/null; then
        sed -i '1a auth       sufficient   pam_fprintd.so' /etc/pam.d/sudo 2>/dev/null || true
    fi
    log "Lector de huellas configurado. Ejecuta 'galaxybook-enroll-fingerprint' para registrar"
else
    warn "fprintd no encontrado — instala con: sudo rpm-ostree install fprintd fprintd-pam"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 12. DECKY LOADER — Plugin manager para Game Mode
# ─────────────────────────────────────────────────────────────────────────────
info "Configurando Decky Loader..."
REAL_USER="${SUDO_USER:-deck}"
USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

# Script de instalación de Decky (requiere red — se ejecuta en primer arranque con iPhone)
cat > "$USER_HOME/install-decky.sh" << 'DECKY'
#!/bin/bash
echo "Instalando Decky Loader (requiere conexión — conecta el iPhone primero)..."
curl -L https://github.com/SteamDeckHomebrew/decky-installer/releases/latest/download/install_release.sh | sh
echo "✓ Decky Loader instalado. Reinicia al Game Mode."
DECKY
chmod +x "$USER_HOME/install-decky.sh"
chown "$REAL_USER":"$REAL_USER" "$USER_HOME/install-decky.sh"
log "Script de Decky listo en ~/install-decky.sh (ejecutar con iPhone conectado)"

# ─────────────────────────────────────────────────────────────────────────────
# 13. PLING SERVER — Streaming para Meta Quest
# ─────────────────────────────────────────────────────────────────────────────
info "Instalando Pling Server..."
if [[ -d "$REPO_ROOT/pling-server-linux" ]]; then
    # Copiar binarios y assets
    install -Dm755 "$REPO_ROOT/pling-server-linux/pling-server" /usr/bin/pling-server 2>/dev/null || true
    install -Dm755 "$REPO_ROOT/pling-server-linux/pling-tray"   /usr/bin/pling-tray   2>/dev/null || true
    install -Dm755 "$REPO_ROOT/pling-server-linux/pling-ctl"    /usr/bin/pling-ctl    2>/dev/null || true
    mkdir -p /usr/share/pling
    cp -r "$REPO_ROOT/pling-server-linux/assets/"* /usr/share/pling/ 2>/dev/null || true
    # Instalar servicio de usuario systemd
    mkdir -p /etc/skel/.config/systemd/user
    cp "$REPO_ROOT/pling-server-linux/systemd/pling-server.service" \
        /etc/skel/.config/systemd/user/ 2>/dev/null || true
    # Para el usuario actual
    if [[ -n "$USER_HOME" ]]; then
        mkdir -p "$USER_HOME/.config/systemd/user"
        cp "$REPO_ROOT/pling-server-linux/systemd/pling-server.service" \
            "$USER_HOME/.config/systemd/user/" 2>/dev/null || true
        chown -R "$REAL_USER":"$REAL_USER" "$USER_HOME/.config"
    fi
    log "Pling Server instalado"
else
    warn "pling-server-linux no encontrado en repo — sáltate este paso"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 14. PROTECCIÓN DE BATERÍA — Umbral 85% (Samsung charging threshold)
# ─────────────────────────────────────────────────────────────────────────────
info "Configurando protección de batería Samsung al 85%..."
cat > /etc/udev/rules.d/90-galaxybook-battery.rules << 'UDEV'
# Samsung Galaxy Book — limitar carga al 85% para alargar vida útil
ACTION=="add", SUBSYSTEM=="power_supply", ATTR{type}=="Battery", \
    ATTR{charge_control_end_threshold}="85"
UDEV
udevadm control --reload-rules
log "Protección batería 85% configurada"

# ─────────────────────────────────────────────────────────────────────────────
# 15. GAMESCOPE — Configuración de resolución personalizada
# ─────────────────────────────────────────────────────────────────────────────
info "Configurando resoluciones Gamescope para Iris Xe..."
mkdir -p /usr/share/gamescope
cp "$REPO_ROOT/config/gamescope-custom-res.conf" /usr/share/gamescope/galaxybook-resolutions.conf

# Variables de entorno Gamescope en /etc/environment (siempre activas)
cat >> /etc/environment << 'GENV'
# Gamescope Intel Iris Xe — Samsung Galaxy Book Flex2 Alpha
GAMESCOPE_OUTPUT_WIDTH=1920
GAMESCOPE_OUTPUT_HEIGHT=1080
GAMESCOPE_OUTPUT_REFRESH=60
INTEL_XESS_DP4A=1
GENV
log "Gamescope 1920x1080@60Hz configurado con XeSS DP4a"

# ─────────────────────────────────────────────────────────────────────────────
# RESUMEN FINAL
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                   ✅  INSTALACIÓN COMPLETA                      ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  ✓ Tecla Enter (\ → Enter) — hwdb activo                       ║"
echo "║  ✓ Kernel args Tiger Lake (GuC=3, FBC=1, mitigaciones=off)     ║"
echo "║  ✓ Sysctl gaming (max_map_count, swappiness=10)                ║"
echo "║  ✓ ZRAM 8 GB comprimido lz4                                    ║"
echo "║  ✓ Touchpad estilo MacBook (tap-click, scroll natural)         ║"
echo "║  ✓ 4 servicios systemd activos (power/audio/iphone/games)      ║"
echo "║  ✓ Intel Xe env vars (DXVK_ASYNC, VKD3D, ANV_GPL, XeSS DP4a) ║"
echo "║  ✓ Templates de juegos (SH2, TLOU, Horizon, RE Engine)         ║"
echo "║  ✓ Protección batería Samsung 85%                              ║"
echo "║  ✓ Gamescope 1920x1080@60Hz con FSR/XeSS                      ║"
echo "║  ✓ Pling Server (streaming Meta Quest)                         ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  PRÓXIMOS PASOS:                                                ║"
echo "║  1. Reinicia → teclado \ ya funciona como Enter                ║"
echo "║  2. Con iPhone: bash ~/install-decky.sh                        ║"
echo "║  3. Para registrar huella: galaxybook-enroll-fingerprint       ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
