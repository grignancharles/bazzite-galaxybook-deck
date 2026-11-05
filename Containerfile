# ==============================================================================
# Containerfile para Bazzite-Deck Hiper-Optimizado para Samsung Galaxy Book Flex2 Alpha
# Target: Intel Core i7-1165G7 (Tiger Lake) + Iris Xe G7 96 EUs (8086:9a49)
# ==============================================================================

FROM --platform=linux/amd64 ghcr.io/ublue-os/bazzite-deck:stable

LABEL maintainer="Antigravity Custom SteamOS Builder"
LABEL description="Bazzite Deck image customized exclusively for Samsung Galaxy Book Flex2 Alpha (NP730QDA)"

# 1. Copiar configuraciones de Kernel, Memoria y Variables de Entorno
COPY config/kargs.conf /usr/lib/bootc/kargs.d/99-galaxybook.conf
COPY config/99-galaxybook-gaming.conf /usr/etc/sysctl.d/99-galaxybook-gaming.conf
COPY config/zram-generator.conf /usr/etc/systemd/zram-generator.conf
COPY config/intel-xe-gaming.sh /usr/etc/profile.d/intel-xe-gaming.sh
COPY config/gamescope-custom-res.conf /usr/share/gamescope/galaxybook-resolutions.conf

# 2. Copiar scripts y demonios de bajo nivel
COPY services/galaxybook-power-optimizer.sh /usr/libexec/galaxybook-power-optimizer.sh
COPY services/galaxybook-game-injector.sh /usr/libexec/galaxybook-game-injector.sh
COPY services/systemd/galaxybook-power-optimizer.service /usr/lib/systemd/system/galaxybook-power-optimizer.service
COPY services/systemd/galaxybook-game-injector.service /usr/lib/systemd/system/galaxybook-game-injector.service

# 3. Copiar plantillas quirúrgicas de juegos (UE5, RE Engine, TLOU, Horizon)
COPY game-optimizations/ /usr/share/game-optimizations/

# 4. Copiar e integrar Antigravity AI
COPY scripts/install-antigravity.sh /tmp/install-antigravity.sh

# 5. Permisos de ejecución, habilitación de servicios e instalación de paquetes esenciales
RUN chmod +x /usr/libexec/galaxybook-*.sh \
             /usr/share/game-optimizations/*.sh \
             /tmp/install-antigravity.sh && \
    /tmp/install-antigravity.sh && \
    rm -f /tmp/install-antigravity.sh && \
    systemctl enable galaxybook-power-optimizer.service && \
    systemctl enable galaxybook-game-injector.service && \
    ostree container commit
