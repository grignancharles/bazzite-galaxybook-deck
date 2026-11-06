#!/usr/bin/env python3
"""
MagicProxy - ProxyConfigurator
1:1 direct port of macOS ProxyConfigurator.swift for Linux (Tiger Lake / Bazzite / SteamOS).
Handles Layer-3 TUN interface (tun69), tun2socks lifecycle, and IPv6 leak prevention.
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
        """Finds current default gateway and network interface."""
        try:
            out = subprocess.check_output(["ip", "route", "show", "default"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                    gw = parts[2]
                    dev = parts[4] if len(parts) >= 5 and parts[3] == "dev" else None
                    return gw, dev
        except Exception as e:
            logger.warning(f"Error detectando puerta de enlace predeterminada: {e}")
        return None, None

    def enable_socks_proxy(self, ip: str, port: int) -> bool:
        """
        Equivalent to ProxyConfigurator.swift enableSocksProxy(ip: String, port: Int):
        - killall tun2socks
        - Detect default gateway
        - route add ip via default gateway
        - Launch tun2socks -device tun69 -proxy socks5://ip:port -loglevel error
        - ifconfig tun69 10.0.0.2 mtu 1400 up
        - route add 0.0.0.0/1 -interface tun69
        - route add 128.0.0.0/1 -interface tun69
        - IPv6 capture to avoid WebRTC leaks (xCloud):
          ifconfig tun69 inet6 fd00::2/64 up
          route add -inet6 ::/1 -interface tun69
          route add -inet6 8000::/1 -interface tun69
        - Apply TTL 65 bypass
        """
        if self.is_active and self.active_ip == ip and self.active_port == port:
            # Check if process is still alive
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

            # 7. DNS resolvectl
            subprocess.run(["resolvectl", "dns", self.tun_device, "1.1.1.1", "8.8.8.8"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["resolvectl", "domain", self.tun_device, "~."], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["resolvectl", "default-route", self.tun_device, "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            self.is_active = True
            self.active_ip = ip
            self.active_port = port
            logger.info(f"[Proxy] VPN Profunda (Capa 3) Activa en {ip}:{port}")
            return True
        except Exception as e:
            logger.error(f"Fallo activando proxy: {e}")
            self.disable_socks_proxy()
            return False

    def disable_socks_proxy(self):
        """
        Equivalent to ProxyConfigurator.swift disableSocksProxy():
        - killall tun2socks
        - route delete 0.0.0.0/1
        - route delete 128.0.0.0/1
        - route delete -inet6 ::/1
        - route delete -inet6 8000::/1
        - route delete ip
        """
        if not self.is_active and not self.tun2socks_proc:
            return

        logger.info("Desactivando VPN profunda...")
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
