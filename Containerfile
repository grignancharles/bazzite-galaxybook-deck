# ==============================================================================
# Containerfile para Bazzite-Deck Hiper-Optimizado para Samsung Galaxy Book Flex2 Alpha
# Target: Intel Core i7-1165G7 (Tiger Lake) + Iris Xe G7 96 EUs (8086:9a49)
# Soporte integral: Audio SOF, Huella, Rotación 2-en-1, Hotspot iPhone 100% Automático
# Experiencia MacBook: Touchpad idéntico a Mac (desplazamiento natural, tap-to-click)
# Teclado: US English nativo por defecto
# Conectividad: Discos Mac APFS, JDownloader 2, Antigravity AI, KDE Connect (Clipboard)
# Streaming: Pling Server 2D Nativo para Meta Quest (VA-API HEVC)
# ==============================================================================

FROM ghcr.io/ublue-os/bazzite-deck:stable

LABEL maintainer="Antigravity Custom SteamOS Builder"
LABEL description="Bazzite Deck image customized exclusively for Samsung Galaxy Book Flex2 Alpha (NP730QDA)"

# 1. Copiar configuraciones de Kernel, Memoria, Pantalla, Teclado US y Touchpad Mac
COPY config/kargs.conf /usr/lib/bootc/kargs.d/99-galaxybook.conf
COPY config/99-galaxybook-gaming.conf /usr/etc/sysctl.d/99-galaxybook-gaming.conf
COPY config/zram-generator.conf /usr/etc/systemd/zram-generator.conf
COPY config/intel-xe-gaming.sh /usr/etc/profile.d/intel-xe-gaming.sh
COPY config/gamescope-custom-res.conf /usr/share/gamescope/galaxybook-resolutions.conf
COPY config/vconsole.conf /usr/etc/vconsole.conf
COPY config/30-touchpad.conf /usr/share/X11/xorg.conf.d/30-touchpad.conf

# 2. Configurar perfil de usuario con Touchpad idéntico a MacBook y Teclado US
RUN mkdir -p /usr/etc/skel/.config
COPY config/kcminputrc /usr/etc/skel/.config/kcminputrc
COPY config/kxkbrc /usr/etc/skel/.config/kxkbrc

# 3. Copiar scripts y demonios de bajo nivel
COPY services/galaxybook-power-optimizer.sh /usr/libexec/galaxybook-power-optimizer.sh
COPY services/galaxybook-game-injector.sh /usr/libexec/galaxybook-game-injector.sh
COPY services/galaxybook-audio-fix.sh /usr/libexec/galaxybook-audio-fix.sh
COPY services/galaxybook-iphone-tunnel.sh /usr/libexec/galaxybook-iphone-tunnel.sh

COPY services/systemd/galaxybook-power-optimizer.service /usr/lib/systemd/system/galaxybook-power-optimizer.service
COPY services/systemd/galaxybook-game-injector.service /usr/lib/systemd/system/galaxybook-game-injector.service
COPY services/systemd/galaxybook-audio-fix.service /usr/lib/systemd/system/galaxybook-audio-fix.service
COPY services/systemd/galaxybook-iphone-tunnel.service /usr/lib/systemd/system/galaxybook-iphone-tunnel.service

# 4. Copiar plantillas quirúrgicas de juegos (UE5, RE Engine, TLOU, Horizon)
COPY game-optimizations/ /usr/share/game-optimizations/

# 5. Copiar scripts de integración
COPY scripts/install-antigravity.sh /tmp/install-antigravity.sh
COPY scripts/setup-fingerprint.sh /tmp/setup-fingerprint.sh
COPY scripts/setup-iphone-tunnel.sh /tmp/setup-iphone-tunnel.sh
COPY scripts/setup-jdownloader.sh /tmp/setup-jdownloader.sh
COPY scripts/setup-mac-disks.sh /tmp/setup-mac-disks.sh
COPY scripts/setup-kdeconnect.sh /tmp/setup-kdeconnect.sh
COPY scripts/setup-pling-server.sh /tmp/setup-pling-server.sh
COPY pling-server-linux/ /tmp/pling-server-linux/

# 6. Instalación de paquetes usando dnf nativo con --skip-unavailable
RUN dnf install -y --skip-unavailable --setopt=install_weak_deps=False \
        fprintd \
        fprintd-pam \
        iio-sensor-proxy \
        apfs-fuse \
        igt-gpu-tools \
        msr-tools \
        python3-pip \
        python3-gobject \
        python3-pyqt6 \
        ffmpeg && \
    dnf clean all && \
    chmod +x /usr/libexec/galaxybook-*.sh \
             /usr/share/game-optimizations/*.sh \
             /tmp/install-antigravity.sh \
             /tmp/setup-fingerprint.sh \
             /tmp/setup-iphone-tunnel.sh \
             /tmp/setup-jdownloader.sh \
             /tmp/setup-mac-disks.sh \
             /tmp/setup-kdeconnect.sh \
             /tmp/setup-pling-server.sh && \
    # Pre-integrar binario nativo de tun2socks x86_64 para funcionamiento 100% offline
    curl -fsSL https://github.com/xjasonlyu/tun2socks/releases/latest/download/tun2socks-linux-amd64.zip -o /tmp/tun2socks.zip && \
    unzip -q /tmp/tun2socks.zip -d /tmp/tun2socks_extracted && \
    mv /tmp/tun2socks_extracted/tun2socks-linux-amd64 /usr/bin/tun2socks && \
    chmod +x /usr/bin/tun2socks && \
    rm -rf /tmp/tun2socks* && \
    # Ejecutar scripts de integración de sistema y aplicaciones
    /tmp/install-antigravity.sh && \
    /tmp/setup-fingerprint.sh && \
    /tmp/setup-iphone-tunnel.sh && \
    /tmp/setup-jdownloader.sh && \
    /tmp/setup-mac-disks.sh && \
    /tmp/setup-kdeconnect.sh && \
    /tmp/setup-pling-server.sh && \
    rm -rf /tmp/install-antigravity.sh /tmp/setup-* /tmp/pling-server-linux && \
    # Habilitar servicios inmutables en systemd mediante enlaces simbólicos limpios
    mkdir -p /usr/lib/systemd/system/multi-user.target.wants && \
    ln -sf /usr/lib/systemd/system/galaxybook-power-optimizer.service /usr/lib/systemd/system/multi-user.target.wants/ && \
    ln -sf /usr/lib/systemd/system/galaxybook-game-injector.service /usr/lib/systemd/system/multi-user.target.wants/ && \
    ln -sf /usr/lib/systemd/system/galaxybook-audio-fix.service /usr/lib/systemd/system/multi-user.target.wants/ && \
    ln -sf /usr/lib/systemd/system/galaxybook-iphone-tunnel.service /usr/lib/systemd/system/multi-user.target.wants/ && \
    ln -sf /usr/lib/systemd/system/iio-sensor-proxy.service /usr/lib/systemd/system/multi-user.target.wants/
