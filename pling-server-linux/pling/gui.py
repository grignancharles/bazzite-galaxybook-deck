#!/usr/bin/env python3
"""
Pling Control Panel GUI (Linux Tiger Lake)
Matches macOS ContentView.swift UI and controls:
- Resolution, FPS, Sliders (3D Power, Saturation, Gamma, Volume Boost, Bitrate)
- Built with GTK3 (native to GNOME / Bazzite, zero extra dependencies).
"""

import os
import sys
import json
import socket
import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, GLib, Gdk
except ImportError:
    Gtk = None

SOCKET_PATH = "/tmp/pling-server.sock"
CONFIG_PATH = os.path.expanduser("~/.config/pling/config.json")

def send_ipc_command(cmd_dict, timeout=1.0):
    if not os.path.exists(SOCKET_PATH):
        return {"status": "offline", "message": "Servidor Pling no está corriendo"}
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(SOCKET_PATH)
        req = json.dumps(cmd_dict) + "\n"
        s.sendall(req.encode("utf-8"))
        data = s.recv(4096)
        s.close()
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        return {"status": "error", "message": str(e)}

class PlingControlWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="🎮 Pling Server - Panel de Control")
        self.set_default_size(440, 680)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(16)

        # Apply dark theme styling
        css = b"""
        window {
            background-color: #1e1e2e;
            color: #cdd6f4;
        }
        label {
            color: #cdd6f4;
            font-size: 13px;
        }
        .header-title {
            font-size: 18px;
            font-weight: bold;
            color: #89b4fa;
        }
        .status-badge {
            background-color: #313244;
            border-radius: 8px;
            padding: 8px;
            margin-bottom: 12px;
        }
        scale trough {
            background-color: #45475a;
            border-radius: 4px;
        }
        scale highlight {
            background-color: #89b4fa;
            border-radius: 4px;
        }
        button {
            background-color: #313244;
            color: #cdd6f4;
            border-radius: 6px;
            padding: 6px 12px;
        }
        button:hover {
            background-color: #45475a;
        }
        button.action-btn {
            background-color: #89b4fa;
            color: #11111b;
            font-weight: bold;
        }
        """
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.add(main_box)

        # Header
        title_label = Gtk.Label(label="🎮 Pling Meta Quest Streamer")
        title_label.get_style_context().add_class("header-title")
        main_box.pack_start(title_label, False, False, 0)

        # Status badge
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.status_box.get_style_context().add_class("status-badge")
        self.status_label = Gtk.Label(label="🟢 Conectando al demonio...")
        self.metrics_label = Gtk.Label(label="Bitrate: -- Mbps | FPS: -- | RTT: -- ms")
        self.status_box.pack_start(self.status_label, False, False, 0)
        self.status_box.pack_start(self.metrics_label, False, False, 0)
        main_box.pack_start(self.status_box, False, False, 0)

        # Resolution & FPS Pickers
        res_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        res_label = Gtk.Label(label="Resolución:")
        self.res_combo = Gtk.ComboBoxText()
        for r in ["720p", "1080p", "1440p", "4K (2160p)"]:
            self.res_combo.append_text(r)
        self.res_combo.set_active(1) # 1080p
        self.res_combo.connect("changed", self._on_res_changed)
        res_box.pack_start(res_label, False, False, 0)
        res_box.pack_start(self.res_combo, True, True, 0)

        fps_label = Gtk.Label(label="FPS:")
        self.fps_combo = Gtk.ComboBoxText()
        for f in ["25 fps", "30 fps", "60 fps"]:
            self.fps_combo.append_text(f)
        self.fps_combo.set_active(2) # 60 fps
        self.fps_combo.connect("changed", self._on_fps_changed)
        res_box.pack_start(fps_label, False, False, 0)
        res_box.pack_start(self.fps_combo, False, False, 0)
        main_box.pack_start(res_box, False, False, 0)

        # Separator
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

        # SLIDERS SECTION (Matching ContentView.swift)
        # 1. 3D Power (0.000 .. 0.020)
        self.scale_3d = self._create_slider(
            main_box, "3D Power", 0.0, 0.020, 0.001, 0.005,
            format_str="{:.3f}", callback=self._on_3d_changed
        )

        # 2. Saturation (0.0 .. 2.0)
        self.scale_sat = self._create_slider(
            main_box, "Saturación", 0.0, 2.0, 0.05, 1.0,
            format_str="{:.2f}", callback=self._on_sat_changed
        )

        # 3. Gamma (0.5 .. 5.0)
        self.scale_gamma = self._create_slider(
            main_box, "Gamma", 0.5, 5.0, 0.1, 1.0,
            format_str="{:.2f}", callback=self._on_gamma_changed
        )

        # 4. Volume Boost (0.0x .. 10.0x)
        self.scale_vol = self._create_slider(
            main_box, "Volume Boost", 0.0, 10.0, 0.1, 1.0,
            format_str="{:.1f}x", callback=self._on_vol_changed
        )

        # 5. Bitrate Slider (4 .. 60 Mbps)
        self.scale_bitrate = self._create_slider(
            main_box, "Bitrate (Mbps)", 4.0, 60.0, 1.0, 20.0,
            format_str="{:.0f} Mbps", callback=self._on_bitrate_changed
        )

        # Separator
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        btn_idr = Gtk.Button(label="⚡ Forzar Keyframe (IDR)")
        btn_idr.connect("clicked", lambda b: send_ipc_command({"command": "keyframe"}))
        btn_box.pack_start(btn_idr, True, True, 0)

        btn_restart = Gtk.Button(label="🔄 Reiniciar Stream")
        btn_restart.connect("clicked", lambda b: send_ipc_command({"command": "restart"}))
        btn_box.pack_start(btn_restart, True, True, 0)

        main_box.pack_start(btn_box, False, False, 0)

        # Periodic status refresh
        GLib.timeout_add_seconds(2, self._refresh_status)
        self._refresh_status()

    def _create_slider(self, parent_box, title, min_v, max_v, step, def_v, format_str, callback):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        label_title = Gtk.Label(label=title)
        label_title.set_alignment(0.0, 0.5)
        top_box.pack_start(label_title, True, True, 0)

        label_val = Gtk.Label(label=format_str.format(def_v))
        label_val.set_alignment(1.0, 0.5)
        top_box.pack_start(label_val, False, False, 0)
        box.pack_start(top_box, False, False, 0)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min_v, max_v, step)
        scale.set_value(def_v)
        scale.set_draw_value(False)
        scale.connect("value-changed", lambda s: self._on_scale_val(s, label_val, format_str, callback))
        box.pack_start(scale, False, False, 0)

        parent_box.pack_start(box, False, False, 0)
        return scale

    def _on_scale_val(self, scale, label_val, format_str, callback):
        val = scale.get_value()
        label_val.set_text(format_str.format(val))
        callback(val)

    def _on_res_changed(self, combo):
        txt = combo.get_active_text()
        heights = {"720p": 720, "1080p": 1080, "1440p": 1440, "4K (2160p)": 2160}
        h = heights.get(txt, 1080)
        send_ipc_command({"command": "resolution", "height": h})

    def _on_fps_changed(self, combo):
        txt = combo.get_active_text()
        fps = int(txt.split()[0])
        send_ipc_command({"command": "fps", "fps": fps})

    def _on_3d_changed(self, val):
        send_ipc_command({"command": "depth_intensity", "value": val})

    def _on_sat_changed(self, val):
        send_ipc_command({"command": "saturation", "value": val})

    def _on_gamma_changed(self, val):
        send_ipc_command({"command": "gamma", "value": val})

    def _on_vol_changed(self, val):
        send_ipc_command({"command": "volume", "value": val})

    def _on_bitrate_changed(self, val):
        send_ipc_command({"command": "bitrate", "mbps": val})

    def _refresh_status(self):
        res = send_ipc_command({"command": "status"})
        if res.get("status") == "ok":
            self.status_label.set_text("🟢 Servidor Pling Activo (Puerto 3000)")
            fps = res.get("current_fps", 0)
            bitrate = res.get("bitrate_mbps", 20.0)
            rtt = res.get("estimated_rtt_ms", 0.0)
            clients = res.get("clients_connected", 0)
            self.metrics_label.set_text(
                f"Clientes: {clients} | FPS: {fps:.1f} | Bitrate: {bitrate:.1f} Mbps | RTT: {rtt:.1f} ms"
            )
        else:
            self.status_label.set_text("🔴 Servidor Pling Detenido o Iniciando")
            self.metrics_label.set_text("El servicio systemd pling-server se iniciará automáticamente")
        return True

def main():
    if Gtk is None:
        print("GTK3 no está disponible en este entorno Python")
        sys.exit(1)
    win = PlingControlWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
