"""
Core TCP Streaming Server and Client Session Manager for Pling Server Linux.
Implements Mac ContentView streaming engine, AIMD rate control, RTT probes, and Quest IPC.
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
    PACKET_KEEPALIVE,
    PACKET_LIVE3D_CTRL,
    PACKET_KEYFRAME_REQ,
    PACKET_FLOW_ACK,
    PACKET_TOUCH,
    PACKET_KEYBOARD_INPUT,
    encode_packet,
    encode_legacy_header,
    encode_live3d_control,
    encode_rtt_probe,
    encode_keyboard_state,
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
    Tracks in-flight bytes, smoothed RTT, flow-control ACKs, and keyframe state.
    """
    def __init__(self, sock: socket.socket, addr: tuple):
        self.sock = sock
        self.addr = addr
        # adb reverse arrives via loopback = USB cable. Anything else = Wi-Fi.
        h = addr[0]
        self.is_usb = h.startswith("127.") or h == "::1" or h.startswith("::ffff:127.")
        self.connected_at = time.time()
        self.bytes_sent: int = 0
        self.bytes_acked: int = 0
        self.ack_supported: bool = False
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
                logger.warning(f"Client {self.addr} send failure: {e}")
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
    Unified Pling Streaming Server for Linux (Tiger Lake Intel Iris Xe).
    Integrates TCP server, VA-API/QSV video capture, PipeWire audio, uinput input, and IPC control.
    """
    def __init__(self, config: Optional[PlingConfig] = None):
        self.config = config or PlingConfig.load()
        self.clients: Dict[tuple, ClientSession] = {}
        self.clients_lock = threading.Lock()
        self._running = False
        self._server_sock: Optional[socket.socket] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._keepalive_thread: Optional[threading.Thread] = None
        self._ipc_thread: Optional[threading.Thread] = None
        self._ipc_sock: Optional[socket.socket] = None

        # AIMD Flow Control State (matching Mac StreamEngine)
        self.current_bitrate_mbps: float = self.config.bitrate_mbps
        self.congestion_ceiling_mbps: float = float("inf")
        self.last_congestion_at: float = 0.0
        self.last_rate_increase_at: float = 0.0
        self.last_applied_bitrate_mbps: float = 0.0
        self.link_status_text: str = ""

        # Components
        self.encoder = VideoEncoder(self.config, on_frame=self._on_video_frame)
        self.audio = AudioStreamer(self.config, on_audio_chunk=self._on_audio_chunk)
        self.input_injector = InputInjector(self.config.width, self.config.height)
        self.discovery = DiscoveryService(self.config)

    @property
    def is_running(self) -> bool:
        return self._running

    # -------------------------------------------------------------
    # AIMD AUTOMATIC BITRATE FLOW CONTROL (Mac Parity)
    # -------------------------------------------------------------
    def _link_cap_mbps(self, clients: List[ClientSession]) -> float:
        any_wifi = any(not c.is_usb for c in clients)
        return self.config.wifi_max_mbps if (any_wifi or not clients) else self.config.usb_max_mbps

    def _target_bitrate_mbps(self, clients: List[ClientSession]) -> float:
        ideal = self.config.ideal_bitrate_mbps()
        cap = self._link_cap_mbps(clients)
        return max(self.config.min_bitrate_mbps, min(ideal, cap))

    def _in_flight_limit_bytes(self) -> int:
        bytes_per_sec = self.current_bitrate_mbps * 1_000_000.0 / 8.0
        return int(max(220_000, bytes_per_sec * 0.070)) # 70ms of video buffer

    def _network_allows_new_frame(self, clients: List[ClientSession], now: float) -> bool:
        if self.config.bitrate_mode == "manual":
            return True

        limit = self._in_flight_limit_bytes()
        congested = any(c.in_flight_bytes > limit for c in clients if c.ack_supported)
        target = self._target_bitrate_mbps(clients)

        if congested:
            if now - self.last_congestion_at > 0.4:
                self.last_congestion_at = now
                self.congestion_ceiling_mbps = max(self.config.min_bitrate_mbps, self.current_bitrate_mbps * 0.92)
                self.current_bitrate_mbps = max(self.config.min_bitrate_mbps, self.current_bitrate_mbps * 0.75)
                self._apply_bitrate_if_needed()
            return False

        if now - self.last_congestion_at > 3.0 and now - self.last_rate_increase_at > 1.0:
            self.last_rate_increase_at = now
            if self.congestion_ceiling_mbps < float("inf"):
                self.congestion_ceiling_mbps *= 1.03
                if self.congestion_ceiling_mbps > target:
                    self.congestion_ceiling_mbps = float("inf")

            ceiling = min(target, self.congestion_ceiling_mbps)
            if self.current_bitrate_mbps < ceiling:
                self.current_bitrate_mbps = min(ceiling, self.current_bitrate_mbps * 1.06 + 0.3)
            elif self.current_bitrate_mbps > target:
                self.current_bitrate_mbps = target
            self._apply_bitrate_if_needed()

        return True

    def _apply_bitrate_if_needed(self) -> None:
        if abs(self.current_bitrate_mbps - self.last_applied_bitrate_mbps) >= 0.25:
            self.last_applied_bitrate_mbps = self.current_bitrate_mbps
            self.encoder.update_bitrate(self.current_bitrate_mbps)

    def _reset_rate_control(self) -> None:
        with self.clients_lock:
            clients = list(self.clients.values())
        target = self._target_bitrate_mbps(clients)
        self.current_bitrate_mbps = max(self.config.min_bitrate_mbps, target * 0.60)
        self.congestion_ceiling_mbps = float("inf")
        self.last_congestion_at = time.time() - 2.0
        self.last_rate_increase_at = 0.0
        self.last_applied_bitrate_mbps = 0.0
        self._apply_bitrate_if_needed()

    def _update_link_status_text(self, clients: List[ClientSession]) -> None:
        if not clients:
            self.link_status_text = "Idle"
            return
        c = clients[0]
        link_name = "USB" if c.is_usb else "Wi-Fi"
        rtt_text = f" · RTT {c.smoothed_rtt_ms:.0f} ms" if c.ack_supported else ""
        self.link_status_text = f"{link_name} · {self.current_bitrate_mbps:.1f} Mbps{rtt_text}"

    # -------------------------------------------------------------
    # SERVER LIFECYCLE & STATUS
    # -------------------------------------------------------------
    def get_status(self) -> dict:
        """
        Returns JSON status for System Tray & CLI.
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
                    "in_flight_kb": round(c.in_flight_bytes / 1024, 1),
                    "bytes_sent_mb": round(c.bytes_sent / (1024 * 1024), 2)
                })
                if avg_rtt == 0.0:
                    avg_rtt = c.smoothed_rtt_ms
                else:
                    avg_rtt = (avg_rtt + c.smoothed_rtt_ms) / 2.0

            self._update_link_status_text(list(self.clients.values()))

        out_w, out_h = self.config.compute_output_dimensions(self.config.width, self.config.height)

        return {
            "running": self._running,
            "clients_count": len(client_list),
            "clients": client_list,
            "link_status": self.link_status_text,
            "fps": round(self.encoder.current_fps, 1),
            "fps_cap": self.config.fps,
            "bitrate_mbps": round(self.current_bitrate_mbps, 1),
            "bitrate_mode": self.config.bitrate_mode,
            "resolution": f"{out_w}x{out_h}",
            "target_height": self.config.target_height,
            "gamma": round(self.config.gamma, 2),
            "saturation": round(self.config.saturation, 2),
            "volume_boost": round(self.config.volume_boost, 1),
            "audio_enabled": self.config.audio_enabled,
            "encoder": self.encoder.active_encoder,
            "capture_mode": self.encoder.active_capture,
            "avg_rtt_ms": round(avg_rtt, 1),
            "uinput_ready": self.input_injector.is_available
        }

    def start(self) -> bool:
        if self._running:
            return True
        self._running = True

        logger.info(f"Starting Pling Server Linux on port {self.config.tcp_port}...")

        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._server_sock.bind(("0.0.0.0", self.config.tcp_port))
            self._server_sock.listen(10)
        except Exception as e:
            logger.error(f"Failed to bind TCP port {self.config.tcp_port}: {e}")
            self.stop()
            return False

        # Start background threads
        self._listen_thread = threading.Thread(target=self._accept_loop, name="PlingTCPAccept", daemon=True)
        self._listen_thread.start()

        self._keepalive_thread = threading.Thread(target=self._keepalive_probe_loop, name="PlingKeepAlive", daemon=True)
        self._keepalive_thread.start()

        # Start Sub-Services
        self.discovery.start()
        self.encoder.start()
        if self.config.audio_enabled:
            self.audio.start()

        self._start_ipc_server()
        logger.info(f"🚀 Pling Server is LIVE and listening on TCP port {self.config.tcp_port}.")
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        logger.info("Stopping Pling Server...")

        # Close listening socket
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

        # Stop components
        self.discovery.stop()
        self.encoder.stop()
        self.audio.stop()
        self.input_injector.close()
        self._stop_ipc_server()

        # Save configuration
        self.config.save()
        logger.info("Pling Server cleanly stopped.")

    def restart(self) -> bool:
        logger.info("Restarting Pling Server streaming pipeline...")
        self.encoder.restart()
        if self.config.audio_enabled:
            self.audio.stop()
            self.audio.start()
        self._reset_rate_control()
        self.broadcast_control()
        return True

    # -------------------------------------------------------------
    # CLIENT CONNECTION & TCP LOOP
    # -------------------------------------------------------------
    def _accept_loop(self) -> None:
        while self._running and self._server_sock:
            try:
                sock, addr = self._server_sock.accept()
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                session = ClientSession(sock, addr)
                logger.info(f"New client connected from {addr} (Link: {'USB Cable' if session.is_usb else 'Wi-Fi'})")

                with self.clients_lock:
                    self.clients[addr] = session

                # 1. Send Legacy PLNG handshake header (width, height)
                w, h = self.config.compute_output_dimensions(self.config.width, self.config.height)
                session.send_raw(encode_legacy_header(w, h))

                # 2. Send 2D Live3D Control packet (gamma, saturation, etc.)
                session.send_raw(encode_live3d_control(
                    enabled=False,
                    fps=self.config.fps,
                    width=w,
                    height=h,
                    gamma=self.config.gamma,
                    saturation=self.config.saturation
                ))

                # 3. New decoder on Quest: request fresh IDR keyframe and reset flow rate
                self.encoder.request_keyframe()
                self._reset_rate_control()

                # Start reader thread for this client
                t = threading.Thread(target=self._client_read_loop, args=(session,), name=f"PlingClient-{addr[0]}", daemon=True)
                t.start()

            except Exception as e:
                if self._running:
                    logger.debug(f"TCP accept error: {e}")
                break

    def _client_read_loop(self, client: ClientSession) -> None:
        sock = client.sock
        while self._running and client.alive:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break

                for packet_type, payload in client.parser.feed(chunk):
                    self._process_inbound_packet(packet_type, payload, client)

            except Exception:
                break

        logger.info(f"Client disconnected: {client.addr}")
        client.close()
        with self.clients_lock:
            self.clients.pop(client.addr, None)
        self._reset_rate_control()

    def _process_inbound_packet(self, packet_type: int, payload: bytes, client: ClientSession) -> None:
        # 1. Touch Event (0x06, 9 bytes)
        if packet_type == PACKET_TOUCH:
            parsed = parse_touch_event(payload)
            if parsed:
                action, nx, ny = parsed
                self.input_injector.handle_touch(action, nx, ny)

        # 2. Keyframe Request (0x07)
        elif packet_type == PACKET_KEYFRAME_REQ:
            client.needs_keyframe = True
            self.encoder.request_keyframe()

        # 3. Flow-Control ACK (0x08, >= 8 bytes)
        elif packet_type == PACKET_FLOW_ACK:
            acked, echo_ts = parse_flow_ack(payload)
            client.bytes_acked = acked
            client.ack_supported = True
            now = time.time()
            client.last_ack_time = now
            if echo_ts > 0:
                rtt = max(0.0, (now - echo_ts) * 1000.0)
                if client.smoothed_rtt_ms == 0.0:
                    client.smoothed_rtt_ms = rtt
                else:
                    client.smoothed_rtt_ms = client.smoothed_rtt_ms * 0.9 + rtt * 0.1

        # 4. Keyboard Input (0x0A)
        elif packet_type == PACKET_KEYBOARD_INPUT:
            parsed = parse_keyboard_event(payload)
            if parsed:
                kind, data = parsed
                self.input_injector.handle_keyboard(kind, data)

    # -------------------------------------------------------------
    # FRAME TRANSMISSION & EMISSION
    # -------------------------------------------------------------
    def _on_video_frame(self, frame_data: bytes, is_keyframe: bool) -> None:
        with self.clients_lock:
            if not self.clients:
                return
            active_clients = list(self.clients.values())

        now = time.time()
        # Drop frame before sending if network link is congested
        if not self._network_allows_new_frame(active_clients, now):
            return

        v_type = self.config.video_packet_type
        packet = encode_packet(v_type, frame_data)

        for client in active_clients:
            if not client.alive:
                continue

            if client.needs_keyframe:
                if not is_keyframe:
                    continue  # Drop P-frames until first clean IDR keyframe arrives
                client.needs_keyframe = False

            # In-flight threshold check for Wi-Fi clients
            if not client.is_usb and not is_keyframe and client.in_flight_bytes > self._in_flight_limit_bytes():
                client.needs_keyframe = True
                self.encoder.request_keyframe()
                continue

            client.send_raw(packet)

    def _on_audio_chunk(self, audio_data: bytes) -> None:
        """
        Emits continuous Float32 PCM audio chunks (Packet type 0x01).
        """
        with self.clients_lock:
            if not self.clients:
                return
            active_clients = list(self.clients.values())

        packet = encode_packet(PACKET_AUDIO, audio_data)
        for client in active_clients:
            if client.alive:
                client.send_raw(packet)

    def _keepalive_probe_loop(self) -> None:
        """
        Sends Keepalive (type 0x02) and RTT probe (type 0x09) every 500ms.
        """
        while self._running:
            time.sleep(0.5)
            with self.clients_lock:
                if not self.clients:
                    continue
                active_clients = list(self.clients.values())

            now = time.time()
            keepalive_pkt = encode_packet(PACKET_KEEPALIVE, b"")
            probe_pkt = encode_rtt_probe(now)

            for client in active_clients:
                if client.alive:
                    client.send_raw(keepalive_pkt)
                    client.send_raw(probe_pkt)

    def broadcast_control(self) -> None:
        """
        Broadcasts updated Live3D control payload (packet 0x04) with current sliders.
        """
        with self.clients_lock:
            if not self.clients:
                return
            active_clients = list(self.clients.values())

        w, h = self.config.compute_output_dimensions(self.config.width, self.config.height)
        pkt = encode_live3d_control(
            enabled=False,
            fps=self.config.fps,
            width=w,
            height=h,
            gamma=self.config.gamma,
            saturation=self.config.saturation
        )
        for client in active_clients:
            if client.alive:
                client.send_raw(pkt)

    # -------------------------------------------------------------
    # LOCAL IPC SOCKET FOR CLI & SYSTEM TRAY
    # -------------------------------------------------------------
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
            self._ipc_thread = threading.Thread(target=self._ipc_loop, name="PlingIPCServer", daemon=True)
            self._ipc_thread.start()
        except Exception as e:
            logger.warning(f"Could not bind Unix domain IPC socket {sock_path}: {e}")

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
                raw = conn.recv(4096).decode("utf-8")
                if not raw:
                    conn.close()
                    continue

                try:
                    req = json.loads(raw)
                    cmd = req.get("command")
                    res = {"status": "ok"}

                    if cmd == "status":
                        res = self.get_status()

                    elif cmd == "set_bitrate":
                        val = req.get("value")
                        if val == "auto" or val is None:
                            self.config.bitrate_mode = "auto"
                            self._reset_rate_control()
                            res["bitrate_mode"] = "auto"
                        else:
                            self.config.bitrate_mode = "manual"
                            new_br = float(val)
                            self.encoder.update_bitrate(new_br)
                            self.current_bitrate_mbps = new_br
                            res["bitrate_mode"] = "manual"
                            res["bitrate_mbps"] = new_br

                    elif cmd == "set_fps":
                        new_fps = int(req.get("value", 60))
                        self.encoder.update_fps(new_fps)
                        self.broadcast_control()
                        res["fps"] = new_fps

                    elif cmd == "set_resolution":
                        new_h = int(req.get("value", 1080))
                        self.encoder.update_resolution(new_h)
                        self.broadcast_control()
                        res["target_height"] = new_h

                    elif cmd == "set_gamma":
                        new_g = float(req.get("value", 1.0))
                        self.config.gamma = max(0.5, min(5.0, new_g))
                        self.broadcast_control()
                        res["gamma"] = self.config.gamma

                    elif cmd == "set_saturation":
                        new_s = float(req.get("value", 1.0))
                        self.config.saturation = max(0.0, min(2.0, new_s))
                        self.broadcast_control()
                        res["saturation"] = self.config.saturation

                    elif cmd == "set_volume_boost":
                        new_v = float(req.get("value", 1.0))
                        self.config.volume_boost = max(0.0, min(10.0, new_v))
                        self.audio.set_volume_boost(self.config.volume_boost)
                        res["volume_boost"] = self.config.volume_boost

                    elif cmd == "set_encoder":
                        enc = str(req.get("value", "auto"))
                        self.encoder.update_encoder(enc)
                        res["encoder"] = self.encoder.active_encoder

                    elif cmd == "toggle_audio":
                        enable = bool(req.get("enabled", True))
                        self.config.audio_enabled = enable
                        if enable and not self.audio.is_running:
                            self.audio.start()
                        elif not enable and self.audio.is_running:
                            self.audio.stop()
                        res["audio_enabled"] = enable

                    elif cmd == "force_keyframe":
                        self.encoder.request_keyframe()

                    elif cmd == "stop_stream":
                        self.encoder.stop()

                    elif cmd == "start_stream":
                        if not self.encoder.is_running:
                            self.encoder.start()

                    elif cmd == "restart":
                        self.restart()

                except Exception as ex:
                    res = {"status": "error", "message": str(ex)}

                conn.sendall(json.dumps(res).encode("utf-8"))
                conn.close()

            except Exception:
                break
