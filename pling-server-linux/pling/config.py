"""
Configuration management for Pling Server Linux.
"""

import os
import json
from dataclasses import dataclass, asdict

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/pling/config.json")

@dataclass
class PlingConfig:
    # Network & Protocol
    tcp_port: int = 3000
    udp_port: int = 7001
    video_packet_type: int = 6  # 6 matches PlingQuestAndroid PlingClient.kt, 0 for compat
    broadcast_interval: float = 0.5  # seconds
    ipc_socket_path: str = "/tmp/pling-server.sock"
    auto_adb: bool = True
    god_mode_optimizations: bool = True

    # Display & Video
    width: int = 1920
    height: int = 1080
    fps: int = 60
    bitrate_mbps: int = 30
    max_bitrate_mbps: int = 40
    capture_mode: str = "auto"  # 'auto', 'kms', 'pipewire', 'x11'
    encoder: str = "hevc_vaapi"
    vaapi_device: str = "/dev/dri/renderD128"
    drm_card: str = "/dev/dri/card0"
    gop_size: int = 60  # Periodic IDR interval (1 IDR per second at 60 fps)
    
    # Audio
    audio_enabled: bool = True
    audio_sample_rate: int = 48000
    audio_channels: int = 2
    audio_chunk_samples: int = 960  # 20ms buffer (960 * 2ch * 4bytes = 7680 bytes)

    # Input Injection
    uinput_enabled: bool = True
    mouse_scroll_multiplier: float = 2.0

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
