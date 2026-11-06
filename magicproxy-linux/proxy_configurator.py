#!/usr/bin/env python3
"""
MagicProxy - ProxyConfigurator
1:1 direct port of macOS ProxyConfigurator.swift for Linux.
Handles Layer-3 TUN interface (tun69), tun2socks lifecycle, and GNOME/Firefox SOCKS5 integration.
"""

import os
import subprocess
import time
import logging

logger = logging.getLogger("MagicProxy.Configurator")

class ProxyConfigurator:
    def __init__(self, tun_device="tun69", tun_ip="10.0.0.2/24", mtu=1400):
        self.tun_device = tun_device
        self.tun_ip = tun_ip
        self.mtu = mtu
        self.is_active = False
        self.active_ip = None
        self.active_port = None
        self.tun2socks_proc = None

    def find_tun2socks(self) -> str:
        candidates = [
            "/usr/local/bin/tun2socks",
            "/usr/bin/tun2socks",
            os.path.expanduser("~/.local/bin/tun2socks"),
            os.path.join(os.path.dirname(__file__), "..", "bin", "tun2socks"),
            os.path.join(os.path.dirname(__file__), "..", "tun2socks")
        ]
        for c in candidates:
            if os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        return "tun2socks"

    def get_default_gateway(self):
        """Finds current physical default gateway and network interface."""
        try:
            out = subprocess.check_output(["ip", "route", "show", "default"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                    gw = parts[2]
                    dev = parts[4] if len(parts) >= 5 and parts[3] == "dev" else None
                    if dev != self.tun_device:
                        return gw, dev
        except Exception as e:
            logger.warning(f"Error detectando puerta de enlace predeterminada: {e}")
        return None, None

    def _set_gnome_proxy(self, ip: str, port: int):
        """Configura el proxy del sistema en GNOME para que Firefox/Chrome usen SOCKS5 remoto sin fallos de DNS."""
        try:
            for uid in os.listdir("/run/user"):
                if uid.isdigit() and int(uid) >= 1000:
                    bus_addr = f"unix:path=/run/user/{uid}/bus"
                    env = {**os.environ, "DBUS_SESSION_BUS_ADDRESS": bus_addr}
                    subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", "manual"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["gsettings", "set", "org.gnome.system.proxy.socks", "host", ip], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["gsettings", "set", "org.gnome.system.proxy.socks", "port", str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    logger.info(f"Proxy de sistema GNOME activado para usuario UID {uid}: socks5://{ip}:{port}")
        except Exception as e:
            logger.warning(f"No se pudo configurar proxy GNOME: {e}")

    def _clear_gnome_proxy(self):
        """Restaura el proxy de sistema GNOME a directo (mode 'none')."""
        try:
            for uid in os.listdir("/run/user"):
                if uid.isdigit() and int(uid) >= 1000:
                    bus_addr = f"unix:path=/run/user/{uid}/bus"
                    env = {**os.environ, "DBUS_SESSION_BUS_ADDRESS": bus_addr}
                    subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", "none"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    logger.info(f"Proxy de sistema GNOME desactivado para usuario UID {uid}")
        except Exception as e:
            pass

    def enable_socks_proxy(self, ip: str, port: int) -> bool:
        """
        Equivalent to ProxyConfigurator.swift enableSocksProxy(ip: String, port: Int):
        1. killall tun2socks
        2. Direct physical route to iPhone IP via default physical gateway
        3. Start tun2socks -device tun69 -proxy socks5://ip:port -loglevel error
        4. Configure tun69 10.0.0.2 mtu 1400 up
        5. route add 0.0.0.0/1 & 128.0.0.0/1 via tun69
        6. IPv6 WebRTC capture (fd00::2/64, ::/1, 8000::/1)
        7. TTL 65 bypass
        8. GNOME System SOCKS5 proxy (fixes Firefox & browser DNS)
        """
        if self.is_active and self.active_ip == ip and self.active_port == port:
            if self.tun2socks_proc and self.tun2socks_proc.poll() is None:
                return True

        logger.info(f"Iniciando VPN profunda (Capa 3) hacia {ip}:{port}...")
        self.disable_socks_proxy()

        bin_path = self.find_tun2socks()
        gw, dev = self.get_default_gateway()
        if not gw:
            gw = ip

        try:
            # 1. Asegurar ruta física directa hacia el iPhone
            cmd_gw = ["ip", "route", "replace", f"{ip}/32", "via", gw]
            if dev:
                cmd_gw.extend(["dev", dev])
            subprocess.run(cmd_gw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 2. Crear y configurar dispositivo TUN
            subprocess.run(["ip", "tuntap", "add", "dev", self.tun_device, "mode", "tun"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["ip", "addr", "replace", self.tun_ip, "dev", self.tun_device], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["ip", "link", "set", "dev", self.tun_device, "mtu", str(self.mtu), "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 3. Iniciar tun2socks en segundo plano
            cmd_t2s = [
                bin_path,
                "-device", self.tun_device,
                "-proxy", f"socks5://{ip}:{port}",
                "-loglevel", "error"
            ]
            self.tun2socks_proc = subprocess.Popen(
                cmd_t2s,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp
            )
            time.sleep(0.8)

            # 4. Enrutar tráfico IPv4 por tun69 sin romper la puerta física
            subprocess.run(["ip", "route", "replace", "0.0.0.0/1", "dev", self.tun_device], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["ip", "route", "replace", "128.0.0.0/1", "dev", self.tun_device], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 5. Secuestro de IPv6 para evitar fugas de WebRTC (xCloud)
            subprocess.run(["ip", "-6", "addr", "replace", "fd00::2/64", "dev", self.tun_device], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["ip", "-6", "route", "replace", "::/1", "dev", self.tun_device], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["ip", "-6", "route", "replace", "8000::/1", "dev", self.tun_device], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 6. TTL 65 bypass de operadora
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_default_ttl=65"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 7. Activar proxy GNOME en el sistema para Firefox y navegadores
            self._set_gnome_proxy(ip, port)

            self.is_active = True
            self.active_ip = ip
            self.active_port = port
            logger.info(f"[Proxy] VPN Profunda y Proxy de Sistema Activo en {ip}:{port}")
            return True
        except Exception as e:
            logger.error(f"Fallo activando proxy: {e}")
            self.disable_socks_proxy()
            return False

    def disable_socks_proxy(self):
        """
        Equivalent to ProxyConfigurator.swift disableSocksProxy():
        - killall tun2socks
        - delete routes
        - restore GNOME proxy to none
        """
        if not self.is_active and not self.tun2socks_proc:
            return

        logger.info("Desactivando VPN profunda y restaurando conexión directa...")
        self._clear_gnome_proxy()

        if self.tun2socks_proc:
            try:
                self.tun2socks_proc.terminate()
                self.tun2socks_proc.wait(timeout=1.0)
            except Exception:
                try:
                    self.tun2socks_proc.kill()
                except Exception:
                    pass
            self.tun2socks_proc = None

        subprocess.run(["pkill", "-9", "-f", f"tun2socks.*{self.tun_device}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ip", "route", "del", "0.0.0.0/1", "dev", self.tun_device], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ip", "route", "del", "128.0.0.0/1", "dev", self.tun_device], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ip", "-6", "route", "del", "::/1", "dev", self.tun_device], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ip", "-6", "route", "del", "8000::/1", "dev", self.tun_device], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if self.active_ip:
            subprocess.run(["ip", "route", "del", f"{self.active_ip}/32"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ip", "link", "set", "dev", self.tun_device, "down"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self.is_active = False
        self.active_ip = None
        self.active_port = None
        logger.info("[Proxy] VPN Profunda Desactivada")
