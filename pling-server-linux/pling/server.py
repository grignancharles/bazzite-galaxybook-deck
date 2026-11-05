"""
Core TCP Streaming Server and Client Session Manager for Pling Server Linux.
"""

import os
import json
import time
import socket
import select
import logging
import threading
from typing import Dict, List, Optional
from pling.config import PlingConfig
from pling.protocol import (
    MAGIC_BYTE,
    PACKET_AUDIO,
    PACKET_KEYFRAME_REQ,
    PACKET_FLOW_ACK,
    PACKET_TOUCH,
    PACKET_KEYBOARD_INPUT,
    encode_packet,
    encode_legacy_header,
    encode_live3d_control,
    encode_rtt_probe,
    parse_flow_ack,
    parse_touch_event,
    parse_keyboard_event,
    PacketStreamParser
)
from pling.video_encoder import VideoEncoder
from pling.audio_streamer import AudioStreamer
from pling.input_injector import InputInjector
from pling.discovery import DiscoveryService

logger = logging.getLogger("PlingServer")

class ClientSession:
    """
    Represents an active Meta Quest client connection over TCP.
    """
    def __init__(self, sock: socket.socket, addr: tuple):
        self.sock = sock
        self.addr = addr
        self.is_usb = addr[0].startswith("127.") or addr[0] == "::1"
        self.connected_at = time.time()
        self.bytes_sent: int = 0
        self.bytes_acked: int = 0
        self.smoothed_rtt_ms: float = 0.0
        self.last_ack_time: float = time.time()
        self.needs_keyframe: bool = True
        self.parser = PacketStreamParser()
        self.lock = threading.Lock()
        self.alive = True

    @property
    def in_flight_bytes(self) -> int:
        return max(0, self.bytes_sent - self.bytes_acked)

    def send_raw(self, data: bytes) -> bool:
        if not self.alive:
            return False
        with self.lock:
            try:
                self.sock.sendall(data)
                self.bytes_sent += len(data)
                return True
            except Exception as e:
                logger.warning(f"Client {self.addr} send error: {e}")
                self.alive = False
                return False

    def close(self) -> None:
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


class PlingServer:
    """
    Unified Pling Streaming Server for Linux.
    Integrates TCP server, VA-API video capture, PipeWire audio, uinput input, and IPC socket.
    """
    def __init__(self, config: Optional[PlingConfig] = None):
        self.config = config or PlingConfig.load()
        self.clients: Dict[tuple, ClientSession] = {}
        self.clients_lock = threading.Lock()
        self._running = False
        self._server_sock: Optional[socket.socket] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._rtt_probe_thread: Optional[threading.Thread] = None
        self._ipc_thread: Optional[threading.Thread] = None
        self._ipc_sock: Optional[socket.socket] = None

        # Components
        self.encoder = VideoEncoder(self.config, on_frame=self._on_video_frame)
        self.audio = AudioStreamer(self.config, on_audio_chunk=self._on_audio_chunk)
        self.input_injector = InputInjector(self.config.width, self.config.height)
        self.discovery = DiscoveryService(self.config)

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        """
        Returns JSON-serializable status metrics for the System Tray app.
        """
        with self.clients_lock:
            client_list = []
            avg_rtt = 0.0
            for addr, c in self.clients.items():
                client_list.append({
                    "ip": addr[0],
                    "port": addr[1],
                    "is_usb": c.is_usb,
                    "rtt_ms": round(c.smoothed_rtt_ms, 1),
                    "in_flight_kb": round(c.in_flight_bytes / 1024, 1)
                })
                if avg_rtt == 0.0:
                    avg_rtt = c.smoothed_rtt_ms
                else:
                    avg_rtt = (avg_rtt + c.smoothed_rtt_ms) / 2.0

        return {
            "running": self._running,
            "clients_count": len(client_list),
            "clients": client_list,
            "fps": round(self.encoder.current_fps, 1),
            "bitrate_mbps": self.config.bitrate_mbps,
            "audio_enabled": self.config.audio_enabled,
            "capture_mode": self.config.capture_mode,
            "avg_rtt_ms": round(avg_rtt, 1),
            "uinput_ready": self.input_injector.is_available
        }

    def start(self) -> bool:
        if self._running:
            return True
        self._running = True

        logger.info(f"Starting Pling Server Linux on port {self.config.tcp_port}...")

        # 1. Start TCP Listener
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._server_sock.bind(("0.0.0.0", self.config.tcp_port))
            self._server_sock.listen(5)
        except Exception as e:
            logger.error(f"Failed to bind TCP server to port {self.config.tcp_port}: {e}")
            self._running = False
            return False

        self._listen_thread = threading.Thread(target=self._accept_loop, name="PlingTCPAccept", daemon=True)
        self._listen_thread.start()

        # 2. Start Discovery & ADB Monitor
        self.discovery.start()

        # 3. Start Video Encoder & Audio Streamer
        self.encoder.start()
        if self.config.audio_enabled:
            self.audio.start()

        # 4. Start RTT Probing loop
        self._rtt_probe_thread = threading.Thread(target=self._rtt_probe_loop, name="PlingRTTProbe", daemon=True)
        self._rtt_probe_thread.start()

        # 5. Start Local IPC Socket for System Tray mini-app
        self._start_ipc_server()

        logger.info("🚀 Pling Server Linux is active and listening for Quest.")
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        logger.info("Stopping Pling Server...")

        # Close TCP listener
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        # Disconnect clients
        with self.clients_lock:
            for client in self.clients.values():
                client.close()
            self.clients.clear()

        # Stop services
        self.discovery.stop()
        self.encoder.stop()
        self.audio.stop()
        self.input_injector.close()
        self._stop_ipc_server()

    def _accept_loop(self) -> None:
        """
        Accepts incoming Quest connections over TCP port 3000.
        """
        while self._running and self._server_sock:
            try:
                sock, addr = self._server_sock.accept()
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                session = ClientSession(sock, addr)
                logger.info(f"✨ New Quest connected from {addr[0]}:{addr[1]} ({'USB' if session.is_usb else 'Wi-Fi'})")

                # Send initial handshake headers
                legacy_header = encode_legacy_header(self.config.width, self.config.height)
                session.send_raw(legacy_header)

                # Send 2D pure control packet
                control_packet = encode_live3d_control(enabled=False)
                session.send_raw(control_packet)

                # Force an immediate IDR keyframe so the Quest decoder starts cleanly
                session.needs_keyframe = True
                self.encoder.request_keyframe()

                with self.clients_lock:
                    self.clients[addr] = session

                # Start client receiver thread
                t = threading.Thread(target=self._client_read_loop, args=(session,), name=f"PlingClient-{addr[0]}", daemon=True)
                t.start()

            except Exception as e:
                if self._running:
                    logger.debug(f"Accept loop notice: {e}")
                break

    def _client_read_loop(self, session: ClientSession) -> None:
        """
        Reads control messages from Quest: Touch, Keyframe request, Flow ACK, Keyboard.
        """
        sock = session.sock
        while self._running and session.alive:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break

                for packet_type, payload in session.parser.feed(chunk):
                    # Packet 0x07: Keyframe request
                    if packet_type == PACKET_KEYFRAME_REQ:
                        session.needs_keyframe = True
                        self.encoder.request_keyframe()

                    # Packet 0x08: Flow Control ACK
                    elif packet_type == PACKET_FLOW_ACK:
                        acked, echo_ts = parse_flow_ack(payload)
                        session.bytes_acked = acked
                        session.last_ack_time = time.time()
                        if echo_ts > 0:
                            now = time.time()
                            rtt = max(0.0, (now - echo_ts) * 1000.0)
                            if session.smoothed_rtt_ms == 0.0:
                                session.smoothed_rtt_ms = rtt
                            else:
                                session.smoothed_rtt_ms = session.smoothed_rtt_ms * 0.9 + rtt * 0.1

                    # Packet 0x06: Touch/Mouse event
                    elif packet_type == PACKET_TOUCH:
                        touch_data = parse_touch_event(payload)
                        if touch_data:
                            action, nx, ny = touch_data
                            self.input_injector.handle_touch(action, nx, ny)

                    # Packet 0x0A: Keyboard event
                    elif packet_type == PACKET_KEYBOARD_INPUT:
                        kb_data = parse_keyboard_event(payload)
                        if kb_data:
                            kind, data = kb_data
                            self.input_injector.handle_keyboard(kind, data)

            except Exception as e:
                logger.debug(f"Client {session.addr} disconnected: {e}")
                break

        session.close()
        with self.clients_lock:
            self.clients.pop(session.addr, None)
        logger.info(f"Quest {session.addr} disconnected.")

    def _on_video_frame(self, frame_data: bytes, is_keyframe: bool) -> None:
        """
        Emits HEVC NAL units directly to Quest clients.
        Paces transmission according to in-flight buffer to avoid latency build-up.
        """
        with self.clients_lock:
            if not self.clients:
                return
            active_clients = list(self.clients.values())

        # Video packet header
        v_type = self.config.video_packet_type
        packet = encode_packet(v_type, frame_data)

        for client in active_clients:
            if not client.alive:
                continue

            if client.needs_keyframe:
                if not is_keyframe:
                    continue  # Wait until first clean IDR frame
                client.needs_keyframe = False

            # Flow control: if more than 1.5MB in flight on Wi-Fi, drop non-keyframes to avoid latency spike
            if not client.is_usb and not is_keyframe and client.in_flight_bytes > 1_500_000:
                client.needs_keyframe = True
                self.encoder.request_keyframe()
                continue

            client.send_raw(packet)

    def _on_audio_chunk(self, audio_data: bytes) -> None:
        """
        Emits PCM Float32 audio chunk as packet type 0x01.
        """
        with self.clients_lock:
            if not self.clients:
                return
            active_clients = list(self.clients.values())

        packet = encode_packet(PACKET_AUDIO, audio_data)
        for client in active_clients:
            if client.alive:
                client.send_raw(packet)

    def _rtt_probe_loop(self) -> None:
        """
        Sends RTT timestamp probes (packet 0x09) every 500ms.
        """
        while self._running:
            time.sleep(0.5)
            with self.clients_lock:
                if not self.clients:
                    continue
                active_clients = list(self.clients.values())

            probe_packet = encode_rtt_probe(time.time())
            for client in active_clients:
                if client.alive:
                    client.send_raw(probe_packet)

    # --- Local IPC Management for System Tray ---
    def _start_ipc_server(self) -> None:
        sock_path = self.config.ipc_socket_path
        if os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except Exception:
                pass

        try:
            self._ipc_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._ipc_sock.bind(sock_path)
            os.chmod(sock_path, 0o666)
            self._ipc_sock.listen(5)
            self._ipc_thread = threading.Thread(target=self._ipc_loop, name="PlingIPC", daemon=True)
            self._ipc_thread.start()
        except Exception as e:
            logger.warning(f"Could not initialize IPC socket: {e}")

    def _stop_ipc_server(self) -> None:
        if self._ipc_sock:
            try:
                self._ipc_sock.close()
            except Exception:
                pass
            self._ipc_sock = None
        if os.path.exists(self.config.ipc_socket_path):
            try:
                os.remove(self.config.ipc_socket_path)
            except Exception:
                pass

    def _ipc_loop(self) -> None:
        while self._running and self._ipc_sock:
            try:
                conn, _ = self._ipc_sock.accept()
                req_data = conn.recv(2048).decode("utf-8")
                if not req_data:
                    conn.close()
                    continue

                try:
                    req = json.loads(req_data)
                    cmd = req.get("command")
                    response = {"status": "ok"}

                    if cmd == "status":
                        response = self.get_status()
                    elif cmd == "set_bitrate":
                        new_br = int(req.get("bitrate_mbps", 30))
                        self.encoder.update_bitrate(new_br)
                        response["bitrate_mbps"] = new_br
                    elif cmd == "toggle_audio":
                        enable = bool(req.get("enabled", True))
                        self.config.audio_enabled = enable
                        if enable and not self.audio.is_running:
                            self.audio.start()
                        elif not enable and self.audio.is_running:
                            self.audio.stop()
                        response["audio_enabled"] = enable
                    elif cmd == "force_keyframe":
                        self.encoder.request_keyframe()
                    elif cmd == "stop_stream":
                        self.encoder.stop()
                    elif cmd == "start_stream":
                        if not self.encoder.is_running:
                            self.encoder.start()

                except Exception as ex:
                    response = {"status": "error", "message": str(ex)}

                conn.sendall(json.dumps(response).encode("utf-8"))
                conn.close()
            except Exception:
                break
