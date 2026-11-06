#!/usr/bin/env python3
"""
MagicProxy Linux Daemon
Direct 1:1 implementation of MenuBarApp / AppDelegate for Linux.
Runs seamlessly as a background systemd service.
"""

import sys
import os
import time
import signal
import json
import logging
from proxy_configurator import ProxyConfigurator
from mdns_browser import MDNSBrowser

STATUS_FILE = "/tmp/magicproxy_status.json"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [MagicProxy] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("MagicProxy.App")

class MagicProxyDaemon:
    def __init__(self):
        self.configurator = ProxyConfigurator()
        self.browser = MDNSBrowser(
            on_resolved_cb=self._on_server_connected,
            on_lost_cb=self._on_server_disconnected
        )
        self.status = "starting"
        self._running = True

    def _write_status(self, status: str, ip=None, port=None):
        self.status = status
        data = {
            "status": status,
            "ip": ip,
            "port": port,
            "timestamp": time.time()
        }
        try:
            with open(STATUS_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _on_server_connected(self, ip: str, port: int):
        logger.info(f"Conectado a servidor iOS en {ip}:{port}")
        self._write_status("connected", ip=ip, port=port)
        self.configurator.enable_socks_proxy(ip, port)

    def _on_server_disconnected(self):
        logger.info("Desconectado del servidor iOS. Restaurando rutas originales...")
        self._write_status("searching")
        self.configurator.disable_socks_proxy()

    def start(self):
        logger.info("Iniciando servicio nativo MagicProxy para Linux...")
        self._write_status("searching")
        self.browser.start_browsing()

        def _signal_handler(sig, frame):
            logger.info("Recibida señal de detención. Cerrando túnel de forma segura...")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self._running = False
        self.browser.stop_browsing()
        self.configurator.disable_socks_proxy()
        self._write_status("disconnected")
        logger.info("Servicio MagicProxy detenido limpiamente.")

if __name__ == "__main__":
    daemon = MagicProxyDaemon()
    daemon.start()
