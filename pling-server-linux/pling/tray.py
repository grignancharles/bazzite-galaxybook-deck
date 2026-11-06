"""
System Tray Mini-App for Pling Server Linux.
Supports PyQt6, PySide6, and GTK3 / AyatanaAppIndicator StatusNotifierItem.
Integrates natively into KDE Plasma, GNOME, and Bazzite / SteamOS desktop.
Features all sliders, resolution presets, and hardware encoder options matching Mac ContentView.
"""

import os
import sys
import json
import time
import socket
import logging
import subprocess
import threading
from typing import Optional, Dict

logger = logging.getLogger("PlingTray")

class PlingClientIPC:
    """
    Communicates with the background PlingServer daemon via Unix Domain Socket.
    """
    def __init__(self, sock_path: str = "/tmp/pling-server.sock"):
        self.sock_path = sock_path

    def request(self, cmd_dict: dict, timeout: float = 1.5) -> Optional[dict]:
        if not os.path.exists(self.sock_path):
            return None
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(self.sock_path)
            s.sendall(json.dumps(cmd_dict).encode("utf-8"))
            raw = s.recv(8192).decode("utf-8")
            s.close()
            return json.loads(raw)
        except Exception:
            return None

    def get_status(self) -> Optional[dict]:
        return self.request({"command": "status"})

    def set_bitrate(self, value: str) -> bool:
        res = self.request({"command": "set_bitrate", "value": value})
        return bool(res and res.get("status") == "ok")

    def set_fps(self, fps: int) -> bool:
        res = self.request({"command": "set_fps", "value": fps})
        return bool(res and res.get("status") == "ok")

    def set_resolution(self, height: int) -> bool:
        res = self.request({"command": "set_resolution", "value": height})
        return bool(res and res.get("status") == "ok")

    def set_encoder(self, enc: str) -> bool:
        res = self.request({"command": "set_encoder", "value": enc})
        return bool(res and res.get("status") == "ok")

    def set_gamma(self, gamma: float) -> bool:
        res = self.request({"command": "set_gamma", "value": gamma})
        return bool(res and res.get("status") == "ok")

    def set_saturation(self, sat: float) -> bool:
        res = self.request({"command": "set_saturation", "value": sat})
        return bool(res and res.get("status") == "ok")

    def set_volume_boost(self, vol: float) -> bool:
        res = self.request({"command": "set_volume_boost", "value": vol})
        return bool(res and res.get("status") == "ok")

    def toggle_audio(self, enabled: bool) -> bool:
        res = self.request({"command": "toggle_audio", "enabled": enabled})
        return bool(res and res.get("status") == "ok")

    def force_keyframe(self) -> bool:
        res = self.request({"command": "force_keyframe"})
        return bool(res and res.get("status") == "ok")

    def stop_stream(self) -> bool:
        res = self.request({"command": "stop_stream"})
        return bool(res and res.get("status") == "ok")

    def start_stream(self) -> bool:
        res = self.request({"command": "start_stream"})
        return bool(res and res.get("status") == "ok")

    def restart_pipeline(self) -> bool:
        res = self.request({"command": "restart"})
        return bool(res and res.get("status") == "ok")


def run_qt_tray():
    """
    Runs the PyQt6 / PySide6 implementation of the System Tray widget.
    """
    try:
        from PyQt6 import QtWidgets, QtGui, QtCore
        from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QWidgetAction, QSlider, QLabel, QHBoxLayout, QWidget
        from PyQt6.QtGui import QIcon, QAction
        Qt = QtCore.Qt
    except ImportError:
        try:
            from PySide6 import QtWidgets, QtGui, QtCore
            from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QWidgetAction, QSlider, QLabel, QHBoxLayout, QWidget
            from PySide6.QtGui import QIcon, QAction
            Qt = QtCore.Qt
        except ImportError:
            return False

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    ipc = PlingClientIPC()
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    icon_active_path = os.path.join(assets_dir, "pling-icon-active.svg")
    icon_idle_path = os.path.join(assets_dir, "pling-icon-idle.svg")
    icon_wait_path = os.path.join(assets_dir, "pling-icon-waiting.svg")

    tray = QSystemTrayIcon()
    tray.setIcon(QIcon(icon_idle_path if os.path.exists(icon_idle_path) else ""))
    tray.setVisible(True)

    menu = QMenu()

    # Title header
    header_action = QAction("🎮 Pling Server (Tiger Lake Gen12)", menu)
    header_action.setEnabled(False)
    menu.addAction(header_action)

    status_action = QAction("⚪ Waiting for Quest...", menu)
    status_action.setEnabled(False)
    menu.addAction(status_action)

    menu.addSeparator()

    # Toggle Stream
    toggle_stream_action = QAction("⏹ Stop Streaming", menu)
    menu.addAction(toggle_stream_action)

    # Force IDR Keyframe
    keyframe_action = QAction("🔄 Force IDR Keyframe (Refresh)", menu)
    menu.addAction(keyframe_action)

    # Restart Engine
    restart_action = QAction("⚡ Restart Engine", menu)
    menu.addAction(restart_action)

    menu.addSeparator()

    # 1. Output Height Resolution Submenu (Mac Stepper parity)
    res_menu = menu.addMenu("📐 Resolution Preset")
    res_actions = {}
    for h in [720, 1080, 1440, 2160]:
        act = QAction(f"{h}p Output Height", res_menu)
        act.setCheckable(True)
        res_actions[h] = act
        res_menu.addAction(act)

    # 2. FPS Cap Submenu (25, 30, 60)
    fps_menu = menu.addMenu("⏱ FPS Cap")
    fps_actions = {}
    for fps in [25, 30, 60]:
        act = QAction(f"{fps} FPS", fps_menu)
        act.setCheckable(True)
        fps_actions[fps] = act
        fps_menu.addAction(act)

    # 3. Bitrate Presets & AIMD Auto Submenu
    bitrate_menu = menu.addMenu("⚡ Bitrate Mode & Cap")
    auto_bitrate_act = QAction("Auto AIMD (Quest ACK Flow Control)", bitrate_menu)
    auto_bitrate_act.setCheckable(True)
    bitrate_menu.addAction(auto_bitrate_act)
    bitrate_menu.addSeparator()
    bitrate_actions = {}
    for mbps in [15, 20, 30, 40, 50, 70]:
        act = QAction(f"{mbps} Mbps (Fixed)", bitrate_menu)
        act.setCheckable(True)
        bitrate_actions[mbps] = act
        bitrate_menu.addAction(act)

    # 4. Hardware Video Encoders Submenu
    encoder_menu = menu.addMenu("🎞 Hardware Video Encoder")
    enc_actions = {}
    for enc, label in [
        ("auto", "Auto Detect (Best Available)"),
        ("vaapi", "Intel VA-API (Iris Xe Tiger Lake Gen12)"),
        ("qsv", "Intel Quick Sync Video (QSV)"),
        ("x265", "Software libx265 (HEVC CPU fallback)"),
        ("x264", "Software libx264 (H.264 CPU fallback)")
    ]:
        act = QAction(label, encoder_menu)
        act.setCheckable(True)
        enc_actions[enc] = act
        encoder_menu.addAction(act)

    menu.addSeparator()

    # 5. Color & Audio Sliders Submenu
    sliders_menu = menu.addMenu("🎨 Sliders: Color & Audio Gain")
    
    # Saturation presets
    sat_menu = sliders_menu.addMenu("Saturation")
    sat_actions = {}
    for s_val in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
        act = QAction(f"{s_val:.1f}x", sat_menu)
        act.setCheckable(True)
        sat_actions[s_val] = act
        sat_menu.addAction(act)

    # Gamma presets
    gamma_menu = sliders_menu.addMenu("Gamma")
    gamma_actions = {}
    for g_val in [0.8, 1.0, 1.2, 1.5, 2.0, 3.0]:
        act = QAction(f"{g_val:.1f}", gamma_menu)
        act.setCheckable(True)
        gamma_actions[g_val] = act
        gamma_menu.addAction(act)

    # Volume boost presets
    vol_menu = sliders_menu.addMenu("Volume Boost")
    vol_actions = {}
    for v_val in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]:
        act = QAction(f"{v_val:.1f}x", vol_menu)
        act.setCheckable(True)
        vol_actions[v_val] = act
        vol_menu.addAction(act)

    # Audio Toggle
    audio_action = QAction("🔊 Desktop Audio (PipeWire)", menu)
    audio_action.setCheckable(True)
    audio_action.setChecked(True)
    menu.addAction(audio_action)

    menu.addSeparator()

    # Quit
    quit_action = QAction("❌ Quit Pling", menu)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)

    # State tracking
    last_connected_count = 0

    def trigger_toggle_stream():
        status = ipc.get_status()
        if status and status.get("running"):
            if status.get("fps", 0) > 0:
                ipc.stop_stream()
            else:
                ipc.start_stream()

    toggle_stream_action.triggered.connect(trigger_toggle_stream)
    keyframe_action.triggered.connect(lambda: ipc.force_keyframe())
    restart_action.triggered.connect(lambda: ipc.restart_pipeline())
    audio_action.triggered.connect(lambda checked: ipc.toggle_audio(checked))
    quit_action.triggered.connect(lambda: QtWidgets.QApplication.quit())

    # Wire resolution actions
    for h, act in res_actions.items():
        act.triggered.connect(lambda _, h_val=h: ipc.set_resolution(h_val))

    # Wire fps actions
    for fps, act in fps_actions.items():
        act.triggered.connect(lambda _, f_val=fps: ipc.set_fps(f_val))

    # Wire bitrate actions
    auto_bitrate_act.triggered.connect(lambda _: ipc.set_bitrate("auto"))
    for mbps, act in bitrate_actions.items():
        act.triggered.connect(lambda _, m_val=mbps: ipc.set_bitrate(str(m_val)))

    # Wire encoder actions
    for enc, act in enc_actions.items():
        act.triggered.connect(lambda _, e_val=enc: ipc.set_encoder(e_val))

    # Wire slider presets
    for s_val, act in sat_actions.items():
        act.triggered.connect(lambda _, val=s_val: ipc.set_saturation(val))
    for g_val, act in gamma_actions.items():
        act.triggered.connect(lambda _, val=g_val: ipc.set_gamma(val))
    for v_val, act in vol_actions.items():
        act.triggered.connect(lambda _, val=v_val: ipc.set_volume_boost(val))

    # Periodic polling timer (1Hz)
    timer = QtCore.QTimer()

    def update_state():
        nonlocal last_connected_count
        status = ipc.get_status()

        if not status or not status.get("running"):
            tray.setIcon(QIcon(icon_idle_path))
            status_action.setText("⚪ Server Stopped")
            toggle_stream_action.setText("▶ Start Server")
            return

        clients_count = status.get("clients_count", 0)
        fps = status.get("fps", 0.0)
        bitrate = status.get("bitrate_mbps", 0.0)
        bitrate_mode = status.get("bitrate_mode", "auto")
        avg_rtt = status.get("avg_rtt_ms", 0.0)
        target_h = status.get("target_height", 1080)
        fps_cap = status.get("fps_cap", 60)
        cur_enc = status.get("encoder", "vaapi")
        sat = status.get("saturation", 1.0)
        gamma = status.get("gamma", 1.0)
        vol = status.get("volume_boost", 1.0)
        audio_on = status.get("audio_enabled", True)

        # Notify on connect/disconnect
        if clients_count > last_connected_count:
            client_ip = status["clients"][0]["ip"] if status.get("clients") else "Quest"
            is_usb = status["clients"][0]["is_usb"] if status.get("clients") else False
            tray.showMessage(
                "Meta Quest Connected",
                f"Link: {'USB Cable (Low Latency)' if is_usb else 'Wi-Fi'} ({client_ip})\nHardware: Intel Iris Xe Gen12",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
        elif clients_count < last_connected_count and last_connected_count > 0:
            tray.showMessage(
                "Meta Quest Disconnected",
                "Quest VR streaming session ended.",
                QSystemTrayIcon.MessageIcon.Warning,
                2000
            )

        last_connected_count = clients_count

        # Update icons & tooltips
        if clients_count > 0:
            tray.setIcon(QIcon(icon_active_path))
            link_desc = "USB" if any(c["is_usb"] for c in status["clients"]) else "Wi-Fi"
            status_text = f"🟢 Streaming ({link_desc}) | {avg_rtt:.0f}ms RTT | {fps:.0f} FPS"
            tray.setToolTip(f"Pling Server: Connected ({link_desc})\nRTT: {avg_rtt:.0f}ms | {bitrate:.1f} Mbps | {fps:.0f} FPS\nEncoder: {cur_enc} | {target_h}p")
        else:
            tray.setIcon(QIcon(icon_wait_path))
            status_text = f"🟡 Waiting for Quest... ({fps:.0f} FPS)"
            tray.setToolTip(f"Pling Server: Waiting on port 3000\n{bitrate:.1f} Mbps | {fps:.0f} FPS\nEncoder: {cur_enc} | {target_h}p")

        status_action.setText(status_text)
        toggle_stream_action.setText("⏹ Stop Streaming" if fps > 0 else "▶ Resume Streaming")

        # Update checked items
        for h, act in res_actions.items():
            act.setChecked(h == target_h)

        for f, act in fps_actions.items():
            act.setChecked(f == fps_cap)

        auto_bitrate_act.setChecked(bitrate_mode == "auto")
        for m, act in bitrate_actions.items():
            act.setChecked(bitrate_mode == "manual" and abs(m - bitrate) < 2.0)

        for e, act in enc_actions.items():
            act.setChecked(e == cur_enc)

        for s_v, act in sat_actions.items():
            act.setChecked(abs(s_v - sat) < 0.05)
        for g_v, act in gamma_actions.items():
            act.setChecked(abs(g_v - gamma) < 0.05)
        for v_v, act in vol_actions.items():
            act.setChecked(abs(v_v - vol) < 0.1)

        audio_action.setChecked(audio_on)

    timer.timeout.connect(update_state)
    timer.start(1000)
    update_state()

    logger.info("PyQt6 / PySide6 System Tray initialized.")
    return app.exec()


def run_gtk_tray():
    """
    Fallback implementation using GTK3 / AyatanaAppIndicator StatusNotifierItem.
    """
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        try:
            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3 as AppIndicator
        except (ValueError, ImportError):
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3 as AppIndicator
        from gi.repository import Gtk, GLib
    except Exception as e:
        logger.error(f"GTK AppIndicator not available: {e}")
        return False

    ipc = PlingClientIPC()
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    icon_active_path = os.path.join(assets_dir, "pling-icon-active.svg")
    icon_idle_path = os.path.join(assets_dir, "pling-icon-idle.svg")

    indicator = AppIndicator.Indicator.new(
        "pling-server-tray",
        icon_idle_path,
        AppIndicator.IndicatorCategory.APPLICATION_STATUS
    )
    indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

    menu = Gtk.Menu()

    header_item = Gtk.MenuItem(label="🎮 Pling Server Linux (Tiger Lake)")
    header_item.set_sensitive(False)
    menu.append(header_item)

    status_item = Gtk.MenuItem(label="⚪ Waiting for Quest...")
    status_item.set_sensitive(False)
    menu.append(status_item)

    menu.append(Gtk.SeparatorMenuItem())

    refresh_item = Gtk.MenuItem(label="🔄 Force IDR Keyframe")
    refresh_item.connect("activate", lambda _: ipc.force_keyframe())
    menu.append(refresh_item)

    restart_item = Gtk.MenuItem(label="⚡ Restart Engine")
    restart_item.connect("activate", lambda _: ipc.restart_pipeline())
    menu.append(restart_item)

    menu.append(Gtk.SeparatorMenuItem())

    quit_item = Gtk.MenuItem(label="❌ Quit")
    quit_item.connect("activate", lambda _: Gtk.main_quit())
    menu.append(quit_item)

    menu.show_all()
    indicator.set_menu(menu)

    def update_gtk():
        status = ipc.get_status()
        if status and status.get("clients_count", 0) > 0:
            indicator.set_icon_full(icon_active_path, "Pling Active")
            rtt = status.get("avg_rtt_ms", 0.0)
            status_item.set_label(f"🟢 Streaming | {rtt:.0f}ms RTT")
        else:
            indicator.set_icon_full(icon_idle_path, "Pling Idle")
            status_item.set_label("🟡 Waiting for Quest...")
        return True

    GLib.timeout_add_seconds(1, update_gtk)
    logger.info("GTK3 AppIndicator System Tray initialized.")
    Gtk.main()
    return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    if run_qt_tray():
        return
    if run_gtk_tray():
        return
    logger.warning("No graphical toolkit (PyQt/PySide/GTK) available. Running CLI monitor.")
    ipc = PlingClientIPC()
    while True:
        status = ipc.get_status()
        print(f"\rStatus: {json.dumps(status)}", end="", flush=True)
        time.sleep(1.0)

if __name__ == "__main__":
    main()
