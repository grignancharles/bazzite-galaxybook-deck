#!/usr/bin/env python3
"""
MagicProxy - MDNSBrowser
1:1 direct port of macOS MDNSBrowser.swift for Linux.
Discovers _magicproxy._tcp.local. via standard mDNS multicast + proactive SOCKS5 probe.
"""

import socket
import struct
import time
import threading
import logging
import subprocess

logger = logging.getLogger("MagicProxy.Browser")

MDNS_GROUP = "224.0.0.251"
MDNS_PORT = 5353
SERVICE_TYPE = "_magicproxy._tcp.local"

class MDNSBrowser:
    def __init__(self, on_resolved_cb=None, on_lost_cb=None):
        self.on_resolved = on_resolved_cb
        self.on_lost = on_lost_cb
        self.server_ip = None
        self.server_port = None
        self.is_searching = False
        self._running = False
        self._thread = None

    def start_browsing(self):
        if self._running:
            return
        self._running = True
        self.is_searching = True
        self._thread = threading.Thread(target=self._browse_loop, daemon=True)
        self._thread.start()
        logger.info("Iniciando búsqueda mDNS para _magicproxy._tcp.local...")

    def stop_browsing(self):
        self._running = False
        self.is_searching = False
        self.server_ip = None
        self.server_port = None
        if self.on_lost:
            self.on_lost()

    def _test_socks5_handshake(self, ip: str, port: int, timeout=0.8) -> bool:
        """Verifica activamente que el servidor SOCKS5 responda (idéntico al handshake RFC 1928)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((ip, port))
            # Handshake: Version 5, 1 Method, No Authentication (0x00)
            s.sendall(b"\x05\x01\x00")
            resp = s.recv(2)
            s.close()
            # Response must be: Version 5, Method Accepted (0x00)
            return len(resp) == 2 and resp[0] == 0x05 and resp[1] == 0x00
        except Exception:
            return False

    def _get_candidate_gateways(self):
        """Retorna las puertas de enlace actuales y la IP estándar de tethering iPhone (172.20.10.1)."""
        candidates = set()
        candidates.add("172.20.10.1")
        try:
            out = subprocess.check_output(["ip", "route", "show", "default"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                    candidates.add(parts[2])
        except Exception:
            pass
        return list(candidates)

    def _parse_mdns_response(self, data: bytes):
        """Parsea paquetes mDNS en busca de respuestas PTR/SRV/A para _magicproxy."""
        try:
            # Buscar texto de _magicproxy en el payload
            if b"_magicproxy" not in data:
                return None, None

            # Buscar puerto SRV (normalmente 10808 = 0x2A38) o IP en los RRs adicionales
            port = 10808
            ip = None

            # Si incluye la IP en formato de 4 bytes tras un registro A
            # Escanear subred típica 172.20.10.x o buscar A record
            for i in range(len(data) - 4):
                if data[i] == 172 and data[i+1] == 20 and data[i+2] == 10:
                    ip = f"{data[i]}.{data[i+1]}.{data[i+2]}.{data[i+3]}"
                    break

            return ip, port
        except Exception:
            return None, None

    def _build_mdns_query(self) -> bytes:
        # Transaction ID 0, Flags 0, 1 Question
        header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)
        qname = b""
        for part in ["_magicproxy", "_tcp", "local"]:
            qname += struct.pack("!B", len(part)) + part.encode("ascii")
        qname += b"\x00"
        qtype = struct.pack("!HH", 12, 1)  # PTR, IN
        return header + qname + qtype

    def _browse_loop(self):
        # Crear socket UDP multicast para mDNS
        mdns_sock = None
        try:
            mdns_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            mdns_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            mdns_sock.settimeout(1.5)
        except Exception as e:
            logger.warning(f"No se pudo crear socket mDNS multicast: {e}")

        query_bytes = self._build_mdns_query()

        while self._running:
            discovered_ip = None
            discovered_port = 10808

            # 1. Probar activamente candidatos conocidos (172.20.10.1 y gateway de red)
            for cand_ip in self._get_candidate_gateways():
                if self._test_socks5_handshake(cand_ip, 10808, timeout=0.4):
                    discovered_ip = cand_ip
                    discovered_port = 10808
                    break

            # 2. Si no respondió el probe directo, emitir consulta mDNS
            if not discovered_ip and mdns_sock:
                try:
                    mdns_sock.sendto(query_bytes, (MDNS_GROUP, MDNS_PORT))
                    start_t = time.time()
                    while time.time() - start_t < 1.0:
                        try:
                            data, addr = mdns_sock.recvfrom(4096)
                            parsed_ip, parsed_port = self._parse_mdns_response(data)
                            if parsed_ip and self._test_socks5_handshake(parsed_ip, parsed_port or 10808):
                                discovered_ip = parsed_ip
                                discovered_port = parsed_port or 10808
                                break
                            elif addr[0] and self._test_socks5_handshake(addr[0], 10808):
                                discovered_ip = addr[0]
                                discovered_port = 10808
                                break
                        except socket.timeout:
                            break
                except Exception:
                    pass

            # Manejar transiciones de estado (idéntico a MDNSBrowser.swift)
            if discovered_ip:
                if self.server_ip != discovered_ip or self.server_port != discovered_port:
                    self.server_ip = discovered_ip
                    self.server_port = discovered_port
                    self.is_searching = False
                    logger.info(f"Servicio resuelto: IP {discovered_ip}, Puerto {discovered_port}")
                    if self.on_resolved:
                        self.on_resolved(discovered_ip, discovered_port)
            else:
                if self.server_ip is not None:
                    logger.info("Servicio perdido: El servidor MagicProxy de iOS ya no responde.")
                    self.server_ip = None
                    self.server_port = None
                    self.is_searching = True
                    if self.on_lost:
                        self.on_lost()

            time.sleep(2.0)

        if mdns_sock:
            try:
                mdns_sock.close()
            except Exception:
                pass
