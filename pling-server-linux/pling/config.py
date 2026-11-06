"""
Configuration management for Pling Server Linux.
Stores persistent settings matching Mac ContentView UserDefaults & Linux Tiger Lake hardware options.
"""

import os
import json
from dataclasses import dataclass, asdict
from typing import Optional

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/pling/config.json")

# Discrete resolution heights matching Mac app
HEIGHT_OPTIONS = [720, 1080, 1440, 2160]

# Supported FPS caps matching Mac app
FPS_OPTIONS = [25, 30, 60]

@dataclass
class PlingConfig:
    # Network & Protocol
    tcp_port: int = 3000
    udp_port: int = 7001
    video_packet_type: int = 6  # 6 = HEVC NAL units (PlingClient.kt default), 0 = compat
    broadcast_interval: float = 0.5  # seconds
    ipc_socket_path: str = "/tmp/pling-server.sock"
    auto_adb: bool = True
    god_mode_optimizations: bool = True

    # Display & Resolution
    target_height: int = 1080  # 720, 1080, 1440, 2160
    width: int = 1920
    height: int = 1080
    fps: int = 60              # 25, 30, 60
    display: str = ":0.0"      # X11 display or KMS connector

    # Dynamic Bitrate & AIMD Flow Control (Mac parity)
    bitrate_mode: str = "auto" # 'auto' (AIMD from Quest ACKs) or 'manual'
    bitrate_mbps: float = 20.0 # Active bitrate in Mbps
    wifi_max_mbps: float = 24.0
    usb_max_mbps: float = 60.0
    min_bitrate_mbps: float = 4.0
    gop_size: int = 60         # IDR keyframe interval in frames

    # Hardware Video Encoders & Screen Capture
    encoder: str = "auto"      # 'auto', 'vaapi' (Tiger Lake Gen12), 'qsv', 'x265', 'x264'
    capture_mode: str = "auto" # 'auto', 'kms', 'pipewire', 'x11'
    vaapi_device: str = "/dev/dri/renderD128"
    drm_card: str = "/dev/dri/card0"

    # Color & Audio Sliders (Quest client control)
    gamma: float = 1.0         # 0.5 .. 5.0 (Default 1.0)
    saturation: float = 1.0    # 0.0 .. 2.0 (Default 1.0)
    volume_boost: float = 1.0  # 0.0 .. 10.0 (Default 1.0x, applied to PCM stream)

    # Audio Streaming (PipeWire / PulseAudio)
    audio_enabled: bool = True
    audio_sample_rate: int = 48000
    audio_channels: int = 2
    audio_chunk_samples: int = 960  # 20ms buffer (960 * 2ch * 4bytes = 7680 bytes)

    # Input Injection
    uinput_enabled: bool = True
    mouse_scroll_multiplier: float = 2.0

    def compute_output_dimensions(self, physical_w: int = 1920, physical_h: int = 1080) -> tuple[int, int]:
        """
        Calculates even output dimensions adhering to target_height and aspect ratio,
        exactly like Mac ContentView.swift updateStreamConfiguration().
        """
        requested_h = self.target_height
        if 0 < requested_h < physical_h:
            out_h = requested_h - (requested_h % 2)
            ratio = float(physical_w) / float(physical_h)
            w = int(round(out_h * ratio))
            out_w = w + (w % 2)
        else:
            out_h = physical_h - (physical_h % 2)
            out_w = physical_w - (physical_w % 2)
        return max(640, out_w), max(360, out_h)

    def ideal_bitrate_mbps(self) -> float:
        """
        Computes ideal bitrate (Mbps) for current resolution & fps before network caps:
        bpp = 0.085 for fps >= 50, else 0.12 (Mac ContentView logic).
        """
        w = float(max(640, self.width))
        h = float(max(360, self.height))
        fps = float(max(1, self.fps))
        bpp = 0.085 if fps >= 50 else 0.12
        return (w * h * fps * bpp) / 1_000_000.0

    @classmethod
    def load(cls, path: str = DEFAULT_CONFIG_PATH) -> "PlingConfig":
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                valid_fields = {f: data[f] for f in data if f in cls.__dataclass_fields__}
                return cls(**valid_fields)
            except Exception as e:
                print(f"[Config] Warning: Failed to load config from {path}: {e}")
        return cls()

    def save(self, path: str = DEFAULT_CONFIG_PATH) -> None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except Exception as e:
            print(f"[Config] Error saving config to {path}: {e}")
