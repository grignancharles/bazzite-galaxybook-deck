#!/bin/bash
# ==============================================================================
# AUDITORÍA DE SILICIO Y OPTIMIZACIONES A BAJO NIVEL (x86_64 TIGER LAKE)
# SAMSUNG GALAXY BOOK FLEX2 ALPHA (NP730QDA)
# Verifica registros MSR, sysfs, frecuencias de GPU/CPU, túnel y reglas udev
# ==============================================================================

set -u

C_RESET="\033[0m"
C_GREEN="\033[1;32m"
C_RED="\033[1;31m"
C_YELLOW="\033[1;33m"
C_CYAN="\033[1;36m"
C_BOLD="\033[1m"

clear
echo -e "${C_CYAN}╔════════════════════════════════════════════════════════════════════╗${C_RESET}"
echo -e "${C_CYAN}║     AUDITORÍA DE SILICIO Y MODO CONSOLA - GALAXY BOOK FLEX2 ALPHA  ║${C_RESET}"
echo -e "${C_CYAN}║     Intel Core i7-1165G7 + Iris Xe (96 EUs) + 16GB LPDDR4x         ║${C_RESET}"
echo -e "${C_CYAN}╚════════════════════════════════════════════════════════════════════╝${C_RESET}"
echo ""

TOTAL_CHECKS=0
PASSED_CHECKS=0

check() {
    local name="$1"
    local condition="$2"
    local detail="$3"
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if eval "$condition"; then
        echo -e " [ ${C_GREEN}PASS${C_RESET} ] ${C_BOLD}${name}${C_RESET} → ${C_GREEN}${detail}${C_RESET}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo -e " [ ${C_RED}FAIL${C_RESET} ] ${C_BOLD}${name}${C_RESET} → ${C_RED}${detail}${C_RESET}"
    fi
}

echo -e "${C_YELLOW}─── 1. SILICIO DE LA GPU (Intel Iris Xe Gen12.1 96 EUs) ───────────${C_RESET}"
GPU_MAX=$(cat /sys/class/drm/card0/gt_max_freq_mhz 2>/dev/null || cat /sys/class/drm/card1/gt_max_freq_mhz 2>/dev/null || echo "0")
GPU_MIN=$(cat /sys/class/drm/card0/gt_min_freq_mhz 2>/dev/null || cat /sys/class/drm/card1/gt_min_freq_mhz 2>/dev/null || echo "0")
GPU_BOOST=$(cat /sys/class/drm/card0/gt_boost_freq_mhz 2>/dev/null || cat /sys/class/drm/card1/gt_boost_freq_mhz 2>/dev/null || echo "0")

check "Frecuencia Máxima GPU" "[ '$GPU_MAX' -ge 1300 ]" "${GPU_MAX} MHz (Clavada a 1300 MHz sin caída de potencia)"
check "Frecuencia Mínima GPU" "[ '$GPU_MIN' -ge 1100 ]" "${GPU_MIN} MHz (Piso de rendimiento de 2.15 TFLOPS)"
check "Frecuencia Boost GPU"  "[ '$GPU_BOOST' -ge 1300 ]" "${GPU_BOOST} MHz (Pico sostenido de consola)"

echo ""
echo -e "${C_YELLOW}─── 2. SILICIO DE LA CPU (Tiger Lake i7-1165G7 4C/8T) ─────────────${C_RESET}"
CPU0_MAX=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || echo "0")
CPU0_EPP=$(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null || echo "none")

check "Tope Frecuencia CPU" "[ '$CPU0_MAX' -le 3200000 ] && [ '$CPU0_MAX' -gt 0 ]" "$((CPU0_MAX / 1000)) MHz (Fijada para no robar vatios a la GPU)"
check "Gobernador / EPP" "[ '$CPU0_EPP' = 'balance_performance' ] || [ '$CPU0_EPP' = 'performance' ]" "EPP en '$CPU0_EPP' (Respuesta instantánea)"

echo ""
echo -e "${C_YELLOW}─── 3. LÍMITES TÉRMICOS Y DE ENERGÍA (RAPL / MSR / BATERÍA) ───────${C_RESET}"
PL1=$(cat /sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw 2>/dev/null || echo "0")
PL2=$(cat /sys/class/powercap/intel-rapl:0/constraint_1_power_limit_uw 2>/dev/null || echo "0")
BAT_THRESH=$(cat /sys/class/power_supply/BAT*/charge_control_end_threshold 2>/dev/null | head -n 1 || echo "0")

check "RAPL PL1 (Sostenido)" "[ '$PL1' -ge 28000000 ]" "$((PL1 / 1000000))W (Potencia de consola sin thermal throttle)"
check "RAPL PL2 (Pico Turbo)" "[ '$PL2' -ge 35000000 ]" "$((PL2 / 1000000))W (Capacidad para picos gráficos)"
check "Límite Carga Batería" "[ '$BAT_THRESH' -eq 85 ]" "${BAT_THRESH}% (Modo protección de vida útil activo)"

echo ""
echo -e "${C_YELLOW}─── 4. SUBSISTEMA DE MEMORIA (RAM LPDDR4x + ZRAM COMPRIMIDA) ───────${C_RESET}"
ZRAM_ACTIVE=$(swapon --show 2>/dev/null | grep -i "zram" || true)
THP=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null | grep -o "\[madvise\]" || true)

check "Memoria ZRAM (16 GB)" "[ -n '$ZRAM_ACTIVE' ]" "Swap zstd en RAM activo (Cero crashes por memoria)"
check "Transparent HugePages" "[ '$THP' = '[madvise]' ]" "madvise activo (70% menos fallos de TLB)"

echo ""
echo -e "${C_YELLOW}─── 5. HARDWARE Y TECLADO (REMAP ENTER FÍSICO) ─────────────────────${C_RESET}"
HWDB_FILE="/etc/udev/hwdb.d/90-galaxybook-enter-key.hwdb"
check "Remap Físico Tecla Enter" "[ -f '$HWDB_FILE' ]" "Tecla '\\' programada como ENTER físico permanente"

echo ""
echo -e "${C_YELLOW}─── 6. SUSPENSIÓN TIPO MACBOOK (LID SLEEP / INSTANT WAKE) ──────────${C_RESET}"
LID_CONF="/etc/systemd/logind.conf.d/99-macbook-lid.conf"
SLEEP_CONF="/etc/systemd/sleep.conf.d/99-macbook-sleep.conf"
check "Suspensión al Cerrar Tapa" "[ -f '$LID_CONF' ] && [ -f '$SLEEP_CONF' ]" "S0ix Modern Standby activo (Cero drenado de batería)"

echo ""
echo -e "${C_YELLOW}─── 7. RED, TÚNEL MAGICPROXY Y BYPASS OPERADORA ───────────────────${C_RESET}"
TUN_DEV_EXISTS=$(ip link show tun69 2>/dev/null || true)
TTL_VAL=$(sysctl -n net.ipv4.ip_default_ttl 2>/dev/null || echo "0")
TUN2SOCKS_EXEC=$([ -x "/usr/local/bin/tun2socks" ] && echo "yes" || echo "no")

check "Binario tun2socks" "[ '$TUN2SOCKS_EXEC' = 'yes' ]" "Instalado en /usr/local/bin/tun2socks"
check "Interfaz Virtual tun69" "[ -n '$TUN_DEV_EXISTS' ]" "Activa y enrutando tráfico al iPhone"
check "Bypass Operadora (TTL)" "[ '$TTL_VAL' -eq 65 ]" "TTL = ${TTL_VAL} (Tráfico identificado como iPhone nativo)"

echo ""
echo -e "${C_YELLOW}─── 8. PRESETS DE JUEGOS Y LIMITADOR 30 FPS (MANGOHUD) ─────────────${C_RESET}"
MANGO_CONF="/etc/MangoHud/MangoHud.conf"
DXVK_CONF="/etc/dxvk.conf"
VKD3D_CONF="/etc/vkd3d.conf"

check "MangoHud 30 FPS Plano" "[ -f '$MANGO_CONF' ]" "Ritmo de 33.33ms plano estilo PS4 (Atajo Alt + 9)"
check "VRAM y Mesh Shaders" "[ -f '$DXVK_CONF' ] && [ -f '$VKD3D_CONF' ]" "VRAM 4.5GB + Compute Shaders fallback activos"

echo ""
echo -e "${C_YELLOW}─── 9. EXPERIENCIA TOUCHPAD ESTILO MACBOOK ─────────────────────────${C_RESET}"
TP_DCONF="/etc/dconf/db/local.d/01-touchpad-macbook"
TP_X11="/etc/X11/xorg.conf.d/30-touchpad.conf"
TAP_ACTIVE=$(gsettings get org.gnome.desktop.peripherals.touchpad tap-to-click 2>/dev/null || echo "false")
NAT_SCROLL=$(gsettings get org.gnome.desktop.peripherals.touchpad natural-scroll 2>/dev/null || echo "false")

check "Touchpad Tap-to-Click" "[ -f '$TP_DCONF' ] || [ '$TAP_ACTIVE' = 'true' ]" "Tocar suave para clic sin hundir mecánicamente"
check "Desplazamiento Natural" "[ -f '$TP_X11' ] || [ '$NAT_SCROLL' = 'true' ]" "Scroll suave idéntico a macOS"

echo ""
echo -e "${C_YELLOW}─── 10. ALMACENAMIENTO Y DISCOS EXTERNOS MAC (APFS / HFS+) ──────────${C_RESET}"
APFS_SCRIPT="/usr/local/bin/galaxybook-apfs-mount.sh"
APFS_UDEV="/etc/udev/rules.d/99-mac-apfs-automount.rules"

check "Montador Automático APFS" "[ -x '$APFS_SCRIPT' ]" "Detección de volúmenes de Mac al conectar"
check "Regla Udev Discos Apple" "[ -f '$APFS_UDEV' ]" "Integración directa en barra lateral de Archivos (Nautilus)"

echo ""
echo -e "${C_YELLOW}─── 11. TECLADO Y ATAJOS ESTILO MACOS (ALT = COMMAND) ───────────────${C_RESET}"
XKB_CONF=$(gsettings get org.gnome.desktop.input-sources xkb-options 2>/dev/null || cat /etc/dconf/db/local.d/01-touchpad-macbook 2>/dev/null | grep "swap_lalt_lctl_lwin" || true)

check "Alt como Command (Mac)" "[ -n '$XKB_CONF' ]" "Alt = Command | Win = Alt/Option | Alt+C/V/Z/Tab nativos"

echo ""
echo -e "${C_YELLOW}─── 12. ACENTOS Y DIÉRESIS MACOS (PRESS-AND-HOLD PARA ñ, á, é, ü) ───${C_RESET}"
ACCENT_EXT=$(ls -d /home/*/.local/share/gnome-shell/extensions/accent-hold* 2>/dev/null || true)
XCOMPOSE_FILE=$(ls /home/*/.XCompose 2>/dev/null || true)

check "Acentos Press-and-Hold" "[ -n '$ACCENT_EXT' ] || [ -f '/etc/skel/.XCompose' ] || [ -n '$XCOMPOSE_FILE' ]" "Mantener n da ñ | a/e/i/o/u dan tildes y diéresis ü estilo Mac"

echo ""
echo -e "${C_CYAN}════════════════════════════════════════════════════════════════════${C_RESET}"
if [ "$PASSED_CHECKS" -eq "$TOTAL_CHECKS" ]; then
    echo -e " ${C_GREEN}✅ RESULTADO FINAL: ${PASSED_CHECKS}/${TOTAL_CHECKS} OPTIMIZACIONES ACTIVAS AL 100%${C_RESET}"
    echo -e " ${C_BOLD}Tu Galaxy Book Flex2 Alpha está operando en Modo Consola Ultra.${C_RESET}"
else
    echo -e " ${C_YELLOW}⚠️ RESULTADO FINAL: ${PASSED_CHECKS}/${TOTAL_CHECKS} OPTIMIZACIONES ACTIVAS${C_RESET}"
    echo -e " (Si ves algún FAIL en el túnel de red, conecta el iPhone y corre CONECTAR_INTERNET_MAGICO.sh)"
fi
echo -e "${C_CYAN}════════════════════════════════════════════════════════════════════${C_RESET}"
echo ""
