# Galaxy Book SteamOS (Bazzite-Deck Hiper-Optimizado)

Repositorio de construcción de imagen inmutable OCI / ISO basada en **`ghcr.io/ublue-os/bazzite-deck:stable`**, diseñada exclusivamente para convertir una laptop **Samsung Galaxy Book Flex2 Alpha (`NP730QDA`)** en una consola dedicada tipo **Steam Deck**.

---

## 🎯 Especificaciones del Hardware Destino

* **Modelo:** Samsung Galaxy Book Flex2 Alpha (NP730QDA)
* **Procesador:** Intel Core i7-1165G7 (Tiger Lake-UP3, 10nm SuperFin, 4 Cores / 8 Threads)
* **GPU Integrada:** Intel Iris Xe Graphics G7 (Gen12.1 Xe-LP, 96 EUs @ 1300 MHz, Aceleración DP4a nativa)
* **Memoria RAM:** 16 GB LPDDR4x @ 4267 MT/s (68.2 GB/s de ancho de banda)
* **Pantalla:** 13.3" QLED 1920x1080p @ 60Hz

---

## ⚡ Optimizaciones Integradas de Fábrica (Desde el Segundo 1)

1. **Kernel Arguments Quirúrgicos (`kargs.conf`):**
   * Driver `i915` con colas de hardware **GuC/HuC (`enable_guc=3`)**, compresión de framebuffer **(`enable_fbc=1`)**, y **PSR desactivado (`enable_psr=0`)** para eliminar micro-stuttering en Gamescope.
   * Mitigaciones de CPU desactivadas (`mitigations=off`, `split_lock_detect=off`, `nowatchdog`) para latencia mínima en traducción Proton/Wine.
2. **Control Térmico y Desbloqueo Eléctrico (`galaxybook-power-optimizer`):**
   * **RAPL:** PL1 fijado en **28W** sostenidos y PL2 en **35W** pico.
   * **Gobernador Dinámico:** Cuando `gamescope` está activo, capa la CPU a **3.2 GHz** para impedir que canibalice el consumo de la gráfica, garantizando los **1300 MHz constantes** en las 96 EUs de la Iris Xe. En modo escritorio, libera la CPU hasta 4.7 GHz.
3. **Memoria y ZRAM:**
   * ZRAM de 8 GB con compresión **`lz4`** (mínima latencia de descompresión en CPU quad-core).
   * `vm.max_map_count = 2147483642` y parámetros de baja sobrecarga en `sysctl`.
4. **Mesa ANV / DXVK / VKD3D:**
   * Caché masiva de shaders (20 GB), `ANV_GPL=true`, `ANV_ENABLE_BUFFER_COMP=1`, `DXVK_ASYNC=1`.
   * Forzado de compatibilidad D3D12 sin crasheos por falta de Mesh Shaders.
5. **Inyección Quirúrgica de Juegos (`galaxybook-game-injector`):**
   * Monitor automático que detecta el primer arranque de juegos como **Silent Hill 2 Remake**, **The Last of Us**, **Resident Evil** y **Horizon Forbidden West**.
   * Inyecta archivos `Engine.ini` desmantelando Lumen y Virtual Shadow Maps (retornando a rasterizado tipo PS4/UE4), inyecta OptiScaler con **Intel XeSS DP4a**, y restringe memoria de streaming.
6. **Túnel Nativo para iPhone (100% Automático y Plug & Play):**
   * Cero botones manuales: el túnel corre como un demonio transparente en segundo plano. En cuanto conectas la laptop al Hotspot del iPhone, `tun2socks` levanta `tun69` y enruta el 100% del tráfico automáticamente.
7. **Experiencia MacBook en Touchpad y Teclado US:**
   * **Touchpad:** Configurado idéntico a una MacBook (Desplazamiento natural, tap-to-click, clic derecho con 2 dedos en cualquier parte del trackpad, aceleración adaptativa suave).
   * **Teclado:** Distribución en Inglés de EE.UU. (`us`) por defecto.
8. **Portapapeles Universal Compartido (iPhone / Mac / Bazzite):**
   * Integración con **KDE Connect**: copia texto en tu iPhone o Mac y pégalo instantáneamente en tu Samsung Galaxy Book (y viceversa).
9. **JDownloader 2 Preinstalado de Fábrica:**
   * Empaquetado de forma nativa con runtime OpenJDK 21.
   * Lanzador global en `/usr/bin/jdownloader` y acceso directo en el menú de aplicaciones de escritorio y Steam.
10. **Soporte Nativo para Discos Externos de Mac (APFS / HFS+) y Windows (NTFS / exFAT):**
   * Incluye el driver `apfs-fuse` para leer discos duros formateados en macOS (como tu disco externo de 1 TB `MessiEnto`).
   * Herramienta y acceso directo de 1 clic: `Abrir Disco Externo Mac (APFS)` (`mount-mac-disk`).
   * Soporte completo para `ntfs-3g`, `exfatprogs` y `hfsprogs`.
11. **Antigravity AI Preinstalado:**
   * Entorno y lanzador de Antigravity (`/usr/bin/antigravity`) listo para usar en Modo Escritorio o desde la terminal.

---

## 🚀 Cómo Generar la ISO y Flashear el USB

### Opción A: Compilación Automática en la Nube (Recomendada para Mac M1)

No necesitas gastar los 8 GB de RAM de tu Mac compilando localmente:

1. Crea un repositorio en GitHub (puedes llamarlo `galaxybook-steamos`).
2. Sube este proyecto:
   ```bash
   git init
   git add .
   git commit -m "feat: Bazzite Galaxy Book Flex2 Alpha Custom Image"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git
   git push -u origin main
   ```
3. Ve a la pestaña **Actions** en tu repositorio de GitHub y selecciona el workflow **"Build Bazzite Galaxy Book ISO"**.
4. Haz clic en **"Run workflow"**.
5. En ~12-15 minutos, GitHub Actions terminará de compilar y encontrarás la ISO lista en los **Artifacts** o **Releases**.

---

### Opción B: Flasheo a USB en macOS

Una vez que tengas la ISO descargada en tu Mac:

1. Conecta tu memoria USB (mínimo 16 GB).
2. Ejecuta en la terminal de tu Mac:
   ```bash
   ./flash_to_usb_mac.sh
   ```
3. El script detectará la ISO automáticamente, te mostrará las unidades USB externas (protegiendo `disk0` de tu Mac), desmontará y grabará la ISO usando `dd` con `rdisk` a máxima velocidad.

---

## 💻 Instalación en la Samsung Galaxy Book Flex2 Alpha

1. Conecta la USB grabada en la laptop apagada.
2. Enciéndela y pulsa repetidamente la tecla **F2** (BIOS) o **F10** (Boot Menu).
3. Selecciona arrancar desde la memoria USB en modo UEFI.
4. Elige **"Install Bazzite-Deck"**.
5. Sigue el instalador gráfico en pantalla.
6. Al reiniciar, la laptop entrará directamente al modo consola de **Steam Gaming Mode**, optimizada desde el primer segundo.
